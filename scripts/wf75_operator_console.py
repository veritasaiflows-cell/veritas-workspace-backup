#!/usr/bin/env python3
"""Build the WF75 local operator console and control cockpit.

This is an internal review surface over anonymous service-state artifacts and
the SQLite WAL control-plane DB. It is not a customer UI, not external delivery,
not approval, not finance canon, and not trade/account authority.
"""
from __future__ import annotations

import argparse
import html
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, atomic_write_text, load_json_artifact

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"

DEFAULT_JSON = TMP / "wf75-operator-console.json"
DEFAULT_HTML = TMP / "wf75-operator-console.html"
DEFAULT_MD = DEFAULT_JSON.with_suffix(".md")
DEFAULT_DB = TMP / "wf75-service-state.sqlite"

SERVICE_STATE = TMP / "wf75-service-state-current.json"
SQLITE_SUMMARY = TMP / "wf75-service-state-sqlite.json"
OPERATOR_QUEUE = TMP / "wf75-operator-queue.json"
ARTIFACT_HANDOFF = TMP / "wf75-artifact-only-pm-handoff.json"
PM_UPDATE = TMP / "wf75-pm-weekly-update.json"
PM_BRIEF = TMP / "wf75-pm-readiness-brief.json"
RENDERER_REGRESSION = TMP / "wf75-renderer-export-regression.json"
SCENARIO_LIBRARY = TMP / "wf75-scenario-template-library.json"
WF77_BRIDGE = TMP / "wf77-price-freshness-bridge.json"
CRON_PLAN = TMP / "wf75-cron-automation-authority-plan.json"
RECOMMENDATION_LEDGER = TMP / "recommendation-outcome-ledger-current.json"
HARNESS_SCORECARD = TMP / "veritas-harness-scorecard.json"
MACRO_EVENT_CALENDAR = TMP / "macro-event-calendar.json"

SCHEMA = "veritas.wf75.operator_console.v1"

AUTHORITY_FALSE_KEYS = [
    "public_launch_allowed",
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


def esc(value: Any) -> str:
    return html.escape("" if value is None else str(value))


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def load(path: Path) -> dict[str, Any]:
    return as_dict(load_json_artifact(path))


def status_class(value: Any) -> str:
    text = str(value or "").lower()
    if text in {"ok", "ready", "control_plane_ready", "handoff_ready", "ready_for_internal_pm_review", "ready_for_internal_artifact_only_pm_handoff", "installed_or_present"}:
        return "good"
    if "blocked" in text or "error" in text or "missing" in text or "failed" in text:
        return "bad"
    if "warning" in text or "review" in text or "needed" in text:
        return "warn"
    return "neutral"


def badge(value: Any) -> str:
    display = "unknown" if value in (None, "") else str(value)
    return f"<span class='badge {status_class(display)}'>{esc(display)}</span>"


def connect_readonly(db_path: Path) -> sqlite3.Connection:
    if not db_path.exists():
        raise FileNotFoundError(db_path)
    uri = f"file:{db_path.as_posix()}?mode=ro"
    conn = sqlite3.connect(uri, uri=True, timeout=5.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def rows(conn: sqlite3.Connection, sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    return [dict(row) for row in conn.execute(sql, params).fetchall()]


def read_db_state(db_path: Path) -> dict[str, Any]:
    if not db_path.exists():
        return {"status": "missing", "db_path": rel(db_path), "errors": [f"missing DB: {rel(db_path)}"]}
    conn = connect_readonly(db_path)
    try:
        return {
            "status": "ok",
            "db_path": rel(db_path),
            "pragmas": {
                "journal_mode": conn.execute("PRAGMA journal_mode").fetchone()[0],
                "busy_timeout_ms": conn.execute("PRAGMA busy_timeout").fetchone()[0],
                "foreign_keys": conn.execute("PRAGMA foreign_keys").fetchone()[0],
            },
            "service_requests": rows(
                conn,
                """
                SELECT request_id, workflow, service_run_id, scenario, request_type, status, priority,
                       anonymous_service_request, real_customer_data_present, external_delivery_allowed,
                       updated_at_utc
                FROM service_requests
                ORDER BY updated_at_utc DESC
                """,
            ),
            "queue_items": rows(
                conn,
                """
                SELECT queue_id, request_id, service_run_id, workflow, status, priority, owner,
                       next_action, inline_execution_allowed, external_delivery_allowed,
                       customer_data_use_allowed, claimed_by, claimed_at_utc, claim_count, updated_at_utc
                FROM queue_items
                ORDER BY priority, updated_at_utc DESC
                """,
            ),
            "artifact_refs": rows(
                conn,
                """
                SELECT artifact_key, path, required, exists_flag, parseable_json, status,
                       validation_status, updated_at_utc
                FROM artifact_refs
                ORDER BY required DESC, artifact_key
                """,
            ),
            "claim_log": rows(
                conn,
                "SELECT worker_id, queue_id, claim_status, claimed_at_utc FROM claim_log ORDER BY id",
            ),
            "events": rows(
                conn,
                "SELECT event_at_utc, event_type, object_type, object_id FROM events ORDER BY id DESC LIMIT 10",
            ),
            "errors": [],
        }
    finally:
        conn.close()


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


def source_artifacts() -> list[dict[str, Any]]:
    return [
        artifact_probe("service_state", SERVICE_STATE),
        artifact_probe("sqlite_summary", SQLITE_SUMMARY),
        artifact_probe("operator_queue", OPERATOR_QUEUE),
        artifact_probe("artifact_handoff", ARTIFACT_HANDOFF),
        artifact_probe("pm_weekly_update", PM_UPDATE),
        artifact_probe("pm_readiness_brief", PM_BRIEF),
        artifact_probe("renderer_regression", RENDERER_REGRESSION),
        artifact_probe("scenario_library", SCENARIO_LIBRARY),
        artifact_probe("wf77_bridge", WF77_BRIDGE),
        artifact_probe("cron_plan", CRON_PLAN),
        artifact_probe("recommendation_outcome_ledger", RECOMMENDATION_LEDGER),
        artifact_probe("veritas_harness_scorecard", HARNESS_SCORECARD),
        artifact_probe("macro_event_calendar", MACRO_EVENT_CALENDAR),
    ]


def lifecycle(service_state: dict[str, Any], db_state: dict[str, Any]) -> list[dict[str, Any]]:
    queue = as_dict(as_list(db_state.get("queue_items"))[0] if as_list(db_state.get("queue_items")) else {})
    run = as_dict(service_state.get("current_service_run"))
    validator = as_dict(run.get("validator_state"))
    blockers = as_list(run.get("blockers"))
    artifact_handoff = load(ARTIFACT_HANDOFF)
    pm_brief = load(PM_BRIEF)
    stages = [
        ("queued", "completed", "Anonymous request exists in service-state."),
        ("claimed", "completed" if queue.get("claimed_by") else "proof_only", f"Claim proof owner: {queue.get('claimed_by') or 'not currently claimed'}."),
        ("building", "completed", "Evidence, scenario, renderer, PM, and queue artifacts build from local scripts."),
        ("validator_failed", "not_active" if not blockers and validator.get("customer_safe_export_validated") is True else "active", "Fail-closed state when blockers or critical validator findings exist."),
        ("needs_manual_review", "active", "Main-session Veritas remains final integrator before any customer/public/decision claim."),
        ("ready_for_pm_handoff", "completed" if artifact_handoff.get("status") == "ready_for_internal_artifact_only_pm_handoff" else "pending", "Artifact-only PM handoff validates from live proof surfaces."),
        ("closed", "not_started", "Future state: service run can close only after operator review and durable handoff record."),
    ]
    if pm_brief.get("status") == "ready":
        stages.append(("pm_brief_rendered", "completed", "Internal PM readiness PDF/HTML/manifest generated."))
    return [{"stage": stage, "status": status, "notes": notes} for stage, status, notes in stages]


def build_console(db_path: Path) -> dict[str, Any]:
    service_state = load(SERVICE_STATE)
    sqlite_summary = load(SQLITE_SUMMARY)
    operator_queue = load(OPERATOR_QUEUE)
    artifact_handoff = load(ARTIFACT_HANDOFF)
    pm_update = load(PM_UPDATE)
    pm_brief = load(PM_BRIEF)
    renderer = load(RENDERER_REGRESSION)
    scenarios = load(SCENARIO_LIBRARY)
    wf77 = load(WF77_BRIDGE)
    cron_plan = load(CRON_PLAN)
    recommendation_ledger = load(RECOMMENDATION_LEDGER)
    harness_scorecard = load(HARNESS_SCORECARD)
    macro_calendar = load(MACRO_EVENT_CALENDAR)
    db_state = read_db_state(db_path)
    queue_items = as_list(db_state.get("queue_items"))
    first_queue = as_dict(queue_items[0] if queue_items else {})
    current_run = as_dict(service_state.get("current_service_run"))
    current_request = as_dict(current_run.get("request"))
    selected_scenario = as_dict(current_run.get("selected_scenario"))
    renderer_seeded = as_dict(renderer.get("seeded_bad"))
    wf77_summary = as_dict(wf77.get("summary"))
    cron_live = as_dict(cron_plan.get("live_cron_state"))
    recommendation_summary = as_dict(recommendation_ledger.get("recommendation_tracking_summary"))
    harness_summary = as_dict(harness_scorecard.get("summary"))
    macro_summary = as_dict(macro_calendar.get("summary"))

    console = {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "workflow": "WF75",
        "status": "ready",
        "title": "WF75 Operator Console And Control Cockpit",
        "purpose": "Local internal control cockpit for anonymous service-state, SQLite WAL queue, artifact health, PM handoff, and next operator action.",
        "source_artifacts": source_artifacts(),
        "db_state": db_state,
        "summary": {
            "service_state_status": service_state.get("status"),
            "current_service_run_id": current_run.get("service_run_id"),
            "current_scenario_id": selected_scenario.get("scenario_id") or current_request.get("request_id"),
            "current_scenario": current_request.get("scenario"),
            "current_ticker_set": current_request.get("ticker_set"),
            "sqlite_control_plane_status": sqlite_summary.get("status"),
            "operator_queue_status": operator_queue.get("status"),
            "queue_count": len(queue_items),
            "first_queue_status": first_queue.get("status"),
            "first_queue_owner": first_queue.get("owner"),
            "claimed_by": first_queue.get("claimed_by"),
            "pm_update_status": pm_update.get("status"),
            "pm_brief_status": pm_brief.get("status"),
            "artifact_handoff_status": artifact_handoff.get("status"),
            "renderer_status": renderer.get("status"),
            "scenario_count": scenarios.get("template_count"),
            "wf77_price_rows": f"{wf77_summary.get('valid_price_row_count')}/{wf77_summary.get('row_count')}",
            "cron_builder_present": cron_live.get("builder_present"),
            "cron_handoff_present": cron_live.get("handoff_present"),
            "recommendation_ledger_status": recommendation_ledger.get("status"),
            "recommendation_tracking_rows": recommendation_summary.get("tracking_row_count"),
            "pending_owner_decision_rows": recommendation_summary.get("pending_owner_decision_rows"),
            "pending_paper_card_rows": recommendation_summary.get("pending_paper_card_rows"),
            "harness_status": harness_scorecard.get("status"),
            "harness_failure_count": harness_summary.get("failure_count"),
            "harness_warning_count": harness_summary.get("warning_count"),
            "macro_event_calendar_status": macro_calendar.get("status"),
            "macro_next_event_date": macro_summary.get("next_event_date"),
            "macro_next_event_metric": macro_summary.get("next_event_metric"),
            "macro_next_14_day_count": macro_summary.get("next_14_day_count"),
        },
        "operator_queue": queue_items,
        "current_service_run": current_run,
        "service_lifecycle": lifecycle(service_state, db_state),
        "artifact_health": as_list(db_state.get("artifact_refs")),
        "scenario_templates": as_list(scenarios.get("templates")),
        "renderer_regression": {
            "status": renderer.get("status"),
            "clean_scenario_count": renderer.get("clean_scenario_count"),
            "clean_failed_count": renderer.get("clean_failed_count"),
            "seeded_bad_json_validation_status": renderer_seeded.get("json_validation_status"),
            "seeded_bad_markdown_validation_status": renderer_seeded.get("markdown_validation_status"),
            "seeded_bad_critical_count": renderer_seeded.get("critical_count"),
        },
        "wf77_price_evidence": {
            "status": wf77.get("status"),
            "latest_market_data_date": as_dict(wf77.get("source_freshness")).get("latest_market_data_date"),
            "valid_price_row_count": wf77_summary.get("valid_price_row_count"),
            "row_count": wf77_summary.get("row_count"),
            "supplemental_public_price_rows": as_list(wf77_summary.get("supplemental_public_price_rows")),
            "fresh_in_band_tickers": as_list(wf77_summary.get("fresh_in_band_tickers")),
            "fresh_below_stop_tickers": as_list(wf77_summary.get("fresh_below_stop_tickers")),
        },
        "recommendation_outcome_loop": {
            "status": recommendation_ledger.get("status"),
            "source": rel(RECOMMENDATION_LEDGER),
            "tracking_summary": recommendation_summary,
            "tracked_rows": as_list(recommendation_ledger.get("tracked_rows")),
            "boundary": recommendation_ledger.get("boundary"),
        },
        "harness_scorecard": {
            "status": harness_scorecard.get("status"),
            "source": rel(HARNESS_SCORECARD),
            "summary": harness_summary,
            "open_readiness_gaps": as_list(harness_scorecard.get("open_readiness_gaps")),
            "operator_guidance": as_dict(harness_scorecard.get("operator_guidance")),
        },
        "macro_event_calendar": {
            "status": macro_calendar.get("status"),
            "source": rel(MACRO_EVENT_CALENDAR),
            "validation": as_dict(macro_calendar.get("validation")),
            "summary": macro_summary,
            "high_impact_next_14_days": as_list(macro_summary.get("high_impact_next_14_days")),
            "operator_followup_contract": as_dict(macro_calendar.get("operator_followup_contract")),
        },
        "pm_and_cron": {
            "weekly_update": rel(PM_UPDATE),
            "pm_readiness_pdf": "tmp/wf75-pm-readiness-brief.pdf",
            "artifact_only_handoff": rel(ARTIFACT_HANDOFF),
            "cron_builder": {
                "present": cron_live.get("builder_present"),
                "job_id": cron_live.get("builder_job_id"),
                "schedule": "Friday 16:30 America/Phoenix",
            },
            "cron_handoff": {
                "present": cron_live.get("handoff_present"),
                "job_id": cron_live.get("handoff_job_id"),
                "schedule": "Friday 16:40 America/Phoenix",
            },
        },
        "next_operator_action": first_queue.get("next_action") or as_dict(service_state.get("main_session_pickup")).get("next_action"),
        "authority_boundary": {key: False for key in AUTHORITY_FALSE_KEYS},
        "render_policy": {
            "json_is_machine_control_surface": True,
            "html_optional_render": True,
            "markdown_optional_render": True,
            "default_write_json_only": True,
            "legacy_sidecars_require_explicit_flags": True,
            "proof_deletion_allowed": False,
            "archive_or_cleanup_allowed": False,
            "authority": "internal_review_control_only_not_customer_not_approval_not_execution",
        },
    }
    console["validation"] = validate(console)
    if console["validation"]["status"] != "ok":
        console["status"] = "blocked"
    return console


def validate(console: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    if console.get("schema") != SCHEMA:
        errors.append("schema mismatch")
    for artifact in as_list(console.get("source_artifacts")):
        if not isinstance(artifact, dict):
            errors.append("source artifact row must be object")
            continue
        if artifact.get("required") and not artifact.get("exists"):
            errors.append(f"required source missing: {artifact.get('path')}")
        if artifact.get("exists") and not artifact.get("parseable_json"):
            errors.append(f"source not parseable JSON: {artifact.get('path')}")
    db_state = as_dict(console.get("db_state"))
    if db_state.get("status") != "ok":
        errors.append(f"db_state not ok: {db_state.get('errors')}")
    pragmas = as_dict(db_state.get("pragmas"))
    if str(pragmas.get("journal_mode")).lower() != "wal":
        errors.append("SQLite DB is not in WAL mode")
    if int(pragmas.get("busy_timeout_ms") or 0) < 5000:
        errors.append("SQLite busy_timeout below 5000ms")
    if int(pragmas.get("foreign_keys") or 0) != 1:
        errors.append("SQLite foreign_keys not enabled")
    queue_items = as_list(console.get("operator_queue"))
    if not queue_items:
        errors.append("operator queue is empty")
    for row in queue_items:
        if not isinstance(row, dict):
            errors.append("queue row must be object")
            continue
        for flag in ("inline_execution_allowed", "external_delivery_allowed", "customer_data_use_allowed"):
            if int(row.get(flag) or 0) != 0:
                errors.append(f"queue authority flag must be false: {flag}")
    artifact_health = as_list(console.get("artifact_health"))
    bad_artifacts = [
        row for row in artifact_health
        if isinstance(row, dict) and int(row.get("required") or 0) == 1 and (int(row.get("exists_flag") or 0) != 1 or int(row.get("parseable_json") or 0) != 1)
    ]
    if bad_artifacts:
        errors.append(f"required artifact refs are missing or unparseable: {bad_artifacts}")
    lifecycle_statuses = {row.get("stage"): row.get("status") for row in as_list(console.get("service_lifecycle")) if isinstance(row, dict)}
    for stage in ("queued", "building", "pm_brief_rendered"):
        if lifecycle_statuses.get(stage) != "completed":
            errors.append(f"lifecycle stage not completed: {stage}={lifecycle_statuses.get(stage)}")
    if lifecycle_statuses.get("ready_for_pm_handoff") != "completed":
        warnings.append(f"lifecycle stage not completed: ready_for_pm_handoff={lifecycle_statuses.get('ready_for_pm_handoff')}")
    renderer = as_dict(console.get("renderer_regression"))
    if renderer.get("status") != "ok" or renderer.get("clean_failed_count") != 0:
        errors.append("renderer regression not clean")
    if renderer.get("seeded_bad_json_validation_status") != "error" or renderer.get("seeded_bad_markdown_validation_status") != "error":
        errors.append("seeded-bad regression did not fail as expected")
    summary = as_dict(console.get("summary"))
    if summary.get("pm_brief_status") != "ready":
        errors.append("PM readiness brief is not ready")
    if summary.get("artifact_handoff_status") != "ready_for_internal_artifact_only_pm_handoff":
        warnings.append("artifact-only handoff is not ready")
    rec_loop = as_dict(console.get("recommendation_outcome_loop"))
    rec_summary = as_dict(rec_loop.get("tracking_summary"))
    if rec_loop.get("status") != "ok":
        errors.append("recommendation/outcome ledger is not ok")
    if int(rec_summary.get("tracking_row_count") or 0) == 0:
        warnings.append("recommendation/outcome ledger has no tracking rows (valid empty preview state while ledger status is ok; append pipeline found zero candidates)")
    if rec_summary.get("predictive_or_model_claims_allowed") is not False:
        errors.append("recommendation/outcome ledger must block predictive/model claims")
    if rec_summary.get("paper_or_live_execution_allowed") is not False:
        errors.append("recommendation/outcome ledger must block paper/live execution")
    harness = as_dict(console.get("harness_scorecard"))
    if harness.get("status") not in {"ok", "warning"}:
        warnings.append(f"harness scorecard not currently usable: {harness.get('status')}")
    macro_calendar = as_dict(console.get("macro_event_calendar"))
    if macro_calendar.get("status") != "ok":
        errors.append(f"macro event calendar not ok: {macro_calendar.get('status')}")
    if as_dict(macro_calendar.get("validation")).get("status") != "ok":
        errors.append("macro event calendar validation is not ok")
    if int(as_dict(macro_calendar.get("summary")).get("next_14_day_count") or 0) == 0:
        warnings.append("macro event calendar has no high-impact event inside 14 days")
    boundary = as_dict(console.get("authority_boundary"))
    for key in AUTHORITY_FALSE_KEYS:
        if boundary.get(key) is not False:
            errors.append(f"authority flag must be false: {key}")
    return {"status": "ok" if not errors else "error", "errors": errors, "warnings": warnings}


def render_html(console: dict[str, Any]) -> str:
    summary = as_dict(console.get("summary"))
    queue = as_list(console.get("operator_queue"))
    artifacts = as_list(console.get("artifact_health"))
    lifecycle_rows = as_list(console.get("service_lifecycle"))
    scenarios = as_list(console.get("scenario_templates"))
    wf77 = as_dict(console.get("wf77_price_evidence"))
    pm = as_dict(console.get("pm_and_cron"))
    rec_loop = as_dict(console.get("recommendation_outcome_loop"))
    rec_summary = as_dict(rec_loop.get("tracking_summary"))
    rec_rows = as_list(rec_loop.get("tracked_rows"))
    harness = as_dict(console.get("harness_scorecard"))
    harness_summary = as_dict(harness.get("summary"))
    macro_calendar = as_dict(console.get("macro_event_calendar"))
    macro_summary = as_dict(macro_calendar.get("summary"))
    macro_events = as_list(macro_calendar.get("high_impact_next_14_days"))
    current_tickers = summary.get("current_ticker_set") if isinstance(summary.get("current_ticker_set"), list) else []

    def table(headers: list[str], body: list[list[Any]]) -> str:
        head = "".join(f"<th>{esc(h)}</th>" for h in headers)
        rows_html = []
        for row in body:
            rows_html.append("<tr>" + "".join(f"<td>{cell}</td>" for cell in row) + "</tr>")
        return f"<table><thead><tr>{head}</tr></thead><tbody>{''.join(rows_html)}</tbody></table>"

    queue_table = table(
        ["Queue", "Status", "Priority", "Owner", "Claim", "Next Action"],
        [
            [
                esc(row.get("queue_id")),
                badge(row.get("status")),
                esc(row.get("priority")),
                esc(row.get("owner")),
                esc(row.get("claimed_by") or "unclaimed"),
                esc(row.get("next_action")),
            ]
            for row in queue if isinstance(row, dict)
        ],
    )
    lifecycle_table = table(
        ["Stage", "Status", "Notes"],
        [[esc(row.get("stage")), badge(row.get("status")), esc(row.get("notes"))] for row in lifecycle_rows if isinstance(row, dict)],
    )
    artifact_table = table(
        ["Artifact", "Required", "Exists", "Parseable", "Status", "Validation"],
        [
            [
                esc(row.get("artifact_key")),
                esc(row.get("required")),
                badge("yes" if row.get("exists_flag") else "missing"),
                badge("yes" if row.get("parseable_json") else "bad"),
                badge(row.get("status")),
                badge(row.get("validation_status")),
            ]
            for row in artifacts if isinstance(row, dict)
        ],
    )
    scenario_list = "".join(
        f"<li><strong>{esc(row.get('scenario_id'))}</strong>: {esc(row.get('coverage_intent'))}</li>"
        for row in scenarios if isinstance(row, dict)
    )
    rec_table = table(
        ["Ticker", "Subtype", "Status", "Decision", "Source"],
        [
            [
                esc(row.get("ticker")),
                esc(row.get("event_subtype")),
                badge(as_dict(row.get("payload")).get("current_status")),
                badge(as_dict(row.get("payload")).get("decision_status")),
                esc(as_dict(row.get("payload")).get("source_artifact_path")),
            ]
            for row in rec_rows if isinstance(row, dict)
        ],
    )
    macro_table = table(
        ["Date", "Agency", "Metric", "Period"],
        [
            [esc(row.get("date")), esc(row.get("agency")), esc(row.get("metric")), esc(row.get("period"))]
            for row in macro_events if isinstance(row, dict)
        ],
    )
    return f"""<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>{esc(console.get('title'))}</title>
<style>
  body {{ margin: 0; font-family: Arial, Helvetica, sans-serif; background:#f6f8fb; color:#172033; }}
  main {{ max-width: 1180px; margin: 0 auto; padding: 24px; }}
  h1 {{ margin: 0 0 6px; color:#0e294a; }}
  h2 {{ margin: 22px 0 8px; color:#12345c; font-size: 18px; }}
  .subtitle {{ color:#5c6f86; margin-bottom: 18px; }}
  .grid {{ display:grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 10px; }}
  .card {{ background:white; border:1px solid #d8e1ec; border-radius:8px; padding:12px; }}
  .label {{ color:#65778c; text-transform:uppercase; letter-spacing:.08em; font-size:11px; }}
  .value {{ font-weight:700; font-size:18px; margin-top:4px; color:#0e294a; overflow-wrap:anywhere; }}
  table {{ width:100%; border-collapse:collapse; background:white; border:1px solid #d8e1ec; }}
  th {{ background:#12345c; color:white; text-align:left; padding:8px; font-size:12px; }}
  td {{ border-top:1px solid #e2e8f0; padding:8px; vertical-align:top; font-size:13px; }}
  .badge {{ display:inline-block; border-radius:999px; padding:2px 8px; font-size:12px; font-weight:700; background:#e8eef7; color:#244b73; }}
  .good {{ background:#e6f4ea; color:#176238; }}
  .warn {{ background:#fff1cc; color:#765200; }}
  .bad {{ background:#fde8e8; color:#8f1d1d; }}
  .neutral {{ background:#e8eef7; color:#244b73; }}
  ul {{ background:white; border:1px solid #d8e1ec; border-radius:8px; padding:14px 18px 14px 30px; }}
  li {{ margin: 6px 0; }}
  .boundary {{ background:#fff7dd; border:1px solid #d5a736; border-radius:8px; padding:10px; margin-top:18px; }}
</style>
</head>
<body>
<main>
  <h1>{esc(console.get('title'))}</h1>
  <div class="subtitle">Generated {esc(console.get('generated_at_utc'))} | {badge(console.get('status'))} | internal anonymous-scenario control surface</div>
  <section class="grid">
    <div class="card"><div class="label">Current Scenario</div><div class="value">{esc(summary.get('current_scenario_id'))}</div></div>
    <div class="card"><div class="label">Current Tickers</div><div class="value">{esc(', '.join(current_tickers))}</div></div>
    <div class="card"><div class="label">Service State</div><div class="value">{badge(summary.get('service_state_status'))}</div></div>
    <div class="card"><div class="label">SQLite WAL</div><div class="value">{badge(summary.get('sqlite_control_plane_status'))}</div></div>
    <div class="card"><div class="label">Queue</div><div class="value">{esc(summary.get('queue_count'))} item(s)</div></div>
    <div class="card"><div class="label">PM Brief</div><div class="value">{badge(summary.get('pm_brief_status'))}</div></div>
    <div class="card"><div class="label">Renderer</div><div class="value">{badge(summary.get('renderer_status'))}</div></div>
    <div class="card"><div class="label">Scenarios</div><div class="value">{esc(summary.get('scenario_count'))}</div></div>
    <div class="card"><div class="label">WF77 Prices</div><div class="value">{esc(summary.get('wf77_price_rows'))}</div></div>
    <div class="card"><div class="label">Cron Pair</div><div class="value">{badge('installed' if summary.get('cron_builder_present') and summary.get('cron_handoff_present') else 'missing')}</div></div>
    <div class="card"><div class="label">Recommendation Loop</div><div class="value">{badge(summary.get('recommendation_ledger_status'))}</div></div>
    <div class="card"><div class="label">Pending Paper Cards</div><div class="value">{esc(summary.get('pending_paper_card_rows'))}</div></div>
    <div class="card"><div class="label">Harness</div><div class="value">{badge(summary.get('harness_status'))}</div></div>
    <div class="card"><div class="label">Harness Gaps</div><div class="value">{esc(summary.get('harness_warning_count'))} warn / {esc(summary.get('harness_failure_count'))} fail</div></div>
    <div class="card"><div class="label">Macro Calendar</div><div class="value">{badge(summary.get('macro_event_calendar_status'))}</div></div>
    <div class="card"><div class="label">Next Macro Event</div><div class="value">{esc(summary.get('macro_next_event_date'))} {esc(summary.get('macro_next_event_metric'))}</div></div>
  </section>
  <h2>Operator Queue</h2>
  {queue_table}
  <h2>Service Lifecycle</h2>
  {lifecycle_table}
  <h2>Artifact Health</h2>
  {artifact_table}
  <h2>Scenario Templates</h2>
  <ul>{scenario_list}</ul>
  <h2>Evidence And PM Links</h2>
  <div class="card">
    <p><strong>Latest market data:</strong> {esc(wf77.get('latest_market_data_date'))}</p>
    <p><strong>Supplemental price rows:</strong> {esc(', '.join(wf77.get('supplemental_public_price_rows') or []))}</p>
    <p><strong>Fresh in-band:</strong> {esc(', '.join((wf77.get('fresh_in_band_tickers') or [])[:12]))}</p>
    <p><strong>Fresh below stop:</strong> {esc(', '.join((wf77.get('fresh_below_stop_tickers') or [])[:12]))}</p>
    <p><strong>PM PDF:</strong> {esc(pm.get('pm_readiness_pdf'))}</p>
    <p><strong>Artifact handoff:</strong> {esc(pm.get('artifact_only_handoff'))}</p>
  </div>
  <h2>Recommendation Outcome Loop</h2>
  <div class="card">
    <p><strong>Tracking rows:</strong> {esc(rec_summary.get('tracking_row_count'))}</p>
    <p><strong>Pending owner decisions:</strong> {esc(rec_summary.get('pending_owner_decision_rows'))}</p>
    <p><strong>Pending paper cards:</strong> {esc(rec_summary.get('pending_paper_card_rows'))}</p>
    <p><strong>Tracked tickers:</strong> {esc(', '.join(rec_summary.get('tracked_tickers') or []))}</p>
  </div>
  {rec_table}
  <h2>Harness Scorecard</h2>
  <div class="card">
    <p><strong>Status:</strong> {esc(harness.get('status'))}</p>
    <p><strong>Checks:</strong> {esc(harness_summary.get('pass_count'))} pass / {esc(harness_summary.get('warning_count'))} warn / {esc(harness_summary.get('failure_count'))} fail</p>
    <p><strong>Source:</strong> {esc(harness.get('source'))}</p>
  </div>
  <h2>Macro Event Calendar</h2>
  <div class="card">
    <p><strong>Status:</strong> {esc(macro_calendar.get('status'))}</p>
    <p><strong>Next event:</strong> {esc(macro_summary.get('next_event_date'))} {esc(macro_summary.get('next_event_metric'))}</p>
    <p><strong>High-impact events next 14 days:</strong> {esc(macro_summary.get('next_14_day_count'))}</p>
    <p><strong>Source:</strong> {esc(macro_calendar.get('source'))}</p>
  </div>
  {macro_table}
  <div class="boundary"><strong>Boundary:</strong> Internal review/control cockpit only. No public launch, real customer data, external delivery, legal/source/compliance readiness, SQL/ticker import, portfolio/canon mutation, paper/live/account action, or owner approval inference.</div>
</main>
</body>
</html>"""


def render_markdown(console: dict[str, Any]) -> str:
    summary = as_dict(console.get("summary"))
    validation = as_dict(console.get("validation"))
    rec_loop = as_dict(console.get("recommendation_outcome_loop"))
    rec_summary = as_dict(rec_loop.get("tracking_summary"))
    lines = [
        "# WF75 Operator Console And Control Cockpit",
        "",
        f"- Generated: `{console.get('generated_at_utc')}`",
        f"- Status: `{console.get('status')}`",
        f"- Validation: `{validation.get('status')}`",
        "",
        "## Summary",
        "",
        f"- Current scenario: `{summary.get('current_scenario_id')}`",
        f"- Current tickers: `{', '.join(summary.get('current_ticker_set') or [])}`",
        f"- Service state: `{summary.get('service_state_status')}`",
        f"- SQLite control plane: `{summary.get('sqlite_control_plane_status')}`",
        f"- Queue count: `{summary.get('queue_count')}`",
        f"- PM brief: `{summary.get('pm_brief_status')}`",
        f"- Renderer: `{summary.get('renderer_status')}`",
        f"- Scenario count: `{summary.get('scenario_count')}`",
        f"- WF77 price rows: `{summary.get('wf77_price_rows')}`",
        f"- Recommendation ledger: `{summary.get('recommendation_ledger_status')}`",
        f"- Recommendation tracking rows: `{summary.get('recommendation_tracking_rows')}`",
        f"- Pending paper cards: `{summary.get('pending_paper_card_rows')}`",
        f"- Harness scorecard: `{summary.get('harness_status')}` / `{summary.get('harness_warning_count')}` warn / `{summary.get('harness_failure_count')}` fail",
        f"- Macro event calendar: `{summary.get('macro_event_calendar_status')}` / next `{summary.get('macro_next_event_date')}` `{summary.get('macro_next_event_metric')}` / next 14 days `{summary.get('macro_next_14_day_count')}`",
        "",
        "## Next Operator Action",
        "",
        str(console.get("next_operator_action")),
        "",
        "## Lifecycle",
        "",
    ]
    for row in as_list(console.get("service_lifecycle")):
        if isinstance(row, dict):
            lines.append(f"- `{row.get('stage')}`: `{row.get('status')}` - {row.get('notes')}")
    lines.extend(
        [
            "",
            "## Recommendation Outcome Loop",
            "",
            f"- Tracking rows: `{rec_summary.get('tracking_row_count')}`",
            f"- Pending owner decisions: `{rec_summary.get('pending_owner_decision_rows')}`",
            f"- Pending paper cards: `{rec_summary.get('pending_paper_card_rows')}`",
            f"- Tracked tickers: `{', '.join(rec_summary.get('tracked_tickers') or [])}`",
            "- Durable append: `false`",
            "- Predictive/model claims: `false`",
            "- Paper/live execution: `false`",
        ]
    )
    lines.extend(
        [
            "",
            "## Outputs",
            "",
            "- `tmp/wf75-operator-console.json`",
            "- optional HTML render when `--write-html` is supplied",
            "- optional Markdown digest when `--write-md` is supplied",
            "",
            "## Boundary",
            "",
            "Internal review/control cockpit only. No public launch, real customer data, external delivery, legal/source/compliance readiness, SQL/ticker import, portfolio/canon mutation, paper/live/account action, or owner approval inference.",
            "",
        ]
    )
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build WF75 local operator console/control cockpit.")
    parser.add_argument("--write", action="store_true", help="Write the JSON machine control surface.")
    parser.add_argument("--json-only", action="store_true", help="Deprecated compatibility flag; --write is JSON-only by default.")
    parser.add_argument("--write-html", action="store_true", help="Explicitly write the optional HTML render.")
    parser.add_argument("--write-md", action="store_true", help="Also write the optional human-readable Markdown digest.")
    parser.add_argument("--validate", action="store_true", help="Fail if console validation is not clean.")
    parser.add_argument("--db", default=str(DEFAULT_DB))
    parser.add_argument("--json-out", default=str(DEFAULT_JSON))
    parser.add_argument("--html-out", default=str(DEFAULT_HTML))
    parser.add_argument("--md-out", default=str(DEFAULT_MD))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    db_path = Path(args.db)
    json_out = Path(args.json_out)
    html_out = Path(args.html_out)
    md_out = Path(args.md_out)
    for name, path in (("db", db_path), ("json_out", json_out), ("html_out", html_out), ("md_out", md_out)):
        if not path.is_absolute():
            path = ROOT / path
        if name == "db":
            db_path = path
        elif name == "json_out":
            json_out = path
        elif name == "html_out":
            html_out = path
        elif name == "md_out":
            md_out = path

    console = build_console(db_path)
    if args.write:
        write_html = args.write_html
        outputs = {"json": rel(json_out)}
        if write_html:
            outputs["html"] = rel(html_out)
        if args.write_md:
            outputs["markdown"] = rel(md_out)
        console["outputs"] = outputs
        atomic_write_json(json_out, console)
        if write_html:
            atomic_write_text(html_out, render_html(console))
    if args.write_md:
        atomic_write_text(md_out, render_markdown(console))
        outputs = console.setdefault("outputs", {})
        if isinstance(outputs, dict):
            outputs["markdown"] = rel(md_out)
    print(json.dumps(console, indent=2, sort_keys=True))
    if args.validate and console.get("status") != "ready":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
