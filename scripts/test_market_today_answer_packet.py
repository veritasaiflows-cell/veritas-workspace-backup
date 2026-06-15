from __future__ import annotations

import market_today_answer_packet as packet


def expect(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def main() -> int:
    payload = packet.build_packet()
    errors: list[str] = []

    expect(payload.get("schema") == packet.SCHEMA, "schema mismatch", errors)
    expect(payload.get("status") in {"ok", "warning", "blocked"}, "bad status", errors)
    expect(payload.get("validation", {}).get("status") in {"ok", "warning"}, "validation should not error on current workspace artifacts", errors)

    boundary = payload.get("authority_boundary", {})
    expect(boundary.get("review_only") is True, "review_only must be true", errors)
    for key in (
        "external_fetch_allowed_by_this_script",
        "canon_or_portfolio_mutation_allowed",
        "ticker_card_mutation_allowed",
        "capital_deployment_allowed",
        "capital_deployment_approved",
        "paper_or_live_execution_allowed",
        "brokerage_or_account_action_allowed",
        "customer_or_external_delivery_allowed",
        "owner_approval_inferred",
    ):
        expect(boundary.get(key) is False, f"{key} must be false", errors)

    readiness = payload.get("answer_readiness", {})
    expect(readiness.get("can_answer_basic_market_day_without_web") is True, "basic local market read should be ready", errors)
    expect(readiness.get("can_answer_full_market_close_recap_without_web") is True, "full recap should be ready after broad-index/rates/driver integration", errors)
    missing = set(readiness.get("missing_for_web_free_full_recap") or [])
    for field in (
        "dow_close_change",
        "nasdaq_composite_close_change",
        "normalized_broad_index_daily_change_table",
        "source_backed_market_driver_news_digest",
        "treasury_2y_same_day_value",
    ):
        expect(field not in missing, f"full recap gap should be closed: {field}", errors)

    levels = payload.get("market_levels", {})
    expect(levels.get("spx_cash", {}).get("available") is True, "SPX cash should be available", errors)
    expect(levels.get("spx_cash", {}).get("change_pct") is not None, "SPX same-day change_pct should be available", errors)
    expect(levels.get("dow_cash", {}).get("available") is True, "Dow should be available", errors)
    expect(levels.get("dow_cash", {}).get("change_pct") is not None, "Dow same-day change_pct should be available", errors)
    expect(levels.get("nasdaq_composite_cash", {}).get("available") is True, "Nasdaq Composite should be available", errors)
    expect(levels.get("russell_2000_trend", {}).get("change") is not None, "Russell 2000 same-day point change should be available", errors)
    broad_table = payload.get("normalized_broad_index_daily_change_table") or []
    available_symbols = {row.get("normalized_symbol") for row in broad_table if isinstance(row, dict) and row.get("available") is True}
    for symbol in ("SPX", "DOW", "NASDAQ_COMPOSITE", "RUSSELL_2000"):
        expect(symbol in available_symbols, f"normalized broad-index table missing {symbol}", errors)
    rates = payload.get("rates_energy_fx", {})
    expect(rates.get("treasury_2y_pct") is not None, "2Y Treasury should be available", errors)
    expect(rates.get("treasury_2y_as_of") == payload.get("as_of", {}).get("market_state_last_trading_day"), "2Y Treasury should be same-day with market state", errors)
    digest = payload.get("source_backed_market_driver_news_digest") or []
    expect(bool(digest), "source-backed market driver digest missing", errors)
    expect(all(row.get("source_refs") for row in digest if isinstance(row, dict)), "every driver digest row needs source_refs", errors)
    expect(bool(payload.get("sector_moves")), "sector moves missing", errors)
    expect("full broad-index close/change and source-backed driver digest available locally" in (payload.get("local_answer_summary") or ""), "summary should disclose full recap readiness", errors)

    if errors:
        print("market_today_answer_packet_tests_failed")
        for error in errors:
            print(f"- {error}")
        return 1
    print("market_today_answer_packet_tests_passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
