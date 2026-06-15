#!/usr/bin/env python3
"""Select a WF78 scaleout batch from the durable candidate pool.

Report-only. This writes a batch-specific source artifact but does not import
tickers, promote tiers, mutate canon/portfolio state, infer approval, or
authorize execution.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

SCRIPTS = Path(__file__).resolve().parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from market_data_utils import atomic_write_json
from wf78_batch_manifest import (  # noqa: E402
    AUTHORITY_BOUNDARY,
    DEFAULT_MANIFEST,
    DEFAULT_SOURCE_POOL,
    artifact_meta,
    batch_artifacts,
    batch_candidates,
    batch_spec,
    load_dict,
    rel,
    sha256_file,
    utc_now,
)

SCHEMA = "veritas.wf78_batch_source_selector.v1"


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def add_check(checks: list[dict[str, Any]], name: str, ok: bool, detail: Any = None, severity: str = "critical") -> None:
    checks.append({"name": name, "status": "ok" if ok else "fail", "ok": bool(ok), "severity": severity, "detail": detail})


def build_report(batch: str) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    spec = batch_spec(batch)
    source_pool = load_dict(DEFAULT_SOURCE_POOL)
    candidates = batch_candidates(spec, source_pool)
    sector_counts = Counter(str(row.get("sector") or "Unknown") for row in candidates)
    already_active = [row for row in candidates if row.get("already_active_in_universe") is True]
    symbols = [str(row.get("yfinance_symbol") or row.get("ticker") or "").upper().replace(".", "-") for row in candidates]

    add_check(checks, "source_pool_exists", DEFAULT_SOURCE_POOL.exists(), rel(DEFAULT_SOURCE_POOL))
    add_check(checks, "manifest_exists", DEFAULT_MANIFEST.exists(), rel(DEFAULT_MANIFEST))
    add_check(checks, "batch_candidate_count_100", len(candidates) == 100, len(candidates))
    add_check(checks, "batch_unique_ticker_count_100", len(set(symbols)) == 100, {"rows": len(symbols), "unique": len(set(symbols))})
    add_check(checks, "batch_rank_window_complete", [row.get("scaleout_candidate_rank") for row in candidates] == list(range(spec.candidate_rank_start, spec.candidate_rank_end + 1)), {
        "expected_start": spec.candidate_rank_start,
        "expected_end": spec.candidate_rank_end,
        "observed_start": candidates[0].get("scaleout_candidate_rank") if candidates else None,
        "observed_end": candidates[-1].get("scaleout_candidate_rank") if candidates else None,
    })
    add_check(checks, "no_active_duplicate_rows_for_new_batch", not already_active, [{"ticker": row.get("ticker"), "rank": row.get("scaleout_candidate_rank")} for row in already_active], "warning")

    critical = [row for row in checks if row["severity"] == "critical" and not row["ok"]]
    warning_rows = [row for row in checks if row["severity"] == "warning" and not row["ok"]]
    status = "ok" if not critical else "blocked"
    return {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "workflow": "WF78 - 500 Ticker Finance Intelligence Scaleout",
        "artifact_type": "wf78_batch_source_selector",
        "status": status,
        "batch": {
            "batch_label": spec.batch_label,
            "rank_start": spec.rank_start,
            "rank_end": spec.rank_end,
            "candidate_rank_start": spec.candidate_rank_start,
            "candidate_rank_end": spec.candidate_rank_end,
            "artifacts": batch_artifacts(spec),
        },
        "authority_boundary": AUTHORITY_BOUNDARY,
        "summary": {
            "candidate_count": len(candidates),
            "unique_ticker_count": len(set(symbols)),
            "already_active_in_universe_count": len(already_active),
            "sector_counts": dict(sorted(sector_counts.items())),
            "source_pool_row_count": len(as_list(source_pool.get("candidates"))),
            "selected_seed_row_count": len(as_list(source_pool.get("selected_101_200"))),
            "source_pool_sha256": sha256_file(DEFAULT_SOURCE_POOL),
            "next_safe_action": "Run batch provider/source validation; do not import or promote from this selector.",
        },
        "candidate_rows": candidates,
        "source_artifacts": [
            artifact_meta(DEFAULT_MANIFEST, "wf78_scaleout_batch_manifest", True),
            artifact_meta(DEFAULT_SOURCE_POOL, "wf78_candidate_source_pool", True),
        ],
        "validation": {
            "status": "ok" if not critical else "error",
            "checks": checks,
            "errors": critical,
            "warnings": warning_rows,
        },
        "stop_lines": [
            "No ticker import/apply.",
            "No production answer-path promotion.",
            "No SQL-first or SQL-canon/cache expansion.",
            "No canon/portfolio/sizing/cash/risk-rule mutation.",
            "No customer/external delivery.",
            "No paper/live/brokerage/account action or money movement.",
            "No owner approval inference.",
        ],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch", required=True, help="Batch label, e.g. 301-400")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--out", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = build_report(args.batch)
    spec = batch_spec(args.batch)
    out = args.out or spec.source_artifact
    if args.write:
        atomic_write_json(out, report, ensure_ascii=False)
    output_errors: list[str] = []
    if args.validate:
        if as_dict(report.get("validation")).get("errors"):
            output_errors.append("critical validation errors present")
        if args.write:
            loaded = load_dict(out)
            if loaded.get("schema") != SCHEMA:
                output_errors.append("written output schema mismatch")
    status = "blocked" if output_errors or report["status"] != "ok" else "ok"
    print(json.dumps({
        "status": status,
        "json_out": rel(out) if args.write else None,
        "summary": report.get("summary"),
        "output_validation_errors": output_errors,
    }, indent=2, sort_keys=True))
    return 0 if status == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
