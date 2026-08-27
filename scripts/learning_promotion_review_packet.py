#!/usr/bin/env python3
"""Build a human review packet for learning promotion candidates.

This script consumes ``learning_promotion_classifier`` output and produces a
review-only packet plus optional Markdown. It does not create Skill Workshop
proposals, append memory, open PM jobs, apply code, mutate cron, or change
finance/account state.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from learning_promotion_classifier import (
    AUTHORITY_BOUNDARY,
    BLOCKED_ACTIONS,
    OUT as CLASSIFIER_OUT,
    as_dict,
    as_list,
    classify_signals,
    rel,
    safe_priority,
)
from market_data_utils import atomic_write_json, atomic_write_text, load_json_artifact


ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
OUT = TMP / "learning-promotion-review-packet.json"
MD_OUT = TMP / "learning-promotion-review-packet.md"
SCHEMA = "veritas.learning_promotion_review_packet.v1"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_candidates(path: Path) -> dict[str, Any]:
    payload = as_dict(load_json_artifact(path))
    if payload:
        return payload
    return classify_signals()


def group_by_target(candidates: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    groups: dict[str, list[dict[str, Any]]] = {}
    for row in candidates:
        target = str(row.get("promotion_target") or "unknown")
        groups.setdefault(target, []).append(row)
    for rows in groups.values():
        rows.sort(key=lambda item: (-safe_priority(item.get("priority")), str(item.get("title") or "")))
    return groups


def compact_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "candidate_id": row.get("candidate_id"),
        "title": row.get("title"),
        "priority": row.get("priority"),
        "source_artifact": row.get("source_artifact"),
        "source_id": row.get("source_id"),
        "reason": row.get("reason"),
        "proposed_action": row.get("proposed_action"),
        "suggested_skill": row.get("suggested_skill"),
        "memory_append": row.get("memory_append"),
        "evidence_paths": row.get("evidence_paths"),
        "blocked_actions": row.get("blocked_actions"),
    }


def build_packet(candidates_packet: dict[str, Any] | None = None) -> dict[str, Any]:
    candidates_packet = candidates_packet or load_candidates(CLASSIFIER_OUT)
    candidates = [as_dict(row) for row in as_list(candidates_packet.get("candidates"))]
    groups = group_by_target(candidates)
    summary = as_dict(candidates_packet.get("summary"))
    recommended_order = [
        "validator_gap",
        "pm_implementation_job",
        "skill_workshop_proposal",
        "daily_memory_append",
        "monitor_only",
        "owner_decision",
        "no_op",
    ]
    packet = {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "ok",
        "purpose": "Review-only operator packet for deciding which learning signals should become PM jobs, Skill Workshop proposals, daily memory notes, validator repairs, monitor rows, or no-ops.",
        "source_artifact": rel(CLASSIFIER_OUT),
        "source_status": candidates_packet.get("status"),
        "source_validation": as_dict(candidates_packet.get("validation")),
        "authority_boundary": AUTHORITY_BOUNDARY.copy(),
        "summary": {
            "candidate_count": len(candidates),
            "pm_implementation_job_count": len(groups.get("pm_implementation_job", [])),
            "skill_workshop_proposal_count": len(groups.get("skill_workshop_proposal", [])),
            "daily_memory_append_count": len(groups.get("daily_memory_append", [])),
            "validator_gap_count": len(groups.get("validator_gap", [])),
            "monitor_only_count": len(groups.get("monitor_only", [])),
            "owner_decision_count": len(groups.get("owner_decision", [])),
            "no_op_count": len(groups.get("no_op", [])),
            "direct_apply_count": summary.get("direct_apply_count", 0),
            "direct_memory_write_count": summary.get("direct_memory_write_count", 0),
            "direct_skill_write_count": summary.get("direct_skill_write_count", 0),
            "recommended_next_action": "Start with validator gaps and metadata-only PM candidates; turn skill/memory candidates into separate explicit actions only after review.",
        },
        "recommended_order": recommended_order,
        "promotion_groups": {
            target: [compact_row(row) for row in groups.get(target, [])]
            for target in recommended_order
            if groups.get(target)
        },
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
    summary = as_dict(packet.get("summary"))
    for key in ("direct_apply_count", "direct_memory_write_count", "direct_skill_write_count"):
        if safe_priority(summary.get(key), default=0) != 0:
            errors.append(f"{key}_must_be_zero")
    source_validation = as_dict(packet.get("source_validation"))
    if source_validation.get("status") == "blocked":
        errors.append("source_classifier_blocked")
    elif source_validation.get("status") == "warning":
        warnings.extend([f"classifier_warning:{item}" for item in as_list(source_validation.get("warnings"))])
    return {"status": "blocked" if errors else "warning" if warnings else "ok", "errors": errors, "warnings": warnings}


def render_markdown(packet: dict[str, Any]) -> str:
    summary = as_dict(packet.get("summary"))
    lines = [
        "# Learning Promotion Review Packet",
        "",
        "Status: review only",
        "",
        "## Summary",
        "",
        f"- Validation: `{as_dict(packet.get('validation')).get('status')}`",
        f"- Candidates: `{summary.get('candidate_count')}`",
        f"- PM implementation candidates: `{summary.get('pm_implementation_job_count')}`",
        f"- Skill Workshop proposal candidates: `{summary.get('skill_workshop_proposal_count')}`",
        f"- Daily memory append previews: `{summary.get('daily_memory_append_count')}`",
        f"- Validator gaps: `{summary.get('validator_gap_count')}`",
        f"- Monitor-only rows: `{summary.get('monitor_only_count')}`",
        f"- Direct apply / memory / skill writes: `{summary.get('direct_apply_count')}` / `{summary.get('direct_memory_write_count')}` / `{summary.get('direct_skill_write_count')}`",
        "",
        "## Recommended Order",
        "",
    ]
    for target in as_list(packet.get("recommended_order")):
        rows = as_list(as_dict(packet.get("promotion_groups")).get(target))
        if not rows:
            continue
        lines.extend([f"### {str(target).replace('_', ' ').title()}", ""])
        for row in rows[:8]:
            item = as_dict(row)
            detail = item.get("suggested_skill") or item.get("source_artifact") or ""
            lines.append(f"- `{item.get('priority')}` {item.get('title')} ({detail})")
            lines.append(f"  - {item.get('proposed_action')}")
        lines.append("")
    lines.extend([
        "## Boundary",
        "",
        "- This packet does not apply skills, write memory, create PM jobs, mutate cron/config/runtime, mutate finance canon/portfolio, or infer owner approval.",
        "- Any actual Skill Workshop proposal, memory append, or implementation job remains a separate explicit action.",
        "",
    ])
    return "\n".join(lines)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--write-md", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--json", action="store_true", dest="print_json")
    parser.add_argument("--candidates", type=Path, default=CLASSIFIER_OUT)
    parser.add_argument("--out", type=Path, default=OUT)
    parser.add_argument("--md-out", type=Path, default=MD_OUT)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    candidates_path = args.candidates if args.candidates.is_absolute() else ROOT / args.candidates
    packet = build_packet(load_candidates(candidates_path))
    out = args.out if args.out.is_absolute() else ROOT / args.out
    md_out = args.md_out if args.md_out.is_absolute() else ROOT / args.md_out
    if args.write:
        atomic_write_json(out, packet)
    if args.write_md:
        atomic_write_text(md_out, render_markdown(packet))
    if args.print_json:
        print(json.dumps(packet, indent=2, sort_keys=True))
    else:
        summary = as_dict(packet.get("summary"))
        print(
            "status={status} validation={validation} candidates={candidates} pm_jobs={pm} skills={skills} memory={memory} validators={validators}".format(
                status=packet.get("status"),
                validation=as_dict(packet.get("validation")).get("status"),
                candidates=summary.get("candidate_count"),
                pm=summary.get("pm_implementation_job_count"),
                skills=summary.get("skill_workshop_proposal_count"),
                memory=summary.get("daily_memory_append_count"),
                validators=summary.get("validator_gap_count"),
            )
        )
    if args.validate and as_dict(packet.get("validation")).get("status") == "blocked":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
