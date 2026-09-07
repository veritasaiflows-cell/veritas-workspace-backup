# NVDA Paper Execution Closeout - 2026-06-18

## Result

- Paper order submitted through the WF67 paper-only wrapper.
- Broker response: HTTP 200.
- Submit-time broker status: `pending_new`.
- Current order-history classification: `filled`.
- Current broker order status from GET-only reconciliation: `filled`.
- Filled quantity: `0.71851497`.
- Filled average price: `$208.75`.
- NVDA paper position observed: `true`.

## Exact Approved Order

- Ticker: `NVDA`
- Side: `BUY`
- Type/TIF: `limit/day`
- Notional: `$150`
- Limit: `$208.75`
- Owner approval: Randall Telegram message `3639`

## Pre-Submit Context

- Fresh quote checked before submit: `$209.15`
- Quote source: `yfinance_fast_info`
- Checked at UTC: `2026-06-18T15:27:30Z`
- Written band: `$191.15-$212.77`
- Stop/invalidation: `$181.33`
- Band status: `IN_BAND`
- Estimated max loss to stop on `$150` notional: about `$19.70`

## Guard Proof

- Dry run: `validated_dry_run`
- Execution guard: `ok`
- Critical findings: `0`
- Warning findings: `0`
- Endpoint: `https://paper-api.alpaca.markets`
- Live endpoint detected: `false`
- Live trading allowed: `false`
- Money movement allowed: `false`
- Account settings mutation allowed: `false`
- Raw broker response bodies, headers, and secrets persisted: `false`

## Reconciliation

- Read-only paper snapshot at UTC: `2026-06-18T15:31:01Z`
- Open orders count: `0`
- Positions count: `9`
- Order-history classifier generated at UTC: `2026-06-18T15:30:51Z`
- NVDA classification: `filled`
- Filled at UTC: `2026-06-18T15:29:27.41013Z`
- Position quantity: `0.71851497`
- Position average entry price: `$208.75`
- Position current price: `$209.065`
- Position market value: `$150.216332`
- Position unrealized P/L: `$0.226332`

## Boundary

This closeout records one exact owner-approved paper-only order. It does not authorize any additional submit, cancel, replace, sell, live trade, money movement, account action, portfolio/canon mutation, or inferred approval.

Next safe action: record the filled paper-order outcome and monitor read-only. Any sell requires exact Randall approval and fresh WF67 guard proof.
