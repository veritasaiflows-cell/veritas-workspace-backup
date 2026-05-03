---
name: veritas-fundamental-pass
description: Produce a decision-grade Veritas fundamental research pass for public equities using reliable public sources, explicit data-quality checks, and the workspace finance operating system. Use when analyzing one or more stocks for business quality, balance-sheet safety, cash-flow durability, valuation, peer ranking, earnings-readiness, or whether a name belongs in the watchlist, research queue, or model portfolio.
---

# Veritas Fundamental Pass

Use this skill to produce a disciplined equity research pass that fits the workspace finance operating system.

This is not a generic stock writeup skill.
Use it when the output needs to be decision-grade, risk-aware, explicit about data quality, and aligned to the live watchlist, portfolio notes, and risk rules.

## Before starting

Read the relevant local note stack first when it matters:
- `02. Markets/Watchlist.md`
- `03. Portfolio/Portfolio Snapshot.md`
- `03. Portfolio/Deployment Trigger Sheet.md` if deployment timing matters
- `05. Intelligence/Weekly Positioning Review.md`
- `07. Risk/Risk Rules.md`
- any ticker-specific or sector-specific research note if it exists

If the name is near earnings or another binary catalyst, fundamentals may still be decision-useful but not deployment-sufficient. Say that explicitly instead of letting business quality leak into timing approval.

Use the workspace first.
Do not analyze a name in isolation if the current vault already contains live posture, risk, or catalyst context that should shape the answer.

## Core mission

For each ticker:
1. resolve the actual company and listing
2. collect reliable public evidence
3. judge business quality, balance-sheet resilience, cash-flow durability, and valuation
4. identify what must be true for the valuation to work
5. identify the fastest thesis breakers
6. place the name in the right operational bucket:
   - candidate for deeper research
   - watchlist only
   - portfolio-quality candidate
   - tactical only
   - avoid for now

## Source hierarchy

Use sources in this order:

### Tier 1
- issuer investor-relations pages
- SEC filings and official reports
- official earnings releases and transcripts when available

### Tier 2
- reputable financial aggregators and market-data sites
- public quote/statistics pages with broad market acceptance

### Tier 3
- financial media and sector reporting for context
- only for catalyst and interpretation support, not as primary line-item truth

Rules:
- cross-check anomalous core metrics against another source
- never fabricate missing metrics
- label stale, partial, conflicting, or approximate data clearly
- if the data is too weak for conviction, say so and downgrade confidence

## Required workflow

### 1. Resolve the entity

For each ticker, state:
- company name
- primary exchange
- country
- why this is the correct interpretation if the symbol could be ambiguous

If the symbol is materially ambiguous and the user context does not resolve it, ask one focused question and stop.

### 2. Collect the core evidence

Capture, where available:
- market cap
- revenue trend
- EPS trend
- gross, operating, and net margins
- return on equity and return on invested capital when available
- cash from operations and free cash flow trend
- current ratio or quick ratio
- debt load and interest coverage
- valuation multiples relevant to the sector
- most relevant recent earnings or guidance context

If a metric is unavailable, mark it `NA`.
Do not fill gaps with fake precision.

### 3. Run the Veritas screen

Use these lenses, in this order:

#### A. Business quality
Ask:
- Is this a real business or just a story stock?
- Are revenue and EPS quality durable or cyclical/noisy?
- Are margins stable, improving, or deteriorating?
- Is the company earning high returns because of real quality or temporary conditions?

#### B. Balance-sheet safety
Ask:
- Can this business absorb stress without financing risk becoming the whole story?
- Is liquidity adequate?
- Is debt acceptable for the business model and sector?
- Would a downturn turn leverage into the dominant thesis breaker?

#### C. Cash-flow durability
Ask:
- Does accounting profit translate into cash?
- Is free cash flow consistently positive?
- Is capital intensity manageable?
- Are buybacks, dilution, or SBC helping or hurting shareholder quality?

#### D. Valuation discipline
Ask:
- What is the market already assuming?
- Is the stock cheap, fair, or expensive versus quality and growth?
- What must happen operationally for current valuation to remain justified?
- Is multiple risk larger than the business risk?

#### E. Operational fit
Ask:
- Does this belong in Randall's current operating universe?
- Is this a core-quality candidate, tactical name, speculative sleeve name, or watch-only idea?
- Does the current portfolio or watchlist already imply a better comparable?

## Data-quality scorecard

Before the final verdict, explicitly state:
- **Coverage**: rough percentage of core fields populated
- **Conflicts**: count of material source conflicts
- **Freshness**: latest quarter, annual only, or stale
- **Confidence cap**:
  - Coverage under 70% -> Low
  - Several material conflicts -> Low
  - Mostly Tier 2 or Tier 3 evidence with limited Tier 1 -> Medium at best

## Output format

Use this structure unless the user requests something else.

### TICKER — Fundamental Verdict
- Resolved entity: [company, exchange, country]
- Verdict: [Bullish / Neutral / Bearish]
- Operational fit: [core-quality / tactical / speculative / watch-only / avoid]
- Confidence: [High / Medium / Low]
- Data quality: Coverage [x%] | Conflicts [x] | Freshness [latest quarter / annual+quarter / stale]

**Business quality**
- [concise judgment with key metrics]

**Balance sheet**
- [concise judgment with key metrics]

**Cash flow**
- [concise judgment with key metrics]

**Valuation**
- [cheap / fair / expensive, with reason]

**What must be true for this to work**
- [1-3 bullets]

**Fastest thesis breakers**
- [1-3 bullets]

**Recent catalysts / earnings context**
- [3-5 concise bullets max, only the most relevant items]

**Bottom line**
- [4-6 lines, decisive, risk-aware, aligned to the current workspace posture]

## Multi-ticker comparison

If multiple tickers are analyzed:
1. analyze each one first
2. then rank them by:
   - business quality
   - balance-sheet resilience
   - cash-flow durability
   - valuation discipline
   - fit with current workspace posture
3. if two names are close, break the tie using:
   - better FCF durability
   - stronger balance sheet
   - cleaner capital allocation
   - lower valuation risk
   - higher confidence in the data

Add this section:

## Peer ranking
1. [ticker] — why #1
2. [ticker] — why #2
3. [ticker] — why #3

### Best fit now
- selected name
- why it wins
- what would invalidate the selection

### Runner-up path
- what would need to change for #2 to become the better choice

## Judgment rules

- Do not confuse a great business with a good stock at the current price.
- Do not let valuation disappear just because the story is exciting.
- Do not overrate noisy cyclical earnings.
- Do not treat media narrative as evidence.
- Prefer explicit uncertainty over fake precision.
- If the company is near earnings and the catalyst risk matters, say so.
- If the output is being used with the portfolio workflow, coordinate with the technical and deployment layers instead of pretending fundamentals alone settle timing.

## What not to do

Do not:
- provide trade execution instructions
- act like a licensed adviser
- rely on a single low-quality source for line-item truth
- hide conflicts or stale data
- produce bloated essays when a clear verdict is possible

## Good triggers

Use this skill for prompts like:
- "give me a fundamental pass on these names"
- "which of these businesses is strongest"
- "rank these stocks fundamentally"
- "is this a real portfolio-quality name or just a story"
- "what has to be true for this valuation to hold"
- "compare these peers and tell me which fits the portfolio"

## Relationship to other skills

- Use `veritas-technical-pass` when timing, support/resistance, and entry discipline matter more than business quality in the Veritas workflow.
- Use this skill first when deciding whether a name deserves serious coverage at all.
- In the Veritas workflow, fundamentals decide whether the business belongs in the serious board. Technicals decide whether the timing is good enough to act.
