#!/usr/bin/env python3
"""Build WF85 review-only decision-card proof artifacts.

WF85 consumes WF84's derived JSON/SQLite data plane and emits fail-closed
decision cards plus separate gates for source/freshness, authority vocabulary,
approval-card draft eligibility, and risk/sizing context. The artifacts are
review/proof surfaces only. They do not approve capital, execution, account,
canon, portfolio, cash, sizing, risk-rule, customer, or external actions.
"""
from __future__ import annotations

import argparse
import json
import re
import sqlite3
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from finance_decision_state_compiler import (
    APPROVAL_DRAFT_BAND_STATUS,
    NO_CHASE_BAND_STATES,
    PROMOTE_VERDICT as PROMOTION_REVIEW_VERDICT,
    REVIEW_READY_PRIMARY_STATES,
    classify_decision_state,
    flag_true,
    thin_monitor_scope,
)
from finance_sql_canon_access import FinanceSqlCanonAccess, p0_registry_lane_status
from market_data_utils import atomic_write_json, load_json_artifact
from trade_grade_decision_os_contract import (
    AUTHORITY_BOUNDARY,
    EXPECTED_APPROVAL_DRAFT_COUNT_BEFORE_FRESHNESS_REPAIR,
    MAX_PAPER_GUARD_CONTEXT_AGE_DAYS,
    REQUIRED_FALSE_KEYS,
    age_days,
)

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"

DEFAULT_CARDS_OUT = TMP / "trade-grade-decision-cards.json"
DEFAULT_SOURCE_GATE_OUT = TMP / "trade-grade-source-freshness-gate.json"
DEFAULT_AUTHORITY_OUT = TMP / "trade-grade-decision-card-authority-validation.json"
DEFAULT_APPROVAL_GATE_OUT = TMP / "trade-grade-approval-card-gate.json"
DEFAULT_RISK_OUT = TMP / "trade-grade-risk-sizing-overlay.json"

WF84_PACKET = TMP / "canonical-finance-data-plane.json"
WF84_DB = TMP / "canonical-finance-data-plane.sqlite"
WF85_CONTRACT = TMP / "trade-grade-decision-os-contract.json"
WF67_GUARD = TMP / "alpaca-paper-readiness" / "paper-execution-guard-validation.json"
CURRENT_ANALOG_MATCH = TMP / "current-regime-analog-match.json"

SCHEMA = "veritas.trade_grade_decision_cards.v1"
SOURCE_GATE_SCHEMA = "veritas.trade_grade_source_freshness_gate.v1"
AUTHORITY_SCHEMA = "veritas.trade_grade_decision_card_authority_validation.v1"
APPROVAL_GATE_SCHEMA = "veritas.trade_grade_approval_card_gate.v1"
RISK_SCHEMA = "veritas.trade_grade_risk_sizing_overlay.v1"
WORKFLOW_ID = "WF85"
LEGACY_PRODUCTION_COMPATIBILITY_COUNT = 42

SOURCE_OK = {"ok", "fresh", "current"}
SOURCE_WARNING_OK_PATHS = {"tmp/post-close-final-quote-ledger.json"}
SOURCE_ARTIFACT_STATUS_ONLY_OK_PATHS = {"tmp/technical-refresh.json"}
NON_EXECUTION_TECHNICAL_PRICE_FRESHNESS = "current_price_technical_available_for_non_executing_review"
QUOTE_FRESH_OK = {
    "fresh",
    "ok",
    "intraday_fresh",
    "post_close_final_quote_available_for_non_executing_review",
    NON_EXECUTION_TECHNICAL_PRICE_FRESHNESS,
}
APPROVAL_DRAFT_QUOTE_FRESH_OK = {"fresh", "ok", "intraday_fresh"}

# Families that only make sense for equity operating companies; ETFs, bond/rate
# proxies, and commodity proxies should not be collection-blocked by their absence.
EQUITY_ONLY_FAMILIES = {
    "analyst_consensus",
    "analyst_price_targets",
    "analyst_ratings",
    "catalyst_earnings_state",
}

NON_EQUITY_INSTRUMENT_TYPES = {
    "etf",
    "bond_or_rate_proxy",
    "commodity_proxy",
}

def is_non_equity_instrument(instrument_type: str | None) -> bool:
    return bool(instrument_type and str(instrument_type).lower() in NON_EQUITY_INSTRUMENT_TYPES)


FORBIDDEN_ACTION_PHRASES = (
    "approved to buy",
    "approved to sell",
    "buy approved",
    "sell approved",
    "trade approved",
    "paper order approved",
    "live trade",
    "execute order",
    "submit order",
    "place trade",
    "order submitted",
    "order placed",
)

NOT_APPROVED_STAMP = "NOT APPROVED - Randall exact approval required"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def load_json(path: Path) -> dict[str, Any]:
    payload = load_json_artifact(path)
    return payload if isinstance(payload, dict) else {}


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def connect_ro(db_path: Path = WF84_DB) -> sqlite3.Connection:
    uri = db_path.resolve().as_uri() + "?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


def parse_json_text(value: Any, default: Any) -> Any:
    if not isinstance(value, str) or not value:
        return default
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return default


def sqlite_probe() -> dict[str, Any]:
    if not WF84_DB.exists():
        return {"status": "blocked", "exists": False, "reason": "wf84_sqlite_missing"}
    try:
        with connect_ro() as conn:
            integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
            schema_row = conn.execute(
                "SELECT generated_at_utc, status, validation_status FROM schema_run ORDER BY generated_at_utc DESC LIMIT 1"
            ).fetchone()
            forbidden = conn.execute("SELECT * FROM v_authority_boundary_false").fetchone()
            return {
                "status": "ok" if integrity == "ok" and schema_row and not any(dict(forbidden).values()) else "blocked",
                "exists": True,
                "integrity_check": integrity,
                "generated_at_utc": schema_row["generated_at_utc"] if schema_row else None,
                "wf84_status": schema_row["status"] if schema_row else None,
                "wf84_validation_status": schema_row["validation_status"] if schema_row else None,
                "authority_view": dict(forbidden) if forbidden else {},
            }
    except sqlite3.Error as exc:
        return {"status": "blocked", "exists": WF84_DB.exists(), "reason": f"sqlite_error:{exc}"}


def wf84_parity_probe(wf84_packet: dict[str, Any], db_probe: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": "ok"
        if db_probe.get("status") == "ok" and wf84_packet.get("generated_at_utc") == db_probe.get("generated_at_utc")
        else "blocked",
        "wf84_packet_generated_at_utc": wf84_packet.get("generated_at_utc"),
        "wf84_sqlite_generated_at_utc": db_probe.get("generated_at_utc"),
        "wf84_packet_status": wf84_packet.get("status"),
        "wf84_sqlite_status": db_probe.get("wf84_status"),
        "wf84_sqlite_validation_status": db_probe.get("wf84_validation_status"),
    }


def sql_canon_scope_context(cards: list[dict[str, Any]]) -> dict[str, Any]:
    client = FinanceSqlCanonAccess()
    validation = client.validate()
    critical: list[str] = []
    warnings: list[str] = []
    registry: dict[str, Any] = {}
    production_tickers: list[str] = []
    legacy_production_tickers: list[str] = []
    wf84_production = sorted(
        str(card.get("ticker") or "").upper()
        for card in cards
        if as_dict(card.get("wf84_scope")).get("production_answer_path_member") is True
    )
    if validation.get("status") != "ok":
        critical.append("sql_canon_access_validation_blocked")
    else:
        production_tickers = client.production_answer_tickers()
        legacy_production_tickers = client.legacy_production_answer_tickers()
        registry = client.migration_registry_summary()
        production_set = set(production_tickers)
        wf84_set = set(wf84_production)
        if not production_tickers:
            warnings.append("production_grade_set_empty_wait_for_decision_grade_gates")
        if len(legacy_production_tickers) != LEGACY_PRODUCTION_COMPATIBILITY_COUNT:
            warnings.append("sql_canon_legacy_42_compatibility_count_mismatch_advisory")
        if production_set != wf84_set:
            warnings.append("legacy_wf84_answer_path_differs_from_strategic_sql_first_scope")
        p0_status = p0_registry_lane_status(registry)
        if not p0_status["ok"]:
            critical.extend(p0_status["errors"])
    status = "blocked" if critical else "ok"
    return {
        "status": status,
        "access_validation_status": validation.get("status"),
        "registry_summary": registry,
        "p0_registry_lane_status": p0_registry_lane_status(registry),
        "wf84_production_answer_tickers": wf84_production,
        "sql_canon_production_answer_tickers": production_tickers,
        "sql_canon_production_answer_count": len(production_tickers),
        "sql_canon_production_answer_definition": "validated proof-joined production-grade set",
        "legacy_42_retired_from_blocking": True,
        "legacy_42_count_advisory_only": True,
        "effective_production_answer_count": len(production_tickers),
        "effective_production_answer_definition": "validated proof-joined production-grade set; empty means wait for decision-grade gates",
        "sql_canon_legacy_production_answer_tickers": legacy_production_tickers,
        "sql_canon_legacy_production_answer_count": len(legacy_production_tickers),
        "sql_canon_legacy_production_answer_definition": "retired legacy 42 compatibility answer scope",
        "production_scope_diff": {
            "missing_from_sql": sorted(set(wf84_production) - set(production_tickers)),
            "extra_in_sql": sorted(set(production_tickers) - set(wf84_production)),
            "legacy_wf84_scope_retired_from_blocking": True,
        },
        "validation": {"status": status, "critical_errors": critical, "warnings": warnings},
        "authority_boundary": {
            "sql_canon_scope_validation_only": True,
            "consumer_cutover_allowed_by_this_packet": False,
            "capital_deployment_allowed": False,
            "paper_or_live_execution_allowed": False,
            "brokerage_or_account_action_allowed": False,
            "owner_approval_inferred": False,
        },
    }


def rows_by_ticker(conn: sqlite3.Connection, sql: str) -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    for row in conn.execute(sql):
        data = dict(row)
        ticker = str(data.get("ticker") or "").upper()
        if ticker:
            rows[ticker] = data
    return rows


def list_by_ticker(conn: sqlite3.Connection, sql: str) -> dict[str, list[dict[str, Any]]]:
    rows: dict[str, list[dict[str, Any]]] = {}
    for row in conn.execute(sql):
        data = dict(row)
        ticker = str(data.get("ticker") or "").upper()
        if ticker:
            rows.setdefault(ticker, []).append(data)
    return rows


def source_status_for(
    ticker: str,
    source_rows: list[dict[str, Any]],
    family_rows: list[dict[str, Any]],
    membership: dict[str, Any],
    current: dict[str, Any] | None = None,
) -> dict[str, Any]:
    accepted_warning_sources: list[dict[str, Any]] = []
    accepted_status_only_sources: list[dict[str, Any]] = []

    def source_row_ok(row: dict[str, Any]) -> bool:
        status = row.get("status")
        validation_status = row.get("validation_status")
        if status in SOURCE_OK and validation_status in SOURCE_OK:
            return True
        source_path_text = str(row.get("path") or "").replace("\\", "/").lstrip("./")
        if (
            status in SOURCE_OK
            and validation_status in (None, "", "unknown")
            and source_path_text in SOURCE_ARTIFACT_STATUS_ONLY_OK_PATHS
        ):
            source_path = ROOT / source_path_text
            source_payload = load_json(source_path)
            records = as_list(source_payload.get("records"))
            matching_record = next(
                (
                    item
                    for item in records
                    if isinstance(item, dict)
                    and str(item.get("ticker") or "").upper() == ticker.upper()
                    and item.get("close") is not None
                    and item.get("data_date")
                ),
                None,
            )
            if source_payload.get("status") == "ok" and matching_record:
                accepted_status_only_sources.append({
                    "source_use": row.get("source_use"),
                    "path": row.get("path"),
                    "status": status,
                    "validation_status": validation_status,
                    "acceptance": "artifact_status_ok_accepted_for_non_executing_review_ticker_row",
                    "ticker_row_present": True,
                    "data_date": matching_record.get("data_date"),
                })
                return True
        if status == "warning" and validation_status in SOURCE_OK and source_path_text in SOURCE_WARNING_OK_PATHS:
            source_path = ROOT / source_path_text
            source_payload = load_json(source_path)
            summary = as_dict(source_payload.get("summary"))
            validation = as_dict(source_payload.get("validation"))
            target_count = int(summary.get("target_count") or 0)
            ok_count = int(summary.get("ok_count") or 0)
            error_count = int(summary.get("error_count") or 0)
            cached_overlay_count = int(summary.get("cached_overlay_count") or 0)
            ok_tickers = {str(item).upper() for item in as_list(summary.get("ok_tickers"))}
            all_cached_overlay = cached_overlay_count == target_count
            ticker_ok = ticker.upper() in ok_tickers
            warning_ok = (
                source_payload.get("status") == "warning"
                and validation.get("status") == "ok"
                and target_count > 0
                and ok_count == target_count
                and error_count == 0
                and (all_cached_overlay or ticker_ok)
            )
            if warning_ok:
                accepted_warning_sources.append({
                    "source_use": row.get("source_use"),
                    "path": row.get("path"),
                    "status": status,
                    "validation_status": validation_status,
                    "acceptance": (
                        "warning_accepted_for_non_executing_review_cached_overlay"
                        if all_cached_overlay
                        else "warning_accepted_for_non_executing_review_ticker_ok"
                    ),
                    "target_count": target_count,
                    "ok_count": ok_count,
                    "cached_overlay_count": cached_overlay_count,
                    "ticker_in_ok_tickers": ticker_ok,
                })
                return True
        return False

    non_ok_sources = [
        {
            "source_use": row.get("source_use"),
            "path": row.get("path"),
            "status": row.get("status"),
            "validation_status": row.get("validation_status"),
        }
        for row in source_rows
        if not source_row_ok(row)
    ]
    non_equity = is_non_equity_instrument(current.get("instrument_type") if current else None)
    exempted_families: list[str] = []
    missing_or_stale_families = []
    for row in family_rows:
        if int(row.get("source_required") or 0) != 1:
            continue
        if (int(row.get("missing_count") or 0) <= 0 and int(row.get("stale_count") or 0) <= 0):
            continue
        family_id = str(row.get("family_id") or "")
        if non_equity and family_id in EQUITY_ONLY_FAMILIES:
            exempted_families.append(family_id)
            continue
        missing_or_stale_families.append({
            "family_id": row.get("family_id"),
            "status": row.get("status"),
            "missing_count": row.get("missing_count"),
            "stale_count": row.get("stale_count"),
            "resolution_state": row.get("resolution_state"),
            "source_paths": parse_json_text(row.get("source_paths_json"), []),
        })
    is_thin_monitor = thin_monitor_scope(membership)
    source_open_status = "blocked" if non_ok_sources or not source_rows else "verified"
    if is_thin_monitor and source_open_status == "blocked":
        source_open_status = "scoped_thin_monitor_not_required"
    result: dict[str, Any] = {
        "ticker": ticker,
        "source_open_status": source_open_status,
        "scope": "thin_monitor_card_wf84_surface" if is_thin_monitor else "production_or_decision_surface",
        "source_drillback_count": len(source_rows),
        "non_ok_sources": non_ok_sources,
        "accepted_warning_sources": accepted_warning_sources,
        "accepted_status_only_sources": accepted_status_only_sources,
        "missing_or_stale_families": missing_or_stale_families,
        "material_claim_guard": "source_open_required_before_material_finance_claims",
        "approval_execution_freshness_guard": "accepted warning/status-only sources are review-only and do not satisfy execution freshness or owner approval",
    }
    if current is not None:
        result["instrument_type"] = current.get("instrument_type")
    if exempted_families:
        result["exempted_equity_only_families"] = exempted_families
        result["non_equity_exemption_applied"] = True
    return result


def freshness_status_for(
    current: dict[str, Any],
    price: dict[str, Any],
    source_gate: dict[str, Any],
    membership: dict[str, Any],
) -> dict[str, Any]:
    quote_status = current.get("quote_freshness_status") or price.get("quote_freshness_status")
    fresh_quote_required = bool(price.get("fresh_quote_required"))
    is_fresh = quote_status in QUOTE_FRESH_OK and not source_gate.get("missing_or_stale_families")
    is_thin_monitor = thin_monitor_scope(membership)
    status = "fresh" if is_fresh else "blocked"
    blockers = []
    if not is_fresh:
        blockers = [
            item
            for item in (
                "quote_not_explicitly_fresh" if quote_status not in QUOTE_FRESH_OK else None,
                "missing_or_stale_evidence_family" if source_gate.get("missing_or_stale_families") else None,
            )
            if item
        ]
    if is_thin_monitor and status == "blocked":
        status = "scoped_thin_monitor_not_required"
        blockers = ["thin_monitor_not_decision_grade_full_freshness_not_required"]
    return {
        "ticker": current.get("ticker"),
        "status": status,
        "scope": "thin_monitor_card_wf84_surface" if is_thin_monitor else "production_or_decision_surface",
        "quote_freshness_status": quote_status,
        "fresh_quote_required": fresh_quote_required,
        "market_date": price.get("market_date"),
        "quote_time_utc": price.get("quote_time_utc"),
        "blockers": blockers,
    }


def source_drillback_public(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "source_use": row.get("source_use"),
            "artifact_id": row.get("artifact_id"),
            "path": row.get("path"),
            "role": row.get("role"),
            "status": row.get("status"),
            "validation_status": row.get("validation_status"),
            "sha256": row.get("sha256"),
        }
        for row in rows
    ]


def scenario_context_public(analog_match: dict[str, Any]) -> dict[str, Any]:
    panel = analog_match.get("scenario_context_panel") if isinstance(analog_match.get("scenario_context_panel"), dict) else {}
    primary = [row for row in (panel.get("primary_analogs") or []) if isinstance(row, dict)]
    stress = [row for row in (panel.get("stress_caution_analogs") or []) if isinstance(row, dict)]
    return {
        "status": analog_match.get("status") or "unavailable",
        "source_artifact": rel(CURRENT_ANALOG_MATCH),
        "generated_at_utc": analog_match.get("generated_at_utc"),
        "active_current_tags": panel.get("active_current_tags") or [],
        "primary_analogs": [
            {
                "event_id": row.get("event_id"),
                "label": row.get("label"),
                "fit": row.get("fit"),
                "scenario_interpretation": row.get("scenario_interpretation"),
            }
            for row in primary[:4]
        ],
        "stress_caution_analogs": [
            {
                "event_id": row.get("event_id"),
                "label": row.get("label"),
                "fit": row.get("fit"),
                "scenario_interpretation": row.get("scenario_interpretation"),
            }
            for row in stress[:3]
        ],
        "authority": {
            "scenario_context_only": True,
            "probability_or_score_allowed": False,
            "deployment_ranking_allowed": False,
            "capital_action_allowed": False,
            "paper_or_live_execution_allowed": False,
            "owner_approval_inference_allowed": False,
        },
    }


def evidence_family_public(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "family_id": row.get("family_id"),
            "status": row.get("status"),
            "missing_count": row.get("missing_count"),
            "stale_count": row.get("stale_count"),
            "resolution_state": row.get("resolution_state"),
            "tier_weighted_resolved": bool(row.get("tier_weighted_resolved")),
            "source_paths": parse_json_text(row.get("source_paths_json"), []),
        }
        for row in rows
    ]


def build_card(
    current: dict[str, Any],
    price: dict[str, Any],
    entry: dict[str, Any],
    source_rows: list[dict[str, Any]],
    family_rows: list[dict[str, Any]],
    membership: dict[str, Any],
    scenario_context: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    ticker = current["ticker"]
    source_gate = source_status_for(ticker, source_rows, family_rows, membership, current)
    freshness = freshness_status_for(current, price, source_gate, membership)
    decision_state, blockers = classify_decision_state(current, source_gate, freshness, membership)
    current_price = current.get("latest_known_price")
    card = {
        "ticker": ticker,
        "name": current.get("name"),
        "auto_tier": current.get("auto_tier"),
        "auto_state": current.get("auto_state"),
        "primary_state": current.get("primary_state"),
        "queue_state": current.get("queue_state"),
        "decision_state": decision_state,
        "decision_state_reason": blockers,
        "promotion_gate": {
            "verdict": current.get("gate_verdict"),
            "vetoes": parse_json_text(current.get("gate_vetoes_json"), []),
            "owner_review_ready_when_gates_clear": current.get("gate_verdict") == PROMOTION_REVIEW_VERDICT,
        },
        "wf84_scope": {
            "universe_scope": membership.get("universe_scope"),
            "production_answer_path_member": flag_true(membership.get("production_answer_path_member")),
            "thin_monitor_row": flag_true(membership.get("thin_monitor_row")),
            "decision_grade_eligible": flag_true(membership.get("decision_grade_eligible")),
            "classification": "thin_monitor_card_wf84_surface" if thin_monitor_scope(membership) else "production_or_decision_surface",
        },
        "thesis_snapshot": {
            "status": "requires_source_open_before_material_claims",
            "summary": "WF85 has not promoted a narrative thesis from source-open evidence in this Phase 1 card.",
        },
        "current_price": {
            "latest_known_price": current_price,
            "market_date": price.get("market_date"),
            "quote_time_utc": price.get("quote_time_utc"),
            "source": price.get("price_source"),
            "quote_freshness_status": freshness.get("quote_freshness_status"),
        },
        "entry_band": {
            "low": current.get("entry_band_low"),
            "high": current.get("entry_band_high"),
            "band_status": current.get("band_status"),
            "source_path": entry.get("source_artifact_path"),
            "source_timestamp": entry.get("source_timestamp"),
            "validation_status": entry.get("validation_status"),
        },
        "stop_or_invalidation": {
            "level": current.get("stop_or_invalidation"),
            "source_path": entry.get("source_artifact_path"),
            "source_timestamp": entry.get("source_timestamp"),
        },
        "source_freshness": freshness,
        "source_drillback": source_drillback_public(source_rows),
        "evidence_family_status": evidence_family_public(family_rows),
        "base_case": "Not generated in Phase 1 until source-open material claims are promoted.",
        "bull_case": "Not generated in Phase 1 until source-open material claims are promoted.",
        "bear_case": "Not generated in Phase 1 until source-open material claims are promoted.",
        "key_risks": [
            "Generated card is review-only.",
            "Primary-state blockers override optimistic routing state.",
            "Material claims require source-open drillback before use.",
        ],
        "counterargument": "If source freshness, band/stop, or invalidation state is stale or blocked, this card cannot support an approval draft.",
        "scenario_context": scenario_context or scenario_context_public({}),
        "sizing_staggering_recommendation": {
            "status": "recommendation_only",
            "recommendation": "No capital or sizing action. Use only for review queue triage until all gates pass and Randall gives exact approval.",
        },
        "owner_action_required": bool(current.get("owner_action_required")),
        "not_approved_stamp": NOT_APPROVED_STAMP,
        "authority_boundary": AUTHORITY_BOUNDARY,
    }
    source_gate["decision_state"] = decision_state
    source_gate["freshness_status"] = freshness.get("status")
    return card, source_gate, freshness


def build_risk_overlay(cards: list[dict[str, Any]]) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for card in cards:
        state = card.get("decision_state")
        band_status = card.get("entry_band", {}).get("band_status")
        if state == "below_stop_or_invalidation":
            posture = "do_not_touch_invalidation_review"
        elif state == "no_chase" or band_status in NO_CHASE_BAND_STATES:
            posture = "wait_no_chase"
        elif state == "review_ready":
            posture = "review_candidate_only"
        elif state == "blocked_missing_freshness":
            posture = "refresh_first"
        else:
            posture = "monitor_or_repair_first"
        rows.append({
            "ticker": card.get("ticker"),
            "decision_state": state,
            "risk_posture": posture,
            "band_status": band_status,
            "sizing_staggering": "recommendation_only_no_cash_or_portfolio_mutation",
            "next_safe_action": {
                "do_not_touch_invalidation_review": "Review invalidation/stop breach; no add proposal.",
                "wait_no_chase": "Wait for a better entry or refreshed band review.",
                "review_candidate_only": "Prepare human review only; capital and execution remain owner-gated.",
                "refresh_first": "Refresh source/quote/card path before any decision-card promotion.",
                "monitor_or_repair_first": "Repair evidence or keep monitor-only.",
            }[posture],
            "authority_boundary": {
                "capital_deployment_approved": False,
                "trade_or_execution_approved": False,
                "portfolio_or_cash_mutation_allowed": False,
                "owner_approval_inferred": False,
            },
        })
    counts = Counter(row["risk_posture"] for row in rows)
    return {
        "schema": RISK_SCHEMA,
        "generated_at_utc": utc_now(),
        "workflow_id": WORKFLOW_ID,
        "status": "ok",
        "summary": {"risk_posture_counts": dict(counts), "row_count": len(rows)},
        "rows": rows,
        "authority_boundary": {
            "review_only": True,
            "sizing_staggering_recommendation_only": True,
            "capital_deployment_approved": False,
            "trade_or_execution_approved": False,
            "portfolio_or_cash_mutation_allowed": False,
            "owner_approval_inferred": False,
        },
    }


def recursive_false_violations(value: Any, path: str = "$") -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}.{key}"
            if key in REQUIRED_FALSE_KEYS and child is not False:
                found.append({"path": child_path, "key": key, "value": child})
            found.extend(recursive_false_violations(child, child_path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            found.extend(recursive_false_violations(child, f"{path}[{index}]"))
    return found


def text_paths(value: Any, path: str = "$") -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = []
    if isinstance(value, dict):
        for key, child in value.items():
            rows.extend(text_paths(child, f"{path}.{key}"))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            rows.extend(text_paths(child, f"{path}[{index}]"))
    elif isinstance(value, str):
        rows.append((path, value))
    return rows


def authority_validation(cards_payload: dict[str, Any], approval_gate: dict[str, Any], risk_overlay: dict[str, Any]) -> dict[str, Any]:
    scan_target = {
        "decision_cards": cards_payload,
        "approval_gate": approval_gate,
        "risk_overlay": risk_overlay,
    }
    false_violations = recursive_false_violations(scan_target)
    phrase_hits: list[dict[str, Any]] = []
    for path, text in text_paths(scan_target):
        lower = text.lower()
        if text == NOT_APPROVED_STAMP:
            continue
        for phrase in FORBIDDEN_ACTION_PHRASES:
            if re.search(rf"\b{re.escape(phrase)}\b", lower):
                phrase_hits.append({"path": path, "phrase": phrase, "text": text[:220]})
    errors: list[str] = []
    if false_violations:
        errors.append("required_false_authority_key_not_false")
    if phrase_hits:
        errors.append("forbidden_action_vocabulary_present")
    return {
        "schema": AUTHORITY_SCHEMA,
        "generated_at_utc": utc_now(),
        "workflow_id": WORKFLOW_ID,
        "status": "ok" if not errors else "blocked",
        "summary": {
            "scanned_card_count": len(cards_payload.get("cards", [])),
            "false_authority_violation_count": len(false_violations),
            "forbidden_action_phrase_count": len(phrase_hits),
        },
        "false_authority_violations": false_violations[:100],
        "forbidden_action_phrase_hits": phrase_hits[:100],
        "validation": {"status": "ok" if not errors else "blocked", "errors": errors, "warnings": []},
    }


def card_band_status(card: dict[str, Any]) -> Any:
    entry_band = card.get("entry_band")
    if isinstance(entry_band, dict):
        return entry_band.get("band_status")
    return None


def card_quote_freshness_status(card: dict[str, Any]) -> str | None:
    source_freshness = card.get("source_freshness")
    if isinstance(source_freshness, dict):
        status = source_freshness.get("quote_freshness_status")
        return str(status) if status is not None else None
    return None


def build_approval_gate(
    cards: list[dict[str, Any]],
    contract: dict[str, Any],
    paper_guard: dict[str, Any] | None = None,
) -> dict[str, Any]:
    paper_guard = paper_guard if isinstance(paper_guard, dict) else load_json(WF67_GUARD)
    paper_guard_age = age_days(paper_guard.get("generated_at_utc"))
    paper_guard_status = paper_guard.get("status")
    paper_guard_ready = paper_guard.get("ready_for_paper_submit_cancel")
    paper_guard_clean = paper_guard_status == "ok" and paper_guard_ready is True
    paper_guard_fresh = (
        isinstance(paper_guard_age, (int, float))
        and paper_guard_age <= MAX_PAPER_GUARD_CONTEXT_AGE_DAYS
        and paper_guard_clean
    )
    eligible = [card for card in cards if card.get("decision_state") == "review_ready"]
    band_eligible = [
        card
        for card in eligible
        if card_band_status(card) == APPROVAL_DRAFT_BAND_STATUS
    ]
    draft_candidates: list[dict[str, Any]] = []
    blocked: list[dict[str, Any]] = []
    for card in cards:
        if card.get("decision_state") != "review_ready":
            blocked.append({
                "ticker": card.get("ticker"),
                "decision_state": card.get("decision_state"),
                "reason": card.get("decision_state_reason"),
            })
            continue
        band_status = card_band_status(card)
        if band_status != APPROVAL_DRAFT_BAND_STATUS:
            blocked.append({
                "ticker": card.get("ticker"),
                "decision_state": "blocked_not_in_band_for_approval_card",
                "reason": [f"band_status={band_status}", "approval_card_draft_requires_IN_BAND"],
            })
            continue
        quote_status = card_quote_freshness_status(card)
        if quote_status not in APPROVAL_DRAFT_QUOTE_FRESH_OK:
            blocked.append({
                "ticker": card.get("ticker"),
                "decision_state": "blocked_non_executing_quote_for_approval_card",
                "reason": [f"quote_freshness_status={quote_status}", "approval_card_draft_requires_execution_fresh_quote_context"],
            })
            continue
        if not paper_guard_fresh:
            blocked.append({
                "ticker": card.get("ticker"),
                "decision_state": "blocked_wf67_guard_context",
                "reason": ["wf67_paper_guard_context_stale_missing_or_blocked"],
            })
            continue
        draft_candidates.append({
            "ticker": card.get("ticker"),
            "draft_state": "approval_card_draft",
            "not_approved_stamp": NOT_APPROVED_STAMP,
            "required_owner_step": "Randall exact scoped approval would still be required before any WF67 paper request path.",
            "authority_boundary": AUTHORITY_BOUNDARY,
        })
    warnings: list[str] = []
    if draft_candidates and contract.get("phase1_prerequisite_gates", {}).get("expected_fail_closed_posture"):
        warnings.append("approval_draft_candidates_present_verify_freshness_repair_completed")
    return {
        "schema": APPROVAL_GATE_SCHEMA,
        "generated_at_utc": utc_now(),
        "workflow_id": WORKFLOW_ID,
        "status": "ok",
        "summary": {
            "card_count": len(cards),
            "review_ready_count": len(eligible),
            "approval_band_eligible_count": len(band_eligible),
            "approval_card_draft_count": len(draft_candidates),
            "decision_blocked_count": sum(1 for card in cards if card.get("decision_state") != "review_ready"),
            "approval_draft_blocked_count": len(blocked),
            "blocked_count": len(blocked),
            "blocked_count_semantics": "approval_draft_blocked_count",
            "expected_approval_card_draft_count_before_freshness_repair": EXPECTED_APPROVAL_DRAFT_COUNT_BEFORE_FRESHNESS_REPAIR,
            "wf67_paper_guard_fresh": paper_guard_fresh,
            "wf67_paper_guard_clean": paper_guard_clean,
            "wf67_paper_guard_status": paper_guard_status,
            "wf67_paper_guard_ready_for_paper_submit_cancel": paper_guard_ready,
            "wf67_paper_guard_age_days": paper_guard_age,
        },
        "approval_card_drafts": draft_candidates,
        "blocked": blocked,
        "validation": {"status": "ok", "errors": [], "warnings": warnings},
        "authority_boundary": AUTHORITY_BOUNDARY,
        "stop_line": "Approval-card drafts are not approval; WF67 paper action remains blocked until Randall exact approval and fresh guards.",
    }


def readiness_invariant_errors(cards: list[dict[str, Any]], approval_gate: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    cards_by_ticker = {str(card.get("ticker") or "").upper(): card for card in cards}
    for card in cards:
        promoted_review_ready = (
            as_dict(card.get("promotion_gate")).get("verdict") == PROMOTION_REVIEW_VERDICT
            and as_dict(card.get("source_freshness")).get("status") == "fresh"
            and card_band_status(card) == APPROVAL_DRAFT_BAND_STATUS
        )
        if (
            card.get("decision_state") == "review_ready"
            and card.get("primary_state") not in REVIEW_READY_PRIMARY_STATES
            and not promoted_review_ready
        ):
            errors.append(f"review_ready_primary_state_invalid:{card.get('ticker')}:{card.get('primary_state')}")
    for draft in approval_gate.get("approval_card_drafts", []):
        ticker = str(draft.get("ticker") or "").upper()
        source_card = cards_by_ticker.get(ticker, {})
        quote_status = card_quote_freshness_status(source_card)
        band_status = card_band_status(source_card)
        if quote_status not in APPROVAL_DRAFT_QUOTE_FRESH_OK:
            errors.append(f"approval_draft_quote_freshness_invalid:{ticker}:{quote_status}")
        if band_status != APPROVAL_DRAFT_BAND_STATUS:
            errors.append(f"approval_draft_band_status_invalid:{ticker}:{band_status}")
    return errors


def self_test() -> dict[str, Any]:
    fresh_guard = {"generated_at_utc": utc_now(), "status": "ok", "ready_for_paper_submit_cancel": True}
    fresh_blocked_guard = {"generated_at_utc": utc_now(), "status": "blocked", "ready_for_paper_submit_cancel": False}
    draft_probe_cards = [
        {
            "ticker": "INB",
            "decision_state": "review_ready",
            "decision_state_reason": [],
            "entry_band": {"band_status": "IN_BAND"},
            "source_freshness": {"quote_freshness_status": "intraday_fresh"},
            "authority_boundary": AUTHORITY_BOUNDARY,
        },
        {
            "ticker": "LOW",
            "decision_state": "review_ready",
            "decision_state_reason": [],
            "entry_band": {"band_status": "BELOW_BAND_WAIT"},
            "source_freshness": {"quote_freshness_status": "intraday_fresh"},
            "authority_boundary": AUTHORITY_BOUNDARY,
        },
        {
            "ticker": "NEAR",
            "decision_state": "review_ready",
            "decision_state_reason": [],
            "entry_band": {"band_status": "NEAR_BAND"},
            "source_freshness": {"quote_freshness_status": "intraday_fresh"},
            "authority_boundary": AUTHORITY_BOUNDARY,
        },
        {
            "ticker": "POST",
            "decision_state": "review_ready",
            "decision_state_reason": [],
            "entry_band": {"band_status": "IN_BAND"},
            "source_freshness": {"quote_freshness_status": "post_close_final_quote_available_for_non_executing_review"},
            "authority_boundary": AUTHORITY_BOUNDARY,
        },
        {
            "ticker": "TECH",
            "decision_state": "review_ready",
            "decision_state_reason": [],
            "entry_band": {"band_status": "IN_BAND"},
            "source_freshness": {"quote_freshness_status": NON_EXECUTION_TECHNICAL_PRICE_FRESHNESS},
            "authority_boundary": AUTHORITY_BOUNDARY,
        },
    ]
    fresh_gate = build_approval_gate(draft_probe_cards, {}, fresh_guard)
    fresh_blocked_gate = build_approval_gate([draft_probe_cards[0]], {}, fresh_blocked_guard)
    stale_post_gate = build_approval_gate([draft_probe_cards[3]], {}, {"generated_at_utc": "2000-01-01T00:00:00Z"})
    stale_gate = build_approval_gate([draft_probe_cards[0]], {}, {"generated_at_utc": "2000-01-01T00:00:00Z"})
    drafts = fresh_gate.get("approval_card_drafts", [])
    errors: list[str] = []
    if [item.get("ticker") for item in drafts] != ["INB"]:
        errors.append("non_in_band_review_ready_card_became_approval_draft")
    post_close_blocks_drafts = not any(item.get("ticker") == "POST" for item in drafts)
    if not post_close_blocks_drafts:
        errors.append("post_close_non_executing_quote_allowed_approval_draft")
    technical_review_blocks_drafts = not any(item.get("ticker") == "TECH" for item in drafts)
    if not technical_review_blocks_drafts:
        errors.append("technical_non_executing_quote_allowed_approval_draft")
    stale_post_block = (stale_post_gate.get("blocked") or [{}])[0]
    stale_post_blocked_by_quote = stale_post_block.get("decision_state") == "blocked_non_executing_quote_for_approval_card"
    if not stale_post_blocked_by_quote:
        errors.append("stale_post_close_quote_not_blocked_before_wf67_guard")
    if stale_gate.get("summary", {}).get("approval_card_draft_count") != 0:
        errors.append("stale_wf67_guard_allowed_approval_draft")
    if fresh_blocked_gate.get("summary", {}).get("approval_card_draft_count") != 0:
        errors.append("blocked_wf67_guard_allowed_approval_draft")
    clean_state, _ = classify_decision_state(
        {"ticker": "CLEAN", "primary_state": "approval_card_clean", "band_status": "IN_BAND", "entry_band_low": 1, "entry_band_high": 2, "stop_or_invalidation": 0.5},
        {"source_open_status": "verified"},
        {"status": "fresh"},
        {},
    )
    dirty_state, _ = classify_decision_state(
        {"ticker": "DIRTY", "primary_state": "in_band_not_clean", "band_status": "IN_BAND", "entry_band_low": 1, "entry_band_high": 2, "stop_or_invalidation": 0.5, "owner_action_required": True},
        {"source_open_status": "verified"},
        {"status": "fresh"},
        {},
    )
    thin_state, _ = classify_decision_state(
        {"ticker": "THIN", "primary_state": "evidence_repair", "band_status": "UNKNOWN", "entry_band_low": None, "entry_band_high": None, "stop_or_invalidation": None},
        {"source_open_status": "scoped_thin_monitor_not_required"},
        {"status": "scoped_thin_monitor_not_required"},
        {"thin_monitor_row": 1, "production_answer_path_member": 0, "decision_grade_eligible": 0},
    )
    stale_freshness_state, _ = classify_decision_state(
        {"ticker": "STALE", "primary_state": "blocked_missing_freshness", "band_status": "ABOVE_BAND_WAIT", "entry_band_low": 1, "entry_band_high": 2, "stop_or_invalidation": 0.5},
        {"source_open_status": "verified"},
        {"status": "fresh"},
        {},
    )
    if clean_state != "review_ready":
        errors.append("approval_card_clean_not_review_ready")
    if dirty_state == "review_ready":
        errors.append("owner_action_required_alone_allowed_review_ready")
    if thin_state != "monitor_only":
        errors.append("thin_monitor_missing_band_or_stop_became_decision_blocker")
    if stale_freshness_state != "no_chase":
        errors.append("stale_primary_freshness_blocker_did_not_clear_against_current_gate")
    return {
        "status": "ok" if not errors else "blocked",
        "tests": {
            "fresh_source_verified_non_in_band_review_ready_cards_blocked_from_drafts": not any(
                item.get("ticker") in {"LOW", "NEAR"} for item in drafts
            ),
            "stale_wf67_guard_blocks_drafts": stale_gate.get("summary", {}).get("approval_card_draft_count") == 0,
            "blocked_wf67_guard_blocks_drafts": fresh_blocked_gate.get("summary", {}).get("approval_card_draft_count") == 0,
            "approval_card_clean_becomes_review_ready": clean_state == "review_ready",
            "owner_action_required_alone_does_not_become_review_ready": dirty_state != "review_ready",
            "thin_monitor_missing_band_or_stop_is_monitor_only": thin_state == "monitor_only",
            "stale_primary_freshness_blocker_clears_when_current_gate_clean": stale_freshness_state == "no_chase",
            "post_close_non_executing_quote_blocks_approval_draft": post_close_blocks_drafts,
            "technical_non_executing_quote_blocks_approval_draft": technical_review_blocks_drafts,
            "post_close_non_executing_quote_blocks_before_wf67_guard": stale_post_blocked_by_quote,
        },
        "errors": errors,
    }


def build_artifacts() -> dict[str, dict[str, Any]]:
    generated = utc_now()
    wf84_packet = load_json(WF84_PACKET)
    contract = load_json(WF85_CONTRACT)
    analog_match = load_json(CURRENT_ANALOG_MATCH)
    scenario_context = scenario_context_public(analog_match)
    db_probe = sqlite_probe()
    parity = wf84_parity_probe(wf84_packet, db_probe)
    errors: list[str] = []
    warnings: list[str] = []
    if parity["status"] != "ok":
        errors.append("wf84_json_sqlite_parity_failed")
    if contract.get("status") not in {"ok", "warning"}:
        errors.append("wf85_contract_not_ok")
    if contract.get("validation", {}).get("warnings"):
        warnings.extend([f"contract:{item}" for item in contract.get("validation", {}).get("warnings", [])])
    cards: list[dict[str, Any]] = []
    source_gate_rows: list[dict[str, Any]] = []
    freshness_rows: list[dict[str, Any]] = []
    if not errors:
        with connect_ro() as conn:
            current_by_ticker = rows_by_ticker(conn, "SELECT * FROM v_wf84_priority_queue ORDER BY review_priority_score DESC, ticker")
            price_by_ticker = rows_by_ticker(conn, "SELECT * FROM price_technical_current")
            entry_by_ticker = rows_by_ticker(conn, "SELECT * FROM entry_stop_reference")
            membership_by_ticker = rows_by_ticker(conn, "SELECT * FROM universe_membership")
            sources_by_ticker = list_by_ticker(conn, "SELECT * FROM v_ticker_source_drillback ORDER BY ticker, source_use")
            families_by_ticker = list_by_ticker(conn, "SELECT * FROM evidence_family_status ORDER BY ticker, family_id")
        for ticker, current in current_by_ticker.items():
            card, source_gate, freshness = build_card(
                current,
                price_by_ticker.get(ticker, {}),
                entry_by_ticker.get(ticker, {}),
                sources_by_ticker.get(ticker, []),
                families_by_ticker.get(ticker, []),
                membership_by_ticker.get(ticker, {}),
                scenario_context,
            )
            cards.append(card)
            source_gate_rows.append(source_gate)
            freshness_rows.append(freshness)
    state_counts = Counter(card.get("decision_state") for card in cards)
    source_counts = Counter(row.get("source_open_status") for row in source_gate_rows)
    freshness_counts = Counter(row.get("status") for row in freshness_rows)
    sql_canon_context = sql_canon_scope_context(cards)
    sql_canon_errors = sql_canon_context.get("validation", {}).get("critical_errors") or []
    if sql_canon_errors:
        errors.extend(f"sql_canon:{item}" for item in sql_canon_errors)
    source_gate_payload = {
        "schema": SOURCE_GATE_SCHEMA,
        "generated_at_utc": generated,
        "workflow_id": WORKFLOW_ID,
        "status": "blocked" if errors else "ok",
        "summary": {
            "ticker_count": len(source_gate_rows),
            "source_open_status_counts": dict(source_counts),
            "freshness_status_counts": dict(freshness_counts),
            "wf84_json_sqlite_parity": parity.get("status"),
            "sql_canon_scope_status": sql_canon_context.get("status"),
            "sql_canon_production_answer_count": sql_canon_context.get("sql_canon_production_answer_count"),
        },
        "wf84_sqlite_probe": db_probe,
        "wf84_json_sqlite_parity": parity,
        "sql_canon_scope": sql_canon_context,
        "rows": source_gate_rows,
        "validation": {"status": "blocked" if errors else "ok", "errors": errors, "warnings": warnings},
        "stop_line": "No material finance claim from WF84 SQLite alone; source drillback remains required.",
    }
    cards_payload = {
        "schema": SCHEMA,
        "generated_at_utc": generated,
        "workflow_id": WORKFLOW_ID,
        "status": "blocked" if errors else "ok",
        "summary": {
            "card_count": len(cards),
            "decision_state_counts": dict(state_counts),
            "approval_card_draft_count": sum(1 for card in cards if card.get("decision_state") == "approval_card_draft"),
            "authority_flags_false_by_contract": True,
            "sql_canon_scope_status": sql_canon_context.get("status"),
            "sql_canon_production_answer_count": sql_canon_context.get("sql_canon_production_answer_count"),
        },
        "source_gate_artifact": rel(DEFAULT_SOURCE_GATE_OUT),
        "scenario_context_artifact": rel(CURRENT_ANALOG_MATCH),
        "sql_canon_scope": sql_canon_context,
        "cards": cards,
        "validation": {"status": "blocked" if errors else "ok", "errors": errors, "warnings": warnings},
        "authority_boundary": AUTHORITY_BOUNDARY,
    }
    approval_gate = build_approval_gate(cards, contract)
    invariant_errors = readiness_invariant_errors(cards, approval_gate)
    if invariant_errors:
        cards_payload["status"] = "blocked"
        cards_payload["validation"]["status"] = "blocked"
        cards_payload["validation"]["errors"].extend(invariant_errors)
        approval_gate["status"] = "blocked"
        approval_gate["validation"]["status"] = "blocked"
        approval_gate["validation"]["errors"].extend(invariant_errors)
    risk_overlay = build_risk_overlay(cards)
    authority = authority_validation(cards_payload, approval_gate, risk_overlay)
    if authority.get("status") != "ok":
        cards_payload["status"] = "blocked"
        cards_payload["validation"]["status"] = "blocked"
        cards_payload["validation"]["errors"].append("authority_validation_failed")
    return {
        "source_gate": source_gate_payload,
        "cards": cards_payload,
        "approval_gate": approval_gate,
        "risk_overlay": risk_overlay,
        "authority_validation": authority,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build WF85 trade-grade decision-card proof artifacts.")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--pretty", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--cards-out", type=Path, default=DEFAULT_CARDS_OUT)
    parser.add_argument("--source-gate-out", type=Path, default=DEFAULT_SOURCE_GATE_OUT)
    parser.add_argument("--authority-out", type=Path, default=DEFAULT_AUTHORITY_OUT)
    parser.add_argument("--approval-gate-out", type=Path, default=DEFAULT_APPROVAL_GATE_OUT)
    parser.add_argument("--risk-out", type=Path, default=DEFAULT_RISK_OUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    test_result = self_test()
    if args.self_test and not args.write:
        print(json.dumps(test_result, indent=2 if args.pretty else None, sort_keys=True))
        return 0 if test_result.get("status") == "ok" else 1
    artifacts = build_artifacts()
    outputs = {
        "source_gate": args.source_gate_out,
        "cards": args.cards_out,
        "authority_validation": args.authority_out,
        "approval_gate": args.approval_gate_out,
        "risk_overlay": args.risk_out,
    }
    if args.write:
        for key, path in outputs.items():
            out = path if path.is_absolute() else ROOT / path
            atomic_write_json(out, artifacts[key])
        print(
            "wrote "
            + ", ".join(rel((path if path.is_absolute() else ROOT / path)) for path in outputs.values())
            + f" status={artifacts['cards'].get('status')} authority={artifacts['authority_validation'].get('status')}"
        )
    else:
        print(json.dumps(artifacts, indent=2 if args.pretty else None, sort_keys=True))
    if args.validate:
        bad = [
            key
            for key, payload in artifacts.items()
            if payload.get("validation", {}).get("status", payload.get("status")) == "blocked"
            or payload.get("status") == "blocked"
        ]
        if test_result.get("status") != "ok":
            bad.append("self_test")
        if bad:
            print(f"validation blocked: {','.join(bad)}")
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
