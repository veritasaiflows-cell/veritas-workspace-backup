from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json

WORKSPACE = Path(__file__).resolve().parents[1]
SKILL_PATH = WORKSPACE / "skills" / "veritas-technical-pass" / "SKILL.md"
DEFAULT_OUT = WORKSPACE / "tmp" / "veritas-technical-pass-validation.json"

REQUIRED_REFERENCES = [
    "04. Research/Coverage and Watchlist.md",
    "03. Portfolio/Portfolio Snapshot.md",
    "03. Portfolio/Execution Board.md",
    "05. Intelligence/Weekly Positioning Review.md",
    "07. Risk/Risk Rules.md",
]

REQUIRED_STATE_LABELS = ["Deployable", "Blocked", "Repair mode", "Watch-only"]
REQUIRED_DATA_REQUIREMENTS = [
    "current price or latest reliable reference price",
    "20-day, 50-day, and 200-day moving-average posture",
    "nearest meaningful support levels",
    "nearest meaningful resistance levels",
    "whether price is in, above, below, or far from the preferred entry zone",
    "stop or invalidation threshold",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate the local file contract and core output requirements for veritas-technical-pass."
    )
    parser.add_argument("--skill", default=str(SKILL_PATH), help="Path to skills/veritas-technical-pass/SKILL.md")
    parser.add_argument("--write", action="store_true", help="Write the validation result JSON to tmp/ or --out.")
    parser.add_argument("--out", help="Optional output path for --write.")
    return parser.parse_args()


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def relpath(path: Path) -> str:
    try:
        return str(path.relative_to(WORKSPACE)).replace("\\", "/")
    except Exception:
        return str(path)


def check_file(path_str: str) -> dict[str, Any]:
    path = WORKSPACE / path_str
    exists = path.exists()
    return {
        "path": path_str,
        "exists": exists,
        "kind": "file",
        "detail": "ok" if exists else f"missing required file {path_str}",
    }


def section_contains_all(text: str, items: list[str]) -> list[str]:
    missing: list[str] = []
    for item in items:
        if item not in text:
            missing.append(item)
    return missing


def build_result(skill_path: Path) -> dict[str, Any]:
    if not skill_path.exists():
        raise SystemExit(f"skill file missing: {skill_path}")

    text = skill_path.read_text(encoding="utf-8")
    file_checks = [check_file(path_str) for path_str in REQUIRED_REFERENCES]
    missing_files = [item["path"] for item in file_checks if not item["exists"]]

    missing_state_labels = section_contains_all(text, REQUIRED_STATE_LABELS)
    missing_data_requirements = section_contains_all(text, REQUIRED_DATA_REQUIREMENTS)

    issues: list[str] = []
    if missing_files:
        issues.append("missing referenced workspace files")
    if missing_state_labels:
        issues.append("skill no longer names the full four-state technical model")
    if missing_data_requirements:
        issues.append("skill no longer states the minimum data requirements")

    status = "ok" if not issues else "blocked"
    return {
        "status": status,
        "validated_at_utc": utc_now_iso(),
        "skill": "veritas-technical-pass",
        "validation_tier": "Tier 2 functional local proof (pilot)",
        "skill_path": relpath(skill_path),
        "summary": {
            "required_reference_count": len(REQUIRED_REFERENCES),
            "present_reference_count": sum(1 for item in file_checks if item["exists"]),
            "missing_reference_count": len(missing_files),
            "missing_state_label_count": len(missing_state_labels),
            "missing_data_requirement_count": len(missing_data_requirements),
        },
        "required_file_contract": file_checks,
        "required_state_labels": {
            "expected": REQUIRED_STATE_LABELS,
            "missing": missing_state_labels,
        },
        "required_data_requirements": {
            "expected": REQUIRED_DATA_REQUIREMENTS,
            "missing": missing_data_requirements,
        },
        "issues": issues,
        "validator_note": "Bounded sidecar validator pilot: proves the skill's required local file contract and core technical-output contract still exist. This does not validate live market data or end-to-end workflow quality.",
    }


def main() -> int:
    args = parse_args()
    skill_path = Path(args.skill)
    if not skill_path.is_absolute():
        skill_path = WORKSPACE / skill_path

    result = build_result(skill_path)

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
