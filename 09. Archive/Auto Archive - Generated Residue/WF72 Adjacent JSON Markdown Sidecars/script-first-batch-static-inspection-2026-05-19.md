# Script First-Batch Static Inspection - 2026-05-19

No scripts were executed, moved, archived, chain-wired, or cron-wired. Static inspection only.

| Script | Parses | Main | Tmp outputs detected | Reference sample count | Authority terms |
|---|---:|---:|---|---:|---|
| `promotion_review_check.py` | True | True | none detected | 12 | `canonical_mutation_allowed`, `mutation` |
| `ranking_shadow_canon_check.py` | True | True | none detected | 12 | none detected |
| `canonical_freshness_patch.py` | True | True | `tmp/research-automation/raw-freshness-candidates.json` | 12 | `apply_allowed` |
| `goog_official_ir_capture.py` | True | True | none detected | 9 | `apply_allowed`, `mutation`, `owner_approval`, `portfolio_mutation_allowed`, `review_only`, `trade_or_account_action_allowed` |
| `official_ir_capture_validator.py` | True | True | none detected | 12 | `apply_allowed`, `mutation`, `owner_approval`, `portfolio_mutation_allowed`, `review_only`, `trade_or_account_action_allowed` |
| `sec_capital_freshness_review.py` | True | True | `tmp/official-ir-captures/goog-q1-2026.json` | 11 | `apply_allowed`, `canonical_mutation_allowed`, `mutation`, `owner_approval`, `portfolio_mutation_allowed`, `review_only`, `trade_or_account_action_allowed` |
| `sec_capital_recommendation_bridge.py` | True | True | none detected | 9 | `apply_allowed`, `canonical_mutation_allowed`, `mutation`, `owner_approval`, `portfolio_mutation_allowed`, `trade_or_account_action_allowed` |
| `sec_evidence_packet.py` | True | True | none detected | 12 | `apply_allowed`, `canonical_mutation_allowed`, `mutation`, `owner_approval`, `portfolio_mutation_allowed`, `review_only`, `trade_or_account_action_allowed` |
| `sec_evidence_packet_validator.py` | True | True | none detected | 11 | `apply_allowed`, `canonical_mutation_allowed`, `mutation`, `owner_approval`, `portfolio_mutation_allowed`, `trade_or_account_action_allowed` |
| `source_freshness_classifier.py` | True | False | none detected | 12 | `mutation`, `review_only` |

## Recommended disposition pass order

1. Guardrail checks: `promotion_review_check.py`, `ranking_shadow_canon_check.py` - decide chain/cron/manual documentation because they protect truth-state.
2. SEC/IR evidence packet pair: `sec_evidence_packet.py`, `sec_evidence_packet_validator.py` - keep as official-source/manual unless output/validator contract is clean enough to wire.
3. Source freshness/IR capture: `source_freshness_classifier.py`, `official_ir_capture_validator.py`, `goog_official_ir_capture.py` - decide whether these are superseded by current WF65/fundamental IR reconciliation.
4. Capital recommendation evidence bridge: `sec_capital_freshness_review.py`, `sec_capital_recommendation_bridge.py`, `canonical_freshness_patch.py` - inspect carefully because they can affect recommendation/canon-proposal surfaces.

Machine-readable detail: `tmp/script-first-batch-static-inspection-2026-05-19.json`.
