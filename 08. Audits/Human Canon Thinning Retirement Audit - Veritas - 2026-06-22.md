# Human Canon Thinning Retirement Audit - Veritas - 2026-06-22

## Scope

Audit the thinned human finance canon notes and identify validators, scripts, proof checks, and cron-facing surfaces that should be retained, narrowed to on-demand, or queued as retirement/archive candidates because structured ticker data now belongs in SQL/JSON proof instead of hand-maintained Markdown.

## Authority Boundary

This audit is review-only. It does not authorize archive, delete, move, cron mutation, SQL mutation, portfolio/canon mutation, paper/live execution, brokerage/account action, capital deployment, or owner approval inference.

## Sources Inspected

- `06. Playbooks/Startup Truth Index.md`
- `06. Playbooks/Notes Layer Governance Protocol.md`
- `06. Playbooks/SQL Canon Full Migration Execution Plan.md`
- `06. Playbooks/Workflow 84 - Finance SQL Canon Data Plane.md`
- `scripts/md_finance_structured_drift_lint.py`
- `scripts/finance_sql_markdown_field_ownership.py`
- `scripts/validate_canonical_ownership.py`
- `scripts/ticker_answer_packet.py`
- `scripts/ticker_answer_packet_retirement_plan.py`
- `scripts/veritas_question_router.py`
- `scripts/today_card_generator.py`
- `scripts/veritas_technical_pass_validate.py`
- `scripts/veritas_harness_scorecard.py`
- `scripts/runtime_performance_scorecard.py`
- `scripts/changed_file_validator_router.py`
- `scripts/validator_bundle_router.py`
- `scripts/workflow_routing_index.py`
- `tmp/md-finance-structured-drift-lint.json`
- `tmp/finance-sql-markdown-field-ownership.json`
- `tmp/canonical-ownership-validation.json`
- `tmp/canonical-finance-data-plane-retirement-readiness.json`
- `tmp/ticker-answer-packet-retirement-approval-plan-20260609.json`
- `tmp/go-source-truth-parity-validation.json`
- `tmp/go-finance-human-notes-sql-check.json`
- `tmp/python-go-finance-human-notes-sql-check-parity.json`
- `tmp/python-go-sql-helper-retirement-gate.json`

## Executive Conclusion

The thinned human canon notes are not the problem. The active thinning proof says they are behaving correctly:

- `tmp/md-finance-structured-drift-lint.json` is `status=ok` with `requires_action_count=0`.
- `tmp/finance-sql-markdown-field-ownership.json` is `status=ok`; it classifies 24 reconciliation rows and explicitly downgrades 19 cross-class blockers as `not_a_sql_markdown_blocker`.
- `tmp/canonical-ownership-validation.json` is `status=ok`; the SQL-first thin Execution Board and Coverage/Watchlist contracts are accepted and ticker/universe rows are owned by SQL/JSON proof.

The waste is in three places:

1. Legacy compatibility surfaces still talk like human Markdown is structured canon.
2. Runtime/performance harnesses still spend cycles on human-note SQL/Go parity checks that are not default-route promotion gates.
3. Some validators are mixed-purpose and should be split or mode-gated so routine validation does not check for structured rows that the thinned notes are no longer supposed to contain.

## Findings

### P1-1. Do Not Retire the Thinning Guards

Evidence:
- `scripts/md_finance_structured_drift_lint.py` is explicitly report-only and flags structured finance facts duplicated in human Markdown.
- `tmp/md-finance-structured-drift-lint.json` reports `status=ok`, 17 findings, and `requires_action_count=0`; all current findings are generated links or historical/audit context.
- `scripts/finance_sql_markdown_field_ownership.py` classifies field families and prevents SQL-proof-only fields from becoming false human-note blockers.
- `tmp/finance-sql-markdown-field-ownership.json` reports 24 rows, all `sql_proof_only`, with 19 cross-class blockers ignored.

Impact:
These scripts are not waste. They are the controls that keep the thinned notes from regrowing old structured tables.

Recommendation:
Keep both validators, but route them only when human finance Markdown, SQL/Markdown reconciliation, or field-family ownership files change, plus weekly/closeout audit lanes.

Acceptance proof:
`md_finance_structured_drift_lint.py --validate --json` remains `ok`; `finance_sql_markdown_field_ownership.py --validate --json` remains `ok`; changed-file routing selects them only for relevant note/SQL-field-family changes.

### P1-2. Runtime Performance Scorecard Is Running Human-Note Checks Too Broadly

Evidence:
- `scripts/runtime_performance_scorecard.py` runs `go_finance_human_notes_sql_check_smoke`, `go_source_truth_parity_validator_smoke`, `python_sql_source_truth_parity_validator`, `go_source_truth_parity_validator`, `python_go_source_truth_parity_validator_parity`, `python_finance_human_notes_thinning_candidates`, and `python_go_finance_human_notes_sql_check_parity`.
- `tmp/python-go-sql-helper-retirement-gate.json` says `retirement_ready=false`, `retire_python_now_count=0`, `python_fallback_retained=true`, and `retirement_gate_signal=dormant_python_owner_default_do_not_delete`.
- `tmp/go-finance-human-notes-sql-check.json` is only a Go parity probe for SQL-canon count checks.

Impact:
The system spends runtime validating migration/proof surfaces that are not active default-route promotion gates. This is the clearest resource-waste candidate.

Recommendation:
Move human-note SQL/Go checks out of default runtime performance scoring and into a targeted `--migration-human-notes` or `--full-sql-migration` mode. Keep lightweight status fields that read existing artifacts without rerunning them.

Acceptance proof:
Default runtime scorecard omits those commands; targeted migration mode still runs them; `tmp/python-go-sql-helper-retirement-gate.json` remains the retirement authority and still blocks deletion/retirement.

### P1-3. `ticker_answer_packet.py` Is Legacy Compatibility, Not Current Structured Canon

Evidence:
- `scripts/ticker_answer_packet.py` states: "Owner markdown (Execution Board, Coverage and Watchlist) stays canon."
- It parses thesis prose from `04. Research/Coverage and Watchlist.md` and marks parsed thesis fields as `canon_owner_source`.
- `tmp/ticker-answer-packet-retirement-approval-plan-20260609.json` reports `status=archived`, `legacy_packets_archived_count=42`, `active_reference_count=0`, and replacement owner `scripts/trade_grade_full_answer_assembler.py`.
- The same packet classifies `scripts/ticker_answer_packet.py` as `legacy_compatibility_wrapper`, not an active consumer.

Impact:
Keeping the wrapper is acceptable for compatibility, but using its wording or command as a routine proof path can mislead operators into thinking thinned Markdown still owns structured ticker answers.

Recommendation:
Retain the wrapper only as compatibility/governance proof. Remove it from routine validation bundles and route instructions except where WF85 retirement proof explicitly requires it. Add or update tests that assert `trade_grade_full_answer_assembler.py` is the default answer path.

Acceptance proof:
Workflow routing no longer recommends `python scripts\ticker_answer_packet.py --all-from-coverage --validate` for normal WF85 closeout; it remains only under retirement-plan validation.

### P1-4. Source-Truth Parity Validator Still Measures the Wrong Shape for Thin Notes

Evidence:
- `scripts/veritas_harness_scorecard.py` explicitly marks `go_source_truth_parity_validator` as expected pending because it still targets Markdown Execution Board rows while the board is intentionally SQL-first/thin.
- `tmp/go-source-truth-parity-validation.json` has `status=phase2_sql_first_thin_board_contract_ok`, but its summary shows `markdown_rows=0`, `finance_sql_rows=42`, and all 42 as SQL/canon extras.

Impact:
This is valid migration evidence, but it should not be a hard gate for routine implementation or closeout. Otherwise, thin notes look like drift simply because they are thin.

Recommendation:
Retarget source-truth parity to SQL-native reference/source lineage proof or keep it as expected-pending migration evidence only.

Acceptance proof:
Harness no longer runs this validator as a normal hard gate; any run that sees `markdown_rows=0` reports thin-contract success, not row absence.

### P2-5. `validate_canonical_ownership.py` Is Correct But Mixed-Purpose

Evidence:
- It already short-circuits when SQL-first thin contracts are detected and allowed, returning info that ticker rows/universe rows are owned by SQL/JSON proof.
- Its legacy branch still contains checks for Execution Board table headers, ticker rows, Coverage/Watchlist universe rows, and thesis sections.

Impact:
The current behavior is clean, but the script blends two eras: active thin-note ownership checks and pre-thinning table completeness checks.

Recommendation:
Keep the script, but split or mode-gate it:
- default mode: retired redirect stubs, thin-contract proof, authority boundaries
- legacy mode: old table/header/thesis completeness checks

Acceptance proof:
Default run remains `status=ok` for thin notes without checking for ticker rows; legacy mode remains available for archived/pre-thin regression work.

### P2-6. `veritas_question_router.py` Still Appends Human Notes as Canonical Owner Notes for Structured Families

Evidence:
- `CANONICAL_OWNER_NOTES` maps `price_band_stop`, `technical_posture`, and `deployment_readiness` to `03. Portfolio/Execution Board.md`.
- The router also has SQL-first route support through `FinanceSqlCanonAccess` and `state/finance/finance-canon.sqlite`.

Impact:
The router is mostly SQL-first, but the output can still overstate Markdown as structured owner. That creates operator confusion and may force unnecessary source-open checks for fields already owned by SQL/JSON proof.

Recommendation:
Change the label from `canonical_markdown_or_source_artifacts_to_open` to separate lanes:
- `structured_owner`: SQL/JSON proof
- `human_context_sources`: owner decisions, narrative, policy, weekly reasoning
- `source_open_required`: only when material claim or stale/conflict case requires it

Acceptance proof:
Question-router validation still passes; structured field questions show SQL/JSON as owner and Markdown only as human-context/source-open fallback.

### P2-7. `veritas_technical_pass_validate.py` Validates Old Human-Note File Contracts

Evidence:
- `REQUIRED_REFERENCES` requires `Coverage and Watchlist.md`, `Portfolio Snapshot.md`, `Execution Board.md`, `Weekly Positioning Review.md`, and `Risk Rules.md`.
- The validator note says it proves the skill's local file contract and does not validate live market data or end-to-end workflow quality.

Impact:
This is not wrong for a skill contract, but it should not be treated as proof that those Markdown files own current technical/band/stop state.

Recommendation:
Keep as a skill-contract validator, but rename or annotate it as such. Add a SQL/JSON route check for technical data if it is used in finance closeout.

Acceptance proof:
Output explicitly distinguishes human reference files from structured technical data ownership; finance closeout relies on WF84/WF85 technical/band proof instead.

### P2-8. `today_card_generator.py` Is Mostly SQL-Aware But Still Carries Old Note Linkage

Evidence:
- The script loads `FinanceSqlCanonAccess`, the artifact index, board guardrail, and canonical read-only links.
- It still lists `Execution Board`, `Portfolio Snapshot`, and `Coverage and Watchlist` as `canonical_read_only_links`.

Impact:
This is acceptable for operator navigation, but the label can imply those notes are structured fact owners.

Recommendation:
Keep the generator. Rename the links to `human_context_links` or `owner_note_links`, and keep structured item generation sourced from SQL/JSON proof packets.

Acceptance proof:
Today card continues to validate; its trust banner states SQL/JSON is the structured owner and human notes are context/policy/narrative links.

## Keep

- `scripts/md_finance_structured_drift_lint.py`
- `scripts/finance_sql_markdown_field_ownership.py`
- `scripts/validate_canonical_ownership.py` default thin-contract branch
- `scripts/finance_sql_canon_access.py`
- `scripts/canonical_finance_data_plane.py`
- `scripts/canonical_finance_data_plane_phase6_10.py`
- `scripts/trade_grade_full_answer_assembler.py`
- `scripts/finance_human_notes_thinning_candidates.py` as owner-review lifecycle planner
- `scripts/finance_human_notes_archive_apply.py` only as owner-gated apply helper
- `scripts/sql_source_truth_authority_manifest.py`
- `scripts/sql_source_truth_parity_validator.py` as migration proof, not a routine hard gate
- Portfolio/canon mutation validators that enforce exact approved gates
- Weekly/PDF/deliverable scripts that read human notes for narrative or reporting context

## Narrow Or Move To On-Demand

- `scripts/runtime_performance_scorecard.py` human-note/Go parity command group
- `go-finance-human-notes-sql-check`
- `scripts/python_go_finance_human_notes_sql_check_parity.py`
- `go-source-truth-parity-validator`
- `scripts/python_go_source_truth_parity_validator_parity.py`
- `scripts/veritas_technical_pass_validate.py` when used outside skill validation
- `scripts/today_card_generator.py` human note links/labels
- `scripts/veritas_question_router.py` Markdown source-open labels for structured field families

## Retire Or Archive Candidates

These are candidates only; no action is approved by this audit.

- Routine validation use of `scripts/ticker_answer_packet.py`
- Any workflow-router recommendation that runs `ticker_answer_packet.py --all-from-coverage --validate` outside WF85 retirement proof
- Pre-thinning table/header/thesis completeness checks in `validate_canonical_ownership.py` default mode
- Runtime-performance default runs of human-notes SQL/Go parity checks

## Do Not Retire

- Thinned human Markdown notes themselves. They still own policy, owner decisions, weekly reasoning, source-open narrative, and audit context.
- Source feeders feeding SQL/JSON proof. `tmp/canonical-finance-data-plane-retirement-readiness.json` says `source_feeder_retirement_ready_count=0` and `duplicate_surface_retirement_ready_count=0`.
- Python default helpers. `tmp/python-go-sql-helper-retirement-gate.json` says `retire_python_now_count=0` and `python_fallback_retained=true`.
- Gated portfolio/canon maintenance validators. These remain authority boundary controls.
- Audit, provenance, backup, and archive ledger surfaces.

## Implementation Plan

### Phase 1 - Add A Retirement Inventory Packet

Create `scripts/human_canon_thinning_retirement_inventory.py` to classify scripts/checks into:

- `keep`
- `narrow_on_demand`
- `retire_candidate`
- `do_not_retire`

The packet should read current proof artifacts and write `tmp/human-canon-thinning-retirement-inventory.json`. It must be review-only and must not apply archive/delete/move/cron/canon changes.

Acceptance proof:
Inventory validates `ok`, contains the files listed in this audit, and preserves all authority flags as false for mutation/execution/archive.

### Phase 2 - Contract Routine Validator Budgets

Patch `runtime_performance_scorecard.py` so human-note SQL/Go checks run only under a targeted migration mode, not the default runtime/performance path.

Patch `changed_file_validator_router.py` only if needed so `md_finance_structured_drift_lint.py` and `finance_sql_markdown_field_ownership.py` run for relevant note/SQL-field-family changes, not every broad implementation.

Acceptance proof:
Default runtime scorecard omits human-note parity command execution; targeted mode still runs and validates.

### Phase 3 - Remove Legacy Answer Packet From Routine WF85 Routing

Patch `workflow_routing_index.py` or the WF85 route metadata so `ticker_answer_packet.py --all-from-coverage --validate` appears only in retirement/compatibility proof, not normal WF85 validation.

Acceptance proof:
`workflow_router.py WF85 --answer all --validate` no longer lists the legacy packet command as a normal validation step unless the route is explicitly retirement proof.

### Phase 4 - Relabel Human Notes In Routers And Cards

Patch `veritas_question_router.py` and `today_card_generator.py` to label human notes as context/policy/narrative/source-open links, not structured fact owners.

Acceptance proof:
Router and Today card validations pass; output differentiates SQL/JSON structured ownership from human-context references.

### Phase 5 - Split Or Mode-Gate Canonical Ownership Validation

Patch `validate_canonical_ownership.py` so the default thin-note mode contains only redirect-stub, thin-contract, and authority-boundary checks. Keep old table/header/thesis checks behind `--legacy-table-contract`.

Acceptance proof:
Default run stays `ok` for thinned notes; legacy mode still checks archived/pre-thin table contracts.

### Phase 6 - Prepare Archive/Retirement Proposals Only After Inventory Is Clean

Use existing lifecycle routes before any archive/delete:

- `db_lifecycle_manifest.py --write --validate`
- exact active-reference review
- exact archive packet
- owner approval
- backup/rollback proof

Acceptance proof:
No file is archived, deleted, or moved until a separate owner-approved apply packet exists.

## Recommended Next Safe Action

Implement Phases 1-4 first. They reduce wasted validation and operator confusion without retiring source feeders, deleting scripts, mutating cron schedules, or weakening the SQL/JSON cutover guards.
