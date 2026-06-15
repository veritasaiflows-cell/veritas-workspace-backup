#!/usr/bin/env python3
"""Score new or changed intelligence artifacts into review-only actions.

This is the cross-artifact control layer for "new artifact arrives -> score
materiality -> route action". It reads existing proof artifacts and emits a
review-only action queue. It does not mutate canon, portfolio state, ticker
cards, WF78 routing artifacts, cron config, brokerage/account state, or
execution systems.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, load_json_artifact

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
DEFAULT_OUT = TMP / "artifact-intelligence-action-scorer.json"

SCHEMA = "veritas.artifact_intelligence_action_scorer.v1"

MACRO_EVENT_CALENDAR = TMP / "macro-event-calendar.json"
MACRO_METRICS = TMP / "macro-metrics-current.json"
MACRO_SIGNAL_SPINE = TMP / "macro-signal-spine.json"
MACRO_JUDGMENT = TMP / "macro-judgment-draft.json"
WF78_AUTO_ROUTER = TMP / "wf78-auto-tier-routing.json"
WF78_TIER_A_CONFIDENCE = TMP / "wf78-tier-a-confidence-gate.json"
WF78_EVENT_REROUTING = TMP / "wf78-event-triggered-rerouting.json"
WORKFLOW_ROUTING_INDEX = TMP / "workflow-routing-index.json"
WORKFLOW_ROUTING_VALIDATION = TMP / "workflow-routing-index-validation.json"

MATERIALITY_ORDER = {"low": 1, "medium": 2, "high": 3, "critical": 4}
CONFIDENCE_ORDER = {"missing": 0, "conflicted": 1, "partial": 2, "clean": 3}

ALLOWED_ACTION_TYPES = {
    "refresh_artifact",
    "rerun_validator",
    "repair_evidence",
    "reroute_candidate",
    "block_readiness",
    "prepare_review_packet",
    "escalate_to_main",
    "notify_if_material",
}

AUTHORITY_BOUNDARY: dict[str, bool] = {
    "review_only": True,
    "artifact_routing_plumbing": True,
    "automated_non_capital_routing_recommendations_allowed": True,
    "writes_only_own_action_queue": True,
    "workflow_artifact_mutation_allowed": False,
    "canon_or_portfolio_mutation_allowed": False,
    "ticker_card_mutation_allowed": False,
    "sql_canon_mutation_allowed": False,
    "production_answer_path_change_allowed": False,
    "cron_config_runtime_mutation_allowed": False,
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

REQUIRED_TRUE_FLAGS = {
    "review_only",
    "artifact_routing_plumbing",
    "automated_non_capital_routing_recommendations_allowed",
    "writes_only_own_action_queue",
}
REQUIRED_FALSE_FLAGS = {key for key in AUTHORITY_BOUNDARY if key not in REQUIRED_TRUE_FLAGS}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_utc(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def age_hours(value: Any, now: datetime) -> float | None:
    dt = parse_utc(value)
    if dt is None:
        return None
    return round(max(0.0, (now - dt).total_seconds() / 3600), 2)


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


def artifact_state(path: Path, payload: dict[str, Any], now: datetime, max_age_hours: int | None = None) -> dict[str, Any]:
    generated = payload.get("generated_at_utc")
    state: dict[str, Any] = {
        "path": rel(path),
        "exists": path.exists(),
        "parseable_json": bool(payload),
        "schema": payload.get("schema") or payload.get("schema_version"),
        "status": payload.get("status"),
        "generated_at_utc": generated,
        "age_hours": age_hours(generated, now),
        "max_age_hours": max_age_hours,
    }
    if path.exists():
        state["mtime_utc"] = datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    if max_age_hours is not None and state["age_hours"] is not None:
        state["freshness"] = "stale" if float(state["age_hours"]) > max_age_hours else "fresh"
    elif path.exists():
        state["freshness"] = "unknown"
    else:
        state["freshness"] = "missing"
    validation = as_dict(payload.get("validation"))
    if validation:
        state["validation_status"] = validation.get("status")
        state["validation_errors"] = validation.get("errors", [])
        state["validation_warnings"] = validation.get("warnings", [])
    return state


def materiality_value(value: str) -> int:
    return MATERIALITY_ORDER.get(value, 0)


def confidence_value(value: str) -> int:
    return CONFIDENCE_ORDER.get(value, 0)


def score_action(materiality: str, confidence: str, urgency: str) -> int:
    base = materiality_value(materiality) * 25
    confidence_penalty = max(0, 3 - confidence_value(confidence)) * 5
    urgency_bonus = {"immediate": 20, "soon": 10, "normal": 0}.get(urgency, 0)
    return max(1, base + urgency_bonus - confidence_penalty)


def make_action(
    *,
    action_id: str,
    action_type: str,
    source_artifact: str,
    event_type: str,
    materiality: str,
    confidence: str,
    urgency: str,
    affected_workflows: list[str],
    recommended_commands: list[str],
    reason: str,
    source_artifacts: list[str],
    market_channels: list[str] | None = None,
    target_artifacts: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "action_id": action_id,
        "action_type": action_type,
        "source_artifact": source_artifact,
        "event_type": event_type,
        "materiality": materiality,
        "confidence": confidence,
        "urgency": urgency,
        "priority": score_action(materiality, confidence, urgency),
        "affected_workflows": sorted(set(affected_workflows)),
        "market_channels": sorted(set(market_channels or [])),
        "target_artifacts": sorted(set(target_artifacts or [])),
        "recommended_commands": recommended_commands,
        "reason": reason,
        "source_artifacts": sorted(set(source_artifacts)),
        "owner_action_required": action_type in {"prepare_review_packet", "escalate_to_main", "notify_if_material"},
        "apply_allowed": False,
        "workflow_artifact_mutation_allowed": False,
        "capital_deployment_allowed": False,
        "capital_deployment_approved": False,
        "trade_or_execution_allowed": False,
        "trade_or_execution_approved": False,
        "paper_or_live_execution_allowed": False,
        "brokerage_or_account_action_allowed": False,
        "money_movement_allowed": False,
        "owner_approval_inferred": False,
    }


def status_confidence(payload: dict[str, Any]) -> str:
    status = str(payload.get("status") or "").lower()
    if not payload:
        return "missing"
    if status in {"ok", "ready"}:
        return "clean"
    if status in {"warning", "partial"}:
        return "partial"
    if status in {"blocked", "error", "failed"}:
        return "conflicted"
    return "partial"


def build_macro_actions(
    *,
    macro_events: dict[str, Any],
    macro_metrics: dict[str, Any],
    macro_judgment: dict[str, Any],
) -> list[dict[str, Any]]:
    actions: list[dict[str, Any]] = []
    event_rows = [as_dict(row) for row in as_list(macro_events.get("events"))]
    high_impact_events = [
        row for row in event_rows
        if row.get("metric") in {"Consumer Price Index", "Producer Price Index", "Personal Income and Outlays / PCE", "Employment Situation", "FOMC Policy Decision"}
        and row.get("status") in {"today", "upcoming", "elapsed"}
    ]
    near_events = [row for row in high_impact_events if int(row.get("days_until") or 999) <= 7 and int(row.get("days_until") or 999) >= -1]
    inflation_events = [row for row in near_events if row.get("metric") in {"Consumer Price Index", "Producer Price Index", "Personal Income and Outlays / PCE"}]
    if inflation_events:
        event_names = ", ".join(f"{row.get('metric')} {row.get('date')}" for row in inflation_events)
        actions.append(make_action(
            action_id="macro-inflation-release-window-review",
            action_type="notify_if_material",
            source_artifact=rel(MACRO_EVENT_CALENDAR),
            event_type="macro_inflation_release_window",
            materiality="high",
            confidence=status_confidence(macro_events),
            urgency="soon",
            affected_workflows=["WF60-MACRO", "WF75", "WF77", "WF78"],
            market_channels=["rates", "inflation", "growth", "equities", "credit"],
            target_artifacts=[rel(MACRO_METRICS), rel(MACRO_SIGNAL_SPINE), rel(MACRO_JUDGMENT), rel(WF78_EVENT_REROUTING)],
            recommended_commands=[
                "python scripts\\macro_metrics_ingest.py --write --validate",
                "python scripts\\macro_signal_spine.py --write --validate",
                "python scripts\\macro_judgment_draft.py --write --validate",
                "python scripts\\wf78_macro_thesis_overlay_gate.py --write --write-db --validate",
            ],
            reason=f"High-impact inflation release window is active or near: {event_names}. Keep deployment certainty and rate-sensitive routing gated until refresh proof exists.",
            source_artifacts=[rel(MACRO_EVENT_CALENDAR)],
        ))

    summary = as_dict(macro_metrics.get("summary"))
    unavailable_count = int(summary.get("unavailable_count") or 0)
    inflation_latest = as_dict(summary.get("inflation_latest"))
    ppi = as_dict(inflation_latest.get("ppi_headline_final_demand"))
    if str(macro_metrics.get("status") or "").lower() != "ok" or unavailable_count > 0 or ppi.get("date") is None:
        actions.append(make_action(
            action_id="macro-metrics-ingest-repair",
            action_type="repair_evidence",
            source_artifact=rel(MACRO_METRICS),
            event_type="macro_metrics_partial_or_missing",
            materiality="high" if ppi.get("date") is None else "medium",
            confidence=status_confidence(macro_metrics),
            urgency="soon",
            affected_workflows=["WF60-MACRO", "WF75", "WF77", "WF78"],
            market_channels=["rates", "inflation", "growth"],
            target_artifacts=[rel(MACRO_METRICS)],
            recommended_commands=[
                "python scripts\\macro_metrics_ingest.py --write --validate",
            ],
            reason=f"Macro metrics are not clean: unavailable_count={unavailable_count}, PPI date={ppi.get('date')}. Repair ingest before claiming complete macro coverage.",
            source_artifacts=[rel(MACRO_METRICS)],
        ))

    machine_status = as_dict(macro_judgment.get("machine_evidence_status"))
    if machine_status.get("macro_metrics") not in {"ok", "ready"}:
        actions.append(make_action(
            action_id="macro-judgment-refresh-after-metrics-repair",
            action_type="refresh_artifact",
            source_artifact=rel(MACRO_JUDGMENT),
            event_type="macro_judgment_depends_on_partial_metrics",
            materiality="medium",
            confidence=status_confidence(macro_judgment),
            urgency="normal",
            affected_workflows=["WF60-MACRO", "WF75", "WF78"],
            market_channels=["rates", "inflation", "growth", "equities"],
            target_artifacts=[rel(MACRO_SIGNAL_SPINE), rel(MACRO_JUDGMENT)],
            recommended_commands=[
                "python scripts\\macro_signal_spine.py --write --validate",
                "python scripts\\macro_judgment_draft.py --write --validate",
            ],
            reason="Macro judgment currently depends on partial macro metrics, so it must be refreshed after metrics repair or post-release data.",
            source_artifacts=[rel(MACRO_JUDGMENT), rel(MACRO_SIGNAL_SPINE), rel(MACRO_METRICS)],
        ))
    return actions


def build_wf78_actions(
    *,
    auto_router: dict[str, Any],
    confidence_gate: dict[str, Any],
    wf78_rerouting: dict[str, Any],
) -> list[dict[str, Any]]:
    actions: list[dict[str, Any]] = []
    router_summary = as_dict(auto_router.get("summary"))
    a_ready = as_list(router_summary.get("auto_state_counts")).copy() if isinstance(router_summary.get("auto_state_counts"), list) else []
    _ = a_ready  # preserves local readability without depending on count shape.
    conflicted_ready_count = int(router_summary.get("tier_a_conflicted_ready_count") or 0)
    if conflicted_ready_count > 0:
        actions.append(make_action(
            action_id="wf78-tier-a-conflicted-ready-block",
            action_type="block_readiness",
            source_artifact=rel(WF78_AUTO_ROUTER),
            event_type="tier_a_confidence_conflict",
            materiality="critical",
            confidence=status_confidence(auto_router),
            urgency="immediate",
            affected_workflows=["WF78", "WF77"],
            market_channels=["equities"],
            target_artifacts=[rel(WF78_AUTO_ROUTER), rel(WF78_TIER_A_CONFIDENCE)],
            recommended_commands=[
                "python scripts\\wf78_tier_a_confidence_gate.py --write --validate",
                "python scripts\\wf78_auto_tier_router.py --write --validate",
            ],
            reason="Tier A conflicted names cannot remain A-READY. Rebuild confidence and auto-router gates.",
            source_artifacts=[rel(WF78_AUTO_ROUTER), rel(WF78_TIER_A_CONFIDENCE)],
        ))

    confidence_summary = as_dict(confidence_gate.get("summary"))
    conflicted_tickers = as_list(confidence_summary.get("conflicted_tickers"))
    force_challenged = as_list(confidence_summary.get("force_a_challenged_tickers"))
    if conflicted_tickers or force_challenged:
        actions.append(make_action(
            action_id="wf78-tier-a-data-conflict-review",
            action_type="reroute_candidate",
            source_artifact=rel(WF78_TIER_A_CONFIDENCE),
            event_type="tier_a_data_conflict_or_manual_review",
            materiality="high",
            confidence=status_confidence(confidence_gate),
            urgency="normal",
            affected_workflows=["WF78", "WF77"],
            market_channels=["equities"],
            target_artifacts=[rel(WF78_EVENT_REROUTING)],
            recommended_commands=[
                "python scripts\\wf78_event_triggered_rerouting.py --write --write-db --validate",
            ],
            reason=f"Tier A confidence gate has conflicted/manual-review names: {', '.join(str(t) for t in force_challenged)}.",
            source_artifacts=[rel(WF78_TIER_A_CONFIDENCE), rel(WF78_AUTO_ROUTER)],
        ))

    reroute_summary = as_dict(wf78_rerouting.get("summary"))
    action_count = int(reroute_summary.get("action_count") or 0)
    if action_count:
        actions.append(make_action(
            action_id="wf78-rerouting-queue-work-selection",
            action_type="prepare_review_packet",
            source_artifact=rel(WF78_EVENT_REROUTING),
            event_type="wf78_non_capital_action_queue",
            materiality="high" if action_count >= 50 else "medium",
            confidence=status_confidence(wf78_rerouting),
            urgency="normal",
            affected_workflows=["WF78", "WF77"],
            market_channels=["equities"],
            target_artifacts=[rel(WF78_EVENT_REROUTING)],
            recommended_commands=[
                "python scripts\\wf78_event_triggered_rerouting.py --write --write-db --validate",
                "python scripts\\concurrent_lane_manager.py --status --validate",
            ],
            reason=f"WF78 has {action_count} review-only rerouting/evidence actions. Use it as the work selector before adding new ticker expansion.",
            source_artifacts=[rel(WF78_EVENT_REROUTING)],
        ))
    return actions


def build_workflow_actions(workflow_index: dict[str, Any], workflow_validation: dict[str, Any]) -> list[dict[str, Any]]:
    actions: list[dict[str, Any]] = []
    validation_status = str(workflow_validation.get("status") or "").lower()
    if workflow_validation and validation_status not in {"ok", "ready"}:
        actions.append(make_action(
            action_id="workflow-routing-validation-repair",
            action_type="rerun_validator",
            source_artifact=rel(WORKFLOW_ROUTING_VALIDATION),
            event_type="workflow_route_validation_warning_or_block",
            materiality="medium",
            confidence=status_confidence(workflow_validation),
            urgency="normal",
            affected_workflows=["WF73"],
            target_artifacts=[rel(WORKFLOW_ROUTING_INDEX), rel(WORKFLOW_ROUTING_VALIDATION)],
            recommended_commands=[
                "python scripts\\workflow_routing_index.py --write --write-db --validate",
                "python scripts\\artifact_index.py incremental",
                "python scripts\\artifact_index.py validate",
            ],
            reason=f"Workflow routing validation status is {workflow_validation.get('status')}; repair route freshness before relying on helper handoff routes.",
            source_artifacts=[rel(WORKFLOW_ROUTING_INDEX), rel(WORKFLOW_ROUTING_VALIDATION)],
        ))
    elif workflow_index and not workflow_validation and status_confidence(workflow_index) != "clean":
        actions.append(make_action(
            action_id="workflow-routing-index-refresh",
            action_type="refresh_artifact",
            source_artifact=rel(WORKFLOW_ROUTING_INDEX),
            event_type="workflow_route_index_partial",
            materiality="low",
            confidence=status_confidence(workflow_index),
            urgency="normal",
            affected_workflows=["WF73"],
            target_artifacts=[rel(WORKFLOW_ROUTING_INDEX)],
            recommended_commands=[
                "python scripts\\workflow_routing_index.py --write --write-db --validate",
            ],
            reason="Workflow routing index is parseable but not clean; refresh before using route handoffs for concurrency planning.",
            source_artifacts=[rel(WORKFLOW_ROUTING_INDEX)],
        ))
    return actions


def build_report() -> dict[str, Any]:
    now_dt = datetime.now(timezone.utc)
    macro_events = load_dict(MACRO_EVENT_CALENDAR)
    macro_metrics = load_dict(MACRO_METRICS)
    macro_signal_spine = load_dict(MACRO_SIGNAL_SPINE)
    macro_judgment = load_dict(MACRO_JUDGMENT)
    auto_router = load_dict(WF78_AUTO_ROUTER)
    confidence_gate = load_dict(WF78_TIER_A_CONFIDENCE)
    wf78_rerouting = load_dict(WF78_EVENT_REROUTING)
    workflow_index = load_dict(WORKFLOW_ROUTING_INDEX)
    workflow_validation = load_dict(WORKFLOW_ROUTING_VALIDATION)

    source_states = {
        "macro_event_calendar": artifact_state(MACRO_EVENT_CALENDAR, macro_events, now_dt, 168),
        "macro_metrics": artifact_state(MACRO_METRICS, macro_metrics, now_dt, 24),
        "macro_signal_spine": artifact_state(MACRO_SIGNAL_SPINE, macro_signal_spine, now_dt, 24),
        "macro_judgment": artifact_state(MACRO_JUDGMENT, macro_judgment, now_dt, 24),
        "wf78_auto_router": artifact_state(WF78_AUTO_ROUTER, auto_router, now_dt, 24),
        "wf78_tier_a_confidence": artifact_state(WF78_TIER_A_CONFIDENCE, confidence_gate, now_dt, 24),
        "wf78_event_rerouting": artifact_state(WF78_EVENT_REROUTING, wf78_rerouting, now_dt, 24),
        "workflow_routing_index": artifact_state(WORKFLOW_ROUTING_INDEX, workflow_index, now_dt, 168),
        "workflow_routing_validation": artifact_state(WORKFLOW_ROUTING_VALIDATION, workflow_validation, now_dt, 168),
    }

    actions: list[dict[str, Any]] = []
    actions.extend(build_macro_actions(macro_events=macro_events, macro_metrics=macro_metrics, macro_judgment=macro_judgment))
    actions.extend(build_wf78_actions(auto_router=auto_router, confidence_gate=confidence_gate, wf78_rerouting=wf78_rerouting))
    actions.extend(build_workflow_actions(workflow_index, workflow_validation))

    # Missing or stale source artifacts create refresh actions even when the
    # domain-specific scorer above cannot classify them.
    for key, state in source_states.items():
        if not state.get("exists") or state.get("freshness") == "stale":
            path = str(state.get("path"))
            actions.append(make_action(
                action_id=f"{key.replace('_', '-')}-source-refresh",
                action_type="refresh_artifact",
                source_artifact=path,
                event_type="source_artifact_missing_or_stale",
                materiality="medium" if state.get("exists") else "high",
                confidence="missing" if not state.get("exists") else "partial",
                urgency="soon",
                affected_workflows=["WF73"],
                target_artifacts=[path],
                recommended_commands=[],
                reason=f"Source artifact {path} is {state.get('freshness')}; refresh or verify before relying on downstream action scoring.",
                source_artifacts=[path],
            ))

    deduped: dict[str, dict[str, Any]] = {}
    for action in actions:
        existing = deduped.get(str(action["action_id"]))
        if not existing or int(action["priority"]) > int(existing["priority"]):
            deduped[str(action["action_id"])] = action
    final_actions = sorted(deduped.values(), key=lambda row: (-int(row["priority"]), str(row["action_id"])))
    for index, action in enumerate(final_actions, start=1):
        action["queue_rank"] = index

    payload: dict[str, Any] = {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "ok",
        "purpose": "Review-only cross-artifact materiality scoring and action routing.",
        "source_states": source_states,
        "summary": {
            "action_count": len(final_actions),
            "action_type_counts": count_by(final_actions, "action_type"),
            "materiality_counts": count_by(final_actions, "materiality"),
            "confidence_counts": count_by(final_actions, "confidence"),
            "affected_workflow_counts": count_workflows(final_actions),
            "top_action": final_actions[0] if final_actions else None,
            "next_safe_action": "Run or lease only the review-only commands listed in top actions; main session must verify proof before any integration.",
        },
        "actions": final_actions,
        "authority_boundary": AUTHORITY_BOUNDARY,
    }
    payload["validation"] = validate(payload)
    if payload["validation"]["errors"]:
        payload["status"] = "blocked"
    elif payload["validation"]["warnings"]:
        payload["status"] = "warning"
    return payload


def count_by(rows: list[dict[str, Any]], field: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        key = str(row.get(field) or "unknown")
        counts[key] = counts.get(key, 0) + 1
    return dict(sorted(counts.items()))


def count_workflows(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        for workflow in as_list(row.get("affected_workflows")):
            key = str(workflow)
            counts[key] = counts.get(key, 0) + 1
    return dict(sorted(counts.items()))


def validate(payload: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    if payload.get("schema") != SCHEMA:
        errors.append("schema mismatch")
    actions = as_list(payload.get("actions"))
    if not actions:
        warnings.append("no actions generated")
    for flag in sorted(REQUIRED_TRUE_FLAGS):
        if as_dict(payload.get("authority_boundary")).get(flag) is not True:
            errors.append(f"authority boundary must be true: {flag}")
    for flag in sorted(REQUIRED_FALSE_FLAGS):
        if as_dict(payload.get("authority_boundary")).get(flag) is not False:
            errors.append(f"authority boundary must be false: {flag}")
    for action in actions:
        row = as_dict(action)
        action_id = row.get("action_id")
        if not action_id:
            errors.append("action missing action_id")
        if row.get("action_type") not in ALLOWED_ACTION_TYPES:
            errors.append(f"invalid action_type for {action_id}: {row.get('action_type')}")
        if row.get("materiality") not in MATERIALITY_ORDER:
            errors.append(f"invalid materiality for {action_id}: {row.get('materiality')}")
        if row.get("confidence") not in CONFIDENCE_ORDER:
            errors.append(f"invalid confidence for {action_id}: {row.get('confidence')}")
        if not as_list(row.get("affected_workflows")):
            warnings.append(f"action missing affected_workflows: {action_id}")
        if row.get("priority") != score_action(str(row.get("materiality")), str(row.get("confidence")), str(row.get("urgency"))):
            errors.append(f"priority mismatch for {action_id}")
        for key in (
            "apply_allowed",
            "workflow_artifact_mutation_allowed",
            "capital_deployment_allowed",
            "capital_deployment_approved",
            "trade_or_execution_allowed",
            "trade_or_execution_approved",
            "paper_or_live_execution_allowed",
            "brokerage_or_account_action_allowed",
            "money_movement_allowed",
            "owner_approval_inferred",
        ):
            if row.get(key) is not False:
                errors.append(f"action authority flag must be false for {action_id}: {key}")
    ranks = [as_dict(row).get("queue_rank") for row in actions]
    if ranks and ranks != list(range(1, len(ranks) + 1)):
        errors.append("queue ranks must be contiguous from 1")
    return {"status": "ok" if not errors else "error", "errors": errors, "warnings": warnings}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default=str(DEFAULT_OUT), help="Output JSON path")
    parser.add_argument("--write", action="store_true", help="Write the scorer artifact")
    parser.add_argument("--validate", action="store_true", help="Return non-zero if validation fails")
    parser.add_argument("--pretty", action="store_true", help="Print full JSON instead of compact status")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    payload = build_report()
    output = Path(args.output)
    if args.write:
        atomic_write_json(output, payload)
    if args.pretty:
        import json

        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        summary = as_dict(payload.get("summary"))
        validation = as_dict(payload.get("validation"))
        print(
            f"status={payload.get('status')} actions={summary.get('action_count')} "
            f"validation={validation.get('status')} errors={len(as_list(validation.get('errors')))} "
            f"warnings={len(as_list(validation.get('warnings')))}"
        )
    if args.validate and payload.get("validation", {}).get("errors"):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
