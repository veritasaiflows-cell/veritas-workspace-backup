# Technical Entry and Invalidation Sheet

## Purpose

Convert the model portfolio from abstract holdings into execution-aware candidates.

This is not a live order sheet. It is the technical discipline layer.

Any deployable-state wording here is subordinate technical shorthand, not final action authority. The canonical deployable-now decision surface lives in [[03. Portfolio/Deployment Trigger Sheet]].

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
- Close: **401.51** *(entry-band refresh; 2026-05-08 close)*
- 20 / 50 / 200-day: **411.67 / 382.83 / 362.25**
- MA posture: **above the 50-day and 200-day but below the 20-day**. Long-term structure remains constructive, but this is a pullback-in-band setup rather than clean momentum continuation.
- Support: **395.59–400** (lower half of the preferred band / current pullback zone), then **382.83–383.23** (50-day / explicit stop cluster)
- Resistance: **411.67** (20-day), then **420.31** (top of preferred band)
- Preferred entry band: **395.59 to 420.31** (vault preferred band set 2026-04-30)
- Explicit stop: **383.23**
- Invalidation logic: loses 383.23 and fails the 50-day / refreshed-band support cluster.
- Stance: **Deployable now / owner-promoted conditional add**. Randall approved promotion on 2026-05-09 after the fresh entry-band check confirmed ETN remained in band at 401.51. This is still a Tier 2 manual-only setup: no chase above 420.31, no automatic execution, and sizing stays governed by the broader AI-power/correlation warnings.
- Entry-distance context: **inside the preferred band, near the lower half**.
- **Recent history:** the May 5 report has been interpreted as constructive; the 2026-05-08 entry-band refresh moved ETN from slightly above-band patience into an in-band promotion-review setup, and Randall promoted it on 2026-05-09 after the rerun confirmed the band remained valid.
- **POST-EARNINGS FOLLOW-UP.** The pre-print blocker has passed and owner promotion has landed, but this remains manual-only Tier 2 deployment authority; no automatic execution and no chase above the written band.

---

### JPM
- Close: **302.10** *(technical refresh; 2026-05-08 close)*
- 20 / 50 / 200-day: **310.61 / 299.30 / 302.76**
- MA posture: **above the 50-day, but below the 20-day and slightly below the 200-day**. The owner-approved setup is still alive, but the latest close no longer satisfies the formal band.
- Support: **301.17–302.76** (explicit stop / 200-day cluster), then **299.30** (50-day)
- Resistance: **306.82** (bottom of refreshed band), then **318.12** (top of refreshed band)
- Preferred entry band: **306.82 to 318.12** (refreshed band)
- Explicit stop: **301.17**
- Invalidation logic: loses 301.17 and the 200-day / higher-low structure together.
- Stance: **Almost deployable / owner-approved setup not live**. Explicit owner approval landed on 2026-05-07, but the 2026-05-08 close is below the formal band and close enough to invalidation that the live trigger must fail closed until price reclaims the band or the band is explicitly reviewed.
- Entry-distance context: **1.5% below the preferred band low and only modestly above invalidation**.
- **Recent history:** the refreshed band moved JPM from pullback-only into a live owner-approved setup, but the latest close fell back below the formal band. Approval remains recorded; current trigger quality does not justify a green deployable-now label.
- Earnings: **July 14 (Q2 2026)** — no near-term earnings risk.

---

### NVDA
- Close: **215.20** *(entry-band refresh; 2026-05-08 close)*
- 20 / 50 / 200-day: **203.18 / 188.65 / 184.72**
- MA posture: **above all three MAs with a bullish 20 > 50 > 200 stack**. AI leadership intact, but crowding still matters.
- Support: **200** (20-day), then **188–184** (50-day / 200-day cluster)
- Resistance: **210.84** (top of refreshed band), then the recent higher-high zone
- Preferred entry band: **197.01 to 210.84**
- Explicit stop: **190.10**
- Invalidation logic: loses 190.10 and the MA cluster, then slips back under the breakout zone.
- Stance: **Wait / no chase**; the 2026-05-09 entry-band rerun moved NVDA back above the written band while the May 20 catalyst path remains timing-sensitive.
- Entry-distance context: **+$4.36 / +2.1% above the top of the preferred band**.
- **Recent history:** the latest rerun shows NVDA no longer inside the written band. Business quality remains intact, but price, crowding, concentration, and earnings timing argue for patience rather than promotion.
- Earnings: **May 20 (DATE CHANGED — vault had May 27, yfinance now shows May 20).** Verify against NVIDIA IR before treating timing as confirmed. If a clean primary confirmation still has not landed by the first post-close chain on **2026-05-13**, keep the date explicitly tagged unconfirmed and do not let downstream notes speak as if it were primary-confirmed.

---

### GOOG
- Close: **395.14** *(WF38 canonical-note sync; 2026-05-06 close)*
- 20 / 50 / 200-day: **346.99 / 318.62 / 284.02**
- MA posture: **above all three MAs with a bullish 20 > 50 > 200 stack**. Trend strengthened after the print.
- Support: **362** (top of the refreshed band / first disciplined pullback zone), then **347** (20-day)
- Resistance: **395**, then fresh post-print highs
- Preferred entry band: **341.96 to 362.08**
- Explicit stop: **331.90**
- Invalidation logic: loses the post-print breakout shelf and falls back under the 20-day / band support zone.
- Stance: **Almost deployable**, but only on pullback / revalidation into the written band.
- Entry-distance context: **+$33.06 / +9.1% above the top of the preferred band** — materially extended.
- **Post-earnings read:** Alphabet's Apr 29 report was thesis-confirming. Search stayed strong and Google Cloud accelerated to **+63%**, but the stock already moved about **10%** above the pre-print close by the May 1 close. Better business read, worse entry location.
- **What matters now:** this is no longer an earnings-block case. It is an entry-discipline case. Do not chase strength far above the written band.

---

### MSFT
- Close: **413.96** *(WF38 canonical-note sync; 2026-05-06 close)*
- 20 / 50 / 200-day: **411.55 / 397.48 / 465.22**
- MA posture: **above the 20-day and 50-day, still below the 200-day**. Recovery intact, long-term repair still incomplete.
- Support: **412–397** (20/50 cluster), then **378**
- Resistance: **414–415** (current area), then **465** (200-day)
- Preferred entry band: **389.64 to 412.56** (still the working post-print band)
- Explicit stop: **378.18**
- Invalidation logic: loses the recovery structure and fails back through the 50-day / band zone.
- Stance: **Almost deployable**, but still needs either a cleaner pullback into band or stronger repair through the 200-day.
- Entry-distance context: **+$1.40 / +0.3% above the top of the preferred band** — only mildly extended, but not quite ideal.
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
- Close: **358.92** *(WF38 canonical-note sync; 2026-05-06 close)*
- 20 / 50 / 200-day: **314.72 / 281.57 / 195.15**
- MA posture: **above all three MAs with a bullish 20 > 50 > 200 stack**. Clean leadership structure.
- Support: **315** (20-day), then **282** (50-day)
- Resistance: confirm via chart
- Preferred entry band: **306.85 to 338.33**
- Explicit stop: **291.11**
- Invalidation logic: loses the 20-day and breaks the uptrend structure.
- Stance: **Watch / research needed** — thesis confirmed by Apr 22 beat-and-raise, but the name remains watch-lane until intentionally promoted.
- Entry-distance context: **+$20.59 / +6.1% above the top of the preferred band**.
- **Recent history:** Reported Q1 2026 on Apr 22 — beat-and-raise confirmed AI power-demand thesis. The refreshed band has nearly caught up to price, but ETN remains the priority first and VRT is still the secondary AI-power name.
- Earnings: **July 29 (Q2 2026 per yfinance; treat as provisional until company IR confirms).**

---

### CAT
- Close: **895.69** *(WF38 review-prep sync; 2026-05-07 close)*
- 20 / 50 / 200-day: **830.87 / 760.37 / 598.58**
- MA posture: **above all three MAs with a bullish 20 > 50 > 200 stack**.
- Support: **831** (20-day), then **760** (50-day)
- Resistance: prior high
- Preferred entry band: **811.65 to 866.48** (band updated 2026-05-01)
- Explicit stop: **784.25**
- Invalidation logic: loses the 50-day and breaks the uptrend.
- Stance: **Watch-only / post-print monitor**. The industrial read-through is useful, but ETN remains the primary execution name for this sleeve.
- Entry-distance context: **+$29.21 / +3.4% above the top of the preferred band**.
- **Recent history:** Industrial-demand read-through still matters for the ETN/industrials sleeve, but the refreshed watch-lane band now sits materially higher after the post-print recalibration. The setup is still extended enough that patience is cleaner than promotion.
- **Lane note:** CAT keeps technical visibility for post-print follow-through and sector read-through, but it no longer earns weekday execution-board ownership.
- Earnings: **August 4 (Q2 2026 per yfinance; treat as provisional until company IR confirms).**

---

### LLY
- Close: **974.96** *(WF38 review-prep sync; 2026-05-07 close)*
- 20 / 50 / 200-day: **924.19 / 943.25 / 913.91**
- MA posture: **above all three MAs**, but the **20-day still sits below the 50-day**, so this is not a clean 20 > 50 > 200 trend-stack breakout.
- Support: **970** (top of the written band), then **943** (50-day)
- Resistance: prior high / confirm via chart
- Preferred entry band: **907.64 to 969.88** (band updated 2026-05-06)
- Explicit stop: **876.52**
- Invalidation logic: loses the written stop and fails the current healthcare watch-lane base.
- Stance: **Watch-only / sector-expansion candidate**. Defined levels now exist in the owner layer, but the name remains watch-lane only until explicit promotion and sizing review.
- Entry-distance context: **+$5.08 / +0.5% above the top of the preferred band**.
- **Recent history:** LLY remains the cleanest current healthcare diversification candidate under WF38, but it is still slightly above the written band and is not execution-board-entitled just because the band now exists.
- **Lane note:** LLY now has explicit owner-layer technical levels for review-only competition against other diversification candidates, not deployable authority.
- Earnings: **August 5 (Q2 2026 per yfinance; treat as provisional until company IR confirms).**

---

### GS
- Close: **937.35** *(WF38 canonical-note sync; 2026-05-06 close)*
- 20 / 50 / 200-day: **918.78 / 871.13 / 828.86**
- MA posture: **above all three MAs with a bullish 20 > 50 > 200 stack**.
- Support: **919** (20-day), then **871** (50-day)
- Resistance: current extension zone; prior written band top is **926.76**
- Preferred entry band: **878.71 to 926.76**
- Explicit stop: **854.68**
- Invalidation logic: loses the 50-day and breaks the uptrend.
- Stance: **Almost deployable**; close is above the preferred band, and latest deployment-readiness surface still requires explicit promotion. If promoted later, treat only as a disciplined tactical secondary versus JPM rather than a default primary bank add.
- Entry-distance context: **+$10.59 / +1.1% above the top of the preferred band**.
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
- **Recent history:** BRK.B is back inside the refreshed band, but all three MAs still sit above price — entering here is still entering into MA resistance, not into clean trend support. The May 2 report does not change that technical judgment; it just removes the stale pre-print holding pattern.
- ⚠️ **EARNINGS — Reported May 2** *(post-print bench state confirmed. Timing is no longer the blocker for this quarter's print; structure repair is. The next-quarter date is not yet rolled cleanly in the machine layer, so keep this in post-earnings cleanup rather than fresh-catalyst mode.)*

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
- Close: **514.26** *(WF38 canonical-note sync; 2026-05-06 close)*
- 20 / 50 / 200-day: **556.95 / 605.91 / 520.89**
- MA posture: **below all three MAs**. The chart is broken — price is below every major MA.
- Support: confirm fresh support only after a new base forms
- Resistance: **521** (200-day), then **557** (20-day)
- Preferred entry band: **548.51 to 582.27** (mechanical reference only, not a live setup)
- Explicit stop: **531.63**
- Invalidation logic: prior setup already failed; no new long thesis trigger until price rebuilds support and reclaims key MAs.
- Stance: **Repair mode / do not touch**.
- Entry-distance context: **-$34.25 / -6.2% below the bottom of the reference band** and still below the refreshed stop.
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
- **Lane note:** do not treat in-band status as deployment permission. This is a watch-lane name and post-May 4 earnings monitor.
- **Post-earnings status:** reported May 4; use it as read-through evidence only unless a later owner review promotes the setup.

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
- **Lane note:** treat this as a post-earnings tactical monitor that informs the AI sleeve, not as a quiet execution-board promotion.
- **Post-earnings status:** reported May 5; use the scorecard / read-through layer for interpretation and do not promote from watch-lane without owner review.

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

- Last updated: **2026-05-10** — ETN remains deployable-now / conditional add after fresh entry-band proof; JPM was corrected to owner-approved but trigger-not-live after the latest close fell below the formal band; NVDA remains wait / no-chase after moving above band.
- Data as of: **2026-05-08 close for ETN, JPM, and NVDA; 2026-05-06 close for the prior artifact-confirmed updates in GOOG, MSFT, VRT, GS, and LMT**; other sections remain as labeled and should not be assumed refreshed unless their section says otherwise.
- Refresh cadence: each weekday for tracked names, plus extra refreshes before key earnings, after material breaks of support or resistance, or after moves large enough to change entry quality
- Next refresh due: after LNG / NFP follow-up, after ETN / AMD / SMCI follow-through materially changes the setup, after JPM either reclaims the formal band or receives explicit band review, or earlier if another band/state transition changes the live board materially
- Refresh policy: refresh tracked-name close, moving averages, posture, and entry-distance context each weekday. Only rewrite support, resistance, stance, or invalidation language when evidence materially changed, so the sheet stays current without turning noisy.

## Current ranking after precision pass

1. **ETN** — in band and owner-promoted as a Tier 2 conditional add; no chase above 420.31 and stop awareness at 383.23
2. **JPM** — owner approval is recorded, but latest close is below the formal band and close to invalidation; trigger is not live until reclaim or explicit band review
3. **NVDA** — above band and wait / no-chase; crowded, Tier 2 only, and timing-sensitive into May 20
4. **GOOG** — almost deployable on pullback only after the strong post-print gap
5. **MSFT** — almost deployable, but still slightly above band and below the 200-day
6. **GS** — almost deployable, but now above band and still secondary to JPM
7. **VRT** — constructive, but watch / research needed until intentionally promoted
8. **BRK.B** — repair mode overrides location
9. **XOM** — below band and still benched until the 50-day reclaim and follow-through improve
10. **LMT** — below stop / repair mode

Watch-lane technical carryovers with maintained bands:
- **AMZN** — post-earnings follow-through monitor, not execution-board-entitled
- **CAT** — post-print industrial read-through, not execution-board-entitled
- **LLY** — healthcare diversification watch-lane candidate with review-only owner levels
- **RTX** — repair-mode defense read-through, not execution-board-entitled

## Data-quality note

- Daily OHLC data is refreshed from the scripted pipeline and should now be treated as a weekday-maintained surface for tracked names.
- This sheet is based on the latest available closing data in the refresh chain. It is precise at the daily level, not intraday.
- Support and resistance were left unchanged unless prior levels appeared materially breached or clearly superseded by new structure.
- Bands updated 2026-04-28 are MA20-anchored mechanical proposals. They confirm the existing structural framing rather than chase price — the largest single-band shift was 4 dollars.
- **Confidence remains usable-with-caution, not clean-deployable.** Dashboard validation is warning-grade: LNG is the only blocking band-review item, while 16 other band reviews are monitor-only. Remaining caution also centers on the unresolved NVDA timing path, directional-only macro interpretation, crowding, and normal size discipline.
- **Market-state context is fresh, but it still carries approximation and mixed-date caveats:** policy probabilities are simplified rather than full FedWatch, pre-market tape is weak, and some rates series are not perfectly aligned to the same trading day.
- **In-band is not deployable-now by default.** ETN is the current owner-approved in-band exception. JPM's approval remains recorded, but the current close is below the formal band, so the live trigger is not green. NVDA remains wait / no-chase, and GS remains almost deployable and above its written band.
- **BRK.B** has symbol-format caveats on some public sites. Cross-site screenshots may still show symbol formatting inconsistently.

## Bottom line

- **Live board leader now:** ETN (**deployable now / owner-promoted conditional add**), still manual-only and no-chase above the written band.
- **Owner-approved but trigger not live:** JPM, because the latest close is below the formal band and near invalidation.
- **Almost deployable but not in band:** GOOG, GS, and MSFT
- **Watch-lane with maintained levels:** VRT, AMZN, CAT, LLY, and other watch-lane names
- **Repair / do not touch:** BRK.B, LMT, XOM, and RTX
- **Confidence:** usable with caution — 1 active dashboard warning (LNG blocking band review) plus 16 monitor-only band-review items
- **Operating directive:** No new entries in the open without a pre-set limit at a defined band level. ETN is the only owner-layer deployable-now name; JPM must reclaim the formal band or receive explicit band review before the trigger is treated as live again; warning-grade validation, crowding, catalyst timing, and normal size discipline still require respect.
