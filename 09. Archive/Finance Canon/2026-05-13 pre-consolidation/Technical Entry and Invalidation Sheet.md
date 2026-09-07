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
- Close: **401.53** *(technical refresh; 2026-05-12 close; current artifact layer)*
- 20 / 50 / 200-day: **411.46 / 383.23 / 361.51**
- MA posture: **above the 50-day and 200-day, but below the 20-day**. The owner-approved setup remains inside the approved band, but the short-term trend is no longer a clean above-all-MAs chase setup.
- Support: **395.59–401.53** (lower/current pullback zone inside the preferred band), then **383.23** (50-day reference) and **349.15** (explicit stop)
- Resistance: **410.79–411.46** (top of preferred band / 20-day reclaim / no-chase ceiling)
- Preferred entry band: **368.84 to 410.75** (auto-applied band maintenance 2026-05-13; KELTNER_PRIMARY / IN_BAND)
- Reference band: **368.42 to 410.79** / reference stop **349.15** (weekly reference refresh 2026-05-12; KELTNER_PRIMARY / IN_BAND; data as of 2026-05-12)
- Reference-band authority: **execution-band eligible if separately applied/approved**. Reference levels refresh chart context only; they do not create trade, sizing, sleeve, owner-approval, or execution authority.
- Explicit stop: **349.79**
- Invalidation logic: loses the preferred band / 50-day support zone and ultimately fails the explicit 349.15 stop.
- Stance: **Deployable now / owner-approved Tier 1 explicit add, with manual-only execution discipline**. Randall approved Tier 1 explicit-add status on 2026-05-10; the current artifact close remains inside the approved band at 401.53, still below the no-chase ceiling. Manual-only deployment authority: no automatic execution, no chase above 410.79–411.46, and sizing stays governed by broader AI-power/correlation warnings.
- Entry-distance context: **inside the preferred band, near the lower/pullback zone**.
- **Recent history:** the May 5 report has been interpreted as constructive; the 2026-05-08 entry-band refresh moved ETN from slightly above-band patience into an in-band promotion-review setup, Randall promoted it on 2026-05-09, Randall upgraded it to Tier 1 explicit-add priority on 2026-05-10, and the 2026-05-12 artifact close keeps it in band while below the 20-day.
- **POST-EARNINGS FOLLOW-UP.** The pre-print blocker has passed and owner promotion has landed. ETN is still the first capital-deployment priority in the review stack, but execution remains manual-only: no automatic execution and no chase above the written band.
- **Automated band maintenance:** 2026-05-13 eligible proposal applied: prior **369.04–410.42 / stop 350.22** → new **368.84–410.75 / stop 349.79**. This updates technical maintenance levels only; it does not create trade, sizing, sleeve, approval, or execution authority.

---

### JPM
- Close: **300.00** *(technical refresh; 2026-05-11 close; corroborated by current artifact layer)*
- 20 / 50 / 200-day: **309.93 / 299.32 / 302.80**
- MA posture: **above the 50-day, but below the 20-day and 200-day**. The owner-approved setup has failed the formal band and is now below the explicit stop on the current artifact layer.
- Support: **299.32** (50-day / next repair reference), then only a fresh base; the former **301.17** stop has been lost.
- Resistance: **301.17** (stop reclaim / first repair line), then **306.82** (bottom of refreshed band), then **318.12** (top of refreshed band)
- Preferred entry band: **294.57 to 308.54** (auto-applied band maintenance 2026-05-12; KELTNER_PRIMARY / IN_BAND)
- Reference band: **294.57 to 308.54** / reference stop **286.81** (weekly reference refresh 2026-05-12; KELTNER_PRIMARY / IN_BAND; data as of 2026-05-12)
- Reference-band authority: **execution-band eligible if separately applied/approved**. Reference levels refresh chart context only; they do not create trade, sizing, sleeve, owner-approval, or execution authority.
- Explicit stop: **286.81**
- Invalidation logic: the 2026-05-11 close below 301.17 invalidates the live trigger. Re-entry now requires a stop reclaim plus either a band reclaim or explicit band review; owner approval alone is not enough.
- Stance: **Do not touch / stop breached**. Explicit owner approval from 2026-05-07 remains recorded as history, but it is suspended operationally while price is below the hard stop.
- Entry-distance context: **$1.17 / 0.4% below the explicit stop and $6.82 / 2.2% below the preferred band low**.
- **Recent history:** the refreshed band moved JPM from pullback-only into a live owner-approved setup, but the latest artifact layer now shows a stop breach rather than merely “almost deployable.” Do not treat approval history as a live trigger.
- Earnings: **July 14 (Q2 2026)** — no near-term earnings risk.
- **Automated band maintenance:** 2026-05-12 eligible proposal applied: prior **306.82–318.12 / stop 301.17** → new **294.57–308.54 / stop 286.81**. This updates technical maintenance levels only; it does not create trade, sizing, sleeve, approval, or execution authority.

---

### NVDA
- Close: **215.20** *(entry-band refresh; 2026-05-08 close)*
- 20 / 50 / 200-day: **203.18 / 188.65 / 184.72**
- MA posture: **above all three MAs with a bullish 20 > 50 > 200 stack**. AI leadership intact, but crowding still matters.
- Support: **200** (20-day), then **188–184** (50-day / 200-day cluster)
- Resistance: **210.84** (top of refreshed band), then the recent higher-high zone
- Preferred entry band: **197.01 to 210.84**
- Reference band: **192.25 to 206.67** / reference stop **183.72** (weekly reference refresh 2026-05-12; KELTNER_MA_CONSTRAINED / ABOVE_BAND_WAIT; data as of 2026-05-12)
- Reference-band authority: **reference only / no execution entitlement — earnings TIMING_WINDOW, ABOVE_BAND_WAIT**. Reference levels refresh chart context only; they do not create trade, sizing, sleeve, owner-approval, or execution authority.
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
- Reference band: **345.91 to 366.43** / reference stop **325.43** (weekly reference refresh 2026-05-12; KELTNER_MA_CONSTRAINED / NEAR_BAND; data as of 2026-05-12)
- Reference-band authority: **execution-band eligible if separately applied/approved**. Reference levels refresh chart context only; they do not create trade, sizing, sleeve, owner-approval, or execution authority.
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
- Reference band: **463.38 to 477.95** / reference stop **451.72** (weekly reference refresh 2026-05-12; DUAL_MA_RECLAIM / BELOW_STOP; data as of 2026-05-12)
- Reference-band authority: **reference only / no execution entitlement — BELOW_STOP**. Reference levels refresh chart context only; they do not create trade, sizing, sleeve, owner-approval, or execution authority.
- Explicit stop: **378.18**
- Invalidation logic: loses the recovery structure and fails back through the 50-day / band zone.
- Stance: **Deployable now / owner-approved staged manual candidate**. Randall approved promotion on 2026-05-12 after MSFT / GOOG / NVDA growth review. The current artifact close is inside the working band, but the stock remains below the 200-day, so this is a staged accumulation candidate rather than a full-confidence trend-reclaim setup.
- Entry-distance context: **inside the preferred band near the upper edge**; latest artifact close **407.77** sits below the **412.56** band ceiling. Prefer a starter tranche while below the 200-day, not a full allocation.
- **Post-earnings read:** Microsoft's Apr 29 report was operationally strong. Azure grew **40%** and management said the AI business surpassed a **$37B annual revenue run rate**, but the 200-day remains a real structural overhang.
- **What matters now:** the earnings blocker is gone and owner promotion has landed. The remaining issue is tranche sizing: starter exposure can be justified inside band, while larger exposure should wait for either a lower-band/risk-reward improvement or a cleaner repair confirmation.

---

### AMZN
- Close: **268.26** *(band-sync refresh; 2026-05-01 close)*
- 20 / 50 / 200-day: **247.37 / 224.80 / 227.38**
- MA posture: **above all three MAs**. Trend is constructive.
- Support: **247** (20-day), then **227** (200-day)
- Resistance: prior highs (confirm via chart)
- Preferred entry band: **243.59 to 258.71** (band updated 2026-05-01)
- Reference band: **246.35 to 261.56** / reference stop **233.13** (weekly reference refresh 2026-05-12; KELTNER_MA_CONSTRAINED / NEAR_BAND; data as of 2026-05-12)
- Reference-band authority: **reference only / no execution entitlement — watch/reference lane, underdefined, WATCH**. Reference levels refresh chart context only; they do not create trade, sizing, sleeve, owner-approval, or execution authority.
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
- Reference band: **286.19 to 331.95** / reference stop **265.39** (weekly reference refresh 2026-05-12; KELTNER_MA_CONSTRAINED / ABOVE_BAND_WAIT; data as of 2026-05-12)
- Reference-band authority: **reference only / no execution entitlement — underdefined, WATCH, ABOVE_BAND_WAIT**. Reference levels refresh chart context only; they do not create trade, sizing, sleeve, owner-approval, or execution authority.
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
- Reference band: **799.68 to 863.94** / reference stop **750.78** (weekly reference refresh 2026-05-12; KELTNER_MA_CONSTRAINED / ABOVE_BAND_WAIT; data as of 2026-05-12)
- Reference-band authority: **reference only / no execution entitlement — watch/reference lane, WATCH, ABOVE_BAND_WAIT**. Reference levels refresh chart context only; they do not create trade, sizing, sleeve, owner-approval, or execution authority.
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
- Reference band: **881.41 to 952.98** / reference stop **841.65** (weekly reference refresh 2026-05-12; KELTNER_PRIMARY / NEAR_BAND; data as of 2026-05-12)
- Reference-band authority: **reference only / no execution entitlement — watch/reference lane, WATCH**. Reference levels refresh chart context only; they do not create trade, sizing, sleeve, owner-approval, or execution authority.
- Explicit stop: **876.52**
- Invalidation logic: loses the written stop and fails the current healthcare watch-lane base.
- Stance: **Watch-only / sector-expansion candidate**. Defined levels now exist in the owner layer, but the name remains watch-lane only until explicit promotion and sizing review.
- Entry-distance context: **+$5.08 / +0.5% above the top of the preferred band**.
- **Recent history:** LLY remains the cleanest current healthcare diversification candidate under WF38, but it is still slightly above the written band and is not execution-board-entitled just because the band now exists.
- **Lane note:** LLY now has explicit owner-layer technical levels for review-only competition against other diversification candidates, not deployable authority.
- Earnings: **August 5 (Q2 2026 per yfinance; treat as provisional until company IR confirms).**

---

### GS
- Close: **944.86** *(band-sync refresh; 2026-05-11 close from `tmp/band-proposals.json`)*
- 20 / 50 / 200-day: **924.03 / 873.36 / 832.38**
- MA posture: **above all three MAs with a bullish 20 > 50 > 200 stack**.
- Support: **924** (20-day / refreshed band top zone), then **873** (50-day)
- Resistance: current extension zone above the refreshed band top at **923.51**
- Preferred entry band: **886.29 to 923.51** (band updated 2026-05-11)
- Reference band: **888.11 to 926.22** / reference stop **860.36** (weekly reference refresh 2026-05-12; KELTNER_MA_CONSTRAINED / NEAR_BAND; data as of 2026-05-12)
- Reference-band authority: **execution-band eligible if separately applied/approved**. Reference levels refresh chart context only; they do not create trade, sizing, sleeve, owner-approval, or execution authority.
- Explicit stop: **858.76**
- Invalidation logic: loses the 50-day and breaks the uptrend; do not chase while price remains above the refreshed band.
- Stance: **Almost deployable / no-chase**; GS is now machine-applied to the refreshed eligible band, but the close remains above the preferred zone and still requires explicit owner promotion/sizing review before any portfolio change.
- Entry-distance context: **+$21.35 / +2.3% above the top of the refreshed preferred band**.
- **Recent history:** the eligible GS band-refresh proposal was applied on 2026-05-11: prior band **878.71–926.76 / stop 854.68** moved to **886.29–923.51 / stop 858.76**. This clears GS from the blocking stale-band list, but it does not create approval, sizing, or execution authority.
- Earnings: **July 14 (Q2 2026 provider-estimate calendar date)** — no near-term earnings risk, but cross-check company IR before treating as primary-confirmed.

---

### BRK.B
- Close: **473.01** *(band-sync refresh; 2026-05-01 close)*
- 20 / 50 / 200-day: **474.98 / 482.48 / 489.90**
- MA posture: **below all three MAs**. Ballast profile intact, chart still in repair.
- Support: **472**
- Resistance: **475**, then **482**
- Preferred entry band: **471.93 to 484.15** (band updated 2026-05-01)
- Reference band: **489.76 to 498.08** / reference stop **483.10** (weekly reference refresh 2026-05-12; DUAL_MA_RECLAIM / RECLAIM_ONLY; data as of 2026-05-12)
- Reference-band authority: **reference only / no execution entitlement — REPAIR, RECLAIM_ONLY**. Reference levels refresh chart context only; they do not create trade, sizing, sleeve, owner-approval, or execution authority.
- Explicit stop: **465.81**
- Invalidation logic: loses 464 and confirms continued relative weakness.
- Stance: **Bench / do not touch**, even though price is right at the top of band the MA structure overrides band location.
- Entry-distance context: **inside the preferred band**, but the weak MA structure still means this is band-location-without-MA-support.
- **Recent history:** BRK.B is back inside the refreshed band, but all three MAs still sit above price — entering here is still entering into MA resistance, not into clean trend support. The May 2 report does not change that technical judgment; it just removes the stale pre-print holding pattern.
- ⚠️ **EARNINGS — Reported May 2** *(post-print bench state confirmed. Timing is no longer the blocker for this quarter's print; structure repair is. The next-quarter date is not yet rolled cleanly in the machine layer, so keep this in post-earnings cleanup rather than fresh-catalyst mode.)*

---

### XOM
- Close: **149.68** *(source-confirmed May 11 close; Exxon IR / LSEG and `tmp/technical-refresh.json`)*
- May 11 range: **146.00–149.72** — the intraday low pierced the written **146.14** stop by **$0.14**, then price reclaimed the stop into the close.
- 20 / 50 / 200-day: **150.01 / 154.84 / 128.04**
- MA posture: **above the 200-day, below the 20-day and 50-day**. The chart failed the refreshed band and remains below the short/intermediate trend stack.
- Support: **146.14** (explicit stop / urgent review line), then **141.97–143.92** (recent low zone / monthly artifact low)
- Resistance: **150.24** (bottom of refreshed band), then **154.84–158.44** (50-day / top of refreshed band)
- Preferred entry band: **150.24 to 158.44** (band updated 2026-05-01)
- Reference band: **142.96 to 152.14** / reference stop **137.86** (weekly reference refresh 2026-05-12; KELTNER_PRIMARY / IN_BAND; data as of 2026-05-12)
- Reference-band authority: **reference only / no execution entitlement — conditional_requalify, REPAIR**. Reference levels refresh chart context only; they do not create trade, sizing, sleeve, owner-approval, or execution authority.
- Explicit stop: **146.14**
- Invalidation logic: loses the refreshed band and fails back below 146.14, or fails another 50-day reclaim with oil context rolling over. **May 11 produced an intraday stop breach and close-back-above-stop, so this must be treated as a formal repair review item before any oil-supported thesis refresh.**
- Stance: **Repair / do not touch**. The close did **not** finish below the explicit stop, but the intraday stop breach means “bench” language alone understates the technical risk.
- Entry-distance context: **$0.56 / 0.4% below the preferred band low and $3.54 / 2.4% above the explicit stop on a closing basis**; intraday low was **$0.14 below** the stop.
- **Post-earnings read:** the quarter was stronger than the GAAP headline implied. Exxon reported **$4.2B / $1.00 EPS** GAAP, but **$8.8B / $2.09 EPS** excluding identified items and timing effects. Guyana and the Permian stayed strong, but Hormuz disruption and LNG repair uncertainty still dominate the near-term risk map.
- **What matters now:** acknowledge the May 11 stop test first. No energy/oil thesis refresh should upgrade XOM until price reclaims the refreshed band / 20-day and then works toward the 50-day with supportive oil tape.

---

### LMT
- Close: **514.26** *(WF38 canonical-note sync; 2026-05-06 close)*
- 20 / 50 / 200-day: **556.95 / 605.91 / 520.89**
- MA posture: **below all three MAs**. The chart is broken — price is below every major MA.
- Support: confirm fresh support only after a new base forms
- Resistance: **521** (200-day), then **557** (20-day)
- Preferred entry band: **548.51 to 582.27** (mechanical reference only, not a live setup)
- Reference band: **569.12 to 587.87** / reference stop **554.12** (weekly reference refresh 2026-05-12; DUAL_MA_RECLAIM / BELOW_STOP; data as of 2026-05-12)
- Reference-band authority: **reference only / no execution entitlement — repair_mode, REPAIR, BELOW_STOP**. Reference levels refresh chart context only; they do not create trade, sizing, sleeve, owner-approval, or execution authority.
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
- Reference band: **171.11 to 182.09** / reference stop **165.01** (weekly reference refresh 2026-05-12; KELTNER_PRIMARY / IN_BAND; data as of 2026-05-12)
- Reference-band authority: **reference only / no execution entitlement — watch/reference lane, underdefined, WATCH**. Reference levels refresh chart context only; they do not create trade, sizing, sleeve, owner-approval, or execution authority.
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
- Reference band: **178.95 to 189.21** / reference stop **173.25** (weekly reference refresh 2026-05-12; KELTNER_PRIMARY / IN_BAND; data as of 2026-05-12)
- Reference-band authority: **reference only / no execution entitlement — watch/reference lane, underdefined, WATCH**. Reference levels refresh chart context only; they do not create trade, sizing, sleeve, owner-approval, or execution authority.
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
- Reference band: **163.73 to 171.22** / reference stop **157.74** (weekly reference refresh 2026-05-12; DUAL_MA_RECLAIM / BELOW_STOP; data as of 2026-05-12)
- Reference-band authority: **reference only / no execution entitlement — watch/reference lane, underdefined, WATCH, BELOW_STOP**. Reference levels refresh chart context only; they do not create trade, sizing, sleeve, owner-approval, or execution authority.
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
- Reference band: **298.49 to 364.13** / reference stop **259.21** (weekly reference refresh 2026-05-12; KELTNER_MA_CONSTRAINED / ABOVE_BAND_WAIT; data as of 2026-05-12)
- Reference-band authority: **reference only / no execution entitlement — watch/reference lane, underdefined, WATCH, ABOVE_BAND_WAIT**. Reference levels refresh chart context only; they do not create trade, sizing, sleeve, owner-approval, or execution authority.
- Explicit stop: **257.98**
- Invalidation logic: loses the pullback zone and breaks back through 257.98 after the earnings window.
- Stance: **Watch-only / do not chase**. The MA stack is strong, but this remains a non-daily watch-lane name and price is too extended for a disciplined fresh entry.
- Entry-distance context: **+$48.74 / +15.6% above the top of the preferred band**.
- **Lane note:** treat this as a post-earnings tactical monitor that informs the AI sleeve, not as a quiet execution-board promotion.
- **Post-earnings status:** reported May 5; use the scorecard / read-through layer for interpretation and do not promote from watch-lane without owner review.

---

### LNG
- Close: **240.70** *(technical refresh; 2026-05-11 close; current artifact layer)*
- 20 / 50 / 200-day: **259.26 / 264.88 / 229.19**
- MA posture: **above the 200-day, but below the 20-day and 50-day**. The May 1 constructive setup is no longer intact.
- Support: no live support from the old band; next repair reference is the **229.19** 200-day after the stop breach.
- Resistance: **253.45** (lost stop / first repair line), then **260.82** (bottom of the old preferred band), then **275.56** (top of the old band)
- Preferred entry band: **260.82 to 275.56** (band updated 2026-05-01; now stale as a live setup and review-only until rebuilt)
- Reference band: **241.62 to 259.80** / reference stop **231.52** (weekly reference refresh 2026-05-12; KELTNER_PRIMARY / IN_BAND; data as of 2026-05-12)
- Reference-band authority: **reference only / no execution entitlement — watch/reference lane, underdefined, WATCH**. Reference levels refresh chart context only; they do not create trade, sizing, sleeve, owner-approval, or execution authority.
- Explicit stop: **253.45**
- Invalidation logic: the 2026-05-11 close below 253.45 invalidates the prior watch-lane setup. Any future setup requires a stop reclaim and fresh band review, not automatic reuse of the old band.
- Stance: **Watch-only / do not touch — stop breached**. LNG remains a watch-lane energy read-through name, but it is no longer a timing-sensitive in-band watch.
- Entry-distance context: **$12.75 / 5.0% below the explicit stop and $20.12 / 7.7% below the preferred band low**.
- **Lane note:** useful for LNG-complex read-through and sector timing, but keep it separate from the XOM decision lane and do not promote from this state without explicit owner review.
- Earnings: provider-estimated next print **2026-08-06** in current artifacts; not primary-confirmed.

---

### BKNG
- Close: **165.93** *(artifact-confirmed repair-mode sync; 2026-05-08 close)*
- 20 / 50 / 200-day: **177.08 / 174.19 / 198.30**
- MA posture: **below all three major moving averages**. This is repair mode, not an entry setup.
- Support: **164.05–170.91** (watch/rebuild zone only), then **161–164** (manual support area from BKNG review)
- Resistance: **174–177** (repair/reclaim zone), then **198.30** (200-day / machine reclaim reference)
- Preferred entry band: **164.05 to 170.91** *(watch/rebuild only; not deployable and not auto-applyable)*
- Reference band: **197.65 to 205.78** / reference stop **191.15** (weekly reference refresh 2026-05-12; DUAL_MA_RECLAIM / BELOW_STOP; data as of 2026-05-12)
- Reference-band authority: **reference only / no execution entitlement — watch/reference lane, repair_mode, REPAIR, BELOW_STOP**. Reference levels refresh chart context only; they do not create trade, sizing, sleeve, owner-approval, or execution authority.
- Explicit stop/reference: **155.97**
- Invalidation logic: fails the 155.97 reference stop or loses the 161–164 support area without reclaiming 174–177.
- Stance: **Watch-only / repair — not deployable**. Fundamentals justify promotion-review monitoring, but the technical gate fails closed while BKNG is below all major MAs and `BELOW_STOP` in the band proposal artifact.
- Entry-distance context: **inside the watch/rebuild zone**, but in-band does not matter while `repair_mode`, below-stop, and watch-lane status remain active.
- **Catalyst state:** earnings state is now **CLEAR** in `tmp/band-proposals.json` (`days_to_earnings=80`) from a **2026-07-29 provider estimate** in `tmp/earnings-calendar.json`; this is not primary-confirmed.
- **Lane note:** BKNG is an accepted repair-mode blocker / manual wait-state. Do not apply the machine-suggested reclaim band as a live execution band and do not promote without explicit owner review.

---

## Freshness and refresh policy

- Last updated: **2026-05-12** — ETN received scoped automatic eligible entry-band maintenance into the canonical note/config layer; JPM and LNG remain close-below-stop/repair review states; XOM remains formal repair review after an intraday 146.14 stop pierce/reclaim; NVDA remains wait / no-chase; BKNG remains watch-only / repair with earnings state provider-clear but not primary-confirmed.
- Data as of: **2026-05-12 artifact layer for ETN; 2026-05-11 close for XOM, JPM, and LNG; 2026-05-08 close for NVDA and BKNG; 2026-05-06 close for the prior artifact-confirmed updates in GOOG, MSFT, VRT, GS, and LMT**; other sections remain as labeled and should not be assumed refreshed unless their section says otherwise.
- Refresh cadence: each weekday for tracked names, plus extra refreshes before key earnings, after material breaks of support or resistance, or after moves large enough to change entry quality
- Next refresh due: after ETN either loses the 368.11 lower band / 348.84 stop, moves above the 410.48 upper band, or materially changes the setup; after JPM reclaims 301.17 and then the formal band or receives explicit band review; after LNG reclaims 253.45 and receives a fresh band review; after BKNG primary earnings-date confirmation, repair through 174–177, or loss of the 155.97 / 161–164 support references; or earlier if another band/state transition changes the live board materially
- Refresh policy: refresh tracked-name close, moving averages, posture, and entry-distance context each weekday. Only rewrite support, resistance, stance, or invalidation language when evidence materially changed, so the sheet stays current without turning noisy.

## Technical condition summary

This section summarizes technical state only. Deployment priority, owner approval state, and portfolio action authority live in [[03. Portfolio/Deployment Trigger Sheet]].

- **Constructive / needs discipline:** ETN, GOOG, MSFT, GS, NVDA, VRT.
- **Repair or weak structure:** BRK.B, XOM, LMT, RTX, BKNG.
- **Watch-lane technical carryovers:** AMZN, CAT, LLY, and other monitored names remain non-execution-board-entitled unless explicitly promoted.

## Data-quality note

- Daily OHLC data is refreshed from the scripted pipeline and should now be treated as a weekday-maintained surface for tracked names.
- This sheet is based on the latest available closing data in the refresh chain. It is precise at the daily level, not intraday.
- Support and resistance were left unchanged unless prior levels appeared materially breached or clearly superseded by new structure.
- Bands updated 2026-04-28 are MA20-anchored mechanical proposals. They confirm the existing structural framing rather than chase price — the largest single-band shift was 4 dollars.
- **Confidence remains usable-with-caution, not clean-deployable.** Dashboard validation is currently clean on critical/warning count after BKNG repair-mode handling, but the broader posture still requires caution around monitor-only band reviews, unresolved/secondary-source catalyst dates, directional-only macro interpretation, crowding, and normal size discipline.
- **Market-state context is fresh, but it still carries approximation and mixed-date caveats:** policy probabilities are simplified rather than full FedWatch, pre-market tape is weak, and some rates series are not perfectly aligned to the same trading day.
- **In-band is not deployable-now by default.** ETN is the current owner-approved in-band exception. JPM's approval remains recorded only as history; the current artifact layer is below the hard stop, so the live trigger is red, not merely below-band. LNG has also breached its watch-lane stop and requires repair before any promotion review. NVDA remains wait / no-chase, and GS remains almost deployable and above its written band.
- **BRK.B** has symbol-format caveats on some public sites. Cross-site screenshots may still show symbol formatting inconsistently.

## Bottom line

- This sheet owns technical condition, levels, repair zones, and invalidation.
- It does not grant owner approval, portfolio weight, trade authority, or deployment state.
- Use [[03. Portfolio/Deployment Trigger Sheet]] for live action state and [[03. Portfolio/Portfolio Snapshot]] for weight/concentration context.
- **Confidence:** usable with caution — dashboard validation is clean on critical/warning count, but monitor-only band-review items and source-confidence caveats still require judgment.
