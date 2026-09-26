---
name: "veritas-os2-cleanup-router"
description: "Cleanup safety, source-defect and partial-apply recovery; retained-proof protection; retirement. Verify without live cleanup; route approved archive work."
---

# Veritas OS2 Cleanup Router

## Purpose

Use this skill to classify, retire, archive, or validate obsolete workspace surfaces. It is a cleanup router, not standing destructive authority. An exact user-authorized retirement scope may be applied with manifest, hashes, rollback, and post-apply proof.

## First Reads

Start with the exact candidate, cleanup entry point and governing lifecycle procedure. For tmp cleanup, inspect `08. Audits/Workspace Lifecycle and Deletion Control Plan - 2026-09-08.md`, then the named script and its owner tools before broad scanning. Separate inspection-only scope from authority to generate proof files or apply moves.

Use these routing and lane checks only when needed, after verifying their current source paths and write gates:

```powershell
python scripts\workflow_router.py WF88 --answer all --validate
python -B scripts\concurrent_lane_manager.py --status --active-lease-safety --validate
```

For SQLite lifecycle work with proof-output writes authorized, use `python scripts\db_lifecycle_manifest.py --write --validate`; otherwise read the existing manifest and state its freshness limits.

## Read-Only Cleanup Safety Review

1. Inspect preview and apply paths before invoking a cleanup command. In the inspected owners, `tmp_cleanup.py --dry-run` still writes its report and hash cache, and `bounded_auto_archive.py` writes a report even without `--apply`. Recheck current source; a no-move preview is not necessarily read-only. Finish with identified side effects and use source inspection or a verified stdout-only validator when writes are excluded.
2. Compare the named entry point with `scripts/tmp_cleanup.py` and `scripts/bounded_auto_archive.py` where applicable. Trace reference protection, actual move/delete calls, archive preservation and manifest persistence separately. Static protected names are not a live lane-reference check; input `reference_count` metadata is not a fresh lookup; a directory record with a null hash is not a per-file recovery manifest. For traversal or post-move reporting defects, use [cleanup source-defect verification](references/source-defect-verification.md) to distinguish static findings, no-disk-write reproduction and untested repair proposals; when an authorized apply crashed or its report predates the run, use [partial-apply recovery](references/partial-apply-recovery.md). Finish with the safeguard each path actually enforces, rather than transferring the documented owner's guarantees to an ad hoc script.
3. Apply Cleanup Sequence steps 1–5 as review criteria, not permission to create a manifest or move files. For an uncovered safeguard, name the responsible entry points and proposed regression cases: terminal proof and its containing directory remain protected, missing proof stays visible, active write overlap blocks, and stale reference metadata cannot authorize movement. Keep proposed guards and tests explicitly unimplemented until separately verified. Finish with a bounded recommendation and the original validation result unchanged.

## Alerts-OS Finance Rule

Use [Veritas Intelligence Effort Router](../veritas-intelligence-effort-router/SKILL.md#active-truth-route) for guarded SQL, freshness checks and any session-matched alerts-chain refresh. Reuse fresh, complete current-window proof; do not run an unconditional midday chain during cleanup. The cleanup-specific retirement check, when proof-output writes are authorized, is:

```powershell
python scripts\alerts_os_pivot_validator.py --write --validate
```

Retired portfolio-management, paper-state, deployment, trade-grade, old data-plane, and old cache artifacts are historical evidence only. They must not be reopened as current sources, indexed into active semantic memory, or recreated by a cleanup validator. The validator's recreated-retired check reads two registries — `RETIRED_RUNTIME_PATHS` and the runtime retirement archive manifest's source list — so absence from the constant alone does not make a path safe to recreate or re-document. When proving no producer can recreate retired state, enumerate documented manual refresh chains as well as scheduled payloads, and sweep the retired module's name across instruction surfaces, classifying every hit before fixing. Clean the live instruction paths — prompt-template command lists, producer remediation or warning strings, changed-file router trigger sets and recommendations; leave deny-guard tests asserting the retired stage's absence and generated derivation artifacts (graphify-out regenerates each run).

When extending or validating a retirement archive manifest, check each recorded source against live chain manifests first: a manifest source a live window still produces keeps it and the pivot validator red on every chain day (verified: a still-live producer with three tmp paths sitting in the retirement manifest). Resolution is an owner decision — never repeated temp-file deletion or validator weakening.

When a review surface flags a recreated retired path, remove it by bounded quarantine, never blind deletion and never force-green: verify the retirement archive manifest preserves the path (manifest status ok; the path listed with a destination and sha256; hash-verify the destination when in doubt), confirm the recreated file is regenerable producer output rather than canon, then move it to a dated path under `tmp/quarantine/`. Re-run the pivot validator to clear the recreated-retired error, then regenerate the consuming control packets.

Removing a retired producer's stage from chain or window manifests follows [retired producer manifest removal](references/retired-producer-manifest-removal.md): consumer classification by real reads, replacement dependencies, archive sequencing, and the counted edit method. A derived code-graph manifest blocked on uncommitted deletions takes a [deleted-sources packet](references/derived-manifest-deleted-sources-packet.md): evidence only, never a hand-edit; the prune stays owner-pathed.

## Cleanup Sequence

1. Resolve exact candidate paths and current owners.
2. Prove no enabled scheduler, active workflow, skill, PM source, checkpoint, vector source, lifecycle rule or retained lane-proof reference depends on the candidate. Include terminal lanes; active admission alone is not a retention check. For missing terminal evidence, use [historical lane validation](../veritas-workspace-audit-orchestrator/references/historical-lane-validation.md).
3. Separate immutable audit/history from active current state.
4. For SQLite, use the backup API, integrity check, foreign-key check, and content hash; preserve nonempty WAL state atomically.
5. Create a content-addressed manifest with source path, destination path, size, hash, reason, rollback, and validation.
6. Apply only the exact authorized move/archive set.
7. Verify source absence, destination hash equality, active-reference absence, and all downstream validators.
8. Never delete historical ledgers merely to make a scan green.

## Stale Validator Expectations

After a retirement, change a validator's existence requirement only when the canonical retirement contract makes that operational path forbidden. Confirm the exact path and expected absence against the retirement manifest and canonical validator before changing the expectation, because one surface can require a file while the retirement validator rejects it.

Editing Go validator source changes nothing until the binary is rebuilt; a green `go test` is not a refreshed proof. Rebuild each affected executable (`go build -o .\bin\<name>.exe .\cmd\<name>`) and re-run it. A consumer that embeds the package statically needs its own rebuild even when its own source is untouched. Confirm with `go_binary_freshness_guard.py --write --validate` (stale_count 0, missing_count 0).

## Junction-Probe Database Sets

Before moving any flagged set of database files, resolve every junction link in the candidate tree and confirm its target stays inside the probe folder. A junction whose files sit in an adjacent parent directory reports identical inodes under several child paths, so a flagged count can collapse to far fewer physical files (verified 2026-09-24: 8 flagged paths were 2 real files reached twice). Only after junction targets are confirmed internal may the archive apply run. A junction linking outside the probe folder or into a live agent store makes the whole set non-archivable.

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
