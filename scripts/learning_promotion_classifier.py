#!/usr/bin/env python3
"""Classify learning-loop findings into safe promotion candidates.

This is a review-only conveyor between WF74/WF88 scorecards and durable
operating surfaces. It generates candidate routes for Skill Workshop proposals,
daily memory append previews, PM implementation jobs, validator gaps, owner
decisions, monitor-only rows, and no-op guardrails.

It does not apply skills, append memory, mutate cron/runtime/config, change
finance canon or portfolio state, or infer owner approval.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, load_json_artifact


ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
OUT = TMP / "learning-promotion-candidates.json"
SCHEMA = "veritas.learning_promotion_candidates.v1"

ACTIONABLE_QUEUE = TMP / "actionable-improvement-queue.json"
WF74_DOCKET = TMP / "wf74-decision-docket.json"
WF88_WIKI = TMP / "wf88-wiki-synthesis-packet.json"
AUTO_PATCH = TMP / "wf74-auto-patch-proposer.json"
IMPROVEMENT_LEDGER = TMP / "improvement-ledger-current.json"
MODEL_QUALITY = TMP / "model-quality-scorecard.json"
TOKEN_EFFICIENCY = TMP / "token-efficiency-scorecard.json"
IMPLEMENTATION_TOKEN_BRIDGE = TMP / "implementation-token-attribution-bridge.json"
RECOMMENDATION_LEDGER = TMP / "recommendation-outcome-ledger-current.json"

PROMOTION_TARGETS = {
    "no_op",
    "monitor_only",
    "daily_memory_append",
    "skill_workshop_proposal",
    "pm_implementation_job",
    "validator_gap",
    "owner_decision",
}

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "proposal_generation_only": True,
    "routes_existing_artifacts": True,
    "direct_memory_write_allowed": False,
    "direct_skill_write_allowed": False,
    "skill_application_allowed": False,
    "auto_apply_allowed": False,
    "code_mutation_allowed": False,
    "cron_schedule_mutation_allowed": False,
    "runtime_config_mutation_allowed": False,
    "finance_canon_or_portfolio_mutation_allowed": False,
    "cash_sizing_risk_mutation_allowed": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "external_delivery_allowed": False,
    "owner_approval_inferred": False,
}

BLOCKED_ACTIONS = [
    "No direct memory writes from this classifier.",
    "No direct skill edits or Skill Workshop apply/install/quarantine.",
    "No code patch application from this classifier.",
    "No cron schedule/config/runtime mutation.",
    "No finance canon, portfolio, cash, sizing, risk, paper/live, brokerage, or account mutation.",
    "No external delivery or owner approval inference.",
]

SKILL_ROUTE_BY_TOPIC = {
    "cron": "cron-automation-manager",
    "token": "disciplined-implementation",
    "implementation": "disciplined-implementation",
    "validator": "disciplined-implementation",
    "memory": "memory-continuity-manager",
    "content_capture": "automation-hardening-manager",
    "execution": "automation-hardening-manager",
    "finance": "veritas-response-contract",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def load(path: Path) -> dict[str, Any]:
    return as_dict(load_json_artifact(path))


def norm(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(value or "").lower()).strip()


def stable_id(*parts: Any) -> str:
    seed = "|".join(str(part or "") for part in parts)
    return hashlib.sha256(seed.encode("utf-8")).hexdigest()[:12]


def source_state(path: Path, payload: dict[str, Any]) -> dict[str, Any]:
    validation = as_dict(payload.get("validation"))
    return {
        "path": rel(path),
        "present": path.exists(),
        "generated_at_utc": payload.get("generated_at_utc"),
        "status": payload.get("status"),
        "validation_status": validation.get("status"),
    }


def safe_priority(value: Any, default: int = 50) -> int:
    try:
        return int(value)
    except Exception:
        return default


def choose_skill(category: str, title: str) -> str:
    text = f"{category} {title}".lower()
    for key, skill in SKILL_ROUTE_BY_TOPIC.items():
        if key in text:
            return skill
    return "veritas-self-improvement"


def candidate(
    *,
    source_artifact: Path,
    source_type: str,
    source_id: Any,
    title: str,
    target: str,
    priority: int,
    reason: str,
    proposed_action: str,
    evidence_paths: list[str] | None = None,
    skill_name: str | None = None,
    memory_append: dict[str, Any] | None = None,
    stop_lines: list[str] | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "schema": "veritas.learning_promotion_candidate.v1",
        "candidate_id": f"lpc-{stable_id(source_type, source_id, title, target)}",
        "source_artifact": rel(source_artifact),
        "source_type": source_type,
        "source_id": source_id,
        "title": title,
        "promotion_target": target,
        "priority": priority,
        "reason": reason,
        "proposed_action": proposed_action,
        "evidence_paths": evidence_paths or [rel(source_artifact)],
        "suggested_skill": skill_name,
        "memory_append": memory_append,
        "requires_owner_approval": target in {"owner_decision"},
        "requires_skill_workshop": target == "skill_workshop_proposal",
        "direct_apply_allowed": False,
        "direct_memory_write_allowed": False,
        "direct_skill_write_allowed": False,
        "blocked_actions": BLOCKED_ACTIONS,
        "stop_lines": stop_lines or BLOCKED_ACTIONS,
        "metadata": metadata or {},
    }


def classify_actionable_item(item: dict[str, Any]) -> dict[str, Any]:
    title = str(item.get("title") or item.get("item_id") or "actionable improvement")
    category = str(item.get("category") or "unknown")
    action_class = str(item.get("action_class") or "")
    text = " ".join([
        title.lower(),
        category.lower(),
        action_class.lower(),
        str(item.get("next_action") or "").lower(),
        str(item.get("ledger_decision") or "").lower(),
    ])
    priority = safe_priority(item.get("priority"))
    evidence = [path for path in as_list(item.get("proof_artifacts")) if isinstance(path, str)] or [rel(ACTIONABLE_QUEUE)]
    metadata = {
        "destination": item.get("destination"),
        "destination_id": item.get("destination_id"),
        "sla_status": item.get("sla_status"),
        "monitor_only": item.get("monitor_only"),
    }

    if item.get("requires_owner_decision"):
        return candidate(
            source_artifact=ACTIONABLE_QUEUE,
            source_type="actionable_improvement",
            source_id=item.get("item_id"),
            title=title,
            target="owner_decision",
            priority=priority,
            reason="Actionable row is explicitly owner-gated.",
            proposed_action="Keep in owner review; do not convert the row into apply or execution authority.",
            evidence_paths=evidence,
            metadata=metadata,
        )
    if item.get("is_orphan") or as_list(item.get("missing_contract_fields")):
        return candidate(
            source_artifact=ACTIONABLE_QUEUE,
            source_type="actionable_improvement",
            source_id=item.get("item_id"),
            title=title,
            target="validator_gap",
            priority=max(priority, 80),
            reason="Actionable row lacks a complete destination/proof contract.",
            proposed_action="Repair the routing/validator contract before any promotion.",
            evidence_paths=evidence,
            metadata={**metadata, "missing_contract_fields": item.get("missing_contract_fields")},
        )
    if "cron" in text and ("dry-run" in text or "migration" in text or action_class == "wf74_fix_now"):
        return candidate(
            source_artifact=ACTIONABLE_QUEUE,
            source_type="actionable_improvement",
            source_id=item.get("item_id"),
            title=title,
            target="pm_implementation_job",
            priority=max(priority, 75),
            reason="Cron learning signal needs a dry-run repair plan, not live schedule mutation.",
            proposed_action="Open a PM/lane candidate that produces dry-run contract validation, rollback notes, and post-change freshness proof.",
            evidence_paths=evidence,
            metadata=metadata,
        )
    if "token" in text or "attribution" in text:
        return candidate(
            source_artifact=ACTIONABLE_QUEUE,
            source_type="actionable_improvement",
            source_id=item.get("item_id"),
            title=title,
            target="pm_implementation_job",
            priority=max(priority, 75),
            reason="Token/implementation attribution is a measurable implementation repair candidate.",
            proposed_action="Prepare metadata-only implementation work; keep raw prompt, response, and tool payload capture blocked.",
            evidence_paths=evidence,
            metadata=metadata,
        )
    if category in {"execution", "content_capture_boundary"} or "proposal-only" in text or "raw content capture" in text:
        return candidate(
            source_artifact=ACTIONABLE_QUEUE,
            source_type="actionable_improvement",
            source_id=item.get("item_id"),
            title=title,
            target="skill_workshop_proposal",
            priority=priority,
            reason="Repeated guardrail should be routable as a Skill Workshop proposal if it is not already covered.",
            proposed_action="Draft or update a skill proposal only after main review confirms the rule is not already captured.",
            evidence_paths=evidence,
            skill_name=choose_skill(category, title),
            metadata=metadata,
        )
    if action_class == "market_session_accrual":
        return candidate(
            source_artifact=ACTIONABLE_QUEUE,
            source_type="actionable_improvement",
            source_id=item.get("item_id"),
            title=title,
            target="monitor_only",
            priority=priority,
            reason="Market-session evidence needs continued accrual, not implementation.",
            proposed_action="Keep collecting proof and block readiness/execution claims until maturity gates clear.",
            evidence_paths=evidence,
            metadata=metadata,
        )
    if item.get("monitor_only"):
        return candidate(
            source_artifact=ACTIONABLE_QUEUE,
            source_type="actionable_improvement",
            source_id=item.get("item_id"),
            title=title,
            target="monitor_only",
            priority=priority,
            reason="Current action row is explicitly monitor-only.",
            proposed_action=str(item.get("next_action") or "Refresh proof and escalate only if severity, SLA, or proof state worsens."),
            evidence_paths=evidence,
            metadata=metadata,
        )
    return candidate(
        source_artifact=ACTIONABLE_QUEUE,
        source_type="actionable_improvement",
        source_id=item.get("item_id"),
        title=title,
        target="no_op",
        priority=priority,
        reason="No safe promotion route is currently indicated.",
        proposed_action="Leave as routed; refresh the source queue if the evidence changes.",
        evidence_paths=evidence,
        metadata=metadata,
    )


def classify_wiki_action(item: dict[str, Any]) -> dict[str, Any]:
    item_id = str(item.get("id") or item.get("title") or "wiki-action")
    title = item_id.replace("-", " ")
    state = str(item.get("state") or "")
    next_action = str(item.get("next_action") or "")
    command = str(item.get("command") or "")
    priority = 80 if state in {"repair_required", "followup_required"} else 70 if state == "review_ready" else 45
    target = "monitor_only"
    reason = "Wiki action is active review context."
    proposed = next_action or "Refresh the source proof packet."

    if state == "repair_required":
        target = "pm_implementation_job"
        reason = "Wiki synthesis marks this item repair-required."
    elif state == "review_ready":
        target = "pm_implementation_job"
        reason = "Wiki synthesis marks this item review-ready for a bounded implementation candidate."
    elif state == "followup_required":
        target = "validator_gap"
        reason = "Follow-up debt needs a durable routing/proof closure before it disappears from summaries."
    elif state in {"clean"}:
        target = "no_op"
        reason = "Wiki synthesis marks this guardrail clean."
        proposed = "Keep the guardrail visible; no action unless a source packet regresses."
    elif state in {"pilot_not_mature", "monitor"}:
        target = "monitor_only"
        reason = "Evidence is not mature enough for promotion."

    return candidate(
        source_artifact=WF88_WIKI,
        source_type="wf88_wiki_action",
        source_id=item_id,
        title=title,
        target=target,
        priority=priority,
        reason=reason,
        proposed_action=proposed,
        evidence_paths=[rel(WF88_WIKI), command] if command else [rel(WF88_WIKI)],
        metadata={"state": state, "owner_workflow": item.get("owner_workflow"), "stop_line": item.get("stop_line")},
    )


def classify_scorecards(inputs: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    bridge = inputs["implementation_token_bridge"]
    bridge_summary = as_dict(bridge.get("summary"))
    token_gap = safe_priority(bridge_summary.get("implementation_token_gap_count"), default=0)
    if token_gap > 0:
        results.append(candidate(
            source_artifact=IMPLEMENTATION_TOKEN_BRIDGE,
            source_type="scorecard",
            source_id="implementation_token_gap",
            title="Close implementation token attribution gap",
            target="pm_implementation_job",
            priority=88,
            reason=f"Implementation token attribution gap remains open ({token_gap}).",
            proposed_action="Prepare metadata-only stamping/join repair; do not capture raw prompts, responses, tool payloads, secrets, or headers.",
            evidence_paths=[rel(IMPLEMENTATION_TOKEN_BRIDGE), rel(TOKEN_EFFICIENCY)],
            metadata={"implementation_token_gap_count": token_gap},
        ))

    token_efficiency = inputs["token_efficiency"]
    token_summary = as_dict(token_efficiency.get("summary"))
    api_candidates = safe_priority(token_summary.get("api_call_reduction_candidate_count"), default=0)
    prompt_candidates = safe_priority(token_summary.get("prompt_compression_candidate_count"), default=0)
    if api_candidates or prompt_candidates:
        results.append(candidate(
            source_artifact=TOKEN_EFFICIENCY,
            source_type="scorecard",
            source_id="token_efficiency_candidates",
            title="Review token-heavy cron/API-call candidates",
            target="pm_implementation_job",
            priority=78,
            reason="Token efficiency scorecard found review-ready reduction candidates.",
            proposed_action="Pick one changed-only prefilter or prompt-compression candidate for a separate validated patch; no cron schedule mutation.",
            evidence_paths=[rel(TOKEN_EFFICIENCY)],
            metadata={
                "api_call_reduction_candidate_count": api_candidates,
                "prompt_compression_candidate_count": prompt_candidates,
                "top_candidate": token_summary.get("top_candidate"),
            },
        ))

    model_quality = inputs["model_quality"]
    model_validation = as_dict(model_quality.get("validation"))
    if str(model_validation.get("status") or "").lower() in {"critical", "error", "blocked"}:
        results.append(candidate(
            source_artifact=MODEL_QUALITY,
            source_type="scorecard",
            source_id="model_quality_validation",
            title="Repair model-quality scorecard critical finding",
            target="validator_gap",
            priority=90,
            reason="Model quality scorecard validation is not clean.",
            proposed_action="Route the exact critical finding into its owner repair conveyor before making model-quality claims.",
            evidence_paths=[rel(MODEL_QUALITY)],
            metadata={"validation": model_validation},
        ))

    improvement = inputs["improvement_ledger"]
    improvement_summary = as_dict(improvement.get("summary"))
    followups = safe_priority(improvement_summary.get("followup_required_open_count"), default=0)
    if followups > 0:
        results.append(candidate(
            source_artifact=IMPROVEMENT_LEDGER,
            source_type="scorecard",
            source_id="followup_required_open_improvements",
            title="Route follow-up-required open improvements",
            target="validator_gap",
            priority=82,
            reason=f"Improvement ledger still has {followups} follow-up-required open rows.",
            proposed_action="Use the actionable queue/no-orphan validator to ensure every row has a destination, proof command, and close condition.",
            evidence_paths=[rel(IMPROVEMENT_LEDGER), rel(ACTIONABLE_QUEUE)],
            metadata={"followup_required_open_count": followups},
        ))

    recommendation = inputs["recommendation_ledger"]
    recommendation_validation = as_dict(recommendation.get("validation"))
    if safe_priority(recommendation_validation.get("warning"), default=0) > 0:
        results.append(candidate(
            source_artifact=RECOMMENDATION_LEDGER,
            source_type="scorecard",
            source_id="recommendation_outcome_warning",
            title="Grade mature recommendation outcomes",
            target="monitor_only",
            priority=55,
            reason="Recommendation ledger has warning residue but no apply authority.",
            proposed_action="Continue outcome grading before making decision-quality or model-performance claims.",
            evidence_paths=[rel(RECOMMENDATION_LEDGER)],
            metadata={"validation": recommendation_validation},
        ))
    return results


def maybe_memory_candidate(date: str, candidates: list[dict[str, Any]]) -> dict[str, Any]:
    pm_count = sum(1 for row in candidates if row.get("promotion_target") == "pm_implementation_job")
    skill_count = sum(1 for row in candidates if row.get("promotion_target") == "skill_workshop_proposal")
    validator_count = sum(1 for row in candidates if row.get("promotion_target") == "validator_gap")
    preview = (
        f"Learning promotion review packet generated review-only: "
        f"{pm_count} PM candidates, {skill_count} Skill Workshop candidates, "
        f"{validator_count} validator gaps; direct apply/memory/skill writes remain blocked."
    )
    return candidate(
        source_artifact=OUT,
        source_type="operator_memory_preview",
        source_id=f"learning-promotion-{date}",
        title="Learning promotion review packet generated",
        target="daily_memory_append",
        priority=40,
        reason="Compact continuity note requested by caller; preview only until explicitly appended by the lane owner.",
        proposed_action="Append the preview to the canonical daily note only after validation succeeds and duplicate guard passes.",
        evidence_paths=[rel(OUT), rel(TMP / "learning-promotion-review-packet.json")],
        memory_append={
            "target_path": f"memory/{date}.md",
            "duplicate_guard_phrase": "Learning promotion review packet generated review-only",
            "append_preview": preview,
        },
    )


def dedupe(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_id: dict[str, dict[str, Any]] = {}
    for row in candidates:
        by_id[str(row.get("candidate_id"))] = row
    return sorted(
        by_id.values(),
        key=lambda row: (
            {
                "owner_decision": 0,
                "validator_gap": 1,
                "pm_implementation_job": 2,
                "skill_workshop_proposal": 3,
                "daily_memory_append": 4,
                "monitor_only": 5,
                "no_op": 6,
            }.get(str(row.get("promotion_target")), 7),
            -safe_priority(row.get("priority")),
            str(row.get("title") or ""),
        ),
    )


def load_inputs() -> dict[str, dict[str, Any]]:
    return {
        "actionable_queue": load(ACTIONABLE_QUEUE),
        "wf74_docket": load(WF74_DOCKET),
        "wf88_wiki": load(WF88_WIKI),
        "auto_patch": load(AUTO_PATCH),
        "improvement_ledger": load(IMPROVEMENT_LEDGER),
        "model_quality": load(MODEL_QUALITY),
        "token_efficiency": load(TOKEN_EFFICIENCY),
        "implementation_token_bridge": load(IMPLEMENTATION_TOKEN_BRIDGE),
        "recommendation_ledger": load(RECOMMENDATION_LEDGER),
    }


def classify_signals(
    inputs: dict[str, dict[str, Any]] | None = None,
    *,
    include_memory_candidate: bool = False,
    memory_date: str | None = None,
) -> dict[str, Any]:
    inputs = inputs or load_inputs()
    generated_at = utc_now()
    raw_candidates: list[dict[str, Any]] = []
    for item in as_list(inputs["actionable_queue"].get("action_items")):
        if isinstance(item, dict):
            raw_candidates.append(classify_actionable_item(item))
    for item in as_list(inputs["wf88_wiki"].get("action_items")):
        if isinstance(item, dict):
            raw_candidates.append(classify_wiki_action(item))
    raw_candidates.extend(classify_scorecards(inputs))
    candidates = dedupe(raw_candidates)
    if include_memory_candidate:
        date = memory_date or datetime.now(timezone.utc).date().isoformat()
        candidates = dedupe([*candidates, maybe_memory_candidate(date, candidates)])

    counts: dict[str, int] = {target: 0 for target in sorted(PROMOTION_TARGETS)}
    for row in candidates:
        counts[str(row.get("promotion_target"))] = counts.get(str(row.get("promotion_target")), 0) + 1
    packet = {
        "schema": SCHEMA,
        "generated_at_utc": generated_at,
        "status": "ok",
        "purpose": "Route learning-loop and scorecard findings into review-only durable promotion candidates.",
        "authority_boundary": AUTHORITY_BOUNDARY.copy(),
        "inputs": {
            "actionable_queue": source_state(ACTIONABLE_QUEUE, inputs["actionable_queue"]),
            "wf74_docket": source_state(WF74_DOCKET, inputs["wf74_docket"]),
            "wf88_wiki": source_state(WF88_WIKI, inputs["wf88_wiki"]),
            "auto_patch": source_state(AUTO_PATCH, inputs["auto_patch"]),
            "improvement_ledger": source_state(IMPROVEMENT_LEDGER, inputs["improvement_ledger"]),
            "model_quality": source_state(MODEL_QUALITY, inputs["model_quality"]),
            "token_efficiency": source_state(TOKEN_EFFICIENCY, inputs["token_efficiency"]),
            "implementation_token_bridge": source_state(IMPLEMENTATION_TOKEN_BRIDGE, inputs["implementation_token_bridge"]),
            "recommendation_ledger": source_state(RECOMMENDATION_LEDGER, inputs["recommendation_ledger"]),
        },
        "summary": {
            "candidate_count": len(candidates),
            "by_target": counts,
            "pm_implementation_job_count": counts.get("pm_implementation_job", 0),
            "skill_workshop_proposal_count": counts.get("skill_workshop_proposal", 0),
            "daily_memory_append_count": counts.get("daily_memory_append", 0),
            "validator_gap_count": counts.get("validator_gap", 0),
            "owner_decision_count": counts.get("owner_decision", 0),
            "direct_apply_count": sum(1 for row in candidates if row.get("direct_apply_allowed")),
            "direct_memory_write_count": sum(1 for row in candidates if row.get("direct_memory_write_allowed")),
            "direct_skill_write_count": sum(1 for row in candidates if row.get("direct_skill_write_allowed")),
            "next_safe_action": "Review the packet, then create separate PM jobs, Skill Workshop proposals, or daily-memory appends only where validated and owner-appropriate.",
        },
        "promotion_targets": sorted(PROMOTION_TARGETS),
        "candidates": candidates,
        "blocked_actions": BLOCKED_ACTIONS,
    }
    packet["validation"] = validate_packet(packet)
    if packet["validation"]["status"] == "blocked":
        packet["status"] = "blocked"
    elif packet["validation"]["status"] == "warning":
        packet["status"] = "warning"
    return packet


def validate_packet(packet: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    boundary = as_dict(packet.get("authority_boundary"))
    for key, expected in AUTHORITY_BOUNDARY.items():
        if boundary.get(key) is not expected:
            errors.append(f"authority_boundary_mismatch:{key}")
    for row in as_list(packet.get("candidates")):
        item = as_dict(row)
        target = str(item.get("promotion_target") or "")
        if target not in PROMOTION_TARGETS:
            errors.append(f"unknown_promotion_target:{item.get('candidate_id')}:{target}")
        if item.get("direct_apply_allowed"):
            errors.append(f"direct_apply_allowed:{item.get('candidate_id')}")
        if item.get("direct_memory_write_allowed"):
            errors.append(f"direct_memory_write_allowed:{item.get('candidate_id')}")
        if item.get("direct_skill_write_allowed"):
            errors.append(f"direct_skill_write_allowed:{item.get('candidate_id')}")
        if target == "skill_workshop_proposal" and not item.get("suggested_skill"):
            errors.append(f"skill_candidate_missing_skill:{item.get('candidate_id')}")
        if target == "daily_memory_append":
            memory = as_dict(item.get("memory_append"))
            target_path = str(memory.get("target_path") or "")
            if not re.fullmatch(r"memory/\d{4}-\d{2}-\d{2}\.md", target_path):
                errors.append(f"memory_candidate_bad_target:{item.get('candidate_id')}:{target_path}")
            if not memory.get("duplicate_guard_phrase") or not memory.get("append_preview"):
                errors.append(f"memory_candidate_missing_guard:{item.get('candidate_id')}")
    summary = as_dict(packet.get("summary"))
    if safe_priority(summary.get("owner_decision_count"), default=0) > 0:
        warnings.append(f"owner_decision_candidates:{summary.get('owner_decision_count')}")
    return {"status": "blocked" if errors else "warning" if warnings else "ok", "errors": errors, "warnings": warnings}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--json", action="store_true", dest="print_json")
    parser.add_argument("--out", type=Path, default=OUT)
    parser.add_argument("--include-memory-candidate", action="store_true")
    parser.add_argument("--memory-date")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    packet = classify_signals(include_memory_candidate=args.include_memory_candidate, memory_date=args.memory_date)
    out = args.out if args.out.is_absolute() else ROOT / args.out
    if args.write:
        atomic_write_json(out, packet)
    if args.print_json:
        print(json.dumps(packet, indent=2, sort_keys=True))
    else:
        summary = as_dict(packet.get("summary"))
        print(
            "status={status} validation={validation} candidates={candidates} pm_jobs={pm} skills={skills} memory={memory} validators={validators} direct_apply={apply}".format(
                status=packet.get("status"),
                validation=as_dict(packet.get("validation")).get("status"),
                candidates=summary.get("candidate_count"),
                pm=summary.get("pm_implementation_job_count"),
                skills=summary.get("skill_workshop_proposal_count"),
                memory=summary.get("daily_memory_append_count"),
                validators=summary.get("validator_gap_count"),
                apply=summary.get("direct_apply_count"),
            )
        )
    if args.validate and as_dict(packet.get("validation")).get("status") == "blocked":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
