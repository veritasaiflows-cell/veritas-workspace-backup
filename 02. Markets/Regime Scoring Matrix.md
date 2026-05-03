# Regime Scoring Matrix

## Purpose

Score every tracked name against the current macro regime on four dimensions. Produces a ranked, sortable priority list that replaces the narrative rankings currently scattered across the Watchlist, Deployment Trigger Sheet, and Portfolio Snapshot.

**Canonical ranking source:** This file is the single source of truth for priority order among tracked names. The Deployment Trigger Sheet uses this ranking but owns the deployment logic (gates, bands, stops). The Portfolio Snapshot references this ranking but owns sizing and posture.

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

## Current scoring — as of 2026-05-02 (data: 2026-05-01 close)

| Ticker | Regime Fit | Technical Posture | Catalyst Risk | Fund. Conviction | **Total** | Current Stance | Notes |
|---|---|---|---|---|---|---|---|
| **JPM** | 4 | 5 | 5 | 5 | **19** | DEPLOYABLE NOW | in band. Earnings in 73d |
| **GOOG** | 5 | 3 | 5 | 5 | **18** | Almost deployable | 9.7% above band. Earnings in 82d |
| **MSFT** | 5 | 3 | 5 | 5 | **18** | Almost deployable | 0.5% above band. Earnings in 88d |
| **GS** | 4 | 5 | 5 | 4 | **18** | DEPLOYABLE NOW | in band. Earnings in 73d. Intact but secondary to jpm for primary bank exposure |
| **NVDA** | 5 | 5 | 4 | 4 | **18** | DEPLOYABLE NOW | in band. Earnings in 18d. Intact but crowded |
| **VRT** | 5 | 4 | 5 | 3 | **17** | WATCH / RESEARCH NEEDED | 0.5% above band. Earnings in 88d. Confirmed and upgraded — q1 2026 beat-and-raise apr 22 |
| **AMZN** | 5 | 3 | 5 | 3 | **16** | Watch | Earnings in 89d. Intact but technically underdefined |
| **CAT** | 5 | 3 | 5 | 3 | **16** | Watch | Under active review |
| **ETN** | 5 | 4 | 1 | 4 | **14** | Almost deployable | 1.2% above band. Earnings in 3d |
| **RTX** | 5 | 1 | 5 | 3 | **14** | Watch | Earnings in 80d. Under active review |
| **CVX** | 4 | 2 | 5 | 3 | **14** | Watch | Earnings in 90d. Secondary energy read-through |
| **LLY** | 3 | 3 | 5 | 3 | **14** | Watch | Workflow 7 healthcare watch-lane pilot — preferred sector leader over jnj for first sleeve monitor |
| **TLT** | 3 | 2 | 5 | 3 | **13** | Watch | Macro duration hedge |
| **SLV** | 2 | 2 | 5 | 3 | **12** | Watch | Macro hedge |
| **KTOS** | 5 | 2 | 2 | 3 | **12** | Watch | Earnings in 4d. Speculative asymmetry |
| **LNG** | 4 | 3 | 2 | 3 | **12** | Watch | Earnings in 5d. Event-driven lng export watch |
| **AMD** | 5 | 3 | 1 | 3 | **12** | Watch | Earnings in 3d. Event-driven ai watch |
| **LMT** | 4 | 1 | 5 | 2 | **12** | Do not touch | 9.5% below band low. Earnings in 80d. Repair mode. Intact but event-sensitive |
| **XOM** | 3 | 2 | 5 | 2 | **12** | Do not touch | in band. Earnings in 90d. Repair mode. Intact long-term, weaker near-term |
| **PLTR** | 5 | 2 | 1 | 3 | **11** | Watch | Earnings in 2d. Higher-risk tactical narrative |
| **SMCI** | 5 | 2 | 1 | 3 | **11** | Watch | Earnings in 3d. Speculative ai infrastructure monitor |
| **BRK.B** | 3 | 2 | 1 | 2 | **8** | Do not touch | in band. Earnings in 0d. Repair mode |
---

## Priority ranking (current)

1. **JPM** — 19 — in band
2. **GOOG** — 18 — 9.7% above band
3. **MSFT** — 18 — 0.5% above band
4. **GS** — 18 — in band; intact but secondary to JPM for primary bank exposure
5. **NVDA** — 18 — in band; intact but crowded
6. **VRT** — 17 — 0.5% above band; confirmed and upgraded — Q1 2026 beat-and-raise Apr 22
7. **AMZN** — 16 — intact but technically underdefined
8. **CAT** — 16 — under active review
9. **ETN** — 14 — 1.2% above band; earnings in 3d
10. **RTX** — 14 — under active review
11. **CVX** — 14 — secondary energy read-through
12. **LLY** — 14 — Workflow 7 Healthcare watch-lane pilot — preferred sector leader over JNJ for first sleeve monitor
13. **TLT** — 13 — macro duration hedge
14. **SLV** — 12 — macro hedge
15. **KTOS** — 12 — earnings in 4d; speculative asymmetry
16. **LNG** — 12 — earnings in 5d; event-driven LNG export watch
17. **AMD** — 12 — earnings in 3d; event-driven AI watch
18. **LMT** — 12 — 9.5% below band low; setup broken; intact but event-sensitive
19. **XOM** — 12 — in band; setup broken; intact long-term, weaker near-term
20. **PLTR** — 11 — earnings in 2d; higher-risk tactical narrative
21. **SMCI** — 11 — earnings in 3d; speculative AI infrastructure monitor
22. **BRK.B** — 8 — in band; earnings in 0d; setup broken

Last auto-scored: 2026-05-02
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

- Last updated: 2026-05-02 — auto-scored by regime_scoring_refresh.py
- Data as of: 2026-04-24 close
- Refresh cadence: after weekly technical refresh, after tracked earnings, after material regime change
- Next refresh due: after Apr 29 FOMC + MSFT/GOOG/AMZN prints — Catalyst Risk scores will change materially for at least 3 names
- Refresh policy: update scores when underlying inputs change materially. Do not adjust scores for minor price noise. When re-scoring, note what changed and why in the "Notes" column.
