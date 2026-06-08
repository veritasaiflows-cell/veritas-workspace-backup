---
name: veritas-investment-deck
description: Build a Veritas finance-first investment presentation deck for a stock, watchlist candidate, or portfolio topic. Use when converting research notes or equity reports into a slide-ready structure with clean hierarchy, decision-focused messaging, portfolio implications, and reusable visual panels.
---

# Veritas Investment Deck

Use this skill when the output should become a presentation, not just a memo.

This is not generic slide fluff.
The deck should stay finance-first, decision-grade, and visually scannable.

## Core mission

Convert research into a slide sequence that answers:
- what is the asset or topic
- what matters now
- what does the evidence say
- what is the decision
- what are the risks
- what should happen next

## Before starting

Read the relevant workspace stack first when it matters:
- `04. Research/Coverage and Watchlist.md`
- `03. Portfolio/Portfolio Snapshot.md`
- `03. Portfolio/Execution Board.md`
- `03. Portfolio/Execution Board.md`
- `tmp/deployment-readiness-surface.json` when the deck touches current actionability or board posture
- `tmp/dashboard-validation.json` when trust grade or stale/manual caveats could affect the output
- `05. Intelligence/Weekly Positioning Review.md`
- `07. Risk/Risk Rules.md`
- any company-specific report, JSON payload, or generated visual panels already created for the name

If a Word report or visual report already exists, reuse its logic and visuals instead of rebuilding everything from scratch.

## Default slide structure

Use this structure unless there is a strong reason not to:

1. **Title / setup**
   - company or topic
   - ticker
   - date
   - one-line framing

2. **Executive summary**
   - thesis in 3 to 5 bullets
   - what matters now
   - action stance

3. **Market and valuation snapshot**
   - price
   - target
   - market cap
   - valuation context
   - institutional context if useful

4. **Quarter and guidance**
   - key reported metrics
   - raised / reaffirmed / cut guidance
   - what changed

5. **Segment or business drivers**
   - main business units
   - best and weakest contributors
   - what is actually driving results

6. **Historical trend**
   - revenue
   - EPS
   - free cash flow if useful

7. **Technical and positioning read**
   - trend posture
   - support / resistance / moving-average structure
   - deployable vs blocked vs repair vs watch-only

8. **Risks**
   - execution
   - macro
   - valuation
   - timing

9. **Decision slide**
   - add / prepare / hold / trim / bench / avoid
   - upgrade trigger
   - downgrade trigger

10. **Appendix**
   - extra metrics
   - methodology
   - source notes

## Slide rules

- one main idea per slide
- use short bullets, not paragraphs
- lead with the conclusion, then support it
- visuals should do real work, not decoration work
- if a chart or panel is weak, remove it
- readability beats density
- do not overfill slides just because data exists

## Visual rules

- larger text beats more text
- darker text beats stylish low-contrast text
- one strong panel per slide is usually enough
- keep colors consistent across the deck
- use portfolio/action color semantics consistently
- if a metric is unreliable, label it instead of polishing it

## Deck tone

- direct
- institutional
- decision-oriented
- no hype
- no generic consulting language
- no fake certainty

## Advisor and authority boundary

Investment decks are presentation and decision-support artifacts. They may recommend owner review, show scenario implications, and summarize portfolio fit, but they do not authorize trades, account actions, owner approval, sizing execution, or workspace canon mutation. Tax, legal, retirement-account, insurance, estate, debt, employment-income, and outside-account issues should be labeled as constraints/referral items, not professional advice.

## Trust and disclosure rules

Every decision-grade deck should make the trust state visible.

At minimum, include or clearly state:
- as-of date
- trust grade or confidence framing
- stale/manual/partial dependency caveats when they matter
- whether the deck reflects note-layer judgment, machine scaffolding, or both
- whether recommendations are heuristic/review-only, owner-gated, and constrained by WF55 probability-readiness limits

If the underlying research or board state is warning-heavy, degraded, or provisional, do not polish that away with cleaner slide language.
The deck must preserve uncertainty instead of laundering it.

## Relationship to scripts

If `scripts/equity_visual_report.py` or a future PowerPoint generator exists, use those outputs as the visual/data base.
This skill defines the story and structure. The script should handle repeatable layout and export.

## Good triggers

Use this skill for prompts like:
- "turn this into a presentation"
- "make a deck for this stock"
- "convert the equity report into PowerPoint"
- "build a pitch deck style report for this name"
- "make slides for the portfolio review"
