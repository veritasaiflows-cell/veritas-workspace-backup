# Excel Operating Workbook Structure

## Purpose

Define the structure for the Veritas Excel operating layer.

Excel is the **operator control surface** of the system.
It is where structured tables, rankings, checklists, and exception monitoring live.
It is not the canonical judgment layer.

Canonical judgment remains in notes.
Excel exists to make recurring operating work faster, clearer, and more auditable.

---

## Core role of Excel in this OS

Use Excel for:
- sortable operating tables
- ranked candidate lists
- exception scanning
- workflow completion tracking
- recurring structured review
- batch comparisons across names and weeks

Do **not** use Excel as the primary home for long-form thesis logic.
Do **not** create a spreadsheet that competes with the note layer for narrative truth.

Blunt rule:
- notes decide
- Excel organizes
- scripts feed
- PDF presents

---

## Best-practice principles adopted

These standards are based on:
- the current Veritas workflow and script stack
- the existing board / earnings / weekly note system
- existing document-generation skills and scripts
- external best-practice patterns from status reporting and dashboard design

The useful patterns worth keeping:
1. put current-state status at the front
2. keep one table per decision job
3. make exceptions and blockers easy to scan
4. distinguish current state from trend / delta
5. use controlled vocabularies instead of freeform chaos
6. make the workbook helpful for weekly operation, not just pretty on day one

---

## Workbook philosophy

The first workbook should be an **operating workbook**, not a valuation model.

Why:
- the current OS gap is workflow visibility and cross-note operational control
- the analysis spine already exists in notes and skills
- a workbook is most valuable when it reduces drift, blind spots, and stale status handling

Recommended first workbook name:
- `Veritas Operating Workbook.xlsx`

Recommended home:
- `06. Playbooks/` or a future `06. Playbooks/Workbooks/`

---

## Workbook architecture

Build the workbook as a set of narrow, useful tabs.
Do not create one giant all-purpose sheet.

## Tab 1 — Control Panel

Purpose:
- front-door operating view
- one-screen summary of current board state

Should show:
- last refresh timestamp
- validation status
- number of actionable names
- number of blocked names
- number of extended names
- number of repair / broken names
- names with stale bands
- names with upcoming earnings inside the blocker window
- current macro regime label
- key warnings from dashboard validation

Data sources:
- `tmp/dashboard-validation.json`
- `tmp/trigger-sheet.json`
- `tmp/macro-regime.json`
- `tmp/earnings-calendar.json`

Hard rule:
- this tab is a triage surface, not a detail dump

## Tab 2 — Watchlist Operating Board

Purpose:
- structured operating table for tracked names

Core columns:
- ticker
- company
- coverage tier
- sleeve / theme
- current state
- deployability label
- nearest catalyst date
- earnings blocker status
- thesis status
- technical freshness flag
- canonical note pointer
- last sync date

Optional columns:
- sector
- country / region if relevant
- quality bucket
- conviction bucket

Primary sources:
- `04. Research/Coverage and Watchlist.md`
- `tmp/trigger-sheet.json`
- `tmp/earnings-calendar.json`
- `tmp/technical-refresh.json`

Hard rule:
- this sheet should remain summary-grade, not a duplicate research database

## Tab 3 — Deployment Ranking

Purpose:
- rank limited-capital opportunities clearly

Core columns:
- ticker
- current action stance
- distance to band
- technical readiness
- earnings / catalyst risk
- macro fit
- invalidation clarity
- portfolio role
- priority rank
- reason for rank

This sheet should answer:
- if capital became available today, where would it go first?

Primary sources:
- `03. Portfolio/Execution Board.md`
- `tmp/trigger-sheet.json`
- `tmp/deployment-check.json`
- `05. Intelligence/Weekly Positioning Review.md`

Hard rule:
- ranking must preserve human judgment; do not pretend a formula alone decides capital allocation

## Tab 4 — Entry Bands and Technical Drift

Purpose:
- monitor staleness and review burden in the technical layer

Core columns:
- ticker
- current price
- entry band low
- entry band high
- stop / invalidation
- distance to band
- stale flag
- review-needed flag
- last updated
- note owner

Primary sources:
- `03. Portfolio/Execution Board.md`
- `tmp/band-proposals.json`
- `tmp/technical-refresh.json`
- `tmp/band-update-log.txt`

Hard rule:
- this is an exception sheet; highlight drift and review need, not just levels

## Tab 5 — Earnings Workflow Tracker

Purpose:
- own post-earnings closure visibility

Core columns:
- ticker
- report date
- quarter
- status
- IR-confirmed date flag
- scorecard created
- interpreted
- board synced
- follow-up open
- next required action
- owner note

Recommended controlled statuses:
- Upcoming
- Reported, evidence pending
- Interpreted
- Synced
- Closed with follow-up

Primary sources:
- `tmp/earnings-calendar.json`
- `tmp/post-earnings-prep.json`
- `tmp/post-earnings-note-targets.json`
- `05. Intelligence/Earnings/`

Hard rule:
- this should reveal unfinished closure immediately

## Tab 6 — Weekly Operating Map

Purpose:
- show this week's real work in one structured surface

Core columns:
- week label
- top macro themes
- key catalysts
- highest-priority names
- names blocked by earnings
- names in repair
- weekly objective
- trust warnings
- next review date

Primary sources:
- `01. Dashboards/This Week.md`
- `05. Intelligence/Weekly Intelligence Brief.md`
- `05. Intelligence/Weekly Positioning Review.md`
- `tmp/weekly-intelligence-brief.json`
- `tmp/dashboard-validation.json`

Hard rule:
- this is for weekly operating focus, not historical archiving of every detail

## Tab 7 — Macro and Validation Monitor

Purpose:
- give one structured read of regime and trust posture

Core columns:
- date
- macro regime
- policy status
- credit regime
- breadth regime
- source mode
- validation grade
- critical count
- warning count
- top warnings

Primary sources:
- `tmp/macro-regime.json`
- `tmp/policy-expectations.json`
- `tmp/credit-spreads.json`
- `tmp/breadth-state.json`
- `tmp/dashboard-validation.json`

Hard rule:
- this tab should make degraded trust visible before it pollutes downstream outputs

## Tab 8 — Portfolio Risk and Concentration

Purpose:
- expose current portfolio construction pressure points

Core columns:
- ticker
- sleeve
- draft weight
- sector
- theme
- concentration bucket
- correlation concern
- catalyst cluster risk
- status
- action needed

Primary sources:
- `03. Portfolio/Portfolio Snapshot.md`
- `07. Risk/Risk Rules.md`
- portfolio config / future structured portfolio exports

Hard rule:
- this tab should stay portfolio-level, not turn into a transaction ledger

---

## Controlled vocabularies

To avoid workbook rot, use explicit values for key status fields.

### Deployability / board state
- Deployable
- Almost deployable
- Blocked
- Bench
- Repair
- Do not touch

### Earnings workflow state
- Upcoming
- Reported, evidence pending
- Interpreted
- Synced
- Closed with follow-up

### Trust grade
- Clean
- Usable with caution
- Partial
- Stale

### Priority rank bucket
- Highest priority
- High priority
- Secondary
- Watch only
- No-action

Do not let ad hoc synonyms multiply.

---

## Visual design rules

- freeze top row and key identifier columns
- use filters on every operating table
- keep one consistent status color scheme across tabs
- avoid merged cells in core tables
- avoid decorative charts unless they help decisions
- make exception columns visually obvious
- keep formulas auditable and simple where possible

If a chart exists, it should answer a real operating question.
Otherwise, skip it.

---

## Automation posture

The workbook should be fed by structured exports, not manual retyping whenever possible.

Recommended generation path:
1. scripts create structured JSON / CSV exports
2. workbook ingests or is regenerated from those structured exports
3. the workbook remains an operating surface, not the source of truth

Near-term recommendation:
- create a future export path for workbook-ready CSVs from the current `tmp/*.json` artifacts
- avoid direct hand-maintained workbook logic for fields already generated by scripts

---

## What the first build should prioritize

## Phase 1 — Minimum viable workbook

Build these tabs first:
1. Control Panel
2. Watchlist Operating Board
3. Deployment Ranking
4. Earnings Workflow Tracker
5. Entry Bands and Technical Drift

Why this set first:
- it directly supports weekly review
- it directly supports post-earnings closure
- it directly supports portfolio-update workflow
- it attacks the current operational blind spots instead of creating spreadsheet theater

## Phase 2 — Weekly and macro expansion

Add:
6. Weekly Operating Map
7. Macro and Validation Monitor

## Phase 3 — Portfolio/risk expansion

Add:
8. Portfolio Risk and Concentration

---

## Workflow integration

### Sunday weekly workflow
- refresh chain runs
- weekly notes are finalized
- workbook updates Control Panel, Weekly Operating Map, Macro/Validation, and Deployment Ranking
- PDF weekly brief can be packaged from the final note layer

### Post-earnings workflow
- `veritas-post-earnings-sync` updates scorecard and board notes
- workbook updates Earnings Workflow Tracker and affected board rows
- if the report matters enough, generate a Post-Earnings PDF

### Portfolio refresh workflow
- `veritas-portfolio-update` syncs technical, trigger, snapshot, and watchlist notes
- workbook updates Watchlist Board, Deployment Ranking, and Technical Drift tabs

---

## Recommended next implementation steps

1. define workbook column schema formally
2. create structured export specs from the current JSON artifacts
3. decide whether the workbook will be:
   - generated from Python, or
   - maintained as a template with imported CSV tabs
4. build the minimum viable workbook first
5. only then add polish or charts

---

## Bottom line

A good Veritas workbook should feel like:
- an operator console
- easy to scan
- hard to corrupt with freeform drift
- tightly connected to the existing note and script OS
- useful every week, not just impressive once

If the workbook becomes a second messy database, it failed.
If it makes the board easier to run, spot-check, and close cleanly, it worked.
