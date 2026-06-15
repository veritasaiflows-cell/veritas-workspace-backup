# Regime Scoring Matrix

## Purpose

Score every tracked name against the current macro regime on four dimensions. Produces a ranked, sortable review-support list for triage and comparison.

**Authority boundary:** This is a controlled machine-companion ranking note, not final canonical deployment truth. `scripts/regime_scoring_refresh.py` may update the scoring, ranking, and freshness blocks here, but final action authority remains with the [[03. Portfolio/Execution Board]], [[03. Portfolio/Portfolio Snapshot]], [[07. Risk/Risk Rules]], and explicit owner approval.

**Use correctly:** A high score means "review first," not "deploy." The Execution Board owns deployable / almost / blocked / do-not-touch states; the Portfolio Snapshot owns sizing and posture; Risk Rules own concentration and escalation limits.

---

## Scoring dimensions (each 1–5)

| Dimension | 1 | 3 | 5 |
|---|---|---|---|
| **Regime Fit** | Fights the current regime — wrong sector, wrong duration, wrong sensitivity | Neutral — works in some scenarios but not regime-tailored | Perfect fit — exactly what outperforms in late-cycle, restrictive, selective risk-on |
| **Technical Posture** | Broken setup — below key MAs, no defined entry, chart in repair mode | Constructive but extended, or in band with weak MA structure | At or near entry band with bullish MA stack — clean actionable setup |
| **Catalyst Risk** | Imminent binary event within 7 days — cannot size in front of it | Moderate catalyst risk — event within 30 days requiring monitoring | Clean — no binary event for 30+ days, or event has already passed constructively |
| **Fundamental Conviction** | Thesis impaired — miss, guidance cut, or structural weakness confirmed | Solid thesis with manageable risks | Exceptional quality — durable earnings, fortress balance sheet, irreplaceable competitive position |

**Total:** Sum of all four dimensions, out of 20. Higher = higher priority.

**Tie-breaking rule:** Ties broken by Fundamental Conviction, then Catalyst Risk (higher = cleaner).

---

## Current scoring — as of 2026-06-15 (data: 2026-06-15 close)

| Ticker | Regime Fit | Technical Posture | Catalyst Risk | Fund. Conviction | **Total** | Current Stance | Notes |
|---|---|---|---|---|---|---|---|
| **GOOG** | 5 | 4 | 5 | 5 | **19** | PROMOTION REVIEW | in band. Earnings in 38d |
| **MSFT** | 5 | 4 | 5 | 5 | **19** | PROMOTION REVIEW | in band. Earnings in 44d. Intact; owner-approved staged manual candidacy recorded on 2026-05-12 after msft/goog/nvda growth review; live trigger currently inactive while price is above written band |
| **ETN** | 5 | 4 | 5 | 4 | **18** | Almost deployable | 0.8% above band. Earnings in 50d. Intact; owner-approved tier 1 explicit add on 2026-05-10 after fresh band review |
| **NVDA** | 5 | 4 | 5 | 4 | **18** | PROMOTION REVIEW | in band. Intact / thesis strengthened by q1 fy2027 post-earnings official review, but crowded and above-band |
| **RTX** | 5 | 5 | 5 | 3 | **18** | Watch | in band. Earnings in 36d. Under active review |
| **JPM** | 4 | 4 | 4 | 5 | **17** | Almost deployable | 3.8% above band. Earnings in 29d. Intact; prior owner approval recorded on 2026-05-07, but current trigger is not live. fresh 2026-05-22 artifact layer places jpm above the 301.50 to 307.78 reference band, so current posture is wait/no-chase pending fresh review. |
| **VRT** | 5 | 4 | 5 | 3 | **17** | PROMOTION REVIEW | in band. Earnings in 44d. Owner-promoted 2026-05-29 into formal ai-power tactical challenger / starter-sizing planning after q1 2026 beat-and-raise; etn remains primary and concentration discipline remains binding. |
| **PH** | 5 | 4 | 5 | 3 | **17** | PROMOTION REVIEW | 1.1% above band. Earnings in 52d. Owner-approved portfolio-review candidate 2026-05-15; best higher-rate-resilient industrial compounder from sector-expansion pass. review-only: requires technical levels, valuation discipline, concentration/risk check, and separate owner decision before any model allocation or deployment. |
| **XLI** | 5 | 4 | 5 | 3 | **17** | Watch | 3.0% above band. Promoted 2026-05-15 to coverage universe as etf monitor only |
| **GS** | 4 | 4 | 4 | 4 | **16** | Almost deployable | 4.6% above band. Earnings in 29d. Intact but secondary to jpm for primary bank exposure |
| **AMZN** | 5 | 3 | 5 | 3 | **16** | Watch | near stop: close 246.02 is 1.21 above stop 244.81; 2.5% below band low 252.27. Earnings in 45d. Intact but technically underdefined |
| **CAT** | 5 | 3 | 5 | 3 | **16** | Watch | 7.8% above band. Earnings in 50d. Under active review |
| **PLTR** | 5 | 3 | 5 | 3 | **16** | Watch | 1.9% below band low. Earnings in 49d. Higher-risk tactical narrative |
| **VMC** | 3 | 5 | 5 | 3 | **16** | Watch | in band. Earnings in 45d. Promoted 2026-05-15 to machine-tracked infrastructure/aggregates materials monitor |
| **XLF** | 4 | 4 | 5 | 3 | **16** | Watch | 0.9% above band. Promoted 2026-05-15 to coverage universe as etf monitor only |
| **KTOS** | 5 | 2 | 5 | 3 | **15** | Watch | Earnings in 52d. Speculative asymmetry |
| **AMD** | 5 | 2 | 5 | 3 | **15** | Watch | 59.8% above band. Earnings in 50d. Event-driven ai watch |
| **SMCI** | 5 | 2 | 5 | 3 | **15** | Watch | Earnings in 50d. Speculative ai infrastructure monitor |
| **LIN** | 3 | 4 | 5 | 3 | **15** | PROMOTION REVIEW | 3.0% above band. Earnings in 46d. Owner-promoted 2026-05-19 into formal materials sleeve / starter-sizing planning after lin owner-review packet; quality case accepted for planning, but premium valuation and top-of-band entry discipline remain blockers before any execution. |
| **XLB** | 3 | 4 | 5 | 3 | **15** | PROMOTION REVIEW | 1.6% above band. Owner-promoted 2026-05-30 into formal materials etf starter-planning lane after promoted-ticker audit; improving materials leadership and underexposure make xlb the cleaner paper-simulation candidate versus forcing another ai-power name. |
| **PAVE** | 3 | 4 | 5 | 3 | **15** | Watch | 3.4% above band. Promoted 2026-05-15 to coverage universe as etf monitor only |
| **XLE** | 4 | 3 | 5 | 3 | **15** | Watch | 1.4% below band low. Promoted 2026-05-15 to coverage universe as etf monitor only |
| **VAW** | 3 | 4 | 5 | 3 | **15** | Watch | 1.5% above band. Promoted 2026-05-15 to coverage universe as etf monitor only |
| **VXUS** | 3 | 4 | 5 | 3 | **15** | Watch | 4.3% above band. Added 2026-05-18 to tracked_universe to close entry-band orphan after official vanguard proof and review-only band fix; not execution-ready and no allocation/sizing/trade authority. |
| **ECL** | 3 | 3 | 5 | 3 | **14** | Watch | 1.0% below band low. Earnings in 43d. Promoted 2026-05-15 to machine-tracked materials-adjacent research monitor; defensive compounder candidate |
| **GE** | 3 | 3 | 5 | 3 | **14** | Watch | 9.8% above band. Earnings in 31d. Promoted 2026-05-15 to machine-tracked aerospace quality / defense-commercial gap monitor |
| **WMB** | 3 | 3 | 5 | 3 | **14** | Watch | 2.4% below band low. Earnings in 49d. Promoted 2026-05-15 to machine-tracked gas infrastructure / power-demand monitor |
| **ITA** | 3 | 3 | 5 | 3 | **14** | PROMOTION REVIEW | 6.2% above band. Owner-promoted 2026-05-18 to review-only paper-candidate queue after official ishares/blackrock holdings proof; not execution-ready and no allocation/sizing/trade authority. |
| **CVX** | 4 | 1 | 5 | 3 | **13** | Do not touch | stop breached: close 180.40 is 1.76 below stop 182.16; 3.5% below band low 186.91. Earnings in 46d. Secondary energy read-through |
| **LNG** | 4 | 1 | 5 | 3 | **13** | Do not touch | stop breached: close 235.25 is 18.20 below stop 253.45; 9.8% below band low 260.82. Earnings in 52d. Event-driven lng export watch |
| **TLT** | 3 | 2 | 5 | 3 | **13** | Watch | Macro duration hedge |
| **LLY** | 3 | 2 | 5 | 3 | **13** | Watch | 16.4% above band. Earnings in 51d. Workflow 7 healthcare watch-lane pilot — preferred sector leader over jnj for first sleeve monitor |
| **SLV** | 2 | 2 | 5 | 3 | **12** | Watch | Macro hedge |
| **META** | 3 | 1 | 5 | 3 | **12** | Do not touch | stop breached: close 593.48 is 62.07 below stop 655.55; 11.8% below band low 672.60. Earnings in 44d. Owner-approved portfolio-review candidate 2026-05-15; strongest communication services fundamental candidate. review-only: direct tech/ai/platform crowding, capex/regulatory risk, and underdefined technical setup block any model allocation or deployment. |
| **NFLX** | 3 | 1 | 5 | 3 | **12** | Do not touch | stop breached: close 81.67 is 18.57 below stop 100.24; 20.4% below band low 102.56. Earnings in 31d. Promoted 2026-05-15 to machine-tracked communication services subscription/media quality monitor |
| **TMUS** | 3 | 1 | 5 | 3 | **12** | Do not touch | stop breached: close 188.86 is 18.25 below stop 207.11; 11.3% below band low 213.01. Earnings in 37d. Promoted 2026-05-15 to machine-tracked defensive telecom growth monitor |
| **CME** | 3 | 1 | 5 | 3 | **12** | Do not touch | stop breached: close 266.08 is 10.60 below stop 276.68; 7.5% below band low 287.74. Earnings in 37d. Owner-approved portfolio-review candidate 2026-05-15; financial infrastructure diversifier away from bank credit-cycle exposure. review-only: valuation/regime fit and technical discipline remain blockers before any model allocation or deployment. |
| **XLC** | 3 | 1 | 5 | 3 | **12** | Do not touch | stop breached: close 112.19 is 0.52 below stop 112.71; 1.9% below band low 114.31. Promoted 2026-05-15 to coverage universe as etf monitor only |
| **LMT** | 4 | 1 | 5 | 2 | **12** | Do not touch | stop breached: close 530.36 is 1.27 below stop 531.63; 3.3% below band low 548.51. Earnings in 36d. Repair mode. Intact but active model weight suspended while below-stop repair; prior 10% core defense draft weight is not counted as active exposure |
| **BRK.B** | 3 | 2 | 5 | 2 | **12** | Do not touch | in band. Earnings in 47d. Repair mode |
| **XOM** | 3 | 1 | 5 | 2 | **11** | Do not touch | stop breached: close 140.92 is 5.22 below stop 146.14; 6.2% below band low 150.24. Earnings in 46d. Repair mode. Intact long-term, weaker near-term |
| **BKNG** | 2 | 2 | 5 | 2 | **11** | Do not touch | 2.2% above band. Earnings in 44d. Repair mode. Consumer discretionary tier 1 research candidate approved for watchlist on 2026-05-10; no deployment authority |
---

## Priority ranking (current)

1. **GOOG** — 19 — in band
2. **MSFT** — 19 — in band; intact; owner-approved staged manual candidacy recorded on 2026-05-12 after MSFT/GOOG/NVDA growth review; live trigger currently inactive while price is above written band
3. **ETN** — 18 — 0.8% above band; intact; owner-approved Tier 1 explicit add on 2026-05-10 after fresh band review
4. **NVDA** — 18 — in band; intact / thesis strengthened by Q1 FY2027 post-earnings official review, but crowded and above-band
5. **RTX** — 18 — in band; under active review
6. **JPM** — 17 — 3.8% above band; intact; prior owner approval recorded on 2026-05-07, but current trigger is not live. Fresh 2026-05-22 artifact layer places JPM above the 301.50 to 307.78 reference band, so current posture is wait/no-chase pending fresh review.
7. **VRT** — 17 — in band; Owner-promoted 2026-05-29 into formal AI-power tactical challenger / starter-sizing planning after Q1 2026 beat-and-raise; ETN remains primary and concentration discipline remains binding.
8. **PH** — 17 — 1.1% above band; Owner-approved portfolio-review candidate 2026-05-15; best higher-rate-resilient industrial compounder from sector-expansion pass. Review-only: requires technical levels, valuation discipline, concentration/risk check, and separate owner decision before any model allocation or deployment.
9. **XLI** — 17 — 3.0% above band; promoted 2026-05-15 to coverage universe as ETF monitor only
10. **GS** — 16 — 4.6% above band; intact but secondary to JPM for primary bank exposure
11. **AMZN** — 16 — near stop: close 246.02 is 1.21 above stop 244.81; 2.5% below band low 252.27; intact but technically underdefined
12. **CAT** — 16 — 7.8% above band; under active review
13. **PLTR** — 16 — 1.9% below band low; higher-risk tactical narrative
14. **VMC** — 16 — in band; promoted 2026-05-15 to machine-tracked infrastructure/aggregates Materials monitor
15. **XLF** — 16 — 0.9% above band; promoted 2026-05-15 to coverage universe as ETF monitor only
16. **KTOS** — 15 — speculative asymmetry
17. **AMD** — 15 — 59.8% above band; event-driven AI watch
18. **SMCI** — 15 — speculative AI infrastructure monitor
19. **LIN** — 15 — 3.0% above band; Owner-promoted 2026-05-19 into formal Materials sleeve / starter-sizing planning after LIN owner-review packet; quality case accepted for planning, but premium valuation and top-of-band entry discipline remain blockers before any execution.
20. **XLB** — 15 — 1.6% above band; Owner-promoted 2026-05-30 into formal Materials ETF starter-planning lane after promoted-ticker audit; improving Materials leadership and underexposure make XLB the cleaner paper-simulation candidate versus forcing another AI-power name.
21. **PAVE** — 15 — 3.4% above band; promoted 2026-05-15 to coverage universe as ETF monitor only
22. **XLE** — 15 — 1.4% below band low; promoted 2026-05-15 to coverage universe as ETF monitor only
23. **VAW** — 15 — 1.5% above band; promoted 2026-05-15 to coverage universe as ETF monitor only
24. **VXUS** — 15 — 4.3% above band; Added 2026-05-18 to tracked_universe to close entry-band orphan after official Vanguard proof and review-only band fix; not execution-ready and no allocation/sizing/trade authority.
25. **ECL** — 14 — 1.0% below band low; promoted 2026-05-15 to machine-tracked Materials-adjacent research monitor; defensive compounder candidate
26. **GE** — 14 — 9.8% above band; promoted 2026-05-15 to machine-tracked aerospace quality / defense-commercial gap monitor
27. **WMB** — 14 — 2.4% below band low; promoted 2026-05-15 to machine-tracked gas infrastructure / power-demand monitor
28. **ITA** — 14 — 6.2% above band; Owner-promoted 2026-05-18 to review-only paper-candidate queue after official iShares/BlackRock holdings proof; not execution-ready and no allocation/sizing/trade authority.
29. **CVX** — 13 — stop breached: close 180.40 is 1.76 below stop 182.16; 3.5% below band low 186.91; secondary energy read-through
30. **LNG** — 13 — stop breached: close 235.25 is 18.20 below stop 253.45; 9.8% below band low 260.82; event-driven LNG export watch
31. **TLT** — 13 — macro duration hedge
32. **LLY** — 13 — 16.4% above band; Workflow 7 Healthcare watch-lane pilot — preferred sector leader over JNJ for first sleeve monitor
33. **SLV** — 12 — macro hedge
34. **META** — 12 — stop breached: close 593.48 is 62.07 below stop 655.55; 11.8% below band low 672.60; Owner-approved portfolio-review candidate 2026-05-15; strongest Communication Services fundamental candidate. Review-only: direct Tech/AI/platform crowding, capex/regulatory risk, and underdefined technical setup block any model allocation or deployment.
35. **NFLX** — 12 — stop breached: close 81.67 is 18.57 below stop 100.24; 20.4% below band low 102.56; promoted 2026-05-15 to machine-tracked Communication Services subscription/media quality monitor
36. **TMUS** — 12 — stop breached: close 188.86 is 18.25 below stop 207.11; 11.3% below band low 213.01; promoted 2026-05-15 to machine-tracked defensive telecom growth monitor
37. **CME** — 12 — stop breached: close 266.08 is 10.60 below stop 276.68; 7.5% below band low 287.74; Owner-approved portfolio-review candidate 2026-05-15; financial infrastructure diversifier away from bank credit-cycle exposure. Review-only: valuation/regime fit and technical discipline remain blockers before any model allocation or deployment.
38. **XLC** — 12 — stop breached: close 112.19 is 0.52 below stop 112.71; 1.9% below band low 114.31; promoted 2026-05-15 to coverage universe as ETF monitor only
39. **LMT** — 12 — stop breached: close 530.36 is 1.27 below stop 531.63; 3.3% below band low 548.51; setup broken; intact but active model weight suspended while below-stop repair; prior 10% Core Defense draft weight is not counted as active exposure
40. **BRK.B** — 12 — in band; setup broken
41. **XOM** — 11 — stop breached: close 140.92 is 5.22 below stop 146.14; 6.2% below band low 150.24; setup broken; intact long-term, weaker near-term
42. **BKNG** — 11 — 2.2% above band; setup broken; Consumer Discretionary Tier 1 research candidate approved for watchlist on 2026-05-10; no deployment authority

Last auto-scored: 2026-06-15
---

## Score change triggers

Re-score a name when any of the following occur:
- Earnings reported (Catalyst Risk changes; Fundamental Conviction may change)
- Price moves >5% relative to entry band (Technical Posture changes)
- Macro regime shifts (Regime Fit changes across the board)
- Thesis impairment from primary data (Fundamental Conviction changes)
- 30-day binary event window clears (Catalyst Risk changes)

---

## Regime context for current scores

**Current regime:** Late-cycle, restrictive-policy, resilient-growth, selective risk-on.

**Regime fit scoring rationale:**
- Score 5: AI infrastructure (ETN, VRT, NVDA, MSFT), defense (LMT), energy quality (XOM) — all outperform in this regime
- Score 4: Financials (JPM, GS), large-cap platform quality (GOOG, AMZN, BRK.B), aerospace (RTX)
- Score 3 or below: Long-duration speculative growth, leveraged businesses, narrative-only plays — not in current tracked universe

---

## Freshness and refresh policy

- Last updated: 2026-06-15 — auto-scored by regime_scoring_refresh.py
- Data as of: 2026-06-15 close
- XOM source check: the confirmed May 11 close is **149.68** from Exxon IR / LSEG and `tmp/technical-refresh.json`; the previously surfaced **144.57** value came from an incomplete/stale May monthly entry-band candle and must not be treated as the daily close.
- Refresh cadence: after weekly technical refresh, after tracked earnings, after material regime change
- Next refresh due: after the next weekly technical/deployment refresh, after NVDA May 20 timing/earnings risk is rechecked, or immediately after any fresh stop/band/catalyst break
- Refresh policy: update scores when underlying inputs change materially. Do not adjust scores for minor price noise. When re-scoring, note what changed and why in the "Notes" column.
