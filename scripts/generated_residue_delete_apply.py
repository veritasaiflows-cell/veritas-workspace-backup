#!/usr/bin/env python3
"""Manifest-bound, fail-closed permanent delete for the 17-file generated-residue pilot.

Two modes:

* ``build``  - after the approved retention window, re-hash every archived pilot file,
  re-run the exact-basename reference scan, and freeze a delete manifest valid for 24h.
  Never deletes.
* ``apply``  - without ``--apply`` it is a read-only preflight. With ``--apply`` it
  deletes only when the caller supplies the manifest file's exact SHA-256, an owner
  approval reference, and every row re-verifies (path, bytes, hash, zero references)
  immediately before deletion. Any preflight failure deletes nothing.

Scope is fixed to the frozen pilot list named by the retention approval; no other
archive family can pass the gates.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE_REL = "08. Audits/Generated Residue Pilot Evidence - 2026-09-08"
APPROVAL_NAME = "generated-residue-17-retention-approval-20260908.json"
FROZEN_NAME = "archive-pilot-input.json"
ARCHIVE_ROOT_REL = "09. Archive/Auto Archive - Generated Residue/2026-09-08/cleanup-pilot"
REFERENCE_SCAN_DIRS = ("scripts", "state", "skills")
REFERENCE_SKIP_SUFFIXES = {".sqlite", ".db", ".sqlite-wal", ".sqlite-shm", ".zip", ".exe", ".pyc", ".png", ".jpg"}
REFERENCE_MAX_BYTES = 5 * 1024 * 1024
MANIFEST_SCHEMA = "veritas.generated_residue_delete_manifest.v1"
RECEIPT_SCHEMA = "veritas.generated_residue_delete_receipt.v1"
MANIFEST_TTL = timedelta(hours=24)

AUTHORITY_BOUNDARY = {
    "scope": "17-file 2026-09-08 generated-residue pilot only",
    "build_deletes": False,
    "apply_requires_apply_flag": True,
    "apply_requires_exact_manifest_sha256": True,
    "apply_requires_owner_approval_reference": True,
    "other_archive_family_covered": False,
    "config_auth_channel_runtime_mutation_allowed": False,
    "finance_canon_mutation_allowed": False,
}


class GateError(Exception):
    """A fail-closed gate refused to continue."""


def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def iso(ts: datetime) -> str:
    return ts.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def parse_iso(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json_new(path: Path, obj: dict[str, Any]) -> None:
    """Write once; refuse to overwrite evidence."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(obj, handle, indent=2, ensure_ascii=False)
        handle.write("\n")


def load_scope(root: Path) -> dict[str, Any]:
    """Load the retention approval and frozen list from tracked evidence and cross-check them."""
    evidence = root / EVIDENCE_REL
    approval_path = evidence / APPROVAL_NAME
    frozen_path = evidence / FROZEN_NAME
    approval = load_json(approval_path)
    scope = approval["scope"]
    frozen_sha = sha256_file(frozen_path)
    if frozen_sha != scope["frozen_manifest_sha256"]:
        raise GateError(f"frozen list sha256 {frozen_sha} != approved {scope['frozen_manifest_sha256']}")
    rows = load_json(frozen_path)["suggestions"]
    if len(rows) != scope["row_count"] or sum(int(r["bytes"]) for r in rows) != scope["total_bytes"]:
        raise GateError("frozen list row count or total bytes differ from the approval scope")
    if approval["authority_boundary"].get("other_archive_family_covered"):
        raise GateError("approval unexpectedly covers other archive families")
    return {
        "approval": approval,
        "approval_sha256": sha256_file(approval_path),
        "frozen_sha256": frozen_sha,
        "rows": rows,
        "eligible_at": parse_iso(approval["retention_rule"]["eligible_at_utc"]),
    }


def archive_path_for(root: Path, row: dict[str, Any]) -> Path:
    if row["proposed_destination"].rstrip("/") != ARCHIVE_ROOT_REL:
        raise GateError(f"{row['path']}: destination outside the pilot archive root")
    return root / ARCHIVE_ROOT_REL / Path(row["path"]).name


def reference_hits(root: Path, basenames: list[str]) -> dict[str, list[str]]:
    """Exact-basename search across live code/state/skills (archive and evidence excluded)."""
    patterns = {name: re.compile(r"(?<![\w.\-])" + re.escape(name) + r"(?![\w.\-])") for name in basenames}
    hits: dict[str, list[str]] = {name: [] for name in basenames}
    for top in REFERENCE_SCAN_DIRS:
        base = root / top
        if not base.is_dir():
            continue
        for path in base.rglob("*"):
            if not path.is_file() or path.suffix.lower() in REFERENCE_SKIP_SUFFIXES:
                continue
            if path.name.startswith("generated_residue_delete_apply") or path.name.startswith("test_generated_residue_delete_apply"):
                continue
            try:
                if path.stat().st_size > REFERENCE_MAX_BYTES:
                    continue
                text = path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            for name, pattern in patterns.items():
                if pattern.search(text):
                    hits[name].append(path.relative_to(root).as_posix())
    return hits


def verify_row(root: Path, archive: Path, expected_sha: str, expected_bytes: int) -> str:
    """Return '' when the archived file is exactly as frozen, else the failure reason."""
    archive_root = (root / ARCHIVE_ROOT_REL).resolve()
    if archive.is_symlink():
        return "archive path is a symlink"
    if not archive.is_file():
        return "archive file missing or not a regular file"
    if archive.resolve().parent != archive_root:
        return "archive path resolves outside the pilot archive root"
    size = archive.stat().st_size
    if size != expected_bytes:
        return f"bytes {size} != {expected_bytes}"
    actual = sha256_file(archive)
    if actual != expected_sha:
        return f"sha256 {actual} != {expected_sha}"
    return ""


def build_manifest(root: Path, now: datetime) -> dict[str, Any]:
    scope = load_scope(root)
    if now < scope["eligible_at"]:
        raise GateError(f"retention not elapsed: eligible at {iso(scope['eligible_at'])}, now {iso(now)}")
    rows = scope["rows"]
    hits = reference_hits(root, [Path(r["path"]).name for r in rows])
    out_rows, failures = [], []
    for row in rows:
        archive = archive_path_for(root, row)
        reason = verify_row(root, archive, row["sha256"], int(row["bytes"]))
        refs = hits[Path(row["path"]).name]
        if refs:
            reason = reason or f"live references: {refs}"
        if reason:
            failures.append({"path": row["path"], "reason": reason})
        out_rows.append({
            "archive_path": archive.relative_to(root).as_posix(),
            "original_path": row["path"],
            "sha256": row["sha256"],
            "bytes": int(row["bytes"]),
            "live_reference_count": len(refs),
        })
    if failures:
        raise GateError(f"build blocked: {failures}")
    return {
        "schema": MANIFEST_SCHEMA,
        "status": "frozen_awaiting_exact_owner_delete_approval",
        "generated_at_utc": iso(now),
        "expires_at_utc": iso(now + MANIFEST_TTL),
        "retention_approval_sha256": scope["approval_sha256"],
        "frozen_list_sha256": scope["frozen_sha256"],
        "eligible_at_utc": iso(scope["eligible_at"]),
        "row_count": len(out_rows),
        "total_bytes": sum(r["bytes"] for r in out_rows),
        "reference_scan": {"dirs": list(REFERENCE_SCAN_DIRS), "method": "exact basename, archive and evidence excluded"},
        "rows": out_rows,
        "authority_boundary": {**AUTHORITY_BOUNDARY, "permanent_deletion_authorized": False},
    }


def preflight(root: Path, manifest_path: Path, approved_sha256: str, now: datetime) -> dict[str, Any]:
    """Every gate that must pass before the first delete. Raises GateError on any failure."""
    actual = sha256_file(manifest_path)
    if actual != approved_sha256.lower():
        raise GateError(f"manifest sha256 {actual} != approved {approved_sha256}")
    manifest = load_json(manifest_path)
    if manifest.get("schema") != MANIFEST_SCHEMA:
        raise GateError("unexpected manifest schema")
    scope = load_scope(root)
    if manifest["retention_approval_sha256"] != scope["approval_sha256"] or manifest["frozen_list_sha256"] != scope["frozen_sha256"]:
        raise GateError("manifest is not bound to the current retention approval and frozen list")
    if now < scope["eligible_at"]:
        raise GateError("retention not elapsed")
    if now > parse_iso(manifest["expires_at_utc"]) or now < parse_iso(manifest["generated_at_utc"]):
        raise GateError(f"manifest outside its validity window (expires {manifest['expires_at_utc']})")
    frozen = {(r["path"], r["sha256"], int(r["bytes"])) for r in scope["rows"]}
    listed = {(r["original_path"], r["sha256"], int(r["bytes"])) for r in manifest["rows"]}
    if listed != frozen or len(manifest["rows"]) != len(scope["rows"]):
        raise GateError("manifest rows differ from the approved frozen list")
    hits = reference_hits(root, [Path(r["original_path"]).name for r in manifest["rows"]])
    failures = []
    for row in manifest["rows"]:
        expected = archive_path_for(root, {"path": row["original_path"], "proposed_destination": ARCHIVE_ROOT_REL})
        if row["archive_path"] != expected.relative_to(root).as_posix():
            failures.append({"path": row["archive_path"], "reason": "archive path does not match the frozen destination"})
            continue
        reason = verify_row(root, expected, row["sha256"], row["bytes"])
        refs = hits[Path(row["original_path"]).name]
        if refs:
            reason = reason or f"live references: {refs}"
        if reason:
            failures.append({"path": row["archive_path"], "reason": reason})
    if failures:
        raise GateError(f"preflight blocked: {failures}")
    return manifest


def apply_manifest(root: Path, manifest_path: Path, approved_sha256: str, approval_reference: str,
                   apply: bool, now: datetime) -> dict[str, Any]:
    receipt: dict[str, Any] = {
        "schema": RECEIPT_SCHEMA,
        "mode": "apply" if apply else "preflight_only",
        "checked_at_utc": iso(now),
        "manifest_path": manifest_path.relative_to(root).as_posix() if manifest_path.is_relative_to(root) else str(manifest_path),
        "approved_manifest_sha256": approved_sha256,
        "approval_reference": approval_reference,
        "deleted": [],
        "authority_boundary": AUTHORITY_BOUNDARY,
    }
    if apply and not approval_reference.strip():
        receipt.update(status="blocked", reason="owner approval reference is required with --apply")
        return receipt
    try:
        manifest = preflight(root, manifest_path, approved_sha256, now)
    except (GateError, OSError, KeyError, ValueError) as exc:
        receipt.update(status="blocked", reason=str(exc))
        return receipt
    receipt["row_count"] = manifest["row_count"]
    receipt["total_bytes"] = manifest["total_bytes"]
    if not apply:
        receipt["status"] = "preflight_ok_nothing_deleted"
        return receipt
    for row in manifest["rows"]:
        target = root / row["archive_path"]
        reason = verify_row(root, target, row["sha256"], row["bytes"])
        if reason:
            receipt.update(status="stopped_partial", reason=f"{row['archive_path']}: {reason}")
            return receipt
        target.unlink()
        if target.exists():
            receipt.update(status="stopped_partial", reason=f"{row['archive_path']}: still present after unlink")
            return receipt
        receipt["deleted"].append({"archive_path": row["archive_path"], "sha256": row["sha256"], "bytes": row["bytes"]})
    receipt["status"] = "deleted_all"
    receipt["deleted_bytes"] = sum(r["bytes"] for r in receipt["deleted"])
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("build", help="freeze a 24h delete manifest into the tracked evidence folder")
    ap = sub.add_parser("apply", help="preflight (default) or delete with --apply")
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--approved-sha256", required=True)
    ap.add_argument("--approval-reference", default="")
    ap.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    now = utc_now()
    evidence = ROOT / EVIDENCE_REL
    stamp = now.strftime("%Y%m%dT%H%M%SZ")
    if args.command == "build":
        try:
            manifest = build_manifest(ROOT, now)
        except (GateError, OSError, KeyError, ValueError) as exc:
            print(json.dumps({"status": "blocked", "reason": str(exc)}, indent=2))
            return 2
        path = evidence / f"generated-residue-delete-manifest-{stamp}.json"
        write_json_new(path, manifest)
        print(json.dumps({"status": manifest["status"], "manifest": path.relative_to(ROOT).as_posix(),
                          "manifest_sha256": sha256_file(path), "rows": manifest["row_count"],
                          "total_bytes": manifest["total_bytes"], "expires_at_utc": manifest["expires_at_utc"]}, indent=2))
        return 0
    manifest_path = Path(args.manifest)
    if not manifest_path.is_absolute():
        manifest_path = ROOT / manifest_path
    receipt = apply_manifest(ROOT, manifest_path, args.approved_sha256, args.approval_reference, args.apply, now)
    if args.apply:
        write_json_new(evidence / f"generated-residue-delete-receipt-{stamp}.json", receipt)
    print(json.dumps(receipt, indent=2))
    return 0 if receipt["status"] in {"preflight_ok_nothing_deleted", "deleted_all"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
