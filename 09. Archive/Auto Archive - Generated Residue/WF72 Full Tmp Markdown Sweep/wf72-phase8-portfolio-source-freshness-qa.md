# WF72 Phase 8 — portfolio source-freshness independent QA

- Generated: 2026-05-24T18:27:00Z
- Candidate: `portfolio:source_freshness_classification`
- Verdict: **blocked / remain held**
- Cache writes performed: **none**

## Review scope

Claim reviewed: whether `portfolio:source_freshness_classification` can safely migrate to SQL-canon proof metadata.

Files inspected:
- `tmp/wf72-phases-8-11-full-activation-readiness-plan.json`
- `tmp/sql-canon-low-risk-field-family-preflight.json`
- `tmp/wf72-phase7-key-level-activation-summary.json`
- `scripts/sql_canon_field_family_preflight.py`
- `scripts/sql_consumer_authority_guard.py`
- `scripts/dashboard_payload.py`
- Adjacent proof/consumer surfaces: `scripts/dashboard_core.py`, `scripts/source_freshness_classifier.py`, `scripts/sql_canon_low_risk_phase3_activate.py`

## Blocking findings

1. **Current value is not low-risk fresh/current metadata.**  
   Preflight shows `portfolio:source_freshness_classification` = `manual_dependency`, posture `hold_separate_gate_shadow_only`, blockers `portfolio_source_freshness_requires_separate_owner_canon_gate` and `not_fresh_or_current`.

2. **Portfolio source is too close to owner/canon truth.**  
   The source is `tmp/portfolio-config.json`, which carries portfolio config, entry bands, and risk thresholds. A SQL-canon row for this source can be misread as portfolio truth, canonical mutation authority, or owner approval unless it has a stricter degraded-metadata contract.

3. **Consumer guard does not yet support this degraded case.**  
   The current approved key list and `dashboard_payload.py` fallback map omit the portfolio key. The guard requires exact approved keys, fallback presence/equality, validator/reconciliation OK, source hash match, and `freshness_status=fresh`; there is no explicit `portfolio_manual_dependency_metadata` path.

4. **Activation design risks mislabeling manual dependency as fresh.**  
   `scripts/sql_canon_low_risk_phase3_activate.py` hard-codes `freshness_status: "fresh"` for approved rows. Reusing that pattern for `manual_dependency` would create misleading proof metadata.

5. **No no-drift proof exists for the portfolio exception.**  
   There is no before/after proof that dashboard, Today, run summary, source-freshness readiness gates, recommendation/deployment/action-state behavior, entry bands, stops, sizing, sleeves, cash/risk rules, and authority flags remain unchanged.

## Non-blocking finding

A future migration could be safe **only** if it is redesigned as explicit degraded review-only portfolio-manual-dependency metadata, not as ordinary fresh/current source-freshness metadata.

## Required proof before reconsideration

Guard/design requirements:
- Exact contract for `portfolio_manual_dependency_metadata`.
- Preserve `field_value=manual_dependency`; do **not** coerce row `freshness_status` to `fresh`.
- Require fallback extraction from live dashboard source assessment and exact SQL/fallback equality.
- Enforce all authority flags false: canon note mutation, portfolio mutation, owner approval, capital action, paper/live trade, account action, money movement.
- Fail closed on missing/mismatched fallback, source hash mismatch, stale/missing source, unexpected classification, or authority flag drift.

Test/no-drift requirements:
- Guard tests for missing fallback, mismatch, hash mismatch, extra/missing key, unexpected fresh coercion, and authority flag true.
- Consumer no-drift diff proving only additive proof metadata changes.
- Dashboard/Today/run-summary proof that manual dependency remains visible and review-only/no-execution wording is unchanged.
- Negative tests proving no effect on recommendation/deployment buckets, decision queue, entry bands, stops, sizing, sleeves, cash, risk rules, owner approval, canonical note mutation, or trade/account authority.

## Proof assessment

Existing proof is sufficient to **hold** the key, not activate it. The preflight already identifies the exact blocker, and code inspection confirms the activation/guard/consumer path is missing the degraded portfolio contract.

## Recommended next repair

Do **not** add `portfolio:source_freshness_classification` to SQL-canon approved-key constants now. Either keep it held/permanent-hold, or first design and test a separate degraded portfolio manual-dependency metadata contract.
