---
name: "veritas-macro-pass"
description: "Produce evidence-backed macro alerts and recommendation implications."
---

# Veritas Macro Pass

## Purpose

Describe the current macro regime, what changed, evidence quality, and implications for market/sector alerts and non-executing recommendations. Macro is context, not a transaction signal.

## Sources

Start with the current macro metrics, signal spine, judgment draft, official releases, and the current alerts digest. Treat slow-moving valuation indicators as backdrop, not timing proof. Identify manual, partial, stale, or conflicting inputs explicitly.

## Evidence Refresh Chain

For FOMC and macro review refreshes, refresh live macro evidence in dependency order:

```powershell
python scripts\policy_expectations_refresh.py
python scripts\credit_spread_refresh.py
python scripts\breadth_refresh.py
python scripts\macro_regime_refresh.py
```

- `macro_regime_refresh.py` does not read market state (docstring reference only); it needs current credit and breadth and reuses existing macro metrics and signal-spine artifacts.
- Macro ingest and signal-spine consumers degrade gracefully without market state and label any proxy fallback explicitly.

Never run `scripts/market_state_refresh.py` and never recreate `tmp/market-state.json`: it is a retired portal/paper current-state path (2026-08-29 finance runtime retirement), and `scripts/alerts_os_pivot_validator.py` treats any recreated copy as a retired-state error that cascades blocked status into cron jobs. After any manual macro refresh, verify:

```powershell
python scripts\alerts_os_pivot_validator.py --write --validate
```

If a retired path was recreated, quarantine it (precedent: `tmp/quarantine/2026-09-20-cron-repair/`) and rerun the validator until clean.

## Required Analysis

- regime label and timeframe
- rates and liquidity
- inflation and growth
- labor and credit
- volatility, breadth, and risk appetite
- energy, commodities, and geopolitics
- major catalysts
- what changed
- invalidation triggers
- source dates, freshness, and confidence

Prefer official central-bank and government releases, then reliable market data, then reputable reporting for context.

## Alert Implications

Translate the regime into:

- broad market alert implications
- sector/theme implications
- thesis or catalyst changes
- risk and uncertainty adjustments
- names or themes that warrant Recommendation review, Monitor only, or Suppressed
- evidence repairs required before a stronger conclusion

Do not translate macro into maintained account posture.

## Output

## Macro regime verdict

- Regime:
- Timeframe:
- Evidence as of:
- Freshness / confidence:
- Main drivers:
- Main risks:
- Rates and liquidity:
- Inflation and growth:
- Volatility and breadth:
- Energy / commodities / geopolitics:
- What changed:
- Market and sector alert implications:
- Invalidation triggers:
- Randall's decision point:

## Truth Rules

Mixed evidence gets mixed language. Manual dependencies must be visible. A clean macro backdrop cannot override stale ticker evidence, No chase, Invalidation alert, or unresolved thesis risk.

## Boundary

No system-owned sleeves, holdings, positions, allocations, weights, sizing, tranches, cash posture, rebalancing, simulated positions, orders, account reads, or execution. Owner-provided objectives may inform a response transiently but are never maintained here.
