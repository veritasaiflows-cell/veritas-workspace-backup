# Workflow 79 - Legacy Finance Command Center

## Current State

- Status: retired on 2026-08-29 by the alerts-and-recommendations OS pivot.
- The compact reader and full-detail dashboard still exposed capital buckets, deployable states, portfolio posture, sizing rules, and legacy finance proof routes.
- `Active Workflows.md` and the workflow override now fail closed; no current dashboard artifact is an active finance truth surface.

## Next Action

Preserve history only. A future local UI must be rebuilt from guarded SQL, explicit quote proof, the alert controller, and the non-executing digest, then pass the pivot validator and independent QA under a new explicit architecture decision.

## Historical Proof

- `tmp/veritas-command-center-compact-reader.json`
- `tmp/veritas-command-center-compact.html`
- `tmp/veritas-command-center.html`

These paths are historical generated evidence and must not be treated as current finance state.

## Stop Line

No legacy dashboard producer, capital/actionability view, finance-state maintenance, canon/account/order/execution route, external delivery, or owner-approval inference.
