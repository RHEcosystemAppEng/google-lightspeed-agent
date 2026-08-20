"""Custom scorer that verifies tool call correctness by querying agent traces.

Searches the agent's MLflow experiment for traces matching each evaluation
question, extracts TOOL-type spans, and compares them against the
expected_tools field from the dataset.

Results:
    yes     — all expected tools called, no unexpected tools
    partial — some expected tools called, some missing, no unexpected
    no      — unexpected tools called, or none of the expected tools called
    unknown — could not find the agent's trace on the MLflow server
"""

from __future__ import annotations

import json
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import mlflow
from mlflow.entities import Feedback, SpanType
from mlflow.genai.scorers.base import Scorer


class ToolCallCorrectness(Scorer):
    """Check if the agent called the expected MCP tools by querying its traces."""

    name: str = "tool_call_correctness"
    agent_experiment_name: str | None = None
    agent_experiment_id: str | None = None
    trace_workers: int = 10
    trace_hours: int = 12

    def model_post_init(self, __context):
        object.__setattr__(self, "_experiment_id_resolved", None)
        object.__setattr__(self, "_trace_cache", [])
        object.__setattr__(self, "_cache_lock", threading.Lock())
        if self.agent_experiment_id:
            self._experiment_id_resolved = self.agent_experiment_id
            print(f"Agent traces experiment ID: {self._experiment_id_resolved}")
        elif self.agent_experiment_name:
            exp = mlflow.get_experiment_by_name(self.agent_experiment_name)
            if not exp:
                print(
                    f"ERROR: Agent experiment '{self.agent_experiment_name}' not found on "
                    "MLflow server. Tool call correctness cannot be checked without agent "
                    "traces. Use agent_experiment_name or agent_experiment_id to specify "
                    "the correct value.",
                    file=sys.stderr,
                )
                sys.exit(1)
            self._experiment_id_resolved = exp.experiment_id
            print(
                f"Agent traces experiment: {self.agent_experiment_name} "
                f"(ID {self._experiment_id_resolved})"
            )
        else:
            print(
                "ERROR: Either agent_experiment_name or agent_experiment_id is required "
                "for ToolCallCorrectness.",
                file=sys.stderr,
            )
            sys.exit(1)
        self._trace_cache = []
        self._cache_lock = threading.Lock()

    def _load_traces(self):
        with self._cache_lock:
            if self._trace_cache:
                return self._trace_cache
            since_ms = int((time.time() - self.trace_hours * 3600) * 1000)
            try:
                stubs = mlflow.search_traces(
                    locations=[self._experiment_id_resolved],
                    filter_string=f"trace.timestamp_ms > {since_ms}",
                    order_by=["timestamp_ms DESC"],
                    return_type="list",
                    include_spans=False,
                )
            except Exception as e:
                print(f"    [tool_call] ERROR searching traces: {e}")
                return []

            print(
                f"    [tool_call] Fetching {len(stubs)} traces from experiment "
                f"{self._experiment_id_resolved} ({self.trace_workers} concurrent workers)..."
            )

            def _fetch(stub):
                try:
                    return mlflow.get_trace(stub.info.trace_id)
                except Exception:
                    return None

            with ThreadPoolExecutor(max_workers=self.trace_workers) as pool:
                results = pool.map(_fetch, stubs)
                self._trace_cache.extend(t for t in results if t is not None)
            print(f"    [tool_call] Cached {len(self._trace_cache)} traces")
            return self._trace_cache

    def _find_trace(self, question: str):
        traces = self._load_traces()
        for t in traces:
            spans = t.data.spans if t.data else []
            for span in spans:
                if question in str(span.inputs or ""):
                    return t
        return None

    def __call__(self, *, inputs, expectations, **kwargs):
        expected_raw = expectations.get("expected_tools", "[]")
        expected = json.loads(expected_raw) if isinstance(expected_raw, str) else expected_raw
        if not expected:
            return Feedback(
                name=self.name,
                value="yes",
                rationale="No tools expected for this question",
            )
        question = inputs.get("question", "")
        trace = self._find_trace(question)
        if not trace:
            return Feedback(
                name=self.name,
                value="unknown",
                rationale="Could not find agent trace on MLflow server",
            )

        tool_spans = trace.search_spans(span_type=SpanType.TOOL)
        tools_called = {
            span.name.removeprefix("execute_tool").strip() for span in tool_spans
        }
        expected_set = set(expected)
        missing = expected_set - tools_called
        unexpected = tools_called - expected_set

        if unexpected:
            return Feedback(
                name=self.name,
                value="no",
                rationale=f"Unexpected tools called: {sorted(unexpected)}. "
                f"Expected: {sorted(expected_set)}. Called: {sorted(tools_called)}",
            )
        if not missing:
            return Feedback(
                name=self.name,
                value="yes",
                rationale=f"All expected tools called: {sorted(expected_set)}",
            )
        if expected_set & tools_called:
            return Feedback(
                name=self.name,
                value="partial",
                rationale=f"Called: {sorted(expected_set & tools_called)}. "
                f"Missing: {sorted(missing)}",
            )
        return Feedback(
            name=self.name,
            value="no",
            rationale=f"None of the expected tools called. "
            f"Expected: {sorted(expected_set)}. "
            f"Called: {sorted(tools_called) if tools_called else 'none'}",
        )
