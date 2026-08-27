#!/usr/bin/env python3
"""Build a compact WF84/WF85/WF86 trade-grade OS readiness rollup.

The rollup is a review-only command surface. It clarifies answer readiness,
approval-card eligibility, execution gating, WF86 bridge state, and the current
Telegram owner-approval posture without granting approval or execution.
"""
from __future__ import annotations

import argparse
import json
import os
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, load_json_artifact


ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
OUT = TMP / "trade-grade-os-readiness-rollup.json"

SCHEMA = "veritas.trade_grade_os_readiness_rollup.v1"
APPROVED_TELEGRAM_OWNER = "telegram:8650152206"
APPROVED_OWNER_NAME = "Randall"

DECISION_SLICE_TIERS = ("Tier A", "Tier B")
DECISION_READY_RATIO = 0.8

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "decision_support_only": True,
    "manual_paper_approval_surface": True,
    "automated_non_capital_routing_allowed": True,
    "approval_or_execution_granted_by_rollup": False,
    "capital_deployment_approved": False,
    "trade_or_execution_approved": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "money_movement_allowed": False,
    "canon_or_portfolio_mutation_allowed": False,
    "cash_sizing_or_risk_rule_mutation_allowed": False,
    "customer_or_external_delivery_allowed": False,
    "owner_approval_inferred": False,
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


def load(path: Path) -> dict[str, Any]:
    value = load_json_artifact(path)
    return value if isinstance(value, dict) else {}


def int_or_zero(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def find_key(root: Any, key: str) -> list[Any]:
    found: list[Any] = []
    if isinstance(root, dict):
        for item_key, item_value in root.items():
            if item_key == key:
                found.append(item_value)
            found.extend(find_key(item_value, key))
    elif isinstance(root, list):
        for item in root:
            found.extend(find_key(item, key))
    return found


def owner_allow_from() -> list[str]:
    config = Path(os.path.expanduser("~")) / ".openclaw" / "openclaw.json"
    if not config.exists():
        return []
    try:
        data = json.loads(config.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    values: list[str] = []
    for item in find_key(data, "ownerAllowFrom"):
        if isinstance(item, list):
            values.extend(str(value) for value in item)
    return sorted(set(values))


def latest_exact_approval_artifacts() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in sorted((TMP / "alpaca-paper-readiness").glob("owner-approval*.json")):
        payload = load(path)
        if payload.get("approved_by") == APPROVED_OWNER_NAME:
            rows.append(
                {
                    "path": rel(path),
                    "approval_status": payload.get("approval_status"),
                    "approved_by": payload.get("approved_by"),
                    "source_context": payload.get("source_context"),
                    "approved_order": payload.get("approved_order"),
                }
            )
    return rows


def wf85_semantic_rollup(cards_payload: dict[str, Any], approval_gate: dict[str, Any], full_answer: dict[str, Any]) -> dict[str, Any]:
    cards = as_list(cards_payload.get("cards"))
    decision_counts = Counter(str(card.get("decision_state")) for card in cards)
    full_answer_summary = as_dict(full_answer.get("summary"))
    approval_summary = as_dict(approval_gate.get("summary"))

    answer_ready_count = int_or_zero(full_answer_summary.get("full_answer_built_count")) or len(cards)
    review_only_ready_count = int_or_zero(approval_summary.get("review_ready_count"))
    approval_eligible_count = int_or_zero(approval_summary.get("approval_card_draft_count"))
    approval_blocked_count = int_or_zero(approval_summary.get("approval_draft_blocked_count"))
    execution_gated_count = approval_eligible_count + approval_blocked_count

    return {
        "answer_ready_count": answer_ready_count,
        "review_only_decision_ready_count": review_only_ready_count,
        "approval_card_eligible_count": approval_eligible_count,
        "approval_card_blocked_valid_reason_count": approval_blocked_count,
        "execution_gated_count": execution_gated_count,
        "decision_state_counts": dict(decision_counts),
        "blocked_count_semantics": "approval_draft_blocked_count_not_system_failure",
        "plain_english": {
            "answer_ready": "Ticker answer/full-answer artifact exists and can be used for review-only intelligence.",
            "review_only_decision_ready": "Card is suitable for human review, but not approval or execution.",
            "approval_card_eligible": "Draft approval card may be prepared; Randall exact approval is still required.",
            "approval_card_blocked_valid_reason": "The OS is correctly blocking approval-card promotion due to freshness, band, source, posture, or guard limits.",
            "execution_gated": "Any paper action remains gated by WF67, fresh kill switch, exact approval, redacted audit, and reconciliation.",
        },
    }


def wf86_bridge_rollup(
    shadow: dict[str, Any],
    assisted: dict[str, Any],
    execution_result: dict[str, Any],
    reconciliation: dict[str, Any],
    order_history: dict[str, Any] | None = None,
) -> dict[str, Any]:
    decisions = as_list(shadow.get("decisions"))
    assisted_cards = as_list(assisted.get("cards"))
    shadow_only = [d for d in decisions if d.get("shadow_eligible") and not d.get("assisted_review_ready")]
    assisted_eligible = [d for d in decisions if d.get("assisted_review_ready")]
    exact_approval_required = [
        card for card in assisted_cards
        if card.get("owner_approval_status") not in {"approved_exact_order", "approved_final_submit"}
    ]
    guard_ready_not_approved = [
        card for card in assisted_cards
        if card.get("wf67_guard_status") == "ok"
        and card.get("wf67_ready_for_paper_submit_cancel") is True
        and card.get("owner_approval_status") != "approved_exact_order"
    ]
    fill_reconciled = []
    terminal_non_fill = []
    positions = as_list(reconciliation.get("positions")) or as_list(as_dict(reconciliation.get("snapshot")).get("positions"))
    execution_ticker = str(as_dict(execution_result.get("request_summary")).get("symbol") or "VRT").upper()
    position_observed = any(str(row.get("symbol") or "").upper() == execution_ticker for row in positions)
    open_orders_count = int_or_zero(as_dict(reconciliation.get("summary")).get("open_orders_count"))
    submitted_open = []
    unresolved_after_reconciliation = []
    order_history_payload = order_history or {}
    order_history_classifications = as_list(order_history_payload.get("classifications"))
    if order_history_classifications:
        for row in order_history_classifications:
            classification = str(as_dict(row).get("classification") or "unresolved")
            ticker = str(as_dict(row).get("symbol") or "").upper()
            record = {
                "ticker": ticker,
                "source_path": as_dict(row).get("source_path"),
                "status": classification,
                "evidence": as_dict(row).get("evidence"),
                "next_safe_action": as_dict(row).get("next_safe_action"),
            }
            if classification in {"filled", "partially_filled", "filled_position_observed_unmatched_order_history"}:
                fill_reconciled.append(record)
            elif classification == "open_or_pending":
                submitted_open.append(record)
            elif classification in {"expired", "canceled", "rejected", "replaced", "terminal_other"}:
                terminal_non_fill.append(record)
            else:
                unresolved_after_reconciliation.append(record)
    elif execution_result.get("status") == "submitted":
        if position_observed:
            fill_reconciled.append({"ticker": execution_ticker, "status": "position_observed"})
        elif open_orders_count > 0:
            submitted_open.append(
                {
                    "ticker": execution_ticker,
                    "result_path": "tmp/alpaca-paper-readiness/paper-execution-result.vrt-wf86-assisted-approved.json",
                    "status": "submitted_open_or_pending_until_fill_reconciliation",
                    "open_orders_count": open_orders_count,
                }
            )
        else:
            unresolved_after_reconciliation.append(
                {
                    "ticker": execution_ticker,
                    "result_path": "tmp/alpaca-paper-readiness/paper-execution-result.vrt-wf86-assisted-approved.json",
                    "status": "submitted_result_but_no_open_order_or_position_observed",
                    "next_safe_action": "Drill into GET-only order-history detail before classifying as filled, expired, canceled, or rejected.",
                }
            )

    return {
        "shadow_only_count": len(shadow_only),
        "shadow_only_tickers": [row.get("ticker") for row in shadow_only],
        "assisted_paper_eligible_count": len(assisted_eligible),
        "assisted_paper_eligible_tickers": [row.get("ticker") for row in assisted_eligible],
        "exact_approval_required_count": len(exact_approval_required),
        "guard_ready_but_not_approved_count": len(guard_ready_not_approved),
        "submitted_open_count": len(submitted_open),
        "submitted_open": submitted_open,
        "fill_reconciled_count": len(fill_reconciled),
        "fill_reconciled": fill_reconciled,
        "terminal_non_fill_count": len(terminal_non_fill),
        "terminal_non_fill": terminal_non_fill,
        "unresolved_after_reconciliation_count": len(unresolved_after_reconciliation),
        "unresolved_after_reconciliation": unresolved_after_reconciliation,
        "order_history_classifier_status": order_history_payload.get("status"),
        "order_history_classifier_validation_status": as_dict(order_history_payload.get("validation")).get("status"),
        "order_history_classifier_summary": as_dict(order_history_payload.get("summary")),
        "autonomous_threshold": as_dict(shadow.get("summary")),
        "bridge_labels": [
            "shadow_only_candidate",
            "assisted_paper_eligible",
            "exact_approval_required",
            "guard_ready_not_approved",
            "submitted_open",
            "fill_reconciled",
            "terminal_non_fill",
            "unresolved_after_reconciliation",
        ],
    }


def telegram_approval_rollup() -> dict[str, Any]:
    allow_from = owner_allow_from()
    exact_approvals = latest_exact_approval_artifacts()
    pilot = load(TMP / "paper-autotrader" / "autonomous-pilot-approval.json")
    return {
        "approved_owner": APPROVED_OWNER_NAME,
        "approved_telegram_owner": APPROVED_TELEGRAM_OWNER,
        "owner_allow_from_contains_telegram_owner": APPROVED_TELEGRAM_OWNER in allow_from,
        "owner_allow_from_redacted_count": len(allow_from),
        "manual_paper_execution_approvals_supported": APPROVED_TELEGRAM_OWNER in allow_from,
        "manual_approval_requirements": [
            "Telegram direct message must be from the approved owner identity.",
            "Approval text must scope the exact paper order terms.",
            "WF67 wrapper, paper endpoint, fresh kill switch, guard validation, redacted audit, and reconciliation remain required.",
        ],
        "latest_exact_order_approvals": exact_approvals[-5:],
        "autonomous_pilot_approval_status": pilot.get("status"),
        "autonomous_pilot_scope": pilot.get("scope"),
        "transition_posture": "manual_exact_approval_now_autonomous_pilot_later_after_threshold_and_reconciliation",
        "authority_boundary": {
            "telegram_approval_can_authorize_exact_paper_order_review": True,
            "telegram_approval_bypasses_wf67": False,
            "telegram_approval_authorizes_live_trading": False,
            "owner_approval_inferred": False,
        },
    }


def trade_grade_data_readiness_rollup(
    ticker_freshness_ledger: dict[str, Any],
    tier_weighted: dict[str, Any],
) -> dict[str, Any]:
    """Measure decision readiness on the Tier A/B slice only.

    Tier C rows are monitor-grade by contract (decision_grade_entry_stop_allowed
    is false), so scoring them against a decision-readiness threshold produced a
    verdict that could never clear on the flat ledger and one that read green on
    the tier-weighted count. The decision slice is the only honest denominator.
    """
    ledger_summary = as_dict(ticker_freshness_ledger.get("summary"))
    counts = as_dict(ledger_summary.get("freshness_state_counts"))
    universe_count = int_or_zero(ledger_summary.get("ticker_count"))
    raw_true_fresh_count = int_or_zero(counts.get("fresh"))

    slice_rows = [
        row
        for row in (as_dict(item) for item in as_list(tier_weighted.get("rows")))
        if str(row.get("auto_tier") or "").strip() in DECISION_SLICE_TIERS
    ]
    slice_count = len(slice_rows)
    resolved_count = sum(1 for row in slice_rows if row.get("tier_weighted_resolved") is True)
    unresolved_tickers = sorted(
        str(row.get("ticker") or "").strip().upper()
        for row in slice_rows
        if row.get("tier_weighted_resolved") is not True and str(row.get("ticker") or "").strip()
    )
    threshold = max(1, int(slice_count * DECISION_READY_RATIO)) if slice_count else 0
    source_ok = tier_weighted.get("status") == "ok"
    ready = bool(source_ok and slice_count and resolved_count >= threshold)

    if not source_ok:
        reason = "tier_weighted_resolution_not_ok"
    elif not slice_count:
        reason = "decision_slice_empty"
    elif ready:
        reason = "tier_a_b_resolved_count_meets_threshold"
    else:
        reason = "tier_a_b_resolved_count_below_threshold"

    return {
        "status": "data_ready" if ready else "data_not_ready",
        "ready_for_trade_grade_decisions": ready,
        "readiness_basis": "tier_a_b_decision_slice",
        "reason": reason,
        "decision_slice_tiers": list(DECISION_SLICE_TIERS),
        "decision_slice_ticker_count": slice_count,
        "decision_slice_resolved_count": resolved_count,
        "decision_slice_threshold": threshold,
        "decision_slice_ratio": round(resolved_count / slice_count, 4) if slice_count else None,
        "decision_slice_unresolved_count": slice_count - resolved_count,
        "decision_slice_unresolved_tickers": unresolved_tickers,
        "universe_reference": {
            "ticker_count": universe_count,
            "raw_true_fresh_ticker_count": raw_true_fresh_count,
            "raw_true_fresh_ratio": (
                round(raw_true_fresh_count / universe_count, 4) if universe_count else None
            ),
            "freshness_state_counts": counts,
            "top_stale_families": as_list(ledger_summary.get("top_stale_families")),
            "note": (
                "Full-universe flat freshness is reference only; Tier C rows are monitor-grade "
                "and are never decision-grade evidence."
            ),
        },
        "source_artifacts": [
            "tmp/wf78-tier-weighted-freshness-resolution.json",
            "tmp/wf78-ticker-freshness-ledger.json",
        ],
        "disclosure_rule": "Do not describe WF84/WF85 as decision-data-ready unless this status is data_ready.",
    }


def decision_depth_rollup(
    cards_payload: dict[str, Any],
    full_answer: dict[str, Any],
    tier_weighted: dict[str, Any],
    repair_conveyor: dict[str, Any],
    approval_gate: dict[str, Any],
) -> dict[str, Any]:
    """Separate structural coverage from current decision-grade evidence depth."""
    cards_by_ticker = {
        str(as_dict(card).get("ticker") or "").upper(): as_dict(card)
        for card in as_list(cards_payload.get("cards"))
        if str(as_dict(card).get("ticker") or "").strip()
    }
    answers_by_ticker = {
        str(as_dict(result).get("ticker") or as_dict(result).get("symbol") or "").upper(): as_dict(result)
        for result in as_list(full_answer.get("results"))
        if str(as_dict(result).get("ticker") or as_dict(result).get("symbol") or "").strip()
    }
    tier_by_ticker = {
        str(as_dict(row).get("ticker") or "").upper(): as_dict(row)
        for row in as_list(tier_weighted.get("rows"))
        if str(as_dict(row).get("ticker") or "").strip()
    }
    repair_by_ticker = {
        str(as_dict(row).get("ticker") or "").upper(): as_dict(row)
        for row in as_list(repair_conveyor.get("rows"))
        if str(as_dict(row).get("ticker") or "").strip()
    }
    approval_drafts = {
        str(as_dict(row).get("ticker") or "").upper()
        for row in as_list(approval_gate.get("approval_card_drafts"))
        if str(as_dict(row).get("ticker") or "").strip()
    }
    approval_authority = as_dict(approval_gate.get("authority_boundary"))
    approval_authority_fail_closed = bool(
        approval_authority.get("review_only") is True
        and approval_authority.get("decision_support_only") is True
        and approval_authority.get("approval_card_draft_allowed") is True
        and all(
            approval_authority.get(key) is False
            for key in (
            "capital_deployment_approved",
            "trade_or_execution_approved",
            "paper_or_live_execution_allowed",
            "brokerage_or_account_action_allowed",
            "money_movement_allowed",
            "customer_or_external_delivery_allowed",
            "canon_or_portfolio_mutation_allowed",
            "cash_sizing_or_risk_rule_mutation_allowed",
            "customer_account_pii_or_suitability_data_allowed",
            "owner_approval_inferred",
            )
        )
    )
    tickers = sorted(
        set(cards_by_ticker)
        | set(answers_by_ticker)
        | set(tier_by_ticker)
        | set(repair_by_ticker)
        | approval_drafts
    )
    rows: list[dict[str, Any]] = []
    tier_a_b_repair_needed_count = 0
    for symbol in tickers:
        card = cards_by_ticker.get(symbol, {})
        tier = tier_by_ticker.get(symbol, {})
        repair = repair_by_ticker.get(symbol, {})
        auto_tier = tier.get("auto_tier") or card.get("auto_tier") or repair.get("auto_tier")
        stale_families = [str(item) for item in as_list(tier.get("stale_families"))]
        decision_state = card.get("decision_state")
        repair_lane = repair.get("repair_lane")
        source_open_status = repair.get("source_open_status")
        freshness_status = repair.get("freshness_status")
        resolution_state = tier.get("resolution_state")

        approval_card_draft_candidate = symbol in approval_drafts and approval_authority_fail_closed
        # A draft is review-only. This compiler never infers exact owner
        # approval; any future owner state needs a separate owner-gated proof.
        owner_card_candidate = False
        review_card_candidate = (
            repair_lane == "fresh_quote_review_ready_pilot_candidate"
            or decision_state == "review_ready"
        )
        fresh_decision_context = bool(
            resolution_state == "fresh"
            and not stale_families
            and source_open_status == "verified"
            and freshness_status == "fresh"
        )
        thin_monitor = bool(
            auto_tier in {"C", "Tier C"}
            and resolution_state == "resolved_thin_monitor_current"
        )
        coverage_floor = bool(card or answers_by_ticker.get(symbol))

        if approval_card_draft_candidate:
            depth_state = "approval_card_draft_candidate"
        elif review_card_candidate:
            depth_state = "review_card_candidate"
        elif fresh_decision_context:
            depth_state = "fresh_decision_context"
        elif thin_monitor:
            depth_state = "thin_monitor"
        elif coverage_floor:
            depth_state = "coverage_floor"
        else:
            depth_state = "blocked"

        if auto_tier in {"A", "B", "Tier A", "Tier B"} and depth_state in {"coverage_floor", "blocked"}:
            tier_a_b_repair_needed_count += 1

        rows.append(
            {
                "ticker": symbol,
                "auto_tier": auto_tier,
                "depth_state": depth_state,
                "coverage_floor": coverage_floor,
                "thin_monitor": thin_monitor,
                "fresh_decision_context": fresh_decision_context,
                "review_card_candidate": review_card_candidate,
                "approval_card_draft_candidate": approval_card_draft_candidate,
                "owner_card_candidate": owner_card_candidate,
                "stale_families": stale_families,
                "repair_lane": repair_lane,
                "decision_state": decision_state,
                "source_open_status": source_open_status,
                "freshness_status": freshness_status,
            }
        )

    depth_state_counts = dict(Counter(str(row["depth_state"]) for row in rows))
    decision_grade_count = sum(
        depth_state_counts.get(state, 0)
        for state in ("fresh_decision_context",)
    )
    review_pipeline_candidate_count = sum(
        depth_state_counts.get(state, 0)
        for state in ("review_card_candidate", "approval_card_draft_candidate")
    )
    return {
        "rows": rows,
        "summary": {
            "ticker_count": len(rows),
            "depth_state_counts": depth_state_counts,
            "coverage_floor_count": sum(1 for row in rows if row["coverage_floor"]),
            "coverage_only_count": depth_state_counts.get("coverage_floor", 0),
            "thin_monitor_count": depth_state_counts.get("thin_monitor", 0),
            "fresh_decision_context_count": depth_state_counts.get("fresh_decision_context", 0),
            "review_card_candidate_count": depth_state_counts.get("review_card_candidate", 0),
            "approval_card_draft_candidate_count": depth_state_counts.get("approval_card_draft_candidate", 0),
            "owner_card_candidate_count": depth_state_counts.get("owner_card_candidate", 0),
            "review_pipeline_candidate_count": review_pipeline_candidate_count,
            "tier_a_b_repair_needed_count": tier_a_b_repair_needed_count,
            "production_or_decision_grade_count": decision_grade_count,
            "headline_state": (
                "decision_grade_depth_ready"
                if decision_grade_count
                else "coverage_only_no_decision_grade_depth"
            ),
            "next_safe_action": (
                "Use qualifying rows for review-only decision support; exact owner approval remains required."
                if decision_grade_count
                else "Repair source, freshness, and tier-resolution gaps before treating coverage as decision-grade depth."
            ),
        },
        "authority_boundary": {
            "review_only": True,
            "capital_deployment_approved": False,
            "trade_or_execution_approved": False,
            "customer_or_external_delivery_allowed": False,
            "canon_or_portfolio_mutation_allowed": False,
            "owner_approval_inferred": False,
        },
    }


def tier_a_b_guard_findings(tier_readiness: dict[str, Any]) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    validation_status = str(tier_readiness.get("validation_status") or "")
    stale_count = int_or_zero(tier_readiness.get("stale_complete_band_context_count"))
    if validation_status == "error":
        errors.append("tier_a_b_guard_validation_error")
    elif stale_count:
        if validation_status == "warning":
            warnings.append("tier_a_b_stale_complete_band_context_finance_domain_debt_present")
        else:
            errors.append("tier_a_b_stale_complete_band_context_count_nonzero")
    elif validation_status == "warning":
        warnings.append("tier_a_b_guard_finance_domain_debt_present")
    return errors, warnings


def build_payload() -> dict[str, Any]:
    wf84 = load(TMP / "canonical-finance-data-plane.json")
    wf84_phase = load(TMP / "canonical-finance-data-plane-phase6-10.json")
    cards = load(TMP / "trade-grade-decision-cards.json")
    approval_gate = load(TMP / "trade-grade-approval-card-gate.json")
    full_answer = load(TMP / "trade-grade-full-answer-assembler.json")
    tier_guard = load(TMP / "tier-ab-band-freshness-cron-guard.json")
    ticker_freshness_ledger = load(TMP / "wf78-ticker-freshness-ledger.json")
    tier_weighted = load(TMP / "wf78-tier-weighted-freshness-resolution.json")
    repair_conveyor = load(TMP / "trade-grade-repair-conveyor.json")
    shadow = load(TMP / "paper-autotrader" / "shadow-decisions.json")
    assisted = load(TMP / "paper-autotrader" / "assisted-order-cards.json")
    execution_result = load(TMP / "alpaca-paper-readiness" / "paper-execution-result.vrt-wf86-assisted-approved.json")
    reconciliation = load(TMP / "alpaca-paper-readiness" / "paper-order-reconciliation.vrt-wf86-assisted-approved.json")
    order_history = load(TMP / "alpaca-paper-readiness" / "paper-order-history-classifier.json")

    wf84_summary = as_dict(wf84.get("summary"))
    phase_summary = as_dict(wf84_phase.get("summary"))
    tier_summary = as_dict(tier_guard.get("summary"))
    approval_summary = as_dict(approval_gate.get("summary"))

    payload = {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "ok",
        "purpose": "Compact trade-grade OS readiness and manual paper-approval posture rollup.",
        "authority_boundary": AUTHORITY_BOUNDARY,
        "wf84_data_plane": {
            "status": wf84.get("status"),
            "phase6_10_status": wf84_phase.get("status"),
            "phase6_10_critical_error_count": phase_summary.get("critical_error_count"),
            "phase6_10_warning_count": phase_summary.get("warning_count"),
            "tier_counts": wf84_summary.get("tier_counts"),
            "forbidden_authority_true_count": wf84_summary.get("forbidden_authority_true_count"),
        },
        "wf85_decision_os": wf85_semantic_rollup(cards, approval_gate, full_answer),
        "trade_grade_data_readiness": trade_grade_data_readiness_rollup(
            ticker_freshness_ledger,
            tier_weighted,
        ),
        "decision_depth": decision_depth_rollup(
            cards,
            full_answer,
            tier_weighted,
            repair_conveyor,
            approval_gate,
        ),
        "tier_a_b_readiness": {
            "guard_status": tier_guard.get("status"),
            "validation_status": as_dict(tier_guard.get("validation")).get("status"),
            "complete_and_current_band_count": tier_summary.get("complete_and_current_count"),
            "stale_complete_band_context_count": tier_summary.get("stale_complete_band_context_count"),
            "cron_contracts_ok": tier_summary.get("cron_contracts_ok"),
        },
        "wf86_bridge": wf86_bridge_rollup(shadow, assisted, execution_result, reconciliation, order_history),
        "telegram_owner_approval": telegram_approval_rollup(),
        "next_recommended_actions": [
            "Use this rollup before deployment conversations.",
            "Keep WF85 answer-ready separate from approval-card eligibility.",
            "Keep Telegram approvals exact-order-only while autonomous paper remains threshold/reconciliation gated.",
            "Use WF86 bridge labels for shadow, assisted-paper, submitted-open, and fill-reconciled state.",
        ],
        "source_artifacts": {
            "wf84": "tmp/canonical-finance-data-plane.json",
            "wf84_phase6_10": "tmp/canonical-finance-data-plane-phase6-10.json",
            "wf85_cards": "tmp/trade-grade-decision-cards.json",
            "wf85_approval_gate": "tmp/trade-grade-approval-card-gate.json",
            "wf85_full_answer": "tmp/trade-grade-full-answer-assembler.json",
            "wf78_ticker_freshness_ledger": "tmp/wf78-ticker-freshness-ledger.json",
            "wf78_tier_weighted_freshness_resolution": "tmp/wf78-tier-weighted-freshness-resolution.json",
            "trade_grade_repair_conveyor": "tmp/trade-grade-repair-conveyor.json",
            "tier_ab_guard": "tmp/tier-ab-band-freshness-cron-guard.json",
            "wf86_shadow": "tmp/paper-autotrader/shadow-decisions.json",
            "wf86_assisted": "tmp/paper-autotrader/assisted-order-cards.json",
            "paper_order_history_classifier": "tmp/alpaca-paper-readiness/paper-order-history-classifier.json",
        },
        "validation": {"status": "ok", "errors": [], "warnings": []},
    }
    errors = payload["validation"]["errors"]
    warnings = payload["validation"]["warnings"]
    if wf84.get("status") != "ok":
        errors.append("wf84_data_plane_not_ok")
    if wf84_phase.get("status") != "ok":
        errors.append("wf84_phase6_10_not_ok")
    if cards.get("status") != "ok":
        errors.append("wf85_decision_cards_not_ok")
    if approval_gate.get("status") != "ok":
        errors.append("wf85_approval_gate_not_ok")
    if payload["telegram_owner_approval"]["owner_allow_from_contains_telegram_owner"] is not True:
        errors.append("approved_telegram_owner_not_in_owner_allow_from")
    if payload["wf84_data_plane"]["forbidden_authority_true_count"] not in {0, None}:
        errors.append("wf84_forbidden_authority_true_count_nonzero")
    tier_errors, tier_warnings = tier_a_b_guard_findings(payload["tier_a_b_readiness"])
    errors.extend(tier_errors)
    warnings.extend(tier_warnings)
    if payload["trade_grade_data_readiness"]["ready_for_trade_grade_decisions"] is not True:
        warnings.append(
            "trade_grade_data_not_ready:"
            f"{payload['trade_grade_data_readiness']['decision_slice_resolved_count']}/"
            f"{payload['trade_grade_data_readiness']['decision_slice_ticker_count']}"
            f"_tier_a_b_threshold_{payload['trade_grade_data_readiness']['decision_slice_threshold']}"
        )
    if payload["wf85_decision_os"]["approval_card_eligible_count"] > 0:
        warnings.append("approval_card_eligible_requires_exact_owner_approval_before_wf67_request")
    if payload["decision_depth"]["summary"]["production_or_decision_grade_count"] == 0:
        warnings.append("decision_grade_depth_empty")
    if errors:
        payload["status"] = "blocked"
        payload["validation"]["status"] = "error"
    elif warnings:
        payload["status"] = "warning"
        payload["validation"]["status"] = "warning"
    return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--out", type=Path, default=OUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    payload = build_payload()
    out = args.out if args.out.is_absolute() else ROOT / args.out
    if args.write:
        atomic_write_json(out, payload)
    print(
        "status={status} validation={validation} wf84={wf84} answer_ready={answer_ready} "
        "approval_eligible={approval_eligible} telegram_owner={telegram_owner} submitted_open={submitted_open}".format(
            status=payload["status"],
            validation=payload["validation"]["status"],
            wf84=payload["wf84_data_plane"]["status"],
            answer_ready=payload["wf85_decision_os"]["answer_ready_count"],
            approval_eligible=payload["wf85_decision_os"]["approval_card_eligible_count"],
            telegram_owner=payload["telegram_owner_approval"]["owner_allow_from_contains_telegram_owner"],
            submitted_open=payload["wf86_bridge"]["submitted_open_count"],
        )
    )
    if args.validate and payload["validation"]["status"] == "error":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
