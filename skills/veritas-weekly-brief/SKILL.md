---
name: veritas-weekly-brief
description: Orchestrate the Sunday weekly rebuild and weekly intelligence workflow. Use this to run the Sunday refresh chain, reconcile machine-generated weekly artifacts with the live note layer, and produce a decision-grade Weekly Intelligence Brief and Weekly Macro Snapshot that fit the current vault structure and trust rules.
---

# Veritas Weekly Brief

This skill owns the Sunday transition from **last week's state** to **next week's operating map**.

It is a workflow skill, not a replacement for the analysis spine.
Use:
- `veritas-macro-pass` for regime judgment
- `veritas-technical-pass` for actionability and extension discipline
- `veritas-positioning-pass` when the weekly board needs explicit capital-priority ranking

Core rule:
- scripts stage the weekly evidence set
- notes own final judgment
- weekly notes should reconcile machine output with live board truth, not simply restate JSON

## When to use this skill

Use when:
- Randall asks for the weekly review, Sunday refresh, weekly brief, or weekly sweep
- the Sunday operating window should be rebuilt for the coming week
- the machine-generated weekly artifacts exist but the judgment layer has not been completed
- a major weekend regime shift or catalyst reset requires a new weekly operating map

Do not use this for routine weekday refreshes.

## Primary inputs

Run first:
- `python scripts/run_finance_refresh_chain.py sunday`

Then inspect:
- `tmp/weekly-intelligence-brief.json`
- `tmp/weekly-macro-snapshot.json`
- `tmp/macro-regime.json`
- `tmp/dashboard-validation.json`
- `tmp/trigger-sheet.json`
- `tmp/technical-refresh.json`
- `tmp/earnings-calendar.json`
- `tmp/post-earnings-prep.json` when the prior week included material tracked reports

If the weekly chain is partial, stale, or warning-heavy, keep that uncertainty visible in the final weekly notes.

## Required note stack

Before writing or syncing, read the live weekly note layer:
- `05. Intelligence/Weekly Intelligence Brief.md`
- `02. Markets/Macro Regime Dashboard.md`
- `05. Intelligence/Weekly Positioning Review.md`
- `01. Dashboards/This Week.md`
- `01. Dashboards/Executive Brief.md`
- `02. Markets/Watchlist.md`
- `03. Portfolio/Portfolio Snapshot.md`
- `07. Risk/Risk Rules.md`

This is the starting truth set.
Do not act like the weekly process starts from a blank slate.

## Canonical weekly outputs

Primary weekly outputs:
- `05. Intelligence/Weekly Intelligence Brief.md`
- `02. Markets/Weekly Macro Snapshot/<ISO-week>.md` via the script layer
- `05. Intelligence/Weekly Positioning Review.md`
- `01. Dashboards/This Week.md`

Secondary orientation output when materially needed:
- `01. Dashboards/Executive Brief.md`

Important vault rule:
- do **not** update `01. Dashboards/Monday Game Plan.md`
- that file does not exist in the current vault and should not be invented as a dependency

## Required workflow

### 1. Rebuild the weekly evidence spine

Run the Sunday chain and verify it completed cleanly enough to use.

At minimum, confirm:
- `tmp/weekly-intelligence-brief.json` exists
- `tmp/weekly-macro-snapshot.json` exists
- `tmp/macro-regime.json` exists
- `tmp/dashboard-validation.json` exists

Then classify the machine layer as one of:
- fresh
- usable with caution
- partial
- stale

Do not hide that classification in the final weekly work.

### 2. Reconcile machine evidence with live notes

Compare the staged weekly outputs against:
- current macro dashboard
- current weekly positioning review
- current portfolio posture
- current watchlist and deployment board

If the note layer and machine layer disagree, say so plainly.
The weekly process should resolve the disagreement or document why it remains.

### 3. Complete the Weekly Intelligence Brief

The machine brief is a scaffold, not the final product.

Your job is to:
- fill judgment slots
- tighten macro interpretation
- identify the coming week's real catalyst density
- distinguish good assets from good entries
- convert summary into operating implications

Rules:
- preserve the existing note's real section structure unless a structural change is clearly justified
- do not force ISO-week heading logic if the note is already using `Week of ...` style and that remains the live convention
- if the script already appended the week's section, refine it; do not duplicate it
- if the section already exists and no rewrite is justified, provide a delta-style update rather than duplicate content

### 4. Complete the Weekly Macro Snapshot and macro layer

Use `tmp/weekly-macro-snapshot.json` and `tmp/macro-regime.json` as evidence, then reconcile the judgment with:
- `02. Markets/Macro Regime Dashboard.md`
- the macro section of `05. Intelligence/Weekly Intelligence Brief.md`

If the weekend regime read materially changes the macro dashboard, update the dashboard.
If not, do not churn the note just because a weekly run happened.

### 5. Sync the weekly operating board

Use this order:

1. `05. Intelligence/Weekly Intelligence Brief.md`
2. `05. Intelligence/Weekly Positioning Review.md`
3. `01. Dashboards/This Week.md`
4. `02. Markets/Macro Regime Dashboard.md` — only if regime framing materially changed
5. `01. Dashboards/Executive Brief.md` — only if what matters now or trust posture materially changed
6. `02. Markets/Watchlist.md` — only if active-universe membership, coverage tier, or high-level state labels changed materially

Important vault rule:
- `Watchlist.md` remains a navigation index, not a full weekly thesis board
- do not dump weekly commentary or duplicate trigger detail into it

### 6. Weekly judgment standards

A production-grade weekly brief must answer:
- what changed from last week?
- what matters most this coming week?
- which names are actionable, blocked, extended, or broken?
- where is trust degraded by stale/manual/partial inputs?
- what is the capital-priority order if opportunities appear?

Every major weekly section should end with a practical implication for:
- portfolio posture
- deployment patience or offense
- catalyst risk
- watchlist triage

## Trust and contradiction rules

- If policy, credit, breadth, or macro artifacts are warning-heavy, keep that visible.
- If machine output says risk-on but the board is broadly extended, say selective risk-on or mixed rather than repeating a simplistic label.
- If the weekly board remains blocked by earnings density or timing uncertainty, that is part of the weekly conclusion.
- If a machine-generated weekly statement conflicts with note-layer truth, resolve the conflict explicitly.

## Verification gate

After meaningful weekly note updates, run:
- `python scripts/validate_dashboard_state.py --write`

If warnings remain, include them in the final confidence framing.
Do not present the weekly output as clean if the trust layer is not clean.

## Execution procedure

When Randall asks for the weekly review or Sunday refresh:

1. **Research**
   - run `python scripts/run_finance_refresh_chain.py sunday`
   - read the weekly artifacts and current note stack
2. **Analysis**
   - apply macro, technical, and positioning judgment where needed
3. **Drafting**
   - complete the Weekly Intelligence Brief and weekly operating notes
4. **Sync**
   - update only the weekly notes whose owned truth materially changed
5. **Validate**
   - run `python scripts/validate_dashboard_state.py --write`
6. **Report**
   - summarize the weekly posture, main catalysts, priority names, and trust limitations

## Quality standard

A production-grade weekly refresh should leave behind:
- one coherent weekly intelligence brief
- a synchronized weekly positioning map
- a `This Week` note that reflects actual catalysts and intended outcomes
- no invented surfaces that do not exist in the vault
- explicit trust language when the machine layer is degraded

The goal is not just to generate a weekly write-up.
The goal is to open the coming week with a trustworthy operating map.
