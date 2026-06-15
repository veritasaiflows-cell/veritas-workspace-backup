#!/usr/bin/env python3
"""Assemble the review-only finance predictive learning loop.

This is an integration surface over existing recommendation/outcome artifacts
and the new history/lookback/calibration components. It does not train a model,
rank capital deployment, create owner cards, mutate canon/portfolio state, or
authorize paper/live execution.
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

HISTORY_LEDGER = TMP / "finance-recommendation-history-ledger.json"
LOOKBACK_ENGINE = TMP / "finance-recommendation-lookback-engine.json"
CALIBRATION_REPORT = TMP / "finance-recommendation-regression-calibration.json"
PERFORMANCE_DIGEST = TMP / "finance-decision-performance-digest.json"
WF55_CURRENT = TMP / "recommendation-outcome-ledger-current.json"
WF78_REVIEW = TMP / "wf78-deployment-readiness-human-review.json"
WF85_READINESS = TMP / "wf85-market-hours-refresh-readiness.json"

DEFAULT_JSON = TMP / "finance-predictive-learning-loop.json"
DEFAULT_MD = TMP / "finance-predictive-learning-loop.md"

SCHEMA = "veritas.finance_predictive_learning_loop.v1"

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "learning_loop_integration_only": True,
    "historical_analysis_only": True,
    "model_training_enabled": False,
    "predictive_skill_claim_allowed_now": False,
    "capital_deployment_approved": False,
    "trade_or_execution_approved": False,
    "owner_cards_created": False,
    "approval_cards_created": False,
    "order_artifacts_created": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "money_movement_allowed": False,
    "portfolio_or_canon_mutation_allowed": False,
    "owner_approval_inferred": False,
}

FORBIDDEN_TRUE_KEYS = {
    "model_training_enabled",
    "predictive_skill_claim_allowed_now",
    "capital_deployment_approved",
    "trade_or_execution_approved",
    "owner_cards_created",
    "approval_cards_created",
    "order_artifacts_created",
    "paper_or_live_execution_allowed",
    "brokerage_or_account_action_allowed",
    "money_movement_allowed",
    "portfolio_or_canon_mutation_allowed",
    "owner_approval_inferred",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def authority_true_paths(value: Any, prefix: str = "") -> list[str]:
    paths: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            child = f"{prefix}.{key}" if prefix else str(key)
            if key in FORBIDDEN_TRUE_KEYS and item is True:
                paths.append(child)
            paths.extend(authority_true_paths(item, child))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            paths.extend(authority_true_paths(item, f"{prefix}[{index}]"))
    return paths


def summarize_component(name: str, path: Path) -> dict[str, Any]:
    payload = load_json_artifact(path)
    parsed = isinstance(payload, dict)
    summary = as_dict(payload.get("summary")) if parsed else {}
    validation = as_dict(payload.get("validation")) if parsed else {}
    authority = as_dict(payload.get("authority_boundary") or payload.get("authority_flags")) if parsed else {}
    return {
        "name": name,
        "path": rel(path),
        "exists": path.exists(),
        "parseable_json": parsed,
        "schema": payload.get("schema") if parsed else None,
        "generated_at_utc": payload.get("generated_at_utc") if parsed else None,
        "status": payload.get("status") if parsed else "missing",
        "classification": payload.get("classification") if parsed else None,
        "summary": summary,
        "validation_status": validation.get("status"),
        "authority_true_paths": authority_true_paths(payload) if parsed else [],
        "authority_boundary": authority,
    }


def component_ready(component: dict[str, Any]) -> bool:
    if component.get("exists") is not True or component.get("parseable_json") is not True:
        return False
    if component.get("authority_true_paths"):
        return False
    status = str(component.get("status") or "")
    validation_status = str(component.get("validation_status") or "")
    if status in {"critical", "error", "blocked"}:
        return False
    if validation_status in {"critical", "error"}:
        return False
    return True


def build_payload(paths: dict[str, Path] | None = None) -> dict[str, Any]:
    artifact_paths = paths or {
        "history_ledger": HISTORY_LEDGER,
        "lookback_engine": LOOKBACK_ENGINE,
        "calibration_report": CALIBRATION_REPORT,
        "performance_digest": PERFORMANCE_DIGEST,
        "wf55_current": WF55_CURRENT,
        "wf78_review": WF78_REVIEW,
        "wf85_readiness": WF85_READINESS,
    }
    components = [summarize_component(name, path) for name, path in artifact_paths.items()]
    required_names = {"history_ledger", "lookback_engine", "calibration_report"}
    required = [component for component in components if component.get("name") in required_names]
    ready_required = [component for component in required if component_ready(component)]
    authority_drift_paths = []
    for component in components:
        for drift in as_list(component.get("authority_true_paths")):
            authority_drift_paths.append(f"{component.get('name')}:{drift}")

    missing_required = [component.get("name") for component in required if not component_ready(component)]
    status = "ready_review_only" if not missing_required and not authority_drift_paths else "pending_components"

    return {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": status,
        "purpose": "Integrate historical ledger, lookback metrics, and conservative calibration into a review-only learning loop.",
        "component_summary": {
            "component_count": len(components),
            "required_component_count": len(required),
            "ready_required_component_count": len(ready_required),
            "missing_or_unready_required_components": missing_required,
            "authority_drift_path_count": len(authority_drift_paths),
        },
        "components": components,
        "decision_contract": {
            "allowed_uses": [
                "explain which recommendation signals have historical support",
                "identify sparse or weak evidence before future recommendation review",
                "prioritize evidence repair and review-only learning-loop improvements",
                "show historical analogs and confidence penalties when enough data exists",
            ],
            "forbidden_uses": [
                "capital deployment approval",
                "paper or live trade execution",
                "brokerage or account action",
                "portfolio, canon, cash, sizing, or risk-rule mutation",
                "owner approval inference",
                "predictive skill or model-performance claim before mature walk-forward proof",
            ],
            "minimum_before_score_adjustment": {
                "requires_walk_forward_split": True,
                "requires_mature_forward_windows": True,
                "requires_source_freshness_at_recommendation_time": True,
                "requires_plain_english_explanation": True,
                "requires_human_review_for_capital_relevance": True,
            },
        },
        "next_safe_actions": [
            "Finish any missing required components.",
            "Run history, lookback, calibration, then this integration script.",
            "Use results for review triage only until mature walk-forward evidence supports stronger claims.",
        ],
        "authority_boundary": AUTHORITY_BOUNDARY.copy(),
    }


def validate_payload(payload: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    boundary = as_dict(payload.get("authority_boundary"))
    for key, expected in AUTHORITY_BOUNDARY.items():
        if boundary.get(key) is not expected:
            errors.append(f"authority_boundary_{key}_not_{str(expected).lower()}")
    drift = authority_true_paths(payload)
    if drift:
        errors.append("authority_drift_detected")
    summary = as_dict(payload.get("component_summary"))
    missing = as_list(summary.get("missing_or_unready_required_components"))
    if missing:
        warnings.append("required_components_pending:" + ",".join(str(item) for item in missing))
    return {
        "status": "error" if errors else "warning" if warnings else "ok",
        "errors": errors,
        "warnings": warnings,
        "authority_drift_paths": drift,
    }


def render_md(payload: dict[str, Any]) -> str:
    summary = as_dict(payload.get("component_summary"))
    lines = [
        "# Finance Predictive Learning Loop",
        "",
        f"- Generated: {payload.get('generated_at_utc')}",
        f"- Status: {payload.get('status')}",
        f"- Required components ready: {summary.get('ready_required_component_count')} / {summary.get('required_component_count')}",
        f"- Authority drift paths: {summary.get('authority_drift_path_count')}",
        "",
        "## Components",
    ]
    for component in as_list(payload.get("components")):
        lines.append(
            f"- {component.get('name')}: exists={component.get('exists')} parseable={component.get('parseable_json')} "
            f"status={component.get('status')} validation={component.get('validation_status')}"
        )
    lines.extend([
        "",
        "## Decision Contract",
        "",
        "- Review-only historical learning surface.",
        "- No owner approval, capital deployment, portfolio/canon mutation, or paper/live execution authority.",
        "- No predictive skill claim until mature walk-forward proof exists.",
    ])
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build the review-only finance predictive learning-loop integration surface")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--write-md", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--json-out", default=str(DEFAULT_JSON))
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args(argv)

    payload = build_payload()
    validation = validate_payload(payload)
    payload["validation"] = validation

    out = Path(args.json_out)
    if args.write:
        atomic_write_json(out, payload)
        if args.write_md:
            atomic_write_text(out.with_suffix(".md"), render_md(payload))

    if not args.quiet:
        summary = as_dict(payload.get("component_summary"))
        print(
            f"status={payload.get('status')} validation={validation.get('status')} "
            f"ready_required={summary.get('ready_required_component_count')}/{summary.get('required_component_count')} "
            f"authority_drift={summary.get('authority_drift_path_count')}"
        )
        for warning in validation.get("warnings", []):
            print(f"  [warning] {warning}")
        for error in validation.get("errors", []):
            print(f"  [error] {error}")

    if args.validate and validation["status"] == "error":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
