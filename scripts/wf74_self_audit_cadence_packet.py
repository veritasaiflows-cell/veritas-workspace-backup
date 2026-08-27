#!/usr/bin/env python3
"""Build a review-only WF74/WF88 self-audit cadence packet.

The packet turns WF74/WF88/OTEL/scorecard proof surfaces into a small
operator-facing action map. It does not create cron jobs, mutate skills, apply
patches, change OTEL runtime/collector config, or infer owner approval.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, load_json_artifact


ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
SCHEMA = "veritas.wf74_self_audit_cadence_packet.v1"
DEFAULT_OUT = TMP / "wf74-self-audit-cadence-packet.json"
DEFAULT_MD_OUT = TMP / "wf74-self-audit-cadence-packet.md"

DEFAULT_SOURCES = {
    "wf74_opportunity_queue": TMP / "wf74-improvement-opportunity-queue.json",
    "wf74_auto_patch_proposer": TMP / "wf74-auto-patch-proposer.json",
    "improvement_ledger": TMP / "improvement-ledger-current.json",
    "model_quality_scorecard": TMP / "model-quality-scorecard.json",
    "otel_learning_loop": TMP / "otel-learning-loop.json",
    "otel_runtime_metadata_probe": TMP / "otel-runtime-metadata-probe.json",
    "implementation_token_bridge": TMP / "implementation-token-attribution-bridge.json",
    "finance_recommendation_ledger": TMP / "finance-recommendation-correctness-ledger-current.json",
    "wf88_control_packet": TMP / "wf88-os2-control-packet.json",
    "wf88_wiki_synthesis": TMP / "wf88-wiki-synthesis-packet.json",
}

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "cadence_packet_only": True,
    "proposal_generation_only": True,
    "cron_schedule_mutation_allowed": False,
    "skill_apply_allowed": False,
    "self_modification_allowed": False,
    "second_memory_tree_allowed": False,
    "otel_runtime_or_collector_mutation_allowed": False,
    "raw_prompt_or_tool_payload_capture_allowed": False,
    "finance_canon_or_portfolio_mutation_allowed": False,
    "capital_deployment_allowed": False,
    "paper_or_live_execution_allowed": False,
    "external_delivery_allowed": False,
    "owner_approval_inferred": False,
}

CADENCE_TIERS = [
    {
        "tier": "tier_1_weekly_self_audit",
        "cadence": "weekly",
        "owner": "cron_or_main_session_review_only",
        "scope": [
            "WF74 queue and decision docket",
            "improvement ledger warning and overdue follow-up state",
            "OTEL learning-loop freshness and approved-vs-observed metadata state",
            "scorecard track coverage",
            "implementation token attribution gaps",
        ],
        "artifact": "tmp/wf74-self-audit-cadence-packet.json",
        "mutation_authority": "none",
    },
    {
        "tier": "tier_2_monthly_track_review",
        "cadence": "monthly",
        "owner": "main_session",
        "scope": [
            "track usefulness and active metric coverage",
            "decision-quality process vs later-outcome scope clarity",
            "performance/token-cost measurement quality",
        ],
        "artifact": "tmp/wf74-track-review-monthly.json (proposed)",
        "mutation_authority": "none",
    },
    {
        "tier": "tier_3_quarterly_doctrine_refresh",
        "cadence": "quarterly",
        "owner": "main_session_plus_randall",
        "scope": [
            "WF74/WF88 stop lines",
            "no-auto-apply contract",
            "Skill Workshop apply boundary",
            "OTEL privacy and capture-depth boundary",
        ],
        "artifact": "Skill Workshop proposal or playbook proposal only",
        "mutation_authority": "owner_gated",
    },
]


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


def load_packet(path: Path) -> dict[str, Any]:
    payload = load_json_artifact(path)
    return payload if isinstance(payload, dict) else {}


def source_status(path: Path) -> dict[str, Any]:
    payload = load_packet(path)
    return {
        "path": rel(path),
        "exists": path.exists(),
        "status": payload.get("status"),
        "validation_status": as_dict(payload.get("validation")).get("status"),
        "generated_at_utc": payload.get("generated_at_utc"),
    }


def track_metric_counts(scorecard: dict[str, Any]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for name, track in as_dict(scorecard.get("tracks")).items():
        counts[str(name)] = len(as_dict(as_dict(track).get("metrics")))
    return dict(sorted(counts.items()))


def build_action_items(sources: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    token_summary = as_dict(sources["implementation_token_bridge"].get("summary"))
    improvement_summary = as_dict(sources["improvement_ledger"].get("summary"))
    otel_summary = as_dict(sources["otel_runtime_metadata_probe"].get("summary"))
    scorecard = sources["model_quality_scorecard"]
    auto_patch_summary = as_dict(sources["wf74_auto_patch_proposer"].get("summary"))
    wf88_summary = as_dict(sources["wf88_control_packet"].get("summary"))
    metric_counts = track_metric_counts(scorecard)

    items: list[dict[str, Any]] = []
    unclassified_supported = int(token_summary.get("unclassified_supported_runtime_gap_count") or 0)
    items.append({
        "id": "close-implementation-token-attribution-gap",
        "priority": "P1",
        "state": "fix_now" if unclassified_supported else "monitor_only",
        "signal": f"unclassified_supported_runtime_gap_count={unclassified_supported}",
        "next_action": "Require future model-lane closeouts to stamp token totals or an accepted unavailable classification; repair historical supported gaps only when evidence supports the classification.",
        "authority": "metadata_closeout_only",
    })

    followup_required = int(improvement_summary.get("followup_required_open_count") or 0)
    overdue = str(improvement_summary.get("top_improvement_sla_status") or "")
    items.append({
        "id": "route-overdue-improvement-followup",
        "priority": "P1" if followup_required else "P2",
        "state": "fix_now" if followup_required else "monitor_only",
        "signal": f"followup_required_open_count={followup_required}; top_improvement_sla_status={overdue}",
        "next_action": "Route the overdue follow-up into a named WF74/PM lane or close it only after a durable successor artifact exists.",
        "authority": "review_only_routing",
    })

    reconciliation = str(otel_summary.get("enabled_vs_observed_reconciliation") or "")
    emission_diagnosis = str(otel_summary.get("emission_path_diagnosis") or "")
    collector_age = otel_summary.get("collector_log_age_hours")
    items.append({
        "id": "reconcile-otel-approved-vs-observed",
        "priority": "P1" if reconciliation == "approved_enabled_not_observed" else "P2",
        "state": "proof_refresh" if reconciliation == "approved_enabled_not_observed" else "monitor_only",
        "signal": f"reconciliation={reconciliation or 'unknown'}; emission_path_diagnosis={emission_diagnosis or 'unknown'}; collector_log_age_hours={collector_age}",
        "next_action": "Generate or inspect a fresh local runtime event path and rerun the metadata probe; do not mutate collector/runtime config from this packet.",
        "authority": "otel_review_only",
    })

    performance_metrics = metric_counts.get("performance", 0)
    items.append({
        "id": "fill-performance-scorecard-measurement",
        "priority": "P2" if performance_metrics == 0 else "monitor",
        "state": "wire_metrics" if performance_metrics == 0 else "monitor_only",
        "signal": f"performance_metric_count={performance_metrics}",
        "next_action": "Wire performance/token/cost metric counts into the scorecard before claiming measurement completeness.",
        "authority": "review_only_metric_wiring",
    })

    items.append({
        "id": "preserve-zero-auto-apply",
        "priority": "P0",
        "state": "clean" if int(auto_patch_summary.get("auto_apply_count") or 0) == 0 else "hard_stop",
        "signal": f"auto_apply_count={auto_patch_summary.get('auto_apply_count')}; auto_apply_candidate_count={auto_patch_summary.get('auto_apply_candidate_count')}",
        "next_action": "Treat any nonzero auto-apply count as a blocker. Pending skill proposals remain owner-gated.",
        "authority": "no_auto_apply_contract",
    })

    items.append({
        "id": "preserve-recommendation-outcome-scope-labels",
        "priority": "P2",
        "state": "monitor_only",
        "signal": str(wf88_summary.get("recommendation_later_outcome_metric_scope") or "unknown"),
        "next_action": "Keep dashboards split between current process correctness and durable later market outcome grading.",
        "authority": "review_only_labeling",
    })

    return items


def build_packet(source_paths: dict[str, Path] | None = None) -> dict[str, Any]:
    paths = source_paths or DEFAULT_SOURCES
    sources = {name: load_packet(path) for name, path in paths.items()}
    source_statuses = {name: source_status(path) for name, path in paths.items()}

    token_summary = as_dict(sources["implementation_token_bridge"].get("summary"))
    improvement_summary = as_dict(sources["improvement_ledger"].get("summary"))
    otel_summary = as_dict(sources["otel_runtime_metadata_probe"].get("summary"))
    scorecard = sources["model_quality_scorecard"]
    scorecard_tracks = as_list(scorecard.get("active_tracks"))
    metric_counts = track_metric_counts(scorecard)
    auto_patch_summary = as_dict(sources["wf74_auto_patch_proposer"].get("summary"))
    queue_summary = as_dict(sources["wf74_opportunity_queue"].get("summary"))
    recommendation_summary = as_dict(sources["wf88_control_packet"].get("summary"))

    action_items = build_action_items(sources)
    summary = {
        "cadence_codified": True,
        "cadence_tier_count": len(CADENCE_TIERS),
        "no_auto_apply_enforced": int(auto_patch_summary.get("auto_apply_count") or 0) == 0,
        "auto_apply_count": int(auto_patch_summary.get("auto_apply_count") or 0),
        "auto_apply_candidate_count": int(auto_patch_summary.get("auto_apply_candidate_count") or 0),
        "owner_gated_plan_count": int(auto_patch_summary.get("owner_gated_plan_count") or 0),
        "skill_workshop_request_count": int(auto_patch_summary.get("skill_workshop_request_count") or 0),
        "pending_skill_snapshot_required_before_apply_decision": True,
        "wf74_opportunity_count": int(queue_summary.get("opportunity_count") or 0),
        "wf74_top_opportunity_id": queue_summary.get("top_opportunity_id"),
        "followup_required_open_count": int(improvement_summary.get("followup_required_open_count") or 0),
        "top_improvement_sla_status": improvement_summary.get("top_improvement_sla_status"),
        "active_scorecard_tracks": scorecard_tracks,
        "scorecard_track_metric_counts": metric_counts,
        "performance_metric_count": metric_counts.get("performance", 0),
        "implementation_token_gap_count": int(token_summary.get("implementation_token_gap_count") or 0),
        "unclassified_supported_runtime_gap_count": int(token_summary.get("unclassified_supported_runtime_gap_count") or 0),
        "implementation_gap_resolution_status": token_summary.get("gap_resolution_status"),
        "otel_runtime_metadata_observed": otel_summary.get("runtime_metadata_observed"),
        "otel_metadata_depth_approved_enabled": otel_summary.get("metadata_depth_approved_enabled"),
        "otel_enabled_vs_observed_reconciliation": otel_summary.get("enabled_vs_observed_reconciliation"),
        "otel_emission_path_diagnosis": otel_summary.get("emission_path_diagnosis"),
        "otel_collector_log_age_hours": otel_summary.get("collector_log_age_hours"),
        "recommendation_later_outcome_metric_scope": recommendation_summary.get("recommendation_later_outcome_metric_scope"),
        "recommendation_current_preview_later_outcome_graded_rows": recommendation_summary.get("recommendation_current_preview_later_outcome_graded_rows"),
        "recommendation_durable_later_outcome_graded_rows": recommendation_summary.get("recommendation_durable_later_outcome_graded_rows"),
        "action_item_count": len(action_items),
        "fix_now_count": sum(1 for item in action_items if item.get("state") == "fix_now"),
        "hard_stop_count": sum(1 for item in action_items if item.get("state") == "hard_stop"),
        "next_safe_action": "Run the Tier 1 packet in the existing review cadence; do not add cron, apply skills, or mutate runtime/config from this artifact.",
    }
    packet = {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "pending_validation",
        "purpose": "Review-only WF74/WF88 self-audit cadence and action-scope packet.",
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "cadence_tiers": CADENCE_TIERS,
        "source_artifacts": source_statuses,
        "summary": summary,
        "action_items": action_items,
    }
    packet["validation"] = validate_packet(packet)
    packet["status"] = "ok" if packet["validation"]["status"] == "ok" else "self_audit_warning_review_only"
    return packet


def validate_packet(packet: dict[str, Any]) -> dict[str, Any]:
    summary = as_dict(packet.get("summary"))
    boundary = as_dict(packet.get("authority_boundary"))
    errors: list[str] = []
    warnings: list[str] = []

    if boundary.get("review_only") is not True:
        errors.append("review_only_boundary_missing")
    for key in (
        "cron_schedule_mutation_allowed",
        "skill_apply_allowed",
        "self_modification_allowed",
        "otel_runtime_or_collector_mutation_allowed",
        "finance_canon_or_portfolio_mutation_allowed",
        "paper_or_live_execution_allowed",
        "owner_approval_inferred",
    ):
        if boundary.get(key) is not False:
            errors.append(f"boundary_flag_not_false:{key}")
    if int(summary.get("auto_apply_count") or 0) != 0:
        errors.append("auto_apply_count_nonzero")
    if int(summary.get("unclassified_supported_runtime_gap_count") or 0) > 0:
        warnings.append(f"unclassified_supported_runtime_gap_count:{summary.get('unclassified_supported_runtime_gap_count')}")
    if int(summary.get("followup_required_open_count") or 0) > 0:
        warnings.append(f"followup_required_open_count:{summary.get('followup_required_open_count')}")
    if summary.get("otel_enabled_vs_observed_reconciliation") == "approved_enabled_not_observed":
        warnings.append("otel_depth_enabled_but_runtime_metadata_not_observed")
    if summary.get("otel_emission_path_diagnosis") == "collector_debug_log_stale_no_current_runtime_metadata_source":
        warnings.append("otel_runtime_metadata_source_stale")
    if int(summary.get("performance_metric_count") or 0) == 0:
        warnings.append("performance_scorecard_metric_count_zero")

    return {
        "status": "error" if errors else ("warning" if warnings else "ok"),
        "errors": errors,
        "warnings": warnings,
    }


def render_markdown(packet: dict[str, Any]) -> str:
    summary = as_dict(packet.get("summary"))
    lines = [
        "# WF74 / WF88 Self-Audit Cadence Packet",
        "",
        f"- Generated: {packet.get('generated_at_utc')}",
        f"- Status: `{packet.get('status')}` / validation `{as_dict(packet.get('validation')).get('status')}`",
        f"- Cadence tiers: `{summary.get('cadence_tier_count')}`",
        f"- Auto-apply count: `{summary.get('auto_apply_count')}`",
        f"- WF74 top opportunity: `{summary.get('wf74_top_opportunity_id')}`",
        f"- Follow-up-required open count: `{summary.get('followup_required_open_count')}`",
        f"- Implementation token gaps / unclassified supported runtime gaps: `{summary.get('implementation_token_gap_count')}` / `{summary.get('unclassified_supported_runtime_gap_count')}`",
        f"- OTEL approved/enabled vs observed: `{summary.get('otel_enabled_vs_observed_reconciliation')}`",
        f"- OTEL emission diagnosis / collector log age hours: `{summary.get('otel_emission_path_diagnosis')}` / `{summary.get('otel_collector_log_age_hours')}`",
        f"- Scorecard track metric counts: `{summary.get('scorecard_track_metric_counts')}`",
        f"- Recommendation later-outcome scope: `{summary.get('recommendation_later_outcome_metric_scope')}`",
        "",
        "## Cadence",
        "",
    ]
    for tier in as_list(packet.get("cadence_tiers")):
        item = as_dict(tier)
        lines.append(f"- `{item.get('tier')}`: {item.get('cadence')} / {item.get('owner')} / {item.get('mutation_authority')}")
    lines.extend(["", "## Actions", ""])
    for action in as_list(packet.get("action_items")):
        item = as_dict(action)
        lines.append(f"- `{item.get('id')}`: `{item.get('priority')}` / `{item.get('state')}` - {item.get('next_action')}")
    lines.extend(["", "## Boundary", ""])
    lines.append("Review-only cadence and action-scope packet. No cron schedule, skill apply, self-modification, OTEL runtime/collector config, finance/canon/portfolio, paper/live/account, external delivery, or owner approval authority.")
    return "\n".join(lines) + "\n"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--md-out", type=Path, default=DEFAULT_MD_OUT)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--write-md", action="store_true")
    parser.add_argument("--validate", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    packet = build_packet()
    out_path = args.out if args.out.is_absolute() else ROOT / args.out
    md_path = args.md_out if args.md_out.is_absolute() else ROOT / args.md_out
    if args.write:
        atomic_write_json(out_path, packet)
    if args.write_md:
        md_path.parent.mkdir(parents=True, exist_ok=True)
        md_path.write_text(render_markdown(packet), encoding="utf-8")
    print(
        f"status={packet.get('status')} validation={as_dict(packet.get('validation')).get('status')} "
        f"fix_now={as_dict(packet.get('summary')).get('fix_now_count')} hard_stop={as_dict(packet.get('summary')).get('hard_stop_count')}"
    )
    if args.validate and as_dict(packet.get("validation")).get("status") == "error":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
