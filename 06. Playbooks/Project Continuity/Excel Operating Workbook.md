# Excel Operating Workbook

## Objective
- Build a thin but genuinely useful Excel operating surface for Veritas.
- Keep notes canonical, scripts as evidence generators, Excel as the operator control layer.

## Current State
- First live workbook exists at `06. Playbooks/Workbooks/Veritas Operating Workbook.xlsx`.
- MVP tabs are live: Control Panel, Watchlist Operating Board, Deployment Ranking, Earnings Workflow Tracker, and Entry Bands and Technical Drift.
- Workbook is now beyond a bare export shell: conditional formatting, summary blocks, legend, and basic typed date/number formatting are in place.
- Claude's 2026-05-02 audit exposed the real packaging risk: the `.xlsx` artifact could lag the command-center / CSV layer because `scripts/workbook_template.py` sat outside the normal finance chain.
- Workflow 5 pass 2 partially closed that gap: manual workbook packaging now validates manifest freshness/checksums before rebuild, writes `tmp/workbook-build-validation.json`, and the workbook was rebuilt successfully against fresh exports during QC.
- Practical truth now: the workbook surface is more honest and recoverable, but it can still drift behind the command center whenever the operator skips the manual `--build-workbook` tail.
- The coverage-gap pass has now made the row contract explicit: `Watchlist Operating Board` carries all **21** tracked names, `Entry Bands and Technical Drift` carries the **17** technical-entitled names, and `Deployment Ranking` stays the **13**-name execution subset.
- This note is now an adjacent workbook workstream note, not the queue-owned continuity note for Workflow 5. The broader packaging/governance decision lives in `06. Playbooks/Project Continuity/Workflow 5 - PDF Excel Workflow Fit Pass.md`.

## Last Meaningful Progress
- `scripts/workbook_template.py` was built and then polished in two passes.
- The workbook now rebuilds successfully from the CSV export layer and remains aligned to the workbook schema notes.
- Dry run of `project-continuity-manager` on this project showed one useful gap: continuity notes for workflow-heavy projects need a small automation/refresh-path section. Skill updated accordingly.
- Dry run of `apply_band_update.py --dry-run` showed the approval path is workable, but exposed a real date-integrity flaw: band updates were being stamped with current UTC date instead of the proposal/trading data date. `scripts/apply_band_update.py` was corrected so Arizona-session note sync will not drift a day ahead.
- Claude's 2026-05-02 audit made the next real gap explicit: workbook export and workbook packaging are still split, so the Sunday chain refreshed the CSV layer but left the `.xlsx` stale.
- Pass 2 hardening landed: `workbook_export.py` now writes source-freshness plus per-export checksum metadata into the export manifest, and `workbook_template.py` now validates that manifest before rebuilding the `.xlsx`.
- Workbook packaging now emits `tmp/workbook-build-validation.json` and shows package age / warning-grade status in the control panel banner, so manual packaging is more honest about stale or degraded inputs.

## Outstanding
- Fix the current truth-sync failure by rebuilding the workbook after same-day finance-chain runs until the chain is patched.
- Keep workbook packaging out of the default scheduled chain for now, but preserve a one-command operator parity path with `run_finance_refresh_chain.py <window> --build-workbook` so the workbook is not left behind the CSV layer when staging parity matters.
- Main-session QC the new segmented workbook contract (`21` tracked / `17` technical-entitled / `13` execution-board) and keep the GS in-band/WATCH conflict explicit until the broader trust stack resolves it.
- Improve workbook polish without drifting into decorative dashboard theater.
- Tighten column-specific formatting and layout in the workbook.
- Start automating entry-band upkeep so the technical drift surface stays fresh with less manual overhead.
- Consider future chart/graph additions for visuals, but only after the operating workflow is stable.

## Blockers / Trust Gaps
- Workbook generation is still outside the default chain, which means the Excel surface can still drift behind the command center if the operator skips the manual packaging tail.
- Entry-band automation is only partially automated today.
- `band_refresh.py` proposes levels and `apply_band_update.py` can apply approved proposals to `tmp/portfolio-config.json`, but canonical note-layer updates to `03. Portfolio/Technical Entry and Invalidation Sheet.md` are still human-gated.
- Claude's audit found 17 of 21 tracked entry bands stale, which means the workbook's technical drift tab is surfacing a real degraded operating state, not cosmetic noise.
- Current dry-run review surface shows 6 names flagged for proposal review: ETN, GOOG, AMZN, VRT, RTX, and CAT.
- That boundary is correct for now. Fully automatic note-layer band rewrites would be too aggressive unless trust quality improves.

## Next Action
- Use `python scripts/run_finance_refresh_chain.py <window> --build-workbook` whenever workbook parity matters; default scheduled chains should still stop at `workbook_export.py`.
- Keep the first Workflow 5 packaging fixes in place: explicit `--build-workbook` for the manual tail, plus manifest row-count/checksum validation and the visible package-age / warning-status banner.
- Keep using the new segmented workbook contract (`21` tracked / `17` technical-entitled / `13` execution-board), then address the missing technical-note sections / parity gaps for `CVX`, `PLTR`, `AMD`, and `LNG`.
- Keep the workbook lane as an adjacent implementation/workstream note while Workflow 5 later decides the broader PDF/Excel workflow-fit and scheduling posture.
- Build the entry-band freshness workflow around the existing chain: keep proposal generation automatic, keep application human-gated, and make the post-application note-sync path cleaner and easier to resume.

## Key Files
- `scripts/workbook_template.py` - workbook generator for the `.xlsx` artifact.
- `scripts/workbook_export.py` - normalized CSV export layer feeding the workbook.
- `06. Playbooks/Excel Operating Workbook Structure.md` - broader workbook architecture and intent.
- `06. Playbooks/Minimum-Viable Workbook Schema.md` - implementation-grade workbook scope and field rules.
- `03. Portfolio/Technical Entry and Invalidation Sheet.md` - canonical note layer for entry bands and stops.
- `scripts/technical_refresh.py` - daily technical data and MA posture refresh.
- `scripts/band_refresh.py` - stale-band detector and proposal generator.
- `scripts/apply_band_update.py` - human-gated band proposal applier.
- `scripts/band_note_sync.py` - exact note-sync checklist generator for canonical band/stop lines.
- `scripts/entry_band_fetch.py` - per-ticker entry-band chart/report generator.
- `scripts/generate_entry_band_status.py` - universe entry-band status surface.
- `scripts/run_finance_refresh_chain.py` - live orchestration windows already wiring most band-freshness steps.

## Automation / Refresh Path
- Current chain already includes the core freshness path in `morning`, `post-close`, and `sunday` windows:
  - `technical_refresh.py`
  - `band_refresh.py`
  - `entry_band_fetch.py --all-tracked --html`
  - `generate_entry_band_status.py`
  - downstream `deployment_check.py` and `trigger_sheet_refresh.py`
  - `workbook_export.py`
- Current break: the chain stops at CSV export and does **not** yet rebuild the `.xlsx` workbook, so workbook truth is not guaranteed even when the command center is fresh.
- Correct near-term operating model under the degraded Workflow 5 contract:
  1. run the normal refresh chain with `--build-workbook` when workbook parity matters
  2. otherwise let the default chain stop at `workbook_export.py` so scheduled workbook packaging remains fail-closed
  3. inspect `tmp/band-proposals.json` and `tmp/entry-band-status.html`
  4. use `apply_band_update.py --dry-run` or targeted ticker approval when needed
  5. run `band_note_sync.py` to generate the exact canonical note-sync checklist
  6. update `03. Portfolio/Technical Entry and Invalidation Sheet.md` from ``tmp/band-note-sync.json`` and `tmp/band-update-log.txt`
  7. rerun downstream technical/deployment validation if band changes were applied
- The structured note-sync helper now exists. The next safe upgrade is to add the workbook build to the chain plus manifest verification — not silent autonomous band rewrites.
