---
name: "project-continuity-manager"
description: "Maintain resumable project, lane, and seven-agent handoff state with proof, acceptance, reporting, and owner-gated next actions."
---

# Project Continuity Manager

## Purpose

Preserve pickup points for real projects, handoffs, and meaningful non-workflow work without turning the workspace into a bloated PM system.

This skill complements adjacent owners:
- `memory-continuity-manager` decides what belongs in daily memory versus durable memory.
- `cron-automation-manager` owns cron design, schedule boundaries, blocked cron signal repair routing, and cron proof gates.
- `veritas-response-contract` owns Randall-facing response shape, proof rollups, recommendation labels, and plain-English blocker wording.
- `disciplined-implementation` owns code/script/validator/release implementation contracts.
- `project-continuity-manager` owns the resumable pickup state: what changed, what remains, where proof lives, and the next safe action.

## Use When

Use this skill when:
- a project has moved meaningfully but is not finished
- priorities are shifting and a clean resume point matters
- several projects are active at once
- a project has blockers, dependencies, or trust gaps worth tracking
- Randall asks how to remember where to pick back up
- the current state is spread across too many notes or chat turns
- meaningful work is not part of a named workflow but has completed items, pending actions, blockers, or a next safe step that should not be lost
- a main session, helper lane, or cron lane needs to hand off incomplete work across sessions
- a blocker must be translated into a resumable next action with a continuity home and proof reference
- lane closeout needs a completion contract but does not need a separate PM workflow

Do not use this skill for trivial one-shot tasks.
Do not use it to duplicate canonical truth that already lives cleanly in an owning note.
Do not use it to mutate cron schedules, workflow authority, finance canon, portfolio state, runtime config, external delivery, paper/live orders, accounts, or destructive cleanup.

## First Route For Handoffs

For incomplete main-session, helper-lane, or cron-adjacent handoffs:

1. Read the future-session packet, today's project continuity pickup note, and the relevant workflow router/capsule before broad search.
2. Run the concurrent lane register status before writing files or spawning helpers.
3. Use PM and cron control packets as queue routers; open exact owner artifacts only when the packet points there or a blocker is material.
4. Treat generated packets and indexes as route proof only. They do not authorize finance, portfolio, account, paper, live, external, destructive, config, auth, network, startup, service, plugin, or schedule action.
5. Route cron-specific repair or schedule-contract questions to `cron-automation-manager`.
6. Route final Randall-facing closeout, recommendation labels, and blocker phrasing to `veritas-response-contract`.
7. Route code, script, validator, release-contract, or refactor work to `disciplined-implementation`.

## Handoff Completion Contract

For every handoff or pickup job, capture these fields before calling it complete or resumable:

- owner workflow or lane
- current status
- exact next action
- proof artifact or validation command
- blocker in plain English if not complete
- whether main session can resolve it automatically
- whether Randall approval is actually required
- continuity home where the next session should resume
- stop line that must not be crossed without approval

Main session owns ordinary blocker handling. Do not ask Randall for issues that can be handled by route refresh, source-open fallback, bounded repair, QA rerun, or continuity update.

Ask Randall only for external action, authority-gated action, destructive/config/auth/network/startup/service change, capital/execution approval, or unclear owner intent.

## Handoff Stop Lines

Stop and escalate instead of treating a handoff as automatically resolvable when it involves:

- external action, messaging, customer/public delivery, or account changes
- capital deployment, trade/order execution, paper/live/brokerage/account action, money movement, or owner-approval inference
- finance canon, portfolio, cash, sizing, or risk-rule mutation outside an exact approved gate
- config, auth, credentials, network exposure, startup, service, plugin, or runtime mutation
- archive/delete/destructive cleanup
- unclear owner intent
- repeated timeout with no bounded fallback
- broad unresolved diff or unknown write ownership
- material finance judgment without fresh proof

## Thin Continuity Standard

Prefer a compact project checkpoint, not a project bureaucracy layer.

Each project checkpoint should answer only:
1. what this project is
2. current state
3. what changed recently
4. outstanding items
5. blockers or trust issues
6. next concrete action
7. key files or artifacts
8. automation or refresh path when workflow cadence matters

For major workflows, also keep explicit if they are live issues:
9. acceptance gate
10. checkpoint decision
11. next 1-2 adjacent workflow candidates when useful

If a checkpoint grows into a long memo, it is drifting.

## Non-Workflow Work Matrix

Use this matrix when work is meaningful but not yet a named workflow, for example response-contract hardening, cron reduction, dashboard cleanup, operator UI improvements, prompt/routing hardening, or a one-off audit that creates follow-up work.

| Field | Required meaning |
|---|---|
| Work item | Short name of the improvement or issue. |
| Current state | `done`, `pending`, `blocked`, `watch`, or `promote-to-workflow`. |
| Completed | What was actually changed or proven. |
| Pending | Specific remaining items, not vague backlog. |
| Blocker / owner decision | Exact blocker or decision needed, if any. |
| Next action | One concrete next step. |
| Proof | Validator, artifact, file diff, proposal id, or control packet. |
| Continuity home | Daily memory, project note, active workflow, PM packet, or proposal id. |
| Stop line | What must not be inferred or done without approval. |

Rules:

- If all pending items are complete and no durable follow-up remains, daily memory is enough.
- If the item has more than one pending action, an owner decision, or likely resume-later work, create or update a compact project continuity note.
- If the item recurs, spans multiple surfaces, or has operational risk, recommend promoting it into PM or a named workflow.
- If the next action would touch config/auth/channel/runtime/destructive cleanup, external/public/customer surfaces, finance canon/portfolio/cash/sizing/risk, or paper/live/account action, state the owner gate explicitly.

## Canonical Homes

Use the smallest correct home:

- daily progress and session checkpoints -> `memory/YYYY-MM-DD.md`
- durable cross-project rules -> `MEMORY.md` or another operating file via `memory-continuity-manager`
- project-specific continuity note -> create or update only when the project spans sessions and needs a dedicated pickup point
- non-workflow work matrix row -> daily memory when short-lived; dedicated project note when resumable; PM packet/workflow only when recurring or broad

Preferred dedicated project-note location:
- `06. Playbooks/Project Continuity/<Project Name>.md`

But if a project already has a natural owning note, keep continuity there instead of creating a duplicate project note.

## Project Checkpoint Template

Use this structure when a dedicated project continuity note is warranted:

```md
Project: <Project Name>

## Objective
- <one or two lines>

## Current State
- <current truth>

## Last Meaningful Progress
- <recent completed step>

## Outstanding
- <open item 1>
- <open item 2>

## Blockers / Trust Gaps
- <real blocker or data-quality issue>

## Next Action
- <single best next move>

## Key Files
- `<path>` - <why it matters>
- `<path>` - <why it matters>

## Automation / Refresh Path
- <only include when the project depends on scripts, chains, cron, or recurring refresh windows>
```

Keep bullets short.
Prefer one next action, not a vague backlog.
Only include the automation section when it materially improves resumability.
If the project is a major workflow, keep its contract compatible with `06. Playbooks/Major Workflow Contract Standard.md`.

## Handoff Matrix Template

Use this compact block in daily memory or a project note when an incomplete handoff needs to be resumable:

```md
## <Handoff Or Work Item> - <HH:MM UTC>

| Field | Status |
|---|---|
| Owner workflow or lane | <workflow/lane id> |
| Current status | <done / pending / blocked / warning / proposal-only> |
| Completed | <specific completed work> |
| Pending | <specific remaining work or none> |
| Blocker in plain English | <real blocker or none> |
| Main can resolve automatically? | <yes/no and how> |
| Randall approval required? | <yes/no and why> |
| Next action | <single next step> |
| Proof | `<artifact/proposal/validator>` |
| Continuity home | `<path or proposal id>` |
| Stop line | <authority boundary> |
```

## Non-Workflow Matrix Template

Use this compact block in daily memory or a project note:

```md
## <Work Item> - <HH:MM UTC>

| Field | Status |
|---|---|
| Current state | <done / pending / blocked / watch / promote-to-workflow> |
| Completed | <specific completed work> |
| Pending | <specific remaining work or none> |
| Blocker / owner decision | <specific blocker or none> |
| Next action | <single next step> |
| Proof | `<artifact/proposal/validator>` |
| Continuity home | `<path or proposal id>` |
| Stop line | <authority boundary> |
```

## Workflow

1. Identify the real project, handoff, or work-item boundary.
2. Decide whether daily memory alone is enough.
3. If not, create or update a dedicated project checkpoint.
4. Capture only the minimum needed to resume cleanly.
5. Link to canonical notes, scripts, skills, or artifacts instead of copying them.
6. If a lesson is truly durable, route it through `memory-continuity-manager`.
7. If non-workflow work starts accumulating recurring pending rows, recommend PM/workflow promotion.
8. For handoffs, make the next automatic action and the true owner-gated stop line explicit.

## Anti-Patterns

Avoid:
- duplicating full research notes into project checkpoints
- turning project notes into diaries
- copying large task lists from other notes
- inventing status language that obscures reality
- keeping multiple conflicting pickup points for the same project
- leaving non-workflow follow-up only in chat when it has a blocker, pending action, or resume-later value
- asking Randall to resolve blockers that main session can resolve through route refresh, source-open fallback, bounded repair, QA rerun, or continuity update
- using continuity notes as hidden authority for execution, finance/canon/portfolio mutation, config/runtime change, schedule mutation, external delivery, or destructive cleanup

## Output Format

When reporting project continuity or handoff work, use:
- project or work item
- continuity action taken
- where the pickup point now lives
- current state
- next action
- proof
- any blockers or owner-gated stop lines

## Seven-Agent Continuity and Measurement

Main is the router, final QC owner, sole acceptance owner, and final judgment owner for Main plus six configured isolated agents. Preserve the active flows:

- General: Main -> Research Scout when needed -> Implementation-Builder -> QA Red-Team -> Main acceptance -> Docs Continuity Editor -> Main closeout.
- Finance: Main -> Finance Source Scout when needed -> Main analysis -> Finance Red-Team -> Main judgment.

For each material job record parent job/workflow/lane, routing reason, assigned agent/phase, exact write boundary, sources, deliverable, validator/proof, model/effort, sanitized attribution status, QA verdict/findings, Main acceptance proof, rework indicator, final documentation link after acceptance, next agent, and next proof. Do not let agents self-route, self-accept, or use documentation as implied acceptance.

### Reporting Cadence

Daily, consume the existing Fleet Posture only after approved producers have refreshed. Brief utilization, coverage/partial status, Main-accepted outcomes, QA/rework, OAuth advisory state, and sandbox status without inferring an invoice or quota. Weekly, compare accepted outcomes, QA yield, rework, route correctness, time to acceptance, attribution completeness, and labeled token/API-equivalent estimates per accepted outcome. Treat the first two clean cycles as measurement, not a promotion signal for new permanent agents.

Keep telemetry metadata-only. `provider_usage_unavailable` is a valid honest closeout; never retain raw prompts, responses, tool payloads, headers, secrets, credentials, account identifiers, or actual-billing claims. Do not create or mutate a schedule here: route cadence changes through cron governance and explicit approval.

Sandbox status remains a separate, rollback-ready project. Missing sandbox proof must appear as unproven, not blocked fleet performance.

