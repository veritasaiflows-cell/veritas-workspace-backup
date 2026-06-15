#!/usr/bin/env python3
"""Build WF84/WF85 full ticker-answer parity proof.

This is the value-level bridge between the WF85 full-answer assembler and the
WF84 canonical data-plane. It is report-only: it never archives, deletes,
mutates canon/portfolio notes, grants approval, or touches execution.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCRIPTS = Path(__file__).resolve().parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from canonical_finance_data_plane import DEFAULT_DB, as_dict, as_list, connect_ro, json_text, rel
from market_data_utils import atomic_write_json

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
OUT_DIR = TMP / "full-answer-parity"
DEFAULT_ROLLUP = OUT_DIR / "full-answer-parity-rollup.json"
FULL_ANSWER_DIR = TMP / "trade-grade-full-answer"
TICKER_CARD_DIR = TMP / "ticker-intelligence-cards"
WF85_CARDS = TMP / "trade-grade-decision-cards.json"

SCHEMA = "veritas.full_intelligence_answer_parity.v1"
PILOT_TICKERS = ["GOOG", "NVDA", "VRT", "BRK.B", "TLT"]
NUMERIC_TOLERANCE = 0.01

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
    "owner_approval_inferred",
    "owner_approval_granted",
    "archive_allowed",
    "delete_allowed",
    "apply_allowed",
}

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "report_only": True,
    "source_open_required_before_material_finance_claims": True,
    "wf84_wf85_route_validation_only": True,
    "archive_allowed": False,
    "delete_allowed": False,
    "apply_allowed": False,
    "canon_or_portfolio_mutation_allowed": False,
    "capital_deployment_allowed": False,
    "capital_deployment_approved": False,
    "trade_or_execution_approved": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "money_movement_allowed": False,
    "owner_approval_inferred": False,
}

FULL_ANSWER_CONTRACT: list[dict[str, Any]] = [
    {"section_id": "identity", "assembler_section_id": None, "card_key": "universe_metadata", "material": True},
    {"section_id": "thesis", "assembler_section_id": "thesis", "card_key": "thesis_bull_bear_entry_context", "material": True},
    {"section_id": "bull_case", "assembler_section_id": "bull_case", "card_key": "thesis_bull_bear_entry_context", "material": True},
    {"section_id": "bear_case", "assembler_section_id": "bear_case", "card_key": "thesis_bull_bear_entry_context", "material": True},
    {"section_id": "latest_earnings", "assembler_section_id": "earnings_guidance", "card_key": "latest_earnings_performance", "material": True},
    {"section_id": "key_financial_metrics", "assembler_section_id": "financial_metrics", "card_key": "key_financial_metrics", "material": True},
    {"section_id": "valuation", "assembler_section_id": "valuation", "card_key": "valuation", "material": True},
    {"section_id": "competitive_moat", "assembler_section_id": "business_quality_moat", "card_key": "competitive_moat", "material": True},
    {"section_id": "recent_developments_catalysts", "assembler_section_id": "catalyst_news_macro", "card_key": "recent_developments", "material": True},
    {"section_id": "analyst_consensus", "assembler_section_id": None, "card_key": "analyst_consensus_ratings_targets", "material": True},
    {"section_id": "technical_posture", "assembler_section_id": "technical_setup", "card_key": "technical_posture", "material": True},
    {"section_id": "sector_macro_context", "assembler_section_id": "catalyst_news_macro", "card_key": "current_sector_performance", "material": True},
    {"section_id": "risks_counterarguments", "assembler_section_id": "risk_invalidation", "card_key": "risk_register", "material": True},
    {"section_id": "entry_band_stop", "assembler_section_id": "entry_stop_sizing", "card_key": "price_band_stop", "material": True},
    {"section_id": "portfolio_fit", "assembler_section_id": "portfolio_fit", "card_key": "portfolio_fit_concentration", "material": True},
    {"section_id": "recommendation_posture", "assembler_section_id": "decision_state", "card_key": "recommendation_support", "material": True},
    {"section_id": "authority_boundary", "assembler_section_id": "authority_approval_status", "card_key": "authority_boundary", "material": True},
]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_json(path: Path, default: Any = None) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return default


def parse_json_text(value: Any, default: Any = None) -> Any:
    if not isinstance(value, str):
        return default
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return default


def stable_hash(value: Any) -> str:
    return hashlib.sha256(json_text(value).encode("utf-8")).hexdigest()


def present(value: Any) -> bool:
    if isinstance(value, dict):
        if not value:
            return False
        status = str(value.get("status") or "").lower()
        if status in {"missing", "unavailable", "source_open_required"} and len(value) <= 2:
            return False
        return any(child not in (None, "", [], {}) for child in value.values())
    if isinstance(value, list):
        return bool(value)
    return value not in (None, "")


def recursive_forbidden_true(value: Any, path: str = "$") -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}.{key}"
            if key in FORBIDDEN_TRUE_FLAGS and child is True:
                found.append({"path": child_path, "flag": key})
            found.extend(recursive_forbidden_true(child, child_path))
    elif isinstance(value, list):
        for idx, child in enumerate(value):
            found.extend(recursive_forbidden_true(child, f"{path}[{idx}]"))
    return found


def full_answer_path(ticker: str) -> Path:
    return FULL_ANSWER_DIR / f"{ticker}.json"


def card_path(ticker: str) -> Path:
    return TICKER_CARD_DIR / f"{ticker}.current.json"


def assembler_section_raw(full_answer: dict[str, Any], assembler_section_id: str | None) -> Any:
    if not assembler_section_id:
        return {}
    section = as_dict(as_dict(full_answer.get("sections")).get(assembler_section_id))
    return section.get("raw") if section else {}


def old_value(section: dict[str, Any], full_answer: dict[str, Any], card: dict[str, Any]) -> Any:
    if section["section_id"] == "identity":
        identity = as_dict(full_answer.get("identity"))
        return {
            "ticker": identity.get("ticker") or card.get("ticker"),
            "instrument_type": card.get("instrument_type"),
            "universe_metadata": card.get("universe_metadata"),
        }
    assembler_value = assembler_section_raw(full_answer, section.get("assembler_section_id"))
    if present(assembler_value):
        return assembler_value
    card_key = section.get("card_key")
    if card_key and card_key in card:
        return card.get(card_key)
    return {}


def source_paths(full_answer: dict[str, Any], card: dict[str, Any], ticker: str) -> list[str]:
    paths = [rel(full_answer_path(ticker)), rel(card_path(ticker))]
    for row in as_list(full_answer.get("source_lineage")):
        path = as_dict(row).get("path")
        if path:
            paths.append(str(path).replace("\\", "/"))
    for row in as_list(card.get("source_artifacts")):
        path = as_dict(row).get("path")
        if path:
            paths.append(str(path).replace("\\", "/"))
    return sorted(set(path for path in paths if path))


def flag_true(value: Any) -> bool:
    return value in {1, True, "1", "true", "True", "yes", "YES"}


def semantic_band_status(value: Any) -> str:
    text = str(value or "").strip().upper().replace(" ", "_").replace("-", "_")
    aliases = {
        "ABOVE_BAND_WAIT": "ABOVE_BAND",
        "ABOVE_BAND_NO_CHASE": "ABOVE_BAND",
        "BELOW_BAND_WAIT": "BELOW_BAND",
        "BELOW_BAND_REPAIR": "BELOW_BAND",
        "IN_BAND_WAIT": "IN_BAND",
        "IN_BAND_REVIEW": "IN_BAND",
    }
    return aliases.get(text, text)


def card_price_band_stop(card: dict[str, Any]) -> dict[str, Any]:
    return as_dict(card.get("price_band_stop"))


def packet_or_card_price_band_stop(packet: dict[str, Any], card: dict[str, Any]) -> dict[str, Any]:
    entry = as_dict(assembler_section_raw(packet, "entry_stop_sizing"))
    wf85_entry = as_dict(entry.get("entry_band"))
    if wf85_entry:
        stop = as_dict(entry.get("stop_or_invalidation"))
        return {
            "entry_band_low": wf85_entry.get("entry_band_low") or wf85_entry.get("low"),
            "entry_band_high": wf85_entry.get("entry_band_high") or wf85_entry.get("high"),
            "stop_or_invalidation": stop.get("level") if stop else entry.get("stop_or_invalidation"),
            "band_status": wf85_entry.get("band_status"),
        }
    return card_price_band_stop(card)


def packet_or_card_effective_price(packet: dict[str, Any], card: dict[str, Any]) -> dict[str, Any]:
    entry = as_dict(assembler_section_raw(packet, "entry_stop_sizing"))
    current_price = as_dict(entry.get("current_price"))
    if current_price.get("latest_known_price") is not None:
        return {
            "effective_price": current_price.get("latest_known_price"),
            "source": current_price.get("source"),
        }
    eff = as_dict(packet.get("effective_price_context"))
    if eff:
        return eff
    pbs = card_price_band_stop(card)
    return {
        "effective_price": pbs.get("latest_known_price"),
        "source": pbs.get("price_source"),
    }


def packet_or_card_action(packet: dict[str, Any], card: dict[str, Any]) -> dict[str, Any]:
    machine = as_dict(packet.get("machine_state"))
    decision = as_dict(assembler_section_raw(packet, "decision_state"))
    entry = as_dict(assembler_section_raw(packet, "entry_stop_sizing"))
    if machine or decision or entry:
        return {
            "band_status": as_dict(entry.get("entry_band")).get("band_status"),
            "deployment_status": machine.get("decision_state") or decision.get("decision_state"),
            "posture": machine.get("primary_state") or decision.get("primary_state"),
        }
    pbs = card_price_band_stop(card)
    support = as_dict(card.get("recommendation_support"))
    contract = as_dict(support.get("deployment_contract"))
    raw_context = as_dict(contract.get("raw_context"))
    return {
        "band_status": support.get("band_status") or raw_context.get("band_status") or pbs.get("band_status"),
        "deployment_status": contract.get("deployment_status"),
        "posture": support.get("posture"),
    }


def packet_or_card_fit(packet: dict[str, Any], card: dict[str, Any]) -> dict[str, Any]:
    fit = as_dict(assembler_section_raw(packet, "portfolio_fit"))
    return fit if fit else as_dict(card.get("portfolio_fit_concentration"))


def best_tier(value: dict[str, Any]) -> Any:
    return (
        value.get("current_route_tier")
        or value.get("wf78_auto_tier")
        or value.get("auto_tier")
        or value.get("research_tier")
        or value.get("tier")
        or value.get("coverage_tier")
        or value.get("wf78_tier")
    )


def wf85_cards_by_ticker() -> dict[str, dict[str, Any]]:
    payload = as_dict(load_json(WF85_CARDS, {}))
    return {
        str(as_dict(card).get("ticker") or "").upper(): as_dict(card)
        for card in as_list(payload.get("cards"))
        if as_dict(card).get("ticker")
    }


def wf84_ticker_universe(db_path: Path) -> list[str]:
    with connect_ro(db_path) as conn:
        return [
            str(row["ticker"]).upper()
            for row in conn.execute("SELECT ticker FROM security_master ORDER BY ticker")
            if row["ticker"]
        ]


def fetch_wf84_context(conn: sqlite3.Connection, ticker: str) -> dict[str, Any]:
    current = conn.execute("SELECT * FROM v_current_decision_overview WHERE ticker=?", (ticker,)).fetchone()
    if not current:
        return {"status": "missing", "ticker": ticker}
    membership = conn.execute("SELECT * FROM universe_membership WHERE ticker=?", (ticker,)).fetchone()
    sections = {
        row["section_id"]: dict(row)
        for row in conn.execute("SELECT * FROM v_full_ticker_answer_context WHERE ticker=? ORDER BY section_id", (ticker,))
    }
    families = [dict(row) for row in conn.execute("SELECT * FROM evidence_family_status WHERE ticker=? ORDER BY family_id", (ticker,))]
    drillback = [dict(row) for row in conn.execute("SELECT * FROM v_ticker_source_drillback WHERE ticker=? ORDER BY source_use", (ticker,))]
    return {
        "status": "ok",
        "current": dict(current),
        "universe_membership": dict(membership) if membership else {},
        "sections": sections,
        "evidence_family_status": families,
        "source_drillback": drillback,
    }


def compare_float(name: str, old_num: Any, new_num: Any, *, tolerance: float = NUMERIC_TOLERANCE, freshness_can_supersede: bool = False) -> dict[str, Any]:
    try:
        old_value_num = None if old_num in (None, "") else float(old_num)
        new_value_num = None if new_num in (None, "") else float(new_num)
    except (TypeError, ValueError):
        return {"name": name, "status": "warning", "old": old_num, "new": new_num, "reason": "non_numeric"}
    if old_value_num is None and new_value_num is None:
        return {"name": name, "status": "ok", "old": old_num, "new": new_num, "reason": "both_missing"}
    if old_value_num is None or new_value_num is None:
        return {"name": name, "status": "critical", "old": old_num, "new": new_num, "reason": "one_missing"}
    delta = abs(old_value_num - new_value_num)
    if delta <= tolerance:
        return {"name": name, "status": "ok", "old": old_value_num, "new": new_value_num, "delta": round(delta, 6)}
    return {
        "name": name,
        "status": "warning" if freshness_can_supersede else "critical",
        "old": old_value_num,
        "new": new_value_num,
        "delta": round(delta, 6),
        "reason": "wf84_may_have_fresher_price_overlay" if freshness_can_supersede else "outside_tolerance",
    }


def norm_tier(value: Any) -> str:
    text = str(value or "").strip()
    if text and not text.lower().startswith("tier"):
        return f"Tier {text}".strip()
    return text


def build_ticker_packet(ticker: str, conn: sqlite3.Connection, wf85_by_ticker: dict[str, dict[str, Any]]) -> dict[str, Any]:
    ticker = ticker.upper()
    full_answer = as_dict(load_json(full_answer_path(ticker), {}))
    card = as_dict(load_json(card_path(ticker), {}))
    wf84 = fetch_wf84_context(conn, ticker)
    wf85 = wf85_by_ticker.get(ticker, {})
    section_results: list[dict[str, Any]] = []
    critical: list[str] = []
    warnings: list[str] = []
    membership = as_dict(wf84.get("universe_membership"))
    requires_answer_packet = flag_true(membership.get("production_answer_path_member"))
    thin_monitor_row = flag_true(membership.get("thin_monitor_row")) and not requires_answer_packet
    parity_scope = "production_full_answer_path" if requires_answer_packet else "thin_monitor_card_wf84_surface"

    if not full_answer and requires_answer_packet:
        critical.append("wf85_full_answer_missing")
    elif not full_answer:
        warnings.append("wf85_full_answer_not_required_for_thin_monitor")
    if not card:
        critical.append("old_ticker_card_missing")
    if wf84.get("status") != "ok":
        critical.append("wf84_context_missing")

    sections = as_dict(wf84.get("sections"))
    for section in FULL_ANSWER_CONTRACT:
        section_id = section["section_id"]
        old = old_value(section, full_answer, card)
        new_row = as_dict(sections.get(section_id))
        new_raw = parse_json_text(new_row.get("raw_json"), {})
        new_source_paths = parse_json_text(new_row.get("source_paths_json"), [])
        old_present = present(old)
        new_present = present(new_raw)
        source_ok = bool(new_source_paths) and new_row.get("source_open_required") in {1, True}
        hash_match = bool(new_row.get("value_hash")) and stable_hash(old) == new_row.get("value_hash")
        if section_id == "identity":
            hash_match = new_present
        status = "ok"
        reason = "mapped"
        if not new_present and old_present:
            status = "critical"
            reason = "old_section_present_but_wf84_wf85_missing"
        elif not source_ok:
            status = "critical"
            reason = "source_open_drillback_missing"
        elif not old_present and not new_present:
            status = "warning"
            reason = "section_explicitly_missing_in_both_routes"
        elif not hash_match and section_id != "identity":
            status = "critical"
            reason = "section_value_hash_mismatch"
        if status == "critical":
            critical.append(f"section:{section_id}:{reason}")
        elif status == "warning":
            warnings.append(f"section:{section_id}:{reason}")
        section_results.append({
            "section_id": section_id,
            "status": status,
            "reason": reason,
            "old_present": old_present,
            "new_present": new_present,
            "source_ok": source_ok,
            "source_kind": new_row.get("source_kind"),
            "source_paths": new_source_paths,
            "hash_match": hash_match,
            "material": section.get("material") is True,
        })

    current = as_dict(wf84.get("current"))
    pbs = packet_or_card_price_band_stop(full_answer, card)
    eff = packet_or_card_effective_price(full_answer, card)
    action = packet_or_card_action(full_answer, card)
    fit = packet_or_card_fit(full_answer, card)
    numeric_checks = [
        compare_float("entry_band_low", pbs.get("entry_band_low"), current.get("entry_band_low")),
        compare_float("entry_band_high", pbs.get("entry_band_high"), current.get("entry_band_high")),
        compare_float("stop_or_invalidation", pbs.get("stop_or_invalidation"), current.get("stop_or_invalidation")),
        compare_float("latest_known_price", eff.get("effective_price"), current.get("latest_known_price"), freshness_can_supersede=True),
    ]
    for check in numeric_checks:
        if check["status"] == "critical":
            if thin_monitor_row:
                check["status"] = "warning"
                check["scope_note"] = "thin_monitor_numeric_context_not_full_answer_retirement_blocking"
                warnings.append(f"monitor_numeric:{check['name']}:{check.get('reason')}")
            else:
                critical.append(f"numeric:{check['name']}:{check.get('reason')}")
        elif check["status"] == "warning":
            warnings.append(f"numeric:{check['name']}:{check.get('reason')}")

    old_band_status = action.get("band_status") or pbs.get("band_status")
    new_band_status = current.get("band_status")
    old_band_semantic = semantic_band_status(old_band_status)
    new_band_semantic = semantic_band_status(new_band_status)
    band_status_ok = not old_band_semantic or old_band_semantic == new_band_semantic
    if band_status_ok and old_band_status and new_band_status and str(old_band_status) != str(new_band_status):
        warnings.append("state:band_status:semantic_match_raw_diff")
    old_tier = best_tier(fit)
    state_checks = [
        {
            "name": "band_status",
            "status": "ok" if band_status_ok else "critical",
            "old": old_band_status,
            "new": new_band_status,
            "old_semantic": old_band_semantic,
            "new_semantic": new_band_semantic,
        },
        {
            "name": "tier",
            "status": "ok" if not old_tier or norm_tier(old_tier) == norm_tier(current.get("auto_tier")) else "critical",
            "old": old_tier,
            "new": current.get("auto_tier"),
        },
        {
            "name": "wf85_decision_card_present",
            "status": "ok" if wf85 else "critical",
            "old": "n/a",
            "new": bool(wf85),
        },
    ]
    for check in state_checks:
        if check["status"] == "critical":
            critical.append(f"state:{check['name']}")

    authority_violations = recursive_forbidden_true({"assembler": full_answer, "card": card, "wf84": wf84, "wf85": wf85, "boundary": AUTHORITY_BOUNDARY})
    if authority_violations:
        critical.append("authority_forbidden_true_flags")

    status = "blocked" if critical else "ok"
    return {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "ticker": ticker,
        "status": status,
        "authority_boundary": AUTHORITY_BOUNDARY,
        "parity_scope": {
            "scope": parity_scope,
            "requires_answer_packet": requires_answer_packet,
            "thin_monitor_row": thin_monitor_row,
            "universe_membership": membership,
        },
        "assembler_snapshot": {
            "full_answer_path": rel(full_answer_path(ticker)),
            "ticker_card_path": rel(card_path(ticker)),
            "source_paths": source_paths(full_answer, card, ticker),
            "generated_at_utc": full_answer.get("generated_at_utc"),
            "schema": full_answer.get("schema"),
            "status": full_answer.get("status"),
        },
        "wf84_wf85_snapshot": {
            "wf84_db": rel(DEFAULT_DB),
            "wf85_cards_path": rel(WF85_CARDS),
            "wf84_current": current,
            "wf85_decision_state": wf85.get("decision_state"),
            "wf85_owner_action_required": wf85.get("owner_action_required"),
            "wf84_section_count": len(sections),
            "source_drillback_count": len(as_list(wf84.get("source_drillback"))),
            "evidence_family_count": len(as_list(wf84.get("evidence_family_status"))),
        },
        "section_results": section_results,
        "numeric_checks": numeric_checks,
        "state_checks": state_checks,
        "authority_violations": authority_violations[:100],
        "validation": {
            "status": status,
            "critical_errors": critical,
            "warnings": warnings,
        },
        "retirement_signal": {
            "legacy_answer_packet_duplicate_candidate_after_assembler_parity": status == "ok" and requires_answer_packet,
            "thin_monitor_not_full_answer_packet_retirement_candidate": thin_monitor_row,
            "ticker_card_remains_evidence_cache": True,
            "source_artifacts_remain_required": True,
            "archive_delete_apply_allowed": False,
        },
    }


def build_rollup(tickers: list[str], db_path: Path, coverage_mode: str) -> dict[str, Any]:
    population_tickers = wf84_ticker_universe(db_path)
    population_set = set(population_tickers)
    evaluated_set = set(tickers)
    full_population_covered = bool(population_set) and evaluated_set == population_set
    wf85_by_ticker = wf85_cards_by_ticker()
    per_ticker: list[dict[str, Any]] = []
    with connect_ro(db_path) as conn:
        for ticker in tickers:
            per_ticker.append(build_ticker_packet(ticker, conn, wf85_by_ticker))
    critical = [
        {"ticker": row["ticker"], "errors": row["validation"]["critical_errors"]}
        for row in per_ticker
        if row["validation"]["critical_errors"]
    ]
    warnings = [
        {"ticker": row["ticker"], "warnings": row["validation"]["warnings"]}
        for row in per_ticker
        if row["validation"]["warnings"]
    ]
    section_total = sum(len(row.get("section_results") or []) for row in per_ticker)
    section_ok = sum(1 for row in per_ticker for item in row.get("section_results", []) if item.get("status") == "ok")
    section_status_counts: dict[str, int] = {}
    section_reason_counts: dict[str, int] = {}
    for row in per_ticker:
        for item in row.get("section_results", []):
            status = str(item.get("status") or "unknown")
            reason = str(item.get("reason") or "unknown")
            section_status_counts[status] = section_status_counts.get(status, 0) + 1
            section_reason_counts[reason] = section_reason_counts.get(reason, 0) + 1
    missing_both_sections = [
        item
        for row in per_ticker
        for item in row.get("section_results", [])
        if item.get("reason") == "section_explicitly_missing_in_both_routes"
    ]
    material_missing_both_sections = [item for item in missing_both_sections if item.get("material") is True]
    technical_posture_missing_both_count = sum(
        1
        for row in per_ticker
        for item in row.get("section_results", [])
        if item.get("section_id") == "technical_posture" and item.get("reason") == "section_explicitly_missing_in_both_routes"
    )
    section_coverage_status = "warning" if material_missing_both_sections else "ok"
    production_answer_path_count = sum(1 for row in per_ticker if as_dict(row.get("parity_scope")).get("requires_answer_packet"))
    thin_monitor_count = sum(1 for row in per_ticker if as_dict(row.get("parity_scope")).get("thin_monitor_row"))
    production_critical = [
        row
        for row in per_ticker
        if as_dict(row.get("parity_scope")).get("requires_answer_packet") and row["validation"]["critical_errors"]
    ]
    thin_monitor_critical = [
        row
        for row in per_ticker
        if as_dict(row.get("parity_scope")).get("thin_monitor_row") and row["validation"]["critical_errors"]
    ]
    ready_for_duplicate_planning = not critical and full_population_covered
    production_answer_packet_retirement_planning_ready = not production_critical and full_population_covered
    if critical:
        duplicate_plan_status = "blocked_on_parity"
    elif not full_population_covered:
        duplicate_plan_status = "blocked_on_population_coverage"
    else:
        duplicate_plan_status = "planning_ready"
    return {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "blocked" if critical else "ok",
        "workflow_ids": ["WF84", "WF85"],
        "purpose": "Full intelligence answer parity proof for migrating rich ticker answers under WF84/WF85 before duplicate surface retirement.",
        "authority_boundary": AUTHORITY_BOUNDARY,
        "full_answer_contract": FULL_ANSWER_CONTRACT,
        "coverage": {
            "mode": coverage_mode,
            "evaluated_ticker_count": len(per_ticker),
            "wf84_population_ticker_count": len(population_tickers),
            "full_population_covered": full_population_covered,
            "population_coverage_ratio": round(len(evaluated_set & population_set) / len(population_set), 4) if population_set else 0,
        },
        "section_coverage_quality": {
            "status": section_coverage_status,
            "meaning": (
                "Parity can be ok while both routes are missing the same material section. "
                "Use this block as completeness evidence separate from parity readiness."
            ),
            "section_status_counts": section_status_counts,
            "section_reason_counts": section_reason_counts,
            "missing_both_count": len(missing_both_sections),
            "material_missing_both_count": len(material_missing_both_sections),
            "technical_posture_missing_both_count": technical_posture_missing_both_count,
        },
        "evaluated_tickers": tickers,
        "pilot_tickers": PILOT_TICKERS,
        "summary": {
            "ticker_count": len(per_ticker),
            "ticker_pass_count": sum(1 for row in per_ticker if row.get("status") == "ok"),
            "critical_ticker_count": len(critical),
            "warning_ticker_count": len(warnings),
            "section_count": section_total,
            "section_ok_count": section_ok,
            "section_ok_ratio": round(section_ok / section_total, 4) if section_total else 0,
            "section_status_counts": section_status_counts,
            "section_reason_counts": section_reason_counts,
            "section_coverage_status": section_coverage_status,
            "section_missing_both_count": len(missing_both_sections),
            "material_section_missing_both_count": len(material_missing_both_sections),
            "technical_posture_missing_both_count": technical_posture_missing_both_count,
            "wf84_population_ticker_count": len(population_tickers),
            "full_population_covered": full_population_covered,
            "production_answer_path_count": production_answer_path_count,
            "thin_monitor_count": thin_monitor_count,
            "production_critical_ticker_count": len(production_critical),
            "thin_monitor_critical_ticker_count": len(thin_monitor_critical),
            "production_answer_packet_retirement_planning_ready": production_answer_packet_retirement_planning_ready,
            "ready_to_start_duplicate_surface_retirement_planning": ready_for_duplicate_planning,
            "archive_delete_apply_allowed": False,
        },
        "phases_implemented": [
            {"phase": 1, "name": "full_answer_contract", "status": "implemented"},
            {"phase": 2, "name": "old_stack_extraction", "status": "implemented"},
            {"phase": 3, "name": "wf84_evidence_mapping", "status": "implemented_via_full_answer_section_context"},
            {"phase": 4, "name": "wf84_wf85_answer_assembly", "status": "implemented"},
            {"phase": 5, "name": "parity_harness", "status": "implemented"},
            {"phase": 6, "name": "consumer_parity_gate", "status": "implemented_for_validator_and_ready_for_consumer_wiring"},
            {"phase": 7, "name": "repair_targeting_inputs", "status": "implemented_via_section_level_failures"},
            {"phase": 8, "name": "retirement_readiness_v2_inputs", "status": "implemented_as_planning_signal_no_apply"},
        ],
        "duplicate_surface_retirement_plan": {
            "status": duplicate_plan_status,
            "recommended_decision_now": "resolve parity blockers and run full-population proof before any duplicate-surface archive packet",
            "scope_note": (
                "Production answer-path tickers require old answer-packet parity. Thin monitor rows are card/WF84 "
                "monitor surfaces and are not full-answer packet retirement candidates."
            ),
            "production_answer_packet_retirement_planning_ready": production_answer_packet_retirement_planning_ready,
            "full_rich_surface_retirement_planning_ready": ready_for_duplicate_planning,
            "candidate_surface_classes": [
                "duplicate generated ticker-answer packets after broad parity and consumer migration",
                "obsolete generated sidecars with no unique source lineage after DB lifecycle approval",
            ],
            "retain_surface_classes": [
                "owner notes",
                "source-open evidence roots",
                "ticker intelligence cards until WF84/WF85 full-answer consumers prove broader live history",
                "WF78 feeders until active reference and lifecycle gates clear",
            ],
            "archive_delete_apply_allowed": False,
        },
        "per_ticker": [
            {
                "ticker": row["ticker"],
                "status": row["status"],
                "parity_scope": as_dict(row.get("parity_scope")).get("scope"),
                "critical_errors": row["validation"]["critical_errors"],
                "warnings": row["validation"]["warnings"],
                "artifact": f"tmp/full-answer-parity/{row['ticker']}.json",
            }
            for row in per_ticker
        ],
        "critical_errors": critical,
        "warnings": warnings,
        "validation": {
            "status": "blocked" if critical else "ok",
            "critical_errors": critical,
            "warnings": warnings,
        },
        "stop_lines": [
            "No archive/delete/apply authority.",
            "No canon/portfolio/cash/sizing/risk-rule mutation.",
            "No capital deployment, paper/live order, brokerage/account action, money movement, or owner approval inference.",
            "Source artifacts remain required until broad value-level parity and DB lifecycle approval clear.",
        ],
        "_per_ticker_full": per_ticker,
    }


def parse_tickers(value: str | None) -> list[str]:
    if not value:
        return PILOT_TICKERS
    return [item.strip().upper() for item in value.split(",") if item.strip()]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tickers", help="Comma-separated ticker list. Defaults to pilot set.")
    parser.add_argument("--pilot", action="store_true", help="Use the default pilot set.")
    parser.add_argument("--all", action="store_true", help="Evaluate every ticker currently present in WF84 security_master.")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--pretty", action="store_true")
    parser.add_argument("--out", type=Path, default=DEFAULT_ROLLUP)
    parser.add_argument("--out-dir", type=Path, default=OUT_DIR)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    args = parser.parse_args()

    if args.all and (args.pilot or args.tickers):
        parser.error("--all cannot be combined with --pilot or --tickers")
    if args.all:
        tickers = wf84_ticker_universe(args.db)
        coverage_mode = "all_wf84_population"
    elif args.tickers:
        tickers = parse_tickers(args.tickers)
        coverage_mode = "custom"
    else:
        tickers = PILOT_TICKERS
        coverage_mode = "pilot"
    rollup = build_rollup(tickers, args.db, coverage_mode)
    per_ticker_full = rollup.pop("_per_ticker_full")
    if args.write:
        args.out_dir.mkdir(parents=True, exist_ok=True)
        for row in per_ticker_full:
            atomic_write_json(args.out_dir / f"{row['ticker']}.json", row)
        atomic_write_json(args.out, rollup)
    print(json.dumps({
        "status": rollup["status"],
        "out": rel(args.out),
        "summary": rollup["summary"],
        "validation": rollup["validation"],
    }, indent=2 if args.pretty else None, sort_keys=True))
    if args.validate and rollup["status"] == "blocked":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
