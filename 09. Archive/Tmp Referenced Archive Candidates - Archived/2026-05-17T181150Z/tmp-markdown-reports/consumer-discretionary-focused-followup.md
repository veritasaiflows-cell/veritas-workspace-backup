# Consumer Discretionary Focused Follow-up — BKNG + TJX + AMZN Taxonomy Review, HD Alternate

- **Generated:** 2026-05-10T22:40:00Z
- **Posture:** review-only focused follow-up lane
- **Authority:** no canonical mutation, no watchlist promotion, no portfolio/deployment mutation, no sizing/allocation recommendation, no trade execution, no owner approval inference.
- **Freshness:** web fetches and SEC submission checks performed 2026-05-10; market/fundamental snapshot data through 2026-05-08 where yfinance was available.

## Source / tool status

- `web_search` was attempted for BKNG, TJX, AMZN, and HD, but the host returned: **SearXNG base URL is not configured**. Search could not be used as a reliable source.
- `web_fetch` was used for direct official / credible pages:
  - SEC submissions API for AMZN, BKNG, TJX, HD.
  - TJX quarterly results page.
  - Home Depot quarterly earnings and 2026 news release pages.
- AMZN and BKNG investor pages returned access blocks / 403 in direct fetch, so SEC filings plus yfinance snapshot data were used as the fallback evidence layer.
- yfinance snapshot data was saved to `tmp/consumer-discretionary-followup-yfinance.json`.

## Current source anchors

| Ticker | Source anchors found | Current evidence implication |
|---|---|---|
| AMZN | SEC: latest 10-Q filed 2026-04-30; latest earnings-related 8-K filed 2026-04-29. SEC SIC: Retail-Catalog & Mail-Order Houses. yfinance: Consumer Cyclical / Internet Retail. | Taxonomy supports Consumer Discretionary relevance, but workspace thesis still treats AMZN as Large-Cap Platform Quality with AWS/AI correlation. |
| BKNG | SEC: latest 10-Q filed 2026-04-28; 8-K filed 2026-04-28 and another 8-K on 2026-05-07. SEC SIC: Transportation Services. yfinance: Consumer Cyclical / Travel Services. | Cleanest Consumer Discretionary diversifier in the shortlist, but current technical state is weak. |
| TJX | SEC: latest 10-K filed 2026-03-31. TJX official quarterly page lists Q4 Fiscal 2026 earnings release, reconciliations, and Form 10-K. SEC SIC: Retail-Family Clothing Stores. yfinance: Consumer Cyclical / Apparel Retail. | Strongest defensive-discretionary candidate; quality is real, but current setup and valuation need discipline. |
| HD | SEC: latest 10-K filed 2026-03-18. Home Depot official IR page lists Q4/FY2025 results and a May 19, 2026 Q1 earnings call announcement. SEC SIC: Retail-Lumber & Other Building Materials Dealers. yfinance: Consumer Cyclical / Home Improvement Retail. | High-quality cyclical alternate, but it has an active near-term earnings date and weak current growth/setup. |

## Portfolio and sector fit

Consumer Discretionary remains worth researching because the model portfolio has **0% XLY exposure**, but this is not a broad sector deployment signal:

- XLY is above its 50-day average in the sector board, but still underperforming SPY over 1d, 5d, and 20d.
- Direct Technology is already at the 25% cap.
- Tech + AI-power correlated sleeve remains warning-grade at 32% including ETN.
- The active deployment board is intentionally narrow.
- Therefore, the correct output is a **research/promotion-review queue**, not a deployment decision.

## AMZN taxonomy review

**Verdict:** keep AMZN in the workspace as **Large-Cap Platform Quality / tactical watch**, but add an explicit taxonomy note if promoted later: AMZN is a **hybrid Consumer Discretionary + Cloud/AI platform** name.

Evidence:

- SEC SIC classifies Amazon under retail catalog / mail-order houses.
- yfinance classifies AMZN as Consumer Cyclical / Internet Retail.
- Workspace Coverage Universe classifies AMZN as Large-Cap Quality / Tactical with a thesis built on AWS, retail operating leverage, and advertising growth.
- AMZN's current yfinance snapshot shows strong growth and technical momentum: revenue growth 16.6%, earnings growth 74.8%, above 50DMA and 200DMA, +14.4% 20-day return.

Why this matters:

- AMZN can help Consumer Discretionary research breadth, but it **does not solve diversification cleanly** because AWS/AI/cloud and mega-cap growth correlation overlap with the capped Tech/AI-power sleeve.
- If Randall wants a clean Consumer Discretionary diversifier, AMZN should rank behind BKNG/TJX on taxonomy purity.
- If Randall wants the best business-quality candidate regardless of taxonomy purity, AMZN remains first.

**Action state:** research-only / taxonomy-gated. Do not promote without explicit taxonomy decision and a separate technical entry/invalidation pass.

## Candidate verdicts

### 1. BKNG — Cleanest Consumer Discretionary promotion-review candidate

- **Resolved entity:** Booking Holdings Inc., Nasdaq, U.S.
- **Role fit:** clean Consumer Discretionary / travel services diversifier.
- **Fundamental snapshot:** yfinance shows strong profitability and cash generation: operating margin ~25.0%, net margin ~22.2%, operating cash flow ~$9.34B, free cash flow ~$7.08B, revenue growth ~16.2%, earnings growth ~240%.
- **Valuation snapshot:** forward P/E ~13.5 and trailing P/E ~21.9; reasonable relative to margins/cash generation if travel demand remains intact.
- **Technical snapshot:** below both 50DMA and 200DMA; 20-day return ~-4.3%, 63-day return ~-6.9%.
- **Main risk:** travel cyclicality, discretionary demand slowdown, and current broken/weak chart.
- **Verdict:** **Best clean sector candidate, but not deployable.** Promote only to deeper research / technical pass, not to execution.

### 2. TJX — Best defensive-discretionary research candidate

- **Resolved entity:** The TJX Companies, NYSE, U.S.
- **Role fit:** defensive Consumer Discretionary / off-price retail diversifier.
- **Fundamental snapshot:** yfinance shows revenue growth ~8.5%, earnings growth ~27.9%, operating margin ~13.3%, net margin ~9.1%, operating cash flow ~$6.87B, free cash flow ~$3.89B.
- **Valuation snapshot:** forward P/E ~27.1, trailing P/E ~31.4; valuation is not cheap for retail.
- **Technical snapshot:** below 50DMA but above 200DMA; 20-day return ~-5.1%.
- **Main risk:** rich multiple, retail margin/inventory risk, and current short-term technical weakness.
- **Verdict:** **Second-best candidate.** Worth deeper research because it diversifies better than AMZN and has more defensive consumer behavior than HD/BKNG, but entry discipline matters.

### 3. AMZN — Best business, weak diversification purity

- **Resolved entity:** Amazon.com, Inc., Nasdaq, U.S.
- **Role fit:** hybrid Large-Cap Platform Quality / Consumer Discretionary / Cloud-AI exposure.
- **Fundamental snapshot:** yfinance shows revenue growth ~16.6%, earnings growth ~74.8%, operating cash flow ~$148.5B, but free cash flow ~$9.8B due to capital intensity; operating margin ~13.1%, net margin ~12.2%.
- **Valuation snapshot:** forward P/E ~27.6, trailing P/E ~32.6, P/S ~3.95; not cheap, but less extreme than many AI/growth names.
- **Technical snapshot:** above 50DMA and 200DMA; 20-day return ~+14.4%, 63-day return ~+29.7%.
- **Main risk:** taxonomy/correlation risk, valuation, AWS growth expectations, and capex intensity.
- **Verdict:** **Best company-quality candidate, but not the best diversification candidate.** Keep as taxonomy-gated research, not clean Consumer Discretionary promotion.

### 4. HD — Cyclical-quality alternate, not first wave

- **Resolved entity:** The Home Depot, Inc., NYSE, U.S.
- **Role fit:** high-quality home-improvement cyclical.
- **Fundamental snapshot:** yfinance shows negative revenue growth ~-3.8% and earnings growth ~-14.2%, but still strong cash generation: operating cash flow ~$16.3B and free cash flow ~$8.62B.
- **Valuation snapshot:** forward P/E ~19.5, trailing P/E ~22.3; fair if housing/rates improve, less attractive if demand remains weak.
- **Technical snapshot:** below 50DMA and 200DMA; 20-day return ~-5.9%, 63-day return ~-17.6%.
- **Catalyst:** Home Depot IR page lists Q1 earnings conference call on **2026-05-19**.
- **Main risk:** housing/rate sensitivity, weak current growth, weak chart, and near-term earnings catalyst.
- **Verdict:** **Keep as alternate only.** It is a quality name but not a current promotion candidate before the May 19 earnings read and technical repair.

## Ranking after follow-up

1. **BKNG** — best clean Consumer Discretionary promotion-review candidate; strong cash/margins/valuation, but technical state blocks deployment.
2. **TJX** — best defensive-discretionary research candidate; quality and diversification value are real, but valuation/setup are not clean.
3. **AMZN** — best business-quality candidate, but taxonomy/correlation risk makes it a bridge name, not a clean Consumer Discretionary fix.
4. **HD** — quality cyclical alternate; wait for May 19 earnings and chart repair.

## Recommended next action

Do **not** mutate the Watchlist, Coverage Universe, Deployment Trigger Sheet, or Portfolio Snapshot from this pass.

Recommended owner-gated queue item:

> Open a Veritas fundamental + technical follow-up for **BKNG and TJX** as Consumer Discretionary diversification candidates. Keep **AMZN** in a separate taxonomy review lane and keep **HD** as post-May-19 earnings alternate.

## Data-quality scorecard

- **Coverage:** ~75% for high-level screen; primary source pages partially accessible.
- **Conflicts:** 1 material taxonomy conflict — AMZN is Consumer Cyclical by market taxonomy / SEC retail SIC, but workspace treats it as Large-Cap Platform Quality / Tech-adjacent.
- **Freshness:** SEC filing dates and official TJX/HD IR pages current as of fetch; yfinance market data as of 2026-05-08.
- **Confidence cap:** Medium. Direct web search failed; AMZN/BKNG IR pages blocked direct fetch. This is enough for queue ranking, not enough for deployment.

## Limits

- No promotion, sizing, deployment, trade, or owner-approval authority.
- yfinance is Tier 2 data and may be incomplete.
- SEC submissions confirm filings and entity identity, but this pass did not parse full 10-Q/10-K line items in depth.
- No full technical entry-band/invalidation pass was completed.
