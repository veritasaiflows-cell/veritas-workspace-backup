# External Research Intake Workflow

## Purpose

Use low-cost external models as research feeders without letting them silently become the truth layer.

This workflow is designed for:
- `GPT5.4 Research` with web access but no workspace access
- `Gemini Flash` as a low-cost bounded workspace worker

Primary goal:
- reduce back-and-forth
- preserve auditability
- keep canonical judgment under Veritas / note-layer control

## Core principle

Cheap models may gather, compare, or diagnose.
They do **not** become canonical truth by themselves.

Routing:
- `GPT5.4 Research` -> external web research and challenge passes
- `Gemini Flash` -> bounded workspace audits, comparisons, and narrow implementation diagnosis
- `Claude Sonnet / Opus` -> higher-stakes synthesis and judgment
- `Gemini Pro` -> heavier implementation and multi-file code work
- `Veritas` -> adjudication, routing, and promotion decisions

## Storage layout

### Raw external research
Store raw pasted reports here:
- `tmp/external-research/`

Naming pattern:
- `YYYY-MM-DD <topic> - GPT5.md`
- `YYYY-MM-DD <topic> - Gemini Flash.md`

Template:
- `06. Playbooks/External Model Report Template.md`

Examples:
- `2026-05-01 MSFT Post-Earnings - GPT5.md`
- `2026-05-01 Machine State Audit - Gemini Flash.md`

### Promoted review notes
If a raw report materially matters after review, promote it into the note layer or project continuity layer selectively.
Do **not** auto-promote raw model output into canonical notes.

## What should be saved

### Save GPT5 reports when they provide
- post-earnings external context
- macro / policy / credit background research
- peer comparisons
- strong bull/bear framing
- event-driven risk framing

### Save Gemini Flash reports when they provide
- bounded artifact contradiction audits
- file-level diagnosis
- implementation blame mapping
- validator / trigger / deployment coherence checks

### Do not save routinely
- vague strategic summaries
- broad workspace overviews from Flash
- repetitive outputs with no new finding
- outputs that are clearly stale relative to newer repairs

## Review policy

### Manual review is the default
Preferred flow:
1. create the report using `06. Playbooks/External Model Report Template.md`
2. save the raw model output as a file in `tmp/external-research/`
3. ask Veritas to review the latest report or a named file
4. Veritas decides whether anything should affect notes, tasks, or project continuity

### Heartbeat policy
Heartbeat may review saved reports only when:
- there is a clear reason to inspect them
- the report appears likely to affect a live decision surface
- the review can remain lightweight

Heartbeat should **not** become a bulk report-reader by default.

### Cron policy
Cron-based review can be added later when:
- the folder convention is stable
- report quality is predictable enough
- the review contract is explicit
- output triage can stay thin and low-noise

Until then, use manual invocation or explicit bounded tasks.

## Promotion rules

A saved report may justify action only if it does at least one of the following:
- changes the judgment on a live candidate
- surfaces a real machine contradiction
- reveals a material external risk or catalyst
- provides evidence strong enough to update a project continuity note or canonical scorecard

A saved report does **not** justify action merely because it is articulate.

## Safe automation boundary

Allowed later:
- scheduled scanning for new files in `tmp/external-research/`
- report inventory or digest generation
- candidate triage into `review`, `no_action`, or `promote`

Not allowed by default:
- automatic canonical note rewrites from raw model output
- auto-promotion of deployment state
- auto-editing `portfolio-config.json` or other stateful files from cheap-model reports

## Recommended operator workflow

### GPT5.4 Research
1. run a bounded external research prompt
2. save the full response to `tmp/external-research/`
3. ask Veritas to review it against workspace truth
4. promote only the durable conclusion, not the whole raw dump

### Gemini Flash
1. run a bounded workspace audit or diagnosis prompt
2. save the response to `tmp/external-research/`
3. ask Veritas to compare it with current machine state
4. if useful, convert it into a bounded implementation task for Gemini Pro or a judgment task for Claude

## Durable lesson

Cheap-model leverage is real, but only when scope is constrained and promotion is gated.
The win is lower-cost evidence gathering and bounded diagnosis, not unsupervised authority.
