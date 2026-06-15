---
name: "veritas-intelligence-effort-router"
description: "Route Veritas intelligence effort by risk, scope, freshness, and authority."
---

# Veritas Intelligence Effort Router

Use this skill before substantial Veritas intelligence work when the prompt could touch markets, portfolio posture, ticker routing, macro/geopolitical context, product/workflow strategy, PM queue movement, or durable automation design.

The goal is not to do less work. The goal is to spend the right amount of work in the right place, avoid broad scans by default, and preserve decision quality where money, workflow authority, or durable state is involved.

This skill is a dispatcher. It does not replace `veritas-response-contract`, `veritas-macro-pass`, `veritas-positioning-pass`, `veritas-fundamental-pass`, `veritas-technical-pass`, `veritas-pm-department`, `cron-automation-manager`, or implementation/QA skills. It decides which of them is actually needed.

## Core Principle

Route by consequence and uncertainty:

- Low consequence + fresh exact artifact = answer from the artifact.
- Medium consequence + mixed/stale evidence = refresh or inspect the narrow producer/consumer chain.
- High consequence + capital/execution/canon/customer/runtime implications = run full gated proof, state boundaries, and ask for owner decision where required.

Do not run the full finance stack just because the topic is financial. Do not answer from memory when exact current artifacts exist.

## Effort Bands

### Band 0 - Direct Answer

Use when:
- The user asks a conceptual, explanatory, or yes/no question.
- No current market/portfolio/state claim is needed.
- No durable artifact, code change, or operational decision is implied.

Do:
- Answer directly.
- Mention uncertainty if relevant.
- Do not run tools unless freshness materially matters.

Examples:
- "What does Sahm Rule mean?"
- "Is CAPE a timing signal?"
- "Can we make skill routing more efficient?" before implementation is requested.

### Band 1 - Thin Artifact Read

Use when:
- The answer depends on current workspace truth, but a front-door artifact exists.
- The decision is review-only or status-level.
- The evidence stack was recently refreshed.

Read only the thinnest truth surface first:
- `tmp/cron-control-packet.json` for cron state.
- `tmp/pm-control-packet.json` for PM state.
- `tmp/macro-signal-spine.json` and `tmp/macro-judgment-draft.json` for broad macro state.
- `tmp/deployment-readiness-surface.json` for deployment posture.
- `tmp/wf78-capital-review-queue.json`, WF78 route packet, or ticker card/answer packet for ticker routing.
- `workflow_router.py WF## --answer summary|all` for named workflow state.

Do:
- Answer from the current artifact.
- State `ok`, `warning`, `stale`, `blocked`, or `partial` status.
- Avoid opening broad notes unless the artifact says source detail is needed.

### Band 2 - Narrow Refresh

Use when:
- The artifact is warning/stale/partial but repairable through one narrow chain.
- The user asks for current intelligence and the producer is cheap and bounded.
- The answer could affect prioritization but not capital/execution approval by itself.

Run the smallest relevant producer/consumer chain:
- Macro: `macro_metrics_ingest.py`, `macro_signal_spine.py`, then `macro_judgment_draft.py` when broad macro claims matter.
- Cron: `cron_control_packet.py`; drill into `cron_freshness_spine.py` only when attention/stale/blocker counts matter.
- PM: `pm_control_packet.py --write --write-db --validate` for PM queue truth.
- Ticker/card: use existing ticker front door or answer packet before broad source reads.
- WF78: use the specific WF78 gate or route packet named by the question.

Do:
- Refresh, validate, then answer.
- Say which warnings remain.
- Do not escalate into full audit unless the narrow refresh fails or exposes a high-consequence conflict.

### Band 3 - Integrated Decision Pass

Use when:
- The user asks what to do next, what to prioritize, what to buy/add/trim/hold/bench, or how current macro/portfolio/ticker evidence changes action.
- Multiple evidence layers are needed: macro, fundamental, technical, positioning, risk, and source freshness.
- The output could influence capital, portfolio posture, or workflow priority.

Route to the relevant domain skills:
- `veritas-macro-pass` for macro/regime/rates/inflation/geopolitical backdrop.
- `veritas-fundamental-pass` for business quality and financial evidence.
- `veritas-technical-pass` / `technical-chart-pass` for entry/timing/invalidation.
- `veritas-positioning-pass` for portfolio implications, priority order, and owner-gated action states.
- `veritas-response-contract` for final answer shape.

Do:
- Include thesis, risk, entry/invalidation, evidence freshness, and owner action required where capital may be influenced.
- Separate review-ready, deployable, paper-ready, and approved.
- Preserve no-trade/no-account/no-owner-approval-inference boundary.

### Band 4 - Proof-Heavy Implementation / Audit

Use when:
- The user asks to implement, harden, audit, repair, or automate a durable workflow.
- Multiple files/artifacts/cron jobs/skills are touched.
- A wrong change could create runtime, canon, portfolio, customer, or execution authority drift.

Use implementation and QA skills:
- `disciplined-implementation` for scripts, validators, manifests, workflow code, boot/control surfaces.
- `cron-automation-manager` for scheduled workflow design or cron payload changes.
- `workspace-qa-pass` and `code-review-auditor` for proof-heavy validation.
- `skill_workshop` for durable skill/procedure changes.

Do:
- Inspect existing pattern first.
- Make scoped edits.
- Run focused tests plus relevant integration validators.
- Update memory/continuity when meaningful.
- Preserve owner gates and report exact proof.

## Routing Matrix

Use this quick matrix before starting work.

| User intent | Default band | Primary evidence | Skills/tools |
|---|---:|---|---|
| Concept/explanation | 0 | none or one source | response contract if substantial |
| Current status | 1 | front-door artifact | response contract |
| Cron/PM/workflow status | 1-2 | cron/PM/router packets | PM/cron skills if changing schedules |
| Macro state | 1-2 | macro signal spine + judgment | macro pass if interpreting consequences |
| Ticker Q&A | 1-3 | ticker card/answer packet | fundamental/technical/positioning as needed |
| Portfolio action | 3 | portfolio snapshot, execution board, macro, readiness | positioning pass + response contract |
| Capital/paper order prep | 3-4 | WF67/WF78/WF85 proof | wf67-paper-trading-operator; owner approval required |
| Automation/cron design | 4 | existing scripts/cron state | disciplined implementation + cron automation manager |
| Skill/procedure change | 4 | skill files + workshop | skill_workshop only for proposal/apply lifecycle |
| Full audit | 4 | WF73/control packets/artifact index | disciplined implementation + QA skills |

## Source Order

Use front doors before broad scans:

1. Exact route or packet named by the user.
2. `TOOLS.md` first-hop route if unsure.
3. Workflow router/capsule for named workflow.
4. Current JSON proof artifact under `tmp/`.
5. Exact owner note or continuity file.
6. Broad `rg` search only when the route is unknown or artifacts conflict.
7. Web/current external lookup only when source freshness, market data, laws, product data, or external facts matter.

Do not let generated SQL/JSON/capsules become canon, approval, trade/account authority, or portfolio truth. They are routing/proof surfaces unless explicitly promoted through a gated path.

## Freshness Rules

If the answer depends on current markets or macro:
- Prefer latest generated artifacts if they are fresh enough and validated.
- If the artifact is warning-classed, name the warning and downgrade confidence.
- If a source is stale but slow-moving, say stale but useful for long-horizon context only.
- If a current-price, band, stop, or readiness claim matters and the artifact is stale/missing, refresh narrowly before answering or state the gap plainly.

Never convert stale data into clean posture language.

## Authority Rules

Always classify authority before effort:

- Review-only routing: may automate within validated derived artifacts.
- Workspace maintenance: only inside approved bounded gates and validators.
- Capital recommendation: may recommend or prepare owner approval card, but no approval is inferred.
- Paper execution: requires WF63/WF67 guardrails, fresh kill switch, exact scoped artifact, and Randall exact approval.
- Live execution/account/money movement: blocked unless Randall gives a separate explicit live-action instruction with full scope and risk acceptance.
- Config/auth/channel/runtime/network mutation: ask first unless already explicitly approved for the current task.

If authority is unclear, stop and state the decision needed.

## Stop Lines

Stop or escalate when:
- Evidence is stale or partial and the answer would influence capital or execution.
- Generated artifacts conflict with canonical notes.
- A result would imply owner approval, portfolio mutation, or trade/account authority.
- The task requires credentials, account mutation, external delivery, public/customer action, or destructive cleanup.
- A skill/procedure change is needed but has not gone through Skill Workshop.
- A broad audit finds a blocker outside the current scope.

## Final Answer Shape

After routing and work, use `veritas-response-contract`:

1. Conclusion.
2. Evidence/proof or files changed.
3. Trust limits and remaining warnings.
4. Next concrete action.

For finance answers, include owner-gated boundary when capital, paper/live execution, portfolio mutation, or approval could be inferred.
