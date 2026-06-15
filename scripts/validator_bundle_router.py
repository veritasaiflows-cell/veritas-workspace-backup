#!/usr/bin/env python3
"""Pick and optionally run the smallest honest validator bundle."""
from __future__ import annotations

import argparse
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json
import changed_file_validator_router as changed_router

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
DEFAULT_OUT = TMP / "validator-bundle-router.json"
SCHEMA = "veritas.validator_bundle_router.v1"
BUDGET_RANK = changed_router.BUDGET_RANK

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "validator_routing_only": True,
    "executes_only_when_execute_flag_set": True,
    "allowed_command_prefixes": ["python", "openclaw"],
    "canon_or_portfolio_mutation_allowed": False,
    "config_auth_runtime_mutation_allowed": False,
    "archive_or_delete_allowed": False,
    "paper_or_live_execution_allowed": False,
    "owner_approval_inferred": False,
}

BLOCKED_TOKENS = ("&&", "||", ";", "|", ">", "<", "`", "--apply", "--submit", "--cancel", "--promote", "--import")


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def command_allowed(command: str) -> tuple[bool, str]:
    stripped = command.strip()
    first = stripped.split(maxsplit=1)[0].lower() if stripped else ""
    if first not in {"python", "openclaw"}:
        return False, f"prefix_not_allowed:{first}"
    for token in BLOCKED_TOKENS:
        if token in stripped:
            return False, f"blocked_token:{token}"
    return True, "ok"


def select_recommendations(recommendations: list[dict[str, Any]], max_budget: str) -> list[dict[str, Any]]:
    max_rank = BUDGET_RANK[max_budget]
    return [rec for rec in recommendations if BUDGET_RANK.get(rec.get("budget"), 99) <= max_rank]


def run_command(command: str, timeout: int) -> dict[str, Any]:
    ok, reason = command_allowed(command)
    if not ok:
        return {"command": command, "ok": False, "returncode": 97, "blocked_reason": reason}
    completed = subprocess.run(
        command,
        cwd=ROOT,
        shell=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout,
        check=False,
    )
    return {
        "command": command,
        "ok": completed.returncode == 0,
        "returncode": completed.returncode,
        "stdout_tail": (completed.stdout or "")[-2000:],
        "stderr_tail": (completed.stderr or "")[-2000:],
    }


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    route = changed_router.build_payload(args.base, args.include_untracked, args.path)
    max_budget = args.max_budget or route["summary"]["recommended_budget"]
    selected = select_recommendations(route["recommendations"], max_budget)
    command_checks = [{"command": rec["command"], "allowed": command_allowed(rec["command"])[0], "reason": command_allowed(rec["command"])[1]} for rec in selected]
    run_results: list[dict[str, Any]] = []
    errors: list[str] = []
    if args.execute:
        for rec in selected:
            result = run_command(rec["command"], args.timeout_seconds)
            run_results.append(result)
            if not result.get("ok"):
                errors.append(f"validator_failed:{rec['command']}")
                if not args.continue_on_failure:
                    break
    warnings = []
    if not selected:
        warnings.append("no_validators_selected")
    if any(not item["allowed"] for item in command_checks):
        errors.append("selected_command_blocked_by_safety_guard")
    status = "error" if errors else "warning" if warnings else "ok"
    return {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": status,
        "mode": "execute" if args.execute else "plan",
        "summary": {
            "changed_path_count": route["summary"]["changed_path_count"],
            "recommended_budget": route["summary"]["recommended_budget"],
            "selected_budget": max_budget,
            "selected_command_count": len(selected),
            "executed_command_count": len(run_results),
            "failed_command_count": sum(1 for item in run_results if not item.get("ok")),
            "next_safe_action": "Run with --execute when the selected bundle is acceptable." if not args.execute else "Review failed_command_count and rerun only after fixing failures.",
        },
        "changed_file_route": route,
        "selected_validators": selected,
        "command_safety": command_checks,
        "run_results": run_results,
        "authority_boundary": AUTHORITY_BOUNDARY,
        "validation": {"status": "error" if errors else "warning" if warnings else "ok", "errors": errors, "warnings": warnings},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", default="HEAD")
    parser.add_argument("--include-untracked", action="store_true")
    parser.add_argument("--no-untracked", action="store_false", dest="include_untracked")
    parser.set_defaults(include_untracked=True)
    parser.add_argument("--path", action="append")
    parser.add_argument("--max-budget", choices=sorted(BUDGET_RANK, key=BUDGET_RANK.get))
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--continue-on-failure", action="store_true")
    parser.add_argument("--timeout-seconds", type=int, default=900)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    payload = build_payload(args)
    out = args.out if args.out.is_absolute() else ROOT / args.out
    if args.write:
        atomic_write_json(out, payload)
    print(
        f"status={payload['status']} mode={payload['mode']} selected={payload['summary']['selected_command_count']} "
        f"failed={payload['summary']['failed_command_count']} out={rel(out)}"
    )
    if args.validate and payload["validation"]["status"] == "error":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
