# Spark 1.3 and GLM 5.3 Cloud frozen six-family arena result - 2026-09-19

## Conclusion

Spark 1.3 is the strongest overall candidate on this frozen envelope with **11/12** strict passes, versus Grok 4.6 at 9/12 and GLM 5.3 Cloud at 7/12 planned (11 operationally eligible). This does **not** authorize a routing or configuration change.

## Verified scorecard

| Model | Planned | Operationally eligible | Strict passes | Factual passes | Full-format passes | Tool passes | Repeated strict families |
|---|---:|---:|---:|---:|---:|---:|---:|
| Grok 4.6 | 12 | 12 | 9/12 | 10/12 | 11/12 | 12/12 | 3/6 |
| DeepSeek 4.1 Flash | 12 | 12 | 8/12 | 10/12 | 9/12 | 12/12 | 3/6 |
| GLM 5.3 Flash | 12 | 11 | 8/12 | 8/11 eligible | 11/11 eligible | 11/11 eligible | 3/6 |
| Spark 1.3 | 12 | 12 | **11/12** | 11/12 | 11/12 | 12/12 | 5/6 |
| GLM 5.3 Cloud | 12 | 11 | 7/12 planned | 7/11 eligible | 9/11 eligible | 11/11 eligible | 3/6 |

Spark repeated-strict families: T1-settlement-cascade, T3-evidence-retraction-chain, T4-multihop-read-recovery, T5-handoff-authority-control, T6-induction-and-planning.

GLM 5.3 Cloud repeated-strict families: T1-settlement-cascade, T3-evidence-retraction-chain, T4-multihop-read-recovery.

## Material findings

- **Spark identity:** all 20 turns used exact `meta/muse-spark-1.3-contributor` with no fallback, reroute, timeout or prompt drift.
- **GLM identity:** 19/20 turns used exact `ollama-cloud/glm-5.3:cloud` with no fallback or reroute. T6 repetition 2 timed out at 601.517s and is operational, not a factual failure. It was not retried.
- **T4 tool recovery:** all four attempts used the missing-primary, index, payload-a, mirror path, avoided the forbidden archive, and returned raw JSON.
- **Spark case split:** T1-settlement-cascade 2/2; T2-event-revert-ambiguity 1/2; T3-evidence-retraction-chain 2/2; T4-multihop-read-recovery 2/2; T5-handoff-authority-control 2/2; T6-induction-and-planning 2/2.
- **GLM 5.3 Cloud case split:** T1-settlement-cascade 2/2 eligible; T2-event-revert-ambiguity 0/2 eligible; T3-evidence-retraction-chain 2/2 eligible; T4-multihop-read-recovery 2/2 eligible; T5-handoff-authority-control 1/2 eligible; T6-induction-and-planning 0/2 eligible.
- **Transport:** 40 planned turns, 39 ok, 1 timeout, 0 identity/prompt mismatches on completed turns, zero retries.

## Decision

Treat this as an open-enrollment addition to the frozen envelope, not a promotion event. No routing or configuration action follows. Two repetitions per family are consistency evidence, not a reliability estimate. Cost/pricing remains out of scope. Latency is operational only.

## Evidence

- Frozen envelope: `../../envelope.json`
- Run contract and raw turns: `run-contract.json`, `attempts/`
- Preserved matrix: `matrix-index.json`
- Deterministic grades: `graded-results.json`
- T4 traces: `t4-tool-traces.json`
- Failure taxonomy: `failure-taxonomy.json`
- Operational adjudication: `operational-adjudication.json`
- Comparison: `open-enrollment-comparison.json`
- Evidence separation and hash attribution: `evidence-separation.json`
- Independent review (Grok 4.6): `independent-qa-review.json`

The result directory is the authoritative evidence root.
