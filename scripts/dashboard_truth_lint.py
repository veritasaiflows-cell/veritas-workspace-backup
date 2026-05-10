#!/usr/bin/env python3
"""Dashboard truth-surface lint for WF35.

Reports places where dashboard or generated companion surfaces may outrank canonical notes.
Read-only: writes a JSON report under tmp/ and exits warning when risks are found.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "tmp" / "dashboard-truth-lint.json"

CANONICAL_OWNERS = {
    "deployment_state": "03. Portfolio/Deployment Trigger Sheet.md",
    "portfolio_posture": "03. Portfolio/Portfolio Snapshot.md",
    "technical_discipline": "03. Portfolio/Technical Entry and Invalidation Sheet.md",
    "macro_regime": "02. Markets/Macro Regime Dashboard.md",
    "weekly_operating_stance": "05. Intelligence/Weekly Positioning Review.md",
    "risk_doctrine": "07. Risk/Risk Rules.md",
}

DASHBOARD_PATHS = [
    "Home.md",
    "01. Dashboards/Executive Brief.md",
    "01. Dashboards/This Week.md",
    "01. Dashboards/Next Actions.md",
]
DASHBOARD_DIRS = [
    "01. Dashboards/Daily Executive Summary",
    "01. Dashboards/Post-Market Snapshot",
    "01. Dashboards/Pre-Market Snapshot",
]
MACHINE_DIRS = [
    "01. Dashboards/Daily Executive Summary",
    "01. Dashboards/Post-Market Snapshot",
    "01. Dashboards/Pre-Market Snapshot",
    "02. Markets/Weekly Macro Snapshot",
]

DEPLOYABLE_RE = re.compile(r"\bdeployable now\b", re.IGNORECASE)
SUBORDINATE_RE = re.compile(r"machine evidence|generated|not approved truth|not canonical|review artifact|historical", re.IGNORECASE)
TECHNICAL_AUTHORITY_RE = re.compile(r"subordinate technical shorthand|canonical deployable-now decision surface lives in|deployment trigger sheet", re.IGNORECASE)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def read_rel(rel: str) -> str:
    path = ROOT / rel
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="replace")


def add(findings: list[dict], path: Path | str, severity: str, issue: str, recommendation: str) -> None:
    rel = path if isinstance(path, str) else path.relative_to(ROOT).as_posix()
    findings.append({"path": rel, "severity": severity, "issue": issue, "recommendation": recommendation})


def collect_markdown_dirs(rel_dirs: list[str]) -> list[Path]:
    paths: list[Path] = []
    for rel in rel_dirs:
        base = ROOT / rel
        if base.exists():
            paths.extend(sorted(base.glob("*.md")))
    return paths


def lint() -> dict:
    findings: list[dict] = []

    trigger = read_rel(CANONICAL_OWNERS["deployment_state"])
    canonical_none_deployable = "DEPLOYABLE NOW: 0" in trigger or "Deployable Now: 0" in trigger or "No names are deployable now" in trigger

    for rel in DASHBOARD_PATHS:
        text = read_rel(rel)
        if not text:
            continue
        if DEPLOYABLE_RE.search(text) and "Deployment Trigger Sheet" not in text:
            add(
                findings,
                rel,
                "warning",
                "dashboard/read-stack surface uses deployable-now language without routing to the canonical deployment owner",
                "state that deployment truth lives in `03. Portfolio/Deployment Trigger Sheet.md`",
            )

    for path in collect_markdown_dirs(DASHBOARD_DIRS):
        text = path.read_text(encoding="utf-8", errors="replace")
        if canonical_none_deployable and DEPLOYABLE_RE.search(text) and "none deployable" not in text.lower():
            add(
                findings,
                path,
                "warning",
                "dated dashboard/history surface may conflict with current canonical deployment state",
                "treat as historical packet and route current deployment truth to Deployment Trigger Sheet",
            )

    for path in collect_markdown_dirs(MACHINE_DIRS):
        if "-machine" not in path.name:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")[:1200]
        if not SUBORDINATE_RE.search(text):
            add(
                findings,
                path,
                "warning",
                "machine companion lacks explicit subordinate/generated-not-canonical labeling near the top",
                "add or regenerate with subordinate machine-evidence disclaimer",
            )

    weekly = ROOT / CANONICAL_OWNERS["weekly_operating_stance"]
    if weekly.exists():
        text = weekly.read_text(encoding="utf-8", errors="replace")
        if "template" in text.lower() or "placeholder" in text.lower():
            add(
                findings,
                weekly,
                "info",
                "weekly canonical surface may contain old template/placeholder residue",
                "inspect and remove old lower-section template residue if it weakens current truth clarity",
            )

    tech = ROOT / CANONICAL_OWNERS["technical_discipline"]
    if tech.exists():
        text = tech.read_text(encoding="utf-8", errors="replace")
        if DEPLOYABLE_RE.search(text) and not TECHNICAL_AUTHORITY_RE.search(text[:1200]):
            add(
                findings,
                tech,
                "info",
                "technical sheet uses deployable-state language and could overlap deployment authority",
                "clarify that final deployment state is owned by Deployment Trigger Sheet",
            )

    status = "warning" if any(f["severity"] == "warning" for f in findings) else "ok"
    return {
        "status": status,
        "generated_at_utc": utc_now(),
        "canonical_truth_note": "Dashboards summarize and route; canonical investment state remains in owner notes.",
        "canonical_owners": CANONICAL_OWNERS,
        "counts": {
            "findings": len(findings),
            "warnings": sum(1 for f in findings if f["severity"] == "warning"),
            "info": sum(1 for f in findings if f["severity"] == "info"),
        },
        "findings": findings,
    }


def main() -> int:
    report = lint()
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 1 if report["status"] == "warning" else 0


if __name__ == "__main__":
    raise SystemExit(main())
