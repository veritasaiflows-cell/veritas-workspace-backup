---
name: wf67-paper-trading-operator
description: Operate or harden Randall's Alpaca paper-only trading lane. Use when creating, validating, submitting, canceling, selling, reconciling, or reporting WF67 paper-trade requests, advisor-derived paper buy/sell packages, paper feedback ledgers, kill switches, audit logs, or Alpaca paper guardrails.
---

# WF67 Paper Trading Operator

## Purpose

Run the Alpaca **paper-only** execution lane as a bounded simulation system. This skill never authorizes live trading, live endpoints, live credentials, money movement, account setting changes, close-position/liquidation endpoints, or promotion of paper results to live deployment.

Current standing approval:
- 2026-05-17: Randall approved Alpaca paper-only submit/cancel under WF63/WF67 guardrails.
- 2026-05-19 21:23 MST: Randall approved advisor-derived paper buy/sell packages during or after market hours with main-session capital-package notification.
- 2026-05-20 21:37 MST: Randall approved paper-trading-only full paper trading abilities when Randall approves the exact order; current validated executable scope is limit/market day orders and limit/GTC orders only.

## Read first

- `SOUL.md`, `AGENTS.md`, `USER.md`, `TOOLS.md` for hard finance boundaries.
- `07. Risk/Alpaca Paper Trading Guardrails.md`.
- `06. Playbooks/Project Continuity/Workflow 67 - Alpaca Paper Execution Guardrail.md`.
- `06. Playbooks/Project Continuity/Workflow 68 - Intraday Alert Engine and Advisor Surface.md` when the order comes from an intraday advisor packet.
- `tmp/alpaca-paper-readiness/phase-7-advisor-paper-execution-approval-2026-05-19.json` for the current advisor-derived paper buy/sell authority.

## External best-practice basis

Use these as supporting principles, not as authority to widen scope:
- Alpaca paper docs: paper trading is a simulation, not a substitute for live trading; paper and live use different API keys/endpoints; fills may differ from live due to market impact, slippage, order queue position, fees/dividends, and liquidity assumptions.
- Alpaca order docs: simple equity orders support buy/sell, market/limit, and day TIF; extended-hours execution requires explicit fields and is not part of the default WF67 lane.
- FIA automated-trading controls: pre-trade risk checks, system safeguards, post-trade analysis, and conformance/testing matter even for automated systems.
- FCA/Deloitte governance pattern: keep governance, pre-trade controls, kill switches, monitoring, change control, documentation, and human oversight visible.
- ClawHub scouting on 2026-05-19 found potentially relevant external skill categories (`trade-executor`, `permissions-broker`, `agent-audit-log`, `audit-log-firewall`, `paper-trader`), but no unaudited finance skill should be installed or imported automatically.

## Allowed paper-only actions

Only under WF67 guardrails:
- create advisor/capital-derived paper order package
- submit scoped paper buy order through `scripts/alpaca_paper_trade_executor.py`
- submit scoped paper sell order through the same wrapper
- cancel scoped paper order through the same wrapper
- read/reconcile paper account/orders/positions
- update paper feedback ledgers and main-session capital-package notification artifacts

Required endpoint: `https://paper-api.alpaca.markets`.
Forbidden endpoint: the live Alpaca endpoint (`https://` + `api.alpaca.markets`).
Credential names must remain paper-specific: `ALPACA_PAPER_API_KEY_ID`, `ALPACA_PAPER_API_SECRET_KEY`.

## Blocked actions

Stop immediately if any path implies:
- live endpoint, live credentials, live order, live brokerage/account action
- money movement or account settings mutation
- close-position, liquidation, replacement, PATCH, PUT, transfer, or unwrapped POST/DELETE paths
- short sales, margin, leverage, options, crypto, multi-leg/bracket/OCO/OTO orders unless separately scoped and validated
- canonical portfolio/cash/risk-rule/sleeve/sizing mutation from a paper packet
- owner approval inferred from alert severity, score, validation, ranking, paper fill, or packet quality
- probability, win-rate, expected-return, calibrated-score, or model-readiness claims while WF55 is NOT_READY

Plain English: a paper sell is allowed only as a normal scoped paper sell order through POST `/v2/orders`; do not use close-position or liquidation endpoints.

## Pre-submit checklist

Before any `--execute` submit/cancel/sell:
1. Confirm the source package:
   - advisor packet, capital packet, explicit owner instruction, or existing scoped pilot artifact
   - exact ticker, side, quantity/notional, order type, TIF, rationale, and risk check
2. Confirm order scope:
   - side is `buy` or `sell`
   - order type is `limit` or `market`
   - TIF is `day` or validated paper-only `gtc`
   - `gtc` is allowed only for `limit` orders; market/GTC is blocked
   - market orders have explicit owner-approval field in the request artifact
   - default pilot cap remains `qty <= 1` and estimated notional `<= $500` unless a validated full-scope artifact exists
3. Run dry-run/validation first:
   - `python scripts\alpaca_paper_trade_executor.py --request <request> --dry-run-output <path>`
   - `python scripts\alpaca_paper_execution_guard_validator.py --output tmp\alpaca-paper-readiness\paper-execution-guard-validation.json`
4. Create/verify a fresh short-lived kill switch only for the narrow execution window.
5. Re-run guard validation; require clean status or a clearly non-safety warning accepted in the main session.
6. Execute only through the WF67 wrapper and exact paper endpoint.
7. Write/review redacted audit log and execution result.
8. Notify main session with a capital-package status: ticker, side, qty/notional, order type/TIF, source artifact, guard status, kill-switch expiry, result, and next risk check.

### Request artifact generation helper

Use this helper to convert a WF68 advisor packet into an exact WF67 request artifact before any kill switch or execution:

```powershell
python scripts\wf67_advisor_paper_request_generator.py --ticker ETN --side buy --qty 1 --order-type market --market-order-owner-approved --max-notional-usd 500 --max-loss-usd 500 --owner-or-pilot-scope "advisor-derived ETN paper package" --output tmp\alpaca-paper-readiness\paper-trade-request.<id>.json
```

Plain English: this only writes the package. It does not contact Alpaca, does not create a kill switch, and cannot execute. The output must still pass WF67 dry-run/guard validation and then a fresh short-lived kill switch must be created only when execution is actually intended.

### Main-session order-card helper

When Veritas main session makes the recommendation itself from a fresh capital/advisor alert, use an approval-ready order card before any execution window:

```powershell
python scripts\wf67_order_card_request_generator.py --card tmp\alpaca-paper-readiness\order-card.<id>.json --output tmp\alpaca-paper-readiness\paper-trade-request.<id>.json
```

Plain English: the order card states the exact proposed ticker, side, quantity/notional, order type, time-in-force, limit price if any, sizing rationale, band/stop evidence, source artifacts, and approval status. The generator only writes a WF67 request artifact; it does not contact Alpaca, create a kill switch, or execute. Pending-approval request artifacts are blocked from `--execute`; execution requires Randall's exact approval metadata, a fresh short-lived kill switch, rerun guard validation, and the WF67 wrapper.

## Post-action reconciliation

After submit/cancel/sell:
- reconcile order/position state through read-only paper APIs or existing reconciliation scripts
- update `tmp/alpaca-paper-readiness/paper-trading-feedback-ledger.*` when a fill or material state change occurs
- preserve append-only outcome/feedback records; do not rewrite thesis-after-the-fact
- if a paper outcome should later feed WF55, create a proposal/sidecar artifact first; do not claim predictive performance

## Cron / WF68 handoff behavior

When a WF68 alert creates an advisor opportunity:
- WF68 may generate/recommend a WF67 paper package, but does not execute itself
- main-session handoff should report `ALERT_READY`, blockers, or exact `NO_REPLY`
- capital-package notifications should be concise and include proof paths
- if guard validation is blocked by expired kill switch outside execution window, that is safe and expected; refresh only when an actual scoped paper action is ready

## Output contract

For any paper-action report, include:
- conclusion: ready / executed / blocked / no action
- paper/live boundary status
- source package and request artifact
- guard validation and kill-switch status
- order/result/reconciliation proof
- remaining risk or next action
