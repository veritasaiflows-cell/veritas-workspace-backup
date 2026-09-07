# Portfolio Model 40% ETF / 60% Stock Proposal

- Generated: 2026-05-18T03:29:00Z
- Status: review-only proposal
- Canonical writes applied: no
- Live/paper trade authority: none from this proposal
- Source basis: Portfolio Snapshot, Execution Board, Risk Rules, market-state, macro-regime, current capital-deployment recommendation bundle, and validation artifact available in this run.

## Conclusion

A 40% ETF / 60% stock model is directionally safer than the current stock-heavy draft because it reduces single-name execution dependency, gives a cleaner answer to the suspended LMT/defense gap, and lowers the need to force repair-state names into active allocations. The model should not be applied yet: ETF holdings/overlap, sector-cap, cash-treatment, and WF64/WF56 gated-apply validators are required first.

Best proposal: treat the 40/60 model as a **risk-asset model** and preserve the existing 10% cash target unless Randall explicitly approves changing cash. If cash is preserved, account-level target becomes **36% ETFs / 54% individual stocks / 10% cash**, which keeps the same 40/60 ETF-stock ratio on the invested 90% sleeve.

## Authority boundary

This is a model proposal only. It does not grant owner approval, portfolio mutation authority, external execution authority, paper/live order authority, cash movement authority, or brokerage/account authority. Any canonical apply would need exact old/new patch material, approval artifact, backups/rollback, validators, and post-apply proof through WF64/WF56.

## Proposed risk-asset model

| Sleeve | Target within risk assets | Account-level if 10% cash retained | State | Rationale |
|---|---:|---:|---|---|
| ETFs | 40% | 36% | Wait / validator required | Diversifies away from single-name timing risk; fills defense/materials/market-beta gaps with less idiosyncratic pressure. |
| Individual stocks | 60% | 54% | Partial deploy / mostly wait | Keep best direct-conviction names, but reduce repair-state placeholders and cap Tech/AI crowding. |
| Cash | n/a | 10% | Preserve unless separately approved | Existing Portfolio Snapshot target cash is 10%; changing it is a separate decision. |

## ETF sleeve proposal (40% of risk assets)

Exact ETF tickers require holdings/overlap, expense/liquidity, and technical validation before canonical sizing. Candidate tickers below are role candidates from the current watch/ETF monitor layer where available.

| ETF role | Candidate examples | Risk-asset weight | Account-level weight with 10% cash | Deploy state | Notes / blockers |
|---|---|---:|---:|---|---|
| Broad U.S. equity core | Broad low-cost market ETF, e.g. S&P 500 / total-market proxy | 12% | 10.8% | Wait / evidence absent | Needed to make ETF sleeve durable instead of only sector bets; exact ticker not evidenced in current files. |
| Defense / aerospace gap filler | ITA or equivalent defense/aerospace ETF | 7% | 6.3% | Wait / review-only | Better than forcing LMT while LMT is below-stop repair; still needs holdings concentration review. |
| Industrials / capex / infrastructure | XLI or PAVE | 6% | 5.4% | Wait / review-only | Fits selective risk-on and ETN adjacency, but avoid overstacking AI-power/capex correlation. |
| Financials diversified exposure | XLF or equivalent | 5% | 4.5% | Repair / wait for reclaim | Current XLF monitor is below stop / repair reference; do not deploy until reclaim/fresh review. |
| Energy / inflation sensitivity | XLE or equivalent | 4% | 3.6% | Wait / review-only | Diversifies XOM single-name risk; requires commodity/oil regime and Exxon/Chevron overlap review. |
| Materials / quality cyclicals | XLB or VAW | 3% | 2.7% | Wait / review-only | Complements LIN/PH review queue without forcing single-name promotion. |
| Macro diversifier | TLT and/or SLV/PDBC-style role | 3% | 2.7% | Watch / macro-confirmation required | TLT below reclaim; SLV macro-linked; commodity cue improving but review-only. |

ETF sleeve total: **40% risk assets / 36% account-level if 10% cash retained**.

## Individual stock sleeve proposal (60% of risk assets)

Weights below are proposal weights, not deployable instructions. They intentionally reduce or zero repair-state placeholders until technical and evidence gates improve.

| Ticker | Proposed risk-asset weight | Account-level with 10% cash | State | Rationale / condition |
|---|---:|---:|---|---|
| ETN | 9% | 8.1% | Deployable now / manual-only, but source freshness review-required | Keep as first capital-deployment priority; in-band, but near upper/no-chase area and source freshness blocker remains. |
| MSFT | 8% | 7.2% | Deployable/staged manual in owner note; current packet says wait_for_band | Keep starter-sized because direct Tech is capped and MSFT remains below 200-day / sequencing-constrained. |
| GOOG | 8% | 7.2% | Almost deployable / wait for band | Keep core quality exposure, but no chase above band; official IR capture must be consumed by WF65/WF66 before apply. |
| BRK.B | 7% | 6.3% | Repair / reclaim watch | Reduce from current 12% placeholder until 200D/reclaim setup heals. |
| JPM | 5% | 4.5% | Do not touch / trigger not live | Keep only a reduced model placeholder; no deployment until authoritative trigger band reclaim or owner-approved band review. |
| GS | 4% | 3.6% | Almost deployable / wait for band | Secondary financials; do not promote until broader bank review and entry clear. |
| XOM | 4% | 3.6% | Repair / do not touch | Reduce single-name energy; pair with ETF sleeve only after commodity/technical review. |
| NVDA | 4% | 3.6% | Wait / no chase / event-risk freeze | Keep AI leader exposure small; no deployment escalation through event-risk/extension. |
| LMT | 0% | 0.0% | Below-stop repair / suspended | Do not carry a 10% active weight while repair state controls; replace defense exposure with ETF role pending review. |
| KTOS | 1% | 0.9% | Speculative watch / repair context | Optional placeholder only; current close below reclaim structure. |
| LIN | 3% | 2.7% | Portfolio-review only / defined setup | Quality materials candidate; no deployment authority until fundamental/valuation packet and owner promotion. |
| CME | 3% | 2.7% | Portfolio-review only / defined setup | Financial infrastructure diversifier; avoid hidden third-bank exposure. |
| WMB | 2% | 1.8% | Watch / pullback setup | Energy infrastructure diversification candidate; wait for pullback and income/rate review. |
| PH | 2% | 1.8% | Portfolio-review only / underdefined wait | Industrial compounder candidate; needs levels/valuation before active model role. |

Stock sleeve total: **60% risk assets / 54% account-level if 10% cash retained**.

## Deployment state

| Bucket | Names / roles | State |
|---|---|---|
| Deploy-now candidate but still manual-only | ETN; MSFT only as staged/manual per owner note | No automatic action; source freshness and concentration gates still require review. |
| Wait / almost deployable | GOOG, GS, LIN, CME, WMB, PH, most ETF roles | Need band/reclaim, valuation, holdings, and overlap validation. |
| Repair / do not force into model | LMT, XOM, JPM, BRK.B, XLF, TLT, KTOS | Keep reduced/zero/placeholder until reclaim or fresh review. |
| No-chase / event-sensitive | NVDA, direct Tech/AI-power additions | Direct Tech already at cap in current snapshot; do not add without reducing other Tech or writing an exception. |

## Risk and concentration notes

- Single-name proposal weights stay below the 15% normal single-position ceiling.
- Sector validation is incomplete because ETF holdings overlap is not resolved. Direct-stock Technology would be MSFT 8% + GOOG 8% + NVDA 4% = 20% of risk assets before any tech-heavy broad ETF look-through; ETF look-through may push effective Tech above the 25% sector cap.
- ETN + XLI/PAVE + possible broad-market AI/capex exposure can still overstack the AI-power/capex sleeve even if sector labels differ.
- Defense is cleaner as ETF-first while LMT and RTX remain repair/watch states.
- Financials should not stack JPM + GS + XLF + CME without a look-through cap check.
- Macro regime supports selective risk-on / large-cap quality bias, not aggressive speculative expansion.

## Validators needed before any canonical WF64/WF56 apply

1. ETF holdings/sector look-through validator for proposed ETF candidates.
2. Pro-forma sector and correlated-sleeve exposure validator, including broad ETF technology overlap.
3. Pro-forma single-name weight validator against 15% normal ceiling and 25% sector cap.
4. Cash-treatment decision validator: gross 40/60 risk-asset model vs account-level 36/54/10 model.
5. Execution-state validator that blocks repair/watch names from deployable language.
6. Source freshness validator for capital recommendation packets; current packets are validator-clean but source freshness is stale/review-required at packet level.
7. Exact patch preview / semantic preview material for Portfolio Snapshot and any model file targeted.
8. Standing/scoped approval artifact matching proposal id, target files, diff hash, and category scope.
9. Backup/rollback and post-apply validation chain.

## Blockers

- No exact ETF ticker selection is validated yet.
- Current capital-deployment packets remain review-only with `apply_allowed=false`, `owner_approval_granted=false`, and `trade_or_account_action_allowed=false`.
- Current recommendation packet source freshness is stale/review-required despite validation being clean.
- Direct Tech and AI-power/capex overlap require a real look-through check before model apply.
- Existing cash target is 10%; changing cash would be a separate owner decision.
- This proposal intentionally does not apply canonical note/model changes.
