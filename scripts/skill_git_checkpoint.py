#!/usr/bin/env python3
"""Create or validate a targeted local git checkpoint for workspace skills.

The default mode is report-only. Use --commit when the owner explicitly wants a
local checkpoint; the script stages only the skill/governance/memory surfaces it
owns, never the whole workspace.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from market_data_utils import atomic_write_json

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "tmp" / "skill-git-checkpoint.json"
PHOENIX = ZoneInfo("America/Phoenix")

SCHEMA = "veritas.skill_git_checkpoint.v1"
SKILL_ROOT = ROOT / "skills"
FIXED_PATHS = [
    "skills",
    "06. Playbooks/Skills Governance Index.md",
]

AUTHORITY_BOUNDARY = {
    "local_git_only": True,
    "stages_entire_workspace": False,
    "external_push_allowed": False,
    "network_action_allowed": False,
    "skill_body_mutation_allowed": False,
    "portfolio_or_canon_mutation_allowed": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "owner_approval_inferred": False,
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def today_memory_path() -> str:
    today = datetime.now(PHOENIX).date().isoformat()
    return f"memory/{today}.md"


def run_git(args: list[str]) -> tuple[int, str, str]:
    proc = subprocess.run(["git", *args], cwd=ROOT, text=True, capture_output=True, check=False)
    return proc.returncode, proc.stdout.strip(), proc.stderr.strip()


def lines(text: str) -> list[str]:
    return [line.strip() for line in text.splitlines() if line.strip()]


def skill_dirs() -> list[str]:
    if not SKILL_ROOT.exists():
        return []
    return sorted(path.name for path in SKILL_ROOT.iterdir() if path.is_dir())


def tracked_skill_dirs() -> list[str]:
    code, out, _ = run_git(["ls-files", "skills"])
    if code != 0:
        return []
    names: set[str] = set()
    for item in lines(out):
        parts = Path(item).parts
        if len(parts) >= 2 and parts[0] == "skills":
            names.add(parts[1])
    return sorted(names)


def git_status(paths: list[str]) -> list[str]:
    code, out, err = run_git(["status", "--short", "--", *paths])
    if code != 0:
        return [f"git_status_failed:{err[:200]}"]
    return lines(out)


def latest_commit() -> dict[str, str | None]:
    code, out, _ = run_git(["log", "-1", "--date=iso", "--pretty=format:%H%n%ad%n%s"])
    if code != 0 or not out:
        return {"hash": None, "date": None, "subject": None}
    parts = out.splitlines()
    return {
        "hash": parts[0] if len(parts) > 0 else None,
        "date": parts[1] if len(parts) > 1 else None,
        "subject": parts[2] if len(parts) > 2 else None,
    }


def build_paths(include_today_memory: bool = True) -> list[str]:
    paths = list(FIXED_PATHS)
    if include_today_memory:
        paths.append(today_memory_path())
    return paths


def build_payload(include_today_memory: bool = True) -> dict[str, object]:
    live_skills = skill_dirs()
    tracked = tracked_skill_dirs()
    untracked_skill_dirs = sorted(set(live_skills) - set(tracked))
    tracked_missing_live = sorted(set(tracked) - set(live_skills))
    paths = build_paths(include_today_memory)
    status_lines = git_status(paths)
    payload = {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "ok" if not untracked_skill_dirs and not tracked_missing_live else "warning",
        "authority_boundary": AUTHORITY_BOUNDARY,
        "summary": {
            "skill_dirs": len(live_skills),
            "tracked_skill_dirs": len(tracked),
            "untracked_skill_dirs": len(untracked_skill_dirs),
            "tracked_missing_live": len(tracked_missing_live),
            "path_status_count": len(status_lines),
            "latest_commit": latest_commit(),
        },
        "checkpoint_paths": paths,
        "untracked_skill_dirs": untracked_skill_dirs,
        "tracked_missing_live": tracked_missing_live,
        "path_status": status_lines,
        "stop_lines": [
            "This helper stages only skills, Skills Governance Index, and today's memory file when --commit is used.",
            "It never pushes externally and never mutates live skill content.",
        ],
        "recommended_use": [
            "Run report mode before and after Skill Workshop apply or bulk skill edits.",
            "Use --commit --tag-name <name> for an explicit local checkpoint after validation passes.",
        ],
    }
    return payload


def ensure_clean_cached(paths: list[str]) -> tuple[bool, list[str]]:
    code, out, err = run_git(["diff", "--cached", "--check", "--", *paths])
    messages = lines(out) + lines(err)
    return code == 0, messages


def create_checkpoint(message: str, tag_name: str | None, include_today_memory: bool) -> tuple[int, dict[str, object]]:
    paths = build_paths(include_today_memory)
    code, _, err = run_git(["add", "-A", "--", *paths])
    if code != 0:
        return 1, {"error": f"git_add_failed:{err[:500]}"}
    clean, messages = ensure_clean_cached(paths)
    if not clean:
        return 1, {"error": "git_diff_check_failed", "messages": messages}
    code, staged, err = run_git(["diff", "--cached", "--name-only", "--", *paths])
    if code != 0:
        return 1, {"error": f"git_cached_diff_failed:{err[:500]}"}
    staged_paths = lines(staged)
    if not staged_paths:
        return 0, {"committed": False, "reason": "no staged skill checkpoint changes"}
    code, out, err = run_git(["commit", "-m", message])
    if code != 0:
        return 1, {"error": f"git_commit_failed:{err[:500] or out[:500]}"}
    commit_hash = latest_commit()["hash"]
    tag_result: dict[str, object] = {"created": False}
    if tag_name:
        code, _, err = run_git(["tag", "-a", tag_name, str(commit_hash), "-m", message])
        if code != 0:
            return 1, {"error": f"git_tag_failed:{err[:500]}", "commit": commit_hash}
        tag_result = {"created": True, "name": tag_name}
    return 0, {
        "committed": True,
        "commit": commit_hash,
        "staged_path_count": len(staged_paths),
        "staged_paths": staged_paths,
        "tag": tag_result,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate or create a targeted local git checkpoint for workspace skills.")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--commit", action="store_true", help="Stage owned skill checkpoint paths and create a local git commit.")
    parser.add_argument("--message", default="Checkpoint workspace skills")
    parser.add_argument("--tag-name", help="Optional annotated local tag to create after a successful commit.")
    parser.add_argument("--no-today-memory", action="store_false", dest="include_today_memory")
    parser.add_argument("--out", type=Path, default=OUT)
    args = parser.parse_args()

    action_result: dict[str, object] | None = None
    exit_code = 0
    if args.commit:
        exit_code, action_result = create_checkpoint(args.message, args.tag_name, args.include_today_memory)
    payload = build_payload(args.include_today_memory)
    if action_result is not None:
        payload["checkpoint_action"] = action_result
        if exit_code != 0:
            payload["status"] = "blocked"
            payload["validation"] = {"status": "blocked", "errors": [action_result], "warnings": []}
        else:
            payload["validation"] = {"status": "ok", "errors": [], "warnings": []}
    else:
        payload["validation"] = {
            "status": "ok" if payload["status"] == "ok" else "warning",
            "errors": [],
            "warnings": [] if payload["status"] == "ok" else ["untracked_or_missing_skill_dirs"],
        }
    if args.write:
        atomic_write_json(args.out, payload)
        summary = payload["summary"]
        print(
            "wrote "
            + str(args.out.relative_to(ROOT))
            + f" status={payload['status']} tracked={summary['tracked_skill_dirs']}/{summary['skill_dirs']}"
        )
    else:
        print(json.dumps(payload["summary"], indent=2, sort_keys=True))
    if args.validate and payload["validation"]["status"] not in {"ok", "warning"}:
        return 1
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
