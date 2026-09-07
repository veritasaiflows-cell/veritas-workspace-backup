from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "wf88_os2_control_packet.py"


def load_module():
    sys.path.insert(0, str(ROOT / "scripts"))
    spec = importlib.util.spec_from_file_location("wf88_os2_control_packet", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def seed_workspace(root: Path, module) -> None:
    module.ROOT = root
    module.TMP = root / "tmp"
    names = {
        "WF88_CLEANUP_PLAN": "wf88-retired-surface-cleanup-plan.json",
        "WF88_ROUTE_CONTRACTION": "wf88-route-contraction-packet.json",
        "WF88_DELETE_READINESS": "wf88-delete-readiness-packet.json",
        "RECOMMENDATION_LEDGER": "recommendation-outcome-ledger-current.json",
        "FINANCE_DIGEST": "finance-decision-performance-digest.json",
        "FINANCE_SQL_VALIDATION": "finance-sql-canon-access-validation.json",
        "ALERT_CONTROLLER": "alert-level-freshness-controller.json",
        "ALERT_DIGEST": "finance-alert-os-digest.json",
        "ALERTS_OS_PIVOT_VALIDATOR": "alerts-os-pivot-validator.json",
        "WF74_DOCKET": "wf74-decision-docket.json",
        "WF74_WF88_LOOP_TRACE": "wf74-wf88-loop-trace.json",
        "LONG_WORK_JOB_STATUS": "long-work-job-status-packet.json",
        "IMPROVEMENT_LEDGER": "improvement-ledger-current.json",
        "PM_CONTROL": "pm-control-packet.json",
        "CRON_CONTROL": "cron-control-packet.json",
        "OTEL_CONTROL": "otel-ops-control.json",
        "WF88_WIKI_SYNTHESIS": "wf88-wiki-synthesis-packet.json",
        "SKILL_WORKSHOP_BODY_GUARD": "skill-workshop-body-guard.json",
    }
    for attr, name in names.items():
        setattr(module, attr, module.TMP / name)
    module.QUOTE_SNAPSHOT = module.TMP / "intraday-alerts" / "quote-snapshot-proof.json"
    module.OUT = module.TMP / "wf88-os2-control-packet.json"
    module.MD_OUT = module.TMP / "wf88-os2-control-packet.md"

    now = module.utc_now()
    write_json(module.FINANCE_SQL_VALIDATION, {"status": "ok", "generated_at_utc": now, "validation": {"status": "ok"}})
    write_json(module.QUOTE_SNAPSHOT, {
        "status": "ok",
        "generated_at_utc": now,
        "symbols_observed": ["NVDA", "GOOG"],
        "freshness_summary": {"calendar_freshness_counts": {"current_last_completed_session": 2}},
    })
    write_json(module.ALERT_CONTROLLER, {
        "status": "ok",
        "generated_at_utc": now,
        "summary": {"ticker_count": 2},
        "validation": {"status": "ok"},
    })
    write_json(module.ALERT_DIGEST, {
        "status": "ok",
        "generated_at_utc": now,
        "summary": {"ticker_count": 2, "alert_state_counts": {"monitor_only": 2}, "freshness_review_tickers": []},
        "validation": {"status": "ok"},
    })
    write_json(module.ALERTS_OS_PIVOT_VALIDATOR, {"status": "ok", "generated_at_utc": now, "validation": {"status": "ok"}})
    write_json(module.WF88_CLEANUP_PLAN, {
        "status": "proposal_ready_no_apply_authority",
        "generated_at_utc": now,
        "summary": {"delete_allowed_now_count": 0, "archive_allowed_now_count": 0, "script_route_contraction_exact_file_count": 1},
    })
    write_json(module.WF88_ROUTE_CONTRACTION, {
        "status": "ok",
        "generated_at_utc": now,
        "summary": {"contracted_or_already_narrowed_count": 1, "script_deletion_ready_now_count": 0, "delete_allowed_now_count": 0, "archive_allowed_now_count": 0},
        "validation": {"status": "ok"},
    })
    write_json(module.WF88_DELETE_READINESS, {
        "status": "ok",
        "generated_at_utc": now,
        "summary": {"tmp_delete_ready_after_owner_approval_count": 0, "db_archive_ready_after_owner_approval_count": 0, "delete_or_archive_performed": False},
        "validation": {"status": "ok"},
    })
    write_json(module.RECOMMENDATION_LEDGER, {
        "status": "ok",
        "generated_at_utc": now,
        "durable_v2_ledger": {"later_outcome_graded_rows": 1, "grade_history": {"graded_ledger_event_count": 1}},
        "recommendation_tracking_summary": {"tracking_row_count": 1, "pending_owner_decision_rows": 1},
        "tracked_rows": [],
        "validation": {"status": "ok"},
    })
    write_json(module.FINANCE_DIGEST, {
        "status": "ok",
        "generated_at_utc": now,
        "recommendation_outcomes": {
            "recommendation_tracking_rows": 1,
            "outcome_grade_assigned_count": 1,
            "tracked_ticker_count": 1,
            "grade_history": {"assigned_grade_event_count": 1},
        },
        "performance_claim_status": {"predictive_skill_claim_allowed_now": False, "model_performance_claim_allowed_now": False},
    })
    write_json(module.WF74_DOCKET, {"status": "ok", "generated_at_utc": now, "summary": {}})
    write_json(module.WF74_WF88_LOOP_TRACE, {"status": "ok", "generated_at_utc": now, "summary": {}, "source_spine": {}, "validation": {"status": "ok"}})
    write_json(module.LONG_WORK_JOB_STATUS, {"status": "ok", "generated_at_utc": now, "summary": {"job_count": 0}, "validation": {"status": "ok"}})
    write_json(module.IMPROVEMENT_LEDGER, {"status": "ok", "generated_at_utc": now, "summary": {"latest_open_count": 0}})
    write_json(module.PM_CONTROL, {"status": "ok", "generated_at_utc": now, "summary": {"pm_readiness": {"readiness_band": "green", "blocked_lanes": 0}}})
    write_json(module.CRON_CONTROL, {"status": "ok", "generated_at_utc": now, "summary": {"blocked_count": 0}})
    write_json(module.OTEL_CONTROL, {"status": "ok", "generated_at_utc": now, "summary": {"event_count": 1}})
    write_json(module.WF88_WIKI_SYNTHESIS, {
        "status": "ok",
        "generated_at_utc": now,
        "summary": {},
        "recommendation_leak_guard": {"pass": True, "auto_apply_count": 0},
        "validation": {"status": "ok"},
    })
    write_json(module.SKILL_WORKSHOP_BODY_GUARD, {"status": "ok", "generated_at_utc": now, "summary": {"critical_count": 0, "live_error_count": 0}, "validation": {"status": "ok"}})


def test_control_packet_uses_active_alerts_os_inputs_only() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as raw:
        seed_workspace(Path(raw), module)
        packet = module.build_packet()
        assert packet["validation"]["status"] in {"ok", "warning"}
        inputs = packet["inputs"]
        assert {"guarded_sql_validation", "quote_snapshot", "alert_controller", "recommendation_digest", "alerts_os_pivot_validator"} <= set(inputs)
        for retired_key in ("wf67", "wf87", "wf78", "paper_guardrail", "finance_cache_frontdoor"):
            assert not any(retired_key in key.lower() for key in inputs)
        finance = packet["finance_alerts_os"]
        assert finance["guarded_sql_validation_status"] == "ok"
        assert finance["quote_symbol_count"] == 2
        assert finance["recommendation_ticker_count"] == 2
        ids = {row["id"] for row in packet["canonical_action_state"]}
        assert "finance-alerts-os-evidence-chain" in ids
        assert not any("wf67" in item or "wf87" in item for item in ids)


def test_control_packet_fails_closed_when_pivot_validator_fails() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as raw:
        seed_workspace(Path(raw), module)
        write_json(module.ALERTS_OS_PIVOT_VALIDATOR, {"status": "error", "generated_at_utc": module.utc_now(), "validation": {"status": "error"}})
        packet = module.build_packet()
        assert packet["validation"]["status"] == "blocked"
        assert "finance_alerts_os_pivot_validation_status_must_be_ok" in packet["validation"]["errors"]


def test_source_has_no_active_retired_finance_routes() -> None:
    source = SCRIPT.read_text(encoding="utf-8").lower()
    for marker in ("wf67", "wf87", "wf78", "finance-cache-frontdoor", "trade-grade", "paper-autonomy"):
        assert marker not in source


if __name__ == "__main__":
    test_control_packet_uses_active_alerts_os_inputs_only()
    test_control_packet_fails_closed_when_pivot_validator_fails()
    test_source_has_no_active_retired_finance_routes()
    print("wf88_os2_control_packet_tests_passed")
