---
name: "memory-continuity-manager"
description: "Merge memory hygiene with long-work logging."
---

# Memory Continuity Manager

## Summary

Manage memory logging, durable promotion, dedupe, daily-note hygiene, audit-to-memory routing, and compact continuity for long local jobs without creating a parallel memory system.

## Pre-Compaction Flush Discipline

When Randall requests a pre-compaction memory flush:

- write only durable facts that should survive context loss
- use the canonical daily file `memory/YYYY-MM-DD.md`
- append only if the file already exists
- do not create timestamped variants such as `YYYY-MM-DD-HHMM.md`
- treat bootstrap/reference files like `MEMORY.md`, `DREAMS.md`, `SOUL.md`, `TOOLS.md`, and `AGENTS.md` as read-only unless Randall explicitly instructs otherwise
- if nothing durable needs storing, reply `NO_REPLY`

## Duplicate Heading Guard

Before appending to a daily note, check for repeated top-level date headings and repeated topic headings.

Rules:

- one daily file should have at most one primary date heading
- append entries under an existing date/topic section when practical
- do not add a new H1 for every flush or session
- if duplicate H1s already exist, report the hygiene issue or run the approved dedupe tool when the task includes cleanup

Suggested checks:

- search `^# ` in `memory/YYYY-MM-DD.md`
- search for the proposed topic phrase before appending
- run `python scripts\daily_note_dedupe.py memory\YYYY-MM-DD.md --apply` only when cleanup is safe and in scope

## Audit Lesson Routing

After a full workspace audit or targeted finding review, route lessons as follows:

- one-time status result -> daily memory or audit note only
- repeated agent behavior -> skill proposal/update
- repeated operator steps -> operating procedure
- deterministic recurring check -> validator/script
- durable owner preference -> `USER.md` or curated durable memory
- workflow-specific current state -> workflow continuity note

Do not put full audit findings into daily memory if the durable audit note already owns them. Daily memory should record the short outcome and pointer, not duplicate the report.

## Long-Work Memory Rule

When a long-work job is durable enough to affect future pickup, daily memory should record only:

- job id
- owning workflow/workstream
- final or current status
- primary status packet path
- output artifact paths
- exact resume command when not complete
- blocker or warning reason when relevant
- authority boundary if the job is finance/runtime/cron-adjacent

Do not paste full command logs, source lists, chunk lists, trace rows, or generated proof contents into memory. Those belong in JSON artifacts.

## Required Live Proof Before Status Claims

Before claiming current long-work state, read or regenerate:

```powershell
python scripts\long_work_job_status_packet.py --write --write-md --validate
```

Memory is only a pointer. Current status comes from `tmp\long-work-job-status-packet.json` and the per-job `state\long-work-jobs\<job-id>\status.json` file.

## Pre-Compaction Long-Work Pattern

If a long job is in progress or resumable during pre-compaction, store a compact note like:

```text
- Long-work pickup: <job-id> status=<resumable|blocked|warning|complete>; packet=`tmp\long-work-job-status-packet.json`; resume=`python scripts\... resume --job-id <job-id> ...`; boundary=<review-only/proof-only>.
```

If the job is complete and the status packet plus WF88 packet already show it, store only the durable outcome and proof paths.

## Memory As Evidence Boundary

Memory can route work, but it does not prove current state by itself.

When answering status, audit, finance, cron, PM, route, or runtime questions:

- use memory as a pointer to relevant surfaces
- verify live artifacts before claiming current truth
- mark memory-only claims as stale or historical unless refreshed

Memory continuity does not prove execution, approval, finance readiness, paper/live authority, cron schedule authority, config/runtime authority, or mutation authority. It only routes future sessions to the proof surfaces.

## Acceptance Proof

After applying material memory-continuity changes:

- `openclaw skills check` passes
- future pre-compaction flushes avoid duplicate daily headings, timestamp variants, and accidental edits to bootstrap/reference files
- audit closeouts route durable lessons to skills/procedures/validators instead of bloating daily memory
- long-work pickup notes point to status packets and resume commands instead of embedding full logs
