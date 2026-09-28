# Finance SQL Canon Rebuild Disposition - 2026-09-27

- **Lane:** FINANCE-SQL-CANON-REBUILD-DISPOSITION-20260927::main (leased, main-session)
- **Status:** Recommendation delivered, awaiting Randall's disposition decision. The two drafted fixes (cascade loss, atomicity) are applied to the tool with focused tests. **No live canon write occurred at any point**; all rebuild proof ran on SQLite copies made with the backup API from a read-only URI (WAL-safe).
- **Untouched as instructed:** `scripts/finance_sql_canon_access.py` (P4-2-WRITER-LANE-20260927 slice-b-r2 lease still active).

## First-hand verification of the six reported gaps (temp copies)

All six confirmed end-to-end on `tmp/finance-sql-canon-rebuild-disposition-20260927/proof-pre.json`:

| # | Gap | Verified result |
|---|-----|-----------------|
| 1 | `sync_tier_routing_state` repopulates retired table | `tier_routing_state` 0 → 300 rows from frozen `tmp/wf78-auto-tier-routing.json` |
| 2 | `insert_universe` recomputes migrated state | `answer_path_scope` flipped `alert_recommendation_review` → `sql_first_review_monitor` (300); `source_artifacts` 5 → 7; `production_scope_member` recomputed from frozen proofs |
| 3 | `disciplined_reference_levels` cascade loss | Seeded sentinel 1 → 0 (`DROP TABLE securities` + `PRAGMA foreign_keys=ON`) |
| 4 | Non-atomic rebuild | Injected mid-insert failure left securities 300 → 0, `universe_membership` empty, audit history gone |
| 5 | Manifest advertises rebuild as recovery route | `db_lifecycle_manifest.py` line 80 confirmed |
| 6 | `raw_json` legacy tier disagreement | 273 of 300 rows; a rebuild "resolves" it to 0 by overwriting the authoritative `tier` column with the stale JSON values |

Also confirmed: a successful rebuild drops all `audit_events` history (the `alerts_os_sql_canon_migration` marker disappears) and silently rolls tiers back to the legacy JSON (15 A / 17 B / 268 C → 289 B / 11 C).

## Truth-surface discrepancy (material)

The context describes lane FINANCE-SQL-CANON-REBUILD-TIER-GUARD-20260927 (2026-09-27) as having added a tier-drift guard (`--write` refuses tier-family changes unless `--accept-tier-drift-sha256` names the drift) plus audit_events carry-over. **None of that exists in the live workspace:**

- Live `scripts/finance_sql_canon.py` mtime is 2026-08-22; no guard, no carry-over, no such CLI flag.
- No lane-register entry for that workflow (register has no TIER-GUARD-20260927 under any status).
- Git history for the script is clean since August; no patch anywhere on disk (only unrelated 2026-08-16/17 memory notes use the word "tier-drift").
- Memory 2026-09-27 (~15:20-15:40) records the hazard as an **open** follow-up (`task_049b4164`: "--write would DROP universe_membership and rebuild tiers from the legacy JSON").

If that guard was believed deployed, it is not. The audit-history carry-over is likewise absent (proven: marker dropped in both pre-fix and post-fix rebuild drills).

## Recommendation: (a) now, (c) as the declared end-state, (b) rejected

**(a) Refuse to run against a migrated canon — do this now.**
- Detection anchor is proven present in the live canon: `audit_events` row `event_type='alerts_os_sql_canon_migration'`.
- Smallest fail-closed containment for the dominant risk: any `--write` against the migrated canon silently rolls back tiers, resurrects retired surfaces, and destroys audit history.
- Subsumes the missing tier-drift guard for the migrated-canon case and needs no new authority: it *removes* a write path rather than widening one.

**(c) Retire in favor of backup restore + Phase 4 per-name writer — the end-state, with prerequisites.**
1. P4-2 per-name writer lane lands (in progress; slices a/b leased).
2. A WAL-safe backup/restore route is proven as the recovery path. Known gap: `g6` backup copies only the main DB file and proves it with a main-file hash — unsafe under WAL with an open reader (today's HIGH finding); the WAL-safe helper (`sqlite` backup API + logical hash) exists at `tmp/p4-2-writer-lane-20260927/walproof/sqlite_snapshot_ref.py`.
3. `db_lifecycle_manifest.py` line 80 recovery route flips from the rebuild command to the backup-restore route (owner-gated edit).
4. One restore drill on a temp copy, then archive the rebuild route.

**(b) Migration-aware rebuild — rejected.** The rebuild's sources are stale by construction (`data/finance/universe-v1.json` tiers 289 B / 11 C vs SQL authority 15/17/268; editing the JSON breaks 800 evidence-lineage hashes). Making the rebuild respect migrated semantics means duplicating every migration invariant (retired surfaces, answer-path scopes, lineage parity, 200-row baseline pins) inside a second whole-DB writer — a permanent two-writer hazard against the per-name writers — and its frozen sources still could not produce truthful current state without becoming a full re-migration.

## Applied fixes (smallest, drafted and tested)

Both in `scripts/finance_sql_canon.py` (27 insertions, 6 deletions; diff reviewed first-hand):

1. **Cascade loss (item 3):** `disciplined_reference_levels` added to `PRESERVED_EXTENSION_TABLES`. This is the same fetch-before/restore-after mechanism that already protects `reference_levels` and `evidence_freshness` (both also carry `ON DELETE CASCADE` to `securities` — verified).
2. **Atomicity (item 4):** `create_schema` no longer uses `executescript()` (which commits pending work, then autocommits every DROP/CREATE). The schema SQL now executes statement-by-statement via `sqlite3.complete_statement` accumulation inside one explicit `BEGIN IMMEDIATE` that joins `build_db`'s `with conn:` block, so the whole rebuild commits or rolls back as a unit. Fails closed on trailing incomplete SQL.

**Tests:** `scripts/test_finance_sql_canon_rebuild_guards.py` — 5/5 pass (sentinel survival, ticker-column preserve contract, mid-rebuild failure full rollback, single-transaction + complete-object schema build, incomplete-SQL refusal).

**Post-fix proof** (`proof-post.json`): sentinel survives a full rebuild (`restored: {disciplined_reference_levels: 1}`); injected mid-rebuild failure leaves the copy content-identical (300 securities, tiers intact, migration marker intact, sentinel intact).

**Regression sweep:** 336 passed / 5 failed across the 19 test files importing the canon module. All 5 failures reproduce identically on the pristine script (stash-rerun proof) — pre-existing live-baseline drift from today's legitimate thesis work (e.g., Tier B coverage positive control now sees 32 vs frozen 18), not caused by this change.

## What the fixes deliberately do NOT change

- The rebuild still resets tiers from legacy JSON, resurrects `tier_routing_state` (access-validator check `legacy_tier_routing_and_consumers_retired` would fail), recomputes scope flags from frozen proofs, re-adds `source_artifacts` rows, and drops audit history. Items 1, 2, 5, 6 of the brief remain open pending the disposition decision — the fixes only remove the two loss/corruption mechanisms that would bite even a deliberate, owner-approved rebuild.
- `build_report` still writes the synced universe JSON before `build_db` runs (cross-surface ordering gap; moot for migrated canon under recommendation (a)).
- `raw_json` tier disagreement (273/300): do not fix via rebuild. Either a scoped SQL writer rewrites `raw_json` to mirror the `tier` column under its own gate, or `raw_json` is documented as a frozen JSON-era audit mirror.

## Owner decisions requested

- **D1:** Approve implementing the (a) refusal guard: `--write` detects the `alerts_os_sql_canon_migration` audit event and refuses, with an explicit owner override that names the migration (and, if still wanted, the tier-drift SHA gate). This also closes the missing-guard gap from the discrepancy above.
- **D2:** Approve the (c) retirement sequence and its prerequisites (P4-2 landing, WAL-safe restore proof, manifest recovery-route flip, restore drill).
- **D3:** Disposition for item 6 (`raw_json` legacy tier mirror).

## Proof artifacts

- `tmp/finance-sql-canon-rebuild-disposition-20260927/proof_harness.py` (rerunnable: `--phase pre|post`)
- `tmp/finance-sql-canon-rebuild-disposition-20260927/proof-pre.json`, `proof-post.json` (pre/post states, sentinel, injected-failure drills, hashes)
- Canon copies used: `canon-pre-rebuild.sqlite`, `canon-pre-atomic.sqlite`, `canon-post-rebuild.sqlite`, `canon-post-atomic.sqlite` (same directory)
