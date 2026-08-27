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
| WF77 | Finance Question Router | ticker cards, finance coverage, answer contracts, ticker intelligence router | Active Workflows + WF77 continuity |
| WF78 | Finance Intelligence Scaleout | finance scaleout, 500 ticker scaleout, ticker scaleout, provider proof, pilot fixtures | Active Workflows + WF78 continuity |
| WF84 | Trade-Grade Personal Finance OS Canonical Data Model | finance OS data model, canonical finance model, canonical finance data plane, trade-grade OS model, personal finance data plane | Active Workflows + WF84 continuity |
| WF85 | Trade-Grade Decision and Approval Card OS | decision OS, approval card OS, trade-grade decision cards, decision card plane, personal finance decision plane | Active Workflows + WF85 continuity |
| WF88 | Veritas OS 2.0 | veritas os 2.0, veritas learning OS, formal experiment layer, finance-call learning loop, promptable veritas, portable veritas behavior | Active Workflows + WF88 continuity |
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
| WF51 | Daily Fresh Intelligence and Price Trend Promotion Branch | price trend branch, daily price trend, fresh intelligence branch | Route-history capsule; superseded by WF78/WF84/WF85 |
| WF52 | Event Calendar Freshness Path | earnings date confidence, event calendar roll-forward, earnings calendar freshness | Route-history capsule; use active earnings/event routes for current proof |
| WF53 | Sector Expansion Coverage and Correlation Proof Layer | sector correlation proof, sector expansion coverage, correlation layer | Route-history capsule; use current macro/sector and WF78/WF84/WF85 proof |
| WF54 | Ticker Monitoring Performance Analytics v1 | monitoring analytics, performance analytics, calibration diagnostics | Route-history capsule; predictive claims gated by WF55 |
| WF57 | Composite Regime and Sector Positioning PDF Visual Enhancement | sector positioning PDF, composite regime PDF, polished PDF product | Route-history capsule; customer/public packaging remains gated |
| WF59 | Continuity and Compaction Hardening | compaction hardening, startup truth index, continuity hardening | Route-history capsule; use Startup Truth Index for live boot routing |
| WF75 | Retail Investor Finance Intelligence SaaS | retail SaaS, finance SaaS, retail investor SaaS, finance intelligence SaaS, investor intelligence product, SaaS readiness | Paused; resume only on Randall's explicit instruction, then use Active Workflows + WF75 continuity |

## Continue Routing

Use this order when Randall says a plain-English `Continue` command:

1. Parse any `WF##` or alias as requested intent, but do not let it bypass current lane validation or authorize execution.
2. Read `tmp/current-resume.json` and `tmp/current-active-lanes.json`, then run `python scripts\session_resume_checkpoint.py --validate` before opening the named workflow route.
3. Resume only when the checkpoint is fresh, validation-clean, bound to the current lane/lease, unambiguous, and compatible with the requested intent. A conflicting named target fails closed rather than replacing an active lease implicitly.
4. Reject a command when `execution_gate.replay_blocked=true`, including an exact `command:` or `action:` do-not-repeat match or any terminal execution receipt. Otherwise record exact-ID acknowledgement and execute only when `execution_gate.command_authorized=true`.
5. After a terminal result, set `$resumeId = [string](Get-Content -LiteralPath 'tmp\current-resume.json' -Raw | ConvertFrom-Json).checkpoint_id`, then run exactly one pasteable receipt command: `python -B scripts\session_resume_checkpoint.py --record-execution $resumeId --execution-status succeeded --executed-by main-session --execution-proof-artifact 'tmp\changed-file-validator-router.json' --write --validate`; use the same command with literal `failed` after a failed result. Emit the successor immediately. Re-acknowledgement never reauthorizes consumption.
6. If the checkpoint is absent, stale, blocked, ambiguous, or conflicts with requested intent, execution remains prohibited. Use this read-only discovery precedence without guessing: active leased lane checkpoint -> exact workflow checkpoint -> named workflow continuity note -> PM queue -> general status. Emit and validate a fresh lane-bound checkpoint and acknowledge its exact ID before any discovered command may execute.

## Legacy Handoff Lifecycle

- `tmp/handoff-current.json` and `tmp/handoff-current.md` are compatibility/history surfaces, not the plain `Continue` owner.
- A legacy handoff is readable only when (Randall names it or a current workflow continuity owner explicitly references it) and freshness, identity, and expiry validation all pass.
- A valid legacy handoff is context-only: convert it into a fresh canonical checkpoint before executing anything. An expired or invalid legacy handoff is unusable for resume.
- A newly emitted `tmp/current-resume.json` supersedes any older generic handoff pointer. There is no permanent default workflow for plain `Continue`.
- Missing or invalid current resume state never revives the May 2026 WF75 handoff automatically; route through the declared fallback precedence instead.
