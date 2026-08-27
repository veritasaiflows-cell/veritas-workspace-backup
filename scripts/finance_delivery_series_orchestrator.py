#!/usr/bin/env python3
"""Build Randall's recurring finance intelligence delivery series.

This is a review-only publishing layer over existing finance proof artifacts.
It packages daily/weekly/monthly market intelligence, investment/performance
state, paper-pilot readiness, and OS KPI/improvement signals into stable JSON,
HTML/PDF shells, and an Excel workbook with charts.

It does not mutate canon/portfolio state, deliver externally, approve capital,
or grant paper/live/account execution authority.
"""
from __future__ import annotations

import argparse
import html
import json
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import xlsxwriter

from market_data_utils import atomic_write_json, atomic_write_text, load_json_artifact

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
OUT = TMP / "finance-delivery-series.json"
XLSX_OUT = TMP / "finance-delivery-series.xlsx"
OUT_DIR = TMP / "finance-delivery-series"

SCHEMA = "veritas.finance_delivery_series.v1"

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "internal_delivery_only": True,
    "customer_or_external_delivery_allowed": False,
    "public_launch_allowed": False,
    "source_licensing_assumed": False,
    "legal_or_compliance_ready": False,
    "forecast_or_probability_claim_allowed_as_certainty": False,
    "capital_deployment_approved": False,
    "trade_or_execution_approved": False,
    "paper_or_live_execution_allowed": False,
    "autonomous_paper_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "money_movement_allowed": False,
    "portfolio_or_canon_mutation_allowed": False,
    "owner_approval_inferred": False,
}

SOURCE_PATHS = {
    "macro_signal_spine": TMP / "macro-signal-spine.json",
    "macro_metrics": TMP / "macro-metrics-current.json",
    "macro_judgment": TMP / "macro-judgment-draft.json",
    "macro_events": TMP / "macro-event-calendar.json",
    "market_readiness": TMP / "market-execution-readiness-cron-hardening.json",
    "weekly_intelligence": TMP / "weekly-intelligence-brief.json",
    "weekly_macro": TMP / "weekly-macro-snapshot.json",
    "canonical_data_plane": TMP / "canonical-finance-data-plane.json",
    "trade_grade_cards": TMP / "trade-grade-decision-cards.json",
    "trade_grade_rollup": TMP / "trade-grade-os-readiness-rollup.json",
    "ticker_performance": TMP / "ticker-monitoring-performance.json",
    "finance_decision_performance": TMP / "finance-decision-performance-digest.json",
    "wf87_readiness": TMP / "wf87-v2-readiness-rollup.json",
    "wf75_packager": TMP / "wf75-deliverable-packager.json",
    "wf75_service_state": TMP / "wf75-service-state-current.json",
    "wf75_operator_console": TMP / "wf75-operator-console.json",
    "wf74_kpis": TMP / "wf74-model-quality-collection-cron-runner.json",
    "pm_control": TMP / "pm-control-packet.json",
    "cron_control": TMP / "cron-control-packet.json",
    "cron_contracts": TMP / "cron-contract-validator.json",
}

DELIVERABLES = {
    "daily_market_read": {
        "title": "Daily Market Read",
        "cadence": "Weekdays after pre-open finance rails",
        "depth": "concise",
        "html": OUT_DIR / "daily-market-read.html",
        "pdf": OUT_DIR / "daily-market-read.pdf",
    },
    "weekly_market_read": {
        "title": "Weekly Market Read",
        "cadence": "Sunday evening / Monday pre-market",
        "depth": "concise",
        "html": OUT_DIR / "weekly-market-read.html",
        "pdf": OUT_DIR / "weekly-market-read.pdf",
    },
    "weekly_investments_performance": {
        "title": "Weekly Investments and Performance",
        "cadence": "Friday post-close / weekend",
        "depth": "concise",
        "html": OUT_DIR / "weekly-investments-performance.html",
        "pdf": OUT_DIR / "weekly-investments-performance.pdf",
    },
    "monthly_investment_direction": {
        "title": "Monthly Investment Direction",
        "cadence": "First weekend of each month",
        "depth": "deep",
        "html": OUT_DIR / "monthly-investment-direction.html",
        "pdf": OUT_DIR / "monthly-investment-direction.pdf",
    },
    "monthly_market_deep_dive": {
        "title": "Monthly Market Deep Dive",
        "cadence": "First weekend of each month",
        "depth": "deep",
        "html": OUT_DIR / "monthly-market-deep-dive.html",
        "pdf": OUT_DIR / "monthly-market-deep-dive.pdf",
    },
}

MODE_DELIVERABLES = {
    "daily": ["daily_market_read"],
    "weekly_market": ["weekly_market_read"],
    "weekly_performance": ["weekly_investments_performance"],
    "monthly": ["monthly_investment_direction", "monthly_market_deep_dive"],
    "all": list(DELIVERABLES.keys()),
}

DELIVERY_SERIES_GATE = {
    "automation_status": "paused_manual_gate",
    "paused_at": "2026-06-17T23:00:00-07:00",
    "pause_reason": "Randall paused recurring cron generation; keep package as SaaS deliverable gate.",
    "manual_generation_allowed": True,
    "cron_generation_allowed": False,
    "saas_gate_role": "Internal quality gate for future SaaS PDF/Excel/CSV deliverables.",
    "gate_requires": [
        "source_freshness_proof",
        "no_leak_no_claim_review",
        "authority_boundary_visible",
        "operator_review",
        "source_licensing_posture",
        "legal_compliance_decision_before_external_delivery",
    ],
}

REQUIRED_FALSE_AUTHORITY = [key for key, value in AUTHORITY_BOUNDARY.items() if value is False]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def esc(value: Any) -> str:
    return html.escape("" if value is None else str(value))


def load_sources() -> dict[str, dict[str, Any]]:
    return {
        key: payload if isinstance((payload := load_json_artifact(path)), dict) else {}
        for key, path in SOURCE_PATHS.items()
    }


def source_probe(path: Path, payload: dict[str, Any]) -> dict[str, Any]:
    validation = as_dict(payload.get("validation"))
    return {
        "path": rel(path),
        "exists": path.exists(),
        "parseable_json": bool(payload),
        "status": payload.get("status") or as_dict(payload.get("summary")).get("status") or "missing",
        "validation_status": validation.get("status"),
        "generated_at_utc": payload.get("generated_at_utc"),
    }


def count_map(rows: list[dict[str, Any]], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        label = str(row.get(key) or "unknown")
        counts[label] = counts.get(label, 0) + 1
    return dict(sorted(counts.items()))


def parse_raw_json(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str) and value.strip():
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, dict) else {}
        except json.JSONDecodeError:
            return {}
    return {}


def canonical_tables(sources: dict[str, dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    tables = as_dict(sources.get("canonical_data_plane", {}).get("tables"))
    clean: dict[str, list[dict[str, Any]]] = {}
    for key, value in tables.items():
        clean[key] = [row for row in as_list(value) if isinstance(row, dict)]
    return clean


def make_lookup(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(row.get("ticker") or "").upper(): row for row in rows if row.get("ticker")}


def build_fundamentals_rows(sources: dict[str, dict[str, Any]], limit: int = 40) -> list[dict[str, Any]]:
    tables = canonical_tables(sources)
    fundamentals = make_lookup(tables.get("fundamental_snapshot", []))
    earnings = make_lookup(tables.get("earnings_catalyst", []))
    analysts = make_lookup(tables.get("analyst_snapshot", []))
    routing = make_lookup(tables.get("routing_state_current", []))
    prices = make_lookup(tables.get("price_technical_current", []))
    queue = make_lookup(tables.get("decision_queue_state", []))
    cards = [
        row for row in as_list(sources.get("trade_grade_cards", {}).get("cards"))
        if isinstance(row, dict)
    ]
    preferred = [
        row for row in cards
        if str(row.get("auto_tier") or "") in {"Tier A", "Tier B"}
    ]
    if not preferred:
        preferred = cards

    rows: list[dict[str, Any]] = []
    for card in preferred[:limit]:
        ticker = str(card.get("ticker") or "").upper()
        f = fundamentals.get(ticker, {})
        e = earnings.get(ticker, {})
        a = analysts.get(ticker, {})
        p = prices.get(ticker, {})
        q = queue.get(ticker, {})
        route = routing.get(ticker, {})
        raw_earnings = parse_raw_json(e.get("raw_json"))
        latest_perf = as_dict(raw_earnings.get("latest_earnings_performance"))
        rows.append(
            {
                "ticker": ticker,
                "name": card.get("name"),
                "tier": card.get("auto_tier") or route.get("auto_tier"),
                "decision_state": card.get("decision_state") or q.get("queue_state"),
                "latest_price": as_dict(card.get("current_price")).get("latest_known_price") or p.get("latest_known_price"),
                "band_status": as_dict(card.get("entry_band")).get("band_status") or p.get("band_status"),
                "fundamentals": f.get("data_quality"),
                "valuation": f.get("valuation_status"),
                "latest_earnings": e.get("latest_earnings_status") or f.get("latest_earnings_status"),
                "business_outlook": e.get("catalyst_status") or "review_required",
                "analyst_view": a.get("rating_summary") or a.get("consensus_rating"),
                "eps_yoy_pct": latest_perf.get("eps_yoy_pct"),
                "revenue_yoy_pct": latest_perf.get("revenue_yoy_pct"),
                "fcf_yoy_pct": latest_perf.get("free_cash_flow_yoy_pct"),
                "bo_note": "BO=business outlook/order-backlog where source-covered; review-required otherwise.",
            }
        )
    return rows


def build_market_read(sources: dict[str, dict[str, Any]]) -> dict[str, Any]:
    macro_signal = sources.get("macro_signal_spine", {})
    macro_metrics = sources.get("macro_metrics", {})
    macro_judgment = sources.get("macro_judgment", {})
    market = sources.get("market_readiness", {})
    ticker_perf = sources.get("ticker_performance", {})
    trade_cards = sources.get("trade_grade_cards", {})
    signal_summary = as_dict(macro_signal.get("summary"))
    metrics_summary = as_dict(macro_metrics.get("summary"))
    market_summary = as_dict(market.get("summary"))
    perf_summary = as_dict(ticker_perf.get("summary"))
    card_summary = as_dict(trade_cards.get("summary"))
    return {
        "macro_posture": signal_summary.get("macro_posture") or "unknown",
        "macro_risk_counts": signal_summary.get("risk_counts") or {},
        "macro_metrics_status": macro_metrics.get("status"),
        "macro_cached_fallback_count": metrics_summary.get("cached_fallback_count"),
        "macro_fetch_failed_count": metrics_summary.get("fetch_failed_count"),
        "market_readiness_status": market.get("status"),
        "market_readiness_critical_count": market_summary.get("critical_count"),
        "market_readiness_warning_count": market_summary.get("warning_count"),
        "macro_judgment_status": macro_judgment.get("status"),
        "decision_state_counts": card_summary.get("decision_state_counts") or {},
        "band_status_counts": perf_summary.get("counts_by_band_status") or {},
        "readiness_direction_counts": perf_summary.get("counts_by_readiness_direction_label") or {},
        "concise_read": [
            f"Macro posture: {signal_summary.get('macro_posture') or 'unknown'}",
            f"Market readiness: {market.get('status')} with {market_summary.get('critical_count', 0)} critical and {market_summary.get('warning_count', 0)} warning",
            f"Trade-grade state: {card_summary.get('card_count', 0)} cards; approval drafts {card_summary.get('approval_card_draft_count', 0)}",
        ],
    }


def build_investments_performance(sources: dict[str, dict[str, Any]]) -> dict[str, Any]:
    perf = sources.get("ticker_performance", {})
    digest = sources.get("finance_decision_performance", {})
    wf87 = sources.get("wf87_readiness", {})
    rollup = sources.get("trade_grade_rollup", {})
    perf_summary = as_dict(perf.get("summary"))
    decision_summary = as_dict(digest.get("wf55_recommendation_outcomes"))
    journal_summary = as_dict(digest.get("wf87_trade_decision_journal"))
    return {
        "ticker_count": perf_summary.get("ticker_count"),
        "workflow_state_counts": perf_summary.get("counts_by_workflow_state") or {},
        "deployment_status_counts": perf_summary.get("counts_by_deployment_status") or {},
        "band_status_counts": perf_summary.get("counts_by_band_status") or {},
        "fail_closed_tickers": perf_summary.get("fail_closed_tickers") or [],
        "blocked_or_review_required_tickers": perf_summary.get("blocked_or_review_required_tickers") or [],
        "decision_performance_status": digest.get("status"),
        "wf55_tracked_ticker_count": decision_summary.get("tracked_ticker_count"),
        "wf87_journal_record_count": journal_summary.get("record_count"),
        "paper_pilot_status": wf87.get("status"),
        "paper_pilot_blockers": wf87.get("blockers") or [],
        "trade_grade_status": rollup.get("status"),
        "trade_grade_validation": as_dict(rollup.get("validation")).get("status"),
    }


def build_saas_smb_interconnect(sources: dict[str, dict[str, Any]]) -> dict[str, Any]:
    wf75 = sources.get("wf75_service_state", {})
    operator = sources.get("wf75_operator_console", {})
    packager = sources.get("wf75_packager", {})
    return {
        "positioning": "Finance OS is the internal truth engine; WF75 is the product-delivery wrapper; SMB remains a service-led adjacent monetization lane.",
        "current_wf75_status": wf75.get("status"),
        "operator_console_status": operator.get("status"),
        "deliverable_packager_status": packager.get("status"),
        "interconnect_plan": [
            "Use the finance delivery series as the internal reference standard for what a customer-safe intelligence product should feel like.",
            "Convert only sanitized, anonymous, source-labeled slices into WF75 customer-safe examples.",
            "Use SMB workflow deliverables as operational proof of packaging discipline, not as finance advice surfaces.",
            "Keep real customer identity, suitability, account, tax, retirement, brokerage, and credential data blocked until later gates.",
        ],
    }


def build_kpis(sources: dict[str, dict[str, Any]]) -> dict[str, Any]:
    pm = sources.get("pm_control", {})
    cron = sources.get("cron_control", {})
    contracts = sources.get("cron_contracts", {})
    wf74 = sources.get("wf74_kpis", {})
    pm_summary = as_dict(pm.get("summary"))
    cron_summary = as_dict(cron.get("summary"))
    contract_summary = as_dict(contracts.get("summary"))
    wf74_summary = as_dict(wf74.get("summary"))
    return {
        "pm_status": pm.get("status"),
        "pm_readiness": as_dict(pm_summary.get("pm_readiness")),
        "top_next_action": as_dict(pm_summary.get("top_next_action")).get("description"),
        "cron_status": cron.get("status"),
        "cron_enabled_jobs": cron_summary.get("enabled_job_count"),
        "cron_blocked_count": cron_summary.get("blocked_count"),
        "cron_escalation_count": cron_summary.get("escalation_signal_count"),
        "cron_contract_count": contract_summary.get("contract_count"),
        "cron_contract_drift": contract_summary.get("drift_count"),
        "wf74_status": wf74.get("status"),
        "wf74_summary": wf74_summary,
    }


def build_scenarios(market_read: dict[str, Any]) -> list[dict[str, Any]]:
    posture = str(market_read.get("macro_posture") or "unknown")
    readiness_warning = int(market_read.get("market_readiness_warning_count") or 0)
    return [
        {
            "scenario": "Base case",
            "probability_view": "moderate",
            "setup": f"{posture}; selective risk-taking only while warnings remain visible.",
            "implication": "Favor review-ready quality names in band; keep no-chase discipline.",
            "invalidation": "Macro risk counts worsen or market readiness becomes critical.",
        },
        {
            "scenario": "Bull case",
            "probability_view": "lower until breadth/freshness improves",
            "setup": "Macro warnings fade, breadth improves, and Tier A/B cards move from monitor/no-chase toward review-ready.",
            "implication": "Prepare approval cards, not automatic deployment.",
            "invalidation": "Freshness or band/stop gates fail.",
        },
        {
            "scenario": "Bear case",
            "probability_view": "meaningful tail risk" if readiness_warning else "monitor",
            "setup": "Data warnings, below-stop names, or macro/geopolitical stress expand.",
            "implication": "Raise evidence burden and keep paper pilot fail-closed.",
            "invalidation": "Risk counts normalize and paper-pilot gates mature.",
        },
    ]


def build_deliverable_catalog() -> dict[str, dict[str, Any]]:
    catalog: dict[str, dict[str, Any]] = {}
    for deliverable_id, spec in DELIVERABLES.items():
        html_path = spec["html"]
        pdf_path = spec["pdf"]
        catalog[deliverable_id] = {
            "title": spec["title"],
            "cadence": spec["cadence"],
            "depth": spec["depth"],
            "automation_status": DELIVERY_SERIES_GATE["automation_status"],
            "html": rel(html_path),
            "pdf": rel(pdf_path),
            "latest_html_exists": html_path.exists(),
            "latest_pdf_exists": pdf_path.exists(),
            "latest_html_modified_utc": (
                datetime.fromtimestamp(html_path.stat().st_mtime, timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
                if html_path.exists() else None
            ),
            "latest_pdf_modified_utc": (
                datetime.fromtimestamp(pdf_path.stat().st_mtime, timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
                if pdf_path.exists() else None
            ),
        }
    return catalog


def build_payload(mode: str = "all") -> dict[str, Any]:
    sources = load_sources()
    market_read = build_market_read(sources)
    investments = build_investments_performance(sources)
    fundamentals = build_fundamentals_rows(sources)
    kpis = build_kpis(sources)
    saas = build_saas_smb_interconnect(sources)
    selected = MODE_DELIVERABLES[mode]
    source_status = {key: source_probe(SOURCE_PATHS[key], sources.get(key, {})) for key in SOURCE_PATHS}
    payload = {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "ok",
        "mode": mode,
        "selected_deliverables": selected,
        "authority_boundary": AUTHORITY_BOUNDARY,
        "delivery_program": {
            "automation_status": DELIVERY_SERIES_GATE["automation_status"],
            "pause_reason": DELIVERY_SERIES_GATE["pause_reason"],
            "daily_depth": "concise",
            "weekly_depth": "concise",
            "monthly_depth": "deep",
            "format_standard": "JSON proof + enhanced Excel workbook + HTML/PDF internal review packets",
            "paper_pilot_posture": "readiness_reporting_only_until_WF87_WF67_owner_gates_clear",
            "saas_deliverable_gate": DELIVERY_SERIES_GATE,
        },
        "cadence": [
            {"id": "daily_market_read", "cadence": "paused; was weekdays 06:50 America/Phoenix", "depth": "concise", "automation_status": DELIVERY_SERIES_GATE["automation_status"]},
            {"id": "weekly_market_read", "cadence": "paused; was Sundays 17:05 America/Phoenix", "depth": "concise", "automation_status": DELIVERY_SERIES_GATE["automation_status"]},
            {"id": "weekly_investments_performance", "cadence": "paused; was Fridays 17:20 America/Phoenix", "depth": "concise", "automation_status": DELIVERY_SERIES_GATE["automation_status"]},
            {"id": "monthly_investment_direction", "cadence": "paused; was first Saturday 08:30 America/Phoenix", "depth": "deep", "automation_status": DELIVERY_SERIES_GATE["automation_status"]},
            {"id": "monthly_market_deep_dive", "cadence": "paused; was first Saturday 08:30 America/Phoenix", "depth": "deep", "automation_status": DELIVERY_SERIES_GATE["automation_status"]},
        ],
        "deliverable_catalog": build_deliverable_catalog(),
        "market_read": market_read,
        "investments_performance": investments,
        "fundamentals_bo_yoy_finance": fundamentals,
        "scenario_outlook": build_scenarios(market_read),
        "saas_smb_interconnect": saas,
        "kpi_improvements": kpis,
        "source_status": source_status,
        "outputs": {
            "json": rel(OUT),
            "excel": rel(XLSX_OUT),
            "deliverables": {
                key: {"html": rel(spec["html"]), "pdf": rel(spec["pdf"])}
                for key, spec in DELIVERABLES.items()
                if key in selected
            },
        },
        "next_safe_action": "Use this series manually as the SaaS deliverable quality gate; do not restore cron generation without a new explicit approval.",
    }
    payload["validation"] = validate_payload(payload)
    payload["status"] = "ok" if payload["validation"]["status"] == "ok" else "blocked"
    return payload


def find_browser() -> str | None:
    for candidate in [
        shutil.which("msedge"),
        shutil.which("chrome"),
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    ]:
        if candidate and Path(candidate).exists():
            return candidate
    return None


def badge(value: Any) -> str:
    text = "unknown" if value in (None, "") else str(value)
    low = text.lower()
    cls = "neutral"
    if low in {"ok", "ready", "clean"}:
        cls = "good"
    elif "blocked" in low or "error" in low or "critical" in low:
        cls = "bad"
    elif "warning" in low or "caution" in low or "stale" in low:
        cls = "warn"
    return f"<span class='badge {cls}'>{esc(text)}</span>"


def bars_from_counts(counts: dict[str, Any], *, max_items: int = 8) -> str:
    pairs = [(str(k), int(v or 0)) for k, v in counts.items()]
    pairs = sorted(pairs, key=lambda item: item[1], reverse=True)[:max_items]
    max_value = max([value for _, value in pairs] or [1])
    lines = []
    for label, value in pairs:
        width = max(4, int((value / max_value) * 100)) if max_value else 4
        lines.append(
            f"<div class='bar-row'><div class='bar-label'>{esc(label)}</div>"
            f"<div class='bar-track'><div class='bar-fill' style='width:{width}%'></div></div>"
            f"<div class='bar-value'>{value}</div></div>"
        )
    return "\n".join(lines) or "<div class='muted'>No count data.</div>"


def table(rows: list[dict[str, Any]], headers: list[str], limit: int = 12) -> str:
    head = "".join(f"<th>{esc(h)}</th>" for h in headers)
    body = []
    for row in rows[:limit]:
        body.append("<tr>" + "".join(f"<td>{esc(row.get(h))}</td>" for h in headers) + "</tr>")
    return f"<table><tr>{head}</tr>{''.join(body)}</table>"


def render_html(payload: dict[str, Any], deliverable_id: str) -> str:
    spec = DELIVERABLES[deliverable_id]
    market = as_dict(payload.get("market_read"))
    inv = as_dict(payload.get("investments_performance"))
    kpis = as_dict(payload.get("kpi_improvements"))
    fundamentals = [row for row in as_list(payload.get("fundamentals_bo_yoy_finance")) if isinstance(row, dict)]
    scenarios = [row for row in as_list(payload.get("scenario_outlook")) if isinstance(row, dict)]
    saas = as_dict(payload.get("saas_smb_interconnect"))
    monthly = spec["depth"] == "deep"
    concise_note = "Concise operating read" if not monthly else "Deep monthly scenario and analytics read"
    extra_sections = ""
    if deliverable_id in {"weekly_investments_performance", "monthly_investment_direction", "monthly_market_deep_dive"}:
        extra_sections += f"""
        <h2>Fundamentals, BO, and YoY Finance</h2>
        {table(fundamentals, ['ticker','tier','decision_state','fundamentals','business_outlook','eps_yoy_pct','revenue_yoy_pct','fcf_yoy_pct'], 14 if monthly else 8)}
        """
    if monthly:
        extra_sections += f"""
        <h2>Scenario Outlook</h2>
        {table(scenarios, ['scenario','probability_view','setup','implication','invalidation'], 5)}
        <h2>SaaS / SMB Interconnect</h2>
        <div class='panel'>{esc(saas.get('positioning'))}</div>
        <ul>{''.join(f'<li>{esc(item)}</li>' for item in as_list(saas.get('interconnect_plan')))}</ul>
        """
    if deliverable_id in {"weekly_investments_performance", "monthly_investment_direction"}:
        extra_sections += f"""
        <h2>Paper Pilot Readiness</h2>
        <div class='panel warn'><strong>Status:</strong> {esc(inv.get('paper_pilot_status'))}. Execution stays blocked until WF87/WF67 gates, shadow threshold, reconciliation maturity, kill switch, and Randall exact approval are clean.</div>
        <ul>{''.join(f'<li>{esc(item)}</li>' for item in as_list(inv.get('paper_pilot_blockers'))[:8])}</ul>
        """

    return f"""<!doctype html>
<html><head><meta charset="utf-8"><title>{esc(spec['title'])}</title>
<style>
@page {{ size: Letter; margin: .45in; }}
body {{ font-family: Arial, Helvetica, sans-serif; color:#162033; margin:0; font-size:10px; line-height:1.34; }}
h1 {{ margin:0; font-size:25px; color:#0f2f55; }}
h2 {{ margin:14px 0 6px; font-size:16px; color:#0f2f55; border-bottom:1px solid #d8e2ef; padding-bottom:4px; }}
.top {{ display:flex; justify-content:space-between; gap:20px; border-bottom:3px solid #12345c; padding-bottom:10px; margin-bottom:10px; }}
.kicker {{ color:#60748c; text-transform:uppercase; letter-spacing:.12em; font-weight:bold; font-size:8px; }}
.grid {{ display:grid; grid-template-columns:repeat(4,1fr); gap:8px; margin:8px 0; }}
.metric {{ border:1px solid #d8e2ef; background:#f8fafc; border-radius:8px; padding:8px; min-height:.62in; }}
.label {{ font-size:7.5px; color:#60748c; text-transform:uppercase; letter-spacing:.08em; }}
.value {{ font-size:13px; font-weight:bold; margin-top:4px; color:#0f2f55; }}
.panel {{ border:1px solid #d8e2ef; border-radius:8px; padding:8px; background:#f8fafc; margin:7px 0; }}
.warn {{ background:#fff8df; border-color:#e0b13a; }}
.badge {{ border-radius:999px; padding:2px 7px; background:#e8eef7; font-weight:bold; font-size:8px; }}
.badge.good {{ background:#e4f4ea; color:#176238; }} .badge.warn {{ background:#fff0c6; color:#765200; }} .badge.bad {{ background:#fde8e8; color:#8f1d1d; }}
.bar-row {{ display:grid; grid-template-columns: 1.4in 1fr .35in; gap:8px; align-items:center; margin:5px 0; }}
.bar-track {{ height:11px; background:#e6edf5; border-radius:999px; overflow:hidden; }} .bar-fill {{ height:11px; background:#2563a6; }}
table {{ width:100%; border-collapse:collapse; table-layout:fixed; margin:7px 0; }} th,td {{ border:1px solid #d8e2ef; padding:5px; vertical-align:top; word-wrap:break-word; }} th {{ background:#12345c; color:white; text-align:left; }}
.muted {{ color:#60748c; }}
li {{ margin:3px 0; }}
</style></head>
<body>
<div class="top"><div><div class="kicker">{esc(concise_note)} | {esc(spec['cadence'])}</div><h1>{esc(spec['title'])}</h1><div class="muted">Generated {esc(payload.get('generated_at_utc'))}</div></div><div>{badge(payload.get('status'))}</div></div>
<div class="panel"><strong>Boundary:</strong> internal review only. Scenario outlook is not certainty, advice, approval, or execution authority.</div>
<div class="grid">
  <div class="metric"><div class="label">Macro posture</div><div class="value">{esc(market.get('macro_posture'))}</div></div>
  <div class="metric"><div class="label">Market readiness</div><div class="value">{badge(market.get('market_readiness_status'))}</div></div>
  <div class="metric"><div class="label">Trade-grade</div><div class="value">{badge(inv.get('trade_grade_status'))}</div></div>
  <div class="metric"><div class="label">Paper pilot</div><div class="value">{badge(inv.get('paper_pilot_status'))}</div></div>
</div>
<h2>Market Read</h2>
<ul>{''.join(f'<li>{esc(item)}</li>' for item in as_list(market.get('concise_read')))}</ul>
<div class="grid"><div class="panel"><strong>Macro risk counts</strong>{bars_from_counts(as_dict(market.get('macro_risk_counts')))}</div><div class="panel"><strong>Band status</strong>{bars_from_counts(as_dict(inv.get('band_status_counts')))}</div><div class="panel"><strong>Deployment status</strong>{bars_from_counts(as_dict(inv.get('deployment_status_counts')))}</div><div class="panel"><strong>KPI</strong><br>PM {badge(kpis.get('pm_status'))}<br>Cron {badge(kpis.get('cron_status'))}<br>Contracts drift {esc(kpis.get('cron_contract_drift'))}</div></div>
{extra_sections}
</body></html>"""


def render_pdf(html_path: Path, pdf_path: Path) -> dict[str, Any]:
    browser = find_browser()
    if not browser:
        return {"status": "pdf_unavailable", "reason": "no headless Edge/Chrome browser found"}
    cmd = [
        browser,
        "--headless=new",
        "--disable-gpu",
        "--no-first-run",
        "--disable-extensions",
        f"--print-to-pdf={pdf_path}",
        str(html_path),
    ]
    proc = subprocess.run(cmd, cwd=str(ROOT), text=True, capture_output=True, timeout=90)
    ok = proc.returncode == 0 and pdf_path.exists() and pdf_path.stat().st_size > 0
    return {
        "status": "ok" if ok else "pdf_failed",
        "returncode": proc.returncode,
        "browser": browser,
        "pdf_size_bytes": pdf_path.stat().st_size if pdf_path.exists() else 0,
        "stderr_tail": proc.stderr[-800:],
    }


def write_outputs(payload: dict[str, Any], selected: list[str], *, html_only: bool = False) -> dict[str, Any]:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    results: dict[str, Any] = {}
    for deliverable_id in selected:
        spec = DELIVERABLES[deliverable_id]
        html_text = render_html(payload, deliverable_id)
        atomic_write_text(spec["html"], html_text)
        pdf_result = {"status": "skipped_html_only"}
        if not html_only:
            pdf_result = render_pdf(spec["html"], spec["pdf"])
        results[deliverable_id] = {
            "html": rel(spec["html"]),
            "pdf": rel(spec["pdf"]),
            "html_size_bytes": spec["html"].stat().st_size if spec["html"].exists() else 0,
            "pdf_result": pdf_result,
        }
    return results


def write_sheet(workbook: xlsxwriter.Workbook, name: str, rows: list[dict[str, Any]]) -> Any:
    sheet = workbook.add_worksheet(name[:31])
    title = workbook.add_format({"bold": True, "font_size": 14, "font_color": "#12345C"})
    header = workbook.add_format({"bold": True, "bg_color": "#D9EAF7", "border": 1})
    cell = workbook.add_format({"border": 1, "valign": "top", "text_wrap": True})
    sheet.write(0, 0, name, title)
    if not rows:
        sheet.write(2, 0, "No rows", cell)
        return sheet
    headers = list(rows[0].keys())
    for col, key in enumerate(headers):
        sheet.write(2, col, key, header)
        sheet.set_column(col, col, min(max(len(key) + 3, 12), 34))
    for r, row in enumerate(rows, start=3):
        for c, key in enumerate(headers):
            value = row.get(key)
            if isinstance(value, (dict, list)):
                value = json.dumps(value, sort_keys=True)
            sheet.write(r, c, "" if value is None else value, cell)
    sheet.freeze_panes(3, 0)
    sheet.autofilter(2, 0, 2 + len(rows), len(headers) - 1)
    return sheet


def count_rows(title: str, counts: dict[str, Any]) -> list[dict[str, Any]]:
    return [{"metric": title, "label": str(k), "count": int(v or 0)} for k, v in counts.items()]


def write_workbook(payload: dict[str, Any], out: Path = XLSX_OUT) -> dict[str, Any]:
    out.parent.mkdir(parents=True, exist_ok=True)
    workbook = xlsxwriter.Workbook(str(out))
    workbook.set_properties({
        "title": "Finance Delivery Series",
        "subject": "Internal review-only market, investment, performance, and KPI delivery series",
        "author": "Veritas",
        "comments": "No capital/execution/customer/public authority.",
    })
    market = as_dict(payload.get("market_read"))
    inv = as_dict(payload.get("investments_performance"))
    kpis = as_dict(payload.get("kpi_improvements"))

    overview = [
        {"field": "generated_at_utc", "value": payload.get("generated_at_utc")},
        {"field": "mode", "value": payload.get("mode")},
        {"field": "status", "value": payload.get("status")},
        {"field": "daily_depth", "value": "concise"},
        {"field": "weekly_depth", "value": "concise"},
        {"field": "monthly_depth", "value": "deep"},
        {"field": "paper_pilot", "value": inv.get("paper_pilot_status")},
        {"field": "next_safe_action", "value": payload.get("next_safe_action")},
    ]
    write_sheet(workbook, "Overview", overview)
    write_sheet(workbook, "Cadence", [row for row in as_list(payload.get("cadence")) if isinstance(row, dict)])
    write_sheet(workbook, "Fundamentals BO YoY", [row for row in as_list(payload.get("fundamentals_bo_yoy_finance")) if isinstance(row, dict)])
    write_sheet(workbook, "Scenarios", [row for row in as_list(payload.get("scenario_outlook")) if isinstance(row, dict)])
    write_sheet(workbook, "SaaS SMB", [{"item": item} for item in as_list(as_dict(payload.get("saas_smb_interconnect")).get("interconnect_plan"))])
    write_sheet(workbook, "Authority Gates", [{"gate": k, "value": v} for k, v in as_dict(payload.get("authority_boundary")).items()])
    write_sheet(workbook, "Sources", [dict({"key": k}, **as_dict(v)) for k, v in as_dict(payload.get("source_status")).items()])

    chart_rows = []
    chart_rows.extend(count_rows("macro_risk", as_dict(market.get("macro_risk_counts"))))
    chart_rows.extend(count_rows("band_status", as_dict(inv.get("band_status_counts"))))
    chart_rows.extend(count_rows("deployment_status", as_dict(inv.get("deployment_status_counts"))))
    chart_rows.extend(count_rows("decision_state", as_dict(market.get("decision_state_counts"))))
    chart_sheet = write_sheet(workbook, "Charts Data", chart_rows)
    dash = workbook.add_worksheet("Dashboard")
    dash.write(0, 0, "Finance Delivery Dashboard", workbook.add_format({"bold": True, "font_size": 16, "font_color": "#12345C"}))
    dash.write(2, 0, f"Macro posture: {market.get('macro_posture')}")
    dash.write(3, 0, f"Paper pilot: {inv.get('paper_pilot_status')}")
    dash.write(4, 0, f"PM status: {kpis.get('pm_status')} | Cron status: {kpis.get('cron_status')} | Contract drift: {kpis.get('cron_contract_drift')}")

    if chart_rows:
        metric_offsets: dict[str, tuple[int, int]] = {}
        for idx, row in enumerate(chart_rows, start=3):
            metric_offsets.setdefault(str(row["metric"]), (idx, idx))
            start, _ = metric_offsets[str(row["metric"])]
            metric_offsets[str(row["metric"])] = (start, idx)
        positions = {
            "macro_risk": "A7",
            "band_status": "J7",
            "deployment_status": "A23",
            "decision_state": "J23",
        }
        for metric, cell in positions.items():
            if metric not in metric_offsets:
                continue
            start, end = metric_offsets[metric]
            chart = workbook.add_chart({"type": "column"})
            chart.add_series({
                "name": metric,
                "categories": ["Charts Data", start, 1, end, 1],
                "values": ["Charts Data", start, 2, end, 2],
                "fill": {"color": "#2563A6"},
            })
            chart.set_title({"name": metric.replace("_", " ").title()})
            chart.set_legend({"none": True})
            dash.insert_chart(cell, chart, {"x_scale": 1.25, "y_scale": 1.0})

    workbook.close()
    return {"path": rel(out), "exists": out.exists(), "size_bytes": out.stat().st_size if out.exists() else 0}


def validate_payload(payload: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    if payload.get("schema") != SCHEMA:
        errors.append("schema_mismatch")
    boundary = as_dict(payload.get("authority_boundary"))
    for key in REQUIRED_FALSE_AUTHORITY:
        if boundary.get(key) is not False:
            errors.append(f"authority_{key}_not_false")
    for key in ("review_only", "internal_delivery_only"):
        if boundary.get(key) is not True:
            errors.append(f"authority_{key}_not_true")
    for key, item in as_dict(payload.get("source_status")).items():
        if not as_dict(item).get("exists"):
            errors.append(f"missing_source:{key}")
        elif not as_dict(item).get("parseable_json"):
            errors.append(f"unparseable_source:{key}")
    if not as_list(payload.get("fundamentals_bo_yoy_finance")):
        errors.append("missing_fundamentals_bo_yoy_rows")
    if as_dict(payload.get("investments_performance")).get("paper_pilot_status") != "phase_a_hardening_implemented_runtime_blocked":
        warnings.append("paper_pilot_status_changed_review_required")
    return {"status": "error" if errors else "warning" if warnings else "ok", "errors": errors, "warnings": warnings}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=sorted(MODE_DELIVERABLES), default="all")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--html-only", action="store_true")
    parser.add_argument("--out", type=Path, default=OUT)
    parser.add_argument("--xlsx-out", type=Path, default=XLSX_OUT)
    args = parser.parse_args()

    payload = build_payload(args.mode)
    selected = MODE_DELIVERABLES[args.mode]
    workbook = write_workbook(payload, args.xlsx_out if args.xlsx_out.is_absolute() else ROOT / args.xlsx_out)
    render_results = write_outputs(payload, selected, html_only=args.html_only)
    payload["workbook"] = workbook
    payload["render_results"] = render_results
    validation = validate_payload(payload) if args.validate else {"status": "not_run", "errors": [], "warnings": []}
    render_errors = [
        f"{key}:{as_dict(result.get('pdf_result')).get('status')}"
        for key, result in render_results.items()
        if not args.html_only and as_dict(result.get("pdf_result")).get("status") != "ok"
    ]
    validation["errors"].extend(render_errors)
    validation["status"] = "error" if validation["errors"] else "warning" if validation["warnings"] else "ok"
    payload["validation"] = validation
    payload["status"] = "ok" if validation["status"] == "ok" else "blocked"
    if args.write:
        out = args.out if args.out.is_absolute() else ROOT / args.out
        atomic_write_json(out, payload)
    print(
        f"status={payload['status']} mode={args.mode} "
        f"deliverables={len(selected)} workbook={workbook.get('path')} validation={validation['status']}"
    )
    return 0 if payload["status"] == "ok" else 2


if __name__ == "__main__":
    raise SystemExit(main())
