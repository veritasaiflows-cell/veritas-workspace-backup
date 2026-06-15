#!/usr/bin/env python3
"""Hash-chained implementation completion ledger.

Records completed implementation/PM proof jobs as local, tamper-evident JSONL
rows. This is proof metadata only: it does not approve capital deployment,
execute trades, mutate canon/portfolio state, import SQL, archive/delete, or
infer owner approval.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, load_json_artifact

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / "state"
TMP = ROOT / "tmp"
LEDGER = STATE / "implementation-completion-ledger.jsonl"
SNAPSHOT_DIRNAME = "implementation-completion-ledger-snapshots"
OUT = TMP / "implementation-completion-ledger-current.json"
SCHEMA = "veritas.implementation_completion_ledger.v1"
ENTRY_SCHEMA = "veritas.implementation_completion_ledger.entry.v1"

DEFAULT_PROOF_ARTIFACTS = [
    TMP / "pm-execution-loop.json",
    TMP / "pm-control-packet.json",
    TMP / "repeatable-work-closeout.json",
    TMP / "control-closeout-bundle.json",
    TMP / "changed-file-validator-router.json",
]

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "completion_proof_only": True,
    "canon_or_portfolio_mutation_allowed": False,
    "sql_canon_mutation_allowed": False,
    "sql_or_ticker_import_allowed": False,
    "archive_or_delete_allowed": False,
    "customer_or_external_delivery_allowed": False,
    "config_auth_runtime_mutation_allowed": False,
    "capital_deployment_allowed": False,
    "capital_deployment_approved": False,
    "trade_or_execution_allowed": False,
    "trade_or_execution_approved": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "money_movement_allowed": False,
    "owner_approval_inferred": False,
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str | None:
    try:
        h = hashlib.sha256()
        with path.open("rb") as fh:
            for chunk in iter(lambda: fh.read(1024 * 1024), b""):
                h.update(chunk)
        return h.hexdigest()
    except OSError:
        return None


def canonical_entry_hash(entry: dict[str, Any]) -> str:
    payload = {k: v for k, v in entry.items() if k != "entry_hash"}
    return sha256_text(stable_json(payload))


def run_git(*args: str) -> subprocess.CompletedProcess[str] | None:
    try:
        return subprocess.run(["git", *args], cwd=ROOT, text=True, capture_output=True, timeout=30)
    except Exception:
        return None


def git_snapshot() -> dict[str, Any]:
    head = run_git("rev-parse", "--short", "HEAD")
    status = run_git("status", "--short")
    status_lines = status.stdout.splitlines() if status and status.returncode == 0 else []
    return {
        "head_short": head.stdout.strip() if head and head.returncode == 0 else None,
        "dirty": bool(status_lines),
        "status_line_count": len(status_lines),
        "porcelain_sha256": sha256_text("\n".join(status_lines)) if status_lines else None,
    }


def artifact_record(path: Path) -> dict[str, Any]:
    exists = path.exists() and path.is_file()
    return {
        "path": rel(path),
        "exists": exists,
        "bytes": path.stat().st_size if exists else None,
        "sha256": sha256_file(path) if exists else None,
    }


def snapshot_source_report(source_path: Path, ledger_path: Path, source_hash: str | None) -> dict[str, Any] | None:
    if not source_hash or not source_path.exists() or not source_path.is_file():
        return None
    snapshot_dir = ledger_path.parent / SNAPSHOT_DIRNAME
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    target = snapshot_dir / f"{source_path.stem}-{source_hash[:16]}.json"
    if not target.exists():
        target.write_bytes(source_path.read_bytes())
    return artifact_record(target)


def source_artifact_paths(source: dict[str, Any], selected_job: dict[str, Any] | None = None) -> list[Path]:
    paths: list[Path] = []
    for item in as_list(source.get("source_artifacts")):
        if isinstance(item, str):
            paths.append(ROOT / item.replace("/", "\\"))
    if selected_job:
        for item in as_list(selected_job.get("target_files")):
            if isinstance(item, str):
                paths.append(ROOT / item.replace("/", "\\"))
    for path in DEFAULT_PROOF_ARTIFACTS:
        paths.append(path)
    deduped: list[Path] = []
    seen: set[str] = set()
    for path in paths:
        key = str(path.resolve() if path.exists() else path)
        if key not in seen:
            seen.add(key)
            deduped.append(path)
    return deduped


def command_result_digest(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in results:
        row = as_dict(row)
        command = row.get("command")
        out.append({
            "name": row.get("name"),
            "ok": row.get("ok"),
            "returncode": row.get("returncode"),
            "completed_at_utc": row.get("completed_at_utc"),
            "command_sha256": sha256_text(stable_json(command)),
        })
    return out


def changed_paths_snapshot() -> dict[str, Any]:
    data = as_dict(load_json_artifact(TMP / "changed-file-validator-router.json"))
    summary = as_dict(data.get("summary"))
    return {
        "artifact_path": rel(TMP / "changed-file-validator-router.json"),
        "artifact_sha256": sha256_file(TMP / "changed-file-validator-router.json"),
        "status": data.get("status"),
        "changed_path_count": summary.get("changed_path_count"),
        "recommendation_count": summary.get("recommendation_count"),
        "recommended_budget": summary.get("recommended_budget"),
        "validation_status": as_dict(data.get("validation")).get("status"),
    }


def load_entries(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    entries: list[dict[str, Any]] = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
        if not line.strip():
            continue
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError as exc:
            entries.append({"_decode_error": str(exc), "_line_no": line_no})
    return entries


def validate_entries(entries: list[dict[str, Any]]) -> dict[str, Any]:
    errors: list[str] = []
    previous: str | None = None
    for idx, entry in enumerate(entries, 1):
        if "_decode_error" in entry:
            errors.append(f"line_{entry.get('_line_no')}:json_decode_error")
            continue
        if entry.get("sequence") != idx:
            errors.append(f"sequence_mismatch:{idx}:{entry.get('sequence')}")
        if entry.get("previous_entry_hash") != previous:
            errors.append(f"previous_hash_mismatch:{idx}")
        expected = canonical_entry_hash(entry)
        if entry.get("entry_hash") != expected:
            errors.append(f"entry_hash_mismatch:{idx}")
        previous = entry.get("entry_hash")
    return {
        "status": "ok" if not errors else "blocked",
        "errors": errors,
        "entry_count": len(entries),
        "tip_entry_hash": previous,
    }


def selected_jobs_from_pm_execution(source: dict[str, Any]) -> list[dict[str, Any]]:
    selected = as_list(source.get("selected"))
    if selected:
        return [as_dict(row) for row in selected]
    return []


def selected_jobs_from_completion_source(source: dict[str, Any]) -> list[dict[str, Any]]:
    """Return explicit completed jobs from a manual/backfill source artifact."""
    jobs = as_list(source.get("completed_jobs"))
    if jobs:
        return [as_dict(row) for row in jobs]
    return []


def result_rows_for_job(source: dict[str, Any], job_id: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    proof = [as_dict(row) for row in as_list(source.get("proof_results")) if str(as_dict(row).get("name", "")).startswith(f"{job_id}:")]
    closeout = [as_dict(row) for row in as_list(source.get("closeout_results")) if str(as_dict(row).get("name", "")).startswith(f"{job_id}:")]
    return proof, closeout


def build_entries_from_source(
    *,
    source_path: Path,
    source: dict[str, Any],
    existing_entries: list[dict[str, Any]],
    ledger_path: Path,
    manual_job_id: str | None,
    manual_title: str | None,
    manual_summary: str | None,
    record: bool,
) -> list[dict[str, Any]]:
    prior = validate_entries(existing_entries)
    previous_hash = prior.get("tip_entry_hash") if prior.get("status") == "ok" else None
    sequence = len(existing_entries) + 1
    source_hash = sha256_file(source_path)
    source_snapshot = snapshot_source_report(source_path, ledger_path, source_hash) if record else None
    existing_pairs = {
        (as_dict(entry.get("job")).get("job_id"), as_dict(entry.get("source_report")).get("sha256"))
        for entry in existing_entries
        if isinstance(entry, dict)
    }
    source_validation = as_dict(source.get("validation"))
    source_summary = as_dict(source.get("summary"))
    is_pm_execution = source.get("schema") == "veritas.pm_execution_loop.v1"
    if is_pm_execution and (source.get("status") != "ok" or source.get("mode") != "execute"):
        jobs = []
    else:
        jobs = selected_jobs_from_pm_execution(source)
    if not jobs and source.get("status") == "ok":
        jobs = selected_jobs_from_completion_source(source)
    if not jobs:
        if is_pm_execution and not manual_job_id:
            return []
        jobs = [{
            "job_id": manual_job_id or source_path.stem,
            "title": manual_title or source.get("purpose") or source_path.stem,
            "implementation_class": source.get("schema"),
            "owner_surface": "manual_or_closeout_source",
        }]
    entries: list[dict[str, Any]] = []
    for job in jobs:
        job_id = str(job.get("job_id") or manual_job_id or source_path.stem)
        if (job_id, source_hash) in existing_pairs:
            continue
        proof_results, closeout_results = result_rows_for_job(source, job_id)
        entry: dict[str, Any] = {
            "schema": ENTRY_SCHEMA,
            "sequence": sequence,
            "previous_entry_hash": previous_hash,
            "recorded_at_utc": utc_now(),
            "completed_at_utc": job.get("completed_at_utc") or source.get("completed_at_utc") or source.get("generated_at_utc") or utc_now(),
            "job": {
                "job_id": job_id,
                "title": job.get("title") or manual_title,
                "implementation_class": job.get("implementation_class"),
                "owner_surface": job.get("owner_surface"),
                "collision_group": job.get("collision_group"),
                "summary": job.get("summary") or manual_summary or source_summary.get("next_safe_action"),
            },
            "source_report": {
                "path": rel(source_path),
                "schema": source.get("schema"),
                "status": source.get("status"),
                "mode": source.get("mode"),
                "sha256": source_hash,
                "snapshot": source_snapshot,
            },
            "proof": {
                "proof_results": command_result_digest(proof_results),
                "closeout_results": command_result_digest(closeout_results),
                "proof_failed": source_summary.get("proof_failed"),
                "closeout_failed": source_summary.get("closeout_failed"),
                "validation_status": source_validation.get("status"),
                "validation_errors": source_validation.get("errors") or [],
                "artifact_hashes": [artifact_record(path) for path in source_artifact_paths(source, job)],
                "changed_paths_snapshot": changed_paths_snapshot(),
            },
            "git": git_snapshot(),
            "authority_boundary": AUTHORITY_BOUNDARY,
        }
        entry["entry_hash"] = canonical_entry_hash(entry)
        entries.append(entry)
        previous_hash = entry["entry_hash"]
        sequence += 1
    return entries


def append_entries(path: Path, entries: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as fh:
        for entry in entries:
            fh.write(stable_json(entry) + "\n")


def build_report(args: argparse.Namespace) -> dict[str, Any]:
    source_path = (ROOT / args.source).resolve() if not args.source.is_absolute() else args.source
    source = as_dict(load_json_artifact(source_path))
    ledger_path = (ROOT / args.ledger).resolve() if not args.ledger.is_absolute() else args.ledger
    existing = load_entries(ledger_path)
    before_validation = validate_entries(existing)
    new_entries: list[dict[str, Any]] = []
    errors: list[str] = []
    if not source:
        errors.append(f"source_unreadable:{rel(source_path)}")
    if before_validation["status"] != "ok":
        errors.extend(before_validation["errors"])
    if source and not errors and args.record:
        new_entries = build_entries_from_source(
            source_path=source_path,
            source=source,
            existing_entries=existing,
            ledger_path=ledger_path,
            manual_job_id=args.job_id,
            manual_title=args.title,
            manual_summary=args.summary,
            record=bool(args.record),
        )
        if new_entries:
            append_entries(ledger_path, new_entries)
            existing = load_entries(ledger_path)
    after_validation = validate_entries(existing)
    if after_validation["status"] != "ok":
        errors.extend(after_validation["errors"])
    status = "ok" if not errors else "blocked"
    return {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": status,
        "purpose": "Hash-chained local implementation completion ledger.",
        "authority_boundary": AUTHORITY_BOUNDARY,
        "ledger_path": rel(ledger_path),
        "source_path": rel(source_path),
        "recorded": bool(args.record and new_entries and status == "ok"),
        "summary": {
            "existing_entry_count_before": before_validation["entry_count"],
            "new_entry_count": len(new_entries),
            "entry_count_after": after_validation["entry_count"],
            "tip_entry_hash": after_validation.get("tip_entry_hash") or (new_entries[-1]["entry_hash"] if new_entries else None),
            "source_sha256": sha256_file(source_path),
            "next_safe_action": "Use this ledger for future completed-job reconstruction; keep PM/closeout artifacts as detailed proof.",
        },
        "new_entries": new_entries,
        "validation": {
            "status": status,
            "errors": errors,
            "warnings": [],
        },
        "stop_lines": [
            "Ledger is local tamper-evident proof metadata, not an external notarization or signed audit.",
            "No canon/portfolio mutation, SQL import, archive/delete, config/auth/runtime change, customer output, capital deployment, trade/paper/live/account action, or owner approval inference.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Record or validate the implementation completion ledger.")
    parser.add_argument("--source", type=Path, default=TMP / "pm-execution-loop.json", help="Source completion report to hash into the ledger.")
    parser.add_argument("--ledger", type=Path, default=LEDGER, help="JSONL ledger path.")
    parser.add_argument("--out", type=Path, default=OUT, help="Current report path.")
    parser.add_argument("--job-id", default=None, help="Manual job id when the source is not a PM execution report.")
    parser.add_argument("--title", default=None, help="Manual title when the source is not a PM execution report.")
    parser.add_argument("--summary", default=None, help="Manual summary to store in the job row.")
    parser.add_argument("--record", action="store_true", help="Append new entry/entries to the ledger.")
    parser.add_argument("--write", action="store_true", help="Write current report artifact.")
    parser.add_argument("--validate", action="store_true", help="Return non-zero when ledger validation is blocked.")
    args = parser.parse_args()

    report = build_report(args)
    if args.write:
        atomic_write_json(args.out, report)
        print(
            f"wrote {rel(args.out)} status={report['status']} recorded={report['recorded']} "
            f"entries={report['summary']['entry_count_after']} new={report['summary']['new_entry_count']}"
        )
    else:
        print(json.dumps(report["summary"], indent=2, default=str))
    if args.validate and report["validation"]["status"] != "ok":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
