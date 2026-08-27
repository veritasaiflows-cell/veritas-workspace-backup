# SQL Primary Finance Canon Migration Audit and Finish Line Plan - 2026-06-19

## Executive Conclusion

The right workflow home is **WF72 - Financial OS SQL Support / SQL-Primary Migration**.

Do not create a new workflow. The migration is a WF72 finish-line lane because WF72 already owns SQL support/cache/index authority, support-only SQL guardrails, artifact-index hygiene, and SQL/canon efficiency boundaries. WF84 and WF85 remain the finance data plane and decision OS consumers. WF78 remains the non-capital routing/feed repair lane. WF72 owns the SQL-primary migration process and gates.

Blunt state: the architecture is directionally right, but the SQL reference layer is not yet trustworthy as a green/red health signal for current bands. The new proof shows the drift is broader than the initial GOOG/NVDA/VRT spot check:

- Execution Board anchor preview: `42` rows
- SQL `reference_levels` rows for those tickers: `42`
- Matches: `4`
- Drift: `38`
- Missing SQL: `0`

That means the next work is not another audit. The next work is a gated derived-refresh dry-run for SQL `reference_levels`, followed by an apply packet only if backup/rollback, all-42 parity, and post-write validation are clean.

## Authority Boundary

This audit is a review and implementation plan. It does not authorize:

- SQL data mutation
- SQL schema mutation
- cron schedule mutation
- human canon or portfolio note mutation
- archive, move, or delete
- SQL-first finance answer-path ownership
- Python fallback retirement
- customer/public output
- capital deployment
- paper/live execution
- brokerage/account action
- money movement
- owner approval inference

Any future SQL apply needs its own exact gated packet: proposed diff, backup/rollback, source hashes, validator proof, and explicit approval for the apply step.

## What Changed Today

Implemented review-only control surfaces:

1. `scripts/finance_sql_primary_migration_plan.py`
   - Records the decision to finish SQL-primary migration with schedule and parity.
   - Current status: `warning`, not fake green.
   - Current registry state:
     - `434` consumer registry rows
     - `35` `sql_primary_guarded`
     - `75` `sql_shadow_validated`
     - `324` `source_producer`
     - SQL-primary completion: `8.06%`

2. `scripts/finance_sql_markdown_field_ownership.py`
   - Classifies reconciliation fields into:
     - `canon_anchor_required`
     - `sql_proof_only`
     - `human_judgment_only`
   - Current proof:
     - `24` rows classified
     - `19` cross-class review-needed rows are no longer fake SQL/Markdown blockers
     - `5` true matches remain matches

3. `scripts/execution_board_canon_anchor_pilot.py`
   - Generates a 42-ticker review-only Execution Board anchor preview.
   - Does not edit `03. Portfolio/Execution Board.md`.
   - No unsafe authority flags.

4. `scripts/execution_board_canon_anchor_drift_validator.py`
   - Compares anchor preview values to SQL `reference_levels`.
   - Current proof:
     - `42` anchors
     - `42` SQL rows
     - `4` match
     - `38` drift
     - `0` missing SQL
   - Domain status is correctly `blocked`.

5. `scripts/artifact_index.py`
   - Added `v_cockpit_action_queue_deduped`.
   - Raw queue remains available as `v_cockpit_action_queue`.
   - Current proof:
     - raw queue rows: `61`
     - de-duped queue rows: `38`
     - duplicate de-dupe keys: `0`

## Durable Pickup Surfaces Updated

- `state/workflows/WF72.json`
  - WF72 is now `support_only_with_active_sql_primary_migration`.
  - Primary route artifact is `tmp/finance-sql-primary-migration-plan.json`.
  - Drift blocker and next step are explicit.

- `06. Playbooks/Active Workflows.md`
  - SQL/data posture now names the SQL-primary migration blocker.
  - WF72 row now points to the derived-refresh dry-run as next safe work.

- `06. Playbooks/Project Continuity/Workflow 72 - Financial OS Efficiency Restructure and Priority Compression.md`
  - Added restart commands, proof artifacts, blocker counts, and finish-line gates.

- `memory/2026-06-18.md`
  - Daily memory has the implementation proof and stop lines.

## Current Architecture

### Human Canon

Human-facing notes remain the durable owner-facing surface. For this lane the critical note is:

- `03. Portfolio/Execution Board.md`

It currently holds the 42 decision rows as Markdown table/prose. The audit direction is not to delete this note or make SQL outrank it blindly. The right next step is to add structured anchor handling so machines do not keep reparsing prose/table text as the only route.

### SQL Canon

Primary DB:

- `state/finance/finance-canon.sqlite`

Current guarded SQL tables cover:

- securities
- universe membership
- answer path scope
- evidence status
- tier routing state
- reference levels
- evidence freshness
- source lineage
- consumer migration registry
- authority events
- migration validation runs

SQL is intended to become the internal current-state routing layer for finance state. But it is not yet safe to treat `reference_levels` as current truth because anchor-vs-SQL drift is material.

### JSON Proof

JSON remains the rebuildable proof and review layer. The target is not to remove JSON proof. The target is to stop maintaining duplicate "current state" JSON mirrors when SQL plus source lineage can own machine lookup.

Relevant current proof:

- `tmp/finance-sql-primary-migration-plan.json`
- `tmp/finance-sql-markdown-field-ownership.json`
- `tmp/execution-board-canon-anchor-pilot.json`
- `tmp/execution-board-canon-anchor-drift-validator.json`
- `tmp/veritas-artifact-index.sqlite`

## Findings

### F1 - SQL reference levels are stale or source-mixed

Severity: P1

Evidence:

- Anchor-vs-SQL drift validator: `38/42` rows drift.
- SQL `reference_levels` still has `3` source artifact families:
  - `tmp/finance-intelligence-state.sqlite`
  - `03. Portfolio/Execution Board.md`
  - `tmp/wf78-tier-weighted-freshness-resolution.json`
- The migration plan reports SQL-primary completion at only `8.06%`.

Impact:

The system cannot trust SQL `reference_levels` as a green/red current-state signal. If a downstream validator sees SQL disagreeing with the Execution Board, it is correct to block until derivation and parity are repaired.

Recommendation:

Build a review-only derived-refresh dry-run for `reference_levels` from one approved daily source family, then apply only after exact approval and full validation.

### F2 - SQL/Markdown reconciliation was creating fake blockers

Severity: P1

Evidence:

- Previous reconciliation had `19/24` review-needed rows.
- Field ownership classifier now proves all `24` rows are classifiable.
- The `19` review-needed rows are cross-class issues, not true SQL/Markdown parity blockers.

Impact:

Without field ownership, machine proof fields such as `deployment_proof_status` and freshness labels get compared against human prose. That creates fake blockers and wastes review cycles.

Recommendation:

Keep the classifier in the SQL-primary workflow. Reconcile only fields that belong in the same class. Do not compare SQL proof-only fields to human judgment prose as blockers.

### F3 - Execution Board needs structured anchors before broad SQL-primary trust

Severity: P1

Evidence:

- Anchor pilot produced all `42` anchors without unsafe authority flags.
- The note still stores current-state fields in a Markdown table.

Impact:

Machines must parse table/prose to find ticker, lane, action state, close/date, band, stop, source/freshness, and authority. This is fragile and easy to drift.

Recommendation:

Pilot structured canon anchors for the 42 decision tickers. First generate preview only. Later, with exact approval, insert/update anchor blocks in the Execution Board or a generated companion surface.

### F4 - Cockpit action queue duplicate load is reduced but not yet migrated

Severity: P2

Evidence:

- Raw cockpit queue: `61` rows.
- De-duped view: `38` rows.
- Duplicate keys in de-duped view: `0`.

Impact:

Operator queue load is cleaner, but consumers still need to opt into the new view. Keeping the raw queue is correct for rollback and audit.

Recommendation:

Use `v_cockpit_action_queue_deduped` for operator-facing queue reads after one more clean index validation window.

### F5 - SQL migration is real but incomplete

Severity: P2

Evidence:

- Registry rows: `434`
- SQL-primary guarded: `35`
- Shadow validated: `75`
- Source producer: `324`

Impact:

The system is paying for both SQL and source parsing without getting full SQL-primary efficiency.

Recommendation:

Run a weekly burn-down lane that moves consumers from source/shadow to SQL-primary only after parity and fallback guards pass. Track percent complete in WF72.

## Finish-Line Target Architecture

One source of truth per fact:

- Human judgment: authored notes.
- Current structured finance state: SQL, after parity and scheduled derivation are clean.
- Proof and rebuild trail: JSON artifacts and source lineage.
- Operator queue: SQL-derived views, with de-duped route for human-facing action queues.

The intended route after finish:

1. Daily finance refresh updates source proof and Execution Board anchor/source state.
2. Reference-level derived-refresh dry-run compares intended SQL rows to current SQL.
3. If clean and approved, SQL `reference_levels` updates from the approved source family.
4. SQL-canon access guard validates DB integrity, authority flags, source lineage, and false authority.
5. WF84/WF85 consume SQL through typed access with fallback retained until repeated parity windows are clean.
6. JSON mirrors are demoted only after consumer search, parity proof, archive/rollback plan, and approval.

## Parallel Implementation Plan

### Lane A - Reference Levels Derived Refresh Dry-Run

Owner: WF72

Deliverable:

- New review-only script that builds a row-level SQL `reference_levels` patch packet from the 42 Execution Board anchors.

Inputs:

- `tmp/execution-board-canon-anchor-pilot.json`
- `state/finance/finance-canon.sqlite`
- `tmp/technical-refresh.json`
- source lineage artifacts as available

Output:

- `tmp/reference-levels-derived-refresh-dry-run.json`
- optional `.md` human review packet

Acceptance:

- Shows before/after values for all 42 rows.
- Includes source path, hash, timestamp, and source family decision.
- Performs no SQL write.
- Flags apply readiness false until backup/rollback is present.

Stop line:

- Do not write `state/finance/finance-canon.sqlite`.

### Lane B - Reference Levels Apply Packet

Owner: WF72, gated by Randall approval

Deliverable:

- Exact apply packet for SQL `reference_levels` after dry-run is reviewed.

Required proof:

- DB backup/export path.
- Rollback command/recipe.
- Row count and row hash before/after.
- All-42 anchor parity expected after apply.
- `finance_sql_canon_access.py --write --validate` expected green.

Stop line:

- No apply without explicit approval after reviewing Lane A dry-run.

### Lane C - Anchor Integration Proposal

Owner: WF72 with canon/portfolio gate awareness

Deliverable:

- Proposal for where anchors should live:
  - embedded in `03. Portfolio/Execution Board.md`, or
  - generated companion anchor surface, or
  - SQL-owned anchor table with Markdown pointer.

Acceptance:

- Parser compatibility preserved.
- No owner-facing note bloat.
- No generated proof pasted into prose.
- Clear rollback.

Stop line:

- No Execution Board mutation without exact gated note apply.

### Lane D - Consumer Migration Burn-Down

Owner: WF72, with WF84/WF85 consumer review

Deliverable:

- Registry burn-down packet ranking the `324` source-producer consumers.

Acceptance:

- Each consumer has:
  - owner script/path
  - field family
  - parity command
  - fallback behavior
  - cutover target
  - rollback path

Stop line:

- No SQL-first consumer migration until the field family passes parity.

### Lane E - Duplicate Surface Retirement Plan

Owner: WF72 / workspace governor, after SQL reference-level parity is clean

Deliverable:

- Archive/demotion proposal for duplicate JSON mirrors and raw_json/schema waste.

Acceptance:

- Consumer search proves no active data dependency.
- Source lineage replaces removed raw_json use.
- Archive/rollback plan exists.

Stop line:

- No archive/delete/schema cleanup without separate approval.

## Tomorrow Pickup

Start here:

```powershell
python scripts\workflow_router.py WF72 --answer all
python scripts\finance_sql_primary_migration_plan.py --write --write-md --validate
python scripts\execution_board_canon_anchor_pilot.py --write --write-md --validate
python scripts\execution_board_canon_anchor_drift_validator.py --write --validate
```

Then implement Lane A:

- Add a review-only `reference_levels` derived-refresh dry-run packet.
- Do not mutate SQL.
- Use the existing anchor preview as the intended current-state source.
- Make the packet fail closed when any anchor is missing band/stop/source hash.
- Make the packet produce a proposed SQL row diff and source-family decision.

After Lane A:

```powershell
python scripts\finance_sql_canon_access.py --write --validate
python scripts\artifact_index.py incremental
python scripts\artifact_index.py validate
python scripts\changed_file_validator_router.py --write --validate
```

If Lane A is clean, ask for explicit approval for Lane B apply. Do not infer approval from this audit.

## Acceptance Criteria For Finish Line

The migration is not finished until all of this is true:

- SQL `reference_levels` matches the approved daily source for all 42 decision tickers.
- `reference_levels.source_generated_at_utc` matches the current daily technical/band refresh window.
- SQL `reference_levels` has one approved source family or a documented exception list.
- `execution_board_canon_anchor_drift_validator.py` reports `ok`.
- `finance_sql_canon_access.py --write --validate` reports `ok`.
- Consumer migration registry shows rising `sql_primary_guarded` count or explicit out-of-scope classifications.
- De-duped cockpit queue is used by operator-facing reads after validation.
- JSON mirrors and raw_json/schema cleanup remain deferred until parity and rollback proof are complete.
- No generated artifact, SQL row, or dashboard becomes approval, execution authority, or portfolio/canon mutation authority.

## Current Proof Commands

Known clean:

```powershell
python scripts\finance_sql_primary_migration_plan.py --write --write-md --validate
python scripts\finance_sql_markdown_field_ownership.py --write --validate
python scripts\execution_board_canon_anchor_pilot.py --write --write-md --validate
python scripts\execution_board_canon_anchor_drift_validator.py --write --validate
python scripts\finance_sql_canon_access.py --write --validate
python scripts\artifact_index.py incremental
python scripts\artifact_index.py validate
python scripts\changed_file_validator_router.py --write --validate
```

Expected truth:

- The drift validator is allowed to produce domain `status=blocked` until the SQL reference-level repair is done.
- Script validation can still be `ok`; that means the validator ran correctly and found real drift.

## Risks

- Updating SQL before source family is chosen could preserve the same drift problem under a new timestamp.
- Embedding anchors directly in human notes could bloat the Execution Board if not controlled.
- Treating SQL as current truth before reference-level parity is clean could break finance answers.
- Retiring JSON mirrors or raw_json before consumer search could break fallback/rebuild paths.
- Reclassifying fake blockers too broadly could hide a real consumer-authority regression. Keep field ownership explicit.

## Recommendation

Proceed with WF72 Lane A tomorrow: build the `reference_levels` derived-refresh dry-run packet.

Do not touch SQL data yet. The first finish-line deliverable is a clean proposed row diff and parity packet. Once that exists, the apply decision becomes concrete instead of theoretical.
