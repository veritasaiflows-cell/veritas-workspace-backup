# Startup Surface Compression Audit - 2026-06-07

## Scope

Audited the boot/startup files that are loaded or consulted during direct startup, recovery, and route selection:

- `SOUL.md`
- `AGENTS.md`
- `IDENTITY.md`
- `USER.md`
- `TOOLS.md`
- `MEMORY.md`
- `HEARTBEAT.md`
- `06. Playbooks/Startup Truth Index.md`

## Finding

The startup layer was valid but close to drift pressure. `MEMORY.md` and Startup Truth Index were just under the 10 KB warning line, and `TOOLS.md` had begun accumulating command detail that belongs in `scripts/README.md`, workflow capsules, or continuity notes.

The core issue was not incorrect doctrine. It was route/procedure mixing:

- `TOOLS.md` carried some script-catalog detail instead of only first-hop routes.
- `MEMORY.md` carried dated workflow command history already owned by WF73/WF75/WF78 notes and generated route packets.
- Startup Truth Index carried a tier-by-tier queue table instead of compact route categories.

## Compression Applied

| File | Before | After | Change |
|---|---:|---:|---:|
| `TOOLS.md` | 9,079 bytes | 7,909 bytes | -1,170 |
| `MEMORY.md` | 9,975 bytes | 7,792 bytes | -2,183 |
| `06. Playbooks/Startup Truth Index.md` | 9,944 bytes | 8,760 bytes | -1,184 |

Total boot/control size after the pass: `96,043` bytes with `0` warnings and `0` hard failures.

## Migration Decisions

- Kept identity, mission, hard authority, and finance boundaries in `SOUL.md`, `AGENTS.md`, and `USER.md`.
- Kept runtime facts, Windows/PowerShell rules, and first-hop route commands in `TOOLS.md`.
- Kept only curated durable decisions in `MEMORY.md`; moved command-level workflow detail back to owner routes/continuity by reference.
- Kept Startup Truth Index as a compact route map; removed queue-detail duplication that belongs in workflow capsules and Active Workflows.
- Created pending Skill Workshop proposal `workspace-governor-20260608-a4535613aa` to add startup-surface compression rules to `workspace-governor`.

## Owner Surfaces

- Startup/boot-size governance: WF73 and `scripts\boot_surface_size_guard.py`.
- Workspace organization skill: `workspace-governor` pending proposal above.
- Detailed script command catalog: `scripts\README.md`.
- Workflow-specific route/state: `state\workflows\*.json`, Active Workflows, and workflow continuity notes.
- Chronological work history: `memory\YYYY-MM-DD.md`.

## Validation

- `python scripts\boot_surface_size_guard.py --write --validate` -> ok, `0` warnings, `0` hard failures.

## Boundary

This pass did not change identity doctrine, finance authority, portfolio/canon apply authority, paper/live/account authority, customer/public authority, config/runtime/channel state, or archive/delete permissions.
