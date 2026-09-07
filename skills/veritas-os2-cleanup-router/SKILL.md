---
name: "veritas-os2-cleanup-router"
description: "Route evidence-backed retirement and cleanup without recreating old finance state."
---

# Veritas OS2 Cleanup Router

## Purpose

Use this skill to classify, retire, archive, or validate obsolete workspace surfaces. It is a cleanup router, not standing destructive authority. An exact user-authorized retirement scope may be applied with manifest, hashes, rollback, and post-apply proof.

## First Reads

```powershell
python scripts\workflow_router.py WF88 --answer all --validate
python scripts\concurrent_lane_manager.py --status --write --validate
python scripts\db_lifecycle_manifest.py --write --validate
```

Open the exact owner artifacts and active reference registry before broad scanning.

## Alerts-OS Finance Rule

The active finance route is:

```powershell
python scripts\finance_sql_canon_access.py --write --validate
python scripts\run_alerts_recommendations_chain.py midday --timeout-seconds 120 --write --validate
python scripts\alerts_os_pivot_validator.py --write --validate
```

Retired portfolio-management, paper-state, deployment, trade-grade, old data-plane, and old cache artifacts are historical evidence only. They must not be reopened as current sources, indexed into active semantic memory, or recreated by a cleanup validator.

## Cleanup Sequence

1. Resolve exact candidate paths and current owners.
2. Prove no enabled scheduler, active workflow, skill, PM source, checkpoint, vector source, or lifecycle rule depends on the candidate.
3. Separate immutable audit/history from active current state.
4. For SQLite, use the backup API, integrity check, foreign-key check, and content hash; preserve nonempty WAL state atomically.
5. Create a content-addressed manifest with source path, destination path, size, hash, reason, rollback, and validation.
6. Apply only the exact authorized move/archive set.
7. Verify source absence, destination hash equality, active-reference absence, and all downstream validators.
8. Never delete historical ledgers merely to make a scan green.

## Current-State Versus History

Retire active generated state that maintains account-like structure or operational pathways. Preserve dated historical evidence, audit events, authority events, migration proof, and deny-only safety controls. Historical material must be clearly labeled and excluded from current answer paths.

## Cron Retirement

For scheduled work:

- disable and rename obsolete jobs with a retirement reason and owner-gated rollback
- keep contract state aligned
- do not force delivery jobs simply to clear history
- prove no enabled payload calls retired routes
- require zero enabled scheduler errors at closeout

Use the cron owner skill for scheduler mutations.

## Stop Lines

Stop when scope is unclear, an active reference remains, a hash or integrity check fails, rollback is missing, or the action would affect config, auth, credentials, network, services, external delivery, accounts, money, or execution. Capital and all execution remain outside this OS.

## Closeout

Report:

- exact retired and preserved families
- archive manifest and hash result
- active reference scan
- cron/contract status
- alerts-chain truth and freshness
- validators and limitations
- rollback route

Never call a cleanup complete while a live producer can recreate the retired state.
