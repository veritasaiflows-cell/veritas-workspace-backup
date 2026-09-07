---
name: "veritas-technical-pass"
description: "Produce evidence-backed technical alerts and non-executing recommendations."
---

# Veritas Technical Alert Pass

## Purpose

Turn current market evidence into a disciplined technical alert or non-executing recommendation. Use exact, source-backed thresholds and state uncertainty plainly.

## First Route

```powershell
python scripts\finance_sql_canon_access.py --write --validate
python scripts\run_alerts_recommendations_chain.py midday --timeout-seconds 120 --write --validate
```

Read:

- `03. Alerts and Recommendations\Alert Bands and Invalidation Register.md`
- `03. Alerts and Recommendations\Alert Trigger Policy.md`
- the current quote snapshot
- `tmp\alert-level-freshness-controller.json`
- the relevant daily or weekly digest

Static levels come from guarded canon. Do not re-derive or auto-apply them. If quote, level, timestamp, or lineage proof is stale or missing, return Freshness decay or Suppressed.

## Alert States

Use only the active vocabulary:

- Recommendation review
- Band entry
- Near band
- No chase
- Invalidation alert
- Thesis change
- Catalyst alert
- Freshness decay
- Monitor only
- Suppressed

These are information states, not action authority.

## Required Evidence

Capture:

- symbol and asset type
- quote and evidence timestamp
- source lineage and freshness
- timeframe
- trend and moving-average context when reliably sourced
- meaningful support and resistance
- guarded band and invalidation threshold
- catalyst timing
- thesis, counter-thesis, and material risks
- confidence and uncertainty

Never fabricate a precise value. If the source does not support it, label the gap and suppress any precise claim.

## Decision Rules

- A strong business can still be No chase or Monitor only.
- Band entry requires a current quote and a valid guarded threshold.
- Near band must state distance and the freshness window.
- A threshold breach becomes Invalidation alert; it does not infer a transaction.
- Event risk may suppress a recommendation even when price is near a band.
- Conflicting sources reduce confidence and route evidence repair.
- Company quality and technical timing remain distinct.

## Output

### SYMBOL

- Alert state:
- Timeframe:
- Quote / as of:
- Freshness / confidence:
- Thesis:
- Technical context:
- Band / invalidation:
- Catalyst:
- Base / bull / bear:
- Risks and uncertainty:
- Recommendation:
- Randall's decision point:

Keep the recommendation non-executing and explain why the state changed.

## Ranking

Rank names by evidence quality, freshness, thesis durability, risk, and timing quality. Do not rank by maintained account exposure or system-owned portfolio structure. Owner-provided objectives or limits may be used transiently and must be identified as owner context.

## Boundary

No system-owned sleeves, holdings, positions, allocations, weights, sizing, tranches, cash, rebalancing, simulated positions, order preparation, account reads, or execution. This skill never writes guarded levels or infers capital approval.

## Validation

```powershell
python scripts\finance_sql_canon_access.py --write --validate
python scripts\run_alerts_recommendations_chain.py midday --timeout-seconds 120 --write --validate
python scripts\alerts_os_pivot_validator.py --write --validate
```

Report any freshness degradation truthfully; a validator is green only for what it actually checks.
