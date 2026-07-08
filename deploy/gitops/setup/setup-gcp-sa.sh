#!/bin/bash
# =============================================================================
# Create GCP Service Account for GitOps Deployment
# =============================================================================
#
# Creates a GCP service account with the minimum permissions required by
# the GitOps deploy Job, downloads a key, and creates the bootstrap K8s
# secret on OpenShift for the External Secrets Operator.
#
# Usage:
#   ./deploy/gitops/setup/setup-gcp-sa.sh
#
# Environment variables:
#   GOOGLE_CLOUD_PROJECT    (required) Target GCP project ID
#   SA_NAME                 Service account name (default: lightspeed-gitops)
#   CLOUD_RUN_SA            Cloud Run runtime SA to scope iam.serviceAccountUser
#                           (default: lightspeed-agent). Must match the SA name
#                           used by deploy/cloudrun/setup.sh (SERVICE_ACCOUNT_NAME).
#                           Override if your environment uses a different name,
#                           e.g.: CLOUD_RUN_SA=sa-lightspeed-agent
#   NAMESPACE               OpenShift namespace for the bootstrap secret
#                           (default: rh-lightspeed-agent)
#   SECRET_NAME             K8s secret name (default: gcp-sa-bootstrap)
#   KEY_FILE                Path to save the SA key JSON
#                           (default: /tmp/lightspeed-gitops-sa-key.json)
#
# Prerequisites:
#   - gcloud CLI installed and authenticated
#   - oc CLI installed and authenticated to the target OpenShift cluster
#   - GCP project with billing enabled
#   - IAM Admin permissions on the GCP project
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

show_help() {
    sed -n '2,/^# =====/{ /^# /s/^# //p; /^# *$/s/^# *$//p }' "$0"
    exit 0
}

[[ "${1:-}" == "--help" || "${1:-}" == "-h" ]] && show_help

# =============================================================================
# Configuration
# =============================================================================

PROJECT_ID="${GOOGLE_CLOUD_PROJECT:-}"
SA_NAME="${SA_NAME:-lightspeed-gitops}"
CLOUD_RUN_SA="${CLOUD_RUN_SA:-lightspeed-agent}"
NAMESPACE="${NAMESPACE:-rh-lightspeed-agent}"
SECRET_NAME="${SECRET_NAME:-gcp-sa-bootstrap}"
KEY_FILE="${KEY_FILE:-/tmp/${SA_NAME}-sa-key.json}"

# =============================================================================
# Preflight checks
# =============================================================================

if [[ -z "$PROJECT_ID" ]]; then
    log_error "GOOGLE_CLOUD_PROJECT environment variable is required."
    echo "  export GOOGLE_CLOUD_PROJECT=your-project-id"
    exit 1
fi

SA_EMAIL="${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"
CLOUD_RUN_SA_EMAIL="${CLOUD_RUN_SA}@${PROJECT_ID}.iam.gserviceaccount.com"

if ! command -v gcloud &>/dev/null; then
    log_error "gcloud CLI not found. Install it: https://cloud.google.com/sdk/docs/install"
    exit 1
fi

if ! command -v oc &>/dev/null; then
    log_error "oc CLI not found. Install it: https://docs.openshift.com/container-platform/latest/cli_reference/openshift_cli/getting-started-cli.html"
    exit 1
fi

if ! oc whoami &>/dev/null; then
    log_error "Not logged in to OpenShift. Run: oc login <cluster-url>"
    exit 1
fi

# =============================================================================
# Step 1: Create GCP Service Account
# =============================================================================

if gcloud iam service-accounts describe "${SA_EMAIL}" --project="${PROJECT_ID}" &>/dev/null; then
    log_info "Service account ${SA_EMAIL} already exists."
else
    log_info "Creating service account: ${SA_NAME}..."
    gcloud iam service-accounts create "${SA_NAME}" \
        --display-name="Lightspeed GitOps Deploy" \
        --description="Used by the ArgoCD deploy Job to trigger Cloud Build and access GCP Secret Manager" \
        --project="${PROJECT_ID}" \
        --quiet
fi

# =============================================================================
# Step 2: Grant IAM Roles
# =============================================================================

log_info "Granting IAM roles to ${SA_EMAIL}..."

# Project-level roles:
PROJECT_ROLES=(
    "roles/secretmanager.secretAccessor"       # ESO reads secrets from GCP Secret Manager
    "roles/cloudbuild.builds.editor"           # Deploy Job submits Cloud Build pipelines
    "roles/run.admin"                          # Cloud Build deploys Cloud Run services
    "roles/serviceusage.serviceUsageConsumer"  # gcloud builds submit API access
)

for role in "${PROJECT_ROLES[@]}"; do
    log_info "  Granting ${role}..."
    gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
        --member="serviceAccount:${SA_EMAIL}" \
        --role="${role}" \
        --quiet || true
done

# iam.serviceAccountUser scoped to the Cloud Run runtime SA only (not project-wide)
log_info "  Granting roles/iam.serviceAccountUser on ${CLOUD_RUN_SA_EMAIL}..."
gcloud iam service-accounts add-iam-policy-binding "${CLOUD_RUN_SA_EMAIL}" \
    --member="serviceAccount:${SA_EMAIL}" \
    --role="roles/iam.serviceAccountUser" \
    --project="${PROJECT_ID}" \
    --quiet || true

# =============================================================================
# Step 3: Create and Download SA Key
# =============================================================================

if [[ -f "${KEY_FILE}" ]]; then
    log_warn "Key file already exists at ${KEY_FILE}. Skipping key creation."
    log_warn "Delete it and re-run to generate a new key."
else
    log_info "Creating service account key..."
    (umask 077 && gcloud iam service-accounts keys create "${KEY_FILE}" \
        --iam-account="${SA_EMAIL}" \
        --project="${PROJECT_ID}" \
        --quiet)
    chmod 600 "${KEY_FILE}"
    log_info "Key saved to: ${KEY_FILE}"
fi

# =============================================================================
# Step 4: Create OpenShift Namespace and Bootstrap Secret
# =============================================================================

if ! oc get namespace "${NAMESPACE}" &>/dev/null; then
    log_info "Creating namespace: ${NAMESPACE}..."
    oc create namespace "${NAMESPACE}"
fi

if oc get secret "${SECRET_NAME}" -n "${NAMESPACE}" &>/dev/null; then
    log_warn "Secret ${SECRET_NAME} already exists in namespace ${NAMESPACE}."
    log_warn "To update it, delete first: oc delete secret ${SECRET_NAME} -n ${NAMESPACE}"
else
    log_info "Creating bootstrap secret: ${SECRET_NAME} in ${NAMESPACE}..."
    oc create secret generic "${SECRET_NAME}" \
        --from-file=gcp-service-account-key="${KEY_FILE}" \
        -n "${NAMESPACE}"
fi

# =============================================================================
# Step 5: Cleanup Key File
# =============================================================================

if oc get secret "${SECRET_NAME}" -n "${NAMESPACE}" &>/dev/null && [[ -f "${KEY_FILE}" ]]; then
    rm -f "${KEY_FILE}"
    log_info "Key file deleted: ${KEY_FILE}"
elif [[ -f "${KEY_FILE}" ]]; then
    log_warn "Could not verify K8s secret — key file retained at ${KEY_FILE}."
    log_warn "Delete it manually after verifying: rm ${KEY_FILE}"
fi

# =============================================================================
# Summary
# =============================================================================

echo ""
log_info "=== GCP Service Account Setup Complete ==="
log_info "  Project:         ${PROJECT_ID}"
log_info "  Service Account: ${SA_EMAIL}"
log_info "  Roles (project-level):"
for role in "${PROJECT_ROLES[@]}"; do
    log_info "    - ${role}"
done
log_info "  Roles (SA-level on ${CLOUD_RUN_SA_EMAIL}):"
log_info "    - roles/iam.serviceAccountUser"
log_info "  K8s Secret:      ${SECRET_NAME} (namespace: ${NAMESPACE})"
echo ""
log_info "Next steps:"
log_info "  1. Verify the secret: oc get secret ${SECRET_NAME} -n ${NAMESPACE}"
log_info "  2. Deploy the GitOps Helm chart (ArgoCD Application)"
echo ""
