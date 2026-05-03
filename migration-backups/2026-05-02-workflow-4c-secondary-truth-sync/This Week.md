# This Week

## Role in the stack

This note defines the week's intended outcomes.

Use it to answer:
- what has to get done this week?
- what would count as a successful week?

Boundary:
- keep this note outcome-focused and short
- do not turn it into the detailed deployment board, portfolio table, or catalyst map

## Week of April 27 – May 3

This is the densest catalyst week of the cycle: **FOMC April 29 + GOOG/MSFT/AMZN earnings April 29 + CAT April 30 + XOM/CVX May 1 + BRK.B May 2 + ETN May 5 + LMT/RTX still in repair from prior prints.**

## Primary outcome

Finish the week with a clean, disciplined board across the FOMC + megacap + energy earnings cluster, without forcing deployment into extended prices, and with the canonical note layer kept synchronized with the post-earnings evidence layer.

## This week's priorities

1. **Stand down through April 29.** Do not force entries into FOMC + megacap earnings. Let the catalyst window resolve before re-evaluating.
2. **Carry only the live conditional adds:** **JPM** (closest to band, no near-term earnings) and **GS** (second-closest, newly added — verify thesis depth) as the two clean conditional candidates. **ETN** as pullback-only with explicit awareness of the May 5 earnings window. **NVDA** as pullback-only and overbought.
3. **Run `post_earnings_prep.py` after each major print** — GOOG, MSFT, AMZN (April 29); CAT (April 30); XOM, CVX (May 1); BRK.B (May 2); ETN (May 5). Use the structured packet as the basis for any band or state revision.
4. **Keep LMT and RTX explicitly in repair mode** — neither is a fresh opportunity. No pre-base entries.
5. **Verify timing-sensitive earnings dates** — NVDA (vault May 27 vs. yfinance May 20), BRK.B (vault May 4 vs. yfinance May 2), LMT (vault April 23 elapsed; yfinance July 21). Cross-check with IR before relying.
6. **Update Fed target constants in `scripts/market_state_refresh.py`** the morning after April 29 FOMC if the rate or stance materially changes.
7. **Refresh the Weekly Intelligence Brief** post-cluster — the auto-generated section appended on Sunday will need narrative completion in the judgment slots.

## Success condition

By the end of this week, we should have:
- a fresh technical and deployment board reflecting all post-earnings prints in the cluster
- structured post-earnings packets (`tmp/post-earnings-prep.json`) written and applied to the note layer for each ticker that printed
- updated Fed target constants if the FOMC moves anything
- explicit go/no-go decisions on each name that printed: did the band hold, did it need reset, did the thesis confirm or invalidate
- a clear capital-priority order heading into May: JPM and GS as the cleanest near-band names, then the post-earnings winners (if any) from this week's prints
- LMT and RTX still explicitly in repair, not quietly drifting back into active capital-allocation thinking
- the operating loop proven against a real high-density catalyst window — three earnings clusters plus FOMC plus energy prints

## Things to avoid

- forcing entries into earnings-blocked names because the chart looks good
- letting LMT/RTX repair-mode framing erode just because there's earnings noise around them
- treating the auto-generated Daily Executive Summary as final without a session pass to verify
- updating the Fed target constants from market reaction alone — wait for the actual FOMC statement and dot plot
- running the dashboard with degraded validation and ignoring the warnings
