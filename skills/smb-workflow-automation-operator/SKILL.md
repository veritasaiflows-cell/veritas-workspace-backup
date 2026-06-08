---
name: smb-workflow-automation-operator
description: "Operate the Veritas SMB Workflow Clarity lane for fake-scenario practice, manual service packets, workflow automation blueprints, tool-fit recommendations, and customer-safety stop lines."
---

# SMB Workflow Automation Operator

## Purpose

Use this skill for Veritas SMB / Workflow Clarity / Lead Rescue work. It owns the SMB department lane so finance skills stay focused on public-market intelligence, portfolio posture, and owner-gated capital decisions.

This skill turns fake or sanitized SMB scenarios into manual review packets, automation blueprints, operator handoffs, training simulations, and readiness proof. It does not implement live customer automations by default.

## Use When

- Randall asks about SMB Workflow Clarity, Lead Rescue, missed-call recovery, lead intake, follow-up tracking, owner dashboards, or SMB automation service delivery.
- The task involves Zapier, Make, n8n, CRM/email/calendar/forms/spreadsheets, or workflow automation tool-fit selection for SMB customers.
- The work is a fake scenario, training simulation, manual service packet, operator handoff, or internal readiness drill.
- The Node cockpit, SQL service-state adapter, PM control lane, Academy training lane, or cron reminder lane needs SMB-specific interpretation.

## Source Order

Start with current workspace truth before inventing a service story:

1. `06. Playbooks/Active Workflows.md`
2. `TOOLS.md`
3. today's `memory/YYYY-MM-DD.md`
4. `tmp/generic-service-run-contract.json`
5. `tmp/wf75-smb-workflow-scenario-library.json`
6. `tmp/wf75-smb-customer-preview.json`
7. `tmp/wf75-smb-customer-preview-validation.json`
8. `tmp/wf75-smb-pilot-decision-packet.json`
9. `tmp/wf75-smb-automation-blueprints.json`
10. `tmp/wf75-smb-automation-blueprints-validation.json`
11. `tmp/wf75-smb-boundary-lint.json`
12. `tmp/generic-service-state.sqlite`
13. `tmp/wf75-service-state.sqlite`
14. PM cockpit routes: `/smb`, `/academy`, `/sql`, `/api/sql/service-state`, `/api/smb/service-runs`
15. Academy assets under `training/wf75-academy/`

SQL and cockpit routes are derived control-plane visibility, not customer canon, launch authority, customer-data import authority, or approval.

`tmp/wf75-smb-boundary-lint.json` is the independent Go validator proof for SMB authority drift. Treat `status=blocked` as a hard stop before readiness, cockpit, or PM handoff claims.

## Department Split

- Finance skills own market, portfolio, ticker, macro, technical, positioning, paper-trading, and financial-planning work.
- `smb-workflow-automation-operator` owns SMB operational workflow automation, service packets, fake scenarios, manual handoffs, and tool-fit recommendations.
- `veritas-pm-department` coordinates PM prioritization, readiness posture, queues, and launch-gate framing.
- `cron-automation-manager` owns scheduled reminders and generated review-only packets.
- `SQLite` owns local database boundaries, read/write safety, schema inspection, and SQL adapter rules.
- `workspace-qa-pass` audits output quality, stop lines, and cross-surface consistency.

## ClawHub Pattern Intake

ClawHub skills may be inspected for ideas, but do not install or activate external automation skills by default. Useful pattern classes from ClawHub include:

- automation opportunity audit
- trigger / condition / action workflow design
- Zapier / Make / n8n tool-fit comparison
- testing with edge cases
- error handling, retry, monitoring, and documentation
- sales workflow examples for CRM, email, forms, spreadsheets, and notifications

Copy only the useful pattern into Veritas-owned skills, scripts, validators, training, or packets after review. External skills do not override Veritas stop lines.

## Packet Workflow

For each SMB scenario:

1. Classify the request as fake scenario, sanitized practice case, internal service drill, or future real-client gate.
2. Map the manual workflow: trigger, intake fields, owner action, follow-up timing, current bottleneck, failure mode, and desired customer-visible result.
3. Build the service packet: problem summary, workflow map, priority, next best manual step, script/template, handoff owner, and success criteria.
4. Build the automation blueprint: trigger, input contract, dedupe key, idempotency store, ordered actions, human review checkpoint, error/fallback route, retry/backoff, audit log, and tool candidate.
5. Mark implementation posture clearly: manual-only, fake-data simulation, dry-run design, internal pilot, or blocked until explicit future gate.
6. Add QA stop lines and unresolved assumptions.

## Automation Blueprint Minimum Fields

Every automation blueprint should include:

- trigger event
- required inputs and source system
- unique ID / dedupe key
- idempotency behavior
- ordered steps
- human review checkpoint
- notification path
- retry / backoff behavior
- failure fallback
- audit log or status trail
- tool candidate: Zapier, Make, n8n, custom Node, manual-only, or undecided
- activation state: design-only, fake-data simulation, dry run, internal pilot, or blocked

## Node And SQL Cockpit Usage

Use the PM cockpit as the operating surface:

- `/smb` for current SMB scenarios and manual service posture.
- `/academy` for Randall/Randall-team training status.
- `/sql` for read-only SQL service-state visibility.
- `/api/sql/service-state` for SQL-backed service-run, queue, artifact, event, and metadata rows.
- `/api/smb/service-runs` for service-run rows with SQL-backed expansion.

Do not accept arbitrary SQL from chat, browser, or generated artifacts. Node should use allowlisted read-only queries over approved local SQLite files.

## Stop Lines

Stop and state the boundary before proceeding if the task would require:

- real customer identity, customer portfolio, suitability, risk profile, income/net-worth, tax, retirement, brokerage, account, credential, or private business data
- customer-data retention or import
- outbound calls, texts, emails, social posts, review requests, ads, or customer communications
- writing to a customer's CRM, email, calendar, forms, payment system, website, or automation account
- using live customer credentials, API keys, OAuth, or billing
- external delivery, public launch, or client-facing representation
- ROI, revenue, legal, compliance, security, or certification claims
- spending, subscriptions, tool purchases, or account changes
- treating SQL as canon, owner approval, customer source of truth, or implementation authority

## Output Format

Return:

1. conclusion
2. scenario classification
3. manual packet summary
4. automation blueprint
5. tool-fit recommendation
6. stop lines / blockers
7. next action
