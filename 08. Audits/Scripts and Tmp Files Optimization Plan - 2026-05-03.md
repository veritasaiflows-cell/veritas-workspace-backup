# Scripts and Tmp Files Optimization Plan

**Date:** 2026-05-03
**Authored by:** Claude (independent audit layer)
**Trigger:** Full scripts + tmp/ audit following WF9B–12 chain closure
**Scope:** 46 Python scripts, 1 JSX component, 16 JS dashboard modules, 52 tmp/ artifacts
**Validation at time of audit:** 0 critical / 0 warning / 17/17 acceptance

---

## Executive Summary

The chain is structurally sound and running correctly. This plan improves health at the margins: three silent defects, one accumulation risk, one high-dependency contract gap, and a structural clarity problem in the scripts/ root. Nothing here requires touching the 26-step chain order, the dashboard JS module structure, or the command center output path — those are working and optimization pressure there is low.

---

## Audit Findings

### Scripts inventory (46 total)

| Category | Count | Scripts |
|---|---|---|
| Chain-active (post-close) | 26 | earnings_calendar_enrichment, policy_expectations_refresh, credit_spread_refresh, breadth_refresh, market_state_refresh, macro_regime_refresh, technical_refresh, regime_scoring_refresh, band_refresh, entry_band_fetch, generate_entry_band_status, deployment_check, trigger_sheet_refresh, positioning_ranking_refresh, post_earnings_prep, post_earnings_note_targets, universe_consistency_check, test_dashboard_acceptance, generate_dashboard, validate_dashboard_state, workbook_export, postmarket_snapshot, daily_executive_brief, run_summary_refresh, dashboard_run_summary_consumer, deployment_readiness_surface |
| Sunday-only additions | 4 | weekly_intelligence_brief, weekly_macro_snapshot, weekly_review_skeleton, call_log_sync |
| Operator tools (off-chain) | 6 | apply_band_update, band_note_sync, daily_note_dedupe, post_earnings_scorecard, test_universe, workbook_template |
| Equity reporting (off-chain) | 3 | equity_visual_report, equity_pdf_report, equity_ppt_report |
| Core libraries | 4 | dashboard_core, dashboard_payload, dashboard_validation, market_data_utils |
| Utility | 3 | universe, universe_consistency_check, band_refresh |

**Chain step sequence (post-close, 26 steps):**
1. earnings_calendar_enrichment → 2. policy_expectations_refresh → 3. credit_spread_refresh → 4. breadth_refresh → 5. market_state_refresh → 6. macro_regime_refresh → 7. technical_refresh → 8. regime_scoring_refresh → 9. band_refresh → 10. entry_band_fetch → 11. generate_entry_band_status → 12. deployment_check → 13. trigger_sheet_refresh → 14. positioning_ranking_refresh → 15. post_earnings_prep → 16. post_earnings_note_targets → 17. universe_consistency_check → 18. test_dashboard_acceptance → 19. generate_dashboard → 20. validate_dashboard_state → 21. workbook_export → 22. postmarket_snapshot → 23. daily_executive_brief → 24. run_summary_refresh → 25. dashboard_run_summary_consumer → 26. deployment_readiness_surface

### Tmp/ inventory (52 artifacts)

**Auto-overwritten on each run (no accumulation risk):** run-chain-*.json, run-summary-*.json, dashboard-validation.json, dashboard-data.json, dashboard-last.json, dashboard-delta.json, entry-band-reports/*.html, workbook CSVs, workbook-export-manifest.json

**Fresh from last run (2026-05-03 14:14 UTC):** all 20 critical artifacts confirmed current

**No automatic cleanup mechanism exists.** Files accumulate until manual audit passes.

---

## Defects Found

### D1 — Broken workspace path in three equity report scripts
**Files:** `equity_visual_report.py`, `equity_pdf_report.py`, `equity_ppt_report.py`
**Line:** 1 (WORKSPACE constant in each file)
**Issue:** `WORKSPACE = Path(r"C:\Users\Veritas2.0\.openclaw\workspace")` — hardcoded to `Veritas2.0`, current machine user is `Veritas`. All three would crash on any manual invocation.
**Fix:** Replace hardcoded path with `Path(__file__).resolve().parents[1]` — the pattern used by every other script.
**Risk:** Zero (off-chain tools). **Effort:** 1 line × 3 files.

### D2 — run_summary_refresh.py chain_status normalization edge case
**File:** `scripts/run_summary_refresh.py`, lines 166–191
**Issue:** `normalized_chain_status()` returns `"running"` when its normalization condition doesn't fire, producing `chain_status: "running"` in `tmp/run-summary-post-close.json` even when the run completed with `status: "ok"` and `exit_code: 0`. The fail-closed constraints (`presentation_allowed: false`, `canonical_note_mutation_allowed: false`) are correct — this is a misleading diagnostic only.
**Fix:** Tighten the normalization condition to also match when `run_summary_refresh.py` is the only running step and the chain exit code is `0`.
**Risk:** Low (confined to normalizer helper). **Effort:** ~10 lines.

### D3 — No tmp/ cleanup mechanism
**Issue:** tmp/ has 52 artifacts with no rotation or pruning. Manual audit passes (like the one preceding this document) are the only cleanup path. Without a scheduled mechanism, the directory will regrow within weeks.
**Fix:** Add `scripts/tmp_cleanup.py` — archives artifacts older than a configurable threshold. Wire as an optional Sunday chain step behind `--cleanup` flag. Encode the retention policy in `06. Playbooks/Workspace Structure Protocol.md`.
**Risk:** Zero if gated. **Effort:** ~80 lines + 1 Sunday chain entry.

---

## Structural Issues

### S1 — portfolio-config.json has no automated writer
**File:** `tmp/portfolio-config.json`
**Issue:** The single most-read file in the system (8+ script dependencies, every chain run) is manually maintained with no schema enforcement. Any field drift propagates silently into the full chain output.
**Fix:** Add `scripts/validate_portfolio_config.py` — a read-only validator checking:
- All `tracked_universe` tickers present in `entry_bands`
- All `workflow_state` values from the approved enum (`ALMOST`, `WATCH`, `REPAIR`, `BLOCKED`)
- All `coverage_lane` values match the approved tier model
- No ticker missing `portfolio_role`

Wire as a fail-soft early chain gate (after step 1, before step 7). Output to `tmp/portfolio-config-validation.json`. Do not block the chain — emit warnings only.

This is not full automation. It is a contract guard that surfaces drift before it reaches the dashboard.

**Risk:** Zero if fail-soft. **Effort:** ~120 lines.

### S2 — scripts/ root mixes chain scripts and operator tools
**Issue:** 26 chain-active scripts share the `scripts/` root with 6 off-chain operator tools and 3 equity reporting scripts. A reader cannot distinguish production chain members from on-demand utilities without reading `run_finance_refresh_chain.py`.
**Fix:** Create `scripts/operators/` and move off-chain operator tools there:

| Script | Purpose |
|---|---|
| `apply_band_update.py` | Apply approved band proposals (operator-gated) |
| `band_note_sync.py` | Sync bands to technical sheet (operator-gated) |
| `daily_note_dedupe.py` | Remove duplicate memory bullets (maintenance) |
| `post_earnings_scorecard.py` | Pre-fill earnings scorecard stubs (per-ticker) |
| `test_universe.py` | Lane resolver unit tests (dev/QA) |

`call_log_sync.py` runs in the Sunday chain — leave in place.
**Prerequisite:** verify `run_finance_refresh_chain.py` references by path before moving.
**Risk:** Medium (requires caller verification). **Effort:** file moves + grep verification pass.

### S3 — entry_band_viewer.jsx is an undocumented embed pattern
**File:** `scripts/entry_band_viewer.jsx`
**Issue:** `entry_band_fetch.py` line 6 documents that this JSX component is embedded inline into per-ticker HTML files. It works, but JSX in a non-build-tooled Python project will surprise any future developer.
**Fix (minimal):** Add a comment block in `entry_band_fetch.py` explaining the embed pattern — that the JSX is not a standalone React component but an inline-rendered bundle.
**Fix (better, optional):** Migrate to vanilla JS. The chart rendering is not complex enough to require React.
**Risk:** Zero for documentation fix. Low for migration.

---

## Performance Opportunities

### P1 — entry_band_fetch.py re-fetches all 20+ tickers on every chain run
**File:** `scripts/entry_band_fetch.py`, step 10 of every morning/post-close/post-earnings chain
**Issue:** Fetches 10 years of monthly OHLC for all tracked tickers via yfinance on every run. This is the heaviest network step in the chain and the most likely to fail under rate-limit conditions.
**Fix:** Add a freshness gate — skip the yfinance fetch for a ticker if its `entry-band-data/{TICKER}.json` is less than 12 hours old and `asof` matches `last_trading_day`. Re-fetch only when stale or missing. On consecutive-day runs, this reduces a full 20-ticker fetch to 0–3 names.
**Risk:** Low if the staleness check is correct (bundles are complete). **Effort:** ~30 lines.

### P2 — dashboard_payload.py (959 lines) is the largest single file
**File:** `scripts/dashboard_payload.py`
**Issue:** Approaching the threshold where a bug in one domain (macro regime, deployment, portfolio) requires reading the whole file to locate.
**Proposed split (when a natural seam arises):**
- `dashboard_payload_macro.py` — regime, policy, rates, yields
- `dashboard_payload_deployment.py` — trigger sheet, deployment board, band status
- `dashboard_payload_portfolio.py` — portfolio config, sector allocation, risk flags
- `dashboard_payload.py` — thin orchestrator importing the above

**Not recommended now.** Only do this when a bug or feature request creates a natural seam. A premature split adds import overhead without solving a real problem.

---

## Tmp/ Retention Policy (proposed)

To be encoded in `06. Playbooks/Workspace Structure Protocol.md`:

| File category | Retention | Mechanism |
|---|---|---|
| run-chain-*.json | Overwritten each run | Automatic |
| run-summary-*.json | Overwritten each run | Automatic |
| dashboard-*.json (data/delta/last/validation) | Overwritten each run | Automatic |
| entry-band-data/*.json | 12h freshness gate (after P1) | Script gate |
| entry-band-reports/*.html | Overwritten each run | Automatic |
| Workbook CSVs + manifest | Overwritten each run | Automatic |
| One-off analysis artifacts | Archive within 7 days | Sunday cleanup (D3) |
| premarket-snapshot.json, postmarket-snapshot.json | Overwritten each window | Automatic |
| weekly-*.json | Overwritten each Sunday | Automatic |

---

## Priority Sequence

| # | Item | Category | Why this order |
|---|---|---|---|
| 1 | Fix `Veritas2.0` path in equity scripts | D1 | Silent crash on any manual use |
| 2 | Fix chain_status normalization | D2 | Active misleading diagnostic, contained fix |
| 3 | Add `tmp_cleanup.py` + Sunday chain hook | D3 | Prevents audit debt from rebuilding |
| 4 | Add `validate_portfolio_config.py` | S1 | Guards the highest-risk single dependency |
| 5 | Create `scripts/operators/` structure | S2 | Clarity, after path verification |
| 6 | Archive equity PDF/PPT if unused | S2 follow-on | After D1 path fix and usage check |
| 7 | Document JSX embed in entry_band_fetch | S3 | One comment block, low urgency |
| 8 | Add freshness gate to entry_band_fetch | P1 | Performance, when chain latency is a real issue |
| 9 | Split dashboard_payload.py | P2 | Only at a natural seam, not proactively |

---

## What This Plan Does Not Touch

- The 26-step chain order — working and proven
- The 16-module dashboard JS structure — clean numbered approach
- The command center output path (`tmp/veritas-command-center.html`) — consistent across all callers
- The `portfolio-config.json` schema itself — validation only, no automation until explicitly designed
- Any canonical note content — this is infrastructure only

---

*Authored during the 2026-05-03 scripts + tmp/ audit session. Preceded by tmp/ cleanup (18 files archived) and directory examination (atomic_slice_precheck, external-research, entry-band-data). Validation held at 0 critical / 0 warning throughout.*
