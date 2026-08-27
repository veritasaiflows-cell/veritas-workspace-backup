#!/usr/bin/env python3
"""Build the PM program-state control packet.

This script turns live workflow proof into a deterministic PM operating
surface. It is review-only coordination infrastructure: it can report stale
proof, blockers, lane status, and next safe actions, but it cannot mutate
canon, portfolio state, customer state, cron config, archives, or execution
systems.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from lib.workflow_control import find_override, is_on_hold, load_registry
from market_data_utils import atomic_write_json, load_json_artifact

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"

PROGRAM_STATE_JSON = TMP / "pm-program-state.json"
LANE_SCOREBOARD_JSON = TMP / "pm-lane-scoreboard.json"
NEXT_ACTIONS_JSON = TMP / "pm-next-actions.json"
BLOCKER_REGISTER_JSON = TMP / "pm-blocker-register.json"
DEFAULT_DB = TMP / "pm-program-state.sqlite"
PM_COCKPIT_SOURCE_REGISTRY = ROOT / "state" / "pm-cockpit-source-registry.json"

SCHEMA = "veritas.pm_program_state.v1"
LANE_SCOREBOARD_SCHEMA = "veritas.pm_lane_scoreboard.v1"
NEXT_ACTION_SCHEMA = "veritas.pm_next_actions.v1"
BLOCKER_SCHEMA = "veritas.pm_blocker_register.v1"
AZ = ZoneInfo("America/Phoenix")
MARKET_REFRESH_TIME = time(6, 55)
NYSE_FULL_HOLIDAYS_2026 = {
    date(2026, 1, 1),
    date(2026, 1, 19),
    date(2026, 2, 16),
    date(2026, 4, 3),
    date(2026, 5, 25),
    date(2026, 6, 19),
    date(2026, 7, 3),
    date(2026, 9, 7),
    date(2026, 11, 26),
    date(2026, 12, 25),
}

ACTIVE_WORKFLOWS = ROOT / "06. Playbooks" / "Active Workflows.md"
SMB_SAAS_PARALLEL_PLAN = ROOT / "09. Archive" / "Legacy Audit Roots - Archived" / "Audit" / "SMB-SaaS-Parallel-Implementation-Plan-2026-06-18.md"

AUTHORITY_FALSE_KEYS = {
    "public_launch_allowed",
    "public_launch_ready",
    "real_customer_data_allowed",
    "customer_data_retention_allowed",
    "external_delivery_allowed",
    "customer_output_external_delivery_allowed",
    "legal_or_compliance_ready",
    "source_licensing_assumed",
    "personalized_regulated_advice_allowed",
    "brokerage_or_account_connection_allowed",
    "paper_or_live_execution_allowed",
    "paper_order_execution_allowed",
    "live_trade_or_account_action_allowed",
    "trade_or_account_action_allowed",
    "money_movement_allowed",
    "portfolio_or_canon_mutation_allowed",
    "portfolio_mutation_allowed",
    "canonical_note_mutation_allowed",
    "sql_or_ticker_import_allowed",
    "owner_approval_inferred",
    "owner_approval_granted",
    "config_auth_channel_runtime_mutation_allowed",
    "destructive_cleanup_allowed",
}

GLOBAL_STOP_LINES = {
    "public_launch_allowed": False,
    "real_customer_data_allowed": False,
    "external_delivery_allowed": False,
    "portfolio_or_canon_mutation_allowed": False,
    "paper_or_live_execution_allowed": False,
    "owner_approval_inferred": False,
    "sql_or_ticker_import_allowed": False,
    "config_auth_channel_runtime_mutation_allowed": False,
}

OK_STATUSES = {
    "ok",
    "ok_with_production_stale_cards",
    "ready",
    "active_gate_contract",
    "control_plane_ready",
    "handoff_ready",
    "ready_for_internal_pm_review",
    "ready_for_internal_artifact_only_pm_handoff",
    "internal_service_led_readiness_plan_ready",
    "review_only_ok",
    "ok_no_work",
}

WARNING_TOKENS = ("warning", "warn", "review", "stale", "partial")
BLOCKED_TOKENS = ("blocked", "critical", "error", "failed", "missing")

# Gates whose "blocked" signal is intentional / by-design. A matching artifact
# status is classified as a transparent "gated" lane state instead of a hard
# blocker. WF72 A2 is no longer listed here because its fallback-backed Go guard
# is expected to be green; a blocked A2 guard is now real breakage.
EXPECTED_GATES: list[dict[str, Any]] = [
    {
        "path": "tmp/retail-customer-output-decision-packet.json",
        "field": "status",
        "value": "blocked",
        "reason": "Customer output is intentionally blocked while retail routing is resumed for internal answer-safety proof only.",
        "pending_work": "Owner launch approval, source licensing, privacy/customer-data policy, legal/compliance review, disclaimer approval, personalization policy, external delivery, and runtime exposure gates.",
    },
    {
        "path": "tmp/automation-stack-hardening-pass.json",
        "field": "status",
        "value": "warning",
        "reason": "Retail routing uses the hardening pass as support proof; current warnings are broader cron/handoff optimization work, not retail answer-safety failures.",
        "pending_work": "Finish the cron enabled-count and morning handoff retirement cleanup before treating the wider automation stack as fully clean.",
    },
]

def match_expected_gate(path: str, field: str, value: Any) -> dict[str, Any] | None:
    for gate in EXPECTED_GATES:
        if gate["path"] == path and gate["field"] == field and str(gate["value"]) == str(value):
            return gate
    return None


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_utc(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    text = value.replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(text)
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


def load_json(path: Path) -> dict[str, Any]:
    payload = load_json_artifact(path)
    return payload if isinstance(payload, dict) else {}


def normalize_registry_path(value: Any) -> str:
    return str(value or "").replace("\\", "/")


def source_registry_index(registry_path: Path = PM_COCKPIT_SOURCE_REGISTRY) -> dict[str, dict[str, Any]]:
    registry = load_json(registry_path)
    index: dict[str, dict[str, Any]] = {}
    for source in as_list(registry.get("sources")):
        row = as_dict(source)
        key = str(row.get("key") or "")
        path = normalize_registry_path(row.get("path"))
        if key:
            index[f"key:{key}"] = row
        if path:
            index[f"path:{path}"] = row
    return index


def registry_source_for_artifact(
    key: str,
    path: str,
    registry_index: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    index = registry_index if registry_index is not None else source_registry_index()
    return index.get(f"key:{key}") or index.get(f"path:{normalize_registry_path(path)}") or {}


def registry_probe_metadata(source: dict[str, Any]) -> dict[str, Any]:
    fields = (
        "key",
        "path",
        "required",
        "max_age_hours",
        "group",
        "role",
        "freshness_cadence",
        "market_calendar_grace",
        "stale_action",
        "blocks_readiness",
        "lifecycle",
        "activation_condition",
        "stale_classification_note",
    )
    return {field: source[field] for field in fields if field in source}


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def nested_get(obj: dict[str, Any], dotted: str) -> Any:
    current: Any = obj
    for part in dotted.split("."):
        if not isinstance(current, dict):
            return None
        current = current.get(part)
    return current


def wf74_finance_source_open_action_override(lane_id: str, status: str, loaded_payloads: list[dict[str, Any]]) -> dict[str, Any]:
    if lane_id != "wf74_learning_runtime" or status != "blocked":
        return {}
    for payload in loaded_payloads:
        summary = as_dict(payload.get("summary"))
        if summary.get("finance_response_quality_recommended_repair_route") != "wf78_wf85_source_open_repair":
            continue
        source_open_blocked_count = summary.get("finance_response_quality_source_open_blocked_count")
        return {
            "action_type": "inspect_blocker",
            "description": (
                "Route the WF74 scorecard blocker through the finance source-open repair conveyor: run "
                "wf78_source_open_repair_executor.py, wf78_source_open_work_packet.py, and "
                "finance_response_quality_slice.py, then rerun the WF74 collection runner. "
                f"Current source_open_blocked_count={source_open_blocked_count}."
            ),
            "department": "finance_wf78_wf84_wf85",
            "department_owner": "main-session-veritas-finance",
            "owner_workflow": "WF78/WF84/WF85",
            "top_job_id": "pm-wf74-finance-source-open-quality-repair",
            "top_job_title": "Clear finance response quality source-open blockers so WF74 scorecard can pass",
            "blocker_chain": summary.get("finance_response_quality_blocker_chain") or [],
        }
    return {}


def artifact_probe(
    key: str,
    path: Path,
    required: bool = True,
    max_age_hours: int | None = None,
    freshness_basis: str = "generated_at_utc",
    registry_index: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    payload = load_json_artifact(path)
    now = datetime.now(timezone.utc)
    relative_path = rel(path)
    registry_source = registry_source_for_artifact(key, relative_path, registry_index)
    registry_required = registry_source.get("required")
    effective_required = registry_required if isinstance(registry_required, bool) else required
    probe: dict[str, Any] = {
        "key": key,
        "path": relative_path,
        "required": effective_required,
        "exists": path.exists(),
        "parseable_json": isinstance(payload, dict),
        "json_expected": True,
        "max_age_hours": max_age_hours,
    }
    if registry_source:
        probe["source_registry"] = registry_probe_metadata(registry_source)
    if path.exists():
        probe["mtime_utc"] = datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    if isinstance(payload, dict):
        generated = payload.get("generated_at_utc")
        probe["schema"] = payload.get("schema") or payload.get("schema_version")
        probe["status"] = payload.get("status")
        probe["generated_at_utc"] = generated
        probe["freshness_basis"] = freshness_basis
        freshness_value = probe.get("mtime_utc") if freshness_basis == "mtime_utc" else generated
        probe["age_hours"] = age_hours(freshness_value, now)
        validation = payload.get("validation")
        if isinstance(validation, dict):
            probe["validation_status"] = validation.get("status")
            probe["validation_errors"] = validation.get("errors", [])
            probe["validation_warnings"] = validation.get("warnings", [])
    return probe


def value_status(value: Any) -> str:
    text = str(value or "").lower()
    if not text:
        return "unknown"
    if text in OK_STATUSES:
        return "ok"
    normalized = text.replace("-", "_").replace(" ", "_")
    if normalized in {"notready", "not_ready", "unready"} or normalized.endswith(("_not_ready", "_unready")):
        return "blocked"
    if any(token in text for token in BLOCKED_TOKENS):
        return "blocked"
    if text.endswith("_ready"):
        return "ok"
    if any(token in text for token in WARNING_TOKENS):
        return "warning"
    return "unknown"


def collect_authority_violations(value: Any, prefix: str = "") -> list[dict[str, Any]]:
    violations: list[dict[str, Any]] = []
    if isinstance(value, dict):
        for key, child in value.items():
            path = f"{prefix}.{key}" if prefix else key
            # SQLite-backed artifacts often encode false as 0. Treat only
            # actual truthy widening as a violation.
            if key in AUTHORITY_FALSE_KEYS and child not in (False, 0, None):
                violations.append({"path": path, "value": child})
            if isinstance(child, (dict, list)):
                violations.extend(collect_authority_violations(child, path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            if isinstance(child, (dict, list)):
                violations.extend(collect_authority_violations(child, f"{prefix}[{index}]"))
    return violations


def artifact_required_for_readiness(item: dict[str, Any]) -> bool:
    registry = as_dict(item.get("source_registry"))
    if isinstance(registry.get("required"), bool):
        return bool(registry["required"])
    return bool(item.get("required"))


def artifact_status_blocks_readiness(item: dict[str, Any]) -> bool:
    """Keep inactive historical/future support status visible without blocking.

    Status suppression is intentionally narrower than stale suppression. A
    source must be explicitly non-required, explicitly non-blocking, and
    lifecycle-classified as demoted/legacy/historical/future. Required current
    workflow artifacts continue to block even when their stale cadence is
    monitor-only or event-triggered.
    """
    registry = as_dict(item.get("source_registry"))
    lifecycle = str(registry.get("lifecycle") or "").strip().lower()
    inactive_support = (
        registry.get("required") is False
        and registry.get("blocks_readiness") is False
        and any(token in lifecycle for token in ("demoted", "legacy", "historical", "future"))
    )
    return not inactive_support


def market_window(now: datetime) -> dict[str, Any]:
    local = now.astimezone(AZ)
    local_date = local.date()
    is_weekday = local.weekday() < 5
    market_holiday = local_date in NYSE_FULL_HOLIDAYS_2026
    if market_holiday:
        window = "market_holiday"
    elif not is_weekday:
        window = "weekend"
    elif local.time() < MARKET_REFRESH_TIME:
        window = "pre_refresh"
    else:
        window = "market_refresh_eligible"
    return {
        "timezone": "America/Phoenix",
        "now_local": local.replace(microsecond=0).isoformat(),
        "window": window,
        "market_holiday": market_holiday,
        "weekend": not is_weekday,
        "closed_market_grace_active": window in {"market_holiday", "weekend", "pre_refresh"},
    }


def next_market_refresh_window(now: datetime) -> str:
    local = now.astimezone(AZ)
    candidate = local.date()
    while True:
        candidate_dt = datetime.combine(candidate, MARKET_REFRESH_TIME, tzinfo=AZ)
        if candidate_dt > local and candidate.weekday() < 5 and candidate not in NYSE_FULL_HOLIDAYS_2026:
            return candidate_dt.replace(microsecond=0).isoformat()
        candidate += timedelta(days=1)


def classify_stale_artifact(item: dict[str, Any], now: datetime) -> dict[str, Any]:
    registry = as_dict(item.get("source_registry"))
    cadence = str(registry.get("freshness_cadence") or "").strip().lower()
    stale_action = str(registry.get("stale_action") or "").strip().lower()
    role = str(registry.get("role") or "").strip().lower()
    lifecycle = str(registry.get("lifecycle") or "").strip().lower()
    market_grace = registry.get("market_calendar_grace") is True
    blocks_readiness = registry.get("blocks_readiness")
    if not isinstance(blocks_readiness, bool):
        blocks_readiness = stale_action in {"refresh_now", "true_blocker"} or not stale_action

    market = market_window(now)
    bucket = "true_blocker" if blocks_readiness else "monitor_only_stale"
    if registry.get("required") is False and any(token in lifecycle for token in ("demoted", "legacy", "historical")):
        bucket = "monitor_only_stale"
    elif stale_action in {"monitor_only", "monitor_only_stale"}:
        bucket = "monitor_only_stale"
    elif stale_action in {"event_triggered", "event_triggered_waiting"}:
        bucket = "event_triggered_waiting"
    elif stale_action == "refresh_now":
        bucket = "refresh_now"
    elif stale_action == "suppress_until_next_market_open":
        bucket = "market_closed_grace" if market.get("closed_market_grace_active") else "refresh_now"
    elif market_grace and market.get("closed_market_grace_active"):
        bucket = "market_closed_grace"
    elif cadence in {"event_triggered", "on_demand"}:
        bucket = "event_triggered_waiting"
    elif cadence in {"weekly", "weekly_or_on_demand", "monthly", "static_reference"} and not blocks_readiness:
        bucket = "monitor_only_stale"
    elif any(token in role for token in ("proposal", "legacy", "historical", "review_only")) and not blocks_readiness:
        bucket = "monitor_only_stale"

    return {
        "key": item.get("key"),
        "path": item.get("path"),
        "age_hours": item.get("age_hours"),
        "max_age_hours": item.get("max_age_hours"),
        "bucket": bucket,
        "freshness_cadence": cadence or None,
        "stale_action": stale_action or None,
        "blocks_readiness": blocks_readiness,
        "market_calendar_grace": market_grace,
        "next_eligible_refresh_window": next_market_refresh_window(now) if bucket == "market_closed_grace" else None,
    }


def artifact_health(artifacts: list[dict[str, Any]], now: datetime | None = None) -> dict[str, Any]:
    now = now or datetime.now(timezone.utc)
    missing = [a for a in artifacts if artifact_required_for_readiness(a) and not a["exists"]]
    unreadable = [
        a
        for a in artifacts
        if artifact_required_for_readiness(a)
        and a["exists"]
        and a.get("json_expected") is not False
        and not a["parseable_json"]
    ]
    stale = []
    suppressed_stale = []
    for item in artifacts:
        if (
            item.get("max_age_hours") is not None
            and item.get("age_hours") is not None
            and item["age_hours"] > item["max_age_hours"]
        ):
            classification = classify_stale_artifact(item, now)
            if classification["bucket"] in {"refresh_now", "true_blocker"}:
                stale.append({**item, "stale_classification": classification})
            else:
                suppressed_stale.append({**item, "stale_classification": classification})
    problem = []
    warned = []
    expected = []
    suppressed_statuses = []
    for item in artifacts:
        for field in ("status", "validation_status"):
            state = value_status(item.get(field))
            if state in {"blocked", "warning"} and not artifact_status_blocks_readiness(item):
                suppressed_statuses.append({
                    "path": item["path"],
                    "field": field,
                    "value": item.get(field),
                    "reason": "registry_non_required_non_blocking_support",
                })
                continue
            if state == "blocked":
                gate = match_expected_gate(item["path"], field, item.get(field))
                if gate is not None:
                    expected.append({
                        "path": item["path"],
                        "field": field,
                        "value": item.get(field),
                        "reason": gate["reason"],
                        "pending_work": gate["pending_work"],
                    })
                else:
                    problem.append({"path": item["path"], "field": field, "value": item.get(field)})
            elif state == "warning":
                gate = match_expected_gate(item["path"], field, item.get(field))
                if gate is not None:
                    expected.append({
                        "path": item["path"],
                        "field": field,
                        "value": item.get(field),
                        "reason": gate["reason"],
                        "pending_work": gate["pending_work"],
                    })
                else:
                    warned.append({"path": item["path"], "field": field, "value": item.get(field)})
    return {
        "required_count": len([a for a in artifacts if artifact_required_for_readiness(a)]),
        "present_count": len([a for a in artifacts if a["exists"]]),
        "missing_required": missing,
        "unreadable_required": unreadable,
        "stale": stale,
        "suppressed_stale": suppressed_stale,
        "suppressed_stale_count": len(suppressed_stale),
        "problem_statuses": problem,
        "warning_statuses": warned,
        "suppressed_statuses": suppressed_statuses,
        "suppressed_status_count": len(suppressed_statuses),
        "expected_gates": expected,
    }


def lane_status(health: dict[str, Any], authority_violations: list[dict[str, Any]]) -> str:
    if health["missing_required"] or health["unreadable_required"] or authority_violations or health["problem_statuses"]:
        return "blocked"
    if health["stale"]:
        return "stale"
    if health["warning_statuses"]:
        return "needs_validation"
    if health.get("expected_gates"):
        return "gated"
    return "ready"


def readiness_score(status: str) -> int:
    return {
        "ready": 90,
        "watch": 75,
        "gated": 75,
        "needs_validation": 60,
        "stale": 45,
        "blocked": 15,
        "complete_for_now": 95,
        "on_hold": 40,
    }.get(status, 50)


def build_lane(
    lane_id: str,
    title: str,
    purpose: str,
    artifacts: list[dict[str, Any]],
    next_action_when_ready: str,
    next_action_when_stale: str,
    stop_lines: list[str],
    enforce_authority_scan: bool = True,
) -> dict[str, Any]:
    registry = load_registry()
    loaded_payloads = [load_json(ROOT / item["path"]) for item in artifacts if item.get("parseable_json")]
    violations: list[dict[str, Any]] = []
    if enforce_authority_scan:
        for payload in loaded_payloads:
            violations.extend(collect_authority_violations(payload))
    health = artifact_health(artifacts)
    status = lane_status(health, violations)
    if lane_id == "authority" and status == "ready":
        status = "complete_for_now"
    hold = find_override(lane_id, lane_id=lane_id, workflow_name=title, registry=registry)
    if is_on_hold(hold):
        status = "on_hold"
    next_action = next_action_when_stale if status in {"stale", "needs_validation", "blocked"} else next_action_when_ready
    action_override = wf74_finance_source_open_action_override(lane_id, status, loaded_payloads)
    if is_on_hold(hold):
        next_action = hold["next_action"]
        action_type = "hold"
    elif status == "blocked":
        action_type = "inspect_blocker"
    elif status == "stale":
        action_type = "refresh_artifact"
    elif status == "needs_validation":
        action_type = "run_validator"
    else:
        action_type = "execute_safe_next_step"
    if action_override:
        next_action = str(action_override.get("description") or next_action)
        action_type = str(action_override.get("action_type") or action_type)
    blockers = []
    for item in health["missing_required"]:
        blockers.append({"severity": "critical", "kind": "missing_required_artifact", "lane_id": lane_id, "path": item["path"]})
    for item in health["unreadable_required"]:
        blockers.append({"severity": "critical", "kind": "unreadable_required_artifact", "lane_id": lane_id, "path": item["path"]})
    for item in health["problem_statuses"]:
        blockers.append({"severity": "critical", "kind": "problem_status", "lane_id": lane_id, **item})
    for item in violations:
        blockers.append({"severity": "critical", "kind": "authority_boundary_widened", "lane_id": lane_id, **item})
    for item in health["stale"]:
        blockers.append({"severity": "warning", "kind": "stale_proof", "lane_id": lane_id, "path": item["path"], "age_hours": item.get("age_hours"), "max_age_hours": item.get("max_age_hours")})
    return {
        "lane_id": lane_id,
        "title": title,
        "purpose": purpose,
        "status": status,
        "readiness_score": readiness_score(status),
        "readiness_contribution": (
            "raises PM/control confidence" if status in {"ready", "complete_for_now"}
            else "operational; intentional gate pending promotion" if status == "gated"
            else "limits PM/control confidence"
        ),
        "artifact_health": health,
        "expected_gates": health.get("expected_gates", []),
        "hold": hold,
        "authority_violations": violations,
        "blockers": blockers,
        "next_action": {
            "action_id": f"{lane_id}-{action_type}",
            "action_type": action_type,
            "description": next_action,
            "lane_id": lane_id,
            "authority": "review_only",
            "inline_execution_allowed": False,
            "helper_lane_allowed_from_main_session": action_type in {"refresh_artifact", "run_validator", "execute_safe_next_step"},
            "heartbeat_may_execute": False,
            "stop_lines": stop_lines,
            **{key: value for key, value in action_override.items() if key not in {"action_type", "description"}},
        },
        "source_artifacts": artifacts,
        "stop_lines": stop_lines,
    }


def source_artifacts() -> dict[str, dict[str, Any]]:
    return {
        "active_workflows": {
            "path": rel(ACTIVE_WORKFLOWS),
            "exists": ACTIVE_WORKFLOWS.exists(),
            "parseable_json": False,
            "json_expected": False,
            "required": True,
        },
        "smb_saas_parallel_morning_plan": {
            "key": "smb_saas_parallel_morning_plan",
            "path": rel(SMB_SAAS_PARALLEL_PLAN),
            "exists": SMB_SAAS_PARALLEL_PLAN.exists(),
            "parseable_json": False,
            "json_expected": False,
            "required": True,
        },
        "wf75_operator_console": artifact_probe("wf75_operator_console", TMP / "wf75-operator-console.json", True, 24),
        "wf75_service_state": artifact_probe("wf75_service_state", TMP / "wf75-service-state-current.json", True, 48),
        "wf75_readiness_plan": artifact_probe("wf75_readiness_plan", TMP / "wf75-service-led-saas-readiness-plan.json", True, 168),
        "json_sql_promotion_index": artifact_probe("json_sql_promotion_index", TMP / "json-sql-promotion-index.json", True, 72),
        "json_sql_promotion_registry": artifact_probe("json_sql_promotion_registry", TMP / "json-sql-promotion-registry.json", True, 72),
        "json_sql_promotion_sqlite": {
            "key": "json_sql_promotion_sqlite",
            "path": "tmp/json-sql-promotion-index.sqlite",
            "required": True,
            "exists": (TMP / "json-sql-promotion-index.sqlite").exists(),
            "parseable_json": False,
            "json_expected": False,
        },
        "veritas_harness_scorecard": artifact_probe("veritas_harness_scorecard", TMP / "veritas-harness-scorecard.json", True, 48),
        "authority_matrix": artifact_probe("authority_matrix", TMP / "authority-matrix.json", True, 168),
        "automation_stack_hardening_pass": artifact_probe("automation_stack_hardening_pass", TMP / "automation-stack-hardening-pass.json", True, 168),
        "retail_truth_routing_contract": artifact_probe("retail_truth_routing_contract", TMP / "retail-truth-routing-contract.json", True, 168),
        "retail_answer_harness": artifact_probe("retail_answer_harness", TMP / "retail-answer-harness.json", True, 24),
        "retail_automation_control_plane": artifact_probe("retail_automation_control_plane", TMP / "retail-automation-control-plane.json", True, 24),
        "retail_customer_output_decision": artifact_probe("retail_customer_output_decision", TMP / "retail-customer-output-decision-packet.json", True, 24),
        "wf75_pm_handoff": artifact_probe("wf75_pm_handoff", TMP / "wf75-artifact-only-pm-handoff.json", True, 48),
        "wf75_pm_weekly_update": artifact_probe("wf75_pm_weekly_update", TMP / "wf75-pm-weekly-update.json", True, 168),
        "wf75_pm_readiness_brief": artifact_probe("wf75_pm_readiness_brief", TMP / "wf75-pm-readiness-brief.json", True, 168),
        "wf75_pm_readiness_pdf": {
            "key": "wf75_pm_readiness_pdf",
            "path": "tmp/wf75-pm-readiness-brief.pdf",
            "required": True,
            "exists": (TMP / "wf75-pm-readiness-brief.pdf").exists(),
            "parseable_json": False,
            "json_expected": False,
        },
        "current_window_artifacts": artifact_probe("current_window_artifacts", TMP / "current-window-artifacts.json", False, 24),
        "finance_data_coverage": artifact_probe("finance_data_coverage", TMP / "finance-data-coverage-current.json", False, 48),
        "ticker_card_refresh_gate": artifact_probe("ticker_card_refresh_gate", TMP / "finance-ticker-card-refresh-gate.json", True, 24),
        "ticker_card_freshness_owner_runner": artifact_probe("ticker_card_freshness_owner_runner", TMP / "ticker-card-freshness-owner-runner.json", True, 24),
        "tier_promotion_review_gate": artifact_probe("tier_promotion_review_gate", TMP / "wf78-tier-promotion-review-gate.json", True, 24),
        "tier_b_research_packets": artifact_probe("tier_b_research_packets", TMP / "wf78-tier-b-research-packets.json", True, 24),
        "tier_b_research_packet_requests": artifact_probe("tier_b_research_packet_requests", TMP / "wf78-tier-b-research-packet-requests.json", True, 24),
        "tier_b_research_packet_phase2_eval": artifact_probe("tier_b_research_packet_phase2_eval", TMP / "wf78-tier-b-research-packet-phase2-eval.json", True, 24),
        # This packet preserves the original owner-decision timestamp after
        # the Tier C import is applied. PM freshness should track the refreshed
        # packet file, not rewrite the historical approval timestamp.
        "tier_c_owner_decision_packet": artifact_probe(
            "tier_c_owner_decision_packet",
            TMP / "wf78-101-200-tier-c-owner-decision-packet.json",
            True,
            24,
            freshness_basis="mtime_utc",
        ),
        "wf78_tier_a_confidence_gate": artifact_probe("wf78_tier_a_confidence_gate", TMP / "wf78-tier-a-confidence-gate.json", True, 24),
        "wf78_auto_tier_router": artifact_probe("wf78_auto_tier_router", TMP / "wf78-auto-tier-routing.json", True, 24),
        "wf78_capital_review_queue": artifact_probe("wf78_capital_review_queue", TMP / "wf78-capital-review-queue.json", True, 24),
        "wf78_event_triggered_rerouting": artifact_probe("wf78_event_triggered_rerouting", TMP / "wf78-event-triggered-rerouting.json", True, 24),
        "wf78_evidence_drag_reduction": artifact_probe("wf78_evidence_drag_reduction", TMP / "wf78-evidence-drag-reduction.json", True, 24),
        "parallel_repeatable_work_orchestration": artifact_probe("parallel_repeatable_work_orchestration", TMP / "parallel-repeatable-work-orchestration.json", True, 24),
        "macro_event_guard_loop": artifact_probe("macro_event_guard_loop", TMP / "macro-event-guard-loop.json", True, 24),
        "wf78_owner_card_prep_loop": artifact_probe("wf78_owner_card_prep_loop", TMP / "wf78-owner-card-prep-loop.json", True, 24),
        "wf78_tier_a_evidence_repair_batch": artifact_probe("wf78_tier_a_evidence_repair_batch", TMP / "wf78-tier-a-evidence-repair-batch.json", True, 24),
        "wf78_evidence_family_repair": artifact_probe("wf78_evidence_family_repair", TMP / "wf78-evidence-family-repair.json", True, 24),
        "wf78_source_open_repair_execution": artifact_probe("wf78_source_open_repair_execution", TMP / "wf78-source-open-repair-execution.json", False, 72),
        "wf78_source_open_work_packets": artifact_probe("wf78_source_open_work_packets", TMP / "wf78-source-open-work-packets.json", True, 24),
        "wf78_position_sizing_surface_review": artifact_probe("wf78_position_sizing_surface_review", TMP / "wf78-position-sizing-surface-review.json", True, 24),
        "wf78_deployment_readiness_review": artifact_probe("wf78_deployment_readiness_review", TMP / "wf78-deployment-readiness-review.json", True, 24),
        "wf78_source_artifact_capture_review": artifact_probe("wf78_source_artifact_capture_review", TMP / "wf78-source-artifact-capture-review.json", True, 24),
        "wf78_position_sizing_integration_proposal": artifact_probe("wf78_position_sizing_integration_proposal", TMP / "wf78-position-sizing-integration-proposal.json", True, 24),
        "wf78_tier_a_owner_readiness_proposals": artifact_probe("wf78_tier_a_owner_readiness_proposals", TMP / "wf78-tier-a-owner-readiness-proposals.json", True, 24),
        "wf78_missing_band_context_repair": artifact_probe("wf78_missing_band_context_repair", TMP / "wf78-missing-band-context-repair.json", True, 24),
        "wf78_source_capture_requirements_queue": artifact_probe("wf78_source_capture_requirements_queue", TMP / "wf78-source-capture-requirements-queue.json", True, 24),
        "wf78_official_source_discovery": artifact_probe("wf78_official_source_discovery", TMP / "wf78-official-source-discovery.json", True, 24),
        "wf78_official_registry_proposal": artifact_probe("wf78_official_registry_proposal", TMP / "wf78-official-registry-proposal.json", True, 24),
        "wf78_promotion_owner_lineage_queue": artifact_probe("wf78_promotion_owner_lineage_queue", TMP / "wf78-promotion-owner-lineage-queue.json", True, 24),
        "wf78_owner_lineage_proposal": artifact_probe("wf78_owner_lineage_proposal", TMP / "wf78-owner-lineage-proposal.json", True, 24),
        "wf78_ph_owner_review_candidate_packet": artifact_probe("wf78_ph_owner_review_candidate_packet", TMP / "wf78-ph-owner-review-candidate-packet.json", True, 24),
        "wf78_tier_a_invalidation_review_queue": artifact_probe("wf78_tier_a_invalidation_review_queue", TMP / "wf78-tier-a-invalidation-review-queue.json", True, 24),
        "wf78_official_source_capture_packet": artifact_probe("wf78_official_source_capture_packet", TMP / "wf78-official-source-capture-packet.json", True, 24),
        "wf78_next_owner_review_and_source_capture_integration": artifact_probe("wf78_next_owner_review_and_source_capture_integration", TMP / "wf78-next-owner-review-and-source-capture-integration.json", True, 24),
        "wf78_ticker_freshness_ledger": artifact_probe("wf78_ticker_freshness_ledger", TMP / "wf78-ticker-freshness-ledger.json", True, 24),
        "wf78_tier_weighted_freshness_resolution": artifact_probe("wf78_tier_weighted_freshness_resolution", TMP / "wf78-tier-weighted-freshness-resolution.json", True, 24),
        "canonical_finance_data_plane_contract": artifact_probe("canonical_finance_data_plane_contract", TMP / "canonical-finance-data-plane-contract.json", True, 168),
        "canonical_finance_data_plane": artifact_probe("canonical_finance_data_plane", TMP / "canonical-finance-data-plane.json", True, 24),
        "canonical_finance_data_plane_validation": artifact_probe("canonical_finance_data_plane_validation", TMP / "canonical-finance-data-plane-validation.json", True, 24),
        "canonical_finance_data_plane_phase6_10": artifact_probe("canonical_finance_data_plane_phase6_10", TMP / "canonical-finance-data-plane-phase6-10.json", True, 24),
        "canonical_finance_data_plane_retirement_readiness": artifact_probe("canonical_finance_data_plane_retirement_readiness", TMP / "canonical-finance-data-plane-retirement-readiness.json", True, 168),
        "canonical_finance_data_plane_sqlite": {
            "key": "canonical_finance_data_plane_sqlite",
            "path": "tmp/canonical-finance-data-plane.sqlite",
            "required": True,
            "exists": (TMP / "canonical-finance-data-plane.sqlite").exists(),
            "parseable_json": False,
            "json_expected": False,
        },
        "trade_grade_decision_os_contract": artifact_probe("trade_grade_decision_os_contract", TMP / "trade-grade-decision-os-contract.json", True, 168),
        "trade_grade_source_freshness_gate": artifact_probe("trade_grade_source_freshness_gate", TMP / "trade-grade-source-freshness-gate.json", True, 24),
        "trade_grade_decision_cards": artifact_probe("trade_grade_decision_cards", TMP / "trade-grade-decision-cards.json", True, 24),
        "trade_grade_decision_card_authority_validation": artifact_probe("trade_grade_decision_card_authority_validation", TMP / "trade-grade-decision-card-authority-validation.json", True, 24),
        "trade_grade_approval_card_gate": artifact_probe("trade_grade_approval_card_gate", TMP / "trade-grade-approval-card-gate.json", True, 24),
        "trade_grade_risk_sizing_overlay": artifact_probe("trade_grade_risk_sizing_overlay", TMP / "trade-grade-risk-sizing-overlay.json", True, 24),
        "trade_grade_repair_conveyor": artifact_probe("trade_grade_repair_conveyor", TMP / "trade-grade-repair-conveyor.json", True, 24),
        "wf78_daily_freshness_loop": artifact_probe("wf78_daily_freshness_loop", TMP / "wf78-daily-freshness-loop.json", True, 24),
        "repeatable_work_closeout": artifact_probe("repeatable_work_closeout", TMP / "repeatable-work-closeout.json", True, 24),
        "artifact_intelligence_action_scorer": artifact_probe("artifact_intelligence_action_scorer", TMP / "artifact-intelligence-action-scorer.json", True, 24),
        "wf78_capital_review_queue_sqlite": {
            "key": "wf78_capital_review_queue_sqlite",
            "path": "tmp/wf78-capital-review-queue.sqlite",
            "required": True,
            "exists": (TMP / "wf78-capital-review-queue.sqlite").exists(),
            "parseable_json": False,
            "json_expected": False,
        },
        "wf78_event_triggered_rerouting_sqlite": {
            "key": "wf78_event_triggered_rerouting_sqlite",
            "path": "tmp/wf78-event-triggered-rerouting.sqlite",
            "required": True,
            "exists": (TMP / "wf78-event-triggered-rerouting.sqlite").exists(),
            "parseable_json": False,
            "json_expected": False,
        },
        "wf78_routing_dashboard": artifact_probe("wf78_routing_dashboard", TMP / "wf78-routing-dashboard.json", True, 24),
        "wf78_routing_dashboard_sqlite": {
            "key": "wf78_routing_dashboard_sqlite",
            "path": "tmp/wf78-routing-dashboard.sqlite",
            "required": True,
            "exists": (TMP / "wf78-routing-dashboard.sqlite").exists(),
            "parseable_json": False,
            "json_expected": False,
        },
        "concurrent_lane_register": artifact_probe("concurrent_lane_register", TMP / "concurrent-lane-register.json", True, 168),
        "parallel_lane_recommendation": artifact_probe("parallel_lane_recommendation", TMP / "parallel-lane-recommendation.json", True, 168),
        "truth_surface_inventory": artifact_probe("truth_surface_inventory", TMP / "truth-surface-inventory.json", True, 168),
        "route_efficiency_scorecard": artifact_probe("route_efficiency_scorecard", TMP / "route-efficiency-scorecard.json", True, 168),
        "fast_path_qa": artifact_probe("fast_path_qa", TMP / "fast-path-qa.json", True, 168),
        "workflow_routing_index": artifact_probe("workflow_routing_index", TMP / "workflow-routing-index.json", True, 168),
        "workflow_routing_index_validation": artifact_probe("workflow_routing_index_validation", TMP / "workflow-routing-index-validation.json", True, 168),
        "workflow_routing_index_sqlite": {
            "key": "workflow_routing_index_sqlite",
            "path": "tmp/workflow-routing-index.sqlite",
            "required": True,
            "exists": (TMP / "workflow-routing-index.sqlite").exists(),
            "parseable_json": False,
            "json_expected": False,
        },
        "finance_sql_go_boundary_lint": artifact_probe("finance_sql_go_boundary_lint", TMP / "finance-sql-boundary-lint.json", True, 168),
        "python_sql_contract_lint": artifact_probe("python_sql_contract_lint", TMP / "python-sql-contract-lint.json", True, 168),
        "sql_schema_drift_lint": artifact_probe("sql_schema_drift_lint", TMP / "sql-schema-drift-lint.json", True, 168),
        "sql_proof_probe": artifact_probe("sql_proof_probe", TMP / "sql-proof-probe.json", True, 168),
        "go_sql_latency_probe": artifact_probe("go_sql_latency_probe", TMP / "go-sql-latency-probe.json", True, 168),
        "go_sql_inventory_helper": artifact_probe("go_sql_inventory_helper", TMP / "go-sql-inventory-helper.json", True, 168),
        "python_go_sql_parity_check": artifact_probe("python_go_sql_parity_check", TMP / "python-go-sql-parity-check.json", True, 168),
        "python_go_sql_migration_candidates": artifact_probe("python_go_sql_migration_candidates", TMP / "python-go-sql-migration-candidates.json", True, 168),
        "go_sql_source_truth_manifest": artifact_probe("go_sql_source_truth_manifest", TMP / "go-sql-source-truth-authority-manifest.json", True, 168),
        "python_go_source_truth_manifest_parity": artifact_probe("python_go_source_truth_manifest_parity", TMP / "python-go-source-truth-manifest-parity.json", True, 168),
        "go_source_truth_parity_validator": artifact_probe("go_source_truth_parity_validator", TMP / "go-source-truth-parity-validation.json", True, 168),
        "python_go_source_truth_parity_validator_parity": artifact_probe("python_go_source_truth_parity_validator_parity", TMP / "python-go-source-truth-parity-validator-parity.json", True, 168),
        "go_sql_500_expansion_gate": artifact_probe("go_sql_500_expansion_gate", TMP / "go-sql-500-ticker-expansion-design-gate.json", True, 168),
        "python_go_sql_500_expansion_gate_parity": artifact_probe("python_go_sql_500_expansion_gate_parity", TMP / "python-go-sql-500-expansion-gate-parity.json", True, 168),
        "wf78_500_reputation_gate": artifact_probe("wf78_500_reputation_gate", TMP / "wf78-500-ticker-reputation-gate.json", True, 168),
        "go_finance_data_coverage_probe": artifact_probe("go_finance_data_coverage_probe", TMP / "go-finance-data-coverage-probe.json", True, 168),
        "python_go_finance_data_coverage_probe_parity": artifact_probe("python_go_finance_data_coverage_probe_parity", TMP / "python-go-finance-data-coverage-probe-parity.json", True, 168),
        "go_finance_human_notes_sql_check": artifact_probe("go_finance_human_notes_sql_check", TMP / "go-finance-human-notes-sql-check.json", True, 168),
        "python_go_finance_human_notes_sql_check_parity": artifact_probe("python_go_finance_human_notes_sql_check_parity", TMP / "python-go-finance-human-notes-sql-check-parity.json", True, 168),
        "go_finance_universe_validation_probe": artifact_probe("go_finance_universe_validation_probe", TMP / "go-finance-universe-validation-probe.json", True, 168),
        "python_go_finance_universe_validation_parity": artifact_probe("python_go_finance_universe_validation_parity", TMP / "python-go-finance-universe-validation-parity.json", True, 168),
        "go_wf78_sql_phase2_readiness_probe": artifact_probe("go_wf78_sql_phase2_readiness_probe", TMP / "go-wf78-sql-phase2-readiness-probe.json", True, 168),
        "python_go_wf78_sql_phase2_readiness_parity": artifact_probe("python_go_wf78_sql_phase2_readiness_parity", TMP / "python-go-wf78-sql-phase2-readiness-parity.json", True, 168),
        "python_go_durable_output_parity_repeated_gate": artifact_probe("python_go_durable_output_parity_repeated_gate", TMP / "python-go-durable-output-parity-repeated-gate.json", True, 168),
        "go_sql_consumer_authority_guard": artifact_probe("go_sql_consumer_authority_guard", TMP / "go-sql-consumer-authority-guard.json", True, 168),
        "python_go_sql_consumer_authority_guard_parity": artifact_probe("python_go_sql_consumer_authority_guard_parity", TMP / "python-go-sql-consumer-authority-guard-parity.json", True, 168),
        "python_go_sql_consumer_authority_guard_fixture_parity": artifact_probe("python_go_sql_consumer_authority_guard_fixture_parity", TMP / "python-go-sql-consumer-authority-guard-fixture-parity.json", True, 168),
        "python_go_sql_consumer_authority_dashboard_ab": artifact_probe("python_go_sql_consumer_authority_dashboard_ab", TMP / "python-go-sql-consumer-authority-dashboard-ab.json", True, 168),
        "python_go_sql_consumer_authority_demotion_dry_run": artifact_probe("python_go_sql_consumer_authority_demotion_dry_run", TMP / "python-go-sql-consumer-authority-demotion-dry-run.json", True, 168),
        "python_go_sql_consumer_authority_controlled_router": artifact_probe("python_go_sql_consumer_authority_controlled_router", TMP / "python-go-sql-consumer-authority-controlled-router.json", True, 168),
        "python_go_sql_helper_demotion_readiness_gate": artifact_probe("python_go_sql_helper_demotion_readiness_gate", TMP / "python-go-sql-helper-demotion-readiness-gate.json", True, 168),
        "python_go_sql_helper_demotion_queue": artifact_probe("python_go_sql_helper_demotion_queue", TMP / "python-go-sql-helper-demotion-queue.json", True, 168),
        "python_go_sql_helper_contract_gate": artifact_probe("python_go_sql_helper_contract_gate", TMP / "python-go-sql-helper-contract-gate.json", True, 168),
        "python_go_sql_helper_controlled_router_batch": artifact_probe("python_go_sql_helper_controlled_router_batch", TMP / "python-go-sql-helper-controlled-router-batch.json", True, 168),
        "python_go_sql_helper_go_primary_history_gate": artifact_probe("python_go_sql_helper_go_primary_history_gate", TMP / "python-go-sql-helper-go-primary-history-gate.json", True, 168),
        "python_go_sql_helper_default_route_promotion": artifact_probe("python_go_sql_helper_default_route_promotion", TMP / "python-go-sql-helper-default-route-promotion.json", True, 168),
        "python_go_sql_helper_default_route_history_gate": artifact_probe("python_go_sql_helper_default_route_history_gate", TMP / "python-go-sql-helper-default-route-history-gate.json", True, 168),
        "python_go_sql_helper_fallback_removal_readiness_gate": artifact_probe("python_go_sql_helper_fallback_removal_readiness_gate", TMP / "python-go-sql-helper-fallback-removal-readiness-gate.json", True, 168),
        "python_go_sql_helper_retirement_gate": artifact_probe("python_go_sql_helper_retirement_gate", TMP / "python-go-sql-helper-retirement-gate.json", True, 168),
        "runtime_performance_scorecard": artifact_probe("runtime_performance_scorecard", TMP / "runtime-performance-scorecard.json", True, 168),
        "wf74_model_quality_collection": artifact_probe("wf74_model_quality_collection", TMP / "wf74-model-quality-collection-cron-runner.json", True, 30),
        "model_quality_scorecard": artifact_probe("model_quality_scorecard", TMP / "model-quality-scorecard.json", True, 30),
        "model_learning_metadata_ledger": artifact_probe("model_learning_metadata_ledger", TMP / "model-learning-metadata-ledger.json", True, 30),
        "otel_runtime_metadata_probe": artifact_probe("otel_runtime_metadata_probe", TMP / "otel-runtime-metadata-probe.json", True, 30),
        "coding_runtime_kpi_probe": artifact_probe("coding_runtime_kpi_probe", TMP / "coding-runtime-kpi-probe.json", True, 30),
        "validator_timing_ledger": artifact_probe("validator_timing_ledger", TMP / "validator-timing-ledger.json", True, 30),
        "changed_file_validator_router": artifact_probe("changed_file_validator_router", TMP / "changed-file-validator-router.json", True, 30),
        "wf77_price_bridge": artifact_probe("wf77_price_bridge", TMP / "wf77-price-freshness-bridge.json", False, 48),
        "macro_event_calendar": artifact_probe("macro_event_calendar", TMP / "macro-event-calendar.json", False, 168),
        "renderer_regression": artifact_probe("renderer_regression", TMP / "wf75-renderer-export-regression.json", True, 168),
        "scenario_library": artifact_probe("scenario_library", TMP / "wf75-scenario-template-library.json", True, 168),
        "generic_service_run_contract": artifact_probe("generic_service_run_contract", TMP / "generic-service-run-contract.json", True, 168),
        "smb_workflow_scenario_library": artifact_probe("smb_workflow_scenario_library", TMP / "wf75-smb-workflow-scenario-library.json", True, 168),
        "smb_pivot_pm_decision_packet": artifact_probe("smb_pivot_pm_decision_packet", TMP / "wf75-smb-pivot-pm-decision-packet.json", True, 168),
        "smb_customer_preview": artifact_probe("smb_customer_preview", TMP / "wf75-smb-customer-preview.json", True, 168),
        "smb_customer_preview_validation": artifact_probe("smb_customer_preview_validation", TMP / "wf75-smb-customer-preview-validation.json", True, 168),
        "smb_pilot_decision_packet": artifact_probe("smb_pilot_decision_packet", TMP / "wf75-smb-pilot-decision-packet.json", True, 168),
        "smb_lead_rescue_service_packet": artifact_probe("smb_lead_rescue_service_packet", TMP / "wf75-smb-lead-rescue-service-packet.json", True, 168),
        "smb_lead_rescue_service_packet_validation": artifact_probe("smb_lead_rescue_service_packet_validation", TMP / "wf75-smb-lead-rescue-service-packet-validation.json", True, 168),
        "smb_automation_blueprints": artifact_probe("smb_automation_blueprints", TMP / "wf75-smb-automation-blueprints.json", True, 168),
        "smb_automation_blueprints_validation": artifact_probe("smb_automation_blueprints_validation", TMP / "wf75-smb-automation-blueprints-validation.json", True, 168),
        "smb_service_state": artifact_probe("smb_service_state", TMP / "wf75-smb-service-state-current.json", True, 168),
        "smb_service_state_validation": artifact_probe("smb_service_state_validation", TMP / "wf75-smb-service-state-validation.json", True, 168),
        "smb_offer_icp_packet": artifact_probe("smb_offer_icp_packet", TMP / "wf79-smb-offer-icp-packet.json", True, 168),
        "smb_demo_packets": artifact_probe("smb_demo_packets", TMP / "wf79-smb-demo-packets.json", True, 168),
        "smb_demo_packets_validation": artifact_probe("smb_demo_packets_validation", TMP / "wf79-smb-demo-packets-validation.json", True, 168),
        "smb_marketing_ops_blueprints": artifact_probe("smb_marketing_ops_blueprints", TMP / "wf79-smb-marketing-ops-blueprints.json", True, 168),
        "smb_marketing_ops_blueprints_validation": artifact_probe("smb_marketing_ops_blueprints_validation", TMP / "wf79-smb-marketing-ops-blueprints-validation.json", True, 168),
        "smb_cockpit_panel": artifact_probe("smb_cockpit_panel", TMP / "wf79-smb-cockpit-panel.json", True, 168),
        "smb_sales_practice_packet": artifact_probe("smb_sales_practice_packet", TMP / "wf79-smb-sales-practice-packet.json", True, 168),
        "smb_phase_closeout": artifact_probe("smb_phase_closeout", TMP / "wf79-smb-phase-closeout.json", True, 168),
        "smb_go_boundary_lint": artifact_probe("smb_go_boundary_lint", TMP / "wf75-smb-boundary-lint.json", True, 168),
        "generic_service_state_sqlite": {
            "key": "generic_service_state_sqlite",
            "path": "tmp/generic-service-state.sqlite",
            "required": True,
            "exists": (TMP / "generic-service-state.sqlite").exists(),
            "parseable_json": False,
            "json_expected": False,
        },
        "heartbeat_candidates": artifact_probe("heartbeat_candidates", TMP / "heartbeat-continuation-candidates.json", False, 48),
        "pm_implementation_job_queue": artifact_probe("pm_implementation_job_queue", TMP / "pm-implementation-job-queue.json", False, 24),
        "pm_previous_state": artifact_probe("pm_previous_state", PROGRAM_STATE_JSON, False, None),
    }


def build_lanes(sources: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        build_lane(
            "retail_truth_routing",
            "Retail Truth Routing System",
            "Resumed internal answer-safety routing proof with source-open/review-only/blocked path classification, seeded-bad regression, customer-output decision packet, and customer launch gates preserved.",
            [
                sources["retail_truth_routing_contract"],
                sources["retail_answer_harness"],
                sources["retail_automation_control_plane"],
                sources["retail_customer_output_decision"],
                sources["automation_stack_hardening_pass"],
                sources["go_sql_consumer_authority_guard"],
                sources["python_go_sql_consumer_authority_guard_parity"],
                sources["finance_data_coverage"],
                sources["authority_matrix"],
                sources["veritas_harness_scorecard"],
            ],
            "Use internally for answer path classification only; keep contract, harness, control plane, and customer-output decision packet green while customer-facing output remains gated.",
            "Refresh the retail truth routing contract, retail answer harness, customer-output decision packet, automation control plane, automation hardening pass, A2 guard/parity proof, finance coverage, authority matrix, and harness scorecard.",
            ["artifact-owned truth", "source-open material claims", "SQL read support only", "PM coordinates but does not own final truth", "internal answer-safety only", "no customer output", "no real customer data", "no external delivery", "no canon/portfolio mutation", "no paper/live/account action", "no owner approval inference"],
        ),
        build_lane(
            "smb_saas_parallel_morning_plan",
            "SMB + SaaS Parallel Morning Sprint",
            "Morning pickup contract for running WF79-SMB sanitized implementation and WF75 internal SaaS deliverable-gate work in parallel while customer/public delivery remains blocked.",
            [sources["smb_saas_parallel_morning_plan"], sources["active_workflows"]],
            "Use the audit plan as first-read, then lease disjoint WF79-SMB and WF75 surfaces for packet/blueprint and deliverable-gate implementation. Keep finance-delivery cron paused.",
            "Refresh the audit plan and PM packet before starting the parallel morning sprint.",
            ["no real customer data", "no customer outreach", "no external delivery", "no public SaaS launch", "no cron restart", "no ROI/legal/compliance/security readiness claim", "no account/trading/capital authority"],
            enforce_authority_scan=False,
        ),
        build_lane(
            "smb_workflow_clarity",
            "SMB Workflow Clarity / Marketing Ops Automation",
            "Automation-first monetization lane for Lead Rescue, workflow clarity, SMB owner-operator service packets, and marketing operations follow-up systems.",
            [
                sources["generic_service_run_contract"],
                sources["smb_workflow_scenario_library"],
                sources["smb_pivot_pm_decision_packet"],
                sources["smb_customer_preview"],
                sources["smb_customer_preview_validation"],
                sources["smb_pilot_decision_packet"],
                sources["smb_lead_rescue_service_packet"],
                sources["smb_lead_rescue_service_packet_validation"],
                sources["smb_automation_blueprints"],
                sources["smb_automation_blueprints_validation"],
                sources["smb_service_state"],
                sources["smb_service_state_validation"],
                sources["smb_offer_icp_packet"],
                sources["smb_demo_packets"],
                sources["smb_demo_packets_validation"],
                sources["smb_marketing_ops_blueprints"],
                sources["smb_marketing_ops_blueprints_validation"],
                sources["smb_cockpit_panel"],
                sources["smb_sales_practice_packet"],
                sources["smb_phase_closeout"],
                sources["smb_go_boundary_lint"],
                sources["generic_service_state_sqlite"],
            ],
            "Use the completed internal phase packets to review offer/ICP, demo packets, marketing-ops blueprints, cockpit panel, sales-practice assets, and approval-gated outreach readiness.",
            "Refresh the generic service-run contract and WF79-SMB phase-closeout proof, then decide whether to prepare approval-gated outreach material. Do not contact real prospects yet.",
            ["no real customer data", "no external delivery", "no customer outreach", "no credential access", "no customer-system or ad-account implementation", "no guaranteed ROI claim"],
        ),
        build_lane(
            "wf75_service_state",
            "WF75 Service State",
            "Anonymous scenario service-run state and current lifecycle proof.",
            [sources["wf75_service_state"], sources["wf75_readiness_plan"], sources["scenario_library"]],
            "Run the next anonymous service lifecycle slice from the scenario library when main session chooses the slice.",
            "Refresh WF75 service state and readiness plan, then rerun validation.",
            ["no customer data", "no external delivery", "no public launch"],
        ),
        build_lane(
            "operator_console",
            "Operator Console",
            "Local operator console/control cockpit proof over service state, queue, and handoff surfaces.",
            [sources["wf75_operator_console"], sources["wf75_pm_handoff"]],
            "Use the operator console as the current internal control view.",
            "Regenerate the operator console from current service state and handoff artifacts.",
            ["local-only control", "no customer portal", "no execution authority"],
        ),
        build_lane(
            "parallel_lane_orchestration",
            "Parallel Helper Lane Orchestration",
            "Review-only recommendation packet for the next safest distinct-output helper lane, with lease command and spawn args for a different session.",
            [sources["parallel_lane_recommendation"], sources["concurrent_lane_register"], sources["workflow_routing_index"], sources["pm_implementation_job_queue"]],
            "Use the parallel lane recommendation before spawning a helper in a different session; lease the lane first and main-session Veritas verifies output before completion.",
            "Refresh the parallel lane recommendation, lease only the emitted distinct-output lane, then spawn a bounded helper if main session wants parallel work.",
            ["recommendation only", "no autonomous spawning", "no cron mutation", "no merge authority", "no canon/portfolio mutation", "no capital deployment or execution authority"],
        ),
        build_lane(
            "wf74_learning_runtime",
            "WF74 Learning Runtime KPIs",
            "Model/tool/coding runtime metadata, privacy gates, validator timing, and PM-visible KPI loop for improving implementation reliability.",
            [
                sources["wf74_model_quality_collection"],
                sources["model_quality_scorecard"],
                sources["model_learning_metadata_ledger"],
                sources["otel_runtime_metadata_probe"],
                sources["coding_runtime_kpi_probe"],
                sources["validator_timing_ledger"],
                sources["changed_file_validator_router"],
            ],
            "Use the WF74 runner and PM KPI section to monitor first-pass clean rate, rework, validator elapsed time, OTEL metadata coverage, and privacy gate state.",
            "Run wf74_model_quality_collection_cron_runner.py with harness, then refresh pm_control_packet.py so PM sees the latest coding/runtime KPIs.",
            [
                "metadata-only learning",
                "no raw prompt/response/tool payload capture",
                "no raw diff or file-content capture",
                "no model-ranking claim",
                "no finance correctness from runtime metrics",
                "no config/runtime mutation without explicit approval",
            ],
        ),
        build_lane(
            "sql_index",
            "WF72 SQL / JSON Support Index",
            "Demoted WF72 support lane for derived JSON-to-SQL lookup, cache guards, artifact index, and fast-path QA below the WF84/WF85 finance answer route.",
            [sources["json_sql_promotion_index"], sources["json_sql_promotion_registry"], sources["json_sql_promotion_sqlite"], sources["python_sql_contract_lint"], sources["sql_schema_drift_lint"], sources["sql_proof_probe"], sources["go_sql_latency_probe"], sources["go_sql_inventory_helper"], sources["python_go_sql_parity_check"], sources["python_go_sql_migration_candidates"], sources["go_sql_source_truth_manifest"], sources["python_go_source_truth_manifest_parity"], sources["go_source_truth_parity_validator"], sources["python_go_source_truth_parity_validator_parity"], sources["go_sql_500_expansion_gate"], sources["python_go_sql_500_expansion_gate_parity"], sources["wf78_500_reputation_gate"], sources["go_finance_human_notes_sql_check"], sources["python_go_finance_human_notes_sql_check_parity"], sources["go_finance_universe_validation_probe"], sources["python_go_finance_universe_validation_parity"], sources["go_wf78_sql_phase2_readiness_probe"], sources["python_go_wf78_sql_phase2_readiness_parity"], sources["python_go_durable_output_parity_repeated_gate"], sources["go_sql_consumer_authority_guard"], sources["python_go_sql_consumer_authority_guard_parity"], sources["python_go_sql_consumer_authority_guard_fixture_parity"], sources["python_go_sql_consumer_authority_dashboard_ab"], sources["python_go_sql_consumer_authority_demotion_dry_run"], sources["python_go_sql_consumer_authority_controlled_router"], sources["python_go_sql_helper_demotion_readiness_gate"], sources["python_go_sql_helper_demotion_queue"], sources["python_go_sql_helper_contract_gate"], sources["python_go_sql_helper_controlled_router_batch"], sources["python_go_sql_helper_go_primary_history_gate"], sources["python_go_sql_helper_default_route_promotion"], sources["python_go_sql_helper_default_route_history_gate"], sources["python_go_sql_helper_fallback_removal_readiness_gate"], sources["python_go_sql_helper_retirement_gate"]],
            "Keep WF72 as support-only derived lookup; finance questions use WF84/WF85 as the answer path.",
            "Refresh JSON-to-SQL promotion index, Python/SQL contract lint, schema drift lint, and SQL proof probe.",
            ["JSON remains source", "no SQL import authority", "no canon/portfolio authority", "no finance answer front-door ownership"],
        ),
        build_lane(
            "wf78_scaleout",
            "WF78 Tier A/B Evidence Repair & Auto-Routing",
            "Non-capital Tier A/B evidence repair and auto-routing over the 200-row active universe; 201-500 import remains gated/report-only.",
            [sources["wf78_auto_tier_router"], sources["wf78_evidence_drag_reduction"], sources["wf78_evidence_family_repair"], sources["wf78_source_open_repair_execution"], sources["wf78_source_open_work_packets"], sources["wf78_position_sizing_surface_review"], sources["wf78_deployment_readiness_review"], sources["wf78_source_artifact_capture_review"], sources["wf78_position_sizing_integration_proposal"], sources["wf78_tier_a_owner_readiness_proposals"], sources["wf78_missing_band_context_repair"], sources["wf78_source_capture_requirements_queue"], sources["wf78_official_source_discovery"], sources["wf78_official_registry_proposal"], sources["wf78_promotion_owner_lineage_queue"], sources["wf78_owner_lineage_proposal"], sources["wf78_ph_owner_review_candidate_packet"], sources["wf78_tier_a_invalidation_review_queue"], sources["wf78_official_source_capture_packet"], sources["wf78_next_owner_review_and_source_capture_integration"], sources["wf78_ticker_freshness_ledger"], sources["wf78_tier_weighted_freshness_resolution"], sources["wf78_daily_freshness_loop"], sources["parallel_repeatable_work_orchestration"], sources["wf78_owner_card_prep_loop"], sources["wf78_tier_a_evidence_repair_batch"], sources["macro_event_guard_loop"], sources["wf78_500_reputation_gate"], sources["tier_promotion_review_gate"], sources["tier_b_research_packets"], sources["tier_b_research_packet_phase2_eval"], sources["tier_c_owner_decision_packet"], sources["wf78_routing_dashboard"], sources["wf78_routing_dashboard_sqlite"], sources["go_sql_500_expansion_gate"], sources["python_go_sql_500_expansion_gate_parity"], sources["go_wf78_sql_phase2_readiness_probe"], sources["python_go_wf78_sql_phase2_readiness_parity"]],
            "Use the WF78 auto-router as the live non-capital tier state; use the daily freshness loop, source-open repair execution, work packets, concrete repair reviews, integration proposals, and owner-readiness packets to keep evidence debt routed before owner-card prep.",
            "Run wf78_daily_freshness_loop, then control_closeout_bundle; use tier-weighted freshness resolution for the 200-row answer, owner-lineage proposal for the 10 Tier B rows, and missing-band repair for KTOS/SMCI before PH/invalidation/source-capture review.",
            ["derived non-capital routing only", "no ticker import without owner approval", "no production promotion", "no SQL-first authority", "no capital deployment or execution authority"],
        ),
        build_lane(
            "finance_os_data_model",
            "WF84 Canonical Finance Data Plane",
            "Internal trade-grade personal finance OS data model lane. Starts with a review-only schema/feeder/validator contract before any JSON packet writer, SQLite companion, or consumer migration.",
            [
                sources["canonical_finance_data_plane_contract"],
                sources["canonical_finance_data_plane"],
                sources["canonical_finance_data_plane_validation"],
                sources["canonical_finance_data_plane_phase6_10"],
                sources["canonical_finance_data_plane_retirement_readiness"],
                sources["canonical_finance_data_plane_sqlite"],
                sources["wf78_auto_tier_router"],
                sources["wf78_tier_weighted_freshness_resolution"],
                sources["ticker_card_refresh_gate"],
            ],
            "Use the validated WF84 phase 6-10 proof for internal read-only consumer expansion, parity, source drillback, priority queue, and retirement gating.",
            "Run canonical_finance_data_plane with DB lifecycle validation, workflow route validation, PM control, artifact index, and major closeout before any consumer default route switch.",
            [
                "internal personal finance infrastructure only",
                "no customer/account/PII/suitability/brokerage data",
                "no canon/portfolio/cash/risk-rule mutation",
                "no capital deployment or execution authority",
                "no SQL row or generated artifact becomes approval",
            ],
        ),
        build_lane(
            "trade_grade_decision_os",
            "WF85 Personal Trade-Grade Decision OS",
            "Review-only trade-grade decision and approval-card layer above WF84. Phase 1 must fail closed through SQLite/JSON parity, source/freshness, state-precedence, and card-authority gates before drafts.",
            [
                sources["trade_grade_decision_os_contract"],
                sources["trade_grade_source_freshness_gate"],
                sources["trade_grade_decision_cards"],
                sources["trade_grade_decision_card_authority_validation"],
                sources["trade_grade_approval_card_gate"],
                sources["trade_grade_risk_sizing_overlay"],
                sources["trade_grade_repair_conveyor"],
                sources["canonical_finance_data_plane"],
                sources["canonical_finance_data_plane_phase6_10"],
                sources["canonical_finance_data_plane_sqlite"],
                sources["wf78_capital_review_queue"],
            ],
            "Use the Phase 1 decision-card family and repair conveyor as the WF85 proof surface: source/freshness gate, fail-closed cards, authority scan, approval-card gate, risk/sizing overlay, and upstream repair routing.",
            "Run the WF85 repair conveyor after WF84/WF78 refreshes; treat normal monitor-only, below-stop/invalidation, and band/stop repair rows as finance-domain debt only. Open implementation work only if the conveyor validation/status or WF84/WF85 quality gates regress.",
            [
                "internal personal decision support only",
                "no customer/account/PII/suitability data",
                "no canon/portfolio/cash/risk-rule mutation",
                "no capital deployment or execution authority",
                "no card/score/SQL row becomes approval",
            ],
        ),
        build_lane(
            "tier_promotion_review",
            "Tier Promotion Review Gate",
            "Separates Tier C/D breadth from Tier B/A research and capital-deployment readiness.",
            [sources["wf78_auto_tier_router"], sources["tier_promotion_review_gate"], sources["tier_b_research_packets"], sources["tier_b_research_packet_requests"], sources["tier_b_research_packet_phase2_eval"], sources["tier_c_owner_decision_packet"], sources["wf78_routing_dashboard"], sources["wf78_routing_dashboard_sqlite"], sources["ticker_card_refresh_gate"], sources["wf78_500_reputation_gate"]],
            "Use the WF78 auto-router for current Tier A/B/C routing state; use Tier B research packets and legacy dashboard proof to explain evidence gaps.",
            "Run wf78_auto_tier_router after the all-safe phase runner, then refresh Tier B evidence packets and dashboard proof if stale.",
            ["derived non-capital routing only", "no import/apply without exact approval", "no production answer-path change", "no capital deployment", "no canon/portfolio mutation", "no paper/live/account action"],
        ),
        build_lane(
            "ticker_card_refresh",
            "Ticker Card Refresh Gate",
            "Review-only upstream evidence refresh, ticker-card rebuild, and stale-card repair queue before promotion-quality finance use.",
            [sources["ticker_card_freshness_owner_runner"], sources["finance_data_coverage"], sources["wf77_price_bridge"]],
            "Use the owner runner to rebuild cards, classify production repair debt, and keep true blockers fail-closed.",
            "Run ticker_card_freshness_owner_runner, then repair only true production blockers before any Tier B/Tier A promotion packet.",
            ["review-only", "no import/apply", "no production promotion", "no canon/portfolio mutation", "no paper/live/account action"],
        ),
        build_lane(
            "finance_engine",
            "Finance Engine",
            "Finance current-window and coverage proof feeding PM awareness.",
            [sources["current_window_artifacts"], sources["finance_data_coverage"], sources["ticker_card_freshness_owner_runner"], sources["go_finance_data_coverage_probe"], sources["python_go_finance_data_coverage_probe_parity"], sources["finance_sql_go_boundary_lint"], sources["python_sql_contract_lint"], sources["sql_schema_drift_lint"], sources["sql_proof_probe"], sources["go_sql_latency_probe"], sources["go_sql_inventory_helper"], sources["python_go_sql_parity_check"], sources["python_go_sql_migration_candidates"], sources["go_sql_source_truth_manifest"], sources["python_go_source_truth_manifest_parity"], sources["go_source_truth_parity_validator"], sources["python_go_source_truth_parity_validator_parity"], sources["go_sql_500_expansion_gate"], sources["python_go_sql_500_expansion_gate_parity"], sources["wf78_500_reputation_gate"], sources["go_finance_human_notes_sql_check"], sources["python_go_finance_human_notes_sql_check_parity"], sources["go_finance_universe_validation_probe"], sources["python_go_finance_universe_validation_parity"], sources["go_wf78_sql_phase2_readiness_probe"], sources["python_go_wf78_sql_phase2_readiness_parity"], sources["python_go_durable_output_parity_repeated_gate"], sources["go_sql_consumer_authority_guard"], sources["python_go_sql_consumer_authority_guard_parity"], sources["python_go_sql_consumer_authority_guard_fixture_parity"], sources["python_go_sql_consumer_authority_dashboard_ab"], sources["python_go_sql_consumer_authority_demotion_dry_run"], sources["python_go_sql_consumer_authority_controlled_router"], sources["python_go_sql_helper_demotion_readiness_gate"], sources["python_go_sql_helper_demotion_queue"], sources["python_go_sql_helper_contract_gate"], sources["python_go_sql_helper_controlled_router_batch"], sources["python_go_sql_helper_go_primary_history_gate"], sources["python_go_sql_helper_default_route_promotion"], sources["python_go_sql_helper_default_route_history_gate"], sources["python_go_sql_helper_fallback_removal_readiness_gate"], sources["python_go_sql_helper_retirement_gate"], sources["runtime_performance_scorecard"], sources["wf77_price_bridge"]],
            "Use current finance proof for PM awareness only.",
            "Refresh stale finance coverage/current-window proof and rerun the Go finance/SQL lint suite, SQL proof probe, and runtime scorecard.",
            ["review-only", "no capital action", "no paper/live/account action"],
            enforce_authority_scan=False,
        ),
        build_lane(
            "alerts_events",
            "Alerts / Events",
            "Macro/event and alert-adjacent proof that can affect workflow priority.",
            [sources["macro_event_calendar"], sources["wf77_price_bridge"]],
            "Monitor event/freshness surfaces for material PM blockers.",
            "Refresh macro/event and price-freshness proof if stale.",
            ["no external alert delivery", "no account action", "no probability claim"],
        ),
        build_lane(
            "pm_handoff_pdf",
            "PM Handoff / PDF",
            "Internal PM handoff, weekly update, and readiness brief packet.",
            [sources["wf75_pm_handoff"], sources["wf75_pm_weekly_update"], sources["wf75_pm_readiness_brief"], sources["wf75_pm_readiness_pdf"]],
            "Use PM packet as internal handoff; update only when source proof changes materially.",
            "Regenerate PM weekly update and readiness brief from current operator proof.",
            ["internal review only", "no launch claim", "no external delivery"],
        ),
        build_lane(
            "qa_source_trust",
            "QA / Source Trust",
            "Harness, renderer regression, and validation posture.",
            [sources["veritas_harness_scorecard"], sources["runtime_performance_scorecard"], sources["renderer_regression"]],
            "Treat warnings as readiness debt and failures as blockers.",
            "Run targeted validators and classify warning/failure state before further claims.",
            ["validator success is not owner approval", "no authority widening"],
        ),
        build_lane(
            "authority",
            "Authority Stop Lines",
            "Cross-surface authority gate audit for PM automation.",
            [sources["authority_matrix"], sources["wf75_operator_console"], sources["wf75_pm_handoff"], sources["json_sql_promotion_index"]],
            "Keep all closed gates closed; PM may coordinate only.",
            "Inspect and repair any authority flag that is not explicitly false.",
            ["no approval inference", "no customer data", "no portfolio/canon mutation", "no trading/account action"],
        ),
    ]


def choose_next_actions(lanes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    # Hard safety/freshness issues outrank advancement. Randall's 2026-06-17
    # night instruction created a temporary morning pickup lane for SMB plus
    # internal SaaS deliverable-gate implementation. Finance P0 remains
    # governance-primary, but this explicit sprint should surface first while
    # it is ready and review-only.
    status_priority = {
        "blocked": 0,
        "stale": 1,
        "ready": 2,
        "needs_validation": 3,
        "watch": 4,
        "complete_for_now": 5,
        "gated": 6,
        "on_hold": 7,
    }
    lane_priority = {
        "smb_saas_parallel_morning_plan": 0,
        "trade_grade_decision_os": 1,
        "finance_os_data_model": 2,
        "wf78_scaleout": 3,
        "ticker_card_refresh": 4,
        "tier_promotion_review": 5,
        "finance_engine": 6,
        "qa_source_trust": 7,
        "parallel_lane_orchestration": 8,
        "operator_console": 9,
        "pm_handoff_pdf": 10,
        "retail_truth_routing": 11,
        "wf75_service_state": 12,
        "smb_workflow_clarity": 13,
        "alerts_events": 14,
        "sql_index": 15,
        "authority": 16,
    }
    actions = [lane["next_action"] | {"lane_status": lane["status"], "readiness_score": lane["readiness_score"]} for lane in lanes]
    actions.sort(
        key=lambda item: (
            status_priority.get(item["lane_status"], 9),
            lane_priority.get(item["lane_id"], 99),
            item["readiness_score"],
        )
    )
    for index, action in enumerate(actions, start=1):
        action["rank"] = index
        action["pm_packet_only"] = True
    return actions


def changed_since_last_run(current: dict[str, Any], previous: dict[str, Any]) -> dict[str, Any]:
    if not previous:
        return {
            "has_previous_run": False,
            "lane_status_changes": [],
            "new_blockers": [],
            "resolved_blockers": [],
            "next_action_changed": True,
            "notes": ["No prior PM program-state packet was available."],
        }
    old_lanes = {lane.get("lane_id"): lane for lane in as_list(previous.get("lanes"))}
    new_lanes = {lane.get("lane_id"): lane for lane in as_list(current.get("lanes"))}
    status_changes = []
    for lane_id, lane in new_lanes.items():
        old_status = as_dict(old_lanes.get(lane_id)).get("status")
        if old_status != lane.get("status"):
            status_changes.append({"lane_id": lane_id, "from": old_status, "to": lane.get("status")})
    def blocker_ids(payload: dict[str, Any]) -> set[str]:
        ids: set[str] = set()
        for item in as_list(payload.get("blockers")):
            ids.add("|".join(str(item.get(k, "")) for k in ("lane_id", "kind", "path", "field")))
        return ids
    old_blockers = blocker_ids(previous)
    new_blockers = blocker_ids(current)
    old_first = as_dict(as_list(previous.get("next_actions"))[0] if as_list(previous.get("next_actions")) else {})
    new_first = as_dict(as_list(current.get("next_actions"))[0] if as_list(current.get("next_actions")) else {})
    return {
        "has_previous_run": True,
        "lane_status_changes": status_changes,
        "new_blockers": sorted(new_blockers - old_blockers),
        "resolved_blockers": sorted(old_blockers - new_blockers),
        "next_action_changed": old_first.get("action_id") != new_first.get("action_id"),
        "previous_generated_at_utc": previous.get("generated_at_utc"),
    }


def validate_payload(payload: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    if payload.get("authority_boundary") != GLOBAL_STOP_LINES:
        errors.append("global_stop_lines_changed")
    if not payload.get("lanes"):
        errors.append("no_lanes")
    if not payload.get("next_actions"):
        errors.append("no_next_actions")
    for lane in as_list(payload.get("lanes")):
        if lane.get("authority_violations"):
            errors.append(f"authority_violation_in_lane:{lane.get('lane_id')}")
    for action in as_list(payload.get("next_actions")):
        if action.get("heartbeat_may_execute") is not False:
            errors.append(f"heartbeat_execution_not_false:{action.get('action_id')}")
        if action.get("authority") != "review_only":
            errors.append(f"next_action_authority_not_review_only:{action.get('action_id')}")
    if any(lane.get("status") in {"blocked", "stale", "needs_validation"} for lane in as_list(payload.get("lanes"))):
        warnings.append("one_or_more_lanes_need_attention")
    return {"status": "ok" if not errors else "blocked", "errors": errors, "warnings": warnings}


def build_program_state() -> dict[str, Any]:
    previous = load_json(PROGRAM_STATE_JSON)
    active_text = read_text(ACTIVE_WORKFLOWS)
    sources = source_artifacts()
    lanes = build_lanes(sources)
    blockers = [blocker for lane in lanes for blocker in lane["blockers"]]
    next_actions = choose_next_actions(lanes)
    readiness_average = round(sum(lane["readiness_score"] for lane in lanes) / len(lanes), 1) if lanes else 0.0
    state: dict[str, Any] = {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "draft",
        "workflow": "WF75 PM program-state automation",
        "purpose": "Review-only PM control packet over live workflow proof.",
        "active_workflows_digest": {
            "path": rel(ACTIVE_WORKFLOWS),
            "exists": ACTIVE_WORKFLOWS.exists(),
            "mentions_wf75": "WF75" in active_text,
            "mentions_retail_saas": "Retail Investor Finance Intelligence SaaS" in active_text,
            "mentions_stop_lines": "Must not do" in active_text or "Stop lines" in active_text,
        },
        "source_artifacts": sources,
        "lanes": lanes,
        "blockers": blockers,
        "next_actions": next_actions,
        "stale_proof": [blocker for blocker in blockers if blocker.get("kind") == "stale_proof"],
        "readiness": {
            "average_score": readiness_average,
            "lane_count": len(lanes),
            "ready_or_complete_lanes": len([lane for lane in lanes if lane["status"] in {"ready", "complete_for_now"}]),
            "blocked_lanes": len([lane for lane in lanes if lane["status"] == "blocked"]),
            "gated_lanes": len([lane for lane in lanes if lane["status"] == "gated"]),
            "stale_lanes": len([lane for lane in lanes if lane["status"] == "stale"]),
            "needs_validation_lanes": len([lane for lane in lanes if lane["status"] == "needs_validation"]),
            "readiness_band": "green" if readiness_average >= 80 else "yellow" if readiness_average >= 55 else "red",
        },
        "expected_gates": [
            {**gate, "lane_id": lane["lane_id"]}
            for lane in lanes
            for gate in lane.get("expected_gates", [])
        ],
        "authority_boundary": GLOBAL_STOP_LINES,
        "automation_levels": {
            "level_1_pm_reports": True,
            "level_2_pm_queues_work": True,
            "level_2b_pm_builds_implementation_job_packets": True,
            "level_3_safe_refresh_triggers": "future_after_packet_stability",
            "level_4_bounded_helper_delegation": "main_session_only",
            "level_5_authority_gates_never_crossed": True,
        },
    }
    state["changed_since_last_run"] = changed_since_last_run(state, previous)
    state["validation"] = validate_payload(state)
    state["status"] = "ok" if state["validation"]["status"] == "ok" else "blocked"
    return state


def derived_packets(program: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    scoreboard = {
        "schema": LANE_SCOREBOARD_SCHEMA,
        "generated_at_utc": program["generated_at_utc"],
        "status": program["status"],
        "source": rel(PROGRAM_STATE_JSON),
        "readiness": program["readiness"],
        "lanes": [
            {
                "lane_id": lane["lane_id"],
                "title": lane["title"],
                "status": lane["status"],
                "readiness_score": lane["readiness_score"],
                "readiness_contribution": lane["readiness_contribution"],
                "blocker_count": len(lane["blockers"]),
                "next_action": lane["next_action"]["description"],
            }
            for lane in program["lanes"]
        ],
        "authority_boundary": program["authority_boundary"],
    }
    next_actions = {
        "schema": NEXT_ACTION_SCHEMA,
        "generated_at_utc": program["generated_at_utc"],
        "status": program["status"],
        "source": rel(PROGRAM_STATE_JSON),
        "next_actions": program["next_actions"],
        "authority_boundary": program["authority_boundary"],
    }
    blocker_register = {
        "schema": BLOCKER_SCHEMA,
        "generated_at_utc": program["generated_at_utc"],
        "status": "blocked_items_present" if program["blockers"] else "ok",
        "source": rel(PROGRAM_STATE_JSON),
        "blocker_count": len(program["blockers"]),
        "blockers": program["blockers"],
        "authority_boundary": program["authority_boundary"],
    }
    return scoreboard, next_actions, blocker_register


def rebuild_sqlite(program: dict[str, Any], db_path: Path) -> dict[str, Any]:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if db_path.exists():
        db_path.unlink()
    conn = sqlite3.connect(db_path)
    try:
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA journal_mode=DELETE")
        conn.executescript(
            """
            CREATE TABLE pm_runs (
              generated_at_utc TEXT PRIMARY KEY,
              status TEXT NOT NULL,
              readiness_band TEXT NOT NULL,
              average_score REAL NOT NULL,
              blocked_lanes INTEGER NOT NULL,
              stale_lanes INTEGER NOT NULL,
              needs_validation_lanes INTEGER NOT NULL
            );
            CREATE TABLE pm_lanes (
              lane_id TEXT PRIMARY KEY,
              title TEXT NOT NULL,
              status TEXT NOT NULL,
              readiness_score INTEGER NOT NULL,
              readiness_contribution TEXT NOT NULL,
              blocker_count INTEGER NOT NULL,
              next_action TEXT NOT NULL
            );
            CREATE TABLE pm_blockers (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              lane_id TEXT NOT NULL,
              severity TEXT NOT NULL,
              kind TEXT NOT NULL,
              path TEXT,
              detail TEXT
            );
            CREATE TABLE pm_next_actions (
              rank INTEGER PRIMARY KEY,
              action_id TEXT NOT NULL,
              lane_id TEXT NOT NULL,
              lane_status TEXT NOT NULL,
              action_type TEXT NOT NULL,
              description TEXT NOT NULL,
              authority TEXT NOT NULL,
              heartbeat_may_execute INTEGER NOT NULL,
              helper_lane_allowed_from_main_session INTEGER NOT NULL
            );
            CREATE TABLE pm_artifacts (
              key TEXT PRIMARY KEY,
              path TEXT NOT NULL,
              required INTEGER NOT NULL,
              exists_flag INTEGER NOT NULL,
              parseable_json INTEGER NOT NULL,
              status TEXT,
              validation_status TEXT,
              generated_at_utc TEXT,
              age_hours REAL
            );
            CREATE TABLE pm_authority_flags (
              key TEXT PRIMARY KEY,
              expected_value TEXT NOT NULL
            );
            """
        )
        readiness = program["readiness"]
        conn.execute(
            "INSERT INTO pm_runs VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                program["generated_at_utc"],
                program["status"],
                readiness["readiness_band"],
                readiness["average_score"],
                readiness["blocked_lanes"],
                readiness["stale_lanes"],
                readiness["needs_validation_lanes"],
            ),
        )
        for lane in program["lanes"]:
            conn.execute(
                "INSERT INTO pm_lanes VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    lane["lane_id"],
                    lane["title"],
                    lane["status"],
                    lane["readiness_score"],
                    lane["readiness_contribution"],
                    len(lane["blockers"]),
                    lane["next_action"]["description"],
                ),
            )
        for blocker in program["blockers"]:
            conn.execute(
                "INSERT INTO pm_blockers (lane_id, severity, kind, path, detail) VALUES (?, ?, ?, ?, ?)",
                (
                    blocker.get("lane_id", "unknown"),
                    blocker.get("severity", "warning"),
                    blocker.get("kind", "unknown"),
                    blocker.get("path"),
                    json.dumps(blocker, sort_keys=True),
                ),
            )
        for action in program["next_actions"]:
            conn.execute(
                "INSERT INTO pm_next_actions VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    action["rank"],
                    action["action_id"],
                    action["lane_id"],
                    action["lane_status"],
                    action["action_type"],
                    action["description"],
                    action["authority"],
                    1 if action["heartbeat_may_execute"] else 0,
                    1 if action["helper_lane_allowed_from_main_session"] else 0,
                ),
            )
        for item in program["source_artifacts"].values():
            conn.execute(
                "INSERT INTO pm_artifacts VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    item.get("key") or item.get("path"),
                    item.get("path"),
                    1 if item.get("required") else 0,
                    1 if item.get("exists") else 0,
                    1 if item.get("parseable_json") else 0,
                    item.get("status"),
                    item.get("validation_status"),
                    item.get("generated_at_utc"),
                    item.get("age_hours"),
                ),
            )
        for key, value in program["authority_boundary"].items():
            conn.execute("INSERT INTO pm_authority_flags VALUES (?, ?)", (key, json.dumps(value)))
        conn.commit()
        integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
        foreign_keys = conn.execute("PRAGMA foreign_key_check").fetchall()
        counts = {
            "pm_runs": conn.execute("SELECT COUNT(*) FROM pm_runs").fetchone()[0],
            "pm_lanes": conn.execute("SELECT COUNT(*) FROM pm_lanes").fetchone()[0],
            "pm_blockers": conn.execute("SELECT COUNT(*) FROM pm_blockers").fetchone()[0],
            "pm_next_actions": conn.execute("SELECT COUNT(*) FROM pm_next_actions").fetchone()[0],
            "pm_artifacts": conn.execute("SELECT COUNT(*) FROM pm_artifacts").fetchone()[0],
            "pm_authority_flags": conn.execute("SELECT COUNT(*) FROM pm_authority_flags").fetchone()[0],
        }
    finally:
        conn.close()
    return {
        "db_path": rel(db_path),
        "status": "ok" if integrity == "ok" and not foreign_keys else "blocked",
        "integrity_check": integrity,
        "foreign_key_errors": len(foreign_keys),
        "table_counts": counts,
        "authority_boundary": "Derived PM lookup only. JSON packets remain source proof; no canon, approval, customer, external, archive/delete, paper/live/account, or mutation authority.",
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build review-only PM program-state packets.")
    parser.add_argument("--write", action="store_true", help="Write PM JSON packets.")
    parser.add_argument("--write-db", action="store_true", help="Rebuild derived PM SQLite index.")
    parser.add_argument("--validate", action="store_true", help="Return nonzero if validation fails.")
    parser.add_argument("--db", default=str(DEFAULT_DB), help="SQLite output path for --write-db.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    program = build_program_state()
    scoreboard, next_actions, blocker_register = derived_packets(program)
    db_result: dict[str, Any] | None = None
    if args.write:
        atomic_write_json(PROGRAM_STATE_JSON, program)
        atomic_write_json(LANE_SCOREBOARD_JSON, scoreboard)
        atomic_write_json(NEXT_ACTIONS_JSON, next_actions)
        atomic_write_json(BLOCKER_REGISTER_JSON, blocker_register)
    if args.write_db:
        db_path = Path(args.db)
        if not db_path.is_absolute():
            db_path = ROOT / db_path
        db_result = rebuild_sqlite(program, db_path)
    result = {
        "status": program["status"],
        "generated_at_utc": program["generated_at_utc"],
        "outputs": {
            "program_state": rel(PROGRAM_STATE_JSON),
            "lane_scoreboard": rel(LANE_SCOREBOARD_JSON),
            "next_actions": rel(NEXT_ACTIONS_JSON),
            "blocker_register": rel(BLOCKER_REGISTER_JSON),
            "sqlite": db_result,
        },
        "readiness": program["readiness"],
        "validation": program["validation"],
    }
    print(json.dumps(result, indent=2))
    if args.validate and (program["validation"]["status"] != "ok" or (db_result and db_result["status"] != "ok")):
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
