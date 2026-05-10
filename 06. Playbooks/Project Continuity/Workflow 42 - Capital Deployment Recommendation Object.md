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
- stable sector/correlation artifact remains absent; v1 explicitly marks `sector_correlation_check=missing_artifact_manual_fallback_required` rather than pretending confidence.
- append-only state-history / owner-outcome retention remains absent and is tracked by WF43.
- repeat window proof before closure.

## Trust gates passed for v1
- Packet schema now includes owner approval required/granted, confidence, trust/source freshness, risk/invalidation, evidence provenance, missing evidence, and WF42 action mapping.
- Fail-closed behavior remains visible when upstream source freshness is `partial / review_required`.
- Recommendation objects and top-level packet explicitly deny canonical, portfolio, deployment-state, and trade mutation.
- Main-session QC reran py_compile, post-close packet generation, daily-review tests, and direct JSON inspection.

## Validation / evidence target
- schema/unit test for recommendation object
- manual packet generation from a known candidate case
- proof that canonical mutation flags remain false
- audit that output wording stays recommendation-only and owner-gated

## Next action
- Move WF42 v1 to monitoring/closeout after repeat proof; proceed to WF43 append-only state-history design/implementation without enabling model-driven deployment.

## Key files
- `06. Playbooks/Project Continuity/Workflow 42 - Capital Deployment Recommendation Object.md`
- `06. Playbooks/Daily Review Objects Contract.md`
- `scripts/daily_review_objects.py`
- `scripts/test_daily_review_objects.py`
- `03. Portfolio/Portfolio Snapshot.md`
- `02. Markets/Technical Entry Sheet.md`
- `02. Markets/Deployment Trigger Sheet.md`
- `06. Playbooks/Promotion Review Queue.md`
