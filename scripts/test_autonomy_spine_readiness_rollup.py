#!/usr/bin/env python3
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import autonomy_spine_readiness_rollup as rollup


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def base(status: str = "ok") -> dict:
    return {"status": status, "validation": {"status": "ok", "errors": [], "warnings": []}, "generated_at_utc": "2026-06-13T06:00:00Z"}


def make_paths(root: Path) -> dict[str, Path]:
    return {key: root / f"{key}.json" for key in rollup.SOURCES}


def write_sources(paths: dict[str, Path], *, mature: bool = False) -> None:
    write_json(paths["promotion_contract"], base())
    outcome = base()
    outcome["summary"] = {
        "clean_shadow_decision_count": 20 if mature else 6,
        "required_clean_decisions": 20,
        "unique_clean_market_sessions": 5 if mature else 2,
        "required_clean_market_sessions": 5,
        "shadow_threshold_met": mature,
        "measurement_maturity_state": "threshold_met" if mature else "accruing",
    }
    write_json(paths["wf55_outcome_ledger"], outcome)
    command = base("ok" if mature else "runtime_blocked")
    command["summary"] = {"phase_a_runtime_gates_clean": mature}
    write_json(paths["wf87_command"], command)
    readiness = base()
    readiness["shadow_threshold"] = {
        "clean_shadow_decision_count": 20 if mature else 6,
        "required_clean_decisions": 20,
        "unique_clean_market_sessions": 5 if mature else 2,
        "required_clean_market_sessions": 5,
        "threshold_met": mature,
    }
    readiness["reconciliation_maturity"] = {"maturity_met": mature}
    write_json(paths["wf87_rollup"], readiness)
    cron = base()
    cron["summary"] = {
        "blocked_count": 0,
        "stale_count": 0,
        "urgent_attention_count": 0,
        "requires_attention_count": 0,
        "implementation_attention_count": 0,
        "missing_expected_artifact_contract_count": 0,
        "unregistered_enabled_count": 0,
    }
    write_json(paths["cron_freshness"], cron)
    advancement = base()
    advancement["summary"] = {"advanced_count": 4, "blocked_count": 0}
    write_json(paths["workflow_advancement"], advancement)
    write_json(paths["wf74_improvement_queue"], {"status": "ok", "summary": {"candidate_count": 2}, "validation": {"status": "ok"}})
    lane = base()
    lane["summary"] = {"active_lane_count": 0}
    write_json(paths["lane_register"], lane)


def test_rollup_stays_continue_accrual_until_thresholds_clear() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        paths = make_paths(Path(tmp))
        write_sources(paths, mature=False)
        payload = rollup.build_payload(paths)
        assert payload["status"] == "ok"
        assert payload["summary"]["final_state"] == "continue_accrual"
        assert "shadow_threshold_not_met" in payload["summary"]["blockers"]
        assert payload["authority_boundary"]["paper_or_live_execution_allowed"] is False


def test_rollup_ready_state_still_requires_owner_review() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        paths = make_paths(Path(tmp))
        write_sources(paths, mature=True)
        payload = rollup.build_payload(paths)
        assert payload["status"] == "ok"
        assert payload["summary"]["final_state"] == "ready_for_owner_review_of_paper_pilot"
        assert payload["summary"]["owner_approval_required"] is True
        assert payload["validation"]["status"] == "ok"


def test_rollup_accepts_wf87_mature_for_autonomy_field() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        paths = make_paths(Path(tmp))
        write_sources(paths, mature=True)
        readiness = json.loads(paths["wf87_rollup"].read_text(encoding="utf-8"))
        readiness["reconciliation_maturity"] = {"mature_for_autonomy": True}
        write_json(paths["wf87_rollup"], readiness)
        payload = rollup.build_payload(paths)
        assert payload["summary"]["reconciliation_mature"] is True
        assert "reconciliation_maturity_not_met" not in payload["summary"]["blockers"]


def test_rollup_ignores_workflow_advancement_self_reference_warning() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        paths = make_paths(Path(tmp))
        write_sources(paths, mature=True)
        advancement = json.loads(paths["workflow_advancement"].read_text(encoding="utf-8"))
        advancement["validation"] = {
            "status": "warning",
            "errors": [],
            "warnings": ["source_validation_not_ok:autonomy_spine_rollup:warning"],
        }
        write_json(paths["workflow_advancement"], advancement)
        payload = rollup.build_payload(paths)
        assert payload["validation"]["status"] == "ok"


def test_rollup_treats_monitor_only_stale_cron_as_clean() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        paths = make_paths(Path(tmp))
        write_sources(paths, mature=True)
        cron = json.loads(paths["cron_freshness"].read_text(encoding="utf-8"))
        cron["status"] = "warning"
        cron["summary"]["stale_count"] = 2
        cron["summary"]["monitor_only_or_stale_count"] = 2
        cron["summary"]["live_scheduler_last_run_exception_count"] = 2
        cron["validation"]["warnings"] = ["one_or_more_enabled_jobs_have_stale_artifacts"]
        write_json(paths["cron_freshness"], cron)

        payload = rollup.build_payload(paths)
        assert payload["summary"]["cron_clean"] is True
        assert "cron_cadence_not_clean" not in payload["summary"]["blockers"]


def test_rollup_blocks_hard_cron_attention() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        paths = make_paths(Path(tmp))
        write_sources(paths, mature=True)
        cron = json.loads(paths["cron_freshness"].read_text(encoding="utf-8"))
        cron["summary"]["requires_attention_count"] = 1
        write_json(paths["cron_freshness"], cron)

        payload = rollup.build_payload(paths)
        assert payload["summary"]["cron_clean"] is False
        assert "cron_cadence_not_clean" in payload["summary"]["blockers"]


if __name__ == "__main__":
    test_rollup_stays_continue_accrual_until_thresholds_clear()
    test_rollup_ready_state_still_requires_owner_review()
    test_rollup_accepts_wf87_mature_for_autonomy_field()
    test_rollup_ignores_workflow_advancement_self_reference_warning()
    test_rollup_treats_monitor_only_stale_cron_as_clean()
    test_rollup_blocks_hard_cron_attention()
    print("autonomy_spine_readiness_rollup_tests_passed")
