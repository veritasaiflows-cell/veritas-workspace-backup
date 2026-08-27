#!/usr/bin/env python3
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import wf85_opportunity_visibility_queue as queue


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def base_payload(status: str = "ok") -> dict:
    return {
        "status": status,
        "generated_at_utc": "2026-06-21T06:00:00Z",
        "validation": {"status": "ok", "errors": [], "warnings": []},
        "authority_boundary": {
            "capital_deployment_approved": False,
            "trade_or_execution_approved": False,
            "paper_or_live_execution_allowed": False,
            "owner_approval_inferred": False,
        },
    }


def make_paths(root: Path) -> dict[str, Path]:
    return {key: root / f"{key}.json" for key in queue.SOURCES}


def write_sources(paths: dict[str, Path], *, market_open: bool = True, drift: bool = False) -> None:
    visibility = base_payload()
    visibility["rows"] = [
        {
            "ticker": "AAA",
            "name": "AAA Corp",
            "visibility_state": "owner_review_ready",
            "blockers": [],
            "auto_tier": "Tier A",
            "auto_state": "A-READY",
            "owner_card_path": "tmp/aaa-card.json",
            "wf67_request_path": "tmp/aaa-request.json",
            "capital_deployment_approved": False,
            "trade_or_execution_approved": False,
            "paper_or_live_execution_allowed": False,
            "owner_approval_inferred": False,
        }
    ]
    write_json(paths["wf78_visibility_queue"], visibility)

    cards = base_payload()
    cards["cards"] = [{"ticker": "AAA", "decision_state": "monitor_only", "decision_state_reason": [], "auto_tier": "Tier A", "auto_state": "A-READY"}]
    if drift:
        cards["authority_boundary"]["paper_or_live_execution_allowed"] = True
    write_json(paths["trade_grade_cards"], cards)

    timing = base_payload()
    timing["rows"] = [{"ticker": "AAA", "final_timing_state": "review_ready_wait_approval", "current_price": 10}]
    write_json(paths["wf85_timing_gate"], timing)

    factory = base_payload()
    factory["decision_ledger"] = [{"ticker": "AAA", "gate_verdict": "promote_for_owner_review", "owner_card_path": "tmp/aaa-card.json"}]
    write_json(paths["finance_decision_factory"], factory)

    market = base_payload()
    market["final_market_deployment_state"] = "owner_review_candidate" if market_open else "candidate_pending_market_refresh"
    market["operator_action"] = "MAIN_SESSION_REVIEW" if market_open else "MARKET_REFRESH_PENDING"
    market["market_session"] = {"deployment_fresh_price_allowed": market_open, "window": "market_hours_fresh" if market_open else "weekend"}
    write_json(paths["market_loop"], market)


def test_owner_review_ready_when_market_and_cards_clean() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        paths = make_paths(Path(tmp))
        write_sources(paths, market_open=True)
        payload = queue.build_payload(paths)
        assert payload["summary"]["owner_review_ready_count"] == 1
        assert payload["rows"][0]["wf85_visibility_state"] == "owner_review_ready"
        assert payload["rows"][0]["paper_or_live_execution_allowed"] is False
        assert payload["validation"]["status"] == "ok"


def test_market_closed_downgrades_to_pending() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        paths = make_paths(Path(tmp))
        write_sources(paths, market_open=False)
        payload = queue.build_payload(paths)
        assert payload["summary"]["market_refresh_pending_count"] == 1
        assert payload["rows"][0]["wf85_visibility_state"] == "market_refresh_pending"
        assert "market_refresh_pending" in payload["rows"][0]["blockers"]


def test_authority_drift_blocks_queue() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        paths = make_paths(Path(tmp))
        write_sources(paths, drift=True)
        payload = queue.build_payload(paths)
        assert payload["status"] == "blocked"
        assert payload["validation"]["status"] == "error"
        assert any("source_authority_drift" in item for item in payload["validation"]["errors"])


def test_intraday_overlay_surfaces_review_without_owner_or_execution_semantics() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        paths = make_paths(Path(tmp))
        write_sources(paths, market_open=True)
        attention = base_payload()
        attention["review_attention"] = [{
            "ticker": "CAT",
            "auto_tier": "Tier B",
            "route_state": "B-CANDIDATE",
            "attention_type": "entry_policy_review",
            "recommended_action": "main_review_required",
            "blockers": ["band_proposal_needs_review"],
            "capital_deployment_approved": False,
            "trade_or_execution_approved": False,
            "paper_or_live_execution_allowed": False,
            "owner_approval_inferred": False,
        }]
        attention["repair_attention"] = []
        write_json(paths["in_band_review_attention"], attention)
        overlay = base_payload()
        overlay["rows"] = [{
            "ticker": "CAT",
            "auto_tier": "Tier B",
            "recommended_action": "main_review_required",
            "entry_band": {"low": 90, "high": 110, "band_status": "IN_BAND"},
            "stop_or_invalidation": {"level": 80},
            "current_price": {
                "latest_known_price": 100,
                "quote_freshness_status": "intraday_review_only_fresh",
                "review_only_quote": True,
                "approval_draft_eligible": False,
            },
            "source_freshness": {
                "fresh_for_review": True,
                "fresh_for_approval": False,
                "expires_at_utc": "2099-08-13T17:15:00Z",
            },
            "capital_deployment_approved": False,
            "trade_or_execution_approved": False,
            "paper_or_live_execution_allowed": False,
            "owner_approval_inferred": False,
        }]
        write_json(paths["intraday_review_overlay"], overlay)
        payload = queue.build_payload(paths)
    row = next(item for item in payload["rows"] if item["ticker"] == "CAT")
    assert payload["status"] == "ok", payload
    assert row["wf85_visibility_state"] == "intraday_review_required", row
    assert row["intraday_review_quote"]["quote_freshness_status"] == "intraday_review_only_fresh", row
    assert row["owner_action_required"] is False, row
    assert row["capital_deployment_approved"] is False, row
    assert row["paper_or_live_execution_allowed"] is False, row


def test_expired_overlay_downgrades_to_attention_repair() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        paths = make_paths(Path(tmp))
        write_sources(paths, market_open=True)
        attention = base_payload()
        attention["review_attention"] = [{
            "ticker": "CAT",
            "auto_tier": "Tier B",
            "attention_type": "entry_policy_review",
            "blockers": ["band_proposal_needs_review"],
        }]
        attention["repair_attention"] = []
        write_json(paths["in_band_review_attention"], attention)
        overlay = base_payload()
        overlay["rows"] = [{
            "ticker": "CAT",
            "current_price": {
                "quote_freshness_status": "intraday_review_only_fresh",
                "review_only_quote": True,
                "approval_draft_eligible": False,
            },
            "source_freshness": {
                "fresh_for_review": True,
                "fresh_for_approval": False,
                "expires_at_utc": "2026-08-13T16:00:00Z",
            },
        }]
        write_json(paths["intraday_review_overlay"], overlay)
        payload = queue.build_payload(paths)
    row = next(item for item in payload["rows"] if item["ticker"] == "CAT")
    assert row["wf85_visibility_state"] == "intraday_review_sync_degraded", row
    assert row["intraday_overlay_applied"] is False, row
    assert "intraday_review_overlay_missing_or_rejected" in row["blockers"], row


if __name__ == "__main__":
    test_owner_review_ready_when_market_and_cards_clean()
    test_market_closed_downgrades_to_pending()
    test_authority_drift_blocks_queue()
    test_intraday_overlay_surfaces_review_without_owner_or_execution_semantics()
    test_expired_overlay_downgrades_to_attention_repair()
    print("wf85_opportunity_visibility_queue tests passed")
