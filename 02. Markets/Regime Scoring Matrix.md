# Regime Scoring Matrix

## Purpose

Rank market, sector, and theme evidence for attention. A score means review priority, never action authority.

## Scoring Dimensions

| Dimension | Question |
|---|---|
| Macro fit | Does the current growth, inflation, rates, credit, and liquidity evidence support the thesis? |
| Leadership | Is relative strength broad, durable, and supported by fundamentals? |
| Catalyst quality | Is there a dated, material catalyst with reliable evidence? |
| Risk clarity | Are downside paths and invalidation conditions explicit? |
| Freshness | Are prices, evidence, and source lineage current enough for the requested timeframe? |

## Review States

- `recommendation_review`
- `band_entry`
- `near_band`
- `no_chase`
- `invalidation_alert`
- `thesis_change`
- `catalyst_alert`
- `freshness_decay`
- `monitor_only`
- `suppressed`

Ticker-level thresholds and current state belong to `03. Alerts and Recommendations/Alert Bands and Invalidation Register.md`. Generic trigger definitions belong to `03. Alerts and Recommendations/Alert Trigger Policy.md`.

## Boundary

This matrix owns attention ranking only. It does not own account, capital, order, execution, or simulated-account state and cannot grant approval.
