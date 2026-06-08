---
name: veritas-macro-pass
description: Produce a Veritas decision-grade macro regime pass for public-market workflows using workspace-first evidence, explicit manual-dependency handling, and regime-aware portfolio implications. Use when refreshing macro regime, rates and inflation posture, risk-on versus risk-off conditions, energy and commodity context, policy-event interpretation, or when preparing weekly positioning, executive briefs, and market-readiness notes.
---

# Veritas Macro Pass

Use this skill to produce a disciplined macro regime review that fits the Veritas finance operating system.

This is not a generic news roundup or a one-number regime classifier.
Use it when the output needs to judge the macro backdrop, explain what is driving it, disclose evidence quality honestly, and translate that backdrop into portfolio and watchlist implications.

## Before starting

Read the relevant workspace stack first when it matters:
- `02. Markets/Macro Regime Dashboard.md`
- `05. Intelligence/Weekly Positioning Review.md`
- `05. Intelligence/Weekly Intelligence Brief.md` if present
- `03. Portfolio/Portfolio Snapshot.md`
- `04. Research/Coverage and Watchlist.md`
- `07. Risk/Risk Rules.md`
- `tmp/market-state.json` when using the scripted macro evidence layer
- `tmp/dashboard-validation.json` when trust status matters

Use the workspace first.
Do not act like macro starts fresh each time if the note layer already contains current regime posture, risk warnings, or open trust gaps.

## Core mission

For each macro pass:
1. identify the current regime clearly
2. explain the main drivers behind it
3. state what evidence is solid versus manual, partial, stale, or unconfirmed
4. identify what changed, if anything
5. translate macro conditions into portfolio and watchlist consequences
6. say what would falsify the current regime read

## Primary regime language

Default to concise labels that are already compatible with the workspace, for example:
- risk-on
- selective risk-on
- mixed / transitional
- risk-off
- restrictive but resilient
- inflationary pressure
- growth scare
- late-cycle resilient

Do not force a canned external regime taxonomy if it makes the output less truthful.
Prefer the label that best matches the evidence actually available.

## Evidence hierarchy

### Tier 1
- central-bank releases and official statements
- government macro data releases
- official commodity or policy sources when relevant

### Tier 2
- reliable public market data already surfaced in `tmp/market-state.json`
- reputable public market and macro data sites
- established financial reporting for context

### Tier 3
- broad market commentary and summaries
- use for framing only, not primary macro truth

Rules:
- if `tmp/market-state.json` is partial or warning-heavy, downgrade confidence explicitly
- if a field is manual, say it is manual
- if timing alignment across sources is mixed, say so
- do not smooth over missing FedWatch or stale policy inputs
- do not pretend futures or latest cash snapshots are true pre-market precision

## Required workflow

### 1. Start with the current machine evidence

If available, inspect:
- `tmp/market-state.json`
- `tmp/dashboard-validation.json`

At minimum, look for:
- rates posture
- inflation posture
- volatility regime
- equity tape context
- energy context
- warnings and manual dependencies

State clearly whether the machine layer is:
- fresh
- usable with caution
- partial
- stale

### 2. Reconcile with the note layer

Compare machine evidence against:
- current macro dashboard
- weekly positioning note
- portfolio posture

If the note layer and machine layer disagree, say so plainly.
Do not silently pick one and pretend there is no conflict.

### 3. Classify the regime

Answer these questions:
- Is the regime risk-on, selective risk-on, mixed, or risk-off?
- Is inflation helping, hurting, or unresolved?
- Are rates restrictive, easing, or ambiguous?
- Is growth resilient, slowing, or rolling over?
- Are energy and commodity conditions supportive, disruptive, or neutral?
- Are we dealing with a clean trend or a caution-heavy mixed state?

### 4. Identify drivers and blockers

For each pass, identify:
- main macro drivers
- main macro risks
- main missing or manual inputs
- key near-term catalysts that could change the read

Examples:
- FOMC
- CPI / PPI
- jobs data
- Treasury yield shifts
- oil shocks
- geopolitical escalations
- earnings read-through when macro-sensitive

### 5. Translate to portfolio impact

Explicitly state what the regime means for:
- core quality growth
- financials
- energy
- defense
- industrials / electrification
- rates-sensitive hedges
- cash posture and patience

When the regime is selective rather than broad, say which sleeves should still be handled with patience even if the macro backdrop is not outright bearish. Do not let a merely decent macro backdrop become a justification for forced deployment.

Do not let the macro section end at description.
Translate it into portfolio consequences.

## Output format

Use this structure unless the user asks for something else.

## Macro regime verdict
- Regime: [concise regime label]
- Confidence: [High / Medium / Low]
- Machine evidence status: [fresh / usable with caution / partial / stale]
- Main drivers: [2-4 bullets]
- Main risks: [2-4 bullets]

**Rates and liquidity**
- [concise judgment]

**Inflation and growth**
- [concise judgment]

**Volatility and risk appetite**
- [concise judgment]

**Energy / commodities / geopolitics**
- [concise judgment]

**What changed**
- [state what is materially different, or say no material change]

**Portfolio implications**
- [3-6 bullets tied to actual sleeves, sectors, or current names]

**Invalidation triggers**
- [2-4 bullets showing what would break the current regime read]

**Data-quality note**
- [explicitly state manual, partial, stale, or unconfirmed dependencies]

## Confidence rules

Use **High** only when:
- machine evidence is fresh
- core fields are populated
- major policy or timing inputs are aligned
- manual dependencies are not dominating the conclusion

Use **Medium** when:
- evidence is usable but some manual or mixed-date dependencies remain
- major fields are directionally clear but not fully clean

Use **Low** when:
- the machine layer is partial or stale
- manual dependencies dominate the call
- key macro signals materially conflict
- the note layer and evidence layer disagree in unresolved ways

## Judgment rules

- Macro is a backdrop, not an excuse for fake precision.
- Mixed evidence should produce mixed language.
- If the regime is selective rather than broad, say selective.
- If policy inputs are manual, the user should feel that uncertainty in the wording.
- Do not smuggle in conviction that the evidence does not support.
- Macro calls should end with portfolio consequences, not just narration.

## Advisor boundary

Macro conclusions can shape portfolio posture, cash patience, sector emphasis, and watchlist triage, but they are not standalone financial advice, owner approval, trade/account authority, or portfolio/canon mutation authority. When macro context becomes holistic allocation guidance, hand off to `veritas-financial-planning-pass` and preserve planning constraints, WF55 language limits, and owner gates.

## What not to do

Do not:
- reduce the whole regime to one sentiment number
- use crypto-specific macro logic as a default for public-equity workflow
- treat news summaries as enough without rates, inflation, and market-state context
- hide unresolved trust gaps
- pretend the macro read is cleaner than the inputs justify

## Good triggers

Use this skill for prompts like:
- "refresh the macro regime"
- "what is the current market regime"
- "how should macro affect the watchlist"
- "what changed in the macro backdrop"
- "turn this into the weekly macro pass"
- "what does the current rates/inflation setup mean for the portfolio"

## Relationship to other skills

- Use `veritas-fundamental-pass` to judge whether businesses deserve serious board status.
- Use `veritas-technical-pass` to judge timing quality and deployment readiness.
- Use this skill to decide whether the broader tape supports, blocks, or tempers those conclusions.
- In the Veritas workflow, macro sets the backdrop, fundamentals choose the businesses, and technicals decide the timing.
