---
name: "ic-swarm-orchestrator"
description: "Route verified challenger review for serious alerts-OS finance gates."
---

# IC Swarm Orchestrator

## Purpose

For material finance-chain, guarded-SQL, freshness, recommendation-contract, or authority-boundary changes, use a bounded independent challenger when risk warrants it.

When the verified model path `claude-cli/claude-opus-4-8` is available, it may serve as the preferred challenger. Verify the actual session registry path; a label is not proof. If unavailable or mismatched, classify the result as standard challenger evidence and record the fallback.

## Challenger Contract

Ask the challenger to test:

- false-green and stale-evidence risk
- source lineage and state precedence
- freshness, confidence, and suppression logic
- schema and contract robustness
- reintroduction of portfolio, paper, account, order, or execution routes
- rollback and validation completeness

The challenger is read-only unless Main grants an exact file lease.

## Handoff

Include required model, actual model verification, bounded task, exact inputs, allowed writes if any, stop lines, proof expected, and fallback classification.

## Closeout

Main reports the expected and actual model, accepted/rejected findings, validator results, and remaining trust downgrade. Challenger output never outranks source truth or Main acceptance.

## Verification And Recovery

- Before judging challenger evidence, machine-verify every frozen input hash, byte count, and inventory digest. Read the generating script and recompute the inventory with its exact algorithm (for example `sha256(json.dumps(rows, sort_keys=True))`); never hand-transcribe a declared value and never mistake the manifest file's own raw hash for the inventory digest. Use a small Python read for canonical recomputation instead of ad-hoc shell one-liners, which misquote and waste calls.
- Compare live sources against their freeze-time hashes before review; drifted sources invalidate the frozen packet.
- If the parent reports a duplicate or stale completion event, do not restart or expand the review. Verify the existing deliverable on disk (path, bytes, SHA256, verdict fields), re-report it, and keep the original scope.

## Boundary

No maintained account or portfolio state, capital action, orders, paper/live/account access, canon mutation, runtime/config mutation, autonomous authority expansion, or owner-approval inference.
