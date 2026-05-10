# Workspace Hygiene Follow-up Audit - 2026-05-05

## Verdict
Workspace organization is healthy overall. I did not find a reopening of the WF34 folder-boundary fixes or the WF35 truth-surface guardrails. Root discipline is mostly holding, `tmp/` has not regressed into a tooling surface, and the current validators still pass.

## Evidence checked
- `python scripts\workspace_boundary_check.py` -> `status: ok`
- `python scripts\dashboard_truth_lint.py` -> `status: ok`
- root folder/file classification
- empty-folder scan
- targeted checks for `tmp/*.py`, stray backup files, HTML outside governed surfaces, and generated artifacts outside `tmp/`

## Top findings
1. **No meaningful boundary regression is visible.**
   - No Python helper scripts have reappeared under `tmp/`.
   - No new stray `.bak`/timestamped backup debris showed up outside `migration-backups/` or archive.
   - The only non-archived HTML outside `tmp/` is `scripts/dashboard-template.html`, which is a durable implementation asset rather than generated output.

2. **Root-exception documentation is slightly behind the lived state.**
   - `attachments/` still exists at root and is currently empty, but `.obsidian/app.json` still points `attachmentFolderPath` there, so deleting it would be premature.
   - `migration-review.md` still lives at root and WF34 explicitly retained it as a root exception.
   - Neither `attachments/` nor `migration-review.md` is currently documented in `06. Playbooks/Workspace Structure Protocol.md` or `skills/workspace-governor/references/workspace-standards.md`, so policy text is lagging the approved runtime state.

3. **A few empty scaffolds remain, but they are minor hygiene residue rather than active drift.**
   - Empty dated backup folders: `migration-backups/2026-04-29-2029/`, `2026-04-29-2035/`, `2026-04-29-2046/`
   - Empty archive leaf: `09. Archive/temp-skill-inspect - Archived/macro-monitor/`
   - Empty skill reference folders: `skills/automation-hardening-manager/references/`, `skills/technical-chart-pass/references/`
   - These do not currently create truth or ownership confusion, but they are the clearest remaining cleanup candidates.

## Immediate low-risk fix worth doing later
Update the structure-policy notes to explicitly record the currently approved root exceptions (`attachments/` while Obsidian still targets it, and `migration-review.md` while it still has retrieval value). That is lower risk and higher clarity than moving or deleting either surface right now.

## Suggested next bounded cleanup pass
Run a small **root-exception and empty-scaffold cleanup pass**:
- document the approved root exceptions in the governing protocol/standards
- once backup retention is no longer a concern, remove truly empty `migration-backups/` leaves and the empty archived `macro-monitor/` folder
- leave canonical finance notes and truth-owner notes untouched
