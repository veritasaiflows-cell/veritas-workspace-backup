# Workflow 24 - Cron Job Build Contract and Session Handoff Hardening

## Objective
- Standardize how Veritas cron jobs are designed so each scheduled run gets an explicit, reusable execution packet instead of vague “do the normal thing” prompting.
- Make every non-trivial cron job say what to read first, what to execute, what to inspect after execution, how to respond, and when to spawn or stop.
- Improve speed, coherence, and honesty without widening autonomy.

## Why this lane exists
- Workflow 20 needs a real cron-backed review design, but the current cron doctrine was still too loose about run-packet structure.
- The morning finance-chain incident on 2026-05-04 proved that explicit runtime, proof, and response contracts matter more than inherited assumptions.
- Workflow 21 and later review-packet lanes should not open on top of a weak cron-build standard.

## Current State
- approved as an inserted enabling workflow on 2026-05-04
- closed with follow-up on 2026-05-04 after protocol hardening, sibling retrofit, direct proof, and closeout sync were completed
- no autonomy widening is approved here
- live target doctrine file: `06. Playbooks/Cron Job Protocol.md`
- the reusable retrofit artifact now exists: `06. Playbooks/Cron Job Retrofit Checklist.md`
- all three live finance sibling cron jobs now carry explicit run-packet payloads with read-first, execute-in-order, inspect-after, response-contract, out-of-bounds, and stop-line wording
- direct cron-history proof now exists for the retrofitted post-close sibling via `openclaw cron runs --id f2fd65c3-29b9-49d8-ab32-8e7ea347297e`
- Workflow 25 is now the active downstream lane

## Scope
- define the reusable cron-build packet fields
- define read-first and execute-in-order requirements
- define the response contract every non-trivial cron run should follow
- define spawn recommendation fields for isolated runs and child sessions
- define efficiency fields that reduce drift, context waste, and fake-green summaries
- create a retrofit checklist for existing finance sibling jobs

## Out of Scope
- adding broad new cron families by default
- autonomous canonical finance note mutation
- autonomous queue movement
- any silent widening of worker authority

## Sequential phase approach

### Phase 1 - Builder contract
- harden `06. Playbooks/Cron Job Protocol.md`
- make the required run-packet fields explicit
- add read-first / execute-in-order / response-contract / spawn-recommendation rules

### Phase 2 - Retrofit checklist
- define the checklist used to compare live sibling jobs against the new contract
- identify which jobs need prompt/handoff tightening first

Status:
- complete

### Phase 3 - Apply to live finance siblings
- review the current morning, post-close, and Sunday jobs against the contract
- tighten only what is actually missing

Status:
- complete
- prompt/handoff layer tightened on all three live siblings
- artifact proof is present for the retrofitted post-close path
- direct cron-history proof is present for the retrofitted post-close path
- remaining symmetry proof for morning and Sunday is preserved as named residue / reopen trigger, not fake-green closure evidence

### Phase 4 - Independent audit
- verify the new contract improves clarity without implying wider autonomy
- record reopen triggers and remaining residue

Status:
- complete
- audit artifact saved under `08. Audits/Workflow Executive Summaries/Workflow 24 - Cron Job Build Contract and Session Handoff Hardening/Independent Audit.md`

## Acceptance Gates
Workflow 24 should not close unless all are true:
1. the cron-builder packet fields are explicit in doctrine
2. the response contract is explicit enough to prevent vague “success” summaries
3. spawn recommendation fields are explicit enough to keep child runs bounded
4. a retrofit checklist exists for live sibling jobs
5. no new autonomy was smuggled in under “efficiency” wording

Result:
- met for closure at the intended scope

## Closure Label
- Closed with follow-up

## Acceptance Evidence
- `06. Playbooks/Cron Job Protocol.md` now requires explicit run-packet fields for non-trivial cron jobs
- `06. Playbooks/Cron Job Retrofit Checklist.md` exists and was used to retrofit the live finance siblings
- `openclaw cron list` shows all three finance siblings live and enabled under the hardened family
- `openclaw cron runs --id f2fd65c3-29b9-49d8-ab32-8e7ea347297e --limit 5 --expect-final --timeout 60000` returned a `finished` / `ok` entry for the retrofitted post-close proof run
- `tmp/run-summary-post-close.json` reports `status: ok`, `dashboard_validation_status: clean`, and `stop_line: false`
- independent audit artifact exists at `08. Audits/Workflow Executive Summaries/Workflow 24 - Cron Job Build Contract and Session Handoff Hardening/Independent Audit.md`

## Named Residue
- only the post-close sibling received direct history-visible proof in this pass
- direct forced runs for the morning and Sunday siblings hit a gateway scope-upgrade pairing requirement on this device
- cron delivery remains fail-closed / no-route by design for these internal jobs
- downstream finance trust caveats remain explicit and outside WF24 scope (`presentation_allowed: false`, `canonical_note_mutation_allowed: false`, partial post-earnings outputs, workbook freshness warning)

## Reopen Triggers
- any finance sibling cron job drifts away from the explicit run-packet structure
- a future cron summary drops trust-boundary or stop-line language
- direct history-visible proof later contradicts the claimed sibling symmetry
- queue, registry, continuity, chain-log, and audit surfaces drift out of agreement on WF24 state

## Next Action
- Promote Workflow 25 as the active downstream lane and build the research-department intake queue plus admission / promotion decision objects before reopening recurring research-source widening.

## Key Files
- `06. Playbooks/Cron Job Protocol.md`
- `06. Playbooks/Cron Job Retrofit Checklist.md`
- `06. Playbooks/Project Continuity/Workflow 24 - Cron Job Build Contract and Session Handoff Hardening - Chain Log.md`
- `06. Playbooks/Automation Orchestration Protocol.md`
- `06. Playbooks/Cron Run Ledger.md`
- `06. Playbooks/Automation Run Summary Contract.md`
- `06. Playbooks/Project Continuity/Workflow 20 - Parallel Agents Automation and Human-Gated Review Workflow.md`
