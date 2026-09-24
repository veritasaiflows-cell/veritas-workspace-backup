<!-- openclaw:wiki:raw-source -->
# Open Follow Up Debt

Canonical page: `wiki/gaps/Open Follow Up Debt.md`
Canonical rendered SHA-256: `354d593220a3a9fc34a1dd5cd47e9659cdef060480e4d101d361e0fdbff704b7`.
Source snapshot SHA-256: `1232da06890b2c2a895aa50bd88f2fa976c072ff78872c8799a029c06af22b8c`.
Authority: review-only retrieval mirror; canonical wiki and named owner artifacts remain authoritative.

## Query aliases

- open followup triage
- improvement debt
- unrouted action backlog

## Canonical content

# Open Follow Up Debt

Status: synthesis only
Owner workflow: WF88
Generated page type: debt_view
Authority boundary: review-only map; no canon, approval, execution, cron mutation, portfolio mutation, model training, or owner approval inference.
Promotion path: wiki insight -> WF88 recommendation -> WF74/PM/Skill Workshop/validator route -> proof -> explicit approval or validated implementation where allowed.

## Source artifacts

- `tmp/improvement-ledger-current.json`
- `tmp/actionable-improvement-queue.json`
- `tmp/no-orphan-validator.json`
- `tmp/wf74-decision-docket.json`
- `tmp/wf88-os2-control-packet.json`
## Current debt

- Improvement open count: `8`.
- Follow-up-required open count: `0`.
- High-priority overdue open count: `2`.
- Pending skill proposal count: `0`.
- Actionable queue items: `8`.
- Actionable queue orphans: `0`.
- No-orphan validation: `ok`.
- Top actionable destination: `wf74_decision_docket`.
- Top actionable next action: Treat this as a current cron regression against the completed migration plan: inspect the blocked cron artifacts, repair the failing proof surface, then refresh cron control.

## Claim evidence

- `followup-no-orphan-health`: `{"actionable_missing_contract_count":0,"actionable_orphan_count":0,"followup_required_open_count":0,"no_orphan_validation":"ok"}`; authority `review_only`; source refs `improvement_ledger#/summary/followup_required_open_count`, `actionable_improvement_queue#/summary/orphan_count`, `actionable_improvement_queue#/summary/missing_contract_count`, `no_orphan_validator#/validation/status`.

Follow-up debt is real until closed as a verified fix, owner packet, applied skill proposal, pending skill proposal, monitor-only row, or superseded open improvement.
