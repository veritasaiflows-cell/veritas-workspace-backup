# Skill Consolidation Review - 2026-08-31

Status: current review snapshot. It is evidence and routing only; it does not authorize skill lifecycle applies, removals, archive/delete work, configuration/runtime changes, finance-canon changes, account action, capital deployment, or paper/live execution.

## Current denominator

- Live registry: 69 eligible skills and 68 command-visible skills.
- Workspace bodies: 51 total = 39 canonical owners + 12 retired/deprecated compatibility fallbacks.
- Use the 39 canonical owners for consolidation decisions. The earlier 57 command-visible count is historical, not the current denominator.

## Completed residue repair

1. Retargeted the active PM implementation queue and WF74 autonomy router from deprecated `operating-procedure-repository-manager` to `workspace-governor`.
2. Corrected the ownership map for the active Finance Alert Canon Surface Ownership Procedure: `veritas-intelligence-effort-router` is now the primary routing owner, with `veritas-response-contract` retaining response and authority wording.
3. Reconciled the Skills Governance Index heading to 39 canonical owners and 12 fallbacks.
4. Marked `Skill Consolidation Matrix - 2026-07-02.md` as historical and superseded for current classification while preserving its July decision record.

## Governed merge applied

Applied Skill Workshop proposal: `disciplined-implementation-20260831-6d62876bcc`, under Randall's explicit approval.

The live `disciplined-implementation` body now absorbs the reusable parts of `implementation-friction-closeout`: recurring-friction classification, producer/consumer ordering, exact-write-surface discipline, and the existing-skill full-body/body-replacement guard.

The applied live body read back as a complete 11,963-byte document with no proposal wrapper or `status: proposal` residue. Local validation and frozen independent QA passed. Under Randall's later explicit approval, Skill Workshop applied `implementation-friction-closeout-20260831-4b9efb35fc`. The retained source is now a complete 3,074-byte deprecated compatibility router to `disciplined-implementation`, with no live proposal wrapper or `status: proposal` residue. It remains live and does not authorize deletion.

## Intentional separations

- Keep `veritas-technical-pass` separate from `veritas-entry-policy-opportunity-surface`: technical truth versus thin visibility routing.
- Keep `otel-operations-analyst` separate from `privacy-safe-telemetry-expansion`: read-only interpretation versus owner-gated telemetry changes.
- Keep `veritas-investment-deck` separate from `veritas-pdf-brief` until usage demonstrates that slides are only fixed-layout PDF packaging.
- Keep implementation, model-routing, isolated-agent, and QA owners separate: they share safeguards but own different decisions.
- Retain retired compatibility and deny-only skills until active references are fully drained and removal is separately authorized.

## Deferred residue

The legacy manual WF78 dashboard and phase-executor scripts have no active cron consumer but still contain retired-route vocabulary. Do a separate consumer inventory and reference-safe retirement/quarantine lane before changing or deleting those scripts.

## Validation

- `python -B scripts/test_skill_route_ownership_residue.py` - pass
- `python -B scripts/test_wf74_autonomy_work_router.py` - pass
- `python -B scripts/test_pm_implementation_job_queue_capabilities.py` - pass
- `python -B scripts/test_pm_implementation_job_queue_control_packet_preference.py` - pass
- `python -m py_compile scripts/pm_implementation_job_queue.py scripts/wf74_autonomy_work_router.py scripts/test_skill_route_ownership_residue.py` - pass
- `python scripts/changed_file_validator_router.py ... --write --validate` - pass for the six repaired route/documentation files
- `python scripts/skill_workshop_body_guard.py --write --validate` - post-apply pass: 51 live skill bodies, zero critical/errors/warnings
- `python scripts/skill_core_proof_tier_audit.py --validate` - post-apply pass: 13/13 Tier 2 local proof
- `openclaw skills check --json` - post-apply pass: 69 eligible, zero blocked or missing requirements
- Fresh independent QA of the actual applied body - pass: target/source/audit SHA-256 values stayed frozen; no thin-wrapper, authority, or source-retirement defect found
- Compatibility-router apply `implementation-friction-closeout-20260831-4b9efb35fc` - post-apply body guard, core audit, registry check, focused 38/13 regression, changed-file validation, and whitespace check passed
- Fresh independent QA of the compatibility-router snapshot - pass: all four frozen source/governance/audit/regression-test hashes and byte sizes stayed stable; no proposal residue, authority, accounting, or removal-gate defect found

## Next safe action

The compatibility conversion is applied. Keep the router in place while active references drain. Only after a separate reference/residue review and Randall's explicit archive/delete/removal approval may the source be considered for removal; do not delete it in this or a follow-on validation lane.
