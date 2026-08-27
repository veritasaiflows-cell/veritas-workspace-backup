#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "run_summary_refresh.py"


def load_module():
    spec = importlib.util.spec_from_file_location("run_summary_refresh", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def chain_with_reference_band_failure() -> dict:
    return {
        "status": "completed_with_recovery",
        "steps": [
            {
                "status": "failed",
                "script": "reference_band_note_sync.py",
                "exit_code": 1,
            }
        ],
        "recovery": {
            "triggered": True,
            "failed_step": {
                "script": "reference_band_note_sync.py",
                "exit_code": 1,
            },
        },
    }


def chain_with_data_quality_repair(classification: str, tickers: list[str]) -> dict:
    status = "completed_with_ticker_repairs" if classification == "ticker_scoped_repair" else "completed_with_systemic_data_quality"
    return {
        "status": status,
        "steps": [
            {
                "status": classification,
                "script": "validate_fundamental_metrics.py",
                "exit_code": 1,
                "data_quality_repair": {"tickers": tickers},
            }
        ],
        "recovery": {"triggered": False},
    }


def chain_with_dashboard_acceptance_failure() -> dict:
    return {
        "status": "completed_with_recovery",
        "steps": [
            {
                "status": "failed",
                "script": "test_dashboard_acceptance.py",
                "exit_code": 1,
            }
        ],
        "recovery": {
            "triggered": True,
            "failed_step": {
                "script": "test_dashboard_acceptance.py",
                "exit_code": 1,
            },
        },
    }


def test_repaired_reference_band_failure_is_not_actionable_blocker() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        module.WORKSPACE = root
        module.TMP = root / "tmp"
        module.REPAIRED_FAILED_STEP_ARTIFACTS = {
            "reference_band_note_sync.py": module.TMP / "reference-band-note-sync.json",
        }
        write_json(module.TMP / "reference-band-note-sync.json", {"status": "ok", "validation": {"status": "ok"}})
        outputs = {
            "premarket_snapshot": {
                "status": "missing",
                "path": "tmp/premarket-snapshot.json",
                "generated_at_utc": None,
            }
        }
        status, stop_line, blockers = module.determine_status(
            outputs,
            {"summary": {"all_passed": True}},
            {"summary": {"critical": 0, "warning": 0}, "warnings": []},
            chain_with_reference_band_failure(),
        )
        actions, next_action = module.operator_action_block(
            "morning",
            status,
            outputs,
            True,
            [],
            [],
            chain_with_reference_band_failure(),
            {"enabled": False},
            {"status": "ok"},
        )
        assert status == "blocked"
        assert stop_line is True
        assert not any("reference_band_note_sync.py" in blocker for blocker in blockers)
        assert any("premarket_snapshot" in blocker for blocker in blockers)
        assert not any("reference_band_note_sync.py" in action for action in actions)
        assert next_action == "Refresh the blocked morning outputs now marked stale or missing before using this window."


def test_unrepaired_reference_band_failure_stays_actionable_blocker() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        module.WORKSPACE = root
        module.TMP = root / "tmp"
        module.REPAIRED_FAILED_STEP_ARTIFACTS = {
            "reference_band_note_sync.py": module.TMP / "reference-band-note-sync.json",
        }
        outputs = {}
        status, stop_line, blockers = module.determine_status(
            outputs,
            {"summary": {"all_passed": True}},
            {"summary": {"critical": 0, "warning": 0}, "warnings": []},
            chain_with_reference_band_failure(),
        )
        assert status == "blocked"
        assert stop_line is True
        assert blockers == ["Finance refresh chain failed at reference_band_note_sync.py (exit code 1)"]


def test_repaired_dashboard_acceptance_failure_is_not_actionable_blocker() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        module.WORKSPACE = root
        module.TMP = root / "tmp"
        module.REPAIRED_FAILED_STEP_ARTIFACTS = {
            "test_dashboard_acceptance.py": module.TMP / "dashboard-acceptance-report.json",
        }
        write_json(module.TMP / "dashboard-acceptance-report.json", {"summary": {"all_passed": True}})
        status, stop_line, blockers = module.determine_status(
            {},
            {"summary": {"all_passed": True}},
            {"summary": {"critical": 0, "warning": 0}, "warnings": []},
            chain_with_dashboard_acceptance_failure(),
        )
        assert status == "ok"
        assert stop_line is False
        assert blockers == []

        write_json(module.TMP / "dashboard-acceptance-report.json", {"summary": {"all_passed": False}})
        status, stop_line, blockers = module.determine_status(
            {},
            {"summary": {"all_passed": False}},
            {"summary": {"critical": 0, "warning": 0}, "warnings": []},
            chain_with_dashboard_acceptance_failure(),
        )
        assert status == "blocked"
        assert stop_line is True
        assert blockers == ["Finance refresh chain failed at test_dashboard_acceptance.py (exit code 1)", "Dashboard acceptance did not fully pass"]


def test_ticker_scoped_data_quality_repair_warns_without_stop_line() -> None:
    module = load_module()
    chain = chain_with_data_quality_repair("ticker_scoped_repair", ["JPM"])
    status, stop_line, blockers = module.determine_status(
        {}, {"summary": {"all_passed": True}}, {"summary": {"critical": 0, "warning": 0}, "warnings": []}, chain,
    )
    actions, _ = module.operator_action_block("morning", status, {}, True, [], [], chain, {"enabled": False}, {"status": "ok"})
    assert status == "warning"
    assert stop_line is False
    assert blockers == []
    assert any("JPM" in action and "Source-open" in action for action in actions)


def test_systemic_data_quality_repair_stops_decision_use_but_not_execution_claims() -> None:
    module = load_module()
    chain = chain_with_data_quality_repair("systemic_data_quality", ["GS", "JPM"])
    status, stop_line, blockers = module.determine_status(
        {}, {"summary": {"all_passed": True}}, {"summary": {"critical": 0, "warning": 0}, "warnings": []}, chain,
    )
    actions, _ = module.operator_action_block("post-close", status, {}, True, [], [], chain, {"enabled": False}, {"status": "ok"})
    assert status == "blocked"
    assert stop_line is True
    assert blockers == ["Systemic data-quality repair required before fundamental decision use: GS, JPM"]
    assert any("consolidated same-day source-open repair queue" in action for action in actions)


def test_finalizer_self_observation_preserves_data_quality_status() -> None:
    module = load_module()
    for classification, expected in (
        ("ticker_scoped_repair", "completed_with_ticker_repairs"),
        ("systemic_data_quality", "completed_with_systemic_data_quality"),
    ):
        chain = {
            "status": "running",
            "steps": [
                {
                    "status": classification,
                    "script": "validate_fundamental_metrics.py",
                    "data_quality_repair": {"tickers": ["JPM"]},
                },
                {"status": "running", "script": "run_summary_refresh.py"},
                {"status": "pending", "script": "dashboard_run_summary_consumer.py"},
            ],
            "recovery": {"triggered": False},
        }
        status, _, normalized = module.normalized_chain_status(chain)
        assert status == expected
        assert normalized is True


def test_current_rollforward_capture_can_be_reused_within_the_same_window() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        module.WORKSPACE = root
        module.TMP = root / "tmp"
        module.ROLLFORWARD_GUARD_PATH = module.TMP / "earnings-rollforward-guard.json"
        capture = module.TMP / "official-ir-captures" / "etn-q2-2026.json"
        now = datetime.now(timezone.utc).replace(microsecond=0)
        attempt_started_at = now - timedelta(minutes=30)
        write_json(capture, {
            "status": "ok",
            "generated_at_utc": (now - timedelta(days=2)).isoformat().replace("+00:00", "Z"),
        })
        write_json(module.ROLLFORWARD_GUARD_PATH, {
            "generated_at_utc": now.isoformat().replace("+00:00", "Z"),
            "tickers": [{
                "ticker": "ETN",
                "status": "current",
                "current_validation_clean": True,
                "current_capture_artifact": "tmp/official-ir-captures/etn-q2-2026.json",
                "current_validation_artifact": "tmp/official-ir-captures/etn-q2-2026-validation.json",
            }],
        })

        reused_paths = module.rollforward_guard_current_output_paths(attempt_started_at)
        capture_path = module.normalized_workspace_path(capture)
        assert capture_path in reused_paths
        status, _, _, reused = module.required_output_status(
            capture,
            "json",
            attempt_started_at=attempt_started_at,
            incremental_reused=capture_path in reused_paths,
        )
        assert status == "ok"
        assert reused is True

        write_json(module.ROLLFORWARD_GUARD_PATH, {
            "generated_at_utc": (attempt_started_at - timedelta(seconds=1)).isoformat().replace("+00:00", "Z"),
            "tickers": [{
                "ticker": "ETN",
                "status": "current",
                "current_validation_clean": True,
                "current_capture_artifact": "tmp/official-ir-captures/etn-q2-2026.json",
            }],
        })
        assert capture_path not in module.rollforward_guard_current_output_paths(attempt_started_at)


def main() -> int:
    test_repaired_reference_band_failure_is_not_actionable_blocker()
    test_unrepaired_reference_band_failure_stays_actionable_blocker()
    test_repaired_dashboard_acceptance_failure_is_not_actionable_blocker()
    test_ticker_scoped_data_quality_repair_warns_without_stop_line()
    test_systemic_data_quality_repair_stops_decision_use_but_not_execution_claims()
    test_finalizer_self_observation_preserves_data_quality_status()
    test_current_rollforward_capture_can_be_reused_within_the_same_window()
    print("run_summary_refresh tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
