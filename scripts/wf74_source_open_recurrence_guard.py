#!/usr/bin/env python3
"""Compatibility guard proving WF74 uses the alerts-OS boundary before scoring."""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, load_json_artifact
import wf74_model_quality_collection_cron_runner as wf74_runner

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
OUT_JSON = TMP / "wf78-source-open-recurrence-guard.json"
SCHEMA = "veritas.wf74_source_open_recurrence_guard.v1"
PIVOT_PROOF = TMP / "alerts-os-pivot-validator.json"
FINANCE_QUALITY = TMP / "finance-response-quality-slice.json"
WF74_PACKET = TMP / "wf74-model-quality-collection-cron-runner.json"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def runner_order() -> dict[str, Any]:
    names = [name for name, _command, _timeout in wf74_runner.command_plan(include_harness=False)]
    boundary_index = names.index("alerts_os_pivot_validator") if "alerts_os_pivot_validator" in names else None
    quality_index = names.index("finance_response_quality_slice") if "finance_response_quality_slice" in names else None
    return {
        "plan_step_count": len(names),
        "alerts_os_boundary_present": boundary_index is not None,
        "finance_response_quality_present": quality_index is not None,
        "alerts_os_boundary_index": boundary_index,
        "finance_response_quality_index": quality_index,
        "boundary_before_quality": boundary_index is not None and quality_index is not None and boundary_index < quality_index,
        "alerts_os_boundary_blocking": not wf74_runner.is_non_blocking_step("alerts_os_pivot_validator"),
    }


def finance_taxonomy(packet: dict[str, Any]) -> dict[str, Any]:
    summary = as_dict(packet.get("summary"))
    return {
        "finance_response_quality_status": packet.get("status"),
        "finance_response_quality_validation": as_dict(packet.get("validation")).get("status"),
        "alerts_os_answer_path_ok": summary.get("alerts_os_answer_path_ok"),
        "blocked_archetype_count": int(summary.get("blocked_archetype_count") or 0),
        "source_open_blocked_count": int(summary.get("source_open_blocked_count") or 0),
        "source_freshness_blocked_count": int(summary.get("source_freshness_blocked_count") or 0),
    }


def validate(payload: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    order = as_dict(payload.get("runner_order"))
    taxonomy = as_dict(payload.get("finance_taxonomy"))
    pivot = as_dict(payload.get("alerts_os_boundary_proof"))
    if order.get("alerts_os_boundary_present") is not True:
        errors.append("missing_alerts_os_pivot_validator_step")
    if order.get("finance_response_quality_present") is not True:
        errors.append("missing_finance_response_quality_slice_step")
    if order.get("boundary_before_quality") is not True:
        errors.append("alerts_os_boundary_not_before_finance_quality")
    if order.get("alerts_os_boundary_blocking") is not True:
        errors.append("alerts_os_boundary_must_be_blocking")
    if pivot.get("status") != "ok" or int(pivot.get("error_count") or 0) != 0:
        errors.append("alerts_os_boundary_proof_not_green")
    if taxonomy.get("finance_response_quality_status") != "ok" or taxonomy.get("finance_response_quality_validation") != "ok":
        errors.append("finance_response_quality_not_green")
    if taxonomy.get("alerts_os_answer_path_ok") is not True:
        errors.append("alerts_os_answer_path_not_green")
    if taxonomy.get("blocked_archetype_count"):
        errors.append("finance_response_archetypes_blocked")
    if taxonomy.get("source_open_blocked_count"):
        errors.append("retired_source_open_state_recurred")
    if taxonomy.get("source_freshness_blocked_count"):
        warnings.append("freshness_review_required")
    return {"status": "blocked" if errors else ("warning" if warnings else "ok"), "errors": errors, "warnings": warnings}


def build_payload() -> dict[str, Any]:
    quality = as_dict(load_json_artifact(FINANCE_QUALITY))
    pivot = as_dict(load_json_artifact(PIVOT_PROOF))
    wf74 = as_dict(load_json_artifact(WF74_PACKET))
    payload = {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "ok",
        "purpose": "Prove the alerts-OS boundary runs before finance response-quality scoring; the legacy filename is compatibility-only.",
        "runner_order": runner_order(),
        "alerts_os_boundary_proof": {
            "path": rel(PIVOT_PROOF),
            "status": pivot.get("status"),
            "error_count": pivot.get("error_count"),
            "warning_count": pivot.get("warning_count"),
        },
        "finance_taxonomy": finance_taxonomy(quality),
        "wf74_runner_artifact": {
            "path": rel(WF74_PACKET),
            "status": wf74.get("status"),
            "validation": as_dict(wf74.get("validation")).get("status"),
        },
        "authority_boundary": {
            "review_only": True,
            "cron_or_runtime_mutation_allowed": False,
            "writes_finance_canon": False,
            "capital_or_order_authority": False,
            "paper_or_live_execution_allowed": False,
            "owner_approval_inferred": False,
        },
        "sources": [rel(PIVOT_PROOF), rel(FINANCE_QUALITY), rel(WF74_PACKET)],
    }
    payload["validation"] = validate(payload)
    payload["status"] = payload["validation"]["status"]
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--out", type=Path, default=OUT_JSON)
    args = parser.parse_args()
    payload = build_payload()
    out = args.out if args.out.is_absolute() else ROOT / args.out
    if args.write:
        atomic_write_json(out, payload)
    print(json.dumps({"status": payload["status"], "validation": payload["validation"]["status"], "out": rel(out), "errors": payload["validation"]["errors"], "warnings": payload["validation"]["warnings"]}, indent=2))
    return 1 if args.validate and payload["validation"]["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
