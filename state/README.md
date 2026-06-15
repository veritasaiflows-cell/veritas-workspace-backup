# State Directory

`state/` holds durable local machine state that is meant to survive sessions and be treated as an operating-system surface.

## Authority

- State files are not owner approval, portfolio action, customer output, paper/live execution, brokerage/account action, or money movement authority.
- Durable state can become the machine-canon source for a bounded data family only when an approval reference, backup/rollback proof, validator report, and continuity note say so.
- Generated proof, scratch packets, and temporary query stores remain under `tmp/`.

## Current Subdirectories

- `finance/` - durable finance machine-state surfaces, including the first SQL canon candidate for ticker universe and answer-path scope.
- `archive-deletion-tombstone.json` - durable hash manifest for archive files deleted after exact approval and restore-drill proof. It preserves provenance for validators and historical references without keeping archive copies live.

## Operating Rules

- Back up SQLite databases with their WAL/SHM sidecars before schema or path changes.
- Do not archive, move, delete, vacuum, or checkpoint state databases without an exact manifest and rollback path.
- Keep human judgment and portfolio truth in the canonical notes layer; use state databases for validated machine routing, lookup, and scoped canon only.
