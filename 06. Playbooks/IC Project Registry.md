# IC Project Registry

## Purpose

Single operator view of active independent-contractor projects.

Use this file to track:
- which IC owns what
- which phase is active
- what the next pass is
- which projects are blocked on operator judgment
- where the continuity note and chain log live

This is the control layer above individual project notes.

## Operating Rules

- one row per active or recently paused project
- update when ownership, phase, or next pass changes materially
- continuity note remains project truth
- chain log remains pass-by-pass ledger
- this registry is the operator control board
- do not treat a workflow as advanced unless `execution mode` and `QC complete` are visible here or in the linked active queue entry

## Active Projects

| Project                               | Lane                                 | Owner   | Status                       | Current phase                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                        | Execution mode                                                                                          | QC complete                 | Last completed pass                                                                                       | Next pass                                                                                                                                                                        | Waiting on operator?                                                                                               | Continuity note                                                                                           | Chain log                                                                      |
| ------------------------------------- | ------------------------------------ | ------- | ---------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------- | --------------------------- | --------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------ | --------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------ |
| OpenClaw Trust-Hardening Queue        | Control plane / workspace governance | Veritas | Active                       | Workflows 9B, 10, 11, and 12 are honestly closed. The chain outcome is real: note/validator truth-sync is hardened, runtime-proof assumptions are explicit, run-summary trust fields are fail-closed again for scheduled windows, intake governance is procedural instead of chat-memory-based, and macro/policy caution is now separated cleanly from stale inherited wording. Named residue stays visible instead of hidden: memory embedding credential/index health is still broken; the upstream daily-note writer remains unpatched runtime debt while the local dedupe guard stays in place; policy probabilities still use a simplified approximation model; NVDA remains the main named timing-confirmation residue when decision-critical. | Main-session controlled; helper lanes limited to planning/research/audit                                | No                          | Workflow 12 closure - active note surfaces repaired, bounded validator guard added, final QA note written | Take the post-chain commit checkpoint, then deliver the end summary and only afterward reopen automation / cron / heartbeat follow-on work                                       | No - the required WF9B -> WF10 -> WF11 -> WF12 chain is complete; next operator touchpoint is checkpoint + summary | `06. Playbooks/Project Continuity/Workflow 12 - Macro Policy Trust Repair.md`                             | -                                                                              |
| E17 Universe Synchronization          | Core OS integrity                    | Veritas | Closed with follow-up        | Core ownership drift closed; residual warning stack handed forward into Workflow 5 packaging guardrails                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                              | Main-session closure / QA                                                                               | Yes                         | Phase 4 Sub-Pass 2 - direct date pass plus GOOG/MSFT revalidation                                         | None inside E17; residual timing-sensitive/date-trust caveats now live in the Workflow 5 degraded-contract guardrails and later trust repair work                                | No - the broader warning-gate judgment is now complete enough for honest handoff                                   | `06. Playbooks/Project Continuity/E17 Universe Synchronization.md`                                        | `06. Playbooks/Project Continuity/E17 Universe Synchronization - Chain Log.md` |
| Capital Deployment Readiness          | Deployment readiness                 | Veritas | Closed with follow-up        | Phase 4 through Phase 7 are complete. The lane is now bounded operating infrastructure: the morning review cadence is explicit, helper packets are read-only by contract, the surface-integration decision stays JSON/operator-only in v1, and canonical readiness judgment still belongs to the Trigger Sheet owner layer. Residue stays named rather than hidden: NVDA timing confirmation, BRK.B next-quarter timing cleanup, and macro/policy caution remain reopen triggers rather than fake-green closure exceptions.                                                                                                                                                                                                                                          | Main-session owner; helper lanes limited to read-only packet prep and contradiction review              | Yes                         | Phase 7 - Closeout and automation posture lock                                                            | None unless a named reopen trigger fires                                                                                                                                        | No - normal use is defined; revisit only if visibility/autonomy widening is intentionally requested             | `06. Playbooks/Project Continuity/Capital Deployment Readiness.md`                                        | `06. Playbooks/Project Continuity/Capital Deployment Readiness - Chain Log.md` |
| Sequential Workflow Protocol Hardening | Control plane / automation          | Veritas | Active                       | Workflow 17 is now the active protocol-hardening pass. The goal is to standardize entry checklist, acceptance gates, exit checklist, checkpoint/commit decision, next-pass expectations, and skills alignment across major sequential workflows before more automation-layer expansion opens. Workflow 18 remains the follow-on governance hardening pass for spawn, closeout, and skills behavior after Workflow 17 establishes the base contract. The immediate downstream consumer is Workflow 16: the research automation lane now explicitly needs source-bundle, ownership-boundary, review-window, handoff, stop-line, and canonical-drift-protection contract sections. | Main-session controlled; helper lanes allowed for bounded read-only audit and draft-prep only           | No                          | Workflow opened - contract and skills-hardening scope defined                                             | Execute Workflow 17 Phase 1 inventory first, specifically mapping the contract sections Workflow 16 will inherit; then queue Workflow 18 immediately behind it                    | No - this is the higher-priority trust blocker before Workflow 16 execution                                     | `06. Playbooks/Project Continuity/Workflow 17 - Sequential Workflow Contract and Skills Hardening.md`     | -                                                                              |
| Scripts + Tmp Optimization            | Script hygiene / tmp lifecycle       | Veritas | Paused after bounded closure | Workflow 13 and Workflow 14 are honestly closed. The low-risk hygiene pass is done, and the structural boundary pass is done: selected operator-only implementations now live behind `scripts/operators/` while root CLI compatibility wrappers preserve the documented surface. `call_log_sync.py`, `workbook_template.py`, and the equity report wrappers were intentionally kept in place because live callers or active documented use still justify them. Workflow 15 remains deferred backlog, not active work.                                                                                                                                                                                                                                | Main-session controlled; helper lanes optional for caller tracing or usage audit                        | Yes for Workflows 13 and 14 | Workflow 14 closure - compatibility-first operator boundary cleanup validated                             | Leave paused unless Workflow 15 is intentionally opened for performance/modularity work                                                                                          | No - no further action is required inside this stream unless Workflow 15 is explicitly opened                      | `06. Playbooks/Project Continuity/Workflow 14 - Operator Script Boundary and Lifecycle Cleanup.md`        | -                                                                              |
| Research Automation Freshness Monitor | Research / automation                | Veritas | Active, held behind trust hardening | Workflow 16 remains the active hardening wrapper for this lane, but execution is intentionally held behind Workflow 17 and Workflow 18. The approved posture is now explicit: parallel agents are a contract-building and QA layer, not a freeform research swarm. Workflow 16A owns the Source Bundle Contract, Intake Packet Contract, and Routing / Promotion Contract. Workflow 16B owns the Canonical Freshness Patch Contract plus the first bounded pilot. Canonical mutation remains default-no until the patch contract and pilot prove otherwise. | Main-session controlled; helper lanes allowed for bounded contract-building, packet QA, contradiction review, and draft prep only | No                          | Workflow 16 opened - automation posture and sub-work split defined                                        | After Workflow 17 and Workflow 18 close, execute Workflow 16A in order (source bundle -> intake packet -> routing/promotion), then Workflow 16B (freshness patch contract -> bounded pilot) | No - this lane is intentionally paused behind protocol / skills hardening, not abandoned                         | `06. Playbooks/Project Continuity/Workflow 16 - Research Automation and Canonical Freshness Hardening.md` | -                                                                              |

## Intake Criteria For New Projects

Before opening another IC project, confirm:
- it improves freshness, deployability, trust, or coverage materially
- it has a distinct lane
- it has a continuity note home
- it has a named owner
- it is not overlapping an active semantic rewrite

If any answer is no, do not open the project yet.

## Current Capacity Guidance

Current recommended parallel load:
- 2 active IC-owned projects at once
- plus 1 active OpenClaw subagent pilot lane for bounded implementation or inspection work
- plus 0-1 cheap helper lane (Gemini Flash or equivalent) only for bounded follow-up checks

Codex Spark rule:
- `openai-codex/gpt-5.3-codex-spark` is removed from Veritas-routed workflow use
- Randall may still use it manually for QA/reports and bring the output back for review

Do not scale beyond this until:
- registry discipline is stable
- chain logs are consistently updated
- project handoffs are staying short instead of growing
- cross-project synthesis burden remains manageable

OpenClaw pilot control note:
- `06. Playbooks/OpenClaw Parallel Pilot Queue.md`

## Likely Next Project Candidates

Only after current lanes stabilize:
- OpenClaw Parallel Pilot Queue execution
- Healthcare Sleeve Thesis Tightening
- Controlled Note Reconciliation
- Morning Deployment Surface

These should not all be opened at once.
