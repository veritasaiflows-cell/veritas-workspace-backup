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
from market_data_utils import guard_dict_or_empty

HISTORY_PATH = TMP / "deployment-history.json"
ENTRY_BAND_REPORTS_DIR = WORKSPACE / "tmp" / "entry-band-reports"
NEAR_BAND_THRESHOLD_PCT = 5.0

# Required payload-shape contract — keys the dashboard view layer relies on.
# Any time these are renamed in the payload assembler, update here too or the
# dashboard fails silent. Validation runs at the end of build_payload and
# emits warnings into the existing validation block.
REQUIRED_TODAY_ACTION_KEYS = ("deployable", "almost", "blocked", "earningsPending", "riskOff")
REQUIRED_ACTION_CARD_KEYS = ("ticker", "close", "entryBand", "stop", "posture")
REQUIRED_DEPLOYMENT_RECORD_KEYS = (
    "ticker", "state", "close", "bandLabel", "bandLow", "bandHigh",
    "bandStatus", "bandPositionPct", "stop", "stopDistPct", "posture",
)
REQUIRED_MACRO_REGIME_KEYS = ("regime_label", "policy_pillar", "credit_pillar", "breadth_pillar")


def _validate_payload_shape(
    today_action: dict[str, Any],
    deployment_records: list[dict[str, Any]],
    macro_regime: dict[str, Any],
    sectors_relative: list[dict[str, Any]],
    post_earnings: dict[str, Any],
) -> list[dict[str, Any]]:
    """Catch breakage between the payload assembler and the view layer.

    Returns a list of validation warnings (same shape as build_validation).
    Treat shape drift as critical — it means the dashboard JS is reading
    fields that no longer exist, which produces silent blanks rather than errors.
    """
    issues: list[dict[str, Any]] = []

    def _add(code: str, severity: str, scope: str, message: str) -> None:
        issues.append({"code": code, "severity": severity, "scope": scope, "message": message})

    # today_action shape
    for key in REQUIRED_TODAY_ACTION_KEYS:
        if key not in today_action:
            _add(
                "today_action_missing_bucket", "critical", "shape",
                f"today_action missing required bucket '{key}' — the Overview action card will not render this section.",
            )
    for bucket_key in ("deployable", "almost", "blocked"):
        for idx, card in enumerate(today_action.get(bucket_key) or []):
            for field in REQUIRED_ACTION_CARD_KEYS:
                if field not in card:
                    _add(
                        "today_action_card_missing_field", "critical", "shape",
                        f"today_action.{bucket_key}[{idx}] ({card.get('ticker','?')}) missing required field '{field}'.",
                    )
                    break

    # deployment_records shape
    if deployment_records:
        sample = deployment_records[0]
        for field in REQUIRED_DEPLOYMENT_RECORD_KEYS:
            if field not in sample:
                _add(
                    "deployment_record_missing_field", "critical", "shape",
                    f"deployment_records[0] ({sample.get('ticker','?')}) missing required field '{field}' — Deployment Board column will be blank.",
                )

    # macro_regime shape
    for key in REQUIRED_MACRO_REGIME_KEYS:
        if not macro_regime.get(key):
            _add(
                "macro_regime_missing_field", "warning", "shape",
                f"macro_regime.{key} is missing or empty — Macro tab regime banner will degrade.",
            )

    # sectors_relative
    if not sectors_relative:
        _add(
            "sectors_relative_empty", "warning", "shape",
            "sectors_relative is empty — Sector RS card will show no data. Check market-state.json sectors block.",
        )

    # post_earnings window contract — Phase 6 expects back_trading_days
    pe_window = (post_earnings or {}).get("window") or {}
    if "back_trading_days" not in pe_window:
        _add(
            "post_earnings_window_missing_field", "warning", "shape",
            "post_earnings.window.back_trading_days missing — re-run post_earnings_prep.py after picking up Phase 6 changes.",
        )

    return issues


def _merge_shape_warnings(validation: dict[str, Any], shape_warnings: list[dict[str, Any]]) -> None:
    """Append shape warnings to the existing validation block and re-tally."""
    if not shape_warnings:
        return
    validation.setdefault("warnings", []).extend(shape_warnings)
    summary = validation.setdefault("summary", {"critical": 0, "warning": 0, "info": 0})
    for w in shape_warnings:
        sev = w["severity"]
        summary[sev] = summary.get(sev, 0) + 1
    if summary.get("critical"):
        validation["overall"] = "critical"
    elif summary.get("warning") and validation.get("overall") != "critical":
        validation["overall"] = "warning"


def _degrade_source_status(
    source_status: dict[str, dict[str, Any]],
    source_key: str,
    *,
    issue: str,
    tag: str,
    overall_status: str,
) -> str:
    info = source_status.get(source_key)
    if not info:
        return overall_status
    if issue not in info["issues"]:
        info["issues"].append(issue)
    if tag not in info["tags"]:
        info["tags"].append(tag)
    info["status"] = status_worse(info["status"], "partial")
    info["fresh"] = info["status"] in {"fresh", "usable_with_caution"}
    if info["critical"]:
        overall_status = status_worse(overall_status, info["status"])
    return overall_status


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
    policy_raw = sources["policy"] or {}
    credit_raw = sources.get("credit") or {}
    breadth_raw = sources.get("breadth") or {}
    tech_raw = sources["technical"] or {}
    deploy_raw = sources["deployment"] or {}
    earn_raw = sources["earnings"] or {}
    pf_raw = sources["portfolio"] or {}

    now = datetime.now(timezone.utc)
    market_session = get_market_session(now)
    source_status = {name: assess_source(name, src) for name, src in sources.items()}
    vault_freshness = get_vault_freshness()
    shape_warnings: list[dict[str, Any]] = []

    overall_status = "fresh"
    for name, info in source_status.items():
        if info["critical"]:
            overall_status = status_worse(overall_status, info["status"])

    last_trade = tech_raw.get("last_trading_day") or market_raw.get("last_trading_day") or now.strftime("%Y-%m-%d")
    last_trade_dt = parse_date(last_trade) or now

    ms_data = market_raw.get("data", {})
    policy_data = policy_raw.get("data", {}) if isinstance(policy_raw.get("data"), dict) else {}
    credit_data = credit_raw.get("data", {}) if isinstance(credit_raw.get("data"), dict) else {}
    breadth_data = breadth_raw.get("data", {}) if isinstance(breadth_raw.get("data"), dict) else {}
    sector_shape_messages: list[str] = []
    sectors_raw, _ = guard_dict_or_empty(get_path(market_raw, "data.sectors"), sector_shape_messages, "market-state.data.sectors")

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
    policy_expectations = {
        "generated_at": policy_raw.get("generated_at_utc"),
        "status": policy_raw.get("status"),
        "source_label": get_path(policy_data, "source_label"),
        "source_mode": get_path(policy_data, "source_mode"),
        "implied_rate_source_mode": get_path(policy_data, "implied_rate_source_mode"),
        "warnings": list(dict.fromkeys(policy_raw.get("warnings", []))),
        "freshness_notes": list(dict.fromkeys(policy_raw.get("freshness_notes", []))),
        "current_target_range": get_path(policy_data, "current_target_range") or {},
        "next_fomc": get_path(policy_data, "next_fomc") or {},
        "next_two_meetings": get_path(policy_data, "next_two_meetings") or [],
        "manual_dependencies": get_path(policy_data, "manual_dependencies") or [],
    }
    credit_spreads = {
        "generated_at": credit_raw.get("generated_at_utc"),
        "status": credit_raw.get("status"),
        "source_label": get_path(credit_data, "source_label"),
        "source_mode": get_path(credit_data, "source_mode"),
        "warnings": list(dict.fromkeys(credit_raw.get("warnings", []))),
        "investment_grade_oas": get_path(credit_data, "investment_grade_oas") or {},
        "high_yield_oas": get_path(credit_data, "high_yield_oas") or {},
        "hy_minus_ig_spread": get_path(credit_data, "hy_minus_ig_spread"),
        "direction": get_path(credit_data, "direction") or {},
        "stress_regime": get_path(credit_data, "stress_regime"),
    }
    market_breadth = {
        "generated_at": breadth_raw.get("generated_at_utc"),
        "status": breadth_raw.get("status"),
        "source_mode": get_path(breadth_data, "source_mode"),
        "warnings": list(dict.fromkeys(breadth_raw.get("warnings", []))),
        "equal_weight_vs_cap_weight": get_path(breadth_data, "equal_weight_vs_cap_weight") or {},
        "sector_participation": get_path(breadth_data, "sector_participation") or {},
        "major_index_breadth": get_path(breadth_data, "major_index_breadth") or {},
        "tier2_metrics": get_path(breadth_data, "tier2_metrics") or {},
    }

    macro_regime_raw = load_json(TMP / "macro-regime.json") or {}
    macro_regime = {
        "generated_at": macro_regime_raw.get("generated_at_utc"),
        "status": macro_regime_raw.get("status"),
        "regime_label": get_path(macro_regime_raw, "regime.label"),
        "regime_key": get_path(macro_regime_raw, "regime.key"),
        "policy_pillar": get_path(macro_regime_raw, "pillars.policy") or {},
        "credit_pillar": get_path(macro_regime_raw, "pillars.credit") or {},
        "breadth_pillar": get_path(macro_regime_raw, "pillars.breadth") or {},
    }

    sectors_relative: list[dict[str, Any]] = []
    for key, info in sectors_raw.items():
        sector_info, bad = guard_dict_or_empty(info, sector_shape_messages, f"market-state.data.sectors.{key}")
        if bad:
            continue
        sectors_relative.append({
            "ticker": sector_info.get("ticker") or key.upper(),
            "label": sector_info.get("label") or key.upper(),
            "change_pct": sector_info.get("change_pct"),
            "relative_vs_spx_pct": sector_info.get("relative_vs_spx_pct"),
            "relative_label": sector_info.get("relative_label"),
            "last_price": sector_info.get("last_price"),
        })
    sectors_relative.sort(key=lambda s: s.get("relative_vs_spx_pct") if s.get("relative_vs_spx_pct") is not None else -999, reverse=True)

    for message in sector_shape_messages:
        shape_warnings.append({
            "code": "market_sectors_invalid_shape",
            "severity": "warning",
            "scope": "shape",
            "message": message,
        })
        overall_status = _degrade_source_status(
            source_status,
            "market",
            issue=message,
            tag="shape_invalid",
            overall_status=overall_status,
        )

    exec_freshness = overall_status
    provenance = build_provenance(source_status)

    entry_bands = pf_raw.get("entry_bands", {}) if isinstance(pf_raw.get("entry_bands"), dict) else {}
    posture_labels = pf_raw.get("posture_labels", {}) if isinstance(pf_raw.get("posture_labels"), dict) else {}
    tracked_universe = pf_raw.get("tracked_universe", {}) if isinstance(pf_raw.get("tracked_universe"), dict) else {}
    deploy_by_ticker = {r.get("ticker"): r for r in normalize_records(deploy_raw.get("records"))}
    earnings_records = normalize_records(earn_raw.get("records"))
    earnings_by_ticker = {r.get("ticker"): r.get("next_earnings_date") for r in earnings_records if r.get("ticker")}

    def _coverage_lane_label(lane: str | None) -> str:
        lane_key = (lane or "").lower()
        return {
            "execution": "Exec",
            "watch": "Watch",
            "macro": "Macro",
            "speculative": "Spec",
        }.get(lane_key, "—")

    technical: list[dict[str, Any]] = []
    for record in normalize_records(tech_raw.get("records")):
        ticker = record.get("ticker")
        band = entry_bands.get(ticker, {})
        meta = tracked_universe.get(ticker, {}) if isinstance(tracked_universe.get(ticker), dict) else {}
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

        earnings_blocked = deploy.get("earnings_blocked", False) if deploy else False

        trigger_ready = bool(
            exec_freshness in {"fresh", "usable_with_caution"}
            and band_gap_dollar is not None
            and band_gap_dollar <= 0
            and not earnings_blocked
            and not record.get("below_stop")
            and action_state in {"DEPLOYABLE", "ALMOST"}
        )

        band_status, band_dist_pct = _compute_band_status(
            close, band_low, band_high,
            record.get("in_entry_band"), record.get("below_stop"),
        )
        report_file = ENTRY_BAND_REPORTS_DIR / f"{ticker}_entry_band.html"
        entry_band_report_path = (
            f"entry-band-reports/{ticker}_entry_band.html"
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
            "blocked": earnings_blocked,
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
            "coverageLane": meta.get("coverage_lane"),
            "coverageLaneLabel": _coverage_lane_label(meta.get("coverage_lane")),
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
    fed = get_path(market_raw, "data.fed") or {}
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

    if policy_raw:
        for dep in policy_expectations["manual_dependencies"]:
            if isinstance(dep, dict):
                _add_dep(
                    dep.get("label") or dep.get("field") or "Policy dependency",
                    "Macro",
                    "manual",
                    dep.get("detail") or "Manual policy-layer maintenance remains in place.",
                )
        if policy_expectations.get("implied_rate_source_mode") == "fallback_proxy":
            _add_dep(
                "Policy expectations source path",
                "Macro",
                "unconfirmed",
                "Policy expectations are currently using the generic ZQ=F front-contract proxy because the contract-specific ZQ quote was unavailable.",
            )
    else:
        if fed.get("manual_update_required"):
            _add_dep(
                "Fed target range",
                "Macro",
                "manual",
                "Update the hardcoded Fed target range in scripts/policy_expectations_refresh.py after each FOMC decision.",
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

    def _band_gap_phrase(row: dict[str, Any]) -> str:
        gap = row.get("bandGapDollar")
        if gap is None:
            return "Band undefined"
        if gap == 0:
            return "In band"
        return f"{fmt_num(abs(gap), prefix='$')} {'above' if gap > 0 else 'below'} band"

    tech_by_ticker = {row["ticker"]: row for row in technical}
    trigger_records = [r for r in normalize_records(trigger_sheet_raw.get("records")) if r.get("ticker")]
    trigger_by_ticker = {r["ticker"]: r for r in trigger_records}
    trigger_summary_raw = trigger_sheet_raw.get("summary") if isinstance(trigger_sheet_raw.get("summary"), dict) else {}

    trigger_do_not_touch = list(trigger_summary_raw.get("do_not_touch", []) or [])
    trigger_watch = list(trigger_summary_raw.get("watch", []) or [])
    below_stop_tickers = [
        ticker for ticker in [*trigger_do_not_touch, *trigger_watch]
        if tech_by_ticker.get(ticker, {}).get("belowStop")
    ]
    bench_tickers = [ticker for ticker in trigger_do_not_touch if ticker not in below_stop_tickers]
    watch_tickers = [ticker for ticker in trigger_watch if ticker not in below_stop_tickers]

    deployment_summary = {
        "deployable": list(trigger_summary_raw.get("deployable_now", []) or []),
        "almost": list(trigger_summary_raw.get("almost_deployable", []) or []),
        "blocked": list(trigger_summary_raw.get("blocked", []) or []),
        "below_stop": below_stop_tickers,
        "bench": bench_tickers,
        "watch": watch_tickers,
        "error": list(trigger_summary_raw.get("error", []) or []),
    }

    priority_buckets = {
        "deployable": 1,
        "almost": 2,
        "blocked": 3,
        "below_stop": 4,
        "bench": 5,
        "watch": 6,
    }
    priority_map: dict[str, int] = {}
    for bucket_name, rank in priority_buckets.items():
        for ticker in deployment_summary.get(bucket_name, []):
            priority_map.setdefault(ticker, rank)

    def _dashboard_state_for_ticker(ticker: str) -> str:
        trigger = trigger_by_ticker.get(ticker, {})
        tech_row = tech_by_ticker.get(ticker, {})
        if tech_row.get("belowStop"):
            return "BELOW STOP"

        action_state = str(trigger.get("action_state") or "").upper()
        if "DEPLOYABLE" in action_state and "ALMOST" not in action_state:
            return "DEPLOYABLE"
        if "ALMOST" in action_state:
            return "ALMOST"
        if action_state == "BLOCKED":
            return "BLOCKED"
        if "WATCH" in action_state:
            return "WATCH"
        if action_state in {"DO NOT TOUCH", "BENCH"}:
            return "BENCH"

        deployment_state = str(trigger.get("deployment_state") or "").upper()
        if deployment_state in {"DEPLOYABLE", "ALMOST", "BLOCKED", "WATCH", "BENCH"}:
            return deployment_state
        return "WATCH"

    def _action_card(
        row: dict[str, Any],
        *,
        state_override: str | None = None,
        reason: str | None = None,
        trigger_label: str | None = None,
    ) -> dict[str, Any]:
        return {
            "ticker": row["ticker"],
            "state": state_override or row["actionState"],
            "close": fmt_num(row["close"], prefix="$"),
            "entryBand": row["entry"],
            "stop": row["stop"],
            "posture": row.get("posture") or row.get("raw_ma_posture") or "—",
            "bandGap": _band_gap_phrase(row),
            "bandGapPct": fmt_pct(row["bandGapPct"], 2) if row["bandGapPct"] is not None else "—",
            "bandStatus": row.get("bandStatus") or "—",
            "stopDist": fmt_pct(row["stopDistPct"], 1) if row["stopDistPct"] is not None else "—",
            "earnings": fmt_date_label(row["earningsDate"], last_trade_dt) if row["earningsDate"] else "No near earnings on file",
            "daysToEarnings": row.get("daysToEarnings"),
            "triggerLabel": trigger_label if trigger_label is not None else ("Trigger conditions met" if row["triggerToday"] else "Wait for better price or cleaner setup"),
            **({"reason": reason} if reason else {}),
        }

    deployable_cards = [
        _action_card(tech_by_ticker[ticker], state_override="DEPLOYABLE")
        for ticker in deployment_summary["deployable"][:3]
        if ticker in tech_by_ticker
    ]
    almost_cards = [
        _action_card(tech_by_ticker[ticker], state_override="ALMOST")
        for ticker in deployment_summary["almost"][:3]
        if ticker in tech_by_ticker
    ]
    blocked_cards = [
        _action_card(
            tech_by_ticker[ticker],
            state_override="BLOCKED",
            reason=trigger_by_ticker.get(ticker, {}).get("why") or "Blocker remains active in the trigger layer",
            trigger_label="Blocker must clear before deployment",
        )
        for ticker in deployment_summary["blocked"][:3]
        if ticker in tech_by_ticker
    ]
    earnings_pending = [
        _action_card(
            tech_by_ticker[ticker],
            state_override="BLOCKED",
            reason="Earnings catalyst pending — do not deploy until print is reviewed",
            trigger_label="Catalyst pause remains active",
        )
        for ticker, trigger in trigger_by_ticker.items()
        if trigger.get("earnings_blocked") and ticker in tech_by_ticker
    ][:3]
    risk_off = [
        _action_card(
            tech_by_ticker[ticker],
            state_override="BELOW STOP",
            reason=f"Closed {fmt_num(tech_by_ticker[ticker]['close'], prefix='$')} vs stop {tech_by_ticker[ticker]['stop']} — risk-off until repair confirmed",
            trigger_label="Repair confirmation required before re-engagement",
        )
        for ticker in deployment_summary["below_stop"][:3]
        if ticker in tech_by_ticker
    ]

    today_action = {
        "enabled": exec_freshness in {"fresh", "usable_with_caution"},
        "status": exec_freshness,
        "deployable": deployable_cards,
        "almost": almost_cards,
        "blocked": blocked_cards,
        "earningsPending": earnings_pending,
        "riskOff": risk_off,
        # Backward-compatible aliases for any consumers reading the prior shape.
        "actionable": deployable_cards + almost_cards,
        "blockedLegacy": [{"ticker": x["ticker"], "detail": x.get("earnings") or x.get("reason")} for x in earnings_pending],
        "belowStop": [{"ticker": x["ticker"], "detail": x["reason"]} for x in risk_off],
        "message": describe_overall_status(exec_freshness),
    }

    deployment_records = []
    ordered_tickers: list[str] = []
    for bucket_name in ("deployable", "almost", "blocked", "below_stop", "bench", "watch"):
        for ticker in deployment_summary.get(bucket_name, []):
            if ticker not in ordered_tickers:
                ordered_tickers.append(ticker)
    for ticker in trigger_by_ticker:
        if ticker not in ordered_tickers:
            ordered_tickers.append(ticker)

    for ticker in ordered_tickers:
        r = trigger_by_ticker.get(ticker, {})
        tech_row = tech_by_ticker.get(ticker, {})
        band = entry_bands.get(ticker, {})
        close = tech_row.get("close", r.get("close"))
        band_low = band.get("low")
        band_high = band.get("high")
        position_pct = None
        if close is not None and band_low is not None and band_high is not None and band_high != band_low:
            position_pct = round(((close - band_low) / (band_high - band_low)) * 100, 1)

        state = _dashboard_state_for_ticker(ticker)
        reason = r.get("why") or r.get("reason") or tech_row.get("actionReason") or ""
        if state == "BELOW STOP" and close is not None:
            reason = f"close {fmt_num(close)} is below stop — do not deploy"
        deployment_records.append({
            "ticker": ticker,
            "state": state,
            "reason": reason,
            "close": fmt_num(close, prefix="$"),
            "closeRaw": close,
            "bandLabel": tech_row.get("entry") or band.get("label") or "—",
            "bandLow": band_low,
            "bandHigh": band_high,
            "bandStatus": tech_row.get("bandStatus") or "—",
            "bandPositionPct": position_pct,
            "stop": tech_row.get("stop") or band.get("stop_label") or "—",
            "stopDistPct": tech_row.get("stopDistPct"),
            "posture": tech_row.get("posture") or tech_row.get("raw_ma_posture") or "—",
            "earningsDate": tech_row.get("earningsDate"),
            "daysToEarnings": tech_row.get("daysToEarnings"),
            "priority": f"P{priority_map.get(ticker, 9)}",
        })

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

    consistency_raw = load_json(TMP / "universe-consistency.json") or {}

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
            "consistency": consistency_raw,
        },
        "validation": validation,
        "market": market,
        "policy_expectations": policy_expectations,
        "credit_spreads": credit_spreads,
        "market_breadth": market_breadth,
        "macro_regime": macro_regime,
        "sectors_relative": sectors_relative,
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

    shape_warnings.extend(_validate_payload_shape(
        today_action=today_action,
        deployment_records=deployment_records,
        macro_regime=macro_regime,
        sectors_relative=sectors_relative,
        post_earnings=post_earnings_raw or {},
    ))
    _merge_shape_warnings(payload["validation"], shape_warnings)

    return payload
