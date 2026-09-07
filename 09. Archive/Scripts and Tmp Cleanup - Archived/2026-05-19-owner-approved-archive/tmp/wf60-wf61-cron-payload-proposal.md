# WF60/WF61 Cron Payload Proposal - 2026-05-13

## Status

Cron payload integration is ready but not applied. `openclaw cron edit` failed with a Gateway scope/pairing approval block, so the cron store was not hand-edited.

## Intended owner jobs

- Weekday: `25aef99b-7b2b-40a9-823c-2cfff7d5493d` / `Finance - Research Freshness and Opportunity Review`
- Sunday: `5918839c-25a0-4220-8d4a-75f8e71b8e4e` / `Finance - Sunday Research Opportunity Reset`

## Intended weekday execute order

1. `python scripts\sector_expansion_board.py --window post-close`
2. `python scripts\sector_dashboard_suite.py`
3. `python scripts\ticker_monitoring_performance.py --window post-close`
4. `python scripts\research_freshness_opportunity_review.py --window post-close`
5. `python scripts\small_mid_cap_regime_feed.py --window post-close`

## Intended Sunday execute order

1. `python scripts\sector_expansion_board.py --window sunday`
2. `python scripts\sector_dashboard_suite.py`
3. `python scripts\ticker_monitoring_performance.py --window sunday`
4. `python scripts\research_freshness_opportunity_review.py --window sunday`
5. `python scripts\small_mid_cap_regime_feed.py --window sunday`

## Stop lines

- No trade/account action.
- No owner-approval inference.
- No portfolio addition.
- No watchlist promotion/demotion or watchlist mutation.
- No sizing, sleeve, cash, risk-rule, or execution-entitlement change.
- No canonical finance mutation.
- No probability, win-rate, expected-return, or model-ranked deployment claims.

## Validation required after scope approval

1. Patch existing cron payloads through `openclaw cron edit` only.
2. Run one controlled `openclaw cron run` for the weekday job.
3. Inspect:
   - `tmp/research-freshness-opportunity-review.json`
   - `tmp/research-freshness-opportunity-review.md`
   - `tmp/small-mid-cap-regime-feed.json`
   - `tmp/small-mid-cap-regime-feed.md`
4. Confirm authority flags remain false.
