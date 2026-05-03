# Workflow 16B - Canonical Freshness Sync and Gated Note Update Helpers

## Objective
- Keep canonical notes fresh without allowing scheduled automation to rewrite judgment-heavy content unsafely.
- Define the canonical freshness patch contract, owner-surface map, and bounded pilot.
- Prove proposal-only freshness work without enabling auto-apply in v1.

## Current State
- **Complete** on 2026-05-03.
- The freshness patch contract is approved.
- Owner-boundary rules are explicit.
- The bounded pilot completed with manual approval only.
- Automation-driven canonical mutation remains fail-closed.

## Last Meaningful Progress
- Converted this note to the full major-workflow contract skeleton before closeout.
- Approved the canonical freshness patch contract.
- Built bounded pilot evidence under `tmp/research-automation/`.
- Applied two low-risk mirror-surface freshness patches manually after review.
- Preserved no-auto-apply guardrails.

## Scope
- canonical freshness patch contract
- owner-surface map
- approval / rollback rules
- bounded pilot on the named high-signal set
- proof that v1 remains patch-proposal only by automation

## Out of Scope
- autonomous canonical note mutation
- thesis rewrites
- deployment-state promotion/demotion
- portfolio weight changes
- cross-surface truth arbitration by helper lanes
- recurring scheduled auto-apply behavior

## Preflight / Entry Checklist
- [x] Workflow 16A contracts were complete before this workflow advanced.
- [x] Packet/routing semantics were explicit enough to interpret pilot cases honestly.
- [x] The lane remained bounded to freshness classification, patch proposals, manual review, and QA.
- [x] No auto-apply behavior was enabled.
- [x] Candidate owner surfaces were explicit.
- [x] Manual-only surfaces remained explicit.
- [x] Rollback expectation remained explicit.
- [x] Pilot scope stayed narrow.

## Execution Posture
- **main-session controlled**
- helper lanes allowed only for bounded read-only review or distinct-output draft prep
- canonical mutation by helpers remained **blocked / operator-gated**

## Owner Layer
- freshness doctrine -> `06. Playbooks/Research Automation Canonical Freshness Patch Contract.md`
- pilot packet evidence -> `tmp/research-automation/freshness-pilot-2026-05-03.json`
- mirror-surface manual freshness applies -> direct main-session edits after review
- canonical owner notes -> still human-approved only

## Review Window
- same-session contract closeout and bounded pilot for this pass
- intended downstream freshness checks after approved finance refresh windows only
- no scheduled auto-apply behavior enabled here

## Stop Lines
Stop immediately when:
- a candidate behaves like a new thesis or deployment decision
- a helper output starts acting like a second truth layer
- owner-surface authority is ambiguous
- source quality is too weak for the proposed patch
- freshness wording would mask a real posture change
- the patch would require cross-surface truth arbitration beyond narrow freshness alignment

## Surface / Handoff Posture
- patch packets -> proposal-only surfaces
- dashboard / weekly / event-calendar mirror surfaces -> eligible for low-risk manual freshness applies after review
- Trigger Sheet / Portfolio Snapshot / Technical Sheet / Macro Dashboard -> evidence inputs and manual-only targets in v1

## Canonical Mutation Posture
- **automation:** disallowed in v1
- **manual main-session approval:** required for any apply
- **auto-apply:** not allowed
- **thesis/posture mutation under freshness wording:** not allowed

## Acceptance Gates
Workflow 16B closes honestly only if all are true:
1. `06. Playbooks/Research Automation Canonical Freshness Patch Contract.md` exists and defines freshness classes, patch fields, owner map, and rollback rules.
2. `tmp/research-automation/freshness-pilot-2026-05-03.json` exists and records bounded pilot outcomes.
3. At least one pilot case results in an exact patch proposal, and any applied change required manual main-session approval.
4. At least one pilot case results in a `held_no_patch` or equivalent stop/hold outcome, proving the system can refuse false certainty.
5. No workflow language or artifact implies automation-level canonical mutation approval.
6. A bounded QA audit names residue and reopen triggers honestly.

## Exit / Closeout Checklist
- [x] Freshness patch contract approved.
- [x] Owner map explicit.
- [x] Rollback rule explicit.
- [x] Bounded pilot completed.
- [x] Manual review/apply path proved on low-risk mirror-surface changes only.
- [x] No-auto-apply guard preserved.
- [ ] Checkpoint posture finalized.

## Checkpoint Decision
- **pending final checkpoint action during same-session closeout**

## Next Pass
- None inside Workflow 16B scope.
- Reopen only if Randall intentionally asks for recurring research packets, gated mechanical helpers, or broader freshness automation.

## Next 1-2 Adjacent Candidate Workflows
1. `Workflow 19 - Playbooks Retrieval and Governance Cleanup`
2. Future reopen for a separately approved schedule/helper widening pass only

## Key Files
- `06. Playbooks/Research Automation Canonical Freshness Patch Contract.md`
- `tmp/research-automation/freshness-pilot-2026-05-03.json`
- `01. Dashboards/This Week.md`
- `08. Audits/Workflow 16 Family Research Automation QA Audit - 2026-05-03.md`
