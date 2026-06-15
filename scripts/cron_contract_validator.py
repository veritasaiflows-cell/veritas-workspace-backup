#!/usr/bin/env python3
"""Validate live cron jobs against intended local contract files."""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, load_json_artifact

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
DEFAULT_CONTRACT_DIR = ROOT / "state" / "cron-contracts"
DEFAULT_OUT = TMP / "cron-contract-validator.json"
SCHEMA = "veritas.cron_contract_validator.v1"

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "drift_detection_only": True,
    "cron_state_mutation_allowed": False,
    "cron_schedule_mutation_allowed": False,
    "runtime_config_mutation_allowed": False,
    "canon_or_portfolio_mutation_allowed": False,
    "customer_or_external_delivery_allowed": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "owner_approval_inferred": False,
}

DEFAULT_COMPARE_FIELDS = [
    "enabled",
    "description",
    "schedule",
    "failureAlert",
    "payload.message",
    "payload.model",
    "payload.thinking",
    "payload.timeoutSeconds",
    "payload.lightContext",
]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def openclaw_cmd() -> str:
    found = shutil.which("openclaw.cmd") or shutil.which("openclaw") or shutil.which("openclaw.ps1")
    if found:
        return found
    known = Path.home() / "AppData" / "Roaming" / "npm" / "openclaw.cmd"
    return str(known) if known.exists() else "openclaw.cmd"


def get_nested(obj: dict[str, Any], dotted: str) -> Any:
    current: Any = obj
    for part in dotted.split("."):
        if not isinstance(current, dict):
            return None
        current = current.get(part)
    return current


def normalize_cron_payload(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        jobs = payload.get("jobs")
        if isinstance(jobs, list):
            return [item for item in jobs if isinstance(item, dict)]
        if payload.get("id") or payload.get("name"):
            return [payload]
    return []


def load_live_jobs(live_file: Path | None = None) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if live_file:
        payload = load_json_artifact(live_file)
        return normalize_cron_payload(payload), {"source": rel(live_file), "ok": True}
    completed = subprocess.run(
        [openclaw_cmd(), "cron", "list", "--all", "--json", "--timeout", "30000"],
        cwd=ROOT,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=45,
        check=False,
    )
    meta = {
        "source": "openclaw cron list --all --json",
        "returncode": completed.returncode,
        "ok": completed.returncode == 0,
        "stderr_tail": (completed.stderr or "")[-2000:],
    }
    if completed.returncode != 0:
        return [], meta
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError:
        meta["ok"] = False
        meta["error"] = "cron_list_json_parse_failed"
        return [], meta
    return normalize_cron_payload(payload), meta


def iter_contract_paths(contract_dir: Path, explicit: list[Path] | None = None) -> list[Path]:
    if explicit:
        return [path if path.is_absolute() else ROOT / path for path in explicit]
    if not contract_dir.exists():
        return []
    return sorted(path for path in contract_dir.glob("*.json") if path.is_file())


def load_contracts(contract_dir: Path, explicit: list[Path] | None = None) -> tuple[list[dict[str, Any]], list[str]]:
    contracts: list[dict[str, Any]] = []
    warnings: list[str] = []
    for path in iter_contract_paths(contract_dir, explicit):
        payload = load_json_artifact(path)
        if not isinstance(payload, dict):
            warnings.append(f"invalid_contract_json:{rel(path)}")
            continue
        payload["_contract_path"] = rel(path)
        contracts.append(payload)
    return contracts, warnings


def contract_identity(contract: dict[str, Any]) -> tuple[str | None, str | None]:
    return (
        contract.get("job_id") or contract.get("id"),
        contract.get("name") or contract.get("job_name"),
    )


def find_live_job(contract: dict[str, Any], jobs: list[dict[str, Any]]) -> dict[str, Any] | None:
    job_id, name = contract_identity(contract)
    if job_id:
        for job in jobs:
            if str(job.get("id") or "") == str(job_id):
                return job
    if name:
        matches = [job for job in jobs if str(job.get("name") or "") == str(name)]
        if len(matches) == 1:
            return matches[0]
    return None


def expected_value(contract: dict[str, Any], field: str) -> Any:
    return get_nested(contract, field)


def compare_contract(contract: dict[str, Any], live_job: dict[str, Any] | None) -> dict[str, Any]:
    fields = [str(item) for item in as_list(contract.get("compare_fields"))] or DEFAULT_COMPARE_FIELDS
    if live_job is None:
        return {
            "contract_path": contract.get("_contract_path"),
            "job_id": contract_identity(contract)[0],
            "name": contract_identity(contract)[1],
            "status": "missing_live_job",
            "severity": "error" if contract.get("required", True) else "warning",
            "drift": [],
        }
    drift: list[dict[str, Any]] = []
    for field in fields:
        expected = expected_value(contract, field)
        if expected is None and not bool(contract.get("compare_nulls", False)):
            continue
        actual = get_nested(live_job, field)
        if actual != expected:
            drift.append({"field": field, "expected": expected, "actual": actual})
    expected_artifacts = []
    for item in as_list(contract.get("expected_artifacts")):
        path = ROOT / str(item)
        expected_artifacts.append({"path": str(item), "exists": path.exists()})
    missing_artifacts = [item for item in expected_artifacts if not item["exists"]]
    return {
        "contract_path": contract.get("_contract_path"),
        "job_id": live_job.get("id"),
        "name": live_job.get("name"),
        "status": "drift" if drift else "ok",
        "severity": "warning" if drift else "ok",
        "drift": drift,
        "expected_artifacts": expected_artifacts,
        "missing_expected_artifacts": missing_artifacts,
    }


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    contract_dir = args.contract_dir if args.contract_dir.is_absolute() else ROOT / args.contract_dir
    jobs, live_meta = load_live_jobs(args.live_file)
    contracts, warnings = load_contracts(contract_dir, args.contract)
    results = [compare_contract(contract, find_live_job(contract, jobs)) for contract in contracts]
    drift_count = sum(1 for item in results if item.get("status") == "drift")
    missing_count = sum(1 for item in results if item.get("status") == "missing_live_job")
    errors = []
    if not live_meta.get("ok"):
        errors.append("live_cron_list_unavailable")
    if args.require_contracts and not contracts:
        errors.append("no_contracts_found")
    if args.fail_on_drift and (drift_count or missing_count):
        errors.append("cron_contract_drift_present")
    if not contracts:
        warnings.append(f"no_contracts_found:{rel(contract_dir)}")
    status = "error" if errors else "warning" if warnings or drift_count or missing_count else "ok"
    return {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": status,
        "summary": {
            "contract_count": len(contracts),
            "live_job_count": len(jobs),
            "drift_count": drift_count,
            "missing_live_job_count": missing_count,
            "next_safe_action": (
                "Create state\\cron-contracts\\*.json for important jobs."
                if not contracts else
                "Review drift entries; use cron_patch_manager.py for approved live patches."
            ),
        },
        "sources": {
            "contract_dir": rel(contract_dir),
            "live": live_meta,
        },
        "contracts": results,
        "authority_boundary": AUTHORITY_BOUNDARY,
        "validation": {"status": "error" if errors else "warning" if warnings else "ok", "errors": errors, "warnings": warnings},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--contract-dir", type=Path, default=DEFAULT_CONTRACT_DIR)
    parser.add_argument("--contract", type=Path, action="append")
    parser.add_argument("--live-file", type=Path)
    parser.add_argument("--require-contracts", action="store_true")
    parser.add_argument("--fail-on-drift", action="store_true")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    payload = build_payload(args)
    out = args.out if args.out.is_absolute() else ROOT / args.out
    if args.write:
        atomic_write_json(out, payload)
    print(
        f"status={payload['status']} contracts={payload['summary']['contract_count']} "
        f"drift={payload['summary']['drift_count']} missing={payload['summary']['missing_live_job_count']} out={rel(out)}"
    )
    if args.validate and payload["validation"]["status"] == "error":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
