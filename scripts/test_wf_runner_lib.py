#!/usr/bin/env python3
"""Focused tests for shared WF runner primitives."""
from __future__ import annotations

import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from wf_runner_lib import authority_true_paths, run_dependency_batches, run_step, topological_batches


def assert_true(value: bool, message: str) -> None:
    if not value:
        raise AssertionError(message)


def test_run_step_dry_run() -> None:
    row = run_step("sample", [sys.executable, "--version"], 30, dry_run=True)
    assert_true(row["ok"] is True, "dry-run step should be ok")
    assert_true(row["dry_run"] is True, "dry-run flag missing")
    assert_true("duration_ms" in row, "duration_ms missing")
    assert_true(row["timeout_seconds"] == 30, "timeout not preserved")


def test_topological_batches() -> None:
    batches, errors = topological_batches(
        ["a", "b", "c"],
        {"a": (), "b": ("a",), "c": ("a",)},
    )
    assert_true(not errors, f"unexpected dependency errors: {errors}")
    assert_true(batches == [["a"], ["b", "c"]], f"unexpected batches: {batches}")
    _batches, cycle_errors = topological_batches(["a", "b"], {"a": ("b",), "b": ("a",)})
    assert_true(cycle_errors and cycle_errors[0].startswith("dependency_cycle:"), "cycle not detected")


def test_run_dependency_batches_dry_run() -> None:
    steps = [
        ("a", [sys.executable, "--version"], 30),
        ("b", [sys.executable, "--version"], 30),
    ]
    rows, batches, errors = run_dependency_batches(
        steps,
        dependencies={"b": ("a",)},
        dry_run=True,
        max_workers=2,
    )
    assert_true(not errors, f"unexpected dependency errors: {errors}")
    assert_true(batches == [["a"], ["b"]], f"unexpected batches: {batches}")
    assert_true([row["name"] for row in rows] == ["a", "b"], "step order not preserved")


def test_authority_true_paths() -> None:
    packet = {
        "authority_boundary": {
            "capital_deployment_approved": False,
            "paper_or_live_execution_allowed": True,
        },
        "rows": [{"owner_approval_inferred": True}],
    }
    paths = authority_true_paths(packet)
    assert_true(
        paths == ["authority_boundary.paper_or_live_execution_allowed", "rows[0].owner_approval_inferred"],
        f"unexpected paths: {paths}",
    )
    override_paths = authority_true_paths(packet, false_keys={"paper_or_live_execution_allowed"})
    assert_true(override_paths == ["authority_boundary.paper_or_live_execution_allowed"], f"unexpected override paths: {override_paths}")


def main() -> int:
    test_run_step_dry_run()
    test_topological_batches()
    test_run_dependency_batches_dry_run()
    test_authority_true_paths()
    print("test_wf_runner_lib: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
