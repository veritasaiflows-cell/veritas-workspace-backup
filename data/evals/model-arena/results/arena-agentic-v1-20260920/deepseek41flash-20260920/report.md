# DeepSeek 4.1 Flash — new-bank first run (2026-09-20)

One-command bench, first live candidate. Exact `ollama-cloud/deepseek-v4.1-flash:cloud`, 12 cases, 600s/turn, zero retries, isolated single-case prompts (no hidden keys).

## Score

**1/12 strict** (11 answered, 1 operational timeout excluded from factual denominator).

| Case | Family | JSON | Factual | Strict |
|---|---|---|---|---|
| 73cd99b6 | T4 | pass | pass | **pass** |
| 14d6a2f3 | T3 | pass | fail | fail |
| a329ef46 | T3 | pass | fail | fail |
| 1707973c | T2 | pass | fail | fail |
| 430898a2 | T2 | pass | fail | fail |
| 36072319 | T1 | pass | fail | fail |
| b5f7b370 | T1 | pass | fail | fail |
| 23273237 | T5 | pass | fail | fail |
| e82ba401 | T5 | pass | fail | fail |
| c8dbb0b4 | T4 | pass | fail | fail |
| 75c25de6 | T6 | pass | fail | fail |
| ad216115 | T6 | — | — | **operational timeout** (no structured output; not a factual fail) |

## Reading

The new bank is materially harder than the old arena for this candidate (old: 8/12 strict). Every answered response was valid JSON; only the T4 truncated-mirror reduction matched exactly. T5/T3/T2 answers were analytically close but structurally non-exact (extra explanatory keys, candidate-shaped schemas vs frozen keys). T1 answers used wrong field names. The T6 timeout is operational per envelope precedent, never a factual failure.

One run, one repetition per case — consistency/ranking evidence only, not a reliability estimate. No routing, configuration, role, or execution authority follows.

## Evidence

- `graded-results.json` (runner-graded, strict JSON + strict_equal)
- `responses.json` (11 raw responses + 1 empty timeout slot)
- `dispatch-plan.json` (schema veritas.arena_dispatch_plan.v1)
- `run-contract.json` (model, hashes, 600s/0 retries)
