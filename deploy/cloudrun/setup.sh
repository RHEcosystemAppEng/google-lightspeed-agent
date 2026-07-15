#!/bin/bash
# =============================================================================
# Google Cloud Run Deployment Setup Script
# =============================================================================
#
# This script sets up all required GCP services for the Lightspeed Agent:
# - Enables required APIs
# - Creates runtime service account with appropriate permissions
# - Creates Pub/Sub Invoker service account (for push subscription auth)
# - Creates secrets in Secret Manager
# - Creates Pub/Sub topic for marketplace events
#
# Usage:
#   ./deploy/cloudrun/setup.sh
#
# Prerequisites:
#   - gcloud CLI installed and authenticated
#   - GCP project created with billing enabled
#
# =============================================================================

set -euo pipefail

# Color output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

wait_for_sa() {
    local sa_email="$1"
    local max_wait=30
    local waited=0
    while ! gcloud iam service-accounts describe "$sa_email" --project="$PROJECT_ID" &>/dev/null; do
        if (( waited >= max_wait )); then
            log_error "Service account $sa_email not visible after ${max_wait}s"
            return 1
        fi
        sleep 2
        waited=$((waited + 2))
    done
}

# =============================================================================
# Configuration
# =============================================================================

# Required: Set these before running
PROJECT_ID="${GOOGLE_CLOUD_PROJECT:-}"
REGION="${GOOGLE_CLOUD_LOCATION:-us-central1}"
SERVICE_NAME="${SERVICE_NAME:-lightspeed-agent}"
SERVICE_ACCOUNT_NAME="${SERVICE_ACCOUNT_NAME:-${SERVICE_NAME}}"
HANDLER_SERVICE_NAME="${HANDLER_SERVICE_NAME:-marketplace-handler}"
DB_INSTANCE_NAME="${DB_INSTANCE_NAME:-lightspeed-agent-db}"
REDIS_INSTANCE_NAME="${REDIS_INSTANCE_NAME:-lightspeed-redis}"
SERVICE_ACCOUNT="${SERVICE_ACCOUNT_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"

# Pub/Sub Invoker Service Account (separate SA for push subscription auth)
PUBSUB_INVOKER_NAME="${PUBSUB_INVOKER_NAME:-pubsub-invoker}"
PUBSUB_INVOKER_SA="${PUBSUB_INVOKER_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"

# Optional features
ENABLE_MARKETPLACE="${ENABLE_MARKETPLACE:-true}"

# Per-service load balancer configuration
ENABLE_LB_AGENT="${ENABLE_LB_AGENT:-false}"
ENABLE_LB_HANDLER="${ENABLE_LB_HANDLER:-false}"
AGENT_DOMAIN_NAME="${AGENT_DOMAIN_NAME:-}"
HANDLER_DOMAIN_NAME="${HANDLER_DOMAIN_NAME:-}"
LB_NAME="${LB_NAME:-lightspeed-lb}"

# Per-instance Secret Manager secret names (for multi-instance support)
DATABASE_URL_SECRET="${DATABASE_URL_SECRET:-database-url}"
SESSION_DATABASE_URL_SECRET="${SESSION_DATABASE_URL_SECRET:-session-database-url}"
DCR_ENCRYPTION_KEY_SECRET="${DCR_ENCRYPTION_KEY_SECRET:-dcr-encryption-key}"
REDIS_URL_SECRET="${REDIS_URL_SECRET:-rate-limit-redis-url}"
REDIS_CA_CERT_SECRET="${REDIS_CA_CERT_SECRET:-redis-ca-cert}"

# VPC connector for Cloud Run → Redis access
VPC_CONNECTOR_NAME="${VPC_CONNECTOR_NAME:-ls-redis-conn}"
VPC_CONNECTOR_RANGE="${VPC_CONNECTOR_RANGE:-10.8.0.0/28}"
VPC_NETWORK="${VPC_NETWORK:-default}"

# Cloud SQL configuration
DB_TIER="${DB_TIER:-db-g1-small}"
DB_VERSION="${DB_VERSION:-POSTGRES_16}"
DB_EDITION="${DB_EDITION:-ENTERPRISE}"

# Redis configuration
REDIS_TIER="${REDIS_TIER:-basic}"
REDIS_SIZE_GB="${REDIS_SIZE_GB:-1}"

# Validate required variables
if [[ -z "$PROJECT_ID" ]]; then
    log_error "GOOGLE_CLOUD_PROJECT environment variable is required"
    echo "  export GOOGLE_CLOUD_PROJECT=your-project-id"
    exit 1
fi

if [[ "$ENABLE_LB_AGENT" == "true" && -z "$AGENT_DOMAIN_NAME" ]]; then
    log_error "AGENT_DOMAIN_NAME is required when ENABLE_LB_AGENT=true"
    echo "  export AGENT_DOMAIN_NAME=agent.example.com"
    exit 1
fi

if [[ "$ENABLE_LB_HANDLER" == "true" && -z "$HANDLER_DOMAIN_NAME" ]]; then
    log_error "HANDLER_DOMAIN_NAME is required when ENABLE_LB_HANDLER=true"
    echo "  export HANDLER_DOMAIN_NAME=dcr.example.com"
    exit 1
fi

log_info "Setting up Cloud Run deployment for project: $PROJECT_ID"
log_info "Region: $REGION"
log_info "Service: $SERVICE_NAME"
log_info "Service account: $SERVICE_ACCOUNT_NAME"
log_info "Handler service: $HANDLER_SERVICE_NAME"
log_info "DB instance: $DB_INSTANCE_NAME"
log_info "Pub/Sub invoker SA: $PUBSUB_INVOKER_NAME"
log_info "Marketplace integration: $ENABLE_MARKETPLACE"
log_info "Redis instance: $REDIS_INSTANCE_NAME"
log_info "VPC connector: $VPC_CONNECTOR_NAME"
log_info "DB secret: $DATABASE_URL_SECRET"
log_info "Redis secret: $REDIS_URL_SECRET"
log_info "Agent load balancer: $ENABLE_LB_AGENT"
log_info "Handler load balancer: $ENABLE_LB_HANDLER"

# =============================================================================
# Step 1: Enable Required APIs
# =============================================================================
log_info "Enabling required GCP APIs..."

# Required APIs and their purposes:
# - run: Cloud Run service hosting
# - cloudbuild: Build container images from source
# - secretmanager: Store and access secrets (API keys, credentials)
# - aiplatform: Access Vertex AI / Gemini models
# - cloudscheduler: Schedule usage reporting jobs
# - pubsub: Receive marketplace procurement events
# - servicecontrol: Report usage metrics for billing
# - servicemanagement: Manage service configuration
# - redis: Cloud Memorystore for Redis (rate limiting backend)
# - vpcaccess: Serverless VPC Access connectors (Cloud Run to Redis)
apis=(
    "run.googleapis.com"
    "cloudbuild.googleapis.com"
    "secretmanager.googleapis.com"
    "aiplatform.googleapis.com"
    "cloudscheduler.googleapis.com"
    "pubsub.googleapis.com"
    "servicecontrol.googleapis.com"
    "servicemanagement.googleapis.com"
    "redis.googleapis.com"
    "vpcaccess.googleapis.com"
    "sqladmin.googleapis.com"
)

# Add Compute Engine API when any load balancer is enabled
if [[ "$ENABLE_LB_AGENT" == "true" || "$ENABLE_LB_HANDLER" == "true" ]]; then
    apis+=("compute.googleapis.com")
fi

for api in "${apis[@]}"; do
    log_info "  Enabling $api..."
    gcloud services enable "$api" --project="$PROJECT_ID" --quiet || true
done

# =============================================================================
# Step 2: Create Service Account
# =============================================================================
log_info "Creating service account: $SERVICE_ACCOUNT"

# Create service account if it doesn't exist
if ! gcloud iam service-accounts describe "$SERVICE_ACCOUNT" --project="$PROJECT_ID" &>/dev/null; then
    gcloud iam service-accounts create "$SERVICE_ACCOUNT_NAME" \
        --display-name="Lightspeed Agent Service Account" \
        --description="Service account for the Red Hat Lightspeed Agent for Google Cloud" \
        --project="$PROJECT_ID"
    log_info "Service account created, waiting for propagation..."
    wait_for_sa "$SERVICE_ACCOUNT"
else
    log_info "Service account already exists"
fi

# Grant required roles
log_info "Granting IAM roles to service account..."

# IAM roles and their purposes:
# - secretmanager.secretAccessor: Read secrets (API keys, credentials)
# - aiplatform.user: Access Vertex AI / Gemini models
# - pubsub.subscriber: Receive marketplace procurement events
# - pubsub.publisher: Publish events (if needed for async processing)
# - servicemanagement.serviceController: Report usage to Service Control API
# - logging.logWriter: Write logs to Cloud Logging
# - monitoring.metricWriter: Write metrics to Cloud Monitoring
# - cloudsql.client: Connect to Cloud SQL instances
# - serviceusage.serviceUsageConsumer: Bill API calls (Procurement API) to this project
#
# Note: roles/run.invoker is NOT granted here. It is granted to the
# separate Pub/Sub Invoker SA on the marketplace-handler service
# (see deploy.sh). This follows the principle of least privilege.
roles=(
    "roles/secretmanager.secretAccessor"
    "roles/aiplatform.user"
    "roles/pubsub.subscriber"
    "roles/pubsub.publisher"
    "roles/servicemanagement.serviceController"
    "roles/logging.logWriter"
    "roles/monitoring.metricWriter"
    "roles/cloudsql.client"
    "roles/serviceusage.serviceUsageConsumer"
)

for role in "${roles[@]}"; do
    log_info "  Granting $role..."
    gcloud projects add-iam-policy-binding "$PROJECT_ID" \
        --member="serviceAccount:$SERVICE_ACCOUNT" \
        --role="$role" \
        --quiet || true
done

# =============================================================================
# Step 3: Create Secrets in Secret Manager
# =============================================================================
log_info "Setting up Secret Manager secrets..."

# Required secrets
secrets=(
    "redhat-sso-client-id"
    "redhat-sso-client-secret"
)

# DCR (Dynamic Client Registration) secrets
dcr_secrets=(
    "gma-client-id"
    "gma-client-secret"
    "$DCR_ENCRYPTION_KEY_SECRET"
)

# Database secrets (PostgreSQL for production - REQUIRED)
db_secrets=(
    "$DATABASE_URL_SECRET"
    "$SESSION_DATABASE_URL_SECRET"
)

# Rate limiting (Redis - REQUIRED for agent)
redis_secrets=(
    "$REDIS_URL_SECRET"
    "$REDIS_CA_CERT_SECRET"
)

# Combine all optional secrets
optional_secrets=("${dcr_secrets[@]}" "${db_secrets[@]}" "${redis_secrets[@]}")

for secret in "${secrets[@]}"; do
    if ! gcloud secrets describe "$secret" --project="$PROJECT_ID" &>/dev/null; then
        log_info "  Creating secret: $secret"
        echo -n "PLACEHOLDER" | gcloud secrets create "$secret" \
            --data-file=- \
            --project="$PROJECT_ID" \
            --replication-policy="automatic"
        log_warn "  Secret '$secret' created with placeholder value. Update it with:"
        log_warn "    echo -n 'your-value' | gcloud secrets versions add $secret --data-file=- --project=$PROJECT_ID"
    else
        log_info "  Secret '$secret' already exists"
    fi

    # Grant access to service account
    gcloud secrets add-iam-policy-binding "$secret" \
        --member="serviceAccount:$SERVICE_ACCOUNT" \
        --role="roles/secretmanager.secretAccessor" \
        --project="$PROJECT_ID" \
        --quiet || true
done

# Create DCR and database secrets
log_info "Setting up DCR and database secrets..."
for secret in "${optional_secrets[@]}"; do
    if ! gcloud secrets describe "$secret" --project="$PROJECT_ID" &>/dev/null; then
        log_info "  Creating secret: $secret"
        echo -n "PLACEHOLDER" | gcloud secrets create "$secret" \
            --data-file=- \
            --project="$PROJECT_ID" \
            --replication-policy="automatic"
        log_warn "  Secret '$secret' created with placeholder. Update after Cloud SQL setup."
    else
        log_info "  Secret '$secret' already exists"
    fi

    # Grant access to service account
    gcloud secrets add-iam-policy-binding "$secret" \
        --member="serviceAccount:$SERVICE_ACCOUNT" \
        --role="roles/secretmanager.secretAccessor" \
        --project="$PROJECT_ID" \
        --quiet || true
done

# Create OTel Collector config secret (from config file, not placeholder)
log_info "Setting up OTel Collector config secret..."
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OTEL_CONFIG_FILE="$SCRIPT_DIR/otel-collector-config.yaml"
if [[ -f "$OTEL_CONFIG_FILE" ]]; then
    if ! gcloud secrets describe "otel-collector-config" --project="$PROJECT_ID" &>/dev/null; then
        log_info "  Creating secret: otel-collector-config"
        gcloud secrets create "otel-collector-config" \
            --data-file="$OTEL_CONFIG_FILE" \
            --project="$PROJECT_ID" \
            --replication-policy="automatic"
    else
        log_info "  Secret 'otel-collector-config' already exists"
    fi

    gcloud secrets add-iam-policy-binding "otel-collector-config" \
        --member="serviceAccount:$SERVICE_ACCOUNT" \
        --role="roles/secretmanager.secretAccessor" \
        --project="$PROJECT_ID" \
        --quiet || true
else
    log_warn "OTel Collector config not found at $OTEL_CONFIG_FILE, skipping"
fi

# =============================================================================
# Step 4: Create Pub/Sub Invoker Service Account and Topic (Optional)
# =============================================================================
if [[ "$ENABLE_MARKETPLACE" == "true" ]]; then
    log_info "Setting up Pub/Sub for Marketplace integration..."

    # -------------------------------------------------------------------------
    # Create Pub/Sub Invoker Service Account
    # -------------------------------------------------------------------------
    # This is a SEPARATE service account from the runtime SA, used exclusively
    # to authenticate Pub/Sub push subscriptions when invoking Cloud Run.
    # Following the principle of least privilege, it only has roles/run.invoker
    # on the marketplace-handler service (granted in deploy.sh after the
    # handler is deployed).
    log_info "Creating Pub/Sub Invoker service account: $PUBSUB_INVOKER_SA"

    if ! gcloud iam service-accounts describe "$PUBSUB_INVOKER_SA" --project="$PROJECT_ID" &>/dev/null; then
        gcloud iam service-accounts create "$PUBSUB_INVOKER_NAME" \
            --display-name="Pub/Sub Invoker SA" \
            --description="Authorizes Pub/Sub push subscriptions to invoke Cloud Run services" \
            --project="$PROJECT_ID"
        log_info "Pub/Sub Invoker service account created, waiting for propagation..."
        wait_for_sa "$PUBSUB_INVOKER_SA"
    else
        log_info "Pub/Sub Invoker service account already exists"
    fi

    # Grant the Pub/Sub Invoker SA permission to act as itself.
    # Required because we authenticate AS this SA and create a subscription
    # that uses it as the push-auth identity.
    log_info "Granting Service Account User to Pub/Sub Invoker SA on itself..."
    gcloud iam service-accounts add-iam-policy-binding "$PUBSUB_INVOKER_SA" \
        --member="serviceAccount:$PUBSUB_INVOKER_SA" \
        --role="roles/iam.serviceAccountUser" \
        --project="$PROJECT_ID" \
        --quiet || true

    # Grant Cloud Build SA permission to impersonate the Pub/Sub Invoker SA.
    # Required for cross-project topic subscriptions where Cloud Build uses
    # --impersonate-service-account to create the push subscription.
    PROJECT_NUMBER=$(gcloud projects describe "$PROJECT_ID" --format='value(projectNumber)')
    CB_SA="${PROJECT_NUMBER}@cloudbuild.gserviceaccount.com"
    log_info "Granting Token Creator to Cloud Build SA on Pub/Sub Invoker SA..."
    gcloud iam service-accounts add-iam-policy-binding "$PUBSUB_INVOKER_SA" \
        --member="serviceAccount:$CB_SA" \
        --role="roles/iam.serviceAccountTokenCreator" \
        --project="$PROJECT_ID" \
        --quiet || true

    # Grant the Pub/Sub Invoker SA the Pub/Sub Editor role in the project.
    # Required so that deploy.sh can impersonate this SA to create a push
    # subscription attached to the marketplace topic (which is typically in a
    # different GCP project, e.g. Google's cloudcommerceproc-prod).
    log_info "Granting roles/pubsub.editor to Pub/Sub Invoker SA..."
    gcloud projects add-iam-policy-binding "$PROJECT_ID" \
        --member="serviceAccount:$PUBSUB_INVOKER_SA" \
        --role="roles/pubsub.editor" \
        --quiet || true

    # -------------------------------------------------------------------------
    # Create Pub/Sub Topic
    # -------------------------------------------------------------------------
    PUBSUB_TOPIC="${PUBSUB_TOPIC:-marketplace-entitlements}"

    # If PUBSUB_TOPIC is a fully-qualified path (projects/.../topics/...),
    # the topic lives in another GCP project (e.g. Google Cloud Marketplace).
    # Skip creation — the topic is managed externally.
    if [[ "$PUBSUB_TOPIC" == projects/* ]]; then
        log_info "Pub/Sub topic is a cross-project reference: $PUBSUB_TOPIC"
        log_info "Skipping topic creation (managed externally)"
    elif ! gcloud pubsub topics describe "$PUBSUB_TOPIC" --project="$PROJECT_ID" &>/dev/null; then
        gcloud pubsub topics create "$PUBSUB_TOPIC" --project="$PROJECT_ID"
        log_info "Pub/Sub topic '$PUBSUB_TOPIC' created"
    else
        log_info "Pub/Sub topic '$PUBSUB_TOPIC' already exists"
    fi

    # Note: The push subscription is created in deploy.sh after the
    # marketplace-handler is deployed, because the push endpoint URL
    # (the handler's Cloud Run URL) is not known until then.
    log_info "Pub/Sub push subscription will be configured by deploy.sh"

    # Auto-generate DCR encryption key if the secret still has a placeholder value
    CURRENT_DCR_VALUE=$(gcloud secrets versions access latest --secret="$DCR_ENCRYPTION_KEY_SECRET" --project="$PROJECT_ID" 2>/dev/null || echo "")
    if [[ "$CURRENT_DCR_VALUE" == "PLACEHOLDER" || -z "$CURRENT_DCR_VALUE" ]]; then
        log_info "Generating DCR encryption key..."
        python3 -c "import os, base64; print(base64.urlsafe_b64encode(os.urandom(32)).decode(), end='')" \
            | gcloud secrets versions add "$DCR_ENCRYPTION_KEY_SECRET" --data-file=- --project="$PROJECT_ID"
        log_info "Secret '$DCR_ENCRYPTION_KEY_SECRET' populated with generated Fernet key"
    else
        log_info "Secret '$DCR_ENCRYPTION_KEY_SECRET' already has a non-placeholder value"
    fi
else
    log_info "Skipping Pub/Sub setup (ENABLE_MARKETPLACE=false)"
fi

# =============================================================================
# Step 5: Create Cloud SQL Instance and Databases
# =============================================================================
log_info "Setting up Cloud SQL instance: $DB_INSTANCE_NAME"

if ! gcloud sql instances describe "$DB_INSTANCE_NAME" --project="$PROJECT_ID" &>/dev/null; then
    log_info "Creating Cloud SQL instance (this may take several minutes)..."
    gcloud sql instances create "$DB_INSTANCE_NAME" \
        --database-version="$DB_VERSION" \
        --edition="$DB_EDITION" \
        --tier="$DB_TIER" \
        --region="$REGION" \
        --project="$PROJECT_ID" \
        --ssl-mode=ENCRYPTED_ONLY \
        --quiet
    log_info "Cloud SQL instance '$DB_INSTANCE_NAME' created"
else
    log_info "Cloud SQL instance '$DB_INSTANCE_NAME' already exists"
fi

# Create databases (idempotent — gcloud returns success if already exists)
log_info "Creating databases..."
gcloud sql databases create lightspeed_agent \
    --instance="$DB_INSTANCE_NAME" --project="$PROJECT_ID" 2>/dev/null || true
gcloud sql databases create agent_sessions \
    --instance="$DB_INSTANCE_NAME" --project="$PROJECT_ID" 2>/dev/null || true

# Create users and populate secrets (only if secrets still have placeholder values)
log_info "Creating database users and populating secrets..."

CURRENT_DB_URL=$(gcloud secrets versions access latest --secret="$DATABASE_URL_SECRET" --project="$PROJECT_ID" 2>/dev/null || echo "")
if [[ "$CURRENT_DB_URL" == "PLACEHOLDER" || -z "$CURRENT_DB_URL" ]]; then
    MARKETPLACE_DB_PASSWORD=$(python3 -c "import secrets; print(secrets.token_urlsafe(24))")
    SESSION_DB_PASSWORD=$(python3 -c "import secrets; print(secrets.token_urlsafe(24))")

    gcloud sql users create insights \
        --instance="$DB_INSTANCE_NAME" --password="$MARKETPLACE_DB_PASSWORD" \
        --project="$PROJECT_ID" 2>/dev/null || true
    gcloud sql users create sessions \
        --instance="$DB_INSTANCE_NAME" --password="$SESSION_DB_PASSWORD" \
        --project="$PROJECT_ID" 2>/dev/null || true

    CONNECTION_NAME=$(gcloud sql instances describe "$DB_INSTANCE_NAME" \
        --project="$PROJECT_ID" --format='value(connectionName)')

    echo -n "postgresql+asyncpg://insights:${MARKETPLACE_DB_PASSWORD}@/lightspeed_agent?host=/cloudsql/${CONNECTION_NAME}" \
        | gcloud secrets versions add "$DATABASE_URL_SECRET" --data-file=- --project="$PROJECT_ID"
    log_info "Secret '$DATABASE_URL_SECRET' populated with database URL"

    echo -n "postgresql+asyncpg://sessions:${SESSION_DB_PASSWORD}@/agent_sessions?host=/cloudsql/${CONNECTION_NAME}" \
        | gcloud secrets versions add "$SESSION_DATABASE_URL_SECRET" --data-file=- --project="$PROJECT_ID"
    log_info "Secret '$SESSION_DATABASE_URL_SECRET' populated with session database URL"
else
    log_info "Database secrets already have non-placeholder values, skipping population"
fi

# =============================================================================
# Step 6: Create Redis (Cloud Memorystore) Instance
# =============================================================================
log_info "Setting up Redis instance: $REDIS_INSTANCE_NAME"

if ! gcloud redis instances describe "$REDIS_INSTANCE_NAME" --region="$REGION" --project="$PROJECT_ID" &>/dev/null; then
    log_info "Creating Redis instance (this may take several minutes)..."
    gcloud redis instances create "$REDIS_INSTANCE_NAME" \
        --region="$REGION" \
        --tier="$REDIS_TIER" \
        --size="$REDIS_SIZE_GB" \
        --transit-encryption-mode=SERVER_AUTHENTICATION \
        --project="$PROJECT_ID" \
        --quiet
    log_info "Redis instance '$REDIS_INSTANCE_NAME' created"
else
    log_info "Redis instance '$REDIS_INSTANCE_NAME' already exists"
fi

# Populate Redis secrets (only if still placeholder)
CURRENT_REDIS_URL=$(gcloud secrets versions access latest --secret="$REDIS_URL_SECRET" --project="$PROJECT_ID" 2>/dev/null || echo "")
if [[ "$CURRENT_REDIS_URL" == "PLACEHOLDER" || -z "$CURRENT_REDIS_URL" ]]; then
    REDIS_HOST=$(gcloud redis instances describe "$REDIS_INSTANCE_NAME" \
        --region="$REGION" --project="$PROJECT_ID" --format='value(host)')
    REDIS_PORT=$(gcloud redis instances describe "$REDIS_INSTANCE_NAME" \
        --region="$REGION" --project="$PROJECT_ID" --format='value(port)')

    echo -n "rediss://${REDIS_HOST}:${REDIS_PORT}/0" \
        | gcloud secrets versions add "$REDIS_URL_SECRET" --data-file=- --project="$PROJECT_ID"
    log_info "Secret '$REDIS_URL_SECRET' populated with Redis URL"

    gcloud redis instances describe "$REDIS_INSTANCE_NAME" \
        --region="$REGION" --project="$PROJECT_ID" \
        --format='value(serverCaCerts[0].cert)' \
        | gcloud secrets versions add "$REDIS_CA_CERT_SECRET" --data-file=- --project="$PROJECT_ID"
    log_info "Secret '$REDIS_CA_CERT_SECRET' populated with Redis CA certificate"
else
    log_info "Redis secrets already have non-placeholder values, skipping population"
fi

# =============================================================================
# Step 7: Create VPC Connector (Cloud Run → Redis)
# =============================================================================
log_info "Setting up VPC connector: $VPC_CONNECTOR_NAME"

if ! gcloud compute networks vpc-access connectors describe "$VPC_CONNECTOR_NAME" \
    --region="$REGION" --project="$PROJECT_ID" &>/dev/null; then
    gcloud compute networks vpc-access connectors create "$VPC_CONNECTOR_NAME" \
        --region="$REGION" \
        --range="$VPC_CONNECTOR_RANGE" \
        --network="$VPC_NETWORK" \
        --project="$PROJECT_ID"
    log_info "VPC connector '$VPC_CONNECTOR_NAME' created"
else
    log_info "VPC connector '$VPC_CONNECTOR_NAME' already exists"
fi

# =============================================================================
# Step 8: Set Up Load Balancer Resources (Optional, per-service)
# =============================================================================

# Reserve a static IP and create a Google-managed SSL certificate for one service.
setup_lb_resources() {
    local service_label="$1"
    local domain_name="$2"
    local ip_name="${LB_NAME}-${service_label}-ip"
    local cert_name="${LB_NAME}-${service_label}-cert"

    log_info "Setting up ${service_label} load balancer resources..."

    if ! gcloud compute addresses describe "$ip_name" --global --project="$PROJECT_ID" &>/dev/null; then
        gcloud compute addresses create "$ip_name" --global --project="$PROJECT_ID"
        log_info "Static IP address '$ip_name' reserved"
    else
        log_info "Static IP address '$ip_name' already exists"
    fi

    log_info "${service_label^} static IP: $(gcloud compute addresses describe "$ip_name" --global --project="$PROJECT_ID" --format='value(address)')"

    if ! gcloud compute ssl-certificates describe "$cert_name" --global --project="$PROJECT_ID" &>/dev/null; then
        gcloud compute ssl-certificates create "$cert_name" --domains="$domain_name" --global --project="$PROJECT_ID"
        log_info "Managed SSL certificate '$cert_name' created for $domain_name"
    else
        log_info "Managed SSL certificate '$cert_name' already exists"
    fi
}

[[ "$ENABLE_LB_AGENT" == "true" ]] && setup_lb_resources "agent" "$AGENT_DOMAIN_NAME"
[[ "$ENABLE_LB_HANDLER" == "true" ]] && setup_lb_resources "handler" "$HANDLER_DOMAIN_NAME"

if [[ "$ENABLE_LB_AGENT" != "true" && "$ENABLE_LB_HANDLER" != "true" ]]; then
    log_info "Skipping load balancer setup (no per-service LBs enabled)"
fi

# =============================================================================
# Summary
# =============================================================================
echo ""
log_info "=========================================="
log_info "Setup complete!"
log_info "=========================================="
echo ""
echo "Resources created:"
echo "  Runtime SA:         $SERVICE_ACCOUNT"
if [[ "$ENABLE_MARKETPLACE" == "true" ]]; then
    echo "  Pub/Sub Invoker SA: $PUBSUB_INVOKER_SA"
fi
echo "  Cloud SQL:          $DB_INSTANCE_NAME"
echo "  Redis:              $REDIS_INSTANCE_NAME"
echo "  VPC connector:      $VPC_CONNECTOR_NAME"
echo ""
echo "Secrets populated automatically:"
echo "  $DATABASE_URL_SECRET"
echo "  $SESSION_DATABASE_URL_SECRET"
echo "  $REDIS_URL_SECRET"
echo "  $REDIS_CA_CERT_SECRET"
if [[ "$ENABLE_MARKETPLACE" == "true" ]]; then
    echo "  $DCR_ENCRYPTION_KEY_SECRET (auto-generated Fernet key)"
fi
if [[ "$ENABLE_LB_AGENT" == "true" ]]; then
    AGENT_LB_IP=$(gcloud compute addresses describe "${LB_NAME}-agent-ip" --global --project="$PROJECT_ID" --format='value(address)')
    echo ""
    echo "Agent load balancer resources:"
    echo "  Static IP:    $AGENT_LB_IP"
    echo "  SSL cert:     ${LB_NAME}-agent-cert (domain: $AGENT_DOMAIN_NAME)"
    echo ""
    log_warn "Configure DNS for the agent before deploying:"
    echo "  Create an A record: $AGENT_DOMAIN_NAME → $AGENT_LB_IP"
    echo "  SSL provisioning requires DNS to resolve to this IP."
fi
if [[ "$ENABLE_LB_HANDLER" == "true" ]]; then
    HANDLER_LB_IP=$(gcloud compute addresses describe "${LB_NAME}-handler-ip" --global --project="$PROJECT_ID" --format='value(address)')
    echo ""
    echo "Handler load balancer resources:"
    echo "  Static IP:    $HANDLER_LB_IP"
    echo "  SSL cert:     ${LB_NAME}-handler-cert (domain: $HANDLER_DOMAIN_NAME)"
    echo ""
    log_warn "Configure DNS for the handler before deploying:"
    echo "  Create an A record: $HANDLER_DOMAIN_NAME → $HANDLER_LB_IP"
    echo "  SSL provisioning requires DNS to resolve to this IP."
fi
echo ""
echo "Remaining manual steps:"
echo ""
echo "1. Update shared secrets (only needed once per project):"
echo ""
echo "   # Red Hat SSO credentials (for user authentication)"
echo "   echo -n 'YOUR_SSO_CLIENT_ID' | gcloud secrets versions add redhat-sso-client-id --data-file=- --project=$PROJECT_ID"
echo "   echo -n 'YOUR_SSO_CLIENT_SECRET' | gcloud secrets versions add redhat-sso-client-secret --data-file=- --project=$PROJECT_ID"
echo ""
echo "   # GMA credentials for DCR (Dynamic Client Registration)"
echo "   echo -n 'YOUR_GMA_CLIENT_ID' | gcloud secrets versions add gma-client-id --data-file=- --project=$PROJECT_ID"
echo "   echo -n 'YOUR_GMA_CLIENT_SECRET' | gcloud secrets versions add gma-client-secret --data-file=- --project=$PROJECT_ID"
echo ""
echo "2. Deploy the agent:"
echo "   # Option A: GitOps (ArgoCD)"
echo "   oc apply -f application.yaml"
echo ""
echo "   # Option B: One-command Cloud Build deployment"
echo "   ./deploy/cloudrun/deploy-cloudbuild.sh"
echo ""
echo "   # Option C: Manual deployment"
echo "   ./deploy/cloudrun/deploy.sh --build --service all"
echo ""
echo "3. Get the service URL:"
echo "   gcloud run services describe $SERVICE_NAME --region=$REGION --project=$PROJECT_ID --format='value(status.url)'"
echo ""
