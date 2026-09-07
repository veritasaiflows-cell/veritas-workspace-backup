#!/usr/bin/env python3
"""Audited SQL-consumer retirement policy for the alerts-OS pivot.

This is deliberately an explicit allowlist.  Broad substring matching can
both retire unrelated consumers and miss legacy operators whose names do not
contain the most obvious portfolio terms.
"""
from __future__ import annotations

import re


AUDITED_RETIREMENT_PREFIXES = (
    "scripts/wf67_",
    "scripts/test_wf67_",
    "scripts/wf78_",
    "scripts/test_wf78_",
    "scripts/wf86_",
    "scripts/test_wf86_",
    "scripts/wf87_",
    "scripts/test_wf87_",
)

AUDITED_RETIREMENT_EXACT_PATHS = frozenset({
    "scripts/alpaca_paper_position_sql_refresh.py",
    "scripts/auto_apply_entry_band_maintenance.py",
    "scripts/auto_apply_position_sizing_semantic_sync.py",
    "scripts/autonomous_routing_deployment_cards.py",
    "scripts/capital_deployment_band_integrity_validator.py",
    "scripts/capital_deployment_recommendation_validator.py",
    "scripts/deployment_contract_legacy_read_audit.py",
    "scripts/deployment_contract_migration_validation_bundle.py",
    "scripts/finance_market_deployment_operating_loop.py",
    "scripts/morning_paper_deployment_recommendation_builder.py",
    "scripts/portfolio_mutation_exact_patch_generator.py",
    "scripts/portfolio_mutation_proposal_generator.py",
    "scripts/python_go_wf78_sql_phase2_readiness_parity.py",
    "scripts/reference_band_note_sync.py",
    "scripts/reference_levels_band_proposals_source_migration.py",
    "scripts/reference_levels_wf78_retirement_migration_exception.py",
    "scripts/sector_allocation_decision_matrix.py",
    "scripts/sector_allocation_decision_matrix_cron_runner.py",
    "scripts/sql_canon_tier_routing_refresh.py",
    "scripts/sql_canon_wf78_routing_parity.py",
    "scripts/test_auto_apply_entry_band_maintenance.py",
    "scripts/test_autonomous_routing_deployment_cards.py",
    "scripts/test_capital_deployment_band_integrity_validator.py",
    "scripts/test_morning_paper_deployment_recommendation_builder.py",
    "scripts/test_portfolio_mutation_exact_patch_generator.py",
    "scripts/test_portfolio_mutation_phase4_scoped_apply.py",
    "scripts/test_portfolio_mutation_proposal_schema_validator.py",
    "scripts/test_portfolio_mutation_semantic_patch_generator.py",
    "scripts/test_portfolio_mutation_semantic_preview_bundle.py",
    "scripts/test_portfolio_mutation_standing_approval_artifact.py",
    "scripts/test_portfolio_mutation_validators.py",
    "scripts/test_portfolio_snapshot_patch_proposal.py",
    "scripts/test_reference_levels_band_proposals_source_migration.py",
    "scripts/test_reference_levels_wf78_retirement_migration_exception.py",
    "scripts/test_sql_canon_wf78_routing_parity.py",
    "scripts/test_ticker_intelligence_card_sizing_policy.py",
    "scripts/test_tier_a_trade_grade_coverage_gate.py",
    "scripts/test_tier_ab_band_freshness_cron_guard.py",
    "scripts/test_trade_grade_decision_cards.py",
    "scripts/test_trade_grade_decision_cards_sql_canon.py",
    "scripts/test_trade_grade_full_answer_decision_gate.py",
    "scripts/test_trade_grade_full_answer_macro_context.py",
    "scripts/test_trade_grade_os_freshness_cron_runner.py",
    "scripts/test_trade_grade_os_readiness_rollup.py",
    "scripts/test_trade_grade_repair_conveyor_scope.py",
    "scripts/tier_a_trade_grade_coverage_gate.py",
    "scripts/tier_ab_band_freshness_cron_guard.py",
    "scripts/tier_c_band_status_refresh.py",
    "scripts/trade_grade_decision_cards.py",
    "scripts/trade_grade_decision_os_contract.py",
    "scripts/trade_grade_full_answer_assembler.py",
    "scripts/trade_grade_os_freshness_cron_runner.py",
    "scripts/trade_grade_os_readiness_rollup.py",
    "scripts/trade_grade_repair_conveyor.py",
    "scripts/tuesday_position_sizing_readiness.py",
    "scripts/wf72_entry_stop_reference_helper.py",
    "scripts/wf72_entry_stop_sql_activate.py",
    "scripts/wf85_deployment_timing_gate.py",
    "scripts/wf85_paper_deployment_notification_digest.py",
    "scripts/wf85_paper_deployment_telegram_cron_runner.py",
})

AUDITED_INITIAL_RECORD_COUNT = 192

LEGACY_SIGNAL_PATTERN = re.compile(
    r"(?:portfolio|paper|deployment|position[-_ ]?sizing|sizing[-_ ]?policy|"
    r"trade[-_ ]?grade|sector[-_ ]?allocation|auto_apply_entry_band|entry_stop|"
    r"tier_(?:a|b|c|ab).*band|wf(?:67|78|86|87))",
    re.I,
)


def is_retired_alerts_os_consumer(path: str) -> bool:
    """Return true only for an explicitly audited legacy consumer."""

    normalized = str(path).replace("\\", "/")
    return normalized in AUDITED_RETIREMENT_EXACT_PATHS or normalized.startswith(
        AUDITED_RETIREMENT_PREFIXES
    )


def is_unaudited_legacy_signal(path: str) -> bool:
    """Flag suspicious new paths for review without retiring them implicitly."""

    normalized = str(path).replace("\\", "/")
    return bool(LEGACY_SIGNAL_PATTERN.search(normalized)) and not is_retired_alerts_os_consumer(
        normalized
    )
