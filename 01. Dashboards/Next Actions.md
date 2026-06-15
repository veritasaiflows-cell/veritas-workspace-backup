# Next Actions

## Status

This dashboard has been **retired as an independent action queue**.

Reason: the live system now has better, lower-drift action surfaces:
- Command Center / generated daily artifacts for current operating status
- Daily Executive Summary, pre-market, and post-close packets for daily market-cycle actions
- [[06. Playbooks/Active Workflows]] for workflow truth and queue movement
- [[05. Intelligence/Weekly Positioning Review]] for weekly strategy posture
- [[03. Portfolio/Execution Board]], [[03. Portfolio/Portfolio Snapshot]], [[04. Research/Coverage and Watchlist]], and [[07. Risk/Risk Rules]] for finance truth

## What to use instead

If you need the next action, use this order:

1. **Live finance status:** `tmp/full-portfolio-view.*`, `tmp/current-window-artifacts.*`, `tmp/deployment-readiness-surface.json`, and the latest run summary.
2. **Daily decision card:** Daily Executive Summary / pre-market / post-close review packets.
3. **Workflow queue:** [[06. Playbooks/Active Workflows]].
4. **Weekly lens:** [[05. Intelligence/Weekly Positioning Review]].
5. **Portfolio truth:** [[03. Portfolio/Execution Board]], [[03. Portfolio/Portfolio Snapshot]], [[04. Research/Coverage and Watchlist]], [[07. Risk/Risk Rules]].

## Boundary

This file no longer owns priorities, ticker state, workflow order, or capital-deployment language.

No trade, portfolio mutation, deployment, sizing, cash, sleeve, execution-entitlement, account action, or owner approval is inferred here.

## Last updated

- 2026-05-14 — converted to a pointer/stub after Randall approved reducing duplicate dashboard truth layers.
- 2026-05-14 — runtime-event check: no independent action queue restored. Active workflow truth remains [[06. Playbooks/Active Workflows]]: WF58/WF56 scheduled proof monitoring is the operational lane, WF62 is implemented/monitoring, WF55 remains the probability-readiness prerequisite, and the latest sector-diversification research outputs are review-only research inputs rather than action authority.
