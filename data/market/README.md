# data/market

Durable market-data registry surface for reusable market and regime inputs.

Authority boundary:
- This folder may hold reusable local market data inputs and registry-style files.
- Generated proof, run summaries, and temporary market snapshots belong in `tmp/`.
- Human judgment and narrative market interpretation belong in `02. Markets/` or `memory/`.
- This folder is not portfolio authority, owner approval, customer delivery, trade/account action, paper/live execution, or money movement authority.

Retention posture:
- Keep durable inputs that are reused by scripts or validators.
- Archive stale one-off generated files only after reference scan, replacement proof, rollback path, and owner-approved move-only archive gate.
