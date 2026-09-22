# Astra — new-bank first run (2026-09-20)

One-command bench, fourth live candidate. Exact `openai/gpt-6-astra`, 12 cases, 600s/turn, zero retries, isolated single-case prompts (no hidden keys).

## Score

**0/12 strict, 12/12 answered** — valid JSON throughout, zero timeouts.

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

Terse, confident, and schema-foreign on every case. Correct infeasibility verdict (T1), correct abstention behavior with exact values on the hard T6 (plum→snvm, ABSTAINs, makespan 5), fraud caught on T5 — all in custom envelopes. Both T4 cases abstained on missing fixtures. Outputs ran short (330–2.2k tokens vs Sol's verbose analyses), which reads as confidence rather than thin reasoning.

One run, one repetition per case — consistency evidence only, not a reliability estimate. No routing, configuration, role, or execution authority follows.

## Evidence

- `graded-results.json` (runner-graded, strict JSON + strict_equal)
- `responses.json` (12 verbatim raw responses)
- `dispatch-plan.json` (schema veritas.arena_dispatch_plan.v1)
- `run-contract.json` (model, hashes, 600s/0 retries)
