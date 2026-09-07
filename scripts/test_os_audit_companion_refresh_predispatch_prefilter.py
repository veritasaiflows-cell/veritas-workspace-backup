#!/usr/bin/env python3
"""Focused tests for the OS audit companion changed-input gate."""

from __future__ import annotations

import json
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import os_audit_companion_refresh_predispatch_prefilter as gate

NOW = datetime(2026, 8, 27, 12, 0, tzinfo=timezone.utc)


def write_runner(path: Path, when: datetime = NOW, *, exit_code: int = 0) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "schema": gate.RUNNER_SCHEMA,
                "generated_at_utc": gate.common.utc_now(when),
                "status": "ok" if exit_code == 0 else "error",
                "failed_at_step": None if exit_code == 0 else 3,
                "results": [
                    {"index": index, "exit_code": exit_code if index == 3 else 0}
                    for index in range(1, gate.STEP_COUNT + 1)
                ],
            }
        ),
        encoding="utf-8",
    )


def test_changed_success_unchanged_and_changed_again() -> None:
    with tempfile.TemporaryDirectory() as raw:
        root = Path(raw)
        source = root / "source.txt"
        proof = root / "prefilter.json"
        runner = root / "runner.json"
        source.write_text("alpha", encoding="utf-8")

        first = gate.build_prefilter_report(
            root=root,
            now=NOW,
            proof_path=proof,
            runner_path=runner,
            source_paths=["source.txt"],
            required_source_paths=["source.txt"],
        )
        assert first["status"] == "run_required"
        write_runner(runner)
        completed = gate.finalize_runner_execution(
            first,
            {"ok": True, "returncode": 0},
            root=root,
            runner_path=runner,
            now=NOW,
            source_paths=["source.txt"],
            required_source_paths=["source.txt"],
        )
        gate.common.atomic_write_json(proof, completed, root=root)
        assert completed["status"] == "runner_executed"

        unchanged = gate.build_prefilter_report(
            root=root,
            now=NOW + timedelta(hours=24),
            proof_path=proof,
            runner_path=runner,
            source_paths=["source.txt"],
            required_source_paths=["source.txt"],
        )
        assert unchanged["status"] == "skipped_unchanged"
        assert unchanged["would_spawn_model_or_agent_turn"] is False
        assert unchanged["promotion_effect"]["eliminates_scheduled_agent_turn"] is True

        source.write_text("beta", encoding="utf-8")
        changed = gate.build_prefilter_report(
            root=root,
            now=NOW + timedelta(hours=24),
            proof_path=proof,
            runner_path=runner,
            source_paths=["source.txt"],
            required_source_paths=["source.txt"],
        )
        assert changed["status"] == "run_required"
        assert changed["prefilter"]["reason"] == "source_signature_changed"


def test_stale_runner_and_malformed_result_fail_closed() -> None:
    valid = {
        "schema": gate.RUNNER_SCHEMA,
        "status": "ok",
        "failed_at_step": None,
        "results": [{"index": index, "exit_code": 0} for index in range(1, gate.STEP_COUNT + 1)],
    }
    assert gate.runner_success(valid) is True
    malformed = json.loads(json.dumps(valid))
    malformed["results"][2]["exit_code"] = False
    assert gate.runner_success(malformed) is False

    with tempfile.TemporaryDirectory() as raw:
        root = Path(raw)
        source = root / "source.txt"
        proof = root / "prefilter.json"
        runner = root / "runner.json"
        source.write_text("alpha", encoding="utf-8")
        first = gate.build_prefilter_report(
            root=root,
            now=NOW,
            proof_path=proof,
            runner_path=runner,
            source_paths=["source.txt"],
            required_source_paths=["source.txt"],
        )
        write_runner(runner, NOW - timedelta(minutes=gate.MAX_REUSE_MINUTES + 1))
        first["status"] = "runner_executed"
        first["last_success_signature"] = first["input_signature"]["hash"]
        gate.common.atomic_write_json(proof, first, root=root)
        stale = gate.build_prefilter_report(
            root=root,
            now=NOW,
            proof_path=proof,
            runner_path=runner,
            source_paths=["source.txt"],
            required_source_paths=["source.txt"],
        )
        assert stale["status"] == "run_required"
        assert stale["prefilter"]["reason"] == "previous_runner_output_outside_reuse_window"


def test_runner_launch_is_exact_and_workspace_bounded() -> None:
    with tempfile.TemporaryDirectory() as raw:
        root = Path(raw)
        script = root / "scripts" / "os_audit_companion_refresh_runner.py"
        runner_out = root / "tmp" / "os-audit-companion-refresh-proof.json"
        script.parent.mkdir(parents=True)
        script.write_text("# fixture", encoding="utf-8")
        write_runner(runner_out)
        completed = subprocess_result = type("Completed", (), {"returncode": 0, "stdout": "ok", "stderr": ""})()
        with patch.object(gate.subprocess, "run", return_value=completed) as run:
            result = gate.run_existing_runner(root=root, runner_out=runner_out)
        assert result["ok"] is True
        command = run.call_args.args[0]
        assert command[-3:] == [str(script), "--write", "--validate"]
        assert subprocess_result.returncode == 0

        outside = root.parent / "outside-os-audit-proof.json"
        blocked = gate.run_existing_runner(root=root, runner_out=outside)
        assert blocked["ok"] is False
        assert blocked["error_code"] == "runner_output_path_outside_workspace"


def test_live_manifest_excludes_runner_outputs() -> None:
    normalized_inputs = {str(path).replace("\\", "/") for path in gate.STATIC_INPUT_SOURCES}
    assert normalized_inputs.isdisjoint(gate.RUNNER_OUTPUT_SOURCES)
    assert "tmp/token-usage-ledger-current.json" in normalized_inputs
    assert "state/workflows/WF84.json" in normalized_inputs
    assert "scripts/os_audit_companion_refresh_runner.py" in normalized_inputs


def main() -> int:
    test_changed_success_unchanged_and_changed_again()
    test_stale_runner_and_malformed_result_fail_closed()
    test_runner_launch_is_exact_and_workspace_bounded()
    test_live_manifest_excludes_runner_outputs()
    print("os_audit_companion_refresh_predispatch_prefilter_tests_passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
