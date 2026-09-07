# WF72 SQL authority prework review

## Current truth vs stale items

- **Phase 4A is already live**, not pending: SQL canon authority exists only for `NVDA:post_earnings_review_confirmed` and `NVDA:earnings_lifecycle_status` in `tmp/veritas-canon-cache.sqlite`.
- The only live consumer family is **dashboard proof metadata**. Fallback to generated artifact / Markdown remains required.
- Validation evidence: `tmp/sql-canon-phase4a-validation.json` is `ok` with 20 checks / 0 failed / 2 rows validated; live cache integrity is `ok`; row set is exactly the two NVDA keys.
- Stale review item to correct: do **not** plan “run Phase 4A” as future work. Future work is guard hardening and separately gated expansion.
- Consumer-side guard gap: `scripts/artifact_index.py::build_sql_consumer_authority_guard()` exists, but dashboard consumer reads in `scripts/dashboard_payload.py` do not enforce that guard at init/read time.
- Note-drift cadence should be owned by **WF76 review-only Sunday maintenance**, not a new WF72 cron.
- FTS bug is confirmed: `workspace_index.py --search note-drift` throws an FTS5 hyphen parse error.

## Implementation phases

1. **4A freeze/document** — preserve exact two-key boundary; only validate/read cache.
2. **4B shared guard** — extract a small side-effect-free `sql_canon_authority` helper from existing `artifact_index.py` logic; avoid importing full `artifact_index.py` in dashboard code.
3. **4C dashboard enforcement** — `_load_phase4a_sql_canon_metadata()` must call the guard first; blocked/degraded guard means SQL values are ignored and fallback remains effective.
4. **4D FTS hardening** — normalize/escape hyphenated FTS queries, retry safe fallback, add synonyms like `note-drift -> note drift`, document retrieval-only authority.
5. **4E next family preflight** — review-only reconciliation for earnings lifecycle proof metadata; no new SQL-canon activation.
6. **4F gated activation** — only after exact approval, row list, rollback, validation, and no forbidden fields.
7. **4G one-consumer-at-a-time migration** — no activation + broad consumer migration in the same lane.

## Minimal guard design

Reuse by **extracting**, not duplicating:

- DB opens read-only; `integrity_check=ok`.
- Meta boundary equals expected boundary.
- `sql_canon_authority=true` only for approved scope.
- `consumer_authority_scope` matches requesting consumer.
- `fallback_required=true`.
- Row set exactly equals approved keys.
- Rows have expected boundary plus `validator_status=ok` / `reconciliation_status=match`.
- Forbidden field families absent: entry, weight, cash, sizing, risk, trade, paper, live, account, credential.

Consumer rule: guard not `ok` => `degraded_fallback_required`, `sqlIsCanon=false`, visible issues, no SQL effective values.

## First field-family candidates

Start with **earnings lifecycle proof metadata**:

- `last_earnings_date`
- `post_earnings_review_date`
- `post_earnings_review_confirmed`
- `earnings_lifecycle_status`

Why: existing registry coverage, generated source artifacts, Markdown mirror paths, freshness contracts, and Phase 4A precedent. Avoid entry bands, sizing, cash, weights, sleeves, sector posture, risk rules, owner approval state, and account/brokerage state.

## Note-drift cadence

Fold into WF76 Tier **T1/T2 review-only** Sunday maintenance:

- refresh workspace index
- run artifact-index incremental/validate
- regenerate `tmp/wf72-sql-to-note-drift-report.json/.md`
- hand off review-needed count to main session

Blocked: unattended note edits, SQL-canon expansion, portfolio mutation, approval inference, archive apply/deletes, config/auth/service/channel/runtime mutation.

## Stop lines

- Any Phase 4A row beyond the exact two approved NVDA keys.
- Any consumer using SQL when guard is degraded/blocked.
- Any dashboard recommendation/deployment/action-state drift.
- Any cron-direct note/canon/portfolio apply.
- Any FTS search exception after hardening.
- Any trade/account/paper/live, money movement, config/auth/service/channel/runtime mutation, delete, or owner-approval inference.

## Safe no-collision edit lanes

- SQL guard lane: `scripts/sql_canon_authority.py`, `scripts/artifact_index.py`, `scripts/test_artifact_index.py`.
- Dashboard lane: `scripts/dashboard_payload.py`, dashboard SQL-canon tests/proof artifacts.
- FTS lane: `scripts/workspace_index.py`, search docs/tests only.
- WF76 cadence lane: WF76 note and `tmp/wf72-sql-to-note-drift-report.*`; no schedule mutation.

Validation baseline: py_compile changed scripts, `artifact_index.py validate`, read-only cache integrity check, dashboard no-drift/acceptance, FTS search smokes, JSON parse all proof artifacts.
