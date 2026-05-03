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

## Week of April 27–May 3, 2026

*Refreshed 2026-05-02. Data as of 2026-05-01 close unless noted. Machine evidence came from `tmp/market-state.json`, `tmp/trigger-sheet.json`, `tmp/post-earnings-prep.json`, `tmp/post-earnings-note-targets.json`, `tmp/weekly-intelligence-brief.json`, and the latest run summaries. Canonical mutation remained human-gated because dashboard validation still carried 9 warnings.*

---

### 1. Macro pulse

- **Fed funds rate:** 3.50%–3.75%, confirmed 2026-04-29. Next FOMC 2026-06-17.
- **Fed cut expectations:** 0% cut probability in the current machine layer.
- **2Y Treasury:** 3.880% as of 2026-04-30.
- **10Y Treasury:** 4.378% as of 2026-05-01.
- **3M T-bill:** 3.575% as of 2026-05-01.
- **2s10s spread:** +49.8 bps.
- **3M-10Y spread:** +80.3 bps.
- **Dollar:** DXY 98.21 as of 2026-05-01.
- **Volatility / tape:** SPX 7,230.12 and VIX 16.99.

**Regime read:** Restrictive pause, resilient growth baseline, selective risk-on. That is still the right base case, but confidence is not clean because the policy layer is partly manual, the warning stack remains real, and energy is still elevated enough to keep inflation risk alive.

---

### 2. Energy sweep

- **Brent crude:** 108.17 as of 2026-05-01.
- **WTI crude:** 101.94 as of 2026-05-01.
- **Brent/WTI spread:** 6.23.
- **Portfolio implication:** energy pricing is strong enough to matter, but that does **not** automatically make energy names deployable. The live decision still runs through post-earnings interpretation plus chart quality.
- **XOM implication:** the market backdrop is better for the business than it was when oil was in the low 90s, but the note layer should not front-run the actual post-report interpretation. XOM stays in do-not-touch / under-review posture for now.

---

### 3. Geopolitical scan

- **What the machine layer can honestly say:** elevated oil still implies a live geopolitical or supply-premium backdrop.
- **What this pass does *not* claim:** no fresh external geopolitical sweep was run inside this bounded truth-sync pass, so do not pretend a clean Iran/Hormuz update was freshly revalidated here.
- **Practical read-through:** keep energy and defense sensitivity on the radar, but do not write narrative certainty that the evidence did not refresh.

---

### 4. Earnings radar

**Just reported / immediate review:**
- **XOM** — reported 2026-05-01. The structured packet now exists, but the interpretation fields are still blank. Treat this as *reported, under review*, not as automatically requalified.

**Earnings today / immediate window:**
- **BRK.B** — 2026-05-02.

**Next week (May 4–8):**
- **WMB** — 2026-05-04
- **PLTR** — 2026-05-04
- **EOG** — 2026-05-05
- **ET** — 2026-05-05
- **MPLX** — 2026-05-05
- **LDOS** — 2026-05-05
- **ETN** — 2026-05-05
- **AMD** — 2026-05-05
- **SMCI** — 2026-05-05
- **KTOS** — 2026-05-06
- **LNG** — 2026-05-07

**Key earnings judgment for the week:**
- **GOOG** and **MSFT** are no longer “about to report,” but they are also **not** cleanly unlocked yet. The trigger layer still carries them as blocked pending post-earnings revalidation.
- **ETN** is the next important setup because it is still almost deployable while the May 5 report is only days away.

---

### 5. Analyst and institutional flow

- No fresh, trustworthy analyst-flow or 13F pass was added in this bounded truth-sync.
- Do **not** recycle older upgrade/downgrade language as if it were current.
- If analyst-flow matters for a live decision this week, pull it fresh instead of inheriting stale April commentary.

---

### 6. Technical check

**Closest actionable names:**
- **NVDA** — deployable now; close 198.45 inside the 188.03–199.28 band.
- **ETN** — almost deployable; close 425.55, still above the 395.59–420.31 band and now close to earnings.
- **JPM** — almost deployable; close 312.47 vs. 300–306.

**Blocked / repair names that still matter:**
- **GOOG, MSFT** — blocked pending post-earnings revalidation.
- **BRK.B, LMT, XOM** — do not touch / repair.

**Important caveat:**
- 17 entry bands still need review.
- **GS** is in band while deployment state still reads WATCH.
- That means the technical layer is usable, but not clean enough to justify loose interpretation.

---

### 7. Sentiment gauge

- **VIX:** 16.99.
- **S&P 500:** 7,230.12.
- **Breadth:** the machine layer says breadth is broad / recovering.
- **Read:** the tape still supports selective risk-on, but this is not a low-risk “buy everything” environment. The live setup list is narrow and the warning stack is still doing real work.

---

### 8. Recommended actions

**Posture:** Selective risk-on, reduced confidence.

**Highest-priority actions this week:**
1. **Review XOM properly.** Report landed; interpretation still has to be written before any status change is honest.
2. **Treat NVDA as the only live in-band name.** If it is considered, size discipline matters because crowding risk is still real.
3. **Keep ETN and JPM conditional.** No chase above written bands.
4. **Keep GOOG and MSFT blocked until post-earnings revalidation is explicit.**
5. **Use the BRK.B / ETN / AMD / SMCI cluster as the next real decision window.**

**Avoid:**
- Overriding blocked status just because provider next-earnings dates rolled forward.
- Treating XOM’s May 1 report as a bullish conclusion before the interpretation exists.
- Treating warning-grade machine output as canonical language.

---

## Freshness and refresh policy

- **Last updated:** 2026-05-02
- **Data as of:** 2026-05-01 close
- **Next refresh due:** after BRK.B is processed and again after the ETN / AMD / SMCI cluster next week
- **Refresh policy:** rewrite only the sections whose truth changed. Do not drag stale prior-week language forward just because it already exists.
