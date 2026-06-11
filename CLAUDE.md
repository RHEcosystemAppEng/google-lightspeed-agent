# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Red Hat Lightspeed Agent for Google Cloud — an A2A-ready (Agent-to-Agent protocol) AI agent providing access to Red Hat Insights, built on Google Agent Development Kit (ADK), Gemini 2.5 Flash, and a Red Hat Lightspeed MCP server sidecar. Integrates with Google Cloud Marketplace for provisioning, billing, and metering.

## Common Commands

### Development

Always use a Python virtual environment — do not install dependencies system-wide.

```bash
python3.12 -m venv .venv              # Create virtual environment
source .venv/bin/activate             # Activate it
pip install -e ".[agent,dev]"         # Install all dependencies (agent + dev)
# Optional: pip install -e ".[agent,dev,telemetry]"  # Include Jaeger/Zipkin exporters
python -m lightspeed_agent.main       # Run the agent API server (port 8000)
```

### Testing

Ensure the virtual environment is activated before running tests.

```bash
make test                              # Run all tests
python -m pytest tests/ -v             # Equivalent direct command
python -m pytest tests/test_auth.py -v # Run a single test file
python -m pytest tests/test_auth.py::test_function_name -v  # Run a single test
```

Tests use in-memory SQLite and `SKIP_JWT_VALIDATION=true` (set automatically in `tests/conftest.py`). The test suite is async — `asyncio_mode = "auto"` is configured in pyproject.toml.

To run with coverage:
```bash
python -m pytest tests/ -v --cov=src/lightspeed_agent --cov-report=term-missing
```

### Dependencies

Lock files pin exact versions with hashes. After editing `pyproject.toml`, run `make lock` and commit both together. For CVE fixes in transitive deps, add them as direct deps in `pyproject.toml` with the safe version, then `make lock`. See `CONTRIBUTING.md` for detailed workflows.

```bash
make lock                              # Regenerate all lock files
make check-lock                        # Verify lock files match pyproject.toml
make audit                             # Scan for known CVEs (pip-audit)
```

### Linting & Type Checking
```bash
make lint                              # Run both ruff and mypy
ruff check src/ tests/                 # Linter only
mypy src/lightspeed_agent/ --ignore-missing-imports  # Type checker only
```

Ruff rules: `E, F, I, N, W, UP, B, C4, SIM`. Line length: 100. Target: Python 3.12.

### Container Build & Operations (Podman)
```bash
make help                              # List all available targets
make build                             # Build both images (agent + marketplace handler)
make build-agent                       # Build agent image only
make build-marketplace                 # Build marketplace handler image only
make run                               # Start all pods
make stop                              # Stop and remove pods
make logs                              # Agent logs
make logs-mcp                          # MCP server logs
make logs-all                          # All container logs
make status                            # Show pod/container status
make clean                             # Remove containers, images, and volumes
make clean-all                         # Full cleanup including volumes
make dev                               # Run agent locally without containers
make check-env                         # Validate required env vars
make cve-scan                          # Scan for CVEs with Trivy
```

### Before Pushing

Run lint and tests before pushing commits:

```bash
make lint && make test
```

If you modified `pyproject.toml`, also regenerate lock files (`make lock`) and commit them together. CI only enforces lock file sync when `pyproject.toml` changes.

## Architecture

### Two-Service Design

The system runs as two separate FastAPI services with separate concerns:

1. **Lightspeed Agent** (port 8000, `src/lightspeed_agent/main.py`) — The AI agent service. Scales to zero on Cloud Run. Handles A2A protocol requests (JSON-RPC 2.0 at `/`), serves the AgentCard at `/.well-known/agent.json`. Uses ADK `LlmAgent` with MCP tools loaded from the sidecar and ADK AI Skills for modular behavioral instructions.

2. **Marketplace Handler** (port 8001, `src/lightspeed_agent/marketplace/app.py`) — Always-on service for Google Cloud Marketplace Pub/Sub provisioning events and Dynamic Client Registration (DCR). Has separate `/dcr` (DCR requests) and `/pubsub` (Pub/Sub events with Google OIDC verification) endpoints.

### Database Isolation

Two separate PostgreSQL databases (security boundary):
- **Marketplace DB** (`DATABASE_URL`) — entitlements, DCR clients, usage records. Shared by both services.
- **Session DB** (`SESSION_DATABASE_URL`) — ADK conversation sessions. Agent-only.

Both fall back to SQLite for development. ORM models are in `src/lightspeed_agent/db/models.py`.

### Authentication Flow

JWT tokens from Red Hat SSO flow through three layers:
1. `auth/middleware.py` validates Bearer tokens — only `POST /` is protected; all other paths are public. Health probes (`/health`, `/ready`) run on a separate probe server (see below), not the main API. The Marketplace Handler has its own auth (Google OIDC on `/pubsub`, DCR JWT on `/dcr`).
2. Token is stored in `contextvars` for the request lifecycle (user_id, org_id, order_id, client_id, request_id)
3. `tools/mcp_headers.py` forwards the caller's JWT to the MCP server so it can authenticate with console.redhat.com on the user's behalf

Setting `SKIP_JWT_VALIDATION=true` bypasses auth (dev only, blocked when running on Cloud Run).

### MCP Integration

The agent loads tools from a Red Hat Lightspeed MCP server running as a sidecar:
- Transport modes: `stdio` (dev), `http` (prod), `sse` (streaming) — configured via `MCP_TRANSPORT_MODE`
- Read-only mode (`MCP_READ_ONLY=true`) filters to a safe subset of tools
- Startup security check warns when `MCP_SERVER_URL` uses HTTP for non-localhost hosts (see `api/app.py:_check_mcp_url_security`)
- Tool categories: Advisor, Inventory, Vulnerability, Remediations, Planning, Image Builder, RHSM (Subscription Management), RBAC, Content Sources
- MCP toolset creation is in `tools/insights_tools.py`; config in `tools/mcp_config.py`

### ADK AI Skills

Agent behavioral instructions use ADK's progressive-disclosure Skills system instead of a monolithic system prompt. Each skill is a `SKILL.md` file with YAML frontmatter (L1: name + description loaded at startup) and a markdown body (L2: full instructions loaded on-demand by the LLM).

- **Bundled skills** (`core/skills/`): tool-invocation-rules, multi-step-workflows, pagination-handling, efficient-counting, error-handling, guardrails-safety, response-formatting — always loaded
- **External skills** (`SKILLS_DIR` env var): deployment-specific skills loaded alongside bundled ones; same-name skills override bundled defaults
- A2A AgentCard skills (`tools/a2a_skills.py`) are a separate concept — they describe agent capabilities for the A2A protocol, not LLM behavioral instructions

### Key Middleware Stack (request order, outermost first)
1. CORS
2. Request body size limit (`security/body_limit.py`) — 10 MB agent, 1 MB marketplace handler
3. Security headers (`security/middleware.py`) — HSTS, CSP, X-Content-Type-Options,
   X-Frame-Options, Referrer-Policy, Permissions-Policy, Cache-Control
4. Redis rate limiting (`ratelimit/middleware.py`) — 60 req/min, 1000 req/hour
5. JWT authentication (`auth/middleware.py`)

### Health Probe Server

A separate lightweight uvicorn server (`probes/server.py`) runs on port 8002 (`PROBES_PORT`) alongside the main API. Provides `/health` (liveness) and `/ready` (readiness with optional async validations) endpoints for Kubernetes and Cloud Run health checking. This is independent of the main FastAPI app and its middleware stack.

### Deployment Modes

The agent supports three deployment targets. The application code is identical — differences are in infrastructure-level security and orchestration:

| Target | Ingress | WAF | Network Isolation | Deployment Config |
|---|---|---|---|---|
| **Cloud Run** | GCLB with managed SSL | Cloud Armor (OWASP CRS, DDoS) | VPC + Cloud Run ingress restrictions | `deploy/cloudrun/` |
| **OpenShift** | Routes with TLS edge termination | None built-in (use external WAF if needed) | NetworkPolicies for DB/Redis | `deploy/openshift/` (Helm) |
| **Podman** | Direct port binding | None | Host-level | `deploy/podman/` + `Makefile` |

OpenShift supports two sub-modes via Helm (`deploymentMode` value):
- **hybrid** (default) — Agent + Redis on OCP; marketplace handler stays on Cloud Run. Order validation skipped (`SKIP_ORDER_VALIDATION=true`).
- **standalone** — Everything on OCP including handler, UI, and PostgreSQL. Full order lifecycle with local marketplace database.

Cloud Run deployments use a Cloud Build CI/CD pipeline (`cloudbuild.yaml`) that pulls pre-built images from Quay.io (built by Konflux), scans them with Trivy, pushes to GCR, and deploys both services to Cloud Run with optional GCLB and Cloud Armor WAF. One-command deployment via `deploy/cloudrun/deploy-cloudbuild.sh`.

Application-level protections (body size limits, security headers, rate limiting, JWT auth) apply identically on all platforms. See `deploy/openshift/README.md` for OCP-specific details.

### DCR (Dynamic Client Registration)

Creates OAuth tenant clients in Red Hat SSO via the GMA API (`dcr/gma_client.py`). Authenticates with `GMA_CLIENT_ID`/`GMA_CLIENT_SECRET` using `scope=api.iam.clients.gma`. Client secrets are Fernet-encrypted at rest (`DCR_ENCRYPTION_KEY`).

### Entitlement Provisioning Lifecycle

Google Cloud Marketplace sends Pub/Sub events to the `/pubsub` endpoint as orders progress through their lifecycle. The `ProcurementService` (`marketplace/service.py`) processes each event type:

1. **`ENTITLEMENT_CREATION_REQUESTED`** — Customer initiates an order. The handler:
   - Creates a local entitlement record in `PENDING_APPROVAL` state
   - Resolves the Procurement Account ID (from the event payload, or by fetching the entitlement from the Procurement API) and persists it to the entitlement record
   - Approves the account via the Procurement API (idempotent — required before entitlement approval)
   - Auto-approves the entitlement via the Procurement API

2. **`ENTITLEMENT_ACTIVE`** — Google confirms the entitlement is active. The handler:
   - Resolves and persists the account ID (if not already set)
   - Updates the entitlement state to `ACTIVE` with product metadata

3. **DCR request arrives** — Gemini Enterprise sends a direct DCR request with a signed JWT containing `account_id` (sub) and `order_id` (google.order). The DCR service validates both against the Procurement API and local DB, then creates OAuth credentials.

4. **`ENTITLEMENT_PLAN_CHANGE_REQUESTED`** → auto-approved via Procurement API. **`ENTITLEMENT_PLAN_CHANGED`** → plan updated in DB.

5. **`ENTITLEMENT_CANCELLED`** / **`ENTITLEMENT_DELETED`** → Entitlement state updated, OAuth client deleted from Red Hat SSO (if GMA-created) and local DB.

All Procurement API calls are idempotent (400/409 treated as success). Failures on 5xx or network errors propagate so Pub/Sub retries the event. Account validation for DCR queries the Procurement API directly (source of truth), not the local DB.

### Usage Metering

`api/a2a/usage_plugin.py` hooks into ADK to track tokens/requests per LLM call. Hourly aggregates are stored in `UsageRecordModel` and async-reported to Google Cloud Service Control (`service_control/reporter.py`). Includes backfill for offline periods.

## Code Layout

```
src/lightspeed_agent/
├── api/app.py              # FastAPI app factory (lifespan, middleware, routes)
├── api/a2a/                # A2A protocol: routes, AgentCard, usage tracking, plugins
│                           #   (logging, output size guard, response formatter, session service)
├── auth/                   # JWT validation middleware + token introspection
├── config/                 # Pydantic BaseSettings (all env vars, validation)
├── core/agent.py           # LlmAgent creation with MCP tools + ADK AI Skills
├── core/gemini_retry.py    # Gemini HTTP retry configuration (exponential backoff + jitter)
├── core/skills/            # Bundled ADK AI Skill definitions (SKILL.md files)
├── db/                     # SQLAlchemy ORM (3 models, async engine)
├── dcr/                    # Dynamic Client Registration service
├── logging/                # Configurable audit context filter (PII gated by AUDIT_LOGGING_ENABLED)
├── marketplace/            # Marketplace handler (separate service entry point)
├── metering/               # Usage record repository + backfill
├── probes/                 # Standalone health/readiness probe server (port 8002)
├── ratelimit/              # Redis-backed distributed rate limiter
├── security/               # Body size limits + security headers middleware
├── service_control/        # Google Cloud Service Control metering
├── telemetry/              # OpenTelemetry setup (OTLP, Jaeger, Zipkin)
├── tools/                  # MCP toolset + JWT forwarding + A2A skills + schema sanitizer
└── main.py                 # Agent service entry point
```

## Configuration

All configuration is via environment variables, managed through Pydantic settings in `config/settings.py`. See `.env.example` for the complete list (30+ vars). Key variables:

**LLM / Google Cloud:**
- `GOOGLE_API_KEY` or `GOOGLE_CLOUD_PROJECT` + `GOOGLE_GENAI_USE_VERTEXAI=TRUE` (LLM access)
- `GEMINI_MODEL` (model selection, default: `gemini-2.5-flash`)
- `LLM_PROVIDER` (default: `gemini`; set to `litellm` for LiteLLM proxy backend)
- `LLM_MODEL`, `LLM_API_KEY`, `LLM_API_BASE` (LiteLLM provider overrides)
- Optional Gemini HTTP retries (Google Gen AI SDK exponential backoff + jitter): `GEMINI_HTTP_RETRY_ATTEMPTS`, `GEMINI_HTTP_RETRY_INITIAL_DELAY`, `GEMINI_HTTP_RETRY_MAX_DELAY`, `GEMINI_HTTP_RETRY_EXP_BASE`, `GEMINI_HTTP_RETRY_JITTER` (see `docs/configuration.md`)

**Database:**
- `DATABASE_URL` / `SESSION_DATABASE_URL` (PostgreSQL or SQLite)
- `DATABASE_REQUIRE_SSL` (enforce SSL for PostgreSQL; not needed for Cloud SQL Proxy)
- `DATABASE_POOL_SIZE` (default: 5), `DATABASE_POOL_MAX_OVERFLOW` (default: 10)
- `SESSION_BACKEND` (default: `memory`; set to `database` for persistent sessions)

**Auth:**
- `RED_HAT_SSO_CLIENT_ID` / `RED_HAT_SSO_CLIENT_SECRET`
- `SKIP_JWT_VALIDATION` (dev only)

**MCP:**
- `MCP_TRANSPORT_MODE`, `MCP_SERVER_URL`

**DCR:**
- `DCR_ENCRYPTION_KEY`
- `GMA_CLIENT_ID`, `GMA_CLIENT_SECRET`, `GMA_API_BASE_URL`
- `SKIP_DCR_JWT_VALIDATION` (dev only; skip DCR JWT validation for non-Cloud-Run deployments)

**Agent:**
- `AGENT_HOST`, `AGENT_PORT`
- `SKILLS_DIR` (optional: path to external ADK AI Skills directory; bundled skills always load, external skills overlay/override by name)
- `PROBES_PORT` (default: 8002; standalone health probe server port)
- `AGENT_LOGGING_DETAIL` (default: `basic`; set to `detailed` for tool arguments/results in logs)
- `AUDIT_LOGGING_ENABLED` (default: `true`; when false, PII fields are not injected into log records)
- `TOOL_RESULT_MAX_CHARS` (default: 204800; truncates oversized MCP tool output; 0 to disable)
- `SKIP_ORDER_VALIDATION` (skip order/entitlement validation in auth; for hybrid OCP deployments)

**Marketplace Handler:**
- `MARKETPLACE_HOST`, `MARKETPLACE_PORT` (default: `0.0.0.0`, `8001`)

**CORS:**
- `CORS_ALLOWED_ORIGINS` (comma-separated allowed origins; empty by default)

**Service Control:**
- `SERVICE_CONTROL_SERVICE_NAME`, `SERVICE_CONTROL_ENABLED`

**Rate Limiting:**
- `RATE_LIMIT_REDIS_URL`

**Observability:**
- `LOG_LEVEL`, `LOG_FORMAT`
- `OTEL_ENABLED`, `OTEL_EXPORTER_TYPE`, `OTEL_SERVICE_NAME`

## CI Pipeline

GitHub Actions (`.github/workflows/ci.yml`) runs on CentOS Stream 9 with Python 3.12:
1. **Konflux Verify** — validates GPG signatures and Signed-off-by trailers on Konflux bot PRs
2. **Detect Changes** — path-based filter that gates downstream jobs (python, pyproject changes)
3. **Lock File Verification** — ensures lock files are in sync with pyproject.toml (runs when pyproject.toml changes)
4. **Vulnerability Scan** — pip-audit for known CVEs
5. **Lint** — ruff + mypy
6. **Test** — pytest
7. **Build** — Podman container build
8. **Container Scan** — Trivy vulnerability scan on built container images
9. **CI Gate** — blocks merge if any job fails

Secret scanning is configured via `.gitleaks.toml`. CVE alerting for Python dependencies is managed via Renovate (`renovate.json`). See `CONTRIBUTING.md` for the CVE alert workflow.
