#!/usr/bin/env python3
"""Build autonomous review-only routing and card queue.

This packet is the V2 bridge between autonomous non-capital tier routing
(WF78/WF85) and owner-gated paper-card prep (WF67/WF86/WF87). It can decide
which rows are review-ready, wait/reclaim, no-chase, invalidation, or repair.
It cannot approve capital or submit/cancel/sell paper/live orders.

The historical file name is retained for compatibility. Forward consumers
should treat this as an autonomous review-card queue, not a deployment authority
or recommendation surface.
"""
from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, load_json_artifact

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
OUT = TMP / "autonomous-routing-deployment-cards.json"
SCHEMA = "veritas.autonomous_routing_deployment_cards.v1"

SOURCES = {
    "wf78_auto_router": TMP / "wf78-auto-tier-routing.json",
    "wf78_batch_manifest": ROOT / "state" / "workflows" / "wf78-scaleout-batch-manifest.json",
    "wf84_data_plane": TMP / "canonical-finance-data-plane.json",
    "wf85_timing_gate": TMP / "wf85-deployment-timing-gate.json",
    "morning_cards": TMP / "morning-paper-deployment-recommendation-cards.json",
    "wf87_command_center": TMP / "wf87-autonomy-command-center.json",
    "wf87_rollup": TMP / "wf87-v2-readiness-rollup.json",
    "wf87_approval_ttl": TMP / "wf87-approval-freshness-ttl.json",
    "wf87_circuit_breakers": TMP / "wf87-portfolio-circuit-breakers.json",
    "wf67_guard": TMP / "alpaca-paper-readiness" / "paper-execution-guard-validation.json",
    "canon_status_invariant": TMP / "canonical-status-invariant-validation.json",
    "canonical_ownership": TMP / "canonical-ownership-validation.json",
    "canon_drift_gate": TMP / "canon-drift-freshness-gate.json",
}

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "autonomous_non_capital_routing_allowed": True,
    "autonomous_review_card_queue_allowed": True,
    "owner_card_generation_reference_allowed": True,
    "wf67_request_artifact_reference_allowed": True,
    "capital_deployment_allowed": False,
    "capital_deployment_approved": False,
    "trade_or_execution_allowed": False,
    "trade_or_execution_approved": False,
    "paper_or_live_execution_allowed": False,
    "paper_submit_allowed": False,
    "paper_cancel_allowed": False,
    "paper_sell_allowed": False,
    "live_trade_allowed": False,
    "live_endpoint_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "money_movement_allowed": False,
    "canon_or_portfolio_mutation_allowed": False,
    "universe_import_or_apply_allowed": False,
    "owner_approval_inferred": False,
    "cron_direct_execution_allowed": False,
}

FALSE_KEYS = {key for key, value in AUTHORITY_BOUNDARY.items() if value is False}

FINAL_STATE_ACTIONS = {
    "review_ready_wait_approval": "owner_review_card_candidate",
    "review_ready_wait_fresh_quote": "market_hours_quote_refresh_required",
    "review_ready_suppressed": "repair_before_owner_card",
    "wait_for_band_reclaim": "watch_for_reclaim",
    "wait_no_chase": "no_chase_monitor",
    "blocked_below_stop_or_invalidation": "invalidation_review",
    "repair_first": "repair_first",
    "thin_monitor_only": "thin_monitor_only",
}

BLOCKING_ACTIONS = {
    "market_hours_quote_refresh_required",
    "repair_before_owner_card",
    "watch_for_reclaim",
    "no_chase_monitor",
    "invalidation_review",
    "repair_first",
    "thin_monitor_only",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def load(path: Path) -> dict[str, Any]:
    payload = load_json_artifact(path)
    return payload if isinstance(payload, dict) else {}


def ticker(value: Any) -> str:
    return str(value or "").strip().upper()


def authority_true_paths(value: Any, prefix: str = "") -> list[str]:
    paths: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            child = f"{prefix}.{key}" if prefix else str(key)
            if key in FALSE_KEYS and item is True:
                paths.append(child)
            paths.extend(authority_true_paths(item, child))
    elif isinstance(value, list):
        for idx, item in enumerate(value):
            paths.extend(authority_true_paths(item, f"{prefix}[{idx}]"))
    return paths


def validation_status(payload: dict[str, Any]) -> str | None:
    return as_dict(payload.get("validation")).get("status")


def source_record(name: str, path: Path, payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": name,
        "path": rel(path),
        "exists": path.exists(),
        "status": payload.get("status") if payload else ("missing" if not path.exists() else "unparseable"),
        "validation_status": validation_status(payload),
        "generated_at_utc": payload.get("generated_at_utc"),
        "authority_drift_paths": authority_true_paths(payload),
    }


def rows_by_ticker(rows: list[Any]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for row in rows:
        row_dict = as_dict(row)
        symbol = ticker(row_dict.get("ticker"))
        if symbol:
            out[symbol] = row_dict
    return out


def import_gate_state(manifest: dict[str, Any]) -> dict[str, Any]:
    authority = as_dict(manifest.get("authority_boundary"))
    return {
        "ticker_import_allowed": authority.get("ticker_import_allowed") is True,
        "apply_allowed": authority.get("apply_allowed") is True,
        "promotion_allowed": authority.get("promotion_allowed") is True,
        "report_only": authority.get("report_only") is True,
    }


def morning_card_summary(card: dict[str, Any] | None) -> dict[str, Any]:
    if not card:
        return {
            "present": False,
            "status": None,
            "clean_for_randall_approval_review": False,
            "owner_card_path": None,
            "wf67_request_path": None,
            "blockers": [],
        }
    return {
        "present": True,
        "status": card.get("status"),
        "clean_for_randall_approval_review": card.get("clean_for_randall_approval_review") is True,
        "owner_card_path": card.get("owner_card_path"),
        "wf67_request_path": card.get("wf67_request_path"),
        "wf67_request_generation_status": card.get("wf67_request_generation_status"),
        "blockers": as_list(card.get("blockers")),
        "warnings": as_list(card.get("warnings")),
    }


def maturity_state(command: dict[str, Any], rollup: dict[str, Any]) -> dict[str, Any]:
    summary = as_dict(command.get("summary"))
    shadow = as_dict(summary.get("shadow_decisions"))
    sessions = as_dict(summary.get("shadow_sessions"))
    rollup_shadow = as_dict(rollup.get("shadow_threshold"))
    return {
        "command_status": command.get("status"),
        "operator_action": command.get("operator_action"),
        "autonomy_state": summary.get("autonomy_state"),
        "shadow_decisions_done": shadow.get("done", rollup_shadow.get("clean_shadow_decision_count")),
        "shadow_decisions_required": shadow.get("required", rollup_shadow.get("required_clean_decisions")),
        "shadow_sessions_done": sessions.get("done", rollup_shadow.get("unique_clean_market_sessions")),
        "shadow_sessions_required": sessions.get("required", rollup_shadow.get("required_clean_market_sessions")),
        "shadow_threshold_met": summary.get("shadow_threshold_met") is True or rollup_shadow.get("threshold_met") is True,
        "reconciliation_mature": as_dict(rollup.get("reconciliation_maturity")).get("mature_for_autonomy") is True,
        "exact_order_preparation_allowed_now": summary.get("exact_order_preparation_allowed_now") is True,
        "autonomous_execution_allowed_now": False,
    }


def gate_is_clean(payload: dict[str, Any]) -> bool:
    return payload.get("status") == "ok" and validation_status(payload) in {"ok", None}


def candidate_key(row: dict[str, Any]) -> str:
    symbol = ticker(row.get("ticker")) or "UNKNOWN"
    as_of = str(
        row.get("market_date")
        or row.get("as_of_date")
        or row.get("quote_as_of")
        or "undated"
    ).strip().casefold()
    safe_as_of = re.sub(r"[^a-z0-9]+", "-", as_of).strip("-") or "undated"
    return f"finance-candidate::{symbol}::{safe_as_of}"


def paper_chain_gates(payloads: dict[str, dict[str, Any]]) -> dict[str, Any]:
    gates = {
        "wf84_data_plane": gate_is_clean(payloads["wf84_data_plane"]),
        "wf87_approval_ttl": gate_is_clean(payloads["wf87_approval_ttl"]),
        "wf87_circuit_breakers": gate_is_clean(payloads["wf87_circuit_breakers"]),
        "wf67_guard": gate_is_clean(payloads["wf67_guard"]),
    }
    return {
        **gates,
        "all_execution_time_gates_clean": all(gates.values()),
    }


def authoritative_action(action: str) -> str:
    actions = {
        "owner_review_card_candidate": "Present the exact review card to Randall; no paper action occurs without Randall's separate exact approval.",
        "market_hours_quote_refresh_required": "Refresh the market-hours quote and rerun the timing gate before any review card.",
        "repair_before_owner_card": "Repair the missing/conflicting evidence before any review card.",
        "owner_card_materialization_blocked": "Keep this candidate blocked until all fail-closed execution-time gates and review evidence are clean.",
        "watch_for_reclaim": "Monitor for a valid entry-band reclaim; do not chase.",
        "no_chase_monitor": "Monitor only; do not chase outside the entry discipline.",
        "invalidation_review": "Treat the below-stop/invalidation state as blocked; reassess the thesis before any action.",
        "repair_first": "Repair the decision inputs before any review.",
        "thin_monitor_only": "Monitor only; this is not an execution-ready candidate.",
    }
    return actions.get(action, "Hold this review-only candidate until the exact owner artifacts resolve the blocker.")


def classify_queue_row(
    row: dict[str, Any],
    router_row: dict[str, Any] | None,
    morning_card: dict[str, Any] | None,
    maturity: dict[str, Any],
    gates: dict[str, Any],
) -> tuple[str, list[str]]:
    final_state = str(row.get("final_timing_state") or "")
    action = FINAL_STATE_ACTIONS.get(final_state, "repair_first")
    blockers: list[str] = []
    router = router_row or {}
    route_blockers: list[str] = []
    if router.get("auto_tier") != "Tier A":
        route_blockers.append(f"wf78_auto_tier_not_tier_a:{router.get('auto_tier')}")
    if router.get("review_lane") not in {None, "equity_depth"}:
        route_blockers.append(f"wf78_review_lane_not_equity_depth:{router.get('review_lane')}")
    if router.get("auto_state") != "A-READY":
        route_blockers.append(f"wf78_auto_state_not_a_ready:{router.get('auto_state')}")
    if router.get("tier_a_confidence_status") not in {None, "ready"}:
        route_blockers.append(f"wf78_confidence_not_ready:{router.get('tier_a_confidence_status')}")
    try:
        conflict_count = int(router.get("critical_data_conflict_count") or 0)
    except (TypeError, ValueError):
        conflict_count = 1
    if conflict_count:
        route_blockers.append(f"wf78_critical_data_conflict_count={conflict_count}")
    if router.get("capital_deployment_approved") is True or router.get("trade_or_execution_approved") is True:
        route_blockers.append("wf78_authority_approval_flag_true")
    blockers.extend(route_blockers)
    if action in BLOCKING_ACTIONS:
        blockers.append(f"timing_state={final_state}")
    card_summary = morning_card_summary(morning_card)
    if action == "owner_review_card_candidate":
        if route_blockers:
            action = "owner_card_materialization_blocked"
        if not card_summary["clean_for_randall_approval_review"]:
            action = "owner_card_materialization_blocked"
            blockers.extend(card_summary["blockers"] or ["morning_card_not_clean"])
        if not maturity.get("exact_order_preparation_allowed_now"):
            blockers.append("wf87_exact_order_preparation_not_allowed_now")
    if maturity.get("shadow_threshold_met") is not True:
        blockers.append("wf87_shadow_threshold_not_met")
    if maturity.get("reconciliation_mature") is not True:
        blockers.append("wf87_reconciliation_maturity_not_met")
    for gate_name in ("wf84_data_plane", "wf87_approval_ttl", "wf87_circuit_breakers", "wf67_guard"):
        if gates.get(gate_name) is not True:
            blockers.append(f"{gate_name}_not_clean")
    # Maturity accrual can still be shown to Randall as a review object, but
    # invalidation and execution-time gate failures are hard stops.
    hard_stop = (
        final_state == "blocked_below_stop_or_invalidation"
        or any(gates.get(name) is not True for name in ("wf84_data_plane", "wf87_approval_ttl", "wf87_circuit_breakers", "wf67_guard"))
    )
    if action == "owner_review_card_candidate" and hard_stop:
        action = "owner_card_materialization_blocked"
    return action, sorted(set(blockers))


def build_queue(payloads: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    timing_rows = [as_dict(row) for row in as_list(payloads["wf85_timing_gate"].get("rows"))]
    router_rows = rows_by_ticker(as_list(payloads["wf78_auto_router"].get("rows")))
    morning_cards = rows_by_ticker(as_list(payloads["morning_cards"].get("cards")))
    maturity = maturity_state(payloads["wf87_command_center"], payloads["wf87_rollup"])
    gates = paper_chain_gates(payloads)
    queue: list[dict[str, Any]] = []
    for row in timing_rows:
        if row.get("tier_scope") != "tier_a_b_decision_layer":
            continue
        symbol = ticker(row.get("ticker"))
        router_row = router_rows.get(symbol)
        morning_card = morning_cards.get(symbol)
        action, blockers = classify_queue_row(row, router_row, morning_card, maturity, gates)
        card = morning_card_summary(morning_card)
        candidate_id = candidate_key(row)
        wf87_state = "eligible" if gates["all_execution_time_gates_clean"] else "blocked"
        wf67_state = "ready" if gates["wf67_guard"] else "blocked"
        queue.append({
            "candidate_id": candidate_id,
            "ticker": symbol,
            "name": row.get("name"),
            "auto_tier": row.get("auto_tier"),
            "auto_state": row.get("auto_state"),
            "wf78_route": {
                "auto_tier": as_dict(router_row).get("auto_tier"),
                "auto_state": as_dict(router_row).get("auto_state"),
                "lane_tier": as_dict(router_row).get("lane_tier"),
                "review_lane": as_dict(router_row).get("review_lane"),
                "instrument_class": as_dict(router_row).get("instrument_class"),
                "asset_class": as_dict(router_row).get("asset_class"),
                "deployment_role": as_dict(router_row).get("deployment_role"),
                "route_priority": as_dict(router_row).get("route_priority"),
                "tier_a_confidence_status": as_dict(router_row).get("tier_a_confidence_status"),
                "critical_data_conflict_count": as_dict(router_row).get("critical_data_conflict_count"),
            },
            "decision_state": row.get("decision_state"),
            "current_price": row.get("current_price"),
            "entry_band": row.get("entry_band"),
            "stop_or_invalidation": row.get("stop_or_invalidation"),
            "price_band_gate": row.get("price_band_gate"),
            "quote_freshness_class": row.get("quote_freshness_class"),
            "earnings_gate": row.get("earnings_gate"),
            "macro_sector_gate": row.get("macro_sector_gate"),
            "wf87_stub_status": row.get("wf87_stub_status"),
            "final_timing_state": row.get("final_timing_state"),
            "autonomous_routing_action": action,
            "authoritative_next_action": authoritative_action(action),
            "candidate_chain": {
                "WF78": {
                    "role": "evidence_routing",
                    "state": as_dict(router_row).get("auto_state") or "not_routed",
                    "candidate_id": candidate_id,
                },
                "WF84": {
                    "role": "structured_data_plane",
                    "state": payloads["wf84_data_plane"].get("status"),
                    "candidate_id": candidate_id,
                },
                "WF85": {
                    "role": "decision_review",
                    "state": row.get("final_timing_state"),
                    "candidate_id": candidate_id,
                },
                "WF87": {
                    "role": "paper_runtime_eligibility",
                    "state": wf87_state,
                    "approval_ttl_clean": gates["wf87_approval_ttl"],
                    "circuit_breakers_clean": gates["wf87_circuit_breakers"],
                    "candidate_id": candidate_id,
                },
                "WF67": {
                    "role": "paper_action_guard",
                    "state": wf67_state,
                    "guard_clean": gates["wf67_guard"],
                    "candidate_id": candidate_id,
                },
                "Randall": {
                    "role": "exact_owner_approval",
                    "state": "not_reached" if blockers else "approval_required",
                    "exact_approval_required": True,
                    "approval_received": False,
                    "candidate_id": candidate_id,
                },
            },
            "autonomous_card_materialization": {
                "owner_card_reference_allowed": card["present"],
                "owner_card_path": card["owner_card_path"],
                "wf67_request_artifact_reference_allowed": card["present"],
                "wf67_request_path": card["wf67_request_path"],
                "wf67_request_generation_status": card.get("wf67_request_generation_status"),
                "clean_for_randall_approval_review": card["clean_for_randall_approval_review"],
                "morning_card_status": card["status"],
            },
            "blockers": blockers,
            "warnings": card.get("warnings", []),
            "authority_boundary": {
                "capital_deployment_approved": False,
                "trade_or_execution_approved": False,
                "paper_or_live_execution_allowed": False,
                "owner_approval_inferred": False,
            },
        })
    return queue


def validate(payload: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    authority = as_dict(payload.get("authority_boundary"))
    for key, expected in AUTHORITY_BOUNDARY.items():
        if authority.get(key) is not expected:
            errors.append(f"authority_{key}_not_{str(expected).lower()}")
    for record in as_list(payload.get("source_records")):
        if record.get("exists") is not True:
            errors.append(f"missing_source:{record.get('name')}")
        if record.get("authority_drift_paths"):
            errors.append(f"authority_drift:{record.get('name')}")
        if record.get("validation_status") not in {"ok", None}:
            warnings.append(f"source_validation_not_ok:{record.get('name')}:{record.get('validation_status')}")
    gate = as_dict(payload.get("import_gate"))
    if gate.get("ticker_import_allowed") or gate.get("apply_allowed") or gate.get("promotion_allowed"):
        errors.append("wf78_import_or_apply_gate_open")
    for row in as_list(payload.get("queue")):
        row = as_dict(row)
        boundary = row.get("authority_boundary", {})
        if as_dict(boundary).get("capital_deployment_approved") or as_dict(boundary).get("trade_or_execution_approved"):
            errors.append(f"row_authority_approval_drift:{row.get('ticker')}")
        candidate_id = row.get("candidate_id")
        if not isinstance(candidate_id, str) or not candidate_id.startswith("finance-candidate::"):
            errors.append(f"candidate_id_invalid:{row.get('ticker')}")
        if not row.get("authoritative_next_action"):
            errors.append(f"authoritative_next_action_missing:{row.get('ticker')}")
        chain = as_dict(row.get("candidate_chain"))
        if set(chain) != {"WF78", "WF84", "WF85", "WF87", "WF67", "Randall"}:
            errors.append(f"candidate_chain_incomplete:{row.get('ticker')}")
        elif any(as_dict(chain.get(stage)).get("candidate_id") != candidate_id for stage in chain):
            errors.append(f"candidate_chain_id_mismatch:{row.get('ticker')}")
        randall = as_dict(chain.get("Randall"))
        if randall.get("approval_received") is not False or randall.get("exact_approval_required") is not True:
            errors.append(f"randall_approval_boundary_drift:{row.get('ticker')}")
        hard_block = (
            row.get("final_timing_state") == "blocked_below_stop_or_invalidation"
            or as_dict(chain.get("WF87")).get("state") != "eligible"
            or as_dict(chain.get("WF67")).get("state") != "ready"
        )
        if hard_block and row.get("autonomous_routing_action") == "owner_review_card_candidate":
            errors.append(f"fail_closed_candidate_advanced:{row.get('ticker')}")
    candidate_ids = [as_dict(row).get("candidate_id") for row in as_list(payload.get("queue"))]
    if len(candidate_ids) != len(set(candidate_ids)):
        errors.append("candidate_id_not_unique")
    summary = as_dict(payload.get("summary"))
    if summary.get("owner_review_card_candidate_count", 0) and summary.get("autonomous_execution_allowed_now") is not False:
        errors.append("review_candidate_with_execution_allowed")
    if not summary.get("tier_a_b_queue_count"):
        errors.append("tier_a_b_queue_empty")
    if summary.get("owner_card_materialization_blocked_count", 0):
        warnings.append("some_owner_card_candidates_are_blocked")
    return {"status": "error" if errors else "warning" if warnings else "ok", "errors": errors, "warnings": warnings}


def build_payload(paths: dict[str, Path]) -> dict[str, Any]:
    payloads = {name: load(path) for name, path in paths.items()}
    records = [source_record(name, path, payloads[name]) for name, path in paths.items()]
    queue = build_queue(payloads)
    action_counts = Counter(row.get("autonomous_routing_action") for row in queue)
    final_counts = Counter(row.get("final_timing_state") for row in queue)
    clean_cards = [row for row in queue if as_dict(row.get("autonomous_card_materialization")).get("clean_for_randall_approval_review")]
    materialized_cards = [row for row in queue if as_dict(row.get("autonomous_card_materialization")).get("owner_card_path")]
    maturity = maturity_state(payloads["wf87_command_center"], payloads["wf87_rollup"])
    execution_time_gates = paper_chain_gates(payloads)
    import_gate = import_gate_state(payloads["wf78_batch_manifest"])
    payload = {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "workflow_ids": ["WF78", "WF84", "WF85", "WF87", "WF67"],
        "status": "draft",
        "purpose": "One review-only candidate/action docket across WF78 evidence routing, WF84 data plane, WF85 decision review, WF87 runtime eligibility, WF67 paper guard, and Randall exact approval. Historical deployment-card naming is compatibility only.",
        "authority_boundary": AUTHORITY_BOUNDARY,
        "summary": {
            "tier_a_b_queue_count": len(queue),
            "candidate_docket_count": len(queue),
            "autonomous_routing_action_counts": dict(action_counts),
            "final_timing_state_counts": dict(final_counts),
            "clean_randall_review_card_count": len(clean_cards),
            "materialized_owner_card_reference_count": len(materialized_cards),
            "owner_review_card_candidate_count": action_counts.get("owner_review_card_candidate", 0),
            "owner_card_materialization_blocked_count": action_counts.get("owner_card_materialization_blocked", 0),
            "blocked_or_waiting_count": sum(count for action, count in action_counts.items() if action != "owner_review_card_candidate"),
            "shadow_threshold_met": maturity["shadow_threshold_met"],
            "reconciliation_mature": maturity["reconciliation_mature"],
            "exact_order_preparation_allowed_now": maturity["exact_order_preparation_allowed_now"],
            "autonomous_execution_allowed_now": False,
            "execution_time_gates_clean": execution_time_gates["all_execution_time_gates_clean"],
            "historical_deployment_card_name_retained_for_compatibility": True,
            "forward_surface_name": "autonomous_review_card_queue",
            "wf78_recommendation_language_retired": True,
            "next_safe_action": (
                "Present exact owner-review cards only when WF67/WF87 gates are fresh and clean; otherwise continue accrual/repair."
                if action_counts.get("owner_review_card_candidate", 0)
                else "Continue scheduled shadow accrual, market-hours quote refresh, and repair/no-chase/reclaim monitoring."
            ),
        },
        "maturity_state": maturity,
        "execution_time_gates": execution_time_gates,
        "import_gate": import_gate,
        "queue": queue,
        "source_artifacts": {name: rel(path) for name, path in paths.items()},
        "source_records": records,
        "stop_lines": [
            "Autonomous routing and card queue outputs are review/prep surfaces only.",
            "No row/card/queue item is capital approval, execution approval, or owner approval.",
            "No paper/live submit, cancel, sell, replace, live endpoint, account action, money movement, portfolio/canon mutation, universe import, or apply authority.",
            "WF78 201-300+ import remains report-only until exact owner approval reference exists.",
        ],
    }
    payload["validation"] = validate(payload)
    payload["status"] = "blocked" if payload["validation"]["status"] == "error" else "ok"
    return payload


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    for key, path in SOURCES.items():
        parser.add_argument(f"--{key.replace('_', '-')}", type=Path, default=path)
    parser.add_argument("--out", type=Path, default=OUT)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--pretty", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    paths = {key: (value if value.is_absolute() else ROOT / value) for key, value in vars(args).items() if key in SOURCES}
    payload = build_payload(paths)
    out = args.out if args.out.is_absolute() else ROOT / args.out
    if args.write:
        atomic_write_json(out, payload)
    if args.pretty:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(json.dumps({
            "status": payload.get("status"),
            "validation": payload.get("validation"),
            "summary": payload.get("summary"),
            "out": rel(out) if args.write else None,
        }, indent=2, sort_keys=True))
    if args.validate and as_dict(payload.get("validation")).get("status") == "error":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
