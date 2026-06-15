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

    pilot = base_payload()
    pilot["summary"] = {
        "window_count": 2,
        "ok_window_count": 2,
        "mutating_step_count": 0,
        "cron_update_recommended": False,
    }
    write_json(paths["layered_pilot"], pilot)

    timing = base_payload()
    timing["summary"] = {"window_count": 2, "cron_update_recommended": False}
    write_json(paths["layered_timing"], timing)

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
        assert by_wf["WF73"]["signal"] == "advanced"
        assert by_wf["WF87"]["signal"] == "blocked"
        assert by_wf["WF55"]["signal"] == "advanced"
        assert by_wf["AUTONOMY-SPINE"]["signal"] == "blocked"
        assert "shadow_threshold_not_met" in by_wf["WF87"]["blockers"]


def test_scorecard_blocks_execution_authority_drift() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        paths = make_paths(Path(tmp))
        write_sources(paths, execution_drift=True)
        payload = scorecard.build_payload(paths)
        assert payload["status"] == "blocked"
        assert "wf87_execution_authority_drift" in payload["validation"]["errors"]


if __name__ == "__main__":
    test_scorecard_separates_cron_progress_from_wf87_blocker()
    test_scorecard_blocks_execution_authority_drift()
    print("workflow_advancement_scorecard tests passed")
