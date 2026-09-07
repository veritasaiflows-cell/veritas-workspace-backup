# WF72 Gate 13 portfolio source freshness QA

- Status: `qa_complete_blocked_hold`
- Candidate: `portfolio:source_freshness_classification`
- Verdict: **do not activate**. Current implementation is fail-closed, but Gate 13 is not activation-ready.

## Review scope

Independent hardening challenge of the Gate 13 portfolio source freshness redesign against these risks:

- normalizing `manual_dependency` to `fresh`/`current`
- implying portfolio owner truth
- implying canonical mutation/apply readiness
- widening SQL-canon/cache activation
- altering dashboard action-state/recommendation/deployment behavior

## Files inspected

- `tmp/wf72-gates13-16-phase-approach.md`
- `tmp/wf72-phase8-closeout.json`
- `tmp/wf72-phase8-portfolio-source-freshness-adjudication.json`
- `tmp/sql-canon-low-risk-field-family-preflight.json`
- `scripts/sql_canon_field_family_preflight.py`
- `scripts/sql_consumer_authority_guard.py`
- `scripts/dashboard_payload.py`
- `scripts/test_artifact_index.py`

## Findings

### Blocking for activation

1. **No concrete degraded/manual-dependency contract exists yet.** Gate 13 is a planning lane, not an activation packet. The existing Phase 7 SQL-canon/cache contract is fresh/current-only and must not be reused.
2. **Live portfolio freshness is degraded:** `manual_dependency` / `review_required`, `usable_for_presentation=0`, `usable_for_canonical_mutation=0`.
3. **Adding the key to current approved constants would widen the exact 13-key boundary.** That would be unsafe without a new Phase 8 boundary, exact approval artifact, rollback/export, and no-drift proof.

### Current-state positives

- Preflight keeps portfolio held: `hold_separate_gate_shadow_only` with blockers `portfolio_source_freshness_requires_separate_owner_canon_gate` and `not_fresh_or_current`.
- Canon cache currently has exactly 13 keys and **zero** portfolio rows.
- `dashboard_payload.py` approved SQL-canon keys exclude portfolio and does not pass a portfolio fallback value into SQL-canon metadata.
- A guard probe that added portfolio to the approved key list still blocked SQL reads because the cache row is missing.

## Required stop lines

- Do **not** normalize `manual_dependency/review_required` to `fresh/current`.
- Do **not** add `portfolio:source_freshness_classification` to the current Phase 7 approved-key constants.
- Do **not** write portfolio cache rows under the Phase 7 boundary.
- Do **not** treat SQL/dashboard/generated freshness metadata as portfolio owner truth, approval, mutation authority, apply readiness, or execution authority.
- Do **not** change dashboard recommendation, deployment, action-state, ranking, bands, stops, sizing, sleeve, cash, or risk-rule behavior from this gate.

## Acceptance tests required before any future activation

- Phase 7 remains exactly 13 keys; portfolio absent.
- Portfolio `manual_dependency` stays held unless a separate Phase 8 degraded metadata contract exists.
- Manual dependency cannot pass by being converted to `fresh/current`.
- Missing fallback, fallback mismatch, stale/missing source hashes, or unexpected vocabulary block SQL reads.
- Authority flags remain false: canonical note mutation, portfolio mutation, proposal apply, owner approval inference, dashboard behavior change, trade/account/paper/live/money.
- Dashboard normalized before/after proves no action/recommendation/deployment/ranking/band/stop/sizing/sleeve/cash/risk-rule drift.
- Future cache write, if ever scoped, has preactivation export, rollback SQL, post-rollback guard proof, and exact key-count proof.

## Proof snapshot

- `python scripts\sql_canon_field_family_preflight.py` -> status `ok`; `already_phase4a_active=13`, `eligible_review_only_shadow_preflight=0`, `hold_separate_gate_shadow_only=11`.
- Read-only artifact-index query -> portfolio row is `manual_dependency`, `review_required`, not presentation/canonical-mutation usable.
- Read-only canon-cache query -> 13 keys, no portfolio rows, Phase 7 exact boundary.
- Consumer guard probe -> base 13-key read allowed; portfolio-added probe blocked.
