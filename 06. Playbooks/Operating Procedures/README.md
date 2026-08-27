# Operating Procedures Repository

## Purpose
This folder is the beginning of the operator-facing procedure repository for running the Veritas OS.

It should hold:
- repeatable operator procedures
- window runbooks
- review-only workflow procedures
- incident / degradation procedures
- repository-maintenance procedures

It should **not** become:
- a second control plane
- a duplicate of continuity notes
- a dumping ground for one-off chat history

## Structure rule
Use this repository for procedures that answer:
- what triggers the procedure
- what to read first
- what to run
- what proof counts
- what stop lines apply
- what the operator should do next

If a note is mostly a workflow history, keep it in continuity or audits instead.
If a note is mostly tool doctrine, keep it in the owning playbook or skill instead.

## Initial repository spine
- `Procedure Index.md`
- `Procedure Classification Rubric.md`
- `Skill-to-Procedure Ownership Map.md`
- `Daily Summary Review-Only Brief Procedure.md`
- `SQLite Retrieval Index Procedure.md`
- `Portfolio Truth Surface Ownership Procedure.md`
- `Subagent Load Budget and Staff Handoff Standard.md`
- `Veritas Encounter Contract.md`

## Current gaps to fill next
- startup / session-opening operating checklist (covered by Startup Truth Index plus `Veritas Encounter Contract.md`)
- execution-efficiency handoff procedure (owned by `Subagent Load Budget and Staff Handoff Standard.md`; route contract remains in `project_implementation_router.py`)
- routine morning closeout / post-close review checklist
- incident / degraded-run response procedure
- cron proof / promotion review procedure
- repository maintenance procedure once the index/classification layer proves stable

## Status posture
This repository is intentionally early.
It is not yet a full OS operator manual.
Build it by promoting proven repeated operations, not by writing aspirational shelfware.

## Plain-English SOP companion
For a simpler non-canonical operator-facing layer, see:
- `06. Playbooks/Operator SOPs/`

Use that folder for plain-English responsibilities and simple how-to notes.
Use this repository for the more structured procedure / classification layer.
