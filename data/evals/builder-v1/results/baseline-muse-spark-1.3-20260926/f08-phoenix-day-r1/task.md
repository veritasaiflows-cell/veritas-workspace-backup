local_day.phoenix_day() returns the UTC calendar date, so evening timestamps land on the
next day. Phoenix is UTC-7 all year (no daylight saving). Fix phoenix_day() without
depending on the zoneinfo/tz database (it is not installed in every runtime), and add
day_bounds_ms(day) that takes "YYYY-MM-DD" and returns (start_ms, end_ms): epoch
milliseconds of the start of that Phoenix calendar day and of the next day's start (end
exclusive).

---
Scoped eval job builder-v1-f08-phoenix-day-r1-20260926T063238Z. Work only inside /worktree. Read /worktree/handoff-manifest.json first.
Files you may change or create: local_day.py.
Read-only files (do not modify): test_local_day.py.
Do not commit, do not access the network, and do not touch anything outside /worktree.
If any part of the task cannot be done as specified (it is contradictory, depends on something
that was not supplied, or needs a change to a read-only file or anything else outside the files
you may change), do not guess and do not work around it: make no edit for that part and include
a line that starts with "BLOCKED:" followed by the reason. Complete every other part.
Run the tests in /worktree before replying (cd /worktree && python3 -m unittest -v).
Reply with a short summary of what you changed and the exact output of the commands you ran.
