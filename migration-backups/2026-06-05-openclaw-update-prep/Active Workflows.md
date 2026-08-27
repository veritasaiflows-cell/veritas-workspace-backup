# Workflows

Compact live workflow control surface for Veritas.

This note owns current queue state, next safe action, blockers, proof routes, and stop lines. It is not history, canon, approval, or execution authority. Detailed history belongs in workflow continuity notes, `memory/YYYY-MM-DD.md`, and proof artifacts under `tmp/`.

## Current Control Snapshot

- **Primary goal lock:** Retail-grade truth routing over artifact-owned finance intelligence. Retail Investor Finance Intelligence remains P0; routing/automation proof outranks UI polish and SMB packaging.
- **Current lane:** Retail Truth Routing Phase 1-4 plus Phase 4.5-7 automation: source-open SQL gate, fallback-decay proof, adversarial answer harness, PM/cockpit visibility, customer-safety gate, freshness prompts, and internal demo cards.
- **Automation posture:** heartbeat/PM/cron/helper lanes produce proof; Veritas main integrates. PM emits implementation-grade job packets. Scaling stays manifest/runner/validator driven.
- **SQL posture:** `state/finance/finance-canon.sqlite` is finance universe/answer-path scope only; WF72 A2 fallback read guard is live for the 265-row cache boundary. SQL is not canon/approval/portfolio/customer/execution authority.
- **WF78 pickup overlay:** Tier B research packets now exist: 15 macro-shortlist packets, all still evidence-repair, 0 Phase 2 eligible. Next WF78 work is repairing technical/price-band context and evidence-repair burden, not import or promotion.
- **Next safe action:** Refresh Retail/WF78/PM proof, then build the highest-value implementation packet from `pm_implementation_job_queue.py`. Customer-safe export, SQL-first promotion, Python fallback retirement, additional cron schedule changes, and any import/apply path require separate decisions/gates.
- **Current blockers:** customer/public use blocked; privacy/licensing/counsel packets are not active route; WF68 trade/execution flags false; Telegram shadow delivery paused; WF55 probability readiness not ready.
- **Must not do:** no live/account/money movement; no paper execution outside WF67; no config/auth/channel/service/runtime mutation without approval; no destructive cleanup; no artifact/dashboard/SQL row becomes approval or execution authority; no SQL-canon expansion beyond exact gates.
- **Proof lookup:** start with `python scripts\artifact_index.py ...`; inspect exact owner artifacts/notes before material claims.

## Queue Tiers

| Tier | Meaning | Current members | Default action |
|---|---|---|---|
| P0 | Primary continuity vertical | Retail Investor Finance Intelligence SaaS, Retail-grade truth routing | Keep internal/service-led finance proof clean; public/customer/account/advice claims stay blocked. |
| P1 | Active build lanes | SMB Workflow Clarity, WF79, WF70/WF66, WF67, WF64/WF56, WF72, WF73, WF71, WF74, WF75, WF76, WF69, WF77, WF78 | Advance Command Center, service-run, SQL, Node/PM, renderer, and validators without customer/external authority. |
| P2 | Operational monitors | WF58, WF63, WF60, WF61, WF65, WF62, WF55, finance chains, guardrails, SQL cockpit, workspace governor | Monitor proof and escalate regressions. |
| P3 | Paused/resume-later | WF37, news intake pilot, WF44/WF45 follow-ups, simplification backlog | Resume only on trigger or owner request. |
| P4 | Blocked/approval-gated | WF49, WF50/archive/root cleanup, channel/config/auth/service changes, live brokerage/account actions | Ask/stop before gated action. |

## P0/P1 Active Register

| Tier | Workflow | Current state | Next action | Proof route | Stop lines |
|---|---|---|---|---|---|
| P0 | Retail Investor Finance Intelligence SaaS / WF75 | Internal/service-led finance vertical exists with anonymous scenarios, service-state, operator console, renderer/export, PM handoff, WF77 evidence, macro/recommendation tracking, and authority spine. | Preserve as P0 while WF79 becomes the local review UI. | WF75 continuity; `tmp/wf75-*`; authority matrix | No fake-person product truth, public/customer/account/advice/trading claims, guaranteed return/win-rate/probability claim, source-licensing assumption, or legal/compliance-readiness claim. |
| P0 | Retail-Grade Truth Routing System | Phase 1-4 and Phase 4.5-7 automation are built, validated, scorecard-green, and scheduled through review-only guard cron. | Keep routing, harness, automation plane, PM/cockpit Retail tab, customer-safety gate, freshness prompts, and demo cards clean; customer-safe output waits for Randall. | `retail_truth_routing_contract.py`; `retail_answer_harness.py`; `retail_automation_control_plane.py`; PM/cockpit; A2 guard; harness scorecard | No SQL-first promotion, SQL writes/imports, customer/external output, canon/portfolio mutation, paper/live/account action, Python fallback retirement, cron mutation, or approval inference. |
| P1 | Generic Intelligence SaaS / SMB Workflow Clarity | Lead Rescue/service-run packets, dry-run blueprints, Academy assets, local cockpit/SQL service-state, and boundary proof exist. | Build sanitized owner-attention queue fixture runner over Lead Rescue service-state slice. | `generic_intelligence_saas_pivot.py`; `wf75_training_desk.py`; `tmp/wf75-smb-*`; PM/cockpit | No real customer data, credentials, outbound/writeback, external delivery, ROI/legal/compliance/security claims, spend, SQL-as-canon, or certification claims. |
| P1 | WF79 Command Center V2 | PM cockpit is the base local review UI; warnings/stops stay prominent. | Build V2 source registry + normalized entry-band contract; wire Deployment and Technical views to same band-status contract. | WF79 continuity; PM cockpit; source registry; deployment/technical/WF72/WF77/WF58 routes | Local/review-only UI. No canon/portfolio mutation, paper/live/account action, approval inference, public/customer delivery, SQL promotion, or config/channel/runtime expansion. |
| P1 | WF72 Financial OS SQL Support | 265-row cache boundary and A2 fallback read guard are green. | Keep support-mode; separate gate required before consumer promotion, Python retirement, or SQL-first use. | WF72 continuity; A2 manifest/values; Go guard; hardening pass; SQL source-truth artifacts | No SQL write expansion, archive/move/delete without proof, action-state/canon/portfolio mutation, customer output, runtime/config mutation, Python retirement, SQL-first promotion, or approval inference. |
| P1 | WF68 Intraday Alert Engine | Reduced-load internal alert/advisor proof; Telegram shadow and high-frequency handoff paused; authority flags false. | Keep producer/digest proof clean; manual `REVIEW` / `PREPARE` only after artifact + WF67 guard inspection. | WF68 continuity; intraday runtime/delivery JSON; alert producer | No channel expansion, config/auth/runtime mutation, live/paper/order/account action, canon/portfolio/sizing/sleeve/cash/risk-rule mutation, or approval inference. |
| P1 | WF73 Queue/Index/Boot Optimization | Boot/control routing, PM queue, cron freshness spine, cron retire/merge, helper manifest, hardening pass, and cockpit proof are active; cron enabled count is 25. Freshness spine registers all 25 enabled jobs with artifact contracts: 23 fresh, 2 needs-review, 0 stale, 0 blocked, 0 unregistered. | Use `cron_freshness_spine.py --write --validate` as the first cron-awareness route; use PM implementation queue before larger work; use retire/merge candidates before adding jobs; keep boot files route-only. | WF73 continuity; PM queue; cron freshness spine; cron ledger; operating leverage/scorecard/escalation; hardening pass; Startup Truth Index | No new authority source, doctrine rewrite, destructive/config/channel/runtime mutation, authority weakening, SQL-first promotion, or inferred approval. |
| P1 | WF70/WF66 Official Evidence Spine | Registry/latest-selector migration complete; official earnings/reconciliation routes have no-drift proof. | Monitor validators; capture/roll forward only for active finance/product goals. | WF70/WF66 continuity; official captures; IR reconciliation/bridge artifacts | No invented values, no bridge-present-equals-reconciled shortcut, no portfolio/canon/trade authority from evidence alone, no owner approval inference. |
| P1 | WF77 Finance Coverage / Question Router | 42/42 production cards enriched; active 200-card review set rebuilds with stale-evidence repair signals. | Use WF77 first for finance questions; run ticker-card refresh before promotion-quality use. | WF77 continuity; coverage current; ticker cards; `finance_intelligence_state.py`; router; artifact index | Review/intelligence only; no live trading/account/money movement, paper execution, approval inference, import/apply, production promotion, or canon/portfolio mutation. |
| P1 | WF78 500 Ticker Scaleout / Promotion | 200 active rows: 42 production + 158 Tier C review-monitor. D/C/B/A funnel Phases 1-4, route dashboard, and Tier B research packet route are built. Live state: 15 macro-shortlist packets, all blocked on evidence repair; 0 Phase 2 eligible/actionable. | Repair technical/price-band context and acceptable repair-burden evidence, then rerun Tier B packets, Phase 2, owner packet, and routing dashboard. | WF78 continuity; Coverage Admission Protocol; `wf78_*` gates; `wf78_tier_b_research_packet.py`; `finance_ticker_card_refresh_gate.py`; `tmp/wf78-tier-b-research-packets.*`; `tmp/wf78-routing-dashboard.*` | No future import/apply without exact owner approval; no promotion from existence, score, macro overlay, checklist, packet, or SQL row; no Tier A roster change without owner approval; no `A-DEPLOY` execution without separate exact order approval; no canon/portfolio/customer/paper/live/account authority. |
| P1 | WF67 Alpaca Paper Execution Guardrail | Paper-only guardrail active; paper sandbox separate from real planning portfolio; manager packet consolidates readiness. | Refresh gate, run manager with request refresh, present ready/blocked/repair status; execute only after fresh kill switch, guards, redacted audit, notification, and Randall exact approval. | WF67 continuity; Chief gate; WF67 manager/cards; paper position SQLite; readiness artifacts | No live endpoint/credentials, money movement/account settings, close/liquidation endpoints, inferred approval, autonomous paper orders, refresh-triggered submit/cancel/sell, or paper-to-live promotion. |
| P1 | WF64/WF56 Portfolio/Canon Maintenance | Proposal/semantic preview/gated apply architecture active; applies remain exact-gated. | Keep validators clean; use only exact standing/scoped approval artifacts. | WF64/WF56 continuity; mutation proposals; post-apply validation chain | No trade/account/brokerage/money movement; no cron direct apply; no cash/risk-rule/execution-entitlement mutation unless separately scoped; no clean-validation-equals-approval. |
| P1 | WF71 Department Staff / Skill Ownership | Skill-routing/load-budget procedure active; PM handoffs embed helper contracts. | Use helper contract, spawn packets, active manifest, and completion handshake around helper work. | WF71 continuity; PM handoff; operating leverage; helper packets/manifest/handshake | No separate autonomous identity, duplicate canon source, authority collision, heartbeat helper spawning, or trading/account/portfolio authority. |
| P1 | WF74 Recursive Self-Improvement | V1 monitor-and-use complete; validation harness and boundary lint exist. | Use only for repeated friction, validator failures, or completed work worth capture. | WF74 continuity; `tmp/wf74-*`; RSI script; self-improvement skill | No base-model self-modification, self-preservation/replication, autonomous authority expansion, second memory tree, owner-approval inference, portfolio/trade/account/paper/live authority, or RSI theater. |
| P1 | WF76 Cron Authority / Canon Auto-Update | Scheduled/review-only; cron awareness now flows through freshness spine -> scorecard -> escalation. PM/heartbeat signal classification remains active. | Verify selectivity with `cron_freshness_spine.py`, `cron_signal_scorecard.py`, and `escalation_trigger.py`; archive moves only after owner approval/proof. | WF76 continuity; cron/db lifecycle scripts; cron freshness spine; operating leverage; signal scorecard | No cron-direct portfolio/canon apply; no deletes; no config/auth/channel/service/runtime mutation, owner approval inference, or heartbeat inline execution. |
| P1 | WF69 Intelligence / Probability Stack V2 | Control-plane/data-contract revamp active; probability claims blocked. | Use SQL truth spine as proof/index substrate only; validate bundles without predictive claims. | WF69 continuity; WF v2 artifacts; intelligence stack validator | No probability/win-rate/expected-return/model-readiness claims while WF55 is not ready; no live/paper/account authority. |

## P2 Monitors

| Monitor | Escalate when | Proof route | Stop lines |
|---|---|---|---|
| WF58 dashboard/capital packets | Validator warning/critical, false-green dashboard, generated packet conflicts with canon | dashboard/capital packet validation artifacts | No self-apply, trade/account authority, or per-packet approval inference. |
| WF63 paper readiness | Readiness/no-submit guard warning/critical, live endpoint/credential exposure | WF63 readiness/no-submit artifacts | No live endpoint/credentials, money movement/account changes, or submit/cancel outside WF67. |
| WF60/WF61 research/regime | Freshness degradation, macro cue conflicts with canon, feed implies action | macro judgment, research freshness, sector expansion artifacts | Review-only; no promotion/sizing/sleeve/cash/risk-rule/trade authority. |
| WF65 fundamentals | Validator warning/critical, official source conflict, stale probe | fundamental/IR/earnings bridge artifacts | Evidence only; no deployment/trade/portfolio authority. |
| WF62 canon consolidation | Consumer points to retired canon or dashboard outranks owner note | canonical ownership validation | No ungated canon mutation or delete/archive without approval. |
| WF55 probability readiness | Hit-rate/probability/win-rate language appears before gates clear | probability readiness, outcome ledger, call log | No predictive scores, expected-return claims, win-rate claims, model-ranked deployment, durable v2 append, paper/live execution, or approval inference. |
| Chief/WF67 manager gate | Candidate/card lacks rank, band/stop proof, sector/monitor/paper context, WF55 caution, or manager readiness | Chief gate and WF67 manager/card artifacts | Review/routing only; no watchlist apply, portfolio/canon mutation, paper/live execution, owner approval inference, probability/model authority, or money movement. |
| Finance chains | Missing/failed run, stale current-window index, validator warning/critical, digest escalates | chain/run/current-window/digest artifacts; cron ledger | Review/proof only; no mutation/action/approval authority. |
| Board/canon guardrails | Critical contradiction, widened authority flag, proposal implies self-apply | board/canon/stale/proposal artifacts | Cron may propose; main applies only bounded freshness/status sync or exact gated maintenance. |
| SQL/current-window indexes | Missing proof, authority flag violation, stale index, index treated as approval/action, lifecycle unlabeled | finance SQL, artifact index, JSON-SQL index, current-window, lifecycle manifest | SQL candidate is universe/scope only; other indexes are proof/staging. No approval/execution/archive/delete authority. |
| Workspace governor/archive | Cleanup suggestion treated as approval or moved/deleted without reference check | archive suggestions; lifecycle manifest | Suggestions only; no destructive cleanup without explicit approval. |

## P3 Paused / Resume Later

| Workflow/lane | Resume trigger | Continuity |
|---|---|---|
| WF37 daily summary commercial brief hardening | After higher-priority finance/canon/reporting cleanup | WF37 continuity |
| Market-moving news intake pilot | After WF68/WF60/WF61 stabilize or Randall requests intraday news awareness | Fold into WF60 or open dedicated workflow only when promoted |
| WF44/WF45 dashboard/source freshness follow-ups | If Randall asks for legacy generated HTML surface; otherwise fold into WF79 | WF44/WF45 + WF79 continuity |
| Workspace simplification/archive backlog | Reference checks plus explicit owner approval | archive suggestions; Portfolio Truth Surface Ownership Procedure |

## P4 Blocked / Approval-Gated

| Lane | Blocker | Required next step | Do not do |
|---|---|---|---|
| WF49 FRED runtime persistence | Credential/runtime environment handling | Rotate/replace credential outside chat, configure runtime inheritance, restart/verify, scan for leaks | Do not expose secrets or mutate runtime/config without explicit approval. |
| WF50/archive/root cleanup | Moves/deletes/archive require owner approval | Exact microbatch packet with reference checks, hashes, manifest, rollback, validators | Do not delete/move protected, canon, current-window, script, skill, config, runtime, credential, or proof-critical surfaces. |
| Channel/config/auth/service changes | Security/runtime exposure | Ask Randall and use first-class Gateway/config tooling where available | Do not restore channels or mutate credentials/config silently. |
| Live brokerage/account actions | Hard finance boundary | Separate explicit live-action instruction with full scope and risk acceptance | Do not place/cancel/replace live orders, move money, change accounts, use live endpoints/credentials, or infer approval. |

## Global Authority Rules

- Active Workflows owns live queue state; continuity notes own resume context; `tmp/` owns proof/review packets; canonical finance notes own portfolio truth.
- No generated artifact, dashboard, Today card, packet, SQL row, score, or validator implies owner approval or execution authority.
- Veritas main remains final integrator and truth owner; helper lanes support but do not publish final authority.
- Operator packets and operating leverage proof are handoff/proof only.
- Harness proof: `tmp/veritas-harness-scorecard.json/.md`; classify noisy tool failures before deciding severity.
- Heartbeat and PM packets are handoff signals only; PM implementation queue and main-session handoff convert safe next actions into scoped continuation packets.
- If proof is stale, partial, missing, or contradictory, downgrade confidence and inspect owner artifacts before claiming readiness.
- Archive/cleanup recommendations are review-only until reference checks, hash manifest, destination plan, and explicit owner approval.
- Standing portfolio/canon maintenance applies are limited to approved categories and exact gated paths; live trading/account/brokerage/money movement remains blocked.
- Paper trading remains WF67-only: exact paper endpoint, scoped request/pilot/full-scope artifact, fresh kill switch, guard validation, redacted audit log, and main-session notification.

## Simplification Decisions

- `01. Dashboards/Today.md` is review-only; no canon, approval, or execution authority.
- `05. Intelligence/Weekly Positioning Review.md` is current weekly strategy product; older Weekly Intelligence Brief is scaffold/archive unless rebuilt.
- `tmp/full-portfolio-view.json/.md/.html` is preferred portfolio communication; `tmp/dashboard-data.json` is UI payload only.
- `state/finance/finance-canon.sqlite` is the finance universe/scope SQL machine-canon candidate; `tmp/veritas-artifact-index.sqlite` is proof/index/staging; `tmp/veritas-canon-cache.sqlite` is bounded 265-row proof/cache.
- WF72 A2 fallback-backed read guard supports faster routing and safer read consumers only; it does not authorize SQL writes, SQL-first customer/retail output, canon/portfolio mutation, Python fallback retirement, or execution authority.
- Quick routing should call existing owner scripts/artifacts first and source-open exact proof before material claims.
- Durable research goes to `04. Research/`; audits to `08. Audits/`; workflow pickup truth to `06. Playbooks/Project Continuity/`.
- Startup Truth Index is the thin pickup map; canonical owner notes still win.
- Workflow Alias Index maps `WF##` IDs to names; it is a router only.
- Portfolio truth conflicts route through Portfolio Truth Surface Ownership Procedure.
