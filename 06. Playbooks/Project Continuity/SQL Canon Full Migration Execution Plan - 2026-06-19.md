# SQL Canon Full Migration Execution Plan - 2026-06-19

## Purpose

Create a phased execution plan that lets Veritas continue the SQL-canon migration without stopping at every routine phase, while preserving exact stop gates for destructive, authority-changing, external, portfolio/canon, cron, and finance-execution actions.

This plan is based on live state as of 2026-06-19 after the WF78/WF85/DB lifecycle archive work and the narrow `tier_routing_state` SQL refresh.

## Current State

- Lane register: active lanes `0`.
- SQL production-grade answer boundary: Tier A/A-READY only.
- Current strategic production-grade tickers: `GOOG`, `NVDA`, `VRT`.
- Legacy 42: compatibility only, not the strategic production boundary.
- WF78 routing SQL parity: `0` diffs after narrow refresh.
- `reference_levels` production-grade rows for `GOOG`, `NVDA`, `VRT` remain sourced from `tmp/execution-board-canon-anchor-pilot.json`.
- Production-grade reference parity: `3/3`, drift `0`.
- WF84 canonical data plane: `ok`.
- WF84 phase 6-10: `ok`; consumer default switch allowed for proven default consumers only.
- WF85 full-answer assembler: `ok`, 200/200 built.
- Consumer inventory: `535` consumers, `467` backlog, `103` raw-SQL review surfaces.
- Consumer burndown: `35` SQL-primary guarded, `75` SQL-shadow validated, `324` source producer.

## Single Approval Envelope

If Randall approves this plan, Veritas may execute Phases 0-7 without asking at each subphase, provided every phase stays inside the authority boundaries below and passes its own validators.

Plan approval authorizes:

- local code edits for SQL-canon consumer migration
- local validator and proof-artifact updates
- derived JSON/SQLite proof refreshes
- narrow SQL current-state row refreshes for non-capital routing/reference metadata only when a script proves exact scope, backup, rollback, post-apply parity, and no forbidden authority flags
- consumer cutover from source/legacy compatibility helpers to typed SQL-canon access when A/B parity is proven and fallback/source-open behavior remains
- archive planning packets and readiness reports
- lane leases and closeouts for exact write surfaces

Plan approval does not authorize:

- hard delete
- SQL schema mutation
- cron schedule mutation
- config/auth/network/channel/credential/startup/service mutation
- public/customer/external delivery
- portfolio/canon/cash/sizing/risk-rule mutation
- source-feeder retirement
- Python fallback retirement
- finance front-door or answer-path ownership promotion to SQL-first
- live or paper orders
- brokerage/account action
- capital deployment
- inferred owner approval for trading or execution

## Hard Stop Gates

Stop for Randall approval before any of these:

- hard delete or irreversible cleanup
- moving/archive of a newly identified lifecycle surface not named in an already approved packet
- SQL schema change or table contract break
- cron schedule mutation or runtime service/channel mutation
- source-feeder retirement
- Python fallback retirement
- finance answer-path ownership or SQL-first promotion
- customer/public output
- portfolio/canon/cash/sizing/risk-rule mutation
- paper/live/account/brokerage/capital action
- any validator reports critical errors that cannot be repaired within the same phase without broad authority expansion

## Phase 0 - Control Preflight

Goal: confirm no collision and refresh live truth surfaces.

Commands:

```powershell
python scripts\concurrent_lane_manager.py --status --write --validate
python scripts\workflow_router.py WF72 --answer all --validate
python scripts\workflow_router.py WF78 --answer all --validate
python scripts\workflow_router.py WF84 --answer all --validate
python scripts\workflow_router.py WF85 --answer all --validate
python scripts\finance_sql_canon_access.py --write --validate
python scripts\finance_production_grade_policy_gate.py --write --validate
python scripts\sql_canon_consumer_inventory.py --write --validate
python scripts\finance_sql_consumer_migration_burndown.py --write --write-md --validate
```

Acceptance:

- lane register active count is `0`
- SQL access guard is `ok`
- production-grade policy gate is `ok`
- production-grade tickers are still `GOOG`, `NVDA`, `VRT`
- inventory and burndown artifacts are fresh

## Phase 1 - Consumer Classification Freeze

Goal: split the backlog into executable batches so consumer migration proceeds without broad ad hoc edits.

Inputs:

- `tmp/sql-canon-consumer-inventory.json`
- `tmp/sql-canon-consumer-migration-backlog.json`
- `tmp/finance-sql-consumer-migration-burndown.json`

Batches:

- Batch A: `typed_access_guard_lane`
- Batch B: `answer_path_parity_lane`
- Batch C: `wf78_wf77_routing_lane`
- Batch D: `test_parity_lane`
- Batch E: `cron_pm_governance_lane`
- Batch F: `pm_cockpit_lane`
- Batch G: `source_loader_lane`
- Batch H: `raw_sql_review`

Acceptance:

- each batch has exact files, owner lane, fallback rule, parity command, and stop line
- no consumer file is patched before its batch has A/B proof or typed-access replacement

## Phase 2 - Typed Access Guard Expansion

Goal: migrate ordinary consumers away from direct legacy helpers/raw SQL and into `finance_sql_canon_access.py` or validated WF84/WF85 typed surfaces.

Allowed work:

- replace direct legacy production checks with explicit `production_answer_tickers()` or `legacy_production_answer_tickers()` as appropriate
- replace raw SQL reads with typed methods when equivalent fields already exist
- add or repair validator coverage

Required proof:

```powershell
python scripts\finance_sql_canon_access.py --write --validate
python scripts\sql_canon_consumer_registry_guard.py --write --validate
python scripts\sql_canon_answer_path_ab_harness.py --write --validate
python scripts\changed_file_validator_router.py --write --validate
```

Acceptance:

- no strategic consumer depends on `legacy_production_42` as production boundary
- legacy 42 references are explicitly compatibility/governance only
- no production answer-path behavior changes without A/B proof

## Phase 3 - Shadow-Validated Consumer Promotion

Goal: promote the `75` SQL-shadow validated consumers to SQL-primary guarded where parity and fallback rules already prove safety.

Allowed work:

- consumer-local default switch to SQL/WF84/WF85 views
- retain JSON/source fallback
- update migration registry state
- update A/B harness expectations

Required proof:

```powershell
python scripts\canonical_finance_data_plane.py --write --write-db --validate
python scripts\canonical_finance_data_plane_phase6_10.py --write --validate
python scripts\full_intelligence_answer_parity.py --all --write --validate
python scripts\finance_sql_consumer_migration_burndown.py --write --write-md --validate
```

Acceptance:

- full-answer parity remains 200/200 and 3400/3400
- source-open and fallback contracts remain present
- burndown moves promoted consumers from `sql_shadow_validated` to `sql_primary_guarded`

## Phase 4 - Raw SQL Review And Typed Replacement

Goal: resolve the `103` raw-SQL review surfaces without breaking owner boundaries.

Allowed work:

- classify raw SQL as one of:
  - valid SQL-canon read
  - replace with typed access
  - source loader/producer
  - test fixture
  - retire candidate
- patch high-confidence typed replacements
- add missing typed methods only when backed by existing SQL tables and validators

Required proof:

```powershell
python scripts\sql_canon_consumer_inventory.py --write --validate
python scripts\sql_canon_consumer_registry_guard.py --write --validate
python scripts\finance_sql_canon_access.py --write --validate
python scripts\changed_file_validator_router.py --write --validate
```

Acceptance:

- raw SQL review count decreases
- no schema mutation
- no portfolio/canon mutation
- no direct DB writes outside approved current-state refresh scripts

## Phase 5 - Source Producer Partition

Goal: distinguish required source feeders from duplicate surfaces that can later be retired.

Allowed work:

- label source producers as retained feeder, duplicate proof surface, stale compatibility surface, or retirement candidate
- create retirement readiness packets
- update artifact index routing
- keep source feeders live unless a separate hard stop gate clears retirement

Required proof:

```powershell
python scripts\canonical_finance_data_plane_retirement_readiness.py --write --validate
python scripts\db_lifecycle_manifest.py --write --validate
python scripts\artifact_index.py incremental
python scripts\artifact_index.py validate
```

Acceptance:

- retirement candidates have exact file lists, references, hashes, and destination/rollback
- `archive_ready` may be prepared, but move/delete waits for exact gate unless already included in approved plan scope

## Phase 6 - P0 Answer-Path Closeout

Goal: prove the production answer route uses strategic Tier A/A-READY scope while legacy 42 remains compatibility-only.

Allowed work:

- repair stale labels and summaries
- update compatibility-only validators
- update answer-path A/B harness
- refresh WF84/WF85 proof surfaces

Required proof:

```powershell
python scripts\finance_production_grade_policy_gate.py --write --validate
python scripts\trade_grade_full_answer_assembler.py --all-wf84 --write --validate
python scripts\full_intelligence_answer_parity.py --all --write --validate
python scripts\ticker_answer_packet_retirement_plan.py --write --validate
```

Acceptance:

- strategic production count remains `3` unless Tier A/A-READY state changes through validated non-capital routing
- legacy compatibility count may remain `42`
- full answer parity remains clean
- no answer-path ownership promotion yet

## Phase 7 - Burndown Closeout And Readiness Packet

Goal: reduce routine backlog as far as possible and produce the next exact apply packet only when a hard stop is reached.

Required proof:

```powershell
python scripts\finance_sql_consumer_migration_burndown.py --write --write-md --validate
python scripts\sql_canon_consumer_inventory.py --write --validate
python scripts\finance_sql_canon_access.py --write --validate
python scripts\fast_path_qa.py --write --validate
python scripts\changed_file_validator_router.py --write --validate
python scripts\control_closeout_bundle.py --validation-budget shared --write --validate
python scripts\concurrent_lane_manager.py --status --write --validate
```

Acceptance:

- active lanes `0`
- closeout bundle `ok`
- next hard gate, if any, is named with exact files/tables/scope
- daily memory updated

## Phase 8 - Separate Approval Packet Only

This phase is not executable under plan approval. It is a packet generator for the next owner decision.

Generate exact approval packets for any of:

- SQL-first finance front-door promotion
- cron schedule cutover
- source-feeder retirement
- Python fallback retirement
- schema changes
- archive/delete of newly identified lifecycle surfaces

Packet requirements:

- exact scope
- exact files/tables
- reason
- before/after diff
- rollback path
- validators
- authority boundary
- stop lines

## Default Execution Order

1. Phase 0
2. Phase 1
3. Phase 2 Batch A and Batch B
4. Phase 3 for the 75 shadow-validated consumers
5. Phase 4 raw SQL review, high-confidence typed replacements first
6. Phase 5 source producer partition
7. Phase 6 P0 answer-path closeout
8. Phase 7 closeout and next packet

## Reporting Cadence

During execution, Veritas should send compact Telegram updates only at meaningful milestones:

- phase start
- material validator failure
- batch completion
- hard stop gate reached
- final closeout

No stop is required for routine successful subphase transitions inside the approved envelope.

## Current Next Action

Start Phase 0 and Phase 1, then execute Phase 2 against typed-access and answer-path parity lanes first. Do not start cron cutover, SQL-first promotion, source-feeder retirement, Python fallback retirement, hard delete, or portfolio/canon mutation under this plan.

## 2026-06-19 Phase Packet Extension Closeout

Main-session exception: Veritas/main kept this pass in the main lane because the work was a coordinating proof/packet extension, not a multi-writer implementation or destructive lifecycle action.

Proof packets:

- `tmp/sql-canon-migration-phase-executor.json`
- `tmp/sql-canon-migration-owner-decision-packet.json`

Current phase state:

- Phase 1 classification freeze: ready.
- Phase 2 typed-access guard expansion: review-ready.
- Phase 3 shadow registry promotion: blocked/exhausted with 0 eligible and 0 blocked shadow rows.
- Phase 4 raw-SQL review: empty; raw SQL present remains visible at 105 surfaces, but actionable review is 0.
- Phase 5 source-producer partition: ready; 346 retained source producers, 0 retirement candidates.
- Phase 6 P0 answer-path closeout: blocked pending exact promotion gate.
- Phase 7 burndown closeout: ready as review-only packet.
- Phase 8 owner decision packet: ready.

Partition result:

- Required finance feeders: 228.
- Validators/proof writers: 79.
- Cron/dashboard/operator surfaces: 31.
- Lifecycle/archive governance: 8.
- Retirement candidates: 0.

Hard stop gates still active:

- Source-feeder retirement: hold; retirement-ready count is 0.
- Python fallback retirement: hold; fallback retained, retirement-ready false, retire count 0.
- SQL-first/front-door promotion: hold; blockers are fallback-required registry rows, remaining parity-required rows, structural-only answer-path A/B proof, retained source feeders, and duplicate-surface retirement not ready.
- Duplicate-surface/schema cleanup: hold; archive-ready/delete-ready/apply-ready are 0.
- Cron schedule mutation: no change recommended for this SQL packet; cron has unrelated attention/blocker signals, but no SQL migration schedule change is justified here.

Validation:

- `python scripts\sql_canon_migration_phase_executor.py --write --validate` -> ok.
- `python scripts\sql_canon_consumer_inventory.py --write --validate` -> ok, 537 consumers, 469 backlog, 346 source producers, raw-SQL review 0.
- `python scripts\sql_canon_consumer_registry_guard.py --write --validate` -> ok.
- `python scripts\canonical_finance_data_plane_retirement_readiness.py --write --validate` -> ok, source-feeder retirement-ready 0, duplicate-surface retirement-ready 0.
- `python scripts\trade_grade_full_answer_assembler.py --all-wf84 --write --validate` -> ok, 200/200 full answers, 0 validation errors/warnings.
- `python scripts\workflow_routing_index.py --write --write-db --validate` and `python scripts\workflow_router.py --all --write-capsules --validate` -> ok.
- `python scripts\changed_file_validator_router.py --write --validate` -> ok.
- `python scripts\control_closeout_bundle.py --validation-budget shared --write --validate` -> ok.

Route note:

- WF72 route now reflects the current support-only SQL-primary migration posture and exact hard gates.
- WF78 still reports `effective_status=stale` from PM/WF78 source freshness, not from this SQL migration packet. Treat that as a separate WF78 refresh lane, not as authorization to promote/retire SQL surfaces.

Next safe action:

- Continue proof-only source-producer and answer-path readiness refinement, or refresh the separate stale WF78/tier-promotion PM lane. Do not promote SQL-first answer ownership, retire Python fallback, retire source feeders, mutate cron schedules, or apply duplicate-surface/schema cleanup without a separate exact approval packet.

## 2026-06-20 Approved Archive And Duplicate-Cleanup Closeout

Randall approved the versioned archive of the 42 legacy WF85 ticker-answer packets and approved duplicate-surface cleanup. Main session executed only the validator-proven archive move and no-op cleanup proof.

Completed:

- Applied the 42-packet versioned archive to `09. Archive/WF85 Legacy Ticker Answer Packets/versioned/legacy-42-regenerated-20260620`.
- Hardened the archive apply and versioned archive packets so post-archive proof reports `already_archived` / `versioned_archive_completed` instead of false missing-candidate blockers.
- Hardened the SQL Canon completion runner so it no longer calls WF85 assembler with `--write-legacy-packets`; archived legacy snapshots should not be regenerated by closeout proof.
- Updated the SQL Canon parallel phase executor so Phase B is `versioned_archive_completed`; Phase A remains owner-review/apply-blocked, Phase C internal/customer-blocked, Phase D runtime-blocked, and Phase E market-window-shadow-blocked.
- Reclassified SQL reference-level rollback-drill DBs as rollback proof in `db_lifecycle_manifest.py`.
- Applied bounded consumer-registry sync for the new SQL Canon completion-runner test row; backup: `backups/finance-sql-canon-migration/finance-canon-consumer-registry-sync-20260620T223643Z.sqlite`.

Current SQL Canon closeout state:

- Completion runner: `status=ok`.
- Track A: `complete`.
- Track B: `complete_retained`.
- Track C: `owner_packet_ready`.
- Consumers: `567`.
- Backlog registry: `501`.
- SQL-primary guarded: `136`.
- Source producers retained: `361`.
- Raw SQL present: `110`.
- Raw SQL review/actionable: `0`.
- Full-answer parity: `ok`.
- Hard-gate actions allowed: `[]`.

Duplicate cleanup result:

- DB lifecycle archive-ready/delete-ready: `0`.
- Duplicate-surface retirement-ready: `0`.
- Source-feeder retirement-ready: `0`.
- Python fallback retirement-ready: `false`.
- SQL-first front-door promotion: `review_ready_not_promotable`; still separately owner-gated.
- Cron schedule mutation: no SQL migration schedule change recommended.

WF85-WF87 posture after refresh:

- WF85: ready as internal review-only decision OS; `200` answer-ready, `0` approval-eligible, `0` execution-authority rows.
- WF86: shadow mode ready but autonomous paper execution blocked; `15/20` clean shadow decisions, `5/5` sessions, reconciliation still blocked.
- WF87: Phase A hardening implemented but runtime blocked; command center reports `runtime_blocked`, `15/20` shadow decisions, and all runtime blockers explained.

Validation:

- `python scripts\ticker_answer_packet_archive_apply.py --archive-root "09. Archive\WF85 Legacy Ticker Answer Packets\versioned\legacy-42-regenerated-20260620" --write --validate` -> `already_archived`, validation ok.
- `python scripts\ticker_answer_packet_versioned_archive_packet.py --write --validate` -> `versioned_archive_completed`, validation ok.
- `python scripts\sql_canon_migration_completion_runner.py --write --write-md --validate` -> ok.
- `python scripts\sql_canon_parallel_phase_executor.py --write --validate` -> ok, Phase B completed.
- `python scripts\db_lifecycle_manifest.py --write --validate` -> ready_for_owner_decision, unknown 0, integrity errors 0.
- Focused SQL/archive/WF85-WF87 pytest suites passed.
- `python scripts\changed_file_validator_router.py --write --validate` -> ok.
- `python scripts\control_closeout_bundle.py --validation-budget shared --continue-on-failure --skip-cockpit-validate --write --validate` -> ok.

Boundary held:

- No source-feeder retirement, Python fallback retirement, SQL-first promotion apply, hard delete, cron schedule mutation, portfolio/canon/cash/sizing/risk mutation, customer/external output, paper/live/account/brokerage action, money movement, or capital/execution approval inference.
