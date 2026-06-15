#!/usr/bin/env python3
"""Review-only WF78 adjudication of the 42 production tickers into Tier A/B/C recommendations.

Production answer-path readiness is not the same as Tier A/B admission. This
packet ranks the current 42 production-scope names with explicit evidence
penalties and prepares a recommendation slate for owner review. It mutates
nothing and grants no promotion, portfolio, paper/live, account, or approval
authority.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, load_json_artifact
from wf78_legacy_42_tier_state import production_entries as legacy_42_tier_entries, source_summary as legacy_42_tier_source_summary


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
TMP = ROOT / "tmp"

UNIVERSE = DATA / "finance" / "universe-v1.json"
CARD_DIR = TMP / "ticker-intelligence-cards"
CAPACITY_GATE = TMP / "wf78-tier-capacity-policy-gate.json"
PROMOTION_REVIEW_GATE = TMP / "wf78-tier-promotion-review-gate.json"
TICKER_CARD_REFRESH_GATE = TMP / "finance-ticker-card-refresh-gate.json"

DEFAULT_OUT = TMP / "wf78-production-tier-adjudication.json"
DEFAULT_DB = TMP / "wf78-production-tier-adjudication.sqlite"
SCHEMA = "veritas.wf78_production_tier_adjudication.v1"

TIER_A_REVIEW_CAP = 25
TIER_B_RESEARCH_CAP = 50

AUTHORITY_BOUNDARY: dict[str, bool] = {
    "review_only": True,
    "report_only": True,
    "recommendation_packet_only": True,
    "tier_a_admission_allowed": False,
    "tier_b_admission_allowed": False,
    "production_answer_path_change_allowed": False,
    "ticker_import_allowed": False,
    "apply_allowed": False,
    "canon_or_portfolio_mutation_allowed": False,
    "capital_deployment_allowed": False,
    "sizing_sleeve_cash_risk_rule_mutation_allowed": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "customer_or_external_delivery_allowed": False,
    "owner_approval_inferred": False,
}

REQUIRED_TRUE_FLAGS = {"review_only", "report_only", "recommendation_packet_only"}
REQUIRED_FALSE_FLAGS = {flag for flag in AUTHORITY_BOUNDARY if flag not in REQUIRED_TRUE_FLAGS}

TIER_A_BLOCKING_FAMILIES = {
    "price_band_stop_position_sizing",
    "deployment_readiness_surface",
    "fresh_price_quote",
}


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


def add_check(checks: list[dict[str, Any]], name: str, ok: bool, detail: Any = None, severity: str = "critical") -> None:
    checks.append({"name": name, "ok": bool(ok), "status": "ok" if ok else "fail", "severity": severity, "detail": detail})


def production_entries(universe: dict[str, Any]) -> list[dict[str, Any]]:
    migrated = legacy_42_tier_entries()
    if migrated:
        return migrated
    rows = [
        row
        for row in as_list(universe.get("entries"))
        if isinstance(row, dict)
        and row.get("active") is not False
        and (row.get("production_scope") is True or row.get("universe_scope") == "production_current_42")
    ]
    rows.sort(key=lambda row: str(row.get("ticker") or ""))
    return rows


def card_for(ticker: str) -> dict[str, Any]:
    return load_dict(CARD_DIR / f"{ticker}.current.json")


def rec_posture(card: dict[str, Any]) -> str:
    support = as_dict(card.get("recommendation_support"))
    return str(support.get("posture_key") or support.get("posture") or "unknown")


def band_status(card: dict[str, Any]) -> str:
    support = as_dict(card.get("recommendation_support"))
    band = support.get("band_status")
    if band is None:
        band = as_dict(card.get("price_band_stop")).get("band_status")
    return str(band or "UNKNOWN")


def state_source(card: dict[str, Any], entry: dict[str, Any]) -> str:
    support = as_dict(card.get("recommendation_support"))
    source = support.get("state_source") or support.get("readiness_state_source") or support.get("deployment_surface_state_source")
    if source:
        return str(source)
    return str(as_dict(entry.get("coverage_reason")).get("workflow_state") or "UNKNOWN")


def missing_items(card: dict[str, Any]) -> list[dict[str, Any]]:
    return [item for item in as_list(card.get("missing_or_stale_evidence")) if isinstance(item, dict)]


def risk_items(card: dict[str, Any]) -> list[dict[str, Any]]:
    return [item for item in as_list(card.get("risk_register")) if isinstance(item, dict)]


def score_entry(entry: dict[str, Any], card: dict[str, Any]) -> dict[str, Any]:
    score = 50
    reasons: list[str] = []
    blockers: list[str] = []
    repair_items: list[str] = []

    legacy_tier = str(entry.get("tier") or "C")
    monitoring_role = str(entry.get("monitoring_role") or "unknown")
    workflow_state = state_source(card, entry)
    posture = rec_posture(card)
    band = band_status(card)
    technical = as_dict(card.get("technical_posture"))
    valuation = as_dict(card.get("valuation"))
    support = as_dict(card.get("recommendation_support"))

    if legacy_tier == "A":
        score += 15
        reasons.append("legacy Tier A monitoring label")
    elif legacy_tier == "B":
        score += 10
        reasons.append("legacy Tier B monitoring label")

    role_points = {
        "decision_queue_or_near_action": 18,
        "priority_watch": 10,
        "sector_or_thematic_monitor": 6,
        "review_100_thin_monitor": 2,
        "tier_c_review_monitor_breadth_only": 0,
    }.get(monitoring_role, 0)
    score += role_points
    if role_points:
        reasons.append(f"monitoring role {monitoring_role}")

    state_points = {
        "DEPLOYABLE NOW": 22,
        "ALMOST DEPLOYABLE": 16,
        "PROMOTION REVIEW": 14,
        "WATCH": 6,
        "REPAIR": -8,
        "SYSTEM HOLD": -4,
    }.get(workflow_state, 0)
    score += state_points
    if state_points:
        reasons.append(f"state {workflow_state}")

    posture_points = {
        "approval_ready_if_fresh": 24,
        "approval-ready paper starter if fresh in band": 24,
        "promotion_review": 16,
        "promotion review": 16,
        "no_chase": 4,
        "no chase": 4,
        "blocked_stale": -16,
        "blocked stale": -16,
    }.get(posture, 0)
    score += posture_points
    if posture_points:
        reasons.append(f"recommendation posture {posture}")

    if band == "IN_BAND":
        score += 18
        reasons.append("in written band")
    elif band == "ABOVE_BAND":
        score -= 6
        blockers.append("above written band / no-chase discipline")
    elif band == "BELOW_STOP":
        score -= 28
        blockers.append("below stop or invalidation")
    else:
        score -= 10
        blockers.append("missing current band status")

    ma_posture = str(technical.get("ma_posture") or "")
    if "above all MAs" in ma_posture:
        score += 8
        reasons.append("strong moving-average stack")
    elif "above 50d and 200d" in ma_posture:
        score += 6
        reasons.append("above 50d and 200d")
    elif "below all MAs" in ma_posture:
        score -= 10
        blockers.append("below all major moving averages")
    elif ma_posture:
        score += 2

    macro_gate = technical.get("macro_gate")
    if macro_gate == "CLEAN":
        score += 4
    elif macro_gate == "DEGRADED":
        score -= 4
        repair_items.append("macro/technical gate degraded")

    forward_pe = valuation.get("forward_pe")
    if isinstance(forward_pe, (int, float)):
        if forward_pe <= 25:
            score += 6
        elif forward_pe <= 35:
            score += 3
        elif forward_pe > 60:
            score -= 6
            repair_items.append("high forward valuation")

    for item in missing_items(card):
        family = str(item.get("family") or "unknown")
        severity = str(item.get("severity") or "")
        status = str(item.get("status") or "")
        repair_items.append(f"{family}:{status or severity}")
        if severity == "blocking" or family in TIER_A_BLOCKING_FAMILIES:
            score -= 14
            blockers.append(f"evidence gap: {family}")
        elif status == "stale_until_refreshed":
            score -= 6
            blockers.append(f"stale evidence: {family}")
        elif severity == "review_required":
            score -= 5
            repair_items.append(f"review required: {family}")

    critical_risks = 0
    warning_risks = 0
    for item in risk_items(card):
        severity = str(item.get("severity") or "")
        if severity == "critical":
            critical_risks += 1
        elif severity == "warning":
            warning_risks += 1
    score -= critical_risks * 8
    score -= min(warning_risks, 4) * 2
    if critical_risks:
        blockers.append(f"{critical_risks} critical risk flag(s)")
    if warning_risks:
        repair_items.append(f"{warning_risks} warning risk flag(s)")

    if support.get("fresh_quote_required") is True:
        blockers.append("fresh quote required before final use")

    score = max(0, min(100, int(round(score))))
    return {
        "score": score,
        "legacy_tier": legacy_tier,
        "monitoring_role": monitoring_role,
        "workflow_state": workflow_state,
        "recommendation_posture": posture,
        "band_status": band,
        "reasons": sorted(set(reasons)),
        "blockers": sorted(set(blockers)),
        "repair_items": sorted(set(repair_items)),
        "tier_a_hard_blocked": bool(blockers),
        "formal_admission_allowed_now": False,
    }


def recommendation_for(index: int, scored: dict[str, Any]) -> tuple[str, str]:
    blockers = as_list(scored.get("blockers"))
    score = int(scored.get("score") or 0)
    if index <= TIER_A_REVIEW_CAP and score >= 50:
        if blockers:
            return "Tier A watchlist candidate - repair required before admission", "A_REPAIR"
        return "Tier A owner-review candidate", "A_REVIEW"
    if score >= 35:
        return "Tier B active research bench", "B_RESEARCH"
    return "Tier C monitor or repair backlog", "C_MONITOR_REPAIR"


def build_report() -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    universe = load_dict(UNIVERSE)
    capacity_gate = load_dict(CAPACITY_GATE)
    promotion_gate = load_dict(PROMOTION_REVIEW_GATE)
    refresh_gate = load_dict(TICKER_CARD_REFRESH_GATE)
    entries = production_entries(universe)

    rows: list[dict[str, Any]] = []
    for entry in entries:
        ticker = str(entry.get("ticker") or "").upper()
        card = card_for(ticker)
        scored = score_entry(entry, card)
        rows.append(
            {
                "ticker": ticker,
                "name": entry.get("name") or card.get("name") or card.get("company_name"),
                "sector": entry.get("sector"),
                "instrument_type": entry.get("instrument_type"),
                "score": scored["score"],
                "legacy_tier": scored["legacy_tier"],
                "monitoring_role": scored["monitoring_role"],
                "workflow_state": scored["workflow_state"],
                "recommendation_posture": scored["recommendation_posture"],
                "band_status": scored["band_status"],
                "tier_a_hard_blocked": scored["tier_a_hard_blocked"],
                "formal_admission_allowed_now": False,
                "reasons": scored["reasons"],
                "blockers": scored["blockers"],
                "repair_items": scored["repair_items"],
            }
        )

    rows.sort(key=lambda row: (-int(row["score"]), str(row["ticker"])))
    for index, row in enumerate(rows, start=1):
        recommendation, bucket = recommendation_for(index, row)
        row["rank"] = index
        row["recommended_bucket"] = bucket
        row["recommendation"] = recommendation

    bucket_counts = Counter(str(row["recommended_bucket"]) for row in rows)
    sector_counts = Counter(str(row.get("sector") or "Unknown") for row in rows)

    add_check(checks, "universe_exists", UNIVERSE.exists(), rel(UNIVERSE))
    add_check(checks, "production_42_count", len(entries) == 42, {"count": len(entries), "expected": 42})
    add_check(checks, "ticker_cards_present_for_all_42", all((CARD_DIR / f"{row['ticker']}.current.json").exists() for row in rows), [row["ticker"] for row in rows if not (CARD_DIR / f"{row['ticker']}.current.json").exists()])
    add_check(checks, "capacity_gate_validation_ok", as_dict(capacity_gate.get("validation")).get("status") == "ok", as_dict(capacity_gate.get("validation")))
    add_check(checks, "promotion_review_gate_validation_ok", as_dict(promotion_gate.get("validation")).get("status") == "ok", as_dict(promotion_gate.get("validation")))
    add_check(checks, "ticker_card_refresh_validation_ok", as_dict(refresh_gate.get("validation")).get("status") == "ok", as_dict(refresh_gate.get("validation")))
    add_check(checks, "tier_a_review_candidate_cap_respected", bucket_counts.get("A_REVIEW", 0) + bucket_counts.get("A_REPAIR", 0) <= TIER_A_REVIEW_CAP, dict(bucket_counts))
    add_check(checks, "no_formal_admission_allowed", all(row["formal_admission_allowed_now"] is False for row in rows), None)
    add_check(checks, "blocked_rows_not_marked_formally_admitted", all(row["formal_admission_allowed_now"] is False for row in rows if row["tier_a_hard_blocked"]), None)
    for flag in REQUIRED_TRUE_FLAGS:
        add_check(checks, f"authority_{flag}_true", AUTHORITY_BOUNDARY.get(flag) is True, AUTHORITY_BOUNDARY.get(flag))
    for flag in REQUIRED_FALSE_FLAGS:
        add_check(checks, f"authority_{flag}_false", AUTHORITY_BOUNDARY.get(flag) is False, AUTHORITY_BOUNDARY.get(flag))

    errors = [check for check in checks if check["severity"] == "critical" and not check["ok"]]
    warnings = [check for check in checks if check["severity"] == "warning" and not check["ok"]]
    validation_status = "ok" if not errors else "error"
    status = "ok" if validation_status == "ok" else "blocked"

    top_a = [row for row in rows if row["recommended_bucket"] in {"A_REVIEW", "A_REPAIR"}]
    b_rows = [row for row in rows if row["recommended_bucket"] == "B_RESEARCH"]
    c_rows = [row for row in rows if row["recommended_bucket"] == "C_MONITOR_REPAIR"]

    return {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": status,
        "workflow": "WF78 - 42 Production Tier A/B Adjudication",
        "purpose": "Recommend a provisional Tier A review slate and Tier B bench from the 42 production answer-path tickers without admitting, promoting, applying, or authorizing action.",
        "authority_boundary": AUTHORITY_BOUNDARY,
        "source_artifacts": {
            "universe": rel(UNIVERSE),
            "legacy_42_tier_shadow": legacy_42_tier_source_summary(),
            "capacity_gate": rel(CAPACITY_GATE),
            "promotion_review_gate": rel(PROMOTION_REVIEW_GATE),
            "ticker_card_refresh_gate": rel(TICKER_CARD_REFRESH_GATE),
            "ticker_cards": rel(CARD_DIR),
        },
        "policy": {
            "production_answer_path_is_not_tier_admission": True,
            "tier_a_review_cap": TIER_A_REVIEW_CAP,
            "tier_b_research_cap": TIER_B_RESEARCH_CAP,
            "formal_tier_admission_requires_owner_approval": True,
            "fresh_quote_source_open_required_before_final_recommendation": True,
        },
        "summary": {
            "production_ticker_count": len(rows),
            "bucket_counts": dict(sorted(bucket_counts.items())),
            "sector_counts": dict(sorted(sector_counts.items())),
            "tier_a_review_candidate_count": len(top_a),
            "tier_b_research_count": len(b_rows),
            "tier_c_monitor_or_repair_count": len(c_rows),
            "formal_admission_allowed_count": 0,
            "top_tier_a_review_candidates": [row["ticker"] for row in top_a],
            "tier_b_research_bench": [row["ticker"] for row in b_rows],
            "next_safe_action": "Source-open and freshness-repair the Tier A review slate, then build an owner decision packet for actual Tier A/B admission.",
        },
        "rows": rows,
        "owner_review_packet": {
            "exact_owner_question": "Approve this provisional Tier A review slate and Tier B bench as labels only, with no trade/account/canon/portfolio action?",
            "recommended_answer": "review_after_freshness_repair_not_auto_apply",
            "tier_a_review_slate": [
                {
                    "rank": row["rank"],
                    "ticker": row["ticker"],
                    "name": row["name"],
                    "score": row["score"],
                    "recommendation": row["recommendation"],
                    "blockers": row["blockers"],
                }
                for row in top_a
            ],
            "tier_b_bench": [
                {
                    "rank": row["rank"],
                    "ticker": row["ticker"],
                    "name": row["name"],
                    "score": row["score"],
                    "blockers": row["blockers"],
                }
                for row in b_rows
            ],
        },
        "validation": {
            "status": validation_status,
            "errors": errors,
            "warnings": warnings,
            "checks": checks,
        },
        "stop_lines": [
            "No formal Tier A/B admission from this packet.",
            "No production answer-path change.",
            "No ticker import/apply.",
            "No canon/portfolio mutation.",
            "No customer/external delivery.",
            "No paper/live/brokerage/account action.",
            "No owner approval inference.",
        ],
    }


def write_db(report: dict[str, Any], path: Path) -> None:
    rows = as_list(report.get("rows"))
    if path.exists():
        path.unlink()
    conn = sqlite3.connect(path)
    try:
        conn.execute(
            """
            CREATE TABLE tier_adjudication (
                rank INTEGER PRIMARY KEY,
                ticker TEXT NOT NULL,
                name TEXT,
                sector TEXT,
                score INTEGER NOT NULL,
                recommended_bucket TEXT NOT NULL,
                recommendation TEXT NOT NULL,
                legacy_tier TEXT,
                monitoring_role TEXT,
                workflow_state TEXT,
                recommendation_posture TEXT,
                band_status TEXT,
                tier_a_hard_blocked INTEGER NOT NULL,
                formal_admission_allowed_now INTEGER NOT NULL,
                blockers_json TEXT NOT NULL,
                repair_items_json TEXT NOT NULL
            )
            """
        )
        for row in rows:
            conn.execute(
                """
                INSERT INTO tier_adjudication (
                    rank, ticker, name, sector, score, recommended_bucket,
                    recommendation, legacy_tier, monitoring_role, workflow_state,
                    recommendation_posture, band_status, tier_a_hard_blocked,
                    formal_admission_allowed_now, blockers_json, repair_items_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    row.get("rank"),
                    row.get("ticker"),
                    row.get("name"),
                    row.get("sector"),
                    row.get("score"),
                    row.get("recommended_bucket"),
                    row.get("recommendation"),
                    row.get("legacy_tier"),
                    row.get("monitoring_role"),
                    row.get("workflow_state"),
                    row.get("recommendation_posture"),
                    row.get("band_status"),
                    1 if row.get("tier_a_hard_blocked") else 0,
                    1 if row.get("formal_admission_allowed_now") else 0,
                    json.dumps(row.get("blockers") or [], sort_keys=True),
                    json.dumps(row.get("repair_items") or [], sort_keys=True),
                ),
            )
        conn.execute(
            """
            CREATE TABLE summary (
                key TEXT PRIMARY KEY,
                value_json TEXT NOT NULL
            )
            """
        )
        for key, value in as_dict(report.get("summary")).items():
            conn.execute("INSERT INTO summary (key, value_json) VALUES (?, ?)", (key, json.dumps(value, sort_keys=True)))
        conn.commit()
    finally:
        conn.close()


def validate_db(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"status": "missing", "path": rel(path)}
    conn = sqlite3.connect(path)
    try:
        integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
        row_count = conn.execute("SELECT COUNT(*) FROM tier_adjudication").fetchone()[0]
        formal_count = conn.execute("SELECT COUNT(*) FROM tier_adjudication WHERE formal_admission_allowed_now != 0").fetchone()[0]
        return {
            "status": "ok" if integrity == "ok" and row_count == 42 and formal_count == 0 else "error",
            "path": rel(path),
            "integrity_check": integrity,
            "row_count": row_count,
            "formal_admission_allowed_count": formal_count,
            "authority_boundary": "Derived review lookup only; JSON remains proof. No admission, apply, canon/portfolio, account, or execution authority.",
        }
    finally:
        conn.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true", help="write JSON output")
    parser.add_argument("--write-db", action="store_true", help="write SQLite lookup output")
    parser.add_argument("--validate", action="store_true", help="exit non-zero on validation failure")
    parser.add_argument("--out", default=str(DEFAULT_OUT), help="JSON output path")
    parser.add_argument("--db", default=str(DEFAULT_DB), help="SQLite output path")
    args = parser.parse_args()

    report = build_report()
    out_path = Path(args.out)
    db_path = Path(args.db)
    if args.write:
        atomic_write_json(out_path, report)
    db_status = None
    if args.write_db:
        write_db(report, db_path)
        db_status = validate_db(db_path)
        report["sqlite"] = db_status
        if args.write:
            atomic_write_json(out_path, report)
    if args.validate and as_dict(report.get("validation")).get("status") != "ok":
        print(json.dumps({"status": report.get("status"), "validation": report.get("validation"), "out": rel(out_path)}, indent=2))
        return 1
    if args.validate and db_status and db_status.get("status") != "ok":
        print(json.dumps({"status": report.get("status"), "validation": report.get("validation"), "sqlite": db_status, "out": rel(out_path)}, indent=2))
        return 1
    print(
        json.dumps(
            {
                "status": report.get("status"),
                "out": rel(out_path),
                "sqlite": db_status,
                "summary": report.get("summary"),
                "validation": {
                    "status": as_dict(report.get("validation")).get("status"),
                    "errors": len(as_list(as_dict(report.get("validation")).get("errors"))),
                    "warnings": len(as_list(as_dict(report.get("validation")).get("warnings"))),
                },
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
