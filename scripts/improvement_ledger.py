#!/usr/bin/env python3
"""Build the durable improvement ledger and current carry-forward packet.

The live WF74 opportunity queue is regenerated under tmp/. This script promotes
its recommendations into append-only state history so new sessions can load the
improvement backlog without relying on chat history or one runtime packet.
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
STATE_HISTORY = ROOT / "data" / "state-history"
DEFAULT_LEDGER = STATE_HISTORY / "improvement-ledger.jsonl"
DEFAULT_JSON = TMP / "improvement-ledger-current.json"
DEFAULT_MD = DEFAULT_JSON.with_suffix(".md")
SCHEMA = "veritas.improvement_ledger_current.v1"
EVENT_SCHEMA = "veritas.improvement_ledger_event.v1"

WF74_QUEUE = TMP / "wf74-improvement-opportunity-queue.json"
OTEL_LEARNING_LOOP = TMP / "otel-learning-loop.json"
WF74_RUNNER = TMP / "wf74-model-quality-collection-cron-runner.json"

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "append_only": True,
    "local_only": True,
    "recommendation_tracking_only": True,
    "code_mutation_allowed": False,
    "skill_application_allowed": False,
    "collector_config_mutation_allowed": False,
    "runtime_config_mutation_allowed": False,
    "cron_schedule_mutation_allowed": False,
    "finance_canon_or_portfolio_mutation_allowed": False,
    "capital_deployment_allowed": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "money_movement_allowed": False,
    "external_export_allowed": False,
    "raw_prompt_or_response_capture_allowed": False,
    "tool_payload_capture_allowed": False,
    "system_prompt_capture_allowed": False,
    "secret_or_header_capture_allowed": False,
    "owner_approval_inferred": False,
}

FORBIDDEN_TEXT = (
    "sk-",
    "Bearer ",
    "Authorization:",
    "BEGIN OPENSSH",
    "BEGIN RSA",
    "system_prompt",
    "access_token",
    "refresh_token",
    "oauth_token",
)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_utc(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        text = str(value).replace("Z", "+00:00")
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def stable_id(*parts: Any) -> str:
    seed = "|".join(str(part or "") for part in parts)
    return hashlib.sha256(seed.encode("utf-8")).hexdigest()[:16]


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            rows.append({"schema": "invalid", "raw_line_sha": stable_id(line), "status": "invalid_json"})
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows


def append_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.touch(exist_ok=True)
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n")


def scan_forbidden(value: Any, path: str = "$") -> list[str]:
    findings: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            lowered = str(key).lower()
            if any(marker in lowered for marker in ("prompt", "response", "tool_input", "tool_output", "system_prompt", "authorization", "secret", "token", "credential", "header")):
                if child is not False:
                    findings.append(f"forbidden_key:{path}.{key}")
                    continue
            findings.extend(scan_forbidden(child, f"{path}.{key}"))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            findings.extend(scan_forbidden(child, f"{path}[{index}]"))
    elif isinstance(value, str):
        if any(marker.lower() in value.lower() for marker in FORBIDDEN_TEXT):
            findings.append(f"forbidden_value:{path}")
    return findings


def source_status(path: Path) -> dict[str, Any]:
    payload = as_dict(load_json_artifact(path))
    return {
        "path": rel(path),
        "exists": path.exists(),
        "status": payload.get("status"),
        "validation_status": as_dict(payload.get("validation")).get("status"),
        "generated_at_utc": payload.get("generated_at_utc"),
    }


def event_base(source_type: str, source_path: Path, source_generated_at: str | None, source_key: str) -> dict[str, Any]:
    return {
        "schema": EVENT_SCHEMA,
        "event_id": stable_id(source_type, rel(source_path), source_generated_at, source_key),
        "recorded_at_utc": utc_now(),
        "source_type": source_type,
        "source_artifact": rel(source_path),
        "source_generated_at_utc": source_generated_at,
        "source_key": source_key,
        "status": "open",
        "carry_forward": True,
        "authority_boundary": AUTHORITY_BOUNDARY.copy(),
    }


def queue_events(queue: dict[str, Any]) -> list[dict[str, Any]]:
    generated_at = queue.get("generated_at_utc")
    rows: list[dict[str, Any]] = []
    for opportunity in as_list(queue.get("opportunities")):
        if not isinstance(opportunity, dict):
            continue
        source_key = str(opportunity.get("opportunity_id") or stable_id(opportunity.get("title"), opportunity.get("signal")))
        row = event_base("wf74_improvement_opportunity", WF74_QUEUE, generated_at, source_key)
        row.update({
            "category": opportunity.get("category"),
            "title": opportunity.get("title"),
            "priority": opportunity.get("priority"),
            "severity": "high" if int(opportunity.get("priority") or 0) >= 80 else "normal",
            "signal": opportunity.get("signal"),
            "decision": opportunity.get("proposal_gate"),
            "recommended_action": opportunity.get("recommended_action"),
            "next_action": opportunity.get("recommended_action"),
            "validation_command": opportunity.get("validation_command"),
            "proof_artifacts": [rel(WF74_QUEUE)],
            "evidence_keys": sorted(as_dict(opportunity.get("evidence")).keys()),
            "requires_before_apply": opportunity.get("requires_before_apply"),
            "allowed_autonomous_output": opportunity.get("allowed_autonomous_output"),
            "review_cadence": opportunity.get("review_cadence"),
        })
        rows.append(row)
    return rows


def otel_events(otel: dict[str, Any]) -> list[dict[str, Any]]:
    generated_at = otel.get("generated_at_utc")
    rows: list[dict[str, Any]] = []
    for rec in as_list(otel.get("recommendations")):
        if not isinstance(rec, dict):
            continue
        source_key = str(rec.get("id") or stable_id(rec.get("decision"), rec.get("rationale")))
        row = event_base("otel_learning_loop_recommendation", OTEL_LEARNING_LOOP, generated_at, source_key)
        row.update({
            "category": "otel_learning_loop",
            "title": rec.get("id"),
            "priority": 75 if rec.get("severity") == "warning" else 55,
            "severity": rec.get("severity") or "info",
            "decision": rec.get("decision"),
            "recommended_action": rec.get("next_action"),
            "next_action": rec.get("next_action"),
            "proof_artifacts": [rel(OTEL_LEARNING_LOOP)],
            "rationale": rec.get("rationale"),
            "blocked_capture": rec.get("blocked_capture"),
        })
        rows.append(row)
    return rows


def resolution_events(runner: dict[str, Any]) -> list[dict[str, Any]]:
    summary = as_dict(runner.get("summary"))
    if runner.get("status") != "ok" or int(summary.get("steps_blocked") or 0) != 0:
        return []
    generated_at = runner.get("generated_at_utc")
    row = event_base("wf74_improvement_opportunity", WF74_RUNNER, generated_at, "code_mutation-eaa17861f4c9")
    row.update({
        "category": "code_mutation",
        "title": "Repair blocked WF74 collection step",
        "priority": 96,
        "severity": "resolved",
        "signal": "wf74_collection_step_clean",
        "decision": "resolved_by_latest_runner",
        "recommended_action": "No carry-forward action while latest WF74 collection has zero blocked steps.",
        "next_action": "Monitor future WF74 collection runs; reopen only if a later runner reports blocked steps.",
        "validation_command": "python scripts\\wf74_model_quality_collection_cron_runner.py --write --write-md --validate",
        "proof_artifacts": [rel(WF74_RUNNER)],
        "status": "complete",
        "carry_forward": False,
        "resolution_reason": "latest_wf74_runner_steps_blocked_zero",
    })
    return [row]


def latest_by_source_key(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    latest: dict[tuple[str, str], dict[str, Any]] = {}
    first_seen: dict[tuple[str, str], datetime] = {}
    last_seen: dict[tuple[str, str], datetime] = {}
    for row in rows:
        key = (str(row.get("source_type")), str(row.get("source_key")))
        seen = parse_utc(row.get("recorded_at_utc")) or parse_utc(row.get("source_generated_at_utc"))
        if seen:
            if key not in first_seen or seen < first_seen[key]:
                first_seen[key] = seen
            if key not in last_seen or seen > last_seen[key]:
                last_seen[key] = seen
        existing = latest.get(key)
        if not existing or str(row.get("source_generated_at_utc") or row.get("recorded_at_utc") or "") >= str(existing.get("source_generated_at_utc") or existing.get("recorded_at_utc") or ""):
            latest[key] = row
    now = datetime.now(timezone.utc)
    for key, row in latest.items():
        opened = first_seen.get(key) or parse_utc(row.get("recorded_at_utc")) or now
        last = last_seen.get(key) or parse_utc(row.get("recorded_at_utc")) or opened
        age_hours = max(0.0, (now - opened).total_seconds() / 3600)
        priority = int(row.get("priority") or 0)
        sla_days = 1 if priority >= 90 else (3 if priority >= 80 else 7)
        ratio = age_hours / (sla_days * 24)
        if ratio >= 1:
            sla_status = "overdue"
        elif ratio >= 0.75:
            sla_status = "due_soon"
        else:
            sla_status = "within_sla"
        row["opened_at_utc"] = opened.replace(microsecond=0).isoformat().replace("+00:00", "Z")
        row["last_seen_at_utc"] = last.replace(microsecond=0).isoformat().replace("+00:00", "Z")
        row["age_hours"] = round(age_hours, 2)
        row["sla_days"] = sla_days
        row["sla_status"] = sla_status
    return sorted(latest.values(), key=lambda row: (int(row.get("priority") or 0), str(row.get("source_generated_at_utc") or "")), reverse=True)


def build_payload(ledger_path: Path, append: bool) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    queue = as_dict(load_json_artifact(WF74_QUEUE))
    otel = as_dict(load_json_artifact(OTEL_LEARNING_LOOP))
    runner = as_dict(load_json_artifact(WF74_RUNNER))
    existing = read_jsonl(ledger_path)
    existing_ids = {str(row.get("event_id")) for row in existing if row.get("event_id")}
    candidate_events = queue_events(queue) + otel_events(otel) + resolution_events(runner)
    new_events = [row for row in candidate_events if row.get("event_id") not in existing_ids]
    if append:
        append_jsonl(ledger_path, new_events)
    all_rows = existing + new_events
    latest = latest_by_source_key([row for row in all_rows if row.get("schema") == EVENT_SCHEMA])
    open_rows = [row for row in latest if row.get("carry_forward") is not False and row.get("status") not in {"complete", "cancelled", "rejected"}]
    high_priority = [row for row in open_rows if int(row.get("priority") or 0) >= 80]
    overdue = [row for row in open_rows if row.get("sla_status") == "overdue"]
    due_soon = [row for row in open_rows if row.get("sla_status") == "due_soon"]
    high_priority_overdue = [row for row in high_priority if row.get("sla_status") == "overdue"]
    if high_priority_overdue:
        escalation_level = "high_priority_overdue"
    elif overdue:
        escalation_level = "overdue"
    elif due_soon:
        escalation_level = "due_soon"
    elif high_priority:
        escalation_level = "high_priority_open"
    else:
        escalation_level = "normal"
    category_counts = Counter(str(row.get("category") or "unknown") for row in open_rows)
    source_counts = Counter(str(row.get("source_type") or "unknown") for row in open_rows)
    privacy_findings = scan_forbidden({"new_events": new_events, "latest_open_improvements": open_rows})
    payload = {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "ok",
        "purpose": "Append-only improvement ledger plus current carry-forward queue for new-session pickup.",
        "mode": "append" if append else "check",
        "authority_boundary": AUTHORITY_BOUNDARY.copy(),
        "ledger_path": rel(ledger_path),
        "source_status": [
            source_status(WF74_QUEUE),
            source_status(OTEL_LEARNING_LOOP),
            source_status(WF74_RUNNER),
        ],
        "summary": {
            "ledger_row_count": len([row for row in read_jsonl(ledger_path) if row.get("schema") == EVENT_SCHEMA]) if append else len([row for row in all_rows if row.get("schema") == EVENT_SCHEMA]),
            "candidate_event_count": len(candidate_events),
            "candidate_new_event_count": len(new_events),
            "would_append_event_count": 0 if append else len(new_events),
            "appended_event_count": len(new_events) if append else 0,
            "latest_open_count": len(open_rows),
            "high_priority_open_count": len(high_priority),
            "overdue_open_count": len(overdue),
            "due_soon_open_count": len(due_soon),
            "high_priority_overdue_open_count": len(high_priority_overdue),
            "escalation_level": escalation_level,
            "by_category": dict(sorted(category_counts.items())),
            "by_source_type": dict(sorted(source_counts.items())),
            "top_improvement_title": open_rows[0].get("title") if open_rows else None,
            "top_improvement_next_action": open_rows[0].get("next_action") if open_rows else None,
            "top_improvement_age_hours": open_rows[0].get("age_hours") if open_rows else None,
            "top_improvement_sla_status": open_rows[0].get("sla_status") if open_rows else None,
            "privacy_scan_status": "ok" if not privacy_findings else "blocked",
        },
        "latest_open_improvements": open_rows[:20],
        "recommendations": [
            {
                "id": "load_improvement_ledger_on_startup",
                "decision": "hard_route_new_sessions_to_improvement_ledger",
                "next_action": "New sessions should inspect tmp/improvement-ledger-current.json after future-session startup before recommending OS/WF74 improvements.",
                "proof": rel(DEFAULT_JSON),
            },
            {
                "id": "use_ledger_not_chat_memory",
                "decision": "treat_chat_context_as_secondary",
                "next_action": "Use data/state-history/improvement-ledger.jsonl and current packet for improvement carry-forward; chat history is not durable authority.",
                "proof": rel(ledger_path),
            },
        ],
        "next_safe_action": "Load this packet in new sessions, review top open improvements, and route implementation through lane register plus validators before applying changes.",
        "blocked_actions": [
            "no auto-apply from ledger",
            "no skill approval/application from ledger",
            "no collector/runtime/config mutation from ledger",
            "no finance canon/portfolio/cash/sizing mutation from ledger",
            "no paper/live/account action from ledger",
            "no owner approval inference from ledger",
        ],
        "privacy_scan": {
            "status": "ok" if not privacy_findings else "blocked",
            "finding_count": len(privacy_findings),
            "findings": privacy_findings,
        },
    }
    payload["validation"] = validate(payload)
    if payload["validation"]["status"] != "ok":
        payload["status"] = "warning"
    return payload, new_events


def validate(payload: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    boundary = as_dict(payload.get("authority_boundary"))
    for key, expected in AUTHORITY_BOUNDARY.items():
        if boundary.get(key) is not expected:
            errors.append(f"authority boundary mismatch: {key}")
    summary = as_dict(payload.get("summary"))
    if summary.get("privacy_scan_status") != "ok":
        errors.append("privacy scan not ok")
    if int(summary.get("latest_open_count") or 0) <= 0:
        warnings.append("no open improvements found")
    for source in payload.get("source_status", []):
        if not source.get("exists"):
            warnings.append(f"missing source: {source.get('path')}")
    return {"status": "critical" if errors else ("warning" if warnings else "ok"), "errors": errors, "warnings": warnings}


def render_md(payload: dict[str, Any]) -> str:
    summary = as_dict(payload.get("summary"))
    lines = [
        "# Improvement Ledger Current",
        "",
        f"- Generated: {payload.get('generated_at_utc')}",
        f"- Status: {payload.get('status')} / validation {as_dict(payload.get('validation')).get('status')}",
        f"- Ledger: `{payload.get('ledger_path')}`",
        f"- Ledger rows: {summary.get('ledger_row_count')}",
        f"- Appended this run: {summary.get('appended_event_count')}",
        f"- Would append in check mode: {summary.get('would_append_event_count')}",
        f"- Open improvements: {summary.get('latest_open_count')} / high priority {summary.get('high_priority_open_count')}",
        f"- SLA pressure: overdue {summary.get('overdue_open_count')} / due soon {summary.get('due_soon_open_count')} / escalation {summary.get('escalation_level')}",
        f"- Top improvement: {summary.get('top_improvement_title')}",
        f"- Next action: {summary.get('top_improvement_next_action')}",
        "",
        "## Open Improvements",
    ]
    for row in payload.get("latest_open_improvements", [])[:10]:
        lines.append(f"- {row.get('title')} [{row.get('category')}] priority={row.get('priority')} sla={row.get('sla_status')} age_hours={row.get('age_hours')} gate={row.get('decision')}")
    lines.extend(["", "## Blocked Actions"])
    for action in payload.get("blocked_actions", []):
        lines.append(f"- {action}")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Build append-only improvement ledger and current packet.")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--check", action="store_true", help="Validate and render from current inputs without appending to the durable ledger.")
    parser.add_argument("--write-md", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--json-out", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--md-out", type=Path, default=DEFAULT_MD)
    parser.add_argument("--ledger-out", type=Path, default=DEFAULT_LEDGER)
    args = parser.parse_args()

    append = bool(args.write and not args.check)
    payload, new_events = build_payload(args.ledger_out, append=append)
    if args.write:
        atomic_write_json(args.json_out, payload)
        if args.write_md:
            atomic_write_text(args.md_out, render_md(payload))
    print(
        f"status={payload.get('status')} validation={as_dict(payload.get('validation')).get('status')} "
        f"mode={payload.get('mode')} open={as_dict(payload.get('summary')).get('latest_open_count')} "
        f"appended={as_dict(payload.get('summary')).get('appended_event_count')} "
        f"would_append={as_dict(payload.get('summary')).get('would_append_event_count')} "
        f"escalation={as_dict(payload.get('summary')).get('escalation_level')} "
        f"ledger={rel(args.ledger_out)}"
    )
    for error in as_dict(payload.get("validation")).get("errors", []):
        print(f"  [critical] {error}")
    for warning in as_dict(payload.get("validation")).get("warnings", []):
        print(f"  [warning] {warning}")
    if args.validate and as_dict(payload.get("validation")).get("status") == "critical":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
