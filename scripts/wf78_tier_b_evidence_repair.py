#!/usr/bin/env python3
"""Build repeatable WF78 Tier B evidence-repair proof for research packets.

This repair layer exists for Tier C -> Tier B research-worthiness only. It can
prove an initial price/technical context from fresh quotes and mark the repair
burden acceptable when the only remaining packet gap is the missing thin-monitor
price-band family. It does not create written entry bands, stops, deployment
readiness, owner approval, canon/portfolio mutation, or execution authority.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, load_json_artifact


ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
RESEARCH_PACKETS = TMP / "wf78-tier-b-research-packets.json"
DEFAULT_OUT = TMP / "wf78-tier-b-evidence-repair.json"
DEFAULT_DB = TMP / "wf78-tier-b-evidence-repair.sqlite"
SCHEMA = "veritas.wf78_tier_b_evidence_repair.v1"

REPAIRED_FAMILIES = [
    "initial technical/price-band context",
    "evidence repair burden acceptable",
]

AUTHORITY_BOUNDARY: dict[str, bool] = {
    "review_only": True,
    "report_only": True,
    "tier_b_research_evidence_repair_only": True,
    "written_entry_band_created": False,
    "stop_or_invalidation_created": False,
    "deployment_ready": False,
    "tier_b_label_applied": False,
    "tier_a_label_applied": False,
    "admission_executed": False,
    "apply_allowed": False,
    "canon_or_portfolio_mutation_allowed": False,
    "production_answer_path_change_allowed": False,
    "capital_deployment_allowed": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "owner_approval_inferred": False,
}

REQUIRED_TRUE_FLAGS = {"review_only", "report_only", "tier_b_research_evidence_repair_only"}
REQUIRED_FALSE_FLAGS = {flag for flag in AUTHORITY_BOUNDARY if flag not in REQUIRED_TRUE_FLAGS}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def load_dict(path: Path) -> dict[str, Any]:
    payload = load_json_artifact(path)
    return payload if isinstance(payload, dict) else {}


def parse_quote(raw: str) -> tuple[str, float]:
    if "=" not in raw:
        raise argparse.ArgumentTypeError("--quote must use TICKER=PRICE")
    ticker, price = raw.split("=", 1)
    ticker = ticker.strip().upper()
    if not ticker:
        raise argparse.ArgumentTypeError("quote ticker is empty")
    try:
        value = float(price)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"invalid price for {ticker}: {price}") from exc
    if value <= 0:
        raise argparse.ArgumentTypeError(f"quote must be positive for {ticker}")
    return ticker, value


def add_check(checks: list[dict[str, Any]], name: str, ok: bool, detail: Any = None, severity: str = "critical") -> None:
    checks.append({"name": name, "ok": bool(ok), "status": "ok" if ok else "fail", "severity": severity, "detail": detail})


def packet_by_ticker(report: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(packet.get("ticker") or "").upper(): packet
        for packet in as_list(report.get("research_packets"))
        if isinstance(packet, dict) and packet.get("ticker")
    }


def repair_row(ticker: str, packet: dict[str, Any], quote: float | None, quote_source: str | None, quote_time_utc: str | None) -> dict[str, Any]:
    prior_missing = [str(item) for item in as_list(packet.get("missing_evidence"))]
    repair_families = [str(item) for item in as_list(packet.get("repair_families"))]
    blockers: list[str] = []
    cautions: list[str] = []
    repaired: list[str] = []

    if quote is None:
        blockers.append("fresh quote missing")
    if "price_band_stop" not in repair_families:
        cautions.append("price_band_stop was not the recorded repair family")
    if any(item not in REPAIRED_FAMILIES for item in prior_missing):
        blockers.append(f"non-price repair gaps remain: {', '.join(sorted(set(prior_missing) - set(REPAIRED_FAMILIES)))}")

    if not blockers:
        repaired = REPAIRED_FAMILIES[:]

    status = "repaired_for_phase2_request" if repaired == REPAIRED_FAMILIES else "blocked"
    return {
        "ticker": ticker,
        "name": packet.get("name"),
        "status": status,
        "prior_packet_status": packet.get("packet_status"),
        "prior_evidence_present_count": packet.get("evidence_present_count"),
        "prior_missing_evidence": prior_missing,
        "prior_repair_families": repair_families,
        "repaired_evidence_families": repaired,
        "fresh_price_context": {
            "current_price": quote,
            "quote_source": quote_source,
            "quote_time_utc": quote_time_utc,
            "source_required_before_material_claims": True,
        },
        "research_only_context": {
            "tier_b_research_bench_only": True,
            "initial_price_context_present": quote is not None,
            "written_entry_band_present": False,
            "stop_or_invalidation_present": False,
            "deployment_readiness_present": False,
            "reason": "Fresh quote repairs initial Tier B research context only; it is not an entry band, stop, or deployable setup.",
        },
        "blockers": sorted(set(blockers)),
        "cautions": sorted(set(cautions)),
        "source_artifacts": [rel(RESEARCH_PACKETS)],
        "authority_boundary": AUTHORITY_BOUNDARY,
    }


def build_report(quotes: dict[str, float], quote_source: str | None, quote_time_utc: str | None) -> dict[str, Any]:
    packets_report = load_dict(RESEARCH_PACKETS)
    packets = packet_by_ticker(packets_report)
    target_tickers = [
        ticker for ticker, packet in packets.items()
        if set(as_list(packet.get("missing_evidence"))) == set(REPAIRED_FAMILIES)
        or as_dict(packet.get("evidence_repair")).get("status") == "repaired_for_phase2_request"
        or (
            packet.get("packet_status") == "phase2_ready_request"
            and "wf78-tier-b-evidence-repair" in str(as_dict(packet.get("phase2_request")).get("evidence_source") or "")
        )
    ]
    rows = [repair_row(ticker, packets[ticker], quotes.get(ticker), quote_source, quote_time_utc) for ticker in sorted(target_tickers)]
    repaired = [row for row in rows if row.get("status") == "repaired_for_phase2_request"]
    blocked = [row for row in rows if row.get("status") != "repaired_for_phase2_request"]

    checks: list[dict[str, Any]] = []
    add_check(checks, "research_packets_present", bool(packets_report), rel(RESEARCH_PACKETS))
    add_check(checks, "research_packets_validation_ok", as_dict(packets_report.get("validation")).get("status") == "ok", as_dict(packets_report.get("validation")))
    add_check(checks, "target_rows_present", len(rows) > 0, {"target_count": len(rows)})
    add_check(checks, "all_targets_have_quotes", len(blocked) == 0, [row["ticker"] for row in blocked])
    add_check(checks, "no_written_band_created", AUTHORITY_BOUNDARY["written_entry_band_created"] is False, AUTHORITY_BOUNDARY["written_entry_band_created"])
    add_check(checks, "no_stop_created", AUTHORITY_BOUNDARY["stop_or_invalidation_created"] is False, AUTHORITY_BOUNDARY["stop_or_invalidation_created"])
    for flag in REQUIRED_TRUE_FLAGS:
        add_check(checks, f"authority_{flag}_true", AUTHORITY_BOUNDARY.get(flag) is True, AUTHORITY_BOUNDARY.get(flag))
    for flag in REQUIRED_FALSE_FLAGS:
        add_check(checks, f"authority_{flag}_false", AUTHORITY_BOUNDARY.get(flag) is False, AUTHORITY_BOUNDARY.get(flag))

    errors = [check for check in checks if check["severity"] == "critical" and not check["ok"]]
    return {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "ok" if not errors else "blocked",
        "workflow": "WF78 - Tier B Evidence Repair",
        "purpose": "Repair repeatable Tier B research-packet evidence gaps using fresh quote context without creating deployable bands/stops.",
        "authority_boundary": AUTHORITY_BOUNDARY,
        "source_artifacts": {"tier_b_research_packets": rel(RESEARCH_PACKETS)},
        "summary": {
            "target_count": len(rows),
            "repaired_for_phase2_request_count": len(repaired),
            "blocked_count": len(blocked),
            "repaired_tickers": [row["ticker"] for row in repaired],
            "blocked_tickers": [row["ticker"] for row in blocked],
            "next_safe_action": "Rerun wf78_tier_b_research_packet.py so repaired evidence can flow into Phase 2 requests; then rerun the Phase 2 funnel gate.",
        },
        "rows": rows,
        "validation": {
            "status": "ok" if not errors else "error",
            "errors": errors,
            "warnings": [],
            "checks": checks,
        },
        "stop_lines": [
            "This repair artifact does not create written entry bands or stops.",
            "This repair artifact does not make any ticker deployable.",
            "This repair artifact does not apply Tier B labels or owner approval.",
            "No canon, portfolio, production answer-path, paper/live, brokerage, or account action authority is granted.",
        ],
    }


def json_text(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def write_db(path: Path, report: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as conn:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.executescript(
            """
            DROP TABLE IF EXISTS repair_rows;
            DROP TABLE IF EXISTS validation;
            DROP TABLE IF EXISTS meta;

            CREATE TABLE repair_rows (
                ticker TEXT PRIMARY KEY,
                status TEXT NOT NULL,
                current_price REAL,
                repaired_evidence_families_json TEXT NOT NULL,
                blockers_json TEXT NOT NULL,
                raw_json TEXT NOT NULL
            ) STRICT;

            CREATE TABLE validation (
                name TEXT PRIMARY KEY,
                ok INTEGER NOT NULL CHECK(ok IN (0,1)),
                severity TEXT NOT NULL,
                detail_json TEXT NOT NULL
            ) STRICT;

            CREATE TABLE meta (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            ) STRICT;
            """
        )
        with conn:
            for row in as_list(report.get("rows")):
                conn.execute(
                    "INSERT INTO repair_rows VALUES (?,?,?,?,?,?)",
                    (
                        row["ticker"],
                        row["status"],
                        as_dict(row.get("fresh_price_context")).get("current_price"),
                        json_text(row.get("repaired_evidence_families")),
                        json_text(row.get("blockers")),
                        json_text(row),
                    ),
                )
            for check in as_list(as_dict(report.get("validation")).get("checks")):
                conn.execute(
                    "INSERT INTO validation VALUES (?,?,?,?)",
                    (check["name"], 1 if check.get("ok") else 0, check.get("severity") or "critical", json_text(check.get("detail"))),
                )
            conn.execute("INSERT INTO meta VALUES (?,?)", ("schema", SCHEMA))
            conn.execute("INSERT INTO meta VALUES (?,?)", ("generated_at_utc", report["generated_at_utc"]))


def resolve(path: Path) -> Path:
    return path if path.is_absolute() else ROOT / path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--quote", action="append", type=parse_quote, help="fresh quote as TICKER=PRICE")
    parser.add_argument("--quote-source")
    parser.add_argument("--quote-time-utc")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--write-db", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    args = parser.parse_args()

    report = build_report(dict(args.quote or []), args.quote_source, args.quote_time_utc)
    if args.write:
        atomic_write_json(resolve(args.out), report)
    if args.write_db:
        write_db(resolve(args.db), report)
    print(json.dumps({
        "status": report["status"],
        "summary": report["summary"],
        "validation": {
            "status": as_dict(report.get("validation")).get("status"),
            "errors": len(as_list(as_dict(report.get("validation")).get("errors"))),
            "warnings": len(as_list(as_dict(report.get("validation")).get("warnings"))),
        },
        "out": rel(resolve(args.out)) if args.write else None,
        "db": rel(resolve(args.db)) if args.write_db else None,
    }, indent=2))
    if args.validate and as_dict(report.get("validation")).get("status") != "ok":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
