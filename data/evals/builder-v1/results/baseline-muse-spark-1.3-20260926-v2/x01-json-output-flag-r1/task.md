Add a --json flag to lane_report.main(). With --json, write exactly one JSON object and a
newline: {"lanes": [{"agent": ..., "tokens": ...}, ...], "total": ...}. Lanes are sorted
by tokens descending, ties by agent name ascending; "total" is the sum of the listed
lanes. --min-tokens filters lanes in both modes (total counts only listed lanes). Without
--json the text output must stay exactly as it is today.

---
Scoped eval job builder-v1-x01-json-output-flag-r1-20260926T065038Z. Work only inside /worktree. Read /worktree/handoff-manifest.json first.
Files you may change or create: lane_report.py.
Read-only files (do not modify): test_lane_report.py.
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
