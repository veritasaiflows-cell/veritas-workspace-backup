#!/usr/bin/env python3
"""Build the review-only owner-gate queue for the active workspace OS.

Finance entries are limited to alert/recommendation canon or policy repair.
Capital, account, simulated-account, and execution workflows are outside this
queue and outside the active finance operating system.
"""
from __future__ import annotations

import argparse
import hashlib
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, atomic_write_text, load_json_artifact

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
DEFAULT_JSON = TMP / "owner-gated-action-review-queue.json"
DEFAULT_MD = DEFAULT_JSON.with_suffix(".md")
SCHEMA = "veritas.owner_gated_action_review_queue.v1"

GATES = [
    "skill_approval",
    "cron_schedule_mutation",
    "alert_canon_policy_mutation",
]

SOURCES = {
    "improvement_ledger": TMP / "improvement-ledger-current.json",
    "wf74_auto_patch": TMP / "wf74-auto-patch-proposer.json",
    "cron_patch_manager": TMP / "cron-patch-manager.json",
    "finance_response_quality": TMP / "finance-response-quality-slice.json",
    "alerts_chain": TMP / "alerts-recommendations-chain-midday.json",
}

# cron-patch-manager.json exists only after a cron patch plan/apply; absence means no pending patch.
OPTIONAL_SOURCES = {"tmp/cron-patch-manager.json"}

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "recommendation_queue_only": True,
    "local_only": True,
    "skill_application_allowed": False,
    "skill_approval_allowed": False,
    "cron_schedule_mutation_allowed": False,
    "cron_state_mutation_allowed": False,
    "runtime_config_mutation_allowed": False,
    "alert_canon_or_policy_mutation_allowed": False,
    "capital_or_order_authority": False,
    "maintains_portfolio_state": False,
    "maintains_simulated_account_state": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "money_movement_allowed": False,
    "external_export_allowed": False,
    "owner_approval_inferred": False,
    "auto_apply_allowed": False,
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


def stable_id(*parts: Any) -> str:
    seed = "|".join(str(part or "") for part in parts)
    return hashlib.sha256(seed.encode("utf-8")).hexdigest()[:14]


def source_status(label: str, path: Path) -> dict[str, Any]:
    payload = as_dict(load_json_artifact(path))
    return {
        "label": label,
        "path": rel(path),
        "exists": path.exists(),
        "status": payload.get("status"),
        "validation_status": as_dict(payload.get("validation")).get("status"),
        "generated_at_utc": payload.get("generated_at_utc"),
    }


def blocked_actions_for_gate(gate: str) -> list[str]:
    by_gate = {
        "skill_approval": ["no skill apply, install, or update without explicit owner approval"],
        "cron_schedule_mutation": ["no cron schedule, delivery, runtime, or job mutation without explicit owner approval"],
        "alert_canon_policy_mutation": ["no alert canon, threshold, invalidation, or finance policy mutation without exact scoped proof"],
    }
    return by_gate.get(gate, []) + ["no owner approval inference", "no auto-apply from this queue"]


def queue_item(
    gate: str,
    title: str,
    recommendation: str,
    *,
    priority: int,
    source: str,
    evidence: list[str] | None = None,
    required_owner_decision: str = "approve_reject_defer_or_request_deeper_review",
    required_before_apply: list[str] | None = None,
    risk: str = "owner_gated",
    decision_state: str = "owner_decision_required",
) -> dict[str, Any]:
    return {
        "schema": "veritas.owner_gated_action_review_item.v1",
        "item_id": stable_id(gate, title, source),
        "gate": gate,
        "title": title,
        "priority": priority,
        "decision_state": decision_state,
        "risk": risk,
        "recommendation": recommendation,
        "required_owner_decision": required_owner_decision,
        "required_before_apply": required_before_apply or [],
        "evidence": evidence or [source],
        "source": source,
        "authority_boundary": AUTHORITY_BOUNDARY.copy(),
        "blocked_actions": blocked_actions_for_gate(gate),
    }


def monitor_item(gate: str, title: str, recommendation: str, source: str) -> dict[str, Any]:
    return queue_item(
        gate,
        title,
        recommendation,
        priority=10,
        source=source,
        required_owner_decision="none_now",
        decision_state="monitor_only",
    )


def skill_items(improvement: dict[str, Any]) -> list[dict[str, Any]]:
    rows = [
        row for row in as_list(improvement.get("latest_open_improvements"))
        if isinstance(row, dict) and row.get("category") == "skill_application"
    ]
    if not rows:
        return [monitor_item(
            "skill_approval",
            "No current skill approval recommendation",
            "Create a Skill Workshop proposal only after repeated procedure friction is evidenced.",
            rel(SOURCES["improvement_ledger"]),
        )]
    return [
        queue_item(
            "skill_approval",
            str(row.get("title") or "Skill approval review"),
            str(row.get("next_action") or "Review whether a Skill Workshop proposal should be drafted."),
            priority=int(row.get("priority") or 50),
            source=rel(SOURCES["improvement_ledger"]),
            evidence=as_list(row.get("proof_artifacts")) or [rel(SOURCES["improvement_ledger"])],
            required_before_apply=[
                "Skill Workshop proposal exists",
                "Randall explicitly approves the specific proposal",
                "active-skill validation passes after apply",
            ],
        )
        for row in rows[:3]
    ]


def cron_items(cron_patch: dict[str, Any], auto_patch: dict[str, Any]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    impact = as_dict(cron_patch.get("impact"))
    if as_list(cron_patch.get("diff")):
        items.append(queue_item(
            "cron_schedule_mutation",
            f"Cron patch plan pending: {as_dict(cron_patch.get('job')).get('name') or 'unknown job'}",
            "Review the exact diff, rollback proof, and post-change validation before any apply.",
            priority=72 if impact.get("schedule_mutation") else 52,
            source=rel(SOURCES["cron_patch_manager"]),
            required_before_apply=[
                "exact cron diff is present",
                "rollback path exists",
                "post-change cron control validates",
                "Randall approves the exact mutation",
            ],
            risk="schedule" if impact.get("schedule_mutation") else "cron_runtime_or_payload",
        ))
    for row in as_list(auto_patch.get("owner_gated_reviews")):
        if isinstance(row, dict) and row.get("category") == "collector_config":
            items.append(queue_item(
                "cron_schedule_mutation",
                str(row.get("title") or "Owner-gated collector decision"),
                str(row.get("next_safe_action") or row.get("expected_benefit") or "Review the collector decision packet."),
                priority=int(row.get("priority") or 50),
                source=rel(SOURCES["wf74_auto_patch"]),
                evidence=as_list(row.get("required_artifacts_before_any_change")) or [rel(SOURCES["wf74_auto_patch"])],
                required_before_apply=as_list(row.get("required_artifacts_before_any_change")) + [
                    "Randall explicitly approves the collector/runtime mutation",
                    "rollback and privacy proof are present",
                ],
                risk=str(row.get("route") or "owner_config_decision"),
            ))
    return items or [monitor_item(
        "cron_schedule_mutation",
        "No current cron mutation recommendation",
        "Scheduled review work may continue; schedule or runtime changes remain owner-gated.",
        rel(SOURCES["cron_patch_manager"]),
    )]


def alert_policy_items(improvement: dict[str, Any], quality: dict[str, Any], chain: dict[str, Any]) -> list[dict[str, Any]]:
    rows = [
        row for row in as_list(improvement.get("latest_open_improvements"))
        if isinstance(row, dict) and row.get("category") == "finance_mutation"
    ]
    quality_validation = as_dict(quality.get("validation")).get("status")
    chain_validation = as_dict(chain.get("validation")).get("status")
    if not rows and quality_validation == "ok" and chain_validation == "ok":
        return [monitor_item(
            "alert_canon_policy_mutation",
            "No current alert-canon policy change recommended",
            "Continue evidence, freshness, and recommendation monitoring without changing canonical levels or policy.",
            rel(SOURCES["alerts_chain"]),
        )]
    return [queue_item(
        "alert_canon_policy_mutation",
        "Review alert and recommendation evidence-repair proposal",
        "Prepare a scoped, review-only repair proposal for any verified alert-chain quality gap; do not alter canonical levels from generated output.",
        priority=max([int(row.get("priority") or 70) for row in rows] or [70]),
        source=rel(SOURCES["finance_response_quality"]),
        evidence=[rel(SOURCES["finance_response_quality"]), rel(SOURCES["alerts_chain"])],
        required_before_apply=[
            "source-backed problem statement",
            "exact scoped diff",
            "freshness and lineage proof",
            "backup and rollback proof",
            "post-change alerts-OS validation",
            "exact owner gate when policy or canonical levels change",
        ],
        risk="alert_canon_policy_change",
    )]


def build_payload() -> dict[str, Any]:
    improvement = as_dict(load_json_artifact(SOURCES["improvement_ledger"]))
    auto_patch = as_dict(load_json_artifact(SOURCES["wf74_auto_patch"]))
    cron_patch = as_dict(load_json_artifact(SOURCES["cron_patch_manager"]))
    quality = as_dict(load_json_artifact(SOURCES["finance_response_quality"]))
    chain = as_dict(load_json_artifact(SOURCES["alerts_chain"]))
    items = sorted(
        skill_items(improvement)
        + cron_items(cron_patch, auto_patch)
        + alert_policy_items(improvement, quality, chain),
        key=lambda row: (int(row.get("priority") or 0), str(row.get("gate") or "")),
        reverse=True,
    )
    owner_decisions = [
        item for item in items
        if item.get("decision_state") != "monitor_only" and item.get("required_owner_decision") != "none_now"
    ]
    counts = Counter(str(item.get("gate")) for item in items)
    payload = {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "ok",
        "purpose": "Surface owner-gated workspace decisions without approving or applying them.",
        "finance_scope": "alerts_and_non_executing_recommendations_only",
        "authority_boundary": AUTHORITY_BOUNDARY.copy(),
        "source_status": [source_status(label, path) for label, path in SOURCES.items()],
        "summary": {
            "item_count": len(items),
            "owner_decision_required_count": len(owner_decisions),
            "monitor_only_count": len(items) - len(owner_decisions),
            "by_gate": dict(sorted(counts.items())),
            "top_gate": items[0].get("gate") if items else None,
            "top_title": items[0].get("title") if items else None,
            "top_plain_status": items[0].get("gate") if items else None,
            "top_required_owner_decision": items[0].get("required_owner_decision") if items else None,
            "next_safe_action": (
                "Review the top owner-gated item; approve, reject, defer, or request deeper review."
                if owner_decisions else "No owner decision is currently required."
            ),
        },
        "review_items": items,
        "blocked_actions": [
            "no skill application",
            "no cron schedule, delivery, configuration, or runtime mutation",
            "no alert canon or policy mutation",
            "no capital, order, account, or money action",
            "no external delivery",
            "no owner approval inference",
            "no auto-apply",
        ],
        "validation": {},
    }
    payload["validation"] = validate(payload)
    if payload["validation"]["status"] != "ok":
        payload["status"] = "warning"
    return payload


def validate(payload: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    boundary = as_dict(payload.get("authority_boundary"))
    for key, expected in AUTHORITY_BOUNDARY.items():
        if boundary.get(key) is not expected:
            errors.append(f"authority boundary mismatch: {key}")
    gates = {item.get("gate") for item in as_list(payload.get("review_items")) if isinstance(item, dict)}
    missing = [gate for gate in GATES if gate not in gates]
    if missing:
        errors.append(f"missing gates: {','.join(missing)}")
    for item in as_list(payload.get("review_items")):
        if not isinstance(item, dict):
            continue
        for key, expected in AUTHORITY_BOUNDARY.items():
            if as_dict(item.get("authority_boundary")).get(key) is not expected:
                errors.append(f"item {item.get('item_id')} boundary mismatch: {key}")
        if item.get("decision_state") != "monitor_only" and not item.get("required_before_apply"):
            warnings.append(f"item {item.get('item_id')} missing required_before_apply")
    for source in as_list(payload.get("source_status")):
        if isinstance(source, dict) and not source.get("exists") and source.get("path") not in OPTIONAL_SOURCES:
            warnings.append(f"missing source: {source.get('path')}")
    return {"status": "critical" if errors else ("warning" if warnings else "ok"), "errors": errors, "warnings": warnings}


def render_md(payload: dict[str, Any]) -> str:
    summary = as_dict(payload.get("summary"))
    lines = [
        "# Owner-Gated Action Review Queue",
        "",
        f"- Generated: {payload.get('generated_at_utc')}",
        f"- Status: {payload.get('status')} / validation {as_dict(payload.get('validation')).get('status')}",
        f"- Finance scope: {payload.get('finance_scope')}",
        f"- Items: {summary.get('item_count')} / owner decisions {summary.get('owner_decision_required_count')}",
        f"- Top item: {summary.get('top_title')} [{summary.get('top_gate')}]",
        f"- Next action: {summary.get('next_safe_action')}",
        "",
        "## Review Items",
    ]
    for item in as_list(payload.get("review_items"))[:12]:
        if isinstance(item, dict):
            lines.extend([
                f"- {item.get('title')} [{item.get('gate')}] priority={item.get('priority')} state={item.get('decision_state')}",
                f"  - Recommendation: {item.get('recommendation')}",
                f"  - Owner decision: {item.get('required_owner_decision')}",
            ])
    lines.extend(["", "## Blocked Actions"])
    lines.extend(f"- {action}" for action in as_list(payload.get("blocked_actions")))
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Build owner-gated action review queue.")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--write-md", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--json-out", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--md-out", type=Path, default=DEFAULT_MD)
    args = parser.parse_args()

    payload = build_payload()
    if args.write:
        atomic_write_json(args.json_out, payload)
        if args.write_md:
            atomic_write_text(args.md_out, render_md(payload))
    summary = as_dict(payload.get("summary"))
    print(
        f"status={payload.get('status')} validation={as_dict(payload.get('validation')).get('status')} "
        f"items={summary.get('item_count')} owner_decisions={summary.get('owner_decision_required_count')} "
        f"top={summary.get('top_gate')}:{summary.get('top_title')}"
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
