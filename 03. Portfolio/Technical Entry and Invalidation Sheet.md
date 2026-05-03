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

> **2026-05-02 targeted trust-hardening note:** the **ETN, JPM, NVDA, XOM, GOOG, and MSFT** sections below were selectively re-synced after the May 1 close, band update, and explicit post-earnings revalidation. The **BRK.B, AMZN, VRT, CAT, LMT, and RTX** sections also had their core technical fields and approved band / stop lines refreshed to the **2026-05-01** artifact layer. `AMZN`, `CAT`, and `RTX` are now event-watch names with retained technical upkeep rather than execution-board names. Unless a section says otherwise, the rest of this sheet still reflects the 2026-04-27 precision pass.

### Readiness scale
- **Ready now:** structure and thesis aligned, price inside band
- **Close:** thesis intact, but entry should improve (extended above band)
- **Bench / patience:** thesis is fine, chart is not yet paying us to be early
- **Repair / do not touch:** structure broken, prior setup invalidated
- **Blocked:** earnings or other catalyst risk overrides the technical read

---

### ETN
- Close: **425.55** *(targeted trust-hardening sync; 2026-05-01 close)*
- 20 / 50 / 200-day: **404.99 / 378.77 / 361.32**
- MA posture: **above all three MAs with a bullish 20 > 50 > 200 stack**. Still the cleanest chart in the sheet.
- Support: **405** (20-day), then **379** (50-day)
- Resistance: **425–426** (recent high / current extension zone)
- Preferred entry band: **395.59 to 420.31** (refreshed band)
- Explicit stop: **383.23**
- Invalidation logic: loses the 20-day cluster and breaks back below 383.23.
- Stance: **Almost deployable**. Best chart in the universe, but still above the preferred zone.
- Entry-distance context: **+$5.24 / +1.25% above the top of the preferred band**.
- **Recent history:** the band update improved the entry asymmetry materially, but price is still extended into a May 5 earnings window. This remains a disciplined pullback case, not a chase.
- ⚠️ **EARNINGS — May 5.** Even if price dips into band before the print, keep pre-event sizing smaller than normal.

---

### JPM
- Close: **312.47** *(targeted trust-hardening sync; 2026-05-01 close)*
- 20 / 50 / 200-day: **309.65 / 298.64 / 302.25**
- MA posture: **above all three MAs**. Constructive trend, now inside the refreshed entry zone.
- Support: **309** (20-day), then **302** (200-day)
- Resistance: **318** (top of refreshed band), then **325**
- Preferred entry band: **306.82 to 318.12** (refreshed band)
- Explicit stop: **301.17**
- Invalidation logic: loses 301.17 and the 200-day / higher-low structure together.
- Stance: **Deployable now**, but still cleaner on support than on forced size.
- Entry-distance context: **inside the preferred band**.
- **Recent history:** the refreshed band moved JPM from pullback-only into live in-band status without changing the underlying judgment that this is a high-quality, discipline-first setup.
- Earnings: **July 14 (Q2 2026)** — no near-term earnings risk.

---

### NVDA
- Close: **198.45** *(targeted trust-hardening sync; 2026-05-01 close)*
- 20 / 50 / 200-day: **197.22 / 187.15 / 183.84**
- MA posture: **above all three MAs with a bullish 20 > 50 > 200 stack**. AI leadership intact, but crowding still matters.
- Support: **197** (20-day), then **187–184** (50-day / 200-day cluster)
- Resistance: **199.28** (top of band), then the recent higher-high zone
- Preferred entry band: **188.03 to 199.28**
- Explicit stop: **182.40**
- Invalidation logic: loses 182.40 and the MA cluster, then slips back under the breakout zone.
- Stance: **Deployable now**, but only with disciplined size and no momentum-chase framing.
- Entry-distance context: **inside the preferred band**.
- **Recent history:** the latest pullback brought NVDA back into the written band after the earlier extension. That improves entry location, but not enough to ignore crowding or concentration rules.
- Earnings: **May 20 (DATE CHANGED — vault had May 27, yfinance now shows May 20).** Verify against NVIDIA IR before treating timing as confirmed. If a clean primary confirmation still has not landed by the first post-close chain on **2026-05-13**, keep the date explicitly tagged unconfirmed and do not let downstream notes speak as if it were primary-confirmed.

---

### GOOG
- Close: **383.22** *(targeted post-earnings sync; 2026-05-01 close)*
- 20 / 50 / 200-day: **334.85 / 314.17 / 281.03**
- MA posture: **above all three MAs with a bullish 20 > 50 > 200 stack**. Trend strengthened after the print.
- Support: **349** (top of the written band / post-print hold zone), then **335** (20-day)
- Resistance: **384**, then fresh post-print highs
- Preferred entry band: **330.01 to 349.37** (post-print working band from the live trigger layer)
- Explicit stop: **320.33**
- Invalidation logic: loses the post-print breakout shelf and falls back under the 20-day / band support zone.
- Stance: **Almost deployable**, but only on pullback / revalidation into the written band.
- Entry-distance context: **+$33.85 / +9.7% above the top of the preferred band** — materially extended.
- **Post-earnings read:** Alphabet's Apr 29 report was thesis-confirming. Search stayed strong and Google Cloud accelerated to **+63%**, but the stock already moved about **10%** above the pre-print close by the May 1 close. Better business read, worse entry location.
- **What matters now:** this is no longer an earnings-block case. It is an entry-discipline case. Do not chase strength far above the written band.

---

### MSFT
- Close: **414.44** *(targeted post-earnings sync; 2026-05-01 close)*
- 20 / 50 / 200-day: **405.57 / 396.11 / 466.64**
- MA posture: **above the 20-day and 50-day, still below the 200-day**. Recovery intact, long-term repair still incomplete.
- Support: **406–396** (20/50 cluster), then **378**
- Resistance: **414–415** (current area), then **467** (200-day)
- Preferred entry band: **389.64 to 412.56** (still the working post-print band)
- Explicit stop: **378.18**
- Invalidation logic: loses the recovery structure and fails back through the 50-day / band zone.
- Stance: **Almost deployable**, but still needs either a cleaner pullback into band or stronger repair through the 200-day.
- Entry-distance context: **+$1.88 / +0.5% above the top of the preferred band** — only mildly extended, but not quite ideal.
- **Post-earnings read:** Microsoft's Apr 29 report was operationally strong. Azure grew **40%** and management said the AI business surpassed a **$37B annual revenue run rate**, but the stock's first reaction was weaker than GOOG's and the 200-day remains a real structural overhang.
- **What matters now:** the earnings blocker is gone. The remaining issue is technical repair quality, not unresolved catalyst risk.

---

### AMZN
- Close: **268.26** *(band-sync refresh; 2026-05-01 close)*
- 20 / 50 / 200-day: **247.37 / 224.80 / 227.38**
- MA posture: **above all three MAs**. Trend is constructive.
- Support: **247** (20-day), then **227** (200-day)
- Resistance: prior highs (confirm via chart)
- Preferred entry band: **243.59 to 258.71** (band updated 2026-05-01)
- Explicit stop: **236.03**
- Invalidation logic: loses the 200-day and fails to recover.
- Stance: **Watch-only / bench**. Broad quality is intact, but this remains a secondary large-cap platform read rather than a daily execution-board candidate.
- Entry-distance context: **+$9.55 / +3.7% above the top of the preferred band**.
- **Recent history:** AMZN recovered from tariff-shock lows near 175–180 (early to mid-April) to the current 268 range. The earnings blocker is gone; the remaining issue is whether price can hold or retest the refreshed band without giving back the post-print move.
- **Lane note:** keep AMZN technically visible for post-earnings follow-through, but it no longer owns weekday deployment-board cost while GOOG and MSFT already cover the large-cap quality sleeve.
- Earnings: **July 30 (Q2 2026 per yfinance; treat as provisional until company IR confirms).**

---

### VRT
- Close: **328.31** *(band-sync refresh; 2026-05-01 close)*
- 20 / 50 / 200-day: **303.28 / 275.80 / 191.93**
- MA posture: **above all three MAs with a bullish 20 > 50 > 200 stack**. Clean leadership structure.
- Support: **303** (20-day), then **276** (50-day)
- Resistance: confirm via chart
- Preferred entry band: **295.49 to 326.63** (band updated 2026-05-01)
- Explicit stop: **279.92**
- Invalidation logic: loses the 20-day and breaks the uptrend structure.
- Stance: **Almost deployable** — thesis confirmed by Apr 22 beat-and-raise, but extended above newly-defined band.
- Entry-distance context: **+$1.68 / +0.5% above the top of the preferred band**.
- **Recent history:** Reported Q1 2026 on Apr 22 — beat-and-raise confirmed AI power-demand thesis. The refreshed band has nearly caught up to price, but ETN remains the priority first and VRT is still the secondary AI-power name.
- Earnings: **July 29 (Q2 2026 per yfinance; treat as provisional until company IR confirms).**

---

### CAT
- Close: **889.67** *(band-sync refresh; 2026-05-01 close)*
- 20 / 50 / 200-day: **800.70 / 749.23 / 588.79**
- MA posture: **above all three MAs with a bullish 20 > 50 > 200 stack**.
- Support: **801** (20-day), then **749** (50-day)
- Resistance: prior high
- Preferred entry band: **787.41 to 840.59** (band updated 2026-05-01)
- Explicit stop: **760.82**
- Invalidation logic: loses the 50-day and breaks the uptrend.
- Stance: **Watch-only / post-print monitor**. The industrial read-through is useful, but ETN remains the primary execution name for this sleeve.
- Entry-distance context: **+$49.08 / +5.8% above the top of the preferred band**.
- **Recent history:** Newly added to the tracked universe with a refreshed band after the Apr 30 print. Industrial-demand read-through still matters for the ETN/industrials sleeve, but the current setup remains extended enough that patience is still the cleaner posture.
- **Lane note:** CAT keeps technical visibility for post-print follow-through and sector read-through, but it no longer earns weekday execution-board ownership.
- Earnings: **April 30 (reported; next date has not rolled forward cleanly yet).**

---

### GS
- Close: **923.71** *(targeted GS sync; 2026-05-01 close)*
- 20 / 50 / 200-day: **912.61 / 869.99 / 825.50**
- MA posture: **above all three MAs with a bullish 20 > 50 > 200 stack**.
- Support: **913** (20-day), then **870** (50-day)
- Resistance: **926.76** (top of preferred band), then prior high
- Preferred entry band: **878.71 to 926.76**
- Explicit stop: **854.68**
- Invalidation logic: loses the 50-day and breaks the uptrend.
- Stance: **Deployable now**, but only as a disciplined tactical secondary versus JPM rather than a default primary bank add.
- Entry-distance context: **inside the preferred band**.
- **Recent history:** the band and stop are now explicit, which clears the old WATCH-state mismatch. That improves execution ownership enough for decision-grade status, but not enough to outrank JPM or justify chasing strength above the written zone.
- Earnings: **July 14 (Q2 2026)** — no near-term earnings risk. Date is newly added to vault calendar; cross-check before treating as confirmed.

---

### BRK.B
- Close: **473.01** *(band-sync refresh; 2026-05-01 close)*
- 20 / 50 / 200-day: **474.98 / 482.48 / 489.90**
- MA posture: **below all three MAs**. Ballast profile intact, chart still in repair.
- Support: **472**
- Resistance: **475**, then **482**
- Preferred entry band: **471.93 to 484.15** (band updated 2026-05-01)
- Explicit stop: **465.81**
- Invalidation logic: loses 464 and confirms continued relative weakness.
- Stance: **Bench / do not touch**, even though price is right at the top of band the MA structure overrides band location.
- Entry-distance context: **inside the preferred band**, but the weak MA structure still means this is band-location-without-MA-support.
- **Recent history:** BRK.B is back inside the refreshed band, but all three MAs still sit above price — entering here is still entering into MA resistance, not into clean trend support.
- ⚠️ **EARNINGS — Reported May 2** *(same-day timing now aligns across yfinance and Berkshire's homepage, but the next-quarter date is not yet rolled cleanly in the machine layer; keep the catalyst in post-earnings cleanup state rather than treating May 2 as a fresh upcoming date).*

---

### XOM
- Close: **152.75** *(targeted post-earnings sync; 2026-05-01 close)*
- 20 / 50 / 200-day: **152.29 / 154.82 / 126.75**
- MA posture: **above the 20-day and 200-day, below the 50-day**. Better than the late-April repair low, but still not a clean trend reclaim.
- Support: **150.24** (bottom of refreshed band), then **146.14** (stop)
- Resistance: **154.82** (50-day), then **158.44** (top of refreshed band)
- Preferred entry band: **150.24 to 158.44** (band updated 2026-05-01)
- Explicit stop: **146.14**
- Invalidation logic: loses the refreshed band and fails back below 146.14, or fails another 50-day reclaim with oil context rolling over.
- Stance: **Bench / do not touch**. Price is in band, but the setup is still not decision-grade enough to promote out of repair.
- Entry-distance context: **inside the preferred band** — location improved, but band location alone is not enough while follow-through and production visibility are still noisy.
- **Post-earnings read:** the quarter was stronger than the GAAP headline implied. Exxon reported **$4.2B / $1.00 EPS** GAAP, but **$8.8B / $2.09 EPS** excluding identified items and timing effects. Guyana and the Permian stayed strong, but Hormuz disruption and LNG repair uncertainty still dominate the near-term risk map.
- **What matters now:** keep the name benched until price can reclaim and hold the 50-day with supportive energy tape, and until the next one to two EIA reads plus shipping follow-through reduce the current binary.

---

### LMT
- Close: **512.77** *(band-sync refresh; 2026-05-01 close)*
- 20 / 50 / 200-day: **574.59 / 614.54 / 520.01**
- MA posture: **below all three MAs**. The chart is broken — price is below every major MA.
- Support: confirm fresh support only after a new base forms
- Resistance: **520** (200-day), then **575** (20-day)
- Preferred entry band: **566.46 to 598.98** (band updated 2026-05-01; mechanical reference only, not a live setup)
- Explicit stop: **550.20** (the prior band's stop, kept as a reference for the level price must reclaim)
- Invalidation logic: prior setup already failed; no new long thesis trigger until price rebuilds support and reclaims key MAs.
- Stance: **Repair mode / do not touch**.
- Entry-distance context: **-$53.69 / -9.5% below the bottom of the reference band** and still below the refreshed stop.
- **Recent history:** Q1 2026 print on April 23 dropped price roughly 14% in a single session. A refreshed reference band exists now, but it is still only a measurement aid — a real long setup still requires 4–6 weeks of stabilization and multiple MA reclaims. **Earnings date:** yfinance now shows **July 21** for Q2 2026.

---

### RTX
- Close: **173.99** *(band-sync refresh; 2026-05-01 close)*
- 20 / 50 / 200-day: **189.44 / 196.23 / 177.95**
- MA posture: **below all three MAs**. Below the 200-day — structural weakness.
- Support: weak; needs to reclaim 185 area first
- Resistance: **178** (200-day), then **189–196** (20/50 cluster)
- Preferred entry band: **186.76 to 197.48** (band updated 2026-05-01, mechanically)
- Explicit stop: **181.40**
- Invalidation logic: name is below stop and below band — prior setup fully invalidated.
- Stance: **Watch-only / repair**. Still below stop and below band; this remains a repair monitor rather than an execution-board candidate.
- Entry-distance context: **-$12.77 / -6.8% below the bottom of the preferred band**.
- **Recent history:** Q1 2026 print on April 21 was a beat-and-raise per company materials, but the stock reaction was not clean enough to treat as a setup upgrade. Now well below all MAs and below the explicit stop. Same repair logic as LMT applies — the prior setup is invalidated regardless of fundamentals. **Earnings:** July 21 (Q2 2026).
- **Lane note:** RTX stays tracked for defense-sector read-through and possible later repair, but not for default weekday deployment upkeep.

---

## Watch-lane technical coverage

> **2026-05-02 bounded parity note:** the four sections below were added to close workbook / note parity for machine-tracked watch-lane names. They are **not** execution-board promotions and should not be read as daily deployment candidates.

### CVX
- Close: **190.63** *(manual watch-lane parity pass; 2026-05-01 close)*
- 20 / 50 / 200-day: **189.29 / 192.94 / 164.49**
- MA posture: **above the 20-day and 200-day, still below the 50-day**. Better than a broken chart, not a clean trend reclaim.
- Support: **189** (20-day), then **186.91** (bottom of preferred band)
- Resistance: **193** (50-day), then **196.41** (top of preferred band)
- Preferred entry band: **186.91 to 196.41** (band updated 2026-05-01)
- Explicit stop: **182.16**
- Invalidation logic: loses 182.16 and breaks back below the band / 20-day support cluster.
- Stance: **Watch-only / bench**. Price is inside the preferred band, but this remains a secondary energy read-through name and is **not** on the execution board.
- Entry-distance context: **inside the preferred band**.
- **Lane note:** use CVX for oil-major read-through versus XOM, not as a hidden second-energy promotion while XOM is still benched.
- Earnings: **July 31** *(next provider date after the May 1 print; treat as provisional until company IR confirms).*

---

### PLTR
- Close: **144.07** *(manual watch-lane parity pass; 2026-05-01 close)*
- 20 / 50 / 200-day: **141.56 / 145.18 / 164.30**
- MA posture: **above the 20-day, below the 50-day and 200-day**. Short-term bounce, longer-term repair is still incomplete.
- Support: **141.56** (20-day), then **138.60** (bottom of preferred band)
- Resistance: **145.18** (50-day), then **150.44** (top of preferred band)
- Preferred entry band: **138.60 to 150.44** (band updated 2026-05-01)
- Explicit stop: **132.68**
- Invalidation logic: loses 132.68 and fails the current rebound attempt.
- Stance: **Watch-only / bench**. Price is inside the preferred band, but the setup is still below the 50-day and 200-day and remains a higher-risk narrative name.
- Entry-distance context: **inside the preferred band**.
- **Lane note:** do not treat in-band status as deployment permission. This is a watch-lane name and a May 4 earnings monitor.
- ⚠️ **EARNINGS — May 4.**

---

### AMD
- Close: **360.54** *(manual watch-lane parity pass; 2026-05-01 close)*
- 20 / 50 / 200-day: **284.89 / 235.38 / 211.38**
- MA posture: **above all three MAs with a bullish 20 > 50 > 200 stack**. Strong structure, but far above the written zone.
- Support: **311.80** (top of preferred band / first disciplined pullback zone), then **284.89** (20-day)
- Resistance: **current extension zone / recent highs** *(exact upside shelf is not pinned from this artifact layer)*
- Preferred entry band: **275.92 to 311.80** (band updated 2026-05-01)
- Explicit stop: **257.98**
- Invalidation logic: loses the pullback zone and breaks back through 257.98 after the earnings window.
- Stance: **Watch-only / do not chase**. The MA stack is strong, but this remains a non-daily watch-lane name and price is too extended for a disciplined fresh entry.
- Entry-distance context: **+$48.74 / +15.6% above the top of the preferred band**.
- **Lane note:** treat this as an earnings-sensitive tactical monitor that informs the AI sleeve, not as a quiet execution-board promotion.
- ⚠️ **EARNINGS — May 5.**

---

### LNG
- Close: **270.06** *(manual watch-lane parity pass; 2026-05-01 close)*
- 20 / 50 / 200-day: **264.51 / 261.44 / 228.36**
- MA posture: **above all three MAs with a bullish 20 > 50 > 200 stack**. Constructive structure, but still watch-lane only.
- Support: **264.51** (20-day), then **260.82** (bottom of preferred band)
- Resistance: **275.56** (top of preferred band), then recent highs *(confirm via chart before treating as a breakout trigger)*
- Preferred entry band: **260.82 to 275.56** (band updated 2026-05-01)
- Explicit stop: **253.45**
- Invalidation logic: loses 253.45 and breaks the current pullback-support area after the earnings window.
- Stance: **Watch-only / timing-sensitive**. Price is inside the preferred band, but this is still a non-daily energy watch name and not an execution-board candidate.
- Entry-distance context: **inside the preferred band**.
- **Lane note:** useful for LNG-complex read-through and sector timing, but keep it separate from the XOM decision lane.
- ⚠️ **EARNINGS — May 7.**

---

## Freshness and refresh policy

- Last updated: **2026-05-02** — targeted trust-hardening sync for ETN, JPM, NVDA, XOM, GOOG, and MSFT; approved band-sync refreshes for BRK.B, AMZN, VRT, CAT, LMT, and RTX after the May 1 close; and manual watch-lane parity sections added for CVX, PLTR, AMD, and LNG from the same artifact layer. Unless otherwise stated, the rest of the sheet still reflects the 2026-04-27 precision pass recorded on 2026-04-28.
- Data as of: **2026-05-01 close for ETN, JPM, NVDA, XOM, GOOG, MSFT, BRK.B, AMZN, VRT, CAT, LMT, RTX, CVX, PLTR, AMD, and LNG**; unchanged sections still reflect the earlier **2026-04-27 close** precision pass.
- Refresh cadence: each weekday for tracked names, plus extra refreshes before key earnings, after material breaks of support or resistance, or after moves large enough to change entry quality
- Next refresh due: after the BRK.B result is assessed and again through the PLTR / ETN / AMD / LNG / SMCI cluster next week, or earlier if another band/state transition changes the live board materially
- Refresh policy: refresh tracked-name close, moving averages, posture, and entry-distance context each weekday. Only rewrite support, resistance, stance, or invalidation language when evidence materially changed, so the sheet stays current without turning noisy.

## Current ranking after precision pass

1. **JPM** — in band, high-quality, no near-term earnings block
2. **NVDA** — in band, but still crowded and Tier 2 only
3. **ETN** — best pullback-only chart, but May 5 earnings caps pre-print aggression
4. **GS** — deployable on paper, but still secondary to JPM
5. **BRK.B** — in band, but repair mode overrides location
6. **GOOG** — almost deployable on pullback only after the strong post-print gap
7. **MSFT** — almost deployable, but still needs either a better pullback or cleaner 200-day repair
8. **VRT** — constructive and still execution-entitled, but ETN remains the primary AI-power name
9. **XOM** — in band, but still benched until the 50-day reclaim and follow-through improve
10. **LMT** — far below stop — repair mode

Watch-lane technical carryovers with maintained bands:
- **AMZN** — post-earnings follow-through monitor, not execution-board-entitled
- **CAT** — post-print industrial read-through, not execution-board-entitled
- **RTX** — repair-mode defense read-through, not execution-board-entitled

## Data-quality note

- Daily OHLC data is refreshed from the scripted pipeline and should now be treated as a weekday-maintained surface for tracked names.
- This sheet is based on the latest available closing data in the refresh chain. It is precise at the daily level, not intraday.
- Support and resistance were left unchanged unless prior levels appeared materially breached or clearly superseded by new structure.
- Bands updated 2026-04-28 are MA20-anchored mechanical proposals. They confirm the existing structural framing rather than chase price — the largest single-band shift was 4 dollars.
- **Confidence remains usable-with-caution, not clean-deployable.** The old `GS` state-vs-band conflict is gone and dashboard validation is clean again, but remaining caution should center on the unresolved NVDA timing path, directional-only macro interpretation, crowding, and normal size discipline.
- **Market-state context is fresh, but it still carries approximation and mixed-date caveats:** policy probabilities are simplified rather than full FedWatch, pre-market tape is weak, and some rates series are not perfectly aligned to the same trading day.
- **Deployable now** in this sheet means the gates line up on paper. It does **not** cancel residual timing-confirmation work, crowding risk, or normal size discipline.
- **BRK.B** has symbol-format caveats on some public sites. Cross-site screenshots may still show symbol formatting inconsistently.

## Bottom line

- **Live in-band names now:** JPM and NVDA
- **Best chart, still earnings-capped:** ETN (above band, May 5 earnings)
- **Post-print, not yet clean enough to force:** GOOG and MSFT
- **Benched despite improved location:** BRK.B and XOM
- **Need patience before aggressive sizing:** GS (deployable on paper, but still secondary to JPM), VRT on the execution board, and AMZN and CAT in the watch lane
- **Repair mode — do not touch:** LMT (below stop, broken structure), RTX (watch-lane repair monitor), BRK.B (at band but MAs broken), XOM (in band, but still benched until the 50-day reclaim and post-print follow-through improve)
- **Confidence:** usable with caution — 5 active dashboard warnings, all known and documented
- **Operating directive:** No new entries in the open without a pre-set limit at a defined band level. JPM and NVDA are live on paper, but the warning stack, crowding, and near-term catalyst calendar still require discipline.
