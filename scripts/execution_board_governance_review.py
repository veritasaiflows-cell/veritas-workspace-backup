#!/usr/bin/env python3
"""Review the thin Execution Board policy surface for SQL-first drift."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, atomic_write_text

ROOT = Path(__file__).resolve().parents[1]
BOARD = ROOT / "03. Portfolio" / "Execution Board.md"
OUT = ROOT / "tmp" / "execution-board-governance-review.json"
MD_OUT = ROOT / "tmp" / "execution-board-governance-review.md"
SCHEMA = "veritas.execution_board_governance_review.v1"

REQUIRED_SNIPPETS = {
    "thin_human_surface_marker": "THIN HUMAN SURFACE",
    "sql_structured_owner": "Structured owner: state/finance/finance-canon.sqlite",
    "human_policy_routes_title": "# Execution Board - Human Policy and SQL Routes",
    "monthly_governance_cadence": "monthly lightweight governance review plus event-driven updates only",
    "sql_canon_guard_route": "python scripts\\finance_sql_canon_access.py --write --validate",
    "ticker_drilldown_route": "python scripts\\finance_intelligence_state.py ticker <TICKER> --pretty",
    "trade_grade_readiness_route": "python scripts\\trade_grade_os_freshness_cron_runner.py --write --validate",
    "parity_proof_route": "python scripts\\full_intelligence_answer_parity.py --all --write --validate",
    "data_plane_proof_route": "python scripts\\canonical_finance_data_plane_phase6_10.py --write --validate",
}

FORBIDDEN_TABLE_MARKERS = {
    "ticker_entry_table_header": "| Ticker | Entry",
    "symbol_entry_table_header": "| Symbol | Entry",
    "ticker_stop_table_header": "| Ticker | Stop",
    "symbol_stop_table_header": "| Symbol | Stop",
}

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "thin_human_surface_check_only": True,
    "sql_first_structured_owner_preserved": True,
    "ticker_freshness_refresh_allowed": False,
    "finance_canon_or_portfolio_mutation_allowed": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "capital_deployment_allowed": False,
    "owner_approval_inferred": False,
    "cron_schedule_mutation_allowed_by_job": False,
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def check_item(name: str, ok: bool, *, severity: str, detail: str) -> dict[str, Any]:
    return {
        "name": name,
        "ok": ok,
        "severity": severity,
        "detail": detail,
    }


def has_sql_owned_ticker_freshness_policy(text: str) -> bool:
    """Recognize equivalent wording for the board's ticker-freshness boundary."""
    normalized = " ".join(text.lower().split())
    freshness_scope_present = all(
        term in normalized
        for term in ("daily", "market-window", "ticker freshness")
    )
    board_not_owner = any(
        phrase in normalized
        for phrase in (
            "page does not take",
            "page is not the source for",
            "page does not own",
        )
    )
    sql_proof_route_present = any(
        phrase in normalized
        for phrase in ("sql/proof routes", "sql/json proof routes")
    )
    structured_state_owned = any(
        phrase in normalized
        for phrase in (
            "own structured current state",
            "current structured state lives in",
            "structured current state is owned by",
        )
    )
    return (
        freshness_scope_present
        and board_not_owner
        and sql_proof_route_present
        and structured_state_owned
    )


def build_report(board_path: Path = BOARD) -> dict[str, Any]:
    text = board_path.read_text(encoding="utf-8") if board_path.exists() else ""
    checks: list[dict[str, Any]] = []

    checks.append(check_item(
        "board_exists",
        board_path.exists(),
        severity="critical",
        detail=rel(board_path),
    ))

    for name, snippet in REQUIRED_SNIPPETS.items():
        checks.append(check_item(
            name,
            snippet in text,
            severity="critical",
            detail=f"required snippet present: {snippet}",
        ))

    checks.append(check_item(
        "no_market_window_ticker_refresh",
        has_sql_owned_ticker_freshness_policy(text),
        severity="critical",
        detail=(
            "board excludes daily and market-window ticker freshness ownership "
            "and routes structured current state to SQL/proof"
        ),
    ))

    for name, marker in FORBIDDEN_TABLE_MARKERS.items():
        checks.append(check_item(
            name,
            marker not in text,
            severity="critical",
            detail=f"forbidden live structured table marker absent: {marker}",
        ))

    lower = text.lower()
    structured_owner_clear = (
        "it no longer hand-maintains ticker levels" in lower
        and "sql-generated/read-only outputs" in lower
        and "do not use this page as:" in lower
    )
    checks.append(check_item(
        "structured_owner_language_clear",
        structured_owner_clear,
        severity="critical",
        detail="board explicitly rejects live ticker-table ownership and routes structured state to SQL/proof",
    ))

    critical_failures = [item for item in checks if item["severity"] == "critical" and not item["ok"]]
    status = "ok" if not critical_failures else "blocked"
    report = {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": status,
        "board_path": rel(board_path),
        "summary": {
            "checks": len(checks),
            "critical_failures": len(critical_failures),
            "monthly_governance_only": True,
            "market_window_freshness_owner": "SQL/proof packets",
            "retirement_recommendation": "keep_as_thin_human_policy_surface",
        },
        "authority_boundary": AUTHORITY_BOUNDARY,
        "checks": checks,
        "critical_failures": critical_failures,
    }
    return report


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Execution Board Governance Review",
        "",
        f"- Status: {report['status']}",
        f"- Generated at UTC: {report['generated_at_utc']}",
        f"- Board: `{report['board_path']}`",
        "- Cadence: monthly lightweight governance review plus event-driven updates only",
        "- Structured owner: SQL/proof packets, not Markdown freshness",
        "- Boundary: review-only; no portfolio/canon mutation, execution, account action, or owner approval inference",
        "",
        "## Checks",
        "",
    ]
    for item in report["checks"]:
        marker = "PASS" if item["ok"] else "FAIL"
        lines.append(f"- {marker} `{item['name']}` - {item['detail']}")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true", help="Write JSON proof artifact.")
    parser.add_argument("--write-md", action="store_true", help="Write Markdown proof sidecar.")
    parser.add_argument("--validate", action="store_true", help="Return non-zero on blocked review.")
    args = parser.parse_args()

    report = build_report()
    if args.write:
        atomic_write_json(OUT, report)
    if args.write_md:
        atomic_write_text(MD_OUT, render_markdown(report))
    if args.validate and report["status"] != "ok":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
