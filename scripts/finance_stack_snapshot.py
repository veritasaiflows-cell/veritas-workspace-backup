#!/usr/bin/env python3
"""Reusable full-stack finance intelligence snapshot.

Builds a fast, local, SQL-backed review surface from existing Veritas finance
artifacts plus optional structured web/AI intelligence evidence. This is a
review/proposal surface only: it does not authorize owner approval, portfolio
mutation, sizing/cash/risk-rule changes, paper/live orders, brokerage/account
actions, or money movement.
"""
from __future__ import annotations

from board_state_contract import legacy_state
import argparse
import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCRIPTS = Path(__file__).resolve().parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from market_data_utils import atomic_write_json, atomic_write_text, load_json_artifact

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
DEFAULT_JSON = TMP / "finance-stack-snapshot.json"
DEFAULT_MD = DEFAULT_JSON.with_suffix(".md")
DEFAULT_SQLITE = TMP / "finance-stack-snapshot.sqlite"
DEFAULT_WEB = TMP / "finance-stack-web-intelligence.json"
SCHEMA_VERSION = 1

AUTHORITY_FALSE = {
    "canonical_mutation_allowed": False,
    "portfolio_mutation_allowed": False,
    "deployment_state_mutation_allowed": False,
    "watchlist_promotion_allowed": False,
    "sizing_apply_allowed": False,
    "cash_or_risk_rule_mutation_allowed": False,
    "trade_execution_allowed": False,
    "trade_or_account_action_allowed": False,
    "live_trade_allowed": False,
    "live_brokerage_or_account_action_allowed": False,
    "paper_order_execution_allowed": False,
    "paper_order_submit_allowed_by_this_snapshot": False,
    "paper_order_cancel_allowed_by_this_snapshot": False,
    "owner_approval_granted": False,
    "owner_approval_inferred": False,
    "probability_or_win_rate_claim_allowed": False,
}

SOURCE_PATHS = {
    "market_state": TMP / "market-state.json",
    "deployment_readiness": TMP / "deployment-readiness-surface.json",
    "capital_recommendations": TMP / "portfolio-mutation-proposals" / "current-capital-deployment-recommendations.json",
    "capital_validation": TMP / "capital-deployment-recommendation-validation.json",
    "sector_matrix": TMP / "sector-allocation-decision-matrix.json",
    "tuesday_watchlist": TMP / "tuesday-entry-opportunity-watchlist-2026-05-26.json",
    "position_sizing": TMP / "position-sizing-readiness-current.json",
    "probability_readiness": TMP / "probability-readiness-report.json",
    "intraday_handoff": TMP / "intraday-alerts" / "runtime-handoff-status.json",
    "paper_positions_sql_packet": TMP / "finance-intelligence-state-paper-positions.json",
    "paper_position_state_db": TMP / "wf67-paper-position-state.sqlite",
    "paper_holdings_export": TMP / "alpaca-paper-readiness" / "current-paper-holdings-readonly.json",
    "web_intelligence": DEFAULT_WEB,
}

PRIORITY_ORDER = ["ETN", "VRT", "CME", "PH", "NVDA", "GOOG", "JPM", "MSFT", "GS", "ITA", "GE", "LIN"]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def load_dict(path: Path) -> dict[str, Any]:
    data = load_json_artifact(path)
    return data if isinstance(data, dict) else {}


def fnum(value: Any) -> float | None:
    try:
        if value in (None, ""):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def money(value: Any) -> str:
    val = fnum(value)
    return "n/a" if val is None else f"${val:,.2f}"


def source_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"path": rel(path), "exists": False}
    return {
        "path": rel(path),
        "exists": True,
        "mtime_utc": datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "size_bytes": path.stat().st_size,
    }


def flatten_deployment_groups(deployment: dict[str, Any]) -> dict[str, dict[str, Any]]:
    groups = deployment.get("groups") if isinstance(deployment.get("groups"), dict) else {}
    out: dict[str, dict[str, Any]] = {}
    for group_name, rows in groups.items():
        if not isinstance(rows, list):
            continue
        for row in rows:
            if isinstance(row, dict) and row.get("ticker"):
                item = dict(row)
                item["readiness_group"] = group_name
                out[str(row["ticker"]).upper()] = item
    return out


def by_ticker(rows: Any, ticker_field: str = "ticker") -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    if isinstance(rows, list):
        for row in rows:
            if isinstance(row, dict) and row.get(ticker_field):
                out[str(row[ticker_field]).upper()] = row
    return out


def paper_positions(paper: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows = paper.get("positions") if isinstance(paper.get("positions"), list) else []
    out: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict) or not row.get("symbol"):
            continue
        normalized = dict(row)
        if "qty" not in normalized and "quantity" in normalized:
            normalized["qty"] = normalized.get("quantity")
        if "avg_entry_price" not in normalized and "average_entry_price" in normalized:
            normalized["avg_entry_price"] = normalized.get("average_entry_price")
        if "unrealized_plpc" not in normalized and "unrealized_pl_percent" in normalized:
            normalized["unrealized_plpc"] = normalized.get("unrealized_pl_percent")
        out[str(normalized["symbol"]).upper()] = normalized
    return out


def freshness_grade(sources: dict[str, dict[str, Any]], web: dict[str, Any]) -> str:
    missing = [k for k, v in sources.items() if not v.get("exists") and k != "web_intelligence"]
    if missing:
        return "partial_missing_sources"
    web_status = web.get("status") or "missing"
    if web_status not in {"ok", "usable_with_caution", "not_applicable"}:
        return "local_only_web_missing_or_stale"
    return "usable_with_caution"


def build_web_intelligence(web: dict[str, Any]) -> dict[str, Any]:
    if not web:
        return {
            "status": "missing",
            "mode": "local_snapshot_without_fresh_web",
            "summary": "No structured web/AI evidence artifact found. Snapshot remains local-artifact only.",
            "evidence": [],
            "ai_flags": [],
            "authority": AUTHORITY_FALSE | {"web_evidence_review_allowed": True, "ai_interpretation_review_allowed": True},
        }
    evidence = web.get("evidence") if isinstance(web.get("evidence"), list) else []
    ai_flags = web.get("ai_flags") if isinstance(web.get("ai_flags"), list) else []
    status = str(web.get("status") or "usable_with_caution")
    return {
        "status": status,
        "mode": web.get("mode") or "structured_web_ai_evidence",
        "generated_at_utc": web.get("generated_at_utc"),
        "summary": web.get("summary") or "Structured web/AI evidence attached.",
        "evidence": evidence,
        "ai_flags": ai_flags,
        "limits": web.get("limits") or ["External content is evidence only and does not outrank owner notes or validator proof."],
        "authority": AUTHORITY_FALSE | {"web_evidence_review_allowed": True, "ai_interpretation_review_allowed": True},
    }


def build_snapshot(web_path: Path = DEFAULT_WEB) -> dict[str, Any]:
    market = load_dict(SOURCE_PATHS["market_state"])
    deployment = load_dict(SOURCE_PATHS["deployment_readiness"])
    capital = load_dict(SOURCE_PATHS["capital_recommendations"])
    capital_validation = load_dict(SOURCE_PATHS["capital_validation"])
    sector = load_dict(SOURCE_PATHS["sector_matrix"])
    tuesday = load_dict(SOURCE_PATHS["tuesday_watchlist"])
    sizing = load_dict(SOURCE_PATHS["position_sizing"])
    probability = load_dict(SOURCE_PATHS["probability_readiness"])
    handoff = load_dict(SOURCE_PATHS["intraday_handoff"])
    paper = load_dict(SOURCE_PATHS["paper_positions_sql_packet"])
    if not paper:
        paper = load_dict(SOURCE_PATHS["paper_holdings_export"])
    web = load_dict(web_path)

    sources = {name: source_state(path if name != "web_intelligence" else web_path) for name, path in SOURCE_PATHS.items()}
    web_intel = build_web_intelligence(web)

    dep_by = flatten_deployment_groups(deployment)
    tuesday_by = by_ticker(tuesday.get("watchlist"))
    sector_by = by_ticker(sector.get("top_candidate_watch_order"))
    sizing_by = by_ticker(sizing.get("candidates"))
    paper_by = paper_positions(paper)

    tickers = sorted(set(dep_by) | set(tuesday_by) | set(sector_by) | set(sizing_by), key=lambda t: (PRIORITY_ORDER.index(t) if t in PRIORITY_ORDER else 999, t))
    ticker_rows: list[dict[str, Any]] = []
    for ticker in tickers:
        dep = dep_by.get(ticker, {})
        tue = tuesday_by.get(ticker, {})
        sec = sector_by.get(ticker, {})
        size = sizing_by.get(ticker, {})
        pos = paper_by.get(ticker, {})
        readiness = dep.get("readiness_group") or legacy_state(dep, "surface_state") or tue.get("state") or sec.get("state") or size.get("readiness") or "UNKNOWN"
        band_status = dep.get("band_position") or tue.get("band_status") or sec.get("entry_band_status") or size.get("band_status")
        close = dep.get("close") if dep.get("close") is not None else tue.get("close") or sec.get("close") or size.get("close_reference")
        ticker_rows.append({
            "ticker": ticker,
            "readiness": readiness,
            "action_state": legacy_state(dep, "action_state") or readiness,
            "close_reference": close,
            "band_status": band_status,
            "entry_band_low": tue.get("band_low") or sec.get("band_low") or size.get("band_low"),
            "entry_band_high": tue.get("band_high") or sec.get("band_high") or size.get("band_high"),
            "stop": tue.get("stop") or sec.get("stop") or size.get("stop"),
            "sector": sec.get("sector") or tue.get("sector"),
            "candidate_score": sec.get("score"),
            "tuesday_readiness": size.get("readiness") or tue.get("state"),
            "suggested_tuesday_incremental_paper_notional_usd": size.get("suggested_tuesday_incremental_paper_notional_usd"),
            "paper_qty": pos.get("qty"),
            "paper_market_value_usd": pos.get("market_value"),
            "decision_note": size.get("decision_note") or dep.get("why") or tue.get("why") or sec.get("rationale"),
            "next_action": classify_next_action(ticker, readiness, str(band_status or ""), size),
            "authority": AUTHORITY_FALSE | {"review_recommendation_allowed": True},
            "source_paths": sorted({p for p in [
                dep.get("source_artifact_path"),
                "tmp/tuesday-entry-opportunity-watchlist-2026-05-26.json" if ticker in tuesday_by else None,
                "tmp/sector-allocation-decision-matrix.json" if ticker in sector_by else None,
                "tmp/position-sizing-readiness-current.json" if ticker in sizing_by else None,
                "tmp/finance-intelligence-state-paper-positions.json" if ticker in paper_by else None,
                "tmp/wf67-paper-position-state.sqlite" if ticker in paper_by else None,
            ] if p}),
        })

    deployable = [r["ticker"] for r in ticker_rows if str(r["readiness"]).upper() == "DEPLOYABLE NOW"]
    promotion = [r["ticker"] for r in ticker_rows if "PROMOTION" in str(r["readiness"]).upper()]
    no_chase = [r["ticker"] for r in ticker_rows if "ABOVE" in str(r.get("band_status") or "").upper() or "NO_CHASE" in str(r.get("tuesday_readiness") or "").upper()]
    repair = [r["ticker"] for r in ticker_rows if "DO NOT TOUCH" in str(r["readiness"]).upper() or "REPAIR" in str(r["readiness"]).upper()]

    authority = AUTHORITY_FALSE | {"review_snapshot_allowed": True, "local_sql_export_allowed": True}
    findings = validate_snapshot_fields(ticker_rows, capital, capital_validation, probability, handoff, authority)
    status = "ok" if not [f for f in findings if f["severity"] == "critical"] else "critical"
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": utc_now(),
        "status": status,
        "purpose": "Reusable full-stack finance intelligence snapshot for fast Veritas/Randall review.",
        "freshness_grade": freshness_grade(sources, web_intel),
        "source_artifacts": sources,
        "regime": summarize_regime(market),
        "portfolio_posture": {
            "capital_base_usd": 10000,
            "target_cash_usd": 1000,
            "investable_capital_usd": 9000,
            "posture": "selective risk-on with reduced confidence",
            "constraints": [
                "Direct Technology is at/near cap; AI-power concentration must be sequenced.",
                "Fresh quote/band/stop check required before any Tuesday paper-order card.",
                "Generated packets are review surfaces, not approval or execution authority.",
            ],
        },
        "readiness_summary": {
            "deployable_now": deployable,
            "promotion_review": promotion,
            "no_chase_or_above_band": no_chase,
            "repair_or_do_not_touch": repair,
            "primary_tuesday_queue": [t for t in ["ETN", "VRT", "CME", "PH", "NVDA"] if any(r["ticker"] == t for r in ticker_rows)],
        },
        "ticker_rows": ticker_rows,
        "sector_intelligence": {
            "status": sector.get("status"),
            "trust_state": sector.get("trust_state"),
            "growth_vs_value_verdict": sector.get("growth_vs_value_verdict"),
            "top_candidate_watch_order": sector.get("top_candidate_watch_order", [])[:12] if isinstance(sector.get("top_candidate_watch_order"), list) else [],
        },
        "paper_trading_readiness": {
            "status": paper.get("status"),
            "account_mode": paper.get("account_mode"),
            "endpoint": paper.get("endpoint"),
            "summary": paper.get("summary"),
            "positions": paper.get("positions") if isinstance(paper.get("positions"), list) else [],
            "wf67_required_for_any_order": True,
        },
        "web_ai_intelligence": web_intel,
        "trust_and_authority": {
            "capital_recommendation_validator_status": capital_validation.get("status"),
            "capital_packet_status": capital.get("status"),
            "proposal_apply_allowed": capital.get("proposal_apply_allowed"),
            "trade_or_account_action_allowed": capital.get("trade_or_account_action_allowed"),
            "probability_verdict": probability.get("verdict"),
            "probability_claims_allowed": False,
            "intraday_handoff_status": handoff.get("handoff_status"),
            "intraday_action_needed": handoff.get("action_needed"),
            "authority": authority,
        },
        "recommended_actions": recommended_actions(ticker_rows, web_intel),
        "validation": {"status": "ok" if not findings else "warning" if not [f for f in findings if f["severity"] == "critical"] else "critical", "findings": findings},
    }


def classify_next_action(ticker: str, readiness: Any, band_status: str, sizing: dict[str, Any]) -> str:
    r = str(readiness).upper()
    b = band_status.upper()
    sr = str(sizing.get("readiness") or "")
    if ticker == "ETN" and "DEPLOYABLE" in r:
        return "fresh quote check; if still in band, prepare approval-ready WF67 paper card for Randall review"
    if ticker in {"VRT", "CME", "PH"}:
        return "promotion-review comparison; only prepare order card after owner promotion and fresh in-band quote"
    if ticker == "NVDA":
        return "concentration exception/substitution decision required before any paper-prep action"
    if "ABOVE" in b or "no_chase" in sr:
        return "wait/no chase; alert only if price re-enters written band or owner approves band review"
    if "REPAIR" in r or "DO NOT TOUCH" in r:
        return "repair/watch only; no deployment prep"
    return "monitor; inspect owner note before action"


def summarize_regime(market: dict[str, Any]) -> dict[str, Any]:
    data = market.get("data") if isinstance(market.get("data"), dict) else {}
    treasuries = data.get("treasuries") if isinstance(data.get("treasuries"), dict) else {}
    vol = data.get("volatility") if isinstance(data.get("volatility"), dict) else {}
    credit = data.get("credit") if isinstance(data.get("credit"), dict) else {}
    breadth = data.get("breadth") if isinstance(data.get("breadth"), dict) else {}
    fed = data.get("fed") if isinstance(data.get("fed"), dict) else {}
    return {
        "status": market.get("status"),
        "generated_at_utc": market.get("generated_at_utc"),
        "last_trading_day": market.get("last_trading_day"),
        "regime_label": "resilient growth / restrictive pause / selective risk-on",
        "vix": vol.get("vix"),
        "ten_year_yield": treasuries.get("10y"),
        "two_year_yield": treasuries.get("2y"),
        "fed_target_range": [fed.get("target_low"), fed.get("target_high")],
        "credit_stress_regime": credit.get("stress_regime"),
        "breadth_regime": breadth.get("breadth_regime") or breadth.get("participation_regime"),
        "warnings": market.get("warnings") if isinstance(market.get("warnings"), list) else [],
        "freshness_notes": market.get("freshness_notes") if isinstance(market.get("freshness_notes"), list) else [],
    }


def recommended_actions(rows: list[dict[str, Any]], web: dict[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for ticker in PRIORITY_ORDER:
        row = next((r for r in rows if r["ticker"] == ticker), None)
        if not row:
            continue
        if ticker == "ETN":
            out.append({"rank": 1, "ticker": ticker, "action": row["next_action"], "why": "only clean deployable-now name; still requires fresh quote and WF67 approval path"})
        elif ticker in {"VRT", "CME", "PH"}:
            out.append({"rank": len(out) + 1, "ticker": ticker, "action": row["next_action"], "why": "diversification/promotion-review queue"})
        elif ticker == "NVDA":
            out.append({"rank": len(out) + 1, "ticker": ticker, "action": row["next_action"], "why": "strong but concentration-limited"})
    if web.get("status") == "missing":
        out.append({"rank": len(out) + 1, "ticker": None, "action": "refresh structured web/AI evidence before market-open decision work", "why": "snapshot is local-only without fresh external catalyst evidence"})
    return out


def validate_snapshot_fields(rows: list[dict[str, Any]], capital: dict[str, Any], capital_validation: dict[str, Any], probability: dict[str, Any], handoff: dict[str, Any], authority: dict[str, Any]) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    for key, expected in AUTHORITY_FALSE.items():
        if authority.get(key) is not expected:
            findings.append({"severity": "critical", "code": "authority_drift", "message": f"authority flag {key} is not false"})
    if capital_validation.get("status") != "ok":
        findings.append({"severity": "warning", "code": "capital_validator_not_ok", "message": "capital deployment validator is not ok"})
    if capital.get("proposal_apply_allowed") is not False:
        findings.append({"severity": "critical", "code": "proposal_apply_allowed", "message": "capital packet proposal_apply_allowed is not false"})
    if capital.get("trade_or_account_action_allowed") is not False:
        findings.append({"severity": "critical", "code": "trade_authority_drift", "message": "capital packet trade_or_account_action_allowed is not false"})
    if probability.get("verdict") != "NOT_READY":
        findings.append({"severity": "warning", "code": "probability_verdict_changed", "message": "probability readiness verdict is not NOT_READY; inspect before using modeling language"})
    if handoff.get("action_needed") not in {False, None}:
        findings.append({"severity": "warning", "code": "handoff_action_needed", "message": "intraday handoff says action_needed"})
    for row in rows:
        auth = row.get("authority") if isinstance(row.get("authority"), dict) else {}
        for key in AUTHORITY_FALSE:
            if auth.get(key) is not False:
                findings.append({"severity": "critical", "code": "ticker_authority_drift", "message": f"{row.get('ticker')} authority {key} is not false"})
    return findings


def render_md(snapshot: dict[str, Any]) -> str:
    lines = [
        "# Finance Stack Snapshot",
        "",
        f"Generated: {snapshot['generated_at_utc']}",
        f"Status: **{snapshot['status']}**",
        f"Freshness grade: **{snapshot['freshness_grade']}**",
        "",
        "## Regime",
    ]
    regime = snapshot["regime"]
    lines += [
        f"- Label: {regime.get('regime_label')}",
        f"- Last trading day: {regime.get('last_trading_day')}",
        f"- VIX: {regime.get('vix')}",
        f"- 10Y: {regime.get('ten_year_yield')}",
        f"- Credit: {regime.get('credit_stress_regime')}",
        f"- Breadth: {regime.get('breadth_regime')}",
        "",
        "## Readiness summary",
        f"- Deployable now: {', '.join(snapshot['readiness_summary']['deployable_now']) or 'none'}",
        f"- Promotion review: {', '.join(snapshot['readiness_summary']['promotion_review']) or 'none'}",
        f"- No-chase / above band: {', '.join(snapshot['readiness_summary']['no_chase_or_above_band']) or 'none'}",
        f"- Repair / do not touch: {', '.join(snapshot['readiness_summary']['repair_or_do_not_touch']) or 'none'}",
        "",
        "## Ticker queue",
        "| Ticker | Readiness | Close | Band status | Next action |",
        "|---|---|---:|---|---|",
    ]
    for row in snapshot["ticker_rows"][:30]:
        lines.append(f"| {row['ticker']} | {row.get('readiness')} | {money(row.get('close_reference'))} | {row.get('band_status') or 'n/a'} | {row.get('next_action')} |")
    lines += ["", "## Web / AI intelligence"]
    web = snapshot["web_ai_intelligence"]
    lines += [f"- Status: {web.get('status')}", f"- Summary: {web.get('summary')}"]
    for flag in web.get("ai_flags", [])[:8]:
        if isinstance(flag, dict):
            lines.append(f"- AI flag: **{flag.get('label') or flag.get('type')}** — {flag.get('summary') or flag.get('finding')}")
    lines += ["", "## Recommended actions"]
    for action in snapshot["recommended_actions"]:
        ticker = action.get("ticker") or "system"
        lines.append(f"{action.get('rank')}. **{ticker}** — {action.get('action')} ({action.get('why')})")
    lines += [
        "",
        "## Authority boundary",
        "Review/proposal snapshot only. No owner approval, portfolio/canon mutation, sizing/cash/risk-rule apply, paper/live order, brokerage/account action, or money movement is authorized by this artifact.",
        "",
        "## Validation",
        f"- Status: {snapshot['validation']['status']}",
    ]
    for finding in snapshot["validation"].get("findings", []):
        lines.append(f"- {finding.get('severity')}: {finding.get('code')} — {finding.get('message')}")
    return "\n".join(lines) + "\n"


def write_sqlite(snapshot: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA temp_store=MEMORY")
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS snapshot_runs (
            id INTEGER PRIMARY KEY,
            generated_at_utc TEXT NOT NULL,
            status TEXT NOT NULL,
            freshness_grade TEXT NOT NULL,
            regime_json TEXT NOT NULL,
            readiness_summary_json TEXT NOT NULL,
            trust_json TEXT NOT NULL,
            web_ai_json TEXT NOT NULL,
            raw_json TEXT NOT NULL
        ) STRICT;
        CREATE TABLE IF NOT EXISTS ticker_rows (
            run_id INTEGER NOT NULL REFERENCES snapshot_runs(id) ON DELETE CASCADE,
            ticker TEXT NOT NULL,
            readiness TEXT,
            action_state TEXT,
            close_reference REAL,
            band_status TEXT,
            entry_band_low REAL,
            entry_band_high REAL,
            stop REAL,
            sector TEXT,
            tuesday_readiness TEXT,
            paper_qty REAL,
            paper_market_value_usd REAL,
            next_action TEXT,
            authority_json TEXT NOT NULL,
            source_paths_json TEXT NOT NULL,
            PRIMARY KEY (run_id, ticker)
        ) STRICT;
        CREATE TABLE IF NOT EXISTS web_evidence_rows (
            run_id INTEGER NOT NULL REFERENCES snapshot_runs(id) ON DELETE CASCADE,
            row_num INTEGER NOT NULL,
            source TEXT,
            title TEXT,
            url TEXT,
            evidence_type TEXT,
            relevance TEXT,
            raw_json TEXT NOT NULL,
            PRIMARY KEY (run_id, row_num)
        ) STRICT;
        CREATE VIEW IF NOT EXISTS latest_snapshot AS
            SELECT * FROM snapshot_runs WHERE id = (SELECT max(id) FROM snapshot_runs);
        CREATE VIEW IF NOT EXISTS latest_ticker_rows AS
            SELECT t.* FROM ticker_rows t JOIN latest_snapshot s ON s.id = t.run_id;
        """
    )
    cur = conn.execute(
        "INSERT INTO snapshot_runs (generated_at_utc,status,freshness_grade,regime_json,readiness_summary_json,trust_json,web_ai_json,raw_json) VALUES (?,?,?,?,?,?,?,?)",
        (
            snapshot["generated_at_utc"], snapshot["status"], snapshot["freshness_grade"],
            json.dumps(snapshot["regime"], sort_keys=True),
            json.dumps(snapshot["readiness_summary"], sort_keys=True),
            json.dumps(snapshot["trust_and_authority"], sort_keys=True),
            json.dumps(snapshot["web_ai_intelligence"], sort_keys=True),
            json.dumps(snapshot, sort_keys=True),
        ),
    )
    run_id = int(cur.lastrowid)
    for row in snapshot["ticker_rows"]:
        conn.execute(
            "INSERT INTO ticker_rows VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                run_id, row.get("ticker"), row.get("readiness"), legacy_state(row, "action_state"), fnum(row.get("close_reference")), row.get("band_status"),
                fnum(row.get("entry_band_low")), fnum(row.get("entry_band_high")), fnum(row.get("stop")), row.get("sector"), row.get("tuesday_readiness"),
                fnum(row.get("paper_qty")), fnum(row.get("paper_market_value_usd")), row.get("next_action"),
                json.dumps(row.get("authority", {}), sort_keys=True), json.dumps(row.get("source_paths", []), sort_keys=True),
            ),
        )
    for idx, ev in enumerate(snapshot["web_ai_intelligence"].get("evidence", []), 1):
        if not isinstance(ev, dict):
            continue
        conn.execute(
            "INSERT INTO web_evidence_rows VALUES (?,?,?,?,?,?,?,?)",
            (run_id, idx, ev.get("source"), ev.get("title"), ev.get("url"), ev.get("evidence_type"), ev.get("relevance"), json.dumps(ev, sort_keys=True)),
        )
    conn.commit()
    conn.close()


def validate_sqlite(path: Path) -> dict[str, Any]:
    uri = path.resolve().as_uri() + "?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute("PRAGMA foreign_keys=ON")
    integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
    foreign_key_rows = [dict(row) for row in conn.execute("PRAGMA foreign_key_check")]
    schema_objects = {
        row["name"]: row["type"]
        for row in conn.execute("SELECT name, type FROM sqlite_master WHERE type IN ('table','view')")
    }
    required_tables = {"snapshot_runs", "ticker_rows", "web_evidence_rows"}
    required_views = {"latest_snapshot", "latest_ticker_rows"}
    latest = conn.execute("SELECT id, status, freshness_grade FROM latest_snapshot").fetchone()
    ticker_count = conn.execute("SELECT count(*) FROM latest_ticker_rows").fetchone()[0]
    deployable = conn.execute("SELECT ticker FROM latest_ticker_rows WHERE readiness='DEPLOYABLE NOW' ORDER BY ticker").fetchall()
    conn.close()
    return {
        "integrity_check": integrity,
        "foreign_key_check_rows": foreign_key_rows,
        "required_tables_present": sorted(required_tables.intersection(schema_objects)),
        "required_views_present": sorted(required_views.intersection(schema_objects)),
        "schema_ready": required_tables.issubset(schema_objects) and required_views.issubset(schema_objects),
        "latest_run_id": latest[0] if latest else None,
        "latest_status": latest[1] if latest else None,
        "freshness_grade": latest[2] if latest else None,
        "latest_ticker_count": ticker_count,
        "deployable_now": [r[0] for r in deployable],
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--validate", action="store_true")
    ap.add_argument("--web-evidence", default=str(DEFAULT_WEB))
    ap.add_argument("--json-out", default=str(DEFAULT_JSON))
    ap.add_argument("--md-out", default=None, help="Optional Markdown output path; JSON/SQLite are the default contracts.")
    ap.add_argument("--sqlite-out", default=str(DEFAULT_SQLITE))
    args = ap.parse_args()

    snapshot = build_snapshot(Path(args.web_evidence))
    if args.write:
        atomic_write_json(Path(args.json_out), snapshot)
        if args.md_out:
            atomic_write_text(Path(args.md_out), render_md(snapshot))
        write_sqlite(snapshot, Path(args.sqlite_out))
    if args.validate:
        findings = list(snapshot["validation"].get("findings", []))
        sqlite_report = validate_sqlite(Path(args.sqlite_out)) if Path(args.sqlite_out).exists() else {"missing": True}
        if sqlite_report.get("integrity_check") not in {None, "ok"}:
            findings.append({"severity": "critical", "code": "sqlite_integrity", "message": str(sqlite_report)})
        report = {"status": "ok" if not [f for f in findings if f.get("severity") == "critical"] else "critical", "findings": findings, "sqlite": sqlite_report}
        print(json.dumps(report, indent=2, sort_keys=True))
        return 0 if report["status"] == "ok" else 1
    if not args.write:
        print(json.dumps(snapshot, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
