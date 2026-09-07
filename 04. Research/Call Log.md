# Alert and Recommendation Outcome Log

## Purpose

Track material, non-executing recommendations against later evidence so the research process can be evaluated without creating or maintaining holdings, simulated positions, orders, or account state.

## Logging rule

Log only a recommendation that states:

- ticker or market subject;
- recommendation timestamp and timeframe;
- evidence date, source lineage, and freshness state;
- thesis and thesis breakers;
- base, bull, and bear cases;
- canonical band/invalidation context when relevant;
- confidence and uncertainty;
- recommendation-review state and Randall's decision point.

An outcome review measures whether the stated thesis and risks were borne out within the stated timeframe. It does not assume a transaction occurred and does not calculate hypothetical account or position performance.

## Outcome states

- `pending_evidence`
- `thesis_supported`
- `thesis_weakened`
- `thesis_invalidated`
- `inconclusive`
- `freshness_blocked`

## Required controls

- preserve the original evidence date and recommendation wording;
- append later evidence rather than rewriting the original judgment;
- distinguish market movement from thesis validation;
- record missing or stale evidence explicitly;
- suppress precision that the source set cannot support;
- review process bias and calibration at least quarterly.

## Authority boundary

This log is research-quality evidence only. It does not own or infer capital, holdings, positions, allocations, weights, sizing, cash, simulated trades, orders, execution, brokerage/account state, or owner approval.

Legacy execution-board call records were retired during the 2026-08-29 alerts-and-recommendations OS cutover and are available only through repository history or the retirement archive.
