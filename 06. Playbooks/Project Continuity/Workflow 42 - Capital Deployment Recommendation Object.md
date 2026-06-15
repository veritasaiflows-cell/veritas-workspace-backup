# Workflow 42 - Capital Deployment Recommendation Object

## Objective
- Convert research, technical, macro, risk, and fresh-intelligence evidence into a reviewable capital-deployment recommendation object.
- Keep deployment recommendation separate from execution, owner approval, and automatic portfolio mutation.

## Workflow under review
- Owner-gated deployment recommendation packet generation for candidates that have enough evidence to support a `deploy / wait / reject / review` recommendation.

## Current phase
- Bounded WF42 recommendation-object hardening completed and main-session QC passed on 2026-05-09.
- `daily_review_objects.py` now emits fuller owner-gated capital-deployment recommendation objects with evidence provenance, risk/invalidation, source freshness, missing-evidence flags, explicit action mapping, and mutation/approval authority fields.

## Recommended next phase
- Treat WF42 v1 as closeout-ready after repeat window proof.
- Do not widen to execution, position sizing, automatic portfolio mutation, or owner approval inference.

## Safe automation boundary
- allowed automatically: gather existing artifact evidence, assemble recommendation packet, state confidence and invalidation, name missing evidence, and require owner approval
- blocked automatically: trade execution, account action, automatic position sizing, automatic portfolio snapshot mutation, automatic deployment-trigger mutation, and treating a clean packet as approval

## Inputs
- deployment trigger sheet
- portfolio snapshot
- technical entry/invalidation sheet
- band proposals
- promotion review queue
- WF41 event packets
- sector/correlation checks

## Outputs
- `deploy / wait / reject / review` packet
- evidence list
- confidence
- invalidation
- owner approval field

## Authority
- recommendation only
- no execution
- no automatic portfolio mutation

## Owner layer
- canonical portfolio state: Portfolio Snapshot and owner notes
- canonical deployment state: Deployment Trigger Sheet / technical entry and invalidation sheet owner layer
- recommendation artifacts: `tmp/` or review-folder packet surfaces
- owner approval: explicit owner field; never inferred from packet confidence

## Review window
- after daily review objects and fresh-intelligence event routing are available
- especially relevant post-close, Sunday weekly positioning, and post-earnings closure windows

## Stop lines
- sector/correlation check is unavailable or too weak for position-impact judgment
- technical entry/invalidation data is stale or contradictory
- WF41 event packet has unresolved truth affecting the candidate
- deployment trigger sheet or portfolio snapshot freshness is degraded
- recommendation text implies approval, execution, or mutation authority

## Trust gates still missing
- repeat scheduled-window proof remains open residue.
- WF43 has durable append/provenance proof, but lifecycle / owner-outcome update flow is still missing before outcome analytics can inform recommendations.
- WF56 proposal schemas and validators are not yet built, so WF42 recommendation objects can inform mutation proposals but must not become apply authority.
- repeat window proof before closure.

## Trust gates passed for v1
- Packet schema now includes owner approval required/granted, confidence, trust/source freshness, risk/invalidation, evidence provenance, missing evidence, and WF42 action mapping.
- Fail-closed behavior remains visible when upstream source freshness is `partial / review_required`.
- WF53 sector/correlation artifacts now exist and are consumed as review-only concentration context when fresh.
- Recommendation objects and top-level packet explicitly deny canonical, portfolio, deployment-state, and trade mutation.
- Main-session QC reran py_compile, post-close packet generation, daily-review tests, and direct JSON inspection.

## Validation / evidence target
- schema/unit test for recommendation object
- manual packet generation from a known candidate case
- proof that canonical mutation flags remain false
- audit that output wording stays recommendation-only and owner-gated

## Next action
- Keep WF42 v1 in monitoring / repeat-proof posture. Use it as an input to WF56 proposal packets only after WF56 schema, risk, invariant, patch-scope, and authority-vocabulary validators exist.

## Key files
- `06. Playbooks/Project Continuity/Workflow 42 - Capital Deployment Recommendation Object.md`
- `06. Playbooks/Daily Review Objects Contract.md`
- `scripts/daily_review_objects.py`
- `scripts/test_daily_review_objects.py`
- `03. Portfolio/Portfolio Snapshot.md`
- `02. Markets/Technical Entry Sheet.md`
- `02. Markets/Deployment Trigger Sheet.md`
- `06. Playbooks/Promotion Review Queue.md`
