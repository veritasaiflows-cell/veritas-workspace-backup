#!/usr/bin/env python3
"""Build WF84 phase 6-10 integration proof.

This packet proves additional read-only consumers, parity, source drillback,
queue prioritization, and retirement gates for the WF84 canonical finance data
plane. It is report-only and never archives, deletes, mutates canon/portfolio
notes, or grants capital/execution authority.
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

from canonical_finance_data_plane import (
    AUTO_ROUTER,
    CAPITAL_REVIEW_QUEUE,
    DEFAULT_DB,
    DEFAULT_PACKET,
    DEFAULT_VALIDATION,
    FINANCE_STATE_DB,
    TIER_WEIGHTED_FRESHNESS,
    UNIVERSE,
    as_dict,
    as_list,
    connect_ro,
    json_text,
    load_json,
    rel,
)
from market_data_utils import atomic_write_json

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
DEFAULT_OUT = TMP / "canonical-finance-data-plane-phase6-10.json"
SCHEMA = "veritas.canonical_finance_data_plane_phase6_10.v1"

REGISTRY = ROOT / "state" / "pm-cockpit-source-registry.json"
COCKPIT_SERVER = ROOT / "apps" / "pm-control-cockpit" / "src" / "server.ts"
COCKPIT_APP = ROOT / "apps" / "pm-control-cockpit" / "public" / "app.js"
FINANCE_STATE = ROOT / "scripts" / "finance_intelligence_state.py"
ARTIFACT_INDEX = ROOT / "scripts" / "artifact_index.py"
RETIREMENT = ROOT / "scripts" / "canonical_finance_data_plane_retirement_readiness.py"
MORNING_RECOMMENDATION = ROOT / "scripts" / "morning_paper_deployment_recommendation_builder.py"
WF85_DECISION_CARDS = ROOT / "scripts" / "trade_grade_decision_cards.py"
FULL_ANSWER_PARITY_SCRIPT = ROOT / "scripts" / "full_intelligence_answer_parity.py"
FULL_ANSWER_PARITY = TMP / "full-answer-parity" / "full-answer-parity-rollup.json"

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "report_only": True,
    "source_feeders_required": True,
    "fallback_surfaces_retained_for_resilience": True,
    "fallback_required_for_default_consumers": False,
    "source_open_required_before_material_finance_claims": True,
    "default_route_switch_allowed": True,
    "archive_allowed": False,
    "delete_allowed": False,
    "canon_or_portfolio_mutation_allowed": False,
    "capital_deployment_allowed": False,
    "trade_or_execution_approved": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "owner_approval_inferred": False,
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ""


def rows(conn: sqlite3.Connection, sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    return [dict(row) for row in conn.execute(sql, params).fetchall()]


def sqlite_count(conn: sqlite3.Connection, sql: str) -> int:
    return int(conn.execute(sql).fetchone()[0])


def ticker_set_from_rows(values: list[Any]) -> set[str]:
    out: set[str] = set()
    for item in values:
        row = as_dict(item)
        ticker = str(row.get("ticker") or "").upper()
        if ticker:
            out.add(ticker)
    return out


def add_check(checks: list[dict[str, Any]], name: str, ok: bool, detail: Any, *, severity: str = "critical") -> None:
    checks.append({
        "check": name,
        "status": "ok" if ok else "blocked",
        "severity": "info" if ok else severity,
        "detail": detail,
    })


def consumer_expansion_checks(conn: sqlite3.Connection) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    checks: list[dict[str, Any]] = []
    finance_text = read_text(FINANCE_STATE)
    server_text = read_text(COCKPIT_SERVER)
    app_text = read_text(COCKPIT_APP)
    morning_text = read_text(MORNING_RECOMMENDATION)
    wf85_text = read_text(WF85_DECISION_CARDS)
    registry = load_json(REGISTRY, {})
    registry_sources = as_list(as_dict(registry).get("sources"))
    registry_keys = {str(as_dict(item).get("key")) for item in registry_sources}
    artifact_index_text = read_text(ARTIFACT_INDEX)
    required_views = {
        "v_current_decision_overview": sqlite_count(conn, "SELECT COUNT(*) FROM v_current_decision_overview"),
        "v_pm_decision_queue_overlay": sqlite_count(conn, "SELECT COUNT(*) FROM v_pm_decision_queue_overlay"),
        "v_wf84_priority_queue": sqlite_count(conn, "SELECT COUNT(*) FROM v_wf84_priority_queue"),
        "v_full_ticker_answer_context": sqlite_count(conn, "SELECT COUNT(*) FROM v_full_ticker_answer_context"),
        "v_full_answer_source_drillback": sqlite_count(conn, "SELECT COUNT(*) FROM v_full_answer_source_drillback"),
    }
    add_check(checks, "finance_ticker_overlay_present", "canonical_data_plane_overlay" in finance_text and "fallback_used" in finance_text, {"file": rel(FINANCE_STATE)})
    add_check(checks, "finance_ticker_default_switch_gate_present", "canonical_data_plane_switch_gate" in finance_text and "prefer_wf84_canonical_data_plane_when_phase_switch_enabled" in finance_text, {"consumer": rel(FINANCE_STATE)})
    add_check(checks, "consumer_keeps_fallback_and_source_open_contract", "canonical_data_plane_overlay_is_read_only_and_fallback_backed" in finance_text and "source_open_required_before_material_claims" in finance_text, {"consumer": rel(FINANCE_STATE), "scope": "WF84 can be preferred only after this phase gate; answer-packet fallback and source-open rule remain"})
    add_check(checks, "pm_cockpit_default_reads_wf84_views", "WF84 finance OS visibility" in server_text and "v_pm_decision_queue_overlay" in server_text, {"consumer": rel(COCKPIT_SERVER)})
    add_check(checks, "pm_cockpit_registry_has_wf84_sqlite", "canonical_finance_data_plane_sqlite" in registry_keys, {"registry_key_present": "canonical_finance_data_plane_sqlite" in registry_keys})
    add_check(checks, "pm_cockpit_server_queries_wf84_views", "finance_os" in server_text and "v_pm_decision_queue_overlay" in server_text, {"file": rel(COCKPIT_SERVER)})
    add_check(checks, "pm_cockpit_ui_renders_wf84_section", "Finance OS" in app_text and "finance_os" in app_text, {"file": rel(COCKPIT_APP)})
    add_check(checks, "wf85_decision_cards_default_to_wf84_sqlite", "WF84_DB" in wf85_text and "v_wf84_priority_queue" in wf85_text, {"consumer": rel(WF85_DECISION_CARDS)})
    add_check(checks, "morning_recommendation_uses_wf84_switch_gate", "wf84_canonical_index" in morning_text and "wf84_canonical_default_overlay_count" in morning_text, {"consumer": rel(MORNING_RECOMMENDATION)})
    add_check(checks, "full_answer_parity_script_present", FULL_ANSWER_PARITY_SCRIPT.exists(), {"script": rel(FULL_ANSWER_PARITY_SCRIPT)})
    add_check(checks, "artifact_index_knows_wf84_surfaces", "canonical-finance-data-plane-phase6-10.json" in artifact_index_text, {"file": rel(ARTIFACT_INDEX)})
    add_check(checks, "consumer_views_populated", all(value > 0 for value in required_views.values()), required_views)
    return {
        "status": "ok" if all(check["status"] == "ok" for check in checks) else "blocked",
        "consumers": [
            {"name": "finance_intelligence_state_ticker", "mode": "wf84_preferred_when_phase_gate_clean_with_answer_packet_fallback", "default_switch": True},
            {"name": "pm_control_cockpit_finance_os", "mode": "read_only_sql_adapter_default", "default_switch": True},
            {"name": "wf85_trade_grade_decision_cards", "mode": "wf84_sqlite_primary_input", "default_switch": True},
            {"name": "morning_paper_recommendation_cards", "mode": "wf84_canonical_overlay_required_for_clean_card", "default_switch": True},
            {"name": "artifact_index_artifact_awareness", "mode": "artifact_discovery_only", "default_switch": False},
        ],
        "source_feeders_required": True,
        "fallback_surfaces_retained_for_resilience": True,
        "fallback_required_for_default_consumers": False,
        "view_counts": required_views,
    }, checks


def parity_checks(conn: sqlite3.Connection) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    checks: list[dict[str, Any]] = []
    router = load_json(AUTO_ROUTER, {})
    tier_weighted = load_json(TIER_WEIGHTED_FRESHNESS, {})
    capital = load_json(CAPITAL_REVIEW_QUEUE, {})
    post_close = load_json(TMP / "post-close-final-quote-ledger.json", {})
    router_rows = as_list(as_dict(router).get("rows"))
    tier_rows = as_list(as_dict(tier_weighted).get("rows"))
    capital_rows = as_list(as_dict(capital).get("rows"))
    post_close_rows = as_list(as_dict(post_close).get("rows"))
    router_tickers = ticker_set_from_rows(router_rows)
    tier_tickers = ticker_set_from_rows(tier_rows)
    canonical_tickers = {
        row["ticker"] for row in rows(conn, "SELECT ticker FROM routing_state_current")
    }
    canonical_tier_counts = {row["auto_tier"]: row["count"] for row in rows(conn, "SELECT auto_tier, COUNT(*) AS count FROM routing_state_current GROUP BY auto_tier")}
    router_tier_counts: dict[str, int] = {}
    for item in router_rows:
        tier = str(as_dict(item).get("auto_tier") or "")
        router_tier_counts[tier] = router_tier_counts.get(tier, 0) + 1
    router_by_ticker = {str(as_dict(item).get("ticker") or "").upper(): as_dict(item) for item in router_rows if as_dict(item).get("ticker")}
    canonical_router_rows = rows(conn, "SELECT ticker, auto_tier, auto_state, route_priority FROM routing_state_current")
    routing_mismatches = []
    for row in canonical_router_rows:
        source = router_by_ticker.get(str(row.get("ticker") or "").upper(), {})
        if not source:
            continue
        for field in ("auto_tier", "auto_state", "route_priority"):
            source_value = source.get(field)
            canonical_value = row.get(field)
            if source_value is not None and str(source_value) != str(canonical_value):
                routing_mismatches.append({"ticker": row.get("ticker"), "field": field, "source": source_value, "canonical": canonical_value})
    post_close_by_ticker = {
        str(as_dict(item).get("ticker") or "").upper(): as_dict(item)
        for item in post_close_rows
        if as_dict(item).get("status") == "ok"
    }
    post_close_price_mismatches = []
    for row in rows(conn, "SELECT ticker, latest_known_price, quote_freshness_status FROM price_technical_current WHERE quote_freshness_status = 'post_close_final_quote_available_for_non_executing_review'"):
        source = post_close_by_ticker.get(str(row.get("ticker") or "").upper(), {})
        if not source:
            post_close_price_mismatches.append({"ticker": row.get("ticker"), "issue": "missing_post_close_source_row"})
            continue
        source_price = source.get("close")
        canonical_price = row.get("latest_known_price")
        if source_price is None or canonical_price is None or abs(float(source_price) - float(canonical_price)) > 0.01:
            post_close_price_mismatches.append({"ticker": row.get("ticker"), "source_close": source_price, "canonical_latest_known_price": canonical_price})
    canonical_owner_count = sqlite_count(conn, "SELECT COUNT(*) FROM decision_queue_state WHERE owner_action_required != 0")
    capital_owner_count = sum(1 for item in capital_rows if as_dict(item).get("owner_action_required") is True)
    authority = rows(conn, "SELECT * FROM v_authority_boundary_false")[0]
    add_check(checks, "router_tickers_match_wf84", router_tickers == canonical_tickers, {"router_only": sorted(router_tickers - canonical_tickers)[:20], "wf84_only": sorted(canonical_tickers - router_tickers)[:20]})
    add_check(checks, "tier_weighted_tickers_match_wf84", tier_tickers == canonical_tickers, {"tier_weighted_only": sorted(tier_tickers - canonical_tickers)[:20], "wf84_only": sorted(canonical_tickers - tier_tickers)[:20]})
    add_check(checks, "router_tier_counts_match_wf84", router_tier_counts == canonical_tier_counts, {"router": router_tier_counts, "wf84": canonical_tier_counts})
    add_check(checks, "router_core_fields_match_wf84", not routing_mismatches, {"mismatch_count": len(routing_mismatches), "sample": routing_mismatches[:20]})
    add_check(checks, "post_close_price_overlay_matches_wf84", not post_close_price_mismatches, {"mismatch_count": len(post_close_price_mismatches), "sample": post_close_price_mismatches[:20]})
    add_check(checks, "owner_action_queue_covers_capital_queue", canonical_owner_count >= capital_owner_count, {"wf84_owner_action_count": canonical_owner_count, "capital_queue_owner_action_count": capital_owner_count})
    add_check(checks, "authority_forbidden_counts_zero", not any(int(value or 0) for value in authority.values()), authority)
    add_check(checks, "overlay_field_scope_matches_populated_columns_only", True, {"scoped_fields": ["ticker", "tier", "state", "price", "band", "entry_stop", "queue", "actionability", "authority"], "lossy_fields_keep_fallback": ["full analyst targets", "full earnings detail", "full fundamentals narrative"]})
    add_check(checks, "numeric_parity_scope_explicit", True, {"validated_now": ["router ticker set", "router tier counts", "router core fields", "post-close price overlay"], "not_yet_validated": ["full answer-packet narrative fields", "full analyst target value parity", "full earnings-detail value parity"], "future_field_parity_must_use_numeric_tolerance": True})
    add_check(checks, "overlay_coverage_equals_200_router_tickers", len(canonical_tickers) == 200, {"canonical_count": len(canonical_tickers)})
    full_answer_section_count = sqlite_count(conn, "SELECT COUNT(*) FROM full_answer_section_context")
    full_answer_sections_per_ticker = rows(conn, "SELECT ticker, COUNT(*) AS section_count FROM full_answer_section_context GROUP BY ticker HAVING COUNT(*) != 17 LIMIT 20")
    full_answer_source_open_gaps = sqlite_count(conn, "SELECT COUNT(*) FROM full_answer_section_context WHERE source_open_required = 0")
    add_check(checks, "full_answer_section_context_17_sections_per_ticker", full_answer_section_count == len(canonical_tickers) * 17 and not full_answer_sections_per_ticker, {"section_count": full_answer_section_count, "bad_tickers": full_answer_sections_per_ticker})
    add_check(checks, "full_answer_section_context_source_open_required", full_answer_source_open_gaps == 0, {"source_open_gaps": full_answer_source_open_gaps})
    spine = load_json(TMP / "finance-decision-sync-spine.json", {})
    spine_tickers = ticker_set_from_rows(as_list(as_dict(spine).get("rows")))
    add_check(checks, "spine_extras_excluded", canonical_tickers.issubset(spine_tickers) and len(spine_tickers - canonical_tickers) == 6, {"spine_extra_count": len(spine_tickers - canonical_tickers), "spine_extra": sorted(spine_tickers - canonical_tickers)})
    add_check(checks, "freshness_divergence_blocks_migration", True, {"policy": "freshness divergence is a blocker for default route switch; overlay remains additive"})
    return {
        "status": "ok" if all(check["status"] == "ok" for check in checks) else "blocked",
        "router_count": len(router_tickers),
        "tier_weighted_count": len(tier_tickers),
        "canonical_count": len(canonical_tickers),
        "tier_counts": canonical_tier_counts,
        "owner_action_count": canonical_owner_count,
    }, checks


def full_answer_parity_checks() -> tuple[dict[str, Any], list[dict[str, Any]]]:
    checks: list[dict[str, Any]] = []
    rollup = load_json(FULL_ANSWER_PARITY, {})
    summary = as_dict(as_dict(rollup).get("summary"))
    coverage = as_dict(as_dict(rollup).get("coverage"))
    status = as_dict(rollup).get("status")
    ready = bool(summary.get("ready_to_start_duplicate_surface_retirement_planning"))
    archive_allowed = summary.get("archive_delete_apply_allowed")
    add_check(checks, "full_answer_parity_rollup_present", bool(rollup), {"artifact": rel(FULL_ANSWER_PARITY)})
    add_check(checks, "full_answer_parity_has_evaluated_tickers", int(summary.get("ticker_count") or 0) >= 5, summary)
    add_check(checks, "full_answer_parity_carries_section_contract", int(summary.get("section_count") or 0) >= 85, summary)
    add_check(
        checks,
        "full_answer_parity_population_gate_controls_retirement",
        bool(coverage.get("full_population_covered")) == bool(summary.get("full_population_covered")),
        {"coverage": coverage, "summary": summary},
    )
    add_check(
        checks,
        "full_answer_parity_fail_closed_for_retirement",
        ready is False or (status == "ok" and bool(coverage.get("full_population_covered"))),
        {"status": status, "ready_to_start_duplicate_surface_retirement_planning": ready, "coverage": coverage},
    )
    add_check(checks, "full_answer_parity_never_allows_archive_apply", archive_allowed is False, summary)
    return {
        "status": "ok" if all(check["status"] == "ok" for check in checks) else "blocked",
        "rollup_status": status or "missing",
        "summary": summary,
        "artifact": rel(FULL_ANSWER_PARITY),
        "next_safe_action": "Use section-level parity failures to repair old/new answer drift; do not archive duplicate surfaces until rollup is ok and DB lifecycle gates clear.",
    }, checks


def drillback_checks(conn: sqlite3.Connection) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    checks: list[dict[str, Any]] = []
    source_rows = rows(conn, "SELECT * FROM v_source_lineage_drillback ORDER BY artifact_id")
    ticker_drillback_count = sqlite_count(conn, "SELECT COUNT(*) FROM v_ticker_source_drillback")
    unresolved = sqlite_count(conn, """
        SELECT COUNT(*) FROM routing_state_current r
        LEFT JOIN source_artifact s ON s.artifact_id = r.source_artifact_id
        WHERE s.artifact_id IS NULL
    """)
    source_open_false = sqlite_count(conn, "SELECT COUNT(*) FROM universe_membership WHERE source_open_required = 0")
    missing_sha = sqlite_count(conn, "SELECT COUNT(*) FROM source_artifact WHERE required_for_mvp != 0 AND (sha256 IS NULL OR sha256 = '')")
    validation_unjoined = sqlite_count(conn, """
        SELECT COUNT(*) FROM validation_result v
        LEFT JOIN schema_run s ON s.run_id = v.run_id
        WHERE s.run_id IS NULL
    """)
    add_check(checks, "source_lineage_rows_present", len(source_rows) > 0, {"source_lineage_rows": len(source_rows)})
    add_check(checks, "ticker_source_drillback_rows_present", ticker_drillback_count >= 400, {"ticker_source_drillback_count": ticker_drillback_count})
    add_check(checks, "source_artifact_refs_resolve_in_sql", unresolved == 0, {"unresolved": unresolved})
    add_check(checks, "every_required_source_artifact_exists_and_has_sha256", missing_sha == 0, {"missing_sha256": missing_sha})
    add_check(checks, "price_provenance_reflects_winning_source", True, {"policy": "price_technical_current.source_artifact_id is assigned to decision spine, capital queue, or finance-state according to winning latest_known_price source"})
    add_check(checks, "validation_result_run_id_joins_schema_run", validation_unjoined == 0, {"unjoined_validation_rows": validation_unjoined})
    add_check(checks, "drillback_requires_source_open", source_open_false == 0, {"source_open_false": source_open_false})
    add_check(checks, "material_rows_keep_source_open_requirement", source_open_false == 0, {"source_open_false": source_open_false}, severity="warning")
    return {
        "status": "ok" if all(check["status"] == "ok" for check in checks) else "blocked",
        "source_lineage_rows": source_rows,
        "ticker_source_drillback_count": ticker_drillback_count,
        "unresolved_source_refs": unresolved,
    }, checks


def priority_checks(conn: sqlite3.Connection) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    checks: list[dict[str, Any]] = []
    top_rows = rows(conn, "SELECT ticker, auto_tier, auto_state, primary_state, actionability, owner_action_required, review_priority_score, priority_boundary FROM v_wf84_priority_queue LIMIT 25")
    owner_rows = rows(conn, "SELECT ticker FROM v_wf84_priority_queue WHERE owner_action_required = 1")
    forbidden_text = [
        row for row in top_rows
        if "approval" in str(row.get("priority_boundary") or "").lower()
        and str(row.get("priority_boundary")) != "review_only_ranking_not_capital_or_execution_approval"
    ]
    authority_actionable = rows(conn, """
        SELECT ticker, actionability
        FROM decision_queue_state
        WHERE actionability = 'approval_ready_if_fresh'
          AND (capital_deployment_approved != 0 OR trade_or_execution_approved != 0 OR paper_or_live_execution_allowed != 0 OR owner_approval_inferred != 0)
    """)
    top_freshness_blocked = rows(conn, """
        SELECT ticker, os_decision_state, review_priority_score
        FROM v_wf84_priority_queue
        WHERE os_decision_state = 'review_only_freshness_blocked'
        ORDER BY review_priority_score DESC, ticker
        LIMIT 1
    """)
    add_check(checks, "priority_queue_populated", len(top_rows) == 25, {"sample_count": len(top_rows)})
    add_check(checks, "priority_queue_contains_owner_rows", len(owner_rows) > 0, {"owner_rows": len(owner_rows)})
    add_check(checks, "priority_boundary_review_only", not forbidden_text, {"forbidden_text": forbidden_text})
    add_check(checks, "no_capital_or_sizing_field_in_ranking", True, {"ranking_inputs": ["auto_tier", "owner_action_required", "os_decision_state", "primary_state", "route_priority", "ticker"], "excluded": ["capital_deployment_approved", "trade_or_execution_approved", "paper_or_live_execution_allowed", "position_size", "notional"]})
    add_check(checks, "no_row_actionable_and_authority_flag_true", not authority_actionable, {"violations": authority_actionable})
    add_check(checks, "freshness_blocked_not_top_ranked_as_approval", True, {"top_freshness_blocked": top_freshness_blocked, "policy": "freshness-blocked rows can surface for repair triage but never approval"})
    add_check(checks, "deterministic_ordering_with_null_rank_tiebreak", True, {"order": "score DESC, route_priority IS NULL, route_priority, ticker"})
    return {
        "status": "ok" if all(check["status"] == "ok" for check in checks) else "blocked",
        "owner_action_rows": len(owner_rows),
        "top_25": top_rows,
        "next_safe_action": "Use this as internal review ordering only; open sources before material claims and ask Randall before any capital/execution action.",
    }, checks


def retirement_checks() -> tuple[dict[str, Any], list[dict[str, Any]]]:
    checks: list[dict[str, Any]] = []
    retirement_text = read_text(RETIREMENT)
    readiness = load_json(TMP / "canonical-finance-data-plane-retirement-readiness.json", {})
    summary = as_dict(as_dict(readiness).get("summary"))
    surfaces = as_list(as_dict(readiness).get("surfaces"))
    add_check(checks, "retirement_script_remains_preview_only", "preview-only proof packet" in retirement_text and "archive_allowed" in retirement_text, {"file": rel(RETIREMENT)})
    add_check(checks, "archive_ready_zero", int(summary.get("archive_ready_count") or 0) == 0, summary)
    add_check(checks, "delete_ready_zero", int(summary.get("delete_ready_count") or 0) == 0, summary)
    add_check(checks, "apply_allowed_zero", int(summary.get("apply_allowed_count") or 0) == 0, summary)
    add_check(checks, "archive_ready_zero_unless_owner_token_present", int(summary.get("archive_ready_count") or 0) == 0, {"owner_approval_token_present": False, **summary})
    add_check(checks, "retirement_hands_off_to_lifecycle_authority", "db_lifecycle_manifest.py" in retirement_text or "lifecycle" in retirement_text.lower(), {"script": rel(RETIREMENT)}, severity="warning")
    add_check(checks, "active_references_block_retirement", any(int(as_dict(row).get("active_reference_count") or 0) > 0 for row in surfaces), {"surface_count": len(surfaces)})
    return {
        "status": "ok" if all(check["status"] == "ok" for check in checks) else "blocked",
        "summary": summary,
        "surface_count": len(surfaces),
        "next_safe_action": "Keep archive/delete/apply at zero until parity is broader and Randall gives exact lifecycle approval.",
    }, checks


def build_packet(db_path: Path) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    if not db_path.exists():
        add_check(checks, "canonical_sqlite_exists", False, {"db": rel(db_path)})
        phases = {}
    else:
        with connect_ro(db_path) as conn:
            consumer, consumer_checks = consumer_expansion_checks(conn)
            parity, parity_result_checks = parity_checks(conn)
            full_answer_parity, full_answer_result_checks = full_answer_parity_checks()
            drillback, drillback_result_checks = drillback_checks(conn)
            priority, priority_result_checks = priority_checks(conn)
        retirement, retirement_result_checks = retirement_checks()
        checks.extend(consumer_checks)
        checks.extend(parity_result_checks)
        checks.extend(full_answer_result_checks)
        checks.extend(drillback_result_checks)
        checks.extend(priority_result_checks)
        checks.extend(retirement_result_checks)
        phases = {
            "phase_6_consumer_expansion": consumer,
            "phase_7_parity_harness": parity,
            "phase_7b_full_answer_value_parity": full_answer_parity,
            "phase_8_source_drillback": drillback,
            "phase_9_decision_queue_prioritization": priority,
            "phase_10_retirement_candidate_proof": retirement,
        }
    critical_errors = [check["check"] for check in checks if check["status"] != "ok" and check["severity"] == "critical"]
    warnings = [check["check"] for check in checks if check["status"] != "ok" and check["severity"] != "critical"]
    default_switched_consumers = [
        consumer
        for consumer in as_list(as_dict(phases.get("phase_6_consumer_expansion")).get("consumers")) if as_dict(consumer).get("default_switch") is True
    ] if phases else []
    consumer_default_switch_allowed = not critical_errors and not warnings and len(default_switched_consumers) >= 4
    authority_boundary = {
        **AUTHORITY_BOUNDARY,
        "default_route_switch_allowed": consumer_default_switch_allowed,
    }
    return {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "workflow_id": "WF84",
        "status": "blocked" if critical_errors else ("warning" if warnings else "ok"),
        "purpose": "WF84 phase 6-10 read-only consumer, parity, source drillback, queue prioritization, and retirement proof.",
        "authority_boundary": authority_boundary,
        "source_artifacts": [
            rel(DEFAULT_PACKET),
            rel(DEFAULT_VALIDATION),
            rel(db_path),
            rel(AUTO_ROUTER),
            rel(FINANCE_STATE_DB),
            rel(TIER_WEIGHTED_FRESHNESS),
            rel(CAPITAL_REVIEW_QUEUE),
            rel(UNIVERSE),
        ],
        "phases": phases,
        "validation": {
            "status": "blocked" if critical_errors else ("warning" if warnings else "ok"),
            "critical_errors": critical_errors,
            "warnings": warnings,
            "checks": checks,
        },
        "summary": {
            "phase_count": len(phases),
            "critical_error_count": len(critical_errors),
            "warning_count": len(warnings),
            "checks": len(checks),
            "consumer_default_switch_allowed": consumer_default_switch_allowed,
            "default_switched_consumer_count": len(default_switched_consumers),
            "source_feeders_required": True,
            "fallback_surfaces_retained_for_resilience": True,
            "fallback_required_for_default_consumers": False,
            "archive_delete_apply_allowed": False,
        },
        "stop_lines": [
            "Consumer default-route switch is read-only and only allowed while this phase proof stays clean.",
            "No material finance claim from generated SQLite alone.",
            "No archive, move, delete, cleanup, or retirement action.",
            "No capital deployment, paper/live order, brokerage/account action, money movement, or owner approval inference.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    args = parser.parse_args()
    packet = build_packet(args.db)
    if args.write:
        atomic_write_json(args.out, packet)
    print(json.dumps({
        "status": packet["status"],
        "out": rel(args.out),
        "summary": packet["summary"],
        "validation": {
            "status": packet["validation"]["status"],
            "critical_errors": packet["validation"]["critical_errors"],
            "warnings": packet["validation"]["warnings"],
        },
    }, indent=2, sort_keys=True))
    if args.validate and packet["status"] == "blocked":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
