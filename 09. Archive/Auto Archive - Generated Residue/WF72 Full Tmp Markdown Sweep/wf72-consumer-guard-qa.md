# WF72 consumer SQL authority guard QA

## Verdict

**BLOCKED for final acceptance** because requested validation proof is not clean.  
**Guard-specific assessment: PASS.** The consumer guard implementation itself is enforced in the right place and fails closed.

## Key findings

1. **Guard enforced before SQL values are used — YES**
   - `dashboard_payload._load_phase4a_sql_canon_metadata()` calls `build_phase4a_sql_consumer_authority_guard(...)` before building/exposing SQL rows.
   - If the guard is not `ok`, it returns `degraded_fallback_required`, `sqlIsCanon=false`, and `rows={}`.
   - `_sql_canon_proof_for_ticker()` only uses SQL values when `sql_canon.status == "ok"`.

2. **Fails closed and surfaces issues — YES**
   - Default state is fallback/degraded with all authority flags false.
   - Guard issues are copied into dashboard `trust.sql_canon.issues`.
   - Acceptance test `phase4a_sql_consumer_authority_guard_fail_closed` passed.

3. **Phase 4A boundary preserved — YES**
   - Exact keys only:
     - `NVDA:post_earnings_review_confirmed`
     - `NVDA:earnings_lifecycle_status`
   - Consumer family remains dashboard proof metadata only.
   - No canon/Markdown mutation, portfolio mutation, owner approval inference, trade/account/paper/live authority, money movement, or dashboard behavior-change authority was introduced.

## Validation run

- `python -m py_compile scripts\sql_consumer_authority_guard.py scripts\dashboard_payload.py scripts\dashboard_run_summary_consumer.py` — **PASS**
- `python scripts\test_dashboard_acceptance.py` — **PASS**, 28/28
- Direct guard smoke — **PASS**, `status=ok`, `sql_read_allowed=true`, no issues
- `tmp/dashboard-data.json` inspection — **PASS** for current SQL proof metadata shape/authority flags
- `python scripts\artifact_index.py validate` — **BLOCKED**: `status=blocked checks=27 failed=1`, failing `freshness_no_stale_content` for `tmp/deployment-readiness-surface.json`

## Acceptance blockers

1. `artifact_index.py validate` is not clean due stale `tmp/deployment-readiness-surface.json`.
2. `tmp/sql-canon-phase4a-validation.json` currently says `status=blocked` even though it validates the exact two rows and authority flags false. Failed checks: `preconditions_ok`, `phase3d_3e_3f_clean`, `activation_wrote_exact_two_rows`. This conflicts with the prework artifact’s stated validation status and should be reconciled before closeout.

## Required fixes before acceptance

- Resolve artifact-index freshness so `python scripts\artifact_index.py validate` returns `ok`.
- Reconcile Phase 4A validation proof: regenerate or replace with an idempotent read-only validation artifact for the already-applied exact Phase 4A scope.
- Rerun compile, dashboard acceptance, artifact-index validate, and inspect `tmp/dashboard-data.json` again.
