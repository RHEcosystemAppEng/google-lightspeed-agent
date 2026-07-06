#!/usr/bin/env bats
# =============================================================================
# Shell tests for deploy/cloudrun/deploy.sh
# =============================================================================
#
# Tests argument parsing, validation, and function behavior using the source
# guard to import deploy.sh functions without triggering main execution.

DEPLOY_SCRIPT="deploy/cloudrun/deploy.sh"
MOCK_GCLOUD="tests/shell/mock_gcloud.sh"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# Source deploy.sh with mock gcloud and minimal required env vars.
# The source guard stops execution before the main deployment section,
# making all functions and variables available for testing.
source_deploy() {
    # Required env vars — set defaults so validation passes
    export GOOGLE_CLOUD_PROJECT="${GOOGLE_CLOUD_PROJECT:-test-project}"
    export GOOGLE_CLOUD_LOCATION="${GOOGLE_CLOUD_LOCATION:-us-central1}"
    export ENABLE_LB_AGENT="${ENABLE_LB_AGENT:-false}"
    export ENABLE_LB_HANDLER="${ENABLE_LB_HANDLER:-false}"
    export ENABLE_CLOUD_ARMOR_AGENT="${ENABLE_CLOUD_ARMOR_AGENT:-false}"
    export ENABLE_CLOUD_ARMOR_HANDLER="${ENABLE_CLOUD_ARMOR_HANDLER:-false}"

    # Forward arguments to deploy.sh's argument parser via positional params
    set -- "$@"
    source "$MOCK_GCLOUD"
    source "$DEPLOY_SCRIPT"
}

setup() {
    GCLOUD_LOG_FILE="$(mktemp)"
    export GCLOUD_LOG_FILE
    export MOCK_GCLOUD_FAIL_DESCRIBE="false"
    export MOCK_GCLOUD_FORMAT_VALUE=""
}

teardown() {
    rm -f "$GCLOUD_LOG_FILE"
}

# ===========================================================================
# Argument parsing
# ===========================================================================

@test "default DEPLOY_SERVICE is 'all'" {
    source_deploy
    [[ "$DEPLOY_SERVICE" == "all" ]]
}

@test "--service sets DEPLOY_SERVICE" {
    source_deploy --service agent
    [[ "$DEPLOY_SERVICE" == "agent" ]]
}

@test "--dry-run sets DRY_RUN=true" {
    source_deploy --dry-run
    [[ "$DRY_RUN" == "true" ]]
}

@test "--allow-unauthenticated sets ALLOW_UNAUTH=true" {
    source_deploy --allow-unauthenticated
    [[ "$ALLOW_UNAUTH" == "true" ]]
}

@test "unknown flag exits with error" {
    run bash -c '
        source tests/shell/mock_gcloud.sh
        export GOOGLE_CLOUD_PROJECT=test-project
        bash deploy/cloudrun/deploy.sh --invalid-flag
    '
    [[ "$status" -ne 0 ]]
    [[ "$output" == *"Unknown option"* ]]
}

# ===========================================================================
# Variable validation
# ===========================================================================

@test "missing GOOGLE_CLOUD_PROJECT exits with error" {
    run bash -c '
        source tests/shell/mock_gcloud.sh
        unset GOOGLE_CLOUD_PROJECT
        bash deploy/cloudrun/deploy.sh
    '
    [[ "$status" -ne 0 ]]
    [[ "$output" == *"GOOGLE_CLOUD_PROJECT"* ]]
}

@test "missing AGENT_DOMAIN_NAME with ENABLE_LB_AGENT=true exits with error" {
    run bash -c '
        source tests/shell/mock_gcloud.sh
        export GOOGLE_CLOUD_PROJECT=test-project
        export ENABLE_LB_AGENT=true
        export AGENT_DOMAIN_NAME=""
        bash deploy/cloudrun/deploy.sh
    '
    [[ "$status" -ne 0 ]]
    [[ "$output" == *"AGENT_DOMAIN_NAME"* ]]
}

@test "ENABLE_CLOUD_ARMOR_AGENT without ENABLE_LB_AGENT exits with error" {
    run bash -c '
        source tests/shell/mock_gcloud.sh
        export GOOGLE_CLOUD_PROJECT=test-project
        export ENABLE_CLOUD_ARMOR_AGENT=true
        export ENABLE_LB_AGENT=false
        bash deploy/cloudrun/deploy.sh
    '
    [[ "$status" -ne 0 ]]
    [[ "$output" == *"ENABLE_CLOUD_ARMOR_AGENT requires ENABLE_LB_AGENT"* ]]
}

# ===========================================================================
# update_agentcard_urls behavior
# ===========================================================================

@test "update_agentcard_urls uses GCLB domain when LB enabled" {
    export ENABLE_LB_AGENT="true"
    export AGENT_DOMAIN_NAME="agent.example.com"
    export ENABLE_LB_HANDLER="true"
    export HANDLER_DOMAIN_NAME="handler.example.com"
    export MOCK_GCLOUD_FAIL_DESCRIBE="true"
    source_deploy

    run update_agentcard_urls
    # The function should attempt to update with the GCLB domains
    [[ "$output" == *"https://agent.example.com"* ]]
    [[ "$output" == *"https://handler.example.com"* ]]
}

# ===========================================================================
# Dry-run end-to-end
# ===========================================================================

@test "dry-run outputs [DRY-RUN] prefix for mutating commands" {
    run bash -c '
        source tests/shell/mock_gcloud.sh
        export GOOGLE_CLOUD_PROJECT=test-project
        bash deploy/cloudrun/deploy.sh --service agent --dry-run
    '
    [[ "$output" == *"DRY-RUN mode"* ]]
    [[ "$output" == *"[DRY-RUN] gcloud"* ]]
}

@test "dry-run intercepts describe/list commands" {
    source_deploy --dry-run

    # In dry-run, gcloud describe should return 1 (intercepted)
    local rc=0
    gcloud run services describe test-service 2>/dev/null || rc=$?
    [[ "$rc" -eq 1 ]]

    # In dry-run, gcloud list should return 1 (intercepted)
    rc=0
    gcloud run services list 2>/dev/null || rc=$?
    [[ "$rc" -eq 1 ]]
}

@test "dry-run prints mutating commands without executing" {
    source_deploy --dry-run

    run gcloud run services update test-service --quiet
    [[ "$status" -eq 0 ]]
    [[ "$output" == "[DRY-RUN] gcloud run services update test-service --quiet" ]]
}

# ===========================================================================
# Ingress behavior
# ===========================================================================

@test "deploy_handler calls gcloud run services replace" {
    source_deploy
    run deploy_handler
    [[ "$status" -eq 0 ]]
    grep -q "gcloud run services replace" "$GCLOUD_LOG_FILE"
}

@test "deploy_handler adds IAM binding when ALLOW_UNAUTH=true" {
    source_deploy --allow-unauthenticated
    run deploy_handler
    [[ "$status" -eq 0 ]]
    grep -q "add-iam-policy-binding" "$GCLOUD_LOG_FILE"
    grep -q "allUsers" "$GCLOUD_LOG_FILE"
}

@test "deploy_agent sets ingress via gcloud when LB disabled" {
    source_deploy
    ENABLE_LB_AGENT="false"

    # deploy_agent calls gcloud run services replace, which the mock intercepts
    run deploy_agent
    [[ "$status" -eq 0 ]]

    # Check that gcloud was called for the replace
    grep -q "gcloud run services replace" "$GCLOUD_LOG_FILE"
}

@test "setup_service_lb sets ingress to internal-and-cloud-load-balancing" {
    export ENABLE_LB_AGENT="true"
    export AGENT_DOMAIN_NAME="agent.example.com"
    source_deploy

    run setup_service_lb "agent" "lightspeed-agent" "agent.example.com" "false" "1"
    [[ "$status" -eq 0 ]]

    # Verify ingress update was called
    grep -q "internal-and-cloud-load-balancing" "$GCLOUD_LOG_FILE"
}

# ===========================================================================
# Dry-run with LB and pubsub
# ===========================================================================

@test "dry-run with setup_service_lb prints NEG, backend, and forwarding rule creates" {
    export ENABLE_LB_AGENT="true"
    export AGENT_DOMAIN_NAME="agent.example.com"
    source_deploy --dry-run

    run setup_service_lb "agent" "lightspeed-agent" "agent.example.com" "false" "1"
    [[ "$status" -eq 0 ]]
    [[ "$output" == *"[DRY-RUN] gcloud compute network-endpoint-groups create"* ]]
    [[ "$output" == *"[DRY-RUN] gcloud compute backend-services create"* ]]
    [[ "$output" == *"[DRY-RUN] gcloud compute forwarding-rules create"* ]]
}

@test "dry-run with Cloud Armor prints WAF rule creates" {
    export ENABLE_LB_AGENT="true"
    export AGENT_DOMAIN_NAME="agent.example.com"
    export ENABLE_CLOUD_ARMOR_AGENT="true"
    source_deploy --dry-run

    run setup_service_lb "agent" "lightspeed-agent" "agent.example.com" "true" "1"
    [[ "$status" -eq 0 ]]
    [[ "$output" == *"[DRY-RUN] gcloud compute security-policies create"* ]]
    [[ "$output" == *"[DRY-RUN] gcloud compute security-policies rules create"* ]]
    [[ "$output" == *"[DRY-RUN] gcloud compute security-policies rules add-preconfig-waf-exclusion"* ]]
}

@test "configure_pubsub_push skips when ENABLE_MARKETPLACE is not true" {
    export ENABLE_MARKETPLACE="false"
    source_deploy

    run configure_pubsub_push
    [[ "$status" -eq 0 ]]
    [[ "$output" == *"Skipping Pub/Sub"* ]]
}

@test "configure_pubsub_push creates subscription when handler URL available" {
    export ENABLE_MARKETPLACE="true"
    export MOCK_GCLOUD_FORMAT_VALUE="https://handler.example.com"
    source_deploy

    run configure_pubsub_push
    [[ "$status" -eq 0 ]]
    grep -q "pubsub subscriptions" "$GCLOUD_LOG_FILE"
}

@test "dry-run configure_pubsub_push returns early when handler URL unavailable" {
    source_deploy --dry-run

    run configure_pubsub_push
    [[ "$status" -eq 0 ]]
    # In dry-run, gcloud describe returns 1, so handler_url is empty → early return
    [[ "$output" == *"Could not retrieve"* || "$output" == *"Skipping"* ]]
}

@test "show_service_info skips gcloud in dry-run mode" {
    source_deploy --dry-run

    run show_service_info "lightspeed-agent"
    [[ "$status" -eq 0 ]]
    [[ "$output" == *"dry-run"* ]]
}

@test "update_agentcard_urls skips in dry-run mode" {
    source_deploy --dry-run

    run update_agentcard_urls
    [[ "$status" -eq 0 ]]
    [[ "$output" == *"Dry-run: skipping"* ]]
}
