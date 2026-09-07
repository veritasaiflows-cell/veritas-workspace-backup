# Workbook Export Contracts

## Purpose

This contract defines the structured transport from the validated alerts-and-recommendations chain to the read-only operating workbook. JSON remains the machine proof layer, CSV is the workbook transport layer, and canonical owner files retain authority.

## Export package

Required outputs:

- `tmp/workbook-control-panel.csv`
- `tmp/workbook-alerts.csv`
- `tmp/workbook-recommendations.csv`
- `tmp/workbook-catalysts.csv`
- `tmp/workbook-evidence-freshness.csv`
- `tmp/workbook-export-manifest.json`

The manifest is mandatory. A workbook package without a current, validated manifest is suppressed.

## Generation windows

Generate only after a completed direct chain:

- `python scripts/run_alerts_recommendations_chain.py morning --timeout-seconds 120 --write --validate`
- `python scripts/run_alerts_recommendations_chain.py midday --timeout-seconds 120 --write --validate`
- `python scripts/run_alerts_recommendations_chain.py post-close --timeout-seconds 120 --write --validate`
- `python scripts/run_alerts_recommendations_chain.py weekly --timeout-seconds 120 --write --validate`

Do not export from a half-built chain or from a retired finance producer.

## Required source set

The exporter may consume only current, validated sources appropriate to the window, including:

- `03. Alerts and Recommendations/Alert Trigger Policy.md`
- `03. Alerts and Recommendations/Alert Bands and Invalidation Register.md`
- `03. Alerts and Recommendations/Alert Operations Board.md`
- `tmp/alerts-recommendations-chain-<window>.json`
- `tmp/alert-level-freshness-controller.json`
- `tmp/finance-alert-os-digest.json`
- `tmp/finance-sql-canon-access-validation.json`
- current quote, macro, catalyst, and evidence artifacts named by the chain proof

The exporter must follow recorded lineage rather than discover sources through retired boards, configuration packets, or execution-era routes.

## Common transport fields

Every CSV row includes:

- `schema_version`
- `run_id`
- `generated_at_utc`
- `source_as_of_utc`
- `source_path`
- `source_hash`
- `validation_state`

Use ISO 8601 dates and timestamps, UTF-8 encoding, `TRUE` and `FALSE` booleans, and blank cells for unavailable values. Never substitute guessed prose for missing data.

## File contracts

### `workbook-control-panel.csv`

One row per metric or warning. Required domain fields:

- `record_type`
- `metric_key`
- `metric_label`
- `metric_value`
- `severity`
- `status`
- `summary`
- `next_check`

### `workbook-alerts.csv`

One row per `ticker + timeframe`. Required domain fields:

- `ticker`
- `company`
- `timeframe`
- `coverage_lane`
- `alert_state`
- `trigger_reason`
- `band_low`
- `band_high`
- `invalidation`
- `band_relationship`
- `thesis_state`
- `catalyst_state`
- `freshness`
- `confidence`
- `next_review_at`
- `owner_pointer`

### `workbook-recommendations.csv`

One row per recommendation review item. Required domain fields:

- `recommendation_id`
- `ticker_or_theme`
- `timeframe`
- `recommendation_state`
- `thesis`
- `base_case`
- `bull_case`
- `bear_case`
- `key_risks`
- `uncertainty`
- `band_context`
- `invalidation_context`
- `decision_point`
- `suppression_reason`
- `evidence_pointer`

### `workbook-catalysts.csv`

One row per event. Required domain fields:

- `event_id`
- `ticker_or_theme`
- `event_type`
- `event_at`
- `evidence_state`
- `prior_thesis_state`
- `current_thesis_state`
- `alert_consequence`
- `unresolved_follow_up`
- `source_pointer`

### `workbook-evidence-freshness.csv`

One row per evidence object. Required domain fields:

- `evidence_id`
- `subject`
- `source_type`
- `published_at`
- `observed_at`
- `ingested_at`
- `freshness_threshold_minutes`
- `freshness`
- `confidence`
- `lineage_hash`
- `validation_reason`

## Manifest contract

`workbook-export-manifest.json` must include:

- `schema_version`
- `run_id`
- `generated_at_utc`
- `chain_window`
- `chain_status`
- `overall_status`
- source paths, hashes, and as-of times
- each export path, row count, hash, and validation state
- warnings, errors, and suppression reasons

## Failure behavior

- Missing required source: do not fabricate rows; suppress the affected export.
- Stale required source: mark rows and manifest `Stale`; suppress recommendations when the active freshness policy requires it.
- Hash or lineage mismatch: fail closed and preserve the last valid package.
- Partial optional evidence: emit only when the conclusion remains honest, with `Warning` or `Blocked` state.
- Schema mismatch or duplicate row key: fail the package.
- Write exports atomically so readers never see a partial package.

## Non-execution boundary

Exports must not contain or maintain system-owned sleeves, holdings or positions, allocation or weight state, sizing or tranche plans, cash state, order packages, transaction instructions, or paper/live execution routes. Recommendation rows are non-executing review records only.

## Acceptance

The package passes only when:

- all required files and manifest entries exist
- schema and unique-key validation pass
- hashes match the files read by the workbook
- freshness and confidence are visible
- stale, missing, or conflicting evidence cannot false-green
- canonical bands and invalidations are unchanged
- every recommendation has traceable evidence and a decision point
- no prohibited state or route appears in any export
