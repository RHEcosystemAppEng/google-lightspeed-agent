# MLflow Evaluation

Evaluation pipeline for the Lightspeed Agent using [MLflow GenAI Evaluation](https://mlflow.org/docs/latest/genai/eval-monitor/). Sends questions to a deployed agent via A2A, then scores the responses using LLM-as-a-judge and code-based scorers.

## How It Works

```
Developer laptop (on VPN)
    │
    ├──► Agent (A2A endpoint) ── sends evaluation questions
    │         │
    │         └──► Traces flow to MLflow automatically (already configured)
    │
    ├──► Judge model (self-hosted) ── scores agent responses
    │
    └──► MLflow server ── stores evaluation results
```

1. Load evaluation questions from `dataset.json` (or registered MLflow dataset)
2. Send each question to the agent's A2A endpoint with a Bearer token
3. Collect the agent's text response
4. Run scorers (deterministic + LLM judges) against each response
5. Log results to the MLflow experiment

## Prerequisites

- Python virtual environment with eval dependencies
- VPN access to the OpenShift cluster (agent + MLflow + judge model endpoints)
- A valid Bearer token for the agent (from Red Hat SSO)

## Setup

```bash
# Install eval dependencies (from repo root, venv activated)
pip install -e ".[eval]"
```

This installs `mlflow>=3.15.0`. Versions below 3.14.0 silently fall back to `api.openai.com` for built-in scorers like `Correctness()`, even when `MLFLOW_GENAI_JUDGE_DEFAULT_MODEL` is set.

## Configuration

### Judge Model (required)

LLM-as-a-judge scorers need a model to evaluate responses. The script **refuses to run** without a judge model set, to prevent evaluation data from being sent to external cloud providers.

```bash
export MLFLOW_GENAI_JUDGE_DEFAULT_MODEL="openai:/Qwen/Qwen3-14B"
export OPENAI_BASE_URL="https://<judge-endpoint>/v1"
export OPENAI_API_KEY="<api-key>"
```

You can also pass `--judge-model "openai:/Qwen/Qwen3-14B"` on the command line. The CLI flag takes precedence over the environment variable.

### Data Privacy

LLM-as-a-judge scorers send agent responses (which may contain CVEs, host names, advisor details) to the judge model for scoring. Use a self-hosted model to keep data within your network.

All LLM scorers receive an explicit `model=judge_model` parameter to prevent any fallback to external providers (e.g., OpenAI, Anthropic) even if default configuration is present.

### SSL/TLS for Internal Clusters

OpenShift clusters and internal model endpoints typically use self-signed certificates that Python doesn't trust by default. To skip certificate verification (connections remain encrypted — only the CA check is skipped):

```bash
export MLFLOW_TRACKING_INSECURE_TLS=true
```

This covers all HTTPS calls: MLflow tracking, agent A2A requests, and judge model calls.

For proper certificate verification instead, export the cluster's CA certificate:

```bash
# Extract the OpenShift ingress CA
oc extract configmap/router-ca -n openshift-ingress-operator \
    --keys=ca-bundle.crt --to=/tmp/

# Point Python at it
export REQUESTS_CA_BUNDLE=/tmp/ca-bundle.crt
```

If the agent and judge endpoints are on different clusters, concatenate both CA certs into a single bundle file.

## Dataset Management

Evaluation questions can be stored as a **registered dataset on the MLflow server** or as a local JSON file. The registered dataset is the default — it lives on the server, is editable from the MLflow UI, and is shared across the team.

### Upload dataset to MLflow (one-time setup)

Seed the MLflow server with questions from `dataset.json`:

```bash
python evals/run_eval.py \
    --upload-dataset \
    --mlflow-uri https://mlflow-<namespace>.apps.<cluster>/
```

This creates a registered dataset named `lightspeed-agent-eval` on the server. Run it again to merge new questions from an updated `dataset.json` — existing records are preserved.

After uploading, the dataset appears in the MLflow UI under the **Datasets** tab where records can be viewed, edited, and tagged.

### How data is loaded at eval time

1. The script tries to load the registered dataset from the MLflow server by name
2. If the dataset is not found, it falls back to the local `dataset.json` file

No extra flags needed — just run the eval and it picks up the registered dataset automatically.

## Usage

```bash
# Prefer environment variables for tokens to avoid exposure in process listings
export EVAL_AGENT_TOKEN="<bearer-token>"

python -u evals/run_eval.py \
    --agent-url https://lightspeed-agent-<namespace>.apps.<cluster>/ \
    --mlflow-uri https://mlflow-<namespace>.apps.<cluster>/ \
    --judge-model "openai:/Qwen/Qwen3-14B"
```

Use `python -u` for unbuffered output to see progress in real time.

### Options

| Flag | Env Var | Default | Description |
|------|---------|---------|-------------|
| `--agent-url` | `EVAL_AGENT_URL` | `http://localhost:8000` | Agent A2A endpoint |
| `--token` | `EVAL_AGENT_TOKEN` | (required) | Bearer token for authentication |
| `--judge-model` | `MLFLOW_GENAI_JUDGE_DEFAULT_MODEL` | (required) | Judge model URI (e.g. `openai:/Qwen/Qwen3-14B`) |
| `--mlflow-uri` | `MLFLOW_TRACKING_URI` | `http://localhost:5000` | MLflow tracking server |
| `--experiment` | | `lightspeed-agent-eval` | MLflow experiment name |
| `--timeout` | | `180` | Timeout per question (seconds) |
| `--dataset` | | `evals/dataset.json` | Local dataset JSON (fallback or upload source) |
| `--dataset-name` | | (same as `--experiment`) | Name of the registered MLflow dataset |
| `--upload-dataset` | | | Upload local JSON to MLflow server and exit |
| `--agent-experiment` | | `lightspeed-agent` | MLflow experiment name where the agent logs traces |
| `--agent-experiment-id` | | | MLflow experiment ID for agent traces (overrides `--agent-experiment`) |
| `--trace-workers` | | `10` | Concurrent workers for fetching agent traces |
| `--trace-hours` | | `12` | Hours back to search for agent traces |

## Scorers

### MLflow built-in scorers

These scorers use the model from `--judge-model` or `MLFLOW_GENAI_JUDGE_DEFAULT_MODEL` to evaluate responses. The model is passed **explicitly** to each scorer to prevent fallback to external providers.

| Scorer | Description |
|--------|-------------|
| Correctness | Compares response against expected behavior |
| RelevanceToQuery | Checks if the response addresses the question |
| ExpectationsGuidelines | Evaluates per-row whether the response matches the `expected_behavior` field |

### Custom scorers (`evals/scorers/`)

Code-based and LLM-judge scorers defined locally as reusable classes.

| Scorer | Type | Description |
|--------|------|-------------|
| ResponseReceived | Deterministic | Validates agent returned a usable response (non-empty, no error, ≥10 chars) |
| AnswerCorrectness | Deterministic | Grades by question type: binary, single_select, multiple_select, substring_match, exact_match, ordered_list. Score: 0.0–1.0 |
| SafetyGuidelines | LLM judge | Enforces safety rules: no tool name leakage, no code generation, domain boundaries, no internal API disclosure |
| ErrorHandlingGuidelines | LLM judge | Evaluates graceful error handling: no raw errors, honest failure acknowledgment, suggests alternatives, professional tone |
| ToolCallCorrectness | Trace-based | Queries agent traces on the MLflow server to verify the correct MCP tools were called (yes / partial / no / unknown) |

`ToolCallCorrectness` searches the `--agent-experiment` experiment for traces matching each question, extracts TOOL-type spans, and compares them against `expected_tools` in the dataset. Traces are fetched concurrently (`--trace-workers`) and cached for the duration of the eval run. Only traces from the last `--trace-hours` hours are searched.

## Dataset

`dataset.json` contains 8 curated evaluation questions covering all question types. Each entry:

```json
{
    "id": "V-001",
    "category": "vulnerability",
    "question": "Is CVE-2024-6387 affecting any of my systems?",
    "question_type": "binary",
    "options": null,
    "expected_response": "yes",
    "expected_tools": ["vulnerability__get_cve_systems"],
    "scenario_type": "single_tool",
    "expected_behavior": [
        "The agent should call vulnerability__get_cve_systems with CVE-2024-6387...",
        "The agent should return the list of impacted hosts"
    ],
    "difficulty": "easy",
    "scenario_intent": "functional"
}
```

### Question Types

| Type | Cases | How it's graded |
|------|-------|-----------------|
| `binary` | V-001 | Yes/no sentiment detection in first sentence |
| `single_select` | V-009 | Expected answer appears in response |
| `multiple_select` | V-017 | Partial credit for each expected item found |
| `substring_match` | V-025 | All required keywords present |
| `exact_match` | V-033 | Normalized string equality (0.8 for substring) |
| `ordered_list` | OL-001 | Items present in correct order |
| `free_form` | E-001, FF-001 | Skipped — graded by LLM correctness judge |

### Fields

| Field | Description |
|-------|-------------|
| `id` | Identifier (e.g. V-001, E-001, FF-001, OL-001) |
| `category` | Domain category (vulnerability, inventory, guardrails) |
| `question` | The prompt sent to the agent |
| `question_type` | Type of expected answer (binary, single_select, etc.) |
| `options` | Multiple-choice options (null if not applicable) |
| `expected_response` | Ground truth for Correctness and AnswerCorrectness scorers |
| `expected_tools` | MCP tools the agent should call |
| `scenario_type` | single_tool, no_tool |
| `expected_behavior` | Behavioral guidelines for ExpectationsGuidelines scorer (list) |
| `difficulty` | easy, medium |
| `scenario_intent` | functional, meta_knowledge, adversarial |
| `note` | (optional) Context about data dependencies or known limitations |
| `grading_note` | (optional) Notes on expected scorer behavior for this case |

## Viewing Results

Results are logged to the MLflow experiment specified by `--experiment`. Open the MLflow UI and navigate to the experiment to see per-question scores, compare evaluation runs, and drill into individual results.
