#!/usr/bin/env python3
"""Focused tests for WF78 route-readiness P3 market/ranking packet."""
from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "wf78_route_readiness_p3_market_ranking.py"


def load_module():
    sys.path.insert(0, str(ROOT / "scripts"))
    spec = importlib.util.spec_from_file_location("wf78_route_readiness_p3_market_ranking", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def row(
    ticker: str,
    *,
    tier: str = "Tier A",
    state: str = "A-WATCH",
    timing: str = "in_band_review_only_quote",
    decision: str = "monitor_only",
    trade: str = "not_trade_ready_in_band_monitor_only",
    band: str = "IN_BAND",
    quote: str = "post_close_final_quote_available_for_non_executing_review",
    priority: int = 10,
    authority: str = "review_only_no_capital_or_execution_authority",
) -> dict:
    return {
        "ticker": ticker,
        "name": f"{ticker} Inc",
        "sector": "Technology",
        "routing_tier": tier,
        "routing_state": state,
        "auto_tier": tier,
        "auto_state": state,
        "route_priority": priority,
        "latest_price": 100.0,
        "entry_band_low": 95.0,
        "entry_band_high": 105.0,
        "stop_or_invalidation": 90.0,
        "band_status": band,
        "quote_freshness_status": quote,
        "timing_state": timing,
        "decision_state": decision,
        "trade_readiness_state": trade,
        "authority_state": authority,
        "route_readiness": {"next_route_action": "fixture next action"},
    }


def seed_workspace(root: Path, module, rows: list[dict]) -> None:
    module.ROOT = root
    module.TMP = root / "tmp"
    module.FRONTDOOR = module.TMP / "finance-cache-frontdoor.json"
    module.MARKET_HOURS_READINESS = module.TMP / "wf85-market-hours-refresh-readiness.json"
    module.DEFAULT_OUT = module.TMP / "wf78-route-readiness-p3-market-ranking.json"
    write_json(
        module.FRONTDOOR,
        {
            "schema": "veritas.finance_cache_frontdoor.v1",
            "generated_at_utc": "2026-07-03T07:00:00Z",
            "status": "ok",
            "validation": {"status": "ok", "errors": [], "warnings": []},
            "rows": rows,
        },
    )
    write_json(
        module.MARKET_HOURS_READINESS,
        {
            "schema": "veritas.wf85_market_hours_refresh_readiness.v1",
            "generated_at_utc": "2026-07-03T07:00:00Z",
            "status": "ok",
            "classification": "WAIT_FOR_MARKET_HOURS",
        },
    )


def test_holiday_keeps_owner_gated_candidate_refresh_required() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        seed_workspace(
            Path(tmpdir),
            module,
            [
                row(
                    "AAA",
                    decision="review_ready",
                    trade="approval_card_candidate_owner_gated",
                    quote="fresh",
                )
            ],
        )
        payload = module.build_payload(datetime(2026, 7, 3, 15, 0, tzinfo=timezone.utc))
        top = payload["top_route_queue"][0]

        assert payload["status"] == "ok"
        assert payload["market_session"]["market_holiday"] is True
        assert payload["market_session"]["window"] == "market_closed"
        assert top["category"] == "approval_card_candidate_owner_gated"
        assert top["market_window_refresh_required"] is True
        assert top["capital_deployment_approved"] is False
        assert payload["summary"]["approval_card_candidate_owner_gated_count"] == 1


def test_categories_are_ranked_without_trade_authority() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        seed_workspace(
            Path(tmpdir),
            module,
            [
                row("INB", timing="in_band_review_only_quote", trade="not_trade_ready_in_band_monitor_only", priority=20),
                row("REC", timing="below_band_reclaim_watch", trade="not_trade_ready_reclaim_watch", band="BELOW_BAND", priority=30),
                row("NOC", timing="above_band_no_chase", trade="not_trade_ready_no_chase", band="ABOVE_BAND", priority=40),
                row("AVD", timing="below_stop_or_invalidation", decision="below_stop_or_invalidation", trade="not_trade_ready_below_stop_or_invalidation", band="BELOW_STOP", priority=50),
            ],
        )
        payload = module.build_payload(datetime(2026, 7, 2, 18, 0, tzinfo=timezone.utc))
        categories = {item["ticker"]: item["category"] for item in payload["rows"]}

        assert payload["validation"]["status"] == "ok"
        assert categories["INB"] == "in_band_review_monitor"
        assert categories["REC"] == "reclaim_watch"
        assert categories["NOC"] == "no_chase"
        assert categories["AVD"] == "avoid_until_reclaim_or_invalidation_repair"
        assert payload["summary"]["authority_state_counts"] == {"review_only_no_capital_or_execution_authority": 4}
        assert all(item["paper_or_live_execution_allowed"] is False for item in payload["rows"])


def test_authority_conflict_blocks_validation() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        seed_workspace(
            Path(tmpdir),
            module,
            [
                row(
                    "BAD",
                    authority="blocked_authority_flag_true",
                    trade="blocked_authority_conflict",
                )
            ],
        )
        payload = module.build_payload(datetime(2026, 7, 2, 18, 0, tzinfo=timezone.utc))

        assert payload["status"] == "blocked"
        assert payload["validation"]["status"] == "error"
        assert payload["rows"][0]["category"] == "blocked_authority_conflict"
        assert payload["summary"]["market_window_refresh_required_count"] == 1


if __name__ == "__main__":
    test_holiday_keeps_owner_gated_candidate_refresh_required()
    test_categories_are_ranked_without_trade_authority()
    test_authority_conflict_blocks_validation()
    print("wf78_route_readiness_p3_market_ranking tests passed")
