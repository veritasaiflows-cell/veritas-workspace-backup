# Vault Efficiency and Precision Audit
## Conducted by Claude — April 26, 2026

**Scope:** Full structural audit of 01. Dashboards through 06. Playbooks, plus supporting layers (07. Risk, 08. Audits, scripts/, tmp/). Focused on: structural redundancy, information precision, decision-grade gaps, and the path to a more autonomous investment OS.

**Verdict:** The vault is architecturally sound but operationally bloated. The script layer is mature. The core decision logic (5-gate framework, operating window model, source-of-truth hierarchy) is genuinely good. But the note layer has accumulated significant redundancy that is creating maintenance drag and inconsistency risk — not because it was built badly, but because it was built iteratively and the consolidation pass never happened. The system is also missing three structural pieces that prevent it from being truly decision-grade: no prediction tracking, no regime-fit scoring, and no quantified feedback loop.

---

## What Is Working Well

Before the problems: these things are real and should not be changed.

**The 5-gate deployment framework** is excellent discipline. Thesis → Macro → Technical → Catalyst → Risk. It prevents the most common failure mode (buying a good company at a bad time). Keep it.

**The three operating-window model** (morning, post-close, post-earnings) is mature. `run_finance_refresh_chain.py` as the single orchestration entrypoint is exactly right. The fact that individual scripts can still be called directly for debugging is correct architecture.

**The source-of-truth hierarchy** in Operating Model is clear and well-enforced. The distinction between canonical notes, machine-generated `tmp/` artifacts, and derived dashboard surfaces is the right mental model.

**The Event Calendar** is the best-maintained file in the vault. Closure-state labels (Reported/Interpreted/Synced/Closed), date-mismatch flagging, and the distinction between confirmed vs. script-surfaced dates are all done correctly.

**The Daily Executive Summaries** are properly derived. They do not pretend to be canonical. The Apr 24 card in particular shows the right discipline — it reports partial-data status, keeps deployment conditions explicit, and does not override the canonical layer.

**The Coverage Universe** structure is the right foundation for a research universe. Four fields (tier/status/thesis/key risk/act when) is the minimum viable investment thesis record. Good.

---

## Critical Problems (Fix These First)

### 1. The Watchlist Is a Zombie File

The Watchlist is the most redundant file in the vault. It currently contains:
- A summary table with tier/thesis/trigger/risk/status → duplicated in Coverage Universe
- A tactical setups table → duplicated in Deployment Trigger Sheet
- A speculative sleeve table → duplicated in Coverage Universe
- A Tier 1/2/3 priority ranking → duplicated in Deployment Trigger Sheet priority order
- "Top 5 to 7 candidates" → duplicated in Portfolio Snapshot
- Next review questions → belong in Next Actions

The Deployment Trigger Sheet was built explicitly to supersede the Watchlist's deployment logic. The Coverage Universe was built explicitly to supersede the Watchlist's thesis record. The Watchlist was never retired.

**Result:** When a name's status changes, it must be updated in 3-4 files. The Apr 24 LMT post-earnings update touched the Watchlist, Deployment Trigger Sheet, Technical Entry Sheet, Portfolio Snapshot, and Coverage Universe. That is five places to stay consistent. In practice, they drift.

**Fix:** Retire the Watchlist as a standalone canonical file. Its content should live in two places only:
- Tier/thesis/status/act-when: Coverage Universe
- Deployment state/priority order: Deployment Trigger Sheet

The Watchlist can survive as a *single-page navigation index* — a short table pointing to Coverage Universe for thesis and Deployment Trigger Sheet for action state — but it should not carry its own content.

---

### 2. Redundant Priority Rankings Across Four Files

The priority ranking of tracked names currently appears in:
1. Watchlist (Tier 1/2/3 section)
2. Deployment Trigger Sheet (Current priority order + deployment board)
3. Technical Entry Sheet (Current ranking after precision pass)
4. Portfolio Snapshot (Current priority order paragraph)

These four lists are not always in the same order. They drift. When the Apr 23 LMT print happened, the ranking in the Technical Entry Sheet and the Deployment Trigger Sheet were updated, but the Watchlist ranking preserved slightly different language.

**Fix:** Deployment Trigger Sheet owns the priority ranking. Period. It is the canonical deployment-decision layer per Operating Model. Every other file should either point to the Trigger Sheet or omit rankings entirely. The Technical Sheet should report technical posture, not priority order. The Portfolio Snapshot should state posture, not restate a ranking that already exists in the Trigger Sheet.

---

### 3. The Weekly Positioning Review Is Never Filled

This is the vault's most valuable synthesis document. It answers: what is the posture for this week, which names matter, which catalysts drive the week, and what are the portfolio implications. It sits at the intersection of macro + technical + event calendar + portfolio posture.

It has never been filled. Every week it is a template.

The Monday Game Plan for Apr 27 was built — good — but it is a daily execution card, not the weekly operating map. The Monday plan is derived from a weekly plan that does not exist.

**Fix:** The Weekly Positioning Review must be treated as mandatory, not optional. Build a `run_finance_refresh_chain.py sunday` operating window that generates a skeleton from `tmp/` artifacts and forces the weekly fill before Monday. If the script cannot generate the skeleton, Claude or Veritas should be required to fill it manually before Monday open. A blank Weekly Positioning Review is an operating failure, not an oversight.

---

### 4. The Partial-Data Problem Has No Resolution Plan

The following failures have been documented since at least April 19 — one week before this audit:
- 2Y Treasury (FRED DGS2) failing intermittently, causing true 2s10s to be unavailable
- FedWatch cut probability not wired — manually maintained
- Earnings dates for ETN, NVDA, BRK.B unresolved between script output and vault note layer

These are not flagged as temporary warnings. They are becoming permanent accepted states. The April 24 Daily Executive Summary says "confidence is moderate to reduced" and lists partial-data conditions as context. But there is no action plan to fix them.

A decision-grade OS that permanently operates at reduced macro confidence is not a decision-grade OS. It is a system that has learned to apologize for its own gaps.

**Specific fixes available now:**

- **2Y Treasury:** FRED offers a free public API at `https://fred.stlouisfed.org/graph/fredgraph.csv?id=DGS2`. No key required for basic public data pulls. `market_state_refresh.py` should retry this endpoint and fall back to a second source (Treasury.gov `yc_curve` endpoint) before marking it partial.
- **FedWatch:** CME publishes cut probabilities at `https://www.cmegroup.com/markets/interest-rates/cme-fedwatch-tool.html`. The data is scrapable via their public tool. This has been labeled "unwired" for 7+ days. Wire it.
- **Earnings date mismatch (ETN, NVDA, BRK.B):** These three names need a single confirmed-date entry in the Event Calendar with an explicit source label. Stop carrying the ambiguity across multiple files. Pick a primary confirmation source (company IR page or SEC 8-K), fetch it once, record it with source and date, and treat it as resolved. If it cannot be confirmed, state that once in the Event Calendar and stop propagating the caveat into five other files.

**Deadline:** These three fixes should be resolved before the April 28-29 FOMC / megacap earnings cluster. Operating into the most catalyst-dense week of the quarter with degraded macro confidence is exactly the wrong time to accept persistent partial-data warnings.

---

### 5. No Prediction Tracking or Feedback Loop

The system makes directional calls continuously:
- "ETN is the best current setup"
- "JPM is the best high-quality conditional add"
- "XOM under review, not deployable"
- "NVDA only on pullback to 186-191"

None of these calls are logged against outcomes. There is no file in the vault that records: date called, prediction, conviction level, what happened, whether the call was right.

This is the most significant precision gap in the entire system. Without a feedback loop, there is no way to know whether the analytical process works. Calls that age out are simply replaced by new calls. Good calls and bad calls are indistinguishable in retrospect.

A system that aspires to be an autonomous investment OS must track its own prediction accuracy. Otherwise it is not intelligence — it is a well-formatted opinion.

**Fix:** Create `04. Research/Call Log.md`. Structure:

| Date | Ticker | Call | Conviction | Entry Level | Target | Stop | Outcome | Correct? | Notes |
|---|---|---|---|---|---|---|---|---|---|

Every directional stance from the Deployment Trigger Sheet (Almost deployable / Blocked / Do not touch) becomes a logged prediction the moment it is made. Every time a name's status changes, the prior call gets an outcome. Review quarterly.

---

### 6. No Regime-Fit Scoring Matrix

Priority rankings in the vault are narrative. ETN is Tier 1 because the prose says it is. The reason ETN outranks NVDA this week is distributed across three different files in different language.

A decision-grade OS should produce a scored, sortable ranking. The 5-gate framework already defines the right dimensions. Wire it to numbers.

**Fix:** Create `02. Markets/Regime Scoring Matrix.md`. One row per tracked name, five columns:

| Ticker | Regime Fit (1-5) | Technical Posture (1-5) | Catalyst Risk (1-5) | Fundamental Conviction (1-5) | Total | Stance |

Regime Fit: does this name outperform in the current regime (late-cycle, restrictive, selective risk-on)?
Technical Posture: is price at or near entry band with constructive MA structure?
Catalyst Risk: how much binary event risk exists in the next 30 days?
Fundamental Conviction: how durable is the earnings / thesis quality?

Lower catalyst risk = higher score (no surprise is better than a big one pending).

Total score drives the ranking. Ties are broken by Fundamental Conviction. This replaces five narrative ranking lists with one scored table that updates when the inputs update.

---

## Efficiency Problems (Fix These Next)

### 7. Coverage Universe Is Bloated With Uncommitted Names

The Coverage Universe has 37 tickers. Of those, approximately 15 are in "Research needed" status with no research path, no thesis development, and no near-term action condition. They are roster padding.

Names like ET, WMB, MPLX, LDOS, BAH, SAIC, EQIX, ASML, AMAT, LRCX, SHY, TIP, BTC, and HYG have been sitting in "research needed" or "monitor only" status since the vault was built. None of them have a defined path to the active portfolio.

A 37-name universe for a $5k-$10k portfolio is not rigorous — it is wishful. The attention and maintenance cost of tracking 37 names means each name gets less scrutiny than a focused 12-15 name universe.

**Fix:** Prune to an active universe of 12-15 names. The remaining names move to a "Watch Pool" section in Coverage Universe (or a separate `04. Research/Watch Pool.md`) with a single line per name and a clear elevation condition. No full thesis entry required until they earn a promotion.

Current active universe should be:
- Core candidates: MSFT, GOOG, NVDA, ETN, JPM, XOM, LMT, BRK.B
- Tactical: AMZN, VRT, RTX, NVDA, GS, LNG, AMD
- Speculative: KTOS, SLV, TLT (if kept)

Everything else moves to the Watch Pool until there is a reason to promote it.

---

### 8. Post-Earnings Closure Is Incomplete

Four names have reported since the last full vault sync:
- JPM (April 14): Interpreted, partially synced
- RTX (April 21): Beat noted, no structured post-earnings record
- VRT (April 22): Beat noted, no structured post-earnings record
- LMT (April 23): Reported, explicitly "evidence pending" across multiple files

The vault acknowledges this lag. The Apr 24 Daily Executive Summary says "the note layer has not fully absorbed the report yet" for LMT and VRT. That is an honest statement. It is also an operational gap that has persisted for 3 days.

**Fix:** Create a standard Post-Earnings Scorecard template in `05. Intelligence/`. After any tracked name reports, a one-page card gets created within 24 hours:

```
# [TICKER] Q[X] [YEAR] Post-Earnings Scorecard
- Report date:
- Beat / Miss / In-line (EPS):
- Beat / Miss / In-line (Revenue):
- Key metric vs. estimate:
- Guidance change:
- Management tone:
- Sector read-through:
- Updated action stance:
- Updated entry band (if changed):
- Closure state: Reported → Interpreted → Synced
```

This replaces scattered inline commentary in the Weekly Intelligence Brief, Watchlist, Technical Sheet, and Portfolio Snapshot with a single durable record per earnings event.

---

### 9. 06. Playbooks Is a Deliverables Graveyard

The current contents of 06. Playbooks:
- `Operating Model.md` — this belongs here
- `Weekly Review Process.md` — this belongs here
- `ETN Deck - 2026-04-24.pptx`
- `ETN PDF Brief - 2026-04-24.pdf`
- `ETN Visual Report - 2026-04-24.docx`
- `RTX Analysis - 2026-04-24.docx`
- `RTX Deck - 2026-04-24 polished.pptx`
- `RTX Deck - 2026-04-24.pptx`
- `RTX PDF Brief - 2026-04-24.pdf`
- `RTX Visual Report - AXIOM Pass.docx`
- `RTX Visual Report - Reusable Template Test.docx`

Nine dated deliverable artifacts are cohabiting with two operating documents. These research reports are outputs, not playbooks. They belong in `09. Archive/06. Research Deliverables/` or a new `05. Intelligence/Equity Reports/` subfolder.

**Fix:** Move all dated report artifacts to archive. The Playbooks folder should contain only operating procedures and protocol documents.

---

### 10. 08. Audits Has 11 Files, Most Resolved or Superseded

Audit files in the folder:
- `2026-04-22-dashboard-command-center-audit.md`
- `Auth Readiness Audit.md`
- `Capability Matrix.md`
- `Command Center Audit - 2026-04-25.md` ← most recent, current
- `Content Model Trend Scan - 2026-04-11.md` ← content pivot era, irrelevant
- `Dashboard Hardening Implementation Plan - 2026-04-22.md`
- `Independent Operations Review - 2026-04-07.md` ← early system setup, superseded
- `Operational Readiness Sprint - 2026-04-23.md`
- `Weekly Workspace Audit - 2026-04-20.md`
- `Workspace Audit - 2026-04-22.md`
- `Workspace Hardening Post-Sprint Summary - 2026-04-23.md`
- `Workspace Hardening Sprint - 2026-04-23.md`
- `Workspace Organization Audit - 2026-04-09.md`
- `Workspace Tightening Plan - 2026-04-22.md`
- `Workspace and Vault Health Audit - 2026-04-10.md`

The Content Model Trend Scan is from the content-pivot era — a prior version of this workspace. The Independent Operations Review and Workspace Organization Audit from early April are entirely superseded. The Dashboard Hardening files were implementation artifacts, not standing operating documents.

**Fix:** Archive everything pre-April-23. Keep only the two most recent audits as active documents. Audit files that close with a completed implementation should be archived the moment the implementation is done — not left in the active folder as resolved items.

---

### 11. FINANCE_SOUL.MD Referenced in CLAUDE.md Does Not Exist

CLAUDE.md, under "Investment Advisory Posture," states:

> "Use the FINANCE_SOUL.MD prediction analysis protocol when making directional calls"

There is no `FINANCE_SOUL.MD` file in the vault. This reference is broken. Either the file was never built, was archived, or was renamed. As a result, every session that references this protocol is referencing a ghost document.

**Fix:** Either build the file or remove the reference. If the prediction analysis protocol is meant to be a structured decision-making framework for directional calls, it should exist as a real document. If it was superseded by the 5-gate deployment framework and FINANCE_SOUL.MD was meant to be something more, define it and build it.

---

## Precision and Analytical Gaps (Longer-Term)

### 12. No Regime-Change Protocol

The vault defines the current regime well. It does not define what happens when the regime changes.

Specifically, there is no documented procedure for:
- What constitutes a regime shift (e.g., unemployment breaks above 5%, 10Y Treasury spikes above 5%, credit spreads widen 150+ bps)
- Which files must be updated, in what order
- What happens to active positions when the regime shifts (all re-reviewed? Tier 3 names automatically benched?)
- Who triggers the reassessment (Veritas on script signals, Claude on qualitative read, or manual)

The current system handles regime continuity well. It handles regime change ad hoc.

**Fix:** Add a `07. Risk/Regime Change Protocol.md` file. Define three regime states (current, transition, broken) with specific quantitative thresholds for each, a mandatory file-update sequence when a shift is triggered, and a default portfolio action (reduce risk, increase cash, review each name against new regime).

---

### 13. No Sector Allocation Tracking

Risk Rules define:
- Max single sector: 25% to 35%
- Tier 1: 8%-12%, Tier 2: 4%-7%, Tier 3: 1%-3%

The current model portfolio draft (from Portfolio Snapshot) has:
- Technology (MSFT 12% + GOOG 12% + ETN 7% + NVDA 6%) = ~37% in tech/industrial-AI
- Energy (XOM 8%) = 8%
- Defense (LMT 8%) = 8%
- Financial (JPM 12%) = 12%
- Diversified (BRK.B 10%) = 10%
- Speculative (KTOS 2% + SLV 3%) = 5%
- Cash: 20%

The Technology/AI-infrastructure cluster is already at or above the 35% sector cap if ETN and NVDA are included with MSFT and GOOG. This concentration risk is not currently tracked anywhere in the vault. It only becomes visible when you manually sum the Portfolio Snapshot.

**Fix:** Add a sector allocation summary table to Portfolio Snapshot that shows current weight by sector versus the Risk Rules max. This should auto-flag when any sector is within 5% of its cap. It does not need a script — a manually maintained table in Portfolio Snapshot is sufficient.

---

### 14. The Macro Dashboard Data Is 6 Days Old Heading Into FOMC

The Macro Regime Dashboard was last updated April 20. Today is April 26. The FOMC decision is April 29 — three days away.

The vault's own staleness protocol says: "Data older than 7 days should be flagged in market and macro files." The dashboard is at 6 days, inside the technical threshold. But entering the most catalyst-dense week of the quarter with a macro dashboard from 6 days ago — before the FOMC setup was fully priced, before VRT and LMT reported, and before the latest market structure — is not sufficient precision.

The dashboard needs a refresh before April 28. Specifically:
- Current 2Y, 10Y, and 2s10s levels (the Apr 20 print is pre-FOMC pricing)
- Current VIX context (18.82 Apr 24 vs. 17.48 Apr 17 — fear is slightly elevated)
- Updated Fed posture language reflecting current cut probability repricing
- Updated oil posture given the continued post-ceasefire structure at Brent ~$88-90

---

### 15. Technical Entry Sheet Lacks Price History Context

The Technical Entry Sheet has precise current-state data per name: close, MAs, support, resistance, entry band, stance. What it does not have is any historical context for whether those entry bands have been tested, whether support levels held on prior touches, or how many days a name has been extended above its band.

This matters for deployment discipline. ETN has been above its 388-396 entry band for at least 10 trading days based on the price trajectory described in the vault. The sheet says "extended 7.3% above band" but does not record how long it has been extended or how it behaved the last time it was in the band.

**Fix:** Add a "Recent history" row per name with a two-line note on: (1) the last time price was in or near the entry band and what happened, and (2) the number of trading days the name has been at the current stance. This is manual maintenance but it takes 30 seconds per name per week.

---

## Recommended Priority Sequence

### This Week (before April 29 FOMC cluster)
1. Fix the partial-data problems: 2Y Treasury retry endpoint, FedWatch wire, earnings date confirmations for ETN/NVDA/BRK.B resolved once in Event Calendar
2. Refresh Macro Regime Dashboard with current rates, oil, and VIX context
3. Fill the Weekly Positioning Review for the week of April 27
4. Create LMT and VRT post-earnings scorecards (they have been "evidence pending" for 3+ days)

### This Month (before May earnings cluster)
5. Retire the Watchlist as a standalone canonical file — migrate its unique content to Coverage Universe and Deployment Trigger Sheet
6. Create the Call Log in `04. Research/Call Log.md` — backfill current active stances as starting entries
7. Create the Regime Scoring Matrix in `02. Markets/Regime Scoring Matrix.md`
8. Move 06. Playbooks deliverable artifacts to archive
9. Archive pre-April-23 audit files
10. Add sector allocation tracking table to Portfolio Snapshot
11. Resolve or create FINANCE_SOUL.MD

### Next Quarter (structural precision upgrades)
12. Prune Coverage Universe to 12-15 active names; move remainder to Watch Pool
13. Build `07. Risk/Regime Change Protocol.md`
14. Add post-earnings scorecard as a required output for all tracked names
15. Add price history context to Technical Entry Sheet
16. Build a `run_finance_refresh_chain.py sunday` operating window for Weekly Positioning Review skeleton generation

---

## Net Assessment

The vault is not broken. It is operational. The scripts are mature, the decision logic is correct, and the source-of-truth hierarchy is well-enforced in the note layer. The Daily Executive Summaries are probably the best single-session execution document in the system.

The problem is accumulated maintenance drag. A system that was built iteratively now has 4-5 places that say the same thing at the same level of detail, a never-filled synthesis layer, a broken reference to a missing document, and no mechanism to know whether its own calls were right.

The path to a genuinely autonomous decision-grade OS requires closing those gaps — specifically the Watchlist redundancy, the prediction tracking absence, the regime-fit scoring gap, and the partial-data tolerance. None of these are hard to fix individually. They are hard to fix collectively only if they are not prioritized.

The system as built can support excellent investment decisions. It cannot yet evaluate whether it is actually making them.

---

*Audit conducted by Claude — April 26, 2026*
*Authority: Claude.md — Section: Workspace Enhancement Layer, Audit Layer, Truth and Proof Layer*
*Next audit recommended: May 15, 2026 (after the April-May earnings cluster closes)*
