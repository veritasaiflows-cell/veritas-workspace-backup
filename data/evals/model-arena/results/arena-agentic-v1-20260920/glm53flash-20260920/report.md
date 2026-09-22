# GLM 5.3 Flash — new-bank first run (2026-09-20)

One-command bench, second live candidate. Exact `ollama-cloud/glm-5.3-flash:cloud`, 12 cases, 600s/turn, zero retries, isolated single-case prompts (no hidden keys).

## Score

**0/12 strict** (11 answered, all valid JSON; 1 operational timeout excluded from factual denominator).

| Case | Family | JSON | Factual | Strict |
|---|---|---|---|---|
| 14d6a2f3 | T3 | pass | fail | fail |
| 1707973c | T2 | pass | fail | fail |
| 23273237 | T5 | pass | fail | fail |
| 36072319 | T1 | pass | fail | fail |
| 430898a2 | T2 | pass | fail | fail |
| 73cd99b6 | T4 | pass | fail | fail (abstained: refused fixtures) |
| 75c25de6 | T6 | pass | fail | fail |
| a329ef46 | T3 | pass | fail | fail |
| ad216115 | T6 | — | — | **operational timeout** (not a factual fail) |
| b5f7b370 | T1 | pass | fail | fail |
| c8dbb0b4 | T4 | pass | fail | fail |
| e82ba401 | T5 | pass | fail | fail |

## Reading

Same disease as DeepSeek, one degree worse: reasoning present, frozen schemas absent. Notable behaviors: T4-truncated case abstained outright (declared fixtures out of scope rather than attempting); T4-fallback case read beyond its assigned file into harness fixtures (discipline flag — answer still schema-failed); T6-abstention case timed out exactly like DeepSeek's. Old-arena contrast holds: GLM was 8/12 there on tool/format discipline, but this bank punishes schema drift absolutely.

One run, one repetition per case — consistency evidence only, not a reliability estimate. No routing, configuration, role, or execution authority follows.

## Evidence

- `graded-results.json` (runner-graded, strict JSON + strict_equal)
- `responses.json` (11 raw responses + 1 empty timeout slot)
- `dispatch-plan.json` (schema veritas.arena_dispatch_plan.v1)
- `run-contract.json` (model, hashes, 600s/0 retries)
