#!/usr/bin/env python3
"""Targeted checks for WF68 delivery router."""
from __future__ import annotations

import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from intraday_alert_delivery_router import build_router, write_json


def alert(ticker: str, event_type: str, entry_status: str, price: float, low: float = 90.0, high: float = 110.0):
    return {
        "ticker": ticker,
        "event_type": event_type,
        "severity": "HIGH" if event_type == "price_enters_band" else "MONITOR",
        "source_alert_packet_path": f"tmp/intraday-alerts/current-alerts.json#alerts[{ticker}]",
        "source_handoff_path": "tmp/intraday-alerts/main-session-handoff.json",
        "authority": {
            "live_trade_or_account_action_allowed": False,
            "paper_or_live_order_submission_allowed": False,
            "owner_approval_inferred": False,
        },
        "advisor_decision_packet": {
            "thesis": f"{ticker} thesis context",
            "entry_logic": "Inside written band; do not chase above upper band.",
            "invalidation": "Use written stop/reference.",
            "concentration_risk_note": "Pilot paper order only; review concentration before real capital.",
            "entry_context": {
                "observed_entry_status": entry_status,
                "observed_price": price,
                "entry_band_low": low,
                "entry_band_high": high,
            },
            "stop_context": {"stop": 80.0},
            "source_freshness": {"alert_freshness_status": "fresh"},
            "recommendation_context": {"status": "available_review_only", "recommendation_posture": "owner_decision_required"},
            "official_evidence_adequacy": {
                "decision": "sufficient_for_paper_execution_recommendation",
                "sufficient_for_paper_execution_recommendation": True,
                "blockers": [],
                "captured_official_facts": {"captured_or_explicitly_addressed_fields": ["adjusted_eps", "guidance", "growth_bridge", "segment_margins", "orders_backlog", "management_explanation", "acquisition_debt_notes"], "missing_fields": [], "manual_required_fields": []},
            },
            "wf67_paper_package_route": {
                "status": "allowed_under_wf67_guardrails",
                "required_endpoint": "https://paper-api.alpaca.markets",
                "forbidden_endpoint": "https://api.alpaca.markets",
            },
        },
    }


def clean_guard(path: Path) -> None:
    write_json(path, {
        "schema_version": "wf67.paper_execution_guard_validation.v1",
        "generated_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "status": "ok",
        "ready_for_paper_submit_cancel": True,
        "findings": [],
    })


def scoped_request(path: Path, ticker: str) -> None:
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    write_json(path, {
        "artifact_type": "wf67_paper_trade_request",
        "request_id": f"test-{ticker.lower()}",
        "created_at_utc": now,
        "order": {"symbol": ticker.upper(), "side": "buy", "qty": 1, "type": "limit", "time_in_force": "day"},
        "source": {"scoped_paper_trade_or_pilot": True},
        "execution_readiness": {
            "currently_executable": True,
            "exact_order_owner_approval_status": "test_clean",
        },
    })


def main() -> int:
    with tempfile.TemporaryDirectory() as raw:
        td = Path(raw)
        guard = td / "guard.json"
        requests = td / "requests"
        clean_guard(guard)
        scoped_request(requests / "paper-trade-request.etn.json", "ETN")

        advisor = td / "advisor.json"
        packet = {"schema_version": "wf68.advisor_alert_packet.v1", "status": "ADVISOR_READY", "alerts": [
            alert("ETN", "price_enters_band", "IN_BAND", 100.25),
            alert("MSFT", "no_chase_upper_band_breach", "ABOVE_BAND_WAIT", 120.0),
            alert("LMT", "price_breaches_stop", "BELOW_STOP", 79.0),
        ]}
        write_json(advisor, packet)
        router = build_router(advisor, td / "exec", guard, requests)
        assert router["status"] == "EXECUTION_PACKET_READY", router
        assert router["action_needed"] is True, router
        assert router["immediate_count"] == 1, router
        assert router["owner_review_count"] == 0, router
        assert router["grouped_count"] == 2, router
        immediate = router["immediate_execution_recommendations"][0]
        assert immediate["ticker"] == "ETN", immediate
        assert immediate["approval_word"] == "APPROVE", immediate
        assert immediate["recommended_order_terms"]["qty"] == 1.0, immediate
        assert immediate["recommended_order_terms"]["limit_price"] == 100.25, immediate
        assert Path(td / "exec" / "execution-recommendation.etn.json").exists(), "missing execution packet"
        assert "paper-only" in router["user_facing_message"], router["user_facing_message"]

        owner_review_advisor = td / "owner-review.json"
        write_json(owner_review_advisor, {"alerts": [alert("ETN", "price_enters_band", "IN_BAND", 100.25)]})
        owner_review = build_router(owner_review_advisor, td / "owner-review-exec", td / "missing-guard.json", td / "empty-requests")
        assert owner_review["status"] == "OWNER_REVIEW_PACKET_READY", owner_review
        assert owner_review["action_needed"] is True, owner_review
        assert owner_review["owner_review_action_needed"] is True, owner_review
        assert owner_review["immediate_count"] == 0, owner_review
        assert owner_review["owner_review_count"] == 1, owner_review
        review_packet = owner_review["owner_review_packets"][0]
        assert review_packet["approval_word"] is None, review_packet
        assert review_packet["recommended_order_terms"]["approval_word"] is None, review_packet
        assert "wf67_guard_missing" in review_packet["blockers"], owner_review
        assert "exact_scoped_wf67_request_artifact_missing_or_stale" in review_packet["blockers"], owner_review
        assert "OWNER-REVIEW" in owner_review["user_facing_message"], owner_review["user_facing_message"]
        generated = json.loads((td / "owner-review-exec" / "execution-recommendation.etn.json").read_text(encoding="utf-8"))
        assert generated["one_word_approval_contract"]["approval_word"] is None, generated
        assert generated["recommended_order_terms"]["approval_word"] is None, generated
        assert generated["wf67_next_step"]["generate_request_after_approval"] is False, generated

        blocked_advisor = td / "blocked.json"
        write_json(blocked_advisor, {"alerts": [alert("BIG", "price_enters_band", "IN_BAND", 600.0, 550.0, 650.0)]})
        blocked = build_router(blocked_advisor, td / "blocked-exec", guard, requests)
        assert blocked["status"] == "GROUPED_DIGEST_READY", blocked
        assert blocked["immediate_count"] == 0, blocked
        assert blocked["blocked_in_band_count"] == 1, blocked
        assert blocked["blocked_in_band_candidates"][0]["blockers"] == ["estimated_notional_exceeds_default_wf67_pilot_cap"], blocked

        missing_evidence_advisor = td / "missing-evidence.json"
        missing = alert("MISS", "price_enters_band", "IN_BAND", 100.0)
        missing["advisor_decision_packet"]["official_evidence_adequacy"] = {
            "decision": "insufficient_for_paper_execution_recommendation",
            "sufficient_for_paper_execution_recommendation": False,
            "blockers": ["official_evidence_not_manual_confirmed:manual_required"],
            "captured_official_facts": {"missing_fields": ["adjusted_eps"]},
        }
        write_json(missing_evidence_advisor, {"alerts": [missing]})
        evidence_blocked = build_router(missing_evidence_advisor, td / "missing-evidence-exec")
        assert evidence_blocked["status"] == "GROUPED_DIGEST_READY", evidence_blocked
        assert evidence_blocked["immediate_count"] == 0, evidence_blocked
        assert any(str(b).startswith("official_evidence_not_sufficient") for b in evidence_blocked["blocked_in_band_candidates"][0]["blockers"]), evidence_blocked

        repair_advisor = td / "repair.json"
        repair = alert("XOM", "price_enters_band", "IN_BAND", 100.0)
        repair["advisor_decision_packet"]["recommendation_context"] = {
            "status": "missing_for_ticker",
            "recommendation_posture": "manual_review_required",
            "recommended_action": "prepare_packet",
            "current_state": {"deployment_state": "DO NOT TOUCH", "daily_review_state": "REPAIR"},
        }
        write_json(repair_advisor, {"alerts": [repair]})
        repair_blocked = build_router(repair_advisor, td / "repair-exec")
        assert repair_blocked["status"] == "GROUPED_DIGEST_READY", repair_blocked
        assert repair_blocked["immediate_count"] == 0, repair_blocked
        repair_blockers = repair_blocked["blocked_in_band_candidates"][0]["blockers"]
        assert "capital_recommendation_not_available:missing_for_ticker" in repair_blockers, repair_blocked
        assert "recommendation_posture_not_execution_ready:manual_review_required" in repair_blockers, repair_blocked
        assert "deployment_state_blocks_execution_ready_packet" in repair_blockers, repair_blocked
        repair_packet = json.loads((td / "repair-exec" / "execution-recommendation.xom.json").read_text(encoding="utf-8"))
        assert repair_packet["recommended_order_terms"]["approval_word"] is None, repair_packet

        quiet_advisor = td / "quiet.json"
        write_json(quiet_advisor, {"alerts": []})
        quiet = build_router(quiet_advisor, td / "quiet-exec")
        assert quiet["status"] == "NO_REPLY", quiet
        assert quiet["action_needed"] is False, quiet

    print("intraday_alert_delivery_router targeted tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
