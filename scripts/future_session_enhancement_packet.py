#!/usr/bin/env python3
"""Build a thin startup packet for future Veritas sessions.

This is a routing/proof surface. It summarizes the current boot route,
workflow/PM/cron/WF74 state, and hard authority boundaries so a new session can
orient quickly without treating generated artifacts as canon or approval.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from market_data_utils import atomic_write_json, atomic_write_text, load_json_artifact

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
MEMORY = ROOT / "memory"
OUT = TMP / "future-session-enhancement-packet.json"
SCHEMA = "veritas.future_session_enhancement_packet.v1"
LOCAL_TZ = ZoneInfo("America/Phoenix")

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "routes_truth_surfaces_only": True,
    "canon_or_portfolio_mutation_allowed": False,
    "capital_deployment_approved": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "config_auth_runtime_mutation_allowed": False,
    "customer_or_external_delivery_allowed": False,
    "owner_approval_inferred": False,
}

CORE_SURFACES = [
    "SOUL.md",
    "AGENTS.md",
    "USER.md",
    "TOOLS.md",
    "06. Playbooks/Startup Truth Index.md",
    "06. Playbooks/Active Workflows.md",
    "MEMORY.md",
]

ARTIFACTS = {
    "pm_control_packet": "tmp/pm-control-packet.json",
    "cron_control_packet": "tmp/cron-control-packet.json",
    "wf74_collection": "tmp/wf74-model-quality-collection-cron-runner.json",
    "improvement_ledger": "tmp/improvement-ledger-current.json",
    "owner_gated_action_review_queue": "tmp/owner-gated-action-review-queue.json",
    "token_usage_ledger": "tmp/token-usage-ledger-current.json",
    "model_run_ledger": "tmp/model-run-ledger-current.json",
    "finance_correctness_ledger": "tmp/finance-recommendation-correctness-ledger-current.json",
    "model_quality_scorecard": "tmp/model-quality-scorecard.json",
    "wf74_cron_duplication_audit": "tmp/wf74-cron-duplication-audit.json",
    "training_dataset_candidates": "tmp/training-dataset-candidates.json",
    "changed_file_validator_router": "tmp/changed-file-validator-router.json",
}

DERIVED_FILES = {
    "artifact_index_sqlite": "tmp/veritas-artifact-index.sqlite",
}

WORKFLOW_IDS = ["WF75", "WF78", "WF79-SMB", "WF72", "WF73", "WF74", "WF84", "WF85"]

CHALLENGER_MODEL_POLICY = {
    "schema": "veritas.challenger_model_policy.v1",
    "scope": "serious finance workflow contracts, authority-sensitive decision layers, and trade-grade OS promotion gates",
    "required_challenger_model": "claude-cli/claude-opus-4-8",
    "use_for": [
        "false-ready detection",
        "authority-drift review",
        "source/freshness and state-precedence critique",
        "schema/contract stress test before implementation or promotion",
    ],
    "do_not_use_as": [
        "routine implementation default",
        "execution authority",
        "approval authority",
        "canon or portfolio mutation authority",
    ],
    "verification_rule": "After spawn, verify the actual subagent model path equals claude-cli/claude-opus-4-8; labels such as Opus are not sufficient.",
    "fallback_rule": "If the verified model path is unavailable or mismatched, classify the lane as standard challenger output and do not count it as Opus acceptance proof.",
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


def file_state(path: str) -> dict[str, Any]:
    full = ROOT / path
    try:
        stat = full.stat()
    except FileNotFoundError:
        return {"path": path, "exists": False}
    return {
        "path": path,
        "exists": True,
        "size_bytes": stat.st_size,
        "modified_utc": datetime.fromtimestamp(stat.st_mtime, timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
    }


def artifact_state(label: str, path: str) -> dict[str, Any]:
    full = ROOT / path
    data = as_dict(load_json_artifact(full))
    validation = as_dict(data.get("validation"))
    summary = as_dict(data.get("summary"))
    return {
        "label": label,
        "path": path,
        "exists": full.exists(),
        "schema": data.get("schema"),
        "status": data.get("status"),
        "validation_status": validation.get("status"),
        "generated_at_utc": data.get("generated_at_utc"),
        "summary_keys": sorted(summary.keys())[:20],
    }


def daily_memory_surfaces(now: datetime) -> list[dict[str, Any]]:
    today = now.date()
    yesterday = today - timedelta(days=1)
    candidates = [
        MEMORY / f"{today.isoformat()}.md",
        MEMORY / f"{yesterday.isoformat()}.md",
    ]
    states: list[dict[str, Any]] = []
    for path in candidates:
        states.append(file_state(rel(path)))
    return states


def workflow_capsules() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for workflow_id in WORKFLOW_IDS:
        path = ROOT / "state" / "workflows" / f"{workflow_id}.json"
        data = as_dict(load_json_artifact(path))
        rows.append({
            "workflow_id": workflow_id,
            "path": rel(path),
            "exists": path.exists(),
            "effective_status": data.get("effective_status"),
            "helper_safe": data.get("helper_safe"),
            "next_action": data.get("next_action"),
            "authority_boundary": data.get("authority_boundary"),
            "blocker_count": len(as_list(data.get("blockers"))),
        })
    return rows


def extract_pm_summary() -> dict[str, Any]:
    data = as_dict(load_json_artifact(TMP / "pm-control-packet.json"))
    summary = as_dict(data.get("summary"))
    next_actions = as_list(data.get("next_actions"))
    jobs = as_list(as_dict(data.get("implementation_job_queue")).get("jobs"))
    return {
        "status": data.get("status"),
        "validation_status": as_dict(data.get("validation")).get("status"),
        "top_lane": (next_actions[0] or {}).get("lane_id") if next_actions and isinstance(next_actions[0], dict) else None,
        "top_action": (next_actions[0] or {}).get("description") if next_actions and isinstance(next_actions[0], dict) else None,
        "open_job_count": len(jobs),
        "summary": {key: summary.get(key) for key in sorted(summary.keys())[:12]},
    }


def extract_cron_summary() -> dict[str, Any]:
    data = as_dict(load_json_artifact(TMP / "cron-control-packet.json"))
    summary = as_dict(data.get("summary"))
    escalation = as_dict(data.get("escalation"))
    return {
        "status": data.get("status"),
        "validation_status": as_dict(data.get("validation")).get("status"),
        "escalation_count": summary.get("escalation_count"),
        "should_wake_main_session": escalation.get("should_wake_main_session"),
        "summary": {key: summary.get(key) for key in sorted(summary.keys())[:12]},
    }


def extract_wf74_summary() -> dict[str, Any]:
    collection = as_dict(load_json_artifact(TMP / "wf74-model-quality-collection-cron-runner.json"))
    improvement_ledger = as_dict(load_json_artifact(TMP / "improvement-ledger-current.json"))
    owner_gated = as_dict(load_json_artifact(TMP / "owner-gated-action-review-queue.json"))
    token_usage = as_dict(load_json_artifact(TMP / "token-usage-ledger-current.json"))
    model_run = as_dict(load_json_artifact(TMP / "model-run-ledger-current.json"))
    finance = as_dict(load_json_artifact(TMP / "finance-recommendation-correctness-ledger-current.json"))
    scorecard = as_dict(load_json_artifact(TMP / "model-quality-scorecard.json"))
    duplication_audit = as_dict(load_json_artifact(TMP / "wf74-cron-duplication-audit.json"))
    collection_summary = as_dict(collection.get("summary"))
    improvement_summary = as_dict(improvement_ledger.get("summary"))
    owner_gated_summary = as_dict(owner_gated.get("summary"))
    token_summary = as_dict(token_usage.get("summary"))
    model_summary = as_dict(model_run.get("summary"))
    finance_summary = as_dict(finance.get("summary"))
    duplication_summary = as_dict(duplication_audit.get("summary"))
    return {
        "collection_status": collection.get("status"),
        "collection_validation": as_dict(collection.get("validation")).get("status"),
        "steps_ok": collection_summary.get("steps_ok"),
        "steps_blocked": collection_summary.get("steps_blocked"),
        "improvement_ledger_status": improvement_ledger.get("status"),
        "improvement_ledger_validation": as_dict(improvement_ledger.get("validation")).get("status"),
        "improvement_ledger_rows": improvement_summary.get("ledger_row_count"),
        "improvement_open_count": improvement_summary.get("latest_open_count"),
        "improvement_high_priority_open_count": improvement_summary.get("high_priority_open_count"),
        "improvement_overdue_open_count": improvement_summary.get("overdue_open_count"),
        "improvement_due_soon_open_count": improvement_summary.get("due_soon_open_count"),
        "improvement_high_priority_overdue_open_count": improvement_summary.get("high_priority_overdue_open_count"),
        "improvement_escalation_level": improvement_summary.get("escalation_level"),
        "improvement_top_title": improvement_summary.get("top_improvement_title"),
        "improvement_top_next_action": improvement_summary.get("top_improvement_next_action"),
        "improvement_top_age_hours": improvement_summary.get("top_improvement_age_hours"),
        "improvement_top_sla_status": improvement_summary.get("top_improvement_sla_status"),
        "owner_gated_review_status": owner_gated.get("status"),
        "owner_gated_review_validation": as_dict(owner_gated.get("validation")).get("status"),
        "owner_gated_item_count": owner_gated_summary.get("item_count"),
        "owner_gated_decision_required_count": owner_gated_summary.get("owner_decision_required_count"),
        "owner_gated_top_gate": owner_gated_summary.get("top_gate"),
        "owner_gated_top_title": owner_gated_summary.get("top_title"),
        "owner_gated_next_safe_action": owner_gated_summary.get("next_safe_action"),
        "token_usage_status": token_usage.get("status"),
        "token_usage_validation": as_dict(token_usage.get("validation")).get("status"),
        "token_usage_event_count": token_summary.get("token_event_count"),
        "token_usage_total_tokens": token_summary.get("total_tokens"),
        "token_usage_cron_event_count": token_summary.get("cron_token_event_count"),
        "token_usage_implementation_event_count": token_summary.get("implementation_token_event_count"),
        "token_usage_implementation_gap_count": token_summary.get("implementation_token_gap_count"),
        "token_usage_pricing_status": token_summary.get("pricing_status"),
        "model_run_rows": model_summary.get("row_count"),
        "model_attribution_coverage": model_summary.get("model_attribution_coverage"),
        "session_attribution_coverage": model_summary.get("session_attribution_coverage"),
        "finance_correctness_rows": finance_summary.get("row_count"),
        "finance_ok_rows": finance_summary.get("ok_count"),
        "finance_warning_rows": finance_summary.get("warning_count"),
        "finance_blocked_rows": finance_summary.get("blocked_count"),
        "scorecard_validation": as_dict(scorecard.get("validation")).get("status"),
        "cron_duplication_status": duplication_audit.get("status"),
        "cron_duplication_validation": as_dict(duplication_audit.get("validation")).get("status"),
        "cron_owner_job_matches": duplication_summary.get("owner_job_matches"),
        "cron_component_collectors_outside_owner": duplication_summary.get("recurring_component_collectors_outside_owner_count"),
        "cron_one_shot_component_reminders": duplication_summary.get("one_shot_component_collectors_outside_owner_count"),
        "active_tracks": scorecard.get("active_tracks"),
        "blocked_claims": [
            "model ranking until repeated attributed samples and WF55 graded outcome history exist",
            "investment correctness from OTEL/runtime/validator success",
            "WF55 later outcome grading outside the WF55 gated process",
        ],
    }


def recommended_routes() -> list[dict[str, Any]]:
    return [
        {
            "use_case": "new session or post-compaction startup",
            "command": "python scripts\\future_session_enhancement_packet.py --write --write-md --validate",
        },
        {
            "use_case": "named workflow pickup",
            "command": "python scripts\\workflow_router.py WF## --answer all",
        },
        {
            "use_case": "PM queue and next action",
            "command": "python scripts\\pm_control_packet.py --write --write-db --validate",
        },
        {
            "use_case": "cron/autonomy trust",
            "command": "python scripts\\cron_control_packet.py --write --validate",
        },
        {
            "use_case": "model/run/finance-quality evidence",
            "command": "python scripts\\wf74_model_quality_collection_cron_runner.py --write --write-md --validate --include-harness",
        },
        {
            "use_case": "refresh current improvement packet without appending durable history",
            "command": "python scripts\\improvement_ledger.py --check --write --write-md --validate",
        },
        {
            "use_case": "owner-gated approval/recommendation queue",
            "command": "python scripts\\owner_gated_action_review_queue.py --write --write-md --validate",
        },
        {
            "use_case": "rank cron and implementation token usage",
            "command": "python scripts\\token_usage_ledger.py --write --write-md --validate",
        },
        {
            "use_case": "WF74 cron duplicate collector audit",
            "command": "python scripts\\wf74_cron_duplication_audit.py --write --validate",
        },
        {
            "use_case": "local eval/training candidate review",
            "command": "python scripts\\training_dataset_candidate_builder.py --write --write-md --validate",
        },
        {
            "use_case": "changed-file validator choice",
            "command": "python scripts\\changed_file_validator_router.py --write --validate",
        },
    ]


def build_payload(now: datetime) -> dict[str, Any]:
    payload = {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "ok",
        "posture": "future_session_startup_routing_packet",
        "authority_boundary": AUTHORITY_BOUNDARY.copy(),
        "core_surfaces": [file_state(path) for path in CORE_SURFACES],
        "daily_memory_surfaces": daily_memory_surfaces(now),
        "artifacts": [artifact_state(label, path) for label, path in ARTIFACTS.items()],
        "derived_files": [file_state(path) | {"label": label} for label, path in DERIVED_FILES.items()],
        "workflow_capsules": workflow_capsules(),
        "pm_summary": extract_pm_summary(),
        "cron_summary": extract_cron_summary(),
        "wf74_summary": extract_wf74_summary(),
        "recommended_routes": recommended_routes(),
        "challenger_model_policy": CHALLENGER_MODEL_POLICY.copy(),
        "rsi_observation": {
            "schema": "wf74.rsi_observation.v1",
            "source": "future_session_enhancement_packet",
            "lesson_type": "daily_context",
            "owner_surface": "Startup Truth Index / TOOLS.md / WF74",
            "what_changed": "Future-session startup context was compressed into one packet with PM, cron, WF74, workflow, memory, route, and stop-line state.",
            "warnings_or_blockers": [],
            "future_session_lesson": "Open this packet first after compaction/new-session handoff, then drill into exact owner artifacts only for the active request.",
            "recommended_destination": "memory/YYYY-MM-DD.md for daily deltas; promote only repeated startup failures to skill or TOOLS.md.",
            "actionability": "use_as_startup_route",
        },
        "next_safe_action": "Open this packet first, then drill into exact owner artifacts only for the active request.",
        "stop_lines": [
            "Generated packets route proof; they are not canon or approval.",
            "Do not infer owner approval, portfolio/canon mutation, capital deployment, or paper/live/account authority.",
            "Model-quality evidence is review-only until sample depth, attribution, and WF55 graded outcomes support stronger claims.",
            "For serious finance workflow gates, Opus challenger acceptance requires verified model path claude-cli/claude-opus-4-8; label text alone is not proof.",
        ],
    }
    payload["validation"] = validate(payload)
    if payload["validation"]["status"] != "ok":
        payload["status"] = "warning"
    return payload


def validate(payload: dict[str, Any]) -> dict[str, Any]:
    findings: list[dict[str, Any]] = []
    boundary = as_dict(payload.get("authority_boundary"))
    for key, expected in AUTHORITY_BOUNDARY.items():
        if boundary.get(key) is not expected:
            findings.append({"severity": "critical", "detail": f"authority boundary mismatch: {key}"})
    missing_core = [item["path"] for item in payload.get("core_surfaces", []) if not item.get("exists")]
    for path in missing_core:
        findings.append({"severity": "critical", "detail": f"missing core surface: {path}"})
    missing_memory = [item["path"] for item in payload.get("daily_memory_surfaces", []) if not item.get("exists")]
    for path in missing_memory:
        findings.append({"severity": "warning", "detail": f"missing daily memory surface: {path}"})
    for artifact in payload.get("artifacts", []):
        if not artifact.get("exists"):
            findings.append({"severity": "warning", "detail": f"missing artifact: {artifact.get('path')}"})
    wf74 = as_dict(payload.get("wf74_summary"))
    if wf74.get("collection_validation") not in {None, "ok"}:
        findings.append({"severity": "warning", "detail": "WF74 collection validation is not ok"})
    if wf74.get("improvement_ledger_validation") not in {None, "ok"}:
        findings.append({"severity": "warning", "detail": "improvement ledger validation is not ok"})
    if wf74.get("improvement_escalation_level") == "high_priority_overdue":
        findings.append({"severity": "warning", "detail": "high-priority improvement is overdue"})
    if wf74.get("owner_gated_review_validation") not in {None, "ok"}:
        findings.append({"severity": "warning", "detail": "owner-gated action review queue validation is not ok"})
    if wf74.get("token_usage_validation") == "critical":
        findings.append({"severity": "warning", "detail": "token usage ledger validation is critical"})
    if wf74.get("cron_duplication_validation") not in {None, "ok"}:
        findings.append({"severity": "warning", "detail": "WF74 cron duplication audit validation is not ok"})
    if wf74.get("cron_component_collectors_outside_owner") not in {0, None}:
        findings.append({"severity": "critical", "detail": "WF74 cron component collectors found outside owner job"})
    challenger_policy = as_dict(payload.get("challenger_model_policy"))
    if challenger_policy.get("required_challenger_model") != "claude-cli/claude-opus-4-8":
        findings.append({"severity": "critical", "detail": "challenger model policy must require claude-cli/claude-opus-4-8"})
    critical = sum(1 for finding in findings if finding["severity"] == "critical")
    warnings = sum(1 for finding in findings if finding["severity"] == "warning")
    return {"status": "critical" if critical else ("warning" if warnings else "ok"), "critical": critical, "warnings": warnings, "findings": findings}


def render_md(payload: dict[str, Any]) -> str:
    wf74 = as_dict(payload.get("wf74_summary"))
    pm = as_dict(payload.get("pm_summary"))
    cron = as_dict(payload.get("cron_summary"))
    validation = as_dict(payload.get("validation"))
    challenger_policy = as_dict(payload.get("challenger_model_policy"))
    lines = [
        "# Future Session Enhancement Packet",
        "",
        f"- Generated: {payload.get('generated_at_utc')}",
        f"- Status: {payload.get('status')} / validation {validation.get('status')}",
        f"- PM status: {pm.get('status')} / top lane {pm.get('top_lane')}",
        f"- Cron status: {cron.get('status')} / wake main {cron.get('should_wake_main_session')}",
        f"- WF74 collection: {wf74.get('collection_status')} / validation {wf74.get('collection_validation')}",
        f"- WF74 model attribution: {wf74.get('model_attribution_coverage')}",
        f"- WF74 session attribution: {wf74.get('session_attribution_coverage')}",
        f"- WF74 duplicate cron collectors outside owner: {wf74.get('cron_component_collectors_outside_owner')}",
        f"- Improvement ledger open/high: {wf74.get('improvement_open_count')} / {wf74.get('improvement_high_priority_open_count')}",
        f"- Improvement ledger SLA: overdue {wf74.get('improvement_overdue_open_count')} / due soon {wf74.get('improvement_due_soon_open_count')} / escalation {wf74.get('improvement_escalation_level')}",
        f"- Top improvement: {wf74.get('improvement_top_title')}",
        f"- Owner-gated decisions: {wf74.get('owner_gated_decision_required_count')} / top {wf74.get('owner_gated_top_gate')}: {wf74.get('owner_gated_top_title')}",
        f"- Token usage events/tokens: {wf74.get('token_usage_event_count')} / {wf74.get('token_usage_total_tokens')}",
        f"- Implementation token events/gaps: {wf74.get('token_usage_implementation_event_count')} / {wf74.get('token_usage_implementation_gap_count')}",
        f"- Finance correctness rows ok/warn/blocked: {wf74.get('finance_ok_rows')} / {wf74.get('finance_warning_rows')} / {wf74.get('finance_blocked_rows')}",
        f"- Serious-work challenger model: {challenger_policy.get('required_challenger_model')}",
        "",
        "## Open First",
    ]
    for route in payload.get("recommended_routes", []):
        lines.append(f"- {route.get('use_case')}: `{route.get('command')}`")
    lines.extend([
        "",
        "## Stop Lines",
    ])
    for line in payload.get("stop_lines", []):
        lines.append(f"- {line}")
    lines.extend([
        "",
        "## Challenger Model Policy",
        f"- Scope: {challenger_policy.get('scope')}",
        f"- Required model: `{challenger_policy.get('required_challenger_model')}`",
        f"- Verification: {challenger_policy.get('verification_rule')}",
        f"- Fallback: {challenger_policy.get('fallback_rule')}",
    ])
    if validation.get("findings"):
        lines.extend(["", "## Validation Findings"])
        for finding in validation["findings"]:
            lines.append(f"- [{finding.get('severity')}] {finding.get('detail')}")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a future-session startup enhancement packet.")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--write-md", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--out", type=Path, default=OUT)
    args = parser.parse_args()

    payload = build_payload(datetime.now(LOCAL_TZ))
    if args.write:
        atomic_write_json(args.out, payload)
        if args.write_md:
            atomic_write_text(args.out.with_suffix(".md"), render_md(payload))
    print(
        f"status={payload['status']} validation={payload['validation']['status']} "
        f"wf74={payload['wf74_summary'].get('collection_status')} "
        f"pm={payload['pm_summary'].get('status')} cron={payload['cron_summary'].get('status')}"
    )
    for finding in payload["validation"]["findings"]:
        print(f"  [{finding['severity']}] {finding['detail']}")
    if args.validate and payload["validation"]["status"] == "critical":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
