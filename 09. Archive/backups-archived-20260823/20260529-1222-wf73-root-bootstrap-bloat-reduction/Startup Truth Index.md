# Startup Truth Index

## Purpose and authority

This is the thin startup and post-compaction pickup map for Veritas. It routes to canonical owners; it does not replace them.

- `SOUL.md`, `AGENTS.md`, `USER.md`, `TOOLS.md`, and `MEMORY.md` keep their doctrine/continuity authority.
- `06. Playbooks/Active Workflows.md` owns live workflow queue state.
- Canonical finance notes own portfolio truth.
- `tmp/` artifacts own generated proof/review packets only.
- Do not create another durable boot/control-plane surface unless this file and Active Workflows cannot safely own the route.

## Minimum boot path

1. Confirm/read T0 doctrine/runtime surfaces: `SOUL.md`, `AGENTS.md`, `USER.md`, `TOOLS.md`.
2. Read this file.
3. Read `06. Playbooks/Active Workflows.md` for live queue truth.
4. Read/search today's and yesterday's `memory/YYYY-MM-DD.md` for material deltas.
5. In direct main sessions or prior-decision questions, read/search `MEMORY.md`.
6. Use the SQL cockpit as the first proof/artifact routing layer for generated artifacts, then drill only into the workflow continuity note, canonical owner note, skill, or proof artifact required by the task.
7. For recurring inventory/review questions, classify the question before searching: coverage, missing evidence, freshness, proof, ticker intelligence, recommendation support, authority/guardrail, workflow status, or runtime/config. Route through the matching registry/index first; broad workspace search is fallback only.
8. For plain-English workflow resume commands such as `Continue finance scaleout`, use `06. Playbooks/Workflow Alias Index.md` to resolve the stable `WF##` ID. If the command is only `Continue`, read `tmp/handoff-current.json` first.

For substantial workflow advancement, implementation, broad inspection, helper-lane spawning, or independent QA, also read:
- `06. Playbooks/Automation Orchestration Protocol.md`
- `06. Playbooks/Spawn and Closeout Governance Matrix.md`
- `skills/disciplined-implementation/SKILL.md` when changing scripts, validators, manifests, workflow code, or boot/control surfaces

Implementation sync rule: when a pass changes or exposes a durable contract, authority boundary, data family, workflow state, or routing expectation, check and align the relevant startup/routing surfaces before closeout: `TOOLS.md`, this Startup Truth Index, `06. Playbooks/Active Workflows.md`, the owning workflow continuity note, the relevant skill, and the live SQL/workspace index or canon-cache surface when applicable. If one surface is stale, treat that as implementation residue to fix or log explicitly; do not normalize broad workspace search as the steady-state route.

Do not reread the full finance/navigation stack unless the task requires current finance judgment.

## Always-load vs route-by-task

| Load class | Surface | Use | Notes |
|---|---|---|---|
| Always / if not already present | `SOUL.md` | Identity, mission, finance hard boundaries | Do not rewrite without proven conflict and review. |
| Always / if not already present | `AGENTS.md` | Startup, orchestration, action boundaries | Governs helper-lane default and response shape. |
| Always / if not already present | `USER.md` | Randall preferences and standing finance boundaries | Owner preferences do not bypass hard safety/finance boundaries. |
| Always / if not already present | `TOOLS.md` | Runtime/tool/Windows/config posture | Ask before config/auth/channel/service/runtime mutation. |
| Always for startup/recovery | Startup Truth Index | Route to smallest correct owner surface | This file is an index, not truth replacement. |
| Always for live work | `Active Workflows.md` | Queue/status/next action truth | If workflow state conflicts, Active Workflows wins over this index. |
| Route-by-task | `06. Playbooks/Workflow Alias Index.md` | Plain-English workflow-name routing | Alias router only; stable `WF##` IDs and Active Workflows remain authoritative. |
| Usually direct-main / targeted | `memory/YYYY-MM-DD.md`, `MEMORY.md` | Recent deltas and durable decisions | Use search/excerpts when possible; do not treat memory as fresher than owner notes. |
| Primary artifact lookup | `scripts/artifact_index.py` + `tmp/veritas-artifact-index.sqlite` | Fast generated-artifact/proof/provenance/staging lookup | Use SQL cockpit commands first for routing; inspect target artifacts/owner notes before content claims. SQL remains derived proof/index/staging only. |
| Primary question/coverage routing | coverage registries + SQL/workspace indexes | Fast answers for "what exists / missing / stale / indexed / supportable" | Finance target: `tmp/finance-data-coverage-current.json`, ticker intelligence cards, and future `artifact_index.py data-coverage` / `ticker-card` commands. If missing, record the gap and use SQL/workspace index fallback plus exact source inspection. |
| Route-by-task | Workflow continuity note | Resume state for named workflow | One note per active workflow. |
| Route-by-task | Canonical finance notes | Portfolio/research/macro truth | Generated proof supports but does not replace canon. |
| Route-by-task | Skills | Specialized procedure | Load exactly one applicable skill first; do not load finance spine by habit. |
| Route-by-task | `HEARTBEAT.md` | Heartbeat-only behavior | Do not advance queue from heartbeat. |

## Current queue routing

Use Active Workflows for exact live status. Current routing snapshot:

| Tier | Route | Owner surface | Default drill-in |
|---|---|---|---|
| P0 primary goal | Retail Investor Finance Intelligence SaaS | Active Workflows P0 row + WF75 continuity + `tmp/handoff-current.json` | `tmp/wf75-retail-investor-saas-pivot-plan.*`, `tmp/retail-investor-finance-engine-workflow-map.*`, `tmp/retail-investor-saas-claims-stoplines-qa.*`, `tmp/retail-investor-saas-unified-workflow-plan.*`, `tmp/retail-saas-workflows-full-audit.*`, `tmp/retail-saas-fixture-demo*`, `tmp/retail-saas-customer-export-contract.json`, `tmp/retail-saas-mvp-ux-service-state-contract.json`; drill into WF77/WF78/WF70/WF66/WF68/WF67 only for engine-lane specifics |
| P1 OS control plane | WF72/WF73/WF71 | Active Workflows rows + WF72/WF73/WF71 continuity | `tmp/wf72-phase1-integration-packet.*`, `tmp/wf72-phase2-canon-sync-apply.json`, `tmp/wf73-*`, `tmp/wf71-*` |
| P1 official evidence spine | WF70/WF66/WF65 | Continuity notes + current-window index | official IR captures, reconciliation packets, official earnings bridge validators |
| P1/P2 guarded portfolio/canon | WF64/WF56/WF58/WF62 | Execution Board/Snapshot/Coverage owner notes + proof artifacts | semantic preview/apply artifacts, capital recommendation validator, dashboard validation |
| P1/P2 paper simulation | WF63/WF67 | WF63/WF67 continuity + guardrail note | paper readiness report, kill switch, scoped request, guard validation, audit log |
| P2 research/macro monitors | WF60/WF61/WF65 | Active Workflows + generated proof | research freshness packet, small/mid feed, fundamentals validation |
| P3/P4 paused/blocked | Paused and blocked tables | Active Workflows | Ask/stop before owner/operator-gated actions |

## Department and skill routing

Source after review: `tmp/wf71-department-skill-ownership-proposal.json` and `tmp/wf71-skill-routing-load-budget-rules.json`. Treat them as routing inputs, not new authority layers.

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

## Script and artifact routing

Source after review: `tmp/wf72-script-ownership-inventory.json`. Keep `scripts/` root as compatibility CLI surface unless/until a reviewed module-boundary migration preserves old command names.

- Start generated-artifact/proof/provenance/staging lookup with SQL cockpit commands when available:
  - `python scripts\artifact_index.py cockpit --limit 20` for the current operating queue from indexed artifacts.
  - `python scripts\artifact_index.py ticker-cockpit <TICKER> --limit 30` for ticker-specific indexed proof trails.
  - `python scripts\artifact_index.py trust-cockpit --limit 50` for authority/freshness/trust boundaries.
  - `python scripts\artifact_index.py proof-field <TICKER> <field_name>` for official-source field provenance.
  - `python scripts\artifact_index.py stoplines --limit 50` for staged canon proposal stop lines.
  - `python scripts\artifact_index.py validate` before relying on SQL if index freshness/integrity matters.
- Start recurring finance inventory/intelligence questions with the coverage-router pattern when present:
  - data family coverage -> `tmp/finance-data-coverage-current.json` / `python scripts\artifact_index.py data-coverage`.
  - ticker review packet -> ticker intelligence card under `tmp/ticker-intelligence-cards/` / `python scripts\artifact_index.py ticker-card <TICKER>`; the current WF77 registry target is 42/42 coverage tickers, generated by `python scripts\ticker_intelligence_card.py --all-from-coverage`.
  - material finance/readiness/recommendation/authority answers -> `python scripts\artifact_index.py answer-contract "<question>" --json` or router `answer_contract_v2`, then source-open the listed exact artifacts/owner notes before final claims. If `answer_contract_v2.freshness_and_conflict_checks.final_answer_allowed` is false, treat it as a stop/downgrade until stale/missing/conflict residue is resolved or explicitly disclosed.
  - paper-position visibility / WF67 paper holdings -> `python scripts\finance_intelligence_state.py paper-positions --pretty`, backed by `tmp/wf67-paper-position-state.sqlite`; JSON/Markdown holdings files under `tmp/alpaca-paper-readiness/` are compatibility exports, not state owners.
  - missing evidence -> coverage registry missing-family rows, then exact source artifacts.
  - recommendation support -> ticker card + source freshness + authority/guardrail artifacts, then canonical owner notes when material.
  - If the needed coverage/ticker-card/answer-contract surface is not built, say so, use SQL/current-window/workspace indexes as fallback, and do not treat broad scan as the desired steady-state route.
- Use `tmp/current-window-artifacts.json` / `.md` as the compatibility artifact index and as a cross-check/fallback when SQL is stale, unavailable, or lacks the needed artifact class.
- For finance-chain state, inspect `tmp/run-summary-<window>.json` and the named validator artifact before claiming readiness.
- High-authority script surfaces — paper execution, portfolio apply, canon sync, scheduler/dashboard chain files — are no-delete/gated-review paths.
- Archive candidates are review-only; reference checks and owner approval are required before move/delete/archive.
- New scripts/helpers must pass the reuse-before-new-script gate in `Automation Orchestration Protocol.md` and the system-aware standard in `skills/disciplined-implementation/SKILL.md`.

## Canonical finance truth route

Use these owner notes for finance claims:

- Execution state, bands, stops, repair state: `03. Portfolio/Execution Board.md`
- Portfolio posture/model weights: `03. Portfolio/Portfolio Snapshot.md`
- Research universe/thesis/watchlist membership: `04. Research/Coverage and Watchlist.md`
- Risk rules: `07. Risk/Risk Rules.md`
- Weekly operating map: `05. Intelligence/Weekly Positioning Review.md`
- Macro regime: `02. Markets/Macro Regime Dashboard.md`

Generated packets, dashboards, Today card drafts, capital recommendations, validators, SQL cockpit rows/views, and proof indexes are evidence/review surfaces only.

## Current finance posture snapshot

Use latest `Active Workflows.md`, owner notes, `tmp/market-state.json`, `tmp/deployment-readiness-surface.json`, and `tmp/current-window-artifacts.*` before making finance-state claims.

Known standing boundaries:
- Generated dashboards/packets do not grant owner approval, deployment entitlement, sizing/risk authority, or trade/account action.
- WF63/WF67 paper execution is paper-only and requires exact scoped request artifact, fresh kill switch, guard validation, redacted audit log, and main-session notification.
- Exact portfolio/canon maintenance is allowed only inside approved gates with exact artifacts, preview/proof, validators, backups/rollback, and audit trail.
- Trade/account action, brokerage orders, money movement, and unscoped execution entitlement remain blocked.

## Stop lines

Stop or ask before:

- identity/doctrine rewrites without a proven stale/conflicting rule;
- file moves/deletes/archive/renames;
- config/auth/channel/network/service/runtime mutation;
- live brokerage/account action, money movement, or live credential/endpoint use;
- paper submit/cancel/sell outside exact WF67 scoped guardrails;
- portfolio/canon/sizing/cash/risk/execution entitlement mutation outside exact approved gated apply;
- treating generated surfaces, scores, validators, dashboards, Today cards, or recommendation packets as owner approval.

## SQL cockpit, SQL-canon cache, and current-window proof lookup

- Primary generated-artifact index: `tmp/veritas-artifact-index.sqlite`, accessed through `scripts/artifact_index.py` cockpit/query commands. This is derived proof/provenance/staging only, not canon authority.
- Bounded SQL-canon/cache surface: `tmp/veritas-canon-cache.sqlite` has exact approved metadata authority for 265 rows only: 13 low-risk proof/freshness/lifecycle metadata rows plus 252 WF72 entry/stop reference metadata rows across 42 tickers (`reference_price_low`, `reference_price_high`, `reference_invalidation_level`, source timestamp/hash/owner path). It still grants no approval, apply, portfolio mutation, recommendation/action-state upgrade, trade/account/paper/live authority, cash/sizing/risk-rule change, credential, cron, or Markdown-note mutation authority.
- Retail-grade SQL transition gate: `scripts/sql_canon_retail_grade_readiness.py --write --validate` writes `tmp/sql-canon-retail-grade-readiness.json`, the row-level map for whether active SQL-canon/cache rows are SQL-effective, fallback-required, stale/unsafe, missing-fallback, or display-only. Current status is blocked for SQL-first retail-grade use until stale/fallback/no-drift gates clear; use this before any SQL-first consumer or customer-safe renderer binding.
- Current WF72 pickup after the 2026-05-29 11:55 MST OpenClaw-update handoff: read `tmp/handoff-current.json` first. The typed read-only entry/stop helper is not implemented yet; restart by validating OpenClaw/tool routes, then build the helper over `tmp/veritas-canon-cache.sqlite` in read-only mode only. Cron/operator helper audit found four future archive-packet candidates, but no archive move is approved from that audit alone.
- For ticker entry/stop/band-reference questions, check the live canon-cache rows and their reconciliation/validator status first; if stale/missing/blocked, fall back to the owning source artifact/owner note and name the stale SQL condition. The post-close/morning chains should refresh WF72 entry/stop SQL-canon before canon drift freshness gates.
- Compatibility/fallback index: `tmp/current-window-artifacts.json` / `.md`.
- Rule: use SQL/current-window indexes for existence, freshness, provenance, staging, metadata cache, and authority-boundary routing; inspect the target artifact or canonical owner note before making material content or finance claims.
- Stop line: no SQL row/view/query output grants owner approval, broad canon mutation, portfolio mutation, trade/account action, paper/live order authority, or execution entitlement.
- High-authority exceptions to name directly:
  - `tmp/alpaca-paper-readiness/paper-execution-guard-validation.json`
  - `tmp/alpaca-paper-readiness/kill-switch.json`
  - `tmp/wf67-paper-position-state.sqlite`
  - `tmp/finance-intelligence-state-paper-positions.json`
  - `tmp/portfolio-mutation-proposals/current-capital-deployment-recommendations.json`
  - `tmp/capital-deployment-recommendation-validation.json`
  - `tmp/dashboard-validation.json`
  - `tmp/run-summary-morning.json`
  - `tmp/run-summary-post-close.json`

## Config/compaction posture

Config/auth/channel/service/runtime mutation remains approval-gated unless explicitly authorized. For config schema and broader OpenClaw behavior, use first-class config/gateway tools or local docs before editing.

## Startup behavior rule

After compaction, prefer this file plus `Active Workflows.md` before broad vault reads. Drill into full files only for the current task.
