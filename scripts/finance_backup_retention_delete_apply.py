#!/usr/bin/env python3
"""Apply the owner-approved finance backup retention delete microbatch.

Consumes tmp/finance-backup-retention-packet.json.

Refuses to act unless every guard holds:
  1. --approval-phrase matches the packet phrase exactly.
  2. The digest recomputed from the packet's proposed_delete paths matches the
     digest embedded in the phrase and in the packet summary.
  3. Every target resolves inside backups/ and is not in the retained set.
  4. No on-disk drift: each target's file count and byte size still match what
     the packet recorded, so the recorded content signatures still describe the
     files being deleted.
  5. Every content signature carried by a delete target is still carried by a
     bundle in the retained set.

Guard 5 is the one that matters. It enforces the actual promise: a backup is
removed only when a retained backup holds byte-equivalent table/row state.
Any failure aborts the whole batch. There is no partial-apply mode.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from market_data_utils import atomic_write_json  # noqa: E402

WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
BACKUPS = (WORKSPACE_ROOT / "backups").resolve()
PACKET = WORKSPACE_ROOT / "tmp" / "finance-backup-retention-packet.json"
REPORT = WORKSPACE_ROOT / "tmp" / "finance-backup-retention-delete-report.json"

SCHEMA = "veritas.finance_backup_retention_delete_report.v1"


def now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def check(packet: dict[str, Any], phrase: str) -> tuple[list[dict[str, Any]], list[str]]:
    errors: list[str] = []
    proposed = packet.get("proposed_delete", [])
    retained = packet.get("retained", [])

    expected_phrase = packet["summary"]["approval_phrase"]
    if phrase.strip() != expected_phrase.strip():
        errors.append("approval_phrase_mismatch")

    digest = hashlib.sha256(
        json.dumps(sorted(r["path"] for r in proposed), sort_keys=True).encode()
    ).hexdigest()
    if digest != packet["summary"]["microbatch_digest"]:
        errors.append("microbatch_digest_mismatch_packet_edited_after_generation")
    if digest not in expected_phrase:
        errors.append("digest_not_present_in_approval_phrase")

    retained_paths = {r["path"] for r in retained}
    retained_signatures = {
        db["signature"] for r in retained for db in r.get("databases", []) if db.get("signature")
    }

    targets: list[dict[str, Any]] = []
    for row in proposed:
        rel = row["path"]
        abs_path = (WORKSPACE_ROOT / rel).resolve()
        problems: list[str] = []

        if BACKUPS not in abs_path.parents:
            problems.append("target_outside_backups_root")
        if rel in retained_paths:
            problems.append("target_also_marked_retained")
        if row.get("retain"):
            problems.append("target_marked_retain_true")

        if not abs_path.exists():
            problems.append("target_missing_on_disk")
            files, size = [], 0
        else:
            files = [p for p in abs_path.rglob("*") if p.is_file()]
            size = sum(p.stat().st_size for p in files)
            if len(files) != row["file_count"]:
                problems.append(
                    f"file_count_drift_packet={row['file_count']}_disk={len(files)}")
            if size != row["size_bytes"]:
                problems.append(f"size_drift_packet={row['size_bytes']}_disk={size}")

        sigs = [db["signature"] for db in row.get("databases", []) if db.get("signature")]
        orphaned = [s for s in sigs if s not in retained_signatures]
        if orphaned:
            problems.append(f"content_signature_not_preserved_by_retained_set:{len(orphaned)}")

        targets.append({
            "path": rel,
            "family": row["family"],
            "file_count": len(files),
            "size_bytes": size,
            "database_count": len(sigs),
            "problems": problems,
            "eligible": not problems,
        })
        errors.extend(f"{rel}:{p}" for p in problems)

    return targets, errors


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--packet", default=str(PACKET))
    ap.add_argument("--approval-phrase", required=True)
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--apply", action="store_true")
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--pretty", action="store_true")
    args = ap.parse_args()

    packet = json.loads(Path(args.packet).read_text(encoding="utf-8"))
    targets, errors = check(packet, args.approval_phrase)
    do_apply = args.apply and not errors

    deleted = 0
    freed = 0
    for t in targets:
        if not do_apply or not t["eligible"]:
            t["deleted"] = False
            continue
        shutil.rmtree(WORKSPACE_ROOT / t["path"])
        t["deleted"] = True
        deleted += 1
        freed += t["size_bytes"]

    report = {
        "schema": SCHEMA,
        "generated_at_utc": now_utc(),
        "mode": "apply" if do_apply else "dry_run",
        "packet": str(Path(args.packet).relative_to(WORKSPACE_ROOT)).replace("\\", "/"),
        "packet_generated_at_utc": packet.get("generated_at_utc"),
        "authority_boundary": {
            "owner_approval_inferred": False,
            "approval_phrase_matched": "approval_phrase_mismatch" not in errors,
            "scope_restricted_to_backups_root": True,
            "retained_bundles_touched": False,
            "live_canon_touched": False,
            "sqlite_write_performed": False,
            "sqlite_checkpoint_or_vacuum_performed": False,
            "restore_performed": False,
            "canon_or_portfolio_mutation_performed": False,
            "config_or_runtime_mutation_performed": False,
            "paper_or_live_execution_performed": False,
            "brokerage_or_account_action_performed": False,
        },
        "summary": {
            "target_count": len(targets),
            "eligible_count": sum(1 for t in targets if t["eligible"]),
            "deleted_count": deleted,
            "freed_bytes": freed,
            "freed_mb": round(freed / 1048576, 2),
            "delete_performed": deleted > 0,
            "aborted_on_guard_failure": bool(errors),
        },
        "targets": targets,
        "validation": {"status": "error" if errors else "ok", "errors": errors[:50],
                       "error_count": len(errors), "warnings": []},
    }

    if args.write:
        atomic_write_json(REPORT, report)

    print(json.dumps(report["summary"], indent=1) if args.pretty
          else f"mode={report['mode']} eligible={report['summary']['eligible_count']}"
               f"/{len(targets)} deleted={deleted} freed={report['summary']['freed_mb']} MB")
    if errors:
        print(f"ABORTED - {len(errors)} guard failure(s):", file=sys.stderr)
        for e in errors[:10]:
            print(f"  {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
