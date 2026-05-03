---
name: veritas-pdf-brief
description: Build a Veritas finance-first PDF deliverable from the live note layer, report assets, or staged artifacts. Use when the output should become a printable, shareable, fixed-layout decision document such as a Weekly Intelligence PDF, Post-Earnings PDF, Equity Research / Thesis PDF, or Portfolio Positioning PDF.
---

# Veritas PDF Brief

This skill owns the **PDF presentation layer**.

Its job is to package already-grounded finance work into a fixed-layout deliverable that is portable, readable, and decision-grade.
It does **not** replace the note layer.
It does **not** turn unfinished machine output into a polished lie.

Core rule:
- notes own canonical judgment
- scripts and staged artifacts supply evidence
- PDF packages the conclusion cleanly for review, archive, and sharing

## When to use this skill

Use when Randall wants:
- a polished PDF brief
- a printable weekly memo
- a post-earnings PDF
- a single-name thesis or research PDF
- a portfolio positioning PDF
- a shareable fixed-layout output instead of a raw note, JSON, Word file, or deck

Do not use this as the first drafting surface.
Do not generate a PDF just because a machine artifact exists.

## Approved PDF product types

### 1. Weekly Intelligence PDF
Use for:
- the Sunday / Monday weekly operating memo
- macro + positioning + catalyst + board-readiness packaging

### 2. Post-Earnings PDF
Use for:
- a company-specific quarter verdict
- packaging scorecard conclusions into a portable decision memo

### 3. Equity Research / Thesis PDF
Use for:
- single-name research
- updated thesis packaging
- visual-report-backed memo output

### 4. Portfolio Positioning PDF
Use for:
- current posture
- capital-priority order
- risk and concentration framing
- what changed in portfolio stance

## Before starting

Read the relevant truth layer first.

Possible source stack:
- canonical workspace notes
- staged JSON payloads in `tmp/`
- generated PNG panels
- generated visual report JSON
- generated Word report if it exists
- generated deck if it exists

Hard rule:
- if the note layer and staged machine output disagree, the note layer wins
- if the note layer itself is not coherent yet, stop and fix that first

## Product-specific source guidance

### Weekly Intelligence PDF
Read first:
- `05. Intelligence/Weekly Intelligence Brief.md`
- `05. Intelligence/Weekly Positioning Review.md`
- `01. Dashboards/This Week.md`
- `02. Markets/Macro Regime Dashboard.md`
- `03. Portfolio/Portfolio Snapshot.md`
- `07. Risk/Risk Rules.md`
- `tmp/weekly-intelligence-brief.json`
- `tmp/weekly-macro-snapshot.json`
- `tmp/macro-regime.json`
- `tmp/dashboard-validation.json`
- `tmp/trigger-sheet.json`
- `tmp/earnings-calendar.json`
- `tmp/technical-refresh.json`
- `tmp/market-state.json`

Only package this PDF after:
1. `python scripts/run_finance_refresh_chain.py sunday`
2. `veritas-weekly-brief` reconciliation
3. `python scripts/validate_dashboard_state.py --write`

### Post-Earnings PDF
Read first:
- `05. Intelligence/Earnings/<Ticker> <Quarter> Post-Earnings Scorecard.md`
- `tmp/post-earnings-prep.json`
- `tmp/post-earnings-note-targets.json`
- relevant board notes if deployability changed

Prefer to use this only after `veritas-post-earnings-sync` completed the scorecard and board sync.

### Equity Research / Thesis PDF
Read first:
- company thesis or research note
- relevant pass outputs or note conclusions from:
  - `veritas-fundamental-pass`
  - `veritas-technical-pass`
  - `veritas-positioning-pass` when relevant
- `03. Portfolio/Deployment Trigger Sheet.md`
- `03. Portfolio/Technical Entry and Invalidation Sheet.md`
- visual assets from `python scripts/equity_visual_report.py <TICKER>` when available

### Portfolio Positioning PDF
Read first:
- `03. Portfolio/Portfolio Snapshot.md`
- `05. Intelligence/Weekly Positioning Review.md`
- `07. Risk/Risk Rules.md`
- `tmp/trigger-sheet.json`
- `tmp/dashboard-validation.json`

## Standard PDF structure

Use this structure unless the product type clearly needs a tighter version.

1. **Title strip**
   - document type
   - ticker or scope
   - date
   - optional authoring context

2. **Executive conclusion**
   - stance
   - what changed
   - what matters now
   - one-line action framing

3. **Status / trust panel**
   - deployment state
   - confidence or trust grade
   - catalyst status
   - validation status
   - unresolved blockers

4. **Evidence section**
   - only the evidence needed to support the conclusion
   - macro / company / technical / positioning evidence as relevant

5. **Risk and invalidation**
   - what breaks the conclusion
   - what remains uncertain
   - stale / manual / fallback dependencies

6. **Action logic**
   - add / hold / wait / prepare / bench / avoid
   - what would upgrade or downgrade the stance

7. **Appendix when needed**
   - source notes
   - methodology
   - compact supporting table or chart

## Product-specific rules

### Weekly Intelligence PDF
Target:
- 4 to 6 pages by default
- hard cap of 8 pages without a real reason

Must include:
- weekly verdict
- macro regime and trust grade
- key catalysts next week
- actionable / blocked / extended / broken board summary
- capital-priority order
- risks and open questions

Hard rules:
- lead with what changed from last week
- make trust degradation visible near the front
- do not bury validation warnings
- do not present raw machine weekly output as final judgment

### Post-Earnings PDF
Must separate:
- a good quarter
- a good thesis
- a good entry

Recommended structure:
1. quarter verdict
2. what changed
3. guidance / thesis / segment read-through
4. technical and deployment impact
5. updated stance
6. next trigger / follow-up needed

### Equity Research / Thesis PDF
Recommended structure:
1. thesis
2. business drivers
3. valuation / quality / financial support
4. technical and timing posture
5. risks
6. action stance and invalidation

Avoid long generic company-history filler.

### Portfolio Positioning PDF
Recommended structure:
1. current posture
2. top opportunities
3. blocked or repair names
4. concentration / sleeve / macro risk
5. what changed
6. next decision windows

Do not turn this into a holdings dump.

## Layout rules

- lead with the conclusion, not the setup
- short sections beat long prose
- every page should feel intentional
- one strong panel is better than multiple weak ones
- tables are for comparison, not decoration
- no giant raw data dumps
- keep contrast and spacing readable

## Visual rules

Use visuals only when they do real decision work.

Allowed visual types:
- compact regime summary panel
- board state table
- catalyst strip
- ranking table
- price/history panel when it truly helps

Avoid:
- decorative charts
- dashboard screenshots
- unreadable tiny tables
- filler visuals added just to make the PDF look more substantial

Use consistent color semantics:
- constructive / actionable
- caution / blocked / review needed
- broken / invalidated / repair
- neutral / informational

## Trust and disclosure rules

Every PDF should make these easy to find:
- written date
- data as-of date when relevant
- trust or validation grade
- stale/manual/fallback dependencies
- unresolved follow-ups

Never polish uncertainty out of the document.
A clean PDF with hidden uncertainty is worse than a rough but honest note.

## Output rule

If the PDF is generated from an existing Word report, deck, or visual-report workflow, note the source lineage.

Examples:
- built from `equity_visual_report.py` assets
- packaged from a session-completed weekly note layer
- derived from post-earnings scorecard plus board sync outputs

## Relationship to skills and scripts

Workflow skills own judgment and reconciliation first:
- `veritas-weekly-brief`
- `veritas-post-earnings-sync`
- `veritas-positioning-pass`
- `veritas-fundamental-pass`
- `veritas-technical-pass`

Presentation/rendering tools own export mechanics:
- `python scripts/equity_visual_report.py <TICKER>`
- `python scripts/equity_pdf_report.py <TICKER>`
- `python scripts/equity_ppt_report.py <TICKER>`
- future weekly/portfolio PDF renderers

This skill defines what belongs in the PDF and what should be omitted.
The script should handle rendering.

## Execution procedure

When Randall asks for a PDF brief:
1. identify which PDF product type is needed
2. verify the relevant note layer is coherent
3. gather the minimum necessary sources and visuals
4. package the PDF around conclusion -> status -> evidence -> risk -> action
5. preserve visible trust and disclosure
6. report what source stack the PDF came from

## Quality standard

A Veritas PDF should feel like:
- a real decision document
- short enough to finish
- clean without fluff
- visually stable
- honest about uncertainty
- directly traceable back to the live operating system
