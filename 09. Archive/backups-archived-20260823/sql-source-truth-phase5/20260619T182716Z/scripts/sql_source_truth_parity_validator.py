#!/usr/bin/env python3
"""Validate Markdown-to-SQL parity for the first SQL truth candidate family.

The current candidate family is entry/stop reference metadata from
`03. Portfolio/Execution Board.md` compared with read-only SQL mirrors. This
validator is report-only: mismatches block promotion readiness but do not
mutate SQL, Markdown, portfolio state, or consumer behavior.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sqlite3
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
EXECUTION_BOARD = ROOT / "03. Portfolio" / "Execution Board.md"
FINANCE_DB = TMP / "finance-intelligence-state.sqlite"
CANON_DB = TMP / "veritas-canon-cache.sqlite"
DEFAULT_OUT = TMP / "sql-source-truth-parity-validation.json"
SCHEMA_VERSION = "sql_source_truth_parity_validation.v1"
TOLERANCE = 0.005

FALSE_FLAGS = {
    "source_of_truth_promotion_allowed_by_this_artifact": False,
    "sql_first_consumer_migration_allowed": False,
    "sql_writes_allowed": False,
    "markdown_mutation_allowed": False,
    "portfolio_mutation_allowed": False,
    "owner_approval_inferred": False,
    "recommendation_or_deployment_authority_allowed": False,
    "paper_or_live_execution_allowed": False,
    "customer_or_external_delivery_allowed": False,
}


@dataclass
class ExecutionRow:
    ticker: str
    lane: str
    action_state: str
    close: float | None
    close_date: str | None
    band_low: float | None
    band_high: float | None
    stop: float | None
    technical_posture: str
    blocker_condition: str
    authority_note: str
    source_freshness: str
    line_number: int


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def strip_md(value: str) -> str:
    value = value.replace("**", "").replace("__", "")
    return re.sub(r"\s+", " ", value).strip()


def parse_number(value: str) -> float | None:
    match = re.search(r"-?\d+(?:\.\d+)?", value.replace(",", ""))
    return float(match.group(0)) if match else None


def parse_close(value: str) -> tuple[float | None, str | None]:
    clean = strip_md(value)
    match = re.search(r"(?P<close>-?\d+(?:\.\d+)?)\s*/\s*(?P<date>\d{4}-\d{2}-\d{2})", clean)
    if not match:
        return parse_number(clean), None
    return float(match.group("close")), match.group("date")


def parse_band(value: str) -> tuple[float | None, float | None]:
    clean = strip_md(value).replace(" to ", "-")
    match = re.search(r"(?P<low>-?\d+(?:\.\d+)?)\s*[-–]\s*(?P<high>-?\d+(?:\.\d+)?)", clean)
    if not match:
        return None, None
    return float(match.group("low")), float(match.group("high"))


def split_markdown_row(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def parse_execution_board() -> list[ExecutionRow]:
    if not EXECUTION_BOARD.exists():
        raise FileNotFoundError(rel(EXECUTION_BOARD))

    rows: list[ExecutionRow] = []
    in_table = False
    for line_number, line in enumerate(EXECUTION_BOARD.read_text(encoding="utf-8").splitlines(), start=1):
        if line.startswith("| Ticker | Lane | Action state | Close/date | Band | Stop |"):
            in_table = True
            continue
        if not in_table:
            continue
        if line.startswith("|---"):
            continue
        if not line.startswith("|"):
            break
        cells = split_markdown_row(line)
        if len(cells) < 10:
            continue
        close, close_date = parse_close(cells[3])
        band_low, band_high = parse_band(cells[4])
        rows.append(
            ExecutionRow(
                ticker=strip_md(cells[0]).upper(),
                lane=strip_md(cells[1]),
                action_state=strip_md(cells[2]),
                close=close,
                close_date=close_date,
                band_low=band_low,
                band_high=band_high,
                stop=parse_number(cells[5]),
                technical_posture=strip_md(cells[6]),
                blocker_condition=strip_md(cells[7]),
                authority_note=strip_md(cells[8]),
                source_freshness=strip_md(cells[9]),
                line_number=line_number,
            )
        )
    return rows


def read_only_connect(path: Path) -> sqlite3.Connection:
    uri = path.resolve().as_uri() + "?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def load_finance_refs() -> dict[str, dict[str, Any]]:
    if not FINANCE_DB.exists():
        return {}
    with read_only_connect(FINANCE_DB) as conn:
        rows = conn.execute(
            "SELECT ticker, entry_band_low, entry_band_high, stop_or_invalidation, "
            "band_source, stop_source, freshness_status, validation_status, owner_note_path, "
            "source_artifact_path, source_artifact_hash, source_timestamp "
            "FROM latest_valid_entry_stop_refs"
        ).fetchall()
    return {str(row["ticker"]).upper(): dict(row) for row in rows}


def load_canon_refs() -> dict[str, dict[str, Any]]:
    if not CANON_DB.exists():
        return {}
    fields = {"reference_price_low", "reference_price_high", "reference_invalidation_level"}
    refs: dict[str, dict[str, Any]] = {}
    with read_only_connect(CANON_DB) as conn:
        rows = conn.execute(
            "SELECT scope, field_name, field_value, authority_boundary, validator_status, "
            "freshness_status, reconciliation_status, owner_mirror_note_path, source_artifact_hash "
            "FROM canon_cache_fields WHERE field_name IN (?,?,?)",
            tuple(sorted(fields)),
        ).fetchall()
    for row in rows:
        ticker = str(row["scope"]).upper()
        refs.setdefault(ticker, {})[str(row["field_name"])] = dict(row)
    return refs


def close_enough(left: float | None, right: Any) -> bool:
    if left is None or right is None:
        return left is right
    try:
        return abs(float(left) - float(right)) <= TOLERANCE
    except (TypeError, ValueError):
        return False


def compare_rows(rows: list[ExecutionRow]) -> dict[str, Any]:
    finance_refs = load_finance_refs()
    canon_refs = load_canon_refs()
    comparisons: list[dict[str, Any]] = []
    missing_finance: list[str] = []
    missing_canon: list[str] = []
    mismatches: list[dict[str, Any]] = []
    blocked_field_observations: list[dict[str, str]] = []

    for row in rows:
        ticker = row.ticker
        finance = finance_refs.get(ticker)
        canon = canon_refs.get(ticker)
        if not finance:
            missing_finance.append(ticker)
        if not canon:
            missing_canon.append(ticker)

        checks = {
            "finance_band_low_match": close_enough(row.band_low, finance.get("entry_band_low") if finance else None),
            "finance_band_high_match": close_enough(row.band_high, finance.get("entry_band_high") if finance else None),
            "finance_stop_match": close_enough(row.stop, finance.get("stop_or_invalidation") if finance else None),
            "canon_band_low_match": close_enough(row.band_low, canon.get("reference_price_low", {}).get("field_value") if canon else None),
            "canon_band_high_match": close_enough(row.band_high, canon.get("reference_price_high", {}).get("field_value") if canon else None),
            "canon_stop_match": close_enough(row.stop, canon.get("reference_invalidation_level", {}).get("field_value") if canon else None),
        }
        row_mismatches = [name for name, ok in checks.items() if not ok]
        if row_mismatches:
            mismatches.append({"ticker": ticker, "line_number": row.line_number, "mismatches": row_mismatches})

        blocked_field_observations.append(
            {
                "ticker": ticker,
                "action_state": row.action_state,
                "lane": row.lane,
                "blocked_reason": "action_state_and_lane_are_markdown_owner_only_not_part_of_entry_stop_reference_promotion",
            }
        )
        comparisons.append(
            {
                "ticker": ticker,
                "line_number": row.line_number,
                "markdown": asdict(row),
                "finance_sql": finance,
                "canon_cache_sql": canon,
                "checks": checks,
                "candidate_family_ready_for_this_row": bool(finance and canon and not row_mismatches),
            }
        )

    finance_extra = sorted(set(finance_refs) - {row.ticker for row in rows})
    canon_extra = sorted(set(canon_refs) - {row.ticker for row in rows})
    ready_rows = sum(1 for row in comparisons if row["candidate_family_ready_for_this_row"])
    return {
        "summary": {
            "markdown_rows": len(rows),
            "finance_sql_rows": len(finance_refs),
            "canon_cache_tickers": len(canon_refs),
            "ready_rows": ready_rows,
            "mismatch_rows": len(mismatches),
            "missing_finance_rows": len(missing_finance),
            "missing_canon_rows": len(missing_canon),
            "finance_extra_rows": len(finance_extra),
            "canon_extra_rows": len(canon_extra),
        },
        "missing_finance_tickers": missing_finance,
        "missing_canon_tickers": missing_canon,
        "finance_extra_tickers": finance_extra,
        "canon_extra_tickers": canon_extra,
        "mismatches": mismatches,
        "blocked_field_observations": blocked_field_observations,
        "comparisons": comparisons,
    }


def build_payload() -> dict[str, Any]:
    rows = parse_execution_board()
    comparison = compare_rows(rows)
    summary = comparison["summary"]
    structurally_ready = (
        summary["markdown_rows"] > 0
        and summary["markdown_rows"] == summary["finance_sql_rows"] == summary["canon_cache_tickers"]
        and summary["mismatch_rows"] == 0
        and summary["missing_finance_rows"] == 0
        and summary["missing_canon_rows"] == 0
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": utc_now(),
        "status": "phase2_parity_green_for_entry_stop_reference_metadata" if structurally_ready else "phase2_parity_not_ready",
        "authority_boundary": (
            "report_only_markdown_to_sql_parity_no_sql_writes_no_markdown_mutation_"
            "no_consumer_migration_no_recommendation_deployment_execution_or_customer_authority"
        ),
        **FALSE_FLAGS,
        "candidate_field_family": {
            "name": "entry_stop_reference_metadata",
            "source_owner_note": rel(EXECUTION_BOARD),
            "finance_sql_view": "tmp/finance-intelligence-state.sqlite:latest_valid_entry_stop_refs",
            "canon_cache_table": "tmp/veritas-canon-cache.sqlite:canon_cache_fields",
            "included_fields": ["reference_price_low", "reference_price_high", "reference_invalidation_level"],
            "excluded_fields": [
                "lane",
                "action_state",
                "technical_posture",
                "blocker_condition",
                "authority_note",
                "sizing",
                "sleeve",
                "cash",
                "order_terms",
            ],
        },
        "source_note": {
            "path": rel(EXECUTION_BOARD),
            "sha256": sha256(EXECUTION_BOARD),
        },
        **comparison,
        "next_required_gates": [
            "Add bidirectional drift validator that fails on SQL-only or Markdown-only changes.",
            "Run production consumer A/B proof with SQL-first optional read and Markdown fallback.",
            "Prepare exact field-family promotion decision packet before any source-of-truth promotion.",
        ],
    }


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp_path.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    args = parser.parse_args()

    payload = build_payload()
    if args.write:
        write_json(args.out, payload)
    else:
        print(json.dumps(payload, indent=2, sort_keys=True))

    if args.validate:
        missing_false = [key for key, expected in FALSE_FLAGS.items() if payload.get(key) is not expected]
        if missing_false:
            raise SystemExit(f"authority false flag drift: {missing_false}")
        if payload["summary"]["markdown_rows"] == 0:
            raise SystemExit("no execution board rows parsed")
        if payload["status"] != "phase2_parity_green_for_entry_stop_reference_metadata":
            raise SystemExit(f"parity not ready: {payload['summary']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
