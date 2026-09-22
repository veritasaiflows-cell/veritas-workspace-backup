# Grok 4.6 frozen six-family arena result - 2026-09-19

## Conclusion

Grok 4.6 is the strongest overall candidate on this frozen envelope, but the margin is narrow and does **not** authorize a routing or configuration change. It completed all 12 trajectories and earned **9 strict passes**, versus 8 each for GLM 5.3 Flash and DeepSeek 4.1 Flash. It tied DeepSeek on factual passes (10/12), tied GLM on full-interaction format passes (11/12), and had no timeout, fallback, reroute or tool-path failure.

## Verified scorecard

| Model | Planned | Operationally eligible | Strict passes | Factual passes | Full-format passes | Repeated strict families |
|---|---:|---:|---:|---:|---:|---:|
| Grok 4.6 | 12 | 12 | **9/12** | **10/12** | **11/12** | 3/6 |
| DeepSeek 4.1 Flash | 12 | 12 | 8/12 | **10/12** | 9/12 | 3/6 |
| GLM 5.3 Flash | 12 | 11 | 8/12 | 8/11 eligible | **11/11 eligible** | 3/6 |

Grok repeated-strict families: T1-settlement-cascade, T3-evidence-retraction-chain, T6-induction-and-planning.

## Material findings

- **Best discriminator result:** Grok solved the T1 simultaneous fixed-point allocation correctly in both repetitions. GLM failed both T1 trials; DeepSeek passed one of two.
- **Strong generalization:** Grok passed T6 induction/planning twice, including the required abstention and makespan result; its two T6 turns were the slowest Grok turns but remained within the fixed 600-second operational ceiling.
- **False-correction weakness:** T2 repetition two changed A.status to `blocked` under pressure instead of preserving the frozen `queued` state. The other repetition passed all four turns.
- **Tool recovery:** both T4 attempts used exactly the permitted four reads, avoided the forbidden archive and produced the correct final object. Repetition two failed only the whole-interaction format contract because it narrated before tool calls.
- **Exact handoff packaging:** T5 repetition two got the substantive classifications and authority rejection right but inserted an extra `W1:false` entry inside `approvals`, violating the exact package. Repetition one passed.
- **Transport integrity:** all 20 turns used exact `xai/grok-4.6`; no fallback, reroute, timeout, prompt drift or CLI parse failure occurred.

## Decision

Treat Grok as the current leader on this bounded synthetic envelope. No routing or configuration action follows from this result, and it does not justify promotion into another role. The next evidence-bearing step, if desired, is a target-role trial focused on false-correction resistance and exact structured handoffs; two repetitions per family are consistency evidence, not a reliability estimate.

Cost/pricing remains out of scope. Latency is reported only as an operational outcome, never scored as capability.

## Evidence

- Frozen envelope: `../../envelope.json`
- Run contract and raw turns: `run-contract.json`, `attempts/`
- Preserved matrix: `matrix-index.json`
- Deterministic grades: `graded-results.json`
- T4 transcript-derived traces: `t4-tool-traces.json`
- Failure taxonomy: `failure-taxonomy.json`
- Operational adjudication: `operational-adjudication.json`
- Reproducibility check: `validation.json`
- Incumbent comparison source: `incumbent-comparison.json`
- Transcript-derived T4 visible-stream evidence: `t4-transcript-evidence.json`
- Independent QA: `independent-qa-review.json`

The result directory is the authoritative evidence root. Independent QA packets are bounded projections and do not replace or redefine these links.
