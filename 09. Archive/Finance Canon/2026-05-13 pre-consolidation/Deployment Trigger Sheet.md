# Deployment Trigger Sheet

## Purpose

This file bridges the gap between research and action.

Use it to decide when a name is actually deployable, not just interesting.

Role in the stack:
- this is the canonical deployment-decision note
- it owns deployable, almost deployable, blocked, and do-not-touch states
- it owns the live gate verdict and concise blocker / condition for execution-board names
- exact levels, stops, support, resistance, and repair mechanics live in [[03. Portfolio/Technical Entry and Invalidation Sheet]]
- thesis detail lives in [[04. Research/Coverage Universe]] and portfolio-weight context lives in [[03. Portfolio/Portfolio Snapshot]]

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

This board is intentionally compressed. It owns live execution state and blocker logic only; use the Technical Sheet for exact bands/stops and Coverage Universe for thesis detail.

| Ticker | Action state | Live condition / blocker | Authority note | Detail source |
|---|---|---|---|---|
| ETN | **Deployable now** | Owner-approved Tier 1 explicit add; current gated execution band is 368.42-410.79 and latest artifact close is 401.53 | Manual-only; no automatic execution | Technical Sheet + Coverage Universe |
| JPM | **Deployable now** | Owner-approved setup remains inside current gated execution band 294.57-308.54 at latest artifact close 304.88 | Manual-only; no automatic execution | Technical Sheet |
| GOOG | **Almost deployable** | Thesis confirmed; entry still needs pullback / better setup | Explicit promotion still required | Technical Sheet + Coverage Universe |
| MSFT | **Deployable now** | Owner-approved promotion on 2026-05-12; inside 389.64-412.56 band at latest artifact close; still below 200-day, so use staged manual deployment discipline | Manual-only; no automatic execution; tranche decision remains owner-gated | Technical Sheet + Coverage Universe |
| NVDA | **Wait / no chase** | Above written setup with timing and concentration caveats active | No deployable-now authority | Technical Sheet + Coverage Universe |
| GS | **Almost deployable** | Tactical secondary to JPM; entry discipline still required | Explicit promotion still required | Technical Sheet + Coverage Universe |
| VRT | **Watch / research needed** | Thematic fit is real, but ETN remains primary AI-power execution name | No quiet promotion | Technical Sheet + Coverage Universe |
| BRK.B | **Do not touch** | Repair / chart weakness still active | Bench state holds | Technical Sheet |
| XOM | **Do not touch** | May 11 intraday low pierced the explicit 146.14 stop before reclaiming into a 149.68 close; formal repair review required before any oil-supported thesis refresh | Repair / no-reentry state holds; not a deployable bench | Technical Sheet + Coverage Universe |
| LMT | **Do not touch** | Repair mode after failed setup; current artifact layer is below the **531.63** stop, so repair state is stop-confirmed rather than merely soft bench | No re-entry case yet | Technical Sheet + Coverage Universe |
| LNG | **Do not touch / watch-lane repair** | Watch-lane name, but the 2026-05-11 artifact close **240.70** is below the **253.45** stop and old **260.82** band low | No execution-board entitlement; old band is repair/reference only | Technical Sheet |

## Current priority order

- **Deployable now / Tier 1 explicit add:** ETN.
- **Deployable now / owner-approved bank setup:** JPM — current artifact close is inside the refreshed 294.57-308.54 band; still manual-only and secondary to concentration/risk review.
- **Deployable now / owner-approved promotion:** MSFT — approved 2026-05-12 as a staged manual candidate while inside band; still below 200-day, so starter-tranche discipline applies.
- **Wait / no chase:** NVDA.
- **Almost deployable:** GOOG, GS.
- **Watch / repair:** BKNG and VRT, with BKNG details owned by Coverage Universe + Technical Sheet.
- **Bench / do not touch:** BRK.B, LMT.
- **Repair / stop-test do not touch:** XOM — May 11 pierced the 146.14 explicit stop intraday, reclaimed by close, and now requires formal repair review before any thesis refresh.
- **Watch-lane stop-breached / do not touch:** LNG — not execution-board entitled, but the old watch-lane setup is invalidated until stop reclaim and fresh band review.

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

- Keep the board manual and owner-gated.
- ETN remains the first deployable-now / Tier 1 explicit-add priority.
- JPM is back in deployable-now status on the refreshed artifact layer, but remains manual-only and should not outrank ETN or MSFT without a separate capital-allocation decision.
- MSFT is now owner-promoted to deployable-now review, but execution remains manual and staged because the stock is still below the 200-day; GOOG, GS, and NVDA still need better entry quality, promotion, or timing resolution before escalation.
- LNG is a watch-lane stop breach; it remains review-only repair and does not enter the execution board without explicit promotion after fresh technical repair.
- BKNG and other watch-lane names remain review-only and do not enter the execution board without explicit promotion.

## Freshness and update policy

- Last updated: 2026-05-12 — MSFT owner-approved promotion added as deployable-now / staged manual candidate while inside the 389.64-412.56 band; ETN and JPM current execution bands reconciled to same-day artifacts. No trade, sizing, sleeve, cash, risk-rule, or automatic execution authority granted. LNG stop-breached state and XOM repair language remain in force.
- Data as of: 2026-05-12 close for current execution/technical artifacts unless separately labeled; exact levels live in the Technical Sheet.
- Refresh cadence: after weekly technical refreshes, after tracked earnings, after material macro regime change, or when a name clearly changes action state
- Next refresh due: when an execution-board name changes action state, owner approval state, or live blocker status
- Refresh policy: update action states, triggers, blockers, and size logic only when the evidence materially changes. Do not churn wording just to restate the same setup. Version 1 script output should inform this note, not overwrite judgment.

## Data-quality note

- Inputs are now expected to flow through `tmp/trigger-sheet.json`, which reads from the cached technical, deployment, macro, and earnings artifacts.
- The trigger-sheet script is intentionally read-only. It prepares action buckets, blockers, and invalidation context, but it does not replace human interpretation.
- Inputs are fresh and same-day only when the underlying `tmp/` artifacts are fresh. If freshness flags turn stale, downgrade confidence explicitly.
- The macro/policy layer is cleaner now: the live policy artifact is primary-sourced, but policy probabilities still come from a simplified futures approximation rather than a full FedWatch tree.
- Dashboard validation is currently clean on critical/warning count after accepted repair-mode handling; do not misread that as deployable authority. Monitor-only band reviews and source-confidence caveats still require judgment.
- Treat rate and policy context as directional, not precision timing input, even after the stale manual-policy warnings are retired.
- Watch-lane names remain outside this execution board unless explicitly promoted. Their technical or thesis state is review context, not hidden deployment authority.
- **Deployable now** means the gates line up on paper; it does **not** cancel source-confidence caveats, crowding risk, normal size discipline, or later price movement out of the written trigger zone.
