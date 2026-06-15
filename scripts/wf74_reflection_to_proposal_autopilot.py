#!/usr/bin/env python3
"""Convert WF74 improvement opportunities into bounded review proposals.

This is an autopilot for proposal generation only. It never applies code,
skills, collector config, finance mutations, or execution actions.
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
QUEUE = TMP / "wf74-improvement-opportunity-queue.json"
OUT_JSON = TMP / "wf74-reflection-to-proposal-autopilot.json"
OUT_MD = OUT_JSON.with_suffix(".md")
SCHEMA = "veritas.wf74_reflection_to_proposal_autopilot.v1"

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "proposal_generation_only": True,
    "auto_apply_allowed": False,
    "code_mutation_allowed": False,
    "skill_application_allowed": False,
    "collector_config_mutation_allowed": False,
    "finance_canon_or_portfolio_mutation_allowed": False,
    "capital_deployment_allowed": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "money_movement_allowed": False,
    "owner_approval_inferred": False,
    "raw_prompt_or_response_capture_allowed": False,
    "tool_payload_capture_allowed": False,
}

CATEGORY_PROPOSAL_POSTURE = {
    "code_mutation": {
        "proposal_status": "main_review_required",
        "proposal_type": "implementation_patch_proposal",
        "review_owner": "Veritas main session",
        "blocked_apply_action": "No code mutation until a narrow implementation lane validates the exact patch.",
    },
    "skill_application": {
        "proposal_status": "skill_workshop_proposal_candidate",
        "proposal_type": "skill_workshop_proposal",
        "review_owner": "Skill Workshop / owner",
        "blocked_apply_action": "No skill apply/install/update unless Randall explicitly approves a specific proposal.",
    },
    "collector_config": {
        "proposal_status": "owner_decision_required",
        "proposal_type": "collector_config_review_packet",
        "review_owner": "Randall / OpenClaw operator",
        "blocked_apply_action": "No collector config, file exporter, logs pipeline, runtime config, or capture-depth change.",
    },
    "finance_mutation": {
        "proposal_status": "finance_repair_proposal_only",
        "proposal_type": "finance_quality_repair_proposal",
        "review_owner": "Veritas main session / Randall where gated",
        "blocked_apply_action": "No finance canon, portfolio, cash, sizing, risk, capital, or execution mutation from WF74.",
    },
    "execution": {
        "proposal_status": "exact_owner_approval_required",
        "proposal_type": "execution_guardrail_cadence",
        "review_owner": "Randall exact approval",
        "blocked_apply_action": "No paper/live submit, cancel, replace, sell, account action, or money movement.",
    },
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
    return hashlib.sha256(seed.encode("utf-8")).hexdigest()[:12]


def proposal_from_opportunity(row: dict[str, Any]) -> dict[str, Any]:
    category = str(row.get("category") or "unknown")
    posture = CATEGORY_PROPOSAL_POSTURE.get(category, CATEGORY_PROPOSAL_POSTURE["code_mutation"])
    proposal_id = f"wf74-proposal-{stable_id(row.get('opportunity_id'), row.get('title'), category)}"
    return {
        "schema": "veritas.wf74_reflection_proposal.v1",
        "proposal_id": proposal_id,
        "source_opportunity_id": row.get("opportunity_id"),
        "category": category,
        "proposal_type": posture["proposal_type"],
        "proposal_status": posture["proposal_status"],
        "review_owner": posture["review_owner"],
        "priority": row.get("priority"),
        "title": row.get("title"),
        "problem": row.get("signal"),
        "evidence": row.get("evidence"),
        "recommended_fix": row.get("recommended_action"),
        "expected_benefit": expected_benefit(category),
        "review_cadence": row.get("review_cadence"),
        "allowed_autonomous_actions": [
            "refresh proof",
            "rank opportunity",
            "generate proposal",
            "surface PM/cron review signal",
        ],
        "blocked_apply_action": posture["blocked_apply_action"],
        "requires_before_apply": row.get("requires_before_apply"),
        "validation_command": row.get("validation_command"),
        "authority_boundary": AUTHORITY_BOUNDARY.copy(),
    }


def expected_benefit(category: str) -> str:
    return {
        "code_mutation": "Higher attribution coverage, lower rework, and less validator drag after reviewed patches.",
        "skill_application": "Repeated procedure friction becomes reusable guidance instead of repeated rediscovery.",
        "collector_config": "Clear owner decision path for richer local metadata without accidental capture-depth expansion.",
        "finance_mutation": "Finance-quality gaps become repair packets while canon/portfolio/execution authority stays gated.",
        "execution": "Execution remains exact-approval-gated while approval-ready evidence stays organized.",
    }.get(category, "Improvement opportunity becomes explicit and reviewable.")


def build_payload(queue: dict[str, Any], limit: int) -> dict[str, Any]:
    opportunities = [row for row in as_list(queue.get("opportunities")) if isinstance(row, dict)]
    actionable = [row for row in opportunities if int(row.get("priority") or 0) >= 60]
    standing = [row for row in opportunities if int(row.get("priority") or 0) < 60 and row.get("category") == "execution"]
    selected = [*actionable[:limit], *standing[:1]]
    proposals = [proposal_from_opportunity(row) for row in selected]
    by_category: dict[str, int] = {}
    by_status: dict[str, int] = {}
    for proposal in proposals:
        by_category[proposal["category"]] = by_category.get(proposal["category"], 0) + 1
        by_status[proposal["proposal_status"]] = by_status.get(proposal["proposal_status"], 0) + 1
    payload = {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "ok",
        "purpose": "Autonomously generate bounded review proposals from WF74 improvement opportunities.",
        "source_artifacts": {
            "opportunity_queue": rel(QUEUE),
        },
        "summary": {
            "queue_status": queue.get("status"),
            "queue_opportunity_count": as_dict(queue.get("summary")).get("opportunity_count"),
            "proposal_count": len(proposals),
            "by_category": dict(sorted(by_category.items())),
            "by_status": dict(sorted(by_status.items())),
            "owner_decision_required_count": by_status.get("owner_decision_required", 0) + by_status.get("exact_owner_approval_required", 0),
            "auto_apply_count": 0,
            "next_safe_action": "Review proposals; only separately approved implementation/Skill Workshop/config/finance/execution gates may apply changes.",
        },
        "review_cadence": queue.get("review_cadence"),
        "proposals": proposals,
        "blocked_actions": [
            "no code mutation",
            "no skill application",
            "no collector config mutation",
            "no finance canon/portfolio/capital mutation",
            "no paper/live execution or account action",
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
    cadence = as_dict(payload.get("review_cadence"))
    for required in ("code_mutation", "skill_application", "collector_config", "finance_mutation", "execution"):
        if required not in cadence:
            errors.append(f"missing_cadence:{required}")
    if not as_list(payload.get("proposals")):
        warnings.append("no_proposals_generated")
    for proposal in as_list(payload.get("proposals")):
        status = as_dict(proposal).get("proposal_status")
        if status in {"auto_apply", "auto_execute", "applied"}:
            errors.append(f"forbidden_proposal_status:{proposal.get('proposal_id')}")
    return {"status": "error" if errors else "warning" if warnings else "ok", "errors": errors, "warnings": warnings}


def render_md(payload: dict[str, Any]) -> str:
    summary = as_dict(payload.get("summary"))
    lines = [
        "# WF74 Reflection To Proposal Autopilot",
        "",
        f"- Generated: {payload.get('generated_at_utc')}",
        f"- Status: {payload.get('status')}",
        f"- Proposals: {summary.get('proposal_count')}",
        f"- Owner-gated proposals: {summary.get('owner_decision_required_count')}",
        "",
        "## Proposals",
    ]
    for proposal in as_list(payload.get("proposals")):
        lines.append(
            f"- {proposal.get('priority')} | {proposal.get('category')} | "
            f"{proposal.get('title')} | status={proposal.get('proposal_status')}"
        )
    lines.extend(["", "## Blocked Actions"])
    for item in as_list(payload.get("blocked_actions")):
        lines.append(f"- {item}")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--queue", type=Path, default=QUEUE)
    parser.add_argument("--json-out", type=Path, default=OUT_JSON)
    parser.add_argument("--limit", type=int, default=8)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--write-md", action="store_true")
    parser.add_argument("--validate", action="store_true")
    args = parser.parse_args(argv)
    queue_path = args.queue if args.queue.is_absolute() else ROOT / args.queue
    out = args.json_out if args.json_out.is_absolute() else ROOT / args.json_out
    queue = as_dict(load_json_artifact(queue_path))
    payload = build_payload(queue, args.limit)
    if args.write:
        atomic_write_json(out, payload)
        if args.write_md:
            atomic_write_text(out.with_suffix(".md") if out != OUT_JSON else OUT_MD, render_md(payload))
    else:
        print(json.dumps(payload, indent=2))
    print(
        "status={status} validation={validation} proposals={count} owner_gated={owner}".format(
            status=payload["status"],
            validation=payload["validation"]["status"],
            count=payload["summary"]["proposal_count"],
            owner=payload["summary"]["owner_decision_required_count"],
        )
    )
    if args.validate and payload["validation"]["status"] == "error":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
