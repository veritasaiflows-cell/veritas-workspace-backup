from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = ROOT / "tmp" / "wf70-official-source-inventory.json"
DEFAULT_OUTPUT = ROOT / "tmp" / "wf70-official-source-inventory-validation.json"
PACKETS_PATH = ROOT / "tmp" / "fundamental-ir-reconciliation-packets.json"
CONTRACT_PATH = ROOT / "data" / "fundamentals" / "official-ir-capture-contract.json"

FORBIDDEN_TRUE_AUTHORITY = [
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
REQUIRED_SOURCES = {"ir_home", "earnings_release", "sec_exhibit", "investor_presentation", "transcript"}
REQUIRED_FIELDS = {
    "adjusted_eps",
    "guidance",
    "growth_bridge",
    "segment_margins",
    "orders_backlog",
    "management_explanation",
    "acquisition_debt_notes",
}
ALLOWED_SOURCE_STATUS = {"known", "not_fetched", "missing_metadata", "manual_required"}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def add(findings: list[dict[str, Any]], severity: str, code: str, message: str, field: str | None = None) -> None:
    item: dict[str, Any] = {"severity": severity, "code": code, "message": message}
    if field:
        item["field"] = field
    findings.append(item)


def validate_authority(authority: Any, findings: list[dict[str, Any]], prefix: str) -> None:
    if not isinstance(authority, dict):
        add(findings, "critical", "authority_missing", f"{prefix} authority block is required", prefix)
        return
    if authority.get("review_packet_generation_allowed") is not True:
        add(findings, "critical", "review_packet_generation_not_allowed", f"{prefix} review generation must be true", prefix)
    if authority.get("official_source_evidence_allowed") is not True:
        add(findings, "critical", "official_source_evidence_not_allowed", f"{prefix} official-source evidence must be true", prefix)
    for key in FORBIDDEN_TRUE_AUTHORITY:
        if authority.get(key) is not False:
            add(findings, "critical", "authority_not_hard_false", f"{prefix}.{key} must be false", f"{prefix}.{key}")


def build_report(input_path: Path) -> dict[str, Any]:
    findings: list[dict[str, Any]] = []
    payload = load_json(input_path)
    contract = load_json(CONTRACT_PATH)
    packets = load_json(PACKETS_PATH)
    packet_tickers = sorted(str(packet.get("ticker")) for packet in packets.get("packets", []) if packet.get("ticker"))
    rows = payload.get("rows")

    validate_authority(payload.get("authority"), findings, "authority")
    validate_authority(contract.get("authority"), findings, "contract.authority")

    field_dictionary = payload.get("field_dictionary")
    if not isinstance(field_dictionary, dict):
        add(findings, "critical", "field_dictionary_missing", "field_dictionary block is required", "field_dictionary")
    else:
        missing_fields = sorted(REQUIRED_FIELDS - set(field_dictionary))
        if missing_fields:
            add(findings, "critical", "field_dictionary_incomplete", "missing fields: " + ", ".join(missing_fields), "field_dictionary")

    if not isinstance(rows, list):
        add(findings, "critical", "rows_missing", "rows list is required", "rows")
        rows = []
    row_tickers = sorted(str(row.get("ticker")) for row in rows if isinstance(row, dict) and row.get("ticker"))
    if row_tickers != packet_tickers:
        add(findings, "critical", "ticker_coverage_mismatch", "inventory tickers must exactly match current fundamental IR reconciliation packet tickers", "rows")

    for idx, row in enumerate(rows):
        if not isinstance(row, dict):
            add(findings, "critical", "row_invalid", f"row {idx} is not an object", f"rows[{idx}]")
            continue
        ticker = row.get("ticker") or f"row_{idx}"
        if row.get("review_only") is not True:
            add(findings, "critical", "row_not_review_only", f"{ticker} must be review_only=true", f"rows[{idx}].review_only")
        if row.get("resolved_for_apply") is not False:
            add(findings, "critical", "row_apply_ready", f"{ticker} must not claim apply readiness", f"rows[{idx}].resolved_for_apply")
        if row.get("official_capture_status") != "manual_required":
            add(findings, "critical", "row_capture_not_manual_required", f"{ticker} Phase 1 inventory must remain manual_required", f"rows[{idx}].official_capture_status")
        validate_authority(row.get("authority"), findings, f"rows[{idx}].authority")
        sources = row.get("sources")
        if not isinstance(sources, dict):
            add(findings, "critical", "sources_missing", f"{ticker} sources block missing", f"rows[{idx}].sources")
            continue
        missing_sources = sorted(REQUIRED_SOURCES - set(sources))
        if missing_sources:
            add(findings, "critical", "source_inventory_incomplete", f"{ticker} missing sources: " + ", ".join(missing_sources), f"rows[{idx}].sources")
        for name, source in sources.items():
            if not isinstance(source, dict):
                add(findings, "critical", "source_invalid", f"{ticker}.{name} source candidate must be object", f"rows[{idx}].sources.{name}")
                continue
            status = source.get("status")
            if status not in ALLOWED_SOURCE_STATUS:
                add(findings, "critical", "source_status_invalid", f"{ticker}.{name} invalid status {status}", f"rows[{idx}].sources.{name}.status")
            if source.get("captured_artifact") is not None:
                add(findings, "critical", "phase1_capture_artifact_present", f"{ticker}.{name} should not claim capture artifact in Phase 1 inventory", f"rows[{idx}].sources.{name}.captured_artifact")
            if source.get("retrieval_status") != "not_fetched":
                add(findings, "critical", "phase1_retrieval_not_degraded", f"{ticker}.{name} retrieval_status must be not_fetched", f"rows[{idx}].sources.{name}.retrieval_status")

    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    if summary.get("inventory_count") != len(row_tickers) or summary.get("packet_equity_count") != len(packet_tickers):
        add(findings, "critical", "summary_count_mismatch", "summary counts must match rows and packet ticker count", "summary")

    critical = sum(1 for finding in findings if finding["severity"] == "critical")
    warning = sum(1 for finding in findings if finding["severity"] == "warning")
    return {
        "generated_at_utc": utc_now(),
        "status": "critical" if critical else "warning" if warning else "ok",
        "input": str(input_path.relative_to(ROOT)).replace("\\", "/") if input_path.is_absolute() else str(input_path),
        "summary": {"critical": critical, "warning": warning, "findings": len(findings), "packet_equity_count": len(packet_tickers), "inventory_count": len(row_tickers)},
        "authority": {
            "review_only": True,
            "canonical_note_mutation_allowed": False,
            "portfolio_mutation_allowed": False,
            "trade_or_account_action_allowed": False,
            "owner_approval_inferred": False,
        },
        "findings": findings,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate WF70 official source inventory contract and coverage.")
    parser.add_argument("--input", default=str(DEFAULT_INPUT))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    report = build_report(Path(args.input))
    if args.write:
        atomic_write_json(Path(args.output), report)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 1 if report["summary"]["critical"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
