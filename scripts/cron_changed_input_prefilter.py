#!/usr/bin/env python3
"""Report-only changed-input gate for cron pre-dispatch wrappers."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
DEFAULT_STATE = TMP / "cron-predispatch-prefilter-state.json"
DEFAULT_PROOF = TMP / "cron-predispatch-prefilter-smoke.json"
SCHEMA = "veritas.cron_changed_input_prefilter.v1"

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "cron_schedule_mutation": False,
    "cron_runtime_mutation": False,
    "cron_config_mutation": False,
    "finance_canon_mutation": False,
    "portfolio_or_capital_mutation": False,
    "paper_or_live_execution": False,
    "owner_approval_inference": False,
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def atomic_write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp_path.replace(path)


def path_record(source: Path) -> dict[str, Any]:
    resolved = source if source.is_absolute() else (ROOT / source)
    display = str(source)
    if not resolved.exists():
        return {
            "path": display,
            "resolved_path": str(resolved),
            "exists": False,
            "kind": "missing",
            "sha256": None,
            "size_bytes": None,
        }
    if resolved.is_file():
        digest = hashlib.sha256()
        size = 0
        with resolved.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                size += len(chunk)
                digest.update(chunk)
        return {
            "path": display,
            "resolved_path": str(resolved),
            "exists": True,
            "kind": "file",
            "sha256": digest.hexdigest(),
            "size_bytes": size,
        }
    if resolved.is_dir():
        entries: list[dict[str, Any]] = []
        for child in sorted(p for p in resolved.rglob("*") if p.is_file()):
            rel_child = child.relative_to(resolved)
            child_digest = hashlib.sha256()
            child_size = 0
            with child.open("rb") as handle:
                for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                    child_size += len(chunk)
                    child_digest.update(chunk)
            entries.append(
                {
                    "relative_path": str(rel_child).replace("\\", "/"),
                    "sha256": child_digest.hexdigest(),
                    "size_bytes": child_size,
                }
            )
        digest = hashlib.sha256(json.dumps(entries, sort_keys=True).encode("utf-8")).hexdigest()
        return {
            "path": display,
            "resolved_path": str(resolved),
            "exists": True,
            "kind": "directory",
            "sha256": digest,
            "size_bytes": sum(int(item["size_bytes"]) for item in entries),
            "file_count": len(entries),
        }
    return {
        "path": display,
        "resolved_path": str(resolved),
        "exists": True,
        "kind": "unsupported",
        "sha256": None,
        "size_bytes": None,
    }


def source_signature(records: list[dict[str, Any]]) -> str:
    material = json.dumps(records, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(material).hexdigest()


def build_prefilter(
    *,
    job_name: str,
    sources: list[Path],
    state_path: Path,
    update_state: bool,
) -> tuple[dict[str, Any], dict[str, Any]]:
    state = load_json(state_path, {"schema": SCHEMA, "jobs": {}})
    if not isinstance(state, dict):
        state = {"schema": SCHEMA, "jobs": {}}
    state.setdefault("schema", SCHEMA)
    jobs = state.setdefault("jobs", {})
    if not isinstance(jobs, dict):
        state["jobs"] = jobs = {}

    records = [path_record(source) for source in sources]
    signature = source_signature(records)
    job_state = jobs.get(job_name, {})
    last_success_signature = job_state.get("last_success_signature")
    missing_sources = [record["path"] for record in records if not record.get("exists")]
    unsupported_sources = [record["path"] for record in records if record.get("kind") == "unsupported"]
    changed = signature != last_success_signature
    decision = "run_required" if changed else "skip_unchanged"

    warnings: list[str] = []
    errors: list[str] = []
    if not job_name.strip():
        errors.append("job_name_required")
    if not sources:
        errors.append("at_least_one_source_required")
    if missing_sources:
        warnings.append("missing_sources_force_run_required")
        decision = "run_required"
    if unsupported_sources:
        warnings.append("unsupported_sources_force_run_required")
        decision = "run_required"
    status = "blocked" if errors else ("warning" if warnings else "ok")

    if update_state and status != "blocked":
        jobs[job_name] = {
            "last_success_signature": signature,
            "updated_at_utc": utc_now(),
            "source_count": len(records),
            "missing_source_count": len(missing_sources),
        }

    proof = {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": status,
        "decision": decision,
        "job_name": job_name,
        "state_path": str(state_path),
        "source_signature": signature,
        "last_success_signature": last_success_signature,
        "changed": changed,
        "source_count": len(records),
        "missing_source_count": len(missing_sources),
        "unsupported_source_count": len(unsupported_sources),
        "missing_sources": missing_sources,
        "unsupported_sources": unsupported_sources,
        "warnings": warnings,
        "errors": errors,
        "sources": records,
        "state_updated": bool(update_state and status != "blocked"),
        "authority_boundary": AUTHORITY_BOUNDARY,
    }
    return proof, state


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--job-name", required=True, help="Stable cron or wrapper job name.")
    parser.add_argument("--source", action="append", default=[], help="File or directory input to hash.")
    parser.add_argument("--state", type=Path, default=DEFAULT_STATE, help="State JSON path.")
    parser.add_argument("--proof", type=Path, default=DEFAULT_PROOF, help="Proof JSON path.")
    parser.add_argument("--update-state", action="store_true", help="Record the current signature as last successful.")
    parser.add_argument("--write", action="store_true", help="Write proof and optional state artifacts.")
    parser.add_argument("--validate", action="store_true", help="Exit non-zero only for blocked validation.")
    parser.add_argument("--pretty", action="store_true", help="Print formatted JSON.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    proof, state = build_prefilter(
        job_name=args.job_name,
        sources=[Path(item) for item in args.source],
        state_path=args.state,
        update_state=args.update_state,
    )
    if args.write:
        atomic_write_json(args.proof, proof)
        if proof["state_updated"]:
            atomic_write_json(args.state, state)
    if args.pretty or not args.write:
        print(json.dumps(proof, indent=2, sort_keys=True))
    if args.validate and proof["status"] == "blocked":
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
