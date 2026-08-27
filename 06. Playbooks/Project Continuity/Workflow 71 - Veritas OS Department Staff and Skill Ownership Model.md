# Workflow 71 - Veritas OS Department Staff and Skill Ownership Model

## Objective
- Define additional Veritas OS staff lanes as role/department ownership contracts, not autonomous identities with independent authority.
- Assign skills, departments, stop lines, deliverables, and QA expectations so work can run in parallel without unclear ownership or two-writer collisions.

## Current State
- Opened 2026-05-20 22:20 MST after Randall requested a workflow to define additional staff for the OS, with clear skill ownership and departmental organization.
- Veritas main remains the single final integrator, truth surface, queue owner, and authority boundary. Staff lanes are bounded helper roles/subagents/manual IC packages; they do not hold live account authority or owner-approval authority.
- Phase 1 artifact complete as of 2026-05-21 23:25 MST: `tmp/wf71-department-skill-ownership-proposal.json/.md` maps main-session minimal skills, 14 department/staff-lane ownership contracts, 41-skill assignment matrix, workflow owners, split/merge/deprecate candidates, routing rules, handoff template, negative triggers, and stop lines.
- Phase 2 skill-routing/load-budget artifact complete as of 2026-05-21 23:50 MST: `tmp/wf71-skill-routing-load-budget-rules.json/.md` defines main-session minimal routing, positive/negative triggers for 14 departments, load-budgeted handoff template, acceptance checks, global stop lines, and a review-only procedure patch proposal at `legacy tmp artifact tombstoned in state/tmp-lifecycle-deletion-tombstone.json (wf71-load-budget-procedure-patch-proposal.md)`.
- Phase 3A applied as of 2026-05-21 23:58 MST: the load-budget procedure now includes the WF71 Department Routing Gate and positive/negative skill trigger checks. This was a procedure/control-surface thinning apply only; no canon/config/destructive/trade/account/paper edits were made.

## Proposed Department Map

| Department / Staff Lane | Owns | Primary skills / surfaces | Stop lines |
|---|---|---|---|
| Official Source Desk | Company releases, SEC exhibits, presentations, transcripts, source provenance | `sec`, WF70 capture tools, WF65/WF66 artifacts | No invented values; no authority inference; official evidence only |
| Fundamental Research Desk | Business quality, financial metrics, valuation, official bridge interpretation | `veritas-fundamental-pass`, WF65 | Review-only; no deployment approval from fundamentals alone |
| Technical / Entry Discipline Desk | Bands, stops, trend state, no-chase discipline | `veritas-technical-pass`, WF58, Execution Board | No trade/account action; bands do not imply approval |
| Macro / Regime Desk | Macro, rates, commodities, sector context, fund proxies | `veritas-macro-pass`, WF60/WF61 | No sleeve/cash/risk-rule mutation without gated approval |
| Portfolio / Canon Steward | Canon coherence, bounded workspace maintenance, proposal packets | `veritas-portfolio-update`, WF56/WF58/WF64 | No live execution; exact gated apply only |
| Risk and Paper Execution Guard | WF63/WF67 paper-only guardrails, kill switch, audit logs | `wf67-paper-trading-operator`, WF63/WF67 | Paper-only; no live endpoint; exact owner terms required |
| Advisor Alert Desk | Intraday alerts, advisory packets, no-fire downgrade, main-session handoff | WF68, WF55 outcome bridge | Review-only alerting; no automatic paper/live orders |
| Analytics / Probability Desk | State history, readiness, descriptive analytics, validation | WF55/WF69, SQLite/data artifacts | No probability/win-rate/model-readiness claims while WF55 NOT_READY |
| OS Operator / Automation Desk | Cron, workflow registry, skills, process hardening, audits | `openclaw-operator`, `cron-automation-manager`, `workspace-governor` | No auth/config/channel/network/destructive mutation without approval |
| Independent QA Desk | Read-only audit, validator proof, closeout challenge | `workspace-qa-pass`, `disciplined-implementation` for scoped refactor parity, deprecated `code-review-auditor` router only for legacy references | Read-only unless explicitly scoped; no final queue movement |

## Phased Approach

### Phase 0 - Role contract standard
- Define a staff-lane contract template: mission, allowed surfaces, forbidden actions, skills, deliverables, acceptance proof, stop lines, handoff format.
- Acceptance: no lane can claim owner approval, portfolio/trade authority, or final integration authority.

### Phase 1 - Department-to-skill assignment
- Map each installed skill and major workflow to exactly one primary owner lane plus optional secondary consumers.
- Identify orphan skills/workflows and overloaded lanes.
- Acceptance: no ambiguous primary owner for active finance skills/workflows.

### Phase 2 - Subagent handoff templates
- Build file-grounded handoff templates for each lane: inputs to read, outputs to write, forbidden files, acceptance proof, stop conditions.
- Acceptance: helper lanes can be spawned in parallel with disjoint ownership and low merge risk.

### Phase 3 - Parallel execution board
- Create a live assignment surface for current worker lanes: Official Source Desk, Analytics Desk, QA Desk, Operator Desk, etc.
- Acceptance: Active Workflows can point to staff lanes without duplicating all history.

### Phase 4 - Skill hardening / routing
- Update relevant skills where procedural ownership is missing or ambiguous.
- Acceptance: skill descriptions and workflow notes agree on department ownership.

### Phase 5 - Closeout validator
- Add a lightweight checklist/validator for staff-lane packets: required context read, artifact proof, stop lines, authority flags, no hidden final decisions.

## Parallel Completion Design
- Worker 1: skill inventory and department mapping.
- Worker 2: role contract and handoff templates.
- Worker 3: active workflow-to-department mapping.
- Worker 4: independent QA for authority/ownership collisions.
- Veritas main: final synthesis, conflict resolution, Active Workflows integration.

## Outstanding
- Review and apply a small subset of `legacy tmp artifact tombstoned in state/tmp-lifecycle-deletion-tombstone.json (wf71-load-budget-procedure-patch-proposal.md)` only if it reduces load without duplicating governance.
- Decide whether staff lanes should be represented in `IC Project Registry`, Startup Truth Index, or existing workflow notes; avoid creating a new durable staff-control surface unless a validator/procedure truly needs it.
- Later optional: audit every skill body against the WF71 department map; Phase 2 did not re-audit all skill bodies.

## Blockers / Trust Gaps
- Staff lanes must not become separate identities with independent authority.
- Department ownership must not create duplicate canonical truth surfaces.
- External/manual IC lanes remain manual surfaces unless Randall explicitly chooses them.

## Session Load-Budget Rule
- New helper sessions must use `06. Playbooks/Operating Procedures/Subagent Load Budget and Staff Handoff Standard.md` unless Randall explicitly asks for a broad audit.
- Default helper lanes should read 3-8 exact files first, not the entire workspace.
- Broad audit lanes may read more, but must be read-only by default and return a claim matrix plus priority recommendations.
- Veritas main remains the final integrator; staff lanes do not move final queue state or infer owner approval.

## Latest Live-Use Audit - 2026-05-22 16:45 MST
- Small WF71 live-use audit ran against the next WF70/WF72 task. Proof: `tmp/wf71-live-use-audit-wf70-wf72-next-task.json/.md`.
- Result: route the next WF70/WF72 registry-literal closeout as a bounded **Implementation / Refactor Desk** task, with Official Source Desk and OS Operator as secondary consumers and Independent QA as read-only challenger.
- Candidate next pass was `scripts/chain_manifest.py` official-capture registry closeout. It already called `official_capture_period_registry` at import but still carried many static `q1-2026` expected-output literals; the completed closeout preserved manifest output across all windows before any bridge/reconciliation migration.
- Follow-through proof: `tmp/wf70-chain-manifest-registry-closeout.json/.md`; no-drift compare matched across morning, post-close, post-earnings, Sunday, and full windows with no excluded fields. This validated WF71 routing in live workflow use without requiring a new staff registry.
- No new durable staff registry is justified yet; existing WF71 continuity + Active Workflows are sufficient for routing.

## Next Action
- Continue using WF71 department routing/load budgets for future WF70/WF72 flattening. Defer full skill-body audit and any new staff registry unless repeated routing friction appears.

## Key Files
- `AGENTS.md` - orchestration doctrine and helper-lane defaults.
- `SOUL.md` - authority and finance boundary.
- `TOOLS.md` - skill/runtime posture.
- `06. Playbooks/Active Workflows.md` - live workflow control surface.
- `06. Playbooks/IC Project Registry.md` - candidate staff/owner index if kept thin.
- `skills/*/SKILL.md` - skill ownership targets.

## Automation / Refresh Path
- This workflow is operating-model design first. Automation should be limited to inventory, validation, and handoff generation until contracts are accepted.
