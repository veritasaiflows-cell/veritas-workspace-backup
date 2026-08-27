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

## Current scoring — as of 2026-08-21 (data: 2026-08-21 close)

| Ticker | Regime Fit | Technical Posture | Catalyst Risk | Fund. Conviction | **Total** | Current Stance | Notes |
|---|---|---|---|---|---|---|---|
| **GOOG** | 5 | 4 | 5 | 5 | **19** | PROMOTION REVIEW | near stop: close 341.75 is 0.68 above stop 341.07; 3.5% below band low 354.25. Earnings in 68d |
| **NVDA** | 5 | 5 | 5 | 4 | **19** | PROMOTION REVIEW | 1.2% above band. Intact / thesis strengthened by q1 fy2027 post-earnings official review, but crowded and above-band |
| **JPM** | 4 | 4 | 5 | 5 | **18** | Almost deployable | 11.3% above band. Earnings in 53d. Intact; prior owner approval recorded on 2026-05-07, but current trigger is not live. fresh 2026-05-22 artifact layer places jpm above the 304.96 to 315.95 reference band, so current posture is wait/no-chase pending fresh review. |
| **ETN** | 5 | 4 | 5 | 4 | **18** | DEPLOYABLE NOW | 3.8% above band. Earnings in 74d. Intact; owner-approved tier 1 explicit add on 2026-05-10 after fresh band review |
| **MSFT** | 5 | 2 | 5 | 5 | **17** | Almost deployable | 17.1% above band. Earnings in 68d. Intact; owner-approved staged manual candidacy recorded on 2026-05-12 after msft/goog/nvda growth review; live trigger currently inactive while price is above written band |
| **GS** | 4 | 4 | 5 | 4 | **17** | PROMOTION REVIEW | in band. Earnings in 53d. Intact but secondary to jpm for primary bank exposure |
| **AMZN** | 5 | 4 | 5 | 3 | **17** | Watch | in band. Earnings in 69d. Intact but technically underdefined |
| **RTX** | 5 | 4 | 5 | 3 | **17** | Watch | 8.6% above band. Earnings in 60d. Under active review |
| **CAT** | 5 | 4 | 5 | 3 | **17** | Watch | in band. Earnings in 69d. Under active review |
| **AMD** | 5 | 4 | 5 | 3 | **17** | Watch | 38.2% above band. Earnings in 74d. Event-driven ai watch |
| **PH** | 5 | 4 | 5 | 3 | **17** | PROMOTION REVIEW | 10.2% above band. Earnings in 76d. Owner-approved portfolio-review candidate 2026-05-15; best higher-rate-resilient industrial compounder from sector-expansion pass. review-only: requires technical levels, valuation discipline, concentration/risk check, and separate owner decision before any model allocation or deployment. |
| **CVX** | 4 | 4 | 5 | 3 | **16** | Watch | 4.5% above band. Earnings in 70d. Secondary energy read-through |
| **LNG** | 4 | 4 | 5 | 3 | **16** | Watch | 0.7% above band. Earnings in 69d. Event-driven lng export watch |
| **XLI** | 5 | 3 | 5 | 3 | **16** | Watch | 4.0% above band. Promoted 2026-05-15 to coverage universe as etf monitor only |
| **PLTR** | 5 | 2 | 5 | 3 | **15** | Watch | 20.3% above band. Earnings in 73d. Higher-risk tactical narrative |
| **KTOS** | 5 | 2 | 5 | 3 | **15** | Watch | Earnings in 74d. Speculative asymmetry |
| **SMCI** | 5 | 2 | 5 | 3 | **15** | Watch | Earnings in 74d. Speculative ai infrastructure monitor |
| **LIN** | 3 | 4 | 5 | 3 | **15** | PROMOTION REVIEW | near stop: close 487.57 is 0.40 above stop 487.17; 1.9% below band low 497.11. Earnings in 70d. Owner-promoted 2026-05-19 into formal materials sleeve / starter-sizing planning after lin owner-review packet; quality case accepted for planning, but premium valuation and top-of-band entry discipline remain blockers before any execution. |
| **ECL** | 3 | 4 | 5 | 3 | **15** | Watch | 0.9% above band. Earnings in 67d. Promoted 2026-05-15 to machine-tracked materials-adjacent research monitor; defensive compounder candidate |
| **GE** | 3 | 4 | 5 | 3 | **15** | Watch | 11.7% above band. Earnings in 60d. Promoted 2026-05-15 to machine-tracked aerospace quality / defense-commercial gap monitor |
| **WMB** | 3 | 4 | 5 | 3 | **15** | Watch | near stop: close 70.49 is 0.17 above stop 70.32; 3.8% below band low 73.25. Earnings in 73d. Promoted 2026-05-15 to machine-tracked gas infrastructure / power-demand monitor |
| **XLB** | 3 | 4 | 5 | 3 | **15** | PROMOTION REVIEW | 3.6% above band. Owner-promoted 2026-05-30 into formal materials etf starter-planning lane after promoted-ticker audit; improving materials leadership and underexposure make xlb the cleaner paper-simulation candidate versus forcing another ai-power name. |
| **XLE** | 4 | 3 | 5 | 3 | **15** | Watch | 9.6% above band. Promoted 2026-05-15 to coverage universe as etf monitor only |
| **VAW** | 3 | 4 | 5 | 3 | **15** | Watch | 2.6% above band. Promoted 2026-05-15 to coverage universe as etf monitor only |
| **VRT** | 5 | 1 | 5 | 3 | **14** | Do not touch | stop breached: close 261.95 is 15.02 below stop 276.97; 12.7% below band low 300.02. Earnings in 61d. Owner-promoted 2026-05-29 into formal ai-power tactical challenger / starter-sizing planning after q1 2026 beat-and-raise; etn remains primary and concentration discipline remains binding. |
| **PAVE** | 3 | 3 | 5 | 3 | **14** | Watch | 0.2% above band. Promoted 2026-05-15 to coverage universe as etf monitor only |
| **XLF** | 4 | 2 | 5 | 3 | **14** | Watch | 8.3% above band. Promoted 2026-05-15 to coverage universe as etf monitor only |
| **VXUS** | 3 | 3 | 5 | 3 | **14** | Watch | 5.2% above band. Added 2026-05-18 to tracked_universe to close entry-band orphan after official vanguard proof and review-only band fix; not execution-ready and no allocation/sizing/trade authority. |
| **TLT** | 3 | 2 | 5 | 3 | **13** | Watch | Macro duration hedge |
| **LLY** | 3 | 2 | 5 | 3 | **13** | Watch | 29.4% above band. Earnings in 69d. Workflow 7 healthcare watch-lane pilot — preferred sector leader over jnj for first sleeve monitor |
| **ITA** | 3 | 2 | 5 | 3 | **13** | PROMOTION REVIEW | 6.2% above band. Owner-promoted 2026-05-18 to review-only paper-candidate queue after official ishares/blackrock holdings proof; not execution-ready and no allocation/sizing/trade authority. |
| **LMT** | 4 | 2 | 5 | 2 | **13** | Do not touch | in band. Earnings in 60d. Repair mode. Intact but active model weight suspended while below-stop repair; prior 10% core defense draft weight is not counted as active exposure |
| **SLV** | 2 | 2 | 5 | 3 | **12** | Watch | Macro hedge |
| **VMC** | 3 | 1 | 5 | 3 | **12** | Do not touch | stop breached: close 276.04 is 8.54 below stop 284.58; 5.4% below band low 291.87. Earnings in 69d. Promoted 2026-05-15 to machine-tracked infrastructure/aggregates materials monitor |
| **META** | 3 | 1 | 5 | 3 | **12** | Do not touch | stop breached: close 549.90 is 105.65 below stop 655.55; 18.2% below band low 672.60. Earnings in 68d. Owner-approved portfolio-review candidate 2026-05-15; strongest communication services fundamental candidate. review-only: direct tech/ai/platform crowding, capex/regulatory risk, and underdefined technical setup block any model allocation or deployment. |
| **NFLX** | 3 | 1 | 5 | 3 | **12** | Do not touch | stop breached: close 79.59 is 20.65 below stop 100.24; 22.4% below band low 102.56. Earnings in 60d. Promoted 2026-05-15 to machine-tracked communication services subscription/media quality monitor |
| **TMUS** | 3 | 1 | 5 | 3 | **12** | Do not touch | stop breached: close 183.04 is 24.07 below stop 207.11; 14.1% below band low 213.01. Earnings in 62d. Promoted 2026-05-15 to machine-tracked defensive telecom growth monitor |
| **CME** | 3 | 1 | 5 | 3 | **12** | Do not touch | stop breached: close 274.98 is 1.70 below stop 276.68; 4.4% below band low 287.74. Earnings in 61d. Owner-approved portfolio-review candidate 2026-05-15; financial infrastructure diversifier away from bank credit-cycle exposure. review-only: valuation/regime fit and technical discipline remain blockers before any model allocation or deployment. |
| **XLC** | 3 | 1 | 5 | 3 | **12** | Do not touch | stop breached: close 111.40 is 1.31 below stop 112.71; 2.5% below band low 114.31. Promoted 2026-05-15 to coverage universe as etf monitor only |
| **BRK.B** | 3 | 2 | 5 | 2 | **12** | Do not touch | in band. Earnings in 78d. Repair mode |
| **XOM** | 3 | 2 | 5 | 2 | **12** | Do not touch | 4.2% above band. Earnings in 70d. Repair mode. Intact long-term, weaker near-term |
| **BKNG** | 2 | 2 | 5 | 2 | **11** | Do not touch | 22.6% above band. Earnings in 67d. Repair mode. Consumer discretionary tier 1 research candidate approved for watchlist on 2026-05-10; no deployment authority |
---

## Priority ranking (current)

1. **GOOG** — 19 — near stop: close 341.75 is 0.68 above stop 341.07; 3.5% below band low 354.25
2. **NVDA** — 19 — 1.2% above band; intact / thesis strengthened by Q1 FY2027 post-earnings official review, but crowded and above-band
3. **JPM** — 18 — 11.3% above band; intact; prior owner approval recorded on 2026-05-07, but current trigger is not live. Fresh 2026-05-22 artifact layer places JPM above the 304.96 to 315.95 reference band, so current posture is wait/no-chase pending fresh review.
4. **ETN** — 18 — 3.8% above band; intact; owner-approved Tier 1 explicit add on 2026-05-10 after fresh band review
5. **MSFT** — 17 — 17.1% above band; intact; owner-approved staged manual candidacy recorded on 2026-05-12 after MSFT/GOOG/NVDA growth review; live trigger currently inactive while price is above written band
6. **GS** — 17 — in band; intact but secondary to JPM for primary bank exposure
7. **AMZN** — 17 — in band; intact but technically underdefined
8. **RTX** — 17 — 8.6% above band; under active review
9. **CAT** — 17 — in band; under active review
10. **AMD** — 17 — 38.2% above band; event-driven AI watch
11. **PH** — 17 — 10.2% above band; Owner-approved portfolio-review candidate 2026-05-15; best higher-rate-resilient industrial compounder from sector-expansion pass. Review-only: requires technical levels, valuation discipline, concentration/risk check, and separate owner decision before any model allocation or deployment.
12. **CVX** — 16 — 4.5% above band; secondary energy read-through
13. **LNG** — 16 — 0.7% above band; event-driven LNG export watch
14. **XLI** — 16 — 4.0% above band; promoted 2026-05-15 to coverage universe as ETF monitor only
15. **PLTR** — 15 — 20.3% above band; higher-risk tactical narrative
16. **KTOS** — 15 — speculative asymmetry
17. **SMCI** — 15 — speculative AI infrastructure monitor
18. **LIN** — 15 — near stop: close 487.57 is 0.40 above stop 487.17; 1.9% below band low 497.11; Owner-promoted 2026-05-19 into formal Materials sleeve / starter-sizing planning after LIN owner-review packet; quality case accepted for planning, but premium valuation and top-of-band entry discipline remain blockers before any execution.
19. **ECL** — 15 — 0.9% above band; promoted 2026-05-15 to machine-tracked Materials-adjacent research monitor; defensive compounder candidate
20. **GE** — 15 — 11.7% above band; promoted 2026-05-15 to machine-tracked aerospace quality / defense-commercial gap monitor
21. **WMB** — 15 — near stop: close 70.49 is 0.17 above stop 70.32; 3.8% below band low 73.25; promoted 2026-05-15 to machine-tracked gas infrastructure / power-demand monitor
22. **XLB** — 15 — 3.6% above band; Owner-promoted 2026-05-30 into formal Materials ETF starter-planning lane after promoted-ticker audit; improving Materials leadership and underexposure make XLB the cleaner paper-simulation candidate versus forcing another AI-power name.
23. **XLE** — 15 — 9.6% above band; promoted 2026-05-15 to coverage universe as ETF monitor only
24. **VAW** — 15 — 2.6% above band; promoted 2026-05-15 to coverage universe as ETF monitor only
25. **VRT** — 14 — stop breached: close 261.95 is 15.02 below stop 276.97; 12.7% below band low 300.02; Owner-promoted 2026-05-29 into formal AI-power tactical challenger / starter-sizing planning after Q1 2026 beat-and-raise; ETN remains primary and concentration discipline remains binding.
26. **PAVE** — 14 — 0.2% above band; promoted 2026-05-15 to coverage universe as ETF monitor only
27. **XLF** — 14 — 8.3% above band; promoted 2026-05-15 to coverage universe as ETF monitor only
28. **VXUS** — 14 — 5.2% above band; Added 2026-05-18 to tracked_universe to close entry-band orphan after official Vanguard proof and review-only band fix; not execution-ready and no allocation/sizing/trade authority.
29. **TLT** — 13 — macro duration hedge
30. **LLY** — 13 — 29.4% above band; Workflow 7 Healthcare watch-lane pilot — preferred sector leader over JNJ for first sleeve monitor
31. **ITA** — 13 — 6.2% above band; Owner-promoted 2026-05-18 to review-only paper-candidate queue after official iShares/BlackRock holdings proof; not execution-ready and no allocation/sizing/trade authority.
32. **LMT** — 13 — in band; setup broken; intact but active model weight suspended while below-stop repair; prior 10% Core Defense draft weight is not counted as active exposure
33. **SLV** — 12 — macro hedge
34. **VMC** — 12 — stop breached: close 276.04 is 8.54 below stop 284.58; 5.4% below band low 291.87; promoted 2026-05-15 to machine-tracked infrastructure/aggregates Materials monitor
35. **META** — 12 — stop breached: close 549.90 is 105.65 below stop 655.55; 18.2% below band low 672.60; Owner-approved portfolio-review candidate 2026-05-15; strongest Communication Services fundamental candidate. Review-only: direct Tech/AI/platform crowding, capex/regulatory risk, and underdefined technical setup block any model allocation or deployment.
36. **NFLX** — 12 — stop breached: close 79.59 is 20.65 below stop 100.24; 22.4% below band low 102.56; promoted 2026-05-15 to machine-tracked Communication Services subscription/media quality monitor
37. **TMUS** — 12 — stop breached: close 183.04 is 24.07 below stop 207.11; 14.1% below band low 213.01; promoted 2026-05-15 to machine-tracked defensive telecom growth monitor
38. **CME** — 12 — stop breached: close 274.98 is 1.70 below stop 276.68; 4.4% below band low 287.74; Owner-approved portfolio-review candidate 2026-05-15; financial infrastructure diversifier away from bank credit-cycle exposure. Review-only: valuation/regime fit and technical discipline remain blockers before any model allocation or deployment.
39. **XLC** — 12 — stop breached: close 111.40 is 1.31 below stop 112.71; 2.5% below band low 114.31; promoted 2026-05-15 to coverage universe as ETF monitor only
40. **BRK.B** — 12 — in band; setup broken
41. **XOM** — 12 — 4.2% above band; setup broken; intact long-term, weaker near-term
42. **BKNG** — 11 — 22.6% above band; setup broken; Consumer Discretionary Tier 1 research candidate approved for watchlist on 2026-05-10; no deployment authority

Last auto-scored: 2026-08-21
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

- Last updated: 2026-08-21 — auto-scored by regime_scoring_refresh.py
- Data as of: 2026-08-21 close
- XOM source check: the confirmed May 11 close is **149.68** from Exxon IR / LSEG and `tmp/technical-refresh.json`; the previously surfaced **144.57** value came from an incomplete/stale May monthly entry-band candle and must not be treated as the daily close.
- Refresh cadence: after weekly technical refresh, after tracked earnings, after material regime change
- Next refresh due: after the next weekly technical/deployment refresh, after NVDA May 20 timing/earnings risk is rechecked, or immediately after any fresh stop/band/catalyst break
- Refresh policy: update scores when underlying inputs change materially. Do not adjust scores for minor price noise. When re-scoring, note what changed and why in the "Notes" column.
