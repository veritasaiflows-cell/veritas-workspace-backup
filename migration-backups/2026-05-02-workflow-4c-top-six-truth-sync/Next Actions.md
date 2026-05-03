# Next Actions

## Role

This dashboard answers one question:
- what should Randall do next?

Boundary:
- this is the immediate action queue
- point to the right source notes instead of restating them
- keep it to the next few concrete moves, not full weekly analysis or doctrine

## Current best next actions (as of 2026-04-28)

1. **Stand down through the April 29 catalyst window**
   - **FOMC decision + GOOG/MSFT/AMZN earnings on the same day.** Do not pre-position.
   - Use [[03. Portfolio/Deployment Trigger Sheet]] and [[03. Portfolio/Technical Entry and Invalidation Sheet]] as the gate before any action.
   - Hold all earnings-blocked names blocked. No exceptions.

2. **Watch JPM and GS for any pullback into band**
   - **JPM** at 311.63, band 300–306 — closest active candidate, +1.8% extended
   - **GS** at 937.81, band 879–927 — second-closest, +1.2% extended (newly added — verify thesis depth before treating as core)
   - Neither has near-term earnings risk (both Q2 prints in mid-July)
   - These are the two cleanest "thesis-intact, just wait for entry" names in the universe

3. **Treat ETN as pullback-only with explicit earnings awareness**
   - At 416.77, band 386–410. The May 5 earnings window is live.
   - Do not enter above band under any circumstances. If price pulls into band before May 5, size smaller than normal because gap-down risk is unhedged.

4. **Keep NVDA in pullback-only mode, overbought**
   - At 216.61, band 188–199, +8.7% extended. Chip-sector RSI reportedly above 80.
   - Pullback to MA cluster (183–191) is the only valid entry trigger.
   - Verify the May 20 earnings date against NVIDIA IR (vault had May 27).

5. **Run `post_earnings_prep.py` after every major print this week**
   - GOOG, MSFT, AMZN (April 29) — review packets, decide band confirm/reset/widen
   - CAT (April 30), XOM (May 1), CVX (May 1), BRK.B (May 2), ETN (May 5)
   - Use the structured packet as the input to the note layer; do not free-write interpretation

6. **Keep LMT and RTX in repair mode**
   - Both below stop. Both prior setups invalidated.
   - No pre-base entries. Reassess only when a new support base forms.
   - LMT date corrected: yfinance shows July 21 for Q2 2026 (vault had April 23 elapsed).

7. **Update Fed target constants the morning after April 29 FOMC**
   - Edit `FED_TARGET_LOW`, `FED_TARGET_HIGH`, `FED_TARGET_DATE` in `scripts/market_state_refresh.py`
   - Re-run morning chain so all downstream artifacts pick up the update

8. **Confirm timing-sensitive earnings dates with IR**
   - NVDA: yfinance shows May 20 (vault had May 27)
   - BRK.B: yfinance shows May 2 (vault had May 4)
   - LMT: vault had April 23 (elapsed); yfinance shows July 21
   - These need direct confirmation before any timing-sensitive deployment decision

## If there are only 15 minutes

Do one of these, not five:
- read [[01. Dashboards/Pre-Market Snapshot]] (auto-generated each morning) and act on or dismiss the closest-to-band signal
- read [[01. Dashboards/Daily Executive Summary]] (auto-generated each post-close) and absorb the day's deltas
- check `tmp/dashboard-validation.json` for any new critical warnings
- update one entry-distance line in [[03. Portfolio/Technical Entry and Invalidation Sheet]]

## If there is a full focused session

Work in this order:
1. [[01. Dashboards/Daily Executive Summary]] (today's auto-brief — verify or refine)
2. [[05. Intelligence/Weekly Intelligence Brief]] (current week's section, judgment slots)
3. [[03. Portfolio/Technical Entry and Invalidation Sheet]]
4. [[03. Portfolio/Portfolio Snapshot]]
5. [[02. Markets/Watchlist]]
6. [[02. Markets/Macro Regime Dashboard]]
7. [[07. Risk/Risk Rules]]

## Anti-drift rule

If a task does not improve market understanding, watchlist quality, portfolio discipline, risk awareness, or decision clarity, it is probably not the best next action.

## Last updated

- 2026-04-28 — full refresh against 2026-04-27 close. Updated to reflect: CAT/GS/VRT now ALMOST DEPLOYABLE (no longer benched); RTX below-stop; band updates applied for 8 names; new auto-generated dashboard surfaces (Pre-Market, Post-Market, Daily Exec Brief) now in the operating loop.
