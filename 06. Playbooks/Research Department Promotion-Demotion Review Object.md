# Research Attention Promotion-Demotion Review Object

## Purpose

Change research attention only when evidence quality, materiality, freshness cost, or expected learning value changes.

## Required fields

- candidate or market theme
- current research-attention state
- proposed state
- evidence date, freshness, and confidence
- thesis/catalyst/risk change
- source coverage and unresolved gaps
- alert relevance
- expected benefit and maintenance cost
- reviewer and next review date

## States

- `active_research`
- `monitor_only`
- `event_driven`
- `evidence_repair`
- `suppressed`
- `retired_history`

This object governs research attention, not capital or execution. It cannot create or change holdings, positions, allocations, weights, sizing, orders, accounts, or paper/live execution state.
