#!/usr/bin/env python3
"""Compile upstream WF74/WF88 action surfaces into review-only decisions.

Runtime direction is deliberately one-way: this compiler reads upstream
actionability, docket, router, loop-trace, improvement, and outcome artifacts.
It never requires the WF88 wiki synthesis or OS2 control packets, allowing the
wiki producer to consume this compiler without a producer cycle.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from advanced_capability_pilot_packet import DECISION_OBJECT_SCHEMA


ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
OUT = TMP / "wf88-decision-compiler.json"
MD_OUT = TMP / "wf88-decision-compiler.md"

SCHEMA = "veritas.wf88_decision_compiler.v1"
DECISION_SCHEMA = "veritas.wf88_decision_object.v1"

MISSING_ROUTE_SENTINEL = "unassigned_review_only_route"
MISSING_ROUTE_ID_SENTINEL = "unassigned_review_only_route_id"
MISSING_SECONDARY_ROUTE_ID_SENTINEL = "unassigned_review_only_secondary_route_id"
MISSING_SECONDARY_ROUTE_TITLE_SENTINEL = "untitled_review_only_secondary_route"
MISSING_SECONDARY_ROUTE_STATE_SENTINEL = "unresolved_review_only_secondary_route_state"
MISSING_COMMAND_SENTINEL = "no_command_available_review_only"

SOURCE_SPECS: dict[str, dict[str, Any]] = {
    "actionable_improvement_queue": {
        "path": "tmp/actionable-improvement-queue.json",
        "required": True,
        "max_age_hours": 24,
    },
    "wf74_decision_docket": {
        "path": "tmp/wf74-decision-docket.json",
        "required": True,
        "max_age_hours": 24,
    },
    "wf74_autonomy_work_router": {
        "path": "tmp/wf74-autonomy-work-router.json",
        "required": True,
        "max_age_hours": 24,
    },
    "wf74_wf88_loop_trace": {
        "path": "tmp/wf74-wf88-loop-trace.json",
        "required": True,
        "max_age_hours": 24,
    },
    "improvement_ledger": {
        "path": "tmp/improvement-ledger-current.json",
        "required": True,
        "max_age_hours": 24,
    },
    "recommendation_outcome_ledger": {
        "path": "tmp/recommendation-outcome-ledger-current.json",
        "required": False,
        "max_age_hours": 168,
    },
}

FORBIDDEN_RUNTIME_INPUTS = {
    "tmp/wf88-wiki-synthesis-packet.json",
    "tmp/wf88-os2-control-packet.json",
}

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "deterministic_compiler_only": True,
    "model_or_api_call_used": False,
    "wiki_or_os2_runtime_input_required": False,
    "creates_canon": False,
    "approval_authority": False,
    "apply_allowed": False,
    "auto_apply_allowed": False,
    "cron_schedule_mutation_allowed": False,
    "config_auth_runtime_mutation_allowed": False,
    "sql_or_source_mutation_allowed": False,
    "canonical_note_mutation_allowed": False,
    "portfolio_mutation_allowed": False,
    "cash_sizing_risk_mutation_allowed": False,
    "capital_deployment_allowed": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "customer_or_external_output_allowed": False,
    "delete_archive_or_move_allowed": False,
    "raw_prompt_or_tool_capture_allowed": False,
    "owner_approval_inferred": False,
}

GLOBAL_STOP_LINES = [
    "Decision objects are review/routing outputs only; they do not approve or apply their recommendation.",
    "No capital deployment, paper/live execution, brokerage/account action, money movement, or portfolio/canon/cash/sizing/risk mutation.",
    "No cron schedule, config/auth/runtime, external delivery, delete/archive/move, skill apply, raw prompt/tool capture, or owner approval inference.",
]

REQUIRED_DECISION_FIELDS = {
    "decision_id",
    "question",
    "state",
    "recommendation",
    "alternatives",
    "source_pointers",
    "source_selection",
    "freshness",
    "conflict_uncertainty",
    "authority_class",
    "owner_route",
    "stop_lines",
    "next_action",
    "next_command",
    "acceptance_proof",
    "expiry_reopen",
    "later_outcome_pointer",
}

FORBIDDEN_CAPTURE_KEYS = {
    "api_key",
    "authorization",
    "headers",
    "messages",
    "raw_prompt",
    "raw_response",
    "secret",
    "secrets",
    "system_prompt",
    "tool_payload",
}

FORBIDDEN_COMMAND_PATTERNS = [
    re.compile(r"(?:^|\s)--apply(?:\s|$)", re.IGNORECASE),
    re.compile(r"\b(?:submit|replace|cancel)[-_ ]?(?:order|trade)\b", re.IGNORECASE),
    re.compile(r"\bcron\s+(?:add|edit|remove|delete)\b", re.IGNORECASE),
    re.compile(r"\bskill[_ -]?workshop\b.*\b(?:apply|install|quarantine)\b", re.IGNORECASE),
    re.compile(r"\bRemove-Item\b", re.IGNORECASE),
    re.compile(r"\brm\s+-", re.IGNORECASE),
]

SENSITIVE_TRUE_KEYS = {
    "apply_allowed",
    "approval_authority",
    "auto_apply_allowed",
    "brokerage_or_account_action_allowed",
    "capital_deployment_allowed",
    "canonical_note_mutation_allowed",
    "config_auth_runtime_mutation_allowed",
    "cron_schedule_mutation_allowed",
    "customer_or_external_output_allowed",
    "delete_archive_or_move_allowed",
    "owner_approval_inferred",
    "paper_or_live_execution_allowed",
    "portfolio_mutation_allowed",
    "raw_prompt_or_tool_capture_allowed",
    "sql_or_source_mutation_allowed",
}


def utc_now_dt() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def utc_text(value: datetime) -> str:
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def dedupe_strings(values: list[Any]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        text = str(value or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result


def parse_utc(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def normalize_text(value: Any) -> str:
    return " ".join(str(value or "").lower().split())


def stable_decision_id(stable_key: str) -> str:
    digest = hashlib.sha256(stable_key.encode("utf-8")).hexdigest()[:16]
    return f"wf88dec-{digest}"


def json_pointer_escape(value: str) -> str:
    return str(value).replace("~", "~0").replace("/", "~1")


def source_pointer(source_name: str, pointer: str, role: str, *, selected: bool) -> dict[str, Any]:
    return {
        "source_name": source_name,
        "path": SOURCE_SPECS[source_name]["path"],
        "json_pointer": pointer,
        "exact_pointer": f"{SOURCE_SPECS[source_name]['path']}#{pointer}",
        "role": role,
        "selected": selected,
    }


def read_json_source(root: Path, source_name: str) -> tuple[dict[str, Any] | None, str | None]:
    path = root / str(SOURCE_SPECS[source_name]["path"])
    if not path.exists() or not path.is_file():
        return None, "missing_source"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return None, f"unparseable_source:{type(exc).__name__}"
    if not isinstance(payload, dict):
        return None, "unparseable_source:top_level_not_object"
    return payload, None


def load_sources(root: Path = ROOT) -> tuple[dict[str, dict[str, Any] | None], dict[str, str | None]]:
    payloads: dict[str, dict[str, Any] | None] = {}
    errors: dict[str, str | None] = {}
    for source_name in SOURCE_SPECS:
        payload, error = read_json_source(root, source_name)
        payloads[source_name] = payload
        errors[source_name] = error
    return payloads, errors


def source_descriptor(
    source_name: str,
    payload: dict[str, Any] | None,
    load_error: str | None,
    now: datetime,
) -> dict[str, Any]:
    spec = SOURCE_SPECS[source_name]
    generated_at = payload.get("generated_at_utc") if payload else None
    generated_dt = parse_utc(generated_at)
    age_hours = None
    expires_at = None
    if generated_dt is not None:
        age_hours = round((now - generated_dt).total_seconds() / 3600.0, 2)
        expires_at = utc_text(generated_dt + timedelta(hours=float(spec["max_age_hours"])))
    if payload is None:
        freshness_status = "unparseable" if load_error and load_error.startswith("unparseable") else "missing"
    elif generated_dt is None:
        freshness_status = "unknown_generated_at"
    elif age_hours is not None and (age_hours < 0 or age_hours > float(spec["max_age_hours"])):
        freshness_status = "stale"
    else:
        freshness_status = "fresh"
    validation_status = as_dict(payload.get("validation")).get("status") if payload else None
    return {
        "path": spec["path"],
        "required": bool(spec["required"]),
        "present": payload is not None,
        "load_error": load_error,
        "schema": payload.get("schema") or payload.get("schema_version") if payload else None,
        "status": payload.get("status") if payload else None,
        "validation_status": validation_status,
        "generated_at_utc": generated_at,
        "age_hours": age_hours,
        "max_age_hours": spec["max_age_hours"],
        "expires_at_utc": expires_at,
        "freshness_status": freshness_status,
    }


def source_descriptors(
    payloads: dict[str, dict[str, Any] | None],
    load_errors: dict[str, str | None],
    now: datetime,
) -> dict[str, dict[str, Any]]:
    return {
        name: source_descriptor(name, payloads.get(name), load_errors.get(name), now)
        for name in SOURCE_SPECS
    }


def semantic_state(value: Any) -> str:
    raw = str(value or "").strip().lower()
    mapping = {
        "wf74_fix_now": "repair",
        "fix_now": "repair",
        "patch_plan": "repair",
        "market_session_accrual": "monitor",
        "monitor_only": "monitor",
        "owner_decision": "owner_review",
        "owner_review": "owner_review",
        "hard_stop": "blocked",
        "blocked": "blocked",
    }
    return mapping.get(raw, raw or "unknown")


def normalized_state(item: dict[str, Any], primary_descriptor: dict[str, Any]) -> str:
    freshness = primary_descriptor.get("freshness_status")
    if freshness in {"missing", "unparseable", "stale", "unknown_generated_at"}:
        return "blocked_source_not_current"
    if item.get("is_orphan") is True or as_list(item.get("missing_contract_fields")):
        return "blocked_missing_contract"
    action_class = str(item.get("action_class") or "")
    if item.get("requires_owner_decision") is True or action_class == "owner_decision":
        return "owner_review_required"
    if action_class == "hard_stop":
        return "blocked_stop_line"
    if item.get("monitor_only") is True or action_class in {"monitor_only", "market_session_accrual"}:
        return "monitor_only"
    if action_class == "wf74_fix_now":
        return "repair_ready_review_only"
    if action_class in {"pm_job", "pm_implementation_job"}:
        return "routed_review_job"
    return "review_ready"


def authority_class_for(item: dict[str, Any], state: str) -> str:
    if state.startswith("blocked"):
        return "review_only_fail_closed"
    if item.get("requires_owner_decision") is True or state == "owner_review_required":
        return "review_only_owner_gated"
    stop_text = " ".join(str(value).lower() for value in as_list(item.get("stop_lines")))
    if "cron" in stop_text or "config" in stop_text or "runtime" in stop_text:
        return "review_only_governance_sensitive"
    if state == "monitor_only":
        return "review_only_monitor"
    return "review_only_local_repair"


def owner_workflow_for(item: dict[str, Any]) -> str:
    destination = str(item.get("destination") or "")
    if "wf74" in destination:
        return "WF74"
    if destination.startswith("pm_") or destination == "pm":
        return "PM"
    if "owner" in destination:
        return "OWNER_REVIEW"
    return "WF88"


def alternatives_for(state: str, item: dict[str, Any]) -> list[dict[str, str]]:
    if state == "monitor_only":
        return [
            {
                "alternative_id": "continue_monitor_only",
                "description": "Keep the row visible without opening implementation work until its escalation trigger fires.",
            },
            {
                "alternative_id": "escalate_on_reopen_trigger",
                "description": "Route a new bounded review when the source regresses, the monitor deadline arrives, or authority changes.",
            },
        ]
    if state == "owner_review_required":
        return [
            {
                "alternative_id": "defer_without_owner_decision",
                "description": "Take no mutating action while owner authority is absent.",
            },
            {
                "alternative_id": "prepare_exact_owner_packet",
                "description": "Prepare an exact review packet with proof and rollback, without applying it.",
            },
        ]
    if state.startswith("blocked"):
        return [
            {
                "alternative_id": "repair_source_contract",
                "description": "Refresh or repair the missing, stale, conflicting, or incomplete source contract.",
            },
            {
                "alternative_id": "defer_fail_closed",
                "description": "Leave the decision blocked until acceptance proof is current.",
            },
        ]
    return [
        {
            "alternative_id": "defer_until_next_refresh",
            "description": "Wait for the next upstream refresh and preserve the current review-only state.",
        },
        {
            "alternative_id": "escalate_if_scope_expands",
            "description": "Route to the exact owner before any action would cross a stop line.",
        },
    ]


def nonempty_text(value: Any, fallback: str) -> str:
    """Return honest nonempty text without inventing missing route authority."""
    text = str(value).strip() if value is not None else ""
    return text or fallback


def normalized_secondary_routes(value: Any) -> list[dict[str, str]]:
    routes: list[dict[str, str]] = []
    for raw in as_list(value):
        row = as_dict(raw)
        routes.append(
            {
                "route_id": nonempty_text(
                    row.get("destination_id") or row.get("route_id"),
                    MISSING_SECONDARY_ROUTE_ID_SENTINEL,
                ),
                "title": nonempty_text(row.get("title"), MISSING_SECONDARY_ROUTE_TITLE_SENTINEL),
                "state": nonempty_text(
                    row.get("action_state") or row.get("state"),
                    MISSING_SECONDARY_ROUTE_STATE_SENTINEL,
                ),
            }
        )
    return routes


def find_matching_rows(
    item: dict[str, Any],
    payloads: dict[str, dict[str, Any] | None],
) -> dict[str, tuple[int, dict[str, Any]] | None]:
    destination_id = str(item.get("destination_id") or "")
    source_key = str(item.get("source_key") or "")
    source_keys = {source_key, *[str(value) for value in as_list(item.get("source_keys"))]}
    title = normalize_text(item.get("title"))

    docket_match = None
    docket_rows = as_list(as_dict(payloads.get("wf74_decision_docket")).get("rows"))
    for index, raw in enumerate(docket_rows):
        row = as_dict(raw)
        if destination_id and str(row.get("docket_id")) == destination_id:
            docket_match = (index, row)
            break
    if docket_match is None:
        title_matches = [
            (index, as_dict(raw))
            for index, raw in enumerate(docket_rows)
            if title and normalize_text(as_dict(raw).get("title")) == title
        ]
        if len(title_matches) == 1:
            docket_match = title_matches[0]

    trace_match = None
    trace_rows = as_list(as_dict(payloads.get("wf74_wf88_loop_trace")).get("trace_rows"))
    for index, raw in enumerate(trace_rows):
        row = as_dict(raw)
        if destination_id and str(row.get("decision_docket_id")) == destination_id:
            trace_match = (index, row)
            break
    if trace_match is None:
        title_matches = [
            (index, as_dict(raw))
            for index, raw in enumerate(trace_rows)
            if title and normalize_text(as_dict(raw).get("title")) == title
        ]
        if len(title_matches) == 1:
            trace_match = title_matches[0]

    router_match = None
    route_rows = as_list(as_dict(payloads.get("wf74_autonomy_work_router")).get("opportunity_routes"))
    for index, raw in enumerate(route_rows):
        row = as_dict(raw)
        if str(row.get("source_key")) in source_keys or (title and normalize_text(row.get("title")) == title):
            router_match = (index, row)
            break

    return {"docket": docket_match, "trace": trace_match, "router": router_match}


def later_outcome_for(
    item: dict[str, Any],
    payloads: dict[str, dict[str, Any] | None],
) -> dict[str, Any]:
    source_key = str(item.get("source_key") or "")
    keys = {source_key, *[str(value) for value in as_list(item.get("source_keys"))]}
    title = normalize_text(item.get("title"))
    improvement = as_dict(payloads.get("improvement_ledger"))
    matches: dict[str, tuple[int, dict[str, Any]] | None] = {
        "latest_closed_improvements": None,
        "latest_open_improvements": None,
    }
    for array_name in matches:
        for index, raw in enumerate(as_list(improvement.get(array_name))):
            row = as_dict(raw)
            if str(row.get("source_key")) in keys or (title and normalize_text(row.get("title")) == title):
                matches[array_name] = (index, row)
                break
    closed = matches["latest_closed_improvements"]
    current_open = matches["latest_open_improvements"]
    if closed or current_open:
        selected_array = "latest_closed_improvements" if closed else "latest_open_improvements"
        selected_index, selected_row = closed or current_open or (0, {})
        selected_pointer = f"/{selected_array}/{selected_index}"
        closed_pointer = (
            f"{SOURCE_SPECS['improvement_ledger']['path']}#/latest_closed_improvements/{closed[0]}"
            if closed
            else None
        )
        current_pointer = (
            f"{SOURCE_SPECS['improvement_ledger']['path']}#/latest_open_improvements/{current_open[0]}"
            if current_open
            else None
        )
        if closed and current_open:
            status = "reopened_after_prior_close"
        elif closed:
            status = "linked_closed_outcome"
        else:
            status = "tracking_open_no_later_outcome"
        grade = as_dict(selected_row.get("follow_up")).get("status") or selected_row.get("status")
        return {
            "path": SOURCE_SPECS["improvement_ledger"]["path"],
            "json_pointer": selected_pointer,
            "exact_pointer": f"{SOURCE_SPECS['improvement_ledger']['path']}#{selected_pointer}",
            "match_key": source_key,
            "status": status,
            "outcome_state": grade,
            "current_tracking_pointer": current_pointer,
            "closed_outcome_pointer": closed_pointer,
            "future_collection_pointer": f"{SOURCE_SPECS['improvement_ledger']['path']}#/latest_closed_improvements",
        }

    outcome = as_dict(payloads.get("recommendation_outcome_ledger"))
    match_values = {source_key, str(item.get("item_id") or ""), str(item.get("destination_id") or "")}
    for index, raw in enumerate(as_list(outcome.get("tracked_rows"))):
        row = as_dict(raw)
        payload = as_dict(row.get("payload"))
        row_values = {
            str(row.get("object_id") or ""),
            str(payload.get("recommendation_id") or ""),
            str(payload.get("source_key") or ""),
        }
        if (match_values - {""}) & (row_values - {""}):
            grade = as_dict(row.get("forward_scorecard")).get("outcome_grade_status")
            return {
                "path": SOURCE_SPECS["recommendation_outcome_ledger"]["path"],
                "json_pointer": f"/tracked_rows/{index}",
                "exact_pointer": f"{SOURCE_SPECS['recommendation_outcome_ledger']['path']}#/tracked_rows/{index}",
                "match_key": source_key,
                "status": "linked_recommendation_outcome",
                "outcome_state": grade,
                "current_tracking_pointer": f"{SOURCE_SPECS['recommendation_outcome_ledger']['path']}#/tracked_rows/{index}",
                "closed_outcome_pointer": None,
                "future_collection_pointer": f"{SOURCE_SPECS['recommendation_outcome_ledger']['path']}#/tracked_rows",
            }
    return {
        "path": SOURCE_SPECS["improvement_ledger"]["path"],
        "json_pointer": "/latest_closed_improvements",
        "exact_pointer": f"{SOURCE_SPECS['improvement_ledger']['path']}#/latest_closed_improvements",
        "match_key": source_key,
        "status": "pending_future_match",
        "outcome_state": None,
        "current_tracking_pointer": None,
        "closed_outcome_pointer": None,
        "future_collection_pointer": f"{SOURCE_SPECS['improvement_ledger']['path']}#/latest_closed_improvements",
    }


def relevant_freshness(
    source_names: list[str],
    descriptors: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    severity = {
        "missing": 5,
        "unparseable": 5,
        "stale": 4,
        "unknown_generated_at": 3,
        "fresh": 0,
    }
    rows = [descriptors[name] for name in source_names if name in descriptors]
    worst = max(rows, key=lambda row: severity.get(str(row.get("freshness_status")), 2)) if rows else {}
    status = str(worst.get("freshness_status") or "missing")
    if status == "fresh" and any(
        row.get("validation_status") in {"warning", "blocked", "error"}
        or "warning" in str(row.get("status") or "").lower()
        for row in rows
    ):
        status = "warning"
    primary = descriptors.get("actionable_improvement_queue", {})
    return {
        "status": status,
        "generated_at_utc": primary.get("generated_at_utc"),
        "age_hours": primary.get("age_hours"),
        "max_age_hours": primary.get("max_age_hours"),
        "expires_at_utc": primary.get("expires_at_utc"),
        "source_statuses": [
            {
                "source_name": name,
                "path": descriptors[name].get("path"),
                "freshness_status": descriptors[name].get("freshness_status"),
                "validation_status": descriptors[name].get("validation_status"),
            }
            for name in source_names
            if name in descriptors
        ],
        "expiry_behavior": "block_current_action_until_upstream_source_refresh",
    }


def conflict_uncertainty_for(
    item: dict[str, Any],
    matches: dict[str, tuple[int, dict[str, Any]] | None],
    freshness: dict[str, Any],
    later_outcome: dict[str, Any],
    pointers: list[dict[str, Any]],
) -> dict[str, Any]:
    recommendation_values = {normalize_text(item.get("next_action"))} - {""}
    state_values = {semantic_state(item.get("action_class"))} - {"unknown"}
    conflicting_pointer_values: list[str] = []
    docket = matches.get("docket")
    if docket:
        _, row = docket
        docket_recommendation = row.get("next_action") or row.get("recommendation")
        if normalize_text(docket_recommendation):
            recommendation_values.add(normalize_text(docket_recommendation))
        state_values.add(semantic_state(row.get("action_state")))
    trace = matches.get("trace")
    if trace:
        _, row = trace
        if normalize_text(row.get("decision_next_action")):
            recommendation_values.add(normalize_text(row.get("decision_next_action")))
        state_values.add(semantic_state(row.get("decision_action_state")))
    router = matches.get("router")
    if router:
        _, row = router
        if normalize_text(row.get("recommended_action")):
            recommendation_values.add(normalize_text(row.get("recommended_action")))

    recommendation_conflict = len(recommendation_values) > 1
    state_conflict = len(state_values - {""}) > 1
    if recommendation_conflict or state_conflict:
        conflicting_pointer_values = [row["exact_pointer"] for row in pointers if not row.get("selected")]
    uncertainties = ["generated_review_surfaces_do_not_grant_apply_or_approval_authority"]
    if freshness.get("status") != "fresh":
        uncertainties.append(f"source_freshness_or_validation={freshness.get('status')}")
    if not docket:
        uncertainties.append("no_unique_docket_link")
    if not trace:
        uncertainties.append("no_unique_loop_trace_link")
    if later_outcome.get("status") != "linked_closed_outcome":
        uncertainties.append("later_outcome_not_closed")
    return {
        "conflict": recommendation_conflict or state_conflict,
        "recommendation_conflict": recommendation_conflict,
        "state_conflict": state_conflict,
        "uncertainties": dedupe_strings(uncertainties),
        "conflicting_source_pointers": conflicting_pointer_values,
        "resolution_rule": "The originating deduplicated action row supplies current state/recommendation; route context enriches it and contradictions remain explicit.",
    }


def compile_decision(
    index: int,
    item: dict[str, Any],
    payloads: dict[str, dict[str, Any] | None],
    descriptors: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    item_id = str(item.get("item_id") or item.get("source_key") or f"row-{index}")
    stable_key = f"actionable_improvement_queue:{item_id}"
    primary_pointer = source_pointer(
        "actionable_improvement_queue",
        f"/action_items/{index}",
        "originating_deduplicated_action_row",
        selected=True,
    )
    pointers = [primary_pointer]
    matches = find_matching_rows(item, payloads)
    relevant_sources = ["actionable_improvement_queue", "improvement_ledger"]
    if matches["docket"]:
        docket_index, _ = matches["docket"]
        pointers.append(source_pointer("wf74_decision_docket", f"/rows/{docket_index}", "route_and_proof_context", selected=False))
        relevant_sources.append("wf74_decision_docket")
    if matches["trace"]:
        trace_index, _ = matches["trace"]
        pointers.append(source_pointer("wf74_wf88_loop_trace", f"/trace_rows/{trace_index}", "route_linkage_context", selected=False))
        relevant_sources.append("wf74_wf88_loop_trace")
    if matches["router"]:
        router_index, _ = matches["router"]
        pointers.append(source_pointer("wf74_autonomy_work_router", f"/opportunity_routes/{router_index}", "router_context", selected=False))
        relevant_sources.append("wf74_autonomy_work_router")

    freshness = relevant_freshness(dedupe_strings(relevant_sources), descriptors)
    state = normalized_state(item, descriptors["actionable_improvement_queue"])
    later_outcome = later_outcome_for(item, payloads)
    conflict_uncertainty = conflict_uncertainty_for(item, matches, freshness, later_outcome, pointers)
    title = str(item.get("title") or item_id).strip()
    next_action = str(item.get("next_action") or "Refresh the source row and route it through the no-orphan contract.").strip()

    docket_row = matches["docket"][1] if matches["docket"] else {}
    proof_artifacts = dedupe_strings(
        [
            *as_list(item.get("proof_artifacts")),
            *as_list(docket_row.get("proof_artifacts")),
        ]
    )
    proof_artifacts = [value for value in proof_artifacts if value != "proof_commands"]
    proof_commands = dedupe_strings(
        [
            *as_list(item.get("proof_commands")),
            *as_list(docket_row.get("proof_commands")),
        ]
    )
    command = nonempty_text(
        item.get("proof_command") or (proof_commands[0] if proof_commands else None),
        MISSING_COMMAND_SENTINEL,
    )
    stop_lines = dedupe_strings(
        [
            *GLOBAL_STOP_LINES,
            *as_list(as_dict(payloads.get("actionable_improvement_queue")).get("blocked_actions")),
            *as_list(item.get("stop_lines")),
            *as_list(docket_row.get("stop_lines")),
        ]
    )
    reopen_trigger = (
        item.get("monitor_escalation_trigger")
        or item.get("monitor_review_rule")
        or item.get("close_condition")
        or "Reopen when the source state, route, acceptance proof, or governing authority changes."
    )
    authority_class = authority_class_for(item, state)
    decision = {
        "schema": DECISION_SCHEMA,
        "decision_id": stable_decision_id(stable_key),
        "question": f"What review-only action should be taken for \"{title}\"?",
        "state": state,
        "recommendation": next_action,
        "alternatives": alternatives_for(state, item),
        "source_pointers": pointers,
        "source_selection": {
            "stable_key": stable_key,
            "primary_source_pointer": primary_pointer["exact_pointer"],
            "candidate_source_pointers": [row["exact_pointer"] for row in pointers],
            "field_precedence": {
                "question_state_recommendation_next_action": "originating actionable-improvement-queue row",
                "route_and_acceptance_proof": "linked WF74 docket, then router and loop trace",
                "authority_and_stop_lines": "most-restrictive union across linked sources",
                "later_outcome": "improvement ledger, then recommendation outcome ledger",
            },
            "selection_reason": "The deduplicated no-orphan action row is the bounded decision origin; linked artifacts enrich but cannot silently override it.",
            "generated_review_only": True,
            "source_open_required_for_material_claim": True,
        },
        "freshness": freshness,
        "conflict_uncertainty": conflict_uncertainty,
        "authority_class": authority_class,
        "owner_route": {
            "owner_workflow": owner_workflow_for(item),
            "route": nonempty_text(item.get("destination"), MISSING_ROUTE_SENTINEL),
            "route_id": nonempty_text(item.get("destination_id"), MISSING_ROUTE_ID_SENTINEL),
            "secondary_routes": normalized_secondary_routes(item.get("secondary_routes")),
            "requires_owner_decision": bool(item.get("requires_owner_decision")),
        },
        "stop_lines": stop_lines,
        "next_action": next_action,
        "next_command": {
            "command": command,
            "execution_posture": "review_only_not_executed_by_compiler",
            "requires_separate_authority_if_scope_crosses_stop_line": True,
        },
        "acceptance_proof": {
            "proof_artifacts": proof_artifacts,
            "proof_commands": proof_commands,
            "close_condition": item.get("close_condition")
            or "The source row is resolved or explicitly monitor-only, linked routes are current, and required validators pass.",
            "source_contract_requirements": [
                "originating action row is non-orphan and contract-complete",
                "linked source pointers remain parseable and current",
                "no authority flag widens to apply, approval, execution, mutation, or external action",
            ],
        },
        "expiry_reopen": {
            "expires_at_utc": freshness.get("expires_at_utc"),
            "review_by_utc": item.get("monitor_review_by_utc"),
            "reopen_trigger": str(reopen_trigger),
            "expiry_behavior": "block_current_action_until_upstream_source_refresh",
        },
        "later_outcome_pointer": later_outcome,
    }
    return decision


def recursive_key_scan(value: Any, path: str = "$") -> list[str]:
    leaks: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            normalized = str(key).strip().lower()
            child_path = f"{path}.{key}"
            if normalized in FORBIDDEN_CAPTURE_KEYS:
                leaks.append(f"forbidden_capture_key:{child_path}")
            leaks.extend(recursive_key_scan(child, child_path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            leaks.extend(recursive_key_scan(child, f"{path}[{index}]"))
    return leaks


def command_violation(command: Any) -> str | None:
    if command is None or str(command).strip() == "":
        return None
    text = str(command)
    for pattern in FORBIDDEN_COMMAND_PATTERNS:
        if pattern.search(text):
            return pattern.pattern
    return None


def json_type_matches(value: Any, expected_type: str) -> bool:
    """Match JSON Schema primitive types without Python bool/int ambiguity."""
    if expected_type == "null":
        return value is None
    if expected_type == "object":
        return isinstance(value, dict)
    if expected_type == "array":
        return isinstance(value, list)
    if expected_type == "string":
        return isinstance(value, str)
    if expected_type == "boolean":
        return isinstance(value, bool)
    if expected_type == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)
    if expected_type == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    return False


def json_type_name(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, dict):
        return "object"
    if isinstance(value, list):
        return "array"
    if isinstance(value, str):
        return "string"
    if isinstance(value, (int, float)):
        return "number"
    return type(value).__name__


def strict_schema_instance_errors(
    value: Any,
    schema: dict[str, Any],
    *,
    path: str = "$",
) -> list[str]:
    """Recursively validate the JSON Schema subset used by the shared decision contract."""
    errors: list[str] = []
    raw_expected = schema.get("type")
    expected_types = [raw_expected] if isinstance(raw_expected, str) else as_list(raw_expected)
    expected_types = [str(item) for item in expected_types]
    if expected_types and not any(json_type_matches(value, item) for item in expected_types):
        errors.append(
            f"strict_schema_type:{path}:expected={'|'.join(expected_types)}:actual={json_type_name(value)}"
        )
        return errors
    if isinstance(value, str) and not value.strip():
        errors.append(f"strict_schema_blank_string:{path}")
        return errors

    if isinstance(value, dict):
        properties = as_dict(schema.get("properties"))
        for required_key in as_list(schema.get("required")):
            if required_key not in value:
                errors.append(f"strict_schema_missing_required:{path}:{required_key}")
        if schema.get("additionalProperties") is False:
            for extra_key in sorted(set(value) - set(properties)):
                errors.append(f"strict_schema_additional_property:{path}.{extra_key}")
        for key, child in value.items():
            child_schema = properties.get(key)
            if isinstance(child_schema, dict):
                errors.extend(strict_schema_instance_errors(child, child_schema, path=f"{path}.{key}"))
    elif isinstance(value, list):
        item_schema = schema.get("items")
        if isinstance(item_schema, dict):
            for index, child in enumerate(value):
                errors.extend(strict_schema_instance_errors(child, item_schema, path=f"{path}[{index}]"))
    return errors


def validate_packet(packet: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    boundary = as_dict(packet.get("authority_boundary"))
    for key, expected in AUTHORITY_BOUNDARY.items():
        if boundary.get(key) is not expected:
            errors.append(f"authority_boundary_mismatch:{key}")
    for key in SENSITIVE_TRUE_KEYS:
        if boundary.get(key) is True:
            errors.append(f"forbidden_authority_true:{key}")
    input_paths = {str(as_dict(row).get("path")) for row in as_dict(packet.get("inputs")).values()}
    cycles = sorted(input_paths & FORBIDDEN_RUNTIME_INPUTS)
    if cycles:
        errors.append(f"producer_cycle_input_forbidden:{','.join(cycles)}")
    for source_name, descriptor in as_dict(packet.get("inputs")).items():
        row = as_dict(descriptor)
        if row.get("required") and not row.get("present"):
            errors.append(f"missing_required_source:{source_name}:{row.get('path')}")
        if row.get("required") and row.get("freshness_status") in {"stale", "unknown_generated_at"}:
            warnings.append(f"required_source_not_current:{source_name}:{row.get('freshness_status')}")
        if row.get("validation_status") in {"blocked", "error"}:
            errors.append(f"source_validation_blocked:{source_name}:{row.get('validation_status')}")
        elif row.get("validation_status") == "warning":
            warnings.append(f"source_validation_warning:{source_name}")

    decisions = [as_dict(row) for row in as_list(packet.get("decisions"))]
    ids: list[str] = []
    for index, decision in enumerate(decisions):
        decision_id = str(decision.get("decision_id") or f"row_{index}")
        ids.append(decision_id)
        errors.extend(
            f"decision_schema_violation:{decision_id}:{error}"
            for error in strict_schema_instance_errors(decision, DECISION_OBJECT_SCHEMA)
        )
        missing = sorted(REQUIRED_DECISION_FIELDS - set(decision))
        if missing:
            errors.append(f"decision_missing_fields:{decision_id}:{','.join(missing)}")
        if not re.fullmatch(r"wf88dec-[a-f0-9]{16}", decision_id):
            errors.append(f"invalid_decision_id:{decision_id}")
        stable_key = str(as_dict(decision.get("source_selection")).get("stable_key") or "")
        if stable_key and stable_decision_id(stable_key) != decision_id:
            errors.append(f"unstable_decision_id:{decision_id}")
        if not str(decision.get("question") or "").strip():
            errors.append(f"empty_question:{decision_id}")
        if not str(decision.get("recommendation") or "").strip():
            errors.append(f"empty_recommendation:{decision_id}")
        if len(as_list(decision.get("alternatives"))) < 2:
            errors.append(f"insufficient_alternatives:{decision_id}")
        if not as_list(decision.get("source_pointers")):
            errors.append(f"missing_source_pointers:{decision_id}")
        for pointer in as_list(decision.get("source_pointers")):
            source = as_dict(pointer)
            if source.get("path") not in input_paths:
                errors.append(f"unknown_source_pointer_path:{decision_id}:{source.get('path')}")
            if not str(source.get("json_pointer") or "").startswith("/"):
                errors.append(f"non_exact_json_pointer:{decision_id}:{source.get('json_pointer')}")
        if not str(decision.get("authority_class") or "").startswith("review_only"):
            errors.append(f"authority_class_not_review_only:{decision_id}:{decision.get('authority_class')}")
        if str(decision.get("state") or "").lower() in {
            "approved",
            "apply",
            "execute",
            "execution_ready",
            "ready_to_execute",
        }:
            errors.append(f"forbidden_decision_state:{decision_id}:{decision.get('state')}")
        if len(as_list(decision.get("stop_lines"))) < len(GLOBAL_STOP_LINES):
            errors.append(f"stop_lines_incomplete:{decision_id}")
        command = as_dict(decision.get("next_command")).get("command")
        violation = command_violation(command)
        if violation:
            errors.append(f"forbidden_next_command:{decision_id}:{violation}")
        for proof_command in as_list(as_dict(decision.get("acceptance_proof")).get("proof_commands")):
            violation = command_violation(proof_command)
            if violation:
                errors.append(f"forbidden_proof_command:{decision_id}:{violation}")
        later = as_dict(decision.get("later_outcome_pointer"))
        if not later.get("path") or not str(later.get("json_pointer") or "").startswith("/"):
            errors.append(f"later_outcome_pointer_incomplete:{decision_id}")
        uncertainty = as_dict(decision.get("conflict_uncertainty"))
        if uncertainty.get("conflict"):
            warnings.append(f"decision_conflict:{decision_id}")
        if as_dict(decision.get("freshness")).get("status") != "fresh":
            warnings.append(f"decision_source_warning:{decision_id}:{as_dict(decision.get('freshness')).get('status')}")
    if len(ids) != len(set(ids)):
        errors.append("duplicate_decision_ids")
    leaks = recursive_key_scan(packet)
    errors.extend(leaks)
    return {
        "status": "blocked" if errors else ("warning" if warnings else "ok"),
        "errors": sorted(set(errors)),
        "warnings": sorted(set(warnings)),
    }


def build_packet(
    *,
    root: Path = ROOT,
    source_payloads: dict[str, dict[str, Any] | None] | None = None,
    source_load_errors: dict[str, str | None] | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    current = now or utc_now_dt()
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    current = current.astimezone(timezone.utc).replace(microsecond=0)
    if source_payloads is None:
        payloads, load_errors = load_sources(root)
    else:
        payloads = {name: source_payloads.get(name) for name in SOURCE_SPECS}
        load_errors = {
            name: (source_load_errors or {}).get(name)
            or (None if isinstance(payloads.get(name), dict) else "missing_source")
            for name in SOURCE_SPECS
        }
    descriptors = source_descriptors(payloads, load_errors, current)
    queue = as_dict(payloads.get("actionable_improvement_queue"))
    decisions = [
        compile_decision(index, as_dict(raw), payloads, descriptors)
        for index, raw in enumerate(as_list(queue.get("action_items")))
    ]
    state_counts = Counter(str(row.get("state")) for row in decisions)
    authority_counts = Counter(str(row.get("authority_class")) for row in decisions)
    later_counts = Counter(str(as_dict(row.get("later_outcome_pointer")).get("status")) for row in decisions)
    packet: dict[str, Any] = {
        "schema": SCHEMA,
        "generated_at_utc": utc_text(current),
        "workflow_id": "WF88",
        "status": "decision_objects_ready_review_only",
        "purpose": "Deterministic review-only compilation of upstream actionability and route evidence into structured decision objects.",
        "authority_boundary": AUTHORITY_BOUNDARY.copy(),
        "runtime_dependency_contract": {
            "direction": "upstream_action_surfaces_to_decision_compiler_to_wiki",
            "wiki_or_os2_inputs_forbidden": sorted(FORBIDDEN_RUNTIME_INPUTS),
            "model_or_api_call": False,
            "source_selection_first": True,
        },
        "inputs": descriptors,
        "summary": {
            "decision_object_count": len(decisions),
            "state_counts": dict(sorted(state_counts.items())),
            "authority_class_counts": dict(sorted(authority_counts.items())),
            "conflict_count": sum(bool(as_dict(row.get("conflict_uncertainty")).get("conflict")) for row in decisions),
            "uncertain_count": sum(bool(as_list(as_dict(row.get("conflict_uncertainty")).get("uncertainties"))) for row in decisions),
            "source_warning_count": sum(as_dict(row.get("freshness")).get("status") != "fresh" for row in decisions),
            "later_outcome_status_counts": dict(sorted(later_counts.items())),
            "owner_review_required_count": sum(row.get("state") == "owner_review_required" for row in decisions),
            "blocked_count": sum(str(row.get("state") or "").startswith("blocked") for row in decisions),
            "review_or_monitor_count": sum(not str(row.get("state") or "").startswith("blocked") for row in decisions),
        },
        "decisions": decisions,
    }
    packet["leak_guard"] = {
        "raw_capture_key_count": len(recursive_key_scan(packet)),
        "runtime_cycle_input_count": len(
            {str(as_dict(row).get("path")) for row in descriptors.values()} & FORBIDDEN_RUNTIME_INPUTS
        ),
        "forbidden_authority_true_count": sum(
            key in SENSITIVE_TRUE_KEYS and value is True for key, value in AUTHORITY_BOUNDARY.items()
        ),
        "decision_apply_or_execute_state_count": sum(
            str(row.get("state") or "").lower() in {"approved", "apply", "execute", "execution_ready", "ready_to_execute"}
            for row in decisions
        ),
        "pass": False,
    }
    packet["validation"] = validate_packet(packet)
    packet["leak_guard"]["pass"] = (
        packet["leak_guard"]["raw_capture_key_count"] == 0
        and packet["leak_guard"]["runtime_cycle_input_count"] == 0
        and packet["leak_guard"]["forbidden_authority_true_count"] == 0
        and packet["leak_guard"]["decision_apply_or_execute_state_count"] == 0
        and packet["validation"]["status"] != "blocked"
    )
    if packet["validation"]["status"] == "blocked":
        packet["status"] = "decision_compiler_blocked_fail_closed"
    elif packet["validation"]["status"] == "warning":
        packet["status"] = "decision_objects_warning_review_only"
    packet["summary"]["status"] = packet["status"]
    packet["summary"]["validation_status"] = packet["validation"]["status"]
    return packet


def render_markdown(packet: dict[str, Any]) -> str:
    summary = as_dict(packet.get("summary"))
    lines = [
        "# WF88 Decision Compiler",
        "",
        "## Outcome",
        "",
        f"- Status: `{packet.get('status')}`",
        f"- Validation: `{as_dict(packet.get('validation')).get('status')}`",
        f"- Decision objects: `{summary.get('decision_object_count')}`",
        f"- State counts: `{json.dumps(as_dict(summary.get('state_counts')), sort_keys=True)}`",
        f"- Conflicts: `{summary.get('conflict_count')}`",
        f"- Source warnings: `{summary.get('source_warning_count')}`",
        f"- Leak guard pass: `{as_dict(packet.get('leak_guard')).get('pass')}`",
        "",
        "## Decisions",
        "",
        "| Decision | State | Authority | Owner / route | Freshness | Recommendation |",
        "|---|---|---|---|---|---|",
    ]
    for raw in as_list(packet.get("decisions")):
        row = as_dict(raw)
        owner = as_dict(row.get("owner_route"))
        recommendation = str(row.get("recommendation") or "").replace("|", "\\|")
        lines.append(
            f"| `{row.get('decision_id')}` | `{row.get('state')}` | `{row.get('authority_class')}` | "
            f"`{owner.get('owner_workflow')} / {owner.get('route')}` | `{as_dict(row.get('freshness')).get('status')}` | {recommendation} |"
        )
    lines.extend(
        [
            "",
            "## Runtime dependency contract",
            "",
            "The compiler reads only upstream actionability, docket, router, loop-trace, improvement, and outcome artifacts. It does not read the WF88 wiki synthesis or OS2 control packet, so the wiki may consume this output without a producer cycle.",
            "",
            "## Boundary",
            "",
            "Generated decisions are review/routing objects only. They do not approve, apply, execute, mutate finance/canon/runtime/cron/account state, capture raw prompts/tools, or infer owner approval.",
            "",
        ]
    )
    return "\n".join(lines)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--write-md", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--pretty", action="store_true")
    parser.add_argument("--out", type=Path, default=OUT)
    parser.add_argument("--md-out", type=Path, default=MD_OUT)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    packet = build_packet()
    out = args.out if args.out.is_absolute() else ROOT / args.out
    md_out = args.md_out if args.md_out.is_absolute() else ROOT / args.md_out
    if args.write:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(packet, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    if args.write_md:
        md_out.parent.mkdir(parents=True, exist_ok=True)
        md_out.write_text(render_markdown(packet), encoding="utf-8")
    if args.pretty:
        print(json.dumps(packet, indent=2, ensure_ascii=False, sort_keys=True))
    else:
        print(
            json.dumps(
                {
                    "status": packet.get("status"),
                    "validation": as_dict(packet.get("validation")).get("status"),
                    "decision_objects": as_dict(packet.get("summary")).get("decision_object_count"),
                    "state_counts": as_dict(packet.get("summary")).get("state_counts"),
                    "conflicts": as_dict(packet.get("summary")).get("conflict_count"),
                    "leak_guard_pass": as_dict(packet.get("leak_guard")).get("pass"),
                    "json": str(out.relative_to(ROOT)).replace("\\", "/") if out.is_relative_to(ROOT) else str(out),
                    "md": str(md_out.relative_to(ROOT)).replace("\\", "/") if md_out.is_relative_to(ROOT) else str(md_out),
                },
                indent=2,
            )
        )
    if args.validate and as_dict(packet.get("validation")).get("status") == "blocked":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
