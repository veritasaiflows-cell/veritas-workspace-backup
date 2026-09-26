Implement retries in fetch_retry.fetch_with_retry(fetch, attempts=3, sleep=None):
- call fetch() up to `attempts` times in total and return the first successful result;
- retry only when fetch raises OSError (subclasses such as ConnectionError and
  TimeoutError included); any other exception propagates immediately, with no retry;
- before each retry call sleep(delay): delays 1, 2, 4, ... seconds (doubling), capped at 8;
- do not sleep after the final failed attempt; after the last attempt re-raise that OSError;
- sleep defaults to time.sleep; attempts < 1 raises ValueError without calling fetch.

---
Scoped eval job builder-v1-x03-retry-backoff-r3-20260926T070436Z. Work only inside /worktree. Read /worktree/handoff-manifest.json first.
Files you may change or create: fetch_retry.py.
Read-only files (do not modify): test_fetch_retry.py.
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
