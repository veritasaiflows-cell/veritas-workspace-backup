# Upstream Issue Draft — `memory_search` KNN child spawn on Windows

**Status:** DRAFT ONLY — not filed. Requires Randall's explicit approval before anything public
(AGENTS.md: external/public action asks first).
**Prepared:** 2026-09-21 (America/Phoenix)
**Host evidence:** OpenClaw 2026.9.4 (3a9d69d), Windows 10.0.26200, Node v26.7.0
**Local canon:** `06. Playbooks/Project Continuity/Workspace Speed Audit - 2026-09-20.md` section 5

---

## 0. Duplicate check — IMPORTANT, read before filing

A directly related issue **already exists and is closed**:

| Item | Value |
|---|---|
| Issue | [#140681](https://github.com/openclaw/openclaw/issues/140681) — *"[Bug]: memory-core: since 2026.8.1, memory.search spends ~2.3 s per query booting a throwaway KNN child process — KNN itself is ~70 ms (was in-process in 2026.7.1)"* |
| State | closed / `state_reason: completed`, 2026-09-07T18:10:25Z |
| Fix PR | [#140730](https://github.com/openclaw/openclaw/pull/140730) — *fix(memory): avoid repeated vector search startup delays* (merged 2026-09-07T18:10:24Z) |
| Fix shape | Slimmed the child's module graph: added a private `memory-core-host-engine-knn` entrypoint; child no longer pulls the broad foundation barrel |

**The fix IS present in this build.** The installed child imports the slim entrypoint, not the barrel.
Upstream's matched Linux proof for #140730 was child boot **443 ms → 60 ms** median.

**So this is not a reopen and not a duplicate.** After the import-slimming fix, the remaining cost on
Windows is **process creation itself**, which that fix never targeted. The child and its query owner are
still one-shot per query, and on Windows a bare `node --version` costs about the same as the full child.

Recommendation: **file as a new issue**, cross-referencing #140681 and #140730 as predecessor work.
Do not post to the closed thread — it would not be seen as a new signal.

---

## 1. Issue title (proposed)

> `memory_search`: after the #140730 import-slimming fix, the per-query KNN child is now dominated by Windows process-creation cost (~1.5–1.8 s bare spawn), not module load

---

## 2. Bug report body (ready to paste)

### Bug type

Performance / portability gap (not a regression — the child design is deliberate and documented)

### Beta release blocker

No

### Summary

The KNN helper process added in 2026.8.1 is correct in design (bounded, OS-killable, read-only, keeps
the KNN step off the Gateway event loop). PR #140730 successfully cut its **module-load** cost on Linux
(443 ms → 60 ms median). On Windows, that fix buys far less, because the dominant term is not module load
at all — it is **Windows process creation**, which the slim-import change cannot touch.

Measured here: a bare `node --version` costs ~1.5–1.8 s, statistically indistinguishable from booting the
real KNN child (empty stdin). The child's *net* cost above bare process creation is only ~0.1–0.4 s.
Since `runVectorKnnInSubprocess` spawns a **fresh one-shot child per query** with no pool or reuse, every
`memory_search` still pays this floor, and it is ~55–75 % of a typical `searchMs`.

This is a **Windows process-creation cost**, so the impact is likely much smaller on Linux/macOS — stated
explicitly so severity can be judged correctly. On this host it is the single largest user-visible
recall cost.

### Steps to reproduce

Windows 10.0.26200, Node v26.7.0, OpenClaw 2026.9.4, file-backed memory index, sqlite-vec enabled.

1. Confirm the child is one-shot and spawned per query (no reuse, no pool):

   ```
   dist/extensions/memory-core/manager-runtime.js:5189   spawn(process.execPath, resolveRuntimeWorkerArgv(childUrl), {...})
   dist/extensions/memory-core/manager-runtime.js:5170   async function runVectorKnnInSubprocess(params)
   dist/extensions/memory-core/manager-runtime.js:5567   runVectorKnn: async (request, knnSignal) => await runVectorKnnInSubprocess({...})
   dist/extensions/memory-core/manager-runtime.js:5084   const MAX_CONCURRENT_VECTOR_KNN_CHILDREN = 2;
   ```

   The child is strictly one-shot — it reads stdin to `end`, writes one JSON result, and exits
   (`memory-search-knn.child.js`, `process.stdin.once("end", ...)`). `MAX_CONCURRENT_VECTOR_KNN_CHILDREN`
   bounds concurrency only; nothing is reused.

2. Time bare process creation (PowerShell, 6 runs each):

   ```powershell
   $sw=[Diagnostics.Stopwatch]::StartNew(); node --version *> $null; $sw.Stop(); $sw.ElapsedMilliseconds
   $sw=[Diagnostics.Stopwatch]::StartNew(); node -e 0      *> $null; $sw.Stop(); $sw.ElapsedMilliseconds
   ```

3. Time the real child with no work to do:

   ```powershell
   '' | node dist/extensions/memory-core/memory-search-knn.child.js
   ```

4. Compare. On this host the three are the same within noise — the child costs roughly what any Node
   process costs.

### Expected behavior

Either the per-query spawn cost is amortized (one long-lived KNN worker per manager, already bounded at 2),
or KNN runs in-process when the index working set is small enough, the way it did in 2026.7.1.

### Actual behavior

Every query pays a full process-creation + module-graph cost that does not shrink with the query.

### Measured attribution

| Term | ms | share |
|---|---|---|
| KNN child process spawn (boot + module graph) | ~1,200–1,700 | **~55–75 %** |
| KNN execution inside the child | ~100–540 | ~5–15 % |
| query embedding (warm) | 69–183 | ~3–8 % |
| source stat + sha256 (588 sources) | ~36–52 | ~2 % |
| FTS match | <5 | ~0 % |
| host jitter / scheduling | up to ~500 | ~10–20 % |

Independent re-measure of the spawn term alone (2026-09-21, 6 samples each, Node v26.7.0):

| Probe | min | median | max |
|---|---|---|---|
| `node --version` (bare boot) | 1,499 ms | 1,696 ms | 1,810 ms |
| `node -e 0` (bare boot + eval) | 1,650 ms | 1,747 ms | 2,162 ms |
| real KNN child, empty stdin | 1,658 ms | 1,778 ms | 2,216 ms |
| real KNN child, immediate repeat (warming) | 1,777 ms | 2,358 ms | 2,650 ms |

**Interpretation:** `node --version` ≈ the real child. There is no measurable "module graph" penalty left
here — the residual after #140730 is pure process creation. The repeat row shows no OS-level warming:
the cost does not amortize across consecutive spawns either.

Supporting notes from the same investigation:

- **Windows Defender is NOT the amplifier.** `Get-MpComputerStatus` reports
  `RealTimeProtectionEnabled: False`, `AntivirusEnabled: False`, no exclusions.
- Neither min-env, `--no-warnings`, `--jitless`, nor a larger old-space changes the number.
- The host is not idle-jitter-free: baseline samples ranged ~1.2–1.9 s across sessions, i.e. ±0.5 s.

### Note on the pragma hypothesis (secondary, refuted as dominant)

`PRAGMA mmap_size=0` / `cache_size=-2000` are **SQLite defaults**, not OpenClaw settings. The child sets
only `PRAGMA query_only = ON; PRAGMA busy_timeout = 5000`. Raising them is a real but small win
(~100 ms at the default candidate width, because the KNN working set is ~43.8 MB against a 1.87 GB file),
and there is **no config surface** for it — an exhaustive scan of `dist/**/*.{mjs,js}` finds **zero**
`mmap_size` occurrences.

### Confirmation requested in the report: does the same spawn path apply to local (non-file-backed) indexes?

**Yes.** In this build there is no runtime branch on the store's backing. `runVectorKnnInSubprocess` is
wired unconditionally into the manager's `searchVector` whenever the vector index is ready:

- `manager-runtime.js:5567` passes `runVectorKnn` unconditionally; `manager-runtime.js:4594` throws
  `"memory vector KNN subprocess is unavailable"` if it is absent rather than falling back.
- The only alternative path is `searchChunksByEmbedding` (`manager-runtime.js:4616`), a **full in-process
  scan**, used when the vector index is unavailable, not ready, or when the child returns
  `fallbackScanRequired`. That is not an "in-process KNN" path.
- No `isInMemoryDatabasePath` / `:memory:` / file-backed discrimination exists anywhere in
  `extensions/memory-core/`. The phrase "file-backed" occurs **only in a code comment**
  (`manager-runtime.js:5169`, `manager-search-knn.ts`) — it describes intent, it is not a condition.
  The `isInMemoryDatabasePath` helpers live in unrelated debug-proxy / config-doctor code.

So the spawn applies to every vector-enabled memory search regardless of backing; the comment's
"file-backed" qualifier is descriptive, not gating.

---

## 3. Upstream asks (priority order)

**Ask 1 — Amortize the KNN child. (primary; expected ~1.2–1.7 s per search on Windows)**
Reuse one long-lived KNN worker per manager — a small pool bounded by the existing
`MAX_CONCURRENT_VECTOR_KNN_CHILDREN = 2` — or run KNN in-process when the index working set is below a
threshold. The child protocol is already a clean request/response over stdin/stdout JSON, so a
persistent worker is a natural extension rather than a redesign. The bounded, killable-child property
that motivated the design is preserved by keeping per-request timeouts and admission caps; recycling a
child after N queries or on abort keeps the OS-killable escape hatch.

**Ask 2 — Set `PRAGMA mmap_size` (~2 GB) and `cache_size` (~64 MB) on the KNN child connection.
(secondary; expected ~100 ms at the default candidate width)**
The child currently sets only `query_only` + `busy_timeout`. Exact change:

```diff
--- a/dist/extensions/memory-core/memory-search-knn.child.js
+++ b/dist/extensions/memory-core/memory-search-knn.child.js
  	try {
  		db.exec("PRAGMA query_only = ON; PRAGMA busy_timeout = 5000");
+	 	db.exec("PRAGMA mmap_size = 2147483648");   // 2 GB; read-only map of the 1.87 GB store
+	 	db.exec("PRAGMA cache_size = -65536");      // 64 MB page cache
  		if (!extensionLoadingSupported) return {
```

Both pragmas are per-connection and non-persistent — they change nothing on disk and cannot corrupt the
store. (This diff is illustrative for upstream; it is **not** recommended as a local patch, since
`node_modules` edits are destroyed by `openclaw update` and it buys only ~5 %.)

---

## 4. Severity framing for upstream

- **Portability-dependent.** The dominant term is Windows process creation. On Linux/macOS the child boot
  is now ~60 ms after #140730, so the same design is a minor cost there. This should be weighed as a
  **Windows/portability** issue, not a universal one.
- **User-visible.** `memory_search` is on the recall path; a 1.5–1.8 s floor per search is felt directly.
- **No local mitigation exists.** No config surface for the pragmas, no env toggle on the spawn path, and
  patching `node_modules` is not durable.

---

## 5. Reproduction of the local canon

- Playbook: `06. Playbooks/Project Continuity/Workspace Speed Audit - 2026-09-20.md` §5 (full evidence,
  probes `tmp/_knn01…_knn07`).
- Re-measure probe (this pass): `tmp/knn_spawn_probe.mjs`.
- Upstream snapshots: `tmp/upstream140681/` (`timeline.json`, `comments.json`, `prs.json`,
  `pr140730.json`, `pr140730-files.json`).
