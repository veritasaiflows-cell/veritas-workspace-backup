#!/usr/bin/env python3
"""Focused regression tests for the status-card pre-dispatch gate."""

from __future__ import annotations

import json
import subprocess
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import status_card_freshness_predispatch_prefilter as gate


NOW = datetime(2026, 8, 27, 20, 0, tzinfo=timezone.utc)


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def successful_runner(path: Path, generated_at: datetime = NOW) -> None:
    write_json(
        path,
        {
            "schema": gate.RUNNER_SCHEMA,
            "status": "ok",
            "step_count": 1,
            "steps_executed": 1,
            "steps_passed": 1,
            "steps_failed": 0,
            "completed_at_utc": gate.utc_now(generated_at),
        },
    )


def test_changed_then_unchanged_then_changed() -> None:
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
        )
        assert first["status"] == "run_required"
        assert first["prefilter"]["reason"] == "missing_previous_success_signature"

        successful_runner(runner)
        first["status"] = "runner_executed"
        first["last_success_signature"] = first["input_signature"]["hash"]
        proof.write_text(json.dumps(first), encoding="utf-8")

        unchanged = gate.build_prefilter_report(
            root=root,
            now=NOW + timedelta(minutes=10),
            proof_path=proof,
            runner_path=runner,
            source_paths=["source.txt"],
        )
        assert unchanged["status"] == "skipped_unchanged"
        assert unchanged["would_run_existing_runner"] is False
        assert unchanged["would_spawn_model_or_agent_turn"] is False

        source.write_text("beta", encoding="utf-8")
        changed = gate.build_prefilter_report(
            root=root,
            now=NOW + timedelta(minutes=10),
            proof_path=proof,
            runner_path=runner,
            source_paths=["source.txt"],
        )
        assert changed["status"] == "run_required"
        assert changed["prefilter"]["reason"] == "source_signature_changed"


def test_stale_successful_output_cannot_be_reused() -> None:
    with tempfile.TemporaryDirectory() as raw:
        root = Path(raw)
        source = root / "source.txt"
        proof = root / "prefilter.json"
        runner = root / "runner.json"
        source.write_text("alpha", encoding="utf-8")
        report = gate.build_prefilter_report(
            root=root,
            now=NOW,
            proof_path=proof,
            runner_path=runner,
            source_paths=["source.txt"],
        )
        successful_runner(runner, NOW - timedelta(minutes=46))
        report["status"] = "runner_executed"
        report["last_success_signature"] = report["input_signature"]["hash"]
        proof.write_text(json.dumps(report), encoding="utf-8")

        stale = gate.build_prefilter_report(
            root=root,
            now=NOW,
            proof_path=proof,
            runner_path=runner,
            source_paths=["source.txt"],
        )
        assert stale["status"] == "run_required"
        assert stale["prefilter"]["reason"] == "previous_runner_output_outside_reuse_window"


def test_post_run_signature_is_authoritative() -> None:
    with tempfile.TemporaryDirectory() as raw:
        root = Path(raw)
        source = root / "source.txt"
        proof = root / "prefilter.json"
        runner = root / "runner.json"
        source.write_text("alpha", encoding="utf-8")
        report = gate.build_prefilter_report(
            root=root,
            now=NOW,
            proof_path=proof,
            runner_path=runner,
            source_paths=["source.txt"],
        )
        successful_runner(runner)
        report["status"] = "runner_executed"
        report["input_signature"]["hash"] = "pre-run-signature"
        report["last_success_signature"] = gate.build_input_signature(
            root=root,
            now=NOW,
            source_paths=["source.txt"],
        )["hash"]
        proof.write_text(json.dumps(report), encoding="utf-8")

        reused = gate.build_prefilter_report(
            root=root,
            now=NOW + timedelta(minutes=10),
            proof_path=proof,
            runner_path=runner,
            source_paths=["source.txt"],
        )
        assert reused["status"] == "skipped_unchanged"


def test_malformed_runner_output_cannot_be_reused() -> None:
    with tempfile.TemporaryDirectory() as raw:
        root = Path(raw)
        source = root / "source.txt"
        proof = root / "prefilter.json"
        runner = root / "runner.json"
        source.write_text("alpha", encoding="utf-8")
        report = gate.build_prefilter_report(
            root=root,
            now=NOW,
            proof_path=proof,
            runner_path=runner,
            source_paths=["source.txt"],
        )
        write_json(runner, {"schema": gate.RUNNER_SCHEMA, "status": "ok", "steps_passed": "not-a-number"})
        report["status"] = "runner_executed"
        report["last_success_signature"] = report["input_signature"]["hash"]
        proof.write_text(json.dumps(report), encoding="utf-8")

        malformed = gate.build_prefilter_report(
            root=root,
            now=NOW,
            proof_path=proof,
            runner_path=runner,
            source_paths=["source.txt"],
        )
        assert malformed["status"] == "run_required"
        assert malformed["prefilter"]["reason"] == "previous_runner_output_not_successful"


def test_required_paths_are_added_to_the_manifest() -> None:
    with tempfile.TemporaryDirectory() as raw:
        root = Path(raw)
        signature = gate.build_input_signature(
            root=root,
            now=NOW,
            source_paths=["observed.txt"],
            required_source_paths=["required-but-omitted.txt"],
        )
        required = next(
            record
            for record in signature["sources"]
            if record["path"] == "required-but-omitted.txt"
        )
        assert required["required"] is True
        assert required["exists"] is False
        assert signature["required_source_problem_count"] == 1


def test_required_unsupported_and_unparseable_inputs_force_run() -> None:
    with tempfile.TemporaryDirectory() as raw:
        root = Path(raw)
        malformed = root / "malformed.json"
        unsupported = root / "unsupported"
        malformed.write_text("{not-json", encoding="utf-8")
        unsupported.mkdir()
        report = gate.build_prefilter_report(
            root=root,
            now=NOW,
            proof_path=root / "prefilter.json",
            runner_path=root / "runner.json",
            source_paths=["malformed.json", "unsupported"],
            required_source_paths=["malformed.json", "unsupported"],
        )
        assert report["status"] == "run_required"
        assert report["input_signature"]["required_source_problem_count"] == 2
        assert report["prefilter"]["force_run_warnings"] == [
            "required_source_unparseable_force_run_required",
            "required_source_unsupported_force_run_required",
        ]


def test_runner_success_requires_exact_step_counters() -> None:
    payload = {
        "schema": gate.RUNNER_SCHEMA,
        "status": "ok",
        "step_count": 1,
        "steps_executed": 1,
        "steps_passed": 1,
        "steps_failed": 0,
    }
    assert gate.runner_success(payload) is True
    for field, value in (
        ("steps_executed", 0),
        ("steps_passed", 1.9),
        ("step_count", "1"),
        ("steps_failed", False),
    ):
        malformed = dict(payload)
        malformed[field] = value
        assert gate.runner_success(malformed) is False


def test_optional_missing_input_is_visible_but_does_not_repeat_run() -> None:
    with tempfile.TemporaryDirectory() as raw:
        root = Path(raw)
        proof = root / "prefilter.json"
        runner = root / "runner.json"
        source_paths = ["optional-packet.json"]

        first = gate.build_prefilter_report(
            root=root,
            now=NOW,
            proof_path=proof,
            runner_path=runner,
            source_paths=source_paths,
        )
        assert first["input_signature"]["optional_source_problem_count"] >= 1
        optional_packet = next(
            record
            for record in first["input_signature"]["sources"]
            if record["path"] == "optional-packet.json"
        )
        assert optional_packet["required"] is False
        assert optional_packet["exists"] is False
        successful_runner(runner)
        first["status"] = "runner_executed"
        first["last_success_signature"] = first["input_signature"]["hash"]
        proof.write_text(json.dumps(first), encoding="utf-8")

        unchanged = gate.build_prefilter_report(
            root=root,
            now=NOW + timedelta(minutes=10),
            proof_path=proof,
            runner_path=runner,
            source_paths=source_paths,
        )
        assert unchanged["status"] == "skipped_unchanged"
        assert "optional_source_missing_warning_reuse_allowed" in unchanged["validation"]["warnings"]
        assert not unchanged["prefilter"]["force_run_warnings"]


def test_required_missing_input_still_forces_repeated_run() -> None:
    with tempfile.TemporaryDirectory() as raw:
        root = Path(raw)
        proof = root / "prefilter.json"
        runner = root / "runner.json"
        source_paths = ["required-input.json"]

        first = gate.build_prefilter_report(
            root=root,
            now=NOW,
            proof_path=proof,
            runner_path=runner,
            source_paths=source_paths,
            required_source_paths=source_paths,
        )
        successful_runner(runner)
        first["status"] = "runner_executed"
        first["last_success_signature"] = first["input_signature"]["hash"]
        proof.write_text(json.dumps(first), encoding="utf-8")

        repeated = gate.build_prefilter_report(
            root=root,
            now=NOW + timedelta(minutes=10),
            proof_path=proof,
            runner_path=runner,
            source_paths=source_paths,
            required_source_paths=source_paths,
        )
        assert repeated["status"] == "run_required"
        assert repeated["prefilter"]["reason"] == "required_source_missing_force_run_required"
        assert repeated["prefilter"]["force_run_warnings"] == [
            "required_source_missing_force_run_required"
        ]


def test_retired_tools_absence_does_not_block_valid_manifest() -> None:
    assert "TOOLS.md" not in gate.STATIC_INPUT_SOURCES
    assert "TOOLS.md" not in gate.REQUIRED_INPUT_SOURCES
    with tempfile.TemporaryDirectory() as raw:
        root = Path(raw)
        proof = root / "prefilter.json"
        runner = root / "runner.json"
        source_paths = ["AGENTS.md"]
        (root / "AGENTS.md").write_text("active control owner", encoding="utf-8")

        first = gate.build_prefilter_report(
            root=root,
            now=NOW,
            proof_path=proof,
            runner_path=runner,
            source_paths=source_paths,
            required_source_paths=source_paths,
        )
        assert first["input_signature"]["required_source_problem_count"] == 0
        assert not any(record["path"] == "TOOLS.md" for record in first["input_signature"]["sources"])
        successful_runner(runner)
        first["status"] = "runner_executed"
        first["last_success_signature"] = first["input_signature"]["hash"]
        proof.write_text(json.dumps(first), encoding="utf-8")

        unchanged = gate.build_prefilter_report(
            root=root,
            now=NOW + timedelta(minutes=10),
            proof_path=proof,
            runner_path=runner,
            source_paths=source_paths,
            required_source_paths=source_paths,
        )
        assert unchanged["status"] == "skipped_unchanged"
        assert not unchanged["prefilter"]["force_run_warnings"]


def test_missing_agents_md_still_forces_repeated_run() -> None:
    with tempfile.TemporaryDirectory() as raw:
        root = Path(raw)
        proof = root / "prefilter.json"
        runner = root / "runner.json"
        source_paths = ["AGENTS.md"]

        first = gate.build_prefilter_report(
            root=root,
            now=NOW,
            proof_path=proof,
            runner_path=runner,
            source_paths=source_paths,
            required_source_paths=source_paths,
        )
        successful_runner(runner)
        first["status"] = "runner_executed"
        first["last_success_signature"] = first["input_signature"]["hash"]
        proof.write_text(json.dumps(first), encoding="utf-8")

        repeated = gate.build_prefilter_report(
            root=root,
            now=NOW + timedelta(minutes=10),
            proof_path=proof,
            runner_path=runner,
            source_paths=source_paths,
            required_source_paths=source_paths,
        )
        assert repeated["status"] == "run_required"
        assert repeated["prefilter"]["reason"] == "required_source_missing_force_run_required"
        assert repeated["prefilter"]["force_run_warnings"] == [
            "required_source_missing_force_run_required"
        ]


def test_missing_input_forces_run_and_authority_is_review_only() -> None:
    with tempfile.TemporaryDirectory() as raw:
        root = Path(raw)
        report = gate.build_prefilter_report(
            root=root,
            now=NOW,
            proof_path=root / "prefilter.json",
            runner_path=root / "runner.json",
            source_paths=["missing.txt"],
            required_source_paths=["missing.txt"],
        )
        assert report["status"] == "run_required"
        assert "required_source_missing_force_run_required" in report["validation"]["warnings"]
        assert report["prefilter"]["force_run_warnings"] == [
            "required_source_missing_force_run_required"
        ]
        assert report["authority_boundary"]["review_only"] is True
        assert report["authority_boundary"]["prefilter_is_review_proof_surface"] is True
        assert report["authority_boundary"]["prefilter_proof_write_allowed"] is True
        assert report["authority_boundary"]["status_card_review_artifact_writes_allowed"] is True
        assert report["authority_boundary"]["control_or_authority_mutation_allowed"] is False
        assert report["authority_boundary"]["cron_schedule_mutation_allowed"] is False
        assert report["authority_boundary"]["cron_payload_mutation_allowed"] is False
        assert report["authority_boundary"]["model_route_mutation_allowed"] is False
        assert report["authority_boundary"]["runtime_config_mutation_allowed"] is False
        assert report["authority_boundary"]["finance_canon_or_portfolio_mutation_allowed"] is False
        assert report["authority_boundary"]["paper_or_live_execution_allowed"] is False
        assert report["authority_boundary"]["brokerage_or_account_action_allowed"] is False
        assert report["authority_boundary"]["capital_deployment_allowed"] is False
        assert report["authority_boundary"]["external_delivery_allowed"] is False
        assert report["authority_boundary"]["owner_approval_inferred"] is False
        assert report["execution_semantics"]["prefilter_writes_its_own_review_proof"] is True
        assert report["execution_semantics"]["execute_mode_writes_existing_review_packets"] is True
        assert report["execution_semantics"]["control_or_authority_state_mutation"] is False
        assert report["promotion_effect"]["current_live_payload_kind"] == "command"
        assert report["promotion_effect"]["eliminates_scheduled_agent_turn"] is True
        assert report["promotion_effect"]["requires_separate_cron_payload_promotion"] is False
        assert report["execution_semantics"]["scheduled_agent_turn_occurs_if_embedded_in_current_agent_turn"] is False


def test_custom_runner_output_is_forwarded_and_launch_failures_are_structured() -> None:
    with tempfile.TemporaryDirectory() as raw:
        root = Path(raw)
        custom_runner = root / "nested" / "custom-runner.json"
        runner_script = root / "scripts" / "status_card_packet.py"
        runner_script.parent.mkdir(parents=True, exist_ok=True)
        runner_script.write_text(
            "import argparse, json\n"
            "from datetime import datetime, timezone\n"
            "from pathlib import Path\n"
            "parser = argparse.ArgumentParser()\n"
            "parser.add_argument('--write', action='store_true')\n"
            "parser.add_argument('--validate', action='store_true')\n"
            "args = parser.parse_args()\n"
            "raise SystemExit(0)\n",
            encoding="utf-8",
        )
        actual = gate.run_existing_runner(root=root, runner_out=custom_runner)
        assert actual["ok"] is True
        assert custom_runner.exists()

        completed = subprocess.CompletedProcess([], 0, stdout="ok", stderr="")
        with patch.object(gate.subprocess, "run", return_value=completed) as run:
            result = gate.run_existing_runner(root=root, runner_out=custom_runner)
        command = run.call_args.args[0]
        assert result["ok"] is True
        assert command[1].endswith("status_card_packet.py")

        with patch.object(gate.subprocess, "run", side_effect=OSError("cannot launch")):
            failed = gate.run_existing_runner(root=root, runner_out=custom_runner)
        assert failed["ok"] is False
        assert failed["error_code"] == "runner_launch_failed"
        assert failed["error_type"] == "OSError"

        with patch.object(
            gate.subprocess,
            "run",
            return_value=subprocess.CompletedProcess([], 3, stdout="", stderr="failed"),
        ):
            nonzero = gate.run_existing_runner(root=root, runner_out=custom_runner)
        assert nonzero["ok"] is False
        assert nonzero["returncode"] == 3

        with patch.object(
            gate.subprocess,
            "run",
            side_effect=subprocess.TimeoutExpired([], 2, output="partial", stderr="timeout"),
        ):
            timed_out = gate.run_existing_runner(root=root, runner_out=custom_runner)
        assert timed_out["ok"] is False
        assert timed_out["timeout_seconds"] == 180

        outside = root.parent / "status-card-proof-outside-workspace.json"
        try:
            gate.atomic_write_json(outside, {"unsafe": True}, root=root)
        except ValueError as exc:
            assert "inside the workspace" in str(exc)
        else:
            raise AssertionError("outside proof path was accepted")
        assert not outside.exists()


def test_finalize_records_post_run_signature_and_rejects_invalid_output() -> None:
    with tempfile.TemporaryDirectory() as raw:
        root = Path(raw)
        source = root / "source.txt"
        proof = root / "prefilter.json"
        runner = root / "runner.json"
        source.write_text("alpha", encoding="utf-8")
        report = gate.build_prefilter_report(
            root=root,
            now=NOW,
            proof_path=proof,
            runner_path=runner,
            source_paths=["source.txt"],
            required_source_paths=[],
        )
        successful_runner(runner)
        finalized = gate.finalize_runner_execution(
            report,
            {"ok": True, "returncode": 0},
            root=root,
            runner_path=runner,
            now=NOW,
            source_paths=["source.txt"],
            required_source_paths=[],
        )
        assert finalized["status"] == "runner_executed"
        assert finalized["post_run_input_signature"]["hash"] == finalized["last_success_signature"]
        assert finalized["runner_output"]["success"] is True

        write_json(runner, {"schema": gate.RUNNER_SCHEMA, "status": "ok"})
        invalid = gate.finalize_runner_execution(
            report,
            {"ok": True, "returncode": 0},
            root=root,
            runner_path=runner,
            now=NOW,
            source_paths=["source.txt"],
            required_source_paths=[],
        )
        assert invalid["status"] == "blocked"
        assert invalid["action"] == "runner_output_invalid"
        assert invalid["validation"]["errors"] == [
            "status_card_alerts_os_refresh_output_invalid"
        ]

        for timestamp in (
            gate.utc_now(NOW - timedelta(minutes=46)),
            gate.utc_now(NOW + timedelta(minutes=1)),
            "not-a-timestamp",
        ):
            timestamp_report = gate.build_prefilter_report(
                root=root,
                now=NOW,
                proof_path=proof,
                runner_path=runner,
                source_paths=["source.txt"],
                required_source_paths=[],
            )
            write_json(
                runner,
                {
                    "schema": gate.RUNNER_SCHEMA,
                    "status": "ok",
                        "step_count": 1,
                        "steps_executed": 1,
                        "steps_passed": 1,
                    "steps_failed": 0,
                    "completed_at_utc": timestamp,
                },
            )
            not_reusable = gate.finalize_runner_execution(
                timestamp_report,
                {"ok": True, "returncode": 0},
                root=root,
                runner_path=runner,
                now=NOW,
                source_paths=["source.txt"],
                required_source_paths=[],
            )
            assert not_reusable["status"] == "blocked"
            assert not_reusable["action"] == "runner_output_not_reusable"
            assert not_reusable["validation"]["errors"] == [
                "status_card_alerts_os_refresh_output_not_reusable"
            ]


def test_static_manifest_uses_active_alerts_os_proofs_only() -> None:
    sources = set(gate.STATIC_INPUT_SOURCES)
    expected = {
        "tmp/finance-sql-canon-access-validation.json",
        "tmp/intraday-alerts/quote-snapshot-proof.json",
        "tmp/alert-level-freshness-controller.json",
        "tmp/finance-alert-os-digest.json",
        "tmp/alerts-os-pivot-validator.json",
    }
    assert expected <= sources
    for source in sources:
        lowered = source.lower()
        assert "wf67" not in lowered
        assert "wf78" not in lowered
        assert "paper-autotrader" not in lowered
        assert "paper-execution" not in lowered


def main() -> int:
    test_changed_then_unchanged_then_changed()
    test_stale_successful_output_cannot_be_reused()
    test_post_run_signature_is_authoritative()
    test_malformed_runner_output_cannot_be_reused()
    test_required_paths_are_added_to_the_manifest()
    test_required_unsupported_and_unparseable_inputs_force_run()
    test_runner_success_requires_exact_step_counters()
    test_optional_missing_input_is_visible_but_does_not_repeat_run()
    test_required_missing_input_still_forces_repeated_run()
    test_retired_tools_absence_does_not_block_valid_manifest()
    test_missing_agents_md_still_forces_repeated_run()
    test_missing_input_forces_run_and_authority_is_review_only()
    test_custom_runner_output_is_forwarded_and_launch_failures_are_structured()
    test_finalize_records_post_run_signature_and_rejects_invalid_output()
    test_static_manifest_uses_active_alerts_os_proofs_only()
    print("status_card_freshness_predispatch_prefilter_tests_passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
