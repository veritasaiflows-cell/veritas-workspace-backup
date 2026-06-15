#!/usr/bin/env python3
"""Build a review-only queue for actions that require Randall approval.

This packet is deliberately not an apply path. It normalizes owner-gated
recommendations for skill approval, cron mutation, finance canon/portfolio
mutation, capital deployment, and execution so new sessions can surface them
without inferring approval.
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
DEFAULT_JSON = TMP / "owner-gated-action-review-queue.json"
DEFAULT_MD = DEFAULT_JSON.with_suffix(".md")
SCHEMA = "veritas.owner_gated_action_review_queue.v1"

GATES = [
    "skill_approval",
    "cron_schedule_mutation",
    "finance_canon_portfolio_mutation",
    "capital_deployment",
    "execution",
]

SOURCES = {
    "improvement_ledger": TMP / "improvement-ledger-current.json",
    "wf74_auto_patch": TMP / "wf74-auto-patch-proposer.json",
    "wf74_reflection": TMP / "wf74-reflection-to-proposal-autopilot.json",
    "cron_patch_manager": TMP / "cron-patch-manager.json",
    "capital_review_queue": TMP / "wf78-capital-review-queue.json",
    "portfolio_mutation_posture": TMP / "portfolio-mutation-proposal-posture.json",
    "wf87_circuit_breakers": TMP / "wf87-portfolio-circuit-breakers.json",
}

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "recommendation_queue_only": True,
    "local_only": True,
    "skill_application_allowed": False,
    "skill_approval_allowed": False,
    "cron_schedule_mutation_allowed": False,
    "cron_state_mutation_allowed": False,
    "runtime_config_mutation_allowed": False,
    "finance_canon_or_portfolio_mutation_allowed": False,
    "cash_sizing_sleeve_risk_rule_mutation_allowed": False,
    "capital_deployment_allowed": False,
    "capital_deployment_approved": False,
    "trade_or_execution_allowed": False,
    "trade_or_execution_approved": False,
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


def blocked_actions_for_gate(gate: str) -> list[str]:
    common = ["no owner approval inference", "no auto-apply from this queue"]
    by_gate = {
        "skill_approval": ["no skill apply/install/update without explicit owner approval"],
        "cron_schedule_mutation": ["no cron schedule, delivery, runtime, or job mutation without explicit owner approval"],
        "finance_canon_portfolio_mutation": ["no canon, portfolio, cash, sizing, sleeve, or risk-rule mutation without exact gate proof"],
        "capital_deployment": ["no buy, sell, add, trim, remove, allocation, or deployment approval inferred"],
        "execution": ["no paper/live submit, cancel, replace, sell, brokerage/account action, or money movement"],
    }
    return by_gate.get(gate, []) + common


def skill_items(improvement: dict[str, Any]) -> list[dict[str, Any]]:
    rows = [
        row for row in as_list(improvement.get("latest_open_improvements"))
        if isinstance(row, dict) and row.get("category") == "skill_application"
    ]
    if not rows:
        return [queue_item(
            "skill_approval",
            "No current skill approval recommendation",
            "Keep monitoring improvement ledger; create Skill Workshop proposals only after repeated procedure friction.",
            priority=10,
            source=rel(SOURCES["improvement_ledger"]),
            decision_state="monitor_only",
            required_owner_decision="none_now",
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
                "Randall explicitly asks to apply or approve the specific proposal",
                "openclaw skills check passes after apply",
            ],
        )
        for row in rows[:3]
    ]


def cron_items(cron_patch: dict[str, Any], auto_patch: dict[str, Any]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    impact = as_dict(cron_patch.get("impact"))
    diff = as_list(cron_patch.get("diff"))
    if diff:
        mutation_type = "schedule" if impact.get("schedule_mutation") else "cron_runtime_or_payload"
        items.append(queue_item(
            "cron_schedule_mutation",
            f"Cron patch plan pending: {as_dict(cron_patch.get('job')).get('name') or 'unknown job'}",
            "Review the cron patch diff, backup/rollback posture, and expected benefit before any apply.",
            priority=72 if impact.get("schedule_mutation") else 52,
            source=rel(SOURCES["cron_patch_manager"]),
            evidence=[rel(SOURCES["cron_patch_manager"])],
            required_before_apply=[
                "cron_patch_manager apply preview is exact",
                "backup path exists",
                "post-apply cron control validates",
                "Randall approves the exact job mutation",
            ],
            risk=mutation_type,
        ))
    for row in as_list(auto_patch.get("owner_gated_reviews")):
        if isinstance(row, dict) and row.get("category") == "collector_config":
            items.append(queue_item(
                "cron_schedule_mutation",
                str(row.get("title") or "Owner-gated runtime/collector decision"),
                str(row.get("next_safe_action") or row.get("expected_benefit") or "Review owner-gated runtime decision packet."),
                priority=int(row.get("priority") or 50),
                source=rel(SOURCES["wf74_auto_patch"]),
                evidence=as_list(row.get("required_artifacts_before_any_change")) or [rel(SOURCES["wf74_auto_patch"])],
                required_before_apply=as_list(row.get("required_artifacts_before_any_change")) + [
                    "Randall explicitly approves collector/runtime mutation",
                    "rollback and privacy proof are present",
                ],
                risk=str(row.get("route") or "owner_config_decision"),
            ))
    return items or [queue_item(
        "cron_schedule_mutation",
        "No current cron mutation recommendation",
        "Cron may continue refreshing review packets; schedule/config changes remain owner-gated.",
        priority=10,
        source=rel(SOURCES["cron_patch_manager"]),
        decision_state="monitor_only",
        required_owner_decision="none_now",
    )]


def finance_mutation_items(improvement: dict[str, Any], posture: dict[str, Any]) -> list[dict[str, Any]]:
    rows = [
        row for row in as_list(improvement.get("latest_open_improvements"))
        if isinstance(row, dict) and row.get("category") == "finance_mutation"
    ]
    items = [
        queue_item(
            "finance_canon_portfolio_mutation",
            str(row.get("title") or "Finance canon/portfolio mutation review"),
            str(row.get("next_action") or "Prepare review-only finance repair or mutation proposal."),
            priority=int(row.get("priority") or 80),
            source=rel(SOURCES["improvement_ledger"]),
            evidence=as_list(row.get("proof_artifacts")) or [rel(SOURCES["improvement_ledger"])],
            required_before_apply=[
                "scoped proposal and exact diff",
                "standing/scoped authority gate",
                "validator proof",
                "backup/rollback",
                "post-apply audit trail",
            ],
            risk="finance_canon_portfolio_mutation",
        )
        for row in rows[:3]
    ]
    if as_dict(posture.get("authority")).get("portfolio_mutation_allowed") is False:
        items.append(queue_item(
            "finance_canon_portfolio_mutation",
            "Portfolio mutation lane is initialized but apply is disabled",
            "Use this lane for proposals only until Randall gives exact scoped apply approval.",
            priority=45,
            source=rel(SOURCES["portfolio_mutation_posture"]),
            evidence=[rel(SOURCES["portfolio_mutation_posture"])],
            required_before_apply=as_list(posture.get("validators")) + [
                "explicit owner scope",
                "proposal diff and rollback",
            ],
            risk="portfolio_apply_disabled",
        ))
    return items or [queue_item(
        "finance_canon_portfolio_mutation",
        "No current finance canon/portfolio mutation recommendation",
        "Keep generating proposals only; do not mutate canon or portfolio from review artifacts.",
        priority=10,
        source=rel(SOURCES["portfolio_mutation_posture"]),
        decision_state="monitor_only",
        required_owner_decision="none_now",
    )]


def capital_items(capital_queue: dict[str, Any]) -> list[dict[str, Any]]:
    rows = [row for row in as_list(capital_queue.get("rows")) if isinstance(row, dict)]
    if not rows:
        return [queue_item(
            "capital_deployment",
            "No current capital deployment review candidate",
            "Keep capital review blocked until a review-ready candidate queue exists.",
            priority=10,
            source=rel(SOURCES["capital_review_queue"]),
            decision_state="monitor_only",
            required_owner_decision="none_now",
        )]
    items: list[dict[str, Any]] = []
    for row in rows[:5]:
        ticker = str(row.get("ticker") or "UNKNOWN")
        band = row.get("current_band_status") or as_dict(row.get("written_band")).get("current_band_status")
        items.append(queue_item(
            "capital_deployment",
            f"Capital review card ready: {ticker}",
            f"Prepare or review a non-executing owner capital-review card for {ticker}; current band status {band}.",
            priority=max(30, 90 - int(row.get("queue_rank") or 9) * 5),
            source=rel(SOURCES["capital_review_queue"]),
            evidence=as_list(row.get("source_artifacts")) or [rel(SOURCES["capital_review_queue"])],
            required_before_apply=[
                "fresh quote/band/stop confirmation",
                "owner selects ticker and deployment intent",
                "sizing/staggering recommendation card",
                "explicit owner capital approval",
            ],
            risk="capital_review_only",
        ))
    return items


def execution_items(auto_patch: dict[str, Any], circuit: dict[str, Any]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for row in as_list(auto_patch.get("owner_gated_reviews")):
        if isinstance(row, dict) and row.get("category") == "execution":
            items.append(queue_item(
                "execution",
                str(row.get("title") or "Execution owner gate review"),
                str(row.get("next_safe_action") or "Keep execution blocked unless exact approval and guard proof exist."),
                priority=int(row.get("priority") or 40),
                source=rel(SOURCES["wf74_auto_patch"]),
                evidence=as_list(row.get("required_artifacts_before_any_action")) or [rel(SOURCES["wf74_auto_patch"])],
                required_owner_decision="exact_order_approval_or_keep_blocked",
                required_before_apply=as_list(row.get("required_artifacts_before_any_action")),
                risk="execution_guardrail_review",
            ))
    if circuit.get("status") == "blocked":
        items.append(queue_item(
            "execution",
            "Paper/live execution is blocked by circuit breaker proof",
            str(as_dict(circuit.get("summary")).get("next_safe_action") or "Keep execution blocked."),
            priority=65,
            source=rel(SOURCES["wf87_circuit_breakers"]),
            evidence=[rel(SOURCES["wf87_circuit_breakers"])],
            required_owner_decision="keep_blocked_until_fresh_guard_proof",
            required_before_apply=[
                "fresh WF63/WF67 paper-only guard proof",
                "fresh kill switch",
                "exact owner-approved order/request artifact",
                "paper/live isolation validation",
            ],
            risk="execution_blocked",
            decision_state="blocked_until_owner_and_guard_proof",
        ))
    return items or [queue_item(
        "execution",
        "No current execution recommendation",
        "Continue producing approval-ready cards only; execution remains exact-owner-gated.",
        priority=10,
        source=rel(SOURCES["wf74_auto_patch"]),
        decision_state="monitor_only",
        required_owner_decision="none_now",
    )]


def build_payload() -> dict[str, Any]:
    improvement = as_dict(load_json_artifact(SOURCES["improvement_ledger"]))
    auto_patch = as_dict(load_json_artifact(SOURCES["wf74_auto_patch"]))
    cron_patch = as_dict(load_json_artifact(SOURCES["cron_patch_manager"]))
    capital_queue = as_dict(load_json_artifact(SOURCES["capital_review_queue"]))
    posture = as_dict(load_json_artifact(SOURCES["portfolio_mutation_posture"]))
    circuit = as_dict(load_json_artifact(SOURCES["wf87_circuit_breakers"]))

    items = (
        skill_items(improvement)
        + cron_items(cron_patch, auto_patch)
        + finance_mutation_items(improvement, posture)
        + capital_items(capital_queue)
        + execution_items(auto_patch, circuit)
    )
    items = sorted(items, key=lambda row: (int(row.get("priority") or 0), row.get("gate", "")), reverse=True)
    category_counts = Counter(str(item.get("gate")) for item in items)
    owner_decisions = [
        item for item in items
        if item.get("decision_state") not in {"monitor_only"} and item.get("required_owner_decision") != "none_now"
    ]
    payload = {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "ok",
        "purpose": "Automatically surface owner-gated recommendations without approving or applying them.",
        "authority_boundary": AUTHORITY_BOUNDARY.copy(),
        "source_status": [source_status(label, path) for label, path in SOURCES.items()],
        "summary": {
            "item_count": len(items),
            "owner_decision_required_count": len(owner_decisions),
            "monitor_only_count": len(items) - len(owner_decisions),
            "by_gate": dict(sorted(category_counts.items())),
            "capital_review_candidate_count": as_dict(capital_queue.get("summary")).get("candidate_count"),
            "top_gate": items[0].get("gate") if items else None,
            "top_title": items[0].get("title") if items else None,
            "top_required_owner_decision": items[0].get("required_owner_decision") if items else None,
            "next_safe_action": "Review top owner-gated item; approve/reject/defer/request deeper review explicitly. Do not apply from this packet.",
        },
        "review_items": items,
        "blocked_actions": [
            "no skill apply/install/update",
            "no cron schedule/config/runtime mutation",
            "no finance canon/portfolio/cash/sizing/risk mutation",
            "no capital deployment approval",
            "no paper/live/brokerage/account execution",
            "no money movement",
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
        item_boundary = as_dict(item.get("authority_boundary"))
        for key, expected in AUTHORITY_BOUNDARY.items():
            if item_boundary.get(key) is not expected:
                errors.append(f"item {item.get('item_id')} boundary mismatch: {key}")
        if item.get("decision_state") != "monitor_only" and not item.get("required_before_apply"):
            warnings.append(f"item {item.get('item_id')} missing required_before_apply")
    for source in as_list(payload.get("source_status")):
        if isinstance(source, dict) and not source.get("exists"):
            warnings.append(f"missing source: {source.get('path')}")
    return {"status": "critical" if errors else ("warning" if warnings else "ok"), "errors": errors, "warnings": warnings}


def render_md(payload: dict[str, Any]) -> str:
    summary = as_dict(payload.get("summary"))
    lines = [
        "# Owner-Gated Action Review Queue",
        "",
        f"- Generated: {payload.get('generated_at_utc')}",
        f"- Status: {payload.get('status')} / validation {as_dict(payload.get('validation')).get('status')}",
        f"- Items: {summary.get('item_count')} / owner decisions {summary.get('owner_decision_required_count')}",
        f"- Top item: {summary.get('top_title')} [{summary.get('top_gate')}]",
        f"- Next action: {summary.get('next_safe_action')}",
        "",
        "## Review Items",
    ]
    for item in as_list(payload.get("review_items"))[:12]:
        if not isinstance(item, dict):
            continue
        lines.extend([
            f"- {item.get('title')} [{item.get('gate')}] priority={item.get('priority')} state={item.get('decision_state')}",
            f"  - Recommendation: {item.get('recommendation')}",
            f"  - Owner decision: {item.get('required_owner_decision')}",
        ])
    lines.extend(["", "## Blocked Actions"])
    for action in as_list(payload.get("blocked_actions")):
        lines.append(f"- {action}")
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
