---
name: "disciplined-implementation"
description: "Require lane-register preflight for implementation."
---

# Proposal: Cross-Session Lane Register Gate for Disciplined Implementation

## Goal
Ensure every implementation pass, regardless of Telegram, WebChat, main session, or helper lane, follows the same durable lane coordination contract before writing workspace files.

## Proposed Skill Update
Add this section after the existing **Contract** checklist or before **Implementation Size Classes**.

```markdown
## Cross-Session Lane Register Gate

Before implementation work that may write files, generated artifacts, proof packets, validators, scripts, notes, or control surfaces, check the shared lane register:

```powershell
python scripts\concurrent_lane_manager.py --status --write --validate
```

Use runtime session listings only as advisory. The durable coordination surface is `tmp/concurrent-lane-register.json`.

When the work may run concurrently with another Telegram, WebChat, main, helper, cron, or isolated session:

1. Lease the exact writable surfaces before editing or generating artifacts.
2. Use a narrow workstream id that names the real output owner.
3. Declare all intended writes with `--allowed-write`; do not lease broad folders unless the owner surface is intentionally a folder-level output.
4. Set the lane to `running` when actual work starts and include session metadata when available.
5. Mark the lane terminal with proof when work completes, blocks, or is cancelled.

Example:

```powershell
python scripts\concurrent_lane_manager.py --lease WF85 --workstream freshness-runner-hardening --owner webchat-wf85 --allowed-write scripts\trade_grade_os_freshness_cron_runner.py --allowed-write tmp\trade-grade-os-freshness-cron-runner.json --write --validate
python scripts\concurrent_lane_manager.py --set-status WF85 --workstream freshness-runner-hardening --status-value running --session-key <session-key> --session-id <session-id> --session-label <label> --task-name <task-name> --write --validate
python scripts\concurrent_lane_manager.py --complete WF85 --workstream freshness-runner-hardening --proof tmp\trade-grade-os-freshness-cron-runner.json --write --validate
```

If `concurrent_lane_manager.py --status --write --validate` reports an active lane whose `allowed_writes` overlap the intended change, stop and either wait, choose a non-overlapping output, or ask Randall for priority. Do not rely on chat memory to resolve write ownership.

Old lane records may have `created_at_utc` and `completed_at_utc` without true `started_at_utc`; treat those as legacy lifecycle records, not runtime proof. New lanes should use `started_at_utc`, `ended_at_utc`, and runtime session metadata.
```

## Validation Expected After Apply
- `openclaw skills check`
- `python scripts\concurrent_lane_manager.py --status --write --validate`
- `python scripts\test_concurrent_lane_manager_runtime_metadata.py`

## Boundary
Coordination only. This does not grant helper spawn authority, cron mutation, config/runtime mutation, canon/portfolio mutation, capital deployment, paper/live execution, brokerage/account action, or owner approval inference.
