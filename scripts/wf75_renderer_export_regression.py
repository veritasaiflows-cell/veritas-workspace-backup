#!/usr/bin/env python3
"""Run WF75 renderer/export regression over anonymous scenarios.

The harness proves repeatable local JSON/Markdown/HTML export and validator
behavior. It is internal proof only: no real customer data, no external
delivery, no legal/compliance/source-readiness claim, and no execution
authority.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, atomic_write_text, load_json_artifact
from retail_saas_customer_output_validator import validate_payload, validate_rendered_text
from retail_saas_fixture_demo import build_payload, customer_export_document, render_md, write_seeded_bad, write_seeded_bad_markdown
from retail_saas_html_report import render_html
from retail_truth_safety import export_guard, render_internal_route
from veritas_question_router import build_route
from wf75_scenario_template_library import DEFAULT_OUT as TEMPLATE_LIBRARY, build_library

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
RUN_DIR = TMP / "wf75-renderer-regression"
DEFAULT_OUT = TMP / "wf75-renderer-export-regression.json"

SCHEMA = "veritas.wf75.renderer_export_regression.v1"

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
}

ROUTER_RENDERER_PILOTS = [
    ("DASH", "https://ir.doordash.com/"),
    ("TSM", "https://investor.tsmc.com/english"),
    ("AVGO", "https://investors.broadcom.com/"),
    ("ALLE", "https://investor.allegion.com/"),
    ("AOS", "https://investor.aosmith.com/"),
]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def safe_name(value: str) -> str:
    return "".join(ch if ch.isalnum() or ch in {"-", "_"} else "-" for ch in value.lower()).strip("-")


def apply_scenario(payload: dict[str, Any], scenario: dict[str, Any]) -> dict[str, Any]:
    payload = dict(payload)
    export = dict(payload["customer_export"])
    request = dict(export.get("anonymous_service_request") or {})
    request.update(
        {
            "request_id": scenario["scenario_id"],
            "request_type": scenario["request_type"],
            "audience_segment": scenario["audience_segment"],
            "scenario": scenario["scenario"],
            "personal_data_used": False,
            "suitability_data_used": False,
            "portfolio_data_used": False,
            "watchlist_intent_is_personalized": False,
            "ticker_set": scenario["ticker_set"],
        }
    )
    export["anonymous_service_request"] = request
    export["brief_title"] = "Anonymous Watchlist Intelligence Brief"
    export["fixture_notice"] = (
        "Internal anonymous service request scenario using real public ticker evidence where available. "
        "No real customer data, personal identity, portfolio, or suitability data is used."
    )
    export["scenario_context"] = {
        "scenario_id": scenario["scenario_id"],
        "coverage_intent": scenario["coverage_intent"],
        "fake_person_persona_used": False,
    }
    payload["customer_export"] = export
    payload["internal_input_summary"] = dict(payload.get("internal_input_summary") or {})
    payload["internal_input_summary"]["scenario_id"] = scenario["scenario_id"]
    return payload


def validate_customer_and_rendered(customer_export: dict[str, Any], md: str, html: str) -> dict[str, Any]:
    validation = validate_payload(customer_export)
    validation["findings"].extend(validate_rendered_text(md, "markdown"))
    validation["findings"].extend(validate_rendered_text(html, "html"))
    validation["critical_count"] = sum(1 for finding in validation["findings"] if finding["severity"] == "critical")
    validation["warning_count"] = sum(1 for finding in validation["findings"] if finding["severity"] == "warning")
    validation["status"] = "ok" if validation["critical_count"] == 0 else "error"
    return validation


def run_scenario(scenario: dict[str, Any]) -> dict[str, Any]:
    scenario_id = scenario["scenario_id"]
    base = build_payload(list(scenario["ticker_set"]))
    payload = apply_scenario(base, scenario)
    customer_export = customer_export_document(payload)
    md = render_md(payload)
    html = render_html(customer_export)
    validation = validate_customer_and_rendered(customer_export, md, html)

    stem = safe_name(scenario_id)
    json_path = RUN_DIR / f"{stem}.json"
    customer_path = RUN_DIR / f"{stem}.customer-export.json"
    md_path = RUN_DIR / f"{stem}.md"
    html_path = RUN_DIR / f"{stem}.html"
    validation_path = RUN_DIR / f"{stem}.validation.json"

    atomic_write_json(json_path, payload)
    atomic_write_json(customer_path, customer_export)
    atomic_write_text(md_path, md)
    atomic_write_text(html_path, html)
    atomic_write_json(validation_path, validation)

    return {
        "scenario_id": scenario_id,
        "status": validation["status"],
        "ticker_set": scenario["ticker_set"],
        "expected_validator_outcome": scenario.get("expected_validator_outcome"),
        "critical_count": validation["critical_count"],
        "warning_count": validation["warning_count"],
        "artifacts": {
            "fixture_json": rel(json_path),
            "customer_export": rel(customer_path),
            "markdown": rel(md_path),
            "html": rel(html_path),
            "validation": rel(validation_path),
        },
    }


def run_seeded_bad() -> dict[str, Any]:
    clean = build_payload(["ETN", "NVDA", "VRT"])
    json_path = RUN_DIR / "seeded-bad.json"
    validation_path = RUN_DIR / "seeded-bad.validation.json"
    md_path = RUN_DIR / "seeded-bad.md"
    md_validation_path = RUN_DIR / "seeded-bad-md.validation.json"
    validation = write_seeded_bad(clean, json_path, validation_path)
    md_validation = write_seeded_bad_markdown(md_path, md_validation_path)
    return {
        "scenario_id": "seeded-bad-claim-and-leak-fixture",
        "expected_validator_outcome": "error",
        "json_validation_status": validation["status"],
        "markdown_validation_status": md_validation["status"],
        "critical_count": validation.get("critical_count", 0) + md_validation.get("critical_count", 0),
        "artifacts": {
            "fixture_json": rel(json_path),
            "validation": rel(validation_path),
            "markdown": rel(md_path),
            "markdown_validation": rel(md_validation_path),
        },
    }


def build_router_renderer_pilot(
    route_builder=build_route,
    now: datetime | None = None,
) -> dict[str, Any]:
    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    as_of = now.replace(microsecond=0).isoformat().replace("+00:00", "Z")
    rows: list[dict[str, Any]] = []
    for ticker, source_url in ROUTER_RENDERER_PILOTS:
        route = route_builder(f"What is the internal evidence readiness for {ticker}?")
        claim = {
            "claim_type": "routing_state",
            "text": "Issuer investor-relations endpoint is queued for source-open review; no finance recommendation is rendered.",
            "source_label": "issuer_ir_endpoint_fixture_unfetched",
            "source_url": source_url,
            "as_of_utc": as_of,
        }
        rendered = render_internal_route(ticker=ticker, route=route, claims=[claim], now=now)
        internal = export_guard(rendered, "internal_state")
        external = export_guard(rendered, "customer")
        rows.append({
            "ticker": ticker,
            "question_class": route.get("question_class"),
            "route_status": rendered.get("route_status"),
            "audience": rendered.get("audience"),
            "source_labels_present": rendered.get("source_labels_present"),
            "freshness_labels_present": rendered.get("freshness_labels_present"),
            "recommendation_allowed": rendered.get("recommendation_allowed"),
            "decision_grade": rendered.get("decision_grade"),
            "internal_export_allowed": internal.get("allowed"),
            "external_export_blocked": external.get("allowed") is False and external.get("serialized") is False,
            "external_block_reasons": external.get("reasons"),
        })

    base_route = route_builder("What is the internal evidence readiness for DASH?")
    expired_claim = {
        "claim_type": "routing_state",
        "text": "Expired routing state fixture.",
        "source_label": "issuer_ir_endpoint_fixture_unfetched",
        "source_url": "https://ir.doordash.com/",
        "as_of_utc": "2000-01-01T00:00:00Z",
    }
    expired_render = render_internal_route(ticker="DASH", route=base_route, claims=[expired_claim], now=now)
    leaked_claim = dict(expired_claim)
    leaked_claim.update({"text": r"Read C:\private\workspace\tmp\proof.json", "as_of_utc": as_of})
    leaked_render = render_internal_route(ticker="DASH", route=base_route, claims=[leaked_claim], now=now)
    wrong_audience = render_internal_route(
        ticker="DASH",
        route=base_route,
        claims=[dict(expired_claim, as_of_utc=as_of)],
        now=now,
    )
    wrong_audience["audience"] = "customer"
    seeded_bad = {
        "expired_claim_blocked": export_guard(expired_render, "internal_state").get("allowed") is False,
        "internal_path_leak_blocked": export_guard(leaked_render, "internal_state").get("allowed") is False,
        "wrong_audience_blocked": export_guard(wrong_audience, "internal_state").get("allowed") is False,
        "external_target_blocked": export_guard(wrong_audience, "public").get("serialized") is False,
    }
    clean = [
        row for row in rows
        if row["internal_export_allowed"] is True
        and row["external_export_blocked"] is True
        and row["source_labels_present"] is True
        and row["freshness_labels_present"] is True
        and row["recommendation_allowed"] is False
        and row["decision_grade"] is False
    ]
    return {
        "audience": "internal_anonymous_service_state",
        "pilot_tickers": [row[0] for row in ROUTER_RENDERER_PILOTS],
        "pilot_count": len(rows),
        "clean_internal_case_count": len(clean),
        "rows": rows,
        "seeded_bad": seeded_bad,
        "all_seeded_bad_blocked": all(seeded_bad.values()),
        "customer_or_external_delivery_allowed": False,
    }


def load_library(path: Path) -> dict[str, Any]:
    payload = load_json_artifact(path)
    if isinstance(payload, dict) and isinstance(payload.get("templates"), list):
        return payload
    return build_library()


def validate_payload_result(payload: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    if payload.get("clean_scenario_count", 0) < 8:
        errors.append("clean_scenario_count_below_8")
    if payload.get("clean_failed_count") != 0:
        errors.append("clean_scenario_validation_failed")
    seeded = payload.get("seeded_bad") or {}
    if seeded.get("json_validation_status") != "error" or seeded.get("markdown_validation_status") != "error":
        errors.append("seeded_bad_did_not_fail")
    for key, value in AUTHORITY_BOUNDARY.items():
        if payload.get("authority_boundary", {}).get(key) is not value:
            errors.append(f"authority_{key}_unexpected")
    boundary = payload.get("router_renderer_export_guard") or {}
    if boundary.get("pilot_count", 0) < 3:
        errors.append("router_renderer_pilot_count_below_3")
    if boundary.get("clean_internal_case_count") != boundary.get("pilot_count"):
        errors.append("router_renderer_internal_case_failed")
    if boundary.get("all_seeded_bad_blocked") is not True:
        errors.append("router_renderer_seeded_bad_not_blocked")
    if boundary.get("customer_or_external_delivery_allowed") is not False:
        errors.append("router_renderer_external_authority_widened")
    return {"status": "ok" if not errors else "error", "errors": errors}


def build_regression(args: argparse.Namespace) -> dict[str, Any]:
    RUN_DIR.mkdir(parents=True, exist_ok=True)
    library = load_library(args.template_library)
    scenarios = [row for row in library.get("templates", []) if isinstance(row, dict)]
    clean_results = [run_scenario(scenario) for scenario in scenarios]
    seeded_bad = run_seeded_bad()
    router_renderer = build_router_renderer_pilot()
    clean_failed = [row for row in clean_results if row["status"] != "ok"]
    payload: dict[str, Any] = {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "ok" if not clean_failed else "blocked",
        "template_library": rel(args.template_library),
        "run_dir": rel(RUN_DIR),
        "clean_scenario_count": len(clean_results),
        "clean_failed_count": len(clean_failed),
        "clean_results": clean_results,
        "seeded_bad": seeded_bad,
        "router_renderer_export_guard": router_renderer,
        "authority_boundary": AUTHORITY_BOUNDARY,
    }
    payload["validation"] = validate_payload_result(payload)
    if payload["validation"]["status"] != "ok":
        payload["status"] = "error"
    return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run WF75 renderer/export regression.")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--template-library", type=Path, default=TEMPLATE_LIBRARY)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    for attr in ("template_library", "out"):
        path = getattr(args, attr)
        if not path.is_absolute():
            setattr(args, attr, ROOT / path)
    payload = build_regression(args)
    if args.write:
        atomic_write_json(args.out, payload)
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if (payload["validation"]["status"] == "ok" or not args.validate) else 1


if __name__ == "__main__":
    raise SystemExit(main())
