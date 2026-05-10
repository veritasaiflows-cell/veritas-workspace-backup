# WF36 Slice A Retrieval Metadata Follow-up Audit - 2026-05-06

## Scope
- Audit the bounded WF36 follow-up Slice A after implementation in `scripts/workspace_index.py`.
- Confirm the new SQL metadata layer stays retrieval/cache-only, provenance-first, and subordinate to source files.

## Evidence checked
- `scripts/workspace_index.py`
- `06. Playbooks/Project Continuity/Workflow 36 - Workspace Retrieval Index and SQLite Knowledge Layer.md`
- `tmp/workspace-index-report.json`
- direct SQLite inspection of `artifact_metadata`

## What was implemented
- schema advanced to `3`
- added `artifact_metadata` table
- metadata capture limited to:
  - `top_level_keys`
  - `schema_version`
  - `generated_at_utc`
  - `run_id`
- every metadata row is stamped:
  - `source_kind: discovery-only`
  - `source_required: 1`
- `tmp/workspace-index-report.json` is excluded from metadata summarization to avoid self-reference

## Proof
- `python -m py_compile scripts\workspace_index.py`
- `python scripts\workspace_index.py`
- rebuilt report now shows:
  - `schema_version: 3`
  - `artifact_metadata_summary.status: discovery-only`
  - `artifact_metadata_summary.source_required: true`
  - `artifact_metadata_summary.rows: 228`
  - `artifact_metadata_summary.artifacts_summarized: 57`
- direct DB inspection confirmed subordinate rows for sample artifact `tmp/run-summary-morning.json`

## Findings
- No canon-shadowing found.
- No queue-advancement authority was introduced.
- No cron widening or workflow-state automation widening was introduced.
- No self-reference residue remains after excluding `tmp/workspace-index-report.json` from summarization.

## Minor residue
- Null-valued `schema_version` / `run_id` rows are still inserted when those keys are absent.
- That is small noise, not a truth-surface defect.
- Safe to defer unless a later consumer proves the noise matters.

## Verdict
- **Close WF36 bounded follow-up now.**
- Slice A is small enough, honest enough, and properly subordinate.
- Do not widen beyond provenance/discovery metadata without a separate consumer-driven workflow.
