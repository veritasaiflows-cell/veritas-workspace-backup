# Workflow 36 - Workspace Retrieval Index and SQLite Knowledge Layer

## Objective
- Build a fast, file-grounded retrieval layer for the Veritas workspace using a local SQLite index.
- Improve workflow lookup, folder audits, source-of-truth checks, and dashboard/document retrieval without replacing canonical Markdown notes.

## Current State
- **Closed with follow-up on 2026-05-06 after the bounded Slice A metadata pass and independent audit.**
- A v1 SQL-backed retrieval layer now exists at `scripts/workspace_index.py`.
- A separate bounded artifact-output retrieval index now exists at `scripts/artifact_index.py` as a 2026-05-09 follow-up slice for market-intelligence and daily-review JSON outputs.
- Latest live build/report on hand is `tmp/workspace-index-report.json` generated 2026-05-06T20:59:09Z:
  - database: `tmp/workspace-index.sqlite`
  - report: `tmp/workspace-index-report.json`
  - schema version: 3
  - documents indexed: 476
  - headings indexed: 6,949
  - links indexed: 172
  - workflow/surface aliases: 254
  - owner-map rows: 11
  - bounded generated artifacts: 90
  - artifact metadata rows: 228
  - freshness rows: 566
  - FTS5 enabled: true
- SQL/SQLite is now the foundation inside WF36; there is no separate WF36-lite pre-pass.
- The active queue scope is still narrow: retrieval/cache-only consumer hardening, selected metadata summaries, and no canon or queue judgment from SQL alone.
- Slice A is now implemented: a discovery-only artifact metadata summary layer records top-level keys plus scalar `schema_version`, `generated_at_utc`, and `run_id` where present.
- Those summaries are explicitly subordinate provenance/shape hints only. They must not become alternate authority for workflow, deployment, dashboard, or portfolio judgments.
- `tmp/workspace-index-report.json` itself is intentionally excluded from the metadata-summary layer to avoid self-referential drift.
- The artifact-output index is also derived/cache-only: `tmp/veritas-artifact-index.sqlite` can speed ticker/window/escalation/capital-recommendation lookup, but source JSON artifacts and canonical notes remain the authority.
- Operator usage now lives in `06. Playbooks/Operating Procedures/SQLite Retrieval Index Procedure.md` so command examples and SQL stop lines do not sprawl across continuity notes.

## Last Meaningful Progress
- Added alias, owner, artifact, freshness, and rebuild-run tables to `scripts/workspace_index.py`.
- Rebuilt the index successfully after WF34/WF35 hardening.
- Implemented the bounded WF36 follow-up Slice A in `scripts/workspace_index.py`, rebuilt the index successfully, and wrote discovery-only artifact metadata summaries into the DB/report.
- Independent closeout audit landed: `08. Audits/WF36 Slice A Retrieval Metadata Follow-up Audit - 2026-05-06.md`.
- Completion audit: `08. Audits/WF36 SQLite Retrieval Knowledge Layer Audit and Completion - 2026-05-05.md`.
- 2026-05-09 follow-up Slice B added `scripts/artifact_index.py` and `scripts/test_artifact_index.py` for market-intelligence / daily-review artifact retrieval; proof and command usage are recorded in the procedure and `scripts/README.md`.

## Scope
- durable SQLite indexing script in `scripts/`
- generated retrieval database and report in `tmp/`
- schema for documents, headings, links, metadata, and full-text search
- bounded query CLI for fast retrieval
- future integration with workflow queue preflight, folder audits, and dashboard/document owner-map checks
- bounded retrieval over market-intelligence and daily-review JSON output packets

## Out of Scope
- replacing OpenClaw memory search
- treating SQLite as canonical truth
- indexing secrets, credentials, `.git`, `.obsidian`, `.openclaw`, `tmp`, or `migration-backups`
- treating artifact-output index rows as portfolio truth without opening the source JSON and owning notes
- autonomous edits based only on search results
- vector embeddings or external database services in v1

## Preflight / Entry Checklist
- [x] confirm SQLite is available through Python stdlib
- [x] build a local generated DB under `tmp/`
- [x] prove FTS search works on a known workflow query
- [ ] decide whether DB/report artifacts should be ignored, retained, or periodically regenerated
- [ ] define which cron jobs may consume the index and under what fail-closed rules

## Execution Posture
- `serial main-session` for v1 implementation and validation
- later cron consumption allowed only as read-only retrieval support

## Owner Layer
- canonical truth: Markdown notes and JSON artifacts in their owning folders
- indexer implementation: `scripts/workspace_index.py`
- generated DB/cache: `tmp/workspace-index.sqlite`
- generated report: `tmp/workspace-index-report.json`
- artifact-output indexer: `scripts/artifact_index.py`
- generated artifact-output DB/cache: `tmp/veritas-artifact-index.sqlite`
- workflow integration owner: this note plus WF30/WF34/WF35 where appropriate

## Review Window
- manual rebuild on demand in v1
- possible later cron rebuild after finance/control-plane windows if it proves useful

## Stop Lines
- index includes secrets, config credentials, runtime state, or generated tmp content beyond intended report/DB
- retrieval result is treated as canonical proof without opening source files
- search output conflicts with source files and no direct source-file inspection follows
- the indexer starts mutating notes or control surfaces

## Surface / Handoff Posture
- may support workflow preflight, folder audits, and dashboard/document truth-owner maps
- may produce retrieval reports
- may not directly advance workflow state without the owning workflow contract gates

## Canonical Mutation Posture
- disallowed; index is read-only/cache-only

## Phased Completion Approach

### Phase 1 - Local SQLite proof
Status: completed
- v1 indexer exists
- DB/report generated
- search proof completed

### Phase 2 - Retrieval contract hardening
Status: completed
- generated DB/report retained under `tmp/`; DB files ignored by git
- manual rebuild remains v1 posture
- consumer rule added: retrieval hit -> open source file(s) before judgment, queue movement, or mutation

### Phase 3 - Workflow integration
Status: completed for v1
- alias table supports workflow lookup and stale-name detection
- owner table supports WF35 dashboard/canonical owner routing
- artifact table supports WF34/WF36 generated-artifact inventory
- freshness/run tables stamp index rebuild state

### Phase 4 - Validation and closeout
Status: completed for v1
- index rebuild proof passed with FTS enabled
- dashboard truth and boundary validators passed or returned only non-blocking informational findings
- recurring index rebuild cron deferred; manual rebuild is safer until consumers prove need

### 2026-05-09 Follow-up Slice B - Artifact-output retrieval index
Status: closed with follow-up for manual-only use; not approved for chain integration
- `scripts/artifact_index.py` rebuilds `tmp/veritas-artifact-index.sqlite` from current market-intelligence and daily-review JSON artifacts
- query modes cover latest escalations, ticker/sleeve lookup, operating window lookup, capital recommendations, and trust/freshness summaries
- boundary remains derived/cache-only; no canonical note mutation, queue movement, or portfolio-state authority
- proof: compile, test, and manual query examples passed; current rebuild indexed 7 source artifact files, 92 market-event rows, 51 daily-review rows, and 13 capital-recommendation rows
- independent audit: `08. Audits/WF36 Slice B Artifact Output SQLite Retrieval QA - 2026-05-09.md` returned `closed with follow-up` as an audit verdict
- main-session follow-up fixes closed the generated DB ignore gap, item-level authority-flag regression gap, and ticker/latest provenance-display gap
- remaining residue: stale-source fail-soft classification is required before any chain integration, because a fresh DB rebuild can faithfully index stale upstream finance artifacts

## Acceptance Gates
- index build succeeds from clean script execution
- FTS search works and returns source paths
- generated DB/cache is clearly non-canonical
- excluded paths are explicit and safe
- at least one workflow lookup and one folder/audit lookup are proved useful
- consuming workflows are told to open source files after retrieval hits
- any indexed finance-contract summaries stay subordinate to live source artifacts and are updated when shared vocab/contracts change
- artifact-output retrieval rows stay subordinate to their source JSON artifacts and owning Markdown notes

## Exit / Closeout Checklist
- [x] generated DB retention/ignore policy decided
- [x] index rebuild rule documented
- [x] query examples documented
- [ ] workflow consumers updated if appropriate - deferred until a separate fail-soft chain-integration pass is approved
- [x] independent QA/audit completed or explicitly deferred
- [x] checkpoint decision recorded

## Checkpoint Decision
- closed with follow-up on 2026-05-06 after Slice A proved discovery-only metadata summaries without canon-shadowing, queue authority, or cron widening.

## Next Pass
- Closed with follow-up.
- If WF36 reopens later, keep the bar unchanged:
  - any added metadata must stay discovery/provenance-only
  - retrieval hit -> open source files/artifacts before judgment, queue movement, or mutation
  - no query-abstraction expansion, no queue/registry authority from SQL, no cron rebuild widening, no portfolio-config split, and no canon-shadowing consumer layer without a separate consumer-driven workflow
- Current 2026-05-09 follow-up residue: run a bounded QA/closeout pass on `scripts/artifact_index.py` before chain integration; if useful, add fail-soft chain integration only after the manual query layer proves value.
- Updated after QA: Slice B is safe manual-only retrieval support. Do not wire it into `chain_manifest.py` or scheduled finance chains until a fail-soft consumer design pass distinguishes fresh DB rebuilds from stale source artifacts and proves degraded behavior.

## Next 1-2 Adjacent Candidate Workflows
- Workflow 30 - Workflow Queue Truth and Carryover Governance Reconciliation
- Workflow 35 - Dashboard and Document Truth-Surface Integration

## Key Files
- `scripts/workspace_index.py`
- `tmp/workspace-index.sqlite`
- `tmp/workspace-index-report.json`
- `scripts/artifact_index.py`
- `scripts/test_artifact_index.py`
- `tmp/veritas-artifact-index.sqlite`
- `06. Playbooks/OpenClaw Parallel Pilot Queue.md`
- `06. Playbooks/IC Project Registry.md`
- `06. Playbooks/Project Continuity/Workflow 30 - Workflow Queue Truth and Carryover Governance Reconciliation.md`
