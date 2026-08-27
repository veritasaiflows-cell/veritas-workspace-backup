#!/usr/bin/env python3
"""Build the WF85 review-ready repair conveyor.

This artifact does not repair cards directly. It joins WF85 cards with WF78
freshness/band repair proof and routes each blocker to the upstream owner lane
that can make a future WF85 card legitimately review-ready.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCRIPTS = Path(__file__).resolve().parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from market_data_utils import atomic_write_json, load_json_artifact

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
DEFAULT_OUT = TMP / "trade-grade-repair-conveyor.json"

CARDS = TMP / "trade-grade-decision-cards.json"
SOURCE_GATE = TMP / "trade-grade-source-freshness-gate.json"
APPROVAL_GATE = TMP / "trade-grade-approval-card-gate.json"
TIER_WEIGHTED = TMP / "wf78-tier-weighted-freshness-resolution.json"
FRESHNESS_LEDGER = TMP / "wf78-ticker-freshness-ledger.json"
MISSING_BAND_REPAIR = TMP / "wf78-missing-band-context-repair.json"
BAND_HYGIENE = TMP / "band-hygiene-freshness-controller.json"
TICKER_CARD_GATE = TMP / "finance-ticker-card-refresh-gate.json"

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "repair_routing_only": True,
    "automated_non_capital_routing_allowed": True,
    "ticker_card_mutation_allowed": False,
    "canon_or_portfolio_mutation_allowed": False,
    "cash_sizing_or_risk_rule_mutation_allowed": False,
    "capital_deployment_allowed": False,
    "capital_deployment_approved": False,
    "approval_card_draft_allowed_by_conveyor": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "money_movement_allowed": False,
    "customer_or_external_delivery_allowed": False,
    "owner_approval_inferred": False,
}

FALSE_AUTHORITY_KEYS = [
    key
    for key, value in AUTHORITY_BOUNDARY.items()
    if value is False
]

FINANCE_DOMAIN_REPAIR_LANES = {
    "fresh_quote_review_ready_pilot_candidate",
    "fresh_quote_thin_monitor_or_promotion_decision",
    "freshness_repair_after_band_review",
    "invalidation_or_below_stop_review_only",
    "primary_state_blocker_repair",
    "review_ready_waiting_approval_gate",
    "tier_c_thin_monitor_deferred",
    "wf78_band_context_recheck",
    "wf78_band_stop_context_repair",
    "wf78_source_open_or_owner_lineage_repair",
}

MONITOR_ONLY_LANES = {
    "monitor_only",
    "tier_c_thin_monitor_deferred",
}

OWNER_GATE_LANES = {
    "review_ready_waiting_approval_gate",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def load(path: Path) -> dict[str, Any]:
    payload = load_json_artifact(path)
    return payload if isinstance(payload, dict) else {}


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def rows_by_ticker(payload: dict[str, Any], key: str = "rows") -> dict[str, dict[str, Any]]:
    rows = as_list(payload.get(key))
    out: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        ticker = str(row.get("ticker") or "").upper()
        if ticker:
            out[ticker] = row
    return out


def source_open_status(source_row: dict[str, Any]) -> str:
    return str(source_row.get("source_open_status") or "blocked")


def card_band_status(card: dict[str, Any]) -> str | None:
    return as_dict(card.get("entry_band")).get("band_status")


def stop_present(card: dict[str, Any]) -> bool:
    return as_dict(card.get("stop_or_invalidation")).get("level") is not None


def decision_grade_band_missing(card: dict[str, Any]) -> bool:
    band = as_dict(card.get("entry_band"))
    return (
        band.get("low") is None
        or band.get("high") is None
        or not stop_present(card)
        or band.get("band_status") in {None, "", "UNKNOWN", "missing_required_refresh"}
    )


def source_freshness_status(card: dict[str, Any]) -> str:
    return str(as_dict(card.get("source_freshness")).get("status") or "blocked")


def quote_status(card: dict[str, Any]) -> str:
    return str(as_dict(card.get("source_freshness")).get("quote_freshness_status") or "unknown")


def repair_scope(repair_lane: str) -> str:
    if repair_lane in OWNER_GATE_LANES:
        return "owner_finance_gate"
    if repair_lane in FINANCE_DOMAIN_REPAIR_LANES or repair_lane in MONITOR_ONLY_LANES:
        return "finance_domain"
    return "finance_domain"


def finance_domain_blocker(repair_lane: str) -> bool:
    return repair_scope(repair_lane) == "finance_domain"


def implementation_blocker_for_row(_: str) -> bool:
    return False


def scope_summary(rows: list[dict[str, Any]], validation_errors: list[str]) -> dict[str, Any]:
    finance_domain_rows = [row for row in rows if row.get("repair_scope") == "finance_domain"]
    owner_gate_rows = [row for row in rows if row.get("repair_scope") == "owner_finance_gate"]
    implementation_rows = [row for row in rows if row.get("implementation_blocker") is True]
    tier_a_b_missing_band = [
        row for row in rows
        if row.get("auto_tier") in {"Tier A", "Tier B"}
        and row.get("decision_grade_band_missing") is True
    ]
    tier_b_missing_band = [row for row in tier_a_b_missing_band if row.get("auto_tier") == "Tier B"]
    return {
        "pm_blocker_scope": "finance_domain_only" if not validation_errors else "control_plane_validation_failed",
        "implementation_queue_posture": "not_an_implementation_blocker" if not validation_errors else "implementation_attention_required",
        "tier_a_b_daily_decision_grade_band_policy": "required_for_daily_finance_review_not_auto_canon_apply",
        "tier_a_b_missing_decision_grade_band_count": len(tier_a_b_missing_band),
        "tier_a_b_missing_decision_grade_band_tickers": [str(row.get("ticker")) for row in tier_a_b_missing_band],
        "tier_b_missing_decision_grade_band_count": len(tier_b_missing_band),
        "tier_b_missing_decision_grade_band_tickers": [str(row.get("ticker")) for row in tier_b_missing_band],
        "normal_finance_repair_rows_create_pm_implementation_jobs": False,
        "only_validation_errors_create_implementation_blockers": True,
        "total_repair_conveyor_row_count": len(rows),
        "finance_domain_repair_item_count": len(finance_domain_rows),
        "finance_or_owner_gate_repair_item_count": len(finance_domain_rows) + len(owner_gate_rows),
        "finance_domain_blocker_count": len([row for row in finance_domain_rows if row.get("finance_domain_blocker") is True]),
        "implementation_blocker_count": len(implementation_rows) + len(validation_errors),
        "control_plane_blocker_count": len(validation_errors),
        "monitor_only_count": len([row for row in rows if row.get("repair_lane") in MONITOR_ONLY_LANES]),
        "owner_finance_gate_count": len(owner_gate_rows),
    }


def pilot_contract_errors(pilot: list[dict[str, Any]]) -> list[str]:
    """Return tickers whose pilot rows violate repair-only safety constraints."""
    allowed_decision_states = {"blocked_missing_freshness", "monitor_only"}
    return [
        str(row.get("ticker"))
        for row in pilot
        if row.get("source_open_status") != "verified"
        or row.get("band_status") != "IN_BAND"
        or row.get("stop_or_invalidation_present") is not True
        or row.get("auto_tier") not in {"Tier A", "Tier B"}
        or row.get("decision_state") not in allowed_decision_states
    ]


ATOMIC_FIVE_FAMILIES = (
    "catalyst_earnings_state",
    "price_band_stop",
    "technical_posture",
    "recommendation_support",
    "deployment_readiness",
)

ATOMIC_REPAIR_FALSE_AUTHORITY = {
    "finance_data_mutation_allowed": False,
    "canon_mutation_allowed": False,
    "portfolio_mutation_allowed": False,
    "customer_or_external_delivery_allowed": False,
    "capital_deployment_approved": False,
    "trade_or_execution_approved": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "owner_approval_inferred": False,
}

EARNINGS_INTAKE_REQUIREMENTS = [
    "issuer_or_ticker",
    "event_type",
    "source_class",
    "source_url",
    "publisher",
    "published_at_utc",
    "retrieved_at_utc",
    "fiscal_period_label",
    "fiscal_period_start",
    "fiscal_period_end",
    "fiscal_period_basis",
    "event_datetime",
    "event_timezone",
    "event_session",
    "timing_status",
    "evidence_linkage_id",
    "conflicts",
    "ambiguity_reason",
]


def atomic_five_family_repair_queue(
    tier_rows: list[Any], repair_as_of_utc: str
) -> list[dict[str, Any]]:
    """Build a deterministic, manual-only intake for unresolved Tier A/B debt."""
    queue: list[dict[str, Any]] = []
    for value in tier_rows:
        row = as_dict(value)
        symbol = str(row.get("ticker") or "").upper()
        tier = str(row.get("auto_tier") or row.get("tier") or "")
        resolution_state = str(row.get("resolution_state") or "")
        if (
            not symbol
            or tier not in {"Tier A", "Tier B"}
            or resolution_state != "blocked_unresolved_tier_ab_debt"
        ):
            continue

        stale_families = {
            str(item).removeprefix("stale:")
            for item in as_list(row.get("stale_families"))
        }
        dispositions = [
            {
                "family": family,
                "status": "refresh_required" if family in stale_families else "retained_current",
                "depends_on": (
                    ["catalyst_earnings_state", "price_band_stop", "technical_posture"]
                    if family == "recommendation_support"
                    else list(ATOMIC_FIVE_FAMILIES[:4])
                    if family == "deployment_readiness"
                    else []
                ),
            }
            for family in ATOMIC_FIVE_FAMILIES
        ]
        queue.append(
            {
                "ticker": symbol,
                "tier": tier,
                "required_depth": row.get("required_depth"),
                "current_resolution_state": resolution_state,
                "repair_bundle_id": f"tier-ab-five-family:{symbol}:{resolution_state}",
                "repair_input_signature": "|".join(
                    [symbol, tier, resolution_state, *sorted(stale_families)]
                ),
                "repair_as_of_utc": repair_as_of_utc,
                "first_family": "catalyst_earnings_state",
                "family_dispositions": dispositions,
                "official_earnings_intake_requirements": list(EARNINGS_INTAKE_REQUIREMENTS),
                "official_earnings_intake_status": "pending_source_open",
                "source_open_manual_only": True,
                "authority_boundary": dict(ATOMIC_REPAIR_FALSE_AUTHORITY),
                "source_mismatch_handling": "manual_source_open_only_no_auto_overwrite",
            }
        )

    def queue_order(row: dict[str, Any]) -> tuple[int, str]:
        symbol = str(row["ticker"])
        if row["tier"] == "Tier A":
            return (0, symbol)
        if symbol in {"DASH", "TSM"}:
            return (1, symbol)
        if symbol == "AVGO":
            return (2, symbol)
        return (3, symbol)

    return sorted(queue, key=queue_order)


def atomic_five_family_repair_errors(queue: list[dict[str, Any]]) -> list[str]:
    """Validate the repair intake without mutating any source data."""
    errors: list[str] = []
    tickers = [str(row.get("ticker") or "") for row in queue]
    if len(tickers) != len(set(tickers)):
        errors.append("atomic_repair_queue_duplicate_ticker")
    required_row_keys = {
        "ticker",
        "tier",
        "required_depth",
        "current_resolution_state",
        "repair_bundle_id",
        "repair_input_signature",
        "repair_as_of_utc",
        "first_family",
        "family_dispositions",
        "official_earnings_intake_requirements",
        "official_earnings_intake_status",
        "source_open_manual_only",
        "authority_boundary",
    }
    for row in queue:
        symbol = str(row.get("ticker") or "unknown")
        if not required_row_keys.issubset(row):
            errors.append(f"atomic_repair_queue_required_field_missing:{symbol}")
        dispositions = as_list(row.get("family_dispositions"))
        families = [str(as_dict(item).get("family") or "") for item in dispositions]
        if len(dispositions) != 5 or set(families) != set(ATOMIC_FIVE_FAMILIES):
            errors.append(f"atomic_repair_queue_family_completeness_failed:{symbol}")
            continue
        if row.get("first_family") != "catalyst_earnings_state" or any(
            not {"family", "status", "depends_on"}.issubset(as_dict(item))
            for item in dispositions
        ):
            errors.append(f"atomic_repair_queue_family_field_missing:{symbol}")
        by_family = {
            str(as_dict(item).get("family")): as_dict(item)
            for item in dispositions
        }
        if any(
            item.get("status") not in {"refresh_required", "retained_current"}
            for item in by_family.values()
        ):
            errors.append(f"atomic_repair_queue_family_status_invalid:{symbol}")
        if by_family["recommendation_support"].get("depends_on") != list(ATOMIC_FIVE_FAMILIES[:3]):
            errors.append(f"atomic_repair_queue_recommendation_dependency_invalid:{symbol}")
        if by_family["deployment_readiness"].get("depends_on") != list(ATOMIC_FIVE_FAMILIES[:4]):
            errors.append(f"atomic_repair_queue_deployment_dependency_invalid:{symbol}")
        if set(as_list(row.get("official_earnings_intake_requirements"))) != set(EARNINGS_INTAKE_REQUIREMENTS):
            errors.append(f"atomic_repair_queue_earnings_intake_incomplete:{symbol}")
        if row.get("source_open_manual_only") is not True:
            errors.append(f"atomic_repair_queue_source_open_not_manual:{symbol}")
        if any(
            as_dict(row.get("authority_boundary")).get(key) is not False
            for key in ATOMIC_REPAIR_FALSE_AUTHORITY
        ):
            errors.append(f"atomic_repair_queue_unsafe_authority:{symbol}")
    return errors


def classify_lane(
    card: dict[str, Any],
    source_row: dict[str, Any],
    tier_row: dict[str, Any],
    ledger_row: dict[str, Any],
    missing_band_row: dict[str, Any],
    band_row: dict[str, Any],
) -> tuple[str, list[str], str, int]:
    decision_state = str(card.get("decision_state") or "")
    auto_tier = str(card.get("auto_tier") or "")
    band_status = card_band_status(card)
    src_status = source_open_status(source_row)
    fresh_status = source_freshness_status(card)
    has_stop = stop_present(card)

    blockers: list[str] = []
    if src_status != "verified":
        blockers.append("source_open_not_verified")
    if fresh_status != "fresh":
        blockers.append("freshness_not_verified")
    if band_status != "IN_BAND":
        blockers.append(f"band_status={band_status}")
    if not has_stop:
        blockers.append("stop_or_invalidation_missing")

    if decision_state == "below_stop_or_invalidation":
        return (
            "invalidation_or_below_stop_review_only",
            ["below_stop_or_invalidation_blocks_review_ready"],
            "Keep blocked; do not draft approval. Use invalidation/reclaim review outside WF85.",
            90,
        )

    if str(card.get("primary_state") or "") in {"blocked_missing_freshness", "blocked_missing_source_open", "blocked_missing_band_or_stop"}:
        return (
            "primary_state_blocker_repair",
            blockers,
            "Repair the upstream primary-state blocker before treating this as a review-ready pilot candidate.",
            58,
        )

    if not has_stop or band_status in {None, "", "UNKNOWN", "missing_required_refresh"}:
        if auto_tier == "Tier C" and str(tier_row.get("resolution_state") or "").startswith("resolved_thin_monitor"):
            return (
                "tier_c_thin_monitor_deferred",
                blockers,
                "Keep as Tier C thin-monitor; promote before decision-grade band/stop repair.",
                20,
            )
        if missing_band_row:
            return (
                "wf78_band_context_recheck",
                blockers,
                "Use wf78_missing_band_context_repair proof, then rerun WF78/WF84/WF85.",
                65,
            )
        return (
            "wf78_band_stop_context_repair",
            blockers,
            "Run or extend WF78 missing-band/entry-stop repair before WF85 can use this card.",
            60,
        )

    if src_status != "verified":
        return (
            "wf78_source_open_or_owner_lineage_repair",
            blockers,
            "Use WF78 source-open/owner-lineage repair before material claims or review-ready cards.",
            70,
        )

    if fresh_status != "fresh" and band_status == "IN_BAND" and has_stop:
        if str(card.get("auto_tier")) in {"Tier A", "Tier B"}:
            return (
                "fresh_quote_review_ready_pilot_candidate",
                blockers,
                "Refresh quote/evidence freshness, then rerun WF84/WF85; this is the first pilot queue.",
                100 if card.get("auto_state") == "A-READY" else 85,
            )
        return (
            "fresh_quote_thin_monitor_or_promotion_decision",
            blockers,
            "Do not treat Tier C as decision-grade until promoted; freshness refresh can support monitor triage only.",
            40,
        )

    if fresh_status != "fresh":
        return (
            "freshness_repair_after_band_review",
            blockers,
            "Repair quote/evidence freshness, but non-IN_BAND posture still blocks approval-card drafts.",
            55,
        )

    if decision_state == "review_ready":
        return (
            "review_ready_waiting_approval_gate",
            [],
            "Card is review-ready; approval draft still requires IN_BAND, fresh WF67 guard, and exact owner approval boundary.",
            100,
        )

    return (
        "monitor_only",
        blockers,
        "Monitor only; no WF85 repair action required now.",
        10,
    )


def build() -> dict[str, Any]:
    generated = utc_now()
    cards_payload = load(CARDS)
    source_payload = load(SOURCE_GATE)
    approval_payload = load(APPROVAL_GATE)
    tier_payload = load(TIER_WEIGHTED)
    ledger_payload = load(FRESHNESS_LEDGER)
    missing_band_payload = load(MISSING_BAND_REPAIR)
    band_hygiene_payload = load(BAND_HYGIENE)
    ticker_card_gate_payload = load(TICKER_CARD_GATE)

    source_by_ticker = rows_by_ticker(source_payload)
    tier_by_ticker = rows_by_ticker(tier_payload)
    ledger_by_ticker = rows_by_ticker(ledger_payload)
    missing_band_by_ticker = rows_by_ticker(missing_band_payload)
    band_by_ticker = rows_by_ticker(band_hygiene_payload)
    cards = as_list(cards_payload.get("cards"))

    rows: list[dict[str, Any]] = []
    for card in cards:
        if not isinstance(card, dict):
            continue
        ticker = str(card.get("ticker") or "").upper()
        if not ticker:
            continue
        source_row = source_by_ticker.get(ticker, {})
        tier_row = tier_by_ticker.get(ticker, {})
        ledger_row = ledger_by_ticker.get(ticker, {})
        missing_band_row = missing_band_by_ticker.get(ticker, {})
        band_row = band_by_ticker.get(ticker, {})
        repair_lane, blockers, next_action, priority = classify_lane(
            card, source_row, tier_row, ledger_row, missing_band_row, band_row
        )
        row = {
            "ticker": ticker,
            "auto_tier": card.get("auto_tier"),
            "auto_state": card.get("auto_state"),
            "primary_state": card.get("primary_state"),
            "decision_state": card.get("decision_state"),
            "repair_lane": repair_lane,
            "repair_scope": repair_scope(repair_lane),
            "decision_grade_band_missing": decision_grade_band_missing(card),
            "repair_priority": priority,
            "blockers": blockers,
            "finance_domain_blocker": finance_domain_blocker(repair_lane),
            "implementation_blocker": implementation_blocker_for_row(repair_lane),
            "control_plane_blocker": False,
            "source_open_status": source_open_status(source_row),
            "freshness_status": source_freshness_status(card),
            "quote_freshness_status": quote_status(card),
            "band_status": card_band_status(card),
            "stop_or_invalidation_present": stop_present(card),
            "tier_weighted_resolution_state": tier_row.get("resolution_state"),
            "freshness_ledger_state": ledger_row.get("overall_freshness_state"),
            "missing_band_repair_status": missing_band_row.get("repair_status"),
            "band_hygiene_state": band_row.get("state"),
            "next_action": next_action,
            "source_artifacts": [
                rel(CARDS),
                rel(SOURCE_GATE),
                rel(TIER_WEIGHTED),
                rel(FRESHNESS_LEDGER),
                rel(MISSING_BAND_REPAIR),
                rel(BAND_HYGIENE),
                rel(TICKER_CARD_GATE),
            ],
            "capital_deployment_approved": False,
            "trade_or_execution_approved": False,
            "paper_or_live_execution_allowed": False,
            "owner_approval_inferred": False,
        }
        rows.append(row)

    rows.sort(key=lambda row: (-int(row.get("repair_priority") or 0), str(row.get("auto_tier") or ""), str(row.get("ticker") or "")))
    lane_counts = Counter(str(row.get("repair_lane") or "unknown") for row in rows)
    decision_counts = Counter(str(row.get("decision_state") or "unknown") for row in rows)
    pilot = [row for row in rows if row.get("repair_lane") == "fresh_quote_review_ready_pilot_candidate"]
    pilot_tickers = [str(row.get("ticker")) for row in pilot]

    validation_errors: list[str] = []
    validation_warnings: list[str] = [
        "review_ready pilot candidates are not approval-card drafts",
        "WF67 paper guard must be fresh before any paper-request draft posture",
    ]
    for key in FALSE_AUTHORITY_KEYS:
        if AUTHORITY_BOUNDARY.get(key) is not False:
            validation_errors.append(f"authority_boundary_not_false:{key}")
    bad_pilot = pilot_contract_errors(pilot)
    if bad_pilot:
        validation_errors.append(f"pilot_candidate_contract_failed:{','.join(map(str, bad_pilot[:10]))}")
    approval_summary = as_dict(approval_payload.get("summary"))
    approval_card_draft_count = int(approval_summary.get("approval_card_draft_count") or 0)
    approval_gate_review_ready_count = int(approval_summary.get("review_ready_count") or 0)
    if approval_card_draft_count != 0:
        validation_errors.append("approval_card_drafts_present_before_conveyor_repair")

    ticker_gate_summary = as_dict(ticker_card_gate_payload.get("summary"))
    card_rollup = as_dict(ticker_gate_summary.get("card_rollup"))
    ticker_gate_decision_ready_count = int(card_rollup.get("decision_ready_card_count") or 0)
    if ticker_gate_decision_ready_count > 0:
        validation_warnings.append("ticker_card_gate_decision_ready_requires_owner_approval_gate")

    tier_rows = as_list(tier_payload.get("rows"))
    atomic_repair_queue = atomic_five_family_repair_queue(tier_rows, generated)
    atomic_repair_errors = atomic_five_family_repair_errors(atomic_repair_queue)
    expected_atomic_queue_count = sum(
        1
        for value in tier_rows
        if as_dict(value).get("auto_tier") in {"Tier A", "Tier B"}
        and as_dict(value).get("resolution_state") == "blocked_unresolved_tier_ab_debt"
    )
    if len(atomic_repair_queue) != expected_atomic_queue_count:
        atomic_repair_errors.append(
            "atomic_repair_queue_count_mismatch:"
            f"{len(atomic_repair_queue)}/{expected_atomic_queue_count}"
        )
    validation_errors.extend(atomic_repair_errors)
    atomic_tier_counts = Counter(str(row.get("tier") or "unknown") for row in atomic_repair_queue)
    atomic_pilot_tickers = [
        str(row.get("ticker"))
        for row in atomic_repair_queue
        if str(row.get("ticker")) in {"DASH", "TSM", "AVGO"}
    ]
    atomic_complete_count = sum(
        1
        for row in atomic_repair_queue
        if len(as_list(row.get("family_dispositions"))) == len(ATOMIC_FIVE_FAMILIES)
    )
    scope = scope_summary(rows, validation_errors)
    status = "blocked" if validation_errors else "ready_for_repair_execution"
    return {
        "schema": "veritas.trade_grade_repair_conveyor.v1",
        "generated_at_utc": generated,
        "status": status,
        "purpose": "Route WF85 fail-closed cards to upstream source/freshness and band/stop repair lanes before review-ready pilots.",
        "authority": AUTHORITY_BOUNDARY,
        "authority_boundary": AUTHORITY_BOUNDARY,
        "source_artifacts": {
            "decision_cards": rel(CARDS),
            "source_freshness_gate": rel(SOURCE_GATE),
            "approval_card_gate": rel(APPROVAL_GATE),
            "tier_weighted_freshness_resolution": rel(TIER_WEIGHTED),
            "ticker_freshness_ledger": rel(FRESHNESS_LEDGER),
            "missing_band_context_repair": rel(MISSING_BAND_REPAIR),
            "band_hygiene_freshness_controller": rel(BAND_HYGIENE),
            "ticker_card_refresh_gate": rel(TICKER_CARD_GATE),
        },
        "summary": {
            "card_count": len(rows),
            "decision_state_counts": dict(decision_counts),
            "repair_lane_counts": dict(lane_counts),
            "repair_scope_counts": dict(Counter(str(row.get("repair_scope") or "unknown") for row in rows)),
            "review_ready_pilot_candidate_count": len(pilot),
            "review_ready_pilot_tickers": pilot_tickers,
            "tier_a_b_pilot_candidate_count": sum(1 for row in pilot if row.get("auto_tier") in {"Tier A", "Tier B"}),
            "approval_card_draft_count": approval_summary.get("approval_card_draft_count"),
            "approval_gate_review_ready_count": approval_gate_review_ready_count,
            "ticker_card_gate_decision_ready_card_count": ticker_gate_decision_ready_count,
            "wf67_paper_guard_fresh": approval_summary.get("wf67_paper_guard_fresh"),
            "atomic_five_family_repair_queue_count": len(atomic_repair_queue),
            "atomic_five_family_tier_a_count": atomic_tier_counts.get("Tier A", 0),
            "atomic_five_family_tier_b_count": atomic_tier_counts.get("Tier B", 0),
            "atomic_five_family_pilot_tickers": atomic_pilot_tickers,
            "atomic_five_family_completeness_count": atomic_complete_count,
            **scope,
            "next_safe_action": "Use these rows as finance-domain repair queue only; create implementation work only if conveyor validation fails or WF84/WF85 quality gates regress.",
        },
        "implementation_noise_policy": {
            "normal_repair_lanes_are_domain_debt": True,
            "normal_repair_lanes_block_implementation": False,
            "monitor_only_rows_block_implementation": False,
            "below_stop_or_invalidation_rows_block_implementation": False,
            "band_stop_context_repair_rows_block_implementation": False,
            "implementation_blocker_trigger": "validation_errors_only",
        },
        "pilot_queue": pilot[:25],
        "atomic_five_family_repair_intake": {
            "queue": atomic_repair_queue,
            "summary": {
                "queue_count": len(atomic_repair_queue),
                "tier_a_count": atomic_tier_counts.get("Tier A", 0),
                "tier_b_count": atomic_tier_counts.get("Tier B", 0),
                "pilot_tickers": atomic_pilot_tickers,
                "five_family_completeness_count": atomic_complete_count,
                "first_family": "catalyst_earnings_state",
                "source_open_manual_only": True,
                "next_safe_action": (
                    "Open official sources manually, reconcile fiscal-period evidence, and retain "
                    "source mismatches without auto-overwriting finance data."
                ),
            },
            "validation_errors": atomic_repair_errors,
        },
        "rows": rows,
        "validation": {
            "status": "error" if validation_errors else "ok",
            "errors": validation_errors,
            "warnings": validation_warnings,
        },
        "stop_lines": [
            "No approval-card draft is created by this conveyor.",
            "No generated row is Randall approval.",
            "No paper/live/account action, money movement, canon/portfolio/cash/sizing/risk-rule mutation, or customer/external delivery.",
        ],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build WF85 upstream repair conveyor.")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--pretty", action="store_true")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    payload = build()
    if args.write:
        out = args.output if args.output.is_absolute() else ROOT / args.output
        atomic_write_json(out, payload)
        print(f"wrote {rel(out)} status={payload.get('status')} pilots={payload.get('summary', {}).get('review_ready_pilot_candidate_count')}")
    else:
        print(json.dumps(payload, indent=2 if args.pretty else None, sort_keys=True))
    if args.validate and payload.get("validation", {}).get("errors"):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
