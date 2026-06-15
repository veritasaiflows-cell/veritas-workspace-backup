#!/usr/bin/env python3
"""Audit autonomous review-card surfaces for authority drift.

This is a narrow WF87 hardening proof. It verifies that clean routing/card
language remains review-only and that no source artifact has drifted into
approval, execution, import/apply, account, money, or canon authority.
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
OUT = TMP / "autonomous-card-authority-audit.json"
SCHEMA = "veritas.autonomous_card_authority_audit.v1"

SOURCES = {
    "autonomous_routing_cards": TMP / "autonomous-routing-deployment-cards.json",
    "wf87_command_center": TMP / "wf87-autonomy-command-center.json",
    "wf87_rollup": TMP / "wf87-v2-readiness-rollup.json",
    "wf85_timing_gate": TMP / "wf85-deployment-timing-gate.json",
    "morning_cards": TMP / "morning-paper-deployment-recommendation-cards.json",
    "finance_market_loop": TMP / "finance-market-deployment-operating-loop.json",
    "wf78_batch_manifest": ROOT / "state" / "workflows" / "wf78-scaleout-batch-manifest.json",
}

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "semantic_authority_audit_only": True,
    "capital_deployment_allowed": False,
    "capital_deployment_approved": False,
    "trade_or_execution_allowed": False,
    "trade_or_execution_approved": False,
    "paper_or_live_execution_allowed": False,
    "paper_submit_allowed": False,
    "paper_cancel_allowed": False,
    "paper_sell_allowed": False,
    "live_trade_allowed": False,
    "live_execution_allowed_now": False,
    "autonomous_execution_allowed_now": False,
    "brokerage_or_account_action_allowed": False,
    "money_movement_allowed": False,
    "canon_or_portfolio_mutation_allowed": False,
    "ticker_card_mutation_allowed": False,
    "universe_import_or_apply_allowed": False,
    "ticker_import_allowed": False,
    "apply_allowed": False,
    "promotion_allowed": False,
    "owner_approval_inferred": False,
    "cron_direct_execution_allowed": False,
}

FORBIDDEN_TRUE_KEYS = {key for key, value in AUTHORITY_BOUNDARY.items() if value is False}
REQUIRED_STOP_LINE_TERMS = (
    "owner approval",
    "execution",
)


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


def load(path: Path) -> dict[str, Any]:
    payload = load_json_artifact(path)
    return payload if isinstance(payload, dict) else {}


def validation_status(payload: dict[str, Any]) -> str | None:
    return as_dict(payload.get("validation")).get("status")


def forbidden_true_paths(value: Any, prefix: str = "") -> list[str]:
    paths: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            child = f"{prefix}.{key}" if prefix else str(key)
            if key in FORBIDDEN_TRUE_KEYS and item is True:
                paths.append(child)
            paths.extend(forbidden_true_paths(item, child))
    elif isinstance(value, list):
        for idx, item in enumerate(value):
            paths.extend(forbidden_true_paths(item, f"{prefix}[{idx}]"))
    return paths


def source_record(name: str, path: Path, payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": name,
        "path": rel(path),
        "exists": path.exists(),
        "status": payload.get("status") if payload else ("missing" if not path.exists() else "unparseable"),
        "validation_status": validation_status(payload),
        "forbidden_true_paths": forbidden_true_paths(payload),
        "generated_at_utc": payload.get("generated_at_utc"),
    }


def text_items(value: Any) -> list[str]:
    items: list[str] = []
    if isinstance(value, str):
        items.append(value)
    elif isinstance(value, dict):
        for item in value.values():
            items.extend(text_items(item))
    elif isinstance(value, list):
        for item in value:
            items.extend(text_items(item))
    return items


def stop_line_score(payload: dict[str, Any]) -> dict[str, Any]:
    stop_lines = [str(item).lower() for item in as_list(payload.get("stop_lines"))]
    joined = " ".join(stop_lines)
    missing_terms = [term for term in REQUIRED_STOP_LINE_TERMS if term not in joined]
    return {
        "stop_line_count": len(stop_lines),
        "missing_required_terms": missing_terms,
        "has_review_boundary": "review" in joined or "prep" in joined,
    }


def source_semantics(name: str, payload: dict[str, Any]) -> dict[str, Any]:
    summary = as_dict(payload.get("summary"))
    stop_score = stop_line_score(payload)
    return {
        "name": name,
        "clean_review_count": (
            summary.get("clean_randall_review_card_count")
            or summary.get("morning_clean_approval_review_card_count")
            or summary.get("clean_approval_card_count")
            or 0
        ),
        "owner_review_candidate_count": (
            summary.get("owner_review_card_candidate_count")
            or summary.get("autonomous_owner_review_card_candidate_count")
            or 0
        ),
        "execution_allowed_count": (
            summary.get("morning_card_execution_allowed_count")
            or summary.get("execution_allowed_count")
            or 0
        ),
        "autonomous_execution_allowed_now": (
            summary.get("autonomous_execution_allowed_now") is True
            or summary.get("autonomous_card_execution_allowed_now") is True
        ),
        "exact_order_preparation_allowed_now": summary.get("exact_order_preparation_allowed_now") is True,
        "stop_line_score": stop_score,
    }


def maturity_summary(payloads: dict[str, dict[str, Any]]) -> dict[str, Any]:
    command = payloads["wf87_command_center"]
    rollup = payloads["wf87_rollup"]
    command_summary = as_dict(command.get("summary"))
    rollup_shadow = as_dict(rollup.get("shadow_threshold"))
    reconciliation = as_dict(rollup.get("reconciliation_maturity"))
    return {
        "wf87_status": command.get("status"),
        "operator_action": command.get("operator_action"),
        "shadow_decisions_done": as_dict(command_summary.get("shadow_decisions")).get(
            "done", rollup_shadow.get("clean_shadow_decision_count")
        ),
        "shadow_decisions_required": as_dict(command_summary.get("shadow_decisions")).get(
            "required", rollup_shadow.get("required_clean_decisions")
        ),
        "shadow_sessions_done": as_dict(command_summary.get("shadow_sessions")).get(
            "done", rollup_shadow.get("unique_clean_market_sessions")
        ),
        "shadow_sessions_required": as_dict(command_summary.get("shadow_sessions")).get(
            "required", rollup_shadow.get("required_clean_market_sessions")
        ),
        "shadow_threshold_met": command_summary.get("shadow_threshold_met") is True
        or rollup_shadow.get("threshold_met") is True,
        "reconciliation_mature": reconciliation.get("mature_for_autonomy") is True,
    }


def validate(payload: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    authority = as_dict(payload.get("authority_boundary"))
    for key, expected in AUTHORITY_BOUNDARY.items():
        if authority.get(key) is not expected:
            errors.append(f"authority_{key}_not_{str(expected).lower()}")
    for record in as_list(payload.get("source_records")):
        if record.get("exists") is not True:
            errors.append(f"missing_source:{record.get('name')}")
        if record.get("forbidden_true_paths"):
            errors.append(f"forbidden_true_authority:{record.get('name')}")
        if record.get("validation_status") not in {"ok", None}:
            warnings.append(f"source_validation_not_ok:{record.get('name')}:{record.get('validation_status')}")
    for item in as_list(payload.get("semantic_checks")):
        if item.get("autonomous_execution_allowed_now"):
            errors.append(f"autonomous_execution_allowed:{item.get('name')}")
        if item.get("execution_allowed_count"):
            errors.append(f"execution_allowed_count_nonzero:{item.get('name')}")
    maturity = as_dict(payload.get("maturity_summary"))
    summary = as_dict(payload.get("summary"))
    if not maturity.get("shadow_threshold_met") and summary.get("owner_review_candidate_count"):
        warnings.append("owner_review_candidates_exist_before_shadow_threshold")
    if not maturity.get("reconciliation_mature") and summary.get("owner_review_candidate_count"):
        warnings.append("owner_review_candidates_exist_before_reconciliation_maturity")
    if summary.get("clean_review_card_count") and summary.get("execution_allowed_count"):
        errors.append("clean_review_cards_with_execution_allowed_count")
    return {"status": "error" if errors else "warning" if warnings else "ok", "errors": errors, "warnings": warnings}


def build_payload(paths: dict[str, Path]) -> dict[str, Any]:
    payloads = {name: load(path) for name, path in paths.items()}
    records = [source_record(name, path, payloads[name]) for name, path in paths.items()]
    semantic_checks = [source_semantics(name, payload) for name, payload in payloads.items()]
    maturity = maturity_summary(payloads)
    clean_review_count = sum(int(item.get("clean_review_count") or 0) for item in semantic_checks)
    owner_candidates = sum(int(item.get("owner_review_candidate_count") or 0) for item in semantic_checks)
    execution_allowed_count = sum(int(item.get("execution_allowed_count") or 0) for item in semantic_checks)
    weak_stop_line_source_count = sum(
        1 for item in semantic_checks if as_dict(item.get("stop_line_score")).get("missing_required_terms")
    )
    payload = {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "draft",
        "workflow_ids": ["WF78", "WF85", "WF86", "WF87"],
        "purpose": "Review-only semantic authority audit for autonomous routing and deployment-card surfaces.",
        "authority_boundary": AUTHORITY_BOUNDARY,
        "summary": {
            "source_count": len(records),
            "source_forbidden_true_count": sum(1 for record in records if record.get("forbidden_true_paths")),
            "clean_review_card_count": clean_review_count,
            "owner_review_candidate_count": owner_candidates,
            "execution_allowed_count": execution_allowed_count,
            "weak_stop_line_source_count": weak_stop_line_source_count,
            "autonomous_execution_allowed_now": False,
            "next_safe_action": (
                "Continue maturity accrual and market-hours refresh; review cards remain owner-gated."
                if not owner_candidates
                else "Review candidates as owner-review cards only; no execution without exact approval and WF67 proof."
            ),
        },
        "maturity_summary": maturity,
        "source_artifacts": {name: rel(path) for name, path in paths.items()},
        "source_records": records,
        "semantic_checks": semantic_checks,
        "stop_lines": [
            "This audit is proof only; it is not a trade, approval, or execution surface.",
            "Clean card language means Randall review only, never owner approval.",
            "No paper/live submit, cancel, sell, replace, account action, money movement, import/apply, or canon/portfolio mutation authority.",
        ],
    }
    payload["validation"] = validate(payload)
    payload["status"] = "blocked" if payload["validation"]["status"] == "error" else "ok"
    return payload


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    for key, path in SOURCES.items():
        parser.add_argument(f"--{key.replace('_', '-')}", type=Path, default=path)
    parser.add_argument("--out", type=Path, default=OUT)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--pretty", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    paths = {key: (value if value.is_absolute() else ROOT / value) for key, value in vars(args).items() if key in SOURCES}
    payload = build_payload(paths)
    out = args.out if args.out.is_absolute() else ROOT / args.out
    if args.write:
        atomic_write_json(out, payload)
    if args.pretty:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(json.dumps({
            "status": payload.get("status"),
            "validation": payload.get("validation"),
            "summary": payload.get("summary"),
            "out": rel(out) if args.write else None,
        }, indent=2, sort_keys=True))
    if args.validate and as_dict(payload.get("validation")).get("status") == "error":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
