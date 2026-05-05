---
name: cron-automation-manager
description: Design and maintain scheduled OpenClaw automation safely. Use when planning or rebuilding cron workflows, deciding heartbeat versus cron responsibilities, or validating that scheduled finance chains produce coherent artifacts without false precision.
---

# Cron Automation Manager

## Purpose

Own scheduled workflow design without letting automation drift into fiction.

## When to Use

Use this skill when:
- scheduling a new reminder or recurring job
- rebuilding workspace cron after resets
- deciding whether work belongs in heartbeat or cron
- validating morning, post-close, or event-driven automation chains
- checking for stale or overlapping scheduled workflows

## Inputs to Check First

Inspect before scheduling:
- `HEARTBEAT.md`
- `AGENTS.md`
- `MEMORY.md`
- `06. Playbooks/Operating Model.md`
- `06. Playbooks/Cron Job Protocol.md`
- `06. Playbooks/Cron Job Retrofit Checklist.md`
- `06. Playbooks/Automation Run Summary Contract.md`
- `06. Playbooks/Cron Run Ledger.md`
- `06. Playbooks/OpenClaw Parallel Pilot Queue.md`
- `scripts/README.md`
- current cron state
- the upstream artifacts or files the job depends on

## Procedure

1. Decide whether the need is heartbeat or cron.
2. Use the `Cron Job Protocol.md` job-card fields in order so the design is symmetrical with sibling jobs.
3. Define the smallest schedule that solves the real problem.
4. Identify dependencies, artifacts, freshness assumptions, and downgrade rules.
5. Prefer one owner for each workflow window.
6. Avoid overlapping jobs that write the same layer.
7. Define the operator-facing response contract and the machine-readable proof surface together.
8. Validate coherence after scheduling with list/show/run/runs plus artifact inspection.
8. Record durable automation rules in the right file.

For research or freshness automation, do not schedule until these are explicit:
- approved source bundle
- owner layer
- review window
- stop lines
- canonical mutation posture

## Scheduling Rules

- Use cron for exact timing, delayed reminders, or isolated background work.
- Use heartbeat for lightweight periodic maintenance only.
- Prefer isolated jobs unless current-session binding is explicitly needed.
- Do not emulate timers with polling loops.
- If upstream artifacts are partial, stale, or manual, the workflow must downgrade confidence instead of speaking with false precision.

## Safety Rules

- Do not schedule jobs against assumptions you have not verified.
- Do not let two jobs silently compete over the same notes or artifacts.
- Keep reminder text readable as a reminder when it fires.
- Validate the resulting artifacts, not just the job creation command.
- If a safe forward fix exists for a broken cron path, take it before stopping at diagnosis.

## Files This Skill May Read

- core files
- `06. Playbooks/Operating Model.md`
- `scripts/README.md`
- relevant notes or generated artifacts
- cron state and run history

## Files This Skill May Edit

- cron jobs
- `HEARTBEAT.md`
- `TOOLS.md`
- daily notes
- operator references when the workflow standard changes

## Output Format

Use this structure:
- scheduling goal
- chosen mechanism: heartbeat or cron
- job card
- dependency chain
- operator action still required
- risk or trust downgrade rules
- validation result

## Memory Update Rules

- log meaningful scheduling changes in the daily note
- promote durable automation policy to `TOOLS.md` or `MEMORY.md`
- keep one clear source of truth for each recurring workflow
- if a new scheduling pattern becomes standard, update `06. Playbooks/Cron Job Protocol.md` instead of inventing a second doctrine note
