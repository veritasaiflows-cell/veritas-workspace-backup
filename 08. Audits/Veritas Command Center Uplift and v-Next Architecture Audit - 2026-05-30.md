# Veritas Command Center — Uplift & v-Next Architecture Audit

- **Date:** 2026-05-30 (America/Phoenix)
- **Author:** Veritas (main session)
- **Scope:** `tmp/veritas-command-center.html` and its generation pipeline; how to uplift it to a new version that leverages the current workspace (SQL artifact index, normalized finance state, DB lifecycle registry, WF77 routing) and new efficiencies.
- **Type:** Review-only architecture audit. No code changed, no canon/portfolio mutation, no execution authority. All recommendations require owner approval before implementation.
- **Boundary inheritance:** Every recommendation below preserves the Command Center's standing rules — *derived operating surface, never canonical truth; no canonical note mutation; no trade/deployment/paper/live execution authority; owner notes remain truth owners.*

---

## 1. Executive verdict

The Command Center is **functionally healthy but structurally heavy**. The view layer, boundary discipline, and truth-contract coverage are good. The problem is the **payload**: a 2.7 MB self-contained HTML file in which **~80% of the bytes are audit/proof metadata** (`trust`, `sql_canon`, `history`) that a human never reads at a glance, **pretty-printed** into the file on every render, and **re-read from ~20 loose `tmp/` JSON files** that the newer SQL artifact index already holds in indexed, microsecond-readable, deduplicated form.

**Rating of the current build: B / 7.0.** Solid surface, outgrown payload — the same "scaffolding heavier than the cargo" pattern seen elsewhere in the OS.

**The uplift is high-leverage and low-risk:** two changes (minify the embed; move proof metadata out of the client payload) cut the file from **2.7 MB → ~0.4 MB (-85%)** with zero behavior change and zero boundary change. The deeper v-next (SQL-backed sourcing + stable path + lifecycle label) removes fragility and aligns the Command Center with the workspace it now lives in.

---

## 2. How it works today (verified pipeline)

```
generate_dashboard.py  (entrypoint)
  └─ load_sources()                     reads ~20 loose tmp/*.json + a few .md notes
  └─ build_payload()  [dashboard_payload.py, 2,437 lines]
        assembles 40 top-level keys → payload dict
  └─ writes:  dashboard-data.json (2.6 MB / 60,180 lines, indent=2)
              dashboard-delta.json   (delta vs dashboard-last.json)
              dashboard-validation.json
  └─ inject_into_template():
        dashboard-template.html (262-line shell, 13 tabs)
        + dashboard-styles.css (21 KB, inlined as <style>)
        + dashboard-js/*.js  (19 files, 77 KB, concatenated, inlined as <script>)
        + %%DASHBOARD_DATA%% ← json.dumps(payload, indent=2)   ← PRETTY-PRINTED
        + %%DASHBOARD_DELTA%% ← json.dumps(delta, indent=2)
  └─ writes: veritas-command-center.html  (2.7 MB / 62,058 lines)
```

The view layer is pure client-side JS rendering from a single inlined `const DATA = {...}`. The file is **self-contained and offline-openable** — that portability is the one genuine virtue of the current design, and the uplift should preserve it.

**Source coupling:** the generator reads loose JSON directly — `run-summary-*.json`, `trigger-sheet.json`, `post-earnings-prep.json`, `band-proposals.json`, `macro-regime.json`, `universe-consistency.json`, `deployment-history.json`, the `alpaca-paper-readiness/*` set, `research-freshness-opportunity-review.json`, plus `05. Intelligence/Weekly Positioning Review.md`, and the bounded `veritas-canon-cache.sqlite` Phase-4A read. This predates the SQL artifact index and never migrated to it.

---

## 3. Findings (evidence-backed)

### F1 — Payload is 80% audit metadata, pretty-printed into the client (CRITICAL / efficiency)
Measured top-level key sizes (serialized bytes, total 2,067,655):

| Key | Bytes | % of payload | Nature |
|---|---:|---:|---|
| `trust` | 657,765 | 31.8% | provenance/trust-source audit metadata |
| `sql_canon` | 640,493 | 31.0% | SQL canon-cache proof metadata (a *degraded-fallback* surface) |
| `history` | 353,093 | 17.1% | deployment time-series |
| `fundamental_trends` | 112,167 | 5.4% | display |
| `technical` | 87,309 | 4.2% | display |
| `deployment_records` | 73,292 | 3.5% | display |
| (34 more keys) | ~144,000 | ~7.0% | display |

`trust + sql_canon + history` = **1,575,204 bytes (~76% of the payload, ~1.5 MB)** of evidence/audit data embedded into the at-a-glance surface. `sql_canon` alone — 640 KB — is proof metadata for a cache the boundary explicitly marks `degraded_fallback_required` / review-only; it does not need to ship to the browser at all.

### F2 — The inline embed is pretty-printed (HIGH / trivial fix)
`generate_dashboard.py:29` → `json.dumps(payload, indent=2)`. The 60,180-line / 62,058-line file exists because a machine-only blob is human-formatted. No human reads the inlined constant.

**Measured savings on the *current* payload, no data change:**
- Current inline (indent=2): **2,627,645 bytes / 60,180 lines**
- Minified (same data): **1,968,072 bytes / 1 line → −25% (≈660 KB)**
- Minified **+ proof keys removed from client**: **392,868 bytes → −85% vs current**

### F3 — Full payload re-embedded every render despite an existing delta mechanism (MEDIUM)
The pipeline already computes `dashboard-delta.json` against `dashboard-last.json`, but the **entire** payload is still inlined each render. The delta is carried but not used to reduce the client weight. The heavy proof sections are re-serialized in full even when unchanged.

### F4 — Generator reads ~20 loose JSON files; the SQL artifact index already holds much of it (HIGH / fragility)
The newer `tmp/veritas-artifact-index.sqlite` (verified this session) already contains, indexed: `daily_review_objects` (71), `capital_recommendations` (22), `market_events` (176), `source_artifacts` (81), `source_freshness_rows` (20), `deployment_readiness_rows` (10), `authority_flags` (506). The normalized `finance-intelligence-state.sqlite` holds the 42-ticker `universe / latest_price_technical / entry_stop_reference / fundamental_snapshot / analyst_snapshot / earnings_calendar / card_registry`. The Command Center re-derives this from loose JSON instead — the exact "six surfaces to answer one question" fragility the 2026-05-20 efficiency audit flagged. SQL reads are microsecond-fast (benchmarked this session); the only per-call cost is ~370 ms Python startup, which a single generation run pays once regardless.

### F5 — No stable output path; not lifecycle-labeled (MEDIUM)
The Command Center is written to `tmp/veritas-command-center.html` with no stable, linkable path — flagged in the 2026-05-20 audit ("lives in `tmp/` … has no stable path") and still true. With the **DB lifecycle registry** now in place (built 2026-05-30), this HTML and its `dashboard-*.json` siblings are unlabeled `live-derived` artifacts that should be classified and given a durable home.

### F6 — Inherited truth-contract gaps still open (MEDIUM, carryover)
From the 2026-05-09 alignment audit and WF44 (partial): the **LMT-style dual-layer owner-state vs technical-risk** rendering remains deferred, and the **post-close authority-vocabulary contradiction** (`canonical_mutation_allowed` true in some summary writes, false in others) was flagged HIGH and should be confirmed closed. An uplift is the right moment to fold these in with acceptance tests so they cannot silently regress.

---

## 4. New efficiencies available to leverage

These did not exist (or were not mature) when the Command Center pipeline was written:

1. **SQL artifact index** (`veritas-artifact-index.sqlite`) — derived, review-only, microsecond indexed reads. Natural backing store for `daily_review_objects`, `capital_recommendations`, `market_events`, `source_freshness`, `deployment_readiness`, `authority_flags`, and the entire `trust`/provenance section. **Authority fit is exact:** the index is already "derived/no-canon/no-apply," identical to the Command Center's own boundary — so sourcing from it changes nothing about trust posture.
2. **Normalized finance state** (`finance-intelligence-state.sqlite`) — single normalized source for the technical/deployment/fundamental/earnings tables, replacing several loose JSON reads.
3. **DB lifecycle registry** (`db_lifecycle_manifest.py`, 2026-05-30) — gives the Command Center artifacts a labeled lifecycle (`live-derived`) and a re-runnable validator, ending the "unlabeled tmp residue" status.
4. **WF77 routing surfaces** (coverage registry, ticker cards, `finance_intelligence_state.py`, `artifact_index.py` answer/coverage commands) — already the canonical finance-question route; the Command Center should consume the same routes rather than parallel JSON.
5. **Measured latency profile** — proves SQL sourcing is effectively free; the optimization target is payload bytes and file-read fan-out, not query speed.

---

## 5. Proposed v-Next architecture ("Command Center v2")

**Design principle:** keep the portable single-file surface; split the payload by *purpose*, and source structured data from the canonical SQL index with JSON fallback (preserving fail-soft).

1. **Tier the payload into core vs proof.**
   - **Core decision payload** (inlined, minified): `today_action`, `deployment_records`, `technical`, `portfolio`, `macro_regime`, `decision_queue`, `earnings`, `reference_bands`, `trigger_sheet`, `source_freshness` summary, `validation`. → ~400 KB minified.
   - **Proof/audit payload** (`trust`, `sql_canon`, `history`): moved to a sibling `dashboard-proof.json` (or served from the SQL index), loaded **on demand** when the user opens a "Trust / Provenance" drawer. Removes ~1.5 MB from the default load.
2. **Minify the inline embed** (`indent=2` → compact separators). Immediate −25%, zero risk; combined with tiering → −85%.
3. **Source structured sections from SQL** (`artifact_index.py` / `finance_intelligence_state.py`) with the existing loose-JSON path as fail-soft fallback. One indexed read per section instead of N loose-file reads; de-dupes the `trust` provenance that currently balloons the payload.
4. **Use the existing delta** to drive an "what changed since last render" ribbon instead of only being written to disk.
5. **Stable path + lifecycle label.** Emit to a stable location, label both the HTML and `dashboard-*.json` as `live-derived` in the DB lifecycle registry, and register the route in `TOOLS.md` / Active Workflows so it is discoverable.
6. **Fold in the open truth-contract gaps** (F6) with acceptance tests in `test_dashboard_acceptance.py`.

**Explicitly preserved:** single-file portability remains available (proof drawer can fall back to inlined if offline); derived-not-canonical footer; review-only language; no execution/mutation authority; owner-note truth ownership; the WF63 forbidden-phrase shape validator.

---

## 6. Phased uplift plan (proposed; owner-gated)

| Phase | Change | Risk | Payoff | Reversible |
|---|---|---|---|---|
| **P1** | Minify inline embed (`generate_dashboard.py:29-30`) | Trivial | −25% size, −60K lines | Yes (1-line) |
| **P2** | Move `trust`/`sql_canon`/`history` to on-demand `dashboard-proof.json` + drawer | Low | −85% default load (2.7 MB→~0.4 MB) | Yes |
| **P3** | Re-source `daily_review_objects`, `capital_recommendations`, `market_events`, `source_freshness`, `deployment_readiness` from SQL artifact index w/ JSON fallback | Medium | Removes file fan-out fragility | Yes (fallback retained) |
| **P4** | Stable output path + lifecycle label + routing registration | Low | Discoverable, labeled | Yes |
| **P5** | Close LMT dual-layer + authority-vocabulary gaps + acceptance tests | Medium | Truth-contract completeness | Yes |

Recommended start: **P1 + P2** as one bounded slice — together they deliver the entire 85% size win, are fully reversible, change no displayed data, and touch no boundary. P3–P5 are separate slices.

---

## 7. Acceptance criteria for the uplift

- Rendered Command Center shows **identical decision content** before/after P1–P2 (diff the rendered DOM/data, not the file bytes).
- `test_dashboard_acceptance.py` passes at ≥ current count; new tests added for P5 gaps.
- Default HTML load ≤ 0.5 MB; proof drawer loads full provenance on demand.
- All boundary flags unchanged: `canonical_note_mutation_allowed=false`, `trade_execution_allowed=false`, `deployment_state_mutation_allowed=false`, WF63 forbidden-phrase validator still rejects.
- SQL-sourced sections fall back cleanly to loose JSON when the index is stale/missing (fail-soft preserved; no silent blanks).
- DB lifecycle validator classifies the new artifacts without error.

---

## 8. Appendix — measurements (2026-05-30)

- Current HTML: **2,795,329 bytes (~2.7 MB), 62,058 lines**.
- Inlined data (indent=2): 2,627,645 bytes / 60,180 lines.
- Minified same payload: 1,968,072 bytes (−25%).
- Minified + proof keys removed: 392,868 bytes (−85%).
- Proof metadata removed: 1,575,204 bytes (`trust` 657,765 + `sql_canon` 640,493 + `history` 353,093 ... using top-3 heavy keys).
- View layer: CSS 21,313 bytes; JS 19 files / 79,565 bytes.
- Generator: `dashboard_payload.py` 2,437 lines; template 262 lines; acceptance tests 1,639 lines.
- SQL backing already available: artifact index (`daily_review_objects` 71, `capital_recommendations` 22, `market_events` 176, `source_artifacts` 81, `authority_flags` 506, `source_freshness_rows` 20, `deployment_readiness_rows` 10); finance state (42-ticker normalized).

---

*Review-only audit. Implementation of any phase requires Randall's approval. No phase may grant the Command Center canonical, portfolio, execution, paper/live, or owner-approval authority.*
