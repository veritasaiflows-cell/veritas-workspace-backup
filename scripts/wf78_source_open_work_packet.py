#!/usr/bin/env python3
"""Build WF78 source-open repair work packets.

The source-open executor classifies the remaining debt. This script turns that
classification into parallel-safe review work packets with concrete batches,
source lineage, and owner-readiness impact. It does not edit ticker cards,
deployment surfaces, canon, portfolio state, SQL canon/cache, or any execution
surface.
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
OUT = TMP / "wf78-source-open-work-packets.json"
SOURCE_EXECUTOR = TMP / "wf78-source-open-repair-execution.json"
FRESHNESS_LEDGER = TMP / "wf78-ticker-freshness-ledger.json"
DECISION_FACTORY = TMP / "finance-decision-factory.json"
DEPLOYMENT_SURFACE = TMP / "deployment-readiness-surface.json"
CARD_DIR = TMP / "ticker-intelligence-cards"
SCHEMA = "veritas.wf78_source_open_work_packets.v1"

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "work_packet_generation_only": True,
    "automated_non_capital_routing_allowed": True,
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

TRUE_AUTHORITY = {"review_only", "work_packet_generation_only", "automated_non_capital_routing_allowed"}
FALSE_AUTHORITY = {key for key in AUTHORITY_BOUNDARY if key not in TRUE_AUTHORITY}
TIER_ORDER = {"Tier A": 0, "Tier B": 1, "Tier C": 2}
DISPOSITION_ORDER = {
    "needs_position_sizing_surface": 0,
    "needs_deployment_readiness_surface": 1,
    "needs_source_artifact": 2,
    "needs_owner_entry_stop_source": 3,
    "repaired_from_owner_source": 4,
    "thin_monitor_hold": 5,
}
PACKET_META = {
    "needs_position_sizing_surface": {
        "lane": "position_sizing_surface",
        "title": "Position-Sizing / Deployment-Readiness Surface Rows",
        "owner": "WF78 source-open repair",
        "collision_group": "wf78_position_sizing_surface_review_packet",
        "parallel_safe": True,
        "next_command": "python scripts\\wf78_source_open_work_packet.py --write --validate",
        "acceptance": "Each row has source-backed entry/stop lineage and an explicit non-executing sizing/deployment-readiness recommendation target.",
    },
    "needs_deployment_readiness_surface": {
        "lane": "deployment_readiness_surface",
        "title": "Deployment-Readiness Surface Rows",
        "owner": "WF78 deployment-readiness review",
        "collision_group": "wf78_deployment_readiness_review_packet",
        "parallel_safe": True,
        "next_command": "python scripts\\wf78_source_open_work_packet.py --write --validate",
        "acceptance": "Each row is either mapped to a deployment surface group or preserved as a context blocker.",
    },
    "needs_source_artifact": {
        "lane": "source_artifact_capture",
        "title": "Owner / Source Artifact Capture Rows",
        "owner": "WF78 source-open evidence capture",
        "collision_group": "wf78_source_artifact_capture_review_packet",
        "parallel_safe": True,
        "next_command": "python scripts\\wf78_source_open_repair_executor.py --write --validate",
        "acceptance": "Each row gains owner entry/stop source evidence or remains blocked with explicit missing-source proof.",
    },
    "needs_owner_entry_stop_source": {
        "lane": "owner_entry_stop_source",
        "title": "Owner Entry/Stop Source Rows",
        "owner": "WF78 owner-source reconciliation",
        "collision_group": "wf78_owner_entry_stop_source_review_packet",
        "parallel_safe": False,
        "next_command": "python scripts\\wf78_source_open_repair_executor.py --write --validate",
        "acceptance": "Official-source pointers are reconciled to owner entry/stop source evidence without fabricating bands.",
    },
    "repaired_from_owner_source": {
        "lane": "rerun_verify",
        "title": "Rerun Verification Rows",
        "owner": "WF78 freshness verification",
        "collision_group": "wf78_freshness_verification",
        "parallel_safe": True,
        "next_command": "python scripts\\wf78_daily_freshness_loop.py --skip-provider-refresh --write --validate",
        "acceptance": "Rebuilt proof shows the source-open debt clears or remains explicitly blocked.",
    },
    "thin_monitor_hold": {
        "lane": "thin_monitor_hold",
        "title": "Thin Monitor Holds",
        "owner": "WF78 Tier C monitor",
        "collision_group": "wf78_thin_monitor_hold",
        "parallel_safe": True,
        "next_command": "monitor only",
        "acceptance": "Rows remain blocked/monitor-only until promotion or source-open evidence exists.",
    },
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


def ticker(value: Any) -> str:
    return str(value or "").strip().upper()


def by_ticker(rows: list[Any]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for item in rows:
        row = as_dict(item)
        symbol = ticker(row.get("ticker"))
        if symbol:
            out[symbol] = row
    return out


def card_for(symbol: str) -> dict[str, Any]:
    path = CARD_DIR / f"{symbol}.current.json"
    if not path.exists():
        return {}
    return load_dict(path)


def deployment_rows(surface: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    for group in as_dict(surface.get("groups")).values():
        for item in as_list(group):
            row = as_dict(item)
            symbol = ticker(row.get("ticker"))
            if symbol:
                rows[symbol] = row
    return rows


def decision_rows(factory: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return by_ticker(as_list(factory.get("decision_ledger")))


def current_band_context(symbol: str, card: dict[str, Any]) -> dict[str, Any]:
    band = as_dict(card.get("price_band_stop"))
    reference = as_dict(card.get("entry_stop_reference_metadata"))
    values = as_dict(reference.get("values"))
    lineage = as_dict(reference.get("source_lineage"))
    return {
        "latest_known_price": band.get("latest_known_price") or card.get("latest_known_price"),
        "entry_band_low": band.get("entry_band_low") or values.get("reference_price_low"),
        "entry_band_high": band.get("entry_band_high") or values.get("reference_price_high"),
        "stop_or_invalidation": band.get("stop_or_invalidation") or values.get("reference_invalidation_level"),
        "band_status": band.get("band_status"),
        "entry_stop_reference_status": reference.get("status"),
        "owner_source_path": lineage.get("owner_source_path") or values.get("reference_level_owner_source_path"),
        "owner_source_timestamp": lineage.get("source_timestamp") or values.get("reference_level_source_timestamp"),
        "owner_source_sha256": lineage.get("source_sha256") or values.get("reference_level_source_sha256"),
    }


def readiness_impact(symbol: str, executor_row: dict[str, Any], decision: dict[str, Any], deploy: dict[str, Any]) -> str:
    if decision.get("disposition") in {"owner_card_and_wf67_request_ready", "gate_deferred"}:
        return "capital_review_lane_already_has_owner_card_context"
    if deploy:
        return "deployment_surface_row_exists_but_stale_or_incomplete"
    if executor_row.get("auto_tier") == "Tier A":
        return "tier_a_repair_unblocks_decision_grade_review"
    if executor_row.get("auto_tier") == "Tier B":
        return "tier_b_repair_unblocks_promotion_review"
    return "monitor_only"


def work_action(disposition: str, symbol: str) -> str:
    if disposition == "needs_position_sizing_surface":
        return f"Prepare non-executing sizing/deployment-readiness review row for {symbol} from existing owner entry/stop lineage."
    if disposition == "needs_deployment_readiness_surface":
        return f"Prepare deployment-readiness review row for {symbol} or preserve blocker with source lineage."
    if disposition == "needs_source_artifact":
        return f"Capture/source-open owner entry/stop evidence for {symbol}; keep blocked if source is absent."
    if disposition == "needs_owner_entry_stop_source":
        return f"Reconcile official/source pointer to owner entry/stop source for {symbol}; no fabricated band."
    if disposition == "repaired_from_owner_source":
        return f"Rerun daily freshness proof to verify {symbol} clears source-open debt."
    if disposition == "thin_monitor_hold":
        return f"Keep {symbol} as monitor-only until promotion or owner source evidence exists."
    return f"Inspect {symbol}."


def sort_key(row: dict[str, Any]) -> tuple[int, int, int, int, str]:
    return (
        TIER_ORDER.get(str(row.get("auto_tier")), 9),
        DISPOSITION_ORDER.get(str(row.get("repair_disposition")), 99),
        -int(row.get("priority_score") or 0),
        int(row.get("queue_rank") or 99999),
        str(row.get("ticker") or ""),
    )


def build_items() -> list[dict[str, Any]]:
    executor = load_dict(SOURCE_EXECUTOR)
    freshness = by_ticker(as_list(load_dict(FRESHNESS_LEDGER).get("rows")))
    decisions = decision_rows(load_dict(DECISION_FACTORY))
    deploy_rows = deployment_rows(load_dict(DEPLOYMENT_SURFACE))
    items: list[dict[str, Any]] = []
    for source_row in sorted(as_list(executor.get("rows")), key=sort_key):
        row = as_dict(source_row)
        symbol = ticker(row.get("ticker"))
        disposition = str(row.get("repair_disposition") or "inspect")
        card = card_for(symbol)
        deploy = deploy_rows.get(symbol, {})
        decision = decisions.get(symbol, {})
        band = current_band_context(symbol, card)
        source_status = as_dict(row.get("source_status"))
        has_source_lineage = bool(
            source_status.get("entry_stop_reference_available")
            or band.get("owner_source_path")
            or source_status.get("official_registry_available")
        )
        items.append({
            "ticker": symbol,
            "auto_tier": row.get("auto_tier"),
            "route_state": row.get("route_state"),
            "queue_rank": row.get("queue_rank"),
            "priority_score": row.get("priority_score"),
            "repair_disposition": disposition,
            "repair_mode": row.get("repair_mode"),
            "readiness_impact": readiness_impact(symbol, row, decision, deploy),
            "freshness_state": freshness.get(symbol, {}).get("overall_freshness_state"),
            "current_band_context": band,
            "source_lineage_available": has_source_lineage,
            "deployment_surface_status": {
                "present": bool(deploy),
                "bucket": deploy.get("deployment_status") or deploy.get("surface_state") or deploy.get("display_label"),
                "source_artifact_path": deploy.get("source_artifact_path"),
                "source_generated_at_utc": deploy.get("source_generated_at_utc"),
            },
            "capital_review_context": {
                "factory_disposition": decision.get("disposition"),
                "owner_card_path": decision.get("owner_card_path"),
                "wf67_request_path": decision.get("wf67_request_path"),
                "gate_verdict": decision.get("gate_verdict"),
            },
            "work_action": work_action(disposition, symbol),
            "source_artifacts": sorted(set([
                rel(SOURCE_EXECUTOR),
                rel(FRESHNESS_LEDGER),
                rel(DECISION_FACTORY),
                rel(DEPLOYMENT_SURFACE),
                rel(CARD_DIR / f"{symbol}.current.json"),
            ])),
            "capital_deployment_approved": False,
            "trade_or_execution_approved": False,
            "paper_or_live_execution_allowed": False,
            "owner_approval_inferred": False,
        })
    return items


def build_packets(items: list[dict[str, Any]], batch_size: int) -> list[dict[str, Any]]:
    packets: list[dict[str, Any]] = []
    grouped: dict[str, list[dict[str, Any]]] = {}
    for item in items:
        grouped.setdefault(str(item.get("repair_disposition") or "inspect"), []).append(item)
    for disposition in sorted(grouped, key=lambda key: DISPOSITION_ORDER.get(key, 99)):
        meta = PACKET_META.get(disposition, {
            "lane": disposition,
            "title": disposition,
            "owner": "WF78 repair review",
            "collision_group": f"wf78_{disposition}",
            "parallel_safe": True,
            "next_command": "inspect",
            "acceptance": "Inspect rows and preserve stop lines.",
        })
        rows = grouped[disposition]
        for index in range(0, len(rows), batch_size):
            batch = rows[index:index + batch_size]
            packets.append({
                "packet_id": f"{meta['lane']}-{index // batch_size + 1:02d}",
                "lane": meta["lane"],
                "title": meta["title"],
                "owner": meta["owner"],
                "collision_group": meta["collision_group"],
                "parallel_safe": meta["parallel_safe"],
                "disposition": disposition,
                "ticker_count": len(batch),
                "tickers": [row["ticker"] for row in batch],
                "tier_counts": dict(Counter(str(row.get("auto_tier")) for row in batch).most_common()),
                "readiness_impact_counts": dict(Counter(str(row.get("readiness_impact")) for row in batch).most_common()),
                "next_command": meta["next_command"],
                "acceptance": meta["acceptance"],
                "rows": batch,
                "stop_lines": [
                    "Review packet only; do not mutate ticker cards, canon, portfolio, deployment surface, or SQL canon/cache.",
                    "No capital deployment, paper/live execution, brokerage/account action, money movement, or owner approval inference.",
                ],
            })
    return packets


def recommended_parallel_lanes(packets: list[dict[str, Any]]) -> list[dict[str, Any]]:
    candidates = [packet for packet in packets if packet.get("parallel_safe") and packet.get("ticker_count")]
    return [
        {
            "rank": idx,
            "packet_id": packet["packet_id"],
            "lane": packet["lane"],
            "ticker_count": packet["ticker_count"],
            "tickers": packet["tickers"],
            "collision_group": packet["collision_group"],
            "why": (
                "Best leverage: source-backed rows can become owner-review sizing/deployment readiness work "
                "without touching execution authority."
                if packet["lane"] == "position_sizing_surface"
                else "Independent proof lane; output remains review-only and main-session verified."
            ),
            "handoff": {
                "deliverable": "Review-only packet findings and exact residual blockers; no file mutation unless main session integrates.",
                "stop_lines": [
                    "No capital/execution/account action.",
                    "No canon/portfolio/ticker-card/deployment-surface mutation.",
                    "Do not fabricate source evidence.",
                ],
            },
        }
        for idx, packet in enumerate(candidates[:3], start=1)
    ]


def build_report(args: argparse.Namespace) -> dict[str, Any]:
    items = build_items()
    packets = build_packets(items, args.batch_size)
    disposition_counts = Counter(str(item.get("repair_disposition")) for item in items)
    tier_counts = Counter(str(item.get("auto_tier")) for item in items)
    impact_counts = Counter(str(item.get("readiness_impact")) for item in items)
    errors: list[str] = []
    for key in sorted(FALSE_AUTHORITY):
        if AUTHORITY_BOUNDARY.get(key) is not False:
            errors.append(f"authority flag not false: {key}")
    if any(
        item.get("capital_deployment_approved")
        or item.get("trade_or_execution_approved")
        or item.get("paper_or_live_execution_allowed")
        or item.get("owner_approval_inferred")
        for item in items
    ):
        errors.append("row authority boundary widened")
    if args.validate and not items:
        errors.append("no source-open work items found")
    return {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "blocked" if errors else "ok",
        "purpose": "Convert WF78 source-open repair dispositions into parallel-safe review work packets.",
        "authority_boundary": AUTHORITY_BOUNDARY,
        "source_artifacts": [
            rel(SOURCE_EXECUTOR),
            rel(FRESHNESS_LEDGER),
            rel(DECISION_FACTORY),
            rel(DEPLOYMENT_SURFACE),
            "tmp/ticker-intelligence-cards/*.current.json",
        ],
        "parameters": {"batch_size": args.batch_size},
        "summary": {
            "work_item_count": len(items),
            "packet_count": len(packets),
            "parallel_recommended_count": len(recommended_parallel_lanes(packets)),
            "tier_counts": dict(tier_counts.most_common()),
            "repair_disposition_counts": dict(disposition_counts.most_common()),
            "readiness_impact_counts": dict(impact_counts.most_common()),
            "top_recommendation": (
                "Start with packet position_sizing_surface-01, then source_artifact_capture-01; keep deployment/execution blocked."
                if packets else "No packet work available."
            ),
        },
        "packets": packets,
        "recommended_parallel_lanes": recommended_parallel_lanes(packets),
        "validation": {"status": "blocked" if errors else "ok", "errors": errors, "warnings": []},
        "stop_lines": [
            "This work-packet artifact is review-only and does not write repair rows into owner/canon/card surfaces.",
            "Packet acceptance can make evidence ready for owner review, not approved for capital deployment or execution.",
            "Randall's exact approval remains required before any paper/live/account/capital action.",
        ],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build WF78 source-open repair work packets.")
    parser.add_argument("--batch-size", type=int, default=12)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--out", type=Path, default=OUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.batch_size <= 0:
        raise SystemExit("--batch-size must be positive")
    report = build_report(args)
    if args.write:
        atomic_write_json(args.out, report)
        print(
            f"wrote {rel(args.out)} status={report['status']} "
            f"items={report['summary']['work_item_count']} packets={report['summary']['packet_count']}"
        )
    else:
        print(json.dumps(report["summary"], indent=2))
    if args.validate and report["validation"]["status"] != "ok":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
