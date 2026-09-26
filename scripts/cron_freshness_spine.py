#!/usr/bin/env python3
"""Build a read-only cron freshness spine.

The spine gives the main session one proof surface for cron freshness. It
registers every enabled cron job against its expected proof artifacts, checks
freshness and authority posture, and emits queue signals for the scorecard.

It does not mutate cron state, schedules, runtime config, notes, canon,
portfolio state, SQL source tables, customer surfaces, paper orders, live
accounts, or owner approvals.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from market_data_utils import atomic_write_json, load_json_artifact


ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"

DEFAULT_OUT = TMP / "cron-freshness-spine.json"
DEFAULT_LEDGER = TMP / "cron-operator-ledger.json"
DEFAULT_OPERATING_SPINE = TMP / "operating-leverage-spine.json"
DEFAULT_CONTRACT_DIR = ROOT / "state" / "cron-contracts"
LOCAL_TZ = ZoneInfo("America/Phoenix")

SCHEMA = "veritas.cron_freshness_spine.v1"
SIGNAL_CLASSES = {"NO_REPLY", "MAIN_SESSION_REQUIRED", "BLOCKED", "OWNER_DECISION", "STALE_OR_NOISE"}

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "cron_state_mutation_allowed": False,
    "cron_schedule_mutation_allowed": False,
    "runtime_config_mutation_allowed": False,
    "sql_write_or_import_allowed": False,
    "sql_first_promotion_allowed": False,
    "canon_or_portfolio_mutation_allowed": False,
    "customer_or_external_delivery_allowed": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "owner_approval_inferred": False,
}

EXPECTED_SUSPENDED_WEIGHT_WARNING = (
    "Active portfolio weights plus cash sum to 90.0%; 10% is explicitly suspended legacy model weight "
    "and not active exposure."
)

REVIEW_ONLY_BLOCKED_ROLES = {
    "paper_positions_state",
    "wf84_wf85_full_answer_parity",
    "wf86_guard_readiness",
    "wf86_vrt_get_only_reconciliation",
    "wf87_approval_freshness_ttl",
    "wf87_intraday_monitor",
    "wf87_portfolio_circuit_breakers",
    "wf87_position_sizing_runtime_check",
    "wf85_paper_deployment_notification_digest",
    "wf85_paper_deployment_telegram_cron_runner",
    "morning_paper_deployment_recommendation_cards",
    "wf78_owner_card_prep_loop",
}

CONTEXT_ONLY_ROLES = {
    "cron_control_packet",
    "pm_execution_loop",
}

STATUS_ROUTE_RESIDUE_ROLES = {
    "startup_brief_packet",
    "veritas_status_card",
}

WF78_TIER_SEMANTIC_ROLES = {
    "wf78_clean_tier_roster",
    "wf78_truth_layer_map",
    "wf78_tier_semantics_guard",
}
WF78_AUTO_TIER_ROUTER = TMP / "wf78-auto-tier-routing.json"
ROUTER_IDENTITY_VOLATILE_KEYS = {
    "generated_at",
    "generated_at_utc",
    "completed_at",
    "completed_at_utc",
    "started_at",
    "started_at_utc",
    "duration_ms",
    "elapsed_seconds",
    "age_hours",
    "mtime",
    "mtime_utc",
    "path_mtime_utc",
}


def artifact(path: str, role: str | None = None, required: bool = True, blocking: bool | None = None) -> dict[str, Any]:
    return {
        "path": path,
        "role": role or Path(path).stem,
        "required": required,
        "blocking": required if blocking is None else blocking,
    }


JOB_CONTRACTS: dict[str, dict[str, Any]] = {
    "Cron Reduction - Control Fail-Closed Dispatcher": {
        "owner_workflow": "CRON phase1 control reduction",
        "freshness_hours": 18,
        "expected_artifacts": [
            artifact("tmp/cron-control-digest-runner-control.json", "phase1_control_fail_closed_dispatcher"),
        ],
    },
    "Cron Reduction - Morning Control Digest": {
        "owner_workflow": "CRON phase1 morning control reduction",
        "freshness_hours": 36,
        "expected_artifacts": [
            artifact("tmp/cron-control-digest-runner-morning.json", "phase1_morning_control_digest"),
        ],
    },
    "Cron Reduction - Post-Close Control Digest": {
        "owner_workflow": "CRON phase1 post-close control reduction",
        "freshness_hours": 36,
        "expected_artifacts": [
            artifact("tmp/cron-control-digest-runner-post-close.json", "phase1_post_close_control_digest"),
        ],
    },
    "Memory Dreaming Promotion": {
        "owner_workflow": "WF74/OpenClaw memory-core Dreaming",
        "freshness_hours": 30,
        "expected_artifacts": [
            artifact("tmp/dream-review-packet.json", "openclaw_dreaming_review_packet"),
        ],
    },
    "Memory Dream Review Packet": {
        "owner_workflow": "WF74/OpenClaw memory-core Dreaming review packet",
        "freshness_hours": 30,
        "expected_artifacts": [
            artifact("tmp/dream-review-packet.json", "openclaw_dreaming_review_packet"),
        ],
    },
    "Governance - Monthly Execution Board SQL-First Review": {
        "owner_workflow": "Execution Board SQL-first governance review",
        "freshness_hours": 744,
        "expected_artifacts": [
            artifact("tmp/execution-board-governance-review.json", "execution_board_governance_review"),
        ],
    },
    "Cron - Main Session Auto-Green Watchdog": {
        "owner_workflow": "WF73/WF76 cron oversight",
        "freshness_hours": 18,
        "expected_artifacts": [
            artifact("tmp/cron-operator-ledger.json", "cron_operator_ledger", blocking=False),
            artifact("tmp/main-session-handoff-first-proof.json", "handoff_first_proof_gate", blocking=False),
            artifact("tmp/cron-signal-scorecard.json", "cron_signal_scorecard"),
            artifact("tmp/escalation-trigger.json", "escalation_trigger"),
            artifact("tmp/main-session-escalation-consumer.json", "main_session_escalation_consumer", required=False, blocking=False),
        ],
    },
    "Cron - Main Session Failure and Action Watchdog": {
        "owner_workflow": "WF73/WF76 cron oversight",
        "freshness_hours": 18,
        "expected_artifacts": [
            artifact("tmp/cron-operator-ledger.json", "cron_operator_ledger", blocking=False),
            artifact("tmp/main-session-handoff-first-proof.json", "handoff_first_proof_gate", blocking=False),
            artifact("tmp/cron-signal-scorecard.json", "cron_signal_scorecard"),
            artifact("tmp/escalation-trigger.json", "escalation_trigger"),
            artifact("tmp/main-session-escalation-consumer.json", "main_session_escalation_consumer", required=False, blocking=False),
        ],
    },
    "Cron Spark Canary Review Reminder": {
        "owner_workflow": "cron model canary monitoring",
        "freshness_hours": 96,
        "expected_artifacts": [artifact("tmp/cron-spark-canary-monitor.json", "cron_spark_canary_monitor")],
    },
    "WF74 - Learning Loop Telegram Digest": {
        "owner_workflow": "WF74 recursive self-improvement notification digest",
        "freshness_hours": 30,
        "expected_artifacts": [
            artifact("tmp/wf74-learning-loop-telegram-cron-runner.json", "wf74_learning_loop_telegram_cron_runner"),
            artifact("tmp/wf74-learning-loop-telegram-digest.json", "wf74_learning_loop_telegram_digest"),
            artifact("tmp/wf74-improvement-opportunity-queue.json", "wf74_improvement_opportunity_queue"),
            artifact("tmp/wf74-reflection-to-proposal-autopilot.json", "wf74_reflection_to_proposal_autopilot"),
            artifact("tmp/wf74-auto-patch-proposer.json", "wf74_auto_patch_proposer"),
        ],
    },
    "GPT54mini canary - WF74 Learning Loop Telegram Digest": {
        "owner_workflow": "WF74 recursive self-improvement notification digest model canary",
        "freshness_hours": 30,
        "expected_artifacts": [
            artifact("tmp/wf74-learning-loop-telegram-cron-runner.json", "wf74_learning_loop_telegram_cron_runner"),
            artifact("tmp/wf74-learning-loop-telegram-digest.json", "wf74_learning_loop_telegram_digest"),
            artifact("tmp/wf74-improvement-opportunity-queue.json", "wf74_improvement_opportunity_queue"),
            artifact("tmp/wf74-reflection-to-proposal-autopilot.json", "wf74_reflection_to_proposal_autopilot"),
            artifact("tmp/wf74-auto-patch-proposer.json", "wf74_auto_patch_proposer"),
        ],
    },
    "Finance - Daily Canon Drift Freshness Gate": {
        "owner_workflow": "WF64/WF56 canon drift proof",
        "freshness_hours": 36,
        "expected_artifacts": [artifact("tmp/canon-drift-freshness-gate.json", "canon_drift_gate")],
    },
    "Finance - Main Session Canon Drift Gate Handoff": {
        "owner_workflow": "WF64/WF56 canon drift handoff",
        "freshness_hours": 96,
        "expected_artifacts": [artifact("tmp/canon-drift-freshness-gate.json", "canon_drift_gate")],
    },
    "Finance - Main Session Sunday Weekly Artifact/Note Sync Handoff": {
        "owner_workflow": "Sunday weekly finance handoff",
        "freshness_hours": 192,
        "expected_artifacts": [
            artifact("tmp/run-summary-sunday.json", "sunday_run_summary"),
            artifact("tmp/research-freshness-opportunity-review.json", "research_opportunity_review"),
        ],
    },
    "Finance - Morning Control Digest Proof Refresh": {
        "owner_workflow": "morning control digest",
        "freshness_hours": 36,
        "expected_artifacts": [artifact("tmp/morning-control-digest.json", "morning_control_digest")],
    },
    "Finance - Post-Close Control Digest Consolidated Handoff": {
        "owner_workflow": "post-close control digest",
        "freshness_hours": 36,
        "expected_artifacts": [artifact("tmp/post-close-control-digest.json", "post_close_control_digest")],
    },
    "Finance - Research Freshness and Opportunity Review": {
        "owner_workflow": "WF60/WF61 research freshness",
        "freshness_hours": 36,
        "expected_artifacts": [
            artifact("tmp/promotion-review-queue-reconciler.json", "promotion_review_queue_reconciler"),
            artifact("tmp/research-freshness-opportunity-review.json", "research_opportunity_review"),
        ],
    },
    "Finance - Sector Allocation Decision Matrix": {
        "owner_workflow": "sector allocation matrix",
        "freshness_hours": 36,
        "expected_artifacts": [
            artifact("tmp/sector-allocation-decision-matrix-cron-runner.json", "sector_allocation_decision_matrix_cron_runner"),
            artifact("tmp/sector-allocation-decision-matrix.json", "sector_allocation_matrix"),
        ],
    },
    "GPT54mini canary - Sector Allocation Decision Matrix": {
        "owner_workflow": "sector allocation matrix model canary",
        "freshness_hours": 36,
        "expected_artifacts": [artifact("tmp/sector-allocation-decision-matrix.json", "sector_allocation_matrix")],
    },
    "Finance - Sunday Generated Artifact Cleanup Dry Run": {
        "owner_workflow": "WF72 cleanup dry-run proof",
        "freshness_hours": 192,
        "expected_artifacts": [artifact("tmp/tmp-cleanup-report.json", "tmp_cleanup_report")],
    },
    "Finance - Sunday Research Opportunity Reset": {
        "owner_workflow": "WF60/WF61 Sunday research reset",
        "freshness_hours": 192,
        "expected_artifacts": [
            artifact("tmp/sunday-research-opportunity-reset-cron-runner.json", "sunday_research_opportunity_reset_cron_runner"),
            artifact("tmp/promotion-review-queue-reconciler.json", "promotion_review_queue_reconciler"),
            artifact("tmp/research-freshness-opportunity-review.json", "research_opportunity_review"),
        ],
    },
    "Finance - Sunday Weekly Printable Intelligence Refresh": {
        "owner_workflow": "Sunday weekly finance refresh",
        "freshness_hours": 192,
        "expected_artifacts": [
            artifact("tmp/run-summary-sunday.json", "sunday_run_summary"),
            artifact("tmp/earnings-rollforward-guard.json", "earnings_rollforward_guard"),
        ],
    },
    "Finance - Weekday Morning Review Refresh": {
        "owner_workflow": "weekday morning finance chain",
        "freshness_hours": 36,
        "expected_artifacts": [
            artifact("tmp/weekday-morning-review-cron-launcher.json", "weekday_morning_review_cron_launcher", required=False, blocking=False),
            artifact("tmp/weekday-morning-review-cron-runner.json", "weekday_morning_review_cron_runner"),
            artifact("tmp/run-summary-morning.json", "morning_run_summary"),
            artifact("tmp/run-chain-morning.json", "morning_run_chain"),
            artifact("tmp/earnings-rollforward-guard.json", "earnings_rollforward_guard"),
        ],
    },
    "GPT54mini canary - Weekday Morning Review Refresh": {
        "owner_workflow": "weekday morning finance chain model canary",
        "freshness_hours": 36,
        "expected_artifacts": [
            artifact("tmp/weekday-morning-review-cron-launcher.json", "weekday_morning_review_cron_launcher", required=False, blocking=False),
            artifact("tmp/weekday-morning-review-cron-runner.json", "weekday_morning_review_cron_runner"),
            artifact("tmp/run-summary-morning.json", "morning_run_summary"),
            artifact("tmp/run-chain-morning.json", "morning_run_chain"),
        ],
    },
    "Finance - Layered Morning Advancement Audit": {
        "owner_workflow": "WF73/WF76 layered finance advancement proof",
        "freshness_hours": 36,
        "expected_artifacts": [
            artifact("tmp/layered-finance-cron-pilot-runner.json", "layered_finance_cron_pilot_runner"),
            artifact("tmp/layered-finance-refresh-chain-plan-morning.json", "layered_morning_read_only_plan"),
            artifact("tmp/workflow-advancement-scorecard.json", "workflow_advancement_scorecard"),
        ],
    },
    "Finance - Layered Post-Close Advancement Audit": {
        "owner_workflow": "WF73/WF76 layered finance advancement proof",
        "freshness_hours": 36,
        "expected_artifacts": [
            artifact("tmp/layered-finance-cron-pilot-runner.json", "layered_finance_cron_pilot_runner"),
            artifact("tmp/layered-finance-refresh-chain-plan-post-close.json", "layered_post_close_read_only_plan"),
            artifact("tmp/workflow-advancement-scorecard.json", "workflow_advancement_scorecard"),
        ],
    },
    "Finance - Morning Paper Deployment Recommendation Cards": {
        "owner_workflow": "WF78/WF67 morning paper recommendation cards",
        "freshness_hours": 36,
        "expected_artifacts": [
            artifact("tmp/morning-paper-deployment-recommendation-cards.json", "morning_paper_deployment_recommendation_cards"),
            artifact("tmp/intraday-alerts/quote-snapshot-proof.json", "wf68_quote_snapshot_proof"),
            artifact("tmp/market-execution-readiness-cron-hardening.json", "market_execution_readiness_cron_hardening"),
            artifact("tmp/band-hygiene-freshness-controller.json", "band_hygiene_freshness_controller"),
            artifact("tmp/wf78-capital-review-queue.json", "wf78_capital_review_queue"),
            artifact("tmp/wf78-owner-card-prep-loop.json", "wf78_owner_card_prep_loop"),
            artifact("tmp/finance-decision-factory.json", "finance_decision_factory"),
            artifact("tmp/finance-decision-sync-spine.json", "finance_decision_sync_spine"),
            artifact("tmp/veritas-finance-brief.json", "veritas_finance_brief"),
            artifact("tmp/veritas-finance-brief.md", "veritas_finance_brief_md", required=False, blocking=False),
        ],
    },
    "Finance - Midday Paper Deployment Recommendation Cards": {
        "owner_workflow": "WF78/WF67 midday paper recommendation cards",
        "freshness_hours": 18,
        "expected_artifacts": [
            artifact("tmp/morning-paper-deployment-recommendation-cards.json", "morning_paper_deployment_recommendation_cards"),
            artifact("tmp/intraday-alerts/quote-snapshot-proof.json", "wf68_quote_snapshot_proof"),
            artifact("tmp/market-execution-readiness-cron-hardening.json", "market_execution_readiness_cron_hardening"),
            artifact("tmp/band-hygiene-freshness-controller.json", "band_hygiene_freshness_controller"),
            artifact("tmp/wf78-capital-review-queue.json", "wf78_capital_review_queue"),
            artifact("tmp/wf78-owner-card-prep-loop.json", "wf78_owner_card_prep_loop"),
            artifact("tmp/finance-decision-factory.json", "finance_decision_factory"),
            artifact("tmp/finance-decision-sync-spine.json", "finance_decision_sync_spine"),
            artifact("tmp/veritas-finance-brief.json", "veritas_finance_brief"),
            artifact("tmp/veritas-finance-brief.md", "veritas_finance_brief_md", required=False, blocking=False),
        ],
    },
    "Finance - Open-Ready Paper Deployment Recommendation Cards": {
        "owner_workflow": "WF78/WF67 open-ready paper recommendation cards",
        "freshness_hours": 36,
        "expected_artifacts": [
            artifact("tmp/morning-paper-deployment-recommendation-cards.json", "morning_paper_deployment_recommendation_cards"),
            artifact("tmp/intraday-alerts/quote-snapshot-proof.json", "wf68_quote_snapshot_proof"),
            artifact("tmp/market-execution-readiness-cron-hardening.json", "market_execution_readiness_cron_hardening"),
            artifact("tmp/band-hygiene-freshness-controller.json", "band_hygiene_freshness_controller"),
            artifact("tmp/wf78-capital-review-queue.json", "wf78_capital_review_queue"),
            artifact("tmp/wf78-owner-card-prep-loop.json", "wf78_owner_card_prep_loop"),
            artifact("tmp/finance-decision-factory.json", "finance_decision_factory"),
            artifact("tmp/finance-decision-sync-spine.json", "finance_decision_sync_spine"),
            artifact("tmp/veritas-finance-brief.json", "veritas_finance_brief"),
            artifact("tmp/veritas-finance-brief.md", "veritas_finance_brief_md", required=False, blocking=False),
        ],
    },
    "Finance - WF85 Paper Deployment Telegram Radar": {
        "owner_workflow": "WF85/WF67 paper deployment notification radar",
        "freshness_hours": 18,
        "expected_artifacts": [
            artifact("tmp/wf85-paper-deployment-telegram-cron-runner.json", "wf85_paper_deployment_telegram_cron_runner"),
            artifact("tmp/wf85-paper-deployment-notification-digest.json", "wf85_paper_deployment_notification_digest"),
            artifact("tmp/wf85-paper-deployment-telegram-notifier.json", "wf85_paper_deployment_telegram_notifier"),
            artifact("tmp/trade-grade-os-freshness-cron-runner.json", "trade_grade_os_freshness_cron_runner", blocking=False),
            artifact("tmp/trade-grade-decision-card-authority-validation.json", "wf85_authority_validation"),
            artifact("tmp/trade-grade-approval-card-gate.json", "wf85_approval_card_gate"),
            artifact("tmp/morning-paper-deployment-recommendation-cards.json", "morning_paper_deployment_recommendation_cards"),
            artifact("tmp/alpaca-paper-readiness/wf67-autonomous-paper-manager-current.json", "wf67_autonomous_paper_manager"),
            artifact("tmp/alpaca-paper-readiness/paper-execution-guard-validation.json", "wf67_paper_execution_guard_validation", blocking=False),
            artifact("tmp/finance-decision-sync-spine.json", "finance_decision_sync_spine"),
            artifact("tmp/veritas-finance-brief.json", "veritas_finance_brief"),
            artifact("tmp/veritas-finance-brief.md", "veritas_finance_brief_md", required=False, blocking=False),
        ],
    },
    "Finance - WF85 Post-Refresh Paper Deployment Telegram Radar": {
        "owner_workflow": "WF85/WF67 paper deployment notification radar",
        "freshness_hours": 12,
        "expected_artifacts": [
            artifact("tmp/wf85-paper-deployment-telegram-cron-runner.json", "wf85_paper_deployment_telegram_cron_runner"),
            artifact("tmp/wf85-paper-deployment-notification-digest.json", "wf85_paper_deployment_notification_digest"),
            artifact("tmp/wf85-paper-deployment-telegram-notifier.json", "wf85_paper_deployment_telegram_notifier"),
            artifact("tmp/trade-grade-os-freshness-cron-runner.json", "trade_grade_os_freshness_cron_runner", blocking=False),
            artifact("tmp/trade-grade-decision-card-authority-validation.json", "wf85_authority_validation"),
            artifact("tmp/trade-grade-approval-card-gate.json", "wf85_approval_card_gate"),
            artifact("tmp/morning-paper-deployment-recommendation-cards.json", "morning_paper_deployment_recommendation_cards"),
            artifact("tmp/alpaca-paper-readiness/wf67-autonomous-paper-manager-current.json", "wf67_autonomous_paper_manager"),
            artifact("tmp/alpaca-paper-readiness/paper-execution-guard-validation.json", "wf67_paper_execution_guard_validation", blocking=False),
            artifact("tmp/finance-decision-sync-spine.json", "finance_decision_sync_spine"),
            artifact("tmp/veritas-finance-brief.json", "veritas_finance_brief"),
            artifact("tmp/veritas-finance-brief.md", "veritas_finance_brief_md", required=False, blocking=False),
        ],
    },
    "Finance - WF85 Open-Ready Telegram Radar": {
        "owner_workflow": "WF85/WF67 open-ready paper deployment notification radar",
        "freshness_hours": 18,
        "expected_artifacts": [
            artifact("tmp/wf85-paper-deployment-telegram-cron-runner.json", "wf85_paper_deployment_telegram_cron_runner"),
            artifact("tmp/wf85-paper-deployment-notification-digest.json", "wf85_paper_deployment_notification_digest"),
            artifact("tmp/wf85-paper-deployment-telegram-notifier.json", "wf85_paper_deployment_telegram_notifier"),
            artifact("tmp/trade-grade-os-freshness-cron-runner.json", "trade_grade_os_freshness_cron_runner", blocking=False),
            artifact("tmp/trade-grade-decision-card-authority-validation.json", "wf85_authority_validation"),
            artifact("tmp/trade-grade-approval-card-gate.json", "wf85_approval_card_gate"),
            artifact("tmp/morning-paper-deployment-recommendation-cards.json", "morning_paper_deployment_recommendation_cards"),
            artifact("tmp/alpaca-paper-readiness/wf67-autonomous-paper-manager-current.json", "wf67_autonomous_paper_manager"),
            artifact("tmp/alpaca-paper-readiness/paper-execution-guard-validation.json", "wf67_paper_execution_guard_validation", blocking=False),
            artifact("tmp/finance-decision-sync-spine.json", "finance_decision_sync_spine"),
            artifact("tmp/veritas-finance-brief.json", "veritas_finance_brief"),
            artifact("tmp/veritas-finance-brief.md", "veritas_finance_brief_md", required=False, blocking=False),
        ],
    },
    "Finance - WF86 Daily Shadow and Paper Reconciliation": {
        "owner_workflow": "WF86 paper autotrader shadow/reconciliation proof",
        "freshness_hours": 36,
        "expected_artifacts": [
            artifact("tmp/paper-autotrader/wf86-daily-shadow-reconciliation-cron-runner.json", "wf86_daily_shadow_reconciliation_runner"),
            artifact("tmp/paper-autotrader/shadow-eligibility.json", "wf86_shadow_eligibility"),
            artifact("tmp/paper-autotrader/assisted-order-cards.json", "wf86_assisted_order_cards", required=False, blocking=False),
            artifact("tmp/paper-autotrader/shadow-decisions.json", "wf86_shadow_decision_ledger"),
            artifact("tmp/paper-autotrader/autotrader-readiness.json", "wf86_autotrader_readiness"),
            artifact("tmp/paper-autotrader/guard-readiness.json", "wf86_guard_readiness", blocking=False),
            artifact("tmp/alpaca-paper-readiness/paper-order-reconciliation.vrt-wf86-assisted-approved.json", "wf86_vrt_get_only_reconciliation"),
            artifact("tmp/alpaca-paper-readiness/paper-order-history-classifier.json", "wf86_all_submitted_order_history_classifier"),
            artifact("tmp/trade-grade-os-readiness-rollup.json", "trade_grade_os_readiness_rollup"),
            artifact("tmp/paper-autotrader/trade-decision-journal.jsonl", "wf87_trade_decision_journal", required=False, blocking=False),
            artifact("tmp/wf87-position-sizing-runtime-check.json", "wf87_position_sizing_runtime_check"),
            artifact("tmp/wf87-portfolio-circuit-breakers.json", "wf87_portfolio_circuit_breakers"),
            artifact("tmp/wf87-approval-freshness-ttl.json", "wf87_approval_freshness_ttl"),
            artifact("tmp/wf87-intraday-monitor.json", "wf87_intraday_monitor"),
            artifact("tmp/wf87-assisted-paper-cadence.json", "wf87_assisted_paper_cadence"),
            artifact("tmp/wf87-shadow-outcome-scorecard.json", "wf87_shadow_outcome_scorecard"),
            artifact("tmp/wf87-market-hours-gate-probe.json", "wf87_market_hours_gate_probe", required=False, blocking=False),
            artifact("tmp/wf87-v2-readiness-rollup.json", "wf87_v2_readiness_rollup"),
            artifact("tmp/wf87-autonomy-command-center.json", "wf87_autonomy_command_center"),
            artifact("tmp/autonomous-routing-deployment-cards.json", "autonomous_routing_deployment_cards"),
            artifact("tmp/autonomous-card-authority-audit.json", "autonomous_card_authority_audit"),
        ],
    },
    "Finance - WF87 Market-Hours Fresh Gate Probe": {
        "owner_workflow": "WF87 V2 market-hours gate proof",
        "freshness_hours": 12,
        "expected_artifacts": [
            artifact("tmp/wf87-market-hours-gate-probe.json", "wf87_market_hours_gate_probe"),
            artifact("tmp/wf87-position-sizing-runtime-check.json", "wf87_position_sizing_runtime_check"),
            artifact("tmp/wf87-portfolio-circuit-breakers.json", "wf87_portfolio_circuit_breakers"),
            artifact("tmp/wf87-approval-freshness-ttl.json", "wf87_approval_freshness_ttl"),
            artifact("tmp/wf87-intraday-monitor.json", "wf87_intraday_monitor"),
            artifact("tmp/wf87-shadow-outcome-scorecard.json", "wf87_shadow_outcome_scorecard"),
            artifact("tmp/wf87-v2-readiness-rollup.json", "wf87_v2_readiness_rollup"),
            artifact("tmp/autonomous-routing-deployment-cards.json", "autonomous_routing_deployment_cards"),
            artifact("tmp/autonomous-card-authority-audit.json", "autonomous_card_authority_audit"),
        ],
    },
    "Finance - WF87 Autonomy Command Center Refresh": {
        "owner_workflow": "WF87 V2 autonomy command center",
        "freshness_hours": 12,
        "expected_artifacts": [
            artifact("tmp/wf87-autonomy-command-center.json", "wf87_autonomy_command_center"),
            artifact("tmp/wf87-v2-readiness-rollup.json", "wf87_v2_readiness_rollup"),
            artifact("tmp/paper-autotrader/assisted-order-cards.json", "wf86_assisted_order_cards", required=False, blocking=False),
            artifact("tmp/wf87-market-hours-gate-probe.json", "wf87_market_hours_gate_probe"),
            artifact("tmp/wf87-shadow-outcome-scorecard.json", "wf87_shadow_outcome_scorecard"),
            artifact("tmp/wf87-assisted-paper-cadence.json", "wf87_assisted_paper_cadence"),
            artifact("tmp/wf85-deployment-timing-gate.json", "wf85_deployment_timing_gate"),
            artifact("tmp/morning-paper-deployment-recommendation-cards.json", "morning_paper_deployment_recommendation_cards"),
            artifact("tmp/autonomous-routing-deployment-cards.json", "autonomous_routing_deployment_cards"),
            artifact("tmp/autonomous-card-authority-audit.json", "autonomous_card_authority_audit"),
        ],
    },
    "Finance - Autonomy Spine Readiness Rollup": {
        "owner_workflow": "WF55/WF71/WF74/WF76 autonomy spine measurement and cadence proof",
        "freshness_hours": 18,
        "expected_artifacts": [
            artifact("tmp/autonomy-spine-promotion-contract.json", "autonomy_spine_promotion_contract"),
            artifact("tmp/wf55-autonomy-outcome-ledger.json", "wf55_autonomy_outcome_ledger"),
            artifact("tmp/autonomy-spine-readiness-rollup.json", "autonomy_spine_readiness_rollup"),
            artifact("tmp/workflow-advancement-scorecard.json", "workflow_advancement_scorecard"),
        ],
    },
    "Finance - Silent Tier A Intraday Market Readiness Probe": {
        "owner_workflow": "WF78/WF84/WF85/WF87 silent market-readiness producer",
        "freshness_hours": 12,
        "expected_artifacts": [
            artifact("tmp/finance-market-deployment-operating-loop.json", "finance_market_deployment_operating_loop", blocking=False),
            artifact("tmp/finance-market-deployment-operating-loop.md", "finance_market_deployment_operating_loop_md", required=False, blocking=False),
            artifact("tmp/tier-a-intraday-opportunity-probe.json", "tier_a_intraday_opportunity_probe"),
            artifact("tmp/market-execution-readiness-cron-hardening.json", "market_execution_readiness_cron_hardening"),
        ],
    },
    "Finance - Silent Tier A Confirmation Market Readiness Probe": {
        "owner_workflow": "WF78/WF84/WF85/WF87 silent market-readiness producer",
        "freshness_hours": 12,
        "expected_artifacts": [
            artifact("tmp/finance-market-deployment-operating-loop.json", "finance_market_deployment_operating_loop", blocking=False),
            artifact("tmp/finance-market-deployment-operating-loop.md", "finance_market_deployment_operating_loop_md", required=False, blocking=False),
            artifact("tmp/tier-a-intraday-opportunity-probe.json", "tier_a_intraday_opportunity_probe"),
            artifact("tmp/market-execution-readiness-cron-hardening.json", "market_execution_readiness_cron_hardening"),
        ],
    },
    "Finance - Silent Tier A Late-Session Market Readiness Probe": {
        "owner_workflow": "WF78/WF84/WF85/WF87 silent market-readiness producer",
        "freshness_hours": 12,
        "expected_artifacts": [
            artifact("tmp/finance-market-deployment-operating-loop.json", "finance_market_deployment_operating_loop", blocking=False),
            artifact("tmp/finance-market-deployment-operating-loop.md", "finance_market_deployment_operating_loop_md", required=False, blocking=False),
            artifact("tmp/tier-a-intraday-opportunity-probe.json", "tier_a_intraday_opportunity_probe"),
            artifact("tmp/market-execution-readiness-cron-hardening.json", "market_execution_readiness_cron_hardening"),
        ],
    },
    "Finance - Tier A Intraday Opportunity Probe": {
        "owner_workflow": "WF85/WF68/WF87 Tier A intraday opportunity probe",
        "freshness_hours": 12,
        "expected_artifacts": [
            artifact("tmp/finance-market-deployment-operating-loop.json", "finance_market_deployment_operating_loop"),
            artifact("tmp/tier-a-intraday-opportunity-probe.json", "tier_a_intraday_opportunity_probe"),
            artifact("tmp/intraday-alerts/current-alerts.json", "wf68_current_intraday_alerts"),
            artifact("tmp/intraday-alerts/runtime-handoff-status.json", "wf68_runtime_handoff"),
            artifact("tmp/intraday-alerts/quote-snapshot-proof.json", "wf68_quote_snapshot_proof"),
            artifact("tmp/wf87-intraday-monitor.json", "wf87_intraday_monitor"),
            artifact("tmp/wf85-paper-deployment-notification-digest.json", "wf85_paper_deployment_notification_digest"),
            artifact("tmp/wf78-auto-tier-routing.json", "wf78_auto_tier_router"),
            artifact("tmp/wf85-deployment-timing-gate.json", "wf85_deployment_timing_gate"),
            artifact("tmp/autonomous-routing-deployment-cards.json", "autonomous_routing_deployment_cards"),
            artifact("tmp/autonomous-card-authority-audit.json", "autonomous_card_authority_audit"),
        ],
    },
    "Finance - Tier A Confirmation Opportunity Probe": {
        "owner_workflow": "WF85/WF68/WF87 Tier A confirmation opportunity probe",
        "freshness_hours": 12,
        "expected_artifacts": [
            artifact("tmp/finance-market-deployment-operating-loop.json", "finance_market_deployment_operating_loop"),
            artifact("tmp/tier-a-intraday-opportunity-probe.json", "tier_a_intraday_opportunity_probe"),
            artifact("tmp/intraday-alerts/current-alerts.json", "wf68_current_intraday_alerts"),
            artifact("tmp/intraday-alerts/runtime-handoff-status.json", "wf68_runtime_handoff"),
            artifact("tmp/intraday-alerts/quote-snapshot-proof.json", "wf68_quote_snapshot_proof"),
            artifact("tmp/wf87-intraday-monitor.json", "wf87_intraday_monitor"),
            artifact("tmp/wf85-paper-deployment-notification-digest.json", "wf85_paper_deployment_notification_digest"),
            artifact("tmp/wf78-auto-tier-routing.json", "wf78_auto_tier_router"),
            artifact("tmp/wf85-deployment-timing-gate.json", "wf85_deployment_timing_gate"),
            artifact("tmp/autonomous-routing-deployment-cards.json", "autonomous_routing_deployment_cards"),
            artifact("tmp/autonomous-card-authority-audit.json", "autonomous_card_authority_audit"),
        ],
    },
    "Finance - Tier A Late-Session Opportunity Probe": {
        "owner_workflow": "WF85/WF68/WF87 Tier A intraday opportunity probe",
        "freshness_hours": 12,
        "expected_artifacts": [
            artifact("tmp/tier-a-late-session-opportunity-cron-runner.json", "tier_a_late_session_opportunity_cron_runner"),
            artifact("tmp/finance-market-deployment-operating-loop.json", "finance_market_deployment_operating_loop"),
            artifact("tmp/tier-a-intraday-opportunity-probe.json", "tier_a_intraday_opportunity_probe"),
            artifact("tmp/intraday-alerts/current-alerts.json", "wf68_current_intraday_alerts"),
            artifact("tmp/intraday-alerts/runtime-handoff-status.json", "wf68_runtime_handoff"),
            artifact("tmp/intraday-alerts/quote-snapshot-proof.json", "wf68_quote_snapshot_proof"),
            artifact("tmp/wf87-intraday-monitor.json", "wf87_intraday_monitor"),
            artifact("tmp/wf85-paper-deployment-notification-digest.json", "wf85_paper_deployment_notification_digest"),
            artifact("tmp/wf78-auto-tier-routing.json", "wf78_auto_tier_router"),
            artifact("tmp/wf85-deployment-timing-gate.json", "wf85_deployment_timing_gate"),
            artifact("tmp/autonomous-routing-deployment-cards.json", "autonomous_routing_deployment_cards"),
            artifact("tmp/autonomous-card-authority-audit.json", "autonomous_card_authority_audit"),
        ],
    },
    "Finance - Ticker Card Freshness Owner Runner": {
        "owner_workflow": "WF77/WF78 ticker-card freshness owner runner",
        "freshness_hours": 36,
        "expected_artifacts": [
            artifact("tmp/ticker-card-freshness-owner-runner.json", "ticker_card_freshness_owner_runner"),
            artifact("tmp/trade-grade-os-freshness-cron-runner.json", "trade_grade_os_freshness_cron_runner"),
            artifact("tmp/wf78-missing-band-context-repair.json", "wf78_missing_band_context_repair"),
            artifact("tmp/tier-ab-band-freshness-cron-guard.json", "tier_ab_band_freshness_cron_guard"),
            artifact("tmp/position-sizing-readiness-current.json", "position_sizing_readiness_current"),
            artifact("tmp/finance-ticker-card-refresh-gate.json", "finance_ticker_card_refresh_gate"),
            artifact("tmp/finance-data-coverage-current.json", "finance_data_coverage"),
            artifact("tmp/earnings-rollforward-guard.json", "earnings_rollforward_guard"),
        ],
    },
    "Finance - Weekday Post-Close Review Refresh": {
        "owner_workflow": "weekday post-close finance chain",
        "freshness_hours": 36,
        "expected_artifacts": [
            artifact("tmp/post-close-review-cron-runner.json", "post_close_review_cron_runner"),
            artifact("tmp/run-summary-post-close.json", "post_close_run_summary"),
            artifact("tmp/run-chain-post-close.json", "post_close_run_chain"),
            artifact("tmp/post-close-final-quote-ledger.json", "post_close_final_quote_ledger"),
            artifact("tmp/ticker-card-freshness-owner-runner.json", "ticker_card_freshness_owner_runner"),
            artifact("tmp/wf78-capital-review-queue.json", "wf78_capital_review_queue"),
            artifact("tmp/finance-decision-factory.json", "finance_decision_factory"),
            artifact("tmp/finance-decision-sync-spine.json", "finance_decision_sync_spine"),
            artifact("tmp/veritas-finance-brief.json", "veritas_finance_brief"),
            artifact("tmp/veritas-finance-brief.md", "veritas_finance_brief_md", required=False, blocking=False),
            artifact("tmp/market-today-answer-packet.json", "market_today_answer_packet"),
            artifact("tmp/earnings-rollforward-guard.json", "earnings_rollforward_guard"),
        ],
    },
    "Finance - WF63/WF67 Paper Position Read-Only Refresh": {
        "owner_workflow": "WF63/WF67 paper read-only position proof",
        "freshness_hours": 36,
        "expected_artifacts": [
            artifact("tmp/alpaca-paper-readiness/paper-position-refresh-cron-runner.json", "paper_position_runner"),
            artifact("tmp/finance-intelligence-state-paper-positions.json", "paper_positions_state"),
        ],
    },
    "Finance - WF68 Grouped Alert Digest Handoff": {
        "owner_workflow": "WF68 grouped alert digest",
        "freshness_hours": 24,
        "expected_artifacts": [
            artifact("tmp/intraday-alerts/delivery-router-status.json", "wf68_delivery_router"),
            artifact("tmp/intraday-alerts/runtime-handoff-status.json", "wf68_runtime_handoff"),
        ],
    },
    "Finance - WF68 Intraday Alert Producer": {
        "owner_workflow": "WF68 intraday alert producer",
        "freshness_hours": 24,
        "expected_artifacts": [
            artifact("tmp/intraday-alerts/runtime-handoff-status.json", "wf68_runtime_handoff"),
            artifact("tmp/intraday-alerts/quote-snapshot-proof.json", "wf68_quote_snapshot_proof"),
            artifact("tmp/market-execution-readiness-cron-hardening.json", "market_execution_readiness_cron_hardening"),
        ],
    },
    "Finance - WF78 Daily Freshness and Promotion Proof": {
        "owner_workflow": "WF78 daily freshness and promotion proof",
        "freshness_hours": 30,
        "expected_artifacts": [
            artifact("tmp/wf78-intelligence-routing-v2.json", "wf78_intelligence_routing_v2"),
            artifact("tmp/wf78-daily-movement-ledger.json", "wf78_daily_movement_ledger"),
            artifact("tmp/wf78-repair-priority-queue.json", "wf78_repair_priority_queue"),
            artifact("tmp/wf78-daily-freshness-loop.json", "wf78_daily_freshness_loop"),
            artifact("tmp/wf78-auto-tier-routing.json", "wf78_auto_tier_router"),
            artifact("tmp/wf78-tier-c-attention-trigger.json", "wf78_tier_c_attention_trigger"),
            artifact("tmp/wf78-tier-c-hold-recheck.json", "wf78_tier_c_hold_recheck"),
            artifact("tmp/wf78-tier-c-to-b-auto-promotion-pipeline.json", "wf78_tier_c_to_b_auto_promotion_pipeline"),
            artifact("tmp/wf78-tier-c-attention-evidence-repair-bridge.json", "wf78_tier_c_attention_evidence_repair_bridge"),
            artifact("tmp/wf78-clean-tier-roster.json", "wf78_clean_tier_roster"),
            artifact("tmp/wf78-truth-layer-map.json", "wf78_truth_layer_map"),
            artifact("tmp/wf78-tier-semantics-guard.json", "wf78_tier_semantics_guard"),
            artifact("tmp/wf78-routing-delta.json", "wf78_routing_delta"),
            artifact("tmp/wf78-tier-b-research-packets.json", "wf78_tier_b_research_packets"),
            artifact("tmp/wf78-tier-b-research-packet-requests.json", "wf78_tier_b_research_packet_requests"),
            artifact("tmp/wf78-tier-b-research-packet-phase2-eval.json", "wf78_tier_b_research_packet_phase2_eval"),
            artifact("tmp/wf78-tier-a-competitive-promotion-gate.json", "wf78_tier_a_competitive_promotion_gate"),
            artifact("tmp/wf78-tier-weighted-freshness-resolution.json", "wf78_tier_weighted_freshness_resolution"),
            artifact("tmp/wf78-ticker-freshness-ledger.json", "wf78_ticker_freshness_ledger"),
            artifact("tmp/tier-c-band-status.json", "tier_c_band_status"),
            artifact("tmp/wf78-source-capture-requirements-queue.json", "wf78_source_capture_requirements_queue"),
            artifact("tmp/wf78-official-source-discovery.json", "wf78_official_source_discovery"),
            artifact("tmp/wf78-official-registry-proposal.json", "wf78_official_registry_proposal"),
            artifact("tmp/wf78-official-registry-apply-preview.json", "wf78_official_registry_apply_preview"),
            artifact("tmp/wf78-promotion-owner-lineage-queue.json", "wf78_promotion_owner_lineage_queue"),
            artifact("tmp/wf78-contract-state-guard.json", "wf78_contract_state_guard"),
            artifact("tmp/wf78-owner-lineage-discovery.json", "wf78_owner_lineage_discovery"),
            artifact("tmp/wf78-owner-lineage-proposal.json", "wf78_owner_lineage_proposal"),
            artifact("tmp/wf78-official-source-capture-packet.json", "wf78_official_source_capture_packet"),
            artifact("tmp/wf78-next-owner-review-and-source-capture-integration.json", "wf78_next_owner_review_and_source_capture_integration"),
            artifact("tmp/market-execution-readiness-cron-hardening.json", "market_execution_readiness_cron_hardening"),
            artifact("tmp/finance-decision-factory.json", "finance_decision_factory"),
            artifact("tmp/post-close-final-quote-ledger.json", "post_close_final_quote_ledger"),
            artifact("tmp/canonical-finance-data-plane.json", "wf84_canonical_finance_data_plane"),
            artifact("tmp/canonical-finance-data-plane-validation.json", "wf84_canonical_finance_data_plane_validation"),
            artifact("tmp/canonical-finance-data-plane.sqlite", "wf84_canonical_finance_data_plane_sqlite"),
            artifact("tmp/canonical-finance-data-plane-phase6-10.json", "wf84_phase6_10_proof"),
            artifact("tmp/canonical-finance-data-plane-retirement-readiness.json", "wf84_retirement_readiness"),
            artifact("tmp/full-answer-parity/full-answer-parity-rollup.json", "wf84_wf85_full_answer_parity"),
            artifact("tmp/trade-grade-os-freshness-cron-runner.json", "trade_grade_os_freshness_cron_runner"),
            artifact("tmp/wf78-missing-band-context-repair.json", "wf78_missing_band_context_repair"),
            artifact("tmp/tier-ab-band-freshness-cron-guard.json", "tier_ab_band_freshness_cron_guard"),
            artifact("tmp/trade-grade-source-freshness-gate.json", "wf85_source_freshness_gate"),
            artifact("tmp/trade-grade-decision-cards.json", "wf85_decision_cards"),
            artifact("tmp/trade-grade-decision-card-authority-validation.json", "wf85_authority_validation"),
            artifact("tmp/trade-grade-approval-card-gate.json", "wf85_approval_card_gate"),
            artifact("tmp/trade-grade-risk-sizing-overlay.json", "wf85_risk_sizing_overlay"),
            artifact("tmp/trade-grade-repair-conveyor.json", "wf85_repair_conveyor"),
            artifact("tmp/wf78-position-sizing-surface-review.json", "wf78_position_sizing_surface_review"),
            artifact("tmp/wf78-deployment-readiness-review.json", "wf78_deployment_readiness_review"),
            artifact("tmp/wf78-source-artifact-capture-review.json", "wf78_source_artifact_capture_review"),
            artifact("tmp/wf78-position-sizing-integration-proposal.json", "wf78_position_sizing_integration_proposal"),
            artifact("tmp/wf78-tier-a-owner-readiness-proposals.json", "wf78_tier_a_owner_readiness_proposals"),
        ],
    },
    "Finance - WF78 Opportunity Refresh Controller": {
        "owner_workflow": "WF78/WF84/WF85 opportunity refresh and promotion visibility top-10",
        "freshness_hours": 30,
        "expected_artifacts": [
            artifact("tmp/wf78-opportunity-refresh-controller.json", "wf78_opportunity_refresh_controller"),
            artifact("tmp/wf78-opportunity-visibility-queue.json", "wf78_opportunity_visibility_queue"),
            artifact("tmp/wf78-promotion-visibility-top10.json", "wf78_promotion_visibility_top10"),
            artifact("tmp/wf78-tier-b-research-packets.json", "wf78_tier_b_research_packets"),
            artifact("tmp/wf78-tier-b-research-packet-requests.json", "wf78_tier_b_research_packet_requests"),
            artifact("tmp/wf78-tier-b-research-packets.sqlite", "wf78_tier_b_research_packets_sqlite"),
            artifact("tmp/wf78-tier-c-to-b-auto-promotion-pipeline.json", "wf78_tier_c_to_b_auto_promotion_pipeline"),
            artifact("tmp/wf78-tier-c-to-b-auto-promotion-pipeline.closeout.json", "wf78_tier_c_to_b_auto_promotion_pipeline_closeout"),
            artifact("tmp/wf85-opportunity-visibility-queue.json", "wf85_opportunity_visibility_queue"),
            artifact("tmp/finance-decision-factory.json", "finance_decision_factory"),
            artifact("tmp/finance-market-deployment-operating-loop.json", "finance_market_deployment_operating_loop"),
        ],
    },
    "GPT54mini canary - WF78 Daily Freshness and Promotion Proof": {
        "owner_workflow": "WF78 daily freshness and promotion proof model canary",
        "freshness_hours": 30,
        "expected_artifacts": [
            artifact("tmp/wf78-daily-freshness-cron-runner.json", "wf78_daily_freshness_cron_runner", required=False, blocking=False),
            artifact("tmp/wf78-daily-freshness-loop.json", "wf78_daily_freshness_loop"),
            artifact("tmp/wf78-auto-tier-routing.json", "wf78_auto_tier_router"),
            artifact("tmp/wf78-tier-c-attention-trigger.json", "wf78_tier_c_attention_trigger"),
            artifact("tmp/wf78-tier-c-hold-recheck.json", "wf78_tier_c_hold_recheck"),
            artifact("tmp/wf78-tier-c-to-b-auto-promotion-pipeline.json", "wf78_tier_c_to_b_auto_promotion_pipeline"),
            artifact("tmp/wf78-tier-c-attention-evidence-repair-bridge.json", "wf78_tier_c_attention_evidence_repair_bridge"),
            artifact("tmp/wf78-clean-tier-roster.json", "wf78_clean_tier_roster"),
            artifact("tmp/wf78-truth-layer-map.json", "wf78_truth_layer_map"),
            artifact("tmp/wf78-tier-semantics-guard.json", "wf78_tier_semantics_guard"),
            artifact("tmp/wf78-routing-delta.json", "wf78_routing_delta"),
            artifact("tmp/wf78-tier-b-research-packets.json", "wf78_tier_b_research_packets"),
            artifact("tmp/wf78-tier-b-research-packet-requests.json", "wf78_tier_b_research_packet_requests"),
            artifact("tmp/wf78-tier-b-research-packet-phase2-eval.json", "wf78_tier_b_research_packet_phase2_eval"),
            artifact("tmp/wf78-tier-a-competitive-promotion-gate.json", "wf78_tier_a_competitive_promotion_gate"),
            artifact("tmp/wf78-tier-weighted-freshness-resolution.json", "wf78_tier_weighted_freshness_resolution"),
            artifact("tmp/wf78-ticker-freshness-ledger.json", "wf78_ticker_freshness_ledger"),
            artifact("tmp/tier-c-band-status.json", "tier_c_band_status"),
            artifact("tmp/market-execution-readiness-cron-hardening.json", "market_execution_readiness_cron_hardening"),
            artifact("tmp/finance-decision-factory.json", "finance_decision_factory"),
            artifact("tmp/post-close-final-quote-ledger.json", "post_close_final_quote_ledger"),
            artifact("tmp/canonical-finance-data-plane.json", "wf84_canonical_finance_data_plane"),
            artifact("tmp/canonical-finance-data-plane-validation.json", "wf84_canonical_finance_data_plane_validation"),
            artifact("tmp/canonical-finance-data-plane.sqlite", "wf84_canonical_finance_data_plane_sqlite"),
            artifact("tmp/canonical-finance-data-plane-phase6-10.json", "wf84_phase6_10_proof"),
            artifact("tmp/canonical-finance-data-plane-retirement-readiness.json", "wf84_retirement_readiness"),
            artifact("tmp/full-answer-parity/full-answer-parity-rollup.json", "wf84_wf85_full_answer_parity"),
            artifact("tmp/trade-grade-os-freshness-cron-runner.json", "trade_grade_os_freshness_cron_runner"),
            artifact("tmp/wf78-missing-band-context-repair.json", "wf78_missing_band_context_repair"),
            artifact("tmp/tier-ab-band-freshness-cron-guard.json", "tier_ab_band_freshness_cron_guard"),
            artifact("tmp/trade-grade-source-freshness-gate.json", "wf85_source_freshness_gate"),
            artifact("tmp/trade-grade-decision-cards.json", "wf85_decision_cards"),
            artifact("tmp/trade-grade-decision-card-authority-validation.json", "wf85_authority_validation"),
            artifact("tmp/trade-grade-approval-card-gate.json", "wf85_approval_card_gate"),
            artifact("tmp/trade-grade-risk-sizing-overlay.json", "wf85_risk_sizing_overlay"),
            artifact("tmp/trade-grade-repair-conveyor.json", "wf85_repair_conveyor"),
        ],
    },
    "Finance - WF78 Open-Ready Owner Review Proof": {
        "owner_workflow": "WF78/WF85 open-ready owner review proof",
        "freshness_hours": 30,
        "expected_artifacts": [
            artifact("tmp/wf78-open-ready-owner-review-cron-runner.json", "wf78_open_ready_owner_review_cron_runner"),
            artifact("tmp/wf78-position-sizing-surface-review.json", "wf78_position_sizing_surface_review"),
            artifact("tmp/wf78-deployment-readiness-review.json", "wf78_deployment_readiness_review"),
            artifact("tmp/wf78-source-artifact-capture-review.json", "wf78_source_artifact_capture_review"),
            artifact("tmp/wf78-position-sizing-integration-proposal.json", "wf78_position_sizing_integration_proposal"),
            artifact("tmp/wf78-tier-a-owner-readiness-proposals.json", "wf78_tier_a_owner_readiness_proposals"),
        ],
    },
    "Operating Leverage - Escalation Trigger Check": {
        "owner_workflow": "operating leverage escalation",
        "freshness_hours": 18,
        "expected_artifacts": [
            artifact("tmp/cron-signal-scorecard.json", "cron_signal_scorecard"),
            artifact("tmp/escalation-trigger.json", "escalation_trigger"),
            artifact("tmp/main-session-handoff-first-proof.json", "handoff_first_proof_gate", blocking=False),
            artifact("tmp/main-session-escalation-consumer.json", "main_session_escalation_consumer", required=False, blocking=False),
        ],
    },
    "Ops - OTEL Local Digest": {
        "owner_workflow": "WF74 observability and model-quality operations",
        "freshness_hours": 30,
        "expected_artifacts": [
            artifact("tmp/wf74-model-quality-collection-cron-runner.json", "wf74_model_quality_collection_cron_runner"),
            artifact("tmp/otel-ops-control.json", "otel_ops_control"),
            artifact("tmp/otel-ops-window-summary.json", "otel_ops_window_summary"),
            artifact("tmp/otel-runtime-metadata-probe.json", "otel_runtime_metadata_probe"),
            artifact("tmp/otel-tool-workflow-metadata.json", "otel_tool_workflow_metadata"),
            artifact("tmp/otel-ops.sqlite", "otel_ops_sqlite"),
            artifact("tmp/changed-file-validator-router.json", "changed_file_validator_router"),
            artifact("tmp/validator-timing-ledger.json", "validator_timing_ledger"),
            artifact("tmp/coding-runtime-kpi-probe.json", "coding_runtime_kpi_probe"),
            artifact("tmp/model-run-ledger-current.json", "model_run_ledger"),
            artifact("tmp/model-learning-metadata-ledger.json", "model_learning_metadata_ledger"),
            artifact("tmp/otel-learning-loop.json", "otel_learning_loop"),
            artifact("tmp/finance-recommendation-correctness-ledger-current.json", "finance_recommendation_correctness_ledger"),
            artifact("tmp/finance-response-quality-slice.json", "finance_response_quality_slice"),
            artifact("tmp/model-quality-scorecard.json", "model_quality_scorecard"),
            artifact("tmp/wf74-improvement-opportunity-queue.json", "wf74_improvement_opportunity_queue"),
            artifact("tmp/wf74-reflection-to-proposal-autopilot.json", "wf74_reflection_to_proposal_autopilot"),
            artifact("tmp/wf74-auto-patch-proposer.json", "wf74_auto_patch_proposer"),
            artifact("tmp/wf74-cron-duplication-audit.json", "wf74_cron_duplication_audit"),
        ],
    },
    "Runtime - OTEL Collector Log Retention": {
        "owner_workflow": "runtime OTEL log retention",
        "freshness_hours": 36,
        "expected_artifacts": [
            artifact("tmp/otel-log-retention.json", "otel_log_retention"),
            artifact("tmp/otel-ops-control.json", "otel_ops_control", required=False, blocking=False),
            artifact("tmp/otel-runtime-metadata-probe.json", "otel_runtime_metadata_probe", required=False, blocking=False),
        ],
    },
    "Runtime - Future Session Packet Refresh": {
        "owner_workflow": "future session carryover packet refresh",
        "freshness_hours": 18,
        "expected_artifacts": [
            artifact("tmp/future-session-enhancement-packet.json", "future_session_enhancement_packet"),
            artifact("tmp/future-session-enhancement-packet.md", "future_session_enhancement_packet_md", required=False, blocking=False),
        ],
    },
    "Runtime - Weekly OS Improvement Radar Proof Refresh": {
        "owner_workflow": "runtime OS improvement radar",
        "freshness_hours": 192,
        "expected_artifacts": [
            artifact("tmp/artifact-staleness-explainer.json", "artifact_staleness_explainer"),
            artifact("tmp/lane-collision-preflight.json", "lane_collision_preflight"),
            artifact("tmp/validator-bundle-router.json", "validator_bundle_router"),
            artifact("tmp/worktree-checkpoint-planner.json", "worktree_checkpoint_planner"),
            artifact("tmp/cron-contract-validator.json", "cron_contract_validator"),
            artifact("tmp/cron-control-packet.json", "cron_control_packet", blocking=False),
            artifact("tmp/pm-control-packet.json", "pm_control_packet"),
        ],
    },
    "Runtime - Weekly OS Improvement Radar Review": {
        "owner_workflow": "runtime OS improvement radar",
        "freshness_hours": 192,
        "expected_artifacts": [
            artifact("tmp/artifact-staleness-explainer.json", "artifact_staleness_explainer"),
            artifact("tmp/lane-collision-preflight.json", "lane_collision_preflight"),
            artifact("tmp/validator-bundle-router.json", "validator_bundle_router"),
            artifact("tmp/worktree-checkpoint-planner.json", "worktree_checkpoint_planner"),
            artifact("tmp/cron-contract-validator.json", "cron_contract_validator"),
            artifact("tmp/cron-control-packet.json", "cron_control_packet", blocking=False),
            artifact("tmp/pm-control-packet.json", "pm_control_packet"),
        ],
    },
    "Macro - Energy and Geopolitical Inputs Refresh": {
        "owner_workflow": "macro intelligence inputs",
        "freshness_hours": 30,
        "expected_artifacts": [
            artifact("tmp/macro-metrics-current.json", "macro_metrics_current"),
            artifact("tmp/macro-signal-spine.json", "macro_signal_spine"),
            artifact("tmp/macro-energy-supply.json", "macro_energy_supply"),
            artifact("tmp/macro-geopolitical-sweep.json", "macro_geopolitical_sweep"),
            artifact("tmp/macro-judgment-draft.json", "macro_judgment_draft"),
            artifact("tmp/artifact-intelligence-action-scorer.json", "artifact_intelligence_action_scorer", required=False),
        ],
    },
    "GPT54mini canary - Macro Energy and Geopolitical Inputs Refresh": {
        "owner_workflow": "macro intelligence inputs model canary",
        "freshness_hours": 30,
        "expected_artifacts": [
            artifact("tmp/macro-metrics-current.json", "macro_metrics_current"),
            artifact("tmp/macro-signal-spine.json", "macro_signal_spine"),
            artifact("tmp/macro-energy-supply.json", "macro_energy_supply"),
            artifact("tmp/macro-geopolitical-sweep.json", "macro_geopolitical_sweep"),
            artifact("tmp/macro-judgment-draft.json", "macro_judgment_draft"),
            artifact("tmp/artifact-intelligence-action-scorer.json", "artifact_intelligence_action_scorer", required=False),
        ],
    },
    "P0 Retail Automation Control Plane Guard": {
        "owner_workflow": "P0 retail truth routing",
        "freshness_hours": 18,
        "expected_artifacts": [
            artifact(
                "tmp/retail-automation-control-plane-cron-runner.json",
                "retail_automation_control_plane_cron_runner",
                required=False,
                blocking=False,
            ),
            artifact("tmp/retail-automation-control-plane.json", "retail_automation_control_plane"),
            artifact("tmp/wf78-phase-runner-current.json", "wf78_phase_runner"),
            artifact("tmp/wf78-capital-review-queue.json", "wf78_capital_review_queue"),
            artifact("tmp/wf78-event-triggered-rerouting.json", "wf78_event_triggered_rerouting"),
            artifact("tmp/market-execution-readiness-cron-hardening.json", "market_execution_readiness_cron_hardening"),
        ],
    },
    "PM - Main Session Continuation Dispatcher": {
        "owner_workflow": "PM continuation dispatcher",
        "freshness_hours": 18,
        "expected_artifacts": [
            artifact("tmp/pm-control-packet.json", "pm_control_packet"),
            artifact("tmp/main-session-escalation-consumer.json", "main_session_escalation_consumer", required=False, blocking=False),
            artifact("tmp/main-session-action-executor.json", "main_session_action_executor"),
        ],
    },
    "PM - Autonomous Implementation Proof Worker": {
        "owner_workflow": "PM autonomous implementation proof worker",
        "freshness_hours": 24,
        "expected_artifacts": [
            artifact("tmp/pm-autonomy-dispatcher.json", "pm_autonomy_dispatcher"),
            artifact("tmp/pm-job-worker-runner.json", "pm_job_worker_runner"),
            artifact("tmp/pm-autonomy-verifier.json", "pm_autonomy_verifier"),
            artifact("tmp/pm-main-session-action-inbox.json", "pm_main_session_action_inbox", required=False, blocking=False),
        ],
    },
    "Security Audit - Daily Bounded Hardening": {
        "owner_workflow": "WF40 security audit",
        "freshness_hours": 36,
        "expected_artifacts": [
            artifact("tmp/cyber-security-daily-audit-cron-proof.json", "security_cron_proof"),
            artifact("tmp/cyber-security-daily-audit.json", "security_audit"),
        ],
    },
    "SQL Coverage - Daily Control Plane Guard": {
        "owner_workflow": "SQL/control-plane coverage",
        "freshness_hours": 36,
        "expected_artifacts": [
            artifact("tmp/sql-coverage-guard.json", "sql_coverage_guard"),
            artifact("tmp/workflow-routing-index.json", "workflow_routing_index"),
            artifact("tmp/workflow-routing-index-validation.json", "workflow_routing_index_validation"),
            artifact("tmp/workflow-routing-index.sqlite", "workflow_routing_index_sqlite"),
        ],
    },
    "WF75 PM Weekly Artifact Builder": {
        "owner_workflow": "WF75 PM weekly artifacts",
        "freshness_hours": 192,
        "expected_artifacts": [
            artifact("tmp/wf75-pm-weekly-update.json", "wf75_pm_weekly_update"),
            artifact("tmp/pm-control-packet.json", "pm_control_packet"),
        ],
    },
    "Finance Delivery Series - Daily Market Read Builder": {
        "owner_workflow": "WF75 finance delivery series",
        "freshness_hours": 36,
        "expected_artifacts": [
            artifact("tmp/finance-delivery-series.json", "finance_delivery_series"),
            artifact("tmp/finance-delivery-series.xlsx", "finance_delivery_series_workbook"),
            artifact("tmp/finance-delivery-series/daily-market-read.pdf", "daily_market_read_pdf"),
        ],
    },
    "Finance Delivery Series - Daily Market Read Handoff": {
        "owner_workflow": "WF75 finance delivery series",
        "freshness_hours": 36,
        "expected_artifacts": [
            artifact("tmp/finance-delivery-series.json", "finance_delivery_series"),
            artifact("tmp/finance-delivery-series/daily-market-read.pdf", "daily_market_read_pdf"),
            artifact("tmp/cron-control-packet.json", "cron_control_packet"),
        ],
    },
    "Finance Delivery Series - Weekly Market Read Builder": {
        "owner_workflow": "WF75 finance delivery series",
        "freshness_hours": 192,
        "expected_artifacts": [
            artifact("tmp/finance-delivery-series.json", "finance_delivery_series"),
            artifact("tmp/finance-delivery-series.xlsx", "finance_delivery_series_workbook"),
            artifact("tmp/finance-delivery-series/weekly-market-read.pdf", "weekly_market_read_pdf"),
        ],
    },
    "Finance Delivery Series - Weekly Performance Builder": {
        "owner_workflow": "WF75 finance delivery series",
        "freshness_hours": 192,
        "expected_artifacts": [
            artifact("tmp/finance-delivery-series.json", "finance_delivery_series"),
            artifact("tmp/finance-delivery-series.xlsx", "finance_delivery_series_workbook"),
            artifact("tmp/finance-delivery-series/weekly-investments-performance.pdf", "weekly_investments_performance_pdf"),
        ],
    },
    "Finance Delivery Series - Weekly Handoff": {
        "owner_workflow": "WF75 finance delivery series",
        "freshness_hours": 192,
        "expected_artifacts": [
            artifact("tmp/finance-delivery-series.json", "finance_delivery_series"),
            artifact("tmp/finance-delivery-series/weekly-market-read.pdf", "weekly_market_read_pdf"),
            artifact("tmp/finance-delivery-series/weekly-investments-performance.pdf", "weekly_investments_performance_pdf"),
            artifact("tmp/pm-control-packet.json", "pm_control_packet"),
        ],
    },
    "Finance Delivery Series - Monthly Direction and Deep Dive Builder": {
        "owner_workflow": "WF75 finance delivery series",
        "freshness_hours": 900,
        "expected_artifacts": [
            artifact("tmp/finance-delivery-series.json", "finance_delivery_series"),
            artifact("tmp/finance-delivery-series.xlsx", "finance_delivery_series_workbook"),
            artifact("tmp/finance-delivery-series/monthly-investment-direction.pdf", "monthly_investment_direction_pdf"),
            artifact("tmp/finance-delivery-series/monthly-market-deep-dive.pdf", "monthly_market_deep_dive_pdf"),
        ],
    },
    "Finance Delivery Series - Monthly Handoff": {
        "owner_workflow": "WF75 finance delivery series",
        "freshness_hours": 900,
        "expected_artifacts": [
            artifact("tmp/finance-delivery-series.json", "finance_delivery_series"),
            artifact("tmp/finance-delivery-series/monthly-investment-direction.pdf", "monthly_investment_direction_pdf"),
            artifact("tmp/finance-delivery-series/monthly-market-deep-dive.pdf", "monthly_market_deep_dive_pdf"),
            artifact("tmp/pm-control-packet.json", "pm_control_packet"),
        ],
    },
    "WF76 - Weekly Cron Authority and OS Maintenance": {
        "owner_workflow": "WF76 cron authority maintenance",
        "freshness_hours": 192,
        "expected_artifacts": [
            artifact("tmp/cron-automation-authority-validation.json", "cron_authority_validation"),
            artifact("tmp/db-lifecycle-manifest.json", "db_lifecycle_manifest"),
        ],
    },
    "WF77 Weekly Analyst Consensus Main-Session Handoff": {
        "owner_workflow": "WF77 analyst consensus handoff",
        "freshness_hours": 192,
        "expected_artifacts": [
            artifact("tmp/wf77-weekly-analyst-refresh-cron-runner.json", "wf77_weekly_runner"),
            artifact("tmp/analyst-consensus-current.json", "analyst_consensus_current"),
        ],
    },
    "WF77 Weekly Analyst Consensus Refresh - Tier A/B Review": {
        "owner_workflow": "WF77 analyst consensus refresh",
        "freshness_hours": 192,
        "expected_artifacts": [
            artifact("tmp/wf77-weekly-analyst-refresh-cron-runner.json", "wf77_weekly_runner"),
            artifact("tmp/analyst-consensus-current.json", "analyst_consensus_current"),
            artifact("tmp/finance-data-coverage-current.json", "finance_data_coverage"),
        ],
    },
}


# Compatibility-only artifact contracts for retired scheduler routes.  They are
# kept separate for historical tests and audit explanation, and are never
# merged into the active freshness contract map.  Current finance jobs must be
# registered through state/cron-contracts/*.json so a stale embedded name can
# neither reactivate a retired route nor false-green an uncontracted live job.
_RETIRED_LEGACY_CONTRACT_PREFIXES = (
    "Finance -",
    "Finance Delivery Series -",
    "GPT54mini canary -",
)
_RETIRED_LEGACY_CONTRACT_NAMES = frozenset(
    {
        "Cron Reduction - Morning Control Digest",
        "Cron Reduction - Post-Close Control Digest",
        "Governance - Monthly Execution Board SQL-First Review",
        "Cron - Main Session Auto-Green Watchdog",
        "Operating Leverage - Escalation Trigger Check",
        "P0 Retail Automation Control Plane Guard",
        "PM - Autonomous Implementation Proof Worker",
        "WF74 - Learning Loop Telegram Digest",
        "WF76 - Weekly Cron Authority and OS Maintenance",
    }
)


def _is_retired_legacy_embedded_contract(name: str) -> bool:
    return name in _RETIRED_LEGACY_CONTRACT_NAMES or name.startswith(_RETIRED_LEGACY_CONTRACT_PREFIXES)


RETIRED_LEGACY_JOB_CONTRACTS: dict[str, dict[str, Any]] = {
    name: contract
    for name, contract in JOB_CONTRACTS.items()
    if _is_retired_legacy_embedded_contract(name)
}
JOB_CONTRACTS = {
    name: contract
    for name, contract in JOB_CONTRACTS.items()
    if not _is_retired_legacy_embedded_contract(name)
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def workspace_path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else ROOT / path


def artifact_role_from_path(path: str) -> str:
    return Path(path).stem.replace("-", "_")


def normalize_artifact_spec(value: Any, base_specs: dict[str, dict[str, Any]] | None = None) -> dict[str, Any] | None:
    if isinstance(value, str):
        raw: dict[str, Any] = {"path": value}
    elif isinstance(value, dict):
        raw = dict(value)
    else:
        return None
    path = str(raw.get("path") or "").replace("\\", "/")
    if not path:
        return None
    base = dict(as_dict((base_specs or {}).get(path)))
    merged = {**base, **raw}
    merged["path"] = path
    merged["role"] = str(merged.get("role") or artifact_role_from_path(path))
    merged["required"] = bool(merged.get("required", True))
    merged["blocking"] = bool(merged.get("blocking", merged.get("required", True)))
    return merged


def inferred_contract_freshness_hours(contract: dict[str, Any]) -> float:
    schedule = as_dict(contract.get("schedule"))
    expr = str(schedule.get("expr") or "")
    fields = expr.split()
    if len(fields) >= 5 and fields[4] not in {"*", "1-5", "MON-FRI", "Mon-Fri", "mon-fri"}:
        return 192.0
    return 36.0


def load_file_contracts(contract_dir: Path = DEFAULT_CONTRACT_DIR) -> dict[str, dict[str, Any]]:
    if not contract_dir.exists():
        return {}
    contracts: dict[str, dict[str, Any]] = {}
    for path in sorted(contract_dir.glob("*.json")):
        payload = load_json(path)
        if not isinstance(payload, dict):
            continue
        name = str(payload.get("name") or payload.get("job_name") or "")
        if not name:
            continue
        payload["_contract_source"] = rel(path)
        contracts[name] = payload
    return contracts


def merged_job_contracts(contract_dir: Path = DEFAULT_CONTRACT_DIR) -> dict[str, dict[str, Any]]:
    contracts: dict[str, dict[str, Any]] = {
        name: {
            **contract,
            "expected_artifacts": [dict(item) for item in as_list(contract.get("expected_artifacts"))],
        }
        for name, contract in JOB_CONTRACTS.items()
    }
    for name, file_contract in load_file_contracts(contract_dir).items():
        base = as_dict(contracts.get(name))
        base_specs = {
            str(as_dict(item).get("path") or "").replace("\\", "/"): as_dict(item)
            for item in as_list(base.get("expected_artifacts"))
            if as_dict(item).get("path")
        }
        expected_artifacts = [
            spec for spec in (
                normalize_artifact_spec(item, base_specs)
                for item in as_list(file_contract.get("expected_artifacts"))
            )
            if spec
        ]
        merged = {
            **base,
            "owner_workflow": file_contract.get("owner_workflow") or base.get("owner_workflow"),
            "freshness_hours": float(file_contract.get("freshness_hours") or base.get("freshness_hours") or inferred_contract_freshness_hours(file_contract)),
            "contract_source": file_contract.get("_contract_source"),
        }
        if expected_artifacts:
            merged["expected_artifacts"] = expected_artifacts
        elif "expected_artifacts" not in merged:
            merged["expected_artifacts"] = []
        if file_contract.get("known_platform_failure"):
            merged["known_platform_failure"] = dict(as_dict(file_contract.get("known_platform_failure")))
        contracts[name] = merged
    return contracts


def load_json(path: Path) -> Any:
    if not path.exists():
        return None
    return load_json_artifact(path)


def normalize_router_for_identity(value: Any) -> Any:
    """Return stable router content without artifact-generation residue."""
    if isinstance(value, dict):
        return {
            str(key): normalize_router_for_identity(item)
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
            if str(key) not in ROUTER_IDENTITY_VOLATILE_KEYS
        }
    if isinstance(value, (list, tuple)):
        return [normalize_router_for_identity(item) for item in value]
    return value


def router_lineage(router: dict[str, Any], router_path: Path = WF78_AUTO_TIER_ROUTER) -> dict[str, Any]:
    normalized = normalize_router_for_identity(router)
    encoded = json.dumps(normalized, sort_keys=True, separators=(",", ":"), default=str)
    return {
        "path": rel(router_path),
        "content_sha256": hashlib.sha256(encoded.encode("utf-8")).hexdigest(),
        "generated_at_utc": router.get("generated_at_utc") or router.get("generated_at"),
    }


def router_lineage_complete(lineage: dict[str, Any]) -> bool:
    return bool(
        str(lineage.get("path") or "")
        and str(lineage.get("content_sha256") or "")
        and str(lineage.get("generated_at_utc") or "")
    )


def router_lineage_matches(lineage: dict[str, Any], live_lineage: dict[str, Any]) -> bool:
    return router_lineage_complete(lineage) and router_lineage_complete(live_lineage) and all(
        lineage.get(key) == live_lineage.get(key)
        for key in ("path", "content_sha256", "generated_at_utc")
    )


def wf78_tier_semantic_lineage(
    payload: dict[str, Any],
    role: Any,
    router_path: Path = WF78_AUTO_TIER_ROUTER,
) -> dict[str, Any]:
    """Fail closed when a WF78 tier-truth artifact is not bound to the live router."""
    if role not in WF78_TIER_SEMANTIC_ROLES:
        return {"applicable": False, "status": "not_applicable", "errors": []}

    live_router = as_dict(load_json(router_path))
    if not live_router:
        return {
            "applicable": True,
            "status": "live_router_missing",
            "live_router_lineage": None,
            "checked_lineages": [],
            "errors": ["live_router_missing"],
        }

    live_lineage = router_lineage(live_router, router_path)
    if not router_lineage_complete(live_lineage):
        return {
            "applicable": True,
            "status": "live_router_lineage_incomplete",
            "live_router_lineage": live_lineage,
            "checked_lineages": [],
            "errors": ["live_router_lineage_incomplete"],
        }

    checked = [("artifact_source_router", as_dict(payload.get("source_router_lineage")))]
    if role in {"wf78_truth_layer_map", "wf78_tier_semantics_guard"}:
        checked.append(
            (
                "downstream_roster_source_router",
                as_dict(as_dict(payload.get("source_roster_lineage")).get("source_router_lineage")),
            )
        )
    if role == "wf78_tier_semantics_guard":
        checked.append(
            (
                "downstream_truth_layer_map_source_router",
                as_dict(as_dict(payload.get("source_truth_layer_map_lineage")).get("source_router_lineage")),
            )
        )

    records: list[dict[str, Any]] = []
    errors: list[str] = []
    for name, lineage in checked:
        complete = router_lineage_complete(lineage)
        matches_live = router_lineage_matches(lineage, live_lineage)
        records.append({
            "name": name,
            "lineage": lineage,
            "complete": complete,
            "matches_live_router": matches_live,
        })
        if not complete:
            errors.append(f"{name}_missing_or_incomplete")
        elif not matches_live:
            errors.append(f"{name}_mismatched_live_router")

    return {
        "applicable": True,
        "status": "ok" if not errors else "missing" if any("missing_or_incomplete" in item for item in errors) else "mismatched",
        "live_router_lineage": live_lineage,
        "checked_lineages": records,
        "errors": errors,
    }


def parse_utc(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def age_hours_from_dt(dt: datetime | None) -> float | None:
    if not dt:
        return None
    return round(max(0.0, (datetime.now(timezone.utc) - dt).total_seconds() / 3600), 2)


def expected_warning_quiet(payload: dict[str, Any]) -> bool:
    warnings = as_list(payload.get("warnings"))
    validation_warnings = as_list(as_dict(payload.get("validation")).get("warnings"))
    summary = as_dict(payload.get("summary"))
    readiness = as_dict(payload.get("answer_readiness"))
    market_today_gap_quiet = (
        payload.get("schema") == "veritas.market_today_answer_packet.v1"
        and str(payload.get("status") or "").lower() == "warning"
        and as_dict(payload.get("validation")).get("status") in {"ok", "warning"}
        and readiness.get("can_answer_basic_market_day_without_web") is True
        and readiness.get("can_answer_full_market_close_recap_without_web") in {False, True}
        and not as_list(as_dict(payload.get("validation")).get("errors"))
    )
    if market_today_gap_quiet:
        return True
    quote_warning_quiet = (
        str(payload.get("status") or "").lower() == "warning"
        and validation_warnings == ["wf78_event_queue_keeps_fresh_quote_first"]
        and as_dict(payload.get("validation")).get("status") == "ok"
        and int(summary.get("critical_count") or 0) == 0
        and len(as_list(summary.get("missing_required_symbols"))) == 0
        and int(summary.get("stale_or_missing_snapshot_count") or 0) == 0
    )
    if quote_warning_quiet:
        return True
    operator_attention = as_dict(payload.get("operator_attention"))
    artifact_inventory = as_dict(payload.get("artifact_inventory"))
    cron_ledger_rollup_quiet = (
        payload.get("schema_version") == 1
        and str(payload.get("status") or "").lower() == "warning"
        and not as_list(operator_attention.get("stop_line_windows"))
        and not as_list(operator_attention.get("blocked_windows"))
        and not as_list(artifact_inventory.get("missing_required_roles"))
        and not as_list(artifact_inventory.get("critical_or_unreadable_roles"))
    )
    if cron_ledger_rollup_quiet:
        return True
    pm_no_action_status_residue_quiet = (
        payload.get("schema") == "veritas.pm_autonomy_verifier.v1"
        and str(payload.get("status") or "").lower() == "warning"
        and as_dict(payload.get("summary")).get("action_type") == "no_action"
        and as_dict(payload.get("validation")).get("status") == "ok"
        and as_list(as_dict(payload.get("validation")).get("warnings")) == ["status_packet_refresh_validation_residue"]
    )
    if pm_no_action_status_residue_quiet:
        return True
    main_session_no_action_quiet = (
        payload.get("schema") == "veritas.main_session_action_executor.v1"
        and str(payload.get("status") or "").lower() == "warning"
        and summary.get("action_type") == "no_action"
        and summary.get("classification") == "no_reply"
        and summary.get("executed") is False
        and not as_list(summary.get("execution_failed"))
        and as_dict(payload.get("validation")).get("status") == "ok"
        and as_list(as_dict(payload.get("validation")).get("warnings")) == ["no_action_available"]
    )
    if main_session_no_action_quiet:
        return True
    return (
        str(payload.get("status") or "").lower() == "warning"
        and payload.get("stop_line") is not True
        and not as_list(payload.get("blockers"))
        and as_dict(payload.get("execution")).get("chain_status") == "ok"
        and as_dict(payload.get("validation")).get("acceptance_passed") is True
        and warnings
        and all(EXPECTED_SUSPENDED_WEIGHT_WARNING in str(warning) for warning in warnings)
    )


def status_route_self_loop_residue(payload: dict[str, Any]) -> bool:
    validation = as_dict(payload.get("validation"))
    errors = as_list(validation.get("errors"))
    return (
        str(payload.get("status") or "").lower() == "critical"
        and validation.get("status") == "critical"
        and errors
        and set(errors).issubset({
            "wf74_pickup.missing_cron_migration_repair",
            "wf88_wiki_synthesis.validation_blocked",
        })
    )


def artifact_record(spec: dict[str, Any], default_freshness_hours: float) -> dict[str, Any]:
    path = workspace_path(str(spec.get("path") or ""))
    payload = load_json(path)
    payload_dict = as_dict(payload)
    stat_dt: datetime | None = None
    if path.exists():
        stat_dt = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
    generated_dt = (
        parse_utc(payload_dict.get("generated_at_utc"))
        or parse_utc(payload_dict.get("generated_at"))
        or parse_utc(as_dict(payload_dict.get("summary")).get("generated_at_utc"))
        or stat_dt
    )
    age = age_hours_from_dt(generated_dt)
    status = str(payload_dict.get("status") or ("ok" if path.exists() else "missing")).lower()
    validation_status = str(as_dict(payload_dict.get("validation")).get("status") or "").lower()
    operator_action = str(payload_dict.get("operator_action") or payload_dict.get("operator_action_required") or "")
    has_forbidden_authority = authority_widened(payload_dict)
    role = str(spec.get("role") or "")
    context_only = role in CONTEXT_ONLY_ROLES or rel(path) == "tmp/cron-control-packet.json"
    status_route_residue = role in STATUS_ROUTE_RESIDUE_ROLES and status_route_self_loop_residue(payload_dict)
    lineage_router_path = workspace_path(str(spec.get("source_router_path") or WF78_AUTO_TIER_ROUTER))
    tier_semantic_lineage = wf78_tier_semantic_lineage(payload_dict, role, lineage_router_path)
    tier_semantic_lineage_blocked = bool(
        tier_semantic_lineage.get("applicable")
        and tier_semantic_lineage.get("status") != "ok"
    )
    raw_blocked_semantic = (
        not status_route_residue
        and (
            status in {"blocked", "error", "critical"}
            or validation_status == "error"
            or operator_action == "BLOCKED"
            or tier_semantic_lineage_blocked
        )
    )
    review_only_blocked_semantic = bool(
        role in REVIEW_ONLY_BLOCKED_ROLES
        and status == "blocked"
        and validation_status != "error"
        and operator_action != "BLOCKED"
        and not has_forbidden_authority
    )
    blocking = (
        False
        if context_only
        else True
        if role in WF78_TIER_SEMANTIC_ROLES
        else bool(spec.get("blocking", spec.get("required", True)))
    )
    return {
        "role": role,
        "path": rel(path),
        "required": bool(spec.get("required", True)),
        "blocking": blocking,
        "exists": path.exists(),
        "parseable_json": isinstance(payload, dict),
        "status": status,
        "validation_status": validation_status or None,
        "operator_action": operator_action or None,
        "generated_at_utc": generated_dt.replace(microsecond=0).isoformat().replace("+00:00", "Z") if generated_dt else None,
        "age_hours": age,
        "freshness_window_hours": float(spec.get("freshness_hours") or default_freshness_hours),
        # existence_only artifacts (e.g. doctrine files) prove presence, not recency.
        "stale": not spec.get("existence_only") and age is not None and age > float(spec.get("freshness_hours") or default_freshness_hours),
        "blocked_semantic": raw_blocked_semantic and not review_only_blocked_semantic,
        "review_only_blocked_semantic": review_only_blocked_semantic,
        "main_handoff_semantic": operator_action in {"MAIN_HANDOFF_REQUIRED", "MAIN_SESSION_REQUIRED"} or review_only_blocked_semantic,
        "owner_decision_semantic": operator_action == "OWNER_DECISION",
        "expected_warning_quiet": expected_warning_quiet(payload_dict),
        "authority_widened": has_forbidden_authority,
        "wf78_tier_semantic_lineage": tier_semantic_lineage,
        "wf78_tier_semantic_lineage_blocked": tier_semantic_lineage_blocked,
    }


def schedule_expr(job: dict[str, Any]) -> str:
    schedule = job.get("schedule")
    if isinstance(schedule, dict):
        return str(schedule.get("expr") or "")
    if isinstance(schedule, str):
        try:
            parsed = json.loads(schedule)
        except json.JSONDecodeError:
            return schedule
        if isinstance(parsed, dict):
            return str(parsed.get("expr") or "")
    return ""


def schedule_kind(job: dict[str, Any]) -> str:
    schedule = job.get("schedule")
    if isinstance(schedule, dict):
        return str(schedule.get("kind") or "")
    if isinstance(schedule, str):
        try:
            parsed = json.loads(schedule)
        except json.JSONDecodeError:
            return ""
        if isinstance(parsed, dict):
            return str(parsed.get("kind") or "")
    return ""


def weekday_only_schedule(job: dict[str, Any]) -> bool:
    expr = schedule_expr(job)
    fields = expr.split()
    return len(fields) >= 5 and fields[4] in {"1-5", "MON-FRI", "Mon-Fri", "mon-fri"}


def effective_freshness_hours(job: dict[str, Any], contract: dict[str, Any]) -> float:
    base = float(contract.get("freshness_hours") or 36)
    # Weekday-only producers should not be labeled stale just because the
    # weekend crossed a normal weekday freshness window. On Monday, this falls
    # back to the normal window so a missed Monday refresh is visible.
    local_weekday = datetime.now(timezone.utc).astimezone(LOCAL_TZ).weekday()
    if weekday_only_schedule(job) and local_weekday in {5, 6}:
        return float(contract.get("weekend_freshness_hours") or 84)
    return base


def authority_widened(payload: dict[str, Any]) -> bool:
    text = json.dumps(payload, sort_keys=True).lower()
    forbidden_true_tokens = (
        '"cron_state_mutation_allowed": true',
        '"cron_schedule_mutation_allowed": true',
        '"runtime_config_mutation_allowed": true',
        '"sql_write_or_import_allowed": true',
        '"sql_first_promotion_allowed": true',
        '"customer_or_external_delivery_allowed": true',
        '"paper_or_live_execution_allowed": true',
        '"brokerage_or_account_action_allowed": true',
        '"owner_approval_inferred": true',
    )
    return any(token in text for token in forbidden_true_tokens)


MAX_SCHEDULER_ERROR_CHARS = 400


SCHEDULER_ERROR_JSON_KEYS = (
    "status",
    "proof_status",
    "error",
    "errors",
    "critical",
    "blockers",
    "failed_steps",
)


def compact_json_error(text: str) -> str | None:
    """Some producers dump their whole result object into the error field. A
    truncated blob is unreadable in a digest line, so pull the few keys that say
    what actually failed."""
    try:
        data = json.loads(text)
    except ValueError:
        # The operator ledger caps error text at 2000 chars, so long blobs arrive
        # truncated and unparseable; scrape the same keys textually instead.
        pattern = r'"(%s)"\s*:\s*"([^"]*)"' % "|".join(SCHEDULER_ERROR_JSON_KEYS)
        found = {key: value for key, value in re.findall(pattern, text)}
        return "; ".join(f"{k}={found[k]}" for k in SCHEDULER_ERROR_JSON_KEYS if found.get(k)) or None
    if not isinstance(data, dict):
        return None
    parts = []
    for key in SCHEDULER_ERROR_JSON_KEYS:
        value = data.get(key)
        if isinstance(value, (list, tuple)):
            value = ", ".join(str(item) for item in value[:3])
        elif isinstance(value, dict):
            value = value.get("status") or ""
        value = " ".join(str(value or "").split())
        if value:
            parts.append(f"{key}={value}")
    return "; ".join(parts) or None


def scheduler_error_text(job: dict[str, Any]) -> str | None:
    """Operator-ledger error text, kept so escalations name the failure instead of
    only counting it. Diagnostic summary is preferred because bare last_error is
    often just an exit code."""
    candidates = [
        text
        for text in (
            str(job.get(key) or "").strip()
            for key in ("last_diagnostic_summary", "last_error")
        )
        if text
    ]
    for text in candidates:
        if not text.startswith(("{", "[")):
            return " ".join(text.split())[:MAX_SCHEDULER_ERROR_CHARS]
        compact = compact_json_error(text)
        if compact:
            return compact[:MAX_SCHEDULER_ERROR_CHARS]
    if candidates:
        return " ".join(candidates[0].split())[:MAX_SCHEDULER_ERROR_CHARS]
    return None


def artifacts_prove_post_failure_recovery(
    artifacts: list[dict[str, Any]],
    last_run_at: datetime | None,
) -> bool:
    """Require every required artifact to be newer than the failed scheduler run."""
    if last_run_at is None:
        return False
    required = [item for item in artifacts if item.get("required")]
    generated = [parse_utc(item.get("generated_at_utc")) for item in required]
    return bool(required and all(value is not None and value > last_run_at for value in generated))


def installed_openclaw_version() -> str | None:
    appdata = os.environ.get("APPDATA")
    if not appdata:
        return None
    try:
        package = json.loads((Path(appdata) / "npm" / "node_modules" / "openclaw" / "package.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    version = package.get("version")
    return str(version) if version else None


def known_platform_failure_match(
    contract: dict[str, Any],
    live_last_error: str | None,
    openclaw_version: str | None,
) -> dict[str, Any] | None:
    """Owner-approved known platform defect: exact error text on the exact recorded OpenClaw version.

    `error_substring` names one exact error; `error_substrings` may add further owner-approved exact
    errors for the same defect. Any other error, a missing version, or a version change fails closed
    back to normal escalation so the defect is re-checked after every OpenClaw update.
    """
    known = as_dict(contract.get("known_platform_failure"))
    extra = known.get("error_substrings")
    error_texts = [str(known.get("error_substring") or "")]
    error_texts += [str(item) for item in extra] if isinstance(extra, list) else []
    error_texts = [text for text in error_texts if text]
    recorded_version = str(known.get("openclaw_version") or "")
    if not (error_texts and recorded_version and known.get("owner_approved_at")):
        return None
    if not live_last_error or not any(text in live_last_error for text in error_texts):
        return None
    if not openclaw_version or openclaw_version != recorded_version:
        return None
    return known


def classify_job(
    job: dict[str, Any],
    contract: dict[str, Any] | None,
    openclaw_version: str | None = None,
) -> dict[str, Any]:
    enabled = bool(job.get("enabled"))
    name = str(job.get("name") or "")
    live_last_status = str(job.get("last_status") or "").strip().lower()
    live_consecutive_errors = int(job.get("consecutive_errors") or 0)
    live_last_run_exception = enabled and live_last_status not in {"", "ok", "idle"}
    live_last_error = scheduler_error_text(job)
    live_last_run_at = parse_utc(job.get("last_run_utc"))
    if not enabled:
        return {
            "id": job.get("id"),
            "name": name,
            "enabled": False,
            "schedule": job.get("schedule"),
            "owner_workflow": None,
            "status": "disabled",
            "signal_class": "NO_REPLY",
            "attention": "quiet_success",
            "live_scheduler_last_status": live_last_status or None,
            "live_scheduler_consecutive_errors": live_consecutive_errors,
            "live_scheduler_last_run_exception": False,
            "live_scheduler_last_run_at": job.get("last_run_utc") or None,
            "expected_artifacts": [],
        }
    if not contract and schedule_kind(job) == "at":
        if live_last_run_exception:
            return {
                "id": job.get("id"),
                "name": name,
                "enabled": True,
                "schedule": job.get("schedule"),
                "owner_workflow": None,
                "status": "one_shot_scheduler_error",
                "signal_class": "BLOCKED",
                "attention": "requires_main_attention",
                "reason": "one_shot_job_last_run_failed",
                "live_scheduler_last_status": live_last_status or None,
                "live_scheduler_consecutive_errors": live_consecutive_errors,
                "live_scheduler_last_run_exception": live_last_run_exception,
                "live_scheduler_last_run_at": job.get("last_run_utc") or None,
                "live_scheduler_last_error": live_last_error,
                "expected_artifacts": [],
            }
        return {
            "id": job.get("id"),
            "name": name,
            "enabled": True,
            "schedule": job.get("schedule"),
            "owner_workflow": None,
            "status": "one_shot_pending",
            "signal_class": "NO_REPLY",
            "attention": "quiet_success",
            "reason": "one_shot_at_job_exempt_from_standing_freshness_contract",
            "live_scheduler_last_status": live_last_status or None,
            "live_scheduler_consecutive_errors": live_consecutive_errors,
            "live_scheduler_last_run_exception": live_last_run_exception,
            "live_scheduler_last_run_at": job.get("last_run_utc") or None,
            "live_scheduler_last_error": live_last_error,
            "expected_artifacts": [],
        }
    if not contract:
        return {
            "id": job.get("id"),
            "name": name,
            "enabled": True,
            "schedule": job.get("schedule"),
            "owner_workflow": None,
            "status": "unregistered",
            "signal_class": "BLOCKED",
            "attention": "requires_main_attention",
            "reason": "enabled_job_missing_freshness_contract",
            "live_scheduler_last_status": live_last_status or None,
            "live_scheduler_consecutive_errors": live_consecutive_errors,
            "live_scheduler_last_run_exception": live_last_run_exception,
            "live_scheduler_last_run_at": job.get("last_run_utc") or None,
            "live_scheduler_last_error": live_last_error,
            "expected_artifacts": [],
        }
    default_freshness = effective_freshness_hours(job, contract)
    artifacts = [artifact_record(spec, default_freshness) for spec in as_list(contract.get("expected_artifacts"))]
    missing = [item for item in artifacts if item.get("required") and not item.get("exists")]
    stale = [item for item in artifacts if item.get("required") and item.get("stale")]
    blocked = [item for item in artifacts if item.get("blocking") and (item.get("blocked_semantic") or item.get("authority_widened"))]
    tier_semantic_lineage_blocked = [
        item for item in artifacts
        if item.get("wf78_tier_semantic_lineage_blocked")
    ]
    main_required = [item for item in artifacts if item.get("main_handoff_semantic")]
    owner_decision = [item for item in artifacts if item.get("owner_decision_semantic")]
    warning = [
        item for item in artifacts
        if item.get("status") == "warning" and not item.get("expected_warning_quiet") and not item.get("blocked_semantic")
    ]
    if not artifacts:
        status = "missing_expected_artifact_contract"
        signal_class = "BLOCKED"
        attention = "requires_main_attention"
        reason = status
    elif missing:
        status = "missing_artifact"
        signal_class = "BLOCKED"
        attention = "requires_main_attention"
        reason = "one_or_more_required_artifacts_missing"
    elif tier_semantic_lineage_blocked:
        status = "blocked"
        signal_class = "BLOCKED"
        attention = "requires_main_attention"
        reason = "wf78_tier_semantic_lineage_missing_or_mismatched"
    elif blocked:
        status = "blocked"
        signal_class = "BLOCKED"
        attention = "requires_main_attention"
        reason = "artifact_blocked_or_authority_widened"
    elif owner_decision:
        status = "owner_decision"
        signal_class = "OWNER_DECISION"
        attention = "requires_main_attention"
        reason = "artifact_requests_owner_decision"
    elif main_required or warning:
        status = "needs_review"
        signal_class = "MAIN_SESSION_REQUIRED"
        attention = "requires_main_attention"
        reason = "artifact_requests_or_warns_for_review"
    elif stale:
        status = "stale"
        signal_class = "STALE_OR_NOISE"
        attention = "inspect_if_relevant"
        reason = "one_or_more_required_artifacts_stale"
    else:
        status = "fresh"
        signal_class = "NO_REPLY"
        attention = "quiet_success"
        reason = "required_artifacts_fresh"
    recovery_proven = bool(
        live_last_run_exception
        and live_consecutive_errors >= 2
        and status in {"fresh", "needs_review"}
        and artifacts_prove_post_failure_recovery(artifacts, live_last_run_at)
    )
    known_failure = None
    if live_last_run_exception and live_consecutive_errors >= 2:
        if signal_class not in {"BLOCKED", "OWNER_DECISION"}:
            known_failure = known_platform_failure_match(contract, live_last_error, openclaw_version)
        if known_failure:
            status = "known_platform_failure"
            signal_class = "STALE_OR_NOISE"
            attention = "inspect_if_relevant"
            reason = f"owner_approved_known_platform_failure:{known_failure.get('upstream') or 'unspecified'}"
        elif recovery_proven:
            if status == "fresh":
                status = "recovered_waiting_scheduler_canary"
                signal_class = "STALE_OR_NOISE"
                attention = "inspect_if_relevant"
                reason = "fresh_artifacts_prove_recovery_after_last_scheduler_failure"
        else:
            status = "scheduler_error"
            signal_class = "BLOCKED"
            attention = "requires_main_attention"
            reason = "enabled_job_repeated_scheduler_failures"
    latest = max((item.get("generated_at_utc") for item in artifacts if item.get("generated_at_utc")), default=None)
    max_age = max((item.get("age_hours") for item in artifacts if item.get("age_hours") is not None), default=None)
    return {
        "id": job.get("id"),
        "name": name,
        "enabled": True,
        "schedule": job.get("schedule"),
        "owner_workflow": contract.get("owner_workflow"),
        "status": status,
        "signal_class": signal_class,
        "attention": attention,
        "reason": reason,
        "generated_at_utc": latest,
        "age_hours": max_age,
        "freshness_window_hours": default_freshness,
        "live_scheduler_last_status": live_last_status or None,
        "live_scheduler_consecutive_errors": live_consecutive_errors,
        "live_scheduler_last_run_exception": live_last_run_exception,
        "live_scheduler_last_run_at": job.get("last_run_utc") or None,
        "live_scheduler_last_error": live_last_error,
        "live_scheduler_reconciliation": (
            "owner_approved_known_platform_failure_on_recorded_openclaw_version"
            if known_failure
            else "newer_nonblocking_artifacts_prove_execution_recovery_waiting_natural_canary"
            if recovery_proven
            else "artifact_freshness_governs_escalation_but_last_scheduler_status_is_visible"
            if live_last_run_exception
            else "last_scheduler_status_clean_or_absent"
        ),
        "wf78_tier_semantic_lineage_blocked_count": len(tier_semantic_lineage_blocked),
        "wf78_tier_semantic_lineage_blocked_roles": [item.get("role") for item in tier_semantic_lineage_blocked],
        "expected_artifacts": artifacts,
    }


def operating_signals(operating_spine: dict[str, Any]) -> list[dict[str, Any]]:
    phases = as_list(operating_spine.get("implemented_phases"))
    handoff = next((as_dict(item) for item in phases if as_dict(item).get("name") == "handoff_selectivity"), {})
    results: list[dict[str, Any]] = []
    for signal in as_list(handoff.get("signals")):
        signal_dict = as_dict(signal)
        cls = signal_dict.get("class") if signal_dict.get("class") in SIGNAL_CLASSES else "STALE_OR_NOISE"
        results.append({
            "source": f"operating_spine:{signal_dict.get('source')}",
            "artifact": signal_dict.get("path"),
            "signal_class": cls,
            "attention": "requires_main_attention" if cls in {"MAIN_SESSION_REQUIRED", "BLOCKED", "OWNER_DECISION"} else "quiet_success",
            "status": signal_dict.get("status"),
            "generated_at_utc": None,
            "age_hours": None,
            "reason": signal_dict.get("reason"),
            "next_action": "",
        })
    return results


def signal_from_job(job: dict[str, Any]) -> dict[str, Any]:
    first_artifact = next((item for item in as_list(job.get("expected_artifacts")) if item.get("required")), {})
    return {
        "source": f"cron_job:{job.get('name')}",
        "artifact": first_artifact.get("path"),
        "signal_class": job.get("signal_class"),
        "attention": job.get("attention"),
        "attention_bucket": job.get("attention_bucket"),
        "attention_class": job.get("attention_class"),
        "status": job.get("status"),
        "generated_at_utc": job.get("generated_at_utc"),
        "age_hours": job.get("age_hours"),
        "reason": job.get("reason"),
        "next_action": next_action_for(job),
        "live_scheduler_last_status": job.get("live_scheduler_last_status"),
        "live_scheduler_consecutive_errors": job.get("live_scheduler_consecutive_errors"),
        "live_scheduler_last_run_exception": job.get("live_scheduler_last_run_exception"),
        "live_scheduler_last_run_at": job.get("live_scheduler_last_run_at"),
        "live_scheduler_last_error": job.get("live_scheduler_last_error"),
    }


def next_action_for(job: dict[str, Any]) -> str:
    status = job.get("status")
    if status == "fresh":
        return ""
    if status == "stale":
        return "Inspect the named cron proof artifact before relying on this workflow's freshness."
    if status == "missing_artifact":
        return "Run or repair the producer for the missing required artifact."
    if status == "unregistered":
        return "Add a freshness-spine contract before treating this enabled cron as governed."
    if status == "one_shot_pending":
        return "One-shot follow-up job is scheduled; no standing freshness contract applies."
    if status == "one_shot_scheduler_error":
        return "Inspect the failed one-shot follow-up run; it will not retry on a schedule."
    if status == "blocked":
        return "Inspect the blocked artifact and stop before further consolidation."
    if status == "needs_review":
        return "Route through main session for warning or handoff review."
    if status == "owner_decision":
        return "Route owner-decision packet to Randall; do not infer approval."
    if status == "scheduler_error":
        return "Inspect live cron run history and repair the scheduler execution path before trusting artifact freshness."
    if status == "recovered_waiting_scheduler_canary":
        return "Keep the failed-run history visible and confirm the next natural scheduler run; newer clean artifact proof already exists."
    return ""


def attention_bucket(job: dict[str, Any]) -> str:
    if job.get("standing_review_quiet"):
        return "quiet_success"
    cls = job.get("signal_class")
    if cls in {"BLOCKED", "OWNER_DECISION"}:
        return "urgent_blocked_or_owner_decision"
    if cls == "MAIN_SESSION_REQUIRED":
        return "main_review_queue"
    if cls == "STALE_OR_NOISE":
        return "monitor_only_or_stale"
    return "quiet_success"


def attention_class(job: dict[str, Any], previous_jobs: dict[str, dict[str, Any]]) -> str:
    cls = job.get("signal_class")
    status = job.get("status")
    if cls == "NO_REPLY":
        return "quiet"
    if cls in {"BLOCKED", "OWNER_DECISION"}:
        return "urgent"
    if cls == "STALE_OR_NOISE":
        return "monitor_only"
    previous = previous_jobs.get(str(job.get("name") or ""))
    previous_signal = (previous.get("underlying_signal_class") or previous.get("signal_class")) if previous else None
    previous_status = (previous.get("underlying_status") or previous.get("status")) if previous else None
    previous_reason = (previous.get("underlying_reason") or previous.get("reason")) if previous else None
    current_signal = job.get("underlying_signal_class") or cls
    current_status = job.get("underlying_status") or status
    current_reason = job.get("underlying_reason") or job.get("reason")
    same_signal = (
        previous
        and previous_signal == current_signal
        and previous_status == current_status
        and previous_reason == current_reason
    )
    return "known_monitor_only" if same_signal else "new_or_changed"


def build_payload(
    ledger_path: Path,
    operating_spine_path: Path,
    out_path: Path = DEFAULT_OUT,
    job_contracts: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    ledger = as_dict(load_json(ledger_path))
    operating_spine = as_dict(load_json(operating_spine_path))
    previous = as_dict(load_json(out_path))
    previous_jobs = {
        str(as_dict(job).get("name") or ""): as_dict(job)
        for job in as_list(previous.get("jobs"))
    }
    ledger_jobs = as_list(ledger.get("jobs"))
    contracts = job_contracts or merged_job_contracts()
    openclaw_version = installed_openclaw_version()
    jobs = [
        classify_job(as_dict(job), contracts.get(str(as_dict(job).get("name") or "")), openclaw_version)
        for job in ledger_jobs
    ]
    enabled_jobs = [job for job in jobs if job.get("enabled")]
    unregistered = [job for job in enabled_jobs if job.get("status") == "unregistered"]
    missing_contract = [job for job in enabled_jobs if not as_list(job.get("expected_artifacts"))]
    for job in enabled_jobs:
        job["underlying_signal_class"] = job.get("signal_class")
        job["underlying_status"] = job.get("status")
        job["underlying_reason"] = job.get("reason")
        job["attention_class"] = attention_class(job, previous_jobs)
        if job["attention_class"] == "known_monitor_only":
            job["standing_review_quiet"] = True
            job["standing_review_disposition"] = "unchanged_review_signal_quiet_until_changed"
            job["signal_class"] = "NO_REPLY"
            job["attention"] = "quiet_success"
            job["status"] = "standing_review_quiet"
            job["reason"] = "standing_review_quiet"
        job["attention_bucket"] = attention_bucket(job)
    blocked = [job for job in enabled_jobs if job.get("signal_class") == "BLOCKED"]
    main_required = [job for job in enabled_jobs if job.get("signal_class") in {"MAIN_SESSION_REQUIRED", "OWNER_DECISION"}]
    stale = [job for job in enabled_jobs if job.get("status") == "stale"]
    fresh = [job for job in enabled_jobs if job.get("status") == "fresh"]
    standing_review_quiet = [job for job in enabled_jobs if job.get("standing_review_quiet")]
    live_scheduler_exceptions = [
        {
            "id": job.get("id"),
            "name": job.get("name"),
            "last_status": job.get("live_scheduler_last_status"),
            "consecutive_errors": job.get("live_scheduler_consecutive_errors"),
            "last_error": job.get("live_scheduler_last_error"),
            "artifact_status": job.get("underlying_status") or job.get("status"),
            "signal_class": job.get("underlying_signal_class") or job.get("signal_class"),
            "reconciliation": job.get("live_scheduler_reconciliation"),
        }
        for job in enabled_jobs
        if job.get("live_scheduler_last_run_exception")
    ]
    job_signals = [signal_from_job(job) for job in enabled_jobs]
    all_signals = job_signals + operating_signals(operating_spine)
    attention_buckets = {
        bucket: len([job for job in enabled_jobs if job.get("attention_bucket") == bucket])
        for bucket in (
            "urgent_blocked_or_owner_decision",
            "main_review_queue",
            "monitor_only_or_stale",
            "quiet_success",
        )
    }
    attention_classes = {
        name: len([job for job in enabled_jobs if job.get("attention_class") == name])
        for name in ("urgent", "new_or_changed", "known_monitor_only", "monitor_only", "quiet")
    }
    payload = {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "draft",
        "sources": {
            "cron_operator_ledger": rel(ledger_path),
            "operating_leverage_spine": rel(operating_spine_path),
        },
        "authority_boundary": AUTHORITY_BOUNDARY,
        "contract": {
            "enabled_jobs_must_have_registry_rows": True,
            "enabled_jobs_must_have_expected_artifacts": True,
            "main_session_first_read": rel(out_path),
            "scorecard_should_consume": rel(out_path),
        },
        "summary": {
            "job_count": len(jobs),
            "enabled_job_count": len(enabled_jobs),
            "disabled_job_count": len(jobs) - len(enabled_jobs),
            "fresh_count": len(fresh),
            "stale_count": len(stale),
            "requires_attention_count": len(main_required),
            "urgent_attention_count": attention_buckets["urgent_blocked_or_owner_decision"],
            "review_queue_count": attention_buckets["main_review_queue"],
            "monitor_only_or_stale_count": attention_buckets["monitor_only_or_stale"],
            "quiet_success_count": attention_buckets["quiet_success"],
            "blocked_count": len(blocked),
            "wf78_tier_semantic_lineage_blocked_job_count": len([
                job for job in enabled_jobs
                if int(job.get("wf78_tier_semantic_lineage_blocked_count") or 0) > 0
            ]),
            "wf78_tier_semantic_lineage_blocked_jobs": [
                job.get("name") for job in enabled_jobs
                if int(job.get("wf78_tier_semantic_lineage_blocked_count") or 0) > 0
            ],
            "unregistered_enabled_count": len(unregistered),
            "missing_expected_artifact_contract_count": len(missing_contract),
            "attention_buckets": attention_buckets,
            "attention_classes": attention_classes,
            "implementation_attention_count": attention_classes["urgent"] + attention_classes["new_or_changed"],
            "known_monitor_only_attention_count": attention_classes["known_monitor_only"],
            "standing_review_quiet_count": len(standing_review_quiet),
            "live_scheduler_last_run_exception_count": len(live_scheduler_exceptions),
        },
        "live_scheduler_last_run_exceptions": live_scheduler_exceptions,
        "jobs": jobs,
        "signals": all_signals,
        "operator_recommendation": (
            "Read this spine first for cron freshness. Wake main immediately for urgent_blocked_or_owner_decision. "
            "Create implementation work only for urgent or new_or_changed attention classes. "
            "Batch known_monitor_only review items as review work unless Randall asks or a safety-critical lane is involved. "
            "Treat monitor_only_or_stale as route-time inspection."
        ),
    }
    payload["validation"] = validate_payload(payload)
    if blocked:
        payload["status"] = "blocked"
    elif main_required or stale:
        payload["status"] = "warning"
    else:
        payload["status"] = "ok"
    return payload


def validate_payload(payload: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    boundary = as_dict(payload.get("authority_boundary"))
    for key, expected in AUTHORITY_BOUNDARY.items():
        if boundary.get(key) is not expected:
            errors.append(f"authority_boundary_{key}_not_{str(expected).lower()}")
    enabled = [job for job in as_list(payload.get("jobs")) if as_dict(job).get("enabled")]
    if not enabled:
        errors.append("enabled_jobs_missing")
    for job in enabled:
        job_dict = as_dict(job)
        if job_dict.get("status") == "unregistered":
            errors.append(f"enabled_job_missing_contract:{job_dict.get('name')}")
        if not as_list(job_dict.get("expected_artifacts")) and job_dict.get("status") not in {"one_shot_pending", "one_shot_scheduler_error"}:
            errors.append(f"enabled_job_missing_expected_artifacts:{job_dict.get('name')}")
        if job_dict.get("signal_class") not in SIGNAL_CLASSES:
            errors.append(f"bad_job_signal_class:{job_dict.get('name')}")
    for signal in as_list(payload.get("signals")):
        signal_dict = as_dict(signal)
        if signal_dict.get("signal_class") not in SIGNAL_CLASSES:
            errors.append(f"bad_signal_class:{signal_dict.get('source')}")
    if as_dict(payload.get("summary")).get("stale_count", 0):
        warnings.append("one_or_more_enabled_jobs_have_stale_artifacts")
    if as_dict(payload.get("summary")).get("requires_attention_count", 0):
        warnings.append("one_or_more_enabled_jobs_require_attention")
    if as_dict(payload.get("summary")).get("blocked_count", 0):
        warnings.append("one_or_more_enabled_jobs_blocked")
    return {"status": "ok" if not errors else "error", "errors": errors, "warnings": warnings}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build read-only cron freshness spine.")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--ledger", default=str(DEFAULT_LEDGER))
    parser.add_argument("--operating-spine", default=str(DEFAULT_OPERATING_SPINE))
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    out = workspace_path(args.out)
    payload = build_payload(workspace_path(args.ledger), workspace_path(args.operating_spine), out_path=out)
    if args.write:
        atomic_write_json(out, payload)
    print(json.dumps({
        "status": payload.get("status"),
        "out": rel(out),
        "summary": payload.get("summary"),
        "validation": payload.get("validation"),
    }, indent=2, sort_keys=True))
    return 1 if args.validate and as_dict(payload.get("validation")).get("status") != "ok" else 0


if __name__ == "__main__":
    raise SystemExit(main())
