"""Build the Phase 2 dashboard compatibility payload proof.

This artifact proves route coverage for the current Command Center DATA
contract using compact panels plus explicit legacy refs. It does not produce
a drop-in replacement for `dashboard-data.json`.
"""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"

ADAPTER = TMP / "dashboard-presentation-adapter.json"
THIN_PREVIEW = TMP / "dashboard-data-thin-preview.json"
V2_READER = TMP / "dashboard-v2-reader-migration.json"
LEGACY_DASHBOARD = TMP / "dashboard-data.json"
OUT = TMP / "dashboard-compatibility-payload.json"
VALIDATION = TMP / "dashboard-compatibility-payload-validation.json"
JS_DIR = ROOT / "scripts" / "dashboard-js"

DATA_ACCESS_RE = re.compile(r"\bDATA(?:\.([A-Za-z_$][\w$]*)|\[['\"]([^'\"]+)['\"]\])")
ROW_FIELD_RE = re.compile(r"\b(?:r|t|p|item|queue|daily|intel|techCtx|deployCtx|sum|m|c|b|rt)\.([A-Za-z_$][\w$]*)")
LEGACY_STATE_FIELDS = {
    "action_state",
    "actionState",
    "workflow_state",
    "machine_state",
    "surface_state",
    "base_surface_state",
}
CANONICAL_STATE_FIELDS = {"deployment_contract", "deployment_status"}


def relpath(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def classify_value_requirement(value: Any) -> str:
    if isinstance(value, list):
        return "table_rows_required"
    if isinstance(value, dict):
        if isinstance(value.get("records"), list):
            return "nested_records_required"
        if isinstance(value.get("packets"), list):
            return "nested_packets_required"
        return "object_fields_required"
    return "metadata_value_required"


def sample_records(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, list):
        return [row for row in value if isinstance(row, dict)][:10]
    if isinstance(value, dict):
        for key in ("records", "packets", "rows", "capital_recommendations", "escalations"):
            rows = value.get(key)
            if isinstance(rows, list):
                return [row for row in rows if isinstance(row, dict)][:10]
    return []


def state_contract_preference(section: str, value: Any, row_fields: set[str]) -> dict[str, Any]:
    records = sample_records(value)
    canonical_fields_present = sorted(
        field
        for field in CANONICAL_STATE_FIELDS
        if any(field in record for record in records)
    )
    legacy_fields_present = sorted(
        field
        for field in LEGACY_STATE_FIELDS
        if any(field in record for record in records) or field in row_fields
    )
    reader_uses_legacy_state = sorted(field for field in LEGACY_STATE_FIELDS if field in row_fields)
    canonical_available = bool(canonical_fields_present)
    if canonical_available and reader_uses_legacy_state:
        preference = "canonical_available_reader_should_migrate"
    elif canonical_available:
        preference = "canonical_available"
    elif legacy_fields_present:
        preference = "legacy_or_source_state_only"
    else:
        preference = "not_state_related"
    return {
        "section": section,
        "preference": preference,
        "canonical_fields_present": canonical_fields_present,
        "legacy_fields_present": legacy_fields_present,
        "reader_uses_legacy_state_fields": reader_uses_legacy_state,
    }


def scan_js_dependencies(legacy_payload: dict[str, Any]) -> dict[str, Any]:
    by_section: dict[str, dict[str, Any]] = {}
    files_scanned = 0
    files_with_data_reads = 0
    if not JS_DIR.exists():
        return {
            "status": "blocked",
            "files_scanned": 0,
            "files_with_data_reads": 0,
            "section_count": 0,
            "row_table_dependency_count": 0,
            "canonical_migration_needed_count": 0,
            "sections": [],
        }

    for path in sorted(JS_DIR.glob("*.js")):
        files_scanned += 1
        text = path.read_text(encoding="utf-8", errors="replace")
        sections_in_file = {match.group(1) or match.group(2) for match in DATA_ACCESS_RE.finditer(text)}
        sections_in_file = {section for section in sections_in_file if section}
        if sections_in_file:
            files_with_data_reads += 1
        row_fields = {match.group(1) for match in ROW_FIELD_RE.finditer(text)}
        for section in sorted(sections_in_file):
            row = by_section.setdefault(
                section,
                {
                    "section": section,
                    "files": [],
                    "value_requirement": classify_value_requirement(legacy_payload.get(section)),
                    "row_field_examples": set(),
                },
            )
            row["files"].append(relpath(path))
            row["row_field_examples"].update(row_fields)

    sections: list[dict[str, Any]] = []
    for section, row in sorted(by_section.items()):
        fields = sorted(str(field) for field in row["row_field_examples"] if field)[:30]
        state_preference = state_contract_preference(section, legacy_payload.get(section), set(fields))
        value_requirement = str(row["value_requirement"])
        sections.append(
            {
                "section": section,
                "files": row["files"],
                "value_requirement": value_requirement,
                "requires_concrete_rows_or_objects": value_requirement
                in {"table_rows_required", "nested_records_required", "nested_packets_required", "object_fields_required"},
                "row_field_examples": fields,
                "deployment_contract_preference": state_preference,
            }
        )

    return {
        "status": "ok",
        "files_scanned": files_scanned,
        "files_with_data_reads": files_with_data_reads,
        "section_count": len(sections),
        "row_table_dependency_count": sum(1 for row in sections if row["requires_concrete_rows_or_objects"]),
        "canonical_migration_needed_count": sum(
            1
            for row in sections
            if as_dict(row.get("deployment_contract_preference")).get("preference") == "canonical_available_reader_should_migrate"
        ),
        "sections": sections,
    }


def build_payload() -> dict[str, Any]:
    adapter = as_dict(read_json(ADAPTER)) if ADAPTER.exists() else {}
    thin_preview = as_dict(read_json(THIN_PREVIEW)) if THIN_PREVIEW.exists() else {}
    v2_reader = as_dict(read_json(V2_READER)) if V2_READER.exists() else {}
    legacy_payload = as_dict(read_json(LEGACY_DASHBOARD)) if LEGACY_DASHBOARD.exists() else {}
    js_dependencies = scan_js_dependencies(legacy_payload)
    js_by_section = {as_dict(row).get("section"): as_dict(row) for row in as_list(js_dependencies.get("sections"))}
    sections: list[dict[str, Any]] = []
    for route in as_list(adapter.get("routes")):
        route = as_dict(route)
        section = route.get("section")
        dependency = as_dict(js_by_section.get(section))
        sections.append(
            {
                "section": section,
                "route_kind": route.get("route_kind"),
                "compact_panel_id": route.get("compact_panel_id"),
                "compact_ref": route.get("compact_ref"),
                "legacy_source_ref": route.get("source_ref"),
                "proof_ref": route.get("proof_ref"),
                "drop_in_value_included": False,
                "current_js_dependency": {
                    "files": dependency.get("files", []),
                    "value_requirement": dependency.get("value_requirement", "not_read_by_current_js"),
                    "requires_concrete_rows_or_objects": dependency.get("requires_concrete_rows_or_objects", False),
                    "row_field_examples": dependency.get("row_field_examples", []),
                    "deployment_contract_preference": dependency.get("deployment_contract_preference", {}),
                },
            }
        )
    route_counts = as_dict(as_dict(adapter.get("summary")).get("route_counts"))
    row_dependency_sections = [
        row["section"]
        for row in sections
        if as_dict(row.get("current_js_dependency")).get("requires_concrete_rows_or_objects") is True
    ]
    canonical_reader_debt = [
        {
            "section": row["section"],
            "preference": as_dict(as_dict(row.get("current_js_dependency")).get("deployment_contract_preference")).get("preference"),
            "files": as_dict(row.get("current_js_dependency")).get("files", []),
            "reader_uses_legacy_state_fields": as_dict(
                as_dict(row.get("current_js_dependency")).get("deployment_contract_preference")
            ).get("reader_uses_legacy_state_fields", []),
        }
        for row in sections
        if as_dict(as_dict(row.get("current_js_dependency")).get("deployment_contract_preference")).get("preference")
        == "canonical_available_reader_should_migrate"
    ]
    return {
        "schema_version": "dashboard_compatibility_payload.v1",
        "generated_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "status": "coverage_ready_not_drop_in",
        "source_payload_embedded": False,
        "drop_in_replacement_ready": False,
        "authority": {
            "review_only": True,
            "dashboard_data_replaced": False,
            "legacy_payload_embedded": False,
            "proof_deletion_allowed": False,
            "archive_or_cleanup_allowed": False,
            "canonical_mutation_allowed": False,
            "portfolio_mutation_allowed": False,
            "sql_canon_promotion_allowed": False,
            "customer_or_public_output_allowed": False,
            "paper_or_live_execution_allowed": False,
            "brokerage_or_account_action_allowed": False,
            "owner_approval_inferred": False,
        },
        "summary": {
            "required_section_count": len(sections),
            "route_counts": route_counts,
            "compact_or_metadata_coverage_count": sum(1 for row in sections if row["route_kind"] in {"compact_panel_primary_with_legacy_passthrough", "adapter_metadata"}),
            "legacy_only_route_count": route_counts.get("legacy_passthrough_required", 0),
            "v2_migrated_panel_count": as_dict(v2_reader.get("summary")).get("migrated_panel_count"),
            "thin_preview_status": thin_preview.get("status"),
            "current_js_drop_in_ready": False,
            "current_js_files_with_data_reads": js_dependencies.get("files_with_data_reads"),
            "current_js_row_table_dependency_count": len(row_dependency_sections),
            "current_js_row_table_dependency_sections": row_dependency_sections,
            "canonical_reader_debt_count": len(canonical_reader_debt),
            "replacement_blocker": "Current JS still reads concrete DATA row/object sections directly; compact shell is reader-ready, but the legacy JS contract is not satisfied by route refs alone.",
        },
        "source_artifacts": {
            "adapter": relpath(ADAPTER),
            "thin_preview": relpath(THIN_PREVIEW),
            "v2_reader_migration": relpath(V2_READER),
            "legacy_dashboard": relpath(LEGACY_DASHBOARD),
        },
        "current_js_dependency_summary": js_dependencies,
        "deployment_contract_reader_debt": canonical_reader_debt,
        "sections": sections,
        "next_gate": {
            "required_before_drop_in_replacement": [
                "Migrate JS readers panel-by-panel to compact view-model sections.",
                "Retain legacy payload only for explicit drilldown/detail loads.",
                "Run dashboard acceptance against the migrated reader path.",
            ],
        },
    }


def validate(payload: dict[str, Any]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for path in (ADAPTER, THIN_PREVIEW, V2_READER, LEGACY_DASHBOARD):
        if not path.exists():
            findings.append({"severity": "critical", "issue": "missing_required_artifact", "path": relpath(path)})
    authority = as_dict(payload.get("authority"))
    if authority.get("review_only") is not True:
        findings.append({"severity": "critical", "issue": "review_only_not_true"})
    for key, value in authority.items():
        if key.endswith("_allowed") or key.endswith("_embedded") or key.endswith("_replaced") or key.endswith("_inferred"):
            if value is not False:
                findings.append({"severity": "critical", "issue": "authority_flag_not_false", "flag": key, "value": value})
    if payload.get("source_payload_embedded") is not False:
        findings.append({"severity": "critical", "issue": "source_payload_embedded"})
    summary = as_dict(payload.get("summary"))
    if summary.get("required_section_count", 0) < 30:
        findings.append({"severity": "critical", "issue": "required_section_count_low", "count": summary.get("required_section_count")})
    if summary.get("legacy_only_route_count", 0) != 0:
        findings.append({"severity": "critical", "issue": "legacy_only_routes_remain", "count": summary.get("legacy_only_route_count")})
    if payload.get("drop_in_replacement_ready") is not False:
        findings.append({"severity": "critical", "issue": "drop_in_replacement_claimed"})
    return findings


def write_outputs() -> tuple[dict[str, Any], dict[str, Any]]:
    payload = build_payload()
    findings = validate(payload)
    validation = {
        "schema_version": "dashboard_compatibility_payload_validation.v1",
        "status": "ok" if not any(f.get("severity") == "critical" for f in findings) else "blocked",
        "critical": sum(1 for f in findings if f.get("severity") == "critical"),
        "warning": sum(1 for f in findings if f.get("severity") == "warning"),
        "output": relpath(OUT),
        "drop_in_replacement_ready": payload.get("drop_in_replacement_ready"),
        "findings": findings,
    }
    payload["validation"] = {
        "status": validation["status"],
        "critical": validation["critical"],
        "warning": validation["warning"],
    }
    OUT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    VALIDATION.write_text(json.dumps(validation, indent=2) + "\n", encoding="utf-8")
    return payload, validation


def main() -> int:
    parser = argparse.ArgumentParser(description="Build dashboard compatibility payload proof.")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    args = parser.parse_args()
    payload = build_payload()
    findings = validate(payload)
    validation = {"critical": sum(1 for f in findings if f.get("severity") == "critical"), "status": "ok" if not any(f.get("severity") == "critical" for f in findings) else "blocked"}
    if args.write:
        payload, validation = write_outputs()
        print(f"wrote {relpath(OUT)}")
        print(f"wrote {relpath(VALIDATION)}")
    print(f"dashboard_compatibility_payload: {validation['status']} ({validation['critical']} critical)")
    return 1 if args.validate and validation["critical"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
