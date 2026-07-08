# A2UI Integration

This document describes the A2UI (Agent-to-User Interface) integration in the Lightspeed Agent.

## Overview

A2UI is Google's open-source protocol that enables AI agents to generate rich, interactive user interfaces declaratively via JSON. Instead of responding with plain text, the agent produces structured JSON payloads describing UI components (cards, tables, buttons, text fields, etc.). The client application — such as Gemini Enterprise — renders these as native widgets.

A2UI complements the A2A (Agent-to-Agent) protocol:

| Protocol | Purpose | Direction |
|----------|---------|-----------|
| **A2A** | Agent-to-agent communication | Agent ↔ Agent |
| **A2UI** | Agent-to-user UI rendering | Agent → User |

A2UI payloads travel as A2A `DataPart` objects with MIME type `application/json+a2ui`, so the existing A2A transport is reused.

## Why A2UI?

The Google Cloud AI Agent Marketplace / Gemini Enterprise expects registered agents to support A2UI for rich UI rendering. Benefits include:

- **Native rendering** — UI components inherit the host application's styling (Gemini Enterprise, Google Chat, custom apps)
- **Cross-platform** — the same JSON payload renders on web (React), mobile (Flutter), and desktop
- **Security by design** — no executable code crosses trust boundaries; agents can only request pre-approved components from a catalog
- **LLM-friendly** — flat component structure is easy for LLMs to generate incrementally, enabling streaming rendering
- **Multi-agent transparency** — orchestrating agents can inspect A2UI messages (they're just JSON), unlike opaque HTML blobs
- **Marketplace requirement** — first-class integration path for Gemini Enterprise registration

## How It Works

### Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Lightspeed Agent                          │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐    │
│  │                    LlmAgent                          │    │
│  │                                                     │    │
│  │  Tools: SendA2uiToClientToolset                     │    │
│  │                                                     │    │
│  │  The toolset injects A2UI schema + Insights         │    │
│  │  examples into LLM requests. The LLM calls          │    │
│  │  send_a2ui_json_to_client which validates JSON      │    │
│  │  against the catalog before delivery.               │    │
│  └──────────────────────┬──────────────────────────────┘    │
│                         │                                    │
│                         ▼                                    │
│  ┌─────────────────────────────────────────────────────┐    │
│  │              LLM Response                            │    │
│  │                                                     │    │
│  │  Text: "Here are your vulnerabilities..."            │    │
│  │  Tool call: send_a2ui_json_to_client(json=...)       │    │
│  │  → validated A2UI components (Table, Card, ...)      │    │
│  └──────────────────────┬──────────────────────────────┘    │
│                         │                                    │
│                         ▼                                    │
│  ┌─────────────────────────────────────────────────────┐    │
│  │              A2A Response                            │    │
│  │                                                     │    │
│  │  DataPart { mimeType: "application/json+a2ui" }     │    │
│  └─────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│              Client (Gemini Enterprise)                      │
│                                                             │
│  A2UI Renderer maps JSON components to native widgets:      │
│  - "Table" → native data table                              │
│  - "Card" → styled card component                           │
│  - "Button" → clickable button                              │
│  - "Text" → formatted text                                  │
└─────────────────────────────────────────────────────────────┘
```

### Key Concepts

**Component Catalog** — A JSON Schema file defining the set of available UI component types. The agent uses the A2UI **Basic Catalog** (v0.9), which includes standard components like Text, Card, Button, Row, Column, List, Tabs, TextField, DateTimeInput, and Image. Agents can only generate components present in the catalog.

**SendA2uiToClientToolset** — The agent uses the SDK's `SendA2uiToClientToolset` which automatically injects the A2UI schema and domain-specific examples into LLM requests. The LLM calls the `send_a2ui_json_to_client` tool, which validates JSON against the catalog schema before delivering it to the client. This replaces manual system prompt augmentation with server-side validation.

**Data Model Separation** — A2UI separates UI structure from application data. Components bind to a data model via references. The agent can update data without resending the entire component tree.

**No Code Execution** — A2UI is purely declarative. The agent outputs JSON describing components; the client renders them using its own widget library. There is no iframe, no embedded JavaScript, no sandboxing needed.

### Spec Version

The agent targets **A2UI v0.9**, the current stable version supported by Gemini Enterprise. The `a2ui-agent-sdk` supports v0.8 through v0.9.1.

## Configuration

A2UI is controlled by a single environment variable:

| Variable | Default | Description |
|----------|---------|-------------|
| `A2UI_ENABLED` | `false` | Enable A2UI rich UI rendering in agent responses |

When `A2UI_ENABLED=false` (the default), the agent behaves exactly as before — plain text responses only. No A2UI code paths are activated.

When `A2UI_ENABLED=true`:

1. The `SendA2uiToClientToolset` is added to the agent's tools, injecting the A2UI catalog schema and domain-specific Insights examples into LLM requests (the LLM validates JSON via the `send_a2ui_json_to_client` tool)
2. The Agent Card declares the A2UI extension (`https://a2ui.org/a2a-extension/a2ui/v0.9`)
3. The Agent Card's `defaultOutputModes` includes `application/json+a2ui`
4. The Agent Card's `defaultInputModes` includes `application/json+a2ui` (for receiving A2UI action payloads like button clicks)

### Enabling A2UI

```bash
# In .env or environment
A2UI_ENABLED=true
```

Or in the Podman configmap:

```yaml
A2UI_ENABLED: "true"
```

Or as a Cloud Run environment variable:

```bash
gcloud run services update lightspeed-agent \
  --set-env-vars A2UI_ENABLED=true
```

## Agent Card Changes

When A2UI is enabled, the Agent Card (`/.well-known/agent.json`) is updated:

### A2UI Extension

Added to `capabilities.extensions`:

```json
{
  "uri": "https://a2ui.org/a2a-extension/a2ui/v0.9",
  "params": {
    "supportedCatalogIds": [
      "https://a2ui.org/specification/v0_9/catalogs/basic/catalog.json"
    ],
    "acceptsInlineCatalogs": true
  }
}
```

This tells A2A clients (like Gemini Enterprise) that the agent supports A2UI rendering with the standard Basic Catalog.

### Output Modes

Updated from `["text/plain"]` to `["text/plain", "application/json+a2ui"]`, indicating the agent can produce both plain text and A2UI component responses.

## Code Structure

```
src/lightspeed_agent/
├── a2ui/                       # A2UI integration
│   ├── __init__.py
│   ├── examples.py            # Domain-specific A2UI examples for Insights data
│   └── prompt.py              # Schema manager + catalog access
├── core/
│   └── agent.py               # create_agent() adds SendA2uiToClientToolset
└── api/a2a/
    └── agent_card.py          # A2UI extension + input/output modes in AgentCard
```

### Key Functions

| Function | File | Purpose |
|----------|------|---------|
| `get_a2ui_schema_manager()` | `a2ui/prompt.py` | Creates and caches the A2UI schema manager with Basic Catalog v0.9 |
| `get_a2ui_catalog()` | `a2ui/prompt.py` | Returns the A2uiCatalog for the Basic Catalog v0.9 |
| `get_insights_a2ui_examples()` | `a2ui/prompt.py` | Returns domain-specific A2UI examples for Insights data |
| `_build_a2ui_extension()` | `api/a2a/agent_card.py` | Builds the A2UI AgentCard extension |

## Use Cases for Red Hat Insights

A2UI is particularly valuable for Insights data because structured UI makes complex data more actionable:

| Insights Service | A2UI Components | Benefit |
|-----------------|-----------------|---------|
| **Vulnerability** | Lists, Cards | CVE lists with severity badges, structured detail cards |
| **Advisor** | Cards, Text | Recommendation cards with risk levels and remediation steps |
| **Inventory** | Lists, Cards | System lists with structured attributes |
| **Remediations** | Cards, Buttons | Playbook summaries with action buttons |
| **Planning** | Lists, Text | Upgrade readiness views |

## Testing

### Unit Tests

Run the A2UI-specific tests (no credentials or services required):

```bash
source .venv/bin/activate
python -m pytest tests/test_a2ui.py -v
```

Tests cover:
- Schema manager initialization and caching
- A2UI catalog and Insights examples retrieval
- Agent Card extension presence/absence based on `A2UI_ENABLED`
- Agent Card output modes based on `A2UI_ENABLED`
- Agent Card input modes based on `A2UI_ENABLED`
- Agent creation with/without A2UI toolset

### Agent Card Verification

Start the agent in dev mode and verify the Agent Card reflects A2UI configuration.

**With A2UI enabled:**

```bash
A2UI_ENABLED=true SKIP_JWT_VALIDATION=true python -m lightspeed_agent.main
```

In another terminal:

```bash
# Verify A2UI extension is declared
curl -s http://localhost:8000/.well-known/agent.json | jq '.capabilities.extensions[].uri'
# Should include (among others):
#   "https://cloud.google.com/marketplace/docs/partners/ai-agents/setup-dcr"
#   "urn:redhat:lightspeed:access-mode"
#   "urn:redhat:lightspeed:rate-limiting"
#   "https://a2ui.org/a2a-extension/a2ui/v0.9"

# Verify output modes include A2UI
curl -s http://localhost:8000/.well-known/agent.json | jq '.defaultOutputModes'
# Should be: ["text/plain", "application/json+a2ui"]
```

**With A2UI disabled (default):**

```bash
A2UI_ENABLED=false SKIP_JWT_VALIDATION=true python -m lightspeed_agent.main
```

```bash
curl -s http://localhost:8000/.well-known/agent.json | jq '.defaultOutputModes'
# Should be: ["text/plain"]

curl -s http://localhost:8000/.well-known/agent.json | jq '.capabilities.extensions[].uri'
# Should show DCR, access-mode, and rate-limiting extensions — but NOT the A2UI extension
```

### Interactive Testing with ADK Web UI (Recommended)

The ADK development UI (`adk web`) renders A2UI components natively since ADK v1.24. This is the easiest way to see A2UI rendering in action because it **bypasses the entire FastAPI middleware stack** — no authentication, no order_id validation, no rate limiting. ADK runs the agent directly.

**Prerequisites:**
- `GOOGLE_API_KEY` set in `.env` (or Vertex AI configured)
- MCP server running (optional — agent works without it but has no Insights tools)

```bash
source .venv/bin/activate
A2UI_ENABLED=true adk web agents
```

Open the browser URL it prints and try queries like:
- "Show my system vulnerabilities"
- "List my registered systems"
- "What are the top advisor recommendations?"

The responses should include rendered UI components (tables, cards) alongside text.

### Interactive Testing with the API Server

To test A2UI through the full FastAPI stack (auth, rate limiting, A2A protocol), use dev mode with `SKIP_JWT_VALIDATION=true`.

> **Note on order_id:** In production, the auth middleware requires a valid order_id linked to an active marketplace entitlement (returns 403 otherwise). With `SKIP_JWT_VALIDATION=true`, this check is skipped entirely. Usage metering silently logs a warning and continues. Rate limiting falls back to IP-based. The agent executes normally.

**Prerequisites:**
- `GOOGLE_API_KEY` set in `.env`
- Redis running (for rate limiting) — or accept 500 on rate limit check
- MCP server running (optional)

**1. Start the agent:**

```bash
A2UI_ENABLED=true SKIP_JWT_VALIDATION=true python -m lightspeed_agent.main
```

**2. Send a query via curl:**

```bash
curl -X POST http://localhost:8000/ \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "message/send",
    "id": "1",
    "params": {
      "message": {
        "messageId": "1",
        "role": "user",
        "parts": [{"type": "text", "text": "Show my vulnerabilities"}]
      }
    }
  }'
```

The response will contain A2A parts — text parts with plain text and data parts with `mimeType: application/json+a2ui` containing the UI component JSON.

**3. (Optional) Provide a fake order_id for usage tracking:**

A Bearer token must be present for `X-Order-Id` to be picked up (the middleware only reads the header inside the token extraction path):

```bash
curl -X POST http://localhost:8000/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer fake-dev-token" \
  -H "X-Order-Id: test-order-123" \
  -d '{
    "jsonrpc": "2.0",
    "method": "message/send",
    "id": "1",
    "params": {
      "message": {
        "messageId": "1",
        "role": "user",
        "parts": [{"type": "text", "text": "List my systems"}]
      }
    }
  }'
```

The `X-Order-Id` header is picked up in dev mode (when a Bearer token is also present) so usage tracking persists metrics. The token itself is not validated when `SKIP_JWT_VALIDATION=true`, but it is forwarded to the MCP server.

### Testing with Podman

To test A2UI in a containerized deployment:

1. Set `A2UI_ENABLED: "true"` in `deploy/podman/lightspeed-agent-configmap.yaml`
2. Rebuild and restart the agent pod:

```bash
make build-agent
podman kube down deploy/podman/lightspeed-agent-pod.yaml
podman kube play \
  --configmap deploy/podman/lightspeed-agent-configmap.yaml \
  deploy/podman/lightspeed-agent-pod.yaml
```

3. Verify via the A2A Inspector at http://localhost:8080 or curl:

```bash
curl -s http://localhost:8000/.well-known/agent.json | jq '.capabilities.extensions[].uri'
```

## References

- [A2UI Official Site](https://a2ui.org/)
- [A2UI v0.9 Specification](https://a2ui.org/specification/v0.9-a2ui/)
- [A2UI A2A Extension Specification](https://a2ui.org/specification/v0.9-a2a-extension/)
- [A2UI Agent Development Guide](https://a2ui.org/guides/agent-development/)
- [ADK A2UI Integration](https://adk.dev/integrations/a2ui/)
- [Register A2UI Agents in Gemini Enterprise](https://docs.cloud.google.com/gemini/enterprise/docs/a2ui-agents/register-and-manage-an-a2ui-agent)
- [GitHub: google/A2UI](https://github.com/google/A2UI/)
- [a2ui-agent-sdk on PyPI](https://pypi.org/project/a2ui-agent-sdk/)
