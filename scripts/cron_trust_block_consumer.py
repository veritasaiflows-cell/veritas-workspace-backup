from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from market_data_utils import load_json_artifact

WORKSPACE = Path(__file__).resolve().parents[1]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fail-closed reader for machine-readable automation trust blocks."
    )
    parser.add_argument("--trust-block", required=True, help="Path to a normalized automation trust block JSON artifact.")
    parser.add_argument("--require-workflow", help="Optional expected workflow name.")
    return parser.parse_args()


def read_json(path: Path) -> dict[str, Any]:
    data = load_json_artifact(path)
    if not isinstance(data, dict):
        raise SystemExit(f"trust block artifact must be a JSON object: {path}")
    return data


def main() -> int:
    args = parse_args()
    path = Path(args.trust_block)
    if not path.is_absolute():
        path = WORKSPACE / path
    payload = read_json(path)

    status = str(payload.get("status") or "").strip().lower()
    trust_block = payload.get("trust_block") or {}
    consumer = payload.get("consumer") or {}
    issues = payload.get("issues") or []
    workflow = str(trust_block.get("workflow") or "").strip()
    expected = str(args.require_workflow or "").strip()

    if expected and workflow != expected:
        print(json.dumps({
            "status": "blocked",
            "workflow": workflow,
            "reason": f"workflow mismatch: expected {expected}, got {workflow or 'missing'}",
        }, indent=2))
        return 2

    if status != "ok":
        print(json.dumps({
            "status": "blocked",
            "workflow": workflow,
            "reason": str(consumer.get("fail_closed_reason") or "; ".join(str(x) for x in issues) or "trust block not approved"),
        }, indent=2))
        return 2

    if not bool(consumer.get("cron_read_allowed")):
        print(json.dumps({
            "status": "blocked",
            "workflow": workflow,
            "reason": str(consumer.get("fail_closed_reason") or "cron read not allowed"),
        }, indent=2))
        return 2

    if str(consumer.get("allowed_posture") or "") != "read_only":
        print(json.dumps({
            "status": "blocked",
            "workflow": workflow,
            "reason": f"unsafe consumer posture: {consumer.get('allowed_posture') or 'missing'}",
        }, indent=2))
        return 2

    print(json.dumps({
        "status": "ok",
        "workflow": workflow,
        "consumer_posture": "read_only",
        "decision": trust_block.get("decision"),
        "trust_level": trust_block.get("trust_level"),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
