#!/usr/bin/env python3
"""Normalize retired cron contracts as disabled, owner-gated history."""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
RETIRED_DIR = ROOT / "state" / "cron-contracts-retired"
PROOF = ROOT / "tmp" / "retired-cron-contract-normalization.json"


def now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"contract must be an object: {path}")
    return value


def normalized(contract: dict[str, Any]) -> dict[str, Any]:
    result = dict(contract)
    name = str(result.get("name") or result.get("job_name") or "Unnamed retired cron")
    if not name.startswith("Retired — "):
        name = "Retired — " + name
    result["name"] = name
    result["required"] = False
    result["enabled"] = False
    result["retired_at_local"] = result.get("retired_at_local") or "2026-08-29 America/Phoenix"
    result["retirement_reason"] = result.get("retirement_reason") or (
        "Retired from the active scheduler contract set. Historical proof only; no automatic resume."
    )
    result["rollback_requires_owner_gate"] = True
    return result


def write_json(path: Path, payload: dict[str, Any]) -> None:
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(payload, indent=2, sort_keys=False) + "\n", encoding="utf-8")
    temp.replace(path)


def validate_contract(contract: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if contract.get("required") is not False:
        errors.append("required_not_false")
    if contract.get("enabled") is not False:
        errors.append("enabled_not_false")
    if not str(contract.get("name") or "").startswith("Retired — "):
        errors.append("name_not_prefixed")
    if contract.get("rollback_requires_owner_gate") is not True:
        errors.append("rollback_gate_missing")
    if not contract.get("retired_at_local"):
        errors.append("retired_at_missing")
    if not contract.get("retirement_reason"):
        errors.append("retirement_reason_missing")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    args = parser.parse_args()
    files = sorted(RETIRED_DIR.glob("*.json"))
    results: list[dict[str, Any]] = []
    for path in files:
        original = load(path)
        candidate = normalized(original)
        if args.write and candidate != original:
            write_json(path, candidate)
        current = load(path) if args.write else candidate
        results.append({
            "path": path.relative_to(ROOT).as_posix(),
            "changed": candidate != original,
            "errors": validate_contract(current),
        })
    errors = [f"{row['path']}:{error}" for row in results for error in row["errors"]]
    proof = {
        "schema": "veritas.retired_cron_contract_normalization.v1",
        "generated_at_utc": now_utc(),
        "status": "error" if errors else "ok",
        "summary": {
            "contract_count": len(results),
            "changed_count": sum(1 for row in results if row["changed"]),
            "error_count": len(errors),
        },
        "results": results,
        "validation": {"status": "error" if errors else "ok", "errors": errors},
    }
    if args.write:
        write_json(PROOF, proof)
    print(json.dumps({"status": proof["status"], **proof["summary"]}, indent=2))
    return 1 if args.validate and errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
