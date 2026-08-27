from __future__ import annotations

import argparse
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
FINANCE_DB = ROOT / "state" / "finance" / "finance-canon.sqlite"
DATA_PLANE_DB = TMP / "canonical-finance-data-plane.sqlite"
GATE_PATH = TMP / "tier-a-trade-grade-coverage-gate.json"
AUTO_TIER_PATH = TMP / "wf78-auto-tier-routing.json"
CARD_DIR = TMP / "ticker-intelligence-cards"
OUT_PATH = TMP / "tier-a-cohort-alignment-reconciliation.json"

AUTHORITY_BOUNDARY = {
    "artifact_role": "tier_a_cohort_alignment_reconciliation_review_only",
    "review_only": True,
    "sql_read_only": True,
    "finance_canon_mutation_allowed": False,
    "data_plane_mutation_allowed": False,
    "universe_mutation_allowed": False,
    "portfolio_mutation_allowed": False,
    "capital_deployment_approved": False,
    "trade_or_execution_approved": False,
    "paper_or_live_execution_allowed": False,
    "owner_approval_inferred": False,
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return str(path)


def load_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def query_one(db_path: Path, table: str, ticker: str) -> dict[str, Any] | None:
    if not db_path.exists():
        return None
    with sqlite3.connect(f"file:{db_path.as_posix()}?mode=ro", uri=True) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(f"select * from {table} where ticker=?", (ticker,)).fetchone()
        return dict(row) if row else None


def find_auto_tier_row(payload: Any, ticker: str) -> dict[str, Any] | None:
    if isinstance(payload, dict):
        if str(payload.get("ticker") or "").upper() == ticker:
            return payload
        for value in payload.values():
            found = find_auto_tier_row(value, ticker)
            if found:
                return found
    elif isinstance(payload, list):
        for value in payload:
            found = find_auto_tier_row(value, ticker)
            if found:
                return found
    return None


def classify_mismatch(ticker: str, finance_row: dict[str, Any] | None, data_plane_row: dict[str, Any] | None, card: dict[str, Any], auto_row: dict[str, Any] | None) -> dict[str, Any]:
    instrument_type = str(card.get("instrument_type") or (auto_row or {}).get("instrument_type") or "").lower()
    universe = card.get("universe_metadata") if isinstance(card.get("universe_metadata"), dict) else {}
    decision_grade_eligible = universe.get("decision_grade_eligible")
    current_auto_tier = (auto_row or {}).get("auto_tier") or (data_plane_row or {}).get("auto_tier")
    current_auto_state = (auto_row or {}).get("auto_state") or (data_plane_row or {}).get("auto_state")
    finance_auto_tier = (finance_row or {}).get("auto_tier")
    finance_auto_state = (finance_row or {}).get("auto_state")
    if instrument_type in {"etf", "etf_or_macro_proxy"} and decision_grade_eligible is False:
        disposition = "proxy_exception_not_decision_grade"
        next_action = "Keep in proxy/watch coverage unless a separate ETF/proxy promotion gate changes route state."
    elif finance_auto_tier != current_auto_tier or finance_auto_state != current_auto_state:
        disposition = "durable_finance_canon_route_drift"
        next_action = "Use the approved SQL-canon tier-routing sync/apply path with backup and rollback proof before changing durable state."
    else:
        disposition = "classified_no_action"
        next_action = "No action."
    return {
        "ticker": ticker,
        "disposition": disposition,
        "next_action": next_action,
        "finance_canon": {
            "auto_tier": finance_auto_tier,
            "auto_state": finance_auto_state,
            "route_reason": (finance_row or {}).get("route_reason"),
            "source_generated_at_utc": (finance_row or {}).get("source_generated_at_utc"),
        },
        "data_plane": {
            "auto_tier": (data_plane_row or {}).get("auto_tier"),
            "auto_state": (data_plane_row or {}).get("auto_state"),
            "route_reason": (data_plane_row or {}).get("route_reason"),
        },
        "current_auto_tier_artifact": {
            "auto_tier": (auto_row or {}).get("auto_tier"),
            "auto_state": (auto_row or {}).get("auto_state"),
            "route_reason": (auto_row or {}).get("route_reason"),
        },
        "card_context": {
            "instrument_type": card.get("instrument_type"),
            "universe_tier": universe.get("tier"),
            "decision_grade_eligible": decision_grade_eligible,
            "monitoring_role": universe.get("monitoring_role"),
            "sector": universe.get("sector"),
        },
    }


def build_packet() -> dict[str, Any]:
    gate = load_json(GATE_PATH, {})
    rows = gate.get("tier_definition_diff") or gate.get("cohort_alignment") or {}
    if not rows:
        rows = {"finance_only": [], "data_plane_only": []}
        for row in gate.get("rows") or []:
            if row.get("cohort") == "finance_canon_only":
                rows["finance_only"].append(row.get("ticker"))
            elif row.get("cohort") == "data_plane_only":
                rows["data_plane_only"].append(row.get("ticker"))
    finance_only = sorted(str(ticker).upper() for ticker in rows.get("finance_only") or [] if ticker)
    data_plane_only = sorted(str(ticker).upper() for ticker in rows.get("data_plane_only") or [] if ticker)
    auto_payload = load_json(AUTO_TIER_PATH, {})
    reconciliations: list[dict[str, Any]] = []
    for ticker in finance_only:
        card = load_json(CARD_DIR / f"{ticker}.current.json", {}) or {}
        reconciliations.append(
            classify_mismatch(
                ticker,
                query_one(FINANCE_DB, "tier_routing_state", ticker),
                query_one(DATA_PLANE_DB, "routing_state_current", ticker),
                card,
                find_auto_tier_row(auto_payload, ticker),
            )
        )
    disposition_counts: dict[str, int] = {}
    for row in reconciliations:
        key = str(row.get("disposition"))
        disposition_counts[key] = disposition_counts.get(key, 0) + 1
    unresolved = [
        row["ticker"]
        for row in reconciliations
        if row.get("disposition") == "durable_finance_canon_route_drift"
    ]
    status = "cohort_alignment_reconciled_with_durable_sync_followup" if reconciliations else "cohort_alignment_already_clean"
    return {
        "schema": "veritas.tier_a_cohort_alignment_reconciliation.v1",
        "generated_at_utc": utc_now(),
        "status": status,
        "authority_boundary": AUTHORITY_BOUNDARY,
        "inputs": {
            "gate": rel(GATE_PATH),
            "finance_canon_db": rel(FINANCE_DB),
            "data_plane_db": rel(DATA_PLANE_DB),
            "auto_tier_artifact": rel(AUTO_TIER_PATH),
        },
        "summary": {
            "finance_only_count": len(finance_only),
            "data_plane_only_count": len(data_plane_only),
            "disposition_counts": disposition_counts,
            "durable_sync_followup_count": len(unresolved),
            "durable_sync_followup_tickers": unresolved,
            "capital_or_execution_allowed": False,
        },
        "finance_only_reconciliations": reconciliations,
        "data_plane_only_reconciliations": data_plane_only,
        "next_safe_action": "Do not mutate finance-canon tier rows from this packet. Use the approved SQL-canon tier-routing sync/apply gate if durable alignment should follow current auto-tier routing.",
    }


def validate_packet(packet: dict[str, Any]) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []

    def add(name: str, ok: bool, detail: Any = None) -> None:
        checks.append({"name": name, "ok": bool(ok), "detail": detail})

    boundary = packet.get("authority_boundary") or {}
    add("authority_no_finance_canon_mutation", boundary.get("finance_canon_mutation_allowed") is False)
    add("authority_no_execution", boundary.get("paper_or_live_execution_allowed") is False)
    add("finance_only_classified", packet["summary"]["finance_only_count"] == len(packet.get("finance_only_reconciliations") or []))
    add("dispositions_present", bool(packet["summary"]["disposition_counts"]) or packet["summary"]["finance_only_count"] == 0)
    return checks


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a review-only Tier A cohort alignment reconciliation packet.")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--out", type=Path, default=OUT_PATH)
    args = parser.parse_args()
    packet = build_packet()
    if args.validate:
        checks = validate_packet(packet)
        failed = [check for check in checks if not check["ok"]]
        packet["validation"] = {"status": "ok" if not failed else "blocked", "errors": failed, "checks": checks}
    if args.write:
        atomic_write_json(args.out, packet)
    print(json.dumps({"status": packet["status"], "summary": packet["summary"], "validation": packet.get("validation")}, indent=2))
    return 0 if packet.get("validation", {}).get("status", "ok") == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
