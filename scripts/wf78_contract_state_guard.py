#!/usr/bin/env python3
"""Validate the WF78 reusable repair-contract artifact set.

This guard protects the new source/registry/lineage repair layer from silent
schema drift. It is review-only: it reads generated artifacts and reports
contract health without mutating registry, cards, canon, portfolio, deployment
surfaces, SQL canon/cache, or execution/account surfaces.
"""
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
OUT = TMP / "wf78-contract-state-guard.json"
SCHEMA = "veritas.wf78_contract_state_guard.v1"

ARTIFACTS = {
    "official_source_discovery": TMP / "wf78-official-source-discovery.json",
    "official_registry_proposal": TMP / "wf78-official-registry-proposal.json",
    "promotion_owner_lineage_queue": TMP / "wf78-promotion-owner-lineage-queue.json",
    "position_sizing_integration_proposal": TMP / "wf78-position-sizing-integration-proposal.json",
    "deployment_readiness_review": TMP / "wf78-deployment-readiness-review.json",
}

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "contract_guard_only": True,
    "registry_mutation_allowed": False,
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

FORBIDDEN_TRUE_KEYS = {
    "registry_mutation_allowed",
    "ticker_card_mutation_allowed",
    "deployment_surface_mutation_allowed",
    "canon_or_portfolio_mutation_allowed",
    "portfolio_sizing_mutation_allowed",
    "sql_canon_mutation_allowed",
    "customer_or_external_delivery_allowed",
    "config_auth_runtime_mutation_allowed",
    "capital_deployment_allowed",
    "capital_deployment_approved",
    "trade_or_execution_allowed",
    "trade_or_execution_approved",
    "paper_or_live_execution_allowed",
    "brokerage_or_account_action_allowed",
    "money_movement_allowed",
    "owner_approval_inferred",
    "proposal_applied",
    "source_values_copied_into_cards",
    "thin_monitor_lineage_creation_allowed",
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


def count_where(rows: list[Any], key: str, expected: Any = True) -> int:
    return sum(1 for row in rows if as_dict(row).get(key) == expected)


def add_check(checks: list[dict[str, Any]], artifact: str, check: str, ok: bool, detail: Any = None, severity: str = "critical") -> None:
    checks.append({
        "artifact": artifact,
        "check": check,
        "status": "ok" if ok else "fail",
        "ok": bool(ok),
        "severity": severity,
        "detail": detail,
    })


def authority_findings(name: str, payload: dict[str, Any], checks: list[dict[str, Any]]) -> None:
    authority = as_dict(payload.get("authority_boundary"))
    add_check(checks, name, "review_only_true", authority.get("review_only") is True, authority)
    for key in sorted(FORBIDDEN_TRUE_KEYS):
        if key in authority:
            add_check(checks, name, f"authority_{key}_false", authority.get(key) is False, authority.get(key))
    for row in as_list(payload.get("rows")):
        row = as_dict(row)
        symbol = row.get("ticker")
        for key in sorted(FORBIDDEN_TRUE_KEYS):
            if key in row and row.get(key) is not False:
                add_check(checks, name, f"row_{key}_false", False, {"ticker": symbol, "value": row.get(key)})


def validate_official_source(payload: dict[str, Any], checks: list[dict[str, Any]]) -> None:
    name = "official_source_discovery"
    rows = as_list(payload.get("rows"))
    summary = as_dict(payload.get("summary"))
    confidences = Counter(str(as_dict(row).get("discovery_confidence")) for row in rows)
    add_check(checks, name, "status_ok", payload.get("status") == "ok", payload.get("status"))
    add_check(checks, name, "row_count_matches_summary", summary.get("row_count") == len(rows), {"summary": summary.get("row_count"), "actual": len(rows)})
    add_check(checks, name, "confidence_counts_match", as_dict(summary.get("confidence_counts")) == dict(confidences), {"summary": summary.get("confidence_counts"), "actual": dict(confidences)})
    add_check(checks, name, "registry_needed_count_matches", summary.get("registry_proposal_needed_count") == count_where(rows, "registry_proposal_needed"), summary)
    add_check(checks, name, "lineage_required_count_matches", summary.get("owner_entry_stop_lineage_still_required_count") == count_where(rows, "owner_entry_stop_lineage_still_required"), summary)


def validate_registry_proposal(payload: dict[str, Any], checks: list[dict[str, Any]]) -> None:
    name = "official_registry_proposal"
    rows = as_list(payload.get("rows"))
    summary = as_dict(payload.get("summary"))
    actions = Counter(str(as_dict(row).get("proposal_action")) for row in rows)
    add_check(checks, name, "status_ok", payload.get("status") == "ok", payload.get("status"))
    add_check(checks, name, "row_count_matches_summary", summary.get("row_count") == len(rows), {"summary": summary.get("row_count"), "actual": len(rows)})
    add_check(checks, name, "action_counts_match", as_dict(summary.get("proposal_action_counts")) == dict(actions), {"summary": summary.get("proposal_action_counts"), "actual": dict(actions)})
    add_check(checks, name, "no_applied_rows", count_where(rows, "proposal_applied") == 0, count_where(rows, "proposal_applied"))


def validate_lineage_queue(payload: dict[str, Any], checks: list[dict[str, Any]]) -> None:
    name = "promotion_owner_lineage_queue"
    rows = as_list(payload.get("rows"))
    summary = as_dict(payload.get("summary"))
    statuses = Counter(str(as_dict(row).get("lineage_status")) for row in rows)
    add_check(checks, name, "status_ok", payload.get("status") == "ok", payload.get("status"))
    add_check(checks, name, "row_count_matches_summary", summary.get("row_count") == len(rows), {"summary": summary.get("row_count"), "actual": len(rows)})
    add_check(checks, name, "lineage_status_counts_match", as_dict(summary.get("lineage_status_counts")) == dict(statuses), {"summary": summary.get("lineage_status_counts"), "actual": dict(statuses)})
    add_check(checks, name, "thin_monitor_exclusions_present", int(summary.get("thin_monitor_excluded_count") or 0) > 0, summary.get("thin_monitor_excluded_count"))


def validate_position_integration(payload: dict[str, Any], checks: list[dict[str, Any]]) -> None:
    name = "position_sizing_integration_proposal"
    rows = as_list(payload.get("rows"))
    summary = as_dict(payload.get("summary"))
    statuses = Counter(str(as_dict(row).get("proposal_status")) for row in rows)
    add_check(checks, name, "status_ok", payload.get("status") == "ok", payload.get("status"))
    add_check(checks, name, "row_count_matches_summary", summary.get("proposal_row_count") == len(rows), {"summary": summary.get("proposal_row_count"), "actual": len(rows)})
    add_check(checks, name, "status_counts_match", as_dict(summary.get("proposal_status_counts")) == dict(statuses), {"summary": summary.get("proposal_status_counts"), "actual": dict(statuses)})
    add_check(checks, name, "all_rows_not_applied", all(as_dict(row).get("apply_status") == "not_applied_review_only" for row in rows), None)


def validate_deployment_review(payload: dict[str, Any], checks: list[dict[str, Any]]) -> None:
    name = "deployment_readiness_review"
    rows = as_list(payload.get("rows"))
    summary = as_dict(payload.get("summary"))
    statuses = Counter(str(as_dict(row).get("review_status")) for row in rows)
    add_check(checks, name, "status_ok", payload.get("status") == "ok", payload.get("status"))
    add_check(checks, name, "row_count_matches_summary", summary.get("row_count") == len(rows), {"summary": summary.get("row_count"), "actual": len(rows)})
    add_check(checks, name, "status_counts_match", as_dict(summary.get("review_status_counts")) == dict(statuses), {"summary": summary.get("review_status_counts"), "actual": dict(statuses)})


def build() -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    payloads = {name: load_dict(path) for name, path in ARTIFACTS.items()}
    for name, path in ARTIFACTS.items():
        add_check(checks, name, "artifact_exists", path.exists(), rel(path))
        add_check(checks, name, "artifact_is_object", bool(payloads[name]), type(payloads[name]).__name__)
        authority_findings(name, payloads[name], checks)
    validate_official_source(payloads["official_source_discovery"], checks)
    validate_registry_proposal(payloads["official_registry_proposal"], checks)
    validate_lineage_queue(payloads["promotion_owner_lineage_queue"], checks)
    validate_position_integration(payloads["position_sizing_integration_proposal"], checks)
    validate_deployment_review(payloads["deployment_readiness_review"], checks)
    critical = [check for check in checks if check["severity"] == "critical" and not check["ok"]]
    warnings = [check for check in checks if check["severity"] == "warning" and not check["ok"]]
    return {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "ok" if not critical else "blocked",
        "purpose": "Review-only guard for WF78 reusable repair artifact contracts.",
        "authority_boundary": AUTHORITY_BOUNDARY,
        "source_artifacts": [rel(path) for path in ARTIFACTS.values()],
        "summary": {
            "artifacts_checked": len(ARTIFACTS),
            "checks": len(checks),
            "critical": len(critical),
            "warning": len(warnings),
            "next_safe_action": "If blocked, repair the producer contract before using the daily loop as proof.",
        },
        "checks": checks,
        "validation": {"status": "ok" if not critical else "error", "errors": critical, "warnings": warnings},
        "stop_lines": [
            "Contract guard only; no registry/card/deployment/canon/portfolio/SQL-canon mutation.",
            "No capital deployment, paper/live execution, brokerage/account action, money movement, customer output, or owner approval inference.",
        ],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate WF78 reusable repair contracts.")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--out", type=Path, default=OUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = build()
    if args.write:
        atomic_write_json(args.out, report)
        print(f"wrote {rel(args.out)} status={report['status']} checks={report['summary']['checks']}")
    else:
        print(json.dumps(report["summary"], indent=2))
    if args.validate and report["validation"]["status"] != "ok":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
