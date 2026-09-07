#!/usr/bin/env python3
"""Index only the active alerts-and-recommendations proof chain by window."""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, atomic_write_text, load_json_artifact


ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
OUT_JSON = TMP / "current-window-artifacts.json"
OUT_MD = OUT_JSON.with_suffix(".md")
WINDOW_ALIASES = {"full": "post-close", "sunday": "weekly"}
WINDOWS = ("morning", "midday", "post-close", "weekly")

COMMON_ARTIFACTS = {
    "finance_sql_guard": "tmp/finance-sql-canon-access-validation.json",
    "quote_snapshot": "tmp/intraday-alerts/quote-snapshot-proof.json",
    "quote_snapshot_validation": "tmp/intraday-alerts/quote-snapshot-proof-validation.json",
    "alert_freshness_controller": "tmp/alert-level-freshness-controller.json",
    "alerts_os_boundary": "tmp/alerts-os-pivot-validator.json",
}


def iso_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def normalize_window(window: str) -> str:
    return WINDOW_ALIASES.get(window, window)


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def artifact_status(payload: dict[str, Any]) -> str:
    value = str(payload.get("status") or as_dict(payload.get("validation")).get("status") or "unknown").lower()
    if value in {"ok", "sent", "weekend_quiet", "duplicate_quiet"}:
        return "ok"
    if value in {"warning", "monitor_only", "stale_input_warning"}:
        return "warning"
    return "error" if value in {"error", "critical", "blocked", "failed"} else "unknown"


def artifact_record(role: str, relative_path: str, *, required: bool = True) -> dict[str, Any]:
    path = ROOT / relative_path
    payload = load_json_artifact(path) if path.is_file() and path.suffix.lower() == ".json" else None
    payload = payload if isinstance(payload, dict) else {}
    generated = payload.get("generated_at_utc")
    if not generated and path.is_file():
        generated = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    return {
        "role": role,
        "path": relative_path,
        "required": required,
        "exists": path.is_file(),
        "status": artifact_status(payload) if path.is_file() else "missing",
        "generated_at_utc": generated,
    }


def build_index(window: str) -> dict[str, Any]:
    selected = normalize_window(window)
    if selected not in WINDOWS:
        raise ValueError(f"unsupported alerts OS window: {window}")
    paths = dict(COMMON_ARTIFACTS)
    paths["alerts_recommendations_chain"] = f"tmp/alerts-recommendations-chain-{selected}.json"
    paths["recommendation_digest"] = f"tmp/finance-alert-os-{selected}-digest.json"
    records = [artifact_record(role, path) for role, path in paths.items()]
    missing = [row["role"] for row in records if row["required"] and not row["exists"]]
    failed = [row["role"] for row in records if row["required"] and row["status"] not in {"ok", "warning"}]
    status = "ok" if not missing and not failed else "error"
    return {
        "schema": "veritas.alerts_os_current_window_index.v1",
        "generated_at_utc": iso_now(),
        "window": selected,
        "status": status,
        "purpose": "bounded index of active alert, freshness, and non-executing recommendation proofs",
        "authority": {
            "review_only": True,
            "writes_canon": False,
            "maintains_finance_state": False,
            "maintains_simulated_state": False,
            "capital_or_execution_authority": False,
            "owner_approval_inferred": False,
        },
        "summary": {
            "artifact_count": len(records),
            "existing_artifact_count": sum(1 for row in records if row["exists"]),
            "missing_required_roles": missing,
            "failed_required_roles": failed,
            "current_usable": status == "ok",
        },
        "role_aliases": {row["role"]: row["path"] for row in records if row["exists"]},
        "artifacts": records,
        "rendered_outputs": {"json": "tmp/current-window-artifacts.json"},
        "validation": {"status": status, "errors": [*missing, *failed], "warnings": []},
    }


def render_md(index: dict[str, Any]) -> str:
    lines = [
        "# Alerts OS Current-Window Artifact Index",
        "",
        f"- Generated: `{index['generated_at_utc']}`",
        f"- Window: `{index['window']}`",
        f"- Status: **{index['status']}**",
        "- Boundary: review-only alerts and non-executing recommendation proof",
        "",
        "| Role | Status | Exists | Path |",
        "|---|---|---:|---|",
    ]
    for row in index["artifacts"]:
        lines.append(f"| `{row['role']}` | {row['status']} | {str(row['exists']).lower()} | `{row['path']}` |")
    return "\n".join(lines) + "\n"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--window", default="post-close", choices=[*WINDOWS, *WINDOW_ALIASES])
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--write-md", action="store_true")
    parser.add_argument("--validate", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    payload = build_index(args.window)
    if args.write:
        atomic_write_json(OUT_JSON, payload, indent=2)
        if args.write_md:
            atomic_write_text(OUT_MD, render_md(payload))
    print(json.dumps({
        "status": payload["status"],
        "window": payload["window"],
        "artifact_count": payload["summary"]["artifact_count"],
        "output": "tmp/current-window-artifacts.json",
    }, indent=2))
    return 1 if args.validate and payload["status"] != "ok" else 0


if __name__ == "__main__":
    raise SystemExit(main())
