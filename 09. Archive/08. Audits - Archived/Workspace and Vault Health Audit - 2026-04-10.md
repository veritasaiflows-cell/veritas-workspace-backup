# Workspace and Vault Health Audit - 2026-04-10

## Bottom line

The workspace is structurally healthy, but there were still three real drift points:
- `state/` reappeared as an empty root folder
- machine-state files were showing up as untracked workspace noise
- older readiness notes had become stale enough to misstate current reality

## What was verified

- Root review order and numbered top-level folders remain intact
- Obsidian desktop is pointed at the workspace root, not `.obsidian/`
- `.obsidian/workspace.json` and `.obsidian/appearance.json` are already ignored
- Last commit was `2026-04-07 20:57 -0700`, so normal commit batching is now old enough if a checkpoint is wanted

## Readiness truth after recheck

- `clawhub` is callable and logged in
- `obsidian` is callable and the vault target is correct
- `gh`, `rg`, and `jq` are not callable from the current shell, so prior install claims should not be treated as operational truth here
- Obsidian API-driven usage is still gated by missing `OBSIDIAN_API_KEY`

## Cleanup applied

- removed stale `memory/heartbeat-state.json` guidance from `AGENTS.md`
- ignored `.openclaw/workspace-state.json`
- ignored `memory/.dreams/`
- refreshed `07. Audits/Auth Readiness Audit.md`
- refreshed `07. Audits/Capability Matrix.md`

## Remaining low-risk cleanup

- remove empty `state/` if it is still present

## Lesson reinforced

Installed is not enough. For this workspace, readiness means callable from the active shell, correctly configured, and authenticated when required.
