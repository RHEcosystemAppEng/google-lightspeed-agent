#!/bin/bash
# =============================================================================
# Secret Rotation Bootstrap for Cloud Run Deployment
# =============================================================================
#
# Configures Secret Manager-native rotation plumbing for production:
# 1) Secret Manager rotation metadata (rotation period + next rotation time)
# 2) Secret Manager event notifications to Pub/Sub topics on each secret
# 3) Pub/Sub subscription to receive SECRET_ROTATE events for future rotator workflows
#
# This script does NOT rotate secret values by itself.
# It only creates schedules and notification plumbing.
#
# Usage:
#   ./deploy/cloudrun/setup-secret-rotation.sh
#
# Prerequisite:
#   Run ./deploy/cloudrun/setup.sh first.
#
# Optional environment variables:
#   GOOGLE_CLOUD_PROJECT            Required. GCP project id.
#   GOOGLE_CLOUD_LOCATION           Optional. Scheduler region (default: us-central1).
#   ROTATION_TOPIC                  Optional. Pub/Sub topic (default: secret-rotation-trigger).
#   ROTATION_SUBSCRIPTION           Optional. Pub/Sub subscription name
#                                   (default: secret-rotation-trigger-sub).
#   ROTATION_NEXT_TIME              Optional. RFC3339 UTC timestamp for next rotation metadata.
#
# =============================================================================

set -euo pipefail

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

PROJECT_ID="${GOOGLE_CLOUD_PROJECT:-}"
REGION="${GOOGLE_CLOUD_LOCATION:-us-central1}"
ROTATION_TOPIC="${ROTATION_TOPIC:-secret-rotation-trigger}"
ROTATION_SUBSCRIPTION="${ROTATION_SUBSCRIPTION:-secret-rotation-trigger-sub}"
# Use first day of next month at midnight UTC by default.
ROTATION_NEXT_TIME="${ROTATION_NEXT_TIME:-$(date -u -d "$(date -u +%Y-%m-01) +1 month" +%Y-%m-01T00:00:00Z)}"
FULL_TOPIC_NAME="projects/${PROJECT_ID}/topics/${ROTATION_TOPIC}"

if [[ -z "$PROJECT_ID" ]]; then
    log_error "GOOGLE_CLOUD_PROJECT environment variable is required"
    echo "  export GOOGLE_CLOUD_PROJECT=your-project-id"
    exit 1
fi

# Secret rotation definitions:
# secret_name|rotation_period_seconds
# NOTE: currently set to 3600s (1 hour) for testing.
ROTATION_DEFINITIONS=(
    "redhat-sso-client-secret|3600"
    "gma-client-secret|3600"
)

log_info "Configuring secret rotation bootstrap for project: $PROJECT_ID"
log_info "Pub/Sub region (for subscription): $REGION"
log_info "Rotation event topic: $FULL_TOPIC_NAME"
log_info "Rotation event subscription: $ROTATION_SUBSCRIPTION"
log_info "Initial next rotation timestamp: $ROTATION_NEXT_TIME"

if ! gcloud pubsub topics describe "$ROTATION_TOPIC" --project="$PROJECT_ID" &>/dev/null; then
    log_info "Creating Pub/Sub topic: $ROTATION_TOPIC"
    gcloud pubsub topics create "$ROTATION_TOPIC" --project="$PROJECT_ID"
else
    log_info "Pub/Sub topic already exists: $ROTATION_TOPIC"
fi

# Create Secret Manager service identity (publisher principal for notifications).
log_info "Ensuring Secret Manager service identity exists..."
gcloud beta services identity create \
  --service="secretmanager.googleapis.com" \
  --project="$PROJECT_ID" --quiet >/dev/null 2>&1 || true

project_number=$(gcloud projects describe "$PROJECT_ID" --format='value(projectNumber)')
sm_service_account="service-${project_number}@gcp-sa-secretmanager.iam.gserviceaccount.com"

log_info "Granting Pub/Sub publisher role to Secret Manager service account..."
gcloud pubsub topics add-iam-policy-binding "$ROTATION_TOPIC" \
  --member="serviceAccount:${sm_service_account}" \
  --role="roles/pubsub.publisher" \
  --project="$PROJECT_ID" --quiet >/dev/null

if ! gcloud pubsub subscriptions describe "$ROTATION_SUBSCRIPTION" --project="$PROJECT_ID" &>/dev/null; then
    log_info "Creating Pub/Sub subscription: $ROTATION_SUBSCRIPTION"
    gcloud pubsub subscriptions create "$ROTATION_SUBSCRIPTION" \
      --topic="$ROTATION_TOPIC" \
      --project="$PROJECT_ID" --quiet
else
    log_info "Pub/Sub subscription already exists: $ROTATION_SUBSCRIPTION"
fi

for definition in "${ROTATION_DEFINITIONS[@]}"; do
    IFS='|' read -r secret_name rotation_period <<< "$definition"

    if ! gcloud secrets describe "$secret_name" --project="$PROJECT_ID" &>/dev/null; then
        log_warn "Secret not found, skipping: $secret_name"
        continue
    fi

    log_info "Configuring rotation + topic notification for $secret_name"
    gcloud secrets update "$secret_name" \
      --project="$PROJECT_ID" \
      --add-topics="$FULL_TOPIC_NAME" \
      --next-rotation-time="$ROTATION_NEXT_TIME" \
      --rotation-period="${rotation_period}s" \
      --quiet
done

echo ""
log_info "Secret rotation bootstrap complete."
echo ""
echo "What is now configured:"
echo "  - Secret Manager rotation metadata on 2 secrets"
echo "  - Secret event notifications (including SECRET_ROTATE) to topic: $FULL_TOPIC_NAME"
echo "  - Pub/Sub subscription to receive rotation events: $ROTATION_SUBSCRIPTION"
echo ""
echo "Next step:"
echo "  - Deploy a rotator worker subscribed to '$ROTATION_SUBSCRIPTION' and handle eventType=SECRET_ROTATE."
