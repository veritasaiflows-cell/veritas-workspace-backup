# Retired — Weekly Positioning Review

Status: retired on 2026-08-29 during the alerts-and-recommendations OS pivot.

This path remains only for backlinks and historical audit context. It is not active finance canon, a weekly control surface, or a source of current recommendation state.

## Active replacement

- Human finance canon: `03. Alerts and Recommendations/`
- Weekly deterministic route: `python scripts\run_alerts_recommendations_chain.py weekly --timeout-seconds 120 --write --validate`
- Weekly output: evidence-dated alerts and non-executing recommendations with freshness, confidence, thesis, risks, band/invalidation context, uncertainty, and Randall's decision point

No content below this notice authorizes or maintains portfolio structure, account state, orders, or paper/live execution.

## Retired historical source — non-operative

The preserved body below is dated legacy/audit material. Its routes, owners, states, permissions, and “current” labels are retired and must not be used operationally.

<!-- THIN HUMAN SURFACE
Backup before thinning: backups/sql-json-md-thinning/20260619T192613Z/05. Intelligence/Weekly Positioning Review.md
Structured owner: state/finance/finance-canon.sqlite plus generated/read-only proof packets.
Authority: weekly reasoning and audit context only; no execution, portfolio mutation, archive/delete/apply authority, or inferred approval.
-->

# Weekly Positioning Review

## Role

This is the human weekly reasoning layer for Randall and Veritas. It should explain market posture, risk posture, opportunity themes, owner decisions, and what the daily machinery should watch next.

It should not duplicate ticker-level current state, technical levels, evidence currentness, routing status, answer-scope membership, or machine queues. Those structured facts are SQL-generated/read-only.

## Weekly Reasoning Standard

Each weekly pass should answer:

- what changed in the macro and market regime
- which portfolio risks deserve patience
- which opportunity themes deserve more research
- what constraints should shape any later proposal
- what proof packet should be checked before a material finance claim

## Current Structured Views

Use these generated/read-only routes for structured finance state:

- SQL-generated/read-only structured canon guard: `python scripts\finance_sql_canon_access.py --write --validate`
- SQL-generated/read-only trade-grade readiness: `python scripts\trade_grade_os_freshness_cron_runner.py --write --validate`
- SQL-generated/read-only WF78 routing: `python scripts\wf78_intelligence_routing_v2.py --layer daily_core_v2 --fail-on-budget-exceeded --write --validate`
- SQL-generated/read-only WF84 data plane: `python scripts\canonical_finance_data_plane_phase6_10.py --write --validate`
- SQL-generated/read-only WF85 parity: `python scripts\full_intelligence_answer_parity.py --all --write --validate`

Generated/read-only proof files:

- `tmp/trade-grade-os-freshness-cron-runner.json`
- `tmp/wf78-intelligence-routing-v2.json`
- `tmp/canonical-finance-data-plane-phase6-10.json`
- `tmp/full-answer-parity/full-answer-parity-rollup.json`

## Boundary

Weekly reasoning may recommend research, repair, or proposal work. It does not approve orders, paper execution, live execution, cash changes, portfolio mutation, SQL schema changes, or archive/delete/apply packets.

## Historical Trail

The pre-thinning weekly review was preserved before this rewrite:

- `backups/sql-json-md-thinning/20260619T192613Z/05. Intelligence/Weekly Positioning Review.md`

Use it as historical/audit context only. Rebuild future weekly reasoning as narrative, not as a hand-maintained duplicate of structured finance fields.
---

## Current Sunday Sync - 2026-06-28

### Weekly posture

- **Posture:** Defensive-neutral / selective-risk-on for review only.
- **Historical/audit Sunday sync snapshot - confidence:** Moderate for review-only posture; not enough for deployment approval. Sunday artifacts were accepted with no stop line and dashboard validation was clean except for the known info-grade active-weight accounting gap. Deployment readiness was still presentation-blocked/review-only, and the research radar was degraded because sector-expansion proof was degraded.
- **Historical/audit Sunday sync snapshot - operating stance:** Keep deployment selective and owner-gated; prioritize in-band quality setups, avoid chase behavior, and require manual review for macro/rates-sensitive names, financials, and AI-power concentration before any proposal.
- **What changed:** Breadth improved back to broad participation, credit remains benign, and rates/dollar/inflation pressure still argue against broad deployment. ETN is the only deployable-now review candidate; GS and VRT are promotion-review names; JPM is almost deployable but above band.

### Macro regime and confidence

Sources: `tmp/weekly-macro-snapshot.json`, `tmp/macro-judgment-draft.json`, `tmp/macro-metrics-current.json`, `tmp/macro-signal-spine.json`, and `tmp/dashboard-validation.json`, generated 2026-06-28.

- **Regime:** Restrictive pause, resilient growth, selective risk-on with large-cap quality bias.
- **Rates:** Fed target 3.50%-3.75%, next FOMC 2026-07-29, next-meeting cut probability 0%; 2Y 4.070%, 10Y 4.372%, 3M bill 3.663%.
- **Market tape:** SPX 7,354.02, VIX 18.41, DXY 101.36, Brent $72.60, WTI $69.23.
- **Inflation/growth read:** CPI/core/PCE still keep rate sensitivity high; claims and payrolls do not show a collapse. GDP and ISM keep the base case away from risk-off, but inflation and dollar pressure keep broad deployment gated.
- **Risk stack:** Credit is benign and breadth is broad, with 8 of 11 sectors above 50DMA and RSP/SPY +3.00% over 5 days. That supports selective review, not automatic allocation.

### Deployment map

Sources: `tmp/deployment-readiness-surface.json` and `tmp/portfolio-mutation-proposals/current-capital-deployment-recommendations.json`, generated 2026-06-28. Review-only; no apply packet is authorized.

- **Deployable now:** ETN.
- **Promotion review:** GS, VRT.
- **Almost deployable:** JPM.
- **Do not touch:** BRK.B, LMT, XOM.
- **Additional do-not-touch states:** GOOG, MSFT, and NVDA are also in do-not-touch state in the generated deployment surface.
- **Capital-deployment recommendation packet:** 4 proposal rows exist for GS, VRT, ETN, and JPM; validation is ok, but `proposal_apply_allowed=false`, packet-level owner approval is not inferred, and `trade_execution_allowed=false`. It is a review packet, not an instruction to mutate portfolio, sizing, cash, sleeve, account, or execution state.
- **Historical/audit Sunday sync snapshot - priority:** ETN was the only in-band deployable-now review candidate in this snapshot, still constrained by size/correlation and no-chase discipline. GS/VRT needed explicit promotion review; JPM needed band discipline because it was above band.

### Research opportunity radar

Source: `tmp/research-freshness-opportunity-review.json`, generated 2026-06-28T16:54:51Z.

- **Improving leadership:** Consumer Staples, Financials, Health Care, Industrials, Materials, Real Estate, Utilities.
- **Underexposed lanes:** Communication Services, Consumer Discretionary, Consumer Staples, Health Care, Materials, Real Estate, Utilities.
- **Portfolio-review candidates:** CME, ITA, LIN, META, PH, VRT, XLB.
- **Conditional watch:** ECL, GE, NFLX, TMUS, VMC, WMB.
- **Blocked/deferred:** CAT, ETN, GS, JPM, LLY, NVDA.
- **Diversified-fund cue:** small/mid-cap posture is improving-review-only; AVUV, IJH, IJR, IJS, IWM, MDY, SCHA, VB, VBR, and VO are improving. No commodity review candidate is current. Macro/correlation review is required before any proposal.
- **Historical/audit Sunday sync snapshot - freshness gaps:** Required research sources were fresh enough, but outcome analytics were not ready, future realized outcomes were not used, portfolio config was stale/manual-dependency context, and sector-expansion status was degraded. No monitoring context was missing.

### WF65 fundamental context

Sources: `tmp/fundamental-metrics-current.json`, `tmp/fundamental-metrics-validation.json`, `tmp/fundamental-ir-reconciliation-packets.json`, and `tmp/fundamental-ir-reconciliation-validation.json`, generated 2026-06-28.

- **Coverage:** 300 tickers covered; 289 equity tickers; 132 clean equity rows, 2 partial rows, and 155 missing rows.
- **Per-share quality gates:** WF65 tracks revenue/EPS/FCF per share, share count, buyback/SBC/dividend/capital-return behavior, ROIC proxy, valuation context, and anomaly flags. These are evidence gates, not deployment gates.
- **SEC reconciliation:** 113 matched, 11 matched via period alias, 4 SEC-lag wait, 158 manual-review required, 3 foreign-issuer IR required, and 11 not applicable.
- **IR reconciliation:** 31 active equity IR packets exist and validation is ok; all 31 consumed validated official captures and SEC reconciliation status is matched, but the packets remain manual-required review packets.
- **Anomaly pressure:** Capital-allocation caution remains high: capital return exceeds FCF in 55 rows, debt-funded capital-return risk in 42, elevated leverage in 36, EPS/FCF per-share divergence in 25, capital returns with negative FCF in 23, low ROIC proxy in 18, SBC offsets buybacks in 14, buybacks with net dilution in 14, net share issuance in 14, and share-count dilution in 13.
- **Validation warning surface:** 475 warning findings, 0 critical. Main warning codes are SEC manual period review, missing equity core growth/period fields, SEC-lag wait, and foreign-issuer IR review.
- **Authority:** WF65 is review-only. SEC/IR manual-review warnings must be respected before using fundamentals for any high-consequence answer, and fundamentals do not grant deployability, sizing, sleeve, cash, execution, paper/live order, trade/account, or owner-approval authority.

### Constraints and next questions

- **Breadth:** Breadth is broad again, but dollar, rates, inflation pressure, and deployment-surface gating keep the stance selective rather than broad-risk-on.
- **Historical/audit Sunday sync snapshot - research radar degradation:** Sector-expansion proof was degraded by a degraded sector-correlation check, parsed-portfolio fallback, daily-review freshness requiring review, and band-proposal review debt.
- **Concentration:** Direct Technology is at its 25% cap and AI-power correlated exposure is 32% including ETN. Any VRT/NVDA/ETN/MSFT action needs concentration sequencing, not just ticker-level attractiveness.
- **Accounting:** Active portfolio weights plus cash sum to 90%; the remaining 10% is suspended legacy model weight, not active exposure.
- **Historical/audit Sunday sync snapshot - questions:** Whether ETN remained inside the owner band without breaching no-chase discipline; whether GS/VRT deserved source-open promotion-review packets; whether JPM should wait for band reclaim; whether WF65 anomaly review weakened any almost-deployable or promotion-review thesis.

Review-only cue: no promotion, sizing, sleeve, cash, deployment, trade, account action, or owner approval is inferred from this cron output.

Historical/audit note: the older 2026-06-15 to 2026-06-26 scaffold below is retained as stale/unpromoted structure only where it conflicts with this current sync.

## Week of 2026-06-15 to 2026-06-19

### 1) Weekly posture

- **Posture (judgment):** _[Fill: Offensive / Defensive-neutral / Defensive]_
- **Confidence level (judgment):** _[Fill: High / Moderate / Low — state the basis]_
- **Operating stance (judgment):** _[Fill: what is the 1-sentence directive for this week?]_
- **What changed from last week (judgment):** _[Fill: key developments since last review]_

---

### 2) Macro regime and confidence

*Machine-populated from market-state.json as of 2026-06-19. Sections marked (judgment) require human/AI interpretation.*

- **Fed / rates:** Target 3.50%–3.75% (confirmed 2026-06-21). Next FOMC 2026-07-29 — 0% cut probability. 2Y 4.190%, 10Y 4.451%, 3M 3.658%.
- **Yield curve:** 2s10s +26 bps, 3m-10y +79 bps. Curve constructive but front-end still restrictive.
- **Volatility / equities:** VIX 16.40, SPX 7,500.58.
- **Dollar / energy:** DXY 100.85, Brent 80.59 $/bbl, WTI 76.54 $/bbl.
- **Regime assessment (judgment):** _[Fill: is this week's data consistent with late-cycle restrictive baseline? Any threshold approaching?]_

---

### 3) Deployment map

*Data: trigger-sheet.json as of 2026-06-18*


**Almost deployable — pullback required (7):**
  - **Historical/audit scaffold snapshot - GOOG** - close 367.46, band 354.25-369.69 | stop 341.07 | score 19/20
  - **Historical/audit scaffold snapshot - NVDA** - close 210.69, band 202.81-212.23 | stop 192.95 | score 18/20
  - **Historical/audit scaffold snapshot - VRT** - close 333.05, band 300.02-319.13 | stop 276.97 | score 16/20
  - **Historical/audit scaffold snapshot - ETN** - close 421.77, band 387.67-404.02 | stop 367.60 | score 17/20
  - **Historical/audit scaffold snapshot - GS** - close 1,096.56, band 971.53-1048.14 | stop 928.97 | score 15/20 | earnings in 23d
  - **Historical/audit scaffold snapshot - JPM** - close 325.22, band 304.96-315.95 | stop 296.21 | score 16/20 | earnings in 23d
  - **Historical/audit scaffold snapshot - MSFT** - close 379.40, band 389.64-412.56 | stop 378.18 | score 18/20

**Do not touch — repair or review (3):**
  - **BRK.B** — Repair mode remains active until chart structure and support rebuild make the setup decision-grade again
  - **Historical/audit scaffold snapshot - LMT** - close 510.95 is below stop 531.63 -- do not deploy
  - **Historical/audit scaffold snapshot - XOM** - close 137.81 is below stop 146.14 -- do not deploy

- **Priority this week (judgment):** _[Fill: which 1–3 names are closest to actionable? What specific trigger would move them to deployed?]_

---

### 4) Catalyst calendar

**This week (Jun 15–Jun 19):** No tracked earnings this week.

- **FOMC / macro events (judgment):** _[Fill: list any FOMC dates, macro data releases, or geopolitical events that could change the regime this week]_
- **Read-throughs to watch (judgment):** _[Fill: any peer earnings or sector data that would shift conviction on names in the universe?]_

---

### 5) Sector allocation and risk flags

*Draft sector groupings from trigger sheet. Weights are model targets, not live deployed positions.*

| Sector | Names | Risk Cap | Note |
|---|---|---|---|
| Defense | LMT | 25% max | — |
| Diversified Quality | BRK.B | 25% max | — |
| Energy | XOM | 25% max | — |
| Financials | GS, JPM | 25% max | — |
| Industrials | VRT, ETN | 25% max | — |
| Tech | GOOG, NVDA, MSFT | 25% max | — |

- **Concentration check (judgment):** _[Fill: is any sector approaching the 25% cap at current draft weights? What sequencing constraint does that impose?]_
- **Cash level (judgment):** _[Fill: is current cash allocation consistent with regime state and deployment opportunity set?]_
- **Historical/audit scaffold placeholder - risk flags (judgment):** _[Fill: any names approaching stop, any positions requiring re-assessment this week?]_

---

### 6) Risk rules check

- _[Fill: are all sizing tiers being respected? Any escalation triggers from Risk Rules approaching? Drawdown vs. model high?]_

---

### 7) Key questions to answer this week

- _[Fill: what are the 3–5 questions whose answers would most change deployment decisions this week?]_

---

### 8) Friday close / week lookback

- _[Fill at end of week: what happened, what changed, which theses were confirmed or challenged, what updates to the vault are needed?]_

---

## Week of 2026-06-22 to 2026-06-26

### 1) Weekly posture

- **Posture (judgment):** _[Fill: Offensive / Defensive-neutral / Defensive]_
- **Confidence level (judgment):** _[Fill: High / Moderate / Low — state the basis]_
- **Operating stance (judgment):** _[Fill: what is the 1-sentence directive for this week?]_
- **What changed from last week (judgment):** _[Fill: key developments since last review]_

---

### 2) Macro regime and confidence

*Machine-populated from market-state.json as of 2026-06-26. Sections marked (judgment) require human/AI interpretation.*

- **Fed / rates:** Target 3.50%–3.75% (confirmed 2026-06-28). Next FOMC 2026-07-29 — 0% cut probability. 2Y 4.070%, 10Y 4.372%, 3M 3.663%.
- **Yield curve:** 2s10s +30 bps, 3m-10y +71 bps. Curve constructive but front-end still restrictive.
- **Volatility / equities:** VIX 18.41, SPX 7,354.02.
- **Dollar / energy:** DXY 101.36, Brent 72.60 $/bbl, WTI 69.23 $/bbl.
- **Regime assessment (judgment):** _[Fill: is this week's data consistent with late-cycle restrictive baseline? Any threshold approaching?]_

---

### 3) Deployment map

*Data: trigger-sheet.json as of 2026-06-26*

**Deployable now (1):**
  - **Historical/audit scaffold snapshot - ETN** - close 402.68, band 387.67-404.02 | stop 367.60 | score 18/20

**Almost deployable — pullback required (3):**
  - **Historical/audit scaffold snapshot - GS** - close 1,019.61, band 971.53-1048.14 | stop 928.97 | score 16/20 | earnings in 16d
  - **Historical/audit scaffold snapshot - VRT** - close 303.95, band 300.02-319.13 | stop 276.97 | score 17/20
  - **Historical/audit scaffold snapshot - JPM** - close 329.05, band 304.96-315.95 | stop 296.21 | score 17/20 | earnings in 16d

**Do not touch — repair or review (6):**
  - **BRK.B** — Repair mode remains active until chart structure and support rebuild make the setup decision-grade again
  - **Historical/audit scaffold snapshot - GOOG** - close 334.69 is below stop 341.07 -- do not deploy
  - **Historical/audit scaffold snapshot - LMT** - close 507.4 is below stop 531.63 -- do not deploy
  - **Historical/audit scaffold snapshot - MSFT** - close 372.97 is below stop 378.18 -- do not deploy
  - **Historical/audit scaffold snapshot - NVDA** - close 192.53 is below stop 192.95 -- do not deploy
  - **Historical/audit scaffold snapshot - XOM** - close 136.54 is below stop 146.14 -- do not deploy

- **Priority this week (judgment):** _[Fill: which 1–3 names are closest to actionable? What specific trigger would move them to deployed?]_

---

### 4) Catalyst calendar

**This week (Jun 22–Jun 26):** No tracked earnings this week.

- **FOMC / macro events (judgment):** _[Fill: list any FOMC dates, macro data releases, or geopolitical events that could change the regime this week]_
- **Read-throughs to watch (judgment):** _[Fill: any peer earnings or sector data that would shift conviction on names in the universe?]_

---

### 5) Sector allocation and risk flags

*Draft sector groupings from trigger sheet. Weights are model targets, not live deployed positions.*

| Sector | Names | Risk Cap | Note |
|---|---|---|---|
| Defense | LMT | 25% max | — |
| Diversified Quality | BRK.B | 25% max | — |
| Energy | XOM | 25% max | — |
| Financials | GS, JPM | 25% max | — |
| Industrials | ETN, VRT | 25% max | — |
| Tech | GOOG, MSFT, NVDA | 25% max | — |

- **Concentration check (judgment):** _[Fill: is any sector approaching the 25% cap at current draft weights? What sequencing constraint does that impose?]_
- **Cash level (judgment):** _[Fill: is current cash allocation consistent with regime state and deployment opportunity set?]_
- **Historical/audit scaffold placeholder - risk flags (judgment):** _[Fill: any names approaching stop, any positions requiring re-assessment this week?]_

---

### 6) Risk rules check

- _[Fill: are all sizing tiers being respected? Any escalation triggers from Risk Rules approaching? Drawdown vs. model high?]_

---

### 7) Key questions to answer this week

- _[Fill: what are the 3–5 questions whose answers would most change deployment decisions this week?]_

---

### 8) Friday close / week lookback

- _[Fill at end of week: what happened, what changed, which theses were confirmed or challenged, what updates to the vault are needed?]_

---

## Week of 2026-06-29 to 2026-07-03

### 1) Weekly posture

- **Posture (judgment):** _[Fill: Offensive / Defensive-neutral / Defensive]_
- **Confidence level (judgment):** _[Fill: High / Moderate / Low — state the basis]_
- **Operating stance (judgment):** _[Fill: what is the 1-sentence directive for this week?]_
- **What changed from last week (judgment):** _[Fill: key developments since last review]_

---

### 2) Macro regime and confidence

*Machine-populated from market-state.json as of 2026-07-03. Sections marked (judgment) require human/AI interpretation.*

- **Fed / rates:** Target 3.50%–3.75% (confirmed 2026-07-05). Next FOMC 2026-07-29 — 0% cut probability. 2Y 4.140%, 10Y 4.485%, 3M 3.668%.
- **Yield curve:** 2s10s +34 bps, 3m-10y +82 bps. Curve constructive but front-end still restrictive.
- **Volatility / equities:** VIX 16.15, SPX 7,483.24.
- **Dollar / energy:** DXY 100.86, Brent 72.13 $/bbl, WTI 68.78 $/bbl.
- **Regime assessment (judgment):** _[Fill: is this week's data consistent with late-cycle restrictive baseline? Any threshold approaching?]_

---

### 3) Deployment map

*Data: trigger-sheet.json as of 2026-07-02*

**Deployable now (1):**
  - **Historical/audit scaffold snapshot - ETN** - close 398.52, band 387.67-404.02 | stop 367.60 | score 17/20 | earnings in 30d

**Almost deployable — pullback required (6):**
  - **Historical/audit scaffold snapshot - GOOG** - close 356.18, band 354.25-369.69 | stop 341.07 | score 18/20 | earnings in 18d
  - **Historical/audit scaffold snapshot - GS** - close 1,021.00, band 971.53-1048.14 | stop 928.97 | score 15/20 | earnings in 9d
  - **Historical/audit scaffold snapshot - MSFT** - close 390.49, band 389.64-412.56 | stop 378.18 | score 18/20 | earnings in 24d
  - **Historical/audit scaffold snapshot - VRT** - close 300.53, band 300.02-319.13 | stop 276.97 | score 16/20 | earnings in 24d
  - **Historical/audit scaffold snapshot - JPM** - close 334.47, band 304.96-315.95 | stop 296.21 | score 15/20 | earnings in 9d
  - **Historical/audit scaffold snapshot - NVDA** - close 194.83, band 202.81-212.23 | stop 192.95 | score 17/20

**Do not touch — repair or review (3):**
  - **BRK.B** — Repair mode remains active until chart structure and support rebuild make the setup decision-grade again
  - **LMT** — Repair mode remains active until chart structure and support rebuild make the setup decision-grade again
  - **Historical/audit scaffold snapshot - XOM** - close 137.09 is below stop 146.14 -- do not deploy

- **Priority this week (judgment):** _[Fill: which 1–3 names are closest to actionable? What specific trigger would move them to deployed?]_

---

### 4) Catalyst calendar

**This week (Jun 29–Jul 3):** No tracked earnings this week.

**Coming up (next 2 weeks):**
  - **JPM** — earnings 2026-07-14 (in 9d)
  - **GS** — earnings 2026-07-14 (in 9d)
  - **ASML** — earnings 2026-07-15 (in 10d)
  - **NFLX** — earnings 2026-07-16 (in 11d)
  - **GE** — earnings 2026-07-16 (in 11d)

- **FOMC / macro events (judgment):** _[Fill: list any FOMC dates, macro data releases, or geopolitical events that could change the regime this week]_
- **Read-throughs to watch (judgment):** _[Fill: any peer earnings or sector data that would shift conviction on names in the universe?]_

---

### 5) Sector allocation and risk flags

*Draft sector groupings from trigger sheet. Weights are model targets, not live deployed positions.*

| Sector | Names | Risk Cap | Note |
|---|---|---|---|
| Defense | LMT | 25% max | — |
| Diversified Quality | BRK.B | 25% max | — |
| Energy | XOM | 25% max | — |
| Financials | GS, JPM | 25% max | — |
| Industrials | ETN, VRT | 25% max | — |
| Tech | GOOG, MSFT, NVDA | 25% max | — |

- **Concentration check (judgment):** _[Fill: is any sector approaching the 25% cap at current draft weights? What sequencing constraint does that impose?]_
- **Cash level (judgment):** _[Fill: is current cash allocation consistent with regime state and deployment opportunity set?]_
- **Historical/audit scaffold placeholder - risk flags (judgment):** _[Fill: any names approaching stop, any positions requiring re-assessment this week?]_

---

### 6) Risk rules check

- _[Fill: are all sizing tiers being respected? Any escalation triggers from Risk Rules approaching? Drawdown vs. model high?]_

---

### 7) Key questions to answer this week

- _[Fill: what are the 3–5 questions whose answers would most change deployment decisions this week?]_

---

### 8) Friday close / week lookback

- _[Fill at end of week: what happened, what changed, which theses were confirmed or challenged, what updates to the vault are needed?]_
