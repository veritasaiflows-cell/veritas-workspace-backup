# WF72 FTS query hardening proof

- Generated: `2026-05-24T07:48:28Z`
- Status: `ok`
- Owner file: `scripts/workspace_index.py`
- Boundary: workspace index remains retrieval/cache only; source Markdown/JSON remains authority; no canon/apply/approval/trade/account/paper authority.

## Before

- `note-drift` failed with `sqlite3.OperationalError: no such column: drift when raw FTS5 MATCH parsed hyphenated human text as syntax`.

## After

- Exact aliases are returned first when present (for example `WF72`).
- Raw FTS5 query behavior is tried first for compatibility.
- Punctuation-heavy human queries fall back to safe quoted phrase and token-AND variants built from extracted word tokens, so `note-drift` normalizes to `note drift` instead of failing.

## Smoke queries

| Query | Return code | Hits | Top paths |
|---|---:|---:|---|
| `note-drift` | 0 | 5 | 06. Playbooks/Operating Procedures/SQLite Retrieval Index Procedure.md; memory/2026-05-23.md; 06. Playbooks/Project Continuity/Workflow 72 - Financial OS Efficiency Restructure and Priority Compression.md |
| `note drift` | 0 | 5 | 09. Archive/temp-skill-inspect - Archived/portfolio-manager/portfolio-manager/references/rebalancing-strategies.md; 06. Playbooks/Operating Procedures/SQLite Retrieval Index Procedure.md; 06. Playbooks/Project Continuity/E17 Universe Synchronization - Phase 0 Decision.md |
| `Phase 4A SQL canon` | 0 | 5 | memory/2026-05-23.md; skills/sqlite/SKILL.md; 06. Playbooks/Active Workflows.md |
| `WF72` | 0 | 4 | 06. Playbooks/Project Continuity/Workflow 72 - Financial OS Efficiency Restructure and Priority Compression.md; 06. Playbooks/Project Continuity/Workflow 73 - Queue Index and Boot Surface Optimization.md; 06. Playbooks/Active Workflows.md |

## Validation

- `python -m py_compile scripts\workspace_index.py` passed.
- `python scripts\workspace_index.py` rebuilt `tmp/workspace-index.sqlite` and `tmp/workspace-index-report.json` with status `ok`.
- `tmp/wf72-fts-query-hardening.json` and `tmp/workspace-index-report.json` parsed successfully; Markdown proof readability marker check passed.

## Residue

- SQL hits remain retrieval hints only; operators must open source notes/artifacts before judgment or mutation.
