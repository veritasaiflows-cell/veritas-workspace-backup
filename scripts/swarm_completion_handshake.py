from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, load_json_artifact

WORKSPACE = Path(__file__).resolve().parents[1]
TMP = WORKSPACE / "tmp"
DEFAULT_OUT = TMP / "swarm-handshake-status.json"
TERMINAL_STATUSES = {"completed", "abandoned", "canceled", "timed_out", "failed"}
SUCCESS_STATUSES = {"completed", "abandoned", "canceled", "timed_out"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fail-closed swarm completion handshake for bounded multi-lane synthesis."
    )
    parser.add_argument("--manifest", required=True, help="Path to the expected-lane manifest JSON.")
    parser.add_argument(
        "--write",
        action="store_true",
        help="Write the evaluated handshake result to tmp/swarm-handshake-status.json or --out.",
    )
    parser.add_argument("--out", help="Optional output path for --write.")
    return parser.parse_args()


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_dict(path: Path) -> dict[str, Any]:
    data = load_json_artifact(path)
    if not isinstance(data, dict):
        raise SystemExit(f"manifest must be a JSON object: {path}")
    return data


def relpath(path: Path) -> str:
    try:
        return str(path.relative_to(WORKSPACE)).replace("\\", "/")
    except Exception:
        return str(path)


def artifact_ok(spec: dict[str, Any]) -> tuple[bool, str]:
    raw_path = spec.get("path")
    if not raw_path or not isinstance(raw_path, str):
        return False, "artifact path missing"
    path = Path(raw_path)
    if not path.is_absolute():
        path = WORKSPACE / path
    kind = str(spec.get("kind") or "file").strip().lower()
    if not path.exists():
        return False, f"missing artifact {relpath(path)}"
    if kind == "json":
        data = load_json_artifact(path)
        if data is None:
            return False, f"invalid json artifact {relpath(path)}"
        status_value = ""
        if isinstance(data, dict):
            status_value = str(data.get("status") or data.get("overall_status") or data.get("overall") or "").strip().lower()
        if status_value in {"error", "failed", "blocked", "missing", "critical"}:
            return False, f"artifact {relpath(path)} status={status_value}"
    return True, "ok"


def evaluate_lane(lane: dict[str, Any]) -> dict[str, Any]:
    lane_id = str(lane.get("lane_id") or "").strip()
    if not lane_id:
        return {"lane_id": "<missing>", "status": "invalid", "resolved": False, "ready_for_synthesis": False, "issues": ["lane_id missing"]}

    status = str(lane.get("status") or "pending").strip().lower()
    artifacts = lane.get("required_artifacts") or []
    if not isinstance(artifacts, list):
        artifacts = []
    issues: list[str] = []
    artifact_results: list[dict[str, Any]] = []
    for artifact in artifacts:
        if not isinstance(artifact, dict):
            issues.append("artifact spec invalid")
            continue
        ok, detail = artifact_ok(artifact)
        artifact_results.append({
            "path": artifact.get("path"),
            "kind": artifact.get("kind", "file"),
            "ok": ok,
            "detail": detail,
        })
        if not ok:
            issues.append(detail)

    if status not in TERMINAL_STATUSES and not lane.get("allow_partial"):
        issues.append(f"lane status unresolved ({status})")

    verdict = str(lane.get("verdict") or "").strip()
    if status == "completed" and not verdict:
        issues.append("completed lane missing verdict")

    resolved = status in TERMINAL_STATUSES
    ready = status in SUCCESS_STATUSES and not issues
    return {
        "lane_id": lane_id,
        "status": status,
        "resolved": resolved,
        "ready_for_synthesis": ready,
        "verdict": verdict,
        "artifact_checks": artifact_results,
        "issues": issues,
    }


def build_result(manifest: dict[str, Any], manifest_path: Path) -> dict[str, Any]:
    lanes = manifest.get("expected_lanes")
    if not isinstance(lanes, list) or not lanes:
        raise SystemExit("manifest.expected_lanes must be a non-empty array")

    results = [evaluate_lane(lane if isinstance(lane, dict) else {}) for lane in lanes]
    blocking = [lane for lane in results if not lane["ready_for_synthesis"]]
    status = "ok" if not blocking else "blocked"
    stop_line = bool(blocking)

    return {
        "status": status,
        "generated_at_utc": utc_now_iso(),
        "manifest_path": relpath(manifest_path),
        "swarm_id": manifest.get("swarm_id") or manifest_path.stem,
        "summary": {
            "expected_lane_count": len(results),
            "resolved_lane_count": sum(1 for lane in results if lane["resolved"]),
            "ready_lane_count": sum(1 for lane in results if lane["ready_for_synthesis"]),
            "blocking_lane_count": len(blocking),
        },
        "stop_line": stop_line,
        "blocking_lanes": [
            {"lane_id": lane["lane_id"], "status": lane["status"], "issues": lane["issues"]}
            for lane in blocking
        ],
        "lanes": results,
        "synthesis_allowed": not stop_line,
    }


def main() -> int:
    args = parse_args()
    manifest_path = Path(args.manifest)
    if not manifest_path.is_absolute():
        manifest_path = WORKSPACE / manifest_path
    manifest = load_dict(manifest_path)
    result = build_result(manifest, manifest_path)

    if args.write:
        out_path = Path(args.out) if args.out else DEFAULT_OUT
        if not out_path.is_absolute():
            out_path = WORKSPACE / out_path
        atomic_write_json(out_path, result)
        result["out"] = relpath(out_path)

    print(json.dumps(result, indent=2))
    return 0 if result["status"] == "ok" else 2


if __name__ == "__main__":
    raise SystemExit(main())
