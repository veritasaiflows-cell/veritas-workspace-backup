#!/usr/bin/env python3
"""Predict lane/write collisions before implementation starts."""
from __future__ import annotations

import argparse
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, load_json_artifact
import concurrent_lane_manager as lanes

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
DEFAULT_OUT = TMP / "lane-collision-preflight.json"
DEFAULT_REGISTER = TMP / "concurrent-lane-register.json"
SCHEMA = "veritas.lane_collision_preflight.v1"

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "collision_prediction_only": True,
    "leases_lanes": False,
    "writes_register": False,
    "canon_or_portfolio_mutation_allowed": False,
    "config_auth_runtime_mutation_allowed": False,
    "paper_or_live_execution_allowed": False,
    "owner_approval_inferred": False,
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def normalize(path: str) -> str:
    return path.replace("\\", "/").strip().lstrip("./")


def rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def load_register(path: Path) -> dict[str, Any]:
    payload = load_json_artifact(path)
    return payload if isinstance(payload, dict) else {}


def active_lanes(register: dict[str, Any]) -> list[dict[str, Any]]:
    return [lane for lane in as_list(register.get("lanes")) if isinstance(lane, dict) and lane.get("status") in lanes.ACTIVE_STATUSES]


def git_dirty_paths() -> list[str]:
    completed = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT, text=True, capture_output=True, check=False)
    if completed.returncode != 0:
        return []
    paths: list[str] = []
    for line in completed.stdout.splitlines():
        if len(line) < 4:
            continue
        path = line[3:]
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        paths.append(normalize(path))
    return sorted(set(paths))


def overlaps(requested: list[str], active: list[dict[str, Any]]) -> list[dict[str, Any]]:
    hits: list[dict[str, Any]] = []
    requested_set = {normalize(path) for path in requested}
    for lane in active:
        for path in [normalize(str(item)) for item in as_list(lane.get("allowed_writes"))]:
            if path in requested_set:
                hits.append({"path": path, "lane_id": lane.get("lane_id"), "owner": lane.get("owner"), "status": lane.get("status")})
    return hits


def forbidden_hits(requested: list[str]) -> list[dict[str, str]]:
    hits = []
    for path in requested:
        pattern = lanes.path_forbidden(path)
        if pattern:
            hits.append({"path": normalize(path), "pattern": pattern})
    return hits


def dirty_overlaps(requested: list[str], dirty: list[str]) -> list[str]:
    requested_set = {normalize(path) for path in requested}
    return sorted(requested_set & set(dirty))


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    register_path = args.register if args.register.is_absolute() else ROOT / args.register
    register = load_register(register_path)
    requested = [normalize(path) for path in (args.write_path or [])]
    dirty = git_dirty_paths()
    active = active_lanes(register)
    collision_rows = overlaps(requested, active)
    forbidden = forbidden_hits(requested)
    dirty_hits = dirty_overlaps(requested, dirty)
    errors = []
    warnings = []
    if collision_rows:
        errors.append("active_lane_write_collision_predicted")
    if forbidden:
        errors.append("requested_forbidden_write_surface")
    if dirty_hits and not args.ignore_dirty:
        warnings.append("requested_paths_already_dirty")
    if not requested:
        warnings.append("no_requested_write_paths")
    status = "error" if errors else "warning" if warnings else "ok"
    return {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": status,
        "summary": {
            "requested_write_count": len(requested),
            "active_lane_count": len(active),
            "collision_count": len(collision_rows),
            "forbidden_hit_count": len(forbidden),
            "dirty_overlap_count": len(dirty_hits),
            "next_safe_action": "Lease exact writable surfaces only after collision_count and forbidden_hit_count are zero.",
        },
        "requested_writes": requested,
        "collisions": collision_rows,
        "forbidden_hits": forbidden,
        "dirty_overlaps": dirty_hits,
        "active_lanes": [{"lane_id": lane.get("lane_id"), "owner": lane.get("owner"), "allowed_writes": lane.get("allowed_writes", [])} for lane in active],
        "sources": {"register": rel(register_path)},
        "authority_boundary": AUTHORITY_BOUNDARY,
        "validation": {"status": "error" if errors else "warning" if warnings else "ok", "errors": errors, "warnings": warnings},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write-path", action="append", help="Intended write path; may be repeated.")
    parser.add_argument("--register", type=Path, default=DEFAULT_REGISTER)
    parser.add_argument("--ignore-dirty", action="store_true")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    payload = build_payload(args)
    out = args.out if args.out.is_absolute() else ROOT / args.out
    if args.write:
        atomic_write_json(out, payload)
    print(
        f"status={payload['status']} requested={payload['summary']['requested_write_count']} "
        f"collisions={payload['summary']['collision_count']} out={rel(out)}"
    )
    if args.validate and payload["validation"]["status"] == "error":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
