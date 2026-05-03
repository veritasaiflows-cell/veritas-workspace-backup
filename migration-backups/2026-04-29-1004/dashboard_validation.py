from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from dashboard_core import (
    TMP,
    SEVERITY_ORDER,
    load_json,
    normalize_records,
    parse_date,
    get_path,
    status_worse,
)

BAND_PROPOSALS_PATH = TMP / "band-proposals.json"


def build_validation(
    sources: dict[str, dict | None],
    source_status: dict[str, dict[str, Any]],
    technical_rows: list[dict[str, Any]],
    sector_weights: dict[str, float],
    last_trade_dt: datetime,
) -> dict[str, Any]:
    tech_raw = sources["technical"] or {}
    deploy_raw = sources["deployment"] or {}
    earn_raw = sources["earnings"] or {}
    pf_raw = sources["portfolio"] or {}

    warnings: list[dict[str, Any]] = []

    def add_warning(code: str, severity: str, scope: str, message: str, ticker: str | None = None, details: dict[str, Any] | None = None) -> None:
        warning = {
            "code": code,
            "severity": severity,
            "scope": scope,
            "message": message,
        }
        if ticker:
            warning["ticker"] = ticker
        if details:
            warning["details"] = details
        warnings.append(warning)

    deploy_by_ticker = {r.get("ticker"): r for r in normalize_records(deploy_raw.get("records"))}
    summary = deploy_raw.get("summary", {}) if isinstance(deploy_raw.get("summary"), dict) else {}
    entry_bands = (pf_raw or {}).get("entry_bands", {})
    tracked_universe = (pf_raw or {}).get("tracked_universe", {})
    risk_thresholds = (pf_raw or {}).get("risk_thresholds", {})
    portfolio = (pf_raw or {}).get("portfolio", {})
    posture_labels = (pf_raw or {}).get("posture_labels", {})

    # Priority 2.5: Move posture expectations to config
    posture_expectations = (pf_raw or {}).get("posture_expectations")
    if not posture_expectations:
        posture_expectations = {
            "above all MAs -- bullish 20>50>200 stack": {"above20": True, "above50": True, "above200": True, "close_vs": ["ma20", "ma50", "ma200"]},
            "above all MAs": {"above20": True, "above50": True, "above200": True, "close_vs": ["ma20", "ma50", "ma200"]},
            "above 20d and 50d, below 200d": {"above20": True, "above50": True, "above200": False},
            "above 200d, below 20d and 50d": {"above20": False, "above50": False, "above200": True},
            "below all MAs": {"above20": False, "above50": False, "above200": False, "close_vs_below": ["ma20", "ma50", "ma200"]},
        }

    for row in technical_rows:
        ticker = row["ticker"]
        posture_key = row["raw_ma_posture"]
        expectation = posture_expectations.get(posture_key)
        if expectation:
            for field in ("above20", "above50", "above200"):
                if field in expectation and row.get(field) is not None and row.get(field) != expectation[field]:
                    add_warning(
                        "ma_posture_flag_mismatch",
                        "critical",
                        "technical",
                        f"{ticker} posture disagrees with MA flags",
                        ticker,
                        {"posture": posture_key, field: row.get(field), "expected": expectation[field]},
                    )
            for ma_field in expectation.get("close_vs", []):
                ma_value = row.get(ma_field)
                close = row.get("close")
                if ma_value is not None and close is not None and close < ma_value:
                    add_warning(
                        "close_below_claimed_ma",
                        "critical",
                        "technical",
                        f"{ticker} is labeled above {ma_field} but close is below that average",
                        ticker,
                        {"close": close, ma_field: ma_value},
                    )
            for ma_field in expectation.get("close_vs_below", []):
                ma_value = row.get(ma_field)
                close = row.get("close")
                if ma_value is not None and close is not None and close > ma_value:
                    add_warning(
                        "close_above_claimed_ma",
                        "critical",
                        "technical",
                        f"{ticker} is labeled below all MAs but close is above {ma_field}",
                        ticker,
                        {"close": close, ma_field: ma_value},
                    )

        band = entry_bands.get(ticker, {})
        meta = tracked_universe.get(ticker, {}) if isinstance(tracked_universe, dict) else {}
        band_low, band_high, stop_val = band.get("low"), band.get("high"), band.get("stop")
        close = row.get("close")
        computed_in_band = None
        if close is not None and band_low is not None and band_high is not None:
            computed_in_band = band_low <= close <= band_high
            if row.get("inBand") is not None and row.get("inBand") != computed_in_band:
                add_warning(
                    "entry_band_mismatch",
                    "critical",
                    "technical",
                    f"{ticker} inBand flag disagrees with configured band math",
                    ticker,
                    {"close": close, "band_low": band_low, "band_high": band_high, "inBand": row.get("inBand")},
                )
        elif row.get("inBand"):
            add_warning(
                "entry_band_without_numeric_band",
                "warning",
                "technical",
                f"{ticker} shows in-band state without numeric band bounds in portfolio config",
                ticker,
            )

        if close is not None and stop_val is not None and row.get("belowStop") is not None:
            computed_below_stop = close < stop_val
            if row.get("belowStop") != computed_below_stop:
                add_warning(
                    "below_stop_mismatch",
                    "critical",
                    "technical",
                    f"{ticker} belowStop flag disagrees with configured stop",
                    ticker,
                    {"close": close, "stop": stop_val, "belowStop": row.get("belowStop")},
                )

        if meta:
            coverage_tier = meta.get("coverage_tier")
            workflow_state = meta.get("workflow_state")
            if coverage_tier == "daily" and ticker not in entry_bands:
                add_warning(
                    "missing_entry_band_config",
                    "warning",
                    "config",
                    f"{ticker} is in daily coverage but missing entry-band config entry",
                    ticker,
                )
            if workflow_state == "REPAIR" and row.get("blocked"):
                add_warning(
                    "repair_mode_vs_block_flag",
                    "warning",
                    "config",
                    f"{ticker} is marked repair-mode in config but still shows earnings-blocked in technical output",
                    ticker,
                )
            if coverage_tier != "daily" and ticker in deploy_by_ticker:
                add_warning(
                    "non_daily_in_deployment_flow",
                    "warning",
                    "config",
                    f"{ticker} appears in deployment flow despite non-daily coverage tier {coverage_tier}",
                    ticker,
                )

        deploy = deploy_by_ticker.get(ticker)
        if not deploy:
            add_warning("missing_deployment_record", "warning", "deployment", f"{ticker} has technical coverage but no deployment record", ticker)
            continue

        action_state = deploy.get("action_state")
        if row.get("belowStop") and action_state != "BELOW STOP":
            add_warning(
                "state_vs_stop_conflict",
                "critical",
                "deployment",
                f"{ticker} is below stop but deployment state is {action_state}",
                ticker,
            )
        if row.get("blocked") and action_state not in {"BLOCKED", "BELOW STOP"}:
            add_warning(
                "state_vs_blocker_conflict",
                "warning",
                "deployment",
                f"{ticker} is earnings-blocked but deployment state is {action_state}",
                ticker,
            )
        if computed_in_band and action_state in {"WATCH", "UNKNOWN"}:
            add_warning(
                "state_vs_entry_band_conflict",
                "warning",
                "deployment",
                f"{ticker} is in band but deployment state remains {action_state}",
                ticker,
            )

        earnings_date = row.get("earningsDate")
        earnings_dt = parse_date(earnings_date)
        if earnings_date and earnings_dt and earnings_dt.date() < (last_trade_dt.date() - timedelta(days=1)):
            action_state_upper = str(action_state).upper() if action_state else ""
            if action_state_upper not in {"WATCH", "WATCH / RESEARCH NEEDED"}:
                add_warning(
                    "earnings_date_in_past",
                    "warning",
                    "earnings",
                    f"{ticker} earnings date {earnings_date} is already in the past and may need roll-forward confirmation",
                    ticker,
                )
        if row.get("blocked") and row.get("daysToEarnings") is not None and row.get("daysToEarnings") > 14:
            add_warning(
                "earnings_block_window_unexpected",
                "warning",
                "earnings",
                f"{ticker} is blocked even though earnings are more than 14 days away",
                ticker,
                {"daysToEarnings": row.get("daysToEarnings")},
            )

    # deployment summary vs records
    summary_expected = {
        "deployable": "DEPLOYABLE",
        "almost": "ALMOST",
        "blocked": "BLOCKED",
        "below_stop": "BELOW STOP",
        "bench": "BENCH",
        "watch": "WATCH",
        "error": "ERROR",
    }
    counts = {key: 0 for key in summary_expected}
    for record in normalize_records(deploy_raw.get("records")):
        state = record.get("action_state")
        for key, expected_state in summary_expected.items():
            if state == expected_state:
                counts[key] += 1
    for key, expected_state in summary_expected.items():
        listed = summary.get(key, []) if isinstance(summary.get(key, []), list) else []
        if len(listed) != counts[key]:
            add_warning(
                "deployment_summary_mismatch",
                "warning",
                "deployment",
                f"Deployment summary {key} count does not match record states for {expected_state}",
                details={"summary_count": len(listed), "record_count": counts[key]},
            )

    # portfolio math and concentration
    sleeves = portfolio.get("core", []) + portfolio.get("tactical", []) + portfolio.get("speculative", [])
    invested = round(sum((p.get("weight") or 0) for p in sleeves), 2)
    cash = round(float(portfolio.get("cash") or 0), 2)
    total = round(invested + cash, 2)
    if abs(total - 100.0) > 0.25:
        add_warning(
            "portfolio_total_not_100",
            "critical",
            "portfolio",
            f"Portfolio weights plus cash sum to {total}%, not 100%",
            details={"invested": invested, "cash": cash},
        )

    max_single_normal = risk_thresholds.get("max_single_position_normal")
    max_sector = risk_thresholds.get("max_sector_pct")
    if max_single_normal is not None:
        for position in sleeves:
            weight = position.get("weight")
            ticker = position.get("ticker")
            if weight is not None and weight > max_single_normal:
                add_warning(
                    "single_position_limit_exceeded",
                    "warning",
                    "portfolio",
                    f"{ticker} weight {weight}% exceeds normal single-position threshold {max_single_normal}%",
                    ticker,
                )
    if max_sector is not None:
        for sector, weight in sector_weights.items():
            if weight > max_sector:
                add_warning(
                    "sector_concentration_exceeded",
                    "warning",
                    "portfolio",
                    f"{sector} concentration {weight}% exceeds max sector threshold {max_sector}%",
                    details={"sector": sector, "weight": weight},
                )

    # timing-sensitive governance
    earnings_status = source_status.get("earnings", {})
    if "timing_sensitive" in earnings_status.get("tags", []):
        add_warning(
            "timing_sensitive_earnings_dates",
            "warning",
            "earnings",
            "One or more timing-critical earnings dates changed and still need direct confirmation",
        )
    market_status = source_status.get("market", {})
    if "macro_manual_dependency" in market_status.get("tags", []):
        add_warning(
            "macro_manual_dependency",
            "warning",
            "macro",
            "Macro payload still depends on manual Fed target maintenance or missing FedWatch confirmation",
        )

    # band staleness — loaded directly here; not routed through load_sources()
    # to avoid polluting the source_status loop (assess_source requires SOURCE_SPECS entry)
    band_proposals_raw = load_json(BAND_PROPOSALS_PATH) or {}
    band_summary = band_proposals_raw.get("summary") or {}
    needs_review_tickers = band_summary.get("needs_review_tickers") or []
    if needs_review_tickers:
        add_warning(
            "band_staleness",
            "warning",
            "bands",
            f"{len(needs_review_tickers)} entry band(s) need review: "
            f"{', '.join(needs_review_tickers)}. "
            f"Run apply_band_update.py to review and apply proposed levels.",
        )
    elif band_proposals_raw and band_proposals_raw.get("status") == "ok":
        pass
    elif not band_proposals_raw:
        add_warning(
            "band_proposals_missing",
            "warning",
            "bands",
            "tmp/band-proposals.json not found. Run band_refresh.py to generate band staleness proposals.",
        )

    warnings.sort(key=lambda item: (-SEVERITY_ORDER[item["severity"]], item["scope"], item.get("ticker", ""), item["code"]))
    summary_counts = {"critical": 0, "warning": 0, "info": 0}
    for warning in warnings:
        summary_counts[warning["severity"]] += 1

    overall = "clean"
    if summary_counts["critical"]:
        overall = "critical"
    elif summary_counts["warning"]:
        overall = "warning"

    return {
        "overall": overall,
        "summary": summary_counts,
        "warnings": warnings,
    }
