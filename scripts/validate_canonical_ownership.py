#!/usr/bin/env python3
"""Validate finance-note canonical ownership boundaries.

This is a note-layer hygiene validator. It does not validate investment merit,
deployment authority, or trading readiness.
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from sql_first_thin_board_contract import evaluate_sql_first_thin_board_contract

ROOT = Path(__file__).resolve().parents[1]

EXECUTION_BOARD = ROOT / "03. Portfolio" / "Execution Board.md"
SNAPSHOT = ROOT / "03. Portfolio" / "Portfolio Snapshot.md"
TECHNICAL_RETIRED = ROOT / "09. Archive" / "Finance Canon" / "2026-05-13 retired redirects" / "Technical Entry and Invalidation Sheet.md"
TRIGGER_RETIRED = ROOT / "09. Archive" / "Finance Canon" / "2026-05-13 retired redirects" / "Deployment Trigger Sheet.md"
COVERAGE_WATCHLIST = ROOT / "04. Research" / "Coverage and Watchlist.md"
WATCHLIST_RETIRED = ROOT / "09. Archive" / "Finance Canon" / "2026-05-13 retired redirects" / "Watchlist.md"
COVERAGE_RETIRED = ROOT / "09. Archive" / "Finance Canon" / "2026-05-13 retired redirects" / "Coverage Universe.md"
ARCHIVED_ORIGINALS = [
    ROOT / "09. Archive" / "Finance Canon" / "2026-05-13 pre-consolidation" / "Technical Entry and Invalidation Sheet.md",
    ROOT / "09. Archive" / "Finance Canon" / "2026-05-13 pre-consolidation" / "Deployment Trigger Sheet.md",
    ROOT / "09. Archive" / "Finance Canon" / "2026-05-13 pre-consolidation" / "Watchlist.md",
    ROOT / "09. Archive" / "Finance Canon" / "2026-05-13 pre-consolidation" / "Coverage Universe.md",
]
RETIRED_ACTIVE_PATHS = [
    ROOT / "03. Portfolio" / "Technical Entry and Invalidation Sheet.md",
    ROOT / "03. Portfolio" / "Deployment Trigger Sheet.md",
    ROOT / "02. Markets" / "Watchlist.md",
    ROOT / "04. Research" / "Coverage Universe.md",
]
CONFIG = ROOT / "tmp" / "portfolio-config.json"
OUT = ROOT / "tmp" / "canonical-ownership-validation.json"
ARCHIVE_TOMBSTONE = ROOT / "state" / "archive-deletion-tombstone.json"

DISALLOWED_COVERAGE_ACTION_TERMS = re.compile(
    r"\b(Deployable now|Almost deployable|Wait / no chase|Do not touch|Below stop|entry band|preferred band|explicit stop|invalidation)\b",
    re.IGNORECASE,
)
EXACT_LEVEL_IN_COVERAGE_ACT_WHEN = re.compile(
    r"^- \*\*Act when:\*\*.*(?:\$\d|\b\d{3,}(?:\.\d+)?\s*[–-]\s*\d{3,}(?:\.\d+)?\b|Stop\s+\$?\d)",
    re.IGNORECASE | re.MULTILINE,
)
LEGACY_SNAPSHOT_HEADERS = ["| Ticker | Thesis | Weight | Entry | Target | Stop | Status |"]
LEGACY_EXECUTION_HEADERS = [
    "| Ticker | Thesis status | Macro fit | Technical trigger | Catalyst blocker | Invalidation | Size tier | Action state | Why |",
    "| Ticker | Action state | Live condition / blocker | Authority note | Detail source |",
]
REQUIRED_EXECUTION_HEADER = "| Ticker | Lane | Action state | Close/date | Band | Stop | Technical posture | Blocker/condition | Authority note | Source/freshness |"
REQUIRED_COVERAGE_HEADER = "| Ticker | Sector | Coverage Tier | Thesis pointer | Deployment/action pointer | Source lineage |"


@dataclass
class Finding:
    severity: str
    file: str
    message: str
    ticker: str | None = None


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def load_config() -> dict:
    return json.loads(CONFIG.read_text(encoding="utf-8"))


def load_archive_tombstone() -> set[str]:
    if not ARCHIVE_TOMBSTONE.exists():
        return set()
    payload = json.loads(ARCHIVE_TOMBSTONE.read_text(encoding="utf-8"))
    return {str(row.get("path")) for row in payload.get("deleted_files", []) if row.get("path")}


def tracked_tickers(config: dict) -> list[str]:
    tracked = set(config.get("tracked_universe", {}).keys())
    tracked.update(config.get("entry_bands", {}).keys())
    return sorted(t for t in tracked if t)


def lane_for(config: dict, ticker: str) -> str:
    return (config.get("tracked_universe", {}).get(ticker, {}) or {}).get("coverage_lane", "unknown")


def markdown_rows(text: str) -> list[list[str]]:
    rows: list[list[str]] = []
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith("|") or "---" in line:
            continue
        rows.append([cell.strip() for cell in line.strip("|").split("|")])
    return rows


def has_heading(text: str, ticker: str) -> bool:
    return re.search(rf"^###\s+{re.escape(ticker)}\b", text, re.MULTILINE) is not None


def table_row_for(rows: Iterable[list[str]], ticker: str) -> list[str] | None:
    for row in rows:
        if row and row[0] == ticker:
            return row
    return None


def validate_retired_stub(path: Path, text: str, target: str) -> list[Finding]:
    findings: list[Finding] = []
    if target not in text:
        findings.append(Finding("warning", rel(path), f"retired legacy stub should redirect to {target}"))
    if "| Ticker |" in text or re.search(r"^###\s+[A-Z][A-Z0-9.]*\b", text, re.MULTILINE):
        findings.append(Finding("warning", rel(path), "retired legacy stub still appears to contain parseable current finance content"))
    return findings


def validate_retired_legacy_files() -> list[Finding]:
    findings: list[Finding] = []
    tombstoned = load_archive_tombstone()
    for path in ARCHIVED_ORIGINALS:
        if not path.exists() and rel(path).replace("\\", "/") not in tombstoned:
            findings.append(Finding("critical", rel(path), "archived pre-consolidation original is missing"))
    for path in RETIRED_ACTIVE_PATHS:
        if path.exists():
            findings.append(Finding("warning", rel(path), "retired legacy finance note still exists in an active canon folder"))
    retired_targets = [
        (TECHNICAL_RETIRED, "[[03. Portfolio/Execution Board]]"),
        (TRIGGER_RETIRED, "[[03. Portfolio/Execution Board]]"),
        (WATCHLIST_RETIRED, "[[04. Research/Coverage and Watchlist]]"),
        (COVERAGE_RETIRED, "[[04. Research/Coverage and Watchlist]]"),
    ]
    for path, target in retired_targets:
        if not path.exists():
            if rel(path).replace("\\", "/") in tombstoned:
                findings.append(Finding("info", rel(path), "retired legacy redirect stub is tombstoned after approved archive deletion"))
                continue
            findings.append(Finding("critical", rel(path), "retired legacy redirect stub is missing"))
            continue
        findings.extend(validate_retired_stub(path, read_text(path), target))
    return findings


def validate_execution_board(config: dict, tickers: list[str], text: str, thin_contract: dict, *, legacy_table_contract: bool) -> list[Finding]:
    findings: list[Finding] = []
    if thin_contract.get("sql_first_thin_board_detected"):
        if thin_contract.get("sql_first_thin_board_allowed"):
            findings.append(Finding("info", rel(EXECUTION_BOARD), "SQL-first thin Execution Board contract accepted; ticker rows are owned by SQL/JSON proof"))
            return findings
        findings.append(
            Finding(
                "critical",
                rel(EXECUTION_BOARD),
                "Execution Board is thin, but the SQL-first / JSON proof contract is blocked",
            )
        )
        return findings
    if not legacy_table_contract:
        findings.append(Finding("info", rel(EXECUTION_BOARD), "Legacy Execution Board table checks skipped; use --legacy-table-contract for pre-thinning table/header validation"))
        return findings
    if REQUIRED_EXECUTION_HEADER not in text:
        findings.append(Finding("critical", rel(EXECUTION_BOARD), "Execution Board missing required consolidated execution table header"))
    rows = markdown_rows(text)
    for ticker in tickers:
        lane = lane_for(config, ticker)
        if lane in {"execution", "watch"}:
            if table_row_for(rows, ticker) is None:
                findings.append(Finding("critical", rel(EXECUTION_BOARD), "execution/watch ticker missing Execution Board table row", ticker))
            if not has_heading(text, ticker):
                findings.append(Finding("warning", rel(EXECUTION_BOARD), "execution/watch ticker missing parser-compatible Execution Board section", ticker))
    for header in LEGACY_EXECUTION_HEADERS:
        if header in text:
            findings.append(Finding("warning", rel(EXECUTION_BOARD), "Execution Board still contains legacy execution/trigger schema"))
    if "Do not touch / stop breached" in text and "### JPM" in text:
        jpm_section = text[text.find("### JPM") : text.find("### NVDA") if "### NVDA" in text else len(text)]
        if "Do not touch / stop breached" in jpm_section and "archive-only" not in jpm_section.lower():
            findings.append(Finding("warning", rel(EXECUTION_BOARD), "JPM section contains live-looking stale stop-breach language", "JPM"))
    return findings


def validate_coverage_watchlist(tickers: list[str], text: str, thin_contract: dict, *, legacy_table_contract: bool) -> list[Finding]:
    findings: list[Finding] = []
    if thin_contract.get("sql_first_thin_board_detected"):
        if thin_contract.get("sql_first_thin_board_allowed"):
            findings.append(Finding("info", rel(COVERAGE_WATCHLIST), "SQL-first thin Coverage and Watchlist contract accepted; universe rows are owned by SQL/JSON proof"))
            return findings
        findings.append(
            Finding(
                "critical",
                rel(COVERAGE_WATCHLIST),
                "Coverage and Watchlist is thin, but the SQL-first / JSON proof contract is blocked",
            )
        )
        return findings
    if not legacy_table_contract:
        findings.append(Finding("info", rel(COVERAGE_WATCHLIST), "Legacy Coverage and Watchlist table/thesis checks skipped; use --legacy-table-contract for pre-thinning validation"))
        return findings
    if REQUIRED_COVERAGE_HEADER not in text:
        findings.append(Finding("critical", rel(COVERAGE_WATCHLIST), "Coverage and Watchlist missing required consolidated universe table header"))
    if re.search(r"\|[^\n]*Current Deployment State[^\n]*\|", text):
        findings.append(Finding("warning", rel(COVERAGE_WATCHLIST), "Coverage and Watchlist must not carry Current Deployment State column"))
    rows = markdown_rows(text)
    for ticker in tickers:
        if table_row_for(rows, ticker) is None:
            findings.append(Finding("critical", rel(COVERAGE_WATCHLIST), "tracked ticker missing Coverage and Watchlist universe row", ticker))
        if not has_heading(text, ticker):
            findings.append(Finding("critical", rel(COVERAGE_WATCHLIST), "tracked ticker missing Coverage and Watchlist thesis section", ticker))
    for match in EXACT_LEVEL_IN_COVERAGE_ACT_WHEN.finditer(text):
        line = match.group(0)
        findings.append(Finding("warning", rel(COVERAGE_WATCHLIST), "Coverage act-when line appears to contain exact technical levels", line[:80]))
    # Limit deployment/action language check to the top universe table; thesis sections may quote historical statuses.
    table_start = text.find(REQUIRED_COVERAGE_HEADER)
    table_end = text.find("## Tier definitions")
    if table_start != -1 and table_end != -1:
        universe_table = text[table_start:table_end]
        for line in universe_table.splitlines():
            if DISALLOWED_COVERAGE_ACTION_TERMS.search(line):
                findings.append(Finding("warning", rel(COVERAGE_WATCHLIST), "Coverage universe table appears to duplicate live action state", line[:80]))
    return findings


def validate_snapshot(text: str, *, legacy_table_contract: bool) -> list[Finding]:
    findings: list[Finding] = []
    if legacy_table_contract:
        for header in LEGACY_SNAPSHOT_HEADERS:
            if header in text:
                findings.append(Finding("warning", rel(SNAPSHOT), "legacy thesis/entry/stop table still exists in Snapshot"))
        if "## Core holdings" in text and "Draft weight" not in text:
            findings.append(Finding("warning", rel(SNAPSHOT), "Snapshot model tables should own draft weight explicitly"))
    else:
        findings.append(Finding("info", rel(SNAPSHOT), "Legacy Snapshot table checks skipped; thin portfolio posture is validated by SQL/JSON proof and owner-note route markers"))
    return findings


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true", help="Compatibility flag; this validator always writes its JSON proof.")
    parser.add_argument("--legacy-table-contract", action="store_true", help="Also run pre-thinning table/header/thesis completeness checks.")
    parser.add_argument("--out", type=Path, default=OUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config = load_config()
    tickers = tracked_tickers(config)
    thin_contract = evaluate_sql_first_thin_board_contract(EXECUTION_BOARD)
    coverage_thin_contract = evaluate_sql_first_thin_board_contract(
        COVERAGE_WATCHLIST,
        route_tokens=[
            "finance_sql_canon_access.py",
            "finance_intelligence_state.py",
            "full_intelligence_answer_parity.py",
            "canonical_finance_data_plane.py",
        ],
        proof_files=[
            "tmp/full-answer-parity/full-answer-parity-rollup.json",
            "tmp/trade-grade-full-answer/",
            "tmp/ticker-intelligence-cards/",
            "state/finance/finance-canon.sqlite",
        ],
        authority_phrases=[
            "no execution state",
            "owner approval",
            "portfolio mutation",
            "archive/delete/apply authority",
            "inferred approval",
        ],
    )

    findings: list[Finding] = []
    findings.extend(validate_execution_board(config, tickers, read_text(EXECUTION_BOARD), thin_contract, legacy_table_contract=args.legacy_table_contract))
    findings.extend(validate_coverage_watchlist(tickers, read_text(COVERAGE_WATCHLIST), coverage_thin_contract, legacy_table_contract=args.legacy_table_contract))
    findings.extend(validate_snapshot(read_text(SNAPSHOT), legacy_table_contract=args.legacy_table_contract))
    findings.extend(validate_retired_legacy_files())

    summary = {
        "critical": sum(1 for f in findings if f.severity == "critical"),
        "warning": sum(1 for f in findings if f.severity == "warning"),
        "info": sum(1 for f in findings if f.severity == "info"),
        "tracked_or_banded_tickers": len(tickers),
    }
    status = "ok" if summary["critical"] == 0 and summary["warning"] == 0 else "needs_review"
    payload = {
        "generated_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "status": status,
        "consumer_posture": "note_layer_hygiene_only",
        "validation_mode": "legacy_table_contract" if args.legacy_table_contract else "thin_contract_default",
        "canonical_surfaces": {
            "execution": rel(EXECUTION_BOARD),
            "coverage_watchlist": rel(COVERAGE_WATCHLIST),
            "portfolio_snapshot": rel(SNAPSHOT),
        },
        "retired_legacy_stubs": [
            rel(TECHNICAL_RETIRED),
            rel(TRIGGER_RETIRED),
            rel(WATCHLIST_RETIRED),
            rel(COVERAGE_RETIRED),
        ],
        "retired_active_paths": [rel(path) for path in RETIRED_ACTIVE_PATHS],
        "archived_originals": [rel(path) for path in ARCHIVED_ORIGINALS],
        "authority": {
            "portfolio_mutation_allowed": False,
            "deployment_state_mutation_allowed": False,
            "trade_execution_allowed": False,
            "owner_approval_granted": False,
        },
        "summary": summary,
        "sql_first_thin_board_contract": thin_contract,
        "sql_first_thin_coverage_watchlist_contract": coverage_thin_contract,
        "findings": [asdict(f) for f in findings],
    }
    out = args.out if args.out.is_absolute() else ROOT / args.out
    out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": status, "summary": summary, "output": str(out.relative_to(ROOT)), "validation_mode": payload["validation_mode"]}, indent=2))
    return 1 if summary["critical"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
