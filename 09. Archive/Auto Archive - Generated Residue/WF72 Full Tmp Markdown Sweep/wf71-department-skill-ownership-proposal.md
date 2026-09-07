# WF71 Department / Skill Ownership Proposal

Status: **review-only proposal**. This artifact does **not** authorize config/auth/channel changes, destructive cleanup, canonical portfolio/canon mutation, live trading, paper execution, brokerage/account action, money movement, or owner-approval inference.

## Decision

Represent Veritas OS staff as bounded **departments/helper lanes**, not separate autonomous identities. Veritas main remains the final integrator, queue owner, truth surface, and owner-approval boundary.

Sources inspected:
- `SOUL.md`
- `AGENTS.md`
- `TOOLS.md`
- `USER.md`
- `06. Playbooks/Project Continuity/Workflow 71 - Veritas OS Department Staff and Skill Ownership Model.md`
- `06. Playbooks/Active Workflows.md`
- `tmp/wf72-full-restructure-synthesis.md`
- installed skill `SKILL.md` description inventory

## Authority flags

| Flag | Value |
|---|---:|
| Review-only | true |
| Main-session final integration required | true |
| Config/auth/channel mutation allowed | false |
| Destructive cleanup allowed | false |
| Canonical note mutation allowed | false |
| Portfolio mutation allowed | false |
| Trade/account action allowed | false |
| Paper execution authorized by this artifact | false |
| Owner approval inferred | false |

## Minimal main-session skill set

Main should load only the exact skill needed for the immediate task.

| Skill | Use |
|---|---|
| `veritas-response-contract` | Owner-facing status, closeout, audit/result summary, recommendation response. |
| `ic-swarm-orchestrator` | Multi-lane orchestration, worker/QA contracts, fallback order, completion handshake. |
| `project-continuity-manager` | Workflow pickup state and continuity-note changes. |
| `memory-continuity-manager` | Daily/durable memory routing after material work. |
| `openclaw-operator` | Runtime/control-plane/workspace operating-file tasks only. |

## Department ownership map

| Department | Mission | Primary skills | Workflow surfaces | Hard stop lines |
|---|---|---|---|---|
| Official Source Desk | Capture official company/SEC evidence and provenance. | `sec` | WF70, WF65, WF66 | No invented values; no bridge-present-equals-reconciled shortcut; no approval/canon mutation from capture alone. |
| Fundamental Research Desk | Business quality, metrics, valuation, earnings bridge. | `veritas-fundamental-pass`, `veritas-post-earnings-sync` | WF65, WF66, WF70 | Fundamentals alone do not grant deployability; no ungated canon/portfolio mutation; no trade/account authority. |
| Technical / Entry Discipline Desk | Bands, stops, trend state, repair/block/no-chase labels. | `veritas-technical-pass` | WF58, WF56, WF64 | Bands do not imply approval; no paper/live order; no account action. |
| Macro / Regime Desk | Rates, inflation, dollar, commodities, sector regime. | `veritas-macro-pass` | WF60, WF61, WF68 | No sleeve/cash/risk-rule mutation; no automatic fund additions; stale macro must degrade. |
| Portfolio / Canon Steward | Board/snapshot/watchlist canon, proposal packets, gated maintenance. | `veritas-portfolio-update`, `veritas-bounded-portfolio-agent`, `veritas-positioning-pass`, `veritas-financial-planning-pass` | WF56, WF58, WF62, WF64 | No live trading/account/money movement; no inferred approval; generated packet is not canon. |
| Advisor Alert Desk | Intraday alert semantics, no-fire downgrades, advisor handoffs. | `automation-hardening-manager` | WF68, WF41, WF55 | No channel/config/auth mutation; no canon/outcome mutation from alert alone; no paper/live order. |
| Risk and Paper Execution Guard | WF63/WF67 paper-only guardrails, kill switch, audit logs, reconciliation. | `wf67-paper-trading-operator` | WF63, WF67 | Paper-only; no live endpoint/credentials; no money/account mutation; this proposal grants no paper execution. |
| Analytics / Probability Desk | State history, outcome retention, SQLite/data artifacts, readiness gates. | `SQLite` | WF55, WF69 | No predictive readiness/win-rate claims while WF55 is `NOT_READY`; no model-driven portfolio action. |
| OS Operator / Automation Desk | Cron/runtime/workflow registry/process hardening. | `openclaw-operator`, `cron-automation-manager`, `workspace-governor`, `openclaw-troubleshooter`, `windows-powershell-workspace`, `obsidian` | WF59, WF72, cron monitors | No config/auth/channel/service mutation or move/delete/archive without approval; no secret exposure. |
| Implementation / Refactor Desk | Scripts, validators, shared helpers, behavior-preservation proof. | `disciplined-implementation`, `safe-refactor-planner` | WF69, WF70, WF72 | No broad rewrites without inventory; no high-authority refactor without side-by-side proof and rollback posture. |
| Independent QA Desk | Read-only closeout challenge, authority collision scan, validator coverage. | `workspace-qa-pass`, `code-review-auditor` | closeout audits, WF71, WF72 | Read-only unless explicitly scoped; no final queue movement; no fake-green status. |
| Packaging / Publishing Desk | PDFs, decks, weekly brief deliverables from approved sources. | `veritas-pdf-brief`, `veritas-investment-deck`, `veritas-weekly-brief` | weekly/deck/PDF surfaces | No send/publish/share without approval; reports do not outrank canon or imply approval. |
| Continuity / Procedure Desk | Memory, project pickup, SOPs, skill/procedure hygiene. | `memory-continuity-manager`, `project-continuity-manager`, `operating-procedure-repository-manager`, `veritas-self-improvement` | `memory/`, `MEMORY.md`, Project Continuity, SOPs, skills | No duplicate memory/control plane; no bloated project bureaucracy; no skill publication/install without approval where external. |
| External / Bundled Utility Desk | Generic bundled tools only when explicitly triggered. | `github`, `healthcheck`, `node-connect`, `browser-automation`, `clawhub`, `taskflow`, `taskflow-inbox-triage`, `weather` | external/task-specific surfaces | No external/public action without approval; no blind ClawHub installs; no unrelated skill loading. |

## Skill assignment matrix

| Skill | Primary owner |
|---|---|
| `automation-hardening-manager` | Advisor Alert Desk |
| `browser-automation` | External / Bundled Utility Desk |
| `clawhub` | External / Bundled Utility Desk |
| `code-review-auditor` | Independent QA Desk; secondary Implementation / Refactor Desk |
| `cron-automation-manager` | OS Operator / Automation Desk |
| `disciplined-implementation` | Implementation / Refactor Desk |
| `github` | External / Bundled Utility Desk |
| `healthcheck` | External / Bundled Utility Desk |
| `ic-swarm-orchestrator` | Main-session orchestration surface |
| `memory-continuity-manager` | Continuity / Procedure Desk; main-session minimal set |
| `node-connect` | External / Bundled Utility Desk |
| `obsidian` | OS Operator / Automation Desk |
| `openclaw-operator` | OS Operator / Automation Desk; main-session minimal set for runtime tasks |
| `openclaw-troubleshooter` | OS Operator / Automation Desk |
| `operating-procedure-repository-manager` | Continuity / Procedure Desk |
| `project-continuity-manager` | Continuity / Procedure Desk; main-session minimal set |
| `safe-refactor-planner` | Implementation / Refactor Desk |
| `sec` | Official Source Desk |
| `skill-creator` | Continuity / Procedure Desk; external publication/install mechanics only when approved |
| `SQLite` | Analytics / Probability Desk |
| `taskflow` | External / Bundled Utility Desk |
| `taskflow-inbox-triage` | External / Bundled Utility Desk |
| `technical-chart-pass` | Technical / Entry Discipline Desk as deprecated fallback only |
| `veritas-bounded-portfolio-agent` | Portfolio / Canon Steward |
| `veritas-financial-planning-pass` | Portfolio / Canon Steward |
| `veritas-fundamental-pass` | Fundamental Research Desk |
| `veritas-investment-deck` | Packaging / Publishing Desk |
| `veritas-macro-pass` | Macro / Regime Desk |
| `veritas-pdf-brief` | Packaging / Publishing Desk |
| `veritas-portfolio-update` | Portfolio / Canon Steward |
| `veritas-positioning-pass` | Portfolio / Canon Steward |
| `veritas-post-earnings-sync` | Fundamental Research Desk |
| `veritas-response-contract` | Main-session response surface; secondary all departments for closeout style |
| `veritas-self-improvement` | Continuity / Procedure Desk |
| `veritas-technical-pass` | Technical / Entry Discipline Desk |
| `veritas-weekly-brief` | Packaging / Publishing Desk; secondary Macro / Regime Desk |
| `weather` | External / Bundled Utility Desk |
| `wf67-paper-trading-operator` | Risk and Paper Execution Guard |
| `windows-powershell-workspace` | OS Operator / Automation Desk |
| `workspace-governor` | OS Operator / Automation Desk |
| `workspace-qa-pass` | Independent QA Desk |

## Workflow primary owners

| Workflow | Primary owner |
|---|---|
| WF55 | Analytics / Probability Desk |
| WF56 | Portfolio / Canon Steward |
| WF58 | Technical / Entry Discipline Desk with Portfolio / Canon Steward consumer |
| WF59 | OS Operator / Automation Desk with Continuity / Procedure Desk consumer |
| WF60 | Macro / Regime Desk |
| WF61 | Macro / Regime Desk |
| WF62 | Portfolio / Canon Steward |
| WF63 | Risk and Paper Execution Guard |
| WF64 | Portfolio / Canon Steward |
| WF65 | Fundamental Research Desk |
| WF66 | Official Source Desk with Fundamental Research Desk consumer |
| WF67 | Risk and Paper Execution Guard |
| WF68 | Advisor Alert Desk |
| WF69 | Analytics / Probability Desk with Implementation / Refactor Desk support |
| WF70 | Official Source Desk |
| WF71 | Main-session operating model; Independent QA Desk challenges |
| WF72 | OS Operator / Automation Desk with Implementation / Refactor Desk support |

## Split / merge / deprecate candidates

### Split / clarify ownership

- `veritas-weekly-brief` spans macro, packaging, and portfolio recap. Keep Packaging / Publishing as primary; Macro and Portfolio provide input sections.
- `veritas-portfolio-update` overlaps bounded apply and positioning. Keep board/canon sync here; exact gated applies belong to `veritas-bounded-portfolio-agent`; recommendation synthesis belongs to positioning/planning.
- `automation-hardening-manager` applies to both alert automation and OS automation. Primary for Advisor Alert; OS Operator uses it secondarily for rollout/trust-gate design.

### Merge / consolidate candidates

- WF70 capture scripts should converge around `scripts/official_ir_capture_common.py` / metadata-driven runner while preserving root CLI compatibility.
- Chain manifests and dashboard builders should gradually move into `scripts/veritas_os/chain` and `scripts/veritas_os/dashboard`, with old/new side-by-side proof before behavior switch.

### Deprecate / demote

- `technical-chart-pass`: keep as deprecated generic fallback only. Use `veritas-technical-pass` for Veritas board-sync, entry-band, and deployment-state work.
- Generic bundled external/channel skills: keep out of standing Veritas routing unless an explicit task trigger and approval boundary exist.

### Orphan / low-clarity surfaces

- `browser-automation`: proposed owner External / Bundled Utility Desk; stop on login/payment/account changes unless explicitly approved.
- `taskflow` / `taskflow-inbox-triage`: proposed owner External / Bundled Utility Desk; avoid duplicate long-running workflow state unless Randall explicitly wants TaskFlow.
- `skill-creator`: proposed owner Continuity / Procedure Desk; treat publication/install as control-plane sensitive.

## Routing rules

1. Load only the exact skill needed for the immediate task; do not load finance spine by habit.
2. Every helper lane gets one primary department, explicit files to read first, deliverables, forbidden surfaces, acceptance proof, and stop lines.
3. Assign exactly one primary owner for a workflow/artifact; list secondary consumers separately.
4. Generated artifacts can inform canon but do not become canon or owner approval by themselves.
5. Substantial workflow advancement should use bounded worker lane plus independent read-only QA when closeout risk is material, with Veritas main final integration.
6. Cron may generate review packets/proposals/proof; cron must not apply canonical portfolio/intelligence edits or portfolio mutations unless an explicit standing-approved exact gated path applies and validators pass.
7. Manual IC/challenger tools are not automatic OpenClaw helper lanes; use only when Randall chooses them.

## Standard department handoff template

```md
# <Department> helper handoff

Role: You are the <department> lane for <workflow/task>; you are not Veritas main.

Read first:
- SOUL.md
- AGENTS.md
- TOOLS.md
- USER.md
- <relevant workflow continuity note>
- 06. Playbooks/Active Workflows.md
- <exact artifacts/scripts named in task>

Owned surfaces:
- <specific tmp/script/note surfaces the helper may inspect or write>

Forbidden surfaces:
- config/auth/channel/service/runtime mutation
- destructive moves/deletes/archive
- trade/account/brokerage/money movement
- canonical portfolio/canon mutation unless exact gated task says so
- final queue movement

Deliverables:
- <artifact path 1>
- <artifact path 2>
- concise final claim matrix

Acceptance proof:
- validators/tests or direct inspection named
- authority flags hard-false
- source/provenance captured
- residual risks listed

Stop conditions:
- missing required source
- authority ambiguity
- validator failure not understood
- would need forbidden mutation
- two-writer collision risk

Final response:
- what changed/found
- proof
- risks/blockers
- next recommendation
```

## Negative triggers

- Do not spawn a department lane for a simple one-step lookup/edit that main can safely do.
- Do not use Official Source Desk to infer missing financial values or reconcile by assumption.
- Do not use Fundamental Research Desk to approve deployment without technical, portfolio, risk, and owner gates.
- Do not use Technical / Entry Desk to place, preview as approved, or imply trades.
- Do not use Macro / Regime Desk to mutate cash, sleeve, or risk rules.
- Do not use Portfolio / Canon Steward for live brokerage/account actions or ungated canon writes.
- Do not use Advisor Alert Desk for external delivery/channel expansion without approval.
- Do not use Risk and Paper Execution Guard without WF67 scoped request, paper endpoint, fresh kill switch, guard validation, and audit proof.
- Do not use Analytics / Probability Desk to claim predictive readiness while WF55 is `NOT_READY`.
- Do not use OS Operator / Automation Desk to mutate config/auth/channel/service or delete/move files without explicit approval.
- Do not use Implementation / Refactor Desk to reorganize high-authority scripts without side-by-side proof and rollback posture.
- Do not use Independent QA Desk as a writer or final decision maker.
- Do not use Packaging / Publishing Desk to publish, send, or make reports canonical.
- Do not use External / Bundled Utility Desk unless the task explicitly needs that external tool surface.

## Global stop lines

- No separate autonomous identities or independent authority for staff lanes.
- No duplicate canonical truth surfaces.
- No owner approval inference from confidence, score, clean validation, ranking, or packet quality.
- No live trading, brokerage/account action, money movement, live credentials/endpoints, or real-account mutation.
- No paper submit/cancel/sell except through existing WF67 guardrails and separate scoped artifacts; this proposal grants none.
- No config/auth/channel/network/service/runtime mutation without explicit approval.
- No destructive cleanup, move, delete, archive, or rename without reference checks and owner approval.
- No canonical portfolio/canon mutation outside exact scoped approved gate with validator proof and audit trail.
- Veritas main session must perform final synthesis and queue/control-surface updates.

## Recommended next steps

1. Main session review this packet for authority collisions.
2. If accepted, promote the department map into a thin WF71 operating surface or IC Project Registry lane index without duplicating Active Workflows history.
3. Build department-specific handoff snippets for the highest-use lanes: Official Source, Portfolio/Canon, Advisor Alert, Risk/Paper Guard, Independent QA, OS Operator.
4. Add a lightweight staff-lane packet validator/checklist before updating skill descriptions or workflow routing.

## Known limits

- This artifact maps skill descriptions and live workflow notes; it did not read every full skill body or every workflow continuity note.
- No skills were edited and no routing/config changes were applied.
- Department ownership is a proposal until main-session review/acceptance.
