---
name: technical-chart-pass
description: Produce a decision-grade technical analysis pass for stocks, ETFs, and other liquid public-market assets using live charts and reliable public market data. Use when defining or refreshing support/resistance, trend posture, moving-average structure, entry bands, stop levels, invalidation logic, readiness labels, or rank-ordering candidates for watchlists and model portfolios. Especially useful when converting a thesis or watchlist into an execution-aware technical sheet.
---

# Technical Chart Pass

Use this skill to turn a market idea into a disciplined technical setup.

This is not for vague chart commentary. Use it when the output needs exact levels, entry discipline, invalidation logic, and a clear readiness judgment.

## Core workflow

1. Confirm the asset and context
- Identify ticker, asset type, and whether the task is core holding, tactical setup, hedge, or speculative sleeve.
- Read the relevant vault notes first if they exist, especially macro regime, watchlist, portfolio snapshot, and any existing technical sheet.

2. Get live market structure
- Use the browser tool when live chart inspection is needed.
- Prefer reliable public chart and quote sources.
- Capture at minimum:
  - current price
  - recent swing highs and lows
  - nearest support and resistance
  - 20-day, 50-day, and 200-day moving-average posture
  - trend condition, uptrend, range, breakdown risk, or extended move

3. Classify the setup
Use one of these labels:
- Ready now
- Close
- Bench
- Avoid for now

Base the label on both thesis alignment and technical quality. A good company with bad structure is not ready.

4. Define the trade discipline layer
For each asset, specify:
- support levels
- resistance levels
- preferred entry band or entry style
- stop level or invalidation threshold
- what behavior to avoid, for example chasing vertical extension or buying into resistance
- one-sentence judgment on timing quality

5. Note data-quality limits
- If values are approximate, say so.
- If live chart precision is blocked, say so clearly.
- Do not fabricate exact levels.

## Output standard

Use this format unless the user asks for another one:

### TICKER
- Price: [current or recent reference]
- Trend posture: [bullish / constructive / mixed / weak]
- 20-day: [above / below / sloping up / flat / down]
- 50-day: [above / below / sloping up / flat / down]
- 200-day: [above / below / sloping up / flat / down]
- Support: [level 1], [level 2]
- Resistance: [level 1], [level 2]
- Preferred entry: [precise band or conditional trigger]
- Stop / invalidation: [level and why]
- Avoid: [bad entry behavior]
- Readiness: [Ready now / Close / Bench / Avoid for now]
- Note: [one concise judgment]

## Judgment rules

- Prefer pullbacks into support over emotional breakouts unless the breakout is from a clean base with volume.
- Respect the 200-day. A name below a falling 200-day usually needs extra caution.
- Distinguish trend continuation from late-stage extension.
- Do not confuse relative strength with low-risk entry.
- For tactical names, catalysts matter. For core names, structure matters more than excitement.
- If the asset is heavily macro-linked, for example XOM, TLT, or SLV, include the macro dependency in the note.

## Portfolio use

When this skill is used for a portfolio sheet:
- rank the names by risk-adjusted entry quality, not by story strength alone
- call out which names are ready versus just attractive businesses
- keep the output concise enough to paste into a technical sheet or portfolio review note

## Good triggers

Use this skill for prompts like:
- "finish the precision technical pass"
- "add exact entry and stop levels"
- "update the technical sheet"
- "which of these watchlist names are technically ready"
- "give me support, resistance, moving averages, and invalidation"

## Do not use this skill when

- the task is purely fundamental or valuation-driven
- the user only wants news summary without chart timing
- there is no need for exact levels or readiness judgment
