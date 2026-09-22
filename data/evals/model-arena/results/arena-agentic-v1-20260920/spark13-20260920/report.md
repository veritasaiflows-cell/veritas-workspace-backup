# Spark 1.3 — new-bank first run (2026-09-20)

One-command bench, fifth live candidate. Exact `meta/muse-spark-1.3-contributor`, 12 cases, 600s/turn, zero retries, isolated single-case prompts (no hidden keys).

## Score

**1/12 strict** (11 answered, 1 operational timeout excluded from factual denominator) — ties DeepSeek.

| Case | Family | JSON | Factual | Strict |
|---|---|---|---|---|
| 14d6a2f3 | T3 | pass | fail | fail |
| 1707973c | T2 | pass | fail | fail |
| 23273237 | T5 | pass | fail | fail |
| 36072319 | T1 | pass | fail | fail |
| 430898a2 | T2 | pass | fail | fail |
| 73cd99b6 | T4 | pass | fail | **pass (exact)** |
| 75c25de6 | T6 | — | — | **operational timeout** (not a factual fail) |
| a329ef46 | T3 | pass | fail | fail |
| ad216115 | T6 | pass | fail | fail |
| b5f7b370 | T1 | pass | fail | fail |
| c8dbb0b4 | T4 | pass | fail | fail (wrong values) |
| e82ba401 | T5 | pass | fail | fail |

## Reading

Ties DeepSeek at the top with the same lone T4-truncated hit — the only two attempters, the only two passes. Answered the killer abstention case (plum snvm, nulls, makespan 5) but wrong envelope; missed the infeasibility verdict both OpenAI models caught; hallucinated T4-fallback row values (r2 b2/2026-09-18 vs b1/2026-09-11) — the only fabricated-content miss of its run. Timed out on T6-bottleneck where it wrote the bench itself.

One run, one repetition per case — consistency evidence only, not a reliability estimate. No routing, configuration, role, or execution authority follows.

## Evidence

- `graded-results.json` (runner-graded, strict JSON + strict_equal)
- `responses.json` (11 verbatim raw responses + 1 empty timeout slot)
- `dispatch-plan.json` (schema veritas.arena_dispatch_plan.v1)
- `run-contract.json` (model, hashes, 600s/0 retries)
