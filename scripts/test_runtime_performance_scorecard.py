#!/usr/bin/env python3
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))

import runtime_performance_scorecard as scorecard


def decorated_artifacts(*, extra: dict[str, tuple[dict, dict]] | None = None) -> dict:
    rows: dict[str, dict] = {
        "go_sql_latency_probe": {"path": "unused-latency.json", "status": "ok", "sqlite_driver": "inprocess"},
        "go_sql_inventory_helper": {"path": "unused-inventory.json", "status": "ok", "sqlite_driver": "inprocess"},
        "go_sql_inprocess_driver_pilot_gate": {
            "path": "unused-pilot.json",
            "status": "ok",
            "python_owner_default": True,
            "routing_changed_by_this_gate": False,
        },
    }
    payloads: dict[str, dict] = {
        key: {"status": "ok", "validation": {"status": "ok", "errors": [], "warnings": []}}
        for key in rows
    }
    for key, (row, payload) in (extra or {}).items():
        rows[key] = row
        payloads[key] = payload
    return scorecard.decorate_artifact_snapshot(rows, payload_overrides=payloads)


def artifact_only_args(history_out: Path) -> SimpleNamespace:
    return SimpleNamespace(
        artifact_only=True,
        quick=False,
        timed_quick=False,
        smoke=False,
        write=False,
        write_md=False,
        history_out=history_out,
        include_human_note_migration_checks=False,
    )


class ArtifactHealthTests(unittest.TestCase):
    def test_status_and_validation_are_both_fail_closed(self) -> None:
        self.assertEqual(scorecard.artifact_health({"status": "blocked", "validation": {"status": "ok"}})["artifact_health"], "blocked")
        self.assertEqual(
            scorecard.artifact_health({"status": "ok", "validation": {"status": "error", "errors": ["bad"]}})["artifact_health"],
            "blocked",
        )
        self.assertEqual(scorecard.artifact_health({"status": "warning", "validation": {"status": "ok"}})["artifact_health"], "warning")
        self.assertEqual(scorecard.artifact_health({"status": "unexpected_state"})["artifact_health"], "warning")

    def test_legacy_success_status_requires_success_semantics(self) -> None:
        self.assertEqual(scorecard.artifact_health({"status": "ready_for_source_open_cleanup"})["artifact_health"], "ok")
        self.assertEqual(scorecard.artifact_health({"status": "phase2_contract_ok"})["artifact_health"], "ok")
        self.assertEqual(
            scorecard.artifact_health({"status": "custom_success", "validation": {"status": "ok", "errors": []}})["artifact_health"],
            "ok",
        )

    def test_artifact_only_build_counts_blocked_and_warning_rows(self) -> None:
        artifacts = decorated_artifacts(
            extra={
                "bad_proof": (
                    {"path": "unused-bad.json", "status": "ok"},
                    {"status": "ok", "validation": {"status": "error", "errors": ["broken"]}},
                ),
                "warning_proof": (
                    {"path": "unused-warning.json", "status": "warning"},
                    {"status": "warning", "validation": {"status": "ok", "warnings": ["review"]}},
                ),
            }
        )
        with tempfile.TemporaryDirectory() as temp_dir, patch.object(scorecard, "artifact_snapshot", return_value=artifacts):
            report = scorecard.build_scorecard(artifact_only_args(Path(temp_dir) / "history.jsonl"))

        self.assertEqual(report["status"], "blocked")
        self.assertEqual(report["summary"]["checks_total"], 5)
        self.assertEqual(report["summary"]["ok_count"], 3)
        self.assertEqual(report["summary"]["warning_count"], 1)
        self.assertEqual(report["summary"]["blocked_count"], 1)
        self.assertEqual(report["summary"]["warning_artifacts"], ["warning_proof"])
        self.assertEqual(report["summary"]["blocked_artifacts"], ["bad_proof"])
        self.assertEqual(report["validation"]["status"], "ok")


class AuthorityBoundaryTests(unittest.TestCase):
    def test_live_plan_boundary_discloses_only_derived_db_mutation(self) -> None:
        boundary = scorecard.scorecard_authority_boundary(
            proof_orchestration=True,
            proof_artifact_writes=True,
            derived_db_mutation=True,
        )
        self.assertFalse(boundary["report_only"])
        self.assertTrue(boundary["proof_orchestration"])
        self.assertTrue(boundary["db_mutation"])
        self.assertTrue(boundary["derived_control_db_or_index_mutation"])
        self.assertEqual(
            boundary["derived_db_mutation_scope"],
            ["tmp/pm-program-state.sqlite", "tmp/veritas-artifact-index.sqlite"],
        )
        self.assertFalse(boundary["finance_canon_db_mutation"])
        self.assertFalse(boundary["canon_or_portfolio_mutation"])
        self.assertFalse(boundary["brokerage_or_account_mutation"])
        self.assertFalse(boundary["paper_or_live_execution_authority"])

    def test_validation_rejects_false_db_mutation_claim(self) -> None:
        artifacts = decorated_artifacts()
        boundary = scorecard.scorecard_authority_boundary(
            proof_orchestration=True,
            proof_artifact_writes=True,
            derived_db_mutation=False,
        )
        report = {
            "schema": scorecard.SCHEMA,
            "status": "ok",
            "summary": {
                "checks_total": 2,
                "ok_count": 2,
                "warning_count": 0,
                "blocked_count": 0,
                "artifact_only": False,
                "scorecard_write_requested": True,
            },
            "commands": [
                {"name": "python_pm_program_state", "status": "ok"},
                {"name": "python_artifact_index_incremental", "status": "ok"},
            ],
            "artifacts": artifacts,
            "authority_boundary": boundary,
            "human_note_migration_checks": {"executed": False},
            "regression_check": {"warnings": []},
        }
        validation = scorecard.validate(report)
        self.assertEqual(validation["status"], "error")
        self.assertIn("authority boundary mismatch: db_mutation", validation["errors"])
        self.assertIn("authority boundary mismatch: derived_control_db_or_index_mutation", validation["errors"])

    def test_bounded_live_build_derives_db_mutation_from_command_names(self) -> None:
        args = SimpleNamespace(
            artifact_only=False,
            quick=False,
            timed_quick=False,
            smoke=False,
            write=False,
            write_md=False,
            history_out=Path("unused-history.jsonl"),
            include_human_note_migration_checks=False,
        )
        plan = [
            ("python_pm_program_state", [sys.executable], scorecard.ROOT, 1),
            ("python_artifact_index_incremental", [sys.executable], scorecard.ROOT, 1),
        ]

        def fake_run(name: str, _command: list[str], **_kwargs: object) -> dict:
            return {"name": name, "status": "ok", "runtime": "python", "duration_ms": 1}

        with (
            patch.object(scorecard, "command_plan", return_value=plan),
            patch.object(scorecard, "run_command", side_effect=fake_run),
            patch.object(scorecard, "artifact_snapshot", return_value=decorated_artifacts()),
            patch.object(scorecard, "latest_history", return_value={}),
        ):
            report = scorecard.build_scorecard(args)

        self.assertEqual(report["status"], "ok")
        self.assertTrue(report["authority_boundary"]["db_mutation"])
        self.assertTrue(report["authority_boundary"]["derived_control_db_or_index_mutation"])
        self.assertFalse(report["authority_boundary"]["finance_canon_db_mutation"])
        self.assertEqual(report["validation"]["status"], "ok")

    def test_consumer_guard_keeps_inprocess_driver(self) -> None:
        args = SimpleNamespace(
            smoke=False,
            quick=True,
            sql_iterations=1,
            include_human_note_migration_checks=False,
        )
        plan = {name: command for name, command, _cwd, _timeout in scorecard.command_plan(args)}
        command = plan["go_sql_consumer_authority_guard"]
        self.assertIn("--driver", command)
        self.assertEqual(command[command.index("--driver") + 1], "inprocess")


class RetiredProofContractTests(unittest.TestCase):
    def test_smoke_and_full_plans_exclude_obsolete_wf78_and_capital_commands(self) -> None:
        full_args = SimpleNamespace(
            smoke=False,
            quick=True,
            sql_iterations=1,
            include_human_note_migration_checks=False,
        )
        smoke_args = SimpleNamespace(
            smoke=True,
            quick=True,
            sql_iterations=1,
            include_human_note_migration_checks=False,
        )
        full_plan = scorecard.command_plan(full_args)
        smoke_plan = scorecard.command_plan(smoke_args)
        command_text = "\n".join(
            part
            for plan in (full_plan, smoke_plan)
            for name, command, _cwd, _timeout in plan
            for part in [name, *command]
        )
        for token in (
            "wf78_sql_phase2_readiness.py",
            "go-wf78-sql-phase2-readiness-probe",
            "python_go_wf78_sql_phase2_readiness_parity.py",
            "capital_deployment_band_integrity_validator.py",
        ):
            self.assertNotIn(token, command_text)
        self.assertIn(
            "python_go_durable_output_parity_repeated_gate",
            {name for name, _command, _cwd, _timeout in full_plan},
        )

    def test_stale_retired_artifacts_are_absent_and_legacy_durable_gate_blocks(self) -> None:
        legacy_durable = {
            "schema": "veritas.python_go_durable_output_parity_repeated_gate.v1",
            "status": "ok",
            "summary": {
                "cases": 2,
                "case_names": ["finance_universe_validation", "retired_case"],
                "stable_case_fingerprints": 2,
            },
            "validation": {"status": "ok", "errors": [], "warnings": []},
        }

        def fake_load(path: Path) -> dict:
            if path.name == "python-go-durable-output-parity-repeated-gate.json":
                return legacy_durable
            return {"status": "ok", "validation": {"status": "ok", "errors": [], "warnings": []}}

        with patch.object(scorecard, "load_json_artifact", side_effect=fake_load), patch.object(
            scorecard, "pm_program_state", return_value={"status": "ok"}
        ):
            artifacts = scorecard.artifact_snapshot()

        for key in (
            "go_wf78_sql_phase2_readiness_probe",
            "python_go_wf78_sql_phase2_readiness_parity",
            "capital_deployment_band_integrity",
        ):
            self.assertNotIn(key, artifacts)
        durable = artifacts["python_go_durable_output_parity_repeated_gate"]
        self.assertEqual(durable["artifact_health"], "blocked")
        self.assertEqual(durable["case_contract_status"], "error")
        self.assertIn(
            "python_go_durable_output_parity_repeated_gate",
            scorecard.artifact_health_summary(artifacts)["blocked_artifacts"],
        )

    def test_exact_current_durable_case_contract_keeps_normal_health(self) -> None:
        payload = {
            "schema": scorecard.DURABLE_OUTPUT_SCHEMA,
            "status": "ok",
            "summary": {
                "cases": 1,
                "case_names": list(scorecard.DURABLE_OUTPUT_CASE_NAMES),
                "case_contract_status": "ok",
                "stable_case_fingerprints": 1,
            },
            "validation": {"status": "ok", "errors": [], "warnings": []},
        }
        self.assertEqual(scorecard.validated_durable_output_payload(payload), payload)
        self.assertEqual(scorecard.artifact_health(payload)["artifact_health"], "ok")


if __name__ == "__main__":
    unittest.main()
