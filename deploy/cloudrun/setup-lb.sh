#!/bin/bash
# =============================================================================
# GCLB Setup Script — shared by deploy.sh and cloudbuild.yaml
# =============================================================================
# Creates a full Google Cloud Load Balancer stack for a single Cloud Run
# service: static IP, SSL cert, serverless NEG, backend service, optional
# Cloud Armor WAF, URL map, HTTPS proxy, forwarding rule, and ingress update.
#
# All commands are idempotent (check existence before creation).
#
# Usage:
#   ./deploy/cloudrun/setup-lb.sh <service_label> <cloud_run_service> \
#       <domain_name> <cloud_armor_enabled> <region> <project_id> [lb_name] [waf_sensitivity]
#
# Arguments:
#   service_label:       "agent" or "handler" (used in resource naming)
#   cloud_run_service:   Cloud Run service name to front with the LB
#   domain_name:         Domain for the Google-managed SSL certificate
#   cloud_armor_enabled: "true" to create and attach a Cloud Armor WAF policy
#   region:              GCP region for the Cloud Run service / NEG
#   project_id:          GCP project ID
#   lb_name:             Resource name prefix (default: lightspeed-lb)
#   waf_sensitivity:     OWASP CRS sensitivity level 1-4 (default: 1)
# =============================================================================

set -euo pipefail

SERVICE_LABEL="$1"
CLOUD_RUN_SERVICE="$2"
DOMAIN_NAME="$3"
CLOUD_ARMOR_ENABLED="$4"
REGION="$5"
PROJECT_ID="$6"
LB_NAME="${7:-lightspeed-lb}"
WAF_SENSITIVITY="${8:-1}"

NEG_NAME="${LB_NAME}-${SERVICE_LABEL}-neg"
BACKEND_NAME="${LB_NAME}-${SERVICE_LABEL}-backend"
POLICY_NAME="${LB_NAME}-${SERVICE_LABEL}-security-policy"
URL_MAP_NAME="${LB_NAME}-${SERVICE_LABEL}-url-map"
CERT_NAME="${LB_NAME}-${SERVICE_LABEL}-cert"
PROXY_NAME="${LB_NAME}-${SERVICE_LABEL}-https-proxy"
RULE_NAME="${LB_NAME}-${SERVICE_LABEL}-forwarding-rule"
IP_NAME="${LB_NAME}-${SERVICE_LABEL}-ip"

echo "Setting up GCLB for ${SERVICE_LABEL} (${CLOUD_RUN_SERVICE})..."

# Static IP
if ! gcloud compute addresses describe "$IP_NAME" \
    --global --project="$PROJECT_ID" &>/dev/null; then
    gcloud compute addresses create "$IP_NAME" \
        --global --project="$PROJECT_ID"
    echo "Static IP '$IP_NAME' reserved."
else
    echo "Static IP '$IP_NAME' already exists."
fi

# Google-managed SSL certificate
if ! gcloud compute ssl-certificates describe "$CERT_NAME" \
    --global --project="$PROJECT_ID" &>/dev/null; then
    gcloud compute ssl-certificates create "$CERT_NAME" \
        --domains="$DOMAIN_NAME" --global --project="$PROJECT_ID"
    echo "SSL certificate '$CERT_NAME' created for $DOMAIN_NAME."
else
    echo "SSL certificate '$CERT_NAME' already exists."
fi

# Serverless NEG
if ! gcloud compute network-endpoint-groups describe "$NEG_NAME" \
    --region="$REGION" --project="$PROJECT_ID" &>/dev/null; then
    gcloud compute network-endpoint-groups create "$NEG_NAME" \
        --region="$REGION" \
        --network-endpoint-type=serverless \
        --cloud-run-service="$CLOUD_RUN_SERVICE" \
        --project="$PROJECT_ID"
    echo "NEG '$NEG_NAME' created."
else
    echo "NEG '$NEG_NAME' already exists."
fi

# Backend service
if ! gcloud compute backend-services describe "$BACKEND_NAME" \
    --global --project="$PROJECT_ID" &>/dev/null; then
    gcloud compute backend-services create "$BACKEND_NAME" \
        --global --project="$PROJECT_ID"
    gcloud compute backend-services add-backend "$BACKEND_NAME" \
        --global \
        --network-endpoint-group="$NEG_NAME" \
        --network-endpoint-group-region="$REGION" \
        --project="$PROJECT_ID"
    echo "Backend service '$BACKEND_NAME' created."
else
    echo "Backend service '$BACKEND_NAME' already exists."
fi

# Cloud Armor WAF
if [ "$CLOUD_ARMOR_ENABLED" = "true" ]; then
    if ! gcloud compute security-policies describe "$POLICY_NAME" \
        --global --project="$PROJECT_ID" &>/dev/null; then
        gcloud compute security-policies create "$POLICY_NAME" \
            --global --project="$PROJECT_ID"
        echo "Cloud Armor policy '$POLICY_NAME' created."
    else
        echo "Cloud Armor policy '$POLICY_NAME' already exists."
    fi
    # Enable JSON parsing for JSON-RPC/DCR request bodies and verbose logging
    # --request-body-inspection-size requires beta; fall back to GA if unavailable
    if gcloud beta compute security-policies update "$POLICY_NAME" \
        --json-parsing=STANDARD \
        --request-body-inspection-size=64kB \
        --log-level=VERBOSE \
        --global \
        --project="$PROJECT_ID" 2>/dev/null; then
        echo "Security policy '$POLICY_NAME' configured: JSON parsing, 64kB body inspection, verbose logging"
    else
        gcloud compute security-policies update "$POLICY_NAME" \
            --json-parsing=STANDARD \
            --log-level=VERBOSE \
            --global \
            --project="$PROJECT_ID"
        echo "Security policy '$POLICY_NAME' configured: JSON parsing, verbose logging (body inspection size requires gcloud beta)"
    fi

    # Add preconfigured WAF rules (OWASP ModSecurity CRS)
    for ENTRY in "900:methodenforcement-v422-stable" \
                 "1000:sqli-v422-stable" "1100:xss-v422-stable" "1200:lfi-v422-stable" \
                 "1300:rfi-v422-stable" "1400:rce-v422-stable" "1500:scannerdetection-v422-stable" \
                 "1600:protocolattack-v422-stable" "1700:sessionfixation-v422-stable" \
                 "1800:cve-canary"; do
        PRIORITY="${ENTRY%%:*}"
        RULE="${ENTRY##*:}"
        if ! gcloud compute security-policies rules describe "$PRIORITY" \
            --security-policy="$POLICY_NAME" --project="$PROJECT_ID" &>/dev/null; then
            gcloud compute security-policies rules create "$PRIORITY" \
                --security-policy="$POLICY_NAME" \
                --expression="evaluatePreconfiguredWaf('${RULE}', {'sensitivity': ${WAF_SENSITIVITY}})" \
                --action=deny-403 --project="$PROJECT_ID"
            echo "WAF rule '${RULE}' added at priority $PRIORITY (sensitivity $WAF_SENSITIVITY)."
        fi
    done
    gcloud compute backend-services update "$BACKEND_NAME" \
        --security-policy="$POLICY_NAME" --global --project="$PROJECT_ID"
    echo "Cloud Armor policy attached to '$BACKEND_NAME'."
fi

# URL map
if ! gcloud compute url-maps describe "$URL_MAP_NAME" \
    --global --project="$PROJECT_ID" &>/dev/null; then
    gcloud compute url-maps create "$URL_MAP_NAME" \
        --default-service="$BACKEND_NAME" \
        --global --project="$PROJECT_ID"
    echo "URL map '$URL_MAP_NAME' created."
else
    echo "URL map '$URL_MAP_NAME' already exists."
fi

# HTTPS proxy
if ! gcloud compute target-https-proxies describe "$PROXY_NAME" \
    --global --project="$PROJECT_ID" &>/dev/null; then
    gcloud compute target-https-proxies create "$PROXY_NAME" \
        --ssl-certificates="$CERT_NAME" \
        --url-map="$URL_MAP_NAME" \
        --global --project="$PROJECT_ID"
    echo "HTTPS proxy '$PROXY_NAME' created."
else
    echo "HTTPS proxy '$PROXY_NAME' already exists."
fi

# Forwarding rule
if ! gcloud compute forwarding-rules describe "$RULE_NAME" \
    --global --project="$PROJECT_ID" &>/dev/null; then
    gcloud compute forwarding-rules create "$RULE_NAME" \
        --global \
        --target-https-proxy="$PROXY_NAME" \
        --address="$IP_NAME" \
        --ports=443 \
        --project="$PROJECT_ID"
    echo "Forwarding rule '$RULE_NAME' created."
else
    echo "Forwarding rule '$RULE_NAME' already exists."
fi

# Restrict Cloud Run ingress to GCLB only
gcloud run services update "$CLOUD_RUN_SERVICE" \
    --region="$REGION" --project="$PROJECT_ID" \
    --ingress=internal-and-cloud-load-balancing --quiet

# Print SSL cert status
CERT_STATUS=$(gcloud compute ssl-certificates describe "$CERT_NAME" \
    --global --project="$PROJECT_ID" \
    --format='value(managed.status)' 2>/dev/null || echo "UNKNOWN")
STATIC_IP=$(gcloud compute addresses describe "$IP_NAME" \
    --global --project="$PROJECT_ID" \
    --format='value(address)' 2>/dev/null || echo "UNKNOWN")

echo ""
echo "${SERVICE_LABEL^} GCLB setup complete:"
echo "  Static IP:    $STATIC_IP"
echo "  Domain:       $DOMAIN_NAME"
echo "  SSL status:   $CERT_STATUS"
if [ "$CERT_STATUS" != "ACTIVE" ]; then
    echo "  NOTE: Google-managed SSL certificates take 15-60 minutes to provision."
    echo "        Ensure DNS A record for $DOMAIN_NAME points to $STATIC_IP."
    echo "        Check status: gcloud compute ssl-certificates describe $CERT_NAME --global --format='value(managed.status)'"
fi
