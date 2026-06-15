from __future__ import annotations

from full_portfolio_view import action_bucket, build_records, sector_summary


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    artifacts = {
        "portfolio_config": {
            "portfolio": {"core": [{"ticker": "AAA", "weight": 10, "sector": "Tech", "thesis": "quality"}], "tactical": [], "speculative": []},
            "tracked_universe": {"AAA": {"sector": "Tech", "portfolio_role": "core", "coverage_lane": "execution", "workflow_state": "DEPLOYED"}},
            "entry_bands": {"AAA": {"low": 90, "high": 100, "stop": 85, "label": "90-100"}},
        },
        "technical_refresh": {"records": [{"ticker": "AAA", "close": 95, "in_entry_band": True, "below_stop": False, "data_date": "2026-05-11"}]},
        "deployment_check": {"records": [{"ticker": "AAA", "action_state": "DEPLOYABLE NOW", "reason": "in band"}]},
        "trigger_sheet": {"records": []},
        "regime_scores": {"records": [{"ticker": "AAA", "stance": "DEPLOYABLE NOW", "total": 19}]},
        "board_canon_guardrail": {"risks": []},
        "daily_executive_brief": {"qualified_band_behavior": []},
        "market_state": {},
    }
    records = build_records(artifacts)
    require(len(records) == 1, "tracked universe record should be joined")
    record = records[0]
    require(record["ticker"] == "AAA", "ticker should be preserved")
    require(record["draft_weight"] == 10, "draft weight should come from portfolio config")
    require(record["entry_band"]["low"] == 90, "entry band should come from config")
    require(record["action_bucket"] == "deployable_now_review_only", "deployable state should be review-only deployable bucket")
    require("portfolio_config" in record["source_provenance"], "source provenance should include config")
    require(action_bucket({"below_stop": True, "trigger_action_state": "DEPLOYABLE NOW"}) == "do_not_touch", "below-stop must override deployable language")
    sectors = sector_summary(records)
    require(sectors[0]["sector"] == "Tech" and sectors[0]["draft_weight_total"] == 10, "sector summary should aggregate weights")
    print("full_portfolio_view_tests_passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
