#!/usr/bin/env python3
"""Explain why generated artifacts look stale and who should refresh them."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, load_json_artifact

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
DEFAULT_OUT = TMP / "artifact-staleness-explainer.json"
SCHEMA = "veritas.artifact_staleness_explainer.v1"

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "explains_staleness_only": True,
    "refreshes_artifacts": False,
    "cron_state_mutation_allowed": False,
    "canon_or_portfolio_mutation_allowed": False,
    "paper_or_live_execution_allowed": False,
    "owner_approval_inferred": False,
}

PRODUCER_RULES = [
    ("cron-control-packet.json", "cron_control_packet.py", "python scripts\\cron_control_packet.py --write --validate", "cron"),
    ("cron-freshness-spine.json", "cron_freshness_spine.py", "python scripts\\cron_freshness_spine.py --write --validate", "cron"),
    ("pm-control-packet.json", "pm_control_packet.py", "python scripts\\pm_control_packet.py --write --write-db --validate", "pm"),
    ("fast-path-qa.json", "fast_path_qa.py", "python scripts\\fast_path_qa.py --write --validate", "runtime"),
    ("truth-surface-inventory.json", "truth_surface_inventory.py", "python scripts\\truth_surface_inventory.py --write --validate", "runtime"),
    ("workflow-routing-index.json", "workflow_router.py", "python scripts\\workflow_router.py --all --write-capsules --validate", "workflow"),
    ("concurrent-lane-register.json", "concurrent_lane_manager.py", "python scripts\\concurrent_lane_manager.py --status --write --validate", "runtime"),
    ("wf78-daily-freshness-cron-runner.json", "wf78_daily_freshness_cron_runner.py", "python scripts\\wf78_daily_freshness_cron_runner.py --write --validate", "finance"),
    ("trade-grade-full-answer-assembler.json", "trade_grade_full_answer_assembler.py", "python scripts\\trade_grade_full_answer_assembler.py --all-wf84 --write --validate", "finance"),
]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_utc(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def producer_for(path: Path) -> dict[str, str]:
    name = path.name
    for suffix, owner, command, domain in PRODUCER_RULES:
        if name == suffix or name.endswith(suffix):
            return {"owner": owner, "refresh_command": command, "domain": domain}
    stem = name.replace("-", "_").replace(".json", ".py")
    candidate = ROOT / "scripts" / stem
    if candidate.exists():
        return {"owner": stem, "refresh_command": f"python scripts\\{stem} --write --validate", "domain": "inferred"}
    return {"owner": "unknown", "refresh_command": "Use artifact_index.py latest or inspect script README owner route.", "domain": "unknown"}


def artifact_generated_at(payload: Any) -> str | None:
    if not isinstance(payload, dict):
        return None
    for key in ("generated_at_utc", "updated_at_utc", "created_at_utc"):
        if payload.get(key):
            return str(payload.get(key))
    return None


def explain_artifact(path: Path, max_age_hours: float) -> dict[str, Any]:
    target = path if path.is_absolute() else ROOT / path
    info = producer_for(target)
    exists = target.exists()
    payload = load_json_artifact(target) if exists else None
    generated_at = artifact_generated_at(payload)
    generated_dt = parse_utc(generated_at)
    mtime_dt = datetime.fromtimestamp(target.stat().st_mtime, tz=timezone.utc) if exists else None
    reference_dt = generated_dt or mtime_dt
    age_hours = None
    if reference_dt:
        age_hours = round((datetime.now(timezone.utc) - reference_dt).total_seconds() / 3600, 2)
    artifact_status = as_dict(payload).get("status") if isinstance(payload, dict) else "missing" if not exists else "unreadable"
    source_refs = []
    if isinstance(payload, dict):
        sources = payload.get("sources")
        if isinstance(sources, dict):
            source_refs = [str(value) for value in sources.values() if isinstance(value, (str, int, float))]
        elif isinstance(sources, list):
            source_refs = [str(value) for value in sources if isinstance(value, (str, int, float))]
    stale = (age_hours is None) or age_hours > max_age_hours
    reason = "missing" if not exists else "unreadable_json" if payload is None else "older_than_threshold" if stale else "fresh_enough"
    return {
        "artifact": rel(target),
        "exists": exists,
        "status": artifact_status,
        "generated_at_utc": generated_at,
        "file_mtime_utc": mtime_dt.replace(microsecond=0).isoformat().replace("+00:00", "Z") if mtime_dt else None,
        "age_hours": age_hours,
        "max_age_hours": max_age_hours,
        "stale": stale,
        "reason": reason,
        "owner": info["owner"],
        "domain": info["domain"],
        "refresh_command": info["refresh_command"],
        "source_refs": source_refs[:20],
        "validation_warnings": as_list(as_dict(as_dict(payload).get("validation")).get("warnings")) if isinstance(payload, dict) else [],
        "validation_errors": as_list(as_dict(as_dict(payload).get("validation")).get("errors")) if isinstance(payload, dict) else [],
    }


def default_artifacts() -> list[Path]:
    return [
        TMP / "cron-control-packet.json",
        TMP / "pm-control-packet.json",
        TMP / "fast-path-qa.json",
        TMP / "concurrent-lane-register.json",
    ]


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    artifacts = args.artifact or default_artifacts()
    rows = [explain_artifact(path, args.max_age_hours) for path in artifacts]
    stale_count = sum(1 for row in rows if row["stale"])
    missing_count = sum(1 for row in rows if not row["exists"])
    status = "warning" if stale_count or missing_count else "ok"
    return {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": status,
        "summary": {
            "artifact_count": len(rows),
            "stale_count": stale_count,
            "missing_count": missing_count,
            "next_safe_action": "Run the listed refresh_command for stale artifacts, then rerun this explainer.",
        },
        "artifacts": rows,
        "authority_boundary": AUTHORITY_BOUNDARY,
        "validation": {"status": status, "errors": [], "warnings": ["stale_or_missing_artifacts_present"] if status == "warning" else []},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact", type=Path, action="append")
    parser.add_argument("--max-age-hours", type=float, default=24.0)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    payload = build_payload(args)
    out = args.out if args.out.is_absolute() else ROOT / args.out
    if args.write:
        atomic_write_json(out, payload)
    print(
        f"status={payload['status']} artifacts={payload['summary']['artifact_count']} "
        f"stale={payload['summary']['stale_count']} out={rel(out)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
