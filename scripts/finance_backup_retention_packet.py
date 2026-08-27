#!/usr/bin/env python3
"""Build a review-only retention proposal for backups/.

Answers the blocker raised by backup_rollback_delete_prep_packet.py:
"keep the newest valid recovery point per backup family and propose only older
redundant bundles after restore proof."

Retention rule (a bundle is RETAINED if either holds):
  1. it is among the newest --keep bundles in its family, or
  2. it is the newest holder of its content signature.

Rule 2 is the safety rule. A bundle is only ever proposed for deletion when a
strictly newer backup carries the byte-equivalent table/row state, so no unique
recovery state can be proposed for deletion. This matters: backups/proof-join-*
holds 200 rows in disciplined_reference_levels that no longer exist live.

Never deletes, moves, renames, checkpoints, vacuums, or restores. Every SQLite
read is performed on a temp copy so nothing under backups/ is opened for write.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sqlite3
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from market_data_utils import atomic_write_json  # noqa: E402

WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
BACKUPS = WORKSPACE_ROOT / "backups"
LIVE_CANON = WORKSPACE_ROOT / "state" / "finance" / "finance-canon.sqlite"
OUT = WORKSPACE_ROOT / "tmp" / "finance-backup-retention-packet.json"

SCHEMA = "veritas.finance_backup_retention_packet.v1"

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "delete_performed": False,
    "archive_performed": False,
    "move_performed": False,
    "rename_performed": False,
    "restore_performed": False,
    "sqlite_write_performed": False,
    "sqlite_checkpoint_or_vacuum_performed": False,
    "canon_or_portfolio_mutation_performed": False,
    "config_or_runtime_mutation_performed": False,
    "cron_schedule_mutation_performed": False,
    "paper_or_live_execution_performed": False,
    "brokerage_or_account_action_performed": False,
    "customer_or_external_output_performed": False,
    "owner_approval_inferred": False,
}


def utc(ts: float) -> str:
    return datetime.fromtimestamp(ts, timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def signature(db: Path) -> tuple[str, int, int, str]:
    """Return (sig, table_count, total_rows, integrity) for a SQLite file."""
    con = sqlite3.connect(f"{db.resolve().as_uri()}?mode=ro", uri=True)
    try:
        integrity = con.execute("PRAGMA quick_check").fetchone()[0]
        rows: list[tuple[str, int]] = []
        for (name,) in con.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ):
            rows.append((name, con.execute(f'SELECT COUNT(*) FROM "{name}"').fetchone()[0]))
    finally:
        con.close()
    payload = json.dumps(rows, sort_keys=True).encode()
    total = sum(c for _, c in rows)
    return hashlib.sha256(payload).hexdigest(), len(rows), total, integrity


def safe_signature(src: Path, scratch: Path) -> dict[str, Any]:
    """Signature via temp copy so backups/ is never opened for write."""
    dst = scratch / f"{hashlib.sha256(str(src).encode()).hexdigest()[:16]}.sqlite"
    try:
        shutil.copy2(src, dst)
        sig, tables, total, integrity = signature(dst)
        return {"signature": sig, "table_count": tables, "total_rows": total,
                "integrity": integrity, "error": None}
    except Exception as exc:  # noqa: BLE001 - surfaced into the packet, never swallowed
        return {"signature": None, "table_count": None, "total_rows": None,
                "integrity": None, "error": f"{type(exc).__name__}: {exc}"}
    finally:
        dst.unlink(missing_ok=True)


def discover_bundles() -> list[dict[str, Any]]:
    """A bundle is a family's immediate child dir, else the family itself."""
    bundles: list[dict[str, Any]] = []
    if not BACKUPS.is_dir():
        return bundles
    for family in sorted(p for p in BACKUPS.iterdir() if p.is_dir()):
        children = sorted(p for p in family.iterdir() if p.is_dir())
        roots = children if children else [family]
        for root in roots:
            files = [p for p in root.rglob("*") if p.is_file()]
            if not files:
                continue
            bundles.append({
                "family": family.name,
                "path": str(root.relative_to(WORKSPACE_ROOT)).replace("\\", "/"),
                "_abs": root,
                "file_count": len(files),
                "size_bytes": sum(p.stat().st_size for p in files),
                "newest_mtime": max(p.stat().st_mtime for p in files),
                "_sqlites": sorted(p for p in root.rglob("*.sqlite")),
            })
    return bundles


def build(keep: int) -> dict[str, Any]:
    bundles = discover_bundles()
    scratch = Path(tempfile.mkdtemp(prefix="retention-", dir=WORKSPACE_ROOT / "tmp"))
    try:
        live_sig = safe_signature(LIVE_CANON, scratch) if LIVE_CANON.exists() else None
        for b in bundles:
            b["databases"] = [
                {"file": str(p.relative_to(WORKSPACE_ROOT)).replace("\\", "/"),
                 "size_bytes": p.stat().st_size, **safe_signature(p, scratch)}
                for p in b["_sqlites"]
            ]
    finally:
        shutil.rmtree(scratch, ignore_errors=True)

    # Rule 1: newest --keep per family.
    by_family: dict[str, list[dict[str, Any]]] = {}
    for b in bundles:
        by_family.setdefault(b["family"], []).append(b)
    for group in by_family.values():
        group.sort(key=lambda x: x["newest_mtime"], reverse=True)
        for idx, b in enumerate(group):
            b["_rank"] = idx
            b["_recent"] = idx < keep

    # Rule 2: newest holder of each content signature.
    newest_for_sig: dict[str, dict[str, Any]] = {}
    for b in sorted(bundles, key=lambda x: x["newest_mtime"], reverse=True):
        for db in b["databases"]:
            sig = db["signature"]
            if sig and sig not in newest_for_sig:
                newest_for_sig[sig] = b

    for b in bundles:
        unique = [db["signature"] for db in b["databases"]
                  if db["signature"] and newest_for_sig.get(db["signature"]) is b]
        failed = [db for db in b["databases"] if db["error"] or db["integrity"] not in (None, "ok")]
        b["_unique_signatures"] = unique
        b["_unreadable"] = bool(failed)
        reasons = []
        if b["_recent"]:
            reasons.append(f"newest_{keep}_in_family")
        if unique:
            reasons.append("sole_newest_holder_of_content_signature")
        if failed:
            reasons.append("unreadable_or_failed_integrity_retain_for_inspection")
        b["retain"] = bool(reasons)
        b["retain_reasons"] = reasons
        b["delete_candidate_reason"] = (
            None if reasons else "content_signature_preserved_by_a_strictly_newer_backup"
        )

    rows = []
    for b in sorted(bundles, key=lambda x: (x["family"], -x["newest_mtime"])):
        rows.append({
            "family": b["family"],
            "path": b["path"],
            "rank_in_family": b["_rank"],
            "file_count": b["file_count"],
            "size_bytes": b["size_bytes"],
            "size_mb": round(b["size_bytes"] / 1048576, 3),
            "newest_mtime_utc": utc(b["newest_mtime"]),
            "database_count": len(b["databases"]),
            "unique_signature_count": len(b["_unique_signatures"]),
            "integrity_ok": not b["_unreadable"],
            "retain": b["retain"],
            "retain_reasons": b["retain_reasons"],
            "delete_candidate_reason": b["delete_candidate_reason"],
            "databases": b["databases"],
        })

    proposed = [r for r in rows if not r["retain"]]
    retained = [r for r in rows if r["retain"]]
    digest = hashlib.sha256(
        json.dumps(sorted(r["path"] for r in proposed), sort_keys=True).encode()
    ).hexdigest()

    total = sum(r["size_bytes"] for r in rows)
    reclaim = sum(r["size_bytes"] for r in proposed)

    return {
        "schema": SCHEMA,
        "generated_at_utc": now_utc(),
        "status": "ok",
        "purpose": "Review-only retention proposal for backups/. Owner approval required before any deletion.",
        "authority_boundary": AUTHORITY_BOUNDARY,
        "retention_rule": {
            "keep_newest_per_family": keep,
            "always_keep_newest_holder_of_each_content_signature": True,
            "always_keep_unreadable_or_failed_integrity": True,
            "delete_only_when": "a strictly newer backup carries the identical table/row signature",
            "date_cutoff_used": False,
            "date_cutoff_rationale": "Two families are still written by active cron; a date cutoff could strip a live safety net.",
        },
        "live_reference": {
            "path": str(LIVE_CANON.relative_to(WORKSPACE_ROOT)).replace("\\", "/"),
            **(live_sig or {"error": "live_canon_missing"}),
        },
        "summary": {
            "bundle_count": len(rows),
            "family_count": len(by_family),
            "total_bytes": total,
            "total_mb": round(total / 1048576, 2),
            "retained_count": len(retained),
            "proposed_delete_count": len(proposed),
            "proposed_delete_bytes": reclaim,
            "proposed_delete_mb": round(reclaim / 1048576, 2),
            "database_integrity_failures": sum(1 for r in rows if not r["integrity_ok"]),
            "delete_performed": False,
            "microbatch_digest": digest,
            "approval_phrase": (
                f"Approve finance backup retention delete microbatch {digest} "
                f"exactly as listed in tmp/finance-backup-retention-packet.json."
            ),
        },
        "proposed_delete": proposed,
        "retained": retained,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--keep", type=int, default=3)
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--validate", action="store_true")
    ap.add_argument("--pretty", action="store_true")
    args = ap.parse_args()

    packet = build(args.keep)

    errors: list[str] = []
    if packet["summary"]["database_integrity_failures"]:
        errors.append("database_integrity_failure_present")
    if packet["live_reference"].get("error"):
        errors.append("live_reference_unavailable")
    packet["validation"] = {"status": "ok" if not errors else "error", "errors": errors, "warnings": []}

    if args.write:
        atomic_write_json(OUT, packet)

    s = packet["summary"]
    if args.pretty:
        print(json.dumps(packet["summary"], indent=1))
    else:
        print(f"bundles={s['bundle_count']} retained={s['retained_count']} "
              f"proposed_delete={s['proposed_delete_count']} "
              f"reclaim={s['proposed_delete_mb']} MB of {s['total_mb']} MB")
    if args.validate and errors:
        print("VALIDATION ERRORS: " + ", ".join(errors), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
