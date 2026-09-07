# Script Ownership Manifest v2 - 2026-05-19

Review/control artifact only. No files were moved, archived, deleted, chain-wired, cron-wired, or finance-mutated by this pass.

## Authority

- `review_only`: `true`
- `moves_deletes_archives_performed`: `false`
- `chain_or_cron_mutation_performed`: `false`
- `finance_artifact_mutation_performed`: `false`
- `trade_account_or_paper_order_authority`: `false`

## Owner-state counts

| Owner state | Count |
|---|---:|
| `candidate_wire_guardrail_or_document_manual` | 2 |
| `candidate_wire_evidence_pipeline` | 8 |
| `candidate_wire_state_history_or_keep_manual` | 2 |
| `candidate_wire_research_or_archive` | 4 |
| `manual_report_or_archive_candidate` | 5 |
| `needs_inspection` | 12 |
| `cron_owned` | 7 |
| `manual_documented` | 1 |
| `manual_gated` | 16 |
| `library_component` | 4 |
| `test_harness` | 60 |

## First actionable batch - guardrails + evidence pipeline

These are the highest-value scripts to inspect next because they protect truth-state or improve official-source evidence. They should not be auto-wired until each has current outputs, clean authority blocks, and clear consumers.

| Script | Owner state | Recommended action |
|---|---|---|
| `promotion_review_check.py` | `candidate_wire_guardrail_or_document_manual` | inspect_for_wiring_or_manual_doc |
| `ranking_shadow_canon_check.py` | `candidate_wire_guardrail_or_document_manual` | inspect_for_wiring_or_manual_doc |
| `canonical_freshness_patch.py` | `candidate_wire_evidence_pipeline` | inspect_for_wiring_or_manual_doc |
| `goog_official_ir_capture.py` | `candidate_wire_evidence_pipeline` | inspect_for_wiring_or_manual_doc |
| `official_ir_capture_validator.py` | `candidate_wire_evidence_pipeline` | inspect_for_wiring_or_manual_doc |
| `sec_capital_freshness_review.py` | `candidate_wire_evidence_pipeline` | inspect_for_wiring_or_manual_doc |
| `sec_capital_recommendation_bridge.py` | `candidate_wire_evidence_pipeline` | inspect_for_wiring_or_manual_doc |
| `sec_evidence_packet.py` | `candidate_wire_evidence_pipeline` | inspect_for_wiring_or_manual_doc |
| `sec_evidence_packet_validator.py` | `candidate_wire_evidence_pipeline` | inspect_for_wiring_or_manual_doc |
| `source_freshness_classifier.py` | `candidate_wire_evidence_pipeline` | inspect_for_wiring_or_manual_doc |

## Keep gated / do not casually wire

- `alpaca_order_preview_generator.py` - Paper-trading guard/proof surface; keep manual/gated unless explicitly wired into WF67 validation.
- `alpaca_paper_pilot_reconciliation.py` - Paper-trading guard/proof surface; keep manual/gated unless explicitly wired into WF67 validation.
- `alpaca_paper_readiness_validator.py` - Paper-trading guard/proof surface; keep manual/gated unless explicitly wired into WF67 validation.
- `alpaca_read_only_connection_proof.py` - Paper-trading guard/proof surface; keep manual/gated unless explicitly wired into WF67 validation.
- `alpaca_reviewed_packet_pilot_request.py` - Paper-trading guard/proof surface; keep manual/gated unless explicitly wired into WF67 validation.
- `portfolio_mutation_apply_helper.py` - WF64 gated portfolio/canon apply helper; keep manual/gated with owner contract before wiring.
- `portfolio_mutation_exact_patch_generator.py` - WF64 gated portfolio/canon apply helper; keep manual/gated with owner contract before wiring.
- `portfolio_mutation_patch_preview_validator.py` - WF64 gated portfolio/canon apply helper; keep manual/gated with owner contract before wiring.
- `portfolio_mutation_proposal_schema_validator.py` - WF64 gated portfolio/canon apply helper; keep manual/gated with owner contract before wiring.
- `portfolio_mutation_proposal_verifier.py` - WF64 gated portfolio/canon apply helper; keep manual/gated with owner contract before wiring.
- `portfolio_mutation_scoped_apply_helper.py` - WF64 gated portfolio/canon apply helper; keep manual/gated with owner contract before wiring.
- `portfolio_mutation_semantic_patch_generator.py` - WF64 gated portfolio/canon apply helper; keep manual/gated with owner contract before wiring.
- `portfolio_mutation_semantic_preview_bundle.py` - WF64 gated portfolio/canon apply helper; keep manual/gated with owner contract before wiring.
- `portfolio_mutation_standing_approval_artifact.py` - WF64 gated portfolio/canon apply helper; keep manual/gated with owner contract before wiring.
- `wf67_full_portfolio_scope_validator.py` - Paper-trading guard/proof surface; keep manual/gated unless explicitly wired into WF67 validation.
- `write_wf64_approval_templates.py` - WF64 gated portfolio/canon apply helper; keep manual/gated with owner contract before wiring.

## Needs inspection before archive/document

- `automation_trust_block.py` - No obvious active owner from name/static reachability; review before archive.
- `board_state_contract.py` - No obvious active owner from name/static reachability; review before archive.
- `chain_manifest.py` - No obvious active owner from name/static reachability; review before archive.
- `cron_trust_block_consumer.py` - No obvious active owner from name/static reachability; review before archive.
- `daily_note_dedupe.py` - No obvious active owner from name/static reachability; review before archive.
- `market_data_utils.py` - No obvious active owner from name/static reachability; review before archive.
- `paper_pilot_status_surface.py` - No obvious active owner from name/static reachability; review before archive.
- `portfolio_integrity_check.py` - No obvious active owner from name/static reachability; review before archive.
- `summary_brief_lint.py` - No obvious active owner from name/static reachability; review before archive.
- `swarm_completion_handshake.py` - No obvious active owner from name/static reachability; review before archive.
- `universe.py` - No obvious active owner from name/static reachability; review before archive.
- `veritas_technical_pass_validate.py` - No obvious active owner from name/static reachability; review before archive.

## Full row source

Machine-readable rows live in `tmp/script-ownership-manifest-v2-2026-05-19.json`.
