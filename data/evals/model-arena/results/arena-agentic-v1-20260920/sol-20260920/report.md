# Sol — new-bank first run (2026-09-20)

One-command bench, third live candidate. Exact `openai/gpt-5.6-sol`, 12 cases, 600s/turn, zero retries, isolated single-case prompts (no hidden keys). Grading is deterministic `strict_equal`, so Sol's prior advisory QA of the runner is not self-grading.

## Score

**0/12 strict, 12/12 answered** — the only model to finish every case with zero timeouts.

| Case | Family | JSON | Factual | Strict |
|---|---|---|---|---|
| 14d6a2f3 | T3 | pass | fail | fail |
| 1707973c | T2 | pass | fail | fail |
| 23273237 | T5 | pass | fail | fail |
| 36072319 | T1 | pass | fail | fail |
| 430898a2 | T2 | pass | fail | fail |
| 73cd99b6 | T4 | pass | fail | fail (abstained) |
| 75c25de6 | T6 | pass | fail | fail |
| a329ef46 | T3 | pass | fail | fail |
| ad216115 | T6 | pass | fail | fail |
| b5f7b370 | T1 | pass | fail | fail |
| c8dbb0b4 | T4 | pass | fail | fail (abstained) |
| e82ba401 | T5 | pass | fail | fail |

## Reading

Sol is the semantic runner-up on nearly every case and the only model to answer the abstention-heavy T6 (both Flash models timed out there): correct `plum→snvm`, correct ABSTAIN on Cat7/ab1, makespan 5 right — wrong envelope. It alone declared T1-infeasible correctly in verdict (both Flash models forced allocations). Its T2-ambiguity used `ambiguous/states` keys — closest to frozen of any answer. Both T4 cases abstained on missing fixtures (same posture as GLM, opposite of DeepSeek's attempt-and-win).

One run, one repetition per case — consistency evidence only, not a reliability estimate. No routing, configuration, role, or execution authority follows.

## Evidence

- `graded-results.json` (runner-graded, strict JSON + strict_equal)
- `responses.json` (12 raw responses)
- `dispatch-plan.json` (schema veritas.arena_dispatch_plan.v1)
- `run-contract.json` (model, hashes, 600s/0 retries)
