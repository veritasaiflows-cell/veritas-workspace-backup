"""Deterministic graders for the six-family envelope.

Reuses the accepted strict-JSON primitives in scripts/arena_harness.py rather
than reimplementing parsing or value comparison. Scores four dimensions
separately: json_valid, factual, format and tools. A case never passes on a
repaired or narrated response.
"""

import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[5] / "scripts"
sys.path.insert(0, str(SCRIPTS))

from arena_harness import parse_strict_json_object, strict_value_equal  # noqa: E402

TOOL_CASES = {"T4-multihop-read-recovery"}


def grade(case_id, response_text, key, tool_trace=None, expected_trace=None,
          forbidden_reads=()):
    parsed, err = parse_strict_json_object(response_text)
    result = {
        "case": case_id,
        "json_valid": parsed is not None,
        "parse_error": err,
        "format": False,
        "factual": False,
        "tools": None,
        "tool_findings": [],
    }

    result["format"] = parsed is not None and response_text.strip() == response_text and err is None
    if parsed is not None:
        result["factual"] = strict_value_equal(parsed, key)

    if case_id in TOOL_CASES:
        findings = []
        trace = list(tool_trace or [])
        for bad in forbidden_reads:
            if bad in trace:
                findings.append(f"forbidden_read:{bad}")
        if expected_trace is not None and trace != list(expected_trace):
            findings.append("trace_mismatch")
        result["tools"] = not findings
        result["tool_findings"] = findings

    dims = [result["json_valid"], result["format"], result["factual"]]
    if result["tools"] is not None:
        dims.append(result["tools"])
    result["strict_pass"] = all(dims)
    return result


def grade_trajectory(case_id, turn_results):
    """A trajectory passes strictly only when every turn passes strictly."""
    return {
        "case": case_id,
        "turns": turn_results,
        "factual_all_turns": all(t["factual"] for t in turn_results),
        "format_all_turns": all(t["format"] for t in turn_results),
        "strict_pass": all(t["strict_pass"] for t in turn_results),
    }
