#!/usr/bin/env python3
"""Focused tests for cron_changed_input_prefilter.py."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import cron_changed_input_prefilter as prefilter


def test_changed_then_unchanged_then_changed() -> None:
    with tempfile.TemporaryDirectory() as raw:
        root = Path(raw)
        source = root / "source.txt"
        state = root / "state.json"
        source.write_text("alpha", encoding="utf-8")

        proof, new_state = prefilter.build_prefilter(
            job_name="Example Cron",
            sources=[source],
            state_path=state,
            update_state=True,
        )
        assert proof["status"] == "ok"
        assert proof["decision"] == "run_required"
        assert proof["state_updated"] is True
        state.write_text(json.dumps(new_state), encoding="utf-8")

        proof, _ = prefilter.build_prefilter(
            job_name="Example Cron",
            sources=[source],
            state_path=state,
            update_state=False,
        )
        assert proof["status"] == "ok"
        assert proof["decision"] == "skip_unchanged"

        source.write_text("beta", encoding="utf-8")
        proof, _ = prefilter.build_prefilter(
            job_name="Example Cron",
            sources=[source],
            state_path=state,
            update_state=False,
        )
        assert proof["status"] == "ok"
        assert proof["decision"] == "run_required"


def test_missing_source_warns_and_runs() -> None:
    with tempfile.TemporaryDirectory() as raw:
        root = Path(raw)
        proof, _ = prefilter.build_prefilter(
            job_name="Missing Source Cron",
            sources=[root / "missing.json"],
            state_path=root / "state.json",
            update_state=False,
        )
        assert proof["status"] == "warning"
        assert proof["decision"] == "run_required"
        assert proof["missing_source_count"] == 1


def main() -> int:
    test_changed_then_unchanged_then_changed()
    test_missing_source_warns_and_runs()
    print("cron_changed_input_prefilter_tests_passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
