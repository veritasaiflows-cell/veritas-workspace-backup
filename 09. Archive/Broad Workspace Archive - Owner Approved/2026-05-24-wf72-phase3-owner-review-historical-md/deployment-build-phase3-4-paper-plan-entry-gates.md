# Phase 3/4 Staged $100k Paper Portfolio Plan + Entry Discipline Gates

- **Generated:** 2026-05-17 22:18 MST helper lane
- **Status:** review-only staged paper-portfolio plan; **no order, no live/account/canon authority**
- **Scope:** translate the 2026-05-17 quality-diversification review into a staged $100k Alpaca paper-portfolio implementation plan with entry discipline, WF67 guardrails, market-hours sequencing, and stop lines.
- **Authority boundary:** This artifact is not approval to submit paper orders. Current WF67 implementation supports only scoped paper-trade/pilot artifacts under the implemented guardrails. The existing Phase 6 approval artifact has `pilot_caps.max_notional_usd=500` and `pilot_caps.max_qty=1`; a full $100k paper portfolio requires a new explicit WF67 full-portfolio/basket pilot scope before any submit/cancel execution.

## 1. Current truth inputs

| Input | Relevant truth |
|---|---|
| `tmp/quality-diversification-integrated-review-2026-05-17.md` | Desired planning structure: 54% stock quality sleeve, 36% equity ETF sleeve, 10% reserve/bonds/cash-like sleeve. Entry discipline overrides model target. |
| `tmp/deployment-readiness-surface.json` | Current surface has macro gate `DEGRADED`, 0 critical / 1 warning (`band_staleness`), and only **ETN** listed `DEPLOYABLE NOW`; GOOG/GS/MSFT are almost deployable; NVDA is near-earnings caution; BRK.B/JPM/LMT/XOM are do-not-touch; VRT is watch/research. |
| `07. Risk/Risk Rules.md` | Normal single-name ceiling 15%; sector cap 25%; speculative sleeve up to 5% target / 10% hard exception; catalyst-window and correlated-sleeve escalation required. |
| `07. Risk/Alpaca Paper Trading Guardrails.md` + WF67 continuity | Paper submit/cancel is approved only through exact paper endpoint, paper credentials, kill switch, validator-clean scoped artifact, redacted audit, no live/account/money movement, no inferred approval. |
| `phase-6-paper-execution-approval.json` | Paper-only submit/cancel approved in principle; current implemented pilot caps are 1 share and $500 notional per scoped pilot. |

## 2. Portfolio target model for a $100,000 paper account

This is a **paper simulation target**, not a live recommendation or canonical portfolio mutation.

| Sleeve | Target % | Target $ | Notes |
|---|---:|---:|---|
| Stock quality sleeve | 54% | $54,000 | Quality single names, diversified beyond U.S. mega-cap Tech/AI-power. |
| Equity ETF sleeve | 36% | $36,000 | Broad U.S., international, sector-gap, and thematic ETF exposure after holdings look-through. |
| Reserve / bonds / cash-like | 10% | $10,000 | SGOV-led ballast; do not use high-yield as cash. |
| **Total** | **100%** | **$100,000** | Deploy gradually; cash is valid when setups are not ready. |

### Planning weights from integrated review

| Segment | Candidate | Planning % | Planning $ | Entry status today |
|---|---|---:|---:|---|
| Stock | ETN | 7.2% | $7,200 | Only current deployable-now name, but still owner/WF67 scoped. |
| Stock | GOOG | 6.3% | $6,300 | Wait: above band / almost deployable. |
| Stock | MSFT | 5.4% | $5,400 | Wait: above band; paper pilot active/unfilled separate from this plan. |
| Stock | BRK.B | 4.5% | $4,500 | Reject/hold: do-not-touch until repair lifted. |
| Stock | JPM/GS combined | 4.5% | $4,500 | GS wait; JPM reject/hold below stop. |
| Stock | LIN | 5.4% | $5,400 | Research/promotion packet required. |
| Stock | PH | 5.4% | $5,400 | Research/promotion packet required; compare vs ETN. |
| Stock | CME | 3.6% | $3,600 | Research/promotion packet required. |
| Stock | TMUS | 3.6% | $3,600 | Research/promotion packet required. |
| Stock | WMB | 2.7% | $2,700 | Research/promotion packet required. |
| Stock | GE | 2.7% | $2,700 | Research/promotion packet required. |
| Stock | NVDA | 1.8% | $1,800 | Wait/reject for now: near-earnings, above band, tactical cap only. |
| Stock | KTOS | 0.9% | $900 | Speculative placeholder only; requires explicit high-risk packet. |
| ETF | VTI | 8% | $8,000 | Holdings/Tech overlap validator required. |
| ETF | VXUS | 7% | $7,000 | Issuer/holdings/geography/China/EM/currency validator required. |
| ETF | ITA | 5% | $5,000 | Defense/aerospace gap route; holdings overlap required. |
| ETF | XLI | 4% | $4,000 | Industrials overlap with ETN/PH required. |
| ETF | XLB | 4% | $4,000 | Materials sleeve route; holdings validator required. |
| ETF | PAVE | 3% | $3,000 | Higher-fee/theme/valuation review required. |
| ETF | XLE | 3% | $3,000 | Energy/inflation hedge; avoid XOM/CVX stacking. |
| ETF | XLC | 2% | $2,000 | Small monitor only due GOOG/META overlap. |
| Reserve | SGOV | 6% | $6,000 | Cash-like reserve core. |
| Reserve | SHY | 2% | $2,000 | Short Treasury step-out. |
| Reserve | BND | 1% | $1,000 | Small aggregate ballast. |
| Reserve | SCHP | 1% | $1,000 | Small TIPS/inflation hedge. |

## 3. Required new WF67 scope before full portfolio execution

The current WF67 pilot lane is deliberately tiny (`max_qty=1`, `max_notional_usd=$500`) and order-by-order. A staged $100k paper portfolio is a materially different scope.

A new WF67 full-portfolio/basket pilot scope must exist before any basket/tranche submit path:

1. **New explicit owner scope artifact** naming:
   - paper-only $100k model portfolio simulation
   - allowed symbols/tickers
   - maximum total submitted notional per day
   - maximum per-symbol order notional
   - maximum aggregate open order notional
   - allowed sides: initial buy only unless a sell/cancel/close simulation is separately scoped
   - limit/day only, regular-hours only
   - no market, short, margin, leverage, options, crypto, bracket/OCO/OTO, replace, liquidation, close-position, account mutation, or money movement
2. **Validator changes/allowances** that lift the pilot cap only for that exact basket scope while preserving hard-fail behavior elsewhere.
3. **Basket/tranche request schema** or one-scoped-request-per-order bundle that records:
   - source plan id
   - target sleeve and target percent
   - entry band / limit rationale
   - tranche number
   - maximum notional and limit price
   - risk checks and sector/correlation math
   - owner approval fields still false until explicitly approved
4. **Fresh kill switch** limited to the basket execution window.
5. **Dry-run bundle first**, then main-session final confirmation, then paper-only execution if explicitly authorized.
6. **Post-submit reconciliation** for all open/filled/expired/canceled orders, with redacted audit and no raw secrets/broker responses persisted.

Until that exists, this artifact can only feed non-executable planning and possibly future order-preview generation.

## 4. Staged implementation order

### Phase 3A — Validate the bench before sizing

Do first, no orders:

1. ETF holdings / issuer / overlap validation for VTI, VXUS, ITA, XLI, XLB, PAVE, XLE, XLC, SGOV, SHY, BND, SCHP.
2. Promotion packets for LIN, GE/ITA, PH, TMUS, CME, WMB, VXUS, reserve sleeve.
3. Pro-forma sector/correlation cap check, including ETF look-through.
4. Refresh bands/stops and source freshness.
5. Re-run deployment readiness surface after refresh.

### Phase 3B — Paper tranche design

Do after promotion packets and fresh bands exist:

| Tranche | Target cumulative deployment | Max new deployment | What can enter | Purpose |
|---:|---:|---:|---|---|
| 0 | 0% | $0 | None | Build validators, dry-run bundle, and deploy/wait/reject table. |
| 1 | 20% | $20,000 | Only deployable-now + cash-like reserve + validated broad ETFs with in-band/no-chase entries | Establish paper baseline without forcing full exposure. |
| 2 | 40% | $20,000 | Add validated ETF sleeve gaps and 1-2 newly promoted quality names | Diversify after first tranche behavior confirms process. |
| 3 | 60% | $20,000 | Add second wave of promoted sector names; no near-earnings or above-band chases | Broaden sector coverage. |
| 4 | 80% | $20,000 | Add reserve/bond completion and remaining validated ETFs | Bring portfolio close to target while preserving cash. |
| 5 | 100% max | $20,000 | Only if macro gate, bands, and sector/correlation checks are clean | Full simulation deployment; otherwise hold cash. |

**Recommended max tranches:** 5 tranches of up to 20% each, with a minimum one regular session between tranches unless Randall explicitly approves faster simulation. If the goal is stricter discipline, use 10 tranches of 10% each. Do not deploy all $100k in one session while the macro gate is degraded and several candidates lack promotion packets.

### Phase 4 — First full-portfolio paper pilot sequence

Only after new WF67 full-portfolio scope and validators are clean:

1. Generate a non-executable basket preview from the deploy/wait/reject table.
2. Main session verifies symbols, limits, notional, sector math, and no-chase status.
3. Randall explicitly approves exact basket/tranche terms.
4. Create short-lived kill switch for regular-hours execution window.
5. Submit only approved limit/day paper orders.
6. Reconcile open/filled/expired/canceled states after submission and at/after market close.
7. Record outcome state for later retained-outcome analysis; do not promote paper results to live authority.

## 5. Entry discipline gates

A ticker/ETF can move from planning target to paper-order candidate only if all gates pass:

| Gate | Pass condition | Fail / wait condition |
|---|---|---|
| Authority | New WF67 scope covers the symbol, tranche, notional, and order type. | Missing/expired scope; current $500/1-share pilot cap still applies. |
| Price / band | Current price is inside written entry band or at/below approved limit from packet. | Above band top, stale band, or no band. |
| No-chase | Limit price is at or below the approved band/discount logic; no market orders. | Breakout/FOMO chase, gap-up above band, invented limit. |
| Source freshness | Primary/issuer/official sources current enough for decision. | Stale, contradictory, partial, or unconfirmed critical source. |
| Catalyst | No near-term earnings/FOMC/CPI/material event unless packet explicitly accepts event risk. | Near-earnings caution, event risk not modeled. |
| Risk cap | Single-name <= 15%, sector <= 25%, speculative sleeve <= 5% target / <=10% only by exception. | Cap breach or correlated sleeve stack. |
| ETF look-through | Holdings, concentration, fees, geography/sector overlap understood. | Hidden mega-cap duplication or unreviewed exposure. |
| Technical state | Trend/support/reclaim logic supports entry. | Below stop, repair mode, do-not-touch, watch-only. |
| Paper execution guard | Dry-run validator ok, kill switch unexpired, audit/redaction ok. | Any critical/warning unless explicitly accepted as non-safety. |

## 6. Current deploy / wait / reject starter view

Based only on the inspected readiness surface and integrated review; this must be refreshed before any actual basket preview.

| Symbol / sleeve | Decision now | Reason | Next gate |
|---|---|---|---|
| ETN | Deploy-review only | Only current `DEPLOYABLE NOW`, in band; still macro degraded and paper order scope not approved for full portfolio. | New WF67 scope + exact tranche limit/notional + sector AI-power correlation check. |
| GOOG | Wait | Almost deployable but 4.9% above band top. | Reclaim/entry band refresh and platform overlap check. |
| MSFT | Wait | Almost deployable but 2.3% above band top; separate WF67 pilot is active/unfilled. | Band reclaim/update; Tech cap sequencing. |
| GS | Wait | Almost deployable but above band top. | Financials cap + price discipline. |
| NVDA | Reject/wait | Near earnings in 3d, stale band, 6.9% above band top. | Post-earnings reset and tactical cap review. |
| BRK.B | Reject/hold | Do-not-touch; below stop. | Repair lifted after reclaim/base. |
| JPM | Reject/hold | Do-not-touch; below stop. | Reclaim above stop/band and source refresh. |
| LMT | Reject/hold | Repair/below stop. | Fresh support base after earnings; ITA route may be cleaner. |
| XOM | Reject/hold | Repair mode despite in-band; active-zero preferred. | Energy sleeve via XLE/WMB after review. |
| VRT | Research only | Watch/research; 9.6% above band top. | Promotion packet and no-chase reset. |
| LIN / PH / CME / TMUS / WMB / GE | Research/promotion | Not in current readiness surface; integrated review names packets required. | Build packets, bands, source refresh. |
| VTI / VXUS / ITA / XLI / XLB / PAVE / XLE / XLC | Research/promotion | ETF picks are finalized for review, not execution. | Issuer/holdings/look-through validator and entry levels. |
| SGOV / SHY / BND / SCHP | Research/promotion | Reserve model approved conceptually; still needs yield/duration/tax/account-fit review. | Reserve packet + paper scope. |

## 7. Deploy / wait / reject table template for each tranche

Use this table as the required pre-order control surface. No row should become executable unless every gate is explicit.

| Tranche | Symbol | Sleeve | Target % | Target $ | Proposed tranche $ | Side | Order type/TIF | Limit price | Current price | Band status | Source freshness | Catalyst status | Sector/correlation impact | Risk cap pass? | WF67 scope id | Dry-run status | Decision (`DEPLOY`/`WAIT`/`REJECT`) | Reason | Stop / invalidation | Owner approval status |
|---:|---|---|---:|---:|---:|---|---|---:|---:|---|---|---|---|---|---|---|---|---|---|---|
| 1 | ETN | Industrials / AI-power | 7.2% | $7,200 | TBD | buy | limit/day | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD | not run | WAIT | Full-portfolio WF67 scope missing | TBD | false |

## 8. Market-hours plan

Arizona/MST regular U.S. equity market hours in May:

- **Pre-market planning window:** 05:45-06:25 MST — refresh prices, bands, news/catalyst screen, and validation artifacts. No submits.
- **Opening volatility avoidance:** 06:30-06:45 MST — no basket submits unless specifically scoped; opening prints can distort fills.
- **Primary execution window:** 06:45-11:30 MST — preferred for paper limit/day entries if scope is approved.
- **Late-session review window:** 11:30-12:45 MST — reconcile open/unfilled orders, decide whether to leave, cancel, or let expire under explicit scope.
- **No new routine entries:** after 12:45 MST — avoid last-minute fills unless specifically approved.
- **Post-close reconciliation:** after 13:00 MST — read-only reconciliation, dashboard/status update, outcome-history logging.

Rules:

- Regular-hours only unless a separate extended-hours policy is approved.
- Limit/day orders only.
- No market orders.
- No unreviewed same-day re-submits after an unfilled order expires/cancels.
- If a limit does not fill, that is information; do not chase upward automatically.

## 9. No-chase rules

1. Do not raise a limit after a gap-up unless a fresh packet explicitly updates the entry band and risk/reward.
2. Do not enter above band top just because a target weight says exposure is desired.
3. Do not fill ETF sleeve gaps with hidden overlap that recreates the same Tech/AI concentration problem.
4. Do not add NVDA or other event-risk names before earnings without explicit event-risk approval.
5. Do not convert cash/reserve allocation into HYG/JNK or equity risk to force full deployment.
6. Do not let paper simulation success imply live readiness.
7. Do not use current pilots (ETN/MSFT accepted/unfilled) as permission for a larger basket.

## 10. Explicit stop lines

Stop the plan immediately if any of these occur:

- Live endpoint, live credential, live account, money movement, account-setting, or real trade path appears.
- Any secret, header, token, API key, raw credential, or unredacted sensitive response appears in notes/chat/logs/artifacts.
- New WF67 full-portfolio scope is missing, expired, ambiguous, or does not name the exact symbols/notional/order constraints.
- Existing pilot caps are bypassed without validator-reviewed scope change.
- Kill switch missing, expired, malformed, or broader than the approved execution window.
- Validator critical/warning appears unless main session verifies it is non-safety and explicitly records acceptance.
- Any order terms are invented, stale, contradictory, or not owner/basket-scoped.
- Price is above entry band or near a catalyst window and the packet does not explicitly accept the risk.
- Pro-forma single-name, sector, speculative, or correlated-sleeve cap breaches.
- Generated recommendation, score, dashboard, or clean validation is treated as owner approval.
- Paper result is promoted to live trading, canonical portfolio truth, or external execution entitlement.

## 11. Recommended next concrete actions

1. Keep this as a planning artifact; do **not** submit paper orders from it.
2. Build ETF issuer/holdings/look-through validation first.
3. Build promotion packets for LIN, GE/ITA, PH, reserve sleeve, VXUS, TMUS, CME, WMB.
4. Refresh deployment readiness after packets/bands are current.
5. Draft a new WF67 full-portfolio/basket pilot approval artifact for Randall review, with proposed tranche caps:
   - max 20% account notional per tranche (`$20,000`)
   - max 7.5% account notional per single-name order unless lower target applies
   - max 8% account notional for broad ETF core order unless staged lower
   - max 10 total submitted orders per tranche
   - max 40% aggregate open order notional at any time during initial pilot
6. Only after that scope is explicitly approved and validators are updated: generate dry-run basket preview for Tranche 1.
