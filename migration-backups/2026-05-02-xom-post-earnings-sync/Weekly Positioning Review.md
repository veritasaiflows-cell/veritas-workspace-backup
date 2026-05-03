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

## Week of 2026-04-27 to 2026-05-03

### 1) Weekly posture

- **Posture:** Selective risk-on, but with reduced confidence.
- **Confidence level:** Reduced. The machine layer is fresh through the 2026-05-01 close, but dashboard validation still carries 9 warnings, 17 entry bands need review, and timing-sensitive earnings/date mismatches remain unresolved.
- **Operating stance:** Keep the active list narrow. **NVDA** is the only name currently in band. **ETN** and **JPM** remain pullback-only. **GOOG** and **MSFT** stay blocked until post-earnings revalidation is written through the note/trigger layer. **XOM** reported on May 1 but is still not requalified.
- **What changed from earlier in the week:** The Apr 29 FOMC event is behind us, the Fed target remains 3.50%–3.75%, oil is higher again (Brent 108.17 / WTI 101.94 as of May 1), **NVDA** has moved into band, and **XOM** has shifted from pre-earnings watch to post-report review.

---

### 2) Macro regime and confidence

- **Rates / curve:** 2Y 3.88% as of 2026-04-30, 10Y 4.378% as of 2026-05-01, 2s10s +49.8 bps, 3m-10y +80.3 bps. The curve remains positively sloped, but policy is still restrictive.
- **Inflation / energy posture:** Brent 108.17 and WTI 101.94 keep energy pressure alive. No fresh CPI/PCE interpretation was added in this pass, so treat the inflation view as still late-cycle and cautionary rather than cleanly improving.
- **Growth / liquidity posture:** The live machine layer still supports a resilient-growth baseline, not a full risk-off regime. Credit is benign and breadth is recovering, but this is not a clean all-clear because the policy layer still has manual dependencies.
- **Volatility / sentiment:** SPX 7,230.12 and VIX 16.99 keep the regime in selective risk-on territory, not fear. That supports discipline, not chasing.
- **Confidence limits:** policy expectations remain partly manual, direct IR confirmation is still needed for timing-sensitive earnings-date changes, and true pre-market pricing was unavailable from the current yfinance responses.

---

### 3) Weekly deployment map

**Deployable now:**
- **NVDA** — Close 198.45. Entry band 188.03–199.28. Stop 182.40. The only live in-band name right now. Still crowded, so treat it as a disciplined Tier 2 setup, not a free pass.

**Almost deployable — pullback still required:**
- **ETN** — Close 425.55. Band 395.59–420.31. Best chart in the sheet, but still above band and now only 3 days from May 5 earnings.
- **JPM** — Close 312.47. Band 300–306. Still one of the cleanest quality setups, but price is not in the zone yet.

**Blocked pending post-earnings revalidation:**
- **GOOG** — Trigger layer still says blocked. Provider dates have rolled forward to July, but that does **not** count as a real unlock. Revalidate first.
- **MSFT** — Same issue as GOOG. Do not pretend the blocker disappeared just because the next provider date moved.

**Do not touch / repair:**
- **BRK.B** — Repair mode remains active.
- **LMT** — Repair mode remains active.
- **XOM** — Reported May 1, but the setup is still not decision-grade. Post-earnings interpretation comes first.

**Watch / research needed:**
- **AMZN, CAT, GS, RTX, VRT** — live names, but not current deployment names.

---

### 4) Weekly catalyst map

- **Sat May 2:** **BRK.B** earnings.
- **Already hit:** **XOM** reported May 1. Keep it under review until the post-earnings interpretation is written cleanly.
- **Next week (May 4–8):** **WMB, PLTR, EOG, ET, MPLX, LDOS, ETN, AMD, SMCI, KTOS, LNG**.
- **What matters most now:**
  1. clear the post-earnings status of **XOM**
  2. keep **GOOG/MSFT** blocked until post-print revalidation is explicit
  3. manage the **ETN** May 5 catalyst without chasing extension

---

### 5) Portfolio implications

- **Breadth of opportunity is still narrow.** One live in-band name is not a broad green light.
- **Best conditional adds remain ETN and JPM, not the extended names.**
- **Energy is not automatically back on the board.** Oil is strong, but **XOM** still needs post-earnings interpretation and technical requalification.
- **Concentration discipline still matters.** The tech/AI cluster remains the easiest place to outrun risk rules if discipline slips.

---

### 6) Risk focus for the week

- **Top process risk:** 17 entry-band review warnings are still live. Do not act as if every written band is equally clean.
- **Top catalyst risk:** timing-sensitive earnings/date mismatches still need direct confirmation if they matter to a decision.
- **Top market risk:** energy/inflation pressure remains elevated while policy expectations still require manual caution.
- **Top position risk:** treating **NVDA** being in band as permission to ignore crowding or size discipline.

---

### 7) Priority actions

**Do this week:**
1. Review the **XOM** post-earnings packet before changing any energy stance.
2. Keep **NVDA**, **ETN**, and **JPM** as the only real action list.
3. Keep **GOOG** and **MSFT** blocked until post-earnings revalidation is written through the note/trigger layer.
4. Process **BRK.B** today and the **ETN / AMD / SMCI** cluster next week without widening scope.
5. Continue the note-layer truth-sync so the visible operator surfaces stop speaking in late-April future tense.

**Avoid this week:**
- Chasing anything above band.
- Treating provider-rolled July earnings dates as automatic blocker clears.
- Treating **XOM** as requalified before the actual post-earnings interpretation lands.
- Expanding the active list just because the market tape still looks resilient.

---

### 8) Open operating rules for the week

- Warning-grade machine outputs are evidence, not automatic note text.
- A name being in band is necessary, not sufficient.
- Post-earnings revalidation must be explicit for **GOOG**, **MSFT**, and **XOM**.
- Keep weekly notes aligned to current evidence, not to the prior catalyst calendar.

---

## Freshness and refresh policy

- **Last updated:** 2026-05-02
- **Data as of:** 2026-05-01 close
- **Next mandatory refresh:** after the BRK.B result is assessed and again after the ETN / AMD / SMCI cluster next week
- **Refresh policy:** update posture, catalyst map, and deployment map when a result or price move materially changes the decision surface. Do not rewrite for noise.
