# Workspace Governor Audit - 2026-05-08

## Verdict
Workspace organization is mostly healthy, but the boundary validator no longer returns clean. Two real drift classes need a bounded cleanup pass: an undocumented root `backups/` folder and six executable helper scripts living under `tmp/`.

## Validator proof
- `python scripts\workspace_boundary_check.py` -> `status: warning` with 11 findings: 7 warnings and 4 informational findings.
- `python scripts\dashboard_truth_lint.py` -> `status: ok` with 0 findings.

## Main findings
1. `backups/` exists at root with `startup-hardening-20260506-230017/` containing core-file `.bak` copies. Current policy allows `migration-backups/`, not a separate root `backups/` surface. This needs owner/workflow confirmation before move/archive/removal.
2. `tmp/` again contains executable Python helpers: `dump_bands.py`, `find_band_refs.py`, `find_disallowed_model_refs.py`, `find_disallowed_openclaw_refs.py`, `find_model_refs.py`, and `market_close_quick.py`. Under current standards, durable tooling belongs in `scripts/`; one-off helpers belong in archive, not active generated-artifact storage.
3. Previously lagging root-exception policy has been corrected: `attachments/` is documented and still justified by `.obsidian/app.json` using `attachmentFolderPath: "attachments"`; `migration-review.md` is documented while it retains review/retrieval value.
4. Generated artifact placement is otherwise coherent: entry-band reports remain under `tmp/entry-band-reports/`, active machine outputs remain under `tmp/`, and dashboard truth lint found no dashboard/canon boundary violations.
5. Minor empty scaffolds remain from the prior hygiene audit: empty dated `migration-backups/` leaves, empty archived `macro-monitor/`, and empty skill `references/` folders. These are cleanup candidates, not current truth-boundary blockers.

## Next bounded cleanup pass
Run a no-destructive **root-backup and tmp-helper classification pass**:
- classify `backups/startup-hardening-20260506-230017/` against `migration-backups/` retention policy and move/archive only with the proper workflow/owner approval if still needed;
- classify the six `tmp/*.py` helpers as durable scripts vs one-off probes, then move to `scripts/` or archive accordingly;
- optionally remove empty scaffold folders only after confirming no active workflow references them.

## Stop lines preserved
- No destructive cleanup performed.
- No canonical finance notes edited.
- No config/auth/network changes.
- No broad reorganization performed.
