# SMB + SaaS Parallel Implementation Plan - 2026-06-18

Created: 2026-06-17 23:25 MST / 2026-06-18 UTC  
Owner: Veritas main session  
Status: morning pickup plan, review-only, implementation-ready inside gates

## Decision

Continue SMB Workflow Clarity and internal SaaS deliverable implementation in parallel tomorrow morning.

This does not resume public/customer SaaS delivery. The finance-delivery cron series remains paused. The daily/weekly/monthly PDF and Excel series becomes a manual internal SaaS deliverable gate: prove the format, workflow purpose, export quality, source freshness, authority labeling, and operator usability before any later customer/public decision.

## Morning Objective

By the end of the next work block, produce one clean internal implementation slice on each side:

- SMB: one stronger sanitized Lead Rescue / Marketing Ops packet path with blueprint, demo, sales-practice, and boundary proof.
- SaaS: one stronger internal deliverable-gate path showing what the PDF/Excel cadence is for, how it is QA'd, and how it stays review-only while cron is paused.
- PM/WF: PM first-read packet surfaces this plan as the morning sprint, while exact workflow notes preserve the gate boundaries.

## First Read

Use these first, in order:

1. `Audit/SMB-SaaS-Parallel-Implementation-Plan-2026-06-18.md`
2. `python scripts\pm_control_packet.py --write --write-db --validate`
3. `python scripts\workflow_router.py WF79-SMB --answer all`
4. `python scripts\workflow_router.py WF75 --answer all`
5. WF75 continuity note and WF79-SMB continuity note

## Parallel Lanes

| Lane | Workflow | Owner shape | Output | Proof | Stop line |
|---|---|---|---|---|---|
| A. SMB packet and blueprint | WF79-SMB | Helper-safe if leased | Sanitized Lead Rescue / Marketing Ops packet refresh: offer/ICP, demo packet, blueprint, service-state, sales-practice next action | `python scripts\generic_intelligence_saas_pivot.py --write --write-db --validate` | No real customer data, outreach, credentials, public claims, spend, or customer-system writeback |
| B. SaaS deliverable gate | WF75 | Helper-safe if leased | Internal PDF/Excel gate definition: daily/weekly/monthly purpose, fields, QA checklist, manual runbook while cron stays paused | `python scripts\wf75_deliverable_packager.py --write --validate` and manual finance-delivery status proof | No customer delivery, regulated-advice claim, source/licensing assumption, account/brokerage action, or cron restart |
| C. Academy and operator readiness | WF75 / WF79-SMB | Parallel only if disjoint from A/B | Training/sales-practice handout update for Randall: offer explanation, discovery questions, packet review, stop-line QA | `python scripts\wf75_training_desk.py --write --write-md --write-training-assets --validate` | No certification, legal/compliance/security readiness, or external use claim |
| D. QA boundary pass | Shared | Main or helper | Boundary lint and no-leak/no-claim review across packet, blueprint, exports, and PM handoff | Existing WF79-SMB validation artifacts plus PM packet validation | Stop on any real customer data, outbound language, ROI guarantee, legal/security certainty, or authority widening |
| E. PM integration | PM/WF | Main session | PM morning sprint lane and implementation job queue point to this plan; continuity notes identify pickup path | `python scripts\pm_control_packet.py --write --write-db --validate` | No route/Active Workflows edits while another lane owns those files |

## Execution Order

1. Refresh PM control packet and confirm `smb_saas_parallel_morning_plan` is the visible morning action.
2. Lease Lane A and Lane B as disjoint write surfaces before edits.
3. Run Lane A first if only one helper is available; run Lane B in parallel if the write lease is clean.
4. Main session integrates A/B results into the audit plan follow-up section or continuity notes.
5. Run QA boundary pass after both lanes produce artifacts.
6. Refresh PM control packet again.
7. If the active WF78 lane has released `Active Workflows.md` and `workflow_routing_index.py`, reconcile those route surfaces so WF75 is labeled as an internal SaaS deliverable gate while public/customer SaaS remains paused.

## SaaS Deliverable Gate Definition

The PDF/Excel daily/weekly/monthly set is not a publishing schedule right now. It is the test gate for a future SaaS/service product.

Minimum gate questions:

- What decision does this deliverable support?
- What source freshness is required before it can be trusted?
- What fields are mandatory in PDF and Excel?
- What fields are explicitly prohibited because they imply advice, account authority, suitability, execution, or legal/compliance readiness?
- What can be automated safely, and what must remain manual review?
- What validator proves no public/customer authority leaked into the artifact?
- What would make Randall say this is useful enough to preserve?

## SMB Implementation Definition

The SMB lane remains service-first, not agency drift and not SaaS-first.

Minimum gate questions:

- Which owner pain is being solved: missed lead, slow follow-up, stale lead, poor visibility, weak handoff, or no next action?
- What is the before/after workflow map?
- What manual packet can Randall inspect without a real customer?
- What automation blueprint is plausible without credentials or implementation access?
- What would a real pilot require later: approval, prospect identity, data permission, tool access, legal/compliance/security posture, and customer delivery boundary?

## Acceptance Proof

Morning work is acceptable when:

- PM packet validates and surfaces the morning sprint lane.
- WF75 continuity notes describe the paused-cron/internal-gate posture.
- WF79-SMB continuity notes describe the sanitized implementation sequence.
- The audit plan remains the first-read execution contract.
- Any generated packet/export remains review-only and internally labeled.
- No live/public/customer/outreach/account/credential/action authority is introduced.

## Known Limits

- `Active Workflows.md` and `scripts/workflow_routing_index.py` are currently owned by an active WF78 lane. Do not edit those surfaces until the WF78 lane releases them.
- PM can point to this plan now, but route-index reconciliation remains a follow-up if the WF78 lease is still active.
- This plan is not approval for outreach, customer delivery, public launch, cron restart, external messages, spend, or capital/execution activity.

