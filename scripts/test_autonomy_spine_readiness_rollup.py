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
    cron["summary"] = {"blocked_count": 0, "stale_count": 0, "urgent_attention_count": 0, "missing_expected_artifact_contract_count": 0}
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


if __name__ == "__main__":
    test_rollup_stays_continue_accrual_until_thresholds_clear()
    test_rollup_ready_state_still_requires_owner_review()
    print("autonomy_spine_readiness_rollup_tests_passed")
