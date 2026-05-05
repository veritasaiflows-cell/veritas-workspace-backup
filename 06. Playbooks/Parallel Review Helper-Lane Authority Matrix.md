# Parallel Review Helper-Lane Authority Matrix

## Purpose
Define exactly what helper lanes may do inside the WF20 review layer without implying final judgment or widening automation.

## Core rule
Helper lanes may prepare evidence, packets, contradiction findings, and distinct-output drafts.
They do not own final queue state, canonical truth, or approval-dependent actions.

## Authority matrix

| Lane / role | Allowed outputs | Prohibited outputs | Escalate when |
|---|---|---|---|
| Main session (Veritas) | final status reply, queue movement, registry update, closeout judgment, operator-action framing | none within approved scope, but must still honor manual-only boundaries | trust state is unclear or a boundary would be widened |
| Review cron run | review/status reply, reminder, proof-surface summary | canonical note mutation, queue movement, implied approval, autonomous universe/posture/publication changes | evidence is partial, stale, contradictory, or missing |
| Spawned packet-prep lane | intake packet, contradiction packet, affected-surface list, patch-prep candidate only when explicitly allowed later | canonical note edits, final routing judgment, final operator-action judgment | packet validation errors remain or source quality is insufficient |
| Contradiction / QA lane | gap list, contradiction note, validation verdict, missing-proof list | conflict resolution by assertion, autonomous closure, canonical edits | two sources disagree or a proof surface is missing |
| Independent audit lane | closure verdict, acceptance-proof check, residue, reopen triggers, next-work recommendation | implementation edits unless explicitly asked, self-closing the workflow without main-session integration | acceptance evidence is incomplete or cross-surface state disagrees |

## Packet-prep boundary
Any helper lane preparing a review object must emit a packet or distinct-output artifact that is explicitly subordinate to the main-session judgment layer.

Minimum packet-prep obligations:
- name exact files read
- name contradictions or missing proof
- name proposed routing only as a proposal
- default `canonical_mutation_allowed` to false
- stop when source quality or validation errors make routing unsafe

## Contradiction rules
A helper lane must escalate instead of smoothing over disagreement when:
- primary and secondary sources disagree materially
- a live artifact conflicts with the canonical control surface
- the latest window is missing and only stale artifacts exist
- a machine-prepared packet would imply thesis, deployment, or publication judgment

## Escalation rules
Escalate to the main session or Randall when the action would:
- mutate canonical finance notes
- add/remove/promote/demote tracked names or cadence
- change thesis, posture, or deployment state
- publish a workbook, PDF, or decision-grade deck
- widen cron authority or helper-lane permissions

## Distinct-output rule
If a helper lane writes anything, it should prefer a distinct-output artifact, audit note, or packet instead of editing the owner surface directly.

## Stop line
If a helper lane cannot stay inside packet-prep, contradiction review, or independent-audit scope, it must stop and return the blocker.

## Relationship to Workflow 20
This note is the Phase 3 helper-lane authority output for:
- `06. Playbooks/Project Continuity/Workflow 20 - Parallel Agents Automation and Human-Gated Review Workflow.md`

It inherits and must remain subordinate to:
- `06. Playbooks/Parallel Review Operator Action Taxonomy and Status Contract.md`
- `06. Playbooks/Research Automation Intake Packet Contract.md`
- `06. Playbooks/Automation Orchestration Protocol.md`
