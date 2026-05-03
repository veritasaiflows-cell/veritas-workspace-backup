# Workspace Root Cleanup and Classification Pass - 2026-05-02

## Scope
Bounded root cleanup and classification pass under `Notes Layer Governance Protocol` and `workspace-governor` standards.

## Root decisions

### Removed from active root
- `state/`
  - reason: empty scaffolding
- `templates/`
  - reason: duplicate of `09. Archive/templates - Archived/`
  - verification: file hashes matched archived copies before removal from active root

### Moved out of active root
- `temp-skill-inspect/` -> `09. Archive/temp-skill-inspect - Archived/`
  - reason: scratch inspection material, not an active skill root
  - preservation posture: archived, not deleted

### Kept in root as documented exceptions
- `generated documents/`
  - reason: live scripts still hard-reference `generated documents/entry-bands/`
  - trust decision: keep as a temporary generated-surface exception until the code path is intentionally migrated
- `migration-backups/`
  - reason: justified reversible-backup surface

## What this pass did not do
- did not rewrite script paths for `generated documents/`
- did not reorganize numbered domains
- did not change canonical finance notes
- did not change auth, config, or network posture

## Outcome
- active root is tighter
- duplicate and scratch root clutter was reduced
- one remaining generated root surface is now treated as an explicit exception rather than silent drift

## Follow-on recommendation
- keep `generated documents/` only until a bounded script-path migration intentionally moves that surface under `tmp/`
- use `Workspace Structure Protocol` and `Notes Layer Audit Checklist` for recurring enforcement
