#!/usr/bin/env python3
"""Build WF75 service-state and automation movement proof.

This is the Phase C/D bridge for the WF75 infrastructure sprint. It records
anonymous service request state, operator queue posture, and validator-gated
movement rules. It does not store real customer data, deliver externally,
mutate finance canon/portfolio state, import SQL/tickers, or grant execution
authority.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, load_json_artifact

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
RUN_DIR = TMP / "wf75-service-runs"

DEFAULT_STATE = TMP / "wf75-service-state-current.json"
DEFAULT_QUEUE = TMP / "wf75-operator-queue.json"
DEFAULT_MOVEMENT = TMP / "wf75-automation-movement.json"

CUSTOMER_EXPORT = TMP / "retail-saas-fixture-demo.customer-export.json"
CUSTOMER_EXPORT_VALIDATION = TMP / "retail-saas-fixture-demo.customer-export-validation.json"
HTML_VALIDATION = TMP / "retail-saas-fixture-demo.html-validation.json"
RENDERER_OUTPUT_DIR = TMP / "wf75-renderer-regression"
WF77_BRIDGE = TMP / "wf77-price-freshness-bridge.json"
WF77_SUPPLEMENTAL_PRICE_EVIDENCE = TMP / "wf77-supplemental-price-evidence.json"
RENDERER_REGRESSION = TMP / "wf75-renderer-export-regression.json"
SCENARIO_TEMPLATE_LIBRARY = TMP / "wf75-scenario-template-library.json"
SQLITE_CONTROL_PLANE = TMP / "wf75-service-state-sqlite.json"
ARTIFACT_ONLY_PM_HANDOFF = TMP / "wf75-artifact-only-pm-handoff.json"
OPERATOR_CONSOLE = TMP / "wf75-operator-console.json"
READINESS_PLAN = TMP / "wf75-service-led-saas-readiness-plan.json"
OVERNIGHT_PLAN = TMP / "wf75-real-functioning-overnight-plan.json"

STATE_SCHEMA = "veritas.wf75.service_state.v1"
QUEUE_SCHEMA = "veritas.wf75.operator_queue.v1"
MOVEMENT_SCHEMA = "veritas.wf75.automation_movement.v1"
RUN_SCHEMA = "veritas.wf75.service_run.v1"
DEFAULT_SCENARIO_ID = "anon-watchlist-ai-infrastructure-v1"

AUTHORITY_FALSE_KEYS = [
    "real_customer_data_allowed",
    "customer_data_retention_allowed",
    "customer_output_external_delivery_allowed",
    "public_launch_allowed",
    "legal_or_compliance_ready",
    "source_licensing_assumed",
    "personalized_regulated_advice_allowed",
    "brokerage_or_account_connection_allowed",
    "paper_order_execution_allowed",
    "live_trade_or_account_action_allowed",
    "portfolio_or_canon_mutation_allowed",
    "sql_or_ticker_import_allowed",
    "owner_approval_inferred",
    "config_auth_channel_runtime_mutation_allowed",
]

FUTURE_QUARANTINE_CLASSES = [
    "real_customer_identity",
    "real_customer_portfolio",
    "suitability_profile",
    "risk_profile",
    "income_net_worth",
    "tax_retirement",
    "brokerage_account",
    "credentials",
    "external_delivery_destination",
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


def artifact_summary(path: Path, *, required: bool = True) -> dict[str, Any]:
    payload = load_json_artifact(path)
    summary: dict[str, Any] = {
        "path": rel(path),
        "required": required,
        "exists": path.exists(),
        "parseable_json": isinstance(payload, dict),
    }
    if path.exists():
        summary["size_bytes"] = path.stat().st_size
    if isinstance(payload, dict):
        for key in ("schema", "schema_version", "status", "generated_at_utc"):
            if key in payload:
                summary[key] = payload[key]
        validation = payload.get("validation")
        if isinstance(validation, dict):
            summary["validation_status"] = validation.get("status")
    return summary


def safe_scenario_name(scenario_id: str) -> str:
    return "".join(ch if ch.isalnum() or ch in {"-", "_"} else "-" for ch in scenario_id).strip("-") or DEFAULT_SCENARIO_ID


def scenario_artifacts(scenario_id: str) -> dict[str, Path]:
    safe = safe_scenario_name(scenario_id)
    return {
        "customer_export": RENDERER_OUTPUT_DIR / f"{safe}.customer-export.json",
        "validation": RENDERER_OUTPUT_DIR / f"{safe}.validation.json",
        "html": RENDERER_OUTPUT_DIR / f"{safe}.html",
        "markdown": RENDERER_OUTPUT_DIR / f"{safe}.md",
    }


def load_scenario_template(scenario_id: str) -> dict[str, Any]:
    library = as_dict(load_json_artifact(SCENARIO_TEMPLATE_LIBRARY))
    for template in as_list(library.get("templates")):
        if isinstance(template, dict) and template.get("scenario_id") == scenario_id:
            return template
    return {}


def selected_inputs(scenario_id: str) -> dict[str, Any]:
    paths = scenario_artifacts(scenario_id)
    customer_export_path = paths["customer_export"] if paths["customer_export"].exists() else CUSTOMER_EXPORT
    validation_path = paths["validation"] if paths["validation"].exists() else CUSTOMER_EXPORT_VALIDATION
    return {
        "scenario_id": scenario_id,
        "template": load_scenario_template(scenario_id),
        "customer_export_path": customer_export_path,
        "customer_validation_path": validation_path,
        "html_validation_path": validation_path if paths["validation"].exists() else HTML_VALIDATION,
        "html_path": paths["html"],
        "markdown_path": paths["markdown"],
    }


def status_from_artifacts(artifacts: list[dict[str, Any]], wf77: dict[str, Any], customer_validation: dict[str, Any], html_validation: dict[str, Any]) -> str:
    for item in artifacts:
        if item.get("required") and not item.get("exists"):
            return "blocked"
        if item.get("exists") and not item.get("parseable_json"):
            return "blocked"
    if str(customer_validation.get("status") or "").lower() not in {"ok"}:
        return "blocked"
    if str(html_validation.get("status") or "").lower() not in {"ok"}:
        return "blocked"
    if str(wf77.get("status") or "").lower() in {"blocked", "error", "critical"}:
        return "blocked"
    summary = as_dict(wf77.get("summary"))
    if summary.get("missing_price_rows") or summary.get("excluded_price_rows") or summary.get("stale_price_rows"):
        return "warning"
    if str(wf77.get("status") or "").lower() == "warning":
        return "warning"
    return "ok"


def build_blockers(wf77: dict[str, Any], customer_validation: dict[str, Any], html_validation: dict[str, Any], customer_validation_path: Path, html_validation_path: Path) -> list[dict[str, Any]]:
    blockers: list[dict[str, Any]] = []
    wf77_summary = as_dict(wf77.get("summary"))
    missing = as_list(wf77_summary.get("missing_price_rows"))
    if missing:
        blockers.append(
            {
                "code": "missing_price_rows",
                "severity": "warning",
                "summary": "WF77 price bridge lacks current rows for part of the production universe.",
                "affected": missing,
                "blocks": ["clean price-freshness claim", "unqualified automated handoff"],
                "next_action": "Repair or explicitly explain missing rows before treating the service state as clean.",
            }
        )
    excluded = as_list(wf77_summary.get("excluded_price_rows"))
    if excluded:
        blockers.append(
            {
                "code": "excluded_price_rows",
                "severity": "warning",
                "summary": "WF77 price bridge has production-universe rows intentionally excluded from technical_refresh by current lane entitlement.",
                "affected": excluded,
                "blocks": ["clean all-production-universe price-freshness claim", "unqualified automated handoff"],
                "next_action": "Either keep the explicit exclusion reason or deliberately expand the upstream price source without widening portfolio/deployment authority.",
            }
        )
    stale = as_list(wf77_summary.get("stale_price_rows"))
    if stale:
        blockers.append(
            {
                "code": "stale_price_rows",
                "severity": "warning",
                "summary": "WF77 price bridge contains stale rows.",
                "affected": stale,
                "blocks": ["clean price-freshness claim"],
                "next_action": "Refresh public-market price evidence or downgrade output freshness labels.",
            }
        )
    if str(customer_validation.get("status") or "").lower() != "ok":
        blockers.append(
            {
                "code": "customer_export_validation_failed",
                "severity": "critical",
                "summary": "Customer-safe export validation is not clean.",
                "affected": [rel(customer_validation_path)],
                "blocks": ["validated brief pipeline", "operator handoff ready state"],
                "next_action": "Fix export or validator findings before any customer-safe brief is considered ready.",
            }
        )
    if str(html_validation.get("status") or "").lower() != "ok":
        blockers.append(
            {
                "code": "html_validation_failed",
                "severity": "critical",
                "summary": "HTML/rendered-output validation is not clean.",
                "affected": [rel(html_validation_path)],
                "blocks": ["validated brief pipeline", "operator handoff ready state"],
                "next_action": "Fix rendered output before treating the renderer pipeline as ready.",
            }
        )
    return blockers


def build_service_run(now: str, scenario_id: str = DEFAULT_SCENARIO_ID) -> dict[str, Any]:
    inputs = selected_inputs(scenario_id)
    template = as_dict(inputs.get("template"))
    customer_export_path = inputs["customer_export_path"]
    customer_validation_path = inputs["customer_validation_path"]
    html_validation_path = inputs["html_validation_path"]
    customer_export = as_dict(load_json_artifact(customer_export_path))
    customer_validation = as_dict(load_json_artifact(customer_validation_path))
    html_validation = as_dict(load_json_artifact(html_validation_path))
    wf77 = as_dict(load_json_artifact(WF77_BRIDGE))
    readiness_plan = as_dict(load_json_artifact(READINESS_PLAN))

    artifacts = [
        artifact_summary(customer_export_path),
        artifact_summary(customer_validation_path),
        artifact_summary(html_validation_path),
        artifact_summary(WF77_BRIDGE),
        artifact_summary(WF77_SUPPLEMENTAL_PRICE_EVIDENCE),
        artifact_summary(RENDERER_REGRESSION),
        artifact_summary(SCENARIO_TEMPLATE_LIBRARY),
        artifact_summary(SQLITE_CONTROL_PLANE, required=False),
        artifact_summary(ARTIFACT_ONLY_PM_HANDOFF, required=False),
        artifact_summary(READINESS_PLAN),
        artifact_summary(OVERNIGHT_PLAN, required=False),
    ]
    status = status_from_artifacts(artifacts, wf77, customer_validation, html_validation)
    blockers = build_blockers(wf77, customer_validation, html_validation, customer_validation_path, html_validation_path)
    export_request = as_dict(customer_export.get("anonymous_service_request"))
    tickers = as_list(export_request.get("ticker_set")) or [
        item.get("ticker") for item in as_list(customer_export.get("watchlist_items")) if isinstance(item, dict) and item.get("ticker")
    ]
    bridge_summary = as_dict(wf77.get("summary"))

    external_delivery_ready = False
    customer_safe_export_validated = str(customer_validation.get("status") or "").lower() == "ok" and str(html_validation.get("status") or "").lower() == "ok"

    return {
        "schema": RUN_SCHEMA,
        "generated_at_utc": now,
        "service_run_id": f"wf75-{scenario_id}",
        "workflow": "WF75",
        "phase": "C",
        "phase_name": "Service-state layer v0",
        "status": status,
        "request": {
            "request_id": export_request.get("request_id") or template.get("scenario_id") or scenario_id,
            "request_type": export_request.get("request_type") or template.get("request_type") or "watchlist_brief",
            "scenario": export_request.get("scenario") or template.get("scenario") or "anonymous_service_request",
            "audience_segment": export_request.get("audience_segment") or template.get("audience_segment") or "self_directed_retail_investor",
            "ticker_set": tickers or as_list(template.get("ticker_set")),
            "anonymous_service_request": True,
            "fake_person_persona_used": False,
        },
        "selected_scenario": {
            "scenario_id": scenario_id,
            "coverage_intent": template.get("coverage_intent"),
            "expected_validator_outcome": template.get("expected_validator_outcome"),
            "renderer_customer_export": rel(customer_export_path),
            "renderer_validation": rel(customer_validation_path),
            "renderer_html": rel(inputs["html_path"]),
            "renderer_markdown": rel(inputs["markdown_path"]),
        },
        "data_trust_state": {
            "current_allowed_classes": [
                "anonymous_service_request",
                "public_market_evidence",
                "public_company_reference_evidence",
                "generated_customer_safe_fixture_export",
            ],
            "real_customer_data_present": False,
            "customer_identity_present": False,
            "customer_portfolio_present": False,
            "suitability_or_risk_profile_present": False,
            "brokerage_or_account_data_present": False,
            "credential_data_present": False,
            "future_quarantine_classes": [
                {"data_class": name, "present": False, "use_allowed": False, "external_delivery_allowed": False}
                for name in FUTURE_QUARANTINE_CLASSES
            ],
        },
        "artifact_inputs": artifacts,
        "validator_state": {
            "customer_export_validation_status": customer_validation.get("status"),
            "html_validation_status": html_validation.get("status"),
            "selected_scenario_validation_status": customer_validation.get("status"),
            "wf77_bridge_status": wf77.get("status"),
            "wf75_readiness_plan_status": readiness_plan.get("status"),
            "customer_safe_export_validated": customer_safe_export_validated,
            "external_delivery_ready": external_delivery_ready,
        },
        "evidence_state": {
            "latest_market_data_date": as_dict(wf77.get("source_freshness")).get("latest_market_data_date"),
            "source_freshness_status": as_dict(wf77.get("source_freshness")).get("status"),
            "missing_price_rows": as_list(bridge_summary.get("missing_price_rows")),
            "excluded_price_rows": as_list(bridge_summary.get("excluded_price_rows")),
            "price_unavailable_rows": as_list(bridge_summary.get("price_unavailable_rows")),
            "valid_price_row_count": bridge_summary.get("valid_price_row_count"),
            "row_count": bridge_summary.get("row_count"),
            "stale_price_rows": as_list(bridge_summary.get("stale_price_rows")),
            "fresh_in_band_tickers": as_list(bridge_summary.get("fresh_in_band_tickers")),
            "fresh_below_stop_tickers": as_list(bridge_summary.get("fresh_below_stop_tickers")),
            "supplemental_public_price_rows": as_list(bridge_summary.get("supplemental_public_price_rows")),
            "supplemental_public_price_row_count": bridge_summary.get("supplemental_public_price_row_count"),
            "review_signals_only": True,
        },
        "blockers": blockers,
        "next_operator_actions": [
            {
                "action_id": "repair_or_accept_unavailable_wf77_price_rows",
                "status": "needed" if as_list(bridge_summary.get("missing_price_rows")) or as_list(bridge_summary.get("excluded_price_rows")) else "not_needed",
                "owner": "main_session_or_bounded_helper",
                "authority": "read_only_repair_or_explanation_only",
            },
            {
                "action_id": "source_open_price_sensitive_claims",
                "status": "needed",
                "owner": "main_session",
                "authority": "review_only_material_claim_check",
            },
            {
                "action_id": "promote_reusable_renderer_and_regression_harness",
                "status": "completed" if RENDERER_REGRESSION.exists() else "queued",
                "owner": "main_session_or_bounded_helper",
                "authority": "anonymous_scenario_fixture_only",
            },
            {
                "action_id": "expand_scenario_template_library",
                "status": "completed" if SCENARIO_TEMPLATE_LIBRARY.exists() else "queued",
                "owner": "main_session_or_bounded_helper",
                "authority": "anonymous_scenario_fixture_only",
            },
            {
                "action_id": "build_sqlite_wal_control_plane",
                "status": "completed" if SQLITE_CONTROL_PLANE.exists() else "queued",
                "owner": "main_session_or_bounded_helper",
                "authority": "local_control_plane_only_not_canon_or_customer_db",
            },
            {
                "action_id": "build_artifact_only_pm_handoff",
                "status": "completed" if ARTIFACT_ONLY_PM_HANDOFF.exists() else "queued",
                "owner": "main_session_or_bounded_helper",
                "authority": "artifact_only_internal_pm_handoff",
            },
            {
                "action_id": "build_operator_console_control_cockpit",
                "status": "completed" if OPERATOR_CONSOLE.exists() else "queued",
                "owner": "main_session_or_bounded_helper",
                "authority": "local_internal_control_surface_only",
            },
        ],
        "heartbeat_pickup": {
            "may_validate_shape": True,
            "may_refresh_this_artifact": True,
            "refresh_command": f"python scripts\\wf75_service_state.py --scenario-id {scenario_id} --write --validate",
            "may_queue_main_session_review": True,
            "may_execute_phase": False,
            "notify_if": [
                "validation.status != ok",
                "service_run.status == blocked",
                "blockers contains critical",
                "authority_boundary has any true blocked flag",
            ],
            "must_not": [
                "store real customer data",
                "approve customer delivery",
                "run paper/live/account actions",
                "mutate canon or portfolio",
                "infer owner approval",
            ],
        },
        "authority_boundary": {key: False for key in AUTHORITY_FALSE_KEYS},
    }


def build_queue(service_run: dict[str, Any], now: str) -> dict[str, Any]:
    status = service_run.get("status")
    severity = "warning" if status == "warning" else "normal"
    blockers = as_list(service_run.get("blockers"))
    critical = any(isinstance(item, dict) and item.get("severity") == "critical" for item in blockers)
    if critical:
        severity = "critical"
    selected = as_dict(service_run.get("selected_scenario"))
    selected_validation = selected.get("renderer_validation") or rel(CUSTOMER_EXPORT_VALIDATION)
    selected_html = selected.get("renderer_html") or rel(HTML_VALIDATION)
    queue_item = {
        "queue_id": "wf75-service-state-current",
        "service_run_id": service_run.get("service_run_id"),
        "workflow": "WF75",
        "phase": "D",
        "phase_name": "Automation movement and validated brief handoff",
        "status": "blocked" if critical else "handoff_ready_with_warning" if status == "warning" else "handoff_ready",
        "priority": "high" if severity in {"critical", "warning"} else "normal",
        "owner": "Veritas main session",
        "heartbeat_action": "queue_main_session_review",
        "inline_execution_allowed": False,
        "external_delivery_allowed": False,
        "customer_data_use_allowed": False,
        "next_action": (
            "Resolve or explicitly accept WF77 unavailable price rows, then continue reusable renderer/regression harness work."
            if status == "warning"
            else "Use the operator console/control cockpit to run the next service lifecycle slice."
            if OPERATOR_CONSOLE.exists()
            else "Continue PM handoff and next infrastructure slice after supplemental price, renderer regression, and scenario templates."
        ),
        "blocker_codes": [item.get("code") for item in blockers if isinstance(item, dict)],
        "proof": [
            rel(DEFAULT_STATE),
            selected_validation,
            selected_html,
            rel(WF77_SUPPLEMENTAL_PRICE_EVIDENCE),
            rel(WF77_BRIDGE),
            rel(RENDERER_REGRESSION),
            rel(SCENARIO_TEMPLATE_LIBRARY),
            rel(SQLITE_CONTROL_PLANE),
            rel(ARTIFACT_ONLY_PM_HANDOFF),
            rel(OPERATOR_CONSOLE),
        ],
        "authority_boundary": {key: False for key in AUTHORITY_FALSE_KEYS},
    }
    return {
        "schema": QUEUE_SCHEMA,
        "generated_at_utc": now,
        "status": "ok" if not critical else "blocked",
        "queue_owner": "WF75 local operator queue",
        "current_queue": [queue_item],
        "heartbeat_pickup": {
            "may_report_or_queue": True,
            "may_execute_queue_item": False,
            "must_not": [
                "advance phases inline",
                "deliver externally",
                "ingest real customer data",
                "mutate finance canon or portfolio",
                "submit paper/live/account actions",
            ],
        },
        "authority_boundary": {key: False for key in AUTHORITY_FALSE_KEYS},
    }


def build_movement(service_run: dict[str, Any], queue: dict[str, Any], now: str) -> dict[str, Any]:
    critical = any(isinstance(item, dict) and item.get("severity") == "critical" for item in as_list(service_run.get("blockers")))
    warning = service_run.get("status") == "warning"
    phase_c = "completed_with_warning" if warning else "completed"
    if critical:
        phase_c = "blocked"
    phase_d = "handoff_ready_with_warning" if warning else "handoff_ready"
    if critical:
        phase_d = "blocked"
    service_run_path = RUN_DIR / f"{service_run['service_run_id']}.json"
    selected = as_dict(service_run.get("selected_scenario"))
    selected_validation = selected.get("renderer_validation") or rel(CUSTOMER_EXPORT_VALIDATION)
    selected_html = selected.get("renderer_html") or rel(HTML_VALIDATION)
    return {
        "schema": MOVEMENT_SCHEMA,
        "generated_at_utc": now,
        "workflow": "WF75",
        "status": "warning" if warning else "ok",
        "phase_execution_status": {
            "C": {
                "status": phase_c,
                "proof": [rel(DEFAULT_STATE), rel(service_run_path)],
                "acceptance": [
                    "service-state schema exists",
                    "real_customer_data_present remains false",
                    "customer output remains external-delivery blocked",
                    "validator state is captured",
                ],
            },
            "D": {
                "status": phase_d,
                "proof": [
                    rel(DEFAULT_QUEUE),
                    rel(DEFAULT_MOVEMENT),
                    selected_validation,
                    selected_html,
                    rel(RENDERER_REGRESSION),
                    rel(SCENARIO_TEMPLATE_LIBRARY),
                    rel(SQLITE_CONTROL_PLANE),
                    rel(ARTIFACT_ONLY_PM_HANDOFF),
                ],
                "acceptance": [
                    "operator queue exists",
                    "movement transitions are validator-gated",
                    "clean customer-safe validation is required before brief readiness",
                    "renderer/export regression passes clean scenarios and seeded-bad failures",
                    "scenario-template library covers multiple anonymous service request shapes",
                    "heartbeat can queue review but cannot execute phases",
                ],
            },
        },
        "transitions": [
            {
                "from": "phase_b_price_freshness_bridge",
                "to": "phase_c_service_state_v0",
                "state": phase_c,
                "required_proof": [rel(WF77_BRIDGE), selected_validation, selected_html],
                "validator_command": f"python scripts\\wf75_service_state.py --scenario-id {as_dict(service_run.get('request')).get('request_id') or DEFAULT_SCENARIO_ID} --write --validate",
                "authority": "review_only_anonymous_scenario_state",
            },
            {
                "from": "phase_c_service_state_v0",
                "to": "phase_d_operator_queue_handoff",
                "state": phase_d,
                "required_proof": [rel(DEFAULT_STATE), rel(DEFAULT_QUEUE)],
                "validator_command": f"python scripts\\wf75_service_state.py --scenario-id {as_dict(service_run.get('request')).get('request_id') or DEFAULT_SCENARIO_ID} --write --validate",
                "authority": "queue_and_handoff_only_no_inline_execution",
            },
        ],
        "automation_policy": {
            "heartbeat_may_refresh": True,
            "heartbeat_may_queue_main_session": True,
            "heartbeat_may_execute_phase": False,
            "cron_may_refresh_artifact_only_after_job_card": True,
            "main_session_is_final_integrator": True,
            "helper_outputs_untrusted_until_main_verifies": True,
        },
        "current_queue_summary": {
            "queue_status": queue.get("status"),
            "queue_count": len(as_list(queue.get("current_queue"))),
            "next_action": as_dict(as_list(queue.get("current_queue"))[0] if as_list(queue.get("current_queue")) else {}).get("next_action"),
        },
        "authority_boundary": {key: False for key in AUTHORITY_FALSE_KEYS},
    }


def build_all(scenario_id: str = DEFAULT_SCENARIO_ID) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    now = utc_now()
    service_run = build_service_run(now, scenario_id)
    queue = build_queue(service_run, now)
    movement = build_movement(service_run, queue, now)
    state = {
        "schema": STATE_SCHEMA,
        "generated_at_utc": now,
        "workflow": "WF75",
        "status": service_run.get("status"),
        "phase": "C_and_D",
        "phase_name": "Service-state layer v0 plus automation movement handoff",
        "service_runs": [service_run],
        "current_service_run": service_run,
        "operator_queue_path": rel(DEFAULT_QUEUE),
        "movement_path": rel(DEFAULT_MOVEMENT),
        "authority_boundary": {key: False for key in AUTHORITY_FALSE_KEYS},
        "main_session_pickup": {
            "next_phase": "Phase E main-session intelligence pickup",
            "next_action": as_dict(as_list(queue.get("current_queue"))[0] if as_list(queue.get("current_queue")) else {}).get("next_action"),
            "residue": [
                "WF77 supplemental price evidence now clears the prior lane-excluded price rows without widening technical_refresh authority.",
                "SQLite WAL control-plane proof now exists for local Veritas queue/artifact coordination; JSON artifacts remain the source proof surfaces.",
                "Artifact-only PM handoff now exists for internal operator/PM pickup without public/customer/external authority.",
            ],
        },
    }
    state["validation"] = validate_state_bundle(state, queue, movement)
    queue["validation"] = validate_queue(queue)
    movement["validation"] = validate_movement(movement)
    return state, queue, movement, service_run


def validate_false_authority(boundary: Any, label: str, errors: list[str]) -> None:
    if not isinstance(boundary, dict):
        errors.append(f"{label}: missing authority_boundary")
        return
    for key in AUTHORITY_FALSE_KEYS:
        if boundary.get(key) is not False:
            errors.append(f"{label}: authority flag must be false: {key}")


def validate_service_run(run: dict[str, Any], errors: list[str], warnings: list[str]) -> None:
    if run.get("schema") != RUN_SCHEMA:
        errors.append("service_run schema mismatch")
    trust = as_dict(run.get("data_trust_state"))
    for key in (
        "real_customer_data_present",
        "customer_identity_present",
        "customer_portfolio_present",
        "suitability_or_risk_profile_present",
        "brokerage_or_account_data_present",
        "credential_data_present",
    ):
        if trust.get(key) is not False:
            errors.append(f"service_run data trust must be false: {key}")
    if as_dict(run.get("request")).get("fake_person_persona_used") is not False:
        errors.append("service_run must not use fake-person personas")
    validators = as_dict(run.get("validator_state"))
    if validators.get("customer_safe_export_validated") is not True:
        errors.append("customer-safe export must validate before Phase D handoff")
    if validators.get("external_delivery_ready") is not False:
        errors.append("external_delivery_ready must remain false")
    for artifact in as_list(run.get("artifact_inputs")):
        if isinstance(artifact, dict) and artifact.get("required") and not artifact.get("exists"):
            errors.append(f"missing required artifact: {artifact.get('path')}")
        if isinstance(artifact, dict) and artifact.get("exists") and not artifact.get("parseable_json"):
            errors.append(f"required artifact not parseable JSON: {artifact.get('path')}")
    for blocker in as_list(run.get("blockers")):
        if isinstance(blocker, dict) and blocker.get("severity") == "warning":
            warnings.append(str(blocker.get("code")))
    validate_false_authority(run.get("authority_boundary"), "service_run", errors)


def validate_state_bundle(state: dict[str, Any], queue: dict[str, Any], movement: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    if state.get("schema") != STATE_SCHEMA:
        errors.append("state schema mismatch")
    runs = as_list(state.get("service_runs"))
    if not runs:
        errors.append("state missing service_runs")
    for run in runs:
        if isinstance(run, dict):
            validate_service_run(run, errors, warnings)
        else:
            errors.append("service_runs entries must be objects")
    if queue.get("schema") != QUEUE_SCHEMA:
        errors.append("queue schema mismatch")
    if movement.get("schema") != MOVEMENT_SCHEMA:
        errors.append("movement schema mismatch")
    validate_false_authority(state.get("authority_boundary"), "state", errors)
    return {"status": "ok" if not errors else "error", "errors": errors, "warnings": sorted(set(warnings))}


def validate_queue(queue: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    if queue.get("schema") != QUEUE_SCHEMA:
        errors.append("queue schema mismatch")
    for item in as_list(queue.get("current_queue")):
        if not isinstance(item, dict):
            errors.append("queue item must be object")
            continue
        if item.get("inline_execution_allowed") is not False:
            errors.append(f"{item.get('queue_id')}: inline execution must be false")
        if item.get("external_delivery_allowed") is not False:
            errors.append(f"{item.get('queue_id')}: external delivery must be false")
        if item.get("customer_data_use_allowed") is not False:
            errors.append(f"{item.get('queue_id')}: customer data use must be false")
        validate_false_authority(item.get("authority_boundary"), f"queue:{item.get('queue_id')}", errors)
    validate_false_authority(queue.get("authority_boundary"), "queue", errors)
    return {"status": "ok" if not errors else "error", "errors": errors}


def validate_movement(movement: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    if movement.get("schema") != MOVEMENT_SCHEMA:
        errors.append("movement schema mismatch")
    policy = as_dict(movement.get("automation_policy"))
    if policy.get("heartbeat_may_execute_phase") is not False:
        errors.append("heartbeat_may_execute_phase must be false")
    if policy.get("main_session_is_final_integrator") is not True:
        errors.append("main session must remain final integrator")
    if not as_list(movement.get("transitions")):
        errors.append("movement transitions missing")
    validate_false_authority(movement.get("authority_boundary"), "movement", errors)
    return {"status": "ok" if not errors else "error", "errors": errors}


def write_all(state: dict[str, Any], queue: dict[str, Any], movement: dict[str, Any], service_run: dict[str, Any]) -> None:
    atomic_write_json(DEFAULT_STATE, state)
    atomic_write_json(DEFAULT_QUEUE, queue)
    atomic_write_json(DEFAULT_MOVEMENT, movement)
    atomic_write_json(RUN_DIR / f"{service_run['service_run_id']}.json", service_run)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build WF75 service-state and movement proof.")
    parser.add_argument("--scenario-id", default=DEFAULT_SCENARIO_ID, help="Anonymous WF75 scenario id to promote into current service-state.")
    parser.add_argument("--write", action="store_true", help="Write state, queue, movement, and run artifacts.")
    parser.add_argument("--validate", action="store_true", help="Validate generated or existing artifacts.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.write or not args.validate:
        state, queue, movement, service_run = build_all(args.scenario_id)
    else:
        state = as_dict(load_json_artifact(DEFAULT_STATE))
        queue = as_dict(load_json_artifact(DEFAULT_QUEUE))
        movement = as_dict(load_json_artifact(DEFAULT_MOVEMENT))
        service_run_id = as_dict(state.get("current_service_run")).get("service_run_id") or f"wf75-{args.scenario_id}"
        service_run = as_dict(load_json_artifact(RUN_DIR / f"{service_run_id}.json"))

    state_validation = validate_state_bundle(state, queue, movement)
    queue_validation = validate_queue(queue)
    movement_validation = validate_movement(movement)
    status = "ok" if all(v["status"] == "ok" for v in (state_validation, queue_validation, movement_validation)) else "error"

    if args.write:
        state["validation"] = state_validation
        queue["validation"] = queue_validation
        movement["validation"] = movement_validation
        write_all(state, queue, movement, service_run)

    summary = {
        "status": status,
        "state": rel(DEFAULT_STATE),
        "queue": rel(DEFAULT_QUEUE),
        "movement": rel(DEFAULT_MOVEMENT),
        "service_run": rel(RUN_DIR / f"{service_run['service_run_id']}.json") if service_run.get("service_run_id") else None,
        "state_validation": state_validation,
        "queue_validation": queue_validation,
        "movement_validation": movement_validation,
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    if args.validate and status != "ok":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
