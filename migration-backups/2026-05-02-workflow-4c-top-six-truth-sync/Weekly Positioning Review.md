# Weekly Positioning Review

## Purpose

Use this as the standing weekly operating map.

It sits between the broad Sunday intelligence sweep and the short weekday execution card.

Use it to answer:
- what is the market posture for this week?
- which names matter this week?
- which names are closest to actionable, blocked, or benched?
- which catalysts actually matter this week?
- what portfolio and risk implications matter right now?

Boundary:
- this is the canonical weekly operating map
- summarize only the names and catalysts that matter this week
- do not duplicate full portfolio tables from [[03. Portfolio/Portfolio Snapshot]]
- do not duplicate full gate-by-gate trigger logic from [[03. Portfolio/Deployment Trigger Sheet]]
- let the daily executive summary handle next-session execution detail

Script-backed prep path:
- default to `python scripts/run_finance_refresh_chain.py post-close`
- use narrower script calls only when intentionally validating or debugging one layer
- treat outputs in `tmp/` as evidence inputs, not as automatic final note text

---

## Week of 2026-04-27 to 2026-05-02

### 1) Weekly posture

- **Posture:** Defensive-neutral. Stand down unless price comes to us.
- **Confidence level:** Moderate. Macro data is fresh (Apr 24 close), but the week ahead is the highest-catalyst density of the quarter. No setup should be forced into this window.
- **Operating stance:** Wait for earnings and FOMC to set new levels. The portfolio has no deployable names at current prices — ETN, JPM, and NVDA remain conditional-pullback-only. Every blocked name stays blocked until post-print evidence exists.
- **What changed from last week:** Oil has recovered sharply — Brent $99, WTI $94 as of Apr 24, up ~$9-10 from Apr 17 levels. This changes the XOM picture materially going into May 1 earnings. LMT reported Apr 23 and dropped ~14% to $509 — full repair mode, do not touch. VRT reported Apr 22 beat-and-raise — positive AI power-demand read-through but no defined entry yet. FOMC now 2 days away. Megacap earnings cluster (MSFT/GOOG/AMZN) lands Apr 29 after close.

---

### 2) Macro regime and confidence

- **Rates / curve:** 2Y 3.83%, 10Y 4.31%, 2s10s +48 bps, 3m-10y +71.7 bps. Curve steepening slowly. Front-end restrictive. FOMC decision Apr 29 — no cut. Powell's tone is the real variable.
- **Inflation posture:** March CPI +3.3% YoY, Core +2.6% YoY. April CPI (May 12) should show energy relief from post-ceasefire crash — but oil has partially recovered to $94-99, which complicates the narrative. Core stickiness remains the Fed's stated concern.
- **Labor / growth:** March payrolls +178k, unemployment 4.3%. Softening at the margin, not breaking. Q1 GDP advance estimate Apr 30 — Hormuz shock hit March production. A large miss (below 1.5%) is a regime reassessment signal.
- **Volatility / sentiment:** VIX 18.71 as of Apr 24. Not complacent, not fearful. Symmetric risk from all-time-high SPX 7,165.
- **Energy / dollar context:** Oil recovery is the week's most underappreciated development. Brent $99, WTI $94 as of Apr 24 — up ~$9-10 from Apr 17. DXY 98.51, softer dollar provides mild multi-national support.
- **Confidence limits:** Fed rate hardcoded, FedWatch manually maintained. 2Y carries 1-day FRED lag (expected, not a failure). All data as of Apr 24 close.

---

### 3) Weekly deployment map

**Closest actionable — conditional pullback only:**
- **ETN** — Almost deployable. Close $424.88. Entry band 388-396. 7.3% above band. Best chart in the portfolio but extended. Only on genuine pullback into band. Earnings timing Apr 30-May 5 still unresolved — treat as conditional block until confirmed.
- **JPM** — Almost deployable. Close $309.46. Entry band 300-306. Only 1.1% above band top. Best high-quality conditional add this week. No near-term earnings blocker. Only legitimate add window this week if it gives back $3-5.
- **NVDA** — Almost deployable. Close $208.96. Entry band 186-191. 9.4% above band. Valid only on a real pullback. May 20 earnings unconfirmed — treat as timing-sensitive.

**Blocked — do not add before prints:**
- **MSFT** — Hard block into Apr 29 after close. Close $420.24, band 393-401.
- **GOOG** — Hard block into Apr 29 after close. Close $338.98, band 314-321.
- **AMZN** — Hard block into Apr 29 after close. Close $261.41, no band defined yet.

**Repair / do not touch:**
- **LMT** — Do not touch. Close $509.68, below all MAs. Pre-broken setup confirmed by earnings. No re-entry until new base forms above 200-day (~$519). Earliest review: May-June.
- **XOM** — Do not touch pre-May-1 earnings. Close $147.80. Oil recovery at $94 WTI changes the prior under-review framing — May 1 is the requalification event.
- **BRK.B** — Bench. Close $468.74, below all MAs. Possible May 2 earnings (unconfirmed). No deployment before earnings or before chart repairs through $481.

**Watch / not deployment-grade:**
- VRT, RTX, CAT, GS — all underdefined technically. Stay benched.

---

### 4) Weekly catalyst map

- **Mon Apr 28:** FOMC Day 1. Watch pre-FOMC market tone.
- **Tue Apr 29 2:00 PM ET:** FOMC rate decision + Powell press conference. No cut expected. Tone is what matters.
- **Tue Apr 29 after close:** MSFT, GOOG, AMZN, META earnings. Dominant event of the week for this portfolio.
- **Wed Apr 30 8:30 AM ET:** Q1 2026 GDP advance estimate. Key growth read through Hormuz period.
- **Wed Apr 30 — possible ETN earnings:** Date unresolved (Apr 30 vs May 5). Monitor Eaton IR.
- **Thu May 1:** XOM Q1 2026 earnings. Requalification event for energy thesis.
- **Sat May 2 — possible BRK.B earnings:** Unconfirmed. Treat as live timing risk.

**Event sequencing risk:** The Apr 29 cluster is the dominant compression point. Four mega-cap prints simultaneous with FOMC = maximum binary risk. Do not have conditional entries that could trigger accidentally into this window.

**What matters most:** Apr 29 FOMC tone + MSFT/GOOG results. These two events together set the posture for the next 3-4 weeks.

---

### 5) Portfolio implications

- **Sizing / concentration posture:** Zero deployable names now. Cash 20% stays intact. No deployment justified at current prices.
- **Tech/AI concentration flag:** MSFT + GOOG + ETN + NVDA = ~37% at full draft weight. At or above the 35% sector cap in Risk Rules. Post-Apr-29, do not deploy both MSFT and GOOG simultaneously — sequence and monitor concentration.
- **What can be added this week:** JPM only, if it genuinely pulls back to 300-306 before Apr 29. That is the sole legitimate add window this week.
- **What stays blocked:** MSFT, GOOG, AMZN — hard block until post-Apr-29 prints. ETN — conditional block until earnings timing confirmed.
- **Cross-position read-throughs:** META → GOOG ad market read. COP (Apr 30) → XOM upstream energy read. AMD (May 5) → NVDA AI chip cycle read.
- **Portfolio cleanup needed:** LMT post-earnings scorecard not yet synced. VRT post-earnings scorecard not yet synced.

---

### 6) Risk focus for the week

- **Top market risk:** FOMC hawkish surprise or MSFT/GOOG earnings disappointment from all-time-high SPX. VIX at 18.71 means the market is unhedged. A 3-5% drawdown in two sessions is the realistic bad outcome.
- **Top portfolio risk:** Tech/AI concentration — if MSFT and GOOG both disappoint Apr 29, two of the largest draft positions are printing negative simultaneously.
- **Top process risk:** Forcing a JPM entry just because other names are blocked. Only a genuine pullback into band is justified.
- **Invalidation or escalation triggers:** Q1 GDP below 1.0% = regime reassessment. MSFT Azure growth below 18% = reconsider core draft status. GOOG search revenue decline = reconsider core draft status. Powell signals more hikes possible = immediate portfolio review.

---

### 7) Priority actions

**Do this week:**
1. Monitor JPM only — the sole legitimate add candidate if it pulls back to 300-306 before Apr 29.
2. Run morning readiness chain each weekday.
3. After Apr 29 close: interpret MSFT and GOOG results. Update Technical Entry Sheet, Deployment Trigger Sheet, and Portfolio Snapshot within 24 hours.
4. After Apr 30 GDP: update Macro Regime Dashboard if growth read materially changes regime framing.
5. After May 1 XOM: resolve under-review status definitively — requalify or explicitly bench.

**Watch this week:**
- ETN pulling back toward 388-396 before the earnings window tightens
- NVDA giving back extension toward 186-191
- Oil holding above $90 WTI into XOM earnings
- BRK.B earnings date confirmation
- COP (Apr 30) upstream energy read

**Avoid this week:**
- Adding to any blocked name before its earnings print
- Treating LMT as a near-term opportunity — the setup does not exist yet
- Overriding concentration discipline even if MSFT and GOOG both print strong
- Making any decision based on first 30 minutes of post-earnings price action

---

### 8) Open operating rules for the week

- A beat from MSFT or GOOG does not erase an extended chart. Re-verify entry bands in the Technical Entry Sheet before treating any post-earnings name as deployable.
- If either MSFT or GOOG misses materially, revisit draft core status — a thesis miss is different from a price miss.
- XOM under-review status must be formally resolved by end of day May 1. It cannot stay in perpetual under-review.
- ETN earnings timing must be resolved before the window forces a blind decision. Confirm Eaton IR before treating ETN as freely deployable.
- Use this note as the baseline reference for weekday daily execution cards. Do not duplicate trigger sheet or technical sheet detail — point there instead.

---

## Freshness and refresh policy

- Last updated: 2026-04-26
- Data as of: 2026-04-24 close
- Next mandatory refresh: after Apr 29 FOMC + MSFT/GOOG prints. Update posture, deployment map, and risk section within 24 hours.
- Refresh policy: update posture, catalyst map, and deployment map when events materially change the picture. Do not rewrite standing doctrine sections unless something actually changed.

---

## [Template — for future weeks]

### 1) Weekly posture

- **Posture:**
- **Confidence level:**
- **Operating stance:**
- **What changed from last week:**

### 2) Macro regime and confidence

- **Rates / curve:**
- **Inflation posture:**
- **Labor / growth:**
- **Volatility / sentiment:**
- **Energy / dollar context:**
- **Confidence limits and missing data:**

### 3) Weekly deployment map

Summarize only the names that matter this week.

- **Closest actionable names:**
- **Blocked names:**
- **Repair / do not touch:**
- **Watch / not deployment-grade:**

### 4) Weekly catalyst map

- **Macro events this week:**
- **Tracked earnings this week:**
- **Event sequencing risk:**
- **What matters most:**

### 5) Portfolio implications

- **Sizing / concentration posture:**
- **What can be added this week:**
- **What stays blocked:**
- **Cross-position read-throughs:**
- **Portfolio cleanup needed:**

### 6) Risk focus for the week

- **Top market risk:**
- **Top portfolio risk:**
- **Top process risk:**
- **Invalidation or escalation triggers:**

### 7) Priority actions

- **Do this week:**
- **Watch this week:**
- **Avoid this week:**

### 8) Open operating rules for the week

- Do not restate standing doctrine unless it changed materially.
- Use this note as the baseline reference for weekday daily execution cards.
- If a tracked earnings result materially changes setup quality, blocker status, or conviction, update this note selectively when needed.
- If true pre-market pricing is unavailable, say so explicitly in downstream daily cards.
- If a detail belongs in the trigger sheet or technical sheet, point there instead of duplicating it here.
---

## Week of 2026-04-27 to 2026-05-01

### 1) Weekly posture

- **Posture (judgment):** _[Fill: Offensive / Defensive-neutral / Defensive]_
- **Confidence level (judgment):** _[Fill: High / Moderate / Low — state the basis]_
- **Operating stance (judgment):** _[Fill: what is the 1-sentence directive for this week?]_
- **What changed from last week (judgment):** _[Fill: key developments since last review]_

---

### 2) Macro regime and confidence

*Machine-populated from market-state.json as of 2026-04-27. Sections marked (judgment) require human/AI interpretation.*

- **Fed / rates:** Target 3.50%–3.75% (confirmed 2026-04-19). Next FOMC 2026-04-29 — cut probability unavailable. 2Y 3.780%, 10Y 4.336%, 3M 3.590%.
- **Yield curve:** 2s10s +56 bps, 3m-10y +75 bps. Curve constructive but front-end still restrictive.
- **Volatility / equities:** VIX 18.02, SPX 7,173.91.
- **Dollar / energy:** DXY 98.53, Brent 102.10 $/bbl, WTI 96.89 $/bbl.
- **Regime assessment (judgment):** _[Fill: is this week's data consistent with late-cycle restrictive baseline? Any threshold approaching?]_

---

### 3) Deployment map

*Data: trigger-sheet.json as of 2026-04-24*


**Almost deployable — pullback required (3):**
  - **ETN** — close 423.92, band 383.41–406.93 | stop 371.65 | score 16/20 | earnings in 9d
  - **JPM** — close 308.28, band 300-306 | stop 295.50 | score 18/20
  - **NVDA** — close 208.27, band 185.74–196.3 | stop 180.46 | score 16/20 | earnings in 24d

**Blocked — earnings or event (3):**
  - **AMZN** — Earnings block active until 2026-04-29 (3d)
  - **GOOG** — Earnings block active until 2026-04-29 (3d)
  - **MSFT** — Earnings block active until 2026-04-29 (3d)

**Do not touch — repair or review (4):**
  - **BRK.B** — Repair mode remains active until chart structure and support rebuild make the setup decision-grade again
  - **LMT** — Repair mode remains active until chart structure and support rebuild make the setup decision-grade again
  - **RTX** — Name is tracked, but not yet decision-grade because explicit entry and stop are still missing
  - **XOM** — Repair mode remains active until chart structure and support rebuild make the setup decision-grade again

**Active watch — no entry band yet (3):**
  - **CAT** — Name is tracked, but not yet decision-grade because explicit entry and stop are still missing
  - **GS** — Name is tracked, but not yet decision-grade because explicit entry and stop are still missing
  - **VRT** — Name is tracked, but not yet decision-grade because explicit entry and stop are still missing

- **Priority this week (judgment):** _[Fill: which 1–3 names are closest to actionable? What specific trigger would move them to deployed?]_

---

### 4) Catalyst calendar

**This week (Apr 27–May 1):**
  - **GD** — earnings 2026-04-29 (in 2d)
  - **MSFT** — earnings 2026-04-29 (in 2d)
  - **GOOG** — earnings 2026-04-29 (in 2d)
  - **EQIX** — earnings 2026-04-29 (in 2d)
  - **AMZN** — earnings 2026-04-29 (in 2d)
  - **COP** — earnings 2026-04-30 (in 3d)
  - **CAT** — earnings 2026-04-30 (in 3d)
  - **XOM** — earnings 2026-05-01 (in 4d)
  - **CVX** — earnings 2026-05-01 (in 4d)

**Coming up (next 2 weeks):**
  - **BRK.B** — earnings 2026-05-02 (in 5d)
  - **WMB** — earnings 2026-05-04 (in 7d)
  - **PLTR** — earnings 2026-05-04 (in 7d)
  - **EOG** — earnings 2026-05-05 (in 8d)
  - **ET** — earnings 2026-05-05 (in 8d)
  - **MPLX** — earnings 2026-05-05 (in 8d)
  - **LDOS** — earnings 2026-05-05 (in 8d)
  - **ETN** — earnings 2026-05-05 (in 8d)
  - **AMD** — earnings 2026-05-05 (in 8d)
  - **SMCI** — earnings 2026-05-05 (in 8d)
  - **KTOS** — earnings 2026-05-06 (in 9d)
  - **LNG** — earnings 2026-05-07 (in 10d)

- **FOMC / macro events (judgment):** _[Fill: list any FOMC dates, macro data releases, or geopolitical events that could change the regime this week]_
- **Read-throughs to watch (judgment):** _[Fill: any peer earnings or sector data that would shift conviction on names in the universe?]_

---

### 5) Sector allocation and risk flags

*Draft sector groupings from trigger sheet. Weights are model targets, not live deployed positions.*

| Sector | Names | Risk Cap | Note |
|---|---|---|---|
| Defense | LMT, RTX | 35% max | — |
| Energy | XOM | 35% max | — |
| Financials | JPM, BRK.B, GS | 35% max | — |
| Industrials | ETN, CAT | 35% max | — |
| Tech | NVDA, AMZN, GOOG, MSFT | 35% max | — |

- **Concentration check (judgment):** _[Fill: is any sector approaching the 35% cap at current draft weights? What sequencing constraint does that impose?]_
- **Cash level (judgment):** _[Fill: is current cash allocation consistent with regime state and deployment opportunity set?]_
- **Risk flags (judgment):** _[Fill: any names approaching stop, any positions requiring re-assessment this week?]_

---

### 6) Risk rules check

- _[Fill: are all sizing tiers being respected? Any escalation triggers from Risk Rules approaching? Drawdown vs. model high?]_

---

### 7) Key questions to answer this week

- _[Fill: what are the 3–5 questions whose answers would most change deployment decisions this week?]_

---

### 8) Friday close / week lookback

- _[Fill at end of week: what happened, what changed, which theses were confirmed or challenged, what updates to the vault are needed?]_
