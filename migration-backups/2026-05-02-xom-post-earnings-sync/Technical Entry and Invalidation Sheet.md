# Technical Entry and Invalidation Sheet

## Purpose

Convert the model portfolio from abstract holdings into execution-aware candidates.

This is not a live order sheet. It is the technical discipline layer.

Script-backed prep path:
- default to `python scripts/run_finance_refresh_chain.py morning` for weekday session-readiness refreshes
- use `python scripts/technical_refresh.py` directly only for narrow technical validation or debugging
- run `python scripts/market_state_refresh.py` when macro-linked setups, especially energy and rates-sensitive names, may need context
- run `python scripts/deployment_check.py` after both refresh scripts when you want a quick ranked action-state summary
- run `python scripts/apply_band_update.py` after the morning chain when band-staleness warnings are active

## Precision refresh, as of 2026-04-27 close

### Readiness scale
- **Ready now:** structure and thesis aligned, price inside band
- **Close:** thesis intact, but entry should improve (extended above band)
- **Bench / patience:** thesis is fine, chart is not yet paying us to be early
- **Repair / do not touch:** structure broken, prior setup invalidated
- **Blocked:** earnings or other catalyst risk overrides the technical read

---

### ETN
- Close: **416.77**
- 20 / 50 / 200-day: **392.26 / 375.80 / 360.07**
- MA posture: **above all three MAs with a bullish 20 > 50 > 200 stack**. Cleanest chart in the sheet.
- Support: **392** (20-day), then **376** (50-day)
- Resistance: **427** (recent intraday high)
- Preferred entry band: **386.28 to 410.19** (band updated 2026-04-28, MA-anchored)
- Explicit stop: **374.33**
- Invalidation logic: loses the 20-day cluster and breaks back into the prior range under 374.
- Stance: **Almost deployable**, only on disciplined pullback into band.
- Entry-distance context: **+$6.58 / +1.6% above the top of the preferred band**, so close to disciplined entry.
- **Recent history:** Price was last in the 386–410 band during the early-April selloff (Apr 4–10). The trend has held above the band for ~10 trading days. Latest band update narrowed the gap from ~7% extended to ~1.6% extended — a meaningful improvement in entry asymmetry.
- ⚠️ **EARNINGS — May 5 (CONFIRMED via Eaton IR).** Window closes within 7 days. Any pullback into band before May 5 must be sized smaller than normal because gap-down risk is unhedged.

---

### JPM
- Close: **311.63**
- 20 / 50 / 200-day: **305.43 / 298.12 / 301.68**
- MA posture: **above all three MAs**. Constructive trend, mildly extended above the preferred pullback zone.
- Support: **305** (20-day), then **301** (200-day)
- Resistance: **315**, then **325**
- Preferred entry band: **300 to 306** (within tolerance — not flagged for revision)
- Explicit stop: **295.50**
- Invalidation logic: loses the 200-day and the higher-low structure together.
- Stance: **Almost deployable**, high-quality setup, smallest gap to band in the sheet.
- Entry-distance context: **+$5.63 / +1.84% above the top of the preferred band**, so a normal pullback brings price into discipline.
- **Recent history:** JPM crossed above the 300–306 band on Apr 14 following the Q1 2026 beat (ROTCE 23%, but full-year NII guide trimmed from $104.5B to $103B). It has been above the band for ~8 trading days. Closest active name to a clean disciplined entry.
- Earnings: **July 14 (Q2 2026)** — no near-term earnings risk. This is the cleanest "thesis-intact, just wait for entry" name in the universe.

---

### NVDA
- Close: **216.61**
- 20 / 50 / 200-day: **190.84 / 185.62 / 183.09**
- MA posture: **above all three MAs with a bullish 20 > 50 > 200 stack**. AI leadership intact but tightly clustered MAs argue for pullback discipline.
- Support: **191** (20-day), then **183–185** (MA cluster)
- Resistance: **218** (intraday high)
- Preferred entry band: **188.03 to 199.28** (band updated 2026-04-28)
- Explicit stop: **182.40**
- Invalidation logic: loses the MA cluster and slips back under the recent breakout zone.
- Stance: **Almost deployable**, only on pullback. Do not chase a fresh high print.
- Entry-distance context: **+$17.33 / +8.7% above the top of the preferred band**, so this remains a pullback-only setup.
- **Recent history:** NVDA closed +4.0% on Apr 27 to 216.61, extending well above the entry zone. The MA cluster at 183–191 remains the anchor — a pullback to the cluster without breaching 182 would bring price back into band. Chip-sector RSI reportedly above 80 — overbought.
- Earnings: **May 20 (DATE CHANGED — vault had May 27, yfinance now shows May 20).** Verify against NVIDIA IR before treating timing as confirmed.

---

### GOOG
- Close: **348.52**
- 20 / 50 / 200-day: **319.32 / 309.28 / 277.38**
- MA posture: **above all three MAs with a bullish 20 > 50 > 200 stack**. Trend remains constructive.
- Support: **319** (20-day), then **309** (50-day)
- Resistance: **350**, then prior high
- Preferred entry band: **315.41 to 331.05** (band updated 2026-04-28)
- Explicit stop: **307.59**
- Invalidation logic: loses the breakout shelf and falls back under the 50-day.
- Stance: **Blocked**, attractive but not worth forcing ahead of earnings.
- Entry-distance context: **+$17.47 / +5.3% above the top of the preferred band**, still meaningfully extended.
- **Recent history:** Price was last in the 315–331 band approximately mid-March during the pre-rally consolidation. The 20-day MA at 319 sits at the bottom of the preferred band — that is constructive, but the current price is still 5%+ above where disciplined entry begins.
- ⚠️ **EARNINGS — April 29, after close.** Do not add before the print. Reassess entry zone and stop post-earnings.

---

### MSFT
- Close: **424.82**
- 20 / 50 / 200-day: **395.37 / 394.46 / 468.29**
- MA posture: **above 20 and 50-day, still below 200-day**. Recovery intact, long-term repair still incomplete.
- Support: **395–394** (20/50 cluster), then **378**
- Resistance: **433**, then **468** (200-day)
- Preferred entry band: **389.64 to 412.56** (band updated 2026-04-28)
- Explicit stop: **378.18**
- Invalidation logic: loses the 50-day recovery zone and fails to reclaim it quickly.
- Stance: **Blocked**, still close on chart quality but not actionable ahead of earnings.
- Entry-distance context: **+$12.26 / +3.0% above the top of the preferred band**, so still extended versus disciplined entry.
- **Recent history:** Price was last in the 389–412 band during the early-April selloff (Apr 7–10). The recovery has kept price above the band for ~10 trading days. MSFT is the only tracked name still trading below its 200-day MA — a structural weakness in an otherwise strong market. Watch the post-earnings reaction closely.
- ⚠️ **EARNINGS — April 29, after close.** Do not add before the print. A failure to rally on a beat would be a structural signal.

---

### AMZN
- Close: **261.12**
- 20 / 50 / 200-day: **236.04 / 219.87 / 226.60**
- MA posture: **above all three MAs**. Trend is constructive.
- Support: **236** (20-day), then **227** (200-day)
- Resistance: prior highs (confirm via chart)
- Preferred entry band: **232.44 to 246.82** (band INITIALIZED 2026-04-28 from prior null state)
- Explicit stop: **225.25**
- Invalidation logic: loses the 200-day and fails to recover.
- Stance: **Blocked**, strong posture but earnings tomorrow.
- Entry-distance context: **+$14.30 / +5.8% above the top of the preferred band**, so extended.
- **Recent history:** AMZN recovered from tariff-shock lows near 175–180 (early to mid-April) to the current 261 range — roughly a 45% recovery in 2–3 weeks. Band is now formally defined for the first time. Post-Apr-29 earnings is the first decision gate.
- ⚠️ **EARNINGS — April 29, after close.** Do not add before the print. Post-earnings re-evaluation will determine if the new band holds or needs reset.

---

### VRT
- Close: **322.43**
- 20 / 50 / 200-day: **290.15 / 269.72 / 188.09**
- MA posture: **above all three MAs with a bullish 20 > 50 > 200 stack**. Clean leadership structure.
- Support: **290** (20-day), then **270** (50-day)
- Resistance: confirm via chart
- Preferred entry band: **283.12 to 311.22** (band INITIALIZED 2026-04-28 from prior null state)
- Explicit stop: **269.07**
- Invalidation logic: loses the 20-day and breaks the uptrend structure.
- Stance: **Almost deployable** — thesis confirmed by Apr 22 beat-and-raise, but extended above newly-defined band.
- Entry-distance context: **+$11.21 / +3.6% above the top of the preferred band**.
- **Recent history:** Reported Q1 2026 on Apr 22 — beat-and-raise confirmed AI power-demand thesis. Price has been extended above the new 311 band since the print. ETN remains the priority first; VRT is the secondary AI-power name.
- Earnings: **April 22 (REPORTED).** Q2 print not yet on calendar.

---

### CAT
- Close: **828.79**
- 20 / 50 / 200-day: **771.22 / 741.99 / 579.81**
- MA posture: **above all three MAs with a bullish 20 > 50 > 200 stack**.
- Support: **771** (20-day), then **742** (50-day)
- Resistance: prior high
- Preferred entry band: **759.77 to 805.57** (band INITIALIZED 2026-04-28 from prior null state)
- Explicit stop: **736.87**
- Invalidation logic: loses the 50-day and breaks the uptrend.
- Stance: **Almost deployable** — under active review until earnings clear.
- Entry-distance context: **+$23.22 / +2.9% above the top of the preferred band**.
- **Recent history:** Newly added to the tracked universe with formal band. Earnings April 30 is the first decision gate. A beat on industrial demand would strengthen the ETN/industrials thesis; a miss would create read-through risk for ETN's power/electrification setup.
- ⚠️ **EARNINGS — April 30.** Treat as timing-sensitive. No pre-print add.

---

### GS
- Close: **937.81**
- 20 / 50 / 200-day: **897.47 / 869.45 / 821.03**
- MA posture: **above all three MAs with a bullish 20 > 50 > 200 stack**.
- Support: **897** (20-day), then **869** (50-day)
- Resistance: prior high
- Preferred entry band: **878.71 to 926.76** (within tolerance — not flagged for revision)
- Explicit stop: **854.68**
- Invalidation logic: loses the 50-day and breaks the uptrend.
- Stance: **Almost deployable** — newly added, under active review.
- Entry-distance context: **+$11.05 / +1.2% above the top of the preferred band** — second-closest name to disciplined entry after JPM.
- Earnings: **July 14 (Q2 2026)** — no near-term earnings risk. Date is newly added to vault calendar; cross-check before treating as confirmed.

---

### BRK.B
- Close: **472.81**
- 20 / 50 / 200-day: **475.46 / 484.41 / 489.87**
- MA posture: **below all three MAs**. Ballast profile intact, chart still in repair.
- Support: **464**
- Resistance: **481**, then **488**
- Preferred entry band: **465 to 472** (within tolerance — not flagged)
- Explicit stop: **459.50**
- Invalidation logic: loses 464 and confirms continued relative weakness.
- Stance: **Bench / do not touch**, even though price is right at the top of band the MA structure overrides band location.
- Entry-distance context: **at the top of the preferred band**, but the weak MA structure means this is band-location-without-MA-support.
- **Recent history:** BRK.B exited the band on the 2026-04-27 dashboard delta (was in band, now at top edge). All three MAs (475 / 484 / 490) sit above price — entering here is entering into MA resistance, not into clean trend support.
- ⚠️ **EARNINGS — May 2 (DATE CHANGED — vault had May 4, yfinance shows May 2).** Verify before relying on timing.

---

### XOM
- Close: **148.19**
- 20 / 50 / 200-day: **154.81 / 154.50 / 125.91**
- MA posture: **above 200-day, below 20 and 50-day**. Long-term uptrend intact, intermediate momentum broken.
- Support: **141.97**
- Resistance: **154–155** (20/50 cluster)
- Preferred entry band: **NOT YET DEFINED** — requalify only above 141.97 with reclaim of the 50-day in supportive energy context
- Explicit stop: **139.50**
- Invalidation logic: loses 141.97 and confirms a failed support retest.
- Stance: **Bench / do not touch**, needs both oil structure and price stabilization first.
- Entry-distance context: **inside the prior reference zone (142–148)**, but posture too weak for that to be deployable.
- **Recent history:** WTI has rallied from $84 (Apr 17) to $97 (Apr 27) on Hormuz re-disruption. XOM's earnings quality on May 1 will be much better than when the repair call was made — but the chart hasn't followed yet. The May 1 print is the requalification gate.
- ⚠️ **EARNINGS — May 1.** Critical. Watch realized oil pricing, Q2 guidance, and tone after the post-ceasefire-then-renewed-disruption oil whipsaw.

---

### LMT
- Close: **513.35**
- 20 / 50 / 200-day: **594.12 / 625.58 / 518.97**
- MA posture: **below all three MAs**. The chart is broken — price is below every major MA.
- Support: confirm fresh support only after a new base forms
- Resistance: **581** (200-day), then **594** (20-day)
- Preferred entry band: **NOT YET DEFINED** — post-earnings rebuild only
- Explicit stop: **581.50** (the prior band's stop, kept as a reference for the level price must reclaim)
- Invalidation logic: prior setup already failed; no new long thesis trigger until price rebuilds support and reclaims key MAs.
- Stance: **Repair mode / do not touch**.
- Entry-distance context: **far below the prior band and below the prior stop** — prior setup fully invalidated.
- **Recent history:** Q1 2026 print on April 23 dropped price ~$82 (~14%) in a single session. Price is now ~5 trading days post-event. A new base requires 4–6 weeks of stabilization above 509. **Earnings date:** vault originally had April 23 (now elapsed); yfinance now shows **July 21** for Q2 2026.

---

### RTX
- Close: **173.38**
- 20 / 50 / 200-day: **193.06 / 198.48 / 177.40**
- MA posture: **below all three MAs**. Below the 200-day — structural weakness.
- Support: weak; needs to reclaim 185 area first
- Resistance: **177** (200-day), then **193–198** (20/50 cluster)
- Preferred entry band: **190.33 to 201.25** (band updated 2026-04-28, mechanically)
- Explicit stop: **184.87**
- Invalidation logic: name is below stop and below band — prior setup fully invalidated.
- Stance: **Below stop / do not touch**. Band update is mechanical only — actual setup is in repair.
- Entry-distance context: **-$16.95 / -8.9% below the bottom of the preferred band**.
- **Recent history:** Q1 2026 print on April 21 was a beat-and-raise per company materials, but the stock reaction was not clean enough to treat as a setup upgrade. Now well below all MAs and below the explicit stop. Same repair logic as LMT applies — the prior setup is invalidated regardless of fundamentals. **Earnings:** July 21 (Q2 2026).

---

## Freshness and refresh policy

- Last updated: **2026-04-28** — full precision refresh against 2026-04-27 close. Bands updated for ETN, GOOG, MSFT, NVDA, AMZN, VRT, RTX, CAT (8 names) via `apply_band_update.py`. AMZN, VRT, CAT bands formally defined for the first time. RTX, GS added as tracked names.
- Data as of: scripted technical refresh covering the **2026-04-27 close**
- Refresh cadence: each weekday for tracked names, plus extra refreshes before key earnings, after material breaks of support or resistance, or after moves large enough to change entry quality
- Next refresh due: post-FOMC (April 29) and post-earnings cluster (GOOG/MSFT/AMZN April 29; CAT April 30; XOM May 1)
- Refresh policy: refresh tracked-name close, moving averages, posture, and entry-distance context each weekday. Only rewrite support, resistance, stance, or invalidation language when evidence materially changed, so the sheet stays current without turning noisy.

## Current ranking after precision pass

1. **JPM** — closest to band (1.8% extended), thesis intact, no near-term earnings risk
2. **GS** — second closest (1.2% extended), but newly added — verify thesis depth before treating as core
3. **ETN** — cleanest chart, 1.6% extended, but earnings May 5 caps any pre-print sizing
4. **CAT** — 2.9% extended, but earnings April 30 — wait for print
5. **MSFT** — 3.0% extended, earnings tomorrow — blocked
6. **VRT** — 3.6% extended, post-earnings setup, no near-term print
7. **GOOG** — 5.3% extended, earnings tomorrow — blocked
8. **AMZN** — 5.8% extended, earnings tomorrow — blocked
9. **NVDA** — 8.7% extended, earnings May 20, also overbought
10. **BRK.B** — at band but MA structure broken
11. **XOM** — at prior reference zone but MA structure broken; May 1 earnings is gate
12. **RTX** — below stop and below band — repair mode
13. **LMT** — far below stop — repair mode

## Data-quality note

- Daily OHLC data is refreshed from the scripted pipeline and should now be treated as a weekday-maintained surface for tracked names.
- This sheet is based on the latest available closing data in the refresh chain. It is precise at the daily level, not intraday.
- Support and resistance were left unchanged unless prior levels appeared materially breached or clearly superseded by new structure.
- Bands updated 2026-04-28 are MA20-anchored mechanical proposals. They confirm the existing structural framing rather than chase price — the largest single-band shift was 4 dollars.
- **Confidence is downgraded to usable-with-caution, not clean-deployable.** Dashboard validation is warning-level (4 warnings: band-drift, timing-sensitive earnings, VRT-earnings-in-past, macro-manual-dependency).
- **Market-state context is fresh, but it carries manual and mixed-date caveats:** Fed target range is hardcoded as of 2026-04-19, FedWatch cut probability is not wired, and rates series are not fully aligned to the same trading day.
- **Do not treat any setup in this sheet as deployable now solely from this refresh pass.** Use the action-state note and direct catalyst confirmation before any real decision.
- **BRK.B** has symbol-format caveats on some public sites. Cross-site screenshots may still show symbol formatting inconsistently.

## Bottom line

- **Closest to disciplined entry now:** JPM (+1.8%) and GS (+1.2%) — both no near-term earnings risk
- **Best chart, earnings-capped:** ETN (+1.6% to band, May 5 earnings)
- **Earnings cluster blocking action:** AMZN, GOOG, MSFT (April 29), CAT (April 30), XOM (May 1), BRK.B (May 2), ETN (May 5)
- **Need patience before clean entries:** NVDA (8.7% extended, overbought), VRT (3.6%, fresh post-earnings)
- **Repair mode — do not touch:** LMT (below stop, broken structure), RTX (below stop, broken structure), BRK.B (at band but MAs broken), XOM (sub-MA, awaits May 1)
- **Confidence:** usable with caution — 4 active dashboard warnings, all known and documented
- **Operating directive:** No new entries in the open without a pre-set limit at a defined band level. Earnings cluster is the dominant near-term variable. FOMC April 29 is a parallel macro variable.
