---
name: "veritas-fundamental-pass"
description: "Produce source-backed fundamental research for non-executing recommendations."
---

# Veritas Fundamental Pass

## Purpose

Produce disciplined public-equity research that can support an alert or non-executing recommendation. Separate business quality from price/timing quality and expose evidence gaps.

## First Route

```powershell
python scripts\finance_sql_canon_access.py --write --validate
python scripts\run_alerts_recommendations_chain.py midday --timeout-seconds 120 --write --validate
```

Use guarded state for routing and open official evidence for material claims. Prefer issuer IR, SEC filings, and official releases; use reputable market sources for context and media only for interpretation.

## Required Analysis

For each company cover:

- resolved entity, listing, and country
- evidence dates and source hierarchy
- revenue, earnings, margin, and cash-flow trend
- balance-sheet resilience
- company capital-allocation quality
- valuation and assumptions embedded in price
- competitive position and industry risks
- recent catalysts and guidance
- base, bull, and bear cases
- fastest thesis breakers
- confidence, freshness, conflicts, and missing fields

Company capital allocation and order backlog are business evidence; they are not account or portfolio state.

## Recommendation Labels

Use recommendation-risk/time-horizon labels such as:

- high-quality long-horizon candidate
- tactical/cyclical candidate
- speculative/high-uncertainty candidate
- income-oriented candidate
- monitor only
- avoid / thesis impaired

These labels do not create system-owned sleeves.

## Output

### SYMBOL — Fundamental Verdict

- Entity:
- Verdict:
- Timeframe:
- Evidence as of:
- Freshness / confidence:
- Business quality:
- Balance sheet:
- Cash flow:
- Valuation:
- Thesis:
- Base / bull / bear:
- Risks and thesis breakers:
- Catalyst:
- Technical/threshold context:
- Recommendation:
- Randall's decision point:

For multi-name work, rank by business quality, balance-sheet resilience, cash-flow durability, valuation discipline, evidence quality, and thesis risk.

## Truth Rules

- Never fabricate a metric; use NA and explain the impact.
- A source conflict lowers confidence and routes repair.
- Strong fundamentals do not override No chase, Invalidation alert, event risk, or stale market evidence.
- A cached summary cannot replace current official evidence for a material claim.
- Owner objectives may inform judgment transiently but are not maintained as account state.

## Boundary

No maintained holdings, positions, sleeves, allocations, weights, sizing, tranches, cash, rebalancing, simulated positions, order packages, account reads, or execution. The output is research and recommendation support only.
