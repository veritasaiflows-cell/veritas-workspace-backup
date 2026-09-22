#!/usr/bin/env python3
"""Policy-compliant bounded auto-archive helper.

Consumes `tmp/archive-suggestions.json` and can move only suggestions explicitly
marked as apply-eligible. This helper is deliberately stricter than the current
archive suggester, so initial runs should validate the pipeline without moving
anything until a future suggester marks safe generated residue as eligible.
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
DEFAULT_INPUT = ROOT / "tmp" / "archive-suggestions.json"
TMP_REPORT = ROOT / "tmp" / "bounded-auto-archive-last-report.json"
TMP_MD = ROOT / "tmp" / "bounded-auto-archive-last-report.md"
LOG_ROOT = ROOT / "09. Archive" / "Archive Logs"
GENERATED_ROOT = ROOT / "09. Archive" / "Auto Archive - Generated Residue"
DEPRECATED_ROOT = ROOT / "09. Archive" / "Deprecated Files - Auto Archived"

PROTECTED_PREFIXES = (
    "01. Dashboards/",
    "02. Markets/",
    "03. Portfolio/",
    "04. Research/",
    "05. Intelligence/",
    "06. Playbooks/",
    "07. Risk/",
    "08. Audits/",
    "09. Archive/",
    "data/",
    "memory/",
    "scripts/",
    "skills/",
)
PROTECTED_BASENAMES = {"SOUL.md", "AGENTS.md", "USER.md", "TOOLS.md", "MEMORY.md", "HEARTBEAT.md"}
ALLOWED_KINDS = {"generated_residue", "deprecated_scratch", "duplicate_generated_output", "obsolete_proof_residue", "tmp_markdown_historical_sidecar_with_json", "tmp_markdown_script_output_sidecar_with_json"}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def sha256_file(path: Path) -> str | None:
    if not path.is_file():
        return None
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def is_protected(rel_path: str) -> bool:
    if rel_path in PROTECTED_BASENAMES or Path(rel_path).name in PROTECTED_BASENAMES:
        return True
    return rel_path.startswith(PROTECTED_PREFIXES)


def destination_for(item: dict[str, Any], source: Path) -> Path:
    proposed = item.get("proposed_destination")
    if proposed:
        dest = ROOT / str(proposed)
        if dest.suffix == "":
            dest = dest / source.name
    else:
        dest = GENERATED_ROOT / source.name
    try:
        dest.relative_to(GENERATED_ROOT)
        return dest
    except ValueError:
        pass
    try:
        dest.relative_to(DEPRECATED_ROOT)
        return dest
    except ValueError:
        pass
    raise ValueError("destination is outside approved archive roots")


def manifest_integrity_error(item: dict[str, Any], source: Path) -> str | None:
    """Require the frozen source identity before a mover can act."""
    expected_hash = item.get("sha256")
    expected_bytes = item.get("bytes")
    if not isinstance(expected_hash, str) or len(expected_hash) != 64 or any(char not in "0123456789abcdefABCDEF" for char in expected_hash):
        return "manifest sha256 must be a 64-character hexadecimal digest"
    if not isinstance(expected_bytes, int) or isinstance(expected_bytes, bool) or expected_bytes < 0:
        return "manifest bytes must be a non-negative integer"
    actual_bytes = source.stat().st_size
    if actual_bytes != expected_bytes:
        return f"manifest byte count mismatch: expected {expected_bytes}, found {actual_bytes}"
    actual_hash = sha256_file(source)
    if actual_hash != expected_hash.lower():
        return "manifest sha256 mismatch"
    return None


def evaluate_item(item: dict[str, Any]) -> tuple[str, str | None]:
    path_value = str(item.get("path") or "").strip().replace("\\", "/")
    if not path_value or path_value.endswith("/"):
        return "blocked", "missing path or directory archive not supported by this helper"
    if ".." in Path(path_value).parts or Path(path_value).is_absolute():
        return "blocked", "path must be workspace-relative without parent traversal"
    if is_protected(path_value):
        return "blocked", "protected path prefix or basename"
    if item.get("apply_allowed") is not True:
        return "skipped", "suggestion is not marked apply_allowed=true"
    if item.get("owner_approval_required") is True:
        return "blocked", "suggestion still requires owner approval"
    if item.get("reference_count") not in (0, None):
        if not (
            item.get("blocking_reference_count") == 0
            and item.get("kind") in {"tmp_markdown_historical_sidecar_with_json", "tmp_markdown_script_output_sidecar_with_json"}
            and (item.get("historical_reference_count", 0) + item.get("script_output_reference_count", 0)) >= item.get("reference_count", 0)
        ):
            return "blocked", "inbound references present"
    if item.get("kind") not in ALLOWED_KINDS:
        return "blocked", f"kind {item.get('kind')} is not in auto-archive allowlist"
    source = ROOT / path_value
    if not source.exists() or not source.is_file():
        return "blocked", "source missing or not a file"
    integrity_error = manifest_integrity_error(item, source)
    if integrity_error:
        return "blocked", integrity_error
    try:
        destination = destination_for(item, source)
    except ValueError as exc:
        return "blocked", str(exc)
    if destination.exists():
        return "blocked", "declared destination already exists; manifest must be regenerated"
    return "eligible", None


def build_report(input_path: Path, apply: bool) -> dict[str, Any]:
    data = json.loads(input_path.read_text(encoding="utf-8")) if input_path.exists() else {"suggestions": []}
    moved: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    blocked: list[dict[str, Any]] = []
    for item in data.get("suggestions", []):
        status, reason = evaluate_item(item)
        row = {"path": item.get("path"), "kind": item.get("kind"), "status": status, "reason": reason}
        if status == "eligible" and apply:
            source = ROOT / str(item["path"]).replace("\\", "/")
            dest = destination_for(item, source)
            # Recheck immediately before moving: preflight cannot protect against
            # source drift between validation and the filesystem mutation.
            integrity_error = manifest_integrity_error(item, source)
            if integrity_error:
                row.update({"status": "blocked", "reason": integrity_error})
                blocked.append(row)
                continue
            if dest.exists():
                row.update({"status": "blocked", "reason": "declared destination already exists; manifest must be regenerated"})
                blocked.append(row)
                continue
            dest.parent.mkdir(parents=True, exist_ok=True)
            before = sha256_file(source)
            shutil.move(str(source), str(dest))
            after = sha256_file(dest)
            if before != str(item["sha256"]).lower() or after != before or dest.stat().st_size != item["bytes"]:
                raise RuntimeError("archive move integrity failure; source or destination diverged from manifest")
            row.update({"status": "moved", "destination": rel(dest), "sha256_manifest": item["sha256"].lower(), "bytes_manifest": item["bytes"], "sha256_before": before, "sha256_after": after})
            moved.append(row)
        elif status == "eligible":
            row["status"] = "dry_run_eligible"
            skipped.append(row)
        elif status == "skipped":
            skipped.append(row)
        else:
            blocked.append(row)
    report = {
        "status": "ok" if not blocked else "review_required",
        "generated_at_utc": utc_now(),
        "script": "scripts/bounded_auto_archive.py",
        "mode": "apply" if apply else "dry_run",
        "input": rel(input_path) if input_path.exists() and input_path.is_relative_to(ROOT) else str(input_path),
        "moves_performed": bool(moved),
        "deletes_performed": False,
        "counts": {"moved": len(moved), "skipped": len(skipped), "blocked": len(blocked)},
        "moved": moved,
        "skipped": skipped,
        "blocked": blocked,
        "authority_boundary": "archive-only helper; no deletes; protected paths blocked; explicit apply_allowed suggestions can move only with zero references, the WF72 adjacent-JSON historical-reference-only exception, or the WF72 adjacent-JSON script-output-constant exception",
        "manifest_binding": "apply requires a 64-character SHA-256 and exact byte count; both are rechecked immediately before every move and destination collisions fail closed",
    }
    return report


def write_outputs(report: dict[str, Any], write_md: bool = False) -> None:
    TMP_REPORT.parent.mkdir(parents=True, exist_ok=True)
    TMP_REPORT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    if not write_md:
        if report["mode"] == "apply":
            LOG_ROOT.mkdir(parents=True, exist_ok=True)
            stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            (LOG_ROOT / f"bounded-auto-archive-{stamp}.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        return
    lines = [
        "# Bounded Auto-Archive Report",
        "",
        f"Generated: `{report['generated_at_utc']}`",
        f"Mode: `{report['mode']}`",
        f"Status: `{report['status']}`",
        f"Moves performed: `{report['moves_performed']}`",
        f"Deletes performed: `{report['deletes_performed']}`",
        f"Counts: `{report['counts']}`",
        "",
        "## Boundary",
        "",
        report["authority_boundary"],
        "",
        "## Moved",
        "",
    ]
    lines.extend([f"- `{row['path']}` -> `{row.get('destination')}`" for row in report["moved"]] or ["- None"])
    lines.extend(["", "## Blocked", ""])
    lines.extend([f"- `{row['path']}` — {row.get('reason')}" for row in report["blocked"]] or ["- None"])
    lines.extend(["", "## Skipped", ""])
    lines.extend([f"- `{row['path']}` — {row.get('reason')}" for row in report["skipped"][:50]] or ["- None"])
    TMP_MD.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    if report["mode"] == "apply":
        LOG_ROOT.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        (LOG_ROOT / f"bounded-auto-archive-{stamp}.json").write_text(json.dumps(report, indent=2), encoding="utf-8")


def validate_last() -> int:
    report = json.loads(TMP_REPORT.read_text(encoding="utf-8"))
    bad = []
    if report.get("deletes_performed") is not False:
        bad.append("deletes_performed must be false")
    for row in report.get("moved", []):
        dest = str(row.get("destination") or "")
        if not (dest.startswith("09. Archive/Auto Archive - Generated Residue/") or dest.startswith("09. Archive/Deprecated Files - Auto Archived/")):
            bad.append(f"bad destination {dest}")
        if row.get("sha256_before") != row.get("sha256_after"):
            bad.append(f"hash mismatch for {row.get('path')}")
        if row.get("sha256_manifest") != row.get("sha256_before"):
            bad.append(f"manifest hash mismatch for {row.get('path')}")
    print(json.dumps({"status": "ok" if not bad else "critical", "errors": bad}, indent=2))
    return 0 if not bad else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Bounded auto-archive helper.")
    parser.add_argument("--input", default=str(DEFAULT_INPUT))
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--write-md", action="store_true", help="Also write legacy human-readable 09. Archive/Auto Archive - Generated Residue/WF72 JSON First Legacy Markdown/bounded-auto-archive-last-report.md")
    parser.add_argument("--validate-last-report", action="store_true")
    args = parser.parse_args()
    if args.validate_last_report:
        return validate_last()
    input_path = Path(args.input)
    if not input_path.is_absolute():
        input_path = ROOT / input_path
    report = build_report(input_path, apply=args.apply)
    write_outputs(report, write_md=args.write_md)
    print(json.dumps(report, indent=2))
    return 0 if report["status"] in {"ok", "review_required"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
