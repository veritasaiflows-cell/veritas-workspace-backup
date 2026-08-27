#!/usr/bin/env python3
"""Build a review-only canon-anchor preview for the Execution Board table."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, atomic_write_text
from sql_first_thin_board_contract import evaluate_sql_first_thin_board_contract


ROOT = Path(__file__).resolve().parents[1]
EXECUTION_BOARD = ROOT / "03. Portfolio" / "Execution Board.md"
OUT = ROOT / "tmp" / "execution-board-canon-anchor-pilot.json"
MD_OUT = ROOT / "tmp" / "execution-board-canon-anchor-pilot.md"
SCHEMA_VERSION = "execution_board_canon_anchor_pilot.v1"

AUTHORITY = {
    "review_only": True,
    "anchor_preview_only": True,
    "human_canon_mutation_performed": False,
    "sql_mutation_performed": False,
    "portfolio_mutation_allowed": False,
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


def clean_cell(value: str) -> str:
    value = value.strip()
    value = re.sub(r"</?[^>]+>", "", value)
    value = value.replace("**", "").replace("`", "")
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def parse_float(value: str) -> float | None:
    match = re.search(r"-?\d+(?:\.\d+)?", value.replace(",", ""))
    return float(match.group(0)) if match else None


def sha_file(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def sha_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def split_table_row(line: str) -> list[str]:
    return [clean_cell(part) for part in line.strip().strip("|").split("|")]


def parse_close_date(value: str) -> tuple[float | None, str | None]:
    match = re.search(r"(-?\d+(?:\.\d+)?)\s*/\s*(\d{4}-\d{2}-\d{2})", value.replace(",", ""))
    if not match:
        return parse_float(value), None
    return float(match.group(1)), match.group(2)


def parse_band(value: str) -> tuple[float | None, float | None]:
    match = re.search(r"(-?\d+(?:\.\d+)?)\s*-\s*(-?\d+(?:\.\d+)?)", value.replace(",", ""))
    if not match:
        return None, None
    return float(match.group(1)), float(match.group(2))


def band_position(close: float | None, low: float | None, high: float | None, stop: float | None) -> str:
    if close is None:
        return "unknown"
    if stop is not None and close < stop:
        return "below_stop"
    if low is None or high is None:
        return "unknown"
    if close < low:
        return "below_band"
    if close > high:
        return "above_band_no_chase"
    return "inside_band"


def source_paths(source_freshness: str) -> list[str]:
    return sorted(set(re.findall(r"tmp/[A-Za-z0-9_.\-/]+\.json", source_freshness.replace("\\", "/"))))


def source_timestamp(source_freshness: str, close_date: str | None) -> str | None:
    dates = re.findall(r"\d{4}-\d{2}-\d{2}", source_freshness)
    if dates:
        return sorted(dates)[-1]
    return close_date


def build_anchor(row: dict[str, str]) -> dict[str, Any]:
    close, close_date = parse_close_date(row["Close/date"])
    low, high = parse_band(row["Band"])
    stop = parse_float(row["Stop"])
    paths = source_paths(row["Source/freshness"])
    path_hashes = []
    for item in paths:
        digest = sha_file(ROOT / item)
        path_hashes.append({"path": item, "sha256": digest})
    first_hash = next((item["sha256"] for item in path_hashes if item["sha256"]), None)
    source_sha256 = first_hash or sha_text(row["Source/freshness"])
    source_time = source_timestamp(row["Source/freshness"], close_date)
    authority_note = row["Authority note"]
    no_execution = "no automatic execution" in authority_note.lower() or "no execution" in authority_note.lower()
    no_inferred_approval = "no inferred owner approval" in authority_note.lower() or "no owner approval" in authority_note.lower()
    ticker = row["Ticker"].upper()
    anchor = {
        "canon_id": f"execution_board:{ticker}",
        "ticker": ticker,
        "lane": row["Lane"],
        "action_state": row["Action state"],
        "close": close,
        "close_date": close_date,
        "band_low": low,
        "band_high": high,
        "stop": stop,
        "technical_posture": row["Technical posture"],
        "blocker_condition": row["Blocker/condition"],
        "authority": "reference_only",
        "authority_note": authority_note,
        "band_position": band_position(close, low, high, stop),
        "source_artifact_path": paths[0] if paths else rel(EXECUTION_BOARD),
        "source_artifact_paths": paths,
        "source_artifact_sha256": source_sha256,
        "source_artifact_hashes": path_hashes,
        "source_generated_at_utc": source_time,
        "execution_authority_allowed": False,
        "capital_deployment_allowed": False,
        "owner_approval_inferred": False,
        "authority_parse": {
            "no_execution_language_present": no_execution,
            "no_inferred_approval_language_present": no_inferred_approval,
        },
    }
    return anchor


def parse_execution_board(path: Path) -> list[dict[str, str]]:
    lines = path.read_text(encoding="utf-8").splitlines()
    header: list[str] | None = None
    rows: list[dict[str, str]] = []
    for line in lines:
        if not line.startswith("|"):
            if header and rows:
                break
            continue
        cells = split_table_row(line)
        if cells and cells[0] == "---":
            continue
        if cells and cells[0] == "Ticker":
            header = cells
            continue
        if not header or len(cells) != len(header):
            continue
        if cells[0] == "---":
            continue
        rows.append(dict(zip(header, cells)))
    return rows


def render_anchor_block(anchor: dict[str, Any]) -> str:
    keys = [
        "canon_id",
        "ticker",
        "lane",
        "action_state",
        "close",
        "close_date",
        "band_low",
        "band_high",
        "stop",
        "authority",
        "band_position",
        "source_artifact_path",
        "source_artifact_sha256",
        "source_generated_at_utc",
    ]
    lines = ["```canon"]
    for key in keys:
        value = anchor.get(key)
        lines.append(f"{key}: {value}")
    lines.append("capital_deployment_allowed: false")
    lines.append("paper_or_live_execution_allowed: false")
    lines.append("owner_approval_inferred: false")
    lines.append("```")
    return "\n".join(lines)


def build_report(path: Path) -> dict[str, Any]:
    thin_contract = evaluate_sql_first_thin_board_contract(path)
    if thin_contract.get("sql_first_thin_board_detected"):
        errors = [] if thin_contract.get("sql_first_thin_board_allowed") else ["sql_first_thin_board_contract_blocked"]
        warnings = [] if thin_contract.get("sql_first_thin_board_allowed") else [
            f"{len(thin_contract.get('errors') or [])} thin-board contract check(s) blocked"
        ]
        return {
            "schema_version": SCHEMA_VERSION,
            "status": "ok" if not errors else "blocked",
            "generated_at_utc": utc_now(),
            "authority": AUTHORITY,
            "source": {"path": rel(path), "row_count": 0, "mode": "sql_first_thin_board"},
            "summary": {
                "anchor_count": 0,
                "tickers": [],
                "missing_required_count": 0,
                "unsafe_authority_count": 0,
                "board_table_required": False,
                "sql_first_thin_board_allowed": bool(thin_contract.get("sql_first_thin_board_allowed")),
            },
            "anchors": [],
            "missing_required": [],
            "sql_first_thin_board_contract": thin_contract,
            "validation": {"status": "ok" if not errors else "blocked", "errors": errors, "warnings": warnings},
        }
    rows = parse_execution_board(path)
    anchors = [build_anchor(row) for row in rows]
    required = ["ticker", "lane", "action_state", "close", "close_date", "band_low", "band_high", "stop", "authority"]
    missing_required = [
        {"ticker": anchor.get("ticker"), "missing": [key for key in required if anchor.get(key) in (None, "")]}
        for anchor in anchors
        if any(anchor.get(key) in (None, "") for key in required)
    ]
    unsafe = [
        anchor["ticker"]
        for anchor in anchors
        if anchor["capital_deployment_allowed"] or anchor["execution_authority_allowed"] or anchor["owner_approval_inferred"]
    ]
    errors: list[str] = []
    warnings: list[str] = []
    if not path.exists():
        errors.append(f"Execution Board not found: {rel(path)}")
    if len(anchors) < 40:
        errors.append(f"expected at least 40 Execution Board table rows, found {len(anchors)}")
    if unsafe:
        errors.append(f"unsafe authority flags in anchors: {unsafe}")
    if missing_required:
        warnings.append(f"{len(missing_required)} anchors have missing required values")
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "blocked" if errors else ("warning" if warnings else "ok"),
        "generated_at_utc": utc_now(),
        "authority": AUTHORITY,
        "source": {"path": rel(path), "row_count": len(rows)},
        "summary": {
            "anchor_count": len(anchors),
            "tickers": [anchor["ticker"] for anchor in anchors],
            "missing_required_count": len(missing_required),
            "unsafe_authority_count": len(unsafe),
        },
        "anchors": anchors,
        "missing_required": missing_required,
        "validation": {"status": "ok" if not errors else "blocked", "errors": errors, "warnings": warnings},
    }


def render_md(report: dict[str, Any]) -> str:
    lines = [
        "# Execution Board Canon Anchor Pilot",
        "",
        f"- Status: `{report['status']}`",
        f"- Generated: `{report['generated_at_utc']}`",
        f"- Anchor count: `{report['summary']['anchor_count']}`",
        "",
        "This is a review-only preview. It does not modify the Execution Board, SQL canon, portfolio state, or any execution authority.",
        "",
    ]
    for anchor in report["anchors"]:
        lines.append(f"## {anchor['ticker']}")
        lines.append("")
        lines.append(render_anchor_block(anchor))
        lines.append("")
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", default=str(EXECUTION_BOARD))
    parser.add_argument("--output", default=str(OUT))
    parser.add_argument("--md-output", default=str(MD_OUT))
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--write-md", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    input_path = Path(args.input)
    if not input_path.is_absolute():
        input_path = ROOT / input_path
    report = build_report(input_path)
    if args.write:
        atomic_write_json(args.output, report)
    if args.write_md:
        atomic_write_text(args.md_output, render_md(report))
    if args.json or not args.write:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(f"status={report['status']} anchors={report['summary']['anchor_count']}")
    if args.validate and report["validation"]["status"] != "ok":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
