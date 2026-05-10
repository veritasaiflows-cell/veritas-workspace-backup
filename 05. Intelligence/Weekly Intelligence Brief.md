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

## Week of May 4–May 8, 2026

*Refreshed 2026-05-07. Data as of 2026-05-06 close unless noted. Machine evidence came from `tmp/market-state.json`, `tmp/trigger-sheet.json`, `tmp/technical-refresh.json`, `tmp/dashboard-validation.json`, current post-earnings packets, and the latest run summaries. Canonical mutation remains owner-gated: dashboard validation is warning-grade because LNG is the only blocking band-review warning; 16 other band-review items are monitor-only.*

---

### 1. Macro pulse

- **Fed funds rate:** 3.50%–3.75%, confirmed 2026-04-29. Next FOMC 2026-06-17.
- **Fed cut expectations:** 0% cut probability in the current machine layer.
- **2Y Treasury:** 3.930% as of 2026-05-05.
- **10Y Treasury:** 4.356% as of 2026-05-06.
- **3M T-bill:** 3.600% as of 2026-05-06.
- **2s10s spread:** +42.6 bps.
- **3M-10Y spread:** +75.6 bps.
- **Dollar:** DXY 97.96 as of 2026-05-06.
- **Volatility / tape:** SPX 7,365.12 and VIX 17.39.

**Regime read:** Restrictive pause, resilient growth baseline, selective risk-on. That is still the right base case, but confidence is not clean because policy expectations remain simplified, dashboard validation has one LNG blocking warning, and energy is still elevated enough to keep inflation risk alive.

---

### 2. Energy sweep

- **Brent crude:** 102.06 as of 2026-05-06.
- **WTI crude:** 95.82 as of 2026-05-06.
- **Brent/WTI spread:** 6.24.
- **Portfolio implication:** energy pricing is still strong enough to matter, but it cooled from the prior note and does **not** automatically make energy names deployable. The live decision still runs through post-earnings interpretation plus chart quality.
- **XOM implication:** the market backdrop is better for the business than it was when oil was in the low 90s, and the scorecard now says the quarter was stronger than the GAAP headline. That still does **not** put XOM back on the active board. It stays benched until post-print follow-through gets cleaner.

---

### 3. Geopolitical scan

- **What the machine layer can honestly say:** elevated oil still implies a live geopolitical or supply-premium backdrop.
- **What this pass does *not* claim:** no fresh external geopolitical sweep was run inside this bounded truth-sync pass, so do not pretend a clean Iran/Hormuz update was freshly revalidated here.
- **Practical read-through:** keep energy and defense sensitivity on the radar, but do not write narrative certainty that the evidence did not refresh.

---

### 4. Earnings radar

**Just reported / immediate review:**
- **XOM** — reported 2026-05-01. Scorecard complete. Underlying quarter was stronger than the GAAP headline, but the name remains *closed with follow-up*, not requalified.

**Just processed from the May 5 window:**
- **ETN** — Q1 2026 interpreted from secondary evidence after direct primary-source fetch did not land cleanly. Beat / revenue upside / raised-guidance evidence is constructive, but guidance and reaction nuance keep ETN **almost deployable**, not promoted.
- **AMD** — Q1 2026 primary-source confirmed. Revenue $10.253B (+38% YoY), non-GAAP EPS $1.37, Data Center revenue $5.8B (+57% YoY). Constructive AI infrastructure read-through, but no standalone portfolio deployment trigger.
- **SMCI** — Q3 2026 interpreted from secondary evidence after IR fetch was blocked. EPS beat / upbeat forward-demand signal is constructive for AI servers, but company-specific risk and missing primary details keep this read-through only.

**Next immediate window:**
- **KTOS** — 2026-05-06
- **LNG** — 2026-05-07
- **April NFP** — 2026-05-08

**Key earnings judgment for the week:**
- The May 5 AI-infrastructure cluster supports the demand regime, but it does **not** unlock capital deployment by itself.
- ETN remains an almost-deployable post-earnings candidate pending primary-source confirmation and next-session price confirmation.
- AMD and SMCI are read-through evidence for the AI infrastructure sleeve, especially NVDA / server / power-enabler demand, not direct deployment triggers.

---

### 5. Analyst and institutional flow

- No fresh, trustworthy analyst-flow or 13F pass was added in this bounded truth-sync.
- Do **not** recycle older upgrade/downgrade language as if it were current.
- If analyst-flow matters for a live decision this week, pull it fresh instead of inheriting stale April commentary.

---

### 6. Technical check

**Closest actionable names:**
- **JPM** — deployable now in the owner layer; explicit approval landed on 2026-05-07, but normal size discipline and no automatic execution still apply.
- **NVDA** — promotion review only; in band, but crowding, sizing, and May 20 timing risk still require discipline.
- **ETN** — almost deployable; post-earnings interpretation is constructive but still needs primary-source follow-up and next-session confirmation.
- **GOOG** — almost deployable on thesis, but close is extended above the refreshed band; no chase.
- **GS** — almost deployable; above band, tactical secondary to JPM, and still not deployable-now just because the cash/cap posture is now resolved.
- **MSFT** — almost deployable; slightly above band and still needs cleaner repair / promotion.

**Blocked / repair names that still matter:**
- **BRK.B, LMT, XOM** — do not touch / repair.

**Important caveat:**
- Dashboard validation is warning-grade because **LNG** is the only blocking band-review warning.
- The other 16 band-review items are monitor-only, not deployment blockers.
- That means the technical layer is usable, but not clean enough to justify loose interpretation.

---

### 7. Sentiment gauge

- **VIX:** 17.39.
- **S&P 500:** 7,365.12.
- **Breadth:** the machine layer says breadth is broad / recovering.
- **Read:** the tape still supports selective risk-on, but this is not a low-risk “buy everything” environment. The live setup list is narrow and the one-warning validation surface is still doing real work.

---

### 8. Recommended actions

**Posture:** Selective risk-on, reduced confidence.

**Highest-priority actions this week:**
1. **Treat deployable-now as narrow, not broad.** **JPM** is now the sole deployable-now name in the owner layer.
2. **Keep NVDA in promotion review** and do not widen from one approved name into a broad green light; timing sensitivity and crowding still matter.
3. **Use AMD and SMCI as constructive AI-infrastructure read-through**, not as standalone portfolio triggers.
4. **Keep ETN conditional after the print.** Constructive evidence is not enough without primary-source follow-up and next-session price confirmation.
5. **Use the XOM scorecard as the canonical read and keep energy benched until follow-through improves.**

**Avoid:**
- Overriding blocked status just because provider next-earnings dates rolled forward.
- Treating XOM’s May 1 report as immediate requalification just because the scorecard is written.
- Treating warning-grade machine output as canonical language.

---

## Freshness and refresh policy

- **Last updated:** 2026-05-07
- **Data as of:** 2026-05-06 close plus May 5 ETN / AMD / SMCI post-earnings interpretation
- **Next refresh due:** after Eaton and SMCI primary-source follow-up is captured, LNG / NFP follow-up is processed, and NVDA timing is rechecked no later than 2026-05-13
- **Refresh policy:** rewrite only the sections whose truth changed. Do not drag stale prior-week language forward just because it already exists.
