# Workflow 33 - Declarative Finance Chain and Dependency Map Hardening

## Objective
- Move the finance refresh chain away from a long hard-coded step map toward an explicit, inspectable dependency manifest.
- Make window ownership, ordering, optional tails, and artifact expectations easier to audit without reading one large Python file.

## Current State (updated 2026-05-06)
- **WF33 closed:** the remaining four failure modes are resolved and proved.
- `scripts/weekly_review_skeleton.py` now uses canonical action-state classification; `DEPLOYABLE NOW` no longer falls through to the almost-deployable bucket.
- `scripts/validate_dashboard_state.py` now writes `generated_at_utc` plus `stale_after_hours`, and `scripts/deployment_readiness_surface.py` now surfaces validation freshness and degrades macro-gate posture when validation is stale.
- `scripts/pipeline_state_consistency_check.py` now routes through `board_state_contract.canonical_action_state()` instead of re-implementing contradictory state buckets.
- `scripts/chain_manifest.py` now owns declarative window/step definitions, expected outputs, dependency claims, and recovery posture; `scripts/run_finance_refresh_chain.py` now derives live and dry-run chain definitions from that manifest.
- Proof completed:
  - synthetic deployment-map proof shows `DEPLOYABLE NOW` lands in the correct weekly skeleton group
  - stale-validation simulation degraded `macro_gate` and surfaced `validation_staleness_warning`
  - `python scripts\test_dashboard_acceptance.py` -> **17 / 17 passed**
  - `python scripts\run_finance_refresh_chain.py post-close` -> completed successfully with `status: ok`, `stop_line: false`

## Scope
- define a declarative window/step manifest for the finance chain
- define required inputs, expected outputs, and failure posture by step
- preserve current live behavior while reducing hidden chain drift risk
- keep optional tails (`workbook`, `cleanup`, later packet steps) explicit instead of ad hoc

## Out of Scope
- changing market logic or deployment judgment rules
- widening cron autonomy
- replacing the existing chain runner before manifest parity is proved
- JSON surface normalization beyond what Workflow 32 owns

## Preflight / Entry Checklist
- [ ] current live chain order is pinned from `run_finance_refresh_chain.py`
- [ ] every target window has an owner description before refactor work starts
- [ ] fallback / recovery behavior is mapped before any runner split happens
- [ ] a compatibility path exists for current documented CLI usage

## Execution Posture
- `serial main-session`

## Phased completion approach

### Phase 1 - Chain inventory and manifest design
Purpose:
- define the exact manifest shape before moving live chain definitions

Required outputs:
- manifest schema for windows, steps, args, optional tails, and recovery posture
- explicit list of chain windows and their current owners
- no-go list for what must stay code-owned in v1

### Phase 2 - Parity extraction
Purpose:
- move current hard-coded windows into the manifest without changing behavior

Required outputs:
- manifest file(s) with morning / post-close / post-earnings / sunday parity
- runner support for loading the manifest
- dry-run parity proof versus the prior hard-coded order

### Phase 3 - Dependency and artifact guards
Purpose:
- make the manifest useful for audits instead of a blind script list

Required outputs:
- per-step expected artifact / dependency metadata
- optional-tail flags represented declaratively
- clearer operator visibility for why a step exists and what it feeds

### Phase 4 - Validation and closeout
Purpose:
- prove the manifest reduced hidden drift without weakening the fail-closed posture

Required outputs:
- direct dry-run / live-run proof on at least one weekday window
- updated docs naming the manifest as the chain-definition owner
- explicit residual debt list for anything still intentionally code-owned

## Stop Lines
- parity cannot be shown between the manifest and live chain order
- recovery/finalizer behavior becomes less explicit after refactor
- the pass drifts into broad automation widening instead of chain-definition hardening

## Acceptance Gates
- [x] chain windows are readable from one manifest surface instead of only embedded Python lists
- [x] existing CLI entrypoint remains intact or has a clearly documented compatibility wrapper
- [x] step order, optional tails, and recovery posture are explicit and testable
- [x] at least one live or dry-run parity proof exists

## Next Pass
- Hand forward to WF21 Phase 2 resume.
- Later follow-up may let cron/reporting consumers read manifest metadata directly, but that is widening work, not WF33 residue.

## Key Files
- `scripts/run_finance_refresh_chain.py`
- `scripts/README.md`
- `06. Playbooks/Automation Run Summary Contract.md`
- `06. Playbooks/Cron Run Ledger.md`
- `06. Playbooks/Project Continuity/Workflow 24 - Cron Job Build Contract and Session Handoff Hardening.md`
- `scripts/chain_manifest.py`
