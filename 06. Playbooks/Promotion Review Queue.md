# Recommendation Review Queue

Status: active alerts-and-recommendations replacement. The former execution-lane promotion queue and its static candidate rows were retired on 2026-08-29.

## Purpose

Route names or themes that need human review because evidence, freshness, thesis, catalyst, band, invalidation, or recommendation confidence changed.

## Source of current state

Current review state comes from:

- `03. Alerts and Recommendations/Alert Trigger Policy.md`
- `03. Alerts and Recommendations/Alert Bands and Invalidation Register.md`
- `tmp/alert-level-freshness-controller.json`
- `tmp/finance-alert-os-digest.json`

This file does not duplicate ticker rows or become a second current-state database.

## Review object

Each queued review states:

- ticker or market theme
- timeframe and evidence date
- alert state and reason for review
- freshness and confidence
- thesis and strongest disconfirming evidence
- catalyst, band, and invalidation context
- base, bull, and bear interpretation when material
- unresolved risk or contradiction
- Randall's decision point, if one exists

Allowed outcomes are `recommendation_review`, `band_entry`, `near_band`, `no_chase`, `invalidation_alert`, `thesis_change`, `catalyst_alert`, `freshness_decay`, `monitor_only`, and `suppressed`.

## Boundary

A review row is evidence only. It does not create or maintain sleeves, holdings, positions, allocations, weights, sizing, tranches, cash, rebalancing, simulated positions, orders, accounts, money movement, or execution authority. A recommendation never implies approval.
