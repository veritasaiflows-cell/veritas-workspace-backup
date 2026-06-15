from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, atomic_write_text

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
DATA = ROOT / "data" / "fundamentals"
CONTRACT_PATH = DATA / "official-ir-capture-contract.json"
METADATA_PATH = DATA / "company-ir-metadata.json"
PORTFOLIO_CONFIG_PATH = TMP / "portfolio-config.json"
PACKETS_PATH = TMP / "fundamental-ir-reconciliation-packets.json"
OUT_JSON = TMP / "wf70-official-source-inventory.json"
OUT_MD = TMP / "wf70-official-source-inventory.md"

AUTHORITY_FALSE_FIELDS = [
    "canonical_note_mutation_allowed",
    "portfolio_mutation_allowed",
    "deployment_authority_allowed",
    "owner_approval_inferred",
    "owner_approval_granted",
    "proposal_apply_allowed",
    "trade_execution_allowed",
    "trade_or_account_action_allowed",
    "brokerage_account_action_allowed",
    "money_movement_allowed",
    "sizing_allocation_action_allowed",
    "sizing_sleeve_cash_risk_rule_authority",
]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT)).replace("\\", "/")


def source_candidate(source_type: str, url: str | None, priority: int, notes: str) -> dict[str, Any]:
    status = "not_fetched" if url else "missing_metadata"
    return {
        "status": status,
        "url": url,
        "source_type": source_type,
        "priority": priority,
        "retrieval_status": "not_fetched",
        "captured_artifact": None,
        "latest_period": None,
        "notes": notes,
    }


def build_inventory() -> dict[str, Any]:
    contract = load_json(CONTRACT_PATH)
    metadata = load_json(METADATA_PATH)
    portfolio_config = load_json(PORTFOLIO_CONFIG_PATH)
    packets_artifact = load_json(PACKETS_PATH)

    tickers_meta = metadata.get("tickers") if isinstance(metadata.get("tickers"), dict) else {}
    tracked = portfolio_config.get("tracked_universe") if isinstance(portfolio_config.get("tracked_universe"), dict) else {}
    packets = packets_artifact.get("packets") if isinstance(packets_artifact.get("packets"), list) else []
    packet_tickers = [str(packet.get("ticker")) for packet in packets if packet.get("ticker")]

    rows: list[dict[str, Any]] = []
    missing_ir_metadata: list[str] = []
    partial_ir_metadata: list[str] = []

    for ticker in packet_tickers:
        meta = tickers_meta.get(ticker, {}) if isinstance(tickers_meta.get(ticker, {}), dict) else {}
        tracked_row = tracked.get(ticker, {}) if isinstance(tracked.get(ticker, {}), dict) else {}
        ir_home = meta.get("ir_home_url")
        earnings = meta.get("earnings_url")
        guidance = meta.get("guidance_url")
        if not meta:
            missing_ir_metadata.append(ticker)
        elif not ir_home or not earnings:
            partial_ir_metadata.append(ticker)

        sources = {
            "ir_home": source_candidate(
                "issuer_ir_home",
                ir_home,
                1,
                "Official issuer investor-relations home from company-ir-metadata; discovery only, not captured.",
            ),
            "earnings_release": source_candidate(
                "issuer_ir_earnings_release_candidate",
                earnings,
                2,
                "Candidate latest earnings release/results page from metadata; exact release/exhibit still not fetched.",
            ),
            "sec_exhibit": source_candidate(
                "sec_8k_exhibit_99_1_candidate",
                None,
                3,
                "SEC exhibit URL not resolved in Phase 1 inventory; requires SEC filing lookup/capture.",
            ),
            "investor_presentation": source_candidate(
                "issuer_investor_presentation_candidate",
                guidance,
                4,
                "Guidance/presentation candidate from metadata when available; exact presentation still not fetched.",
            ),
            "transcript": source_candidate(
                "issuer_transcript_candidate",
                None,
                5,
                "Official transcript/call remarks candidate not resolved in Phase 1 inventory; manual/source-specific capture required.",
            ),
        }

        if ir_home and earnings:
            inventory_status = "candidate_sources_known_not_fetched"
        elif ir_home or earnings:
            inventory_status = "partial_ir_metadata"
        else:
            inventory_status = "missing_ir_metadata"

        rows.append({
            "ticker": ticker,
            "company_name": meta.get("company_name"),
            "portfolio_role": tracked_row.get("portfolio_role"),
            "coverage_tier": tracked_row.get("coverage_tier"),
            "sector": tracked_row.get("sector"),
            "inventory_status": inventory_status,
            "official_capture_status": "manual_required",
            "manual_review_required": True,
            "review_only": True,
            "resolved_for_apply": False,
            "sources": sources,
            "authority": contract["authority"],
        })

    return {
        "schema_version": 1,
        "generated_at_utc": utc_now(),
        "workflow": "WF70",
        "source_posture": "review_only_phase_1_official_source_inventory",
        "contract_artifact": rel(CONTRACT_PATH),
        "source_artifacts": {
            "portfolio_config": rel(PORTFOLIO_CONFIG_PATH),
            "ir_metadata": rel(METADATA_PATH),
            "ir_reconciliation_packets": rel(PACKETS_PATH),
        },
        "authority": contract["authority"],
        "field_dictionary": contract["field_dictionary"],
        "source_priority": contract["source_priority"],
        "summary": {
            "packet_equity_count": len(packet_tickers),
            "inventory_count": len(rows),
            "missing_ir_metadata_count": len(missing_ir_metadata),
            "partial_ir_metadata_count": len(partial_ir_metadata),
            "missing_ir_metadata": missing_ir_metadata,
            "partial_ir_metadata": partial_ir_metadata,
            "all_sources_review_only": True,
            "all_captures_manual_required": True,
        },
        "rows": rows,
    }


def render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# WF70 Official Source Inventory",
        "",
        f"Generated: {payload['generated_at_utc']}",
        "",
        "Review-only Phase 1 inventory. It records source candidates and degraded states; it does not fetch, reconcile, approve, apply, or authorize any portfolio/trade/account action.",
        "",
        "## Summary",
        "",
        f"- Equity packets covered: {payload['summary']['inventory_count']} / {payload['summary']['packet_equity_count']}",
        f"- Missing IR metadata: {payload['summary']['missing_ir_metadata_count']}",
        f"- Partial IR metadata: {payload['summary']['partial_ir_metadata_count']}",
        "- Capture state: manual_required for all rows until validated ticker capture artifacts exist.",
        "",
        "## Rows",
        "",
        "| Ticker | Status | IR home | Earnings candidate | SEC exhibit | Presentation | Transcript |",
        "|---|---|---:|---:|---:|---:|---:|",
    ]
    for row in payload["rows"]:
        sources = row["sources"]
        lines.append(
            "| {ticker} | {status} | {ir} | {earn} | {sec} | {pres} | {trans} |".format(
                ticker=row["ticker"],
                status=row["inventory_status"],
                ir=sources["ir_home"]["status"],
                earn=sources["earnings_release"]["status"],
                sec=sources["sec_exhibit"]["status"],
                pres=sources["investor_presentation"]["status"],
                trans=sources["transcript"]["status"],
            )
        )
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build WF70 review-only official company source inventory.")
    parser.add_argument("--write", action="store_true", help="Write tmp/wf70-official-source-inventory artifacts.")
    args = parser.parse_args()
    payload = build_inventory()
    if args.write:
        atomic_write_json(OUT_JSON, payload)
        atomic_write_text(OUT_MD, render_markdown(payload))
    else:
        print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
