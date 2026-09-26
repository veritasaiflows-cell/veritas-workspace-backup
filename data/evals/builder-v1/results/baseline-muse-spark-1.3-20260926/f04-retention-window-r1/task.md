retention.is_expired() is wrong since the store switched units: "ended_at" is now epoch
milliseconds, like now_ms. A row expires exactly at ended_at + days (inclusive: at that
instant it is expired). ended_at of None means the run is still going and never expires.
Fix is_expired(), then add expiring_within(rows, now_ms, hours, days=7): rows are dicts
with "id" and "ended_at"; return the ids of rows that are not yet expired and will expire
at or before now_ms + hours, ordered by expiry time (earliest first). Skip rows whose
ended_at is None.

---
Scoped eval job builder-v1-f04-retention-window-r1-20260926T062945Z. Work only inside /worktree. Read /worktree/handoff-manifest.json first.
Files you may change or create: retention.py.
Read-only files (do not modify): test_retention.py.
Do not commit, do not access the network, and do not touch anything outside /worktree.
If any part of the task cannot be done as specified (it is contradictory, depends on something
that was not supplied, or needs a change to a read-only file or anything else outside the files
you may change), do not guess and do not work around it: make no edit for that part and include
a line that starts with "BLOCKED:" followed by the reason. Complete every other part.
Run the tests in /worktree before replying (cd /worktree && python3 -m unittest -v).
Reply with a short summary of what you changed and the exact output of the commands you ran.
