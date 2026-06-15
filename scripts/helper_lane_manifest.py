#!/usr/bin/env python3
"""Build helper-lane manifests for completion handshakes.

This is a thin adapter around ``swarm_completion_handshake.py``. It records the
expected helper lanes and their required closeout artifacts; it does not spawn
helpers, merge work, or grant any authority beyond proof routing.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
DEFAULT_OUT = TMP / "helper-lane-active-manifest.json"

SCHEMA = "veritas.helper_lane_manifest.v1"
TERMINAL_STATUSES = {"completed", "abandoned", "canceled", "timed_out", "failed"}
NON_TERMINAL_STATUSES = {"pending", "running"}
ALLOWED_STATUSES = TERMINAL_STATUSES | NON_TERMINAL_STATUSES

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "helper_final_authority": False,
    "main_session_final_integrator": True,
    "cron_or_heartbeat_may_spawn": False,
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


def workspace_path(value: str | None, default: Path | None = None) -> Path:
    if not value:
        if default is None:
            raise SystemExit("path value missing")
        return default
    path = Path(value)
    return path if path.is_absolute() else ROOT / path


def parse_artifact(value: str) -> dict[str, Any]:
    raw_path, sep, raw_kind = value.partition(":")
    kind = raw_kind.strip().lower() if sep else "file"
    if kind not in {"file", "json"}:
        raise SystemExit(f"unsupported artifact kind: {kind}")
    return {"path": raw_path.strip(), "kind": kind}


def validate_payload(payload: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    lanes = payload.get("expected_lanes")
    if not isinstance(lanes, list) or not lanes:
        errors.append("expected_lanes_missing")
    for lane in lanes if isinstance(lanes, list) else []:
        if not isinstance(lane, dict):
            errors.append("lane_not_object")
            continue
        lane_id = str(lane.get("lane_id") or "").strip()
        status = str(lane.get("status") or "").strip().lower()
        if not lane_id:
            errors.append("lane_id_missing")
        if status not in ALLOWED_STATUSES:
            errors.append(f"{lane_id or '<missing>'}:invalid_status:{status or '<missing>'}")
        if status == "completed" and not str(lane.get("verdict") or "").strip():
            errors.append(f"{lane_id}:completed_without_verdict")
        if lane.get("allow_partial") is True and status not in TERMINAL_STATUSES:
            errors.append(f"{lane_id}:partial_allowed_before_terminal_status")
        artifacts = lane.get("required_artifacts")
        if not isinstance(artifacts, list):
            errors.append(f"{lane_id}:required_artifacts_not_array")
    for key, expected in AUTHORITY_BOUNDARY.items():
        if payload.get("authority_boundary", {}).get(key) is not expected:
            errors.append(f"authority_boundary_{key}_not_{str(expected).lower()}")
    return {"status": "ok" if not errors else "error", "errors": errors, "warnings": []}


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    status = str(args.status).strip().lower()
    lane = {
        "lane_id": args.lane_id,
        "status": status,
        "packet_id": args.packet_id,
        "session_id": args.session_id,
        "session_label": args.session_label,
        "owner_workflow": args.owner_workflow,
        "started_at_utc": args.started_at_utc,
        "updated_at_utc": utc_now(),
        "verdict": args.verdict or "",
        "required_artifacts": [parse_artifact(item) for item in args.required_artifact],
        "allow_partial": bool(args.allow_partial),
        "authority_boundary": AUTHORITY_BOUNDARY,
    }
    payload = {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "swarm_id": args.swarm_id,
        "status": "ok",
        "expected_lanes": [lane],
        "authority_boundary": AUTHORITY_BOUNDARY,
        "use_rule": "Main session uses this manifest to block synthesis until expected helper lanes close with proof.",
    }
    payload["validation"] = validate_payload(payload)
    payload["status"] = "ok" if payload["validation"]["status"] == "ok" else "error"
    return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a helper-lane completion manifest.")
    parser.add_argument("--swarm-id", default="operating-leverage-helper-lanes")
    parser.add_argument("--lane-id", required=True)
    parser.add_argument("--packet-id", default="independent-qa-helper")
    parser.add_argument("--session-id", default="")
    parser.add_argument("--session-label", default="")
    parser.add_argument("--owner-workflow", default="operating_leverage")
    parser.add_argument("--started-at-utc", default=utc_now())
    parser.add_argument("--status", choices=sorted(ALLOWED_STATUSES), required=True)
    parser.add_argument("--verdict", default="")
    parser.add_argument("--required-artifact", action="append", default=[])
    parser.add_argument("--allow-partial", action="store_true")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    out = workspace_path(args.out, DEFAULT_OUT)
    payload = build_payload(args)
    if args.write:
        atomic_write_json(out, payload)
    print(json.dumps({
        "status": payload.get("status"),
        "out": rel(out),
        "swarm_id": payload.get("swarm_id"),
        "lane_count": len(payload.get("expected_lanes", [])),
        "synthesis_status": "blocked" if args.status in NON_TERMINAL_STATUSES else "ready_for_handshake_check",
        "validation": payload.get("validation"),
    }, indent=2, sort_keys=True))
    return 1 if args.validate and payload.get("status") != "ok" else 0


if __name__ == "__main__":
    raise SystemExit(main())
