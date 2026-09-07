# Portfolio Snapshot

## Purpose

This is the live summary of current portfolio posture, model allocations, and active review notes.

Use it for recurring review, not hype.

Role in the stack:
- this is the canonical portfolio-posture and model-allocation note
- it owns overall posture, draft weights, cash, and portfolio-level review flags
- it does not own exact deployment triggers or gate-by-gate entry decisions, which belong in [[03. Portfolio/Execution Board]]

## Portfolio posture

- **Date:** 2026-05-18
- **Data as of:** 2026-05-18 close
- **Macro regime:** restrictive pause, resilient growth baseline, selective risk-on
- **Overall posture:** selective risk-on with reduced confidence
- **Cash level:** 10% target cash after the 2026-05-07 owner posture decision
- **Drawdown from recent high:** not applicable; still model-draft stage
- **Capital base assumption:** starting framework for roughly $5k to $10k
- **Sizing note:** keep draft weights subordinate to the written risk framework. A fresh in-band signal still does not overrule concentration limits, crowding risk, or warning-grade trust.
- **Current priority order:** ETN remains the first capital-deployment priority. MSFT remains a high-quality owner-promoted staged/manual candidate, but the audit-remediation pass found a live freshness/price-state conflict: the canonical board context had MSFT in/near the working band, while the newer recommendation bundle shows `wait_for_band` / stale-review-required context. Treat MSFT as **planning-only / no action** until fresh technical state and Tech-cap sequencing are resolved. JPM has prior owner approval recorded, but the trigger is **not live** after the 2026-05-15 research handoff; keep it fail-closed / secondary until formal band reclaim or explicit band review clears the parser-vs-research conflict. NVDA is wait / no chase through earnings risk. GOOG and GS are almost deployable. BKNG is near-stop repair/no-chase; BRK.B, LMT, LNG, and RTX are below-stop or repair-state names with no deployment entitlement. Detail lives in the Execution Board, not this snapshot.

## Core holdings

This table owns draft model role and weight only. Thesis detail belongs in [[04. Research/Coverage and Watchlist]]; action-state, trigger, and level detail belongs in [[03. Portfolio/Execution Board]].

| Ticker | Sleeve role | Draft weight | Portfolio status | Detail source |
|---|---:|---:|---|---|
| MSFT | Core Technology quality | 10% | Owner-promoted staged manual candidate, but current state is wait / above-band / no-chase; below 200-day and Tech-cap sequencing prevent fresh action until pullback or explicit band review | Coverage + Execution Board |
| JPM | Core Financials | 14% | Do not touch / below-stop; approval recorded but trigger not live; below formal trigger band and below 301.17 stop; manual-only | Coverage + Execution Board |
| GOOG | Core Technology quality | 10% | Draft core; almost deployable on better entry | Coverage + Execution Board |
| XOM | Core Energy | 10% | Bench / repair until follow-through improves | Coverage + Execution Board |
| LMT | Core Defense | 10% | Repair mode; stance suspended; draft weight is a placeholder and cannot be treated as deployable until owner resolves the defense gap | Coverage + Execution Board |
| BRK.B | Diversified quality ballast | 12% | Repair mode; bench state holds | Coverage + Execution Board |

## Tactical positions

| Ticker | Sleeve role | Draft weight | Portfolio status | Detail source |
|---|---:|---:|---|---|
| ETN | AI-power / electrification tactical | 7% | Deployable now / Tier 1 explicit add; first capital-deployment priority; manual-only | Coverage + Execution Board |
| NVDA | AI leader tactical | 5% | Wait / no chase | Coverage + Execution Board |
| GS | Tactical Financials secondary | 7% | Almost deployable; secondary to JPM | Coverage + Execution Board |

## Speculative sleeve

| Ticker / Asset | Sleeve role | Draft weight | Portfolio status | Detail source |
|---|---:|---:|---|---|
| KTOS | Defense-tech asymmetry | 2% | Draft speculative sleeve | Coverage and Watchlist |
| SLV | Macro / metals hedge | 3% | Draft speculative sleeve | Coverage and Watchlist |


## Owner-approved portfolio-review queue

These names are approved for portfolio-review work only. They carry **0% draft weight** here until a separate model/sleeve/sizing decision is explicitly approved and validator-backed.

| Ticker | Review role | Current blocker | Detail source |
|---|---|---|---|
| PH | Industrial compounder candidate | Technical levels underdefined; valuation not cheap | [[04. Research/Sector Expansion Portfolio Promotion Review - 2026-05-15]] + Execution Board |
| LIN | Materials quality candidate | Premium valuation; entry discipline required | [[04. Research/Sector Expansion Portfolio Promotion Review - 2026-05-15]] + Execution Board |
| META | Communication Services quality candidate | Direct Tech/AI/platform crowding; capex/regulatory risk; setup underdefined | [[04. Research/Sector Expansion Portfolio Promotion Review - 2026-05-15]] + Execution Board |
| CME | Financial infrastructure diversifier | Valuation/rate-volatility regime fit; entry discipline required | [[04. Research/Sector Expansion Portfolio Promotion Review - 2026-05-15]] + Execution Board |
| ITA | Defense/aerospace ETF candidate | Concentrated GE/RTX/BA exposure; look-through acceptance required; no execution authority | `tmp/review-packets/lin-ita-ph-missing-info-closeout-2026-05-18.md` + Execution Board |

## Watch now

Watch-only names carry no model weight and no deployment authority unless separately promoted.

| Ticker | Portfolio implication | Detail source |
|---|---|---|
| AMZN | Large-cap quality monitor | Coverage + Execution Board |
| BKNG | Consumer Discretionary candidate; near-stop repair/no-chase; no model weight | Coverage + Execution Board |
| VRT | AI-power monitor, secondary to ETN | Coverage + Execution Board |
| LLY | Healthcare diversification monitor | Coverage + Execution Board |
| CAT | Industrial read-through monitor | Coverage + Execution Board |
| RTX | Defense below-stop repair monitor; no deployment entitlement | Coverage + Execution Board |
| VXUS | International diversification ETF review target; official proof/band exist but pro-forma currency/EM/overlap review required | Coverage + Execution Board |
| TLT | Duration / macro monitor | Coverage and Watchlist |

## Sector allocation vs. Risk Rules caps

Risk Rules maximum: 25% per single sector. Flag if any sector is within 5% of its cap, and treat the Tech + AI-power sleeve as a separate correlated-sleeve warning even when ETN stays classified as Industrials.

| Sector | Names | Draft Weight Total | Risk Rules Cap | Status |
|---|---|---|---|---|
| Technology | MSFT (10%) + GOOG (10%) + NVDA (5%) | **25%** | 25% | ⚠️ **AT CAP** - do not add more direct Tech exposure without reducing something first |
| Financials | JPM (14%) + GS (7%) | 21% | 25% | ✅ Within limit - GS stays secondary to JPM |
| Diversified Quality | BRK.B (12%) | 12% | 25% | ✅ Within limit |
| Energy | XOM (10%) | 10% | 25% | ✅ Within limit - but still under review, not active |
| Defense | LMT (10%) + KTOS (2%) | 12% | 25% | ⚠️ Decision required - LMT's 10% draft weight is suspended while in repair; either reduce it to a holding placeholder and earmark replacement defense exposure, or formally accept KTOS-only 2% defense exposure until LMT heals |
| Industrials | ETN (7%) | 7% | 25% | ✅ Within limit |
| Commodities | SLV (3%) | 3% | 25% | ✅ Within limit |
| Cash | - | 10% | - | ✅ Aligned to the 2026-05-07 owner posture |

**Concentration action rule:** direct Tech exposure is already at the 25% single-sector cap, and the broader AI-power correlated sleeve still rises to 32% once ETN is included. MSFT is planning-relevant but currently action-blocked by unresolved sequencing and a fresh board-vs-packet state conflict. Default Veritas recommendation from the audit-remediation decision packet: use the proposed 40/60 model planning weight for MSFT (**8% risk assets / 7.2% account-level if 10% cash is retained**), do **not** approve a Tech-cap exception, and do **not** treat MSFT as actionable until fresh band confirmation and pro-forma Tech exposure are clean. Quality is not an exception to concentration discipline.

**Note:** weights shown are draft model weights, not live deployed allocations. No positions have been established.

---

## Risk flags

- This is still a model draft, not an execution-ready account snapshot.
- Draft weights are not live allocations and do not grant trade authority.
- ETN remains the first Tier 1 explicit-add priority and remains manual-only.
- MSFT is owner-promoted as a deployable-now / staged manual candidate, but below-200-day repair risk argues against full initial sizing.
- JPM approval remains recorded, but the current trigger is not live: latest evidence has it below the formal trigger band and below the 301.17 stop. Treat JPM as do-not-touch / below-stop until band reclaim or explicit band review clears the setup.
- GOOG, GS, and NVDA require better entry quality or event resolution before any deployment escalation.
- BKNG is near-stop repair/no-chase; BRK.B, LMT, watch-lane LNG, and RTX are below-stop or repair-state names. Do not soften any of these into deployment entitlement without a fresh reclaim/review.
- Direct Tech is already at the written cap; MSFT deployment requires an explicit sequencing decision and fresh price/band confirmation before any real sizing action. Audit-remediation packet: `tmp/audit-remediation-portfolio-decision-packets.md`.
- Defense has a named gap: LMT's 10% draft weight is suspended while in repair. Randall promoted ITA on 2026-05-18 to review-only Defense/aerospace ETF candidate after official holdings proof, but no canonical model apply, sizing, sleeve, cash, paper/live order, brokerage/account action, or execution authority has occurred; concentration acceptance remains required.
- If total model drawdown exceeds 6% to 8%, force a full review.

## Freshness and refresh policy

- **Last updated:** 2026-05-15 - WF64 bounded freshness/status sync for JPM trigger-not-live residue and portfolio-config freshness; no weight, cash, sleeve, owner-approval, execution entitlement, account, or trade change
- **Data as of:** 2026-05-15 close for JPM/ETN trigger and deployment surfaces; other technical rows remain governed by the Execution Board freshness fields
- **Refresh cadence:** after Execution Board refreshes, tracked earnings, material macro regime changes, or any draft sizing decision
- **Next refresh due:** when a model weight, sleeve role, concentration limit, or portfolio-level status changes materially
- **Refresh policy:** update posture, weights, risk flags, and status lines when the Execution Board, macro regime, or catalyst map changes materially. Do not treat draft weights as live allocations.

## Recommended review actions

1. Use [[03. Portfolio/Execution Board]] for live decision state.
2. Use [[03. Portfolio/Execution Board]] for exact bands, stops, repair zones, and invalidation.
3. Use [[04. Research/Coverage and Watchlist]] for thesis, key risk, and act-when conditions.
4. Review the audit-remediation owner-decision packets in `tmp/audit-remediation-portfolio-decision-packets.md`:
   - MSFT: prefer 40/60 planning weight, no Tech-cap exception, no action until fresh band confirmation.
   - LMT / Defense: prefer LMT 0% active planning role pending repair, validate a Defense ETF role, keep KTOS as a small speculative placeholder.
5. Revisit draft weights only when blocker status, setup quality, thesis conviction, or concentration posture actually changes and WF64/WF56 gated validators support the apply.
6. Keep watch-only and repair-mode names explicitly benched until new evidence changes their lane.
