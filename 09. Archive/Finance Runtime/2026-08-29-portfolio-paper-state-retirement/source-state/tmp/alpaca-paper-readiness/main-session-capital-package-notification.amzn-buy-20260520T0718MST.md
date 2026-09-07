# WF67 AMZN Paper Capital Package Notification

Status: **submitted**
Generated: `2026-05-20T14:30:29Z`

## Order
- Symbol: `AMZN`
- Side / qty: `buy` / `1`
- Type / TIF: `limit` / `day`
- Limit price: `262.04`
- Broker redacted status: `pending_new`
- Paper order id present: `true`

## Validation
- Dry run: `validated_dry_run`
- Pre-submit guard: `ok` / critical `0` / warning `0`
- Post-submit guard: `ok` / critical `0` / warning `0`
- Credential status: `ok`
- Kill switch status: `ok`

## Boundary
Paper-only simulation. No live trading, live endpoint, live credentials, money movement, account mutation, portfolio/canonical mutation, raw broker body persistence, secret persistence, or inferred owner approval.

## Artifacts
- Request: `tmp/alpaca-paper-readiness/paper-trade-request.wf67-advisor-amzn-buy-limit-20260520T0718MST.json`
- Execution result: `tmp/alpaca-paper-readiness/paper-execution-result.amzn-buy-20260520T0718MST.json`
- Post-submit guard validation: `tmp/alpaca-paper-readiness/paper-execution-guard-validation.amzn-buy-post-submit-20260520T0718MST.json`
