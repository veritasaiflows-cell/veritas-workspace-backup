# WF72 Broad Archive Execution Contract

- Generated UTC: 2026-05-24T22:19:41Z
- Status: **active bounded execution contract**
- Owner direction: continue broad archive/flattening phases to completion, keep the OS lean/fast, and harden cron so cleanup pressure does not depend on memory.

## Non-negotiables

- Archive-only before delete; **deletes remain blocked** unless separately exact-approved.
- No config/auth/channel/service/runtime/credential movement.
- No canonical finance notes, active workflow notes, memory, scripts, skills, current-window validator inputs, SQL/cache authority surfaces, or proof-critical artifacts move without exact review.
- Every move requires reference checks, source/destination hashes, manifest, rollback route, and validation.
- Cron may report/propose and run bounded archive suggestions; it must not perform broad canon apply, infer owner approval, mutate config/channels/services, or touch finance/trading authority.

## Active phase sequence

1. Root warning classification.
2. Remaining `tmp/*.py` executable helper disposition.
3. `tmp/*.md` report triage.
4. Backup surface rationalization.
5. Archive-domain thinning.
6. Playbook/workflow redundancy proposal pass.
7. Cron lean-OS cadence hardening.
8. Validation and continuity closeout.

## Current evidence

- `tmp/archive-suggestions.json`: 366 suggestions / 54 inbound-reference candidates / `apply_allowed=false`.
- `tmp/workspace-boundary-check.json`: warning posture with root/data/tmp helper findings.
- `tmp/broad-workspace-archive-phase-plan.*`: plan-only phase map.

## Apply proof required

Reference scan, manifest JSON/MD, SHA-256 before/after, `delete_count=0`, rollback instructions, `artifact_index validate`, `dashboard_truth_lint`, and `workspace_boundary_check` warning reduction or documented residue.
