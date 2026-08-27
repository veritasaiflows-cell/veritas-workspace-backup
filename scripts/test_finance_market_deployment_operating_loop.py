#!/usr/bin/env python3
"""Focused tests for finance_market_deployment_operating_loop.py."""
from __future__ import annotations

from datetime import datetime, timezone

import finance_market_deployment_operating_loop as loop


def dt(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def test_market_session_classifies_phoenix_market_hours() -> None:
    settling = loop.market_session(dt("2026-06-15T13:35:00Z"))
    regular = loop.market_session(dt("2026-06-15T13:45:00Z"))
    final_probe = loop.market_session(dt("2026-06-15T19:07:00Z"))
    pre = loop.market_session(dt("2026-06-15T12:00:00Z"))
    after = loop.market_session(dt("2026-06-15T21:00:00Z"))
    weekend = loop.market_session(dt("2026-06-14T16:00:00Z"))
    juneteenth = loop.market_session(dt("2026-06-19T15:00:00Z"))
    assert settling["window"] == "open_settling"
    assert settling["deployment_fresh_price_allowed"] is False
    assert regular["window"] == "market_hours_fresh"
    assert regular["regular_market_hours"] is True
    assert regular["deployment_fresh_price_allowed"] is True
    assert final_probe["window"] == "late_session"
    assert final_probe["deployment_fresh_price_allowed"] is True
    assert final_probe["recommended_probe_times_az"] == ["06:42", "07:14", "12:07"]
    assert pre["window"] == "pre_open"
    assert pre["deployment_fresh_price_allowed"] is False
    assert after["window"] == "post_close"
    assert weekend["window"] == "weekend"
    assert weekend["deployment_fresh_price_allowed"] is False
    assert juneteenth["window"] == "market_closed"
    assert juneteenth["market_holiday"] is True
    assert juneteenth["deployment_fresh_price_allowed"] is False


def test_final_state_prioritizes_risk_and_owner_review() -> None:
    tier = {"capital_deployment_approved_count": 0, "trade_or_execution_approved_count": 0}
    fresh = {"market_hours_refresh_classification": "READY"}
    opp = {
        "invalidation_count": 1,
        "clean_paper_prep_count": 1,
        "new_review_opportunity_count": 0,
        "paper_drift_count": 0,
        "near_deployment_blocked_count": 0,
    }
    open_session = {"deployment_fresh_price_allowed": True}
    state, action = loop.final_state(tier, fresh, opp, [], open_session)
    assert state == "risk_review_now"
    assert "invalidation" in action

    opp["invalidation_count"] = 0
    state, action = loop.final_state(tier, fresh, opp, [], open_session)
    assert state == "owner_review_candidate"
    assert "WF67" in action


def test_final_state_downgrades_material_signals_outside_fresh_price_window() -> None:
    tier = {"capital_deployment_approved_count": 0, "trade_or_execution_approved_count": 0}
    fresh = {"market_hours_refresh_classification": "READY"}
    opp = {
        "invalidation_count": 0,
        "clean_paper_prep_count": 1,
        "new_review_opportunity_count": 0,
        "paper_drift_count": 0,
        "near_deployment_blocked_count": 0,
    }
    state, action = loop.final_state(tier, fresh, opp, [], {"deployment_fresh_price_allowed": False})
    assert state == "candidate_pending_market_refresh"
    assert "fresh market-hours probe" in action


def test_reconciliation_downgrades_when_opportunity_ahead_of_decision_layer() -> None:
    session = {"deployment_fresh_price_allowed": True}
    fresh = {
        "market_hours_refresh_classification": "WAIT_FOR_MARKET_HOURS",
        "deployment_timing_validation": "ok",
        "wf85_runner_status": "ok",
        "wf85_runner_validation": "ok",
    }
    opp = {
        "clean_paper_prep_count": 1,
        "autonomous_owner_review_card_candidate_count": 0,
        "new_review_opportunity_count": 0,
        "autonomous_execution_allowed_now": False,
    }
    reconciliation = loop.reconcile_surfaces(session, fresh, opp)
    assert reconciliation["status"] == "downgrade_required"
    assert "opportunity_layer_ahead_of_wf85_decision_layer" in reconciliation["reasons"]


def test_determinism_hashes_same_inputs_same_decision_counts() -> None:
    input_snapshot = {"session": "market_hours_fresh", "tier_counts": {"Tier A": 1}}
    decision_snapshot = {"final_market_deployment_state": "watch_repair_or_wait", "no_chase_count": 2}
    assert loop.stable_hash(input_snapshot) == loop.stable_hash(dict(reversed(list(input_snapshot.items()))))
    assert loop.stable_hash(decision_snapshot) == loop.stable_hash(decision_snapshot.copy())


def test_semantic_input_snapshot_includes_blockers_for_determinism() -> None:
    base = loop.semantic_input_snapshot({}, {}, {}, {"window": "post_close"}, [])
    blocked = loop.semantic_input_snapshot({}, {}, {}, {"window": "post_close"}, ["source_validation_not_ok"])

    assert base["blockers"] == []
    assert blocked["blockers"] == ["source_validation_not_ok"]
    assert loop.stable_hash(base) != loop.stable_hash(blocked)


def test_validate_rejects_authority_widening() -> None:
    payload = {
        "authority_boundary": dict(loop.AUTHORITY_BOUNDARY),
        "artifact_records": [{"name": "bad", "exists": True, "parseable_json": True, "forbidden_true_authority_paths": ["owner_approval_inferred"]}],
        "tier_state": {"capital_deployment_approved_count": 0, "trade_or_execution_approved_count": 0},
        "refresh_steps": [],
        "final_market_deployment_state": "no_action_monitor",
    }
    validation = loop.validate(payload)
    assert validation["status"] == "error"
    assert any("authority_widened" in item for item in validation["errors"])


def test_validate_allows_owner_review_without_execution_authority() -> None:
    payload = {
        "authority_boundary": dict(loop.AUTHORITY_BOUNDARY),
        "artifact_records": [{"name": "ok", "exists": True, "parseable_json": True, "forbidden_true_authority_paths": []}],
        "tier_state": {"capital_deployment_approved_count": 0, "trade_or_execution_approved_count": 0},
        "refresh_steps": [{"name": "probe", "required": True, "ok": True}],
        "final_market_deployment_state": "owner_review_candidate",
        "market_session": {"deployment_fresh_price_allowed": True},
    }
    validation = loop.validate(payload)
    assert validation["status"] == "ok"


def test_validate_rejects_current_decision_state_when_market_not_fresh() -> None:
    payload = {
        "authority_boundary": dict(loop.AUTHORITY_BOUNDARY),
        "artifact_records": [{"name": "ok", "exists": True, "parseable_json": True, "forbidden_true_authority_paths": []}],
        "tier_state": {"capital_deployment_approved_count": 0, "trade_or_execution_approved_count": 0},
        "refresh_steps": [{"name": "probe", "required": True, "ok": True}],
        "final_market_deployment_state": "owner_review_candidate",
        "market_session": {"deployment_fresh_price_allowed": False},
    }
    validation = loop.validate(payload)
    assert validation["status"] == "error"
    assert "current_decision_state_outside_fresh_price_window" in validation["errors"]


def test_validate_rejects_current_decision_state_when_reconciliation_downgrades() -> None:
    payload = {
        "authority_boundary": dict(loop.AUTHORITY_BOUNDARY),
        "artifact_records": [{"name": "ok", "exists": True, "parseable_json": True, "forbidden_true_authority_paths": []}],
        "tier_state": {"capital_deployment_approved_count": 0, "trade_or_execution_approved_count": 0},
        "refresh_steps": [{"name": "probe", "required": True, "ok": True}],
        "final_market_deployment_state": "owner_review_candidate",
        "market_session": {"deployment_fresh_price_allowed": True},
        "cross_surface_reconciliation": {"status": "downgrade_required"},
    }
    validation = loop.validate(payload)
    assert validation["status"] == "error"
    assert "current_decision_state_with_surface_reconciliation_downgrade" in validation["errors"]


def main() -> int:
    test_market_session_classifies_phoenix_market_hours()
    test_final_state_prioritizes_risk_and_owner_review()
    test_final_state_downgrades_material_signals_outside_fresh_price_window()
    test_reconciliation_downgrades_when_opportunity_ahead_of_decision_layer()
    test_determinism_hashes_same_inputs_same_decision_counts()
    test_semantic_input_snapshot_includes_blockers_for_determinism()
    test_validate_rejects_authority_widening()
    test_validate_allows_owner_review_without_execution_authority()
    test_validate_rejects_current_decision_state_when_market_not_fresh()
    test_validate_rejects_current_decision_state_when_reconciliation_downgrades()
    print("finance_market_deployment_operating_loop tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
