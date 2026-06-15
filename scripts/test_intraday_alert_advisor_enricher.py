#!/usr/bin/env python3
"""Targeted WF68 Phase 4 advisor-enricher checks."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

from intraday_alert_advisor_enricher import (
    DEFAULT_FRESHNESS_REVIEW,
    DEFAULT_HANDOFF,
    DEFAULT_RECOMMENDATIONS,
    DEFAULT_RECOMMENDATION_VALIDATION,
    DEFAULT_WF66_OFFICIAL_BRIDGE,
    ROOT,
    alert_scoped_recommendation_context,
    build_advisor_packet,
    main,
    validate_advisor_packet,
)

def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def main_test() -> int:
    packet = build_advisor_packet(
        DEFAULT_HANDOFF,
        DEFAULT_RECOMMENDATIONS,
        DEFAULT_RECOMMENDATION_VALIDATION,
        DEFAULT_FRESHNESS_REVIEW,
        DEFAULT_WF66_OFFICIAL_BRIDGE,
    )
    validation = validate_advisor_packet(packet)
    assert packet["status"] == "ADVISOR_READY", packet
    assert packet["alert_count"] == 1, packet
    assert validation["status"] == "ok", validation
    alert = packet["alerts"][0]
    assert alert["ticker"] == "ETN", alert
    decision = alert["advisor_decision_packet"]
    assert decision["thesis"], decision
    assert decision["entry_logic"], decision
    assert decision["entry_context"]["entry_band_low"] == 360.99, decision
    assert decision["entry_context"]["entry_band_high"] == 404.94, decision
    assert decision["invalidation"], decision
    assert decision["stop_context"]["stop"] == 341.01, decision
    assert decision["source_freshness"]["alert_freshness_status"] == "fresh", decision
    assert decision["entry_context"]["observed_entry_status"] == "IN_BAND", decision
    assert decision["recommendation_context"]["recommendation_posture"] in {"owner_decision_required", "manual_review_required"}, decision
    assert decision["recommendation_context"]["trade_or_account_action_allowed"] is False, decision
    assert decision["wf66_official_source_context"]["status"] == "available_review_only", decision
    assert decision["wf66_official_source_context"]["trade_or_account_action_allowed"] is False, decision
    adequacy = decision["official_evidence_adequacy"]
    assert adequacy["decision"] == "sufficient_for_paper_execution_recommendation", adequacy
    assert adequacy["sufficient_for_paper_execution_recommendation"] is True, adequacy
    assert adequacy["blockers"] == [], adequacy
    assert adequacy["latest_official_evidence"]["status"] == "manual_confirmed", adequacy
    facts = adequacy["captured_official_facts"]
    assert "adjusted_eps" in facts["captured_or_explicitly_addressed_fields"], facts
    assert "orders_backlog" in facts["captured_or_explicitly_addressed_fields"], facts
    assert facts["missing_fields"] == [], facts
    assert facts["manual_required_fields"] == [], facts
    assert decision["outcome_linkage"]["probability_claims_allowed"] is False, decision
    assert "explicit" in decision["owner_action_required"], decision
    assert decision["wf67_paper_package_route"]["status"] == "allowed_under_wf67_guardrails", decision
    assert decision["wf67_paper_package_route"]["required_endpoint"] == "https://paper-api.alpaca.markets", decision
    assert decision["wf67_paper_package_route"]["forbidden_endpoint"] == "https://" + "api.alpaca.markets", decision
    assert alert["authority"]["live_trade_or_account_action_allowed"] is False, alert
    assert packet["authority"]["paper_trade_allowed"] is False, packet
    assert packet["wf67_paper_package_route"]["execution_owner"] == "WF67 wrapper only", packet

    scoped_wait = alert_scoped_recommendation_context(
        {"recommendation_posture": "wait_for_band", "recommended_action": "wait_for_band"},
        "IN_BAND",
        "price_enters_band",
    )
    assert scoped_wait["recommendation_posture"] == "manual_review_required", scoped_wait
    assert scoped_wait["recommended_action"] == "prepare_packet", scoped_wait
    assert scoped_wait["trade_or_account_action_allowed"] is False, scoped_wait
    assert scoped_wait["apply_allowed"] is False, scoped_wait

    with tempfile.TemporaryDirectory() as raw_td:
        td = Path(raw_td)
        no_reply_handoff = td / "no-reply-handoff.json"
        no_reply_handoff.write_text(json.dumps({
            "schema_version": "wf68.main_session_handoff.v1",
            "workflow": "WF68",
            "status": "NO_REPLY",
            "generated_at_utc": "2026-05-20T00:00:00Z",
            "alerts": [],
            "authority": {"live_trade_or_account_action_allowed": False, "paper_trade_allowed": False},
        }), encoding="utf-8")
        no_alert = build_advisor_packet(
            no_reply_handoff,
            DEFAULT_RECOMMENDATIONS,
            DEFAULT_RECOMMENDATION_VALIDATION,
            DEFAULT_FRESHNESS_REVIEW,
            DEFAULT_WF66_OFFICIAL_BRIDGE,
        )
        no_alert_validation = validate_advisor_packet(no_alert)
        assert no_alert["status"] == "NO_REPLY", no_alert
        assert no_alert["alert_count"] == 0, no_alert
        assert no_alert_validation["status"] == "ok", no_alert_validation

        rc = main([
            "--handoff", str(DEFAULT_HANDOFF),
            "--output-json", str(td / "advisor.json"),
            "--output-md", str(td / "advisor.md"),
            "--validation-output", str(td / "validation.json"),
        ])
        assert rc == 0, rc
        written = load(td / "advisor.json")
        assert written["status"] == "ADVISOR_READY", written
        assert (td / "advisor.md").exists(), "markdown advisor packet missing"
        assert load(td / "validation.json")["status"] == "ok", "validation status not ok"

    print("intraday_alert_advisor_enricher targeted tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main_test())
