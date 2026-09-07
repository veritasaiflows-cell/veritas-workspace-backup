#!/usr/bin/env python3
"""Compatibility callers must fail closed after WF78 retirement."""
from __future__ import annotations

import wf_manifest as manifest


def test_generic_helpers_remain_available() -> None:
    first = manifest.StepDef("first", ("python", "noop.py"), 1, "test")
    second = manifest.StepDef("second", ("python", "noop.py"), 1, "test", ("first", "missing"))
    assert manifest.dependencies_for([first, second]) == {"first": (), "second": ("first",)}
    assert manifest.as_runner_tuples([first]) == [("first", ["python", "noop.py"], 1)]


def test_retired_phase_request_is_explicit() -> None:
    try:
        manifest.selected_phases(["daily_core"])
    except manifest.RetiredWorkflowError as exc:
        assert "WF78 orchestration is retired" in str(exc)
    else:
        raise AssertionError("retired phase selection did not fail closed")


def main() -> int:
    test_generic_helpers_remain_available()
    test_retired_phase_request_is_explicit()
    print("test_wf78_orchestrator_compat: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
