#!/usr/bin/env python3
"""Validate helper-lane completion before main-session synthesis.

This wraps the existing swarm completion idea for helper lanes. It can evaluate
a manifest of expected helper lanes, or emit an idle/ready contract when no
helpers are active. It is proof only and grants no merge, mutation, or approval
authority.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, load_json_artifact
from swarm_completion_handshake import build_result as build_swarm_result

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
DEFAULT_OUT = TMP / "helper-completion-handshake.json"
DEFAULT_PACKETS = TMP / "helper-spawn-packets.json"

SCHEMA = "veritas.helper_completion_handshake.v1"

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "synthesis_allowed_by_default": False,
    "helper_final_authority": False,
    "main_session_final_integrator": True,
    "config_auth_channel_runtime_mutation_allowed": False,
    "cleanup_move_delete_archive_allowed": False,
    "customer_or_external_delivery_allowed": False,
    "sql_or_ticker_import_allowed": False,
    "canon_or_portfolio_mutation_allowed": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "owner_approval_inferred": False,
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def load_json(path: Path) -> dict[str, Any]:
    payload = load_json_artifact(path)
    return payload if isinstance(payload, dict) else {}


def idle_payload(packets_path: Path) -> dict[str, Any]:
    packets = load_json(packets_path)
    payload = {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "ok",
        "mode": "idle_contract",
        "sources": {"helper_spawn_packets": rel(packets_path)},
        "authority_boundary": AUTHORITY_BOUNDARY,
        "active_helper_lanes": [],
        "synthesis_allowed": True,
        "reason": "no_active_helper_lanes_declared",
        "required_closeout_fields": [
            "status",
            "files_inspected",
            "files_changed_or_patch_proposed",
            "tests_or_validators_run",
            "blockers_or_trust_gaps",
            "confidence",
            "merge_recommendation",
            "next_action",
        ],
        "packet_count": packets.get("packet_count"),
    }
    payload["validation"] = validate_payload(payload)
    payload["status"] = "ok" if payload["validation"]["status"] == "ok" else "error"
    return payload


def manifest_payload(manifest_path: Path) -> dict[str, Any]:
    manifest = load_json(manifest_path)
    result = build_swarm_result(manifest, manifest_path)
    payload = {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "ok" if result.get("synthesis_allowed") else "blocked",
        "mode": "manifest_evaluation",
        "sources": {"manifest": rel(manifest_path)},
        "authority_boundary": AUTHORITY_BOUNDARY,
        "active_helper_lanes": result.get("lanes", []),
        "synthesis_allowed": bool(result.get("synthesis_allowed")),
        "blocking_lanes": result.get("blocking_lanes", []),
        "swarm_result": result,
    }
    payload["validation"] = validate_payload(payload)
    if payload["validation"]["status"] != "ok":
        payload["status"] = "error"
    return payload


def validate_payload(payload: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    for key, expected in AUTHORITY_BOUNDARY.items():
        if as_dict(payload.get("authority_boundary")).get(key) is not expected:
            errors.append(f"authority_boundary_{key}_not_{str(expected).lower()}")
    if payload.get("mode") == "manifest_evaluation" and payload.get("synthesis_allowed") and payload.get("blocking_lanes"):
        errors.append("synthesis_allowed_with_blocking_lanes")
    if payload.get("mode") == "idle_contract" and payload.get("active_helper_lanes"):
        errors.append("idle_contract_has_active_lanes")
    return {"status": "ok" if not errors else "error", "errors": errors, "warnings": []}


def workspace_path(value: str | None) -> Path | None:
    if not value:
        return None
    path = Path(value)
    return path if path.is_absolute() else ROOT / path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate helper-lane completion before synthesis.")
    parser.add_argument("--manifest", help="Expected helper-lane manifest JSON.")
    parser.add_argument("--packets", default=str(DEFAULT_PACKETS), help="Helper spawn packet artifact for idle mode.")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    out = workspace_path(args.out)
    manifest = workspace_path(args.manifest)
    payload = manifest_payload(manifest) if manifest else idle_payload(workspace_path(args.packets) or DEFAULT_PACKETS)
    if args.write and out:
        atomic_write_json(out, payload)
    print(json.dumps({
        "status": payload.get("status"),
        "mode": payload.get("mode"),
        "synthesis_allowed": payload.get("synthesis_allowed"),
        "out": rel(out) if out else None,
        "validation": payload.get("validation"),
    }, indent=2, sort_keys=True))
    return 1 if args.validate and payload.get("status") not in {"ok", "blocked"} else 0


if __name__ == "__main__":
    raise SystemExit(main())
