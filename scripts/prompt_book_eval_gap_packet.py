#!/usr/bin/env python3
"""Create a WF74/WF88 eval-gap packet for prompt-book entries."""
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from prompt_book_common import (
    AUTHORITY_BOUNDARY,
    EVAL_GAP_MD_PATH,
    EVAL_GAP_PATH,
    ROOT,
    utc_now,
    write_json,
    write_text,
)
from prompt_book_registry import build_registry

SCHEMA = "veritas.prompt_book.eval_gap.v1"


def _priority_for(entry: dict[str, Any]) -> str:
    dept = entry.get("department")
    if dept in {"finance", "rsi", "ops"}:
        return "high"
    if dept == "pm":
        return "medium"
    return "normal"


def build_eval_gap_packet(root: Path = ROOT) -> dict[str, Any]:
    registry = build_registry(root)

    gaps: list[dict[str, Any]] = []
    covered = 0
    for entry in registry.get("entries") or []:
        if not isinstance(entry, dict):
            continue
        eval_contract = entry.get("eval_contract") or {}
        status = eval_contract.get("status")
        if status == "covered":
            covered += 1
            continue
        gaps.append({
            "prompt_id": entry.get("prompt_id"),
            "name": entry.get("name"),
            "department": entry.get("department"),
            "owner_workflow": entry.get("owner_workflow"),
            "eval_status": status or "missing",
            "priority": _priority_for(entry),
            "recommended_route": "PM job + WF74 Skill Workshop candidate only after repeated use",
            "minimum_fixture": {
                "input_contract": "synthetic source packet with authority boundary and expected output fields",
                "expected_checks": [
                    "required fields present",
                    "forbidden authority claims absent",
                    "raw prompt/response/tool payload absent",
                    "stop lines preserved",
                ],
            },
        })

    high = [gap for gap in gaps if gap["priority"] == "high"]
    status = "warning" if gaps else "ok"
    validation_errors: list[str] = []
    boundary = dict(AUTHORITY_BOUNDARY)
    if boundary.get("capital_deployment") or boundary.get("paper_live_account_action"):
        validation_errors.append("authority_boundary_invalid")
    return {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "blocked" if validation_errors else status,
        "summary": {
            "registry_status": registry.get("status"),
            "entry_count": len(registry.get("entries") or []),
            "covered_count": covered,
            "eval_gap_count": len(gaps),
            "high_priority_gap_count": len(high),
            "wf74_route_candidate_count": len(gaps),
            "skill_workshop_candidate_count": 0,
            "next_safe_action": "Create PM implementation jobs for high-priority eval gaps; create Skill Workshop proposals only when repeated failures prove reusable doctrine change.",
        },
        "authority_boundary": boundary,
        "eval_gaps": gaps,
        "validation": {
            "status": "blocked" if validation_errors else "ok",
            "errors": validation_errors,
            "warnings": [] if not gaps else [f"{len(gaps)} prompt-book entries lack covered eval fixtures"],
        },
    }


def render_markdown(packet: dict[str, Any]) -> str:
    summary = packet.get("summary") or {}
    lines = [
        "# Prompt Book Eval Gap Packet",
        "",
        f"- Status: `{packet.get('status')}`",
        f"- Eval gaps: `{summary.get('eval_gap_count')}`",
        f"- High-priority gaps: `{summary.get('high_priority_gap_count')}`",
        "",
        "| Prompt ID | Department | Workflow | Priority |",
        "|---|---|---|---|",
    ]
    for gap in packet.get("eval_gaps") or []:
        lines.append(
            f"| `{gap.get('prompt_id')}` | {gap.get('department')} | {gap.get('owner_workflow')} | {gap.get('priority')} |"
        )
    lines.extend([
        "",
        "This packet is review-only. It routes eval debt; it does not apply skills, mutate workflows, or create authority.",
    ])
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--write-md", action="store_true")
    parser.add_argument("--validate", action="store_true")
    args = parser.parse_args()

    packet = build_eval_gap_packet(ROOT)
    if args.write:
        write_json(EVAL_GAP_PATH, packet)
    if args.write_md:
        write_text(EVAL_GAP_MD_PATH, render_markdown(packet))
    print(
        f"status={packet['status']} gaps={packet['summary']['eval_gap_count']} "
        f"validation={packet['validation']['status']}"
    )
    if args.validate and packet["validation"]["status"] == "blocked":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
