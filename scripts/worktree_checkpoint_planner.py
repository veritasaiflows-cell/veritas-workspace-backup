#!/usr/bin/env python3
"""Plan clean git checkpoints without staging or reverting anything."""
from __future__ import annotations

import argparse
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json
import changed_file_validator_router as validator_router

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
DEFAULT_OUT = TMP / "worktree-checkpoint-planner.json"
SCHEMA = "veritas.worktree_checkpoint_planner.v1"

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "plans_git_staging_only": True,
    "executes_git_add_or_commit": False,
    "reverts_or_deletes_files": False,
    "pushes_external": False,
    "canon_or_portfolio_mutation_allowed": False,
    "config_auth_runtime_mutation_allowed": False,
    "paper_or_live_execution_allowed": False,
    "owner_approval_inferred": False,
}

RISK_PREFIXES = (
    ".openclaw/",
    "03. Portfolio/",
    "state/finance/",
    "data/finance/universe-v1.json",
)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def normalize(path: str) -> str:
    return path.replace("\\", "/").strip().lstrip("./")


def rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def run_git(args: list[str]) -> tuple[int, str, str]:
    completed = subprocess.run(["git", *args], cwd=ROOT, text=True, capture_output=True, check=False)
    return completed.returncode, completed.stdout, completed.stderr


def parse_status_porcelain(text: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in text.splitlines():
        if not line:
            continue
        status = line[:2]
        path = line[3:] if len(line) > 3 else ""
        if " -> " in path:
            old, new = path.split(" -> ", 1)
            path = new
            old_path = old
        else:
            old_path = ""
        rows.append({"status": status, "path": normalize(path), "old_path": normalize(old_path)})
    return rows


def changed_rows(explicit_paths: list[str] | None = None) -> tuple[list[dict[str, Any]], list[str]]:
    if explicit_paths:
        return [{"status": "??", "path": normalize(path), "old_path": ""} for path in explicit_paths], []
    code, stdout, stderr = run_git(["status", "--porcelain"])
    if code != 0:
        return [], [f"git_status_failed:{stderr[:200]}"]
    return parse_status_porcelain(stdout), []


def group_for_path(path: str) -> str:
    lower = path.lower()
    if lower.startswith("scripts/test_") or "/test_" in lower:
        return "tests"
    if lower.startswith("scripts/") and "cron" in lower:
        return "cron_tools"
    if lower.startswith("scripts/") and ("finance" in lower or "wf78" in lower or "wf84" in lower or "wf85" in lower):
        return "finance_tools"
    if lower.startswith("scripts/"):
        return "runtime_tools"
    if lower.startswith("skills/") or lower.endswith("skill.md"):
        return "skills"
    if lower.startswith("memory/") or lower in {"tools.md", "agents.md", "user.md", "soul.md"} or lower.startswith("06. playbooks/"):
        return "continuity_docs"
    if lower.startswith("tmp/"):
        return "generated_proof"
    return "misc"


def risk_for_path(path: str) -> str:
    if any(path.startswith(prefix.lower()) for prefix in [p.lower() for p in RISK_PREFIXES]):
        return "owner_gated_or_sensitive"
    if ".env" in path.lower() or "secret" in path.lower() or "credential" in path.lower():
        return "secret_or_credential_risk"
    if path.startswith("tmp/"):
        return "generated_proof_do_not_commit_by_default"
    return "normal"


def quote_path(path: str) -> str:
    ps = path.replace("/", "\\")
    return f'"{ps}"' if " " in ps else ps


def build_groups(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        path = row["path"]
        groups.setdefault(group_for_path(path), []).append({**row, "risk": risk_for_path(path)})
    result: list[dict[str, Any]] = []
    for name, items in sorted(groups.items()):
        commit_allowed = name != "generated_proof" and not any(item["risk"] != "normal" for item in items)
        paths = [item["path"] for item in items]
        result.append({
            "group": name,
            "path_count": len(paths),
            "commit_allowed_by_default": commit_allowed,
            "paths": paths,
            "risks": sorted({item["risk"] for item in items}),
            "suggested_stage_command": "git add -- " + " ".join(quote_path(path) for path in paths),
        })
    return result


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    rows, warnings = changed_rows(args.path)
    paths = [row["path"] for row in rows]
    groups = build_groups(rows)
    validator_payload = validator_router.build_payload("HEAD", True, paths)
    risky = [path for path in paths if risk_for_path(path) != "normal"]
    return {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "ok",
        "summary": {
            "changed_path_count": len(paths),
            "checkpoint_group_count": len(groups),
            "risky_path_count": len(risky),
            "recommended_validator_budget": validator_payload["summary"]["recommended_budget"],
            "next_safe_action": "Stage one coherent group at a time; do not include tmp proof unless the artifact is intentionally durable.",
        },
        "changed_paths": rows,
        "checkpoint_groups": groups,
        "validator_route": validator_payload["recommendations"],
        "authority_boundary": AUTHORITY_BOUNDARY,
        "validation": {"status": "warning" if warnings else "ok", "errors": [], "warnings": warnings},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--path", action="append", help="Explicit path to plan; may be repeated.")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    payload = build_payload(args)
    out = args.out if args.out.is_absolute() else ROOT / args.out
    if args.write:
        atomic_write_json(out, payload)
    print(
        f"status={payload['status']} paths={payload['summary']['changed_path_count']} "
        f"groups={payload['summary']['checkpoint_group_count']} out={rel(out)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
