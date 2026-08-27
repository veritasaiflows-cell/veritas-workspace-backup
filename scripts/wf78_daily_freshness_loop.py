#!/usr/bin/env python3
"""WF78 daily freshness loop.

Runs the review-only WF78 freshness chain in the right order and writes a compact
digest. This is safe for cron/daily use because every called script is a proof
or routing surface and all authority flags remain false.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from wf_manifest import as_runner_tuples, build_daily_steps, selected_phases, steps_for_phases
from wf_registry import SCHEMA_WF78_DAILY_FRESHNESS_LOOP, TMP, WF78_DAILY_FRESHNESS_LOOP
from wf_registry import WF78_INTELLIGENCE_ROUTING_V2
from wf_runner_lib import (
    as_dict,
    atomic_write_json,
    authority_true_paths,
    DANGEROUS_ARTIFACT_AUTHORITY_KEYS,
    load_dict,
    rel,
    run_dependency_batches,
    run_serial_chain,
    utc_now,
)

ROOT = Path(__file__).resolve().parents[1]
OUT = WF78_DAILY_FRESHNESS_LOOP
SCHEMA = SCHEMA_WF78_DAILY_FRESHNESS_LOOP
V2_COMPAT_PHASE = "daily_core_v2"

# Phase and step definitions live in scripts/wf_manifest.py.

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "daily_freshness_routing_only": True,
    "automated_non_capital_routing_allowed": True,
    "ticker_card_mutation_allowed": False,
    "canon_or_portfolio_mutation_allowed": False,
    "sql_canon_mutation_allowed": False,
    "customer_or_external_delivery_allowed": False,
    "config_auth_runtime_mutation_allowed": False,
    "capital_deployment_allowed": False,
    "capital_deployment_approved": False,
    "trade_or_execution_allowed": False,
    "trade_or_execution_approved": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "money_movement_allowed": False,
    "owner_approval_inferred": False,
}


def parse_utc(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).astimezone(timezone.utc)
    except Exception:
        return None


def load(path: Path) -> dict[str, Any]:
    return load_dict(path)


def artifact_authority_findings(artifacts: dict[str, dict[str, Any]]) -> list[str]:
    findings: list[str] = []
    for name, payload in artifacts.items():
        for path in authority_true_paths(payload, false_keys=DANGEROUS_ARTIFACT_AUTHORITY_KEYS):
            findings.append(f"{name}:{path}")
    return findings


def all_steps(args: argparse.Namespace) -> list[tuple[str, list[str], int]]:
    return as_runner_tuples(
        build_daily_steps(
            skip_provider_refresh=bool(args.skip_provider_refresh),
            full_answer_mode=str(args.full_answer_mode),
        )
    )


def _requested_phase_names(args: argparse.Namespace) -> set[str]:
    names: set[str] = set()
    for raw in args.phase or [V2_COMPAT_PHASE]:
        for part in str(raw).split(","):
            name = part.strip()
            if name:
                names.add(name)
    return names


def _use_v2_compat(args: argparse.Namespace) -> bool:
    names = _requested_phase_names(args)
    return not names or names == {V2_COMPAT_PHASE}


def _step_dependencies(args: argparse.Namespace, runnable_names: set[str]) -> dict[str, tuple[str, ...]]:
    return {
        step.name: tuple(dep for dep in step.depends_on if dep in runnable_names)
        for step in build_daily_steps(
            skip_provider_refresh=bool(args.skip_provider_refresh),
            full_answer_mode=str(args.full_answer_mode),
        )
        if step.name in runnable_names
    }

def build_steps(args: argparse.Namespace) -> list[tuple[str, list[str], int]]:
    runnable, _skipped, _phases = steps_for_phases(
        args.phase,
        skip_provider_refresh=bool(args.skip_provider_refresh),
        full_answer_mode=str(args.full_answer_mode),
    )
    return as_runner_tuples(runnable)


def build_v2_compat_report(args: argparse.Namespace) -> dict[str, Any]:
    command = [
        "python",
        "scripts\\wf78_intelligence_routing_v2.py",
        "--layer",
        "daily_core_v2",
        "--fail-on-budget-exceeded",
        "--write",
        "--validate",
    ]
    started = time.perf_counter()
    if bool(getattr(args, "dry_run", False)):
        completed = subprocess.CompletedProcess(command, 0, stdout="dry-run", stderr="")
    else:
        completed = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=180)
    duration_ms = int((time.perf_counter() - started) * 1000)
    v2 = load(WF78_INTELLIGENCE_ROUTING_V2)
    v2_validation = as_dict(v2.get("validation"))
    errors: list[str] = []
    if completed.returncode != 0:
        errors.append("wf78_intelligence_routing_v2_failed")
    if v2_validation.get("status") not in (None, "ok"):
        errors.append(f"wf78_intelligence_routing_v2_validation_{v2_validation.get('status')}")
    authority_findings = artifact_authority_findings({
        "wf78_intelligence_routing_v2": v2,
        "wf78_auto_tier_routing": load(TMP / "wf78-auto-tier-routing.json"),
        "wf78_tier_weighted_freshness_resolution": load(TMP / "wf78-tier-weighted-freshness-resolution.json"),
        "canonical_finance_data_plane": load(TMP / "canonical-finance-data-plane.json"),
        "trade_grade_decision_cards": load(TMP / "trade-grade-decision-cards.json"),
        "tier_ab_band_freshness_cron_guard": load(TMP / "tier-ab-band-freshness-cron-guard.json"),
    })
    if authority_findings:
        errors.append("artifact authority drift detected")
    return {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "blocked" if errors else "ok",
        "purpose": "Compatibility wrapper for the current WF78 daily-core-v2 review-only freshness route.",
        "compatibility_mode": V2_COMPAT_PHASE,
        "authority_boundary": AUTHORITY_BOUNDARY,
        "parameters": {
            "skip_provider_refresh": bool(args.skip_provider_refresh),
            "requested_phase": args.phase or [V2_COMPAT_PHASE],
            "selected_phases": [V2_COMPAT_PHASE],
            "dry_run": bool(getattr(args, "dry_run", False)),
            "parallel": int(getattr(args, "parallel", 1)),
        },
        "steps": [{
            "name": "wf78_intelligence_routing_v2_daily_core",
            "command": command,
            "ok": completed.returncode == 0,
            "returncode": completed.returncode,
            "duration_ms": duration_ms,
            "stdout_tail": (completed.stdout or "")[-1000:],
            "stderr_tail": (completed.stderr or "")[-1000:],
        }],
        "skipped_steps": [{
            "name": "legacy_all_phase_daily_freshness_loop",
            "reason": "compatibility_default_uses_time_boxed_daily_core_v2; pass --phase all for the legacy broad runner",
        }],
        "dependency_batches": [["wf78_intelligence_routing_v2_daily_core"]],
        "summary": {
            "steps_run": 1,
            "steps_skipped": 1,
            "failed_steps": [] if completed.returncode == 0 else ["wf78_intelligence_routing_v2_daily_core"],
            "total_step_duration_ms": duration_ms,
            "authority_drift_count": len(authority_findings),
            "v2_status": v2.get("status"),
            "v2_summary": v2.get("summary"),
            "next_safe_action": "Use the time-boxed WF78 daily-core-v2 route for normal green pickup; reserve --phase all for explicit broad audits.",
        },
        "validation": {
            "status": "blocked" if errors else "ok",
            "errors": errors,
            "warnings": [],
            "authority_drift_paths": authority_findings,
        },
        "stop_lines": [
            "Daily loop is review-only and creates proof/routing artifacts only.",
            "No capital deployment, paper/live execution, brokerage/account action, money movement, customer output, canon/portfolio mutation, or owner approval inference.",
        ],
    }


def build_report(args: argparse.Namespace) -> dict[str, Any]:
    if _use_v2_compat(args):
        return build_v2_compat_report(args)
    runnable_defs, skipped_steps, phases = steps_for_phases(
        args.phase,
        skip_provider_refresh=bool(args.skip_provider_refresh),
        full_answer_mode=str(args.full_answer_mode),
    )
    runnable_steps = as_runner_tuples(runnable_defs)
    runnable_names = {name for name, _command, _timeout in runnable_steps}
    dependencies = _step_dependencies(args, runnable_names)
    if getattr(args, "parallel", 1) > 1:
        steps, dependency_batches, dependency_errors = run_dependency_batches(
            runnable_steps,
            dependencies=dependencies,
            max_workers=int(args.parallel),
            dry_run=bool(getattr(args, "dry_run", False)),
        )
    else:
        steps = run_serial_chain(runnable_steps, dry_run=bool(getattr(args, "dry_run", False)))
        dependency_batches = [[name] for name, _command, _timeout in runnable_steps]
        dependency_errors = []
    def _summary_int(payload: dict[str, Any], default: int = 0, *keys: str) -> int:
        current: Any = payload
        for key in keys:
            if not isinstance(current, dict):
                return default
            current = current.get(key, {})
        return current if isinstance(current, int) else default

    ledger = load(TMP / "wf78-ticker-freshness-ledger.json")
    executor = load(TMP / "wf78-source-open-repair-execution.json")
    packets = load(TMP / "wf78-source-open-work-packets.json")
    sizing_review = load(TMP / "wf78-position-sizing-surface-review.json")
    deployment_review = load(TMP / "wf78-deployment-readiness-review.json")
    source_capture_review = load(TMP / "wf78-source-artifact-capture-review.json")
    integration_proposal = load(TMP / "wf78-position-sizing-integration-proposal.json")
    tier_a_owner_proposal = load(TMP / "wf78-tier-a-owner-readiness-proposals.json")
    band_context_repair = load(TMP / "wf78-missing-band-context-repair.json")
    source_requirements = load(TMP / "wf78-source-capture-requirements-queue.json")
    official_discovery = load(TMP / "wf78-official-source-discovery.json")
    registry_proposal = load(TMP / "wf78-official-registry-proposal.json")
    registry_apply_preview = load(TMP / "wf78-official-registry-apply-preview.json")
    owner_lineage_queue = load(TMP / "wf78-promotion-owner-lineage-queue.json")
    contract_guard = load(TMP / "wf78-contract-state-guard.json")
    owner_lineage_discovery = load(TMP / "wf78-owner-lineage-discovery.json")
    owner_lineage_proposal = load(TMP / "wf78-owner-lineage-proposal.json")
    repair_scoreboard = load(TMP / "wf78-repair-debt-scoreboard.json")
    scaleout_policy = load(TMP / "wf78-scaleout-policy-dry-run.json")
    ph_packet = load(TMP / "wf78-ph-owner-review-candidate-packet.json")
    invalidation_queue = load(TMP / "wf78-tier-a-invalidation-review-queue.json")
    official_source_capture = load(TMP / "wf78-official-source-capture-packet.json")
    next_integration = load(TMP / "wf78-next-owner-review-and-source-capture-integration.json")
    tier_c_band_status = load(TMP / "tier-c-band-status.json")
    family = load(TMP / "wf78-evidence-family-repair.json")
    tier_weighted_resolution = load(TMP / "wf78-tier-weighted-freshness-resolution.json")
    tier_c_attention_trigger = load(TMP / "wf78-tier-c-attention-trigger.json")
    tier_c_hold_recheck = load(TMP / "wf78-tier-c-hold-recheck.json")
    tier_c_to_b_pipeline = load(TMP / "wf78-tier-c-to-b-auto-promotion-pipeline.json")
    auto_router = load(TMP / "wf78-auto-tier-routing.json")
    truth_layer_map = load(TMP / "wf78-truth-layer-map.json")
    tier_semantics_guard = load(TMP / "wf78-tier-semantics-guard.json")
    tier_b_research_packet = load(TMP / "wf78-tier-b-research-packets.json")
    tier_b_phase2_eval = load(TMP / "wf78-tier-b-research-packet-phase2-eval.json")
    tier_a_competitive_gate = load(TMP / "wf78-tier-a-competitive-promotion-gate.json")
    routing_delta = load(TMP / "wf78-routing-delta.json")
    wf84_packet = load(TMP / "canonical-finance-data-plane.json")
    wf84_validation = load(TMP / "canonical-finance-data-plane-validation.json")
    wf84_phase6_10 = load(TMP / "canonical-finance-data-plane-phase6-10.json")
    wf84_retirement = load(TMP / "canonical-finance-data-plane-retirement-readiness.json")
    decision_cards = load(TMP / "trade-grade-decision-cards.json")
    repair_conveyor = load(TMP / "trade-grade-repair-conveyor.json")
    tier_ab_guard = load(TMP / "tier-ab-band-freshness-cron-guard.json")
    ticker_card_refresh_gate = load(TMP / "finance-ticker-card-refresh-gate.json")
    fundamentals = load(TMP / "fundamental-metrics-current.json")
    fundamentals_validation = load(TMP / "fundamental-metrics-validation.json")
    authority_findings = artifact_authority_findings({
        "wf78_auto_tier_routing": auto_router,
        "wf78_tier_weighted_freshness_resolution": tier_weighted_resolution,
        "canonical_finance_data_plane": wf84_packet,
        "trade_grade_decision_cards": decision_cards,
        "tier_ab_band_freshness_cron_guard": tier_ab_guard,
    })
    fundamentals_generated_at = parse_utc(fundamentals.get("generated_at_utc"))
    fundamentals_validation_input_at = parse_utc(fundamentals_validation.get("input_generated_at_utc"))
    fundamentals_validation_generated_at = parse_utc(fundamentals_validation.get("generated_at_utc"))
    ticker_card_refresh_gate_soft_ok = (
        ticker_card_refresh_gate.get("status") == "ok_with_expected_context"
        and as_dict(ticker_card_refresh_gate.get("validation")).get("status") == "ok"
        and _summary_int(ticker_card_refresh_gate, 1, "summary", "failed_command_count") == 0
    )

    soft_ok_if_empty_steps = {
        "ticker_card_refresh_gate": ticker_card_refresh_gate_soft_ok,
        "wf78_source_artifact_capture_review": _summary_int(source_capture_review, 0, "summary", "review_row_count") == 0,
        "wf78_source_capture_requirements_queue": _summary_int(source_requirements, 0, "summary", "row_count") == 0,
        "wf78_official_registry_apply_preview": (
            _summary_int(registry_apply_preview, 0, "summary", "preview_row_count") == 0
            and _summary_int(registry_apply_preview, 0, "summary", "would_add_count") == 0
        ),
        "wf78_official_source_capture_packet": _summary_int(official_source_capture, 0, "summary", "row_count") == 0,
        "wf78_next_owner_review_and_source_capture_integration": _summary_int(next_integration, 0, "summary", "official_source_capture_rows") == 0,
        "post_freshness_ticker_card_refresh_gate": ticker_card_refresh_gate_soft_ok,
    }
    failed = [
        step["name"]
        for step in steps
        if not step["ok"] and not soft_ok_if_empty_steps.get(step["name"], False)
    ]
    errors = [f"{len(failed)} loop step(s) failed: {', '.join(failed)}"] if failed else []
    errors.extend(dependency_errors)
    warnings: list[str] = []
    if any(AUTHORITY_BOUNDARY[key] for key in ("capital_deployment_allowed", "trade_or_execution_allowed", "paper_or_live_execution_allowed", "owner_approval_inferred")):
        errors.append("authority boundary widened unexpectedly")
    if authority_findings:
        errors.append("artifact authority drift detected")
    fundamentals_errors: list[str] = []
    if fundamentals_generated_at and fundamentals_validation_input_at and fundamentals_validation_input_at < fundamentals_generated_at:
        fundamentals_errors.append("fundamental_metrics_validation_stale")
    if fundamentals_generated_at and fundamentals_validation_generated_at and fundamentals_validation_generated_at < fundamentals_generated_at:
        fundamentals_errors.append("fundamental_metrics_validation_generated_before_input")
    if fundamentals_validation.get("status") == "critical":
        fundamentals_errors.append("fundamental_metrics_validation_critical")
    if "fundamentals" in phases:
        errors.extend(fundamentals_errors)
    else:
        warnings.extend(f"{error}_outside_selected_phase" for error in fundamentals_errors)
    return {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "blocked" if errors else "ok",
        "purpose": "Daily WF78 review-only freshness loop and digest.",
        "authority_boundary": AUTHORITY_BOUNDARY,
        "parameters": {
            "skip_provider_refresh": bool(args.skip_provider_refresh),
            "requested_phase": args.phase,
            "selected_phases": sorted(phases),
            "dry_run": bool(getattr(args, "dry_run", False)),
            "parallel": int(getattr(args, "parallel", 1)),
        },
        "steps": steps,
        "skipped_steps": skipped_steps,
        "dependency_batches": dependency_batches,
        "summary": {
            "steps_run": len(steps),
            "steps_skipped": len(skipped_steps),
            "failed_steps": failed,
            "total_step_duration_ms": sum(int(step.get("duration_ms") or 0) for step in steps),
            "authority_drift_count": len(authority_findings),
            "freshness_ledger": ledger.get("summary"),
            "source_open_executor": executor.get("summary"),
            "source_open_work_packets": packets.get("summary"),
            "fundamental_metrics": fundamentals.get("summary"),
            "fundamental_metrics_validation": fundamentals_validation.get("summary"),
            "fundamental_metrics_validation_status": fundamentals_validation.get("status"),
            "position_sizing_surface_review": sizing_review.get("summary"),
            "deployment_readiness_review": deployment_review.get("summary"),
            "source_artifact_capture_review": source_capture_review.get("summary"),
            "position_sizing_integration_proposal": integration_proposal.get("summary"),
            "tier_a_owner_readiness_proposals": tier_a_owner_proposal.get("summary"),
            "missing_band_context_repair": band_context_repair.get("summary"),
            "source_capture_requirements_queue": source_requirements.get("summary"),
            "official_source_discovery": official_discovery.get("summary"),
            "official_registry_proposal": registry_proposal.get("summary"),
            "official_registry_apply_preview": registry_apply_preview.get("summary"),
            "promotion_owner_lineage_queue": owner_lineage_queue.get("summary"),
            "contract_state_guard": contract_guard.get("summary"),
            "owner_lineage_discovery": owner_lineage_discovery.get("summary"),
            "owner_lineage_proposal": owner_lineage_proposal.get("summary"),
            "repair_debt_scoreboard": repair_scoreboard.get("summary"),
            "scaleout_policy_dry_run": scaleout_policy.get("summary"),
            "ph_owner_review_candidate_packet": ph_packet.get("summary"),
            "tier_a_invalidation_review_queue": invalidation_queue.get("summary"),
            "official_source_capture_packet": official_source_capture.get("summary"),
            "next_owner_review_and_source_capture_integration": next_integration.get("summary"),
            "tier_c_band_status": tier_c_band_status.get("summary"),
            "family_repair": family.get("summary"),
            "tier_weighted_freshness_resolution": tier_weighted_resolution.get("summary"),
            "tier_c_attention_trigger": tier_c_attention_trigger.get("summary"),
            "tier_c_hold_recheck": tier_c_hold_recheck.get("summary"),
            "tier_c_to_b_auto_promotion_pipeline": tier_c_to_b_pipeline.get("summary"),
            "auto_tier_router": auto_router.get("summary"),
            "truth_layer_map": truth_layer_map.get("summary"),
            "tier_semantics_guard": tier_semantics_guard.get("summary"),
            "tier_b_research_packet": tier_b_research_packet.get("summary"),
            "tier_b_research_packet_phase2_eval": tier_b_phase2_eval.get("summary"),
            "tier_a_competitive_promotion_gate": tier_a_competitive_gate.get("summary"),
            "routing_delta": routing_delta.get("summary"),
            "wf84_canonical_finance_data_plane": wf84_packet.get("summary"),
            "wf84_canonical_finance_data_plane_validation": wf84_validation.get("summary"),
            "trade_grade_decision_cards": decision_cards.get("summary"),
            "trade_grade_repair_conveyor": repair_conveyor.get("summary"),
            "tier_a_b_band_freshness_guard": tier_ab_guard.get("summary"),
            "wf84_phase6_10_proof": wf84_phase6_10.get("summary"),
            "wf84_retirement_readiness": wf84_retirement.get("summary"),
            "next_safe_action": "Use tier-weighted resolution and the refreshed WF84 canonical finance data-plane as read-only internal routing/decision support. Preserve source feeders, fallback paths, and retirement/apply blocks until separate parity and lifecycle approval gates clear.",
        },
        "validation": {
            "status": "blocked" if errors else "ok",
            "errors": errors,
            "warnings": warnings,
            "authority_drift_paths": authority_findings,
        },
        "stop_lines": [
            "Daily loop is review-only and creates proof/routing artifacts only.",
            "No capital deployment, paper/live execution, brokerage/account action, money movement, customer output, canon/portfolio mutation, or owner approval inference.",
        ],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run WF78 daily freshness loop. For the split daily cadence, use "
            "wf78_intelligence_routing_v2.py --layer daily_core_v2; this wrapper "
            "remains the compatibility path for existing phase proof."
        )
    )
    parser.add_argument("--skip-provider-refresh", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument(
        "--phase",
        action="append",
        default=None,
        help=(
            "Comma-separated phase selector. Choices: all, daily_core, card_refresh, "
            "tier_routing, fundamentals, evidence_repair, source_capture, owner_review, wf84_sync, "
            "daily_core_v2. Default daily_core_v2 uses the current time-boxed WF78 route."
        ),
    )
    parser.add_argument(
        "--full-answer-mode",
        choices=("changed", "always", "never"),
        default="changed",
        help="Pass-through WF85 full-answer rebuild mode for the first ticker-card refresh gate.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Build the phase plan without invoking subprocesses.")
    parser.add_argument("--parallel", type=int, default=1, help="Maximum workers for dependency-safe batches. Default preserves serial behavior.")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--out", type=Path, default=OUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = build_report(args)
    if args.write:
        atomic_write_json(args.out, report)
        print(f"wrote {rel(args.out)} status={report['status']} steps={report['summary']['steps_run']} failed={report['summary']['failed_steps']}")
    else:
        print(json.dumps(report["summary"], indent=2))
    if args.validate and report["validation"]["status"] != "ok":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
