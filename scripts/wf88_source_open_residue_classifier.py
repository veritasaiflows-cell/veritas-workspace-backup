#!/usr/bin/env python3
"""Classify WF85 source-open residue for WF88 thinning.

The 42 WF85 source-open rows must not be allowed to look like implementation
blockers. They also must not be blindly deleted: in the current SQL/JSON-first
route they are finance-domain review rows, legacy runtime residue, or monitor
context. This packet makes that split explicit and keeps default runtime closeout
from paying for legacy source-open drag.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, atomic_write_text, load_json_artifact


ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"

WF85_PACKET = TMP / "wf85-decision-os-review-packet.json"
REPAIR_CONVEYOR = TMP / "trade-grade-repair-conveyor.json"
TIER_ROUTER = TMP / "wf78-auto-tier-routing.json"
SOURCE_REPAIR_EXECUTION = TMP / "wf78-source-open-repair-execution.json"
SOURCE_WORK_PACKETS = TMP / "wf78-source-open-work-packets.json"
LEGACY_ARCHIVE_CLOSEOUT = TMP / "legacy-42-full-archive-apply-closeout.json"
LEGACY_NO_RUNTIME_IMPORTS = TMP / "legacy-42-no-runtime-imports-guard.json"
OUT = TMP / "wf88-source-open-residue-classifier.json"
MD_OUT = TMP / "wf88-source-open-residue-classifier.md"

SCHEMA = "veritas.wf88_source_open_residue_classifier.v1"

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "classification_only": True,
    "default_runtime_blocker_authority": False,
    "delete_allowed": False,
    "archive_allowed": False,
    "move_allowed": False,
    "apply_allowed": False,
    "sql_mutation_allowed": False,
    "canon_or_portfolio_mutation_allowed": False,
    "cash_sizing_risk_mutation_allowed": False,
    "capital_deployment_allowed": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "customer_or_external_delivery_allowed": False,
    "owner_approval_inferred": False,
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def load_optional_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    data = load_json_artifact(path)
    return data if isinstance(data, dict) else {}


def input_record(path: Path, payload: dict[str, Any], required: bool = True) -> dict[str, Any]:
    return {
        "path": rel(path),
        "present": path.exists(),
        "required": required,
        "schema": payload.get("schema") or payload.get("schema_version"),
        "status": payload.get("status"),
        "generated_at_utc": payload.get("generated_at_utc"),
    }


def router_by_ticker(router: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows = as_list(router.get("rows"))
    return {
        str(row.get("ticker")): row
        for row in rows
        if isinstance(row, dict) and row.get("ticker")
    }


def source_repair_tickers(execution: dict[str, Any], work_packets: dict[str, Any]) -> set[str]:
    tickers = {str(ticker) for ticker in as_list(as_dict(execution.get("summary")).get("priority_tickers")) if ticker}
    for row in as_list(execution.get("rows")):
        row_dict = as_dict(row)
        if row_dict.get("ticker"):
            tickers.add(str(row_dict["ticker"]))
    for packet in as_list(work_packets.get("packets")):
        packet_dict = as_dict(packet)
        for item in as_list(packet_dict.get("rows")) + as_list(packet_dict.get("items")):
            item_dict = as_dict(item)
            if item_dict.get("ticker"):
                tickers.add(str(item_dict["ticker"]))
    return tickers


def classify_row(row: dict[str, Any], tier_row: dict[str, Any], active_repair_tickers: set[str]) -> str:
    ticker = str(row.get("ticker") or "")
    decision_state = str(row.get("decision_state") or "")
    repair_lane = str(row.get("repair_lane") or "")
    auto_tier = str(tier_row.get("auto_tier") or "")
    if decision_state == "below_stop_or_invalidation" or repair_lane == "invalidation_or_below_stop_review_only":
        return "below_stop_or_invalidation_review_only"
    if auto_tier in {"Tier A", "Tier B"} and decision_state == "blocked_missing_source_open":
        return "active_sql_json_tier_repair"
    if ticker in active_repair_tickers and auto_tier in {"Tier A", "Tier B"}:
        return "active_sql_json_tier_repair"
    if auto_tier == "Tier C" or decision_state == "monitor_only":
        return "monitor_only_context"
    return "legacy_42_deprecated_residue"


def build_rows(
    repair_conveyor: dict[str, Any],
    tier_router: dict[str, Any],
    active_repair_tickers: set[str],
) -> list[dict[str, Any]]:
    tier_lookup = router_by_ticker(tier_router)
    rows: list[dict[str, Any]] = []
    for row in as_list(repair_conveyor.get("rows")):
        row_dict = as_dict(row)
        if row_dict.get("source_open_status") != "blocked":
            continue
        ticker = str(row_dict.get("ticker") or "")
        tier_row = as_dict(tier_lookup.get(ticker))
        classification = classify_row(row_dict, tier_row, active_repair_tickers)
        rows.append({
            "ticker": ticker,
            "classification": classification,
            "legacy_drag_state": "not_default_runtime_blocker",
            "default_runtime_blocker": False,
            "implementation_blocker": False,
            "delete_candidate": False,
            "source_open_status": row_dict.get("source_open_status"),
            "decision_state": row_dict.get("decision_state"),
            "repair_lane": row_dict.get("repair_lane"),
            "primary_state": row_dict.get("primary_state"),
            "auto_tier": tier_row.get("auto_tier"),
            "auto_state": tier_row.get("auto_state"),
            "lane_tier": tier_row.get("lane_tier"),
            "review_lane": tier_row.get("review_lane"),
            "active_source_open_repair_packet_member": ticker in active_repair_tickers,
            "capital_deployment_approved": bool(tier_row.get("capital_deployment_approved")),
            "trade_or_execution_approved": bool(tier_row.get("trade_or_execution_approved")),
            "next_action": row_dict.get("next_action"),
        })
    return sorted(rows, key=lambda item: (str(item.get("classification")), str(item.get("auto_tier")), str(item.get("ticker"))))


def build_packet() -> dict[str, Any]:
    wf85 = load_optional_json(WF85_PACKET)
    repair_conveyor = load_optional_json(REPAIR_CONVEYOR)
    tier_router = load_optional_json(TIER_ROUTER)
    source_exec = load_optional_json(SOURCE_REPAIR_EXECUTION)
    source_work = load_optional_json(SOURCE_WORK_PACKETS)
    legacy_archive = load_optional_json(LEGACY_ARCHIVE_CLOSEOUT)
    legacy_guard = load_optional_json(LEGACY_NO_RUNTIME_IMPORTS)
    active_repair_tickers = source_repair_tickers(source_exec, source_work)
    rows = build_rows(repair_conveyor, tier_router, active_repair_tickers)
    counts = Counter(str(row.get("classification")) for row in rows)
    wf85_source_counts = as_dict(as_dict(wf85.get("summary")).get("source_open_status_counts"))
    legacy_archived = legacy_archive.get("status") in {"archived", "owner_approved_archive_ready"}
    legacy_runtime_import_blockers = as_dict(legacy_guard.get("summary")).get("active_runtime_blocker_count")
    router_summary = as_dict(tier_router.get("summary"))
    default_runtime_blocker_count = sum(1 for row in rows if row.get("default_runtime_blocker") is True)
    packet = {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "workflow_id": "WF88",
        "status": "classified_no_default_runtime_drag",
        "purpose": "Separate current SQL/JSON finance repair rows from legacy source-open runtime drag.",
        "authority_boundary": AUTHORITY_BOUNDARY,
        "inputs": {
            "wf85_decision_os_review_packet": input_record(WF85_PACKET, wf85),
            "trade_grade_repair_conveyor": input_record(REPAIR_CONVEYOR, repair_conveyor),
            "wf78_auto_tier_routing": input_record(TIER_ROUTER, tier_router),
            "wf78_source_open_repair_execution": input_record(SOURCE_REPAIR_EXECUTION, source_exec, required=False),
            "wf78_source_open_work_packets": input_record(SOURCE_WORK_PACKETS, source_work, required=False),
            "legacy_42_full_archive_apply_closeout": input_record(LEGACY_ARCHIVE_CLOSEOUT, legacy_archive, required=False),
            "legacy_42_no_runtime_imports_guard": input_record(LEGACY_NO_RUNTIME_IMPORTS, legacy_guard, required=False),
        },
        "sql_json_route_truth": {
            "active_ticker_count": router_summary.get("active_ticker_count"),
            "auto_tier_counts": router_summary.get("auto_tier_counts"),
            "production_adjudication_deprecated_for_authority": router_summary.get("production_adjudication_deprecated_for_authority") is True,
            "tier_a_packet_deprecated_for_authority": router_summary.get("tier_a_packet_deprecated_for_authority") is True,
            "capital_deployment_approved_count": router_summary.get("capital_deployment_approved_count"),
            "trade_or_execution_approved_count": router_summary.get("trade_or_execution_approved_count"),
        },
        "source_open_truth": {
            "wf85_source_open_status_counts": wf85_source_counts,
            "source_open_blocked_count": len(rows),
            "implementation_blocker_count": as_dict(wf85.get("summary")).get("implementation_blocker_count"),
            "default_runtime_blocker_count": default_runtime_blocker_count,
            "legacy_archive_status": legacy_archive.get("status"),
            "legacy_42_runtime_import_blocker_count": legacy_runtime_import_blockers,
            "legacy_42_archive_already_applied_or_ready": legacy_archived,
        },
        "classification_counts": dict(sorted(counts.items())),
        "rows": rows,
        "runtime_policy": {
            "default_closeout_should_block_on_source_open_42": False,
            "default_validators_should_score_source_open_42": False,
            "source_open_42_is_finance_domain_context": True,
            "active_sql_json_repair_rows_stay_visible": True,
            "delete_current_finance_rows_allowed": False,
            "legacy_artifact_deletion_requires_owner_packet": True,
        },
        "next_safe_action": "Use this classifier in WF88 first-read truth. Keep active SQL/JSON repair visible, but remove source-open 42 from default runtime blocker math.",
    }
    packet["summary"] = summarize_packet(packet)
    packet["validation"] = validate_packet(packet)
    return packet


def summarize_packet(packet: dict[str, Any]) -> dict[str, Any]:
    counts = as_dict(packet.get("classification_counts"))
    source_truth = as_dict(packet.get("source_open_truth"))
    return {
        "status": packet.get("status"),
        "source_open_blocked_count": source_truth.get("source_open_blocked_count"),
        "default_runtime_blocker_count": source_truth.get("default_runtime_blocker_count"),
        "implementation_blocker_count": source_truth.get("implementation_blocker_count"),
        "active_sql_json_tier_repair_count": counts.get("active_sql_json_tier_repair", 0),
        "below_stop_or_invalidation_review_only_count": counts.get("below_stop_or_invalidation_review_only", 0),
        "monitor_only_context_count": counts.get("monitor_only_context", 0),
        "legacy_42_deprecated_residue_count": counts.get("legacy_42_deprecated_residue", 0),
        "unknown_needs_source_open_count": counts.get("unknown_needs_source_open", 0),
        "legacy_42_archive_already_applied_or_ready": source_truth.get("legacy_42_archive_already_applied_or_ready"),
        "next_safe_action": packet.get("next_safe_action"),
    }


def validate_packet(packet: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    boundary = as_dict(packet.get("authority_boundary"))
    for key, value in boundary.items():
        if key.endswith("_allowed") or key.endswith("_inferred") or key == "default_runtime_blocker_authority":
            if value is not False:
                errors.append(f"authority_boundary_{key}_must_be_false")
    inputs = as_dict(packet.get("inputs"))
    for name, descriptor in inputs.items():
        desc = as_dict(descriptor)
        if desc.get("required") and desc.get("present") is not True:
            errors.append(f"missing_required_input:{name}:{desc.get('path')}")
    source_truth = as_dict(packet.get("source_open_truth"))
    wf85_count = as_dict(source_truth.get("wf85_source_open_status_counts")).get("blocked")
    if isinstance(wf85_count, int) and wf85_count != source_truth.get("source_open_blocked_count"):
        errors.append(f"wf85_blocked_count_mismatch:{wf85_count}!={source_truth.get('source_open_blocked_count')}")
    if source_truth.get("default_runtime_blocker_count") not in (0, None):
        errors.append("default_runtime_blocker_count_must_be_zero")
    if as_dict(packet.get("summary")).get("unknown_needs_source_open_count") not in (0, None):
        warnings.append("unknown_source_open_rows_remain")
    if as_dict(packet.get("summary")).get("active_sql_json_tier_repair_count") == 0:
        warnings.append("no_active_sql_json_tier_repair_rows_classified")
    return {
        "status": "ok" if not errors else "blocked",
        "errors": errors,
        "warnings": warnings,
    }


def render_markdown(packet: dict[str, Any]) -> str:
    summary = as_dict(packet.get("summary"))
    lines = [
        "# WF88 Source-Open Residue Classifier",
        "",
        "## Verdict",
        "",
        "The WF85 source-open blocked rows are not implementation blockers and should not drag default runtime closeout. They remain finance-domain context or SQL/JSON repair rows until a separate owner-approved deletion/archive packet exists.",
        "",
        "## Summary",
        "",
        f"- Source-open blocked rows: `{summary.get('source_open_blocked_count')}`",
        f"- Default runtime blockers: `{summary.get('default_runtime_blocker_count')}`",
        f"- WF85 implementation blockers: `{summary.get('implementation_blocker_count')}`",
        f"- Active SQL/JSON Tier A/B repair rows: `{summary.get('active_sql_json_tier_repair_count')}`",
        f"- Below-stop/invalidation review-only rows: `{summary.get('below_stop_or_invalidation_review_only_count')}`",
        f"- Monitor-only context rows: `{summary.get('monitor_only_context_count')}`",
        f"- Legacy/deprecated residue rows: `{summary.get('legacy_42_deprecated_residue_count')}`",
        f"- Unknown rows: `{summary.get('unknown_needs_source_open_count')}`",
        "",
        "## Policy",
        "",
        "- Default validators should not treat these rows as implementation blockers.",
        "- Active SQL/JSON repair rows stay visible as finance-domain evidence debt.",
        "- Current finance rows are not delete targets; deletion applies only to exact legacy artifacts after owner approval.",
        "",
        "## Rows",
        "",
    ]
    for row in as_list(packet.get("rows")):
        row_dict = as_dict(row)
        lines.append(
            f"- `{row_dict.get('ticker')}`: `{row_dict.get('classification')}`, tier `{row_dict.get('auto_tier')}`, state `{row_dict.get('decision_state')}`"
        )
    return "\n".join(lines) + "\n"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--write-md", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--pretty", action="store_true")
    parser.add_argument("--out", type=Path, default=OUT)
    parser.add_argument("--md-out", type=Path, default=MD_OUT)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    packet = build_packet()
    out = args.out if args.out.is_absolute() else ROOT / args.out
    md_out = args.md_out if args.md_out.is_absolute() else ROOT / args.md_out
    if args.write:
        atomic_write_json(out, packet)
    if args.write_md:
        atomic_write_text(md_out, render_markdown(packet))
    response = {
        "status": packet.get("status"),
        "summary": packet.get("summary"),
        "validation": packet.get("validation"),
        "out": rel(out) if args.write else None,
        "md_out": rel(md_out) if args.write_md else None,
    }
    print(json.dumps(packet if args.pretty else response, indent=2, sort_keys=True))
    if args.validate and as_dict(packet.get("validation")).get("status") != "ok":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
