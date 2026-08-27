from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, load_json_artifact
from helper_lane_manifest import (
    CONTRACT_VERSION,
    DELIVERY_MODE_PATCH_DRAFT,
    LEGACY_SCHEMA,
    PREVIOUS_SCHEMA,
    SCHEMA as HANDOFF_SCHEMA,
    normalize_base_path,
    revalidate_lane_handoff,
    validate_receiver_readback,
    v3_completion_proof_issues,
)

WORKSPACE = Path(__file__).resolve().parents[1]
TMP = WORKSPACE / "tmp"
DEFAULT_OUT = TMP / "swarm-handshake-status.json"
TERMINAL_STATUSES = {"completed", "abandoned", "canceled", "timed_out", "failed"}
SUCCESS_STATUSES = {"completed", "abandoned", "canceled", "timed_out"}
SHA256_REF_RE = re.compile(r"^sha256:[0-9a-f]{64}$")


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


def artifact_ok(spec: dict[str, Any], base_path: Path | None = None) -> tuple[bool, str]:
    raw_path = spec.get("path")
    if not raw_path or not isinstance(raw_path, str):
        return False, "artifact path missing"
    path = Path(raw_path)
    if base_path is not None:
        if path.is_absolute() or ".." in path.parts:
            return False, f"artifact path must be base-relative ({raw_path})"
        try:
            path = (base_path / path).resolve(strict=True)
            path.relative_to(base_path.resolve(strict=True))
        except (OSError, ValueError):
            return False, f"artifact path escapes or is missing ({raw_path})"
    elif not path.is_absolute():
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


def main_applied_diff_proof_issues(lane: dict[str, Any], handoff: dict[str, Any]) -> list[str]:
    """Compatibility wrapper for the shared v3 closeout-proof validator."""
    if lane.get("handoff") is not handoff:
        lane = {**lane, "handoff": handoff}
    return v3_completion_proof_issues(lane, WORKSPACE)


def evaluate_lane(
    lane: dict[str, Any],
    strict_handoff: bool = False,
    v3_contract: bool = False,
    expected_contract_version: int | None = None,
    legacy_manifest: bool = False,
) -> dict[str, Any]:
    lane_id = str(lane.get("lane_id") or "").strip()
    if not lane_id:
        return {"lane_id": "<missing>", "status": "invalid", "resolved": False, "ready_for_synthesis": False, "issues": ["lane_id missing"]}

    status = str(lane.get("status") or "pending").strip().lower()
    artifacts = lane.get("required_artifacts") or []
    if not isinstance(artifacts, list):
        artifacts = []
    issues: list[str] = []
    warnings: list[str] = []
    handoff_revalidation: dict[str, Any] | None = None
    receiver_readback: dict[str, Any] | None = None
    artifact_base: Path | None = None
    handoff = lane.get("handoff") if isinstance(lane.get("handoff"), dict) else {}
    actual_contract_version = int(handoff.get("contract_version") or 0) if handoff else None
    if expected_contract_version is not None and actual_contract_version != expected_contract_version:
        issues.append("manifest_handoff_contract_version_mismatch")
    if legacy_manifest and handoff:
        issues.append("legacy_manifest_with_frozen_handoff_unsupported")
    if strict_handoff:
        handoff_revalidation = revalidate_lane_handoff(lane, WORKSPACE)
        if handoff_revalidation["status"] != "ok":
            issues.extend(handoff_revalidation["errors"])
        try:
            _, artifact_base = normalize_base_path(str(handoff.get("base_path") or ""), WORKSPACE)
        except (OSError, ValueError) as exc:
            issues.append(str(exc))
        if actual_contract_version == CONTRACT_VERSION and status == "completed":
            receiver_readback = validate_receiver_readback(handoff, lane.get("receiver_readback"))
            if receiver_readback["status"] != "ok":
                issues.extend(receiver_readback["errors"])
            issues.extend(main_applied_diff_proof_issues(lane, handoff))
    else:
        warnings.append("legacy_manifest_without_frozen_handoff_revalidation")
    artifact_results: list[dict[str, Any]] = []
    for artifact in artifacts:
        if not isinstance(artifact, dict):
            issues.append("artifact spec invalid")
            continue
        ok, detail = artifact_ok(artifact, artifact_base)
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
    ready = (status == "completed" if v3_contract else status in SUCCESS_STATUSES) and not issues
    return {
        "lane_id": lane_id,
        "status": status,
        "resolved": resolved,
        "ready_for_synthesis": ready,
        "verdict": verdict,
        "artifact_checks": artifact_results,
        "handoff_revalidation": handoff_revalidation,
        "receiver_readback": receiver_readback,
        "warnings": warnings,
        "issues": issues,
    }


def build_result(manifest: dict[str, Any], manifest_path: Path) -> dict[str, Any]:
    lanes = manifest.get("expected_lanes")
    if not isinstance(lanes, list) or not lanes:
        raise SystemExit("manifest.expected_lanes must be a non-empty array")

    schema = str(manifest.get("schema") or "")
    if schema not in {HANDOFF_SCHEMA, PREVIOUS_SCHEMA, LEGACY_SCHEMA}:
        raise SystemExit(f"unsupported helper-lane manifest schema: {schema or '<missing>'}")
    strict_handoff = schema in {HANDOFF_SCHEMA, PREVIOUS_SCHEMA}
    v3_contract = schema == HANDOFF_SCHEMA
    expected_contract_version = CONTRACT_VERSION if schema == HANDOFF_SCHEMA else 2 if schema == PREVIOUS_SCHEMA else None
    results = [
        evaluate_lane(
            lane if isinstance(lane, dict) else {},
            strict_handoff,
            v3_contract,
            expected_contract_version,
            schema == LEGACY_SCHEMA,
        )
        for lane in lanes
    ]
    blocking = [lane for lane in results if not lane["ready_for_synthesis"]]
    status = "ok" if not blocking else "blocked"
    stop_line = bool(blocking)

    return {
        "status": status,
        "generated_at_utc": utc_now_iso(),
        "manifest_path": relpath(manifest_path),
        "manifest_schema": schema,
        "observed_manifest_file_sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
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
        "warnings": sorted({warning for lane in results for warning in lane.get("warnings", [])} | ({"v2_manifest_compatibility_mode"} if schema == PREVIOUS_SCHEMA else set())),
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
