#!/usr/bin/env python3
"""Create review-only PM job candidates from prompt-book eval gaps."""
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from prompt_book_common import (
    AUTHORITY_BOUNDARY,
    EVAL_GAP_PATH,
    PM_JOB_MD_PATH,
    PM_JOB_PATH,
    ROOT,
    utc_now,
    write_json,
    write_text,
)
from prompt_book_eval_gap_packet import build_eval_gap_packet

SCHEMA = "veritas.prompt_book.pm_jobs.v1"


def _job(job_id: str, title: str, priority: str, objective: str, acceptance: list[str]) -> dict[str, Any]:
    return {
        "job_id": job_id,
        "title": title,
        "priority": priority,
        "status": "candidate_review_only",
        "objective": objective,
        "acceptance_proof": acceptance,
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "stop_lines": [
            "do not store raw prompt/response/tool payloads",
            "do not auto-apply skills or doctrine",
            "do not mutate finance/canon/portfolio/cash/sizing/risk",
            "do not mutate cron schedules/runtime/config/channels",
            "do not infer owner approval",
        ],
    }


def build_pm_job_packet(root: Path = ROOT) -> dict[str, Any]:
    eval_packet = build_eval_gap_packet(root)
    high_gaps = [gap for gap in eval_packet.get("eval_gaps") or [] if gap.get("priority") == "high"]
    gap_count = len(eval_packet.get("eval_gaps") or [])
    if gap_count == 0:
        eval_fixture_title = "Maintain prompt-book eval fixture coverage"
        eval_fixture_objective = "Keep deterministic prompt-book fixture coverage green as new prompt families are added."
        eval_fixture_priority = "low"
    elif high_gaps:
        eval_fixture_title = "Build prompt-book eval fixtures for high-priority entries"
        eval_fixture_objective = "Create deterministic fixtures for high-priority prompt-book entries and wire them into validator proof."
        eval_fixture_priority = "high"
    else:
        eval_fixture_title = "Build prompt-book eval fixtures for remaining entries"
        eval_fixture_objective = "Create deterministic fixtures for remaining prompt-book entries and wire them into validator proof."
        eval_fixture_priority = "normal"

    jobs = [
        _job(
            "pm-prompt-book-eval-gap-v0",
            eval_fixture_title,
            eval_fixture_priority,
            eval_fixture_objective,
            [
                "python scripts\\prompt_book_eval_fixtures.py --write --write-md --validate",
                "python scripts\\test_prompt_book_eval_fixtures.py",
                "python scripts\\prompt_book_eval_gap_packet.py --write --write-md --validate",
                "python scripts\\prompt_book_linter.py --write --validate",
            ],
        ),
        _job(
            "pm-prompt-book-cron-contract-lint",
            "Design prompt-contract lint for cron/helper jobs",
            "medium",
            "Identify cron/helper prompts that lack objective, sources, allowed tools, forbidden tools, output schema, proof, and stop lines.",
            [
                "review-only cron contract packet",
                "no schedule mutation",
                "cron-control remains clean",
            ],
        ),
        _job(
            "pm-prompt-book-isolated-agent-template-feed",
            "Attach prompt-book entry IDs to isolated-agent packet templates",
            "medium",
            "Ensure future isolated-agent packets cite prompt-book entry IDs, eval fixtures, and demotion triggers.",
            [
                "agent bootstrap generator test",
                "prompt registry contains supervised template feed rows",
                "no new agent creation or binding",
            ],
        ),
        _job(
            "pm-token-heavy-prompt-compression-proof",
            "Use token scorecards to rank prompt compression candidates",
            "normal",
            "Convert repeated token-heavy prompt families into compression candidates without losing stop lines.",
            [
                "token efficiency packet reviewed",
                "compression candidate keeps authority boundary",
                "no raw prompt capture",
            ],
        ),
    ]

    validation_errors: list[str] = []
    for job in jobs:
        boundary = job.get("authority_boundary") or {}
        if boundary.get("capital_deployment") or boundary.get("paper_live_account_action") or boundary.get("skill_auto_apply"):
            validation_errors.append(f"{job.get('job_id')}:authority_boundary_invalid")

    return {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "blocked" if validation_errors else "ok",
        "summary": {
            "job_count": len(jobs),
            "high_priority_gap_count": len(high_gaps),
            "pm_import_required": False,
            "review_only": True,
            "next_safe_action": (
                "Keep fixture coverage green and use PM only for future prompt-book debt; Skill Workshop changes require explicit approval."
                if gap_count == 0
                else "Use PM to schedule eval fixture implementation; keep Skill Workshop proposals pending until explicitly approved."
            ),
        },
        "source_eval_gap_packet": str(EVAL_GAP_PATH.relative_to(ROOT)).replace("\\", "/"),
        "jobs": jobs,
        "validation": {
            "status": "blocked" if validation_errors else "ok",
            "errors": validation_errors,
            "warnings": [],
        },
    }


def render_markdown(packet: dict[str, Any]) -> str:
    lines = [
        "# Prompt Book PM Job Packet",
        "",
        f"- Status: `{packet.get('status')}`",
        f"- Jobs: `{packet.get('summary', {}).get('job_count')}`",
        "",
        "| Job ID | Priority | Status |",
        "|---|---|---|",
    ]
    for job in packet.get("jobs") or []:
        lines.append(f"| `{job.get('job_id')}` | {job.get('priority')} | {job.get('status')} |")
    lines.extend([
        "",
        "These are PM candidates, not imported live PM commitments unless a PM owner packet consumes them.",
    ])
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--write-md", action="store_true")
    parser.add_argument("--validate", action="store_true")
    args = parser.parse_args()

    packet = build_pm_job_packet(ROOT)
    if args.write:
        write_json(PM_JOB_PATH, packet)
    if args.write_md:
        write_text(PM_JOB_MD_PATH, render_markdown(packet))
    print(
        f"status={packet['status']} jobs={packet['summary']['job_count']} "
        f"validation={packet['validation']['status']}"
    )
    if args.validate and packet["validation"]["status"] == "blocked":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
