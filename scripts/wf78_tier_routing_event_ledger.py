#!/usr/bin/env python3
"""Append-only WF78 tier/routing movement event ledger.

This script turns the rolling WF78 routing delta into a durable JSONL event
trail. It is intentionally narrow: it records derived non-capital routing
events and publishes a compact summary for cron/main-session handoff. It does
not mutate the universe, ticker cards, SQL canon, portfolio notes, broker
state, account state, or any execution surface.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, atomic_write_text, load_json_artifact

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
STATE = ROOT / "state" / "workflows"

DEFAULT_DELTA = TMP / "wf78-routing-delta.json"
DEFAULT_AUTO_ROUTER = TMP / "wf78-auto-tier-routing.json"
DEFAULT_DAILY_MOVEMENT = TMP / "wf78-daily-movement-ledger.json"
DEFAULT_FRESHNESS = TMP / "wf78-tier-weighted-freshness-resolution.json"
DEFAULT_COVERAGE = TMP / "tier-a-trade-grade-coverage-gate.json"
DEFAULT_CONFIDENCE = TMP / "wf78-tier-a-confidence-gate.json"
DEFAULT_LEDGER = STATE / "wf78-tier-routing-events.jsonl"
DEFAULT_OUT = TMP / "wf78-tier-routing-event-ledger.json"
DEFAULT_MD = TMP / "wf78-tier-routing-event-ledger.md"

SCHEMA = "veritas.wf78_tier_routing_event_ledger.v1"
EVENT_SCHEMA = "veritas.wf78_tier_routing_event.v1"

AUTHORITY_BOUNDARY: dict[str, bool] = {
    "review_only": True,
    "append_only_event_ledger": True,
    "derived_routing_history_only": True,
    "automated_non_capital_routing_allowed": True,
    "universe_mutation_allowed": False,
    "ticker_card_mutation_allowed": False,
    "canon_or_portfolio_mutation_allowed": False,
    "sql_canon_mutation_allowed": False,
    "customer_or_external_delivery_allowed": False,
    "capital_deployment_allowed": False,
    "capital_deployment_approved": False,
    "trade_or_execution_allowed": False,
    "trade_or_execution_approved": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "money_movement_allowed": False,
    "owner_approval_inferred": False,
}

EVENT_AUTHORITY_BOUNDARY: dict[str, bool] = {
    "automated_non_capital_routing_allowed": True,
    "capital_deployment_approved": False,
    "trade_or_execution_approved": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "money_movement_allowed": False,
    "owner_approval_inferred": False,
}

REQUIRED_TRUE_FLAGS = {
    "review_only",
    "append_only_event_ledger",
    "derived_routing_history_only",
    "automated_non_capital_routing_allowed",
}
REQUIRED_FALSE_FLAGS = {flag for flag in AUTHORITY_BOUNDARY if flag not in REQUIRED_TRUE_FLAGS}

DELTA_SECTIONS = {
    "promotions": "promotion",
    "demotions": "demotion",
    "state_changes": "state_change",
    "added": "added",
    "removed": "removed",
}

DAILY_DECISION_EVENT_TYPES = {
    "promote": "promotion",
    "demote": "demotion",
    "state_change": "state_change",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def resolve(path: Path) -> Path:
    return path if path.is_absolute() else ROOT / path


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def load_dict(path: Path) -> dict[str, Any]:
    payload = load_json_artifact(path)
    return payload if isinstance(payload, dict) else {}


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def stable_hash(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def row_list_by_ticker(rows: Any) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for row in as_list(rows):
        if isinstance(row, dict) and row.get("ticker"):
            result[ticker_key(row.get("ticker"))] = row
    return result


def coverage_row_by_ticker(coverage: dict[str, Any], ticker: str) -> dict[str, Any]:
    cohorts = as_dict(coverage.get("cohorts"))
    for cohort_name in ("router_tier_a", "data_plane_tier_a", "finance_canon_tier_a", "data_plane_a_ready", "finance_canon_a_ready"):
        row = row_list_by_ticker(cohorts.get(cohort_name)).get(ticker)
        if row:
            return row
    return {}


def proof_context(freshness_path: Path, coverage_path: Path, confidence_path: Path) -> dict[str, Any]:
    freshness = load_dict(freshness_path)
    coverage = load_dict(coverage_path)
    confidence = load_dict(confidence_path)
    return {
        "freshness": freshness,
        "coverage": coverage,
        "confidence": confidence,
        "freshness_rows": row_list_by_ticker(freshness.get("rows")),
        "confidence_rows": row_list_by_ticker(confidence.get("rows")),
        "source_artifacts": [rel(freshness_path), rel(coverage_path), rel(confidence_path)],
    }


def gate_verdicts_for_event(event: dict[str, Any], auto_router: dict[str, Any], proofs: dict[str, Any]) -> dict[str, Any]:
    ticker = ticker_key(event.get("ticker"))
    route_row = row_list_by_ticker(auto_router.get("rows")).get(ticker, {})
    freshness_row = as_dict(proofs.get("freshness_rows")).get(ticker, {})
    coverage = as_dict(proofs.get("coverage"))
    coverage_row = coverage_row_by_ticker(coverage, ticker)
    confidence_row = as_dict(proofs.get("confidence_rows")).get(ticker, {})
    coverage_summary = as_dict(coverage.get("summary"))
    stale_reasons = as_list(route_row.get("tier_a_packet_stale_reasons"))
    if stale_reasons:
        freshness_verdict = str(stale_reasons[0])
    else:
        freshness_verdict = (
            route_row.get("tier_a_packet_freshness_status")
            or freshness_row.get("resolution_state")
            or freshness_row.get("freshness_status")
            or "unknown"
        )
    coverage_floor = "unknown"
    if coverage_row:
        coverage_floor = "ok" if coverage_row.get("coverage_floor_passed") is True else "blocked"
    depth = "unknown"
    if coverage_row:
        depth = "ready" if coverage_row.get("depth_ready") is True else "blocked"
    decision_grade_allowed = (
        coverage_row.get("decision_grade_claim_allowed") is True
        and int(coverage_summary.get("decision_grade_allowed_count") or 0) > 0
        and coverage_summary.get("tier_definition_aligned") is True
    )
    return {
        "freshness": freshness_verdict,
        "coverage_floor": coverage_floor,
        "depth": depth,
        "confidence": confidence_row.get("promotion_effect") or confidence_row.get("tier_a_confidence_status") or "unknown",
        "decision_grade_allowed": decision_grade_allowed,
        "quote_time_utc": route_row.get("tier_a_packet_quote_time_utc") or freshness_row.get("quote_time_utc"),
        "quote_age_hours": route_row.get("tier_a_packet_quote_age_hours") or freshness_row.get("quote_age_hours"),
        "quote_ttl_hours": route_row.get("tier_a_packet_quote_ttl_hours") or freshness_row.get("quote_ttl_hours"),
        "packet_age_hours": route_row.get("tier_a_packet_age_hours"),
        "packet_ttl_hours": route_row.get("tier_a_packet_ttl_hours"),
        "coverage_status": coverage_row.get("status"),
        "coverage_depth_blockers": as_list(coverage_row.get("depth_blockers")),
        "coverage_floor_blockers": as_list(coverage_row.get("floor_blockers")),
        "coverage_gate_decision_grade_allowed_count": coverage_summary.get("decision_grade_allowed_count"),
        "tier_definition_aligned": coverage_summary.get("tier_definition_aligned"),
        "critical_data_conflict_count": confidence_row.get("critical_conflict_count"),
        "proof_generated_at_utc": {
            "freshness": as_dict(proofs.get("freshness")).get("generated_at_utc"),
            "coverage": coverage.get("generated_at_utc"),
            "confidence": as_dict(proofs.get("confidence")).get("generated_at_utc"),
        },
        "source_artifacts": proofs.get("source_artifacts"),
        "authority_boundary": EVENT_AUTHORITY_BOUNDARY,
    }


def enrich_event(event: dict[str, Any], auto_router: dict[str, Any], proofs: dict[str, Any]) -> dict[str, Any]:
    if event.get("event_type") == "promotion":
        event = dict(event)
        event["gate_verdicts"] = gate_verdicts_for_event(event, auto_router, proofs)
    return event


def source_day(timestamp: Any) -> str:
    text = str(timestamp or "")
    return text[:10] if len(text) >= 10 else "unknown"


def ticker_key(value: Any) -> str:
    return str(value or "").strip().upper()


def add_check(
    checks: list[dict[str, Any]],
    name: str,
    ok: bool,
    detail: Any = None,
    severity: str = "critical",
) -> None:
    checks.append({"name": name, "ok": bool(ok), "status": "ok" if ok else "fail", "severity": severity, "detail": detail})


def read_jsonl(path: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if not path.exists():
        return [], []
    events: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    for line_number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw_line.strip()
        if not line:
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            errors.append({"line": line_number, "error": str(exc)})
            continue
        if isinstance(value, dict):
            events.append(value)
        else:
            errors.append({"line": line_number, "error": "line is not a JSON object"})
    return events, errors


def write_jsonl_append(path: Path, events: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text("", encoding="utf-8")
    if not events:
        return
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        for event in events:
            handle.write(canonical_json(event) + "\n")


def event_key(event: dict[str, Any]) -> dict[str, Any]:
    return {
        "event_source": event.get("event_source"),
        "source_day": event.get("source_day"),
        "changed_since_utc": event.get("changed_since_utc"),
        "ticker": event.get("ticker"),
        "event_type": event.get("event_type"),
        "prior_auto_tier": event.get("prior_auto_tier"),
        "current_auto_tier": event.get("current_auto_tier"),
        "prior_auto_state": event.get("prior_auto_state"),
        "current_auto_state": event.get("current_auto_state"),
        "reason_code": event.get("reason_code"),
    }


def finalize_event(event: dict[str, Any]) -> dict[str, Any]:
    event["event_id"] = stable_hash(event_key(event))[:32]
    return event


def normalize_delta_event(
    row: dict[str, Any],
    event_type: str,
    delta: dict[str, Any],
    delta_path: Path,
    auto_router_path: Path,
) -> dict[str, Any] | None:
    ticker = ticker_key(row.get("ticker"))
    if not ticker:
        return None
    generated_at = delta.get("generated_at_utc")
    if event_type == "added":
        prior_tier = None
        prior_state = None
        current_tier = row.get("auto_tier")
        current_state = row.get("auto_state")
    elif event_type == "removed":
        prior_tier = row.get("prior_auto_tier") or row.get("auto_tier")
        prior_state = row.get("prior_auto_state") or row.get("auto_state")
        current_tier = None
        current_state = None
    else:
        prior_tier = row.get("prior_auto_tier")
        prior_state = row.get("prior_auto_state")
        current_tier = row.get("current_auto_tier")
        current_state = row.get("current_auto_state")
    reason = row.get("route_reason") or f"routing_delta_{event_type}"
    return finalize_event({
        "schema": EVENT_SCHEMA,
        "workflow": "WF78",
        "event_source": "routing_delta",
        "event_type": event_type,
        "source_quality": "direct_delta",
        "source_day": source_day(generated_at),
        "event_observed_at_utc": generated_at,
        "changed_since_utc": delta.get("changed_since"),
        "ticker": ticker,
        "prior_auto_tier": prior_tier,
        "current_auto_tier": current_tier,
        "prior_auto_state": prior_state,
        "current_auto_state": current_state,
        "reason_code": reason,
        "route_reason": row.get("route_reason"),
        "source_artifacts": [rel(delta_path), rel(auto_router_path)],
        "source_hashes": {
            "routing_delta_event_key_sha256": stable_hash({
                "section_event_type": event_type,
                "delta_generated_at_utc": generated_at,
                "row": row,
            }),
        },
        "authority_boundary": EVENT_AUTHORITY_BOUNDARY,
    })


def events_from_delta(delta: dict[str, Any], delta_path: Path, auto_router_path: Path) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for section, event_type in DELTA_SECTIONS.items():
        for row in as_list(delta.get(section)):
            if not isinstance(row, dict):
                continue
            event = normalize_delta_event(row, event_type, delta, delta_path, auto_router_path)
            if event:
                events.append(event)
    return events


def events_from_daily_movement_backfill(daily: dict[str, Any], daily_path: Path, auto_router_path: Path) -> list[dict[str, Any]]:
    generated_at = daily.get("generated_at_utc")
    moved_today = as_list(as_dict(daily.get("categories")).get("moved_today"))
    events: list[dict[str, Any]] = []
    for row in moved_today:
        if not isinstance(row, dict):
            continue
        decision = str(row.get("decision") or "")
        event_type = DAILY_DECISION_EVENT_TYPES.get(decision)
        ticker = ticker_key(row.get("ticker"))
        if not event_type or not ticker:
            continue
        reason = row.get("reason_code") or f"daily_movement_{decision}"
        events.append(finalize_event({
            "schema": EVENT_SCHEMA,
            "workflow": "WF78",
            "event_source": "daily_movement_ledger_backfill",
            "event_type": event_type,
            "source_quality": "partial_backfill_missing_prior_fields",
            "source_day": source_day(generated_at),
            "event_observed_at_utc": generated_at,
            "changed_since_utc": None,
            "ticker": ticker,
            "prior_auto_tier": None,
            "current_auto_tier": row.get("auto_tier"),
            "prior_auto_state": None,
            "current_auto_state": row.get("auto_state"),
            "reason_code": reason,
            "route_reason": row.get("route_reason"),
            "source_artifacts": [rel(daily_path), rel(auto_router_path)],
            "source_hashes": {
                "daily_movement_event_key_sha256": stable_hash({
                    "source_day": source_day(generated_at),
                    "ticker": ticker,
                    "decision": decision,
                    "current_auto_tier": row.get("auto_tier"),
                    "current_auto_state": row.get("auto_state"),
                    "reason_code": reason,
                }),
            },
            "authority_boundary": EVENT_AUTHORITY_BOUNDARY,
        }))
    return events


def candidate_events(
    delta: dict[str, Any],
    delta_path: Path,
    auto_router_path: Path,
    daily_movement: dict[str, Any],
    daily_movement_path: Path,
    include_daily_movement_backfill: bool,
) -> list[dict[str, Any]]:
    events = events_from_delta(delta, delta_path, auto_router_path)
    if include_daily_movement_backfill:
        events.extend(events_from_daily_movement_backfill(daily_movement, daily_movement_path, auto_router_path))
    deduped: dict[str, dict[str, Any]] = {}
    for event in events:
        deduped.setdefault(str(event.get("event_id")), event)
    return list(deduped.values())


def event_observed_sort_key(event: dict[str, Any]) -> tuple[str, str]:
    return (str(event.get("event_observed_at_utc") or ""), str(event.get("event_id") or ""))


def authority_false_ok(event: dict[str, Any]) -> bool:
    boundary = as_dict(event.get("authority_boundary"))
    return all(boundary.get(flag) is False for flag in (
        "capital_deployment_approved",
        "trade_or_execution_approved",
        "paper_or_live_execution_allowed",
        "brokerage_or_account_action_allowed",
        "money_movement_allowed",
        "owner_approval_inferred",
    ))


def build_report(
    delta_path: Path,
    auto_router_path: Path,
    daily_movement_path: Path,
    freshness_path: Path,
    coverage_path: Path,
    confidence_path: Path,
    ledger_path: Path,
    include_daily_movement_backfill: bool,
    write: bool,
) -> dict[str, Any]:
    delta = load_dict(delta_path)
    auto_router = load_dict(auto_router_path)
    daily_movement = load_dict(daily_movement_path)
    proofs = proof_context(freshness_path, coverage_path, confidence_path)
    existing_events, parse_errors = read_jsonl(ledger_path)
    candidates = [
        enrich_event(event, auto_router, proofs)
        for event in candidate_events(
        delta,
        delta_path,
        auto_router_path,
        daily_movement,
        daily_movement_path,
        include_daily_movement_backfill,
        )
    ]
    existing_ids = {str(event.get("event_id")) for event in existing_events if event.get("event_id")}
    new_events = [event for event in candidates if str(event.get("event_id")) not in existing_ids]
    if write:
        write_jsonl_append(ledger_path, new_events)
        existing_events, parse_errors = read_jsonl(ledger_path)

    all_ids = [str(event.get("event_id")) for event in existing_events if event.get("event_id")]
    duplicate_ids = sorted(event_id for event_id, count in Counter(all_ids).items() if count > 1)
    event_type_counts = Counter(str(event.get("event_type") or "unknown") for event in existing_events)
    source_counts = Counter(str(event.get("event_source") or "unknown") for event in existing_events)
    ticker_counts = Counter(str(event.get("ticker") or "unknown") for event in existing_events)
    sorted_events = sorted(existing_events, key=event_observed_sort_key)
    recent_events = sorted_events[-20:]

    checks: list[dict[str, Any]] = []
    add_check(checks, "routing_delta_present", bool(delta), rel(delta_path))
    add_check(checks, "auto_router_present", bool(auto_router), rel(auto_router_path))
    add_check(checks, "routing_delta_status_ok", delta.get("status") in {"ok", None}, delta.get("status"))
    add_check(checks, "auto_router_status_ok", auto_router.get("status") in {"ok", None}, auto_router.get("status"))
    add_check(checks, "ledger_jsonl_parseable", not parse_errors, parse_errors)
    add_check(checks, "event_ids_unique", not duplicate_ids, duplicate_ids)
    add_check(checks, "new_events_authority_false", all(authority_false_ok(event) for event in new_events), None)
    add_check(checks, "existing_events_authority_false", all(authority_false_ok(event) for event in existing_events), None)
    missing_gate_verdicts = [
        event.get("ticker")
        for event in new_events
        if event.get("event_type") == "promotion" and not as_dict(event.get("gate_verdicts"))
    ]
    add_check(checks, "new_promotion_events_have_gate_verdicts", not missing_gate_verdicts, missing_gate_verdicts)
    for flag in sorted(REQUIRED_TRUE_FLAGS):
        add_check(checks, f"authority_{flag}_true", AUTHORITY_BOUNDARY.get(flag) is True, AUTHORITY_BOUNDARY.get(flag))
    for flag in sorted(REQUIRED_FALSE_FLAGS):
        add_check(checks, f"authority_{flag}_false", AUTHORITY_BOUNDARY.get(flag) is False, AUTHORITY_BOUNDARY.get(flag))
    if include_daily_movement_backfill and any(event.get("event_source") == "daily_movement_ledger_backfill" for event in candidates):
        add_check(
            checks,
            "daily_movement_backfill_is_partial",
            True,
            "Backfilled daily movement rows preserve known current state but may not include prior tier/state fields.",
            severity="warning",
        )

    errors = [check for check in checks if check["severity"] == "critical" and not check["ok"]]
    warnings = [check for check in checks if check["severity"] == "warning"]
    last_event_at = recent_events[-1].get("event_observed_at_utc") if recent_events else None
    total_after_write = len(existing_events)
    return {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "blocked" if errors else "ok",
        "workflow": "WF78 - Append-Only Tier/Routing Event Ledger",
        "purpose": "Durable append-only JSONL movement history for WF78 auto-tier routing changes, with a compact cron/main-session handoff summary.",
        "authority_boundary": AUTHORITY_BOUNDARY,
        "source_artifacts": {
            "routing_delta": rel(delta_path),
            "auto_router": rel(auto_router_path),
            "daily_movement_ledger": rel(daily_movement_path),
            "freshness_resolution": rel(freshness_path),
            "tier_a_coverage_gate": rel(coverage_path),
            "tier_a_confidence_gate": rel(confidence_path),
            "append_only_ledger": rel(ledger_path),
        },
        "source_freshness": {
            "routing_delta_generated_at_utc": delta.get("generated_at_utc"),
            "auto_router_generated_at_utc": auto_router.get("generated_at_utc"),
            "daily_movement_generated_at_utc": daily_movement.get("generated_at_utc"),
        },
        "append_policy": {
            "dedupe": "event_id",
            "event_id_natural_key_fields": sorted(event_key({}).keys()),
            "ledger_is_jsonl": True,
            "append_only": True,
        },
        "parameters": {
            "include_daily_movement_backfill": include_daily_movement_backfill,
            "write": write,
        },
        "summary": {
            "existing_event_count_before_candidates": max(total_after_write - (len(new_events) if write else 0), 0),
            "candidate_event_count": len(candidates),
            "new_event_count": len(new_events),
            "total_event_count": total_after_write if write else len(existing_events),
            "last_event_at_utc": last_event_at,
            "event_type_counts": dict(sorted(event_type_counts.items())),
            "event_source_counts": dict(sorted(source_counts.items())),
            "top_event_tickers": [ticker for ticker, _count in ticker_counts.most_common(15)],
            "handoff_state": "movement_attention_required" if new_events else "no_new_route_events",
            "next_safe_action": "Cron should publish this before the daily movement ledger; main session should inspect new_events or recent_events when tier routing changes appear.",
        },
        "new_events": new_events,
        "recent_events": recent_events,
        "validation": {
            "status": "blocked" if errors else "ok",
            "checks": checks,
            "errors": errors,
            "warnings": warnings,
        },
        "stop_lines": [
            "This ledger records derived non-capital routing movement only.",
            "No capital deployment, paper/live execution, brokerage/account action, money movement, customer output, canon/portfolio mutation, SQL-canon mutation, or owner approval inference.",
        ],
    }


def render_markdown(packet: dict[str, Any]) -> str:
    summary = as_dict(packet.get("summary"))
    lines = [
        "# WF78 Tier Routing Event Ledger",
        "",
        f"- Status: {packet.get('status')}",
        f"- Generated UTC: {packet.get('generated_at_utc')}",
        f"- Ledger: {as_dict(packet.get('source_artifacts')).get('append_only_ledger')}",
        f"- Total events: {summary.get('total_event_count')}",
        f"- New events this run: {summary.get('new_event_count')}",
        f"- Last event UTC: {summary.get('last_event_at_utc')}",
        f"- Handoff state: {summary.get('handoff_state')}",
        "",
        "## Recent Events",
    ]
    for event in as_list(packet.get("recent_events"))[-20:]:
        lines.append(
            "- "
            f"{event.get('ticker')}: {event.get('event_type')} "
            f"{event.get('prior_auto_tier') or 'none'}/{event.get('prior_auto_state') or 'none'} -> "
            f"{event.get('current_auto_tier') or 'none'}/{event.get('current_auto_state') or 'none'} "
            f"({event.get('event_source')})"
        )
    lines.extend(["", "## Boundary", "- Review-only routing history. No capital/execution/account/portfolio authority."])
    return "\n".join(lines).rstrip() + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the WF78 append-only tier/routing event ledger.")
    parser.add_argument("--delta", type=Path, default=DEFAULT_DELTA)
    parser.add_argument("--auto-router", type=Path, default=DEFAULT_AUTO_ROUTER)
    parser.add_argument("--daily-movement", type=Path, default=DEFAULT_DAILY_MOVEMENT)
    parser.add_argument("--freshness", type=Path, default=DEFAULT_FRESHNESS)
    parser.add_argument("--coverage", type=Path, default=DEFAULT_COVERAGE)
    parser.add_argument("--confidence", type=Path, default=DEFAULT_CONFIDENCE)
    parser.add_argument("--ledger", type=Path, default=DEFAULT_LEDGER)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--md-out", type=Path, default=DEFAULT_MD)
    parser.add_argument("--include-daily-movement-backfill", action="store_true")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--write-md", action="store_true")
    parser.add_argument("--validate", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    delta_path = resolve(args.delta)
    auto_router_path = resolve(args.auto_router)
    daily_movement_path = resolve(args.daily_movement)
    freshness_path = resolve(args.freshness)
    coverage_path = resolve(args.coverage)
    confidence_path = resolve(args.confidence)
    ledger_path = resolve(args.ledger)
    out_path = resolve(args.out)
    md_out = resolve(args.md_out)
    packet = build_report(
        delta_path=delta_path,
        auto_router_path=auto_router_path,
        daily_movement_path=daily_movement_path,
        freshness_path=freshness_path,
        coverage_path=coverage_path,
        confidence_path=confidence_path,
        ledger_path=ledger_path,
        include_daily_movement_backfill=args.include_daily_movement_backfill,
        write=args.write,
    )
    if args.write:
        atomic_write_json(out_path, packet)
        if args.write_md:
            atomic_write_text(md_out, render_markdown(packet))
        print(
            json.dumps(
                {
                    "status": packet["status"],
                    "out": rel(out_path),
                    "ledger": rel(ledger_path),
                    "summary": packet["summary"],
                    "validation": {
                        "status": as_dict(packet.get("validation")).get("status"),
                        "errors": len(as_list(as_dict(packet.get("validation")).get("errors"))),
                    },
                },
                indent=2,
                sort_keys=True,
            )
        )
    else:
        print(json.dumps(packet["summary"], indent=2, sort_keys=True))
    if args.validate and as_dict(packet.get("validation")).get("status") != "ok":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
