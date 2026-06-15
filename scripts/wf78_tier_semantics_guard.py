#!/usr/bin/env python3
"""Validate WF78 tier semantics so lower models cannot mix label layers."""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, load_json_artifact

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
AUTO_ROUTER = TMP / "wf78-auto-tier-routing.json"
CLEAN_ROSTER = TMP / "wf78-clean-tier-roster.json"
LABEL_PREVIEW = TMP / "wf78-tier-label-sync-preview.json"
TRUTH_LAYER_MAP = TMP / "wf78-truth-layer-map.json"
DEFAULT_OUT = TMP / "wf78-tier-semantics-guard.json"
SCHEMA = "veritas.wf78_tier_semantics_guard.v1"

AUTHORITY_BOUNDARY: dict[str, bool] = {
    "review_only": True,
    "guard_only": True,
    "automated_non_capital_routing_allowed": True,
    "auto_router_is_current_tier_authority": True,
    "label_preview_is_audit_only": True,
    "truth_layer_map_required": True,
    "universe_mutation_allowed": False,
    "canon_or_portfolio_mutation_allowed": False,
    "ticker_card_mutation_allowed": False,
    "sql_canon_mutation_allowed": False,
    "production_answer_path_change_allowed": False,
    "capital_deployment_allowed": False,
    "capital_deployment_approved": False,
    "trade_or_execution_allowed": False,
    "trade_or_execution_approved": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "money_movement_allowed": False,
    "owner_approval_inferred": False,
}

REQUIRED_TRUE_FLAGS = {
    "review_only",
    "guard_only",
    "automated_non_capital_routing_allowed",
    "auto_router_is_current_tier_authority",
    "label_preview_is_audit_only",
    "truth_layer_map_required",
}
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


def ticker(value: Any) -> str:
    return str(value or "").strip().upper()


def router_map(packet: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        ticker(row.get("ticker")): row
        for row in as_list(packet.get("rows"))
        if isinstance(row, dict) and ticker(row.get("ticker"))
    }


def add_check(checks: list[dict[str, Any]], name: str, ok: bool, detail: Any = None, severity: str = "critical") -> None:
    checks.append({"name": name, "ok": bool(ok), "status": "ok" if ok else "fail", "severity": severity, "detail": detail})


def current_tier_mismatches(roster: dict[str, Any], router: dict[str, Any]) -> list[dict[str, Any]]:
    routes = router_map(router)
    mismatches: list[dict[str, Any]] = []
    for tier_key, expected in (("true_tier_a", "Tier A"), ("true_tier_b", "Tier B"), ("true_tier_c", "Tier C")):
        for symbol in as_list(roster.get(tier_key)):
            route = routes.get(ticker(symbol), {})
            if route.get("auto_tier") != expected:
                mismatches.append({
                    "ticker": ticker(symbol),
                    "list": tier_key,
                    "expected_auto_tier": expected,
                    "actual_auto_tier": route.get("auto_tier"),
                })
    return mismatches


def overlap_rows(roster: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    rows.extend(row for row in as_list(roster.get("legacy_label_overlap")) if isinstance(row, dict))
    rows.extend(row for row in as_list(roster.get("promotion_overlap_explained")) if isinstance(row, dict))
    dedup: dict[str, dict[str, Any]] = {}
    for row in rows:
        dedup[ticker(row.get("ticker"))] = row
    return list(dedup.values())


def top_tier_b_wording_violations(roster: dict[str, Any]) -> list[dict[str, Any]]:
    violations = []
    for row in overlap_rows(roster):
        if row.get("current_tier") == "Tier A" and (
            row.get("approved_tier_b_research_bench_label") or row.get("legacy_universe_tier") == "B"
        ):
            violations.append({
                "ticker": row.get("ticker"),
                "current_tier": row.get("current_tier"),
                "forbidden_wording": "Do not call this a current Tier B name; call it promotion overlap/current Tier A.",
                "overlap_reasons": row.get("overlap_reasons"),
            })
    return violations


def truth_layer_decision_errors(truth_map: dict[str, Any]) -> list[dict[str, Any]]:
    errors: list[dict[str, Any]] = []
    for layer in as_list(truth_map.get("layers")):
        layer_dict = as_dict(layer)
        layer_id = str(layer_dict.get("layer_id") or "")
        if layer_dict.get("not_current_tier_authority") and "current_tier_membership" in as_list(layer_dict.get("can_decide")):
            errors.append({
                "layer_id": layer_id,
                "problem": "non_authority_layer_can_decide_current_tier_membership",
            })
        if layer_id not in {"current_tier_authority", "model_safe_current_roster"} and layer_dict.get("current_tier_authority"):
            errors.append({
                "layer_id": layer_id,
                "problem": "unexpected_current_tier_authority",
            })
    return errors


def build_report() -> dict[str, Any]:
    router = load_dict(AUTO_ROUTER)
    roster = load_dict(CLEAN_ROSTER)
    preview = load_dict(LABEL_PREVIEW)
    truth_map = load_dict(TRUTH_LAYER_MAP)
    checks: list[dict[str, Any]] = []
    mismatches = current_tier_mismatches(roster, router)
    wording_violations = top_tier_b_wording_violations(roster)
    preview_contract = as_dict(preview.get("semantic_contract"))
    roster_contract = as_dict(roster.get("semantic_contract"))
    truth_contract = as_dict(truth_map.get("semantic_contract"))
    truth_summary = as_dict(truth_map.get("summary"))
    truth_allowed_matrix = as_dict(truth_map.get("allowed_decision_matrix"))
    truth_decision_errors = truth_layer_decision_errors(truth_map)
    router_rows = router_map(router)

    add_check(checks, "auto_router_present", bool(router), rel(AUTO_ROUTER))
    add_check(checks, "auto_router_status_ok", router.get("status") == "ok", router.get("status"))
    add_check(checks, "clean_roster_present", bool(roster), rel(CLEAN_ROSTER))
    add_check(checks, "clean_roster_status_ok", roster.get("status") == "ok", roster.get("status"))
    add_check(checks, "label_preview_present", bool(preview), rel(LABEL_PREVIEW))
    add_check(checks, "label_preview_marked_not_current_tier_authority", preview_contract.get("not_current_tier_authority") is True, preview_contract)
    add_check(checks, "label_preview_points_to_auto_router_authority", preview_contract.get("current_tier_authority") == rel(AUTO_ROUTER), preview_contract)
    add_check(checks, "clean_roster_points_to_auto_router_authority", roster_contract.get("current_tier_authority") == rel(AUTO_ROUTER), roster_contract)
    add_check(checks, "truth_layer_map_present", bool(truth_map), rel(TRUTH_LAYER_MAP))
    add_check(checks, "truth_layer_map_status_ok", truth_map.get("status") == "ok", truth_map.get("status"))
    add_check(checks, "truth_layer_map_points_to_auto_router_authority", truth_contract.get("current_tier_membership_source_of_record") == rel(AUTO_ROUTER), truth_contract)
    add_check(checks, "truth_layer_map_points_to_clean_roster_answer_surface", truth_contract.get("preferred_model_safe_current_roster") == rel(CLEAN_ROSTER), truth_contract)
    add_check(checks, "truth_layer_map_blocks_non_authority_membership", not truth_decision_errors, truth_decision_errors)
    add_check(checks, "truth_layer_map_current_membership_matrix_clean", truth_allowed_matrix.get("current_tier_membership") == [rel(CLEAN_ROSTER), rel(AUTO_ROUTER)], truth_allowed_matrix)
    add_check(checks, "truth_layer_map_paper_readiness_not_tier_truth", truth_contract.get("paper_readiness_layers_are_not_tier_truth") is True, truth_contract)
    add_check(checks, "exclusive_lists_match_auto_router", not mismatches, mismatches)
    add_check(checks, "active_count_matches_auto_router", as_dict(roster.get("summary")).get("active_ticker_count") == len(router_rows), {"roster": as_dict(roster.get("summary")).get("active_ticker_count"), "router": len(router_rows)})
    add_check(checks, "capital_deployment_zero", as_dict(roster.get("summary")).get("capital_deployment_approved_count") == 0 and as_dict(router.get("summary")).get("capital_deployment_approved_count") == 0, {"roster": as_dict(roster.get("summary")).get("capital_deployment_approved_count"), "router": as_dict(router.get("summary")).get("capital_deployment_approved_count")})
    add_check(checks, "trade_execution_zero", as_dict(roster.get("summary")).get("trade_or_execution_approved_count") == 0 and as_dict(router.get("summary")).get("trade_or_execution_approved_count") == 0, {"roster": as_dict(roster.get("summary")).get("trade_or_execution_approved_count"), "router": as_dict(router.get("summary")).get("trade_or_execution_approved_count")})
    for flag in sorted(REQUIRED_TRUE_FLAGS):
        add_check(checks, f"authority_{flag}_true", AUTHORITY_BOUNDARY.get(flag) is True, AUTHORITY_BOUNDARY.get(flag))
    for flag in sorted(REQUIRED_FALSE_FLAGS):
        add_check(checks, f"authority_{flag}_false", AUTHORITY_BOUNDARY.get(flag) is False, AUTHORITY_BOUNDARY.get(flag))

    errors = [check for check in checks if check["severity"] == "critical" and not check["ok"]]
    return {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "ok" if not errors else "blocked",
        "workflow": "WF78 - Tier Semantics Guard",
        "purpose": "Fail closed when current tier authority, legacy labels, or overlap wording are ambiguous.",
        "authority_boundary": AUTHORITY_BOUNDARY,
        "source_artifacts": {
            "auto_router": rel(AUTO_ROUTER),
            "clean_tier_roster": rel(CLEAN_ROSTER),
            "label_sync_preview": rel(LABEL_PREVIEW),
            "truth_layer_map": rel(TRUTH_LAYER_MAP),
        },
        "summary": {
            "status": "ok" if not errors else "blocked",
            "current_tier_authority": rel(AUTO_ROUTER),
            "clean_roster": rel(CLEAN_ROSTER),
            "label_preview_role": "audit_only_not_current_tier_authority",
            "truth_layer_map_role": "layer_authority_contract",
            "truth_layer_map_category_counts": truth_summary.get("category_counts"),
            "tier_mismatch_count": len(mismatches),
            "promotion_overlap_wording_guard_count": len(wording_violations),
            "truth_layer_decision_error_count": len(truth_decision_errors),
            "capital_deployment_approved_count": 0,
            "trade_or_execution_approved_count": 0,
            "lower_model_rule": "Answer current Tier A/B/C membership only from wf78-clean-tier-roster or wf78-auto-tier-routing.",
            "next_safe_action": "Use the truth-layer map before any WF78 tier answer; use this guard as the fail-closed semantics proof.",
        },
        "tier_mismatches": mismatches,
        "promotion_overlap_wording_guards": wording_violations,
        "validation": {
            "status": "ok" if not errors else "error",
            "errors": errors,
            "warnings": [],
            "checks": checks,
        },
        "stop_lines": [
            "This guard does not mutate any roster or label surface.",
            "A clean guard result is not capital deployment or trade approval.",
            "Label-sync preview is audit/apply-preview context only, not current tier authority.",
            "Promotion review, deployment readiness, legacy migration, and paper readiness are not current Tier A/B/C membership authority.",
        ],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = build_report()
    out = args.out if args.out.is_absolute() else ROOT / args.out
    if args.write:
        atomic_write_json(out, report)
    print(json.dumps({
        "status": report.get("status"),
        "out": rel(out),
        "summary": report.get("summary"),
        "validation": {
            "status": as_dict(report.get("validation")).get("status"),
            "errors": len(as_list(as_dict(report.get("validation")).get("errors"))),
        },
    }, indent=2))
    if args.validate and as_dict(report.get("validation")).get("status") != "ok":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
