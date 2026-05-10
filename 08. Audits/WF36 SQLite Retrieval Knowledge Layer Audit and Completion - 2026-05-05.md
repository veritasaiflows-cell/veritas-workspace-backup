# WF36 SQLite Retrieval Knowledge Layer Audit and Completion - 2026-05-05

## Plain-English verdict
WF36 is complete as a v1 SQL-backed retrieval layer. It is no longer just text search: the SQLite database now carries documents, headings, links, workflow aliases, truth-owner mappings, a bounded artifact manifest, freshness metadata, and rebuild-run metadata.

It is still not canon. It is a fast map to the source files.

## User direction handled
Randall asked to move "WF36-lite" behind SQL. That is now the posture:
- There is no separate WF36-lite workflow in front of WF34/WF35.
- SQL/SQLite is the foundation inside WF36.
- WF34/WF35 define the boundaries and owner semantics that SQL indexes.

## What exists now
- Script: `scripts/workspace_index.py`
- Database: `tmp/workspace-index.sqlite`
- Report: `tmp/workspace-index-report.json`
- Schema version: 2

## Current indexed tables
- `documents` - Markdown note metadata and body text
- `documents_fts` - SQLite FTS5 search index when available
- `headings` - extracted Markdown headings
- `links` - wikilinks and local Markdown links
- `aliases` - workflow aliases and machine-companion aliases
- `owners` - WF35 truth-owner map for dashboards and canonical surfaces
- `artifacts` - bounded generated-artifact manifest for selected `tmp/` outputs
- `freshness` - per-document/artifact indexed-at metadata
- `runs` - rebuild-run status metadata
- `meta` - schema/root/generated metadata

## Latest build proof
`python scripts/workspace_index.py` returned `status: ok` with:
- schema version: 2
- FTS enabled: true
- documents: 453
- headings: 6,707
- links: 172
- aliases: 251
- owners: 11
- artifacts: 86
- freshness rows: 539

## What SQL is allowed to do
- speed up workflow lookup
- expose stale aliases
- find relevant notes faster
- show which dashboard surfaces summarize which owner notes
- list bounded generated artifacts and their producers/retention classes
- support folder and dashboard audits

## What SQL is not allowed to do
- replace Markdown notes as truth
- advance workflow queue state by itself
- authorize canonical note mutation
- make portfolio/deployment decisions
- index secrets, runtime internals, uncontrolled logs, `.openclaw`, `.obsidian`, `.git`, or broad `tmp/` internals

## Consumer rule
**Retrieval hit -> open source file(s) before judgment, queue movement, or mutation.**

That rule is now written into the report output.

## Query examples proved / available
- workflow lookup:
  - `python scripts/workspace_index.py --search "Workflow 21 Phase 2 packet" --limit 5`
- dashboard truth lookup:
  - `python scripts/workspace_index.py --search "dashboard document truth owner" --limit 5`
- SQL inspection examples:
  - `SELECT * FROM aliases WHERE alias = 'WF34';`
  - `SELECT * FROM owners WHERE surface_path LIKE '01. Dashboards/%';`
  - `SELECT path, producer, retention_class FROM artifacts WHERE path LIKE 'tmp/run-summary%';`

## Cron posture
Manual rebuild remains the right v1 posture.

A cron rebuild can be considered later only if:
- it is read-only
- it never mutates notes
- it never advances workflow state
- it writes run/freshness metadata
- consumers fail closed on stale or missing index state

## Acceptance checklist
- [x] DB/report retention policy decided: retain generated DB/report under `tmp/`; DB files ignored by git; reports may be regenerated.
- [x] Index rebuild rule documented: manual in v1; cron later only as read-only support.
- [x] Query examples documented.
- [x] Alias map added.
- [x] Owner map added.
- [x] Artifact manifest added.
- [x] Freshness/run ledger added.
- [x] FTS search restored and verified.
- [x] Consumer rule explicit.
- [x] WF34/WF35 boundaries represented without making SQL canonical.

## Completion status
**Closed with follow-up.**

Follow-up belongs to later SQL/automation expansion:
- resolve link targets into normalized source paths
- add explicit stale thresholds once workflow consumers need them
- add selected JSON schema summaries after WF32 normalizes finance surfaces
- consider read-only index rebuild cron after the layer proves useful manually
