# Veritas Command Center & Excel Workbook - Security and Sync Audit - 2026-05-02

## Scope
- `tmp/veritas-command-center.html`
- workbook CSV export layer in `tmp/workbook-*.csv`
- `06. Playbooks/Workbooks/Veritas Operating Workbook.xlsx`
- chain/orchestration relationship between `scripts/run_finance_refresh_chain.py`, `scripts/workbook_export.py`, and `scripts/workbook_template.py`

## Executive Summary
- The most material integrity issue is a split between the live command-center / CSV layer and the Excel workbook layer.
- Command-center and workbook CSV artifacts were regenerated on 2026-05-01 around 18:17 local, but `Veritas Operating Workbook.xlsx` was last built on 2026-04-30 at 16:49 local.
- Practical result: the workbook missed the full Sunday chain output and is roughly 25+ hours stale relative to the command center.
- The workbook is therefore not a trustworthy operator surface unless it is rebuilt manually after the chain.

## Primary Finding
### Workbook desync from chain output
- `scripts/run_finance_refresh_chain.py` runs `scripts/workbook_export.py`, but not `scripts/workbook_template.py`.
- The CSV export layer refreshed; the `.xlsx` packaging layer did not.
- This left the workbook behind the current machine truth, including Sunday rebuild outputs and newer deployment warnings.

## Secondary Findings
- No 2026-05-02 morning chain run was present at audit time, so the command center itself was still on 2026-05-01 data despite BRK.B reporting on 2026-05-02.
- Universe coverage gap: control panel reports 21 tracked names while `workbook-watchlist-board.csv` carries 13 rows, leaving 8 tracked names outside the deployment/workbook surface.
- Entry-band freshness is degraded: 17 of 21 tracked names are stale and proposed updates have not been applied.
- GS has an in-band versus WATCH state conflict that the stale workbook does not surface.
- Coverage-tier drift remains for AMD, LNG, CVX, and PLTR, which are appearing in deployment flow without a clean daily-coverage fit.
- `workbook-export-manifest.json` carries a blank timestamp for `dashboard-validation.json`, so export-audit provenance is incomplete.

## Security / Integrity Read
### Working
- Atomic-write posture for JSON and CSV artifacts reduces partial-write risk.
- Validation and acceptance checks appear to be functioning before dashboard render.
- Last-good backup posture for the dashboard remains intact.

### Real integrity risks
- Workbook staleness is not visually obvious enough to the end user.
- Workbook rebuild trusts raw CSVs in `tmp/` without checksum verification against the export manifest.
- Manual policy-mode constants can drift indefinitely without a TTL warning.
- Band proposals and applied bands are both behind the current session, so entry decisions are degraded.
- The `tmp/` layer remains plaintext local data; acceptable only if the machine posture stays private.

## Immediate Recommendations
### Today
1. Run `python scripts/run_finance_refresh_chain.py morning`.
2. Run `python scripts/workbook_template.py` immediately after so the workbook matches the current CSV layer.
3. Confirm BRK.B earnings timing directly from Berkshire materials before treating the catalyst date as trusted.

### This week
1. Add `scripts/workbook_template.py` to the tail of each `WINDOW_CHAINS` path after `scripts/workbook_export.py`.
2. Review and apply the pending band updates through `scripts/apply_band_update.py`.
3. Resolve the GS state conflict and coverage-tier drift for AMD, LNG, CVX, and PLTR.
4. Fix the manifest source-timestamp bug in `scripts/workbook_export.py`.

### Next structural pass
- Add a visible workbook staleness warning driven by export age.
- Add manifest/checksum validation in `scripts/workbook_template.py` before building the workbook.
- Add TTL warnings for manual policy constants.

## Bottom Line
- The architecture is mostly sound.
- The acute failures are operational truth-sync failures, not a collapsed system design.
- Until the workbook is rebuilt in-chain and the stale-band backlog is reviewed, the Excel operator surface is materially less trustworthy than the command center.