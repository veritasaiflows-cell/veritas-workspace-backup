#!/usr/bin/env python3
"""Build automated WF78 non-capital tier/routing state.

Randall's 2026-06-05 routing posture allows Veritas to automate ticker tier and
research/deployment-review routing states. The hard approval boundary remains:
no capital deployment, no order execution, no paper/live/account action, and no
portfolio/cash/sizing execution authority.

This script writes a derived routing state artifact. It does not mutate the
durable universe, canon notes, portfolio notes, ticker cards, SQL canon, or
brokerage surfaces.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, load_json_artifact
from wf78_tier_a_confidence_gate import (
    FUNDAMENTALS as TIER_A_FUNDAMENTALS,
    IR_PACKETS as TIER_A_IR_PACKETS,
    SEC_SCALER as TIER_A_SEC_SCALER,
    classify_confidence as classify_tier_a_confidence,
)


ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
UNIVERSE = ROOT / "data" / "finance" / "universe-v1.json"
TIER_A_PACKET = TMP / "wf78-tier-a-final-promotion-packet.json"
TIER_B_SYNC_PREVIEW = TMP / "wf78-tier-label-sync-preview.json"
TIER_B_PACKET_3 = TMP / "wf78-tier-b-final-promotion-packet.next-batch-3.json"
TIER_B_PHASE2_EVAL = TMP / "wf78-tier-b-research-packet-phase2-eval.json"
TIER_A_COMPETITIVE_GATE = TMP / "wf78-tier-a-competitive-promotion-gate.json"
PRODUCTION_ADJUDICATION = TMP / "wf78-production-tier-adjudication.json"
TIER_A_CONFIDENCE_GATE = TMP / "wf78-tier-a-confidence-gate.json"
TIER_C_ATTENTION_TRIGGER = TMP / "wf78-tier-c-attention-trigger.json"
DEFAULT_OUT = TMP / "wf78-auto-tier-routing.json"
SCHEMA = "veritas.wf78_auto_tier_router.v1"

TIER_A_CAP = 25
TIER_B_CAP = 50
COMBINED_CAP = 75
OWNER_ROUTING_AUTHORITY_REFERENCE = "webchat 2026-06-05 12:30 MST Randall: non-trade/capital ticker tier routing may be automated"

AUTHORITY_BOUNDARY: dict[str, bool] = {
    "review_only": True,
    "automated_non_capital_routing_allowed": True,
    "derived_state_only": True,
    "universe_mutation_allowed": False,
    "canon_or_portfolio_mutation_allowed": False,
    "ticker_card_mutation_allowed": False,
    "sql_canon_mutation_allowed": False,
    "production_answer_path_change_allowed": False,
    "capital_deployment_allowed": False,
    "trade_execution_allowed": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "money_movement_allowed": False,
    "owner_approval_required_for_non_capital_routing": False,
    "owner_approval_required_for_capital_deployment_or_execution": True,
}

REQUIRED_TRUE_FLAGS = {
    "review_only",
    "automated_non_capital_routing_allowed",
    "derived_state_only",
    "owner_approval_required_for_capital_deployment_or_execution",
}
REQUIRED_FALSE_FLAGS = {flag for flag in AUTHORITY_BOUNDARY if flag not in REQUIRED_TRUE_FLAGS}


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


def load_dict(path: Path) -> dict[str, Any]:
    payload = load_json_artifact(path)
    return payload if isinstance(payload, dict) else {}


def add_check(checks: list[dict[str, Any]], name: str, ok: bool, detail: Any = None, severity: str = "critical") -> None:
    checks.append({"name": name, "ok": bool(ok), "status": "ok" if ok else "fail", "severity": severity, "detail": detail})


def universe_entries(universe: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        row for row in as_list(universe.get("entries"))
        if isinstance(row, dict) and row.get("ticker") and row.get("active") is not False
    ]


def by_ticker(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(row.get("ticker") or "").upper(): row for row in rows if row.get("ticker")}


def packet_rows(packet: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return by_ticker([row for row in as_list(packet.get("rows")) if isinstance(row, dict)])


def approved_tier_b(sync_preview: dict[str, Any]) -> set[str]:
    return {
        str(ticker).upper()
        for ticker in as_list(as_dict(sync_preview.get("summary")).get("approved_tier_b_research_bench_labels"))
        if str(ticker).strip()
    }


def open_tier_b_hold_set(packet: dict[str, Any]) -> set[str]:
    return {
        str(ticker).upper()
        for ticker in as_list(as_dict(packet.get("summary")).get("eligible_tickers"))
        if str(ticker).strip()
    }


def eligible_tier_b_from_phase2_eval(packet: dict[str, Any]) -> set[str]:
    return {
        str(row.get("ticker") or "").upper()
        for row in as_list(packet.get("c_to_b_decisions"))
        if isinstance(row, dict)
        and row.get("status") == "eligible_for_admission"
        and str(row.get("ticker") or "").strip()
    }


def eligible_tier_a_from_competitive_gate(packet: dict[str, Any]) -> dict[str, dict[str, Any]]:
    eligible_statuses = {"eligible_for_auto_tier_a_routing", "eligible_for_owner_approval"}
    return {
        str(row.get("ticker") or "").upper(): row
        for row in as_list(packet.get("decisions"))
        if isinstance(row, dict)
        and row.get("status") in eligible_statuses
        and str(row.get("ticker") or "").strip()
    }


def tier_c_attention_rows(packet: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(row.get("ticker") or "").upper(): row
        for row in as_list(packet.get("attention_rows"))
        if isinstance(row, dict)
        and row.get("attention_triggered") is True
        and str(row.get("ticker") or "").strip()
    }


def apply_tier_a_capacity(
    base_tier_a_rows: dict[str, dict[str, Any]],
    competitive_gate_rows: dict[str, dict[str, Any]],
) -> tuple[dict[str, dict[str, Any]], list[str]]:
    """Keep competitive B->A routing inside the existing Tier A cap."""
    remaining = max(0, TIER_A_CAP - len(base_tier_a_rows))
    ordered = sorted(
        competitive_gate_rows.items(),
        key=lambda item: (
            int(as_dict(item[1]).get("open_seat_index") or 999),
            -float(as_dict(item[1]).get("score") or 0),
            item[0],
        ),
    )
    admitted = dict(ordered[:remaining])
    held = [ticker for ticker, _row in ordered[remaining:]]
    return admitted, held


def adjudication_bucket_map(packet: dict[str, Any]) -> dict[str, str]:
    result: dict[str, str] = {}
    for row in as_list(packet.get("rows")):
        if isinstance(row, dict) and row.get("ticker"):
            result[str(row.get("ticker")).upper()] = str(row.get("recommended_bucket") or "")
    return result


def confidence_rows(packet: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return packet_rows(packet)


def converge_missing_tier_a_confidence(
    rows: list[dict[str, Any]],
    confidence_by_ticker: dict[str, dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]], list[str]]:
    missing = sorted(
        row["ticker"]
        for row in rows
        if row["auto_tier"] == "Tier A" and not row.get("tier_a_confidence_promotion_effect")
    )
    if not missing:
        return rows, confidence_by_ticker, []

    fundamentals = load_dict(TIER_A_FUNDAMENTALS)
    ir_packets = load_dict(TIER_A_IR_PACKETS)
    sec_scaler = load_dict(TIER_A_SEC_SCALER)
    fundamental_rows = by_ticker(as_list(fundamentals.get("rows")))
    rows_by_ticker = by_ticker(rows)
    synthesized: dict[str, dict[str, Any]] = {}
    for ticker in missing:
        routing_row = rows_by_ticker.get(ticker, {})
        synthesized[ticker] = {
            **classify_tier_a_confidence(ticker, routing_row, fundamental_rows.get(ticker), ir_packets, sec_scaler),
            "confidence_source": "inline_router_convergence",
        }

    converged_confidence = {**confidence_by_ticker, **synthesized}
    converged_rows: list[dict[str, Any]] = []
    for row in rows:
        ticker = str(row.get("ticker") or "").upper()
        confidence = converged_confidence.get(ticker, {})
        if row.get("auto_tier") == "Tier A" and confidence:
            updated = dict(row)
            confidence_effect = confidence.get("promotion_effect")
            critical_conflicts = int(confidence.get("critical_conflict_count") or 0)
            if ticker in synthesized:
                reason_parts = [
                    part.strip()
                    for part in str(updated.get("route_reason") or "").split(";")
                    if part.strip() and part.strip() != "missing_tier_a_confidence_row"
                ]
                reason_parts.append("tier_a_confidence_repaired_inline_from_current_fundamentals")
                updated["route_reason"] = "; ".join(reason_parts)
            if confidence_effect == "block_tier_a_promotion" or critical_conflicts > 0:
                updated["auto_tier"] = "Tier B"
                updated["auto_state"] = "B-CHALLENGED"
                updated["route_priority"] = max(int(updated.get("route_priority") or 50), 25)
                if "auto_demoted_a_to_b_by_tier_a_confidence_gate_" not in str(updated.get("route_reason") or ""):
                    updated["route_reason"] = f"{updated.get('route_reason')}; auto_demoted_a_to_b_by_tier_a_confidence_gate_{confidence_effect or 'critical_data_conflict'}"
            elif confidence_effect == "force_a_challenged":
                updated["auto_state"] = "A-CHALLENGED"
                if "tier_a_confidence_gate_" not in str(updated.get("route_reason") or ""):
                    updated["route_reason"] = f"{updated.get('route_reason')}; tier_a_confidence_gate_{confidence_effect}"
            updated["data_confidence_rating"] = confidence.get("data_confidence_rating")
            updated["fundamentals_confidence"] = confidence.get("fundamentals_confidence")
            updated["tier_a_confidence_status"] = confidence.get("tier_a_confidence_status")
            updated["tier_a_confidence_promotion_effect"] = confidence_effect
            updated["critical_data_conflict_count"] = confidence.get("critical_conflict_count")
            updated["tier_a_confidence_source"] = confidence.get("confidence_source") or "artifact"
            converged_rows.append(updated)
        else:
            converged_rows.append(row)
    return converged_rows, converged_confidence, sorted(synthesized)


def enforce_tier_a_row_cap(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[str]]:
    tier_a = [row for row in rows if row.get("auto_tier") == "Tier A"]
    if len(tier_a) <= TIER_A_CAP:
        return rows, []
    keep = {
        row["ticker"]
        for row in sorted(tier_a, key=lambda item: (int(item.get("route_priority") or 99), str(item.get("ticker") or "")))[:TIER_A_CAP]
    }
    held: list[str] = []
    capped_rows: list[dict[str, Any]] = []
    for row in rows:
        if row.get("auto_tier") == "Tier A" and row.get("ticker") not in keep:
            updated = dict(row)
            updated["auto_tier"] = "Tier B"
            updated["auto_state"] = "B-CHALLENGED"
            updated["route_priority"] = max(int(updated.get("route_priority") or 50), 25)
            updated["route_reason"] = f"{updated.get('route_reason')}; auto_demoted_to_b_by_tier_a_capacity_cap"
            held.append(str(updated.get("ticker") or ""))
            capped_rows.append(updated)
        else:
            capped_rows.append(row)
    return capped_rows, sorted(held)


def band_status_to_tier_a_state(row: dict[str, Any]) -> str:
    status = as_dict(row.get("written_band")).get("current_band_status")
    if status == "IN_BAND":
        return "A-READY"
    if status in {"ABOVE_BAND", "BELOW_BAND"}:
        return "A-WATCH"
    if status == "BELOW_STOP":
        return "A-CHALLENGED"
    return "A-WATCH"


def default_state(entry: dict[str, Any]) -> tuple[str, str, str]:
    legacy_tier = str(entry.get("tier") or "C").upper()
    monitoring_role = str(entry.get("monitoring_role") or "")
    coverage = as_dict(entry.get("coverage_reason"))
    workflow_state = str(coverage.get("workflow_state") or "")
    if legacy_tier == "A":
        return "Tier A", "A-WATCH", "legacy_tier_a_preserved_pending_auto_router_evidence"
    if legacy_tier == "B":
        return "Tier B", "B-CANDIDATE", "legacy_tier_b_preserved_pending_auto_router_evidence"
    if "repair" in monitoring_role.lower() or workflow_state.upper() == "REPAIR":
        return "Tier C", "C-REPAIR", "legacy_or_card_repair_state"
    return "Tier C", "C-MONITOR", "default_breadth_monitor"


def route_entry(
    entry: dict[str, Any],
    tier_a_rows: dict[str, dict[str, Any]],
    tier_a_gate_rows: dict[str, dict[str, Any]],
    approved_b: set[str],
    held_b_candidates: set[str],
    tier_c_attention: dict[str, dict[str, Any]],
    adjudication_buckets: dict[str, str],
    confidence_by_ticker: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    ticker = str(entry.get("ticker") or "").upper()
    auto_tier, auto_state, reason = default_state(entry)
    route_priority = 50
    blocks_capital = True
    if ticker in tier_a_rows:
        packet_row = tier_a_rows[ticker]
        if packet_row.get("decision_status") in {"eligible_for_auto_tier_a_routing", "eligible_for_owner_tier_a_label_decision"}:
            auto_tier = "Tier A"
            auto_state = band_status_to_tier_a_state(packet_row)
            reason = "auto_admitted_from_tier_a_final_packet_under_non_capital_routing_authority"
            route_priority = 10
    elif ticker in tier_a_gate_rows:
        auto_tier = "Tier A"
        auto_state = "A-WATCH"
        reason = "auto_promoted_from_b_to_a_competitive_gate_under_non_capital_routing_authority"
        route_priority = 15
    elif ticker in approved_b:
        auto_tier = "Tier B"
        auto_state = "B-VALIDATED" if adjudication_buckets.get(ticker) == "B_RESEARCH" else "B-CANDIDATE"
        reason = "auto_research_bench_from_recorded_or_previewed_tier_b_label"
        route_priority = 20
    elif ticker in held_b_candidates:
        auto_tier = "Tier C"
        auto_state = "C-CANDIDATE-HOLD"
        reason = "phase2_eligible_but_auto_router_holds_for_quality_capacity_or_caution_burden"
        route_priority = 30
    elif ticker in tier_c_attention:
        attention_row = tier_c_attention[ticker]
        auto_tier = "Tier C"
        auto_state = str(attention_row.get("attention_state") or "C-CANDIDATE")
        reason = "tier_c_attention_triggered_by_momentum_fundamentals_and_repair_burden"
        route_priority = 35
    elif adjudication_buckets.get(ticker) == "A_REPAIR":
        auto_tier = "Tier A"
        auto_state = "A-CHALLENGED"
        reason = "production_adjudication_tier_a_repair_watchlist_candidate"
        route_priority = 40
    confidence = confidence_by_ticker.get(ticker, {})
    confidence_effect = confidence.get("promotion_effect")
    if auto_tier == "Tier A":
        critical_conflicts = int(confidence.get("critical_conflict_count") or 0)
        if confidence_effect == "block_tier_a_promotion" or critical_conflicts > 0:
            auto_tier = "Tier B"
            auto_state = "B-CHALLENGED"
            route_priority = max(route_priority, 25)
            reason = f"{reason}; auto_demoted_a_to_b_by_tier_a_confidence_gate_{confidence_effect or 'critical_data_conflict'}"
        elif confidence_effect == "force_a_challenged":
            auto_state = "A-CHALLENGED"
            reason = f"{reason}; tier_a_confidence_gate_{confidence_effect}"
        elif not confidence and TIER_A_CONFIDENCE_GATE.exists():
            auto_state = "A-CHALLENGED"
            reason = f"{reason}; missing_tier_a_confidence_row"
    return {
        "ticker": ticker,
        "name": entry.get("name"),
        "sector": entry.get("sector"),
        "instrument_type": entry.get("instrument_type"),
        "legacy_universe_tier": entry.get("tier"),
        "legacy_monitoring_role": entry.get("monitoring_role"),
        "auto_tier": auto_tier,
        "auto_state": auto_state,
        "route_reason": reason,
        "route_priority": route_priority,
        "data_confidence_rating": confidence.get("data_confidence_rating"),
        "fundamentals_confidence": confidence.get("fundamentals_confidence"),
        "tier_a_confidence_status": confidence.get("tier_a_confidence_status"),
        "tier_a_confidence_promotion_effect": confidence_effect,
        "tier_a_confidence_source": "artifact" if confidence else None,
        "critical_data_conflict_count": confidence.get("critical_conflict_count"),
        "tier_c_attention_score": as_dict(tier_c_attention.get(ticker)).get("attention_score"),
        "tier_c_attention_next_action": as_dict(tier_c_attention.get(ticker)).get("recommended_next_action"),
        "capital_deployment_approved": False,
        "trade_or_execution_approved": False,
        "requires_separate_capital_or_execution_approval": blocks_capital,
        "would_mutate_universe": False,
    }


def build_report() -> dict[str, Any]:
    universe = load_dict(UNIVERSE)
    tier_a_packet = load_dict(TIER_A_PACKET)
    sync_preview = load_dict(TIER_B_SYNC_PREVIEW)
    tier_b_packet_3 = load_dict(TIER_B_PACKET_3)
    tier_b_phase2_eval = load_dict(TIER_B_PHASE2_EVAL)
    tier_a_competitive_gate = load_dict(TIER_A_COMPETITIVE_GATE)
    adjudication = load_dict(PRODUCTION_ADJUDICATION)
    confidence_gate = load_dict(TIER_A_CONFIDENCE_GATE)
    attention_trigger = load_dict(TIER_C_ATTENTION_TRIGGER)
    entries = universe_entries(universe)
    tier_a_rows = packet_rows(tier_a_packet)
    tier_a_gate_candidates = eligible_tier_a_from_competitive_gate(tier_a_competitive_gate)
    tier_a_gate_rows, tier_a_gate_capacity_held = apply_tier_a_capacity(tier_a_rows, tier_a_gate_candidates)
    phase2_b_eligible = eligible_tier_b_from_phase2_eval(tier_b_phase2_eval)
    approved_b = approved_tier_b(sync_preview)
    # Phase 2 eligibility is evidence-gate proof, not a durable Tier B label.
    # Hold eligible rows until the bounded C-to-B pipeline/register path admits
    # them, so quote refreshes cannot push the router over the Tier B cap.
    held_b = (open_tier_b_hold_set(tier_b_packet_3) | phase2_b_eligible) - approved_b - set(tier_a_gate_rows)
    tier_c_attention = tier_c_attention_rows(attention_trigger)
    adjudication_buckets = adjudication_bucket_map(adjudication)
    confidence_by_ticker = confidence_rows(confidence_gate)
    rows = [
        route_entry(
            entry,
            tier_a_rows,
            tier_a_gate_rows,
            approved_b,
            held_b,
            tier_c_attention,
            adjudication_buckets,
            confidence_by_ticker,
        )
        for entry in entries
    ]
    rows, confidence_by_ticker, inline_confidence_tickers = converge_missing_tier_a_confidence(rows, confidence_by_ticker)
    rows, tier_a_capacity_demoted_tickers = enforce_tier_a_row_cap(rows)
    rows.sort(key=lambda row: (row["route_priority"], row["auto_tier"], row["auto_state"], row["ticker"]))

    tier_counts = Counter(row["auto_tier"] for row in rows)
    state_counts = Counter(row["auto_state"] for row in rows)
    auto_tier_a = sorted(row["ticker"] for row in rows if row["auto_tier"] == "Tier A")
    auto_tier_b = sorted(row["ticker"] for row in rows if row["auto_tier"] == "Tier B")
    held = sorted(row["ticker"] for row in rows if row["auto_state"] == "C-CANDIDATE-HOLD")
    tier_a_missing_confidence = sorted(row["ticker"] for row in rows if row["auto_tier"] == "Tier A" and not row.get("tier_a_confidence_promotion_effect"))
    tier_a_conflicted_ready = sorted(
        row["ticker"] for row in rows
        if row["auto_state"] == "A-READY" and int(row.get("critical_data_conflict_count") or 0) > 0
    )
    active_attention = sorted(row["ticker"] for row in rows if row.get("tier_c_attention_score") is not None and row["auto_tier"] == "Tier C")

    checks: list[dict[str, Any]] = []
    add_check(checks, "universe_present", bool(universe), rel(UNIVERSE))
    add_check(checks, "active_universe_rows_present", bool(entries), len(entries))
    add_check(checks, "tier_a_packet_present", bool(tier_a_packet), rel(TIER_A_PACKET))
    add_check(checks, "tier_a_packet_validation_ok", as_dict(tier_a_packet.get("validation")).get("status") == "ok", as_dict(tier_a_packet.get("validation")).get("status"))
    add_check(checks, "tier_b_sync_preview_present", bool(sync_preview), rel(TIER_B_SYNC_PREVIEW))
    add_check(checks, "tier_b_sync_preview_validation_ok", as_dict(sync_preview.get("validation")).get("status") == "ok", as_dict(sync_preview.get("validation")).get("status"))
    add_check(checks, "tier_b_phase2_eval_present", bool(tier_b_phase2_eval), rel(TIER_B_PHASE2_EVAL), "warning")
    add_check(checks, "tier_b_phase2_eval_validation_ok_if_present", (not tier_b_phase2_eval) or as_dict(tier_b_phase2_eval.get("validation")).get("status") == "ok", as_dict(tier_b_phase2_eval.get("validation")).get("status"), "warning")
    add_check(checks, "tier_a_competitive_gate_present", bool(tier_a_competitive_gate), rel(TIER_A_COMPETITIVE_GATE), "warning")
    add_check(checks, "tier_a_competitive_gate_validation_ok_if_present", (not tier_a_competitive_gate) or as_dict(tier_a_competitive_gate.get("validation")).get("status") == "ok", as_dict(tier_a_competitive_gate.get("validation")).get("status"), "warning")
    add_check(checks, "production_adjudication_present", bool(adjudication), rel(PRODUCTION_ADJUDICATION))
    add_check(checks, "production_adjudication_validation_ok", as_dict(adjudication.get("validation")).get("status") == "ok", as_dict(adjudication.get("validation")).get("status"))
    add_check(checks, "tier_a_confidence_gate_present", bool(confidence_gate), rel(TIER_A_CONFIDENCE_GATE))
    add_check(checks, "tier_a_confidence_gate_validation_ok", as_dict(confidence_gate.get("validation")).get("status") == "ok", as_dict(confidence_gate.get("validation")).get("status"))
    add_check(checks, "tier_c_attention_trigger_present", bool(attention_trigger), rel(TIER_C_ATTENTION_TRIGGER), "warning")
    add_check(checks, "tier_c_attention_trigger_validation_ok_if_present", (not attention_trigger) or as_dict(attention_trigger.get("validation")).get("status") == "ok", as_dict(attention_trigger.get("validation")).get("status"), "warning")
    add_check(checks, "auto_tier_a_within_cap", len(auto_tier_a) <= TIER_A_CAP, {"count": len(auto_tier_a), "cap": TIER_A_CAP})
    add_check(checks, "auto_tier_b_within_cap", len(auto_tier_b) <= TIER_B_CAP, {"count": len(auto_tier_b), "cap": TIER_B_CAP})
    add_check(checks, "auto_tier_a_b_within_combined_cap", len(auto_tier_a) + len(auto_tier_b) <= COMBINED_CAP, {"count": len(auto_tier_a) + len(auto_tier_b), "cap": COMBINED_CAP})
    add_check(checks, "no_capital_deployment_approved", all(row["capital_deployment_approved"] is False for row in rows), None)
    add_check(checks, "no_trade_or_execution_approved", all(row["trade_or_execution_approved"] is False for row in rows), None)
    add_check(checks, "no_universe_mutation", all(row["would_mutate_universe"] is False for row in rows), None)
    add_check(checks, "tier_a_confidence_rows_complete", not tier_a_missing_confidence, tier_a_missing_confidence)
    add_check(checks, "no_a_ready_with_critical_data_conflicts", not tier_a_conflicted_ready, tier_a_conflicted_ready)
    for flag in REQUIRED_TRUE_FLAGS:
        add_check(checks, f"authority_{flag}_true", AUTHORITY_BOUNDARY.get(flag) is True, AUTHORITY_BOUNDARY.get(flag))
    for flag in REQUIRED_FALSE_FLAGS:
        add_check(checks, f"authority_{flag}_false", AUTHORITY_BOUNDARY.get(flag) is False, AUTHORITY_BOUNDARY.get(flag))

    errors = [check for check in checks if check["severity"] == "critical" and not check["ok"]]
    return {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "ok" if not errors else "blocked",
        "workflow": "WF78 - Automated Non-Capital Tier Router",
        "purpose": "Automatically classify ticker tier/routing states while preserving the hard capital-deployment and execution approval boundary.",
        "owner_routing_authority_reference": OWNER_ROUTING_AUTHORITY_REFERENCE,
        "authority_boundary": AUTHORITY_BOUNDARY,
        "source_artifacts": {
            "universe": rel(UNIVERSE),
            "tier_a_final_packet": rel(TIER_A_PACKET),
            "tier_b_label_sync_preview": rel(TIER_B_SYNC_PREVIEW),
            "tier_b_hold_packet": rel(TIER_B_PACKET_3),
            "tier_b_phase2_eval": rel(TIER_B_PHASE2_EVAL),
            "tier_a_competitive_gate": rel(TIER_A_COMPETITIVE_GATE),
            "production_adjudication": rel(PRODUCTION_ADJUDICATION),
            "tier_a_confidence_gate": rel(TIER_A_CONFIDENCE_GATE),
            "tier_c_attention_trigger": rel(TIER_C_ATTENTION_TRIGGER),
        },
        "summary": {
            "active_ticker_count": len(rows),
            "auto_tier_counts": dict(sorted(tier_counts.items())),
            "auto_state_counts": dict(sorted(state_counts.items())),
            "auto_tier_a_count": len(auto_tier_a),
            "auto_tier_a_tickers": auto_tier_a,
            "auto_tier_b_count": len(auto_tier_b),
            "auto_tier_b_tickers": auto_tier_b,
            "held_phase2_b_candidates_count": len(held),
            "held_phase2_b_candidates": held,
            "phase2_auto_tier_b_candidate_count": 0,
            "phase2_auto_tier_b_candidates": [],
            "phase2_eligible_c_to_b_candidate_count": len(phase2_b_eligible),
            "phase2_eligible_c_to_b_candidates": sorted(phase2_b_eligible),
            "competitive_gate_auto_tier_a_candidate_count": len(tier_a_gate_rows),
            "competitive_gate_auto_tier_a_candidates": sorted(tier_a_gate_rows),
            "competitive_gate_auto_tier_a_capacity_held_count": len(tier_a_gate_capacity_held),
            "competitive_gate_auto_tier_a_capacity_held": tier_a_gate_capacity_held,
            "auto_tier_a_capacity_demoted_count": len(tier_a_capacity_demoted_tickers),
            "auto_tier_a_capacity_demoted_tickers": tier_a_capacity_demoted_tickers,
            "tier_a_missing_confidence_count": len(tier_a_missing_confidence),
            "tier_a_missing_confidence_tickers": tier_a_missing_confidence,
            "tier_a_conflicted_ready_count": len(tier_a_conflicted_ready),
            "tier_a_conflicted_ready_tickers": tier_a_conflicted_ready,
            "inline_confidence_convergence_count": len(inline_confidence_tickers),
            "inline_confidence_convergence_tickers": inline_confidence_tickers,
            "tier_c_attention_candidate_count": len(active_attention),
            "tier_c_attention_candidates": active_attention,
            "capital_deployment_approved_count": 0,
            "trade_or_execution_approved_count": 0,
            "next_safe_action": "Use this artifact as the live non-capital routing state; capital deployment and execution still require separate exact approval.",
        },
        "rows": rows,
        "validation": {
            "status": "ok" if not errors else "error",
            "errors": errors,
            "warnings": [],
            "checks": checks,
        },
        "stop_lines": [
            "Automated routing state does not approve capital deployment.",
            "Automated routing state does not approve paper/live orders or brokerage/account actions.",
            "This artifact does not mutate universe, canon, portfolio, ticker-card, or SQL canon surfaces.",
            "A-READY means decision-grade and in/near evidence posture, not order approval.",
            "A-READY also requires a current Tier A confidence gate row with no critical data conflicts.",
            "B-CANDIDATE/B-VALIDATED means research bench, not deployment readiness.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    report = build_report()
    out = args.out if args.out.is_absolute() else ROOT / args.out
    if args.write:
        atomic_write_json(out, report)
    print(
        json.dumps(
            {
                "status": report.get("status"),
                "out": rel(out),
                "summary": report.get("summary"),
                "validation": {
                    "status": as_dict(report.get("validation")).get("status"),
                    "errors": len(as_list(as_dict(report.get("validation")).get("errors"))),
                },
            },
            indent=2,
        )
    )
    if args.validate and as_dict(report.get("validation")).get("status") != "ok":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
