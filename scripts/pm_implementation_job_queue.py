#!/usr/bin/env python3
"""Build PM implementation job packets from current PM and cron proof.

The PM program state says what should happen next. This script turns that into
implementation-grade job packets: owner surface, files, acceptance proof,
collision group, helper contract, closeout requirements, and stop lines.

It is review-only. It does not spawn helpers, mutate cron, edit files, apply
portfolio/canon changes, import SQL, deliver externally, or infer approval.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from lib.command_guard import command_is_review_only_safe
from lib.proof_budget import (
    closeout_commands,
    scope_split as budget_scope_split,
    validation_budget_contract,
)
from market_data_utils import atomic_write_json, load_json_artifact

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"

DEFAULT_PM_STATE = TMP / "pm-program-state.json"
DEFAULT_PM_ACTIONS = TMP / "pm-next-actions.json"
DEFAULT_CRON_CANDIDATES = TMP / "cron-retire-merge-candidates.json"
DEFAULT_HELPER_PACKETS = TMP / "helper-spawn-packets.json"
DEFAULT_WF74_ROUTER = TMP / "wf74-autonomy-work-router.json"
DEFAULT_OUT = TMP / "pm-implementation-job-queue.json"
DEFAULT_DB = TMP / "pm-implementation-job-queue.sqlite"
DEFAULT_CONTROL_PACKET = TMP / "pm-control-packet.json"
DEFAULT_COMPLETION_LEDGER = ROOT / "state" / "implementation-completion-ledger.jsonl"

SCHEMA = "veritas.pm_implementation_job_queue.v1"

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "executes_jobs": False,
    "spawns_helpers": False,
    "helper_final_authority": False,
    "main_session_final_integrator": True,
    "cron_or_heartbeat_may_execute": False,
    "cron_or_heartbeat_may_spawn": False,
    "config_auth_channel_runtime_mutation_allowed": False,
    "cleanup_move_delete_archive_allowed": False,
    "customer_or_external_delivery_allowed": False,
    "sql_or_ticker_import_allowed": False,
    "sql_first_promotion_allowed": False,
    "canon_or_portfolio_mutation_allowed": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "owner_approval_inferred": False,
}

GLOBAL_STOP_LINES = [
    "no owner approval inference",
    "no customer data, credentials, outreach, or external delivery",
    "no config/auth/channel/service/runtime mutation",
    "no archive/move/delete without exact owner approval",
    "no SQL write/import or SQL-first promotion",
    "no canon/portfolio/sizing/cash/risk-rule mutation",
    "no paper/live/brokerage/account action",
]

PM_CONTROL_WRITE_DB_COMMAND = "python scripts\\pm_control_packet.py --write --write-db --validate"
PM_CONTROL_WRITE_COMMAND = "python scripts\\pm_control_packet.py --write --validate"

AUTO_CRON_PROOF_CLASSES = {
    "finance_validation_pass",
    "pm_packet_refresh",
    "qa_validation_pass",
    "service_state_slice",
    "ticker_card_refresh_gate",
    "trade_grade_decision_os",
    "wf74_cron_migration_repair_plan",
    "wf74_dependency_rollup",
    "wf74_planning_followthrough",
    "wf74_workflow_followup_routing",
    "wf74_workflow_maturity_followup",
    "wf74_workflow_measurement_followup",
}

CRON_PROOF_REFRESH_APPROVAL_FIELDS = (
    "cron_proof_refresh_approved",
    "rsi_cron_graduation_approved",
    "auto_cron_proof_refresh_approved",
)

CRON_GRADUATION_RULE = (
    "Cron proof refresh requires explicit per-job cron graduation approval plus "
    "proof-safe commands, narrow/micro validation budget, queue_only/pm_state closeout, "
    "clean PM worker/verifier proof, and clean cron contracts."
)

PRIORITY_BAND_RANK = {
    "P0": 0,
    "P1": 1,
    "P2": 2,
    "P3": 3,
    "P4": 4,
    "P5": 5,
}

HELPER_LANE_CLASSES = {
    "bounded_product_implementation",
    "canonical_finance_data_plane",
    "finance_validation_pass",
    "local_ui_control_surface",
    "narrow_validation_and_ui_visibility",
    "parallel_overhead_reduction_orchestration",
    "pm_packet_refresh",
    "qa_validation_pass",
    "service_state_slice",
    "ticker_card_refresh_gate",
    "trade_grade_decision_os",
    "wf74_cron_migration_repair_plan",
    "wf74_dependency_rollup",
    "wf74_planning_followthrough",
    "wf74_workflow_followup_routing",
    "wf74_workflow_maturity_followup",
    "wf74_workflow_measurement_followup",
    "wf78_auto_router_consumer_sync",
    "wf78_reputation_scaleout_gate",
}

BOUNDED_PATCH_CLASSES = {
    "bounded_product_implementation",
    "local_ui_control_surface",
    "narrow_validation_and_ui_visibility",
    "parallel_overhead_reduction_orchestration",
    "service_state_slice",
}

LANE_TEMPLATES: dict[str, dict[str, Any]] = {
    "smb_saas_parallel_morning_plan": {
        "owner_surface": "WF75 internal SaaS deliverable gate + WF79-SMB workflow clarity",
        "job_title": "Execute SMB + internal SaaS deliverable-gate morning sprint",
        "implementation_class": "bounded_product_implementation",
        "target_files": [
            "09. Archive/Legacy Audit Roots - Archived/Audit/SMB-SaaS-Parallel-Implementation-Plan-2026-06-18.md",
            "06. Playbooks/Project Continuity/Workflow 75 - AI Productivity and Business Opportunity Intelligence Expansion.md",
            "06. Playbooks/Project Continuity/Workflow 79-SMB - SMB Workflow Clarity and Marketing Ops Automation.md",
            "scripts/generic_intelligence_saas_pivot.py",
            "scripts/wf75_deliverable_packager.py",
            "scripts/wf75_training_desk.py",
            "tmp/wf79-smb-phase-closeout.json",
            "tmp/wf75-deliverable-packager.json",
        ],
        "proof_commands": [
            "python scripts\\generic_intelligence_saas_pivot.py --write --write-db --validate",
            "python scripts\\wf75_deliverable_packager.py --write --validate",
            "python scripts\\wf75_training_desk.py --write --write-md --write-training-assets --validate",
            "python scripts\\pm_control_packet.py --write --write-db --validate",
        ],
        "helper_role": "SMB/SaaS morning sprint implementation helper",
        "collision_group": "smb_saas_parallel_morning_plan",
    },
    "retail_truth_routing": {
        "owner_surface": "P0 Retail Finance / PM cockpit Retail tab",
        "job_title": "Keep retail truth routing implementation surface green",
        "implementation_class": "narrow_validation_and_ui_visibility",
        "target_files": [
            "scripts/retail_truth_routing_contract.py",
            "scripts/retail_answer_harness.py",
            "scripts/retail_automation_control_plane.py",
            "state/pm-cockpit-source-registry.json",
            "apps/pm-control-cockpit",
        ],
        "proof_commands": [
            "python scripts\\retail_truth_routing_contract.py --write --validate",
            "python scripts\\retail_answer_harness.py --write --validate",
            "python scripts\\retail_customer_output_decision_packet.py --write --validate",
            "python scripts\\retail_automation_control_plane.py --write --validate",
            "python scripts\\veritas_harness_scorecard.py --run --write --validate",
        ],
        "helper_role": "Retail truth-routing implementation helper",
        "collision_group": "retail_truth_routing_control_plane",
    },
    "smb_workflow_clarity": {
        "owner_surface": "P1 SMB Workflow Clarity / WF75 service-state lane",
        "job_title": "Advance one anonymous SMB workflow implementation slice",
        "implementation_class": "bounded_product_implementation",
        "target_files": [
            "scripts/generic_intelligence_saas_pivot.py",
            "scripts/wf75_closeout_refresh.py",
            "tmp/wf75-smb-automation-blueprints.json",
            "tmp/wf75-smb-customer-preview-validation.json",
            "tmp/wf79-smb-offer-icp-packet.json",
            "tmp/wf79-smb-demo-packets-validation.json",
            "tmp/wf79-smb-marketing-ops-blueprints-validation.json",
            "tmp/wf79-smb-phase-closeout.json",
        ],
        "proof_commands": [
            "python scripts\\generic_intelligence_saas_pivot.py --write --write-db --validate",
            "python scripts\\wf75_closeout_refresh.py --validation-budget shared --write --validate",
            "python scripts\\pm_control_packet.py --write --write-db --validate",
        ],
        "helper_role": "SMB workflow implementation helper",
        "collision_group": "wf75_smb_service_state",
    },
    "wf75_service_state": {
        "owner_surface": "WF75 service-state automation",
        "job_title": "Run or refine the next anonymous service-state slice",
        "implementation_class": "service_state_slice",
        "target_files": [
            "scripts/wf75_service_state.py",
            "scripts/wf75_closeout_refresh.py",
            "tmp/wf75-service-state-current.json",
            "tmp/wf75-scenario-template-library.json",
        ],
        "proof_commands": [
            "python scripts\\wf75_closeout_refresh.py --validation-budget shared --write --validate",
            "python scripts\\pm_control_packet.py --write --write-db --validate",
        ],
        "helper_role": "WF75 service-state helper",
        "collision_group": "wf75_service_state",
    },
    "operator_console": {
        "owner_surface": "Local operator console / PM cockpit",
        "job_title": "Improve local operator visibility without adding authority",
        "implementation_class": "local_ui_control_surface",
        "target_files": [
            "apps/pm-control-cockpit",
            "state/pm-cockpit-source-registry.json",
            "tmp/wf75-operator-console.json",
        ],
        "proof_commands": [
            "cd apps\\pm-control-cockpit; npm run validate",
            "python scripts\\pm_control_packet.py --write --write-db --validate",
        ],
        "helper_role": "Local cockpit implementation helper",
        "collision_group": "pm_cockpit_ui",
    },
    "parallel_lane_orchestration": {
        "owner_surface": "WF71/WF73 parallel helper orchestration",
        "job_title": "Advance bounded parallel orchestration and overhead reduction lanes",
        "implementation_class": "parallel_overhead_reduction_orchestration",
        "target_files": [
            "scripts/workflow_automation_autonomy_review.py",
            "scripts/parallel_lane_recommender.py",
            "scripts/concurrent_lane_manager.py",
            "tmp/workflow-automation-autonomy-review.json",
            "tmp/parallel-lane-recommendation.json",
            "tmp/concurrent-lane-register.json",
        ],
        "proof_commands": [
            "python scripts\\workflow_automation_autonomy_review.py --write --validate",
            "python scripts\\workflow_routing_index.py --write --write-db --validate",
            "python scripts\\parallel_lane_recommender.py --write --validate",
            "python scripts\\concurrent_lane_manager.py --validate",
            "python scripts\\pm_control_packet.py --write --write-db --validate",
        ],
        "helper_role": "WF71/WF73 orchestration helper",
        "collision_group": "parallel_lane_orchestration",
    },
    "qa_source_trust": {
        "owner_surface": "QA / source trust validator lane",
        "job_title": "Close source-trust and warning debt with targeted validators",
        "implementation_class": "qa_validation_pass",
        "target_files": [
            "scripts/veritas_harness_scorecard.py",
            "scripts/automation_stack_hardening_pass.py",
            "tmp/veritas-harness-scorecard.json",
        ],
        "proof_commands": [
            "python scripts\\veritas_harness_scorecard.py --run --write --validate",
            "python scripts\\automation_stack_hardening_pass.py --write --validate",
        ],
        "helper_role": "Independent QA helper",
        "collision_group": "qa_source_trust",
    },
    "pm_handoff_pdf": {
        "owner_surface": "PM handoff / readiness brief lane",
        "job_title": "Refresh internal PM handoff and readiness packet",
        "implementation_class": "pm_packet_refresh",
        "target_files": [
            "scripts/wf75_pm_weekly_update.py",
            "scripts/wf75_artifact_only_pm_handoff.py",
            "scripts/wf75_pm_readiness_pdf.py",
        ],
        "proof_commands": [
            "python scripts\\wf75_pm_weekly_update.py --write --validate",
            "python scripts\\wf75_artifact_only_pm_handoff.py --write --validate",
            "python scripts\\wf75_pm_readiness_pdf.py --write --validate",
            "python scripts\\pm_control_packet.py --write --write-db --validate",
        ],
        "helper_role": "PM packet helper",
        "collision_group": "pm_handoff_packets",
    },
    "finance_engine": {
        "owner_surface": "WF84/WF85 finance route proof lane",
        "job_title": "Refresh unified finance route proof without capital authority",
        "implementation_class": "finance_validation_pass",
        "target_files": [
            "scripts/finance_data_coverage.py",
            "scripts/runtime_performance_scorecard.py",
            "scripts/artifact_index.py",
            "scripts/finance_intelligence_state.py",
            "tmp/canonical-finance-data-plane.json",
            "tmp/trade-grade-full-answer-assembler.json",
        ],
        "proof_commands": [
            "python scripts\\finance_data_coverage.py --validate --write-contract",
            "python scripts\\runtime_performance_scorecard.py --write --write-md --validate",
            "python scripts\\canonical_finance_data_plane.py --write --write-db --validate",
            "python scripts\\trade_grade_full_answer_assembler.py --all-wf84 --write --validate",
            "python scripts\\artifact_index.py incremental",
            "python scripts\\artifact_index.py validate",
        ],
        "helper_role": "Finance proof helper",
        "collision_group": "finance_proof_refresh",
    },
    "ticker_card_refresh": {
        "owner_surface": "WF77/WF78 ticker-card refresh gate",
        "job_title": "Run ticker-card refresh gate and classify repair queue",
        "implementation_class": "ticker_card_refresh_gate",
        "target_files": [
            "scripts/finance_ticker_card_refresh_gate.py",
            "scripts/ticker_intelligence_card.py",
            "tmp/finance-ticker-card-refresh-gate.json",
            "tmp/ticker-card-refresh-gate-card-build-summary.json",
            "tmp/finance-intelligence-state-stale-tickers.json",
        ],
        "proof_commands": [
            "python scripts\\finance_ticker_card_refresh_gate.py --write --validate --skip-provider-refresh --full-answer-mode changed",
            "python scripts\\automation_stack_hardening_pass.py --write --validate",
            "python scripts\\pm_control_packet.py --write --write-db --validate",
        ],
        "helper_role": "Ticker-card refresh and repair-queue helper",
        "collision_group": "wf77_ticker_card_refresh",
    },
    "tier_promotion_review": {
        "owner_surface": "WF78 automated non-capital tier routing",
        "job_title": "Keep WF78 auto-router primary and classify evidence-repair queue",
        "implementation_class": "wf78_auto_router_consumer_sync",
        "target_files": [
            "scripts/wf78_auto_tier_router.py",
            "scripts/wf78_tier_promotion_review_gate.py",
            "scripts/wf78_tier_b_research_packet.py",
            "scripts/wf78_routing_dashboard.py",
            "tmp/wf78-auto-tier-routing.json",
            "tmp/wf78-capital-review-queue.json",
            "tmp/wf78-capital-review-queue.sqlite",
            "tmp/wf78-event-triggered-rerouting.json",
            "tmp/wf78-event-triggered-rerouting.sqlite",
            "tmp/wf78-tier-promotion-review-gate.json",
            "tmp/wf78-tier-promotion-review-gate.sqlite",
            "tmp/wf78-tier-b-research-packets.json",
            "tmp/wf78-tier-b-research-packet-requests.json",
            "tmp/wf78-tier-b-research-packet-phase2-eval.json",
            "tmp/wf78-101-200-tier-c-owner-decision-packet.json",
            "tmp/wf78-routing-dashboard.json",
            "tmp/wf78-routing-dashboard.sqlite",
            "tmp/finance-ticker-card-refresh-gate.json",
            "tmp/wf78-500-ticker-reputation-gate.json",
        ],
        "proof_commands": [
            "python scripts\\finance_ticker_card_refresh_gate.py --write --validate --skip-provider-refresh --full-answer-mode never",
            "python scripts\\wf78_phase_runner.py --phase all-safe --write --validate",
            "python scripts\\wf78_capital_review_queue.py --write --write-db --validate",
            "python scripts\\wf78_event_triggered_rerouting.py --write --write-db --validate",
            "python scripts\\wf78_auto_tier_router.py --write --validate",
            "python scripts\\wf78_500_ticker_reputation_gate.py --write --write-db --validate",
            "python scripts\\wf78_tier_promotion_review_gate.py --write --write-db --validate",
            "python scripts\\wf78_tier_b_research_packet.py --write --write-db --validate",
            "python scripts\\wf78_tier_funnel_promotion_gate.py --requests tmp\\wf78-tier-b-research-packet-requests.json --out tmp\\wf78-tier-b-research-packet-phase2-eval.json --write --validate",
            "python scripts\\wf78_routing_dashboard.py --write --write-db --validate",
            "python scripts\\automation_stack_hardening_pass.py --write --validate",
            "python scripts\\pm_control_packet.py --write --write-db --validate",
        ],
        "helper_role": "WF78 auto-router consumer-sync helper",
        "collision_group": "wf78_tier_promotion_review",
    },
    "sql_index": {
        "owner_surface": "SQL support-mode index lane",
        "job_title": "Refresh SQL support proof without SQL-first promotion",
        "implementation_class": "sql_support_validation",
        "target_files": [
            "scripts/json_sql_promotion_index.py",
            "scripts/go/bin/python-sql-contract-lint.exe",
            "scripts/go/bin/sql-schema-drift-lint.exe",
            "scripts/go/bin/sql-proof-probe.exe",
            "scripts/go/cmd/python-sql-contract-lint/main.go",
            "scripts/go/cmd/sql-schema-drift-lint/main.go",
            "scripts/go/cmd/sql-proof-probe/main.go",
        ],
        "proof_commands": [
            "python scripts\\json_sql_promotion_index.py --write --write-md --validate",
            ".\\scripts\\go\\bin\\python-sql-contract-lint.exe --root . --out tmp\\python-sql-contract-lint.json",
            ".\\scripts\\go\\bin\\sql-schema-drift-lint.exe --root . --out tmp\\sql-schema-drift-lint.json",
            ".\\scripts\\go\\bin\\sql-proof-probe.exe --root . --out tmp\\sql-proof-probe.json",
        ],
        "helper_role": "SQL support proof helper",
        "collision_group": "sql_support_mode",
    },
    "wf78_scaleout": {
        "owner_surface": "WF78 non-capital feeder for WF84/WF85 finance route",
        "job_title": "Advance 500-ticker feeder scaleout through the reputation gate",
        "implementation_class": "wf78_reputation_scaleout_gate",
        "target_files": [
            "scripts/wf78_phase_runner.py",
            "scripts/wf78_auto_tier_router.py",
            "scripts/wf78_event_triggered_rerouting.py",
            "scripts/wf78_500_ticker_reputation_gate.py",
            "tmp/wf78-auto-tier-routing.json",
            "tmp/wf78-event-triggered-rerouting.json",
            "tmp/wf78-500-ticker-reputation-gate.json",
            "tmp/wf78-500-ticker-reputation-gate.sqlite",
        ],
        "proof_commands": [
            "python scripts\\wf78_phase_runner.py --phase all-safe --write --validate",
            "python scripts\\wf78_event_triggered_rerouting.py --write --write-db --validate",
            "python scripts\\wf78_auto_tier_router.py --write --validate",
            "python scripts\\wf78_500_ticker_reputation_gate.py --write --write-db --validate",
            "python scripts\\automation_stack_hardening_pass.py --write --validate",
            "python scripts\\pm_control_packet.py --write --write-db --validate",
        ],
        "helper_role": "WF78 scaleout feeder reputation helper",
        "collision_group": "wf78_wf84_wf85_feeder_scaleout",
    },
    "finance_os_data_model": {
        "owner_surface": "WF84 canonical finance data-plane contract",
        "job_title": "Maintain WF84 internal finance data-plane consumer/parity proof",
        "implementation_class": "canonical_finance_data_plane",
        "target_files": [
            "scripts/canonical_finance_data_plane_contract.py",
            "scripts/canonical_finance_data_plane.py",
            "tmp/canonical-finance-data-plane-contract.json",
            "tmp/canonical-finance-data-plane.json",
            "tmp/canonical-finance-data-plane-validation.json",
            "tmp/canonical-finance-data-plane.sqlite",
            "tmp/canonical-finance-data-plane-phase6-10.json",
            "tmp/canonical-finance-data-plane-retirement-readiness.json",
        ],
        "proof_commands": [
            "python scripts\\canonical_finance_data_plane_contract.py --write --validate",
            "python scripts\\canonical_finance_data_plane.py --write --write-db --validate",
            "python scripts\\canonical_finance_data_plane_phase6_10.py --write --validate",
            "python scripts\\canonical_finance_data_plane_retirement_readiness.py --write --validate",
            "python scripts\\workflow_router.py WF84 --answer all --validate",
            "python scripts\\pm_control_packet.py --write --write-db --validate",
        ],
        "helper_role": "WF84 canonical finance data-plane implementation helper",
        "collision_group": "finance_os_data_model",
    },
    "trade_grade_decision_os": {
        "owner_surface": "WF85 Personal Trade-Grade Decision OS contract and Phase 1 card builder",
        "job_title": "Advance WF85 Personal Trade-Grade Decision OS",
        "implementation_class": "trade_grade_decision_os",
        "target_files": [
            "scripts/trade_grade_decision_os_contract.py",
            "scripts/trade_grade_decision_cards.py",
            "scripts/trade_grade_repair_conveyor.py",
            "scripts/trade_grade_os_freshness_cron_runner.py",
            "tmp/trade-grade-decision-os-contract.json",
            "tmp/trade-grade-source-freshness-gate.json",
            "tmp/trade-grade-decision-cards.json",
            "tmp/trade-grade-decision-card-authority-validation.json",
            "tmp/trade-grade-approval-card-gate.json",
            "tmp/trade-grade-risk-sizing-overlay.json",
            "tmp/trade-grade-repair-conveyor.json",
            "tmp/trade-grade-os-freshness-cron-runner.json",
            "tmp/post-close-final-quote-ledger.json",
            "tmp/wf78-tier-weighted-freshness-resolution.json",
            "tmp/canonical-finance-data-plane.json",
            "tmp/canonical-finance-data-plane-phase6-10.json",
            "tmp/wf78-capital-review-queue.json",
            "tmp/finance-decision-sync-spine.json",
        ],
        "proof_commands": [
            "python scripts\\trade_grade_decision_os_contract.py --write --validate",
            "python scripts\\trade_grade_os_freshness_cron_runner.py --component daily_core --full-answer-mode changed --write --validate",
            "python scripts\\workflow_router.py WF85 --answer all --validate",
            "python scripts\\pm_control_packet.py --write --write-db --validate",
        ],
        "helper_role": "WF85 trade-grade decision OS implementation helper",
        "collision_group": "trade_grade_decision_os",
    },
}

CRON_DECISION_PROOF = [
    "python scripts\\cron_retire_merge_candidates.py --write --write-md --validate",
    "python scripts\\cron_signal_scorecard.py --write --validate",
    "python scripts\\automation_stack_hardening_pass.py --write --validate",
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


def load_json(path: Path) -> dict[str, Any]:
    payload = load_json_artifact(path)
    return payload if isinstance(payload, dict) else {}


def load_completed_job_ids(path: Path | None = None) -> set[str]:
    path = path or DEFAULT_COMPLETION_LEDGER
    if not path.exists():
        return set()
    completed: set[str] = set()
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        job_id = as_dict(row.get("job")).get("job_id")
        if isinstance(job_id, str) and job_id:
            completed.add(job_id)
    return completed


def completion_text_key(value: Any) -> str:
    return " ".join(str(value or "").casefold().split())


def parse_completion_utc(value: Any) -> datetime | None:
    if not value:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def load_completion_markers(path: Path | None = None) -> dict[str, Any]:
    path = path or DEFAULT_COMPLETION_LEDGER
    markers: dict[str, Any] = {
        "job_ids": set(),
        "lane_title": set(),
        "collision_title": set(),
        "job_completed_at_utc": {},
    }
    if not path.exists():
        return markers
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        job = as_dict(row.get("job"))
        job_id = job.get("job_id")
        title = completion_text_key(job.get("title"))
        lane_id = job.get("lane_id")
        collision_group = job.get("collision_group")
        if isinstance(job_id, str) and job_id:
            markers["job_ids"].add(job_id)
            completed_at = parse_completion_utc(row.get("completed_at_utc") or row.get("recorded_at_utc"))
            if completed_at is not None:
                latest_by_job = markers["job_completed_at_utc"]
                previous = latest_by_job.get(job_id)
                if previous is None or completed_at > previous:
                    latest_by_job[job_id] = completed_at
        if title and isinstance(lane_id, str) and lane_id:
            markers["lane_title"].add((lane_id, title))
        if title and isinstance(collision_group, str) and collision_group:
            markers["collision_title"].add((collision_group, title))
    return markers


def newer_exact_completion_for_regression(job: dict[str, Any], markers: dict[str, Any]) -> bool:
    job_id = job.get("job_id")
    if not isinstance(job_id, str) or job_id not in markers.get("job_ids", set()):
        return False
    prior_completed_at = parse_completion_utc(
        as_dict(job.get("prior_completion")).get("latest_completed_at_utc")
    )
    if prior_completed_at is None:
        return False
    completed_by_job = markers.get("job_completed_at_utc")
    if not isinstance(completed_by_job, dict):
        return False
    exact_completed_at = completed_by_job.get(job_id)
    return isinstance(exact_completed_at, datetime) and exact_completed_at > prior_completed_at


def prior_completion_is_in_ledger(job: dict[str, Any], markers: dict[str, Any]) -> bool:
    matched = as_list(as_dict(job.get("prior_completion")).get("matched_job_ids"))
    known = markers.get("job_ids", set())
    return bool(matched) and all(isinstance(item, str) and item in known for item in matched)


def completion_match_reason(job: dict[str, Any], markers: dict[str, Any]) -> str | None:
    # Residual-visibility rows must not re-enter the ready queue just because the
    # opportunity id changed; resolve them off their recorded prior completion.
    if job.get("completion_status") == "residual_followup_after_completion":
        if prior_completion_is_in_ledger(job, markers):
            return "prior_completion_residual_visibility_only"
        return None
    if job.get("completion_status") == "current_regression_after_completion":
        if newer_exact_completion_for_regression(job, markers):
            return "exact_job_id_after_regression"
        return None
    job_id = job.get("job_id")
    if isinstance(job_id, str) and job_id in markers.get("job_ids", set()):
        return "exact_job_id"
    source_action = str(job.get("source_action_id") or "")
    if not source_action.endswith("-inspect_blocker"):
        return None
    title = completion_text_key(job.get("title"))
    if not title:
        return None
    lane_id = job.get("lane_id")
    collision_group = job.get("collision_group")
    if isinstance(collision_group, str) and (collision_group, title) in markers.get("collision_title", set()):
        return "inspect_blocker_collision_title_alias"
    if isinstance(lane_id, str) and (lane_id, title) in markers.get("lane_title", set()):
        return "inspect_blocker_lane_title_alias"
    return None


def control_pm_program_state() -> dict[str, Any]:
    packet = load_json(DEFAULT_CONTROL_PACKET)
    sections = as_dict(packet.get("sections"))
    program = as_dict(sections.get("pm_program_state"))
    if program.get("status") == "ok" and as_list(program.get("next_actions")):
        return program
    return {}


def path_is_default(value: str | None, default: Path) -> bool:
    return workspace_path(value, default) == default


def actions_from_program_state(program: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema": program.get("schema"),
        "status": program.get("status"),
        "generated_at_utc": program.get("generated_at_utc"),
        "next_actions": program.get("next_actions", []),
        "source": "tmp/pm-control-packet.json#sections.pm_program_state",
    }


def workspace_path(value: str | None, default: Path) -> Path:
    if not value:
        return default
    path = Path(value)
    return path if path.is_absolute() else ROOT / path


def action_template(action: dict[str, Any]) -> dict[str, Any]:
    lane_id = str(action.get("lane_id") or "unknown")
    return LANE_TEMPLATES.get(
        lane_id,
        {
            "owner_surface": f"PM lane: {lane_id}",
            "job_title": f"Execute bounded PM action for {lane_id}",
            "implementation_class": "bounded_review_only_action",
            "target_files": ["tmp/pm-program-state.json", "tmp/pm-next-actions.json"],
            "proof_commands": ["python scripts\\pm_control_packet.py --write --write-db --validate"],
            "helper_role": "OS operator helper",
            "collision_group": lane_id,
        },
    )


def proof_commands_for_template(template: dict[str, Any]) -> list[str]:
    commands = [str(command) for command in as_list(template.get("proof_commands"))]
    if len(commands) <= 1:
        return commands
    pm_control_commands = {PM_CONTROL_WRITE_DB_COMMAND, PM_CONTROL_WRITE_COMMAND}
    # PM execution runs the budgeted closeout command after proof. Keeping the
    # same PM packet command inside every proof list creates duplicate work and
    # inflates the declared proof budget.
    return [command for command in commands if command not in pm_control_commands]


def acceptance_criteria(job: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "criterion": "contract_preserved",
            "done_means": "job output keeps review-only authority and all stop lines remain explicit",
        },
        {
            "criterion": "proof_commands_pass",
            "done_means": "all listed proof commands pass or the job returns a blocker with exact failing artifact",
        },
        {
            "criterion": "adjacent_consumer_updated",
            "done_means": "PM state, handoff, cockpit registry, README, or Active Workflows are updated when their routing text changed",
        },
        {
            "criterion": "closeout_complete",
            "done_means": "PM state, helper handshake if used, and daily/continuity notes are refreshed when work materially changes implementation state",
        },
    ]


def helper_packet(job: dict[str, Any]) -> dict[str, Any]:
    return {
        "packet_id": f"{job['job_id']}-helper",
        "lane_type": job["lane_id"],
        "staff_lane_or_role": job["helper_role"],
        "objective": job["objective"],
        "files_to_read_first": job["target_files"][:8],
        "allowed_actions": [
            "inspect exact files",
            "apply scoped patch or produce patch proposal",
            "run listed proof commands",
            "report blockers before widening scope",
        ],
        "forbidden_actions_or_stop_lines": GLOBAL_STOP_LINES,
        "output_contract": [
            "status",
            "files_inspected",
            "files_changed_or_patch_proposed",
            "tests_or_validators_run",
            "blockers_or_trust_gaps",
            "confidence",
            "merge_recommendation",
            "next_action",
        ],
        "acceptance_proof": job["proof_commands"],
        "validation_budget": job["validation_budget"],
        "closeout_mode": job["closeout_mode"],
        "timeout_or_partial_output_expectation": "20 minutes; return partial findings before timeout",
        "merge_expectation": "main_session_integrates_after_proof",
        "authority_boundary": AUTHORITY_BOUNDARY,
    }


def proof_commands_review_only_safe(commands: list[Any]) -> tuple[bool, list[str]]:
    unsafe: list[str] = []
    for command in commands:
        text = str(command)
        if not command_is_review_only_safe(text):
            unsafe.append(text)
    return (not unsafe, unsafe)


def job_owner_gate_required(job: dict[str, Any]) -> bool:
    status = str(job.get("status") or "")
    if status == "owner_decision_required":
        return True
    if job.get("safe_to_disable_without_more_proof") is False:
        return True
    return False


DEPARTMENT_OWNER_BY_DEPARTMENT = {
    "cron": "cron-automation-manager",
    "runtime_ops": "automation-hardening-manager",
    "pm": "veritas-pm-department",
    "finance_wf78_wf84_wf85": "main-session-veritas-finance",
    "product_wf75_wf79": "smb-workflow-automation-operator",
    "qa": "workspace-qa-pass",
    "skills_procedure": "workspace-governor",
    "memory_continuity": "memory-continuity-manager",
    "main_session_veritas": "main-session-veritas",
}


DEPARTMENT_WORKFLOW_BY_DEPARTMENT = {
    "cron": "CRON/WF73/WF76",
    "runtime_ops": "Runtime Ops/WF74",
    "pm": "PM/WF74",
    "finance_wf78_wf84_wf85": "WF78/WF84/WF85",
    "product_wf75_wf79": "WF75/WF79",
    "qa": "QA/WF73",
    "skills_procedure": "Skills/Procedures/WF74",
    "memory_continuity": "Memory/Continuity",
    "main_session_veritas": "Main Session Veritas",
}


def infer_department(job: dict[str, Any]) -> str:
    text = " ".join(
        str(job.get(key) or "").casefold()
        for key in (
            "implementation_class",
            "owner_surface",
            "lane_id",
            "collision_group",
            "source",
            "source_category",
            "title",
        )
    )
    if "cron" in text:
        return "cron"
    if any(token in text for token in ("wf78", "wf84", "wf85", "finance", "trade_grade", "ticker", "portfolio", "paper_deployment")):
        return "finance_wf78_wf84_wf85"
    if any(token in text for token in ("wf75", "wf79", "retail", "smb", "product", "service_state", "customer_output")):
        return "product_wf75_wf79"
    if any(token in text for token in ("qa", "validator", "validation", "harness", "source_trust", "proof_budget")):
        return "qa"
    if any(token in text for token in ("skill", "procedure", "playbook", "response_contract")):
        return "skills_procedure"
    if any(token in text for token in ("memory", "continuity", "future_session", "status_card", "startup_brief")):
        return "memory_continuity"
    if any(token in text for token in ("wf74", "otel", "runtime", "ops", "dispatcher", "greenkeeper", "worker", "verifier")):
        return "runtime_ops"
    if any(token in text for token in ("pm", "parallel_lane", "implementation_job", "lane")):
        return "pm"
    return "main_session_veritas"


def allowed_execution_mode_for_job(job: dict[str, Any], capabilities: dict[str, Any]) -> str:
    if job.get("status") == "completed_by_ledger" or job.get("completed_by_ledger") is True:
        return "completed_by_ledger_resolved"
    if capabilities.get("owner_gate_required") is True:
        return "owner_gated_review"
    if capabilities.get("auto_cron_may_execute") is True:
        return "cron_review_only_proof_refresh"
    if capabilities.get("auto_main_may_execute") is True:
        return "main_review_only_proof_refresh"
    if capabilities.get("auto_lane_prepare_allowed") is True or capabilities.get("helper_lane_allowed") is True:
        return "main_or_helper_plan_only"
    return "main_session_review"


def attach_department_contract(job: dict[str, Any], capabilities: dict[str, Any] | None = None) -> None:
    capabilities = capabilities or as_dict(job.get("automation_capabilities"))
    department = str(job.get("department") or infer_department(job))
    job["department"] = department
    job["department_owner"] = str(job.get("department_owner") or DEPARTMENT_OWNER_BY_DEPARTMENT.get(department, "main-session-veritas"))
    job["owner_workflow"] = str(job.get("owner_workflow") or DEPARTMENT_WORKFLOW_BY_DEPARTMENT.get(department, "Main Session Veritas"))
    job["accountable_integrator"] = str(job.get("accountable_integrator") or "main_session_veritas")
    job["allowed_execution_mode"] = allowed_execution_mode_for_job(job, capabilities)


def automation_capabilities(job: dict[str, Any]) -> dict[str, Any]:
    implementation_class = str(job.get("implementation_class") or "")
    status = str(job.get("status") or "")
    proof_commands = as_list(job.get("proof_commands"))
    validation_budget = as_dict(job.get("validation_budget")).get("budget")
    closeout_mode = str(job.get("closeout_mode") or "")
    proof_safe, unsafe_commands = proof_commands_review_only_safe(proof_commands)
    owner_gate_required = job_owner_gate_required(job)
    ready_for_main = status == "ready_for_main_or_helper"
    ready_for_review = status == "ready_for_review"
    artifact_refresh = any("--write" in str(command).lower() for command in proof_commands)
    helper_lane_allowed = (
        status in {"ready_for_main_or_helper", "ready_for_review"}
        and implementation_class in HELPER_LANE_CLASSES
        and not owner_gate_required
        and bool(as_list(job.get("target_files")))
    )
    bounded_patch_allowed = implementation_class in BOUNDED_PATCH_CLASSES and helper_lane_allowed
    main_proof_refresh_candidate = (
        proof_safe
        and validation_budget in {"micro", "narrow"}
        and closeout_mode in {"queue_only", "pm_state"}
    )
    auto_main_may_execute = (
        ready_for_main
        and main_proof_refresh_candidate
        and not owner_gate_required
        and not bounded_patch_allowed
    )
    cron_proof_refresh_candidate = (
        auto_main_may_execute
        and implementation_class in AUTO_CRON_PROOF_CLASSES
        and validation_budget in {"micro", "narrow"}
        and closeout_mode in {"queue_only", "pm_state"}
    )
    cron_graduation_satisfied = cron_proof_refresh_candidate and any(
        job.get(field) is True for field in CRON_PROOF_REFRESH_APPROVAL_FIELDS
    )
    auto_cron_may_execute = cron_graduation_satisfied
    return {
        "schema": "veritas.pm_job_automation_capabilities.v1",
        "proof_only": proof_safe,
        "artifact_refresh": artifact_refresh,
        "bounded_patch_allowed": bounded_patch_allowed,
        "helper_lane_allowed": helper_lane_allowed,
        "owner_gate_required": owner_gate_required,
        "main_proof_refresh_candidate": main_proof_refresh_candidate,
        "auto_main_may_execute": auto_main_may_execute,
        "auto_cron_may_execute": auto_cron_may_execute,
        "cron_proof_refresh_candidate": cron_proof_refresh_candidate,
        "cron_graduation_required": cron_proof_refresh_candidate and not cron_graduation_satisfied,
        "cron_graduation_satisfied": cron_graduation_satisfied,
        "auto_heartbeat_may_execute": False,
        "auto_lane_prepare_allowed": (helper_lane_allowed or ready_for_review) and not owner_gate_required,
        "auto_helper_spawn_allowed": False,
        "unsafe_proof_commands": unsafe_commands,
        "execution_scope": (
            "review_only_proof_and_budgeted_closeout"
            if auto_main_may_execute
            else "helper_lane_or_main_review_required"
            if helper_lane_allowed or ready_for_review
            else "blocked_or_owner_gate"
        ),
        "heartbeat_rule": "heartbeat may surface or prepare a main-session action only; it must not execute PM phases.",
        "cron_rule": CRON_GRADUATION_RULE,
    }


def attach_automation_capabilities(job: dict[str, Any]) -> None:
    capabilities = automation_capabilities(job)
    job["automation_capabilities"] = capabilities
    attach_department_contract(job, capabilities)
    # Compatibility fields keep the most important booleans easy to query from
    # JSON, SQLite mirrors, and compact startup packets.
    for key in (
        "proof_only",
        "artifact_refresh",
        "bounded_patch_allowed",
        "helper_lane_allowed",
        "owner_gate_required",
        "main_proof_refresh_candidate",
        "auto_main_may_execute",
        "auto_cron_may_execute",
        "cron_proof_refresh_candidate",
        "cron_graduation_required",
        "cron_graduation_satisfied",
        "auto_heartbeat_may_execute",
    ):
        job[key] = capabilities[key]


def priority_band_rank(priority: Any) -> int:
    return PRIORITY_BAND_RANK.get(str(priority or "P9").upper(), 9)


def numeric_priority(value: Any, fallback_band: Any = None) -> float:
    if isinstance(value, bool):
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str) and value.strip():
        try:
            return float(value.strip())
        except ValueError:
            pass
    band = str(fallback_band or "").upper()
    return {
        "P0": 100.0,
        "P1": 85.0,
        "P2": 65.0,
        "P3": 40.0,
        "P4": 20.0,
        "P5": 10.0,
    }.get(band, 0.0)


def annotate_priority_fields(job: dict[str, Any]) -> None:
    priority = str(job.get("priority") or "P9").upper()
    source_score = numeric_priority(
        job.get("source_priority_score")
        or job.get("priority_score")
        or job.get("source_priority"),
        priority,
    )
    job["priority"] = priority
    job["priority_band_rank"] = priority_band_rank(priority)
    job["source_priority_score"] = source_score
    job["priority_sort_key"] = {
        "status_ready_rank": 0 if job.get("status") in {"ready_for_main_or_helper", "ready_for_review"} else 1,
        "completed_rank": 1 if job.get("status") == "completed_by_ledger" or job.get("completed_by_ledger") is True else 0,
        "priority_band_rank": priority_band_rank(priority),
        "source_priority_desc": -source_score,
        "readiness_desc": -float(job.get("readiness_score") or 0),
        "rank": int(job.get("rank") or 9999),
    }


def job_sort_tuple(job: dict[str, Any]) -> tuple[Any, ...]:
    annotate_priority_fields(job)
    key = as_dict(job.get("priority_sort_key"))
    return (
        int(key.get("completed_rank") or 0),
        int(key.get("status_ready_rank") or 1),
        int(key.get("priority_band_rank") or 9),
        float(key.get("source_priority_desc") or 0),
        float(key.get("readiness_desc") or 0),
        int(key.get("rank") or 9999),
        str(job.get("job_id") or ""),
    )


def wf74_priority_lookup(wf74_router: dict[str, Any]) -> dict[str, dict[str, Any]]:
    lookup: dict[str, dict[str, Any]] = {}
    for row in as_list(wf74_router.get("recommendation_action_ledger")):
        item = as_dict(row)
        keys = [
            item.get("recommendation_id"),
            item.get("opportunity_id"),
            item.get("pm_job_id"),
        ]
        value = {
            "source_priority_score": item.get("priority"),
            "source_priority_band": item.get("priority_band"),
            "source_recommendation_id": item.get("recommendation_id"),
            "source_opportunity_id": item.get("opportunity_id"),
            "source_recommendation_title": item.get("title"),
        }
        for key in keys:
            if key:
                lookup[str(key)] = value
    return lookup


def stable_job_id(prefix: str, *parts: Any) -> str:
    raw = "-".join(str(part or "").strip() for part in parts if str(part or "").strip())
    chars = [ch.lower() if ch.isalnum() else "-" for ch in raw]
    slug = "".join(chars)
    while "--" in slug:
        slug = slug.replace("--", "-")
    slug = slug.strip("-") or "unknown"
    return f"{prefix}-{slug}"


def build_pm_job(action: dict[str, Any], rank: int) -> dict[str, Any]:
    lane_id = str(action.get("lane_id") or "unknown")
    template = action_template(action)
    job_id = stable_job_id("pm", lane_id, action.get("action_type", "action"))
    lane_status = action.get("lane_status")
    if lane_status == "blocked":
        status = "blocked"
    elif lane_status == "on_hold":
        status = "on_hold"
    else:
        status = "ready_for_main_or_helper"
    job = {
        "job_id": job_id,
        "rank": rank,
        "priority": "P1" if rank <= 3 else "P2" if rank <= 6 else "P3",
        "status": status,
        "source": "pm_next_actions",
        "source_action_id": action.get("action_id"),
        "lane_id": lane_id,
        "lane_status": action.get("lane_status"),
        "readiness_score": action.get("readiness_score"),
        "title": template["job_title"],
        "objective": action.get("description") or template["job_title"],
        "implementation_class": template["implementation_class"],
        "owner_surface": template["owner_surface"],
        "target_files": template["target_files"],
        "collision_group": template["collision_group"],
        "dependencies": [
            "source artifacts in PM state must be parseable/current enough for the job",
            "no active helper lane may share the same collision group",
            "main session remains final integrator",
        ],
        "proof_commands": proof_commands_for_template(template),
        "acceptance_criteria": [],
        "scope_split": [],
        "helper_role": template["helper_role"],
        "validation_budget": {},
        "closeout_mode": None,
        "closeout_required": [],
        "stop_lines": sorted(set(GLOBAL_STOP_LINES + as_list(action.get("stop_lines")))),
        "authority_boundary": AUTHORITY_BOUNDARY,
    }
    budget = validation_budget_contract(job["implementation_class"], job["proof_commands"])
    job["validation_budget"] = budget
    job["closeout_mode"] = budget["closeout_mode"]
    job["closeout_required"] = closeout_commands(str(job["closeout_mode"]))
    job["acceptance_criteria"] = acceptance_criteria(job)
    job["scope_split"] = budget_scope_split(job_id, job["implementation_class"], budget["budget"])
    job["helper_packet"] = helper_packet(job)
    attach_automation_capabilities(job)
    return job


def build_cron_decision_job(candidate: dict[str, Any], rank: int) -> dict[str, Any]:
    candidate_type = str(candidate.get("candidate_type") or "cron_candidate")
    name = str(candidate.get("name") or "unknown cron job")
    safe_to_disable = candidate.get("requires_owner_decision_before_disable") is False and candidate_type.startswith("repair")
    status = "owner_decision_required" if candidate.get("requires_owner_decision_before_disable") else "ready_for_review"
    job_id = f"cron-{rank:02d}-{candidate_type}".replace("_", "-")
    job = {
        "job_id": job_id,
        "rank": rank,
        "priority": candidate.get("priority", "P3"),
        "status": status,
        "source": "cron_retire_merge_candidates",
        "source_cron_job_id": candidate.get("job_id"),
        "lane_id": "cron_operating_leverage",
        "lane_status": "candidate",
        "title": f"{'Cron repair' if candidate_type.startswith('repair') else 'Cron thinning decision'}: {name}",
        "objective": candidate.get("recommendation") or "Review cron retire/merge candidate.",
        "implementation_class": candidate_type,
        "owner_surface": "WF73/WF76 cron operating leverage",
        "target_files": [
            "tmp/cron-retire-merge-candidates.json",
            "tmp/cron-signal-scorecard.json",
            "tmp/automation-stack-hardening-pass.json",
        ],
        "collision_group": "cron_scheduler",
        "dependencies": [
            "owner decision required before disabling or merging enabled jobs",
            "replacement proof must preserve coverage and hardening must stay green",
        ],
        "proof_commands": CRON_DECISION_PROOF,
        "acceptance_criteria": [
            {
                "criterion": "coverage_preserved",
                "done_means": "replacement digest/runner proves equivalent or better signal quality",
            },
            {
                "criterion": "rollback_known",
                "done_means": "original cron job ID, schedule, and payload are captured before disable/merge",
            },
            {
                "criterion": "owner_decision_respected",
                "done_means": "no disable/merge occurs unless owner decision is explicit or the candidate is purely a repair-safe no-authority change",
            },
        ],
        "validation_budget": {},
        "closeout_mode": None,
        "scope_split": [],
        "helper_role": "Cron operating-leverage helper",
        "helper_packet": {},
        "closeout_required": [],
        "stop_lines": GLOBAL_STOP_LINES + ["no cron disable/merge without owner decision unless safe_to_disable_without_more_proof is true"],
        "safe_to_disable_without_more_proof": safe_to_disable,
        "authority_boundary": AUTHORITY_BOUNDARY,
    }
    budget = validation_budget_contract(job["implementation_class"], job["proof_commands"])
    job["validation_budget"] = budget
    job["closeout_mode"] = budget["closeout_mode"]
    job["scope_split"] = budget_scope_split(job_id, job["implementation_class"], budget["budget"])
    job["closeout_required"] = closeout_commands(str(job["closeout_mode"]))
    job["helper_packet"] = helper_packet(job)
    attach_automation_capabilities(job)
    return job


def build_wf74_router_job(candidate: dict[str, Any], rank: int) -> dict[str, Any]:
    job_id = str(candidate.get("job_id") or stable_job_id("pm-wf74", candidate.get("source_key"), rank))
    proof_commands = [str(command) for command in as_list(candidate.get("proof_commands")) if str(command).strip()]
    job = {
        "job_id": job_id,
        "rank": rank,
        "priority": candidate.get("priority") or ("P1" if rank <= 3 else "P2"),
        "status": candidate.get("status") or "ready_for_main_or_helper",
        "source": "wf74_autonomy_work_router",
        "source_action_id": candidate.get("source_key"),
        "source_recommendation_id": candidate.get("source_recommendation_id") or candidate.get("source_key"),
        "source_opportunity_id": candidate.get("source_opportunity_id"),
        "source_recommendation_title": candidate.get("source_recommendation_title"),
        "source_priority_score": candidate.get("source_priority_score") or candidate.get("priority_score"),
        "source_priority_band": candidate.get("source_priority_band") or candidate.get("priority_band"),
        "source_category": candidate.get("source_category"),
        "completion_status": candidate.get("completion_status"),
        "prior_completion": candidate.get("prior_completion"),
        "lane_id": candidate.get("lane_id") or "wf74_autonomy_work_router",
        "lane_status": candidate.get("lane_status") or "ready",
        "readiness_score": candidate.get("readiness_score", 85),
        "title": candidate.get("title") or job_id,
        "objective": candidate.get("objective") or candidate.get("title") or "Advance routed WF74 follow-through job.",
        "implementation_class": candidate.get("implementation_class") or "wf74_workflow_followup_routing",
        "owner_surface": candidate.get("owner_surface") or "WF74 autonomy work router",
        "target_files": [str(path) for path in as_list(candidate.get("target_files"))],
        "collision_group": candidate.get("collision_group") or "wf74_autonomy_work_router",
        "dependencies": as_list(candidate.get("dependencies")) or [
            "WF74 autonomy work router must be current and validator-clean",
            "main session remains final integrator",
            "cron may execute only proof-safe narrow jobs when automation capabilities allow it",
        ],
        "proof_commands": proof_commands,
        "acceptance_criteria": as_list(candidate.get("acceptance_criteria")) or [
            {
                "criterion": "wf74_route_consumed",
                "done_means": "router output is reflected in PM queue/control packets",
            },
            {
                "criterion": "proof_commands_pass",
                "done_means": "listed review-only proof commands pass or produce an exact blocker",
            },
        ],
        "scope_split": [],
        "helper_role": candidate.get("helper_role") or "WF74 follow-through helper",
        "validation_budget": {},
        "closeout_mode": None,
        "closeout_required": [],
        "stop_lines": sorted(set(GLOBAL_STOP_LINES + [str(item) for item in as_list(candidate.get("stop_lines"))])),
        "authority_boundary": AUTHORITY_BOUNDARY,
    }
    budget = validation_budget_contract(str(job["implementation_class"]), proof_commands)
    job["validation_budget"] = budget
    job["closeout_mode"] = budget["closeout_mode"]
    job["scope_split"] = budget_scope_split(job_id, str(job["implementation_class"]), budget["budget"])
    job["closeout_required"] = closeout_commands(str(job["closeout_mode"]))
    job["helper_packet"] = helper_packet(job)
    attach_automation_capabilities(job)
    annotate_priority_fields(job)
    return job


def collision_summary(jobs: list[dict[str, Any]]) -> dict[str, Any]:
    groups: dict[str, list[str]] = {}
    for job in jobs:
        groups.setdefault(str(job.get("collision_group")), []).append(str(job.get("job_id")))
    collisions = {key: value for key, value in groups.items() if len(value) > 1}
    return {
        "group_count": len(groups),
        "colliding_group_count": len(collisions),
        "collisions": collisions,
        "rule": "Do not run two implementation jobs in the same collision group at the same time.",
    }


def validate_payload(payload: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    if payload.get("authority_boundary") != AUTHORITY_BOUNDARY:
        errors.append("authority_boundary_changed")
    jobs = as_list(payload.get("jobs"))
    if not jobs:
        errors.append("no_jobs")
    for job in jobs:
        if as_dict(job).get("authority_boundary") != AUTHORITY_BOUNDARY:
            errors.append(f"job_authority_boundary_changed:{job.get('job_id')}")
        if not as_list(job.get("proof_commands")):
            errors.append(f"job_missing_proof_commands:{job.get('job_id')}")
        if not as_list(job.get("acceptance_criteria")):
            errors.append(f"job_missing_acceptance_criteria:{job.get('job_id')}")
        if not as_list(job.get("scope_split")):
            errors.append(f"job_missing_scope_split:{job.get('job_id')}")
        budget = as_dict(job.get("validation_budget"))
        if budget.get("budget") not in {"micro", "narrow", "shared", "major"}:
            errors.append(f"job_missing_validation_budget:{job.get('job_id')}")
        if job.get("closeout_mode") not in {"queue_only", "pm_state", "handoff", "integration"}:
            errors.append(f"job_missing_closeout_mode:{job.get('job_id')}")
        if not as_list(job.get("closeout_required")):
            errors.append(f"job_missing_closeout_required:{job.get('job_id')}")
        if not as_dict(job.get("helper_packet")):
            errors.append(f"job_missing_helper_packet:{job.get('job_id')}")
        capabilities = as_dict(job.get("automation_capabilities"))
        required_capability_keys = {
            "proof_only",
            "artifact_refresh",
            "bounded_patch_allowed",
            "helper_lane_allowed",
            "owner_gate_required",
            "main_proof_refresh_candidate",
            "auto_main_may_execute",
            "auto_cron_may_execute",
            "cron_proof_refresh_candidate",
            "cron_graduation_required",
            "cron_graduation_satisfied",
            "auto_heartbeat_may_execute",
            "auto_lane_prepare_allowed",
            "auto_helper_spawn_allowed",
        }
        missing = sorted(key for key in required_capability_keys if key not in capabilities)
        if missing:
            errors.append(f"job_missing_automation_capabilities:{job.get('job_id')}:{','.join(missing)}")
        if capabilities.get("auto_heartbeat_may_execute") is not False:
            errors.append(f"job_heartbeat_execution_enabled:{job.get('job_id')}")
        if capabilities.get("auto_helper_spawn_allowed") is not False:
            errors.append(f"job_helper_spawn_enabled:{job.get('job_id')}")
        if capabilities.get("owner_gate_required") and capabilities.get("auto_main_may_execute"):
            errors.append(f"owner_gate_job_auto_main_enabled:{job.get('job_id')}")
        if capabilities.get("unsafe_proof_commands") and capabilities.get("auto_main_may_execute"):
            errors.append(f"unsafe_job_auto_main_enabled:{job.get('job_id')}")
        if capabilities.get("auto_cron_may_execute") and capabilities.get("cron_graduation_satisfied") is not True:
            errors.append(f"cron_job_missing_graduation:{job.get('job_id')}")
        for key in ("department", "department_owner", "owner_workflow", "accountable_integrator", "allowed_execution_mode"):
            if not str(job.get(key) or "").strip():
                errors.append(f"job_missing_department_contract:{job.get('job_id')}:{key}")
        if job.get("accountable_integrator") != "main_session_veritas":
            errors.append(f"job_non_main_integrator:{job.get('job_id')}:{job.get('accountable_integrator')}")
        if job.get("department") not in DEPARTMENT_OWNER_BY_DEPARTMENT:
            errors.append(f"job_unknown_department:{job.get('job_id')}:{job.get('department')}")
    if as_dict(payload.get("collision_summary")).get("colliding_group_count"):
        warnings.append("one_or_more_collision_groups_have_multiple_candidate_jobs")
    if as_dict(payload.get("summary")).get("owner_decision_job_count"):
        warnings.append("owner_decision_jobs_present")
    return {"status": "ok" if not errors else "blocked", "errors": errors, "warnings": warnings}


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    pm_state_path = workspace_path(args.pm_state, DEFAULT_PM_STATE)
    pm_actions_path = workspace_path(args.pm_actions, DEFAULT_PM_ACTIONS)
    cron_candidates_path = workspace_path(args.cron_candidates, DEFAULT_CRON_CANDIDATES)
    helper_packets_path = workspace_path(args.helper_packets, DEFAULT_HELPER_PACKETS)
    wf74_router_path = workspace_path(getattr(args, "wf74_router", None), DEFAULT_WF74_ROUTER)
    control_program = (
        control_pm_program_state()
        if path_is_default(args.pm_state, DEFAULT_PM_STATE) and path_is_default(args.pm_actions, DEFAULT_PM_ACTIONS)
        else {}
    )
    pm_state = getattr(args, "pm_state_payload", None) or control_program or load_json(pm_state_path)
    pm_actions = getattr(args, "pm_actions_payload", None) or (actions_from_program_state(control_program) if control_program else load_json(pm_actions_path))
    cron_candidates = getattr(args, "cron_candidates_payload", None) or load_json(cron_candidates_path)
    helper_packets = getattr(args, "helper_packets_payload", None) or load_json(helper_packets_path)
    wf74_router = getattr(args, "wf74_router_payload", None) or load_json(wf74_router_path)

    actions = [item for item in as_list(pm_actions.get("next_actions")) if isinstance(item, dict)]
    selected_actions = actions[: args.max_pm_jobs]
    jobs = [build_pm_job(action, index) for index, action in enumerate(selected_actions, start=1)]
    cron_jobs = [
        build_cron_decision_job(candidate, index + len(jobs))
        for index, candidate in enumerate(as_list(cron_candidates.get("candidates"))[: args.max_cron_jobs], start=1)
        if isinstance(candidate, dict)
    ]
    jobs.extend(cron_jobs)
    wf74_priorities = wf74_priority_lookup(wf74_router)
    wf74_candidates = []
    for candidate in as_list(wf74_router.get("pm_job_candidates"))[: getattr(args, "max_wf74_jobs", 8)]:
        if not isinstance(candidate, dict):
            continue
        enriched = dict(candidate)
        for lookup_key in (candidate.get("source_key"), candidate.get("job_id")):
            if lookup_key and str(lookup_key) in wf74_priorities:
                for key, value in wf74_priorities[str(lookup_key)].items():
                    enriched.setdefault(key, value)
        wf74_candidates.append(enriched)
    wf74_jobs = [
        build_wf74_router_job(candidate, index + len(jobs))
        for index, candidate in enumerate(wf74_candidates, start=1)
    ]
    jobs.extend(wf74_jobs)
    for job in jobs:
        annotate_priority_fields(job)
    completion_markers = load_completion_markers()
    completable_statuses = {"ready_for_main_or_helper", "ready_for_review"}
    for job in jobs:
        match_reason = completion_match_reason(job, completion_markers)
        if match_reason and (
            job.get("status") in completable_statuses
            or str(match_reason).startswith("inspect_blocker_")
        ):
            job["status"] = "completed_by_ledger"
            job["completed_by_ledger"] = True
            job["completion_match"] = match_reason
            attach_automation_capabilities(job)
            annotate_priority_fields(job)
    jobs.sort(key=job_sort_tuple)
    for index, job in enumerate(jobs, start=1):
        job["rank"] = index
        annotate_priority_fields(job)

    ready_jobs = [job for job in jobs if job.get("status") in {"ready_for_main_or_helper", "ready_for_review"}]
    owner_decision_jobs = [job for job in jobs if job.get("status") == "owner_decision_required"]
    completed_jobs = [job for job in jobs if job.get("status") == "completed_by_ledger" or job.get("completed_by_ledger") is True]
    completed_object_ids = {id(job) for job in completed_jobs}
    active_jobs = [job for job in jobs if id(job) not in completed_object_ids]
    top_job = ready_jobs[0] if ready_jobs else (active_jobs[0] if active_jobs else {})
    top_completed_job = completed_jobs[0] if completed_jobs else {}
    payload = {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "draft",
        "purpose": "Implementation-grade PM job queue derived from PM next actions and cron retire/merge proof.",
        "sources": {
            "pm_program_state": rel(pm_state_path),
            "pm_next_actions": rel(pm_actions_path),
            "cron_retire_merge_candidates": rel(cron_candidates_path),
            "helper_spawn_packets": rel(helper_packets_path),
            "wf74_autonomy_work_router": rel(wf74_router_path),
            "implementation_completion_ledger": rel(DEFAULT_COMPLETION_LEDGER),
        },
        "source_status": {
            "pm_program_state_status": pm_state.get("status"),
            "pm_next_actions_status": pm_actions.get("status"),
            "cron_candidates_status": cron_candidates.get("status"),
            "helper_spawn_packets_status": helper_packets.get("status"),
            "wf74_router_status": wf74_router.get("status"),
            "wf74_router_validation_status": as_dict(wf74_router.get("validation")).get("status"),
            "pm_program_state_effective_source": (
                "tmp/pm-control-packet.json#sections.pm_program_state" if control_program else rel(pm_state_path)
            ),
            "pm_next_actions_effective_source": (
                "tmp/pm-control-packet.json#sections.pm_program_state.next_actions" if control_program else rel(pm_actions_path)
            ),
        },
        "summary": {
            "job_count": len(jobs),
            "ready_job_count": len(ready_jobs),
            "owner_decision_job_count": len(owner_decision_jobs),
            "blocked_job_count": len([job for job in jobs if job.get("status") == "blocked"]),
            "pm_action_job_count": len(selected_actions),
            "cron_decision_job_count": len(cron_jobs),
            "wf74_router_pm_job_candidate_count": len(wf74_candidates),
            "wf74_router_job_count": len(wf74_jobs),
            "wf74_recommendation_to_route_conversion_rate": as_dict(wf74_router.get("kpis")).get("recommendation_to_route_conversion_rate"),
            "wf74_route_to_pm_job_conversion_rate": as_dict(wf74_router.get("kpis")).get("route_to_pm_job_conversion_rate"),
            "wf74_high_priority_overdue_count": as_dict(wf74_router.get("kpis")).get("high_priority_overdue_count"),
            "wf74_planning_followthrough_clean_rate": as_dict(wf74_router.get("kpis")).get("planning_followthrough_clean_rate"),
            "completed_by_ledger_job_count": len(completed_jobs),
            "active_job_count": len(active_jobs),
            "auto_main_executable_job_count": len([
                job for job in jobs if as_dict(job.get("automation_capabilities")).get("auto_main_may_execute") is True
            ]),
            "auto_cron_executable_job_count": len([
                job for job in jobs if as_dict(job.get("automation_capabilities")).get("auto_cron_may_execute") is True
            ]),
            "cron_proof_refresh_candidate_count": len([
                job for job in jobs if as_dict(job.get("automation_capabilities")).get("cron_proof_refresh_candidate") is True
            ]),
            "cron_graduation_required_job_count": len([
                job for job in jobs if as_dict(job.get("automation_capabilities")).get("cron_graduation_required") is True
            ]),
            "cron_graduation_satisfied_job_count": len([
                job for job in jobs if as_dict(job.get("automation_capabilities")).get("cron_graduation_satisfied") is True
            ]),
            "auto_heartbeat_executable_job_count": len([
                job for job in jobs if as_dict(job.get("automation_capabilities")).get("auto_heartbeat_may_execute") is True
            ]),
            "helper_lane_allowed_job_count": len([
                job for job in jobs if as_dict(job.get("automation_capabilities")).get("helper_lane_allowed") is True
            ]),
            "bounded_patch_allowed_job_count": len([
                job for job in jobs if as_dict(job.get("automation_capabilities")).get("bounded_patch_allowed") is True
            ]),
            "owner_gate_required_job_count": len([
                job for job in jobs if as_dict(job.get("automation_capabilities")).get("owner_gate_required") is True
            ]),
            "department_counts": {
                department: len([job for job in jobs if job.get("department") == department])
                for department in sorted({str(job.get("department") or "unknown") for job in jobs})
            },
            "department_ready_counts": {
                department: len([
                    job for job in ready_jobs
                    if job.get("department") == department
                ])
                for department in sorted({str(job.get("department") or "unknown") for job in jobs})
            },
            "allowed_execution_mode_counts": {
                mode: len([job for job in jobs if job.get("allowed_execution_mode") == mode])
                for mode in sorted({str(job.get("allowed_execution_mode") or "unknown") for job in jobs})
            },
            "top_job_id": top_job.get("job_id"),
            "top_job_title": top_job.get("title"),
            "top_job_source_priority_score": top_job.get("source_priority_score"),
            "top_ready_job_id": ready_jobs[0].get("job_id") if ready_jobs else None,
            "top_ready_job_title": ready_jobs[0].get("title") if ready_jobs else None,
            "top_ready_job_source_priority_score": ready_jobs[0].get("source_priority_score") if ready_jobs else None,
            "top_completed_job_id": top_completed_job.get("job_id"),
            "top_completed_job_title": top_completed_job.get("title"),
            "top_completed_job_source_priority_score": top_completed_job.get("source_priority_score"),
            "validation_budget_counts": {
                budget: len([job for job in jobs if as_dict(job.get("validation_budget")).get("budget") == budget])
                for budget in ("micro", "narrow", "shared", "major")
            },
            "closeout_mode_counts": {
                mode: len([job for job in jobs if job.get("closeout_mode") == mode])
                for mode in ("queue_only", "pm_state", "handoff", "integration")
            },
        },
        "collision_summary": collision_summary(jobs),
        "jobs": jobs,
        "recommended_execution_rule": "Run only one job per collision group; use each job's validation_budget and closeout_mode instead of a fixed broad closeout ladder.",
        "closeout_enforcer": {
            "budget_modes": {
                "queue_only": closeout_commands("queue_only"),
                "pm_state": closeout_commands("pm_state"),
                "handoff": closeout_commands("handoff"),
                "integration": closeout_commands("integration"),
            },
            "continuity_rule": "Update daily memory or owning continuity only when implementation state materially changed.",
        },
        "authority_boundary": AUTHORITY_BOUNDARY,
    }
    payload["validation"] = validate_payload(payload)
    payload["status"] = "ok" if payload["validation"]["status"] == "ok" else "blocked"
    return payload


def rebuild_sqlite(payload: dict[str, Any], db_path: Path) -> dict[str, Any]:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if db_path.exists():
        db_path.unlink()
    conn = sqlite3.connect(db_path)
    try:
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA journal_mode=DELETE")
        conn.executescript(
            """
            CREATE TABLE pm_implementation_jobs (
              job_id TEXT PRIMARY KEY,
              rank INTEGER NOT NULL,
              priority TEXT NOT NULL,
              status TEXT NOT NULL,
              lane_id TEXT NOT NULL,
              implementation_class TEXT NOT NULL,
              owner_surface TEXT NOT NULL,
              department TEXT NOT NULL,
              department_owner TEXT NOT NULL,
              owner_workflow TEXT NOT NULL,
              accountable_integrator TEXT NOT NULL,
              allowed_execution_mode TEXT NOT NULL,
              title TEXT NOT NULL,
              objective TEXT NOT NULL,
              collision_group TEXT NOT NULL,
              proof_command_count INTEGER NOT NULL,
              validation_budget TEXT NOT NULL,
              closeout_mode TEXT NOT NULL,
              phase_count INTEGER NOT NULL,
              helper_role TEXT NOT NULL,
              proof_only INTEGER NOT NULL,
              artifact_refresh INTEGER NOT NULL,
              bounded_patch_allowed INTEGER NOT NULL,
              helper_lane_allowed INTEGER NOT NULL,
              owner_gate_required INTEGER NOT NULL,
              auto_main_may_execute INTEGER NOT NULL,
              auto_cron_may_execute INTEGER NOT NULL,
              auto_heartbeat_may_execute INTEGER NOT NULL
            );
            CREATE TABLE pm_implementation_job_files (
              job_id TEXT NOT NULL,
              path TEXT NOT NULL,
              FOREIGN KEY(job_id) REFERENCES pm_implementation_jobs(job_id)
            );
            CREATE TABLE pm_implementation_job_proof (
              job_id TEXT NOT NULL,
              command TEXT NOT NULL,
              FOREIGN KEY(job_id) REFERENCES pm_implementation_jobs(job_id)
            );
            """
        )
        for job in as_list(payload.get("jobs")):
            capabilities = as_dict(job.get("automation_capabilities"))
            conn.execute(
                "INSERT INTO pm_implementation_jobs VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    job["job_id"],
                    job["rank"],
                    job["priority"],
                    job["status"],
                    job["lane_id"],
                    job["implementation_class"],
                    job["owner_surface"],
                    job["department"],
                    job["department_owner"],
                    job["owner_workflow"],
                    job["accountable_integrator"],
                    job["allowed_execution_mode"],
                    job["title"],
                    job["objective"],
                    job["collision_group"],
                    len(as_list(job.get("proof_commands"))),
                    as_dict(job.get("validation_budget")).get("budget"),
                    job.get("closeout_mode"),
                    len(as_list(job.get("scope_split"))),
                    job["helper_role"],
                    int(capabilities.get("proof_only") is True),
                    int(capabilities.get("artifact_refresh") is True),
                    int(capabilities.get("bounded_patch_allowed") is True),
                    int(capabilities.get("helper_lane_allowed") is True),
                    int(capabilities.get("owner_gate_required") is True),
                    int(capabilities.get("auto_main_may_execute") is True),
                    int(capabilities.get("auto_cron_may_execute") is True),
                    int(capabilities.get("auto_heartbeat_may_execute") is True),
                ),
            )
            for path in as_list(job.get("target_files")):
                conn.execute("INSERT INTO pm_implementation_job_files VALUES (?, ?)", (job["job_id"], path))
            for command in as_list(job.get("proof_commands")):
                conn.execute("INSERT INTO pm_implementation_job_proof VALUES (?, ?)", (job["job_id"], command))
        conn.commit()
        integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
        foreign_keys = conn.execute("PRAGMA foreign_key_check").fetchall()
        counts = {
            "pm_implementation_jobs": conn.execute("SELECT COUNT(*) FROM pm_implementation_jobs").fetchone()[0],
            "pm_implementation_job_files": conn.execute("SELECT COUNT(*) FROM pm_implementation_job_files").fetchone()[0],
            "pm_implementation_job_proof": conn.execute("SELECT COUNT(*) FROM pm_implementation_job_proof").fetchone()[0],
        }
    finally:
        conn.close()
    return {
        "db_path": rel(db_path),
        "status": "ok" if integrity == "ok" and not foreign_keys else "blocked",
        "integrity_check": integrity,
        "foreign_key_errors": len(foreign_keys),
        "table_counts": counts,
        "authority_boundary": "Derived PM implementation lookup only. JSON remains source proof; no execution or mutation authority.",
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build review-only PM implementation job queue.")
    parser.add_argument("--pm-state", default=str(DEFAULT_PM_STATE))
    parser.add_argument("--pm-actions", default=str(DEFAULT_PM_ACTIONS))
    parser.add_argument("--cron-candidates", default=str(DEFAULT_CRON_CANDIDATES))
    parser.add_argument("--helper-packets", default=str(DEFAULT_HELPER_PACKETS))
    parser.add_argument("--wf74-router", default=str(DEFAULT_WF74_ROUTER))
    parser.add_argument("--max-pm-jobs", type=int, default=10)
    parser.add_argument("--max-cron-jobs", type=int, default=4)
    parser.add_argument("--max-wf74-jobs", type=int, default=8)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--write-db", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    parser.add_argument("--db", default=str(DEFAULT_DB))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    out = workspace_path(args.out, DEFAULT_OUT)
    db_path = workspace_path(args.db, DEFAULT_DB)
    payload = build_payload(args)
    db_result = None
    if args.write:
        atomic_write_json(out, payload)
    if args.write_db:
        db_result = rebuild_sqlite(payload, db_path)
    result = {
        "status": payload.get("status"),
        "out": rel(out),
        "summary": payload.get("summary"),
        "collision_summary": payload.get("collision_summary"),
        "validation": payload.get("validation"),
        "sqlite": db_result,
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    if args.validate and (payload.get("status") != "ok" or (db_result and db_result.get("status") != "ok")):
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
