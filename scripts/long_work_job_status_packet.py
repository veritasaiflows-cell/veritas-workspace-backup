#!/usr/bin/env python3
"""Write the workspace-wide long-work job status packet."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import long_work_job_runtime as runtime


ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
OUT = TMP / "long-work-job-status-packet.json"
MD_OUT = TMP / "long-work-job-status-packet.md"


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def render_markdown(packet: dict[str, Any]) -> str:
    summary = as_dict(packet.get("summary"))
    lines = [
        "# Long Work Job Status Packet",
        "",
        "Status: review-only runtime map",
        "Owner workflow: RUNTIME",
        "Authority boundary: checkpoint/status only; no canon, portfolio, cron schedule, runtime config, execution, external delivery, delete/archive, or owner approval authority.",
        "",
        "## Summary",
        "",
        f"- Status: `{packet.get('status')}`",
        f"- Jobs: `{summary.get('job_count')}`",
        f"- Active jobs: `{summary.get('active_job_count')}`",
        f"- Resumable jobs: `{summary.get('resumable_job_count')}`",
        f"- Blocked jobs: `{summary.get('blocked_job_count')}`",
        f"- Stale active jobs: `{summary.get('stale_active_job_count')}`",
        f"- Next safe action: {summary.get('next_safe_action')}",
        "",
        "## Jobs",
        "",
    ]
    for row in as_list(packet.get("jobs")):
        compact = as_dict(as_dict(row).get("compact_status"))
        lines.append(
            f"- `{compact.get('job_id')}`: `{compact.get('status')}` "
            f"{compact.get('processed_units')}/{compact.get('total_units')} "
            f"({compact.get('percent_complete')}%) - `{compact.get('next_resume_command')}`"
        )
    lines.extend([
        "",
        "## Boundary",
        "",
        "- Status packets may route work to WF74/WF88 or a main-session resume command.",
        "- They do not grant apply, cron mutation, config/runtime mutation, finance/canon mutation, paper/live execution, external delivery, or approval authority.",
        "",
    ])
    return "\n".join(lines)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--write-md", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--pretty", action="store_true")
    parser.add_argument("--out", type=Path, default=OUT)
    parser.add_argument("--md-out", type=Path, default=MD_OUT)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    packet = runtime.build_status_packet()
    out = args.out if args.out.is_absolute() else ROOT / args.out
    md_out = args.md_out if args.md_out.is_absolute() else ROOT / args.md_out
    if args.write:
        runtime.atomic_write_json(out, packet)
    if args.write_md:
        runtime.atomic_write_json(out, packet) if args.write is False else None
        md_out.parent.mkdir(parents=True, exist_ok=True)
        md_out.write_text(render_markdown(packet), encoding="utf-8")
    print(json.dumps(packet if args.pretty else {"status": packet.get("status"), "summary": packet.get("summary"), "validation": packet.get("validation")}, indent=2, sort_keys=True))
    if args.validate and as_dict(packet.get("validation")).get("status") == "blocked":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
