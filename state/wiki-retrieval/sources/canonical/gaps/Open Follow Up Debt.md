<!-- openclaw:wiki:raw-source -->
# Open Follow Up Debt

Canonical page: `wiki/gaps/Open Follow Up Debt.md`
Canonical rendered SHA-256: `dbb7a36ecd109d6dac13a51676617d6aec299eae6e3a25dbb87c926ebccddc8f`.
Source snapshot SHA-256: `3601a6df6c84a49ca4416da23af657e1aaff9026ecf9c52e5f23dcc898744160`.
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

- Improvement open count: `7`.
- Follow-up-required open count: `0`.
- High-priority overdue open count: `3`.
- Pending skill proposal count: `0`.
- Actionable queue items: `7`.
- Actionable queue orphans: `0`.
- No-orphan validation: `ok`.
- Top actionable destination: `wf74_decision_docket`.
- Top actionable next action: Treat this as a current cron regression against the completed migration plan: inspect the blocked cron artifacts, repair the failing proof surface, then refresh cron control.

## Claim evidence

- `followup-no-orphan-health`: `{"actionable_missing_contract_count":0,"actionable_orphan_count":0,"followup_required_open_count":0,"no_orphan_validation":"ok"}`; authority `review_only`; source refs `improvement_ledger#/summary/followup_required_open_count`, `actionable_improvement_queue#/summary/orphan_count`, `actionable_improvement_queue#/summary/missing_contract_count`, `no_orphan_validator#/validation/status`.

Follow-up debt is real until closed as a verified fix, owner packet, applied skill proposal, pending skill proposal, monitor-only row, or superseded open improvement.
