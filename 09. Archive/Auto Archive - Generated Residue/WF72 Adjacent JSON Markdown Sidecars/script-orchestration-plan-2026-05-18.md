# Script Orchestration Plan ? 2026-05-18

## Verdict

There is a real opportunity to wire selected scripts, but not the whole orphan list. The right move is targeted orchestration plus a QA runner, not dumping all 121 scripts into the finance chain.

No chain edits, cron edits, moves, deletes, or execution-authority changes were made by this plan.

## Recommended sequence

1. Create lightweight QA runner for test suites before wiring more scripts
2. Wire/document two guardrails first after direct inspection
3. Integrate source freshness/SEC/IR tools into evidence pipeline as review-only inputs
4. Keep WF63/WF67 and WF64 tools manual/gated
5. Archive/report-generator decisions only after owner approval and reference checks

## Wire-soon candidates

| Script | Proposed target | Why | Acceptance proof |
|---|---|---|---|
| `promotion_review_check.py` | post-close chain after watchlist_promotion_radar.py or inside radar v2 | turn radar flags into explicit promotion-review gate checks | script has --write/review-only output, manifest dry-run resolves, no canon mutation |
| `ranking_shadow_canon_check.py` | post-close chain after capital_deployment_recommendation_validator.py | detect ranking/canon contradictions before summary artifacts are trusted | 0 critical findings or warning-only artifact in current-window index |
| `source_freshness_classifier.py` | official-source/fundamental pipeline before Promotion Radar | normalize fresh/current/stale/manual-required source state for promotion decisions | Promotion Radar consumes source freshness without widening authority |
| `sec_evidence_packet.py` | manual/optional official-source packet generator first; later chain only for selected top candidates | capture SEC evidence for candidates that survive universe narrowing | packets validate review-only and do not imply deployment authority |
| `sec_evidence_packet_validator.py` | paired validator wherever sec_evidence_packet.py is used | prevent unvalidated SEC packet promotion | validator blocks stale/missing provenance |
| `official_ir_capture_validator.py` | fundamental/official bridge validation tail | validate manual official-IR captures before canon/promotion use | validator output integrated or explicitly manual |
| `research_freshness_opportunity_review.py` | post-close review-only after sector_expansion_board.py or Promotion Radar v2 | connect research freshness/opportunity signals to promotion radar | output reviewed by radar/brief without auto-promotion |
| `catalyst_window_check.py` | promotion radar v2 dependency | block names near earnings/event risk before promotion/paper prep | radar gates include catalyst blockers |
| `state_history_outcome_update.py` | manual outcome append or state-history chain after paper/recommendation outcomes | feed realized outcomes into probability readiness without ad hoc updates | validator clean and append-only history preserved |
| `state_history_outcome_update_validator.py` | paired validator with outcome updates | protect state history integrity | invalid outcome rows fail closed |

## Manual/gated families ? do not casually wire

### WF63/WF67 paper helpers

Keep manual/gated; wire only through exact WF67 guard path with kill switch, audit log, paper endpoint, and scoped order artifact.

`alpaca_order_preview_generator.py`, `alpaca_paper_pilot_reconciliation.py`, `alpaca_paper_readiness_validator.py`, `alpaca_read_only_connection_proof.py`, `alpaca_reviewed_packet_pilot_request.py`, `wf67_full_portfolio_scope_validator.py`

### WF64 portfolio/canon apply helpers

Keep manual/gated; never cron-wire apply helpers. Only use inside exact approval/preview/validator/rollback path.

`portfolio_mutation_apply_helper.py`, `portfolio_mutation_exact_patch_generator.py`, `portfolio_mutation_patch_preview_validator.py`, `portfolio_mutation_proposal_schema_validator.py`, `portfolio_mutation_proposal_verifier.py`, `portfolio_mutation_scoped_apply_helper.py`, `portfolio_mutation_semantic_patch_generator.py`, `portfolio_mutation_semantic_preview_bundle.py`, `portfolio_mutation_standing_approval_artifact.py`, `write_wf64_approval_templates.py`

### cron/manual operational tools

Document live owner: cron-owned or manual. Do not duplicate in chain unless schedule is retired.

`canon_drift_freshness_gate.py`, `cyber_security_daily_audit_cron_runner.py`, `intraday_entry_watcher.py`

## Test/dev harness plan

The 60 test/dev harness scripts should become opt-in QA suites. They are regression protection, not ordinary finance-chain work.

| Suite | Count | Use |
|---|---:|---|
| `dashboard_artifact_contracts` | 9 | Run after dashboard, artifact index, summary, or snapshot changes. |
| `finance_core_signals` | 11 | Run after deployment, band, trigger, stale-guard, or universe changes. |
| `misc_dev` | 4 | Inspect or assign before use. |
| `paper_trading_safety` | 2 | Run after WF63/WF67 wrapper/guard changes. |
| `portfolio_canon_mutation_safety` | 19 | Run after WF64/canon/apply/authority changes. |
| `research_market_state` | 15 | Run after macro/research/sector/source/earnings changes. |

### Suite membership

#### `dashboard_artifact_contracts`

`test_artifact_index.py`, `test_current_window_artifact_index.py`, `test_full_portfolio_view.py`, `test_full_portfolio_view_validate.py`, `test_pipeline_state_consistency.py`, `test_run_summary_tail_order.py`, `test_sector_dashboard_suite.py`, `test_snapshot_contract_check.py`, `test_weekly_macro_snapshot.py`

#### `finance_core_signals`

`test_auto_apply_entry_band_maintenance.py`, `test_band_behavior.py`, `test_capital_deployment_recommendation_validator.py`, `test_daily_price_trend_signals.py`, `test_daily_review_objects.py`, `test_deployment_check_owner_state.py`, `test_entry_band_automation.py`, `test_reference_band_note_sync.py`, `test_stale_intelligence_guardrail.py`, `test_ticker_monitoring_performance.py`, `test_universe.py`

#### `misc_dev`

`test_candidate_packet_validator.py`, `test_finance_discrepancy_resolver.py`, `test_policy_expectations_hardening.py`, `test_workspace_governance_truth_check.py`

#### `paper_trading_safety`

`test_alpaca_order_preview_scaffolding.py`, `test_wf67_full_portfolio_scope_validator.py`

#### `portfolio_canon_mutation_safety`

`test_board_canon_guardrail.py`, `test_canonical_note_patch_proposal.py`, `test_canonical_ownership.py`, `test_dashboard_canon_surfaces.py`, `test_portfolio_mutation_apply_helper.py`, `test_portfolio_mutation_exact_patch_generator.py`, `test_portfolio_mutation_patch_preview_validator.py`, `test_portfolio_mutation_phase4_scoped_apply.py`, `test_portfolio_mutation_proposal_generator.py`, `test_portfolio_mutation_proposal_schema_validator.py`, `test_portfolio_mutation_semantic_patch_generator.py`, `test_portfolio_mutation_semantic_preview_bundle.py`, `test_portfolio_mutation_standing_approval_artifact.py`, `test_portfolio_mutation_validators.py`, `test_portfolio_snapshot_patch_proposal.py`, `test_postclose_authority.py`, `test_regime_scoring_authority.py`, `test_wf38_authority.py`, `test_wf64_approval_templates.py`

#### `research_market_state`

`test_earnings_calendar_enrichment.py`, `test_earnings_date_source_confidence.py`, `test_event_calendar_apply.py`, `test_event_calendar_rollforward.py`, `test_market_intelligence_event_router.py`, `test_market_state_refresh_dates.py`, `test_probability_readiness.py`, `test_research_freshness_opportunity_review.py`, `test_sec_evidence_packet_validator.py`, `test_sector_correlation_check.py`, `test_sector_expansion_board.py`, `test_small_mid_cap_regime_feed.py`, `test_source_freshness_classifier.py`, `test_state_history_capture.py`, `test_state_history_outcome_update.py`

## Archive/document review

### report generators

Keep only if Randall wants manual PDF/PPT/equity report package; otherwise archive after reference check.

`dashboard_delta_render.py`, `equity_pdf_report.py`, `equity_ppt_report.py`, `equity_visual_report.py`, `render_composite_regime_sector_pdf.py`, `sector_dashboard_suite.py`

### research helpers

Wire only if they improve Promotion Radar/real-cap universe; otherwise archive as superseded.

`band_behavior.py`, `bounded_entry_band_agent.py`, `candidate_packet_validator.py`, `catalyst_window_check.py`, `small_mid_cap_regime_feed.py`, `ticker_monitoring_performance.py`

### manual review unknowns

Inspect individually; several are likely libraries (`market_data_utils.py`, `chain_manifest.py`) and should not be archived despite static orphan label.

`automation_trust_block.py`, `board_state_contract.py`, `chain_manifest.py`, `cron_trust_block_consumer.py`, `daily_note_dedupe.py`, `market_data_utils.py`, `paper_pilot_status_surface.py`, `portfolio_integrity_check.py`, `summary_brief_lint.py`, `swarm_completion_handshake.py`, `universe.py`, `veritas_technical_pass_validate.py`

## Stop lines

- No auto-wiring of apply/execution helpers
- No paper/live order authority
- No deletes/moves from this plan
- No full-chain slowdown from test harnesses; tests run as opt-in QA suites

## Next implementation packet

Build `scripts/run_qa_suite.py` with dry-run/list/suite selection first, then wire only the two guardrail candidates after direct inspection and proof.