# PDF Brief Standards

## Purpose

Define the house standard for Veritas PDF deliverables.

PDF is the **presentation layer** of the operating system.
It is for fixed-layout, printable, shareable, decision-grade output.
It is not the canonical truth layer.

Canonical truth remains in:
- note layer
- script artifacts
- portfolio / risk / weekly operating notes

PDF exists to package that truth cleanly for review, archival, and discussion.

---

## Core role of PDF in this OS

Use PDF when the output should be:
- printable
- presentation-ready
- portable outside the vault
- visually stable
- concise enough to review fast

Do **not** use PDF as the first drafting surface.
Draft in notes.
Validate in notes and artifacts.
Package in PDF only after the conclusion is coherent.

Blunt rule:
- notes are for thinking
- Excel is for operating
- PDF is for presenting

---

## Best-practice principles adopted

These standards are based on:
- the current Veritas workflow and note stack
- existing workspace output skills (`veritas-pdf-brief`, `veritas-investment-deck`)
- live script outputs (`equity_visual_report.py`, `equity_pdf_report.py`, `equity_ppt_report.py`)
- external best-practice patterns from status-reporting and equity-research conventions

The main patterns worth keeping:
1. lead with the conclusion
2. keep a visible current-state summary near the front
3. separate recommendation, evidence, and risk clearly
4. prefer short sections and strong callouts over long narrative blocks
5. make status, confidence, and unresolved issues easy to scan
6. keep the document tight enough that a real decision-maker will finish it

---

## Approved PDF product types

### 1. Weekly Intelligence PDF

Purpose:
- package the weekly macro + positioning + catalyst read into a committee-grade weekly brief

Primary source stack:
- `05. Intelligence/Weekly Intelligence Brief.md`
- `05. Intelligence/Weekly Positioning Review.md`
- `02. Markets/Macro Regime Dashboard.md`
- `01. Dashboards/This Week.md`
- `tmp/weekly-intelligence-brief.json`
- `tmp/weekly-macro-snapshot.json`
- `tmp/macro-regime.json`
- `tmp/dashboard-validation.json`

### 2. Post-Earnings PDF

Purpose:
- package one earnings event into a clean before/after decision memo

Primary source stack:
- `05. Intelligence/Earnings/<Ticker> <Quarter> Post-Earnings Scorecard.md`
- `tmp/post-earnings-prep.json`
- `tmp/post-earnings-note-targets.json`
- relevant board notes when the earnings changed deployability

### 3. Equity Research / Thesis PDF

Purpose:
- package a single-name research pass or updated thesis into a portable memo

Primary source stack:
- company note / thesis note
- `veritas-fundamental-pass` conclusions
- `veritas-technical-pass` conclusions
- `03. Portfolio/Deployment Trigger Sheet.md`
- `03. Portfolio/Technical Entry and Invalidation Sheet.md`
- visual assets from `equity_visual_report.py`

### 4. Portfolio Positioning PDF

Purpose:
- summarize current positioning logic, capital priority order, risk posture, and what changed

Primary source stack:
- `03. Portfolio/Portfolio Snapshot.md`
- `05. Intelligence/Weekly Positioning Review.md`
- `07. Risk/Risk Rules.md`
- `tmp/trigger-sheet.json`
- `tmp/dashboard-validation.json`

---

## Standard PDF structure

Use this structure unless the product type clearly needs a tighter variant.

1. **Title strip**
   - document type
   - ticker or scope
   - date
   - authoring context if relevant

2. **Executive conclusion**
   - stance
   - what changed
   - what matters now
   - one-line action framing

3. **Status panel**
   - deployment state
   - confidence / trust grade
   - catalyst status
   - validation status
   - unresolved blockers

4. **Evidence section**
   - macro / company / technical / positioning evidence as relevant
   - only the evidence that actually supports the conclusion

5. **Risk and invalidation**
   - what breaks the conclusion
   - what remains uncertain
   - what is manual / stale / partially trusted

6. **Action logic**
   - add / hold / wait / prepare / bench / avoid
   - what must happen next for the stance to improve or worsen

7. **Appendix when needed**
   - methodology
   - source notes
   - extra charts or tables

---

## Product-specific structure rules

## Weekly Intelligence PDF

Recommended flow:
1. weekly verdict
2. macro regime and trust grade
3. key catalysts next week
4. actionable / blocked / extended / broken board summary
5. capital-priority order
6. risks and open questions

Hard rule:
- the weekly PDF must emphasize **change from last week**, not just static description

## Post-Earnings PDF

Recommended flow:
1. quarter verdict
2. what actually changed
3. guidance / thesis / segment read-through
4. technical and deployment impact
5. updated stance
6. next trigger / follow-up needed

Hard rule:
- separate "good quarter" from "good entry"

## Equity Research / Thesis PDF

Recommended flow:
1. thesis in one page
2. business and key drivers
3. valuation / quality / financial support
4. technical and timing posture
5. risks
6. action stance and invalidation

Hard rule:
- no long generic company history section unless it directly matters

## Portfolio Positioning PDF

Recommended flow:
1. current posture
2. top current opportunities
3. names blocked or in repair
4. concentration / sleeve / macro risk
5. what changed since prior review
6. next decision windows

Hard rule:
- this is a decision memo, not a holdings dump

---

## Layout standards

### Page count targets

Default targets:
- Weekly Intelligence PDF: 4-8 pages
- Post-Earnings PDF: 3-6 pages
- Equity Research / Thesis PDF: 5-10 pages
- Portfolio Positioning PDF: 4-8 pages

If a document needs to exceed this, it should do so for evidence reasons, not because unused space exists.

### Typography and density

- readable body size
- obvious section hierarchy
- short bullets beat dense prose
- paragraphs should be rare and earned
- every page should have one dominant message

### Visual rules

- each chart or panel must do real decision work
- one strong panel is better than three weak ones
- annotate key takeaways near the visual
- if a metric is stale or fallback-sourced, label it
- use consistent color semantics for:
  - actionable / constructive
  - caution / blocked
  - broken / invalidated

### Table rules

- use tables for comparison, not decoration
- no giant unfiltered raw dumps
- surface only the rows needed for the decision
- highlight exception cases, not everything

---

## Trust and disclosure rules

Every PDF should make these easy to find:
- data date
- confidence / trust grade
- stale/manual/fallback dependencies
- open risks
- unresolved follow-up items

Never polish uncertainty out of the deliverable.
A good-looking PDF with hidden uncertainty is worse than a rough note.

---

## Workflow rules

### PDF creation sequence

1. run or verify the relevant script chain
2. verify the note-layer conclusion is coherent
3. gather staged visuals / JSON payloads
4. package the PDF
5. label source artifact lineage if built from a Word/deck/report core

### Source-of-truth rule

If the PDF and the note layer conflict, the note layer wins.
The PDF should be regenerated, not treated as authoritative.

### Regeneration triggers

Regenerate a PDF when:
- a weekly view materially changes
- an earnings interpretation changes the stance
- a thesis is upgraded or downgraded
- the portfolio action order changes materially

Do not regenerate for trivial cosmetic edits.

---

## Current implementation posture

Current reusable generators already present:
- `python scripts/equity_visual_report.py <TICKER>`
- `python scripts/equity_pdf_report.py <TICKER>`
- `python scripts/equity_ppt_report.py <TICKER>`

Current skill posture:
- `veritas-pdf-brief` owns what belongs in the PDF
- `veritas-investment-deck` owns slide structure when a presentation is better than a memo

Recommended near-term expansion:
1. standardize a Weekly Intelligence PDF path
2. standardize a Post-Earnings PDF path
3. standardize a Portfolio Positioning PDF path

---

## Bottom line

A Veritas PDF should feel like:
- a real decision document
- short enough to finish
- honest about uncertainty
- visually clean without becoming slide fluff
- directly traceable back to the live operating system
