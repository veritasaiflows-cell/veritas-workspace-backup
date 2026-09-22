# GLM 5.3 Flash full-chain — Surface C (overlay-r2 CLI lab), 2026-09-20

## Score: 9/12 strict, 10/12 answered, dim 0.75, 2 T6 timeouts, 0 invented

Five sweeps of six families: T2, T3, T4, T5 perfect (2/2 each), T1 split (1/2 — the second T1 case answered but off-spec: `{"allocations":[20,20,20,20]}` shape instead of the required allocation JSON), T6 0/2 with both cases hitting the 600s operational timeout.

## Reading

This is the strongest GLM Flash surface and the closest to a like-for-like peer set. Like-for-like CLI board on this envelope: Spark 12/12, DeepSeek-chain 10/12, **GLM-Flash-chain 9/12**, GLM-Flash earlier CLI run 10/12. The 9 differs from that earlier 10 by one answered-fail on T1-r2 rather than a timeout, so the gap is inside one-case noise.

Transport effect remains large and unchanged: GLM Flash scored 4/12 via collectors on this same envelope and 9/12 via the CLI lab here — the instrument, not the model, moves most of that spread.

## Operational note

The first dispatch wave wrote 10 of 12 transports, then the host orchestration was lost before the two T6 lanes emitted. Those two lanes were re-dispatched on the identical documented route (no model-outcome retry; each lane's first attempt was lost, not failed). Both then hit the 600s timeout — the same T6 bottleneck DeepSeek's chain run hit. Disclosed rather than hidden.

## Evidence

`responses.json`, `graded-results.json`, `dimensional-rescore.json`, `dispatch-execution-summary.json`, `transport-receipts.json`, `authorization.json`. All 10 answering receipts carry the exact GLM pin with zero fallbacks. No routing/role/authority change.
