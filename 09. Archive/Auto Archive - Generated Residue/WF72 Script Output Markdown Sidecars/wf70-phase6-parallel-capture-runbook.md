# WF70 Phase 6 — Parallel Capture Runbook

Generated: `2026-05-24T06:30:46Z`

Review-only. No source fetches, canon/portfolio mutations, trades, orders, or authority widening.

## Summary

- Total tickers: 31
- Workers: 7
- Post-merge steps: 4

## Workers (run in parallel)

| Worker | Script | Tickers |
|---|---|---|
| W1 | `goog_official_ir_capture.py` | GOOG |
| W2 | `tech_official_ir_capture.py` | AMZN, MSFT, NVDA |
| W3 | `priority_official_ir_capture.py` | BRK.B, GS, JPM, LMT, RTX, XOM |
| W4 | `etn_vrt_official_ir_capture.py` | ETN, VRT |
| W5a | `batch2_official_ir_capture.py` | AMD, CAT, CVX, PLTR |
| W5b | `batch2b_official_ir_capture.py` | GE, LLY, META, PH |
| W6 | `longtail_official_ir_capture.py` | BKNG, CME, ECL, KTOS, LIN, LNG, NFLX, SMCI, TMUS, VMC, WMB |

## Post-Merge Steps (run sequentially after all workers complete)

| Step | Script | Depends on |
|---|---|---|
| validate_all | `official_ir_capture_validator.py --all --write` | all_workers_complete |
| registry_refresh | `official_capture_period_registry.py --write` | validate_all |
| reconciliation_refresh | `fundamental_ir_reconciliation_packets.py --write` | registry_refresh |
| bridge_refresh | `official_earnings_bridge.py --write` | reconciliation_refresh |

## Sequencing Rules

- All workers (W1–W6) may run in parallel. Each writes to disjoint per-ticker files under tmp/official-ir-captures/.
- No worker may write to another worker's output path. Ticker sets are non-overlapping.
- Post-merge steps run sequentially after all workers complete, in the order listed.
- If any worker exits non-zero, stop and diagnose before running post-merge steps.
- The registry/validator post-merge step is the authority gate; no downstream consumer should run until it passes.
- Parallel execution does not change authority boundaries: all outputs remain review-only.

## Collision Safety

- Each capture script writes one file per ticker (e.g., goog-q1-2026.json). No two workers share a ticker.
- The validator (post-merge) scans all captures atomically after workers complete — not concurrently.
- The registry selector runs after the validator, so latest_by_ticker always reflects the post-merge validated set.
- Period-slug collisions (two workers writing the same ticker+period) are prevented by the disjoint ticker assignment.

## Consumer Contract

Run all workers, then validate_all, then registry_refresh, then reconciliation_refresh, then bridge_refresh. Downstream consumers (capital recommendations, daily review objects, dashboards) should not run until bridge_refresh completes clean.
