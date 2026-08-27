#!/usr/bin/env python3
"""Draft repeatable review-only macro interpretation from current artifacts.

The draft fills the weekly macro judgment layer without granting forecast,
portfolio/canon mutation, paper/live execution, or owner-approval authority.
It is a first-pass Veritas interpretation surface, not final doctrine.
"""
from __future__ import annotations

import argparse
import json
import re
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, atomic_write_text, load_json_artifact

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"

DEFAULT_JSON = TMP / "macro-judgment-draft.json"
DEFAULT_MD = TMP / "macro-judgment-draft.md"

MARKET_STATE = TMP / "market-state.json"
MACRO_REGIME = TMP / "macro-regime.json"
MACRO_METRICS = TMP / "macro-metrics-current.json"
MACRO_SIGNAL_SPINE = TMP / "macro-signal-spine.json"
MACRO_EVENTS = TMP / "macro-event-calendar.json"
MACRO_ENERGY_SUPPLY = TMP / "macro-energy-supply.json"
MACRO_GEOPOLITICAL_SWEEP = TMP / "macro-geopolitical-sweep.json"
DEPLOYMENT_SURFACE = TMP / "deployment-readiness-surface.json"
REGIME_SCORES = TMP / "regime-scores.json"
DASHBOARD_VALIDATION = TMP / "dashboard-validation.json"
CURRENT_ANALOG_MATCH = TMP / "current-regime-analog-match.json"

SCHEMA = "veritas.macro_judgment_draft.v1"
PLACEHOLDER_RE = re.compile(r"_\[[^\]]+\]_|Fill:|Fill from|TODO|TBD|FIXME", re.IGNORECASE)
FORBIDDEN_ACTION_RE = re.compile(
    r"\b(place|execute|submit|cancel|liquidate|rebalance|buy now|sell now|trim now|add now)\b",
    re.IGNORECASE,
)

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "forecast_or_probability_claim_allowed": False,
    "portfolio_or_canon_mutation_allowed": False,
    "paper_or_live_execution_allowed": False,
    "owner_approval_inferred": False,
    "capital_action_allowed": False,
}
USABLE_RIG_STATUSES = {"ok", "cached_fallback", "public_republisher_fallback"}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load(path: Path) -> dict[str, Any]:
    data = load_json_artifact(path)
    return data if isinstance(data, dict) else {}


def metric(metrics: dict[str, Any], key: str) -> dict[str, Any]:
    rows = metrics.get("metrics") if isinstance(metrics.get("metrics"), list) else []
    for row in rows:
        if isinstance(row, dict) and row.get("key") == key:
            return row
    return {}


def pct(value: Any) -> str:
    if value is None:
        return "n/a"
    try:
        return f"{float(value):.2f}%"
    except Exception:
        return str(value)


def num(value: Any, digits: int = 2) -> str:
    if value is None:
        return "n/a"
    try:
        return f"{float(value):,.{digits}f}"
    except Exception:
        return str(value)


def latest_line(row: dict[str, Any], fields: tuple[str, ...]) -> str:
    if not row or row.get("status") != "ok":
        return f"{(row or {}).get('name') or 'metric'} unavailable"
    parts = [f"{row.get('name')} {num(row.get('latest_value'))} as of {row.get('latest_date')}"]
    labels = {
        "mom_pct": "MoM",
        "yoy_pct": "YoY",
        "qoq_annualized_pct": "QoQ annualized",
        "delta": "delta",
    }
    for field in fields:
        value = row.get(field)
        if value is None:
            continue
        formatter = pct if field.endswith("_pct") else num
        parts.append(f"{labels.get(field, field)} {formatter(value)}")
    return "; ".join(parts)


def cpi_component(metrics: dict[str, Any], key: str) -> dict[str, Any]:
    detail = metrics.get("cpi_release_detail") if isinstance(metrics.get("cpi_release_detail"), dict) else {}
    rows = []
    for field in ("components", "narrative_components"):
        value = detail.get(field)
        if isinstance(value, list):
            rows.extend(row for row in value if isinstance(row, dict))
    for row in rows:
        if row.get("key") == key:
            return row
    return {}


def judge_pulse(metrics: dict[str, Any]) -> tuple[str, str]:
    cpi = metric(metrics, "cpi_headline")
    core_cpi = metric(metrics, "cpi_core")
    ppi = metric(metrics, "ppi_headline_final_demand")
    pce = metric(metrics, "pce_headline")
    claims = metric(metrics, "initial_claims")
    continuing = metric(metrics, "continuing_claims")
    payrolls = metric(metrics, "nonfarm_payrolls")
    gdp = metric(metrics, "real_gdp")

    inflation_hot = any((row.get("mom_pct") or 0) >= 0.35 for row in (cpi, core_cpi, pce))
    ppi_hot = (ppi.get("mom_pct") or 0) >= 0.5
    labor_ok = (payrolls.get("delta") or 0) > 0 and (claims.get("latest_value") or 999999) < 250000
    claims_deteriorating = (claims.get("delta") or 0) > 0 or (continuing.get("delta") or 0) > 0
    growth_ok = (gdp.get("qoq_annualized_pct") or 0) > 1.0
    cpi_detail = metrics.get("cpi_release_detail") if isinstance(metrics.get("cpi_release_detail"), dict) else {}
    energy = cpi_component(metrics, "energy")
    gasoline = cpi_component(metrics, "gasoline_all_types")
    shelter = cpi_component(metrics, "shelter")
    rent = cpi_component(metrics, "rent_of_primary_residence")
    owners_equivalent_rent = cpi_component(metrics, "owners_equivalent_rent")

    if inflation_hot or ppi_hot:
        direction = "inflation pressure is re-accelerating enough to keep rate sensitivity high"
    elif labor_ok and growth_ok and not claims_deteriorating:
        direction = "growth is stable with contained labor stress"
    else:
        direction = "growth/inflation momentum is mixed and should be treated as unstable"

    cpi_driver = ""
    if cpi_detail.get("status") in {"ok", "warning"}:
        cpi_driver = (
            f" Latest BLS CPI detail shows headline {pct(cpi_component(metrics, 'all_items').get('latest_mom_pct'))} MoM / "
            f"{pct(cpi_component(metrics, 'all_items').get('yoy_pct'))} YoY, core "
            f"{pct(cpi_component(metrics, 'core_all_items_less_food_energy').get('latest_mom_pct'))} MoM / "
            f"{pct(cpi_component(metrics, 'core_all_items_less_food_energy').get('yoy_pct'))} YoY; "
            f"energy {pct(energy.get('latest_mom_pct'))} MoM / {pct(energy.get('yoy_pct'))} YoY, "
            f"gasoline {pct(gasoline.get('latest_mom_pct'))} MoM / {pct(gasoline.get('yoy_pct'))} YoY, "
            f"shelter {pct(shelter.get('latest_mom_pct'))} MoM / {pct(shelter.get('yoy_pct'))} YoY, "
            f"rent {pct(rent.get('latest_mom_pct'))} MoM, OER {pct(owners_equivalent_rent.get('latest_mom_pct'))} MoM."
        )
    else:
        cpi_driver = " BLS CPI release-detail decomposition is unavailable; headline/core CPI should not be over-interpreted without component review."

    text = (
        f"{direction}. CPI/core/PCE remain the key pressure points; payroll growth is still positive, "
        f"but claims direction keeps labor risk on watch. GDP is not signaling a collapse, so this is "
        f"selective-risk-on rather than broad all-clear.{cpi_driver}"
    )
    confidence = "medium" if metrics.get("status") == "ok" and cpi_detail.get("status") == "ok" else "low"
    return text, confidence


def judge_macro_signal_spine(signal_spine: dict[str, Any]) -> tuple[str, str, list[str]]:
    if not signal_spine:
        return (
            "Macro signal spine is unavailable; Sahm, valuation, financial-conditions, rates/volatility, and expanded breadth checks remain manual dependencies.",
            "low",
            ["missing:tmp/macro-signal-spine.json"],
        )
    buckets = signal_spine.get("signal_buckets") if isinstance(signal_spine.get("signal_buckets"), dict) else {}
    summary = signal_spine.get("summary") if isinstance(signal_spine.get("summary"), dict) else {}

    def bucket_line(key: str) -> str:
        bucket = buckets.get(key) if isinstance(buckets.get(key), dict) else {}
        risk = bucket.get("risk_level") or "unknown"
        status = bucket.get("status") or "unknown"
        return f"{key.replace('_', ' ')} {risk}/{status}"

    lines = [
        bucket_line("recession_labor"),
        bucket_line("valuation"),
        bucket_line("financial_conditions"),
        bucket_line("rates_volatility"),
        bucket_line("expanded_index_breadth"),
    ]
    posture = summary.get("macro_posture") or "unknown"
    risk_counts = summary.get("risk_counts") if isinstance(summary.get("risk_counts"), dict) else {}
    text = (
        f"Macro signal spine posture is {posture}: {', '.join(lines)}. "
        f"Risk stack red/yellow/green/unknown = {risk_counts.get('red', 0)}/"
        f"{risk_counts.get('yellow', 0)}/{risk_counts.get('green', 0)}/{risk_counts.get('unknown', 0)}. "
        "Use this to adjust evidence burden and no-chase discipline; it is not a timing model or capital-action authority."
    )
    confidence = "medium" if signal_spine.get("status") in {"ok", "warning"} else "low"
    return text, confidence, ["tmp/macro-signal-spine.json"]


def judge_energy(market_state: dict[str, Any], energy_supply: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any], str]:
    energy = (((market_state or {}).get("data") or {}).get("energy") or {})
    brent = energy.get("brent")
    wti = energy.get("wti")
    spread_text = "n/a"
    try:
        spread_text = f"${float(brent) - float(wti):.2f}"
    except Exception:
        pass
    eia_artifact = energy_supply.get("eia_weekly_petroleum") if isinstance(energy_supply.get("eia_weekly_petroleum"), dict) else {}
    eia_summary = eia_artifact.get("summary") if isinstance(eia_artifact.get("summary"), dict) else {}
    if eia_artifact.get("status") == "ok":
        eia = {
            "text": (
                f"EIA weekly petroleum table is wired for week {eia_artifact.get('week_current')}; "
                f"commercial crude change {num(eia_summary.get('commercial_crude_week_change_mmbbl'))} mmbbl, "
                f"gasoline change {num(eia_summary.get('gasoline_week_change_mmbbl'))} mmbbl, "
                f"distillate change {num(eia_summary.get('distillate_week_change_mmbbl'))} mmbbl. "
                f"Inventory signal: {eia_summary.get('inventory_signal') or 'n/a'}."
            ),
            "confidence": "medium",
            "source_basis": ["tmp/macro-energy-supply.json"],
        }
    else:
        eia = {
            "text": "No current EIA inventory artifact is usable; do not infer crude/gasoline/distillate balance from price alone.",
            "confidence": "low",
            "source_basis": ["missing:EIA inventory artifact"],
        }

    rig_artifact = energy_supply.get("baker_hughes") if isinstance(energy_supply.get("baker_hughes"), dict) else {}
    if rig_artifact.get("status") in USABLE_RIG_STATUSES and rig_artifact.get("us_rig_count") is not None:
        status = rig_artifact.get("status")
        caveat = (
            " This is a public republisher fallback because Baker Hughes official pages timed out."
            if status == "public_republisher_fallback"
            else ""
        )
        rig = {
            "text": (
                f"Baker Hughes rig-count artifact is wired with U.S. rig count {rig_artifact.get('us_rig_count')} "
                f"as of {rig_artifact.get('latest_date') or 'date unavailable'}; status {status}."
                f"{caveat} Use as supply-response context, not a standalone energy thesis."
            ),
            "confidence": "medium" if status == "ok" else "low",
            "source_basis": ["tmp/macro-energy-supply.json"],
        }
    else:
        rig = {
            "text": "No current Baker Hughes rig-count artifact is usable; treat U.S. supply response as a manual dependency.",
            "confidence": "low",
            "source_basis": ["missing:Baker Hughes rig-count artifact"],
        }
    structure = (
        f"Brent {num(brent)} and WTI {num(wti)} with Brent/WTI spread {spread_text}; "
        "price level is high enough to keep inflation and margin risk relevant; use EIA/rig artifacts for supply confirmation when available."
    )
    return eia, rig, structure


def judge_dollar(market_state: dict[str, Any]) -> str:
    data = (market_state or {}).get("data") or {}
    fx = data.get("fx") or {}
    treasuries = data.get("treasuries") or {}
    dxy = fx.get("dxy")
    ten_year = treasuries.get("10y")
    two_year = treasuries.get("2y")
    return (
        f"DXY {num(dxy)} with 2Y {num(two_year, 3)}% and 10Y {num(ten_year, 3)}%; "
        "the dollar/rates mix argues for selective quality exposure and no broad duration or speculative chase."
    )


def next_events(calendar: dict[str, Any], horizon_days: int = 10) -> list[dict[str, Any]]:
    events = calendar.get("events") if isinstance(calendar.get("events"), list) else []
    upcoming = []
    for event in events:
        if not isinstance(event, dict) or event.get("status") != "upcoming":
            continue
        days = event.get("days_until")
        if isinstance(days, int) and days <= horizon_days:
            upcoming.append(event)
    return sorted(upcoming, key=lambda row: row.get("date") or "")


def judge_geopolitics(calendar: dict[str, Any], geopolitical_sweep: dict[str, Any]) -> tuple[dict[str, Any], str]:
    events = next_events(calendar, 30)
    event_text = ", ".join(f"{e.get('metric')} {e.get('date')}" for e in events[:5]) or "no seeded high-impact macro events"
    geo_summary = geopolitical_sweep.get("summary") if isinstance(geopolitical_sweep.get("summary"), dict) else {}
    if geopolitical_sweep.get("status") in {"ok", "warning"}:
        watch_items = geopolitical_sweep.get("watch_items") if isinstance(geopolitical_sweep.get("watch_items"), list) else []
        top_titles = "; ".join(str(item.get("title")) for item in watch_items[:3] if isinstance(item, dict) and item.get("title"))
        hot = {
            "text": (
                f"Official-source geopolitical sweep is wired: {geo_summary.get('ok_source_count')}/"
                f"{geo_summary.get('source_count')} feeds ok, {geo_summary.get('watch_item_count')} watch items. "
                f"Top routed titles: {top_titles or 'none'}. Treat titles as review cues, not verified market conclusions."
            ),
            "confidence": "medium" if geopolitical_sweep.get("status") == "ok" else "low",
            "source_basis": ["tmp/macro-geopolitical-sweep.json"],
        }
    else:
        hot = {
            "text": (
                "No live geopolitical/news sweep artifact is usable. Treat tariff/trade, Middle East energy risk, "
                "Russia/Ukraine, China/Taiwan, sanctions, and election-cycle risk as manual review items before making market-state claims."
            ),
            "confidence": "low",
            "source_basis": ["missing:live geopolitical/news sweep artifact"],
        }
    implication = (
        f"Near-term event risk is macro-data heavy ({event_text}). Portfolio implication is patience: favor quality and names already in-band, "
        "keep speculative/rate-sensitive exposure owner-gated, and do not convert headline risk into automatic capital action."
    )
    return hot, implication


def judge_next_week(calendar: dict[str, Any]) -> str:
    events = next_events(calendar, 10)
    if not events:
        return "No seeded high-impact CPI/PPI/PCE/NFP/FOMC event falls inside the next 10 days; keep weekly claims/market-state refresh cadence active."
    return "; ".join(
        f"{event.get('date')} {event.get('agency')} {event.get('metric')} ({event.get('period')})"
        for event in events
    )


def judge_posture(market_state: dict[str, Any], macro_regime: dict[str, Any], deployment: dict[str, Any]) -> tuple[str, str, str]:
    data = market_state.get("data") or {}
    vix = ((data.get("volatility") or {}).get("vix"))
    credit = (data.get("credit") or {}).get("stress_regime")
    breadth = (data.get("breadth") or {}).get("breadth_regime")
    regime_label = ((macro_regime.get("regime") or {}).get("label") or "macro regime unavailable")
    system = deployment.get("system") or {}
    warning_codes = system.get("warning_codes") or []
    deployable = ((deployment.get("summary") or {}).get("DEPLOYABLE NOW") or 0)
    promotion = ((deployment.get("summary") or {}).get("PROMOTION REVIEW") or 0)

    if system.get("stop_line"):
        posture = "Defensive"
    elif credit == "benign" and breadth == "broad" and (vix is not None and float(vix) < 18):
        posture = "Defensive-neutral to selective risk-on"
    else:
        posture = "Defensive-neutral"

    basis = (
        f"{posture}: {regime_label}; VIX {num(vix)}, credit {credit or 'unknown'}, breadth {breadth or 'unknown'}, "
        f"{deployable} deployable-now and {promotion} promotion-review names. "
        f"Warnings: {', '.join(warning_codes) if warning_codes else 'none'}."
    )
    directive = (
        "Review-only capital posture: keep deployment selective and owner-gated; prioritize in-band quality setups, "
        "avoid chase behavior, and treat macro/rates-sensitive names as review candidates until fresh event risk clears."
    )
    return posture, basis, directive


def judge_scenario_context(analog_match: dict[str, Any]) -> tuple[str, str, list[str]]:
    panel = analog_match.get("scenario_context_panel") if isinstance(analog_match.get("scenario_context_panel"), dict) else {}
    primary = panel.get("primary_analogs") if isinstance(panel.get("primary_analogs"), list) else []
    stress = panel.get("stress_caution_analogs") if isinstance(panel.get("stress_caution_analogs"), list) else []
    if analog_match.get("status") not in {"ok", "warning"} or not primary:
        return (
            "Current-regime historical analog panel is unavailable; macro judgment should not claim historical scenario support until the WF55 analog matcher is refreshed.",
            "low",
            ["missing:tmp/current-regime-analog-match.json"],
        )
    primary_labels = "; ".join(str(row.get("label")) for row in primary[:4] if isinstance(row, dict) and row.get("label"))
    stress_labels = "; ".join(str(row.get("label")) for row in stress[:3] if isinstance(row, dict) and row.get("label"))
    observations = panel.get("scenario_observations") if isinstance(panel.get("scenario_observations"), list) else []
    text = (
        f"Historical scenario context is wired for review-only use. Primary analogs: {primary_labels or 'none'}. "
        f"Stress/caution analogs: {stress_labels or 'none'}. "
        f"{' '.join(str(item) for item in observations[:2])} "
        "Use this as scenario discipline only; it is not a probability model, deployment ranking, or capital-action signal."
    )
    return text, "medium", ["tmp/current-regime-analog-match.json"]


def build_payload() -> dict[str, Any]:
    market_state = load(MARKET_STATE)
    macro_regime = load(MACRO_REGIME)
    macro_metrics = load(MACRO_METRICS)
    macro_signal_spine = load(MACRO_SIGNAL_SPINE)
    macro_events = load(MACRO_EVENTS)
    energy_supply = load(MACRO_ENERGY_SUPPLY)
    geopolitical_sweep = load(MACRO_GEOPOLITICAL_SWEEP)
    deployment = load(DEPLOYMENT_SURFACE)
    regime_scores = load(REGIME_SCORES)
    dashboard_validation = load(DASHBOARD_VALIDATION)
    analog_match = load(CURRENT_ANALOG_MATCH)

    pulse, pulse_confidence = judge_pulse(macro_metrics)
    signal_spine_text, signal_spine_confidence, signal_spine_sources = judge_macro_signal_spine(macro_signal_spine)
    eia, rig, energy_structure = judge_energy(market_state, energy_supply)
    dollar = judge_dollar(market_state)
    hot_items, portfolio_implication = judge_geopolitics(macro_events, geopolitical_sweep)
    next_week = judge_next_week(macro_events)
    posture, posture_basis, directive = judge_posture(market_state, macro_regime, deployment)
    scenario_context, scenario_confidence, scenario_sources = judge_scenario_context(analog_match)

    judgments = {
        "pulse_read": {
            "text": pulse,
            "confidence": pulse_confidence,
            "source_basis": ["tmp/macro-metrics-current.json", "tmp/macro-regime.json"],
        },
        "macro_signal_spine_read": {
            "text": signal_spine_text,
            "confidence": signal_spine_confidence,
            "source_basis": signal_spine_sources,
        },
        "eia_inventory": {
            "text": eia["text"],
            "confidence": eia["confidence"],
            "source_basis": eia["source_basis"],
        },
        "rig_count": {
            "text": rig["text"],
            "confidence": rig["confidence"],
            "source_basis": rig["source_basis"],
        },
        "energy_structure": {
            "text": energy_structure,
            "confidence": "medium",
            "source_basis": ["tmp/market-state.json"],
        },
        "dollar_read": {
            "text": dollar,
            "confidence": "medium",
            "source_basis": ["tmp/market-state.json"],
        },
        "geopolitical_hot_items": {
            "text": hot_items["text"],
            "confidence": hot_items["confidence"],
            "source_basis": hot_items["source_basis"],
        },
        "portfolio_implication": {
            "text": portfolio_implication,
            "confidence": "medium",
            "source_basis": ["tmp/macro-event-calendar.json", "tmp/deployment-readiness-surface.json"],
        },
        "next_week_macro_data": {
            "text": next_week,
            "confidence": "medium",
            "source_basis": ["tmp/macro-event-calendar.json"],
        },
        "posture_call": {
            "text": posture_basis,
            "confidence": "medium",
            "source_basis": ["tmp/macro-regime.json", "tmp/market-state.json", "tmp/deployment-readiness-surface.json"],
        },
        "one_line_directive": {
            "text": directive,
            "confidence": "medium",
            "source_basis": ["tmp/deployment-readiness-surface.json", "tmp/regime-scores.json"],
        },
        "scenario_context_panel": {
            "text": scenario_context,
            "confidence": scenario_confidence,
            "source_basis": scenario_sources,
        },
    }

    payload: dict[str, Any] = {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "ok",
        "as_of_date": date.today().isoformat(),
        "authority_boundary": AUTHORITY_BOUNDARY,
        "source_artifacts": [
            {"path": str(path.relative_to(ROOT)), "exists": path.exists()}
            for path in (
                MARKET_STATE,
                MACRO_REGIME,
                MACRO_METRICS,
                MACRO_SIGNAL_SPINE,
                MACRO_EVENTS,
                MACRO_ENERGY_SUPPLY,
                MACRO_GEOPOLITICAL_SWEEP,
                DEPLOYMENT_SURFACE,
                REGIME_SCORES,
                DASHBOARD_VALIDATION,
                CURRENT_ANALOG_MATCH,
            )
        ],
        "machine_evidence_status": {
            "market_state": market_state.get("status"),
            "macro_regime": macro_regime.get("status"),
            "macro_metrics": macro_metrics.get("status"),
            "macro_signal_spine": macro_signal_spine.get("status"),
            "macro_events": macro_events.get("status"),
            "macro_energy_supply": energy_supply.get("status"),
            "macro_geopolitical_sweep": geopolitical_sweep.get("status"),
            "deployment_presentation_allowed": (deployment.get("system") or {}).get("presentation_allowed"),
            "dashboard_overall": dashboard_validation.get("overall"),
            "current_regime_analog_match": analog_match.get("status"),
        },
        "judgments": judgments,
        "recommended_capital_action": {
            "posture": posture,
            "action": "review_only_owner_gated_selective_patience",
            "capital_action_allowed": False,
            "text": directive,
        },
    }
    payload["validation"] = validate(payload)
    if payload["validation"]["status"] != "ok":
        payload["status"] = "error"
    elif payload["validation"]["warnings"]:
        payload["status"] = "warning"
    return payload


def validate(payload: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    if payload.get("schema") != SCHEMA:
        errors.append("schema mismatch")
    boundary = payload.get("authority_boundary") if isinstance(payload.get("authority_boundary"), dict) else {}
    for key, expected in AUTHORITY_BOUNDARY.items():
        if boundary.get(key) is not expected:
            errors.append(f"authority boundary mismatch: {key}")
    judgments = payload.get("judgments")
    if not isinstance(judgments, dict) or len(judgments) < 10:
        errors.append("expected ten judgment fields")
    else:
        for key, judgment in judgments.items():
            if not isinstance(judgment, dict):
                errors.append(f"{key}: judgment is not an object")
                continue
            text = str(judgment.get("text") or "")
            if not text.strip():
                errors.append(f"{key}: empty judgment text")
            if PLACEHOLDER_RE.search(text):
                errors.append(f"{key}: placeholder text remains")
            if FORBIDDEN_ACTION_RE.search(text):
                errors.append(f"{key}: forbidden action language")
            if not judgment.get("source_basis"):
                errors.append(f"{key}: source_basis missing")
            if judgment.get("confidence") not in {"high", "medium", "low"}:
                errors.append(f"{key}: confidence missing/invalid")
    unavailable = [
        key
        for key, judgment in (judgments or {}).items()
        if isinstance(judgment, dict) and str(judgment.get("source_basis") or "").find("missing:") >= 0
    ]
    if unavailable:
        warnings.append(f"manual dependencies remain: {', '.join(unavailable)}")
    return {"status": "ok" if not errors else "error", "errors": errors, "warnings": warnings}


def render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Macro Judgment Draft",
        "",
        f"- Generated: `{payload.get('generated_at_utc')}`",
        f"- Status: `{payload.get('status')}`",
        f"- Validation: `{(payload.get('validation') or {}).get('status')}`",
        f"- Recommended capital posture: `{(payload.get('recommended_capital_action') or {}).get('posture')}`",
        "",
        "## Judgment Fields",
        "",
    ]
    for key, judgment in (payload.get("judgments") or {}).items():
        lines.append(f"### {key.replace('_', ' ').title()}")
        lines.append("")
        lines.append(str(judgment.get("text") or ""))
        lines.append("")
        lines.append(f"- Confidence: `{judgment.get('confidence')}`")
        lines.append(f"- Source basis: {', '.join(judgment.get('source_basis') or [])}")
        lines.append("")
    warnings = (payload.get("validation") or {}).get("warnings") or []
    if warnings:
        lines.extend(["## Warnings", ""])
        lines.extend(f"- {warning}" for warning in warnings)
        lines.append("")
    lines.extend(
        [
            "## Boundary",
            "",
            "Review-only macro interpretation. No forecast/probability claim, portfolio/canon mutation, paper/live execution, capital action, or owner approval inference.",
            "",
        ]
    )
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build review-only macro judgment draft from current artifacts.")
    parser.add_argument("--write", action="store_true", help="write JSON and Markdown outputs")
    parser.add_argument("--validate", action="store_true", help="exit nonzero on validation errors")
    parser.add_argument("--json-out", default=str(DEFAULT_JSON))
    parser.add_argument("--md-out", default=str(DEFAULT_MD))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    payload = build_payload()
    if args.write:
        atomic_write_json(Path(args.json_out), payload)
        atomic_write_text(Path(args.md_out), render_markdown(payload))
    if args.validate and payload["validation"]["status"] != "ok":
        print("\n".join(payload["validation"]["errors"]))
        return 1
    print(payload["status"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
