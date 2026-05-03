# Workflow 16 - Research Automation and Canonical Freshness Hardening

## Objective
- Build the research-automation control plane without allowing scheduled research or freshness work to drift into uncontrolled canonical mutation.
- Convert Workflow 17 / Workflow 18 governance outputs into an explicit live research-automation skeleton.
- Finish the umbrella lane only after Workflow 16A and Workflow 16B close honestly behind it.

## Current State
- **Closed with follow-up** on 2026-05-03.
- The readiness gate is complete.
- Workflow 16A contracts are complete.
- Workflow 16B patch contract and bounded pilot are complete.
- No recurring research cron was enabled.
- Canonical mutation remains fail-closed by automation in v1.

## Last Meaningful Progress
- Reviewed `08. Audits/Automation Workflow Review - 2026-05-03.md` and used it as the governing truth baseline for this chain.
- Retrofitted Workflow 16 / 16A / 16B to the major-workflow contract standard.
- Approved the four contract artifacts needed for the lane.
- Completed a bounded freshness pilot with manual approval only.
- Refreshed the stale Cron Run Ledger proof timestamps called out in the opening audit.

## Scope
- close the Workflow 16 readiness gate honestly
- inherit WF17 / WF18 governance explicitly
- define the handoff to 16A and 16B
- ensure the contract artifacts, bounded pilot proof, and closeout surfaces exist
- keep the whole lane sequential and fail-closed

## Out of Scope
- enabling recurring research cron jobs in this pass
- auto-applying canonical note changes
- thesis rewrites or deployment-state promotion by automation
- workbook/PDF presentation promotion
- broad universe expansion or freeform multi-agent research swarming

## Preflight / Entry Checklist
- [x] Workflow 16 was still the real active workflow at open.
- [x] The owning continuity note was current enough to resume cleanly.
- [x] Queue and registry agreed that WF16 was the active readiness gate.
- [x] Workflow 17 / Workflow 18 governance outputs were already live.
- [x] The lane remained bounded to contract-building, bounded pilot work, and QA.
- [x] No recurring research cron was enabled before contract completion.
- [x] Canonical mutation remained default-no by automation.
- [x] Helper-lane role stayed read-only contract challenge only.

## Execution Posture
- **serial main-session** for umbrella control, queue movement, owner-boundary judgment, and final closeout
- helper-lane support limited to bounded read-only contract challenge / QA

## Owner Layer
- generated contract artifacts -> playbook notes under `06. Playbooks/`
- sample packet and pilot artifacts -> `tmp/research-automation/`
- workflow truth -> `06. Playbooks/Project Continuity/Workflow 16*.md`
- canonical finance notes -> human-approved only

## Review Window
- readiness / governance pass: same-session main control-plane window
- downstream intended operating windows after approval: premarket, post-close, Sunday, and bounded event-driven manual review only
- no recurring research window was activated in this workflow

## Stop Lines
Stop the workflow instead of pretending success if:
- contract language widens into implied autonomous judgment
- research packets start acting like a second truth layer
- canonical mutation ceases to be explicit and human-approved only
- owner-surface boundaries become ambiguous
- low-confidence or rumor-heavy evidence is allowed to carry routing or patch decisions
- queue / registry / continuity note cannot be aligned honestly

## Surface / Handoff Posture
- dashboard / workbook / weekly brief outputs remain **review surfaces only**
- thesis-review queue remains a **routing surface only**
- freshness patch packets remain **proposal surfaces only**
- canonical notes remain **manual-approval surfaces only**

## Canonical Mutation Posture
- **disallowed by automation in v1**
- manual main-session approval is required for any applied freshness patch
- no auto-apply, no silent note mutation, no posture/thesis changes under freshness wording

## Acceptance Gates
Workflow 16 closes honestly only if all are true:
1. `Workflow 16`, `Workflow 16A`, and `Workflow 16B` notes are upgraded to the major-workflow contract standard.
2. The four governing contract artifacts exist:
   - `06. Playbooks/Research Automation Source Bundle Contract.md`
   - `06. Playbooks/Research Automation Intake Packet Contract.md`
   - `06. Playbooks/Research Automation Routing and Promotion Contract.md`
   - `06. Playbooks/Research Automation Canonical Freshness Patch Contract.md`
3. Sample packet evidence exists at `tmp/research-automation/intake-packet-samples.json`.
4. Bounded pilot evidence exists at `tmp/research-automation/freshness-pilot-2026-05-03.json`.
5. At least one low-risk freshness patch was manually approved and applied without widening autonomy.
6. Queue, registry, continuity note, and chain log all agree on closure state.
7. A bounded QA audit exists naming residue and reopen triggers.

## Exit / Closeout Checklist
- [x] Workflow scope completed without opening research cron early.
- [x] Governance inheritance made explicit before 16A / 16B closeout.
- [x] Contract artifacts and pilot artifacts exist.
- [x] Helper-lane contract challenge integrated.
- [x] Queue / registry / continuity alignment updated.
- [x] Named residue and reopen triggers kept visible.
- [ ] Checkpoint posture finalized.

## Checkpoint Decision
- **pending final checkpoint action during same-session closeout**

## Next Pass
- Open `Workflow 19 - Playbooks Retrieval and Governance Cleanup` as the next approved major lane.

## Next 1-2 Adjacent Candidate Workflows
1. `Workflow 19 - Playbooks Retrieval and Governance Cleanup`
2. Future reopen only if Randall intentionally asks for recurring research cron, gated helpers, or wider autonomy beyond the current fail-closed boundary

## Key Files
- `08. Audits/Automation Workflow Review - 2026-05-03.md`
- `06. Playbooks/Major Workflow Contract Standard.md`
- `06. Playbooks/Spawn and Closeout Governance Matrix.md`
- `06. Playbooks/Research Automation Source Bundle Contract.md`
- `06. Playbooks/Research Automation Intake Packet Contract.md`
- `06. Playbooks/Research Automation Routing and Promotion Contract.md`
- `06. Playbooks/Research Automation Canonical Freshness Patch Contract.md`
- `tmp/research-automation/intake-packet-samples.json`
- `tmp/research-automation/freshness-pilot-2026-05-03.json`
- `08. Audits/Workflow 16 Family Research Automation QA Audit - 2026-05-03.md`
