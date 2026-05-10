# WF38 Phase 1 Weekly Sector Expansion Review Contract - 2026-05-06

## Purpose
Create a repeatable weekly review that answers three things clearly:
1. which new sector deserves expansion now
2. which 1-2 names are the best candidates
3. why they beat adding to the current crowded sleeve

## Review window
- default window: weekly, after the Sunday rebuild / weekly refresh chain
- optional mid-week recheck only when a major regime or earnings change materially alters sector ranking

## Inputs to review
- `02. Markets/Regime Scoring Matrix.md`
- `tmp/positioning-ranking.json`
- `03. Portfolio/Deployment Trigger Sheet.md`
- `03. Portfolio/Portfolio Snapshot.md`
- `07. Risk/Risk Rules.md`
- candidate packets under `tmp/`
- `tmp/band-proposals.json` when underdefined names need entry-band review

## Output questions
Each weekly review must answer:
- what sleeve is currently overcrowded or capped?
- which underowned or unowned sector best improves diversification under the current regime?
- which candidate has intact thesis, acceptable regime fit, and the least missing technical/risk definition work?
- what still blocks promotion?
- what does not need to be touched this week?

## Current weekly ranking rule
Prefer candidates that:
- diversify away from the crowded Tech / AI sleeve
- do not worsen a correlated-sleeve cap problem
- fit the current regime
- have cleaner or more obtainable band / invalidation definition work
- do not require a near-term catalyst gamble

## Current recommendation
### Sector expansion priority now
1. **Healthcare**
2. **Industrials**

### Best current candidates
1. **LLY**
   - best first healthcare sleeve monitor and expansion candidate
   - gives real diversification away from the crowded AI stack
   - cleaner strategic diversification value than simply adding another AI-adjacent winner
   - still blocked by missing full entry-band / invalidation / sizing definition
2. **CAT**
   - best industrial diversification candidate tied to resilient-growth / capex / infrastructure posture
   - diversifies away from Tech / AI without forcing energy or doubling financials
   - still needs sharper technical-band / invalidation definition before promotion review

### Secondary candidate
- **AMZN**
  - high quality, but still too adjacent to the large-cap growth / Tech bias to solve the main concentration problem first

## Why these beat adding to the current crowded sleeve
- current draft Tech / AI exposure is already 37% versus a 35% cap in `03. Portfolio/Portfolio Snapshot.md`
- adding more AI or AI-adjacent exposure may improve name quality but worsen concentration discipline
- LLY and CAT expand optionality while reducing dependence on one crowded thematic cluster

## Stop lines
Do not recommend promotion if:
- the candidate still lacks entry band or invalidation definition
- the weekly review relies only on watchlist presence
- the review widens exposure inside an already capped or over-capped sleeve without explicit offset logic
- the candidate is inside a blocked catalyst window
- the review implies deployable-now status without owner-layer promotion

## What the operator needs to do weekly
- read the weekly review output
- choose whether to request candidate packets for the top 1-2 names
- approve any manual band-definition work for underdefined candidates
- decide whether a candidate should move into owner-layer promotion review

## What automation may do safely now
- refresh ranking and sector context
- generate review-only candidate packets
- flag missing band / invalidation / sizing fields

## What automation may not do now
- promote a ticker into deployable-now
- change the Trigger Sheet or Portfolio Snapshot automatically
- widen a sector sleeve by itself
