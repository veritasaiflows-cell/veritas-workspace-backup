from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

import official_capture_period_registry as _registry

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "scripts"

_REGISTRY_CAPTURE_SCRIPTS: set[str] = {entry.capture_script for entry in _registry.all_periods()}
_OFFICIAL_VALIDATOR_SCRIPT = "official_ir_capture_validator.py"

_CATEGORY_STAGE_MAP = {
    "fundamentals": "fundamentals",
    "market_data": "market_data",
    "portfolio": "portfolio_technical",
    "intelligence": "intelligence",
    "review_only": "review_and_proposals",
    "validation": "validation",
    "summary": "summary_and_reports",
    "history": "state_history",
}


def _stage_for_step(step: dict[str, Any]) -> str:
    script = str(step.get("script") or "")
    category = str(step.get("category") or "")
    if script in {"validate_portfolio_config.py"}:
        return "preflight"
    if script in {"run_summary_refresh.py", "dashboard_run_summary_consumer.py"}:
        return "recovery_finalizers"
    return _CATEGORY_STAGE_MAP.get(category, category or "uncategorized")


def _apply_stage_names(manifests: dict[str, dict[str, Any]]) -> None:
    for manifest in manifests.values():
        for step in manifest.get("steps", []):
            step.setdefault("stage", _stage_for_step(step))


def _apply_registry_paths(manifests: dict[str, dict[str, Any]]) -> None:
    """Route official-capture expected_outputs through the period registry.

    For each capture script registered in the period registry, replace its
    literal expected_outputs with registry-derived paths so future-quarter
    rollforward becomes additive in the registry without manifest churn.
    The official IR capture validator gets registry validation paths.
    """
    validation_outputs = sorted(_registry.validation_outputs())
    for manifest in manifests.values():
        for step in manifest.get("steps", []):
            script = step.get("script")
            if script in _REGISTRY_CAPTURE_SCRIPTS:
                step["expected_outputs"] = _registry.expected_outputs_for_script(script)
            elif script == _OFFICIAL_VALIDATOR_SCRIPT:
                existing = list(step.get("expected_outputs") or [])
                ordered = list(validation_outputs)
                non_capture = [p for p in existing if not p.startswith("tmp/official-ir-captures/")]
                step["expected_outputs"] = non_capture + ordered


WINDOW_MANIFESTS: dict[str, dict[str, Any]] = {
    "morning": {
        "description": "Pre-open readiness refresh. Rebuilds macro, technical, regime scores, and band-staleness artifacts, then regenerates trigger layer and dashboard.",
        "steps": [
            {"script": "validate_portfolio_config.py", "args": [], "category": "portfolio", "expected_outputs": [], "depends_on": [], "recovery_posture": "fail_chain"},
            {"script": "bank_native_sec_concept_probe.py", "args": ["--write"], "category": "fundamentals", "expected_outputs": ["tmp/bank-native-sec-concept-probe.json"], "depends_on": ["validate_portfolio_config.py"], "recovery_posture": "fail_chain", "incremental_skip": False},
            {"script": "fundamental_metrics_refresh.py", "args": [], "category": "fundamentals", "expected_outputs": ["tmp/fundamental-metrics-current.json", "data/fundamentals/fundamentals-quarterly-v1.jsonl"], "depends_on": ["bank_native_sec_concept_probe.py"], "recovery_posture": "fail_chain", "timeout_seconds": 900},
            {"script": "validate_fundamental_metrics.py", "args": ["--write"], "category": "validation", "expected_outputs": ["tmp/fundamental-metrics-validation.json"], "depends_on": ["fundamental_metrics_refresh.py"], "recovery_posture": "ticker_data_quality", "data_quality_artifact": "tmp/fundamental-metrics-validation.json"},
            {"script": "goog_official_ir_capture.py", "args": [], "category": "fundamentals", "expected_outputs": [], "depends_on": ["validate_fundamental_metrics.py"], "recovery_posture": "fail_chain"},
            {"script": "etn_vrt_official_ir_capture.py", "args": [], "category": "fundamentals", "expected_outputs": [], "depends_on": ["validate_fundamental_metrics.py"], "recovery_posture": "fail_chain"},
            {"script": "tech_official_ir_capture.py", "args": [], "category": "fundamentals", "expected_outputs": [], "depends_on": ["validate_fundamental_metrics.py"], "recovery_posture": "fail_chain"},
            {"script": "priority_official_ir_capture.py", "args": [], "category": "fundamentals", "expected_outputs": [], "depends_on": ["validate_fundamental_metrics.py"], "recovery_posture": "fail_chain"},
            {"script": "batch2_official_ir_capture.py", "args": [], "category": "fundamentals", "expected_outputs": [], "depends_on": ["validate_fundamental_metrics.py"], "recovery_posture": "fail_chain"},
            {"script": "batch2b_official_ir_capture.py", "args": [], "category": "fundamentals", "expected_outputs": [], "depends_on": ["validate_fundamental_metrics.py"], "recovery_posture": "fail_chain"},
            {"script": "longtail_official_ir_capture.py", "args": [], "category": "fundamentals", "expected_outputs": [], "depends_on": ["validate_fundamental_metrics.py"], "recovery_posture": "fail_chain"},
            {"script": "official_ir_capture_validator.py", "args": ["--all", "--write"], "category": "validation", "expected_outputs": [] , "depends_on": ["goog_official_ir_capture.py", "etn_vrt_official_ir_capture.py", "tech_official_ir_capture.py", "priority_official_ir_capture.py", "batch2_official_ir_capture.py", "batch2b_official_ir_capture.py", "longtail_official_ir_capture.py"], "recovery_posture": "fail_chain"},
            {"script": "fundamental_ir_reconciliation_packets.py", "args": ["--write"], "category": "fundamentals", "expected_outputs": ["tmp/fundamental-ir-reconciliation-packets.json"], "depends_on": ["official_ir_capture_validator.py"], "recovery_posture": "fail_chain"},
            {"script": "wf70_wf66_official_evidence_spine.py", "args": [], "category": "validation", "expected_outputs": ["tmp/wf70-wf66-official-evidence-spine.json", "tmp/wf70-wf66-official-evidence-spine-validation.json"], "depends_on": ["fundamental_ir_reconciliation_packets.py"], "recovery_posture": "fail_chain"},
            {"script": "wf70_wf66_official_evidence_spine.py", "args": ["--validate-only"], "category": "validation", "expected_outputs": ["tmp/wf70-wf66-official-evidence-spine-validation.json"], "depends_on": ["wf70_wf66_official_evidence_spine.py"], "recovery_posture": "fail_chain"},
            {"script": "validate_fundamental_ir_reconciliation.py", "args": ["--write"], "category": "validation", "expected_outputs": ["tmp/fundamental-ir-reconciliation-validation.json"], "depends_on": ["wf70_wf66_official_evidence_spine.py"], "recovery_posture": "fail_chain"},
            {"script": "official_earnings_bridge.py", "args": ["--write"], "category": "fundamentals", "expected_outputs": ["tmp/official-earnings-bridge.json"], "depends_on": ["validate_fundamental_ir_reconciliation.py"], "recovery_posture": "fail_chain"},
            {"script": "validate_official_earnings_bridge.py", "args": ["--write"], "category": "validation", "expected_outputs": ["tmp/official-earnings-bridge-validation.json"], "depends_on": ["official_earnings_bridge.py"], "recovery_posture": "fail_chain"},
            {"script": "earnings_calendar_enrichment.py", "args": [], "category": "intelligence", "expected_outputs": ["tmp/earnings-calendar.json"], "depends_on": [], "recovery_posture": "fail_chain"},
            {"script": "earnings_date_source_confidence.py", "args": [], "category": "intelligence", "expected_outputs": ["tmp/earnings-date-source-confidence.json"], "depends_on": ["earnings_calendar_enrichment.py"], "recovery_posture": "fail_chain"},
            {"script": "event_calendar_rollforward.py", "args": [], "category": "intelligence", "expected_outputs": ["tmp/event-calendar-rollforward.json"], "depends_on": ["earnings_calendar_enrichment.py", "earnings_date_source_confidence.py"], "recovery_posture": "fail_chain"},
            {"script": "event_calendar_apply.py", "args": ["--apply"], "category": "intelligence", "expected_outputs": ["tmp/event-calendar-apply.json"], "depends_on": ["event_calendar_rollforward.py"], "recovery_posture": "fail_chain"},
            {"script": "policy_expectations_refresh.py", "args": [], "category": "market_data", "expected_outputs": ["tmp/policy-expectations.json"], "depends_on": [], "recovery_posture": "fail_chain"},
            {"script": "credit_spread_refresh.py", "args": [], "category": "market_data", "expected_outputs": ["tmp/credit-spreads.json"], "depends_on": [], "recovery_posture": "fail_chain"},
            {"script": "breadth_refresh.py", "args": [], "category": "market_data", "expected_outputs": ["tmp/breadth-state.json"], "depends_on": [], "recovery_posture": "fail_chain"},
            {"script": "market_state_refresh.py", "args": [], "category": "market_data", "expected_outputs": ["tmp/market-state.json"], "depends_on": ["policy_expectations_refresh.py", "credit_spread_refresh.py", "breadth_refresh.py"], "recovery_posture": "fail_chain"},
            {"script": "macro_event_calendar.py", "args": ["--write", "--validate"], "category": "market_data", "expected_outputs": ["tmp/macro-event-calendar.json"], "depends_on": ["market_state_refresh.py"], "recovery_posture": "fail_chain"},
            {"script": "macro_metrics_ingest.py", "args": ["--write", "--validate"], "category": "market_data", "expected_outputs": ["tmp/macro-metrics-current.json"], "depends_on": ["macro_event_calendar.py"], "recovery_posture": "fail_chain"},
            {"script": "macro_signal_spine.py", "args": ["--write", "--validate"], "category": "market_data", "expected_outputs": ["tmp/macro-signal-spine.json"], "depends_on": ["macro_metrics_ingest.py", "market_state_refresh.py"], "recovery_posture": "fail_chain"},
            {"script": "macro_energy_supply_ingest.py", "args": ["--write", "--validate"], "category": "market_data", "expected_outputs": ["tmp/macro-energy-supply.json"], "depends_on": ["market_state_refresh.py"], "recovery_posture": "fail_chain"},
            {"script": "macro_geopolitical_sweep.py", "args": ["--write", "--validate"], "category": "market_data", "expected_outputs": ["tmp/macro-geopolitical-sweep.json"], "depends_on": ["macro_event_calendar.py"], "recovery_posture": "fail_chain"},
            {"script": "macro_regime_refresh.py", "args": [], "category": "market_data", "expected_outputs": ["tmp/macro-regime.json"], "depends_on": ["market_state_refresh.py", "credit_spread_refresh.py", "breadth_refresh.py", "macro_metrics_ingest.py"], "recovery_posture": "fail_chain"},
            {"script": "small_mid_cap_regime_feed.py", "args": ["--window", "morning"], "category": "market_data", "expected_outputs": ["tmp/small-mid-cap-regime-feed.json"], "depends_on": ["market_state_refresh.py"], "recovery_posture": "fail_chain"},
            {"script": "historical_regime_event_library.py", "args": ["--write", "--validate"], "category": "review_only", "expected_outputs": ["tmp/historical-regime-event-library.json"], "depends_on": ["small_mid_cap_regime_feed.py"], "recovery_posture": "fail_chain"},
            {"script": "current_regime_analog_matcher.py", "args": ["--write", "--validate"], "category": "review_only", "expected_outputs": ["tmp/current-regime-analog-match.json"], "depends_on": ["historical_regime_event_library.py", "small_mid_cap_regime_feed.py"], "recovery_posture": "fail_chain"},
            {"script": "macro_judgment_draft.py", "args": ["--write", "--validate"], "category": "market_data", "expected_outputs": ["tmp/macro-judgment-draft.json"], "depends_on": ["macro_regime_refresh.py", "macro_metrics_ingest.py", "macro_signal_spine.py", "macro_event_calendar.py", "macro_energy_supply_ingest.py", "macro_geopolitical_sweep.py", "current_regime_analog_matcher.py"], "recovery_posture": "fail_chain"},
            {"script": "json_sql_promotion_index.py", "args": ["--write", "--validate"], "category": "summary", "expected_outputs": ["tmp/json-sql-promotion-index.json", "tmp/json-sql-promotion-registry.json", "tmp/json-sql-promotion-index.sqlite"], "depends_on": ["macro_judgment_draft.py"], "recovery_posture": "fail_chain"},
            {"script": "technical_refresh.py", "args": [], "category": "portfolio", "expected_outputs": ["tmp/technical-refresh.json"], "depends_on": [], "recovery_posture": "fail_chain"},
            {"script": "band_refresh.py", "args": [], "category": "portfolio", "expected_outputs": ["tmp/band-proposals.json"], "depends_on": ["technical_refresh.py"], "recovery_posture": "fail_chain"},
            {"script": "auto_apply_entry_band_maintenance.py", "args": ["--apply"], "category": "portfolio", "expected_outputs": ["tmp/auto-band-apply.json"], "depends_on": ["band_refresh.py"], "recovery_posture": "fail_chain"},
            {"script": "reference_band_note_sync.py", "args": ["--apply"], "category": "portfolio", "expected_outputs": ["tmp/reference-band-note-sync.json"], "depends_on": ["auto_apply_entry_band_maintenance.py"], "recovery_posture": "fail_chain"},
            {"script": "entry_band_fetch.py", "args": ["--all-tracked", "--html"], "category": "portfolio", "expected_outputs": ["tmp/entry-band-data/_batch-manifest.json"], "depends_on": ["reference_band_note_sync.py"], "recovery_posture": "fail_chain"},
            {"script": "generate_entry_band_status.py", "args": [], "category": "portfolio", "expected_outputs": ["tmp/entry-band-status.html"], "depends_on": ["entry_band_fetch.py"], "recovery_posture": "fail_chain"},
            {"script": "deployment_check.py", "args": [], "category": "validation", "expected_outputs": ["tmp/deployment-check.json"], "depends_on": ["technical_refresh.py", "band_refresh.py", "earnings_calendar_enrichment.py"], "recovery_posture": "fail_chain"},
            {"script": "trigger_sheet_refresh.py", "args": [], "category": "portfolio", "expected_outputs": ["tmp/trigger-sheet.json"], "depends_on": ["deployment_check.py"], "recovery_posture": "fail_chain"},
            {"script": "canon_volatile_execution_board_sync.py", "args": ["--apply", "--strict-exit"], "category": "portfolio", "expected_outputs": ["tmp/canon-volatile-execution-board-sync.json"], "depends_on": ["technical_refresh.py", "deployment_check.py", "trigger_sheet_refresh.py", "auto_apply_entry_band_maintenance.py"], "recovery_posture": "fail_chain"},
            {"script": "sql_canon_field_family_preflight.py", "args": ["--write"], "category": "validation", "expected_outputs": ["tmp/sql-canon-low-risk-field-family-preflight.json"], "depends_on": ["canon_volatile_execution_board_sync.py"], "recovery_posture": "fail_chain"},
            {"script": "wf72_entry_stop_sql_activate.py", "args": ["--batch", "all", "--validate-only"], "category": "validation", "expected_outputs": ["tmp/wf72-entry-stop-sql-activation-validation.json"], "depends_on": ["sql_canon_field_family_preflight.py"], "recovery_posture": "fail_chain"},
            {"script": "canon_drift_freshness_gate.py", "args": ["--write", "--strict-exit"], "category": "validation", "expected_outputs": ["tmp/canon-drift-freshness-gate.json"], "depends_on": ["wf72_entry_stop_sql_activate.py"], "recovery_posture": "fail_chain"},
            {"script": "regime_scoring_refresh.py", "args": [], "category": "portfolio", "expected_outputs": ["tmp/regime-scores.json"], "depends_on": ["macro_regime_refresh.py", "technical_refresh.py", "trigger_sheet_refresh.py", "deployment_check.py"], "recovery_posture": "fail_chain"},
            {"script": "positioning_ranking_refresh.py", "args": [], "category": "portfolio", "expected_outputs": [], "depends_on": ["trigger_sheet_refresh.py", "regime_scoring_refresh.py"], "recovery_posture": "fail_chain"},
            {"script": "post_earnings_prep.py", "args": [], "category": "intelligence", "expected_outputs": ["tmp/post-earnings-prep.json"], "depends_on": ["earnings_calendar_enrichment.py"], "recovery_posture": "fail_chain"},
            {"script": "post_earnings_note_targets.py", "args": [], "category": "intelligence", "expected_outputs": ["tmp/post-earnings-note-targets.json"], "depends_on": ["post_earnings_prep.py"], "recovery_posture": "fail_chain"},
            {"script": "universe_consistency_check.py", "args": [], "category": "validation", "expected_outputs": [], "depends_on": ["technical_refresh.py", "deployment_check.py", "trigger_sheet_refresh.py"], "recovery_posture": "fail_chain"},
            {"script": "test_dashboard_acceptance.py", "args": [], "category": "validation", "expected_outputs": ["tmp/dashboard-acceptance-report.json"], "depends_on": ["market_state_refresh.py", "deployment_check.py", "trigger_sheet_refresh.py", "canon_volatile_execution_board_sync.py", "canon_drift_freshness_gate.py"], "recovery_posture": "fail_chain"},
            {"script": "generate_dashboard.py", "args": [], "category": "summary", "expected_outputs": ["tmp/veritas-command-center.html"], "depends_on": ["market_state_refresh.py", "technical_refresh.py", "deployment_check.py"], "recovery_posture": "fail_chain"},
            {"script": "validate_dashboard_state.py", "args": ["--write"], "category": "validation", "expected_outputs": ["tmp/dashboard-validation.json"], "depends_on": ["generate_dashboard.py"], "recovery_posture": "fail_chain"},
            {"script": "workbook_export.py", "args": [], "category": "summary", "expected_outputs": [], "depends_on": ["validate_dashboard_state.py"], "recovery_posture": "fail_chain"},
            {"script": "premarket_snapshot.py", "args": [], "category": "summary", "expected_outputs": ["tmp/premarket-snapshot.json"], "depends_on": ["trigger_sheet_refresh.py", "validate_dashboard_state.py"], "recovery_posture": "fail_chain"},
            {"script": "snapshot_contract_check.py", "args": ["--window", "morning"], "category": "validation", "expected_outputs": ["tmp/snapshot-contract-check.json"], "depends_on": ["trigger_sheet_refresh.py", "premarket_snapshot.py"], "recovery_posture": "fail_chain"},
            {"script": "summary_brief_packet.py", "args": ["--window", "morning"], "category": "summary", "expected_outputs": ["tmp/premarket-brief-input.json"], "depends_on": ["premarket_snapshot.py", "snapshot_contract_check.py", "market_state_refresh.py", "trigger_sheet_refresh.py", "earnings_calendar_enrichment.py", "validate_dashboard_state.py"], "recovery_posture": "fail_chain"},
            {"script": "review_brief_report.py", "args": ["--window", "morning"], "category": "summary", "expected_outputs": ["tmp/reports/premarket-review-brief-latest.json", "tmp/reports/premarket-review-brief-latest.html"], "depends_on": ["summary_brief_packet.py"], "recovery_posture": "fail_chain"},
            {"script": "pipeline_state_consistency_check.py", "args": ["--window", "morning"], "category": "validation", "expected_outputs": ["tmp/pipeline-state-consistency.json"], "depends_on": ["trigger_sheet_refresh.py", "deployment_check.py", "premarket_snapshot.py", "snapshot_contract_check.py"], "recovery_posture": "fail_chain"},
            {"script": "run_summary_refresh.py", "args": ["--window", "morning"], "category": "summary", "expected_outputs": ["tmp/run-summary-morning.json"], "depends_on": ["premarket_snapshot.py", "summary_brief_packet.py", "review_brief_report.py", "validate_dashboard_state.py"], "recovery_posture": "recovery_finalizer"},
            {"script": "dashboard_run_summary_consumer.py", "args": ["--window", "morning"], "category": "summary", "expected_outputs": [], "depends_on": ["run_summary_refresh.py"], "recovery_posture": "recovery_finalizer"},
            {"script": "deployment_readiness_surface.py", "args": ["--window", "morning"], "category": "summary", "expected_outputs": ["tmp/deployment-readiness-surface.json"], "depends_on": ["trigger_sheet_refresh.py", "validate_dashboard_state.py", "run_summary_refresh.py"], "recovery_posture": "fail_chain"},
            {"script": "daily_price_trend_signals.py", "args": ["--window", "morning"], "category": "summary", "expected_outputs": ["tmp/daily-price-trend-signals.json"], "depends_on": ["deployment_readiness_surface.py", "band_refresh.py", "technical_refresh.py", "validate_dashboard_state.py"], "recovery_posture": "fail_chain"},
            {"script": "market_intelligence_event_router.py", "args": ["--window", "morning"], "category": "intelligence", "expected_outputs": ["tmp/market-intelligence-events-morning.json"], "depends_on": ["deployment_readiness_surface.py", "band_refresh.py", "validate_dashboard_state.py", "market_state_refresh.py"], "recovery_posture": "fail_chain"},
            {"script": "sector_correlation_check.py", "args": ["--window", "morning"], "category": "validation", "expected_outputs": ["tmp/sector-correlation-check.json"], "depends_on": ["deployment_readiness_surface.py", "trigger_sheet_refresh.py", "band_refresh.py"], "recovery_posture": "fail_chain"},
            {"script": "sector_expansion_board.py", "args": ["--window", "morning"], "category": "summary", "expected_outputs": ["tmp/sector-expansion-board.json"], "depends_on": ["sector_correlation_check.py", "breadth_refresh.py", "market_state_refresh.py"], "recovery_posture": "fail_chain"},
            {"script": "watchlist_promotion_radar.py", "args": ["--write"], "category": "review_only", "expected_outputs": ["tmp/watchlist-promotion-radar.json"], "depends_on": ["deployment_check.py", "trigger_sheet_refresh.py", "sector_expansion_board.py", "fundamental_ir_reconciliation_packets.py"], "recovery_posture": "fail_chain"},
            {"script": "daily_review_objects.py", "args": ["--window", "morning"], "category": "summary", "expected_outputs": ["tmp/daily-review-objects-morning.json"], "depends_on": ["deployment_readiness_surface.py", "market_intelligence_event_router.py", "sector_correlation_check.py", "sector_expansion_board.py", "watchlist_promotion_radar.py", "premarket_snapshot.py", "run_summary_refresh.py", "validate_dashboard_state.py"], "recovery_posture": "fail_chain"},
            {"script": "portfolio_mutation_proposal_generator.py", "args": ["--window", "morning", "--write"], "category": "review_only", "expected_outputs": ["tmp/portfolio-mutation-proposals/current-capital-deployment-recommendations.json"], "depends_on": ["daily_review_objects.py", "band_refresh.py", "deployment_check.py", "validate_portfolio_config.py"], "recovery_posture": "fail_chain"},
            {"script": "capital_deployment_recommendation_report.py", "args": ["--write-md"], "category": "summary", "expected_outputs": ["tmp/portfolio-mutation-proposals/current-capital-deployment-recommendations.md"], "depends_on": ["portfolio_mutation_proposal_generator.py"], "recovery_posture": "fail_chain"},
            {"script": "capital_deployment_recommendation_validator.py", "args": ["--write"], "category": "validation", "expected_outputs": ["tmp/capital-deployment-recommendation-validation.json"], "depends_on": ["portfolio_mutation_proposal_generator.py", "capital_deployment_recommendation_report.py"], "recovery_posture": "fail_chain"},
            {"script": "auto_apply_position_sizing_semantic_sync.py", "args": ["--apply", "--window", "morning"], "category": "portfolio", "expected_outputs": ["tmp/auto-position-sizing-semantic-sync.json"], "depends_on": ["capital_deployment_recommendation_validator.py"], "recovery_posture": "fail_chain"},
            {"script": "probability_readiness_report.py", "args": ["--write"], "category": "review_only", "expected_outputs": ["tmp/probability-readiness-report.json"], "depends_on": ["auto_apply_position_sizing_semantic_sync.py"], "recovery_posture": "fail_chain"},
            {"script": "probability_readiness_validator.py", "args": ["--write"], "category": "validation", "expected_outputs": ["tmp/probability-readiness-validation.json"], "depends_on": ["probability_readiness_report.py"], "recovery_posture": "fail_chain"},
            {"script": "board_canon_guardrail.py", "args": ["--write"], "category": "validation", "expected_outputs": ["tmp/board-canon-guardrail.json"], "depends_on": ["daily_review_objects.py", "regime_scoring_refresh.py", "trigger_sheet_refresh.py", "deployment_check.py"], "recovery_posture": "fail_chain"},
            {"script": "stale_intelligence_guardrail.py", "args": ["--write"], "category": "validation", "expected_outputs": ["tmp/stale-intelligence-guardrail.json"], "depends_on": ["board_canon_guardrail.py", "daily_review_objects.py", "regime_scoring_refresh.py", "trigger_sheet_refresh.py", "deployment_check.py"], "recovery_posture": "fail_chain"},
            {"script": "canonical_note_patch_proposal.py", "args": ["--write"], "category": "review_only", "expected_outputs": ["tmp/canonical-note-patch-proposal.json"], "depends_on": ["board_canon_guardrail.py", "stale_intelligence_guardrail.py", "daily_review_objects.py", "regime_scoring_refresh.py", "trigger_sheet_refresh.py", "deployment_check.py"], "recovery_posture": "fail_chain"},
            {"script": "full_portfolio_view.py", "args": ["--window", "morning", "--write"], "category": "summary", "expected_outputs": ["tmp/full-portfolio-view.json"], "depends_on": ["canonical_note_patch_proposal.py", "board_canon_guardrail.py", "stale_intelligence_guardrail.py", "regime_scoring_refresh.py", "trigger_sheet_refresh.py", "deployment_check.py"], "recovery_posture": "fail_chain"},
            {"script": "full_portfolio_view_validate.py", "args": ["--window", "morning", "--write"], "category": "validation", "expected_outputs": ["tmp/full-portfolio-view-validation.json"], "depends_on": ["full_portfolio_view.py"], "recovery_posture": "fail_chain"},
            {"script": "portfolio_snapshot_patch_proposal.py", "args": ["--write"], "category": "review_only", "expected_outputs": ["tmp/portfolio-snapshot-patch-proposal.json"], "depends_on": ["full_portfolio_view_validate.py", "full_portfolio_view.py"], "recovery_posture": "fail_chain"},
            {"script": "finance_discrepancy_resolver.py", "args": ["--write"], "category": "review_only", "expected_outputs": ["tmp/finance-discrepancy-resolver.json"], "depends_on": ["canonical_note_patch_proposal.py", "portfolio_snapshot_patch_proposal.py", "board_canon_guardrail.py", "stale_intelligence_guardrail.py"], "recovery_posture": "fail_chain"},
            {"script": "current_window_artifact_index.py", "args": ["--window", "morning", "--write"], "category": "summary", "expected_outputs": ["tmp/current-window-artifacts.json"], "depends_on": ["daily_review_objects.py", "run_summary_refresh.py", "finance_discrepancy_resolver.py"], "recovery_posture": "fail_chain"},
            {"script": "artifact_index.py", "args": ["incremental"], "category": "summary", "expected_outputs": ["tmp/veritas-artifact-index.sqlite"], "depends_on": ["current_window_artifact_index.py"], "recovery_posture": "fail_chain"},
            {"script": "run_summary_refresh.py", "args": ["--window", "morning"], "category": "summary", "expected_outputs": ["tmp/run-summary-morning.json"], "depends_on": ["artifact_index.py"], "recovery_posture": "recovery_finalizer"},
        ],
    },
    "post-close": {
        "description": "End-of-day refresh after the close. Refreshes earnings timing, rebuilds readiness, regime scores, and band-staleness artifacts, then stages post-earnings follow-up packets.",
        "steps": [
            {"script": "earnings_calendar_enrichment.py", "args": [], "category": "intelligence", "expected_outputs": ["tmp/earnings-calendar.json"], "depends_on": [], "recovery_posture": "fail_chain"},
            {"script": "earnings_date_source_confidence.py", "args": [], "category": "intelligence", "expected_outputs": ["tmp/earnings-date-source-confidence.json"], "depends_on": ["earnings_calendar_enrichment.py"], "recovery_posture": "fail_chain"},
            {"script": "event_calendar_rollforward.py", "args": [], "category": "intelligence", "expected_outputs": ["tmp/event-calendar-rollforward.json"], "depends_on": ["earnings_calendar_enrichment.py", "earnings_date_source_confidence.py"], "recovery_posture": "fail_chain"},
            {"script": "event_calendar_apply.py", "args": ["--apply"], "category": "intelligence", "expected_outputs": ["tmp/event-calendar-apply.json"], "depends_on": ["event_calendar_rollforward.py"], "recovery_posture": "fail_chain"},
            {"script": "validate_portfolio_config.py", "args": [], "category": "portfolio", "expected_outputs": [], "depends_on": [], "recovery_posture": "fail_chain"},
            {"script": "bank_native_sec_concept_probe.py", "args": ["--write"], "category": "fundamentals", "expected_outputs": ["tmp/bank-native-sec-concept-probe.json"], "depends_on": ["validate_portfolio_config.py"], "recovery_posture": "fail_chain", "incremental_skip": False},
            {"script": "fundamental_metrics_refresh.py", "args": [], "category": "fundamentals", "expected_outputs": ["tmp/fundamental-metrics-current.json", "data/fundamentals/fundamentals-quarterly-v1.jsonl"], "depends_on": ["bank_native_sec_concept_probe.py"], "recovery_posture": "fail_chain", "timeout_seconds": 900},
            {"script": "validate_fundamental_metrics.py", "args": ["--write"], "category": "validation", "expected_outputs": ["tmp/fundamental-metrics-validation.json"], "depends_on": ["fundamental_metrics_refresh.py"], "recovery_posture": "ticker_data_quality", "data_quality_artifact": "tmp/fundamental-metrics-validation.json"},
            {"script": "goog_official_ir_capture.py", "args": [], "category": "fundamentals", "expected_outputs": [], "depends_on": ["validate_fundamental_metrics.py"], "recovery_posture": "fail_chain"},
            {"script": "etn_vrt_official_ir_capture.py", "args": [], "category": "fundamentals", "expected_outputs": [], "depends_on": ["validate_fundamental_metrics.py"], "recovery_posture": "fail_chain"},
            {"script": "tech_official_ir_capture.py", "args": [], "category": "fundamentals", "expected_outputs": [], "depends_on": ["validate_fundamental_metrics.py"], "recovery_posture": "fail_chain"},
            {"script": "priority_official_ir_capture.py", "args": [], "category": "fundamentals", "expected_outputs": [], "depends_on": ["validate_fundamental_metrics.py"], "recovery_posture": "fail_chain"},
            {"script": "batch2_official_ir_capture.py", "args": [], "category": "fundamentals", "expected_outputs": [], "depends_on": ["validate_fundamental_metrics.py"], "recovery_posture": "fail_chain"},
            {"script": "batch2b_official_ir_capture.py", "args": [], "category": "fundamentals", "expected_outputs": [], "depends_on": ["validate_fundamental_metrics.py"], "recovery_posture": "fail_chain"},
            {"script": "longtail_official_ir_capture.py", "args": [], "category": "fundamentals", "expected_outputs": [], "depends_on": ["validate_fundamental_metrics.py"], "recovery_posture": "fail_chain"},
            {"script": "official_ir_capture_validator.py", "args": ["--all", "--write"], "category": "validation", "expected_outputs": [] , "depends_on": ["goog_official_ir_capture.py", "etn_vrt_official_ir_capture.py", "tech_official_ir_capture.py", "priority_official_ir_capture.py", "batch2_official_ir_capture.py", "batch2b_official_ir_capture.py", "longtail_official_ir_capture.py"], "recovery_posture": "fail_chain"},
            {"script": "fundamental_ir_reconciliation_packets.py", "args": ["--write"], "category": "fundamentals", "expected_outputs": ["tmp/fundamental-ir-reconciliation-packets.json"], "depends_on": ["official_ir_capture_validator.py"], "recovery_posture": "fail_chain"},
            {"script": "wf70_wf66_official_evidence_spine.py", "args": [], "category": "validation", "expected_outputs": ["tmp/wf70-wf66-official-evidence-spine.json", "tmp/wf70-wf66-official-evidence-spine-validation.json"], "depends_on": ["fundamental_ir_reconciliation_packets.py"], "recovery_posture": "fail_chain"},
            {"script": "wf70_wf66_official_evidence_spine.py", "args": ["--validate-only"], "category": "validation", "expected_outputs": ["tmp/wf70-wf66-official-evidence-spine-validation.json"], "depends_on": ["wf70_wf66_official_evidence_spine.py"], "recovery_posture": "fail_chain"},
            {"script": "validate_fundamental_ir_reconciliation.py", "args": ["--write"], "category": "validation", "expected_outputs": ["tmp/fundamental-ir-reconciliation-validation.json"], "depends_on": ["wf70_wf66_official_evidence_spine.py"], "recovery_posture": "fail_chain"},
            {"script": "official_earnings_bridge.py", "args": ["--write"], "category": "fundamentals", "expected_outputs": ["tmp/official-earnings-bridge.json"], "depends_on": ["validate_fundamental_ir_reconciliation.py"], "recovery_posture": "fail_chain"},
            {"script": "validate_official_earnings_bridge.py", "args": ["--write"], "category": "validation", "expected_outputs": ["tmp/official-earnings-bridge-validation.json"], "depends_on": ["official_earnings_bridge.py"], "recovery_posture": "fail_chain"},
            {"script": "policy_expectations_refresh.py", "args": [], "category": "market_data", "expected_outputs": ["tmp/policy-expectations.json"], "depends_on": [], "recovery_posture": "fail_chain"},
            {"script": "credit_spread_refresh.py", "args": [], "category": "market_data", "expected_outputs": ["tmp/credit-spreads.json"], "depends_on": [], "recovery_posture": "fail_chain"},
            {"script": "breadth_refresh.py", "args": [], "category": "market_data", "expected_outputs": ["tmp/breadth-state.json"], "depends_on": [], "recovery_posture": "fail_chain"},
            {"script": "market_state_refresh.py", "args": [], "category": "market_data", "expected_outputs": ["tmp/market-state.json"], "depends_on": ["policy_expectations_refresh.py", "credit_spread_refresh.py", "breadth_refresh.py"], "recovery_posture": "fail_chain"},
            {"script": "macro_event_calendar.py", "args": ["--write", "--validate"], "category": "market_data", "expected_outputs": ["tmp/macro-event-calendar.json"], "depends_on": ["market_state_refresh.py"], "recovery_posture": "fail_chain"},
            {"script": "macro_metrics_ingest.py", "args": ["--write", "--validate"], "category": "market_data", "expected_outputs": ["tmp/macro-metrics-current.json"], "depends_on": ["macro_event_calendar.py"], "recovery_posture": "fail_chain"},
            {"script": "macro_signal_spine.py", "args": ["--write", "--validate"], "category": "market_data", "expected_outputs": ["tmp/macro-signal-spine.json"], "depends_on": ["macro_metrics_ingest.py", "market_state_refresh.py"], "recovery_posture": "fail_chain"},
            {"script": "macro_energy_supply_ingest.py", "args": ["--write", "--validate"], "category": "market_data", "expected_outputs": ["tmp/macro-energy-supply.json"], "depends_on": ["market_state_refresh.py"], "recovery_posture": "fail_chain"},
            {"script": "macro_geopolitical_sweep.py", "args": ["--write", "--validate"], "category": "market_data", "expected_outputs": ["tmp/macro-geopolitical-sweep.json"], "depends_on": ["macro_event_calendar.py"], "recovery_posture": "fail_chain"},
            {"script": "macro_regime_refresh.py", "args": [], "category": "market_data", "expected_outputs": ["tmp/macro-regime.json"], "depends_on": ["market_state_refresh.py", "credit_spread_refresh.py", "breadth_refresh.py", "macro_metrics_ingest.py"], "recovery_posture": "fail_chain"},
            {"script": "small_mid_cap_regime_feed.py", "args": ["--window", "post-close"], "category": "market_data", "expected_outputs": ["tmp/small-mid-cap-regime-feed.json"], "depends_on": ["market_state_refresh.py"], "recovery_posture": "fail_chain"},
            {"script": "historical_regime_event_library.py", "args": ["--write", "--validate"], "category": "review_only", "expected_outputs": ["tmp/historical-regime-event-library.json"], "depends_on": ["small_mid_cap_regime_feed.py"], "recovery_posture": "fail_chain"},
            {"script": "current_regime_analog_matcher.py", "args": ["--write", "--validate"], "category": "review_only", "expected_outputs": ["tmp/current-regime-analog-match.json"], "depends_on": ["historical_regime_event_library.py", "small_mid_cap_regime_feed.py"], "recovery_posture": "fail_chain"},
            {"script": "macro_judgment_draft.py", "args": ["--write", "--validate"], "category": "market_data", "expected_outputs": ["tmp/macro-judgment-draft.json"], "depends_on": ["macro_regime_refresh.py", "macro_metrics_ingest.py", "macro_signal_spine.py", "macro_event_calendar.py", "macro_energy_supply_ingest.py", "macro_geopolitical_sweep.py", "current_regime_analog_matcher.py"], "recovery_posture": "fail_chain"},
            {"script": "json_sql_promotion_index.py", "args": ["--write", "--validate"], "category": "summary", "expected_outputs": ["tmp/json-sql-promotion-index.json", "tmp/json-sql-promotion-registry.json", "tmp/json-sql-promotion-index.sqlite"], "depends_on": ["macro_judgment_draft.py"], "recovery_posture": "fail_chain"},
            {"script": "technical_refresh.py", "args": [], "category": "portfolio", "expected_outputs": ["tmp/technical-refresh.json"], "depends_on": [], "recovery_posture": "fail_chain"},
            {"script": "band_refresh.py", "args": [], "category": "portfolio", "expected_outputs": ["tmp/band-proposals.json"], "depends_on": ["technical_refresh.py"], "recovery_posture": "fail_chain"},
            {"script": "auto_apply_entry_band_maintenance.py", "args": ["--apply"], "category": "portfolio", "expected_outputs": ["tmp/auto-band-apply.json"], "depends_on": ["band_refresh.py"], "recovery_posture": "fail_chain"},
            {"script": "reference_band_note_sync.py", "args": ["--apply"], "category": "portfolio", "expected_outputs": ["tmp/reference-band-note-sync.json"], "depends_on": ["auto_apply_entry_band_maintenance.py"], "recovery_posture": "fail_chain"},
            {"script": "entry_band_fetch.py", "args": ["--all-tracked", "--html"], "category": "portfolio", "expected_outputs": ["tmp/entry-band-data/_batch-manifest.json"], "depends_on": ["reference_band_note_sync.py"], "recovery_posture": "fail_chain"},
            {"script": "generate_entry_band_status.py", "args": [], "category": "portfolio", "expected_outputs": ["tmp/entry-band-status.html"], "depends_on": ["entry_band_fetch.py"], "recovery_posture": "fail_chain"},
            {"script": "deployment_check.py", "args": [], "category": "validation", "expected_outputs": ["tmp/deployment-check.json"], "depends_on": ["technical_refresh.py", "band_refresh.py", "earnings_calendar_enrichment.py"], "recovery_posture": "fail_chain"},
            {"script": "trigger_sheet_refresh.py", "args": [], "category": "portfolio", "expected_outputs": ["tmp/trigger-sheet.json"], "depends_on": ["deployment_check.py"], "recovery_posture": "fail_chain"},
            {"script": "canon_volatile_execution_board_sync.py", "args": ["--apply", "--strict-exit"], "category": "portfolio", "expected_outputs": ["tmp/canon-volatile-execution-board-sync.json"], "depends_on": ["technical_refresh.py", "deployment_check.py", "trigger_sheet_refresh.py", "auto_apply_entry_band_maintenance.py"], "recovery_posture": "fail_chain"},
            {"script": "sql_canon_field_family_preflight.py", "args": ["--write"], "category": "validation", "expected_outputs": ["tmp/sql-canon-low-risk-field-family-preflight.json"], "depends_on": ["canon_volatile_execution_board_sync.py"], "recovery_posture": "fail_chain"},
            {"script": "wf72_entry_stop_sql_activate.py", "args": ["--batch", "all", "--validate-only"], "category": "validation", "expected_outputs": ["tmp/wf72-entry-stop-sql-activation-validation.json"], "depends_on": ["sql_canon_field_family_preflight.py"], "recovery_posture": "fail_chain"},
            {"script": "canon_drift_freshness_gate.py", "args": ["--write", "--strict-exit"], "category": "validation", "expected_outputs": ["tmp/canon-drift-freshness-gate.json"], "depends_on": ["wf72_entry_stop_sql_activate.py"], "recovery_posture": "fail_chain"},
            {"script": "regime_scoring_refresh.py", "args": [], "category": "portfolio", "expected_outputs": ["tmp/regime-scores.json"], "depends_on": ["macro_regime_refresh.py", "technical_refresh.py", "trigger_sheet_refresh.py", "deployment_check.py"], "recovery_posture": "fail_chain"},
            {"script": "positioning_ranking_refresh.py", "args": [], "category": "portfolio", "expected_outputs": [], "depends_on": ["trigger_sheet_refresh.py", "regime_scoring_refresh.py"], "recovery_posture": "fail_chain"},
            {"script": "post_earnings_prep.py", "args": [], "category": "intelligence", "expected_outputs": ["tmp/post-earnings-prep.json"], "depends_on": ["earnings_calendar_enrichment.py"], "recovery_posture": "fail_chain"},
            {"script": "post_earnings_note_targets.py", "args": [], "category": "intelligence", "expected_outputs": ["tmp/post-earnings-note-targets.json"], "depends_on": ["post_earnings_prep.py"], "recovery_posture": "fail_chain"},
            {"script": "universe_consistency_check.py", "args": [], "category": "validation", "expected_outputs": [], "depends_on": ["technical_refresh.py", "deployment_check.py", "trigger_sheet_refresh.py"], "recovery_posture": "fail_chain"},
            {"script": "test_dashboard_acceptance.py", "args": [], "category": "validation", "expected_outputs": ["tmp/dashboard-acceptance-report.json"], "depends_on": ["market_state_refresh.py", "deployment_check.py", "trigger_sheet_refresh.py", "canon_volatile_execution_board_sync.py", "canon_drift_freshness_gate.py"], "recovery_posture": "fail_chain"},
            {"script": "generate_dashboard.py", "args": [], "category": "summary", "expected_outputs": ["tmp/veritas-command-center.html"], "depends_on": ["market_state_refresh.py", "technical_refresh.py", "deployment_check.py"], "recovery_posture": "fail_chain"},
            {"script": "validate_dashboard_state.py", "args": ["--write"], "category": "validation", "expected_outputs": ["tmp/dashboard-validation.json"], "depends_on": ["generate_dashboard.py"], "recovery_posture": "fail_chain"},
            {"script": "workbook_export.py", "args": [], "category": "summary", "expected_outputs": [], "depends_on": ["validate_dashboard_state.py"], "recovery_posture": "fail_chain"},
            {"script": "postmarket_snapshot.py", "args": [], "category": "summary", "expected_outputs": ["tmp/postmarket-snapshot.json"], "depends_on": ["trigger_sheet_refresh.py", "validate_dashboard_state.py"], "recovery_posture": "fail_chain"},
            {"script": "snapshot_contract_check.py", "args": ["--window", "post-close"], "category": "validation", "expected_outputs": ["tmp/snapshot-contract-check.json"], "depends_on": ["trigger_sheet_refresh.py", "postmarket_snapshot.py"], "recovery_posture": "fail_chain"},
            {"script": "daily_executive_brief.py", "args": [], "category": "summary", "expected_outputs": ["tmp/daily-executive-brief.json"], "depends_on": ["postmarket_snapshot.py", "snapshot_contract_check.py", "deployment_check.py", "validate_dashboard_state.py"], "recovery_posture": "fail_chain"},
            {"script": "summary_brief_packet.py", "args": ["--window", "post-close"], "category": "summary", "expected_outputs": ["tmp/postclose-brief-input.json"], "depends_on": ["postmarket_snapshot.py", "snapshot_contract_check.py", "daily_executive_brief.py", "market_state_refresh.py", "trigger_sheet_refresh.py", "deployment_check.py", "post_earnings_prep.py", "validate_dashboard_state.py"], "recovery_posture": "fail_chain"},
            {"script": "pipeline_state_consistency_check.py", "args": ["--window", "post-close"], "category": "validation", "expected_outputs": ["tmp/pipeline-state-consistency.json"], "depends_on": ["trigger_sheet_refresh.py", "deployment_check.py", "daily_executive_brief.py", "postmarket_snapshot.py", "snapshot_contract_check.py"], "recovery_posture": "fail_chain"},
            {"script": "run_summary_refresh.py", "args": ["--window", "post-close"], "category": "summary", "expected_outputs": ["tmp/run-summary-post-close.json"], "depends_on": ["daily_executive_brief.py", "summary_brief_packet.py", "validate_dashboard_state.py"], "recovery_posture": "recovery_finalizer"},
            {"script": "dashboard_run_summary_consumer.py", "args": ["--window", "post-close"], "category": "summary", "expected_outputs": [], "depends_on": ["run_summary_refresh.py"], "recovery_posture": "recovery_finalizer"},
            {"script": "deployment_readiness_surface.py", "args": ["--window", "post-close"], "category": "summary", "expected_outputs": ["tmp/deployment-readiness-surface.json"], "depends_on": ["trigger_sheet_refresh.py", "validate_dashboard_state.py", "run_summary_refresh.py"], "recovery_posture": "fail_chain"},
            {"script": "daily_price_trend_signals.py", "args": ["--window", "post-close"], "category": "summary", "expected_outputs": ["tmp/daily-price-trend-signals.json"], "depends_on": ["deployment_readiness_surface.py", "band_refresh.py", "technical_refresh.py", "validate_dashboard_state.py"], "recovery_posture": "fail_chain"},
            {"script": "market_intelligence_event_router.py", "args": ["--window", "post-close"], "category": "intelligence", "expected_outputs": ["tmp/market-intelligence-events-post-close.json"], "depends_on": ["deployment_readiness_surface.py", "band_refresh.py", "validate_dashboard_state.py", "market_state_refresh.py", "post_earnings_prep.py"], "recovery_posture": "fail_chain"},
            {"script": "sector_correlation_check.py", "args": ["--window", "post-close"], "category": "validation", "expected_outputs": ["tmp/sector-correlation-check.json"], "depends_on": ["deployment_readiness_surface.py", "trigger_sheet_refresh.py", "band_refresh.py"], "recovery_posture": "fail_chain"},
            {"script": "sector_expansion_board.py", "args": ["--window", "post-close"], "category": "summary", "expected_outputs": ["tmp/sector-expansion-board.json"], "depends_on": ["sector_correlation_check.py", "breadth_refresh.py", "market_state_refresh.py"], "recovery_posture": "fail_chain"},
            {"script": "watchlist_promotion_radar.py", "args": ["--write"], "category": "review_only", "expected_outputs": ["tmp/watchlist-promotion-radar.json"], "depends_on": ["deployment_check.py", "trigger_sheet_refresh.py", "sector_expansion_board.py", "fundamental_ir_reconciliation_packets.py"], "recovery_posture": "fail_chain"},
            {"script": "daily_review_objects.py", "args": ["--window", "post-close"], "category": "summary", "expected_outputs": ["tmp/daily-review-objects-post-close.json"], "depends_on": ["deployment_readiness_surface.py", "market_intelligence_event_router.py", "sector_correlation_check.py", "sector_expansion_board.py", "watchlist_promotion_radar.py", "daily_executive_brief.py", "postmarket_snapshot.py", "post_earnings_prep.py", "run_summary_refresh.py", "validate_dashboard_state.py"], "recovery_posture": "fail_chain"},
            {"script": "portfolio_mutation_proposal_generator.py", "args": ["--window", "post-close", "--write"], "category": "review_only", "expected_outputs": ["tmp/portfolio-mutation-proposals/current-capital-deployment-recommendations.json"], "depends_on": ["daily_review_objects.py", "band_refresh.py", "deployment_check.py", "validate_portfolio_config.py"], "recovery_posture": "fail_chain"},
            {"script": "capital_deployment_recommendation_report.py", "args": ["--write-md"], "category": "summary", "expected_outputs": ["tmp/portfolio-mutation-proposals/current-capital-deployment-recommendations.md"], "depends_on": ["portfolio_mutation_proposal_generator.py"], "recovery_posture": "fail_chain"},
            {"script": "capital_deployment_recommendation_validator.py", "args": ["--write"], "category": "validation", "expected_outputs": ["tmp/capital-deployment-recommendation-validation.json"], "depends_on": ["portfolio_mutation_proposal_generator.py", "capital_deployment_recommendation_report.py"], "recovery_posture": "fail_chain"},
            {"script": "auto_apply_position_sizing_semantic_sync.py", "args": ["--apply", "--window", "post-close"], "category": "portfolio", "expected_outputs": ["tmp/auto-position-sizing-semantic-sync.json"], "depends_on": ["capital_deployment_recommendation_validator.py"], "recovery_posture": "fail_chain"},
            {"script": "probability_readiness_report.py", "args": ["--write"], "category": "review_only", "expected_outputs": ["tmp/probability-readiness-report.json"], "depends_on": ["auto_apply_position_sizing_semantic_sync.py"], "recovery_posture": "fail_chain"},
            {"script": "probability_readiness_validator.py", "args": ["--write"], "category": "validation", "expected_outputs": ["tmp/probability-readiness-validation.json"], "depends_on": ["probability_readiness_report.py"], "recovery_posture": "fail_chain"},
            {"script": "board_canon_guardrail.py", "args": ["--write"], "category": "validation", "expected_outputs": ["tmp/board-canon-guardrail.json"], "depends_on": ["daily_review_objects.py", "regime_scoring_refresh.py", "trigger_sheet_refresh.py", "deployment_check.py"], "recovery_posture": "fail_chain"},
            {"script": "stale_intelligence_guardrail.py", "args": ["--write"], "category": "validation", "expected_outputs": ["tmp/stale-intelligence-guardrail.json"], "depends_on": ["board_canon_guardrail.py", "daily_review_objects.py", "regime_scoring_refresh.py", "trigger_sheet_refresh.py", "deployment_check.py"], "recovery_posture": "fail_chain"},
            {"script": "canonical_note_patch_proposal.py", "args": ["--write"], "category": "review_only", "expected_outputs": ["tmp/canonical-note-patch-proposal.json"], "depends_on": ["board_canon_guardrail.py", "stale_intelligence_guardrail.py", "daily_review_objects.py", "regime_scoring_refresh.py", "trigger_sheet_refresh.py", "deployment_check.py"], "recovery_posture": "fail_chain"},
            {"script": "full_portfolio_view.py", "args": ["--window", "post-close", "--write"], "category": "summary", "expected_outputs": ["tmp/full-portfolio-view.json"], "depends_on": ["canonical_note_patch_proposal.py", "board_canon_guardrail.py", "stale_intelligence_guardrail.py", "regime_scoring_refresh.py", "trigger_sheet_refresh.py", "deployment_check.py"], "recovery_posture": "fail_chain"},
            {"script": "full_portfolio_view_validate.py", "args": ["--window", "post-close", "--write"], "category": "validation", "expected_outputs": ["tmp/full-portfolio-view-validation.json"], "depends_on": ["full_portfolio_view.py"], "recovery_posture": "fail_chain"},
            {"script": "portfolio_snapshot_patch_proposal.py", "args": ["--write"], "category": "review_only", "expected_outputs": ["tmp/portfolio-snapshot-patch-proposal.json"], "depends_on": ["full_portfolio_view_validate.py", "full_portfolio_view.py"], "recovery_posture": "fail_chain"},
            {"script": "finance_discrepancy_resolver.py", "args": ["--write"], "category": "review_only", "expected_outputs": ["tmp/finance-discrepancy-resolver.json"], "depends_on": ["canonical_note_patch_proposal.py", "portfolio_snapshot_patch_proposal.py", "board_canon_guardrail.py", "stale_intelligence_guardrail.py"], "recovery_posture": "fail_chain"},
            {"script": "proposal_patch_scope_validator.py", "args": ["--write"], "category": "validation", "expected_outputs": ["tmp/proposal-patch-scope-validation.json"], "depends_on": ["portfolio_mutation_proposal_generator.py"], "recovery_posture": "fail_chain"},
            {"script": "canonical_status_invariant_validator.py", "args": ["--write"], "category": "validation", "expected_outputs": ["tmp/canonical-status-invariant-validation.json"], "depends_on": ["proposal_patch_scope_validator.py"], "recovery_posture": "fail_chain"},
            {"script": "portfolio_pro_forma_risk_validator.py", "args": ["--write"], "category": "validation", "expected_outputs": ["tmp/portfolio-pro-forma-risk-validation.json"], "depends_on": ["canonical_status_invariant_validator.py"], "recovery_posture": "fail_chain"},
            {"script": "authority_vocabulary_consistency_check.py", "args": ["--write"], "category": "validation", "expected_outputs": ["tmp/authority-vocabulary-consistency.json"], "depends_on": ["portfolio_pro_forma_risk_validator.py"], "recovery_posture": "fail_chain"},
            {"script": "post_apply_validation_chain.py", "args": ["--write"], "category": "validation", "expected_outputs": ["tmp/post-apply-validation-chain.json"], "depends_on": ["authority_vocabulary_consistency_check.py"], "recovery_posture": "fail_chain"},
            {"script": "state_history_capture.py", "args": ["append", "--window", "post-close"], "category": "history", "expected_outputs": ["data/state-history/state-history-v1.jsonl"], "depends_on": ["daily_review_objects.py", "market_intelligence_event_router.py", "deployment_readiness_surface.py", "run_summary_refresh.py"], "recovery_posture": "fail_chain"},
            {"script": "post_close_final_quote_ledger.py", "args": ["--write", "--validate"], "category": "market_data", "expected_outputs": ["tmp/post-close-final-quote-ledger.json"], "depends_on": ["state_history_capture.py"], "recovery_posture": "fail_chain"},
            {"script": "ticker_card_freshness_owner_runner.py", "args": ["--skip-provider-refresh", "--full-answer-mode", "changed", "--write", "--validate"], "category": "review_only", "expected_outputs": ["tmp/ticker-card-freshness-owner-runner.json"], "depends_on": ["post_close_final_quote_ledger.py"], "recovery_posture": "fail_chain"},
            {"script": "wf78_capital_review_queue.py", "args": ["--write", "--write-db", "--validate"], "category": "review_only", "expected_outputs": ["tmp/wf78-capital-review-queue.json", "tmp/wf78-capital-review-queue.sqlite"], "depends_on": ["post_close_final_quote_ledger.py", "ticker_card_freshness_owner_runner.py"], "recovery_posture": "fail_chain"},
            {"script": "finance_sql_canon_access.py", "args": ["--write", "--validate"], "category": "validation", "expected_outputs": ["tmp/finance-sql-canon-access-validation.json"], "depends_on": ["wf78_capital_review_queue.py"], "recovery_posture": "fail_chain"},
            {"script": "finance_decision_factory.py", "args": ["--ledger-only", "--write", "--validate"], "category": "review_only", "expected_outputs": ["tmp/finance-decision-factory.json"], "depends_on": ["wf78_capital_review_queue.py", "ticker_card_freshness_owner_runner.py", "finance_sql_canon_access.py"], "recovery_posture": "fail_chain"},
            {"script": "finance_decision_sync_spine.py", "args": ["--write", "--write-md", "--validate"], "category": "review_only", "expected_outputs": ["tmp/finance-decision-sync-spine.json", "tmp/finance-decision-sync-spine.md"], "depends_on": ["finance_decision_factory.py"], "recovery_posture": "fail_chain"},
            {"script": "veritas_finance_brief.py", "args": ["--write", "--write-md", "--validate"], "category": "summary", "expected_outputs": ["tmp/veritas-finance-brief.json", "tmp/veritas-finance-brief.md"], "depends_on": ["finance_decision_sync_spine.py"], "recovery_posture": "fail_chain"},
            {"script": "wf78_tier_weighted_freshness_resolver.py", "args": ["--write", "--validate"], "category": "review_only", "expected_outputs": ["tmp/wf78-tier-weighted-freshness-resolution.json"], "depends_on": ["post_close_final_quote_ledger.py", "ticker_card_freshness_owner_runner.py"], "recovery_posture": "fail_chain"},
            {"script": "market_today_answer_packet.py", "args": ["--write", "--validate"], "category": "summary", "expected_outputs": ["tmp/market-today-answer-packet.json"], "depends_on": ["postmarket_snapshot.py", "macro_signal_spine.py", "macro_metrics_ingest.py", "ticker_card_freshness_owner_runner.py", "wf78_tier_weighted_freshness_resolver.py"], "recovery_posture": "fail_chain"},
            {"script": "current_window_artifact_index.py", "args": ["--window", "post-close", "--write"], "category": "summary", "expected_outputs": ["tmp/current-window-artifacts.json"], "depends_on": ["daily_review_objects.py", "run_summary_refresh.py", "state_history_capture.py", "finance_decision_factory.py", "veritas_finance_brief.py", "wf78_tier_weighted_freshness_resolver.py", "market_today_answer_packet.py"], "recovery_posture": "fail_chain"},
            {"script": "artifact_index.py", "args": ["incremental"], "category": "summary", "expected_outputs": ["tmp/veritas-artifact-index.sqlite"], "depends_on": ["current_window_artifact_index.py"], "recovery_posture": "fail_chain"},
            {"script": "run_summary_refresh.py", "args": ["--window", "post-close"], "category": "summary", "expected_outputs": ["tmp/run-summary-post-close.json"], "depends_on": ["artifact_index.py"], "recovery_posture": "recovery_finalizer"},
        ],
    },
    "post-earnings": {
        "description": "Event-driven follow-up after a material report lands. Refreshes earnings timing, rebuilds post-earnings packets and selective note targets, then revalidates dashboard trust.",
        "steps": [
            {"script": "earnings_calendar_enrichment.py", "args": [], "category": "intelligence", "expected_outputs": ["tmp/earnings-calendar.json"], "depends_on": [], "recovery_posture": "fail_chain"},
            {"script": "earnings_date_source_confidence.py", "args": [], "category": "intelligence", "expected_outputs": ["tmp/earnings-date-source-confidence.json"], "depends_on": ["earnings_calendar_enrichment.py"], "recovery_posture": "fail_chain"},
            {"script": "event_calendar_rollforward.py", "args": [], "category": "intelligence", "expected_outputs": ["tmp/event-calendar-rollforward.json"], "depends_on": ["earnings_calendar_enrichment.py", "earnings_date_source_confidence.py"], "recovery_posture": "fail_chain"},
            {"script": "event_calendar_apply.py", "args": ["--apply"], "category": "intelligence", "expected_outputs": ["tmp/event-calendar-apply.json"], "depends_on": ["event_calendar_rollforward.py"], "recovery_posture": "fail_chain"},
            {"script": "validate_portfolio_config.py", "args": [], "category": "portfolio", "expected_outputs": [], "depends_on": [], "recovery_posture": "fail_chain"},
            {"script": "bank_native_sec_concept_probe.py", "args": ["--write"], "category": "fundamentals", "expected_outputs": ["tmp/bank-native-sec-concept-probe.json"], "depends_on": ["validate_portfolio_config.py"], "recovery_posture": "fail_chain", "incremental_skip": False},
            {"script": "fundamental_metrics_refresh.py", "args": [], "category": "fundamentals", "expected_outputs": ["tmp/fundamental-metrics-current.json", "data/fundamentals/fundamentals-quarterly-v1.jsonl"], "depends_on": ["bank_native_sec_concept_probe.py"], "recovery_posture": "fail_chain", "timeout_seconds": 900},
            {"script": "validate_fundamental_metrics.py", "args": ["--write"], "category": "validation", "expected_outputs": ["tmp/fundamental-metrics-validation.json"], "depends_on": ["fundamental_metrics_refresh.py"], "recovery_posture": "fail_chain"},
            {"script": "goog_official_ir_capture.py", "args": [], "category": "fundamentals", "expected_outputs": [], "depends_on": ["validate_fundamental_metrics.py"], "recovery_posture": "fail_chain"},
            {"script": "etn_vrt_official_ir_capture.py", "args": [], "category": "fundamentals", "expected_outputs": [], "depends_on": ["validate_fundamental_metrics.py"], "recovery_posture": "fail_chain"},
            {"script": "tech_official_ir_capture.py", "args": [], "category": "fundamentals", "expected_outputs": [], "depends_on": ["validate_fundamental_metrics.py"], "recovery_posture": "fail_chain"},
            {"script": "priority_official_ir_capture.py", "args": [], "category": "fundamentals", "expected_outputs": [], "depends_on": ["validate_fundamental_metrics.py"], "recovery_posture": "fail_chain"},
            {"script": "batch2_official_ir_capture.py", "args": [], "category": "fundamentals", "expected_outputs": [], "depends_on": ["validate_fundamental_metrics.py"], "recovery_posture": "fail_chain"},
            {"script": "batch2b_official_ir_capture.py", "args": [], "category": "fundamentals", "expected_outputs": [], "depends_on": ["validate_fundamental_metrics.py"], "recovery_posture": "fail_chain"},
            {"script": "longtail_official_ir_capture.py", "args": [], "category": "fundamentals", "expected_outputs": [], "depends_on": ["validate_fundamental_metrics.py"], "recovery_posture": "fail_chain"},
            {"script": "official_ir_capture_validator.py", "args": ["--all", "--write"], "category": "validation", "expected_outputs": [] , "depends_on": ["goog_official_ir_capture.py", "etn_vrt_official_ir_capture.py", "tech_official_ir_capture.py", "priority_official_ir_capture.py", "batch2_official_ir_capture.py", "batch2b_official_ir_capture.py", "longtail_official_ir_capture.py"], "recovery_posture": "fail_chain"},
            {"script": "fundamental_ir_reconciliation_packets.py", "args": ["--write"], "category": "fundamentals", "expected_outputs": ["tmp/fundamental-ir-reconciliation-packets.json"], "depends_on": ["official_ir_capture_validator.py"], "recovery_posture": "fail_chain"},
            {"script": "wf70_wf66_official_evidence_spine.py", "args": [], "category": "validation", "expected_outputs": ["tmp/wf70-wf66-official-evidence-spine.json", "tmp/wf70-wf66-official-evidence-spine-validation.json"], "depends_on": ["fundamental_ir_reconciliation_packets.py"], "recovery_posture": "fail_chain"},
            {"script": "wf70_wf66_official_evidence_spine.py", "args": ["--validate-only"], "category": "validation", "expected_outputs": ["tmp/wf70-wf66-official-evidence-spine-validation.json"], "depends_on": ["wf70_wf66_official_evidence_spine.py"], "recovery_posture": "fail_chain"},
            {"script": "validate_fundamental_ir_reconciliation.py", "args": ["--write"], "category": "validation", "expected_outputs": ["tmp/fundamental-ir-reconciliation-validation.json"], "depends_on": ["wf70_wf66_official_evidence_spine.py"], "recovery_posture": "fail_chain"},
            {"script": "official_earnings_bridge.py", "args": ["--write"], "category": "fundamentals", "expected_outputs": ["tmp/official-earnings-bridge.json"], "depends_on": ["validate_fundamental_ir_reconciliation.py"], "recovery_posture": "fail_chain"},
            {"script": "validate_official_earnings_bridge.py", "args": ["--write"], "category": "validation", "expected_outputs": ["tmp/official-earnings-bridge-validation.json"], "depends_on": ["official_earnings_bridge.py"], "recovery_posture": "fail_chain"},
            {"script": "technical_refresh.py", "args": [], "category": "portfolio", "expected_outputs": ["tmp/technical-refresh.json"], "depends_on": [], "recovery_posture": "fail_chain"},
            {"script": "band_refresh.py", "args": [], "category": "portfolio", "expected_outputs": ["tmp/band-proposals.json"], "depends_on": ["technical_refresh.py"], "recovery_posture": "fail_chain"},
            {"script": "auto_apply_entry_band_maintenance.py", "args": ["--apply"], "category": "portfolio", "expected_outputs": ["tmp/auto-band-apply.json"], "depends_on": ["band_refresh.py"], "recovery_posture": "fail_chain"},
            {"script": "post_earnings_prep.py", "args": [], "category": "intelligence", "expected_outputs": ["tmp/post-earnings-prep.json"], "depends_on": ["earnings_calendar_enrichment.py", "auto_apply_entry_band_maintenance.py"], "recovery_posture": "fail_chain"},
            {"script": "post_earnings_note_targets.py", "args": [], "category": "intelligence", "expected_outputs": ["tmp/post-earnings-note-targets.json"], "depends_on": ["post_earnings_prep.py"], "recovery_posture": "fail_chain"},
            {"script": "deployment_check.py", "args": [], "category": "validation", "expected_outputs": ["tmp/deployment-check.json"], "depends_on": ["technical_refresh.py", "band_refresh.py", "earnings_calendar_enrichment.py"], "recovery_posture": "fail_chain"},
            {"script": "trigger_sheet_refresh.py", "args": [], "category": "portfolio", "expected_outputs": ["tmp/trigger-sheet.json"], "depends_on": ["deployment_check.py"], "recovery_posture": "fail_chain"},
            {"script": "positioning_ranking_refresh.py", "args": [], "category": "portfolio", "expected_outputs": [], "depends_on": ["trigger_sheet_refresh.py"], "recovery_posture": "fail_chain"},
            {"script": "universe_consistency_check.py", "args": [], "category": "validation", "expected_outputs": [], "depends_on": ["post_earnings_prep.py"], "recovery_posture": "fail_chain"},
            {"script": "canon_volatile_execution_board_sync.py", "args": ["--apply", "--strict-exit"], "category": "portfolio", "expected_outputs": ["tmp/canon-volatile-execution-board-sync.json"], "depends_on": ["technical_refresh.py", "deployment_check.py", "trigger_sheet_refresh.py", "auto_apply_entry_band_maintenance.py"], "recovery_posture": "fail_chain"},
            {"script": "sql_canon_field_family_preflight.py", "args": ["--write"], "category": "validation", "expected_outputs": ["tmp/sql-canon-low-risk-field-family-preflight.json"], "depends_on": ["canon_volatile_execution_board_sync.py"], "recovery_posture": "fail_chain"},
            {"script": "wf72_entry_stop_sql_activate.py", "args": ["--batch", "all", "--validate-only"], "category": "validation", "expected_outputs": ["tmp/wf72-entry-stop-sql-activation-validation.json"], "depends_on": ["sql_canon_field_family_preflight.py"], "recovery_posture": "fail_chain"},
            {"script": "canon_drift_freshness_gate.py", "args": ["--write", "--strict-exit"], "category": "validation", "expected_outputs": ["tmp/canon-drift-freshness-gate.json"], "depends_on": ["wf72_entry_stop_sql_activate.py"], "recovery_posture": "fail_chain"},
            {"script": "test_dashboard_acceptance.py", "args": [], "category": "validation", "expected_outputs": ["tmp/dashboard-acceptance-report.json"], "depends_on": ["post_earnings_prep.py", "canon_volatile_execution_board_sync.py", "canon_drift_freshness_gate.py"], "recovery_posture": "fail_chain"},
            {"script": "generate_dashboard.py", "args": [], "category": "summary", "expected_outputs": ["tmp/veritas-command-center.html"], "depends_on": ["test_dashboard_acceptance.py"], "recovery_posture": "fail_chain"},
            {"script": "validate_dashboard_state.py", "args": ["--write"], "category": "validation", "expected_outputs": ["tmp/dashboard-validation.json"], "depends_on": ["generate_dashboard.py"], "recovery_posture": "fail_chain"},
            {"script": "workbook_export.py", "args": [], "category": "summary", "expected_outputs": [], "depends_on": ["validate_dashboard_state.py"], "recovery_posture": "fail_chain"},
            {"script": "run_summary_refresh.py", "args": ["--window", "post-earnings"], "category": "summary", "expected_outputs": ["tmp/run-summary-post-earnings.json"], "depends_on": ["validate_dashboard_state.py"], "recovery_posture": "recovery_finalizer"},
            {"script": "dashboard_run_summary_consumer.py", "args": ["--window", "post-earnings"], "category": "summary", "expected_outputs": [], "depends_on": ["run_summary_refresh.py"], "recovery_posture": "recovery_finalizer"},
            {"script": "deployment_readiness_surface.py", "args": ["--window", "post-earnings"], "category": "summary", "expected_outputs": ["tmp/deployment-readiness-surface.json"], "depends_on": ["validate_dashboard_state.py", "run_summary_refresh.py"], "recovery_posture": "fail_chain"},
            {"script": "daily_price_trend_signals.py", "args": ["--window", "post-earnings"], "category": "summary", "expected_outputs": ["tmp/daily-price-trend-signals.json"], "depends_on": ["deployment_readiness_surface.py", "band_refresh.py", "technical_refresh.py", "validate_dashboard_state.py"], "recovery_posture": "fail_chain"},
            {"script": "market_intelligence_event_router.py", "args": ["--window", "post-earnings"], "category": "intelligence", "expected_outputs": ["tmp/market-intelligence-events-post-earnings.json"], "depends_on": ["deployment_readiness_surface.py", "validate_dashboard_state.py", "post_earnings_prep.py"], "recovery_posture": "fail_chain"},
            {"script": "daily_review_objects.py", "args": ["--window", "post-earnings"], "category": "summary", "expected_outputs": ["tmp/daily-review-objects-post-earnings.json"], "depends_on": ["deployment_readiness_surface.py", "market_intelligence_event_router.py", "post_earnings_prep.py", "run_summary_refresh.py", "validate_dashboard_state.py"], "recovery_posture": "fail_chain"},
            {"script": "current_window_artifact_index.py", "args": ["--window", "post-earnings", "--write"], "category": "summary", "expected_outputs": ["tmp/current-window-artifacts.json"], "depends_on": ["daily_review_objects.py", "run_summary_refresh.py"], "recovery_posture": "fail_chain"},
            {"script": "artifact_index.py", "args": ["incremental"], "category": "summary", "expected_outputs": ["tmp/veritas-artifact-index.sqlite"], "depends_on": ["current_window_artifact_index.py"], "recovery_posture": "fail_chain"},
            {"script": "run_summary_refresh.py", "args": ["--window", "post-earnings"], "category": "summary", "expected_outputs": ["tmp/run-summary-post-earnings.json"], "depends_on": ["artifact_index.py"], "recovery_posture": "recovery_finalizer"},
        ],
    },
    "sunday": {
        "description": "Weekly intelligence rebuild. Runs all data layers, auto-scores the tracked universe, generates the Weekly Positioning Review scaffold, syncs the call log, and revalidates the full dashboard.",
        "steps": [
            {"script": "earnings_calendar_enrichment.py", "args": [], "category": "intelligence", "expected_outputs": ["tmp/earnings-calendar.json"], "depends_on": [], "recovery_posture": "fail_chain"},
            {"script": "earnings_date_source_confidence.py", "args": [], "category": "intelligence", "expected_outputs": ["tmp/earnings-date-source-confidence.json"], "depends_on": ["earnings_calendar_enrichment.py"], "recovery_posture": "fail_chain"},
            {"script": "event_calendar_rollforward.py", "args": [], "category": "intelligence", "expected_outputs": ["tmp/event-calendar-rollforward.json"], "depends_on": ["earnings_calendar_enrichment.py", "earnings_date_source_confidence.py"], "recovery_posture": "fail_chain"},
            {"script": "event_calendar_apply.py", "args": ["--apply"], "category": "intelligence", "expected_outputs": ["tmp/event-calendar-apply.json"], "depends_on": ["event_calendar_rollforward.py"], "recovery_posture": "fail_chain"},
            {"script": "validate_portfolio_config.py", "args": [], "category": "portfolio", "expected_outputs": [], "depends_on": [], "recovery_posture": "fail_chain"},
            {"script": "bank_native_sec_concept_probe.py", "args": ["--write"], "category": "fundamentals", "expected_outputs": ["tmp/bank-native-sec-concept-probe.json"], "depends_on": ["validate_portfolio_config.py"], "recovery_posture": "fail_chain", "incremental_skip": False},
            {"script": "fundamental_metrics_refresh.py", "args": [], "category": "fundamentals", "expected_outputs": ["tmp/fundamental-metrics-current.json", "data/fundamentals/fundamentals-quarterly-v1.jsonl"], "depends_on": ["bank_native_sec_concept_probe.py"], "recovery_posture": "fail_chain", "timeout_seconds": 900},
            {"script": "validate_fundamental_metrics.py", "args": ["--write"], "category": "validation", "expected_outputs": ["tmp/fundamental-metrics-validation.json"], "depends_on": ["fundamental_metrics_refresh.py"], "recovery_posture": "fail_chain"},
            {"script": "goog_official_ir_capture.py", "args": [], "category": "fundamentals", "expected_outputs": [], "depends_on": ["validate_fundamental_metrics.py"], "recovery_posture": "fail_chain"},
            {"script": "etn_vrt_official_ir_capture.py", "args": [], "category": "fundamentals", "expected_outputs": [], "depends_on": ["validate_fundamental_metrics.py"], "recovery_posture": "fail_chain"},
            {"script": "tech_official_ir_capture.py", "args": [], "category": "fundamentals", "expected_outputs": [], "depends_on": ["validate_fundamental_metrics.py"], "recovery_posture": "fail_chain"},
            {"script": "priority_official_ir_capture.py", "args": [], "category": "fundamentals", "expected_outputs": [], "depends_on": ["validate_fundamental_metrics.py"], "recovery_posture": "fail_chain"},
            {"script": "batch2_official_ir_capture.py", "args": [], "category": "fundamentals", "expected_outputs": [], "depends_on": ["validate_fundamental_metrics.py"], "recovery_posture": "fail_chain"},
            {"script": "batch2b_official_ir_capture.py", "args": [], "category": "fundamentals", "expected_outputs": [], "depends_on": ["validate_fundamental_metrics.py"], "recovery_posture": "fail_chain"},
            {"script": "longtail_official_ir_capture.py", "args": [], "category": "fundamentals", "expected_outputs": [], "depends_on": ["validate_fundamental_metrics.py"], "recovery_posture": "fail_chain"},
            {"script": "official_ir_capture_validator.py", "args": ["--all", "--write"], "category": "validation", "expected_outputs": [] , "depends_on": ["goog_official_ir_capture.py", "etn_vrt_official_ir_capture.py", "tech_official_ir_capture.py", "priority_official_ir_capture.py", "batch2_official_ir_capture.py", "batch2b_official_ir_capture.py", "longtail_official_ir_capture.py"], "recovery_posture": "fail_chain"},
            {"script": "fundamental_ir_reconciliation_packets.py", "args": ["--write"], "category": "fundamentals", "expected_outputs": ["tmp/fundamental-ir-reconciliation-packets.json"], "depends_on": ["official_ir_capture_validator.py"], "recovery_posture": "fail_chain"},
            {"script": "wf70_wf66_official_evidence_spine.py", "args": [], "category": "validation", "expected_outputs": ["tmp/wf70-wf66-official-evidence-spine.json", "tmp/wf70-wf66-official-evidence-spine-validation.json"], "depends_on": ["fundamental_ir_reconciliation_packets.py"], "recovery_posture": "fail_chain"},
            {"script": "wf70_wf66_official_evidence_spine.py", "args": ["--validate-only"], "category": "validation", "expected_outputs": ["tmp/wf70-wf66-official-evidence-spine-validation.json"], "depends_on": ["wf70_wf66_official_evidence_spine.py"], "recovery_posture": "fail_chain"},
            {"script": "validate_fundamental_ir_reconciliation.py", "args": ["--write"], "category": "validation", "expected_outputs": ["tmp/fundamental-ir-reconciliation-validation.json"], "depends_on": ["wf70_wf66_official_evidence_spine.py"], "recovery_posture": "fail_chain"},
            {"script": "official_earnings_bridge.py", "args": ["--write"], "category": "fundamentals", "expected_outputs": ["tmp/official-earnings-bridge.json"], "depends_on": ["validate_fundamental_ir_reconciliation.py"], "recovery_posture": "fail_chain"},
            {"script": "validate_official_earnings_bridge.py", "args": ["--write"], "category": "validation", "expected_outputs": ["tmp/official-earnings-bridge-validation.json"], "depends_on": ["official_earnings_bridge.py"], "recovery_posture": "fail_chain"},
            {"script": "policy_expectations_refresh.py", "args": [], "category": "market_data", "expected_outputs": ["tmp/policy-expectations.json"], "depends_on": [], "recovery_posture": "fail_chain"},
            {"script": "credit_spread_refresh.py", "args": [], "category": "market_data", "expected_outputs": ["tmp/credit-spreads.json"], "depends_on": [], "recovery_posture": "fail_chain"},
            {"script": "breadth_refresh.py", "args": [], "category": "market_data", "expected_outputs": ["tmp/breadth-state.json"], "depends_on": [], "recovery_posture": "fail_chain"},
            {"script": "market_state_refresh.py", "args": [], "category": "market_data", "expected_outputs": ["tmp/market-state.json"], "depends_on": ["policy_expectations_refresh.py", "credit_spread_refresh.py", "breadth_refresh.py"], "recovery_posture": "fail_chain"},
            {"script": "macro_event_calendar.py", "args": ["--write", "--validate"], "category": "market_data", "expected_outputs": ["tmp/macro-event-calendar.json"], "depends_on": ["market_state_refresh.py"], "recovery_posture": "fail_chain"},
            {"script": "macro_metrics_ingest.py", "args": ["--write", "--validate"], "category": "market_data", "expected_outputs": ["tmp/macro-metrics-current.json"], "depends_on": ["macro_event_calendar.py"], "recovery_posture": "fail_chain"},
            {"script": "macro_signal_spine.py", "args": ["--write", "--validate"], "category": "market_data", "expected_outputs": ["tmp/macro-signal-spine.json"], "depends_on": ["macro_metrics_ingest.py", "market_state_refresh.py"], "recovery_posture": "fail_chain"},
            {"script": "macro_energy_supply_ingest.py", "args": ["--write", "--validate"], "category": "market_data", "expected_outputs": ["tmp/macro-energy-supply.json"], "depends_on": ["market_state_refresh.py"], "recovery_posture": "fail_chain"},
            {"script": "macro_geopolitical_sweep.py", "args": ["--write", "--validate"], "category": "market_data", "expected_outputs": ["tmp/macro-geopolitical-sweep.json"], "depends_on": ["macro_event_calendar.py"], "recovery_posture": "fail_chain"},
            {"script": "macro_regime_refresh.py", "args": [], "category": "market_data", "expected_outputs": ["tmp/macro-regime.json"], "depends_on": ["market_state_refresh.py", "credit_spread_refresh.py", "breadth_refresh.py", "macro_metrics_ingest.py"], "recovery_posture": "fail_chain"},
            {"script": "small_mid_cap_regime_feed.py", "args": ["--window", "sunday"], "category": "market_data", "expected_outputs": ["tmp/small-mid-cap-regime-feed.json"], "depends_on": ["market_state_refresh.py"], "recovery_posture": "fail_chain"},
            {"script": "historical_regime_event_library.py", "args": ["--write", "--validate"], "category": "review_only", "expected_outputs": ["tmp/historical-regime-event-library.json"], "depends_on": ["small_mid_cap_regime_feed.py"], "recovery_posture": "fail_chain"},
            {"script": "current_regime_analog_matcher.py", "args": ["--write", "--validate"], "category": "review_only", "expected_outputs": ["tmp/current-regime-analog-match.json"], "depends_on": ["historical_regime_event_library.py", "small_mid_cap_regime_feed.py"], "recovery_posture": "fail_chain"},
            {"script": "macro_judgment_draft.py", "args": ["--write", "--validate"], "category": "market_data", "expected_outputs": ["tmp/macro-judgment-draft.json"], "depends_on": ["macro_regime_refresh.py", "macro_metrics_ingest.py", "macro_signal_spine.py", "macro_event_calendar.py", "macro_energy_supply_ingest.py", "macro_geopolitical_sweep.py", "current_regime_analog_matcher.py"], "recovery_posture": "fail_chain"},
            {"script": "json_sql_promotion_index.py", "args": ["--write", "--validate"], "category": "summary", "expected_outputs": ["tmp/json-sql-promotion-index.json", "tmp/json-sql-promotion-registry.json", "tmp/json-sql-promotion-index.sqlite"], "depends_on": ["macro_judgment_draft.py"], "recovery_posture": "fail_chain"},
            {"script": "technical_refresh.py", "args": [], "category": "portfolio", "expected_outputs": ["tmp/technical-refresh.json"], "depends_on": [], "recovery_posture": "fail_chain"},
            {"script": "band_refresh.py", "args": [], "category": "portfolio", "expected_outputs": ["tmp/band-proposals.json"], "depends_on": ["technical_refresh.py"], "recovery_posture": "fail_chain"},
            {"script": "auto_apply_entry_band_maintenance.py", "args": ["--apply"], "category": "portfolio", "expected_outputs": ["tmp/auto-band-apply.json"], "depends_on": ["band_refresh.py"], "recovery_posture": "fail_chain"},
            {"script": "reference_band_note_sync.py", "args": ["--apply"], "category": "portfolio", "expected_outputs": ["tmp/reference-band-note-sync.json"], "depends_on": ["auto_apply_entry_band_maintenance.py"], "recovery_posture": "fail_chain"},
            {"script": "entry_band_fetch.py", "args": ["--all-tracked", "--html"], "category": "portfolio", "expected_outputs": ["tmp/entry-band-data/_batch-manifest.json"], "depends_on": ["reference_band_note_sync.py"], "recovery_posture": "fail_chain"},
            {"script": "generate_entry_band_status.py", "args": [], "category": "portfolio", "expected_outputs": ["tmp/entry-band-status.html"], "depends_on": ["entry_band_fetch.py"], "recovery_posture": "fail_chain"},
            {"script": "deployment_check.py", "args": [], "category": "validation", "expected_outputs": ["tmp/deployment-check.json"], "depends_on": ["technical_refresh.py", "band_refresh.py", "earnings_calendar_enrichment.py"], "recovery_posture": "fail_chain"},
            {"script": "trigger_sheet_refresh.py", "args": [], "category": "portfolio", "expected_outputs": ["tmp/trigger-sheet.json"], "depends_on": ["deployment_check.py"], "recovery_posture": "fail_chain"},
            {"script": "canon_volatile_execution_board_sync.py", "args": ["--apply", "--strict-exit"], "category": "portfolio", "expected_outputs": ["tmp/canon-volatile-execution-board-sync.json"], "depends_on": ["technical_refresh.py", "deployment_check.py", "trigger_sheet_refresh.py", "auto_apply_entry_band_maintenance.py"], "recovery_posture": "fail_chain"},
            {"script": "sql_canon_field_family_preflight.py", "args": ["--write"], "category": "validation", "expected_outputs": ["tmp/sql-canon-low-risk-field-family-preflight.json"], "depends_on": ["canon_volatile_execution_board_sync.py"], "recovery_posture": "fail_chain"},
            {"script": "wf72_entry_stop_sql_activate.py", "args": ["--batch", "all", "--validate-only"], "category": "validation", "expected_outputs": ["tmp/wf72-entry-stop-sql-activation-validation.json"], "depends_on": ["sql_canon_field_family_preflight.py"], "recovery_posture": "fail_chain"},
            {"script": "canon_drift_freshness_gate.py", "args": ["--write", "--strict-exit"], "category": "validation", "expected_outputs": ["tmp/canon-drift-freshness-gate.json"], "depends_on": ["wf72_entry_stop_sql_activate.py"], "recovery_posture": "fail_chain"},
            {"script": "regime_scoring_refresh.py", "args": [], "category": "portfolio", "expected_outputs": ["tmp/regime-scores.json"], "depends_on": ["macro_regime_refresh.py", "technical_refresh.py", "trigger_sheet_refresh.py", "deployment_check.py"], "recovery_posture": "fail_chain"},
            {"script": "positioning_ranking_refresh.py", "args": [], "category": "portfolio", "expected_outputs": [], "depends_on": ["trigger_sheet_refresh.py", "regime_scoring_refresh.py"], "recovery_posture": "fail_chain"},
            {"script": "post_earnings_prep.py", "args": [], "category": "intelligence", "expected_outputs": ["tmp/post-earnings-prep.json"], "depends_on": ["earnings_calendar_enrichment.py"], "recovery_posture": "fail_chain"},
            {"script": "post_earnings_note_targets.py", "args": [], "category": "intelligence", "expected_outputs": ["tmp/post-earnings-note-targets.json"], "depends_on": ["post_earnings_prep.py"], "recovery_posture": "fail_chain"},
            {"script": "call_log_sync.py", "args": [], "category": "intelligence", "expected_outputs": [], "depends_on": [], "recovery_posture": "fail_chain"},
            {"script": "universe_consistency_check.py", "args": [], "category": "validation", "expected_outputs": [], "depends_on": ["technical_refresh.py", "deployment_check.py", "trigger_sheet_refresh.py"], "recovery_posture": "fail_chain"},
            {"script": "test_dashboard_acceptance.py", "args": [], "category": "validation", "expected_outputs": ["tmp/dashboard-acceptance-report.json"], "depends_on": ["market_state_refresh.py", "deployment_check.py", "trigger_sheet_refresh.py", "canon_volatile_execution_board_sync.py", "canon_drift_freshness_gate.py"], "recovery_posture": "fail_chain"},
            {"script": "generate_dashboard.py", "args": [], "category": "summary", "expected_outputs": ["tmp/veritas-command-center.html"], "depends_on": ["market_state_refresh.py", "technical_refresh.py", "deployment_check.py"], "recovery_posture": "fail_chain"},
            {"script": "validate_dashboard_state.py", "args": ["--write"], "category": "validation", "expected_outputs": ["tmp/dashboard-validation.json"], "depends_on": ["generate_dashboard.py"], "recovery_posture": "fail_chain"},
            {"script": "workbook_export.py", "args": [], "category": "summary", "expected_outputs": [], "depends_on": ["validate_dashboard_state.py"], "recovery_posture": "fail_chain"},
            {"script": "weekly_review_skeleton.py", "args": [], "category": "summary", "expected_outputs": ["tmp/weekly-review-skeleton.json"], "depends_on": ["trigger_sheet_refresh.py", "deployment_check.py", "regime_scoring_refresh.py"], "recovery_posture": "fail_chain"},
            {"script": "weekly_macro_snapshot.py", "args": [], "category": "summary", "expected_outputs": [], "depends_on": ["market_state_refresh.py", "macro_regime_refresh.py", "macro_metrics_ingest.py", "macro_signal_spine.py", "macro_judgment_draft.py", "json_sql_promotion_index.py"], "recovery_posture": "fail_chain"},
            {"script": "weekly_intelligence_brief.py", "args": [], "category": "summary", "expected_outputs": ["tmp/weekly-intelligence-brief.json"], "depends_on": ["weekly_review_skeleton.py", "weekly_macro_snapshot.py"], "recovery_posture": "fail_chain"},
            {"script": "weekly_printable_brief.py", "args": [], "category": "summary", "expected_outputs": ["tmp/reports/weekly-intelligence-brief-printable-latest.json", "tmp/reports/weekly-intelligence-brief-printable-latest.html"], "depends_on": ["weekly_intelligence_brief.py"], "recovery_posture": "fail_chain"},
            {"script": "postmarket_snapshot.py", "args": [], "category": "summary", "expected_outputs": ["tmp/postmarket-snapshot.json"], "depends_on": ["trigger_sheet_refresh.py", "validate_dashboard_state.py"], "recovery_posture": "fail_chain"},
            {"script": "snapshot_contract_check.py", "args": ["--window", "sunday"], "category": "validation", "expected_outputs": ["tmp/snapshot-contract-check.json"], "depends_on": ["trigger_sheet_refresh.py", "postmarket_snapshot.py"], "recovery_posture": "fail_chain"},
            {"script": "daily_executive_brief.py", "args": [], "category": "summary", "expected_outputs": ["tmp/daily-executive-brief.json"], "depends_on": ["postmarket_snapshot.py", "snapshot_contract_check.py", "deployment_check.py", "validate_dashboard_state.py"], "recovery_posture": "fail_chain"},
            {"script": "pipeline_state_consistency_check.py", "args": ["--window", "sunday"], "category": "validation", "expected_outputs": ["tmp/pipeline-state-consistency.json"], "depends_on": ["trigger_sheet_refresh.py", "deployment_check.py", "daily_executive_brief.py", "postmarket_snapshot.py", "snapshot_contract_check.py"], "recovery_posture": "fail_chain"},
            {"script": "run_summary_refresh.py", "args": ["--window", "sunday"], "category": "summary", "expected_outputs": ["tmp/run-summary-sunday.json"], "depends_on": ["weekly_printable_brief.py", "daily_executive_brief.py", "validate_dashboard_state.py"], "recovery_posture": "recovery_finalizer"},
            {"script": "dashboard_run_summary_consumer.py", "args": ["--window", "sunday"], "category": "summary", "expected_outputs": [], "depends_on": ["run_summary_refresh.py"], "recovery_posture": "recovery_finalizer"},
            {"script": "deployment_readiness_surface.py", "args": ["--window", "sunday"], "category": "summary", "expected_outputs": ["tmp/deployment-readiness-surface.json"], "depends_on": ["trigger_sheet_refresh.py", "validate_dashboard_state.py", "run_summary_refresh.py"], "recovery_posture": "fail_chain"},
            {"script": "daily_price_trend_signals.py", "args": ["--window", "sunday"], "category": "summary", "expected_outputs": ["tmp/daily-price-trend-signals.json"], "depends_on": ["deployment_readiness_surface.py", "band_refresh.py", "technical_refresh.py", "validate_dashboard_state.py"], "recovery_posture": "fail_chain"},
            {"script": "market_intelligence_event_router.py", "args": ["--window", "sunday"], "category": "intelligence", "expected_outputs": ["tmp/market-intelligence-events-sunday.json"], "depends_on": ["deployment_readiness_surface.py", "band_refresh.py", "validate_dashboard_state.py", "market_state_refresh.py", "post_earnings_prep.py"], "recovery_posture": "fail_chain"},
            {"script": "sector_correlation_check.py", "args": ["--window", "sunday"], "category": "validation", "expected_outputs": ["tmp/sector-correlation-check.json"], "depends_on": ["deployment_readiness_surface.py", "trigger_sheet_refresh.py", "band_refresh.py"], "recovery_posture": "fail_chain"},
            {"script": "sector_expansion_board.py", "args": ["--window", "sunday"], "category": "summary", "expected_outputs": ["tmp/sector-expansion-board.json"], "depends_on": ["sector_correlation_check.py", "breadth_refresh.py", "market_state_refresh.py"], "recovery_posture": "fail_chain"},
            {"script": "daily_review_objects.py", "args": ["--window", "sunday"], "category": "summary", "expected_outputs": ["tmp/daily-review-objects-sunday.json"], "depends_on": ["deployment_readiness_surface.py", "market_intelligence_event_router.py", "sector_correlation_check.py", "sector_expansion_board.py", "daily_executive_brief.py", "postmarket_snapshot.py", "post_earnings_prep.py", "run_summary_refresh.py", "validate_dashboard_state.py"], "recovery_posture": "fail_chain"},
            {"script": "portfolio_mutation_proposal_generator.py", "args": ["--window", "sunday", "--write"], "category": "review_only", "expected_outputs": ["tmp/portfolio-mutation-proposals/current-capital-deployment-recommendations.json"], "depends_on": ["daily_review_objects.py", "band_refresh.py", "deployment_check.py", "validate_portfolio_config.py"], "recovery_posture": "fail_chain"},
            {"script": "capital_deployment_recommendation_report.py", "args": ["--write-md"], "category": "summary", "expected_outputs": ["tmp/portfolio-mutation-proposals/current-capital-deployment-recommendations.md"], "depends_on": ["portfolio_mutation_proposal_generator.py"], "recovery_posture": "fail_chain"},
            {"script": "capital_deployment_recommendation_validator.py", "args": ["--write"], "category": "validation", "expected_outputs": ["tmp/capital-deployment-recommendation-validation.json"], "depends_on": ["portfolio_mutation_proposal_generator.py", "capital_deployment_recommendation_report.py"], "recovery_posture": "fail_chain"},
            {"script": "auto_apply_position_sizing_semantic_sync.py", "args": ["--apply", "--window", "sunday"], "category": "portfolio", "expected_outputs": ["tmp/auto-position-sizing-semantic-sync.json"], "depends_on": ["capital_deployment_recommendation_validator.py"], "recovery_posture": "fail_chain"},
            {"script": "probability_readiness_report.py", "args": ["--write"], "category": "review_only", "expected_outputs": ["tmp/probability-readiness-report.json"], "depends_on": ["auto_apply_position_sizing_semantic_sync.py"], "recovery_posture": "fail_chain"},
            {"script": "probability_readiness_validator.py", "args": ["--write"], "category": "validation", "expected_outputs": ["tmp/probability-readiness-validation.json"], "depends_on": ["probability_readiness_report.py"], "recovery_posture": "fail_chain"},
            {"script": "board_canon_guardrail.py", "args": ["--write"], "category": "validation", "expected_outputs": ["tmp/board-canon-guardrail.json"], "depends_on": ["daily_review_objects.py", "regime_scoring_refresh.py", "trigger_sheet_refresh.py", "deployment_check.py"], "recovery_posture": "fail_chain"},
            {"script": "stale_intelligence_guardrail.py", "args": ["--write"], "category": "validation", "expected_outputs": ["tmp/stale-intelligence-guardrail.json"], "depends_on": ["board_canon_guardrail.py", "daily_review_objects.py", "regime_scoring_refresh.py", "trigger_sheet_refresh.py", "deployment_check.py"], "recovery_posture": "fail_chain"},
            {"script": "canonical_note_patch_proposal.py", "args": ["--write"], "category": "review_only", "expected_outputs": ["tmp/canonical-note-patch-proposal.json"], "depends_on": ["board_canon_guardrail.py", "stale_intelligence_guardrail.py", "daily_review_objects.py", "regime_scoring_refresh.py", "trigger_sheet_refresh.py", "deployment_check.py"], "recovery_posture": "fail_chain"},
            {"script": "full_portfolio_view.py", "args": ["--window", "sunday", "--write"], "category": "summary", "expected_outputs": ["tmp/full-portfolio-view.json"], "depends_on": ["canonical_note_patch_proposal.py", "board_canon_guardrail.py", "stale_intelligence_guardrail.py", "regime_scoring_refresh.py", "trigger_sheet_refresh.py", "deployment_check.py"], "recovery_posture": "fail_chain"},
            {"script": "full_portfolio_view_validate.py", "args": ["--window", "sunday", "--write"], "category": "validation", "expected_outputs": ["tmp/full-portfolio-view-validation.json"], "depends_on": ["full_portfolio_view.py"], "recovery_posture": "fail_chain"},
            {"script": "portfolio_snapshot_patch_proposal.py", "args": ["--write"], "category": "review_only", "expected_outputs": ["tmp/portfolio-snapshot-patch-proposal.json"], "depends_on": ["full_portfolio_view_validate.py", "full_portfolio_view.py"], "recovery_posture": "fail_chain"},
            {"script": "finance_discrepancy_resolver.py", "args": ["--write"], "category": "review_only", "expected_outputs": ["tmp/finance-discrepancy-resolver.json"], "depends_on": ["canonical_note_patch_proposal.py", "portfolio_snapshot_patch_proposal.py", "board_canon_guardrail.py", "stale_intelligence_guardrail.py"], "recovery_posture": "fail_chain"},
            {"script": "archive_suggester.py", "args": ["--include-tmp-md"], "category": "review_only", "expected_outputs": ["tmp/archive-suggestions.json"], "depends_on": ["portfolio_snapshot_patch_proposal.py", "finance_discrepancy_resolver.py"], "recovery_posture": "fail_chain"},
            {"script": "current_window_artifact_index.py", "args": ["--window", "sunday", "--write"], "category": "summary", "expected_outputs": ["tmp/current-window-artifacts.json"], "depends_on": ["daily_review_objects.py", "run_summary_refresh.py"], "recovery_posture": "fail_chain"},
            {"script": "artifact_index.py", "args": ["incremental"], "category": "summary", "expected_outputs": ["tmp/veritas-artifact-index.sqlite"], "depends_on": ["current_window_artifact_index.py"], "recovery_posture": "fail_chain"},
            {"script": "run_summary_refresh.py", "args": ["--window", "sunday"], "category": "summary", "expected_outputs": ["tmp/run-summary-sunday.json"], "depends_on": ["artifact_index.py"], "recovery_posture": "recovery_finalizer"},
        ],
    },
}

WINDOW_MANIFESTS["full"] = {
    "description": "Alias for post-close for backward compatibility.",
    "alias_of": "post-close",
    "steps": deepcopy(WINDOW_MANIFESTS["post-close"]["steps"]),
}


def _apply_earnings_rollforward_guard(manifests: dict[str, dict[str, Any]]) -> None:
    """Insert the missed-period guard before official capture producers.

    This is deliberately applied to the operating windows rather than to a
    live scheduler payload.  Any existing morning/post-close/Sunday run will
    therefore detect a machine outage or a newly filed quarter on its next
    normal invocation.
    """

    capture_scripts = {
        "goog_official_ir_capture.py",
        "etn_vrt_official_ir_capture.py",
        "tech_official_ir_capture.py",
        "priority_official_ir_capture.py",
        "batch2_official_ir_capture.py",
        "batch2b_official_ir_capture.py",
        "longtail_official_ir_capture.py",
    }
    for window, manifest in manifests.items():
        if window not in {"morning", "post-close", "post-earnings", "sunday", "full"}:
            continue
        steps = manifest.get("steps", [])
        if any(step.get("script") == "earnings_rollforward_guard.py" for step in steps):
            continue
        capture_index = next((idx for idx, step in enumerate(steps) if step.get("script") in capture_scripts), None)
        if capture_index is None:
            continue
        prior_script = str(steps[capture_index - 1].get("script") or "") if capture_index else ""
        args = ["--all-tracked"] if window in {"sunday", "post-earnings"} else ["--priority-only"]
        args.extend(["--auto-capture", "--write", "--validate"])
        guard = {
            "script": "earnings_rollforward_guard.py",
            "args": args,
            "category": "validation",
            "expected_outputs": ["tmp/earnings-rollforward-guard.json"],
            "depends_on": [prior_script] if prior_script else [],
            "recovery_posture": "fail_chain",
            "timeout_seconds": 900,
        }
        steps.insert(capture_index, guard)
        for step in steps[capture_index + 1 :]:
            if step.get("script") in capture_scripts:
                dependencies = list(step.get("depends_on") or [])
                if "earnings_rollforward_guard.py" not in dependencies:
                    dependencies.append("earnings_rollforward_guard.py")
                step["depends_on"] = dependencies


_apply_registry_paths(WINDOW_MANIFESTS)
_apply_earnings_rollforward_guard(WINDOW_MANIFESTS)
_apply_stage_names(WINDOW_MANIFESTS)


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


def manifest_stages(window: str) -> list[str]:
    stages: list[str] = []
    for step in manifest_steps(window):
        stage = str(step.get("stage") or _stage_for_step(step))
        if stage not in stages:
            stages.append(stage)
    return stages


def _latest_prior_index_by_script(steps: list[dict[str, Any]]) -> tuple[dict[int, list[int]], list[dict[str, Any]]]:
    latest: dict[str, int] = {}
    all_scripts = {str(step.get("script") or "") for step in steps}
    deps_by_index: dict[int, list[int]] = {}
    findings: list[dict[str, Any]] = []
    for index, step in enumerate(steps):
        deps: list[int] = []
        for dep in list(step.get("depends_on") or []):
            dep_name = str(dep)
            if dep_name in latest:
                deps.append(latest[dep_name])
            elif dep_name in all_scripts:
                findings.append({
                    "severity": "error",
                    "code": "forward_dependency",
                    "script": step.get("script"),
                    "dependency": dep_name,
                    "index": index + 1,
                })
            else:
                findings.append({
                    "severity": "error",
                    "code": "missing_dependency",
                    "script": step.get("script"),
                    "dependency": dep_name,
                    "index": index + 1,
                })
        deps_by_index[index] = deps
        latest[str(step.get("script") or "")] = index
    return deps_by_index, findings


def dependency_graph(window: str) -> dict[str, Any]:
    steps = manifest_steps(window)
    deps_by_index, findings = _latest_prior_index_by_script(steps)
    dependents: dict[int, list[int]] = {idx: [] for idx in range(len(steps))}
    for idx, deps in deps_by_index.items():
        for dep in deps:
            dependents.setdefault(dep, []).append(idx)
    return {
        "window": window,
        "steps": steps,
        "dependencies": deps_by_index,
        "dependents": dependents,
        "findings": findings,
    }


def topological_batches_from_steps(steps: list[dict[str, Any]]) -> dict[str, Any]:
    deps_by_index, findings = _latest_prior_index_by_script(steps)
    remaining = set(range(len(steps)))
    completed: set[int] = set()
    batches: list[list[int]] = []
    while remaining:
        ready = sorted(idx for idx in remaining if all(dep in completed or dep not in remaining for dep in deps_by_index.get(idx, [])))
        if not ready:
            findings.append({
                "severity": "error",
                "code": "cycle_or_unresolved_dependencies",
                "remaining": sorted(remaining),
            })
            break
        batches.append(ready)
        completed.update(ready)
        remaining.difference_update(ready)
    return {"batches": batches, "dependencies": deps_by_index, "findings": findings}


def topological_batches(window: str) -> dict[str, Any]:
    result = topological_batches_from_steps(manifest_steps(window))
    result["window"] = window
    return result


def manifest_validation(window: str) -> dict[str, Any]:
    steps = manifest_steps(window)
    topo = topological_batches_from_steps(steps)
    findings = list(topo["findings"])
    for index, step in enumerate(steps, start=1):
        script = str(step.get("script") or "")
        if script and not (SCRIPTS_DIR / script).exists():
            findings.append({
                "severity": "error",
                "code": "missing_script_file",
                "script": script,
                "index": index,
            })
        for output in list(step.get("expected_outputs") or []):
            if not isinstance(output, str) or not output.strip():
                findings.append({
                    "severity": "warning",
                    "code": "empty_expected_output",
                    "script": script,
                    "index": index,
                })
    critical = [item for item in findings if item.get("severity") == "error"]
    warnings = [item for item in findings if item.get("severity") == "warning"]
    return {
        "window": window,
        "status": "error" if critical else ("warning" if warnings else "ok"),
        "step_count": len(steps),
        "stage_count": len(manifest_stages(window)),
        "batch_count": len(topo["batches"]),
        "max_batch_size": max((len(batch) for batch in topo["batches"]), default=0),
        "findings": findings,
    }
