# Alert and Recommendation Risk Rules

## Ownership and freshness

- **Owner:** alerts-and-recommendations OS
- **Pivot reviewed:** 2026-08-29
- **Scope:** recommendation risk, evidence quality, alert escalation, and uncertainty
- **Review cadence:** weekly and after a material regime, thesis, catalyst, provenance, or freshness change
- **Freshness rule:** a same-window review resets freshness only when recorded explicitly; silent carry-forward does not count

## Core rules

- Capital preservation is a recommendation objective, never system-owned capital state.
- Every material recommendation states timeframe, evidence date, confidence, downside, and invalidation.
- Distinguish company quality, thesis quality, setup quality, and alert-band quality.
- Avoid obscure, illiquid, unregistered, or weakly sourced instruments.
- Treat leverage, options, and speculative crypto as elevated-risk research domains.
- Missing, stale, conflicted, or hash-mismatched evidence emits `freshness_decay` and blocks a high-confidence recommendation.
- A written band is decision-support metadata, not an instruction or entitlement.

## Recommendation risk labels

- **Lower:** strong lineage, current evidence, clear thesis, bounded downside, and clean invalidation context.
- **Moderate:** credible thesis with one material timing, catalyst, valuation, or evidence uncertainty.
- **High:** speculative thesis, weak liquidity, major catalyst exposure, unclear invalidation, stale evidence, or conflicting sources.
- **Suppressed:** evidence is insufficient or the request crosses the OS boundary.

These labels do not create holdings, allocations, weights, sizing, tranches, cash posture, orders, or execution authority.

## Escalation triggers

- material thesis impairment
- major macro or geopolitical regime change
- circuit breaker, trading halt, or abnormal volatility
- current price breaches a written invalidation threshold
- catalyst timing materially changes uncertainty
- source lineage, timestamp, or hash cannot be verified
- evidence sources conflict on a decision-relevant fact
- a request requires capital, order, brokerage/account, money movement, or execution action

## Review standard

Ask:

- Is the thesis intact and supported by current evidence?
- What changed since the last review?
- What is the strongest disconfirming evidence?
- What invalidates the thesis or alert interpretation?
- Is the latest price current for the market session being described?
- Is the name inside, near, above, or below its written alert band?
- Is no-chase discipline required?
- What uncertainty should Randall see before deciding?

## Boundary

This file does not maintain or authorize sleeves, holdings, positions, allocations, weights, sizing, tranches, cash, rebalancing, simulated positions, order packages, brokerage/account action, money movement, or paper/live execution.
