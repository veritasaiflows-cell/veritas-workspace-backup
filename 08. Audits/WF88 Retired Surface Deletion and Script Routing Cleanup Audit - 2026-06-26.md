# WF88 Retired Surface Deletion and Script Routing Cleanup Audit - 2026-06-26

## Verdict

WF88 should own the workspace drag-reduction program, but it should not start with blind deletion.

The safe first move is a parallel cleanup plan with four lanes:

1. tmp artifact deletion packet
2. script and route contraction
3. database lifecycle archive packet
4. cron/runtime clutter proof

Deletion can begin only from exact owner-gated packets that prove active references, hashes, rebuildability, tombstones, rollback, and post-delete validation. Current proof supports cleanup planning and route contraction now; it does not support broad file deletion yet.

## Authority Boundary

This audit is review-only. It does not delete, move, archive, mutate cron schedules, mutate config/runtime/auth, mutate SQL/canon/portfolio/cash/sizing/risk state, perform paper/live/brokerage/account action, create customer/public output, or infer owner approval.

WF88 may coordinate the cleanup program because cleanup drag directly affects measurement quality, implementation cadence, and Veritas OS 2.0 learning loops. WF88 does not gain destructive authority from that coordination role.

## Evidence Read

- `workflow_router.py WF88 --answer all`: WF88 is P1 `design_bootstrap`, helper-safe, review-only, and blocked by missing experiment registry/intake.
- `concurrent_lane_manager.py --status --write --validate`: active lane count was `0` before this audit lane; this audit lane was leased and run as `WF88::retired_surface_deletion_script_routing_audit_20260626`.
- `tmp/tmp-lifecycle-guard.json`: `11,443` tmp files, `5,699` tmp JSON files, `1,735.86 MB` tmp footprint, `2,627` stale tmp JSON files, and `3,083` cleanup-preview-eligible files. It is preview-only and explicitly blocks delete/move/archive without separate approval.
- `tmp/human-canon-thinning-retirement-inventory.json`: `27` classified items; `8` keep, `9` narrow-on-demand, `3` retire candidates, `7` do-not-retire; `archive_or_delete_candidates_ready_now=0`.
- `tmp/db-lifecycle-manifest.json`: `94` database files, `150` sidecars, `1` archive-ready database candidate, `0` delete-ready databases. The archive-ready file is `tmp/wf72-entry-stop-sql-activation-rollback-drill.sqlite`; owner approval is still required before move/delete.
- `08. Audits/Human Canon Thinning Retirement Audit - Veritas - 2026-06-22.md`: legacy answer packet routing, broad human-note parity checks, and default pre-thinning validation semantics are the script/routing drag candidates.
- `06. Playbooks/Active Workflows.md`: WF50/archive/root cleanup and workspace governor remain approval-gated; suggestions are not authority.

## Drag Sources

### 1. tmp Sprawl

Current state:

- `tmp/` is too large and noisy for fast workspace trust.
- The current guard found `3,083` preview-eligible cleanup candidates, but only preview classification exists.
- Samples include old research automation packets, stale proof reports, old paper-readiness previews, old portfolio mutation previews, and a nested `tmp/audio-tools/node_modules` dependency cache.

Risk:

Deleting from `tmp/` without a reference-aware packet can break current dashboards, source-lineage proof, audit trails, rollback drills, or producer/consumer tests.

WF88 action:

Create a deletion proposal generator that consumes `tmp/tmp-lifecycle-guard.json`, reference search/index proof, and artifact index ownership. It should emit exact microbatches by owner family, not a single broad purge.

First target microbatches:

- stale research automation sample packets
- stale one-off proof reports from closed WF38/WF40/WF43/WF52/WF54 history
- old promotion candidate samples
- stale paper-readiness order previews after proving no live paper/account dependency
- dependency cache candidates such as `tmp/audio-tools/node_modules` only after local audio transcription rebuild proof exists

Do not include:

- current `tmp/*.json` front doors
- WF78/WF84/WF85/WF86/WF87 proof
- `tmp/veritas-artifact-index.sqlite`
- `tmp/finance-intelligence-state.sqlite`
- `tmp/otel-ops.sqlite`
- paper position state
- current PM/cron/status/startup/future-session packets
- portfolio mutation proposals, approvals, or audit trails unless a separate retention packet proves supersession

### 2. Script And Routing Drag

Current state:

- The active human-canon thinning inventory says no scripts are delete-ready.
- It does identify routine route drag:
  - `scripts/ticker_answer_packet.py` should remain compatibility-only, not routine WF85 validation.
  - human-note SQL/Go parity checks should move out of default runtime scoring.
  - pre-thinning table/header checks in `validate_canonical_ownership.py` should be mode-gated.
  - `veritas_question_router.py` and `today_card_generator.py` should label human notes as context/policy/narrative, not structured data owners.

Risk:

Deleting compatibility scripts before route contraction is complete removes rollback and parity proof. Keeping them in default routes wastes validation time and confuses ownership.

WF88 action:

Treat script cleanup as route contraction before file deletion.

Parallel implementation slices:

- Route contraction lane: remove `ticker_answer_packet.py` from normal WF85 validation; retain retirement-plan validation.
- Runtime budget lane: move human-note SQL/Go parity checks behind a migration mode in runtime/harness scoring.
- Canon ownership lane: keep `validate_canonical_ownership.py`, but mode-gate legacy table completeness checks.
- Label hygiene lane: relabel human-note links in routers/cards as human context, not structured owners.

Deletion threshold:

Only after route contraction proves `active_reference_count=0`, compatibility readers are classified, and rollback/rebuild paths exist should a script be considered for archive. No script deletion is ready now.

### 3. Database Lifecycle Drag

Current state:

- `db_lifecycle_manifest.py` reports one archive-ready database candidate: `tmp/wf72-entry-stop-sql-activation-rollback-drill.sqlite`.
- Delete-ready count is `0`.
- The manifest is `ready_for_owner_decision`, not apply authority.

Risk:

Databases often carry rollback, shadow, or proof lineage. Removing them without manifest/tombstone proof can corrupt future audit claims.

WF88 action:

Keep DB cleanup as its own lane:

- refresh `db_lifecycle_manifest.py --write --validate`
- inspect `tmp/db-lifecycle-archive-approval-packet.json`
- prepare an owner approval microbatch
- archive only after explicit approval
- run DB lifecycle manifest again after archive

No DB deletion should be part of the first WF88 cleanup pass.

### 4. Cron And Runtime Clutter

Current state:

- Earlier audits found disabled one-shots, retired handoff jobs, old canaries, and old alert senders as clutter.
- Recent cron contracts are clean, but disabled job cleanup is config/runtime-adjacent and needs explicit approval.

Risk:

Disabled cron jobs usually do not cost runtime, but they increase audit noise and rollback ambiguity. Deleting them touches scheduler/runtime state.

WF88 action:

Prepare a cron-retirement packet only:

- list disabled jobs by category
- prove no enabled contract depends on them
- preserve rollback/export
- ask for exact approval before deletion

Do not mutate cron schedules, job configs, or delivery settings from WF88 cleanup planning.

## Parallel Plan

| Lane | Owner | Mode | Deliverable | Can Run In Parallel | Stop Line |
|---|---|---|---|---|---|
| `WF88::TMP-DELETE-PROPOSAL` | Veritas main plus helper | Review-only proposal | `tmp/wf88-tmp-deletion-proposal.json` and owner-readable summary | Yes | No delete/move/archive until exact approval |
| `WF88::SCRIPT-ROUTE-CONTRACTION` | Veritas main | Implementation | Route changes that remove retired compatibility checks from default paths | Yes, if exact files leased | No script delete, no source feeder retirement |
| `WF88::DB-LIFECYCLE-MICROBATCH` | Veritas main | Owner decision packet | Archive packet for `tmp/wf72-entry-stop-sql-activation-rollback-drill.sqlite` | Yes | No archive/delete before approval |
| `WF88::CRON-RETIRED-JOB-PACKET` | Veritas main plus cron skill | Review-only packet | Disabled/retired cron cleanup packet with export/rollback proof | Yes | No cron mutation before approval |
| `WF88::POST-CLEANUP-VALIDATION` | Veritas main | QA after state change | changed-file, route, lifecycle, cron, release proof | No, runs after changes | No success claim while gates are stale |

## What Can Start Now

Start now without further approval:

- write the WF88 cleanup audit
- update WF88 continuity to include cleanup/drag-reduction as a workstream
- build review-only deletion proposal scripts or packets
- patch script/routing defaults that reduce validation drag without deleting source files
- run reference checks and lifecycle manifests
- prepare owner approval packets

Do not start without exact approval:

- delete files
- move/archive files
- remove disabled cron jobs
- delete databases or sidecars
- retire source feeders
- remove Python fallback helpers
- mutate config/runtime/auth/channel/startup/service surfaces

## First Implementation Sequence

1. Build `scripts/wf88_retired_surface_cleanup_plan.py`.
   - Inputs: `tmp/tmp-lifecycle-guard.json`, `tmp/human-canon-thinning-retirement-inventory.json`, `tmp/db-lifecycle-manifest.json`, artifact index, workflow routing index.
   - Output: `tmp/wf88-retired-surface-cleanup-plan.json` and optional Markdown.
   - Must be review-only.

2. Patch routine script routing drag.
   - Remove legacy `ticker_answer_packet.py` from normal WF85 route validation.
   - Keep it in `ticker_answer_packet_retirement_plan.py` and compatibility proof.
   - Move human-note parity checks out of default runtime scorecard paths.

3. Prepare tmp deletion microbatch packet.
   - Start with small, closed-history stale tmp files.
   - Include hashes, sizes, active-reference count, owning workflow, tombstone path, and rollback/rebuild proof.

4. Prepare DB archive approval microbatch.
   - One candidate only: `tmp/wf72-entry-stop-sql-activation-rollback-drill.sqlite`.
   - No delete.

5. Validate after each state-changing lane.
   - `python scripts\workflow_router.py WF88 --answer all --validate`
   - `python scripts\changed_file_validator_router.py --write --validate`
   - `python scripts\validator_bundle_router.py --write --validate`
   - `python scripts\implementation_release_contract.py --phase blocking --write --validate`
   - relevant lifecycle/cron/script tests for touched lanes

## Audit Conclusion

The blunt truth: workspace drag is real, but the workspace is not yet holding a clean deletion-authority packet. The current proof says:

- route contraction can start now
- deletion proposal generation can start now
- broad deletion cannot start safely yet
- database archive has one candidate but still requires owner approval
- script deletion is not ready
- source feeder and Python fallback retirement remain blocked

WF88 should become the coordination owner for this cleanup because Veritas OS 2.0 needs cleaner measurement surfaces. But WF88 must enforce proof-first deletion, not become a shortcut around workspace governor stop lines.

