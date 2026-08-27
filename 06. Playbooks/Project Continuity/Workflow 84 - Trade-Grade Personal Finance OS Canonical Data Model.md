# Workflow 84 - Trade-Grade Personal Finance OS Canonical Data Model

## Status

Opened 2026-06-08 after Randall approved keeping the work explicitly as internal finance infrastructure, not a retail database launch.

2026-06-11 durable universe policy: `data/finance/universe-v1.json` remains a retained WF78/WF84 universe registry and source-lineage input. It is not retired, not canon/approval authority, and not fast-moving market data. WF84 should validate it by schema, authority boundary, 200-row scope, semantic digest, and parity with downstream router/current-state surfaces; file age alone should not block WF84/WF85 freshness. Retirement is a future gated migration only after consumer inventory, WF84 rebuild parity from a replacement source, rollback/export proof, DB lifecycle classification, and explicit owner approval for archive/delete are clean.

Current state: Phases 0-10 implemented through read-only consumer expansion, parity, source drillback, priority queue, and retirement gating. The owner artifacts are:

- `tmp/canonical-finance-data-plane-contract.json`
- `tmp/canonical-finance-data-plane.json`
- `tmp/canonical-finance-data-plane-validation.json`
- `tmp/canonical-finance-data-plane.sqlite`
- `tmp/canonical-finance-data-plane-phase6-10.json`
- `tmp/canonical-finance-data-plane-retirement-readiness.json`

The primary writer is `scripts/canonical_finance_data_plane.py`. It builds a validated JSON packet first and loads the derived SQLite companion from that packet only.

## 2026-06-19 SQL/JSON internal decision-canon cutover

Randall approved using guarded `state/finance/finance-canon.sqlite` plus JSON proof packets as the primary internal review-only decision/routing source for finance consumers. WF84 remains the normalized data-plane interface above that guarded current-state layer; it does not replace source-open proof, owner notes, or retained fallback surfaces.

Current proof:
- `python scripts\finance_sql_canon_access.py --write --validate` passed.
- `python scripts\canonical_finance_data_plane.py --write --write-db --validate` passed with `200` active rows, Tier A/B/C `18/30/152`, SQLite integrity `ok`, and forbidden authority counts `0`.
- `python scripts\canonical_finance_data_plane_phase6_10.py --write --validate` passed with `consumer_default_switch_allowed=true`, `default_switched_consumer_count=4`, `fallback_surfaces_retained_for_resilience=true`, and `archive_delete_apply_allowed=false`.
- Retirement/lifecycle proof remains conservative: archive-ready `0`, delete-ready `0`, apply-allowed `0`, source-feeder retirement-ready `0`, duplicate-surface retirement-ready `0`.

Operational rule: internal consumers may prefer the typed SQL-canon guard plus JSON proof packets only when validation is clean. Material finance claims still require source-open drillback, and trade-grade decision readiness must check WF78/WF85 freshness gates before any recommendation language is treated as current.

## Purpose

Build a formal internal canonical finance data model for a trade-grade personal OS:

- one stable machine-readable contract for core finance facts
- validated feeder paths from WF78 and current finance intelligence state
- source/freshness/lineage on material finance fields
- hard authority flags that keep recommendations, capital, paper/live execution, and account actions owner-gated
- faster ticker answers, decision cards, repair queues, and PM/dashboard reads without treating SQL or generated artifacts as approval

## Scope

In scope:
- internal personal finance infrastructure
- canonical schema contract and read-only packet writer
- later derived SQLite companion after JSON contract validation is clean
- WF78 auto-router and `finance-intelligence-state` as feeder/proof surfaces
- decision-readiness, evidence, price/technical, entry/stop, source-lineage, and validation-result tables
- strict false authority flags for capital, execution, paper/live, account, money movement, canon/portfolio mutation, customer/public output, and owner approval inference

Out of scope:
- retail/customer launch
- customer, account, suitability, tax, retirement, income, net-worth, brokerage, credential, or PII data
- live brokerage endpoints or account writes
- paper/live submit/cancel/sell
- capital deployment approval
- portfolio/cash/sizing/risk-rule mutation
- SQL-first promotion or generated artifacts becoming canon

## Phase Plan

### Phase 0 - Contract And Route Registration

Deliverables:
- `scripts/canonical_finance_data_plane_contract.py`
- `tmp/canonical-finance-data-plane-contract.json`
- WF84 Active Workflows row, route capsule, and PM lane visibility

Acceptance:
- contract validates
- workflow route/capsule validates
- artifact index sees the contract
- PM packet sees WF84 as an actionable internal infrastructure lane

Status: complete.

### Phase 1 - Read-Only Canonical Packet Writer

Artifacts:
- `scripts/canonical_finance_data_plane.py`
- `tmp/canonical-finance-data-plane.json`
- `tmp/canonical-finance-data-plane-validation.json`

Feeder order:
1. `tmp/wf78-auto-tier-routing.json`
2. `tmp/finance-intelligence-state.sqlite`
3. `tmp/wf78-tier-weighted-freshness-resolution.json`
4. `tmp/finance-decision-sync-spine.json` when present
5. ticker-card/current-state proof surfaces

Acceptance:
- 200 active tickers represented
- Tier A <= 25, Tier B <= 50, A+B <= 75
- 0 capital/trade/execution approval flags
- required fields carry source/freshness/lineage
- stale or missing feeders downgrade status instead of silently passing

Status: complete. Current packet validates with 200 active tickers, Tier A/B/C = 23/23/154, 14 schema families, 4,200 evidence-family rows, 15 owner-action rows, and 0 forbidden authority flags. The decision spine's 6 extra sector rows are recorded as optional enrichment, not merged into the active 200-row packet.

### Phase 2 - SQLite Companion

Artifact:
- `tmp/canonical-finance-data-plane.sqlite`

Acceptance:
- JSON packet remains source proof
- SQLite is rebuildable derived lookup only
- DB lifecycle manifest classifies it with 0 unknown and 0 integrity errors
- `PRAGMA integrity_check` and foreign key checks pass

Status: complete. SQLite has 14 strict tables, `PRAGMA integrity_check=ok`, foreign-key check clean, 200 rows in `v_current_decision_overview`, 15 rows in `v_owner_action_queue`, 200 rows in `v_decision_grade_os_layer`, 7 rows in `v_source_lineage_drillback`, and authority view counts 0/0. DB lifecycle classifies it as derived.

### Phase 3 - One Consumer Migration

Consumer:
- `finance_intelligence_state.py ticker <TICKER> --pretty`
- PM cockpit finance/ticker route
- future decision-card builder

Acceptance:
- consumer has fallback to existing route
- output parity is proven before default use
- no customer/public, canon/portfolio, or execution authority is widened

Status: advanced. `finance_intelligence_state.py ticker <TICKER>` now prefers `wf84_canonical_data_plane` when the WF84 phase 6-10 switch gate is clean, while preserving the existing answer-packet/source fallback and source-open rule. `GOOG` proof shows `canonical_data_plane_default_route.enabled=true` with no capital/execution authority.

### Phase 4 - Retirement Readiness Preview

Artifact:
- `tmp/canonical-finance-data-plane-retirement-readiness.json`

Acceptance:
- preview-only
- archive-ready count 0 unless separate exact lifecycle packet exists
- delete-ready count 0
- source feeders and fallback surfaces retained while WF84 remains an interface built from them

Status: complete / plan prepared. Current proof reviews 6 related surfaces, with archive-ready 0, delete-ready 0, and apply-allowed 0. The artifact now includes an owner-approval archive plan, but the recommended decision remains `do_not_archive_trade_grade_feeders_yet`; source feeders and fallbacks stay retained.

### Phase 5 - Decision-Grade OS Query Layer

SQLite views:
- `v_current_decision_overview`
- `v_owner_action_queue`
- `v_decision_grade_os_layer`
- `v_source_lineage_drillback`
- `v_authority_boundary_false`

Acceptance:
- one query exposes ticker, tier, queue state, price/band/stop context, owner-action flag, and authority boundary
- source drillback remains available
- forbidden authority counts remain 0

Status: complete. Current OS layer has 200 rows: 15 `owner_review_queue` rows and 185 `review_only_freshness_blocked` rows. This is decision support, not approval.

### Phase 6 - Consumer Expansion

Artifacts:
- `tmp/canonical-finance-data-plane-phase6-10.json`
- PM cockpit read-only WF84 finance OS SQL adapter section
- `/api/finance-os`

Acceptance:
- additional consumers are visibility/overlay only
- existing answer fallback remains authoritative
- overlay/default route switch may turn on only while the phase proof stays clean
- authority violations cause ignore/fallback behavior, not decision adoption

Status: complete / switched on for read-only consumers. The local PM cockpit reads WF84 through allowlisted read-only SQLite queries for decision overview, owner-action queue, priority queue, source lineage, and authority counts. The ticker front door now prefers WF84 only when the phase switch gate is enabled. WF85 decision cards read WF84 SQLite as primary input, and the morning paper recommendation-card builder requires a WF84 canonical overlay for clean cards. Fallback/source surfaces remain retained.

### Phase 7 - Parity Harness

Artifact:
- `scripts/canonical_finance_data_plane_phase6_10.py`

Acceptance:
- router ticker set matches WF84
- tier-weighted freshness ticker set matches WF84
- Tier A/B/C counts match
- owner-action queue covers the capital-review queue
- parity is scoped to populated overlay fields only
- 6 decision-spine extras remain excluded from the active 200-row packet
- default-route switching is read-only and requires the phase proof to have 0 critical errors and 0 warnings
- full narrative/analyst/earnings value parity remains out of scope until a future value-level parity harness

Status: complete / switch proof clean. Current proof: 200 router rows, Tier A/B/C = 17/27/156, 18 WF84 owner-action rows, capital-review rows covered, router core fields match WF84, post-close price overlay matches WF84, and `consumer_default_switch_allowed=true` for 4 read-only default-switched consumers. This is not full answer-packet value parity.

### Phase 8 - Source Drillback Layer

SQLite views:
- `v_ticker_source_drillback`
- existing `v_source_lineage_drillback`

Acceptance:
- required source artifacts exist and carry hashes
- routing/price source IDs resolve
- price provenance reflects the winning source among decision spine, capital queue, and finance-state rows
- validation rows join back to the real schema run id
- source-open remains required before material finance claims

Status: complete. Current proof has 8 source-lineage rows and 442 ticker-source drillback rows. This is lineage/proof support only; it does not permit material finance claims from SQLite alone.

### Phase 9 - Decision Queue Prioritization

SQLite views:
- `v_wf84_priority_queue`
- `v_pm_decision_queue_overlay`

Acceptance:
- ranking is review-triage-only
- no capital/sizing/execution fields drive ranking
- no actionable row carries capital/trade/paper/live/owner-approval flags
- deterministic ordering with null route-priority tiebreak

Status: complete. Current priority queue has 200 rows, with 18 owner-action rows. It is a triage queue, not approval.

### Phase 10 - Retirement Candidate Proof

Artifact:
- `tmp/canonical-finance-data-plane-phase6-10.json`

Acceptance:
- retirement readiness remains preview-only
- archive-ready count remains 0 unless an explicit owner-approval token and lifecycle packet exist
- delete-ready count remains 0
- apply-allowed count remains 0
- lifecycle action, if ever approved, must hand off to `db_lifecycle_manifest.py`

Status: complete. WF84 retirement/apply remains blocked: archive/delete/apply all 0. Source feeders and fallback surfaces are retained.

### Full-Answer Parity Consolidation - 2026-06-09

Status: implemented / fail-closed. `scripts/full_intelligence_answer_parity.py` now defines the full ticker-intelligence answer contract, extracts old-stack answer packet/card sections, assembles WF84/WF85 section context, and writes parity artifacts under `tmp/full-answer-parity/`. Opus challenger review forced a hard distinction between pilot diagnosis and retirement proof; duplicate-surface retirement planning now requires `--all` full-WF84-population coverage.

Current WF84 schema additions:
- `full_answer_section_context`
- `v_full_ticker_answer_context`
- `v_full_answer_source_drillback`

Current proof:
- WF84 packet/SQLite validates with 15 canonical tables, 3,400 full-answer section rows, and 0 forbidden authority flags.
- Phase 6-10 proof validates with 54 checks, 0 critical, 0 warning, `consumer_default_switch_allowed=true`, and `archive_delete_apply_allowed=false`.
- Historical/superseded parity note: the initial full-answer parity full-population run covered 200 WF84 tickers and 3,400 section checks but was blocked with only 18 ticker passes and 182 critical blockers. This was superseded by the later full-population parity repair; current parity proof is status `ok` with 200/200 ticker passes and 0 critical tickers.
- Pilot-level drift remains useful repair signal: VRT has old-stack band/stop drift vs WF84's decision-spine band, BRK.B has old/new below-band vocabulary drift, and TLT technical posture is explicitly missing in both routes.
- Retirement readiness v2 includes ticker answer packets and ticker intelligence cards as duplicate/evidence surface classes. Archive/delete/apply remain 0; duplicate-surface retirement-ready count remains 0 until full-answer value parity is clean and DB lifecycle gates clear.
- Opus challenger artifact: `tmp/parallel-lanes/wf84-wf85-full-answer-parity-opus-challenger-20260609.json`.

Boundary: full-answer parity is a retirement and answer-routing validator only. It does not permit archive/delete/apply, canon/portfolio/cash/sizing/risk-rule mutation, capital deployment, paper/live/account action, or owner approval inference.

### Full-Answer Parity Repair Closeout / Retirement Planning Gate - 2026-06-09

Status: implementation complete and planning-ready; archive/delete/apply still blocked. After production-scope repair, `scripts/full_intelligence_answer_parity.py --all --write --pretty` now validates the full WF84 population with status `ok`.

Current proof:
- 200/200 WF84 tickers evaluated and passing.
- 3,400 full-answer section checks, 3,250 OK (`0.9559` informational ratio).
- 42 production full-answer-path rows, 0 production critical tickers.
- 158 thin-monitor rows, 0 thin-monitor critical tickers; these are card/WF84 monitor surfaces, not full-answer packet retirement candidates until classification is separately validated.
- Retirement readiness is OK with `archive_ready_count=0`, `delete_ready_count=0`, `apply_allowed_count=0`, and `full_answer_parity_ready_to_start_duplicate_surface_retirement_planning=true`.
- Owner-facing planning artifact: `tmp/wf84-wf85-duplicate-surface-retirement-approval-plan-20260609.json`.
- Opus CLI challenger artifact: `tmp/wf85-opus-challenger-closeout-20260609.json`, `qualified_pass_for_planning_only`.

Remaining planning gates before any actual duplicate-surface retirement:
- Validate the 158-row thin-monitor classification.
- Prove no target surface holds unique `technical_posture` content for the 150 shared-missing rows.
- Triage 8 latest-price overlay warnings before treating band-status retirement as fully canonical.
- Preserve serial regeneration order for parity proof: cards/answer packets first, then WF84 SQLite, then WF85 cards, then full-answer parity.
- Keep the WF72 no-drift bypass scoped to derived-card WF84 band-precedence refresh only.
- Keep DB lifecycle archive-ready counts separate from WF84/WF85 duplicate-surface authority.
- Require Randall exact per-surface approval before archive/delete/apply.

Boundary: WF84 is the read-only default data plane and full-answer parity now supports retirement planning. It still does not authorize archive/delete/apply, source-feeder retirement, fallback removal, canon/portfolio/cash/sizing/risk-rule mutation, capital deployment, paper/live/account action, or owner approval inference.

### Post-Challenger Hardening - 2026-06-08

Status: complete. Follow-up verification after the Claude challenger pass hardened the Phase 1/2 writer and Phase 0 contract without widening WF84 authority.

Added checks:
- accepted source-schema validation for WF84 JSON feeders
- required-source freshness thresholds
- generated-table primary-key uniqueness checks
- routing enum-domain checks
- decision actionability review-only vocabulary guard
- source-artifact reference resolution checks
- feeder-level forbidden authority scans across JSON feeders and selected finance-state SQL rows
- contract SQLite integrity detection through `PRAGMA integrity_check`, replacing weak table-name probing

Current proof: `canonical_finance_data_plane.py --write --write-db --validate` remains ok with 200 active rows, Tier A/B/C = 23/23/154, 23 validation-result rows, forbidden authority counts 0, feeder forbidden authority count 0, SQLite integrity ok, foreign-key errors 0, 15 owner-action queue rows, and 0 routing/decision authority violations.

### Cron And Heartbeat Posture - 2026-06-08

Status: complete. No separate WF84 cron job is needed. The existing weekday `Finance - WF78 Daily Freshness and Promotion Proof` owner job now refreshes WF84 after the WF78 feeder chain by running:

- `canonical_finance_data_plane.py --write --write-db --validate`
- `canonical_finance_data_plane_retirement_readiness.py --write --validate`
- `canonical_finance_data_plane_phase6_10.py --write --validate`

`cron_freshness_spine.py` now expects the WF84 packet, validation report, SQLite companion, phase 6-10 proof, and retirement-readiness proof from that daily chain. Heartbeat remains flag/handoff-only and may not execute WF84 phases inline. No skill mutation was required; the existing `cron-automation-manager` and `disciplined-implementation` skills cover the posture.

### WF84/WF85 Parallel Advancement Proof - 2026-06-08

Status: ready/ok after WF85 promotion-hardening pass. The ticker-card refresh feeder now emits standard `generated_at_utc` alongside legacy `generated_utc`, so WF84 can ingest a normal generated timestamp for the feeder artifact. The regenerated WF84 packet/SQLite is `status=ok`, SQLite integrity is ok, table counts cover 200 active tickers, Tier A/B/C remains 23/23/154, source artifact count is 7, owner-action queue count is 15, and forbidden authority true count remains 0.

Current proof:
- `python scripts\finance_ticker_card_refresh_gate.py --write --validate --skip-provider-refresh`
- `python scripts\canonical_finance_data_plane.py --write --write-db --validate`
- `python scripts\canonical_finance_data_plane_phase6_10.py --write --validate`
- `python scripts\workflow_router.py WF84 --answer all --write-capsules --validate`

Residual boundary: WF84 remains an internal read-only data plane. Consumer default switch, archive/delete apply, canon/portfolio/cash/risk-rule mutation, and capital/execution authority remain false.

## MVP Schema Families

- `schema_run`
- `source_artifact`
- `security_master`
- `universe_membership`
- `routing_state_current`
- `evidence_family_status`
- `price_technical_current`
- `entry_stop_reference`
- `fundamental_snapshot`
- `analyst_snapshot`
- `earnings_catalyst`
- `official_evidence`
- `decision_queue_state`
- `validation_result`

## Validation Ladder

Initial route/contract setup:

```powershell
python -m py_compile scripts\canonical_finance_data_plane_contract.py scripts\workflow_routing_index.py scripts\workflow_router.py scripts\pm_program_state.py scripts\pm_implementation_job_queue.py scripts\artifact_index.py scripts\truth_surface_inventory.py
python scripts\canonical_finance_data_plane_contract.py --write --validate
python scripts\canonical_finance_data_plane.py --write --write-db --validate
python scripts\canonical_finance_data_plane_phase6_10.py --write --validate
python scripts\canonical_finance_data_plane_retirement_readiness.py --write --validate
python scripts\db_lifecycle_manifest.py --write --validate
python scripts\workflow_routing_index.py --write --write-db --validate
python scripts\workflow_router.py WF84 --answer all --write-capsules --validate
python scripts\workflow_router.py --all --write-capsules --validate
python scripts\pm_control_packet.py --write --write-db --validate
python scripts\truth_surface_inventory.py --write --validate
python scripts\changed_file_validator_router.py --write --validate
python scripts\artifact_index.py incremental
python scripts\artifact_index.py validate
python scripts\control_closeout_bundle.py --validation-budget shared --write --validate
```

SQLite writer setup requires:

```powershell
python scripts\db_lifecycle_manifest.py --write --validate
python scripts\control_closeout_bundle.py --validation-budget major --write --validate
```

## Stop Lines

- No customer/account/PII/suitability/brokerage schema.
- No retail/customer/public launch claim.
- No canon/portfolio/cash/sizing/risk-rule mutation.
- No capital deployment, paper/live order, brokerage/account action, or money movement.
- No SQL/capsule/dashboard/generated row becomes owner approval.
- No owner approval inference.
- No archive/move/delete cleanup from this workflow unless a separate exact lifecycle packet and approval exists.
