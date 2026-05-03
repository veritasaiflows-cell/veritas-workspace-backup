from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
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
import universe

BAND_PROPOSALS_PATH = TMP / "band-proposals.json"
WORKSPACE = TMP.parent
WATCHLIST_PATH = WORKSPACE / "02. Markets" / "Watchlist.md"
COVERAGE_UNIVERSE_PATH = WORKSPACE / "04. Research" / "Coverage Universe.md"
POLICY_MANUAL_NOTE_PATHS = [
    WORKSPACE / "01. Dashboards" / "Executive Brief.md",
    WORKSPACE / "01. Dashboards" / "Next Actions.md",
    WORKSPACE / "02. Markets" / "Macro Regime Dashboard.md",
    WORKSPACE / "03. Portfolio" / "Technical Entry and Invalidation Sheet.md",
    WORKSPACE / "05. Intelligence" / "Weekly Positioning Review.md",
]
POLICY_MANUAL_STALE_PHRASES = [
    "manual target-range maintenance",
    "manual dependencies",
    "still-manual policy layer",
]


def _read_note_text(path: Path) -> str:
    for encoding in ("utf-8", "cp1252"):
        try:
            return path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue
    return path.read_text(encoding="utf-8", errors="ignore")


def _extract_table_rows(text: str, header: str) -> list[list[str]]:
    lines = text.splitlines()
    for idx, line in enumerate(lines):
        if line.strip() != header:
            continue
        rows: list[list[str]] = []
        for row_line in lines[idx + 2:]:
            stripped = row_line.strip()
            if not stripped.startswith("|"):
                break
            cells = [cell.strip() for cell in stripped.strip("|").split("|")]
            rows.append(cells)
        return rows
    return []


def _parse_watchlist_rows() -> dict[str, dict[str, str]]:
    rows = _extract_table_rows(
        _read_note_text(WATCHLIST_PATH),
        "| Ticker | Sector | Coverage Tier | Current Deployment State | Canonical Source |",
    )
    out: dict[str, dict[str, str]] = {}
    for cells in rows:
        if len(cells) < 5:
            continue
        out[cells[0]] = {
            "sector": cells[1],
            "coverage_tier": cells[2],
            "current_state": cells[3],
            "canonical_source": cells[4],
        }
    return out


def _parse_coverage_quick_reference() -> dict[str, dict[str, str]]:
    rows = _extract_table_rows(
        _read_note_text(COVERAGE_UNIVERSE_PATH),
        "| Ticker | Sector | Tier | Status |",
    )
    out: dict[str, dict[str, str]] = {}
    for cells in rows:
        if len(cells) < 4:
            continue
        out[cells[0]] = {
            "sector": cells[1],
            "tier": cells[2],
            "status": cells[3],
        }
    return out


def build_validation(
    sources: dict[str, dict | None],
    source_status: dict[str, dict[str, Any]],
    technical_rows: list[dict[str, Any]],
    sector_weights: dict[str, float],
    last_trade_dt: datetime,
) -> dict[str, Any]:
    policy_raw = sources["policy"] or {}
    credit_raw = sources.get("credit") or {}
    breadth_raw = sources.get("breadth") or {}
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

    def band_review_is_blocking(proposal: dict[str, Any], threshold: float) -> bool:
        if not proposal.get("needs_review") or proposal.get("skip_reason"):
            return False

        entry_policy = proposal.get("entry_policy")

        if any(proposal.get(field) is None for field in ("current_band_low", "current_band_high", "current_stop")):
            return entry_policy == "band_defined"

        if any(proposal.get(field) is None for field in ("suggested_band_low", "suggested_band_high", "suggested_stop")):
            return entry_policy == "band_defined"

        trading_days_old = proposal.get("trading_days_old")
        stale_threshold = band_proposals_raw.get("stale_threshold_trading_days", 7)
        if trading_days_old is not None and trading_days_old > stale_threshold:
            return True

        ma20_vs_mid = proposal.get("ma20_vs_band_midpoint_pct")
        if ma20_vs_mid is not None and abs(float(ma20_vs_mid)) > float(threshold):
            return True

        return False

    deploy_by_ticker = {r.get("ticker"): r for r in normalize_records(deploy_raw.get("records"))}
    trigger_raw = load_json(TMP / "trigger-sheet.json") or {}
    trigger_tickers = {r.get("ticker") for r in normalize_records(trigger_raw.get("records")) if r.get("ticker")}
    trigger_by_ticker = {r.get("ticker"): r for r in normalize_records(trigger_raw.get("records")) if r.get("ticker")}
    summary = deploy_raw.get("summary", {}) if isinstance(deploy_raw.get("summary"), dict) else {}
    entry_bands = (pf_raw or {}).get("entry_bands", {})
    tracked_universe = (pf_raw or {}).get("tracked_universe", {})
    risk_thresholds = (pf_raw or {}).get("risk_thresholds", {})
    portfolio = (pf_raw or {}).get("portfolio", {})
    posture_labels = (pf_raw or {}).get("posture_labels", {})
    watchlist_rows = _parse_watchlist_rows()
    coverage_rows = _parse_coverage_quick_reference()

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
            lane = universe.resolve_lane(ticker, meta)
            if universe.is_entitled(ticker, meta, "deployment_ranking") and ticker not in entry_bands:
                add_warning(
                    "missing_entry_band_config",
                    "warning",
                    "config",
                    f"{ticker} is execution-entitled but missing entry-band config entry",
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
            if not universe.is_entitled(ticker, meta, "deployment_ranking") and ticker in trigger_tickers:
                add_warning(
                    "non_daily_in_deployment_flow",
                    "warning",
                    "config",
                    f"{ticker} leaked into execution trigger surfaces despite {lane} lane / {coverage_tier or 'unlabeled-tier'} coverage",
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
        if computed_in_band and action_state in {"WATCH", "UNKNOWN"} and meta and universe.is_entitled(ticker, meta, "deployment_ranking"):
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
            "Macro payload still depends on manual Fed target maintenance or other policy-layer caution flags.",
        )
    policy_status = source_status.get("policy", {})
    if policy_status.get("status") == "missing":
        add_warning(
            "policy_expectations_missing",
            "warning",
            "policy",
            "tmp/policy-expectations.json is missing. Run policy_expectations_refresh.py before trusting policy-readiness views.",
        )
    elif policy_status.get("status") == "stale":
        add_warning(
            "policy_expectations_stale",
            "warning",
            "policy",
            "Policy expectations artifact is stale relative to its freshness window.",
        )

    if policy_status.get("raw_status") == "partial":
        add_warning(
            "policy_expectations_partial",
            "warning",
            "policy",
            "Policy expectations artifact is partial and should not be treated as decision-grade.",
        )

    if "policy_manual_dependency" in policy_status.get("tags", []) or policy_status.get("raw_status") == "manual":
        add_warning(
            "policy_expectations_manual_dependency",
            "warning",
            "policy",
            "Policy expectations still rely on manual target-range constants and require explicit review.",
        )

    policy_warnings = policy_raw.get("warnings", []) if isinstance(policy_raw.get("warnings"), list) else []
    if get_path(policy_raw, "data.implied_rate_source_mode") == "fallback_proxy":
        add_warning(
            "policy_expectations_fallback_source",
            "warning",
            "policy",
            "Policy expectations are currently using the generic ZQ=F front-contract proxy because the contract-specific ZQ quote was unavailable.",
        )

    # credit spread warnings
    credit_status = source_status.get("credit", {})
    if credit_status.get("status") == "missing":
        add_warning(
            "credit_spreads_missing",
            "warning",
            "macro",
            "tmp/credit-spreads.json is missing. Run credit_spread_refresh.py before trusting macro-regime or deployment views.",
        )
    elif credit_status.get("status") == "stale":
        add_warning(
            "credit_spreads_stale",
            "warning",
            "macro",
            f"Credit spreads artifact is stale (age {credit_status.get('age_h')}h). Refresh before regime-sensitive decisions.",
        )
    if credit_status.get("raw_status") == "partial":
        add_warning(
            "credit_spreads_partial",
            "warning",
            "macro",
            "Credit spreads artifact is partial; one or more required fields are missing or estimated.",
        )
    if "fallback_proxy_only" in credit_status.get("tags", []):
        add_warning(
            "credit_spreads_fallback_proxy_only",
            "warning",
            "macro",
            "Credit spreads are running on proxy basket only (HYG/JNK/LQD). Direct FRED OAS series unavailable.",
        )

    # breadth warnings
    breadth_status = source_status.get("breadth", {})
    if breadth_status.get("status") == "missing":
        add_warning(
            "breadth_state_missing",
            "warning",
            "macro",
            "tmp/breadth-state.json is missing. Run breadth_refresh.py before trusting deployment trust or regime views.",
        )
    elif breadth_status.get("status") == "stale":
        add_warning(
            "breadth_state_stale",
            "warning",
            "macro",
            f"Market breadth artifact is stale (age {breadth_status.get('age_h')}h). Refresh before session-level deployment decisions.",
        )
    if breadth_status.get("raw_status") == "partial":
        add_warning(
            "breadth_state_partial",
            "warning",
            "macro",
            "Market breadth artifact is partial; some required breadth fields are missing or estimated.",
        )
    if "narrow_participation" in breadth_status.get("tags", []):
        breadth_data = breadth_raw.get("data", {}) if isinstance(breadth_raw.get("data"), dict) else {}
        regime_label = (breadth_data.get("major_index_breadth") or {}).get("breadth_regime", "unknown")
        add_warning(
            "breadth_state_narrow_participation",
            "warning",
            "macro",
            f"Breadth regime is {regime_label}. Index-level strength may not reflect broad participation. Deployment confidence should be lower.",
        )

    # band staleness — loaded directly here; not routed through load_sources()
    # to avoid polluting the source_status loop (assess_source requires SOURCE_SPECS entry)
    band_proposals_raw = load_json(BAND_PROPOSALS_PATH) or {}
    band_summary = band_proposals_raw.get("summary") or {}
    blocking_review_tickers = band_summary.get("blocking_review_tickers") or []
    if not blocking_review_tickers:
        price_drift_threshold = band_proposals_raw.get("price_drift_threshold_pct", 5.0)
        blocking_review_tickers = [
            proposal.get("ticker")
            for proposal in band_proposals_raw.get("proposals", []) or []
            if isinstance(proposal, dict) and proposal.get("ticker") and band_review_is_blocking(proposal, price_drift_threshold)
        ]
    if blocking_review_tickers:
        add_warning(
            "band_staleness",
            "warning",
            "bands",
            f"{len(blocking_review_tickers)} entry band(s) still have blocking review debt: "
            f"{', '.join(blocking_review_tickers)}. "
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

    for ticker, meta in tracked_universe.items():
        if not isinstance(meta, dict):
            continue
        lane = universe.resolve_lane(ticker, meta)
        action_state = str((trigger_by_ticker.get(ticker) or {}).get("action_state") or "").upper()
        entry_policy = meta.get("entry_policy")

        watch_row = watchlist_rows.get(ticker)
        if lane == "execution" and not watch_row:
            add_warning(
                "watchlist_execution_missing",
                "warning",
                "notes",
                f"{ticker} is execution-lane in config but missing from the Watchlist mirror table.",
                ticker,
            )
        elif watch_row and action_state == "DEPLOYABLE NOW":
            state_text = watch_row.get("current_state", "").lower()
            if "not intentionally promoted yet" in state_text:
                add_warning(
                    "watchlist_stale_intent_phrase",
                    "warning",
                    "notes",
                    f"{ticker} still reads as an unpromoted watch name in Watchlist despite deployable-now trigger state.",
                    ticker,
                )

        coverage_row = coverage_rows.get(ticker)
        if coverage_row and action_state in {"DEPLOYABLE NOW", "ALMOST", "ALMOST DEPLOYABLE"} and entry_policy == "band_defined":
            status_text = coverage_row.get("status", "").lower()
            if "no levels yet" in status_text:
                add_warning(
                    "coverage_quickref_stale_levels_phrase",
                    "warning",
                    "notes",
                    f"{ticker} quick-reference status still says no levels yet even though a band-defined setup exists.",
                    ticker,
                )
            if "earnings apr 29" in status_text or "requalification" in status_text:
                add_warning(
                    "coverage_quickref_stale_event_phrase",
                    "warning",
                    "notes",
                    f"{ticker} quick-reference status still carries stale event wording that no longer matches the current owner surfaces.",
                    ticker,
                )

    policy_manual_dependencies = get_path(policy_raw, "data.manual_dependencies") or []
    policy_is_non_manual = (
        policy_status.get("raw_status") not in {"manual", "partial"}
        and "policy_manual_dependency" not in policy_status.get("tags", [])
        and isinstance(policy_manual_dependencies, list)
        and not policy_manual_dependencies
    )
    if policy_is_non_manual:
        for note_path in POLICY_MANUAL_NOTE_PATHS:
            note_text = _read_note_text(note_path).lower()
            for phrase in POLICY_MANUAL_STALE_PHRASES:
                if phrase in note_text:
                    add_warning(
                        "policy_manual_phrase_stale_in_note",
                        "warning",
                        "notes",
                        f"{note_path.relative_to(WORKSPACE)} still carries stale manual-policy wording ('{phrase}') even though the live policy artifact is no longer in manual mode.",
                    )
                    break

    consistency_raw = load_json(TMP / "universe-consistency.json") or {}
    if consistency_raw.get("status") == "error":
        for err in consistency_raw.get("warnings", []):
            add_warning(
                "universe_consistency_broken",
                "critical",
                "config",
                f"Universe contract broken: {err}",
            )
    elif not consistency_raw:
        add_warning(
            "universe_consistency_missing",
            "warning",
            "config",
            "tmp/universe-consistency.json not found. Run universe_consistency_check.py before publication.",
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
