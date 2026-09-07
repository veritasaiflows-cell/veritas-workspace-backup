#!/usr/bin/env python3
"""Shared review-only decision-state compiler for WF84/WF85.

This module is deliberately pure: it derives routing/review state from already
produced artifacts, but it does not read/write files, approve capital, submit
orders, or mutate portfolio/canon/account state.
"""
from __future__ import annotations

from typing import Any

# These immutable review-state sets are deliberately local.  Importing the
# retired trade-grade contract here turned a pure current-state compiler into
# an active reactivation edge, despite this module needing no contract I/O.
BLOCKING_PRIMARY_STATES = {
    "blocked_missing_freshness",
    "blocked_missing_source_open",
    "blocked_missing_band_or_stop",
    "blocked_wf67_guard_context",
    "below_stop_or_invalidation",
    "evidence_repair",
}

INVALIDATION_PRIMARY_STATES = {
    "below_stop_or_invalidation",
    "invalidation_review",
}

STATE_ORDER = [
    "below_stop_or_invalidation",
    "blocked_missing_freshness",
    "repair_mode",
    "promotion_vetoed",
    "in_band_not_clean",
    "entry_policy_review_required",
    "wf67_request_blocked",
    "approval_card_clean",
    "paper_request_ready_pending_exact_approval",
    "owner_card_preparable",
    "alert_only",
    "paper_position_monitor",
    "evidence_repair",
    "route_monitor",
]

PROMOTE_VERDICT = "promote_for_owner_review"
IN_BAND_HOLD_VERDICT = "in_band_review_hold"
ABOVE_BAND_VETO = "above band / no-chase"
BELOW_STOP_VETO = "below stop"
BAND_POSITION_VETOES = {ABOVE_BAND_VETO, BELOW_STOP_VETO}

ABOVE_BAND_STATES = {"ABOVE_BAND", "ABOVE_BAND_WAIT", "NO_CHASE"}
NO_CHASE_BAND_STATES = ABOVE_BAND_STATES
MISSING_BAND_STATES = {"UNKNOWN", "missing_required_refresh", None, ""}
APPROVAL_DRAFT_BAND_STATUS = "IN_BAND"
REVIEW_READY_PRIMARY_STATES = {"approval_card_clean", "owner_review_candidate", "route_monitor"}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def flag_true(value: Any) -> bool:
    return value in {1, True, "1", "true", "True", "yes", "YES"}


def thin_monitor_scope(membership: dict[str, Any]) -> bool:
    return (
        flag_true(membership.get("thin_monitor_row"))
        and not flag_true(membership.get("production_answer_path_member"))
        and not flag_true(membership.get("decision_grade_eligible"))
    )


def primary_state_from_states(states: set[str]) -> str:
    for state in STATE_ORDER:
        if state in states:
            return state
    return "route_monitor"


def state_for_promotion_gate_verdict(gate_verdict: str | None) -> str | None:
    if not gate_verdict or gate_verdict == PROMOTE_VERDICT:
        return None
    if gate_verdict == IN_BAND_HOLD_VERDICT:
        return "in_band_not_clean"
    return "promotion_vetoed"


def normalized_promotion_gate_fields(
    gate_verdict: str | None,
    gate_vetoes: Any,
    band_status: Any,
) -> dict[str, Any]:
    """Align stale promotion-gate position verdicts to current band context."""

    status = str(band_status or "").strip().upper()
    vetoes = [str(item).strip() for item in as_list(gate_vetoes) if str(item).strip()]
    original_verdict = gate_verdict
    original_vetoes = list(vetoes)
    warnings: list[str] = []

    if status in ABOVE_BAND_STATES:
        if ABOVE_BAND_VETO not in vetoes:
            vetoes.append(ABOVE_BAND_VETO)
        if gate_verdict in {None, "", PROMOTE_VERDICT, IN_BAND_HOLD_VERDICT}:
            gate_verdict = "defer_until_veto_clears"
    elif status == "BELOW_STOP":
        if BELOW_STOP_VETO not in vetoes:
            vetoes.append(BELOW_STOP_VETO)
        if gate_verdict in {None, "", PROMOTE_VERDICT, IN_BAND_HOLD_VERDICT, "defer_until_veto_clears"}:
            gate_verdict = "reject_currently"
    elif status == "IN_BAND":
        cleaned = [veto for veto in vetoes if veto not in BAND_POSITION_VETOES]
        if cleaned != vetoes:
            vetoes = cleaned
            if gate_verdict in {"defer_until_veto_clears", "reject_currently", "watch_for_reclaim_or_pullback"}:
                gate_verdict = "defer_until_veto_clears" if vetoes else IN_BAND_HOLD_VERDICT
    elif status in {"BELOW_BAND", "BELOW_BAND_WAIT"} and ABOVE_BAND_VETO in vetoes:
        vetoes = [veto for veto in vetoes if veto != ABOVE_BAND_VETO]
        if gate_verdict == "defer_until_veto_clears" and not vetoes:
            gate_verdict = "watch_for_reclaim_or_pullback"

    vetoes = sorted(set(vetoes))
    if gate_verdict != original_verdict or vetoes != sorted(set(original_vetoes)):
        warnings.append("promotion_gate_fields_aligned_to_current_band_status")
    return {
        "gate_verdict": gate_verdict,
        "gate_vetoes": vetoes,
        "warnings": warnings,
    }


def blocking_primary_state_still_applies(
    primary_state: Any,
    current: dict[str, Any],
    source_gate: dict[str, Any],
    freshness: dict[str, Any],
) -> bool:
    """Keep fail-closed primary blockers unless the current gate clears that blocker."""

    band_complete = (
        current.get("entry_band_low") is not None
        and current.get("entry_band_high") is not None
        and current.get("stop_or_invalidation") is not None
        and current.get("band_status") not in MISSING_BAND_STATES
    )
    if primary_state == "blocked_missing_freshness" and freshness.get("status") == "fresh":
        return False
    if primary_state == "blocked_missing_source_open" and source_gate.get("source_open_status") == "verified":
        return False
    if primary_state == "blocked_missing_band_or_stop" and band_complete:
        return False
    return primary_state in BLOCKING_PRIMARY_STATES


def classify_decision_state(
    current: dict[str, Any],
    source_gate: dict[str, Any],
    freshness: dict[str, Any],
    membership: dict[str, Any],
) -> tuple[str, list[str]]:
    blockers: list[str] = []
    primary_state = current.get("primary_state")
    band_status = current.get("band_status")
    is_thin_monitor = thin_monitor_scope(membership)
    if primary_state in INVALIDATION_PRIMARY_STATES or band_status == "BELOW_STOP":
        return "below_stop_or_invalidation", ["primary_state_or_band_below_stop"]
    if is_thin_monitor:
        return "monitor_only", ["thin_monitor_not_decision_grade"]
    if current.get("entry_band_low") is None or current.get("entry_band_high") is None or current.get("stop_or_invalidation") is None:
        return "blocked_missing_band_or_stop", ["missing_entry_band_or_stop"]
    if band_status in MISSING_BAND_STATES:
        return "blocked_missing_band_or_stop", ["band_status_missing_or_unknown"]
    if blocking_primary_state_still_applies(primary_state, current, source_gate, freshness):
        return str(primary_state), [f"primary_state={primary_state}"]
    if source_gate.get("source_open_status") != "verified":
        return "blocked_missing_source_open", ["source_open_not_verified"]
    if freshness.get("status") != "fresh":
        return "blocked_missing_freshness", freshness.get("blockers", ["freshness_not_verified"])
    if band_status in NO_CHASE_BAND_STATES:
        return "no_chase", [f"band_status={band_status}"]
    if primary_state == "promotion_vetoed":
        return "evidence_repair", ["promotion_vetoed"]
    if current.get("gate_verdict") == PROMOTE_VERDICT and band_status == APPROVAL_DRAFT_BAND_STATUS:
        return "review_ready", blockers
    if primary_state in REVIEW_READY_PRIMARY_STATES:
        return "review_ready", blockers
    return "monitor_only", ["not_owner_review_candidate"]
