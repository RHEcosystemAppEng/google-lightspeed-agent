#!/usr/bin/env python3
"""MLflow evaluation for the Lightspeed Agent.

Sends evaluation questions to a deployed agent via A2A, then scores the
responses using MLflow's GenAI evaluation framework.

Scorers:
    MLflow built-in (LLM-as-judge):
        Correctness — checks if expected facts are supported by the response
        RelevanceToQuery — checks if the response addresses the question
        ExpectationsGuidelines — checks per-row behavioral constraints

    Custom deterministic (no LLM needed):
        ResponseReceived — validates agent returned a usable response
        AnswerCorrectness — grades by question_type (binary, single_select,
            multiple_select, substring_match, exact_match, ordered_list)

    Custom LLM-judge (pre-configured Guidelines):
        SafetyGuidelines — tool name leakage, code generation, domain boundaries
        ErrorHandlingGuidelines — graceful error handling, honest failures

    Custom trace-based (queries MLflow, no LLM needed):
        ToolCallCorrectness — verifies the agent called the expected MCP tools

Data privacy: LLM-as-a-judge scorers send agent responses to the judge model
for scoring. A self-hosted judge model is required to prevent evaluation data
from being sent to external cloud providers.

Usage:
    # Set judge model (required — VPN-backed for internal data):
    export MLFLOW_GENAI_JUDGE_DEFAULT_MODEL="openai:/Qwen/Qwen3-14B"
    export OPENAI_BASE_URL="https://<judge-endpoint>/v1"
    export OPENAI_API_KEY="<api-key>"

    # Skip TLS verification for internal clusters:
    export MLFLOW_TRACKING_INSECURE_TLS=true

    # Run evaluation:
    python -u evals/run_eval.py \\
        --agent-url https://<agent-endpoint>/ \\
        --token "<bearer-token>" \\
        --mlflow-uri https://<mlflow-endpoint>/ \\
        --judge-model "openai:/Qwen/Qwen3-14B"
"""

from __future__ import annotations

import argparse
import json
import os
import ssl
import sys
import time
import uuid
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import mlflow
from mlflow.genai.datasets import create_dataset, get_dataset
from mlflow.genai.scorers import Correctness, ExpectationsGuidelines, RelevanceToQuery

from scorers import (
    AnswerCorrectness,
    ErrorHandlingGuidelines,
    ResponseReceived,
    SafetyGuidelines,
    ToolCallCorrectness,
)

SCRIPT_DIR = Path(__file__).parent
DATASET_PATH = SCRIPT_DIR / "dataset.json"


def _extract_final_answer(text: str) -> str:
    """Extract only the user-facing final answer from the agent response.

    Gemini models wrap internal chain-of-thought in /*REASONING*/ and
    /*PLANNING*/ blocks. Only the content after /*FINAL_ANSWER*/ is what
    the user sees — everything before it is internal and should not be scored.
    """
    if "/*FINAL_ANSWER*/" in text:
        _, _, answer = text.partition("/*FINAL_ANSWER*/")
        return answer.strip()
    return text.strip()


def load_dataset(path: Path) -> list[dict]:
    with open(path) as f:
        return json.load(f)


def format_for_mlflow(dataset: list[dict]) -> list[dict]:
    """Convert dataset entries to MLflow evaluate format (inputs + expectations).

    Field mapping for built-in scorers:
        expected_response → expectations.expected_response (Correctness)
        expected_behavior → expectations.guidelines (ExpectationsGuidelines)
    """
    return [
        {
            "inputs": {"question": entry["question"]},
            "expectations": {
                "expected_response": entry.get("expected_response", ""),
                "guidelines": entry["expected_behavior"],
                "scenario_type": entry["scenario_type"],
                "question_type": entry.get("question_type", ""),
                "category": entry["category"],
                "difficulty": entry.get("difficulty", ""),
                "expected_tools": json.dumps(entry.get("expected_tools", [])),
                "options": json.dumps(entry.get("options")),
                "eval_id": entry["id"],
            },
        }
        for entry in dataset
    ]


def send_a2a_message(agent_url: str, token: str, message: str, timeout: int) -> str:
    """Send a JSON-RPC message/send to the agent and return the text response."""
    url = agent_url.rstrip("/") + "/"
    payload = json.dumps({
        "jsonrpc": "2.0",
        "id": str(uuid.uuid4()),
        "method": "message/send",
        "params": {
            "message": {
                "role": "user",
                "parts": [{"kind": "text", "text": message}],
                "messageId": str(uuid.uuid4()),
            },
        },
    }).encode("utf-8")

    ctx = ssl.create_default_context()
    if os.environ.get("MLFLOW_TRACKING_INSECURE_TLS", "").lower() == "true":
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE

    request = Request(
        url,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
        },
        method="POST",
        data=payload,
    )

    result = urlopen(request, timeout=timeout, context=ctx).read()
    response = json.loads(result)

    if "error" in response:
        raise RuntimeError(
            f"Agent returned error: {response['error'].get('message', response['error'])}"
        )

    parts = []
    task_result = response.get("result", {})

    for artifact in task_result.get("artifacts", []):
        for part in artifact.get("parts", []):
            if (part.get("kind") == "text" or part.get("type") == "text") \
                    and not part.get("metadata", {}).get("adk_thought"):
                parts.append(part.get("text", ""))

    status_msg = task_result.get("status", {}).get("message", {})
    if status_msg:
        for part in status_msg.get("parts", []):
            if part.get("kind") == "text" or part.get("type") == "text":
                parts.append(part.get("text", ""))

    text = "\n".join(parts) if parts else "(no text response)"
    return _extract_final_answer(text)


def make_predict_fn(agent_url: str, token: str, timeout: int):
    """Create a predict function that sends questions to the agent."""
    call_count = [0]
    total = [0]

    def set_total(n: int):
        total[0] = n

    @mlflow.trace
    def predict_fn(question: str) -> str:
        call_count[0] += 1
        short_q = question[:80] + "..." if len(question) > 80 else question
        print(f"  [{call_count[0]}/{total[0]}] Sending: {short_q}")

        start = time.time()
        try:
            response = send_a2a_message(agent_url, token, question, timeout)
            elapsed = time.time() - start
            print(f"           Got response ({elapsed:.1f}s, {len(response)} chars)")
            return response
        except (HTTPError, URLError, RuntimeError) as e:
            elapsed = time.time() - start
            print(f"           ERROR after {elapsed:.1f}s: {e}")
            return f"[ERROR] {e}"

    return predict_fn, set_total


def _upload_dataset(local_path: Path, dataset_name: str) -> None:
    """Upload local dataset JSON to the MLflow server as a registered dataset."""
    raw = load_dataset(local_path)
    records = format_for_mlflow(raw)
    try:
        ds = get_dataset(name=dataset_name)
        print(f"Found existing dataset '{dataset_name}', merging {len(records)} records...")
    except Exception:
        ds = create_dataset(name=dataset_name)
        print(f"Created new dataset '{dataset_name}', uploading {len(records)} records...")
    ds.merge_records(records)
    print(f"Done. Dataset '{dataset_name}' now has {len(ds.to_df())} records.")


def _load_eval_data(dataset_name: str, local_path: Path):
    """Load evaluation data from MLflow server, falling back to local JSON."""
    try:
        ds = get_dataset(name=dataset_name)
        n = len(ds.to_df())
        print(f"Using registered dataset '{dataset_name}' ({n} records)")
        return ds
    except Exception:
        print(f"Dataset '{dataset_name}' not found on server, using local {local_path}")
        raw = load_dataset(local_path)
        mlflow_data = format_for_mlflow(raw)
        print(f"Loaded {len(raw)} evaluation questions from {local_path}")
        return mlflow_data


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run MLflow evaluation against a deployed Lightspeed Agent"
    )
    parser.add_argument(
        "--agent-url",
        default=os.environ.get("EVAL_AGENT_URL", "http://localhost:8000"),
        help="Agent A2A endpoint URL",
    )
    parser.add_argument(
        "--token",
        default=os.environ.get("EVAL_AGENT_TOKEN", ""),
        help="Bearer token for agent authentication",
    )
    parser.add_argument(
        "--judge-model",
        default=None,
        help="Judge model URI (e.g. openai:/Qwen/Qwen3-14B). "
        "Falls back to MLFLOW_GENAI_JUDGE_DEFAULT_MODEL env var.",
    )
    parser.add_argument(
        "--mlflow-uri",
        default=os.environ.get("MLFLOW_TRACKING_URI", "http://localhost:5000"),
        help="MLflow tracking server URI",
    )
    parser.add_argument(
        "--experiment",
        default="lightspeed-agent-eval",
        help="MLflow experiment name for evaluation results",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=180,
        help="Timeout in seconds per agent request (default: 180)",
    )
    parser.add_argument(
        "--dataset",
        type=Path,
        default=DATASET_PATH,
        help="Path to local dataset JSON (used with --upload-dataset or as fallback)",
    )
    parser.add_argument(
        "--dataset-name",
        default=None,
        help="Name of the registered MLflow dataset (defaults to --experiment value)",
    )
    parser.add_argument(
        "--upload-dataset",
        action="store_true",
        help="Upload local dataset JSON to MLflow server and exit (one-time setup)",
    )
    parser.add_argument(
        "--agent-experiment",
        default="lightspeed-agent",
        help="MLflow experiment where the agent logs traces (for tool_call_correctness)",
    )
    parser.add_argument(
        "--agent-experiment-id",
        default=None,
        help="MLflow experiment ID for agent traces (overrides --agent-experiment)",
    )
    parser.add_argument(
        "--trace-workers",
        type=int,
        default=10,
        help="Concurrent workers for fetching agent traces (default: 10)",
    )
    parser.add_argument(
        "--trace-hours",
        type=int,
        default=12,
        help="Hours back to search for agent traces (default: 12)",
    )
    args = parser.parse_args()

    if not args.dataset_name:
        args.dataset_name = args.experiment

    # ── Safeguard: require judge model for data privacy ──────────────
    judge_model = args.judge_model or os.environ.get("MLFLOW_GENAI_JUDGE_DEFAULT_MODEL", "")

    if not args.upload_dataset:
        if not args.token:
            print("ERROR: --token required (or set EVAL_AGENT_TOKEN)", file=sys.stderr)
            sys.exit(1)

        if not judge_model:
            print(
                "ERROR: Judge model not set. Pass --judge-model or set "
                "MLFLOW_GENAI_JUDGE_DEFAULT_MODEL. A self-hosted judge model is "
                "required to prevent evaluation data from being sent to external "
                "cloud providers.",
                file=sys.stderr,
            )
            sys.exit(1)

    # ── Apply TLS patch for internal clusters ────────────────────────
    if os.environ.get("MLFLOW_TRACKING_INSECURE_TLS", "").lower() == "true":
        import requests.adapters
        import urllib3

        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        _original_send = requests.adapters.HTTPAdapter.send

        def _patched_send(self, request, **kwargs):
            kwargs["verify"] = False
            return _original_send(self, request, **kwargs)

        requests.adapters.HTTPAdapter.send = _patched_send

    # ── Rate limiting for judge model ────────────────────────────────
    os.environ.setdefault("MLFLOW_GENAI_EVAL_MAX_WORKERS", "1")

    # ── Configure MLflow ──────────────────────────────────────────────
    mlflow.set_tracking_uri(args.mlflow_uri)
    mlflow.set_experiment(args.experiment)
    print(f"MLflow tracking: {args.mlflow_uri}")
    print(f"MLflow experiment: {args.experiment}")

    # ── Upload dataset mode ──────────────────────────────────────────
    if args.upload_dataset:
        _upload_dataset(args.dataset, args.dataset_name)
        return

    # ── Load dataset ──────────────────────────────────────────────────
    eval_data = _load_eval_data(args.dataset_name, args.dataset)

    print(f"Judge model: {judge_model}")

    # ── Build predict function ────────────────────────────────────────
    predict_fn, set_total = make_predict_fn(args.agent_url, args.token, args.timeout)
    n_questions = len(eval_data.to_df()) if hasattr(eval_data, "to_df") else len(eval_data)
    set_total(n_questions)

    # ── Build scorer list ─────────────────────────────────────────────
    scorers = [
        # Deterministic (no LLM needed)
        ResponseReceived(),
        AnswerCorrectness(),
        # MLflow built-in LLM judges (explicit model to prevent fallback)
        Correctness(model=judge_model),
        RelevanceToQuery(model=judge_model),
        ExpectationsGuidelines(model=judge_model),
        # Custom LLM judges (explicit model to prevent fallback)
        SafetyGuidelines(model=judge_model),
        ErrorHandlingGuidelines(model=judge_model),
        # Trace-based (queries MLflow for actual tool calls)
        ToolCallCorrectness(
            agent_experiment_name=args.agent_experiment,
            agent_experiment_id=args.agent_experiment_id,
            trace_workers=args.trace_workers,
            trace_hours=args.trace_hours,
        ),
    ]

    print(f"\nStarting evaluation ({n_questions} questions, {len(scorers)} scorers)...\n")

    # ── Evaluate ──────────────────────────────────────────────────────
    results = mlflow.genai.evaluate(
        data=eval_data,
        predict_fn=predict_fn,
        scorers=scorers,
    )

    # ── Print results ─────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("Evaluation complete!")
    print(f"Results logged to experiment: {args.experiment}")
    print(f"View results at: {args.mlflow_uri}")
    print("=" * 60)

    if hasattr(results, "tables") and "eval_results" in results.tables:
        df = results.tables["eval_results"]
        print(f"\nResults summary ({len(df)} rows):")
        print(df.to_string())


if __name__ == "__main__":
    main()
