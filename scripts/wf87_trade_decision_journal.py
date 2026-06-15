#!/usr/bin/env python3
"""Append the WF87 trade-decision journal from WF86 proof artifacts.

The journal is a JSONL review surface. It consolidates one current WF86
shadow decision per ``session_key:ticker`` into a stable record shape:
decision -> gates -> approval -> order -> fill/reconciliation -> outcome.

This script never submits, cancels, sells, replaces, touches live endpoints,
mutates account/canon/portfolio state, or infers owner approval.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_text, load_json_artifact

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
DEFAULT_SHADOW_DECISIONS = TMP / "paper-autotrader" / "shadow-decisions.json"
DEFAULT_READINESS = TMP / "paper-autotrader" / "autotrader-readiness.json"
DEFAULT_ORDER_HISTORY = TMP / "alpaca-paper-readiness" / "paper-order-history-classifier.json"
DEFAULT_OUT = TMP / "paper-autotrader" / "trade-decision-journal.jsonl"
SCHEMA = "veritas.wf87_trade_decision_journal_record.v1"

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "paper_only_design": True,
    "append_only_journal": True,
    "shadow_or_reconciliation_proof_only": True,
    "paper_submit_allowed": False,
    "paper_cancel_allowed": False,
    "paper_sell_allowed": False,
    "paper_replace_allowed": False,
    "autonomous_paper_execution_allowed_now": False,
    "live_trade_allowed": False,
    "live_endpoint_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "money_movement_allowed": False,
    "portfolio_or_canon_mutation_allowed": False,
    "owner_approval_inferred": False,
}

RECORD_AUTHORITY = {
    "capital_deployment_approved": False,
    "trade_or_execution_approved": False,
    "paper_or_live_execution_allowed": False,
    "paper_submit_allowed": False,
    "paper_cancel_allowed": False,
    "paper_sell_allowed": False,
    "paper_replace_allowed": False,
    "autonomous_paper_execution_allowed_now": False,
    "live_trade_allowed": False,
    "live_endpoint_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "money_movement_allowed": False,
    "portfolio_or_canon_mutation_allowed": False,
    "owner_approval_inferred": False,
}

FORBIDDEN_TRUE_KEYS = {
    "autonomous_paper_execution_allowed_now",
    "brokerage_or_account_action_allowed",
    "capital_deployment_approved",
    "live_endpoint_allowed",
    "live_trade_allowed",
    "money_movement_allowed",
    "order_submitted",
    "owner_approval_inferred",
    "paper_cancel_allowed",
    "paper_or_live_execution_allowed",
    "paper_replace_allowed",
    "paper_sell_allowed",
    "paper_submit_allowed",
    "portfolio_or_canon_mutation_allowed",
    "trade_or_execution_approved",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def resolve(path: Path) -> Path:
    return path if path.is_absolute() else ROOT / path


def rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def load_dict(path: Path) -> dict[str, Any]:
    payload = load_json_artifact(path)
    return payload if isinstance(payload, dict) else {}


def decision_key(row: dict[str, Any]) -> str:
    session = str(row.get("session_key") or "").strip()
    ticker = str(row.get("ticker") or "").strip().upper()
    if session and ticker:
        return f"{session}:{ticker}"
    return str(row.get("decision_id") or row.get("journal_id") or "").strip()


def order_side(action: str) -> str | None:
    if action == "would_buy_shadow":
        return "buy"
    if action == "would_sell_shadow":
        return "sell"
    return None


def classifier_symbol(row: dict[str, Any]) -> str:
    return str(row.get("symbol") or row.get("ticker") or "").upper()


def is_wf86_classification(row: dict[str, Any]) -> bool:
    source = str(row.get("source_path") or "").lower()
    request = as_dict(row.get("request"))
    request_id = str(request.get("request_id") or "").lower()
    request_path = str(request.get("path") or "").lower()
    return "wf86" in source or "wf86" in request_id or "wf86" in request_path


def find_order_classification(ticker: str, order_history: dict[str, Any]) -> dict[str, Any] | None:
    matches = [
        as_dict(row)
        for row in as_list(order_history.get("classifications"))
        if classifier_symbol(as_dict(row)) == ticker and is_wf86_classification(as_dict(row))
    ]
    if not matches:
        return None
    return sorted(matches, key=lambda row: str(row.get("submitted_at_utc") or ""), reverse=True)[0]


def build_order_section(decision: dict[str, Any], classification: dict[str, Any] | None) -> dict[str, Any]:
    action = str(decision.get("shadow_decision") or "")
    intended_side = order_side(action)
    if not classification:
        return {
            "intended_side": intended_side,
            "order_submitted": False,
            "order_status": "no_order_submitted",
            "wf67_request_generation_status": decision.get("wf67_request_generation_status"),
            "request": None,
            "source_path": None,
        }
    request = as_dict(classification.get("request"))
    return {
        "intended_side": intended_side or classification.get("side"),
        "order_submitted": False,
        "order_status": str(classification.get("classification") or "classified_review_only"),
        "wf67_request_generation_status": decision.get("wf67_request_generation_status"),
        "submitted_at_utc": classification.get("submitted_at_utc"),
        "paper_order_status_at_submit": classification.get("paper_order_status_at_submit"),
        "request": {
            "path": request.get("path"),
            "request_id": request.get("request_id"),
            "created_at_utc": request.get("created_at_utc"),
            "order": request.get("order"),
        },
        "source_path": classification.get("source_path"),
    }


def build_reconciliation_section(classification: dict[str, Any] | None) -> dict[str, Any]:
    if not classification:
        return {
            "status": "not_applicable_no_order",
            "classification": None,
            "match_status": None,
            "evidence": None,
            "order_history": None,
            "position_cross_check": None,
        }
    return {
        "status": "classified_review_only",
        "classification": classification.get("classification"),
        "match_status": classification.get("match_status"),
        "evidence": classification.get("evidence"),
        "order_history": classification.get("order_history"),
        "position_cross_check": classification.get("position_cross_check"),
    }


def build_outcome_section(classification: dict[str, Any] | None) -> dict[str, Any]:
    if not classification:
        return {
            "tracked": False,
            "status": "pending_future_session",
            "terminal": False,
            "notes": "Shadow journal record only. No order submitted by this script.",
        }
    classification_name = str(classification.get("classification") or "unknown")
    terminal = classification_name in {"filled", "expired", "canceled", "rejected", "replaced", "terminal_other"}
    return {
        "tracked": True,
        "status": classification_name,
        "terminal": terminal,
        "next_safe_action": classification.get("next_safe_action"),
        "notes": "Paper order lifecycle evidence is review-only; any new order still requires exact gated authority.",
    }


def build_record(
    decision: dict[str, Any],
    readiness: dict[str, Any],
    order_history: dict[str, Any],
    *,
    shadow_path: Path,
    readiness_path: Path,
    order_history_path: Path,
) -> dict[str, Any]:
    ticker = str(decision.get("ticker") or "").upper()
    key = decision_key(decision)
    classification = find_order_classification(ticker, order_history)
    readiness_guard = as_dict(readiness.get("guard"))
    pilot = as_dict(readiness_guard.get("pilot_approval"))
    record = {
        "schema": SCHEMA,
        "journal_id": f"wf87-journal-{key}".replace(" ", "-"),
        "decision_key": key,
        "workflow_id": "WF87",
        "source_workflow_id": "WF86",
        "ingested_at_utc": utc_now(),
        "source_generated_at_utc": decision.get("generated_at_utc"),
        "decision": {
            "decision_id": decision.get("decision_id"),
            "session_key": decision.get("session_key"),
            "ticker": ticker,
            "shadow_decision": decision.get("shadow_decision"),
            "current_price": decision.get("current_price"),
            "current_band_status": decision.get("current_band_status"),
            "written_band": decision.get("written_band"),
            "factory_disposition": decision.get("factory_disposition"),
            "source_artifact": decision.get("source_artifact"),
        },
        "gates": {
            "shadow_eligible": bool(decision.get("shadow_eligible")),
            "assisted_review_ready": bool(decision.get("assisted_review_ready")),
            "execution_ready": False,
            "shadow_blockers": as_list(decision.get("shadow_blockers")),
            "assisted_review_blockers": as_list(decision.get("assisted_review_blockers")),
            "execution_blockers": as_list(decision.get("execution_blockers")),
            "readiness_status": readiness.get("status"),
            "phase_readiness": readiness.get("phase_readiness"),
            "guard_status": readiness_guard.get("status"),
            "wf67_guard_status": as_dict(readiness_guard.get("wf67")).get("guard_status"),
            "blockers_before_assisted_mode": as_list(readiness.get("blockers_before_assisted_mode")),
            "blockers_before_autonomous_paper_execution": as_list(readiness.get("blockers_before_autonomous_paper_execution")),
        },
        "approval": {
            "owner_approval_inferred": False,
            "trade_or_execution_approved": False,
            "capital_deployment_approved": False,
            "exact_order_approval_status": "not_present_or_not_inferred",
            "autonomous_pilot_approval_present": bool(pilot.get("present")),
            "autonomous_pilot_approval_valid": bool(pilot.get("valid")),
            "autonomous_pilot_approval_is_not_order_approval": True,
        },
        "order": build_order_section(decision, classification),
        "fill_reconciliation": build_reconciliation_section(classification),
        "outcome": build_outcome_section(classification),
        "authority": dict(RECORD_AUTHORITY),
        "source_artifacts": [
            rel(shadow_path),
            rel(readiness_path),
            rel(order_history_path) if order_history_path.exists() else None,
        ],
        "stop_lines": [
            "Journal rows are not approval.",
            "No paper submit/cancel/sell/replace from this script.",
            "No live endpoint, account action, money movement, or owner approval inference.",
        ],
    }
    record["source_artifacts"] = [item for item in record["source_artifacts"] if item]
    return record


def load_jsonl_records(path: Path) -> tuple[list[dict[str, Any]], list[str]]:
    if not path.exists():
        return [], []
    records: list[dict[str, Any]] = []
    warnings: list[str] = []
    for index, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            warnings.append(f"invalid_jsonl_line:{index}")
            continue
        if isinstance(payload, dict):
            records.append(payload)
        else:
            warnings.append(f"non_object_jsonl_line:{index}")
    return records, warnings


def merge_records(existing: list[dict[str, Any]], new_records: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], int, int]:
    merged: list[dict[str, Any]] = []
    seen: set[str] = set()
    duplicate_existing = 0
    for row in existing:
        key = str(row.get("decision_key") or decision_key(as_dict(row.get("decision"))) or row.get("journal_id") or "")
        if not key:
            key = str(row.get("journal_id") or f"legacy-row-{len(merged)}")
        if key in seen:
            duplicate_existing += 1
            continue
        seen.add(key)
        merged.append(row)
    appended = 0
    for row in new_records:
        key = str(row.get("decision_key") or "")
        if not key or key in seen:
            continue
        seen.add(key)
        merged.append(row)
        appended += 1
    return merged, appended, duplicate_existing


def find_forbidden_true_values(value: Any, prefix: str = "") -> list[str]:
    errors: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            path = f"{prefix}.{key}" if prefix else str(key)
            if key in FORBIDDEN_TRUE_KEYS and child is True:
                errors.append(f"forbidden_true:{path}")
            errors.extend(find_forbidden_true_values(child, path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            errors.extend(find_forbidden_true_values(child, f"{prefix}[{index}]"))
    return errors


def validate_records(records: list[dict[str, Any]]) -> list[str]:
    errors: list[str] = []
    for row in records:
        key = str(row.get("decision_key") or "")
        if not key:
            errors.append("record_missing_decision_key")
        for section in ("decision", "gates", "approval", "order", "fill_reconciliation", "outcome", "authority"):
            if not isinstance(row.get(section), dict):
                errors.append(f"{key or 'unknown'}:missing_section:{section}")
        errors.extend(find_forbidden_true_values(row))
    return errors


def build_journal(
    *,
    shadow_path: Path,
    readiness_path: Path,
    order_history_path: Path,
    out_path: Path,
) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    if not shadow_path.exists():
        errors.append(f"missing_source:{rel(shadow_path)}")
    if not readiness_path.exists():
        errors.append(f"missing_source:{rel(readiness_path)}")

    shadow = load_dict(shadow_path) if shadow_path.exists() else {}
    readiness = load_dict(readiness_path) if readiness_path.exists() else {}
    order_history = load_dict(order_history_path) if order_history_path.exists() else {}
    if order_history_path.exists() and order_history.get("status") not in {"ok", None}:
        warnings.append(f"order_history_status:{order_history.get('status')}")
    if shadow and shadow.get("status") != "ok":
        errors.append(f"shadow_status_not_ok:{shadow.get('status')}")
    if readiness and readiness.get("validation", {}).get("status") != "ok":
        errors.append(f"readiness_validation_not_ok:{readiness.get('validation', {}).get('status')}")

    decisions = [as_dict(row) for row in as_list(shadow.get("decisions")) if as_dict(row).get("ticker")]
    if not errors and not decisions:
        errors.append("no_shadow_decisions")

    existing, jsonl_warnings = load_jsonl_records(out_path)
    warnings.extend(jsonl_warnings)
    new_records = [
        build_record(
            decision,
            readiness,
            order_history,
            shadow_path=shadow_path,
            readiness_path=readiness_path,
            order_history_path=order_history_path,
        )
        for decision in decisions
    ] if not errors else []
    records, appended_count, duplicate_existing_count = merge_records(existing, new_records)
    validation_errors = validate_records(new_records)
    errors.extend(validation_errors)

    return {
        "status": "ok" if not errors else "blocked",
        "records": records,
        "new_records": new_records,
        "summary": {
            "existing_record_count": len(existing),
            "source_decision_count": len(decisions),
            "new_record_candidate_count": len(new_records),
            "records_to_write_count": len(records),
            "records_appended_count": appended_count,
            "duplicate_existing_count": duplicate_existing_count,
            "authority_flags_false": not validation_errors,
            "source_artifacts": [
                rel(shadow_path),
                rel(readiness_path),
                rel(order_history_path) if order_history_path.exists() else None,
            ],
        },
        "validation": {
            "status": "ok" if not errors else "error",
            "errors": errors,
            "warnings": warnings,
        },
    }


def write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    lines = [json.dumps(record, sort_keys=True, ensure_ascii=False) for record in records]
    content = "\n".join(lines)
    if content:
        content += "\n"
    atomic_write_text(path, content)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--shadow-decisions", type=Path, default=DEFAULT_SHADOW_DECISIONS)
    parser.add_argument("--readiness", type=Path, default=DEFAULT_READINESS)
    parser.add_argument("--order-history", type=Path, default=DEFAULT_ORDER_HISTORY)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    args = parser.parse_args()

    shadow_path = resolve(args.shadow_decisions)
    readiness_path = resolve(args.readiness)
    order_history_path = resolve(args.order_history)
    out_path = resolve(args.out)
    journal = build_journal(
        shadow_path=shadow_path,
        readiness_path=readiness_path,
        order_history_path=order_history_path,
        out_path=out_path,
    )
    wrote = False
    if args.write and journal["validation"]["status"] == "ok":
        out_path.parent.mkdir(parents=True, exist_ok=True)
        write_jsonl(out_path, journal["records"])
        wrote = True

    print(json.dumps({
        "status": journal["status"],
        "out": rel(out_path) if wrote else None,
        "summary": journal["summary"],
        "validation": journal["validation"],
    }, indent=2, sort_keys=True))
    return 1 if args.validate and journal["validation"]["status"] != "ok" else 0


if __name__ == "__main__":
    raise SystemExit(main())
