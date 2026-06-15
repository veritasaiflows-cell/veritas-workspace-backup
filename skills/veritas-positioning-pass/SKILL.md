---
name: "veritas-positioning-pass"
description: "Translate macro, fundamentals, technicals, and risk rules into owner-gated portfolio positioning."
---

# Veritas Positioning Pass

Use this skill to turn analysis into disciplined portfolio positioning.

This is not a broker-connected portfolio manager and not a generic advisory questionnaire.
Use it when the question is: what should the portfolio do next, under current macro, fundamental, technical, and risk conditions?

## Before starting

## Effort routing

Before opening the full portfolio stack, classify the request with `veritas-intelligence-effort-router`.

Default route:

- **Band 0:** answer conceptual positioning questions directly.
- **Band 1:** read `tmp/deployment-readiness-surface.json`, current ticker card/answer packet, or PM/router packet before broad notes.
- **Band 2:** refresh only the stale producer needed for the decision, such as deployment readiness, macro signal spine, or a ticker front door.
- **Band 3:** run the full positioning pass when the answer asks what to add, trim, hold, bench, prioritize, or prepare for owner approval.
- **Band 4:** use implementation/QA governance when positioning rules, portfolio maintenance gates, cron routing, or skill contracts change.

For current macro posture inside positioning, prefer `tmp/macro-signal-spine.json` plus `tmp/macro-judgment-draft.json` before older note-layer summaries. If those are warning-classed, carry the warning into portfolio language.

Do not turn review-ready, deployable, or paper-ready language into approval. Capital deployment, paper/live execution, portfolio mutation, cash/sizing/risk-rule changes, and owner approval remain separately gated.

Read the current workspace stack first:
- `03. Portfolio/Portfolio Snapshot.md`
- `03. Portfolio/Execution Board.md`
- `tmp/deployment-readiness-surface.json`
- `04. Research/Coverage and Watchlist.md`
- `05. Intelligence/Weekly Positioning Review.md`
- `02. Markets/Macro Regime Dashboard.md`
- `07. Risk/Risk Rules.md`
- `tmp/portfolio-config.json` if machine-readable portfolio semantics matter

If a short tactical note exists for the current window, read that too.

Use current workspace posture first.
Do not invent a clean-sheet portfolio process when the vault already contains live allocations, sleeves, and risk standards.

## Core mission

For each pass:
1. identify the current portfolio posture
2. identify the relevant macro backdrop
3. identify which names are fundamentally worthy
4. identify which names are technically ready versus merely interesting
5. apply risk rules and capital constraints
6. produce conditional portfolio actions

## Output decisions

Default to these action buckets:
- **Add now**
- **Prepare / conditional add**
- **Hold / maintain**
- **Trim / reduce risk**
- **Bench / no action**
- **Avoid / do not deploy**

Keep actions conditional when confidence or timing is not clean.
Do not issue absolute trade commands.

## Planner/advisor constraint block

Before giving capital-deployment guidance, state known and unknown planning constraints:
- time horizon
- liquidity or cash needs
- income needs
- drawdown tolerance
- concentration limits
- tax/liquidity constraints when known
- sleeve boundaries: core, tactical, speculative, income, hedge
- current cash/dry-powder context if known

If a material constraint is unknown, do not invent it. Keep the action conditional and say what assumption limits the recommendation.

## WF55 probability / regression boundary

Do not use win probability, expected return, percent likelihood, calibrated readiness score, model-ranked deployment, or regression-backed confidence unless WF55 retained-outcome validators explicitly allow it. Until then, use only heuristic, uncalibrated, scenario-weighted, or evidence-depth language.

## Required workflow

### 1. Establish the portfolio context

State:
- current posture
- current cash or dry-powder context if known
- whether the regime supports offense, patience, defense, or selective deployment
- whether the task is about core positions, tactical positions, speculative sleeve, or hedges

### 2. Pull the three analytical layers together

Use the Veritas stack explicitly:
- macro backdrop from `veritas-macro-pass` logic
- business quality from `veritas-fundamental-pass` logic
- setup quality from `veritas-technical-pass` logic

If one layer is missing or weak, say so.
Do not pretend the decision is complete when one of the three pillars is underdefined.

### 3. Apply risk discipline

At minimum, check:
- single-name concentration limits
- sleeve role, core vs tactical vs speculative
- whether cash should be preserved
- whether catalyst risk is too close
- whether stop/invalidation exists
- whether the setup is extended, blocked, broken, or underdefined

If the name does not fit the written risk rules, the portfolio action should reflect that.

### 4. Rank by capital efficiency

When capital is limited, rank candidates by:
1. quality of the business
2. fit with the current macro regime
3. timing quality of the setup
4. clarity of invalidation
5. opportunity cost versus existing holdings or better candidates

Good business quality does not automatically outrank a cleaner lower-risk setup.
If the board contains many names that are "almost" but not actually clean, say so and let cash rank ahead of forced deployment.

### 5. Produce portfolio guidance

Translate analysis into:
- sleeve-level positioning
- name-level action state
- what to add first if capital is limited
- what to avoid even if the story is attractive
- what conditions would justify upgrading or downgrading a name

## Output format

Use this structure unless the user asks for something else.

## Portfolio positioning verdict
- Posture: [neutral / selective offense / defensive / mixed / etc.]
- Confidence: [High / Medium / Low]
- Deployment stance: [deploy selectively / stay patient / protect capital / etc.]

**Macro implication**
- [2-4 bullets]

**Best positioned names now**
- [ticker] Ã¢â‚¬â€ [why]
- [ticker] Ã¢â‚¬â€ [why]
- [ticker] Ã¢â‚¬â€ [why]

**Hold / maintain**
- [ticker] Ã¢â‚¬â€ [why]

**Bench / wait**
- [ticker] Ã¢â‚¬â€ [why]

**Avoid / do not deploy**
- [ticker] Ã¢â‚¬â€ [why]

**Capital priority order**
1. [ticker] Ã¢â‚¬â€ [why first]
2. [ticker] Ã¢â‚¬â€ [why second]
3. [ticker] Ã¢â‚¬â€ [why third]

**Risk notes**
- [3-6 bullets tied to portfolio concentration, catalyst risk, or invalidation clarity]

**Next actions**
- [conditional action 1]
- [conditional action 2]
- [conditional action 3]

## Name-level decision template

When analyzing specific names, use this compact structure:

### TICKER
- Role: [core / tactical / speculative / hedge]
- Fundamental fit: [strong / acceptable / weak]
- Technical state: [Deployable / Blocked / Repair mode / Watch-only]
- Portfolio action: [Add now / Prepare / Hold / Trim / Bench / Avoid]
- Why: [concise judgment]
- Upgrade trigger: [what would improve the case]
- Downgrade trigger: [what would weaken or invalidate the case]

## Judgment rules

- Protect capital first, then pursue upside.
- Do not let a strong thesis override weak timing and bad risk placement.
- Do not let a pretty chart override weak business quality unless the task is explicitly tactical.
- When macro is mixed, size the language and action accordingly.
- Prefer conditional deployment over impulsive full deployment.
- If a better candidate exists, say so directly.
- If a name belongs on the watchlist but not in the portfolio today, say that clearly.
- Make the priority order explicit. The user should be able to see what gets first call on scarce capital and why.
- Underdefined names should remain benched instead of being smoothed into active consideration.

## What not to do

Do not:
- act like a broker or order-entry system
- recommend leverage or margin by default
- hide opportunity-cost tradeoffs
- blur the difference between watchlist admiration and actual capital allocation
- ignore the written risk rules just because conviction feels high

## Good triggers

Use this skill for prompts like:
- "what should the portfolio do now"
- "rank these names for limited capital"
- "what gets added first"
- "what should stay on the bench"
- "how should the current macro backdrop affect deployment"
- "turn this research into actual portfolio actions"

## Relationship to other skills

- `veritas-financial-planning-pass` owns holistic goals/constraints/advisory synthesis when Randall asks for planner-style guidance.
- `veritas-macro-pass` sets the backdrop.
- `veritas-fundamental-pass` decides whether the business belongs in the serious board.
- `veritas-technical-pass` decides whether timing is disciplined enough.
- This skill converts those three layers into actual portfolio positioning logic.

## Automation authority boundary

Positioning passes may recommend portfolio posture, sizing, sleeve, sector, or candidate changes, but autonomous workspace apply routing belongs to `veritas-bounded-portfolio-agent`. Positioning output is decision evidence; it is not trade/account authority.
