#!/usr/bin/env python3
"""Build the WF75 operator review and external-delivery gate.

This is an internal proof/checklist surface. It can make the local WF75
deliverables ready for operator review, but it must keep customer delivery,
public launch, legal/compliance/source-licensing readiness, advice, account
action, and execution blocked until separate explicit gates exist.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, atomic_write_text, load_json_artifact
from wf75_deliverable_packager import as_dict, excel_contract_ready, pdf_contract_ready

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"

SCHEMA = "veritas.wf75.operator_delivery_gate.v1"
DEFAULT_OUT = TMP / "wf75-operator-delivery-gate.json"
DEFAULT_MD = TMP / "wf75-operator-delivery-gate.md"

SOURCE_PATHS = {
    "customer_safe_pdf_renderer": TMP / "wf75-customer-safe-pdf-renderer.json",
    "customer_safe_excel_exporter": TMP / "wf75-customer-safe-excel-exporter.json",
    "deliverable_packager": TMP / "wf75-deliverable-packager.json",
    "finance_delivery_series": TMP / "finance-delivery-series.json",
}

AUTHORITY_BOUNDARY = {
    "review_only_internal_service_led": True,
    "operator_review_packet_ready": True,
    "customer_external_delivery_allowed": False,
    "public_launch_allowed": False,
    "real_customer_data_allowed": False,
    "legal_compliance_source_licensing_ready": False,
    "source_licensing_assumed": False,
    "personalized_advice_allowed": False,
    "advice_execution_brokerage_account_allowed": False,
    "paper_or_live_execution_allowed": False,
    "portfolio_or_canon_mutation_allowed": False,
    "owner_approval_inferred": False,
}

REQUIRED_FALSE_BOUNDARIES = [
    key for key, value in AUTHORITY_BOUNDARY.items() if value is False
]

FORBIDDEN_CLAIMS = [
    "customer ready",
    "launch ready",
    "legal ready",
    "compliance ready",
    "external delivery allowed",
    "source licensing ready",
    "owner approved",
    "trading allowed",
]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path | None) -> str | None:
    if path is None:
        return None
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def load_sources() -> dict[str, dict[str, Any]]:
    sources: dict[str, dict[str, Any]] = {}
    for key, path in SOURCE_PATHS.items():
        payload = load_json_artifact(path)
        sources[key] = payload if isinstance(payload, dict) else {}
    return sources


def nested(payload: dict[str, Any], *keys: str) -> Any:
    item: Any = payload
    for key in keys:
        if not isinstance(item, dict):
            return None
        item = item.get(key)
    return item


def validation_status(payload: dict[str, Any]) -> Any:
    return as_dict(payload.get("validation")).get("status") or payload.get("validation_status")


def source_probe(key: str, path: Path, payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "key": key,
        "path": rel(path),
        "exists": path.exists(),
        "parseable_json": bool(payload),
        "status": payload.get("status") or as_dict(payload.get("summary")).get("status") or "missing",
        "validation_status": validation_status(payload),
        "generated_at_utc": payload.get("generated_at_utc"),
    }


def check_result(check_id: str, status: str, evidence: str, blocker: str | None = None) -> dict[str, Any]:
    return {
        "check_id": check_id,
        "status": status,
        "evidence": evidence,
        "blocker": blocker,
    }


def seeded_bad_ok(pdf: dict[str, Any], excel: dict[str, Any]) -> bool:
    pdf_seeded = as_dict(pdf.get("seeded_bad_status"))
    excel_seeded = as_dict(excel.get("seeded_bad_status"))
    return (
        pdf_seeded.get("status") == "ok"
        and as_dict(excel_seeded.get("json_validation")).get("expected_error") is True
        and as_dict(excel_seeded.get("markdown_validation")).get("expected_error") is True
    )


def finance_manual_gate_ok(finance: dict[str, Any]) -> bool:
    gate = as_dict(nested(finance, "delivery_program", "saas_deliverable_gate"))
    authority = as_dict(finance.get("authority_boundary"))
    return (
        finance.get("status") == "ok"
        and validation_status(finance) == "ok"
        and gate.get("automation_status") == "paused_manual_gate"
        and gate.get("manual_generation_allowed") is True
        and gate.get("cron_generation_allowed") is False
        and authority.get("customer_or_external_delivery_allowed") is False
        and authority.get("public_launch_allowed") is False
        and authority.get("source_licensing_assumed") is False
        and authority.get("legal_or_compliance_ready") is False
    )


def packager_ok(packager: dict[str, Any]) -> bool:
    return packager.get("status") == "ok" and validation_status(packager) == "ok"


def policy_gate_design() -> list[dict[str, Any]]:
    return [
        {
            "gate": "privacy_retention_export_delete_access",
            "status": "required_not_approved",
            "must_exist_before": "real customer data, customer account data, or retained customer output",
            "decision_owner": "Randall plus qualified legal/compliance review when external use is considered",
        },
        {
            "gate": "source_licensing_posture",
            "status": "required_not_ready",
            "must_exist_before": "external/customer delivery, public launch, marketing claims, or redistribution",
            "decision_owner": "Randall plus source/licensing review",
        },
        {
            "gate": "legal_compliance_review",
            "status": "required_not_ready",
            "must_exist_before": "regulated advice framing, public launch, customer terms, disclaimers, or service claims",
            "decision_owner": "qualified counsel/compliance review",
        },
        {
            "gate": "delivery_channel_and_rollback",
            "status": "required_not_approved",
            "must_exist_before": "email, portal, customer download, API, or other external delivery channel",
            "decision_owner": "Randall",
        },
        {
            "gate": "operator_signoff",
            "status": "manual_review_required",
            "must_exist_before": "any future external-delivery approval packet",
            "decision_owner": "Veritas main session and Randall",
        },
    ]


def operator_checklist(sources: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    pdf = sources["customer_safe_pdf_renderer"]
    excel = sources["customer_safe_excel_exporter"]
    packager = sources["deliverable_packager"]
    finance = sources["finance_delivery_series"]
    pdf_ready = pdf_contract_ready(pdf)
    excel_ready = excel_contract_ready(excel)
    seeded_ready = seeded_bad_ok(pdf, excel)
    packager_ready = packager_ok(packager)
    finance_ready = finance_manual_gate_ok(finance)
    return [
        check_result(
            "pdf_html_contract_validated",
            "pass" if pdf_ready else "block",
            f"status={pdf.get('status')} validation={validation_status(pdf)} html={nested(pdf, 'html_contract', 'status')} pdf={nested(pdf, 'pdf_contract', 'status')}",
            None if pdf_ready else "PDF/HTML customer-safe renderer contract is not clean.",
        ),
        check_result(
            "excel_csv_contract_validated",
            "pass" if excel_ready else "block",
            f"status={excel.get('status')} validation={validation_status(excel)} rows={excel.get('row_count')} row_scan_errors={nested(excel, 'validation_counts', 'row_scan_errors')}",
            None if excel_ready else "Excel/CSV customer-safe export contract is not clean.",
        ),
        check_result(
            "seeded_bad_fail_closed",
            "pass" if seeded_ready else "block",
            "Seeded-bad JSON and Markdown validations are required to fail with critical findings.",
            None if seeded_ready else "Seeded-bad regression proof is missing or weakened.",
        ),
        check_result(
            "deliverable_packager_clean",
            "pass" if packager_ready else "block",
            f"status={packager.get('status')} validation={validation_status(packager)}",
            None if packager_ready else "WF75 packager is not clean.",
        ),
        check_result(
            "finance_delivery_manual_gate_paused",
            "pass" if finance_ready else "block",
            (
                f"status={finance.get('status')} validation={validation_status(finance)} "
                f"automation={nested(finance, 'delivery_program', 'saas_deliverable_gate', 'automation_status')} "
                f"cron={nested(finance, 'delivery_program', 'saas_deliverable_gate', 'cron_generation_allowed')}"
            ),
            None if finance_ready else "Finance-delivery series is not cleanly paused behind manual gate.",
        ),
        check_result(
            "policy_source_legal_gate_design",
            "designed_blocked",
            "Required privacy/retention/export/delete/access, source licensing, legal/compliance, delivery channel, rollback, and operator signoff gates are explicit.",
            "These gates are design requirements only; they are not approved.",
        ),
        check_result(
            "external_delivery_decision",
            "blocked",
            "External delivery remains blocked until all policy/source/legal/operator/owner gates are explicitly approved.",
            "No customer/public/external delivery authority exists.",
        ),
    ]


def build_payload() -> dict[str, Any]:
    sources = load_sources()
    checks = operator_checklist(sources)
    blocking_checks = [row for row in checks if row.get("status") == "block"]
    technical_ready = not blocking_checks
    source_status = {
        key: source_probe(key, SOURCE_PATHS[key], sources.get(key, {}))
        for key in SOURCE_PATHS
    }
    external_delivery_status = "blocked_policy_source_legal_owner_gates"
    payload = {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "workflow": "WF75",
        "status": "ready_for_operator_review_external_blocked" if technical_ready else "blocked",
        "operator_review_status": "ready_for_manual_operator_review" if technical_ready else "blocked_by_technical_gate",
        "external_delivery_status": external_delivery_status,
        "source_status": source_status,
        "operator_checklist": checks,
        "policy_gate_design": policy_gate_design(),
        "authority_boundary": AUTHORITY_BOUNDARY,
        "output_paths": {
            "manifest": rel(DEFAULT_OUT),
            "markdown": rel(DEFAULT_MD),
        },
        "next_safe_action": (
            "Use this packet for operator review of the internal WF75 deliverable contracts. "
            "Do not approve customer/external delivery until privacy/retention/export/delete/access, "
            "source licensing, qualified legal/compliance review, delivery-channel rollback, and Randall "
            "explicit approval gates exist and validate."
        ),
    }
    payload["validation"] = validate_payload(payload)
    if payload["validation"]["status"] != "ok":
        payload["status"] = "blocked"
        payload["operator_review_status"] = "blocked_by_validation"
    return payload


def validate_payload(payload: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    if payload.get("schema") != SCHEMA:
        errors.append("schema_mismatch")
    boundary = as_dict(payload.get("authority_boundary"))
    for key in REQUIRED_FALSE_BOUNDARIES:
        if boundary.get(key) is not False:
            errors.append(f"authority_{key}_not_false")
    for key in ("review_only_internal_service_led", "operator_review_packet_ready"):
        if boundary.get(key) is not True:
            errors.append(f"authority_{key}_not_true")
    if payload.get("external_delivery_status") != "blocked_policy_source_legal_owner_gates":
        errors.append("external_delivery_status_not_blocked")
    for key, item in as_dict(payload.get("source_status")).items():
        if not as_dict(item).get("exists"):
            errors.append(f"missing_source:{key}")
        elif not as_dict(item).get("parseable_json"):
            errors.append(f"unparseable_source:{key}")
    blocking_checks = [
        row.get("check_id")
        for row in as_list(payload.get("operator_checklist"))
        if isinstance(row, dict) and row.get("status") == "block"
    ]
    if blocking_checks:
        errors.append("operator_check_blocks:" + ",".join(str(item) for item in blocking_checks))
    all_text = json.dumps(payload, sort_keys=True).lower()
    for claim in FORBIDDEN_CLAIMS:
        if claim in all_text:
            errors.append(f"forbidden_claim:{claim}")
    return {"status": "ok" if not errors else "error", "errors": errors}


def render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# WF75 Operator Review and External-Delivery Gate",
        "",
        f"- Generated: `{payload.get('generated_at_utc')}`",
        f"- Status: `{payload.get('status')}`",
        f"- Operator review: `{payload.get('operator_review_status')}`",
        f"- External delivery: `{payload.get('external_delivery_status')}`",
        "",
        "## Operator Checklist",
        "",
        "| Check | Status | Evidence | Blocker |",
        "|---|---|---|---|",
    ]
    for row in as_list(payload.get("operator_checklist")):
        if not isinstance(row, dict):
            continue
        lines.append(
            "| {check} | {status} | {evidence} | {blocker} |".format(
                check=row.get("check_id", ""),
                status=row.get("status", ""),
                evidence=str(row.get("evidence") or "").replace("|", "/"),
                blocker=str(row.get("blocker") or "").replace("|", "/"),
            )
        )
    lines.extend(["", "## Policy Gate Design", ""])
    for row in as_list(payload.get("policy_gate_design")):
        if isinstance(row, dict):
            lines.append(
                "- `{gate}`: `{status}`; before `{before}`; owner `{owner}`".format(
                    gate=row.get("gate"),
                    status=row.get("status"),
                    before=row.get("must_exist_before"),
                    owner=row.get("decision_owner"),
                )
            )
    lines.extend(["", "## Authority Boundary", ""])
    for key, value in as_dict(payload.get("authority_boundary")).items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(["", f"## Next Safe Action\n\n{payload.get('next_safe_action')}", ""])
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the WF75 operator review and delivery-gate packet.")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--md-out", type=Path, default=DEFAULT_MD)
    return parser.parse_args()


def absolutize(path: Path) -> Path:
    return path if path.is_absolute() else ROOT / path


def main() -> int:
    args = parse_args()
    out = absolutize(args.out)
    md_out = absolutize(args.md_out)
    payload = build_payload()
    if args.write:
        payload["output_paths"] = {"manifest": rel(out), "markdown": rel(md_out)}
        atomic_write_json(out, payload)
        atomic_write_text(md_out, render_markdown(payload))
    errors = as_list(as_dict(payload.get("validation")).get("errors"))
    print(
        "status={status} operator={operator} external={external} errors={errors}".format(
            status=payload.get("status"),
            operator=payload.get("operator_review_status"),
            external=payload.get("external_delivery_status"),
            errors=len(errors),
        )
    )
    return 0 if (not args.validate or not errors) else 2


if __name__ == "__main__":
    raise SystemExit(main())
