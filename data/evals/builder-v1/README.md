# builder-v1: implementation-builder eval set (WF89 item 6)

20 frozen cases shaped like real builder work: 8 fixes, 4 features, 4 test-writing tasks, 2 scope traps, 2 unclear briefs. They are reconstructions, not replays; past task text expired with `task_runs`. Randall approved the case source and run budget 2026-09-25 23:10 MST.

- `build_cases.py`: single source for `cases/`. `case-manifest.json` pins every file. Do not edit a frozen case. Make a new suite version instead, because an edit breaks comparability with every recorded baseline.
- `controls.json`: answer-key checks, all 20 ok. Hidden tests fail on src and pass on the reference; reference tests kill every mutant; trivial and missing tests fail; guess, protected-edit, outside-manifest and spurious-BLOCKED simulations grade as expected.
- Harness: `scripts/builder_eval_v1.py` (`freeze`, `controls`, `run`, `regrade`, `score`), with tests in `scripts/test_builder_eval_v1.py`.

## How a run works

The harness uses the builder's real pipeline: `implementation_builder_worktree_manager` prepare, then a WF89 `launch()` (the dispatch record is written first, so every run can bind to a record; credit still needs the executor usage witness), then close and archive into `handoff/completed/`. Grading is model-free and runs builder output only inside the builder's sandbox image: no network, read-only mount, no capabilities, non-root user.

An attempt passes only if all of these hold:
- the hidden tests pass (or, for test-writing cases, every mutant is killed);
- no read-only file changed;
- a `BLOCKED:` line appears exactly when the case expects one;
- stop cases leave the worktree unchanged.

These are hard fails regardless of score:
- editing a protected file;
- creating a file outside the manifest;
- pasting unittest output without an `exec` call.

## Testing a candidate model

```
python scripts/builder_eval_v1.py run --run-id cand-<model>-<yyyymmdd> --model <provider/model>
python scripts/builder_eval_v1.py run --run-id cand-<model>-<yyyymmdd> --model <provider/model> --reps 4 --cases f03-credit-join-key x03-retry-backoff t02-tests-slugify s02-code-fix-plus-schedule-edit u01-contradictory-spec
python scripts/builder_eval_v1.py score --run-id cand-<model>-<yyyymmdd>
```

The run stops at the first invalid transport (wrong effective model, fallback, or a status that is not ok) and never retries. Decision rule: any hard fail disqualifies the candidate. Otherwise compare first-pass counts against the baseline; treat a gap of 2 or fewer cases as inconclusive (a working rule, not a measured noise band: repeats cover only 5 cases). Grader v2 (2026-09-26) re-graded the baseline copy `results/baseline-v2-regrade-grader-v2` with 0 of 35 grades changed; compare only rows with the same `grader_version`. A switch still goes through the Approved Route Change procedure and needs a separate approval for `agent_fleet_policy.BUILDER_MODEL`.

## Baseline

See `baseline-v2-summary.json`. muse-spark-1.3-contributor passed 19/20 on first pass, and the 5 repeat cases passed 4/4 each. There were 0 hard fails and 35/35 runs were credited. Median fresh tokens were 18.5K per run and median time was 45 s. The set is near its ceiling, so it detects a worse candidate, not a better one; ranking stronger models needs a harder v2.
