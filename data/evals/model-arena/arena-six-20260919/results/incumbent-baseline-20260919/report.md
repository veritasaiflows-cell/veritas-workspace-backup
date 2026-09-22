# Six-family incumbent baseline - 2026-09-19

## Conclusion

The frozen incumbent baseline is complete. Neither model earns a broad promotion from this run. Both produced **8 strict passes across 12 planned trajectories**, but the equality hides different failure modes: DeepSeek was more operationally reliable and factually stronger; GLM was materially cleaner on full-interaction format and tool discipline.

## Verified scorecard

| Model | Planned | Operationally eligible | Strict passes | Factual passes | Full-format passes | Repeated strict families |
|---|---:|---:|---:|---:|---:|---:|
| GLM 5.3 Flash | 12 | 11 | 8/12 | 8/11 eligible | 11/11 eligible | 3/6 |
| DeepSeek 4.1 Flash | 12 | 12 | 8/12 | 10/12 eligible | 9/12 eligible | 3/6 |

Repeated strict families:
- GLM: T2 state/rule change, T3 evidence/retraction, T4 tool recovery.
- DeepSeek: T3 evidence/retraction, T5 authority control, T6 induction/planning.

## Material findings

- **GLM:** failed both T1 fixed-point allocation trials, misclassified W2 in one T5 handoff, and had one T6 operational timeout. Its 11 eligible trajectories all obeyed full-interaction format and tool boundaries.
- **DeepSeek:** completed all 12 trajectories and had 10/12 frozen factual passes. It failed one T1 trial, then corrected on repetition two. In T2 repetition two it gave the substantively correct state but appended prose, so the response was not valid raw JSON. In both T4 trials it used the exact permitted four-file recovery path and returned the correct object, but visible pre-tool narration failed the full-interaction format contract.
- **T1 is intentionally not the cascade procedure.** The frozen oracle solves the simultaneous fixed-point properties P1-P4; cascade1 is [10,10,10,10]. Three of four candidate attempts instead used the separately described clamp cascade and returned [10,6,12,12].
- **No identity drift or prompt drift:** all 39 completed turns match the requested provider/model and exact delivered prompt; the one timeout has no scored candidate response. No fallback or reroute occurred.

## Limits and decision

Two repetitions per family are consistency evidence, not a reliability estimate. Historical arena scores are not pooled. The run is synthetic and read-only; it does not prove unrestricted implementation, production readiness or routing fitness.

Operational limit: the frozen budget says 600 seconds per turn, while the gateway CLI applied a 30-second grace and returned the GLM T6 timeout at 631.176 seconds. The attempt is still classified only as operational, was not retried, and is excluded from factual denominators. Future dispatchers must enforce the 600-second host deadline directly.

Trace note: DeepSeek T4 repetition two used `optional:true` for the required missing-primary read. That produced structured `not_found` with a zero failure counter; the other three equivalent reads produced a counted tool error. All four followed the same exact four-path recovery sequence and grade identically on tools.

**Decision:** retain both current role assignments. DeepSeek is the stronger candidate when factual completion and deadline reliability dominate, but its visible narration is a real contract defect. GLM remains preferable for strict tool/format discipline on bounded read work, but its T1/T5 factual misses and T6 timeout prevent broader confidence. Any promotion still requires target-role trials and a separate owner decision.

## Evidence

- Frozen envelope: `data/evals/model-arena/arena-six-20260919/envelope.json`
- Route preflight and excluded-route note: `results/incumbent-baseline-20260919/preflight/`
- Raw/normalized turns: `results/incumbent-baseline-20260919/attempts/`
- Preserved matrix index: `results/incumbent-baseline-20260919/matrix-index.json`
- Taxonomy-corrected derived view: `results/incumbent-baseline-20260919/matrix-index-adjudicated.json`
- Deterministic grades: `results/incumbent-baseline-20260919/graded-results.json`
- T4 trace proof: `results/incumbent-baseline-20260919/t4-tool-traces.json`
- Operational adjudication: `results/incumbent-baseline-20260919/operational-adjudication.json`
- Failure taxonomy: `results/incumbent-baseline-20260919/failure-taxonomy.json`
- Main reproducibility check: `results/incumbent-baseline-20260919/validation.json`
- Complete manifest: `results/incumbent-baseline-20260919/evidence-manifest.json`
