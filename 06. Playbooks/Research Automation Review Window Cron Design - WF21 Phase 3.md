# Research Automation Review Window Cron Design - WF21 Phase 3

## Purpose

Define the smallest cron-backed review cadence for WF21 without creating a second finance writer lane.

Core rule:
- finance chains remain the only recurring writers for canonical finance artifacts
- WF21 review windows stay downstream, review-only, and internal-only
- if the finance owner artifacts are missing, stale, or ambiguous, the WF21 job stops instead of reconstructing truth

## Shared owner / overlap rule

- **Finance writers stay upstream owners:** `scripts/run_finance_refresh_chain.py` for `post-close` and `sunday`, plus the isolated weekday `post-earnings` catch-up at 15:30 America/Phoenix.
- **WF21 must not write:** canonical finance notes, `tmp/post-earnings-prep.json`, `tmp/post-earnings-note-targets.json`, weekly finance outputs, dashboard validation outputs, workbook manifests, or run summaries.
- **WF21 may write only:** staged raw-event input files and intake-packet output files under `tmp/research-automation/`, plus continuity/control-plane notes after human review.
- **Overlap stop line:** if the required upstream run summary or post-earnings artifacts are missing or older than the intended window, skip packet assembly and report blocked rather than racing the finance lane.

## Dependency map

1. Finance window finishes first.
2. WF21 reads the fresh finance proof surface.
3. Operator-curated raw events are staged under `tmp/research-automation/`.
4. `python scripts\research_intake_packet.py --input <window-file>` runs once.
5. WF21 inspects packet routes / stop lines.
6. Only review surfaces may be updated manually afterward.

## Job Card 1 - WF21 post-close review packet

- **Name**: `wf21-post-close-review-packet`
- **Window family**: post-close
- **Schedule / time zone**: `10 16 * * 1-5` / America/Phoenix
- **Session target**: isolated
- **Owner**: Workflow 21
- **Trigger goal**: assemble one downstream review packet after both the main post-close finance refresh and the 15:30 post-earnings catch-up window have had time to land
- **Read first**:
  1. `06. Playbooks/Project Continuity/Workflow 21 - Recurring Source Bundle and Review Window Pilot.md`
  2. `06. Playbooks/Cron Job Protocol.md`
  3. `tmp/run-summary-post-close.json`
  4. `tmp/run-summary-post-earnings.json`
  5. `tmp/post-earnings-prep.json`
  6. `tmp/post-earnings-note-targets.json`
  7. latest `tmp/research-automation/raw-events-wf21-post-close-*.json` if one was staged manually
- **Execute in order**:
  1. confirm `tmp/run-summary-post-close.json` is present and not blocked/error
  2. confirm same-day `tmp/run-summary-post-earnings.json` exists or explicitly record that no same-day post-earnings catch-up artifact was produced
  3. stop if raw-event input is missing; do not invent one from chat memory
  4. run `python scripts\research_intake_packet.py --input <staged-post-close-input>`
  5. inspect the new intake-packet output for route counts, stop lines, and `canonical_mutation_allowed: false`
- **Artifacts or notes to inspect after execution**:
  - new `tmp/research-automation/intake-packets-*.json`
  - the staged input file used for the run
  - `tmp/run-summary-post-close.json`
  - `tmp/run-summary-post-earnings.json` when present
- **Response contract**:
  - window
  - staged input file used
  - packet output file produced
  - packet count / routed count / stop-line count
  - whether post-earnings catch-up artifacts were consumed
  - whether any packet tried to cross the writer boundary
  - operator action still required
  - blocked reason if skipped
- **Spawn recommendation**: stay in-run
- **Inputs read**:
  - post-close run summary
  - post-earnings run summary
  - post-earnings prep artifacts
  - staged WF21 raw-event input
- **Artifacts or notes it may write**:
  - `tmp/research-automation/raw-events-wf21-post-close-<date>.json` only if pre-staged by the approved manual collector
  - `tmp/research-automation/intake-packets-<timestamp>.json`
  - continuity/control-plane note updates only after human review outside the cron run
- **Delivery mode**: none
- **Trust grade**: review-required
- **Validation proof**: one same-day intake-packet artifact plus the referenced finance run-summary files
- **Stop line**: missing/stale finance summaries, missing staged input, packet validation errors, or any implied canonical mutation
- **Escalation path**: update notes / report blocked; no retry loop beyond one operator-approved rerun
- **Overlap owner**: finance `post-close` + `post-earnings` windows

## Job Card 2 - WF21 Sunday review packet

- **Name**: `wf21-sunday-review-packet`
- **Window family**: Sunday
- **Schedule / time zone**: `15 09 * * 0` / America/Phoenix
- **Session target**: isolated
- **Owner**: Workflow 21
- **Trigger goal**: assemble one weekly review packet after the Sunday finance refresh has already written the weekly macro and intelligence artifacts
- **Read first**:
  1. `06. Playbooks/Project Continuity/Workflow 21 - Recurring Source Bundle and Review Window Pilot.md`
  2. `06. Playbooks/Cron Job Protocol.md`
  3. `tmp/run-summary-sunday.json`
  4. `tmp/weekly-macro-snapshot.json`
  5. `tmp/weekly-intelligence-brief.json`
  6. `tmp/weekly-review-skeleton.json`
  7. latest `tmp/research-automation/raw-events-wf21-sunday-*.json` if one was staged manually
- **Execute in order**:
  1. confirm `tmp/run-summary-sunday.json` is present and not blocked/error
  2. confirm the weekly macro and weekly intelligence artifacts exist and are fresh for the current Sunday window
  3. stop if raw-event input is missing; do not synthesize a packet from stale chat context
  4. run `python scripts\research_intake_packet.py --input <staged-sunday-input>`
  5. inspect the new intake-packet output for routed items, unresolved verification objects, stop lines, and `canonical_mutation_allowed: false`
- **Artifacts or notes to inspect after execution**:
  - new `tmp/research-automation/intake-packets-*.json`
  - the staged Sunday raw-event input file
  - `tmp/run-summary-sunday.json`
  - `tmp/weekly-macro-snapshot.json`
  - `tmp/weekly-intelligence-brief.json`
- **Response contract**:
  - window
  - staged input file used
  - packet output file produced
  - packet count / routed count / stop-line count
  - whether unresolved-truth or geopolitical objects remained unpromoted
  - whether the weekly finance artifacts were fresh enough to trust as inputs
  - operator action still required
  - blocked reason if skipped
- **Spawn recommendation**: stay in-run
- **Inputs read**:
  - Sunday run summary
  - weekly macro snapshot
  - weekly intelligence brief
  - weekly review skeleton
  - staged WF21 raw-event input
- **Artifacts or notes it may write**:
  - `tmp/research-automation/raw-events-wf21-sunday-<date>.json` only if pre-staged by the approved manual collector
  - `tmp/research-automation/intake-packets-<timestamp>.json`
  - continuity/control-plane note updates only after human review outside the cron run
- **Delivery mode**: none
- **Trust grade**: review-required
- **Validation proof**: one same-day intake-packet artifact plus the referenced Sunday finance artifacts
- **Stop line**: missing/stale Sunday summaries, missing staged input, packet validation errors, or any implied canonical mutation
- **Escalation path**: update notes / report blocked; no retry loop beyond one operator-approved rerun
- **Overlap owner**: finance `sunday` window

## Current design verdict

This is design-complete enough for Phase 3 at the artifact level, but not yet live cron state:
- the windows are named
- schedules are named
- dependency order is explicit
- proof artifacts are named
- overlap owners are explicit
- manual-only canonical mutation posture is preserved
- the 15:30 post-earnings catch-up is consumed downstream rather than duplicated

Do not create the cron jobs until the operator decides the manual packet lane is still worth recurring after Phase 4 usefulness review.
