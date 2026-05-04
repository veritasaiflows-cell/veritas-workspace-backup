# E17 Universe Synchronization — Phase 0 Decision

## Status

**PROPOSAL — pending operator decision.** This document scaffolds the Phase 0 decision required by the E17 Universe Synchronization playbook. Lane assignments below are recommended starting points, not commitments. Phase 1 implementation must not begin until each row in Table 1 has an explicit operator-confirmed lane.

## Purpose

Define three universe layers explicitly, in plain terms, before any script changes:

1. **Machine-tracked universe** — every ticker the chain knows about, regardless of surface.
2. **Execution-board subset** — names entitled to action cards on the dashboard and to deployment-grade workbook surfaces.
3. **Extended human watch universe** — the broader research/observation set captured in `Watchlist.md`.

Phase 0 ends when these three sets are defined, every disputed ticker has an assigned lane, and the relationship between `Watchlist.md` and `tmp/portfolio-config.json` has a stated direction of canonical truth.

## Drift evidence — why this decision exists

| Layer | Count | Names |
|---|---|---|
| `Watchlist.md` active tracking universe (2026-04-26) | 20 | JPM ETN VRT NVDA MSFT BRK.B RTX GOOG AMZN XOM LMT AMD GS CAT LNG PLTR KTOS SLV TLT SMCI |
| `portfolio-config.json` `tracked_universe` | 17 | AMZN BRK.B CAT CVX ETN GOOG GS JPM KTOS LMT MSFT NVDA PLTR RTX SLV VRT XOM |
| `portfolio-config.json` `entry_bands` | 17 | (same as tracked_universe) |
| `technical-refresh.json` records | 13 | tracked_universe ∩ `include_in_technical_refresh: true` |
| `trigger-sheet.json` records | 13 | tracked_universe ∩ `include_in_trigger_sheet: true` |
| `Deployment Trigger Sheet.md` board (2026-04-24) | 13 | (same as trigger-sheet.json — stale dates inside) |
| Action cards on `veritas-command-center.html` | ≤3 | filtered subset of the 13 |

Specific drift signals:

- **CVX is in config but not in `Watchlist.md`** — orphan. Either Watchlist.md is wrong or CVX should not be in config.
- **AMD, LNG, TLT, SMCI are in `Watchlist.md` but not in config** — invisible to all machine surfaces. Cannot drift-alert, cannot block on earnings, cannot be priced.
- **PLTR, KTOS, SLV are in config with `include_in_*: false`** — banded, drift-monitored, validator-flagged, but absent from dashboard and trigger sheet. The current "ghost lane."
- **`Deployment Trigger Sheet.md` is stale** relative to machine outputs — references "Apr 29 earnings" as a future event when today is 2026-04-30.

## Table 1 — Ticker lane proposal

Each ticker present in any layer is listed once. Operator marks the **Decided lane** column. Tickers with `?` rationale require deliberate adjudication before Phase 1 begins.

Legend for `Surfaces today`: T = `technical-refresh`, D = `deployment-check`, S = `trigger-sheet`, C = action cards eligible, W = `Watchlist.md`, N = Trigger Sheet note. `—` = absent.

| Ticker | Surfaces today | Coverage tier (config) | Portfolio role (config) | Workflow (config) | Proposed lane | Decided lane | Rationale |
|---|---|---|---|---|---|---|---|
| AMZN | T D S C W N | daily | watch_only | BLOCKED | execution | | Banded, blocks earnings, on board. Keep. |
| BRK.B | T D S C W N | daily | core | REPAIR | execution | | Core sleeve, structural REPAIR state — stays in execution lane to keep visibility. |
| CAT | T D S C W N | daily | tactical | WATCH | execution | | On board today; thesis active but underdefined. Keep in execution; resolve "underdefined" via band work. |
| CVX | — — — — — — | event | watch_only | WATCH | **REMOVE or relabel** | | Orphan: in config, not in Watchlist, no band drift signal. Either delete from config or formally restore to Watchlist as `watch`. |
| ETN | T D S C W N | daily | tactical | ALMOST | execution | | Best chart in sheet. Keep. |
| GOOG | T D S C W N | daily | core | BLOCKED | execution | | Core. Keep. (Earnings-block window fix is a Phase 3 issue, not lane.) |
| GS | T D S C W N | daily | tactical | WATCH | execution | | On board; underdefined levels. Keep in execution; address levels via band work. |
| JPM | T D S C W N | daily | core | ALMOST | execution | | Top scored name. Keep. |
| KTOS | — — — — W — | event | speculative | WATCH | speculative | | Watchlist tags as Speculative/Draft sleeve. Surface on speculative panel only. |
| LMT | T D S C W N | daily | core | REPAIR | execution | | Defense core; visible during repair. Keep. |
| MSFT | T D S C W N | daily | core | BLOCKED | execution | | Core. Keep. |
| NVDA | T D S C W N | daily | tactical | ALMOST | execution | | Top-3 scored. Keep. |
| PLTR | — — — — W — | event | watch_only | WATCH | watch | | Watchlist tags as Tactical/Speculative; today silently banded. Move to formal watch lane with visible surface. |
| RTX | T D S C W N | daily | tactical | WATCH | execution | | On board; weak structure. Keep in execution lane to maintain repair visibility. |
| SLV | — — — — W — | macro | speculative | MACRO | macro | | Watchlist tags as Macro/Speculative. Surface on macro panel; no action-card eligibility. |
| VRT | T D S C W N | daily | watch_only | WATCH | execution | | On board; underdefined. Keep in execution; resolve levels. |
| XOM | T D S C W N | daily | core | REPAIR | execution | | Energy core. Keep. |
| AMD | — — — — W — | (not in config) | (not in config) | (not in config) | watch | | In Watchlist as Tactical, May 5 earnings flagged. Add to config at watch lane so earnings calendar and band drift can monitor. |
| LNG | — — — — W — | (not in config) | (not in config) | (not in config) | watch | | In Watchlist as Tactical/Active watch. Add to config at watch lane. |
| TLT | — — — — W — | (not in config) | (not in config) | (not in config) | macro | | In Watchlist as Macro/Speculative/Benched. Add to config at macro lane (regime-context, no action cards). |
| SMCI | — — — — W — | (not in config) | (not in config) | (not in config) | speculative | | In Watchlist as Speculative/Active watch high-vol. Add to config at speculative lane. |

**Resulting universe under this proposal (pending decision):**

- execution lane: 13 names (unchanged from today's execution board) — AMZN, BRK.B, CAT, ETN, GOOG, GS, JPM, LMT, MSFT, NVDA, RTX, VRT, XOM
- watch lane: 3 names — PLTR, AMD, LNG
- macro lane: 2 names — SLV, TLT
- speculative lane: 2 names — KTOS, SMCI
- removed/relabeled: 1 name — CVX

Total machine-tracked universe under proposal: **20** (was 17). The execution board stays at 13. The expansion lives entirely in non-execution lanes.

## Table 2 — Lane definition and surface entitlement

| Lane | Definition | Surfaces it appears on | Action card eligible | Band drift monitored | Earnings calendar monitored | Workbook export sheet |
|---|---|---|---|---|---|---|
| **execution** | Thesis intact, deployable in principle, has explicit entry band and stop, scored in priority ranking. | Action cards (top 3 only), Deployment Board panel, Trigger Sheet note, Workbook deployment-ranking + watchlist-board + technical-drift. | Yes | Yes | Yes | deployment-ranking, watchlist-board, technical-drift |
| **watch** | Tracked thesis, may or may not have band, not currently deployment-grade, deserves visible monitoring. | Watch panel on dashboard, Workbook watch-lane sheet, Trigger Sheet note "Watch / research" section. | No | Yes (if banded) | Yes | watch-lane (new) |
| **macro** | Regime-context instrument (rates, hedges, commodities). Not a direct deployment candidate via action cards. | Macro panel on dashboard, Macro Regime Dashboard note. | No | Optional | No (unless ETF-relevant) | macro-context (new, optional) |
| **speculative** | Explicit speculative sleeve. Surfaces only when operator opts into the speculative panel. | Speculative panel on dashboard (collapsed by default), Workbook speculative sheet (optional). | No | Optional | Optional | speculative (new, optional) |

Implementation rule: every downstream script consumes lane membership from a single resolver; no script re-derives lane logic from raw flags. Per Veritas standard: "build one normalizer / entitlement resolver, downstream scripts consume that output, they do not each re-decide lane logic."

## Table 3 — Source / owner / reader / cadence

One owner per artifact. Everyone else is a reader. Mutation policy is explicit.

| Artifact | Owner (writer) | Readers | Update cadence | Mutation policy |
|---|---|---|---|---|
| `tmp/portfolio-config.json` `tracked_universe` | Operator (manual) | technical_refresh, deployment_check, trigger_sheet_refresh, dashboard_payload, workbook_export, band_refresh, validator | When membership changes | Hand-edit only. No script writes here. |
| `tmp/portfolio-config.json` `entry_bands` | `apply_band_update.py` (gated, via `band_refresh.py` proposals) | technical_refresh, dashboard_payload, band_note_sync, validator | Per band drift event | Script writes only via gated apply step; never direct from chain. |
| `tmp/technical-refresh.json` | `technical_refresh.py` | deployment_check, trigger_sheet_refresh, dashboard_payload, workbook_export, validator | Per chain run | Single writer. |
| `tmp/deployment-check.json` | `deployment_check.py` | trigger_sheet_refresh, dashboard_payload, workbook_export, validator | Per chain run | Single writer. |
| `tmp/trigger-sheet.json` | `trigger_sheet_refresh.py` | dashboard_payload, workbook_export | Per chain run | Single writer. |
| `tmp/dashboard-data.json` | `dashboard_payload.py` | `generate_dashboard.py`, validator | Per chain run | Single writer. |
| `tmp/veritas-command-center.html` | `generate_dashboard.py` | Operator | Per chain run | Single writer. Promote-on-pass via Phase 6 manifest. |
| `tmp/workbook-*.csv` + manifest | `workbook_export.py` | Operator (Excel) | Per chain run | Single writer. |
| `tmp/band-proposals.json` | `band_refresh.py` | `apply_band_update.py` | Per chain run | Single writer (proposal only). |
| `tmp/band-update-log.txt` | `apply_band_update.py` | Operator | Per gated apply | Single writer. |
| `tmp/band-note-sync.md` | `band_note_sync.py` | Operator | Per chain run | Read-only against canonical note. Never writes the note. |
| `tmp/run-summary-*.json` | `run_summary_refresh.py` | `dashboard_run_summary_consumer.py` | Per chain run | Single writer. |
| `02. Markets/Watchlist.md` | Operator (human prose) | Operator + audit script (Phase 3 of plan) | Per universe change | Human only. Audit script reads, never writes. |
| `03. Portfolio/Deployment Trigger Sheet.md` | Operator (human interpretation layer) | Operator | Per material change in board state | Human only. Refresh policy in Phase 4. |
| `03. Portfolio/Technical Entry and Invalidation Sheet.md` | Operator + future gated `band_note_apply.py` (dry-run-default) | Operator | After band updates | Gated writer with backup; never silent. |
| `04. Research/Coverage Universe` | Operator | Operator + Watchlist navigation | Per thesis update | Human only. |

Trust state ownership (currently fragmented — Phase 6 fix):

| Field | Today's owner | Should be |
|---|---|---|
| `dashboard-validation.json.overall` | `dashboard_validation.py` | Becomes one input to a single canonical trust resolver |
| `dashboard-acceptance-report.json.summary.all_passed` | `test_dashboard_acceptance.py` | Becomes one input |
| `run-summary-*.json.status` | `run_summary_refresh.py` | Canonical trust state lives here, derived from validation + acceptance + universe-consistency-gate |
| `workbook-export-manifest.json.overall_status` | `workbook_export.py` | Reads from canonical trust state, does not redefine |

## Decision points — operator must answer before Phase 1

These are the questions Phase 0 closes. Every "yes/no" below is a real decision, not a rhetorical one.

### D1. Direction of canonical truth between `Watchlist.md` and `portfolio-config.json`

Pick one:

- **(a) Config is canonical for machine entitlement; `Watchlist.md` is canonical for thesis prose.** Audit script (Phase 3 of plan) asserts every config ticker is mentioned in Watchlist.md and vice versa, with lane consistency. — *recommended.*
- **(b) `Watchlist.md` is canonical; config is generated/synced from it.** Requires a parser for the Watchlist table. More fragile.
- **(c) Hybrid with explicit precedence rules per field.** Most flexible, most failure modes.

**Decided:** _____

### D2. Should the machine universe expand from E17 to include AMD, LNG, TLT, SMCI?

- (yes) — adopt Table 1's proposal. Universe becomes 20 (with CVX removed) or 21 (with CVX retained).
- (no) — keep 17, but `Watchlist.md` must be edited to remove AMD, LNG, TLT, SMCI from active tracking (they become Coverage Universe research items instead).

**Decided:** _____

### D3. CVX disposition

- (a) Remove from `tracked_universe` and `entry_bands`. Drop band drift signal.
- (b) Restore CVX to `Watchlist.md` and assign it the `watch` or `macro` lane formally.

**Decided:** _____

### D4. Disputed lane assignments — confirm or override

For each, the proposal in Table 1 stands unless explicitly overridden:

- PLTR → watch (alt: speculative)
- KTOS → speculative (alt: watch)
- SLV → macro (alt: speculative)
- TLT → macro (alt: watch)
- SMCI → speculative (alt: watch)
- AMD → watch (alt: execution if user wants daily coverage)
- LNG → watch (alt: execution if user wants daily coverage)

**Overrides:** _____

### D5. Lane count — four lanes or fewer?

Table 2 proposes four lanes (execution, watch, macro, speculative). Alternatives:

- (a) Four lanes (proposal). Most expressive, slightly more dashboard surface to build.
- (b) Three lanes — collapse `macro` and `speculative` into one "non-execution tracked" lane. Simpler, loses regime/thesis distinction.
- (c) Two lanes — execution vs. watch. Loses macro and speculative semantics entirely.

**Decided:** _____

### D6. Watch-lane band drift policy

- (a) Watch-lane names get full band drift monitoring (today's behavior for PLTR/KTOS/SLV).
- (b) Watch-lane names get drift monitoring only if explicitly banded; macro/speculative do not.
- (c) Drift monitoring applies only to execution lane.

**Decided:** _____

## What Phase 1 unblocks once these decisions are made

- `coverage_lane` field added to each `tracked_universe` entry, replacing `include_in_technical_refresh` and `include_in_trigger_sheet` booleans.
- A single resolver (working name: `scripts/universe.py`) that returns lane membership and per-lane entitlements. All five downstream scripts import from it.
- `tmp/portfolio-config.json` schema migration with the new lane field; legacy booleans removed in the same change to avoid carrying both.
- Audit fixture + unit test that fails when lane semantics drift (per Veritas "contract test for universe semantics" requirement).

## What this document does not decide

- Earnings-block window logic (Phase 3).
- Macro/policy CME source repair (Phase 5.5).
- Trigger Sheet note refresh process (Phase 4).
- Manifest-gate publication design (Phase 6).
- The actual code of the resolver (Phase 1 implementation).

Each is its own deliverable with its own phase. Phase 0 only closes universe semantics.

## Freshness

- Created: 2026-04-30.
- Authored against: `Watchlist.md` (2026-04-26), `Deployment Trigger Sheet.md` (2026-04-24), `tmp/portfolio-config.json` (2026-05-01 chain run).
- Both notes were read for **operator intent**, not inherited as authoritative implementation truth — per project standard "do not mistake current note content for clean truth."
- Next update: when operator records decisions D1–D6 above. Document then becomes the Phase 0 close-out artifact and the Phase 1 input contract.
