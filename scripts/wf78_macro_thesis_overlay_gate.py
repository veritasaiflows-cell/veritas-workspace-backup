"""Build the WF78 macro/thesis overlay for Tier C scaleout names.

The overlay ranks Tier C review-monitor names for possible Tier B research
work. It is a breadth triage layer, not a fundamental-vetting, promotion,
recommendation, capital-deployment, or portfolio-action surface.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCRIPTS = Path(__file__).resolve().parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from market_data_utils import atomic_write_json, load_json_artifact  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
DATA = ROOT / "data"

OWNER_PACKET = TMP / "wf78-101-200-tier-c-owner-decision-packet.json"
IMPORT_GATE = TMP / "wf78-101-200-tier-c-import-gate.json"
UNIVERSE = DATA / "finance" / "universe-v1.json"
MARKET_STATE = TMP / "market-state.json"
DASHBOARD_VALIDATION = TMP / "dashboard-validation.json"
MACRO_DASHBOARD = ROOT / "02. Markets" / "Macro Regime Dashboard.md"
WEEKLY_POSITIONING = ROOT / "05. Intelligence" / "Weekly Positioning Review.md"

DEFAULT_OUT_JSON = TMP / "wf78-macro-thesis-overlay-gate.json"
DEFAULT_OUT_DB = TMP / "wf78-macro-thesis-overlay-gate.sqlite"
SCHEMA = "veritas.wf78_macro_thesis_overlay_gate.v1"

TARGET_BATCH = "101-200"
SHORTLIST_LIMIT = 15
TIER_A_CAP = 25
TIER_B_CAP = 50
TIER_A_B_COMBINED_CAP = 75
ACTIVE_CAPITAL_ACTION_CANDIDATE_CAP = 15

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "ranking_triage_only": True,
    "full_macro_vetting_claim_allowed": False,
    "full_fundamental_vetting_claim_allowed": False,
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

REQUIRED_FALSE_FLAGS = {
    "full_macro_vetting_claim_allowed",
    "full_fundamental_vetting_claim_allowed",
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

THEME_RULES: list[dict[str, Any]] = [
    {
        "theme": "AI infrastructure and semiconductors",
        "keywords": ["semiconductor", "application software", "internet services", "technology hardware", "communications equipment", "electronic components", "it consulting"],
        "sectors": {"Information Technology", "Communication Services"},
        "require_keyword": True,
        "macro_fit": "Technology remains an improving-leadership cue, but long rates keep valuation discipline active.",
        "score": 23,
    },
    {
        "theme": "Electrification, infrastructure, and industrial automation",
        "keywords": ["electrical", "building products", "machinery", "aerospace", "industrial", "construction", "automation"],
        "sectors": {"Industrials", "Materials"},
        "macro_fit": "Selective risk-on and infrastructure/electrification relevance support research triage, not chase.",
        "score": 20,
    },
    {
        "theme": "Energy and energy infrastructure",
        "keywords": ["oil", "gas", "energy", "drilling", "pipeline", "exploration"],
        "sectors": {"Energy"},
        "macro_fit": "Oil and energy remain macro-relevant pressure points; name-level repair and volatility checks are required.",
        "score": 19,
    },
    {
        "theme": "Financial quality and alternative assets",
        "keywords": ["insurance", "asset management", "capital markets", "financial", "banks", "services"],
        "sectors": {"Financials"},
        "macro_fit": "Benign credit and positive curve support selective financial research, but bank/credit details still matter.",
        "score": 18,
    },
    {
        "theme": "Health care quality and tools",
        "keywords": ["health", "pharmaceutical", "biotechnology", "life sciences", "medical", "tools"],
        "sectors": {"Health Care"},
        "macro_fit": "Health care is an underexposed lane and can add defensive quality, but fundamentals/catalysts decide.",
        "score": 15,
    },
    {
        "theme": "Defensive cash-flow and rates-sensitive income",
        "keywords": ["utilities", "reit", "real estate", "consumer staples", "beverages", "household"],
        "sectors": {"Utilities", "Real Estate", "Consumer Staples"},
        "macro_fit": "Defensive and income-sensitive lanes need rate sensitivity checks before promotion.",
        "score": 11,
    },
]


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


def read_text(path: Path, limit: int = 4000) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="replace")[:limit]


def symbol(value: Any) -> str:
    return str(value or "").upper().strip()


def json_text(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def connect_write(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA synchronous=NORMAL")
    return conn


def macro_context() -> dict[str, Any]:
    market = load_dict(MARKET_STATE)
    dashboard = load_dict(DASHBOARD_VALIDATION)
    market_data = as_dict(market.get("data"))
    treasuries = as_dict(market_data.get("treasuries"))
    fed = as_dict(market_data.get("fed"))
    risk = as_dict(market_data.get("risk"))
    commodities = as_dict(market_data.get("commodities"))
    source_freshness = as_dict(dashboard.get("source_freshness"))
    return {
        "machine_evidence_status": "usable_with_caution" if market.get("status") in {"partial", "warning"} else (market.get("status") or "unknown"),
        "market_state_status": market.get("status"),
        "dashboard_overall_classification": source_freshness.get("overall_classification"),
        "dashboard_trust_level": source_freshness.get("trust_level"),
        "capital_recommendation_ready": source_freshness.get("capital_recommendation_ready"),
        "capital_action_allowed": source_freshness.get("capital_action_allowed"),
        "fed_target": {
            "low": fed.get("target_low"),
            "high": fed.get("target_high"),
            "next_fomc_date": fed.get("next_fomc_date"),
            "cut_probability_next_meeting": fed.get("cut_probability_next_meeting"),
        },
        "rates": {
            "two_year": treasuries.get("2y"),
            "ten_year": treasuries.get("10y"),
            "three_month": treasuries.get("3m"),
            "two_year_note": treasuries.get("2y_note"),
        },
        "risk_appetite": {
            "vix": risk.get("vix"),
            "spx": risk.get("spx"),
            "dxy": risk.get("dxy"),
        },
        "energy": {
            "brent": commodities.get("brent"),
            "wti": commodities.get("wti"),
        },
        "note_layer_cues": {
            "macro_dashboard_excerpt": read_text(MACRO_DASHBOARD, 1600),
            "weekly_positioning_excerpt": read_text(WEEKLY_POSITIONING, 1600),
        },
        "data_quality_note": (
            "Macro layer is review-usable only with caution: market-state is partial and dashboard validation is stale/review-required. "
            "This overlay can rank research leads, but it does not prove full macro or fundamental readiness."
        ),
    }


def candidate_rows() -> list[dict[str, Any]]:
    universe = load_dict(UNIVERSE)
    owner_packet = load_dict(OWNER_PACKET)
    imported = [
        row for row in as_list(universe.get("entries"))
        if isinstance(row, dict)
        and row.get("active") is not False
        and row.get("universe_scope") == "review_100_monitor"
        and row.get("review_monitor_scaleout_batch") == TARGET_BATCH
    ]
    if imported:
        return imported
    return [row for row in as_list(owner_packet.get("tickers")) if isinstance(row, dict)]


def theme_match(row: dict[str, Any]) -> dict[str, Any]:
    sector = str(row.get("sector") or "")
    industry = str(row.get("industry") or "").lower()
    name = str(row.get("name") or "").lower()
    best = {
        "theme": "General Tier C monitor",
        "score": 7,
        "macro_fit": "No strong macro/theme overlay yet; keep monitoring or require separate thesis work.",
    }
    for rule in THEME_RULES:
        keywords = [str(item).lower() for item in as_list(rule.get("keywords"))]
        keyword_hit = any(term in industry or term in name for term in keywords)
        sector_hit = sector in set(rule.get("sectors") or set())
        matched = keyword_hit if rule.get("require_keyword") is True else (keyword_hit or sector_hit)
        if matched and int(rule["score"]) > int(best["score"]):
            best = {"theme": rule["theme"], "score": rule["score"], "macro_fit": rule["macro_fit"]}
    return best


def score_candidate(row: dict[str, Any], macro: dict[str, Any]) -> dict[str, Any]:
    ticker = symbol(row.get("ticker"))
    theme = theme_match(row)
    base = int(row.get("reputation_score") or 75)
    score = min(100, round(base * 0.45 + int(theme["score"]) + 25))
    missing = as_list(row.get("not_decision_grade_because_missing")) or [
        "fundamentals",
        "analyst_layer",
        "valuation_layer",
        "technical_layer",
        "ticker_card",
        "entry_stop_band_context",
        "source_open_answer_contract",
        "owner_approval",
    ]
    return {
        "ticker": ticker,
        "name": row.get("name") or ticker,
        "sector": row.get("sector"),
        "industry": row.get("industry"),
        "overlay_score": score,
        "reputation_score": row.get("reputation_score"),
        "theme": theme["theme"],
        "macro_fit": theme["macro_fit"],
        "recommended_queue": "tier_b_research_candidate_shortlist" if score >= 78 else "keep_tier_c_monitor",
        "full_macro_vetted": False,
        "full_fundamentals_vetted": False,
        "capital_deployment_ready": False,
        "required_before_tier_b": [
            "fresh ticker card",
            "fundamentals",
            "analyst layer",
            "valuation context",
            "technical and entry/stop/band context",
            "thesis and counter-thesis",
            "official/source-open evidence",
            "portfolio fit and concentration check",
        ],
        "not_decision_grade_because_missing": missing,
        "data_quality_note": macro["data_quality_note"],
    }


def validation_checks(report: dict[str, Any]) -> list[dict[str, Any]]:
    summary = as_dict(report.get("summary"))
    authority = as_dict(report.get("authority_boundary"))
    shortlist = as_list(report.get("tier_b_research_shortlist"))
    rows = as_list(report.get("candidates"))
    checks = [
        {"name": "candidate_rows_present", "ok": len(rows) > 0, "detail": len(rows)},
        {"name": "shortlist_limit_respected", "ok": len(shortlist) <= SHORTLIST_LIMIT, "detail": len(shortlist)},
        {"name": "tier_a_capacity_policy_25", "ok": TIER_A_CAP == 25, "detail": TIER_A_CAP},
        {"name": "tier_b_capacity_policy_50", "ok": TIER_B_CAP == 50, "detail": TIER_B_CAP},
        {"name": "combined_capacity_policy_75", "ok": TIER_A_B_COMBINED_CAP == 75, "detail": TIER_A_B_COMBINED_CAP},
        {"name": "authority_false_flags_preserved", "ok": all(authority.get(flag) is False for flag in REQUIRED_FALSE_FLAGS), "detail": authority},
        {"name": "no_full_macro_or_fundamental_claim", "ok": summary.get("full_macro_vetted_count") == 0 and summary.get("full_fundamentals_vetted_count") == 0, "detail": summary},
        {"name": "no_capital_or_promotion_readiness", "ok": summary.get("capital_deployment_ready_count") == 0 and summary.get("tier_b_promoted_count") == 0 and summary.get("tier_a_promoted_count") == 0, "detail": summary},
        {"name": "import_gate_seen_or_owner_packet_available", "ok": IMPORT_GATE.exists() or OWNER_PACKET.exists(), "detail": {"import_gate": rel(IMPORT_GATE), "owner_packet": rel(OWNER_PACKET)}},
    ]
    return checks


def build_report() -> dict[str, Any]:
    macro = macro_context()
    candidates = [score_candidate(row, macro) for row in candidate_rows()]
    candidates.sort(key=lambda row: (-int(row["overlay_score"]), str(row["ticker"])))
    shortlist = [row for row in candidates if row["recommended_queue"] == "tier_b_research_candidate_shortlist"][:SHORTLIST_LIMIT]
    sector_counts = Counter(str(row.get("sector") or "Unknown") for row in candidates)
    theme_counts = Counter(str(row.get("theme") or "Unknown") for row in candidates)
    report = {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "ok",
        "target_batch": TARGET_BATCH,
        "authority_boundary": AUTHORITY_BOUNDARY,
        "source_artifacts": {
            "owner_packet": rel(OWNER_PACKET),
            "import_gate": rel(IMPORT_GATE),
            "universe": rel(UNIVERSE),
            "market_state": rel(MARKET_STATE),
            "dashboard_validation": rel(DASHBOARD_VALIDATION),
            "macro_dashboard": rel(MACRO_DASHBOARD),
            "weekly_positioning": rel(WEEKLY_POSITIONING),
        },
        "tier_capacity_policy": {
            "tier_a_max": TIER_A_CAP,
            "tier_b_max": TIER_B_CAP,
            "tier_a_b_combined_max": TIER_A_B_COMBINED_CAP,
            "active_capital_action_candidate_max": ACTIVE_CAPITAL_ACTION_CANDIDATE_CAP,
            "tier_b_batch_nomination_limit": SHORTLIST_LIMIT,
            "overflow_rule": "Names above capacity remain Tier C review-monitor or Tier D raw/validation/watch.",
        },
        "macro_context": macro,
        "summary": {
            "candidate_count": len(candidates),
            "tier_b_research_shortlist_count": len(shortlist),
            "tier_b_promoted_count": 0,
            "tier_a_promoted_count": 0,
            "capital_deployment_ready_count": 0,
            "full_macro_vetted_count": 0,
            "full_fundamentals_vetted_count": 0,
            "sector_counts": dict(sorted(sector_counts.items())),
            "theme_counts": dict(sorted(theme_counts.items())),
            "next_safe_action": "Use the shortlist to create bounded Tier B research packets; do not promote, recommend, size, or deploy without full evidence repair and owner approval.",
        },
        "tier_b_research_shortlist": shortlist,
        "candidates": candidates,
        "repeatable_scaleout_contract": [
            "Import each approved 100-name batch as Tier C review-monitor only.",
            "Run finance universe/state/readiness validators.",
            "Run this macro/thesis overlay to rank research leads.",
            "Promote only a small shortlist into Tier B research packets.",
            "Require full fundamentals, analyst, valuation, technical, ticker-card, source-open, portfolio-fit, and owner approval before any Tier A/deployment review.",
        ],
    }
    checks = validation_checks(report)
    failed = [check for check in checks if not check["ok"]]
    report["validation"] = {"status": "ok" if not failed else "blocked", "checks": checks, "failed": failed}
    report["status"] = "ok" if not failed else "blocked"
    return report


def write_db(path: Path, report: dict[str, Any]) -> None:
    with connect_write(path) as conn:
        conn.executescript(
            """
            DROP TABLE IF EXISTS candidates;
            DROP TABLE IF EXISTS shortlist;
            DROP TABLE IF EXISTS validation;
            DROP TABLE IF EXISTS meta;

            CREATE TABLE candidates (
                ticker TEXT PRIMARY KEY,
                name TEXT,
                sector TEXT,
                industry TEXT,
                overlay_score INTEGER NOT NULL,
                reputation_score INTEGER,
                theme TEXT NOT NULL,
                recommended_queue TEXT NOT NULL,
                capital_deployment_ready INTEGER NOT NULL CHECK(capital_deployment_ready IN (0,1)),
                raw_json TEXT NOT NULL
            ) STRICT;

            CREATE TABLE shortlist (
                rank INTEGER PRIMARY KEY,
                ticker TEXT NOT NULL,
                overlay_score INTEGER NOT NULL,
                theme TEXT NOT NULL,
                raw_json TEXT NOT NULL
            ) STRICT;

            CREATE TABLE validation (
                name TEXT PRIMARY KEY,
                ok INTEGER NOT NULL CHECK(ok IN (0,1)),
                detail_json TEXT NOT NULL
            ) STRICT;

            CREATE TABLE meta (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            ) STRICT;
            """
        )
        with conn:
            for row in as_list(report.get("candidates")):
                conn.execute(
                    "INSERT INTO candidates VALUES (?,?,?,?,?,?,?,?,?,?)",
                    (
                        row["ticker"],
                        row.get("name"),
                        row.get("sector"),
                        row.get("industry"),
                        int(row.get("overlay_score") or 0),
                        row.get("reputation_score"),
                        row.get("theme"),
                        row.get("recommended_queue"),
                        1 if row.get("capital_deployment_ready") else 0,
                        json_text(row),
                    ),
                )
            for idx, row in enumerate(as_list(report.get("tier_b_research_shortlist")), start=1):
                conn.execute(
                    "INSERT INTO shortlist VALUES (?,?,?,?,?)",
                    (idx, row["ticker"], int(row.get("overlay_score") or 0), row.get("theme"), json_text(row)),
                )
            for check in as_list(as_dict(report.get("validation")).get("checks")):
                conn.execute(
                    "INSERT INTO validation VALUES (?,?,?)",
                    (check["name"], 1 if check.get("ok") else 0, json_text(check.get("detail"))),
                )
            conn.execute("INSERT INTO meta VALUES (?,?)", ("schema", SCHEMA))
            conn.execute("INSERT INTO meta VALUES (?,?)", ("generated_at_utc", report["generated_at_utc"]))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build WF78 macro/thesis overlay for Tier C scaleout names.")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--write-db", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT_JSON)
    parser.add_argument("--db", type=Path, default=DEFAULT_OUT_DB)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = build_report()
    if args.write:
        atomic_write_json(args.out if args.out.is_absolute() else ROOT / args.out, report)
    if args.write_db:
        write_db(args.db if args.db.is_absolute() else ROOT / args.db, report)
    print(json.dumps(report, indent=2, sort_keys=True))
    if args.validate and report["validation"]["status"] != "ok":
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
