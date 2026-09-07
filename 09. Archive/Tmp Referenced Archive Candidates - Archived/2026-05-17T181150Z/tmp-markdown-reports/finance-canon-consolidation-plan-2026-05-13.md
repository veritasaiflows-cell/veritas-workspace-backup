# Finance Canon Consolidation Plan - 2026-05-13

## Goal
Reduce contradictory finance truth layers by consolidating four live canon notes into two compiled owner surfaces, then updating scripts, validators, dashboards, skills, and playbooks so old files no longer waste context or create drift.

## New canon model

| New owner surface | Replaces | Owns | Does not own |
|---|---|---|---|
| `03. Portfolio/Execution Board.md` | `03. Portfolio/Technical Entry and Invalidation Sheet.md` + `03. Portfolio/Deployment Trigger Sheet.md` | action state, execution band, stop/invalidation, technical posture, blocker, authority note, freshness/source stamp | thesis detail, portfolio weights, automatic execution authority |
| `04. Research/Coverage and Watchlist.md` | `02. Markets/Watchlist.md` + `04. Research/Coverage Universe.md` | research universe membership, thesis, tier, machine lane, key risk, act-when/promotion logic | deployment/action truth, exact bands/stops, portfolio weights |

Keep separate:
- `03. Portfolio/Portfolio Snapshot.md` - portfolio posture, draft weights, sleeve/concentration.
- `07. Risk/Risk Rules.md` - risk rules.
- `02. Markets/Macro Regime Dashboard.md` - macro regime.
- `05. Intelligence/Weekly Positioning Review.md` - weekly operating read.
- `06. Playbooks/Active Workflows.md` - workflow state, not portfolio truth.

## Phases

### Phase 0 - Reference map and design
Status: complete.
- Mapped hard-coded paths, parser contracts, tests, skills, playbooks, and generated artifact dependencies.
- Designed `Execution Board.md` and `Coverage and Watchlist.md` structures.

### Phase 1 - Compile new canon, preserve rollback
Status: complete / redirected early.
- Archive pre-consolidation copies under `09. Archive/Finance Canon/2026-05-13 pre-consolidation/`.
- Created compiled notes: `03. Portfolio/Execution Board.md` and `04. Research/Coverage and Watchlist.md`.
- Redirect stubs are already live for `03. Portfolio/Technical Entry and Invalidation Sheet.md` and `03. Portfolio/Deployment Trigger Sheet.md` after Randall approved the redirect strategy.
- Because redirects happened before every downstream consumer was patched, Phase 2 is now urgent.

### Phase 2 - Patch script/validator consumers
Patch highest-risk consumers first:
- `scripts/validate_canonical_ownership.py`
- `scripts/dashboard_core.py`
- `scripts/dashboard_validation.py`
- `scripts/board_canon_guardrail.py`
- `scripts/post_earnings_note_targets.py`
- `scripts/post_earnings_prep.py`
- `scripts/workbook_export.py`
- band/write helpers: `auto_apply_entry_band_maintenance.py`, `operators/band_note_sync.py`, `reference_band_note_sync.py`, `stale_intelligence_guardrail.py`, `operators/apply_band_update.py`
- proposal/status validators: `proposal_patch_scope_validator.py`, `canonical_status_invariant_validator.py`

### Phase 3 - Patch skills, playbooks, navigation
Update current operating docs and skills so startup and workflows read the two compiled files instead of the four old surfaces.
Do not bulk-edit historical workflow notes unless they are still presented as current operating docs.

### Phase 4 - Regenerate artifacts and prove parity
Regenerate or validate:
- dashboard payload / Command Center
- canonical ownership validation
- board/canon guardrail
- workbook exports
- post-earnings target/prep surfaces
- proposal validators
- dashboard validation

### Phase 5 - Redirect old files and archive noise
Only after scripts no longer parse old files:
- convert old notes to short redirect stubs
- leave archived full copies for rollback/history
- rerun `rg` to ensure old paths remain only in archives/history/redirects

## Known current trust issues to preserve, not hide
- `validate_canonical_ownership.py` now reports 0 critical / 0 warning after the first ownership-contract update.
- `validate_dashboard_state.py --write` currently reports usable-with-caution with ETN eligible auto-band apply debt and NVDA manual review/no-chase band debt.
- JPM contradiction is resolved in `Execution Board.md`: refreshed band/stop `294.57–308.54 / 286.81` is the live owner-approved framework; old stop-breach wording is archive-only history.

## Stop lines
- No trade/account action.
- No owner-approval inference.
- No sizing/sleeve/cash/risk-rule/execution-entitlement mutation.
- No destructive archive/delete until replacement surfaces and consumers validate.
- Generated `tmp/` artifacts remain proof/review surfaces, not canon.
