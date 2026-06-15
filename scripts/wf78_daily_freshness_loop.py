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
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, load_json_artifact

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
OUT = TMP / "wf78-daily-freshness-loop.json"
SCHEMA = "veritas.wf78_daily_freshness_loop.v1"

PHASE_ALIASES = {
    "all": {
        "card_refresh",
        "tier_routing",
        "fundamentals",
        "evidence_repair",
        "source_capture",
        "owner_review",
        "wf84_sync",
    },
    "daily_core": {
        "card_refresh",
        "tier_routing",
        "fundamentals",
        "evidence_repair",
        "wf84_sync",
    },
}

STEP_PHASES = {
    "ticker_card_refresh_gate": "card_refresh",
    "wf77_price_freshness_bridge": "card_refresh",
    "wf78_tier_a_confidence_gate": "tier_routing",
    "wf78_auto_tier_router_initial": "tier_routing",
    "wf78_tier_c_attention_trigger": "tier_routing",
    "wf78_tier_c_hold_recheck": "tier_routing",
    "wf78_tier_c_to_b_auto_promotion_pipeline": "tier_routing",
    "wf78_tier_b_research_packet": "tier_routing",
    "wf78_tier_b_research_packet_phase2_eval": "tier_routing",
    "wf78_auto_tier_router_post_phase2_gate": "tier_routing",
    "wf78_tier_a_competitive_promotion_gate": "tier_routing",
    "wf78_auto_tier_router_post_promotion_gates": "tier_routing",
    "wf78_clean_tier_roster": "tier_routing",
    "wf78_truth_layer_map": "tier_routing",
    "wf78_tier_semantics_guard": "tier_routing",
    "wf78_routing_delta": "tier_routing",
    "wf78_event_triggered_rerouting": "tier_routing",
    "wf78_evidence_drag_reducer": "evidence_repair",
    "wf78_evidence_family_repair": "evidence_repair",
    "wf78_source_open_repair_executor": "evidence_repair",
    "wf78_source_open_work_packet": "evidence_repair",
    "bank_native_sec_concept_probe": "fundamentals",
    "fundamental_metrics_refresh": "fundamentals",
    "validate_fundamental_metrics": "fundamentals",
    "wf78_missing_band_context_repair": "evidence_repair",
    "wf78_repair_debt_scoreboard": "evidence_repair",
    "wf78_ticker_freshness_ledger": "evidence_repair",
    "tier_c_band_status_refresh": "evidence_repair",
    "wf78_tier_weighted_freshness_resolver": "evidence_repair",
    "finance_decision_factory": "evidence_repair",
    "wf78_source_capture_requirements_queue": "source_capture",
    "wf78_official_source_discovery": "source_capture",
    "wf78_official_registry_proposal": "source_capture",
    "wf78_official_registry_apply_preview": "source_capture",
    "wf78_promotion_owner_lineage_queue": "source_capture",
    "wf78_contract_state_guard": "source_capture",
    "wf78_owner_lineage_discovery": "source_capture",
    "wf78_owner_lineage_proposal": "source_capture",
    "wf78_official_source_capture_packet": "source_capture",
    "wf78_next_owner_review_and_source_capture_integration": "source_capture",
    "wf78_position_sizing_surface_review": "owner_review",
    "wf78_deployment_readiness_review": "owner_review",
    "wf78_source_artifact_capture_review": "owner_review",
    "wf78_position_sizing_integration_proposal": "owner_review",
    "wf78_tier_a_owner_readiness_proposal": "owner_review",
    "wf78_scaleout_policy_dry_run": "owner_review",
    "wf78_ph_owner_review_candidate_packet": "owner_review",
    "wf78_tier_a_invalidation_review_queue": "owner_review",
    "post_freshness_ticker_card_refresh_gate": "wf84_sync",
    "post_card_price_freshness_bridge": "wf84_sync",
    "wf84_canonical_finance_data_plane": "wf84_sync",
    "trade_grade_decision_cards": "wf84_sync",
    "wf78_missing_band_context_repair_post_cards": "wf84_sync",
    "trade_grade_repair_conveyor": "wf84_sync",
    "tier_ab_band_freshness_cron_guard": "wf84_sync",
    "wf84_retirement_readiness": "wf84_sync",
    "wf84_phase6_10_proof": "wf84_sync",
}

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


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_utc(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).astimezone(timezone.utc)
    except Exception:
        return None


def rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def py_cmd(*parts: str) -> list[str]:
    return [sys.executable, *parts]


def run_step(name: str, command: list[str], timeout: int) -> dict[str, Any]:
    started = utc_now()
    try:
        proc = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, timeout=timeout)
        return {
            "name": name,
            "command": command,
            "started_at_utc": started,
            "completed_at_utc": utc_now(),
            "returncode": proc.returncode,
            "ok": proc.returncode == 0,
            "stdout_preview": proc.stdout.strip()[-2500:],
            "stderr_preview": proc.stderr.strip()[-1500:],
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "name": name,
            "command": command,
            "started_at_utc": started,
            "completed_at_utc": utc_now(),
            "returncode": None,
            "ok": False,
            "timeout_seconds": timeout,
            "stdout_preview": (exc.stdout or "")[-2500:] if isinstance(exc.stdout, str) else "",
            "stderr_preview": (exc.stderr or "")[-1500:] if isinstance(exc.stderr, str) else "",
        }


def load(path: Path) -> dict[str, Any]:
    payload = load_json_artifact(path)
    return payload if isinstance(payload, dict) else {}


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def selected_phases(raw_phases: list[str] | None) -> set[str]:
    phases: set[str] = set()
    for raw in raw_phases or ["all"]:
        for part in str(raw).split(","):
            name = part.strip()
            if not name:
                continue
            phases.update(PHASE_ALIASES.get(name, {name}))
    return phases or set(PHASE_ALIASES["all"])


def all_steps(args: argparse.Namespace) -> list[tuple[str, list[str], int]]:
    refresh = [
        "scripts\\finance_ticker_card_refresh_gate.py",
        "--write",
        "--validate",
        "--full-answer-mode",
        args.full_answer_mode,
    ]
    if args.skip_provider_refresh:
        refresh.append("--skip-provider-refresh")
    return [
        ("ticker_card_refresh_gate", py_cmd(*refresh), 360),
        ("wf77_price_freshness_bridge", py_cmd("scripts\\wf77_price_freshness_bridge.py", "--write", "--validate"), 180),
        ("wf78_tier_a_confidence_gate", py_cmd("scripts\\wf78_tier_a_confidence_gate.py", "--write", "--validate"), 180),
        ("wf78_auto_tier_router_initial", py_cmd("scripts\\wf78_auto_tier_router.py", "--write", "--validate"), 180),
        ("wf78_tier_c_attention_trigger", py_cmd("scripts\\wf78_tier_c_attention_trigger.py", "--write", "--write-db", "--validate"), 240),
        ("wf78_tier_c_hold_recheck", py_cmd("scripts\\wf78_tier_c_hold_recheck.py", "--write", "--validate"), 420),
        ("wf78_tier_c_to_b_auto_promotion_pipeline", py_cmd("scripts\\wf78_tier_c_to_b_auto_promotion_pipeline.py", "--from-attention", "--max-candidates", "10", "--write", "--validate"), 300),
        ("wf78_tier_b_research_packet", py_cmd("scripts\\wf78_tier_b_research_packet.py", "--write", "--write-db", "--validate"), 180),
        ("wf78_tier_b_research_packet_phase2_eval", py_cmd("scripts\\wf78_tier_funnel_promotion_gate.py", "--requests", "tmp\\wf78-tier-b-research-packet-requests.json", "--out", "tmp\\wf78-tier-b-research-packet-phase2-eval.json", "--write", "--validate"), 180),
        ("wf78_auto_tier_router_post_phase2_gate", py_cmd("scripts\\wf78_auto_tier_router.py", "--write", "--validate"), 180),
        ("wf78_tier_a_competitive_promotion_gate", py_cmd("scripts\\wf78_tier_a_competitive_promotion_gate.py", "--write", "--validate"), 180),
        ("wf78_auto_tier_router_post_promotion_gates", py_cmd("scripts\\wf78_auto_tier_router.py", "--write", "--validate"), 180),
        ("wf78_clean_tier_roster", py_cmd("scripts\\wf78_clean_tier_roster.py", "--write", "--validate"), 180),
        ("wf78_truth_layer_map", py_cmd("scripts\\wf78_truth_layer_map.py", "--write", "--validate"), 180),
        ("wf78_tier_semantics_guard", py_cmd("scripts\\wf78_tier_semantics_guard.py", "--write", "--validate"), 180),
        ("wf78_routing_delta", py_cmd("scripts\\wf78_routing_delta.py", "--write", "--validate"), 180),
        ("wf78_event_triggered_rerouting", py_cmd("scripts\\wf78_event_triggered_rerouting.py", "--write", "--write-db", "--validate"), 180),
        ("wf78_evidence_drag_reducer", py_cmd("scripts\\wf78_evidence_drag_reducer.py", "--write", "--validate"), 180),
        ("wf78_evidence_family_repair", py_cmd("scripts\\wf78_evidence_family_repair_runner.py", "--family", "price_band_stop", "--tier", "all", "--cursor", "0", "--limit", "250", "--write", "--validate"), 180),
        ("wf78_source_open_repair_executor", py_cmd("scripts\\wf78_source_open_repair_executor.py", "--tier", "all", "--write", "--validate"), 180),
        ("wf78_source_open_work_packet", py_cmd("scripts\\wf78_source_open_work_packet.py", "--write", "--validate"), 180),
        ("bank_native_sec_concept_probe", py_cmd("scripts\\bank_native_sec_concept_probe.py", "--write"), 240),
        ("fundamental_metrics_refresh", py_cmd("scripts\\fundamental_metrics_refresh.py"), 900),
        ("validate_fundamental_metrics", py_cmd("scripts\\validate_fundamental_metrics.py", "--write"), 120),
        ("wf78_position_sizing_surface_review", py_cmd("scripts\\wf78_position_sizing_surface_review.py", "--write", "--validate"), 180),
        ("wf78_deployment_readiness_review", py_cmd("scripts\\wf78_deployment_readiness_review.py", "--write", "--validate"), 180),
        ("wf78_source_artifact_capture_review", py_cmd("scripts\\wf78_source_artifact_capture_review.py", "--write", "--validate"), 180),
        ("wf78_position_sizing_integration_proposal", py_cmd("scripts\\wf78_position_sizing_integration_proposal.py", "--write", "--validate"), 180),
        ("wf78_tier_a_owner_readiness_proposal", py_cmd("scripts\\wf78_tier_a_owner_readiness_proposal.py", "--write", "--validate"), 180),
        ("wf78_missing_band_context_repair", py_cmd("scripts\\wf78_missing_band_context_repair.py", "--write", "--validate"), 180),
        ("wf78_source_capture_requirements_queue", py_cmd("scripts\\wf78_source_capture_requirements_queue.py", "--write", "--validate"), 180),
        ("wf78_official_source_discovery", py_cmd("scripts\\wf78_official_source_discovery_runner.py", "--write", "--validate"), 180),
        ("wf78_official_registry_proposal", py_cmd("scripts\\wf78_official_registry_proposal.py", "--write", "--validate"), 180),
        ("wf78_official_registry_apply_preview", py_cmd("scripts\\wf78_official_registry_apply_preview.py", "--write", "--write-proposed", "--validate"), 180),
        ("wf78_promotion_owner_lineage_queue", py_cmd("scripts\\wf78_promotion_owner_lineage_queue.py", "--write", "--validate"), 180),
        ("wf78_contract_state_guard", py_cmd("scripts\\wf78_contract_state_guard.py", "--write", "--validate"), 180),
        ("wf78_owner_lineage_discovery", py_cmd("scripts\\wf78_owner_lineage_discovery.py", "--write", "--validate"), 180),
        ("wf78_owner_lineage_proposal", py_cmd("scripts\\wf78_owner_lineage_proposal.py", "--write", "--validate"), 180),
        ("wf78_repair_debt_scoreboard", py_cmd("scripts\\wf78_repair_debt_scoreboard.py", "--write", "--validate"), 180),
        ("wf78_scaleout_policy_dry_run", py_cmd("scripts\\wf78_scaleout_policy_dry_run.py", "--write", "--validate"), 180),
        ("wf78_ph_owner_review_candidate_packet", py_cmd("scripts\\wf78_ph_owner_review_candidate_packet.py", "--write", "--validate"), 180),
        ("wf78_tier_a_invalidation_review_queue", py_cmd("scripts\\wf78_tier_a_invalidation_review_queue.py", "--write", "--validate"), 180),
        ("wf78_official_source_capture_packet", py_cmd("scripts\\wf78_official_source_capture_packet.py", "--write", "--validate"), 180),
        ("wf78_next_owner_review_and_source_capture_integration", py_cmd("scripts\\wf78_next_owner_review_and_source_capture_integration.py", "--write", "--validate"), 180),
        ("wf78_ticker_freshness_ledger", py_cmd("scripts\\wf78_ticker_freshness_ledger.py", "--write", "--validate"), 180),
        ("tier_c_band_status_refresh", py_cmd("scripts\\tier_c_band_status_refresh.py", "--no-skip-provider-refresh", "--write", "--validate"), 420),
        ("wf78_tier_weighted_freshness_resolver", py_cmd("scripts\\wf78_tier_weighted_freshness_resolver.py", "--write", "--validate"), 180),
        ("finance_decision_factory", py_cmd("scripts\\finance_decision_factory.py", "--ledger-only", "--write", "--validate"), 180),
        ("post_freshness_ticker_card_refresh_gate", py_cmd("scripts\\finance_ticker_card_refresh_gate.py", "--write", "--validate", "--skip-provider-refresh", "--full-answer-mode", "never"), 360),
        ("post_card_price_freshness_bridge", py_cmd("scripts\\wf77_price_freshness_bridge.py", "--write", "--validate"), 180),
        ("wf84_canonical_finance_data_plane", py_cmd("scripts\\canonical_finance_data_plane.py", "--write", "--write-db", "--validate"), 240),
        ("trade_grade_decision_cards", py_cmd("scripts\\trade_grade_decision_cards.py", "--write", "--validate"), 180),
        ("wf78_missing_band_context_repair_post_cards", py_cmd("scripts\\wf78_missing_band_context_repair.py", "--write", "--validate"), 180),
        ("trade_grade_repair_conveyor", py_cmd("scripts\\trade_grade_repair_conveyor.py", "--write", "--validate"), 180),
        ("tier_ab_band_freshness_cron_guard", py_cmd("scripts\\tier_ab_band_freshness_cron_guard.py", "--write", "--validate"), 180),
        ("wf84_retirement_readiness", py_cmd("scripts\\canonical_finance_data_plane_retirement_readiness.py", "--write", "--validate"), 120),
        ("wf84_phase6_10_proof", py_cmd("scripts\\canonical_finance_data_plane_phase6_10.py", "--write", "--validate"), 120),
    ]


def build_steps(args: argparse.Namespace) -> list[tuple[str, list[str], int]]:
    phases = selected_phases(args.phase)
    return [
        step
        for step in all_steps(args)
        if STEP_PHASES.get(step[0], "unclassified") in phases
    ]


def build_report(args: argparse.Namespace) -> dict[str, Any]:
    phases = selected_phases(args.phase)
    planned_steps = all_steps(args)
    runnable_steps = [
        step for step in planned_steps if STEP_PHASES.get(step[0], "unclassified") in phases
    ]
    skipped_steps = [
        {"name": name, "phase": STEP_PHASES.get(name, "unclassified"), "reason": "phase_not_selected"}
        for name, _command, _timeout in planned_steps
        if STEP_PHASES.get(name, "unclassified") not in phases
    ]
    steps = [run_step(name, command, timeout) for name, command, timeout in runnable_steps]
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
    if any(AUTHORITY_BOUNDARY[key] for key in ("capital_deployment_allowed", "trade_or_execution_allowed", "paper_or_live_execution_allowed", "owner_approval_inferred")):
        errors.append("authority boundary widened unexpectedly")
    if fundamentals_generated_at and fundamentals_validation_input_at and fundamentals_validation_input_at < fundamentals_generated_at:
        errors.append("fundamental_metrics_validation_stale")
    if fundamentals_generated_at and fundamentals_validation_generated_at and fundamentals_validation_generated_at < fundamentals_generated_at:
        errors.append("fundamental_metrics_validation_generated_before_input")
    if fundamentals_validation.get("status") == "critical":
        errors.append("fundamental_metrics_validation_critical")
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
        },
        "steps": steps,
        "skipped_steps": skipped_steps,
        "summary": {
            "steps_run": len(steps),
            "steps_skipped": len(skipped_steps),
            "failed_steps": failed,
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
        "validation": {"status": "blocked" if errors else "ok", "errors": errors, "warnings": []},
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
            "tier_routing, fundamentals, evidence_repair, source_capture, owner_review, wf84_sync."
        ),
    )
    parser.add_argument(
        "--full-answer-mode",
        choices=("changed", "always", "never"),
        default="changed",
        help="Pass-through WF85 full-answer rebuild mode for the first ticker-card refresh gate.",
    )
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
