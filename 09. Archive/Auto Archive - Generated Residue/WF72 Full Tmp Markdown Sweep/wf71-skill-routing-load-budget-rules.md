# WF71 Skill Routing / Load-Budget Rules

Status: **review-only proposal**. No procedure edits, canon mutation, config/auth/channel/service change, destructive cleanup, paper/live order, account action, money movement, or owner-approval inference were applied.

## Decision

Integrate WF71 department routing with the existing Subagent Load Budget standard by using a two-gate route: first decide whether main session can handle the task, then assign exactly one department/helper lane with a small file-grounded load budget if delegation is warranted.

## Main-session minimal routing

- Main keeps final synthesis, truth integration, queue/control-surface decisions, owner-facing response, authority-boundary judgment, and quick bounded fixes.
- Delegate only when the task is multi-artifact, proof-heavy, implementation-heavy, broad-inspection, or benefits from independent QA.
- Do not delegate one-step lookups/edits, ambiguous authority decisions, tasks without exact read-first files, or any lane that would decide owner approval/final queue priority.

### Minimal main skills

- `veritas-response-contract` - positive: owner-facing status/closeout/recommendation summary needs proof-risk-next-action structure / negative: routine internal inspection or artifact drafting without final response need
- `ic-swarm-orchestrator` - positive: multi-lane worker/QA orchestration with handoff contracts / negative: single helper with clear existing template or simple main-session task
- `project-continuity-manager` - positive: workflow pickup state or continuity note update is part of closeout / negative: temporary artifact creation that does not change workflow truth
- `memory-continuity-manager` - positive: material lesson/status needs daily or durable memory routing / negative: minor local artifact with no future pickup value
- `openclaw-operator` - positive: runtime/control-plane/workspace operating-file task / negative: finance research, portfolio judgment, or external account action

## Department trigger tests

### Official Source Desk
Positive triggers:
- SEC/company IR evidence capture
- official filing/presentation/transcript provenance
- field freshness/status matrix
Negative triggers:
- infer undisclosed values
- make deployment/canon decisions
- use non-official source as authoritative without labeling
Default load budget: `3-8` files; skill route: `sec`; output: official-source packet or proof matrix.

### Fundamental Research Desk
Positive triggers:
- business quality/valuation/earnings interpretation
- fundamental metric bridge with source quality
- base/bull/bear research pass
Negative triggers:
- approve deployment from fundamentals alone
- mutate canon without separate gate
- place or imply trades
Default load budget: `4-8` files; skill route: `veritas-fundamental-pass`; output: research pass or scorecard.

### Technical / Entry Discipline Desk
Positive triggers:
- entry band/stop/no-chase/trend-state review
- technical-state conflict check
- repair/block label validation
Negative triggers:
- order placement
- treat bands as approval
- paper/live execution preview as approved
Default load budget: `4-8` files; skill route: `veritas-technical-pass`; output: technical pass or band/status conflict report.

### Macro / Regime Desk
Positive triggers:
- rates/inflation/dollar/commodities/sector regime context
- macro section for weekly/positioning packet
Negative triggers:
- cash/sleeve/risk-rule mutation
- automatic diversification addition
- stale macro treated as current
Default load budget: `3-7` files; skill route: `veritas-macro-pass`; output: macro regime pass.

### Portfolio / Canon Steward
Positive triggers:
- portfolio board/snapshot/watchlist reconciliation
- capital deployment proposal
- exact gated workspace maintenance proposal
Negative triggers:
- live brokerage/account/money movement
- generated packet becomes canon by itself
- ungated cash/risk/execution entitlement change
Default load budget: `5-8` files; skill route: `veritas-portfolio-update or veritas-bounded-portfolio-agent by scope`; output: review packet or exact gated patch proposal.

### Advisor Alert Desk
Positive triggers:
- intraday alert semantics/no-fire downgrade
- advisor packet/handoff status
- alert router acceptance criteria
Negative triggers:
- channel/config/auth expansion
- canon/outcome mutation from alert alone
- paper/live order action
Default load budget: `4-8` files; skill route: `automation-hardening-manager`; output: alert/handoff packet.

### Risk and Paper Execution Guard
Positive triggers:
- WF63/WF67 paper-only guard validation
- paper request preview with kill switch/audit proof
- paper/live isolation check
Negative triggers:
- live endpoint/credentials
- money/account settings/close-position endpoints
- paper execution without scoped artifact and fresh kill switch
Default load budget: `5-8` files; skill route: `wf67-paper-trading-operator`; output: paper guard report/request preview.

### Analytics / Probability Desk
Positive triggers:
- state history/outcome retention/data contract validation
- SQLite query/report
- descriptive analytics readiness
Negative triggers:
- predictive win-rate/readiness claims while WF55 NOT_READY
- model-driven portfolio action
- hindsight outcome rewrite
Default load budget: `3-8` files; skill route: `SQLite`; output: data/validator report.

### OS Operator / Automation Desk
Positive triggers:
- cron/runtime/workflow registry/process hardening
- PowerShell/workspace operating proof
- Obsidian/CLI runtime issue
Negative triggers:
- config/auth/channel/service mutation without approval
- move/delete/archive without approval
- secret exposure
Default load budget: `3-8` files; skill route: `openclaw-operator, cron-automation-manager, workspace-governor, or windows-powershell-workspace by exact task`; output: patch proposal, validation, or runtime audit.

### Implementation / Refactor Desk
Positive triggers:
- script/validator/helper implementation
- small refactor with behavior-preservation proof
- side-by-side migration proof
Negative triggers:
- broad rewrite without inventory
- high-authority script reorg without rollback/QA
- final closeout without tests
Default load budget: `4-8` files; skill route: `disciplined-implementation or safe-refactor-planner`; output: patch plus tests/proof.

### Independent QA Desk
Positive triggers:
- closeout challenge
- authority collision scan
- validator/proof coverage audit
Negative triggers:
- write implementation unless explicitly scoped
- move final queue state
- green status without file-backed proof
Default load budget: `3-8 target files` files; skill route: `workspace-qa-pass or code-review-auditor`; output: read-only claim matrix.

### Packaging / Publishing Desk
Positive triggers:
- PDF/deck/weekly brief packaging from approved sources
- fixed-layout summary artifact
Negative triggers:
- send/share/post without approval
- report outranks canon
- canonical mutation
Default load budget: `4-8` files; skill route: `veritas-pdf-brief, veritas-investment-deck, or veritas-weekly-brief`; output: packaged artifact with source links.

### Continuity / Procedure Desk
Positive triggers:
- daily/durable memory route
- project pickup checkpoint
- SOP placement/classification
- skill/procedure hygiene proposal
Negative triggers:
- duplicate control plane
- doctrine rewrite without clear need
- external skill install/publication without approval
Default load budget: `3-8` files; skill route: `memory-continuity-manager, project-continuity-manager, operating-procedure-repository-manager, or veritas-self-improvement`; output: thin checkpoint/procedure proposal.

### External / Bundled Utility Desk
Positive triggers:
- explicit user/task need for browser/github/weather/taskflow/clawhub/node/healthcheck
Negative triggers:
- blind external install/action
- public/account/channel write without approval
- unrelated skill loading
Default load budget: `task-specific minimum` files; skill route: `explicit utility skill only`; output: tool-specific result with provenance.

## Load-budgeted department handoff template

```md
# <Department> helper handoff - load-budgeted

Role: You are the <department> lane for <workflow/task>; you are not Veritas main and cannot move final queue state.
Objective: <one-sentence objective with exact deliverable>

Read first (normal 3-8 exact files; broad audit 10-15 max):
- SOUL.md or cited hard boundaries only if pasted context insufficient
- AGENTS.md or cited orchestration rules only if needed
- TOOLS.md runtime notes only if runtime/tooling matters
- <relevant workflow continuity note>
- <target artifacts/scripts>
- <one relevant skill SKILL.md max unless explicitly broad>

Allowed actions:
- read/inspect named workspace files
- write named tmp artifacts or exact patch proposals
- run reversible local validators/tests inside workspace when needed

Forbidden actions / stop lines:
- config/auth/channel/network/service/credential mutation
- destructive moves/deletes/archive/renames
- live brokerage/account/money movement
- paper order action outside WF67 guardrails and separate scoped artifact
- canonical portfolio/canon mutation unless exact approved gated apply is named
- final queue/control-surface movement

Output contract:
- artifact path(s) or concise final response
- claim matrix where audit/QA
- authority flags
- proof/tests/direct inspection
- residual risks/blockers
- next recommended main-session action

Acceptance proof:
- read-first list stayed within budget or justified exception
- one primary department/owner named
- secondary consumers listed without writer collision
- JSON parses if JSON artifact is produced
- tests/validators or direct inspection named
- stop lines hard-false for external/destructive/account/config authority

Timeout / partial output: If blocked or long-running, write partial artifact with inspected files, current findings, blocker, and safe next action.
Merge expectation: read-only report, tmp artifact write, patch proposal, or implementation with tests. Main session integrates.
```

## Acceptance checks

- Exactly one primary department/helper lane is named for delegated work.
- Files-to-read-first are 3-8 exact files for normal lanes or justified broad-audit 10-15 max.
- At most one relevant skill is required up front unless the task is explicitly multi-domain.
- Allowed write surfaces are named and do not collide with another helper lane.
- Forbidden actions include config/auth/channel/service/credential, destructive cleanup, live account/trading/money movement, ungated canon mutation, and final queue movement.
- Acceptance proof names validator/test/direct inspection, not just model confidence.
- Finance/paper/trade authority flags remain hard-false unless a separate exact approved gate is named and validated.
- Main session remains final integrator and owner-facing truth surface.
- Review-only artifacts do not create new canonical truth surfaces.

## Global stop lines

- Stop if the lane would need owner approval, external/public action, or forbidden mutation to proceed.
- Stop if no exact owner surface or files-to-read-first can be identified.
- Stop if two helpers would write the same canonical/procedure/control surface.
- Stop if generated artifacts conflict with canonical notes and no gated reconciliation path is in scope.
- Stop if a skill/department trigger is negative or ambiguous; return to main for routing.
- Stop if validation fails and the cause is not understood.

## Proposed integration path

- Reuse the existing WF71 workflow note and `Subagent Load Budget and Staff Handoff Standard`; do not create a second governance surface.
- Main session should review `tmp/wf71-load-budget-procedure-patch-proposal.md` before applying any procedure text.
- Keep department maps in WF71/IC registry as thin indexes; keep live queue state in Active Workflows.
