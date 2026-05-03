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
| ETN | Intact | Strong fit with AI power, electrification, and industrial capex | Pullback into **388 to 396** with support holding, not continuation at **409.70** outside band | No immediate hard catalyst block | Lose **382.50** or break the recent structure | Tier 2 now, potential Tier 1 on stronger confirmation | **Almost deployable** | Best chart in the sheet, but current price is extended versus the preferred zone |
| JPM | Intact | Good fit in selective risk-on with stable credit and curve backdrop | Pullback into **300 to 306** while holding the 200-day and higher-low structure | No immediate earnings blocker | Lose **295.50** and the 200-day/higher-low structure | Tier 1 | **Almost deployable** | High-quality setup, but still better on pullback than force |
| GOOG | Intact | Good fit for quality large-cap exposure | Pullback into **325.66 to 344.66** only after explicit post-earnings review and revalidation | Post-earnings review still required before any deployment call. No near-term event block (next earnings Jul 23), but price remains extended above the post-print band. | Lose **305.50** or fail post-print trend | Tier 1 | **Blocked** | Strong post-Apr-29 reaction, but do not treat as deployable until explicit post-earnings review is complete and price revalidates into the band. |
| MSFT | Intact | Good fit for quality AI platform exposure | Pullback into **389.64 to 412.56** remains the working post-print band, but no deployment until explicit post-earnings review is complete | Post-earnings review required — Azure growth rate, guidance, and AI monetization commentary. No near-term event block (next earnings Jul 29). Below 200d MA (~467) remains a structural overhang. | Lose **385.00** or fail to hold post-print band | Tier 1 | **Blocked** | Price is inside the post-print band, but that alone is not enough. Keep blocked until the Apr 29 earnings read is explicitly reviewed and cleared. |
| LMT | Intact but event-sensitive | Defense fit remains valid | No trigger until after a fresh post-event base forms | **Post-earnings repair mode**. Old setup already failed before the print, so the name stays blocked until a new structure exists | Lose **581.50** or fail to rebuild support after earnings | Tier 1 only after repair | **Do not touch** | The old setup is invalidated and the post-earnings interpretation is still a repair workflow, not an immediate re-entry case |
| BRK.B | Intact | Good fit for ballast in mixed regime | In band near **465 to 472**, but only actionable on clear repair through **481+** | **May 2 earnings is too close for any new ballast add, and the machine layer now shows May 2 rather than the old May 4 vault date; treat exact timing as unconfirmed until IR is checked.** | Lose **459.50** or continue to fail all major MAs | Tier 1 | **Do not touch** | Price is in band, but structure is still weak enough to keep it on the bench. Near-term earnings timing adds no reason to override the bench state. |
| XOM | Intact — oil macro materially improved | Oil macro improved (WTI ~$106 vs $84–97 prior range); macro sensitivity remains high | Pre-print close 154.33 above requalification level 141.97. Above 20d and 200d MA. Wrestling with 50d (~154.79). No entry band yet defined. | May 1 earnings print now moves this into post-print requalification review. | Lose **141.97** requalification level or fail post-print structure | Tier 1 | **Watch / research needed** | Old "do not touch" driven by stale Apr 24 price context. Oil macro materially improved. Pre-print structure cleared the 141.97 requalification gate. Do not promote until the post-print review confirms the setup survives earnings. |
| NVDA | Intact but crowded | AI regime fit remains strong | Pullback into **186 to 191** only, never on chase above current levels | Crowding keeps discipline high. Machine inputs now point to **May 20** earnings rather than the old **May 27** vault date, so keep this at **Almost deployable** only and do not promote it further until the timing is confirmed from IR. | Lose **179.50** and the MA cluster | Tier 2 | **Almost deployable** | Attractive, but only on disciplined pullback, not current price. Date trust is improved, not fully cleared. |
| AMZN | Intact but still undefined technically | Broad quality fit is fine | Pullback into **235.52 to 255.09** (post-print band; newly defined Apr 28, not yet human-validated for deployment) | No near-term event block (next earnings Jul 30). Stale pre-print block cleared. Entry band and stop not yet human-validated. | Post-earnings structure failure or renewed AWS weakness | Tier 2 | **Watch / research needed** | Essentially flat +1.5% post-Apr-29 print — no impairment, no conviction either. Block cleared. Human validation of entry band and stop required before deployment consideration. |
| VRT | Intact but more crowded than ETN | Good thematic fit | No deployment trigger until explicit entry band and stop exist | No immediate hard block | Break in trend quality or failed support after setup forms | Tier 2 | **Watch / research needed** | Leadership is real, but this is not yet decision-grade without defined levels |
| RTX | Under active review | Useful aerospace and defense mix, plus LMT read-through context | No deployment trigger until explicit entry band and stop exist | No immediate hard block | Chart remains weak until support and trend quality improve | Tier 2 | **Do not touch** | Now tracked on the daily board, but current structure is weak and the setup is still underdefined |
| CAT | Under active review — post-print thesis intact | Useful industrial capex and infrastructure proxy; regime fit supported by post-print demand confirmation | No deployment trigger until band refreshed for post-print price (~890). Pre-print band 779–831 is stale. | **Apr 30 earnings already passed. The pre-print setup is obsolete; explicit post-earnings review plus refreshed band/stop definition are required before any deployment call.** | Break in trend quality or failed support after a defined setup exists | Tier 2 | **Watch / research needed** | Strong +~7.4% post-Apr-30 print confirmed industrial demand thesis and is a positive ETN read-through, but that does not make the old setup usable. Treat this as a post-print rewrite case, not a live entry candidate. |
| GS | Under active review | Useful capital-markets-sensitive financial for tactical board coverage | No deployment trigger until explicit entry band and stop exist | No immediate hard block | Break in trend quality after a defined setup exists | Tier 2 | **Watch / research needed** | Daily coverage added, but the name is still missing explicit levels |

## Current priority order

### Closest to justified action
1. **ETN** on pullback only (near-earnings caution — May 5)
2. **JPM**
3. **NVDA** on pullback only

### Post-earnings review — not deployable yet
1. **MSFT** — blocked pending explicit post-earnings review (in band post-print; below 200d; review Azure commentary before entry)
2. **GOOG** — blocked pending explicit post-earnings review (extended post-print rally; pullback and revalidation required)

### Watch — block cleared or setup undefined
1. **AMZN** — block cleared; entry band not yet human-validated
2. **CAT** — post-earnings positive; band stale; refresh required
3. **XOM** — post-print requalification review required
4. **GS** — WATCH / RESEARCH NEEDED (workflow-state false-positive path is repaired; still not decision-grade)
5. **VRT** — no entry band defined

### Bench, blocked, or invalidated
1. **LMT** — repair mode
2. **BRK.B** — chart weak
3. **RTX** — setup underdefined

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

- **Best near-deployable candidate:** ETN on pullback only (near-earnings caution — May 5).
- **Best high-quality near-deployable candidate:** JPM.
- **Best tactical name if price comes in:** NVDA.
- **Post-earnings review — not deployable yet:** MSFT (priority; in band post-print; explicit earnings review required before any entry), GOOG (explicit earnings review still required; pullback and revalidation into band needed).
- **Watch — block cleared, setup not yet validated:** AMZN (entry band not human-validated), CAT (band stale post-print; refresh required), XOM (post-print requalification review required).
- **Do not treat as deployable — setup or trust issues:** BRK.B, RTX, GS (workflow-gated to WATCH / RESEARCH NEEDED; explicit levels and thesis review still missing), VRT.
- **Do not touch:** LMT (repair mode).

## Freshness and update policy

- Last updated: 2026-05-01
- Data as of: bounded post-earnings review priority pass for MSFT, AMZN, GOOG, CAT, XOM — states updated to reflect post-Apr-29 and post-Apr-30 print outcomes. Machine workflow-state gating has improved materially, but note-layer reconciliation is still incomplete for several names. ETN, JPM, NVDA, LMT, BRK.B, RTX, GS, VRT states unchanged from Apr 24 note.
- Refresh cadence: after weekly technical refreshes, after tracked earnings, after material macro regime change, or when a name clearly changes action state
- Next refresh due: after XOM post-print requalification review, after ETN May 5 earnings print (near-earnings caution active), or when MSFT/GOOG/AMZN post-earnings review notes are completed by operator
- Refresh policy: update action states, triggers, blockers, and size logic only when the evidence materially changes. Do not churn wording just to restate the same setup. Version 1 script output should inform this note, not overwrite judgment.

## Data-quality note

- Inputs are now expected to flow through `tmp/trigger-sheet.json`, which reads from the cached technical, deployment, macro, and earnings artifacts.
- The trigger-sheet script is intentionally read-only. It prepares action buckets, blockers, and invalidation context, but it does not replace human interpretation.
- Inputs are fresh and same-day only when the underlying `tmp/` artifacts are fresh. If freshness flags turn stale, downgrade confidence explicitly.
- The macro file still carries two warnings: the Fed target range is hardcoded as of 2026-04-19, and FedWatch cut probability is not wired.
- Dashboard validation remains **warning-level**, with timing-sensitive earnings-date changes still requiring direct confirmation.
- Treat rate and policy context as directional, not precision timing input, until those warnings are cleared.
- Treat NVDA and BRK.B as the active next-earnings timing mismatches still affecting deployment trust today. CAT is no longer a next-date mismatch case; it is now a post-earnings note-rewrite case.
- **Do not upgrade any name to deployable now from this refresh alone.** Current evidence is fresh but only usable with caution.
