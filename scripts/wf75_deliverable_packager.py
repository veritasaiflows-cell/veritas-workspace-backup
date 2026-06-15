#!/usr/bin/env python3
"""Plan and package WF75 polished PDF and Excel deliverables.

This is an internal/service-led packaging spine. It does not deliver externally,
use real customer data, make legal/compliance/source-licensing claims, mutate
finance canon/portfolio state, or authorize paper/live/account action.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import xlsxwriter

from market_data_utils import atomic_write_json, atomic_write_text, load_json_artifact

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
DEFAULT_OUT = TMP / "wf75-deliverable-packager.json"
DEFAULT_PLAN = TMP / "wf75-deliverable-packaging-plan.json"
DEFAULT_MD = TMP / "wf75-deliverable-packaging-plan.md"
DEFAULT_XLSX = TMP / "wf75-deliverables-workbook.xlsx"

SOURCE_PATHS = {
    "service_state": TMP / "wf75-service-state-current.json",
    "operator_console": TMP / "wf75-operator-console.json",
    "scenario_library": TMP / "wf75-scenario-template-library.json",
    "renderer_regression": TMP / "wf75-renderer-export-regression.json",
    "pm_readiness_pdf": TMP / "wf75-pm-readiness-brief.json",
    "artifact_handoff": TMP / "wf75-artifact-only-pm-handoff.json",
    "wf75_capsule": ROOT / "state" / "workflows" / "WF75.json",
}

REQUIRED_FALSE_BOUNDARIES = [
    "public_launch_allowed",
    "real_customer_data_allowed",
    "external_delivery_allowed",
    "legal_or_compliance_ready",
    "source_licensing_assumed",
    "portfolio_or_canon_mutation_allowed",
    "paper_or_live_execution_allowed",
    "brokerage_or_account_action_allowed",
    "owner_approval_inferred",
]


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


def artifact_probe(path: Path) -> dict[str, Any]:
    item = {
        "path": rel(path),
        "exists": path.exists(),
        "parseable_json": False,
        "status": "missing",
        "validation_status": None,
    }
    if not path.exists():
        return item
    payload = load_json_artifact(path)
    item["parseable_json"] = isinstance(payload, dict)
    if isinstance(payload, dict):
        item["status"] = str(payload.get("status") or as_dict(payload.get("summary")).get("status") or "present")
        item["validation_status"] = as_dict(payload.get("validation")).get("status")
    return item


def load_sources() -> dict[str, dict[str, Any]]:
    sources: dict[str, dict[str, Any]] = {}
    for key, path in SOURCE_PATHS.items():
        payload = load_json_artifact(path)
        sources[key] = payload if isinstance(payload, dict) else {}
    return sources


def scenario_rows(sources: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    library = sources.get("scenario_library") or {}
    rows = as_list(library.get("scenarios") or library.get("scenario_templates"))
    cleaned = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        cleaned.append(
            {
                "scenario_id": row.get("scenario_id") or row.get("id"),
                "scenario": row.get("scenario"),
                "request_type": row.get("request_type"),
                "ticker_set": ", ".join(str(item) for item in as_list(row.get("ticker_set"))),
                "expected_validator_outcome": row.get("expected_validator_outcome"),
            }
        )
    return cleaned


def build_plan(sources: dict[str, dict[str, Any]] | None = None) -> dict[str, Any]:
    sources = sources or load_sources()
    console = sources.get("operator_console") or {}
    service = sources.get("service_state") or {}
    pdf = sources.get("pm_readiness_pdf") or {}
    capsule = sources.get("wf75_capsule") or {}
    console_summary = as_dict(console.get("summary"))
    service_summary = as_dict(service.get("summary"))
    pdf_outputs = as_dict(pdf.get("outputs"))

    deliverables = [
        {
            "id": "internal_pm_readiness_pdf",
            "format": "PDF",
            "audience": "Randall / internal PM review",
            "status": "implemented_refreshable",
            "current_artifact": pdf_outputs.get("pdf") or "tmp/wf75-pm-readiness-brief.pdf",
            "producer": "python scripts\\wf75_pm_readiness_pdf.py --write --validate",
            "purpose": "Fixed-layout readiness brief for internal review, blockers, proof, and next safe action.",
            "next_enhancement": "Tighten visual hierarchy, include deliverable roadmap and service-state snapshot once plan stabilizes.",
        },
        {
            "id": "customer_safe_research_pdf",
            "format": "PDF",
            "audience": "future customer-safe review packet after gates",
            "status": "planned_gated",
            "current_artifact": None,
            "producer": "future renderer over validated customer-safe export only",
            "purpose": "Polished anonymous research packet with visible freshness, evidence, risks, and non-advice language.",
            "next_enhancement": "Promote only after export validator, no-leak checks, source/freshness proof, and operator review are clean.",
        },
        {
            "id": "internal_operator_excel",
            "format": "XLSX",
            "audience": "Randall / Veritas operator",
            "status": "implemented_this_pass",
            "current_artifact": rel(DEFAULT_XLSX),
            "producer": "python scripts\\wf75_deliverable_packager.py --write --validate",
            "purpose": "Workbook view of readiness, deliverables, scenarios, artifact status, and authority gates.",
            "next_enhancement": "Add scenario-by-scenario QA metrics and source freshness rows as the service-state slice expands.",
        },
        {
            "id": "customer_safe_excel_export",
            "format": "XLSX/CSV",
            "audience": "future customer-safe export after gates",
            "status": "planned_gated",
            "current_artifact": None,
            "producer": "future sanitized workbook exporter over customer-safe export JSON only",
            "purpose": "Structured watchlist/evidence table that hides internal paths, proof traces, and execution language.",
            "next_enhancement": "Block until export/delete/retention policy, source-licensing posture, and customer-safe validator are approved.",
        },
    ]

    authority = {
        "review_only": True,
        "internal_service_led": True,
        "customer_output_gated": True,
        "public_launch_allowed": False,
        "real_customer_data_allowed": False,
        "external_delivery_allowed": False,
        "legal_or_compliance_ready": False,
        "source_licensing_assumed": False,
        "portfolio_or_canon_mutation_allowed": False,
        "paper_or_live_execution_allowed": False,
        "brokerage_or_account_action_allowed": False,
        "owner_approval_inferred": False,
    }

    phases = [
        {
            "phase": 1,
            "name": "Refresh internal PM PDF and operator workbook",
            "status": "implemented_this_pass",
            "acceptance": "PM PDF manifest validates; workbook writes with readiness, deliverables, scenarios, artifacts, and gates.",
        },
        {
            "phase": 2,
            "name": "Customer-safe PDF renderer contract",
            "status": "next",
            "acceptance": "Renderer consumes only customer-safe export JSON and no-leak/no-claim validator passes.",
        },
        {
            "phase": 3,
            "name": "Customer-safe Excel/CSV export contract",
            "status": "next",
            "acceptance": "Structured export includes source/freshness/risk labels, hides internals, and blocks advice/execution language.",
        },
        {
            "phase": 4,
            "name": "Polish and QA regression suite",
            "status": "planned",
            "acceptance": "Clean scenarios pass; seeded-bad PDF/Excel exports fail for leaks, stale claims, and directive language.",
        },
        {
            "phase": 5,
            "name": "Operator review and delivery gate",
            "status": "planned_gated",
            "acceptance": "No external delivery until policy, source, legal/compliance, and owner approval gates are explicit.",
        },
    ]

    return {
        "schema": "veritas.wf75.deliverable_packaging_plan.v1",
        "generated_at_utc": utc_now(),
        "workflow": "WF75",
        "status": "ready_for_internal_packaging_review",
        "readiness_context": {
            "workflow_status": capsule.get("effective_status"),
            "workflow_next_action": capsule.get("next_action"),
            "service_status": service.get("status") or service_summary.get("status"),
            "operator_console_status": console.get("status"),
            "operator_console_summary": {
                "scenario_count": console_summary.get("scenario_count"),
                "service_state_status": console_summary.get("service_state_status"),
                "renderer_status": console_summary.get("renderer_status"),
                "pm_brief_status": console_summary.get("pm_brief_status"),
            },
        },
        "deliverables": deliverables,
        "phases": phases,
        "artifact_status": {key: artifact_probe(path) for key, path in SOURCE_PATHS.items()},
        "scenario_rows": scenario_rows(sources),
        "authority_boundary": authority,
        "next_safe_action": (
            "Use this as the WF75 deliverable spine: keep internal PM PDF and internal operator Excel live now; "
            "build customer-safe PDF/Excel only after validator, no-leak, source/freshness, policy, and operator gates are clean."
        ),
    }


def render_markdown(plan: dict[str, Any]) -> str:
    lines = [
        "# WF75 Polished PDF and Excel Deliverable Plan",
        "",
        f"- Generated: `{plan.get('generated_at_utc')}`",
        f"- Status: `{plan.get('status')}`",
        f"- Next safe action: {plan.get('next_safe_action')}",
        "",
        "## Deliverables",
        "",
        "| ID | Format | Status | Audience | Artifact |",
        "|---|---|---|---|---|",
    ]
    for row in as_list(plan.get("deliverables")):
        if not isinstance(row, dict):
            continue
        lines.append(
            "| {id} | {format} | {status} | {audience} | {artifact} |".format(
                id=row.get("id", ""),
                format=row.get("format", ""),
                status=row.get("status", ""),
                audience=row.get("audience", ""),
                artifact=row.get("current_artifact") or "",
            )
        )
    lines.extend(["", "## Gates", ""])
    for key, value in as_dict(plan.get("authority_boundary")).items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(["", "## Phases", ""])
    for row in as_list(plan.get("phases")):
        if isinstance(row, dict):
            lines.append(f"- Phase {row.get('phase')}: {row.get('name')} - `{row.get('status')}`")
    lines.append("")
    return "\n".join(lines)


def write_sheet(workbook: xlsxwriter.Workbook, name: str, rows: list[dict[str, Any]]) -> None:
    sheet = workbook.add_worksheet(name[:31])
    title_fmt = workbook.add_format({"bold": True, "font_size": 14, "font_color": "#1F2937"})
    header_fmt = workbook.add_format({"bold": True, "bg_color": "#D9EAF7", "border": 1})
    cell_fmt = workbook.add_format({"border": 1, "valign": "top", "text_wrap": True})
    sheet.write(0, 0, name, title_fmt)
    if not rows:
        sheet.write(2, 0, "No rows", cell_fmt)
        return
    headers = list(rows[0].keys())
    for col, header in enumerate(headers):
        sheet.write(2, col, header, header_fmt)
        sheet.set_column(col, col, min(max(len(header) + 4, 14), 38))
    for r_idx, row in enumerate(rows, start=3):
        for c_idx, header in enumerate(headers):
            value = row.get(header)
            if isinstance(value, (dict, list)):
                value = json.dumps(value, sort_keys=True)
            sheet.write(r_idx, c_idx, "" if value is None else str(value), cell_fmt)
    sheet.freeze_panes(3, 0)
    sheet.autofilter(2, 0, 2 + len(rows), len(headers) - 1)


def write_workbook(plan: dict[str, Any], out: Path = DEFAULT_XLSX) -> dict[str, Any]:
    out.parent.mkdir(parents=True, exist_ok=True)
    workbook = xlsxwriter.Workbook(str(out))
    workbook.set_properties(
        {
            "title": "WF75 Deliverables Workbook",
            "subject": "Internal WF75 PDF and Excel deliverable packaging plan",
            "author": "Veritas",
            "comments": "Internal review only; no external delivery or approval authority.",
        }
    )
    readiness = as_dict(plan.get("readiness_context"))
    write_sheet(
        workbook,
        "Readiness",
        [
            {"field": key, "value": value}
            for key, value in readiness.items()
            if key != "operator_console_summary"
        ]
        + [
            {"field": f"operator.{key}", "value": value}
            for key, value in as_dict(readiness.get("operator_console_summary")).items()
        ],
    )
    write_sheet(workbook, "Deliverables", [row for row in as_list(plan.get("deliverables")) if isinstance(row, dict)])
    write_sheet(workbook, "Phases", [row for row in as_list(plan.get("phases")) if isinstance(row, dict)])
    write_sheet(workbook, "Scenarios", [row for row in as_list(plan.get("scenario_rows")) if isinstance(row, dict)])
    artifact_rows = []
    for key, item in as_dict(plan.get("artifact_status")).items():
        row = {"artifact_key": key}
        row.update(as_dict(item))
        artifact_rows.append(row)
    write_sheet(workbook, "Artifacts", artifact_rows)
    gate_rows = [{"gate": key, "value": value} for key, value in as_dict(plan.get("authority_boundary")).items()]
    write_sheet(workbook, "Authority Gates", gate_rows)
    workbook.close()
    return {"path": rel(out), "exists": out.exists(), "size_bytes": out.stat().st_size if out.exists() else 0}


def validate_plan(plan: dict[str, Any], workbook_result: dict[str, Any] | None = None) -> list[str]:
    errors: list[str] = []
    if plan.get("schema") != "veritas.wf75.deliverable_packaging_plan.v1":
        errors.append("schema_mismatch")
    deliverable_ids = {row.get("id") for row in as_list(plan.get("deliverables")) if isinstance(row, dict)}
    for required in {
        "internal_pm_readiness_pdf",
        "customer_safe_research_pdf",
        "internal_operator_excel",
        "customer_safe_excel_export",
    }:
        if required not in deliverable_ids:
            errors.append(f"missing_deliverable:{required}")
    boundary = as_dict(plan.get("authority_boundary"))
    for key in REQUIRED_FALSE_BOUNDARIES:
        if boundary.get(key) is not False:
            errors.append(f"authority_{key}_not_false")
    if boundary.get("review_only") is not True or boundary.get("internal_service_led") is not True:
        errors.append("review_only_internal_service_led_not_true")
    for key, item in as_dict(plan.get("artifact_status")).items():
        if not as_dict(item).get("exists"):
            errors.append(f"missing_source_artifact:{key}")
        if not as_dict(item).get("parseable_json"):
            errors.append(f"unparseable_source_artifact:{key}")
    if workbook_result is not None:
        if not workbook_result.get("exists") or int(workbook_result.get("size_bytes") or 0) <= 0:
            errors.append("workbook_missing_or_empty")
    all_text = json.dumps(plan, sort_keys=True).lower()
    for forbidden in ["public launch ready", "external delivery allowed", "trading allowed", "owner approval inferred"]:
        if forbidden in all_text:
            errors.append(f"forbidden_claim:{forbidden}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--plan-out", type=Path, default=DEFAULT_PLAN)
    parser.add_argument("--md-out", type=Path, default=DEFAULT_MD)
    parser.add_argument("--xlsx-out", type=Path, default=DEFAULT_XLSX)
    args = parser.parse_args()

    plan = build_plan()
    workbook_result = write_workbook(plan, args.xlsx_out if args.xlsx_out.is_absolute() else ROOT / args.xlsx_out)
    errors = validate_plan(plan, workbook_result) if args.validate else []
    payload = {
        "schema": "veritas.wf75.deliverable_packager.v1",
        "generated_at_utc": utc_now(),
        "status": "ok" if not errors else "blocked",
        "plan_path": rel(args.plan_out if args.plan_out.is_absolute() else ROOT / args.plan_out),
        "markdown_path": rel(args.md_out if args.md_out.is_absolute() else ROOT / args.md_out),
        "workbook": workbook_result,
        "plan": plan,
        "validation": {"status": "ok" if not errors else "blocked", "errors": errors},
    }
    if args.write:
        plan_out = args.plan_out if args.plan_out.is_absolute() else ROOT / args.plan_out
        md_out = args.md_out if args.md_out.is_absolute() else ROOT / args.md_out
        out = args.out if args.out.is_absolute() else ROOT / args.out
        atomic_write_json(plan_out, plan)
        atomic_write_text(md_out, render_markdown(plan))
        atomic_write_json(out, payload)
    print(f"status={payload['status']} workbook={workbook_result.get('path')} errors={len(errors)}")
    return 0 if not errors else 2


if __name__ == "__main__":
    raise SystemExit(main())
