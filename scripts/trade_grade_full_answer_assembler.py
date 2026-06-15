#!/usr/bin/env python3
"""Assemble WF84/WF85 trade-grade full ticker answers.

This is the replacement owner for the old static ticker-answer-packet answer
route. It builds a canonical full-answer object from WF84, WF85, and the rich
ticker evidence cache, and can emit a legacy ticker_answer_packet_v1 compatibility
snapshot for existing readers.

Review-only boundary: no canon/portfolio/cash/risk-rule mutation, no archive or
delete action, no paper/live order action, no account action, and no inferred
owner approval.
"""
from __future__ import annotations

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

from market_data_utils import atomic_write_json, load_json_artifact
from wf84_sqlite_mutex import wf84_sqlite_mutex
from wf78_legacy_42_tier_state import production_tickers as legacy_42_tier_tickers

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"

CANONICAL_DB = TMP / "canonical-finance-data-plane.sqlite"
CARD_DIR = TMP / "ticker-intelligence-cards"
ANSWER_PACKET_DIR = TMP / "ticker-answer-packets"
WF85_CARDS = TMP / "trade-grade-decision-cards.json"
POST_CLOSE_LEDGER = TMP / "post-close-final-quote-ledger.json"
MACRO_METRICS = TMP / "macro-metrics-current.json"
MACRO_JUDGMENT = TMP / "macro-judgment-draft.json"
MARKET_TODAY = TMP / "market-today-answer-packet.json"
OUT_DIR = TMP / "trade-grade-full-answer"
ROLLUP_OUT = TMP / "trade-grade-full-answer-assembler.json"

SCHEMA = "veritas.trade_grade_full_answer_assembler.v1"
LEGACY_PACKET_SCHEMA_VERSION = 1
STALE_AFTER_HOURS = 36

REQUIRED_SECTION_IDS = [
    "thesis",
    "business_quality_moat",
    "bull_case",
    "bear_case",
    "earnings_guidance",
    "financial_metrics",
    "valuation",
    "technical_setup",
    "catalyst_news_macro",
    "risk_invalidation",
    "portfolio_fit",
    "entry_stop_sizing",
    "decision_state",
    "trade_grade",
    "owner_action",
    "authority_approval_status",
    "evidence_freshness_confidence",
]

FORBIDDEN_TRUE_FLAGS = {
    "capital_deployment_allowed",
    "capital_deployment_approved",
    "trade_execution_allowed",
    "trade_or_execution_approved",
    "paper_or_live_execution_allowed",
    "paper_order_execution_allowed",
    "paper_order_submit_allowed",
    "paper_order_cancel_allowed",
    "live_trade_allowed",
    "live_brokerage_or_account_action_allowed",
    "brokerage_or_account_action_allowed",
    "money_movement_allowed",
    "canon_or_portfolio_mutation_allowed",
    "canonical_note_mutation_allowed",
    "portfolio_mutation_allowed",
    "cash_sizing_or_risk_rule_mutation_allowed",
    "owner_approval_inferred",
    "owner_approval_granted",
    "archive_allowed",
    "delete_allowed",
    "apply_allowed",
}

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "report_only": True,
    "artifact_role": "wf85_full_answer_assembler_review_only",
    "generated_answer_is_canon": False,
    "canonical_note_mutation_allowed": False,
    "portfolio_mutation_allowed": False,
    "cash_sizing_or_risk_rule_mutation_allowed": False,
    "capital_deployment_allowed": False,
    "capital_deployment_approved": False,
    "trade_or_execution_approved": False,
    "paper_or_live_execution_allowed": False,
    "paper_order_execution_allowed": False,
    "paper_order_submit_allowed": False,
    "paper_order_cancel_allowed": False,
    "live_trade_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "live_brokerage_or_account_action_allowed": False,
    "money_movement_allowed": False,
    "archive_allowed": False,
    "delete_allowed": False,
    "apply_allowed": False,
    "owner_approval_inferred": False,
    "source_open_required_before_material_finance_claims": True,
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def load_json(path: Path, default: Any = None) -> Any:
    data = load_json_artifact(path)
    return default if data is None else data


def get_path(value: Any, dotted: str) -> Any:
    cur = value
    for part in dotted.split("."):
        if not isinstance(cur, dict):
            return None
        cur = cur.get(part)
    return cur


def connect_ro(db_path: Path = CANONICAL_DB) -> sqlite3.Connection:
    uri = db_path.resolve().as_uri() + "?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


def card_path(ticker: str) -> Path:
    return CARD_DIR / f"{ticker.upper()}.current.json"


def full_answer_path(ticker: str) -> Path:
    return OUT_DIR / f"{ticker.upper()}.json"


def legacy_packet_path(ticker: str) -> Path:
    return ANSWER_PACKET_DIR / f"{ticker.upper()}.current.json"


def production_tickers() -> list[str]:
    return legacy_42_tier_tickers()


def wf84_tickers() -> list[str]:
    if not CANONICAL_DB.exists():
        return sorted(
            path.name.split(".")[0].upper()
            for path in CARD_DIR.glob("*.current.json")
            if path.is_file()
        )
    with connect_ro() as conn:
        return [
            str(row["ticker"]).upper()
            for row in conn.execute("SELECT ticker FROM security_master ORDER BY ticker")
            if row["ticker"]
        ]


def wf85_cards_by_ticker() -> dict[str, dict[str, Any]]:
    payload = as_dict(load_json(WF85_CARDS, {}))
    return {
        str(as_dict(card).get("ticker") or "").upper(): as_dict(card)
        for card in as_list(payload.get("cards"))
        if as_dict(card).get("ticker")
    }


def wf84_context(ticker: str) -> dict[str, Any]:
    ticker = ticker.upper()
    if not CANONICAL_DB.exists():
        return {"status": "missing", "reason": "canonical DB missing", "current": {}, "sections": {}, "drillback": []}
    try:
        with connect_ro() as conn:
            current = conn.execute("SELECT * FROM v_current_decision_overview WHERE ticker=?", (ticker,)).fetchone()
            sections = {
                row["section_id"]: dict(row)
                for row in conn.execute("SELECT * FROM v_full_ticker_answer_context WHERE ticker=? ORDER BY section_id", (ticker,))
            }
            drillback = [
                dict(row)
                for row in conn.execute("SELECT * FROM v_ticker_source_drillback WHERE ticker=? ORDER BY source_use, path", (ticker,))
            ]
        return {
            "status": "ok" if current else "missing",
            "current": dict(current) if current else {},
            "sections": sections,
            "drillback": drillback,
        }
    except sqlite3.Error as exc:
        return {"status": "blocked", "reason": f"sqlite_read_failed:{type(exc).__name__}", "current": {}, "sections": {}, "drillback": []}


def parse_json_text(value: Any, default: Any = None) -> Any:
    if not isinstance(value, str) or not value:
        return default
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return default


def wf84_section_raw(wf84: dict[str, Any], section_id: str) -> Any:
    row = as_dict(as_dict(wf84.get("sections")).get(section_id))
    return parse_json_text(row.get("raw_json"), {})


def present(value: Any) -> bool:
    if isinstance(value, dict):
        if not value:
            return False
        status = str(value.get("status") or value.get("parse_status") or "").lower()
        if status in {"missing", "unavailable", "source_open_required"}:
            substantive = [
                child for key, child in value.items()
                if key not in {"status", "parse_status"} and child not in (None, "", [], {})
            ]
            if not substantive:
                return False
        return any(child not in (None, "", [], {}) for child in value.values())
    if isinstance(value, list):
        return bool(value)
    return value not in (None, "")


def recursive_forbidden_true(value: Any, path: str = "$") -> list[dict[str, str]]:
    found: list[dict[str, str]] = []
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}.{key}"
            if key in FORBIDDEN_TRUE_FLAGS and child is True:
                found.append({"path": child_path, "flag": key})
            found.extend(recursive_forbidden_true(child, child_path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            found.extend(recursive_forbidden_true(child, f"{path}[{index}]"))
    return found


def source_paths(*values: Any) -> list[str]:
    paths: list[str] = []
    for value in values:
        if isinstance(value, str) and value:
            paths.append(value.replace("\\", "/"))
        elif isinstance(value, dict):
            for key in ("path", "source_path", "source", "source_artifact_path", "owner_source_path"):
                raw = value.get(key)
                if isinstance(raw, str) and raw:
                    paths.append(raw.replace("\\", "/"))
            for child in value.values():
                if isinstance(child, (dict, list)):
                    paths.extend(source_paths(child))
        elif isinstance(value, list):
            for child in value:
                paths.extend(source_paths(child))
    return sorted(set(paths))


def section(section_id: str, title: str, data: Any, *, fallback_sources: list[str] | None = None, confidence: str = "medium") -> dict[str, Any]:
    status = "available" if present(data) else "source_open_required"
    paths = source_paths(data)
    if fallback_sources:
        paths.extend(fallback_sources)
    return {
        "section_id": section_id,
        "title": title,
        "status": status,
        "confidence": confidence if status == "available" else "low",
        "freshness_status": "mapped" if status == "available" else "source_open_required",
        "source_open_required": True,
        "source_paths": sorted(set(paths)),
        "raw": data if present(data) else {"status": "source_open_required"},
    }


def confidence_by_domain(card: dict[str, Any], wf85: dict[str, Any], sections: dict[str, dict[str, Any]]) -> dict[str, Any]:
    def domain(level: str, reasons: list[str]) -> dict[str, Any]:
        score = {"high": 0.9, "medium": 0.6, "low": 0.3, "none": 0.1}.get(level, 0.3)
        return {"level": level, "score": score, "reasons": reasons}

    source_freshness = as_dict(wf85.get("source_freshness"))
    pbs = as_dict(card.get("price_band_stop"))
    analyst = as_dict(card.get("analyst_consensus_ratings_targets"))
    technical = as_dict(as_dict(sections.get("technical_setup")).get("raw"))
    analyst_confidence = str(analyst.get("confidence") or "").lower()
    if analyst_confidence not in {"high", "medium", "low", "none"}:
        analyst_confidence = "medium" if analyst.get("status") not in {None, "missing"} else "low"
    sector = as_dict(card.get("current_sector_performance"))
    return {
        "action_state": domain("high" if wf85.get("decision_state") else "low", [f"decision_state={wf85.get('decision_state')}"]),
        "price_band_stop": domain(
            "high" if pbs.get("entry_band_low") is not None and pbs.get("stop_or_invalidation") is not None else "low",
            [f"band_status={pbs.get('band_status')}", f"source_freshness={source_freshness.get('status')}"],
        ),
        "technical": domain(
            "low" if technical.get("repair_required") else ("high" if present(technical) else "low"),
            [f"technical_status={technical.get('status')}", f"repair_required={technical.get('repair_required')}"],
        ),
        "official_earnings": domain("high" if as_dict(card.get("latest_earnings_performance")).get("status") == "available" else "low", [f"earnings_status={as_dict(card.get('latest_earnings_performance')).get('status')}"]),
        "analyst": domain(analyst_confidence, [f"analyst_status={analyst.get('status')}", f"provider={analyst.get('provider')}", f"card_confidence={analyst.get('confidence')}"]),
        "sector_context": domain("high" if sector.get("status") == "available" else "low", [f"sector_status={sector.get('status')}"]),
        "recommendation": domain("high" if wf85.get("decision_state") in {"review_ready", "no_chase", "below_stop_or_invalidation", "evidence_repair", "monitor_only"} else "low", [f"wf85_state={wf85.get('decision_state')}"]),
        "source_freshness": domain("high" if source_freshness.get("status") == "fresh" else "low", [f"freshness={source_freshness.get('status')}"]),
    }


def answer_confidence(conf: dict[str, dict[str, Any]]) -> dict[str, Any]:
    decision_domains = ["action_state", "price_band_stop", "recommendation", "source_freshness"]
    scores = [float(as_dict(conf.get(name)).get("score") or 0.1) for name in decision_domains]
    avg = sum(scores) / len(scores) if scores else 0.1
    if avg >= 0.8:
        level = "high"
    elif avg >= 0.5:
        level = "medium"
    elif avg >= 0.25:
        level = "low"
    else:
        level = "none"
    lows = [name for name, item in conf.items() if item.get("level") in {"low", "none"}]
    return {
        "overall_level": level,
        "overall_label": f"{level}_for_trade_grade_review",
        "score": round(avg, 3),
        "decision_relevant_level": level,
        "decision_relevant_score": round(avg, 3),
        "peripheral_context_level": "low" if lows else "medium",
        "peripheral_context_score": round(sum(float(item.get("score") or 0.1) for item in conf.values()) / max(len(conf), 1), 3),
        "reasons": [
            "decision domains include action_state, price_band_stop, recommendation, and source_freshness",
            "low/none domains: " + ", ".join(lows) if lows else "no low/none domains",
        ],
    }


def trade_grade(wf85: dict[str, Any], card: dict[str, Any]) -> dict[str, Any]:
    state = wf85.get("decision_state")
    tier = wf85.get("auto_tier") or as_dict(card.get("wf78_auto_tier_routing")).get("auto_tier")
    if state == "review_ready":
        grade = "A"
        actionability = "review_ready_not_approved"
    elif state == "no_chase":
        grade = "B"
        actionability = "wait_no_chase"
    elif state == "evidence_repair":
        grade = "Incomplete"
        actionability = "repair_required"
    elif state == "below_stop_or_invalidation":
        grade = "Reject"
        actionability = "avoid_until_reclaimed"
    elif state == "monitor_only":
        grade = "C"
        actionability = "monitor_only"
    else:
        grade = "D"
        actionability = "blocked_or_unknown"
    return {
        "grade": grade,
        "conviction": "medium" if grade in {"A", "B"} else "low",
        "time_horizon": as_dict(card.get("portfolio_fit_concentration")).get("time_horizon") or "not_structured",
        "research_tier": tier,
        "actionability": actionability,
        "decision_state": state,
        "trade_grade_is_not_owner_approval": True,
    }


def owner_action(wf85: dict[str, Any]) -> dict[str, Any]:
    state = wf85.get("decision_state")
    if state == "review_ready":
        action = "review_only_exact_owner_approval_required_before_any_order_or_capital_action"
    elif state == "no_chase":
        action = "no_action_wait_for_entry_or_band_reclaim"
    elif state == "evidence_repair":
        action = "repair_evidence_or_resolve_promotion_veto_before_review"
    elif state == "below_stop_or_invalidation":
        action = "avoid_until_invalidation_repair_or_reclaim_review"
    else:
        action = "monitor_only_no_owner_action"
    return {
        "owner_action": action,
        "owner_action_required": bool(wf85.get("owner_action_required")),
        "execution_authorized": False,
        "paper_trade_allowed": False,
        "live_trade_allowed": False,
        "approval_status": "not_approved",
        "not_approved_stamp": wf85.get("not_approved_stamp") or "NOT APPROVED - Randall exact approval required",
    }


def decision_grade_gate(wf85: dict[str, Any]) -> dict[str, Any]:
    state = str(wf85.get("decision_state") or "")
    primary = str(wf85.get("primary_state") or "")
    queue = str(wf85.get("queue_state") or "")
    reason = as_list(wf85.get("decision_state_reason"))
    allowed = state == "review_ready"
    blockers: list[str] = []
    if not allowed:
        blockers.append(f"decision_state={state or 'missing'}")
    if primary in {"promotion_vetoed", "blocked_missing_freshness", "repair_mode"}:
        blockers.append(f"primary_state={primary}")
    if queue in {"promotion_vetoed", "blocked_missing_freshness", "repair_mode"}:
        blockers.append(f"queue_state={queue}")
    blockers.extend(str(item) for item in reason if item)
    if state == "evidence_repair" and primary == "promotion_vetoed":
        specific = "promotion_veto_must_clear_before_review_ready"
    elif state == "evidence_repair" and primary == "blocked_missing_freshness":
        specific = "freshness_or_source_family_must_be_repaired_before_review_ready"
    elif state == "evidence_repair":
        specific = "evidence_repair_required_before_review_ready"
    elif state == "blocked_missing_freshness":
        specific = "freshness_blocker_must_clear_before_review_ready"
    elif allowed:
        specific = "review_ready_not_approved"
    else:
        specific = "not_review_ready"
    return {
        "decision_grade_claim_allowed": allowed,
        "decision_grade_status": "review_ready_not_approved" if allowed else "not_decision_grade_yet",
        "specific_repair_required": specific,
        "blockers": sorted(set(blockers)),
        "may_use_approval_ready_language": allowed,
        "owner_approval_required_before_action": True,
        "capital_or_execution_authority": False,
    }


def portfolio_fit_with_current_route(card: dict[str, Any], wf85: dict[str, Any]) -> dict[str, Any]:
    """Return portfolio fit with the current WF85/WF78 route overlaid.

    Older ticker cards can carry historical `wf78_auto_tier` values. The full
    answer route must reflect the current decision card tier/state while keeping
    card provenance visible for audit.
    """
    fit = dict(as_dict(card.get("portfolio_fit_concentration")))
    current_tier = wf85.get("auto_tier")
    current_state = wf85.get("auto_state")
    previous_tier = fit.get("wf78_auto_tier")
    previous_state = fit.get("wf78_auto_state")
    if current_tier:
        fit["wf78_auto_tier"] = current_tier
        fit["current_route_tier"] = current_tier
    if current_state:
        fit["wf78_auto_state"] = current_state
        fit["current_route_state"] = current_state
    if previous_tier and current_tier and previous_tier != current_tier:
        fit["prior_card_wf78_auto_tier"] = previous_tier
    if previous_state and current_state and previous_state != current_state:
        fit["prior_card_wf78_auto_state"] = previous_state
    if wf85.get("decision_state"):
        fit["wf85_decision_state"] = wf85.get("decision_state")
    if wf85.get("primary_state"):
        fit["wf85_primary_state"] = wf85.get("primary_state")
    if wf85.get("queue_state"):
        fit["wf85_queue_state"] = wf85.get("queue_state")
    return fit


def technical_setup_data(card: dict[str, Any], wf84: dict[str, Any]) -> dict[str, Any]:
    card_technical = as_dict(card.get("technical_posture"))
    if present(card_technical):
        return card_technical
    wf84_technical = as_dict(wf84_section_raw(wf84, "technical_posture"))
    if present(wf84_technical):
        return wf84_technical
    return {}


def source_lineage(ticker: str, card: dict[str, Any], wf84: dict[str, Any], wf85: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = [
        {"kind": "wf85_decision_card", "path": rel(WF85_CARDS), "authority": "derived_review_only"},
        {"kind": "ticker_intelligence_card", "path": rel(card_path(ticker)), "authority": "derived_review_only"},
        {"kind": "wf84_canonical_data_plane", "path": rel(CANONICAL_DB), "authority": "derived_read_only"},
    ]
    for row in as_list(wf84.get("drillback")):
        path = as_dict(row).get("source_path") or as_dict(row).get("path")
        if path:
            rows.append({"kind": "wf84_drillback", "path": str(path).replace("\\", "/"), "authority": "source_drillback"})
    for row in as_list(card.get("source_artifacts")):
        path = as_dict(row).get("path")
        if path:
            rows.append({"kind": "card_source_artifact", "path": str(path).replace("\\", "/"), "authority": "derived_review_only"})
    seen: set[tuple[str, str]] = set()
    deduped: list[dict[str, Any]] = []
    for row in rows:
        key = (row.get("kind", ""), row.get("path", ""))
        if key not in seen:
            seen.add(key)
            deduped.append(row)
    return deduped


def pct_value(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return round(float(value), 2)
    except (TypeError, ValueError):
        return None


def macro_component(cpi_detail: dict[str, Any], key: str) -> dict[str, Any]:
    row = as_dict(cpi_detail.get(key))
    return {
        "latest_mom_pct": pct_value(row.get("latest_mom_pct")),
        "previous_mom_pct": pct_value(row.get("previous_mom_pct")),
        "yoy_pct": pct_value(row.get("yoy_pct")),
    }


def classify_inflation_posture(cpi_detail: dict[str, Any]) -> str:
    headline = pct_value(get_path(cpi_detail, "all_items.latest_mom_pct"))
    core = pct_value(get_path(cpi_detail, "core.latest_mom_pct"))
    if headline is None or core is None:
        return "cpi_detail_incomplete"
    if headline >= 0.35 and core < 0.3:
        return "headline_hot_core_contained"
    if headline >= 0.35 and core >= 0.3:
        return "headline_and_core_hot"
    if headline < 0.25 and core < 0.25:
        return "contained"
    return "mixed"


def classify_cpi_driver(cpi_detail: dict[str, Any]) -> str:
    energy = pct_value(get_path(cpi_detail, "energy.latest_mom_pct"))
    gasoline = pct_value(get_path(cpi_detail, "gasoline.latest_mom_pct"))
    shelter = pct_value(get_path(cpi_detail, "shelter.latest_mom_pct"))
    core = pct_value(get_path(cpi_detail, "core.latest_mom_pct"))
    if gasoline is not None and gasoline >= 1.0:
        return "energy_gasoline_headline_pressure"
    if energy is not None and energy >= 1.0:
        return "energy_headline_pressure"
    if shelter is not None and shelter >= 0.4:
        return "shelter_stickiness"
    if core is not None and core >= 0.3:
        return "broad_core_pressure"
    return "mixed_or_contained"


def macro_risk_context() -> dict[str, Any]:
    macro_metrics = as_dict(load_json(MACRO_METRICS, {}))
    macro_judgment = as_dict(load_json(MACRO_JUDGMENT, {}))
    market_today = as_dict(load_json(MARKET_TODAY, {}))
    cpi_detail = as_dict(get_path(macro_metrics, "summary.cpi_release_detail"))
    judgments = as_dict(macro_judgment.get("judgments"))
    pulse = as_dict(judgments.get("pulse_read"))
    market_readiness = as_dict(market_today.get("answer_readiness"))
    broad_table = as_list(market_today.get("normalized_broad_index_daily_change_table"))
    rates = as_dict(market_today.get("rates_energy_fx"))
    driver_digest = as_list(market_today.get("source_backed_market_driver_news_digest"))
    status = "available" if cpi_detail or pulse or market_today else "source_open_required"
    return {
        "status": status,
        "review_only": True,
        "source_artifacts": [
            {"path": rel(MACRO_METRICS), "status": macro_metrics.get("status"), "generated_at_utc": macro_metrics.get("generated_at_utc")},
            {"path": rel(MACRO_JUDGMENT), "status": macro_judgment.get("status"), "generated_at_utc": macro_judgment.get("generated_at_utc")},
            {"path": rel(MARKET_TODAY), "status": market_today.get("status"), "generated_at_utc": market_today.get("generated_at_utc")},
        ],
        "macro_metrics_status": macro_metrics.get("status"),
        "macro_judgment_status": macro_judgment.get("status"),
        "macro_judgment_validation_status": as_dict(macro_judgment.get("validation")).get("status"),
        "market_today_status": market_today.get("status"),
        "market_today_validation_status": as_dict(market_today.get("validation")).get("status"),
        "market_tape_context": {
            "can_answer_full_market_close_recap_without_web": market_readiness.get("can_answer_full_market_close_recap_without_web"),
            "missing_for_web_free_full_recap": as_list(market_readiness.get("missing_for_web_free_full_recap")),
            "local_answer_summary": market_today.get("local_answer_summary"),
            "broad_index_daily_change_table": [
                row for row in broad_table
                if isinstance(row, dict) and row.get("normalized_symbol") in {"SPX", "DOW", "NASDAQ_COMPOSITE", "NASDAQ_100", "RUSSELL_2000"}
            ],
            "rates": {
                "treasury_2y_pct": rates.get("treasury_2y_pct"),
                "treasury_2y_as_of": rates.get("treasury_2y_as_of"),
                "treasury_2y_source": rates.get("treasury_2y_source"),
                "treasury_10y_pct": rates.get("treasury_10y_pct"),
                "curve_2s10s_bps": rates.get("curve_2s10s_bps"),
                "brent": rates.get("brent"),
                "wti": rates.get("wti"),
            },
            "source_backed_market_driver_digest": [
                row for row in driver_digest if isinstance(row, dict)
            ][:5],
            "claim_boundary": "market tape context is evidence burden and risk framing only; it does not prove single-name causality or approve action",
        },
        "inflation_posture": classify_inflation_posture(cpi_detail),
        "cpi_driver": classify_cpi_driver(cpi_detail),
        "cpi_release_detail": {
            "status": cpi_detail.get("status"),
            "source": cpi_detail.get("source"),
            "source_url": cpi_detail.get("source_url"),
            "source_mode": cpi_detail.get("source_mode"),
            "release_period": cpi_detail.get("release_period"),
            "release_date_text": cpi_detail.get("release_date_text"),
            "all_items": macro_component(cpi_detail, "all_items"),
            "core": macro_component(cpi_detail, "core"),
            "energy": macro_component(cpi_detail, "energy"),
            "gasoline": macro_component(cpi_detail, "gasoline"),
            "shelter": macro_component(cpi_detail, "shelter"),
            "rent": macro_component(cpi_detail, "rent"),
            "owners_equivalent_rent": macro_component(cpi_detail, "owners_equivalent_rent"),
        },
        "macro_pulse_read": {
            "text": pulse.get("text"),
            "confidence": pulse.get("confidence"),
            "source_basis": as_list(pulse.get("source_basis")),
        },
        "ticker_use": {
            "risk_effect": "adjust evidence burden, broad tape awareness, rate sensitivity, valuation discipline, and no-chase language",
            "action_effect": "review context only; does not approve capital, sizing, paper, live, brokerage, account, or portfolio action",
            "capital_deployment_approved": False,
            "trade_or_execution_approved": False,
            "owner_approval_inferred": False,
        },
    }


def build_sections(ticker: str, card: dict[str, Any], wf84: dict[str, Any], wf85: dict[str, Any]) -> dict[str, dict[str, Any]]:
    tg = trade_grade(wf85, card)
    oa = owner_action(wf85)
    gate = decision_grade_gate(wf85)
    portfolio_fit = portfolio_fit_with_current_route(card, wf85)
    technical_data = technical_setup_data(card, wf84)
    macro_context = macro_risk_context()
    return {
        "thesis": section("thesis", "Thesis", card.get("thesis_bull_bear_entry_context")),
        "business_quality_moat": section("business_quality_moat", "Business / Moat / Quality", {
            "universe_metadata": card.get("universe_metadata"),
            "competitive_moat": card.get("competitive_moat"),
            "capital_allocation_quality": card.get("capital_allocation_quality"),
        }),
        "bull_case": section("bull_case", "Bull Case", {"bull_case": as_dict(card.get("thesis_bull_bear_entry_context")).get("bull_case_inputs"), "wf85_bull_case": wf85.get("bull_case")}),
        "bear_case": section("bear_case", "Bear Case", {"bear_case": as_dict(card.get("thesis_bull_bear_entry_context")).get("bear_case_inputs"), "wf85_bear_case": wf85.get("bear_case"), "risks": card.get("risk_register")}),
        "earnings_guidance": section("earnings_guidance", "Earnings + Guidance", {"latest_earnings": card.get("latest_earnings_performance"), "catalyst_earnings_state": card.get("catalyst_earnings_state")}),
        "financial_metrics": section("financial_metrics", "Financial Metrics", {"key_financial_metrics": card.get("key_financial_metrics"), "official_fundamentals": card.get("official_fundamentals"), "fundamental_reconciliation": card.get("fundamental_reconciliation")}),
        "valuation": section("valuation", "Valuation", card.get("valuation")),
        "technical_setup": section("technical_setup", "Technical Setup", technical_data),
        "catalyst_news_macro": section("catalyst_news_macro", "Catalyst / News / Macro Sensitivity", {
            "recent_developments": card.get("recent_developments"),
            "sector_performance": card.get("current_sector_performance"),
            "etf_or_macro_proxy_profile": card.get("etf_or_macro_proxy_profile"),
            "orders_backlog_book_to_bill": card.get("orders_backlog_book_to_bill"),
            "macro_risk_context": macro_context,
        }),
        "risk_invalidation": section("risk_invalidation", "Risk + Invalidation", {"risk_register": card.get("risk_register"), "wf85_key_risks": wf85.get("key_risks"), "counterargument": wf85.get("counterargument"), "stop_or_invalidation": wf85.get("stop_or_invalidation"), "macro_risk_context": macro_context}),
        "portfolio_fit": section("portfolio_fit", "Portfolio Fit", portfolio_fit),
        "entry_stop_sizing": section("entry_stop_sizing", "Entry / Stop / Sizing", {"current_price": wf85.get("current_price"), "entry_band": wf85.get("entry_band"), "stop_or_invalidation": wf85.get("stop_or_invalidation"), "sizing": wf85.get("sizing_staggering_recommendation")}),
        "decision_state": section("decision_state", "Decision State", {"research_tier": tg.get("research_tier"), "decision_state": wf85.get("decision_state"), "primary_state": wf85.get("primary_state"), "queue_state": wf85.get("queue_state"), "auto_state": wf85.get("auto_state"), "decision_state_reason": wf85.get("decision_state_reason"), "decision_grade_gate": gate}, confidence="high"),
        "trade_grade": section("trade_grade", "Trade Grade", {**tg, "decision_grade_gate": gate}, confidence="high"),
        "owner_action": section("owner_action", "Owner Action", {**oa, "decision_grade_gate": gate}, confidence="high"),
        "authority_approval_status": section("authority_approval_status", "Authority / Approval Status", {"wf85_authority_boundary": wf85.get("authority_boundary"), "assembler_authority_boundary": AUTHORITY_BOUNDARY}, confidence="high"),
        "evidence_freshness_confidence": section("evidence_freshness_confidence", "Evidence / Freshness / Confidence", {"source_freshness": wf85.get("source_freshness"), "evidence_family_status": wf85.get("evidence_family_status"), "wf84_drillback_count": len(as_list(wf84.get("drillback")))}, confidence="high"),
    }


def section_summary(section_row: dict[str, Any]) -> str:
    raw = section_row.get("raw")
    if not present(raw):
        return "source-open required"
    if isinstance(raw, dict):
        if isinstance(raw.get("decision_grade_gate"), dict):
            gate = raw["decision_grade_gate"]
            status = gate.get("decision_grade_status") or "unknown"
            repair = gate.get("specific_repair_required") or "none"
            return f"decision-grade gate: {status}; repair: {repair}"
        if raw.get("current_route_tier") or raw.get("prior_card_wf78_auto_tier"):
            current = raw.get("current_route_tier") or raw.get("wf78_auto_tier") or "unknown"
            current_state = raw.get("current_route_state") or raw.get("wf78_auto_state") or "unknown"
            prior = raw.get("prior_card_wf78_auto_tier")
            prior_state = raw.get("prior_card_wf78_auto_state")
            prior_note = f"; prior card: {prior} / {prior_state or 'unknown'}" if prior or prior_state else ""
            decision = f"; decision: {raw.get('wf85_decision_state')}" if raw.get("wf85_decision_state") else ""
            return f"current route: {current} / {current_state}{prior_note}{decision}"
        for key in ("summary", "thesis", "grade", "decision_state", "owner_action", "status", "band_status"):
            value = raw.get(key)
            if value not in (None, "", [], {}):
                return f"{key}: {value}"
        keys = [key for key, value in raw.items() if present(value)]
        return "mapped fields: " + ", ".join(keys[:5])
    if isinstance(raw, list):
        return f"{len(raw)} item(s)"
    return str(raw)[:240]


def human_answer_text(ticker: str, sections: dict[str, dict[str, Any]], wf85: dict[str, Any], tg: dict[str, Any], oa: dict[str, Any]) -> str:
    gate = decision_grade_gate(wf85)
    lines = [
        f"{ticker} Trade-Grade Full Answer",
        f"Decision state: {wf85.get('decision_state')}",
        f"Decision-grade gate: {gate.get('decision_grade_status')} / repair: {gate.get('specific_repair_required')}",
        f"Trade grade: {tg.get('grade')} / actionability: {tg.get('actionability')}",
        f"Owner action: {oa.get('owner_action')}",
        "Authority: review-only; no trade, capital, account, or approval authority.",
        "",
    ]
    for section_id in REQUIRED_SECTION_IDS:
        row = sections[section_id]
        lines.append(f"{row['title']}: {section_summary(row)}")
    return "\n".join(lines)


def legacy_analyst(card: dict[str, Any]) -> dict[str, Any]:
    analyst = as_dict(card.get("analyst_consensus_ratings_targets"))
    return {
        "status": analyst.get("status", "missing"),
        "consensus_rating": analyst.get("consensus_rating"),
        "average_target": analyst.get("average_target"),
        "median_target": analyst.get("median_target"),
        "high_target": analyst.get("high_target"),
        "low_target": analyst.get("low_target"),
        "implied_upside_downside_pct": analyst.get("implied_upside_downside_pct"),
        "counts": {
            "strong_buy": analyst.get("strong_buy_count"),
            "buy": analyst.get("buy_count"),
            "hold": analyst.get("hold_count"),
            "sell": analyst.get("sell_count"),
            "strong_sell": analyst.get("strong_sell_count"),
        },
        "provider": analyst.get("provider"),
        "provider_confidence": analyst.get("confidence"),
        "stale": analyst.get("stale"),
    }


def legacy_portfolio_fit(card: dict[str, Any], wf85: dict[str, Any]) -> dict[str, Any]:
    fit = portfolio_fit_with_current_route(card, wf85)
    return {
        "status": "available" if fit else "missing",
        "sector": fit.get("sector"),
        "tier": fit.get("wf78_tier"),
        "wf78_auto_tier": fit.get("wf78_auto_tier"),
        "wf78_auto_state": fit.get("wf78_auto_state"),
        "current_route_tier": fit.get("current_route_tier"),
        "current_route_state": fit.get("current_route_state"),
        "prior_card_wf78_auto_tier": fit.get("prior_card_wf78_auto_tier"),
        "prior_card_wf78_auto_state": fit.get("prior_card_wf78_auto_state"),
        "wf85_decision_state": fit.get("wf85_decision_state"),
        "wf78_tier": fit.get("wf78_tier"),
        "wf78_decision_grade_eligible": fit.get("wf78_decision_grade_eligible"),
        "portfolio_role": fit.get("portfolio_role"),
        "coverage_lane": fit.get("coverage_lane"),
        "monitoring_role": fit.get("wf78_monitoring_role"),
        "recommended_starter_notional": fit.get("recommended_starter_notional"),
        "recommended_target_notional": fit.get("recommended_target_notional"),
        "decision_note": fit.get("decision_note"),
    }


def legacy_effective_price_context(wf85: dict[str, Any], card: dict[str, Any]) -> dict[str, Any]:
    current_price = as_dict(wf85.get("current_price"))
    pbs = as_dict(card.get("price_band_stop"))
    if current_price.get("latest_known_price") is not None:
        return {
            "status": "available",
            "effective_price": current_price.get("latest_known_price"),
            "price_source": current_price.get("source"),
            "market_date": current_price.get("market_date"),
            "as_of_utc": current_price.get("quote_time_utc"),
            "post_close_overlay_applied": current_price.get("source") == rel(POST_CLOSE_LEDGER),
            "fresh_quote_required": bool(pbs.get("fresh_quote_required")),
            "card_latest_known_price": card.get("latest_known_price"),
            "quote_freshness_status": current_price.get("quote_freshness_status"),
        }
    return {
        "status": "available" if card.get("latest_known_price") is not None else "missing",
        "effective_price": card.get("latest_known_price"),
        "price_source": pbs.get("price_source"),
        "fresh_quote_required": bool(pbs.get("fresh_quote_required")),
        "post_close_overlay_applied": False,
    }


def legacy_action_state(wf85: dict[str, Any], card: dict[str, Any]) -> dict[str, Any]:
    rs = as_dict(card.get("recommendation_support"))
    pbs = as_dict(card.get("price_band_stop"))
    decision_state = wf85.get("decision_state")
    legacy_deployment_status = {
        "review_ready": "REVIEW_READY",
        "no_chase": "NO_CHASE",
        "evidence_repair": "EVIDENCE_REPAIR",
        "below_stop_or_invalidation": "DO_NOT_TOUCH",
        "monitor_only": "DO_NOT_TOUCH",
    }.get(str(decision_state or ""), decision_state)
    return {
        "status": "available" if decision_state else "missing",
        "deployment_status": legacy_deployment_status,
        "display_label": decision_state,
        "wf85_decision_state": decision_state,
        "workflow_state": wf85.get("primary_state"),
        "band_status": as_dict(wf85.get("entry_band")).get("band_status") or pbs.get("band_status"),
        "below_stop": decision_state == "below_stop_or_invalidation",
        "support_level": rs.get("support_level"),
        "actionability": as_dict(wf84_context(str(wf85.get("ticker") or "")).get("current")).get("actionability") if wf85.get("ticker") else rs.get("actionability"),
    }


def legacy_recommended_next_action(wf85: dict[str, Any], tg: dict[str, Any], oa: dict[str, Any], eff: dict[str, Any]) -> dict[str, Any]:
    return {
        "action": oa.get("owner_action"),
        "urgency": "review" if wf85.get("decision_state") == "review_ready" else "none",
        "owner_approval_required": True,
        "execution_authorized": False,
        "based_on": {
            "decision_state": wf85.get("decision_state"),
            "trade_grade": tg.get("grade"),
            "band_status": as_dict(wf85.get("entry_band")).get("band_status"),
            "effective_price": eff.get("effective_price"),
        },
    }


def build_full_answer(ticker: str) -> tuple[dict[str, Any] | None, list[str]]:
    ticker = ticker.upper()
    issues: list[str] = []
    card = as_dict(load_json(card_path(ticker), {}))
    if not card:
        return None, [f"ticker_intelligence_card_missing:{rel(card_path(ticker))}"]
    wf85 = wf85_cards_by_ticker().get(ticker, {})
    if not wf85:
        issues.append("wf85_decision_card_missing")
    wf84 = wf84_context(ticker)
    sections = build_sections(ticker, card, wf84, wf85)
    conf = confidence_by_domain(card, wf85, sections)
    answer_conf = answer_confidence(conf)
    tg = trade_grade(wf85, card)
    oa = owner_action(wf85)
    gate = decision_grade_gate(wf85)
    lineage = source_lineage(ticker, card, wf84, wf85)
    forbidden = recursive_forbidden_true({"sections": sections, "wf85": wf85, "authority": AUTHORITY_BOUNDARY})
    missing_sections = [sid for sid in REQUIRED_SECTION_IDS if sections[sid]["status"] != "available"]
    status = "blocked" if forbidden else "ok"
    packet = {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "workflow_ids": ["WF84", "WF85"],
        "status": status,
        "ticker": ticker,
        "review_only": True,
        "canonical_full_answer_contract": {
            "required_sections": REQUIRED_SECTION_IDS,
            "machine_state_fields_separated": True,
            "answer_packet_role": "compatibility_snapshot_only",
            "source_open_required_before_material_claims": True,
        },
        "source_artifacts": {
            "wf84_db": rel(CANONICAL_DB),
            "wf85_cards": rel(WF85_CARDS),
            "ticker_intelligence_card": rel(card_path(ticker)),
            "post_close_ledger": rel(POST_CLOSE_LEDGER),
            "macro_metrics": rel(MACRO_METRICS),
            "macro_judgment": rel(MACRO_JUDGMENT),
            "market_today_answer_packet": rel(MARKET_TODAY),
        },
        "identity": {
            "ticker": ticker,
            "name": wf85.get("name") or card.get("name") or as_dict(card.get("universe_metadata")).get("name"),
            "instrument_type": card.get("instrument_type"),
            "research_tier": tg.get("research_tier"),
        },
        "machine_state": {
            "research_tier": tg.get("research_tier"),
            "decision_state": wf85.get("decision_state"),
            "primary_state": wf85.get("primary_state"),
            "queue_state": wf85.get("queue_state"),
            "decision_grade_gate": gate,
            "trade_grade": tg,
            "execution_eligibility": {
                "status": "paper_review_candidate" if wf85.get("decision_state") == "review_ready" else "not_eligible",
                "paper_trade_allowed": False,
                "live_trade_allowed": False,
                "requires_exact_owner_approval": True,
            },
            "owner_action": oa,
        },
        "sections": sections,
        "section_order": REQUIRED_SECTION_IDS,
        "answer_confidence": answer_conf,
        "confidence_by_domain": conf,
        "source_count": len({row.get("path") for row in lineage if row.get("path")}),
        "source_lineage": lineage,
        "human_answer_text": human_answer_text(ticker, sections, wf85, tg, oa),
        "validation": {
            "status": status,
            "errors": [f"forbidden_authority:{row['path']}" for row in forbidden],
            "warnings": [f"section_source_open_required:{sid}" for sid in missing_sections],
            "missing_sections": missing_sections,
            "forbidden_authority": forbidden,
        },
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "stop_lines": [
            "Generated answer is review-only and not canon.",
            "No paper/live order, capital deployment, account action, money movement, or owner approval inference.",
            "Legacy answer packets generated from this assembler are compatibility snapshots only.",
        ],
    }
    return packet, issues


def build_legacy_answer_packet(ticker: str) -> tuple[dict[str, Any] | None, list[str]]:
    full, issues = build_full_answer(ticker)
    if full is None:
        return None, issues
    ticker = ticker.upper()
    card = as_dict(load_json(card_path(ticker), {}))
    wf85 = wf85_cards_by_ticker().get(ticker, {})
    sections = as_dict(full.get("sections"))
    tg = as_dict(as_dict(full.get("machine_state")).get("trade_grade"))
    oa = as_dict(as_dict(full.get("machine_state")).get("owner_action"))
    eff = legacy_effective_price_context(wf85, card)
    action = legacy_action_state(wf85, card)
    rec = legacy_recommended_next_action(wf85, tg, oa, eff)
    packet = {
        "schema_version": LEGACY_PACKET_SCHEMA_VERSION,
        "artifact_type": "ticker_answer_packet_v1",
        "ticker": ticker,
        "generated_at_utc": full.get("generated_at_utc"),
        "review_only": True,
        "source_card_generated_at_utc": card.get("generated_at_utc"),
        "freshness": {
            "stale_after_hours": STALE_AFTER_HOURS,
            "built_from_card_at_utc": card.get("generated_at_utc"),
            "built_from_trade_grade_full_answer_assembler": True,
            "assembler_schema": SCHEMA,
            "note": "Compatibility snapshot generated from WF85 full-answer assembler.",
        },
        "answer_confidence": full.get("answer_confidence"),
        "confidence_by_domain": full.get("confidence_by_domain"),
        "source_count": full.get("source_count"),
        "source_lineage": full.get("source_lineage"),
        "effective_price_context": eff,
        "action_state": action,
        "price_band_stop": card.get("price_band_stop") or {"status": "missing"},
        "technical_posture": as_dict(sections.get("technical_setup")).get("raw") or {"status": "missing"},
        "thesis_summary": as_dict(sections.get("thesis")).get("raw") or {"status": "source_open_required"},
        "bull_case": as_dict(sections.get("bull_case")).get("raw") or {"status": "source_open_required"},
        "bear_case": as_dict(sections.get("bear_case")).get("raw") or {"status": "source_open_required"},
        "latest_earnings": card.get("latest_earnings_performance") or {"status": "missing"},
        "key_financial_metrics": card.get("key_financial_metrics") or {"status": "missing"},
        "analyst_consensus": legacy_analyst(card),
        "portfolio_fit": legacy_portfolio_fit(card, wf85),
        "blockers": [
            {"kind": "wf85_decision_state_reason", "detail": item}
            for item in as_list(wf85.get("decision_state_reason"))
        ] + [
            {"kind": "missing_or_stale_evidence", "detail": item}
            for item in as_list(card.get("missing_or_stale_evidence"))
        ],
        "recommended_next_action": rec,
        "authority_boundary": {
            **AUTHORITY_BOUNDARY,
            "artifact_role": "derived_ticker_answer_response_and_route_layer_only",
            "generated_packet_is_canon": False,
            "source_open_required_before_final_recommendation_or_action_claim": True,
            "sql_canon_migration_allowed": False,
        },
        "field_provenance": {
            "ticker": "assembler_derived",
            "generated_at_utc": "generated",
            "answer_confidence": "wf85_full_answer_assembler",
            "confidence_by_domain": "wf85_full_answer_assembler",
            "source_count": "wf85_full_answer_assembler",
            "source_lineage": "wf85_full_answer_assembler",
            "effective_price_context": "wf85_current_price_or_card",
            "action_state": "wf85_decision_state",
            "price_band_stop": "ticker_intelligence_card_with_wf85_overlay",
            "technical_posture": "ticker_intelligence_card_or_wf84_repair_state",
            "thesis_summary": "wf85_full_answer_section",
            "bull_case": "wf85_full_answer_section",
            "bear_case": "wf85_full_answer_section",
            "latest_earnings": "ticker_intelligence_card",
            "key_financial_metrics": "ticker_intelligence_card",
            "analyst_consensus": "ticker_intelligence_card",
            "portfolio_fit": "ticker_intelligence_card",
            "blockers": "wf85_decision_state_and_card_evidence",
            "recommended_next_action": "wf85_full_answer_assembler_review_only",
            "authority_boundary": "review_only_boundary",
        },
    }
    return packet, issues


def validate_full_answer(packet: dict[str, Any]) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []

    def add(name: str, passed: bool, detail: Any, severity: str = "error") -> None:
        checks.append({"name": name, "passed": bool(passed), "severity": severity, "detail": detail})

    sections = as_dict(packet.get("sections"))
    missing_keys = [sid for sid in REQUIRED_SECTION_IDS if sid not in sections]
    add("all_required_sections_present", not missing_keys, {"missing": missing_keys})
    add("human_answer_text_present", bool(packet.get("human_answer_text")), "human answer text must be emitted")
    add("machine_state_separated", isinstance(packet.get("machine_state"), dict), "machine_state must be structured")
    machine = as_dict(packet.get("machine_state"))
    gate = as_dict(machine.get("decision_grade_gate"))
    decision_state = machine.get("decision_state")
    add("decision_grade_gate_present", bool(gate), "decision_grade_gate must be structured")
    add(
        "repair_states_not_decision_grade",
        decision_state not in {"evidence_repair", "blocked_missing_freshness"} or gate.get("decision_grade_claim_allowed") is False,
        {"decision_state": decision_state, "gate": gate},
    )
    forbidden = recursive_forbidden_true(packet)
    add("no_forbidden_authority_true", not forbidden, {"forbidden": forbidden})
    boundary = as_dict(packet.get("authority_boundary"))
    add("archive_delete_apply_false", boundary.get("archive_allowed") is False and boundary.get("delete_allowed") is False and boundary.get("apply_allowed") is False, boundary)
    add("execution_authority_false", boundary.get("paper_or_live_execution_allowed") is False and boundary.get("live_trade_allowed") is False, boundary)
    return checks


def validate_legacy_packet(packet: dict[str, Any]) -> list[dict[str, Any]]:
    required = [
        "ticker", "generated_at_utc", "answer_confidence", "confidence_by_domain",
        "source_count", "source_lineage", "effective_price_context", "action_state",
        "price_band_stop", "technical_posture", "thesis_summary", "bull_case",
        "bear_case", "latest_earnings", "key_financial_metrics", "analyst_consensus",
        "portfolio_fit", "blockers", "recommended_next_action", "authority_boundary",
    ]
    checks: list[dict[str, Any]] = []
    missing = [field for field in required if field not in packet]
    checks.append({"name": "legacy_packet_required_fields_present", "passed": not missing, "severity": "error", "detail": {"missing": missing}})
    forbidden = recursive_forbidden_true(packet)
    checks.append({"name": "legacy_packet_no_forbidden_authority_true", "passed": not forbidden, "severity": "error", "detail": {"forbidden": forbidden}})
    checks.append({
        "name": "legacy_packet_from_assembler",
        "passed": as_dict(packet.get("freshness")).get("built_from_trade_grade_full_answer_assembler") is True,
        "severity": "error",
        "detail": as_dict(packet.get("freshness")),
    })
    return checks


def write_full_answer(packet: dict[str, Any]) -> Path:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    path = full_answer_path(str(packet["ticker"]))
    atomic_write_json(path, packet)
    return path


def write_legacy_packet(ticker: str, packet: dict[str, Any]) -> Path:
    ANSWER_PACKET_DIR.mkdir(parents=True, exist_ok=True)
    path = legacy_packet_path(ticker)
    atomic_write_json(path, packet)
    return path


def build_rollup(tickers: list[str], *, write: bool, write_legacy_packets: bool, validate: bool) -> dict[str, Any]:
    results: list[dict[str, Any]] = []
    validation_checks: list[dict[str, Any]] = []
    for ticker in tickers:
        full, issues = build_full_answer(ticker)
        if full is None:
            results.append({"ticker": ticker, "status": "failed", "issues": issues})
            continue
        full_checks = validate_full_answer(full) if validate else []
        legacy, legacy_issues = build_legacy_answer_packet(ticker)
        legacy_checks = validate_legacy_packet(legacy) if validate and isinstance(legacy, dict) else []
        validation_checks.extend({"ticker": ticker, **check} for check in full_checks)
        validation_checks.extend({"ticker": ticker, **check} for check in legacy_checks)
        full_path = write_full_answer(full) if write else full_answer_path(ticker)
        legacy_path = write_legacy_packet(ticker, legacy) if write and write_legacy_packets and isinstance(legacy, dict) else legacy_packet_path(ticker)
        errors = [
            check for check in [*full_checks, *legacy_checks]
            if not check.get("passed") and check.get("severity") == "error"
        ]
        results.append({
            "ticker": ticker,
            "status": "built" if not errors else "blocked",
            "full_answer_path": rel(full_path),
            "legacy_packet_path": rel(legacy_path) if write_legacy_packets else None,
            "decision_state": as_dict(full.get("machine_state")).get("decision_state"),
            "trade_grade": as_dict(as_dict(full.get("machine_state")).get("trade_grade")).get("grade"),
            "missing_sections": as_dict(full.get("validation")).get("missing_sections") or [],
            "issues": [*issues, *legacy_issues],
        })
    errors = [check for check in validation_checks if not check.get("passed") and check.get("severity") == "error"]
    warnings = [check for check in validation_checks if not check.get("passed") and check.get("severity") == "warning"]
    return {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "ok" if not errors and all(row["status"] == "built" for row in results) else "blocked",
        "workflow_ids": ["WF84", "WF85"],
        "purpose": "Build canonical WF85 full-answer objects and optional legacy answer-packet compatibility snapshots.",
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "summary": {
            "requested_ticker_count": len(tickers),
            "full_answer_built_count": sum(1 for row in results if row["status"] == "built"),
            "legacy_packet_write_requested": write_legacy_packets,
            "legacy_packet_generation_source": "trade_grade_full_answer_assembler",
            "validation_error_count": len(errors),
            "validation_warning_count": len(warnings),
            "required_section_count": len(REQUIRED_SECTION_IDS),
        },
        "required_sections": REQUIRED_SECTION_IDS,
        "results": results,
        "validation": {
            "status": "ok" if not errors else "blocked",
            "errors": errors[:100],
            "warnings": warnings[:100],
            "checks": validation_checks[:500],
        },
        "retirement_signal": {
            "ticker_answer_packets_are_compatibility_snapshots": True,
            "answer_packets_may_be_retired_after_reader_inventory_and_exact_owner_approval": True,
            "archive_delete_apply_allowed": False,
        },
        "stop_lines": [
            "No archive/delete/apply authority.",
            "No source feeder or evidence cache retirement.",
            "No paper/live/account/capital action or owner approval inference.",
        ],
    }


def parse_tickers(text: str | None) -> list[str]:
    return [item.strip().upper() for item in (text or "").split(",") if item.strip()]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--ticker", help="Build one ticker")
    group.add_argument("--tickers", help="Comma-separated ticker list")
    group.add_argument("--all-production", action="store_true", help="Build current production answer-path tickers")
    group.add_argument("--all-wf84", action="store_true", help="Build every ticker in WF84")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--write-legacy-packets", action="store_true", help="Also write tmp/ticker-answer-packets compatibility snapshots")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--pretty", action="store_true")
    parser.add_argument("--out", type=Path, default=ROLLUP_OUT)
    args = parser.parse_args()

    with wf84_sqlite_mutex(CANONICAL_DB, role="trade_grade_full_answer_reader"):
        if args.ticker:
            tickers = [args.ticker.strip().upper()]
        elif args.tickers:
            tickers = parse_tickers(args.tickers)
        elif args.all_production:
            tickers = production_tickers()
        else:
            tickers = wf84_tickers()
        rollup = build_rollup(tickers, write=args.write, write_legacy_packets=args.write_legacy_packets, validate=args.validate)
    if args.write:
        atomic_write_json(args.out, rollup)
    print(json.dumps({"status": rollup["status"], "out": rel(args.out), "summary": rollup["summary"], "validation": rollup["validation"]}, indent=2 if args.pretty else None))
    if args.validate and rollup["status"] != "ok":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
