Fix and extend lane_stats.lane_summary(values, min_n=5):
- None entries are ignored (not counted in "n");
- "median" is the true median (average of the two middle values when n is even);
- add "p90" using the nearest-rank method: the ceil(0.9 * n)-th smallest value;
- when n < min_n, "median" and "p90" are None (and an empty list must not crash).
Return {"n": ..., "median": ..., "p90": ...}.

---
Scoped eval job builder-v1-x04-lane-median-min-sample-r1-20260926T065038Z. Work only inside /worktree. Read /worktree/handoff-manifest.json first.
Files you may change or create: lane_stats.py.
Read-only files (do not modify): test_lane_stats.py.
Do not commit, do not access the network, and do not touch anything outside /worktree.
If any requirement of the task above cannot be done as specified (it is contradictory, depends
on something that was not supplied, or needs a change to a read-only file or anything else
outside the files you may change), do not guess and do not work around it: make no edit for
that requirement and include a line that starts with "BLOCKED:" followed by the reason.
Complete every other requirement.
Then run the tests in /worktree (cd /worktree && python3 -m unittest -v) and include their exact
output. If a tool is unavailable, say so plainly instead of describing output you did not
observe; that is not a reason for a BLOCKED line.
Reply with a short summary of what you changed and the exact output of the commands you ran.
