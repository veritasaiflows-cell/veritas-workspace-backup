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
- operator cadence reference: `06. Playbooks/Deployment Readiness Morning Operating Cadence.md`

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
| ETN | Intact, with post-earnings evidence accepted enough for owner-approved conditional deployment | Strong fit with AI power, electrification, and industrial capex, but macro/trust warnings still argue against forcing size | **In band at 401.51** inside the **395.59–420.31** refreshed band; acceptable only as a disciplined lower-half-band setup, not a chase above **420.31** | **May 5 earnings reported / interpreted with follow-up** — secondary evidence constructive; owner promoted ETN on 2026-05-09 after the fresh entry-band rerun confirmed the setup remained in band | Lose **383.23** or break the 50-day / band-support cluster | Tier 2 | **Deployable now** | Owner-approved conditional add. Use Tier 2 sizing discipline, keep stop/invalidation explicit, no automatic execution, and no chase above the written band. |
| JPM | Intact | Good fit in selective risk-on with stable credit and curve backdrop | Owner-approved Tier 1 setup, but the latest machine close **302.10** is now **below** the formal **306.82–318.12** band and only modestly above the **301.17** invalidation line; require reclaim of the band or an explicit band review before treating the trigger as live again | No immediate earnings blocker | Lose **301.17** and the 200-day/higher-low structure | Tier 1 | **Almost deployable** | Explicit owner approval was granted on 2026-05-07, but the current 2026-05-08 close no longer satisfies the written live trigger band. Approval remains recorded; deployment readiness fails closed until price reclaims the band or the band is deliberately revised. |
| GOOG | Intact | Good fit for quality large-cap exposure | Pullback into **341.96 to 362.08** with the post-print structure holding; no chase after the post-print extension | No near-term event block. The Apr 29 report is now explicitly reviewed; next earnings **Jul 23** is still a provider estimate, not primary-confirmed canon. | Lose **331.90** or fail the post-print breakout shelf | Tier 1 | **Almost deployable** | Earnings review is now complete and the thesis is confirmed, but close **395.14** is still extended above the written band. |
| MSFT | Intact | Good fit for quality AI platform exposure | Pullback into **389.64 to 412.56** with support holding, or stronger repair that can reclaim the 200-day cleanly | No near-term event block. The Apr 29 report is now explicitly reviewed; next earnings **Jul 29** is still a provider estimate, not primary-confirmed canon. The live issue is technical repair, not unresolved earnings. | Lose **378.18** or fail the recovery structure | Tier 1 | **Almost deployable** | Azure and AI monetization confirmed the thesis, but close **413.96** is slightly above band and the stock remains below the 200-day. Better than blocked, still not clean enough to force. |
| LMT | Intact but event-sensitive | Defense fit remains valid | No trigger until after a fresh post-event base forms; mechanical reference band is **548.51 to 582.27** only | **Post-earnings repair mode**. Old setup already failed before the print, so the name stays blocked until a new structure exists | Lose **531.63** or fail to rebuild support after earnings | Tier 1 only after repair | **Do not touch** | The old setup is invalidated and close **514.26** remains below stop / below all major MAs. This is a repair workflow, not an immediate re-entry case |
| BRK.B | Intact | Good fit for ballast in mixed regime | In band near **465 to 472**, but only actionable on clear repair through **481+** | **Reported May 2. Post-print state is now explicit: the timing mismatch is closed for the print itself, but the next-quarter machine date still needs cleanup; do not treat May 2 as a live forward catalyst.** | Lose **459.50** or continue to fail all major MAs | Tier 1 | **Do not touch** | Price is in band, but structure is still weak enough to keep it on the bench. The report does not override the bench state; it confirms that the issue is now post-print interpretation/repair rather than pending timing. |
| XOM | Intact long-term, weaker near-term | Mixed: stronger oil helps, but Hormuz / shipping / LNG disruption risk still muddies the read | In band at **150.24 to 158.44**, but only actionable if price can hold the band and reclaim the 50-day with supportive energy context | **Reported May 1. Underlying quarter was stronger than the GAAP headline, but keep it benched until the next one to two EIA reads plus Hormuz / Qatar LNG follow-through clarify production risk.** | Lose **146.14** or fail another 50-day reclaim attempt | Tier 1 | **Do not touch** | The report improved thesis confidence, not deployment readiness. Price is in band, but the workflow still belongs on the bench until follow-through is cleaner. |
| NVDA | Intact but crowded | AI regime fit remains strong | **Above band at 215.20** versus the **197.01 to 210.84** written band after the 2026-05-09 rerun; wait for a pullback or post-earnings reset | Next earnings **May 20** is timing-sensitive, so no-chase discipline remains active | Lose **190.10** and the MA cluster | Tier 2 | **Wait / no chase** | Business quality is intact, but price is now above band while direct Tech is at cap and the earnings window is close. Do not promote here. |
| VRT | Intact but more crowded than ETN | Good thematic fit | Pullback into the **306.85 to 338.33** working band with support holding; still secondary to ETN unless the setup improves further | No immediate hard block | Lose **291.11** or break the trend structure after the current post-earnings run | Tier 2 | **Watch / research needed** | Levels now exist, but ETN remains the primary AI-power execution name and VRT is still watch-lane / above band |
| GS | Intact but secondary to JPM for primary bank exposure | Useful capital-markets-sensitive financial for tactical board coverage | Close **937.35** is above the **878.71 to 926.76** band; only consider as a tactical add with disciplined size while JPM remains the primary bank setup, and do not let the resolved 10% cash / 25% sector-cap posture become an excuse to chase an above-band entry | No immediate hard block | Lose **854.68** or fail the uptrend after the current test | Tier 2 | **Almost deployable** | The setup is above band, workflow state remains ALMOST, and GS stays secondary to JPM. Do not treat it as deployable-now until promotion is explicit and entry quality improves. |

## Current priority order

### Deployable now
- **ETN** — owner-promoted on 2026-05-09 after the fresh entry-band rerun confirmed ETN remained in band at 401.51; use Tier 2 discipline, stop at 383.23, and no chase above 420.31.

### Promotion review / wait — no full deployable-now authority yet
1. **NVDA** — above band, crowded, Tier 2, and timing-sensitive into May 20; wait for a pullback into band or post-earnings reset

### Almost deployable — explicit promotion still required
1. **JPM** — owner approval is recorded, but the 2026-05-08 close at 302.10 is below the formal 306.82–318.12 band and too close to 301.17 invalidation to keep the live trigger green without reclaim or explicit band review
2. **GOOG** — constructive thesis, still extended above band
3. **GS** — above band and useful tactically, but secondary to JPM and still ALMOST / owner-decision-dependent
4. **MSFT** — slightly above band and still needs stronger repair / explicit promotion

### Post-earnings follow-through — not deployable yet
1. **GOOG** — scorecard complete; strong report, but still extended above the post-print band
2. **MSFT** — scorecard complete; thesis confirmed, but the stock is still below the 200-day and only marginally above band

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

- **Deployable now:** ETN only — owner-promoted as a Tier 2 conditional add after the 2026-05-09 entry-band rerun confirmed it remained inside the written band.
- **Owner-approved but trigger not live:** JPM — approval remains recorded, but the latest machine close at 302.10 is below the formal 306.82–318.12 band and close enough to 301.17 invalidation that the artifact layer must fail closed until reclaim or explicit band review.
- **Wait / no chase:** NVDA — the 2026-05-09 entry-band rerun put NVDA above the written band at 215.20 while the May 20 timing window and Tech concentration cap remain active.
- **Post-earnings follow-through — not deployable yet:** GOOG (scorecard complete; still extended above band), MSFT (scorecard complete; slightly above band and still needs cleaner repair / promotion).
- **Additional near-deployable name, but still subordinate to a stronger peer:** GS (above band, still ALMOST and tactical secondary versus JPM for primary bank exposure; the posture is resolved, but the entry problem is not).
- **Execution-board watch, not yet deployable:** VRT (secondary AI-power name; levels exist but ETN remains first and the setup is still not decision-grade enough to force).
- **Do not treat as deployable — setup or trust issues:** BRK.B and XOM.
- **Do not touch:** LMT (repair mode).

## Freshness and update policy

- Last updated: 2026-05-10
- Data as of: 2026-05-08 close with fresh ETN / NVDA entry-band rerun outputs in `tmp/entry-band-data/`; broader note-layer reconciliation remains selective rather than full-rewrite.
- Refresh cadence: after weekly technical refreshes, after tracked earnings, after material macro regime change, or when a name clearly changes action state
- Next refresh due: after BRK.B is interpreted and its stale machine-layer May 2 next-date is cleared or manually held, after Eaton primary-source post-earnings follow-up lands, after JPM either reclaims the written band or receives an explicit band review, or when MSFT / GOOG / VRT / GS follow-on note sync changes a real action state
- Refresh policy: update action states, triggers, blockers, and size logic only when the evidence materially changes. Do not churn wording just to restate the same setup. Version 1 script output should inform this note, not overwrite judgment.

## Data-quality note

- Inputs are now expected to flow through `tmp/trigger-sheet.json`, which reads from the cached technical, deployment, macro, and earnings artifacts.
- The trigger-sheet script is intentionally read-only. It prepares action buckets, blockers, and invalidation context, but it does not replace human interpretation.
- Inputs are fresh and same-day only when the underlying `tmp/` artifacts are fresh. If freshness flags turn stale, downgrade confidence explicitly.
- The macro/policy layer is cleaner now: the live policy artifact is primary-sourced, but policy probabilities still come from a simplified futures approximation rather than a full FedWatch tree.
- Dashboard validation is warning-grade, not clean: LNG is the only blocking band-review warning, while 16 other band reviews are monitor-only.
- Treat rate and policy context as directional, not precision timing input, even after the stale manual-policy warnings are retired.
- `AMD`, `AMZN`, `CAT`, `CVX`, `LLY`, `LNG`, `PLTR`, and `RTX` remain machine-tracked watch-lane names, but they are **not** part of the execution board in this note. Their current validation warnings are ownership residue, not a hidden promotion into deployable status.
- Treat **NVDA** as the main still-unresolved timing-sensitive next-earnings mismatch affecting deployment trust today, with a forced re-check due by the first post-close chain on **2026-05-13** if cleaner confirmation still has not landed. **BRK.B** timing is now homepage-level confirmed for May 2, but the machine layer still needs a post-report next-date cleanup so Workflow 9 does not inherit stale catalyst framing. XOM is no longer a "write the first interpretation" case; it is now a post-print follow-through case. GOOG and MSFT are no longer pending earnings review; they are now post-print entry-discipline cases.
- **Deployable now** means the gates line up on paper; it does **not** cancel residual date-confirmation caution, crowding risk, normal size discipline, or later price movement out of the written trigger zone.
