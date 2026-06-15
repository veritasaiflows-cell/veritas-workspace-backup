#!/usr/bin/env python3
"""Manual read-only SQLite latency benchmark for workspace DBs.

This is a diagnostic proof script, not a tuning or mutation tool. It opens
databases read-only and measures representative query latency so DB lifecycle
and performance claims can be rechecked without relying on a tmp-only snippet.
"""
from __future__ import annotations

import argparse
import json
import math
import sqlite3
import statistics
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_JSON = ROOT / "tmp" / "sql-latency-benchmark-current.json"


BENCHMARKS: tuple[dict[str, Any], ...] = (
    {
        "database": "tmp/workspace-index.sqlite",
        "group": "workspace-index.sqlite (FTS/retrieval cache)",
        "label": "FTS5 MATCH entry stop invalidation",
        "sql": "SELECT rowid FROM documents_fts WHERE documents_fts MATCH ? LIMIT 25",
        "params": ("entry stop invalidation",),
    },
    {
        "database": "tmp/workspace-index.sqlite",
        "group": "workspace-index.sqlite (FTS/retrieval cache)",
        "label": "headings LIKE full scan",
        "sql": "SELECT * FROM headings WHERE heading LIKE ?",
        "params": ("%Portfolio%",),
    },
    {
        "database": "tmp/workspace-index.sqlite",
        "group": "workspace-index.sqlite (FTS/retrieval cache)",
        "label": "freshness subject_key lookup",
        "sql": "SELECT * FROM freshness WHERE subject_type=? LIMIT 50",
        "params": ("document",),
    },
    {
        "database": "tmp/finance-intelligence-state.sqlite",
        "group": "finance-intelligence-state.sqlite (42-ticker current state)",
        "label": "single ticker 4-table join",
        "sql": (
            "SELECT u.ticker,p.*,e.*,f.* FROM universe u "
            "JOIN latest_price_technical p ON p.ticker=u.ticker "
            "JOIN entry_stop_reference e ON e.ticker=u.ticker "
            "JOIN fundamental_snapshot f ON f.ticker=u.ticker "
            "WHERE u.ticker=?"
        ),
        "params": ("ETN",),
    },
    {
        "database": "tmp/finance-intelligence-state.sqlite",
        "group": "finance-intelligence-state.sqlite (42-ticker current state)",
        "label": "full ticker family status",
        "sql": "SELECT * FROM ticker_family_status",
        "params": (),
    },
    {
        "database": "tmp/finance-intelligence-state.sqlite",
        "group": "finance-intelligence-state.sqlite (42-ticker current state)",
        "label": "official evidence index scan",
        "sql": "SELECT * FROM official_evidence_index",
        "params": (),
    },
    {
        "database": "tmp/veritas-artifact-index.sqlite",
        "group": "veritas-artifact-index.sqlite (proof/index)",
        "label": "authority_flags scan",
        "sql": "SELECT * FROM authority_flags",
        "params": (),
    },
    {
        "database": "tmp/veritas-artifact-index.sqlite",
        "group": "veritas-artifact-index.sqlite (proof/index)",
        "label": "market_events recent",
        "sql": "SELECT * FROM market_events ORDER BY rowid DESC LIMIT 50",
        "params": (),
    },
    {
        "database": "tmp/veritas-artifact-index.sqlite",
        "group": "veritas-artifact-index.sqlite (proof/index)",
        "label": "source_field_lineage sample",
        "sql": "SELECT * FROM source_field_lineage LIMIT 100",
        "params": (),
    },
    {
        "database": "tmp/veritas-canon-cache.sqlite",
        "group": "veritas-canon-cache.sqlite (bounded metadata cache)",
        "label": "canon_cache_fields full",
        "sql": "SELECT * FROM canon_cache_fields",
        "params": (),
    },
    {
        "database": "tmp/veritas-canon-cache.sqlite",
        "group": "veritas-canon-cache.sqlite (bounded metadata cache)",
        "label": "change_ledger scan",
        "sql": "SELECT * FROM canon_cache_change_ledger",
        "params": (),
    },
    {
        "database": "tmp/wf67-paper-position-state.sqlite",
        "group": "wf67-paper-position-state.sqlite (paper visibility state)",
        "label": "paper positions",
        "sql": "SELECT * FROM paper_position_snapshot",
        "params": (),
    },
)


def utc_now() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def db_uri(path: Path) -> str:
    return path.resolve().as_uri() + "?mode=ro"


def percentile(sorted_samples: list[float], pct: float) -> float:
    if not sorted_samples:
        return 0.0
    index = max(0, min(len(sorted_samples) - 1, math.ceil((pct / 100.0) * len(sorted_samples)) - 1))
    return sorted_samples[index]


def run_one(spec: dict[str, Any], iterations: int) -> dict[str, Any]:
    db_path = ROOT / spec["database"]
    result: dict[str, Any] = {
        "database": spec["database"],
        "group": spec["group"],
        "label": spec["label"],
        "status": "missing" if not db_path.exists() else "ok",
        "rows": None,
        "cold_ms": None,
        "p50_ms": None,
        "p95_ms": None,
        "error": None,
    }
    if not db_path.exists():
        result["error"] = f"missing database: {spec['database']}"
        return result

    try:
        con = sqlite3.connect(db_uri(db_path), uri=True)
        cur = con.cursor()
        t0 = time.perf_counter()
        rows = cur.execute(spec["sql"], spec["params"]).fetchall()
        result["cold_ms"] = (time.perf_counter() - t0) * 1000
        samples: list[float] = []
        for _ in range(iterations):
            t0 = time.perf_counter()
            cur.execute(spec["sql"], spec["params"]).fetchall()
            samples.append((time.perf_counter() - t0) * 1000)
        con.close()
    except sqlite3.Error as exc:
        result["status"] = "error"
        result["error"] = str(exc)
        return result

    samples.sort()
    result["rows"] = len(rows)
    result["p50_ms"] = statistics.median(samples) if samples else None
    result["p95_ms"] = percentile(samples, 95)
    return result


def build_report(iterations: int) -> dict[str, Any]:
    results = [run_one(spec, iterations) for spec in BENCHMARKS]
    failed = [row for row in results if row["status"] != "ok"]
    successful = [row for row in results if row["status"] == "ok"]
    return {
        "status": "ok" if successful and not failed else "warning" if successful else "critical",
        "generated_at_utc": utc_now(),
        "workspace_root": str(ROOT),
        "iterations": iterations,
        "authority_boundary": {
            "read_only": True,
            "db_mutation": False,
            "canon_or_portfolio_mutation": False,
            "brokerage_or_execution_authority": False,
        },
        "summary": {
            "benchmarks": len(results),
            "successful": len(successful),
            "failed_or_missing": len(failed),
            "max_p95_ms": max((float(row["p95_ms"] or 0) for row in successful), default=None),
        },
        "results": results,
    }


def print_table(report: dict[str, Any]) -> None:
    current_group = None
    for row in report["results"]:
        if row["group"] != current_group:
            current_group = row["group"]
            print(f"=== {current_group} ===")
        if row["status"] != "ok":
            print(f"  {row['label']:42s} status={row['status']} error={row['error']}")
            continue
        print(
            f"  {row['label']:42s} rows={int(row['rows']):5d}  "
            f"cold={float(row['cold_ms']):7.3f}ms  "
            f"p50={float(row['p50_ms']):7.3f}ms  "
            f"p95={float(row['p95_ms']):7.3f}ms"
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--iterations", type=int, default=60, help="warm iterations per benchmark")
    parser.add_argument("--json-out", default=str(DEFAULT_JSON), help="write JSON report path")
    parser.add_argument("--no-write", action="store_true", help="do not write the JSON report")
    parser.add_argument("--json", action="store_true", help="print JSON instead of a compact table")
    parser.add_argument("--validate", action="store_true", help="exit nonzero if any benchmark is missing or errors")
    args = parser.parse_args()

    report = build_report(max(1, args.iterations))
    if not args.no_write:
        out = Path(args.json_out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")

    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print_table(report)

    if args.validate and report["status"] != "ok":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
