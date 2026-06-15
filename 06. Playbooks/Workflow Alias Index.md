# Workflow Alias Index

This is a lightweight routing map for human-friendly workflow names.

## Rules

- Keep `WF##` IDs stable. They are durable references for files, history, scripts, and proof.
- Use display names and aliases for conversation, handoffs, and `Continue <name>` routing.
- Do not rename workflow files from this index alone. File renames need reference checks and a separate migration packet.
- Active Workflows remains the live queue authority. This index is a router, not workflow state.
- Generated artifacts and aliases grant no finance, approval, canon, paper, live trading, account, or mutation authority.

## Active Alias Map

| ID | Display name | Primary aliases | Owner route |
|---|---|---|---|
| WF68 | Advisor Alert Engine | advisor alerts, intraday alerts, alert engine, trade-ready alerts | Active Workflows + WF68 continuity |
| WF70/WF66 | Official Evidence Spine | official evidence, company source capture, evidence bridge, earnings evidence | Active Workflows + WF70/WF66 continuity |
| WF72 | Finance OS Efficiency | finance OS restructure, OS efficiency, SQL metadata cache, archive flattening | Active Workflows + WF72 continuity |
| WF73 | Queue and Startup Router | queue optimization, startup router, boot thinning, control surface compression | Active Workflows + WF73 continuity |
| WF71 | Department Skill Model | staff model, department routing, skill ownership, helper lane routing | Active Workflows + WF71 continuity |
| WF74 | Self-Improvement Loop | recursive improvement, RSI loop, improvement gates, Veritas self-improvement | Active Workflows + WF74 continuity |
| WF75 | Retail Investor Finance Intelligence SaaS | retail SaaS, finance SaaS, retail investor SaaS, finance intelligence SaaS, investor intelligence product, SaaS readiness | Active Workflows + WF75 continuity |
| WF77 | Finance Question Router | ticker cards, finance coverage, answer contracts, ticker intelligence router | Active Workflows + WF77 continuity |
| WF78 | Finance Intelligence Scaleout | finance scaleout, 500 ticker scaleout, ticker scaleout, provider proof, pilot fixtures | Active Workflows + WF78 continuity |
| WF84 | Trade-Grade Personal Finance OS Canonical Data Model | finance OS data model, canonical finance model, canonical finance data plane, trade-grade OS model, personal finance data plane | Active Workflows + WF84 continuity |
| WF85 | Trade-Grade Decision and Approval Card OS | decision OS, approval card OS, trade-grade decision cards, decision card plane, personal finance decision plane | Active Workflows + WF85 continuity |
| WF79 | Veritas Command Center V2 | command center v2, command center, veritas command center, UI infrastructure, entry band tool, deployment board, technical tab | Active Workflows + WF79 continuity |
| WF67 | Paper Trading Guardrails | paper guardrails, paper execution guard, Alpaca paper guard, paper order safety | Active Workflows + WF67 continuity |
| WF63 | Paper Trading Readiness | Alpaca readiness, paper position state, paper holdings freshness | Active Workflows + WF63/WF67 continuity |
| WF60/WF61 | Research Opportunity Radar | research freshness, opportunity radar, sector expansion, small mid cap feed | Active Workflows + WF60/WF61 proof |
| WF76 | Cron Authority Hardening | cron authority, canon auto-update guardrails, scheduled apply guard | Active Workflows + WF76 continuity |
| WF69 | Prediction Stack Revamp | probability stack, predictive analytics, outcome readiness | Active Workflows + WF69 continuity |

## Paused Or Gated Aliases

| ID | Display name | Primary aliases | Route |
|---|---|---|---|
| WF37 | Daily Commercial Brief | daily summary, commercial brief, daily brief hardening | Active Workflows paused table |
| WF44/WF45 | Dashboard Truth Alignment | command center truth, stale source classifier, dashboard drift | Active Workflows paused table |
| WF49 | FRED Runtime Persistence | FRED credentials, FRED runtime, macro data runtime | Active Workflows gated table |
| WF50 | Archive Residue Cleanup | tmp cleanup, archive residue, helper archive | Active Workflows gated table |

## Continue Routing

Use this order when Randall says a plain-English `Continue` command:

1. If the message includes a `WF##`, use that workflow ID.
2. If the message includes an alias from this file, route to that workflow.
3. If the message is only `Continue`, read `tmp/handoff-current.json` first.
4. If `tmp/handoff-current.json` is missing or stale, read Active Workflows and today's daily memory before choosing a workflow.
5. If more than one workflow matches, ask the smallest concrete question or choose the current P0/P1 handoff when the packet is unambiguous.

## Current Default

As of the 2026-05-29 08:22 MST handoff update, the explicit default `Continue` handoff is:

- `WF75 - Retail Investor Finance Intelligence SaaS`
- Handoff packet: `tmp/handoff-current.json`
- Human summary: `tmp/handoff-current.md`
- Next action: build anonymous service request scenarios, service-state storage, operator queue/status, renderer/export, QA regression, and executable no-leak/no-claim-overreach validators before any real customer intake, external delivery, portfolio import, app build, or public launch.
