# Go Validator Layer

This directory holds small, deterministic Go validators for Veritas workflow proof.

Go is the hard validator edge. Python remains the workflow spine that creates artifacts, PM state, SQL caches, and proof packets. TypeScript/Node remains the local cockpit and product/control-plane shell.

## Current Commands

Run all Go tests:

```powershell
cd scripts\go
go test .\...
```

Build the current command set into local Windows executables:

```powershell
New-Item -ItemType Directory -Force -Path scripts\go\bin | Out-Null
Push-Location scripts\go
foreach ($cmd in Get-ChildItem -Path cmd -Directory | Sort-Object Name) {
  go build -o (Join-Path "bin" ($cmd.Name + ".exe")) (".\cmd\" + $cmd.Name)
  if ($LASTEXITCODE -ne 0) { Pop-Location; exit $LASTEXITCODE }
}
Pop-Location
```

The harness/runtime scorecards use the compiled WF78 500-gate executable:

```powershell
scripts\go\bin\go-sql-500-expansion-design-gate.exe --root C:\Users\Veritas\.openclaw\workspace --out C:\Users\Veritas\.openclaw\workspace\tmp\go-sql-500-ticker-expansion-design-gate.json
```

Refresh the WF75 / SMB boundary lint proof:

```powershell
cd scripts\go
go run .\cmd\wf75-smb-boundary-lint --root ..\.. --out ..\..\tmp\wf75-smb-boundary-lint.json
```

Refresh the finance / SQL boundary lint proof:

```powershell
cd scripts\go
go run .\cmd\finance-sql-boundary-lint --root ..\.. --out ..\..\tmp\finance-sql-boundary-lint.json
go run .\cmd\python-sql-contract-lint --root ..\.. --out ..\..\tmp\python-sql-contract-lint.json
go run .\cmd\sql-schema-drift-lint --root ..\.. --out ..\..\tmp\sql-schema-drift-lint.json
go run .\cmd\sql-proof-probe --root ..\.. --out ..\..\tmp\sql-proof-probe.json
go build -o ..\..\tmp\go-binaries\go-sql-latency-probe.exe .\cmd\go-sql-latency-probe
go build -o ..\..\tmp\go-binaries\go-sql-inventory-helper.exe .\cmd\go-sql-inventory-helper
go build -o ..\..\tmp\go-binaries\go-finance-human-notes-sql-check.exe .\cmd\go-finance-human-notes-sql-check
..\..\tmp\go-binaries\go-sql-latency-probe.exe --root ..\.. --iterations 5 --driver inprocess --out ..\..\tmp\go-sql-latency-probe.json
..\..\tmp\go-binaries\go-sql-inventory-helper.exe --root ..\.. --driver inprocess --out ..\..\tmp\go-sql-inventory-helper.json
go run .\cmd\go-sql-latency-probe --root ..\.. --iterations 5 --driver inprocess --out ..\..\tmp\go-sql-latency-probe-inprocess.json
go run .\cmd\go-sql-inventory-helper --root ..\.. --driver inprocess --out ..\..\tmp\go-sql-inventory-helper-inprocess.json
go run .\cmd\go-sql-source-truth-manifest --root ..\.. --out ..\..\tmp\go-sql-source-truth-authority-manifest.json
go run .\cmd\go-finance-data-coverage-probe --root ..\.. --out ..\..\tmp\go-finance-data-coverage-probe.json
..\..\tmp\go-binaries\go-finance-human-notes-sql-check.exe --root ..\.. --driver inprocess --out ..\..\tmp\go-finance-human-notes-sql-check.json
go run .\cmd\go-finance-human-notes-sql-check --root ..\.. --driver inprocess --out ..\..\tmp\go-finance-human-notes-sql-check-inprocess.json
go run .\cmd\go-finance-universe-validation-probe --root ..\.. --out ..\..\tmp\go-finance-universe-validation-probe.json
go run .\cmd\go-wf78-sql-phase2-readiness-probe --root ..\.. --out ..\..\tmp\go-wf78-sql-phase2-readiness-probe.json
go run .\cmd\go-sql-consumer-authority-guard --root ..\.. --out ..\..\tmp\go-sql-consumer-authority-guard.json
cd ..\..
python scripts\python_go_sql_parity_check.py --write --validate
python scripts\python_go_sql_migration_candidates.py --write --validate
python scripts\python_go_source_truth_manifest_parity.py --write --validate
python scripts\python_go_source_truth_parity_validator_parity.py --write --validate
python scripts\python_go_sql_500_expansion_gate_parity.py --write --validate
python scripts\python_go_finance_data_coverage_probe_parity.py --write --validate
python scripts\python_go_finance_human_notes_sql_check_parity.py --write --validate
python scripts\python_go_finance_universe_validation_parity.py --write --validate
python scripts\python_go_wf78_sql_phase2_readiness_parity.py --write --validate
python scripts\python_go_durable_output_parity_repeated_gate.py --write --validate --cycles 3
python scripts\python_go_sql_consumer_authority_guard_parity.py --write --validate
python scripts\python_go_sql_consumer_authority_guard_fixture_parity.py --write --validate
python scripts\python_go_sql_consumer_authority_dashboard_ab.py --write --validate --cycles 3
python scripts\python_go_sql_consumer_authority_demotion_dry_run.py --write --validate
python scripts\python_go_sql_consumer_authority_controlled_router.py --write --validate
python scripts\python_go_sql_helper_demotion_readiness_gate.py --write --validate
python scripts\python_go_sql_helper_demotion_queue.py --write --validate
python scripts\python_go_sql_helper_contract_gate.py --write --validate
python scripts\python_go_sql_helper_controlled_router_batch.py --write --validate
python scripts\python_go_sql_helper_go_primary_history_gate.py --write --validate --cycles 3
python scripts\python_go_sql_helper_default_route_promotion.py --write --validate
python scripts\python_go_sql_helper_default_route_history_gate.py --write --write-history --validate --cycles 5
python scripts\python_go_sql_helper_fallback_removal_readiness_gate.py --write --validate
python scripts\python_go_sql_helper_retirement_gate.py --write --validate
python scripts\go_sql_inprocess_driver_pilot_gate.py --write --write-md --validate --run-probes --build-binaries --binary-route-active
```

Use the full `go_sql_inprocess_driver_pilot_gate.py --run-probes --build-binaries`
form only when intentionally refreshing the in-process SQLite driver proof. Normal
harness and quick runtime closeout paths validate the existing
`tmp/go-sql-inprocess-driver-pilot-gate.json` artifact instead of rerunning the
full probe/build matrix.

## Validators

## Shared Toolkit

The Go layer now has a small reusable toolkit instead of only one-off commands:

- `internal/reporting`: UTC timestamps, shared `ok` / `warning` / `blocked` status logic, common read-only authority boundary flags, finding summaries, and JSON report writing.
- `internal/sqlutil`: read-only `sqlite3` CLI adapter and opt-in `modernc.org/sqlite` in-process adapter for scalar queries, JSON row queries, text row counts, table row counts, identifier quoting, and consistent command errors. Unknown driver names fail closed instead of silently falling back.

This is the foundation for selected Python SQL helper migration. Keep it small: shared helpers should remove duplication from validators and read-only probes, not become a second workflow engine.

The read-only Go SQL helpers with `--driver cli|inprocess` support are:

- default compiled-binary route: `go-sql-inventory-helper`, `go-sql-latency-probe`, `go-finance-human-notes-sql-check`, `go-finance-data-coverage-probe`, `go-source-truth-parity-validator`
- probe-only in-process comparison route: `go-sql-source-truth-manifest`, `go-sql-500-expansion-design-gate`, `go-sql-consumer-authority-guard`, `sql-schema-drift-lint`, `sql-proof-probe`

The shared Python route registry is `scripts/go_sql_helper_route_registry.py`. Only the five default-route helpers are approved for compiled-binary routing under `tmp/go-binaries/`; the five probe-only helpers prove in-process driver parity without changing their default route.

### `wf74-boundary-lint`

Existing WF74 boundary lint surface.

### `wf75-smb-boundary-lint`

Scans the SMB Workflow Clarity artifacts for forbidden authority drift:

- real customer data or retention
- credential/API key access
- outbound calls, texts, emails, or social messages
- customer-system implementation or writeback
- public/external launch readiness
- guaranteed ROI, revenue, sales, leads, payback, or return claims
- legal, compliance, or security readiness claims
- inferred or granted owner approval

The report is written to `tmp/wf75-smb-boundary-lint.json` and is consumed by:

- `scripts/veritas_harness_scorecard.py`
- `scripts/pm_program_state.py`
- `state/pm-cockpit-source-registry.json`
- the local TypeScript/Node PM cockpit source readiness check

### `finance-sql-boundary-lint`

Scans finance/SQL proof artifacts and derived SQLite surfaces for forbidden authority drift:

- SQL-as-canon or SQL-as-approval language
- proposal apply authority
- owner approval inference
- paper/live trading or brokerage/account action authority
- customer/external output authority
- finance SQL row-count and integrity regressions

The report is written to `tmp/finance-sql-boundary-lint.json` and is consumed by:

- `scripts/veritas_harness_scorecard.py`
- `scripts/pm_program_state.py`
- `scripts/runtime_performance_scorecard.py`
- `state/pm-cockpit-source-registry.json`
- the local TypeScript/Node PM cockpit source readiness check

### `python-sql-contract-lint`

Scans Python scripts that touch finance/SQL/canon/portfolio/promotion surfaces for migration readiness and authority contract drift:

- SQL-touching scripts should expose validation and boundary language
- durable finance/portfolio write paths should mention approval and backup/rollback gates
- runtime code should not imply SQL-as-canon, approval inference, customer/external delivery, or paper/live/account authority

The report is written to `tmp/python-sql-contract-lint.json`.

### `sql-schema-drift-lint`

Checks the live SQLite proof/control surfaces for schema and row-count drift:

- `state/finance/finance-canon.sqlite`
- `tmp/finance-intelligence-state.sqlite`
- `tmp/veritas-artifact-index.sqlite`
- `tmp/veritas-canon-cache.sqlite`
- `tmp/json-sql-promotion-index.sqlite`
- `tmp/pm-program-state.sqlite`
- `tmp/generic-service-state.sqlite`
- `tmp/wf75-service-state.sqlite`

The report is written to `tmp/sql-schema-drift-lint.json`.

### `sql-proof-probe`

Aggregates the SQL schema drift proof into a migration-grade read-only SQL proof surface:

- per-DB status over core SQLite proof/control surfaces
- total checks, criticals, warnings, blocked DBs, and warning DBs
- explicit migration posture that keeps Python as generator/orchestrator and Go as read-only proof edge
- embedded `sql-schema-drift-lint` proof for traceability

The report is written to `tmp/sql-proof-probe.json` and is consumed by:

- `scripts/runtime_performance_scorecard.py`
- `scripts/veritas_harness_scorecard.py`
- `scripts/pm_program_state.py`
- `state/pm-cockpit-source-registry.json`

### `go-sql-latency-probe`

Runs the same fixed, allowlisted SQL probe family as the Python latency benchmark through the local `sqlite3` CLI:

- workspace retrieval FTS/freshness probes
- finance intelligence joins/scans
- artifact index proof scans
- bounded canon-cache scans
- paper-position visibility scan

The approved bounded default route writes `tmp/go-sql-latency-probe.json` through the compiled binary at `tmp/go-binaries/go-sql-latency-probe.exe` with `--driver inprocess`. The comparison in-process report is written to `tmp/go-sql-latency-probe-inprocess.json`; the CLI-backed comparison artifact is written to `tmp/go-sql-latency-probe-cli-comparison.json` by the pilot gate.

This remains a read-only validation route. It proves query availability, row shape, authority boundaries, and runtime direction for the selected helper only; Python fallback remains retained and no SQL write/import, canon/portfolio mutation, customer/external delivery, or paper/live/account action authority is added.

### `go-sql-inventory-helper`

Runs fixed read-only inventory over the core SQLite control/proof surfaces:

- table and view inventory
- row-count summaries
- expected-table presence checks
- SQLite `integrity_check`
- explicit no-authority boundary flags

The approved bounded default route writes `tmp/go-sql-inventory-helper.json` through the compiled binary at `tmp/go-binaries/go-sql-inventory-helper.exe` with `--driver inprocess`. The comparison in-process report is written to `tmp/go-sql-inventory-helper-inprocess.json`; the CLI-backed comparison artifact is written to `tmp/go-sql-inventory-helper-cli-comparison.json` by the pilot gate. The default report is consumed by:

- `scripts/runtime_performance_scorecard.py`
- `scripts/veritas_harness_scorecard.py`
- `scripts/pm_program_state.py`
- `state/pm-cockpit-source-registry.json`

This is the first reusable Go SQL helper surface for selected Python-to-Go migration. It remains read-only; the selected default runtime/harness route now uses the compiled binary plus in-process SQLite driver after Randall's bounded approval.

Implementation note: this helper uses `internal/reporting` and `internal/sqlutil`; the same utility package now also backs the Go SQL latency probe, and the finance/schema validators use the shared reporting summary/status path. The route remains gated by `scripts/go_sql_inprocess_driver_pilot_gate.py --binary-route-active`, which must stay `status=ok` with read-only enforcement, Python fallback retained, runtime/PM/harness stability, and rollback instructions present.

### `python_go_sql_parity_check.py`

Compares the existing Python and Go SQL helper proof artifacts before any helper is retired or demoted:

- Python `tmp/sql-latency-benchmark-current.json`
- Go `tmp/go-sql-latency-probe.json`
- Go `tmp/go-sql-inventory-helper.json`

The report is written to `tmp/python-go-sql-parity-check.json` and is consumed by:

- `scripts/runtime_performance_scorecard.py`
- `scripts/veritas_harness_scorecard.py`
- `scripts/pm_program_state.py`
- `state/pm-cockpit-source-registry.json`

It checks benchmark coverage, status parity, row-count parity, inventory health, and authority boundaries. It does not compare timing values as pass/fail because the current Go probe shells out to `sqlite3` and includes process startup overhead.

### `python_go_sql_migration_candidates.py`

Ranks Python SQL helpers for selective Go migration using the cleaned Python SQL contract lint and the Python-Go parity gate.

The report is written to `tmp/python-go-sql-migration-candidates.json` and is consumed by:

- `scripts/runtime_performance_scorecard.py`
- `scripts/veritas_harness_scorecard.py`
- `scripts/pm_program_state.py`
- `state/pm-cockpit-source-registry.json`

It separates low-risk read-only Go spike candidates from helpers that must remain Python-governed, such as canon/portfolio/apply/approval/orchestration/paper surfaces.

### `go-sql-source-truth-manifest`

Builds a Go companion for `scripts/sql_source_truth_authority_manifest.py`:

- fixed SQL surface authority classes
- canonical owner-note hashes
- SQLite integrity/object/table-count proof
- explicit false authority flags
- source-of-truth promotion stop lines

The report is written to `tmp/go-sql-source-truth-authority-manifest.json`.

### `python_go_source_truth_manifest_parity.py`

Compares the Python and Go source-truth authority manifests before any Python helper is demoted:

- status and summary posture
- database surface names, integrity, objects, and table counts
- canonical owner-note hashes
- false authority flags

The report is written to `tmp/python-go-source-truth-manifest-parity.json` and is consumed by runtime, harness, PM, and cockpit proof surfaces.

### `go-source-truth-parity-validator`

Go companion for `scripts/sql_source_truth_parity_validator.py`.

It parses the Execution Board Markdown entry/stop reference table, reads the bounded read-only SQL mirrors, and writes `tmp/go-source-truth-parity-validation.json`. It checks only the approved entry/stop reference metadata field family. It does not promote SQL to source of truth, mutate SQL or Markdown, migrate consumers, infer approval, or grant recommendation/deployment/execution/customer authority.

### `python_go_source_truth_parity_validator_parity.py`

Compares the Python and Go source-truth parity validator outputs.

The report is written to `tmp/python-go-source-truth-parity-validator-parity.json` and checks summary parity, source note hash parity, false authority flags, missing/extra ticker sets, mismatch sets, and per-ticker comparison checks.

### `go-sql-500-expansion-design-gate`

Go companion for `scripts/sql_500_ticker_expansion_design_gate.py`.

It reads `tmp/finance-intelligence-state.sqlite` in read-only mode and writes `tmp/go-sql-500-ticker-expansion-design-gate.json`. It checks the production 42 lock, isolated 25-name pilot candidate set, DB integrity, and zero pilot/production overlap. It does not import tickers, overwrite production answer paths, expand SQL-canon, mutate canon/portfolio state, infer approval, or grant paper/live/account authority.

Current harness/runtime route uses the compiled executable at `scripts/go/bin/go-sql-500-expansion-design-gate.exe`, not `go run`, and expects status `ready_for_source_open_cleanup` while the source-open cleanup queue remains blocked.

### `python_go_sql_500_expansion_gate_parity.py`

Compares the Python and Go SQL 500 expansion design gate outputs.

The report is written to `tmp/python-go-sql-500-expansion-gate-parity.json`.

### `go-finance-data-coverage-probe`

Go fixture probe for `scripts/finance_data_coverage.py`.

It reads `tmp/finance-data-coverage-current.json`, validates the compact coverage summary, source-artifact key set, and authority boundary, then writes `tmp/go-finance-data-coverage-probe.json`. Python remains the coverage registry generator because it owns the detailed router/ticker/family output contract.

### `python_go_finance_data_coverage_probe_parity.py`

Compares the Python finance data coverage registry against the Go fixture probe summary and authority boundary.

The report is written to `tmp/python-go-finance-data-coverage-probe-parity.json`.

### `go-finance-human-notes-sql-check`

Go companion for the embedded SQL-canon check inside `scripts/finance_human_notes_thinning_candidates.py`.

It reads `state/finance/finance-canon.sqlite` in read-only mode, checks integrity, and verifies the expected `100` active / `42` answer-path / `58` review-monitor counts. The approved bounded default route writes `tmp/go-finance-human-notes-sql-check.json` through the compiled binary at `tmp/go-binaries/go-finance-human-notes-sql-check.exe` with `--driver inprocess`; the pilot gate keeps the CLI-backed comparison artifact at `tmp/go-finance-human-notes-sql-check-cli-comparison.json` and the in-process companion artifact at `tmp/go-finance-human-notes-sql-check-inprocess.json`. Python remains the owner-review packet generator and no archive/delete authority is added.

### `python_go_finance_human_notes_sql_check_parity.py`

Compares the Python finance human-notes thinning packet's `sql_canon_check` against the Go SQL check.

The report is written to `tmp/python-go-finance-human-notes-sql-check-parity.json`.

### `go-finance-universe-validation-probe`

Go durable-output probe for `scripts/finance_universe_validator.py`.

It reads `tmp/wf78-finance-universe-validation.json` and `data/finance/universe-v1.json`, then verifies the durable shape, status vocabulary, summary fields, validation fields, authority boundary, active row counts, production/review universe state, source-open requirements, and forbidden authority flags. The report is written to `tmp/go-finance-universe-validation-probe.json`; Python remains the durable universe writer.

### `python_go_finance_universe_validation_parity.py`

Compares the Python finance universe validation artifact against the Go durable-output probe.

The report is written to `tmp/python-go-finance-universe-validation-parity.json`.

### `go-wf78-sql-phase2-readiness-probe`

Go durable-output probe for `scripts/wf78_sql_phase2_readiness.py`.

It reads `tmp/wf78-sql-phase2-readiness.json`, then verifies the durable shape, ready status vocabulary, workflow/phase fields, surface status map, blocked-surface semantics, row-count semantics, phase-2 readiness conditions, and authority boundary. The report is written to `tmp/go-wf78-sql-phase2-readiness-probe.json`; Python remains the readiness writer.

### `python_go_wf78_sql_phase2_readiness_parity.py`

Compares the Python WF78 SQL Phase 2 readiness artifact against the Go durable-output probe.

The report is written to `tmp/python-go-wf78-sql-phase2-readiness-parity.json`.

### `python_go_durable_output_parity_repeated_gate.py`

Runs the finance universe validation and WF78 readiness durable-output parity gates across repeated clean cycles.

The report is written to `tmp/python-go-durable-output-parity-repeated-gate.json`. It requires stable fingerprints across cycles and proves semantic/shape parity without changing production routing or retiring Python.

### `go-sql-consumer-authority-guard`

Go read-only companion for `scripts/sql_consumer_authority_guard.py`.

It reads `tmp/veritas-artifact-index.sqlite` and `tmp/veritas-canon-cache.sqlite` in read-only mode, auto-loads the WF72 A2 fallback fixture from `tmp/wf72-a2-consumer-authority-fallback-values.json` when present, then checks forbidden authority flags, proposal apply flags, cache integrity, expected key scope, fallback-required posture, stale/unsafe source rows, and forbidden field-family drift. Current A2 live state is expected to be `ok` only when the 265-key fallback fixture is present and parity-clean; deleting or corrupting the fixture should fail closed. Python fallback remains retained; this route does not authorize SQL-first consumer promotion or Python retirement.

### `python_go_sql_consumer_authority_guard_parity.py`

Compares Python and Go SQL consumer authority guard output for the current fallback-backed A2 route.

The report is written to `tmp/python-go-sql-consumer-authority-guard-parity.json`.

### `python_go_sql_consumer_authority_guard_fixture_parity.py`

Builds a synthetic clean fixture with exactly the approved consumer keys, matching fallback values, valid source hashes, and closed authority flags, then compares Python and Go read-allowed behavior.

The report is written to `tmp/python-go-sql-consumer-authority-guard-fixture-parity.json`. This is a demotion-readiness signal only; it does not demote the Python owner by itself.

### `python_go_sql_consumer_authority_dashboard_ab.py`

Compares the dashboard's Python-owned SQL consumer hook against the Go authority guard across repeated live fallback-backed, clean fixture/fallback-present, missing fallback, and stale/unsafe source modes.

The report is written to `tmp/python-go-sql-consumer-authority-dashboard-ab.json`. This is the first consumer-level A/B demotion-readiness signal; it does not change dashboard behavior or demote Python by itself.

### `python_go_sql_consumer_authority_demotion_dry_run.py`

Dry-runs a controlled Go-first/Python-fallback mode for `scripts/sql_consumer_authority_guard.py`.

The report is written to `tmp/python-go-sql-consumer-authority-demotion-dry-run.json`. It selects Go primary only for the clean fixture allow case and proves Python fallback remains blocked for missing fallback, stale/unsafe source, and live no-fallback cases. It does not change production routing or retire Python.

### `python_go_sql_consumer_authority_controlled_router.py`

Defines the explicit controlled-router contract for the first demotion candidate.

The report is written to `tmp/python-go-sql-consumer-authority-controlled-router.json`. The default route remains Python-owned; the Go-first/Python-fallback mode is proven only as a controlled proof path. It does not change dashboard routing or retire Python.

### `python_go_sql_helper_demotion_readiness_gate.py`

Checks the full Python SQL helper migration queue before any helper demotion.

The report is written to `tmp/python-go-sql-helper-demotion-readiness-gate.json`. It requires existing Go-covered helpers to have proof artifacts, durable-output helpers to stay Python-owned until semantic/shape parity gates exist, contract-first candidates to keep fixture contracts before replacement, and all helpers to have `retire_python_now=false`.

### `python_go_sql_helper_demotion_queue.py`

Records controlled demotion state and prepares the next candidates.

The report is written to `tmp/python-go-sql-helper-demotion-queue.json`. The first controlled demotion is `scripts/sql_consumer_authority_guard.py` as Go-first/Python-fallback eligible, not retired. The rest of the queue remains contract-gated.

### `python_go_sql_helper_contract_gate.py`

Captures fixture contracts, expected output shapes, semantic/shape parity state, and downstream consumer stability for the remaining demotion candidates.

The report is written to `tmp/python-go-sql-helper-contract-gate.json`. It records which queued helpers are eligible for controlled-router design, which durable-output helpers still need Go semantic parity, and which orchestration-adjacent helpers must keep Python as owner while Go extracts only read-only probes. It does not execute candidate helpers, switch routing, or retire Python.

### `python_go_sql_helper_controlled_router_batch.py`

Records controlled Go-first/Python-fallback demotion for every contract-gate-eligible helper.

The report is written to `tmp/python-go-sql-helper-controlled-router-batch.json`. It moves only parity-green, non-orchestration helpers into controlled demotion state. Default routing remains unchanged, Python fallback remains retained, and `retire_python_now` remains false.

### `python_go_sql_helper_go_primary_history_gate.py`

Runs repeated clean-cycle history checks over the controlled router batch.

The report is written to `tmp/python-go-sql-helper-go-primary-history-gate.json`. It requires stable route fingerprints, green parity, stable runtime/harness/PM consumer proof, unchanged production routing, retained Python fallback, and `retire_python_now=false` across cycles.

### `python_go_sql_helper_default_route_promotion.py`

Records Randall-approved rollback to Python owner/default routing for the already controlled-demoted helper list in `tmp/python-go-sql-helper-retirement-gate.json`.

The report is written to `tmp/python-go-sql-helper-default-route-promotion.json`. It now records `python_owner_only` as the default route and keeps Go as validator-only proof. It denies Python deletion, SQL writes/imports, canon/portfolio mutation, customer/external delivery, config/auth/runtime mutation, paper/live/account action, and inferred approval.

### `python_go_sql_helper_default_route_history_gate.py`

Collects repeated Python-owner/default route history after the approved rollback.

The report is written to `tmp/python-go-sql-helper-default-route-history-gate.json`. It requires stable route fingerprints across cycles, default `python_owner_only`, Go validator-only posture, Python fallback retained, `retire_python_now=false`, and `python_file_delete_allowed=false`.

### `python_go_sql_helper_fallback_removal_readiness_gate.py`

Builds report-only fallback-removal readiness proof for the promoted helper list.

The report is written to `tmp/python-go-sql-helper-fallback-removal-readiness-gate.json`. With Python back as owner/default, fallback removal is not applicable; the gate stays `status=ok`, records the inactive migration state, keeps Python fallback active, and requires a separate exact owner approval before any future removal attempt.

### `python_go_sql_helper_retirement_gate.py`

Gates full Python helper retirement after controlled demotion.

The report is written to `tmp/python-go-sql-helper-retirement-gate.json`. It validates the safe blocked state: Go remains a validator/proof edge, Python deletion remains disallowed, and Python stays the owner/default unless a future exact approval restarts a separate migration.

## Expansion Rules

- Prefer Go for fast read-only validators over JSON/Markdown/proof artifacts.
- Keep Go CLIs deterministic, dependency-light, and fixture-tested.
- Reuse `internal/reporting` and `internal/sqlutil` before adding per-command report or SQLite wrappers.
- Do not use Go to generate canon, mutate SQL, advance PM state, change cron schedules, touch customer systems, or replace Python workflow generators.
- Every new Go validator should have tests, a JSON proof artifact when useful, and a Python/PM/cockpit bridge before being treated as operationally integrated.

## Near-Term Roadmap

1. WF75 / SMB boundary lint: complete.
2. Finance / SQL boundary lint: complete.
3. Python / SQL contract lint: complete.
4. SQL schema drift lint: complete.
5. SQL proof probe: complete.
6. Go SQL latency probe: complete as a read-only parity surface beside the Python benchmark.
7. Go SQL inventory helper: complete as the first reusable read-only SQL helper migration target.
8. Python-vs-Go SQL parity gate: complete as the first retirement/demotion gate for selected read-only Python SQL helper surfaces.
9. Python-Go SQL migration candidate registry: complete as the ranked next-port queue for selected read-only helper surfaces.
10. Go source-truth authority manifest companion and Python-Go parity gate: complete as the first Batch 2 report-generator fixture parity target.
11. Go source-truth parity validator companion and Python-Go parity gate: complete as the first actual Markdown-to-SQL parity validator port.
12. Go SQL 500 expansion design gate companion and Python-Go parity gate: complete as the next compact report-generator parity target.
13. Go finance data coverage fixture probe and Python-Go parity gate: complete as a contract-first coverage registry migration target.
14. Go finance human-notes SQL-canon check and Python-Go parity gate: complete as a narrow SQL helper extraction from the owner-review packet.
15. Go SQL consumer authority guard fail-closed companion and Python-Go parity gate: complete for no-fallback authority denial.
16. SQL consumer authority guard fallback-present fixture parity: complete as the first demotion-readiness fixture.
17. Repeated dashboard A/B gate: complete across clean fixture, live fail-closed, missing fallback, and stale/unsafe source cases.
18. Go-first/Python-fallback demotion dry run: complete for `sql_consumer_authority_guard.py`; production routing unchanged.
19. Controlled router contract proof: complete for `sql_consumer_authority_guard.py`; default remains Python-owned and Python fallback remains retained.
20. Helper demotion readiness gate: complete for durable-output parity and contract-first replacement requirements.
21. Helper demotion queue: complete; first controlled demotion recorded for `sql_consumer_authority_guard.py`, with remaining candidates contract-gated.
22. Durable-output parity probes: complete for finance universe validation and WF78 SQL Phase 2 readiness, including repeated stable-fingerprint parity gates.
23. Remaining helper contract gate: complete; 11 fixture contracts captured, 8 semantic/shape parity gates green, 0 durable-output candidates waiting on Go parity, 8 controlled-router-design eligible, and 2 orchestration helpers keep Python ownership.
24. Controlled-router batch: complete for 8 parity-green eligible helpers as Go-first/Python-fallback recorded state; default routing unchanged and Python not retired.
25. Repeated Go-primary history gate: historical proof complete for controlled routes with stable fingerprints, fallback retained, and no default routing change.
26. Python owner/default rollback: complete for the approved controlled-demoted helper set after the 2026-06-08 benchmark showed no material Go speed advantage for this path. Go remains validator-only and Python fallback is retained.
27. Python-owner route history gate: complete for repeated default-route history, with stable fingerprints and Python deletion denied.
28. Python helper retirement gate: complete as a blocker proof; full Python retirement/deletion remains disallowed while Python is owner/default.
29. PM queue and handoff lint: catch stale, unsafe, or authority-widening PM continuation packets.
30. Cron payload and automation-authority lint: catch schedule payload drift, prompt bloat, delivery mismatch, and unsafe authority language.
31. Shared validator suite: consolidate common report schema, file loading, severity handling, and test fixtures without turning Go into a second operating system.

## Boundary

Go validators are read-only proof tools. They do not grant customer authority, SQL-as-canon authority, canon/portfolio mutation, paper/live/account action, external delivery, config/auth/runtime mutation, or owner approval.
