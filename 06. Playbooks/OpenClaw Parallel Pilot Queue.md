# OpenClaw Parallel Pilot Queue

## Purpose

Define the live operator queue for deliberate parallel execution and workflow sequencing.

This note is the compact active control surface.
Detailed historical workflow entries now live in:
- `06. Playbooks/OpenClaw Parallel Pilot Queue - History.md`

## Resource posture

### Main default
- `openai-codex/gpt-5.4`
- use for orchestration, integration, final judgment, and higher-trust workspace work

### Spawned worker default
- `openai-codex/gpt-5.4`
- use for bounded implementation, patch prep, and detached worker passes by default

### Lower-complexity helper posture
- No lower-complexity Veritas-routed Codex helper is currently on the approved live model list.
- For bounded cheap helper work, prefer scope reduction, lighter task contracts, or manual external evidence review instead of routing through removed or stale model posture.

Do not use reduced-trust helper posture for:
- final trust adjudication
- canonical-state judgment
- ambiguous architecture decisions
- final portfolio or OS calls

## Pilot success standard

The queue is succeeding only if:
- completion time drops
- main-session clutter drops
- reconciliation burden stays low
- artifact ownership stays clear
- the user gets more finished passes, not more chatter

## Queue structure

Each meaningful queued item should make clear:
- lane owner
- model posture or helper posture
- deliverable
- what not to touch
- acceptance check
- category
- parallel posture
- execution mode
- QC complete

## Current chain state

### Active workflow
**Workflow 28 - Skills Critical Corrections and Coherence Hardening**

Status:
- active downstream lane after WF25 closed with follow-up on 2026-05-04
- exists to land the 2026-05-04 audit's critical skill fixes before the next board-sync / weekly-brief path relies on stale skill contracts
- Phase 1 now owns the critical live-skill corrections and technical-overlap decision path
- WF29 remains queued behind this lane so executable proof utilities are built only after the coherence layer is honest
- Randall explicitly directed strict sequential execution: finish WF28 with QA, hardening pass, and executive-summary closeout before WF29 opens

Reason:
- Workflow 25 is honestly closed at the intended scope
- Workflow 28 is the approved next downstream lane before WF29 and broader workflow widening because the audit found live correctness gaps in the skill layer

### Next approved queue item
**Workflow 29 - Skill Validation and Machine-Proof Utilities**

Status:
- queued directly behind WF28
- exists to turn the audit's proof-layer recommendations into bounded executable trust infrastructure
- should not open until WF28 closes with its own QA / hardening / executive-summary artifacts

WF24 closeout facts now live:
- cron-builder doctrine is explicit
- sibling retrofit checklist exists
- live finance sibling payloads were retrofitted to the explicit packet contract
- direct cron-history proof exists for the retrofitted post-close sibling
- independent audit and executive-summary artifacts exist

## Strict ordered execution queue for today (2026-05-04)

1. **WF20 Phase 2A - cron-builder packet standard**
   - status: completed
   - owner: Veritas main lane
   - category: control plane / automation
   - posture: serial
   - deliverable: hardened `06. Playbooks/Cron Job Protocol.md` so every new cron job must specify read-first files, execution order, response contract, stop lines, and spawn recommendation
   - acceptance check: met

2. **WF20 Phase 2B - review cadence and owner map**
   - status: completed
   - owner: Veritas main lane
   - category: control plane / automation
   - posture: serial
   - deliverable: one smallest honest review cadence with overlap-owner and downgrade rules
   - acceptance check: met via `06. Playbooks/Parallel Review Cadence and Owner Map.md`

3. **WF24 Phase 1 - cron build contract and retrofit checklist**
   - status: completed
   - owner: Veritas main lane
   - category: control plane / automation
   - posture: serial
   - deliverable: reusable cron-build contract plus retrofit checklist for live sibling finance jobs
   - acceptance check: met; the contract and checklist now exist and the sibling prompts were retrofitted to match

4. **WF24 Phase 2 through Phase 4 - proof, audit, and closeout**
   - status: completed (closed with follow-up)
   - owner: Veritas main lane
   - category: control plane / automation
   - posture: serial
   - deliverable: controlled proof, independent audit, closeout artifacts, and downstream promotion for the retrofitted cron family
   - acceptance check: met for closure at intended scope; post-close proof is history-visible, while morning/Sunday symmetry remains named residue and reopen-trigger material

5. **WF25 Phase 1 through Phase 4 - desk operating proof and handoff contract**
   - status: completed (closed with follow-up)
   - owner: Veritas main lane
   - category: research / governance
   - posture: serial
   - deliverable: real operating queue, decision objects, first live pilot proofs, downstream handoff contract, and closeout-layer artifacts
   - acceptance check: met for closure at intended scope; the desk can now produce honest admit/defer/hold outcomes without reconstructing chat history
   - closeout rule: satisfied; WF25 now has chain-log, executive-summary, checkpoint, and audit surfaces in progress for final verification

6. **WF28 Phase 1 - critical skill corrections**
   - status: active
   - owner: Veritas main lane
   - category: skills / governance
   - posture: serial
   - deliverable: land the audit's critical live-skill fixes and resolve the technical-analysis overlap decision path
   - acceptance check: the audited critical fixes are landed and the overlap/routing cleanup path is explicit before the next board-sync / weekly-brief execution
   - closeout rule: do not open WF29 until WF28 reaches QA, hardening pass, independent audit / executive-summary closeout, and cross-surface sync

7. **WF29 Phase 1 - validation tier truth and machine-proof utility design**
   - status: queued behind WF28
   - owner: Veritas main lane
   - category: skills / validation
   - posture: serial behind WF28
   - deliverable: honest validation-tier labeling plus bounded machine-proof utility design for swarm handshake / sidecar validators / automation trust block
   - acceptance check: validation tiers and the first executable-proof pilot set are explicit instead of implied
   - closeout rule: same finish-to-closeout discipline; add downstream workflows only after QA and executive-summary closure artifacts are real

8. **WF21 Phase 1 - source map and pilot coverage set**
   - status: queued behind WF29
   - owner: Veritas main lane, helper lanes optional later
   - category: research / automation
   - posture: serial until the source map is explicit
   - deliverable: approved source tiers, blocked source classes, pilot names, and first raw-event input file aligned to WF25 intake needs
   - acceptance check: `scripts/research_intake_packet.py` can be run against a real narrow input set that feeds the research desk cleanly without scope drift

9. **WF26 Phase 1 - fresh external intelligence and geopolitical verification map**
   - owner: Veritas main lane
   - category: research / external intelligence
   - posture: serial
   - deliverable: approved fresh-news / geopolitical source map, pilot sleeves, and unresolved-truth handling rules
   - acceptance check: the lane can keep fast-moving developments visible without rumor-driven false certainty

10. **WF27 Phase 1 - predictive analytics and forecasting readiness**
   - owner: Veritas main lane
   - category: research / quantitative methods
   - posture: blocked until upstream evidence and provenance layers are real
   - deliverable: bounded forecast-question set, target definitions, and data-readiness audit
   - acceptance check: predictive work stays methodology-first rather than model theater

11. **WF21 Phase 2 - one manual packet dry run**
   - owner: Veritas main lane
   - category: research / automation
   - posture: serial
   - deliverable: one reviewed packet run with visible stop lines and unresolved-truth handling
   - acceptance check: the packet remains review-only and low-noise

12. **WF22 Phase 1 - stale-claim pilot inventory**
   - owner: Veritas main lane
   - category: note-sync / reconciliation
   - posture: blocked until WF21 yields honest candidates
   - deliverable: pilot stale-claim list and owner-surface map
   - acceptance check: candidates stay freshness/mechanical, not thesis rewrite

13. **WF23 stays gated**
   - do not open today unless WF21 and WF22 both become materially real

### Recent completed item
**Workflow 16 family - Research Automation and Canonical Freshness Hardening**
- closed with follow-up
- no recurring research cron or auto-apply helper was opened
- canonical mutation remains fail-closed by automation in v1

## Compact execution order

1. Workflow 1 - policy target-range fail-closed hardening [completed]
2. Workflow 2 - residual atomic-write migration [completed]
3. Workflow 3 - external payload schema guards [completed]
4. Workflow 3B - independent workspace QA audit and QA-pass skill creation [completed]
5. Workflow 3C - canonical-note trust gate enforcement [completed]
6. Workflow 4 - sequential chain protocol [completed]
7. Workflow 4B - live cron shakedown + run ledger hardening [completed]
8. Workflow 4C - finance chain truth-sync hardening [completed]
9. Trust-grade reassessment / warning-residue gate [completed - closed with follow-up]
10. Workflow 5 - PDF/Excel workflow-fit pass [completed - closed with follow-up]
11. Workflow 6 - coverage tier framework [completed - closed with follow-up]
12. Workflow 7 - sector coverage expansion plan [completed - closed with follow-up]
13. Workflow 8 - command center chain readiness review [completed - historical no-go preserved; bounded reopen closed]
14. Workflow 9 - research department operating model [completed - closed with follow-up]
15. Workflow 9A - workspace structure and drift cleanup [completed]
16. Workflow 9B - surface alignment and drift-guard hardening [completed]
17. Workflow 10 - subagent/session lifecycle reliability review [completed]
18. Workflow 11 - coverage admission model [completed]
19. Workflow 12 - macro / policy trust repair [completed]
20. Workflow 13 - script and tmp hygiene hardening [completed]
21. Workflow 14 - operator script boundary and lifecycle cleanup [completed]
22. Workflow 15 - script performance and payload modularity backlog [deferred]
23. Workflow 17 - sequential workflow contract and skills hardening [completed]
24. Workflow 18 - spawn, closeout, and skills governance hardening [completed]
25. Workflow 16 - research automation and canonical freshness hardening [closed with follow-up]
26. Workflow 16A - research intake desk and parallel review packets [completed]
27. Workflow 16B - canonical freshness sync and gated note update helpers [completed]
28. Workflow 19 - playbooks retrieval and governance cleanup [closed with follow-up]
29. Workflow 20 - parallel agents automation and human-gated review workflow [closed with follow-up]
30. Workflow 24 - cron job build contract and session handoff hardening [closed with follow-up]
31. Workflow 25 - research department completion and coverage admission operations [closed with follow-up]
32. Workflow 28 - skills critical corrections and coherence hardening [active]
33. Workflow 29 - skill validation and machine-proof utilities [queued behind Workflow 28]
34. Workflow 21 - recurring source bundle and review window pilot [queued behind Workflow 29]
35. Workflow 26 - fresh external intelligence and geopolitical verification pilot [queued behind Workflow 21]
36. Workflow 27 - predictive analytics and forecasting readiness [queued behind Workflow 26]
37. Workflow 22 - canonical freshness patch pilot and surface sync [queued behind Workflow 21]
38. Workflow 23 - Command Center fresh brief and decision surface tightening [queued behind Workflow 22]

## Capacity rule for this queue

At one time:
- 1 active OpenClaw subagent implementation lane
- 1 active Claude review lane
- 0 or 1 cheap helper lane

Do not open multiple cleanup or governance implementation lanes at once unless the merge cost is clearly lower than the speed gain.

## Queue hardening rule

- keep execution order explicit
- update this queue before opening a new major lane when real blockers or prerequisites change
- prefer a named workflow over chat-only residue
- do not widen scope mid-chain without updating the queue entry
- do not mark a workflow advanced unless execution mode and QC posture are visible here or in the registry

## History rule

Use `06. Playbooks/OpenClaw Parallel Pilot Queue - History.md` for:
- detailed completed-workflow history
- long-form rationale from older completed items
- preserved historical proof context that no longer belongs in the active operator surface
