---
name: automation-hardening-manager
description: Harden the Veritas OS toward safer automation without forcing premature autonomy. Use when deciding what should run on schedule, what must remain human-gated, how to phase automation rollout, how to define trust gates and ownership boundaries, or when turning a partially manual workflow into a more automated operating path.
---

# Automation Hardening Manager

## Purpose

Move the OS toward better automation by improving architecture, contracts, review surfaces, and trust gates first.

This skill does not exist to maximize automation volume.
It exists to reduce unsafe ambiguity.

## Use This Skill For

Use this skill when:
- a workflow should become more automated over time
- cron windows need design or cleanup
- a manual workflow has become repetitive and should be hardened
- the OS needs a rollout path from manual -> semi-automated -> more autonomous
- an artifact or note layer needs clearer authority and ownership
- a proposed automation change may blur trust boundaries
- you need to decide whether a workflow should use cron, heartbeat, a spawned subagent / detached helper path, or stay manual

Do not use this skill for simple one-off reminders.
Do not use it to justify removing review steps without evidence.

## What This Skill Owns

This skill owns the architecture judgment for automation hardening:
- workflow-window design
- authority boundaries
- artifact contracts
- review surfaces
- trust gates
- rollout phases
- validation expectations

It does not replace:
- `cron-automation-manager` for specific cron design
- `memory-continuity-manager` for memory routing
- `project-continuity-manager` for project pickup points
- `openclaw-operator` for general workspace/runtime hygiene
- a dedicated detached execution substrate when one is actually verified live

## Core Review Questions

For any workflow under consideration, answer these in order:

1. What is the real job?
2. What is the canonical truth layer?
3. What artifacts are generated versus authoritative?
4. What can run safely without human review?
5. What still requires approval?
6. What failures would be silent or dangerous?
7. What validation proves the automation is helping rather than drifting?

If those answers are vague, the workflow is not ready for more autonomy.

## Hardening Workflow

1. Define the workflow boundary.
2. Name the owner layer for each output.
3. Separate:
   - artifact generation
   - review surface generation
   - apply/update actions
   - canonical note or config mutation
4. Decide the current safe automation phase:
   - manual
   - scheduled artifact generation
   - scheduled review surfaces
   - gated apply helpers
   - higher-autonomy maintenance
5. Define trust gates before expanding autonomy.
6. Define the smallest useful schedule.
7. Validate outputs and downgrade confidence honestly when upstream inputs are stale, partial, or manual.
8. Record the result in the relevant project continuity note and daily memory.

For major automation-facing workflows, also make these explicit:
- owner layer
- review window
- stop lines
- surface / handoff posture
- canonical mutation posture
- checkpoint decision
- next pass

## Safe Automation Preference Order

Prefer this progression:
1. stable script output
2. stable scheduled artifacts
3. stable review/checklist surfaces
4. gated patch/apply helpers
5. selective autonomous maintenance only where trust is repeatedly proven

Do not jump from manual directly to silent canonical rewrites.

## Scaling And Repeatability Default

When a workflow is scaling in ticker count, customer/service scenarios, PM lanes, SQL rows, cron windows, or recurring proof passes, assume the next useful improvement is to make the work easier to repeat safely.

Before widening scope, check whether the current manual command sequence should become:
- a phase runner
- a manifest-driven command set
- a validator or acceptance harness
- a review-only packet generator
- a PM/heartbeat handoff artifact
- a skill/runbook procedure

Default posture:
- report-only first
- explicit stop lines in every summary artifact
- `--apply` or external/runtime/customer/finance actions only with exact approval scope
- boot/core Markdown files stay thin routers, not procedure dumps
- generated proof defaults to JSON/SQLite; Markdown sidecars are opt-in only when a real human-review route exists
- daily memory records checkpoints; durable skills/runbooks own repeatable procedure

For WF78-style finance scaleout and WF75/Retail-SaaS scaleout, do not rely on remembered command order. Build or extend a reusable runner before the work becomes multi-batch.

### Cron / skill / SQL-consumer hardening route

After major cron-load reductions, skill-routing changes, or WF72 SQL consumer-authority proof changes, run:

```powershell
python scripts\automation_stack_hardening_pass.py --write --validate
```

The pass checks the JSON cron ledger, key automation/cron/implementation/QA skills, and WF72 A2 readiness/completion. It is report-only and may not mutate cron definitions, skill files, SQL/cache rows, canon, portfolio, customer surfaces, paper/live/account state, runtime config, or approval state.

As of 2026-06-04, WF72 A2 is live complete when the pass reports `wf72_a2_live_complete=true`: 265 fallback keys, hash manifest, Go guard `ok`, no missing fallback rows, no stale/unsafe rows, and Python fallback retained. The next automation hardening step is quick routing over existing proof routes, not SQL-first promotion. Any consumer promotion, Python fallback retirement, SQL write/import, customer-facing SQL output, or canon/portfolio mutation still needs a separate exact gate.

Quick-routing posture:
- prefer a thin wrapper or procedure over existing scripts before adding a new control surface
- route "what next?" through automation stack hardening, artifact cockpit/answer contracts, PM/cron scorecards, WF78 runner, and WF67 manager as applicable
- source-open exact artifacts before material claims
- keep generated routing packets review-only with explicit authority boundaries

### Retail-grade truth routing route

When Randall prioritizes SQL automation, truth routing, or retail-grade answer paths, make `scripts\retail_truth_routing_contract.py --write --validate` the Phase 1 owner before broad implementation. The route is a report-only contract over existing proof surfaces:
- Phase 1: route contract and stop lines
- Phase 2: source-open SQL-assisted reads
- Phase 3: PM-owned queue/status refreshes
- Phase 4: answer-path regression harness
- Phase 5: customer-safe export gate, requiring owner decision

PM may own queue state, stale proof, blocker registers, and review-packet refresh handoffs. PM may not own final truth claims, SQL-first promotion, customer/export authorization, canon/portfolio mutation, paper/live/account action, or owner approval.

### WF78 tier-funnel routing / monitoring / promotion route

When hardening WF78 routing, monitoring, or finance-promotion work, use the local tier-funnel machinery as the owner path. Do not install or depend on unaudited external finance skills unless Randall explicitly approves the exact package and risk.

Run order:
1. `python scripts\wf78_tier_capacity_policy_gate.py --write --write-db --validate`
2. `python scripts\wf78_tier_funnel_contract.py --write --validate`
3. `python scripts\wf78_tier_funnel_promotion_gate.py --write --validate`
4. `python scripts\wf78_tier_a_competitive_promotion_gate.py --write --validate`
5. `python scripts\wf78_funnel_owner_decision_packet.py --write --validate`
6. `python scripts\automation_stack_hardening_pass.py --write --validate`

Promotion questions:
- Tier D -> C: is this clean enough to monitor cheaply?
- Tier C -> B: does this deserve scarce research time?
- Tier B -> A: does this deserve one of 25 scarce Tier A seats more than current alternatives?

Monitoring posture:
- D names route to identity/source/provider/duplicate repair or reject.
- C names route to monitor, repair, theme watch, candidate, or decay.
- B names route to candidate, validated, stale, challenged, or reject-to-C.
- A names route to nominee, watch, ready, deploy-packet, hold, challenged, or demote.

Hardening rule:
- gate outputs create evidence queues and owner-decision packets only
- `eligible_for_admission` and `eligible_for_owner_approval` are eligibility verdicts, not approval
- C->B remains capped at 15 nominations per 100-name batch and Tier B capacity 50
- B->A remains capped at Tier A capacity 25 and requires open seat or +5 challenger win plus owner approval
- `A-DEPLOY` means approval-ready packet only and never order authority

Stop lines:
- no D/C/B/A promotion from score, checklist completion, legacy tier label, macro overlay, or ClawHub/web pattern
- no import/apply, canon/portfolio mutation, production answer-path expansion, paper/live/account action, or approval inference
- stale or untrusted gate artifacts downgrade owner packets to no-action or needs-evidence, not approval

## WF75 Queue / Agent-Task Pattern

For WF75 and the Generic Intelligence / SMB Workflow Clarity lane, adopt queue-skill patterns only inside Veritas-owned artifacts:
- queue item has one lane, owner, priority, status, blocker reason, next safe action, retry/dead-letter state, source artifacts, and stop lines
- retries may refresh proof or regenerate review packets only
- failed queue items move to blocker/dead-letter review instead of repeating silently
- main session may start bounded helper lanes when the PM handoff explicitly allows it
- heartbeat and cron may wake or queue the main session, but they must not execute the service phase inline

Allowed autonomous queue movement:
- refresh stale proof artifacts
- rebuild review-only PM packets
- regenerate local renderer/validator outputs
- classify blockers and raise handoff packets

Blocked autonomous queue movement:
- real customer intake
- customer-data retention
- credential access
- external delivery
- customer outreach or outbound messaging
- customer-system implementation
- public launch claims
- canon/portfolio mutation
- paper/live/account action
- owner approval inference

## Product-Manager / Evaluation Pattern

Use product-management patterns to make WF75 more commercially coherent:
- define buyer pain, offer, activation proof, time-to-value, pilot deliverables, exclusions, roadmap, and next validation artifact
- keep Retail Finance as P0 continuity and SMB Lead Rescue as the P1 monetization side-lane unless Randall changes the queue
- never let product packaging outrun trust gates

Use evaluation patterns to make WF75 more reliable:
- test clean scenarios and seeded-bad claims
- require renderer/export regression before PM handoff claims
- require `veritas_harness_scorecard.py --run --write --validate` before readiness claims after material WF75 changes
- classify warnings honestly; warning-only can support internal review but cannot support customer/public claims

## WF75 Workflow-Automation Blueprint Pattern

When WF75 reviews n8n, Zapier, Make, Pipedream, or business-automation skills, copy only the architecture pattern into Veritas-owned artifacts.

Required design fields before any automation can move past concept:
- trigger type and timezone
- input contract and required fields
- dedup key
- idempotency store
- ordered steps with one purpose per step
- fallback path for every step
- retry/backoff policy
- audit log / run status fields
- human review queue
- dry-run activation state
- tool candidate and implementation gate

Allowed now:
- design dry-run automation blueprints
- compare tool fit for Zapier, Make, n8n, local Python, or manual process
- model sanitized/anonymous fixtures
- generate review-only owner attention queues, reminder plans, and implementation sequences

Blocked until future explicit gates:
- automation-platform credentials
- CRM/phone/email/ad/payment/POS/payroll credentials
- real customer data ingestion or retention
- outbound calls, texts, emails, posts, or review requests
- customer-system writeback or implementation
- public launch, external delivery, ROI/revenue guarantee, or legal/compliance/security readiness claim

## Mechanism Choice

Use this routing logic:

- **heartbeat** -> lightweight maintenance only
- **cron** -> exact recurring windows, reminders, scheduled artifact generation
- **detached helper lane** -> spawned subagent or other verified detached path when bounded work needs one owner context outside the main lane
- **manual** -> anything with weak trust, sparse validation, or high consequence

Do not assume `TaskFlow` is a live approved mechanism in this workspace unless it is explicitly validated in the current operator protocol. If that proof is absent, default to a spawned subagent or manual path instead.

If a workflow mutates canonical notes or high-consequence config, default to manual or gated apply until proven otherwise.

## Trust Gates

Before widening autonomy, verify:
- upstream artifacts are fresh enough
- sources are not silently conflicting
- validation exists and is actually run
- the workflow has one clear owner per window
- note ownership is explicit
- failure states are visible
- the rollback or correction path is clear

If any of these are weak, keep the workflow in a harder-gated phase.

## Veritas Harness Scorecard Gate

For rapidly expanding workflows, run the unified harness before claiming a
surface is ready:

```powershell
python scripts\veritas_harness_scorecard.py --run --write --validate
```

Use the scorecard as review proof only. A `warning` status can be acceptable
when the consuming workflow explicitly allows warning-only readiness gaps, but
a hard failure blocks readiness claims until the failing producer, validator, or
authority flag is repaired.

For tool/banner errors, classify before escalating:

```powershell
python scripts\veritas_harness_failure_classifier.py --text "<error text>" --write
```

This separates harmless Windows shell/path issues from validator warnings,
real breakage, stale-readiness gaps, and authority regressions.

## Output Format

When using this skill, report in this order:
- workflow under review
- current phase
- recommended next phase
- safe automation boundary
- schedule recommendation
- owner layer
- review window
- stop lines
- trust gates still missing
- validation or evidence

## Machine-readable trust block pilot

Workflow 29 Phase 4 bounded pilot:
- producer: `python scripts/automation_trust_block.py --input <trust-block-input.json> --write`
- default artifact: `tmp/automation-trust-block.json`

Required trust-block fields for this pilot:
- `workflow`
- `producer_skill`
- `reviewed_at_utc`
- `current_phase`
- `recommended_next_phase`
- `trust_level` (`unsafe` / `review_required` / `automation_ready`)
- `decision` (`approve` / `deny` / `defer`)
- `consumer_posture` (`read_only` / `review_only` / `blocked`)
- `safe_automation_boundary`
- `owner_layer`
- `review_window`
- `validation_evidence[]`
- `trust_gates_passed[]`
- `trust_gates_missing[]`
- `stop_lines[]`
- `notes[]`

Pilot approval rule:
- only `decision=approve` + `trust_level=automation_ready` + zero `trust_gates_missing` may produce `status=ok`
- pilot consumers may treat the block as permission for **read-only gating decisions only**
- this trust block does **not** authorize canonical note mutation, destructive apply steps, or broader scheduler autonomy

## Memory Update Rules

- log meaningful automation architecture decisions in `memory/YYYY-MM-DD.md`
- keep per-project rollout state in the relevant `06. Playbooks/Project Continuity/` note when the work spans sessions
- promote durable automation policy only when it is clearly stable enough to survive many sessions

## Veritas portfolio-agent handoff

For WF64/WF56 bounded autonomous workspace portfolio management, route execution governance to `veritas-bounded-portfolio-agent`. This skill keeps the general automation-hardening questions; the portfolio-agent skill owns category scopes, exact apply gates, standing-approval artifacts, post-apply validation, and trading stop lines.
