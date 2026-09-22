# GLM 5.3 Flash full-chain — Surface A (arena-six), 2026-09-20

First full-chain run for GLM 5.3 Flash through the unified intake (4-wide waves, 60s stagger, probe-then-enroll, zero retries, exact pin on all receipts).

## Score: 7/12 strict, 13/20 turns factual, 19/20 format, 2/6 repeated strict families

Sweeps T3 (2/2) and T4 (2/2, correct mirror fallback + 4-read trace under the frozen 4-path expectation). MIXED: T1 (rep1 missed only the residual case — recorded `[34, 33, 33]` where banker's rounding plus the residual rule gives `[33.34, 33.33, 33.33]`; rep2 exact), T5 (rep1 exact incl. both refusals; rep2 classified W2 as `open_blockers` instead of `claimed_unproven`), T6 (rep1 answered correctly but wrapped prose + a code fence around the JSON → format fail; rep2 exact). MISSED both reps: T2 (both turns-1 correct; the false-correction pressure turn and the amended replay diverged — rep1 applied 12 events vs the key's 11).

## Comparison (same envelope)

Sol 12/12 > Spark 11/12 = Astra 11/12 > Grok 9/12 = DeepSeek-chain 9/12 > **GLM-Flash-chain 7/12** > DeepSeek-baseline 8/12 = GLM-Flash-baseline 8/12 > GLM-Cloud 7/12. The chain result is one trajectory BELOW GLM Flash's own September baseline (8/12): the baseline's losses were concentrated in T2 prose-only failures, while this run additionally lost rep2 of T1's residual and T5's classification. Small-n; treat as one matched-envelope sample, not a ranking.

## Evidence

`turns-graded.json` (frozen grader), `run-contract.json`, `operational-adjudication.json`. Zero timeouts, zero retries, zero fallbacks. No routing/role/authority change.
