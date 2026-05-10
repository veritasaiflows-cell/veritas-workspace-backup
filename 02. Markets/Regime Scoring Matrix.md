# Regime Scoring Matrix

## Purpose

Score every tracked name against the current macro regime on four dimensions. Produces a ranked, sortable review-support list for triage and comparison.

**Authority boundary:** This is a controlled machine-companion ranking note, not final canonical deployment truth. `scripts/regime_scoring_refresh.py` may update the scoring, ranking, and freshness blocks here, but final action authority remains with the [[03. Portfolio/Deployment Trigger Sheet]], [[03. Portfolio/Portfolio Snapshot]], [[07. Risk/Risk Rules]], and explicit owner approval.

**Use correctly:** A high score means "review first," not "deploy." The Deployment Trigger Sheet owns deployable / almost / blocked / do-not-touch states; the Portfolio Snapshot owns sizing and posture; Risk Rules own concentration and escalation limits.

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

## Current scoring — as of 2026-05-09 (data: 2026-05-08 close)

| Ticker | Regime Fit | Technical Posture | Catalyst Risk | Fund. Conviction | **Total** | Current Stance | Notes |
|---|---|---|---|---|---|---|---|
| **GOOG** | 5 | 3 | 5 | 5 | **18** | Almost deployable | 9.7% above band. Earnings in 75d |
| **MSFT** | 5 | 3 | 5 | 5 | **18** | Almost deployable | 0.6% above band. Earnings in 81d |
| **ETN** | 5 | 4 | 5 | 4 | **18** | PROMOTION REVIEW | in band. Earnings in 87d |
| **JPM** | 4 | 3 | 5 | 5 | **17** | Almost deployable | 1.5% below band low. Earnings in 66d |
| **GS** | 4 | 4 | 5 | 4 | **17** | Almost deployable | 1.0% above band. Earnings in 66d. Intact but secondary to jpm for primary bank exposure |
| **VRT** | 5 | 4 | 5 | 3 | **17** | WATCH / RESEARCH NEEDED | 0.5% above band. Earnings in 81d. Confirmed and upgraded — q1 2026 beat-and-raise apr 22 |
| **NVDA** | 5 | 4 | 3 | 4 | **16** | Almost deployable | 2.1% above band. Earnings in 11d. Intact but crowded |
| **AMZN** | 5 | 3 | 5 | 3 | **16** | Watch | Earnings in 82d. Intact but technically underdefined |
| **CAT** | 5 | 3 | 5 | 3 | **16** | Watch | Earnings in 87d. Under active review |
| **AMD** | 5 | 3 | 5 | 3 | **16** | Watch | Earnings in 87d. Event-driven ai watch |
| **PLTR** | 5 | 2 | 5 | 3 | **15** | Watch | Earnings in 86d. Higher-risk tactical narrative |
| **KTOS** | 5 | 2 | 5 | 3 | **15** | Watch | Earnings in 89d. Speculative asymmetry |
| **SMCI** | 5 | 2 | 5 | 3 | **15** | Watch | Earnings in 87d. Speculative ai infrastructure monitor |
| **RTX** | 5 | 1 | 5 | 3 | **14** | Watch | Earnings in 73d. Under active review |
| **LLY** | 3 | 3 | 5 | 3 | **14** | Watch | Earnings in 88d. Workflow 7 healthcare watch-lane pilot — preferred sector leader over jnj for first sleeve monitor |
| **CVX** | 4 | 1 | 5 | 3 | **13** | Watch | Earnings in 83d. Secondary energy read-through |
| **LNG** | 4 | 1 | 5 | 3 | **13** | Watch | Earnings in 89d. Event-driven lng export watch |
| **TLT** | 3 | 2 | 5 | 3 | **13** | Watch | Macro duration hedge |
| **SLV** | 2 | 2 | 5 | 3 | **12** | Watch | Macro hedge |
| **LMT** | 4 | 1 | 5 | 2 | **12** | Do not touch | 7.7% below band low. Earnings in 73d. Repair mode. Intact but event-sensitive |
| **BRK.B** | 3 | 2 | 5 | 2 | **12** | Do not touch | in band. Earnings in 84d. Repair mode |
| **XOM** | 3 | 1 | 5 | 2 | **11** | Do not touch | 3.8% below band low. Earnings in 83d. Repair mode. Intact long-term, weaker near-term |
---

## Priority ranking (current)

1. **GOOG** — 18 — 9.7% above band
2. **MSFT** — 18 — 0.6% above band
3. **ETN** — 18 — in band
4. **JPM** — 17 — 1.5% below band low
5. **GS** — 17 — 1.0% above band; intact but secondary to JPM for primary bank exposure
6. **VRT** — 17 — 0.5% above band; confirmed and upgraded — Q1 2026 beat-and-raise Apr 22
7. **NVDA** — 16 — 2.1% above band; earnings in 11d; intact but crowded
8. **AMZN** — 16 — intact but technically underdefined
9. **CAT** — 16 — under active review
10. **AMD** — 16 — event-driven AI watch
11. **PLTR** — 15 — higher-risk tactical narrative
12. **KTOS** — 15 — speculative asymmetry
13. **SMCI** — 15 — speculative AI infrastructure monitor
14. **RTX** — 14 — under active review
15. **LLY** — 14 — Workflow 7 Healthcare watch-lane pilot — preferred sector leader over JNJ for first sleeve monitor
16. **CVX** — 13 — secondary energy read-through
17. **LNG** — 13 — event-driven LNG export watch
18. **TLT** — 13 — macro duration hedge
19. **SLV** — 12 — macro hedge
20. **LMT** — 12 — 7.7% below band low; setup broken; intact but event-sensitive
21. **BRK.B** — 12 — in band; setup broken
22. **XOM** — 11 — 3.8% below band low; setup broken; intact long-term, weaker near-term

Last auto-scored: 2026-05-09
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

- Last updated: 2026-05-09 — auto-scored by regime_scoring_refresh.py
- Data as of: 2026-05-08 close
- Refresh cadence: after weekly technical refresh, after tracked earnings, after material regime change
- Next refresh due: after Apr 29 FOMC + MSFT/GOOG/AMZN prints — Catalyst Risk scores will change materially for at least 3 names
- Refresh policy: update scores when underlying inputs change materially. Do not adjust scores for minor price noise. When re-scoring, note what changed and why in the "Notes" column.
