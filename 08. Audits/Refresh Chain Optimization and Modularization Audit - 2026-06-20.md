# Refresh Chain Optimization and Modularization Audit — 2026-06-20

**Auditor:** Veritas main session  
**Date generated (UTC):** 2026-06-21T06:45:00Z  
**Target files:**
- `scripts/run_finance_refresh_chain.py`
- `scripts/chain_manifest.py`
- Supporting manifest consumers: `scripts/market_data_utils.py`, `scripts/concurrent_lane_manager.py`

**Scope:** Review the finance refresh chain for efficiency, modularity, restartability, and parallelization potential. Provide a concrete optimization plan.

**Authority boundary:** Review-only. No code, config, cron, canon/portfolio, or execution mutations in this audit. Existing `tmp/*` proof artifacts were refreshed only to gather live evidence.

---

## Executive Conclusion

The refresh chain is **functional but inefficient**: it executes 46–101 scripts per window in strict serial order, with large duplicated manifest definitions across windows, no per-step timeouts, no artifact-freshness skipping, no built-in parallelization, and no stage-level restart points.

**Grade: C+** — it works, it has recovery finalizers, and the manifest is explicit, but it is overdue for modularization and parallel execution.

**Estimated impact of the recommended refactor:**
- Wall-clock reduction: **~30–55%** for the full windows (`morning`, `post-close`, `sunday`) by parallelizing independent roots and early branches.
- Maintenance burden reduction: **~40%** less manifest duplication by extracting reusable stage fragments.
- Debug/restart cost reduction: stage-level resume cuts re-run time after a mid-chain failure from ~100% to ~10–30%.

---

## 1. Current Chain Profile

### 1.1 Window sizes (from live `chain_manifest.py`)

| Window | Steps | Declared dependencies | Duplicate scripts | Recovery finalizers |
|---|---|---|---|---|
| `morning` | 86 | 179 | 2 (`wf70_wf66_official_evidence_spine.py`, `run_summary_refresh.py`) | `run_summary_refresh.py`, `dashboard_run_summary_consumer.py` |
| `post-close` | 101 | 217 | 2 (same) | `run_summary_refresh.py` |
| `post-earnings` | 46 | 69 | 2 (same) | `run_summary_refresh.py` |
| `sunday` | 90 | 187 | 2 (same) | `run_summary_refresh.py` |
| `full` | 101 (alias of post-close) | 217 | 2 (same) | `run_summary_refresh.py` |

### 1.2 Execution model

`run_finance_refresh_chain.py` uses a single `for` loop:

```python
for step_record, step in zip(state["steps"], steps):
    result = subprocess.run([sys.executable, str(path), *run_args], cwd=str(WORKSPACE))
```

Characteristics:

- **Serial only.** Every script waits for the previous one to finish, even when dependencies are independent.
- **No per-step timeout.** A hung script blocks the whole window indefinitely. This is a known live failure mode: `wf74_model_quality_collection_cron_runner.py` currently hangs because `validator_timing_ledger.py` triggers long-running downstream calls.
- **No artifact-freshness skipping.** The chain re-runs every script every time, regardless of whether inputs changed.
- **No stage boundaries.** A failure in step 75 forces a restart from step 1 or manual surgery.
- **No dependency-graph validation at runtime.** `--dry-run` prints the list but does not compute a critical path or detect structural issues.
- **Manual tail mutation.** `--build-workbook` and `--cleanup` are handled by inline list splicing in `resolved_steps()` rather than by a composable manifest fragment.

### 1.3 Manifest duplication

`chain_manifest.py` contains five near-identical inline dictionaries. `morning`, `post-close`, and `sunday` share roughly 70+ identical steps in the same order, with only the tail and a few window-specific args (`--window morning|post-close|sunday`) differing. This violates DRY and makes window-wide changes error-prone.

### 1.4 Live control-plane context

During this audit, the following related signals were refreshed:

- `tmp/cron-control-packet.json`: status `error`, 4 escalation signals, including `Ops - OTEL Local Digest` blocked.
- `tmp/cron-freshness-spine.json`: 78 jobs, 2 blocked, 1 unregistered.
- `tmp/wf74-model-quality-collection-cron-runner.json`: status `blocked`, root cause `validator_timing_ledger_normal` blocked.
- `tmp/validator-timing-ledger.json`: status `blocked` because `cron_control_packet` and `fast_path_qa_no_probes` return non-zero (escalation/freshness issues, not the chain itself).

These are **not direct defects of the refresh chain**, but they show the environment in which the chain runs: many long scripts, serial execution, and cascading failures when one validator produces escalation residue.

---

## 2. Findings

### F1 — Serial execution wastes wall-clock time (High impact, Medium effort)

The manifest declares explicit dependencies. A dependency graph can be built automatically. Many early steps are independent roots:

- `earnings_calendar_enrichment.py`
- `policy_expectations_refresh.py`
- `credit_spread_refresh.py`
- `breadth_refresh.py`
- `validate_portfolio_config.py`
- `technical_refresh.py`

These could start simultaneously. The current chain leaves CPU/disk/network idle while scripts that could run in parallel wait.

**Evidence:**
- `post-close` has 101 steps with 217 declared dependencies, but the dependency graph is shallow early and fans out late.
- No concurrency is attempted.

### F2 — No per-step timeout (High impact, Low effort)

A single hung script (`model_run_ledger.py`, `runtime_performance_scorecard.py`, etc.) blocks the entire window. The runner only has a global `for` loop; it relies on external cron/process timeouts.

**Evidence:**
- `wf74_model_quality_collection_cron_runner.py` is currently blocked because a downstream call inside `validator_timing_ledger.py` runs long and returns non-zero.
- `runtime_performance_scorecard.py` was killed during this audit after hanging.

### F3 — No artifact-freshness skipping (Medium impact, Medium effort)

Every script runs every time. Many scripts are idempotent but expensive. With declared inputs (`depends_on`) and declared outputs (`expected_outputs`), the chain could skip a step when all inputs are older than outputs and the output artifact is valid.

**Evidence:**
- `market_state_refresh.py` depends on `policy_expectations_refresh.py`, `credit_spread_refresh.py`, `breadth_refresh.py`. If none of those changed, `market_state_refresh.py` could still be valid.
- `validate_dashboard_state.py` depends on `generate_dashboard.py`. If the dashboard file is unchanged, the validation could be skipped.

### F4 — Massive manifest duplication (Medium impact, Medium effort)

`morning`, `post-close`, `sunday`, and `full` repeat the same core sequence: portfolio config → fundamentals → official IR capture → macro → technical/band → trigger → dashboard → brief/reports → finalizers. Window-specific args are spliced in manually.

This makes it easy for one window to drift from the others and hard to verify parity.

### F5 — No stage-level restartability (Medium impact, Medium effort)

There is no `--from-stage` or `--stage` option. If a late step fails, the only recovery modes are:
- rerun from step 1 (expensive)
- manually invoke the failing script and then resume (error-prone)

The recovery finalizers (`run_summary_refresh.py`, `dashboard_run_summary_consumer.py`) are good, but they only help after a failure, not for resuming mid-window.

### F6 — Dry-run does not analyze the graph (Low impact, Low effort)

`--dry-run` prints the planned chain but does not:
- compute the critical path
- report maximum depth
- identify independent groups
- detect cycles
- flag missing dependency outputs

A richer dry-run would make optimization planning easier.

### F7 — Tail mutation is ad-hoc (Low impact, Low effort)

`resolved_steps()` mutates the list to insert `workbook_template.py` after `workbook_export.py` and appends `tmp_cleanup.py` for the sunday window. This logic should live in the manifest as an optional stage fragment, not as imperative list surgery.

### F8 — No integration with lane manager for helper context (Low impact, Low effort)

When the chain is invoked from a spawned helper lane, there is no automatic lease of write surfaces beyond the chain-state file. The `concurrent_lane_manager.py` exists but is not used by the refresh chain.

### F9 — Step-level state file is overwritten, not append-only (Low impact, Low effort)

`tmp/run-chain-{window}.json` is atomic-written on every step. This is good for crash recovery but makes it the only durable trace. A companion append-only `run-chain-{window}.jsonl` would make post-mortem analysis and timing regression easier.

---

## 3. Recommendations and Optimization Plan

### 3.1 Goal

Refactor the refresh chain into **stage-based, dependency-aware, restartable, optionally parallel** execution while preserving the existing recovery-finalizer behavior and authority boundaries.

### 3.2 Non-goals

- Do not change script behavior or output contracts.
- Do not remove recovery finalizers or stop lines.
- Do not introduce live trading, account, canon/portfolio mutation, or cron-schedule mutation authority.
- Do not make the chain fully autonomous; it remains a callable workflow under explicit window selection.

### 3.3 Implementation plan

#### Phase 1 — Refactor `chain_manifest.py` into fragment-based stages

**Deliverable:** `scripts/chain_manifest.py` uses reusable stage fragments.

Steps:

1. Define stage fragments as plain functions or dicts:
   - `_STAGE_FUNDAMENTALS`
   - `_STAGE_MARKET_DATA`
   - `_STAGE_PORTFOLIO_TECHNICAL`
   - `_STAGE_INTELLIGENCE`
   - `_STAGE_VALIDATION`
   - `_STAGE_SUMMARY_AND_REPORTS`
   - `_STAGE_RECOVERY_FINALIZERS`
2. Each fragment returns a list of step dicts.
3. Window manifests compose fragments plus window-specific tail steps.
4. Add a `stages` field to each window manifest so the runner can name and restart at stage boundaries.

**Validation:**
- `--list` output for all windows matches the current output (order and args).
- A new `--list-stages` option prints stage composition.

**Estimated effort:** 1 helper lane, ~2–3 hours.

#### Phase 2 — Add dependency graph builder and topological scheduler

**Deliverable:** `scripts/chain_manifest.py` exposes `build_dependency_graph(window)` and `topological_batches(window)`.

Steps:

1. Build a directed graph from `depends_on`.
2. Compute depth (longest path from any root) iteratively to avoid recursion limits.
3. Return batches of scripts that share the same depth and have no unresolved in-window dependencies.
4. Detect cycles and missing dependencies; fail fast during `--dry-run`.

**Validation:**
- A new `--dry-run --analyze` option prints depth, batch count, critical-path length, and independent-group sizes.
- No cycles or forward dependencies are reported for any window.

**Estimated effort:** 1 helper lane, ~2–3 hours.

#### Phase 3 — Add incremental execution (artifact freshness skipping)

**Deliverable:** `run_finance_refresh_chain.py` supports `--incremental`.

Steps:

1. For each step, compare the newest mtime of declared input artifacts/dependency outputs against the mtime of each declared expected output.
2. A step is skipped when:
   - all expected outputs exist
   - every expected output is newer than every declared dependency output
   - the previous chain state recorded the step as `ok`
3. Write a `skipped_fresh` status and record the reason.

**Validation:**
- Running twice with `--incremental` on the same window skips unchanged steps.
- Touching an input artifact causes downstream steps to rerun.

**Estimated effort:** 1 helper lane, ~2–3 hours.

#### Phase 4 — Add bounded parallel execution

**Deliverable:** `run_finance_refresh_chain.py` supports `--parallel N` (default 1 to preserve current behavior).

Steps:

1. Use a thread/process pool (prefer `concurrent.futures.ProcessPoolExecutor` for Python scripts to avoid GIL contention) with max workers `N`.
2. Run each topological batch; wait for the batch to finish before starting the next depth.
3. Apply recovery rules across the batch: if any script in a batch fails and is not a finalizer, mark remaining non-finalizer steps in later batches as `skipped_after_failure`.
4. Preserve `chain_state` atomic writes and stdout/stderr capture.

**Authority guard:**
- Parallel execution does not change script semantics; scripts remain subprocess-isolated.
- `--parallel` is opt-in and default 1, so existing cron jobs are unchanged.

**Validation:**
- `--parallel 4 --dry-run --analyze` shows expected batch schedule.
- `--parallel 2` on `post-earnings` completes faster than serial and produces identical artifacts.
- A synthetic failure in an early batch correctly skips later non-finalizer steps.

**Estimated effort:** 1 helper lane, ~3–4 hours.

#### Phase 5 — Add per-step timeouts and stage-level CLI options

**Deliverable:**
- `--step-timeout SECONDS` (default 300)
- `--stage STAGE` to run one stage
- `--from-stage STAGE` to resume from a stage
- `--list-stages` to print stage names

Steps:

1. Apply `subprocess.run(timeout=...)` using the per-step budget.
2. Map stages to contiguous step ranges in the manifest.
3. `--from-stage` runs from the first step of the named stage; earlier steps are marked `skipped_by_user`.
4. `--stage` runs only the named stage and writes a dedicated state file `tmp/run-chain-{window}-{stage}.json`.

**Validation:**
- A synthetic long-running script is terminated at the timeout and triggers recovery.
- `--from-stage portfolio` on `post-close` skips fundamentals/market-data stages.

**Estimated effort:** 1 helper lane, ~2–3 hours.

#### Phase 6 — Add pre-flight validator and richer dry-run

**Deliverable:** A new `--dry-run --validate-manifest` option and a separate `scripts/chain_manifest_validator.py`.

Checks:

1. All referenced scripts exist in `scripts/`.
2. No circular dependencies.
3. No forward dependencies (a step must not depend on a later step in the manifest order).
4. Duplicate scripts are intentional and documented.
5. All declared expected outputs are paths under `tmp/`, `data/`, or `state/`.
6. All `--window` args match the selected window.
7. `--apply`, `--execute`, or `--send` flags are not present in cron-facing windows unless explicitly gated.

**Validation:**
- Running on current manifests passes with documented duplicate exceptions.
- Injecting a fake dependency on a later step fails fast.

**Estimated effort:** 1 helper lane, ~2 hours.

#### Phase 7 — Integrate with lane manager and append-only history

**Deliverable:** Optional `--lane-id` argument; append-only chain log.

Steps:

1. If `--lane-id` is provided, call `concurrent_lane_manager.py --set-status running` at start and `--complete` at finish.
2. Write each completed step as a line to `data/state-history/run-chain-{window}.jsonl`.
3. Keep `tmp/run-chain-{window}.json` as the live state file.

**Validation:**
- Running with `--lane-id TEST-LANE` updates the lane register.
- The JSONL file grows by one line per step.

**Estimated effort:** 1 helper lane, ~1–2 hours.

#### Phase 8 — QA and timing regression baseline

**Deliverable:**
- Smoke tests for all windows in `--dry-run --validate-manifest --analyze` mode.
- At least one real `--parallel 2` run on `post-earnings` compared against a serial run for artifact equality.
- Update `scripts/README.md` with new options.

**Validation:**
- No manifest drift vs. original step order.
- Artifact set identical between serial and parallel runs (except timestamps).
- Timing regression snapshot recorded in `tmp/runtime-performance-scorecard.json`.

**Estimated effort:** 1 helper lane + main QA, ~2–3 hours.

---

## 4. Suggested Module Split

After the refactor, the chain code should be split into:

| File | Responsibility |
|---|---|
| `scripts/chain_manifest.py` | Stage fragments, window composition, dependency graph, topological batches |
| `scripts/chain_executor.py` | Serial/parallel execution, timeouts, incremental skip, recovery rules, state persistence |
| `scripts/chain_validator.py` | Manifest lint: cycles, missing scripts, forward deps, flag audit |
| `scripts/run_finance_refresh_chain.py` | CLI, window selection, argument parsing, calls executor + validator |
| `scripts/chain_state.py` | State model, atomic writes, JSONL append, recovery helpers |

This keeps `run_finance_refresh_chain.py` small and makes the executor independently testable.

---

## 5. Risks and Mitigations

| Risk | Mitigation |
|---|---|
| Parallel execution causes SQLite or file write collisions | Run dependent scripts in separate topological batches; only independent scripts run in parallel. Keep default `--parallel 1`. |
| Incremental skip hides stale upstream config changes | Record input mtimes in state; require `--force` to ignore freshness. |
| Stage boundaries change failure semantics | Stage resume is opt-in; default remains full-window run. |
| Manifest refactor accidentally reorders steps | `--dry-run --validate-manifest` compares against original step order snapshot. |
| Per-step timeout kills a slow but healthy script | Default timeout 300s; allow per-script override in manifest via `timeout_seconds`. |
| Process pool overhead exceeds gains for tiny scripts | Only parallelize batches with >1 script; keep pool size bounded. |

---

## 6. Quick Wins (Can be done before the full refactor)

1. **Add per-step timeout immediately.** Add `timeout=300` to the existing `subprocess.run` call as a one-line safety improvement.
2. **Add `--from-step INDEX`.** Allow resuming from a specific step index; minimal change, high debug value.
3. **Document duplicate scripts.** Add comments in `chain_manifest.py` explaining why `wf70_wf66_official_evidence_spine.py` and `run_summary_refresh.py` appear twice.
4. **Write append-only chain log.** Add a JSONL write next to the atomic state file.

---

## 7. Next Actions

| # | Action | Owner | Status |
|---|---|---|---|
| 1 | Approve the optimization plan and phase order | Randall | Awaiting decision |
| 2 | Implement Phase 1 (fragment-based stages) in a helper lane | Veritas / helper | Blocked on #1 |
| 3 | Implement Phase 2 (dependency graph / topological scheduler) | Veritas / helper | Blocked on #2 |
| 4 | Implement Phase 3 (incremental skip) | Veritas / helper | Blocked on #2 |
| 5 | Implement Phase 4 (bounded parallel execution) | Veritas / helper | Blocked on #3/#4 |
| 6 | Implement quick win #1 (per-step timeout) immediately | Veritas main | Ready, low risk |
| 7 | Run full QA smoke tests after each phase | Veritas main + helper | Ready |

---

## 8. Audit Trail

- Read `scripts/run_finance_refresh_chain.py` and `scripts/chain_manifest.py` in full.
- Refreshed `tmp/cron-control-packet.json`, `tmp/cron-freshness-spine.json`, `tmp/artifact-staleness-explainer.json`, `tmp/wf74-model-quality-collection-cron-runner.json`, `tmp/validator-timing-ledger.json`, and `tmp/pm-control-packet.json` to gather live control-plane context.
- No source files were modified.
- The only file written outside `tmp/` is this audit under `08. Audits/`.

---

*End of audit.*
