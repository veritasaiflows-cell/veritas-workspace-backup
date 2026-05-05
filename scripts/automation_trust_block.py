from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, load_json_artifact

WORKSPACE = Path(__file__).resolve().parents[1]
TMP = WORKSPACE / "tmp"
DEFAULT_OUT = TMP / "automation-trust-block.json"
ALLOWED_PHASES = {"manual", "scheduled_artifact_generation", "scheduled_review_surfaces", "gated_apply_helpers", "higher_autonomy_maintenance"}
ALLOWED_TRUST_LEVELS = {"unsafe", "review_required", "automation_ready"}
ALLOWED_DECISIONS = {"approve", "deny", "defer"}
ALLOWED_CONSUMER_POSTURES = {"read_only", "review_only", "blocked"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate and normalize a machine-readable automation trust block."
    )
    parser.add_argument("--input", required=True, help="Path to the trust-block input JSON.")
    parser.add_argument("--write", action="store_true", help="Write normalized result to tmp/automation-trust-block.json or --out.")
    parser.add_argument("--out", help="Optional output path for --write.")
    return parser.parse_args()


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def relpath(path: Path) -> str:
    try:
        return str(path.relative_to(WORKSPACE)).replace("\\", "/")
    except Exception:
        return str(path)


def read_json(path: Path) -> dict[str, Any]:
    data = load_json_artifact(path)
    if not isinstance(data, dict):
        raise SystemExit(f"trust block input must be a JSON object: {path}")
    return data


def nonempty_string(value: Any) -> str:
    return str(value or "").strip()


def normalize_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    out: list[str] = []
    for item in value:
        text = nonempty_string(item)
        if text:
            out.append(text)
    return out


def build_result(payload: dict[str, Any], input_path: Path) -> dict[str, Any]:
    issues: list[str] = []

    workflow = nonempty_string(payload.get("workflow"))
    producer_skill = nonempty_string(payload.get("producer_skill") or "automation-hardening-manager")
    reviewed_at = nonempty_string(payload.get("reviewed_at_utc")) or utc_now_iso()
    current_phase = nonempty_string(payload.get("current_phase"))
    recommended_next_phase = nonempty_string(payload.get("recommended_next_phase"))
    trust_level = nonempty_string(payload.get("trust_level"))
    decision = nonempty_string(payload.get("decision"))
    consumer_posture = nonempty_string(payload.get("consumer_posture"))
    safe_automation_boundary = nonempty_string(payload.get("safe_automation_boundary"))
    owner_layer = nonempty_string(payload.get("owner_layer"))
    review_window = nonempty_string(payload.get("review_window"))
    validation_evidence = normalize_list(payload.get("validation_evidence"))
    trust_gates_passed = normalize_list(payload.get("trust_gates_passed"))
    trust_gates_missing = normalize_list(payload.get("trust_gates_missing"))
    stop_lines = normalize_list(payload.get("stop_lines"))
    notes = normalize_list(payload.get("notes"))

    if not workflow:
        issues.append("workflow missing")
    if current_phase not in ALLOWED_PHASES:
        issues.append(f"current_phase invalid ({current_phase or 'missing'})")
    if recommended_next_phase not in ALLOWED_PHASES:
        issues.append(f"recommended_next_phase invalid ({recommended_next_phase or 'missing'})")
    if trust_level not in ALLOWED_TRUST_LEVELS:
        issues.append(f"trust_level invalid ({trust_level or 'missing'})")
    if decision not in ALLOWED_DECISIONS:
        issues.append(f"decision invalid ({decision or 'missing'})")
    if consumer_posture not in ALLOWED_CONSUMER_POSTURES:
        issues.append(f"consumer_posture invalid ({consumer_posture or 'missing'})")
    if not safe_automation_boundary:
        issues.append("safe_automation_boundary missing")
    if not owner_layer:
        issues.append("owner_layer missing")
    if not review_window:
        issues.append("review_window missing")
    if not stop_lines:
        issues.append("stop_lines missing")

    if decision == "approve" and trust_level != "automation_ready":
        issues.append("approve requires trust_level=automation_ready")
    if decision == "approve" and trust_gates_missing:
        issues.append("approve requires zero missing trust gates")
    if decision == "approve" and consumer_posture != "read_only":
        issues.append("approve requires consumer_posture=read_only")
    if decision in {"deny", "defer"} and consumer_posture == "read_only":
        issues.append(f"{decision} may not expose consumer_posture=read_only")

    status = "ok" if not issues else "blocked"
    stop_line = status != "ok"

    return {
        "status": status,
        "generated_at_utc": utc_now_iso(),
        "input_path": relpath(input_path),
        "trust_block": {
            "schema_version": 1,
            "workflow": workflow,
            "producer_skill": producer_skill,
            "reviewed_at_utc": reviewed_at,
            "current_phase": current_phase,
            "recommended_next_phase": recommended_next_phase,
            "trust_level": trust_level,
            "decision": decision,
            "consumer_posture": consumer_posture,
            "safe_automation_boundary": safe_automation_boundary,
            "owner_layer": owner_layer,
            "review_window": review_window,
            "validation_evidence": validation_evidence,
            "trust_gates_passed": trust_gates_passed,
            "trust_gates_missing": trust_gates_missing,
            "stop_lines": stop_lines,
            "notes": notes,
        },
        "summary": {
            "missing_gate_count": len(trust_gates_missing),
            "passed_gate_count": len(trust_gates_passed),
            "validation_evidence_count": len(validation_evidence),
            "stop_line": stop_line,
        },
        "consumer": {
            "cron_read_allowed": status == "ok",
            "allowed_posture": consumer_posture if status == "ok" else "blocked",
            "fail_closed_reason": "" if status == "ok" else "; ".join(issues),
        },
        "issues": issues,
    }


def main() -> int:
    args = parse_args()
    input_path = Path(args.input)
    if not input_path.is_absolute():
        input_path = WORKSPACE / input_path
    payload = read_json(input_path)
    result = build_result(payload, input_path)

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
