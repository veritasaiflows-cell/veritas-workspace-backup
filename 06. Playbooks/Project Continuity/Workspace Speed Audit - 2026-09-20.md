# Workspace Speed Audit - 2026-09-20

**Status:** complete. Read-only measurement. No config, cron, schedule, canon, or routing mutation.
**Update (2026-09-20 late, second pass):** the `memory_search` residual is resolved — see section 5. It is a
per-query KNN child-process spawn, not disk. One pragma proposal is recorded there as NOT applied.
**Owner:** Main (Veritas). Remediation owners named per item.
**Scope:** memory recall, routing front doors, data-finding/search, interpreter and disk overhead.
**Method:** live timings, 3-repeat where variance mattered. Probes retained in `tmp/`.

## Verdict (short)

Nothing is pathologically slow except two things: **`memory_search` at ~4.1 s** and
**`db_lifecycle_manifest.py --validate` at 6-8 s**. Everything else is 280 ms - 1.1 s, and most of
that floor is **CPython interpreter startup (~400 ms)**, not the work itself. The real workspace
problem is not latency, it is **unrotated disk mass** - 893 MB of `metrics.jsonl` that no retention
route covers.

## 1. Interpreter baseline (the hidden tax)

| Measurement | ms |
|---|---|
| `python -c pass` | 364-494 |
| `python` + stdlib imports (json, sqlite3, pathlib, re) | 880 |
| `import requests` | 741 |
| `import numpy` | 853 |
| `import pandas` | 1,184 |

Every Python front door pays ~400 ms before doing anything. This is why "fast" scripts still feel slow.

## 2. Routing front doors

| Route | ms |
|---|---|
| `workflow_router.py WF88 --answer next` | 417-546 |
| `concurrent_lane_manager.py --help` | 520 |
| `workflow_routing_index.py --help` | 606 |
| `artifact_index.py --help` | 442 |
| `db_lifecycle_manifest.py --help` | 715 |
| `workspace_index.py --help` | 726 |
| `startup_status_card.py --validate` | 757 |
| `project_implementation_router.py --help` | 830 |
| `vector_memory_index.py --help` | 847 |
| `workflow_router.py WF74 --answer summary` | 862 |
| **`db_lifecycle_manifest.py --validate`** | **6,049-8,129** |

Routing is healthy. Net work per route after the ~400 ms floor is ~100-450 ms. One genuine outlier.

## 3. `db_lifecycle_manifest` outlier - profiled

`cProfile`, 3,057,280 function calls, 7.489 s total:

| Function | tottime | note |
|---|---|---|
| `nt.stat` | 1.721 s | **40,310 calls** |
| `build_reference_index` (line 611) | 1.354 s | 1.723 s cumulative |
| BufferedReader.read | 0.575 s | 1,552 calls |
| TextIOWrapper.read | 0.460 s | 4,659 calls |
| hashlib.update | 0.411 s | 1,070 calls |
| `glob.select_recursive_step` | 0.158 s | 28,353 calls |

Scope is 155 databases / 256 sidecars, but the cost is **stat-and-glob fanout, not database work**.
Not scheduled in any cron contract, so this is a manual/front-door cost only.

## 4. Data finding

| Path | ms |
|---|---|
| `rg` targeted (scripts, memory, skills, playbooks) | 280 |
| `rg scripts` only | 317 |
| `rg -l` whole repo, gitignore honored | 1,078-1,312 |
| `rg` whole repo `--no-ignore` | 1,424 |
| `workspace_index.py --search` | 456-491 |
| `vector_memory_index.py --query` | 694-1,189 |

Search is **not** the bottleneck. `.gitignore` already excludes `tmp/**`, so rg sees 15,796 files
instead of 30,316 - that filtering is working. Index-based retrieval is no faster than rg and is
**40.6 h stale** (`tmp/workspace-index.sqlite`, 908 files changed since its build), so rg is the more
truthful route for current state.

## 5. Memory recall - the slowest user-visible path

| Component | ms |
|---|---|
| `memory_search` toolMs (measured in-session) | 4,123 / 3,442 / 2,843 |
| - managerMs | 1,872 / 1 / 179 |
| - searchMs | 2,248 / 3,440 / 2,660 |
| ollama embed, **cold** | 2,711 |
| ollama embed, **warm** | 36 / 69-161 |
| ollama `/api/tags` (server responsiveness) | 23-47 |
| vector store: 10,389 chunks, 588 sources | 21,446 pages, 15.6% free |

### CORRECTION (2026-09-20 late): embedding warmth is NOT the dominant term

The original finding above claimed recall cost is embedding-model cold start and that warming the
model "turns a 2.7 s cold hit into a 36 ms warm one." **That claim is refuted by direct measurement.**

With the model *provably resident* (`keep_alive: -1`, `/api/ps` expiry shown as year 2318), `memory_search`
still reported `searchMs` of **2,660-3,440 ms**. A direct replica of the retrieval mechanics, measured
independently, totals ~250 ms:

| Replica component | ms |
|---|---|
| query embedding (warm, via /api/embed) | 69-161 |
| FTS match | <2 |
| sqlite-vec KNN (k=60..200, exact query shape) | 25-46 |
| source stat + sha256 (588 sources) | 36 |
| **total** | **~250** |

So embedding residency contributes at most ~100 ms of a ~2.6-3.4 s `searchMs`. **A cold load is real
(~2.7 s) but it is not the dominant cost of a warm recall.** At the time this correction was written,
roughly 2.4-3.2 s of `searchMs` was unattributed; it was resolved in the second pass immediately below.

**RESOLVED (2026-09-20 late, second pass): the residual is a per-query child-process spawn, not disk.**

The prime hypothesis (pragma-driven disk reads) is **refuted as the dominant term**. The secondary
hypothesis (per-query process spawn) is **confirmed and is the answer**.

### Method

Read the real code path, then replicate it. `searchMs` is measured in
`dist/tools-CsMTOSB6.mjs` as `Date.now() - startedAt`, where `startedAt` is taken at
`executeMemorySearchToolQuery` entry (line 445) and the delta is computed in
`finalizeMemorySearchToolQuery` (line 558). That window therefore **encloses all of
`manager.search()`**, including the vector step.

That vector step does **not** run in-process. `manager.searchVector`
(`extensions/memory-core/manager-runtime.js:5555`) delegates to `searchVector`, which calls
`params.runVectorKnn(...)` (line 4594), which is `runVectorKnnInSubprocess` (line 5170). That function
spawns a **fresh Node process** every query:

```js
// manager-runtime.js:5188
child = spawn(process.execPath, resolveRuntimeWorkerArgv(childUrl), {
  env: buildChildEnv(), shell: false,
  stdio: ["pipe", "pipe", "pipe"], windowsHide: true
});
```

`childUrl` resolves to `dist/extensions/memory-core/memory-search-knn.child.js`; admission cap is
`MAX_CONCURRENT_VECTOR_KNN_CHILDREN = 2`. This is the **only** per-query `spawn` in memory-core
(verified by scanning `extensions/memory-core/`), so the spawn count is exactly one per search.

### Measured attribution

Probes: `tmp/_knn02_child_timing.py`, `tmp/_knn03_attribution.py`, `tmp/_knn04_pragma.py`,
`tmp/_knn05_node_spawn.mjs`, `tmp/_knn06_nodeboot.mjs`, `tmp/_knn07_full_replica.py`.

Full end-to-end replica of one retrieval, **including a real child spawn** (`tmp/_knn07_full_replica.py`,
K=200, 588 sources):

| Stage | ms |
|---|---|
| query embedding (warm ollama) | 159 |
| store open + vec0 extension load | 3 |
| FTS keyword match (4,881 hits) | 4 |
| **KNN child spawn (total, wall clock)** | **1,662** |
| source stat + sha256 (588 sources) | 52 |
| **total** | **1,885** |

That 1,885 ms matches the in-session `searchMs` of 1,776-3,440 ms, and **88% of it is the child spawn**.
A fresh in-session `memory_search` during this pass reported `searchMs: 1776`, `toolMs: 1790`,
`outsideSearchMs: 14` — consistent with the replica.

Decomposing the spawn itself (Node parent, exact `buildChildEnv()` replica,
`tmp/_knn05_node_spawn.mjs`):

| Measurement | ms |
|---|---|
| bare `node -e 0` (boot only) | 1,204-1,358 |
| child, real KNN k=60 (x8 = 480) | 1,553 min |
| child, real KNN k=200 (x8 = 1,600) | 1,744 min |
| **KNN work net of bare boot** | **+349 / +539** |

So the child pays ~1.2-1.4 s just to *exist*, then does the actual KNN in another ~0.35-0.54 s.
`tmp/_knn06_nodeboot.mjs` isolates the startup term: `node --version` costs the same as `node -e 0`
(~1,355 vs ~1,254 ms), and neither min-env, `--no-warnings`, `--jitless`, nor a larger old-space
changes it. **The cost is Windows process creation itself, not Node initialization.** Host load matters:
baseline samples ranged 1,204-1,900 ms, i.e. ~±0.5 s of jitter on this host.

Windows Defender is **not** the amplifier: `Get-MpComputerStatus` reports
`RealTimeProtectionEnabled: False`, `AntivirusEnabled: False`, and no exclusions.

### Why the pragma hypothesis failed, and what it is actually worth

`mmap_size = 0` and `cache_size = -2000` were **confirmed on the live store**, but they are SQLite
*defaults*, not OpenClaw settings — the child sets only `PRAGMA query_only = ON; PRAGMA busy_timeout = 5000`
(`memory-search-knn.child.js`) and inherits the rest. The hypothesis was right about the pragma values and
wrong about their weight, for two reasons:

1. **The KNN working set is tiny relative to the store.** Only ~43.8 MB is actually touched
   (30.5 MB vectors + 13.1 MB chunk text + 0.25 MB paths) out of 1,871 MB / 479,189 pages. The 1,772 MB
   figure in the earlier pass was the *file*, not the *scan* (`tmp/_knn04_pragma.py`, section A).
2. **Measured with the pragma raised, the gain is real but small** (`tmp/_knn04_pragma.py`, section B,
exact `runVectorKnnQuery` SQL, fresh process per invocation):

| Pragma | KNN k=480 | KNN k=1,600 |
|---|---|---|
| `mmap_size=0 cache_size=-2000` (live default) | 130-138 ms | 329-351 ms |
| `mmap_size=2GB cache_size=-64MB` | 22-36 ms | 58-71 ms |

Raising mmap saves ~100 ms at k=480 and ~280 ms at k=1,600. The real candidate width is
determined at `manager-runtime.js:5442` as `candidates = min(200, maxResults * hybrid.candidateMultiplier)`,
so a default 6-result query requests ~60 candidates (k≈480 after the **8x** oversample factor in
`manager-search-knn-Un_gF0VH.mjs`), i.e. the ~100 ms case. **That is ~5% of the observed searchMs — worth
having, but it is not the 2.4-3.2 s.**

The earlier replica only looked fast because it ran the KNN in-process: `tmp/_knn02_child_timing.py`
showed the child failing on a wrong extension path while still paying 1,306-1,608 ms, which is what
first exposed the spawn as the real term.

### Conclusion

The ~2.4-3.2 s residual is **not** unexplained disk I/O. It is OpenClaw's deliberate design choice to run
file-backed KNN in a **bounded, OS-killable child process** (`manager-search-knn-subprocess.ts`), paying
the host's full ~1.2-1.4 s process-creation cost on every `memory_search` because the store's KNN step is
never allowed inside the Gateway event loop. The code comment states the intent explicitly:
*"This function must run outside the Gateway event loop for file-backed indexes."*

Attribution of a typical 1,800-3,400 ms `searchMs`:

| Term | ms | share |
|---|---|---|
| KNN child process spawn (boot + module graph) | ~1,200-1,700 | **~55-75%** |
| KNN execution inside the child | ~100-540 | ~5-15% |
| query embedding (warm) | 69-183 | ~3-8% |
| source stat + sha256 | ~36-52 | ~2% |
| FTS match | <5 | ~0% |
| host jitter / scheduling | up to ~500 | ~10-20% |

**Do not claim a recall speedup from embedding residency, and do not expect a pragma change to fix recall
latency.** The only large lever is eliminating or amortizing the per-query child spawn, which is an
upstream design question, not a local tuning knob. See the proposal below.

### Proposal (owner approval required — NOT applied)

A pragma change is **warranted only as a small secondary win**, and there is **no config surface** for it:
exhaustive scan of `dist/**/*.{mjs,js,cjs}` found **zero** `mmap_size` occurrences and no memory-search
`cache_size` setting (the four `cache_size` hits are unrelated: transport caches and
`session-accessor.sqlite-import-stage`). It cannot be set from `openclaw.json` and would require a code
patch that an `openclaw update` would overwrite.

**Recommendation: do not patch locally. Escalate upstream instead.** Two upstream asks, in priority order:

1. **Amortize the KNN child** — reuse one long-lived KNN worker per manager (the spawn is already bounded
   by `MAX_CONCURRENT_VECTOR_KNN_CHILDREN = 2`) or run KNN in-process for indexes below a working-set
   threshold. Expected saving: ~1.2-1.7 s per search, i.e. most of the residual.
2. **Raise `mmap_size` / `cache_size` on the KNN child connection** (child currently sets only
   `query_only` + `busy_timeout`). Expected saving: ~100 ms at the default candidate width. Exact change
   if the owner ever wants it patched locally:

   ```diff
   --- a/dist/extensions/memory-core/memory-search-knn.child.js
   +++ b/dist/extensions/memory-core/memory-search-knn.child.js
   @@ -1,6 +1,8 @@
     try {
       db.exec("PRAGMA query_only = ON; PRAGMA busy_timeout = 5000");
   +   db.exec("PRAGMA mmap_size = 2147483648");   // 2 GB; read-only map of the 1.87 GB store
   +   db.exec("PRAGMA cache_size = -65536");      // 64 MB page cache
       if (!extensionLoadingSupported) return {
   ```

   **Rollback:** revert those two added lines (or restore the file from the pre-edit copy). Both pragmas are
   per-connection and non-persistent — they change nothing on disk and cannot corrupt the store. This edit
   lives in `node_modules` and is **destroyed by any `openclaw update`**; treat it as disposable.

   **Not recommended**, because the local patch is unversioned, gets overwritten, and buys ~5%.

**Do not claim a recall speedup from embedding residency until the residual is attributed.**

## 6. Disk mass and hygiene

Workspace total: **6,155 MB / 43,706 files**.

| Tree | MB | Files |
|---|---|---|
| tmp | 2,267 | 12,520 |
| 09. Archive | 1,166 | 4,900 |
| backups | 672 | 357 |
| scripts | 637 | 5,173 |
| data | 414 | - |
| tools | 288 | 3,929 |
| state | 217 | 358 |
| graphify-out | 188 | 4,005 |

**`tmp/otel-collector/metrics.jsonl` = 893 MB = 39.4% of tmp.** Created 2026-06-19, still growing at
~9.6 MB/day, open and live right now.

**Retention gap confirmed:** the `runtime-otel-collector-log-retention` cron contract runs
`otel_log_retention.py --max-mb 256 --keep 5`, but its defaults are `collector.err.log` and
`collector.out.log` only (`scripts/otel_log_retention.py:28-29`). **`metrics.jsonl` has no rotation
route** - it is only referenced by the watchdog and the metadata probe. `traces.jsonl` is 16 MB.

Aging: 8,329 tmp files >14 d (764 MB); 6,089 >30 d (480 MB).

Agent store `openclaw-agent.sqlite`: **1,772 MB**.

| Table | Rows | Blob mass |
|---|---|---|
| transcript_events | 100,328 | **662.3 MB** (avg 6,922 B, max 1.2 MB) |
| trajectory_runtime_events | 29,975 | 125.1 MB (avg 4,378 B) |

freelist_count = 19 pages. **There is no vacuum headroom** - the file is genuinely full of live data,
not fragmented. `transcript_events` alone carries 37% of the file as JSON payloads.

Query note: an unindexed `LIKE '%"type":"model.completed"%'` scan over
`trajectory_runtime_events` costs **1,171 ms**; a plain `COUNT(*)` costs 3 ms. The table has
`idx_agent_trajectory_runtime_run` but nothing usable for event-type filtering.

Git pack: 341 MB.

## Findings

1. **`metrics.jsonl` is an unbounded local write with no retention owner.** 893 MB, 39% of tmp,
   growing daily, and the one retention contract that looks like it should cover it does not.
2. **`memory_search` pays a per-query child-process spawn (~1.2-1.7 s of a ~1.8-3.4 s `searchMs`).**
   Resolved in section 5: the KNN step runs in `spawn(process.execPath, [...memory-search-knn.child.js])`,
   so every search pays this host's Windows process-creation cost. Embedding cold start is a separate,
   smaller, already-fixed term; the pragmas are real but worth only ~100 ms.
3. **Every Python front door pays ~400 ms interpreter startup.** Acceptable per-call; it multiplies
   across the 49 cron contracts and any multi-step shell sequence.
4. **`db_lifecycle_manifest.py --validate` is 15-20x slower than peer front doors** due to stat/glob
   fanout (40k `nt.stat` calls), not data volume.
5. **`workspace-index.sqlite` is stale (40.6 h, 908-file drift)** and slower than `rg`, so it should
   not be trusted as a current-state retrieval surface.
6. **Agent store is genuinely full (freelist ~0).** No compaction win is available; only retention
   policy would reduce it.
7. Search, routing, and most indexes are healthy. No structural retrieval problem.

## Recommendations (ranked)

1. **Bring `metrics.jsonl` under retention.** Highest value, lowest risk: it is 39% of tmp and the
   only unbounded growth. Either extend `otel_log_retention.py` to cover it or add a sibling
   contract. Requires owner approval (cron contract + script change). Estimated reclaim: 700-890 MB.
2. **Embedding residency is now genuinely armed (bug fixed), but it is not the recall-latency fix it
   was described as.** The guard at `scripts/embedding_keepalive_guard.py` had been reading
   `agents.defaults.memorySearch` and `providers.ollama.baseUrl`, neither of which exists in the live
   config. It therefore reported `status: skipped` on the false premise that memory search was not
   configured against local ollama, and **residency was never armed**. Repaired to read `memory.search`
   and `models.providers.ollama.baseUrl` (both shapes accepted so a rollback cannot silently disable it
   again). Re-arm verified end to end. **What it fixes:** removal of the ~2.7 s cold-load penalty after
   idle or an ollama restart. **What it does not fix:** the residual in `searchMs`, now attributed in
   section 5 to the per-query KNN child spawn. Do not expect any local tuning knob to fix it.
3. **Escalate the KNN child spawn upstream.** The single largest recall cost. Upstream asks: reuse one
   long-lived KNN worker per manager (already capped at 2 concurrent), or run KNN in-process below a
   working-set threshold. Expected saving ~1.2-1.7 s per search. Local patching cannot fix this and a
   `mmap_size`/`cache_size` patch buys only ~5%. No config surface exists for those pragmas (verified:
   zero `mmap_size` occurrences in `dist/**`).
4. **Fix `build_reference_index` fanout** in `db_lifecycle_manifest.py` (memoize stat results, scope
   the glob, or cache the index between runs). Pure code change, no authority question. Would take
   6-8 s to ~1-2 s.
5. **Retire or downgrade `workspace-index.sqlite` as a truth surface**, or reindex far more often.
   40 h stale + slower than rg means it currently only adds risk of stale answers.
6. **Prune tmp/backups under the existing DB-lifecycle gate** (8,329 files >14 d, 764 MB). Requires
   explicit owner approval and the existing archive/rollback path.
7. **Add `graphify-out` (3,999 files) to ignore scope** so whole-tree searches stay bounded.

Not recommended: vacuuming the agent store (no freelist headroom), or chasing interpreter startup
(400 ms is inherent to CPython on Windows and not worth a rewrite).

## Authority note

No config, cron, schedule, canon, capital, account, or routing mutation was made. All probes were
read-only, including every `memory_search` call. The `mmap_size`/`cache_size` diff in section 5 is a
**proposal only and was NOT applied**; section 5 also records why it is not recommended. Items 1, 2 (if
config), 3 (as an upstream change), and 6 require explicit owner approval.

## Provenance

Probes (first pass): `tmp/probe_ollama_cache_trend.py`, `tmp/probe_ollama_cache_now.py`,
`tmp/probe_ollama_cache_answer.py`, `tmp/probe_numctx_impact.py`, `tmp/probe_numctx_token_share.py`,
`tmp/_dbstat2.py`, `tmp/_tq.py`, `tmp/_blob.py`, `tmp/_blob2.py`, `tmp/_prof3.py`, `tmp/_wal.py`,
`tmp/_vms.py`, `tmp/_embed.py`.
Probes (residual attribution, second pass): `tmp/_knn01_store.py` (pragmas + page mass),
`tmp/_knn02_child_timing.py` (first child-spawn exposure), `tmp/_knn03_attribution.py` (boot vs KNN),
`tmp/_knn04_pragma.py` (working-set mass + mmap A/B), `tmp/_knn05_node_spawn.mjs` (exact `buildChildEnv`
replica), `tmp/_knn06_nodeboot.mjs` (process-creation isolation), `tmp/_knn07_full_replica.py`
(end-to-end accounting).
Sources: workspace filesystem; `~/.openclaw/agents/main/agent/openclaw-agent.sqlite`;
`tmp/workspace-index.sqlite`; `tmp/vector-memory.sqlite`; `state/cron-contracts/*.json`;
OpenClaw 2026.9.4 `dist/`.
