# Workflow 62 - Finance Canon Consolidation and Consumer Migration

## Objective
- Reduce contradictory finance truth layers by consolidating four live canon notes into two compiled owner surfaces, then migrate scripts, validators, dashboards, skills, and playbooks so old files no longer waste context or create drift.

## Current State
- **Implemented / monitoring.** The live consumer migration and active-folder redirect-stub retirement are complete enough to close WF62 as an active migration lane.
- Canonical owner surfaces are now:
  - `03. Portfolio/Execution Board.md` — action state, execution bands, stops/invalidation, blockers, technical posture, and deployment-state interpretation.
  - `04. Research/Coverage and Watchlist.md` — active universe, sector/tier, thesis, key risk, act-when/promotion logic, and research/watch context.
- Old full notes are archived under `09. Archive/Finance Canon/2026-05-13 pre-consolidation/`.
- Retired redirect stubs are archived outside active canon folders under:
  - `09. Archive/Finance Canon/2026-05-13 retired redirects/`

## Last Meaningful Progress
- Patched dashboard/guardrail consumers and added `scripts/test_dashboard_canon_surfaces.py`.
- Patched band/write helper, stale guardrail, post-earnings, workbook, proposal/status, workspace index, and governance consumers to the new two-surface model.
- Patched current docs, dashboards, skills, and navigation references; historical/archive continuity was intentionally not bulk-rewritten.
- Fixed `scripts/validate_canonical_ownership.py` and `scripts/test_canonical_ownership.py` to accept the current `Source lineage` Coverage/Watchlist header and to validate archived legacy originals / retired stubs instead of requiring old live redirect files.
- Preserved authority boundaries: no trade/account action, no owner-approval inference, no ungated sizing/sleeve/sector-posture mutation, and no cash/risk-rule/execution-entitlement mutation.

## Proof
- `python -m py_compile` passed for touched / nearest WF62 scripts.
- `python scripts\test_dashboard_canon_surfaces.py` passed.
- `python scripts\test_board_canon_guardrail.py` passed.
- `python scripts\test_auto_apply_entry_band_maintenance.py` passed.
- `python scripts\test_reference_band_note_sync.py` passed.
- `python scripts\test_stale_intelligence_guardrail.py` passed.
- `python scripts\test_canonical_ownership.py` passed.
- `python scripts\validate_canonical_ownership.py` returned `status=ok`, `0 critical / 0 warning`, `tracked_or_banded_tickers=23`.
- `python scripts\board_canon_guardrail.py --write` returned `0 critical / 5 warning`.
- `python scripts\generate_dashboard.py` and `python scripts\validate_dashboard_state.py --write` returned dashboard integrity `0 critical / 1 warning`.
- `python scripts\workbook_export.py` completed and refreshed workbook CSVs / manifest.
- `python scripts\post_earnings_prep.py` and `python scripts\post_earnings_note_targets.py` completed; no in-window packets currently.
- `python scripts\proposal_patch_scope_validator.py` returned `0 critical / 0 warning`.
- `python scripts\canonical_status_invariant_validator.py` returned `0 critical / 0 warning`.
- `python scripts\veritas_technical_pass_validate.py --write` returned `status=ok`.
- `python scripts\workspace_index.py` regenerated retrieval/cache index successfully.

## Remaining Residue / Trust Gaps
- Dashboard remains **usable-with-caution**, not clean-green, because NVDA is correctly earnings-frozen / no-chase and non-applyable. This belongs to WF58, not WF62 routing.
- `tmp/band-note-sync.json` reports `needs_sync=0` after bounded band/status sync for AMZN, RTX, PLTR, AMD, BKNG and NVDA review.
- Independent QC found and main session repaired two live-reference residues after stub retirement: `Home.md` navigation and `tmp/portfolio-config.json.manual_review_fields.source_of_truth` now point to the consolidated canon.
- `board_canon_guardrail` still reports warning-grade stop visibility: BKNG/LMT/LNG/PLTR below-stop and RTX near-stop. No critical canon contradiction.
- `scripts\workspace_governance_truth_check.py` is clean except the WF40 info item after Telegram removal.
- Old references remain in archive/history/project-continuity notes and one historical dated dashboard note by design.

## Next Action
- Keep WF62 in implemented/monitoring only.
- Continue WF58 for dashboard freshness / NVDA no-chase warning and normal band proof monitoring.
- If future work touches historical continuity notes, update stale old-canon references opportunistically, not as a broad rewrite.

## Key Files
- `03. Portfolio/Execution Board.md` — canonical execution/action/technical surface.
- `04. Research/Coverage and Watchlist.md` — canonical universe/thesis/watchlist surface.
- `tmp/canonical-ownership-validation.json` — ownership validator proof.
- `tmp/dashboard-validation.json` — dashboard proof / residual warning.
- `tmp/board-canon-guardrail.json` and `.md` — board/canon guardrail proof.
- `tmp/band-note-sync.json` and `.md` — band parity proof, currently `needs_sync=0`.
- `09. Archive/Finance Canon/2026-05-13 retired redirects/` — retired stubs moved out of active canon folders.

## Stop Lines
- No trade/account action.
- No owner-approval inference.
- No sizing/sleeve/cash/risk-rule/execution-entitlement mutation.
- Generated `tmp/` artifacts remain proof/review surfaces, not canon.
- Do not delete historical archives, retired stubs, or backups without explicit approval after reference checks.
