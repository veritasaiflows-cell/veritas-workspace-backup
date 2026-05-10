# Workflow 43 - State History and Review Outcome Retention

## Retrieval Notes
- Type: workflow
- Status: durable-path-approved / proof-pending
- Owner surface: `06. Playbooks/OpenClaw Parallel Pilot Queue.md`
- Authority: historical
- Workflow: WF43
- Key entities: state history, review outcomes, owner decisions, `data/state-history/state-history-v1.jsonl`, `scripts/state_history_capture.py`
- Source freshness: partial; durable append proof pending
- Next action: run durable-path proof contract before consumer wiring
- Archive posture: keep-active
- Tags: #veritas/workflow #wf/WF43 #status/proof-pending

## Objective
- Preserve point-in-time deployment state, band status, review outcomes, owner approvals/rejections, and realized subsequent outcomes so future predictive analytics can be honest instead of hindsight-biased.
- Create append-only historical state needed for future WF27-style modeling datasets without letting models drive deployment decisions.

## Workflow under review
- Append-only state-history and label-retention layer for deployment/readiness review outcomes.

## Current phase
- Append-only state-history v1 proof implemented and main-session QC passed on 2026-05-09.
- Randall approved the durable retention path on 2026-05-09: `data/state-history/state-history-v1.jsonl`.
- `scripts/state_history_capture.py` can sample, append, and validate `state_snapshot_v1` rows from current post-close artifacts; its default output now points to the approved durable path.
- Prior `tmp/state-history-v1.jsonl` remains proof-only historical residue, not the durable path.

## Recommended next phase
- Run the durable-path proof contract, then decide whether recommendation consumers may read history availability.
- Do not open model-training or model-driven deployment work until retention is stable, durable, audited, and explicitly reopened.

## Safe automation boundary
- allowed automatically: append point-in-time state rows, retain labels/outcomes, mark stale-note handling metadata, and produce future dataset candidates
- blocked automatically: rewriting historical labels, backfilling with hindsight as if known at the time, changing current deployment state, changing owner notes, or using model output to authorize deployment

## Inputs
- daily deployment state
- band status
- review outcomes
- owner approvals/rejections
- realized subsequent outcomes

## Outputs
- point-in-time history table
- label-retention rules
- stale-note handling
- future WF27 modeling dataset

## Authority
- append-only historical state
- no model-driven deployment

## Owner layer
- current canonical state: live note layer and existing finance artifacts
- historical truth: append-only state-history table/artifact with timestamp/provenance
- modeling readiness: future WF27 successor only after retention proof exists

## Review window
- daily after deployment/readiness artifacts are generated
- additional append after explicit owner approval/rejection events or realized outcome updates

## Stop lines
- append logic would rewrite or reinterpret prior labels
- point-in-time timestamp/provenance is missing
- realized outcomes are mixed with known-at-the-time fields without clear separation
- model-readiness language starts implying model-driven deployment authority
- stale-note handling mutates canonical notes instead of flagging review needs

## Trust gates still missing
- first durable append + validation proof under `data/state-history/state-history-v1.jsonl`
- lifecycle policy for retention length, archive/compaction, and backup expectations
- future owner approval/rejection and realized-outcome update flow
- stale-note handling contract that flags instead of silently edits
- linkage to WF27 methodology without reopening modeling prematurely
- consumer wiring so recommendation packets can stop reporting state history as missing once durable history is proven

## Trust gates passed for v1
- append-only JSONL schema with source/provenance fields exists under `tmp/state-history-v1.jsonl`
- validator proves required fields, authority flags, empty future-outcome fields, source provenance, unique run IDs, and JSONL validity
- regression test appends twice and confirms the second append preserves the exact original file prefix
- sample row captures known-at-time deployment states, band statuses, review objects, capital recommendations, market-intelligence events, run summary, known gaps, source timestamps, and source hashes
- authority remains historical-review-only: no model training, model-driven deployment, canonical mutation, portfolio/deployment mutation, trade execution, or owner approval inference

## Validation / evidence target
- schema/unit test for append-only table
- sample daily append from existing deployment artifacts
- no-rewrite validator proof
- durable-path validation proof at `data/state-history/state-history-v1.jsonl`
- audit proving separation between known-at-time fields and realized subsequent outcomes

## Next proof contract
```bash
python -m py_compile scripts\state_history_capture.py scripts\test_state_history_capture.py
python scripts\test_state_history_capture.py
python scripts\state_history_capture.py sample --window post-close
python scripts\state_history_capture.py append --window post-close
python scripts\state_history_capture.py validate
```
Stop if validation fails, if provenance is missing, or if authority fields imply model training, model-driven deployment, canonical mutation, portfolio/deployment mutation, trade execution, or owner approval.

## Next action
- Run the durable-path proof contract and inspect the first durable JSONL row before allowing any consumer to treat state history as available.

## Key files
- `06. Playbooks/Project Continuity/Workflow 43 - State History and Review Outcome Retention.md`
- `06. Playbooks/Project Continuity/Workflow 27 - Predictive Analytics and Forecasting Readiness.md`
- `06. Playbooks/WF27 Data and Provenance Audit - Phase 2.md`
- `06. Playbooks/WF27 Baseline Methods and Decision-Boundary Contract - Phases 3-4.md`
- `scripts/daily_review_objects.py`
- `data/state-history/state-history-v1.jsonl` - approved durable append-only history path
- `data/state-history/README.md` - path authority and proof contract
- `tmp/state-history-v1.jsonl` - old proof-only artifact, not durable truth
