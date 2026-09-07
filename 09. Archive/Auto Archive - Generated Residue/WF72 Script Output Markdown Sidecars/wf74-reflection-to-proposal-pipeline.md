# WF74 reflection-to-proposal pipeline

- Generated: 2026-05-24T05:52:54Z
- Status: ready for pilot

## Stages

| stage | name | owner | output | gate |
|---|---|---|---|---|
| 1 | capture | Veritas main / Continuity Desk | raw_reflection | meaningful work, correction, validator failure, or repeated friction only |
| 2 | classify | Veritas main | lesson_type + destination | daily/durable/operating/tooling/domain/automation classification required |
| 3 | evidence_bind | Analytics / Proof Desk | source links, files, validator evidence | no vibes-only lessons |
| 4 | proposal | Implementation / Refactor Desk | structured improvement proposal | files affected, risks, validation, rollback named |
| 5 | evaluate | Evaluator / QA Desk | eval score + failure modes | truth/evidence/boundary/continuity/actionability checks pass |
| 6 | apply_or_defer | Veritas main | applied change or explicit queue item | human approval when authority/config/destructive/external scope is touched |
| 7 | monitor | OS Operator | recurrence/regression status | same failure recurrence tracked before durable closeout |

## Required proposal fields

- problem
- evidence
- lesson_type
- destination
- proposed_change
- files_affected
- risks
- validation
- rollback
- qa_required
- authority_boundary

## Stop lines

- base-model self-modification
- self-preservation/replication/resource acquisition
- autonomous authority expansion
- config/auth/channel/service mutation without explicit approval
- second memory tree
- owner approval inference
- portfolio/trade/account/paper/live authority
- automatic skill installation
