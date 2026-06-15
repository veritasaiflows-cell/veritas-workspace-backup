# Workspace Index and Tmp Hardening Pass - 2026-05-25

## Retrieval Notes

- Status: completed with approval-gated residue
- Owner: Veritas main session / workspace-governor
- Scope: workspace retrieval index, artifact index, `tmp/` generated/staged files, live references to archived tmp Markdown
- Archive posture: no deletes or archive moves performed in this pass
- Authority: path/index hardening only; no finance canon/portfolio mutation, no owner approval inference, no trade/account/paper/live authority, no config/auth/channel mutation

## Actions completed

- Rebuilt `tmp/workspace-index.sqlite` after the archive/path changes.
- Refreshed `tmp/veritas-artifact-index.sqlite` with `artifact_index.py incremental`.
- Ran SQLite integrity/foreign-key checks and `PRAGMA optimize` on both workspace SQLite indexes.
- Retargeted missing live/durable text references from old `tmp/*.md` paths to their unique archived paths where the archived target was unambiguous.
- Preserved backups for retargeted files under `tmp\backups\20260525-182218-workspace-index-tmp-reference-retarget`.
- Generated machine proof: `tmp/workspace-index-tmp-hardening-pass-2026-05-25.json`, `tmp/workspace-index-tmp-reference-retarget-proposal-2026-05-25.json`, and `tmp/workspace-index-tmp-reference-retarget-apply-2026-05-25.json`.

## Proof summary

| Check | Result |
|---|---|
| `workspace_index.py` rebuild | ok |
| `artifact_index.py incremental` | ok |
| `artifact_index.py validate` | ok, 28/28 |
| `workspace_boundary_check.py` | ok, warnings 0 |
| `dashboard_truth_lint.py --write` | ok, warnings 0 |
| `bounded_auto_archive.py --validate-last-report` | ok |
| SQLite quick checks | ok for `tmp/veritas-artifact-index.sqlite` and `tmp/workspace-index.sqlite` |

## Tmp inventory snapshot

- Total `tmp/` files: 2156
- Total `tmp/` bytes: 80912458
- Zero-byte files: 617 ? mostly OTEL collector and compact-exec receipt/log files
- Large files over 5 MB: 1; largest/only material large file is `tmp/workspace-index.sqlite`
- Tmp Markdown suggestions: 101; active-reference Markdown: 94; zero-reference Markdown: 6

## Residue / approval-gated items

- Six zero-reference WF75 Markdown sidecars remain in `tmp/`; each has an adjacent JSON companion and is a low-risk archive candidate, but archive/move/delete remains approval-gated.
- Residual tmp reference candidates remain after unique archive retargeting. They are mostly historical/prose/prefix references; do not mass-edit them without manual classification.
- No `VACUUM` was run because DB integrity is clean, no bulk SQL delete occurred, and the databases are small/healthy.
