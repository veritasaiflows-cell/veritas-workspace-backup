# Workflow 32 - Finance Surface Contract and JSON Spine Normalization

## Objective
- Normalize the finance surface contract so board state, render state, and JSON summaries stop drifting across scripts.
- Replace ad hoc duplicated state logic with a shared contract and explicit output metadata.

## Current State (CLOSED 2026-05-05)
- Five confirmed finance-pipeline discrepancies were verified and resolved. All acceptance gates met.
  - **WF32A** — `board_state_contract.py`: BENCH is now a first-class canonical state (not collapsed into DO NOT TOUCH). STATE_ORDER updated with BENCH at rank 5.
  - **WF32B** — `deployment_check.py` now emits canonical state strings (DEPLOYABLE NOW, ALMOST DEPLOYABLE, WATCH / RESEARCH NEEDED, etc.) aligned to board_state_contract. `dashboard_payload.py` `state_to_bucket` updated to accept canonical keys plus legacy short-form aliases. `trigger_ready` check also updated to accept canonical forms so `triggerToday` fires correctly.
  - **WF32C** — `premarket_snapshot.py` now calls `canonical_note_mutation_gate(validation)` — same trust-gate posture as `postmarket_snapshot.py` and `daily_executive_brief.py`. Summary JSON now includes `canonical_mutation_allowed`, `trust_reason`, `trust_gate_blocked`.
  - **WF32D** — `daily_executive_brief.py` now loads `deployment-check.json` in `main()`. Section 5 shows BENCH (chart-weak) and BELOW STOP names from the deployment-check layer. Summary JSON now includes `bench` and `below_stop` ticker lists plus `deploy_check_source`.
  - **WF32E** — `scripts/pipeline_state_consistency_check.py` is a new cross-surface contradiction detector. Reads trigger-sheet, deployment-check, daily-brief, and premarket-snapshot; reports contradictions. Wired into morning, post-close, and Sunday chains as the final tail step.
- Acceptance proof: `test_dashboard_acceptance.py` 17/17 passed. `pipeline_state_consistency_check.py` 0 contradictions.
- Bounded regeneration of `tmp/daily-executive-brief.json` and `tmp/premarket-snapshot.json` is deferred to the next morning chain run (no blocking residue).
- Remaining known debt (handed forward honestly):
  - output summaries do not carry explicit schema/version metadata yet (deferred to WF33 manifest pass)
  - note-write / canon-mutation semantics naming in some JSON outputs still varies (deferred)
  - the consistency validator is new and not yet battle-tested against live data — treat as v1 audit tool

## Scope
- shared action-state vocabulary and render filters
- shared active-board metadata for render surfaces
- explicit JSON contract/version metadata for the main finance surfaces
- separation between dashboard-surface write permission and broader finance-canon mutation posture
- lightweight contract validation for the main summary artifacts

## Out of Scope
- changing portfolio judgment rules
- widening autonomous note mutation
- broad chain-manifest / scheduler refactor (owned by Workflow 33)
- research-source packet widening (owned by Workflow 21 / Workflow 26)

## Preflight / Entry Checklist
- [ ] current board-state helper still matches the live trigger-sheet truth
- [ ] all target JSON outputs are listed before edits begin
- [ ] backward-compatibility risk is named before renaming any field
- [ ] consumer scripts are identified before deleting any legacy field

## Execution Posture
- `serial main-session`

## Phased completion approach

### Phase 1 - Contract inventory
Purpose:
- pin every live surface that emits board-state or summary JSON

Required outputs:
- inventory of emitting scripts and their output files
- field-level comparison table for duplicated semantics
- list of legacy fields that cannot be removed yet

### Phase 2 - Shared contract extraction
Purpose:
- move remaining duplicated state / filter / metadata logic behind shared helpers

Required outputs:
- shared helpers for state vocab, active-board metadata, and output-contract annotations
- render scripts updated to consume the shared helpers
- no behavior drift on the live board without explicit reason

### Phase 3 - Output normalization
Purpose:
- make the machine outputs coherent enough for downstream validation and later automation

Required outputs:
- explicit schema/version metadata on target JSON artifacts
- aligned field names for write-permission versus broader canon-mutation posture
- documented compatibility map for retained legacy fields

### Phase 4 - Validation and closeout
Purpose:
- prove the normalization pass improved truth instead of just renaming fields

Required outputs:
- direct regeneration proof on affected surfaces
- validator or audit output showing no unresolved contract ambiguity on in-scope files
- named residual debt handed forward honestly

## Stop Lines
- a field rename would break an active downstream consumer without a compatibility plan
- the pass starts changing judgment logic instead of contract logic
- the work drifts into scheduler/cron manifest design instead of output normalization

## Acceptance Gates
- in-scope surfaces share one action-state vocabulary
- active-board metadata is explicit instead of hidden in script internals
- JSON output semantics for write permission versus broader canon mutation are no longer ambiguous
- at least one lightweight proof/validator exists for the normalized contract

## Next Pass
- After Workflow 32 closes, open `Workflow 33 - Declarative Finance Chain and Dependency Map Hardening` unless a downstream consumer forces another contract pass first.

## Key Files
- `scripts/board_state_contract.py`
- `scripts/market_state_refresh.py`
- `scripts/premarket_snapshot.py`
- `scripts/postmarket_snapshot.py`
- `scripts/daily_executive_brief.py`
- `tmp/market-state.json`
- `tmp/premarket-snapshot.json`
- `tmp/postmarket-snapshot.json`
- `tmp/daily-executive-brief.json`
- `tmp/deployment-readiness-surface.json`
