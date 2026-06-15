# Scripts / Tmp / Data Audit - 2026-05-29

**Auditor:** Veritas main session
**Date:** 2026-05-29 15:11–15:20 MST
**Scope:** `scripts/`, `tmp/`, `data/` — inventory, gap analysis, and opportunities
**Posture:** Read-only analysis. No files moved, deleted, or modified.

---

## Executive Summary

| Layer | Size | File Count | Health |
|---|---|---|---|
| `scripts/` | 5.0 MB | 321 (237 non-test, 84 test) | Good structure; 174 scripts have no `test_` counterpart; several large critical scripts untested |
| `tmp/` | 112 MB | ~900+ files | Bloated; 432 stale JSON, 102 stale MD, 75 non-JSON/MD "other" files including large debug dumps; 29 subdirs, some empty or misplaced |
| `data/` | ~12.7 MB | 12 files | Thin; 4 subdirectories only; market/technical/sector data lives entirely in `tmp/`, not here; `company-ir-metadata.json` is 307h stale |

**Primary gaps:** critical scripts untested, `tmp/` has accumulated large debug/log/backup artifacts that belong elsewhere, and the `data/` layer is too shallow to support the retail SaaS product.

**Primary opportunities:** test coverage for the 5 highest-risk untested scripts; IR capture consolidation; `data/` layer deepening for durable market/sector/technical data; `tmp/` cleanup of large stale non-proof artifacts.

---

## 1. Scripts Audit

### 1.1 Inventory Overview

- **321 total scripts**, ~5.0 MB
- **237 non-test scripts**, **84 test scripts**
- **88 referenced directly** in `chain_manifest.py` + `run_finance_refresh_chain.py`
- **151 not in main chain** — on-demand, workflow-specific, validators called elsewhere, or historical
- **174 non-test scripts with no `test_` counterpart** (54% untested)

### 1.2 Size Distribution (non-test scripts)

| Size tier | Count | Examples |
|---|---|---|
| > 60 KB (very large) | 7 | `artifact_index.py` 305KB, `dashboard_payload.py` 121KB, `test_dashboard_acceptance.py` 94KB, `chain_manifest.py` 79KB, `fundamental_metrics_refresh.py` 71KB, `finance_intelligence_state.py` 65KB, `sql_canon_field_family_preflight.py` 64KB |
| 30–60 KB | 12 | `daily_review_objects.py`, `bounded_entry_band_agent.py`, `band_refresh.py`, `ticker_intelligence_card.py`, `wf74_rsi.py`, `alpaca_paper_trade_executor.py`, `run_summary_refresh.py`, `workbook_export.py`, and others |
| 15–30 KB | ~60 | Most finance/chain/SQL/WF scripts |
| < 1 KB (stubs) | 4 | `apply_band_update.py`, `band_note_sync.py`, `post_earnings_scorecard.py`, `daily_note_dedupe.py` — all are one-liner `from operators.X import main` shims |

### 1.3 Critical Untested Scripts

The following high-risk scripts have no `test_` counterpart and are either in the main finance chain, critical to canon integrity, or directly produce customer-facing output:

| Script | Size | Risk | Why it matters |
|---|---|---|---|
| `dashboard_payload.py` | 121.5 KB | **Critical** | Builds the entire Command Center payload; biggest single script; false-green failures here cascade to every consumer |
| `chain_manifest.py` | 79.2 KB | **Critical** | Orchestrates the morning/post-close/Sunday chain; no test means chain regressions are caught only by the acceptance test, which can drift |
| `fundamental_metrics_refresh.py` | 71.0 KB | **High** | Primary fundamental data pipeline; untested |
| `finance_intelligence_state.py` | 65.7 KB | **High** | Core SQL routing/query layer for 42 tickers + WF78 pilot; untested |
| `band_refresh.py` | 34.0 KB | **High** | Drives daily entry-band maintenance; auto-apply path depends on it |
| `deployment_readiness_surface.py` | 20.3 KB | **High** | Generates machine/prose conflict state; the false-green guard lives here |
| `canon_volatile_execution_board_sync.py` | 24.7 KB | **High** | Writes to `03. Portfolio/Execution Board.md`; canon mutation without test coverage is high risk |
| `ticker_intelligence_card.py` | 40.5 KB | **High** | Builds all 42 ticker-intelligence cards; primary retail SaaS evidence layer |
| `retail_saas_customer_output_validator.py` | 15.3 KB | **High** | The claim-boundary enforcer for the retail SaaS product; ironic that the validator itself has no test suite |
| `alpaca_paper_position_sql_refresh.py` | 32.9 KB | **Medium** | Paper-position SQL layer; tested manually but no `test_` file |
| `macro_regime_refresh.py` | 33.4 KB | **Medium** | Macro regime driver; no test |
| `research_freshness_opportunity_review.py` | 28.5 KB | **Medium** | Weekly intelligence input; no test |

### 1.4 Potentially Superseded / Low-Use Scripts

These scripts have names or shapes suggesting they may be historical, diagnostic, or superseded by newer scripts:

| Script | Size | Concern |
|---|---|---|
| `etn_vrt_official_ir_capture.py` | 15.0 KB | Ticker-specific IR capture; likely superseded by `longtail_official_ir_capture.py` (52.4KB) |
| `goog_official_ir_capture.py` | 11.0 KB | Same pattern — ticker-specific, likely superseded |
| `tech_official_ir_capture.py` | 21.6 KB | Same pattern |
| `batch2_official_ir_capture.py` + `batch2b_official_ir_capture.py` | 15.9+15.7 KB | Batch-run scripts; may be historical |
| `priority_official_ir_capture.py` | 18.5 KB | Phase-specific IR capture |
| `bank_native_sec_concept_probe.py` | 31.0 KB | "Probe" in name; 31KB suggests it grew into something real or should be archived |
| `codex_app_server_timeout_diagnostics.py` | 9.4 KB | Diagnostic for `@openclaw/codex` plugin which was uninstalled 2026-05-25 |
| `openai_provider_compat_matrix.py` | 31.3 KB | Provider compatibility matrix; unclear if still active |
| `openclaw_cache_efficiency_scorecard.py` | 38.7 KB | Cache scorecard; unclear current use |
| `openclaw_otel_privacy_packet.py` | 20.9 KB | OTEL privacy audit; local telemetry mostly dormant |
| `local_otel_collector.py` | 4.0 KB | OTEL collector stub |
| `telemetry_audit_window_control.py` | 3.5 KB | Telemetry control; low apparent use |
| `sql_canon_low_risk_phase3_activate.py` | 30.3 KB | Phase 3 activation script; may have run once and now be historical |
| `sql_canon_cache_rollback_phase3c.py` | 4.1 KB | Rollback utility for a past phase |
| `sql_500_ticker_expansion_design_gate.py` | 5.3 KB | Design gate for expansion not yet approved |
| `weekly_review_skeleton.py` | 19.9 KB | Skeleton/scaffold; unclear if generating real output |
| `ranking_shadow_canon_check.py` | 3.2 KB | Shadow check; unclear current use |
| `swarm_completion_handshake.py` | 5.9 KB | IC swarm handshake; unclear if wired |

### 1.5 Stub Scripts Pointing to `operators/` Package

Four scripts are one-liner shims importing from an `operators` package:
- `apply_band_update.py`, `band_note_sync.py`, `post_earnings_scorecard.py`, `daily_note_dedupe.py`

No `operators/` package exists as a visible directory in `scripts/` or the root. These will fail at import time if called directly. Either the `operators` module is embedded elsewhere (unlikely) or these are stubs left from a refactor that was never completed. **Verify before relying on them in any chain step.**

### 1.6 Gaps in Scripts Coverage

What should exist but doesn't:

| Missing script | Why needed |
|---|---|
| `scripts/test_retail_saas_customer_output_validator.py` | The hardness report written today argues this validator is the claim-boundary enforcer; it needs adversarial test cases committed as a test suite |
| `scripts/test_retail_saas_fixture_demo.py` | Fixture generation path is untested beyond manual runs |
| `scripts/retail_saas_validated_brief_generator.py` | The one-function hardness pattern: fused generation + validation that cannot return unvalidated output |
| `scripts/test_canon_volatile_execution_board_sync.py` | Canon mutation script with no test; high-risk gap |
| `scripts/test_deployment_readiness_surface.py` | The false-green guard needs its own isolated test, not just end-to-end acceptance |
| `scripts/test_band_refresh.py` | Daily auto-apply depends on this; untested |
| `scripts/data_freshness_gate.py` | A single script that validates freshness thresholds across `data/` and `tmp/` key artifacts; currently this logic is scattered across multiple validators |
| `scripts/retail_saas_real_data_pipeline.py` | When the real data path is approved, a script that pipes live ticker-intelligence-card output through the customer output validator |

---

## 2. Tmp Audit

### 2.1 Volume Overview

| Category | Files | Size | Notes |
|---|---|---|---|
| JSON fresh (<48h) | 220 | 18.0 MB | Active proof artifacts; appropriate |
| JSON stale (>48h) | 432 | 15.1 MB | Large accumulation; 135 files > 7 days old (3.0 MB) |
| MD fresh (<48h) | 57 | 358 KB | Active Markdown reports; appropriate |
| MD stale (>48h) | 102 | 892 KB | Historical reports; many can be retired |
| SQLite | 10 | 29.8 MB | See Section 2.3 |
| HTML | 6 | 5.2 MB | Dashboard + report renders; mostly appropriate |
| Other (txt/sql/log/png/etc) | 75 | 12.7 MB | **Primary cleanup target** — debug dumps, log exports, SQL rollback files |

**Total: ~112 MB across ~900+ files**

### 2.2 Large Stale "Other" Files (Primary Cleanup Targets)

These are debug logs, config dumps, and diagnostic artifacts that have no ongoing proof role:

| File | Size | Age | Disposition |
|---|---|---|---|
| `openclaw-config-schema-20260526.txt` | 4.6 MB | 69h | Config schema text dump; regenerable; archive or delete after next config run |
| `cron-source-rg.txt` | 3.9 MB | 111h | Cron source grep output from a diagnostic pass; archive |
| `openclaw-config-schema-current.json` | 4.5 MB | 113h | Superseded by the `2026.5.27` runtime; regenerable; archive |
| `cron-delay-log-excerpts.txt` | 1.6 MB | 111h | Cron debug log; archive |
| `openclaw-log-tail-after-restart.txt` | 222 KB | 111h | Post-restart log dump; archive |
| `cron-target-id-log-context.txt` | 113 KB | 111h | Diagnostic; archive |
| `cron-log-lines-tail.txt` | 106 KB | 111h | Diagnostic; archive |
| `archive-suggestions-run.log` | 127 KB | 98h | Archive run log; archive |
| `postclose-sql-canon-hardening-dry-run.txt` | 48 KB | 69h | One-off dry-run output; archive |
| `wf69-phase2-provenance-spine-run.log` | 89 KB | 157h | Run log; archive |
| `authority_flag_search_2026_05_18.txt` | 252 KB | 271h | Historical search; archive |

**Estimated cleanup yield: ~16 MB** from these 11 files alone.

### 2.3 SQLite Files in `tmp/`

| File | Size | Age | Status |
|---|---|---|---|
| `workspace-index.sqlite` | 15.8 MB | fresh | Active — rebuildable retrieval cache |
| `veritas-artifact-index.sqlite` | 3.8 MB | fresh | Active — derived proof/index |
| `veritas-canon-cache.sqlite` | 3.1 MB | fresh | Active — 265 approved metadata rows; bounded canon authority |
| `wf72-entry-stop-sql-activation-rollback-drill.sqlite` | 2.9 MB | 2h | Recent rollback drill DB; retain until WF72 SQL work closes |
| `finance-intelligence-state.sqlite` | 2.0 MB | 17h | Active — WF78 routing/query layer |
| `finance-stack-snapshot.sqlite` | 2.0 MB | fresh | Active — daily finance snapshot |
| `wf67-paper-position-state.sqlite` | 56 KB | fresh | Active — paper-position GET-only state |
| `wf67-paper-position-state.pre-block-test.*.sqlite` | 52 KB | 22h | Test artifact from WF67 block-test; can be cleaned after WF67 repair |
| `wf72-phase4-six-key-stabilization-*.sqlite` | 76+68 KB | 124h | Historical phase cache copies; archive after WF72 closes |

**Concern:** `wf72-entry-stop-sql-activation-rollback-drill.sqlite` at 2.9 MB is large for a rollback drill artifact. Verify it's needed before next SQL work or archive it.

### 2.4 Misplaced Subdirectories

| Path | Size | Issue |
|---|---|---|
| `tmp/backups/` | 1.76 MB | Backups inside `tmp/` instead of `backups/`; should be moved to `backups/` when safe |
| `tmp/core-file-backups/` | 49 KB | Single 426h-old file (`2026-05-11_2055_canon_posture`); should be in `backups/` |
| `tmp/post-update-hardening-backup-20260527-224519/` | 9.9 MB | Post-update backup sitting in `tmp/`; **largest single tmp directory**; move to `backups/` |
| `tmp/__pycache__/` | 13 KB | Python runtime cache; add to `.gitignore` if not already |
| `tmp/go-build/` | 3.6 MB | Contains a single file `wf74-boundary-lint.exe` — a Go binary; unclear if still used; check before removing |
| `tmp/wf60-backups/` | 0 KB | Empty; can be removed |
| `tmp/wf61-backups/` | 0 KB | Empty; can be removed |

**Estimated cleanup yield: ~12 MB** from moving/archiving the backup subdirs alone.

### 2.5 `tmp/otel-collector/` — 981 Files

The OTEL collector directory contains 981 files totaling 412 KB. This is extreme fragmentation for 412 KB of data. The OTEL stack appears mostly dormant. If telemetry is not actively used, this directory should be cleared and the cron job that generates these files (if any) should be disabled.

### 2.6 Large Historical Proof Directories

| Path | Size | Files | Notes |
|---|---|---|---|
| `tmp/wf70-proof/` | 7.3 MB | 131 | WF70 official evidence proof runs; oldest files may be archivable |
| `tmp/portfolio-mutation-proposals/` | 1.0 MB | 177 | Active — daily recommendation chain output; mostly appropriate |
| `tmp/entry-band-reports/` | 2.1 MB | 38 | HTML entry band reports; large for reports |
| `tmp/compact-exec-logs/` | 187 KB | 84 | Compact exec session logs; older ones archivable |

### 2.7 Stale JSON > 7 Days (135 files, 3.0 MB)

The 135 files older than 7 days are mostly historical planning, phase artifacts, and research runs. Top candidates for a review-only stale-tmp archive proposal:

| Category | Representative files | Age |
|---|---|---|
| WF72 historical planning | `wf72-safe-delete-proposal-runtime-cache-2026-05-25.json`, `wf72-archive-suggestions-decision-register-2026-05-25.json`, `wf72-runtime-cache-delete-2026-05-25.json` | 101h |
| SQL phase artifacts | `sql-canon-phase4-dashboard-before.json` (1.1 MB), `sql-canon-phase4a-activation.json` (605 KB), `sql-canon-phase4a-validation.json` | 98-146h |
| Config/cron dumps | `openclaw-config-schema-current.json` (4.5 MB), `cron-tasks.json` (144 KB), `cron-list-20260526T1700.json` (150 KB) | 70-145h |
| Old research runs | `state-history-v1-sample.json` (84 KB), `archive_ref_check_raw.json` (224 KB), `archive-candidate-apply-manifest-2026-05-19.json` (172 KB) | 244-400h |
| WF72 archive sweeps | `wf72-tmp-md-blocking-vs-historical-classification-2026-05-25.json` (187 KB), `wf72-full-tmp-md-sweep-2026-05-25.json` (182 KB), `wf72-active-tmp-md-cleanup-2026-05-25.json` (89 KB) | 101h |

**Recommended action:** generate a review-only `tmp/stale-tmp-cleanup-proposal-2026-05-29.json` with reference scans, categorization, and proposed archive/delete disposition, then present as a microbatch packet for approval. Do not move or delete without that packet.

---

## 3. Data Audit

### 3.1 Inventory

```
data/
├── finance/
│   ├── README.md             (1.2 KB, 17h old)
│   └── universe-v1.json      (157.4 KB, 20h old) — 42 production + 11 pilot + 25 live-pilot
├── fundamentals/
│   ├── README.md             (1.7 KB, 120h old)
│   ├── company-ir-metadata.json      (17.6 KB, 307h old) — STALE
│   ├── fundamentals-quarterly-v1.jsonl (11.2 MB, 2h old) — active, well-maintained
│   └── official-ir-capture-contract.json (5.3 KB, 192h old)
└── state-history/
    ├── README.md             (1.6 KB, 455h old) — stale
    ├── automation-health-dashboard-history.jsonl (51.4 KB, 96h old)
    ├── outcome-updates-v1.jsonl      (10.2 KB, 237h old) — sparse use
    ├── runtime-expansion-pilot-history.jsonl (26.4 KB, 2h old)
    ├── runtime-expansion-pilot-latest.json (2.9 KB, 2h old)
    └── state-history-v1.jsonl        (1.2 MB, 23h old) — active
```

### 3.2 What's Working

- **`data/fundamentals/fundamentals-quarterly-v1.jsonl`** (11.2 MB) is the crown jewel of the data layer — the primary fundamental data store, refreshed every 2 hours, directly used by `fundamental_metrics_refresh.py`. This is real durable data.
- **`data/finance/universe-v1.json`** is the canonical 42-ticker production universe registry introduced in WF78 Phase 1. Well-maintained and the right structure.
- **`data/state-history/state-history-v1.jsonl`** is active and appended to daily.

### 3.3 Gaps — The Data Layer is Too Thin for a SaaS Product

The `data/` directory has only 12 files across 4 subdirectories. For a retail investor finance intelligence product, durable data needs to live in `data/`, not `tmp/`. Currently:

| Data type | Where it lives | Should live | Problem |
|---|---|---|---|
| Market/price data | `tmp/` (stale within hours) | `data/market/` | Evaporates; no durable price history |
| Technical levels | `tmp/portfolio-config.json`, `tmp/technical-refresh.json` | `data/technical/` or `data/finance/` | Config-file pattern, not data layer |
| Sector/macro regime | `tmp/market-state.json`, `tmp/regime-scoring-*.json` | `data/macro/` | tmp-only, no history |
| Sector leadership | `tmp/sector-expansion-board.json` | `data/sector/` | No durable history |
| Company IR metadata | `data/fundamentals/company-ir-metadata.json` | ✓ correct location | But **307h stale** |
| Outcome/probability history | `data/state-history/outcome-updates-v1.jsonl` | ✓ correct location | Only 10.2 KB — barely used |
| Entry bands / stops | `tmp/portfolio-config.json` | `data/finance/` or `data/technical/` | In tmp/, risk of drift |

**The retail SaaS product cannot deliver consistent, auditable customer intelligence if the underlying data lives entirely in `tmp/`.** The `data/` layer needs to grow to support: technical level history, sector leadership snapshots, macro regime history, and a durable price reference layer.

### 3.4 Specific Data Gaps

| Missing data asset | Why needed | Priority |
|---|---|---|
| `data/technical/entry-bands-v1.json` | Durable home for the 42-ticker entry bands/stops currently in `tmp/portfolio-config.json` | High |
| `data/market/price-snapshots/YYYY-MM-DD.json` | Durable daily price history; currently nothing survives past `tmp/` | High (for SaaS) |
| `data/macro/regime-history-v1.jsonl` | Regime state history; currently no durable record | Medium |
| `data/sector/leadership-snapshots-v1.jsonl` | Sector rotation history; currently ephemeral in `tmp/` | Medium |
| `data/finance/ticker-card-snapshots/` | Daily ticker-card snapshots for trend detection; currently only "current" card exists | Medium (for SaaS) |
| `data/fundamentals/company-ir-metadata.json` | **Needs refresh** — 307h stale | Immediate |
| `data/state-history/README.md` | **Needs refresh** — 455h stale, likely inaccurate | Low |

### 3.5 `data/state-history/outcome-updates-v1.jsonl`

This file is only 10.2 KB and 237h old. It represents the probability/outcome tracking layer (WF55). Given that WF55 is blocked and `wf55_outcome_ledger_v2.py` (26 KB) exists in scripts/, the outcome update path appears nearly dormant. Before WF55 can be activated, this ledger needs to be meaningfully populated with outcome records.

---

## 4. Cross-Layer Findings

### 4.1 The Truth Triangle Is Strained

The canonical truth architecture is: `data/` (durable) → `tmp/` (fresh proofs) → `scripts/` (generation). But in practice:

- `data/` is so thin that `tmp/` has become the de facto durable data store.
- When `tmp/` artifacts age past 7 days they become stale "proof" that no one is refreshing.
- Scripts that should read from `data/` (like entry bands, sector regime) read from `tmp/` instead.

This is manageable for an internal tool but becomes a structural problem for a SaaS product where customer-facing claims need auditable, version-controlled data sources.

### 4.2 Test Coverage Is Inverted

The most-tested scripts tend to be the most stable and smallest. The least-tested are often the largest and most critical:

- `test_dashboard_acceptance.py` is 94.5 KB — but tests the whole chain end-to-end rather than the generating scripts in isolation.
- `dashboard_payload.py` at 121.5 KB has no unit tests at all.
- The chain manifest (79 KB) has no test.

End-to-end acceptance tests catch integration failures but drift from the system's truth (GOOG vs JPM/MSFT/GS). Unit tests on the generating scripts would catch logic regressions earlier.

### 4.3 IR Capture Fragmentation

There are 8+ IR capture scripts targeting different tickers or phases:
`etn_vrt_official_ir_capture.py`, `goog_official_ir_capture.py`, `tech_official_ir_capture.py`, `batch2_official_ir_capture.py`, `batch2b_official_ir_capture.py`, `priority_official_ir_capture.py`, `longtail_official_ir_capture.py`, `official_ir_capture_common.py`.

The `longtail_official_ir_capture.py` (52.4 KB) appears to be the generalized version. The ticker-specific scripts are likely historical batch runs from before the general capture path existed. If `longtail_official_ir_capture.py` covers all tickers in the universe, the ticker-specific scripts can be archived.

### 4.4 Retail SaaS Scripts Are Structurally Isolated

`retail_saas_fixture_demo.py`, `retail_saas_customer_output_validator.py`, and `retail_saas_html_report.py` exist as standalone scripts not wired into any chain or cron job. They are valid for fixture/demo use but:

- No test suite for the validator (see hardness report 2026-05-29)
- No integration with the live ticker-intelligence-card pipeline
- No cron scheduling or refresh cadence
- The generation and validation are separate callables (soft architecture per hardness report)

When the real data path is approved, this cluster needs to become a proper pipeline stage, not three standalone scripts.

---

## 5. Prioritized Recommendations

### Immediate (no approval needed, low risk)

| # | Action | Effort |
|---|---|---|
| 1 | Refresh `data/fundamentals/company-ir-metadata.json` (307h stale) | 15 min |
| 2 | Verify the 4 `operators/` stub scripts (`apply_band_update.py` etc.) — confirm whether `operators` package exists or scripts are broken | 10 min |
| 3 | Add `tmp/__pycache__/` to `.gitignore` if not already present | 5 min |
| 4 | Write `scripts/test_retail_saas_customer_output_validator.py` with adversarial claim-boundary test cases | 1–2 hrs |

### Approval-gated microbatches (propose → approve → move)

| # | Action | Effort | Approval type |
|---|---|---|---|
| 5 | Move `tmp/post-update-hardening-backup-20260527-224519/` (9.9 MB) to `backups/` | Propose + approve | Single-item move, low risk |
| 6 | Move `tmp/backups/` and `tmp/core-file-backups/` contents to `backups/` | Propose + approve | Directory consolidation |
| 7 | Archive 11 large stale "other" files in `tmp/` (config dumps, cron logs, ~16 MB) | Propose microbatch + approve | Stale debug artifacts |
| 8 | Archive `openclaw-config-schema-current.json` (4.5 MB, superseded by 2026.5.27) | Propose + approve | Regenerable |
| 9 | Archive WF72 historical phase SQLite copies (`wf72-phase4-six-key-stabilization-*.sqlite`) | Propose + approve | Historical only |
| 10 | Generate stale-tmp cleanup proposal for 135 JSON files > 7 days old | Propose (no move yet) | Review-only first |

### Medium-term build work

| # | Action | Effort | Value |
|---|---|---|---|
| 11 | Write unit tests for `dashboard_payload.py` (critical, untested) | 2–3 hrs | Prevents chain regressions from drifting past acceptance tests |
| 12 | Write unit test for `canon_volatile_execution_board_sync.py` (canon mutation, untested) | 1–2 hrs | Hardness: canon mutations need test coverage |
| 13 | Introduce `data/technical/entry-bands-v1.json` — move entry bands out of `tmp/portfolio-config.json` | 2–3 hrs | Durable data layer; pre-req for SaaS |
| 14 | Audit IR capture scripts against `longtail_official_ir_capture.py` — identify which are superseded | 1 hr | Reduces script surface by 5-7 scripts |
| 15 | Clear `tmp/otel-collector/` (981 files, 412 KB) if OTEL is not active | 30 min (after verify) | Reduces fragmentation |
| 16 | Archive `tmp/wf70-proof/` oldest files (7.3 MB, historical capture runs) | Propose + approve | Storage |

### Longer-term (data layer deepening for SaaS)

| # | Action | Value |
|---|---|---|
| 17 | Introduce `data/market/` with daily price snapshots | Durable price history for customer trend analysis |
| 18 | Introduce `data/macro/regime-history-v1.jsonl` | Regime context over time |
| 19 | Introduce `data/sector/leadership-snapshots-v1.jsonl` | Sector rotation history |
| 20 | Fuse retail SaaS generation + validation into a single pipeline stage | Hardness (per 2026-05-29 report) |

---

## 6. What to Leave Alone

- `scripts/artifact_index.py` (305 KB) — very large but the right size for what it does; has a 63 KB test suite.
- `tmp/portfolio-mutation-proposals/` (1 MB, 177 files) — active daily chain output; do not touch.
- `tmp/ticker-intelligence-cards/` (887 KB, 42 files + pilot) — production ticker cards; active.
- `tmp/intraday-alerts/` — active WF68 output; do not archive while WF68 repair is pending.
- `data/fundamentals/fundamentals-quarterly-v1.jsonl` (11.2 MB) — the most valuable data asset; do not move.
- `tmp/wf72-entry-stop-sql-activation-rollback-drill.sqlite` — keep until the current WF72 SQL activation work is complete.
- All current-window proof artifacts (JSON fresh <48h) — these are the live evidence layer.

---

## 7. Authority Boundary

This document is read-only analysis. No files were moved, modified, deleted, or archived in producing this report. All recommendations in Section 5 require separate owner decision before any action. Microbatch moves require exact approval packets per the WF72 archive protocol. No portfolio, canon, SQL-canon, trade/account, paper/live, config/auth/channel/runtime state was changed.

---

## 8. Proof Sources

- `scripts/workspace_boundary_check.py` — boundary residue check
- `scripts/artifact_index.py validate` — freshness/lineage proof
- `scripts/boot_surface_size_guard.py` — boot surface sizes
- Direct file system enumeration via Python `pathlib` — size, age, count
- `scripts/chain_manifest.py` + `scripts/run_finance_refresh_chain.py` — chain reference scan
- `tmp/sql-canon-retail-grade-readiness.json` — SQL readiness state
- `tmp/intraday-alerts/advisor-alert-packet-validation.json` — WF68 validation state
- `tmp/dashboard-acceptance-report.json` — WF58 acceptance state

---

*Audit complete. No mutations performed.*
