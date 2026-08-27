#!/usr/bin/env python3
"""WF78 orchestration manifest.

This file is declarative on purpose: runners import it to avoid two competing
maps for the same WF78 daily-core workflow.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from wf_registry import (
    ARTIFACT_INDEX_DB,
    AUTONOMOUS_ROUTING_DEPLOYMENT_CARDS,
    CRON_CONTRACT_VALIDATOR,
    CRON_FRESHNESS_SPINE,
    STATE,
    TMP,
    WF78_AUTO_TIER_ROUTING,
    WF78_DAILY_MOVEMENT_LEDGER,
    WF78_DAILY_MOVEMENT_LEDGER_MD,
    WF78_REPAIR_DEBT_SCOREBOARD,
    WF78_REPAIR_PRIORITY_QUEUE,
    WF78_ROUTING_DELTA,
    WF78_TIER_C_ATTENTION_TRIGGER,
    WF78_TIER_ROUTING_EVENT_LEDGER,
    WF78_TIER_ROUTING_EVENT_LEDGER_MD,
    WF78_TIER_ROUTING_EVENTS,
    WF78_TIER_WEIGHTED_FRESHNESS_RESOLUTION,
)
from wf_runner_lib import py_cmd, rel


@dataclass(frozen=True)
class StepDef:
    name: str
    command: tuple[str, ...]
    timeout: int
    phase: str
    depends_on: tuple[str, ...] = field(default_factory=tuple)

    def runner_tuple(self) -> tuple[str, list[str], int]:
        return self.name, list(self.command), self.timeout


@dataclass(frozen=True)
class LayerDef:
    name: str
    purpose: str
    time_budget_seconds: int
    commands: tuple[StepDef, ...] = field(default_factory=tuple)
    phase: str | None = None
    expected_artifacts: tuple[str, ...] = field(default_factory=tuple)
    dependencies: dict[str, tuple[str, ...]] = field(default_factory=dict)


PHASE_ALIASES: dict[str, set[str]] = {
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


def _step(name: str, command: list[str], timeout: int, phase: str, depends_on: tuple[str, ...] = ()) -> StepDef:
    return StepDef(name=name, command=tuple(command), timeout=timeout, phase=phase, depends_on=depends_on)


def build_daily_steps(*, skip_provider_refresh: bool = True, full_answer_mode: str = "changed") -> list[StepDef]:
    refresh = [
        "scripts\\finance_ticker_card_refresh_gate.py",
        "--write",
        "--validate",
        "--full-answer-mode",
        full_answer_mode,
    ]
    if skip_provider_refresh:
        refresh.append("--skip-provider-refresh")
    steps = [
        _step("ticker_card_refresh_gate", py_cmd(*refresh), 360, "card_refresh"),
        _step("wf77_price_freshness_bridge", py_cmd("scripts\\wf77_price_freshness_bridge.py", "--write", "--validate"), 180, "card_refresh", ("ticker_card_refresh_gate",)),
        _step("wf78_tier_a_confidence_gate", py_cmd("scripts\\wf78_tier_a_confidence_gate.py", "--write", "--validate"), 180, "tier_routing"),
        _step("wf78_auto_tier_router_initial", py_cmd("scripts\\wf78_auto_tier_router.py", "--write", "--validate"), 180, "tier_routing", ("wf78_tier_a_confidence_gate",)),
        _step("wf78_tier_c_attention_trigger", py_cmd("scripts\\wf78_tier_c_attention_trigger.py", "--write", "--write-db", "--validate"), 240, "tier_routing", ("wf78_auto_tier_router_initial",)),
        _step("wf78_tier_c_hold_recheck", py_cmd("scripts\\wf78_tier_c_hold_recheck.py", "--write", "--validate"), 420, "tier_routing", ("wf78_tier_c_attention_trigger",)),
        _step(
            "wf78_tier_c_to_b_auto_promotion_pipeline",
            py_cmd(
                "scripts\\wf78_tier_c_to_b_auto_promotion_pipeline.py",
                "--from-attention",
                "--max-candidates",
                "25",
                "--approve-passing",
                "--approval-reference",
                "webchat 2026-07-05 Randall standing approval: automatically apply passing WF78 C-to-B derived Tier B research-bench labels only; no capital, execution, portfolio, canon, account, or owner-approval inference",
                "--write",
                "--validate",
            ),
            300,
            "tier_routing",
            ("wf78_tier_c_hold_recheck",),
        ),
        _step("wf78_tier_b_research_packet", py_cmd("scripts\\wf78_tier_b_research_packet.py", "--write", "--write-db", "--validate"), 180, "tier_routing", ("wf78_tier_c_to_b_auto_promotion_pipeline",)),
        _step("wf78_tier_b_research_packet_phase2_eval", py_cmd("scripts\\wf78_tier_funnel_promotion_gate.py", "--requests", "tmp\\wf78-tier-b-research-packet-requests.json", "--out", "tmp\\wf78-tier-b-research-packet-phase2-eval.json", "--write", "--validate"), 180, "tier_routing", ("wf78_tier_b_research_packet",)),
        _step("wf78_auto_tier_router_post_phase2_gate", py_cmd("scripts\\wf78_auto_tier_router.py", "--write", "--validate"), 180, "tier_routing", ("wf78_tier_b_research_packet_phase2_eval",)),
        _step("wf78_tier_a_competitive_promotion_gate", py_cmd("scripts\\wf78_tier_a_competitive_promotion_gate.py", "--write", "--validate"), 180, "tier_routing", ("wf78_auto_tier_router_post_phase2_gate",)),
        _step("wf78_auto_tier_router_post_promotion_gates", py_cmd("scripts\\wf78_auto_tier_router.py", "--write", "--validate"), 180, "tier_routing", ("wf78_tier_a_competitive_promotion_gate",)),
        _step("wf78_clean_tier_roster", py_cmd("scripts\\wf78_clean_tier_roster.py", "--write", "--validate"), 180, "tier_routing", ("wf78_auto_tier_router_post_promotion_gates",)),
        _step("wf78_truth_layer_map", py_cmd("scripts\\wf78_truth_layer_map.py", "--write", "--validate"), 180, "tier_routing", ("wf78_clean_tier_roster",)),
        _step("wf78_tier_semantics_guard", py_cmd("scripts\\wf78_tier_semantics_guard.py", "--write", "--validate"), 180, "tier_routing", ("wf78_truth_layer_map",)),
        _step("wf78_routing_delta", py_cmd("scripts\\wf78_routing_delta.py", "--write", "--validate"), 180, "tier_routing", ("wf78_tier_semantics_guard",)),
        _step("wf78_event_triggered_rerouting", py_cmd("scripts\\wf78_event_triggered_rerouting.py", "--write", "--write-db", "--validate"), 180, "tier_routing", ("wf78_routing_delta",)),
        _step("wf78_evidence_drag_reducer", py_cmd("scripts\\wf78_evidence_drag_reducer.py", "--write", "--validate"), 180, "evidence_repair", ("wf78_event_triggered_rerouting",)),
        _step("wf78_evidence_family_repair", py_cmd("scripts\\wf78_evidence_family_repair_runner.py", "--family", "price_band_stop", "--tier", "all", "--cursor", "0", "--limit", "250", "--write", "--validate"), 180, "evidence_repair", ("wf78_evidence_drag_reducer",)),
        _step("wf78_source_open_repair_executor", py_cmd("scripts\\wf78_source_open_repair_executor.py", "--tier", "all", "--write", "--validate"), 180, "evidence_repair", ("wf78_evidence_family_repair",)),
        # The ledger's primary input is only written by this subcommand. Without it the
        # ledger consumes the previous post-close snapshot and cannot see the repair
        # steps that just ran above it.
        _step("finance_state_stale_tickers", py_cmd("scripts\\finance_intelligence_state.py", "stale-tickers", "--limit", "500"), 180, "evidence_repair", ("wf78_source_open_repair_executor",)),
        _step("wf78_ticker_freshness_ledger", py_cmd("scripts\\wf78_ticker_freshness_ledger.py", "--write", "--validate"), 180, "evidence_repair", ("wf78_source_open_repair_executor", "finance_state_stale_tickers")),
        _step("wf78_source_open_work_packet", py_cmd("scripts\\wf78_source_open_work_packet.py", "--write", "--validate"), 180, "evidence_repair", ("wf78_ticker_freshness_ledger",)),
        _step("wf78_deployment_readiness_review", py_cmd("scripts\\wf78_deployment_readiness_review.py", "--write", "--validate"), 180, "evidence_repair", ("wf78_source_open_work_packet",)),
        _step("bank_native_sec_concept_probe", py_cmd("scripts\\bank_native_sec_concept_probe.py", "--write"), 240, "fundamentals"),
        _step("fundamental_metrics_refresh", py_cmd("scripts\\fundamental_metrics_refresh.py"), 900, "fundamentals", ("bank_native_sec_concept_probe",)),
        _step("validate_fundamental_metrics", py_cmd("scripts\\validate_fundamental_metrics.py", "--write"), 120, "fundamentals", ("fundamental_metrics_refresh",)),
        _step("wf78_position_sizing_surface_review", py_cmd("scripts\\wf78_position_sizing_surface_review.py", "--write", "--validate"), 180, "owner_review"),
        _step("wf78_source_artifact_capture_review", py_cmd("scripts\\wf78_source_artifact_capture_review.py", "--write", "--validate"), 180, "owner_review"),
        _step("wf78_position_sizing_integration_proposal", py_cmd("scripts\\wf78_position_sizing_integration_proposal.py", "--write", "--validate"), 180, "owner_review", ("wf78_position_sizing_surface_review",)),
        _step("wf78_tier_a_owner_readiness_proposal", py_cmd("scripts\\wf78_tier_a_owner_readiness_proposal.py", "--write", "--validate"), 180, "owner_review", ("wf78_deployment_readiness_review",)),
        _step("wf78_missing_band_context_repair", py_cmd("scripts\\wf78_missing_band_context_repair.py", "--write", "--validate"), 180, "evidence_repair", ("wf78_deployment_readiness_review",)),
        _step("wf78_source_capture_requirements_queue", py_cmd("scripts\\wf78_source_capture_requirements_queue.py", "--write", "--validate"), 180, "source_capture"),
        _step("wf78_official_source_discovery", py_cmd("scripts\\wf78_official_source_discovery_runner.py", "--write", "--validate"), 180, "source_capture", ("wf78_source_capture_requirements_queue",)),
        _step("wf78_official_registry_proposal", py_cmd("scripts\\wf78_official_registry_proposal.py", "--write", "--validate"), 180, "source_capture", ("wf78_official_source_discovery",)),
        _step("wf78_official_registry_apply_preview", py_cmd("scripts\\wf78_official_registry_apply_preview.py", "--write", "--write-proposed", "--validate"), 180, "source_capture", ("wf78_official_registry_proposal",)),
        _step("wf78_promotion_owner_lineage_queue", py_cmd("scripts\\wf78_promotion_owner_lineage_queue.py", "--write", "--validate"), 180, "source_capture", ("wf78_official_registry_apply_preview",)),
        _step("wf78_contract_state_guard", py_cmd("scripts\\wf78_contract_state_guard.py", "--write", "--validate"), 180, "source_capture", ("wf78_promotion_owner_lineage_queue",)),
        _step("wf78_owner_lineage_discovery", py_cmd("scripts\\wf78_owner_lineage_discovery.py", "--write", "--validate"), 180, "source_capture", ("wf78_contract_state_guard",)),
        _step("wf78_owner_lineage_proposal", py_cmd("scripts\\wf78_owner_lineage_proposal.py", "--write", "--validate"), 180, "source_capture", ("wf78_owner_lineage_discovery",)),
        _step("wf78_repair_debt_scoreboard", py_cmd("scripts\\wf78_repair_debt_scoreboard.py", "--write", "--validate"), 180, "evidence_repair", ("wf78_missing_band_context_repair",)),
        _step("wf78_scaleout_policy_dry_run", py_cmd("scripts\\wf78_scaleout_policy_dry_run.py", "--write", "--validate"), 180, "owner_review"),
        _step("wf78_ph_owner_review_candidate_packet", py_cmd("scripts\\wf78_ph_owner_review_candidate_packet.py", "--write", "--validate"), 180, "owner_review"),
        _step("wf78_tier_a_invalidation_review_queue", py_cmd("scripts\\wf78_tier_a_invalidation_review_queue.py", "--write", "--validate"), 180, "owner_review"),
        _step("wf78_official_source_capture_packet", py_cmd("scripts\\wf78_official_source_capture_packet.py", "--write", "--validate"), 180, "source_capture", ("wf78_owner_lineage_proposal",)),
        _step("wf78_next_owner_review_and_source_capture_integration", py_cmd("scripts\\wf78_next_owner_review_and_source_capture_integration.py", "--write", "--validate"), 180, "source_capture", ("wf78_official_source_capture_packet",)),
        _step("tier_c_band_status_refresh", py_cmd("scripts\\tier_c_band_status_refresh.py", "--no-skip-provider-refresh", "--write", "--validate"), 420, "evidence_repair", ("wf78_repair_debt_scoreboard",)),
        _step("wf78_tier_c_attention_evidence_repair_bridge", py_cmd("scripts\\wf78_tier_c_attention_evidence_repair_bridge.py", "--write", "--validate"), 180, "evidence_repair", ("tier_c_band_status_refresh",)),
        _step("wf78_tier_weighted_freshness_resolver", py_cmd("scripts\\wf78_tier_weighted_freshness_resolver.py", "--write", "--validate"), 180, "evidence_repair", ("wf78_tier_c_attention_evidence_repair_bridge", "wf78_deployment_readiness_review")),
        _step("finance_decision_factory", py_cmd("scripts\\finance_decision_factory.py", "--ledger-only", "--write", "--validate"), 180, "evidence_repair", ("wf78_tier_weighted_freshness_resolver",)),
        _step("post_freshness_ticker_card_refresh_gate", py_cmd("scripts\\finance_ticker_card_refresh_gate.py", "--write", "--validate", "--skip-provider-refresh", "--full-answer-mode", "never"), 360, "wf84_sync"),
        _step("post_card_price_freshness_bridge", py_cmd("scripts\\wf77_price_freshness_bridge.py", "--write", "--validate"), 180, "wf84_sync", ("post_freshness_ticker_card_refresh_gate",)),
        # Any wf78_auto_tier_router run rewrites tmp/wf78-auto-tier-routing.json and
        # leaves the SQL-canon tier_routing_state mirror behind it. This sits in the
        # consuming phase rather than tier_routing so the mirror is current no matter
        # which phases were selected: cross-phase depends_on is filtered out of
        # unselected runs by dependencies_for and would silently stop enforcing order.
        _step("sql_canon_tier_routing_mirror_refresh", py_cmd("scripts\\sql_canon_tier_routing_refresh.py", "--write", "--apply-db", "--validate"), 240, "wf84_sync", ("post_card_price_freshness_bridge",)),
        _step("sql_canon_wf78_routing_parity", py_cmd("scripts\\sql_canon_wf78_routing_parity.py", "--write", "--validate"), 120, "wf84_sync", ("sql_canon_tier_routing_mirror_refresh",)),
        # --write-db is required: --write alone emits the JSON packet and leaves the
        # SQLite companion at its previous generation.
        _step("wf84_canonical_finance_data_plane", py_cmd("scripts\\canonical_finance_data_plane.py", "--write", "--write-db", "--validate"), 240, "wf84_sync", ("sql_canon_wf78_routing_parity",)),
        _step("trade_grade_decision_cards", py_cmd("scripts\\trade_grade_decision_cards.py", "--write", "--validate"), 180, "wf84_sync", ("wf84_canonical_finance_data_plane",)),
        _step("wf78_missing_band_context_repair_post_cards", py_cmd("scripts\\wf78_missing_band_context_repair.py", "--write", "--validate"), 180, "wf84_sync", ("trade_grade_decision_cards",)),
        _step("trade_grade_repair_conveyor", py_cmd("scripts\\trade_grade_repair_conveyor.py", "--write", "--validate"), 180, "wf84_sync", ("wf78_missing_band_context_repair_post_cards",)),
        _step("tier_ab_band_freshness_cron_guard", py_cmd("scripts\\tier_ab_band_freshness_cron_guard.py", "--write", "--validate"), 180, "wf84_sync", ("trade_grade_repair_conveyor",)),
        _step("wf84_retirement_readiness", py_cmd("scripts\\canonical_finance_data_plane_retirement_readiness.py", "--write", "--validate"), 120, "wf84_sync", ("tier_ab_band_freshness_cron_guard",)),
        _step("wf84_phase6_10_proof", py_cmd("scripts\\canonical_finance_data_plane_phase6_10.py", "--write", "--validate"), 120, "wf84_sync", ("wf84_retirement_readiness",)),
    ]
    return steps


def selected_phases(raw_phases: list[str] | None) -> set[str]:
    phases: set[str] = set()
    for raw in raw_phases or ["all"]:
        for part in str(raw).split(","):
            name = part.strip()
            if not name:
                continue
            phases.update(PHASE_ALIASES.get(name, {name}))
    return phases or set(PHASE_ALIASES["all"])


def steps_for_phases(
    raw_phases: list[str] | None,
    *,
    skip_provider_refresh: bool = True,
    full_answer_mode: str = "changed",
) -> tuple[list[StepDef], list[dict[str, Any]], set[str]]:
    phases = selected_phases(raw_phases)
    planned_steps = build_daily_steps(skip_provider_refresh=skip_provider_refresh, full_answer_mode=full_answer_mode)
    runnable = [step for step in planned_steps if step.phase in phases]
    skipped = [
        {"name": step.name, "phase": step.phase, "reason": "phase_not_selected"}
        for step in planned_steps
        if step.phase not in phases
    ]
    return runnable, skipped, phases


def steps_for_phase(
    phase: str,
    *,
    skip_provider_refresh: bool = True,
    full_answer_mode: str = "changed",
) -> list[StepDef]:
    return [
        step
        for step in build_daily_steps(skip_provider_refresh=skip_provider_refresh, full_answer_mode=full_answer_mode)
        if step.phase == phase
    ]


def dependencies_for(steps: list[StepDef]) -> dict[str, tuple[str, ...]]:
    names = {step.name for step in steps}
    return {step.name: tuple(dep for dep in step.depends_on if dep in names) for step in steps}


def as_runner_tuples(steps: list[StepDef]) -> list[tuple[str, list[str], int]]:
    return [step.runner_tuple() for step in steps]


def _artifact(path: object) -> str:
    return rel(path)  # type: ignore[arg-type]


LAYER_DEFS: dict[str, LayerDef] = {
    "preflight": LayerDef(
        name="preflight",
        time_budget_seconds=45,
        purpose="Control-plane health before ticker routing.",
        commands=(
            _step("cron_contract_validator", py_cmd("scripts\\cron_contract_validator.py", "--require-contracts", "--fail-on-drift", "--write", "--validate"), 90, "preflight"),
            _step("cron_freshness_spine", py_cmd("scripts\\cron_freshness_spine.py", "--write", "--validate"), 90, "preflight"),
            _step("artifact_index_incremental", py_cmd("scripts\\artifact_index.py", "incremental"), 90, "preflight"),
            _step("artifact_index_validate", py_cmd("scripts\\artifact_index.py", "validate"), 90, "preflight", ("artifact_index_incremental",)),
        ),
        expected_artifacts=(_artifact(CRON_CONTRACT_VALIDATOR), _artifact(CRON_FRESHNESS_SPINE)),
    ),
    "tier_routing": LayerDef(
        name="tier_routing",
        time_budget_seconds=240,
        purpose="Tier A/B/C route state and Tier C attention pass.",
        phase="tier_routing",
        expected_artifacts=(
            _artifact(WF78_AUTO_TIER_ROUTING),
            _artifact(WF78_TIER_C_ATTENTION_TRIGGER),
            _artifact(WF78_ROUTING_DELTA),
        ),
    ),
    "freshness": LayerDef(
        name="freshness",
        time_budget_seconds=300,
        purpose="Tier-weighted freshness and band context resolution.",
        phase="evidence_repair",
        expected_artifacts=(
            _artifact(WF78_TIER_WEIGHTED_FRESHNESS_RESOLUTION),
            _artifact(WF78_REPAIR_DEBT_SCOREBOARD),
            "tmp/wf78-ticker-freshness-ledger.json",
            "tmp/wf78-source-open-work-packets.json",
            "tmp/wf78-deployment-readiness-review.json",
        ),
    ),
    "repair_scan": LayerDef(
        name="repair_scan",
        time_budget_seconds=90,
        purpose="Checkpoint current repair-priority queue before ledger publish.",
        commands=(),
        expected_artifacts=(_artifact(WF78_REPAIR_PRIORITY_QUEUE),),
    ),
    "card_materialization": LayerDef(
        name="card_materialization",
        time_budget_seconds=120,
        purpose="Refresh review-only card materialization queue where existing gates allow references.",
        commands=(
            _step("autonomous_routing_deployment_cards", py_cmd("scripts\\autonomous_routing_deployment_cards.py", "--write", "--validate"), 180, "card_materialization"),
        ),
        expected_artifacts=(_artifact(AUTONOMOUS_ROUTING_DEPLOYMENT_CARDS),),
    ),
    "source_capture": LayerDef(
        name="source_capture",
        time_budget_seconds=600,
        purpose="Repair official-source and owner-lineage gaps before promotion or owner-card surfacing.",
        phase="source_capture",
        expected_artifacts=(
            "tmp/wf78-source-capture-requirements-queue.json",
            "tmp/wf78-official-source-discovery.json",
            "tmp/wf78-official-registry-proposal.json",
            "tmp/wf78-official-registry-apply-preview.json",
            "tmp/wf78-promotion-owner-lineage-queue.json",
            "tmp/wf78-contract-state-guard.json",
            "tmp/wf78-owner-lineage-discovery.json",
            "tmp/wf78-owner-lineage-proposal.json",
            "tmp/wf78-official-source-capture-packet.json",
            "tmp/wf78-next-owner-review-and-source-capture-integration.json",
        ),
    ),
    "wf84_sync": LayerDef(
        name="wf84_sync",
        time_budget_seconds=900,
        purpose="Reconcile the SQL-canon routing mirror, then refresh WF84/WF85 trade-grade data plane, Tier A/B band guard, and repair conveyor.",
        phase="wf84_sync",
        expected_artifacts=(
            "tmp/sql-canon-tier-routing-refresh.json",
            "tmp/sql-canon-wf78-routing-parity.json",
            "tmp/canonical-finance-data-plane.json",
            "tmp/canonical-finance-data-plane-validation.json",
            "tmp/canonical-finance-data-plane.sqlite",
            "tmp/trade-grade-decision-cards.json",
            "tmp/wf78-missing-band-context-repair.json",
            "tmp/trade-grade-repair-conveyor.json",
            "tmp/tier-ab-band-freshness-cron-guard.json",
            "tmp/canonical-finance-data-plane-retirement-readiness.json",
            "tmp/canonical-finance-data-plane-phase6-10.json",
        ),
    ),
    "owner_review": LayerDef(
        name="owner_review",
        time_budget_seconds=420,
        purpose="Refresh Tier A/B owner-review, sizing, deployment-readiness, and source-capture review surfaces.",
        phase="owner_review",
        expected_artifacts=(
            "tmp/wf78-position-sizing-surface-review.json",
            "tmp/wf78-deployment-readiness-review.json",
            "tmp/wf78-source-artifact-capture-review.json",
            "tmp/wf78-position-sizing-integration-proposal.json",
            "tmp/wf78-tier-a-owner-readiness-proposals.json",
            "tmp/wf78-scaleout-policy-dry-run.json",
            "tmp/wf78-ph-owner-review-candidate-packet.json",
            "tmp/wf78-tier-a-invalidation-review-queue.json",
        ),
    ),
    "ledger_publish": LayerDef(
        name="ledger_publish",
        time_budget_seconds=60,
        purpose="Publish durable tier/routing event history, final daily movement ledger, and repair priority queue.",
        commands=(
            _step("wf78_tier_routing_event_ledger", py_cmd("scripts\\wf78_tier_routing_event_ledger.py", "--write", "--write-md", "--validate"), 90, "ledger_publish"),
            _step("wf78_daily_movement_ledger", py_cmd("scripts\\wf78_daily_movement_ledger.py", "--write", "--write-md", "--validate"), 90, "ledger_publish"),
        ),
        expected_artifacts=(
            _artifact(WF78_TIER_ROUTING_EVENT_LEDGER),
            _artifact(WF78_TIER_ROUTING_EVENT_LEDGER_MD),
            _artifact(WF78_TIER_ROUTING_EVENTS),
            _artifact(WF78_DAILY_MOVEMENT_LEDGER),
            _artifact(WF78_DAILY_MOVEMENT_LEDGER_MD),
            _artifact(WF78_REPAIR_PRIORITY_QUEUE),
        ),
    ),
    "postflight": LayerDef(
        name="postflight",
        time_budget_seconds=120,
        purpose="Refresh and validate the artifact index after V2 writes its proof artifacts.",
        commands=(
            _step("artifact_index_incremental", py_cmd("scripts\\artifact_index.py", "incremental"), 120, "postflight"),
            _step("artifact_index_validate", py_cmd("scripts\\artifact_index.py", "validate"), 120, "postflight", ("artifact_index_incremental",)),
        ),
        expected_artifacts=(_artifact(ARTIFACT_INDEX_DB),),
    ),
}

ALIASES = {
    "all": [
        "preflight",
        "tier_routing",
        "freshness",
        "source_capture",
        "wf84_sync",
        "owner_review",
        "repair_scan",
        "card_materialization",
        "ledger_publish",
        "postflight",
    ],
    "daily_core_v2": ["preflight", "tier_routing", "freshness", "repair_scan", "ledger_publish", "postflight"],
    "pre_market_repair_v2": [
        "preflight",
        "tier_routing",
        "freshness",
        "source_capture",
        "wf84_sync",
        "owner_review",
        "repair_scan",
        "card_materialization",
        "ledger_publish",
        "postflight",
    ],
    "market_probe": ["tier_routing", "freshness", "ledger_publish", "postflight"],
    "evening_ledger": ["repair_scan", "card_materialization", "ledger_publish", "postflight"],
}


def selected_layers(raw_layers: list[str] | None) -> list[str]:
    selected: list[str] = []
    for raw in raw_layers or ["daily_core_v2"]:
        for part in str(raw).split(","):
            name = part.strip()
            if not name:
                continue
            for layer in ALIASES.get(name, [name]):
                if layer not in selected:
                    selected.append(layer)
    return selected


def structural_errors(raw_layers: list[str] | None = None) -> list[str]:
    errors: list[str] = []
    daily = build_daily_steps()
    names = [step.name for step in daily]
    duplicates = sorted({name for name in names if names.count(name) > 1})
    errors.extend(f"duplicate_daily_step:{name}" for name in duplicates)
    for step in daily:
        for dep in step.depends_on:
            if dep not in names:
                errors.append(f"unknown_daily_dependency:{step.name}:{dep}")
    layers = selected_layers(raw_layers)
    for layer_name in layers:
        layer = LAYER_DEFS.get(layer_name)
        if layer is None:
            errors.append(f"unknown_layer:{layer_name}")
            continue
        if layer.phase and not steps_for_phase(layer.phase, skip_provider_refresh=True, full_answer_mode="never"):
            errors.append(f"layer_phase_empty:{layer_name}:{layer.phase}")
        command_names = [step.name for step in layer.commands]
        for step in layer.commands:
            for dep in step.depends_on:
                if dep not in command_names:
                    errors.append(f"unknown_layer_dependency:{layer_name}:{step.name}:{dep}")
    return errors


def manifest_summary(raw_layers: list[str] | None = None) -> dict[str, Any]:
    daily = build_daily_steps()
    layers = selected_layers(raw_layers)
    return {
        "daily_step_count": len(daily),
        "phase_counts": {phase: sum(1 for step in daily if step.phase == phase) for phase in sorted(PHASE_ALIASES["all"])},
        "selected_layers": layers,
        "layer_count": len(layers),
        "structural_errors": structural_errors(raw_layers),
        "cron_contracts": {
            "wf78_daily_freshness": rel(STATE / "cron-contracts" / "finance-wf78-daily-freshness-and-promotion-proof.json"),
        },
        "wf86_wf87_trigger_policy": {
            "wf86_shadow_decisions": "refreshed by WF86 shadow/reconciliation routes and surfaced through WF87 market-hours probe into tmp/paper-autotrader/shadow-decisions.json",
            "wf87_market_hours": "cron-triggered during market-hours fresh-gate probe",
            "wf87_command_center": "cron-triggered after market-hours probe as owner-facing readiness state",
        },
    }
