#!/bin/bash
# =============================================================================
# Install External Secrets Operator (ESO) for Red Hat OpenShift
# =============================================================================
#
# Installs the Red Hat-supported External Secrets Operator from OperatorHub.
# ESO synchronizes secrets from external providers (GCP Secret Manager,
# Vault, AWS SM) into Kubernetes Secrets.
#
# Usage:
#   ./deploy/gitops/setup/install-eso-operator.sh
#
# Prerequisites:
#   - oc CLI installed and authenticated to the target OpenShift cluster
#   - cluster-admin privileges
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

OPERATOR_NAMESPACE="openshift-external-secrets"
TIMEOUT="${TIMEOUT:-300}"

# =============================================================================
# Preflight checks
# =============================================================================

if ! command -v oc &>/dev/null; then
    log_error "oc CLI not found. Install it: https://docs.openshift.com/container-platform/latest/cli_reference/openshift_cli/getting-started-cli.html"
    exit 1
fi

if ! oc whoami &>/dev/null; then
    log_error "Not logged in to OpenShift. Run: oc login <cluster-url>"
    exit 1
fi

# =============================================================================
# Step 1: Check if already installed
# =============================================================================

if oc get subscription external-secrets-operator -n "${OPERATOR_NAMESPACE}" &>/dev/null; then
    log_info "External Secrets Operator subscription already exists."
    CSV=$(oc get subscription external-secrets-operator -n "${OPERATOR_NAMESPACE}" -o jsonpath='{.status.currentCSV}' 2>/dev/null || true)
    if [[ -n "$CSV" ]]; then
        PHASE=$(oc get csv "$CSV" -n "${OPERATOR_NAMESPACE}" -o jsonpath='{.status.phase}' 2>/dev/null || true)
        if [[ "$PHASE" == "Succeeded" ]]; then
            log_info "Operator is already installed and ready (CSV: ${CSV})."
            exit 0
        fi
        log_warn "Operator CSV ${CSV} is in phase: ${PHASE}. Waiting for it to become ready..."
    fi
else
    # =========================================================================
    # Step 2: Create Namespace and OperatorGroup
    # =========================================================================

    log_info "Creating namespace ${OPERATOR_NAMESPACE}..."

    oc apply -f - <<EOF
apiVersion: v1
kind: Namespace
metadata:
  name: ${OPERATOR_NAMESPACE}
---
apiVersion: operators.coreos.com/v1
kind: OperatorGroup
metadata:
  name: external-secrets-operator
  namespace: ${OPERATOR_NAMESPACE}
spec: {}
EOF

    # =========================================================================
    # Step 3: Create Subscription
    # =========================================================================

    log_info "Installing External Secrets Operator..."

    oc apply -f - <<EOF
apiVersion: operators.coreos.com/v1alpha1
kind: Subscription
metadata:
  name: external-secrets-operator
  namespace: ${OPERATOR_NAMESPACE}
spec:
  channel: stable-v1
  installPlanApproval: Automatic
  name: external-secrets-operator
  source: redhat-operators
  sourceNamespace: openshift-marketplace
EOF
fi

# =============================================================================
# Step 4: Wait for CSV to reach Succeeded
# =============================================================================

log_info "Waiting for operator to be ready (timeout: ${TIMEOUT}s)..."

ELAPSED=0
while [[ $ELAPSED -lt $TIMEOUT ]]; do
    CSV=$(oc get subscription external-secrets-operator -n "${OPERATOR_NAMESPACE}" \
        -o jsonpath='{.status.currentCSV}' 2>/dev/null || true)
    if [[ -n "$CSV" ]]; then
        PHASE=$(oc get csv "$CSV" -n "${OPERATOR_NAMESPACE}" \
            -o jsonpath='{.status.phase}' 2>/dev/null || true)
        if [[ "$PHASE" == "Succeeded" ]]; then
            log_info "Operator installed successfully (CSV: ${CSV})."
            break
        fi
    fi
    sleep 10
    ELAPSED=$((ELAPSED + 10))
    echo -n "."
done
echo ""

if [[ $ELAPSED -ge $TIMEOUT ]]; then
    log_error "Timed out waiting for operator. Check: oc get csv -n ${OPERATOR_NAMESPACE}"
    exit 1
fi

# =============================================================================
# Summary
# =============================================================================

echo ""
log_info "=== External Secrets Operator Setup Complete ==="
log_info "  Operator:  external-secrets-operator"
log_info "  Namespace: ${OPERATOR_NAMESPACE}"
log_info "  Channel:   stable-v1"
echo ""
log_info "Next steps:"
log_info "  1. Create a SecretStore pointing to your external provider (GCP SM, Vault, etc.)"
log_info "  2. Create ExternalSecret CRs to pull secrets into K8s"
log_info "  3. See deploy/gitops/google-cloud/ for the Helm chart that automates this"
echo ""
