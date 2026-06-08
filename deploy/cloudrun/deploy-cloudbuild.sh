#!/bin/bash
# =============================================================================
# One-Command Cloud Build Deployment
# =============================================================================
#
# Deploys the Red Hat Lightspeed Agent for Google Cloud using Cloud Build
# in a single command. Runs setup.sh (idempotent), grants the Cloud Build
# service account required IAM roles, then submits the Cloud Build pipeline.
#
# Usage:
#   ./deploy/cloudrun/deploy-cloudbuild.sh [OPTIONS]
#
# Options:
#   --agent-domain DOMAIN     Domain name for the agent GCLB (enables LB)
#   --handler-domain DOMAIN   Domain name for the handler GCLB (enables LB)
#   --no-lb                   Disable GCLB for both services
#   --allow-unauthenticated   Allow public access to both services
#   --region REGION           GCP region (default: us-central1)
#   --image-tag TAG           Container image tag (default: latest)
#   --skip-setup              Skip setup.sh and IAM role grants (reuse previous setup)
#   --dry-run                 Print the gcloud command without executing
#   --help                    Show this help message
#
# Environment variables (see setup.sh and deploy/cloudrun/README.md):
#   GOOGLE_CLOUD_PROJECT      (required) GCP project ID
#   GOOGLE_CLOUD_LOCATION     Cloud Run region (default: us-central1)
#   SERVICE_NAME              Agent service name (default: lightspeed-agent)
#   HANDLER_SERVICE_NAME      Handler service name (default: marketplace-handler)
#   PUBSUB_TOPIC              Pub/Sub topic (default: marketplace-entitlements)
#   PUBSUB_SUBSCRIPTION       Pub/Sub subscription name (required for FQ topics)
#   SERVICE_CONTROL_SERVICE_NAME  Managed service name from Producer Portal
#   AGENT_SOURCE_IMAGE        Agent container image (default: quay.io/ecosystem-appeng/google-lightspeed-agent:latest)
#   HANDLER_SOURCE_IMAGE      Handler container image (default: quay.io/ecosystem-appeng/google-marketplace-handler:latest)
#   MCP_SOURCE_IMAGE          MCP server image (default: quay.io/redhat-services-prod/.../red-hat-lightspeed-mcp:latest)
#   SERVICE_ACCOUNT_NAME      Cloud Run service account (default: lightspeed-agent)
#   DB_INSTANCE_NAME          Cloud SQL instance name (default: lightspeed-agent-db)
#   VPC_CONNECTOR_NAME        VPC connector name (default: lightspeed-redis-conn)
#   SCAN_SEVERITY             Trivy scan severity threshold (default: CRITICAL,HIGH)
#   VERTEXAI_LOCATION         Vertex AI location (default: global)
#
# Prerequisites:
#   - gcloud CLI installed and authenticated
#   - GCP project with billing enabled
#
# =============================================================================

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# =============================================================================
# Parse arguments
# =============================================================================

AGENT_DOMAIN=""
HANDLER_DOMAIN=""
NO_LB=false
ALLOW_UNAUTH=false
REGION="${GOOGLE_CLOUD_LOCATION:-us-central1}"
IMAGE_TAG="latest"
SKIP_SETUP=false
DRY_RUN=false

show_help() {
    sed -n '2,/^# =====/{ /^# /s/^# //p; /^# *$/s/^# *$//p }' "$0"
    exit 0
}

while [[ $# -gt 0 ]]; do
    case $1 in
        --agent-domain)
            AGENT_DOMAIN="$2"
            shift 2
            ;;
        --handler-domain)
            HANDLER_DOMAIN="$2"
            shift 2
            ;;
        --no-lb)
            NO_LB=true
            shift
            ;;
        --allow-unauthenticated)
            ALLOW_UNAUTH=true
            shift
            ;;
        --region)
            REGION="$2"
            shift 2
            ;;
        --image-tag)
            IMAGE_TAG="$2"
            shift 2
            ;;
        --skip-setup)
            SKIP_SETUP=true
            shift
            ;;
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        --help|-h)
            show_help
            ;;
        *)
            log_error "Unknown option: $1"
            echo "Run with --help for usage."
            exit 1
            ;;
    esac
done

# =============================================================================
# Validate
# =============================================================================

PROJECT_ID="${GOOGLE_CLOUD_PROJECT:-}"
if [[ -z "$PROJECT_ID" ]]; then
    log_error "GOOGLE_CLOUD_PROJECT environment variable is required"
    echo "  export GOOGLE_CLOUD_PROJECT=your-project-id"
    exit 1
fi

# Determine LB configuration
ENABLE_LB_AGENT="false"
ENABLE_LB_HANDLER="false"

if [[ "$NO_LB" != "true" ]]; then
    if [[ -n "$AGENT_DOMAIN" ]]; then
        ENABLE_LB_AGENT="true"
    fi
    if [[ -n "$HANDLER_DOMAIN" ]]; then
        ENABLE_LB_HANDLER="true"
    fi
fi

# Resolve the repo root (where cloudbuild.yaml lives)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# =============================================================================
# Step 1: Run setup.sh (idempotent) — skipped with --skip-setup
# =============================================================================

if [[ "$SKIP_SETUP" == "true" ]]; then
    log_info "Skipping setup (--skip-setup). Assuming setup.sh and IAM roles are already configured."
else
    log_info "Running setup.sh..."

    export GOOGLE_CLOUD_PROJECT="$PROJECT_ID"
    export GOOGLE_CLOUD_LOCATION="$REGION"
    export ENABLE_LB_AGENT
    export ENABLE_LB_HANDLER
    export AGENT_DOMAIN_NAME="${AGENT_DOMAIN}"
    export HANDLER_DOMAIN_NAME="${HANDLER_DOMAIN}"

    bash "$SCRIPT_DIR/setup.sh"

    # =========================================================================
    # Step 2: Grant Cloud Build SA required IAM roles
    # =========================================================================

    log_info "Granting IAM roles to Cloud Build service account..."

    PROJECT_NUMBER=$(gcloud projects describe "$PROJECT_ID" --format='value(projectNumber)')
    CB_SA="${PROJECT_NUMBER}@cloudbuild.gserviceaccount.com"

    # These roles are the simplest way to grant Cloud Build the permissions it
    # needs. For production, consider replacing roles/pubsub.editor and
    # roles/compute.admin with custom roles scoped to the specific resources
    # this pipeline manages (see cloudbuild.yaml header for details).
    cb_roles=(
        "roles/run.admin"
        "roles/iam.serviceAccountUser"
        "roles/pubsub.editor"
    )

    if [[ "$ENABLE_LB_AGENT" == "true" || "$ENABLE_LB_HANDLER" == "true" ]]; then
        cb_roles+=("roles/compute.admin")
    fi

    for role in "${cb_roles[@]}"; do
        log_info "  Granting $role to $CB_SA..."
        gcloud projects add-iam-policy-binding "$PROJECT_ID" \
            --member="serviceAccount:$CB_SA" \
            --role="$role" \
            --quiet || true
    done
fi

# =============================================================================
# Step 3: Build Cloud Build substitutions
# =============================================================================

SUBSTITUTIONS="_REGION=${REGION},_IMAGE_TAG=${IMAGE_TAG}"
SUBSTITUTIONS="${SUBSTITUTIONS},_ENABLE_LB_AGENT=${ENABLE_LB_AGENT}"
SUBSTITUTIONS="${SUBSTITUTIONS},_ENABLE_LB_HANDLER=${ENABLE_LB_HANDLER}"

if [[ -n "$AGENT_DOMAIN" ]]; then
    SUBSTITUTIONS="${SUBSTITUTIONS},_AGENT_DOMAIN_NAME=${AGENT_DOMAIN}"
fi
if [[ -n "$HANDLER_DOMAIN" ]]; then
    SUBSTITUTIONS="${SUBSTITUTIONS},_HANDLER_DOMAIN_NAME=${HANDLER_DOMAIN}"
fi
if [[ "$ALLOW_UNAUTH" == "true" ]]; then
    SUBSTITUTIONS="${SUBSTITUTIONS},_ALLOW_UNAUTHENTICATED=true"
fi

# Forward optional environment variables as substitutions
if [[ -n "${SERVICE_NAME:-}" ]]; then
    SUBSTITUTIONS="${SUBSTITUTIONS},_SERVICE_NAME=${SERVICE_NAME}"
fi
if [[ -n "${HANDLER_SERVICE_NAME:-}" ]]; then
    SUBSTITUTIONS="${SUBSTITUTIONS},_HANDLER_SERVICE_NAME=${HANDLER_SERVICE_NAME}"
fi
if [[ -n "${PUBSUB_TOPIC:-}" ]]; then
    SUBSTITUTIONS="${SUBSTITUTIONS},_PUBSUB_TOPIC=${PUBSUB_TOPIC}"
fi
if [[ -n "${PUBSUB_SUBSCRIPTION:-}" ]]; then
    SUBSTITUTIONS="${SUBSTITUTIONS},_PUBSUB_SUBSCRIPTION=${PUBSUB_SUBSCRIPTION}"
fi
if [[ -n "${SERVICE_CONTROL_SERVICE_NAME:-}" ]]; then
    SUBSTITUTIONS="${SUBSTITUTIONS},_SERVICE_CONTROL_SERVICE_NAME=${SERVICE_CONTROL_SERVICE_NAME}"
fi
if [[ -n "${AGENT_SOURCE_IMAGE:-}" ]]; then
    SUBSTITUTIONS="${SUBSTITUTIONS},_AGENT_SOURCE_IMAGE=${AGENT_SOURCE_IMAGE}"
fi
if [[ -n "${HANDLER_SOURCE_IMAGE:-}" ]]; then
    SUBSTITUTIONS="${SUBSTITUTIONS},_HANDLER_SOURCE_IMAGE=${HANDLER_SOURCE_IMAGE}"
fi
if [[ -n "${MCP_SOURCE_IMAGE:-}" ]]; then
    SUBSTITUTIONS="${SUBSTITUTIONS},_MCP_SOURCE_IMAGE=${MCP_SOURCE_IMAGE}"
fi
if [[ -n "${SERVICE_ACCOUNT_NAME:-}" ]]; then
    SUBSTITUTIONS="${SUBSTITUTIONS},_SERVICE_ACCOUNT_NAME=${SERVICE_ACCOUNT_NAME}"
fi
if [[ -n "${DB_INSTANCE_NAME:-}" ]]; then
    SUBSTITUTIONS="${SUBSTITUTIONS},_DB_INSTANCE_NAME=${DB_INSTANCE_NAME}"
fi
if [[ -n "${VPC_CONNECTOR_NAME:-}" ]]; then
    SUBSTITUTIONS="${SUBSTITUTIONS},_VPC_CONNECTOR_NAME=${VPC_CONNECTOR_NAME}"
fi
if [[ -n "${SCAN_SEVERITY:-}" ]]; then
    SUBSTITUTIONS="${SUBSTITUTIONS},_SCAN_SEVERITY=${SCAN_SEVERITY}"
fi
if [[ -n "${VERTEXAI_LOCATION:-}" ]]; then
    SUBSTITUTIONS="${SUBSTITUTIONS},_VERTEXAI_LOCATION=${VERTEXAI_LOCATION}"
fi

# =============================================================================
# Step 4: Submit Cloud Build
# =============================================================================

CMD=(
    gcloud builds submit
    --config=cloudbuild.yaml
    --project="$PROJECT_ID"
    "--substitutions=${SUBSTITUTIONS}"
)

echo ""
log_info "Cloud Build command:"
echo "  ${CMD[*]}"
echo ""

if [[ "$DRY_RUN" == "true" ]]; then
    log_warn "Dry run — not submitting. Run without --dry-run to deploy."
    exit 0
fi

log_info "Submitting Cloud Build pipeline..."
cd "$REPO_ROOT"
exec "${CMD[@]}"
