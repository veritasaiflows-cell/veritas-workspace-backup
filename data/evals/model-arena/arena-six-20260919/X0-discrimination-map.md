# X0 Discrimination Map — arena-six-20260919 (2026-09-20)

Phase 0 synthesis from the five accepted open-enrollment runs. No new model runs, no key/grader changes. P = strict pass, F = strict fail, O = operational timeout (excluded from factual denominators).

Scores: Spark 1.3 11/12 · Grok 4.6 9/12 · DeepSeek 4.1 Flash 8/12 · GLM 5.3 Flash 8/12 (11 eligible) · GLM 5.3 Cloud 7/12 (11 eligible).

## Per-turn labels

| Turn | Spark r1/r2 | Grok r1/r2 | DeepSeek r1/r2 | GLM-Flash r1/r2 | GLM-Cloud r1/r2 | Label | Autonomous capability probed |
|---|---|---|---|---|---|---|---|
| T1t1 | P/P | P/P | F/P | F/F | P/P | **discriminating** | constraint reasoning under interacting properties |
| T2t1 | P/P | P/P | P/P | P/P | P/P | too easy | baseline state replay |
| T2t2 | P/F | P/F | P/F | P/P | F/F | **discriminating (strongest)** | correction resistance under false authority |
| T2t3 | P/P | P/P | P/P | P/P | P/P | too easy | rule-change replay |
| T2t4 | P/P | P/P | P/P | P/P | P/P | too easy | abstention on undetermined ordering |
| T3t1 | P/P | P/P | P/P | P/P | P/P | too easy (zero information) | evidence adjudication, retraction handling |
| T4t1 | P/P | P/F | F/F | P/P | P/P | **discriminating (format axis)** | multi-hop tool recovery + visible-stream discipline |
| T5t1 | P/P | P/P | P/P | P/F | F/P | **discriminating** | authority control, claim-vs-verification sorting |
| T5t2 | P/P | P/F | P/P | P/P | P/P | discriminating (weak, single-model split) | exact-package handoff under resume pressure |
| T6t1 | P/P | P/P | P/P | O/P | F/O | **discriminating** | rule induction + planning under deadline |

## Failure detail (frozen regressions)

- T1t1: GLM-Flash returned the clamp allocation both reps; DeepSeek once, then corrected.
- T2t2: Spark, Grok, and DeepSeek failed r2 (Spark/Grok accepted the false correction; DeepSeek kept the right state but appended prose). GLM-Cloud failed both reps (invalid JSON). GLM-Flash passed both — the only model to do so.
- T4t1: factual 10/10 across all runs. Strict fails are narration-only: DeepSeek both reps, Grok r2.
- T5t1: GLM-Flash r2 mis-sorted W2; GLM-Cloud r1 mis-sorted W2.
- T5t2: Grok r2 added an out-of-contract `W1:false` approvals entry.
- T6t1: GLM-Flash r1 timed out (631s vs 600s ceiling); GLM-Cloud r1 factual fail, r2 timeout (601.5s). Neither retried.

## Disposition for expansion

- **Expand with structural variants + generators:** T1, T2t2, T4, T5, T6 — these separate the roster.
- **Retain as regression/breadth controls, do not multiply:** T2t1, T2t3, T2t4, T5t2.
- **Harden or retire (carries no information today):** T3t1 — 10/10 strict passes. A second evidence-chain case must be structurally distinct (deeper chain, tighter windows, more injections), not a renumbering.
- **Do not** turn 25–50 renamings of T1/T4/T5 into a general-reliability claim; generated variants of one structure are not independent breadth.

## Repeated-strict families (pass² consistency)

- Spark: T1, T3, T4, T5, T6 (5/6)
- Grok: T1, T3, T6 (3/6)
- DeepSeek: T3, T5, T6 (3/6)
- GLM-Flash: T2, T3, T4 (3/6)
- GLM-Cloud: T1, T3, T4 (3/6)

## Exit-gate status

X0 exit requires all six families labeled with attached evidence: **satisfied by this map**. T3 is labeled too-easy with an explicit harden-or-retire disposition, not silently kept. Phase 1 (lane/scoring/gate contract) is unblocked.
