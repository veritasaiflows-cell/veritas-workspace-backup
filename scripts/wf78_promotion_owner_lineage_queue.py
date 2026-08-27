#!/usr/bin/env python3
"""Build a promotion-only owner entry/stop lineage queue for WF78."""
from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, load_json_artifact

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
AUTO_ROUTER = TMP / "wf78-auto-tier-routing.json"
PROD_ADJUDICATION = TMP / "wf78-production-tier-adjudication.json"
SOURCE_REQUIREMENTS = TMP / "wf78-source-capture-requirements-queue.json"
INTEGRATION = TMP / "wf78-position-sizing-integration-proposal.json"
OWNER_PROPOSALS = TMP / "wf78-tier-a-owner-readiness-proposals.json"
OUT = TMP / "wf78-promotion-owner-lineage-queue.json"
SCHEMA = "veritas.wf78_promotion_owner_lineage_queue.v1"

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "promotion_only_owner_lineage_queue": True,
    "thin_monitor_lineage_creation_allowed": False,
    "owner_note_mutation_allowed": False,
    "ticker_card_mutation_allowed": False,
    "deployment_surface_mutation_allowed": False,
    "canon_or_portfolio_mutation_allowed": False,
    "sql_canon_mutation_allowed": False,
    "customer_or_external_delivery_allowed": False,
    "config_auth_runtime_mutation_allowed": False,
    "capital_deployment_allowed": False,
    "capital_deployment_approved": False,
    "trade_or_execution_allowed": False,
    "trade_or_execution_approved": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "money_movement_allowed": False,
    "owner_approval_inferred": False,
}
TRUE_KEYS = {"review_only", "promotion_only_owner_lineage_queue"}
FALSE_KEYS = {key for key in AUTHORITY_BOUNDARY if key not in TRUE_KEYS}


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


def ticker(value: Any) -> str:
    return str(value or "").strip().upper()


def route_map() -> dict[str, dict[str, Any]]:
    data = load_dict(AUTO_ROUTER)
    return {ticker(row.get("ticker")): as_dict(row) for row in as_list(data.get("rows"))}


def production_map() -> dict[str, dict[str, Any]]:
    data = load_dict(PROD_ADJUDICATION)
    if as_dict(data.get("deprecation_status")).get("deprecated_for_authority") is True:
        return {}
    return {ticker(row.get("ticker")): as_dict(row) for row in as_list(data.get("rows"))}


def lineage_available(row: dict[str, Any]) -> bool:
    return bool(as_dict(row.get("source_lineage")).get("available"))


def build_rows() -> list[dict[str, Any]]:
    routes = route_map()
    prod = production_map()
    rows: dict[str, dict[str, Any]] = {}

    integration = load_dict(INTEGRATION)
    for row in as_list(integration.get("rows")):
        row = as_dict(row)
        symbol = ticker(row.get("ticker"))
        if not symbol:
            continue
        route = routes.get(symbol, {})
        if route.get("auto_tier") not in {"Tier A", "Tier B"}:
            continue
        rows[symbol] = {
            "ticker": symbol,
            "auto_tier": route.get("auto_tier") or row.get("tier"),
            "route_state": route.get("auto_state") or row.get("route_state"),
            "production_bucket": prod.get(symbol, {}).get("recommended_bucket") or prod.get(symbol, {}).get("bucket"),
            "lineage_status": "owner_lineage_present" if lineage_available(row) else "owner_lineage_required",
            "selection_reason": "source_backed_integration_row",
            "lineage_source_artifacts": row.get("source_artifacts"),
        }

    owner = load_dict(OWNER_PROPOSALS)
    for row in as_list(owner.get("rows")):
        row = as_dict(row)
        symbol = ticker(row.get("ticker"))
        if symbol in rows and lineage_available(row):
            rows[symbol]["lineage_status"] = "owner_lineage_present"
            rows[symbol]["selection_reason"] = "owner_readiness_source_lineage_present"

    requirements = load_dict(SOURCE_REQUIREMENTS)
    for row in as_list(requirements.get("rows")):
        row = as_dict(row)
        symbol = ticker(row.get("ticker"))
        route = routes.get(symbol, {})
        auto_tier = route.get("auto_tier") or row.get("tier")
        if auto_tier not in {"Tier A", "Tier B"}:
            continue
        checklist = as_dict(row.get("required_evidence_checklist"))
        owner_req = as_dict(checklist.get("owner_entry_stop_source"))
        rows[symbol] = {
            "ticker": symbol,
            "auto_tier": auto_tier,
            "route_state": route.get("auto_state") or row.get("route_state"),
            "production_bucket": prod.get(symbol, {}).get("recommended_bucket") or prod.get(symbol, {}).get("bucket"),
            "lineage_status": "owner_lineage_required" if owner_req.get("required") else "owner_lineage_present",
            "selection_reason": "source_capture_owner_entry_stop_lineage_required",
            "lineage_source_artifacts": [rel(SOURCE_REQUIREMENTS)],
        }

    out: list[dict[str, Any]] = []
    for symbol, row in rows.items():
        status = row["lineage_status"]
        out.append({
            **row,
            "queue_scope": "promotion_only_a_b_or_promoted_c",
            "thin_monitor_lineage_creation_allowed": False,
            "recommended_next_step": (
                f"Gather owner entry/stop lineage for {symbol} before repair integration."
                if status == "owner_lineage_required"
                else f"{symbol} owner entry/stop lineage is present; no lineage queue action required."
            ),
            "owner_note_mutation_allowed": False,
            "ticker_card_mutation_allowed": False,
            "capital_deployment_approved": False,
            "trade_or_execution_approved": False,
            "paper_or_live_execution_allowed": False,
            "owner_approval_inferred": False,
        })
    out.sort(key=lambda row: (0 if row["lineage_status"] == "owner_lineage_required" else 1, row.get("auto_tier") or "", row["ticker"]))
    return out


def thin_monitor_exclusions() -> list[dict[str, Any]]:
    out = []
    for symbol, route in route_map().items():
        if route.get("auto_tier") == "Tier C" and route.get("auto_state") == "C-MONITOR":
            out.append({
                "ticker": symbol,
                "auto_tier": "Tier C",
                "route_state": "C-MONITOR",
                "lineage_status": "do_not_create_for_thin_monitor",
                "thin_monitor_lineage_creation_allowed": False,
            })
    return out


def build() -> dict[str, Any]:
    rows = build_rows()
    excluded = thin_monitor_exclusions()
    errors: list[str] = []
    for key in sorted(FALSE_KEYS):
        if AUTHORITY_BOUNDARY.get(key) is not False:
            errors.append(f"authority flag not false: {key}")
    for row in rows:
        if row.get("auto_tier") not in {"Tier A", "Tier B"}:
            errors.append(f"{row.get('ticker')} non-promoted row entered lineage queue")
        if row.get("owner_note_mutation_allowed") or row.get("ticker_card_mutation_allowed") or row.get("thin_monitor_lineage_creation_allowed"):
            errors.append(f"{row.get('ticker')} row implies mutation/thin-lineage creation")
        if row.get("capital_deployment_approved") or row.get("trade_or_execution_approved") or row.get("paper_or_live_execution_allowed") or row.get("owner_approval_inferred"):
            errors.append(f"{row.get('ticker')} authority boundary widened")
    return {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "blocked" if errors else "ok",
        "purpose": "Promotion-only owner entry/stop lineage queue for WF78 A/B and promoted candidates.",
        "authority_boundary": AUTHORITY_BOUNDARY,
        "source_artifacts": [rel(AUTO_ROUTER), rel(SOURCE_REQUIREMENTS), rel(INTEGRATION), rel(OWNER_PROPOSALS)],
        "deprecated_compatibility_artifacts": [rel(PROD_ADJUDICATION)],
        "summary": {
            "row_count": len(rows),
            "lineage_status_counts": dict(Counter(str(row.get("lineage_status")) for row in rows)),
            "owner_lineage_required_count": sum(1 for row in rows if row.get("lineage_status") == "owner_lineage_required"),
            "owner_lineage_present_count": sum(1 for row in rows if row.get("lineage_status") == "owner_lineage_present"),
            "thin_monitor_excluded_count": len(excluded),
            "next_safe_action": "Gather owner entry/stop lineage only for promotion-scope rows; keep ordinary Tier C monitor rows excluded.",
        },
        "rows": rows,
        "thin_monitor_exclusions_sample": excluded[:25],
        "validation": {"status": "blocked" if errors else "ok", "errors": errors, "warnings": []},
        "stop_lines": [
            "Owner-lineage queue only; no owner-note, card, deployment, canon, portfolio, or SQL-canon mutation.",
            "Ordinary Tier C monitor rows are excluded from lineage creation.",
            "No capital deployment, paper/live execution, brokerage/account action, money movement, customer output, or owner approval inference.",
        ],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build WF78 promotion-only owner lineage queue.")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--out", type=Path, default=OUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = build()
    if args.write:
        atomic_write_json(args.out, report)
        print(f"wrote {rel(args.out)} status={report['status']} rows={report['summary']['row_count']}")
    else:
        print(json.dumps(report["summary"], indent=2))
    if args.validate and report["validation"]["status"] != "ok":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
