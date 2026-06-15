#!/usr/bin/env python3
"""Regression checks for the WF72 tool bloat reduction guard."""
from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "tool_bloat_reduction_guard.py"


def load_module():
    spec = importlib.util.spec_from_file_location("tool_bloat_reduction_guard", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


def main() -> int:
    m = load_module()
    sample = {
        "events_count": 3,
        "events": [
            {"severity": "medium", "truncated": True},
            {"severity": "medium", "truncated": False},
            {"severity": "low", "truncated": False},
        ],
        "summary_by_tool": {
            "read": {"count": 2, "total_output_chars": 20000, "max_output_chars": 16000},
            "exec": {"count": 1, "total_output_chars": 10000, "max_output_chars": 10000},
        },
    }
    baseline = {"counts": {"tool_result_events": 10, "medium_events": 4, "truncated_events": 2, "high_events": 0}}
    report = m.build_report(sample, baseline=baseline, target_reduction_pct=25)
    assert report["report_only"] is True
    assert report["mutations_performed"] is False
    assert report["counts"]["medium_events"] == 2
    assert report["counts"]["truncated_events"] == 1
    assert report["counts"]["high_events"] == 0
    assert report["top_output_tools"][0]["tool"] == "read"
    assert "bounded read" in report["top_output_tools"][0]["next_action"]
    assert report["comparison"]["metrics"]["medium_events"]["delta"] == -2
    assert report["target"]["target_met"] is True
    md = m.render_md(report)
    assert "Next action" in md
    assert "artifact path" in md
    print("tool_bloat_reduction_guard_tests_passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
