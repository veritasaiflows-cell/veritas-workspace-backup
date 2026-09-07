# Macro Regime Dashboard

## Purpose

Provide market and sector context for alerts and recommendations. This surface does not own finance action state.

## Current Evidence Routes

- `tmp/macro-inputs-refresh-cron-runner.json`
- `tmp/macro-metrics-current.json`
- `tmp/macro-signal-spine.json`
- `tmp/macro-energy-supply.json`
- `tmp/macro-geopolitical-sweep.json`
- `tmp/macro-judgment-draft.json`

The scheduled macro refresh is the freshness owner for these inputs. A scheduler-green result proves the runner completed; warnings inside an artifact remain visible and must be carried into any material recommendation.

## Interpretation Contract

For each material macro conclusion, state:

- evidence date and source lineage
- freshness and confidence
- base, upside, and downside regime paths
- affected sectors or themes
- alert or recommendation implications
- what would invalidate the interpretation

Do not convert macro context into maintained account or execution state. Owner-provided objectives or limits may inform a recommendation transiently but are not stored here.

## Freshness Rule

If the required macro inputs are stale, missing, internally inconsistent, or warning-grade, say so and suppress precision that the evidence does not support. Older authored observations are historical context only; they do not become current merely because this file exists.
