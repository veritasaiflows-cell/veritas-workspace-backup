#!/usr/bin/env python3
"""Build the morning P0 pickup contract for Prompt Book V0.

The contract is a review/proof surface. It does not apply Skill Workshop
proposals, change cron schedules, capture raw prompts, or widen authority.
"""
from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path
from typing import Any

from prompt_book_common import (
    AUTHORITY_BOUNDARY,
    EVAL_FIXTURE_PATH,
    EVAL_GAP_PATH,
    LINT_PATH,
    PM_JOB_PATH,
    REGISTRY_PATH,
    ROOT,
    TMP,
    load_json,
    scan_forbidden,
    utc_now,
    write_json,
    write_text,
)

SCHEMA = "veritas.prompt_book.morning_p0_contract.v1"
OUTPUT_PATH = TMP / "prompt-book-morning-p0-contract.json"
OUTPUT_MD_PATH = TMP / "prompt-book-morning-p0-contract.md"

P0_EVAL_FIXTURE_TARGETS = [
    "task-intake-contract-v1",
    "agi-harness-mode-v1",
    "finance-response-contract-v1",
    "helper-lane-contract-v1",
    "wf88-wiki-synthesis-contract-v1",
]
HIGH_PRIORITY_EVAL_FIXTURES = P0_EVAL_FIXTURE_TARGETS

SKILL_PROPOSAL_REVIEW = [
    {
        "proposal_id": "veritas-prompt-book-operator-20260707-2aeadc5cf7",
        "kind": "create",
        "skill_name": "veritas-prompt-book-operator",
        "scan": "clean",
        "review_status": "applied",
        "recommended_action": "applied_by_owner_approval",
        "recommended_change": "Live operator includes eval fixtures, morning P0 contract, and Skill Workshop apply sequence.",
        "apply_order": 1,
    },
    {
        "proposal_id": "veritas-self-improvement-20260707-62b9afa283",
        "kind": "update",
        "skill_name": "veritas-self-improvement",
        "scan": "clean",
        "review_status": "applied",
        "recommended_action": "applied_by_owner_approval",
        "recommended_change": "Live skill now routes repeated prompt friction through prompt-book fixture and eval-gap proof.",
        "apply_order": 2,
    },
    {
        "proposal_id": "veritas-pm-department-20260707-6edf8475a5",
        "kind": "update",
        "skill_name": "veritas-pm-department",
        "scan": "clean",
        "review_status": "applied",
        "recommended_action": "applied_by_owner_approval",
        "recommended_change": "Live skill now includes prompt-book PM job intake and zero-gap maintenance interpretation.",
        "apply_order": 3,
    },
    {
        "proposal_id": "cron-automation-manager-20260707-3f67cbf78f",
        "kind": "update",
        "skill_name": "cron-automation-manager",
        "scan": "clean",
        "review_status": "applied",
        "recommended_action": "applied_by_owner_approval",
        "recommended_change": "Live skill now includes review-only prompt-contract lint proof with no schedule mutation.",
        "apply_order": 4,
    },
    {
        "proposal_id": "agi-harness-readiness-operator-20260707-a616ee1af3",
        "kind": "update",
        "skill_name": "agi-harness-readiness-operator",
        "scan": "clean",
        "review_status": "rejected_superseded",
        "recommended_action": "rejected_after_merge",
        "recommended_change": "Superseded by merged applied proposal agi-harness-readiness-operator-20260707-3f71cd8311.",
        "apply_order": None,
    },
    {
        "proposal_id": "agi-harness-readiness-operator-20260707-3f71cd8311",
        "kind": "update",
        "skill_name": "agi-harness-readiness-operator",
        "scan": "clean",
        "review_status": "applied",
        "recommended_action": "applied_by_owner_approval",
        "recommended_change": "Live skill now merges prompt-book readiness evidence with token/ticker-card proof path.",
        "apply_order": None,
    },
]


def _rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def _load_packet(root: Path, path: Path) -> dict[str, Any]:
    payload = load_json(root / path.relative_to(ROOT))
    return payload if isinstance(payload, dict) else {}


def _source_summary(name: str, root: Path, path: Path) -> dict[str, Any]:
    actual = root / path.relative_to(ROOT)
    payload = load_json(actual)
    summary = payload.get("summary") if isinstance(payload, dict) else {}
    validation = payload.get("validation") if isinstance(payload, dict) else {}
    return {
        "name": name,
        "path": _rel(path),
        "exists": actual.exists(),
        "status": payload.get("status") if isinstance(payload, dict) else None,
        "validation_status": validation.get("status") if isinstance(validation, dict) else None,
        "summary": summary if isinstance(summary, dict) else {},
    }


def _high_priority_gaps(eval_packet: dict[str, Any]) -> list[str]:
    if not isinstance(eval_packet.get("eval_gaps"), list):
        return list(P0_EVAL_FIXTURE_TARGETS)
    gaps = []
    for gap in eval_packet.get("eval_gaps") or []:
        if isinstance(gap, dict) and gap.get("priority") == "high":
            prompt_id = gap.get("prompt_id")
            if isinstance(prompt_id, str):
                gaps.append(prompt_id)
    return gaps


def _covered_fixture_prompt_ids(fixture_packet: dict[str, Any]) -> list[str]:
    summary = fixture_packet.get("summary") or {}
    covered = summary.get("covered_prompt_ids")
    if isinstance(covered, list):
        return [item for item in covered if isinstance(item, str)]
    ids: list[str] = []
    for fixture in fixture_packet.get("fixtures") or []:
        if isinstance(fixture, dict) and fixture.get("fixture_status") == "covered":
            prompt_id = fixture.get("prompt_id")
            if isinstance(prompt_id, str):
                ids.append(prompt_id)
    return ids


def _skill_review() -> dict[str, Any]:
    unresolved_rows = [
        row
        for row in SKILL_PROPOSAL_REVIEW
        if row["review_status"] not in {"applied", "rejected_superseded"}
    ]
    skill_counts = Counter(row["skill_name"] for row in unresolved_rows)
    duplicate_update_skills = sorted(
        skill
        for skill, count in skill_counts.items()
        if count > 1
        and any(
            row["skill_name"] == skill and row["kind"] == "update"
            for row in unresolved_rows
        )
    )
    return {
        "source": "Skill Workshop apply/reject outputs from 2026-07-07",
        "reviewed_proposal_count": len(SKILL_PROPOSAL_REVIEW),
        "pending_proposal_count": len(unresolved_rows),
        "applied_proposal_count": sum(1 for row in SKILL_PROPOSAL_REVIEW if row["review_status"] == "applied"),
        "rejected_proposal_count": sum(1 for row in SKILL_PROPOSAL_REVIEW if row["review_status"] == "rejected_superseded"),
        "clean_scan_count": sum(1 for row in SKILL_PROPOSAL_REVIEW if row["scan"] == "clean"),
        "duplicate_update_skills": duplicate_update_skills,
        "duplicate_update_count": len(duplicate_update_skills),
        "recommendation": (
            "No prompt-book Skill Workshop proposal remains pending from this packet. Keep future changes owner-gated "
            "and use full-body merged proposals for existing-skill updates."
        ),
        "proposals": SKILL_PROPOSAL_REVIEW,
    }


def _p0_work_items(
    high_priority_gaps: list[str],
    covered_fixture_prompt_ids: list[str],
    remaining_eval_gaps: list[str],
    pm_packet: dict[str, Any],
) -> list[dict[str, Any]]:
    pm_job_ids = [
        job.get("job_id")
        for job in pm_packet.get("jobs") or []
        if isinstance(job, dict) and job.get("job_id")
    ]
    fixture_status = "complete" if not high_priority_gaps and set(P0_EVAL_FIXTURE_TARGETS).issubset(covered_fixture_prompt_ids) else "ready_for_implementation"
    return [
        {
            "work_item_id": "p0-skill-proposal-review",
            "priority": "p0",
            "status": "complete",
            "objective": "Review, revise, apply, and supersede Skill Workshop proposals in the approved sequence.",
            "recommended_sequence": [
                "Applied veritas-prompt-book-operator first after exact approval.",
                "Applied self-improvement, PM, cron, and merged AGI harness updates after full-body revisions.",
                "Rejected the duplicate AGI harness proposal as superseded.",
            ],
            "acceptance_proof": [
                "Skill Workshop proposal ids named explicitly",
                "openclaw skills check after approved apply",
                "skill_workshop_body_guard.py --write --validate after approved apply",
            ],
            "stop_lines": [
                "no Skill Workshop apply/reject/quarantine without exact Randall approval",
                "do not apply duplicate AGI harness updates as-is",
            ],
        },
        {
            "work_item_id": "p0-high-priority-eval-fixtures",
            "priority": "p0",
            "status": fixture_status,
            "objective": "Keep deterministic fixtures for the high-priority prompt-book entries green.",
            "target_prompt_ids": list(P0_EVAL_FIXTURE_TARGETS),
            "covered_prompt_ids": covered_fixture_prompt_ids,
            "remaining_high_priority_prompt_ids": high_priority_gaps,
            "acceptance_proof": [
                "focused fixture tests pass",
                "python scripts\\prompt_book_eval_fixtures.py --write --write-md --validate",
                "python scripts\\prompt_book_registry.py --write --write-md --validate",
                "python scripts\\prompt_book_linter.py --write --validate",
                "python scripts\\prompt_book_eval_gap_packet.py --write --write-md --validate",
                "python scripts\\prompt_book_pm_job_packet.py --write --write-md --validate",
            ],
            "stop_lines": [
                "metadata-only fixtures only",
                "no raw prompt/response/tool payload capture",
                "no finance/canon/portfolio/cash/sizing/risk mutation",
            ],
        },
        {
            "work_item_id": "p0-pm-job-routing",
            "priority": "p0",
            "status": "review_only_ready",
            "objective": "Use the PM job packet to route remaining non-P0 eval fixture work without treating candidates as live PM commitments.",
            "pm_job_ids": pm_job_ids,
            "recommended_first_job": "pm-prompt-book-eval-gap-v0",
            "remaining_eval_gap_prompt_ids": remaining_eval_gaps,
            "acceptance_proof": [
                "tmp/prompt-book-pm-job-packet.json validation ok",
                "PM owner packet consumes or explicitly defers the candidate",
            ],
            "stop_lines": [
                "PM packet candidates are not live commitments until a PM owner packet consumes them",
                "no external/customer delivery or authority expansion",
            ],
        },
        {
            "work_item_id": "p0-revalidate-harness",
            "priority": "p0",
            "status": "ready_after_eval_fixtures",
            "objective": "Refresh AGI harness readiness after prompt-book eval fixtures land.",
            "acceptance_proof": [
                "python scripts\\agi_harness_readiness_packet.py --write --write-md --validate",
                "prompt-book eval gap count reduced or explained",
                "lane register closed with proof",
            ],
            "stop_lines": [
                "no AGI/ASI capability claim",
                "no autonomy promotion from clean proof",
                "no cron schedule/runtime/config mutation",
            ],
        },
    ]


def validate_contract(packet: dict[str, Any], root: Path = ROOT) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []

    for source in packet.get("source_artifacts") or []:
        if not source.get("exists"):
            errors.append(f"missing_source_artifact:{source.get('path')}")
        if source.get("validation_status") == "blocked":
            errors.append(f"blocked_source_artifact:{source.get('path')}")

    boundary = packet.get("authority_boundary") or {}
    forbidden_true = [
        "raw_prompt_capture",
        "raw_response_capture",
        "tool_payload_capture",
        "secret_capture",
        "skill_auto_apply",
        "doctrine_auto_apply",
        "cron_schedule_mutation",
        "runtime_config_mutation",
        "finance_canon_portfolio_mutation",
        "capital_deployment",
        "paper_live_account_action",
        "external_delivery",
        "owner_approval_inference",
    ]
    for key in forbidden_true:
        if boundary.get(key) is not False:
            errors.append(f"authority_boundary_not_false:{key}")

    if boundary.get("review_only") is not True or boundary.get("metadata_only") is not True:
        errors.append("authority_boundary_not_review_metadata_only")

    missing_high = sorted(set(HIGH_PRIORITY_EVAL_FIXTURES) - set(packet.get("p0_high_priority_prompt_ids") or []))
    fixture_covered = set(packet.get("p0_fixture_covered_prompt_ids") or [])
    if missing_high and not fixture_covered.issuperset(HIGH_PRIORITY_EVAL_FIXTURES):
        errors.append("missing_high_priority_eval_fixture_ids:" + ",".join(missing_high))
    missing_fixture_coverage = sorted(set(P0_EVAL_FIXTURE_TARGETS) - fixture_covered)
    if missing_fixture_coverage:
        errors.append("missing_p0_fixture_coverage:" + ",".join(missing_fixture_coverage))

    skill_review = packet.get("skill_proposal_review") or {}
    if skill_review.get("duplicate_update_count", 0) > 0:
        warnings.append("duplicate_skill_update_proposals_require_merge_before_apply")
    if packet.get("summary", {}).get("eval_gap_count", 0) > 0:
        warnings.append(f"{packet['summary']['eval_gap_count']} prompt-book eval gaps remain")
    if packet.get("summary", {}).get("high_priority_eval_gap_count", 0) > 0:
        warnings.append(f"{packet['summary']['high_priority_eval_gap_count']} high-priority prompt-book eval gaps remain")

    forbidden = scan_forbidden(packet)
    if forbidden:
        errors.extend(forbidden)

    return {
        "status": "blocked" if errors else "ok",
        "errors": errors,
        "warnings": warnings,
        "error_count": len(errors),
        "warning_count": len(warnings),
    }


def build_contract(root: Path = ROOT) -> dict[str, Any]:
    root = Path(root)
    registry = _load_packet(root, REGISTRY_PATH)
    lint = _load_packet(root, LINT_PATH)
    eval_packet = _load_packet(root, EVAL_GAP_PATH)
    fixture_packet = _load_packet(root, EVAL_FIXTURE_PATH)
    pm_packet = _load_packet(root, PM_JOB_PATH)
    high_priority_gaps = _high_priority_gaps(eval_packet)
    covered_fixture_prompt_ids = _covered_fixture_prompt_ids(fixture_packet)
    all_eval_gap_ids = [
        gap.get("prompt_id")
        for gap in eval_packet.get("eval_gaps") or []
        if isinstance(gap, dict) and isinstance(gap.get("prompt_id"), str)
    ]
    skill_review = _skill_review()

    source_artifacts = [
        _source_summary("prompt_book_registry", root, REGISTRY_PATH),
        _source_summary("prompt_book_lint", root, LINT_PATH),
        _source_summary("prompt_book_eval_gap_packet", root, EVAL_GAP_PATH),
        _source_summary("prompt_book_eval_fixtures", root, EVAL_FIXTURE_PATH),
        _source_summary("prompt_book_pm_job_packet", root, PM_JOB_PATH),
    ]

    summary = {
        "readiness_state": "ready_for_morning_pickup",
        "registry_status": registry.get("status"),
        "lint_status": lint.get("status"),
        "eval_gap_status": eval_packet.get("status"),
        "pm_job_status": pm_packet.get("status"),
        "prompt_book_entry_count": (registry.get("summary") or {}).get("entry_count"),
        "eval_gap_count": (eval_packet.get("summary") or {}).get("eval_gap_count", len(high_priority_gaps)),
        "high_priority_eval_gap_count": (eval_packet.get("summary") or {}).get("high_priority_gap_count", len(high_priority_gaps)),
        "p0_fixture_target_count": len(P0_EVAL_FIXTURE_TARGETS),
        "p0_fixture_covered_count": len(set(P0_EVAL_FIXTURE_TARGETS) & set(covered_fixture_prompt_ids)),
        "p0_remaining_high_priority_count": len(high_priority_gaps),
        "pm_job_count": (pm_packet.get("summary") or {}).get("job_count"),
        "reviewed_skill_proposal_count": skill_review["reviewed_proposal_count"],
        "pending_skill_proposal_count": skill_review["pending_proposal_count"],
        "applied_skill_proposal_count": skill_review["applied_proposal_count"],
        "rejected_skill_proposal_count": skill_review["rejected_proposal_count"],
        "duplicate_skill_update_count": skill_review["duplicate_update_count"],
        "next_safe_action": (
            "Prompt Book is fixture-covered and skill-updated. Next safe action: keep coverage green and only design "
            "review-only cron/helper lint after a separate schedule/payload gate."
        ),
    }

    packet: dict[str, Any] = {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "warning",
        "summary": summary,
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "source_artifacts": source_artifacts,
        "morning_contract": {
            "objective": "Resume Prompt Book P0 in the morning and turn warning-grade prompt families into tested reusable internal challenge solvers.",
            "authority_class": "L2 review/proof plus L3 bounded local implementation only after lane lease for fixture/code surfaces",
            "non_goals": [
            "no future Skill Workshop apply/reject/quarantine without exact owner approval",
                "no cron schedule, payload, model-route, delivery, runtime, config, channel, credential, or startup mutation",
                "no raw prompt, raw response, tool payload, system prompt, secret, or credential capture",
                "no finance/canon/portfolio/cash/sizing/risk mutation",
                "no paper/live/brokerage/account action",
                "no external/customer delivery",
                "no AGI/ASI capability claim or autonomy promotion",
            ],
            "first_read_commands": [
                "python scripts\\prompt_book_registry.py --write --write-md --validate",
                "python scripts\\prompt_book_eval_fixtures.py --write --write-md --validate",
                "python scripts\\prompt_book_linter.py --write --validate",
                "python scripts\\prompt_book_eval_gap_packet.py --write --write-md --validate",
                "python scripts\\prompt_book_pm_job_packet.py --write --write-md --validate",
                "python scripts\\prompt_book_morning_p0_contract.py --write --write-md --validate",
            ],
            "acceptance_proof": [
                "python scripts\\test_prompt_book_morning_p0_contract.py",
                "python scripts\\test_prompt_book_eval_fixtures.py",
                "python scripts\\test_prompt_book_registry.py",
                "python scripts\\test_prompt_book_linter.py",
                "python scripts\\test_prompt_book_eval_gap_packet.py",
                "python scripts\\test_prompt_book_pm_job_packet.py",
                "python -m py_compile scripts\\prompt_book_morning_p0_contract.py scripts\\test_prompt_book_morning_p0_contract.py",
                "python scripts\\concurrent_lane_manager.py --status --write --validate",
            ],
        },
        "skill_proposal_review": skill_review,
        "p0_high_priority_prompt_ids": high_priority_gaps,
        "p0_fixture_target_prompt_ids": list(P0_EVAL_FIXTURE_TARGETS),
        "p0_fixture_covered_prompt_ids": covered_fixture_prompt_ids,
        "remaining_eval_gap_prompt_ids": all_eval_gap_ids,
        "p0_work_items": _p0_work_items(high_priority_gaps, covered_fixture_prompt_ids, all_eval_gap_ids, pm_packet),
    }
    packet["validation"] = validate_contract(packet, root=root)
    if packet["validation"]["status"] == "blocked":
        packet["status"] = "blocked"
    elif packet["validation"]["warning_count"]:
        packet["status"] = "warning"
    else:
        packet["status"] = "ok"
    return packet


def render_markdown(packet: dict[str, Any]) -> str:
    summary = packet.get("summary") or {}
    skill_review = packet.get("skill_proposal_review") or {}
    lines = [
        "# Prompt Book Morning P0 Contract",
        "",
        f"- Status: `{packet.get('status')}`",
        f"- Readiness: `{summary.get('readiness_state')}`",
        f"- Eval gaps: `{summary.get('eval_gap_count')}`",
        f"- High-priority gaps: `{summary.get('high_priority_eval_gap_count')}`",
        f"- P0 fixture coverage: `{summary.get('p0_fixture_covered_count')}/{summary.get('p0_fixture_target_count')}`",
        f"- PM jobs: `{summary.get('pm_job_count')}`",
        f"- Pending skill proposals: `{summary.get('pending_skill_proposal_count')}`",
        f"- Duplicate skill updates needing merge: `{summary.get('duplicate_skill_update_count')}`",
        "",
        "## Morning P0 Order",
        "",
        "1. Review pending Skill Workshop proposals through Skill Workshop.",
        "2. Apply `veritas-prompt-book-operator` first only with exact Randall approval.",
        "3. Apply self-improvement, PM, cron, and merged AGI updates only after full-body proposal revisions.",
        "4. Reject duplicate AGI harness updates after merge/supersede proof.",
        "5. Keep deterministic prompt-book eval fixtures green and route future gaps through PM.",
        "",
        "## P0 Eval Fixture Coverage",
        "",
    ]
    covered = set(packet.get("p0_fixture_covered_prompt_ids") or [])
    remaining_high = set(packet.get("p0_high_priority_prompt_ids") or [])
    for prompt_id in packet.get("p0_fixture_target_prompt_ids") or []:
        state = "covered" if prompt_id in covered else ("remaining_high_priority" if prompt_id in remaining_high else "missing")
        lines.append(f"- `{prompt_id}` - `{state}`")
    lines.extend([
        "",
        "## Remaining Eval Gaps",
        "",
    ])
    for prompt_id in packet.get("remaining_eval_gap_prompt_ids") or []:
        lines.append(f"- `{prompt_id}`")
    lines.extend([
        "",
        "## Skill Proposal Review",
        "",
        "| Proposal | Skill | Review | Recommendation |",
        "|---|---|---|---|",
    ])
    for row in skill_review.get("proposals") or []:
        lines.append(
            f"| `{row.get('proposal_id')}` | `{row.get('skill_name')}` | {row.get('review_status')} | {row.get('recommended_action')} |"
        )
    lines.extend([
        "",
        "## Stop Lines",
        "",
        "- No Skill Workshop apply/reject/quarantine without exact Randall approval.",
        "- No raw prompt, response, tool payload, system prompt, secret, or credential capture.",
        "- No cron schedule/runtime/config/channel mutation.",
        "- No finance/canon/portfolio/cash/sizing/risk mutation.",
        "- No paper/live/brokerage/account action.",
        "- No external/customer delivery, AGI/ASI capability claim, autonomy promotion, or owner approval inference.",
        "",
        "## First-Hop Commands",
        "",
        "```powershell",
    ])
    for command in (packet.get("morning_contract") or {}).get("first_read_commands") or []:
        lines.append(command)
    lines.extend([
        "```",
        "",
        "This packet is a morning pickup contract and review/proof surface only. It does not apply skills, mutate schedules, or create authority.",
    ])
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--write-md", action="store_true")
    parser.add_argument("--validate", action="store_true")
    args = parser.parse_args()

    packet = build_contract(ROOT)
    if args.write:
        write_json(OUTPUT_PATH, packet)
    if args.write_md:
        write_text(OUTPUT_MD_PATH, render_markdown(packet))
    print(
        f"status={packet['status']} readiness={packet['summary']['readiness_state']} "
        f"eval_gaps={packet['summary']['eval_gap_count']} high={packet['summary']['high_priority_eval_gap_count']} "
        f"skill_proposals={packet['summary']['pending_skill_proposal_count']} validation={packet['validation']['status']}"
    )
    if args.validate and packet["validation"]["status"] == "blocked":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
