# WF73 Startup Truth Index Proposal

Status: `review_only` / review-only. No target files edited.

## Authority flags

- `review_only`: `True`
- `target_file_edited`: `False`
- `new_durable_control_surface_created`: `False`
- `destructive_cleanup_allowed`: `False`
- `config_auth_channel_service_mutation_allowed`: `False`
- `canonical_note_mutation_allowed`: `False`
- `portfolio_mutation_allowed`: `False`
- `trade_or_account_action_allowed`: `False`
- `paper_execution_authorized_by_this_artifact`: `False`
- `owner_approval_inferred`: `False`

## Rewrite goal

Convert Startup Truth Index into a route-by-task boot map that sends the main session to the smallest correct owner surface: doctrine first, Active Workflows for queue truth, owner notes for canon, current-window index/proof artifacts for generated proof, and WF71/WF72 indexes for skill/script routing.

## Diagnosis

- Startup Truth Index already has the right role and should be rewritten/compressed, not replaced.
- The current workflow list is useful but can drift behind Active Workflows; the index should summarize queue tiers and point to Active Workflows for live truth.
- The proof pointer list is long and should route through `tmp/current-window-artifacts.json` plus high-authority exception pointers instead of growing indefinitely.
- WF71 department routing and WF72 script ownership should appear as pointers/routing tables after review, not as new durable control surfaces.

## Proposed exact sections

### # Startup Truth Index

- **notes:** Keep title and purpose; add explicit no-duplicate-control-plane rule.

### ## Purpose and authority

- **exact_section_text:** ## Purpose and authority

This is the thin startup and post-compaction pickup map for Veritas. It routes to canonical owners; it does not replace them.

- `SOUL.md`, `AGENTS.md`, `USER.md`, `TOOLS.md`, and `MEMORY.md` keep their doctrine/continuity authority.
- `06. Playbooks/Active Workflows.md` owns live workflow queue state.
- Canonical finance notes own portfolio truth.
- `tmp/` artifacts own generated proof/review packets only.
- Do not create another durable boot/control-plane surface unless this file and Active Workflows cannot safely own the route.


### ## Minimum boot path

- **exact_section_text:** ## Minimum boot path

1. Confirm/read T0 doctrine/runtime surfaces: `SOUL.md`, `AGENTS.md`, `USER.md`, `TOOLS.md`.
2. Read this file.
3. Read `06. Playbooks/Active Workflows.md` for live queue truth.
4. Read/search today's and yesterday's `memory/YYYY-MM-DD.md` for material deltas.
5. In direct main sessions or prior-decision questions, read/search `MEMORY.md`.
6. Drill only into the workflow continuity note, canonical owner note, skill, or proof artifact required by the task.

For substantial workflow advancement, implementation, broad inspection, helper-lane spawning, or independent QA, also read `06. Playbooks/Automation Orchestration Protocol.md` and `06. Playbooks/Spawn and Closeout Governance Matrix.md`.


### ## Always-load vs route-by-task

- **exact_section_text:** ## Always-load vs route-by-task

| Load class | Surface | Use | Notes |
|---|---|---|---|
| Always / if not already present | `SOUL.md` | Identity, mission, finance hard boundaries | Do not rewrite without proven conflict and review. |
| Always / if not already present | `AGENTS.md` | Startup, orchestration, action boundaries | Governs helper-lane default and response shape. |
| Always / if not already present | `USER.md` | Randall preferences and standing finance boundaries | Owner preferences do not bypass hard safety/finance boundaries. |
| Always / if not already present | `TOOLS.md` | Runtime/tool/Windows/config posture | Ask before config/auth/channel/service/runtime mutation. |
| Always for startup/recovery | Startup Truth Index | Route to smallest correct owner surface | This file is an index, not truth replacement. |
| Always for live work | `Active Workflows.md` | Queue/status/next action truth | If workflow state conflicts, Active Workflows wins over this index. |
| Usually direct-main / targeted | `memory/YYYY-MM-DD.md`, `MEMORY.md` | Recent deltas and durable decisions | Use search/excerpts when possible; do not treat memory as fresher than owner notes. |
| Route-by-task | Workflow continuity note | Resume state for named workflow | One note per active workflow. |
| Route-by-task | Canonical finance notes | Portfolio/research/macro truth | Generated proof supports but does not replace canon. |
| Route-by-task | Skills | Specialized procedure | Load exactly one applicable skill first; do not load finance spine by habit. |
| Route-by-task | `HEARTBEAT.md` | Heartbeat-only behavior | Do not advance queue from heartbeat. |


### ## Current queue routing

- **exact_section_text:** ## Current queue routing

Use Active Workflows for exact live status. Current routing snapshot:

| Tier | Route | Owner surface | Default drill-in |
|---|---|---|---|
| P0 primary goal | WF68 advisor/intraday alerting | Active Workflows row + WF68 continuity | `tmp/intraday-alerts/*`, router/handoff proof, capital recommendation packet, WF67 guardrail if paper action is discussed |
| P1 OS control plane | WF72/WF73/WF71 | Active Workflows rows + WF72/WF73/WF71 continuity | `tmp/wf72-phase1-integration-packet.*`, `tmp/wf73-*`, `tmp/wf71-*` |
| P1 official evidence spine | WF70/WF66/WF65 | Continuity notes + current-window index | official IR captures, reconciliation packets, official earnings bridge validators |
| P1/P2 guarded portfolio/canon | WF64/WF56/WF58/WF62 | Execution Board/Snapshot/Coverage owner notes + proof artifacts | semantic preview/apply artifacts, capital recommendation validator, dashboard validation |
| P1/P2 paper simulation | WF63/WF67 | WF63/WF67 continuity + guardrail note | paper readiness report, kill switch, scoped request, guard validation, audit log |
| P2 research/macro monitors | WF60/WF61/WF65 | Active Workflows + generated proof | research freshness packet, small/mid feed, fundamentals validation |
| P3/P4 paused/blocked | Paused and blocked tables | Active Workflows | Ask/stop before owner/operator-gated actions |


### ## Department and skill routing

- **exact_section_text:** ## Department and skill routing

Source after review: `tmp/wf71-department-skill-ownership-proposal.json`. Until promoted, treat it as proposal-only.

Minimal main-session routing set:
- `veritas-response-contract` for owner-facing closeout/status/recommendations.
- `ic-swarm-orchestrator` for multi-lane worker/QA orchestration.
- `project-continuity-manager` for workflow pickup state.
- `memory-continuity-manager` for daily/durable memory routing.
- `openclaw-operator` for runtime/control-plane tasks.

Department route examples:
- Official-source/SEC/company evidence -> Official Source Desk / `sec`.
- Portfolio/canon/gated maintenance -> Portfolio / Canon Steward.
- Intraday alerts -> Advisor Alert Desk.
- Paper-only execution guardrails -> Risk and Paper Execution Guard / `wf67-paper-trading-operator`.
- Implementation/refactor -> Implementation / Refactor Desk; use independent QA when risk warrants.

Negative route rule: do not load specialist finance or external/bundled skills by habit; load only when the task trigger is explicit.


### ## Script and artifact routing

- **exact_section_text:** ## Script and artifact routing

Source after review: `tmp/wf72-script-ownership-inventory.json`. Keep `scripts/` root as compatibility CLI surface unless/until a reviewed module-boundary migration preserves old command names.

- Start proof lookup with `tmp/current-window-artifacts.json` / `.md`.
- For finance-chain state, inspect `tmp/run-summary-<window>.json` and the named validator artifact before claiming readiness.
- High-authority script surfaces (paper execution, portfolio apply, canon sync, scheduler/dashboard chain files) are no-delete/gated-review paths.
- Archive candidates are review-only; reference checks and owner approval are required before move/delete/archive.
- New scripts/helpers must pass the reuse-before-new-script gate in `Automation Orchestration Protocol.md`.


### ## Canonical finance truth route

- **exact_section_text:** ## Canonical finance truth route

Use these owner notes for finance claims:

- Execution state, bands, stops, repair state: `03. Portfolio/Execution Board.md`
- Portfolio posture/model weights: `03. Portfolio/Portfolio Snapshot.md`
- Research universe/thesis/watchlist membership: `04. Research/Coverage and Watchlist.md`
- Risk rules: `07. Risk/Risk Rules.md`
- Weekly operating map: `05. Intelligence/Weekly Positioning Review.md`
- Macro regime: `02. Markets/Macro Regime Dashboard.md`

Generated packets, dashboards, Today card drafts, capital recommendations, validators, and proof indexes are evidence/review surfaces only.


### ## Stop lines

- **exact_section_text:** ## Stop lines

Stop or ask before:

- identity/doctrine rewrites without a proven stale/conflicting rule;
- file moves/deletes/archive/renames;
- config/auth/channel/network/service/runtime mutation;
- live brokerage/account action, money movement, or live credential/endpoint use;
- paper submit/cancel/sell outside exact WF67 scoped guardrails;
- portfolio/canon/sizing/cash/risk/execution entitlement mutation outside exact approved gated apply;
- treating generated surfaces, scores, validators, dashboards, Today cards, or recommendation packets as owner approval.



## Current-window proof lookup

- **primary_index:** tmp/current-window-artifacts.json
- **rule:** Use index for existence/freshness routing only; inspect target artifact before making content claims.
- **high_authority_exceptions_to_name_directly:** `["tmp/alpaca-paper-readiness/paper-execution-guard-validation.json", "tmp/alpaca-paper-readiness/kill-switch.json", "tmp/portfolio-mutation-proposals/current-capital-deployment-recommendations.json", "tmp/capital-deployment-recommendation-validation.json", "tmp/dashboard-validation.json", "tmp/run-summary-morning.json", "tmp/run-summary-post-close.json"]`

## Acceptance checks after apply

- Startup Truth Index no longer duplicates long live workflow history; it routes to Active Workflows.
- Always-load vs route-by-task is explicit.
- Department/skill and script indexes are proposal pointers unless reviewed/promoted.
- Current-window proof lookup is simplified without dropping high-authority exception links.
- Stop lines remain at least as strict as SOUL/AGENTS/USER/TOOLS.

## Recommended next action

After main review, apply this as an in-place Startup Truth Index rewrite and then run a link/path spot-check against Active Workflows, WF71/WF72/WF73 artifacts, and current-window proof surfaces.
