#!/usr/bin/env python3
"""Route finance response-quality gaps into review-only repair proposals.

This WF74 loop reads the finance response-quality slice plus the improvement
queue and emits deterministic repair proposals. It does not mutate finance
canon, portfolio, cash, sizing, risk, deployment, ticker-card, paper/live, or
account surfaces.
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

SLICE = TMP / "finance-response-quality-slice.json"
QUEUE = TMP / "wf74-improvement-opportunity-queue.json"
OUT_JSON = TMP / "finance-response-quality-repair-loop.json"
OUT_MD = OUT_JSON.with_suffix(".md")

SCHEMA = "veritas.finance_response_quality_repair_loop.v1"

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "local_only": True,
    "repair_proposal_loop_only": True,
    "proposal_generation_only": True,
    "auto_apply_allowed": False,
    "code_mutation_allowed": False,
    "skill_application_allowed": False,
    "collector_config_mutation_allowed": False,
    "runtime_config_mutation_allowed": False,
    "finance_canon_or_portfolio_mutation_allowed": False,
    "canon_or_portfolio_mutation_allowed": False,
    "portfolio_or_canon_mutation_allowed": False,
    "cash_or_sizing_mutation_allowed": False,
    "risk_rule_mutation_allowed": False,
    "ticker_card_mutation_allowed": False,
    "universe_mutation_allowed": False,
    "deployment_surface_mutation_allowed": False,
    "capital_deployment_allowed": False,
    "capital_deployment_approved": False,
    "trade_or_execution_approved": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "money_movement_allowed": False,
    "external_delivery_allowed": False,
    "raw_prompt_or_response_capture_allowed": False,
    "tool_payload_capture_allowed": False,
    "owner_approval_inferred": False,
}

FORBIDDEN_TRUE_KEYS = {key for key, value in AUTHORITY_BOUNDARY.items() if value is False}

REPAIR_TYPE_DEFAULTS = {
    "blocked_archetype_repair": {
        "priority": 96,
        "gate": "scoped finance-quality repair gate required before any implementation",
        "validation_command": "python scripts\\finance_response_quality_slice.py --write --write-md --validate",
    },
    "warning_archetype_repair": {
        "priority": 78,
        "gate": "standing review-only quality gate; scoped implementation lane required for edits",
        "validation_command": "python scripts\\finance_response_quality_slice.py --write --write-md --validate",
    },
    "source_freshness_repair": {
        "priority": 90,
        "gate": "standing/scoped source-freshness repair gate; no canon or portfolio mutation from WF74",
        "validation_command": "python scripts\\trade_grade_repair_conveyor.py --write --validate",
    },
    "source_open_repair": {
        "priority": 88,
        "gate": "standing/scoped source-open repair gate; no external delivery or raw payload capture",
        "validation_command": "python scripts\\wf78_source_open_repair_executor.py --tier all --write --validate",
    },
    "remediation_track_repair": {
        "priority": 86,
        "gate": "standing/scoped remediation proposal gate; exact validator proof required before apply",
        "validation_command": "python scripts\\finance_response_quality_slice.py --write --write-md --validate",
    },
}

ROLLBACK_PROOF_REQUIREMENT = (
    "Proposal packet only. Any later finance repair must have exact scoped artifact, "
    "validator proof, backup/rollback plan where files or canon-like surfaces are touched, "
    "post-repair validation, and audit proof; this loop itself must not mutate finance state."
)


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


def as_int(value: Any) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return 0


def stable_id(*parts: Any) -> str:
    seed = "|".join(str(part or "") for part in parts)
    return hashlib.sha256(seed.encode("utf-8")).hexdigest()[:12]


def load_inputs(slice_path: Path = SLICE, queue_path: Path = QUEUE) -> dict[str, Any]:
    return {
        "finance_response_quality_slice": as_dict(load_json_artifact(slice_path)),
        "improvement_opportunity_queue": as_dict(load_json_artifact(queue_path)),
    }


def authority_true_paths(value: Any, prefix: str = "") -> list[str]:
    paths: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{prefix}.{key}" if prefix else str(key)
            if key in FORBIDDEN_TRUE_KEYS and child is True:
                paths.append(child_path)
            paths.extend(authority_true_paths(child, child_path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            paths.extend(authority_true_paths(child, f"{prefix}[{index}]"))
    return paths


def finance_queue_opportunities(queue: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for row in as_list(queue.get("opportunities")):
        item = as_dict(row)
        if item.get("category") == "finance_mutation" or item.get("proposal_gate") == "finance_repair_proposal_only":
            rows.append(item)
    return rows


def source_artifacts(slice_payload: dict[str, Any], queue_payload: dict[str, Any]) -> dict[str, str]:
    artifacts = {
        "finance_response_quality_slice": rel(SLICE),
        "improvement_opportunity_queue": rel(QUEUE),
    }
    for key, value in as_dict(slice_payload.get("source_artifacts")).items():
        artifacts[f"slice.{key}"] = str(value)
    for key, value in as_dict(queue_payload.get("source_artifacts")).items():
        if key in {"finance_response", "wf74_runner", "pm_control"}:
            artifacts[f"queue.{key}"] = str(value)
    return dict(sorted(artifacts.items()))


def proposal(
    *,
    repair_type: str,
    affected_gap: str,
    affected_archetype: str | None,
    source_artifact_keys: list[str],
    evidence: dict[str, Any],
    source_opportunity_ids: list[str] | None = None,
    priority_boost: int = 0,
) -> dict[str, Any]:
    defaults = REPAIR_TYPE_DEFAULTS[repair_type]
    priority = min(100, int(defaults["priority"]) + priority_boost)
    proposal_id = f"wf74-finance-repair-{stable_id(repair_type, affected_gap, affected_archetype)}"
    return {
        "schema": "veritas.finance_response_quality_repair_proposal.v1",
        "proposal_id": proposal_id,
        "priority": priority,
        "repair_type": repair_type,
        "affected_archetype": affected_archetype,
        "affected_gap": affected_gap,
        "source_artifact_keys": sorted(set(source_artifact_keys)),
        "source_opportunity_ids": sorted(set(source_opportunity_ids or [])),
        "evidence": evidence,
        "recommended_action": recommended_action(repair_type, affected_gap),
        "validation_command": defaults["validation_command"],
        "standing_or_scoped_gate_requirement": defaults["gate"],
        "rollback_or_proof_requirement": ROLLBACK_PROOF_REQUIREMENT,
        "no_mutation_authority_flags": AUTHORITY_BOUNDARY.copy(),
    }


def recommended_action(repair_type: str, affected_gap: str) -> str:
    if repair_type == "source_freshness_repair":
        return "Refresh or repair the stale source-freshness rows, then rerun the WF85 repair conveyor and response-quality slice."
    if repair_type == "source_open_repair":
        return "Route source-open blockers through WF78/WF85 repair, preserving source labels and refusing stale precision until clean."
    if repair_type in {"blocked_archetype_repair", "warning_archetype_repair"}:
        return f"Repair the response-quality archetype gap `{affected_gap}` and prove the slice returns to ok without authority expansion."
    return f"Turn remediation track `{affected_gap}` into a bounded repair task with validator proof before any future mutation."


def build_proposals(slice_payload: dict[str, Any], queue_payload: dict[str, Any]) -> list[dict[str, Any]]:
    summary = as_dict(slice_payload.get("summary"))
    source_state = as_dict(slice_payload.get("source_state"))
    finance_opportunities = finance_queue_opportunities(queue_payload)
    source_opportunity_ids = [str(row.get("opportunity_id")) for row in finance_opportunities if row.get("opportunity_id")]
    proposals: list[dict[str, Any]] = []

    for row in as_list(slice_payload.get("archetypes")):
        archetype = as_dict(row)
        status = str(archetype.get("status") or "")
        if status not in {"blocked", "warning"}:
            continue
        failed = as_list(archetype.get("failed_required_checks")) or ["quality_score_warning"]
        repair_type = "blocked_archetype_repair" if status == "blocked" else "warning_archetype_repair"
        for failed_check in failed:
            proposals.append(proposal(
                repair_type=repair_type,
                affected_archetype=str(archetype.get("archetype_id")),
                affected_gap=str(failed_check),
                source_artifact_keys=["finance_response_quality_slice"],
                source_opportunity_ids=source_opportunity_ids,
                evidence={
                    "archetype_status": status,
                    "quality_score": archetype.get("quality_score"),
                    "failed_required_checks": failed,
                },
            ))

    freshness_blocked = as_int(summary.get("source_freshness_blocked_count") or source_state.get("source_freshness_blocked_count"))
    source_open_blocked = as_int(summary.get("source_open_blocked_count") or source_state.get("source_open_blocked_count"))
    if freshness_blocked:
        proposals.append(proposal(
            repair_type="source_freshness_repair",
            affected_archetype="staleness_refusal_answer",
            affected_gap="source_freshness_blocked_count",
            source_artifact_keys=["finance_response_quality_slice", "slice.source_freshness_gate", "queue.finance_response"],
            source_opportunity_ids=source_opportunity_ids,
            evidence={
                "source_freshness_blocked_count": freshness_blocked,
                "source_freshness_status": source_state.get("source_freshness_status"),
                "source_freshness_validation": source_state.get("source_freshness_validation"),
            },
            priority_boost=min(5, freshness_blocked),
        ))
    if source_open_blocked:
        proposals.append(proposal(
            repair_type="source_open_repair",
            affected_archetype="staleness_refusal_answer",
            affected_gap="source_open_blocked_count",
            source_artifact_keys=["finance_response_quality_slice", "slice.source_freshness_gate", "queue.finance_response"],
            source_opportunity_ids=source_opportunity_ids,
            evidence={
                "source_open_blocked_count": source_open_blocked,
                "source_freshness_status": source_state.get("source_freshness_status"),
                "source_freshness_validation": source_state.get("source_freshness_validation"),
            },
            priority_boost=min(5, source_open_blocked),
        ))

    for track in as_list(slice_payload.get("remediation_tracks")):
        item = as_dict(track)
        if item.get("status") != "needs_repair":
            continue
        track_id = str(item.get("track_id") or "unknown_remediation_track")
        proposals.append(proposal(
            repair_type="remediation_track_repair",
            affected_archetype=None,
            affected_gap=track_id,
            source_artifact_keys=["finance_response_quality_slice"],
            source_opportunity_ids=source_opportunity_ids,
            evidence={
                "track_id": track_id,
                "owner_workflow": item.get("owner_workflow"),
                "current_gap_count": item.get("current_gap_count"),
                "target_next_checkpoint_count": item.get("target_next_checkpoint_count"),
                "next_commands": item.get("next_commands"),
            },
            priority_boost=min(4, as_int(item.get("current_gap_count"))),
        ))

    deduped = {row["proposal_id"]: row for row in proposals}
    return sorted(deduped.values(), key=lambda row: (-as_int(row.get("priority")), str(row.get("proposal_id"))))


def build_payload(inputs: dict[str, Any]) -> dict[str, Any]:
    slice_payload = as_dict(inputs.get("finance_response_quality_slice"))
    queue_payload = as_dict(inputs.get("improvement_opportunity_queue"))
    proposals = build_proposals(slice_payload, queue_payload)
    by_type: dict[str, int] = {}
    for row in proposals:
        repair_type = str(row.get("repair_type"))
        by_type[repair_type] = by_type.get(repair_type, 0) + 1
    payload = {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "ok" if proposals else "noop_ok",
        "purpose": "Route WF74 finance response-quality gaps into bounded repair proposals without mutation authority.",
        "source_artifacts": source_artifacts(slice_payload, queue_payload),
        "summary": {
            "proposal_count": len(proposals),
            "high_priority_count": sum(1 for row in proposals if as_int(row.get("priority")) >= 85),
            "by_repair_type": dict(sorted(by_type.items())),
            "blocked_archetype_count": as_dict(slice_payload.get("summary")).get("blocked_archetype_count", 0),
            "warning_archetype_count": as_dict(slice_payload.get("summary")).get("warning_archetype_count", 0),
            "source_freshness_blocked_count": as_dict(slice_payload.get("summary")).get("source_freshness_blocked_count", 0),
            "source_open_blocked_count": as_dict(slice_payload.get("summary")).get("source_open_blocked_count", 0),
            "remediation_tracks_needing_repair": as_dict(slice_payload.get("summary")).get("remediation_tracks_needing_repair", 0),
            "next_safe_action": "Review repair proposals; apply nothing from this loop without standing/scoped gate, validator proof, rollback/proof, and authority guard.",
        },
        "proposals": proposals,
        "blocked_actions": [
            "no finance canon, portfolio, cash, sizing, risk, universe, ticker-card, or deployment-surface mutation",
            "no capital deployment approval or owner approval inference",
            "no paper/live submit, cancel, replace, sell, brokerage, account, or money movement action",
            "no raw prompt, raw response, customer, account, or tool-payload capture",
            "no auto-apply from WF74",
        ],
        "authority_boundary": AUTHORITY_BOUNDARY.copy(),
    }
    payload["validation"] = validate_payload(payload, inputs)
    if payload["validation"]["status"] == "error":
        payload["status"] = "blocked"
    return payload


def validate_payload(payload: dict[str, Any], inputs: dict[str, Any] | None = None) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    boundary = as_dict(payload.get("authority_boundary"))
    for key, expected in AUTHORITY_BOUNDARY.items():
        if boundary.get(key) is not expected:
            errors.append(f"authority_boundary_{key}_not_{str(expected).lower()}")
    source_drift = authority_true_paths(inputs or {})
    if source_drift:
        errors.append("source_authority_drift_detected:" + ",".join(source_drift[:20]))
    output_drift = authority_true_paths(payload)
    if output_drift:
        errors.append("output_authority_drift_detected:" + ",".join(output_drift[:20]))
    for row in as_list(payload.get("proposals")):
        proposal_id = as_dict(row).get("proposal_id")
        if not proposal_id:
            errors.append("proposal_missing_id")
        if not as_dict(row).get("repair_type"):
            errors.append(f"proposal_missing_repair_type:{proposal_id}")
        if not as_dict(row).get("validation_command"):
            errors.append(f"proposal_missing_validation_command:{proposal_id}")
        if not as_dict(row).get("standing_or_scoped_gate_requirement"):
            errors.append(f"proposal_missing_gate_requirement:{proposal_id}")
        if not as_dict(row).get("rollback_or_proof_requirement"):
            errors.append(f"proposal_missing_rollback_or_proof_requirement:{proposal_id}")
    if not as_list(payload.get("proposals")):
        warnings.append("no_repair_proposals_generated")
    return {"status": "error" if errors else "warning" if warnings else "ok", "errors": errors, "warnings": warnings}


def render_md(payload: dict[str, Any]) -> str:
    summary = as_dict(payload.get("summary"))
    lines = [
        "# Finance Response Quality Repair Loop",
        "",
        f"- Generated: {payload.get('generated_at_utc')}",
        f"- Status: {payload.get('status')}",
        f"- Proposals: {summary.get('proposal_count')}",
        f"- High priority: {summary.get('high_priority_count')}",
        f"- Source freshness blocked: {summary.get('source_freshness_blocked_count')}",
        f"- Remediation tracks needing repair: {summary.get('remediation_tracks_needing_repair')}",
        "",
        "## Repair Proposals",
    ]
    for row in as_list(payload.get("proposals")):
        lines.append(
            f"- {row.get('priority')} | {row.get('repair_type')} | "
            f"{row.get('affected_archetype') or 'remediation'} | {row.get('affected_gap')} | `{row.get('proposal_id')}`"
        )
    if not as_list(payload.get("proposals")):
        lines.append("- No repair proposals generated.")
    lines.extend(["", "## Blocked Actions"])
    for item in as_list(payload.get("blocked_actions")):
        lines.append(f"- {item}")
    lines.append("")
    lines.append("Boundary: repair/proposal packet only; no finance state, canon, portfolio, capital, execution, account, or owner-approval authority.")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--write-md", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--json-out", type=Path, default=OUT_JSON)
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args(argv)

    out = args.json_out if args.json_out.is_absolute() else ROOT / args.json_out
    payload = build_payload(load_inputs())
    if args.write:
        atomic_write_json(out, payload)
        if args.write_md:
            atomic_write_text(out.with_suffix(".md") if out != OUT_JSON else OUT_MD, render_md(payload))

    if not args.quiet:
        print(
            "status={status} validation={validation} proposals={proposals} high_priority={high}".format(
                status=payload["status"],
                validation=payload["validation"]["status"],
                proposals=payload["summary"]["proposal_count"],
                high=payload["summary"]["high_priority_count"],
            )
        )
        for warning in as_list(payload["validation"].get("warnings")):
            print(f"  [warning] {warning}")
        for error in as_list(payload["validation"].get("errors")):
            print(f"  [error] {error}")

    if args.validate and payload["validation"]["status"] == "error":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
