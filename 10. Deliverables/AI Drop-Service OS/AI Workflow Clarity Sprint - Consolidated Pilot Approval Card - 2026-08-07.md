# AI Workflow Clarity Sprint - Consolidated Pilot Approval Card

- Generated: 2026-08-07 (Phoenix)
- Status: **APPROVED - all default recommendations** (Randall, 2026-08-07 webchat: "Yes, proceed with recommendations.")
- Approved scope: Decisions 1-7 as recommended. Decision 8 items remain deferred. Sends remain manual by Randall (or explicit per-send approval per Decision 4).
- Purpose: single decision surface covering every gate item named in the 2026-07-03 offer draft (target slice, exact wedge, pricing, outreach copy, data boundary, delivery terms, measurement plan) so one approval unlocks Phase 2 outreach.
- Authority: approval of this card authorizes only the exact scope below. It does not authorize bulk outreach, payments infrastructure, customer data ingestion, SMS, ads, or any live-system access.

## What Already Exists (Phase 1 asset inventory - verified 2026-08-07)

| Asset | File | State |
| --- | --- | --- |
| One-page offer | `AI Workflow Clarity Sprint - HVAC Internal Offer Draft - 2026-07-03.md` | Ready |
| Intake/discovery script | `AI Workflow Clarity Sprint - HVAC Intake Discovery Script - 2026-07-03.md` | Ready |
| Synthetic demo deliverable | `AI Workflow Clarity Sprint Synthetic Demo - 2026-07-03.md` | Ready (labeled synthetic) |
| Outreach packet + 20 researched prospects | `AI Workflow Clarity Sprint - HVAC Private Pilot Outreach Packet - 2026-07-03.md` | Ready, send-gated |
| Prospect research source | `workspaces/research-scout/findings/wf75/hvac-prospect-research-20260703.json` | 5 weeks old - light refresh recommended before send |

## Decision 1 - Target slice

**Recommended:** single-location residential HVAC operators in the East Valley / Phoenix metro with public emergency/same-day/scheduling signals. First batch = the 5 priority prospects from the outreach packet:

1. Olive Air & Heating (Gilbert)
2. Instant Heating and Air (Phoenix)
3. Frozen Cactus Air (Mesa)
4. Cold Stinger Heating & Air Conditioning (Phoenix)
5. Norris Air (Gilbert)

- [ ] Approve as listed
- [ ] Substitute prospects: ______

## Decision 2 - Exact wedge

**Recommended:** missed-call recovery + callback-handoff workflow only. One workflow, 5 business days, diagnostic only. No production changes, no credentials, no call recording/SMS setup.

- [ ] Approve
- [ ] Change: ______

## Decision 3 - Pricing

**Recommended:** quote **$500 fixed** for the pilot Sprint. If a high-fit prospect hesitates, Randall may at his discretion offer a founding-pilot rate down to free-in-exchange-for-feedback-and-testimonial. No payment is collected until a separate payment-method approval (Decision 8) - the first conversation only tests willingness to pay.

- [ ] Approve $500 with discretionary founding-rate fallback
- [ ] Different price: ______

## Decision 4 - Outreach channel and copy

**Recommended:** manual send only, by Randall, using official-site public contact form or public business email. Copy = **Email 1** (or the contact-form variant) from the outreach packet, verbatim. One follow-up (Email 2) after 3-5 business days, then stop. No SMS, no phone for first batch, no automation, max 5 sends.

- [ ] Approve
- [ ] Edit copy first
- [ ] Veritas may send on my behalf after I approve each exact message (explicit per-send approval still required)

## Decision 5 - Data boundary

**Recommended (restates packet rules):** official-site public business contact paths only; no scraped/personal emails; no snippet-only phone numbers; prospect tracking in workspace only, no PII beyond public business contact info; during any pilot, redacted/synthetic examples only - live customer data, recordings, transcripts, or credentials trigger stop-and-review.

- [ ] Approve
- [ ] Tighten/change: ______

## Decision 6 - Delivery terms

**Recommended:** 5 business days from kickoff call; deliverables = the 10-item list in the offer draft (workflow map, risk summary, intake checklist, handoff checklist, PoC prompt pack, 30-day backlog, closeout summary, etc.); delivered as PDF + one 30-minute walkthrough call; no ROI/compliance/emergency-response claims anywhere in delivery.

- [ ] Approve
- [ ] Change: ______

## Decision 7 - Measurement plan

**Recommended:** track per prospect: contacted (y/n), channel, date, response (y/n), fit call booked (y/n), disqualify reason, follow-up state. Kill criteria: 10 total outreaches (batch 1 + one refill batch) with zero discovery calls -> stop and re-niche/reprice before further outreach. Pilot success = 1 completed Sprint + explicit answer on willingness to pay.

- [ ] Approve
- [ ] Change: ______

## Decision 8 - Explicitly deferred (not part of this card)

- Payment method/infrastructure (invoice, Stripe, etc.) - separate approval when a prospect says yes
- Phone/voicemail outreach - separate approval + phone-path validation
- Any real customer data ingestion - separate privacy boundary review
- Batch 2 prospects (#6-20 research pool) - separate refresh + approval

## Recommended pre-send checklist (Veritas executes after approval, before Randall sends)

1. Re-verify the 5 prospect sites are live and contact paths unchanged (public pages only).
2. Render the one-page offer to a clean customer-facing PDF (strip internal gate/authority language).
3. Set up the manual outreach tracker file per Decision 7.

## Bottom line

Phase 1 is complete: offer, script, demo, prospect list, and copy all exist and were verified today. This card is the only thing between you and first outreach. Approve it (or mark edits) and Phase 2 starts with 5 manual sends.
