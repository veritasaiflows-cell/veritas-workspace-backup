"""Workflow routing index (derived, review-only route map).

Mirrors the P0/P1/P2 active/monitor rows and P3 paused rows in
`06. Playbooks/Active Workflows.md` into a single derived route object so a new
session, helper lane, or status answer can jump straight to a workflow's
continuity note, primary proof artifact, validators, blockers, stop lines, and
next action without a broad workspace search.

Active Workflows is the live authority. This index is a derived route map only:
it never outranks Active Workflows or the exact continuity notes, and it carries
no canon/portfolio/SQL/approval/execution authority.

Phase 1 (--write): build `tmp/workflow-routing-index.json` with every P0/P1/P2/P3
route row and the 16 required route fields, resolving on-disk existence for the
continuity note and proof artifacts it points at.

Phase 2 (--validate): emit `tmp/workflow-routing-index-validation.json`.
  C  schema_version, route count, or tier-count drift from the expected
     P0/P1/P2/P3 coverage set
  C  missing required field on a route row
  C  invalid route field type or empty required string
  C  stop_lines empty (every route must carry a stop line)
  C  authority widening (any approval/execution/mutation flag flipped true,
     or owner_action_required dropped on an owner-gated row)
  C  freshness or helper-handoff authority/mode regression
  W  continuity_note path declared but absent on disk (coverage gap)
  W  primary_route_artifact path declared, not pending, and absent on disk
  W  no validator_commands on an active build lane (P0/P1)

Critical findings block (status -> "blocked"); warnings keep status "ok" while
surfacing coverage gaps. Report-only: no canon/portfolio/SQL mutation, no
paper/live/brokerage/account action, no owner-approval inference.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from lib.workflow_control import apply_route_override, load_registry

ROOT = Path(__file__).resolve().parents[1]
INDEX_OUT = ROOT / "tmp" / "workflow-routing-index.json"
VALIDATION_OUT = ROOT / "tmp" / "workflow-routing-index-validation.json"
DB_OUT = ROOT / "tmp" / "workflow-routing-index.sqlite"
HANDOFF_DIR = ROOT / "tmp"

CONTINUITY = "06. Playbooks/Project Continuity"

REQUIRED_FIELDS = (
    "workflow_id",
    "display_name",
    "tier",
    "current_state",
    "next_action",
    "continuity_note",
    "primary_route_artifact",
    "secondary_artifacts",
    "validator_commands",
    "last_validated_at",
    "blockers",
    "stop_lines",
    "authority_boundary",
    "owner_action_required",
    "safe_for_helper_lane",
    "default_resume_command",
)

EXPECTED_ROUTE_COUNT = 35
EXPECTED_TIER_COUNTS = {"P0": 6, "P1": 15, "P2": 10, "P3": 4}
FRESHNESS_SCORES = {"fresh", "aging", "stale", "missing", "n/a"}
HANDOFF_MODES = {"Spawn read-only", "Main-session only"}

# Review-only authority clamp. Mirrors the Active Workflows global authority
# rules. The validator treats any of these flipping true (other than
# review_only) as authority widening.
AUTHORITY = {
    "review_only": True,
    "canonical_mutation_allowed": False,
    "portfolio_mutation_allowed": False,
    "sql_canon_promotion_allowed": False,
    "customer_or_public_output_allowed": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "cron_config_runtime_mutation_allowed": False,
    "owner_approval_inferred": False,
}

LIST_FIELDS = ("secondary_artifacts", "validator_commands", "blockers", "stop_lines")
BOOL_FIELDS = ("owner_action_required", "safe_for_helper_lane", "primary_pending")


def route(
    workflow_id: str,
    display_name: str,
    tier: str,
    current_state: str,
    next_action: str,
    continuity_note: str | None,
    primary_route_artifact: str | None,
    secondary_artifacts: list[str],
    validator_commands: list[str],
    blockers: list[str],
    stop_lines: list[str],
    authority_boundary: str,
    owner_action_required: bool,
    safe_for_helper_lane: bool,
    default_resume_command: str | None,
    primary_pending: bool = False,
    effective_status_override: str | None = None,
) -> dict[str, Any]:
    row = {
        "workflow_id": workflow_id,
        "display_name": display_name,
        "tier": tier,
        "current_state": current_state,
        "next_action": next_action,
        "continuity_note": continuity_note,
        "primary_route_artifact": primary_route_artifact,
        "primary_pending": primary_pending,
        "secondary_artifacts": secondary_artifacts,
        "validator_commands": validator_commands,
        "last_validated_at": None,  # filled at build time
        "blockers": blockers,
        "stop_lines": stop_lines,
        "authority_boundary": authority_boundary,
        "owner_action_required": owner_action_required,
        "safe_for_helper_lane": safe_for_helper_lane,
        "default_resume_command": default_resume_command,
    }
    if effective_status_override:
        row["effective_status_override"] = effective_status_override
    return row


# Stop-line phrasing reused across review-only lanes.
_REVIEW_STOP = (
    "Index is a derived route map; Active Workflows and exact continuity notes "
    "stay authority. No canon/portfolio/ticker-card/SQL-canon mutation, no "
    "paper/live/brokerage/account action, no cron/config/runtime mutation, no "
    "owner-approval inference from any route row."
)


def build_routes() -> list[dict[str, Any]]:
    return [
        # ---- P0 ----
        route(
            "WF75",
            "Retail Investor Finance Intelligence SaaS",
            "P0",
            "Internal/service-led finance vertical: anonymous scenarios, "
            "service-state, operator console, renderer/export, PM handoff, WF77 "
            "evidence, macro/recommendation tracking, polished PDF/Excel packaging, recurring finance delivery series, authority spine.",
            "Run/refine the next anonymous service-state slice and keep the internal PM PDF, operator Excel, and recurring finance delivery series current.",
            f"{CONTINUITY}/Workflow 75 - AI Productivity and Business Opportunity Intelligence Expansion.md",
            "scripts/wf75_training_desk.py",
            [
                "tmp/wf75-operator-console.json",
                "tmp/wf75-service-state-current.json",
                "tmp/wf75-deliverable-packager.json",
                "tmp/wf75-deliverables-workbook.xlsx",
                "tmp/finance-delivery-series.json",
                "tmp/finance-delivery-series.xlsx",
            ],
            [
                "python scripts\\wf75_training_desk.py --write --write-md --write-training-assets --validate",
                "python scripts\\wf75_deliverable_packager.py --write --validate",
                "python scripts\\finance_delivery_series_orchestrator.py --mode all --write --validate",
            ],
            ["Customer/public/account/advice output blocked", "No fake-person product truth"],
            [
                "No fake-person product truth, public/customer/account/advice/trading claims, "
                "guaranteed return/win-rate/probability claim, source-licensing assumption, "
                "or legal/compliance-readiness claim.",
            ],
            "review-only internal/service-led; customer output gated",
            True,
            True,
            None,
        ),
        route(
            "WF-RETAIL-ROUTING",
            "Retail-Grade Truth Routing System",
            "P0",
            "Phase 1-4 and Phase 4.5-7 automation built, validated, "
            "scorecard-green, scheduled through review-only guard cron.",
            "Keep routing, harness, automation plane, PM/cockpit Retail tab, "
            "customer-safety gate, freshness prompts, demo cards clean; "
            "customer-safe output waits for Randall.",
            None,  # no dedicated continuity note; routes through Active Workflows + scripts
            "scripts/retail_truth_routing_contract.py",
            ["scripts/retail_answer_harness.py", "scripts/retail_automation_control_plane.py"],
            [
                "python scripts\\retail_truth_routing_contract.py --write --validate",
                "python scripts\\retail_answer_harness.py --write --validate",
                "python scripts\\retail_automation_control_plane.py --write --validate",
            ],
            ["Customer-safe output waits for Randall"],
            [
                "No SQL-first promotion, SQL writes/imports, customer/external output, "
                "canon/portfolio mutation, paper/live/account action, Python fallback "
                "retirement, cron mutation, or approval inference.",
            ],
            "review-only internal routing; customer output gated",
            True,
            True,
            "python scripts\\retail_truth_routing_contract.py --write --validate",
        ),
        # ---- P1 ----
        route(
            "WF79-SMB",
            "SMB Workflow Clarity / Marketing Ops Automation",
            "P1",
            "Resumed by Randall on 2026-06-13 as an automation-first "
            "monetization lane: Lead Rescue, workflow clarity, marketing "
            "operations follow-up engine, Academy assets, local cockpit/SQL "
            "service-state, and boundary proof.",
            "Review completed sanitized Lead Rescue and Marketing Ops phase "
            "proof: offer/ICP packet, demo packets, automation blueprints, "
            "cockpit panel, training/sales practice, outreach kit, pilot "
            "scope/intake, vertical ICP targeting, demo polish, pilot-readiness "
            "packet, sales conversation drill, demo-selection tree, vertical "
            "test framework, rollout-readiness plan, client-rollout checklist, "
            "curriculum map, and validator lint. Next gate is Randall exact "
            "approval for real outreach or pilot use; do not contact real "
            "prospects yet.",
            None,
            "scripts/generic_intelligence_saas_pivot.py",
            [
                "scripts/wf75_training_desk.py",
                "tmp/wf75-smb-boundary-lint.json",
                "tmp/wf79-smb-outreach-prep-validation.json",
                "tmp/wf79-smb-pilot-readiness-validation.json",
                "tmp/wf79-smb-rollout-readiness-validation.json",
            ],
            ["python scripts\\generic_intelligence_saas_pivot.py --write --write-db --validate"],
            ["No real customer data/outbound/public claims"],
            [
                "No real customer data, credentials, outbound/writeback, external delivery, "
                "ROI/legal/compliance/security claims, spend, ad account action, SQL-as-canon, "
                "or certification claims.",
            ],
            "review-only; no customer/outbound/public",
            True,
            True,
            "python scripts\\generic_intelligence_saas_pivot.py --write --write-db --validate",
        ),
        route(
            "WF79",
            "Veritas Command Center V2 UI Infrastructure",
            "P1",
            "Compact shell is promoted as the active Veritas first-read route; "
            "Randall full-detail legacy dashboard and dashboard-data.json remain "
            "retained by design for row-level drilldown/rollback. Adapter mode "
            "compact_primary_legacy_passthrough (29 compact-primary, 4 metadata, "
            "0 legacy-only routes). Render-default proof: 4 safe disable paths, "
            "0 unsafe.",
            "Use compact reader/shell as active route; keep legacy full-detail "
            "dashboard for Randall drilldown. Optional future work is legacy "
            "payload retirement, not a blocking Path B dependency.",
            f"{CONTINUITY}/Workflow 79 - Veritas Command Center V2 UI Infrastructure.md",
            "tmp/presentation-retrieval-route-map.json",
            [
                f"{CONTINUITY}/Presentation Artifact Flattening and Retrieval Routing.md",
                f"{CONTINUITY}/Deployment State Contract Migration.md",
                "tmp/veritas-command-center-compact-reader.json",
                "tmp/veritas-command-center-compact.html",
                "tmp/veritas-command-center.html",
                "tmp/dashboard-presentation-view-model.json",
            ],
            ["python scripts\\deployment_contract_migration_validation_bundle.py --write"],
            [],
            [
                "Local/review-only UI. No canon/portfolio mutation, paper/live/account action, "
                "approval inference, public/customer delivery, SQL promotion, proof deletion, "
                "sidecar archive/delete, or config/channel/runtime expansion.",
            ],
            "review-only local UI",
            True,
            True,
            None,
        ),
        route(
            "WF72",
            "Financial OS SQL Support",
            "P1",
            "265-row cache boundary and A2 fallback read guard are green. "
            "WF72 is formally demoted to support/index/cache infrastructure "
            "below the WF84/WF85 ticker-answer route, not the finance front door.",
            "Keep support-only mode; use WF72 only for read-only lookup, cache "
            "guard, artifact index, and fast-path QA support. Separate gate "
            "required before consumer promotion, Python retirement, SQL-first "
            "use, or any finance answer-path ownership.",
            f"{CONTINUITY}/Workflow 72 - Financial OS Efficiency Restructure and Priority Compression.md",
            "tmp/veritas-canon-cache.sqlite",
            ["state/finance/finance-canon.sqlite", "tmp/veritas-artifact-index.sqlite", "tmp/fast-path-qa.json"],
            ["python scripts\\artifact_index.py validate", "python scripts\\fast_path_qa.py --write --validate"],
            ["Separate gate required before SQL-first use / Python retirement"],
            [
                "No SQL write expansion, archive/move/delete without proof, "
                "action-state/canon/portfolio mutation, customer output, runtime/config "
                "mutation, Python retirement, SQL-first promotion, finance front-door "
                "ownership, or approval inference.",
            ],
            "support-only; SQL is proof/index, not canon/approval",
            True,
            True,
            None,
            effective_status_override="support_only",
        ),
        route(
            "WF68",
            "Intraday Alert Engine and Advisor Surface",
            "P1",
            "Reduced-load internal alert/advisor proof; Telegram shadow and "
            "high-frequency handoff paused; authority flags false.",
            "Keep producer/digest proof clean; manual REVIEW / PREPARE only "
            "after artifact + WF67 guard inspection.",
            f"{CONTINUITY}/Workflow 68 - Intraday Alert Engine and Advisor Surface.md",
            None,
            [],
            ["python scripts\\wf68_runtime_wiring_plan_validator.py --write"],
            ["Telegram shadow delivery paused", "authority flags false"],
            [
                "No channel expansion, config/auth/runtime mutation, live/paper/order/account "
                "action, canon/portfolio/sizing/sleeve/cash/risk-rule mutation, or approval inference.",
            ],
            "review-only; manual REVIEW/PREPARE gated",
            True,
            False,
            None,
        ),
        route(
            "WF73",
            "Queue/Index/Boot Optimization",
            "P1",
            "Boot/control routing, PM queue, cron freshness spine, cron "
            "retire/merge, helper manifest, hardening pass, cockpit proof "
            "active. Workflow routing index covers 33 routes, derived SQLite "
            "route-control lookup is live, concurrent lane lease register is "
            "live, ordered WF73 audit runner is active, and truth-surface/"
            "efficiency proof is active. Local Postgres coordination-spine "
            "Phase D/E review artifacts are complete; shadow-pilot telemetry "
            "is active with JSON primary. All remain derived/review-only.",
            "Use wf73_control_plane_audit.py for full WF73 audits; use canned "
            "SQL route-control lookups after JSON/DB parity is green; use lane "
            "manager before intentional multi-helper work. Monitor shadow "
            "metrics only; no Postgres service, SQL execution, or lane-claim "
            "authority is active.",
            f"{CONTINUITY}/Workflow 73 - Queue Index and Boot Surface Optimization.md",
            "tmp/workflow-routing-index.json",
            [
                f"{CONTINUITY}/Workflow Routing Index Expansion.md",
                "tmp/workflow-routing-index.sqlite",
                "tmp/concurrent-lane-register.json",
                "tmp/truth-surface-inventory.json",
                "tmp/route-efficiency-scorecard.json",
                "tmp/fast-path-qa.json",
                "tmp/wf73-control-plane-audit.json",
                "tmp/wf73-postgres-coordination-spine-plan.json",
                "tmp/wf73-postgres-schema-adapter-proposal.json",
                "tmp/wf73-postgres-phase-e-review-packet.json",
                "tmp/wf73-postgres-ddl-contract-review.json",
                "tmp/wf73-postgres-parity-validator-spec-review.json",
                "tmp/wf73-postgres-failure-drills-review.json",
                "tmp/wf73-postgres-windows-runtime-matrix-review.json",
                "tmp/wf73-postgres-go-no-go-review.json",
                "tmp/wf73-postgres-shadow-pilot.json",
                "tmp/wf73-postgres-shadow-pilot-metrics.json",
                "scripts/concurrent_lane_manager.py",
                "scripts/wf73_postgres_shadow_pilot.py",
                "tmp/cron-freshness-spine.json",
            ],
            [
                "python scripts\\wf73_control_plane_audit.py --write --validate",
                "python scripts\\workflow_routing_index.py --write --write-db --validate",
                "python scripts\\concurrent_lane_manager.py --status --write --validate",
                "python scripts\\wf73_postgres_shadow_pilot.py --write --validate",
                "python scripts\\truth_surface_inventory.py --write --validate",
                "python scripts\\fast_path_qa.py --write --validate",
                "python scripts\\cron_freshness_spine.py --write --validate",
            ],
            [],
            [
                "No new authority source, doctrine rewrite, destructive/config/channel/runtime "
                "mutation, Postgres/Docker/native-service install, network exposure, "
                "authority weakening, SQL-first promotion, autonomous spawning/scheduling, "
                "or inferred approval.",
            ],
            "review-only route capacity; index never outranks Active Workflows",
            False,
            True,
            "python scripts\\workflow_routing_index.py --write --write-db --validate",
        ),
        route(
            "WF70-WF66",
            "Official Evidence Spine",
            "P1",
            "Registry/latest-selector migration complete; official "
            "earnings/reconciliation routes have no-drift proof.",
            "Monitor validators; capture/roll forward only for active "
            "finance/product goals.",
            f"{CONTINUITY}/Workflow 70 - Official Company Source Capture and Reconciliation.md",
            None,
            [f"{CONTINUITY}/Workflow 66 - Why-Aware Recommendation Packet Evidence Bridge.md"],
            ["python scripts\\wf70_wf66_official_evidence_spine.py --validate-only"],
            [],
            [
                "No invented values, no bridge-present-equals-reconciled shortcut, no "
                "portfolio/canon/trade authority from evidence alone, no owner approval inference.",
            ],
            "evidence-only; no portfolio/trade authority",
            True,
            True,
            None,
        ),
        route(
            "WF77",
            "Finance Coverage / Question Router",
            "P1",
            "42/42 production cards enriched; active 200-card review set "
            "rebuilds with stale-evidence repair signals. Shared "
            "deployment-state contract available; 200-card rebuild passed after "
            "Slice 6. WF77 now feeds coverage/card/source proof into the "
            "finance_intelligence_state -> WF84 -> WF85 answer route.",
            "Use finance_intelligence_state.py ticker <TICKER> first for "
            "finance questions. Use WF77 for ticker-card coverage/source proof "
            "and refresh repair before promotion-quality WF84/WF85 use.",
            f"{CONTINUITY}/Workflow 77 - Finance Intelligence Coverage and Question Router.md",
            "scripts/finance_intelligence_state.py",
            [
                f"{CONTINUITY}/Deployment State Contract Migration.md",
                "scripts/artifact_index.py",
            ],
            ["python scripts\\artifact_index.py validate"],
            [],
            [
                "Review/intelligence only; no live trading/account/money movement, paper "
                "execution, approval inference, import/apply, production promotion, or "
                "canon/portfolio mutation.",
            ],
            "review/intelligence only",
            True,
            True,
            None,
        ),
        route(
            "WF78",
            "500 Ticker Scaleout / Promotion",
            "P1",
            "200 active rows. Auto-router currently classifies 19 Tier A, 29 Tier B, "
            "152 Tier C. Tier A confidence gate blocks conflicted rows from "
            "A-READY. Daily delta, route-TICKER, capital-review queue, AI "
            "event-triggered rerouting, evidence-drag reduction, family-level "
            "repair routing, source-open repair execution, source-open work packets, "
            "position-sizing review, deployment-readiness review, source-artifact capture review, "
            "sizing integration proposals, Tier A owner-readiness proposals, missing-band repair, source-capture requirements, "
            "official-source discovery, official registry proposals, registry apply preview, "
            "promotion-only owner-lineage queue, contract guard, owner-lineage discovery, owner-lineage proposal, repair scoreboard, "
            "scaleout policy dry run, tier-weighted freshness resolution, "
            "daily movement ledger, repair-priority queue, Intelligence Routing V2, "
            "PH owner-review packet, Tier A invalidation queue, official source-capture packet, "
            "ticker freshness ledger, daily freshness loop, and artifact action scoring are built. Repeatable "
            "parallel orchestration still handles macro/evidence/card-prep work; all "
            "surfaces have 0 capital/trade approvals.",
            "WF78 is the non-capital repair/promotion feeder for the "
            "finance_intelligence_state -> WF84 -> WF85 answer route. "
            "Use wf78_intelligence_routing_v2.py --layer daily_core_v2 --fail-on-budget-exceeded as the promoted daily cron surface, with wf78_daily_movement_ledger.py as the operator ledger; keep wf78_daily_freshness_loop.py as a compatibility refresh/routing/debt "
            "measurement spine, then use tier-weighted freshness resolution for the 200-row debt answer. Use source-open repair execution, source-open work "
            "packets, concrete sizing/deployment/source-capture reviews, integration proposals, "
            "Tier A owner-readiness proposals, missing-band repair, source-capture requirements, owner-lineage proposal, freshness ledger, tier-weighted resolver, daily movement ledger, and repair-priority queue "
            "for Tier A/B repair routing before owner-card prep. Use the repair debt scoreboard first: "
            "review ready sizing/deployment rows, keep owner-lineage rows blocked for owner/source decision, "
            "and treat registry apply preview as a separate gated path. Keep CME/LMT/META in invalidation "
            "review. The market deployment operating loop now reads WF78 tier movement "
            "beside WF85 timing and WF87 daylight proof so tier changes, freshness, "
            "opportunity probes, and autonomous review-card materialization are visible "
            "as one review-only chain. Ask only for capital/execution/account/sizing/apply mutation.",
            f"{CONTINUITY}/Workflow 78 - 500 Ticker Finance Intelligence Scaleout.md",
            "tmp/wf78-auto-tier-routing.json",
            [
                "scripts/wf78_tier_a_confidence_gate.py",
                "scripts/wf78_auto_tier_router.py",
                "scripts/wf78_event_triggered_rerouting.py",
                "scripts/wf78_evidence_drag_reducer.py",
                "scripts/wf78_evidence_family_repair_runner.py",
                "scripts/wf78_source_open_repair_executor.py",
                "scripts/wf78_source_open_work_packet.py",
                "scripts/wf78_position_sizing_surface_review.py",
                "scripts/wf78_deployment_readiness_review.py",
                "scripts/wf78_source_artifact_capture_review.py",
                "scripts/wf78_position_sizing_integration_proposal.py",
                "scripts/wf78_tier_a_owner_readiness_proposal.py",
                "scripts/wf78_missing_band_context_repair.py",
                "scripts/wf78_source_capture_requirements_queue.py",
                "scripts/wf78_official_source_discovery_runner.py",
                "scripts/wf78_official_registry_proposal.py",
                "scripts/wf78_official_registry_apply_preview.py",
                "scripts/wf78_promotion_owner_lineage_queue.py",
                "scripts/wf78_contract_state_guard.py",
                "scripts/wf78_owner_lineage_discovery.py",
                "scripts/wf78_owner_lineage_proposal.py",
                "scripts/wf78_repair_debt_scoreboard.py",
                "scripts/wf78_scaleout_policy_dry_run.py",
                "scripts/wf78_ph_owner_review_candidate_packet.py",
                "scripts/wf78_tier_a_invalidation_review_queue.py",
                "scripts/wf78_official_source_capture_packet.py",
                "scripts/wf78_next_owner_review_and_source_capture_integration.py",
                "scripts/wf78_ticker_freshness_ledger.py",
                "scripts/wf78_tier_weighted_freshness_resolver.py",
                "scripts/wf78_daily_freshness_loop.py",
                "scripts/wf78_daily_movement_ledger.py",
                "scripts/wf78_intelligence_routing_v2.py",
                "scripts/parallel_repeatable_work_orchestrator.py",
                "scripts/repeatable_work_closeout.py",
                "scripts/finance_decision_factory.py",
                "scripts/wf78_evidence_repair_batch_runner.py",
                "scripts/control_closeout_bundle.py",
                "scripts/pm_execution_loop.py",
                "scripts/artifact_intelligence_action_scorer.py",
                "scripts/finance_market_deployment_operating_loop.py",
                "scripts/autonomous_routing_deployment_cards.py",
                "scripts/test_autonomous_routing_deployment_cards.py",
                "tmp/wf78-tier-a-confidence-gate.json",
                "tmp/wf78-event-triggered-rerouting.json",
                "tmp/wf78-evidence-drag-reduction.json",
                "tmp/wf78-evidence-family-repair.json",
                "tmp/wf78-source-open-repair-execution.json",
                "tmp/wf78-source-open-work-packets.json",
                "tmp/wf78-position-sizing-surface-review.json",
                "tmp/wf78-deployment-readiness-review.json",
                "tmp/wf78-source-artifact-capture-review.json",
                "tmp/wf78-position-sizing-integration-proposal.json",
                "tmp/wf78-tier-a-owner-readiness-proposals.json",
                "tmp/wf78-missing-band-context-repair.json",
                "tmp/wf78-source-capture-requirements-queue.json",
                "tmp/wf78-official-source-discovery.json",
                "tmp/wf78-official-registry-proposal.json",
                "tmp/wf78-official-registry-apply-preview.json",
                "tmp/wf78-promotion-owner-lineage-queue.json",
                "tmp/wf78-contract-state-guard.json",
                "tmp/wf78-owner-lineage-discovery.json",
                "tmp/wf78-owner-lineage-proposal.json",
                "tmp/wf78-repair-debt-scoreboard.json",
                "tmp/wf78-scaleout-policy-dry-run.json",
                "tmp/wf78-ph-owner-review-candidate-packet.json",
                "tmp/wf78-tier-a-invalidation-review-queue.json",
                "tmp/wf78-official-source-capture-packet.json",
                "tmp/wf78-next-owner-review-and-source-capture-integration.json",
                "tmp/wf78-ticker-freshness-ledger.json",
                "tmp/wf78-tier-weighted-freshness-resolution.json",
                "tmp/wf78-daily-freshness-loop.json",
                "tmp/wf78-daily-movement-ledger.json",
                "tmp/wf78-repair-priority-queue.json",
                "tmp/wf78-intelligence-routing-v2.json",
                "tmp/parallel-repeatable-work-orchestration.json",
                "tmp/macro-event-guard-loop.json",
                "tmp/wf78-owner-card-prep-loop.json",
                "tmp/wf78-tier-a-evidence-repair-batch.json",
                "tmp/repeatable-work-closeout.json",
                "tmp/finance-decision-factory.json",
                "tmp/wf78-evidence-repair-batch.json",
                "tmp/control-closeout-bundle.json",
                "tmp/pm-execution-loop.json",
                "tmp/artifact-intelligence-action-scorer.json",
                "tmp/finance-market-deployment-operating-loop.json",
                "tmp/autonomous-routing-deployment-cards.json",
                "tmp/wf78-routing-dashboard.json",
            ],
            [
                "python scripts\\finance_decision_factory.py --write --validate",
                "python scripts\\wf78_evidence_repair_batch_runner.py --tier A --write --validate",
                "python scripts\\wf78_evidence_family_repair_runner.py --family price_band_stop --write --validate",
                "python scripts\\wf78_source_open_repair_executor.py --write --validate",
                "python scripts\\wf78_source_open_work_packet.py --write --validate",
                "python scripts\\wf78_position_sizing_surface_review.py --write --validate",
                "python scripts\\wf78_deployment_readiness_review.py --write --validate",
                "python scripts\\wf78_source_artifact_capture_review.py --write --validate",
                "python scripts\\wf78_position_sizing_integration_proposal.py --write --validate",
                "python scripts\\wf78_tier_a_owner_readiness_proposal.py --write --validate",
                "python scripts\\wf78_missing_band_context_repair.py --write --validate",
                "python scripts\\wf78_source_capture_requirements_queue.py --write --validate",
                "python scripts\\wf78_official_source_discovery_runner.py --write --validate",
                "python scripts\\wf78_official_registry_proposal.py --write --validate",
                "python scripts\\wf78_official_registry_apply_preview.py --write --write-proposed --validate",
                "python scripts\\wf78_promotion_owner_lineage_queue.py --write --validate",
                "python scripts\\wf78_contract_state_guard.py --write --validate",
                "python scripts\\wf78_owner_lineage_discovery.py --write --validate",
                "python scripts\\wf78_owner_lineage_proposal.py --write --validate",
                "python scripts\\wf78_repair_debt_scoreboard.py --write --validate",
                "python scripts\\wf78_scaleout_policy_dry_run.py --write --validate",
                "python scripts\\wf78_ph_owner_review_candidate_packet.py --write --validate",
                "python scripts\\wf78_tier_a_invalidation_review_queue.py --write --validate",
                "python scripts\\wf78_official_source_capture_packet.py --write --validate",
                "python scripts\\wf78_next_owner_review_and_source_capture_integration.py --write --validate",
                "python scripts\\wf78_ticker_freshness_ledger.py --write --validate",
                "python scripts\\wf78_tier_weighted_freshness_resolver.py --write --validate",
                "python scripts\\wf78_daily_movement_ledger.py --write --write-md --validate",
                "python scripts\\wf78_intelligence_routing_v2.py --layer ledger_publish --write --validate",
                "python scripts\\wf78_daily_freshness_loop.py --write --validate",
                "python scripts\\parallel_repeatable_work_orchestrator.py --write --validate",
                "python scripts\\repeatable_work_closeout.py --write --validate",
                "python scripts\\control_closeout_bundle.py --write --validate",
                "python scripts\\wf78_phase_runner.py --phase all-safe --write --validate",
                "python scripts\\wf78_evidence_drag_reducer.py --write --validate",
                "python scripts\\artifact_intelligence_action_scorer.py --write --validate",
                "python scripts\\finance_market_deployment_operating_loop.py --refresh-readiness --write --write-md --validate",
            ],
            [],
            [
                "Automated routing is non-capital only; no capital deployment, paper/live "
                "order, brokerage/account action, money movement, portfolio/cash/sizing "
                "execution, customer/public output, or SQL-first/canon authority without "
                "separate exact approval/gates. No generated artifact implies trade approval.",
            ],
            "automated non-capital routing; capital/execution gated",
            True,
            True,
            "python scripts\\wf78_phase_runner.py --phase all-safe --write --validate",
        ),
        route(
            "WF84",
            "Trade-Grade Personal Finance OS Canonical Data Model",
            "P0",
            "Internal finance infrastructure lane opened for a formal canonical "
            "data-plane contract, read-only packet, and derived SQLite companion. "
            "WF78 and finance-intelligence state may feed it only through "
            "validated non-capital artifacts.",
            "Use the validated JSON packet, SQLite companion, and phase 6-10 "
            "proof for internal read-only consumer expansion; use full-answer "
            "parity before duplicate-surface retirement.",
            f"{CONTINUITY}/Workflow 84 - Trade-Grade Personal Finance OS Canonical Data Model.md",
            "tmp/canonical-finance-data-plane.json",
            [
                "scripts/canonical_finance_data_plane_contract.py",
                "scripts/canonical_finance_data_plane.py",
                "scripts/canonical_finance_data_plane_phase6_10.py",
                "scripts/full_intelligence_answer_parity.py",
                "tmp/canonical-finance-data-plane-contract.json",
                "tmp/canonical-finance-data-plane-validation.json",
                "tmp/canonical-finance-data-plane.sqlite",
                "tmp/canonical-finance-data-plane-phase6-10.json",
                "tmp/canonical-finance-data-plane-retirement-readiness.json",
                "tmp/full-answer-parity/full-answer-parity-rollup.json",
                "tmp/wf78-auto-tier-routing.json",
                "tmp/finance-intelligence-state.sqlite",
                "tmp/wf78-tier-weighted-freshness-resolution.json",
                "tmp/finance-decision-sync-spine.json",
            ],
            [
                "python scripts\\canonical_finance_data_plane_contract.py --write --validate",
                "python scripts\\canonical_finance_data_plane.py --write --write-db --validate",
                "python scripts\\full_intelligence_answer_parity.py --all --write --pretty",
                "python scripts\\canonical_finance_data_plane_phase6_10.py --write --validate",
                "python scripts\\canonical_finance_data_plane_retirement_readiness.py --write --validate",
                "python scripts\\db_lifecycle_manifest.py --write --validate",
                "python scripts\\workflow_routing_index.py --write --write-db --validate",
                "python scripts\\workflow_router.py WF84 --answer all --write-capsules --validate",
            ],
            [],
            [
                "Internal personal finance infrastructure only; no retail/customer launch, "
                "customer/account/PII/suitability/brokerage data, canon/portfolio/cash/"
                "risk-rule mutation, capital approval, paper/live/account action, SQL/"
                "capsule/dashboard row as approval, or owner approval inference.",
            ],
            "internal review-only canonical data-plane interface; no customer/account/execution authority",
            True,
            True,
            "python scripts\\canonical_finance_data_plane_phase6_10.py --write --validate",
        ),
        route(
            "WF85",
            "Personal Trade-Grade Decision OS",
            "P0",
            "Contract and Phase 1 builder are active above WF84. The builder "
            "emits fail-closed review-only decision cards, source/freshness "
            "gate, authority/vocabulary validation, approval-card gate, and "
            "risk/sizing overlay; the repair conveyor routes finance-domain blockers "
            "back to WF78/WF84 feeder repair without creating implementation blockers "
            "unless conveyor validation or WF84/WF85 quality gates regress. Tier A/B "
            "rows require daily decision-grade entry-band/stop coverage for finance "
            "review; missing coverage is finance-domain debt, while canon/note apply "
            "remains limited to the approved entry_band maintenance gate. A cron guard "
            "proves complete Tier A/B band rows carry current market-date context and "
            "cron contracts include the required artifacts. Primary-state blockers and below-stop states "
            "override optimistic auto_state; generated approval drafts remain "
            "zero until all gates and fresh WF67 guard context pass; exact "
            "paper execution still routes through WF67 only after Randall "
            "approves the scoped order. The market deployment operating loop "
            "now unifies the morning/intraday cron schedule, WF78 tier routing, "
            "WF84/WF85 freshness, WF85 timing, WF87 daylight gates, and Tier A "
            "opportunity probes into one review-only trade-readiness packet. The "
            "autonomous routing/card queue materializes owner-review references only "
            "when WF78/WF85/WF87 gates agree and keeps execution authority false.",
            "WF85 full-answer parity is clean across the 200-ticker WF84 population, "
            "and targeted production blockers have been repaired or adjudicated: "
            "missing band/stop, freshness, and source-open blocker counts are now "
            "zero; remaining rows are true no-chase, true below-stop/invalidation, "
            "or finance-domain repair/monitor states that do not create PM implementation "
            "blockers while conveyor validation and quality gates remain clean. Tier A/B "
            "missing decision-grade band/stop coverage is refreshed daily as finance-domain "
            "debt, not auto-applied to canon. The WF85 full-answer "
            "assembler now owns the default ticker-answer contract; legacy answer "
            "packets are compatibility snapshots generated from the assembler. "
            "Retirement planning may continue, but archive/delete/apply and "
            "source-feeder retirement remain false until exact owner approval.",
            f"{CONTINUITY}/Workflow 85 - Trade-Grade Decision and Approval Card OS.md",
            "tmp/trade-grade-decision-cards.json",
            [
                "scripts/trade_grade_decision_os_contract.py",
                "scripts/trade_grade_decision_cards.py",
                "scripts/trade_grade_repair_conveyor.py",
                "scripts/trade_grade_os_freshness_cron_runner.py",
                "scripts/trade_grade_os_readiness_rollup.py",
                "scripts/test_trade_grade_os_readiness_rollup.py",
                "scripts/wf85_deployment_timing_gate.py",
                "scripts/test_wf85_deployment_timing_gate.py",
                "scripts/finance_market_deployment_operating_loop.py",
                "scripts/test_finance_market_deployment_operating_loop.py",
                "scripts/autonomous_routing_deployment_cards.py",
                "scripts/test_autonomous_routing_deployment_cards.py",
                "scripts/autonomous_card_authority_audit.py",
                "scripts/test_autonomous_card_authority_audit.py",
                "scripts/trade_grade_full_answer_assembler.py",
                "scripts/wf78_missing_band_context_repair.py",
                "scripts/tier_ab_band_freshness_cron_guard.py",
                "scripts/wf85_retirement_gate_adjudication.py",
                "scripts/wf85_production_blocker_repair.py",
                "scripts/ticker_answer_packet_retirement_plan.py",
                "tmp/trade-grade-decision-os-contract.json",
                "tmp/trade-grade-source-freshness-gate.json",
                "tmp/trade-grade-decision-cards.json",
                "tmp/trade-grade-decision-card-authority-validation.json",
                "tmp/trade-grade-approval-card-gate.json",
                "tmp/trade-grade-risk-sizing-overlay.json",
                "tmp/wf85-deployment-timing-gate.json",
                "tmp/finance-market-deployment-operating-loop.json",
                "tmp/autonomous-routing-deployment-cards.json",
                "tmp/trade-grade-full-answer-assembler.json",
                "tmp/wf85-retirement-gate-adjudication.json",
                "tmp/wf85-production-blocker-repair.json",
                "tmp/ticker-answer-packet-retirement-approval-plan-20260609.json",
                "tmp/wf85-full-answer-assembler-opus-challenger-20260609.json",
                "tmp/trade-grade-repair-conveyor.json",
                "tmp/trade-grade-os-freshness-cron-runner.json",
                "tmp/trade-grade-os-readiness-rollup.json",
                "tmp/wf78-missing-band-context-repair.json",
                "tmp/tier-ab-band-freshness-cron-guard.json",
                "tmp/post-close-final-quote-ledger.json",
                "tmp/wf78-tier-weighted-freshness-resolution.json",
                "tmp/canonical-finance-data-plane.json",
                "tmp/canonical-finance-data-plane.sqlite",
                "tmp/canonical-finance-data-plane-phase6-10.json",
                "tmp/full-answer-parity/full-answer-parity-rollup.json",
                "tmp/wf78-capital-review-queue.json",
                "tmp/finance-decision-sync-spine.json",
            ],
            [
                "python scripts\\trade_grade_decision_os_contract.py --write --validate",
                "python scripts\\trade_grade_decision_cards.py --write --validate",
                "python scripts\\trade_grade_full_answer_assembler.py --all-wf84 --write --validate",
                "python scripts\\wf78_missing_band_context_repair.py --write --validate",
                "python scripts\\test_wf78_missing_band_context_repair_policy.py",
                "python scripts\\tier_ab_band_freshness_cron_guard.py --write --validate",
                "python scripts\\test_tier_ab_band_freshness_cron_guard.py",
                "python scripts\\ticker_answer_packet.py --all-from-coverage --validate",
                "python scripts\\trade_grade_repair_conveyor.py --write --validate",
                "python scripts\\trade_grade_os_readiness_rollup.py --write --validate",
                "python scripts\\test_trade_grade_os_readiness_rollup.py",
                "python scripts\\wf85_deployment_timing_gate.py --write --validate",
                "python scripts\\test_wf85_deployment_timing_gate.py",
                "python scripts\\autonomous_routing_deployment_cards.py --write --validate",
                "python scripts\\test_autonomous_routing_deployment_cards.py",
                "python scripts\\finance_market_deployment_operating_loop.py --refresh-readiness --write --write-md --validate",
                "python scripts\\test_finance_market_deployment_operating_loop.py",
                "python scripts\\trade_grade_os_freshness_cron_runner.py --write --write-md --validate",
                "python scripts\\wf85_retirement_gate_adjudication.py --write --validate",
                "python scripts\\wf85_production_blocker_repair.py --write --validate",
                "python scripts\\canonical_finance_data_plane.py --write --write-db --validate",
                "python scripts\\full_intelligence_answer_parity.py --all --write --pretty",
                "python scripts\\canonical_finance_data_plane_phase6_10.py --write --validate",
                "python scripts\\ticker_answer_packet_retirement_plan.py --write --validate",
                "python scripts\\workflow_routing_index.py --write --write-db --validate",
                "python scripts\\workflow_router.py WF85 --answer all --write-capsules --validate",
                "python scripts\\pm_control_packet.py --write --write-db --validate",
            ],
            [],
            [
                "Internal/personal decision support only; no customer/account/PII/"
                "suitability data, no canon/portfolio/cash/sizing/risk-rule "
                "mutation, no capital approval, no paper/live/account action, "
                "no generated card/score/SQL row as owner approval, no owner "
                "approval inference.",
            ],
            "internal review-only decision/approval-card interface; no capital or execution authority",
            True,
            True,
            "python scripts\\trade_grade_decision_cards.py --write --validate",
        ),
        route(
            "WF86",
            "Main-Session Paper Autotrader OS",
            "P0",
            "Opened by Randall on 2026-06-11 as a paper-only, main-session-owned "
            "autotrader orchestration lane. It is shadow-first and currently "
            "grants no autonomous order authority. WF86 consumes WF85 decision "
            "state, written bands/stops, fresh quotes, market/sector context, "
            "paper positions, and WF67 guard state.",
            "Use the daily WF86 shadow/reconciliation cron runner to accumulate "
            "clean shadow decisions and GET-only paper-order reconciliation proof. "
            "The scoped autonomous paper pilot is approved in principle, but "
            "autonomous execution stays blocked until the 20-decision/5-session "
            "threshold and reconciliation maturity gates are clean.",
            f"{CONTINUITY}/Workflow 86 - Main-Session Paper Autotrader OS.md",
            "tmp/paper-autotrader/policy.json",
            [
                "tmp/trade-grade-decision-cards.json",
                "tmp/finance-decision-factory.json",
                "tmp/wf78-capital-review-queue.json",
                "tmp/paper-autotrader/shadow-eligibility.json",
                "tmp/paper-autotrader/assisted-order-cards.json",
                "tmp/paper-autotrader/shadow-decisions.json",
                "tmp/paper-autotrader/autotrader-readiness.json",
                "tmp/paper-autotrader/guard-readiness.json",
                "tmp/paper-autotrader/wf86-daily-shadow-reconciliation-cron-runner.json",
                "tmp/alpaca-paper-readiness/wf67-autonomous-paper-manager-current.json",
                "tmp/alpaca-paper-readiness/paper-execution-guard-validation.json",
                "tmp/alpaca-paper-readiness/paper-order-reconciliation.vrt-wf86-assisted-approved.json",
                "tmp/alpaca-paper-readiness/paper-order-history-classifier.json",
                "tmp/paper-autotrader/trade-decision-journal.jsonl",
                "tmp/wf87-position-sizing-runtime-check.json",
                "tmp/wf87-portfolio-circuit-breakers.json",
                "tmp/wf87-approval-freshness-ttl.json",
                "tmp/wf87-intraday-monitor.json",
                "tmp/wf87-assisted-paper-cadence.json",
                "tmp/wf87-shadow-outcome-scorecard.json",
                "tmp/wf87-market-hours-gate-probe.json",
                "tmp/wf87-v2-readiness-rollup.json",
                "tmp/wf87-autonomy-command-center.json",
                "scripts/alpaca_paper_order_history_classifier.py",
                "scripts/test_alpaca_paper_order_history_classifier.py",
                "scripts/wf86_daily_shadow_reconciliation_cron_runner.py",
                "scripts/test_wf86_daily_shadow_reconciliation_cron_runner.py",
                "scripts/wf86_assisted_order_card_builder.py",
                "scripts/test_wf86_assisted_order_card_builder.py",
                "scripts/wf86_shadow_eligibility_validator.py",
                "scripts/test_wf86_shadow_eligibility_validator.py",
                "scripts/wf87_market_hours_gate_probe.py",
                "scripts/test_wf87_market_hours_gate_probe.py",
                "scripts/wf87_autonomy_command_center.py",
                "scripts/test_wf87_autonomy_command_center.py",
                "scripts/test_wf86_shadow_decision_ledger.py",
            ],
            [
                "python scripts\\workflow_router.py WF86 --answer all --write-capsules --validate",
                "python scripts\\wf86_shadow_eligibility_validator.py --write --validate",
                "python scripts\\wf86_assisted_order_card_builder.py --write --validate",
                "python scripts\\wf86_shadow_decision_ledger.py --write --validate",
                "python scripts\\test_wf86_assisted_order_card_builder.py",
                "python scripts\\test_wf86_shadow_eligibility_validator.py",
                "python scripts\\test_wf86_shadow_decision_ledger.py",
                "python scripts\\wf86_autotrader_readiness_packet.py --write --validate",
                "python scripts\\alpaca_paper_order_history_classifier.py --write --validate",
                "python scripts\\wf86_daily_shadow_reconciliation_cron_runner.py --write --write-md --validate",
                "python scripts\\wf87_assisted_paper_cadence.py --write --validate",
                "python scripts\\wf87_shadow_outcome_scorecard.py --write --validate",
                "python scripts\\wf87_market_hours_gate_probe.py --write --validate",
                "python scripts\\wf87_v2_readiness_rollup.py --write --validate",
                "python scripts\\wf87_autonomy_command_center.py --write --write-md --validate",
                "python scripts\\test_wf87_market_hours_gate_probe.py",
                "python scripts\\test_wf87_autonomy_command_center.py",
                "python scripts\\test_alpaca_paper_order_history_classifier.py",
                "python scripts\\test_wf86_daily_shadow_reconciliation_cron_runner.py",
                "python scripts\\concurrent_lane_manager.py --status --write --validate",
            ],
            [
                "WF86 shadow threshold is not met yet",
                "Post-trade reconciliation is not yet mature enough for autonomy",
                "Fresh short-lived kill switch, audit, WF67 guard, and reconciliation proof must be clean at execution time",
            ],
            [
                "Paper-only design. No live endpoint/credentials, live order, account "
                "action, money movement, portfolio/canon/cash/risk-rule mutation, "
                "cron-direct execution, Telegram approve-to-execute, owner approval "
                "inference, or autonomous paper submit/cancel/sell until a separate "
                "scoped pilot gate clears.",
            ],
            "paper-only future autonomy design; current state grants no autonomous paper/live execution authority",
            True,
            True,
            None,
        ),
        route(
            "WF87",
            "Veritas OS V2 Trade-Grade Autonomous OS Upgrade",
            "P0",
            "Official V2 workflow opened from Randall's 2026-06-11 plan. "
            "V2 is not a rebuild: it hardens the WF84 -> WF85 -> WF86 "
            "spine guarded by WF67, unifies decision/readiness state, adds "
            "review-only coding/performance tracking, and prepares gated "
            "script/canon optimization.",
            "Phase A hardening components are implemented: append-only "
            "trade-decision journal, position sizing runtime check, "
            "portfolio circuit breakers, approval/freshness TTL, intraday "
            "monitor, assisted-paper cadence proof, shadow outcome scorecard "
            "with non-score cause classification, autonomous routing/deployment "
            "card queue, "
            "market-hours fresh-gate probe, "
            "autonomy command center, "
            "finance decision performance digest, coding outcome ledger, and "
            "unified readiness rollup. Runtime remains blocked "
            "until stale/expired gates, shadow threshold, and reconciliation "
            "maturity clear. "
            "Phase C requires shadow threshold plus clean Phase B round trips; "
            "Phase E/live remains out of scope.",
            f"{CONTINUITY}/Veritas OS V2 - Trade-Grade Autonomous OS Upgrade Plan.md",
            "tmp/paper-autotrader/trade-decision-journal.jsonl",
            [
                "tmp/paper-autotrader/shadow-decisions.json",
                "tmp/paper-autotrader/autotrader-readiness.json",
                "tmp/paper-autotrader/guard-readiness.json",
                "tmp/paper-autotrader/assisted-order-cards.json",
                "tmp/trade-grade-os-readiness-rollup.json",
                "tmp/alpaca-paper-readiness/paper-execution-guard-validation.json",
                "tmp/alpaca-paper-readiness/paper-order-reconciliation.vrt-wf86-assisted-approved.json",
                "tmp/alpaca-paper-readiness/paper-order-history-classifier.json",
                "tmp/wf87-v2-readiness-rollup.json",
                "tmp/wf87-position-sizing-runtime-check.json",
                "tmp/wf87-portfolio-circuit-breakers.json",
                "tmp/wf87-approval-freshness-ttl.json",
                "tmp/wf87-intraday-monitor.json",
                "tmp/wf87-assisted-paper-cadence.json",
                "tmp/wf87-shadow-outcome-scorecard.json",
                "tmp/wf87-market-hours-gate-probe.json",
                "tmp/wf87-autonomy-command-center.json",
                "tmp/autonomous-routing-deployment-cards.json",
                "tmp/autonomous-card-authority-audit.json",
                "tmp/wf85-deployment-timing-gate.json",
                "tmp/morning-paper-deployment-recommendation-cards.json",
                "tmp/finance-decision-performance-digest.json",
                "tmp/coding-outcome-ledger-current.json",
                "data/state-history/coding-outcome-ledger.jsonl",
                "scripts/wf87_trade_decision_journal.py",
                "scripts/test_wf87_trade_decision_journal.py",
                "scripts/wf87_position_sizing_runtime_check.py",
                "scripts/test_wf87_position_sizing_runtime_check.py",
                "scripts/wf87_portfolio_circuit_breakers.py",
                "scripts/test_wf87_portfolio_circuit_breakers.py",
                "scripts/wf87_approval_freshness_ttl.py",
                "scripts/test_wf87_approval_freshness_ttl.py",
                "scripts/wf87_intraday_monitor.py",
                "scripts/test_wf87_intraday_monitor.py",
                "scripts/wf87_assisted_paper_cadence.py",
                "scripts/test_wf87_assisted_paper_cadence.py",
                "scripts/wf87_shadow_outcome_scorecard.py",
                "scripts/test_wf87_shadow_outcome_scorecard.py",
                "scripts/wf87_market_hours_gate_probe.py",
                "scripts/test_wf87_market_hours_gate_probe.py",
                "scripts/wf87_autonomy_command_center.py",
                "scripts/test_wf87_autonomy_command_center.py",
                "scripts/autonomous_routing_deployment_cards.py",
                "scripts/test_autonomous_routing_deployment_cards.py",
                "scripts/autonomous_card_authority_audit.py",
                "scripts/test_autonomous_card_authority_audit.py",
                "scripts/finance_decision_performance_digest.py",
                "scripts/test_finance_decision_performance_digest.py",
                "scripts/coding_outcome_ledger.py",
                "scripts/test_coding_outcome_ledger.py",
                "scripts/wf87_v2_readiness_rollup.py",
                "scripts/test_wf87_v2_readiness_rollup.py",
            ],
            [
                "python scripts\\workflow_router.py WF87 --answer all --write-capsules --validate",
                "python scripts\\workflow_routing_index.py --write --write-db --validate",
                "python scripts\\test_wf87_trade_decision_journal.py",
                "python scripts\\test_wf87_position_sizing_runtime_check.py",
                "python scripts\\test_wf87_portfolio_circuit_breakers.py",
                "python scripts\\test_wf87_approval_freshness_ttl.py",
                "python scripts\\test_wf87_intraday_monitor.py",
                "python scripts\\test_wf87_v2_readiness_rollup.py",
                "python scripts\\wf87_trade_decision_journal.py --write --validate",
                "python scripts\\wf87_position_sizing_runtime_check.py --write --validate",
                "python scripts\\wf87_portfolio_circuit_breakers.py --write --validate",
                "python scripts\\wf87_approval_freshness_ttl.py --write --validate",
                "python scripts\\wf87_intraday_monitor.py --write --validate",
                "python scripts\\wf87_assisted_paper_cadence.py --write --validate",
                "python scripts\\wf87_shadow_outcome_scorecard.py --write --validate",
                "python scripts\\wf87_market_hours_gate_probe.py --write --validate",
                "python scripts\\autonomous_routing_deployment_cards.py --write --validate",
                "python scripts\\autonomous_card_authority_audit.py --write --validate",
                "python scripts\\wf87_autonomy_command_center.py --write --write-md --validate",
                "python scripts\\finance_decision_performance_digest.py --write --write-md --validate",
                "python scripts\\coding_outcome_ledger.py --write --validate",
                "python scripts\\test_finance_decision_performance_digest.py",
                "python scripts\\test_coding_outcome_ledger.py",
                "python scripts\\test_wf87_market_hours_gate_probe.py",
                "python scripts\\test_wf87_autonomy_command_center.py",
                "python scripts\\test_autonomous_routing_deployment_cards.py",
                "python scripts\\test_autonomous_card_authority_audit.py",
                "python scripts\\wf87_v2_readiness_rollup.py --write --validate",
                "python scripts\\changed_file_validator_router.py --write --validate",
            ],
            [
                "Shadow proof threshold is not met yet",
                "Post-trade reconciliation maturity is not yet sufficient for autonomy",
                "Current live TTL/circuit/intraday proofs are fail-closed because approvals, quote/band/stop freshness, guard, kill switch, anomaly halt, or same-session stop proof are not clean",
            ],
            [
                "Planning/validator/readiness integration only. No live endpoint/"
                "credentials, live order, account action, money movement, portfolio/"
                "canon/cash/risk-rule mutation, cron-direct execution, owner "
                "approval inference, paper-to-live promotion, or autonomous paper "
                "submit/cancel/sell until separate scoped gates clear.",
            ],
            "official V2 upgrade workflow; planning, validators, journal, and readiness integration only until separate execution gates clear",
            True,
            True,
            "python scripts\\workflow_router.py WF87 --answer all",
            primary_pending=True,
            effective_status_override="phase_a_implemented_runtime_blocked",
        ),
        route(
            "WF67",
            "Alpaca Paper Execution Guardrail",
            "P1",
            "Paper-only guardrail active; paper sandbox separate from real "
            "planning portfolio; manager packet consolidates readiness.",
            "Refresh gate, run manager with request refresh, present "
            "ready/blocked/repair status; execute only after fresh kill switch, "
            "guards, redacted audit, notification, and Randall exact approval.",
            f"{CONTINUITY}/Workflow 67 - Alpaca Paper Execution Guardrail.md",
            "scripts/wf67_autonomous_paper_manager.py",
            ["tmp/wf67-paper-position-state.sqlite"],
            ["python scripts\\chief_intelligence_promotion_gate.py --write --validate"],
            ["Execution requires fresh kill switch + guards + redacted audit + notification + exact approval"],
            [
                "No live endpoint/credentials, money movement/account settings, "
                "close/liquidation endpoints, inferred approval, autonomous paper orders, "
                "refresh-triggered submit/cancel/sell, or paper-to-live promotion.",
            ],
            "paper-only simulation; exact owner approval required to execute",
            True,
            False,
            None,
        ),
        route(
            "WF64-WF56",
            "Portfolio/Canon Maintenance",
            "P1",
            "Proposal/semantic preview/gated apply architecture active; scoped "
            "routine entry-band maintenance is system-owned inside its gate, "
            "while broader applies remain exact-gated.",
            "Keep validators clean; use scoped band maintenance for eligible "
            "entry-band/stop refresh and exact standing/scoped approval artifacts "
            "for broader categories.",
            f"{CONTINUITY}/Workflow 64 - Bounded Portfolio Agent Cron Architecture.md",
            None,
            [f"{CONTINUITY}/Workflow 56 - Portfolio Mutation Proposal Object and Gated Apply Helper.md"],
            ["python scripts\\test_portfolio_mutation_validators.py"],
            ["Broader applies remain exact-gated"],
            [
                "No trade/account/brokerage/money movement; no cron direct apply "
                "outside approved scoped band/reference paths; no cash/risk-rule/"
                "execution-entitlement mutation unless separately scoped; no "
                "clean-validation-equals-approval.",
            ],
            "scoped entry-band maintenance allowed; broader proposal/preview/gated-apply only",
            True,
            False,
            None,
        ),
        route(
            "WF71",
            "Department Staff / Skill Ownership",
            "P1",
            "Elevated P1 autonomy helper factory: skill-routing/load-budget "
            "procedure active; PM handoffs embed helper contracts.",
            "Use the autonomy spine promotion contract plus helper contract, "
            "spawn packets, active manifest, and completion handshake around "
            "helper work.",
            f"{CONTINUITY}/Workflow 71 - Veritas OS Department Staff and Skill Ownership Model.md",
            "tmp/autonomy-spine-promotion-contract.json",
            ["tmp/autonomy-spine-readiness-rollup.json", "tmp/concurrent-lane-register.json"],
            [
                "python scripts\\autonomy_spine_promotion_contract.py --write --validate",
                "python scripts\\autonomy_spine_readiness_rollup.py --write --validate",
                "openclaw skills check",
            ],
            [],
            [
                "No separate autonomous identity, duplicate canon source, authority collision, "
                "heartbeat helper spawning, or trading/account/portfolio authority.",
            ],
            "orchestration-only; no autonomous identity/authority",
            False,
            True,
            None,
        ),
        route(
            "WF74",
            "Recursive Self-Improvement",
            "P1",
            "P0-adjacent learning spine: V1 monitor-and-use complete; "
            "validation harness and boundary lint exist; consumes WF55/WF87 "
            "measurement telemetry for proposal-only improvements.",
            "Use WF55 outcome measurement and validation telemetry only for "
            "safe improvement candidates; do not expand authority.",
            f"{CONTINUITY}/Workflow 74 - Veritas Recursive Self-Improvement Loop.md",
            "tmp/autonomy-spine-readiness-rollup.json",
            ["tmp/wf55-autonomy-outcome-ledger.json", "tmp/wf74-improvement-opportunity-queue.json"],
            [
                "python scripts\\wf55_autonomy_outcome_ledger.py --write --validate",
                "python scripts\\autonomy_spine_readiness_rollup.py --write --validate",
                "python scripts\\wf74_rsi.py --validate-only",
            ],
            [],
            [
                "No base-model self-modification, self-preservation/replication, autonomous "
                "authority expansion, second memory tree, owner-approval inference, "
                "portfolio/trade/account/paper/live authority, or RSI theater.",
            ],
            "review-only; no self-modification/authority expansion",
            False,
            True,
            None,
        ),
        route(
            "WF76",
            "Cron Authority / Canon Auto-Update",
            "P1",
            "P0-adjacent cadence spine; scheduled/review-only cron awareness "
            "flows through freshness spine -> scorecard -> escalation. "
            "Autonomy-spine measurement and readiness contracts are now "
            "tracked by cron freshness.",
            "Verify selectivity with cron_freshness_spine.py, "
            "workflow_advancement_scorecard.py, cron_signal_scorecard.py, and "
            "escalation_trigger.py; archive moves only after owner approval/proof.",
            f"{CONTINUITY}/Workflow 76 - Cron Automation Authority and Canon Auto-Update Expansion.md",
            "scripts/cron_freshness_spine.py",
            [
                "tmp/cron-freshness-spine.json",
                "tmp/autonomy-spine-readiness-rollup.json",
                "tmp/wf55-autonomy-outcome-ledger.json",
            ],
            [
                "python scripts\\wf55_autonomy_outcome_ledger.py --write --validate",
                "python scripts\\autonomy_spine_readiness_rollup.py --write --validate",
                "python scripts\\cron_freshness_spine.py --write --validate",
            ],
            [],
            [
                "No cron-direct portfolio/canon apply; no deletes; no "
                "config/auth/channel/service/runtime mutation, owner approval inference, or "
                "heartbeat inline execution.",
            ],
            "scheduled review-only; cron may propose, main applies bounded sync",
            True,
            True,
            "python scripts\\cron_freshness_spine.py --write --validate",
        ),
        route(
            "WF69",
            "Intelligence / Probability Stack V2",
            "P1",
            "Control-plane/data-contract revamp active; probability claims "
            "blocked.",
            "Use SQL truth spine as proof/index substrate only; validate "
            "bundles without predictive claims.",
            f"{CONTINUITY}/Workflow 69 - Intelligence Probability Predictive Stack V2 Revamp.md",
            None,
            [],
            ["python scripts\\wf_v2_intelligence_stack_validator.py --write"],
            ["Probability/win-rate claims blocked while WF55 not ready"],
            [
                "No probability/win-rate/expected-return/model-readiness claims while WF55 is "
                "not ready; no live/paper/account authority.",
            ],
            "review-only; no predictive claims",
            True,
            True,
            None,
        ),
        route(
            "WF80",
            "Multi-Product Scaleout Control Plane",
            "P3",
            "Product-portfolio operating layer is intentionally on hold as the "
            "ultimate goal while near-term effort focuses on efficiency, routing, "
            "evidence quality, and command-center leverage.",
            "Do not advance product registry/build work unless Randall resumes "
            "WF80-WF83. Near-term priority routes through WF84/WF85 finance "
            "decision unification, WF78 evidence repair, WF73/WF72 support-route "
            "efficiency, and WF79 command visibility.",
            f"{CONTINUITY}/Workflow 80 - Multi-Product Scaleout Control Plane.md",
            f"{CONTINUITY}/Workflow 80 - Multi-Product Scaleout Control Plane.md",
            [
                f"{CONTINUITY}/Workflow 81 - AI and Technology Opportunity Intelligence Product Line.md",
                f"{CONTINUITY}/Workflow 82 - Learning and Teaching Product Line.md",
                f"{CONTINUITY}/Workflow 83 - Product Packaging and Launch Readiness Factory.md",
            ],
            ["python scripts\\workflow_routing_index.py --write --validate"],
            [
                "Owner paused WF80-WF83 on 2026-06-06",
                "Product registry/validator not built yet",
                "Customer/public launch remains blocked",
            ],
            [
                "Report-only product scaleout; no customer/public output, spend, external action, "
                "account/customer-data import, legal/compliance claim, finance execution authority, "
                "or owner-approval inference.",
            ],
            "review-only product portfolio control plane",
            False,
            True,
            "python scripts\\workflow_routing_index.py --route WF80",
        ),
        route(
            "WF81",
            "AI and Technology Opportunity Intelligence Product Line",
            "P3",
            "Product/opportunity intelligence lane is intentionally on hold under "
            "the WF80-WF83 pause.",
            "Do not build opportunity-intake artifacts unless Randall resumes "
            "WF80-WF83. Use general research only for direct questions.",
            f"{CONTINUITY}/Workflow 81 - AI and Technology Opportunity Intelligence Product Line.md",
            f"{CONTINUITY}/Workflow 81 - AI and Technology Opportunity Intelligence Product Line.md",
            [f"{CONTINUITY}/Workflow 80 - Multi-Product Scaleout Control Plane.md"],
            ["python scripts\\workflow_routing_index.py --write --validate"],
            ["Owner paused WF80-WF83 on 2026-06-06", "Opportunity schema and candidate queue not built yet"],
            [
                "No external action, spend, account creation, outreach, customer claim, "
                "compliance/security claim, or public launch without separate approval.",
            ],
            "review-only opportunity/product intelligence",
            False,
            True,
            "python scripts\\workflow_routing_index.py --route WF81",
        ),
        route(
            "WF82",
            "Learning and Teaching Product Line",
            "P3",
            "Learning/teaching product lane is intentionally on hold under the "
            "WF80-WF83 pause.",
            "Do not build learning-product inventory unless Randall resumes "
            "WF80-WF83. Keep internal training assets available for current "
            "workflow efficiency only.",
            f"{CONTINUITY}/Workflow 82 - Learning and Teaching Product Line.md",
            f"{CONTINUITY}/Workflow 82 - Learning and Teaching Product Line.md",
            ["scripts/wf75_training_desk.py", f"{CONTINUITY}/Workflow 83 - Product Packaging and Launch Readiness Factory.md"],
            ["python scripts\\workflow_routing_index.py --write --validate"],
            [
                "Owner paused WF80-WF83 on 2026-06-06",
                "Learning-asset inventory and readiness validator not built yet",
            ],
            [
                "No customer/public training product, certification, legal/compliance claim, "
                "guaranteed outcome claim, or external publication without separate approval.",
            ],
            "internal-first learning product lane",
            False,
            True,
            "python scripts\\workflow_routing_index.py --route WF82",
        ),
        route(
            "WF83",
            "Product Packaging and Launch Readiness Factory",
            "P3",
            "Packaging/readiness factory is intentionally on hold under the "
            "WF80-WF83 pause.",
            "Do not build launch/readiness matrix unless Randall resumes "
            "WF80-WF83. Near-term readiness work should support internal "
            "efficiency/proof, not launch packaging.",
            f"{CONTINUITY}/Workflow 83 - Product Packaging and Launch Readiness Factory.md",
            f"{CONTINUITY}/Workflow 83 - Product Packaging and Launch Readiness Factory.md",
            [
                f"{CONTINUITY}/Workflow 80 - Multi-Product Scaleout Control Plane.md",
                "scripts/retail_automation_control_plane.py",
                "scripts/generic_intelligence_saas_pivot.py",
            ],
            ["python scripts\\workflow_routing_index.py --write --validate"],
            [
                "Owner paused WF80-WF83 on 2026-06-06",
                "Readiness matrix/no-go validator not built yet",
                "Customer/public launch remains blocked",
            ],
            [
                "No public launch, customer delivery, outbound action, spend, credential/account use, "
                "customer-data import, legal/compliance/security certification claim, finance advice/"
                "customer allocation, or owner approval inference.",
            ],
            "review-only packaging/readiness gate",
            False,
            True,
            "python scripts\\workflow_routing_index.py --route WF83",
        ),
        # ---- P2 monitors ----
        route(
            "WF58",
            "Dashboard / Capital Packets Monitor",
            "P2",
            "Monitor: dashboard/capital packet validation + deployment-state "
            "contract proof.",
            "Escalate on validator warning/critical, false-green dashboard, "
            "packet-vs-canon conflict, or duplicated legacy deployment-state "
            "fields reappearing in presentation artifacts.",
            f"{CONTINUITY}/Deployment State Contract Migration.md",
            "scripts/deployment_contract_migration_validation_bundle.py",
            ["tmp/deployment-contract-agreement-validation.json"],
            ["python scripts\\deployment_contract_migration_validation_bundle.py --write"],
            [],
            [
                "No self-apply, trade/account authority, per-packet approval inference, or "
                "legacy/source-field deletion outside compatibility proof.",
            ],
            "monitor-only",
            False,
            True,
            None,
        ),
        route(
            "WF63",
            "Paper Readiness Monitor",
            "P2",
            "Monitor: paper readiness / no-submit guard.",
            "Escalate on readiness/no-submit guard warning/critical or live "
            "endpoint/credential exposure.",
            f"{CONTINUITY}/Workflow 63 - Alpaca Paper Trading Readiness.md",
            None,
            [],
            [],
            [],
            [
                "No live endpoint/credentials, money movement/account changes, or "
                "submit/cancel outside WF67.",
            ],
            "monitor-only",
            False,
            True,
            None,
        ),
        route(
            "WF60-WF61",
            "Research / Regime Monitor",
            "P2",
            "Monitor: macro judgment, research freshness, sector expansion.",
            "Escalate on freshness degradation, macro cue conflicting with "
            "canon, or feed implying action.",
            f"{CONTINUITY}/Workflow 60 - Research Freshness and Opportunity Cron Automation.md",
            None,
            [f"{CONTINUITY}/Workflow 61 - Small Mid Cap Regime Feed and Candidate Sleeve.md"],
            [],
            [],
            ["Review-only; no promotion/sizing/sleeve/cash/risk-rule/trade authority."],
            "monitor-only",
            False,
            True,
            None,
        ),
        route(
            "WF65",
            "Fundamentals Monitor",
            "P2",
            "Monitor: fundamental/IR/earnings bridge artifacts.",
            "Escalate on validator warning/critical, official source conflict, "
            "or stale probe.",
            f"{CONTINUITY}/Workflow 65 - Fundamental Metrics Tracker V1.md",
            None,
            [],
            [],
            [],
            ["Evidence only; no deployment/trade/portfolio authority."],
            "monitor-only",
            False,
            True,
            None,
        ),
        route(
            "WF62",
            "Canon Consolidation Monitor",
            "P2",
            "Monitor: canonical ownership validation.",
            "Escalate when a consumer points to retired canon or a dashboard "
            "outranks an owner note.",
            f"{CONTINUITY}/Workflow 62 - Finance Canon Consolidation and Consumer Migration.md",
            None,
            [],
            [],
            [],
            ["No ungated canon mutation or delete/archive without approval."],
            "monitor-only",
            False,
            True,
            None,
        ),
        route(
            "WF55",
            "Outcome Measurement / Probability Readiness",
            "P1",
            "Promoted to active autonomy measurement substrate; probability "
            "claims remain blocked while neutral outcome events feed WF87 and "
            "WF74.",
            "Build and validate neutral outcome events from WF86/WF87 shadow "
            "artifacts; escalate if predictive language appears before gates clear.",
            f"{CONTINUITY}/Workflow 55 - Probability Readiness and Outcome Retention Gate.md",
            "tmp/wf55-autonomy-outcome-ledger.json",
            ["tmp/autonomy-spine-promotion-contract.json", "tmp/autonomy-spine-readiness-rollup.json"],
            [
                "python scripts\\wf55_autonomy_outcome_ledger.py --write --validate",
                "python scripts\\test_wf55_autonomy_outcome_ledger.py",
                "python scripts\\autonomy_spine_readiness_rollup.py --write --validate",
            ],
            ["Probability claims not ready; outcome ledger is measurement-only"],
            [
                "No predictive scores, expected-return claims, win-rate claims, model-ranked "
                "deployment, durable v2 append, paper/live execution, or approval inference.",
            ],
            "measurement-only; predictive claims gated",
            False,
            True,
            "python scripts\\wf55_autonomy_outcome_ledger.py --write --validate",
        ),
        route(
            "WF-CHIEF-GATE",
            "Chief / WF67 Manager Gate Monitor",
            "P2",
            "Monitor: Chief gate and WF67 manager/card artifacts.",
            "Escalate when a candidate/card lacks rank, band/stop proof, "
            "sector/monitor/paper context, WF55 caution, or manager readiness.",
            None,
            "scripts/chief_intelligence_promotion_gate.py",
            ["scripts/wf67_autonomous_paper_manager.py"],
            ["python scripts\\chief_intelligence_promotion_gate.py --write --validate"],
            [],
            [
                "Review/routing only; no watchlist apply, portfolio/canon mutation, paper/live "
                "execution, owner approval inference, probability/model authority, or money movement.",
            ],
            "monitor-only; review/routing",
            False,
            True,
            None,
        ),
        route(
            "WF-FINANCE-CHAINS",
            "Finance Chains Monitor",
            "P2",
            "Monitor: chain/run/current-window/digest artifacts + cron ledger.",
            "Escalate on missing/failed run, stale current-window index, "
            "validator warning/critical, or digest escalation.",
            None,
            "tmp/current-window-artifacts.json",
            ["tmp/cron-freshness-spine.json"],
            [],
            [],
            ["Review/proof only; no mutation/action/approval authority."],
            "monitor-only",
            False,
            True,
            None,
        ),
        route(
            "WF-BOARD-CANON-GUARDRAILS",
            "Board / Canon Guardrails Monitor",
            "P2",
            "Monitor: board/canon/stale/proposal artifacts.",
            "Escalate on critical contradiction, widened authority flag, or "
            "proposal implying self-apply.",
            None,
            None,
            [],
            [],
            [],
            [
                "Cron may propose; main applies only bounded freshness/status sync or exact "
                "gated maintenance.",
            ],
            "monitor-only; cron proposes, main applies bounded",
            False,
            True,
            None,
        ),
        route(
            "WF-SQL-INDEXES",
            "SQL / Current-Window Indexes Monitor",
            "P2",
            "Monitor: finance SQL, artifact index, JSON-SQL index, "
            "current-window, lifecycle manifest.",
            "Escalate on missing proof, authority flag violation, stale index, "
            "index treated as approval/action, or unlabeled lifecycle.",
            None,
            "scripts/artifact_index.py",
            ["tmp/veritas-artifact-index.sqlite"],
            ["python scripts\\artifact_index.py incremental", "python scripts\\artifact_index.py validate"],
            [],
            [
                "SQL candidate is universe/scope only; other indexes are proof/staging. No "
                "approval/execution/archive/delete authority.",
            ],
            "monitor-only; SQL is proof/staging",
            False,
            True,
            None,
        ),
        route(
            "WF-WORKSPACE-GOVERNOR",
            "Workspace Governor / Archive Monitor",
            "P2",
            "Monitor: archive suggestions + lifecycle manifest.",
            "Escalate when a cleanup suggestion is treated as approval or a "
            "surface is moved/deleted without reference check.",
            None,
            None,
            [],
            [],
            [],
            ["Suggestions only; no destructive cleanup without explicit approval."],
            "monitor-only; suggestions are not approval",
            True,
            True,
            None,
        ),
    ]


def relpath(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def exists_on_disk(rel: str) -> bool:
    return (ROOT / rel).exists()


# Route freshness thresholds (hours). A route's freshness is the age of its
# freshest declared proof signal (primary artifact preferred, else continuity
# note). This surfaces stale or missing proof without a broad workspace scan.
FRESH_HOURS = 72.0
AGING_HOURS = 336.0  # 14 days


def _age_hours(rel: str | None) -> float | None:
    if not rel:
        return None
    p = ROOT / rel
    if not p.exists():
        return None
    mtime = datetime.fromtimestamp(p.stat().st_mtime, tz=timezone.utc)
    return round((datetime.now(timezone.utc) - mtime).total_seconds() / 3600.0, 1)


def score_route_freshness(r: dict[str, Any]) -> dict[str, Any]:
    cont = r.get("continuity_note")
    primary = r.get("primary_route_artifact")
    primary_declared = bool(primary) and not r.get("primary_pending")

    cont_exists = bool(cont) and exists_on_disk(cont)
    primary_exists = primary_declared and exists_on_disk(primary)

    cont_age = _age_hours(cont) if cont_exists else None
    primary_age = _age_hours(primary) if primary_exists else None

    missing = (bool(cont) and not cont_exists) or (primary_declared and not primary_exists)

    if missing:
        score = "missing"
    else:
        basis = primary_age if primary_age is not None else cont_age
        if basis is None:
            score = "n/a"
        elif basis < FRESH_HOURS:
            score = "fresh"
        elif basis < AGING_HOURS:
            score = "aging"
        else:
            score = "stale"

    return {
        "score": score,
        "continuity_note_age_hours": cont_age,
        "primary_artifact_age_hours": primary_age,
        "validator_count": len(r.get("validator_commands") or []),
        "has_next_action": bool(r.get("next_action")),
    }


def build_handoff(rt: dict[str, Any]) -> dict[str, Any]:
    """Derive a bounded helper-lane handoff packet from a single route row,
    shaped to `06. Playbooks/Subagent Spawn Handoff Template.md`."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    safe = bool(rt.get("safe_for_helper_lane"))

    read_first: list[str] = []
    if rt.get("continuity_note"):
        read_first.append(rt["continuity_note"])
    if rt.get("primary_route_artifact") and not rt.get("primary_pending"):
        read_first.append(rt["primary_route_artifact"])
    read_first.extend(rt.get("secondary_artifacts") or [])

    validators = list(rt.get("validator_commands") or [])
    acceptance = validators + ["python scripts\\workflow_routing_index.py --validate"]

    packet: dict[str, Any] = {
        "schema_version": "workflow_routing_handoff.v1",
        "generated_at_utc": now,
        "source_authority": "06. Playbooks/Active Workflows.md",
        "spawn_template": "06. Playbooks/Subagent Spawn Handoff Template.md",
        "workflow_id": rt.get("workflow_id"),
        "display_name": rt.get("display_name"),
        "tier": rt.get("tier"),
        "mode": "Spawn read-only" if safe else "Main-session only",
        "safe_for_helper_lane": safe,
        "owner_action_required": bool(rt.get("owner_action_required")),
        "objective": rt.get("next_action"),
        "current_truth": rt.get("current_state"),
        "read_first": read_first[:6],
        "do_not_read_first": [
            "broad workflow folders", "all skills", "full tmp/ scans",
            "parent transcript/forked chat context", "unrelated continuity history",
        ],
        "do_not_touch": [
            "canonical portfolio/canon notes",
            "config/auth/credentials/runtime surfaces",
            "paper/live/brokerage/account actions",
            "destructive move/delete/archive",
        ],
        "validators": validators,
        "stop_lines": rt.get("stop_lines") or [],
        "blockers": rt.get("blockers") or [],
        "authority_boundary": rt.get("authority_boundary"),
        "acceptance_proof": acceptance,
        "freshness": rt.get("freshness"),
        "authority": dict(AUTHORITY),
        "note": (
            "Derived review-only helper packet. Active Workflows and the exact "
            "continuity note remain authority; this packet grants no canon/"
            "portfolio/SQL/approval/execution authority and never implies owner "
            "approval."
        ),
    }
    if not safe:
        packet["helper_lane_warning"] = (
            "Route is owner-gated / main-session only (safe_for_helper_lane=false). "
            "Do not auto-spawn; route requires Randall's decision or main-session "
            "execution per the route stop lines."
        )
    return packet


def build_index() -> dict[str, Any]:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    registry = load_registry()
    routes = [apply_route_override(route, registry) for route in build_routes()]
    for r in routes:
        r["last_validated_at"] = now
        r["freshness"] = score_route_freshness(r)
    tier_counts: dict[str, int] = {}
    freshness_counts: dict[str, int] = {}
    for r in routes:
        tier_counts[r["tier"]] = tier_counts.get(r["tier"], 0) + 1
        fs = r["freshness"]["score"]
        freshness_counts[fs] = freshness_counts.get(fs, 0) + 1
    return {
        "schema_version": "workflow_routing_index.v1",
        "generated_at_utc": now,
        "source_authority": "06. Playbooks/Active Workflows.md",
        "note": (
            "Derived review-only route map. Active Workflows and exact continuity "
            "notes remain authority; this index never outranks them and carries no "
            "canon/portfolio/SQL/approval/execution authority."
        ),
        "authority": dict(AUTHORITY),
        "summary": {
            "route_count": len(routes),
            "tier_counts": tier_counts,
            "freshness_counts": freshness_counts,
        },
        "routes": routes,
    }


def validate_index(index: dict[str, Any]) -> dict[str, Any]:
    findings: list[dict[str, Any]] = []
    routes = index.get("routes", [])
    summary = index.get("summary", {})

    if index.get("schema_version") != "workflow_routing_index.v1":
        findings.append({
            "severity": "critical",
            "scope": "index",
            "check": "schema_version",
            "issue": "index schema_version must be workflow_routing_index.v1",
            "value": index.get("schema_version"),
        })

    if not isinstance(routes, list):
        findings.append({
            "severity": "critical",
            "scope": "index",
            "check": "routes",
            "issue": "index.routes must be a list",
            "value_type": type(routes).__name__,
        })
        routes = []

    if summary.get("route_count") != len(routes):
        findings.append({
            "severity": "critical",
            "scope": "index",
            "check": "route_count",
            "issue": "summary.route_count must equal actual route length",
            "summary_value": summary.get("route_count"),
            "actual_value": len(routes),
        })

    if len(routes) != EXPECTED_ROUTE_COUNT:
        findings.append({
            "severity": "critical",
            "scope": "index",
            "check": "route_coverage",
            "issue": "route count drifted from the expected P0/P1/P2/P3 coverage set",
            "expected": EXPECTED_ROUTE_COUNT,
            "actual": len(routes),
        })

    actual_tier_counts: dict[str, int] = {}
    for r in routes:
        tier = r.get("tier")
        actual_tier_counts[tier] = actual_tier_counts.get(tier, 0) + 1
    if actual_tier_counts != EXPECTED_TIER_COUNTS:
        findings.append({
            "severity": "critical",
            "scope": "index",
            "check": "tier_coverage",
            "issue": "tier counts drifted from expected P0/P1/P2/P3 coverage",
            "expected": EXPECTED_TIER_COUNTS,
            "actual": actual_tier_counts,
        })
    if summary.get("tier_counts") != actual_tier_counts:
        findings.append({
            "severity": "critical",
            "scope": "index",
            "check": "tier_counts",
            "issue": "summary.tier_counts must equal actual route tiers",
            "summary_value": summary.get("tier_counts"),
            "actual_value": actual_tier_counts,
        })

    # Index-level authority clamp.
    authority = index.get("authority", {})
    for flag, expected in AUTHORITY.items():
        if authority.get(flag) != expected:
            findings.append({
                "severity": "critical",
                "scope": "index",
                "check": "authority",
                "issue": f"index authority.{flag} must be {expected}",
                "value": authority.get(flag),
            })

    seen_ids: set[str] = set()
    for r in routes:
        wid = r.get("workflow_id", "<unknown>")

        # Required fields present.
        for field in REQUIRED_FIELDS:
            if field not in r:
                findings.append({
                    "severity": "critical", "workflow_id": wid, "check": "required_field",
                    "issue": f"missing required route field: {field}",
                })

        for field in LIST_FIELDS:
            if field in r and not isinstance(r.get(field), list):
                findings.append({
                    "severity": "critical",
                    "workflow_id": wid,
                    "check": "field_type",
                    "issue": f"{field} must be a list",
                    "value_type": type(r.get(field)).__name__,
                })
            for idx, value in enumerate(r.get(field) or []):
                if not isinstance(value, str) or not value.strip():
                    findings.append({
                        "severity": "critical",
                        "workflow_id": wid,
                        "check": "field_type",
                        "issue": f"{field}[{idx}] must be a non-empty string",
                        "value": value,
                    })

        for field in BOOL_FIELDS:
            if field in r and not isinstance(r.get(field), bool):
                findings.append({
                    "severity": "critical",
                    "workflow_id": wid,
                    "check": "field_type",
                    "issue": f"{field} must be boolean",
                    "value": r.get(field),
                })

        if not isinstance(r.get("workflow_id"), str) or not r.get("workflow_id", "").strip():
            findings.append({
                "severity": "critical", "workflow_id": wid, "check": "workflow_id",
                "issue": "workflow_id must be a non-empty string",
            })
        if r.get("tier") not in EXPECTED_TIER_COUNTS:
            findings.append({
                "severity": "critical", "workflow_id": wid, "check": "tier",
                "issue": "tier must be one of P0/P1/P2/P3",
                "value": r.get("tier"),
            })
        for field in ("display_name", "current_state", "next_action", "authority_boundary"):
            if not isinstance(r.get(field), str) or not r.get(field, "").strip():
                findings.append({
                    "severity": "critical",
                    "workflow_id": wid,
                    "check": "field_value",
                    "issue": f"{field} must be a non-empty string",
                })

        # Unique workflow id.
        if wid in seen_ids:
            findings.append({
                "severity": "critical", "workflow_id": wid, "check": "unique_id",
                "issue": "duplicate workflow_id in routing index",
            })
        seen_ids.add(wid)

        # Stop lines mandatory.
        stop_lines = r.get("stop_lines")
        if not isinstance(stop_lines, list) or not stop_lines:
            findings.append({
                "severity": "critical", "workflow_id": wid, "check": "stop_lines",
                "issue": "route must carry at least one stop line",
            })

        # Authority boundary string mandatory.
        if not r.get("authority_boundary"):
            findings.append({
                "severity": "critical", "workflow_id": wid, "check": "authority_boundary",
                "issue": "route must declare an authority_boundary",
            })

        # Continuity note: null is allowed (explicit "no dedicated note"); a
        # declared path that is absent on disk is a coverage warning.
        cont = r.get("continuity_note")
        if cont is not None and not exists_on_disk(cont):
            findings.append({
                "severity": "warning", "workflow_id": wid, "check": "continuity_note",
                "issue": "declared continuity_note not found on disk",
                "path": cont,
            })

        # Primary route artifact: null allowed (e.g. pure-monitor with no single
        # proof file); declared, non-pending, absent path is a coverage warning.
        primary = r.get("primary_route_artifact")
        if primary is not None and not r.get("primary_pending") and not exists_on_disk(primary):
            findings.append({
                "severity": "warning", "workflow_id": wid, "check": "primary_route_artifact",
                "issue": "declared primary_route_artifact not found on disk",
                "path": primary,
            })

        # Secondary artifacts: declared paths that look like workspace paths and
        # are absent are coverage warnings (skip bare command-ish entries).
        for sec in r.get("secondary_artifacts", []) or []:
            if ("/" in sec or "\\" in sec) and not exists_on_disk(sec):
                findings.append({
                    "severity": "warning", "workflow_id": wid, "check": "secondary_artifact",
                    "issue": "declared secondary_artifact not found on disk",
                    "path": sec,
                })

        # Active build lanes (P0/P1) should carry at least one validator command.
        if r.get("tier") in ("P0", "P1") and not (r.get("validator_commands") or []):
            findings.append({
                "severity": "warning", "workflow_id": wid, "check": "validator_commands",
                "issue": "active build lane has no validator_commands",
            })

        freshness = r.get("freshness")
        if not isinstance(freshness, dict):
            findings.append({
                "severity": "critical", "workflow_id": wid, "check": "freshness",
                "issue": "route must carry a freshness object",
            })
        else:
            if freshness.get("score") not in FRESHNESS_SCORES:
                findings.append({
                    "severity": "critical",
                    "workflow_id": wid,
                    "check": "freshness",
                    "issue": "freshness.score is outside the allowed enum",
                    "value": freshness.get("score"),
                })
            if freshness.get("validator_count") != len(r.get("validator_commands") or []):
                findings.append({
                    "severity": "critical",
                    "workflow_id": wid,
                    "check": "freshness",
                    "issue": "freshness.validator_count must equal validator_commands length",
                    "freshness_value": freshness.get("validator_count"),
                    "actual_value": len(r.get("validator_commands") or []),
                })
            if freshness.get("has_next_action") is not bool(r.get("next_action")):
                findings.append({
                    "severity": "critical",
                    "workflow_id": wid,
                    "check": "freshness",
                    "issue": "freshness.has_next_action must match next_action presence",
                })

        packet = build_handoff(r)
        expected_mode = "Spawn read-only" if r.get("safe_for_helper_lane") else "Main-session only"
        if packet.get("mode") != expected_mode or packet.get("mode") not in HANDOFF_MODES:
            findings.append({
                "severity": "critical",
                "workflow_id": wid,
                "check": "handoff_mode",
                "issue": "handoff mode must match safe_for_helper_lane",
                "expected": expected_mode,
                "actual": packet.get("mode"),
            })
        if not r.get("safe_for_helper_lane") and not packet.get("helper_lane_warning"):
            findings.append({
                "severity": "critical",
                "workflow_id": wid,
                "check": "handoff_mode",
                "issue": "main-session-only handoff must carry helper_lane_warning",
            })
        if packet.get("authority") != AUTHORITY:
            findings.append({
                "severity": "critical",
                "workflow_id": wid,
                "check": "handoff_authority",
                "issue": "handoff authority clamp must match index authority clamp",
            })

    critical = sum(1 for f in findings if f.get("severity") == "critical")
    warning = sum(1 for f in findings if f.get("severity") == "warning")
    return {
        "generated_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "input": relpath(INDEX_OUT),
        "status": "ok" if critical == 0 else "blocked",
        "authority": dict(AUTHORITY),
        "summary": {
            "routes_checked": len(routes),
            "critical": critical,
            "warning": warning,
            "checks": [
                "schema_version", "routes", "route_count", "route_coverage",
                "tier_coverage", "tier_counts", "authority", "required_field",
                "field_type", "field_value", "unique_id", "stop_lines",
                "authority_boundary", "continuity_note",
                "primary_route_artifact", "secondary_artifact",
                "validator_commands", "freshness", "handoff_mode",
                "handoff_authority",
            ],
        },
        "findings": findings,
    }


def _db_path(path: str | None) -> Path:
    return ROOT / path if path else DB_OUT


def write_sqlite_index(index: dict[str, Any], db_path: Path) -> dict[str, Any]:
    """Write a derived/rebuildable SQLite lookup from the JSON route objects."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as con:
        con.execute("PRAGMA foreign_keys = ON")
        con.executescript(
            """
            DROP TABLE IF EXISTS workflow_authority;
            DROP TABLE IF EXISTS workflow_freshness;
            DROP TABLE IF EXISTS workflow_stop_lines;
            DROP TABLE IF EXISTS workflow_blockers;
            DROP TABLE IF EXISTS workflow_validators;
            DROP TABLE IF EXISTS workflow_artifacts;
            DROP TABLE IF EXISTS workflow_routes;
            DROP TABLE IF EXISTS workflow_runs;

            CREATE TABLE workflow_runs (
                run_id TEXT PRIMARY KEY,
                generated_at_utc TEXT NOT NULL,
                schema_version TEXT NOT NULL,
                source_authority TEXT NOT NULL,
                route_count INTEGER NOT NULL,
                authority_json TEXT NOT NULL
            );

            CREATE TABLE workflow_routes (
                workflow_id TEXT PRIMARY KEY,
                display_name TEXT NOT NULL,
                tier TEXT NOT NULL,
                current_state TEXT NOT NULL,
                next_action TEXT NOT NULL,
                continuity_note TEXT,
                primary_route_artifact TEXT,
                primary_pending INTEGER NOT NULL,
                last_validated_at TEXT,
                authority_boundary TEXT NOT NULL,
                owner_action_required INTEGER NOT NULL,
                safe_for_helper_lane INTEGER NOT NULL,
                default_resume_command TEXT,
                freshness_score TEXT,
                freshness_primary_artifact_age_hours REAL,
                freshness_continuity_note_age_hours REAL,
                validator_count INTEGER NOT NULL
            );

            CREATE TABLE workflow_artifacts (
                workflow_id TEXT NOT NULL,
                artifact_role TEXT NOT NULL,
                artifact_path TEXT NOT NULL,
                ordinal INTEGER NOT NULL,
                exists_on_disk INTEGER NOT NULL,
                FOREIGN KEY(workflow_id) REFERENCES workflow_routes(workflow_id)
            );

            CREATE TABLE workflow_validators (
                workflow_id TEXT NOT NULL,
                validator_command TEXT NOT NULL,
                ordinal INTEGER NOT NULL,
                FOREIGN KEY(workflow_id) REFERENCES workflow_routes(workflow_id)
            );

            CREATE TABLE workflow_blockers (
                workflow_id TEXT NOT NULL,
                blocker TEXT NOT NULL,
                ordinal INTEGER NOT NULL,
                FOREIGN KEY(workflow_id) REFERENCES workflow_routes(workflow_id)
            );

            CREATE TABLE workflow_stop_lines (
                workflow_id TEXT NOT NULL,
                stop_line TEXT NOT NULL,
                ordinal INTEGER NOT NULL,
                FOREIGN KEY(workflow_id) REFERENCES workflow_routes(workflow_id)
            );

            CREATE TABLE workflow_freshness (
                workflow_id TEXT PRIMARY KEY,
                score TEXT NOT NULL,
                continuity_note_age_hours REAL,
                primary_artifact_age_hours REAL,
                validator_count INTEGER NOT NULL,
                has_next_action INTEGER NOT NULL,
                FOREIGN KEY(workflow_id) REFERENCES workflow_routes(workflow_id)
            );

            CREATE TABLE workflow_authority (
                workflow_id TEXT NOT NULL,
                flag TEXT NOT NULL,
                value INTEGER NOT NULL,
                PRIMARY KEY(workflow_id, flag),
                FOREIGN KEY(workflow_id) REFERENCES workflow_routes(workflow_id)
            );

            CREATE INDEX idx_workflow_routes_tier ON workflow_routes(tier);
            CREATE INDEX idx_workflow_routes_freshness ON workflow_routes(freshness_score);
            CREATE INDEX idx_workflow_routes_helper ON workflow_routes(safe_for_helper_lane);
            CREATE INDEX idx_workflow_routes_owner ON workflow_routes(owner_action_required);
            """
        )

        run_id = f"workflow-routing-index-{index.get('generated_at_utc')}"
        con.execute(
            """
            INSERT INTO workflow_runs
            (run_id, generated_at_utc, schema_version, source_authority, route_count, authority_json)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                index.get("generated_at_utc"),
                index.get("schema_version"),
                index.get("source_authority"),
                index.get("summary", {}).get("route_count", 0),
                json.dumps(index.get("authority", {}), sort_keys=True),
            ),
        )

        for r in index.get("routes", []):
            f = r.get("freshness") or {}
            con.execute(
                """
                INSERT INTO workflow_routes
                (workflow_id, display_name, tier, current_state, next_action,
                 continuity_note, primary_route_artifact, primary_pending,
                 last_validated_at, authority_boundary, owner_action_required,
                 safe_for_helper_lane, default_resume_command, freshness_score,
                 freshness_primary_artifact_age_hours,
                 freshness_continuity_note_age_hours, validator_count)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    r["workflow_id"],
                    r["display_name"],
                    r["tier"],
                    r["current_state"],
                    r["next_action"],
                    r.get("continuity_note"),
                    r.get("primary_route_artifact"),
                    1 if r.get("primary_pending") else 0,
                    r.get("last_validated_at"),
                    r["authority_boundary"],
                    1 if r.get("owner_action_required") else 0,
                    1 if r.get("safe_for_helper_lane") else 0,
                    r.get("default_resume_command"),
                    f.get("score"),
                    f.get("primary_artifact_age_hours"),
                    f.get("continuity_note_age_hours"),
                    len(r.get("validator_commands") or []),
                ),
            )

            artifacts: list[tuple[str, str | None]] = [
                ("continuity_note", r.get("continuity_note")),
                ("primary_route_artifact", r.get("primary_route_artifact")),
            ]
            artifacts.extend(("secondary_artifact", p) for p in r.get("secondary_artifacts", []))
            for ordinal, (role, artifact) in enumerate(artifacts):
                if not artifact:
                    continue
                con.execute(
                    """
                    INSERT INTO workflow_artifacts
                    (workflow_id, artifact_role, artifact_path, ordinal, exists_on_disk)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (r["workflow_id"], role, artifact, ordinal, 1 if exists_on_disk(artifact) else 0),
                )

            for ordinal, command in enumerate(r.get("validator_commands") or []):
                con.execute(
                    "INSERT INTO workflow_validators VALUES (?, ?, ?)",
                    (r["workflow_id"], command, ordinal),
                )
            for ordinal, blocker in enumerate(r.get("blockers") or []):
                con.execute(
                    "INSERT INTO workflow_blockers VALUES (?, ?, ?)",
                    (r["workflow_id"], blocker, ordinal),
                )
            for ordinal, stop_line in enumerate(r.get("stop_lines") or []):
                con.execute(
                    "INSERT INTO workflow_stop_lines VALUES (?, ?, ?)",
                    (r["workflow_id"], stop_line, ordinal),
                )
            con.execute(
                """
                INSERT INTO workflow_freshness
                (workflow_id, score, continuity_note_age_hours,
                 primary_artifact_age_hours, validator_count, has_next_action)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    r["workflow_id"],
                    f.get("score"),
                    f.get("continuity_note_age_hours"),
                    f.get("primary_artifact_age_hours"),
                    f.get("validator_count", 0),
                    1 if f.get("has_next_action") else 0,
                ),
            )
            for flag, expected in AUTHORITY.items():
                con.execute(
                    "INSERT INTO workflow_authority VALUES (?, ?, ?)",
                    (r["workflow_id"], flag, 1 if expected else 0),
                )
        con.commit()

        integrity = con.execute("PRAGMA integrity_check").fetchone()[0]
        fk_errors = len(con.execute("PRAGMA foreign_key_check").fetchall())
        route_count = con.execute("SELECT COUNT(*) FROM workflow_routes").fetchone()[0]

    return {
        "db_path": relpath(db_path),
        "status": "ok" if integrity == "ok" and fk_errors == 0 else "blocked",
        "integrity_check": integrity,
        "foreign_key_errors": fk_errors,
        "route_count": route_count,
        "authority_boundary": "Derived/rebuildable workflow route lookup only; JSON and Active Workflows remain authority.",
    }


def validate_sqlite_index(index: dict[str, Any], db_path: Path) -> dict[str, Any]:
    findings: list[dict[str, Any]] = []
    if not db_path.exists():
        return {
            "status": "blocked",
            "db_path": relpath(db_path),
            "summary": {"critical": 1, "warning": 0},
            "findings": [{
                "severity": "critical",
                "check": "db_exists",
                "issue": "requested SQLite route index does not exist",
            }],
        }

    with sqlite3.connect(db_path) as con:
        con.row_factory = sqlite3.Row
        integrity = con.execute("PRAGMA integrity_check").fetchone()[0]
        if integrity != "ok":
            findings.append({
                "severity": "critical",
                "check": "integrity_check",
                "issue": "SQLite integrity_check failed",
                "value": integrity,
            })
        fk_errors = con.execute("PRAGMA foreign_key_check").fetchall()
        if fk_errors:
            findings.append({
                "severity": "critical",
                "check": "foreign_key_check",
                "issue": "SQLite foreign_key_check returned rows",
                "count": len(fk_errors),
            })

        route_count = con.execute("SELECT COUNT(*) FROM workflow_routes").fetchone()[0]
        expected_count = index.get("summary", {}).get("route_count")
        if route_count != expected_count:
            findings.append({
                "severity": "critical",
                "check": "route_count",
                "issue": "SQLite route count must match JSON route count",
                "expected": expected_count,
                "actual": route_count,
            })

        tier_counts = {
            row["tier"]: row["count"]
            for row in con.execute("SELECT tier, COUNT(*) AS count FROM workflow_routes GROUP BY tier")
        }
        if tier_counts != index.get("summary", {}).get("tier_counts"):
            findings.append({
                "severity": "critical",
                "check": "tier_counts",
                "issue": "SQLite tier counts must match JSON tier counts",
                "expected": index.get("summary", {}).get("tier_counts"),
                "actual": tier_counts,
            })

        freshness_counts = {
            row["freshness_score"]: row["count"]
            for row in con.execute(
                "SELECT freshness_score, COUNT(*) AS count FROM workflow_routes GROUP BY freshness_score"
            )
        }
        if freshness_counts != index.get("summary", {}).get("freshness_counts"):
            findings.append({
                "severity": "critical",
                "check": "freshness_counts",
                "issue": "SQLite freshness counts must match JSON freshness counts",
                "expected": index.get("summary", {}).get("freshness_counts"),
                "actual": freshness_counts,
            })

        authority_rows = con.execute(
            "SELECT workflow_id, flag, value FROM workflow_authority"
        ).fetchall()
        expected_authority_rows = expected_count * len(AUTHORITY)
        if len(authority_rows) != expected_authority_rows:
            findings.append({
                "severity": "critical",
                "check": "authority_row_count",
                "issue": "Every route must carry every authority flag",
                "expected": expected_authority_rows,
                "actual": len(authority_rows),
            })
        for row in authority_rows:
            expected = 1 if AUTHORITY.get(row["flag"]) else 0
            if row["value"] != expected:
                findings.append({
                    "severity": "critical",
                    "workflow_id": row["workflow_id"],
                    "check": "authority_clamp",
                    "issue": f"authority flag {row['flag']} drifted",
                    "expected": expected,
                    "actual": row["value"],
                })

    critical = sum(1 for f in findings if f["severity"] == "critical")
    warning = sum(1 for f in findings if f["severity"] == "warning")
    return {
        "status": "ok" if critical == 0 else "blocked",
        "db_path": relpath(db_path),
        "summary": {
            "critical": critical,
            "warning": warning,
            "route_count": route_count if "route_count" in locals() else None,
            "tier_counts": tier_counts if "tier_counts" in locals() else None,
            "freshness_counts": freshness_counts if "freshness_counts" in locals() else None,
        },
        "findings": findings,
    }


def _sql_route_dict(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "workflow_id": row["workflow_id"],
        "display_name": row["display_name"],
        "tier": row["tier"],
        "current_state": row["current_state"],
        "next_action": row["next_action"],
        "freshness_score": row["freshness_score"],
        "owner_action_required": bool(row["owner_action_required"]),
        "safe_for_helper_lane": bool(row["safe_for_helper_lane"]),
        "authority_boundary": row["authority_boundary"],
        "default_resume_command": row["default_resume_command"],
    }


def sql_route_lookup(db_path: Path, query: str) -> dict[str, Any] | None:
    q = query.strip().lower()
    q_compact = q.replace("wf", "").replace("-", "").replace(" ", "")
    with sqlite3.connect(db_path) as con:
        con.row_factory = sqlite3.Row
        rows = con.execute("SELECT * FROM workflow_routes").fetchall()
    for row in rows:
        wid = str(row["workflow_id"]).lower()
        name = str(row["display_name"]).lower()
        if q == wid or q == name:
            return _sql_route_dict(row)
        if q_compact and q_compact == wid.replace("wf", "").replace("-", ""):
            return _sql_route_dict(row)
        if q in name:
            return _sql_route_dict(row)
    return None


def sql_query(db_path: Path, mode: str) -> list[dict[str, Any]]:
    query_map = {
        "list": "SELECT * FROM workflow_routes ORDER BY tier, workflow_id",
        "freshness": "SELECT * FROM workflow_routes ORDER BY freshness_score, tier, workflow_id",
        "next_actions": "SELECT * FROM workflow_routes WHERE next_action <> '' ORDER BY tier, workflow_id",
        "helper_safe": "SELECT * FROM workflow_routes WHERE safe_for_helper_lane = 1 ORDER BY tier, workflow_id",
        "owner_gated": "SELECT * FROM workflow_routes WHERE owner_action_required = 1 ORDER BY tier, workflow_id",
    }
    with sqlite3.connect(db_path) as con:
        con.row_factory = sqlite3.Row
        return [_sql_route_dict(row) for row in con.execute(query_map[mode]).fetchall()]


def find_route(index: dict[str, Any], query: str) -> dict[str, Any] | None:
    """Resolve a route by workflow_id or display_name (case-insensitive,
    accepts the bare number or a WF## form)."""
    q = query.strip().lower()
    q_compact = q.replace("wf", "").replace("-", "").replace(" ", "")
    for r in index.get("routes", []):
        wid = str(r.get("workflow_id", "")).lower()
        name = str(r.get("display_name", "")).lower()
        if q == wid or q == name:
            return r
        if q_compact and q_compact == wid.replace("wf", "").replace("-", ""):
            return r
        if q in name:
            return r
    return None


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build the derived workflow routing index (review-only)."
    )
    parser.add_argument("--write", action="store_true", help="Write the routing index JSON.")
    parser.add_argument("--validate", action="store_true", help="Write the validation JSON.")
    parser.add_argument("--route", metavar="WORKFLOW", help="Print one route object (by workflow_id or display name) and exit.")
    parser.add_argument("--list", action="store_true", help="Print a compact id/tier/state/next-action listing and exit.")
    parser.add_argument("--handoff", metavar="WORKFLOW", help="Build a bounded helper-lane handoff packet for one route (use with --write to save).")
    parser.add_argument("--freshness", action="store_true", help="Print a compact per-route freshness listing and exit.")
    parser.add_argument("--write-db", action="store_true", help="Write derived SQLite route lookup DB.")
    parser.add_argument("--db", help=f"SQLite DB path for --write-db/--sql-* (default {relpath(DB_OUT)}).")
    parser.add_argument("--sql-route", metavar="WORKFLOW", help="Read one route from the derived SQLite lookup DB.")
    parser.add_argument("--sql-list", action="store_true", help="List routes from the derived SQLite lookup DB.")
    parser.add_argument("--sql-freshness", action="store_true", help="List freshness from the derived SQLite lookup DB.")
    parser.add_argument("--sql-next-actions", action="store_true", help="List next actions from the derived SQLite lookup DB.")
    parser.add_argument("--sql-helper-safe", action="store_true", help="List helper-safe routes from the derived SQLite lookup DB.")
    parser.add_argument("--sql-owner-gated", action="store_true", help="List owner-gated routes from the derived SQLite lookup DB.")
    args = parser.parse_args()

    index = build_index()
    db_path = _db_path(args.db)

    if args.sql_route:
        if not db_path.exists():
            print(json.dumps({"error": "db_not_found", "db_path": relpath(db_path)}, indent=2))
            return 1
        match = sql_route_lookup(db_path, args.sql_route)
        if match is None:
            print(json.dumps({"error": "route_not_found", "query": args.sql_route}, indent=2))
            return 1
        print(json.dumps(match, indent=2))
        return 0

    sql_modes = [
        (args.sql_list, "list"),
        (args.sql_freshness, "freshness"),
        (args.sql_next_actions, "next_actions"),
        (args.sql_helper_safe, "helper_safe"),
        (args.sql_owner_gated, "owner_gated"),
    ]
    selected_sql_modes = [mode for selected, mode in sql_modes if selected]
    if selected_sql_modes:
        if len(selected_sql_modes) > 1:
            print(json.dumps({"error": "choose_one_sql_query_mode"}, indent=2))
            return 1
        if not db_path.exists():
            print(json.dumps({"error": "db_not_found", "db_path": relpath(db_path)}, indent=2))
            return 1
        print(json.dumps({
            "db_path": relpath(db_path),
            "mode": selected_sql_modes[0],
            "authority": dict(AUTHORITY),
            "rows": sql_query(db_path, selected_sql_modes[0]),
        }, indent=2))
        return 0

    if args.route:
        match = find_route(index, args.route)
        if match is None:
            print(json.dumps({"error": "route_not_found", "query": args.route}, indent=2))
            return 1
        print(json.dumps(match, indent=2))
        return 0

    if args.list:
        for r in index["routes"]:
            print(f"{r['tier']:<3} {r['workflow_id']:<26} {r['display_name']}")
            print(f"      next: {r['next_action']}")
        return 0

    if args.freshness:
        fc = index["summary"]["freshness_counts"]
        print("freshness_counts: " + json.dumps(fc))
        for r in index["routes"]:
            f = r["freshness"]
            print(
                f"{f['score']:<8} {r['tier']:<3} {r['workflow_id']:<26} "
                f"primary={f['primary_artifact_age_hours']}h "
                f"note={f['continuity_note_age_hours']}h "
                f"validators={f['validator_count']}"
            )
        return 0

    if args.handoff:
        match = find_route(index, args.handoff)
        if match is None:
            print(json.dumps({"error": "route_not_found", "query": args.handoff}, indent=2))
            return 1
        packet = build_handoff(match)
        if args.write:
            safe_id = "".join(c if (c.isalnum() or c in "-_") else "-" for c in str(match["workflow_id"])).lower()
            out = HANDOFF_DIR / f"workflow-routing-handoff-{safe_id}.json"
            out.write_text(json.dumps(packet, indent=2) + "\n", encoding="utf-8")
            print(f"wrote {relpath(out)} ({packet['mode']})")
        else:
            print(json.dumps(packet, indent=2))
        return 0

    if args.write:
        INDEX_OUT.write_text(json.dumps(index, indent=2) + "\n", encoding="utf-8")
        print(f"wrote {relpath(INDEX_OUT)} ({index['summary']['route_count']} routes)")

    db_report: dict[str, Any] | None = None
    if args.write_db:
        db_report = write_sqlite_index(index, db_path)
        print(
            f"wrote {db_report['db_path']}: {db_report['status']} "
            f"({db_report['route_count']} routes, integrity={db_report['integrity_check']}, "
            f"fk_errors={db_report['foreign_key_errors']})"
        )

    rc = 0
    if args.validate:
        report = validate_index(index)
        if args.write_db:
            report["sqlite"] = validate_sqlite_index(index, db_path)
            if report["sqlite"]["status"] != "ok":
                report["status"] = "blocked"
                report["summary"]["critical"] += report["sqlite"]["summary"]["critical"]
                report["summary"]["warning"] += report["sqlite"]["summary"]["warning"]
        VALIDATION_OUT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        s = report["summary"]
        print(
            f"wrote {relpath(VALIDATION_OUT)}: {report['status']} "
            f"({s['routes_checked']} routes, {s['critical']} critical, {s['warning']} warning)"
        )
        rc = 1 if s["critical"] else 0

    if not args.write and not args.validate and not args.write_db:
        print(f"workflow_routing_index: {index['summary']['route_count']} routes (dry run; pass --write/--validate)")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
