# Workflow 79-SMB - SMB Workflow Clarity and Marketing Ops Automation

Owner: Veritas main session  
Status: active P1 monetization implementation lane, review-only  
Primary plan: `09. Archive/Legacy Audit Roots - Archived/Audit/SMB-SaaS-Parallel-Implementation-Plan-2026-06-18.md`

## Purpose

Build a service-first SMB workflow automation offer that starts with Lead Rescue and expands into Marketing Ops only where the workflow proof supports it.

This is not a public launch, marketing agency pivot, customer portal, credentialed implementation, or SaaS product claim yet. It is an internal implementation and proof lane using sanitized scenarios and generated packets.

## Current State - 2026-06-17 23:25 MST / 2026-06-18 UTC

- Randall resumed SMB Workflow Clarity on 2026-06-13 as the priority monetization side-lane.
- The route artifact is `scripts/generic_intelligence_saas_pivot.py`.
- Current proof family includes generic service-run contract, SMB scenario library, customer preview, pilot packet, automation blueprints, offer/ICP packet, demo packets, Marketing Ops blueprints, cockpit panel, sales-practice packet, phase closeout, and boundary lint artifacts.
- The next real gate is Randall exact approval before any real outreach, pilot use, prospect contact, customer data, external delivery, credential use, or implementation access.

## Morning Pickup

Use `09. Archive/Legacy Audit Roots - Archived/Audit/SMB-SaaS-Parallel-Implementation-Plan-2026-06-18.md` as the first-read contract.

Execution order:

1. Refresh PM: `python scripts\pm_control_packet.py --write --write-db --validate`.
2. If a helper is used, lease a WF79-SMB write surface before changing packet or blueprint artifacts.
3. Run the SMB implementation validator: `python scripts\generic_intelligence_saas_pivot.py --write --write-db --validate`.
4. Inspect the output packet family and choose one next implementation slice: missed-call rescue, website-form follow-up, stale-lead reactivation, owner attention dashboard, or monthly lead/marketing ops packet.
5. Strengthen the chosen slice with a before/after workflow map, automation blueprint, manual packet, sales-practice language, and QA stop-line pass.
6. Refresh PM again after proof.

## Parallel Contract With WF75

WF79-SMB owns the customer-problem and workflow-automation packet path.

WF75 owns the internal SaaS deliverable gate: service-state, deliverable packaging, training assets, and PDF/Excel QA. The finance-delivery daily/weekly/monthly series remains paused as cron but is retained as the manual deliverable-gate test surface.

These lanes may run in parallel only when write leases are clean and outputs are disjoint.

## Refresh and review-ready offer — 2026-09-18 11:40 MST

- Randall reactivated the monetization lane (2026-09-18, "What do we currently have for SMB?" → "Yes proceed").
- Pickup sequence executed and green: `pm_control_packet.py --write --write-db --validate` ok; `generic_intelligence_saas_pivot.py --write --write-db --validate` ok (errors [], warnings []). Packet family current.
- **Review-ready offer drafted:** `10. Deliverables/WF79-SMB/Lead Rescue Offer and Prospect Profile - 2026-09-18.md` — one-page Lead Rescue Sprint service description, offer ladder carrying the June pricing hypotheses unchanged, honest $10k/mo math (clearing $10k/mo within 4–6 clients requires the retainer to validate at $1,500–$2,500/mo; recommended pilot: $1,500 sprint + $1,000/mo), and a 10-name Mesa prospect profile built from public web evidence only (5 plumbing, 4 HVAC wave 1; 1 dental wave 2).
- Public-evidence boundary honored: names/domains from each business's own public site, zero contact made, all claims flagged self-reported and unverified, verification pass required before any use.
- Pending owner decisions (recorded in the offer doc, none approved): pilot pricing shape; outreach method; first-contact count (recommended 3 of 9 wave-1 names). Outreach remains stop-lined until exact approval.

## Outreach approved — email, 3 wave-1 names (2026-09-18 11:56 MST)

- Randall approved outreach method and count: "Continue with email and the 3 suggested." Pricing decision remains open — no scope approved, so no numbers quoted anywhere.
- Selected 3: **JLM Air Conditioning & Heating** (info@jlmazac.com — only prospect with a public email), **Phend Plumbing** (web form, no public email), **OX Plumbing** (web form, no public email). Rationale: each publishes a specific promise that missed calls directly break — same-day emergency AC in 115° weather; 24-hour emergency service against 7–5 office hours; 60-minute emergency response with 300+ reviews.
- Emails staged: `10. Deliverables/WF79-SMB/Outreach Emails Wave 1 - 2026-09-18.md` — plain-text, personalized to each business's own public copy, no pricing, no ROI claims, 15-minute CTA, opt-out line, one-per-day cadence, day-4 follow-up template.
- Delivery path: the OS has no email channel (Telegram only, verified 2026-09-18 via conversations list); nothing sends automatically. Randall sends personally from his inbox; Phend/OX via their contact forms (equivalent channel for trades).
- Send/reply tracking logs to this note once sending begins.

## Marketing/outreach owned by persistent agent `marketing-outreach` (2026-09-18 ~12:50 Phoenix)

- Randall rejected the v2 drafts as "too commercial" and directed the structural fix: a dedicated isolated agent that owns marketing and outreach copy, armed with a ClawHub skill.
- **Skill:** searched ClawHub (cold email / email marketing / copywriting), verified, and installed `@huajianjiu000/cold-outreach-email-writer@1.0.0` globally (`~/.openclaw/skills/`). Bulk-send/scraping infrastructure skills (Resend/Apollo/Instantly/SMS/Maps-harvest) deliberately rejected — wrong fit; the need is writing quality, not mass outreach.
- **Agent registered:** `marketing-outreach` ("Marketing and Outreach") in gateway `agents.entries`: model `openai/gpt-5.6-luna` (fallback `zai/glm-5.3`), own workspace `~/.openclaw/workspaces/marketing-outreach` whose AGENTS.md carries the owner-set voice rules (post-v1/v2 rejections) and hard boundaries (drafts only, no pricing, no ROI claims, public evidence only, sign as Randall), agentDir `~/.openclaw/agents/marketing-outreach/agent`. Tools: `read`/`web_search`/`web_fetch` only — exec, write, message, and session tools all denied, so it structurally cannot send anything. Added to `main.subagents.allowAgents` and `agentToAgent.allow`. Config backup: `openclaw.json.bak-marketing-agent-20260918`.
- **Gateway hot-loaded the new config — no restart needed; G8 untouched.** First spawn accepted with `resolvedModel: openai/gpt-5.6-luna`.
- **Standing routing rule (owner-set):** marketing and outreach copy requests route to the `marketing-outreach` agent. Main still QC's its output and owns delivery decisions.
- First task dispatched: v3 redraft of the 3 wave-1 emails + day-4 follow-up (`taskName: wf79-email-redraft-v3`).

## Stop Lines

- No real customer data.
- No real prospect outreach.
- No external delivery.
- No public launch.
- No credentials or customer-system access.
- No ad-account, CRM, phone, email, payment, POS, payroll, or customer writeback.
- No spend or subscription action.
- No guaranteed ROI/revenue claim.
- No legal, compliance, security, or certification readiness claim.
- No SQL-as-canon promotion.
- No finance/account/trading/capital authority.

## Acceptance Proof

WF79-SMB is morning-ready when:

- `generic_intelligence_saas_pivot.py --write --write-db --validate` passes.
- PM packet validates.
- The chosen sanitized slice has a clear owner pain, workflow map, packet output, automation blueprint, sales-practice surface, and boundary proof.
- Any customer-facing-looking artifact is explicitly internal/sample/review-only.

## Current State - 2026-06-18 10:00 MST

- The morning SMB/SaaS sprint executed under the PM lane `PM::smb-saas-parallel-morning-plan-execute-safe-next-step`.
- `generic_intelligence_saas_pivot.py --write --write-db --validate` passed and refreshed the full WF79-SMB packet family: scenario library, customer preview, pilot packet, Lead Rescue packet, automation blueprints, offer/ICP packet, demo packets, Marketing Ops blueprints, cockpit panel, sales practice packet, outreach prep validation, pilot readiness, rollout readiness, curriculum map, and phase closeout.
- Current `tmp/wf79-smb-phase-closeout.json` status is `ready`; phases 0-8 are internally ready/ok, and phase 9 remains `approval_required` for any real outreach or pilot gate.
- Remaining gate is explicit Randall approval before real outreach, real customer data, credentials, ads, external delivery, spending, or customer-system implementation.
- Boundary preserved: no real prospect/customer action, no external delivery, no public launch, no credential/customer-system access, no guaranteed ROI/revenue claim, no legal/compliance/security readiness claim, no finance/account/trading/capital authority, and no owner approval inference.

## Current State - 2026-07-04 22:07 Phoenix / 2026-07-05 UTC

- Randall created the future outreach identity `veritasaiflows@gmail.com` for Veritas AI Flows.
- This plan fits primarily in **WF79-SMB** because WF79-SMB owns SMB Workflow Clarity, Lead Rescue, Marketing Ops, pilot-readiness, outreach-prep, and real-pilot approval gates.
- WF75 remains the parent packaging lane because it owns the AI Drop-Service OS, Workflow Clarity Sprint service model, training assets, delivery templates, QA cadence, and private-pilot proof.
- The Gmail account is a future outreach channel identity only. It does not grant Veritas access, send authority, OAuth authority, connector authority, password authority, or customer/prospect contact authority.
- Recommended readiness posture: keep outreach manual until Randall explicitly approves a named first batch, exact copy, exact channel, follow-up rule, data rule, and tracking method.
- Safe near-term use: Veritas drafts emails, contact-form copy, reply scripts, status tracker rows, and owner approval cards; Randall signs in and sends manually from the Gmail account.
- Future owner-gated access path: use an official OAuth/delegated connector or app-specific service route only after exact approval. Never share the Gmail password in chat or store credentials in workspace files. If delegated access is configured, use least-privilege scopes and prefer draft/review workflows before any send-capable workflow.
- Phase 9 remains `approval_required`: no outreach, message sending, contact-form submission, payment link, customer data, CRM import, Google account mutation, external connector setup, or automated sending is approved by the existence of the Gmail account.

## Outreach Channel Readiness Plan

1. Internal-safe now: prepare Gmail account profile text, sender name guidance, signature draft, inbox labels, prospect tracker schema, and manual-send SOP as review-only artifacts.
2. Owner-gated next: Randall approves the first batch/channel/copy/follow-up rule and chooses whether the first test is manual Gmail send, official-site contact form, or both.
3. First pilot test: send only the approved microbatch manually, log the result in the workspace, and stop after one approved follow-up.
4. After response proof: decide whether to keep manual sending, build a draft-only Gmail workflow, or request an official connector/OAuth setup.
5. Scale gate: no automation, bulk sending, campaign tooling, CRM sync, payment flow, or customer-data handling until the first manual pilot produces honest response and delivery proof.
