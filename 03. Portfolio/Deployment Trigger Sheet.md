# Deployment Trigger Sheet

## Purpose

This file bridges the gap between research and action.

Use it to decide when a name is actually deployable, not just interesting.

Role in the stack:
- this is the canonical deployment-decision note
- it owns deployable, almost deployable, blocked, and do-not-touch states
- it owns entry bands, invalidation, and gate-based justification
- it does not replace the weekly operating map or the portfolio-allocation note

A position becomes justifiable only when the required gates line up.

Version 1 operating model:
- scripts generate hard data and machine-readable action buckets in `tmp/trigger-sheet.json`
- this note remains the human decision layer that interprets those inputs and states the actual recommendation
- when the machine output and the note disagree, explain why rather than pretending the difference does not exist

## Deployment gates

Every serious candidate must pass these five gates before action:

1. **Thesis gate**
   - Thesis remains intact.
   - No material earnings, macro, sector, or company-specific degradation.
2. **Macro and regime gate**
   - Current regime still supports the name and sector.
   - Do not force a trade that fights the macro tape.
3. **Technical gate**
   - Price is in or near the preferred zone, or structure confirmed without obvious chase risk.
   - Support and invalidation are defined.
4. **Catalyst gate**
   - No avoidable binary event is too close unless the plan is explicitly event-driven.
   - Pre-earnings caution blocks normal entries.
5. **Risk and sizing gate**
   - Position size fits `07. Risk/Risk Rules.md`.
   - Stop or invalidation is explicit.
   - Reward-to-risk and opportunity cost are acceptable.

If one gate fails, the name is not deployable yet.

## Action states

- **Deployable now** — all five gates pass and entry is justified now.
- **Almost deployable** — thesis is intact, but one blocking condition remains.
- **Blocked** — a real catalyst, structure, or regime issue prevents action.
- **Do not touch** — risk, structure, or uncertainty is too poor for justified deployment.

## Current deployment board

| Ticker | Thesis status | Macro fit | Technical trigger | Catalyst blocker | Invalidation | Size tier | Action state | Why |
|---|---|---|---|---|---|---|---|---|
| ETN | Intact | Strong fit with AI power, electrification, and industrial capex | Pullback into **388 to 396** with support holding, or disciplined continuation that does not become a chase | **May 5 earnings in 3d — treat as timing-sensitive even though the setup is structurally strong** | Lose **383.23** or break the recent structure | Tier 2 | **Almost deployable** | Best chart in the sheet, but current price is extended versus the preferred zone |
| JPM | Intact | Good fit in selective risk-on with stable credit and curve backdrop | **In band at 306.82 to 318.12** while holding the 200-day and higher-low structure; cleaner adds still favor pullbacks toward **300 to 306** | No immediate earnings blocker | Lose **301.17** and the 200-day/higher-low structure | Tier 1 | **Deployable now** | Close **312.47** is inside the refreshed band. High-quality setup, but normal size discipline still applies. |
| GOOG | Intact | Good fit for quality large-cap exposure | Pullback into **330.01 to 349.37** with the post-print structure holding; no chase after the ~10% earnings gap | No near-term event block. The Apr 29 report is now explicitly reviewed; next earnings **Jul 23** is still a provider estimate, not primary-confirmed canon. | Lose **320.33** or fail the post-print breakout shelf | Tier 1 | **Almost deployable** | Earnings review is now complete and the thesis is confirmed, but price is still too extended above the written band to justify a fresh add. |
| MSFT | Intact | Good fit for quality AI platform exposure | Pullback into **389.64 to 412.56** with support holding, or stronger repair that can reclaim the 200-day cleanly | No near-term event block. The Apr 29 report is now explicitly reviewed; next earnings **Jul 29** is still a provider estimate, not primary-confirmed canon. The live issue is technical repair, not unresolved earnings. | Lose **378.18** or fail the recovery structure | Tier 1 | **Almost deployable** | Azure and AI monetization confirmed the thesis, but price is still only slightly above band and the stock remains below the 200-day. Better than blocked, still not clean enough to force. |
| LMT | Intact but event-sensitive | Defense fit remains valid | No trigger until after a fresh post-event base forms | **Post-earnings repair mode**. Old setup already failed before the print, so the name stays blocked until a new structure exists | Lose **581.50** or fail to rebuild support after earnings | Tier 1 only after repair | **Do not touch** | The old setup is invalidated and the post-earnings interpretation is still a repair workflow, not an immediate re-entry case |
| BRK.B | Intact | Good fit for ballast in mixed regime | In band near **465 to 472**, but only actionable on clear repair through **481+** | **Reported May 2. The old May 4 timing mismatch is closed for the print itself, but the machine layer has not yet rolled to a next-quarter date; do not keep treating May 2 as a fresh upcoming catalyst.** | Lose **459.50** or continue to fail all major MAs | Tier 1 | **Do not touch** | Price is in band, but structure is still weak enough to keep it on the bench. The report does not override the bench state; it only moves the issue from timing to interpretation. |
| XOM | Intact long-term, weaker near-term | Mixed: stronger oil helps, but Hormuz / shipping / LNG disruption risk still muddies the read | In band at **150.24 to 158.44**, but only actionable if price can hold the band and reclaim the 50-day with supportive energy context | **Reported May 1. Underlying quarter was stronger than the GAAP headline, but keep it benched until the next one to two EIA reads plus Hormuz / Qatar LNG follow-through clarify production risk.** | Lose **146.14** or fail another 50-day reclaim attempt | Tier 1 | **Do not touch** | The report improved thesis confidence, not deployment readiness. Price is in band, but the workflow still belongs on the bench until follow-through is cleaner. |
| NVDA | Intact but crowded | AI regime fit remains strong | **In band at 188.03 to 199.28**; only actionable with disciplined size and no breakout chasing | No immediate earnings blocker, but the machine layer now points to **May 20** rather than the old **May 27** vault date; re-check NVIDIA IR no later than the first post-close chain on **2026-05-13** and keep the date explicitly unconfirmed unless a cleaner primary path lands | Lose **182.40** and the MA cluster | Tier 2 | **Deployable now** | Close **198.45** is inside the band, but crowding risk keeps this a disciplined tactical setup, not a free pass. |
| VRT | Intact but more crowded than ETN | Good thematic fit | Pullback into the **295.49 to 326.63** working band with support holding; still secondary to ETN unless the setup improves further | No immediate hard block | Lose **279.92** or break the trend structure after the current post-earnings run | Tier 2 | **Watch / research needed** | Levels now exist, but ETN remains the primary AI-power execution name and VRT is still only marginally above band |
| GS | Intact but secondary to JPM for primary bank exposure | Useful capital-markets-sensitive financial for tactical board coverage | **In band at 878.71 to 926.76**, but only as a tactical add with disciplined size while JPM remains the primary bank setup | No immediate hard block | Lose **854.68** or fail the uptrend after the current in-band test | Tier 2 | **Deployable now** | The setup is now decision-grade and in band, but it still ranks behind JPM and does not justify aggressive promotion or chase behavior. |

## Current priority order

### Deployable now
1. **JPM** — in band, cleaner quality setup
2. **NVDA** — in band, but crowded and still Tier 2
3. **GS** — in band and now decision-grade, but still secondary to JPM for primary bank exposure

### Post-earnings follow-through — not deployable yet
1. **GOOG** — scorecard complete; strong report, but still extended above the post-print band
2. **MSFT** — scorecard complete; thesis confirmed, but the stock is still below the 200-day and only marginally above band

### Almost deployable
1. **ETN** — best pullback-only chart, but May 5 earnings caps pre-print aggression

### Watch — setup still undefined
1. **VRT** — thematic fit is real, but ETN remains the primary AI-power execution name

### Bench, blocked, or invalidated
1. **LMT** — repair mode
2. **BRK.B** — chart weak
3. **XOM** — interpreted, but still benched pending post-print follow-through

## Pull-the-trigger rule

A position is justifiable only when:
- the thesis is intact,
- the macro regime still supports it,
- the chart is at or near the intended trigger,
- no avoidable binary catalyst is too close,
- and the size fits the written risk rules.

Liking the company is not enough.
A good earnings report alone is not enough.
A spot on the watchlist is not enough.

## Current recommendation

- **Best live high-quality candidate:** JPM.
- **Best live tactical candidate:** NVDA.
- **Best near-deployable candidate:** ETN on pullback only (near-earnings caution — May 5).
- **Post-earnings follow-through — not deployable yet:** GOOG (scorecard complete; still extended above band), MSFT (scorecard complete; still needs either a pullback into band or cleaner 200-day repair).
- **Additional deployable-now name, but still subordinate to a stronger peer:** GS (in band and decision-grade, but still a tactical secondary versus JPM for primary bank exposure).
- **Execution-board watch, not yet deployable:** VRT (secondary AI-power name; levels exist but ETN remains first and the setup is still not decision-grade enough to force).
- **Do not treat as deployable — setup or trust issues:** BRK.B and XOM.
- **Do not touch:** LMT (repair mode).

## Freshness and update policy

- Last updated: 2026-05-02
- Data as of: 2026-05-01 close with current trigger-sheet state, XOM post-earnings sync, and the band-update follow-through that moved **JPM** and **NVDA** into live in-band status. Broader note-layer reconciliation remains selective rather than full-rewrite.
- Refresh cadence: after weekly technical refreshes, after tracked earnings, after material macro regime change, or when a name clearly changes action state
- Next refresh due: after BRK.B is interpreted and its stale machine-layer May 2 next-date is cleared or manually held, after ETN May 5 earnings print (near-earnings caution active), or when MSFT / GOOG / VRT / GS follow-on note sync changes a real action state
- Refresh policy: update action states, triggers, blockers, and size logic only when the evidence materially changes. Do not churn wording just to restate the same setup. Version 1 script output should inform this note, not overwrite judgment.

## Data-quality note

- Inputs are now expected to flow through `tmp/trigger-sheet.json`, which reads from the cached technical, deployment, macro, and earnings artifacts.
- The trigger-sheet script is intentionally read-only. It prepares action buckets, blockers, and invalidation context, but it does not replace human interpretation.
- Inputs are fresh and same-day only when the underlying `tmp/` artifacts are fresh. If freshness flags turn stale, downgrade confidence explicitly.
- The macro file still carries two warnings: the Fed target range is hardcoded as of 2026-04-19, and FedWatch cut probability is not wired.
- Dashboard validation remains **warning-level**, with timing-sensitive earnings-date changes still requiring direct confirmation.
- Treat rate and policy context as directional, not precision timing input, until those warnings are cleared.
- `AMD`, `AMZN`, `CAT`, `CVX`, `LNG`, `PLTR`, and `RTX` remain machine-tracked watch-lane names, but they are **not** part of the execution board in this note. Their current validation warnings are ownership residue, not a hidden promotion into deployable status.
- Treat **NVDA** as the main still-unresolved timing-sensitive next-earnings mismatch affecting deployment trust today, with a forced re-check due by the first post-close chain on **2026-05-13** if cleaner confirmation still has not landed. **BRK.B** timing is now homepage-level confirmed for May 2, but the machine layer still needs a post-report next-date cleanup so Workflow 9 does not inherit stale catalyst framing. XOM is no longer a "write the first interpretation" case; it is now a post-print follow-through case. GOOG and MSFT are no longer pending earnings review; they are now post-print entry-discipline cases.
- **Deployable now** means the gates line up on paper; it does **not** cancel warning-level trust, date-confirmation caution, crowding risk, or normal size discipline.
