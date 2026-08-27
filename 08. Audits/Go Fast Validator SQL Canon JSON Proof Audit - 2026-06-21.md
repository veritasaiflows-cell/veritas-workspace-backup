# Go Fast Validator SQL Canon JSON Proof Audit - 2026-06-21

## Classification

- Task type: audit, validator architecture review, SQL-first proof posture hardening plan.
- Authority: review-only. This audit does not approve canon mutation, portfolio mutation, cron schedule mutation, account action, paper execution, live execution, or Python retirement.
- Write scope used: this report plus validator proof refresh outputs in `tmp/`.
- Primary posture: keep Python as workflow owner/orchestrator/generator; use Go for fast, deterministic, fail-closed validation edges.

## Executive Conclusion

The current Go validator layer is healthy, fresh, and useful, but it is still mostly a set of point validators. The next hardening step should not be a broad Python-to-Go port. The highest return is to add a small number of Go validators that validate cross-artifact proof contracts across SQL canon, JSON proof packets, consumer registry state, and validator-route budget.

The SQL-first/canon structure is now mature enough for Go bundle validators. The main remaining gap is not raw SQL speed. Current benchmark evidence says Python `sqlite3` remains faster than Go in-process for small SQLite probes, while Go CLI process startup is slower. The value of Go here is compiled, deterministic, fail-closed checks that can run repeatedly in routing, closeout, and cron posture validation without relying on broad Python workflow context.

Recommended next implementation order:

1. `go-json-proof-contract-lint`
2. `go-sql-canon-proof-bundle-lint`
3. `go-canon-json-field-family-parity`
4. `go-sql-consumer-registry-drift-lint`
5. `go-validator-route-budget-lint`
6. `go-cron-contract-json-proof-lint`
7. `go-finance-canon-authority-event-lint`

Do not promote Go as the primary SQL route yet. Do not retire Python. Do not make Go write SQL/canon/portfolio artifacts.

## Evidence Snapshot

### Go Validator Estate

Current Go command binaries under `scripts/go/bin`: 17.

Current commands:

- `finance-sql-boundary-lint`
- `go-finance-data-coverage-probe`
- `go-finance-human-notes-sql-check`
- `go-finance-universe-validation-probe`
- `go-source-truth-parity-validator`
- `go-sql-500-expansion-design-gate`
- `go-sql-consumer-authority-guard`
- `go-sql-inprocess-readonly-probe`
- `go-sql-inventory-helper`
- `go-sql-latency-probe`
- `go-sql-source-truth-manifest`
- `go-wf78-sql-phase2-readiness-probe`
- `python-sql-contract-lint`
- `sql-proof-probe`
- `sql-schema-drift-lint`
- `wf74-boundary-lint`
- `wf75-smb-boundary-lint`

Current freshness proof:

- `go_binary_freshness_guard.py --write --validate`: `status=ok`, stale binaries `0`, missing binaries `0`.
- `go test ./...` from `scripts/go`: passed.

### Current Go Posture Proof

The current route evidence supports Go as a validator-only edge:

- `tmp/go-sql-inprocess-driver-pilot-gate.json`: `status=ok`; Go validator-only; Python owner/default retained; helpers compared `10`; helpers ok `7`; warnings `0`.
- `tmp/python-go-sql-helper-default-route-history-gate.json`: `status=ok`; default route remains `python_owner_only`; Go validator-only; Python retirement count `0`.
- `tmp/python-go-sql-helper-demotion-readiness-gate.json`: `status=ok`; candidate rows `76`; existing Go coverage `7`; ready for Go spike contracts `18`; durable output candidates `38`; Python retirement count `0`.
- `tmp/python-go-sql-migration-candidates.json`: `status=warning` but validation ok; `76` candidates; `18` ready for Go spike; `42` keep Python-governed; `4` need contract repair.

Blunt reading: there is real Go opportunity, but the evidence says "contract-first validator expansion," not "replace Python."

### SQL Canon Inventory

`state/finance/finance-canon.sqlite` is the central SQL canon proof surface. Current object count is 22.

Important tables and views:

- `securities`: 200 rows
- `reference_levels`: 200 rows
- `evidence_freshness`: 200 rows
- `evidence_status`: 200 rows
- `tier_routing_state`: 200 rows
- `universe_membership`: 200 rows
- `answer_path_scope`: 200 rows
- `source_lineage`: 3121 rows
- `consumer_migration_registry`: 516 rows
- `migration_validation_runs`: 27 rows
- `validator_runs`: 9 rows
- `current_active_universe`: 200 rows
- `current_sql_canon_routing`: 200 rows
- `review_monitor_universe`: 158 rows
- `current_answer_path`: 42 rows

This is enough structure to justify Go validators that inspect SQL families and cross-check JSON proof summaries without mutating anything.

### JSON Proof Packet Condition

Relevant proof packets are mostly green, but generated at different times and across different owners. This creates proof-sprawl risk.

Representative packet status:

- `tmp/finance-sql-canon-access-validation.json`: `status=ok`, read-only authority flags clean.
- `tmp/sql-canon-front-door-readiness-packet.json`: `status=readiness_green_promotion_still_owner_gated`; validation ok with warnings.
- `tmp/sql-canon-consumer-inventory.json`: `status=ok`; consumer count `585`; backlog count `516`; raw SQL retained guarded count `8`; P0 count `19`; P1 count `386`.
- `tmp/sql-canon-consumer-registry-guard.json`: `status=ok`.
- `tmp/sql-canon-migration-completion-runner.json`: `status=ok`; warnings include a closeout warning and intentionally retained source-producer rows.
- `tmp/sql-canon-owner-decision-packet.json`: `status=ready_for_owner_review`; validation ok.
- `tmp/sql-canon-answer-path-ab-harness.json`: `status=ok`.
- `tmp/sql-canon-wf78-routing-parity.json`: `status=ok`, but older than newer SQL/canon packets.
- `tmp/reference-levels-sql-native-source-family-proof.json`: `status=ok`; active rows `200`; reference rows `200`; row proof `200`; nonblocking source-family coverage gap noted.
- `tmp/md-finance-structured-drift-lint.json`: `status=ok`; findings `17`; requires-action count `0`.

The gap is that no single fast Go validator currently says: "The SQL canon, JSON proof packets, consumer registry, and authority boundaries agree as a bundle."

### Validator Routing And Timing Pressure

Current route proof shows a growing validation surface:

- `tmp/changed-file-validator-router.json`: `status=ok`, major budget, paths `570`; warnings for large diff path count and ignored tmp artifacts.
- `tmp/validator-bundle-router.json`: `status=ok`, selected validators `78`.
- `tmp/validator-timing-ledger.json`: `status=warning`, normal profile elapsed about `16.7s`, target `10.0s`, failed commands `0`.

This is exactly where Go should help: not by replacing full workflow generators, but by collapsing common structural checks into small compiled validators that fail closed and run cheaply in route/closeout bundles.

## Findings

### Finding 1: Existing Go Layer Is Healthy

The Go validator binaries are current, all Go packages pass tests, and the freshness guard is clean. The current Go layer already covers SQL inventory, schema drift, SQL boundary linting, source-truth parity, consumer authority guardrails, and WF74/WF75 boundary language.

Recommendation: preserve this layer and add to it incrementally.

### Finding 2: Go Should Stay Validator-Only For Now

The route history and demotion readiness gates explicitly retain Python as owner/default and keep Go as validator-only. Python still owns artifact generation, orchestration, workflow semantics, and multi-step repair paths.

Recommendation: no Go primary-route promotion until repeated clean parity runs exist for a specific helper family, with an explicit rollback path.

### Finding 3: SQL Canon Is Ready For Bundle Validation

The canon DB now has stable core field families with 200-row coverage and enough migration/audit/validator metadata to support compact bundle validation. The best next Go validator should check the entire SQL-canon proof posture in one read-only pass.

Recommendation: implement `go-sql-canon-proof-bundle-lint` before any deeper Go migration.

### Finding 4: JSON Proof Sprawl Is The Main Fast-Validation Gap

Important proof packets are green individually, but they have different freshness timestamps, schema styles, warning formats, and authority-boundary fields. That creates a risk where individual validators pass while the proof bundle is stale, mismatched, or semantically inconsistent.

Recommendation: implement a generic JSON proof contract lint that can validate required envelope fields, freshness, status/validation consistency, and forbidden authority flags.

### Finding 5: Consumer Migration Registry Needs A Hard Drift Edge

The consumer inventory reports `585` consumers and `516` backlog rows. The migration registry is now important enough that stale or mismatched registry state could create false confidence in SQL-first migration posture.

Recommendation: implement `go-sql-consumer-registry-drift-lint` to compare the SQLite registry and JSON proof packets.

### Finding 6: Validator Routing Needs A Budget Guard

The normal validator timing profile is warning, while the major route selected 78 validators and saw 570 paths. The router is working, but the validation surface needs a compact guard that detects heavy-route creep, duplicate expensive validators, missing Go freshness checks for Go changes, and stale route outputs.

Recommendation: implement `go-validator-route-budget-lint` and wire it into closeout/changed-file validation once stable.

### Finding 7: Go Is Not Automatically Faster For Raw SQL

Current benchmark evidence says Go in-process removes CLI startup overhead but is not faster than Python `sqlite3` on the measured microbenchmark set. Go CLI is substantially slower for tiny probes because process startup dominates.

Recommendation: use Go where determinism, compiled deployment, fail-closed semantics, and cross-artifact structural validation matter. Do not use "Go is faster" as the reason to port Python producers.

## Recommended New Go Validators

### P1: `go-json-proof-contract-lint`

Purpose:

- Validate JSON proof packet envelope and posture consistency across selected `tmp/*.json` and, later, `state/cron-contracts/*.json`.

Checks:

- Required envelope fields: `status`, `generated_at_utc` or equivalent timestamp, `validation` when applicable.
- Status/validation consistency: `status=ok` cannot hide validation errors.
- Freshness threshold by packet class.
- Forbidden authority flags: no capital approval, no execution approval, no live/paper order approval, no portfolio mutation authority unless exact approved gate is present.
- Warning format sanity: warnings must be explicit, countable, and visible.
- Proof packet references must not claim canon status unless the source is a canonical SQL/owner artifact.

Output:

- `tmp/go-json-proof-contract-lint.json`

Acceptance:

- Fixture tests for missing status, stale timestamp, invalid validation envelope, hidden errors, and forbidden authority flags.
- Integration with `validator_bundle_router.py`.

### P1: `go-sql-canon-proof-bundle-lint`

Purpose:

- Validate the SQL canon and its primary JSON proof packets as one read-only bundle.

Checks:

- `finance-canon.sqlite` exists and opens read-only.
- Core tables/views exist.
- Expected 200-row family coverage for `securities`, `reference_levels`, `evidence_freshness`, `evidence_status`, `tier_routing_state`, `universe_membership`, and `answer_path_scope`.
- `source_lineage` is nonempty and aligns with source-lineage proof expectations.
- `consumer_migration_registry` count matches consumer inventory/registry guard summaries.
- JSON packets agree on status, freshness, and authority boundaries.
- Owner decision packets remain review-only.
- Front-door readiness does not imply owner approval or execution authority.

Output:

- `tmp/go-sql-canon-proof-bundle-lint.json`

Acceptance:

- Fails closed on missing DB, missing proof packet, stale proof packet, row-count mismatch, authority flag mismatch, or validation errors.
- Does not write to SQL or canon state.

### P2: `go-canon-json-field-family-parity`

Purpose:

- Validate SQL field-family coverage against JSON proof summaries.

Checks:

- SQL family row counts match JSON proof claims.
- Active universe count stays aligned at 200 unless an explicit owner-approved universe mutation exists.
- Field families remain classified as SQL-owned, JSON proof/review-only, or owner-note retained.
- Markdown thinning guard is clean or only has non-actionable findings.

Output:

- `tmp/go-canon-json-field-family-parity.json`

Acceptance:

- Fails on field-family mismatch, missing family, stale field-family proof, or owner/canon authority ambiguity.

### P2: `go-sql-consumer-registry-drift-lint`

Purpose:

- Validate SQL-canon consumer migration posture and prevent stale migration confidence.

Checks:

- `consumer_migration_registry` rows match inventory summary.
- P0/P1/high-impact consumers are classified.
- Raw SQL consumers are either migrated, guarded, or explicitly retained with reason.
- Backlog count changes are visible and timestamped.
- Registry sync/guard packets are fresh enough relative to inventory packet.

Output:

- `tmp/go-sql-consumer-registry-drift-lint.json`

Acceptance:

- Fails on unclassified high-impact raw SQL consumers, stale guard packet, missing registry rows, or inconsistent counts.

### P2/P3: `go-validator-route-budget-lint`

Purpose:

- Keep changed-file validation and bundle routing from silently becoming slow or overbroad.

Checks:

- Changed-file router output is fresh.
- Validator bundle output is fresh.
- Go source or binary changes include Go freshness guard.
- Heavy validators are not duplicated unnecessarily.
- Normal timing profile remains within target or emits explicit warning.
- Route selected validators align with changed file families.

Output:

- `tmp/go-validator-route-budget-lint.json`

Acceptance:

- Warning when route is broad but expected.
- Error when route misses required validators, contains duplicate high-cost commands, or hides a failed timing/route proof.

### P3: `go-cron-contract-json-proof-lint`

Purpose:

- Validate cron contract JSON and cron control packet posture without mutating schedules.

Checks:

- Contract command and expected proof outputs align.
- Send/delivery posture is explicit.
- Commands do not imply external/public delivery unless approved.
- Finance cron remains review/proof-only unless exact gate says otherwise.
- Schedule mutation is not inferred from proof packet generation.

Output:

- `tmp/go-cron-contract-json-proof-lint.json`

Acceptance:

- Read-only. No cron schedule/state mutation.
- Fail on command/output mismatch, missing proof target, or authority contradiction.

### P3: `go-finance-canon-authority-event-lint`

Purpose:

- Audit `authority_events`, `audit_events`, `validator_runs`, and `migration_validation_runs` in `finance-canon.sqlite`.

Checks:

- Append-only shape for authority/audit rows.
- No approval/execution flags appear in review-only validation events.
- Validator run timestamps are monotonic enough for audit continuity.
- Migration validation runs do not claim portfolio/account/execution authority.

Output:

- `tmp/go-finance-canon-authority-event-lint.json`

Acceptance:

- Fail on authority boundary contradiction.
- Warning on missing recent validation run where the related proof packet is fresh.

## Do Not Implement In Go Yet

Do not port these classes to Go now:

- Artifact generators.
- Multi-step orchestrators.
- SQL migration phase executors.
- Canon or portfolio apply scripts.
- Markdown thinning writers.
- Approval card generators.
- Cron patch/apply tools.
- Anything that writes SQL/canon/portfolio state.

Examples that should remain Python-owned:

- `finance_sql_primary_migration_plan.py`
- `finance_ticker_card_refresh_gate.py`
- `go_sql_inprocess_driver_pilot_gate.py`
- `sql_canon_migration_phase_executor.py`
- `sql_canon_parallel_phase_executor.py`
- `sql_field_family_canon_promotion_apply.py`
- `sql_canon_consumer_cutover_apply.py`

Reason: those tools carry workflow semantics, write behavior, repair behavior, or owner-gated authority boundaries. Go should verify them, not replace them prematurely.

## Implementation Plan

### Phase 0: Contracts And Fixtures

Goal:

- Define the reusable proof-contract inputs before writing validator logic.

Actions:

- Add a small fixture set under `scripts/go/internal/testdata` or the existing Go testdata pattern.
- Include green and failing JSON packets.
- Include minimal SQLite fixtures for canon family counts and consumer registry drift.
- Document packet classes and freshness thresholds.

Acceptance:

- `go test ./...` passes.
- No workspace SQL/canon files are modified.
- Fixture failures cover stale proof, missing required fields, hidden validation errors, and forbidden authority flags.

### Phase 1: Generic JSON Proof Contract Lint

Goal:

- Make proof packet envelope and authority posture validation fast and reusable.

Actions:

- Implement `cmd/go-json-proof-contract-lint`.
- Add a shared internal package for proof-envelope parsing.
- Emit structured JSON with `status`, `generated_at_utc`, `summary`, `findings`, `warnings`, and `validation`.
- Add router integration only after the binary is stable.

Acceptance:

- Green run against selected current proof packets.
- Failing fixture tests pass.
- `go_binary_freshness_guard.py --write --validate` clean.

### Phase 2: SQL Canon Proof Bundle Lint

Goal:

- Build one hard-edge validator for SQL canon plus the primary JSON proof packets.

Actions:

- Implement `cmd/go-sql-canon-proof-bundle-lint`.
- Use read-only SQLite access only.
- Validate required table/view presence and row-count expectations.
- Validate agreement with selected proof packets.
- Fail closed on missing/stale/mismatched proof.

Acceptance:

- Output `tmp/go-sql-canon-proof-bundle-lint.json`.
- Fails on missing DB, missing packet, row-count mismatch, authority contradiction, or stale proof.
- No SQL writes.

### Phase 3: Field-Family And Consumer Registry Drift

Goal:

- Turn SQL-first migration posture into fast drift checks.

Actions:

- Implement `go-canon-json-field-family-parity`.
- Implement `go-sql-consumer-registry-drift-lint`.
- Share read-only SQL and proof-envelope helpers.

Acceptance:

- Field-family count and ownership checks pass.
- Consumer registry and inventory proof agree or emit explicit drift findings.
- Router integration remains opt-in until two clean real runs.

### Phase 4: Validator Route Budget Lint

Goal:

- Prevent validation route creep from becoming normalized.

Actions:

- Implement `go-validator-route-budget-lint`.
- Read `tmp/changed-file-validator-router.json`, `tmp/validator-bundle-router.json`, and `tmp/validator-timing-ledger.json`.
- Detect missing required validators, duplicate heavy validators, stale route outputs, and timing target breach.

Acceptance:

- Current `normal` profile warning is surfaced explicitly without failing unrelated work.
- Missing Go freshness guard on Go changes is an error.
- Route-budget output is included in closeout only after stable.

### Phase 5: Cron Contract And Authority Event Lints

Goal:

- Extend hard-edge validation to scheduled proof posture and canon authority history.

Actions:

- Implement `go-cron-contract-json-proof-lint`.
- Implement `go-finance-canon-authority-event-lint`.
- Keep both read-only and warning-first until repeated clean runs.

Acceptance:

- No cron schedule mutation.
- No canon mutation.
- Output packets are review-only proof.

## Integration Rules

- New Go validators must be read-only by default.
- Any validator that reads finance SQL must open databases read-only.
- Every command must produce structured JSON proof.
- Every command must have fixture tests.
- Every binary must be covered by `go_binary_freshness_guard.py`.
- Router integration must start as advisory before becoming required.
- Python remains the workflow owner unless a separate owner-approved route migration passes repeated parity and rollback gates.

## Stop Lines

Stop and escalate before any of the following:

- SQL/canon writes.
- Portfolio or canon-note mutation.
- Cron schedule mutation.
- Config/auth/runtime/channel/credential mutation.
- Paper/live/account/brokerage action.
- Owner approval inference.
- Python retirement or Go default-route promotion without explicit approval and repeated parity proof.

## Validation Commands Run

- `go test ./...` from `scripts/go`: passed.
- `python scripts\go_binary_freshness_guard.py --write --validate`: passed.
- `python scripts\validator_bundle_router.py --write --validate`: passed.
- `python scripts\changed_file_validator_router.py --write --validate`: passed.
- `python scripts\validator_timing_ledger.py --profile normal --write --validate`: completed with warning because elapsed time exceeded the normal target; no command failures.

## Final Recommendation

Approve a narrow implementation lane for Phase 0 through Phase 2 only:

1. Build `go-json-proof-contract-lint`.
2. Build `go-sql-canon-proof-bundle-lint`.
3. Add tests, freshness guard coverage, and advisory router integration.

After two clean advisory runs, continue with field-family parity and consumer-registry drift lints. Keep route-budget lint as the next validator-hardening step if timing warnings continue.
