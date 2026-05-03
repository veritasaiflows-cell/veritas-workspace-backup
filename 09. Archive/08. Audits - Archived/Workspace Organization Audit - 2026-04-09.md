# Workspace Organization Audit - 2026-04-09

## Verdict

The workspace is mostly coherent, but it will drift without an explicit governance rule set.

The current structure is acceptable. The main problems were:
- an empty `state/` folder had reappeared in root
- the root folder policy was not yet formalized, so future sprawl risk was high
- at least one special-purpose dated memory note needed review for proper placement

## Current root inventory

Core files in root:
- `AGENTS.md`
- `Continuity Protocol.md`
- `HEARTBEAT.md`
- `Home.md`
- `IDENTITY.md`
- `MEMORY.md`
- `SOUL.md`
- `TOOLS.md`
- `USER.md`

System folders in root:
- `.git/`
- `.obsidian/`
- `.openclaw/`
- `memory/`
- `templates/`

Current top-level domain folders:
- `07. Audits/`
- `01. Dashboards/`
- `04. Departments/`
- `03. Offers/`
- `02. Opportunities/`
- `05. Plans/`
- `06. Training Documents/`

Additional root folder previously needing action:
- `state/` (was empty and has now been removed)

## Recommended root folder policy

Allow only:
- core operating files
- essential system folders
- a small number of durable top-level domain folders

Approved durable top-level domain folders right now:
- `07. Audits/`
- `01. Dashboards/`
- `04. Departments/`
- `03. Offers/`
- `02. Opportunities/`
- `05. Plans/`
- `06. Training Documents/`

Do not create new top-level folders unless they represent a durable domain with repeated use.

## Recommended naming conventions

### Folders
- Use Title Case with spaces for human-facing knowledge folders
- Use lowercase for system/implementation folders like `memory`, `templates`, and `skills`
- Avoid duplicate patterns like `Training`, `TrainingDocs`, and `training-documents`

### Notes
- Use descriptive Title Case
- Prefer stable patterns like `<Topic>.md` or `<Topic> - <Subtype>.md`
- Use `YYYY-MM-DD.md` for daily notes
- Use dated special-purpose notes only when they are truly separate from the daily log
- Avoid vague names like `Misc.md`, `Ideas.md`, or `Notes.md`
- Avoid version clutter like `final-final` or uncontrolled `v2`, `v3`

## Cleanup checklist

1. Root sanity
- remove empty folders
- move misplaced notes out of root
- block accidental new top-level folders

2. Naming drift
- detect vague filenames
- detect duplicate categories or inconsistent capitalization
- standardize separators for related note sets

3. Folder fit
- keep audits in `07. Audits/`
- keep training material in `06. Training Documents/`
- keep plans in `05. Plans/`
- keep offer and opportunity material distinct unless there is a clear reason to combine them

4. Obsidian hygiene
- do not treat `.obsidian/workspace.json` as durable content
- avoid accidental nested vaults

5. Memory hygiene
- daily logs stay in `memory/YYYY-MM-DD.md`
- durable truths go to `MEMORY.md` or operating files
- avoid bloating long-term memory with raw logs

6. Loose ends
- review one-off diagnostic notes
- remove empty scaffolding
- either finalize or explicitly preserve draft notes with a reason

## Concrete next actions

Low-risk and obvious:
- remove `state/` because it is empty and violates the prior cleanup principle

Resolved:
- removed `memory/2026-04-10-heartbeat-config.md` because it was a transient control-session artifact, not durable memory
- removed `memory/heartbeat-state.json` because it carried no meaningful state

## Outcome

To prevent drift, a custom skill named `workspace-governor` was created and a weekly silent cron audit was added.

Low-risk cleanup completed:
- removed empty `state/`
- removed transient `memory/2026-04-10-heartbeat-config.md`
- removed unused `memory/heartbeat-state.json`
