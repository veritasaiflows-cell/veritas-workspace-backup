#!/usr/bin/env python3
"""Build gated WF74 auto-patch and skill-update proposals.

This is the bridge between WF74 reflection proposals and implementation work.
It may classify, plan, and validate patch/skill requests. It does not directly
apply code, apply skills, widen authority, mutate config, or touch finance
canon/portfolio/execution surfaces.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, atomic_write_text, load_json_artifact

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
DEFAULT_QUEUE = TMP / "wf74-improvement-opportunity-queue.json"
DEFAULT_PROPOSALS = TMP / "wf74-reflection-to-proposal-autopilot.json"
DEFAULT_OUT = TMP / "wf74-auto-patch-proposer.json"
DEFAULT_MD = DEFAULT_OUT.with_suffix(".md")
SCHEMA = "veritas.wf74_auto_patch_proposer.v1"

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "local_only": True,
    "proposal_generation_only": True,
    "patch_plan_generation_allowed": True,
    "skill_workshop_request_generation_allowed": True,
    "code_mutation_allowed": False,
    "skill_application_allowed": False,
    "collector_config_mutation_allowed": False,
    "runtime_config_mutation_allowed": False,
    "cron_schedule_mutation_allowed": False,
    "finance_canon_or_portfolio_mutation_allowed": False,
    "cash_sizing_sleeve_risk_rule_mutation_allowed": False,
    "capital_deployment_allowed": False,
    "trade_or_execution_allowed": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "money_movement_allowed": False,
    "external_export_allowed": False,
    "raw_prompt_or_response_capture_allowed": False,
    "tool_payload_capture_allowed": False,
    "owner_approval_inferred": False,
    "auto_apply_allowed": False,
}

SAFE_AUTO_APPLY_CLASSES = {
    "test_fixture_refresh",
    "non_authority_doc_typo",
    "validator_routing_metadata",
    "alert_wording_or_dedupe",
    "cron_freshness_expected_artifact_non_authority",
}

FORBIDDEN_TARGET_PATTERNS = [
    "SOUL.md",
    "AGENTS.md",
    "TOOLS.md",
    "MEMORY.md",
    "03. Portfolio/",
    "state/finance/",
    "data/finance/universe-v1.json",
    ".openclaw/openclaw.json",
    "credentials",
    "secrets",
]

PATCHABLE_TITLE_RULES = [
    {
        "needle": "model_path",
        "risk_class": "implementation_metadata_patch",
        "targets": [
            "scripts/concurrent_lane_manager.py",
            "scripts/model_run_ledger.py",
            "scripts/coding_outcome_ledger.py",
        ],
        "tests": [
            "python scripts\\test_concurrent_lane_manager_runtime_metadata.py",
            "python scripts\\test_model_run_ledger.py",
            "python scripts\\test_coding_outcome_ledger.py",
        ],
        "scope": "Stamp model/run metadata on producers that already expose runtime metadata.",
    },
    {
        "needle": "validator drag",
        "risk_class": "validator_routing_metadata",
        "targets": [
            "scripts/changed_file_validator_router.py",
            "scripts/validator_timing_ledger.py",
        ],
        "tests": [
            "python scripts\\changed_file_validator_router.py --write --validate",
            "python scripts\\validator_timing_ledger.py --profile normal --write --validate",
        ],
        "scope": "Reduce normal validator drag while preserving shared/major proof gates.",
    },
    {
        "needle": "alert",
        "risk_class": "alert_wording_or_dedupe",
        "targets": [
            "scripts/wf74_learning_loop_telegram_digest.py",
            "scripts/wf74_learning_loop_telegram_cron_runner.py",
        ],
        "tests": [
            "python scripts\\test_wf74_learning_loop_telegram_digest.py",
            "python scripts\\wf74_learning_loop_telegram_cron_runner.py --dry-run --write --validate",
        ],
        "scope": "Improve digest wording, dedupe, and operator context without changing delivery authority.",
    },
]

CATEGORY_ROUTE = {
    "code_mutation": "patch_plan",
    "skill_application": "skill_workshop_request",
    "collector_config": "owner_config_decision",
    "finance_mutation": "finance_repair_review",
    "execution": "execution_guardrail_review",
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


def stable_id(*parts: Any) -> str:
    seed = "|".join(str(part or "") for part in parts)
    return hashlib.sha256(seed.encode("utf-8")).hexdigest()[:12]


def normalize_path(value: Any) -> str:
    return str(value or "").strip().replace("\\", "/").lstrip("./")


def target_forbidden(path: str) -> bool:
    normalized = normalize_path(path).lower()
    for pattern in FORBIDDEN_TARGET_PATTERNS:
        if pattern.lower() in normalized:
            return True
    return False


def proposal_rows(packet: dict[str, Any]) -> list[dict[str, Any]]:
    return [row for row in as_list(packet.get("proposals")) if isinstance(row, dict)]


def opportunity_rows(packet: dict[str, Any]) -> list[dict[str, Any]]:
    return [row for row in as_list(packet.get("opportunities")) if isinstance(row, dict)]


def opportunity_by_id(queue: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(row.get("opportunity_id")): row for row in opportunity_rows(queue)}


def title_rule(title: str) -> dict[str, Any] | None:
    lowered = title.lower()
    for rule in PATCHABLE_TITLE_RULES:
        if rule["needle"] in lowered:
            return rule
    return None


def base_plan(proposal: dict[str, Any], route: str, opportunity: dict[str, Any]) -> dict[str, Any]:
    title = str(proposal.get("title") or opportunity.get("title") or "WF74 improvement proposal")
    category = str(proposal.get("category") or opportunity.get("category") or "unknown")
    return {
        "schema": "veritas.wf74_auto_patch_plan.v1",
        "plan_id": f"wf74-auto-patch-{stable_id(proposal.get('proposal_id'), title, route)}",
        "source_proposal_id": proposal.get("proposal_id"),
        "source_opportunity_id": proposal.get("source_opportunity_id") or opportunity.get("opportunity_id"),
        "category": category,
        "route": route,
        "priority": proposal.get("priority") or opportunity.get("priority"),
        "title": title,
        "problem": proposal.get("problem") or opportunity.get("signal"),
        "expected_benefit": proposal.get("expected_benefit"),
        "evidence": proposal.get("evidence") or opportunity.get("evidence"),
        "authority_boundary": AUTHORITY_BOUNDARY.copy(),
    }


def patch_plan(proposal: dict[str, Any], opportunity: dict[str, Any]) -> dict[str, Any]:
    plan = base_plan(proposal, "patch_plan", opportunity)
    rule = title_rule(str(plan.get("title") or ""))
    if rule:
        risk_class = rule["risk_class"]
        targets = list(rule["targets"])
        tests = list(rule["tests"])
        scope = rule["scope"]
    else:
        risk_class = "main_review_patch_required"
        targets = []
        tests = [str(proposal.get("validation_command") or opportunity.get("validation_command") or "python scripts\\changed_file_validator_router.py --write --validate")]
        scope = "Main-session inspection required before any patch target is selected."
    forbidden_targets = [target for target in targets if target_forbidden(target)]
    auto_apply_class = risk_class if risk_class in SAFE_AUTO_APPLY_CLASSES else None
    auto_apply_eligible = False
    plan.update({
        "risk_class": risk_class,
        "scope": scope,
        "target_files": targets,
        "forbidden_target_files": forbidden_targets,
        "auto_apply_class": auto_apply_class,
        "auto_apply_eligible": auto_apply_eligible,
        "patch_apply_allowed": False,
        "requires_owner_approval": bool(forbidden_targets or not auto_apply_class),
        "required_lane_contract": {
            "lease_required": True,
            "allowed_writes": targets or ["exact target files must be selected by main session first"],
            "read_first": [
                "tmp/wf74-improvement-opportunity-queue.json",
                "tmp/wf74-reflection-to-proposal-autopilot.json",
                "tmp/wf74-auto-patch-proposer.json",
            ],
        },
        "validation_commands": [
            *tests,
            "python scripts\\changed_file_validator_router.py --write --validate",
            "python scripts\\wf74_rsi.py --validate-only",
        ],
        "rollback_plan": "Use git diff plus the lane proof artifacts to revert the exact scoped patch if validation regresses.",
        "next_safe_action": (
            "Open a scoped implementation lane for this patch plan; do not apply from the proposer artifact."
        ),
    })
    return plan


def skill_request(proposal: dict[str, Any], opportunity: dict[str, Any]) -> dict[str, Any]:
    plan = base_plan(proposal, "skill_workshop_request", opportunity)
    title = str(plan.get("title") or "WF74 skill update")
    suggested_skill = "veritas-self-improvement"
    if "cron" in title.lower() or "alert" in title.lower():
        suggested_skill = "cron-automation-manager"
    elif "implementation" in title.lower() or "validator" in title.lower():
        suggested_skill = "disciplined-implementation"
    plan.update({
        "suggested_skill": suggested_skill,
        "skill_workshop_action": "update",
        "skill_application_allowed": False,
        "proposal_apply_allowed": False,
        "description": f"WF74 gated auto-improvement procedure for {suggested_skill}",
        "goal": title,
        "evidence": {
            "source_proposal_id": proposal.get("proposal_id"),
            "source_opportunity_id": plan.get("source_opportunity_id"),
            "category": plan.get("category"),
            "wf74_evidence": plan.get("evidence"),
        },
        "proposal_content_outline": [
            "Add a bounded WF74 auto-patch proposer procedure.",
            "Require lane leases and exact target files before code changes.",
            "Generate Skill Workshop proposals automatically, but keep apply owner-gated.",
            "Preserve blocks on doctrine, finance canon, collector config, execution, credentials, and owner approval inference.",
        ],
        "validation_commands": [
            "openclaw skills check",
            "python scripts\\wf74_auto_patch_proposer.py --write --write-md --validate",
            "python scripts\\wf74_rsi.py --validate-only",
        ],
        "next_safe_action": "Create or update a Skill Workshop proposal; do not apply the skill unless Randall explicitly approves that proposal.",
    })
    return plan


def owner_config_decision(proposal: dict[str, Any], opportunity: dict[str, Any]) -> dict[str, Any]:
    plan = base_plan(proposal, "owner_config_decision", opportunity)
    plan.update({
        "config_mutation_allowed": False,
        "patch_apply_allowed": False,
        "requires_owner_approval": True,
        "required_artifacts_before_any_change": [
            "tmp/otel-critical-review-decision-packet.json",
            "tmp/otel-field-depth-limited-owner-packet.json",
            "tmp/otel-ops-control.json",
        ],
        "validation_commands": [
            "python scripts\\otel_ops_control.py --write --write-db --multi-window --validate",
            "python scripts\\wf74_auto_patch_proposer.py --write --write-md --validate",
        ],
        "next_safe_action": "Review owner decision packet; keep collector config unchanged unless explicitly approved with rollback/privacy proof.",
    })
    return plan


def finance_repair_review(proposal: dict[str, Any], opportunity: dict[str, Any]) -> dict[str, Any]:
    plan = base_plan(proposal, "finance_repair_review", opportunity)
    plan.update({
        "finance_mutation_allowed": False,
        "patch_apply_allowed": False,
        "requires_owner_approval": True,
        "required_artifacts_before_any_change": [
            "tmp/finance-response-quality-slice.json",
            "tmp/finance-response-quality-repair-loop.json",
            "tmp/trade-grade-repair-conveyor.json",
        ],
        "validation_commands": [
            "python scripts\\finance_response_quality_slice.py --write --write-md --validate",
            "python scripts\\finance_response_quality_repair_loop.py --write --validate",
        ],
        "next_safe_action": "Treat as finance repair/proposal only; no canon, portfolio, capital, or execution mutation from WF74.",
    })
    return plan


def execution_guardrail_review(proposal: dict[str, Any], opportunity: dict[str, Any]) -> dict[str, Any]:
    plan = base_plan(proposal, "execution_guardrail_review", opportunity)
    plan.update({
        "execution_allowed": False,
        "patch_apply_allowed": False,
        "requires_exact_owner_approval": True,
        "required_artifacts_before_any_action": [
            "fresh WF63/WF67 paper-only guard proof",
            "exact owner-approved order/request artifact",
            "kill switch and audit/redaction proof",
        ],
        "validation_commands": [
            "python scripts\\cron_control_packet.py --write --validate",
        ],
        "next_safe_action": "Keep execution blocked unless a separate exact owner approval and fresh paper-only guard path exist.",
    })
    return plan


def build_plan_for_proposal(proposal: dict[str, Any], opportunities: dict[str, dict[str, Any]]) -> dict[str, Any]:
    opportunity = opportunities.get(str(proposal.get("source_opportunity_id"))) or {}
    category = str(proposal.get("category") or opportunity.get("category") or "code_mutation")
    route = CATEGORY_ROUTE.get(category, "patch_plan")
    if route == "patch_plan":
        return patch_plan(proposal, opportunity)
    if route == "skill_workshop_request":
        return skill_request(proposal, opportunity)
    if route == "owner_config_decision":
        return owner_config_decision(proposal, opportunity)
    if route == "finance_repair_review":
        return finance_repair_review(proposal, opportunity)
    if route == "execution_guardrail_review":
        return execution_guardrail_review(proposal, opportunity)
    return patch_plan(proposal, opportunity)


def build_payload(queue: dict[str, Any], proposals: dict[str, Any], limit: int) -> dict[str, Any]:
    opportunities = opportunity_by_id(queue)
    rows = proposal_rows(proposals)[:limit]
    plans = [build_plan_for_proposal(row, opportunities) for row in rows]
    route_counts: dict[str, int] = {}
    risk_counts: dict[str, int] = {}
    for plan in plans:
        route = str(plan.get("route") or "unknown")
        risk = str(plan.get("risk_class") or route)
        route_counts[route] = route_counts.get(route, 0) + 1
        risk_counts[risk] = risk_counts.get(risk, 0) + 1
    patch_plans = [plan for plan in plans if plan.get("route") == "patch_plan"]
    skill_requests = [plan for plan in plans if plan.get("route") == "skill_workshop_request"]
    auto_apply_candidates = [plan for plan in patch_plans if plan.get("auto_apply_eligible")]
    payload = {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "ok",
        "purpose": "Generate gated WF74 code patch plans and Skill Workshop update requests from reflection proposals.",
        "source_artifacts": {
            "opportunity_queue": rel(DEFAULT_QUEUE),
            "proposal_autopilot": rel(DEFAULT_PROPOSALS),
        },
        "summary": {
            "proposal_source_status": proposals.get("status"),
            "input_proposal_count": len(rows),
            "plan_count": len(plans),
            "patch_plan_count": len(patch_plans),
            "skill_workshop_request_count": len(skill_requests),
            "owner_gated_plan_count": sum(1 for plan in plans if plan.get("requires_owner_approval") or plan.get("requires_exact_owner_approval")),
            "auto_apply_candidate_count": len(auto_apply_candidates),
            "auto_apply_count": 0,
            "by_route": dict(sorted(route_counts.items())),
            "by_risk_class": dict(sorted(risk_counts.items())),
            "next_safe_action": "Review generated patch plans; open scoped implementation lanes or Skill Workshop proposals, but do not apply from this artifact.",
        },
        "safe_auto_apply_classes": sorted(SAFE_AUTO_APPLY_CLASSES),
        "patch_plans": patch_plans,
        "skill_workshop_requests": skill_requests,
        "owner_gated_reviews": [plan for plan in plans if plan.get("route") not in {"patch_plan", "skill_workshop_request"}],
        "blocked_actions": [
            "no direct code mutation",
            "no skill apply/install/update from this artifact",
            "no collector/runtime/cron config mutation",
            "no finance canon/portfolio/cash/sizing/risk mutation",
            "no paper/live/brokerage/account action",
            "no owner approval inference",
        ],
        "authority_boundary": AUTHORITY_BOUNDARY.copy(),
    }
    payload["validation"] = validate_payload(payload)
    if payload["validation"]["status"] == "error":
        payload["status"] = "blocked"
    return payload


def validate_payload(payload: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    boundary = as_dict(payload.get("authority_boundary"))
    for key, expected in AUTHORITY_BOUNDARY.items():
        if boundary.get(key) is not expected:
            errors.append(f"authority_boundary_{key}_not_{str(expected).lower()}")
    summary = as_dict(payload.get("summary"))
    if int(summary.get("auto_apply_count") or 0) != 0:
        errors.append("auto_apply_count_must_remain_zero")
    for plan in [*as_list(payload.get("patch_plans")), *as_list(payload.get("skill_workshop_requests")), *as_list(payload.get("owner_gated_reviews"))]:
        plan_dict = as_dict(plan)
        if plan_dict.get("patch_apply_allowed") is True:
            errors.append(f"patch_apply_allowed_true:{plan_dict.get('plan_id')}")
        if plan_dict.get("skill_application_allowed") is True:
            errors.append(f"skill_application_allowed_true:{plan_dict.get('plan_id')}")
        for target in as_list(plan_dict.get("target_files")):
            if target_forbidden(str(target)):
                errors.append(f"forbidden_target_file:{plan_dict.get('plan_id')}:{target}")
    if not as_list(payload.get("patch_plans")) and not as_list(payload.get("skill_workshop_requests")):
        warnings.append("no_code_or_skill_plans_generated")
    return {"status": "error" if errors else "warning" if warnings else "ok", "errors": errors, "warnings": warnings}


def render_md(payload: dict[str, Any]) -> str:
    summary = as_dict(payload.get("summary"))
    lines = [
        "# WF74 Auto Patch Proposer",
        "",
        f"- Generated: {payload.get('generated_at_utc')}",
        f"- Status: {payload.get('status')}",
        f"- Plans: {summary.get('plan_count')}",
        f"- Patch plans: {summary.get('patch_plan_count')}",
        f"- Skill Workshop requests: {summary.get('skill_workshop_request_count')}",
        f"- Auto-apply count: {summary.get('auto_apply_count')}",
        "",
        "## Patch Plans",
    ]
    for plan in as_list(payload.get("patch_plans")):
        lines.append(f"- {plan.get('priority')} | {plan.get('risk_class')} | {plan.get('title')}")
    lines.extend(["", "## Skill Workshop Requests"])
    for req in as_list(payload.get("skill_workshop_requests")):
        lines.append(f"- {req.get('priority')} | {req.get('suggested_skill')} | {req.get('title')}")
    lines.extend(["", "## Blocked Actions"])
    for item in as_list(payload.get("blocked_actions")):
        lines.append(f"- {item}")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--queue", type=Path, default=DEFAULT_QUEUE)
    parser.add_argument("--proposals", type=Path, default=DEFAULT_PROPOSALS)
    parser.add_argument("--json-out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--write-md", action="store_true")
    parser.add_argument("--validate", action="store_true")
    args = parser.parse_args(argv)

    queue_path = args.queue if args.queue.is_absolute() else ROOT / args.queue
    proposal_path = args.proposals if args.proposals.is_absolute() else ROOT / args.proposals
    out = args.json_out if args.json_out.is_absolute() else ROOT / args.json_out
    queue = as_dict(load_json_artifact(queue_path))
    proposals = as_dict(load_json_artifact(proposal_path))
    payload = build_payload(queue, proposals, args.limit)
    if args.write:
        atomic_write_json(out, payload)
        if args.write_md:
            atomic_write_text(out.with_suffix(".md") if out != DEFAULT_OUT else DEFAULT_MD, render_md(payload))
    else:
        print(json.dumps(payload, indent=2))
    print(
        "status={status} validation={validation} plans={plans} patch_plans={patches} skill_requests={skills} auto_apply={auto_apply}".format(
            status=payload["status"],
            validation=payload["validation"]["status"],
            plans=payload["summary"]["plan_count"],
            patches=payload["summary"]["patch_plan_count"],
            skills=payload["summary"]["skill_workshop_request_count"],
            auto_apply=payload["summary"]["auto_apply_count"],
        )
    )
    if args.validate and payload["validation"]["status"] == "error":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
