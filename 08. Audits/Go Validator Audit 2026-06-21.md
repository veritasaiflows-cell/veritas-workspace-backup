# Go Validator Layer Audit — 2026-06-21

**Auditor:** Veritas (main session)
**Scope:** All Go validators under `scripts/go/`, binary freshness, test coverage, gap analysis vs. SQL-first / Canon / JSON proof posture
**Authority:** Read-only audit. No code/config/runtime mutation.

---

## 1. Executive Summary

**Grade: A-**

The Go validator layer is mature, well-structured, and correctly bounded. 17 commands, 16 internal packages, all tests passing, 0 stale binaries, 0 critical findings. The layer correctly serves as a read-only proof edge while Python remains the workflow spine.

**Key strengths:**
- Clean shared toolkit (`internal/reporting`, `internal/sqlutil`) eliminating per-command duplication
- Comprehensive boundary lint coverage (WF74, WF75, finance-SQL, Python-SQL contract)
- Full SQL schema drift and proof probe pipeline across 8 databases
- Source-truth parity validation between Markdown owner notes and SQL mirrors
- Consumer authority guard with fail-closed fallback design
- In-process SQLite driver proof with read-only enforcement

**Key gaps (10 identified):**
1. JSON proof packet structural validator
2. Entry/stop band freshness validator (Go companion)
3. Cron contract payload authority lint
4. PM queue authority and staleness lint
5. Finance answer packet completeness validator
6. Cross-DB referential integrity probe
7. Workflow artifact freshness gate
8. Validator timing benchmark (Go-native)
9. Portfolio note / Execution Board structural lint
10. Paper trading guard preflight

---

## 2. Current Inventory

### 2.1 Commands (17)

| Command | Type | Status | Checks | Critical | Warnings |
|---------|------|--------|--------|----------|----------|
| `finance-sql-boundary-lint` | boundary | ok | 43 | 0 | 0 |
| `python-sql-contract-lint` | boundary | warning | 491 | 0 | 14 |
| `sql-schema-drift-lint` | schema | ok | 82 | 0 | 0 |
| `sql-proof-probe` | schema | ok | 82 | 0 | 0 |
| `go-source-truth-parity-validator` | parity | ok | phase2 | 0 | 0 |
| `go-sql-consumer-authority-guard` | authority | ok | 15 | 0 | 0 |
| `go-sql-500-expansion-design-gate` | gate | ok | — | 0 | 0 |
| `wf74-boundary-lint` | boundary | ok | 13 | 0 | 0 |
| `wf75-smb-boundary-lint` | boundary | ok | — | 0 | 0 |
| `go-sql-latency-probe` | perf | ok | — | 0 | 0 |
| `go-sql-inventory-helper` | inventory | ok | — | 0 | 0 |
| `go-sql-source-truth-manifest` | manifest | ok | — | 0 | 0 |
| `go-finance-data-coverage-probe` | coverage | ok | — | 0 | 0 |
| `go-finance-human-notes-sql-check` | check | ok | — | 0 | 0 |
| `go-finance-universe-validation-probe` | validation | ok | — | 0 | 0 |
| `go-wf78-sql-phase2-readiness-probe` | readiness | ok | — | 0 | 0 |
| `go-sql-inprocess-readonly-probe` | driver | ok | 4 | 0 | 0 |

### 2.2 Internal Packages (16)

| Package | Tests | Purpose |
|---------|-------|---------|
| `boundarylint` | ✅ | Shared boundary language scanner |
| `consumerauthority` | ✅ | SQL consumer authority guard logic |
| `durableoutputs` | — | Durable output shape validation |
| `expansiongate` | ✅ | 500-ticker expansion gate logic |
| `financecoverage` | ✅ | Finance data coverage probe |
| `financehuman` | ✅ | Human notes SQL check |
| `financesqllint` | ✅ | Finance SQL boundary lint |
| `pythonsqllint` | ✅ | Python SQL contract lint |
| `reporting` | ✅ | Shared UTC timestamps, status, JSON output |
| `schemalint` | ✅ | SQL schema drift detection |
| `smblint` | ✅ | SMB workflow boundary lint |
| `sourcetruthmanifest` | ✅ | Source truth authority manifest |
| `sourcetruthparity` | ✅ | Markdown-to-SQL parity validation |
| `sqlinventory` | ✅ | SQLite table/view inventory |
| `sqllatency` | ✅ | SQL query latency benchmarking |
| `sqlproof` | ✅ | SQL proof aggregation |
| `sqlutil` | ✅ | Shared SQLite CLI + in-process adapters |

### 2.3 Binary Freshness

```
Go binary freshness guard: status=ok, stale=0, missing=0
All 17 compiled binaries in scripts/go/bin/ are current vs. source.
```

### 2.4 Test Coverage

```
go test ./... — all 16 packages with test files: PASS (cached)
4 packages without test files: durableoutputs (utility), plus 3 cmd entrypoints
```

### 2.5 Python-Go Parity Gates (17)

All 17 Python-Go parity comparison scripts exist and validate Go output against Python reference output. The controlled demotion experiment (Go-first/Python-fallback) was rolled back to Python-owner/Go-validator-only after the 2026-06-08 benchmark showed no material Go speed advantage for the tested path.

---

## 3. Gap Analysis

### 3.1 JSON Proof Packet Structural Validator — HIGH

**What:** A Go validator that reads JSON proof artifacts and checks schema conformance, required field presence, authority boundary flags, and status vocabulary.

**Why:** The workspace has hundreds of JSON proof artifacts. Python schema validation is slow for bulk checks. Go could validate the entire proof surface in under a second.

**Current state:** No Go JSON schema validator exists. Python validators check individual artifacts but there's no bulk structural pass.

**Design:**
- Read `tmp/veritas-artifact-index.sqlite` for the artifact inventory
- For each JSON artifact, check: valid JSON parse, `status` field present and in allowed vocabulary, `authority_boundary` block present with required false flags, `generated_at_utc` or `schema` field present
- Report: total artifacts, passed, failed, by-category breakdown
- Output: `tmp/go-json-proof-structural-validator.json`

**Internal packages needed:** `internal/jsonstruct` (new) — JSON parse, schema conformance, status vocabulary check
**Command:** `go-json-proof-structural-validator`
**Estimated effort:** Small (1 new internal package, 1 new command)

### 3.2 Entry/Stop Band Freshness Validator — HIGH

**What:** A Go companion that reads `state/finance/finance-canon.sqlite` reference_levels and checks hash consistency against `03. Portfolio/Execution Board.md`.

**Why:** The entry/stop cache freshness guard is currently Python-only (`finance_intelligence_state.py` entry_stop_cache_freshness_guard). A Go companion would provide fast independent verification that the SQL reference levels match the owner Markdown source.

**Current state:** `go-source-truth-parity-validator` checks Markdown-to-SQL parity for the entry/stop table. But it doesn't check hash freshness or flag staleness — it only checks value parity.

**Design:**
- Read Execution Board.md, compute SHA-256 of the entry/stop table section
- Read `finance-canon.sqlite` reference_levels, compare stored source hash
- Flag: hash match/mismatch, stale count, fresh count, per-ticker staleness
- Output: `tmp/go-entry-stop-band-freshness-validator.json`

**Internal packages needed:** `internal/bandfreshness` (new) — hash computation, staleness classification
**Command:** `go-entry-stop-band-freshness-validator`
**Estimated effort:** Small (1 new internal package, 1 new command)

### 3.3 Cron Contract Payload Authority Lint — HIGH (Roadmap #30)

**What:** Scan cron job definitions for forbidden authority language, delivery drift, prompt bloat, and unsafe patterns.

**Why:** Listed as roadmap item #30 in `scripts/go/README.md`. Cron jobs are the most likely surface for authority drift because they run unattended. A fast Go lint pass over cron definitions would catch issues before they execute.

**Current state:** `cron_contract_validator.py` and `cron_authority_matrix_validator.py` exist in Python. No Go equivalent.

**Design:**
- Read cron job definitions from the Gateway API or from `tmp/cron-control-packet.json`
- Check each job for: forbidden action language (execute, apply, submit, delete, mutate), delivery drift (announce mode on isolated jobs that should be none), prompt bloat (payload message length), unsafe model assignments
- Output: `tmp/go-cron-contract-authority-lint.json`

**Internal packages needed:** `internal/cronlint` (new) — cron payload scanning, authority vocabulary check
**Command:** `go-cron-contract-authority-lint`
**Estimated effort:** Small (1 new internal package, 1 new command)

### 3.4 PM Queue Authority and Staleness Lint — HIGH (Roadmap #29)

**What:** Scan PM state for stale lanes, authority-widening continuation packets, and unsafe handoff language.

**Why:** Listed as roadmap item #29. PM lanes can accumulate stale state that implies authority that was never granted. A fast Go lint pass would catch these before they mislead a main-session review.

**Current state:** `pm_control_packet.py` produces the PM state. No Go consumer exists.

**Design:**
- Read `tmp/pm-control-packet.json`
- Check: lane age (stale if >24h without completion), authority language in lane descriptions, handoff packet safety, implementation queue job descriptions for forbidden actions
- Output: `tmp/go-pm-queue-authority-lint.json`

**Internal packages needed:** `internal/pmlint` (new) — PM state scanning, staleness detection, authority vocabulary
**Command:** `go-pm-queue-authority-lint`
**Estimated effort:** Small (1 new internal package, 1 new command)

### 3.5 Finance Answer Packet Completeness Validator — MEDIUM

**What:** Validate that WF85 full-answer packets have all 17 required sections, no missing sections, and correct authority boundary flags.

**Why:** WF85 is the default full-answer path. A fast Go check that every production-grade ticker has a complete answer packet would catch assembly failures before they reach a user query.

**Current state:** `full_intelligence_answer_parity.py` checks parity but is Python-only and runs per-ticker. No bulk Go check exists.

**Design:**
- Read `tmp/trade-grade-full-answer-assembler.json` for the production ticker list
- For each ticker, read `tmp/trade-grade-full-answer/<TICKER>.json`
- Check: 17 sections present, 0 missing_sections, authority_boundary flags all false, status=ok
- Output: `tmp/go-finance-answer-completeness-validator.json`

**Internal packages needed:** `internal/answercheck` (new) — section counting, boundary flag verification
**Command:** `go-finance-answer-completeness-validator`
**Estimated effort:** Small (1 new internal package, 1 new command)

### 3.6 Cross-DB Referential Integrity Probe — MEDIUM

**What:** Check that ticker sets are consistent across all SQLite databases in the finance surface.

**Why:** The workspace has 8+ SQLite databases. Ticker drift between them (e.g., a ticker in `finance-canon.sqlite` but missing from `finance-intelligence-state.sqlite`) is a silent data quality bug. Go can cross-check all DBs in one fast pass.

**Current state:** No cross-DB referential integrity check exists in any language.

**Design:**
- Read ticker lists from: `finance-canon.sqlite`, `finance-intelligence-state.sqlite`, `canonical-finance-data-plane.sqlite`, `veritas-canon-cache.sqlite`
- Report: union set, per-DB counts, tickers missing from each DB, extra tickers in each DB
- Output: `tmp/go-cross-db-referential-integrity-probe.json`

**Internal packages needed:** `internal/crossdb` (new) — multi-DB ticker set comparison
**Command:** `go-cross-db-referential-integrity-probe`
**Estimated effort:** Small (1 new internal package, 1 new command)

### 3.7 Workflow Artifact Freshness Gate — MEDIUM

**What:** Scan `veritas-artifact-index.sqlite` for stale artifacts and flag those past their refresh policy.

**Why:** `artifact_staleness_explainer.py` does this in Python but is slow for bulk scans. A Go version could run as a fast preflight before any workflow advancement.

**Current state:** Python-only. No Go equivalent.

**Design:**
- Read `tmp/veritas-artifact-index.sqlite`
- For each artifact with a refresh policy: compute age, compare to policy, flag stale
- Group by: critical (blocking), warning (aging), ok (fresh)
- Output: `tmp/go-workflow-artifact-freshness-gate.json`

**Internal packages needed:** `internal/artifactfreshness` (new) — age computation, policy comparison
**Command:** `go-workflow-artifact-freshness-gate`
**Estimated effort:** Small (1 new internal package, 1 new command)

### 3.8 Validator Timing Benchmark (Go-Native) — LOW

**What:** A Go harness that runs the full Go validator suite and reports wall-clock time per validator.

**Why:** `validator_timing_ledger.py` profiles Python validators. A Go-native equivalent would provide baseline timing for the Go edge and help identify slow validators.

**Current state:** Python `validator_timing_ledger.py` exists. No Go equivalent.

**Design:**
- Run each Go binary in sequence, capture wall-clock time
- Report: per-validator timing, total time, slowest validator
- Output: `tmp/go-validator-timing-benchmark.json`

**Internal packages needed:** None (uses `os/exec` from stdlib)
**Command:** `go-validator-timing-benchmark`
**Estimated effort:** Trivial (1 new command, no new internal packages)

### 3.9 Portfolio Note / Execution Board Structural Lint — LOW

**What:** Parse `03. Portfolio/Execution Board.md` for structural integrity — required sections present, ticker table format valid, band/stop completeness.

**Why:** The Execution Board is the canonical owner note for entry bands and stops. Structural drift (missing sections, malformed tables) would break downstream parsers silently.

**Current state:** `execution_board_canon_anchor_drift_validator.py` checks anchor drift. No structural lint exists.

**Design:**
- Parse Execution Board.md sections
- Check: required headers present, ticker table has expected columns, band/stop values are numeric, no empty required fields
- Output: `tmp/go-execution-board-structural-lint.json`

**Internal packages needed:** `internal/boardlint` (new) — Markdown section parsing, table structure validation
**Command:** `go-execution-board-structural-lint`
**Estimated effort:** Small (1 new internal package, 1 new command)

### 3.10 Paper Trading Guard Preflight — LOW

**What:** Fast Go check that paper execution preconditions are met before any paper workflow advances.

**Why:** Paper trading has strict guardrails (kill switch, paper/live isolation, credential check). A fast Go preflight that runs before any paper workflow would catch missing guards early.

**Current state:** `alpaca_paper_execution_guard_validator.py` does this in Python. No Go equivalent.

**Design:**
- Check: kill switch file exists and is not expired, paper credentials present, live credentials absent from paper path, paper position DB is paper-only
- Output: `tmp/go-paper-trading-guard-preflight.json`

**Internal packages needed:** `internal/paperguard` (new) — kill switch check, credential isolation check
**Command:** `go-paper-trading-guard-preflight`
**Estimated effort:** Small (1 new internal package, 1 new command)

---

## 4. Implementation Plan

### Phase 1 — High-Impact, Low-Effort (This Week)

| # | Validator | Effort | Rationale |
|---|-----------|--------|-----------|
| 1 | JSON proof packet structural validator | Small | Bulk validation of entire proof surface. Highest leverage. |
| 2 | Entry/stop band freshness validator | Small | Directly strengthens the finance truth surface. Complements existing parity validator. |
| 3 | Cron contract authority lint | Small | Roadmap #30. Closes a known gap. Prevents unattended authority drift. |
| 4 | PM queue authority lint | Small | Roadmap #29. Closes a known gap. Catches stale/unsafe lane state. |

### Phase 2 — Medium-Impact (Next Week)

| # | Validator | Effort | Rationale |
|---|-----------|--------|-----------|
| 5 | Finance answer packet completeness | Small | Protects WF85 answer quality. Fast bulk check. |
| 6 | Cross-DB referential integrity probe | Small | Catches silent ticker drift across SQLite surfaces. |
| 7 | Workflow artifact freshness gate | Small | Fast preflight for workflow advancement. |

### Phase 3 — Lower Priority (When Needed)

| # | Validator | Effort | Rationale |
|---|-----------|--------|-----------|
| 8 | Validator timing benchmark | Trivial | Nice-to-have profiling. No new internal packages. |
| 9 | Execution Board structural lint | Small | Defensive. Execution Board format is stable. |
| 10 | Paper trading guard preflight | Small | Python equivalent already exists and works. Go version is speed optimization only. |

### Implementation Pattern (per validator)

Each new validator follows the established pattern:

1. **Internal package** under `scripts/go/internal/<name>/` with:
   - `main logic` in a single `.go` file
   - `_test.go` with at least one table-driven test
   - Reuse `internal/reporting` for UTC timestamps, status, JSON output
   - Reuse `internal/sqlutil` if SQLite access is needed

2. **Command entrypoint** under `scripts/go/cmd/<name>/main.go` with:
   - `--root` flag for workspace root
   - `--out` flag for JSON report path
   - Status line to stdout
   - Exit code 0 on ok, 1 on blocked, 2 on runtime error

3. **Binary** built to `scripts/go/bin/<name>.exe`

4. **Python bridge** (when consumed by harness/PM/cockpit):
   - Register in `scripts/go_sql_helper_route_registry.py` if SQL-touching
   - Add to `scripts/veritas_harness_scorecard.py` if harness-gated
   - Add to `state/pm-cockpit-source-registry.json` if cockpit-visible
   - Add to `scripts/README.md` and `scripts/go/README.md`

5. **Validation:**
   - `go test ./...` must pass
   - `go build` must succeed
   - Binary must produce valid JSON output
   - `python scripts/go_binary_freshness_guard.py --write --validate` must stay green

### Build Commands

```powershell
# Build all binaries
cd scripts\go
New-Item -ItemType Directory -Force -Path bin | Out-Null
foreach ($cmd in Get-ChildItem -Path cmd -Directory | Sort-Object Name) {
  go build -o (Join-Path "bin" ($cmd.Name + ".exe")) (".\cmd\" + $cmd.Name)
  if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}

# Run all tests
go test ./...

# Verify binary freshness
cd ..\..
python scripts\go_binary_freshness_guard.py --write --validate
```

---

## 5. Architecture Assessment

### 5.1 What's Working Well

| Attribute | Grade | Evidence |
|-----------|-------|----------|
| **Shared toolkit** | A | `internal/reporting` and `internal/sqlutil` eliminate duplication. 16 packages, 0 copy-paste. |
| **Boundary discipline** | A+ | Every command carries explicit authority_boundary flags. No false authority claims found. |
| **Test coverage** | A- | 12/16 packages have tests. 4 without tests are thin entrypoints or utility packages. |
| **Binary management** | A | 17 binaries in `scripts/go/bin/`, 0 stale, 0 missing. Freshness guard is green. |
| **Python parity** | A | 17 Python-Go parity scripts. Controlled demotion experiment completed and correctly rolled back. |
| **SQLite driver** | A | Dual CLI + in-process driver with read-only enforcement. In-process probe proves write rejection. |
| **Roadmap discipline** | A | README tracks 31 roadmap items. 28 complete, 3 remaining (29, 30, 31). |
| **Correct boundaries** | A+ | Go is validator edge only. No canon generation, no SQL mutation, no PM/cron/config changes. |

### 5.2 What Needs Attention

| Issue | Severity | Detail |
|-------|----------|--------|
| **python-sql-contract-lint warnings** | Low | 14 warnings across 236 files. Non-blocking. Likely informational (scripts without explicit SQL boundary language). |
| **No cmd-level tests** | Low | 17 commands have no `_test.go` files at the cmd level. Logic lives in internal packages (tested), but command argument parsing is untested. |
| **durableoutputs package** | Low | No test file. Utility package — low risk but should have at least a shape-validation test. |
| **Roadmap items 29-31** | Medium | PM queue lint, cron authority lint, and shared validator suite are documented but not implemented. This audit recommends implementing 29 and 30 in Phase 1. |
| **No bulk JSON validator** | Medium | Hundreds of JSON proof artifacts with no bulk structural validation. This audit's top recommendation. |

### 5.3 Design Quality

The Go layer correctly follows the architecture decision from 2026-05-23:

> "Keep Python as the core workflow/finance/SQL/artifact/validator spine; add Go later only as hardened standalone validators after Python contracts stabilize."

The contracts have stabilized. The Go layer is now mature enough to expand from 17 to ~27 validators with the 10 gaps identified above. The shared toolkit (`reporting`, `sqlutil`) makes new validators cheap to add — each new validator is ~100-200 lines of Go plus a test.

---

## 6. Recommendations

1. **Implement Phase 1 validators (4 new) this week.** JSON structural validator, entry/stop freshness, cron authority lint, and PM queue lint. These close the highest-leverage gaps and two documented roadmap items.

2. **Implement Phase 2 validators (3 new) next week.** Answer completeness, cross-DB integrity, and artifact freshness. These strengthen the finance truth surface.

3. **Add cmd-level argument parsing tests.** A single table-driven test per command that verifies `--root` and `--out` flag behavior would catch regressions.

4. **Add tests to `internal/durableoutputs`.** Low effort, closes the last untested internal package.

5. **Resolve the 14 python-sql-contract-lint warnings.** Review whether they're false positives (scripts that don't need SQL boundary language) or real gaps.

6. **Keep Go as validator edge.** The controlled demotion experiment proved Python should remain the owner/orchestrator. Go adds speed and independence for read-only validation. Do not expand Go into workflow generation, SQL mutation, or orchestration.

---

## 7. Boundary

This audit is read-only. No code was written, no config was changed, no binaries were rebuilt, and no authority was expanded. All findings are based on live artifact inspection and binary execution of existing validators.

**Next action:** Randall reviews and approves Phase 1 implementation. Veritas main session or a bounded helper lane implements the 4 Phase 1 validators following the established pattern.
