# DeepSeek full-chain — Surface A (arena-six), 2026-09-20

First live run through the unified intake (4-wide waves, 60s stagger, probe-then-enroll).

## Score: 9/12 strict, 19/20 turns factual, 20/20 format, 4/6 families

Sweeps T1 (2/2, fixed-point + rounds + infeasible), T2 (8/8 turns, held through the trap both reps), T3 (2/2), T5 (4/4 turns, both refusals). Misses: T4 both reps (values exact, 3-path traces vs the frozen 4-path expectation — trace discipline, same bar as Sol/Astra) and T6-r2 (one zebra value).

## Comparison (same envelope)

Sol 12/12 > DeepSeek-chain 9/12 = Grok 9/12 > DeepSeek-baseline 8/12. The chain run beats DeepSeek's own September baseline by a full trajectory (T1 sweep + T2 sweep, previously 1/2 and prose-fail).

## Evidence

`turns-graded.json`, `graded-results.json` (frozen grader), `run-contract.json`, `operational-adjudication.json`. No routing/role/authority change.
