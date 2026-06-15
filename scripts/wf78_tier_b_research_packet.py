#!/usr/bin/env python3
"""WF78 Tier B research/evidence packet generator.

This report-only layer turns the macro/thesis Tier C shortlist into concrete
Tier C -> Tier B research packet requests. It does not re-decide the funnel
rules; it prepares evidence-present/missing rows that the existing Phase 2
`wf78_tier_funnel_promotion_gate.py --requests ...` evaluator can consume.

Report-only. It admits/promotes nothing, mutates no canon/portfolio state,
infers no owner approval, and authorizes no paper/live/account action.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, load_json_artifact

from wf78_tier_funnel_contract import TRANSITIONS

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"

MACRO_OVERLAY = TMP / "wf78-macro-thesis-overlay-gate.json"
TICKER_CARD_REFRESH_GATE = TMP / "finance-ticker-card-refresh-gate.json"
FINANCE_COVERAGE = TMP / "finance-data-coverage-current.json"
TIER_PROMOTION_REVIEW_GATE = TMP / "wf78-tier-promotion-review-gate.json"
TIER_B_EVIDENCE_REPAIR = TMP / "wf78-tier-b-evidence-repair.json"
CARD_DIR = TMP / "ticker-intelligence-cards"

DEFAULT_OUT = TMP / "wf78-tier-b-research-packets.json"
DEFAULT_REQUESTS_OUT = TMP / "wf78-tier-b-research-packet-requests.json"
DEFAULT_DB = TMP / "wf78-tier-b-research-packets.sqlite"
SCHEMA = "veritas.wf78_tier_b_research_packets.v1"

AUTHORITY_BOUNDARY: dict[str, bool] = {
    "review_only": True,
    "report_only": True,
    "research_packet_only": True,
    "phase2_request_generation_only": True,
    "ticker_import_allowed": False,
    "apply_allowed": False,
    "promotion_allowed": False,
    "tier_b_admission_executed": False,
    "tier_a_admission_executed": False,
    "capital_deployment_allowed": False,
    "production_answer_path_change_allowed": False,
    "sql_first_promotion_allowed": False,
    "canon_or_portfolio_mutation_allowed": False,
    "customer_or_external_delivery_allowed": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "money_movement_allowed": False,
    "owner_approval_inferred": False,
}

REQUIRED_TRUE_FLAGS = {"review_only", "report_only", "research_packet_only", "phase2_request_generation_only"}
REQUIRED_FALSE_FLAGS = {flag for flag in AUTHORITY_BOUNDARY if flag not in REQUIRED_TRUE_FLAGS}

STOP_LINES = [
    "These packets prepare Tier C -> Tier B evidence requests only; they admit/promote nothing.",
    "A complete packet can feed Phase 2 eligibility review, but owner approval is still required for admission.",
    "No score, macro overlay, ticker card, packet, or generated request creates Tier B/Tier A promotion.",
    "No import/apply, no production answer-path expansion, no SQL-first promotion.",
    "No capital deployment, paper/live/account action, money movement, canon/portfolio mutation, or owner approval inference.",
]

C_TO_B_REQUIRED = [str(item) for item in TRANSITIONS["c_to_b"]["required_evidence"]]


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


def json_text(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def symbol(value: Any) -> str:
    return str(value or "").upper().strip()


def add_check(checks: list[dict[str, Any]], name: str, ok: bool, detail: Any = None, severity: str = "critical") -> None:
    checks.append({"name": name, "ok": bool(ok), "status": "ok" if ok else "fail", "severity": severity, "detail": detail})


def source_present(card: dict[str, Any], fragment: str, expected_statuses: set[str] | None = None) -> bool:
    for item in as_list(card.get("source_artifacts")):
        if not isinstance(item, dict):
            continue
        path = str(item.get("path") or "").replace("\\", "/")
        if fragment not in path:
            continue
        if expected_statuses is None:
            return bool(item.get("exists") is True)
        return str(item.get("status") or "") in expected_statuses
    return False


def card_path(ticker: str) -> Path:
    return CARD_DIR / f"{ticker}.current.json"


def load_card(ticker: str) -> dict[str, Any]:
    return load_dict(card_path(ticker))


def missing_families_for(ticker: str, coverage: dict[str, Any], refresh_gate: dict[str, Any]) -> set[str]:
    families: set[str] = set()
    for key in ("missing_by_ticker", "stale_by_ticker"):
        for item in as_list(as_dict(coverage.get(key)).get(ticker)):
            families.add(str(item))
    for row in as_list(refresh_gate.get("repair_queue")):
        if isinstance(row, dict) and symbol(row.get("ticker")) == ticker:
            for reason in as_list(row.get("stale_reasons")):
                families.add(str(reason).replace("stale:", ""))
    return families


def repair_map(report: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        symbol(row.get("ticker")): row
        for row in as_list(report.get("rows"))
        if isinstance(row, dict) and symbol(row.get("ticker"))
    }


def repaired_family(ticker: str, family: str, repairs: dict[str, dict[str, Any]]) -> bool:
    row = as_dict(repairs.get(ticker))
    if row.get("status") != "repaired_for_phase2_request":
        return False
    return family in [str(item) for item in as_list(row.get("repaired_evidence_families"))]


def present_if_no_gap(ticker: str, evidence_name: str, candidate: dict[str, Any], card: dict[str, Any],
                      coverage: dict[str, Any], refresh_gate: dict[str, Any],
                      repairs: dict[str, dict[str, Any]]) -> tuple[bool, str]:
    gaps = missing_families_for(ticker, coverage, refresh_gate)
    universe = as_dict(card.get("universe_metadata"))
    recommendation = as_dict(card.get("recommendation_support"))

    if evidence_name == "macro/theme fit":
        return bool(candidate.get("theme") and candidate.get("macro_fit")), "macro overlay ranked this as a Tier B research shortlist lead"
    if evidence_name == "business quality reason":
        metrics = as_dict(card.get("key_financial_metrics"))
        moat = card.get("competitive_moat")
        return bool(metrics.get("status") == "available" or moat), "card has financial/moat context usable for an initial quality reason"
    if evidence_name == "initial fundamentals snapshot available":
        metrics = as_dict(card.get("key_financial_metrics"))
        return bool(metrics.get("status") == "available" and "revenue_growth_margins_fcf_debt" not in gaps), "fundamental metrics snapshot is present"
    if evidence_name == "valuation context available":
        valuation = as_dict(card.get("valuation"))
        return bool(valuation.get("valuation_context") == "available" and "valuation_multiples" not in gaps), "valuation fields are present"
    if evidence_name == "analyst/revision layer available or explicitly not applicable":
        analyst = as_dict(card.get("analyst_consensus_ratings_targets"))
        return bool(analyst.get("status") and "analyst_consensus" not in gaps and "analyst_ratings" not in gaps), "analyst consensus layer is present or explicitly sourced"
    if evidence_name == "initial technical/price-band context":
        if repaired_family(ticker, evidence_name, repairs):
            return True, "repeatable evidence-repair artifact supplied fresh Tier B research-only price context; not a written entry band or deployment setup"
        technical = as_dict(card.get("technical_posture"))
        band = as_dict(card.get("price_band_stop"))
        no_price_gap = "price_band_stop" not in gaps and "technical_posture" not in gaps
        has_band = any(band.get(k) is not None for k in ("entry_band_low", "entry_band_high", "stop_or_invalidation", "band_status"))
        has_technical = any(technical.get(k) is not None for k in ("latest_close", "ma20", "ma50", "ma200", "data_date"))
        return bool(no_price_gap and (has_band or has_technical)), "technical and price/band context must be current enough for research-worthiness"
    if evidence_name == "risk reason understood":
        risks = as_list(card.get("risk_register"))
        return bool(risks), "card risk register has at least one explicit risk/evidence gap"
    if evidence_name == "portfolio role identified":
        return bool(universe.get("monitoring_role") or as_dict(card.get("portfolio_fit_concentration")).get("portfolio_role")), "universe metadata names the monitoring/portfolio role"
    if evidence_name == "source-open proof usable":
        authority = as_dict(card.get("authority_boundary"))
        has_sources = bool(as_list(card.get("source_artifacts")))
        source_required = authority.get("source_open_required_before_final_recommendation_or_action_claim") is True
        return bool(has_sources and source_required and source_present(card, "data/finance/universe-v1.json")), "source artifacts and source-open requirement are visible"
    if evidence_name == "evidence repair burden acceptable":
        if repaired_family(ticker, evidence_name, repairs):
            return True, "repeatable evidence-repair artifact confirms only the thin price-band context gap remained after fresh quote repair"
        blocking = [item for item in gaps if item in {"price_band_stop", "technical_posture", "deployment_readiness", "portfolio_fit_concentration", "recommendation_support"}]
        posture = str(recommendation.get("posture_key") or recommendation.get("posture") or "").lower()
        return bool(len(blocking) <= 1 and "blocked_stale" not in posture), "repair burden is acceptable only when current blocking/stale gaps are small"
    return False, "unknown evidence family"


def build_packet(candidate: dict[str, Any], coverage: dict[str, Any], refresh_gate: dict[str, Any], repairs: dict[str, dict[str, Any]]) -> dict[str, Any]:
    ticker = symbol(candidate.get("ticker"))
    card = load_card(ticker)
    evidence_present: list[str] = []
    evidence_details: list[dict[str, Any]] = []
    for required in C_TO_B_REQUIRED:
        ok, reason = present_if_no_gap(ticker, required, candidate, card, coverage, refresh_gate, repairs)
        if ok:
            evidence_present.append(required)
        evidence_details.append({"family": required, "present": ok, "reason": reason})

    missing = [item for item in C_TO_B_REQUIRED if item not in evidence_present]
    gaps = sorted(missing_families_for(ticker, coverage, refresh_gate))
    request = {
        "ticker": ticker,
        "name": candidate.get("name") or ticker,
        "from_tier": "tier_c",
        "to_tier": "tier_b",
        "current_state": "C-CANDIDATE",
        "evidence_present": evidence_present,
        "batch_id": "101-200",
        "evidence_source": "wf78-tier-b-research-packets+wf78-tier-b-evidence-repair" if ticker in repairs else "wf78-tier-b-research-packets",
    }
    return {
        "ticker": ticker,
        "name": candidate.get("name") or ticker,
        "from_tier": "tier_c",
        "to_tier": "tier_b",
        "current_state": "C-CANDIDATE",
        "theme": candidate.get("theme"),
        "macro_fit": candidate.get("macro_fit"),
        "overlay_score": candidate.get("overlay_score"),
        "sector": candidate.get("sector"),
        "industry": candidate.get("industry"),
        "card_path": rel(card_path(ticker)),
        "card_exists": bool(card),
        "required_evidence_count": len(C_TO_B_REQUIRED),
        "evidence_present_count": len(evidence_present),
        "missing_evidence_count": len(missing),
        "evidence_present": evidence_present,
        "missing_evidence": missing,
        "evidence_details": evidence_details,
        "repair_families": gaps,
        "evidence_repair": as_dict(repairs.get(ticker)),
        "phase2_request": request,
        "packet_status": "phase2_ready_request" if not missing else "needs_evidence_repair",
        "admission_executed": False,
        "owner_approval_inferred": False,
    }


def validation_checks(report: dict[str, Any]) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    summary = as_dict(report.get("summary"))
    authority = as_dict(report.get("authority_boundary"))
    packets = as_list(report.get("research_packets"))
    requests = as_list(as_dict(report.get("phase2_requests")).get("requests"))
    add_check(checks, "schema_current", report.get("schema") == SCHEMA, report.get("schema"))
    add_check(checks, "macro_overlay_ok", as_dict(report.get("input_status")).get("macro_overlay_status") == "ok", report.get("input_status"))
    add_check(checks, "packet_count_matches_shortlist", int(summary.get("packet_count") or 0) == int(summary.get("shortlist_count") or -1), summary)
    add_check(checks, "shortlist_bounded_15", 0 < int(summary.get("packet_count") or 0) <= 15, summary)
    add_check(checks, "phase2_request_count_matches_packets", len(requests) == len(packets), {"requests": len(requests), "packets": len(packets)})
    add_check(checks, "no_tier_b_admission_executed", int(summary.get("tier_b_admission_executed_count") or 0) == 0, summary)
    add_check(checks, "no_owner_approval_inferred", int(summary.get("owner_approval_inferred_count") or 0) == 0, summary)
    add_check(checks, "authority_true_flags_preserved", all(authority.get(flag) is True for flag in REQUIRED_TRUE_FLAGS), authority)
    add_check(checks, "authority_false_flags_preserved", all(authority.get(flag) is False for flag in REQUIRED_FALSE_FLAGS), authority)
    all_ready = int(summary.get("phase2_ready_request_count") or 0) == len(packets)
    repair_backed = int(summary.get("evidence_repair_repaired_count") or 0) == len(packets)
    add_check(checks, "all_ready_requires_repair_backing", (not all_ready) or repair_backed, summary, "warning")
    return checks


def build_report() -> dict[str, Any]:
    macro = load_dict(MACRO_OVERLAY)
    coverage = load_dict(FINANCE_COVERAGE)
    refresh_gate = load_dict(TICKER_CARD_REFRESH_GATE)
    review_gate = load_dict(TIER_PROMOTION_REVIEW_GATE)
    evidence_repair = load_dict(TIER_B_EVIDENCE_REPAIR)
    repairs = repair_map(evidence_repair)
    shortlist = as_list(macro.get("tier_b_research_shortlist"))
    packets = [build_packet(row, coverage, refresh_gate, repairs) for row in shortlist if isinstance(row, dict) and symbol(row.get("ticker"))]
    packets.sort(key=lambda row: (-int(row.get("evidence_present_count") or 0), int(row.get("missing_evidence_count") or 99), -int(row.get("overlay_score") or 0), str(row.get("ticker"))))
    requests = [packet["phase2_request"] for packet in packets]
    complete = [packet for packet in packets if packet["packet_status"] == "phase2_ready_request"]
    missing_counts: dict[str, int] = {}
    for packet in packets:
        for item in as_list(packet.get("missing_evidence")):
            missing_counts[item] = missing_counts.get(item, 0) + 1

    report: dict[str, Any] = {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "ok",
        "authority_boundary": AUTHORITY_BOUNDARY,
        "stop_lines": STOP_LINES,
        "input_status": {
            "macro_overlay_status": macro.get("status"),
            "macro_overlay_validation": as_dict(macro.get("validation")).get("status"),
            "ticker_card_refresh_status": refresh_gate.get("status"),
            "finance_coverage_status": coverage.get("status"),
            "tier_promotion_review_status": review_gate.get("status"),
            "tier_b_evidence_repair_status": evidence_repair.get("status"),
        },
        "source_artifacts": {
            "macro_overlay": rel(MACRO_OVERLAY),
            "ticker_card_refresh_gate": rel(TICKER_CARD_REFRESH_GATE),
            "finance_coverage": rel(FINANCE_COVERAGE),
            "tier_promotion_review_gate": rel(TIER_PROMOTION_REVIEW_GATE),
            "tier_b_evidence_repair": rel(TIER_B_EVIDENCE_REPAIR),
            "ticker_cards": rel(CARD_DIR),
        },
        "summary": {
            "shortlist_count": len(shortlist),
            "packet_count": len(packets),
            "phase2_request_count": len(requests),
            "phase2_ready_request_count": len(complete),
            "needs_evidence_repair_count": len(packets) - len(complete),
            "tier_b_admission_executed_count": 0,
            "tier_a_admission_executed_count": 0,
            "owner_approval_inferred_count": 0,
            "evidence_repair_rows": len(repairs),
            "evidence_repair_repaired_count": len([row for row in repairs.values() if row.get("status") == "repaired_for_phase2_request"]),
            "missing_evidence_counts": dict(sorted(missing_counts.items())),
            "next_safe_action": "Feed phase2_requests into wf78_tier_funnel_promotion_gate --requests, then build/repair the missing evidence families before any owner Tier B admission decision.",
        },
        "phase2_requests": {"requests": requests},
        "research_packets": packets,
    }
    checks = validation_checks(report)
    critical = [item for item in checks if item["ok"] is not True and item["severity"] == "critical"]
    warnings = [item for item in checks if item["ok"] is not True and item["severity"] == "warning"]
    report["validation"] = {
        "status": "ok" if not critical else "blocked",
        "checks": checks,
        "errors": [item["name"] for item in critical],
        "warnings": [item["name"] for item in warnings],
    }
    report["status"] = "ok" if not critical else "blocked"
    return report


def connect_write(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA synchronous=NORMAL")
    return conn


def write_db(path: Path, report: dict[str, Any]) -> None:
    with connect_write(path) as conn:
        conn.executescript(
            """
            DROP TABLE IF EXISTS packets;
            DROP TABLE IF EXISTS missing_evidence;
            DROP TABLE IF EXISTS phase2_requests;
            DROP TABLE IF EXISTS validation;
            DROP TABLE IF EXISTS meta;

            CREATE TABLE packets (
                ticker TEXT PRIMARY KEY,
                name TEXT,
                overlay_score INTEGER,
                evidence_present_count INTEGER NOT NULL,
                missing_evidence_count INTEGER NOT NULL,
                packet_status TEXT NOT NULL,
                raw_json TEXT NOT NULL
            ) STRICT;

            CREATE TABLE missing_evidence (
                ticker TEXT NOT NULL,
                family TEXT NOT NULL,
                PRIMARY KEY (ticker, family)
            ) STRICT;

            CREATE TABLE phase2_requests (
                ticker TEXT PRIMARY KEY,
                request_json TEXT NOT NULL
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
            for packet in as_list(report.get("research_packets")):
                conn.execute(
                    "INSERT INTO packets VALUES (?,?,?,?,?,?,?)",
                    (
                        packet["ticker"],
                        packet.get("name"),
                        packet.get("overlay_score"),
                        int(packet.get("evidence_present_count") or 0),
                        int(packet.get("missing_evidence_count") or 0),
                        packet.get("packet_status"),
                        json_text(packet),
                    ),
                )
                conn.execute(
                    "INSERT INTO phase2_requests VALUES (?,?)",
                    (packet["ticker"], json_text(packet.get("phase2_request"))),
                )
                for family in as_list(packet.get("missing_evidence")):
                    conn.execute("INSERT INTO missing_evidence VALUES (?,?)", (packet["ticker"], str(family)))
            for check in as_list(as_dict(report.get("validation")).get("checks")):
                conn.execute(
                    "INSERT INTO validation VALUES (?,?,?,?)",
                    (check["name"], 1 if check.get("ok") else 0, check.get("severity") or "critical", json_text(check.get("detail"))),
                )
            conn.execute("INSERT INTO meta VALUES (?,?)", ("schema", SCHEMA))
            conn.execute("INSERT INTO meta VALUES (?,?)", ("generated_at_utc", report["generated_at_utc"]))


def resolve(path: Path) -> Path:
    return path if path.is_absolute() else ROOT / path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build WF78 Tier B research/evidence packets from the macro shortlist.")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--write-db", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--requests-out", type=Path, default=DEFAULT_REQUESTS_OUT)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = build_report()
    if args.write:
        atomic_write_json(resolve(args.out), report)
        atomic_write_json(resolve(args.requests_out), report["phase2_requests"])
    if args.write_db:
        write_db(resolve(args.db), report)
    print(json.dumps(report, indent=2, sort_keys=True))
    if args.validate and report["validation"]["status"] != "ok":
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
