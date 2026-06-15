# Workflow 61 - Small Mid Cap Regime Feed and Candidate Sleeve

## Objective

Add a small/mid-cap regime feed and review-only candidate sleeve so the portfolio system can detect improving broadening without prematurely adding small caps or mid caps to the portfolio. As of the 2026-05-13 diversification reopen, this workflow may also carry a review-only diversified fund / commodity probe set so small-cap, fund, and hard-asset candidates can be compared under one risk-gated broadening lens.

## Current State

Opened on 2026-05-12 after Randall noted that small-cap or mid-cap posture may be improving and asked to add small-cap exposure into the regime feed. Reopened/expanded on 2026-05-13 after Randall asked to include small-cap funds, funds, commodities, research, and probability workflows as part of the diversification review path.

Implementation proof on 2026-05-13: `scripts/small_mid_cap_regime_feed.py` v1 exists and wrote `tmp/small-mid-cap-regime-feed.json` plus `.md` in a manual post-close run. The artifact is review-only; all authority flags remain false. QC fix on 2026-05-13: independent review found the v1 feed exposed `market_data_as_of` without enforcing freshness and only presence-checked benchmark data. The feed now degrades stale/unparseable market data, blocks insufficient benchmark history, and has regression tests for both cases.

Cron integration proof on 2026-05-14: after Randall approved cron-edit scope, both WF60 research cron jobs were patched to run `small_mid_cap_regime_feed.py` after the sector/ticker/WF60 composer steps. Controlled proof refreshed `tmp/small-mid-cap-regime-feed.json/.md` at `2026-05-14T21:40:03Z`, `window=post-close`, `status=ok`, with 19/19 proxies having price history. The only improving candidate was `USO`; all small-cap and mid-cap proxy buckets remained deteriorating. Authority fields remained false for canonical mutation, portfolio mutation, sizing/allocation, trade execution, owner approval, watchlist promotion, deployment mutation, owner-approval inference, probability/model authority, model-driven deployment, and capital action.

Refresh on 2026-05-15/16 after the leadership-research pass: `python scripts\small_mid_cap_regime_feed.py --window post-close` wrote `tmp/small-mid-cap-regime-feed.json/.md` with `status=ok`, 19/19 proxies reviewed, and improving review-only candidates `PDBC`, `DBC`, and `USO`. Small-cap and mid-cap buckets remained deteriorating, so the sleeve conclusion stays tactical commodity/research-packet-only rather than broad small/mid-cap allocation. Authority remains false for portfolio mutation, sleeve creation, sizing/allocation, trade/account action, owner approval, and owner-approval inference.

This workflow does **not** add a small-cap, fund, or commodity position to the portfolio. It creates the evidence and proposal path required before a later owner-approved portfolio decision.

## Why this workflow exists

The current regime stack has breadth and sector participation, but small/mid-cap posture is not first-class enough yet.

Current available evidence is mixed:

- `tmp/breadth-state.json` is fresh and shows broad participation: 8/11 sectors above 50DMA.
- Equal-weight vs cap-weight ratio is still deteriorating on 5d and 20d, which argues against a clean broadening confirmation.
- Current regime score says selective risk-on with large-cap quality bias.
- Existing artifacts do not yet provide a dedicated small/mid-cap relative-strength, trend, liquidity, earnings-quality, or risk-budget feed.

## Candidate feed scope

Initial ETF/proxy universe for regime feed only:

- `IWM` / Russell 2000 small caps
- `IJR` / S&P SmallCap 600 quality-biased small caps
- `VB` / Vanguard small-cap broad proxy
- `IJH` / S&P MidCap 400
- `MDY` / S&P MidCap 400 ETF
- `VO` / Vanguard mid-cap broad proxy
- optional quality/value tilts after v1: `IJS`, `IWN`, `IWO`, `IJK`, `IJJ`

Expanded diversified fund / commodity probe set for review-only comparison:

- small-cap / quality / value funds: `IWM`, `SCHA`, `IJR`, `VB`, `AVUV`, `VBR`, `IJS`
- mid-cap funds: `IJH`, `MDY`, `VO`
- precious metals / hard-asset funds: `SLV`, `GLD`
- broad commodities: `PDBC`, `DBC`
- tactical commodity expressions: `USO`, `CPER`, `DBA`, `URA`, `COPX` only when liquidity, volatility, and correlation warnings are explicit

Initial individual-stock candidate posture:

- Do not add individual small/mid-cap names automatically.
- Use ETFs first as regime/asset-class probes.
- Only request individual candidate packets after the regime feed shows sustained confirmation and sector/factor fit.

## Required data fields

For each proxy:

- close and as-of date
- 5d / 20d / 60d relative strength versus `SPY`
- 5d / 20d / 60d relative strength versus `QQQ`
- above/below 20/50/200DMA
- drawdown from 52-week high if available
- volume/liquidity warning
- volatility proxy or ATR band if available
- correlation to existing portfolio crowded sleeves when available
- regime label: improving / neutral / deteriorating / blocked
- owner-gated recommendation: monitor / research packet / proposal candidate / reject-bench

## Proposed artifacts

- `tmp/small-mid-cap-regime-feed.json`
- `tmp/small-mid-cap-regime-feed.md`
- optional dashboard sidecar: `tmp/small-mid-cap-regime-feed.html`

The feed must be review-only and must include an authority block:

- canonical_mutation_allowed=false
- portfolio_mutation_allowed=false
- sizing_allocation_recommendation_allowed=false
- trade_execution_allowed=false
- owner_approval_granted=false
- watchlist_promotion_allowed=false

## Cron posture

Do not schedule a separate small/mid-cap cron. WF61 is now a downstream reader inside the existing WF60 research cron jobs so it does not create another competing writer or truth layer.

Current cadence:

- weekday post-close feed: `Finance - Research Freshness and Opportunity Review` at 14:05 America/Phoenix, after the post-close finance chain.
- Sunday weekly confirmation: `Finance - Sunday Research Opportunity Reset` at 09:35 America/Phoenix, after the Sunday weekly refresh window.

The job may write only `tmp/` review artifacts unless Randall separately approves a specific canonical note sync.

## Candidate promotion path

1. Generate small/mid-cap regime feed.
2. If signal is improving for at least the configured review window, request ETF/fund candidate packets first.
3. Compare against existing sector expansion board and risk rules.
4. If the candidate improves diversification without breaking risk limits, generate a review-only portfolio-change proposal packet.
5. Use the exact gated apply path or ask Randall before any watchlist promotion, portfolio addition, sizing, sleeve, sector-posture, cash, risk-rule, or execution-entitlement change.

## Stop lines

- No automatic portfolio addition.
- No automatic small-cap, fund, commodity, or hard-asset sleeve creation.
- No owner approval inference from improving breadth.
- No trade/account action.
- No sizing/sleeve/cash/risk-rule change.
- No individual small/mid-cap candidate promotion without fundamental, liquidity, technical, and risk checks.
- If equal-weight breadth deteriorates while small/mid proxies improve, mark signal as mixed rather than bullish.

## Acceptance gates

- v1 feed script or wrapper exists and runs cleanly.
- It validates freshness and source dates.
- It distinguishes ETF/proxy regime signal from portfolio recommendation.
- It names top candidates but keeps all actions review-only.
- It is represented in Active Workflows and, after proof, in the cron-owned monitor table.

## Next action

Monitor the next ordinary WF60 scheduled runs for feed freshness, especially Sunday. Keep the feed review-only and do not route any small/mid-cap, fund, or commodity candidate into portfolio mutation without explicit Randall approval. Current read-through: commodities are the only improving broadening cue; small/mid-cap sleeves are still not confirmed. Optional later enhancement: add the correlation sidecar once scheduled proof is stable.
