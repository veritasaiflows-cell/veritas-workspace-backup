#!/usr/bin/env python3
"""Build the WF75 anonymous scenario regression matrix.

This lane summarizes existing renderer/export regression proof only. It does
not re-run customer-output generation, use real customer data, deliver
externally, make legal/compliance/source-readiness claims, mutate finance
canon/portfolio state, or authorize account/execution activity.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.dont_write_bytecode = True

from market_data_utils import atomic_write_json, atomic_write_text, load_json_artifact  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
DEFAULT_RENDERER = TMP / "wf75-renderer-export-regression.json"
DEFAULT_TEMPLATE_LIBRARY = TMP / "wf75-scenario-template-library.json"
DEFAULT_OUT = TMP / "wf75-scenario-regression-matrix.json"
DEFAULT_MD = TMP / "wf75-scenario-regression-matrix.md"

SCHEMA = "veritas.wf75.scenario_regression_matrix.v1"

AUTHORITY_BOUNDARY = {
    "real_customer_data_allowed": False,
    "customer_data_retention_allowed": False,
    "external_delivery_allowed": False,
    "public_launch_allowed": False,
    "legal_or_compliance_ready": False,
    "source_licensing_assumed": False,
    "personalized_regulated_advice_allowed": False,
    "brokerage_or_account_connection_allowed": False,
    "paper_or_live_execution_allowed": False,
    "portfolio_or_canon_mutation_allowed": False,
    "owner_approval_inferred": False,
    "scenario_matrix_grants_launch_readiness": False,
    "scenario_matrix_grants_customer_delivery_authority": False,
    "scenario_matrix_grants_execution_authority": False,
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def absolutize(path: Path) -> Path:
    return path if path.is_absolute() else ROOT / path


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def load(path: Path) -> dict[str, Any]:
    payload = load_json_artifact(path)
    return payload if isinstance(payload, dict) else {}


def path_from_artifact(value: Any) -> Path | None:
    if not isinstance(value, str) or not value.strip():
        return None
    path = Path(value)
    return path if path.is_absolute() else ROOT / path


def artifact_probe(value: Any) -> dict[str, Any]:
    path = path_from_artifact(value)
    if path is None:
        return {"path": None, "exists": False}
    return {
        "path": rel(path),
        "exists": path.exists(),
        "size_bytes": path.stat().st_size if path.exists() else 0,
    }


def artifact_probes(artifacts: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {key: artifact_probe(value) for key, value in sorted(artifacts.items())}


def validation_artifact_summary(path_text: Any) -> dict[str, Any]:
    path = path_from_artifact(path_text)
    payload = load(path) if path else {}
    findings = [row for row in as_list(payload.get("findings")) if isinstance(row, dict)]
    return {
        "path": rel(path) if path else None,
        "exists": bool(path and path.exists()),
        "parseable_json": bool(payload),
        "status": payload.get("status"),
        "critical_count": int(payload.get("critical_count") or 0),
        "warning_count": int(payload.get("warning_count") or 0),
        "finding_codes": sorted(
            {
                str(row.get("code"))
                for row in findings
                if row.get("severity") == "critical" and row.get("code")
            }
        ),
        "authority_boundary": as_dict(payload.get("authority_boundary")),
    }


def expected_status(expected_validator_outcome: Any) -> str:
    if str(expected_validator_outcome or "").strip().lower() == "clean":
        return "ok"
    if str(expected_validator_outcome or "").strip().lower() in {"error", "fail", "failed"}:
        return "error"
    return str(expected_validator_outcome or "")


def template_index(template_library: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows = as_list(template_library.get("templates"))
    return {
        str(row.get("scenario_id")): row
        for row in rows
        if isinstance(row, dict) and row.get("scenario_id")
    }


def clean_scenario_matrix(renderer: dict[str, Any], template_library: dict[str, Any]) -> list[dict[str, Any]]:
    templates = template_index(template_library)
    rows: list[dict[str, Any]] = []
    for item in as_list(renderer.get("clean_results")):
        if not isinstance(item, dict):
            continue
        scenario_id = str(item.get("scenario_id") or "")
        template = templates.get(scenario_id, {})
        artifacts = as_dict(item.get("artifacts"))
        validation = validation_artifact_summary(artifacts.get("validation"))
        expected = expected_status(item.get("expected_validator_outcome"))
        actual = str(item.get("status") or "")
        critical_count = int(item.get("critical_count") if item.get("critical_count") is not None else validation.get("critical_count") or 0)
        warning_count = int(item.get("warning_count") if item.get("warning_count") is not None else validation.get("warning_count") or 0)
        rows.append(
            {
                "scenario_id": scenario_id,
                "anonymous": scenario_id.startswith("anon-"),
                "request_type": template.get("request_type"),
                "scenario": template.get("scenario"),
                "audience_segment": template.get("audience_segment"),
                "ticker_set": as_list(item.get("ticker_set")),
                "coverage_intent": template.get("coverage_intent"),
                "expected_validator_outcome": item.get("expected_validator_outcome"),
                "expected_status": expected,
                "actual_status": actual,
                "status_match": expected == actual,
                "critical_count": critical_count,
                "warning_count": warning_count,
                "artifact_paths": artifacts,
                "artifact_probes": artifact_probes(artifacts),
                "validation_artifact": validation,
            }
        )
    return sorted(rows, key=lambda row: str(row.get("scenario_id")))


def seeded_bad_matrix(renderer: dict[str, Any]) -> dict[str, Any]:
    seeded = as_dict(renderer.get("seeded_bad"))
    artifacts = as_dict(seeded.get("artifacts"))
    json_validation = validation_artifact_summary(artifacts.get("validation"))
    markdown_validation = validation_artifact_summary(artifacts.get("markdown_validation"))
    json_status = str(seeded.get("json_validation_status") or json_validation.get("status") or "")
    markdown_status = str(seeded.get("markdown_validation_status") or markdown_validation.get("status") or "")
    json_critical = int(json_validation.get("critical_count") or 0)
    markdown_critical = int(markdown_validation.get("critical_count") or 0)
    return {
        "scenario_id": seeded.get("scenario_id"),
        "expected_validator_outcome": seeded.get("expected_validator_outcome"),
        "expected_status": "error",
        "json_validation": {
            "expected_status": "error",
            "actual_status": json_status,
            "status_match": json_status == "error",
            "critical_count": json_critical,
            "warning_count": int(json_validation.get("warning_count") or 0),
            "finding_codes": json_validation.get("finding_codes", []),
            "artifact_path": artifacts.get("validation"),
            "artifact_probe": artifact_probe(artifacts.get("validation")),
            "source_summary": json_validation,
        },
        "markdown_validation": {
            "expected_status": "error",
            "actual_status": markdown_status,
            "status_match": markdown_status == "error",
            "critical_count": markdown_critical,
            "warning_count": int(markdown_validation.get("warning_count") or 0),
            "finding_codes": markdown_validation.get("finding_codes", []),
            "artifact_path": artifacts.get("markdown_validation"),
            "artifact_probe": artifact_probe(artifacts.get("markdown_validation")),
            "source_summary": markdown_validation,
        },
        "total_critical_count": json_critical + markdown_critical,
        "reported_total_critical_count": int(seeded.get("critical_count") or 0),
        "fail_closed": json_status == "error" and markdown_status == "error" and json_critical > 0 and markdown_critical > 0,
        "artifact_paths": artifacts,
        "artifact_probes": artifact_probes(artifacts),
    }


def authority_flags_closed(authority: dict[str, Any]) -> bool:
    return bool(authority) and all(value is False for value in authority.values())


def renderer_authority_closed(renderer: dict[str, Any]) -> bool:
    return authority_flags_closed(as_dict(renderer.get("authority_boundary")))


def validation_authority_closed(summary: dict[str, Any]) -> bool:
    authority = as_dict(summary.get("authority_boundary"))
    return not authority or authority_flags_closed(authority)


def build_matrix(renderer_path: Path = DEFAULT_RENDERER, template_library_path: Path = DEFAULT_TEMPLATE_LIBRARY) -> dict[str, Any]:
    renderer_path = absolutize(renderer_path)
    template_library_path = absolutize(template_library_path)
    renderer = load(renderer_path)
    template_library = load(template_library_path)
    clean_rows = clean_scenario_matrix(renderer, template_library)
    seeded_bad = seeded_bad_matrix(renderer)
    clean_failures = [
        row
        for row in clean_rows
        if row.get("expected_status") != "ok"
        or row.get("actual_status") != "ok"
        or int(row.get("critical_count") or 0) != 0
    ]
    warning_count = sum(int(row.get("warning_count") or 0) for row in clean_rows)
    payload: dict[str, Any] = {
        "schema": SCHEMA,
        "generated_at_utc": str(renderer.get("generated_at_utc") or utc_now()),
        "workflow": "WF75",
        "lane": "WF75::scenario_regression_matrix",
        "status": "ok",
        "posture": "internal_review_only_fail_closed_regression_summary",
        "source_artifacts": {
            "renderer_export_regression": rel(renderer_path),
            "scenario_template_library": rel(template_library_path),
        },
        "source_status": {
            "renderer_status": renderer.get("status"),
            "renderer_validation_status": as_dict(renderer.get("validation")).get("status"),
            "renderer_generated_at_utc": renderer.get("generated_at_utc"),
            "template_library_status": template_library.get("status"),
            "template_library_validation_status": as_dict(template_library.get("validation")).get("status"),
            "template_library_generated_at_utc": template_library.get("generated_at_utc"),
        },
        "summary": {
            "clean_scenario_count": len(clean_rows),
            "clean_passed_count": len(clean_rows) - len(clean_failures),
            "clean_failed_count": len(clean_failures),
            "clean_warning_count": warning_count,
            "seeded_bad_json_failed": as_dict(seeded_bad.get("json_validation")).get("actual_status") == "error",
            "seeded_bad_markdown_failed": as_dict(seeded_bad.get("markdown_validation")).get("actual_status") == "error",
            "seeded_bad_total_critical_count": seeded_bad.get("total_critical_count"),
            "authority_flags_closed": authority_flags_closed(AUTHORITY_BOUNDARY),
            "renderer_authority_flags_closed": renderer_authority_closed(renderer),
        },
        "clean_scenarios": clean_rows,
        "seeded_bad_fail_closed": seeded_bad,
        "authority_boundary": AUTHORITY_BOUNDARY,
    }
    payload["validation"] = validate_payload(payload)
    if payload["validation"]["status"] != "ok":
        payload["status"] = "blocked"
    return payload


def validate_payload(payload: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    if payload.get("schema") != SCHEMA:
        errors.append("schema_mismatch")

    source_status = as_dict(payload.get("source_status"))
    if source_status.get("renderer_status") != "ok":
        errors.append(f"renderer_status_not_ok:{source_status.get('renderer_status')}")
    if source_status.get("renderer_validation_status") != "ok":
        errors.append(f"renderer_validation_status_not_ok:{source_status.get('renderer_validation_status')}")
    if source_status.get("template_library_status") != "ok":
        errors.append(f"template_library_status_not_ok:{source_status.get('template_library_status')}")
    if source_status.get("template_library_validation_status") != "ok":
        errors.append(f"template_library_validation_status_not_ok:{source_status.get('template_library_validation_status')}")

    clean_rows = [row for row in as_list(payload.get("clean_scenarios")) if isinstance(row, dict)]
    if len(clean_rows) < 8:
        errors.append("clean_scenario_count_below_8")

    clean_failures = []
    for row in clean_rows:
        scenario_id = row.get("scenario_id")
        if row.get("anonymous") is not True:
            clean_failures.append(f"{scenario_id}:not_anonymous")
        if row.get("expected_status") != "ok":
            clean_failures.append(f"{scenario_id}:unexpected_clean_expectation")
        if row.get("actual_status") != "ok":
            clean_failures.append(f"{scenario_id}:actual_status_{row.get('actual_status')}")
        if int(row.get("critical_count") or 0) != 0:
            clean_failures.append(f"{scenario_id}:critical_count_{row.get('critical_count')}")
        if row.get("status_match") is not True:
            clean_failures.append(f"{scenario_id}:status_mismatch")
        artifacts = as_dict(row.get("artifact_probes"))
        missing = [key for key, probe in artifacts.items() if not as_dict(probe).get("exists")]
        if missing:
            clean_failures.append(f"{scenario_id}:missing_artifacts={','.join(sorted(missing))}")
        validation = as_dict(row.get("validation_artifact"))
        if validation.get("parseable_json") is False or validation.get("status") != "ok":
            clean_failures.append(f"{scenario_id}:validation_artifact_not_ok")
        if not validation_authority_closed(validation):
            clean_failures.append(f"{scenario_id}:validation_authority_not_closed")
    if clean_failures:
        errors.append("clean_scenario_failures:" + ";".join(clean_failures))

    summary = as_dict(payload.get("summary"))
    if int(summary.get("clean_failed_count") or 0) != 0:
        errors.append("summary_clean_failed_count_nonzero")

    seeded = as_dict(payload.get("seeded_bad_fail_closed"))
    seeded_json = as_dict(seeded.get("json_validation"))
    seeded_md = as_dict(seeded.get("markdown_validation"))
    if seeded.get("fail_closed") is not True:
        errors.append("seeded_bad_fail_closed_false")
    if seeded_json.get("actual_status") != "error" or int(seeded_json.get("critical_count") or 0) <= 0:
        errors.append("seeded_bad_json_failure_missing")
    if seeded_md.get("actual_status") != "error" or int(seeded_md.get("critical_count") or 0) <= 0:
        errors.append("seeded_bad_markdown_failure_missing")
    for label, item in (("json", seeded_json), ("markdown", seeded_md)):
        probe = as_dict(item.get("artifact_probe"))
        if not probe.get("exists"):
            errors.append(f"seeded_bad_{label}_validation_artifact_missing")
        source = as_dict(item.get("source_summary"))
        if not validation_authority_closed(source):
            errors.append(f"seeded_bad_{label}_validation_authority_not_closed")

    boundary = as_dict(payload.get("authority_boundary"))
    for key in AUTHORITY_BOUNDARY:
        if boundary.get(key) is not False:
            errors.append(f"authority_{key}_not_false")
    if summary.get("renderer_authority_flags_closed") is not True:
        errors.append("renderer_authority_flags_not_closed")
    if summary.get("authority_flags_closed") is not True:
        errors.append("matrix_authority_flags_not_closed")

    if warnings:
        warnings = sorted(set(warnings))
    return {"status": "ok" if not errors else "error", "errors": errors, "warnings": warnings}


def table_cell(value: Any) -> str:
    if isinstance(value, list):
        text = ", ".join(str(item) for item in value)
    else:
        text = "" if value is None else str(value)
    return text.replace("|", "/").replace("\n", " ")


def render_markdown(payload: dict[str, Any]) -> str:
    summary = as_dict(payload.get("summary"))
    seeded = as_dict(payload.get("seeded_bad_fail_closed"))
    seeded_json = as_dict(seeded.get("json_validation"))
    seeded_md = as_dict(seeded.get("markdown_validation"))
    lines = [
        "# WF75 Scenario Regression Matrix",
        "",
        f"- Generated: `{payload.get('generated_at_utc')}`",
        f"- Status: `{payload.get('status')}`",
        f"- Lane: `{payload.get('lane')}`",
        f"- Clean scenarios: `{summary.get('clean_passed_count')}/{summary.get('clean_scenario_count')}` passed",
        f"- Seeded-bad JSON: `{seeded_json.get('actual_status')}` with `{seeded_json.get('critical_count')}` critical findings",
        f"- Seeded-bad Markdown: `{seeded_md.get('actual_status')}` with `{seeded_md.get('critical_count')}` critical findings",
        f"- Authority flags closed: `{summary.get('authority_flags_closed')}`",
        "",
        "## Clean Scenario Matrix",
        "",
        "| Scenario | Expected | Actual | Critical | Warning | Artifacts |",
        "|---|---:|---:|---:|---:|---|",
    ]
    for row in as_list(payload.get("clean_scenarios")):
        if not isinstance(row, dict):
            continue
        artifacts = ", ".join(
            f"{key}:{as_dict(probe).get('path')}"
            for key, probe in as_dict(row.get("artifact_probes")).items()
        )
        lines.append(
            "| {scenario} | {expected} | {actual} | {critical} | {warning} | {artifacts} |".format(
                scenario=table_cell(row.get("scenario_id")),
                expected=table_cell(row.get("expected_status")),
                actual=table_cell(row.get("actual_status")),
                critical=table_cell(row.get("critical_count")),
                warning=table_cell(row.get("warning_count")),
                artifacts=table_cell(artifacts),
            )
        )
    lines.extend(
        [
            "",
            "## Seeded-Bad Fail-Closed Proof",
            "",
            "| Surface | Expected | Actual | Critical | Warning | Validation Artifact |",
            "|---|---:|---:|---:|---:|---|",
            "| JSON | {expected} | {actual} | {critical} | {warning} | {artifact} |".format(
                expected=table_cell(seeded_json.get("expected_status")),
                actual=table_cell(seeded_json.get("actual_status")),
                critical=table_cell(seeded_json.get("critical_count")),
                warning=table_cell(seeded_json.get("warning_count")),
                artifact=table_cell(seeded_json.get("artifact_path")),
            ),
            "| Markdown | {expected} | {actual} | {critical} | {warning} | {artifact} |".format(
                expected=table_cell(seeded_md.get("expected_status")),
                actual=table_cell(seeded_md.get("actual_status")),
                critical=table_cell(seeded_md.get("critical_count")),
                warning=table_cell(seeded_md.get("warning_count")),
                artifact=table_cell(seeded_md.get("artifact_path")),
            ),
            "",
            "## Authority Boundary",
            "",
        ]
    )
    for key, value in as_dict(payload.get("authority_boundary")).items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(
        [
            "",
            "Internal regression proof only. No customer data, external delivery, public launch, legal/compliance/source-licensing readiness, portfolio/canon mutation, account action, or paper/live execution authority is granted.",
            "",
        ]
    )
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the WF75 scenario regression matrix.")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--renderer", type=Path, default=DEFAULT_RENDERER)
    parser.add_argument("--template-library", type=Path, default=DEFAULT_TEMPLATE_LIBRARY)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--md-out", type=Path, default=DEFAULT_MD)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    payload = build_matrix(args.renderer, args.template_library)
    out = absolutize(args.out)
    md_out = absolutize(args.md_out)
    if args.write:
        atomic_write_json(out, payload)
        atomic_write_text(md_out, render_markdown(payload))
    validation = as_dict(payload.get("validation"))
    errors = as_list(validation.get("errors"))
    print(
        "status={status} clean={passed}/{total} seeded_bad={seeded} errors={errors}".format(
            status=payload.get("status"),
            passed=as_dict(payload.get("summary")).get("clean_passed_count"),
            total=as_dict(payload.get("summary")).get("clean_scenario_count"),
            seeded=as_dict(payload.get("seeded_bad_fail_closed")).get("fail_closed"),
            errors=len(errors),
        )
    )
    return 0 if (not args.validate or validation.get("status") == "ok") else 2


if __name__ == "__main__":
    raise SystemExit(main())
