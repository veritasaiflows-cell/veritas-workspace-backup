---
name: veritas-technical-pass
description: Produce a Veritas decision-grade technical pass for stocks, ETFs, and other liquid public-market assets using live chart structure, moving-average posture, entry discipline, invalidation logic, and deployment-state judgment. Use when defining or refreshing support, resistance, entry bands, stops, repair-mode status, blocked status, readiness labels, or when converting a watchlist or thesis list into an execution-aware technical board.
---

# Veritas Technical Pass

Use this skill to convert a market idea into a disciplined technical setup that fits the Veritas finance operating system.

This is not for vague chart commentary.
Use it when the output needs exact levels, clear setup status, deployment discipline, and explicit timing quality.

## Before starting

Read the relevant workspace files first when they matter:
- `02. Markets/Watchlist.md`
- `03. Portfolio/Portfolio Snapshot.md`
- `03. Portfolio/Technical Entry and Invalidation Sheet.md`
- `03. Portfolio/Deployment Trigger Sheet.md`
- `05. Intelligence/Weekly Positioning Review.md`
- `07. Risk/Risk Rules.md`
- any ticker-specific or sector-specific note that already exists

Do not analyze a name as if it were greenfield if the vault already has active posture, risk, or catalyst context.

## Core mission

For each asset:
1. identify the live chart structure
2. define support, resistance, moving-average posture, and setup quality
3. define the preferred entry band or entry style
4. define stop or invalidation logic
5. assign the right operational state
6. say clearly whether the name is actually deployable, merely interesting, broken, or underdefined

## Allowed state language

Use this four-state Veritas model first:
- **Deployable**: setup is decision-grade and timing is acceptable now
- **Blocked**: a binary event or explicit timing rule prevents action
- **Repair mode**: prior setup failed or chart is broken and needs structural repair
- **Watch-only**: idea is interesting but levels, structure, or confidence are not good enough yet

Optional nuance labels may appear inside the note body, but do not replace the main four-state model.

## Data requirements

At minimum, capture:
- current price or latest reliable reference price
- trend posture
- 20-day, 50-day, and 200-day moving-average posture
- nearest meaningful support levels
- nearest meaningful resistance levels
- whether price is in, above, below, or far from the preferred entry zone
- stop or invalidation threshold
- earnings or catalyst timing risk when relevant

If exact values are approximate, say so.
If live chart precision is weak, say so.
Do not fabricate exact levels.

## Required workflow

### 1. Resolve the asset and role

State:
- ticker or symbol
- asset type if not obvious
- whether this is a core-quality candidate, tactical name, hedge, speculative sleeve, or watch-only idea in the current workspace context

### 2. Read the existing board context

Before setting fresh levels, check whether the vault already defines:
- existing entry bands
- prior stop logic
- repair-mode status
- blocked status
- unresolved earnings timing risk

If current live structure materially disagrees with the vault, say so clearly.
Do not smooth over contradictions.

### 3. Analyze the chart structure

For each asset, determine:
- trend direction and quality
- whether price is above or below the 20-day, 50-day, and 200-day
- whether moving averages are rising, flat, or falling if that can be observed reliably
- whether the chart is extended, constructive, weak, or broken
- whether support and resistance are clean or noisy

### 4. Define the discipline layer

For each asset, specify:
- support levels
- resistance levels
- preferred entry band or conditional trigger
- stop or invalidation level
- distance from the preferred entry band in dollars and percent when the reference price is available
- bad behavior to avoid, for example chasing extension or buying directly into resistance

### 5. Assign operational state

Use these rules:

#### Deployable
Use only when:
- structure is constructive enough
- the entry is disciplined now, not theoretical
- stop or invalidation is explicit
- no avoidable earnings or catalyst blocker is too close

#### Blocked
Use when:
- earnings or another binary event makes a normal entry unjustified
- timing-sensitive date uncertainty itself is a reason to wait
- the setup might be valid later, but now is not the time

#### Repair mode
Use when:
- a prior setup has failed
- the chart is below key support or below the old stop
- the stock needs a new base or major reclaim before a fresh long case is even discussable

#### Watch-only
Use when:
- the idea is interesting but not decision-grade
- levels are still underdefined
- structure is too noisy, extended, or ambiguous to treat as real deployment work
- the business may be attractive, but the technical definition is still too weak for capital-allocation ranking

## Output format

Use this structure unless the user asks for something else.

### TICKER
- Price: [current or latest reliable reference]
- Trend posture: [constructive / bullish / mixed / weak / broken]
- 20-day: [above / below / approximate slope if known]
- 50-day: [above / below / approximate slope if known]
- 200-day: [above / below / approximate slope if known]
- Support: [level 1], [level 2]
- Resistance: [level 1], [level 2]
- Preferred entry: [precise band or conditional trigger]
- Stop / invalidation: [level and why]
- State: [Deployable / Blocked / Repair mode / Watch-only]
- Avoid: [bad entry behavior]
- Note: [one concise judgment]

## Ranking use

When used for a board or sheet:
- rank by risk-adjusted entry quality, not story strength
- clearly separate deployable names from merely good businesses
- do not promote a name just because the company is high quality
- if levels are missing, do not fake decision-grade readiness
- underdefined names should stay benched even if they are compelling themes, because undefined levels are a real decision-quality gap, not a cosmetic omission

## Judgment rules

- A good company with a bad chart is not deployable.
- A strong chart far above the preferred entry band is not low-risk.
- Respect the 200-day. Below a weak or falling 200-day usually means extra caution.
- Distinguish trend continuation from late-stage extension.
- Distinguish repair mode from simple earnings blocking.
- Macro-linked assets must include macro dependency in the note.
- If the technical output is being used with the portfolio workflow, coordinate with the fundamental and deployment layers instead of pretending the chart alone settles the decision.

## What not to do

Do not:
- give vague chart vibes without levels
- hide weak data quality
- collapse blocked and repair mode into the same thing
- call something deployable if the stop, band, or catalyst discipline is still unclear
- let enthusiasm outrun the setup

## Good triggers

Use this skill for prompts like:
- "give me the technical pass"
- "refresh the technical sheet"
- "which of these names are technically ready"
- "define entry bands and invalidation"
- "is this blocked or in repair mode"
- "rank these names by technical readiness"

## Sidecar validator pilot

Workflow 29 pilot validator:
- `python scripts/veritas_technical_pass_validate.py --write`

What it proves locally:
- the file references named in this skill's required pre-read contract still exist in the workspace
- the canonical four-state model still appears in this skill
- the minimum data-requirement contract still appears in this skill

What it does not prove:
- live chart correctness
- market-data freshness
- end-to-end technical-sheet quality

Treat this validator as a bounded Tier 2 local proof sidecar, not a substitute for live workflow judgment.

## Relationship to other skills

- Use `veritas-fundamental-pass` to decide whether the business belongs in the serious board.
- Use this skill to decide whether timing quality is good enough to act.
- In the Veritas workflow, fundamentals decide whether a name deserves attention. Technicals decide whether the setup is disciplined enough for real deployment work.
- If an inbound request uses older generic labels such as `Ready now`, `Close`, `Bench`, or `Avoid for now`, translate that request into the canonical four-state Veritas model instead of routing to the deprecated `technical-chart-pass` unless the user explicitly wants the legacy generic format.
