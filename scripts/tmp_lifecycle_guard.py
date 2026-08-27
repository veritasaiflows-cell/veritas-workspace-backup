#!/usr/bin/env python3
"""Preview-only tmp artifact lifecycle guard.

This script classifies tmp/ artifact sprawl and stale proof files. It never
archives or deletes; any cleanup apply remains a separate owner-gated action.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, load_json_artifact

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
OUT = TMP / "tmp-lifecycle-guard.json"
SPIRE_OUT = TMP / "tmp-artifact-spire.json"
SCHEMA = "veritas.tmp_lifecycle_guard.v1"

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "preview_only": True,
    "archive_allowed": False,
    "delete_allowed": False,
    "move_allowed": False,
    "cron_schedule_mutation_allowed": False,
    "config_auth_runtime_mutation_allowed": False,
    "canon_or_portfolio_mutation_allowed": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "owner_approval_inferred": False,
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def load(path: Path) -> dict[str, Any]:
    payload = load_json_artifact(path)
    return payload if isinstance(payload, dict) else {}


def referenced_tmp_paths() -> set[str]:
    references: set[str] = set()
    for packet in (TMP / "cron-control-packet.json", TMP / "cron-freshness-spine.json"):
        payload = load(packet)
        jobs = as_list(as_dict(payload.get("freshness")).get("jobs")) or as_list(payload.get("jobs"))
        for job in jobs:
            for artifact in as_list(as_dict(job).get("expected_artifacts")):
                path = as_dict(artifact).get("path")
                if isinstance(path, str) and path.startswith("tmp/"):
                    references.add(path.replace("\\", "/"))
    return references


def file_age_days(path: Path, now: datetime) -> float:
    return max(0.0, (now.timestamp() - path.stat().st_mtime) / 86400.0)


def classify_file(path: Path, now: datetime, references: set[str], stale_days: int) -> dict[str, Any]:
    age_days = round(file_age_days(path, now), 3)
    relative = rel(path)
    protected_reasons: list[str] = []
    if relative in references:
        protected_reasons.append("referenced_by_cron_contract")
    if path.suffix.lower() in {".sqlite", ".db"}:
        protected_reasons.append("database_requires_owner_review")
    if age_days < stale_days:
        protected_reasons.append("fresh_within_stale_window")
    eligible = not protected_reasons and path.suffix.lower() in {".json", ".md", ".txt", ".html"}
    return {
        "path": relative,
        "suffix": path.suffix.lower(),
        "size_bytes": path.stat().st_size,
        "last_write_utc": datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "age_days": age_days,
        "stale": age_days >= stale_days,
        "cleanup_preview_eligible": eligible,
        "protected_reasons": protected_reasons,
    }


def build_payload(*, stale_days: int = 14, sample_limit: int = 50) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    references = referenced_tmp_paths()
    files = [path for path in TMP.rglob("*") if path.is_file()]
    json_files = [path for path in files if path.suffix.lower() == ".json"]
    wf78_json = [path for path in json_files if path.name.startswith("wf78-")]
    stale_json = [path for path in json_files if file_age_days(path, now) >= stale_days]
    classified = [classify_file(path, now, references, stale_days) for path in files]
    eligible = [row for row in classified if row["cleanup_preview_eligible"]]
    eligible.sort(key=lambda row: (-float(row["age_days"]), -int(row["size_bytes"]), row["path"]))
    total_bytes = sum(path.stat().st_size for path in files)
    warnings: list[str] = []
    if len(stale_json) > 50:
        warnings.append("stale_tmp_json_count_above_target")
    if len(wf78_json) > 60:
        warnings.append("wf78_tmp_json_count_above_target")
    if total_bytes > 500 * 1024 * 1024:
        warnings.append("tmp_size_above_target")
    payload = {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "warning" if warnings else "ok",
        "purpose": "Preview-only tmp artifact lifecycle classifier; no cleanup is applied.",
        "authority_boundary": AUTHORITY_BOUNDARY,
        "parameters": {
            "stale_days": stale_days,
            "sample_limit": sample_limit,
            "target_stale_json_count": 50,
            "target_wf78_json_count": 60,
            "target_tmp_size_mb": 500,
        },
        "summary": {
            "tmp_file_count": len(files),
            "tmp_json_count": len(json_files),
            "tmp_total_mb": round(total_bytes / (1024 * 1024), 2),
            "tmp_json_older_than_stale_days": len(stale_json),
            "wf78_json_count": len(wf78_json),
            "sqlite_file_count": len([path for path in files if path.suffix.lower() in {".sqlite", ".db"}]),
            "cleanup_preview_eligible_count": len(eligible),
            "referenced_tmp_path_count": len(references),
            "next_safe_action": "Review cleanup_preview_eligible samples; archive/delete still requires separate owner-gated preview/apply approval.",
        },
        "cleanup_preview_samples": eligible[:sample_limit],
        "referenced_tmp_paths_sample": sorted(references)[:sample_limit],
        "validation": {"status": "ok", "errors": [], "warnings": warnings},
        "stop_lines": [
            "This packet does not delete, move, archive, or mutate files.",
            "Any cleanup apply requires separate preview, owner approval, backup/rollback, and validation.",
        ],
    }
    return payload


def spire_from_payload(payload: dict[str, Any]) -> dict[str, Any]:
    summary = as_dict(payload.get("summary"))
    return {
        "schema": "veritas.tmp_artifact_spire.v1",
        "generated_at_utc": payload.get("generated_at_utc"),
        "status": payload.get("status"),
        "summary": {
            "tmp_json_count": summary.get("tmp_json_count"),
            "tmp_total_mb": summary.get("tmp_total_mb"),
            "stale_json_count": summary.get("tmp_json_older_than_stale_days"),
            "wf78_json_count": summary.get("wf78_json_count"),
            "cleanup_preview_eligible_count": summary.get("cleanup_preview_eligible_count"),
        },
        "authority_boundary": AUTHORITY_BOUNDARY,
        "next_safe_action": summary.get("next_safe_action"),
        "validation": payload.get("validation"),
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stale-days", type=int, default=14)
    parser.add_argument("--sample-limit", type=int, default=50)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--pretty", action="store_true")
    parser.add_argument("--out", type=Path, default=OUT)
    parser.add_argument("--spire-out", type=Path, default=SPIRE_OUT)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    payload = build_payload(stale_days=args.stale_days, sample_limit=args.sample_limit)
    out = args.out if args.out.is_absolute() else ROOT / args.out
    spire_out = args.spire_out if args.spire_out.is_absolute() else ROOT / args.spire_out
    if args.write:
        atomic_write_json(out, payload)
        atomic_write_json(spire_out, spire_from_payload(payload))
    if args.pretty:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(json.dumps({
            "status": payload.get("status"),
            "summary": payload.get("summary"),
            "out": rel(out) if args.write else None,
            "spire_out": rel(spire_out) if args.write else None,
        }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
