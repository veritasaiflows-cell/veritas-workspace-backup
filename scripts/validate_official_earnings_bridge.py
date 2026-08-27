from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, load_json_artifact

WORKSPACE = Path(__file__).resolve().parents[1]
TMP = WORKSPACE / "tmp"
INPUT_PATH = TMP / "official-earnings-bridge.json"
OUT_PATH = TMP / "official-earnings-bridge-validation.json"
EVIDENCE_SPINE_PATH = TMP / "wf70-wf66-official-evidence-spine.json"
EVIDENCE_SPINE_VALIDATION_PATH = TMP / "wf70-wf66-official-evidence-spine-validation.json"
FORBIDDEN_TRUE_AUTHORITY_FIELDS = {
    "canonical_note_mutation_allowed",
    "portfolio_mutation_allowed",
    "deployment_authority_allowed",
    "owner_approval_inferred",
    "trade_or_account_action_allowed",
    "sizing_sleeve_cash_risk_rule_authority",
}
REQUIRED_UNRESOLVED_OFFICIAL_FIELDS = {
    "adjusted_eps",
    "guidance",
    "growth_bridge",
    "segment_margins",
    "orders_backlog",
    "management_explanation",
    "acquisition_debt_notes",
}
REQUIRED_SOURCE_FRESHNESS_FIELDS = {
    "source_url",
    "source_type",
    "retrieval_status",
    "manual_capture_date",
    "as_of_period",
    "freshness_status",
}
BANK_NATIVE_FIELDS = {
    "rotce",
    "roe",
    "nim",
    "deposits",
    "funding_liquidity",
    "provisions",
    "net_charge_offs",
    "allowance_reserves",
    "efficiency_ratio",
}
ALLOWED_CAPTURE_STATUSES = {"manual_required", "official_captured", "not_disclosed_in_release", "partial", "not_applicable"}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate review-only official earnings bridge artifact.")
    parser.add_argument("input", nargs="?", default=str(INPUT_PATH.relative_to(WORKSPACE)), help="Bridge artifact JSON")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--strict", action="store_true", help="Exit non-zero on warnings as well as criticals")
    return parser.parse_args()


def add(findings: list[dict[str, Any]], severity: str, code: str, message: str, ticker: str | None = None) -> None:
    item: dict[str, Any] = {"severity": severity, "code": code, "message": message}
    if ticker:
        item["ticker"] = ticker
    findings.append(item)


def validate_authority(authority: Any, findings: list[dict[str, Any]], scope: str, ticker: str | None = None) -> None:
    if not isinstance(authority, dict):
        add(findings, "critical", "authority_missing", f"Authority block missing or invalid at {scope}.", ticker)
        return
    for field in FORBIDDEN_TRUE_AUTHORITY_FIELDS:
        if authority.get(field) is True:
            add(findings, "critical", "authority_widened", f"Forbidden authority field {field}=true at {scope}.", ticker)


def https_or_missing(value: Any) -> bool:
    return isinstance(value, str) and value.startswith("https://")


def validate_source_freshness(block: Any, findings: list[dict[str, Any]], ticker: str | None) -> None:
    if not isinstance(block, dict):
        add(findings, "critical", "source_freshness_missing", "source_freshness must be object-shaped.", ticker)
        return
    missing = sorted(REQUIRED_SOURCE_FRESHNESS_FIELDS - set(block))
    if missing:
        add(findings, "critical", "source_freshness_fields_missing", f"source_freshness missing fields: {', '.join(missing)}.", ticker)
    if block.get("retrieval_status") not in {"not_fetched", "manual_confirmed", "source_verified"}:
        add(findings, "critical", "source_freshness_retrieval_invalid", "source_freshness.retrieval_status must be not_fetched, source_verified, or manual_confirmed.", ticker)
    if block.get("freshness_status") not in {"manual_required", "source_verified_not_review_fresh", "current", "stale"}:
        add(findings, "critical", "source_freshness_status_invalid", "source_freshness.freshness_status must be manual_required/source_verified_not_review_fresh/current/stale.", ticker)
    if block.get("freshness_status") == "current" and block.get("retrieval_status") != "manual_confirmed":
        add(findings, "critical", "source_freshness_false_current", "Current source freshness requires manual_confirmed retrieval.", ticker)


def value_without_capture(value: Any, bridge: dict[str, Any]) -> bool:
    if value in (None, "", [], {}):
        return False
    freshness = bridge.get("source_freshness") if isinstance(bridge.get("source_freshness"), dict) else {}
    has_capture = bool(freshness.get("manual_capture_date") and freshness.get("source_url"))
    return not has_capture


def validate_evidence_claims(claims: Any, bridge: dict[str, Any], findings: list[dict[str, Any]], ticker: str | None) -> None:
    if not isinstance(claims, list):
        add(findings, "critical", "evidence_claims_invalid", "evidence_claims must be a list.", ticker)
        return
    for idx, claim in enumerate(claims):
        if not isinstance(claim, dict):
            add(findings, "critical", "evidence_claim_invalid", f"evidence_claims[{idx}] must be an object.", ticker)
            continue
        if claim.get("reconciled") is True:
            add(findings, "critical", "evidence_claim_false_reconciled", "No bridge claim may be reconciled before official manual capture.", ticker)
        if claim.get("manual_capture_required") is True and claim.get("value") not in (None, ""):
            if not (claim.get("manual_capture_date") and claim.get("source_url") and claim.get("source_section")):
                add(findings, "critical", "manual_value_without_capture", "Manual-required evidence claim has a value without manual_capture_date, source_url, and source_section.", ticker)
        if value_without_capture(claim.get("value"), bridge):
            add(findings, "critical", "evidence_value_without_source_capture", "Evidence claim value requires source_freshness manual capture metadata.", ticker)


def validate_bank_native_metrics(block: Any, findings: list[dict[str, Any]], ticker: str | None) -> None:
    if block is None:
        return
    if not isinstance(block, dict):
        add(findings, "critical", "bank_native_metrics_invalid", "bank_native_metrics must be object-shaped when present.", ticker)
        return
    if block.get("status") != "manual_required" or block.get("review_only") is not True or block.get("manual_review_required") is not True:
        add(findings, "critical", "bank_native_metrics_posture_invalid", "bank_native_metrics must remain manual_required/review_only/manual_review_required.", ticker)
    if block.get("source_required") != "official_company_ir_or_sec":
        add(findings, "critical", "bank_native_metrics_source_invalid", "bank_native_metrics.source_required must be official_company_ir_or_sec.", ticker)
    for field in BANK_NATIVE_FIELDS:
        if block.get(field) not in (None, ""):
            add(findings, "critical", "bank_native_metric_value_present", f"bank_native_metrics.{field} must stay placeholder-only until manual official capture is implemented.", ticker)


def validate_evidence_spine(bridge_tickers: set[str], findings: list[dict[str, Any]]) -> None:
    if not EVIDENCE_SPINE_PATH.exists() or not EVIDENCE_SPINE_VALIDATION_PATH.exists():
        add(findings, "critical", "official_evidence_spine_missing", "WF70/WF66 official evidence spine and validation artifacts are required.")
        return
    spine = load_json_artifact(EVIDENCE_SPINE_PATH)
    validation = load_json_artifact(EVIDENCE_SPINE_VALIDATION_PATH)
    if validation.get("status") != "ok" or validation.get("critical") not in (0, None):
        add(findings, "critical", "official_evidence_spine_not_clean", "WF70/WF66 official evidence spine validation must be clean before official earnings bridge passes.")
    records = spine.get("records") if isinstance(spine, dict) else []
    spine_tickers = {str(record.get("ticker") or "") for record in records if isinstance(record, dict)}
    missing = sorted(bridge_tickers - spine_tickers)
    if missing:
        add(findings, "critical", "official_evidence_spine_ticker_missing", f"Evidence spine missing bridge tickers: {', '.join(missing)}.")
    for record in records:
        if not isinstance(record, dict):
            continue
        ticker = str(record.get("ticker") or "")
        if ticker not in bridge_tickers:
            continue
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


def validate_bridge_row(row: Any, findings: list[dict[str, Any]]) -> None:
    if not isinstance(row, dict):
        add(findings, "critical", "bridge_row_invalid", "Each bridge row must be an object.")
        return
    ticker = str(row.get("ticker") or "")
    validate_authority(row.get("authority"), findings, "bridge_row", ticker)
    if row.get("status") not in {"manual_required", "source_verified_manual_reconciliation_pending", "manual_confirmed_official_source"}:
        add(findings, "critical", "bridge_row_status_invalid", "Bridge row status must be manual_required, source_verified_manual_reconciliation_pending, or manual_confirmed_official_source.", ticker)
    if row.get("source_posture") != "review_only" or row.get("review_only") is not True:
        add(findings, "critical", "bridge_row_not_review_only", "Bridge row must be review-only.", ticker)
    if row.get("manual_review_required") is not True:
        add(findings, "critical", "bridge_row_manual_review_missing", "Bridge row must require manual review.", ticker)
    bridge = row.get("official_earnings_bridge")
    if not isinstance(bridge, dict):
        add(findings, "critical", "official_earnings_bridge_missing", "official_earnings_bridge must be object-shaped.", ticker)
        return
    validate_authority(bridge, findings, "official_earnings_bridge", ticker)
    if bridge.get("status") != "manual_required" or bridge.get("reconciled") is not False:
        add(findings, "critical", "official_earnings_bridge_not_manual", "Bridge must remain manual_required and unreconciled.", ticker)
    if bridge.get("official_evidence_status") not in {"manual_required", "source_verified_manual_reconciliation_pending", "manual_confirmed"} or bridge.get("official_evidence_posture") != "review_only":
        add(findings, "critical", "official_evidence_posture_invalid", "official evidence must stay manual_required/source_verified/manual_confirmed and review_only.", ticker)
    if bridge.get("source_authority_level") not in {"official_company_ir_metadata_only", "verified_official_source_pending_reconciliation", "manual_confirmed_official_source"}:
        add(findings, "critical", "source_authority_level_invalid", "source_authority_level must be metadata-only, source-verified-pending-reconciliation, or manual-confirmed official source.", ticker)
    if bridge.get("source_posture") != "review_only" or bridge.get("review_only") is not True:
        add(findings, "critical", "official_earnings_bridge_not_review_only", "Bridge must remain review-only.", ticker)
    if bridge.get("manual_review_required") is not True:
        add(findings, "critical", "official_earnings_bridge_manual_review_missing", "Bridge must require manual review.", ticker)
    for field in ("official_earnings_release_url", "official_guidance_url"):
        if not https_or_missing(bridge.get(field)):
            add(findings, "critical", "official_source_url_invalid", f"{field} must be an https URL.", ticker)
    for block in ("growth_bridge", "adjusted_eps", "orders_backlog", "guidance", "management_explanation", "acquisition_debt_notes"):
        if not isinstance(bridge.get(block), dict):
            add(findings, "critical", "bridge_block_invalid", f"{block} must be an object.", ticker)
    unresolved = bridge.get("unresolved_official_fields")
    if not isinstance(unresolved, list):
        add(findings, "critical", "unresolved_official_fields_missing", "Bridge must list unresolved official fields.", ticker)
    elif bridge.get("official_evidence_status") == "manual_required" and not REQUIRED_UNRESOLVED_OFFICIAL_FIELDS.issubset(set(str(item) for item in unresolved)):
        add(findings, "critical", "unresolved_official_fields_missing", "Manual-required bridges must list all unresolved official fields.", ticker)
    validate_source_freshness(bridge.get("source_freshness"), findings, ticker)
    validate_evidence_claims(bridge.get("evidence_claims"), bridge, findings, ticker)
    validate_bank_native_metrics(bridge.get("bank_native_metrics"), findings, ticker)
    if not isinstance(bridge.get("segment_margins"), list):
        add(findings, "critical", "segment_margins_invalid", "segment_margins must be a list.", ticker)
    adjusted = bridge.get("adjusted_eps") or {}
    guidance = bridge.get("guidance") or {}
    if isinstance(adjusted, dict):
        if adjusted.get("status") not in ALLOWED_CAPTURE_STATUSES or adjusted.get("reconciled_to_gaap") is not False:
            add(findings, "critical", "adjusted_eps_bridge_not_manual", "Adjusted EPS bridge must remain an allowed review-only capture status and unreconciled.", ticker)
        if not isinstance(adjusted.get("adjustment_items"), list):
            add(findings, "critical", "adjustment_items_invalid", "adjustment_items must be a list.", ticker)
    if isinstance(guidance, dict) and guidance.get("status") not in ALLOWED_CAPTURE_STATUSES:
        add(findings, "critical", "guidance_bridge_not_manual", "Guidance bridge must remain an allowed review-only capture status.", ticker)


def build_report(path: Path) -> dict[str, Any]:
    findings: list[dict[str, Any]] = []
    payload = load_json_artifact(path)
    if not isinstance(payload, dict):
        add(findings, "critical", "payload_invalid", "Bridge payload must be a JSON object.")
        bridges: list[Any] = []
    else:
        bridges = payload.get("bridges") if isinstance(payload.get("bridges"), list) else []
        validate_authority(payload.get("authority"), findings, "payload")
        if payload.get("status") not in {"manual_required", "manual_confirmed_partial"} or payload.get("review_only") is not True or payload.get("manual_review_required") is not True:
            add(findings, "critical", "payload_posture_invalid", "Payload must be manual_required/manual_confirmed_partial, review_only, and manual_review_required.")
        summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
        if summary.get("official_values_fetched") not in (0, None) and not summary.get("validated_official_captures_consumed"):
            add(findings, "critical", "official_values_without_validated_capture", "Fetched official values require a validated official capture artifact.")
        if summary.get("invented_values_allowed") is not False:
            add(findings, "critical", "invented_values_allowed", "Invented values must be explicitly disallowed.")
    if not bridges:
        add(findings, "critical", "bridges_missing", "Bridge artifact must contain at least one bridge row.")
    bridge_tickers = {str(row.get("ticker") or "") for row in bridges if isinstance(row, dict)}
    validate_evidence_spine(bridge_tickers, findings)
    for row in bridges:
        validate_bridge_row(row, findings)
    critical = sum(1 for item in findings if item["severity"] == "critical")
    warning = sum(1 for item in findings if item["severity"] == "warning")
    return {
        "generated_at_utc": utc_now(),
        "status": "critical" if critical else ("warning" if warning else "ok"),
        "input": str(path.relative_to(WORKSPACE)).replace("\\", "/") if path.is_absolute() else str(path),
        "authority": {
            "review_only": True,
            "canonical_note_mutation_allowed": False,
            "portfolio_mutation_allowed": False,
            "deployment_authority_allowed": False,
            "trade_or_account_action_allowed": False,
        },
        "summary": {"bridges": len(bridges), "critical": critical, "warning": warning, "findings": len(findings)},
        "findings": findings,
    }


def main() -> int:
    args = parse_args()
    path = WORKSPACE / args.input
    report = build_report(path)
    if args.write:
        atomic_write_json(OUT_PATH, report, indent=2)
    print(json.dumps(report, indent=2))
    if report["summary"]["critical"]:
        return 1
    if args.strict and report["summary"]["warning"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
