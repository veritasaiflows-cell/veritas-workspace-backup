# Startup Truth Index

Thin startup/post-compaction pickup map. It routes to canonical owners; it does not replace them.

## Authority

- `SOUL.md`, `AGENTS.md`, `USER.md`, `TOOLS.md`, and `MEMORY.md` keep doctrine/runtime/continuity authority.
- `06. Playbooks/Active Workflows.md` owns live queue state; workflow continuity notes own resume detail.
- Canonical finance notes own portfolio truth. `tmp/` artifacts own generated proof/review packets only.
- Do not add durable boot/control surfaces unless this file and Active Workflows cannot own the route.

## Minimum Boot Path

1. Confirm T0 surfaces: `SOUL.md`, `AGENTS.md`, `USER.md`, `TOOLS.md`.
2. Read this file and `06. Playbooks/Active Workflows.md`.
3. Read/search today's and yesterday's `memory/YYYY-MM-DD.md`; read/search `MEMORY.md` for direct main-session or prior-decision questions.
4. For future-session/post-compaction handoff, refresh or inspect `tmp/future-session-enhancement-packet.json`.
5. For named workflows, use `workflow_router.py WF## --answer summary` or fresh `state/workflows/WF##.json`; use `workflow_routing_index.py` for rebuild/drilldown only.
6. Use SQL/workspace indexes for proof routing, then drill only into exact owner notes, continuity notes, skills, or artifacts needed for the task.

For simple direct-session greetings or shallow status checks, use `startup_brief_packet.py --write --validate` when existing PM/cron/future-session packets are fresh. It reads existing route packets only; refresh heavier packets when inputs are stale or the user asks for material status/workflow action.

For implementation/helper/QA work, read the relevant governance/skill, check `concurrent_lane_manager.py --status --write --validate`, lease exact write surfaces, tag running lanes, and close with proof. Prefer PM/WF implementation slices; repeat QA/audit only after state changes or Randall asks. Pause/resume through `workflow_control_override.py`, then refresh capsules/PM packet as needed.

## Load Map

| Surface | Use |
|---|---|
| `SOUL.md` | Identity, mission, hard finance boundaries. |
| `AGENTS.md` | Startup, orchestration, action boundaries. |
| `USER.md` | Randall preferences and standing finance boundaries. |
| `TOOLS.md` | Runtime/tool/Windows/config posture and route commands. |
| Startup Truth Index | Smallest correct owner route. |
| Active Workflows | Queue/status/next-action truth. |
| `memory/YYYY-MM-DD.md`, `MEMORY.md` | Recent deltas and durable decisions. |
| `workflow_router.py`, `state/workflows/*.json` | Fast workflow status, next action, blockers, helper safety, PM job, overrides. |
| `startup_brief_packet.py`, `tmp/startup-brief-packet.json` | Fast simple-greeting/status summary from existing packets; no control-packet regeneration. |
| `pm_control_packet.py`, `tmp/pm-control-packet.json` | PM state/queue/heartbeat/handoff; use stale-lane digest for yellow state. |
| `cron_control_packet.py`, `tmp/cron-control-packet.json` | Cron freshness/scorecard/escalation; drill only on attention/stale/blocker. |
| `wf73_control_plane_audit.py`, `tmp/wf73-control-plane-audit.json` | Ordered WF73 audit and warning classification. |
| `artifact_index.py`, `tmp/veritas-artifact-index.sqlite` | Generated artifact/proof lookup. |
| `changed_file_validator_router.py` | Smallest honest validator budget for current changes. |
| `future_session_enhancement_packet.py` | Thin startup packet for PM, cron, WF74, workflow, memory, route commands, improvement-ledger state, stop lines. |
| `improvement_ledger.py`, `tmp/improvement-ledger-current.json`, `data/state-history/improvement-ledger.jsonl` | Durable append-only improvement carry-forward ledger plus current open recommendations. Load in new sessions before recommending OS/WF74 improvements. |
| `token_usage_ledger.py`, `tmp/token-usage-ledger-current.json`, `data/state-history/token-usage-ledger.jsonl` | Metadata-only token usage ledger for ranking token-heavy cron jobs and implementation attribution gaps. Cost fields require a local pricing table. |
| `otel_ops_control.py`, `tmp/otel-ops-control.json`, `tmp/otel-ops-window-summary.json`, `tmp/otel-ops.sqlite` | Local OTEL digest and multi-window operational summary. |
| Workflow continuity notes | Resume state for named workflow. |
| Canonical finance notes | Portfolio/research/macro truth. |
| Skills | Specialized procedure. |
| `HEARTBEAT.md` | Heartbeat behavior only. |

## Queue Routing

Use `workflow_router.py` / capsules first, then Active Workflows or continuity notes only when source detail is needed.

| Route | Drill-in |
|---|---|
| Personal Trade-Grade Decision OS/WF85 | WF85 continuity, WF84 data plane, WF78 repair/freshness inputs, WF67 paper guard context, trade-grade artifacts. Current primary PM/workflow goal after Randall's 2026-06-09 pivot. |
| Autonomous paper OS/WF86-WF87 | WF86/V2 continuity, WF85/WF78 inputs, WF67 guard proof, `tmp/paper-autotrader/*`, V2 rollup, command center. Phase A hardening is built; critical path is shadow/reconciliation maturity, fresh WF67 guard/kill-switch proof, and exact owner approval. |
| Retail/WF75 | Paused as primary work on 2026-06-09; use for historical/internal proof or if Randall resumes SaaS/service-state work. |
| Command center/WF79 | WF79 continuity, PM cockpit, source registry, entry-band/deployment/technical views. |
| OS/control plane | WF72 support/cache/index continuity, WF73/WF71/WF76 continuity, A2 read guard, artifact indexes, PM/heartbeat/cron selectivity. |
| Finance truth/evidence | Canonical finance notes, WF64/WF56/WF58/WF62, WF70/WF66/WF65, WF77/WF78 artifacts. |
| Alerts/paper | WF68 for alerts/advisor; WF63/WF67 for paper simulation. |
| Product scaleout | WF80-WF83 hold/resume-later; public/customer/external action gated. |
| Paused/blocked | Active Workflows paused/blocked tables; stop before gated action. |

## Department And Skill Routing

- Closeout/status -> `veritas-response-contract`; workflow pickup -> `project-continuity-manager`; memory -> `memory-continuity-manager`.
- Worker/QA -> `ic-swarm-orchestrator`; implementation/refactor -> `disciplined-implementation`, `safe-refactor-planner`, QA when warranted.
- Serious finance challenger gates -> use `claude-cli/claude-opus-4-8` when available and verify actual subagent model path; labels are not proof.
- Runtime/control -> `openclaw-operator` / `openclaw-troubleshooter`; SEC/company evidence -> `sec`; paper guardrails -> `wf67-paper-trading-operator`.

## Script And Artifact Routing

- Workflow routing: `workflow_router.py WF## --answer summary|next|blockers|helper|all`; refresh capsules with `workflow_router.py --all --write-capsules --validate`.
- Fast startup greeting/status: `startup_brief_packet.py --write --validate`; use existing packets first, then drill only if stale or material.
- WF73 full audit: `wf73_control_plane_audit.py --write --validate`; use instead of parallel producer/consumer validation batches.
- Future-session packet: `future_session_enhancement_packet.py --write --write-md --validate`.
- Artifact cockpit: `artifact_index.py cockpit|ticker-cockpit|trust-cockpit|proof-field|stoplines|validate`.
- Concurrent helper work: `concurrent_lane_manager.py --status --write --validate`; lease exact files, tag running lanes, and close with proof. Coordination-only; default to implementation-first parallelism, then QA/audit after state changes or disputed trust.
- Finance questions: `finance_intelligence_state.py ticker <TICKER> --pretty` first; route is finance-state -> WF84 data plane -> WF85 full answer/card when guard-clean, with source-open fallback when stale. Open exact source artifacts/owner notes before material claims.
- WF78 routing: use WF78 capsule/front doors as non-capital repair/promotion feeders for WF84/WF85; drill into freshness, resolver, ledger, action scorer, confidence gate, queue, and event artifacts as needed.
- WF84: `workflow_router.py WF84 --answer all`, `canonical_finance_data_plane.py --write --write-db --validate`, and phase 6-10. Internal/personal proof only.
- WF85: `workflow_router.py WF85 --answer all`, freshness runner, decision cards, full-answer assembler, and repair conveyor. No generated card/score/SQL row/draft is approval.
- PM/cron/OTEL/improvements/tokens: inspect `tmp/pm-control-packet.json`, `tmp/cron-control-packet.json`, `tmp/improvement-ledger-current.json`, `tmp/token-usage-ledger-current.json`, `tmp/otel-ops-control.json`, and `tmp/otel-ops-window-summary.json` first; drill into components only when needed. For improvement recommendations, prefer `data/state-history/improvement-ledger.jsonl` plus the current packet over chat history. For token/cost work, use token counts as factual and leave dollar cost null until a local pricing table exists.
- Validation selection: run `changed_file_validator_router.py --write --validate`; use `validator_timing_ledger.py --profile normal` for timing proof.
- Product scaleout: WF80-WF83 hold/resume-later; if restarted, use `workflow_router.py WF80|WF81|WF82|WF83 --answer all`.
- Archive candidates are review-only; reference checks and owner approval are required before move/delete/archive.
- New scripts/helpers must pass reuse-before-new-script and system-aware implementation gates.

## Finance Truth Route

Canonical finance truth lives in Execution Board, Portfolio Snapshot, Coverage/Watchlist, Risk Rules, Weekly Positioning Review, and Macro Regime Dashboard. Generated packets, SQL, and proof indexes are review surfaces only. WF78 auto-tier artifacts are non-capital routing, not deployment/execution authority.

Macro route: use current macro metrics, energy supply, geopolitical sweep, and judgment draft artifacts before deeper logs. Review-only; no forecast, canon/portfolio mutation, capital deployment, paper/live execution, or approval authority.

## Stop Lines

Stop or ask before identity/doctrine rewrites, moves/deletes/archive/renames, config/auth/channel/network/service/runtime mutation, brokerage/account action, money movement, live endpoint use, paper submit/cancel/sell outside WF67, capital deployment, trade/order execution, portfolio/canon/sizing/cash/risk mutation outside exact approved gates, or treating generated surfaces as approval. Do not stop for ordinary validated non-capital ticker/tier routing.

## Startup Behavior Rule

After compaction, use this file plus `workflow_router.py`/capsules before broad vault reads. Drill into full files only for the current task.
