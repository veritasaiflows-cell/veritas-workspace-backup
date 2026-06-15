#!/usr/bin/env python3
"""Build the WF75 artifact-only PM handoff.

This handoff is a compact PM/operator packet fed only by validated artifacts.
It does not deliver externally, store real customer data, mutate finance canon
or portfolio state, import tickers, infer approval, or grant execution authority.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, atomic_write_text, load_json_artifact

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
DEFAULT_JSON = TMP / "wf75-artifact-only-pm-handoff.json"
DEFAULT_MD = DEFAULT_JSON.with_suffix(".md")

WF77_BRIDGE = TMP / "wf77-price-freshness-bridge.json"
WF77_SUPPLEMENTAL = TMP / "wf77-supplemental-price-evidence.json"
RENDERER_REGRESSION = TMP / "wf75-renderer-export-regression.json"
SCENARIO_LIBRARY = TMP / "wf75-scenario-template-library.json"
SERVICE_STATE = TMP / "wf75-service-state-current.json"
OPERATOR_QUEUE = TMP / "wf75-operator-queue.json"
OPERATOR_CONSOLE = TMP / "wf75-operator-console.json"
MOVEMENT = TMP / "wf75-automation-movement.json"
PM_WEEKLY_UPDATE = TMP / "wf75-pm-weekly-update.json"
CONTROL_PLANE = TMP / "wf75-service-state-sqlite.json"
HARNESS_SCORECARD = TMP / "veritas-harness-scorecard.json"
MACRO_EVENT_CALENDAR = TMP / "macro-event-calendar.json"

SCHEMA = "veritas.wf75.artifact_only_pm_handoff.v1"

AUTHORITY_FALSE_KEYS = [
    "public_launch_ready",
    "real_customer_data_allowed",
    "customer_data_retention_allowed",
    "external_delivery_allowed",
    "legal_or_compliance_ready",
    "source_licensing_assumed",
    "personalized_regulated_advice_allowed",
    "brokerage_or_account_connection_allowed",
    "paper_or_live_execution_allowed",
    "portfolio_or_canon_mutation_allowed",
    "sql_or_ticker_import_allowed",
    "owner_approval_inferred",
]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def load(path: Path) -> dict[str, Any]:
    return as_dict(load_json_artifact(path))


def artifact_probe(key: str, path: Path, required: bool = True) -> dict[str, Any]:
    payload = load_json_artifact(path)
    probe: dict[str, Any] = {
        "key": key,
        "path": rel(path),
        "required": required,
        "exists": path.exists(),
        "parseable_json": isinstance(payload, dict),
    }
    if isinstance(payload, dict):
        probe["schema"] = payload.get("schema") or payload.get("schema_version")
        probe["status"] = payload.get("status")
        validation = payload.get("validation")
        if isinstance(validation, dict):
            probe["validation_status"] = validation.get("status")
    return probe


def renderer_summary(renderer: dict[str, Any]) -> dict[str, Any]:
    seeded_bad = as_dict(renderer.get("seeded_bad"))
    clean_total = renderer.get("clean_scenario_count")
    clean_failed = renderer.get("clean_failed_count")
    return {
        "status": renderer.get("status"),
        "clean_scenarios_passed": None if clean_total is None or clean_failed is None else int(clean_total) - int(clean_failed),
        "clean_scenarios_total": clean_total,
        "clean_failed_count": clean_failed,
        "seeded_bad_json_validation_status": seeded_bad.get("json_validation_status"),
        "seeded_bad_markdown_validation_status": seeded_bad.get("markdown_validation_status"),
        "seeded_bad_critical_count": seeded_bad.get("critical_count"),
    }


def scenario_summary(library: dict[str, Any]) -> dict[str, Any]:
    scenarios = as_list(library.get("templates"))
    return {
        "status": library.get("status"),
        "scenario_count": library.get("template_count") if library.get("template_count") is not None else len(scenarios),
        "scenario_ids": [item.get("scenario_id") for item in scenarios if isinstance(item, dict)],
    }


def build_handoff() -> dict[str, Any]:
    wf77 = load(WF77_BRIDGE)
    renderer = load(RENDERER_REGRESSION)
    scenarios = load(SCENARIO_LIBRARY)
    service_state = load(SERVICE_STATE)
    queue = load(OPERATOR_QUEUE)
    movement = load(MOVEMENT)
    operator_console = load(OPERATOR_CONSOLE)
    pm = load(PM_WEEKLY_UPDATE)
    control_plane = load(CONTROL_PLANE)
    harness = load(HARNESS_SCORECARD)
    macro_calendar = load(MACRO_EVENT_CALENDAR)

    artifacts = [
        artifact_probe("wf77_price_freshness_bridge", WF77_BRIDGE),
        artifact_probe("wf77_supplemental_price_evidence", WF77_SUPPLEMENTAL),
        artifact_probe("renderer_export_regression", RENDERER_REGRESSION),
        artifact_probe("scenario_template_library", SCENARIO_LIBRARY),
        artifact_probe("service_state", SERVICE_STATE),
        artifact_probe("operator_queue", OPERATOR_QUEUE),
        artifact_probe("operator_console", OPERATOR_CONSOLE),
        artifact_probe("automation_movement", MOVEMENT),
        artifact_probe("pm_weekly_update", PM_WEEKLY_UPDATE),
        artifact_probe("sqlite_wal_control_plane", CONTROL_PLANE),
        artifact_probe("veritas_harness_scorecard", HARNESS_SCORECARD),
        artifact_probe("macro_event_calendar", MACRO_EVENT_CALENDAR),
    ]

    current_queue = as_list(queue.get("current_queue"))
    queue_item = as_dict(current_queue[0] if current_queue else {})
    wf77_summary = as_dict(wf77.get("summary"))
    validation_status = {
        "wf77_bridge": wf77.get("status"),
        "renderer_regression": renderer.get("status"),
        "scenario_library": scenarios.get("status"),
        "service_state": as_dict(service_state.get("validation")).get("status"),
        "operator_queue": as_dict(queue.get("validation")).get("status"),
        "operator_console": as_dict(operator_console.get("validation")).get("status"),
        "automation_movement": as_dict(movement.get("validation")).get("status"),
        "pm_weekly_update": pm.get("status"),
        "sqlite_wal_control_plane": as_dict(control_plane.get("validation")).get("status"),
        "veritas_harness_scorecard": harness.get("status"),
        "macro_event_calendar": as_dict(macro_calendar.get("validation")).get("status", macro_calendar.get("status")),
    }

    handoff = {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "workflow": "WF75",
        "status": "ready_for_internal_artifact_only_pm_handoff",
        "headline": "WF75 now has artifact-only PM handoff proof fed by price freshness, renderer regression, scenario templates, service state, operator queue, weekly PM update, and SQLite WAL control-plane state.",
        "artifact_inputs": artifacts,
        "validation_status": validation_status,
        "current_operator_queue": {
            "status": queue.get("status"),
            "queue_count": len(current_queue),
            "first_queue_id": queue_item.get("queue_id"),
            "first_queue_status": queue_item.get("status"),
            "priority": queue_item.get("priority"),
            "next_action": queue_item.get("next_action"),
        },
        "wf77_price_evidence": {
            "status": wf77.get("status"),
            "valid_price_row_count": wf77_summary.get("valid_price_row_count"),
            "row_count": wf77_summary.get("row_count"),
            "missing_price_rows": as_list(wf77_summary.get("missing_price_rows")),
            "excluded_price_rows": as_list(wf77_summary.get("excluded_price_rows")),
            "supplemental_public_price_rows": as_list(wf77_summary.get("supplemental_public_price_rows")),
            "supplemental_public_price_row_count": wf77_summary.get("supplemental_public_price_row_count"),
        },
        "renderer_export_regression": renderer_summary(renderer),
        "scenario_template_library": scenario_summary(scenarios),
        "sqlite_wal_control_plane": {
            "status": control_plane.get("status"),
            "db_path": control_plane.get("db_path"),
            "journal_mode": as_dict(as_dict(control_plane.get("validation")).get("pragmas")).get("journal_mode"),
            "busy_timeout_ms": as_dict(as_dict(control_plane.get("validation")).get("pragmas")).get("busy_timeout_ms"),
            "table_counts": as_dict(as_dict(control_plane.get("validation")).get("table_counts")),
            "claim_rows": as_list(as_dict(control_plane.get("validation")).get("claim_rows")),
        },
        "pm_surface": {
            "weekly_update_status": pm.get("status"),
            "headline": pm.get("headline"),
            "next_safe_action": pm.get("next_safe_action"),
        },
        "harness_scorecard": {
            "status": harness.get("status"),
            "source": rel(HARNESS_SCORECARD),
            "summary": as_dict(harness.get("summary")),
            "open_readiness_gaps": as_list(harness.get("open_readiness_gaps")),
        },
        "macro_event_calendar": {
            "status": macro_calendar.get("status"),
            "source": rel(MACRO_EVENT_CALENDAR),
            "summary": as_dict(macro_calendar.get("summary")),
            "operator_followup_contract": as_dict(macro_calendar.get("operator_followup_contract")),
        },
        "operator_consumption_contract": {
            "read_order": [
                rel(CONTROL_PLANE),
                rel(SERVICE_STATE),
                rel(OPERATOR_QUEUE),
                rel(OPERATOR_CONSOLE),
                rel(MACRO_EVENT_CALENDAR),
                rel(WF77_BRIDGE),
                rel(RENDERER_REGRESSION),
                rel(SCENARIO_LIBRARY),
                rel(PM_WEEKLY_UPDATE),
            ],
            "artifact_only": True,
            "main_session_final_integrator": True,
            "helper_outputs_untrusted_until_main_verifies": True,
            "cron_may_refresh_only_after_job_card": True,
        },
        "authority_boundary": {key: False for key in AUTHORITY_FALSE_KEYS},
    }
    handoff["validation"] = validate(handoff)
    if handoff["validation"]["status"] != "ok":
        handoff["status"] = "blocked"
    return handoff


def validate(handoff: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    if handoff.get("schema") != SCHEMA:
        errors.append("schema mismatch")
    for artifact in as_list(handoff.get("artifact_inputs")):
        if not isinstance(artifact, dict):
            errors.append("artifact input must be object")
            continue
        if artifact.get("required") and not artifact.get("exists"):
            errors.append(f"required artifact missing: {artifact.get('path')}")
        if artifact.get("exists") and not artifact.get("parseable_json"):
            errors.append(f"artifact is not parseable JSON: {artifact.get('path')}")
    validation = as_dict(handoff.get("validation_status"))
    expected_ok = {
        "renderer_regression": "ok",
        "scenario_library": "ok",
        "service_state": "ok",
        "operator_queue": "ok",
        "operator_console": "ok",
        "automation_movement": "ok",
        "pm_weekly_update": "ready_for_internal_pm_review",
        "sqlite_wal_control_plane": "ok",
        "macro_event_calendar": "ok",
    }
    for key, expected in expected_ok.items():
        if validation.get(key) != expected:
            errors.append(f"{key} expected {expected}, found {validation.get(key)}")
    if validation.get("wf77_bridge") not in {"ok", "warning"}:
        errors.append(f"wf77 bridge not usable: {validation.get('wf77_bridge')}")
    if validation.get("veritas_harness_scorecard") not in {"ok", "warning"}:
        warnings.append(f"veritas harness scorecard not currently usable: {validation.get('veritas_harness_scorecard')}")
    price = as_dict(handoff.get("wf77_price_evidence"))
    if price.get("missing_price_rows") or price.get("excluded_price_rows"):
        errors.append("wf77 price evidence still has missing/excluded rows")
    if price.get("valid_price_row_count") != price.get("row_count"):
        errors.append("wf77 valid price row count does not match row count")
    renderer = as_dict(handoff.get("renderer_export_regression"))
    if renderer.get("clean_scenarios_passed") != renderer.get("clean_scenarios_total"):
        errors.append("renderer clean scenario coverage incomplete")
    scenarios = as_dict(handoff.get("scenario_template_library"))
    if int(scenarios.get("scenario_count") or 0) < 3:
        errors.append("scenario library must contain at least three anonymous scenarios")
    sqlite_state = as_dict(handoff.get("sqlite_wal_control_plane"))
    if str(sqlite_state.get("journal_mode")).lower() != "wal":
        errors.append("SQLite control plane is not in WAL mode")
    claim_statuses = [row.get("claim_status") for row in as_list(sqlite_state.get("claim_rows")) if isinstance(row, dict)]
    if "claimed" not in claim_statuses or "already_claimed" not in claim_statuses:
        errors.append("SQLite control plane did not prove one-worker claim exclusion")
    boundary = as_dict(handoff.get("authority_boundary"))
    for key in AUTHORITY_FALSE_KEYS:
        if boundary.get(key) is not False:
            errors.append(f"authority flag must be false: {key}")
    if warnings:
        warnings = sorted(set(warnings))
    return {"status": "ok" if not errors else "error", "errors": errors, "warnings": warnings}


def render_markdown(handoff: dict[str, Any]) -> str:
    queue = as_dict(handoff.get("current_operator_queue"))
    price = as_dict(handoff.get("wf77_price_evidence"))
    sqlite_state = as_dict(handoff.get("sqlite_wal_control_plane"))
    lines = [
        "# WF75 Artifact-Only PM Handoff",
        "",
        f"- Generated: `{handoff.get('generated_at_utc')}`",
        f"- Status: `{handoff.get('status')}`",
        f"- Workflow: `{handoff.get('workflow')}`",
        "",
        "## Verdict",
        "",
        str(handoff.get("headline")),
        "",
        "## Operator Queue",
        "",
        f"- Queue status: `{queue.get('status')}`",
        f"- First item: `{queue.get('first_queue_id')}` / `{queue.get('first_queue_status')}` / priority `{queue.get('priority')}`",
        f"- Next action: {queue.get('next_action')}",
        "",
        "## Evidence",
        "",
        f"- WF77 price rows: `{price.get('valid_price_row_count')}/{price.get('row_count')}`",
        f"- Supplemental rows: `{', '.join(price.get('supplemental_public_price_rows') or [])}`",
        f"- Renderer regression: `{as_dict(handoff.get('renderer_export_regression')).get('status')}`",
        f"- Scenario library count: `{as_dict(handoff.get('scenario_template_library')).get('scenario_count')}`",
        f"- SQLite WAL DB: `{sqlite_state.get('db_path')}` / journal `{sqlite_state.get('journal_mode')}`",
        f"- Harness scorecard: `{as_dict(handoff.get('harness_scorecard')).get('status')}`",
        "",
        "## Validation",
        "",
        f"- Validation status: `{as_dict(handoff.get('validation')).get('status')}`",
        f"- Errors: `{len(as_list(as_dict(handoff.get('validation')).get('errors')))}`",
        "",
        "## Boundary",
        "",
        "Internal artifact-only PM/operator handoff. No public launch, real customer data, external delivery, legal/compliance/source-licensing claim, portfolio/canon mutation, SQL/ticker import, paper/live/account action, or owner approval inference.",
        "",
    ]
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the WF75 artifact-only PM handoff.")
    parser.add_argument("--write", action="store_true", help="Write JSON handoff artifact.")
    parser.add_argument("--write-md", action="store_true", help="Also write the optional human-readable Markdown digest.")
    parser.add_argument("--validate", action="store_true", help="Fail if the handoff is not clean.")
    parser.add_argument("--json-out", default=str(DEFAULT_JSON), help="JSON output path.")
    parser.add_argument("--md-out", default=str(DEFAULT_MD), help="Markdown output path.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    handoff = build_handoff()
    json_out = Path(args.json_out)
    if not json_out.is_absolute():
        json_out = ROOT / json_out
    if args.write:
        atomic_write_json(json_out, handoff)
    if args.write_md:
        md_out = Path(args.md_out)
        if not md_out.is_absolute():
            md_out = ROOT / md_out
        atomic_write_text(md_out, render_markdown(handoff))
    print(json.dumps(handoff, indent=2, sort_keys=True))
    if args.validate and handoff.get("status") != "ready_for_internal_artifact_only_pm_handoff":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
