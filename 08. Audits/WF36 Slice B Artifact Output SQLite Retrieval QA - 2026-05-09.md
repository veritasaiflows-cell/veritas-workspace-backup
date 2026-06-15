# WF36 Slice B Artifact Output SQLite Retrieval QA - 2026-05-09

## Audit verdict

**Closed with follow-up** as an independent audit verdict only. Main session retains final closeout authority.

Slice B is useful and safe to keep as a **manual-only derived retrieval helper**. It should **not yet be wired into a finance chain** until the follow-up items below are closed with a fail-soft integration proof. I did not find unsafe path indexing, secret/config exposure, canonical note mutation, queue movement, deployment authorization, or portfolio-state authority in the live implementation.

## Scope audited

Audited `scripts/artifact_index.py` and `scripts/test_artifact_index.py` against the WF36 Slice B contract:

- build `tmp/veritas-artifact-index.sqlite` from current market-intelligence and daily-review JSON packets only
- preserve SQL/SQLite as derived/cache-only retrieval support
- keep source JSON artifacts and canonical notes authoritative
- avoid queue, registry, portfolio, deployment, trade, config, credential, runtime, or note-layer mutation
- assess correctness, trust boundaries, usefulness, validation coverage, and closeout readiness

## Files inspected

Required files:

- `SOUL.md`
- `AGENTS.md`
- `TOOLS.md`
- `06. Playbooks/Project Continuity/Workflow 36 - Workspace Retrieval Index and SQLite Knowledge Layer.md`
- `06. Playbooks/Operating Procedures/SQLite Retrieval Index Procedure.md`
- `06. Playbooks/Spawn and Closeout Governance Matrix.md`
- `06. Playbooks/Workflow Closeout Artifact Standard.md`
- `scripts/artifact_index.py`
- `scripts/test_artifact_index.py`
- `scripts/README.md`
- `memory/2026-05-09.md`

Additional control-surface / adjacent evidence inspected:

- `06. Playbooks/IC Project Registry.md`
- `06. Playbooks/OpenClaw Parallel Pilot Queue.md`
- `06. Playbooks/Project Continuity/Workflow 10 - Subagent Session Lifecycle Reliability Review.md`
- `scripts/market_data_utils.py` JSON loader excerpt
- `.gitignore`
- live generated DB metadata from `tmp/veritas-artifact-index.sqlite`
- early checkpoint written to `09. Archive/Tmp Referenced Archive Candidates - Archived/2026-05-17T181150Z/tmp-markdown-reports/wf36-slice-b-qa-checkpoint.md`

## Contract reconstruction

WF36 Slice B is a bounded follow-up to the SQLite retrieval layer. The live contract is explicit in the WF36 note and SQLite retrieval procedure:

- `scripts/artifact_index.py` rebuilds `tmp/veritas-artifact-index.sqlite` from `tmp/market-intelligence-events-*.json` and `tmp/daily-review-objects-*.json` only.
- SQL rows are retrieval/provenance hints, not portfolio truth.
- Retrieval hit -> open the source JSON artifact and owning note before judgment or mutation.
- No cron/chain integration until manual usefulness is proven and the owning workflow records fail-soft behavior.

Evidence:

- `scripts/artifact_index.py:17-18` limits source globs to market-intelligence and daily-review artifact names.
- `scripts/artifact_index.py:45-49` discovers files only under `tmp/` using those globs.
- `06. Playbooks/Project Continuity/Workflow 36 - Workspace Retrieval Index and SQLite Knowledge Layer.md:29` states the artifact-output index is derived/cache-only and subordinate to source JSON and canonical notes.
- `06. Playbooks/Operating Procedures/SQLite Retrieval Index Procedure.md:42-48` requires opening source files after SQL hits and blocks cron/chain integration until fail-soft behavior is recorded.
- `scripts/README.md:263-287` documents the script as a live derived retrieval index and says it is not wired into `chain_manifest.py` yet.

## Validation run

Commands run from `C:\Users\Veritas\.openclaw\workspace`:

| Check | Result | Evidence |
|---|---:|---|
| `python -m py_compile scripts\artifact_index.py scripts\test_artifact_index.py` | Pass | exited 0, no output |
| `python scripts\test_artifact_index.py` | Pass | `artifact_index_tests_passed` |
| `python scripts\artifact_index.py rebuild` | Pass | `source_files=7 runs=7 market_events=92 daily_review_objects=51 capital_recommendations=13` |
| `python scripts\artifact_index.py latest --limit 5` | Pass | returned cross-artifact escalation rows with source timestamps |
| `python scripts\artifact_index.py ticker ETN --limit 10` | Pass with usefulness caveat | returned ETN market events, daily review objects, and capital recommendation rows, but with duplicate-looking rows because list provenance is hidden in printed output |
| `python scripts\artifact_index.py capital --limit 10` | Pass | returned 10 owner-gated capital recommendation rows; all shown with `owner_approval_required=1` |
| `python scripts\artifact_index.py trust --limit 10` | Pass | returned 7 artifact runs; all shown as `review_only`, `canonical_mutation_allowed=0`, `owner_review_required=1` |
| `python scripts\artifact_index.py window post-close --limit 5` | Pass | returned the post-close market-intelligence and daily-review source artifacts |
| SQLite trust query over item-level flags | Pass | `unsafe_market_events=0`, `unsafe_daily_reviews=0`, `unsafe_capital_recs=0` |
| SQLite keyword scan for obvious config/secret/runtime strings in raw indexed JSON | Pass | 0 hits for `.openclaw`, `openclaw.json`, `credential`, `token`, `api_key`, `secret` |
| `python scripts\workspace_boundary_check.py` | Warning, unrelated existing residue | 11 findings: root `backups/` and old executable helpers under `tmp/`; no new stop-line finding for Slice B |
| `python scripts\dashboard_truth_lint.py` | Pass | `status: ok`, 0 findings |

Validation limitation: `git` is not available on this host (`git` command not recognized), so I could not use `git status` to prove whether the generated DB is currently untracked. Direct `.gitignore` inspection still shows the ignore-pattern gap below.

## Top findings

### 1. Generated artifact DB is documented but not ignored like the existing workspace SQLite cache

- **Severity:** Medium before closeout hygiene / low for manual runtime safety
- **Evidence/source file:**
  - `.gitignore:6` ignores `tmp/workspace-index.sqlite*` but has no matching `tmp/veritas-artifact-index.sqlite*` entry.
  - `scripts/README.md:280-281` documents `tmp/veritas-artifact-index.sqlite` and possible `-wal` / `-shm` sidecars.
  - live filesystem check showed `tmp/veritas-artifact-index.sqlite` exists after rebuild.
- **Why it matters:** This DB is explicitly derived/cache-only. If the file or WAL/SHM sidecars are not ignored, the workspace can accidentally preserve or version a generated cache as if it were durable evidence. That would weaken the “source JSON artifacts and notes remain authority” boundary.
- **Owner / affected surface:** WF36 retrieval layer; `.gitignore`; workspace boundary hygiene.
- **Recommended fix:** Add `tmp/veritas-artifact-index.sqlite*` to `.gitignore`. Consider teaching `scripts/workspace_boundary_check.py` to classify it the same way it already classifies `tmp/workspace-index.sqlite` as a generated SQLite retrieval cache.
- **Acceptance proof:**
  - `.gitignore` contains `tmp/veritas-artifact-index.sqlite*`.
  - `python scripts\workspace_boundary_check.py` either remains no worse than current unrelated warnings or explicitly classifies the artifact index DB as generated/cache-only.
  - A direct file check confirms DB sidecars, if present, match the ignore pattern.

### 2. Regression guard checks run-level trust flags but not all item-level authority flags

- **Severity:** Medium before chain integration; low while manual-only
- **Evidence/source file:**
  - `scripts/test_artifact_index.py:50` checks only `artifact_runs` for `canonical_mutation_allowed != 0 OR owner_review_required != 1`.
  - `scripts/artifact_index.py:215-223` stores item-level `owner_review_required`, `canonical_mutation_allowed`, and `trade_execution_allowed` for `market_events`.
  - `scripts/artifact_index.py:234-243` stores item-level `owner_review_required` for `daily_review_objects`.
  - `scripts/artifact_index.py:255-261` stores item-level `owner_approval_required` for `capital_recommendations`.
  - Live ad hoc SQLite trust query passed: 0 unsafe market events, 0 unsafe daily reviews, 0 unsafe capital recommendations.
- **Why it matters:** The current source data is safe, but the formal test would not fail if a future source artifact accidentally emitted a market event with `trade_execution_allowed=true`, a daily review object with `owner_review_required=false`, or a capital recommendation with `owner_approval_required=false`. That is exactly the kind of boundary regression this index should refuse to normalize.
- **Owner / affected surface:** `scripts/test_artifact_index.py`; future fail-soft chain proof.
- **Recommended fix:** Extend the regression guard to assert:
  - `market_events.canonical_mutation_allowed = 0`
  - `market_events.trade_execution_allowed = 0`
  - `market_events.owner_review_required = 1`
  - `daily_review_objects.owner_review_required = 1`
  - `capital_recommendations.owner_approval_required = 1`
- **Acceptance proof:** `python scripts\test_artifact_index.py` fails on a controlled unsafe fixture or mutation and passes on the current live artifacts. At minimum, the live test should include the same item-level SQL query used in this audit.

### 3. Ticker query is useful but can present duplicate-looking rows because list provenance is indexed but not shown

- **Severity:** Low / usefulness follow-up
- **Evidence/source file:**
  - `scripts/artifact_index.py:278-285` indexes both full lists and escalation lists: `("events", "escalations")` and `("review_objects", "escalations")`.
  - `scripts/artifact_index.py:352-379` `query_ticker` unions market events, daily review objects, and capital recommendations but does not project `list_name` or `source_file`.
  - Live `python scripts\artifact_index.py ticker ETN --limit 10` returned duplicate-looking ETN daily review rows and repeated market-event rows with the same title/timestamp.
- **Why it matters:** This does not corrupt the cache, because `list_name` exists in the tables and the source JSON remains authoritative. But the CLI output is a human retrieval surface. Duplicate-looking rows can make an operator overcount signal strength or waste time reconstructing provenance.
- **Owner / affected surface:** `scripts/artifact_index.py` query presentation; operator usefulness.
- **Recommended fix:** Add `source_file` and `list_name` to `latest` / `ticker` output, or de-duplicate identical source item IDs while preserving an `escalated` marker. The smaller safe patch is to expose `source_file` and `list_name` first.
- **Acceptance proof:** `python scripts\artifact_index.py ticker ETN --limit 10` shows enough provenance to distinguish full-list rows from escalation rows, or returns one row per logical item with an explicit escalation indicator.

### 4. Current query layer exposes timestamps but does not compute freshness status for finance decision use

- **Severity:** Medium for capital-deployment readiness; low for manual retrieval
- **Evidence/source file:**
  - `scripts/artifact_index.py:410-422` `query_trust` prints `generated_at_utc` and `file_mtime_utc` but no age/freshness classification.
  - Live trust output showed all seven indexed artifacts generated on `2026-05-08`, while this audit ran on `2026-05-09`.
  - `06. Playbooks/Operating Procedures/SQLite Retrieval Index Procedure.md:23-27` tells operators to rebuild if freshness matters, but rebuilding the index does not refresh stale source artifacts.
- **Why it matters:** A fresh SQLite rebuild can faithfully index stale upstream finance artifacts. For manual use, timestamps are visible enough if the operator reads them. For chain integration or capital-deployment readiness, a consumer needs an explicit fail-soft stale-source rule so a fresh DB timestamp cannot be mistaken for fresh market intelligence.
- **Owner / affected surface:** future integration pass; `scripts/artifact_index.py` trust query or downstream chain consumer.
- **Recommended fix:** Before any chain integration, add a small freshness summary or consumer-side gate that distinguishes `indexed_at_utc` from source `generated_at_utc` / `file_mtime_utc`, and fails soft when source packets are stale for the intended window.
- **Acceptance proof:** A controlled stale source artifact produces an explicit warning / degraded status and does not allow a downstream chain step to treat capital recommendations as current.

## Closed / satisfactory items

- **Source scope is bounded.** `iter_artifact_paths()` uses only `tmp/market-intelligence-events-*.json` and `tmp/daily-review-objects-*.json`.
- **No canonical mutation path found.** The script writes only the SQLite DB/cache under `tmp/`; it does not edit Markdown notes, portfolio files, queues, registry state, config, credentials, runtime files, or accounts.
- **SQLite implementation is reasonable for this cache role.** It uses stdlib SQLite, WAL, `busy_timeout`, foreign keys, strict tables, explicit indexes, a rebuild transaction, and `PRAGMA optimize`.
- **Trust boundary is visible in output.** `trust`, `window`, and `capital` queries expose review-only / owner-gated fields; live data returned `canonical_mutation_allowed=0`, `owner_review_required=1`, and `owner_approval_required=1` where expected.
- **Documentation is aligned.** WF36, the SQLite retrieval procedure, and `scripts/README.md` all preserve source-file authority and block premature chain integration.
- **Control surfaces agree on state.** Queue and registry both describe Slice B as implemented with manual proof but still needing QA/closeout before fail-soft chain integration.

## Manual-only vs integration posture

- **Safe to remain manual-only:** Yes. The index is useful as a locator for artifact runs, escalations, ticker/sleeve hits, capital recommendation objects, and trust/freshness timestamps.
- **Safe for fail-soft chain integration now:** Not yet. The code is close, but integration should wait until the generated DB ignore pattern, item-level trust regression guard, provenance clarity, and stale-source fail-soft rule are closed or explicitly accepted as non-blocking by main.
- **Blocked from integration entirely:** No. I did not find a design flaw that requires abandoning this layer. Future integration can be safe if kept fail-soft, read-only, and subordinate to source artifacts.

## Recommended next bounded passes

1. **WF36 Slice B hardening micro-pass**
   - Patch `.gitignore` for `tmp/veritas-artifact-index.sqlite*`.
   - Extend `scripts/test_artifact_index.py` to assert item-level owner/trade/canonical gates.
   - Add `source_file` / `list_name` to ticker/latest CLI output or otherwise de-duplicate with provenance.
   - Acceptance: compile + test + manual `ticker ETN` and `trust` queries show clearer provenance and stronger authority guard coverage.

2. **Fail-soft consumer design pass for WF41/WF42 readiness**
   - Define how market-intelligence / daily-review chain steps may optionally rebuild or query this index without depending on it.
   - Require stale-source degradation and source artifact open/read before any finance judgment.
   - Acceptance: a missing DB, stale source artifact, or rebuild failure produces a warning/degraded retrieval state, not a blocked finance chain and not a deployment authorization.

These tighten finance decisions and capital-deployment readiness without widening authority.

## Reopen triggers

Reopen WF36 Slice B or a bounded successor if any of these occur:

- `artifact_index.py` is wired into `chain_manifest.py` or a scheduled chain.
- The source artifact contract for `market_intelligence_event_router.py` or `daily_review_objects.py` changes materially.
- SQL rows are cited as closeout proof, queue authority, portfolio truth, or deployment authorization without opening source artifacts.
- The index begins storing broader `tmp/`, runtime, config, credential, or note-layer content.
- Operators repeatedly rely on ticker/latest output and duplicate-looking rows create decision confusion.

## Intentionally deferred items

- No canonical finance notes, portfolio/deployment/watchlist notes, queue state, registry state, OpenClaw config, credentials, runtime files, or script code were edited.
- I did not audit the full source correctness of `market_intelligence_event_router.py` or `daily_review_objects.py`; this pass only verified how their current JSON outputs are indexed.
- I did not attempt git tracking proof because `git` is unavailable in this runtime.
- I did not recommend folding this into `scripts/workspace_index.py` now; the separate index is acceptable while it remains small, documented, derived, and manually invoked.

## Main-session follow-up fixes after audit

Status: three audit findings were closed directly by main-session micro-fix; stale-source fail-soft classification remains follow-up before chain integration.

Closed fixes:
- Added `tmp/veritas-artifact-index.sqlite*` to `.gitignore` so the generated cache and WAL/SHM sidecars remain non-canonical generated artifacts.
- Extended `scripts/test_artifact_index.py` with item-level authority checks for market events, daily review objects, and capital recommendations.
- Added `source_file` and `list_name` provenance columns to `latest` and `ticker` CLI output in `scripts/artifact_index.py`; documented this in `scripts/README.md`.

Follow-up still open:
- Add stale-source fail-soft classification before any `chain_manifest.py` or scheduled-chain integration. A fresh DB rebuild can still index stale upstream finance artifacts faithfully, so freshness judgment must remain explicit.

Post-fix validation:
- `python -m py_compile scripts\artifact_index.py scripts\test_artifact_index.py` passed.
- `python scripts\test_artifact_index.py` passed.
- `python scripts\artifact_index.py latest --limit 5` passed and now displays `source_file` / `list_name`.
- `python scripts\artifact_index.py ticker ETN --limit 10` passed and now distinguishes `review_objects`, `escalations`, `events`, and `capital_deployment_recommendations` rows.
- `python scripts\artifact_index.py trust --limit 10` passed.
- `python scripts\workspace_boundary_check.py` returned existing unrelated warnings only; no Slice B stop-line issue surfaced.
- `python scripts\dashboard_truth_lint.py` passed with 0 findings.
