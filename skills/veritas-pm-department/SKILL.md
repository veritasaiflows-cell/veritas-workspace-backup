---
name: "veritas-pm-department"
description: "Operate PM status, roadmap, queue, readiness, and cross-workflow coordination."
---

# Veritas PM Department

This skill owns the **project-management layer** for active Veritas product and workflow delivery.

Its job is to turn live workflow truth into weekly project updates, upcoming enhancement roadmaps, WF75 readiness timelines, and presentation/PDF handoff briefs.
It does not create launch authority, customer authority, legal authority, source-licensing authority, portfolio authority, or execution authority.

## When to use this skill

Use when Randall asks for:
- PM department updates
- weekly project status
- upcoming enhancements
- WF75 readiness timelines
- 55-65% internal/service-led SaaS readiness tracking
- infrastructure-first WF75 sprint tracking
- WF75 generic service-run / SMB Workflow Clarity / Lead Rescue queue advancement
- product-management triage, product roadmap, pilot-readiness, customer-onboarding, or SaaS delivery planning
- roadmap or milestone planning
- presentation or PDF planning for project readiness
- cross-workflow delivery coordination

Do not use this skill to run broad workflow phases by itself.
It packages and coordinates live truth; it does not infer approval.

## Source order

## Effort routing

Before PM work, classify the request with `veritas-intelligence-effort-router`.

Default route:

- **Band 0:** answer conceptual PM/process questions directly.
- **Band 1:** read `tmp/pm-control-packet.json`, workflow router output, or the exact PM packet named by the user.
- **Band 2:** refresh `pm_control_packet.py --write --write-db --validate` when PM state is stale, warning-classed, or needed for current queue truth.
- **Band 3:** integrate PM, cron, workflow router, and artifact proof when selecting next work or changing priority.
- **Band 4:** use disciplined implementation, cron automation, QA, and Skill Workshop when PM rules, recurring jobs, skills, workflow state, or control-plane contracts change.

PM should reduce ambiguity. Do not broad-scan Active Workflows, project notes, and memory before checking the current PM/control front doors unless the front door is missing, contradictory, or says source detail is required.

Read the thinnest live truth surfaces first:
- `06. Playbooks/Active Workflows.md`
- `tmp/wf75-service-led-saas-readiness-plan.json`
- `tmp/operator-packets/retail-saas-wf75.json`
- `tmp/workflow-automation-autonomy-review.json`
- `tmp/heartbeat-continuation-candidates.json`
- `06. Playbooks/Project Continuity/Workflow 75 - AI Productivity and Business Opportunity Intelligence Expansion.md`
- relevant WF72/WF78 continuity notes when SQL or ticker expansion affects WF75
- today's `memory/YYYY-MM-DD.md`
- exact proof artifacts named by the workflow surfaces

If a source is stale, missing, or contradictory, say that directly and downgrade confidence.

## ClawHub Pattern Intake

Do not install generic ClawHub skills by default. Use their search results as pattern libraries, then fold only the useful operating pattern into Veritas-owned skills, scripts, validators, and PM packets.

Current WF75 pattern intake:
- `queue` / `agent-task-queue` pattern: durable queue rows, priority, retry/dead-letter review, blocker reason, owner, next action, and lifecycle state. In Veritas, this belongs in `tmp/pm-next-actions.json`, `tmp/pm-blocker-register.json`, `tmp/pm-main-session-handoff.json`, and the local SQLite control-plane surfaces. It must not create autonomous execution authority.
- `afrexai-product-manager` / `pm-copilot` pattern: product discovery, roadmap, prioritization, activation metrics, pilot-readiness, customer value, and delivery risk. In Veritas, use this for WF75 PM packets and the Lead Rescue roadmap, while keeping launch/customer/external-delivery gates closed.
- `agent-evaluation` / `skill-evaluation` pattern: scenario quality, output consistency, safety/regression checks, trigger fit, and claim-boundary validation. In Veritas, this belongs in `veritas_harness_scorecard.py`, renderer/export regression, SMB preview validation, and skill QA.
- workflow automation pattern: n8n/Zapier/Make-style trigger design, dedup keys, idempotent reruns, retry/backoff, audit logs, failure queues, tool-selection, automation ROI, and maintenance reviews. In Veritas, this belongs in `tmp/wf75-smb-automation-blueprints.json` and its validation artifact. It is design-only until a future customer/intake/implementation gate opens.

Current WF78 pattern intake:
- ClawHub routing/monitoring/finance-promotion searches are pattern intake only unless Randall explicitly approves installation. Generic hits such as workflow templates, monitoring dashboards, infra/API monitoring, ledger/PE monitoring, or portfolio-risk analyzers do not outrank the local WF78 gate stack.
- Web pattern carry-forward: use human review, explicit approvals, monitoring/evaluation proof, source freshness, concentration-risk controls, and audit trails as design inputs. Fold these into Veritas-owned scripts/skills instead of giving external skills finance authority.
- PM should track WF78 by phase and live proof artifact: capacity policy, funnel contract, lower-tier promotion gate, Tier A competitive gate, owner-decision packet layer, evidence/research packet depth, and baseline/batch reruns.
- PM status must separate machinery built from ticker readiness. A green gate stack means the evaluator works; it does not mean any D/C/B/A promotion is approved.

When reviewing an external skill candidate, score it against:
- WF75 fit
- overlap with existing Veritas skills
- install/runtime risk
- customer-data or credential risk
- external-delivery or autonomous-action risk
- whether the pattern should be copied into existing Veritas surfaces instead of installed
- acceptance proof needed after adoption

For finance-promotion skill candidates, add these checks:
- whether the skill needs market/account credentials
- whether it could imply recommendation, allocation, or execution authority
- whether it preserves owner approval and concentration-risk review
- whether its useful pattern can be copied locally without installing it
- whether the candidate has enough provenance to justify a future security review

## Core outputs

### Weekly PM Update

Include:
- headline status
- current readiness band or phase
- completed this week
- planned next week
- upcoming enhancements
- blockers, dependencies, and owner decisions needed
- proof artifacts and validation status
- next safe action

### WF75 Readiness Timeline

Include:
- target readiness band, usually 55-65% internal/service-led readiness
- week-by-week milestone path
- acceptance criteria by phase
- infrastructure gaps and proof gates
- what does and does not count as SaaS readiness

### Enhancement Roadmap

Include:
- enhancement name
- user or operator value
- dependency
- expected timing band
- required proof or validator
- launch/customer/legal/source boundary

### WF75 Queue Advancement Review

Use this when PM needs to move the work forward without crossing authority gates.

Include:
- selected lane and source packet
- queue status: ready, stale, blocked, or needs validation
- retry/dead-letter condition if a prior action failed
- next safe action
- owner layer: main session, helper lane, cron proof, or manual Randall decision
- acceptance proof
- stop lines

PM may queue bounded review-only work for main-session continuation. PM may not execute customer outreach, external delivery, credential access, customer-data ingestion, system implementation, canon/portfolio mutation, paper/live/account action, config/auth/runtime mutation, or infer owner approval.

### Product / Pilot Readiness Review

Use the product-manager pattern for WF75 and Lead Rescue.

Include:
- target user and painful job
- offer shape
- activation / time-to-value hypothesis
- pilot deliverables
- exclusions
- pricing or package hypothesis if requested
- risk and trust gates
- next validation artifact

Do not turn a PM-ready packet into public launch readiness. Product readiness is internal proof until explicit owner approval opens a customer/pilot gate.

### Workflow Automation Blueprint Review

Use the workflow-automation pattern when WF75 turns an SMB scenario into a proposed automation.

Include:
- trigger and schedule/event source
- input contract and required fields
- dedup key and idempotency store
- ordered steps and fallback path
- retry/backoff behavior
- audit log and status fields
- human review queue
- tool candidate: existing tools, Zapier, Make, n8n, local script, or manual process
- dry-run status and activation gate
- stop lines

PM may recommend a blueprint as a service-design artifact. PM may not activate Zaps, n8n workflows, Make scenarios, CRM workflows, phone/SMS/email automation, ad-platform automation, payment/POS/payroll automation, or customer-system writeback without a separate explicit gate.

### Evaluation / Skill QA Review

Use the evaluation pattern when a skill, renderer, scenario, or PM queue rule changes.

Include:
- scenarios tested
- expected good outputs
- seeded-bad or blocked claims
- safety checks
- regression result
- remaining warning-only debt

Clean evaluation means the artifact is safer to review. It does not imply launch, customer, delivery, approval, or execution authority.

### Presentation/PDF Handoff Brief

Use this when the output should become a deck or fixed-layout document.
Provide:
- audience
- purpose
- slide/page outline
- required charts or tables
- source stack
- trust disclosures
- open decisions

Then hand the rendering posture to `veritas-pdf-brief` for PDFs or the relevant presentation tool when Randall explicitly wants a generated deck.

## Weekly reporting format

Use this default shape:

1. Conclusion
2. Readiness status
3. Timeline
4. Completed work
5. Upcoming enhancements
6. Blockers and decisions
7. Proof
8. Next action

Keep it concise. PM work should reduce ambiguity, not create bureaucracy.

## Stop lines

Never let PM packaging imply:
- public launch readiness
- real customer-data readiness
- external delivery approval
- legal, compliance, or source-licensing clearance
- SQL import or ticker expansion approval
- portfolio/canon mutation approval
- paper/live/account/trading authority
- owner approval inferred from clean validation

Current WF75 posture:
- the active 6-10 week route is infrastructure-first: anonymous-scenario service-state storage, operator queue/status, renderer/export pipeline, QA regression harness, scenario-template library, and artifact-only PM handoffs
- use anonymous service request scenarios, not fake-person customer personas; real public ticker/company/market evidence may be used when source-labeled and validator-gated
- privacy/licensing/counsel decision-packet work is not the active sprint route
- public launch, real customer data, customer identity, customer portfolio data, suitability/risk-profile intake, external delivery, legal/compliance claims, source-licensing claims, brokerage/account connection, personalized regulated advice, and paper/live execution remain blocked

WF75 PM updates are internal and review-only unless a separate exact approval artifact says otherwise.
