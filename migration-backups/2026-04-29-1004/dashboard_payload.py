from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from dashboard_core import (
    TMP,
    WORKSPACE,
    load_json,
    write_json,
    parse_date,
    get_path,
    normalize_records,
    get_market_session,
    assess_source,
    build_provenance,
    get_vault_freshness,
    status_worse,
    status_badge,
    fmt_num,
    fmt_pct,
    fmt_date_label,
    describe_overall_status,
)
from dashboard_validation import build_validation

HISTORY_PATH = TMP / "deployment-history.json"
ENTRY_BAND_REPORTS_DIR = WORKSPACE / "generated documents" / "entry-bands"
NEAR_BAND_THRESHOLD_PCT = 5.0


def _compute_band_status(
    close: float | None,
    band_low: float | None,
    band_high: float | None,
    in_band: bool | None,
    below_stop: bool | None,
) -> tuple[str, float | None]:
    if close is None:
        return "NO DATA", None
    if below_stop:
        return "BELOW STOP", None
    if in_band:
        return "IN BAND", None
    if band_low is None or band_high is None:
        return "NO BAND", None
    dist_pct = round((close - band_high) / band_high * 100, 2)
    if close < band_low:
        return "BELOW BAND", dist_pct
    if dist_pct <= NEAR_BAND_THRESHOLD_PCT:
        return "NEAR BAND", dist_pct
    return "ABOVE BAND", dist_pct


def update_history(payload: dict[str, Any]) -> list[dict[str, Any]]:
    history = []
    if HISTORY_PATH.exists():
        try:
            history = json.loads(HISTORY_PATH.read_text(encoding="utf-8"))
        except Exception:
            history = []

    history.append({
        "generated_at": payload["generated_at"],
        "technical": [
            {
                "ticker": t["ticker"],
                "actionState": t["actionState"],
                "close": t["close"],
                "inBand": t.get("inBand"),
                "blocked": t.get("blocked"),
                "belowStop": t.get("belowStop"),
            }
            for t in payload.get("technical", [])
        ]
    })

    if len(history) > 50:
        history = history[-50:]

    write_json(HISTORY_PATH, history)
    return history


def compute_delta(current: dict[str, Any], previous: dict[str, Any] | None) -> dict[str, Any]:
    gen_at = current.get("generated_at", "")
    if previous is None:
        return {
            "generated_at": gen_at,
            "compared_to": None,
            "first_run": True,
            "changes": [],
            "summary": "First run, no prior snapshot to compare.",
        }

    changes: list[dict[str, Any]] = []
    cur_tech = {t["ticker"]: t for t in current.get("technical", [])}
    prev_tech = {t["ticker"]: t for t in previous.get("technical", [])}

    for ticker, ct in cur_tech.items():
        pt = prev_tech.get(ticker)
        if not pt:
            changes.append({"type": "new_ticker", "ticker": ticker})
            continue
        if ct.get("actionState") != pt.get("actionState"):
            changes.append({"type": "action_state_change", "ticker": ticker, "from": pt.get("actionState"), "to": ct.get("actionState")})
        if ct.get("belowStop") and not pt.get("belowStop"):
            changes.append({"type": "below_stop_entered", "ticker": ticker})
        elif not ct.get("belowStop") and pt.get("belowStop"):
            changes.append({"type": "below_stop_exited", "ticker": ticker})
        if ct.get("blocked") and not pt.get("blocked"):
            changes.append({"type": "new_blocker", "ticker": ticker})
        elif not ct.get("blocked") and pt.get("blocked"):
            changes.append({"type": "blocker_cleared", "ticker": ticker})

        cur_gap = ct.get("bandGapDollar")
        prev_gap = pt.get("bandGapDollar")
        if cur_gap is not None and prev_gap is not None:
            was_in = prev_gap <= 0
            now_in = cur_gap <= 0
            if now_in and not was_in:
                changes.append({"type": "entered_band", "ticker": ticker})
            elif was_in and not now_in:
                changes.append({"type": "exited_band", "ticker": ticker})

        if ct.get("earningsDate") != pt.get("earningsDate") and ct.get("earningsDate"):
            changes.append({"type": "earnings_date_change", "ticker": ticker, "from": pt.get("earningsDate"), "to": ct.get("earningsDate")})

    cur_sources = {f["label"]: f["status"] for f in current.get("trust", {}).get("sources", [])}
    prev_sources = {f["label"]: f["status"] for f in previous.get("trust", {}).get("sources", [])}
    for label, status in cur_sources.items():
        prior = prev_sources.get(label)
        if prior and prior != status:
            changes.append({"type": "source_status_change", "source": label, "from": prior, "to": status})

    if current.get("exec_freshness") != previous.get("exec_freshness"):
        changes.append({"type": "exec_freshness_change", "from": previous.get("exec_freshness"), "to": current.get("exec_freshness")})

    counts: dict[str, int] = {}
    for change in changes:
        counts[change["type"]] = counts.get(change["type"], 0) + 1
    parts = []
    summary_specs = [
        ("new_ticker", "new ticker(s) on the board"),
        ("action_state_change", "action state change(s)"),
        ("earnings_date_change", "earnings date shift(s)"),
        ("source_status_change", "source status change(s)"),
        ("exec_freshness_change", "exec-freshness change(s)"),
        ("new_blocker", "new blocker(s)"),
        ("blocker_cleared", "blocker(s) cleared"),
        ("below_stop_entered", "below-stop entry(ies)"),
        ("below_stop_exited", "below-stop exit(s)"),
        ("entered_band", "band entry(ies)"),
        ("exited_band", "band exit(s)"),
    ]
    enumerated_keys = {key for key, _ in summary_specs}
    for key, label in summary_specs:
        if counts.get(key):
            parts.append(f"{counts[key]} {label}")
    # Safety net: never claim "No material changes" while changes is non-empty.
    unenumerated = [c for c in changes if c["type"] not in enumerated_keys]
    if unenumerated:
        parts.append(f"{len(unenumerated)} other change(s)")
    if not changes:
        parts.append("No material changes")
    elif not parts:
        parts.append(f"{len(changes)} change(s) detected")

    return {
        "generated_at": gen_at,
        "compared_to": previous.get("generated_at"),
        "first_run": False,
        "changes": changes,
        "summary": "; ".join(parts),
    }


def build_payload(sources: dict[str, dict | None]) -> dict[str, Any]:
    print("generate_dashboard.py v5, assembling payload …")
    trigger_sheet_raw = load_json(TMP / "trigger-sheet.json") or {}
    post_earnings_raw = load_json(TMP / "post-earnings-prep.json") or {}

    market_raw = sources["market"] or {}
    tech_raw = sources["technical"] or {}
    deploy_raw = sources["deployment"] or {}
    earn_raw = sources["earnings"] or {}
    pf_raw = sources["portfolio"] or {}

    now = datetime.now(timezone.utc)
    market_session = get_market_session(now)
    source_status = {name: assess_source(name, src) for name, src in sources.items()}
    provenance = build_provenance(source_status)
    vault_freshness = get_vault_freshness()

    overall_status = "fresh"
    for name, info in source_status.items():
        if info["critical"]:
            overall_status = status_worse(overall_status, info["status"])
    exec_freshness = overall_status

    last_trade = tech_raw.get("last_trading_day") or market_raw.get("last_trading_day") or now.strftime("%Y-%m-%d")
    last_trade_dt = parse_date(last_trade) or now

    ms_data = market_raw.get("data", {})
    market = {
        "generated_at": market_raw.get("generated_at_utc"),
        "fed": {
            "target_low": get_path(ms_data, "fed.target_low"),
            "target_high": get_path(ms_data, "fed.target_high"),
            "cut_prob": get_path(ms_data, "fed.cut_probability_next_meeting"),
            "manual_update_required": get_path(ms_data, "fed.manual_update_required"),
        },
        "treasuries": {
            "y2": get_path(ms_data, "treasuries.2y"),
            "y10": get_path(ms_data, "treasuries.10y"),
            "m3": get_path(ms_data, "treasuries.3m_tbill"),
            "curve_2s10s": get_path(ms_data, "treasuries.curve_2s10s_bps"),
            "curve_3m10y": get_path(ms_data, "treasuries.curve_3m10y_bps"),
        },
        "vix": get_path(ms_data, "volatility.vix"),
        "spx": get_path(ms_data, "equities.spx"),
        "dxy": get_path(ms_data, "fx.dxy"),
        "brent": get_path(ms_data, "energy.brent"),
        "wti": get_path(ms_data, "energy.wti"),
        "warnings": list(dict.fromkeys(market_raw.get("warnings", []))),
    }

    entry_bands = pf_raw.get("entry_bands", {}) if isinstance(pf_raw.get("entry_bands"), dict) else {}
    posture_labels = pf_raw.get("posture_labels", {}) if isinstance(pf_raw.get("posture_labels"), dict) else {}
    deploy_by_ticker = {r.get("ticker"): r for r in normalize_records(deploy_raw.get("records"))}
    earnings_records = normalize_records(earn_raw.get("records"))
    earnings_by_ticker = {r.get("ticker"): r.get("next_earnings_date") for r in earnings_records if r.get("ticker")}

    technical: list[dict[str, Any]] = []
    for record in normalize_records(tech_raw.get("records")):
        ticker = record.get("ticker")
        band = entry_bands.get(ticker, {})
        band_low, band_high, stop_val = band.get("low"), band.get("high"), band.get("stop")
        close = record.get("close")

        band_gap_dollar = None
        band_gap_pct = None
        if close is not None and band_low is not None and band_high is not None and close != 0:
            if close > band_high:
                band_gap_dollar = round(close - band_high, 2)
            elif close < band_low:
                band_gap_dollar = round(close - band_low, 2)
            else:
                band_gap_dollar = 0.0
            band_gap_pct = round((band_gap_dollar / close) * 100, 2)

        stop_dist_pct = None
        if close is not None and stop_val is not None and close > 0:
            stop_dist_pct = round(((close - stop_val) / close) * 100, 2)

        earnings_date = earnings_by_ticker.get(ticker)
        earnings_dt = parse_date(earnings_date)
        days_to_earnings = (earnings_dt.date() - last_trade_dt.date()).days if earnings_dt else None

        deploy = deploy_by_ticker.get(ticker)
        action_state = deploy.get("action_state") if deploy else "UNKNOWN"
        action_reason = deploy.get("reason") if deploy else "No deployment record found"
        priority = deploy.get("priority") if deploy else 99

        trigger_ready = bool(
            exec_freshness in {"fresh", "usable_with_caution"}
            and band_gap_dollar is not None
            and band_gap_dollar <= 0
            and not record.get("earnings_blocked")
            and not record.get("below_stop")
            and action_state in {"DEPLOYABLE", "ALMOST", "BENCH"}
        )

        band_status, band_dist_pct = _compute_band_status(
            close, band_low, band_high,
            record.get("in_entry_band"), record.get("below_stop"),
        )
        report_file = ENTRY_BAND_REPORTS_DIR / f"{ticker}_entry_band.html"
        entry_band_report_path = (
            f"../generated documents/entry-bands/{ticker}_entry_band.html"
            if report_file.exists() else None
        )

        technical.append({
            "ticker": ticker,
            "close": close,
            "ma20": record.get("ma20"),
            "ma50": record.get("ma50"),
            "ma200": record.get("ma200"),
            "posture": posture_labels.get(record.get("ma_posture"), record.get("ma_posture")),
            "raw_ma_posture": record.get("ma_posture"),
            "above20": record.get("above_ma20"),
            "above50": record.get("above_ma50"),
            "above200": record.get("above_ma200"),
            "inBand": record.get("in_entry_band"),
            "belowStop": record.get("below_stop"),
            "blocked": record.get("earnings_blocked"),
            "entry": band.get("label", "TBD"),
            "stop": band.get("stop_label", "TBD"),
            "actionState": action_state,
            "actionReason": action_reason,
            "priority": priority,
            "bandGapDollar": band_gap_dollar,
            "bandGapPct": band_gap_pct,
            "stopDistPct": stop_dist_pct,
            "daysToEarnings": days_to_earnings,
            "earningsDate": earnings_date,
            "triggerToday": trigger_ready,
            "bandStatus": band_status,
            "bandDistPct": band_dist_pct,
            "entryBandReportPath": entry_band_report_path,
        })

    pf = pf_raw.get("portfolio", {}) if isinstance(pf_raw.get("portfolio"), dict) else {}
    sector_map = pf_raw.get("sector_map", {}) if isinstance(pf_raw.get("sector_map"), dict) else {}
    all_positions = pf.get("core", []) + pf.get("tactical", []) + pf.get("speculative", [])
    sector_weights: dict[str, float] = {}
    for sector, tickers in sector_map.items():
        weight = round(sum((p.get("weight") or 0) for p in all_positions if p.get("ticker") in tickers), 2)
        if weight > 0:
            sector_weights[sector] = weight

    validation = build_validation(sources, source_status, technical, sector_weights, last_trade_dt)

    manual_dependencies: list[dict[str, Any]] = []
    # Friendlier human labels and tone hints for the rendered Trust panel.
    dep_status_meta = {
        "manual":                {"label": "Manual",          "tone": "warn"},
        "unconfirmed":           {"label": "Unconfirmed",     "tone": "bad"},
        "unconfirmed_change":    {"label": "Date changed",    "tone": "bad"},
        "unconfirmed_addition":  {"label": "New on calendar", "tone": "warn"},
    }

    def _add_dep(label: str, scope: str, status: str, detail: str) -> None:
        meta = dep_status_meta.get(status, {"label": status, "tone": "bad"})
        manual_dependencies.append({
            "label": label,
            "scope": scope,
            "status": status,
            "statusLabel": meta["label"],
            "tone": meta["tone"],
            "detail": detail,
        })

    fed = get_path(market_raw, "data.fed") or {}
    if fed.get("manual_update_required"):
        _add_dep(
            "Fed target range",
            "Macro",
            "manual",
            "Update the hardcoded Fed target range in scripts/market_state_refresh.py after each FOMC decision.",
        )
    if fed.get("cut_probability_next_meeting") is None:
        _add_dep(
            "FedWatch cut probability",
            "Macro",
            "unconfirmed",
            "Keep this null until a stable CME FedWatch source is wired or manually verified in the note layer.",
        )
    for alert in earn_raw.get("watchlist_alerts", []):
        # Both DATE CHANGED and NEW alerts represent script/vault drift that the
        # operator needs to acknowledge. Distinct status values let the UI color
        # them differently (change vs addition) without losing the underlying detail.
        if "DATE CHANGED" in alert:
            _add_dep(alert.split(":", 1)[0], "Earnings timing", "unconfirmed_change", alert)
        elif "NEW" in alert:
            _add_dep(alert.split(":", 1)[0], "Earnings coverage", "unconfirmed_addition", alert)

    trust_sources = []
    for info in source_status.values():
        badge = status_badge(info["status"])
        trust_sources.append({
            "label": info["label"],
            "status": info["status"],
            "statusLabel": badge["label"],
            "tone": badge["tone"],
            "ageLabel": f"{info['age_h']}h" if info["age_h"] is not None else "Unavailable",
            "generatedLabel": info["generated_at"] or "Unavailable",
            "tags": info["tags"],
            "issues": info["issues"],
            "source": info["source"],
        })

    actionable = sorted(
        [row for row in technical if row["actionState"] in {"DEPLOYABLE", "ALMOST"}],
        key=lambda row: (row.get("priority", 99), abs(row.get("bandGapPct") or 999)),
    )[:3]
    today_action = {
        "enabled": exec_freshness in {"fresh", "usable_with_caution"},
        "status": exec_freshness,
        "actionable": [
            {
                "ticker": row["ticker"],
                "state": row["actionState"],
                "close": fmt_num(row["close"], prefix="$"),
                "bandGap": "In band" if row["bandGapDollar"] == 0 else (f"{fmt_num(abs(row['bandGapDollar']), prefix='$')} {'above' if (row['bandGapDollar'] or 0) > 0 else 'below'} band" if row["bandGapDollar"] is not None else "Band undefined"),
                "bandGapPct": fmt_pct(row["bandGapPct"], 2) if row["bandGapPct"] is not None else "—",
                "stopDist": fmt_pct(row["stopDistPct"], 1) if row["stopDistPct"] is not None else "—",
                "earnings": fmt_date_label(row["earningsDate"], last_trade_dt) if row["earningsDate"] else "No near earnings on file",
                "triggerLabel": "Trigger conditions met" if row["triggerToday"] else "Wait for better price or cleaner setup",
            }
            for row in actionable
        ],
        "blocked": [
            {
                "ticker": row["ticker"],
                "detail": fmt_date_label(row["earningsDate"], last_trade_dt) if row["earningsDate"] else "Unconfirmed",
            }
            for row in technical if row["blocked"]
        ],
        "belowStop": [
            {
                "ticker": row["ticker"],
                "detail": f"{fmt_num(row['close'], prefix='$')} vs stop {row['stop']}",
            }
            for row in technical if row["belowStop"]
        ],
        "message": describe_overall_status(exec_freshness),
    }

    deployment_summary = deploy_raw.get(
        "summary",
        {"deployable": [], "almost": [], "blocked": [], "below_stop": [], "bench": [], "watch": [], "error": []},
    )
    deployment_records = [
        {
            "ticker": r.get("ticker"),
            "state": r.get("action_state"),
            "reason": r.get("reason", ""),
            "close": fmt_num(r.get("close"), prefix="$"),
            "priority": f"P{r.get('priority', 9)}",
        }
        for r in normalize_records(deploy_raw.get("records"))
    ]

    history = update_history({"generated_at": now.strftime("%Y-%m-%d %H:%M UTC"), "technical": technical})

    earnings = sorted(
        [{"ticker": r.get("ticker"), "date": r.get("next_earnings_date")} for r in earnings_records if r.get("ticker") and r.get("next_earnings_date")],
        key=lambda item: item["date"],
    )
    earnings_alerts = earn_raw.get("watchlist_alerts", [])

    risk_thresholds = pf_raw.get("risk_thresholds", {}) if isinstance(pf_raw.get("risk_thresholds"), dict) else {}
    sizing_rules = pf_raw.get("sizing_rules", []) if isinstance(pf_raw.get("sizing_rules"), list) else []
    escalation_triggers = pf_raw.get("escalation_triggers", []) if isinstance(pf_raw.get("escalation_triggers"), list) else []
    regime_indicators = [
        {
            "label": item.get("label"),
            "value": item.get("value"),
            "detail": item.get("detail"),
            "colorKey": item.get("color_key", "amber"),
        }
        for item in pf_raw.get("regime_indicators", [])
    ]

    tech_concentration_tickers = set(sector_map.get("Tech", []))
    core_positions = pf.get("core", [])
    active_positions = pf.get("core", []) + pf.get("tactical", [])
    max_single = risk_thresholds.get("max_single_position_normal", 15)
    max_sector = risk_thresholds.get("max_sector_pct", 35)
    min_cash = risk_thresholds.get("min_cash_pct", 5)
    compliance_checks = [
        {
            "label": "Position sizing",
            "status": "warn" if any((p.get("weight") or 0) >= max_single for p in core_positions) else "ok",
            "detail": f"{sum(1 for p in core_positions if (p.get('weight') or 0) >= max_single)} core position(s) at or above {max_single}% normal cap.",
        },
        {
            "label": "Tech concentration",
            "status": "warn" if sum((p.get("weight") or 0) for p in active_positions if p.get("ticker") in tech_concentration_tickers) > max_sector else "ok",
            "detail": f"Tech sleeve is {round(sum((p.get('weight') or 0) for p in active_positions if p.get('ticker') in tech_concentration_tickers), 2)}% against {max_sector}% sector threshold.",
        },
        {
            "label": "Stop discipline",
            "status": "bad" if any(row["belowStop"] for row in technical) else "ok",
            "detail": "; ".join(f"{row['ticker']} below stop" for row in technical if row["belowStop"]) or "No tracked name is below stop.",
        },
        {
            "label": "Cash reserve",
            "status": "ok" if (pf.get("cash") or 0) >= min_cash else "bad",
            "detail": f"Cash is {pf.get('cash', 0)}% against minimum {min_cash}%.",
        },
        {
            "label": "Data integrity",
            "status": "bad" if validation["summary"]["critical"] else ("warn" if validation["summary"]["warning"] else "ok"),
            "detail": f"{validation['summary']['critical']} critical and {validation['summary']['warning']} warning integrity issue(s).",
        },
    ]

    overview_cards = [
        {"label": "S&P 500", "value": fmt_num(market["spx"]), "detail": "Cash index", "tone": "ok"},
        {"label": "VIX", "value": fmt_num(market["vix"]), "detail": "Volatility context", "tone": "warn" if (market["vix"] or 0) >= 20 else "ok"},
        {"label": "10Y Treasury", "value": fmt_pct(market["treasuries"]["y10"], 2), "detail": "Rates backdrop", "tone": "info"},
        {"label": "DXY", "value": fmt_num(market["dxy"]), "detail": "Dollar context", "tone": "info"},
        {"label": "Brent", "value": fmt_num(market["brent"], prefix="$"), "detail": "Energy complex", "tone": "info"},
        {"label": "Fed funds", "value": f"{fmt_num(market['fed']['target_low'])}-{fmt_num(market['fed']['target_high'])}%" if market['fed']['target_low'] is not None and market['fed']['target_high'] is not None else "—", "detail": "Manual dependency if post-FOMC not updated", "tone": "warn" if fed.get("manual_update_required") else "info"},
    ]

    alerts: list[dict[str, Any]] = []
    if exec_freshness in {"partial", "stale", "missing"}:
        alerts.append({"tone": "bad" if exec_freshness in {"stale", "missing"} else "warn", "title": "Execution trust degraded", "detail": describe_overall_status(exec_freshness)})
    if manual_dependencies:
        alerts.append({"tone": "warn", "title": "Manual and unconfirmed dependencies remain", "detail": "; ".join(dep["detail"] for dep in manual_dependencies[:3])})
    if validation["summary"]["critical"]:
        alerts.append({"tone": "bad", "title": "Integrity contradictions detected", "detail": f"{validation['summary']['critical']} critical issue(s) need attention before trusting the rendered view."})
    elif validation["summary"]["warning"]:
        alerts.append({"tone": "warn", "title": "Integrity warnings present", "detail": f"{validation['summary']['warning']} warning issue(s) were surfaced by the generator."})

    generated_at = now.strftime("%Y-%m-%d %H:%M UTC")

    payload = {
        "generated_at": generated_at,
        "last_trade_date": last_trade,
        "exec_freshness": exec_freshness,
        "market_session": market_session,
        "vault_freshness": vault_freshness,
        "history": history,
        "freshness": [
            {
                "label": info["label"],
                "time": info["generated_at"] or "Unavailable",
                "fresh": info["status"] in {"fresh", "usable_with_caution"},
                "age_h": info["age_h"],
                "status": info["status"],
                "issues": info["issues"],
            }
            for info in source_status.values()
        ],
        "provenance": provenance,
        "trust": {
            "overall_status": exec_freshness,
            "overall_label": status_badge(exec_freshness)["label"],
            "summary": describe_overall_status(exec_freshness),
            "sources": trust_sources,
            "manual_dependencies": manual_dependencies,
        },
        "validation": validation,
        "market": market,
        "technical": technical,
        "deployment_summary": deployment_summary,
        "deployment_records": deployment_records,
        "earnings": earnings,
        "earnings_alerts": earnings_alerts,
        "portfolio": pf,
        "sizing_rules": sizing_rules,
        "escalation_triggers": escalation_triggers,
        "regime_indicators": regime_indicators,
        "risk_thresholds": risk_thresholds,
        "today_action": today_action,
        "sector_weights": sector_weights,
        "ui": {
            "alerts": alerts,
            "overview_cards": overview_cards,
            "compliance_checks": compliance_checks,
        },
        "trigger_sheet": trigger_sheet_raw,
        "post_earnings": post_earnings_raw,
    }
    return payload
