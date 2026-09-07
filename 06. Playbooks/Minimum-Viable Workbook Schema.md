# Minimum-Viable Workbook Schema

## Purpose

This schema defines the smallest useful workbook for the alerts-and-recommendations OS. It is a read-only projection of validated artifacts, not a source of canonical judgment or action authority.

## Global requirements

Every data row must include, where applicable:

- `schema_version`
- `run_id`
- `generated_at_utc`
- `source_as_of_utc`
- `source_path`
- `source_hash`
- `validation_state`

Dates use ISO 8601. Unknown values remain blank and are accompanied by an explicit warning when required for interpretation.

## Sheet 1 — Control Panel

Row key: `metric_key`

Required columns:

| Column | Type | Meaning |
|---|---|---|
| metric_key | text | Stable machine key |
| metric_label | text | Human-readable label |
| metric_value | text | Current value |
| severity | enum | `Info`, `Warning`, or `Critical` |
| status | enum | `Ok`, `Warning`, `Blocked`, or `Suppressed` |
| summary | text | Concise explanation |
| next_check | text | Bounded follow-up |

Required metrics include chain status, validation status, source cutoff, alert counts by state, freshness-decay count, suppressed count, and evidence-gap count.

## Sheet 2 — Alerts

Row key: `ticker + timeframe`

Required columns:

| Column | Type | Meaning |
|---|---|---|
| ticker | text | Instrument identifier |
| company | text | Display name |
| timeframe | text | Review horizon |
| coverage_lane | text | Research or theme lane |
| alert_state | enum | Active controlled alert state |
| trigger_reason | text | Why the state applies |
| band_low | decimal | Guarded canonical lower level |
| band_high | decimal | Guarded canonical upper level |
| invalidation | decimal/text | Guarded canonical invalidation context |
| band_relationship | text | In, near, above, below, or unavailable |
| thesis_state | text | Current thesis condition |
| catalyst_state | text | Current catalyst condition |
| freshness | enum | `Fresh`, `Aging`, `Stale`, or `Unknown` |
| confidence | enum | `High`, `Medium`, `Low`, or `Unrated` |
| next_review_at | datetime | Next required review |
| owner_pointer | text | Canonical owner path |

## Sheet 3 — Recommendations

Row key: `recommendation_id`

Required columns:

| Column | Type | Meaning |
|---|---|---|
| recommendation_id | text | Stable review identifier |
| ticker_or_theme | text | Subject |
| timeframe | text | Intended review horizon |
| recommendation_state | enum | Review, monitor, no-chase, suppressed, or invalidated state |
| thesis | text | Concise evidence-backed view |
| base_case | text | Central scenario |
| bull_case | text | Constructive scenario |
| bear_case | text | Adverse scenario |
| key_risks | text | Material risks |
| uncertainty | text | Known limits or missing proof |
| band_context | text | Relevant canonical band relationship |
| invalidation_context | text | What would break the view |
| decision_point | text | Randall's explicit review question |
| suppression_reason | text | Required when suppressed |
| evidence_pointer | text | Evidence lineage route |

## Sheet 4 — Catalysts and Thesis Changes

Row key: `event_id`

Required columns:

| Column | Type | Meaning |
|---|---|---|
| event_id | text | Stable event identifier |
| ticker_or_theme | text | Subject |
| event_type | text | Earnings, policy, macro, company, technical, or other catalyst |
| event_at | datetime | Expected or observed time |
| evidence_state | text | Confirmed, pending, conflicting, or stale |
| prior_thesis_state | text | State before the event |
| current_thesis_state | text | State after review |
| alert_consequence | text | Resulting alert state |
| unresolved_follow_up | text | Required next evidence step |
| source_pointer | text | Evidence source |

## Sheet 5 — Evidence and Freshness

Row key: `evidence_id`

Required columns:

| Column | Type | Meaning |
|---|---|---|
| evidence_id | text | Stable evidence identifier |
| subject | text | Covered ticker, theme, or signal |
| source_type | text | Filing, IR, market, macro, research, or canon |
| published_at | datetime | Original publication time |
| observed_at | datetime | Observation time |
| ingested_at | datetime | System ingestion time |
| freshness_threshold_minutes | integer | Allowed age |
| freshness | enum | `Fresh`, `Aging`, `Stale`, or `Unknown` |
| confidence | enum | `High`, `Medium`, `Low`, or `Unrated` |
| lineage_hash | text | Content or lineage hash when available |
| validation_state | enum | `Ok`, `Warning`, `Blocked`, or `Suppressed` |
| validation_reason | text | Failure or warning explanation |

## Non-execution boundary

No sheet or hidden range may contain or maintain system-owned sleeves, holdings or positions, allocation or weight state, sizing or tranche plans, cash state, order packages, transaction instructions, or paper/live execution routes. Owner-provided objectives or limits may appear only as transient recommendation context and never as maintained state.

## Acceptance criteria

- Required columns exist with stable names and types.
- Row keys are unique within each export.
- All material rows carry source time, validation state, and lineage.
- Stale or incomplete sources cannot appear as clean.
- Canonical bands and invalidations remain unchanged by export.
- Suppressed recommendations include a reason.
- No prohibited state or route appears anywhere in the workbook.
