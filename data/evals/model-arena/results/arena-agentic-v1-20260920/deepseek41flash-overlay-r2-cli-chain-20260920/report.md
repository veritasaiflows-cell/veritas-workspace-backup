# DeepSeek full-chain — Surface C (overlay-r2 CLI lab), 2026-09-20

## Score: 10/12 strict, 10 answered, 2 operational timeouts, dim 0.8333

All 10 answered cases pass clean (families T1/T2/T3/T4/T5 all 1.0, 0 traps, 0 invented, 0 contaminated). Both T6s hit the 600s turn timeout (~610s each, empty fail-closed, zero retries) — the same T6 wall that took GLM's CLI run and DeepSeek's prior overlay run (zebra).

## Comparison (same pipe, same prompts, byte-verified)

Spark 12/12 > DeepSeek 11/12 (prior) > DeepSeek-chain 10/12 = GLM Flash CLI 10/12 = MiniMax 10/12. The delta to DeepSeek's own prior 11 is exactly one T6 timeout (abstention-case answered then, timed out now) — transport variance, not regression: 10/10 answered still pass.

## Conditions note

Live canonical prompts copied byte-verbatim from the GLM CLI run (proven identical with Spark's). 4-wide waves (prior runs used 12-wide; direction favors reliability). Readiness-lane preview prompts were found to differ from live bytes — live bytes used here; preview noted as non-canonical for dispatch.

## Evidence

`prompts/` (live bytes), `candidate-mount/`, `transport-*.json`, `responses.json`, `graded-results.json`, `dimensional-rescore.json`, `authorization.json` (run-scoped). Canonical gate untouched. No routing/role/authority change.
