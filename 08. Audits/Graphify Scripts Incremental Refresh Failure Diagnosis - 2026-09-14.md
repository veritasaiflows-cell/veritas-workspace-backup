# Graphify Scripts Incremental Refresh — Failure Diagnosis and Fix Proposal

**Date:** 2026-09-14 (America/Phoenix)
**Job:** `Runtime - Graphify Scripts Incremental Refresh` (`d1f906e9-0eec-4cae-a7d5-80c40b3728c8`)
**Declaration key:** `veritas.graphify-scripts-incremental-refresh.v1`
**Schedule:** `0 4 * * 0` America/Phoenix (weekly, Sunday 04:00), `sessionTarget: isolated`, `delivery.mode: none`
**Payload:** `python.exe scripts/memory_graph_maintenance.py --mode refresh --max-seconds 600 --write --validate`, `timeoutSeconds: 660`
**Status:** `error`, exit code 1, `consecutiveErrors: 4`
**Owner of failing logic:** `scripts/lib/graphify_incremental_owner.py` (`v0.3.0-bounded-incremental`)
**Authority:** diagnosis and proposal only. No graph, cron, contract, or config mutation was made.

---

## 1. Bottom line

The refresh does not have an intermittent problem. **The bounded incremental path has never once published a batch.**

The failure is a **false-positive integrity refusal**, not bad data. `merge_candidate` rejects a batch whose contents are entirely legitimate: Graphify 0.9.45 emits AST nodes and edges that the owner's validator treats as corrupt but that the full build path handles routinely. There are **three stacked refusals**, and fixing the one named in the error message only exposes the next one.

The refreshed graph is currently **stale by roughly five weekly cycles**: `scripts/graphify-out/graph.json` was last written 2026-09-07, while 127–128 code files have drifted and the owner itself was last modified 2026-09-13.

---

## 2. What the packet actually says

From `tmp/operational-graph-maintenance.json` (written 2026-09-15T01:02:35Z):

| Field | Value |
|---|---|
| `status` | `error` |
| `action` | `owner_stage_then_publish_incremental_batch` |
| `before.freshness` | `stale` — 97 changed, 30 new, 0 deleted |
| `owner_preflight.outcome` | `ready`, `launch_allowed: true` |
| `selection.target_count` | 25 of 127 changed (`MAX_TARGETS` cap) |
| `stage_result.returncode` | 2 |
| `owner_refusal.reason` | `fresh_node_foreign_source` |
| `publication` | `not_attempted` |

Preflight passed, so the owner accepted the batch and then refused it during merge. The refusal payload carries **no offending node id or path**, which is itself a defect (§6.1).

---

## 3. Root cause — three stacked refusals

All three were reproduced against the real pinned backend (`graphifyy 0.9.45`) using the real selected 25-target batch, the real `unchanged_resolution_context`, and the owner's real `merge_candidate` / `validate_graph`. No graph was written.

### Layer 1 — `fresh_node_foreign_source` (owner line 935, via `_fresh_source_key` lines 884–894)

`_fresh_source_key("")` falls through to `_normalize_rel("")`, which raises `relative_path_required`; `merge_candidate` converts that into `fresh_node_foreign_source`.

**The premise is wrong.** Of the 972 nodes returned for the batch, **74 carry `source_file: ""`** and **none of them is foreign**. They are shared resolution stubs — builtin / stdlib / external symbols:

```
agent_bootstrap_generator_py_any        label "Any"
agent_bootstrap_generator_py_path       label "Path"
agent_bootstrap_generator_py_namespace  label "Namespace"
bare: json, argparse, pathlib, typing, sys, datetime, subprocess, ...
shape: {id, label, file_type, source_location, source_file:"", _origin:"ast"}
```

Critically, **this shape is already normal in the maintained graph**:

- The base graph (`graph.json`) contains **2,853 blank-`source_file` AST nodes**, all with `_origin: "ast"`.
- 2,763 of those are file-scoped (`concurrent_lane_manager_py_any` → `concurrent_lane_manager.py`).
- 24 are bare symbols (`decimal`, `htmlparser`, `go_type_time_time`, `moduletype`).
- 59 of the fresh batch's 74 stub ids **already exist in the base graph with a blank `source_file`** and identical content.

So the base graph was built by a path that accepted these nodes, and the incremental path refuses them. This is a false positive in `merge_candidate`, not a data problem.

### Layer 2 — `fresh_edge_dangling_refused` (owner line 999)

Relaxing Layer 1 exposes the next refusal: **192 of 3,495 fresh edges dangle** against `preserved_ids | fresh_ids`.

Every one of those 192 targets a **bare stdlib module id that exists in neither the fresh nodes nor the base graph**:

```
argparse 24, json 24, pathlib 24, typing 20, datetime 15, sys 13,
hashlib 12, shutil 11, subprocess 10, os 7, re 6, math 4, sqlite3 4,
copy 3, time 3  (22 distinct)
```

`base_edges_targeting_stdlib_ids` is **empty** — the full build never retained these edges. `cli.py` dedups and the clustered build runs edges through NetworkX, which drops unresolvable endpoints; the owner instead hard-refuses the whole batch.

### Layer 3 — `candidate_duplicate_edge` (via `validate_graph`)

With Layers 1–2 handled, the merged candidate fails validation: `graphify.extract()` returns **157 exact duplicate edge pairs** (222 by Graphify's own `(source, target, relation, source_file, source_location)` key).

This is **inherent to `extract()` and not caused by the resolution context** — an A/B run with `resolution_context_nodes=None` and a cold cache returned the identical 157/222 duplicates. The base graph contains **zero** duplicate edges by the same key.

Upstream, this is handled explicitly before graph state is written:

```
cli.py:3771    merged["nodes"] = _dedupe_nodes(merged["nodes"])
cli.py:3772    merged["edges"] = _dedupe_edges(merged["edges"])
watch.py:1479  "nodes": _dedupe_nodes(result.get("nodes", []))
watch.py:1480  "links": _dedupe_edges(result.get("edges", []))
```

with `graphify.build.dedupe_edges` documented as collapsing exact parallel edges by `(source, target, relation)` and restoring idempotency across build modes (upstream issue #1317). **The owner never applies that dedup, so its validator is stricter than the API contract it consumes.**

---

## 4. Proof the correction terminates

Applying the three corrections in upstream's own order — real backend, real validator, real corpus, no graph write (`tmp/graphify_three_layer_fix_proof.py`):

| Stage | Result |
|---|---|
| Fresh nodes in | 972 |
| File-owned nodes kept | 898 |
| Stub ids base already owns → dropped (base wins) | 59 |
| Genuinely new shared stubs kept | 15 |
| Selected sources omitted | **0** |
| Fresh edges in → after upstream dedupe | 3,495 → 3,218 (277 removed) |
| Edges kept / unresolvable-endpoint edges dropped | 3,026 / 192 |
| Refused file-owned dangling endpoints | **0** |
| **Candidate validation** | **`ok: true`** |
| Nodes | 27,129 → **27,313** (+184) |
| Edges | 80,027 → **80,456** (+429) |

The candidate validates, grows, and does not shrink. Every existing safety refusal for real defects (foreign absolute paths, out-of-scope sources, omitted sources, ownership collisions, file-owned dangling endpoints) is preserved untouched.

---

## 5. Corroborating evidence

- **7 stage directories leaked** under `tmp/graphify-owner-stage/` (2026-09-14 → 2026-09-15), **26 files / ≈2.9 MB each (~20.6 MB total)**, and **not one contains `proof.json`**. The owner creates the stage dir and extraction cache *before* calling `merge_candidate`, then returns on refusal without cleaning up.
- **No `published_bounded_batch` anywhere** in `memory/*.md`, `state/cron-contracts/*.json`, or the maintenance packet.
- `graph.json` mtime **2026-09-07 10:21** is older than the owner's own last modification **2026-09-13 19:26**.

---

## 6. Secondary defects found

### 6.1 Refusals are unactionable
`fresh_node_foreign_source` returns no id, no `source_file`, no sample. `run_refresh` therefore logs `{"action": "...", "status": "error"}` — the exact cause required a bespoke repro to recover. Every refusal should carry bounded offending detail (id, raw value, first N paths).

### 6.2 Artifact collision between two jobs
Both jobs write the **same** path, `tmp/operational-graph-maintenance.json`:

- `Runtime - Graphify Scripts Freshness Gate` (`74ae81d7`, `--mode gate`, daily `10 23 * * *`)
- `Runtime - Graphify Scripts Incremental Refresh` (`d1f906e9`, `--mode refresh`, weekly)

The daily gate overwrites the weekly refresh packet, so refresh evidence survives less than a day. Verified: both contracts list the identical `expected_artifacts`.

### 6.3 Timeout arithmetic is wrong
`--max-seconds 600` is applied **per subprocess** — once to the stage run and again to the publish run — so worst-case wall time is **2 × 600 = 1,200 s** against a job `timeoutSeconds` of **660 s**. A slow publish would be killed mid-write by the scheduler rather than failing cleanly under owner control.

### 6.4 Chronic failure is silent
`delivery.mode: "none"` with no `failureAlert` configured means **4 consecutive failures produced no notification**. `lastFailureNotificationDeliveryStatus: "not_requested"`.

### 6.5 Backlog outruns cadence
127 changed files against `MAX_TARGETS = 25` per run means **≥5 successful weekly runs (~5 weeks)** just to catch up, during which `--mode gate` keeps reporting `refresh_due`. The refresh is structurally unable to converge after any meaningful burst of code change.

### 6.6 No regression coverage for any of the three classes
`scripts/test_graphify_incremental_owner.py` (30 tests) has no case for blank-`source_file` stubs, duplicate edges from `extract()`, or unresolvable external endpoints. The only `dangling` coverage concerns *hyperedge* members.

---

## 7. Proposed fix

Target: `scripts/lib/graphify_incremental_owner.py`, function `merge_candidate` (line 896).

**F1 — Move base-graph indices above the fresh-node loop.**
Compute `base_nodes`, `edge_slot`, `preserved_nodes`, `preserved_ids`, and a `base_index` map **before** iterating `fresh_nodes`, so stub ownership can be decided against the base.

**F2 — Treat blank `source_file` as a shared stub, not a foreign source.**

```python
raw_source = str(node.get("source_file") or "")
if not raw_source:
    node_id = node.get("id")
    if not isinstance(node_id, str) or not node_id:
        return {"ok": False, "error": "fresh_node_missing_string_id"}
    if node_id in fresh_ids:
        continue                      # exact duplicate stub
    if node_id in base_index:
        continue                      # base already owns it; base copy is preserved
    fresh_ids.add(node_id)            # genuinely new shared stub
    normalized_nodes.append(copy.deepcopy(node))
    continue
```

Shared stubs must **not** increment `emitted`, so they can never trigger `fresh_selected_source_omitted_or_empty`.
Safe by construction: base blank-source nodes have `source_file == ""`, so `_source_file(n) in target_paths` is always false and they are always preserved — "base wins" is always the correct resolution.

**F3 — Apply upstream's dedup to the fresh output.**
Reuse `graphify.build.dedupe_nodes` / `dedupe_edges` (matching `cli.py:3771–3772`), or mirror the `(source, target, relation)` key locally if the owner should not couple to `graphify.build`. This resolves `candidate_duplicate_edge` and `fresh_duplicate_node_id` together.

**F4 — Drop unresolvable external endpoints, keep refusing real breaks.**

```python
missing = [e for e in (edge.get("source"), edge.get("target")) if e not in known]
if missing:
    if any(m in base_index and str(base_index[m].get("source_file") or "") for m in missing):
        return {"ok": False, "error": "fresh_edge_dangling_refused",
                "edge": {...}, "missing": missing}      # real integrity failure
    continue                                             # external/stdlib symbol
```

**F5 — Add the bounded detail to every refusal** (§6.1).

**F6 — Clean up the stage directory on refusal**, or move the `mkdir` after merge, so a refused run cannot leak ~2.9 MB (§5).

**F7 — Separate the gate and refresh packets** (§6.2): give refresh its own artifact (e.g. `tmp/operational-graph-refresh.json`) or a distinct `mode` section the gate does not overwrite.

**F8 — Fix the timeout budget** (§6.3): pass one overall deadline and split it across stage/publish, or raise the job `timeoutSeconds` above the true worst case.

**F9 — Add regression tests** (§6.6) for all three classes, plus a test that a file-owned dangling endpoint still refuses.

---

## 8. Enhancements

| # | Enhancement | Why |
|---|---|---|
| E1 | **Failure alert route** on `d1f906e9` (currently `delivery.mode: none`, no `failureAlert`) | 4 consecutive failures went unnoticed (§6.4) |
| E2 | **Backlog catch-up mode**: `--batches N` loop, or daily cadence until `outcome == "published"` | 25/run vs 127 changed cannot converge (§6.5) |
| E3 | **Emit `resolved_batch_count` / `remaining_changed_count`** in the refresh packet | Makes convergence measurable instead of inferred |
| E4 | **Surface `consecutiveErrors` and last-success age** in the daily gate output | The gate reports graph staleness but not that repair itself is broken |
| E5 | **Retire leaked stage dirs** under a bounded, owner-approved cleanup | ~20.6 MB of orphaned evidence already accumulated |
| E6 | **Record `owner_version` + `graphifyy` version in the refresh packet** | The contract pins `SUPPORTED_GRAPHIFY = 0.9.45`; drift should be explicit |
| E7 | **Health-check the merge preconditions** (stub tolerance, dedup availability) in preflight | Turn a 72-second refusal into an instant, actionable preflight result |

---

## 9. Verification plan for the implementer

1. `python -m pytest scripts/test_graphify_incremental_owner.py` — all existing 30 tests plus new F9 cases pass.
2. `python scripts/lib/graphify_incremental_owner.py --mode stage --source-root scripts --graph scripts/graphify-out/graph.json --manifest scripts/graphify-out/manifest.json --stage-dir <fresh-dir>` → expect `outcome: "staged"` and a written `proof.json`.
3. `python scripts/memory_graph_maintenance.py --mode refresh --max-seconds 600 --write --validate` → expect `status` `ok`/`warning` and `publication: "published_bounded_batch"`.
4. `python scripts/lib/graphify_router.py health --graph scripts` → expect `fresh`.
5. Confirm `scripts/graphify-out/graph.json` mtime advances and node/edge counts do not shrink versus the 27,129 / 80,027 baseline.

Gate order matters: do **not** run the refresh from this proposal alone. It writes derived graph state and should go through the contract's own lane/lease path with Main acceptance.

---

## 10. Scope of what was done here

**Read-only diagnosis.** Probes read the graph, manifest, packet, cron state, and the pinned `graphify` package. Two bounded scratch scripts were left for reproduction:

- `tmp/graphify_three_layer_fix_proof.py` — the end-to-end three-layer proof
- `tmp/graphify_dup_ab_probe.py` — the no-context A/B that isolates Layer 3
- `tmp/graphify-fresh-extraction-20260914.json` — cached fresh extraction (1.2 MB)

**Not done, correctly:** no write to `graph.json` or `manifest.json`; no cron schedule or state mutation; no contract edit; no config/auth/runtime change; no deletion of the leaked stage dirs; no implementation of §7 without owner approval.

---

*Diagnosis performed with the real `graphifyy 0.9.45` backend and the owner's own validators. Every count in this document is reproducible from the three scripts listed in §10.*
