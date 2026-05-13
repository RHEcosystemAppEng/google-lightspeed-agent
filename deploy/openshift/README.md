# Red Hat Lightspeed Agent — OpenShift Deployment (Helm)

Deploy the Red Hat Lightspeed Agent on OpenShift using Helm. Two deployment
modes are supported:

| Mode | `deploymentMode` | What runs on OCP | What stays on GCP |
|------|-------------------|------------------|-------------------|
| **Hybrid** (default) | `hybrid` | Agent, Redis | Marketplace handler (Cloud Run) |
| **Standalone** | `standalone` | Everything — agent, handler, UI, PostgreSQL, Redis | Only the Gemini API |

## Architecture

### Hybrid mode

```
  Google Cloud                         OpenShift Cluster
  +-----------------+                  +-------------------------------+
  |  Cloud Run      |                  |     OpenShift Route           |
  |  marketplace    |                  |     (TLS edge termination)    |
  |  handler        |                  +-------------+-----------------+
  |  (port 8001)    |                                |
  +-----------------+                  +-------------v-----------------+
                                       |   lightspeed-agent (Pod)      |
                                       |   agent (8000) + MCP (8081)   |
                                       +---+--------------------------+
                                           |
                                 +----------+--------+
                                 |  Redis            |
                                 |  (rate limiting)  |
                                 |  Port 6379        |
                                 +-------------------+
```

In hybrid mode the handler is **not deployed** on OCP and sessions use in-memory
storage by default. Order validation is skipped (`auth.skipOrderValidation: true`)
since there is no local marketplace database. JWT introspection against Red Hat
SSO is still enforced.

### Standalone mode

```
  OpenShift Cluster
  +---------------------------------------------------------------------+
  |                                                                     |
  |  +------------------+  +------------------+  +-----------+          |
  |  |  Agent Route     |  |  Handler Route   |  |  UI Route |          |
  |  +--------+---------+  +--------+---------+  +-----+-----+          |
  |           |                      |                  |                |
  |  +--------v---------+  +--------v---------+  +-----v-----+          |
  |  | lightspeed-agent |  | marketplace      |  | standalone|          |
  |  | agent + MCP      |  | handler          |  | UI        |          |
  |  | (port 8000)      |  | (port 8001)      |  | (8080)    |          |
  |  +--------+---------+  +----+--------+----+  +-----------+          |
  |           |                  |        |                              |
  |  +--------v---------+  +----v--------v----+  +-----------+          |
  |  |  Marketplace     |  |  Session         |  |   Redis   |          |
  |  |  PostgreSQL      |  |  PostgreSQL      |  |   (6379)  |          |
  |  |  (marketplace)   |  |  (sessions,      |  +-----------+          |
  |  |  Port 5432       |  |   optional)      |                         |
  |  +------------------+  +------------------+                         |
  +---------------------------------------------------------------------+
```

Everything runs on OCP. Sessions use in-memory storage by default; set
`postgresql.sessionBackend: database` to persist sessions across pod restarts
(deploys a separate session PostgreSQL instance). The standalone UI provides
a web interface to:
1. **Discover the agent** and register an OAuth client (DCR)
2. **Get an access token** from Red Hat SSO (client credentials grant)
3. **Send A2A messages** to the agent with the token

## Mode Comparison

| Setting / Behavior | Hybrid | Standalone |
|---|---|---|
| **Agent + MCP sidecar** | Deployed | Deployed |
| **Session PostgreSQL** | Not deployed (in-memory sessions by default) | Not deployed (in-memory sessions by default) |
| **Marketplace PostgreSQL** | NOT deployed | Deployed |
| **Redis** | Deployed | Deployed |
| **Marketplace handler** | NOT deployed (stays on Cloud Run) | Deployed |
| **Standalone UI** | NOT deployed | Deployed |
| `auth.skipOrderValidation` | Must be `true` (no local marketplace DB) | Should be `false` (handler manages orders locally) |
| `auth.skipDcrJwtValidation` | Not applicable | `true` for self-signed JWTs, `false` if using Google SA |
| `secrets.databaseUrl` | Not needed | Required (marketplace DB connection) |
| `secrets.marketplaceDbPassword` | Not needed | Required (marketplace PostgreSQL password) |
| `secrets.dcrEncryptionKey` | Not needed | Required (handler encrypts DCR client secrets) |
| `secrets.gmaClientId/Secret` | Not needed | Required (handler creates SSO clients via GMA) |

## Components

| Component | Description | Deployed in |
|---|---|---|
| **lightspeed-agent** | A2A agent (Gemini + ADK) with MCP sidecar | Both modes |
| **postgresql** | PostgreSQL 16 for session persistence | Both (only when `sessionBackend: database`) |
| **marketplace-postgresql** | PostgreSQL 16 for marketplace/entitlement data | Standalone only |
| **redis** | Redis 7 for distributed rate limiting | Both modes |
| **marketplace-handler** | DCR and marketplace event handler | Standalone only |
| **standalone-ui** | Web UI for DCR + A2A testing | Standalone only |

## Prerequisites

### CLI tools

Install `oc` and `helm` if not already available:

```bash
# OpenShift CLI — download from your cluster's web console (? > Command Line Tools)
# or from https://mirror.openshift.com/pub/openshift-v4/clients/ocp/

# Helm CLI
curl https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash
```

### Requirements

**Both modes:**
- OpenShift 4.x cluster with `oc` and `helm` CLIs
- Container image access: `quay.io/ecosystem-appeng/google-lightspeed-agent`,
  `quay.io/redhat-services-prod/.../red-hat-lightspeed-mcp`,
  `quay.io/fedora/redis-7`, `registry.redhat.io/rhel9/postgresql-16` (if using database session backend or standalone mode)
- Google AI Studio API key **or** Vertex AI project
- Red Hat SSO OAuth credentials (client ID and secret)

**Standalone mode (additional):**
- Container images for handler and UI:
  `quay.io/ecosystem-appeng/google-marketplace-handler`,
  `quay.io/ecosystem-appeng/google-lightspeed-agent-ui`
- A Fernet encryption key for DCR
  (`python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`)
- A GCP service account key (if Service Control is enabled)

## Deployment — Hybrid Mode

### 1. Create a project

```bash
oc new-project lightspeed-agent
```

### 2. Configure image pull secrets (if needed)

The agent and UI images on `quay.io/ecosystem-appeng/` are public — no pull
secret is required for them. However, the Red Hat registry images (PostgreSQL,
MCP sidecar) may need authentication if your cluster doesn't already have a
global pull secret for `registry.redhat.io`:

```bash
oc create secret docker-registry redhat-pull-secret \
  --docker-server=registry.redhat.io \
  --docker-username=<user> \
  --docker-password=<password> \
  -n lightspeed-agent
```

Then add the secret name to your values file:

```yaml
imagePullSecrets:
  - name: redhat-pull-secret
```

> **Tip**: Most OpenShift clusters have a global pull secret for
> `registry.redhat.io` configured at install time — check with your cluster
> admin before creating one. If using private image registries, add their
> pull secrets to the same list.

### 3. Select an image tag

The default images in `values.yaml` point to the official repositories. Browse
the available tags and choose the one matching your desired version or commit:

- **Agent**: `quay.io/ecosystem-appeng/google-lightspeed-agent`
- **MCP sidecar**: `quay.io/redhat-services-prod/.../red-hat-lightspeed-mcp`

Set the tag in your values file:

```yaml
agent:
  image:
    tag: "<commit-sha-or-version>"
```

> **Tip — local testing**: You can also build and push images to your own
> registry for development purposes:
>
> ```bash
> podman build -t quay.io/<your-org>/lightspeed-agent:latest -f Containerfile .
> podman push quay.io/<your-org>/lightspeed-agent:latest
> ```
>
> Then override the repository in your values file:
> `agent.image.repository: quay.io/<your-org>/lightspeed-agent`

### 4. Configure values

```bash
cp deploy/openshift/values.yaml deploy/openshift/my-values.yaml
```

Edit `my-values.yaml`:

```yaml
deploymentMode: hybrid   # default

auth:
  skipOrderValidation: true

secrets:
  create: true
  googleApiKey: "your-real-api-key"
  redHatSsoClientId: "your-real-client-id"
  redHatSsoClientSecret: "your-real-client-secret"
  redisPassword: "a-strong-redis-password"
```

No database, handler, or UI configuration is needed — sessions use in-memory
storage by default, and the handler and standalone UI are not deployed in hybrid
mode. Order validation is skipped (`skipOrderValidation: true`) since there is
no local marketplace database. JWT introspection against Red Hat SSO is still
enforced.

> **Persistent sessions**: To persist sessions across pod restarts, set
> `postgresql.sessionBackend: database` and provide `secrets.sessionDbPassword`
> and `secrets.sessionDatabaseUrl`. This deploys a session PostgreSQL instance.

### 5. Install

```bash
helm install lightspeed-agent deploy/openshift/ \
  -f deploy/openshift/my-values.yaml \
  -n lightspeed-agent
```

### 6. Update the provider URL in values file

After the Route is created, get the hostname and persist it in your values file
so it survives future upgrades and pod restarts:

```bash
AGENT_HOST=$(oc get route lightspeed-agent -n lightspeed-agent -o jsonpath='{.spec.host}')
echo "Agent Route: https://${AGENT_HOST}"
```

Add the URL to `my-values.yaml`:

```yaml
agent:
  providerUrl: "https://<AGENT_HOST>"   # paste the actual hostname
```

Then apply:

```bash
helm upgrade lightspeed-agent deploy/openshift/ \
  -f deploy/openshift/my-values.yaml \
  -n lightspeed-agent
```

### 7. Verify

```bash
oc get pods -n lightspeed-agent
AGENT_HOST=$(oc get route lightspeed-agent -n lightspeed-agent -o jsonpath='{.spec.host}')
curl -s https://${AGENT_HOST}/health
curl -s https://${AGENT_HOST}/.well-known/agent.json | python -m json.tool
```

## Deployment — Standalone Mode

### 1. Create a project

```bash
oc new-project lightspeed-agent
```

### 2. Configure image pull secrets

Follow the same pull secret setup as in [hybrid mode step 2](#2-configure-image-pull-secrets).

### 3. Select image tags

The default images in `values.yaml` point to the official repositories. Browse
the available tags and choose the ones matching your desired version or commit:

- **Agent**: `quay.io/ecosystem-appeng/google-lightspeed-agent`
- **Handler**: `quay.io/ecosystem-appeng/google-marketplace-handler`
- **Standalone UI**: `quay.io/ecosystem-appeng/google-lightspeed-agent-ui`

Set the tags in your values file:

```yaml
agent:
  image:
    tag: "<commit-sha-or-version>"
handler:
  image:
    tag: "<commit-sha-or-version>"
standaloneUI:
  image:
    tag: "<commit-sha-or-version>"
```

> **Tip — local testing**: You can also build and push images to your own
> registry for development purposes:
>
> ```bash
> # Agent
> podman build -t quay.io/<your-org>/lightspeed-agent:latest -f Containerfile .
> podman push quay.io/<your-org>/lightspeed-agent:latest
>
> # Handler
> podman build -t quay.io/<your-org>/lightspeed-agent-handler:latest \
>   -f Containerfile.marketplace-handler .
> podman push quay.io/<your-org>/lightspeed-agent-handler:latest
>
> # Standalone UI
> podman build -t quay.io/<your-org>/lightspeed-agent-ui:latest \
>   -f deploy/openshift/standalone-ui/Containerfile deploy/openshift/standalone-ui/
> podman push quay.io/<your-org>/lightspeed-agent-ui:latest
> ```
>
> Then override the repositories in your values file (e.g.,
> `agent.image.repository: quay.io/<your-org>/lightspeed-agent`).

### 4. Configure values

```bash
cp deploy/openshift/values.yaml deploy/openshift/my-values.yaml
```

Edit `my-values.yaml`:

```yaml
deploymentMode: standalone

auth:
  # Disable order validation skip — standalone has a local marketplace DB
  skipOrderValidation: false
  # Accept self-signed DCR JWTs (not signed by Google's production SA)
  skipDcrJwtValidation: true

secrets:
  create: true
  googleApiKey: "your-real-api-key"
  redHatSsoClientId: "your-real-client-id"
  redHatSsoClientSecret: "your-real-client-secret"
  # Redis authentication password
  redisPassword: "a-strong-redis-password"
  # Marketplace database (separate PostgreSQL instance, deployed automatically)
  marketplaceDbPassword: "a-strong-marketplace-password"
  databaseUrl: "postgresql+asyncpg://marketplace:a-strong-marketplace-password@lightspeed-agent-marketplace-postgresql:5432/marketplace"
  # DCR encryption key (generate with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
  dcrEncryptionKey: "your-fernet-key"
  # GMA API credentials — required for the handler to create SSO clients
  gmaClientId: "your-gma-client-id"
  gmaClientSecret: "your-gma-client-secret"
```

> **Note:** Setting `deploymentMode: standalone` automatically deploys the handler,
> standalone UI, and marketplace PostgreSQL — no additional flags are needed.
> Sessions use in-memory storage by default; set `postgresql.sessionBackend: database`
> to persist them (see hybrid mode note above).

### 5. Install

```bash
helm install lightspeed-agent deploy/openshift/ \
  -f deploy/openshift/my-values.yaml \
  -n lightspeed-agent
```

### 6. Update the provider URL in values file

After the Route is created, get the agent hostname and persist it in your values
file so it survives future upgrades and pod restarts:

```bash
AGENT_HOST=$(oc get route lightspeed-agent -n lightspeed-agent -o jsonpath='{.spec.host}')
echo "Agent Route: https://${AGENT_HOST}"
```

Add the URL to `my-values.yaml`:

```yaml
agent:
  providerUrl: "https://<AGENT_HOST>"     # paste the actual hostname

auth:
  corsAllowedOrigins: "http://localhost:8080"  # for port-forward UI access
```

Then apply:

```bash
helm upgrade lightspeed-agent deploy/openshift/ \
  -f deploy/openshift/my-values.yaml \
  -n lightspeed-agent
```

> **Security note:** Only the agent has a public OpenShift Route. The handler
> and standalone UI are ClusterIP-only services — they are not exposed outside
> the cluster. Use `oc port-forward` to access the UI from your local machine.

### 7. Access the UI via port-forward

The standalone UI is not publicly exposed. Use `oc port-forward` to access it:

```bash
oc port-forward svc/lightspeed-agent-ui 8080:8080 -n lightspeed-agent
```

Then open http://localhost:8080 in your browser.

### 8. Verify

```bash
oc get pods -n lightspeed-agent
# Expect: agent, handler, UI, marketplace-postgresql, redis pods

AGENT_HOST=$(oc get route lightspeed-agent -n lightspeed-agent -o jsonpath='{.spec.host}')
curl -s https://${AGENT_HOST}/.well-known/agent.json | python -m json.tool
```

### Understanding `skip_dcr_jwt_validation`

The `skipDcrJwtValidation` flag **only** skips JWT signature and issuer
verification on the DCR software_statement. It does **not** bypass account or
order validation — the handler still validates that the Procurement Account ID
and Order ID exist in the local marketplace database. This means:

- You must create an order (entitlement) before registering a client.
- The standalone UI automates this via the "Create Order" step.

### Using the Standalone UI

The interface guides you through the full order lifecycle:

1. **Create Order** — Simulates a Google Cloud Marketplace Pub/Sub event to
   create an entitlement in the local marketplace database. Enter an Account ID
   and Order ID (or use the defaults), then click **Create Order**. This must
   be done before DCR registration.

2. **Register Client (DCR)** — The agent card is fetched automatically. Click
   **Register Client** to create an OAuth client via the handler's `/dcr`
   endpoint using the Account ID and Order ID from step 1. The returned
   `client_id` and `client_secret` are displayed with copy buttons.

3. **Get Access Token** — Credentials from step 2 are pre-filled. Click
   **Get Token** to perform a client credentials grant against Red Hat SSO. If
   CORS blocks the request, a `curl` command is shown instead — run it and
   paste the token back.

4. **A2A Client** — The token from step 3 is pre-filled. Type a message and
   click **Send** to send a JSON-RPC 2.0 A2A request to the agent.

Use the **Reset** button to clear all state and start over (the entitlement and
DCR client are cleaned up from the database).

## Configuration Reference

### Deployment mode

| Value | Description | Default |
|---|---|---|
| `deploymentMode` | `hybrid` or `standalone` — controls which components are deployed and how auth behaves (see [Mode Comparison](#mode-comparison)) | `hybrid` |

### Image pull secrets

| Value | Description | Default |
|---|---|---|
| `imagePullSecrets` | List of `{name: "secret-name"}` entries for private registry authentication. Applied to all pods. | `[]` |

### Agent

| Value | Description | Default |
|---|---|---|
| `agent.image.repository` | Agent container image | `quay.io/ecosystem-appeng/google-lightspeed-agent` |
| `agent.image.tag` | Image tag | `latest` |
| `agent.image.pullPolicy` | Image pull policy | `Always` |
| `agent.replicas` | Replica count | `1` |
| `agent.name` | Internal agent name | `lightspeed_agent` |
| `agent.description` | Agent description | `Red Hat Lightspeed Agent` |
| `agent.host` | Agent listen address | `0.0.0.0` |
| `agent.port` | Agent listen port | `8000` |
| `agent.probePort` | Health/readiness probe port | `8002` |
| `agent.providerUrl` | Agent URL (set to Route hostname after install) | `https://lightspeed-agent.apps.example.com` |
| `agent.displayName` | Agent display name for the agent card | `Red Hat Lightspeed Agent for Google Cloud` |
| `agent.providerOrganizationUrl` | Organization URL for the agent card | `https://www.redhat.com` |
| `agent.loggingDetail` | Agent logging verbosity (`basic` / `detailed`) | `basic` |
| `agent.toolResultMaxChars` | Max characters in MCP tool results | `204800` |

### MCP Sidecar

The MCP server runs as a sidecar container in the agent pod.

| Value | Description | Default |
|---|---|---|
| `mcp.image.repository` | MCP server container image | `quay.io/redhat-services-prod/.../red-hat-lightspeed-mcp` |
| `mcp.image.tag` | Image tag | `latest` |
| `mcp.image.pullPolicy` | Image pull policy | `Always` |
| `mcp.transport` | Transport mode (`http` / `stdio` / `sse`) | `http` |
| `mcp.port` | MCP server port | `8081` |
| `mcp.host` | MCP server listen address | `0.0.0.0` |
| `mcp.readOnly` | Enable read-only mode (safe tool subset) | `true` |
| `mcp.baseUrl` | Red Hat console base URL (override for staging) | `""` |
| `mcp.ssoBaseUrl` | Red Hat SSO base URL for MCP (override for staging) | `""` |
| `mcp.proxyUrl` | HTTP proxy for MCP (required for some staging environments) | `""` |

### Google AI / Gemini

| Value | Description | Default |
|---|---|---|
| `google.geminiModel` | Gemini model name | `gemini-2.5-flash` |
| `google.useVertexAI` | Use Vertex AI instead of AI Studio | `false` |
| `google.cloudLocation` | Vertex AI region | `us-central1` |
| `google.httpRetry.attempts` | Max retry attempts for Gemini HTTP calls | `5` |
| `google.httpRetry.initialDelay` | Initial retry delay (seconds) | `1.0` |
| `google.httpRetry.maxDelay` | Max retry delay (seconds) | `60.0` |
| `google.httpRetry.expBase` | Exponential backoff base | `2.0` |
| `google.httpRetry.jitter` | Retry jitter (seconds) | `1.0` |

### Authentication

| Value | Description | Default | Mode |
|---|---|---|---|
| `auth.skipJwtValidation` | Skip JWT validation (dev only — blocked on Cloud Run) | `false` | Both |
| `auth.skipOrderValidation` | Skip marketplace order-id checks. Must be `true` in hybrid (no marketplace DB). Should be `false` in standalone (handler manages orders locally). | `true` | Both |
| `auth.skipDcrJwtValidation` | Skip DCR software_statement JWT signature verification. Enable for standalone deployments using self-signed JWTs. Does not affect agent auth. | `false` | Standalone |
| `auth.corsAllowedOrigins` | CORS allowed origins (comma-separated) | `""` | Both |
| `sso.issuer` | Red Hat SSO issuer URL | `https://sso.redhat.com/auth/realms/redhat-external` | Both |
| `sso.requiredScope` | Required OAuth scopes (comma-separated) | `api.console,api.ocm` | Both |
| `sso.allowedScopes` | Allowed OAuth scopes allowlist (comma-separated) | `openid,profile,email,api.console,api.ocm,metering:admin` | Both |

### Session Database (PostgreSQL)

The session PostgreSQL instance is **only deployed when `postgresql.sessionBackend: database`**.
With the default `memory` backend, no session database is created.

| Value | Description | Default |
|---|---|---|
| `postgresql.image.repository` | PostgreSQL container image | `registry.redhat.io/rhel9/postgresql-16` |
| `postgresql.image.tag` | Image tag | `latest` |
| `postgresql.image.pullPolicy` | Image pull policy | `IfNotPresent` |
| `postgresql.sessionBackend` | `database` (persist to PostgreSQL) or `memory` (lost on restart) | `memory` |
| `postgresql.poolSize` | Connection pool size | `5` |
| `postgresql.poolMaxOverflow` | Max pool overflow | `10` |
| `postgresql.user` | Database user | `sessions` |
| `postgresql.database` | Database name | `agent_sessions` |
| `postgresql.storage.size` | PVC size | `1Gi` |

### Marketplace Database (standalone mode only)

A separate PostgreSQL instance for marketplace/entitlement data. Deployed only
when `deploymentMode: standalone`.

| Value | Description | Default |
|---|---|---|
| `marketplacePostgresql.image.repository` | PostgreSQL container image | `registry.redhat.io/rhel9/postgresql-16` |
| `marketplacePostgresql.image.tag` | Image tag | `latest` |
| `marketplacePostgresql.image.pullPolicy` | Image pull policy | `IfNotPresent` |
| `marketplacePostgresql.user` | Database user | `marketplace` |
| `marketplacePostgresql.database` | Database name | `marketplace` |
| `marketplacePostgresql.storage.size` | PVC size | `1Gi` |

### Rate Limiting & Redis

| Value | Description | Default |
|---|---|---|
| `rateLimit.requestsPerMinute` | Per-IP requests/min | `60` |
| `rateLimit.requestsPerHour` | Per-IP requests/hour | `1000` |
| `rateLimit.redisTimeoutMs` | Redis operation timeout (ms) | `200` |
| `rateLimit.keyPrefix` | Redis key prefix for rate-limit counters | `lightspeed:ratelimit` |
| `rateLimit.redisCaCert` | Redis TLS CA certificate path | `""` |
| `redis.image.repository` | Redis container image | `quay.io/fedora/redis-7` |
| `redis.image.tag` | Image tag | `latest` |
| `redis.image.pullPolicy` | Image pull policy | `IfNotPresent` |
| `redis.storage.size` | Redis PVC size | `1Gi` |

### Routes

| Value | Description | Default |
|---|---|---|
| `route.enabled` | Create an OpenShift Route for the agent | `true` |
| `route.tls.termination` | TLS termination type | `edge` |
| `route.tls.insecureEdgeTerminationPolicy` | Redirect HTTP to HTTPS | `Redirect` |

### Handler (standalone mode only)

Deployed only when `deploymentMode: standalone`.

| Value | Description | Default |
|---|---|---|
| `handler.image.repository` | Handler container image | `quay.io/ecosystem-appeng/google-marketplace-handler` |
| `handler.image.tag` | Image tag | `latest` |
| `handler.image.pullPolicy` | Image pull policy | `Always` |
| `handler.replicas` | Replica count (keep at 1 to avoid duplicate event processing) | `1` |
| `handler.host` | Handler listen address | `0.0.0.0` |
| `handler.port` | Handler listen port | `8001` |
| `handler.probePort` | Handler probe port | `8003` |
| `handler.route.enabled` | Create an OpenShift Route for the handler (disabled by default — handler is ClusterIP only, reached via UI nginx proxy) | `false` |
| `handler.dcr.clientNamePrefix` | Prefix for created OAuth clients | `gemini-order-` |
| `handler.serviceControlServiceName` | Marketplace product identifier (from GCP Producer Portal) | `""` |
| `handler.metering.staleClaimMinutes` | Stale claim timeout | `15` |
| `handler.metering.backfillMaxAgeHours` | Max backfill age | `168` |
| `handler.metering.backfillLimitPerRun` | Max records per backfill run | `20` |
| `handler.gma.apiBaseUrl` | GMA SSO API base URL | `https://sso.redhat.com/...` |
| `handler.gma.apiTimeout` | GMA API timeout (seconds) | `30` |

### Service Control

| Value | Description | Default |
|---|---|---|
| `serviceControl.enabled` | Enable Google Cloud Service Control usage reporting | `false` |

### Standalone UI (standalone mode only)

Deployed only when `deploymentMode: standalone`.

| Value | Description | Default |
|---|---|---|
| `standaloneUI.image.repository` | UI container image | `quay.io/ecosystem-appeng/google-lightspeed-agent-ui` |
| `standaloneUI.image.tag` | Image tag | `latest` |
| `standaloneUI.image.pullPolicy` | Image pull policy | `Always` |
| `standaloneUI.port` | UI listen port | `8080` |
| `standaloneUI.route.enabled` | Create a Route for the UI | `true` |

### Secrets

| Value | Description | Required in |
|---|---|---|
| `secrets.create` | Have the chart create the Secret from values below (`false` = manage externally) | Both |
| `secrets.googleApiKey` | Google AI API key | Both (unless Vertex AI) |
| `secrets.googleCloudProject` | GCP project ID | Both (Vertex AI only) |
| `secrets.redHatSsoClientId` | Red Hat SSO client ID | Both |
| `secrets.redHatSsoClientSecret` | Red Hat SSO client secret | Both |
| `secrets.sessionDbPassword` | Session PostgreSQL password | Only when `sessionBackend: database` |
| `secrets.sessionDatabaseUrl` | Session database connection URL | Only when `sessionBackend: database` |
| `secrets.redisPassword` | Redis authentication password | Both |
| `secrets.marketplaceDbPassword` | Marketplace PostgreSQL password | Standalone only |
| `secrets.databaseUrl` | Marketplace database connection URL | Standalone only |
| `secrets.dcrEncryptionKey` | Fernet key for encrypting stored DCR client secrets | Standalone only |
| `secrets.gmaClientId` | GMA API client ID (for DCR tenant creation) | Standalone only |
| `secrets.gmaClientSecret` | GMA API client secret | Standalone only |
| `secrets.gcpServiceAccountKey` | Base64-encoded GCP SA key JSON (for ADC outside Cloud Run) | Standalone + GCP only |

### Observability

| Value | Description | Default |
|---|---|---|
| `logging.level` | Log level | `INFO` |
| `logging.format` | Log format (`json` / `text`) | `json` |
| `otel.enabled` | Enable OpenTelemetry | `false` |
| `otel.serviceName` | OTEL service name | `lightspeed_agent` |
| `otel.exporterType` | Exporter type | `otlp` |
| `otel.otlpEndpoint` | OTLP gRPC endpoint | `http://localhost:4317` |
| `otel.otlpHttpEndpoint` | OTLP HTTP endpoint | `http://localhost:4318` |
| `otel.tracesSampler` | Traces sampler strategy | `always_on` |
| `otel.tracesSamplerArg` | Traces sampler argument | `1.0` |

## Authentication

The agent authenticates requests via Red Hat SSO token introspection:

1. Clients obtain a Bearer token from Red Hat SSO
2. The agent validates the token via the SSO introspection endpoint
3. The required scopes (`api.console,api.ocm` by default) are checked

**Hybrid mode** — order validation is skipped (`skipOrderValidation: true`).
Token introspection against Red Hat SSO is still enforced.

**Standalone mode** — the handler manages DCR clients and entitlements locally
in the shared PostgreSQL. Order validation can be enabled or skipped.

## Using Red Hat Staging Environment

To point the deployment at `console.stage.redhat.com` instead of production,
add these overrides to your `my-values.yaml`:

```yaml
# SSO issuer — staging realm
sso:
  issuer: "https://sso.stage.redhat.com/auth/realms/redhat-external"

# MCP sidecar — staging console and SSO
mcp:
  baseUrl: "https://console.stage.redhat.com"
  ssoBaseUrl: "https://sso.stage.redhat.com"
  # HTTP proxy — required if staging is behind edge lockdown
  proxyUrl: "http://<your-proxy>"

# Handler GMA API — staging SSO (standalone mode only)
handler:
  gma:
    apiBaseUrl: "https://sso.stage.redhat.com/auth/realms/redhat-external/apis/beta/acs/v1/"
```

## Scaling

```bash
oc scale deployment/lightspeed-agent --replicas=3 -n lightspeed-agent
```

Rate limiting state is shared across replicas through Redis. For automatic
scaling:

```bash
oc autoscale deployment/lightspeed-agent --min=1 --max=5 --cpu-percent=80 -n lightspeed-agent
```

> The marketplace handler should typically run with a single replica to avoid
> processing duplicate events.

## Upgrading

```bash
helm upgrade lightspeed-agent deploy/openshift/ \
  -f deploy/openshift/my-values.yaml \
  -n lightspeed-agent
```

## Troubleshooting

### View logs

```bash
# Agent
oc logs deployment/lightspeed-agent -c lightspeed-agent -n lightspeed-agent
# MCP sidecar
oc logs deployment/lightspeed-agent -c lightspeed-mcp -n lightspeed-agent
# Handler (standalone mode)
oc logs deployment/lightspeed-agent-handler -n lightspeed-agent
# Standalone UI
oc logs deployment/lightspeed-agent-ui -n lightspeed-agent
# Session PostgreSQL (only when sessionBackend=database)
oc logs deployment/lightspeed-agent-postgresql -n lightspeed-agent
# Marketplace PostgreSQL (standalone mode)
oc logs deployment/lightspeed-agent-marketplace-postgresql -n lightspeed-agent
# Redis
oc logs deployment/lightspeed-agent-redis -n lightspeed-agent
```

### Common issues

**Pod stuck in `ImagePullBackOff`**: Verify image registry access. Ensure the
pull secrets exist in the namespace and are listed in `imagePullSecrets` in your
values file (see [step 2](#2-configure-image-pull-secrets)).

**Agent cannot connect to PostgreSQL**: Check the relevant PostgreSQL pod is
running and that `SESSION_DATABASE_URL` / `DATABASE_URL` in the secret matches
the correct service name (`lightspeed-agent-postgresql` for sessions,
`lightspeed-agent-marketplace-postgresql` for marketplace).

**Agent cannot connect to Redis**: Verify the Redis pod is running and
`RATE_LIMIT_REDIS_URL` in the ConfigMap points to the Redis service.

**Health check failing**: Check agent logs for startup errors (missing secrets,
unreachable database/Redis).

**Standalone UI shows CORS error on token request**: Red Hat SSO may not allow
CORS from the UI origin. Use the displayed `curl` command to get the token
manually and paste it into the UI.

## Cleanup

```bash
helm uninstall lightspeed-agent -n lightspeed-agent
```

PVCs are not deleted by `helm uninstall`:

```bash
oc delete pvc -l app.kubernetes.io/part-of=lightspeed-agent -n lightspeed-agent
```

Or delete the entire project:

```bash
oc delete project lightspeed-agent
```
