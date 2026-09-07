# Quality Bench: Bond / Cash Reserve Lane

- Generated: 2026-05-17 22:05 MST
- Status: review-only allocation recommendation
- Scope: recommended structure for the preserved 10% account-level reserve in the 40% ETF / 60% stock proposal
- Trade/account authority: none. This is not an order, allocation approval, or brokerage instruction.

## Conclusion

For the preserved 10% reserve, use a **cash-first ballast sleeve**, not a yield-chasing credit sleeve. The current regime is restrictive pause / resilient growth / selective risk-on with benign credit and broad-but-deteriorating breadth; that supports modest duration diversification, but not treating high yield as cash.

Recommended reserve mix:

| Reserve role | Suggested weight of account | Share of 10% reserve | Candidate vehicles / proxies | Rationale | State |
|---|---:|---:|---|---|---|
| T-bill / cash-like core | 6.0% | 60% | SGOV / BIL / SHV | Highest confidence reserve role; yields about 3.92%-3.95%; low duration; preserves dry powder. | Preferred core |
| Short-duration Treasury | 2.0% | 20% | SHY | Modest step-out from T-bills; yield about 3.72%; limited rate sensitivity. | Useful ballast |
| Intermediate Treasury / aggregate bond | 1.0% | 10% | IEI / IEF / AGG / BND | Adds recession/risk-off convexity; yields about 3.58%-3.95%, but more duration mark-to-market risk. | Small diversifier |
| TIPS / inflation hedge | 1.0% | 10% | TIP / SCHP | Energy/inflation sensitivity remains relevant with Brent/WTI elevated; yields cited about 2.77%-3.68%; useful but not dominant. | Small diversifier |
| High-yield credit | 0.0% active reserve; watch only | 0% | HYG / JNK | Yields about 5.82%-6.59%, but this is credit beta, not cash. Benign spreads reduce urgency; do not use as reserve ballast. | Watch / separate risk sleeve only |

## Why this mix

- **Reserve purpose:** preserve optionality and reduce forced selling risk while the 40/60 risk-asset model remains review-only and source/validator gated.
- **Policy backdrop:** Fed target 3.50%-3.75%, hold probability 100%, next FOMC 2026-06-17. Cash-like T-bills still pay enough to justify patience.
- **Curve/duration:** 10Y around 4.595% vs 2Y around 3.82% and 3M T-bill around 3.588%; intermediate duration can help if growth/risk rolls over, but should not dominate the reserve.
- **Credit:** HY OAS 2.76% / IG OAS 0.76%, benign and tightening. That is supportive for risk assets, but compensation for high-yield credit risk is not a cash substitute.
- **Inflation/energy:** Brent/WTI elevated in the market-state artifact, so a small TIPS sleeve is reasonable; large TIPS allocation is not required without a stronger inflation shock thesis.

## Guardrails

1. Keep this reserve separate from the 40% ETF / 60% stock risk-asset model unless Randall explicitly approves changing the cash target.
2. Do not label HYG/JNK as cash or ballast; route them as credit-risk candidates only.
3. Do not extend duration materially without a clear recession/risk-off thesis or rate-cut path.
4. Do not apply canonical portfolio/model changes from this note. Any apply needs WF64/WF56-style exact patch preview, approval artifact, validator proof, backup/rollback, and post-apply validation.

## Practical recommendation

Use **60/20/10/10/0 within the 10% reserve**: 60% T-bill/cash-like, 20% short Treasury, 10% intermediate/aggregate duration, 10% TIPS, 0% high yield. This keeps the reserve liquid and defensive while still adding small rate/inflation hedges.