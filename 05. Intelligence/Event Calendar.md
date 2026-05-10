# Event Calendar

## Purpose

Track known market-moving events. Use this before every session to orient around upcoming catalysts.

Script-backed prep path:
- run `python scripts/run_finance_refresh_chain.py post-close` after the close to refresh the earnings-date layer before trigger logic and stage post-earnings follow-up artifacts for the next session
- run `python scripts/run_finance_refresh_chain.py post-earnings` after a material report lands when the close-level board already exists and the main need is closure-state follow-up
- run `python scripts/run_finance_refresh_chain.py morning` for next-session readiness when the goal is to read the board, not rebuild every event-driven artifact
- use `tmp/earnings-calendar.json` to confirm new dates or date changes, but do not blindly trust a single source for critical catalysts

Color coding (text labels):
- **[CRITICAL]** — direct portfolio impact, binary outcome, requires a pre-event decision
- **[HIGH]** — significant macro or sector signal
- **[MONITOR]** — useful context, not requiring pre-event action

## Freshness and refresh policy

- Last updated: 2026-05-05
- Data as of: targeted May 5 ETN / AMD / SMCI post-earnings interpretation plus current machine evidence through the 2026-05-05 close
- Refresh cadence: weekly, after major portfolio-company earnings, and whenever a dated catalyst elapses or a new confirmed event is added
- Next refresh due: after Eaton primary-source follow-up is captured, after SMCI primary-source follow-up is captured, and no later than the NVDA timing-confirmation deadline on **2026-05-13** if a cleaner primary confirmation path still has not landed.
- Refresh policy: remove elapsed one-time events from live month sections once they have reported, keep recurring events intact, promote newly confirmed items from the standing watch list, and preserve only the next relevant rolling window of dated catalysts. For material earnings, pair calendar maintenance with the post-earnings closure workflow: move the name from upcoming to **Reported, evidence pending**, **Interpreted**, **Synced**, or **Closed with follow-up** instead of leaving a stale upcoming line behind. Treat script-surfaced date changes as usable evidence, but cross-check critical portfolio-company dates before relying on them blindly.

## Timing-critical governance

- If `tmp/earnings-calendar.json` raises a `DATE CHANGED` alert for a portfolio name or top watchlist name, treat the date as **unconfirmed timing risk** until it is verified against company IR, an earnings release, or another clearly labeled primary source.
- Current unresolved manual timing dependencies are now narrower. **NVDA** still lacks a clean direct confirmation path for the likely **May 20** date, and any provider-only next-quarter dates for recently reported names should stay labeled as estimates rather than silently normalized into primary-confirmed canon.
- Close rule for **NVDA**: if a clean primary confirmation still does not exist by the first post-close chain on **2026-05-13** (7 calendar days ahead of the likely print), keep the note-layer date explicitly tagged **unconfirmed**, keep deployment trust capped at the current caution posture, and do not let downstream notes speak as if the date were primary-confirmed.
- The operating-window chains now end with `python scripts/validate_dashboard_state.py --write`; keep that validator as the final trust gate after material calendar updates so the dashboard trust panel and contradiction warnings stay aligned with the note layer.
- Macro/policy caveats matter too, but they should stay specific: the live policy artifact is now primary-sourced, while the remaining caution is the simplified probability model and any future source degradation.

## Post-earnings closure visibility rule

For each material tracked earnings event, this note should make the current closure state visible.

Use these labels:
- **Prepared** — pre-event packet and blocker posture are in place
- **Reported, evidence pending** — event happened, but interpretation is not complete yet
- **Interpreted** — the note layer contains a concise what happened / what it means / what we do now line
- **Synced** — required note targets were selectively updated and this calendar no longer treats the event as still upcoming
- **Closed with follow-up** — the report is processed, but a real next dependency remains explicit

Minimum rule:
- material tracked earnings must not stop at a bare reported marker
- once reported, the entry must either show a decision line or explicitly say evidence / interpretation is still pending
- once synced, clear the stale upcoming framing and either preserve the concise post-earnings implication here or roll the catalyst forward properly
- event-calendar maintenance is part of the closure process adopted in Phase 1, not a separate optional cleanup pass

## Recurring weekly events

| Day | Event | Time (ET) | Notes |
|---|---|---|---|
| Wednesday | EIA Weekly Petroleum Status Report | 10:30 AM | Crude/distillate/gasoline inventories plus refinery utilization. For weekly maintenance, capture actual vs prior vs consensus when available. Key for XOM thesis and energy read. |
| Friday | Baker Hughes Rig Count | 1:00 PM | US oil and gas rig activity. Lagging indicator but useful for supply-side read. |

---

## April 2026

| Date | Day | Event | Priority | Notes |
|---|---|---|---|---|
| Apr 28 | Tue | FOMC Meeting begins (Day 1 of 2) | **[HIGH]** | No cut expected. Rate held at 3.5%–3.75%. Watch Powell's tone on inflation persistence and rate path. |
| Apr 29 | Wed | **FOMC Rate Decision + Powell Press Conference** | **[CRITICAL]** | Decision 2:00 PM ET. Press conference follows. Market at all-time highs — hawkish surprise from this level would hit hard. |
| Apr 29 | Wed | **MSFT Q3 FY2026 Earnings — Reported / Synced** | **[CRITICAL]** | Report date directly confirmed via Microsoft 8-K dated Apr 29. Strong quarter led by Azure +40% and a $37B AI revenue run rate, but the stock remains below the 200-day and still needs pullback / repair. Closure state: **Closed with follow-up**. |
| Apr 29 | Wed | **GOOG Q1 2026 Earnings — Reported / Synced** | **[CRITICAL]** | Report date directly confirmed via Alphabet 8-K dated Apr 29. Search stayed strong and Google Cloud accelerated to +63%, but the stock is now extended above the written band. Closure state: **Closed with follow-up**. |
| Apr 29 | Wed | **META Q1 2026 Earnings — After close** | **[HIGH]** | Not in portfolio but major market signal. Ad market health and AI capex commentary directly relevant to MSFT/GOOG read. |
| Apr 29 | Wed | **AMZN Q1 2026 Earnings — After close** | **[HIGH]** | Watchlist name (secondary bench). AWS growth and operating leverage are the key variables. Strong beat could justify upgrading to portfolio candidate. |
| Apr 29 | Wed | **EQIX Earnings** | **[MONITOR]** | Data-center and digital infrastructure read-through relevant to AI-capex and power-demand framing. |
| Apr 30 | Thu | **Q1 2026 GDP Advance Estimate** | **[CRITICAL]** | 8:30 AM ET. First read on Q1 growth. If materially below expectations, regime reassessment required. The Hormuz shock hit in March — this number will partially reflect it. |
| Apr 30 | Thu | **ETN Q1 2026 Earnings — earlier cross-check no longer primary** | **[MONITOR]** | Earlier cross-check work had pointed to Apr 30, but that window has now passed and the live script layer still shows **May 5**. Do not keep treating Apr 30 to May 5 as an active mismatch window; carry forward May 5 as the current working date unless cleaner primary confirmation appears. |
| Apr 30 | Thu | **COP Earnings** | **[MONITOR]** | Energy read-through ahead of XOM. Helpful for commodity and upstream tone. |
| Apr 30 | Thu | **AAPL Q2 FY2026 Earnings — After close** | **[HIGH]** | Not in portfolio. Consumer demand proxy, services growth, and any AI monetization commentary. |

---

## May 2026

| Date | Day | Event | Priority | Notes |
|---|---|---|---|---|
| May 1 | Fri | **XOM Q1 2026 Earnings — Reported / Interpreted** | **[CRITICAL]** | Report landed. Underlying quarter was stronger than the GAAP headline, but XOM stays benched until the next one to two EIA reads plus Hormuz / Qatar LNG follow-through clarify whether the setup can reclaim the 50-day cleanly. Closure state: **Closed with follow-up**. |
| May 1 | Fri | **CVX Earnings** | **[MONITOR]** | Additional oil-major read-through on pricing, buybacks, and downstream tone. Useful context for XOM. |
| May 2 | Sat | **BRK.B Q1 2026 Earnings — Reported, evidence pending** | **[HIGH]** | Berkshire's official homepage now shows **Annual & Interim Reports** and **News Releases** updated **May 2, 2026**, which is strong homepage-level confirmation that the old May 4 vault date was stale. The report itself is no longer a timing mismatch, but the machine layer has not yet rolled to a next-quarter date. Do **not** keep treating **May 2** as a fresh upcoming catalyst once this post-earnings cleanup is complete. Watch: portfolio composition changes, cash deployment, and Buffett macro commentary. |
| May 4 | Mon | **PLTR Earnings** | **[MONITOR]** | Newly confirmed again in the refreshed script pass. Useful for software, government, and defense-tech demand tone. |
| May 4 | Mon | Baker Hughes Rig Count carryover / weekly positioning review | [MONITOR] | Use the post-April earnings cluster to reassess energy and industrial positioning. |
| May 5 | Tue | **ETN Q1 2026 Earnings — Reported / Interpreted** | **[CRITICAL]** | Secondary-source scorecard written after direct Eaton primary fetch did not produce a clean release. Evidence indicates a beat, revenue upside, and raised guidance, but guidance/reaction nuance keeps ETN **almost deployable**, not promoted. Closure state: **Closed with follow-up**. |
| May 5 | Tue | **AMD Q1 2026 Earnings — Reported / Interpreted** | **[HIGH]** | Primary-source scorecard written. AMD reported $10.253B revenue (+38% YoY), non-GAAP EPS $1.37, and Data Center revenue $5.8B (+57% YoY). Constructive AI infrastructure read-through, but no standalone portfolio deployment trigger. Closure state: **Closed with follow-up**. |
| May 5 | Tue | **SMCI Q3 2026 Earnings — Reported / Interpreted** | **[MONITOR]** | Secondary-source scorecard written after IR fetch was blocked. Evidence indicates an EPS beat and constructive forward AI-server demand signal, but primary-source details remain follow-up. Closure state: **Closed with follow-up**. |
| May 6 | Wed | EIA Weekly Petroleum Status | [MONITOR] | Second post-ceasefire read. Supply normalization trend will be clearer by this point, and it should be used explicitly to decide whether XOM stays benched or can begin requalification work. |
| May 8 | Fri | **April 2026 NFP / Jobs Report** | **[HIGH]** | 8:30 AM ET. Watch: payrolls, unemployment rate (currently 4.3%). Continued softening vs. sharp break is the key distinction. Sharp break = regime change signal. |
| May 12 | Tue | **April 2026 CPI Release** | **[CRITICAL]** | 8:30 AM ET. First major inflation print post-Hormuz ceasefire. Energy component will be the swing factor — oil crashed in mid-April. Watch core vs. headline divergence. Fed watching this closely before any rate path repricing. |
| May 13 | Wed | **April 2026 PPI Release** | **[HIGH]** | 8:30 AM ET. Producer-side inflation read. Energy price collapse should show up here first. |
| May 13 | Wed | **NVDA timing-confirmation deadline** | **[HIGH]** | By the first post-close chain on this date, either land a cleaner primary confirmation path for the likely May 20 print or keep the note layer explicitly tagged unconfirmed and capped at the current caution posture. |
| May 20 | Wed | **NVDA Q1 FY2027 Earnings — After close?** | **[CRITICAL]** | The best currently accessible evidence still points to **May 20** rather than the old May 27 vault date, but this pass still did **not** produce a clean primary confirmation because NVIDIA IR fetch remains blocked and SEC review did not surface an earnings-announcement filing. Keep this as an unconfirmed likely date change. Watch: Blackwell demand, data center revenue, forward guidance. Single most important earnings call for the AI infrastructure thesis. |
| May 28 | Thu | **March 2026 PCE / Personal Income and Outlays** | **[HIGH]** | 8:30 AM ET. Fed's preferred inflation gauge. Core PCE last read was 3.0% YoY. Any movement toward or away from 2% target is a rate path signal. |

---

## June 2026

| Date | Day | Event | Priority | Notes |
|---|---|---|---|---|
| Jun 7 | Sun | **OPEC+ 41st Ministerial Meeting** | **[CRITICAL]** | Major production decision. ~3.24M bpd of cuts still in place. Post-ceasefire oil crash + Hormuz reopening creates pressure to reassess production levels. Decision will reset the oil price structure for Q3. Direct read on XOM thesis. |
| Jun 16–17 | Tue–Wed | **FOMC Meeting** | **[HIGH]** | Second meeting of the year after the April hold. June meetings include the dot plot / economic projections update. If data between now and June softens materially, this is the first live cut meeting. |

---

## Standing watch list (no date yet — add when confirmed)

| Event | Notes |
|---|---|
| May FOMC minutes release | ~3 weeks after April 28–29 meeting |
| Q1 2026 GDP second estimate | ~4 weeks after advance estimate (late May) |
| April 2026 PCE release | Late May — confirm exact date |
| Baker Hughes OPEC+ compliance report | Monthly, track alongside rig count |

---

## Recurring events to monitor

| Event | Frequency | Source | Notes |
|---|---|---|---|
| EIA Weekly Petroleum Status | Every Wednesday, 10:30 AM ET | eia.gov | Crude, distillate, gasoline, refinery utilization |
| Baker Hughes Rig Count | Every Friday, 1:00 PM ET | bakerhughes.com | US oil/gas rig activity |
| Fed Funds Futures | Daily | CME FedWatch | Rate cut probability tracker |
| CPI | Monthly, ~10th–15th of following month | bls.gov | 8:30 AM ET |
| PPI | Monthly, ~11th–16th of following month | bls.gov | 8:30 AM ET |
| PCE / Personal Income & Outlays | Monthly, last week of following month | bea.gov | 8:30 AM ET — Fed's preferred inflation gauge |
| Nonfarm Payrolls | First Friday of each month | bls.gov | 8:30 AM ET |
| FOMC Meetings | 8 times per year | federalreserve.gov | 2026 remaining: Apr 28–29, Jun 16–17, Jul 28–29, Sep 15–16, Oct 27–28, Dec 8–9 |
| OPEC+ Meetings | Variable | opec.org | Next: June 7, 2026 |

---

## Last updated

- 2026-04-19 — initial population by Claude. Data sourced from BLS, BEA, Federal Reserve, company investor relations pages, and confirmed market data services.
- 2026-04-20 — reconciled against `tmp/earnings-calendar.json`. Promoted RTX, NOC, PLTR, and SMCI into dated sections. Flagged likely date changes for ETN, NVDA, and BRK.B from the script-assisted cross-check, with explicit caution to confirm against company IR before relying on exact timing.
- 2026-04-20 (later) — attempted direct confirmation pass for ETN, BRK.B, and NVDA. Result: no clean direct-confirmation win from fetched IR pages, so those three remain flagged as likely but unconfirmed date changes rather than treated as fully confirmed calendar truth.
- 2026-04-21 — marked RTX as reported after a beat and raised full-year outlook, preserving it as a positive defense read-through ahead of LMT.
- 2026-04-22 — tightened workflow notes so NOC and RTX explicitly feed the LMT review path, ETN is treated as a live Apr 30 to May 5 date-mismatch window, and EIA updates are linked directly to the XOM under-review decision.
- 2026-04-22 (later) — marked VRT as reported after a beat and raised full-year guidance, with explicit positive read-through for AI power demand and a still-disciplined no-chase implication.
- 2026-04-24 — cleared stale next-refresh language after the LMT event, converted LMT from upcoming to reported-evidence-pending status, and made post-earnings closure-state maintenance explicit so elapsed catalysts do not linger as still upcoming.
- 2026-04-24 (post-earnings refresh, 13:49 UTC) — reran the finance refresh chain in `post-earnings` mode and kept the calendar focused on the current rolling window. GOOG, MSFT, XOM, ETN, VRT, and AMZN remain the active Event Calendar note targets. No new critical portfolio-company dates were blindly changed because dashboard validation still flags timing-sensitive earnings-date warnings, including LMT now rolling to Jul 21 in the script layer plus unresolved NVDA and BRK.B date-shift caution. ETN remains explicitly treated as an Apr 30 to May 5 timing-sensitive window pending direct confirmation.
- 2026-04-29 (heartbeat cleanup, 13:52 UTC) — removed elapsed Apr 21 to Apr 25 one-time items from the live April section and advanced the note into the active Apr 29 to May 5 catalyst window without claiming a fresh script rerun.
- 2026-05-02 — marked XOM as reported / interpreted, rolled the event out of stale upcoming framing, and kept the follow-up dependency explicit instead of pretending the name was requalified.
- 2026-05-02 (later) — directly confirmed the GOOG and MSFT report dates via their Apr 29 SEC 8-Ks, updated both names to reported / synced, and upgraded BRK.B timing from "likely May 2" to homepage-level confirmed May 2. NVDA remains the main unresolved timing-sensitive date.
- 2026-05-02 (QC follow-up) — made the BRK.B post-report state explicit as **Reported, evidence pending** and added a hard close rule for the still-unconfirmed NVDA May 20 timing path. Workflow 9 should not inherit BRK.B's stale machine-layer May 2 next-date without an explicit cleanup decision.
- 2026-05-03 (post-close run) — post-close chain ran clean (0/0 validation, 17/17 acceptance). BRK.B remains **Reported, evidence pending**; no scorecard completion captured yet. NVDA May 20 timing path remains unconfirmed. ETN earnings on May 5 are the live critical catalyst.
- 2026-05-05 — post-earnings interpretation pass written for ETN, AMD, and SMCI. AMD is primary-source confirmed and constructive for AI infrastructure demand. ETN and SMCI are interpreted from secondary evidence because direct primary fetches were blocked / incomplete; both are **Closed with follow-up**, not deployable-now promotion evidence. At that point the deployment surface was still in its pre-approval posture; owner-layer status changed on 2026-05-07 when JPM moved to explicit deployable-now approval.
- Next review: capture Eaton and SMCI primary-source releases/transcripts when accessible, complete BRK.B scorecard cleanup, and re-check NVDA timing no later than the first post-close chain on 2026-05-13.
