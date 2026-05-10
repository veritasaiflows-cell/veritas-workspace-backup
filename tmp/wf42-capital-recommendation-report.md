# WF42 Capital Deployment Recommendation Object Report

Generated: 2026-05-10T02:45:52Z (post-close proof run)

## Files changed
- `scripts/daily_review_objects.py`
  - Hardened each `capital_deployment_recommendations[]` packet with explicit WF42 contract fields.
  - Added top-level review-only authority flags to the daily review object artifact.
- `scripts/test_daily_review_objects.py`
  - Added acceptance checks for approval/mutation boundaries, WF42 action-vocabulary mapping, evidence provenance, source freshness, and explicit sector/correlation missing-evidence fallback.
- Regenerated artifact: `tmp/daily-review-objects-post-close.json`
- Report written: `tmp/wf42-capital-recommendation-report.md`

## Schema / field contract now emitted for each recommendation
Each capital recommendation now includes:
- Compatibility action: `recommended_action` (existing values such as `deploy_candidate`, `wait_for_band`, `wait_for_catalyst_clearance`, `hold_promotion_review`, `no_new_approval`).
- WF42 action mapping: `recommendation_action` in `deploy / wait / reject / review`.
- Source class: `recommendation_class` plus `action_vocabulary` explaining the compatibility mapping.
- Evidence: `evidence` and structured `evidence_provenance[]` with `claim`, `source_artifact`, and `source_type`.
- Risk/invalidation: `risk_invalidation`, `risk_invalidation_summary`, and `blocked_reasons`.
- Confidence/trust/freshness: `confidence`, `trust_level`, and structured `source_freshness`.
- Missing evidence: `missing_evidence`, including explicit sector/correlation manual fallback and missing state-history retention.
- Approval and authority flags: `owner_approval_required=true`, `owner_approval_granted=false`, `canonical_mutation_allowed=false`, `portfolio_mutation_allowed=false`, `deployment_state_mutation_allowed=false`, `trade_execution_allowed=false`.

Top-level packet authority now also declares:
- `canonical_mutation_allowed=false`
- `portfolio_mutation_allowed=false`
- `deployment_state_mutation_allowed=false`
- `trade_execution_allowed=false`
- `owner_approval_required_for_capital=true`
- `owner_approval_granted=false`

## Proof run
- `python -m py_compile scripts\daily_review_objects.py scripts\test_daily_review_objects.py` — passed.
- `python scripts\daily_review_objects.py --window post-close` — passed; regenerated `tmp/daily-review-objects-post-close.json` with 16 review objects, 3 escalations, and 1 capital recommendation.
- `python scripts\test_daily_review_objects.py` — passed.

`python scripts\market_intelligence_event_router.py --window post-close` was not rerun because the existing router packet was already present and fresh enough for this bounded WF42 patch; the daily review packet consumed it successfully.

## Live recommendation example
Current post-close recommendation example: `GS`.
- `recommended_action`: `wait_for_band`
- `recommendation_class`: `conditional_pullback_review`
- `recommendation_action`: `wait`
- `confidence`: `moderate`
- `trust_level`: `review_required`
- `fresh_intelligence_status`: `deployment_review:this_week:materiality_3`
- `sector_correlation_check`: `missing_artifact_manual_fallback_required`
- `owner_approval_required`: `true`
- `owner_approval_granted`: `false`
- all canonical / portfolio / deployment / trade mutation flags: `false`

## Remaining gaps
- Stable sector/correlation artifact is still missing; represented as explicit missing evidence/manual fallback, not confidence.
- State-history / owner-outcome retention remains unwired; represented as explicit missing evidence.
- Source freshness is partial/review-required because several upstream sources are classified partial; recommendation output remains review-only.

## Authority statement
WF42 remains recommendation-only and owner-gated. This pass does not add position sizing, trade execution, account actions, canonical finance-note mutation, portfolio/deployment mutation, owner approval inference, config/auth/channel/network changes, or broad external-source automation.
