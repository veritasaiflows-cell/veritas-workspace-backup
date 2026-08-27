# Human Canon Thinning Retirement Audit - DeepSeek V4 Pro - 2026-06-22

## Run Posture

- Challenger route: `ollama-cloud/deepseek-v4-pro:cloud`
- Scope: read-only audit of thinned human finance canon notes and related validators/scripts
- Main-session verification: key claims were checked against live files before inclusion
- Boundary: no archive/delete/move, no cron mutation, no SQL/canon/portfolio mutation, no paper/live/account action, no owner approval inference

## DeepSeek Executive Conclusion

The three primary human finance surfaces are already correctly thinned:

- `03. Portfolio/Execution Board.md`
- `04. Research/Coverage and Watchlist.md`
- `03. Portfolio/Portfolio Snapshot.md`

Each now routes structured ticker facts to `state/finance/finance-canon.sqlite` plus generated/read-only proof packets, while preserving human policy, owner decisions, narrative, historical pointers, and audit context. The remaining work is not more note thinning. It is narrowing legacy validators and compatibility scripts so routine validation does not keep checking for structured rows that no longer belong in human Markdown.

## Top Findings

### P1-1. Core Human Surfaces Are Correctly Thinned

Evidence:
- The three core files contain `THIN HUMAN SURFACE` markers.
- Each declares `Structured owner: state/finance/finance-canon.sqlite plus generated/read-only proof packets`.
- Execution Board states it no longer hand-maintains ticker levels, routing states, price context, evidence currentness, or queue status.
- Portfolio Snapshot states it no longer hand-maintains ticker-level current state, routing, technical levels, evidence currentness, answer-scope membership, or queue status.
- Coverage and Watchlist states it no longer hand-maintains universe tables, queue membership, technical levels, evidence currentness, answer-scope membership, or routing status.

Impact:
The human-note thinning migration has reached the intended state for the core surfaces.

Recommendation:
Keep these files thin. Do not re-expand them into structured ticker tables.

Acceptance proof:
The markers and SQL/JSON route language remain present, and structured facts continue to come from SQL/JSON proof.

### P1-2. `md_finance_structured_drift_lint.py` Is Working, But Should Be Targeted

Evidence:
- `tmp/md-finance-structured-drift-lint.json` is `status=ok`.
- It reports 17 findings and `requires_action_count=0`.
- The script is report-only and carries false mutation/archive/execution authority flags.

Impact:
The lint remains useful as a guard, but it is not currently finding active note-thinning work.

Recommendation:
Keep the script, but run it on demand, after note-layer changes, or in periodic governance sweeps. Do not treat it as a heavy default closeout requirement for unrelated implementation work.

Acceptance proof:
Latest run remains `requires_action_count=0`; changed-file or closeout routing selects it only when relevant surfaces changed.

### P1-3. `finance_sql_markdown_field_ownership.py` Is A Critical Cross-Class Blocker Guard

Evidence:
- It classifies fields into `canon_anchor_required`, `sql_proof_only`, and `human_judgment_only`.
- Current proof classifies 24 rows and ignores 19 cross-class review-needed rows as `not_a_sql_markdown_blocker`.

Impact:
This prevents SQL-proof-only fields from becoming fake Markdown blockers.

Recommendation:
Keep. Run before reconciliation review or migration phase gates.

Acceptance proof:
`cross_class_blockers_ignored=19` or equivalent guard behavior remains present, with all mutation flags false.

### P1-4. `validate_canonical_ownership.py` Should Stay As The Ownership Boundary Validator

Evidence:
- It validates Execution Board, Coverage/Watchlist, Portfolio Snapshot, retired legacy stubs, and archived originals.
- It detects SQL-first thin contracts via `evaluate_sql_first_thin_board_contract()`.
- Current `tmp/canonical-ownership-validation.json` is `status=ok`, with SQL-first thin board and Coverage/Watchlist contracts accepted.

Impact:
This script proves the human-note layer has not drifted back into a structured-data role.

Recommendation:
Keep. Main-session note: keep the default thin-contract branch active, but consider moving legacy table/header/thesis completeness checks behind an explicit legacy mode.

Acceptance proof:
Default validation accepts thin notes without requiring ticker rows; retired stub validation still works.

### P1-5. Go Human-Notes SQL Check Should Be Retained But Not Necessarily Default

Evidence:
- `tmp/go-finance-human-notes-sql-check.json` is `status=ok`.
- It verifies `state/finance/finance-canon.sqlite`, integrity `ok`, 200 active tickers, 42 legacy answer-path rows, and 158 review-monitor rows.
- `tmp/python-go-finance-human-notes-sql-check-parity.json` is `status=ok` with 18 checks, 0 critical, 0 warnings.

Impact:
DeepSeek classifies this as a useful compiled fast validator edge.

Recommendation:
Keep the Go checker. Main-session adjustment: retain it as targeted migration/performance proof, but remove it from default broad runtime scorecard execution if the run is unrelated to human-note/SQL migration.

Acceptance proof:
The checker remains callable and parity-clean; default runtime validation no longer pays this cost unless a migration/human-note mode is selected.

### P2-6. `ticker_answer_packet.py` Is Legacy Compatibility

Evidence:
- Its docstring states `scripts/trade_grade_full_answer_assembler.py` is now the trade-grade full-answer owner.
- The script remains as a legacy reader/writer compatibility wrapper.
- Writes are blocked unless `--allow-legacy-write` is supplied.
- If write is attempted without that flag, it returns `legacy_packet_write_requires_explicit_allow_legacy_write` and points to `scripts\trade_grade_full_answer_assembler.py --all-wf84 --write --validate`.
- `tmp/ticker-answer-packet-retirement-approval-plan-20260609.json` reports legacy packets archived and active references `0`.

Impact:
The wrapper should not be routine validation or cron proof except inside compatibility/retirement proof.

Recommendation:
Narrow to on-demand compatibility and retirement-plan use. Remove from routine WF85 validation paths.

Acceptance proof:
Normal WF85 route points to `trade_grade_full_answer_assembler.py`; `ticker_answer_packet.py` appears only in compatibility/retirement validation.

### P2-7. `veritas_question_router.py` Is SQL-First And Should Be Kept

Evidence:
- It routes finance questions through `FinanceSqlCanonAccess` and `state/finance/finance-canon.sqlite`.
- It enforces source-open requirements before material finance claims.
- It carries review-only authority boundaries and blocks capital/execution authority.

Impact:
This is part of the thinned-canon architecture, not waste.

Recommendation:
Keep. Main-session adjustment: relabel human-note outputs as context/source-open references, not structured field owners.

Acceptance proof:
Question-router validation passes and output separates SQL/JSON structured ownership from human-context links.

### P3-8. `veritas_technical_pass_validate.py` Is Low-Value As Routine Validation

Evidence:
- It checks that `skills/veritas-technical-pass/SKILL.md` references five required workspace files.
- It checks static state labels and data-requirement strings.
- It does not validate live market data or end-to-end workflow quality.

Impact:
This is a narrow skill-contract validator. It can be useful after skill edits, but it is weak evidence for finance data readiness.

Recommendation:
Move to on-demand skill validation. DeepSeek classified it as a retire/archive candidate; main verification recommends narrower use first, not immediate archive.

Acceptance proof:
It is selected only when the technical-pass skill or its file contract changes.

## DeepSeek Classification

### Keep

- `validate_canonical_ownership.py`
- `finance_sql_markdown_field_ownership.py`
- `veritas_question_router.py`
- `veritas_harness_scorecard.py`
- `today_card_generator.py`
- `go-finance-human-notes-sql-check`
- `03. Portfolio/Execution Board.md`
- `04. Research/Coverage and Watchlist.md`
- `03. Portfolio/Portfolio Snapshot.md`

### Narrow / On-Demand

- `md_finance_structured_drift_lint.py`
- `ticker_answer_packet.py`
- `veritas_technical_pass_validate.py`
- Go/Python human-notes SQL parity checks when unrelated to SQL/human-note migration

### Retire / Archive Candidates

Candidates only; no apply authority from this audit:

- Routine use of `ticker_answer_packet.py` as a validation path
- Routine use of `veritas_technical_pass_validate.py` outside skill validation
- Pre-thinning row/table/thesis completeness checks in default validators

### Do Not Retire

- The thinned human surfaces themselves
- SQL/JSON proof guards
- Field-ownership and canonical-ownership boundary validators
- Archive/provenance/retired-stub validation
- Source feeders that still feed WF84/WF85, because current retirement readiness says source-feeder retirement count is `0`

## Main-Session Comparison

Agreements:
- Human notes are correctly thinned.
- `finance_sql_markdown_field_ownership.py` and `validate_canonical_ownership.py` should stay.
- `ticker_answer_packet.py` is legacy compatibility and should not be routine.
- `veritas_technical_pass_validate.py` is low-value outside its narrow skill scope.

Differences:
- DeepSeek was more willing to keep `go-finance-human-notes-sql-check` in validator bundles. Main-session recommendation is stricter: keep the checker, but move it out of default runtime/performance runs unless human-note/SQL migration work is in scope.
- DeepSeek framed `md_finance_structured_drift_lint.py` as on-demand only. Main-session recommendation keeps it as a durable thinning guard, selected by changed-file routing and periodic governance, but not as a broad default validation cost.
- DeepSeek classified `veritas_technical_pass_validate.py` as an archive candidate. Main-session recommendation is first to narrow and relabel it as skill-contract validation before any archive proposal.

## Recommended Next Safe Action

Build a review-only retirement inventory packet, then use it to contract validator budgets and remove legacy answer-packet commands from routine WF85 routes. Do not archive or delete scripts from this audit alone.
