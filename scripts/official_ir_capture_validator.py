from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = ROOT / "tmp" / "official-ir-captures" / "goog-q1-2026.json"
DEFAULT_OUTPUT = ROOT / "tmp" / "official-ir-captures" / "goog-q1-2026-validation.json"

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

REQUIRED_FIELDS = {
    "adjusted_eps",
    "guidance",
    "growth_bridge",
    "segment_margins",
    "orders_backlog",
    "management_explanation",
    "acquisition_debt_notes",
}

ALLOWED_STATUS = {"official_captured", "not_disclosed_in_release", "not_applicable", "manual_required", "partial"}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def add(findings: list[dict[str, Any]], severity: str, code: str, message: str, field: str | None = None) -> None:
    item: dict[str, Any] = {"severity": severity, "code": code, "message": message}
    if field:
        item["field"] = field
    findings.append(item)


def validate_authority(payload: dict[str, Any], findings: list[dict[str, Any]]) -> None:
    authority = payload.get("authority")
    if not isinstance(authority, dict):
        add(findings, "critical", "authority_missing", "authority block is required")
        return
    if authority.get("review_packet_generation_allowed") is not True:
        add(findings, "critical", "review_packet_generation_not_allowed", "review packet generation should be explicitly allowed")
    if authority.get("official_source_evidence_allowed") is not True:
        add(findings, "critical", "official_source_evidence_not_allowed", "official source evidence should be explicitly allowed")
    for key in FORBIDDEN_TRUE_AUTHORITY:
        if authority.get(key) is not False:
            add(findings, "critical", "authority_not_hard_false", f"{key} must be false", f"authority.{key}")


def validate_source(payload: dict[str, Any], findings: list[dict[str, Any]]) -> None:
    source = payload.get("source")
    if not isinstance(source, dict):
        add(findings, "critical", "source_missing", "source block is required")
        return
    if source.get("source_type") not in {
        "sec_8k_exhibit_99_1",
        "issuer_ir_release",
        "sec_10q_official_report",
        "sec_10k_official_report",
    }:
        add(findings, "critical", "source_type_invalid", "source_type must be an official SEC/IR release/report type", "source.source_type")
    if not str(source.get("source_url", "")).startswith("https://"):
        add(findings, "critical", "source_url_invalid", "source_url must be https", "source.source_url")
    if not source.get("retrieved_at_utc"):
        add(findings, "critical", "retrieval_timestamp_missing", "retrieved_at_utc is required", "source.retrieved_at_utc")
    if not source.get("source_text_sha256"):
        add(findings, "critical", "source_hash_missing", "source_text_sha256 is required", "source.source_text_sha256")


def evidence_ok(block: dict[str, Any]) -> bool:
    return bool(block.get("source_url") and block.get("source_section") and block.get("excerpt"))


def validate_field(name: str, block: Any, findings: list[dict[str, Any]]) -> None:
    if not isinstance(block, dict):
        add(findings, "critical", "capture_field_invalid", f"{name} must be object-shaped", name)
        return
    status = block.get("status")
    if status not in ALLOWED_STATUS:
        add(findings, "critical", "capture_status_invalid", f"{name}.status invalid: {status}", f"captures.{name}.status")
    if status in {"official_captured", "not_disclosed_in_release", "partial"} and not evidence_ok(block):
        add(findings, "critical", "capture_missing_evidence", f"{name} requires source_url, source_section, and excerpt", f"captures.{name}")
    if block.get("inferred") is not False:
        add(findings, "critical", "capture_inference_flag_invalid", f"{name}.inferred must be false", f"captures.{name}.inferred")
    if not isinstance(block.get("period"), str) or not block.get("period", "").strip():
        add(findings, "critical", "capture_period_missing", f"{name}.period is required", f"captures.{name}.period")
    if status == "official_captured" and block.get("value") in (None, "", [], {}):
        add(findings, "critical", "captured_value_missing", f"{name} is captured but value is empty", f"captures.{name}.value")


def build_report(path: Path) -> dict[str, Any]:
    findings: list[dict[str, Any]] = []
    payload = load_json(path)
    ticker = payload.get("ticker")
    if not isinstance(ticker, str) or not ticker.strip():
        add(findings, "critical", "ticker_invalid", "ticker is required", "ticker")
    if payload.get("review_only") is not True:
        add(findings, "critical", "review_only_missing", "payload must be review_only=true", "review_only")
    validate_authority(payload, findings)
    validate_source(payload, findings)
    captures = payload.get("captures")
    if not isinstance(captures, dict):
        add(findings, "critical", "captures_missing", "captures block is required")
    else:
        missing = sorted(REQUIRED_FIELDS - set(captures))
        if missing:
            add(findings, "critical", "capture_fields_missing", "missing required fields: " + ", ".join(missing), "captures")
        for name in sorted(REQUIRED_FIELDS & set(captures)):
            validate_field(name, captures.get(name), findings)
    if payload.get("resolved_for_apply") is not False:
        add(findings, "critical", "resolved_for_apply_not_false", "official capture must not claim apply readiness", "resolved_for_apply")
    critical = sum(1 for f in findings if f["severity"] == "critical")
    warning = sum(1 for f in findings if f["severity"] == "warning")
    return {
        "generated_at_utc": utc_now(),
        "status": "critical" if critical else "warning" if warning else "ok",
        "input": str(path.relative_to(ROOT)).replace("\\", "/") if path.is_absolute() else str(path),
        "authority": {
            "review_only": True,
            "canonical_note_mutation_allowed": False,
            "portfolio_mutation_allowed": False,
            "trade_or_account_action_allowed": False,
            "owner_approval_inferred": False,
        },
        "summary": {"critical": critical, "warning": warning, "findings": len(findings)},
        "findings": findings,
    }


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(path)


def validate_one(input_path: Path, output_path: Path | None, write: bool) -> dict[str, Any]:
    report = build_report(input_path)
    if write:
        target = output_path if output_path else input_path.with_name(input_path.stem + "-validation.json")
        write_json(target, report)
    return report


def build_all_report(reports: list[dict[str, Any]]) -> dict[str, Any]:
    critical = sum(int(report.get("summary", {}).get("critical", 0)) for report in reports)
    warning = sum(int(report.get("summary", {}).get("warning", 0)) for report in reports)
    return {
        "generated_at_utc": utc_now(),
        "status": "critical" if critical else "warning" if warning else "ok",
        "input_glob": "tmp/official-ir-captures/*.json",
        "authority": {
            "review_only": True,
            "canonical_note_mutation_allowed": False,
            "portfolio_mutation_allowed": False,
            "trade_or_account_action_allowed": False,
            "owner_approval_inferred": False,
        },
        "summary": {
            "captures_checked": len(reports),
            "critical": critical,
            "warning": warning,
            "findings": sum(int(report.get("summary", {}).get("findings", 0)) for report in reports),
        },
        "reports": reports,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate review-only official IR/SEC earnings capture artifact.")
    parser.add_argument("--input", default=str(DEFAULT_INPUT))
    parser.add_argument("--output", default=None)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--all", action="store_true", help="Validate every non-validation JSON capture under tmp/official-ir-captures.")
    args = parser.parse_args()
    if args.all:
        capture_dir = ROOT / "tmp" / "official-ir-captures"
        input_paths = sorted(
            path for path in capture_dir.glob("*.json")
            if not path.name.endswith("-validation.json")
        )
        reports = [validate_one(path, None, args.write) for path in input_paths]
        report = build_all_report(reports)
        if args.output and args.write:
            write_json(Path(args.output), report)
        print(json.dumps(report, indent=2, sort_keys=True))
        return 1 if report["summary"]["critical"] else 0
    input_path = Path(args.input)
    output_path = Path(args.output) if args.output else None
    report = validate_one(input_path, output_path, args.write)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 1 if report["summary"]["critical"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
