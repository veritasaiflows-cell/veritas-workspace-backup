#!/usr/bin/env python3
"""Direct checks for the WF75 AI Drop-Service OS demo generator."""
from __future__ import annotations

import copy

import wf75_ai_drop_service_demo as demo


def test_payload_is_internal_safe() -> None:
    payload = demo.build_payload()
    assert payload["validation"]["status"] == "ok"
    boundary = payload["authority_boundary"]
    for key in demo.REQUIRED_FALSE_AUTHORITY:
        assert boundary.get(key) is False, f"{key} must stay false"
    assert payload["scenario"]["no_real_customer_data"] is True
    assert payload["scenario"]["sensitive_data_used"] is False


def test_demo_has_required_delivery_assets() -> None:
    payload = demo.build_payload()
    assert len(payload["lead_events"]) >= 3
    assert len(payload["workflow_map"]) >= 5
    assert len(payload["business_hours_state_machine"]["states"]) >= 3
    assert len(payload["triage_rule_set"]["worked_examples"]) >= 3
    assert payload["normalized_lead_records"]
    assert payload["acknowledgement_decisions"]
    assert len(payload["executed_escalation_trail"]) >= 4
    assert payload["daily_operational_digest"]
    assert payload["weekly_improvement_backlog"]
    assert len(payload["opportunity_matrix"]) >= 5
    assert len(payload["source_support"]) >= 5
    assert len(payload["research_evidence"]) >= 5
    assert payload["unsupported_claims"]
    assert payload["agent_validation_evidence"]["research_scout"]["verdict"] == "tool_and_source_support_integrated"
    assert payload["agent_validation_evidence"]["qa_redteam_recheck"]["verdict"] == "internal_demo_ready"
    assert payload["sla"]["first_human_touch_minutes"] == 15
    assert payload["private_pilot_approval_card"]["status"] == "draft_not_approved"
    assert payload["pilot_readiness_gate"]["status"] == "internal_demo_ready_private_pilot_prep_not_ready"
    assert payload["pilot_readiness_gate"]["required_before_private_pilot_prep"]


def test_validation_catches_authority_expansion() -> None:
    payload = demo.build_payload()
    bad = copy.deepcopy(payload)
    bad["authority_boundary"]["payment_collection_allowed"] = True
    validation = demo.validate_payload(bad)
    assert validation["status"] == "error"
    assert "authority_payment_collection_allowed_not_false" in validation["errors"]


def test_rendered_report_keeps_boundary() -> None:
    report = demo.render_deliverable(demo.build_payload()).lower()
    assert "internal synthetic proof only" in report
    assert "not customer-ready" in report
    assert "no real customer data" in report
    assert "remaining gap" in report


def main() -> int:
    test_payload_is_internal_safe()
    test_demo_has_required_delivery_assets()
    test_validation_catches_authority_expansion()
    test_rendered_report_keeps_boundary()
    print("ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
