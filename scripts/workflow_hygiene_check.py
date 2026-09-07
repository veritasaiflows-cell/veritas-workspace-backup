#!/usr/bin/env python3
"""Report-only hygiene check for live workflow truth surfaces.

This validator checks that Active Workflows, WF72/WF73 continuity, and the
latest boot-size proof preserve the current queue and alerts-OS authority
boundaries. It does not mutate any inspected surface.
"""
from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
DEFAULT_OUT = TMP / "workflow-hygiene-check.json"

ACTIVE_WORKFLOWS = ROOT / "06. Playbooks" / "Active Workflows.md"
WF72 = ROOT / "06. Playbooks" / "Project Continuity" / "Workflow 72 - Guarded Finance SQL Canon.md"
WF73 = ROOT / "06. Playbooks" / "Project Continuity" / "Workflow 73 - Queue Index and Boot Surface Optimization.md"
BOOT_GUARD = TMP / "boot-surface-size-guard.json"

REQUIRED_ACTIVE_LANES: tuple[str, ...] = (
    "WF72",
    "WF73",
    "WF70/WF66",
    "WF77",
    "WF79-SMB",
    "WF84",
    "WF85",
    "WF88",
    "WF71",
    "WF74",
    "WF69",
)

STOP_LINE_CHECKS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("no_account_order_execution", ("no capital, account, order, or execution",)),
    ("no_portfolio_state_maintenance", ("no portfolio construction/state maintenance",)),
    (
        "no_config_auth_channel_service_runtime_without_approval",
        ("no config/auth/channel/service/runtime mutation without approval",),
    ),
    (
        "generated_artifact_dashboard_sql_no_approval_execution",
        ("no generated artifact", "dashboard", "SQL row", "approval", "execution authority"),
    ),
    ("no_sql_canon_expansion_beyond_gates", ("no SQL-canon expansion beyond exact",)),
)

STOP_LINE_ALTERNATIVES: dict[str, tuple[tuple[str, ...], ...]] = {
    "no_account_order_execution": (
        ("no portfolio construction/state maintenance", "no paper/live trading", "account action", "money movement"),
        ("no operational paper/live route", "account access", "order generation", "execution"),
    ),
    "no_sql_canon_expansion_beyond_gates": (
        ("canon/import/apply authority",),
        ("SQL/JSON structured canon owner", "approved field families"),
    ),
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def section_between(text: str, start_heading: str, next_heading_pattern: str = r"^## ") -> str:
    start = text.find(start_heading)
    if start < 0:
        return ""
    body_start = start + len(start_heading)
    match = re.search(next_heading_pattern, text[body_start:], re.MULTILINE)
    if not match:
        return text[body_start:]
    return text[body_start : body_start + match.start()]


def top_next_action(text: str) -> str:
    return section_between(text, "## Next Action")


def add_finding(findings: list[dict[str, Any]], severity: str, check: str, message: str, **extra: Any) -> None:
    payload: dict[str, Any] = {"severity": severity, "check": check, "message": message}
    payload.update(extra)
    findings.append(payload)


def contains_all(text: str, needles: tuple[str, ...]) -> bool:
    lowered = text.lower()
    return all(needle.lower() in lowered for needle in needles)


def stop_line_present(text: str, check: str, needles: tuple[str, ...]) -> bool:
    if contains_all(text, needles):
        return True
    return any(contains_all(text, alternative) for alternative in STOP_LINE_ALTERNATIVES.get(check, ()))


def compact_slashes(text: str) -> str:
    return re.sub(r"\s*/\s*", "/", text)


def lane_present(register: str, lane: str) -> bool:
    return lane in compact_slashes(register)


def load_boot_guard(findings: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not BOOT_GUARD.exists():
        add_finding(findings, "blocked", "boot_guard_exists", f"Missing {BOOT_GUARD.relative_to(ROOT).as_posix()}")
        return None
    try:
        return json.loads(BOOT_GUARD.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        add_finding(findings, "blocked", "boot_guard_parse", f"Boot guard JSON does not parse: {exc}")
        return None


def build_report() -> dict[str, Any]:
    findings: list[dict[str, Any]] = []

    active = read_text(ACTIVE_WORKFLOWS)
    wf72 = read_text(WF72)
    wf73 = read_text(WF73)
    active_register = section_between(active, "## P0/P1 Active Register", r"^## P2 ")
    current_snapshot = section_between(active, "## Current Control Snapshot", r"^## Queue Tiers")
    wf72_next = top_next_action(wf72)
    wf73_next = top_next_action(wf73)

    for lane in REQUIRED_ACTIVE_LANES:
        if not lane_present(active_register, lane):
            add_finding(
                findings,
                "blocked",
                "required_active_lane",
                f"P0/P1 active register is missing required lane {lane}.",
                lane=lane,
            )

    if "WF50" in active_register:
        add_finding(findings, "blocked", "wf50_not_active", "WF50 appears in the P0/P1 active register.")

    for check, needles in STOP_LINE_CHECKS:
        if not stop_line_present(active, check, needles):
            add_finding(
                findings,
                "blocked",
                check,
                "Active Workflows is missing a core stop-line term.",
                required_terms=list(needles),
            )

    if not contains_all(wf72, ("guarded finance sql canon", "numeric alert", "independent reviews")):
        add_finding(
            findings,
            "blocked",
            "wf72_next_action",
            "WF72 continuity does not preserve the guarded SQL, numeric-preservation, and independent-review contract.",
        )
    if contains_all(wf72_next, ("boot", "guard", "rollup")):
        add_finding(
            findings,
            "blocked",
            "wf72_next_action",
            "WF72 top Next Action still appears to prioritize boot guard after rollup.",
        )

    if not ("guard mode" in wf73_next.lower() or "monitor/guard mode" in wf73_next.lower()):
        add_finding(
            findings,
            "blocked",
            "wf73_next_action",
            "WF73 top Next Action does not point to guard/monitor mode.",
        )
    if "continue boot/core Markdown reduction" in wf73_next:
        add_finding(
            findings,
            "blocked",
            "wf73_next_action",
            "WF73 top Next Action still says to continue boot/core Markdown reduction.",
        )

    boot_guard = load_boot_guard(findings)
    boot_hard_failures = None
    boot_status = None
    if boot_guard is not None:
        boot_status = boot_guard.get("status")
        counts = boot_guard.get("counts") if isinstance(boot_guard.get("counts"), dict) else {}
        boot_hard_failures = counts.get("hard_failures")
        if boot_hard_failures != 0:
            add_finding(
                findings,
                "blocked",
                "boot_guard_hard_failures",
                "Latest boot surface size guard has hard failures.",
                hard_failures=boot_hard_failures,
            )
        if boot_status == "warning":
            add_finding(
                findings,
                "warning",
                "boot_guard_warning",
                "Latest boot surface size guard is warning-only; validation still passes if hard_failures=0.",
            )

    counts = {
        "required_active_lanes": len(REQUIRED_ACTIVE_LANES),
        "required_active_lanes_present": sum(1 for lane in REQUIRED_ACTIVE_LANES if lane_present(active_register, lane)),
        "core_stop_line_checks": len(STOP_LINE_CHECKS),
        "core_stop_line_checks_present": sum(
            1 for check, needles in STOP_LINE_CHECKS if stop_line_present(active, check, needles)
        ),
        "findings": len(findings),
        "blocking_findings": sum(1 for item in findings if item["severity"] == "blocked"),
        "warning_findings": sum(1 for item in findings if item["severity"] == "warning"),
        "active_workflows_bytes": ACTIVE_WORKFLOWS.stat().st_size,
        "boot_guard_hard_failures": boot_hard_failures,
    }
    status = "blocked" if counts["blocking_findings"] else "warning" if counts["warning_findings"] else "ok"

    return {
        "generated_at_utc": utc_now(),
        "status": status,
        "report_only": True,
        "mutations_performed": False,
        "authority_boundary": (
            "Read-only workflow hygiene validator. No config/auth/channel/service/runtime mutation, "
            "SQL-canon expansion, archive/move/delete, finance-canon mutation, capital/account/order/"
            "execution action, external delivery, or owner-approval authority."
        ),
        "policy": {
            "validate_exit_nonzero_only_on": "critical/blocking findings",
            "warnings_are_report_only": True,
            "active_register_scope": "P0/P1 Active Register section of Active Workflows",
            "generated_surfaces_are_not_authority": True,
        },
        "inputs": {
            "active_workflows": ACTIVE_WORKFLOWS.relative_to(ROOT).as_posix(),
            "wf72_continuity": WF72.relative_to(ROOT).as_posix(),
            "wf73_continuity": WF73.relative_to(ROOT).as_posix(),
            "boot_guard": BOOT_GUARD.relative_to(ROOT).as_posix(),
            "boot_guard_status": boot_status,
        },
        "required_active_lanes": list(REQUIRED_ACTIVE_LANES),
        "counts": counts,
        "findings": findings,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Report-only workflow hygiene validator")
    parser.add_argument("--write", action="store_true", help=f"Write {DEFAULT_OUT.as_posix()}")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--validate", action="store_true", help="Return nonzero only for blocking findings")
    args = parser.parse_args()

    report = build_report()
    if args.write:
        atomic_write_json(args.output, report, indent=2, ensure_ascii=True)
    else:
        print(json.dumps(report, indent=2, sort_keys=True))

    print(
        "status={status} blocking={blocking} warnings={warnings} active_lanes={lanes}/{required} output={output}".format(
            status=report["status"],
            blocking=report["counts"]["blocking_findings"],
            warnings=report["counts"]["warning_findings"],
            lanes=report["counts"]["required_active_lanes_present"],
            required=report["counts"]["required_active_lanes"],
            output=args.output.as_posix() if args.write else "stdout",
        )
    )

    if args.validate and report["counts"]["blocking_findings"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
