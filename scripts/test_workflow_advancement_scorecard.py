from __future__ import annotations

import json
import tempfile
from pathlib import Path

import workflow_advancement_scorecard as scorecard


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def base_payload(status: str = "ok") -> dict:
    return {
        "status": status,
        "generated_at_utc": "2026-06-13T06:50:00Z",
        "validation": {"status": "ok", "errors": [], "warnings": []},
    }


def make_paths(root: Path) -> dict[str, Path]:
    return {key: root / f"{key}.json" for key in scorecard.SOURCES}


def write_sources(paths: dict[str, Path], *, execution_drift: bool = False) -> None:
    cron = base_payload()
    cron["summary"] = {
        "enabled_job_count": 38,
        "fresh_count": 26,
        "blocked_count": 0,
        "stale_count": 0,
        "urgent_attention_count": 0,
        "unregistered_enabled_count": 0,
        "missing_expected_artifact_contract_count": 0,
    }
    write_json(paths["cron_freshness"], cron)

    command = base_payload("runtime_blocked")
    command["operator_action"] = "MAIN_HANDOFF_REQUIRED"
    command["summary"] = {
        "shadow_decisions": {"done": 6, "required": 20},
        "shadow_sessions": {"done": 2, "required": 5},
        "shadow_threshold_met": False,
    }
    write_json(paths["wf87_command"], command)

    audit = base_payload()
    audit["summary"] = {
        "execution_allowed_count": 1 if execution_drift else 0,
        "source_forbidden_true_count": 0,
    }
    write_json(paths["autonomous_card_audit"], audit)

    ledger = base_payload()
    ledger["summary"] = {
        "decision_event_count": 9,
        "clean_shadow_decision_count": 6,
        "required_clean_decisions": 20,
        "unique_clean_market_sessions": 2,
        "required_clean_market_sessions": 5,
        "measurement_maturity_state": "accruing",
    }
    write_json(paths["wf55_outcome_ledger"], ledger)

    spine = base_payload()
    spine["summary"] = {
        "final_state": "continue_accrual",
        "owner_approval_required": True,
        "blockers": ["shadow_threshold_not_met"],
        "next_safe_action": "Continue scheduled accrual and proof.",
    }
    write_json(paths["autonomy_spine_rollup"], spine)

    contract = base_payload()
    write_json(paths["autonomy_spine_contract"], contract)

    routes = base_payload()
    routes["routes"] = []
    write_json(paths["workflow_routes"], routes)


def test_scorecard_separates_cron_progress_from_wf87_blocker() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        paths = make_paths(Path(tmp))
        write_sources(paths)
        payload = scorecard.build_payload(paths)
        assert payload["status"] == "ok"
        assert payload["validation"]["status"] == "ok"
        by_wf = {signal["workflow_id"]: signal for signal in payload["signals"]}
        assert by_wf["CRON"]["signal"] == "advanced"
        assert "WF73" not in by_wf
        assert by_wf["WF87"]["signal"] == "blocked"
        assert by_wf["WF55"]["signal"] == "advanced"
        assert by_wf["AUTONOMY-SPINE"]["signal"] == "blocked"
        assert "shadow_threshold_not_met" in by_wf["WF87"]["blockers"]
        followups = {row["workflow_id"]: row for row in payload["workflow_blocker_followups"]}
        assert payload["workflow_blocker_followup_summary"]["followup_count"] == 2
        assert followups["WF87"]["route"] == "maturity_accrual"
        assert followups["WF87"]["owner"] == "WF87 maturity lane"
        assert followups["AUTONOMY-SPINE"]["route"] == "dependency_rollup"
        assert followups["AUTONOMY-SPINE"]["acceptance_validators"]
        assert followups["WF87"]["authority_boundary"]["paper_or_live_execution_allowed"] is False


def test_retired_layered_artifacts_cannot_restore_wf73_green() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        paths = make_paths(root)
        write_sources(paths)
        stale_green = base_payload()
        stale_green["summary"] = {
            "window_count": 2,
            "ok_window_count": 2,
            "mutating_step_count": 0,
            "cron_update_recommended": False,
        }
        write_json(root / "layered-finance-cron-pilot-runner.json", stale_green)
        write_json(root / "layered-finance-refresh-timing-probe.json", stale_green)

        payload = scorecard.build_payload(paths)
        source_names = {record["name"] for record in payload["source_records"]}
        workflow_ids = {signal["workflow_id"] for signal in payload["signals"]}
        assert "layered_pilot" not in scorecard.SOURCES
        assert "layered_timing" not in scorecard.SOURCES
        assert "layered_pilot" not in source_names
        assert "layered_timing" not in source_names
        assert "WF73" not in workflow_ids


def test_scorecard_keeps_stale_only_cron_warning_out_of_blockers() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        paths = make_paths(Path(tmp))
        write_sources(paths)
        cron = json.loads(paths["cron_freshness"].read_text(encoding="utf-8"))
        cron["status"] = "warning"
        cron["summary"]["stale_count"] = 1
        cron["summary"]["monitor_only_or_stale_count"] = 1
        cron["validation"]["warnings"] = ["one_or_more_enabled_jobs_have_stale_artifacts"]
        write_json(paths["cron_freshness"], cron)

        payload = scorecard.build_payload(paths)
        by_wf = {signal["workflow_id"]: signal for signal in payload["signals"]}
        assert by_wf["CRON"]["signal"] == "advanced"
        assert by_wf["CRON"]["blockers"] == []
        assert "stale_count=1" in by_wf["CRON"]["attention"]
        followups = {row["workflow_id"]: row for row in payload["workflow_blocker_followups"]}
        assert "CRON" not in followups


def test_scorecard_keeps_reconciled_scheduler_exceptions_out_of_blockers() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        paths = make_paths(Path(tmp))
        write_sources(paths)
        cron = json.loads(paths["cron_freshness"].read_text(encoding="utf-8"))
        cron["status"] = "warning"
        cron["summary"]["stale_count"] = 2
        cron["summary"]["monitor_only_or_stale_count"] = 2
        cron["summary"]["live_scheduler_last_run_exception_count"] = 2
        cron["validation"]["warnings"] = ["one_or_more_enabled_jobs_have_stale_artifacts"]
        write_json(paths["cron_freshness"], cron)

        payload = scorecard.build_payload(paths)
        by_wf = {signal["workflow_id"]: signal for signal in payload["signals"]}
        assert by_wf["CRON"]["signal"] == "advanced"
        assert by_wf["CRON"]["blockers"] == []
        assert "live_scheduler_last_run_exception_count=2" in by_wf["CRON"]["attention"]
        followups = {row["workflow_id"]: row for row in payload["workflow_blocker_followups"]}
        assert "CRON" not in followups


def test_scorecard_blocks_scheduler_exceptions_when_hard_cron_blocker_present() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        paths = make_paths(Path(tmp))
        write_sources(paths)
        cron = json.loads(paths["cron_freshness"].read_text(encoding="utf-8"))
        cron["summary"]["blocked_count"] = 1
        cron["summary"]["live_scheduler_last_run_exception_count"] = 1
        write_json(paths["cron_freshness"], cron)

        payload = scorecard.build_payload(paths)
        by_wf = {signal["workflow_id"]: signal for signal in payload["signals"]}
        assert by_wf["CRON"]["signal"] == "blocked"
        assert "blocked_count=1" in by_wf["CRON"]["blockers"]
        assert "live_scheduler_last_run_exception_count=1" in by_wf["CRON"]["blockers"]


def test_scorecard_blocks_execution_authority_drift() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        paths = make_paths(Path(tmp))
        write_sources(paths, execution_drift=True)
        payload = scorecard.build_payload(paths)
        assert payload["status"] == "blocked"
        assert "wf87_execution_authority_drift" in payload["validation"]["errors"]


if __name__ == "__main__":
    test_scorecard_separates_cron_progress_from_wf87_blocker()
    test_retired_layered_artifacts_cannot_restore_wf73_green()
    test_scorecard_keeps_stale_only_cron_warning_out_of_blockers()
    test_scorecard_keeps_reconciled_scheduler_exceptions_out_of_blockers()
    test_scorecard_blocks_scheduler_exceptions_when_hard_cron_blocker_present()
    test_scorecard_blocks_execution_authority_drift()
    print("workflow_advancement_scorecard tests passed")
