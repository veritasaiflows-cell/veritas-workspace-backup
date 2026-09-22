# Workspace Lifecycle and Deletion Control Plan

**Status:** active operating plan; archive moves may be owner-approved per exact manifest. Permanent deletion remains separately owner-gated.

## Purpose

Make cleanup repeatable without turning an age-based candidate list into a destructive bulk action. Every future batch must be small, immutable, attributable, reversible through the archive-retention stage, and independently verifiable.

## Lifecycle states

| State | Meaning | Allowed action |
|---|---|---|
| Protected | Canon, runtime, active workflow, database, credential/config, or live-reference surface | No cleanup action |
| Review required | History, archive, ambiguous dependency, directory, or non-classified output | Read-only classification only |
| Archive candidate | Exact file has age, class, hash, and zero active-reference proof | Owner-approved archive move only |
| Archived / retention | Destination hash and source absence are proven | Restore remains available; no deletion |
| Delete candidate | Retention elapsed, restore drill passed, no references, and fresh manifest exists | Requires a second, exact owner deletion approval |

## Required manifest fields

Each archive/delete input is JSON and must include: workspace-relative source path, SHA-256, byte count, lifecycle class, evidence timestamp, dependency/reference result, proposed archive destination, rollback source/destination pair, and the owner-approval reference. The mover must reject paths, hashes, classes, or destinations outside the manifest.

## Control gates

1. Run `python scripts\tmp_cleanup.py --dry-run --days 7`; capture its candidate digest and protection result.
2. Classify a narrow candidate family. Exclude `09. Archive`, active numbered domains, `data`, `memory`, `scripts`, `skills`, databases, directories, and anything with an active reference.
3. Re-hash every proposed source and rerun exact-name reference checks immediately before the move.
4. Use `scripts\bounded_auto_archive.py` with an explicit manifest. It may **move to archive only**; it never deletes.
5. Verify source absence and destination SHA-256 equality, then run `python scripts\bounded_auto_archive.py --validate-last-report`.
6. Rerun the dry run and affected bounded validators. A blocked or changed result halts the next batch.
7. Keep the archive copy through a retention period and complete a restore drill before asking for any permanent deletion authorization.

## Pilot evidence

On 2026-09-08 Phoenix, the first pilot archived 17 top-level transient `tmp` logs/outputs (607,330 bytes) using `tmp/cleanup-infrastructure-20260908/archive-pilot-input.json`. All had zero active references apart from the cleanup hash cache. The move report proves source absence and matching destination hashes; no files were deleted. The subsequent dry run reported 1,962 remaining candidates with zero protection violations.

## Current boundaries

- The 3,905 pre-existing files under `09. Archive` remain `manual_review_required`; none is deletion-ready.
- No cron schedule or automatic deletion is created by this plan.
- A default archive retention duration is intentionally not enacted here. Before permanent deletion, Randall must approve an exact retention policy and deletion manifest.
- **Approved pilot exception (2026-09-08 Phoenix):** the already-proven 17-file generated-residue cleanup pilot has a **14-calendar-day** retention rule, measured from its latest successful all-file restore drill at `2026-09-09T05:01:23Z` (`2026-09-08 22:01:23` Phoenix). Its retention gate expires at `2026-09-23T05:01:23Z` (`2026-09-22 22:01:23` Phoenix). This approval applies only to the frozen 17-file manifest `tmp/cleanup-infrastructure-20260908/archive-pilot-input.json`; it does not approve permanent deletion, create a default rule, or cover any other archive family.

## Archive-family reduction program

The refreshed archive inventory contains 3,923 files. It is not a homogeneous deletion set. The next iterations are deliberately family-specific:

1. **DB Lifecycle - Archived** (250 files / 505 MB): route only through the database lifecycle manifest and a restore/integrity drill. No generic file deletion.
2. **Finance Runtime** (2,578 files / 353 MB): retain until a finance evidence-retention decision identifies replacement proof and a non-finance-safe retention rule. No bulk deletion.
3. **Archived backups** (216 files / 214 MB): route through the existing backup-retention packet, which preserves family coverage and content-signature uniqueness.
4. **Scripts and Tmp Cleanup - Archived** (142 files / 42 MB) and **Auto Archive - Generated Residue** (198 files / 1.4 MB): first candidates for a restore-tested retention microbatch after the mover has hash binding.
5. **Legacy ticker, SQL, workflow, and human-deliverable archives**: retain pending owner classification; they are not suitable for age-only deletion.

For every family, the deliverable is a review packet—not a delete command—with a frozen file list, hashes/bytes, source lineage, retention recommendation, restore-drill result, and post-delete validation plan. Permanent deletion begins only with the smallest family whose packet reaches `delete_ready`.

## Next infrastructure increment

Completed on 2026-09-08 Phoenix: `scripts\bounded_auto_archive.py` now requires every move row to declare a valid SHA-256 and exact byte count, verifies both during eligibility and immediately before the move, and fails closed when the declared destination already exists. It no longer auto-renames a colliding destination. `scripts\test_bounded_auto_archive.py` proves valid bound moves plus hash drift, byte drift, and destination collision rejection.

The first retention packet is `tmp\generated-residue-microbatch-retention-packet-20260908.json`. Its 17-file frozen list is bound to the pilot input's SHA-256, all current non-archive reference checks are zero, and one file completed a byte-identical restore-and-return drill. The packet is **retention_ready, not delete_ready**: a retention duration/rule, per-file replacement proof, applicable integrity rule, and a second exact deletion approval remain required before permanent deletion can even be considered.
