"""Deterministic answer correctness scorer.

Grades responses by question_type (binary, single_select, multiple_select,
substring_match, exact_match, ordered_list) without needing an LLM judge.
"""

from __future__ import annotations

import json
import re
from typing import Any

from mlflow.genai.scorers import Scorer


def _maybe_parse_json(value):
    """Deserialize JSON strings that were serialized by format_for_mlflow()."""
    if isinstance(value, str):
        try:
            return json.loads(value)
        except (json.JSONDecodeError, TypeError):
            pass
    return value


class AnswerCorrectness(Scorer):
    """Deterministic grading by question_type and expected_response.

    Grades binary (yes/no sentiment), single_select (option matching),
    multiple_select (partial credit), substring_match, exact_match, and
    ordered_list questions without needing an LLM judge.
    """

    name: str = "answer_correctness"
    description: str = (
        "Deterministic correctness check against the evaluation dataset's expected response. "
        "No LLM judge — uses programmatic grading matched to the question type: "
        "binary (yes/no sentiment detection), single_select (correct option mentioned), "
        "multiple_select (partial credit for each option found), "
        "substring_match (all required keywords present), "
        "exact_match (normalized string equality), "
        "ordered_list (items present in correct order). "
        "Score: 1.0 = fully correct, 0.0 = wrong, partial credit for multi-answer types."
    )

    _AFFIRMATIVE = [
        "yes", "yeah", "yep", "correct", "right", "true",
        "affirmative", "indeed", "absolutely", "certainly",
        "sure", "of course", "confirmed", "it is", "it does", "it can",
    ]

    _NEGATIVE = [
        "no", "nope", "incorrect", "wrong", "false", "negative",
        "not", "never", "none", "it is not", "it does not",
        "it cannot", "it can't", "it doesn't", "it isn't",
    ]

    def __call__(self, *, inputs, outputs, expectations, **kwargs):
        q_type = expectations.get("question_type", "")
        expected = _maybe_parse_json(expectations.get("expected_response"))
        options = _maybe_parse_json(expectations.get("options"))
        response = outputs if isinstance(outputs, str) else str(outputs)

        if not q_type:
            return 0.0

        score, _ = self._grade_response(q_type, expected, options, response)
        return score

    @staticmethod
    def _normalize(text: str) -> str:
        return " ".join(text.lower().split())

    @classmethod
    def _grade_binary(cls, expected: str, response: str) -> tuple[float, str]:
        expected = cls._normalize(expected)
        if expected not in ("yes", "no"):
            return 0.0, f"Invalid binary expected: {expected}"

        norm = cls._normalize(response)
        first_sentence = re.split(r'\. |\n', norm)[0]
        words = first_sentence.split()
        first = words[0].strip("*_,.!:") if words else ""

        # Use word boundary regex to avoid false positives like "no" in "known"
        aff = sum(1 for w in cls._AFFIRMATIVE if re.search(rf'\b{re.escape(w)}\b', first_sentence))
        neg = sum(1 for w in cls._NEGATIVE if re.search(rf'\b{re.escape(w)}\b', first_sentence))

        if first == "yes":
            aff += 3
        elif first == "no":
            neg += 3

        detected = "yes" if aff > neg else "no" if neg > aff else "ambiguous"
        passed = detected == expected
        return (1.0 if passed else 0.0), f"Expected '{expected}', detected '{detected}'"

    @classmethod
    def _grade_single_select(
        cls, expected: Any, options: Any, response: str,
    ) -> tuple[float, str]:
        norm_resp = cls._normalize(response)
        norm_expected = cls._normalize(str(expected))

        if norm_expected in norm_resp:
            return 1.0, f"Found '{expected}'"

        if isinstance(options, list):
            for opt in options:
                norm_opt = cls._normalize(str(opt))
                if norm_opt in norm_resp and norm_expected.endswith(norm_opt):
                    return 1.0, f"Found '{opt}' (matches '{expected}')"

        return 0.0, f"'{expected}' not found"

    @classmethod
    def _grade_multiple_select(cls, expected: Any, response: str) -> tuple[float, str]:
        items = expected if isinstance(expected, list) else [expected]
        if not items:
            return 1.0, "No expected answers"

        norm_resp = cls._normalize(response)
        expected_norms = {cls._normalize(str(e)) for e in items}
        found = {e for e in expected_norms if e in norm_resp}
        missed = expected_norms - found

        score = len(found) / len(expected_norms)
        parts = [f"{len(found)}/{len(expected_norms)}"]
        if missed:
            parts.append(f"missed: {sorted(missed)}")
        return round(score, 4), ", ".join(parts)

    @classmethod
    def _grade_substring_match(cls, expected: Any, response: str) -> tuple[float, str]:
        subs = [expected] if isinstance(expected, str) else list(expected)
        norm_resp = cls._normalize(response)

        matched = [s for s in subs if cls._normalize(s) in norm_resp]
        missing = [s for s in subs if cls._normalize(s) not in norm_resp]

        total = len(subs) or 1
        score = len(matched) / total
        parts = [f"{len(matched)}/{total} substrings"]
        if missing:
            parts.append(f"missing: {missing}")
        return round(score, 4), ", ".join(parts)

    @classmethod
    def _grade_exact_match(cls, expected: str, response: str) -> tuple[float, str]:
        ne, nr = cls._normalize(str(expected)), cls._normalize(response)
        if ne == nr:
            return 1.0, "Exact match"
        if ne in nr:
            return 0.8, f"'{expected}' found as substring"
        return 0.0, f"Expected '{expected}'"

    @classmethod
    def _grade_ordered_list(cls, expected: Any, response: str) -> tuple[float, str]:
        items = (
            [s.strip() for s in expected.split(",")]
            if isinstance(expected, str)
            else list(expected)
        )
        norm_resp = cls._normalize(response)

        positions, missing = [], []
        for item in items:
            pos = norm_resp.find(cls._normalize(item))
            (positions if pos >= 0 else missing).append(pos if pos >= 0 else item)

        in_order = all(a < b for a, b in zip(positions, positions[1:]))
        found = len(items) - len(missing)
        total = len(items) or 1

        if missing:
            score = found / total * 0.5
        elif not in_order:
            score = 0.5
        else:
            score = 1.0
        return round(score, 4), (
            f"{found}/{total} items" + (f", missing: {missing}" if missing else "")
        )

    @classmethod
    def _grade_response(
        cls, question_type: str, expected: Any, options: Any, response: str,
    ) -> tuple[float, str]:
        """Grade a response by question type. Returns (score, justification)."""
        q = question_type.lower()
        dispatch = {
            "binary": lambda: cls._grade_binary(str(expected), response),
            "single_select": lambda: cls._grade_single_select(expected, options, response),
            "multiple_select": lambda: cls._grade_multiple_select(expected, response),
            "substring_match": lambda: cls._grade_substring_match(expected, response),
            "exact_match": lambda: cls._grade_exact_match(str(expected), response),
            "ordered_list": lambda: cls._grade_ordered_list(expected, response),
            "free_form": lambda: (
                1.0,
                "Skipped: free-form questions are graded by the LLM correctness judge",
            ),
        }
        handler = dispatch.get(q)
        if handler is None:
            return 0.0, f"Unknown question_type: {q}"
        return handler()
