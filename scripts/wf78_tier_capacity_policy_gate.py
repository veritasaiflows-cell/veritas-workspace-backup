#!/usr/bin/env python3
"""Enforce the lightweight WF78 Tier A/B capacity policy.

This gate turns Randall's 25/50 operating preference into repeatable proof:
Tier A is capped at 25, Tier B is capped at 50, and the combined research plus
deployment bench is capped at 75. It is report-only. It never promotes a ticker,
imports a batch, mutates canon/portfolio state, infers approval, or authorizes
paper/live/account action.
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


ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
DATA = ROOT / "data"

UNIVERSE = DATA / "finance" / "universe-v1.json"
TIER_PROMOTION_REVIEW_GATE = TMP / "wf78-tier-promotion-review-gate.json"
MACRO_THESIS_OVERLAY_GATE = TMP / "wf78-macro-thesis-overlay-gate.json"
TICKER_CARD_REFRESH_GATE = TMP / "finance-ticker-card-refresh-gate.json"
REPUTATION_GATE = TMP / "wf78-500-ticker-reputation-gate.json"

DEFAULT_OUT = TMP / "wf78-tier-capacity-policy-gate.json"
DEFAULT_DB = TMP / "wf78-tier-capacity-policy-gate.sqlite"
SCHEMA = "veritas.wf78_tier_capacity_policy_gate.v1"

TIER_A_CAP = 25
TIER_B_CAP = 50
TIER_A_B_COMBINED_CAP = 75
ACTIVE_CAPITAL_ACTION_CANDIDATE_CAP = 15
TIER_B_BATCH_NOMINATION_LIMIT = 15

AUTHORITY_BOUNDARY: dict[str, bool] = {
    "review_only": True,
    "report_only": True,
    "policy_gate_only": True,
    "ticker_import_allowed": False,
    "apply_allowed": False,
    "tier_b_promotion_allowed": False,
    "tier_a_promotion_allowed": False,
    "capital_deployment_allowed": False,
    "production_answer_path_change_allowed": False,
    "canon_or_portfolio_mutation_allowed": False,
    "customer_or_external_delivery_allowed": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "owner_approval_inferred": False,
}

REQUIRED_TRUE_FLAGS = {"review_only", "report_only", "policy_gate_only"}
REQUIRED_FALSE_FLAGS = {
    "ticker_import_allowed",
    "apply_allowed",
    "tier_b_promotion_allowed",
    "tier_a_promotion_allowed",
    "capital_deployment_allowed",
    "production_answer_path_change_allowed",
    "canon_or_portfolio_mutation_allowed",
    "customer_or_external_delivery_allowed",
    "paper_or_live_execution_allowed",
    "brokerage_or_account_action_allowed",
    "owner_approval_inferred",
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


def json_text(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def add_check(checks: list[dict[str, Any]], name: str, ok: bool, detail: Any = None, severity: str = "critical") -> None:
    checks.append({"name": name, "ok": bool(ok), "status": "ok" if ok else "fail", "severity": severity, "detail": detail})


def active_entries(universe: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        entry
        for entry in as_list(universe.get("entries"))
        if isinstance(entry, dict) and entry.get("active") is not False
    ]


def admission_counts(tier_gate: dict[str, Any]) -> dict[str, int]:
    summary = as_dict(tier_gate.get("summary"))
    return {
        "tier_a_admitted_or_deployment_ready_count": int(summary.get("tier_a_deployment_eligible_now_count") or 0),
        "tier_b_admitted_or_research_ready_count": int(summary.get("tier_b_research_eligible_now_count") or 0),
    }


def build_report() -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    universe = load_dict(UNIVERSE)
    tier_gate = load_dict(TIER_PROMOTION_REVIEW_GATE)
    macro_gate = load_dict(MACRO_THESIS_OVERLAY_GATE)
    card_gate = load_dict(TICKER_CARD_REFRESH_GATE)
    reputation_gate = load_dict(REPUTATION_GATE)

    entries = active_entries(universe)
    legacy_tier_counts = Counter(str(entry.get("tier") or "Unassigned") for entry in entries)
    scope_counts = Counter(str(entry.get("universe_scope") or "unknown") for entry in entries)
    monitoring_role_counts = Counter(str(entry.get("monitoring_role") or "unknown") for entry in entries)
    counts = admission_counts(tier_gate)
    tier_a_count = counts["tier_a_admitted_or_deployment_ready_count"]
    tier_b_count = counts["tier_b_admitted_or_research_ready_count"]
    combined_count = tier_a_count + tier_b_count
    macro_shortlist_count = int(as_dict(macro_gate.get("summary")).get("tier_b_research_shortlist_count") or 0)

    add_check(checks, "tier_a_cap_is_25", TIER_A_CAP == 25, TIER_A_CAP)
    add_check(checks, "tier_b_cap_is_50", TIER_B_CAP == 50, TIER_B_CAP)
    add_check(checks, "combined_cap_is_75", TIER_A_B_COMBINED_CAP == 75, TIER_A_B_COMBINED_CAP)
    add_check(checks, "active_capital_action_cap_is_15", ACTIVE_CAPITAL_ACTION_CANDIDATE_CAP == 15, ACTIVE_CAPITAL_ACTION_CANDIDATE_CAP)
    add_check(checks, "batch_nomination_limit_is_15", TIER_B_BATCH_NOMINATION_LIMIT == 15, TIER_B_BATCH_NOMINATION_LIMIT)
    add_check(checks, "universe_exists", UNIVERSE.exists(), rel(UNIVERSE))
    add_check(checks, "tier_promotion_gate_exists", TIER_PROMOTION_REVIEW_GATE.exists(), rel(TIER_PROMOTION_REVIEW_GATE))
    add_check(checks, "tier_promotion_gate_validation_ok", as_dict(tier_gate.get("validation")).get("status") == "ok", as_dict(tier_gate.get("validation")))
    add_check(checks, "macro_overlay_gate_exists", MACRO_THESIS_OVERLAY_GATE.exists(), rel(MACRO_THESIS_OVERLAY_GATE))
    add_check(checks, "macro_overlay_gate_validation_ok", as_dict(macro_gate.get("validation")).get("status") == "ok", as_dict(macro_gate.get("validation")))
    add_check(checks, "ticker_card_refresh_gate_exists", TICKER_CARD_REFRESH_GATE.exists(), rel(TICKER_CARD_REFRESH_GATE))
    add_check(checks, "ticker_card_refresh_gate_validation_ok", as_dict(card_gate.get("validation")).get("status") == "ok", as_dict(card_gate.get("validation")))
    add_check(checks, "reputation_gate_exists", REPUTATION_GATE.exists(), rel(REPUTATION_GATE))
    add_check(checks, "reputation_gate_validation_ok", as_dict(reputation_gate.get("validation")).get("status") == "ok", as_dict(reputation_gate.get("validation")))
    add_check(checks, "tier_a_within_capacity", tier_a_count <= TIER_A_CAP, {"count": tier_a_count, "cap": TIER_A_CAP})
    add_check(checks, "tier_b_within_capacity", tier_b_count <= TIER_B_CAP, {"count": tier_b_count, "cap": TIER_B_CAP})
    add_check(checks, "combined_tier_a_b_within_capacity", combined_count <= TIER_A_B_COMBINED_CAP, {"count": combined_count, "cap": TIER_A_B_COMBINED_CAP})
    add_check(checks, "macro_shortlist_within_batch_nomination_limit", macro_shortlist_count <= TIER_B_BATCH_NOMINATION_LIMIT, {"count": macro_shortlist_count, "cap": TIER_B_BATCH_NOMINATION_LIMIT})
    add_check(checks, "legacy_tier_labels_not_treated_as_admission", True, dict(sorted(legacy_tier_counts.items())), "info")
    for flag in REQUIRED_TRUE_FLAGS:
        add_check(checks, f"authority_{flag}_true", AUTHORITY_BOUNDARY.get(flag) is True, AUTHORITY_BOUNDARY.get(flag))
    for flag in REQUIRED_FALSE_FLAGS:
        add_check(checks, f"authority_{flag}_false", AUTHORITY_BOUNDARY.get(flag) is False, AUTHORITY_BOUNDARY.get(flag))

    errors = [check for check in checks if check["severity"] == "critical" and not check["ok"]]
    warnings = [check for check in checks if check["severity"] == "warning" and not check["ok"]]
    status = "ok" if not errors else "blocked"
    return {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": status,
        "workflow": "WF78 - Lightweight Tier Capacity Policy",
        "purpose": "Machine-enforce Randall's lightweight Tier A/B ceilings while preserving Tier C/D breadth.",
        "policy": {
            "tier_a_max": TIER_A_CAP,
            "tier_b_max": TIER_B_CAP,
            "tier_a_b_combined_max": TIER_A_B_COMBINED_CAP,
            "active_capital_action_candidate_max": ACTIVE_CAPITAL_ACTION_CANDIDATE_CAP,
            "tier_b_batch_nomination_limit": TIER_B_BATCH_NOMINATION_LIMIT,
            "overflow_rule": "Anything beyond capacity remains Tier C review-monitor or Tier D raw/validation/watch.",
            "override_rule": "No override without exact owner approval and a separate gate.",
        },
        "authority_boundary": AUTHORITY_BOUNDARY,
        "source_artifacts": {
            "universe": rel(UNIVERSE),
            "tier_promotion_review_gate": rel(TIER_PROMOTION_REVIEW_GATE),
            "macro_thesis_overlay_gate": rel(MACRO_THESIS_OVERLAY_GATE),
            "ticker_card_refresh_gate": rel(TICKER_CARD_REFRESH_GATE),
            "reputation_gate": rel(REPUTATION_GATE),
        },
        "summary": {
            "status": status,
            "active_ticker_count": len(entries),
            "legacy_universe_tier_counts": dict(sorted(legacy_tier_counts.items())),
            "legacy_tier_label_note": "Universe A/B/C labels are monitoring metadata and are not Tier A/B admission or capital-readiness proof.",
            "universe_scope_counts": dict(sorted(scope_counts.items())),
            "monitoring_role_counts": dict(sorted(monitoring_role_counts.items())),
            "tier_a_admitted_or_deployment_ready_count": tier_a_count,
            "tier_b_admitted_or_research_ready_count": tier_b_count,
            "tier_a_b_combined_count": combined_count,
            "tier_a_remaining_capacity": max(0, TIER_A_CAP - tier_a_count),
            "tier_b_remaining_capacity": max(0, TIER_B_CAP - tier_b_count),
            "combined_remaining_capacity": max(0, TIER_A_B_COMBINED_CAP - combined_count),
            "macro_thesis_shortlist_count": macro_shortlist_count,
            "current_capital_ready_count": int(as_dict(macro_gate.get("summary")).get("capital_deployment_ready_count") or 0),
            "ticker_card_decision_ready_count": int(as_dict(as_dict(card_gate.get("summary")).get("card_rollup")).get("decision_ready_card_count") or 0),
            "next_safe_action": "Use the 15-name macro shortlist as Tier B research-candidate work queue only; admit names into Tier B only after full research packets pass capacity and evidence gates.",
        },
        "tier_c_d_usage_model": {
            "tier_c": "Primary breadth layer: monitor signals, macro/theme cues, repair state, and shortlist nominations without investability claims.",
            "tier_d": "Raw/validation/watch layer: hold weak, incomplete, duplicate, stale, or low-conviction names until identity/source/macro evidence improves.",
            "scale_rule": "Each 100-name batch may nominate a small Tier B research queue, but capacity prevents automatic promotion.",
        },
        "admission_requirements": {
            "tier_b": [
                "macro/theme fit",
                "company fundamentals snapshot",
                "valuation context",
                "analyst layer",
                "technical/price-band/stop context",
                "thesis and counter-thesis",
                "risk/invalidation",
                "source-open proof",
                "portfolio-fit/concentration check",
            ],
            "tier_a": [
                "fresh ticker card",
                "fresh price/band/stop",
                "deployment/readiness state",
                "position sizing/staggering logic",
                "portfolio concentration fit",
                "approval-ready recommendation packet",
                "exact owner approval before action",
            ],
        },
        "repeatable_sequence": [
            "Run wf78_tier_capacity_policy_gate.py --write --write-db --validate before every promotion-review pass.",
            "Run macro/thesis overlay after each approved Tier C batch to nominate, not promote, the top research leads.",
            "Keep Tier B admissions under 50 and Tier A admissions under 25.",
            "Send overflow and incomplete names back to Tier C or Tier D with named evidence gaps.",
            "Require stale-card repair and full research packets before any Tier B/A admission.",
        ],
        "validation": {
            "status": "ok" if not errors else "error",
            "errors": errors,
            "warnings": warnings,
            "checks": checks,
        },
        "stop_lines": [
            "No Tier A/B admission from legacy universe labels.",
            "No promotion from Tier C existence or macro shortlist membership.",
            "No import/apply authority.",
            "No production answer-path expansion.",
            "No capital deployment, paper/live/account action, or owner approval inference.",
            "No canon/portfolio mutation.",
        ],
    }


def connect_write(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute("PRAGMA synchronous=NORMAL")
    return conn


def write_db(report: dict[str, Any], db_path: Path) -> None:
    with connect_write(db_path) as conn:
        conn.executescript(
            """
            DROP TABLE IF EXISTS policy;
            DROP TABLE IF EXISTS capacity;
            DROP TABLE IF EXISTS authority_boundary;
            DROP TABLE IF EXISTS validation_checks;
            DROP TABLE IF EXISTS meta;

            CREATE TABLE policy (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            ) STRICT;

            CREATE TABLE capacity (
                tier TEXT PRIMARY KEY,
                current_count INTEGER NOT NULL,
                cap INTEGER NOT NULL,
                remaining INTEGER NOT NULL,
                ok INTEGER NOT NULL CHECK (ok IN (0,1))
            ) STRICT;

            CREATE TABLE authority_boundary (
                flag TEXT PRIMARY KEY,
                value INTEGER NOT NULL CHECK (value IN (0,1)),
                required_value INTEGER NOT NULL CHECK (required_value IN (0,1)),
                ok INTEGER NOT NULL CHECK (ok IN (0,1))
            ) STRICT;

            CREATE TABLE validation_checks (
                name TEXT PRIMARY KEY,
                ok INTEGER NOT NULL CHECK (ok IN (0,1)),
                severity TEXT NOT NULL,
                detail_json TEXT NOT NULL
            ) STRICT;

            CREATE TABLE meta (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            ) STRICT;
            """
        )
        policy = as_dict(report.get("policy"))
        summary = as_dict(report.get("summary"))
        for key, value in policy.items():
            conn.execute("INSERT INTO policy VALUES (?,?)", (str(key), json_text(value)))
        capacity_rows = [
            ("tier_a", int(summary.get("tier_a_admitted_or_deployment_ready_count") or 0), TIER_A_CAP, int(summary.get("tier_a_remaining_capacity") or 0)),
            ("tier_b", int(summary.get("tier_b_admitted_or_research_ready_count") or 0), TIER_B_CAP, int(summary.get("tier_b_remaining_capacity") or 0)),
            ("tier_a_b_combined", int(summary.get("tier_a_b_combined_count") or 0), TIER_A_B_COMBINED_CAP, int(summary.get("combined_remaining_capacity") or 0)),
        ]
        for tier, count, cap, remaining in capacity_rows:
            conn.execute("INSERT INTO capacity VALUES (?,?,?,?,?)", (tier, count, cap, remaining, 1 if count <= cap else 0))
        for flag, value in AUTHORITY_BOUNDARY.items():
            required = True if flag in REQUIRED_TRUE_FLAGS else False if flag in REQUIRED_FALSE_FLAGS else bool(value)
            conn.execute("INSERT INTO authority_boundary VALUES (?,?,?,?)", (flag, 1 if value else 0, 1 if required else 0, 1 if bool(value) == required else 0))
        for check in as_list(as_dict(report.get("validation")).get("checks")):
            conn.execute("INSERT INTO validation_checks VALUES (?,?,?,?)", (check.get("name"), 1 if check.get("ok") else 0, check.get("severity"), json_text(check.get("detail"))))
        for key in ("schema", "generated_at_utc", "status", "summary"):
            conn.execute("INSERT INTO meta VALUES (?,?)", (key, json_text(report.get(key))))
        conn.commit()


def resolve(path: Path) -> Path:
    return path if path.is_absolute() else ROOT / path


def validate_outputs(report: dict[str, Any], out: Path, db: Path, write: bool, write_db_flag: bool) -> list[str]:
    errors: list[str] = []
    if as_dict(report.get("validation")).get("status") != "ok":
        errors.append("report validation is not ok")
    if write:
        loaded = load_json_artifact(out)
        if not isinstance(loaded, dict) or loaded.get("schema") != SCHEMA:
            errors.append("main JSON missing or schema mismatch")
    if write_db_flag:
        if not db.exists():
            errors.append("SQLite output missing")
        else:
            with sqlite3.connect(str(db)) as conn:
                if conn.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                    errors.append("SQLite integrity_check failed")
                if conn.execute("SELECT count(*) FROM capacity WHERE ok=0").fetchone()[0]:
                    errors.append("capacity table has exceeded rows")
                if conn.execute("SELECT count(*) FROM authority_boundary WHERE ok=0").fetchone()[0]:
                    errors.append("authority boundary table has unsafe rows")
    return errors


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build WF78 Tier A/B capacity policy gate.")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--write-db", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    out = resolve(args.out)
    db = resolve(args.db)
    report = build_report()
    if args.write:
        atomic_write_json(out, report, ensure_ascii=False)
    if args.write_db:
        write_db(report, db)
    output_errors = validate_outputs(report, out, db, args.write, args.write_db)
    status = report["status"] if not output_errors else "blocked"
    print(
        json.dumps(
            {
                "status": status,
                "validation_status": as_dict(report.get("validation")).get("status"),
                "output_errors": output_errors,
                "out": rel(out) if args.write else None,
                "db": rel(db) if args.write_db else None,
                "summary": report.get("summary"),
            },
            indent=2,
            sort_keys=True,
        )
    )
    if args.validate and status != "ok":
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
