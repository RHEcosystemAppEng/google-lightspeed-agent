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
│  │  System Prompt = AGENT_INSTRUCTION + A2UI Schema    │    │
│  │                                                     │    │
│  │  The A2UI schema (from BasicCatalog v0.8) is        │    │
│  │  appended to the agent instruction, teaching the    │    │
│  │  LLM how to output A2UI JSON components alongside   │    │
│  │  text responses.                                    │    │
│  └──────────────────────┬──────────────────────────────┘    │
│                         │                                    │
│                         ▼                                    │
│  ┌─────────────────────────────────────────────────────┐    │
│  │              LLM Response                            │    │
│  │                                                     │    │
│  │  Text: "Here are your vulnerabilities..."            │    │
│  │  ---a2ui_JSON---                                     │    │
│  │  { "components": [ Table, Card, ... ] }              │    │
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

**Component Catalog** — A JSON Schema file defining the set of available UI component types. The agent uses the A2UI **Basic Catalog** (v0.8), which includes standard components like Text, Card, Button, Table, TextField, DateTimeInput, Image, Row, and Column. Agents can only generate components present in the catalog.

**System Prompt Augmentation** — The `a2ui-agent-sdk` generates a system prompt that includes the catalog schema and few-shot examples. This is appended to the existing `AGENT_INSTRUCTION`, so the LLM understands both its role (Red Hat Insights agent) and how to format responses with A2UI components.

**Data Model Separation** — A2UI separates UI structure from application data. Components bind to a data model via references. The agent can update data without resending the entire component tree.

**No Code Execution** — A2UI is purely declarative. The agent outputs JSON describing components; the client renders them using its own widget library. There is no iframe, no embedded JavaScript, no sandboxing needed.

### Spec Version

The agent targets **A2UI v0.8**, which is the version currently supported by Gemini Enterprise. The `a2ui-agent-sdk` supports both v0.8 and v0.9, but we pin to v0.8 for marketplace compatibility.

## Configuration

A2UI is controlled by a single environment variable:

| Variable | Default | Description |
|----------|---------|-------------|
| `A2UI_ENABLED` | `false` | Enable A2UI rich UI rendering in agent responses |

When `A2UI_ENABLED=false` (the default), the agent behaves exactly as before — plain text responses only. No A2UI code paths are activated.

When `A2UI_ENABLED=true`:

1. The agent's system prompt is augmented with the A2UI catalog schema and examples
2. The Agent Card declares the A2UI extension (`https://a2ui.org/a2a-extension/a2ui/v0.8`)
3. The Agent Card's `defaultOutputModes` includes `application/json+a2ui`

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
  "uri": "https://a2ui.org/a2a-extension/a2ui/v0.8",
  "params": {
    "supportedCatalogIds": [
      "https://a2ui.org/specification/v0_8/standard_catalog_definition.json"
    ],
    "acceptsInlineCatalogs": true
  }
}
```

This tells A2A clients (like Gemini Enterprise) that the agent supports A2UI rendering with the standard Basic Catalog.

### Output Modes

Updated from `["text"]` to `["text", "application/json+a2ui"]`, indicating the agent can produce both plain text and A2UI component responses.

## Code Structure

```
src/lightspeed_agent/
├── a2ui/                       # A2UI integration
│   ├── __init__.py
│   └── prompt.py              # Schema manager + system prompt generation
├── core/
│   └── agent.py               # create_agent() conditionally augments instruction
└── api/a2a/
    └── agent_card.py          # A2UI extension + output modes in AgentCard
```

### Key Functions

| Function | File | Purpose |
|----------|------|---------|
| `get_a2ui_schema_manager()` | `a2ui/prompt.py` | Creates the A2UI schema manager with Basic Catalog v0.8 |
| `generate_a2ui_instruction()` | `a2ui/prompt.py` | Augments the base agent instruction with A2UI schema |
| `_build_a2ui_extension()` | `api/a2a/agent_card.py` | Builds the A2UI AgentCard extension |

## Use Cases for Red Hat Insights

A2UI is particularly valuable for Insights data because structured UI makes complex data more actionable:

| Insights Service | A2UI Components | Benefit |
|-----------------|-----------------|---------|
| **Vulnerability** | Tables, Cards | CVE lists with severity badges, sortable columns |
| **Advisor** | Cards, Text | Recommendation cards with risk levels and remediation steps |
| **Inventory** | Tables | System lists with filterable attributes |
| **Remediations** | Cards, Buttons | Playbook summaries with action buttons |
| **Planning** | Tables, Text | Upgrade readiness matrices |

## Testing

### Verifying A2UI is Disabled (Default)

```bash
# Start agent
A2UI_ENABLED=false python -m lightspeed_agent.main

# Check Agent Card
curl -s http://localhost:8000/.well-known/agent.json | jq '.capabilities.extensions[].uri'
# Should only show DCR extension

curl -s http://localhost:8000/.well-known/agent.json | jq '.defaultOutputModes'
# Should be: ["text"]
```

### Verifying A2UI is Enabled

```bash
# Start agent with A2UI
A2UI_ENABLED=true python -m lightspeed_agent.main

# Check Agent Card
curl -s http://localhost:8000/.well-known/agent.json | jq '.capabilities.extensions[].uri'
# Should show both DCR and A2UI extensions

curl -s http://localhost:8000/.well-known/agent.json | jq '.defaultOutputModes'
# Should be: ["text", "application/json+a2ui"]
```

### ADK Web UI

The ADK development UI (`adk web`) renders A2UI components natively since ADK v1.24. This provides a convenient way to test A2UI rendering locally:

```bash
A2UI_ENABLED=true adk web agents
```

### Unit Tests

```bash
python -m pytest tests/test_a2ui.py -v
```

Tests cover:
- Schema manager initialization
- System prompt augmentation (contains both base instruction and A2UI schema)
- Agent Card extension presence/absence based on `A2UI_ENABLED`
- Agent Card output modes based on `A2UI_ENABLED`
- Agent creation with augmented vs. plain instruction

## References

- [A2UI Official Site](https://a2ui.org/)
- [A2UI v0.8 Specification](https://a2ui.org/specification/v0.8-a2ui/)
- [A2UI A2A Extension Specification](https://a2ui.org/specification/v0.8-a2a-extension/)
- [A2UI Agent Development Guide](https://a2ui.org/guides/agent-development/)
- [ADK A2UI Integration](https://adk.dev/integrations/a2ui/)
- [Register A2UI Agents in Gemini Enterprise](https://docs.cloud.google.com/gemini/enterprise/docs/a2ui-agents/register-and-manage-an-a2ui-agent)
- [GitHub: google/A2UI](https://github.com/google/A2UI/)
- [a2ui-agent-sdk on PyPI](https://pypi.org/project/a2ui-agent-sdk/)
