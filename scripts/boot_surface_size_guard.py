#!/usr/bin/env python3
"""Report-only guard for OpenClaw boot/control Markdown size.

This checks the small set of files that are intentionally read during startup or
used as live control surfaces. It does not mutate runtime, config, auth,
channels, cron, finance canon, or portfolio state.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
DEFAULT_OUT = TMP / "boot-surface-size-guard.json"


@dataclass(frozen=True)
class Target:
    path: str
    max_bytes: int
    warning_bytes: int
    role: str
    fail_on_over_budget: bool = True
    hard_failure_multiplier: float = 1.5


TARGETS: tuple[Target, ...] = (
    Target("SOUL.md", 12_000, 10_000, "identity and hard boundaries"),
    Target("AGENTS.md", 12_000, 10_000, "startup and orchestration rules"),
    Target("TOOLS.md", 12_000, 10_000, "runtime/tool posture"),
    Target("MEMORY.md", 12_000, 10_000, "curated durable continuity"),
    Target("USER.md", 12_000, 10_000, "Randall preferences"),
    Target("IDENTITY.md", 4_000, 3_000, "short identity mirror"),
    Target("HEARTBEAT.md", 8_000, 6_500, "heartbeat-only behavior"),
    Target("06. Playbooks/Active Workflows.md", 25_000, 22_000, "live workflow control surface"),
    Target("06. Playbooks/Startup Truth Index.md", 12_000, 10_000, "startup routing map"),
    Target("06. Playbooks/Automation Orchestration Protocol.md", 25_000, 22_000, "helper-lane protocol"),
    Target(
        "06. Playbooks/Project Continuity/Workflow 72 - Financial OS Efficiency Restructure and Priority Compression.md",
        90_000,
        70_000,
        "historical continuity watch item; not a startup surface",
        False,
    ),
    Target(
        "06. Playbooks/Project Continuity/Workflow 73 - Queue Index and Boot Surface Optimization.md",
        35_000,
        28_000,
        "active WF73 continuity",
        False,
    ),
)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def inspect_target(target: Target) -> dict[str, Any]:
    path = ROOT / target.path
    exists = path.exists()
    size = path.stat().st_size if exists else None
    over_budget = bool(exists and size is not None and size > target.max_bytes)
    warning = bool(exists and size is not None and size > target.warning_bytes)
    hard_failure_bytes = int(target.max_bytes * target.hard_failure_multiplier)
    over_hard_failure_limit = bool(
        target.fail_on_over_budget and exists and size is not None and size > hard_failure_bytes
    )
    status = "missing" if not exists else "over_budget" if over_budget else "warning" if warning else "ok"
    return {
        "path": target.path,
        "role": target.role,
        "exists": exists,
        "size_bytes": size,
        "warning_bytes": target.warning_bytes,
        "max_bytes": target.max_bytes,
        "hard_failure_bytes": hard_failure_bytes if target.fail_on_over_budget else None,
        "fail_on_over_budget": target.fail_on_over_budget,
        "over_hard_failure_limit": over_hard_failure_limit,
        "status": status,
        "sha256": sha256(path) if exists else None,
    }


def build_report() -> dict[str, Any]:
    files = [inspect_target(target) for target in TARGETS]
    hard_failures = [
        item
        for item in files
        if (
            item["status"] == "missing" and item.get("fail_on_over_budget") is True
        )
        or (
            item["status"] == "over_budget"
            and item.get("fail_on_over_budget") is True
            and item.get("over_hard_failure_limit") is True
        )
    ]
    warnings = [item for item in files if item["status"] in {"warning", "over_budget"}]
    total_boot_bytes = sum(
        item["size_bytes"] or 0
        for item in files
        if item["exists"] and "Project Continuity" not in item["path"]
    )
    return {
        "generated_at_utc": utc_now(),
        "status": "blocked" if hard_failures else "warning" if warnings else "ok",
        "report_only": True,
        "mutations_performed": False,
        "authority_boundary": (
            "Read-only bootstrap/control-surface size guard. No config/auth/channel/service/runtime, "
            "finance canon, portfolio, SQL-canon, archive, delete, move, trade, account, paper, or live authority."
        ),
        "policy": {
            "hard_fail": "core startup/control files missing or above the hard failure ceiling",
            "warning": "file above warning_bytes/max_bytes or continuity watch item above budget",
            "soft_over_budget_policy": (
                "Core boot/control files above max_bytes but below hard_failure_bytes are warning-only; "
                "they should drive compaction work without making WF73 red."
            ),
            "continuity_watch_items_do_not_fail_validation": True,
            "next_action_on_warning": "compact or split historical proof tails into owner continuity/proof artifacts; keep live control files route-only",
        },
        "counts": {
            "files_checked": len(files),
            "warnings": len(warnings),
            "hard_failures": len(hard_failures),
            "total_boot_control_bytes_excluding_project_continuity": total_boot_bytes,
        },
        "files": files,
        "hard_failures": [{"path": item["path"], "status": item["status"], "size_bytes": item["size_bytes"], "max_bytes": item["max_bytes"]} for item in hard_failures],
        "warnings": [{"path": item["path"], "status": item["status"], "size_bytes": item["size_bytes"], "warning_bytes": item["warning_bytes"], "max_bytes": item["max_bytes"]} for item in warnings],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Report-only boot/control Markdown size guard")
    parser.add_argument("--write", action="store_true", help=f"Write {DEFAULT_OUT.as_posix()}")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--validate", action="store_true", help="Return nonzero only for hard startup/control failures")
    parser.add_argument("--strict-warnings", action="store_true", help="Return nonzero for warnings too")
    args = parser.parse_args()

    report = build_report()
    if args.write:
        atomic_write_json(args.output, report, indent=2, ensure_ascii=True)
    else:
        print(json.dumps(report, indent=2, sort_keys=True))

    print(
        "status={status} hard_failures={hard} warnings={warnings} total_boot_control_bytes={total} output={output}".format(
            status=report["status"],
            hard=report["counts"]["hard_failures"],
            warnings=report["counts"]["warnings"],
            total=report["counts"]["total_boot_control_bytes_excluding_project_continuity"],
            output=args.output.as_posix() if args.write else "stdout",
        )
    )

    if args.validate and report["counts"]["hard_failures"]:
        return 1
    if args.validate and args.strict_warnings and report["counts"]["warnings"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
