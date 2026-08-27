#!/usr/bin/env python3
"""Score WF75 internal/service-led prototype readiness.

This scorecard measures only the local internal prototype: anonymous service
state, reproducible runs, validated deliverables, scenario regressions,
operator review state, training assets, and manual gates. It does not measure
or grant customer delivery, public launch, legal/compliance readiness, source
licensing, advice, brokerage/account action, execution, or owner approval.
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

SCHEMA = "veritas.wf75.internal_prototype_readiness.v1"
DEFAULT_OUT = TMP / "wf75-internal-prototype-readiness.json"
DEFAULT_MD = TMP / "wf75-internal-prototype-readiness.md"

SOURCE_PATHS = {
    "service_state": TMP / "wf75-service-state-current.json",
    "operator_console": TMP / "wf75-operator-console.json",
    "deliverable_packager": TMP / "wf75-deliverable-packager.json",
    "operator_delivery_gate": TMP / "wf75-operator-delivery-gate.json",
    "scenario_matrix": TMP / "wf75-scenario-regression-matrix.json",
    "operator_review_state": TMP / "wf75-operator-review-state.json",
    "run_loop": TMP / "wf75-internal-service-run-loop.json",
    "training_manifest": ROOT / "training" / "wf75-academy" / "wf75-academy-manifest.json",
    "finance_delivery_series": TMP / "finance-delivery-series.json",
}

CATEGORY_WEIGHTS = {
    "service_state_and_console": 15,
    "deliverable_contracts": 15,
    "safety_and_regression_matrix": 15,
    "operator_gate_and_review_state": 15,
    "one_command_run_loop": 15,
    "training_and_runbook_assets": 10,
    "manual_gate_and_authority_boundary": 15,
}

AUTHORITY_BOUNDARY = {
    "internal_service_led_prototype_scorecard": True,
    "customer_external_delivery_allowed": False,
    "public_launch_allowed": False,
    "real_customer_data_allowed": False,
    "legal_compliance_source_licensing_ready": False,
    "source_licensing_assumed": False,
    "personalized_advice_allowed": False,
    "advice_execution_brokerage_account_allowed": False,
    "paper_or_live_execution_allowed": False,
    "portfolio_or_canon_mutation_allowed": False,
    "cron_restart_allowed": False,
    "owner_approval_inferred": False,
}

REQUIRED_FALSE_AUTHORITY = [
    key for key, value in AUTHORITY_BOUNDARY.items() if value is False
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


def validation_status(payload: dict[str, Any]) -> str | None:
    validation = as_dict(payload.get("validation"))
    return validation.get("status") or payload.get("validation_status")


def load_sources() -> dict[str, dict[str, Any]]:
    sources: dict[str, dict[str, Any]] = {}
    for key, path in SOURCE_PATHS.items():
        payload = load_json_artifact(path)
        sources[key] = payload if isinstance(payload, dict) else {}
    return sources


def source_probe(key: str, payload: dict[str, Any]) -> dict[str, Any]:
    path = SOURCE_PATHS[key]
    return {
        "key": key,
        "path": rel(path),
        "exists": path.exists(),
        "parseable_json": bool(payload),
        "status": payload.get("status") or as_dict(payload.get("summary")).get("status") or "missing",
        "validation_status": validation_status(payload),
        "generated_at_utc": payload.get("generated_at_utc"),
    }


def category(category_id: str, earned: int, evidence: list[str], blockers: list[str]) -> dict[str, Any]:
    weight = CATEGORY_WEIGHTS[category_id]
    return {
        "category_id": category_id,
        "weight": weight,
        "earned": max(0, min(weight, earned)),
        "status": "complete" if earned >= weight and not blockers else "partial" if earned > 0 else "blocked",
        "evidence": evidence,
        "blockers": blockers,
    }


def deliverable_statuses(packager: dict[str, Any]) -> dict[str, str]:
    plan = as_dict(packager.get("plan"))
    statuses: dict[str, str] = {}
    for row in as_list(plan.get("deliverables")):
        if isinstance(row, dict) and row.get("id"):
            statuses[str(row["id"])] = str(row.get("status") or "")
    return statuses


def service_state_category(sources: dict[str, dict[str, Any]]) -> dict[str, Any]:
    service = sources["service_state"]
    console = sources["operator_console"]
    ok = (
        service.get("status") == "ok"
        and validation_status(service) == "ok"
        and console.get("status") == "ready"
        and validation_status(console) == "ok"
    )
    blockers = [] if ok else ["service state or operator console is not clean"]
    evidence = [rel(SOURCE_PATHS["service_state"]), rel(SOURCE_PATHS["operator_console"])]
    return category("service_state_and_console", 15 if ok else 8 if service or console else 0, evidence, blockers)


def deliverable_category(sources: dict[str, dict[str, Any]]) -> dict[str, Any]:
    packager = sources["deliverable_packager"]
    statuses = deliverable_statuses(packager)
    required = {
        "internal_pm_readiness_pdf",
        "customer_safe_research_pdf",
        "internal_operator_excel",
        "customer_safe_excel_export",
        "operator_delivery_gate_packet",
    }
    implemented = [key for key in required if statuses.get(key, "").startswith("implemented")]
    clean = packager.get("status") == "ok" and validation_status(packager) == "ok" and len(implemented) == len(required)
    blockers = [] if clean else [f"implemented deliverables {len(implemented)}/{len(required)}"]
    earned = 15 if clean else int(15 * len(implemented) / len(required))
    return category("deliverable_contracts", earned, [rel(SOURCE_PATHS["deliverable_packager"])], blockers)


def safety_category(sources: dict[str, dict[str, Any]]) -> dict[str, Any]:
    matrix = sources["scenario_matrix"]
    seeded_bad = as_dict(matrix.get("seeded_bad") or matrix.get("seeded_bad_fail_closed"))
    json_validation = as_dict(seeded_bad.get("json_validation"))
    markdown_validation = as_dict(seeded_bad.get("markdown_validation"))
    clean_scenarios = [
        row for row in as_list(matrix.get("clean_scenarios") or matrix.get("clean_results"))
        if isinstance(row, dict)
    ]
    clean_count = int(matrix.get("clean_scenario_count") or len(clean_scenarios))
    clean_failed_count = int(
        matrix.get("clean_failed_count")
        if matrix.get("clean_failed_count") is not None
        else sum(
            1
            for row in clean_scenarios
            if row.get("actual_status") not in {"ok", None}
            or row.get("status") not in {"ok", None}
            or row.get("status_match") is False
        )
    )
    clean = (
        matrix.get("status") == "ok"
        and validation_status(matrix) == "ok"
        and clean_count >= 8
        and clean_failed_count == 0
        and (
            seeded_bad.get("json_validation_status") == "error"
            or json_validation.get("actual_status") == "error"
        )
        and (
            seeded_bad.get("markdown_validation_status") == "error"
            or markdown_validation.get("actual_status") == "error"
        )
        and seeded_bad.get("fail_closed", True) is True
    )
    blockers = [] if clean else ["scenario regression matrix is missing or not clean"]
    earned = 15 if clean else 8 if sources["operator_delivery_gate"].get("status") == "ready_for_operator_review_external_blocked" else 0
    return category("safety_and_regression_matrix", earned, [rel(SOURCE_PATHS["scenario_matrix"])], blockers)


def operator_review_category(sources: dict[str, dict[str, Any]]) -> dict[str, Any]:
    gate = sources["operator_delivery_gate"]
    review = sources["operator_review_state"]
    clean = (
        gate.get("status") == "ready_for_operator_review_external_blocked"
        and validation_status(gate) == "ok"
        and review.get("status") in {
            "ready_for_internal_operator_decision",
            "ready_for_internal_operator_review_external_blocked",
        }
        and validation_status(review) == "ok"
        and review.get("external_delivery_status") in {
            "blocked",
            "blocked_internal_review_only",
        }
    )
    blockers = [] if clean else ["operator delivery gate or review state is not complete"]
    earned = 15 if clean else 10 if gate.get("status") == "ready_for_operator_review_external_blocked" else 0
    return category(
        "operator_gate_and_review_state",
        earned,
        [rel(SOURCE_PATHS["operator_delivery_gate"]), rel(SOURCE_PATHS["operator_review_state"])],
        blockers,
    )


def run_loop_category(sources: dict[str, dict[str, Any]]) -> dict[str, Any]:
    run_loop = sources["run_loop"]
    commands = [
        row for row in as_list(run_loop.get("commands"))
        if isinstance(row, dict)
    ]
    clean = (
        run_loop.get("status") == "ok"
        and validation_status(run_loop) == "ok"
        and commands
        and all(row.get("status") == "ok" for row in commands)
    )
    blockers = [] if clean else ["one-command service run loop is missing or not clean"]
    return category("one_command_run_loop", 15 if clean else 0, [rel(SOURCE_PATHS["run_loop"])], blockers)


def training_category(sources: dict[str, dict[str, Any]]) -> dict[str, Any]:
    training = sources["training_manifest"]
    clean = training.get("status") == "ready" and validation_status(training) == "ok"
    blockers = [] if clean else ["WF75 Academy/training manifest is not ready"]
    return category("training_and_runbook_assets", 10 if clean else 0, [rel(SOURCE_PATHS["training_manifest"])], blockers)


def authority_category(sources: dict[str, dict[str, Any]]) -> dict[str, Any]:
    finance = sources["finance_delivery_series"]
    authority = as_dict(finance.get("authority_boundary"))
    gate = as_dict(as_dict(finance.get("delivery_program")).get("saas_deliverable_gate"))
    clean = (
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
    blockers = [] if clean else ["manual finance-delivery gate or authority boundary is not clean"]
    return category(
        "manual_gate_and_authority_boundary",
        15 if clean else 0,
        [rel(SOURCE_PATHS["finance_delivery_series"])],
        blockers,
    )


def readiness_band(score: int) -> str:
    if score >= 100:
        return "complete_internal_prototype"
    if score >= 90:
        return "near_complete_internal_prototype"
    if score >= 80:
        return "strong_internal_prototype"
    if score >= 70:
        return "working_internal_prototype"
    return "incomplete_internal_prototype"


def build_payload() -> dict[str, Any]:
    sources = load_sources()
    categories = [
        service_state_category(sources),
        deliverable_category(sources),
        safety_category(sources),
        operator_review_category(sources),
        run_loop_category(sources),
        training_category(sources),
        authority_category(sources),
    ]
    score = sum(int(row.get("earned") or 0) for row in categories)
    blockers = [
        f"{row['category_id']}: {blocker}"
        for row in categories
        for blocker in as_list(row.get("blockers"))
    ]
    remaining_to_100 = [
        {
            "category_id": row["category_id"],
            "remaining_points": int(row["weight"]) - int(row["earned"]),
            "blockers": row.get("blockers", []),
        }
        for row in categories
        if int(row["earned"]) < int(row["weight"])
    ]
    payload = {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "workflow": "WF75",
        "status": "ok" if score >= 90 and not any("authority" in item.lower() for item in blockers) else "incomplete",
        "readiness_scope": "internal_service_led_prototype_only",
        "score": score,
        "max_score": 100,
        "readiness_band": readiness_band(score),
        "categories": categories,
        "remaining_to_100": remaining_to_100,
        "source_status": {key: source_probe(key, sources[key]) for key in SOURCE_PATHS},
        "authority_boundary": AUTHORITY_BOUNDARY,
        "external_readiness": {
            "customer_external_delivery": "blocked",
            "public_launch": "blocked",
            "real_customer_data": "blocked",
            "source_licensing": "not_ready",
            "legal_compliance": "not_ready",
        },
        "next_safe_action": (
            "Finish any incomplete internal categories, then keep WF75 as an internal/service-led prototype. "
            "External/customer use remains a separate future gate."
        ),
    }
    payload["validation"] = validate_payload(payload)
    if payload["validation"]["status"] != "ok":
        payload["status"] = "error"
    return payload


def validate_payload(payload: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    if payload.get("schema") != SCHEMA:
        errors.append("schema_mismatch")
    if sum(CATEGORY_WEIGHTS.values()) != 100:
        errors.append("category_weights_do_not_total_100")
    categories = as_list(payload.get("categories"))
    if len(categories) != len(CATEGORY_WEIGHTS):
        errors.append("category_count_mismatch")
    score = payload.get("score")
    if not isinstance(score, int) or score < 0 or score > 100:
        errors.append("score_out_of_bounds")
    boundary = as_dict(payload.get("authority_boundary"))
    if boundary.get("internal_service_led_prototype_scorecard") is not True:
        errors.append("internal_service_led_prototype_scorecard_not_true")
    for key in REQUIRED_FALSE_AUTHORITY:
        if boundary.get(key) is not False:
            errors.append(f"authority_{key}_not_false")
    external = as_dict(payload.get("external_readiness"))
    for key in ("customer_external_delivery", "public_launch", "real_customer_data"):
        if external.get(key) != "blocked":
            errors.append(f"external_{key}_not_blocked")
    return {"status": "ok" if not errors else "error", "errors": errors}


def render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# WF75 Internal Prototype Readiness",
        "",
        f"- Generated: `{payload.get('generated_at_utc')}`",
        f"- Scope: `{payload.get('readiness_scope')}`",
        f"- Score: `{payload.get('score')}/{payload.get('max_score')}`",
        f"- Band: `{payload.get('readiness_band')}`",
        f"- Status: `{payload.get('status')}`",
        "",
        "## Categories",
        "",
        "| Category | Earned | Weight | Status | Blockers |",
        "|---|---:|---:|---|---|",
    ]
    for row in as_list(payload.get("categories")):
        if not isinstance(row, dict):
            continue
        blockers = "; ".join(str(item) for item in as_list(row.get("blockers")))
        lines.append(
            f"| {row.get('category_id')} | {row.get('earned')} | {row.get('weight')} | {row.get('status')} | {blockers} |"
        )
    lines.extend(["", "## Remaining To 100", ""])
    remaining = as_list(payload.get("remaining_to_100"))
    if remaining:
        for row in remaining:
            if isinstance(row, dict):
                lines.append(f"- `{row.get('category_id')}`: {row.get('remaining_points')} points remaining")
    else:
        lines.append("- No internal prototype categories remain incomplete.")
    lines.extend(["", "## External Readiness", ""])
    for key, value in as_dict(payload.get("external_readiness")).items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(["", "## Authority Boundary", ""])
    for key, value in as_dict(payload.get("authority_boundary")).items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(["", "## Next Safe Action", "", str(payload.get("next_safe_action") or ""), ""])
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Score WF75 internal/service-led prototype readiness.")
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
        atomic_write_json(out, payload)
        atomic_write_text(md_out, render_markdown(payload))
    errors = as_list(as_dict(payload.get("validation")).get("errors"))
    print(
        "status={status} score={score}/{max_score} band={band} errors={errors}".format(
            status=payload.get("status"),
            score=payload.get("score"),
            max_score=payload.get("max_score"),
            band=payload.get("readiness_band"),
            errors=len(errors),
        )
    )
    return 0 if (not args.validate or not errors) else 2


if __name__ == "__main__":
    raise SystemExit(main())
