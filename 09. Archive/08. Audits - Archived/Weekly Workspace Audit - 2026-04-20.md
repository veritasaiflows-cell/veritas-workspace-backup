# Weekly Workspace Audit - 2026-04-20

## Scope
- root folder policy
- naming consistency
- misplaced notes
- empty folders
- Obsidian hygiene
- memory hygiene
- loose ends

## Low-risk fixes made
- Removed empty root folder: `state/`
- Removed empty scaffold folder: `skills/technical-chart-pass/references/`

## Findings

### Root policy
- The workspace is internally consistent around the current finance-first root order:
  - `01. Dashboards/` through `09. Archive/`
- This no longer matches the older `workspace-governor` reference policy, which still names the prior consulting-era top-level folders.
- Extra root folders remain present: `scripts/`, `tmp/`, and `.clawhub/`.
  - `scripts/` appears intentional and active.
  - `tmp/` is currently being used as a transient output area.
  - `.clawhub/` appears tool-driven.

### Naming consistency
- Numbered finance folders are clean and consistently named.
- Root file naming is mostly stable.
- `FINANCE_SOUL.MD` is functionally fine, but its all-caps extension is a small naming inconsistency relative to the rest of the vault.

### Misplaced notes
- No obvious human-facing notes are stranded in root.
- Audit material is correctly under `08. Audits/`.
- Training/playbook-like material appears correctly grouped under `06. Playbooks/` in the current finance model.

### Empty folders
- Fixed the two obvious empty folders found during this audit.
- No other empty directories were detected after cleanup.

### Obsidian hygiene
- No obvious nested vault problem detected.
- `.obsidian/workspace.json` and `.obsidian/appearance.json` remain present as non-durable app state; that is normal, but they should stay treated as incidental rather than knowledge content.

### Memory hygiene
- Daily notes are using the expected `memory/YYYY-MM-DD.md` pattern.
- `MEMORY.md` is curated and not bloated with raw logs.
- One special-context note remains: `memory/2026-04-12 - Content Pivot.md`.
  - This may still be justified as a transition artifact, but it is now a candidate to merge into the main daily note or archive logic if it no longer serves navigation.

### Loose ends
- `tmp/` contains multiple generated artifacts and is the main remaining source of workspace clutter.
- The root-policy documentation used by the workspace-governor skill is out of sync with the actual finance-first vault structure.

## Recommendations
1. Update `skills/workspace-governor/references/workspace-standards.md` so the written canonical top-level policy matches the live finance-first root structure.
2. Decide whether `tmp/` is a permanent scratch zone.
   - If yes, explicitly bless it and add ignore guidance.
   - If no, prune it regularly or fold repeatable outputs into `scripts/` or a clearer state folder.
3. Decide whether `CLAUDE.md` and `FINANCE_SOUL.MD` should be treated as core operating files in the documented root policy.
4. Review whether `memory/2026-04-12 - Content Pivot.md` should remain separate, be merged, or be archived as a retired transition note.

## Bottom line
- The vault is in decent shape.
- The main drift is not chaos inside the finance structure.
- The main drift is that the written workspace-governor standard still reflects the older vault model, while the live workspace has already moved on.