# Weekly Intelligence PDF Product Spec

## Purpose

Define the first production PDF product for the Veritas operating system.

This document specifies the **Weekly Intelligence PDF**:
- what it is
- when it should be generated
- what sources it uses
- what sections it contains
- what trust rules it must preserve
- how it fits the weekly workflow

---

## Product definition

The Weekly Intelligence PDF is the fixed-layout packaging of the weekly operating conclusion.

It is not a raw export of `Weekly Intelligence Brief.md`.
It is not a presentation deck.
It is not the canonical truth layer.

It is a **decision-grade weekly memo** that compresses the most important macro, positioning, catalyst, and board-readiness conclusions into a portable, scannable document.

Primary user:
- Randall

Primary use cases:
- weekly review
- weekly reset before Monday
- archival snapshot of weekly posture
- shareable committee-grade summary of what matters now

---

## Trigger conditions

Generate the Weekly Intelligence PDF when:
- the Sunday weekly refresh is complete
- the weekly note layer has been judgment-completed
- the board meaningfully changed from the prior week
- Randall explicitly asks for a weekly PDF

Do **not** generate it before the note layer is coherent.
Do **not** generate it as a blind export from unfinished machine output.

---

## Workflow placement

### Upstream workflow

1. run `python scripts/run_finance_refresh_chain.py sunday`
2. complete `veritas-weekly-brief`
3. update, as needed:
   - `05. Intelligence/Weekly Intelligence Brief.md`
   - `05. Intelligence/Weekly Positioning Review.md`
   - `01. Dashboards/This Week.md`
   - `02. Markets/Macro Regime Dashboard.md` when materially changed
   - `01. Dashboards/Executive Brief.md` when materially changed
4. run `python scripts/validate_dashboard_state.py --write`
5. only then package the PDF

### Downstream role

The PDF becomes:
- the portable weekly memo
- a fixed weekly archive artifact
- optional feedstock for a later deck or external review packet

---

## Source stack

### Canonical note inputs
- `05. Intelligence/Weekly Intelligence Brief.md`
- `05. Intelligence/Weekly Positioning Review.md`
- `01. Dashboards/This Week.md`
- `02. Markets/Macro Regime Dashboard.md`
- `03. Portfolio/Portfolio Snapshot.md`
- `07. Risk/Risk Rules.md`

### Structured artifact inputs
- `tmp/weekly-intelligence-brief.json`
- `tmp/weekly-macro-snapshot.json`
- `tmp/macro-regime.json`
- `tmp/dashboard-validation.json`
- `tmp/trigger-sheet.json`
- `tmp/earnings-calendar.json`
- `tmp/technical-refresh.json`
- `tmp/market-state.json`

### Optional visual inputs
- generated charts/panels from current report scripts when they directly help the weekly message

Hard rule:
- if the PDF and note layer disagree, the note layer wins and the PDF must be regenerated

---

## Output path

Recommended output path:
- `06. Playbooks/Weekly Intelligence PDF/`

Recommended filename pattern:
- `Weekly Intelligence PDF - YYYY-MM-DD.pdf`

Optional alternate naming:
- `Weekly Intelligence PDF - Week of YYYY-MM-DD.pdf`

Do not use ambiguous filenames.

---

## Target length

Default target:
- 4 to 6 pages

Hard cap without explicit reason:
- 8 pages

This product should be finishable in one sitting.
If it needs more than 8 pages regularly, the structure is wrong.

---

## Page-by-page structure

## Page 1 — Executive Verdict

Purpose:
- tell the reader what the week means immediately

Required blocks:
- week label / date
- one-sentence regime verdict
- one-sentence portfolio posture verdict
- what changed from last week
- top 3 catalysts for the coming week
- trust grade / validation summary

Required questions answered:
- what matters now?
- are we in offense, patience, or defense?
- what is the biggest near-term risk to the current view?

## Page 2 — Macro and Regime

Purpose:
- summarize the macro backdrop that actually matters to deployment

Required blocks:
- regime label
- policy / rates posture
- credit posture
- breadth posture
- inflation / growth / energy / dollar context as relevant
- macro implication for deployment behavior

Rules:
- do not dump every macro datapoint
- only surface the ones shaping risk or timing
- if policy data is fallback/manual, say so clearly

## Page 3 — Board Readiness and Capital Priority

Purpose:
- translate the weekly conclusion into the actual board state

Required blocks:
- actionable names
- almost-deployable names
- blocked / earnings-sensitive names
- repair / do-not-touch names
- capital-priority order

Preferred format:
- compact table with 1-line notes, not long paragraphs

Required questions answered:
- where would capital go first if conditions improve?
- what remains attractive but unusable right now?

## Page 4 — Catalysts and Earnings Density

Purpose:
- show the catalyst map for the coming week

Required blocks:
- highest-impact macro events
- highest-impact tracked earnings
- names entering or exiting blocker windows
- timing-sensitive risk cluster

Rules:
- focus on tracked names and portfolio-relevant events
- do not reproduce the full event calendar

## Page 5 — Risks, Invalidations, and Trust Limits

Purpose:
- preserve uncertainty honestly

Required blocks:
- top risks to current posture
- what would invalidate the weekly stance
- stale/manual/fallback dependencies
- major unresolved follow-ups

Required examples:
- policy expectations on fallback source
- timing-sensitive earnings-date uncertainty
- stale technical bands needing review

## Optional Page 6 — Appendix / Supporting Table

Use only when needed for:
- a compact watchlist state table
- a technical extension table
- a short validation-warning appendix

Do not add filler appendix pages.

---

## Content rules

### Conclusion-first rule

The first half-page must state:
- regime
- posture
- change
- action implication

No warm-up section.
No generic intro.

### Delta rule

The PDF must emphasize:
- what changed from the prior week
- what stayed true
- what became more or less actionable

A weekly PDF with no delta logic is low value.

### Evidence discipline rule

Every directional claim should be traceable to either:
- a live note-layer conclusion, or
- a current structured artifact

If a claim cannot be grounded, cut it.

### Good asset vs good entry rule

The PDF must preserve the distinction between:
- a name with a strong thesis
- a name with a deployable entry

Do not let weekly enthusiasm blur this.

### Trust visibility rule

Trust degradation must be visible near the front, not buried in fine print.

Use a compact trust panel with:
- validation grade
- critical count
- warning count
- key degraded sources

---

## Visual specification

### Allowed visual types
- compact regime summary panel
- board state table
- catalyst calendar strip
- compact ranking table
- one supporting market or price panel if it clearly helps

### Avoid
- decorative charts
- multi-panel page clutter
- screenshots of raw dashboards
- unreadable tiny tables

### Color semantics
- green / constructive = actionable or healthy
- yellow / caution = blocked, warning, review needed
- red / broken = invalidated, repair, do not touch
- gray = neutral / informational

Use these consistently.

---

## Data freshness and disclosure block

Every Weekly Intelligence PDF must show:
- written date
- market data as-of date/time if relevant
- source mode warnings if material
- validation state

Recommended footer or status-panel fields:
- `Data as of:`
- `Validation:`
- `Trust posture:`

---

## Minimum acceptance criteria

A Weekly Intelligence PDF is acceptable only if:
- weekly note layer is already updated
- `validate_dashboard_state.py --write` has been run
- the PDF includes a visible executive verdict
- the PDF includes a visible trust/risk section
- the PDF distinguishes actionable vs blocked vs broken names
- the PDF clearly states the coming week's key catalysts

If any of these are missing, the product is incomplete.

---

## Recommended implementation path

### Version 1
- use existing weekly notes and JSON artifacts
- generate a clean fixed-layout PDF with simple tables and callout panels
- prioritize readability over styling complexity

### Version 2
- add more reusable visual panels
- add standardized trust panel design
- add optional sector / sleeve mini-panels when they materially help

### Version 3
- integrate more tightly with workbook exports for ranking tables

---

## Relationship to skills and scripts

- `veritas-weekly-brief` owns the weekly judgment workflow
- `veritas-pdf-brief` owns what belongs in the PDF
- future packaging script should own rendering/export

This product should not bypass the weekly skill.
It should sit on top of it.

---

## Bottom line

The Weekly Intelligence PDF should feel like:
- a sharp Sunday/Monday operating memo
- short enough to finish fast
- honest about uncertainty
- explicit about what changed
- directly useful for deployment discipline in the coming week
