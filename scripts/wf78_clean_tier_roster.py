#!/usr/bin/env python3
"""Build the non-overlapping WF78 tier roster for model-safe consumption."""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, load_json_artifact

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
AUTO_ROUTER = TMP / "wf78-auto-tier-routing.json"
LABEL_PREVIEW = TMP / "wf78-tier-label-sync-preview.json"
DEFAULT_OUT = TMP / "wf78-clean-tier-roster.json"
SCHEMA = "veritas.wf78_clean_tier_roster.v1"

AUTHORITY_BOUNDARY: dict[str, bool] = {
    "review_only": True,
    "derived_roster_only": True,
    "automated_non_capital_routing_allowed": True,
    "auto_router_is_current_tier_authority": True,
    "label_preview_is_audit_only": True,
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
    "derived_roster_only",
    "automated_non_capital_routing_allowed",
    "auto_router_is_current_tier_authority",
    "label_preview_is_audit_only",
}
REQUIRED_FALSE_FLAGS = {flag for flag in AUTHORITY_BOUNDARY if flag not in REQUIRED_TRUE_FLAGS}

ROUTER_IDENTITY_VOLATILE_KEYS = {
    "generated_at",
    "generated_at_utc",
    "completed_at",
    "completed_at_utc",
    "started_at",
    "started_at_utc",
    "duration_ms",
    "elapsed_seconds",
    "age_hours",
    "mtime",
    "mtime_utc",
    "path_mtime_utc",
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


def normalize_router_for_identity(value: Any) -> Any:
    """Return stable router content without artifact-generation residue."""
    if isinstance(value, dict):
        return {
            str(key): normalize_router_for_identity(item)
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
            if str(key) not in ROUTER_IDENTITY_VOLATILE_KEYS
        }
    if isinstance(value, (list, tuple)):
        return [normalize_router_for_identity(item) for item in value]
    return value


def source_router_lineage(router: dict[str, Any]) -> dict[str, Any]:
    normalized = normalize_router_for_identity(router)
    encoded = json.dumps(normalized, sort_keys=True, separators=(",", ":"), default=str)
    return {
        "path": rel(AUTO_ROUTER),
        "content_sha256": hashlib.sha256(encoded.encode("utf-8")).hexdigest(),
        "generated_at_utc": router.get("generated_at_utc") or router.get("generated_at"),
    }


def router_lineage_complete(lineage: dict[str, Any]) -> bool:
    return bool(
        str(lineage.get("path") or "")
        and str(lineage.get("content_sha256") or "")
        and str(lineage.get("generated_at_utc") or "")
    )


def load_dict(path: Path) -> dict[str, Any]:
    payload = load_json_artifact(path)
    return payload if isinstance(payload, dict) else {}


def ticker(value: Any) -> str:
    return str(value or "").strip().upper()


def router_rows(packet: dict[str, Any]) -> list[dict[str, Any]]:
    return [row for row in as_list(packet.get("rows")) if isinstance(row, dict) and ticker(row.get("ticker"))]


def label_rows(packet: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        ticker(row.get("ticker")): row
        for row in as_list(packet.get("rows"))
        if isinstance(row, dict) and ticker(row.get("ticker"))
    }


def approved_label_set(packet: dict[str, Any]) -> set[str]:
    labels = as_dict(packet.get("summary")).get("approved_tier_b_research_bench_labels")
    return {ticker(item) for item in as_list(labels) if ticker(item)}


def add_check(checks: list[dict[str, Any]], name: str, ok: bool, detail: Any = None, severity: str = "critical") -> None:
    checks.append({"name": name, "ok": bool(ok), "status": "ok" if ok else "fail", "severity": severity, "detail": detail})


def clean_row(row: dict[str, Any], approved_labels: set[str], preview_by_ticker: dict[str, dict[str, Any]]) -> dict[str, Any]:
    symbol = ticker(row.get("ticker"))
    auto_tier = row.get("auto_tier")
    seeded_from_legacy = bool(row.get("tier_seeded_from_legacy_label"))
    has_tier_b_label = symbol in approved_labels
    preview_row = preview_by_ticker.get(symbol, {})
    overlap_reasons: list[str] = []
    if has_tier_b_label and auto_tier != "Tier B":
        overlap_reasons.append("approved_tier_b_research_bench_label_but_current_auto_tier_differs")
    if seeded_from_legacy:
        overlap_reasons.append("current_tier_seeded_from_legacy_label_without_auto_router_evidence")
    if auto_tier == "Tier A" and has_tier_b_label:
        overlap_reasons.append("promotion_overlap_current_tier_a_with_approved_label_b_context")
    return {
        "ticker": symbol,
        "name": row.get("name"),
        "sector": row.get("sector"),
        "instrument_type": row.get("instrument_type"),
        "asset_class": row.get("asset_class"),
        "instrument_class": row.get("instrument_class"),
        "exposure_type": row.get("exposure_type"),
        "review_lane": row.get("review_lane"),
        "deployment_role": row.get("deployment_role"),
        "opportunity_tier": row.get("opportunity_tier") or auto_tier,
        "lane_tier": row.get("lane_tier"),
        "current_tier": auto_tier,
        "current_state": row.get("auto_state"),
        "current_route_reason": row.get("route_reason"),
        "current_tier_source": rel(AUTO_ROUTER),
        "tier_seeded_from_legacy_label": seeded_from_legacy,
        "legacy_monitoring_role": row.get("legacy_monitoring_role"),
        "approved_tier_b_research_bench_label": has_tier_b_label,
        "label_preview_action": preview_row.get("proposed_sync_action"),
        "overlap": bool(overlap_reasons),
        "overlap_reasons": overlap_reasons,
        "model_safe_current_membership": auto_tier,
        "capital_deployment_approved": False,
        "trade_or_execution_approved": False,
    }


def build_report() -> dict[str, Any]:
    router = load_dict(AUTO_ROUTER)
    router_lineage = source_router_lineage(router)
    preview = load_dict(LABEL_PREVIEW)
    rows = router_rows(router)
    approved_labels = approved_label_set(preview)
    preview_by_ticker = label_rows(preview)
    clean_rows = [clean_row(row, approved_labels, preview_by_ticker) for row in rows]
    clean_rows.sort(key=lambda row: (str(row.get("current_tier") or ""), str(row.get("current_state") or ""), row["ticker"]))

    true_tier_a = sorted(row["ticker"] for row in clean_rows if row.get("current_tier") == "Tier A")
    true_tier_b = sorted(row["ticker"] for row in clean_rows if row.get("current_tier") == "Tier B")
    true_tier_c = sorted(row["ticker"] for row in clean_rows if row.get("current_tier") == "Tier C")
    overlaps = [row for row in clean_rows if row.get("overlap")]
    promotion_overlaps = [
        row for row in overlaps
        if row.get("current_tier") == "Tier A"
        and row.get("approved_tier_b_research_bench_label")
    ]
    legacy_seed_overlaps = [row for row in overlaps if row.get("tier_seeded_from_legacy_label")]
    tier_counts = Counter(row.get("current_tier") for row in clean_rows)
    state_counts = Counter(row.get("current_state") for row in clean_rows)
    lane_tier_counts = Counter(str(row.get("lane_tier") or "missing") for row in clean_rows)
    review_lane_counts = Counter(str(row.get("review_lane") or "missing") for row in clean_rows)

    checks: list[dict[str, Any]] = []
    add_check(checks, "auto_router_present", bool(router), rel(AUTO_ROUTER))
    add_check(checks, "auto_router_status_ok", router.get("status") == "ok", router.get("status"))
    add_check(checks, "auto_router_lineage_complete", router_lineage_complete(router_lineage), router_lineage)
    add_check(checks, "auto_router_validation_ok", as_dict(router.get("validation")).get("status") == "ok", as_dict(router.get("validation")).get("status"))
    add_check(checks, "rows_present", bool(clean_rows), len(clean_rows))
    add_check(checks, "exclusive_count_matches_rows", len(true_tier_a) + len(true_tier_b) + len(true_tier_c) == len(clean_rows), {"a": len(true_tier_a), "b": len(true_tier_b), "c": len(true_tier_c), "rows": len(clean_rows)})
    add_check(checks, "lane_qualified_fields_present", all(row.get("review_lane") and row.get("lane_tier") for row in clean_rows), [row.get("ticker") for row in clean_rows if not (row.get("review_lane") and row.get("lane_tier"))])
    add_check(checks, "label_preview_audit_only", as_dict(preview.get("semantic_contract")).get("not_current_tier_authority") is True, as_dict(preview.get("semantic_contract")))
    add_check(checks, "no_capital_deployment_approved", all(row.get("capital_deployment_approved") is False for row in clean_rows), None)
    add_check(checks, "no_trade_or_execution_approved", all(row.get("trade_or_execution_approved") is False for row in clean_rows), None)
    for flag in sorted(REQUIRED_TRUE_FLAGS):
        add_check(checks, f"authority_{flag}_true", AUTHORITY_BOUNDARY.get(flag) is True, AUTHORITY_BOUNDARY.get(flag))
    for flag in sorted(REQUIRED_FALSE_FLAGS):
        add_check(checks, f"authority_{flag}_false", AUTHORITY_BOUNDARY.get(flag) is False, AUTHORITY_BOUNDARY.get(flag))

    errors = [check for check in checks if check["severity"] == "critical" and not check["ok"]]
    return {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "ok" if not errors else "blocked",
        "workflow": "WF78 - Clean Tier Roster",
        "purpose": "Provide one non-overlapping current Tier A/B/C roster so lower models do not confuse legacy labels with live routing.",
        "semantic_contract": {
            "current_tier_authority": rel(AUTO_ROUTER),
            "source_router_lineage_required": True,
            "legacy_label_preview_role": "audit_only_not_current_tier_authority",
            "exclusive_lists_are_current_truth": True,
            "lower_model_instruction": "Use true_tier_a/true_tier_b/true_tier_c for current membership. Treat overlap arrays as explanation only.",
        },
        "authority_boundary": AUTHORITY_BOUNDARY,
        "source_artifacts": {
            "auto_router": rel(AUTO_ROUTER),
            "label_sync_preview": rel(LABEL_PREVIEW),
        },
        "source_router_lineage": router_lineage,
        "summary": {
            "active_ticker_count": len(clean_rows),
            "current_tier_counts": dict(tier_counts),
            "current_state_counts": dict(state_counts),
            "lane_tier_counts": dict(sorted(lane_tier_counts.items())),
            "review_lane_counts": dict(sorted(review_lane_counts.items())),
            "tier_a_equity_count": lane_tier_counts.get("Tier A Equity", 0),
            "tier_a_sleeve_count": lane_tier_counts.get("Tier A Sleeve", 0),
            "tier_a_commodity_count": lane_tier_counts.get("Tier A Commodity", 0),
            "tier_a_rates_income_count": lane_tier_counts.get("Tier A Rates/Income", 0),
            "tier_a_macro_currency_count": lane_tier_counts.get("Tier A Macro/Currency", 0),
            "tier_a_crypto_proxy_count": lane_tier_counts.get("Tier A Crypto Proxy", 0),
            "true_tier_a_count": len(true_tier_a),
            "true_tier_b_count": len(true_tier_b),
            "true_tier_c_count": len(true_tier_c),
            "legacy_seed_overlap_count": len(legacy_seed_overlaps),
            "promotion_overlap_count": len(promotion_overlaps),
            "capital_deployment_approved_count": 0,
            "trade_or_execution_approved_count": 0,
            "source_router_sha256": router_lineage.get("content_sha256"),
            "source_router_generated_at_utc": router_lineage.get("generated_at_utc"),
            "next_safe_action": "Route current tier questions through this artifact or wf78-auto-tier-routing; use label preview only for audit/apply-preview work.",
        },
        "true_tier_a": true_tier_a,
        "true_tier_b": true_tier_b,
        "true_tier_c": true_tier_c,
        "legacy_seed_overlap": legacy_seed_overlaps,
        "promotion_overlap_explained": promotion_overlaps,
        "rows": clean_rows,
        "validation": {
            "status": "ok" if not errors else "error",
            "errors": errors,
            "warnings": [],
            "checks": checks,
        },
        "stop_lines": [
            "This roster is derived review-only routing state.",
            "It does not mutate universe, canon, portfolio, SQL, ticker cards, or production answer paths.",
            "Tier membership is not capital deployment approval.",
            "No trade, paper/live order, brokerage/account action, or money movement authority is created.",
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
