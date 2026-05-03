# Workflow 16A - Research Intake Desk and Parallel Review Packets

## Objective
- Stand up the review-first intake layer for company news, macro/policy shifts, geopolitical/energy developments, and thesis-drift detection.
- Define the three contracts that make research automation useful without turning it into a noisy second truth layer.
- Hand approved packet/routing contracts to Workflow 16B without opening recurring research cron early.

## Current State
- **Complete** on 2026-05-03.
- Source bundle, intake packet, and routing / promotion contracts are approved.
- Sample route / no-route packets exist.
- Canonical mutation remains out of scope and was not opened here.

## Last Meaningful Progress
- Added the full preflight and major-workflow contract skeleton to this note before implementation.
- Approved the source bundle, intake packet, and routing/promotion artifacts.
- Wrote sample packets that show route, no-route, and stop-line outcomes.
- Passed the approved handoff packet to Workflow 16B.

## Scope
- Source Bundle Contract
- Intake Packet Contract
- Routing / Promotion Contract
- sample packet proof for route / no-route / stop-line behavior
- explicit owner boundaries and stop lines for the intake lane

## Out of Scope
- canonical note mutation
- recurring research cron enablement
- autonomous thesis maintenance
- portfolio-posture changes from packet output alone
- freeform helper-lane research swarming

## Preflight / Entry Checklist
- [x] Workflow 16 readiness gate was logged complete.
- [x] Governance baseline remained committed and stable enough to proceed.
- [x] `Major Workflow Contract Standard.md` and `Spawn and Closeout Governance Matrix.md` were treated as controlling references.
- [x] The lane remained contract-building and QA only.
- [x] No recurring research cron was enabled.
- [x] Canonical mutation remained default-no.
- [x] Owner boundaries remained explicit for dashboard, workbook, weekly brief, thesis-review queue, and canonical notes.
- [x] Helper output remained bounded and could not publish final truth.

## Execution Posture
- **main-session controlled**
- helper lanes allowed only as **spawn read-only** or **spawn distinct-output** for bounded contract challenge / QA
- no helper lane authority over queue movement, canonical mutation, or final verdicts

## Owner Layer
- source policy and routing doctrine -> playbook contracts under `06. Playbooks/`
- sample packet artifacts -> `tmp/research-automation/`
- routing surfaces -> dashboard watch, weekly intelligence, thesis-review queue, freshness-patch candidate only
- canonical notes -> not owned here

## Review Window
- same-session contract build and QA for this pass
- intended downstream packet windows after approval: premarket, post-close, Sunday, and later explicit event-driven manual review
- no recurring packet schedule enabled here

## Stop Lines
Stop instead of routing when:
- evidence is rumor-heavy or unattributed
- primary support is missing on a timing-critical claim
- duplicate/circular reporting is being mistaken for confirmation
- the packet would smuggle in a thesis or deployment judgment
- owner-surface contradiction cannot be resolved safely
- degraded macro/policy context makes the interpretation unsafe

## Surface / Handoff Posture
- dashboard / workbook / weekly brief -> review surfaces only
- thesis-review queue -> decision-intake surface only
- freshness patch candidate -> proposal-only handoff to WF16B
- canonical notes -> out of bounds here

## Canonical Mutation Posture
- **disallowed** in this workflow
- packet output may recommend `freshness_patch_candidate`
- packet output may not apply changes or imply approval

## Acceptance Gates
Workflow 16A closes honestly only if all are true:
1. `06. Playbooks/Research Automation Source Bundle Contract.md` exists and is explicit about tiers, blocked sources, cadence, cron boundaries, and stop lines.
2. `06. Playbooks/Research Automation Intake Packet Contract.md` exists and defines the packet schema, confidence/materiality scales, and stop lines.
3. `06. Playbooks/Research Automation Routing and Promotion Contract.md` exists and keeps routing distinct from truth mutation.
4. `tmp/research-automation/intake-packet-samples.json` exists and contains route, no-route, and stop-line examples.
5. Workflow 16B can consume the outputs without needing a second contract-definition pass just to understand what a packet means.
6. A bounded QA audit names remaining residue honestly.

## Exit / Closeout Checklist
- [x] All three contract artifacts created.
- [x] Sample packets created.
- [x] Route / no-route / stop-line behavior shown explicitly.
- [x] Owner boundaries kept fail-closed.
- [x] Canonical mutation remained out of scope.
- [x] Handoff to Workflow 16B made explicit.
- [ ] Checkpoint posture finalized.

## Checkpoint Decision
- **pending final checkpoint action during same-session closeout**

## Next Pass
- Workflow 16B consumes the approved packet/routing contracts and closes the freshness-patch contract plus bounded pilot.

## Next 1-2 Adjacent Candidate Workflows
1. `Workflow 16B - Canonical Freshness Sync and Gated Note Update Helpers`
2. Future reopen only if new source categories or routing surfaces are intentionally added

## Key Files
- `06. Playbooks/Research Automation Source Bundle Contract.md`
- `06. Playbooks/Research Automation Intake Packet Contract.md`
- `06. Playbooks/Research Automation Routing and Promotion Contract.md`
- `tmp/research-automation/intake-packet-samples.json`
- `08. Audits/Workflow 16 Family Research Automation QA Audit - 2026-05-03.md`
