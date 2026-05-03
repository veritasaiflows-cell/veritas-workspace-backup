---
name: veritas-post-earnings-sync
description: Orchestrate the end-to-end post-earnings closure workflow for tracked names. Use this to run the post-earnings refresh chain, turn `tmp/post-earnings-prep.json` and `tmp/post-earnings-note-targets.json` into a canonical scorecard under `05. Intelligence/Earnings/`, and synchronize only the note-layer updates that actually belong in the current vault structure.
---

# Veritas Post-Earnings Sync

This skill owns the transition from **reported earnings event** to **synchronized note-layer truth**.

It is a workflow skill, not a replacement for the analysis spine.
Use:
- `veritas-fundamental-pass` for thesis / business / valuation judgment
- `veritas-technical-pass` for band / stop / state judgment
- `veritas-positioning-pass` when the print materially changes portfolio priority or action state

Core rule:
- scripts prepare evidence
- notes own final judgment
- do not promote raw machine output into canonical conclusions without an explicit interpretation pass

## When to use this skill

Use when:
- a tracked company has just reported
- Randall asks to sync, process, interpret, or close out an earnings event
- `tmp/post-earnings-prep.json` and `tmp/post-earnings-note-targets.json` exist and the note layer needs to catch up
- an earnings blocker should be removed, extended, or replaced with a new post-print stance

Do not use this for general research unrelated to a fresh report.

## Primary inputs

Run and inspect these first:

1. `python scripts/run_finance_refresh_chain.py post-earnings`
2. `tmp/post-earnings-prep.json`
3. `tmp/post-earnings-note-targets.json`
4. `tmp/earnings-calendar.json`
5. `tmp/trigger-sheet.json`
6. `tmp/technical-refresh.json`
7. `tmp/dashboard-validation.json`

If the post-earnings chain fails or artifacts are partial, continue only with explicit warnings.
Do not pretend the closure is clean when evidence is weak.

## Canonical output home

The canonical post-earnings interpretation note lives here:
- `05. Intelligence/Earnings/<Ticker> <Quarter> Post-Earnings Scorecard.md`

This is the first required write target.
The scorecard is the canonical interpretation layer for the report.

## Closure-state model

Use these states consistently inside the scorecard and related note updates:

- **Reported, evidence pending** — the event happened, but interpretation is incomplete
- **Interpreted** — results and implications are written clearly in the scorecard
- **Synced** — required downstream note targets were updated selectively
- **Closed with follow-up** — the report is processed, but a real dependency remains explicit

Do not use `Closed` by itself.
If follow-up remains, say what it is.

## Required workflow

### 1. Evidence pass

Before editing notes, identify:
- what actually happened versus consensus
- whether guidance changed
- what the price reaction implies technically
- whether earnings timing is now resolved or rolled forward
- whether the machine layer surfaced warnings, missing fields, or contradictions

If primary-source confirmation is missing, say so directly in the scorecard.
High-confidence secondary evidence is acceptable for a first interpretation pass, but must be labeled honestly.

### 2. Scorecard pass

Create or update the canonical scorecard first.

Minimum sections to preserve or populate:
- event metadata
- results summary
- price reaction
- what the results mean
- sector / peer read-through when relevant
- updated action stance
- thesis integrity check
- required follow-up
- closure state

Rules:
- keep the judgment layer explicit
- distinguish confirmed facts from estimated or unverified figures
- if the technical picture changed materially, say whether the name is now deployable, blocked, repair mode, or watch-only
- if the thesis changed materially, say whether it confirmed, weakened, or invalidated the prior view

### 3. Selective sync pass

Only update the notes that actually own the changed information.
Default sync order:

1. `05. Intelligence/Earnings/<Ticker> <Quarter> Post-Earnings Scorecard.md`
2. `03. Portfolio/Technical Entry and Invalidation Sheet.md` — only if levels, support, resistance, entry band, stop, or repair-mode framing changed
3. `03. Portfolio/Deployment Trigger Sheet.md` — remove or replace the earnings block; update state if the setup changed
4. `03. Portfolio/Portfolio Snapshot.md` — only if current stance, draft role, or portfolio-level implication changed materially
5. `05. Intelligence/Event Calendar.md` — roll the event forward and update closure visibility
6. `05. Intelligence/Weekly Positioning Review.md` or `01. Dashboards/Executive Brief.md` — only if the print materially changes the operating board
7. `02. Markets/Watchlist.md` — only if universe membership, coverage tier, canonical source pointer, or material deployment-state label changed

Important vault rule:
- `02. Markets/Watchlist.md` is a navigation index, not a live catalyst commentary board
- do **not** add freeform post-earnings commentary or duplicate scorecard content there

### 4. Judgment precedence rules

- If machine artifacts and explicit analysis disagree, the analysis judgment wins.
- If the print breaks the old thesis or old levels, say so plainly. No smoothing.
- If a new entry band is not decision-grade yet, do not fake one.
- If the company beat but the stock is still too extended or structurally weak, keep that distinction explicit.
- If the scorecard is solid but board sync is still pending, the closure state is `Interpreted`, not `Synced`.

### 5. Verification pass

After note updates, run:
- `python scripts/validate_dashboard_state.py --write`

If the update introduced or preserved warnings, surface them honestly.
Do not claim full closure if contradiction or trust warnings remain relevant.

## Minimum board-sync logic by note type

### Technical Entry and Invalidation Sheet
Owns:
- entry bands
- support / resistance
- stops / invalidation
- repair-mode technical framing

### Deployment Trigger Sheet
Owns:
- blocked / unblocked state
- deployable vs not deployable state
- post-print readiness judgment in operational terms

### Portfolio Snapshot
Owns:
- current stance
- draft role / weight relevance
- portfolio-level implication

### Event Calendar
Owns:
- removal of stale upcoming framing
- roll-forward to next expected quarter when appropriate
- explicit closure visibility for material tracked earnings

### Watchlist
Owns only:
- active tracking universe membership
- coverage tier
- high-level current deployment state
- canonical source pointer

## Execution procedure

When Randall asks to sync a ticker's earnings:

1. **Research**
   - run `python scripts/run_finance_refresh_chain.py post-earnings`
   - read the relevant `tmp/` artifacts
2. **State the update path briefly**
   - what changed
   - which notes actually need updates
   - what remains unknown
3. **Write the scorecard first**
4. **Sync only the owning notes** in the required order
5. **Validate** with `python scripts/validate_dashboard_state.py --write`
6. **Report the real closure state**
   - Reported, evidence pending
   - Interpreted
   - Synced
   - Closed with follow-up

## Quality standard

A production-grade post-earnings sync should leave behind:
- one canonical scorecard
- no stale upcoming earnings framing for the processed event
- no silent mismatch between scorecard, trigger sheet, technical sheet, and portfolio posture
- explicit unresolved items when closure is partial

The goal is not just to record the quarter.
The goal is to leave the operating board more truthful than it was before the report landed.
