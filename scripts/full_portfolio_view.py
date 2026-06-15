from __future__ import annotations

from board_state_contract import legacy_state
import argparse
import html
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

WORKSPACE = Path(__file__).resolve().parents[1]
TMP = WORKSPACE / "tmp"
OUT_JSON = TMP / "full-portfolio-view.json"
OUT_MD = TMP / "full-portfolio-view.md"
OUT_HTML = TMP / "full-portfolio-view.html"
SCHEMA_VERSION = 1

ARTIFACTS = {
    "portfolio_config": TMP / "portfolio-config.json",
    "technical_refresh": TMP / "technical-refresh.json",
    "deployment_check": TMP / "deployment-check.json",
    "trigger_sheet": TMP / "trigger-sheet.json",
    "regime_scores": TMP / "regime-scores.json",
    "board_canon_guardrail": TMP / "board-canon-guardrail.json",
    "daily_executive_brief": TMP / "daily-executive-brief.json",
    "market_state": TMP / "market-state.json",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat(timespec="seconds").replace("+00:00", "Z")


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def records_by_ticker(data: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(record.get("ticker")): record
        for record in data.get("records", []) or []
        if isinstance(record, dict) and record.get("ticker")
    }


def money(value: Any) -> str:
    try:
        return f"{float(value):.2f}"
    except (TypeError, ValueError):
        return "-"


def pct(value: Any) -> str:
    try:
        return f"{float(value):.1f}%"
    except (TypeError, ValueError):
        return "-"


def first_present(*values: Any) -> Any:
    for value in values:
        if value is not None and value != "":
            return value
    return None


def source_artifact(name: str, path: Path, data: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": name,
        "path": str(path.relative_to(WORKSPACE)),
        "exists": path.exists(),
        "status": data.get("status"),
        "generated_at_utc": data.get("generated_at_utc") or data.get("generated_at"),
        "last_trading_day": data.get("last_trading_day") or data.get("market_data_as_of") or data.get("brief_date"),
        "stale_after_hours": data.get("stale_after_hours"),
        "expected_update_window": data.get("expected_update_window"),
    }


def portfolio_weight_index(config: dict[str, Any]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    portfolio = config.get("portfolio", {}) if isinstance(config.get("portfolio"), dict) else {}
    for sleeve in ("core", "tactical", "speculative"):
        for item in portfolio.get(sleeve, []) or []:
            if isinstance(item, dict) and item.get("ticker"):
                out[str(item["ticker"])] = {
                    "sleeve": sleeve,
                    "draft_weight": item.get("weight"),
                    "portfolio_thesis": item.get("thesis"),
                    "portfolio_entry": item.get("entry"),
                    "portfolio_stop": item.get("stop") or item.get("risk"),
                    "portfolio_sector": item.get("sector"),
                }
    return out


def guardrail_risk_index(data: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(record.get("ticker")): record
        for record in data.get("risks", []) or []
        if isinstance(record, dict) and record.get("ticker")
    }


def daily_band_behavior_index(data: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(record.get("ticker")): record
        for record in data.get("qualified_band_behavior", []) or []
        if isinstance(record, dict) and record.get("ticker")
    }


def action_bucket(record: dict[str, Any]) -> str:
    if record.get("below_stop"):
        return "do_not_touch"
    state = str(first_present(record.get("trigger_action_state"), record.get("deployment_action_state"), record.get("regime_stance"), "") or "").lower()
    if "deployable now" in state:
        return "deployable_now_review_only"
    if "almost" in state:
        return "prepare_or_wait"
    if "watch" in state:
        return "watch"
    if "bench" in state or "repair" in state or "do not" in state:
        return "bench_or_repair"
    return "monitor"


def build_records(artifacts: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    config = artifacts["portfolio_config"]
    technical = records_by_ticker(artifacts["technical_refresh"])
    deployment = records_by_ticker(artifacts["deployment_check"])
    trigger = records_by_ticker(artifacts["trigger_sheet"])
    regime = records_by_ticker(artifacts["regime_scores"])
    risks = guardrail_risk_index(artifacts["board_canon_guardrail"])
    band_behavior = daily_band_behavior_index(artifacts["daily_executive_brief"])
    tracked = config.get("tracked_universe", {}) if isinstance(config.get("tracked_universe"), dict) else {}
    bands = config.get("entry_bands", {}) if isinstance(config.get("entry_bands"), dict) else {}
    weights = portfolio_weight_index(config)
    tickers = sorted(set(tracked) | set(weights) | set(technical) | set(deployment) | set(trigger) | set(regime))

    records: list[dict[str, Any]] = []
    for ticker in tickers:
        tcfg = tracked.get(ticker, {}) if isinstance(tracked.get(ticker), dict) else {}
        weight = weights.get(ticker, {})
        tech = technical.get(ticker, {})
        dep = deployment.get(ticker, {})
        trig = trigger.get(ticker, {})
        reg = regime.get(ticker, {})
        risk = risks.get(ticker, {})
        band = bands.get(ticker, {}) if isinstance(bands.get(ticker), dict) else {}
        row: dict[str, Any] = {
            "ticker": ticker,
            "sleeve": first_present(weight.get("sleeve"), tcfg.get("portfolio_role"), reg.get("role")),
            "draft_weight": weight.get("draft_weight"),
            "sector": first_present(tcfg.get("sector"), weight.get("portfolio_sector"), reg.get("sector")),
            "coverage_lane": tcfg.get("coverage_lane"),
            "coverage_tier": tcfg.get("coverage_tier"),
            "workflow_state": first_present(legacy_state(trig, "workflow_state"), legacy_state(tcfg, "workflow_state")),
            "sizing_tier": first_present(tcfg.get("sizing_tier"), trig.get("size_tier")),
            "thesis_status": first_present(tcfg.get("thesis_status"), reg.get("thesis_status"), weight.get("portfolio_thesis")),
            "macro_fit": tcfg.get("macro_fit"),
            "trigger_condition": first_present(trig.get("technical_trigger"), tcfg.get("trigger_condition"), weight.get("portfolio_entry")),
            "close": first_present(tech.get("close"), dep.get("close"), trig.get("close"), reg.get("close")),
            "data_date": first_present(tech.get("data_date"), dep.get("data_date"), trig.get("data_date")),
            "ma20": first_present(tech.get("ma20"), dep.get("ma20")),
            "ma50": first_present(tech.get("ma50"), dep.get("ma50")),
            "ma200": first_present(tech.get("ma200"), dep.get("ma200")),
            "ma_posture": first_present(tech.get("ma_posture"), dep.get("ma_posture"), trig.get("ma_posture")),
            "entry_band": {
                "low": first_present(band.get("low"), (trig.get("entry_band") or {}).get("low") if isinstance(trig.get("entry_band"), dict) else None),
                "high": first_present(band.get("high"), (trig.get("entry_band") or {}).get("high") if isinstance(trig.get("entry_band"), dict) else None),
                "label": first_present(band.get("label"), (trig.get("entry_band") or {}).get("label") if isinstance(trig.get("entry_band"), dict) else None),
            },
            "stop": first_present(band.get("stop"), trig.get("invalidation"), risk.get("stop")),
            "in_entry_band": first_present(tech.get("in_entry_band"), dep.get("in_entry_band"), trig.get("in_entry_band")),
            "below_stop": bool(first_present(tech.get("below_stop"), dep.get("below_stop"), trig.get("below_stop"), reg.get("below_stop"), risk.get("risk_state") == "below_stop")),
            "near_stop": risk.get("risk_state") == "near_stop",
            "deployment_action_state": legacy_state(dep, "action_state"),
            "deployment_reason": dep.get("reason"),
            "trigger_action_state": legacy_state(trig, "action_state"),
            "trigger_reason": trig.get("why"),
            "regime_stance": reg.get("stance"),
            "regime_total": reg.get("total"),
            "regime_scores": {
                "regime_fit": reg.get("regime_fit"),
                "technical_posture": reg.get("technical_posture"),
                "catalyst_risk": reg.get("catalyst_risk"),
                "fundamental_conviction": reg.get("fundamental_conviction"),
            },
            "band_note": reg.get("band_note"),
            "earnings_blocked": bool(first_present(dep.get("earnings_blocked"), trig.get("earnings_blocked"), False)),
            "catalyst_blocker": trig.get("catalyst_blocker"),
            "days_to_earnings": first_present(trig.get("days_to_earnings"), reg.get("days_to_earnings")),
            "next_earnings_date": trig.get("next_earnings_date"),
            "band_behavior": band_behavior.get(ticker),
            "risk_alert": risk,
            "source_provenance": sorted([
                name for name, source in {
                    "portfolio_config": tcfg or weight,
                    "technical_refresh": tech,
                    "deployment_check": dep,
                    "trigger_sheet": trig,
                    "regime_scores": reg,
                    "board_canon_guardrail": risk,
                    "daily_executive_brief": band_behavior.get(ticker),
                }.items() if source
            ]),
        }
        row["action_bucket"] = action_bucket(row)
        records.append(row)
    return records


def sector_summary(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    totals: dict[str, float] = {}
    names: dict[str, list[str]] = {}
    for record in records:
        sector = str(record.get("sector") or "Unclassified")
        try:
            weight = float(record.get("draft_weight") or 0)
        except (TypeError, ValueError):
            weight = 0.0
        totals[sector] = totals.get(sector, 0.0) + weight
        names.setdefault(sector, []).append(record["ticker"])
    return [
        {"sector": sector, "draft_weight_total": round(total, 2), "tickers": sorted(names.get(sector, []))}
        for sector, total in sorted(totals.items(), key=lambda item: (-item[1], item[0]))
    ]


def build_market_view(artifacts: dict[str, dict[str, Any]], records: list[dict[str, Any]]) -> dict[str, Any]:
    config = artifacts["portfolio_config"]
    market = artifacts["market_state"]
    portfolio = config.get("portfolio", {}) if isinstance(config.get("portfolio"), dict) else {}
    market_data = market.get("data", {}) if isinstance(market.get("data"), dict) else {}
    rates = market_data.get("treasuries", {}) if isinstance(market_data.get("treasuries"), dict) else {}
    energy = market_data.get("energy", {}) if isinstance(market_data.get("energy"), dict) else {}
    credit = market_data.get("credit", {}) if isinstance(market_data.get("credit"), dict) else {}
    breadth = market_data.get("breadth", {}) if isinstance(market_data.get("breadth"), dict) else {}
    themes = [
        {
            "theme": "AI power / electrification",
            "read": "still the cleanest active theme, but every name remains governed by current band position, no-chase discipline, and explicit owner review",
            "tickers": [record["ticker"] for record in records if record.get("ticker") in {"ETN", "VRT", "NVDA", "MSFT", "GOOG"}],
        },
        {
            "theme": "Quality tech discipline",
            "read": "direct Tech draft weight is at the 25% cap; do not let theme strength override entry bands, catalyst timing, or owner-gated deployment",
            "tickers": [record["ticker"] for record in records if record.get("sector") == "Tech"],
        },
        {
            "theme": "Financials with stop discipline",
            "read": "JPM and GS require live band/stop discipline; any deployable label is review-only and does not imply sizing, cash, sleeve, or trade authority",
            "tickers": [record["ticker"] for record in records if record.get("sector") == "Financials"],
        },
        {
            "theme": "Energy / inflation risk without deployable energy setup",
            "read": "oil remains macro-relevant, but energy exposure still needs individual setup repair, stop discipline, and owner review before any deployment change",
            "tickers": [record["ticker"] for record in records if record.get("sector") == "Energy"],
        },
    ]
    return {
        "portfolio_posture": portfolio.get("posture"),
        "portfolio_regime": portfolio.get("regime"),
        "market_state_status": market.get("status"),
        "market_state_last_trading_day": market.get("last_trading_day"),
        "market_state_warnings": market.get("warnings", []),
        "macro_points": {
            "spx": (market_data.get("equities") or {}).get("spx") if isinstance(market_data.get("equities"), dict) else None,
            "vix": (market_data.get("volatility") or {}).get("vix") if isinstance(market_data.get("volatility"), dict) else None,
            "ten_year": rates.get("10y"),
            "curve_2s10s_bps": rates.get("curve_2s10s_bps"),
            "brent": energy.get("brent"),
            "wti": energy.get("wti"),
            "credit_stress": credit.get("stress_regime"),
            "breadth_regime": breadth.get("participation_regime"),
        },
        "current_investment_themes": themes,
        "fresh_research_rule": "Use this market/theme block only when market_state is fresh for the requested window; if stale, partial, contradictory, or decision-critical, verify with live web/primary sources before making a capital recommendation.",
    }


def build_report(window: str) -> dict[str, Any]:
    artifacts = {name: read_json(path) for name, path in ARTIFACTS.items()}
    records = build_records(artifacts)
    market_data_as_of = first_present(
        artifacts["deployment_check"].get("last_trading_day"),
        artifacts["technical_refresh"].get("last_trading_day"),
        artifacts["trigger_sheet"].get("last_trading_day"),
        artifacts["regime_scores"].get("last_trading_day"),
        artifacts["daily_executive_brief"].get("market_data_as_of"),
    )
    buckets: dict[str, list[str]] = {}
    for record in records:
        buckets.setdefault(str(record.get("action_bucket") or "monitor"), []).append(record["ticker"])
    summary = {
        "record_count": len(records),
        "market_data_as_of": market_data_as_of,
        "deployable_now_review_only": sorted(buckets.get("deployable_now_review_only", [])),
        "prepare_or_wait": sorted(buckets.get("prepare_or_wait", [])),
        "watch": sorted(buckets.get("watch", [])),
        "bench_or_repair": sorted(buckets.get("bench_or_repair", [])),
        "do_not_touch": sorted(buckets.get("do_not_touch", [])),
        "monitor": sorted(buckets.get("monitor", [])),
        "below_stop": sorted([record["ticker"] for record in records if record.get("below_stop")]),
        "near_stop": sorted([record["ticker"] for record in records if record.get("near_stop")]),
        "sector_summary": sector_summary(records),
    }
    market_view = build_market_view(artifacts, records)
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": utc_now(),
        "window": window,
        "market_data_as_of": market_data_as_of,
        "source_artifacts": [source_artifact(name, path, artifacts[name]) for name, path in ARTIFACTS.items()],
        "authority": {
            "posture": "review_only_full_portfolio_view",
            "canonical_mutation_allowed": False,
            "portfolio_mutation_allowed": False,
            "deployment_state_mutation_allowed": False,
            "owner_approval_granted": False,
            "sizing_or_weight_change_allowed": False,
            "trade_execution_allowed": False,
            "generated_report_is_canonical": False,
        },
        "summary": summary,
        "market_view": market_view,
        "records": records,
        "rendered_outputs": {
            "json": str(OUT_JSON.relative_to(WORKSPACE)),
            "markdown": str(OUT_MD.relative_to(WORKSPACE)),
            "html": str(OUT_HTML.relative_to(WORKSPACE)),
        },
        "render_policy": {
            "json_is_machine_report_truth": True,
            "markdown_optional_render": True,
            "html_optional_render": True,
            "default_write_json_only": True,
            "legacy_sidecars_require_explicit_flags": True,
            "proof_deletion_allowed": False,
            "archive_or_cleanup_allowed": False,
            "authority": "review_only_report_not_canon_not_approval_not_execution",
        },
    }


def text_bar(value: Any, max_value: float = 25.0, width: int = 20) -> str:
    try:
        val = max(0.0, float(value))
    except (TypeError, ValueError):
        val = 0.0
    filled = min(width, round((val / max_value) * width)) if max_value else 0
    return "█" * filled + "░" * (width - filled)


def render_md(report: dict[str, Any]) -> str:
    summary = report["summary"]
    lines = ["# Full Portfolio View", ""]
    lines.append(f"- Generated: `{report['generated_at_utc']}`")
    lines.append(f"- Window: `{report['window']}`")
    lines.append(f"- Market data as of: **{report.get('market_data_as_of') or 'unknown'}**")
    lines.append("- Authority: **review-only machine report; not canonical; no portfolio mutation, approval, sizing, execution entitlement, or trade authority**")
    lines.append("")
    lines.append("## Portfolio verdict dashboard")
    lines.append(f"- Deployable now / review-only: {', '.join(summary['deployable_now_review_only']) or '-'}")
    lines.append(f"- Prepare / wait: {', '.join(summary['prepare_or_wait']) or '-'}")
    lines.append(f"- Do not touch: {', '.join(summary['do_not_touch']) or '-'}")
    lines.append(f"- Below stop: {', '.join(summary['below_stop']) or '-'}")
    lines.append(f"- Near stop: {', '.join(summary['near_stop']) or '-'}")
    lines.append("")
    market_view = report.get("market_view", {}) if isinstance(report.get("market_view"), dict) else {}
    lines.append("## Market regime and current investment theme")
    lines.append(f"- Portfolio posture: {market_view.get('portfolio_posture') or '-'}")
    lines.append(f"- Portfolio regime: {market_view.get('portfolio_regime') or '-'}")
    macro = market_view.get("macro_points", {}) if isinstance(market_view.get("macro_points"), dict) else {}
    lines.append(f"- Macro tape: SPX {money(macro.get('spx'))}, VIX {money(macro.get('vix'))}, 10Y {money(macro.get('ten_year'))}, Brent {money(macro.get('brent'))}, credit stress `{macro.get('credit_stress') or '-'}`, breadth `{macro.get('breadth_regime') or '-'}`")
    for theme in market_view.get("current_investment_themes", []) or []:
        lines.append(f"- **{theme.get('theme')}** — {theme.get('read')} ({', '.join(theme.get('tickers') or []) or '-'})")
    if market_view.get("market_state_warnings"):
        lines.append(f"- Freshness warnings: {'; '.join(str(w) for w in market_view.get('market_state_warnings') or [])}")
    lines.append("")
    lines.append("## Sector exposure graphic")
    lines.append("")
    lines.append("| Sector | Draft weight | Graphic | Names |")
    lines.append("|---|---:|---|---|")
    for sector in summary["sector_summary"]:
        lines.append(f"| {sector['sector']} | {pct(sector['draft_weight_total'])} | `{text_bar(sector['draft_weight_total'])}` | {', '.join(sector['tickers'])} |")
    lines.append("")
    lines.append("## Name-level table")
    lines.append("")
    lines.append("| Ticker | Sleeve | Weight | Sector | Close | Band | Stop | Action | Risk |")
    lines.append("|---|---|---:|---|---:|---|---:|---|---|")
    for record in report["records"]:
        band = record.get("entry_band") or {}
        band_label = band.get("label") or f"{money(band.get('low'))}-{money(band.get('high'))}"
        risk = "below stop" if record.get("below_stop") else ("near stop" if record.get("near_stop") else "-")
        lines.append(
            f"| {record['ticker']} | {record.get('sleeve') or '-'} | {pct(record.get('draft_weight'))} | {record.get('sector') or '-'} | {money(record.get('close'))} | {band_label} | {money(record.get('stop'))} | {record.get('action_bucket')} | {risk} |"
        )
    lines.append("")
    return "\n".join(lines)


def svg_sector_chart(sectors: list[dict[str, Any]]) -> str:
    width = 760
    row_h = 28
    height = max(90, 35 + len(sectors) * row_h)
    bars = [f'<svg viewBox="0 0 {width} {height}" width="100%" height="{height}" role="img" aria-label="Sector exposure bars">']
    bars.append('<style>text{font-family:Inter,Segoe UI,Arial,sans-serif;font-size:13px}.bar{fill:#3b82f6}.cap{stroke:#ef4444;stroke-width:2}.muted{fill:#64748b}</style>')
    bars.append('<text x="0" y="18" font-weight="700">Draft sector exposure vs 25% cap</text>')
    for idx, sector in enumerate(sectors):
        y = 38 + idx * row_h
        weight = float(sector.get("draft_weight_total") or 0)
        bar_w = min(500, max(0, weight / 25.0 * 500))
        bars.append(f'<text x="0" y="{y + 14}">{html.escape(str(sector["sector"]))}</text>')
        bars.append(f'<rect x="190" y="{y}" width="{bar_w:.1f}" height="18" rx="4" class="bar"/>')
        bars.append(f'<line x1="690" y1="{y-2}" x2="690" y2="{y+21}" class="cap"/>')
        bars.append(f'<text x="705" y="{y + 14}" class="muted">{weight:.1f}%</text>')
    bars.append('</svg>')
    return "".join(bars)


def render_html(report: dict[str, Any]) -> str:
    summary = report["summary"]
    market_view = report.get("market_view", {}) if isinstance(report.get("market_view"), dict) else {}
    macro = market_view.get("macro_points", {}) if isinstance(market_view.get("macro_points"), dict) else {}
    theme_items = "".join(
        f"<li><strong>{html.escape(str(theme.get('theme') or ''))}</strong> — {html.escape(str(theme.get('read') or ''))} <span class=\"muted\">({html.escape(', '.join(theme.get('tickers') or []) or '-')})</span></li>"
        for theme in market_view.get("current_investment_themes", []) or []
    )
    rows = []
    for record in report["records"]:
        band = record.get("entry_band") or {}
        band_label = band.get("label") or f"{money(band.get('low'))}-{money(band.get('high'))}"
        risk = "below stop" if record.get("below_stop") else ("near stop" if record.get("near_stop") else "")
        rows.append(
            "<tr>"
            f"<td>{html.escape(record['ticker'])}</td>"
            f"<td>{html.escape(str(record.get('sleeve') or ''))}</td>"
            f"<td>{pct(record.get('draft_weight'))}</td>"
            f"<td>{html.escape(str(record.get('sector') or ''))}</td>"
            f"<td>{money(record.get('close'))}</td>"
            f"<td>{html.escape(str(band_label))}</td>"
            f"<td>{money(record.get('stop'))}</td>"
            f"<td>{html.escape(str(record.get('action_bucket') or ''))}</td>"
            f"<td>{html.escape(risk)}</td>"
            "</tr>"
        )
    style = """
    body{font-family:Inter,Segoe UI,Arial,sans-serif;margin:32px;color:#0f172a;background:#f8fafc}
    .card{background:white;border:1px solid #e2e8f0;border-radius:14px;padding:18px;margin:16px 0;box-shadow:0 1px 2px rgba(15,23,42,.05)}
    .kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:12px}.kpi{background:#eff6ff;border-radius:12px;padding:12px}
    .label{font-size:12px;color:#64748b;text-transform:uppercase;letter-spacing:.06em}.value{font-size:20px;font-weight:700;margin-top:4px}
    table{border-collapse:collapse;width:100%;background:white}th,td{border-bottom:1px solid #e2e8f0;padding:8px;text-align:left;font-size:13px}th{background:#f1f5f9}
    .warn{color:#b45309}.danger{color:#b91c1c}.muted{color:#64748b}
    """
    return f"""<!doctype html>
<html><head><meta charset="utf-8"><title>Full Portfolio View</title><style>{style}</style></head>
<body>
<h1>Full Portfolio View</h1>
<p class="muted">Generated {html.escape(report['generated_at_utc'])} · Window {html.escape(report['window'])} · Market data as of <strong>{html.escape(str(report.get('market_data_as_of') or 'unknown'))}</strong></p>
<p><strong>Authority:</strong> review-only machine report; not canonical; no portfolio mutation, approval, sizing, execution entitlement, or trade authority.</p>
<div class="kpis">
  <div class="kpi"><div class="label">Deployable now / review-only</div><div class="value">{html.escape(', '.join(summary['deployable_now_review_only']) or '-')}</div></div>
  <div class="kpi"><div class="label">Prepare / wait</div><div class="value">{html.escape(', '.join(summary['prepare_or_wait']) or '-')}</div></div>
  <div class="kpi"><div class="label">Below stop</div><div class="value danger">{html.escape(', '.join(summary['below_stop']) or '-')}</div></div>
  <div class="kpi"><div class="label">Near stop</div><div class="value warn">{html.escape(', '.join(summary['near_stop']) or '-')}</div></div>
</div>
<div class="card"><h2>Market regime and current investment theme</h2>
<p><strong>Posture:</strong> {html.escape(str(market_view.get('portfolio_posture') or '-'))} · <strong>Regime:</strong> {html.escape(str(market_view.get('portfolio_regime') or '-'))}</p>
<p><strong>Macro tape:</strong> SPX {money(macro.get('spx'))}, VIX {money(macro.get('vix'))}, 10Y {money(macro.get('ten_year'))}, Brent {money(macro.get('brent'))}, credit {html.escape(str(macro.get('credit_stress') or '-'))}, breadth {html.escape(str(macro.get('breadth_regime') or '-'))}</p>
<ul>{theme_items}</ul>
<p class="muted">{html.escape(str(market_view.get('fresh_research_rule') or ''))}</p>
</div>
<div class="card">{svg_sector_chart(summary['sector_summary'])}</div>
<div class="card"><h2>Name-level table</h2><table><thead><tr><th>Ticker</th><th>Sleeve</th><th>Weight</th><th>Sector</th><th>Close</th><th>Band</th><th>Stop</th><th>Action</th><th>Risk</th></tr></thead><tbody>{''.join(rows)}</tbody></table></div>
</body></html>"""


def write_outputs(report: dict[str, Any], *, write_markdown: bool = False, write_html: bool = False) -> list[Path]:
    written: list[Path] = []
    OUT_JSON.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    written.append(OUT_JSON)
    if write_markdown:
        OUT_MD.write_text(render_md(report), encoding="utf-8")
        written.append(OUT_MD)
    if write_html:
        OUT_HTML.write_text(render_html(report), encoding="utf-8")
        written.append(OUT_HTML)
    return written


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the review-only full portfolio view machine report.")
    parser.add_argument("--window", default="post-close", choices=["morning", "post-close", "sunday", "post-earnings", "full"])
    parser.add_argument("--write", action="store_true", help="Write the JSON machine report.")
    parser.add_argument("--json-only", action="store_true", help="Deprecated compatibility flag; --write is JSON-only by default.")
    parser.add_argument("--write-md", action="store_true", help="Explicitly write the optional Markdown render.")
    parser.add_argument("--write-html", action="store_true", help="Explicitly write the optional HTML render.")
    args = parser.parse_args()
    window = "post-close" if args.window == "full" else args.window
    report = build_report(window)
    if args.write:
        write_markdown = args.write_md
        write_html = args.write_html
        written = write_outputs(report, write_markdown=write_markdown, write_html=write_html)
        for path in written:
            print(f"wrote {path}")
    print(
        "full_portfolio_view: "
        f"records={report['summary']['record_count']} market_data_as_of={report.get('market_data_as_of') or 'unknown'} "
        f"deployable={','.join(report['summary']['deployable_now_review_only']) or '-'} "
        f"below_stop={','.join(report['summary']['below_stop']) or '-'}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
