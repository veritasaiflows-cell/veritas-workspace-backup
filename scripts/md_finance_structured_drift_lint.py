#!/usr/bin/env python3
"""Flag structured finance facts duplicated in human Markdown surfaces.

This lint is deliberately report-only. It helps thin finance Markdown by
identifying band/stop/tier/freshness/source/decision facts that should be
generated from SQL/JSON or explicitly marked as historical/audit context.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCRIPTS = Path(__file__).resolve().parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from market_data_utils import atomic_write_json  # noqa: E402


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = ROOT / "tmp" / "md-finance-structured-drift-lint.json"
DEFAULT_MD_OUT = ROOT / "tmp" / "md-finance-structured-drift-lint.md"
DEFAULT_RECONCILIATION = ROOT / "tmp" / "sql-markdown-reconciliation.json"
SCHEMA = "veritas.md_finance_structured_drift_lint.v1"

DEFAULT_TARGETS = [
    "03. Portfolio/Execution Board.md",
    "03. Portfolio/Portfolio Snapshot.md",
    "04. Research/Coverage and Watchlist.md",
    "05. Intelligence/Weekly Positioning Review.md",
    "01. Dashboards/Today.md",
    "01. Dashboards/This Week.md",
    "01. Dashboards/Executive Brief.md",
    "01. Dashboards/Next Actions.md",
]

STRUCTURED_PATTERNS: dict[str, re.Pattern[str]] = {
    "reference_band": re.compile(r"\b(entry\s+band|reference\s+price|reference_price|band[_ -]?(low|high)|\bin[- ]band\b|\bno[- ]chase\b)\b", re.I),
    "stop_or_invalidation": re.compile(r"\b(stop|invalidation|below[- ]stop|near[- ]stop|reclaim)\b", re.I),
    "tier_routing": re.compile(r"\b(Tier\s+[ABC]|A-READY|A-WATCH|A-CHALLENGED|B-CANDIDATE|C-MONITOR|C-CANDIDATE)\b", re.I),
    "freshness": re.compile(r"\b(true[- ]freshness|freshness|currentness|fresh|stale|stale_refreshable|stale_review_required)\b", re.I),
    "source_lineage": re.compile(r"\b(source lineage|source[_ -]?artifact|source[_ -]?open|provenance|sha256|generated_at_utc|source freshness)\b", re.I),
    "answer_path": re.compile(r"\b(answer[- ]path|production[- ]grade|production_current|legacy\s+42|full[- ]answer|WF85)\b", re.I),
    "decision_state": re.compile(r"\b(review[- ]ready|approval[- ]draft|approval[- ]card|monitor_only|below_stop|evidence_repair|repair_first|wait_no_chase|decision state)\b", re.I),
}

GENERATED_MARKERS = re.compile(
    r"\b(SQL-generated|generated from SQL|generated/read-only|read-only export|machine-generated|generated artifact|tmp/|source artifact)\b",
    re.I,
)
HISTORICAL_MARKERS = re.compile(r"\b(historical|audit|snapshot|as of|previous|archived|legacy compatibility)\b", re.I)

AUTHORITY_BOUNDARY = {
    "report_only": True,
    "markdown_mutation_allowed": False,
    "sql_mutation_allowed": False,
    "portfolio_mutation_allowed": False,
    "archive_or_delete_allowed": False,
    "capital_deployment_allowed": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "owner_approval_inferred": False,
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def line_status(path: Path, line: str) -> tuple[str, str, bool]:
    normalized_path = path.as_posix().lower()
    if "machine.md" in normalized_path or GENERATED_MARKERS.search(line):
        return "generated_or_linked_ok", "line is generated or points at generated proof", False
    if HISTORICAL_MARKERS.search(line):
        return "historical_or_audit_context", "line appears explicitly historical/audit context", False
    return (
        "structured_fact_requires_sql_export_or_stale_marker",
        "human Markdown repeats structured finance fact without generated/historical marker",
        True,
    )


def scan_text(path: Path, text: str) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for number, raw_line in enumerate(text.splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("<!--"):
            continue
        families = [family for family, pattern in STRUCTURED_PATTERNS.items() if pattern.search(line)]
        if not families:
            continue
        status, reason, requires_action = line_status(path, line)
        findings.append(
            {
                "path": rel(path),
                "line_number": number,
                "field_families": families,
                "status": status,
                "requires_thinning_or_marker": requires_action,
                "reason": reason,
                "line_excerpt": line[:260],
            }
        )
    return findings


def reconciliation_summary(path: Path) -> dict[str, Any]:
    payload = load_json(path)
    rows = payload.get("rows")
    if not isinstance(rows, list):
        rows = []
    status_counts = Counter(str(row.get("reconciliation_status") or row.get("status") or "unknown") for row in rows if isinstance(row, dict))
    review_needed = sum(1 for row in rows if isinstance(row, dict) and (row.get("review_needed") or row.get("manual_review_required")))
    return {
        "path": rel(path),
        "exists": path.exists(),
        "row_count": len(rows),
        "review_needed_count": review_needed,
        "status_counts": dict(status_counts),
        "generated_at_utc": payload.get("generated_at_utc"),
        "authority_boundary": payload.get("authority_boundary") or payload.get("authority"),
    }


def build_report(targets: list[Path], reconciliation: Path) -> dict[str, Any]:
    findings: list[dict[str, Any]] = []
    target_rows: list[dict[str, Any]] = []
    warnings: list[str] = []
    for path in targets:
        if not path.exists():
            warnings.append(f"target_missing:{rel(path)}")
            target_rows.append({"path": rel(path), "exists": False, "finding_count": 0, "requires_action_count": 0})
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        file_findings = scan_text(path, text)
        findings.extend(file_findings)
        target_rows.append(
            {
                "path": rel(path),
                "exists": True,
                "line_count": len(text.splitlines()),
                "finding_count": len(file_findings),
                "requires_action_count": sum(1 for row in file_findings if row["requires_thinning_or_marker"]),
            }
        )

    family_counts: Counter[str] = Counter()
    status_counts: Counter[str] = Counter()
    by_path_requires_action: Counter[str] = Counter()
    for row in findings:
        status_counts[row["status"]] += 1
        for family in row["field_families"]:
            family_counts[family] += 1
        if row["requires_thinning_or_marker"]:
            by_path_requires_action[row["path"]] += 1

    errors: list[str] = []
    for key, expected in AUTHORITY_BOUNDARY.items():
        if key != "report_only" and expected is False:
            continue
    return {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "warning" if any(row["requires_thinning_or_marker"] for row in findings) else "ok",
        "purpose": "Report Markdown lines that duplicate structured finance facts and should be SQL-generated, marked historical, or thinned.",
        "authority_boundary": AUTHORITY_BOUNDARY,
        "targets": target_rows,
        "source_reconciliation": reconciliation_summary(reconciliation),
        "summary": {
            "target_count": len(targets),
            "finding_count": len(findings),
            "requires_action_count": sum(1 for row in findings if row["requires_thinning_or_marker"]),
            "status_counts": dict(status_counts),
            "field_family_counts": dict(family_counts),
            "requires_action_by_path": dict(by_path_requires_action),
            "next_safe_action": "Thin one Markdown surface at a time by replacing duplicated structured fields with SQL-generated read-only exports and stale/historical markers.",
        },
        "findings": findings,
        "validation": {"status": "ok" if not errors else "blocked", "errors": errors, "warnings": warnings},
        "stop_lines": [
            "This lint does not edit Markdown, SQL, portfolio notes, archives, or execution state.",
            "Do not thin away audit trails, source provenance, or owner approval records.",
            "Archive/delete requires DB lifecycle packet and exact owner approval.",
        ],
    }


def write_markdown(path: Path, report: dict[str, Any]) -> None:
    summary = report["summary"]
    lines = [
        "# Markdown Finance Structured Drift Lint",
        "",
        f"Status: `{report['status']}`",
        f"Generated: `{report['generated_at_utc']}`",
        "",
        "## Summary",
        "",
        f"- Findings: {summary['finding_count']}",
        f"- Requires thinning or marker: {summary['requires_action_count']}",
        f"- Field families: `{json.dumps(summary['field_family_counts'], sort_keys=True)}`",
        "",
        "## Targets",
        "",
    ]
    for target in report["targets"]:
        lines.append(
            f"- `{target['path']}`: exists={target['exists']} findings={target.get('finding_count', 0)} requires_action={target.get('requires_action_count', 0)}"
        )
    lines.extend(["", "## Action Samples", ""])
    for row in [item for item in report["findings"] if item["requires_thinning_or_marker"]][:40]:
        families = ",".join(row["field_families"])
        lines.append(f"- `{row['path']}:{row['line_number']}` [{families}] {row['line_excerpt']}")
    lines.extend(["", "## Stop Lines", ""])
    lines.extend(f"- {line}" for line in report["stop_lines"])
    lines.append("")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", action="append", help="Markdown file to scan. Defaults to core finance human surfaces.")
    parser.add_argument("--reconciliation", default=str(DEFAULT_RECONCILIATION))
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    parser.add_argument("--md-out", default=str(DEFAULT_MD_OUT))
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--write-md", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser.parse_args()


def resolve_path(text: str) -> Path:
    path = Path(text)
    return path if path.is_absolute() else ROOT / path


def main() -> int:
    args = parse_args()
    targets = [resolve_path(value) for value in (args.target or DEFAULT_TARGETS)]
    reconciliation = resolve_path(args.reconciliation)
    report = build_report(targets, reconciliation)
    out = resolve_path(args.out)
    md_out = resolve_path(args.md_out)
    if args.write:
        atomic_write_json(out, report, indent=2)
    if args.write_md:
        write_markdown(md_out, report)
    if args.json or not args.write:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(
            f"status={report['status']} findings={report['summary']['finding_count']} "
            f"requires_action={report['summary']['requires_action_count']} out={rel(out)}"
        )
    if args.validate and report["validation"]["status"] != "ok":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
