# WF73 Active Workflows Compression Proposal

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

## Compression goal

Make Active Workflows usable as a fast control surface: current goal, next action, blockers, proof, owner/department route, and stop lines should be findable without reading the entire 50KB workflow history block.

## Diagnosis

- The file already owns live workflow truth and should be reused, not replaced.
- Current top section mixes primary goal, historical integration deltas, workflow rows, cron monitors, and cleanup queues in a long read path.
- Many rows carry valuable proof links but too much detail for startup; detail belongs in continuity notes and proof artifacts.
- WF72/WF73/WF71 are now OS-control-plane work and should be visible near the top without displacing WF68 as primary finance goal.

## Proposed queue tiers

### P0_primary_goal_lock

- **tier:** P0_primary_goal_lock
- **purpose:** One active top goal that controls default next work.
- **current_members:** `["WF68"]`
- **required_fields:** `["goal", "current_status", "next_action", "acceptance_gate", "blocker_or_trust_limit", "stop_lines", "proof_links"]`

### P1_active_enablers

- **tier:** P1_active_enablers
- **purpose:** Directly supporting lanes for the primary goal or newly approved OS restructure.
- **current_members:** `["WF70", "WF66", "WF67", "WF64", "WF72", "WF73", "WF71", "WF69"]`
- **required_fields:** `["status", "owner_department", "next_action", "acceptance_gate", "proof_links", "stop_lines"]`

### P2_operational_monitors

- **tier:** P2_operational_monitors
- **purpose:** Cron/review surfaces and implemented chains that matter for confidence but are not the current implementation focus.
- **current_members:** `["WF58", "WF56", "WF63", "WF60", "WF61", "WF65", "WF62", "cron-owned monitors"]`
- **required_fields:** `["monitor_status", "proof_surface", "escalation_condition", "stop_lines"]`

### P3_paused_or_resume_later

- **tier:** P3_paused_or_resume_later
- **purpose:** Known follow-ups that should not steal startup attention.
- **current_members:** `["WF37", "Market-moving news intake pilot", "WF44/WF45 follow-ups"]`
- **required_fields:** `["resume_trigger", "stop_lines", "continuity_link"]`

### P4_blocked_owner_or_operator_gated

- **tier:** P4_blocked_owner_or_operator_gated
- **purpose:** Items requiring owner/operator approval or external/runtime action.
- **current_members:** `["WF49", "WF50", "Root backup cleanup"]`
- **required_fields:** `["blocker", "required_approval_or_next_step", "do_not_do"]`


## Proposed exact sections

### # Active Workflows

- **notes:** Keep current purpose and authority statement, shortened.

### ## Read me first: current control snapshot

- **exact_section_text:** ## Read me first: current control snapshot

- **Primary goal lock:** WF68 - Intraday Alert Engine and Advisor Surface remains the primary finance/advisor goal.
- **Current OS restructure focus:** WF72/WF73/WF71 are active enablers to reduce boot, queue, skill, and script-routing drag; they are review/proposal-first.
- **Next queue item:** <single next workflow action from the P0/P1 queue>.
- **Current blocker/trust limit:** <fresh blocker, stale proof, or approval gate>.
- **Must-not-do:** no live trading/account/money movement; no paper execution outside WF67 guardrails; no config/auth/channel/service/destructive cleanup without approval; no generated packet/dashboard becomes canon or approval.
- **Proof lookup:** start with `tmp/current-window-artifacts.json`, the row proof links below, and the workflow continuity note before inspecting generated artifacts.


### ## Queue tiers

- **exact_section_text:** ## Queue tiers

| Tier | Meaning | Current members | Default action |
|---|---|---|---|
| P0 | Primary goal lock | WF68 | Continue unless blocked or Randall redirects. |
| P1 | Active enablers | WF70, WF66, WF67, WF64, WF72, WF73, WF71, WF69 | Advance only when it supports P0 or approved OS restructure. |
| P2 | Operational monitors | WF58, WF56, WF63, WF60, WF61, WF65, WF62, cron-owned monitors | Monitor proof/escalate regressions; do not let routine monitor work become the queue. |
| P3 | Paused/resume-later | WF37, news intake pilot, WF44/WF45 follow-ups | Resume only on trigger or owner request. |
| P4 | Blocked/approval-gated | WF49, WF50, root backup cleanup | Ask/stop before any gated action. |


### ## P0 / P1 active workflow register

- **exact_section_text:** ## P0 / P1 active workflow register

| Tier | Workflow | Status | Owner department | Next action | Acceptance gate | Stop lines | Continuity / proof |
|---|---|---|---|---|---|---|---|
| P0 | WF68 - Intraday Alert Engine and Advisor Surface | Primary goal / runtime enabled | Advisor Alert Desk + Veritas main | Observe next market-hours in-band event and verify `EXECUTION_PACKET_READY` only with sufficient official evidence; continue Alpaca market-data spine v2 if no event. | Immediate alert only for trade-ready in-band execution recommendation with sizing/price/stop/reference and sufficient official evidence. | No live trading/account/money movement; paper only through WF67; no owner-approval inference; no channel/config/auth mutation. | WF68 continuity; `tmp/intraday-alerts/*`; `tmp/portfolio-mutation-proposals/current-capital-deployment-recommendations.*`; `tmp/current-window-artifacts.*` |
| P1 | WF73 - Queue, Index, and Boot Surface Optimization | Phase 1 inputs integrated / proposal lane active | OS Operator / Automation Desk + Continuity / Procedure Desk | Review/apply boot-surface load map, Active Workflows compression proposal, and Startup Truth Index proposal after main review. | Main can identify goal, next action, blockers, proof, skill/department route, and stop lines quickly; no apply until reviewed. | No doctrine rewrite, destructive/config/channel/runtime mutation, portfolio/canon/trade/account/paper mutation, or generated-surface-as-canon. | WF73 continuity; `tmp/wf73-*`; Startup Truth Index; Active Workflows |
| P1 | WF72 - Financial OS Efficiency Restructure | Phase 1 integrated / Phase 2 proposal-prototype queue active | OS Operator + Implementation / Refactor Desk | Continue Phase 2 proposal/prototype lanes, especially Today-card prototype and script/helper migration proof. | Preserve proof links, review-only/prototype authority, no destructive action without reference checks and approval. | No moves/deletes/archive/config/auth/channel/service mutation; no trade/account; no owner approval inference. | WF72 continuity; `tmp/wf72-phase1-integration-packet.*`; `tmp/wf72-*` |
| P1 | WF71 - OS Department Staff and Skill Ownership Model | Proposal artifact complete / review pending | Main-session operating model + Independent QA challenge | Review department/skill ownership matrix and promote only a thin routing table if accepted. | Staff lanes have one mission, owned skills/surfaces, deliverables, stop lines, handoff format, and proof. | No separate autonomous identity; no duplicate canon; no authority collision. | WF71 continuity; `tmp/wf71-department-skill-ownership-proposal.*` |
| P1 | WF70 / WF66 official evidence spine | 20 priority captures clean / long-tail + helper migration active | Official Source Desk + Fundamental Research Desk | Migrate one capture script to common helper with side-by-side output proof; then long-tail captures. | Official values sourced or marked not_disclosed/not_applicable/manual_required; validators clean. | No invented values; no portfolio/canon/trade authority from evidence alone. | WF70/WF66 continuity; `tmp/official-ir-captures/*`; `tmp/fundamental-ir-reconciliation-packets.*`; `tmp/official-earnings-bridge.*` |
| P1 | WF67 - Alpaca Paper Execution Guardrail | Guardrail active / kill switch normally expired outside execution windows | Risk and Paper Execution Guard | Before any advisor-derived paper order: exact scoped request + fresh kill switch + guard validation + redacted audit + main-session notification. | Paper endpoint only, scoped artifact, clean guard proof, audit trail. | No live endpoint/credentials, money movement/account settings, close/liquidation endpoints, or inferred approval. | WF67 continuity; `tmp/alpaca-paper-readiness/*` |


### ## P2 operational monitors

- **exact_section_text:** ## P2 operational monitors

Keep this as a compact table with: monitor/workflow, status, escalation condition, proof surface, stop lines. Move historical proof details to continuity notes, Cron Run Ledger, or generated artifacts.


### ## Paused / blocked / cleanup queues

- **exact_section_text:** ## Paused / blocked / cleanup queues

Keep paused and blocked tables, but require one-line resume trigger/blocker. Archive/cleanup candidates remain review-only and must not be moved/deleted without reference checks and owner approval.


### ## Global authority and proof rules

- **exact_section_text:** ## Global authority and proof rules

- Active Workflows owns live queue state; continuity notes own resume context; `tmp/` owns proof/review packets; canonical finance notes own portfolio truth.
- Generated artifacts, dashboards, Today card drafts, packets, scores, and validators do not imply owner approval or execution authority.
- Preserve proof links in every compressed row: continuity note plus the few primary proof artifacts needed to verify status.
- If proof is stale, partial, missing, or contradictory, downgrade confidence and inspect the owner artifact before claiming readiness.



## Proof link preservation

- **minimum_per_active_row:** `["continuity note link", "primary tmp proof artifact(s)", "validator or acceptance proof when available", "canonical owner note only when it is the truth source"]`
- **do_not_drop:** `["WF67 paper guardrail proof links", "WF64/WF56 gated apply proof links", "WF68 alert/router/handoff proof links", "WF70/WF66 official-source validator links", "WF72/WF73/WF71 Phase 1 and proposal artifacts"]`
- **move_long_history_to:** `["workflow continuity notes", "memory/YYYY-MM-DD.md for dated deltas", "Cron Run Ledger for scheduled proof", "tmp/ generated proof artifacts"]`

## Acceptance checks after apply

- Top snapshot names one primary goal and one next queue action.
- Every P0/P1 row has owner department, next action, acceptance gate, stop lines, continuity/proof links.
- Paused/blocked cleanup remains review-only and owner-gated.
- No finance/trade/account/paper/config/destructive authority widened.
- Links/paths preserved for current proof and continuity.

## Recommended next action

Main review this proposal, then rewrite Active Workflows in-place using the proposed section order and compressed rows; do not delete proof links without continuity/proof relocation.
