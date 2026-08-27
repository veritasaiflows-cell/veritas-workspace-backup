#!/usr/bin/env python3
"""Build the WF85 Decision OS review packet.

This is a read-only compositor over WF85 proof artifacts. It ranks the current
Tier A/B review and repair surface without creating approval-card drafts,
mutating finance canon/portfolio state, or implying execution authority.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, load_json_artifact

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"

DEFAULT_OUT = TMP / "wf85-decision-os-review-packet.json"
DEFAULT_MD_OUT = TMP / "wf85-decision-os-review-packet.md"

CARDS_PATH = TMP / "trade-grade-decision-cards.json"
SOURCE_GATE_PATH = TMP / "trade-grade-source-freshness-gate.json"
AUTHORITY_VALIDATION_PATH = TMP / "trade-grade-decision-card-authority-validation.json"
APPROVAL_GATE_PATH = TMP / "trade-grade-approval-card-gate.json"
RISK_OVERLAY_PATH = TMP / "trade-grade-risk-sizing-overlay.json"
REPAIR_CONVEYOR_PATH = TMP / "trade-grade-repair-conveyor.json"
READINESS_ROLLUP_PATH = TMP / "trade-grade-os-readiness-rollup.json"
FRESHNESS_RUNNER_PATH = TMP / "trade-grade-os-freshness-cron-runner.json"
DEPLOYMENT_TIMING_PATH = TMP / "wf85-deployment-timing-gate.json"
FULL_ANSWER_ASSEMBLER_PATH = TMP / "trade-grade-full-answer-assembler.json"
CAPITAL_REVIEW_QUEUE_PATH = TMP / "wf78-capital-review-queue.json"

SOURCE_PATHS = {
    "decision_cards": CARDS_PATH,
    "source_freshness_gate": SOURCE_GATE_PATH,
    "authority_validation": AUTHORITY_VALIDATION_PATH,
    "approval_card_gate": APPROVAL_GATE_PATH,
    "risk_sizing_overlay": RISK_OVERLAY_PATH,
    "repair_conveyor": REPAIR_CONVEYOR_PATH,
    "readiness_rollup": READINESS_ROLLUP_PATH,
    "freshness_cron_runner": FRESHNESS_RUNNER_PATH,
    "deployment_timing_gate": DEPLOYMENT_TIMING_PATH,
    "full_answer_assembler": FULL_ANSWER_ASSEMBLER_PATH,
    "capital_review_queue": CAPITAL_REVIEW_QUEUE_PATH,
}

SCHEMA = "veritas.wf85_decision_os_review_packet.v1"
WORKFLOW_ID = "WF85"
TIER_AB = {"Tier A", "Tier B"}

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "decision_support_only": True,
    "repair_queue_routing_only": True,
    "automated_non_capital_routing_allowed": True,
    "approval_card_generation_allowed": False,
    "approval_card_generation_performed": False,
    "capital_deployment_allowed": False,
    "capital_deployment_approved": False,
    "trade_or_execution_allowed": False,
    "trade_or_execution_approved": False,
    "paper_or_live_execution_allowed": False,
    "paper_order_execution_allowed": False,
    "paper_order_submit_allowed": False,
    "paper_order_cancel_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "money_movement_allowed": False,
    "canon_or_portfolio_mutation_allowed": False,
    "cash_sizing_or_risk_rule_mutation_allowed": False,
    "customer_or_external_delivery_allowed": False,
    "owner_approval_inferred": False,
}

FALSE_AUTHORITY_KEYS = [key for key, value in AUTHORITY_BOUNDARY.items() if value is False]

BUCKET_ORDER = [
    "review_ready_wait_fresh_quote",
    "repair_first",
    "review_ready_suppressed",
    "wait_no_chase",
    "blocked_below_stop_or_invalidation",
    "review_ready_wait_approval",
]

BUCKET_ACTIONS = {
    "review_ready_wait_fresh_quote": "Refresh quote/evidence context, then rerun WF85 cards and timing. Do not draft approval.",
    "repair_first": "Work the upstream WF78/WF84 repair lane before treating the ticker as review-ready.",
    "review_ready_suppressed": "Keep suppressed until the earnings, macro, or authority suppressor clears. Do not draft approval.",
    "wait_no_chase": "Hold as no-chase. Refresh later instead of forcing an entry decision.",
    "blocked_below_stop_or_invalidation": "Keep blocked for invalidation or reclaim review. Do not advance toward deployment.",
    "review_ready_wait_approval": "Main-session review only. Randall exact approval and fresh WF67 guards are still required before any paper action.",
}

REPAIR_LANE_ACTIONS = {
    "wf78_source_open_or_owner_lineage_repair": "Repair source-open and owner-lineage evidence before any review-ready language.",
    "primary_state_blocker_repair": "Resolve primary-state blockers, no-chase state, or fresh-quote gaps before review-ready handling.",
    "invalidation_or_below_stop_review_only": "Keep in invalidation or below-stop review; this is not deployment prep.",
    "wf78_band_stop_context_repair": "Repair band/stop context through WF78/WF84 proof before revisiting the card.",
    "wf78_band_context_recheck": "Recheck band context only; do not mutate canon outside the approved entry-band gate.",
    "tier_c_thin_monitor_deferred": "Leave as deferred thin-monitor work unless promoted by WF78.",
    "review_ready_waiting_approval_gate": "Owner review gate only; no execution or inferred approval.",
}

STOP_LINES = [
    "No capital deployment approval.",
    "No trade, paper, live, brokerage, account, or money-movement action.",
    "No approval-card generation in this packet.",
    "No canon, portfolio, cash, sizing, or risk-rule mutation.",
    "No owner approval inference from any card, score, SQL row, queue row, or packet row.",
]


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


def int_value(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def validation_status(payload: dict[str, Any]) -> str:
    validation = as_dict(payload.get("validation"))
    if validation.get("status"):
        return str(validation.get("status"))
    errors = as_list(validation.get("errors"))
    warnings = as_list(validation.get("warnings"))
    if errors:
        return "error"
    if warnings:
        return "warning"
    return str(payload.get("validation_status") or payload.get("status") or "unknown")


def load_payload(path: Path) -> dict[str, Any]:
    payload = load_json_artifact(path)
    return payload if isinstance(payload, dict) else {}


def load_inputs(paths: dict[str, Path] = SOURCE_PATHS) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
    payloads: dict[str, dict[str, Any]] = {}
    records: list[dict[str, Any]] = []
    for key, path in paths.items():
        payload = load_payload(path)
        payloads[key] = payload
        records.append({
            "key": key,
            "path": rel(path),
            "exists": path.exists(),
            "loaded": bool(payload),
            "schema": payload.get("schema"),
            "status": payload.get("status"),
            "generated_at_utc": payload.get("generated_at_utc"),
            "validation_status": validation_status(payload) if payload else "missing_or_unreadable",
        })
    return payloads, records


def rows_by_ticker(payload: dict[str, Any], key: str = "rows") -> dict[str, dict[str, Any]]:
    output: dict[str, dict[str, Any]] = {}
    for row in as_list(payload.get(key)):
        if not isinstance(row, dict):
            continue
        ticker = str(row.get("ticker") or "").upper()
        if ticker:
            output[ticker] = row
    return output


def cards_by_ticker(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return rows_by_ticker({"rows": as_list(payload.get("cards"))})


def sorted_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        rows,
        key=lambda row: (
            BUCKET_ORDER.index(str(row.get("final_timing_state")))
            if str(row.get("final_timing_state")) in BUCKET_ORDER
            else len(BUCKET_ORDER),
            -int_value(row.get("repair_priority")),
            str(row.get("ticker") or ""),
        ),
    )


def row_blockers(timing_row: dict[str, Any], repair_row: dict[str, Any]) -> list[str]:
    blockers: list[str] = []
    for key in ("final_timing_reasons", "price_band_reasons", "quote_reasons", "earnings_reasons", "macro_sector_reasons"):
        blockers.extend(str(item) for item in as_list(timing_row.get(key)) if item)
    blockers.extend(str(item) for item in as_list(repair_row.get("blockers")) if item)
    seen: set[str] = set()
    deduped: list[str] = []
    for blocker in blockers:
        if blocker not in seen:
            seen.add(blocker)
            deduped.append(blocker)
    return deduped


def design_intent_note(final_state: str, repair_lane: str, blockers: list[str]) -> str:
    if repair_lane == "wf78_source_open_or_owner_lineage_repair":
        return "Repair official-source and owner-lineage evidence before treating the row as decision-grade."
    if repair_lane == "tier_c_thin_monitor_deferred":
        return "Tier C thin-monitor visibility is intentional review debt, not a Tier A/B promotion or deployment signal."
    if final_state == "review_ready_wait_fresh_quote":
        return "Closest to review-ready, but fresh quote/evidence context must be rerun before any approval-card drafting."
    if final_state == "repair_first":
        return "Evidence repair outranks price momentum; do not advance until blockers are cleared."
    if final_state == "review_ready_suppressed":
        return "Suppression is intentional until earnings, macro, or authority gates clear."
    if final_state == "wait_no_chase":
        return "No-chase state is intentional entry discipline; do not force a deployment decision."
    if final_state == "blocked_below_stop_or_invalidation":
        return "Below-stop or invalidation state blocks deployment prep until reclaim review clears."
    if final_state == "review_ready_wait_approval":
        return "Owner-review surface only; Randall exact approval and WF67 guards are still required before paper action."
    if blockers:
        return "Preserve blockers as repair context; do not convert this row into approval language."
    return "Review-only routing context; inspect source artifacts before any downstream action."


def build_review_rows(payloads: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    timing_rows = [
        row for row in as_list(payloads["deployment_timing_gate"].get("rows"))
        if isinstance(row, dict) and row.get("auto_tier") in TIER_AB
    ]
    repair_rows = rows_by_ticker(payloads["repair_conveyor"])
    card_rows = cards_by_ticker(payloads["decision_cards"])
    output: list[dict[str, Any]] = []
    for timing in timing_rows:
        ticker = str(timing.get("ticker") or "").upper()
        repair = repair_rows.get(ticker, {})
        card = card_rows.get(ticker, {})
        final_state = str(timing.get("final_timing_state") or "unknown")
        repair_lane = str(repair.get("repair_lane") or "unmapped")
        blockers = row_blockers(timing, repair)
        output.append({
            "ticker": ticker,
            "name": timing.get("name") or card.get("name"),
            "auto_tier": timing.get("auto_tier"),
            "auto_state": timing.get("auto_state") or repair.get("auto_state") or card.get("auto_state"),
            "final_timing_state": final_state,
            "decision_state": timing.get("decision_state") or repair.get("decision_state") or card.get("decision_state"),
            "primary_state": repair.get("primary_state") or card.get("primary_state"),
            "repair_lane": repair_lane,
            "repair_scope": repair.get("repair_scope"),
            "repair_priority": repair.get("repair_priority"),
            "source_open_status": repair.get("source_open_status"),
            "freshness_status": repair.get("freshness_status"),
            "quote_freshness_status": repair.get("quote_freshness_status"),
            "band_status": repair.get("band_status") or as_dict(timing.get("entry_band")).get("band_status"),
            "price_band_gate": timing.get("price_band_gate"),
            "quote_freshness_class": timing.get("quote_freshness_class"),
            "earnings_gate": timing.get("earnings_gate"),
            "macro_sector_gate": timing.get("macro_sector_gate"),
            "blockers": blockers,
            "design_intent_note": design_intent_note(final_state, repair_lane, blockers),
            "next_safe_action": repair.get("next_action") or BUCKET_ACTIONS.get(final_state, "Keep review-only; rerun owner artifacts before action."),
            "authority_boundary": {
                "capital_deployment_approved": False,
                "trade_or_execution_approved": False,
                "paper_or_live_execution_allowed": False,
                "owner_approval_inferred": False,
            },
        })
    return sorted_rows(output)


def build_buckets(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        buckets[str(row.get("final_timing_state") or "unknown")].append(row)
    output: dict[str, dict[str, Any]] = {}
    for state in list(BUCKET_ORDER) + sorted(k for k in buckets if k not in BUCKET_ORDER):
        group = sorted_rows(buckets.get(state, []))
        output[state] = {
            "count": len(group),
            "tickers": [str(row.get("ticker")) for row in group],
            "next_safe_action": BUCKET_ACTIONS.get(state, "Keep review-only and inspect source artifacts before action."),
            "rows": group,
        }
    return output


def build_repair_lanes(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    lanes: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        lanes[str(row.get("repair_lane") or "unmapped")].append(row)
    output: dict[str, dict[str, Any]] = {}
    for lane, group in sorted(lanes.items(), key=lambda item: (-len(item[1]), item[0])):
        ordered = sorted_rows(group)
        output[lane] = {
            "count": len(ordered),
            "tickers": [str(row.get("ticker")) for row in ordered],
            "next_safe_action": REPAIR_LANE_ACTIONS.get(lane, "Treat as finance-domain repair routing only."),
            "rows": ordered,
        }
    return output


def ranked_next_actions(buckets: dict[str, dict[str, Any]], repair_lanes: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    actions: list[dict[str, Any]] = []
    fresh_quote = as_dict(buckets.get("review_ready_wait_fresh_quote"))
    if int_value(fresh_quote.get("count")):
        actions.append({
            "rank": 1,
            "action": "fresh_quote_refresh",
            "count": fresh_quote.get("count"),
            "tickers": fresh_quote.get("tickers"),
            "why": "These names are closest to review-ready but lack fresh executable-context quotes.",
            "authority": "review_only_no_approval",
        })
    source_lane = as_dict(repair_lanes.get("wf78_source_open_or_owner_lineage_repair"))
    if int_value(source_lane.get("count")):
        actions.append({
            "rank": len(actions) + 1,
            "action": "source_open_owner_lineage_repair",
            "count": source_lane.get("count"),
            "tickers": source_lane.get("tickers"),
            "why": "Source-open/owner-lineage gaps block trusted decision-grade language.",
            "authority": "finance_domain_repair_only",
        })
    primary_lane = as_dict(repair_lanes.get("primary_state_blocker_repair"))
    if int_value(primary_lane.get("count")):
        actions.append({
            "rank": len(actions) + 1,
            "action": "primary_state_blocker_repair",
            "count": primary_lane.get("count"),
            "tickers": primary_lane.get("tickers"),
            "why": "Primary state, no-chase, or quote blockers stop review-ready handling.",
            "authority": "finance_domain_repair_only",
        })
    suppressed = as_dict(buckets.get("review_ready_suppressed"))
    if int_value(suppressed.get("count")):
        actions.append({
            "rank": len(actions) + 1,
            "action": "suppression_review",
            "count": suppressed.get("count"),
            "tickers": suppressed.get("tickers"),
            "why": "These names would otherwise look close, but earnings/macro/authority suppressors still apply.",
            "authority": "review_only_no_approval",
        })
    invalidation = as_dict(buckets.get("blocked_below_stop_or_invalidation"))
    if int_value(invalidation.get("count")):
        actions.append({
            "rank": len(actions) + 1,
            "action": "invalidation_reclaim_review",
            "count": invalidation.get("count"),
            "tickers": invalidation.get("tickers"),
            "why": "Below-stop or invalidation rows should not consume approval-card prep time.",
            "authority": "review_only_no_deployment",
        })
    for idx, action in enumerate(actions, start=1):
        action["rank"] = idx
    return actions


def summarize(payloads: dict[str, dict[str, Any]], rows: list[dict[str, Any]]) -> dict[str, Any]:
    card_summary = as_dict(payloads["decision_cards"].get("summary"))
    approval_summary = as_dict(payloads["approval_card_gate"].get("summary"))
    authority_summary = as_dict(payloads["authority_validation"].get("summary"))
    repair_summary = as_dict(payloads["repair_conveyor"].get("summary"))
    timing_summary = as_dict(payloads["deployment_timing_gate"].get("summary"))
    full_summary = as_dict(payloads["full_answer_assembler"].get("summary"))
    capital_queue_summary = as_dict(payloads["capital_review_queue"].get("summary"))
    freshness_summary = as_dict(payloads["freshness_cron_runner"].get("summary"))
    source_summary = as_dict(payloads["source_freshness_gate"].get("summary"))
    readiness = as_dict(payloads["readiness_rollup"].get("trade_grade_data_readiness"))
    final_counts = Counter(str(row.get("final_timing_state") or "unknown") for row in rows)
    repair_counts = Counter(str(row.get("repair_lane") or "unmapped") for row in rows)
    return {
        "card_count": card_summary.get("card_count"),
        "decision_state_counts": card_summary.get("decision_state_counts"),
        "approval_card_draft_count": approval_summary.get("approval_card_draft_count", card_summary.get("approval_card_draft_count")),
        "approval_gate_review_ready_count": approval_summary.get("review_ready_count"),
        "approval_band_eligible_count": approval_summary.get("approval_band_eligible_count"),
        "capital_review_candidate_count": capital_queue_summary.get("candidate_count"),
        "capital_review_ready_count": capital_queue_summary.get("review_ready_count"),
        "authority_false_violation_count": authority_summary.get("false_authority_violation_count"),
        "forbidden_action_phrase_count": authority_summary.get("forbidden_action_phrase_count"),
        "full_answer_built_count": full_summary.get("full_answer_built_count"),
        "full_answer_validation_error_count": full_summary.get("validation_error_count"),
        "required_section_count": full_summary.get("required_section_count"),
        "repair_row_count": repair_summary.get("total_repair_conveyor_row_count", repair_summary.get("card_count")),
        "finance_domain_repair_item_count": repair_summary.get("finance_domain_repair_item_count"),
        "implementation_blocker_count": repair_summary.get("implementation_blocker_count"),
        "pm_blocker_scope": repair_summary.get("pm_blocker_scope"),
        "implementation_queue_posture": repair_summary.get("implementation_queue_posture"),
        "wf67_paper_guard_fresh": approval_summary.get("wf67_paper_guard_fresh"),
        "wf67_paper_guard_clean": approval_summary.get("wf67_paper_guard_clean"),
        "wf67_paper_guard_status": approval_summary.get("wf67_paper_guard_status"),
        "source_open_status_counts": source_summary.get("source_open_status_counts"),
        "freshness_status_counts": source_summary.get("freshness_status_counts"),
        "trade_grade_data_ready_for_decisions": freshness_summary.get("trade_grade_data_ready_for_decisions"),
        "trade_grade_data_readiness_status": freshness_summary.get("trade_grade_data_readiness_status"),
        "trade_grade_data_readiness_rollup_ready": readiness.get("ready_for_trade_grade_decisions"),
        "tier_a_b_row_count": timing_summary.get("tier_a_b_row_count", len(rows)),
        "tier_a_b_final_timing_state_counts": dict(final_counts),
        "tier_a_b_repair_lane_counts": dict(repair_counts),
        "design_intent_note_count": len([row for row in rows if row.get("design_intent_note")]),
        "next_safe_action": "Use ranked Tier A/B actions as review/repair routing only; do not draft approval cards or execute orders from this packet.",
    }


def validate_packet(
    payloads: dict[str, dict[str, Any]],
    source_records: list[dict[str, Any]],
    rows: list[dict[str, Any]],
    summary: dict[str, Any],
) -> dict[str, list[str]]:
    errors: list[str] = []
    warnings: list[str] = []

    missing = [record["key"] for record in source_records if not record.get("exists") or not record.get("loaded")]
    if missing:
        errors.append(f"missing_or_unreadable_sources:{','.join(missing)}")

    for key in FALSE_AUTHORITY_KEYS:
        if AUTHORITY_BOUNDARY.get(key) is not False:
            errors.append(f"authority_boundary_not_false:{key}")
    for row in rows:
        row_boundary = as_dict(row.get("authority_boundary"))
        for key in ("capital_deployment_approved", "trade_or_execution_approved", "paper_or_live_execution_allowed", "owner_approval_inferred"):
            if row_boundary.get(key) is not False:
                errors.append(f"row_authority_boundary_not_false:{row.get('ticker')}:{key}")

    if int_value(summary.get("authority_false_violation_count")):
        errors.append("source_authority_validation_has_false_authority_violations")
    if int_value(summary.get("forbidden_action_phrase_count")):
        errors.append("source_authority_validation_has_forbidden_action_phrases")
    if int_value(summary.get("implementation_blocker_count")):
        errors.append("repair_conveyor_reports_implementation_blockers")

    timing_summary = as_dict(payloads["deployment_timing_gate"].get("summary"))
    expected_counts = as_dict(timing_summary.get("tier_a_b_final_timing_state_counts"))
    actual_counts = summary.get("tier_a_b_final_timing_state_counts") or {}
    if expected_counts and {str(k): int_value(v) for k, v in expected_counts.items()} != {str(k): int_value(v) for k, v in actual_counts.items()}:
        errors.append("tier_a_b_timing_bucket_reconciliation_mismatch")
    expected_total = int_value(timing_summary.get("tier_a_b_row_count"))
    if expected_total and expected_total != len(rows):
        errors.append(f"tier_a_b_row_count_mismatch:{len(rows)}!={expected_total}")

    if int_value(summary.get("approval_card_draft_count")):
        warnings.append("approval_card_drafts_present_in_source_gate_requires_exact_owner_review")
    if int_value(summary.get("capital_review_candidate_count")):
        warnings.append("capital_review_queue_candidates_present_review_only")
    if summary.get("wf67_paper_guard_fresh") is not True or summary.get("wf67_paper_guard_clean") is not True:
        warnings.append("wf67_paper_guard_not_fresh_or_clean_no_paper_posture")
    if payloads["readiness_rollup"].get("status") not in {"ok", None}:
        warnings.append(f"readiness_rollup_status={payloads['readiness_rollup'].get('status')}")
    if int_value(as_dict(summary.get("tier_a_b_final_timing_state_counts")).get("repair_first")):
        warnings.append("tier_a_b_repair_first_rows_present")
    if int_value(as_dict(summary.get("tier_a_b_final_timing_state_counts")).get("review_ready_suppressed")):
        warnings.append("review_ready_suppressed_rows_present")

    return {"errors": errors, "warnings": warnings}


def build_packet(
    payloads: dict[str, dict[str, Any]],
    source_records: list[dict[str, Any]] | None = None,
    *,
    generated_at_utc: str | None = None,
) -> dict[str, Any]:
    generated = generated_at_utc or utc_now()
    records = source_records or [
        {
            "key": key,
            "path": None,
            "exists": True,
            "loaded": bool(payload),
            "schema": payload.get("schema"),
            "status": payload.get("status"),
            "generated_at_utc": payload.get("generated_at_utc"),
            "validation_status": validation_status(payload) if payload else "missing_or_unreadable",
        }
        for key, payload in payloads.items()
    ]
    rows = build_review_rows(payloads)
    buckets = build_buckets(rows)
    repair_lanes = build_repair_lanes(rows)
    summary = summarize(payloads, rows)
    validation = validate_packet(payloads, records, rows, summary)
    status = "error" if validation["errors"] else "warning" if validation["warnings"] else "ok"
    return {
        "schema": SCHEMA,
        "generated_at_utc": generated,
        "workflow_id": WORKFLOW_ID,
        "status": status,
        "purpose": "Rank the WF85 Tier A/B review and repair surface without approval, execution, or portfolio mutation authority.",
        "authority_boundary": AUTHORITY_BOUNDARY,
        "summary": summary,
        "ranked_next_actions": ranked_next_actions(buckets, repair_lanes),
        "tier_a_b_review": {
            "row_count": len(rows),
            "bucket_order": BUCKET_ORDER,
            "buckets": buckets,
        },
        "repair_lanes": repair_lanes,
        "source_artifacts": records,
        "validation": validation,
        "stop_lines": STOP_LINES,
    }


def build_payload(paths: dict[str, Path] = SOURCE_PATHS) -> dict[str, Any]:
    payloads, records = load_inputs(paths)
    return build_packet(payloads, records)


def render_markdown(payload: dict[str, Any]) -> str:
    summary = as_dict(payload.get("summary"))
    actions = as_list(payload.get("ranked_next_actions"))
    buckets = as_dict(as_dict(payload.get("tier_a_b_review")).get("buckets"))
    lines = [
        "# WF85 Decision OS Review Packet",
        "",
        f"- Status: `{payload.get('status')}`",
        f"- Generated: `{payload.get('generated_at_utc')}`",
        f"- Cards: `{summary.get('card_count')}`",
        f"- Tier A/B rows: `{summary.get('tier_a_b_row_count')}`",
        f"- Approval-card drafts: `{summary.get('approval_card_draft_count')}`",
        f"- Capital-review candidates: `{summary.get('capital_review_candidate_count')}`",
        f"- Authority violations: `{summary.get('authority_false_violation_count')}`",
        f"- WF67 paper guard: `{summary.get('wf67_paper_guard_status')}`",
        "",
        "## Ranked Next Actions",
        "",
    ]
    if actions:
        for action in actions:
            tickers = ", ".join(str(ticker) for ticker in as_list(action.get("tickers")))
            lines.extend([
                f"{action.get('rank')}. `{action.get('action')}` - `{action.get('count')}` rows",
                f"   - Tickers: {tickers or 'none'}",
                f"   - Why: {action.get('why')}",
                f"   - Authority: `{action.get('authority')}`",
            ])
    else:
        lines.append("- No ranked Tier A/B actions available.")
    lines.extend(["", "## Tier A/B Buckets", ""])
    for state in BUCKET_ORDER:
        bucket = as_dict(buckets.get(state))
        if not bucket:
            continue
        tickers = ", ".join(str(ticker) for ticker in as_list(bucket.get("tickers")))
        lines.extend([
            f"### {state}",
            "",
            f"- Count: `{bucket.get('count')}`",
            f"- Tickers: {tickers or 'none'}",
            f"- Next safe action: {bucket.get('next_safe_action')}",
            "",
        ])
    lines.extend(["## Boundary", ""])
    for stop in STOP_LINES:
        lines.append(f"- {stop}")
    lines.append("")
    return "\n".join(lines)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--md-out", type=Path, default=DEFAULT_MD_OUT)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--write-md", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--pretty", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    payload = build_payload()
    out = args.out if args.out.is_absolute() else ROOT / args.out
    md_out = args.md_out if args.md_out.is_absolute() else ROOT / args.md_out
    if args.write:
        atomic_write_json(out, payload)
    if args.write_md:
        md_out.parent.mkdir(parents=True, exist_ok=True)
        md_out.write_text(render_markdown(payload), encoding="utf-8", newline="\n")
    if args.write:
        print(
            "wrote {path} status={status} tier_ab={tier_ab} actions={actions}".format(
                path=rel(out),
                status=payload.get("status"),
                tier_ab=as_dict(payload.get("summary")).get("tier_a_b_row_count"),
                actions=len(as_list(payload.get("ranked_next_actions"))),
            )
        )
    else:
        print(json.dumps(payload, indent=2 if args.pretty else None, sort_keys=True))
    for item in as_list(as_dict(payload.get("validation")).get("errors")):
        print(f"  [error] {item}")
    for item in as_list(as_dict(payload.get("validation")).get("warnings")):
        print(f"  [warning] {item}")
    if args.validate and as_list(as_dict(payload.get("validation")).get("errors")):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
