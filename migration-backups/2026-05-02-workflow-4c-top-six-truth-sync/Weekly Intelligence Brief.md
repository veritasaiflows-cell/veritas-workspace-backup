# Weekly Intelligence Brief

## Purpose

Run this as the recurring market sweep.

Use it to synthesize macro, sector, company, sentiment, and event-driven signals into an actionable brief.

Script-backed prep path:
- run `python scripts/market_state_refresh.py` before refreshing this note
- optionally run `python scripts/earnings_calendar_enrichment.py` when the earnings map may have changed materially
- run `python scripts/trigger_sheet_refresh.py` when deployment status may have changed
- run `python scripts/post_earnings_prep.py` after material reports so the interpretation pass starts from a clean structured packet
- run `python scripts/post_earnings_note_targets.py` before editing notes so update scope stays selective
- treat script outputs in `tmp/` as evidence inputs, not as automatic final note text

---

## Week of April 21–27, 2026

*Written: 2026-04-27. Data as of April 27 close. Sources: tmp/market-state.json, tmp/earnings-calendar.json, tmp/trigger-sheet.json, tmp/technical-refresh.json, tmp/regime-scores.json.*

---

### 1. Macro pulse

- **Fed funds rate:** 3.50%–3.75% (hold). FOMC decision tomorrow, April 29. No cut expected — consensus is hold. With oil surging back above $100 and inflation persistence unresolved, the bar for any dovish signal is high.
- **Fed cut expectations:** FedWatch probability unavailable from automated source this cycle (ZQK26 contract failed to fetch). Manual read: market pricing approximately one cut in late 2026 at best, possibly zero. Oil above $100 is actively re-tightening financial conditions and reignites inflation tail risk.
- **2Y Treasury:** 3.78% as of 2026-04-24 (FRED DGS2). Effectively unchanged from last week's 3.71%.
- **10Y Treasury:** 4.336% as of 2026-04-27 (yfinance ^TNX). Up from 4.25% last week — rates moving higher at the long end.
- **3M T-bill:** 3.590% as of 2026-04-27 (yfinance ^IRX).
- **2s10s spread:** +55.6 bps (FRED 2Y + yfinance 10Y). Widened modestly from last week's +54 bps. Curve still positively sloped — not recessionary, but the steepening is happening at the wrong end (long rates rising, not short rates falling).
- **3M-10Y spread:** +74.6 bps (live derived). Healthy but no longer as dovish as it appeared when 10Y was at 4.25%.
- **Inflation:** No new CPI/PCE print this week. March CPI was headline +3.3% YoY with core +2.6%. The oil surge from Hormuz disruption is now re-feeding into energy components. Watch the April CPI print (due mid-May) for the second pass of energy-driven headline inflation.
- **GDP:** April 30 advance Q1 GDP print is the next major data point. Consensus around +1.5–2.0% annualized. A miss would add recession anxiety on top of oil shock; a beat would embolden bulls and complicate any cut narrative.
- **Dollar:** DXY 98.53 as of April 27. DXY is soft — below 100 for the first time in extended recent history. A weak dollar with oil above $100 is a mixed but inflation-amplifying combination.

**Regime read:** The macro regime from last week has NOT changed in direction, but has materially changed in *intensity*. The ceasefire is not holding (see Geopolitical section). Oil is back above $100. The dollar is soft. The Fed is on hold. Long rates are rising. This is a stagflationary pressure set — not a crisis, but the conditions that make a "soft landing" narrative more fragile. Selective risk-on remains the right posture, but the energy and inflation tail risk is higher than it was at the prior WIB.

---

### 2. Energy sweep

- **Brent crude:** $102.10/bbl as of April 27 close (yfinance BZ=F). This is a $12 reversal from the $90 post-ceasefire low cited in the prior WIB. Intraweek Brent hit $105–107 before pulling back. The rally is driven by the Hormuz situation (see Geopolitical section).
- **WTI crude:** $96.94/bbl as of April 27 close (yfinance CL=F). WTI crossed $96 — a significant level for US producer economics. WTI was at $84 in the prior WIB.
- **Brent/WTI spread:** $5.16. Elevated, reflecting ongoing supply-route disruption premium in Brent vs. landlocked US crude.
- **EIA inventory:** Not updated for this sweep. Last known: week ending April 10 showed a surprise draw. Current status unknown — monitor Thursday EIA release.
- **Rig count:** Not updated for this sweep.
- **XOM implication:** Oil at $97–102 changes the XOM picture materially. The prior entry band (142–148) was set when oil was $84–90. With WTI at $97, XOM's cash flow and margin outlook is considerably stronger. The setup is still "under review until May 1 earnings" but the earnings quality potential is now meaningfully higher than when the repair call was made. Do not chase. May 1 is the trigger.
- **CVX:** Reports May 1 alongside XOM. Same read-through.
- **Energy sector (XLE):** Down 0.18% on April 27 — underperforming on a day when broader tape is flat to up. This is unusual given oil at $102. Suggests the market may be pricing in either Hormuz resolution hope OR sector-rotation headwinds from rising rates.

---

### 3. Geopolitical scan

**Iran / Strait of Hormuz — the dominant macro variable, now worse than the prior WIB implied:**

- **Prior read (April 14–19 WIB):** Ceasefire announced April 7–8 was holding. Oil collapsing from highs. Hormuz "completely open."
- **Current read (April 27):** The ceasefire is NOT holding. Trump suspended negotiations. Iran's President Pezeshkian stated Tehran would not engage in "imposed negotiations under threats." Iran submitted a new proposal via Pakistani mediators to extend the ceasefire and reopen Hormuz. Strait remains effectively closed or severely restricted.
- **Oil impact:** Brent surged from ~$90 to $106–107 intraweek, IEA characterized the supply disruption as the largest on record. As of April 27, Brent has partially corrected to $102 — reflecting uncertainty about whether a new agreement is achievable.
- **Confidence:** This is a volatile and uncertain situation. The new Iranian proposal via Pakistan is either a genuine opening or a delaying tactic. Either way, the risk premium is back in the market and should not be modeled as fully resolved.
- **Portfolio implications:** Defense names (LMT, RTX) get geopolitical support from this environment but are currently in repair mode. Energy (XOM, CVX) gets direct earnings uplift. Any ceasefire breakthrough is a $10–15/bbl oil downside risk that would reverse this week's energy gains.

**Key watch:** Progress or breakdown of Pakistani-mediated Iran/US ceasefire talks. Any confirmed reopening of Hormuz would be an immediate oil shock in reverse.

---

### 4. Earnings radar

**Reported this week (April 21–25):**
- **VRT (April 22):** Beat-and-raise. Q1 2026 beat on both EPS and revenue with raised guidance. Confirmed strong AI power-demand tailwind. Full scorecard in `05. Intelligence/Earnings/VRT Q1 2026 Post-Earnings Scorecard.md`. VRT is now in "watch only, no entry band" status — thesis confirmed, but no deployment-grade setup yet.
- **LMT (April 23 — date was prior WIB, post-earnings review pending):** Disappointing result. Setup was already broken pre-earnings. Post-earnings scorecard in vault. LMT is in repair mode — do not touch until a fresh base forms. Q2 report is July 21 (yfinance confirmed).
- **LRCX (April 22):** Reported. Semi-equipment read-through for AI capex thesis. Not in tracked universe but positive for the AI infrastructure backdrop.

**Upcoming — this coming week (April 28 – May 2):**
- **MSFT, GOOG, AMZN (April 29 — tomorrow):** The single most important earnings cluster of the season for this portfolio. All three are BLOCKED until results are in. Do not touch. Watch for AI monetization evidence (MSFT Azure, GOOG cloud), advertising resilience (GOOG, AMZN), and ecommerce/margins (AMZN). These prints will determine whether the current extension is justified or needs a pullback.
- **GD (April 29):** Defense read-through. Not in tracked universe but a signal for the defense sector posture.
- **CAT (April 30):** Tracked. In "WATCH / RESEARCH NEEDED" status. A CAT beat on industrial demand would strengthen the ETN and industrials thesis. A miss or guidance cut would be a read-through risk for ETN's power/electrification setup.
- **XOM + CVX (May 1):** Critical for the energy sleeve. With WTI at $97, both companies should have strong Q1 earnings. XOM's report is the requalification trigger for XOM re-entry. Watch for guidance on capex, buyback, and oil-price assumptions.
- **BRK.B (May 2):** Reported earlier than expected (May 2 vs. vault's May 4). In BENCH status currently.
- **ETN (May 5 — CONFIRMED):** Key catalyst. ETN is the leading pullback candidate. The May 5 report is confirmed via Eaton IR. Until then, ETN is earnings-aware — do not chase extension. If it pulls into 383–407 before May 5, the entry is conditional on no gap-down risk from the report.

---

### 5. Analyst and institutional flow

*No machine-fed analyst upgrade/downgrade or 13F data available for this sweep. Manual monitoring required.*

Key items to track manually:
- Watch for any analyst reaction to GOOG/MSFT/AMZN prints on April 29–30 — these will dominate price target revisions for the week of April 28.
- VRT upgrades/target increases likely following the beat-and-raise. Already reflected in price above band.
- RTX and LMT: Both in repair mode. Watch for any analyst downgrades or rating changes following disappointing results.
- Energy sector: Watch for XOM/CVX price target revisions post May 1 earnings given the oil price move.

---

### 6. Technical check

*Data as of April 27 close. Source: tmp/technical-refresh.json, tmp/trigger-sheet.json.*

| Ticker | Close | MA20 | MA50 | MA200 | Posture | State | Notes |
|--------|-------|------|------|-------|---------|-------|-------|
| JPM | 311.63 | 305.43 | 298.12 | 301.68 | Above all MAs | ALMOST | 1.9% above band top (306) |
| ETN | 416.77 | 392.26 | 375.80 | 360.07 | Above all MAs | ALMOST | 9.7% above band top (407) — extended |
| NVDA | 216.61 | 190.84 | 185.62 | 183.09 | Above all MAs | ALMOST | 10.1% above band top (197) |
| VRT | 322.43 | 290.15 | 269.72 | 188.09 | Above all MAs | ALMOST | 14.8% above band top (308) — well extended |
| GS | 937.81 | 897.47 | 869.45 | 821.03 | Above all MAs | ALMOST | 1.2% above band top (927) — near-band |
| CAT | 828.79 | 771.22 | 741.99 | 579.81 | Above all MAs | ALMOST | 3.7% above band top (799) |
| GOOG | 348.52 | 319.32 | 309.28 | 277.38 | Above all MAs | BLOCKED | Earnings tomorrow |
| MSFT | 424.82 | 395.37 | 394.46 | 468.29 | Above 20d/50d, below 200d | BLOCKED | Earnings tomorrow |
| AMZN | 261.12 | 236.04 | 219.87 | 226.60 | Above all MAs | BLOCKED | Earnings tomorrow |
| BRK.B | 472.81 | 475.46 | 484.41 | 489.87 | Below all MAs | BENCH | In/near band but chart weak |
| XOM | 148.19 | 154.81 | 154.50 | 125.91 | Above 200d, below 20d/50d | BENCH | Chart weak; await May 1 |
| LMT | 513.35 | 594.12 | 625.58 | 518.97 | Below all MAs | BELOW STOP | Do not touch |
| RTX | 173.38 | 193.06 | 198.48 | 177.40 | Below all MAs | BELOW STOP | Below stop and below band |

**Key technical reads:**
- The "almost deployable" group (JPM, ETN, NVDA, VRT, GS, CAT) is broadly extended. Only JPM and GS are within 2% of their band tops. All others require meaningful pullbacks before discipline allows entry.
- RTX is below its stop (173 vs. stop 186) and well below its band (191–202). This is "do not touch" territory. RTX needs recovery above 186 before the band becomes relevant.
- MSFT is the only tracked name trading below its 200-day MA (424 vs. 468 200-day). This is a technical structural weakness in an otherwise strong market. Watch the post-earnings reaction closely — a failure to rally on a beat could be a structural signal.

---

### 7. Sentiment gauge

- **VIX:** 18.02 as of April 27 (yfinance ^VIX). Moderate fear. Slightly elevated relative to the ATH tape — the market is not complacent. VIX at 18 with SPX at all-time highs suggests investors are hedging the upcoming catalyst cluster (FOMC + Big Tech earnings).
- **S&P 500:** 7,173.91 as of April 27. Four consecutive up weeks. Market is at or near all-time highs.
- **Market breadth:** Only 53% of S&P 500 stocks trade above their 50-day MA (down from 60% a week ago). This is a narrowing breadth warning — the index is being carried by fewer names while the average stock is weakening. A classic late-stage rally warning sign.
- **Chip/Semi momentum:** RSI on chip stocks reportedly above 80. NVDA closed at 216 today (+4% on the day). Overbought conditions do not mean a top, but they do mean the asymmetry for new entries is poor.
- **Earnings sentiment:** 84% of reporting S&P 500 companies have beaten estimates. EPS growth running at 15.1% — materially above the 13.1% expected a week ago. The earnings backdrop is genuinely strong.
- **Oil fear vs. equity resilience:** The combination of Brent back above $100, VIX at 18, and SPX at all-time highs is an unusual tension. The market is either correctly anticipating a Hormuz resolution, or underpricing the ongoing supply shock. This is a risk.

---

### 8. Recommended actions

**Posture:** Selective risk-on. Unchanged from prior week. No new entries now — wait for catalysts to resolve.

**Highest-priority actions this week:**

1. **FOMC (April 29) — no trade, high attention.** Expect hold. Watch the statement language around inflation (especially energy/oil). Any hint of delayed cuts due to energy inflation would be a hawkish signal. If Powell is more dovish than expected on the growth side, that's a mild positive for risk.

2. **GOOG / MSFT / AMZN earnings (April 29) — stay blocked, prep entry bands post-print.** All three remain earnings-blocked. After results, run `post_earnings_prep.py` and use the post-earnings packet to determine whether to update bands or confirm block. Decision framework: beat + constructive guidance = reassess band and consider unlocking. Miss or guide down = extend block or move to bench.

3. **ETN — patience, no chase.** ETN is 9.7% above the band top at 416. The May 5 earnings window is live. Do not enter above band under any circumstances. If it pulls to 383–407 before May 5, evaluate entry only with the earnings window explicitly factored into sizing.

4. **JPM — closest to deployable.** At 311.63 vs. band 300–306, JPM is the nearest-to-deployable name with the least extension (1.9% above band top). If macro cooperates post-FOMC and JPM pulls toward 305–306, this is the best risk/reward near-term opportunity.

5. **XOM — watch for May 1 requalification.** With WTI at $97, XOM's Q1 earnings quality is substantially better than the setup when the repair call was made. A clean beat with constructive guidance on May 1 is the trigger to reassess the entry band and consider establishing a position. Do not move early.

6. **Earnings date housekeeping — update vault.** LMT earnings date changed: vault shows April 23 (elapsed), yfinance shows July 21 (correct Q2 date). BRK.B: vault shows May 4, yfinance shows May 2. NVDA: vault shows May 27, yfinance shows May 20. Update the Event Calendar and watchlist to reflect these corrections.

**Avoid:**
- Chasing NVDA, VRT, or ETN at current prices. All three are extended well above their bands. The AI momentum is real, but the entry asymmetry at current levels is poor.
- Treating the Hormuz situation as resolved. It is not. Any energy trade should carry explicit awareness of the reversal risk if a deal closes.
- Entering GOOG, MSFT, or AMZN before the April 29 print. The upside from a beat is partially priced in; the downside from a miss is not.

---

## Week of April 14–19, 2026

### Macro pulse

- **Fed funds rate:** 3.5%–3.75% (hold). Fed meets April 28–29. No cut expected at that meeting.
- **Fed cut expectations:** Sharply reduced. Futures now imply roughly one cut in all of 2026, with approximately a 48% probability of zero cuts. This is a meaningful hawkish repricing from earlier expectations of two cuts. Treat this as manually maintained commentary until a stable FedWatch workflow is wired; do not present it as live machine-fed output.
- **2Y Treasury:** 3.71% as of 2026-04-17 (FRED DGS2 via `scripts/market_state_refresh.py`).
- **10Y Treasury:** 4.25% as of 2026-04-20 (live via yfinance ^TNX). Rates remain elevated; bond market may be pricing some growth softening ahead of the April 30 GDP print.
- **2s10s spread:** +54.0 bps using FRED 2Y and yfinance 10Y. Curve remains positively sloped rather than signaling deep inversion panic.
- **3M T-bill:** 3.598% as of 2026-04-20 (live via yfinance ^IRX).
- **3M-10Y spread:** +65.2 bps (live derived).
- **CPI trend:** March 2026 headline +0.9% MoM / +3.3% YoY. Core CPI +0.2% MoM / +2.6% YoY. Energy drove the headline spike during the Hormuz crisis. Core remains cooler than headline fear suggests but still above target.
- **PCE trend:** February 2026 PCE 2.8% YoY. Core PCE 3.0% YoY. Trimmed Mean PCE 2.3% YoY. Stickiness is real but not spiraling.
- **Labor:** Jobless claims 207k for week ending April 11 — below consensus 215k. March 2026 payrolls +178k, unemployment 4.3%. Labor softening at the margin but not breaking.
- **Dollar trend:** Mixed. DXY monitoring warranted. Oil-price collapse following Hormuz ceasefire creates cross-currents for the dollar.

**Regime read:** Late-cycle, restrictive-policy, resilient-growth regime with sticky disinflation. Geopolitical shock (Iran/Hormuz) created an oil spike and spike in uncertainty in March and early April, both now partially unwinding. The base macro regime has not changed — selective risk-on, not euphoric broad risk-on.

---

### Energy sweep

- **Brent crude:** Peaked above $120/barrel during the Strait of Hormuz closure (early March), then crashed following the US-Iran ceasefire (April 7–8). As of April 17 close, Brent at $90.38 (live via yfinance BZ=F) — down a further ~$6 from the ~$96 level cited earlier in this brief. Now ~$30 off the crisis peak and approaching the pre-conflict ~$85 area.
- **WTI crude:** $83.85 as of April 17 close (live via yfinance CL=F) — down from the $92–94 range cited earlier. WTI is now well below $90, which is a psychologically and fundamentally significant level for US producers.
- **EIA inventory (week ending April 10):** US crude inventories fell 913k barrels to 463.8 million — a surprise draw vs. expectations for a 200k build. Cushing hub dropped 1.7 million barrels (largest single-week decline since January 2025). Refinery runs softened.
- **Hormuz posture:** Iran confirmed strait "completely open" after ceasefire. Geopolitical risk premium continuing to drain out of the price. Structural fragility remains but is not being priced.
- **Rig count:** Not updated for this sweep. Monitor for response to sustained price collapse.
- **XOM implication:** Oil has fallen further than previously modeled. Brent $90 and WTI $84 mean the XOM entry band of 142.50–147.50 was set at a materially different oil price level. XOM is technically in that band at 146.44, but the band itself needs to be reassessed against the current oil structure before treating that as an actionable entry signal. XOM should be treated as under review, not deployable, until May 1 earnings plus follow-through from the next EIA reads either repair or break the thesis.

---

### Geopolitical scan

**Iran / Strait of Hormuz — dominant macro event of the month:**

- February 28, 2026: US and Israel launched coordinated airstrikes on Iran (Operation Epic Fury), targeting nuclear sites and military facilities.
- March 2, 2026: Iran closed the Strait of Hormuz. IRGC confirmed closure, launched 21 confirmed attacks on merchant ships, reportedly laid sea mines. Gulf producers collectively lost ~6.7M barrels/day by March 10, and at least 10M bpd by March 12. QatarEnergy declared force majeure on all LNG exports.
- April 7–8, 2026: US-Iran ceasefire announced. Iran confirmed Hormuz is "completely open."
- As of April 19: Ceasefire holding. Oil crashing from highs. S&P 500 hit all-time highs April 15. Geopolitical risk premium still partially embedded in oil — do not assume permanent resolution.
- Trump confirmed calls with Lebanese President Aoun and Israeli PM Netanyahu on ceasefire progress.

**Key watch:** Ceasefire durability, Iran nuclear status, residual shipping disruption, and continued US-Israel-Iran diplomatic posture. A breakdown in the ceasefire is the single biggest macro tail risk right now.

---

### Earnings radar

**Already reported:**
- **JPM — April 14, Q1 2026 — Beat.** EPS $5.94 vs. $5.45 estimate (+9.2%). Revenue $50.5B vs. $49.2B estimate (+10% YoY). Fixed income trading +21%, IB fees +28%, ROTCE 23%. Important caveat: JPM trimmed full-year 2026 NII guidance from ~$104.5B to ~$103B. The quality beat was real, but the guidance cut muted the reaction. Mixed signal.

**Reported / fresh read-through:**
- **RTX — April 21, Q1 2026 — Beat and raised outlook.** Reuters and company materials indicate stronger-than-expected Q1 results with higher full-year revenue and profit guidance, driven by defense and aftermarket demand. Useful positive sector read-through for LMT, though the stock reaction was not clean enough to treat it as a setup upgrade by itself.

**Reported / fresh read-through:**
- **VRT — April 22, Q1 2026 — Beat and raised.** Search-visible company materials indicate about $2.65B of Q1 net sales, adjusted EPS near $1.17, and higher full-year guidance. That is a clean positive read-through for AI power, thermal, and infrastructure demand, which supports ETN and the broader power-enabler sleeve. Action implication: thesis quality improved, but VRT still stays in wait-for-levels mode because the setup remains crowded and the technical sheet still lacks a defined entry band.

**Upcoming — next 2 weeks (critical):**
- **NOC — April 21.** Newly confirmed from the script pass. Another useful defense tone-setter ahead of LMT, especially when paired with the positive RTX read-through rather than judged as a one-off data point.
- **LMT — April 23, pre-market.** Q1 2026. Analyst consensus EPS $6.73 (down 7.6% YoY vs. $7.28). LMT is up ~26% YTD 2026. Watch for defense budget commentary, F-35 delivery updates, and any geopolitical-demand guidance upgrade.
- **MSFT — April 29, after close.** Q3 FY2026. Azure growth rate, Copilot monetization, and cloud margins are the key variables. Do not add to MSFT ahead of earnings without a defined entry plan.
- **GOOG — April 29, after close.** Q1 2026. Search resilience vs. AI disruption narrative is the key read. Advertising demand and Google Cloud revenue are the primary drivers.
- **ETN — Apr 30 to May 5 timing window, unresolved.** Older cross-check work pointed to Apr 30 rather than May 5, but the latest `tmp/earnings-calendar.json` now shows May 5 again. Treat the exact date as unresolved and verify against Eaton IR before using the earnings window for timing-sensitive deployment decisions.
- **XOM — May 1.** Q1 2026. Results will cover the peak of the Hormuz disruption period. Energy pricing and production impact will be the focus.
- **BRK.B — May 2?, likely date change.** Script-assisted cross-check points to May 2 rather than May 4, but this pass did not produce a clean Berkshire earnings-date confirmation page. Treat the event as potentially earlier than previously logged, not fully confirmed.
- **PLTR — May 4.** Newly confirmed from the script pass. Not a core name, but relevant for defense-tech and AI software tone.
- **SMCI — May 5.** Newly confirmed from the script pass. Useful high-beta AI server supply-chain read-through.
- **NVDA — May 20?, likely date change.** Script-assisted cross-check points to May 20 rather than May 27, but NVIDIA IR blocked direct fetch and secondary-source confirmation quality was weak. Treat this as a likely but unconfirmed change.

---

### Analyst and institutional flow

- **MSFT:** Upgraded by Envision Research (early April 2026). Analysts cited attractive P/E entry point.
- **NVDA:** Upgraded to Buy mid-April 2026 as AI trade showed signs of re-acceleration following the market recovery.
- **GOOG:** No specific notable upgrade or downgrade found this sweep.
- **ETN:** No specific notable upgrade or downgrade found this sweep.
- **JPM:** Post-earnings, the NII guidance trim has analysts watching whether guidance conservatism is idiosyncratic or signals a broader net interest income headwind across financials.
- **Insider / 13F signals:** No specific notable signals found this cycle. 13F filings for Q1 2026 will become available in mid-May — add to May sweep.

---

### Technical check

*Based on April 17 close data. Full precision refresh needed this week before the earnings cascade begins.*

- **ETN:** Best technical posture in the portfolio. Bullish MA stack (20 > 50 > 200). Close: 406.21. Preferred entry band 388–396. Do not chase above 410. Treat it as conditional Tier 2, not fully actionable, until price and earnings-window timing stop fighting the setup.
- **JPM:** Above all three MAs. One of the cleaner setups. Close: 310.29. Preferred entry 300–306. NII guidance overhang is a fundamental consideration, not a technical one.
- **GOOG:** Above all three MAs. Constructive trend posture. Close: 339.40. Preferred entry 314–321. Do not buy into April 29 earnings resistance without a plan.
- **MSFT:** Above 20 and 50-day but still below 200-day (471.96). Rebound real but trend not fully repaired. Close: 422.79. Preferred entry 393–401. Do not chase near resistance (~431).
- **NVDA:** Above all three clustered MAs. Close: 201.68. Preferred entry 186–191. Do not chase at or above 201.
- **LMT:** Below 20 and 50-day, above 200-day. Close: 592.19. Stance: Close but patient. 588 area is critical support. Reports Tuesday April 23.
- **XOM:** Below 20 and 50-day, above 200-day. Close: 146.44. Oil crash muddies the entry zone. Patience required, and the name should stay under review rather than be framed as a normal near-term core add.
- **BRK.B:** Below all three MAs. Close: 474.58. Still in repair mode. Patience required before treating 465–472 as actionable.
- **S&P 500:** New all-time high at 7,126.06 as of April 17 close (live via yfinance ^GSPC) — extended above the prior 7,041.28 ATH. Market is not cheap and is now further extended. Entry discipline matters more at these levels, not less.

---

### Sentiment gauge

- **VIX:** 17.48 as of April 17 close (live via yfinance ^VIX) — down from ~19.12 mid-April and down ~44% from the March 27 high of 31. Approaching complacency territory (sub-15 = complacent). Fear has effectively evaporated at new all-time equity highs.
- **S&P 500:** New all-time high at 7,126.06 as of April 17 close. Nasdaq posted 12 consecutive positive sessions — longest winning streak since 2009.
- **Put/call ratio:** Not specifically sourced this sweep. Add to next weekly update.
- **Overall read:** Sentiment has swung from fear (March, VIX 31, Hormuz crisis) to confidence bordering on complacency (April 17, VIX 17.48, new all-time highs above 7,100). VIX at 17.48 with S&P at 7,126 is a combination that historically rewards patience and punishes chasing. This is not a time to be aggressive — it is a time to be disciplined and wait for earnings to set new levels.

---

### Risk flags

1. **Ceasefire durability.** The Iran ceasefire is the single biggest risk variable right now. A breakdown returns oil toward $120, re-spikes VIX, and creates broad market stress. Defense names would rally; growth equities would sell off.
2. **Fed tone at April 28–29 meeting.** No cut expected, but Powell's commentary on inflation persistence and the rate path is a major market catalyst. A hawkish surprise from the all-time-high market level could create sharp equity pressure.
3. **Earnings risk — LMT (April 23), MSFT and GOOG (April 29).** Three of the eight draft portfolio names report in the next 10 days. These are binary events. Avoid adding aggressively to these positions ahead of results.
4. **Oil price structure post-ceasefire.** Brent is now closer to ~$90 rather than the earlier ~$96 framing, and that drop matters. If the ceasefire holds and supply normalizes, XOM and energy names face further price pressure. If ceasefire breaks, supply risk returns fast. The practical implication is that XOM stays under review until both earnings and EIA evidence clarify the path.
5. **JPM NII guidance trim.** Full-year 2026 NII guided down from $104.5B to ~$103B. If other financials echo this, the financial sector thesis weakens at the margin.
6. **Valuation at all-time highs.** S&P 500 at 7,041 with a restrictive Fed and sticky inflation is not a cheap market. Indiscriminate buying at these levels is a discipline failure.
7. **Energy geopolitical tail.** Iran conflict is in ceasefire, not resolved. The Hormuz risk remains a tail event that can return quickly.

---

### Recommended actions

1. **Hold and do not chase.** Market is at all-time highs, VIX is at 19, and several key portfolio names report earnings in the next 10 days. This is not a moment for aggressive new positioning. The discipline here is patience.

2. **Use NOC and RTX as the defense workflow input for LMT.** LMT is still blocked and below stop in `tmp/deployment-check.json`, so no pre-earnings anticipation trade is justified. But post-print interpretation should explicitly use the NOC and RTX read-throughs rather than treating LMT as an isolated event.

3. **Keep XOM under review, not on standby buy mode.** The oil crash from $120 to the $92–96 range has fundamentally changed the near-term picture for XOM. The long-term energy thesis is intact but the chart and entry need a fresh pass. Requalification requires May 1 earnings plus the next EIA reads, not just price drifting into an old band.

4. **ETN remains the cleanest conditional setup, and VRT's print helps the thesis.** Best MA posture in the portfolio, and VRT's beat-and-raise strengthens the AI power-demand backdrop, but ETN still is not a chase. If ETN pulls back toward the 388–396 entry band and the earnings window is directly confirmed, that is still the clearest defined opportunity in the current setup.

5. **Keep VRT on the watch list, not in impulsive promotion mode.** The earnings read improved conviction, but without defined entry and stop levels it remains a selective follow-up name rather than a deployment candidate.

6. **Keep the refreshed files aligned.** Deployment, technical, portfolio, and calendar notes now need to carry the same message: sizing stays inside rules, earnings blocks stay real, ETN is conditional Tier 2, VRT got a positive demand-confirmation read-through without becoming a chase, and XOM stays under review until evidence improves.

---

## Freshness and refresh policy

- Last updated: 2026-04-22
- Data as of: mixed weekly sweep data through 2026-04-22, including refreshed `tmp/market-state.json`, `tmp/earnings-calendar.json`, and `tmp/deployment-check.json`; macro context is now materially stronger because 2Y Treasury and true 2s10s are live again, while FedWatch remains unwired and the Fed target range is still a maintained hardcoded input
- Refresh cadence: weekly, plus after major macro shocks, key portfolio earnings, Fed meetings, or geopolitical events that change the regime read
- Next refresh due: post-LMT earnings and before MSFT/GOOG results
- Refresh policy: refresh only when the macro read, catalyst map, technical implications, or recommended actions materially change. Keep prior conclusions only if they still survive current evidence.

## Timestamp

- Written: 2026-04-19
- Data currency: live 2Y / 10Y / 3M / SPX / VIX / DXY / oil inputs through 2026-04-21 from `tmp/market-state.json`, with 2Y restored via FRED DGS2 and true 2s10s back online. FedWatch remains unwired and the Fed target range remains a maintained hardcoded field. JPM earnings April 14. RTX earnings April 21. Earnings dates remain a mix of confirmed company materials and script-assisted cross-checks where explicitly noted.
- Next scheduled update: post-LMT earnings, pre-MSFT/GOOG results.
- 2026-04-22 — tightened operating language: ETN stays conditional until timing ambiguity is resolved, XOM remains under review pending earnings plus EIA follow-through, and the template now requires EIA actual/prior/consensus structure rather than vague inventory notes.
- 2026-04-22 (later) — added VRT as a reported beat-and-raise with positive AI power-demand read-through, while keeping the action stance disciplined because the post-earnings setup is still undefined.

---

## [Template — for future weeks]

### Macro pulse
- Fed funds rate:
- Fed cut probability / FedWatch:
- 2Y / 10Y / curve posture:
- CPI / PPI / PCE trend:
- Labor trend: NFP and jobless claims
- Dollar trend:

### Energy sweep
- Brent / WTI structure:
- Most recent EIA inventories: crude [actual vs prior vs consensus], gasoline [actual vs prior vs consensus], distillates [actual vs prior vs consensus], refinery utilization [actual vs prior vs consensus], source-labeled when available
- Rig count:
- Key geopolitical pressure points affecting energy:

### Geopolitical scan
- Developments affecting energy or defense names:

### Earnings radar
- Upcoming earnings in the next 14 days for any Coverage Universe name:
- Important peers reporting:
- Key macro events in the next 14 days from Event Calendar:

### Analyst and institutional flow
- Upgrades / downgrades on tracked names:
- Analyst flow on tracked names:
- Insider or 13F signals:
- Notable positioning changes:

### Technical check
- Key support and resistance updates:
- Trend posture for top names:

### Sentiment gauge
- VIX level and trend:
- S&P 500 level and trend:
- Put / call ratio:
- Fear and greed or similar signals:

### Risk flags
-

### Recommended actions
1.
2.
3.

## Timestamp
-

---

## Week of April 27–May 3, 2026

*Auto-generated by `scripts/weekly_intelligence_brief.py` on 2026-04-27 22:36. Data as of 2026-04-27 close. Sources: tmp/market-state.json, tmp/trigger-sheet.json, tmp/earnings-calendar.json, tmp/post-earnings-prep.json, tmp/technical-refresh.json, tmp/regime-scores.json. Sections marked _judgment_ require human/AI completion.*

---

### 1. Macro pulse

- **Fed funds rate:** 3.50%–3.75% (confirmed 2026-04-19). Next FOMC 2026-04-29.
- **Fed cut expectations:** FedWatch unwired (manual read required).
- **2Y Treasury:** 3.780% as of 2026-04-24 (FRED DGS2).
- **10Y Treasury:** 4.336% as of 2026-04-27 (yfinance ^TNX).
- **3M T-bill:** 3.590% as of 2026-04-27 (yfinance ^IRX).
- **2s10s spread:** 55.6 bps.
- **3M-10Y spread:** 74.6 bps.
- **Inflation (judgment):** _[Fill: latest CPI/PCE prints, MoM and YoY]_.
- **Growth (judgment):** _[Fill: latest GDP estimate, jobless claims, payrolls]_.
- **Dollar:** DXY 98.53 as of 2026-04-27.

**Regime read (judgment):** _[Fill: 2-3 sentence synthesis tying the above into a regime read for the week]_.

---

### 2. Energy sweep

- **Brent crude:** $102.10 as of 2026-04-27 (yfinance BZ=F).
- **WTI crude:** $96.89 as of 2026-04-27 (yfinance CL=F).
- **Brent/WTI spread:** $5.21.
- **EIA inventory (judgment):** _[Fill: latest weekly crude / gasoline / distillate actual vs. consensus, refinery utilization]_.
- **Rig count (judgment):** _[Fill: latest Baker Hughes if available]_.
- **XOM / CVX implication (judgment):** _[Fill: how does current oil structure change earnings setup or entry framing?]_

---

### 3. Geopolitical scan

- **Hot items (judgment):** _[Fill: Iran/Hormuz, Russia/Ukraine, China/Taiwan, sanctions, election cycles]_.
- **Defense / energy implication (judgment):** _[Fill: which tracked names get tailwind or headwind from current geopolitics?]_
- **Key watch:** _[Fill: 1-2 specific developments that would shift conviction this week]_.

---

### 4. Earnings radar

**Reported this week (Apr 27–May 03):**
- No tracked-universe reports captured this week (or post-earnings packets not staged).

**Earnings this week (calendar — tracked universe):**
- **GD** — 2026-04-29.
- **MSFT** — 2026-04-29.
- **GOOG** — 2026-04-29.
- **EQIX** — 2026-04-29.
- **AMZN** — 2026-04-29.
- **COP** — 2026-04-30.
- **CAT** — 2026-04-30.
- **XOM** — 2026-05-01.
- **CVX** — 2026-05-01.
- **BRK.B** — 2026-05-02.

**Coming next week (May 04–May 10):**
- **WMB** — 2026-05-04.
- **PLTR** — 2026-05-04.
- **EOG** — 2026-05-05.
- **ET** — 2026-05-05.
- **MPLX** — 2026-05-05.
- **LDOS** — 2026-05-05.
- **ETN** — 2026-05-05.
- **AMD** — 2026-05-05.
- **SMCI** — 2026-05-05.
- **KTOS** — 2026-05-06.
- **LNG** — 2026-05-07.

---

### 5. Analyst and institutional flow

- **Upgrades / downgrades (judgment):** _[Fill: notable rating changes on tracked names this week]_.
- **13F flow (judgment):** _[Fill: institutional positioning changes if any are in the cycle]_.
- **Insider activity (judgment):** _[Fill: notable Form 4 prints]_.

---

### 6. Technical check

*Data: tmp/technical-refresh.json + tmp/trigger-sheet.json.*

| Ticker | Close | MA20 | MA50 | MA200 | Posture | State | Notes |
|---|---|---|---|---|---|---|---|
| ETN | 416.77 | 392.26 | 375.80 | 360.07 | above all MAs -- bullish 20>50>200 stack | ALMOST DEPLOYABLE | +2.3% above band top (407.22) |
| JPM | 311.63 | 305.43 | 298.12 | 301.68 | above all MAs | ALMOST DEPLOYABLE | +1.8% above band top (306.00) |
| GOOG | 348.52 | 319.32 | 309.28 | 277.38 | above all MAs -- bullish 20>50>200 stack | BLOCKED | +6.5% above band top (327.31) |
| MSFT | 424.82 | 395.37 | 394.46 | 468.29 | above 20d and 50d, below 200d | BLOCKED | +3.8% above band top (409.16) |
| LMT | 513.35 | 594.12 | 625.58 | 518.97 | below all MAs | DO NOT TOUCH | Post-earnings rebuild only |
| BRK.B | 472.81 | 475.46 | 484.41 | 489.87 | below all MAs | DO NOT TOUCH | +0.2% above band top (472.00) |
| XOM | 148.19 | 154.81 | 154.50 | 125.91 | above 200d, below 20d and 50d | DO NOT TOUCH | Requalify above 141.97 and reclaim 50d |
| NVDA | 216.61 | 190.84 | 185.62 | 183.09 | above all MAs -- bullish 20>50>200 stack | ALMOST DEPLOYABLE | +10.1% above band top (196.82) |
| AMZN | 261.12 | 236.04 | 219.87 | 226.60 | above all MAs | BLOCKED | +7.1% above band top (243.73) |
| VRT | 322.43 | 290.15 | 269.72 | 188.09 | above all MAs -- bullish 20>50>200 stack | ALMOST DEPLOYABLE | +4.8% above band top (307.64) |
| RTX | 173.38 | 193.06 | 198.48 | 177.40 | below all MAs | DO NOT TOUCH | -9.3% below band bot (191.15) |
| CAT | 828.79 | 771.22 | 741.99 | 579.81 | above all MAs -- bullish 20>50>200 stack | ALMOST DEPLOYABLE | +3.8% above band top (798.83) |
| GS | 937.81 | 897.47 | 869.45 | 821.03 | above all MAs -- bullish 20>50>200 stack | ALMOST DEPLOYABLE | +1.2% above band top (926.76) |

**Technical reads (judgment):** _[Fill: 2-3 sentences summarizing where the universe sits structurally and which names are closest to actionable]_.

---

### 7. Sentiment gauge

- **VIX:** 18.02 as of 2026-04-27.
- **S&P 500:** 7,173.91 as of 2026-04-27.
- **Put/call ratio (judgment):** _[Fill if available]_.
- **Breadth (judgment):** _[Fill: % of SPX above 50d/200d, advance/decline if available]_.
- **Sentiment read (judgment):** _[Fill: complacent / neutral / fearful and what that implies for entry timing]_.

---

### 8. Recommended actions

**Posture (judgment):** _[Selective risk-on / Defensive-neutral / Defensive — state basis]_.

**Highest-priority actions this week:**

1. **Earnings cluster — stay disciplined.** AMZN, GOOG, MSFT are blocked or imminent. Run `post_earnings_prep.py` after each print and re-evaluate band/state from data, not narrative.
2. **Almost-deployable watch.** CAT, ETN, GS, JPM, NVDA, VRT are conditional on pullbacks into band. No chase above the written entry zone.
3. **Repair / do-not-touch.** BRK.B, LMT, RTX, XOM stay off the board until structure repairs.
4. _[Fill judgment-driven priority — what's the single most important call for this week?]_

**Avoid:**
- Overriding earnings blocks on **AMZN, GOOG, MSFT**.
- Chasing any name extended above its band.
- Treating geopolitical situations as resolved without explicit evidence.
