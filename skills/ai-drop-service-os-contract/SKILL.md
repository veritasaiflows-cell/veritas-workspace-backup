---
name: "ai-drop-service-os-contract"
description: "Design and govern AI drop-service delivery workflows."
---

# AI Drop-Service OS Contract

## Purpose

Use this skill when Randall wants to research, design, build, package, or operate an AI-powered service monetization workflow that sells a clear business outcome while OpenClaw/Veritas coordinates research, diagnosis, delivery, proof, QA, and continuity.

This skill treats "AI drop shipping" as two possible models:

- Product dropshipping: selling physical products without holding inventory, with AI helping research, store setup, descriptions, pricing, support, and fulfillment routing.
- AI drop servicing / AI drop-service OS: selling a service outcome where AI agents, workflows, templates, and vetted human review produce the deliverable.

Default recommendation: prefer AI drop servicing / service-as-system first. OpenClaw is better suited to producing workflow audits, automation maps, lead-response systems, research packets, training desks, and proof-backed implementation artifacts than it is to operating a physical ecommerce supply chain.

## Authority

Default authority class: review-only and internal-build-safe.

Allowed without separate approval:

- market research and competitor scans
- local workflow design
- internal demo assets
- reusable templates, scripts, validators, and proof packets inside the workspace
- fictional or anonymized demos
- lead-prep research using public business information when source-labeled
- draft offer pages, sales scripts, intake forms, diagnostic checklists, and delivery SOPs
- multi-agent helper lanes that are read-only or write only to leased internal workspace paths
- exact proposed agent topology, config diff, cron design, and rollout plan

Owner-gated:

- creating persistent isolated agents with new agent directories or workspaces
- public posting, outbound messages, email, ads, cold outreach, sales calls, payment links, account creation, vendor signup, domain/publishing, customer delivery, or client system access
- individual Telegram/Discord bots, channel routing, account binding, external webhooks, or public/customer delivery
- spend, subscriptions, app installs, credentials, OAuth, runtime/channel/config/network/startup/service mutation
- use of real customer identity, private business systems, customer credentials, sensitive customer data, or regulated data
- legal, tax, compliance, guarantee, income, ROI, or performance claims

Blocked unless separately approved through exact scope:

- deceptive advertising, fake case studies, fake customer identities, fake testimonials, scraped private data, spam outreach, credential sharing, unlicensed resale, counterfeit/infringing products, or claims that cannot be evidenced
- finance/account/trade/brokerage/capital actions outside existing finance guardrails

## Outreach Email Channel Readiness

When Randall creates or names an outreach email identity for Veritas AI Flows or another AI Drop-Service OS offer, treat the account as an owner-gated channel asset, not as access authority.

Default workflow fit:

- Primary monetization/outreach workflow: WF79-SMB when the offer is SMB Workflow Clarity, Lead Rescue, Marketing Ops, Website-To-Lead Audit, or similar small-business service work.
- Parent service-system workflow: WF75 when the work concerns AI Drop-Service OS packaging, training, delivery templates, QA cadence, private-pilot proof, or service model design.
- WF74/WF88 may support internal proof, routing, self-review, memory, and checkpointing, but they do not grant external action authority.

Allowed without separate approval:

- draft sender profile guidance, signature text, labels, manual-send SOPs, outreach copy, contact-form copy, reply scripts, status trackers, and owner approval cards
- prepare microbatch send packets using public business information that is source-labeled and not enriched with private/personal data
- prepare response triage and follow-up recommendations for Randall review
- record the channel identity as future owner-gated readiness in workflow continuity notes

Owner-gated before any action:

- signing in, connecting, configuring, or delegating the email account
- OAuth setup, connector installation, app-password creation, API access, forwarding, filters, aliases, domain setup, DNS, payment links, CRM sync, campaign tools, or account/security settings changes
- sending emails, submitting contact forms, replying to prospects, follow-ups, bulk sending, warmup, ads, public posting, or any customer/prospect contact
- receiving, storing, importing, or processing real customer/prospect private data beyond explicitly approved minimal public business contact metadata

Blocked handling:

- Do not ask Randall to paste or share an email password, recovery code, OAuth token, app password, session cookie, 2FA code, or secret screenshot.
- Do not store credentials or tokens in workspace files, memory, chat, notes, artifacts, screenshots, or generated packets.
- Do not infer send authority from the existence of an email account, draft copy, QA-clean packet, prospect list, pilot-readiness status, or owner excitement.

Recommended first operating mode:

1. Veritas drafts outreach copy, follow-up copy, approval cards, and tracker rows.
2. Randall signs in to the account and sends manually after approving exact first batch, channel, copy, follow-up rule, and data rule.
3. Veritas helps classify replies and prepare next-step recommendations from owner-provided, non-sensitive snippets.
4. After manual proof, Randall may approve an official OAuth/delegated connector with least-privilege scopes, audit logging, and draft/review-first posture.
5. Send-capable automation remains blocked until repeated manual proof, QA review, explicit owner approval, and a narrow audit trail exist.

Safe first approval-card language:

`Approve manual outreach prep for [offer] using [email identity] for [exact first batch] with [exact copy], [exact channel], one follow-up after [3-5 business days], no automation, no personal-email harvesting, no customer data, no payment links, and manual owner send only.`

Closeout requirement:

Any outreach-channel readiness update must report whether credentials were untouched, no external messages were sent, no connector/runtime/account mutation occurred, and whether the next action is internal-safe, owner-gated, or blocked.

## Recommended First Offer

Default first monetization target: AI Workflow Clarity Sprint.

Positioning:

- fixed-scope diagnostic and implementation-readiness service for a small business workflow
- OpenClaw/Veritas produces a workflow map, automation opportunities, tool stack recommendation, risk list, implementation plan, and proof-backed before/after demo
- optionally adds a small prototype automation after the diagnostic is validated

Avoid starting with:

- generic "AI agency" services
- AI product dropshipping stores
- broad "we automate anything" positioning
- guaranteed revenue claims
- customer-facing finance intelligence products before separate gates clear

## Logical Multi-Agent Department Model

These are task roles, not instructions to create additional persistent agents. Map them onto the current roster: Main owns architecture and acceptance; Research Scout handles public research and bounded offer drafting; Implementation Builder handles delivery-system code and templates; QA Red-Team challenges claims and implementations; Docs Continuity Editor handles accepted continuity updates.

Main Veritas session:

- owns strategy, truth integration, authority boundaries, final recommendation, and user-facing closeout
- verifies every helper output against live sources, files, artifacts, or validators before using it

Research Scout helper:

- gathers market/competitor/service evidence from public sources
- labels source freshness and uncertainty
- writes only to a leased research packet or returns a draft
- stop line: no final recommendation, no outreach, no claims without sources

Offer Architect task on Research Scout:

- drafts offer, niche hypothesis, deliverables, pricing logic, guarantee-safe language, and intake questions
- stop line: no legal/tax/compliance claim and no public-facing launch without main review

Workflow Engineer task on Implementation Builder:

- designs the actual delivery system: intake, diagnosis, automation map, artifact templates, acceptance checklist, and implementation proof
- may draft scripts/templates only to leased paths
- stop line: no credential, vendor, customer, or runtime mutation

QA / Red-Team task on QA Red-Team:

- challenges the offer for hype, weak evidence, operational risk, privacy risk, delivery gaps, and over-promising
- verifies that claims are evidence-backed and that the delivery contract can be fulfilled

Continuity / Recovery task on Docs Continuity Editor:

- builds or checks the long-work packet, compaction recovery notes, lane status, proof artifacts, and next-pickup instructions
- ensures a future session can resume without relying on chat memory

## Physical Isolated-Agent Topology

Use the existing persistent roster before considering another agent. OpenClaw does not auto-discover agents from a workspace folder; live `agents.list[]` configuration is the authority. Verify it with `openclaw agents list --json` before dispatch.

Current approved roster:

| Agent | Purpose | Exact model |
|---|---|---|
| `main` | architect, queue owner, final integrator, and acceptance owner | `openai/gpt-5.6-sol` |
| `research-scout` | public market, competitor, niche, and offer research | `openai/gpt-5.6-terra` |
| `implementation-builder` | scoped implementation and proof | `meta/muse-spark-1.3-contributor` |
| `qa-redteam` | independent implementation and claim review | `ollama-cloud/glm-5.3:cloud` |
| `docs-continuity-editor` | accepted documentation and continuity updates | `ollama-cloud/glm-5.3-flash:cloud` |
| `finance-source-scout` | finance evidence gathering | `openai/gpt-5.6-terra` |
| `finance-redteam` | independent finance challenge | `openai/gpt-5.6-terra` |

Treat logical offer architecture, workflow engineering, and recovery roles as bounded assignments to this roster, not reasons to create duplicate persistent agents. Add a new agent only after repeated work proves an unmet capability, isolation, memory, tool-policy, or standing-routing need and Randall explicitly approves the config mutation.

Each persistent agent should have:

- its own workspace directory
- its own agent state directory
- its own `IDENTITY.md` / `SOUL.md` or equivalent identity surfaces scoped to its role
- its own memory file or memory directory for role-specific continuity
- a shared read-only route to approved team memory/project board artifacts
- no default access to credentials, customer systems, finance execution, external sending, or config/runtime mutation

## Shared Team Memory And Project Board

Use a hub-and-spoke memory design:

- Team board: one shared project-state artifact controlled by Veritas main, such as `state/ai-drop-service-os/team-board.json` plus optional human-readable Markdown.
- Agent local memory: each persistent agent records role-specific discoveries and open tasks in its own workspace.
- Main integration memory: Veritas records accepted facts and decisions into daily memory and the canonical project continuity surface.

Rules:

- helper memory is not canon
- team board is routing state, not final truth
- Veritas main decides what gets promoted into durable accepted memory
- every material agent output must include source/proof, timestamp, and confidence

## Orchestrator And Inter-Agent Communication

Default orchestrator: Veritas main.

Communication options:

1. Main-mediated tasks: Randall talks to Veritas; Veritas spawns or messages agents and returns integrated results. This is the safest default.
2. Direct session messaging: Veritas can use visible session keys/labels/agent IDs to send a task to another agent.
3. Persistent named agents: configured agents can receive work through `sessions_send` by `agentId` or through their routed channel bindings.
4. Scheduled isolated work: cron can run an `agentTurn` in isolated/current/session mode for proof, digests, reminders, or watchdogs.
5. External bots/channels: only after exact approval; use for owner-only review notifications first, not customer/public delivery.

Inter-agent messages should be task packets, not vague chat:

```text
Role: Research Scout
Objective: Find 10 public examples of AI workflow audit offers for local service businesses.
Allowed sources: public web only.
Deliverable: source-labeled comparison table with URL, offer, price if public, buyer, claim, risk.
Write target: state/ai-drop-service-os/research/offer-scan-YYYYMMDD.json
Stop lines: no outreach, no signup, no scraping private data, no customer contact, no claims without sources.
```

## Heartbeats, Watchdogs, And Cron

Use automation levels:

- Level 0: observe only
- Level 1: route only
- Level 2: review-only proof refresh
- Level 3: helper-lane contract preparation
- Level 4: guarded proof execution and front-door refresh
- Level 5: owner-gated action only after exact approval

Recommended first schedules after approval:

- Daily team-board freshness check: ensure open lanes have owner, next action, and stale markers.
- Daily continuity packet: summarize accepted outputs, rejected/unverified outputs, blockers, and next safe step.
- Weekly offer/research refresh: update competitor examples and niche evidence.
- Watchdog heartbeat: detect overdue agent tasks and report to main; do not spawn new helpers or patch state silently at first.

Cron must not:

- create or delete agents without exact approval
- mutate schedules/config/runtime from inside the job
- send customer/public messages
- infer approval
- act on credentials, customer systems, finance/capital/account surfaces, or paper/live execution

## Long-Work Packet Requirements

For any serious AI Drop-Service OS build lane, create or maintain a packet with these fields before helper spawning or multi-hour work:

- `workflow_id`
- `workstream_id`
- `objective`
- `original_request`
- `latest_user_intent`
- `authority_class`
- `non_goals`
- `stop_lines`
- `frontdoor_proof`
- `source_surfaces`
- `write_mode`
- `leased_paths`
- `helper_lanes`
- `model_route`
- `acceptance_proof`
- `recovery_state`
- `last_completed_step`
- `next_safe_step`
- `open_questions`
- `proof_artifacts`
- `closeout_required`

When the existing workspace long-work packet linter applies, run it at preflight, spawn, and closeout stages.

## Recovery Rules

A long AI Drop-Service OS lane must survive compaction, tool aborts, helper failures, and session restarts.

Minimum recovery surfaces:

- durable packet under `tmp/` or the workflow's approved continuity path
- daily memory note after material progress
- exact list of active/closed helper lanes and what output was accepted, rejected, or unverified
- original request and current interpretation copied into the packet
- latest source list and freshness notes
- exact next command or next decision needed
- proof status: passed, warning-grade, blocked, or not yet run

After compaction or recovery:

1. Read `SOUL.md`, `USER.md`, `AGENTS.md` and its local route map, Startup Truth Index, today/yesterday memory, and the work packet.
2. Reconstruct the objective, stop lines, source surfaces, and latest accepted state.
3. Check lane register before writing.
4. Resume from `next_safe_step`, not from scratch.
5. Do not trust helper summaries without verifying live files or artifacts.
6. If original user intent and packet disagree, stop and ask Randall.

## Delivery Phases

Phase 0: Research and fit check

- define whether the opportunity is product dropshipping, AI drop servicing, automation agency, or workflow productization
- identify top 3 niches and disqualifiers
- produce a blunt recommendation: pursue, defer, or reject

Phase 1: Internal offer design

- one offer, one buyer, one problem, one measurable deliverable
- draft scope, price test, timeline, intake form, proof checklist, and no-guarantee claims language
- produce a fictional/anonymized demo

Phase 2: Delivery OS v0

- build templates for intake, workflow audit, automation map, ROI estimate caveats, implementation backlog, QA checklist, and closeout proof
- define helper-lane prompts and acceptance checks
- run a dry internal test from fake client brief to final packet

Phase 3: Existing persistent-agent pilot

- use the current configured specialist roster before proposing another agent
- keep research and QA read-only or distinct-output; use Builder write access only through the scoped sandbox/writeback contract
- verify agent-specific bootstraps, transport, model parity, memory boundaries, and message routing
- no external channel bindings unless exact approval exists

Phase 4: Private pilot readiness

- prepare pilot criteria, risk boundaries, customer-data rules, onboarding checklist, deliverables, revision policy, and support limits
- no outreach or payment collection until Randall approves exact channel/action

Phase 5: Pilot execution, owner-gated

- only after explicit approval for outreach/customer interaction/payment/vendor setup
- log every customer-facing action and keep data minimal
- after each pilot, produce case-study-safe internal proof without fake claims

Phase 6: Productization

- convert repeated delivery patterns into reusable templates, validators, optional scripts, and packaged workflow modules
- consider external packaging only after evidence of repeat demand and delivery reliability

## Default Timeline

Fast internal feasibility: 2-3 days.

Offer and demo v0: 5-7 focused days.

Delivery OS v0 with templates, helper lanes, and recovery packet: 2-3 weeks.

Persistent agent pilot: 1-2 additional days for exact roster, creation, identity/memory scaffolding, routing smoke test, and rollback proof after approval.

Private pilot readiness: 3-4 weeks if scope stays narrow.

First paid pilot: 4-8 weeks, mainly limited by outreach approval, offer clarity, buyer access, and Randall's available sales/training time.

Repeatable monetization system: 8-12 weeks if a narrow niche works; longer if the first niche or offer fails.

## Acceptance Proof

A lane is not complete until it has:

- clear chosen business model and rejected alternatives
- one-sentence offer and target buyer
- delivery workflow map
- artifacts/templates for each delivery step
- helper-lane contracts and stop lines
- evidence-backed claims register
- privacy/customer-data boundary
- recovery packet with original request/current state/next action
- dry-run proof from sample brief to final deliverable
- QA/red-team findings resolved or explicitly accepted
- persistent agent roster and exact command packet when physical agents are in scope
- routing smoke test for any created persistent agent
- rollback/delete plan for any created persistent agent
- closeout summary with remaining owner-gated actions

## Closeout Shape

Every closeout should report:

- bottom-line recommendation or build status
- what changed or was produced
- evidence and proof status
- monetization risk and operational risk
- authority boundaries preserved
- exact next action: internal-safe, owner-gated, or blocked

Never imply that a clean workflow, demo, agent roster, cron heartbeat, or packet means public launch, customer contact, payment collection, revenue certainty, legal/compliance readiness, or external delivery approval.

