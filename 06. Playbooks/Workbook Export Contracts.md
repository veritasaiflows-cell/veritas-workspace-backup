# Workbook Export Contracts

## Purpose

Define the structured export layer that feeds the minimum-viable Veritas operating workbook.

This document specifies:
- which exports exist
- which workbook tab each export feeds
- the required columns
- the source artifacts
- normalization and status-mapping rules
- failure and freshness behavior

This is the bridge between:
- current `tmp/*.json` artifacts
- future workbook-ready CSV outputs

---

## Core architecture rule

The workbook should not parse raw JSON directly.

Use this path:
1. script chain generates canonical JSON artifacts
2. export layer normalizes those artifacts into workbook-ready CSVs
3. workbook tabs ingest those CSVs

Blunt rule:
- JSON is for machines
- CSV is for workbook transport
- notes remain the judgment layer

---

## Export package

The MVP workbook uses 5 CSV exports:

1. `tmp/workbook-control-panel.csv`
2. `tmp/workbook-watchlist-board.csv`
3. `tmp/workbook-deployment-ranking.csv`
4. `tmp/workbook-earnings-tracker.csv`
5. `tmp/workbook-technical-drift.csv`

Optional metadata sidecar:
- `tmp/workbook-export-manifest.json`

The manifest is recommended but not required for v1.
It should eventually capture export timestamps, source timestamps, row counts, and export status.

---

## Export timing

Default generation points:
- after `python scripts/validate_dashboard_state.py --write`
- after `run_finance_refresh_chain.py morning`
- after `run_finance_refresh_chain.py post-close`
- after `run_finance_refresh_chain.py post-earnings`
- after `run_finance_refresh_chain.py sunday`

Hard rule:
- exports should be generated from already-finished artifact sets
- do not emit workbook exports from half-built chains

---

## Global field rules

### Common metadata fields

Every export should include these when applicable:
- `export_generated_at_utc`
- `source_last_trading_day`
- `validation_grade`
- `data_status`

### Null handling

- use empty string for unknown text fields
- use empty cell for unavailable numeric fields
- use `TRUE` / `FALSE` for booleans
- do not use placeholder prose like `N/A maybe` or `unknown?`

### Date handling

- use ISO date format: `YYYY-MM-DD`
- use UTC timestamps for export metadata fields

### Column stability rule

Once an export contract is adopted, do not casually rename columns.
Add columns only when needed and preserve backwards compatibility where practical.

---

## Status normalization rules

Map raw artifact language into workbook vocabularies.

### `board_state`
Normalize to:
- `Deployable`
- `Almost deployable`
- `Blocked`
- `Bench`
- `Repair`
- `Do not touch`

Recommended mapping examples:
- `DEPLOYABLE NOW` / `DEPLOYABLE` -> `Deployable`
- `ALMOST DEPLOYABLE` / `ALMOST` -> `Almost deployable`
- `BLOCKED` -> `Blocked`
- `WATCH` or `WATCH / RESEARCH NEEDED` -> `Bench` unless a stronger manual mapping exists
- `BELOW STOP` / broken posture -> `Do not touch`
- explicit repair-mode note logic -> `Repair`

### `earnings_state`
Normalize to:
- `Upcoming`
- `Reported, evidence pending`
- `Interpreted`
- `Synced`
- `Closed with follow-up`

### `trust_grade`
Normalize to:
- `Clean`
- `Usable with caution`
- `Partial`
- `Stale`

Recommended mapping:
- validation `ok` / no warnings -> `Clean`
- validation warning-only state -> `Usable with caution`
- partial artifact state -> `Partial`
- stale freshness breach -> `Stale`

### `review_flag`
Normalize to:
- `None`
- `Review needed`
- `Stale`
- `Blocked by catalyst`
- `Manual check required`

---

## Export 1 — Control Panel

### Output file
- `tmp/workbook-control-panel.csv`

### Workbook tab
- `Control Panel`

### Granularity
- small KPI table plus warning rows

### Recommended shape
Use one file with row `record_type` values:
- `kpi`
- `warning`

Alternative two-file split is acceptable later, but v1 should stay simple.

### Required columns
| Column | Type | Source | Notes |
|---|---|---|---|
| record_type | text | export layer | `kpi` or `warning` |
| metric_key | text | export layer | stable key |
| metric_label | text | export layer | readable label |
| metric_value | text | mixed | stringify KPI value for easy workbook ingest |
| severity | text | validation/export | blank for KPI rows |
| summary | text | validation/export | warning summary |
| action_needed | text | derived/manual mapping | next step |
| export_generated_at_utc | datetime | export layer | |
| source_last_trading_day | date | artifacts | |
| validation_grade | text | normalized | |
| data_status | text | export layer | `ok`, `warning`, `partial`, `stale` |

### Source stack
- `tmp/dashboard-validation.json`
- `tmp/trigger-sheet.json`
- `tmp/macro-regime.json`
- `tmp/policy-expectations.json`
- `tmp/earnings-calendar.json`
- `tmp/technical-refresh.json`

### KPI rows to emit
At minimum:
- `refresh_timestamp`
- `validation_grade`
- `critical_count`
- `warning_count`
- `actionable_count`
- `blocked_count`
- `extended_count`
- `repair_count`
- `stale_band_count`
- `near_earnings_count`
- `macro_regime`
- `policy_mode`

### Warning rows to emit
One row per major warning from validation, preserving:
- code
- severity
- message
- derived `action_needed`

---

## Export 2 — Watchlist Operating Board

### Output file
- `tmp/workbook-watchlist-board.csv`

### Workbook tab
- `Watchlist Operating Board`

### Granularity
- one row per tracked ticker

### Required columns
| Column | Type | Source |
|---|---|---|
| ticker | text | canonical / trigger |
| company | text | portfolio config or future lookup |
| coverage_tier | text | trigger-sheet |
| sleeve | text | portfolio role mapping |
| board_state | text | normalized from trigger/deployment state |
| deployability_label | text | trigger-sheet action state |
| nearest_catalyst_date | date | trigger-sheet / earnings artifact |
| catalyst_type | text | derived |
| earnings_blocked | boolean | technical/trigger |
| thesis_status | text | trigger-sheet |
| technical_freshness | text | derived from band/validation state |
| priority_bucket | text | optional derived/manual; blank if unavailable |
| canonical_note_pointer | text | derived/manual mapping |
| last_sync_date | date | export day or future workflow output |
| notes_short | text | short operational note |
| export_generated_at_utc | datetime | export layer |

### Source stack
- `tmp/trigger-sheet.json`
- `tmp/technical-refresh.json`
- `tmp/earnings-calendar.json`
- future structured watchlist export if added later

### Notes
- `company` may require a future ticker metadata source; allow blank in v1 if not readily available
- `canonical_note_pointer` can default to the owning note class in v1, then become ticker-specific later
- `board_state` should not preserve raw all-caps machine labels directly

---

## Export 3 — Deployment Ranking

### Output file
- `tmp/workbook-deployment-ranking.csv`

### Workbook tab
- `Deployment Ranking`

### Granularity
- one row per tracked ticker or active candidate

### Required columns
| Column | Type | Source |
|---|---|---|
| ticker | text | canonical |
| board_state | text | normalized |
| distance_to_band_pct | decimal | derived |
| entry_band_low | decimal | trigger-sheet entry band |
| entry_band_high | decimal | trigger-sheet entry band |
| technical_readiness | text | derived from posture + in-band + stop state |
| earnings_catalyst_risk | text | derived from earnings proximity/blocker |
| macro_fit | text | trigger-sheet |
| invalidation_clarity | text | derived/manual from invalidation presence |
| portfolio_role | text | trigger-sheet |
| priority_rank | integer | blank/manual in v1 unless ranking logic exists |
| priority_bucket | text | blank/manual in v1 unless ranking logic exists |
| reason_for_rank | text | blank/manual in v1 unless ranking logic exists |
| next_trigger | text | trigger-sheet technical trigger |
| export_generated_at_utc | datetime | export layer |

### Source stack
- `tmp/trigger-sheet.json`
- `tmp/technical-refresh.json`
- `tmp/deployment-check.json` when useful
- future positioning export when available

### Derived rules
- `distance_to_band_pct` should be negative when below band, zero-ish when in band, positive when above band if that best matches current math convention — pick one convention and document it in code
- `technical_readiness` should compress raw posture into readable operator language such as `In band`, `Near band`, `Extended`, `Blocked`, `Broken`
- leave ranking fields blank rather than inventing fake precision if no real ranking model exists yet

---

## Export 4 — Earnings Workflow Tracker

### Output file
- `tmp/workbook-earnings-tracker.csv`

### Workbook tab
- `Earnings Workflow Tracker`

### Granularity
- one row per `ticker + quarter`

### Required columns
| Column | Type | Source |
|---|---|---|
| ticker | text | earnings packet |
| company | text | future metadata source; blank allowed in v1 |
| quarter | text | derived from packet/note context |
| report_date | date | earnings packet |
| earnings_state | text | normalized workflow state |
| ir_confirmed | boolean | manual/verified or false/blank |
| scorecard_created | boolean | note existence check |
| interpreted | boolean | derived from note/workflow state |
| board_synced | boolean | derived from note-target completion or blank in v1 |
| follow_up_open | boolean | derived/manual |
| next_required_action | text | workflow-driven |
| owner_note | text | scorecard path |
| deployment_impact | text | short judgment / blank in v1 |
| technical_impact | text | short judgment / blank in v1 |
| unresolved_issue | text | warning or follow-up |
| export_generated_at_utc | datetime | export layer |

### Source stack
- `tmp/post-earnings-prep.json`
- `tmp/post-earnings-note-targets.json`
- `tmp/earnings-calendar.json`
- `05. Intelligence/Earnings/` note existence checks

### Derived rules
- if packet stage is pre-report or upcoming -> `Upcoming`
- if report day hit but interpretation slots are still pending -> `Reported, evidence pending`
- if scorecard exists and interpretation is filled but broader sync incomplete -> `Interpreted`
- if board sync completed -> `Synced`
- if synced with remaining follow-up item -> `Closed with follow-up`

Hard truth:
- some of these fields require future workflow instrumentation to become fully reliable
- v1 can emit honest blanks rather than fake completion status

---

## Export 5 — Entry Bands and Technical Drift

### Output file
- `tmp/workbook-technical-drift.csv`

### Workbook tab
- `Entry Bands and Technical Drift`

### Granularity
- one row per tracked ticker

### Required columns
| Column | Type | Source |
|---|---|---|
| ticker | text | canonical |
| current_price | decimal | technical-refresh |
| entry_band_low | decimal | trigger-sheet |
| entry_band_high | decimal | trigger-sheet |
| stop_invalidation | decimal | trigger-sheet |
| distance_to_band_pct | decimal | derived |
| stale_flag | boolean | derived from validation / future band artifact |
| review_flag | text | normalized |
| last_band_update | date | band log / future instrumentation |
| note_owner | text | technical note path |
| posture | text | derived |
| comments_short | text | warning/context |
| export_generated_at_utc | datetime | export layer |

### Source stack
- `tmp/technical-refresh.json`
- `tmp/trigger-sheet.json`
- `tmp/dashboard-validation.json`
- `tmp/band-proposals.json` when available
- `tmp/band-update-log.txt` when structured enough to read

### Derived rules
- if ticker appears in `band_staleness` warning set -> `stale_flag=TRUE` and `review_flag=Stale`
- if earnings block is active and technical work should pause -> `review_flag=Blocked by catalyst`
- if entry band missing -> `review_flag=Manual check required`
- otherwise review flag can be `None` or `Review needed` depending on future band proposal status

---

## Optional manifest export

### Output file
- `tmp/workbook-export-manifest.json`

### Purpose
Track export-level health.

### Suggested fields
- `generated_at_utc`
- `overall_status`
- `source_files`
- `exports`
  - file path
  - row count
  - status
- `warnings`

This will help debugging and later cron/workflow automation.

---

## Failure behavior

### Hard failure
If a required source artifact is missing for an export:
- do not fabricate rows
- emit either no file or a file with explicit `data_status=partial`
- log the missing-source condition in the manifest if manifest exists

### Soft failure
If some fields are unavailable but core row generation is still possible:
- emit the export
- leave unavailable fields blank
- preserve `data_status=warning` or `partial`

### Staleness failure
If source artifacts breach freshness thresholds:
- keep export generation allowed when still useful
- set `data_status=stale`
- surface that clearly in control-panel export and manifest

---

## Recommended implementation path

1. create one export script, e.g. `scripts/workbook_export.py`
2. read existing artifacts through shared safe loaders
3. normalize statuses once in code, not separately per tab
4. emit the 5 CSVs
5. optionally emit manifest JSON
6. add the export script after validation in the relevant chain windows

Do not spread workbook export logic across many tiny scripts unless there is a strong reason.
One export orchestrator is cleaner.

---

## Acceptance criteria

The export layer is good enough only if:
- all 5 CSVs can be generated from the current artifact stack
- raw machine labels are normalized into workbook vocabularies
- missing data stays visibly missing instead of being guessed
- the control-panel export surfaces current warning pressure honestly
- the earnings tracker can reveal unfinished closure work
- the technical drift export can reveal stale-band pressure

If the exports hide uncertainty, the workbook layer will become misleading.

---

## Bottom line

The export layer should make the workbook easy to build and hard to lie with.

If it simply mirrors messy JSON one-for-one, it failed.
If it normalizes the current OS into stable operator tables, it worked.
