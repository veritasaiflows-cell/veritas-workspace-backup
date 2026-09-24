# Claude Opus 5.5 — Surface A closeout

**Outcome: owner-stopped; no score.**

Frozen oracle calibration and staged-input hashes passed. Opus 5.5 pinned cleanly through Claude CLI with no fallback, and the T4 read-route canary passed. The available `--message-file` path removed terminal line feeds from every prompt. Those bytes are part of Surface A's frozen prompt hashes, and the envelope does not authorize normalization.

Four initial first-turn calls are retained as transport-invalid and are not graded or replayed. Randall chose to stop Surface A rather than authorize a revised transport contract.

Evidence: `transport-blocker.json`, `surface-a-closeout.json`, raw `transport-*.json` receipts.
