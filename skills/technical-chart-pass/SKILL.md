---
name: technical-chart-pass
description: Deprecated generic technical-analysis fallback for stocks, ETFs, and other liquid public-market assets. Use only when a non-Veritas generic chart read is explicitly requested outside the canonical board-sync workflow. Do not use for technical-sheet updates, watchlist-to-board conversion, deployment-state decisions, or other Veritas board-sync work; use `veritas-technical-pass` instead.
---

# Technical Chart Pass

## Status

Deprecated legacy fallback.

Default to `veritas-technical-pass` for all live Veritas board-sync, watchlist, technical-sheet, weekly-brief, and deployment-readiness work.
Use this skill only when the user explicitly wants a generic technical read that does **not** need the canonical Veritas four-state model.

Use this skill to turn a market idea into a disciplined technical setup.

This is not for vague chart commentary. Use it when the output needs exact levels, entry discipline, invalidation logic, and a clear readiness judgment.

Boundary: treat this as a legacy generic technical-analysis fallback, not the canonical Veritas workflow skill for board sync, deployment-sheet decisions, weekly brief production, post-earnings workflow integration, or watchlist-to-board conversion.

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

Legacy-label translation rule:
- `Ready now` -> usually `Deployable` in the canonical Veritas system
- `Close` -> usually `Watch-only`, or `Blocked` when a catalyst/timing rule is the real reason to wait
- `Bench` -> usually `Watch-only`, or `Repair mode` if the chart is structurally damaged
- `Avoid for now` -> usually `Blocked` or `Repair mode`, not a free-floating bucket

If the output will feed any Veritas board or workflow, stop and use `veritas-technical-pass` instead of relying on this translation layer.

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

When this skill is used for a generic comparison sheet:
- rank the names by risk-adjusted entry quality, not by story strength alone
- call out which names are ready versus just attractive businesses
- do not present the output as the canonical Veritas technical sheet state

## Good triggers

Use this skill for prompts like:
- "finish the precision technical pass"
- "add exact entry and stop levels"
- "which of these watchlist names are technically ready"
- "give me support, resistance, moving averages, and invalidation"

If the request is to update the technical sheet, sync the board, classify deployment state, or produce a Veritas operating judgment, use `veritas-technical-pass` instead.

## Do not use this skill when

- the task is purely fundamental or valuation-driven
- the user only wants news summary without chart timing
- there is no need for exact levels or readiness judgment
