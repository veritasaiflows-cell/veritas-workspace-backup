# WF62 Cleanup / Archive Plan — Finance Canon Noise Reduction

Generated: 2026-05-13 MST

## Goal
- Keep new sessions from treating retired finance notes as active canon.
- Preserve rollback/history, but remove old live-canon surfaces from the day-to-day read path.
- Status: Tier 1 redirect-stub retirement completed 2026-05-13 after Randall approval; no deletions performed.

## Current canon to keep active
- `03. Portfolio/Execution Board.md` — execution/action state, bands, stops, repair/watch/deployability, technical posture.
- `04. Research/Coverage and Watchlist.md` — research universe, coverage tier, thesis, key risk, act-when/promotion logic.
- `03. Portfolio/Portfolio Snapshot.md` — portfolio posture/allocation-level truth.
- `07. Risk/Risk Rules.md` — risk doctrine.

## Already archived rollback set
Keep as historical rollback only:
- `09. Archive/Finance Canon/2026-05-13 pre-consolidation/Watchlist.md`
- `09. Archive/Finance Canon/2026-05-13 pre-consolidation/Coverage Universe.md`
- `09. Archive/Finance Canon/2026-05-13 pre-consolidation/Technical Entry and Invalidation Sheet.md`
- `09. Archive/Finance Canon/2026-05-13 pre-consolidation/Deployment Trigger Sheet.md`

## Cleanup candidates

### Tier 1 — Active-folder redirect stubs causing context noise — Completed
Moved these stubs out of active folders into `09. Archive/Finance Canon/2026-05-13 retired redirects/`:

- `02. Markets/Watchlist.md`
- `04. Research/Coverage Universe.md`
- `03. Portfolio/Technical Entry and Invalidation Sheet.md`
- `03. Portfolio/Deployment Trigger Sheet.md`

Completed safeguards:
1. Patched `scripts/validate_canonical_ownership.py` so it no longer requires live redirect stubs; it verifies active canon, archived originals, retired stubs, and absence of retired live paths.
2. Ran `rg` to confirm no current live consumer still imports those paths.
3. Repaired independent QC findings: `Home.md` navigation and `tmp/portfolio-config.json.manual_review_fields.source_of_truth` no longer point at retired active paths.
4. Ran proof gates:
   - `python scripts\validate_canonical_ownership.py`
   - `python scripts\generate_dashboard.py`
   - `python scripts\validate_dashboard_state.py --write`
   - `python scripts\board_canon_guardrail.py --write`
   - `python scripts\workbook_export.py`

### Tier 2 — Current docs / skills that still mention retired names as history
Recommended action: do not bulk-edit old project-history notes. Add one top-level warning banner only to any still-current procedure that references retired notes as active owner surfaces.

Current scan shows stale references mostly in:
- historical `06. Playbooks/WF*.md` notes
- `06. Playbooks/Project Continuity/*` history notes
- dated dashboard notes

Leave these in place unless they are still used as startup/current operating docs.

### Tier 3 — Generated tmp artifacts
Recommended action: keep fresh proof artifacts; archive or regenerate stale communication artifacts only after current validators pass.

Keep current proof artifacts:
- `tmp/canonical-ownership-validation.json`
- `tmp/dashboard-validation.json`
- `tmp/board-canon-guardrail.json` / `.md`
- `tmp/band-note-sync.json` / `.md`
- `tmp/auto-band-apply.json` / `.md`
- `tmp/workbook-*.csv` and `tmp/workbook-export-manifest.json`

Candidate stale/noisy artifacts to inspect before archive:
- `tmp/full-portfolio-view.md` / `.json` / `.html` if still stale relative to Execution Board and Coverage+Watchlist.
- old one-off `tmp/*finance-canon*` planning artifacts after WF62 is fully stable.

### Tier 4 — Backup folders
Recommended action: preserve for now; propose later cleanup only after a commit/checkpoint or separate owner approval.

- `.backups/WF62/*`
- `.backups/WF58-band-sync/*`
- `~/.openclaw/backups/openclaw-WF62-telegram-remove-*.json`

These are safety backups from live config/canon edits. They should not be deleted in the same pass that created them.

## Remaining proposed cleanup order
1. Leave historical references alone unless a current operating doc still treats retired notes as active canon.
2. Inspect `tmp/full-portfolio-view.md` / `.json` / `.html` separately if they are stale relative to Execution Board and Coverage+Watchlist.
3. Only after a separate approval, archive stale tmp communication artifacts and older backup folders.

## Stop lines
- No deletion without explicit approval.
- No movement of backups in the same pass that depends on them.
- No portfolio mutation, trade/account action, owner-approval inference, sizing/sleeve/cash/risk-rule/execution-entitlement change.
- Generated artifacts stay proof/review surfaces, not canon.
