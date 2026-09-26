snapshot_stats.coverage() over-reports history: "days" equals the file count, but several
snapshot files can share a date. Each snapshot is a JSON object with a top-level
"data_date" string (YYYY-MM-DD). Fix coverage() so:
- "snapshots" = number of *.json files in the directory (unchanged);
- "days" = number of distinct data_date values; files that are unreadable, not a JSON
  object, or lack a data_date string are still counted in "snapshots" but not in "days";
- new key "gaps" = sorted list of weekday dates (YYYY-MM-DD, Monday to Friday) strictly
  between the earliest and latest data_date that have no snapshot. Empty list when there
  are fewer than two distinct dates.

---
Scoped eval job builder-v1-f07-snapshot-distinct-days-r1-20260926T063238Z. Work only inside /worktree. Read /worktree/handoff-manifest.json first.
Files you may change or create: snapshot_stats.py.
Read-only files (do not modify): test_snapshot_stats.py.
Do not commit, do not access the network, and do not touch anything outside /worktree.
If any part of the task cannot be done as specified (it is contradictory, depends on something
that was not supplied, or needs a change to a read-only file or anything else outside the files
you may change), do not guess and do not work around it: make no edit for that part and include
a line that starts with "BLOCKED:" followed by the reason. Complete every other part.
Run the tests in /worktree before replying (cd /worktree && python3 -m unittest -v).
Reply with a short summary of what you changed and the exact output of the commands you ran.
