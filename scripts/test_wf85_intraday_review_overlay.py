#!/usr/bin/env python3
from __future__ import annotations

import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import wf85_intraday_review_overlay as overlay


NOW = datetime(2026, 8, 13, 17, 0, 0, tzinfo=timezone.utc)
QUOTE_TIME = "2026-08-13T16:59:50Z"


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def paths(root: Path) -> dict[str, Path]:
    return {
        "quote_snapshot_proof": root / "quote.json",
        "quote_snapshot_validation": root / "quote-validation.json",
        "in_band_review_attention": root / "attention.json",
    }


def write_sources(root: Path, *, calendar: str = "fresh_intraday", attention_status: str = "ok", authority_drift: bool = False) -> dict[str, Path]:
    source_paths = paths(root)
    quote = {
        "status": "ok",
        "generated_at_utc": "2026-08-13T16:59:55Z",
        "authority": {"paper_or_live_execution_allowed": False},
        "snapshots": [{
            "symbol": "CAT",
            "price": 100.0,
            "source_timestamp_utc": QUOTE_TIME,
            "source_market_date": "2026-08-13",
            "age_seconds": 10,
            "freshness_status": "fresh",
            "calendar_freshness_status": calendar,
        }],
    }
    validation = {"status": "ok", "generated_at_utc": "2026-08-13T16:59:56Z"}
    attention = {
        "status": attention_status,
        "generated_at_utc": "2026-08-13T16:59:57Z",
        "validation": {"status": "ok"},
        "authority_boundary": {"capital_deployment_approved": authority_drift},
        "summary": {"attention_fingerprint": "cat-test-v1"},
        "review_attention": [{
            "ticker": "CAT",
            "auto_tier": "Tier B",
            "route_state": "B-CANDIDATE",
            "current_price": 100.0,
            "quote_source_timestamp_utc": QUOTE_TIME,
            "entry_band_low": 90.0,
            "entry_band_high": 110.0,
            "stop_or_invalidation": 80.0,
            "derived_band_status": "IN_BAND",
            "attention_type": "entry_policy_review",
            "recommended_action": "main_review_required",
            "capital_deployment_approved": False,
            "trade_or_execution_approved": False,
            "paper_or_live_execution_allowed": False,
            "owner_approval_inferred": False,
        }],
        "repair_attention": [],
    }
    write_json(source_paths["quote_snapshot_proof"], quote)
    write_json(source_paths["quote_snapshot_validation"], validation)
    write_json(source_paths["in_band_review_attention"], attention)
    return source_paths


def test_fresh_in_band_overlay_is_review_only() -> None:
    with tempfile.TemporaryDirectory() as temp:
        payload = overlay.build_payload(write_sources(Path(temp)), NOW)
    assert payload["status"] == "ok", payload
    assert payload["validation"]["status"] == "ok", payload
    assert payload["summary"]["overlay_tickers"] == ["CAT"], payload
    row = payload["rows"][0]
    assert row["current_price"]["quote_freshness_status"] == overlay.REVIEW_ONLY_QUOTE_STATUS, row
    assert row["current_price"]["approval_draft_eligible"] is False, row
    assert row["source_freshness"]["fresh_for_approval"] is False, row
    assert row["capital_deployment_approved"] is False, row
    assert row["paper_or_live_execution_allowed"] is False, row


def test_after_hours_or_stale_quote_is_rejected_not_promoted() -> None:
    with tempfile.TemporaryDirectory() as temp:
        payload = overlay.build_payload(write_sources(Path(temp), calendar="current_last_completed_session"), NOW)
    assert payload["status"] == "warning", payload
    assert payload["rows"] == [], payload
    assert payload["rejected_attention"][0]["ticker"] == "CAT", payload
    assert "quote_not_market_hours_fresh" in payload["rejected_attention"][0]["reasons"], payload
    assert payload["summary"]["approval_card_draft_eligible_count"] == 0, payload


def test_blocked_attention_or_authority_drift_fails_closed() -> None:
    with tempfile.TemporaryDirectory() as temp:
        payload = overlay.build_payload(write_sources(Path(temp), attention_status="blocked"), NOW)
    assert payload["status"] == "blocked", payload
    assert payload["rows"] == [], payload
    assert payload["validation"]["status"] == "error", payload

    with tempfile.TemporaryDirectory() as temp:
        payload = overlay.build_payload(write_sources(Path(temp), authority_drift=True), NOW)
    assert payload["status"] == "blocked", payload
    assert payload["rows"] == [], payload
    assert any("source_authority_drift" in item for item in payload["errors"]), payload


if __name__ == "__main__":
    test_fresh_in_band_overlay_is_review_only()
    test_after_hours_or_stale_quote_is_rejected_not_promoted()
    test_blocked_attention_or_authority_drift_fails_closed()
    print("wf85_intraday_review_overlay tests passed")
