#!/usr/bin/env python3
"""WF63 non-executable Alpaca order-preview and shadow-mode scaffold.

This script converts review-only capital-deployment proposal packets into
non-executable order intent previews. It never imports brokerage SDKs, never
reads credentials, and never calls Alpaca or any other brokerage endpoint.
"""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, load_json_artifact

WORKSPACE = Path(__file__).resolve().parents[1]
TMP = WORKSPACE / "tmp"
WF63_DIR = TMP / "alpaca-paper-readiness"
DEFAULT_INPUT = TMP / "portfolio-mutation-proposals" / "current-capital-deployment-recommendations.json"
DEFAULT_PREVIEW_DIR = WF63_DIR / "order-previews"
DEFAULT_SHADOW_REPORT = WF63_DIR / "shadow-mode-report.json"
SCHEMA_VERSION = 1

AUTHORITY_FALSE_FLAGS = {
    "owner_approval_granted": False,
    "paper_submit_allowed": False,
    "live_submit_allowed": False,
    "trade_or_account_action_allowed": False,
}

PREVIEW_RESTRICTIONS = {
    "order_type": "limit",
    "time_in_force": "day",
    "market_orders_allowed": False,
    "short_sales_allowed": False,
    "margin_allowed": False,
    "leverage_allowed": False,
    "options_allowed": False,
    "crypto_allowed": False,
    "bracket_orders_allowed": False,
    "oco_orders_allowed": False,
    "oto_orders_allowed": False,
    "multi_leg_allowed": False,
}

RECOMMENDATION_ACTIONS_TO_SIDE = {
    "deploy_candidate": "buy_review_only",
    "wait_for_band": "buy_review_only",
    "owner_decision_required": "manual_review_only",
    "owner_gated_band_review": "manual_review_only",
    "review_required": "manual_review_only",
}

FORBIDDEN_SIDE_TOKENS = {"sell", "short"}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(WORKSPACE)).replace("\\", "/")
    except ValueError:
        return str(path)


def slug(value: Any) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "-", str(value or "preview")).strip("-")
    return cleaned[:120] or "preview"


def load_object(path: Path) -> dict[str, Any]:
    data = load_json_artifact(path)
    if not isinstance(data, dict):
        raise ValueError(f"{path} did not contain a JSON object")
    return data


def _extract_ticker(proposal: dict[str, Any]) -> str:
    return str(proposal.get("ticker") or proposal.get("ticker_or_scope") or "").strip().upper()


def _extract_limit_price(proposal: dict[str, Any]) -> dict[str, Any]:
    technical_gate = proposal.get("technical_gate") if isinstance(proposal.get("technical_gate"), dict) else {}
    close = technical_gate.get("close")
    # WF63 scaffolding is deliberately conservative: a close/reference price is
    # not converted into an executable limit. Owner must supply/approve a limit.
    return {
        "value": None,
        "currency": "USD",
        "status": "missing_owner_limit_price",
        "reference_close": close,
        "source": "proposal.technical_gate.close" if close is not None else None,
    }


def _extract_quantity_or_notional(proposal: dict[str, Any]) -> dict[str, Any]:
    return {
        "quantity": None,
        "notional": None,
        "currency": "USD",
        "status": "missing_owner_sizing",
        "source": None,
    }


def _side_for(proposal: dict[str, Any]) -> str:
    posture = str((proposal.get("proposed_state") or {}).get("recommendation_posture") or "review_required")
    return RECOMMENDATION_ACTIONS_TO_SIDE.get(posture, "manual_review_only")


def build_preview(proposal: dict[str, Any], *, source_path: Path, generated_at: str) -> dict[str, Any]:
    ticker = _extract_ticker(proposal)
    source_id = str(proposal.get("proposal_id") or f"unknown:{ticker}")
    preview_id = f"wf63-preview:{slug(source_id)}"
    side = _side_for(proposal)
    sizing = _extract_quantity_or_notional(proposal)
    limit_price = _extract_limit_price(proposal)
    validation_blockers: list[str] = []
    if not ticker:
        validation_blockers.append("missing_ticker")
    if side in FORBIDDEN_SIDE_TOKENS:
        validation_blockers.append("forbidden_side")
    if limit_price["value"] is None:
        validation_blockers.append("owner_limit_price_required")
    if sizing["quantity"] is None and sizing["notional"] is None:
        validation_blockers.append("owner_quantity_or_notional_required")

    preview = {
        "schema_version": SCHEMA_VERSION,
        "preview_id": preview_id,
        "generated_at_utc": generated_at,
        "artifact_type": "wf63_non_executable_order_preview",
        "status": "blocked_owner_inputs_required" if validation_blockers else "review_ready_non_executable",
        "ticker": ticker,
        "side": side,
        "order_type": "limit",
        "time_in_force": "day",
        "limit_price": limit_price,
        "quantity_or_notional": sizing,
        "source_proposal_id": source_id,
        "source_artifact": rel(source_path),
        "source_window": proposal.get("current_state", {}).get("source_window") if isinstance(proposal.get("current_state"), dict) else None,
        "risk_check_summary": {
            "risk_rule_check": proposal.get("risk_rule_check") or {},
            "concentration_check": proposal.get("concentration_check") or {},
            "technical_gate": proposal.get("technical_gate") or {},
            "catalyst_gate": proposal.get("catalyst_gate") or {},
            "source_freshness": proposal.get("source_freshness") or {},
            "blockers": validation_blockers,
        },
        "restrictions": dict(PREVIEW_RESTRICTIONS),
        "owner_decision_required": True,
        **AUTHORITY_FALSE_FLAGS,
        "execution_status": {
            "is_order": False,
            "is_approval": False,
            "would_submit": False,
            "brokerage_endpoint_calls_made": False,
            "brokerage_write_path_present": False,
            "portfolio_or_account_state_mutated": False,
        },
        "stop_lines": [
            "This preview is not an order and is not owner approval.",
            "Owner must explicitly decide before any manual paper pilot activity.",
            "No OpenClaw brokerage submit/cancel/replace or account action is authorized.",
        ],
    }
    return preview


def build_previews(input_path: Path) -> list[dict[str, Any]]:
    payload = load_object(input_path)
    proposals = payload.get("proposals")
    if not isinstance(proposals, list):
        raise ValueError("input artifact missing proposals list")
    generated_at = utc_now()
    return [build_preview(item, source_path=input_path, generated_at=generated_at) for item in proposals if isinstance(item, dict)]


def build_shadow_report(previews: list[dict[str, Any]], *, input_path: Path, preview_paths: list[Path]) -> dict[str, Any]:
    generated_at = utc_now()
    invalid = [p for p in previews if p.get("status") != "review_ready_non_executable"]
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": generated_at,
        "artifact_type": "wf63_shadow_mode_report",
        "status": "blocked_preview_inputs_required" if invalid else "ok_non_executable_shadow_mode",
        "source_artifact": rel(input_path),
        "preview_count": len(previews),
        "invalid_or_blocked_preview_count": len(invalid),
        "preview_artifacts": [rel(path) for path in preview_paths],
        "would_submit": False,
        "alpaca_endpoint_calls_made": False,
        "brokerage_endpoint_calls_made": False,
        "brokerage_write_methods_used": [],
        "paper_account_state_read": False,
        "paper_account_state_mutated": False,
        "portfolio_canon_mutated": False,
        "owner_decision_required": True,
        **AUTHORITY_FALSE_FLAGS,
        "shadow_checks": {
            "missed_previews": [],
            "invalid_previews": [p.get("preview_id") for p in invalid],
            "stale_previews": [],
            "contradictory_previews": [],
            "next_day_manual_reconciliation": "not_run_no_connection_or_manual_pilot",
        },
        "stop_lines": [
            "Shadow mode records preview intent only; it does not submit brokerage orders.",
            "Clean shadow mode is not owner approval.",
            "No Alpaca endpoint was called by this scaffold.",
        ],
    }


def write_outputs(previews: list[dict[str, Any]], *, input_path: Path, preview_dir: Path, shadow_report_path: Path) -> tuple[list[Path], Path]:
    preview_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for preview in previews:
        out = preview_dir / f"{slug(preview.get('preview_id'))}.json"
        atomic_write_json(out, preview)
        written.append(out)
    shadow_report = build_shadow_report(previews, input_path=input_path, preview_paths=written)
    atomic_write_json(shadow_report_path, shadow_report)
    return written, shadow_report_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate WF63 non-executable order previews and shadow-mode report.")
    parser.add_argument("--input", default=str(DEFAULT_INPUT))
    parser.add_argument("--preview-dir", default=str(DEFAULT_PREVIEW_DIR))
    parser.add_argument("--shadow-report", default=str(DEFAULT_SHADOW_REPORT))
    parser.add_argument("--write", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    input_path = Path(args.input)
    previews = build_previews(input_path)
    written: list[Path] = []
    shadow_path = Path(args.shadow_report)
    if args.write:
        written, shadow_path = write_outputs(
            previews,
            input_path=input_path,
            preview_dir=Path(args.preview_dir),
            shadow_report_path=shadow_path,
        )
    print(json.dumps({
        "status": "ok",
        "write": bool(args.write),
        "preview_count": len(previews),
        "preview_dir": rel(Path(args.preview_dir)),
        "shadow_report": rel(shadow_path),
        "written_previews": [rel(path) for path in written],
        "would_submit": False,
        "brokerage_endpoint_calls_made": False,
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
