credit_join.join_runs() loses runs. Registry rows that were re-announced get a new
"run_id" (for example "announce:requester-settle:..."); the true join key is "taskRunId"
inside the row's "payload_json" (a JSON string). When payload_json is missing, empty, not
valid JSON, not a JSON object, or has no taskRunId, fall back to the row's "run_id".
Also, today a task matched by two registry rows silently keeps one of them: such a task
must map to the string "AMBIGUOUS". Unmatched tasks map to None.

---
Scoped eval job builder-v1-f03-credit-join-key-r2-20260926T070146Z. Work only inside /worktree. Read /worktree/handoff-manifest.json first.
Files you may change or create: credit_join.py.
Read-only files (do not modify): test_credit_join.py.
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
