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
    sql_context = payload.get("sql_canon_context", {})
    sql_validation = sql_context.get("validation", {})
    payload_errors = payload.get("validation", {}).get("errors") or []
    expect(sql_context.get("status") == "ok", "SQL-canon guard should be ok", errors)
    expect(sql_context.get("production_answer_count") is not None, "SQL-canon production count missing", errors)
    expect(sql_context.get("legacy_production_answer_count") is not None, "SQL-canon legacy production count missing", errors)
    expect("sql_canon_guard_blocked" not in payload_errors, "empty SQL-canon production scope must not block market recap", errors)
    if sql_context.get("production_answer_count") == 0:
        expect(
            "production_answer_set_empty_fail_closed" in (sql_validation.get("warnings") or []),
            "empty SQL-canon production scope should be warning-only fail-closed state",
            errors,
        )
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

    negative_contained = packet.classify_cpi_driver(
        {
            "all_items_mom_pct": -0.4,
            "core_mom_pct": 0.0,
            "energy_mom_pct": -5.7,
            "gasoline_mom_pct": -9.7,
        }
    )
    expect(
        negative_contained is not None and negative_contained.get("driver_id") == "cpi_monthly_contained",
        "negative energy/gasoline evidence must classify as monthly contained",
        errors,
    )
    positive_pressure = packet.classify_cpi_driver(
        {
            "all_items_mom_pct": 0.5,
            "core_mom_pct": 0.2,
            "energy_mom_pct": 3.9,
            "gasoline_mom_pct": 7.0,
        }
    )
    expect(
        positive_pressure is not None
        and positive_pressure.get("driver_id") == "cpi_energy_gasoline_headline_pressure",
        "positive gasoline impulse should classify as energy/gasoline headline pressure",
        errors,
    )
    positive_gasoline_contained_headline = packet.classify_cpi_driver(
        {
            "all_items_mom_pct": 0.1,
            "core_mom_pct": 0.1,
            "energy_mom_pct": 2.0,
            "gasoline_mom_pct": 4.0,
        }
    )
    expect(
        positive_gasoline_contained_headline is not None
        and positive_gasoline_contained_headline.get("driver_id") == "cpi_monthly_contained",
        "positive gasoline alone cannot imply headline pressure when headline and core are contained",
        errors,
    )
    current_cpi = payload.get("macro_events", {}).get("cpi_release", {})
    if (
        current_cpi.get("energy_mom_pct") is not None
        and current_cpi.get("gasoline_mom_pct") is not None
        and current_cpi.get("energy_mom_pct") < 0
        and current_cpi.get("gasoline_mom_pct") < 0
    ):
        current_macro_ids = {
            row.get("driver_id")
            for row in digest
            if isinstance(row, dict) and row.get("driver_type") == "macro_release"
        }
        expect(
            "cpi_energy_gasoline_headline_pressure" not in current_macro_ids,
            "negative current energy CPI cannot emit a positive gasoline-pressure claim",
            errors,
        )

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
