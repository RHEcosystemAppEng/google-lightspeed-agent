#!/bin/bash
# =============================================================================
# Install OpenShift GitOps (ArgoCD) Operator
# =============================================================================
#
# Installs the OpenShift GitOps operator from OperatorHub and waits for it
# to be ready. The operator creates an ArgoCD instance in the
# openshift-gitops namespace automatically.
#
# Usage:
#   ./deploy/gitops/setup/install-gitops-operator.sh
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

OPERATOR_NAMESPACE="openshift-operators"
GITOPS_NAMESPACE="openshift-gitops"
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

if oc get subscription openshift-gitops-operator -n "${OPERATOR_NAMESPACE}" &>/dev/null; then
    log_info "OpenShift GitOps operator subscription already exists."
    CSV=$(oc get subscription openshift-gitops-operator -n "${OPERATOR_NAMESPACE}" -o jsonpath='{.status.currentCSV}' 2>/dev/null || true)
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
    # Step 2: Create Subscription
    # =========================================================================

    log_info "Installing OpenShift GitOps operator..."

    oc apply -f - <<EOF
apiVersion: operators.coreos.com/v1alpha1
kind: Subscription
metadata:
  name: openshift-gitops-operator
  namespace: ${OPERATOR_NAMESPACE}
spec:
  channel: latest
  installPlanApproval: Automatic
  name: openshift-gitops-operator
  source: redhat-operators
  sourceNamespace: openshift-marketplace
EOF
fi

# =============================================================================
# Step 3: Wait for CSV to reach Succeeded
# =============================================================================

log_info "Waiting for operator to be ready (timeout: ${TIMEOUT}s)..."

ELAPSED=0
while [[ $ELAPSED -lt $TIMEOUT ]]; do
    CSV=$(oc get subscription openshift-gitops-operator -n "${OPERATOR_NAMESPACE}" \
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
# Step 4: Wait for ArgoCD instance
# =============================================================================

log_info "Waiting for ArgoCD instance in ${GITOPS_NAMESPACE}..."

ELAPSED=0
while [[ $ELAPSED -lt $TIMEOUT ]]; do
    READY=$(oc get argocd openshift-gitops -n "${GITOPS_NAMESPACE}" \
        -o jsonpath='{.status.phase}' 2>/dev/null || true)
    if [[ "$READY" == "Available" ]]; then
        log_info "ArgoCD instance is ready."
        break
    fi
    sleep 10
    ELAPSED=$((ELAPSED + 10))
    echo -n "."
done
echo ""

if [[ $ELAPSED -ge $TIMEOUT ]]; then
    log_warn "ArgoCD instance not yet Available. It may still be starting up."
    log_warn "Check: oc get argocd -n ${GITOPS_NAMESPACE}"
fi

# =============================================================================
# Summary
# =============================================================================

echo ""
log_info "=== OpenShift GitOps Setup Complete ==="
log_info "  Operator:  openshift-gitops-operator"
log_info "  Namespace: ${GITOPS_NAMESPACE}"
log_info "  ArgoCD UI: oc get route openshift-gitops-server -n ${GITOPS_NAMESPACE} -o jsonpath='{.spec.host}'"
echo ""
