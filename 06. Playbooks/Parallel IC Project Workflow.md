# Parallel IC Project Workflow

## Purpose

Define how Claude, Gemini, and future ICs can run **in parallel** on separate end-to-end projects inside the Veritas Market Intelligence OS without creating drift.

The goal is not maximum simultaneous motion.
The goal is controlled parallelism that improves freshness, deployability, and operating quality.

## Core rule

Each IC should usually own **one project at a time end to end**.

Do not split one fragile workstream across multiple ICs unless the boundaries are unusually clean.

Good parallelism:
- IC A owns one project continuity note and chain log
- IC B owns a different project continuity note and chain log
- Veritas manages sequencing, approvals, escalation, and cross-project coherence

Bad parallelism:
- two ICs editing the same artifact layer at once
- one IC changing semantics while another changes surfaces that depend on them
- multiple ICs independently redefining trust state

## Minimum structure for each parallel project

Each concurrent project should have:
1. one continuity note
2. one chain log when the work is multi-pass
3. one named IC owner at a time
4. one current phase and next pass
5. explicit non-negotiables
6. explicit operator decisions still open
7. one registry row in `06. Playbooks/IC Project Registry.md`

## Recommended parallel lanes

Use separate lanes like these when work needs to run concurrently:

### Lane A — Core OS integrity
Examples:
- lane semantics
- consistency gates
- trust propagation
- validator hardening
- publication hardening

### Lane B — Deployment readiness
Examples:
- deployability contract
- priority ranking integrity
- morning readiness surfaces
- trust-aware action filtering
- blocked-vs-ready clarity

### Lane C — Research / coverage expansion
Examples:
- new names
- watch-universe expansion
- macro sleeve expansion
- thesis initiation queue

### Lane D — Note reconciliation / controlled write-back
Examples:
- trigger-sheet note reconciliation
- watchlist semantics alignment
- gated canonical note sync helpers

Do not run Lane D in parallel with upstream semantic rewrites unless the ownership boundary is extremely clear.

## Priority order when capital deployment urgency is high

When markets are moving and deployment certainty matters, prefer this order:
1. core OS integrity
2. deployment readiness
3. research expansion
4. note reconciliation

Reason:
- bad semantics or weak trust state can make deployment surfaces dangerous
- research expansion without deployability discipline just adds noise

## Assignment rule

When multiple ICs are available:
- assign one to **bones/trust/freshness**
- assign one to **deployment readiness / operator clarity**
- do not assign both to the same artifact family unless one is purely reviewing

## Coordination rule for Veritas

Veritas should manage the IC layer by doing six things:
1. assign the owner and lane
2. define the current phase/sub-pass
3. reject overlapping scope early
4. absorb the completion report into continuity and chain log
5. update the project registry
6. generate the next pass prompt

Veritas is the orchestration layer, not just a passive mailbox.

## Daily operating cadence for parallel ICs

For active multi-day projects, use this cadence:

### Morning
- decide which projects actually matter today
- assign or confirm one pass per IC
- keep the asks bounded

### During the day
- accept one clean completion report per pass
- avoid forcing constant micro-updates

### Evening / handoff
- update continuity note
- update chain log
- define next pass
- stop if the next move needs operator judgment rather than labor

## Project selection rule

Before opening a new parallel project, ask:
- does this improve deployment certainty or freshness materially?
- is the project bounded enough for an IC to own end to end?
- does it have a clear continuity note and chain log home?
- is it independent from currently active semantic rewrites?

If no, do not open it yet.

## Current recommended parallel pattern

For the current Veritas OS state, the best pattern is:
- **Gemini** -> core OS integrity project (`E17 Universe Synchronization`, now moving into Phase 3)
- **Claude** -> capital deployment readiness project (separate project focused on deployability confidence, blocked-vs-ready clarity, and morning decision quality)

This keeps one IC on the bones and one IC on capital-readiness utility.

## Success criteria for parallel IC operation

Parallel IC work is succeeding when:
- freshness improves
- deployability clarity improves
- trust state becomes more explicit
- no two projects fight over ownership
- operator handoffs get shorter instead of longer

If parallel work creates more synthesis burden than leverage, the structure is wrong.
