state_io.write_json() can destroy the last good state: if json.dump fails midway (for
example on a value that is not JSON-serializable) the target file is left truncated.
Make write_json atomic: write to a temporary file in the same directory, then move it
onto the target with os.replace. On failure the original file must be unchanged, no
temporary file may be left behind, and the original exception must propagate. Keep the
output format identical (UTF-8, indent=2, sort_keys=True).

---
Scoped eval job builder-v1-f06-atomic-state-write-r1-20260926T064608Z. Work only inside /worktree. Read /worktree/handoff-manifest.json first.
Files you may change or create: state_io.py.
Read-only files (do not modify): test_state_io.py.
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
