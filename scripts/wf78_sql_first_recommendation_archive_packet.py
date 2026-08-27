"""Move-only archive helper for deprecated WF78 recommendation surfaces.

This helper is intentionally exact-list and owner-reference gated. It archives
only WF78 recommendation/adjudication compatibility surfaces that have already
been replaced by SQL-first lane-qualified routing.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "tmp" / "wf78-sql-first-recommendation-archive-apply.json"
OUT_MD = ROOT / "tmp" / "wf78-sql-first-recommendation-archive-apply.md"
INVENTORY = ROOT / "tmp" / "wf78-sql-first-archive-candidate-inventory.json"
ARCHIVE_ROOT = ROOT / "09. Archive" / "WF78 SQL-First Deprecated Recommendation Surfaces" / "2026-06-24"
SCHEMA = "veritas.wf78_sql_first_recommendation_archive_packet.v1"

SCRIPT_CANDIDATES = [
    "scripts/wf78_production_tier_adjudication.py",
    "scripts/wf78_tier_a_final_promotion_packet.py",
    "scripts/wf78_tier_b_final_promotion_packet.py",
]

ARTIFACT_CANDIDATES = [
    "tmp/wf78-production-tier-adjudication.json",
    "tmp/wf78-production-tier-adjudication.sqlite",
    "tmp/wf78-tier-a-final-promotion-packet.json",
    "tmp/wf78-tier-b-final-promotion-packet.json",
    "tmp/wf78-tier-b-final-promotion-packet.next-batch.json",
    "tmp/wf78-tier-b-final-promotion-packet.next-batch-2.json",
    "tmp/wf78-tier-b-final-promotion-packet.next-batch-3.json",
    "tmp/wf78-tier-b-final-promotion-packet.production-bench.json",
]

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "archive_move_only": True,
    "delete_allowed": False,
    "overwrite_allowed": False,
    "portfolio_or_canon_mutation_allowed": False,
    "cash_sizing_or_risk_mutation_allowed": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "capital_deployment_allowed": False,
    "owner_approval_inferred": False,
}


def rel(path: Path) -> str:
    return path.resolve().relative_to(ROOT).as_posix()


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def sha256_file(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def archive_destination(source_rel: str) -> Path:
    return ARCHIVE_ROOT / source_rel.replace("/", "\\")


def inventory_ok(inventory: dict[str, Any]) -> tuple[bool, list[str]]:
    errors: list[str] = []
    if inventory.get("status") != "ready_for_versioned_archive_packet":
        errors.append("inventory_not_ready_for_versioned_archive_packet")
    summary = inventory.get("summary") if isinstance(inventory.get("summary"), dict) else {}
    if int(summary.get("active_runtime_blocker_count") or 0) != 0:
        errors.append("inventory_has_active_runtime_blockers")
    if sorted(inventory.get("script_candidates") or []) != sorted(SCRIPT_CANDIDATES):
        errors.append("script_candidate_set_mismatch")
    if sorted(inventory.get("artifact_candidates") or []) != sorted(ARTIFACT_CANDIDATES):
        errors.append("artifact_candidate_set_mismatch")
    return not errors, errors


def build_rows(apply: bool) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for source_rel in SCRIPT_CANDIDATES + ARTIFACT_CANDIDATES:
        source = ROOT / source_rel
        destination = archive_destination(source_rel)
        source_hash = sha256_file(source)
        destination_hash = sha256_file(destination)
        source_exists = source.exists()
        destination_exists = destination.exists()
        already_archived = bool(not source_exists and destination_exists)
        hash_conflict = bool(source_exists and destination_exists and source_hash != destination_hash)
        eligible = (source_exists and not destination_exists) or already_archived
        action = "already_archived" if already_archived else "move" if eligible else "blocked"
        if apply and action == "move":
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(source), str(destination))
            source_exists = source.exists()
            destination_exists = destination.exists()
            destination_hash = sha256_file(destination)
            source_hash = sha256_file(source)
            action = "moved"
        rows.append(
            {
                "source_path": source_rel,
                "archive_path": rel(destination),
                "source_exists": source_exists,
                "archive_exists": destination_exists,
                "source_sha256": source_hash,
                "archive_sha256": destination_hash,
                "eligible_for_move_only_archive": eligible,
                "already_archived": already_archived,
                "destination_hash_conflict": hash_conflict,
                "action": action,
                "rollback": f"Move {rel(destination)} back to {source_rel}",
            }
        )
    return rows


def render_md(payload: dict[str, Any]) -> str:
    lines = [
        "# WF78 SQL-First Recommendation Archive Apply",
        "",
        f"- Status: `{payload['status']}`",
        f"- Apply requested: `{payload['summary']['apply_requested']}`",
        f"- Moved: `{payload['summary']['moved_count']}`",
        f"- Already archived: `{payload['summary']['already_archived_count']}`",
        f"- Blocked: `{payload['summary']['blocked_count']}`",
        f"- Approval reference: `{payload['summary'].get('approval_reference') or ''}`",
        "",
        "## Rows",
    ]
    for row in payload["rows"]:
        lines.append(f"- `{row['source_path']}` -> `{row['archive_path']}`: `{row['action']}`")
    lines.append("")
    return "\n".join(lines)


def build_payload(apply: bool, approval_reference: str | None) -> dict[str, Any]:
    inventory = read_json(INVENTORY)
    inventory_ready, inventory_errors = inventory_ok(inventory)
    approval_ok = bool(approval_reference and approval_reference.strip())
    rows = build_rows(apply and inventory_ready and approval_ok)
    blocked_rows = [row for row in rows if row["action"] == "blocked" or row["destination_hash_conflict"]]
    moved_rows = [row for row in rows if row["action"] == "moved"]
    already_rows = [row for row in rows if row["action"] == "already_archived"]
    errors = list(inventory_errors)
    if apply and not approval_ok:
        errors.append("approval_reference_required_for_apply")
    if blocked_rows:
        errors.append("blocked_archive_rows_present")
    status = "ok"
    if errors:
        status = "blocked"
    elif apply:
        status = "applied"
    else:
        status = "owner_approved_archive_ready" if approval_ok else "ready_for_owner_approval_reference"
    return {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": status,
        "authority_boundary": AUTHORITY_BOUNDARY,
        "archive_root": rel(ARCHIVE_ROOT),
        "summary": {
            "apply_requested": apply,
            "apply_executed": bool(apply and not errors),
            "approval_reference": approval_reference,
            "candidate_count": len(rows),
            "moved_count": len(moved_rows),
            "already_archived_count": len(already_rows),
            "blocked_count": len(blocked_rows),
            "delete_count": 0,
            "overwrite_count": 0,
            "next_safe_action": "Rerun routing/release proof; do not delete archived surfaces.",
        },
        "rows": rows,
        "validation": {"status": "ok" if not errors else "error", "errors": errors},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--approval-reference")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--write-md", action="store_true")
    parser.add_argument("--validate", action="store_true")
    args = parser.parse_args()
    payload = build_payload(args.apply, args.approval_reference)
    if args.write:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(payload, indent=2, sort_keys=False) + "\n", encoding="utf-8")
    if args.write_md:
        OUT_MD.write_text(render_md(payload), encoding="utf-8")
    print(
        "status={status} apply={apply} moved={moved} already_archived={already} blocked={blocked} out={out}".format(
            status=payload["status"],
            apply=payload["summary"]["apply_requested"],
            moved=payload["summary"]["moved_count"],
            already=payload["summary"]["already_archived_count"],
            blocked=payload["summary"]["blocked_count"],
            out=rel(OUT),
        )
    )
    if args.validate and payload["validation"]["status"] != "ok":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
