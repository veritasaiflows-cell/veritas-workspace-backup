#!/usr/bin/env python3
"""Review active workflows for safe automation/autonomy expansion.

This is a report-only governance artifact. It does not create cron jobs, run
workflow phases, mutate canon/portfolio state, or widen heartbeat authority.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
DEFAULT_OUT = TMP / "workflow-automation-autonomy-review.json"
SCHEMA_VERSION = "workflow_automation_autonomy_review.v1"


WORKFLOW_REVIEWS: list[dict[str, Any]] = [
    {
        "workflow": "WF75 Retail Investor Finance Intelligence SaaS",
        "tier": "P0",
        "current_phase": "anonymous_scenario_customer_safe_internal_service_led_readiness_sprint_with_phase_c_d_state_movement_sqlite_handoff_proof",
        "recommended_next_phase": "continue the 6-10 week 55-65% internal/service-led SaaS readiness buildout from WF77 supplemental price evidence, renderer/export regression, scenario templates, SQLite WAL control plane, and artifact-only PM handoff",
        "heartbeat_posture": "flag_only",
        "cron_posture": "anonymous_scenario_validation_readiness_plan_and_infrastructure_proof_only",
        "helper_lane_posture": "bounded anonymous-scenario, validator, service-state, SQLite control-plane, renderer, queue, handoff, and regression prep",
        "main_session_posture": "final_integrator_and_infrastructure_sprint_owner",
        "safe_unattended_actions": [
            "refresh anonymous-scenario customer-safe export validation",
            "refresh rendered-output leak/claim validation",
            "refresh WF75 internal/service-led readiness plan",
            "refresh WF75 service-state/operator queue/movement proof",
            "refresh WF75 SQLite WAL control-plane proof",
            "refresh WF75 artifact-only PM handoff",
            "refresh anonymous-scenario renderer/regression proof after harness exists",
        ],
        "human_decision_required_for": [
            "real customer identity, portfolio, suitability, risk, account, brokerage, tax, retirement, or credential data",
            "external delivery or public launch",
            "account/brokerage connection",
            "personalized regulated advice",
        ],
        "stop_lines": [
            "real customer data stays typed as future-gated/quarantine-only until explicit gates exist",
            "no public launch",
            "no external delivery",
            "no personalized regulated advice or brokerage connection",
        ],
    },
    {
        "workflow": "WF72 SQL support-mode transition",
        "tier": "P1",
        "current_phase": "on_demand_support_substrate_with_a2_fallback_fixture_parity_ready_for_live_implementation",
        "recommended_next_phase": "complete WF72 A2 fallback fixture wiring before any 101-200 SQL expansion or SQL-first consumer promotion",
        "heartbeat_posture": "flag_only",
        "cron_posture": "no recurring SQL retail-grade/readiness churn; operator packets only",
        "helper_lane_posture": "bounded A2 implementation or QA lanes only when scoped to fixture wiring, parity proof, or live guard validation",
        "main_session_posture": "final integrator before any SQL/canon/import decision",
        "safe_unattended_actions": [
            "confirm recurring finance chains do not run SQL retail-grade blocked-state proof",
            "run SQL retail-grade gates only after scoped SQL/helper/ticker-card changes",
            "refresh A2 fixture parity and controlled-router proof",
            "refresh operator packets",
        ],
        "human_decision_required_for": [
            "SQL-canon expansion",
            "SQL-first consumer migration",
            "DB path promotion",
            "cleanup/archive/move/delete",
        ],
        "stop_lines": [
            "live Go consumer authority guard remains fail-closed until fallback fixture path and 13 source-drift rows are resolved",
            "no SQL-effective retail rows before live guard ok",
            "no ticker import",
            "no production answer-path overwrite",
            "no canon/portfolio mutation",
        ],
    },
    {
        "workflow": "WF78 500 Ticker Finance Intelligence Scaleout",
        "tier": "P1",
        "current_phase": "mechanism_proven_candidate_scope_frozen",
        "recommended_next_phase": "resume candidate/import work only on product demand or explicit owner review",
        "heartbeat_posture": "flag_only",
        "cron_posture": "no recurring broad ticker expansion proof; provider/runtime checks only when candidate packet is reopened",
        "helper_lane_posture": "candidate-scope research/design only when product demand exists",
        "main_session_posture": "owner decision packet and import gate owner",
        "safe_unattended_actions": [
            "preserve current pilot/candidate packet as proof",
            "refresh provider/runtime proof only for explicit candidate review",
            "refresh 42-card no-regression proof only before any proposed import",
        ],
        "human_decision_required_for": [
            "100/200/350/500 ticker import",
            "promotion of pilot rows",
            "retail/customer output from SQL",
        ],
        "stop_lines": [
            "no import from design proof alone",
            "no customer output",
            "no recommendation/deployment authority",
        ],
    },
    {
        "workflow": "WF68 Intraday Alert Engine and Advisor Surface",
        "tier": "P1",
        "current_phase": "scheduled_artifact_generation",
        "recommended_next_phase": "scheduled_artifact_generation",
        "heartbeat_posture": "flag_if_stale_or_authority_widens",
        "cron_posture": "already scheduled internal artifact generation",
        "helper_lane_posture": "validator hardening and handoff QA only",
        "main_session_posture": "review/escalation owner",
        "safe_unattended_actions": [
            "produce internal alert packets",
            "validate authority false flags",
            "refresh runtime handoff status",
        ],
        "human_decision_required_for": [
            "external channel delivery",
            "paper-order conversion",
            "config/channel/runtime changes",
        ],
        "stop_lines": [
            "no external delivery",
            "no paper/live/account action",
            "no canon/portfolio mutation",
            "no approval inference",
        ],
    },
    {
        "workflow": "WF67 Paper Trading Guardrail",
        "tier": "P1",
        "current_phase": "scheduled_review_surfaces",
        "recommended_next_phase": "scheduled_review_surfaces",
        "heartbeat_posture": "flag_only",
        "cron_posture": "position visibility and guard proof only",
        "helper_lane_posture": "approval-card prep and guard QA only",
        "main_session_posture": "exact order approval-card integrator",
        "safe_unattended_actions": [
            "refresh paper-position visibility",
            "prepare paper-only request cards",
            "validate no-submit/paper-live isolation guard artifacts",
        ],
        "human_decision_required_for": [
            "paper submit",
            "paper cancel/sell",
            "any live brokerage endpoint or account action",
        ],
        "stop_lines": [
            "no paper execution without exact approval",
            "no live endpoint or credential",
            "no money movement or account mutation",
        ],
    },
    {
        "workflow": "WF64/WF56 Bounded Portfolio/Canon Maintenance",
        "tier": "P1",
        "current_phase": "gated_apply_helpers",
        "recommended_next_phase": "gated_apply_helpers",
        "heartbeat_posture": "flag_only",
        "cron_posture": "proposal/verifier/preview generation only",
        "helper_lane_posture": "proposal QA and semantic preview only",
        "main_session_posture": "exact gated apply owner",
        "safe_unattended_actions": [
            "generate proposals",
            "generate semantic previews",
            "run validators and post-apply validation dry checks",
        ],
        "human_decision_required_for": [
            "exact apply packet",
            "cash/risk-rule/execution entitlement change",
            "trade/account/brokerage action",
        ],
        "stop_lines": [
            "no self-apply from proposal validation",
            "no cron direct apply beyond exact approved helpers",
            "no owner approval inference",
        ],
    },
    {
        "workflow": "WF70/WF66 Official Evidence Spine",
        "tier": "P1",
        "current_phase": "scheduled_review_surfaces",
        "recommended_next_phase": "scheduled_artifact_generation",
        "heartbeat_posture": "flag_if_source_conflict_or_stale",
        "cron_posture": "official-source capture/reconciliation proof only",
        "helper_lane_posture": "source capture QA and gap-map prep",
        "main_session_posture": "evidence interpretation and final judgment",
        "safe_unattended_actions": [
            "refresh official evidence inventory",
            "run bridge/reconciliation validators",
            "prepare source-gap maps",
        ],
        "human_decision_required_for": [
            "material thesis change",
            "portfolio/canon mutation",
            "capital deployment recommendation",
        ],
        "stop_lines": [
            "no invented values",
            "no source-present equals reconciled shortcut",
            "no portfolio/trade authority",
        ],
    },
    {
        "workflow": "WF77 Coverage and Question Router",
        "tier": "P1",
        "current_phase": "scheduled_review_surfaces",
        "recommended_next_phase": "scheduled_artifact_generation",
        "heartbeat_posture": "flag_if_coverage_or_router_artifact_missing",
        "cron_posture": "coverage/router QA refresh only",
        "helper_lane_posture": "source-open answer-contract QA only",
        "main_session_posture": "material finance answer finalizer",
        "safe_unattended_actions": [
            "refresh coverage registry",
            "refresh WF77 price freshness bridge",
            "validate answer contracts",
            "run source-open/no-authority QA",
        ],
        "human_decision_required_for": [
            "recommendation/action change",
            "paper/live order",
            "portfolio/canon mutation",
        ],
        "stop_lines": [
            "no owner approval inference",
            "no trade/account authority",
            "no source-closed material claims",
        ],
    },
    {
        "workflow": "WF73 Queue/Index/Boot Surface Optimization",
        "tier": "P1",
        "current_phase": "scheduled_review_surfaces",
        "recommended_next_phase": "scheduled_artifact_generation",
        "heartbeat_posture": "flag_if_boot_or_workflow_guard_warns",
        "cron_posture": "size/hygiene/index validation only",
        "helper_lane_posture": "patch proposal for route-only compression",
        "main_session_posture": "control-surface editor",
        "safe_unattended_actions": [
            "run boot_surface_size_guard",
            "run workflow_hygiene_check",
            "refresh operator-packet index",
        ],
        "human_decision_required_for": [
            "doctrine rewrite",
            "new durable control surface",
            "config/runtime mutation",
        ],
        "stop_lines": [
            "no authority boundary weakening",
            "no destructive cleanup",
            "no config/runtime mutation",
        ],
    },
    {
        "workflow": "WF71 Department Staff / Skill Ownership",
        "tier": "P1",
        "current_phase": "scheduled_review_surfaces",
        "recommended_next_phase": "scheduled_review_surfaces",
        "heartbeat_posture": "flag_if_helper_contract_missing",
        "cron_posture": "staff/load-budget audit only",
        "helper_lane_posture": "allowed only with explicit task contract",
        "main_session_posture": "orchestration owner",
        "safe_unattended_actions": [
            "audit helper-lane contracts",
            "validate load-budget procedure references",
        ],
        "human_decision_required_for": [
            "new autonomous role",
            "authority model change",
        ],
        "stop_lines": [
            "no separate autonomous identity",
            "no duplicate canon",
            "no independent trade/account authority",
        ],
    },
    {
        "workflow": "WF74 Recursive Self-Improvement",
        "tier": "P1",
        "current_phase": "scheduled_review_surfaces",
        "recommended_next_phase": "scheduled_review_surfaces",
        "heartbeat_posture": "flag_only_after_repeated_friction_or_validator_failure",
        "cron_posture": "validator/report only",
        "helper_lane_posture": "patch proposal only after concrete repeated issue",
        "main_session_posture": "promotion decision owner",
        "safe_unattended_actions": [
            "run boundary lint",
            "prepare improvement proposal from repeated failures",
        ],
        "human_decision_required_for": [
            "policy/doctrine promotion",
            "authority expansion",
        ],
        "stop_lines": [
            "no self-modification theater",
            "no authority expansion",
            "no portfolio/trade/account authority",
        ],
    },
    {
        "workflow": "WF76 Cron Authority / Canon Auto-Update Expansion",
        "tier": "P1",
        "current_phase": "scheduled_review_surfaces",
        "recommended_next_phase": "scheduled_artifact_generation",
        "heartbeat_posture": "flag_if_cron_run_state_action_needed",
        "cron_posture": "authority matrix and dry-run/archive suggestions only",
        "helper_lane_posture": "cron contract QA or proposal only",
        "main_session_posture": "scheduler/change owner",
        "safe_unattended_actions": [
            "run cron authority matrix validator",
            "produce archive suggestions",
            "inspect cron state for actionable failures",
        ],
        "human_decision_required_for": [
            "cron edit/create/delete",
            "archive move/delete",
            "config/auth/channel/runtime mutation",
        ],
        "stop_lines": [
            "no cron-direct broad apply",
            "no deletes",
            "no owner approval inference",
        ],
    },
    {
        "workflow": "WF69 Intelligence / Probability / Predictive Stack V2",
        "tier": "P1",
        "current_phase": "manual",
        "recommended_next_phase": "scheduled_review_surfaces",
        "heartbeat_posture": "flag_if_probability_language_appears",
        "cron_posture": "contract/provenance validation only",
        "helper_lane_posture": "methodology/provenance audit only",
        "main_session_posture": "claim boundary owner",
        "safe_unattended_actions": [
            "run intelligence-stack validator",
            "scan for probability/win-rate/expected-return claim leakage",
        ],
        "human_decision_required_for": [
            "predictive model readiness claims",
            "deployment ranking by model output",
        ],
        "stop_lines": [
            "no probability/win-rate claims",
            "no model-ranked deployment",
            "no live/paper/account authority",
        ],
    },
]


P2_MONITORS = [
    "WF58 dashboard/capital recommendation packets",
    "WF63 paper readiness",
    "WF60/WF61 research and regime feeds",
    "WF65 fundamentals",
    "WF62 canon consolidation",
    "WF55 probability readiness",
    "finance chains",
    "board/canon guardrails",
    "SQL cockpit/current-window index",
    "workspace governor/archive suggestions",
]

P3_PAUSED = [
    "WF37 daily summary commercial brief hardening",
    "market-moving news intake pilot",
    "WF44/WF45 dashboard/source freshness follow-ups",
    "workspace simplification/archive backlog",
]

P4_BLOCKED = [
    "WF49 FRED runtime persistence",
    "WF50/root backups/archive candidates",
    "channel/config/auth/service changes",
    "live brokerage/account actions",
]

OVERHEAD_FRICTION_FINDINGS: list[dict[str, Any]] = [
    {
        "workflow": "WF72 SQL support-mode transition",
        "friction_id": "wf72_sql_retail_grade_churn",
        "severity": "high",
        "friction_type": "repeated_known_blocked_gate",
        "evidence": [
            "SQL retail-grade readiness remains report-only and activation_allowed=false.",
            "Recurring chains should not rerun SQL retail-grade blocked-state proof unless SQL/helper/ticker-card consumers changed.",
        ],
        "fix_strategy": "Keep lightweight A2/read-guard health checks recurring; run heavy SQL retail-grade gates only after scoped SQL/helper/router changes or owner-reviewed SQL promotion work.",
        "parallel_lane": "WF72 A2 support-readiness QA lane",
        "owner_surface": "WF72 / SQL support-mode transition",
        "next_fix": "Confirm finance chains and operator packets preserve on-demand-only SQL retail-grade readiness posture.",
    },
    {
        "workflow": "WF78 500 Ticker Finance Intelligence Scaleout",
        "friction_id": "wf78_broad_expansion_proof_without_demand",
        "severity": "high",
        "friction_type": "repeated_breadth_proof",
        "evidence": [
            "Candidate/import work is mechanism-proven and frozen until product demand or explicit owner review.",
            "Recurring broad ticker expansion proof does not improve decision quality while production answer path remains constrained.",
        ],
        "fix_strategy": "Keep provider/runtime and no-regression checks on demand; route current effort to evidence debt, freshness, owner-card readiness, and decision-factory proof.",
        "parallel_lane": "WF78 event-rerouting QA or Tier 1 quote-readiness QA",
        "owner_surface": "WF78 / non-capital routing and evidence repair",
        "next_fix": "Keep import/scaleout checks out of recurring chains unless a candidate packet is reopened.",
    },
    {
        "workflow": "WF73 Queue/Index/Boot Surface Optimization",
        "friction_id": "wf73_control_surface_revalidation_overlap",
        "severity": "medium",
        "friction_type": "duplicated_control_plane_validation",
        "evidence": [
            "Workflow routing index, fast-path QA, truth-surface inventory, PM state, and closeout bundles can overlap if run independently.",
            "The closeout bundle is the preferred one-command integration proof after meaningful workflow automation changes.",
        ],
        "fix_strategy": "Use targeted validators during implementation and reserve control_closeout_bundle for integrated closeout; avoid running the full chain after every small proof refresh.",
        "parallel_lane": "WF73 route/closeout compression QA",
        "owner_surface": "WF73 / route and closeout control plane",
        "next_fix": "Add route-aware overhead review before broad scans and use the closeout bundle only at integration boundaries.",
    },
    {
        "workflow": "WF76 Cron Authority / Canon Auto-Update Expansion",
        "friction_id": "wf76_cron_signal_noise",
        "severity": "medium",
        "friction_type": "monitor_noise_or_old_blocker_repetition",
        "evidence": [
            "Cron freshness and signal scorecards can surface blocked signals that are known stop lines rather than new work.",
            "Cron posture should remain validator/report only unless an explicit scheduler decision is in scope.",
        ],
        "fix_strategy": "Classify recurring blocked signals as known, new, or escalated; only new/escalated signals should create implementation work.",
        "parallel_lane": "WF76 cron contract QA",
        "owner_surface": "WF76 / cron authority",
        "next_fix": "Plan a signal-classification lane after WF72/WF78 overhead gates are confirmed.",
    },
    {
        "workflow": "WF74 Recursive Self-Improvement",
        "friction_id": "wf74_meta_work_without_repeated_failure",
        "severity": "medium",
        "friction_type": "meta_process_overhead",
        "evidence": [
            "WF74 should run after repeated friction, validator failure, or a completed lesson worth capture.",
            "Using RSI for ordinary planning creates process overhead without improving workflow output.",
        ],
        "fix_strategy": "Keep WF74 flag-only until a concrete repeated failure appears; then produce a patch proposal or validator hardening item.",
        "parallel_lane": "WF74 boundary/lesson QA only after trigger",
        "owner_surface": "WF74 / recursive self-improvement",
        "next_fix": "Use the overhead review artifact as the trigger source instead of opening broad RSI sessions.",
    },
    {
        "workflow": "P2 monitor lanes",
        "friction_id": "p2_monitor_queue_advancement",
        "severity": "medium",
        "friction_type": "monitor_to_work_queue_drift",
        "evidence": [
            "P2 lanes are monitor/report surfaces by default.",
            "Turning every stale monitor into active work competes with P0/P1 decision-critical lanes.",
        ],
        "fix_strategy": "Require material drift, contradiction, authority widening, or missing proof before a P2 monitor becomes a helper lane.",
        "parallel_lane": "P2 material-drift classifier",
        "owner_surface": "Active Workflows / P2 monitor policy",
        "next_fix": "Keep P2 monitors in flag-only posture unless the overhead review marks them escalated.",
    },
]

QA_LANE_MODEL = "ollama-cloud/glm-5.3:cloud"

PARALLEL_OVERHEAD_FIX_PLAN: list[dict[str, Any]] = [
    {
        "rank": 1,
        "lane": "WF72 A2 support-readiness QA",
        "model": QA_LANE_MODEL,
        "objective": "Prove WF72 remains support-only and recurring SQL retail-grade readiness churn is absent.",
        "allowed_writes": ["tmp/parallel-lanes/wf72-a2-readonly-qa.json"],
        "acceptance": [
            "A2 read guard remains green or exact blocker is named.",
            "No SQL-canon, SQL-first, Python-retirement, or customer-output authority is introduced.",
            "Heavy SQL retail-grade gate is documented as on-demand only.",
        ],
    },
    {
        "rank": 2,
        "lane": "WF78 event-rerouting / quote-readiness QA",
        "model": QA_LANE_MODEL,
        "objective": "Reduce broad expansion proof overhead by keeping WF78 focused on evidence repair and owner-card readiness.",
        "allowed_writes": [
            "tmp/parallel-lanes/wf78-event-rerouting-qa.json",
            "tmp/parallel-lanes/wf78-tier1-quote-readiness-qa.json",
        ],
        "acceptance": [
            "No ticker import or broad expansion proof is queued without product demand or owner review.",
            "Top WF78 actions remain non-capital and source-backed.",
            "Freshness/quote blockers are separated from structural monitor debt.",
        ],
    },
    {
        "rank": 3,
        "lane": "WF73 closeout compression QA",
        "model": QA_LANE_MODEL,
        "objective": "Ensure control-plane validators are run at the right layer and not duplicated after every small proof refresh.",
        "allowed_writes": ["tmp/parallel-lanes/wf73-closeout-compression-qa.json"],
        "acceptance": [
            "Targeted validators are used during implementation.",
            "control_closeout_bundle is reserved for integration closeout.",
            "Route/index proof remains derived and review-only.",
        ],
    },
    {
        "rank": 4,
        "lane": "WF76 cron signal classifier",
        "model": QA_LANE_MODEL,
        "objective": "Separate known blocked cron signals from new/escalated signals before they create implementation work.",
        "allowed_writes": ["tmp/parallel-lanes/wf76-cron-signal-classifier.json"],
        "acceptance": [
            "Known blocked signals are marked monitor-only.",
            "New or changed signals get exact owner, artifact, and stop-line routing.",
            "No cron edits are made without a separate explicit scheduler decision.",
        ],
    },
]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def validate_review(payload: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    workflows = payload.get("workflow_reviews", [])
    if not workflows:
        errors.append("missing_workflow_reviews")
    for item in workflows:
        workflow = item.get("workflow", "unknown")
        for key in (
            "current_phase",
            "recommended_next_phase",
            "heartbeat_posture",
            "cron_posture",
            "helper_lane_posture",
            "main_session_posture",
            "safe_unattended_actions",
            "human_decision_required_for",
            "stop_lines",
        ):
            if not item.get(key):
                errors.append(f"{workflow}:missing_{key}")
        if item.get("heartbeat_posture") not in {
            "flag_only",
            "flag_if_stale_or_authority_widens",
            "flag_if_source_conflict_or_stale",
            "flag_if_coverage_or_router_artifact_missing",
            "flag_if_boot_or_workflow_guard_warns",
            "flag_if_helper_contract_missing",
            "flag_only_after_repeated_friction_or_validator_failure",
            "flag_if_cron_run_state_action_needed",
            "flag_if_probability_language_appears",
        }:
            warnings.append(f"{workflow}:unrecognized_heartbeat_posture")
    if payload.get("heartbeat_policy", {}).get("may_advance_workflow_queue") is not False:
        errors.append("heartbeat_may_advance_workflow_queue_not_false")
    if payload.get("heartbeat_policy", {}).get("may_trigger_bounded_handoff") is not True:
        errors.append("heartbeat_bounded_handoff_not_enabled")
    for finding in payload.get("overhead_friction_findings", []):
        if finding.get("severity") not in {"high", "medium", "low"}:
            errors.append(f"{finding.get('friction_id', 'unknown')}:invalid_severity")
        for key in ("workflow", "friction_id", "fix_strategy", "next_fix"):
            if not finding.get(key):
                errors.append(f"{finding.get('friction_id', 'unknown')}:missing_{key}")
    for lane in payload.get("parallel_overhead_fix_plan", []):
        if lane.get("model") != QA_LANE_MODEL:
            errors.append(f"{lane.get('lane', 'unknown')}:model_not_qa_lane_model")
        allowed_writes = lane.get("allowed_writes", [])
        if not isinstance(allowed_writes, list) or not allowed_writes:
            errors.append(f"{lane.get('lane', 'unknown')}:missing_allowed_writes")
        for path in allowed_writes:
            if not isinstance(path, str) or not path.startswith("tmp/parallel-lanes/"):
                errors.append(f"{lane.get('lane', 'unknown')}:allowed_write_not_parallel_lane_tmp")
    return {
        "status": "ok" if not errors else "error",
        "errors": errors,
        "warnings": warnings,
        "workflow_count": len(workflows),
    }


def build_review() -> dict[str, Any]:
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": utc_now(),
        "status": "draft",
        "scope": {
            "active_workflows_source": "06. Playbooks/Active Workflows.md",
            "heartbeat_source": "HEARTBEAT.md",
            "cron_protocol_source": "06. Playbooks/Cron Job Protocol.md",
            "operator_packet_source": "tmp/operator-packets/operator-packet-index.json",
        },
        "heartbeat_policy": {
            "may_advance_workflow_queue": False,
            "may_run_major_phase_work": False,
            "may_mutate_canon_or_portfolio": False,
            "may_take_external_or_account_actions": False,
            "may_trigger_bounded_handoff": True,
            "allowed_actions": [
                "flag stale/missing/contradictory proof",
                "run lightweight read-only status checks",
                "refresh operator-packet review surfaces when cheap",
                "wake or queue main-session review for an already-defined safe next action",
            ],
        },
        "workflow_reviews": WORKFLOW_REVIEWS,
        "p2_monitor_policy": {
            "members": P2_MONITORS,
            "recommended_phase": "scheduled_artifact_generation_or_flag_only",
            "heartbeat_posture": "flag material drift only",
            "cron_posture": "monitor/report/validator refresh only",
            "stop_line": "no queue advancement, canon mutation, approval inference, or trade/account authority",
        },
        "p3_paused_policy": {
            "members": P3_PAUSED,
            "recommended_phase": "manual_or_resume_trigger_only",
            "heartbeat_posture": "no action unless explicit trigger or contradiction",
            "cron_posture": "none unless separately approved",
        },
        "p4_blocked_policy": {
            "members": P4_BLOCKED,
            "recommended_phase": "blocked",
            "heartbeat_posture": "report only if active risk appears",
            "cron_posture": "no mutation; audit/report only if already scheduled",
        },
        "recommended_next_implementation": [
            "Add a heartbeat continuation candidate artifact that records safe next actions without executing them.",
            "Add a cron/isolated job only after a job card proves exact owner, artifacts, stop lines, and overlap rules.",
            "Use operator packets as the common recovery surface for high-risk lanes.",
            "Keep heartbeat from directly advancing the queue; let it trigger bounded handoffs or report drift.",
        ],
        "overhead_friction_findings": OVERHEAD_FRICTION_FINDINGS,
        "parallel_overhead_fix_plan": PARALLEL_OVERHEAD_FIX_PLAN,
        "authority_boundary": {
            "owner_approval_inferred": False,
            "live_trade_or_account_action_allowed": False,
            "paper_execution_allowed": False,
            "canon_or_portfolio_mutation_allowed": False,
            "config_auth_channel_runtime_mutation_allowed": False,
            "destructive_cleanup_allowed": False,
        },
    }
    payload["validation"] = validate_review(payload)
    payload["status"] = "ok" if payload["validation"]["status"] == "ok" else "error"
    return payload


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temp.replace(path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Review active workflows for safe automation autonomy expansion.")
    parser.add_argument("--write", action="store_true", help="Write the review JSON artifact.")
    parser.add_argument("--validate", action="store_true", help="Exit nonzero if validation fails.")
    parser.add_argument("--out", default=str(DEFAULT_OUT), help="Output path for --write.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    payload = build_review()
    if args.write:
        out = Path(args.out)
        if not out.is_absolute():
            out = ROOT / out
        write_json(out, payload)
        payload["out"] = str(out.relative_to(ROOT)).replace("\\", "/")
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if (payload["status"] == "ok" or not args.validate) else 1


if __name__ == "__main__":
    raise SystemExit(main())
