# Deployment Build Phase 2 Promotion Packets - Core Quality Candidates

- **Generated:** 2026-05-17 22:18 MST subagent lane
- **Scope:** concise review-only promotion packets for LIN, PH, GE/ITA, TMUS, CME, WMB.
- **Inputs used:** `07. Risk/Risk Rules.md`, `04. Research/Coverage and Watchlist.md`, `04. Research/Sector Expansion Candidate Queue - 2026-05-15.md`, `04. Research/ETF Coverage Promotion Review - 2026-05-15.md`, `03. Portfolio/Execution Board.md`, `tmp/quality-diversification-integrated-review-2026-05-17.md`, `tmp/deployment-readiness-surface.json`, `tmp/technical-refresh.json`, `tmp/band-proposals.json`.
- **Authority boundary:** review-only. No trade, account, brokerage, paper order, portfolio/canon apply, sizing, sleeve, cash, or execution entitlement. Any canonical apply remains WF64/WF56-gated; any brokerage/live action remains owner-approved only.
- **System context:** `tmp/deployment-readiness-surface.json` shows macro gate **DEGRADED**, deployable-now presentation suspended false but canonical note mutation not allowed, and a band-staleness warning. New candidates are not in deployable-now state.
- **Risk frame:** respect normal 15% single-position ceiling, 25% single-sector cap, 5% default speculative sleeve, and catalyst-window escalation discipline. Direct Technology is already capped; these candidates are diversification candidates, not automatic adds.

## Quick verdict table

| Candidate | Sleeve / role | Technical state from artifacts | Primary blocker | Promotion verdict |
|---|---|---|---|---|
| LIN | Materials quality | Constructive; above all major MAs; near/inside reference band | Premium valuation + primary-source refresh | **Advance to full promotion packet first**; not deployable yet |
| PH | Industrial compounder | In band but below 20/50d, above 200d | ETN/CAT opportunity cost + order/FCF refresh | **Advance, but require stronger fundamental/valuation proof than LIN** |
| GE / ITA | Aerospace/defense gap | GE below all MAs/below stop; ITA in band but below 20/50d | GE chart broken; ITA holdings/valuation look-through missing | **Prefer ITA diagnostic route before GE single-name promotion** |
| TMUS | Defensive telecom growth | Below all MAs/below stop | Leverage/rate sensitivity + failed technical gate | **Do not promote yet; keep sector monitor** |
| CME | Financial infrastructure | Above all MAs; near/at upper reference band; needs band review | Financials cap/overlap + rate/vol regime + valuation | **Advance to promotion packet as JPM/GS substitute candidate** |
| WMB | Energy infrastructure | Strong trend but above preferred pullback band | No-chase entry + rate/project/regulatory/income-sleeve fit | **Advance to watchlist packet; wait for pullback/base** |

---

## LIN - Linde plc

- **Thesis:** Best current Materials-quality candidate. Industrial gases oligopoly, mission-critical customer inputs, durable relationships, margin quality, and better inflation pass-through than commodity Materials beta.
- **Portfolio role:** Materials quality sleeve; proposed planning weight in integrated review was **5.4% account-level** inside the stock quality sleeve. Candidate to fill the absent Materials exposure without relying on broad commodity cyclicality.
- **Current evidence:** Coverage note ranks LIN as the top Materials candidate and owner-approved portfolio-review candidate. Technical refresh shows close **506.11**, above 20/50/200d (**503.14 / 497.11 / 461.42**) with bullish 20>50>200 stack. Execution Board says setup is defined but watch-only; preferred entry band **497.11-506.11**, explicit stop **487.17**. Band proposals show workflow state **PROMOTION REVIEW**, earnings state **CLEAR**, days to earnings **75**, but earnings is provider-estimate and not primary-confirmed.
- **Valuation/source gap:** Premium valuation is the main risk. Needs primary-source refresh, recent earnings/filing review, margin/FCF durability, leverage/capex check, and peer valuation sanity versus ECL/SHW/VMC/XLB/VAW. No web/primary source was used in this lane.
- **Technical/entry gate:** Constructive but no-chase. Price is near upper edge of preferred band; reference band **490.63-505.45** / stop **478.25** also says near band. Treat as review-only; do not equate in-band status with deployability.
- **Sector/overlap risk:** Adds true Materials diversification and reduces Tech/AI dependence. Main risk is overpaying for quality; broad Materials ETFs may be cheaper but more cyclical/lower quality.
- **Promotion verdict:** **Advance to full promotion packet first.** LIN is the cleanest single-name diversification candidate in this wave, but promotion requires primary-source refresh, valuation proof, and owner-gated decision.

---

## PH - Parker-Hannifin

- **Thesis:** High-quality industrial compounder tied to motion/control systems, aftermarket, pricing/mix, and margin quality; better-quality cyclical rather than fragile duration growth.
- **Portfolio role:** Industrial compounder / higher-rate-resilient cyclical. Integrated review gave PH a proposed planning weight of **5.4% account-level** but explicitly says it must clear ETN opportunity cost.
- **Current evidence:** Coverage note marks PH as owner-approved portfolio-review candidate. Technical refresh: close **862.72**, above 200d **856.62** but below 20/50d **915.41 / 920.98**; `in_entry_band=true`, below_stop=false. Execution Board table shows portfolio-review only, underdefined wait setup, band **851.36-908.98**, stop **819.35**. Band proposals show workflow **PROMOTION REVIEW**, earnings state **CLEAR**, days to earnings **81**, provider-estimate not primary-confirmed.
- **Valuation/source gap:** Needs latest-result primary-source refresh: orders/backlog, segment margin durability, cash conversion, debt/capital allocation, and valuation versus ETN/CAT/XLI/PAVE. Premium valuation and industrial order slowdown are the key risks.
- **Technical/entry gate:** Technically mixed. It is in the current watch band and above 200d, but below 20/50d; not a clean momentum/reclaim setup. Require support hold above the 200d/stop zone or reclaim of 20/50d before deployment language.
- **Sector/overlap risk:** Overlaps with ETN/CAT/industrial/capex sleeve. If ETN remains the cleaner deployable-quality industrial, PH must justify incremental exposure rather than duplicating the same cyclical factor.
- **Promotion verdict:** **Advance to a full packet, but second behind LIN/CME.** Do not promote to deployable without order durability, valuation, and ETN opportunity-cost proof.

---

## GE / ITA - Aerospace and defense gap

### GE Aerospace

- **Thesis:** Aerospace-quality candidate with engine services, aftermarket economics, aerospace backlog, and commercial/defense exposure; useful while LMT/RTX are repair/watch.
- **Portfolio role:** Single-name aerospace quality / defense-commercial gap; integrated review planning weight **2.7% account-level** if validated.
- **Current evidence:** Coverage note keeps GE as sector monitor only. Technical refresh: close **281.53**, below 20/50/200d (**290.31 / 296.50 / 299.03**), below stop, `in_entry_band=false`. Execution Board says reference band **299.03-311.84**, stop **288.78**, below all MAs, do-not-touch/stop-breached repair context. Band proposals show needs_review=true, band_status **BELOW_STOP**, earnings state **CLEAR** but provider-estimate not primary-confirmed.
- **Valuation/source gap:** Needs fundamental packet, post-spin/source refresh, backlog/services/margin execution evidence, supply-chain risk review, and valuation-premium justification.
- **Technical/entry gate:** Failed. GE must reclaim the stop/200d/reclaim band before any promotion beyond monitor.

### ITA ETF

- **Thesis:** Aerospace/defense ETF proxy while LMT/RTX repair and GE remains technically broken; can fill defense/aerospace gap without forcing one single-name execution risk.
- **Portfolio role:** Defense/aerospace ETF gap monitor; integrated ETF sleeve planning target **5% account-level** if issuer/holdings/overlap validation passes.
- **Current evidence:** ETF review promotes ITA to coverage monitoring only. Technical refresh: close **217.27**, above 200d **216.71** but below 20/50d **220.36 / 225.30**; `in_entry_band=true`, below_stop=false. Band proposals: band **212.15-223.44**, stop **205.88**, earnings unknown/catalyst confidence downgraded because ETF has no earnings catalyst.
- **Valuation/source gap:** Needs issuer fact sheet, holdings concentration, expense/liquidity, defense-budget exposure, overlap with LMT/RTX/GE/KTOS, and look-through sector cap review.
- **Technical/entry gate:** Better than GE but not clean momentum; it is in band while below 20/50d. Needs fresh ETF technicals and holdings validation before proposal.
- **Sector/overlap risk:** Defense/aerospace gap is real, but ITA may concentrate in contractors and overlap with existing defense/GE/KTOS themes.
- **Promotion verdict:** **Prefer ITA diagnostic route before GE single-name promotion.** GE remains monitor/repair until reclaim; ITA can advance to ETF look-through packet, not deployment.

---

## TMUS - T-Mobile US

- **Thesis:** Defensive telecom-growth candidate with wireless execution, service-revenue growth, and FCF generation; less economically cyclical than ad/platform Communication Services names.
- **Portfolio role:** Defensive Communication Services diversifier; integrated review proposed **3.6% account-level** planning weight if leverage/rate sensitivity and technical setup pass.
- **Current evidence:** Coverage note keeps TMUS as sector monitor. Technical refresh: close **185.22**, below all major MAs (**192.17 / 200.74 / 213.01**), below stop, not in entry band. Execution Board reference band **213.01-220.38**, stop **207.11**, below all MAs; do-not-touch/stop-breached repair context. Band proposals show band_status **BELOW_STOP**, significant band drift, earnings state **CLEAR** with days to earnings **~75** but provider-estimate not primary-confirmed.
- **Valuation/source gap:** Needs primary-source refresh on leverage, debt maturity/rate sensitivity, capex/spectrum needs, FCF, buybacks, competitive pricing, and valuation.
- **Technical/entry gate:** Failed. No promotion until reclaim toward 200d/reference band and stop no longer breached.
- **Sector/overlap risk:** Cleaner diversification than META/XLC if platform crowding is binding, but telecom adds leverage/rate risk rather than pure quality growth.
- **Promotion verdict:** **Do not promote yet.** Keep TMUS as sector monitor; assign full packet only after technical reclaim or if Communication Services diversification becomes urgent enough to study despite failed chart.

---

## CME - CME Group

- **Thesis:** Financial market infrastructure / exchange-and-clearing candidate that can benefit from rates, volatility, open interest, and hedging demand without direct bank credit-cycle exposure.
- **Portfolio role:** Financial infrastructure diversifier and possible JPM/GS substitute/complement; integrated review planning weight **3.6% account-level**.
- **Current evidence:** Coverage note marks CME as owner-approved portfolio-review candidate. Technical refresh: close **298.86**, above all major MAs (**287.74 / 296.93 / 276.68**), `in_entry_band=true`, below_stop=false. Execution Board says preferred band **287.74-298.86**, explicit stop **276.68**, technically eligible for deeper review, not promoted. Band proposals show workflow **PROMOTION REVIEW**, earnings state **CLEAR**, days to earnings **66**, provider-estimate not primary-confirmed, and needs_review=true due proposed midpoint drift.
- **Valuation/source gap:** Needs primary-source revenue mix/open-interest/rate-volume refresh, fee/competition review, low-vol downside case, valuation versus ICE and versus JPM/GS opportunity cost.
- **Technical/entry gate:** Constructive but near the upper edge / round-number 300. No chase above 300 without a fresh band review; monitor support at 296.93/287.74 and stop at 276.68.
- **Sector/overlap risk:** Financials already include JPM/GS exposure and sector cap matters. CME is cleaner than adding bank credit risk, but it is still a Financials allocation and must fit under 25% sector cap.
- **Promotion verdict:** **Advance to full promotion packet.** CME is one of the better first-wave candidates because it diversifies Financials factor exposure; not deployable until valuation/regime/sector-cap proof clears.

---

## WMB - Williams Companies

- **Thesis:** Natural-gas transmission/storage infrastructure tied to power demand, LNG, and energy security; less direct spot-price beta than E&P/integrated oil.
- **Portfolio role:** Energy infrastructure / income-infrastructure watch; integrated review planning weight **2.7% account-level** if income/infrastructure sleeve construction begins.
- **Current evidence:** Coverage note keeps WMB as sector monitor. Technical refresh: close **77.72**, above 20/50/200d (**73.82 / 73.25 / 64.18**) with bullish 20>50>200 stack. Execution Board preferred entry band **73.25-75.50**, stop **70.32**, stance watch-only/pullback setup; price is **2.9% above** preferred band top. Band proposals show band_status **ABOVE_BAND_WAIT**, needs_review=true, earnings state **CLEAR**, days to earnings **78**, provider-estimate not primary-confirmed.
- **Valuation/source gap:** Needs primary-source refresh on distribution coverage, leverage, project backlog/regulatory risk, rate sensitivity, FCF/distributable cash flow, and valuation after strong energy moves.
- **Technical/entry gate:** Trend is strong but entry is not. Wait for pullback into 73.25-75.50 or a fresh base/band update; no chase at extended levels.
- **Sector/overlap risk:** Diversifies away from XOM spot oil beta toward gas infrastructure/power/LNG, but still overlaps Energy/inflation sleeve and adds rate-sensitive income characteristics.
- **Promotion verdict:** **Advance to watchlist packet, not deployment.** WMB is useful for energy diversification, but current price behavior demands pullback discipline and income-sleeve risk review.

---

## Recommended sequencing

1. **LIN** - full primary-source + valuation packet first; strongest sector-diversification fit.
2. **CME** - full packet next; best Financials diversifier if JPM/GS exposure is constrained.
3. **PH** - full packet after LIN/CME; must beat ETN opportunity cost.
4. **ITA look-through** before GE - ETF route may solve defense/aerospace gap while GE chart is broken.
5. **WMB** - build packet but keep no-chase pullback gate.
6. **TMUS** - hold as monitor until chart repair; source refresh can wait unless Communication Services urgency rises.

## Universal blockers before any promotion/apply

- Primary-source refresh required for every single-name candidate; issuer/holdings/expense/liquidity look-through required for ITA.
- Fresh technical refresh and band/stop validation required before any deployability claim.
- Pro-forma sector/correlation cap check required, including ETF look-through and ETN/AI-power correlation.
- Owner decision required for any promotion beyond review; brokerage/account execution remains separate and blocked.
