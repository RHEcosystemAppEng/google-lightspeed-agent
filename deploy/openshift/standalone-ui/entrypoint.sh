#!/bin/bash
# Escape characters that could break out of JavaScript string literals
escape_js() { printf '%s' "$1" | sed 's/["\]/\\&/g'; }

cat > /usr/share/nginx/html/config.js << EOF
window.CONFIG = {
  agentUrl: "$(escape_js "${AGENT_URL:-http://localhost:8000}")",
  ssoIssuerUrl: "$(escape_js "${SSO_ISSUER_URL:-https://sso.redhat.com/auth/realms/redhat-external}")",
  redirectUris: "$(escape_js "${REDIRECT_URIS:-https://vertexaisearch.cloud.google.com/oauth-redirect}")"
};
EOF

# Replace URL placeholders in nginx config
# sed -i creates a temp file in the same directory, which may be read-only.
# Write to /tmp first, then copy back.
sed -e "s|__AGENT_INTERNAL_URL__|${AGENT_INTERNAL_URL:-http://lightspeed-agent:8000}|g" \
    -e "s|__HANDLER_INTERNAL_URL__|${HANDLER_INTERNAL_URL:-http://lightspeed-agent-handler:8001}|g" \
    "${NGINX_CONF_PATH}" > /tmp/nginx.conf
cp /tmp/nginx.conf "${NGINX_CONF_PATH}"
rm /tmp/nginx.conf

exec nginx -g 'daemon off;'
