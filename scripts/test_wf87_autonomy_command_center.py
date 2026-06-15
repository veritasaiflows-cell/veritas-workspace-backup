#!/usr/bin/env python3
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import wf87_autonomy_command_center as center


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def base_payload(status: str = "ok") -> dict:
    return {
        "status": status,
        "generated_at_utc": "2026-06-12T05:00:00Z",
        "authority_boundary": {
            "paper_or_live_execution_allowed": False,
            "owner_approval_inferred": False,
            "live_endpoint_allowed": False,
            "money_movement_allowed": False,
        },
        "validation": {"status": "ok", "errors": [], "warnings": []},
    }


def make_paths(root: Path) -> dict[str, Path]:
    return {key: root / f"{key}.json" for key in center.DEFAULT_SOURCES}


def write_minimal_sources(paths: dict[str, Path], *, daylight_blocked: bool = False, authority_drift: bool = False) -> None:
    rollup = base_payload("phase_a_hardening_implemented_runtime_blocked")
    rollup["phase_readiness"] = {
        "phase_a_hardening_components_installed": True,
        "phase_a_runtime_gates_clean": False,
        "phase_a_hardening_gates_clean": False,
        "phase_c_autonomous_paper_buy_ready": False,
        "phase_e_live_ready": False,
    }
    rollup["shadow_threshold"] = {
        "clean_shadow_decision_count": 6,
        "required_clean_decisions": 20,
        "unique_clean_market_sessions": 2,
        "required_clean_market_sessions": 5,
        "threshold_met": False,
    }
    rollup["assisted_paper_cadence"] = {
        "status": "attempted_cadence_satisfied_maturity_blocked",
        "current_week_assisted_attempt_count": 1,
        "current_week_assisted_terminal_attempt_count": 1,
        "current_week_assisted_maturity_rep_count": 0,
        "all_time_assisted_filled_round_trip_count": 0,
    }
    rollup["blocker_taxonomy"] = {
        "maturity_blockers": ["shadow_threshold_not_met", "reconciliation_maturity_not_met"],
        "fail_closed_at_rest": ["approval_freshness_ttl_status_not_allowed:blocked"],
        "runtime_blockers": [],
        "counts": {
            "maturity_blocker_count": 2,
            "fail_closed_at_rest_count": 1,
            "runtime_blocker_count": 0,
            "binding_blocker_count": 2,
        },
    }
    if authority_drift:
        rollup["authority_boundary"]["paper_or_live_execution_allowed"] = True
    write_json(paths["v2_rollup"], rollup)

    runner = base_payload("ok")
    runner["operator_action"] = "MAIN_HANDOFF_REQUIRED"
    runner["summary"] = {
        "clean_shadow_decision_count": 6,
        "required_clean_decisions": 20,
        "unique_clean_market_sessions": 2,
        "required_clean_market_sessions": 5,
    }
    write_json(paths["wf86_daily_runner"], runner)

    assisted_cards = base_payload("draft_blocked_before_approval")
    assisted_cards["summary"] = {
        "card_count": 1,
        "ticker": "VRT",
        "notional_usd": 1500.0,
        "limit_price": 297.88,
        "assisted_review_blockers": ["fresh_execution_quote_needed"],
        "execution_ready": False,
    }
    assisted_cards["cards"] = [
        {
            "ticker": "VRT",
            "owner_approval_status": "pending_exact_randall_approval",
            "execution_blockers": ["submit_channel_not_allowed_from_assisted_builder"],
        }
    ]
    write_json(paths["assisted_order_cards"], assisted_cards)

    cadence = base_payload("attempted_cadence_satisfied_maturity_blocked")
    cadence["assisted_maturity_reps"] = {
        "current_week_wf86_assisted_attempt_count": 1,
        "current_week_assisted_terminal_attempt_count": 1,
        "current_week_assisted_maturity_rep_count": 0,
        "all_time_assisted_filled_round_trip_count": 0,
    }
    write_json(paths["assisted_cadence"], cadence)

    outcomes = base_payload("pending_regular_session_followup")
    outcomes["summary"] = {
        "scoreable_decision_count": 0,
        "pending_regular_session_followup_count": 4,
        "stale_pending_followup_count": 0,
        "decision_quality_claim_allowed_now": False,
        "model_performance_claim_allowed_now": False,
    }
    write_json(paths["shadow_outcomes"], outcomes)

    probe = base_payload("daylight_gates_blocked" if daylight_blocked else "outside_market_hours_sample_only")
    probe["operator_action"] = "MAIN_HANDOFF_REQUIRED" if daylight_blocked else "NO_REPLY"
    probe["summary"] = {
        "daylight_sample": daylight_blocked,
        "daylight_gate_result": "blocked" if daylight_blocked else "not_a_daylight_sample",
    }
    write_json(paths["market_gate_probe"], probe)

    timing = base_payload("ok")
    timing["summary"] = {
        "review_ready_wait_approval_count": 0,
        "review_ready_wait_fresh_quote_count": 0,
        "review_ready_suppressed_count": 2,
    }
    write_json(paths["wf85_timing_gate"], timing)

    morning = base_payload("ok")
    morning["summary"] = {
        "clean_approval_card_count": 2,
        "blocked_or_not_clean_count": 1,
    }
    morning["cards"] = [
        {
            "ticker": "VRT",
            "capital_deployment_approved": False,
            "trade_or_execution_approved": False,
            "paper_or_live_execution_allowed": False,
        }
    ]
    write_json(paths["morning_cards"], morning)

    autonomous = base_payload("ok")
    autonomous["summary"] = {
        "owner_review_card_candidate_count": 0,
        "clean_randall_review_card_count": 2,
        "blocked_or_waiting_count": 50,
        "autonomous_execution_allowed_now": False,
    }
    write_json(paths["autonomous_routing_cards"], autonomous)

    cron = base_payload("blocked")
    cron["summary"] = {"job_count": 52, "enabled_job_count": 34, "blocked_count": 1, "urgent_attention_count": 1}
    write_json(paths["cron_freshness"], cron)
    cron_control = base_payload("ok")
    cron_control["summary"] = {"enabled_job_count": 34, "blocked_count": 1}
    write_json(paths["cron_control"], cron_control)


def test_command_center_quiets_expected_collecting_data_state() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        paths = make_paths(Path(tmp))
        write_minimal_sources(paths)
        payload = center.build_command_center(paths)
        assert payload["status"] == "maturity_blocked_collecting_data"
        assert payload["operator_action"] == "NO_REPLY"
        assert payload["summary"]["shadow_decisions"]["done"] == 6
        assert payload["summary"]["assisted_maturity_reps_current_week"] == 0
        assert payload["summary"]["assisted_order_card_status"] == "draft_blocked_before_approval"
        assert payload["summary"]["assisted_order_card_notional_usd"] == 1500.0
        assert payload["summary"]["assisted_order_owner_approval_status"] == "pending_exact_randall_approval"
        assert payload["summary"]["assisted_order_execution_ready"] is False
        assert payload["summary"]["wf85_review_ready_suppressed_count"] == 2
        assert payload["summary"]["morning_clean_approval_review_card_count"] == 2
        assert payload["summary"]["morning_card_execution_allowed_count"] == 0
        assert payload["summary"]["autonomous_card_execution_allowed_now"] is False
        assert payload["summary"]["autonomous_execution_allowed_now"] is False
        assert payload["validation"]["status"] == "ok"


def test_daylight_blocked_probe_requires_handoff() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        paths = make_paths(Path(tmp))
        write_minimal_sources(paths, daylight_blocked=True)
        payload = center.build_command_center(paths)
        assert payload["operator_action"] == "MAIN_HANDOFF_REQUIRED"
        assert payload["summary"]["daylight_gate_result"] == "blocked"
        assert payload["validation"]["status"] == "ok"


def test_authority_drift_blocks_packet() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        paths = make_paths(Path(tmp))
        write_minimal_sources(paths, authority_drift=True)
        payload = center.build_command_center(paths)
        assert payload["status"] == "blocked"
        assert payload["operator_action"] == "BLOCKED"
        assert payload["validation"]["status"] == "error"
        assert payload["summary"]["authority_drift_count"] == 1


if __name__ == "__main__":
    test_command_center_quiets_expected_collecting_data_state()
    test_daylight_blocked_probe_requires_handoff()
    test_authority_drift_blocks_packet()
    print("wf87_autonomy_command_center_tests_passed")
