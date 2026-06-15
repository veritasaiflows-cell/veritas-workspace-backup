# ClawHub / Web Skill Scout - WF67 Paper Trading Posture

Generated: 2026-05-19 22:05 MST / 2026-05-20 UTC

## Purpose

Scout external skill ideas and public best-practice patterns for Randall's expanded paper-only Alpaca posture, then encode the useful parts locally without installing unaudited finance skills.

## ClawHub search findings

Commands run:
- `clawhub search "paper trading"`
- `clawhub search "trading risk management"`
- `clawhub search "broker api"`
- `clawhub search "risk controls"`
- `clawhub search "audit log"`

Relevant candidate categories found:
- Trading/execution: `trade-executor`, `auto-trading-strategy`, `trading`, `paper-trader`, `kalshi-paper-trading`.
- Permissions/control: `permissions-broker`, `registry-broker-skills`.
- Audit/logging: `agent-audit-log`, `audit-log-firewall`, `openclaw-audit-log-hook`, `transparency-log-auditor`, `openclaw-ledger`.
- Security/hardening: `huamu668-openclaw-security`, `vps-openclaw-security-hardening`, `openclaw-config-guardian`.

Decision: do not install any unaudited third-party finance/trading skill automatically. Use the patterns locally: explicit permissions, audit logging, narrow execution wrapper, and fail-closed guard validation.

## Web best-practice findings

Sources inspected:
- Alpaca paper trading docs: paper trading is simulation; paper/live use different API keys and endpoint; paper fills differ from live because of market impact, slippage/latency, queue position, fees/dividends, and liquidity assumptions.
- Alpaca order docs: equity orders support buy/sell, market/limit, day TIF; extended-hours execution requires explicit fields and is not part of default WF67.
- FIA automated trading risk controls: pre-trade risk checks, system safeguards, post-trade analysis, and conformance/testing.
- Deloitte/FCA governance summary: governance, pre-trade controls, kill switches, monitoring, change control, documentation, and human oversight.

## Local changes made

Created:
- `skills/wf67-paper-trading-operator/SKILL.md`

Updated:
- `skills/veritas-bounded-portfolio-agent/SKILL.md`
- `skills/veritas-response-contract/SKILL.md`
- `skills/cron-automation-manager/SKILL.md`
- `TOOLS.md`
- WF68 handoff cron payload `a6b30d94-9223-4760-9e8e-e83417708b38` to name `wf67-paper-trading-operator` when a paper package is involved.

## Encoded guardrail themes

- Paper-only endpoint: `https://paper-api.alpaca.markets`.
- Live endpoint remains forbidden: `https://api.alpaca.markets`.
- Separate paper credentials only.
- Scoped request artifact before any action.
- Fresh short-lived kill switch.
- Pre-trade guard validation.
- Redacted append-only audit logging.
- Main-session capital-package notification.
- Paper sell is a normal scoped sell order; no close-position/liquidation endpoint.
- Paper fills are simulation feedback, not live-deployment evidence.

## Validation

- `openclaw skills check` sees `wf67-paper-trading-operator` as ready and visible.
- Known non-blocking environment issue remains: browser plugin symlink creation reports Windows `EPERM`, while skill inventory still shows `browser-automation` ready/visible. This is a pre-existing Windows symlink privilege issue, not caused by this pass.
