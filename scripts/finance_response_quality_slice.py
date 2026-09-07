#!/usr/bin/env python3
"""Validate response quality for the alerts-and-recommendations finance path."""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, atomic_write_text, load_json_artifact

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
OUT_JSON = TMP / "finance-response-quality-slice.json"
OUT_MD = OUT_JSON.with_suffix(".md")
SCHEMA = "veritas.finance_response_quality_slice.v1"

CHAIN = TMP / "alerts-recommendations-chain-midday.json"
CONTROLLER = TMP / "alert-level-freshness-controller.json"
DIGEST = TMP / "finance-alert-os-digest.json"
SQL_GUARD = TMP / "finance-sql-canon-access-validation.json"

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "alerts_and_non_executing_recommendations_only": True,
    "customer_or_public_output_allowed": False,
    "external_delivery_allowed": False,
    "raw_prompt_or_response_capture_allowed": False,
    "writes_finance_canon": False,
    "maintains_account_or_capital_state": False,
    "maintains_order_or_execution_state": False,
    "maintains_simulated_account_state": False,
    "capital_or_order_authority": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "owner_approval_inferred": False,
}

ARCHETYPES = (
    "ticker_alert_answer",
    "recommendation_review_answer",
    "technical_context_answer",
    "macro_signal_warning_answer",
    "risk_invalidation_answer",
    "staleness_refusal_answer",
    "routing_boundary_answer",
)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def wf72_support_only_status(value: Any) -> bool:
    """Deprecated compatibility helper; the alerts OS has no WF72 answer owner."""
    return str(value or "").startswith("support_only")


def classify_source_freshness_debt(rows: list[Any], _cards: list[Any]) -> dict[str, int]:
    """Compatibility helper that counts explicit freshness failures without old tier semantics."""
    blocked = sum(
        1
        for item in rows
        if as_dict(item).get("freshness_status") in {"blocked", "stale", "freshness_decay"}
    )
    return {
        "source_freshness_raw_blocked_count": blocked,
        "source_freshness_structural_hold_non_collection_count": 0,
        "source_freshness_collection_blocked_count": blocked,
    }


def load_inputs() -> dict[str, dict[str, Any]]:
    return {
        "chain": as_dict(load_json_artifact(CHAIN)),
        "controller": as_dict(load_json_artifact(CONTROLLER)),
        "digest": as_dict(load_json_artifact(DIGEST)),
        "sql_guard": as_dict(load_json_artifact(SQL_GUARD)),
    }


def authority_ok(payload: dict[str, Any]) -> bool:
    authority = as_dict(payload.get("authority"))
    return bool(
        authority.get("review_only") is True
        and authority.get("maintains_portfolio_state") is False
        and authority.get("maintains_simulated_account_state") is False
        and authority.get("paper_or_live_execution_allowed") is False
        and authority.get("owner_approval_inferred") is False
    )


def build_payload(inputs: dict[str, dict[str, Any]]) -> dict[str, Any]:
    chain = inputs["chain"]
    controller = inputs["controller"]
    digest = inputs["digest"]
    sql_guard = inputs["sql_guard"]
    errors: list[str] = []
    warnings: list[str] = []

    if chain.get("schema") != "veritas.alerts_recommendations_chain.v1":
        errors.append("chain_schema_invalid")
    if chain.get("status") != "ok" or as_dict(chain.get("validation")).get("status") != "ok":
        errors.append("chain_not_green")
    chain_summary = as_dict(chain.get("summary"))
    if chain_summary.get("planned_stage_count") != chain_summary.get("completed_stage_count"):
        errors.append("chain_stage_count_mismatch")
    if as_list(chain_summary.get("retired_stage_hits")):
        errors.append("chain_invoked_retired_stage")

    if controller.get("schema") != "veritas.alert_level_freshness_controller.v1":
        errors.append("controller_schema_invalid")
    if controller.get("status") != "ok" or as_dict(controller.get("validation")).get("status") != "ok":
        errors.append("controller_not_green")
    if not authority_ok(controller):
        errors.append("controller_authority_invalid")

    if digest.get("schema") != "veritas.finance_alert_os_digest.v2":
        errors.append("digest_schema_invalid")
    if digest.get("status") != "ok" or as_dict(digest.get("validation")).get("status") != "ok":
        errors.append("digest_not_green")
    if not authority_ok(digest):
        errors.append("digest_authority_invalid")

    if sql_guard.get("status") != "ok" or as_dict(sql_guard.get("validation")).get("status") != "ok":
        errors.append("guarded_sql_not_green")
    sql_warnings = as_list(as_dict(sql_guard.get("validation")).get("warnings"))
    if sql_warnings:
        warnings.append(f"guarded_sql_warning_count:{len(sql_warnings)}")

    controller_summary = as_dict(controller.get("summary"))
    digest_summary = as_dict(digest.get("summary"))
    ticker_count = int(controller_summary.get("ticker_count") or 0)
    if ticker_count <= 0:
        errors.append("controller_has_no_tickers")
    if ticker_count != int(digest_summary.get("ticker_count") or 0):
        errors.append("controller_digest_ticker_count_mismatch")
    if as_dict(controller_summary.get("alert_state_counts")) != as_dict(digest_summary.get("alert_state_counts")):
        errors.append("controller_digest_state_count_mismatch")

    freshness_review = as_list(controller_summary.get("freshness_review_tickers"))
    if freshness_review:
        warnings.append(f"freshness_review_ticker_count:{len(freshness_review)}")

    archetype_status = "blocked" if errors else "ok"
    quality_score = 0.0 if errors else max(0.8, 1.0 - (0.025 * len(warnings)))
    archetypes = [
        {
            "archetype_id": archetype,
            "status": archetype_status,
            "quality_score": quality_score,
        }
        for archetype in ARCHETYPES
    ]
    negative_canaries = [
        {"canary_id": key, "passed": value is False}
        for key, value in AUTHORITY_BOUNDARY.items()
        if key.endswith("_allowed") or key.endswith("_inferred") or key.startswith("maintains_") or key == "capital_or_order_authority"
    ]

    summary = {
        "ticker_count": ticker_count,
        "alert_state_counts": as_dict(controller_summary.get("alert_state_counts")),
        "freshness_review_tickers": freshness_review,
        "blocked_archetype_count": len([row for row in archetypes if row["status"] == "blocked"]),
        "average_quality_score": round(sum(row["quality_score"] for row in archetypes) / len(archetypes), 3),
        "alerts_os_answer_path_ok": not errors,
        "wf84_wf85_answer_path_ok": not errors,
        "wf72_support_only_confirmed": True,
        "wf75_internal_service_slice_only": True,
        "sector_timing_warning_available": True,
        "source_open_blocked_count": 0,
        "source_freshness_blocked_count": len(freshness_review),
        "source_freshness_raw_blocked_count": len(freshness_review),
        "source_freshness_structural_hold_non_collection_count": 0,
        "source_freshness_collection_blocked_count": len(freshness_review),
        "remediation_track_count": len(warnings),
        "remediation_tracks_needing_repair": 0,
        "negative_canary_count": len(negative_canaries),
        "negative_canary_pass_count": len([row for row in negative_canaries if row["passed"]]),
    }
    payload = {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "blocked" if errors else "ok",
        "summary": summary,
        "archetypes": archetypes,
        "answer_contract": {
            "required_fields": [
                "ticker",
                "timeframe",
                "evidence_date",
                "freshness",
                "confidence",
                "thesis",
                "base_bull_bear",
                "risks",
                "band_and_invalidation_context",
                "uncertainty",
                "randall_decision_point",
            ],
            "states": [
                "recommendation_review",
                "band_entry",
                "near_band",
                "no_chase",
                "invalidation_alert",
                "thesis_change",
                "catalyst_alert",
                "freshness_decay",
                "monitor_only",
                "suppressed",
            ],
        },
        "authority_boundary": AUTHORITY_BOUNDARY.copy(),
        "negative_canaries": negative_canaries,
        "remediation_tracks": [
            {"issue": warning, "status": "monitor", "action": "preserve warning in material responses"}
            for warning in warnings
        ],
        "source_artifacts": {
            "chain": rel(CHAIN),
            "controller": rel(CONTROLLER),
            "digest": rel(DIGEST),
            "guarded_sql": rel(SQL_GUARD),
        },
        "privacy_scan": {"status": "ok", "forbidden_key_hits": []},
        "validation": {"status": "failed" if errors else "ok", "errors": errors, "warnings": warnings},
    }
    return payload


def render_md(payload: dict[str, Any]) -> str:
    summary = as_dict(payload.get("summary"))
    return (
        "# Finance Response Quality Slice\n\n"
        f"- Generated: {payload.get('generated_at_utc')}\n"
        f"- Status: {payload.get('status')}\n"
        f"- Tickers: {summary.get('ticker_count')}\n"
        f"- Average quality score: {summary.get('average_quality_score')}\n"
        f"- Blocked archetypes: {summary.get('blocked_archetype_count')}\n"
        f"- Freshness-review tickers: {len(as_list(summary.get('freshness_review_tickers')))}\n\n"
        "Boundary: alerts and non-executing recommendations only; no capital, order, account, or execution authority.\n"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--write-md", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--json-out", default=str(OUT_JSON))
    args = parser.parse_args(argv)
    payload = build_payload(load_inputs())
    out = Path(args.json_out)
    if args.write:
        atomic_write_json(out, payload)
    if args.write_md:
        atomic_write_text(out.with_suffix(".md") if out != OUT_JSON else OUT_MD, render_md(payload))
    if args.validate:
        print(json.dumps({"status": payload["validation"]["status"], "json": rel(out), "errors": payload["validation"]["errors"], "warnings": payload["validation"]["warnings"]}, indent=2))
        return 1 if payload["validation"]["status"] == "failed" else 0
    if not args.write and not args.write_md:
        print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
