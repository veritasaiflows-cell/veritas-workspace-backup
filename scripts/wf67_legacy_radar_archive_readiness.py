#!/usr/bin/env python3
"""Prepare WF67 legacy paper-radar archive readiness proof.

This packet is deliberately review-only. It does not archive, delete, move,
rewrite references, infer owner approval, or touch paper/live execution.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, load_json_artifact


ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
GUARD_REPORT = TMP / "stale-paper-card-reference-guard.json"
REFERENCE_REVIEW = TMP / "wf67-stale-paper-artifact-reference-review.json"
ARCHIVE_DRY_RUN = TMP / "wf67-stale-paper-artifact-archive-dry-run.json"
OUT = TMP / "wf67-legacy-radar-archive-readiness.json"
MD_OUT = TMP / "wf67-legacy-radar-archive-readiness.md"

SCHEMA = "veritas.wf67_legacy_radar_archive_readiness.v1"

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "archive_readiness_packet_only": True,
    "archive_apply_allowed": False,
    "delete_allowed": False,
    "move_allowed": False,
    "source_artifact_mutation_allowed": False,
    "cron_schedule_mutation_allowed": False,
    "config_auth_runtime_channel_mutation_allowed": False,
    "canon_or_portfolio_mutation_allowed": False,
    "cash_sizing_sleeve_risk_rule_mutation_allowed": False,
    "capital_deployment_allowed": False,
    "capital_deployment_approved": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "owner_approval_inferred": False,
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def load_dict(path: Path) -> dict[str, Any]:
    payload = load_json_artifact(path)
    return payload if isinstance(payload, dict) else {}


def rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def ref_family(path_text: str) -> str:
    normalized = str(path_text or "").replace("\\", "/")
    if normalized.startswith("state/long-work-jobs/"):
        return "vector_memory_long_work_index"
    if normalized.startswith("tmp/alpaca-paper-readiness/"):
        return "paper_readiness_internal_history"
    if normalized == "state/agent-message-ledger.jsonl":
        return "agent_message_ledger"
    if normalized.startswith("tmp/canonical-finance-data-plane"):
        return "canonical_finance_data_plane"
    if normalized.startswith("tmp/trade-grade-full-answer/"):
        return "trade_grade_full_answer_packets"
    if normalized.startswith("06. Playbooks/"):
        return "workflow_playbooks"
    if normalized.startswith("scripts/"):
        return "script_docs_or_tests"
    if "/" in normalized:
        return normalized.split("/", 1)[0]
    return normalized or "unknown"


def summarize_blocking_refs(candidates: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, int]]:
    family_counts: Counter[str] = Counter()
    examples: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in candidates:
        for ref in as_list(row.get("references")):
            ref_row = as_dict(ref)
            if ref_row.get("blocking") is not True:
                continue
            family = ref_family(str(ref_row.get("path") or ""))
            family_counts[family] += 1
            if len(examples[family]) < 5:
                examples[family].append({
                    "candidate": str(row.get("path") or ""),
                    "reference": str(ref_row.get("path") or ""),
                })
    rows = [
        {
            "family": family,
            "reference_count": count,
            "examples": examples.get(family, []),
        }
        for family, count in family_counts.most_common()
    ]
    return rows, dict(family_counts)


def build_candidate_rows(review: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for raw in as_list(review.get("candidates")):
        row = as_dict(raw)
        blocking_refs = [
            as_dict(ref)
            for ref in as_list(row.get("references"))
            if as_dict(ref).get("blocking") is True
        ]
        rows.append({
            "path": row.get("path"),
            "source_exists": row.get("source_exists"),
            "older_than_current_window": row.get("older_than_current_window"),
            "classification": row.get("classification"),
            "archiveable": row.get("archiveable") is True,
            "blocking_reference_count": len(blocking_refs),
            "blocking_reference_families": sorted({ref_family(str(ref.get("path") or "")) for ref in blocking_refs}),
            "blocking_references_sample": [
                {
                    "path": ref.get("path"),
                    "family": ref_family(str(ref.get("path") or "")),
                }
                for ref in blocking_refs[:10]
            ],
        })
    return rows


def determine_status(summary: dict[str, Any], guard_summary: dict[str, Any]) -> str:
    current_violations = int(guard_summary.get("current_surface_violation_count") or 0)
    archive_ready = int(summary.get("archive_ready_count") or 0)
    retained = int(summary.get("retained_or_blocked_count") or 0)
    if current_violations:
        return "blocked_current_surface_leakage"
    if archive_ready and retained == 0:
        return "owner_ready_pending_exact_archive_approval"
    if archive_ready:
        return "partial_owner_ready_pending_exact_archive_approval"
    if retained:
        return "blocked_not_archive_ready"
    return "nothing_to_archive"


def remediation_plan(blocking_families: list[dict[str, Any]]) -> list[dict[str, str]]:
    present = {str(row.get("family")) for row in blocking_families}
    plan: list[dict[str, str]] = []
    if "canonical_finance_data_plane" in present or "trade_grade_full_answer_packets" in present:
        plan.append({
            "step": "Regenerate current finance decision surfaces without legacy WF67 prepared-card paths.",
            "proof": "Rerun canonical finance data plane and trade-grade full-answer builders, then rerun the stale-paper guard.",
        })
    if "paper_readiness_internal_history" in present:
        plan.append({
            "step": "Split paper-readiness internal history from current recommendation/card references.",
            "proof": "Paper-readiness history may keep audit links, but current readiness packets must not block archive readiness unless they are live guard inputs.",
        })
    if "vector_memory_long_work_index" in present:
        plan.append({
            "step": "Refresh or reclassify the vector-memory long-work index references as historical index residue.",
            "proof": "Archive readiness should not be blocked by stale semantic-index chunks once current surfaces are clean.",
        })
    if "agent_message_ledger" in present:
        plan.append({
            "step": "Classify agent-message ledger references as immutable audit history, not active consumers.",
            "proof": "The reference review should treat ledger-only mentions as retained audit evidence, not archive blockers.",
        })
    if "workflow_playbooks" in present or "script_docs_or_tests" in present:
        plan.append({
            "step": "Review playbook/script/test references and replace live-looking file paths with archived-proof examples or generic patterns.",
            "proof": "Reference review should show no active code/control dependency before archive approval.",
        })
    plan.append({
        "step": "Rerun guard, reference review, dry-run archive, and readiness packet.",
        "proof": "Owner-ready only when current-surface violations are 0 and archive-ready count is non-zero with no active blockers for the chosen batch.",
    })
    return plan


def build_packet(
    *,
    guard: dict[str, Any] | None = None,
    review: dict[str, Any] | None = None,
    dry_run: dict[str, Any] | None = None,
) -> dict[str, Any]:
    guard = guard if guard is not None else load_dict(GUARD_REPORT)
    review = review if review is not None else load_dict(REFERENCE_REVIEW)
    dry_run = dry_run if dry_run is not None else load_dict(ARCHIVE_DRY_RUN)

    guard_summary = as_dict(guard.get("summary"))
    review_summary = as_dict(review.get("summary"))
    dry_summary = as_dict(dry_run.get("summary"))
    candidates = build_candidate_rows(review)
    blocking_rows = [row for row in candidates if int(row.get("blocking_reference_count") or 0) > 0]
    blocking_families, family_counts = summarize_blocking_refs(as_list(review.get("candidates")))

    merged_summary = {
        "current_surface_violation_count": guard_summary.get("current_surface_violation_count", 0),
        "historical_artifact_count": guard_summary.get("historical_artifact_count", review_summary.get("candidate_count", 0)),
        "historical_artifact_older_than_current_window_count": guard_summary.get("historical_artifact_older_than_current_window_count", 0),
        "archive_ready_count": review_summary.get("archive_ready_count", dry_summary.get("archive_ready_count", 0)),
        "retained_or_blocked_count": review_summary.get("retained_or_blocked_count", dry_summary.get("retained_or_blocked_count", 0)),
        "blocked_active_reference_count": review_summary.get("blocked_active_reference_count", len(blocking_rows)),
        "framework_fixture_count": review_summary.get("framework_fixture_count", 0),
        "candidate_count": review_summary.get("candidate_count", len(candidates)),
    }
    status = determine_status(merged_summary, guard_summary)
    validation_errors: list[str] = []
    if int(merged_summary.get("current_surface_violation_count") or 0) > 0:
        validation_errors.append("current_surface_violations_present")
    validation_warnings: list[str] = []
    if status == "blocked_not_archive_ready":
        validation_warnings.append("no_archive_ready_candidates_due_to_active_references")
    elif status == "partial_owner_ready_pending_exact_archive_approval":
        validation_warnings.append("partial_archive_ready_only")

    return {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": status,
        "purpose": "Prepare full archive readiness for retired WF67 legacy paper-radar artifacts without performing archive/delete.",
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "input_artifacts": {
            "stale_reference_guard": rel(GUARD_REPORT),
            "reference_review": rel(REFERENCE_REVIEW),
            "archive_dry_run": rel(ARCHIVE_DRY_RUN),
        },
        "summary": merged_summary,
        "archive_apply_state": {
            "archive_apply_allowed_now": False,
            "exact_owner_approval_required": True,
            "owner_ready_now": status in {
                "owner_ready_pending_exact_archive_approval",
                "partial_owner_ready_pending_exact_archive_approval",
            },
            "reason": (
                "No candidates are archive-ready; all historical WF67 artifacts still have active/blocking references."
                if status == "blocked_not_archive_ready"
                else "Review status before approval."
            ),
        },
        "blocking_reference_families": blocking_families,
        "blocking_reference_family_counts": family_counts,
        "candidate_rows": candidates,
        "remediation_plan": remediation_plan(blocking_families),
        "owner_approval_packet_next": {
            "create_only_after": [
                "current_surface_violation_count remains 0",
                "reference review shows archive_ready_count greater than 0",
                "selected archive batch has no active code/control/current-finance references",
                "rollback manifest/dry-run is clean",
            ],
            "required_post_approval_validators": [
                "python scripts\\stale_paper_card_reference_guard.py --write --validate",
                "python scripts\\wf67_stale_paper_artifact_archive_apply.py --write --validate",
                "python scripts\\wf85_paper_deployment_notification_digest.py --write --validate",
                "python scripts\\cron_control_packet.py --write --validate",
                "python scripts\\concurrent_lane_manager.py --status --write --validate",
            ],
        },
        "validation": {
            "status": "ok" if not validation_errors else "error",
            "errors": validation_errors,
            "warnings": validation_warnings,
        },
        "stop_lines": [
            "Do not archive, delete, move, or rewrite files from this readiness packet.",
            "Do not treat old WF67 files as current deployment or approval-card truth.",
            "Do not infer capital deployment, paper execution, or owner approval from archive readiness.",
        ],
    }


def render_md(packet: dict[str, Any]) -> str:
    summary = as_dict(packet.get("summary"))
    lines = [
        "# WF67 Legacy Radar Archive Readiness",
        "",
        f"Generated: {packet.get('generated_at_utc')}",
        f"Status: `{packet.get('status')}`",
        "",
        "## Summary",
        "",
        f"- Current-surface violations: `{summary.get('current_surface_violation_count')}`",
        f"- Historical artifacts: `{summary.get('historical_artifact_count')}`",
        f"- Archive-ready now: `{summary.get('archive_ready_count')}`",
        f"- Retained/blocked: `{summary.get('retained_or_blocked_count')}`",
        f"- Active-reference blockers: `{summary.get('blocked_active_reference_count')}`",
        "",
        "## Blocking Reference Families",
        "",
    ]
    for row in as_list(packet.get("blocking_reference_families")):
        lines.append(f"- `{row.get('family')}`: `{row.get('reference_count')}` references")
    lines.extend([
        "",
        "## Archive Apply State",
        "",
        f"- Owner-ready now: `{as_dict(packet.get('archive_apply_state')).get('owner_ready_now')}`",
        f"- Archive apply allowed now: `{as_dict(packet.get('archive_apply_state')).get('archive_apply_allowed_now')}`",
        f"- Reason: {as_dict(packet.get('archive_apply_state')).get('reason')}",
        "",
        "## Remediation Plan",
        "",
    ])
    for index, row in enumerate(as_list(packet.get("remediation_plan")), start=1):
        lines.append(f"{index}. {as_dict(row).get('step')} Proof: {as_dict(row).get('proof')}")
    lines.extend([
        "",
        "## Boundary",
        "",
        "- Review-only archive readiness. No archive/delete/move/apply, no finance/canon/portfolio mutation, no capital deployment, no paper/live/brokerage/account action, and no owner approval inference.",
        "",
    ])
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--write-md", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--out", type=Path, default=OUT)
    parser.add_argument("--md-out", type=Path, default=MD_OUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    packet = build_packet()
    out = args.out if args.out.is_absolute() else ROOT / args.out
    md_out = args.md_out if args.md_out.is_absolute() else ROOT / args.md_out
    if args.write:
        atomic_write_json(out, packet)
    if args.write_md:
        md_out.parent.mkdir(parents=True, exist_ok=True)
        md_out.write_text(render_md(packet), encoding="utf-8")
    print(json.dumps({
        "status": packet.get("status"),
        "out": rel(out),
        "md_out": rel(md_out),
        "summary": packet.get("summary"),
        "archive_apply_state": packet.get("archive_apply_state"),
        "validation": packet.get("validation"),
    }, indent=2, sort_keys=True))
    if args.validate and as_dict(packet.get("validation")).get("status") != "ok":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
