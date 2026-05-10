from __future__ import annotations

from copy import deepcopy
from typing import Any

WINDOW_MANIFESTS: dict[str, dict[str, Any]] = {
    "morning": {
        "description": "Pre-open readiness refresh. Rebuilds macro, technical, regime scores, and band-staleness artifacts, then regenerates trigger layer and dashboard.",
        "steps": [
            {"script": "validate_portfolio_config.py", "args": [], "category": "portfolio", "expected_outputs": [], "depends_on": [], "recovery_posture": "fail_chain"},
            {"script": "earnings_calendar_enrichment.py", "args": [], "category": "intelligence", "expected_outputs": ["tmp/earnings-calendar.json"], "depends_on": [], "recovery_posture": "fail_chain"},
            {"script": "policy_expectations_refresh.py", "args": [], "category": "market_data", "expected_outputs": ["tmp/policy-expectations.json"], "depends_on": [], "recovery_posture": "fail_chain"},
            {"script": "credit_spread_refresh.py", "args": [], "category": "market_data", "expected_outputs": ["tmp/credit-spreads.json"], "depends_on": [], "recovery_posture": "fail_chain"},
            {"script": "breadth_refresh.py", "args": [], "category": "market_data", "expected_outputs": ["tmp/breadth-state.json"], "depends_on": [], "recovery_posture": "fail_chain"},
            {"script": "market_state_refresh.py", "args": [], "category": "market_data", "expected_outputs": ["tmp/market-state.json"], "depends_on": ["policy_expectations_refresh.py", "credit_spread_refresh.py", "breadth_refresh.py"], "recovery_posture": "fail_chain"},
            {"script": "macro_regime_refresh.py", "args": [], "category": "market_data", "expected_outputs": ["tmp/macro-regime.json"], "depends_on": ["market_state_refresh.py", "credit_spread_refresh.py", "breadth_refresh.py"], "recovery_posture": "fail_chain"},
            {"script": "technical_refresh.py", "args": [], "category": "portfolio", "expected_outputs": ["tmp/technical-refresh.json"], "depends_on": [], "recovery_posture": "fail_chain"},
            {"script": "regime_scoring_refresh.py", "args": [], "category": "portfolio", "expected_outputs": ["tmp/regime-scores.json"], "depends_on": ["macro_regime_refresh.py", "technical_refresh.py"], "recovery_posture": "fail_chain"},
            {"script": "band_refresh.py", "args": [], "category": "portfolio", "expected_outputs": ["tmp/band-proposals.json"], "depends_on": ["technical_refresh.py"], "recovery_posture": "fail_chain"},
            {"script": "entry_band_fetch.py", "args": ["--all-tracked", "--html"], "category": "portfolio", "expected_outputs": [], "depends_on": ["band_refresh.py"], "recovery_posture": "fail_chain"},
            {"script": "generate_entry_band_status.py", "args": [], "category": "portfolio", "expected_outputs": [], "depends_on": ["entry_band_fetch.py"], "recovery_posture": "fail_chain"},
            {"script": "deployment_check.py", "args": [], "category": "validation", "expected_outputs": ["tmp/deployment-check.json"], "depends_on": ["technical_refresh.py", "band_refresh.py", "earnings_calendar_enrichment.py"], "recovery_posture": "fail_chain"},
            {"script": "trigger_sheet_refresh.py", "args": [], "category": "portfolio", "expected_outputs": ["tmp/trigger-sheet.json"], "depends_on": ["deployment_check.py"], "recovery_posture": "fail_chain"},
            {"script": "positioning_ranking_refresh.py", "args": [], "category": "portfolio", "expected_outputs": [], "depends_on": ["trigger_sheet_refresh.py", "regime_scoring_refresh.py"], "recovery_posture": "fail_chain"},
            {"script": "post_earnings_prep.py", "args": [], "category": "intelligence", "expected_outputs": ["tmp/post-earnings-prep.json"], "depends_on": ["earnings_calendar_enrichment.py"], "recovery_posture": "fail_chain"},
            {"script": "post_earnings_note_targets.py", "args": [], "category": "intelligence", "expected_outputs": ["tmp/post-earnings-note-targets.json"], "depends_on": ["post_earnings_prep.py"], "recovery_posture": "fail_chain"},
            {"script": "universe_consistency_check.py", "args": [], "category": "validation", "expected_outputs": [], "depends_on": ["technical_refresh.py", "deployment_check.py", "trigger_sheet_refresh.py"], "recovery_posture": "fail_chain"},
            {"script": "test_dashboard_acceptance.py", "args": [], "category": "validation", "expected_outputs": ["tmp/dashboard-acceptance-report.json"], "depends_on": ["market_state_refresh.py", "deployment_check.py", "trigger_sheet_refresh.py"], "recovery_posture": "fail_chain"},
            {"script": "generate_dashboard.py", "args": [], "category": "summary", "expected_outputs": ["tmp/veritas-command-center.html"], "depends_on": ["market_state_refresh.py", "technical_refresh.py", "deployment_check.py"], "recovery_posture": "fail_chain"},
            {"script": "validate_dashboard_state.py", "args": ["--write"], "category": "validation", "expected_outputs": ["tmp/dashboard-validation.json"], "depends_on": ["generate_dashboard.py"], "recovery_posture": "fail_chain"},
            {"script": "workbook_export.py", "args": [], "category": "summary", "expected_outputs": [], "depends_on": ["validate_dashboard_state.py"], "recovery_posture": "fail_chain"},
            {"script": "premarket_snapshot.py", "args": [], "category": "summary", "expected_outputs": ["tmp/premarket-snapshot.json"], "depends_on": ["trigger_sheet_refresh.py", "validate_dashboard_state.py"], "recovery_posture": "fail_chain"},
            {"script": "summary_brief_packet.py", "args": ["--window", "morning"], "category": "summary", "expected_outputs": ["tmp/premarket-brief-input.json"], "depends_on": ["premarket_snapshot.py", "market_state_refresh.py", "trigger_sheet_refresh.py", "earnings_calendar_enrichment.py", "validate_dashboard_state.py"], "recovery_posture": "fail_chain"},
            {"script": "pipeline_state_consistency_check.py", "args": [], "category": "validation", "expected_outputs": ["tmp/pipeline-state-consistency.json"], "depends_on": ["trigger_sheet_refresh.py", "deployment_check.py", "premarket_snapshot.py"], "recovery_posture": "fail_chain"},
            {"script": "run_summary_refresh.py", "args": ["--window", "morning"], "category": "summary", "expected_outputs": ["tmp/run-summary-morning.json"], "depends_on": ["premarket_snapshot.py", "summary_brief_packet.py", "validate_dashboard_state.py"], "recovery_posture": "recovery_finalizer"},
            {"script": "dashboard_run_summary_consumer.py", "args": ["--window", "morning"], "category": "summary", "expected_outputs": [], "depends_on": ["run_summary_refresh.py"], "recovery_posture": "recovery_finalizer"},
            {"script": "deployment_readiness_surface.py", "args": ["--window", "morning"], "category": "summary", "expected_outputs": ["tmp/deployment-readiness-surface.json"], "depends_on": ["trigger_sheet_refresh.py", "validate_dashboard_state.py", "run_summary_refresh.py"], "recovery_posture": "fail_chain"},
            {"script": "market_intelligence_event_router.py", "args": ["--window", "morning"], "category": "intelligence", "expected_outputs": ["tmp/market-intelligence-events-morning.json"], "depends_on": ["deployment_readiness_surface.py", "band_refresh.py", "validate_dashboard_state.py", "market_state_refresh.py"], "recovery_posture": "fail_chain"},
            {"script": "daily_review_objects.py", "args": ["--window", "morning"], "category": "summary", "expected_outputs": ["tmp/daily-review-objects-morning.json"], "depends_on": ["deployment_readiness_surface.py", "market_intelligence_event_router.py", "premarket_snapshot.py", "run_summary_refresh.py", "validate_dashboard_state.py"], "recovery_posture": "fail_chain"},
        ],
    },
    "post-close": {
        "description": "End-of-day refresh after the close. Refreshes earnings timing, rebuilds readiness, regime scores, and band-staleness artifacts, then stages post-earnings follow-up packets.",
        "steps": [
            {"script": "earnings_calendar_enrichment.py", "args": [], "category": "intelligence", "expected_outputs": ["tmp/earnings-calendar.json"], "depends_on": [], "recovery_posture": "fail_chain"},
            {"script": "validate_portfolio_config.py", "args": [], "category": "portfolio", "expected_outputs": [], "depends_on": [], "recovery_posture": "fail_chain"},
            {"script": "policy_expectations_refresh.py", "args": [], "category": "market_data", "expected_outputs": ["tmp/policy-expectations.json"], "depends_on": [], "recovery_posture": "fail_chain"},
            {"script": "credit_spread_refresh.py", "args": [], "category": "market_data", "expected_outputs": ["tmp/credit-spreads.json"], "depends_on": [], "recovery_posture": "fail_chain"},
            {"script": "breadth_refresh.py", "args": [], "category": "market_data", "expected_outputs": ["tmp/breadth-state.json"], "depends_on": [], "recovery_posture": "fail_chain"},
            {"script": "market_state_refresh.py", "args": [], "category": "market_data", "expected_outputs": ["tmp/market-state.json"], "depends_on": ["policy_expectations_refresh.py", "credit_spread_refresh.py", "breadth_refresh.py"], "recovery_posture": "fail_chain"},
            {"script": "macro_regime_refresh.py", "args": [], "category": "market_data", "expected_outputs": ["tmp/macro-regime.json"], "depends_on": ["market_state_refresh.py", "credit_spread_refresh.py", "breadth_refresh.py"], "recovery_posture": "fail_chain"},
            {"script": "technical_refresh.py", "args": [], "category": "portfolio", "expected_outputs": ["tmp/technical-refresh.json"], "depends_on": [], "recovery_posture": "fail_chain"},
            {"script": "regime_scoring_refresh.py", "args": [], "category": "portfolio", "expected_outputs": ["tmp/regime-scores.json"], "depends_on": ["macro_regime_refresh.py", "technical_refresh.py"], "recovery_posture": "fail_chain"},
            {"script": "band_refresh.py", "args": [], "category": "portfolio", "expected_outputs": ["tmp/band-proposals.json"], "depends_on": ["technical_refresh.py"], "recovery_posture": "fail_chain"},
            {"script": "entry_band_fetch.py", "args": ["--all-tracked", "--html"], "category": "portfolio", "expected_outputs": [], "depends_on": ["band_refresh.py"], "recovery_posture": "fail_chain"},
            {"script": "generate_entry_band_status.py", "args": [], "category": "portfolio", "expected_outputs": [], "depends_on": ["entry_band_fetch.py"], "recovery_posture": "fail_chain"},
            {"script": "deployment_check.py", "args": [], "category": "validation", "expected_outputs": ["tmp/deployment-check.json"], "depends_on": ["technical_refresh.py", "band_refresh.py", "earnings_calendar_enrichment.py"], "recovery_posture": "fail_chain"},
            {"script": "trigger_sheet_refresh.py", "args": [], "category": "portfolio", "expected_outputs": ["tmp/trigger-sheet.json"], "depends_on": ["deployment_check.py"], "recovery_posture": "fail_chain"},
            {"script": "positioning_ranking_refresh.py", "args": [], "category": "portfolio", "expected_outputs": [], "depends_on": ["trigger_sheet_refresh.py", "regime_scoring_refresh.py"], "recovery_posture": "fail_chain"},
            {"script": "post_earnings_prep.py", "args": [], "category": "intelligence", "expected_outputs": ["tmp/post-earnings-prep.json"], "depends_on": ["earnings_calendar_enrichment.py"], "recovery_posture": "fail_chain"},
            {"script": "post_earnings_note_targets.py", "args": [], "category": "intelligence", "expected_outputs": ["tmp/post-earnings-note-targets.json"], "depends_on": ["post_earnings_prep.py"], "recovery_posture": "fail_chain"},
            {"script": "universe_consistency_check.py", "args": [], "category": "validation", "expected_outputs": [], "depends_on": ["technical_refresh.py", "deployment_check.py", "trigger_sheet_refresh.py"], "recovery_posture": "fail_chain"},
            {"script": "test_dashboard_acceptance.py", "args": [], "category": "validation", "expected_outputs": ["tmp/dashboard-acceptance-report.json"], "depends_on": ["market_state_refresh.py", "deployment_check.py", "trigger_sheet_refresh.py"], "recovery_posture": "fail_chain"},
            {"script": "generate_dashboard.py", "args": [], "category": "summary", "expected_outputs": ["tmp/veritas-command-center.html"], "depends_on": ["market_state_refresh.py", "technical_refresh.py", "deployment_check.py"], "recovery_posture": "fail_chain"},
            {"script": "validate_dashboard_state.py", "args": ["--write"], "category": "validation", "expected_outputs": ["tmp/dashboard-validation.json"], "depends_on": ["generate_dashboard.py"], "recovery_posture": "fail_chain"},
            {"script": "workbook_export.py", "args": [], "category": "summary", "expected_outputs": [], "depends_on": ["validate_dashboard_state.py"], "recovery_posture": "fail_chain"},
            {"script": "postmarket_snapshot.py", "args": [], "category": "summary", "expected_outputs": ["tmp/postmarket-snapshot.json"], "depends_on": ["trigger_sheet_refresh.py", "validate_dashboard_state.py"], "recovery_posture": "fail_chain"},
            {"script": "daily_executive_brief.py", "args": [], "category": "summary", "expected_outputs": ["tmp/daily-executive-brief.json"], "depends_on": ["postmarket_snapshot.py", "deployment_check.py", "validate_dashboard_state.py"], "recovery_posture": "fail_chain"},
            {"script": "summary_brief_packet.py", "args": ["--window", "post-close"], "category": "summary", "expected_outputs": ["tmp/postclose-brief-input.json"], "depends_on": ["postmarket_snapshot.py", "daily_executive_brief.py", "market_state_refresh.py", "trigger_sheet_refresh.py", "deployment_check.py", "post_earnings_prep.py", "validate_dashboard_state.py"], "recovery_posture": "fail_chain"},
            {"script": "pipeline_state_consistency_check.py", "args": [], "category": "validation", "expected_outputs": ["tmp/pipeline-state-consistency.json"], "depends_on": ["trigger_sheet_refresh.py", "deployment_check.py", "daily_executive_brief.py", "postmarket_snapshot.py"], "recovery_posture": "fail_chain"},
            {"script": "run_summary_refresh.py", "args": ["--window", "post-close"], "category": "summary", "expected_outputs": ["tmp/run-summary-post-close.json"], "depends_on": ["daily_executive_brief.py", "summary_brief_packet.py", "validate_dashboard_state.py"], "recovery_posture": "recovery_finalizer"},
            {"script": "dashboard_run_summary_consumer.py", "args": ["--window", "post-close"], "category": "summary", "expected_outputs": [], "depends_on": ["run_summary_refresh.py"], "recovery_posture": "recovery_finalizer"},
            {"script": "deployment_readiness_surface.py", "args": ["--window", "post-close"], "category": "summary", "expected_outputs": ["tmp/deployment-readiness-surface.json"], "depends_on": ["trigger_sheet_refresh.py", "validate_dashboard_state.py", "run_summary_refresh.py"], "recovery_posture": "fail_chain"},
            {"script": "market_intelligence_event_router.py", "args": ["--window", "post-close"], "category": "intelligence", "expected_outputs": ["tmp/market-intelligence-events-post-close.json"], "depends_on": ["deployment_readiness_surface.py", "band_refresh.py", "validate_dashboard_state.py", "market_state_refresh.py", "post_earnings_prep.py"], "recovery_posture": "fail_chain"},
            {"script": "daily_review_objects.py", "args": ["--window", "post-close"], "category": "summary", "expected_outputs": ["tmp/daily-review-objects-post-close.json"], "depends_on": ["deployment_readiness_surface.py", "market_intelligence_event_router.py", "daily_executive_brief.py", "postmarket_snapshot.py", "post_earnings_prep.py", "run_summary_refresh.py", "validate_dashboard_state.py"], "recovery_posture": "fail_chain"},
        ],
    },
    "post-earnings": {
        "description": "Event-driven follow-up after a material report lands. Refreshes earnings timing, rebuilds post-earnings packets and selective note targets, then revalidates dashboard trust.",
        "steps": [
            {"script": "earnings_calendar_enrichment.py", "args": [], "category": "intelligence", "expected_outputs": ["tmp/earnings-calendar.json"], "depends_on": [], "recovery_posture": "fail_chain"},
            {"script": "validate_portfolio_config.py", "args": [], "category": "portfolio", "expected_outputs": [], "depends_on": [], "recovery_posture": "fail_chain"},
            {"script": "post_earnings_prep.py", "args": [], "category": "intelligence", "expected_outputs": ["tmp/post-earnings-prep.json"], "depends_on": ["earnings_calendar_enrichment.py"], "recovery_posture": "fail_chain"},
            {"script": "post_earnings_note_targets.py", "args": [], "category": "intelligence", "expected_outputs": ["tmp/post-earnings-note-targets.json"], "depends_on": ["post_earnings_prep.py"], "recovery_posture": "fail_chain"},
            {"script": "positioning_ranking_refresh.py", "args": [], "category": "portfolio", "expected_outputs": [], "depends_on": [], "recovery_posture": "fail_chain"},
            {"script": "universe_consistency_check.py", "args": [], "category": "validation", "expected_outputs": [], "depends_on": ["post_earnings_prep.py"], "recovery_posture": "fail_chain"},
            {"script": "test_dashboard_acceptance.py", "args": [], "category": "validation", "expected_outputs": ["tmp/dashboard-acceptance-report.json"], "depends_on": ["post_earnings_prep.py"], "recovery_posture": "fail_chain"},
            {"script": "generate_dashboard.py", "args": [], "category": "summary", "expected_outputs": ["tmp/veritas-command-center.html"], "depends_on": ["test_dashboard_acceptance.py"], "recovery_posture": "fail_chain"},
            {"script": "validate_dashboard_state.py", "args": ["--write"], "category": "validation", "expected_outputs": ["tmp/dashboard-validation.json"], "depends_on": ["generate_dashboard.py"], "recovery_posture": "fail_chain"},
            {"script": "workbook_export.py", "args": [], "category": "summary", "expected_outputs": [], "depends_on": ["validate_dashboard_state.py"], "recovery_posture": "fail_chain"},
            {"script": "run_summary_refresh.py", "args": ["--window", "post-earnings"], "category": "summary", "expected_outputs": ["tmp/run-summary-post-earnings.json"], "depends_on": ["validate_dashboard_state.py"], "recovery_posture": "recovery_finalizer"},
            {"script": "dashboard_run_summary_consumer.py", "args": ["--window", "post-earnings"], "category": "summary", "expected_outputs": [], "depends_on": ["run_summary_refresh.py"], "recovery_posture": "recovery_finalizer"},
            {"script": "deployment_readiness_surface.py", "args": ["--window", "post-earnings"], "category": "summary", "expected_outputs": ["tmp/deployment-readiness-surface.json"], "depends_on": ["validate_dashboard_state.py", "run_summary_refresh.py"], "recovery_posture": "fail_chain"},
            {"script": "market_intelligence_event_router.py", "args": ["--window", "post-earnings"], "category": "intelligence", "expected_outputs": ["tmp/market-intelligence-events-post-earnings.json"], "depends_on": ["deployment_readiness_surface.py", "validate_dashboard_state.py", "post_earnings_prep.py"], "recovery_posture": "fail_chain"},
            {"script": "daily_review_objects.py", "args": ["--window", "post-earnings"], "category": "summary", "expected_outputs": ["tmp/daily-review-objects-post-earnings.json"], "depends_on": ["deployment_readiness_surface.py", "market_intelligence_event_router.py", "post_earnings_prep.py", "run_summary_refresh.py", "validate_dashboard_state.py"], "recovery_posture": "fail_chain"},
        ],
    },
    "sunday": {
        "description": "Weekly intelligence rebuild. Runs all data layers, auto-scores the tracked universe, generates the Weekly Positioning Review scaffold, syncs the call log, and revalidates the full dashboard.",
        "steps": [
            {"script": "earnings_calendar_enrichment.py", "args": [], "category": "intelligence", "expected_outputs": ["tmp/earnings-calendar.json"], "depends_on": [], "recovery_posture": "fail_chain"},
            {"script": "validate_portfolio_config.py", "args": [], "category": "portfolio", "expected_outputs": [], "depends_on": [], "recovery_posture": "fail_chain"},
            {"script": "policy_expectations_refresh.py", "args": [], "category": "market_data", "expected_outputs": ["tmp/policy-expectations.json"], "depends_on": [], "recovery_posture": "fail_chain"},
            {"script": "credit_spread_refresh.py", "args": [], "category": "market_data", "expected_outputs": ["tmp/credit-spreads.json"], "depends_on": [], "recovery_posture": "fail_chain"},
            {"script": "breadth_refresh.py", "args": [], "category": "market_data", "expected_outputs": ["tmp/breadth-state.json"], "depends_on": [], "recovery_posture": "fail_chain"},
            {"script": "market_state_refresh.py", "args": [], "category": "market_data", "expected_outputs": ["tmp/market-state.json"], "depends_on": ["policy_expectations_refresh.py", "credit_spread_refresh.py", "breadth_refresh.py"], "recovery_posture": "fail_chain"},
            {"script": "macro_regime_refresh.py", "args": [], "category": "market_data", "expected_outputs": ["tmp/macro-regime.json"], "depends_on": ["market_state_refresh.py", "credit_spread_refresh.py", "breadth_refresh.py"], "recovery_posture": "fail_chain"},
            {"script": "technical_refresh.py", "args": [], "category": "portfolio", "expected_outputs": ["tmp/technical-refresh.json"], "depends_on": [], "recovery_posture": "fail_chain"},
            {"script": "regime_scoring_refresh.py", "args": [], "category": "portfolio", "expected_outputs": ["tmp/regime-scores.json"], "depends_on": ["macro_regime_refresh.py", "technical_refresh.py"], "recovery_posture": "fail_chain"},
            {"script": "band_refresh.py", "args": [], "category": "portfolio", "expected_outputs": ["tmp/band-proposals.json"], "depends_on": ["technical_refresh.py"], "recovery_posture": "fail_chain"},
            {"script": "entry_band_fetch.py", "args": ["--all-tracked", "--html"], "category": "portfolio", "expected_outputs": [], "depends_on": ["band_refresh.py"], "recovery_posture": "fail_chain"},
            {"script": "generate_entry_band_status.py", "args": [], "category": "portfolio", "expected_outputs": [], "depends_on": ["entry_band_fetch.py"], "recovery_posture": "fail_chain"},
            {"script": "deployment_check.py", "args": [], "category": "validation", "expected_outputs": ["tmp/deployment-check.json"], "depends_on": ["technical_refresh.py", "band_refresh.py", "earnings_calendar_enrichment.py"], "recovery_posture": "fail_chain"},
            {"script": "trigger_sheet_refresh.py", "args": [], "category": "portfolio", "expected_outputs": ["tmp/trigger-sheet.json"], "depends_on": ["deployment_check.py"], "recovery_posture": "fail_chain"},
            {"script": "positioning_ranking_refresh.py", "args": [], "category": "portfolio", "expected_outputs": [], "depends_on": ["trigger_sheet_refresh.py", "regime_scoring_refresh.py"], "recovery_posture": "fail_chain"},
            {"script": "post_earnings_prep.py", "args": [], "category": "intelligence", "expected_outputs": ["tmp/post-earnings-prep.json"], "depends_on": ["earnings_calendar_enrichment.py"], "recovery_posture": "fail_chain"},
            {"script": "post_earnings_note_targets.py", "args": [], "category": "intelligence", "expected_outputs": ["tmp/post-earnings-note-targets.json"], "depends_on": ["post_earnings_prep.py"], "recovery_posture": "fail_chain"},
            {"script": "call_log_sync.py", "args": [], "category": "intelligence", "expected_outputs": [], "depends_on": [], "recovery_posture": "fail_chain"},
            {"script": "universe_consistency_check.py", "args": [], "category": "validation", "expected_outputs": [], "depends_on": ["technical_refresh.py", "deployment_check.py", "trigger_sheet_refresh.py"], "recovery_posture": "fail_chain"},
            {"script": "test_dashboard_acceptance.py", "args": [], "category": "validation", "expected_outputs": ["tmp/dashboard-acceptance-report.json"], "depends_on": ["market_state_refresh.py", "deployment_check.py", "trigger_sheet_refresh.py"], "recovery_posture": "fail_chain"},
            {"script": "generate_dashboard.py", "args": [], "category": "summary", "expected_outputs": ["tmp/veritas-command-center.html"], "depends_on": ["market_state_refresh.py", "technical_refresh.py", "deployment_check.py"], "recovery_posture": "fail_chain"},
            {"script": "validate_dashboard_state.py", "args": ["--write"], "category": "validation", "expected_outputs": ["tmp/dashboard-validation.json"], "depends_on": ["generate_dashboard.py"], "recovery_posture": "fail_chain"},
            {"script": "workbook_export.py", "args": [], "category": "summary", "expected_outputs": [], "depends_on": ["validate_dashboard_state.py"], "recovery_posture": "fail_chain"},
            {"script": "weekly_review_skeleton.py", "args": [], "category": "summary", "expected_outputs": ["tmp/weekly-review-skeleton.json"], "depends_on": ["trigger_sheet_refresh.py", "deployment_check.py", "regime_scoring_refresh.py"], "recovery_posture": "fail_chain"},
            {"script": "weekly_macro_snapshot.py", "args": [], "category": "summary", "expected_outputs": [], "depends_on": ["market_state_refresh.py", "macro_regime_refresh.py"], "recovery_posture": "fail_chain"},
            {"script": "weekly_intelligence_brief.py", "args": [], "category": "summary", "expected_outputs": [], "depends_on": ["weekly_review_skeleton.py", "weekly_macro_snapshot.py"], "recovery_posture": "fail_chain"},
            {"script": "postmarket_snapshot.py", "args": [], "category": "summary", "expected_outputs": ["tmp/postmarket-snapshot.json"], "depends_on": ["trigger_sheet_refresh.py", "validate_dashboard_state.py"], "recovery_posture": "fail_chain"},
            {"script": "daily_executive_brief.py", "args": [], "category": "summary", "expected_outputs": ["tmp/daily-executive-brief.json"], "depends_on": ["postmarket_snapshot.py", "deployment_check.py", "validate_dashboard_state.py"], "recovery_posture": "fail_chain"},
            {"script": "pipeline_state_consistency_check.py", "args": [], "category": "validation", "expected_outputs": ["tmp/pipeline-state-consistency.json"], "depends_on": ["trigger_sheet_refresh.py", "deployment_check.py", "daily_executive_brief.py", "postmarket_snapshot.py"], "recovery_posture": "fail_chain"},
            {"script": "run_summary_refresh.py", "args": ["--window", "sunday"], "category": "summary", "expected_outputs": ["tmp/run-summary-sunday.json"], "depends_on": ["daily_executive_brief.py", "validate_dashboard_state.py"], "recovery_posture": "recovery_finalizer"},
            {"script": "dashboard_run_summary_consumer.py", "args": ["--window", "sunday"], "category": "summary", "expected_outputs": [], "depends_on": ["run_summary_refresh.py"], "recovery_posture": "recovery_finalizer"},
            {"script": "deployment_readiness_surface.py", "args": ["--window", "sunday"], "category": "summary", "expected_outputs": ["tmp/deployment-readiness-surface.json"], "depends_on": ["trigger_sheet_refresh.py", "validate_dashboard_state.py", "run_summary_refresh.py"], "recovery_posture": "fail_chain"},
            {"script": "market_intelligence_event_router.py", "args": ["--window", "sunday"], "category": "intelligence", "expected_outputs": ["tmp/market-intelligence-events-sunday.json"], "depends_on": ["deployment_readiness_surface.py", "band_refresh.py", "validate_dashboard_state.py", "market_state_refresh.py", "post_earnings_prep.py"], "recovery_posture": "fail_chain"},
            {"script": "daily_review_objects.py", "args": ["--window", "sunday"], "category": "summary", "expected_outputs": ["tmp/daily-review-objects-sunday.json"], "depends_on": ["deployment_readiness_surface.py", "market_intelligence_event_router.py", "daily_executive_brief.py", "postmarket_snapshot.py", "post_earnings_prep.py", "run_summary_refresh.py", "validate_dashboard_state.py"], "recovery_posture": "fail_chain"},
        ],
    },
}

WINDOW_MANIFESTS["full"] = {
    "description": "Alias for post-close for backward compatibility.",
    "alias_of": "post-close",
    "steps": deepcopy(WINDOW_MANIFESTS["post-close"]["steps"]),
}


def window_names() -> list[str]:
    return list(WINDOW_MANIFESTS.keys())


def window_description(window: str) -> str:
    return str(WINDOW_MANIFESTS[window]["description"])


def manifest_steps(window: str) -> list[dict[str, Any]]:
    return deepcopy(WINDOW_MANIFESTS[window]["steps"])


def expected_outputs_by_script(window: str) -> dict[str, list[str]]:
    outputs: dict[str, list[str]] = {}
    for step in manifest_steps(window):
        outputs[step["script"]] = list(step.get("expected_outputs") or [])
    return outputs
