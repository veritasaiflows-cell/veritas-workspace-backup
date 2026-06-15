from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, load_json_artifact

WORKSPACE = Path(__file__).resolve().parents[1]
TMP = WORKSPACE / "tmp"
DATA_DIR = WORKSPACE / "data" / "fundamentals"
METADATA_PATH = DATA_DIR / "company-ir-metadata.json"
PACKETS_PATH = TMP / "fundamental-ir-reconciliation-packets.json"
VALIDATION_PATH = TMP / "fundamental-ir-reconciliation-validation.json"
CONFIG_PATH = TMP / "portfolio-config.json"
EVIDENCE_SPINE_PATH = TMP / "wf70-wf66-official-evidence-spine.json"
EVIDENCE_SPINE_VALIDATION_PATH = TMP / "wf70-wf66-official-evidence-spine-validation.json"
SCHEMA_VERSION = 1
FORBIDDEN_TRUE_AUTHORITY_FIELDS = {
    "canonical_note_mutation_allowed",
    "portfolio_mutation_allowed",
    "deployment_authority_allowed",
    "owner_approval_inferred",
    "trade_or_account_action_allowed",
    "sizing_sleeve_cash_risk_rule_authority",
}
ETF_OR_PROXY = {"SLV", "TLT", "XLI", "XLB", "XLC", "PAVE", "XLF", "XLE", "ITA", "VAW", "VXUS"}
ETF_OR_PROXY_ROLES = {"etf_monitor"}
ALLOWED_CAPTURE_STATUSES = {"manual_required", "official_captured", "not_disclosed_in_release", "partial", "not_applicable"}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate review-only fundamental IR reconciliation packets.")
    parser.add_argument("--write", action="store_true", help="Write validation artifact.")
    parser.add_argument("--strict", action="store_true", help="Exit non-zero on warnings as well as critical findings.")
    return parser.parse_args()


def add(findings: list[dict[str, Any]], severity: str, code: str, message: str, ticker: str | None = None) -> None:
    item: dict[str, Any] = {"severity": severity, "code": code, "message": message}
    if ticker:
        item["ticker"] = ticker
    findings.append(item)


def equity_tickers() -> set[str]:
    cfg = load_json_artifact(CONFIG_PATH)
    tracked = (cfg.get("tracked_universe") if isinstance(cfg, dict) else {}) or {}
    return {
        ticker
        for ticker, meta in tracked.items()
        if ticker not in ETF_OR_PROXY
        and isinstance(meta, dict)
        and str(meta.get("coverage_lane") or "").lower() != "macro"
        and str(meta.get("portfolio_role") or "").lower() not in ETF_OR_PROXY_ROLES
    }


def validate_authority(authority: Any, findings: list[dict[str, Any]], scope: str, ticker: str | None = None) -> None:
    if not isinstance(authority, dict):
        add(findings, "critical", "authority_missing", f"Authority block missing or invalid at {scope}.", ticker)
        return
    for field in FORBIDDEN_TRUE_AUTHORITY_FIELDS:
        if authority.get(field) is True:
            add(findings, "critical", "authority_widened", f"Forbidden authority field {field}=true at {scope}.", ticker)


def validate_evidence_spine(expected: set[str], findings: list[dict[str, Any]]) -> None:
    if not EVIDENCE_SPINE_PATH.exists() or not EVIDENCE_SPINE_VALIDATION_PATH.exists():
        add(findings, "critical", "official_evidence_spine_missing", "WF70/WF66 official evidence spine and validation artifacts are required.")
        return
    spine = load_json_artifact(EVIDENCE_SPINE_PATH)
    validation = load_json_artifact(EVIDENCE_SPINE_VALIDATION_PATH)
    if validation.get("status") != "ok" or validation.get("critical") not in (0, None):
        add(findings, "critical", "official_evidence_spine_not_clean", "WF70/WF66 official evidence spine validation must be clean before reconciliation packets pass.")
    records = spine.get("records") if isinstance(spine, dict) else []
    spine_tickers = {str(record.get("ticker") or "") for record in records if isinstance(record, dict)}
    missing = sorted(expected - spine_tickers)
    if missing:
        add(findings, "critical", "official_evidence_spine_ticker_missing", f"Evidence spine missing equity tickers: {', '.join(missing)}.")
    for record in records:
        if not isinstance(record, dict):
            continue
        ticker = str(record.get("ticker") or "")
        validate_authority(record.get("authority"), findings, "official_evidence_spine", ticker)
        source_evidence = record.get("source_evidence") if isinstance(record.get("source_evidence"), dict) else {}
        for source_type in ("official_company_release", "sec_exhibit", "investor_presentation", "transcript"):
            if source_type not in source_evidence:
                add(findings, "critical", "official_evidence_source_state_missing", f"Evidence spine missing source state {source_type}.", ticker)
        fields = {str(field.get("field") or ""): field for field in record.get("priority_fields", []) if isinstance(field, dict)}
        for field_name in ("adjusted_eps", "guidance", "revenue_growth_bridge", "segment_margins", "orders_backlog_book_to_bill", "management_explanation", "acquisition_debt_notes"):
            field = fields.get(field_name)
            if not field:
                add(findings, "critical", "official_evidence_priority_field_missing", f"Evidence spine missing priority field {field_name}.", ticker)
            elif field.get("status") not in ALLOWED_CAPTURE_STATUSES | {"missing"}:
                add(findings, "critical", "official_evidence_priority_field_status_invalid", f"Evidence spine invalid status for {field_name}.", ticker)


def validate_official_earnings_bridge(bridge: Any, findings: list[dict[str, Any]], ticker: str) -> None:
    if not isinstance(bridge, dict):
        add(findings, "critical", "official_earnings_bridge_missing", "official_earnings_bridge must be present and object-shaped.", ticker)
        return
    validate_authority(bridge, findings, "official_earnings_bridge", ticker)
    if bridge.get("status") != "manual_required":
        add(findings, "critical", "official_earnings_bridge_status_invalid", "official_earnings_bridge.status must remain manual_required until an apply-specific bridge exists.", ticker)
    if bridge.get("source_posture") != "review_only" or bridge.get("review_only") is not True:
        add(findings, "critical", "official_earnings_bridge_not_review_only", "official_earnings_bridge must be review-only.", ticker)
    if bridge.get("manual_review_required") is not True:
        add(findings, "critical", "official_earnings_bridge_manual_review_missing", "official_earnings_bridge must require manual review.", ticker)
    if bridge.get("reconciled") is not False:
        add(findings, "critical", "official_earnings_bridge_reconciled_without_apply_bridge", "official_earnings_bridge must not claim apply reconciliation in V1.3.", ticker)
    for field in ("official_earnings_release_url", "official_guidance_url"):
        value = bridge.get(field)
        if not isinstance(value, str) or not value.startswith("https://"):
            add(findings, "critical", "official_earnings_bridge_url_invalid", f"{field} must be an https URL.", ticker)
    for block in ("growth_bridge", "adjusted_eps", "orders_backlog", "guidance", "management_explanation", "acquisition_debt_notes"):
        if not isinstance(bridge.get(block), dict):
            add(findings, "critical", "official_earnings_bridge_block_invalid", f"{block} must be an object.", ticker)
    if not isinstance(bridge.get("segment_margins"), list):
        add(findings, "critical", "official_earnings_bridge_segment_margins_invalid", "segment_margins must be a list.", ticker)
    adjusted = bridge.get("adjusted_eps") or {}
    guidance = bridge.get("guidance") or {}
    if isinstance(adjusted, dict):
        if adjusted.get("status") not in ALLOWED_CAPTURE_STATUSES or adjusted.get("reconciled_to_gaap") is not False:
            add(findings, "critical", "official_earnings_bridge_adjusted_eps_must_remain_review_only", "adjusted_eps bridge must remain an allowed review-only capture status and unreconciled.", ticker)
        if not isinstance(adjusted.get("adjustment_items"), list):
            add(findings, "critical", "official_earnings_bridge_adjustment_items_invalid", "adjustment_items must be a list.", ticker)
    if isinstance(guidance, dict) and guidance.get("status") not in ALLOWED_CAPTURE_STATUSES:
        add(findings, "critical", "official_earnings_bridge_guidance_must_remain_review_only", "guidance bridge must remain an allowed review-only capture status.", ticker)


def main() -> int:
    args = parse_args()
    findings: list[dict[str, Any]] = []
    expected = equity_tickers()
    metadata = load_json_artifact(METADATA_PATH)
    packets_payload = load_json_artifact(PACKETS_PATH)
    meta_tickers = set(((metadata.get("tickers") if isinstance(metadata, dict) else {}) or {}).keys())
    packets = (packets_payload.get("packets") if isinstance(packets_payload, dict) else []) or []
    validate_authority(metadata.get("authority") if isinstance(metadata, dict) else None, findings, "metadata")
    validate_authority(packets_payload.get("authority") if isinstance(packets_payload, dict) else None, findings, "packet_payload")
    validate_evidence_spine(expected, findings)

    for ticker in sorted(expected - meta_tickers):
        add(findings, "critical", "ir_metadata_missing", "Equity ticker missing official IR URL metadata.", ticker)
    packet_tickers = set()
    for packet in packets:
        if not isinstance(packet, dict):
            add(findings, "critical", "packet_invalid", "Each packet must be an object.")
            continue
        ticker = str(packet.get("ticker") or "")
        packet_tickers.add(ticker)
        validate_authority(packet.get("authority"), findings, "packet", ticker)
        urls = packet.get("source_urls") or {}
        for field in ("ir_home_url", "earnings_url", "guidance_url"):
            value = urls.get(field)
            if not isinstance(value, str) or not value.startswith("https://"):
                add(findings, "critical", "official_ir_url_invalid", f"{field} must be an https URL.", ticker)
        for block in ("adjusted_eps_reconciliation", "guidance_reconciliation"):
            rec = packet.get(block) or {}
            if rec.get("status") != "manual_required" or rec.get("reconciled") is not False:
                add(findings, "critical", "reconciliation_must_remain_manual", f"{block} must be manual_required and unreconciled in V1.2.", ticker)
        validate_official_earnings_bridge(packet.get("official_earnings_bridge"), findings, ticker)
        if packet.get("manual_review_required") is not True:
            add(findings, "critical", "manual_review_not_required", "Packet must require manual review.", ticker)
    for ticker in sorted(expected - packet_tickers):
        add(findings, "critical", "ir_packet_missing", "Equity ticker missing IR reconciliation packet.", ticker)

    critical = sum(1 for f in findings if f["severity"] == "critical")
    warning = sum(1 for f in findings if f["severity"] == "warning")
    output = {
        "generated_at_utc": utc_now(),
        "status": "critical" if critical else ("warning" if warning else "ok"),
        "input": str(PACKETS_PATH.relative_to(WORKSPACE)),
        "metadata": str(METADATA_PATH.relative_to(WORKSPACE)),
        "authority": {
            "review_only": True,
            "canonical_note_mutation_allowed": False,
            "portfolio_mutation_allowed": False,
            "deployment_authority_allowed": False,
            "trade_or_account_action_allowed": False,
        },
        "summary": {"expected_equity_tickers": len(expected), "packets": len(packet_tickers), "critical": critical, "warning": warning, "findings": len(findings)},
        "findings": findings,
    }
    if args.write:
        atomic_write_json(VALIDATION_PATH, output)
    print(json.dumps(output, indent=2))
    if critical:
        return 1
    if args.strict and warning:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
