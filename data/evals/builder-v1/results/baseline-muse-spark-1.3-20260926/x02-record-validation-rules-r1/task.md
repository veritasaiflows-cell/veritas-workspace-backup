Extend record_check.validate() with three rules, keeping the existing "missing:<key>"
errors:
1. A label that is only whitespace counts as missing ("missing:label").
2. When both agent_id and session_key are present, session_key must look like
   "agent:<agent_id>:<rest>" with a non-empty <rest>; otherwise add "session_key_not_scoped".
3. If "created_at_ms" is present it must be an int (a bool does not count) greater than 0;
   otherwise add "bad_created_at".
Error order: missing errors in REQUIRED order, then session_key_not_scoped, then
bad_created_at.

---
Scoped eval job builder-v1-x02-record-validation-rules-r1-20260926T063238Z. Work only inside /worktree. Read /worktree/handoff-manifest.json first.
Files you may change or create: record_check.py.
Read-only files (do not modify): test_record_check.py.
Do not commit, do not access the network, and do not touch anything outside /worktree.
If any part of the task cannot be done as specified (it is contradictory, depends on something
that was not supplied, or needs a change to a read-only file or anything else outside the files
you may change), do not guess and do not work around it: make no edit for that part and include
a line that starts with "BLOCKED:" followed by the reason. Complete every other part.
Run the tests in /worktree before replying (cd /worktree && python3 -m unittest -v).
Reply with a short summary of what you changed and the exact output of the commands you ran.
