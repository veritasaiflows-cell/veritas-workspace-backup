# WF78 / WF85 / WF86 / WF87 Script Optimization Audit — 2026-06-20

**Auditor:** Veritas main session  
**Date generated (UTC):** 2026-06-21T07:00:00Z  
**Scope:** Review the WF78 intelligence-routing/tier-promotion family and the WF85–WF87 decision/execution-support layers for optimization opportunities: code duplication, orchestration efficiency, file I/O bloat, and modularization.

**Authority boundary:** Review-only. No code, config, cron, canon/portfolio, or execution mutations in this audit. Some existing `tmp/*` proof artifacts were refreshed to gather live evidence.

---

## Executive Conclusion

The WF78/WF85/WF86/WF87 family has grown into a **mature but sprawling pipeline**. It correctly preserves authority boundaries (review-only, no capital/execution approval inference), but it pays a high tax in **boilerplate duplication, nested serial orchestration, and tiny artifact sprawl**.

**Grade: C+** — functionally sound, architecturally overdue for consolidation.

**Estimated optimization impact:**
- **Code base reduction:** ~15–25% fewer lines in the WF family by extracting a shared runner library.
- **Wall-clock reduction:** ~20–40% for `wf78_daily_freshness_loop` and `wf78_intelligence_routing_v2` by parallelizing independent steps within phases/layers.
- **Maintenance cost reduction:** ~30% by centralizing authority-boundary helpers, JSON I/O, schema/path registry, and timeout runners.
- **Artifact volume reduction:** ~30–50% fewer tiny `tmp/wf78-*.json` files by consolidating per-phase packets.

---

## 1. Scope and Inventory

### 1.1 Script counts

| Family | Scripts | Notes |
|---|---|---|
| `wf78_*` | ~98 | Intelligence routing, tier promotion, source capture, scaleout |
| `wf85_*` | ~12 | Deployment timing, market-hours readiness, paper notifications |
| `wf86_*` | ~6 | Shadow decision ledger, assisted order cards, reconciliation |
| `wf87_*` | ~12 | Intraday monitor, autonomy command center, readiness rollup |
| **Total WF family** | **~128** | Slight overlap with tests; ~116 distinct non-test scripts observed |
| **All workspace scripts** | **970** | For context |

### 1.2 Largest WF-family scripts

| Script | Size |
|---|---|
| `wf78_legacy_42_tier_migration_planner.py` | 43.6 KB |
| `wf78_100_to_200_candidate_manifest.py` | 43.2 KB |
| `wf78_routing_dashboard.py` | 37.0 KB |
| `wf78_capital_review_queue.py` | 36.4 KB |
| `wf78_sql_readiness_index.py` | 35.1 KB |
| `wf78_101_200_provider_source_validation.py` | 34.9 KB |
| `wf78_500_ticker_reputation_gate.py` | 34.3 KB |
| `wf78_tier_a_competitive_promotion_gate.py` | 33.3 KB |

### 1.3 Artifact sprawl

| Family | `tmp/*.json` count | Total bytes | Average size |
|---|---|---|---|
| `wf78-*` | 174 | ~17.7 MB | ~102 KB |
| `wf85-*` | 17 | ~0.6 MB | ~35 KB |
| `wf86-*` | 1 | ~7.8 KB | — |
| `wf87-*` | 11 | ~0.1 MB | ~10 KB |

The WF78 artifact prefix distribution shows heavy concentration:

- `tier*` — 46 artifacts
- `route*` — 24 artifacts
- `batch*` — 14 artifacts
- `source*` — 7 artifacts

Many of these are small, single-purpose packets that could be consolidated into per-phase composite packets.

---

## 2. Key Findings

### F1 — Severe boilerplate duplication across 97–109 of 116 WF-family scripts (High impact, Low effort)

The same helper functions are copy-pasted into nearly every script:

| Pattern | Occurrences in WF family |
|---|---|
| `def utc_now()` | 109 |
| `atomic_write_json` import/usage | 109 |
| `def rel(path)` | 107 |
| `load_json_artifact` import/usage | 107 |
| `def as_dict(value)` | 103 |
| `def as_list(value)` | 97 |
| `def load_dict(path)` / equivalent | 81 |
| `def build_report()` / similar | 66 |

This is not just cosmetic. It means:

- Authority-boundary widening checks are re-implemented differently in each file.
- JSON I/O semantics (encoding, error handling, atomicity) vary subtly.
- Subprocess runner logic (timeout, stdout/stderr capture, dry-run) is duplicated.
- Any improvement to the runner primitive requires touching 100+ files.

**Evidence:** Static AST scan across `wf78_*.py`, `wf85_*.py`, `wf86_*.py`, `wf87_*.py`.

### F2 — `wf78_daily_freshness_loop.py` is a 47-step serial orchestrator with no dependency graph (High impact, Medium effort)

The script defines 47 steps in a flat list, tags each with a phase, then filters by selected phase and runs them serially. There is:

- no dependency graph
- no parallelization within a phase
- no `duration_ms` field per step (only 1-second-resolution UTC timestamps)
- no time-budget enforcement at the step level
- no incremental skip based on artifact freshness

**Evidence:**
- `wf78_daily_freshness_loop.py` defines `all_steps()` with 47 tuples.
- Latest run with `--phase evidence_repair` executed 10 steps in ~12 seconds wall-clock; several steps show 0-second resolution because they completed within the same UTC second.
- The loop calls `wf78_auto_tier_router.py` three separate times, `finance_ticker_card_refresh_gate.py` twice, `wf77_price_freshness_bridge.py` twice — all serially.

### F3 — `wf78_intelligence_routing_v2.py` is the right abstraction but under-parallelized (Medium impact, Medium effort)

This script introduces:

- layer definitions (`preflight`, `tier_routing`, `freshness`, `repair_scan`, `card_materialization`, `ledger_publish`, `postflight`)
- per-layer time budgets
- aliases (`daily_core_v2`, `market_probe`, `evening_ledger`)
- expected artifacts per layer

However:

- Commands inside each layer still run serially.
- `wf78_daily_freshness_loop.py` is called as a single command inside layers (`tier_routing`, `freshness`), so the v2 abstraction does not fix the serial loop problem inside the loop.
- The v2 orchestrator and the daily freshness loop are parallel implementations of the same concept; maintenance must happen in both places.

**Evidence:**
- `LAYER_DEFS` in `wf78_intelligence_routing_v2.py` lists commands as a flat list per layer.
- The `tier_routing` layer invokes `wf78_daily_freshness_loop.py --phase tier_routing` (a nested serial pass).

### F4 — Ticker scaleout generated many near-duplicate scripts (Medium impact, Medium effort)

WF78 universe expansion produced separate scripts for:

- `wf78_100_ticker_candidate_scope_packet.py`
- `wf78_100_ticker_import_gate.py`
- `wf78_100_to_200_candidate_manifest.py`
- `wf78_101_200_candidate_source_registry.py`
- `wf78_101_200_import_decision_packet.py`
- `wf78_101_200_provider_source_validation.py`
- `wf78_101_200_tier_c_import_gate.py`
- `wf78_500_ticker_reputation_gate.py`

These likely share 80%+ logic (read registry, validate source, build packet, write JSON). They differ mainly in ticker ranges and gating rules.

**Evidence:** File sizes are 27–43 KB each and names differ by range/gate type.

### F5 — Literal tmp/data/state paths and schemas are scattered (Medium impact, Low effort)

AST scan found repeated literal strings:

- `tmp/wf78-auto-tier-routing.json` — 5 scripts
- `tmp/wf78-tier-weighted-freshness-resolution.json` — 3 scripts
- `data/finance/universe-v1.json` — 3 scripts
- `tmp/wf78-routing-delta.json` — 2 scripts
- Multiple `veritas.wf78_*` schema strings — each appears in its owning script only

A central path/schema registry would eliminate typos, make renames safer, and reduce boilerplate.

### F6 — WF85/WF86/WF87 duplicate the same primitives (Medium impact, Low effort)

Despite being thin compositors over WF78/WF84, these layers still:

- redefine `utc_now`, `rel`, `load_json`, authority boundary
- hardcode input artifact paths
- re-implement false-key validation for authority widening

For example, `wf85_paper_deployment_notification_digest.py` contains a large `DANGEROUS_FALSE_KEYS` set. Other scripts likely contain similar sets.

### F7 — No fast dry-run smoke for the WF78 pipeline (Medium impact, Low effort)

There is no single command that validates the entire WF78 orchestrator graph without executing heavy sub-scripts. `wf78_intelligence_routing_v2.py --dry-run` exists, but it still invokes subprocesses (the dry-run logic is inside `run_command`, not at the manifest level), so it is not a fast structural test.

### F8 — `wf78_phase_runner.py` requires explicit phase selection and can run long (Medium impact, Low effort)

This script is a manual repair/apply runner. It is not part of the daily cron but is used for targeted fixes. It supports phases like `source-open-cleanup`, `proof-lock`, `phase4-recommendation`, `all-safe`. There is no documented map of when to use each phase, and `--phase all-safe` can be long-running.

### F9 — WF86/WF87 appear underutilized (Low impact, Low effort)

Live artifact ages:

- `wf86-*` artifacts: only 1 found, age ~230 hours.
- `wf87-*` artifacts: 11 found, newest ~0 hours, but several ~8 hours old.

This may indicate these workflows are not on the daily cron path or are not completing reliably. Either they need integration, retirement, or explicit documentation of their trigger policy.

### F10 — No shared timeout/parallel runner primitive (Medium impact, Medium effort)

Each orchestrator re-implements `subprocess.run(..., capture_output=True, timeout=...)`. None use a shared runner that can:

- enforce per-step timeouts
- run independent commands in parallel
- produce uniform step records with `duration_ms`
- support dry-run uniformly
- record append-only JSONL history

---

## 3. Recommendations and Optimization Plan

### 3.1 Goal

Consolidate the WF family around a **shared runner library**, a **single dependency-aware orchestrator**, and a **schema/path registry**, while preserving the existing review-only authority model and output contracts.

### 3.2 Non-goals

- No changes to authority boundaries.
- No live trading, execution, canon/portfolio, or cron schedule mutation.
- No removal of existing recovery finalizers or stop lines.
- No changes to individual script output JSON schemas unless backward-compatible.

### 3.3 Implementation plan

#### Phase 1 — Create `scripts/wf_runner_lib.py` (shared library)

**Deliverable:** A new module providing common primitives used by all WF scripts.

**Exports (examples):**

```python
# Time / paths
utc_now() -> str
rel(path: Path) -> str

# JSON I/O
load_dict(path) -> dict
load_list(path) -> list
atomic_write_json(path, payload) -> None

# Authority helpers
build_authority_boundary(base: dict, **overrides) -> dict
verify_authority_keys_stay_false(packet: dict, keys: set) -> list[str]

# Subprocess runner
run_step(name, command, timeout, dry_run=False, cwd=ROOT) -> dict
#   returns uniform dict with name, command, started_at_utc, completed_at_utc,
#   duration_ms, returncode, ok, timeout, stdout_preview, stderr_preview

# Orchestration primitives
run_parallel_batch(steps: list[tuple], max_workers=1, dry_run=False) -> list[dict]
run_serial_chain(steps, ...) -> list[dict]
```

**Migration:**
- Start by replacing boilerplate in new scripts.
- Backfill the 10–15 most frequently modified scripts per week.
- Do not mass-refactor all 116 scripts at once; that is high risk and low incremental value.

**Estimated effort:** 1 helper lane, ~3 hours.

#### Phase 2 — Refactor `wf78_daily_freshness_loop.py` into stage fragments + dependency graph

**Deliverable:** The loop uses stage fragments and a topological scheduler.

Steps:

1. Define stage fragments:
   - `card_refresh`
   - `tier_routing`
   - `fundamentals`
   - `evidence_repair`
   - `source_capture`
   - `owner_review`
   - `wf84_sync`
2. Each fragment declares its steps with `depends_on` and `expected_outputs`.
3. Build a dependency graph within the fragment.
4. Run independent commands within each fragment in parallel (default max workers 2 or 4).
5. Add `duration_ms` to every step record.
6. Add `--incremental` skip based on input/output mtimes.

**Validation:**
- `--dry-run --analyze` prints the dependency graph, depth, and batch schedule.
- Running `--phase evidence_repair` produces the same artifacts as today but faster.
- Running twice with `--incremental` skips unchanged steps.

**Estimated effort:** 1 helper lane, ~4–5 hours.

#### Phase 3 — Consolidate `wf78_intelligence_routing_v2.py` and `wf78_daily_freshness_loop.py`

**Deliverable:** One primary orchestrator, not two.

Options:

- **Option A (recommended):** Make `wf78_intelligence_routing_v2.py` the primary orchestrator. Have it call stage fragments directly, not via `wf78_daily_freshness_loop.py`. Keep `wf78_daily_freshness_loop.py` as a thin backward-compatible alias that calls v2 with the right layer alias.
- **Option B:** Keep both but extract the stage-fragment scheduler into a shared module used by both.

**Validation:**
- Both entry points produce identical artifacts for the same phase/layer combination.
- A test script asserts output parity.

**Estimated effort:** 1 helper lane, ~3 hours.

#### Phase 4 — Parallelize commands within WF78 v2 layers

**Deliverable:** `wf78_intelligence_routing_v2.py` runs independent commands in each layer in parallel.

Steps:

1. Add `depends_on` to each command in `LAYER_DEFS`.
2. Compute batches per layer.
3. Use `wf_runner_lib.run_parallel_batch`.
4. Default `--parallel 1` to preserve current behavior; allow `--parallel 2|4|8`.

**Validation:**
- `--parallel 2` completes faster than serial.
- Artifacts are identical except timestamps.
- A synthetic failure in an early batch correctly blocks dependent later commands.

**Estimated effort:** 1 helper lane, ~3 hours.

#### Phase 5 — Consolidate ticker scaleout scripts

**Deliverable:** Parameter-driven scripts replace range-specific copies where logic is shared.

Candidates:

- `wf78_100_ticker_import_gate.py` + `wf78_101_200_tier_c_import_gate.py` → `wf78_ticker_import_gate.py --range 100|101-200|all`
- `wf78_100_to_200_candidate_manifest.py` + `wf78_101_200_candidate_source_registry.py` + `wf78_101_200_provider_source_validation.py` → a single `wf78_universe_scaleout_packet.py` with subcommands.
- `wf78_500_ticker_reputation_gate.py` → keep as a specialized gate but extract shared registry reader from above.

**Validation:**
- Existing outputs are reproduced by the consolidated scripts.
- Legacy script names can remain as thin wrappers during a deprecation window.

**Estimated effort:** 1 helper lane, ~4 hours.

#### Phase 6 — Create schema/path registry

**Deliverable:** `scripts/wf_constants.py` or `scripts/wf_registry.py`.

Contents:

```python
TMP = Path("tmp")
WF78_TIER_ROUTING = TMP / "wf78-auto-tier-routing.json"
WF78_FRESHNESS_RESOLUTION = TMP / "wf78-tier-weighted-freshness-resolution.json"
WF84_DATA_PLANE = TMP / "canonical-finance-data-plane.json"
SCHEMA_WF78_ROUTING = "veritas.wf78_auto_tier_routing.v1"
...
```

**Validation:**
- New scripts use registry paths.
- A lint script flags new literal `tmp/wf78-*` paths in PRs.

**Estimated effort:** 1 helper lane, ~2 hours.

#### Phase 7 — Add fast structural smoke test for WF78 pipeline

**Deliverable:** `scripts/test_wf78_pipeline_smoke.py`.

Behavior:

1. Load all layer/phase definitions.
2. Verify all referenced scripts exist.
3. Verify no circular/forward dependencies.
4. Run all orchestrators in `--dry-run` mode without invoking heavy sub-scripts (stub subprocess runner).
5. Assert authority boundaries remain review-only.

**Validation:**
- Runs in under 10 seconds.
- Catches broken layer definitions immediately.

**Estimated effort:** 1 helper lane, ~2 hours.

#### Phase 8 — Consolidate tiny WF78 artifacts into per-phase packets

**Deliverable:** A consolidation pass that merges small related WF78 outputs.

Examples:

- Merge `wf78-tier-c-attention-trigger.json`, `wf78-tier-c-hold-recheck.json`, `wf78-routing-delta.json`, `wf78-event-triggered-rerouting.json` into `wf78-tier-routing-state.json` with nested sections.
- Merge `wf78-source-capture-requirements-queue.json`, `wf78-official-source-discovery.json`, `wf78-official-registry-proposal.json`, `wf78-promotion-owner-lineage-queue.json` into `wf78-source-capture-packet.json`.

**Caution:** This changes consumer read paths. Do it only after establishing the registry and updating the main consumers (WF84, WF85, dashboard).

**Estimated effort:** 1 helper lane, ~4 hours.

#### Phase 9 — WF86/WF87 activation or retirement decision

**Deliverable:** Audit note + Randall decision.

- If these workflows are meant to be daily, add them to the cron spine and freshness contract.
- If they are exploratory/paused, mark them as deprecated or move to `06. Playbooks/Paused Workflows/`.
- If they are event-driven, document the trigger policy.

**Estimated effort:** Veritas main, ~1 hour.

#### Phase 10 — QA and regression baseline

**Deliverable:**
- Smoke tests for all WF78 phases/layers in dry-run.
- Real run timing baseline for `wf78_intelligence_routing_v2.py --layer daily_core_v2` before and after refactor.
- Artifact parity check between old and new entry points.

**Estimated effort:** 1 helper lane + main QA, ~3 hours.

---

## 4. Suggested Module Split After Refactor

| File | Responsibility |
|---|---|
| `scripts/wf_runner_lib.py` | Shared time, path, JSON I/O, authority helpers, subprocess/parallel runner |
| `scripts/wf_registry.py` | Central artifact paths and schema names for WF78/WF85/WF86/WF87 |
| `scripts/wf_manifest.py` | Stage fragments, dependency graph, topological batches for WF78 |
| `scripts/wf78_intelligence_routing_v2.py` | Primary orchestrator; calls stage fragments |
| `scripts/wf78_daily_freshness_loop.py` | Thin backward-compatible alias |
| `scripts/wf78_scaleout_packet.py` | Consolidated 100/101-200/500 scaleout logic |
| `scripts/wf85_deployment_timing_gate.py` | Reads consolidated WF78/WF84 packets |
| `scripts/wf85_paper_deployment_notification_digest.py` | Reads consolidated WF78/WF84/WF67 packets |
| `scripts/test_wf78_pipeline_smoke.py` | Fast structural smoke test |

---

## 5. Risks and Mitigations

| Risk | Mitigation |
|---|---|
| Mass refactor breaks output parity | Migrate incrementally; preserve old scripts as thin wrappers; run artifact parity tests. |
| Parallel execution causes file/SQLite collisions | Only parallelize within a topological batch; default to serial. |
| Consolidating artifacts breaks downstream consumers | Use the registry module; update consumers before removing old paths. |
| Shared library import failure breaks many scripts | Keep the shared library simple, pure-Python, no heavy imports at module load. |
| Time spent on refactor exceeds value | Phase 1 + Phase 2 alone deliver the biggest gains; later phases can be deferred. |
| WF86/WF87 retirement decision is contentious | Treat as a separate governance decision, not part of the technical refactor. |

---

## 6. Quick Wins (Can be done immediately)

1. **Add `duration_ms` to `wf78_daily_freshness_loop.py` step records.** One-line change using `time.perf_counter()`.
2. **Create `scripts/wf_runner_lib.py` and migrate `wf78_intelligence_routing_v2.py` + `wf78_daily_freshness_loop.py` to use it.** These two scripts are the highest-leverage consumers.
3. **Add a fast `--dry-run --no-subprocess` mode to `wf78_intelligence_routing_v2.py`.** Structural validation without spawning sub-scripts.
4. **Document the phase/layer map.** A short playbook note explaining when to use `wf78_intelligence_routing_v2.py --layer ...` vs `wf78_phase_runner.py --phase ...` vs `wf78_daily_freshness_loop.py --phase ...`.

---

## 7. Next Actions

| # | Action | Owner | Status |
|---|---|---|---|
| 1 | Approve the optimization plan and priority order | Randall | Awaiting decision |
| 2 | Decide WF86/WF87 activation/retirement policy | Randall | Awaiting decision |
| 3 | Implement quick win #1: add `duration_ms` to freshness loop | Veritas main | Ready |
| 4 | Implement Phase 1: `scripts/wf_runner_lib.py` | Veritas / helper | Blocked on #1 |
| 5 | Implement Phase 2: stage fragments + dependency graph in daily loop | Veritas / helper | Blocked on #4 |
| 6 | Implement Phase 3: consolidate v2 and daily loop | Veritas / helper | Blocked on #5 |
| 7 | Implement Phase 4: parallelize within layers | Veritas / helper | Blocked on #3/#6 |
| 8 | Implement Phase 5: consolidate scaleout scripts | Veritas / helper | Blocked on #1 |

---

## 8. Audit Trail

- Read representative WF78/WF85/WF86/WF87 scripts: `wf78_intelligence_routing_v2.py`, `wf78_daily_freshness_loop.py`, `wf85_deployment_timing_gate.py`, `wf85_paper_deployment_notification_digest.py`, `wf86_shadow_decision_ledger.py`, `wf87_v2_readiness_rollup.py`.
- Ran AST scan across 116 WF-family scripts for boilerplate, duplicated paths, and schema literals.
- Refreshed `tmp/wf78-daily-freshness-loop.json`, `tmp/wf85-paper-deployment-notification-digest.json`, `tmp/wf86-shadow-decisions.json`, `tmp/wf87-v2-readiness-rollup.json`, `tmp/veritas-artifact-index.sqlite`, and related cron/PM packets to gather live context.
- No source files were modified.
- The only file written outside `tmp/` is this audit under `08. Audits/`.

---

*End of audit.*
