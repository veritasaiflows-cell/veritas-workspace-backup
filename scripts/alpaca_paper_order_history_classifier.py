#!/usr/bin/env python3
"""Classify WF67-submitted paper orders from GET-only Alpaca order history.

This script reconciles every locally submitted WF67 paper order artifact against
Alpaca paper order history and current paper positions. It is read-only:
GET /v2/orders and GET /v2/positions only, no submit/cancel/replace/sell.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import requests

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from market_data_utils import atomic_write_json, load_json_artifact


BASE = ROOT / "tmp" / "alpaca-paper-readiness"
DEFAULT_OUT = BASE / "paper-order-history-classifier.json"
DEFAULT_AUDIT_LOG = BASE / "audit-log.jsonl"

PAPER_BASE_URL = "https://paper-api.alpaca.markets"
LIVE_BASE_URL = "https://" + "api.alpaca.markets"
KEY_ENV = "ALPACA_PAPER_API_KEY_ID"
SECRET_ENV = "ALPACA_PAPER_API_SECRET_KEY"
ALLOWED_METHODS = ["GET"]
BLOCKED_METHODS = ["POST", "PATCH", "PUT", "DELETE"]
OPEN_STATUSES = {"new", "accepted", "pending_new", "accepted_for_bidding", "pending_replace", "pending_cancel"}
TERMINAL_STATUSES = {"filled", "canceled", "cancelled", "expired", "rejected", "replaced", "stopped", "suspended"}
SCHEMA = "veritas.alpaca_paper_order_history_classifier.v1"

AMBIGUOUS_OR_LIVE_NAMES = {
    "ALPACA_API_KEY_ID",
    "ALPACA_SECRET_KEY",
    "APCA_API_KEY_ID",
    "APCA_API_SECRET_KEY",
    "ALPACA_LIVE_API_KEY_ID",
    "ALPACA_LIVE_API_SECRET_KEY",
    "APCA_LIVE_API_KEY_ID",
    "APCA_LIVE_API_SECRET_KEY",
}


class BlockedRun(Exception):
    """Expected fail-closed block."""


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_time(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def as_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def stable_hash(value: Any) -> str | None:
    if value in (None, ""):
        return None
    return hashlib.sha256(str(value).encode("utf-8")).hexdigest()[:16]


def authority_boundary() -> dict[str, Any]:
    return {
        "review_only": True,
        "paper_only": True,
        "endpoint": PAPER_BASE_URL,
        "allowed_methods": ALLOWED_METHODS,
        "blocked_methods": BLOCKED_METHODS,
        "get_only_order_history_allowed": True,
        "get_only_positions_allowed": True,
        "paper_submit_allowed": False,
        "paper_cancel_allowed": False,
        "paper_sell_allowed": False,
        "paper_replace_allowed": False,
        "close_position_or_liquidation_allowed": False,
        "live_endpoint_allowed": False,
        "live_trade_or_account_action_allowed": False,
        "money_movement_allowed": False,
        "account_settings_mutation_allowed": False,
        "owner_approval_inferred": False,
        "portfolio_or_canon_mutation_allowed": False,
        "raw_response_bodies_persisted": False,
        "broker_order_ids_redacted": True,
    }


def append_audit(event: dict[str, Any], audit_log: Path) -> None:
    audit_log.parent.mkdir(parents=True, exist_ok=True)
    with audit_log.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(event, sort_keys=True) + "\n")


def audit_event(action: str, result: str, reason_code: str, artifact_paths: list[str]) -> dict[str, Any]:
    return {
        "timestamp_utc": utc_now(),
        "workflow": "WF67/WF86 paper order history classifier",
        "event_id": f"wf86-order-history-{uuid.uuid4().hex[:12]}",
        "actor": "script",
        "action": action,
        "method_class": "GET" if action.startswith("read_") else "LOCAL_WRITE",
        "endpoint_mode": "paper",
        "request_intent": "paper_order_history_classification",
        "result": result,
        "reason_code": reason_code,
        "artifact_paths": artifact_paths,
        "redaction_status": "redacted",
        "secret_material_present": False,
        "trade_or_account_action_allowed": False,
    }


def make_session() -> requests.Session:
    if any(os.environ.get(name) for name in AMBIGUOUS_OR_LIVE_NAMES):
        raise BlockedRun("ambiguous_or_live_alpaca_env_present")
    if not os.environ.get(KEY_ENV) or not os.environ.get(SECRET_ENV):
        raise BlockedRun("missing_paper_credentials")
    session = requests.Session()
    session.headers.update(
        {
            "APCA-API-KEY-ID": os.environ[KEY_ENV],
            "APCA-API-SECRET-KEY": os.environ[SECRET_ENV],
            "Accept": "application/json",
        }
    )
    return session


def get_json(session: requests.Session, path: str, *, params: dict[str, Any] | None, timeout: int) -> Any:
    if not path.startswith("/v2/"):
        raise BlockedRun("path_not_v2")
    url = PAPER_BASE_URL + path
    if not url.startswith(PAPER_BASE_URL) or url.startswith(LIVE_BASE_URL):
        raise BlockedRun("endpoint_not_exact_paper")
    response = session.get(url, params=params or {}, timeout=timeout)
    if not (200 <= response.status_code < 300):
        raise BlockedRun(f"paper_get_failed:{path}:{response.status_code}")
    return response.json()


def load_payload(path: Path) -> dict[str, Any]:
    payload = load_json_artifact(path)
    return payload if isinstance(payload, dict) else {}


def latest_request_for(symbol: str, side: str, submitted_at: datetime | None) -> dict[str, Any]:
    best: tuple[float, dict[str, Any]] | None = None
    for path in sorted(BASE.glob("paper-trade-request*.json")):
        payload = load_payload(path)
        order = as_dict(payload.get("order"))
        if str(order.get("symbol") or "").upper() != symbol or str(order.get("side") or "").lower() != side:
            continue
        created_at = parse_time(payload.get("created_at_utc"))
        score = 0.0
        if submitted_at and created_at:
            delta = (submitted_at - created_at).total_seconds()
            if delta >= -60:
                score += max(0.0, 7200.0 - abs(delta))
        if as_dict(payload.get("source")).get("exact_order_owner_approval_status") == "approved_exact_order":
            score += 200.0
        candidate = {
            "path": rel(path),
            "request_id": payload.get("request_id"),
            "created_at_utc": payload.get("created_at_utc"),
            "order": {
                "symbol": order.get("symbol"),
                "side": order.get("side"),
                "type": order.get("type"),
                "time_in_force": order.get("time_in_force"),
                "limit_price": as_float(order.get("limit_price")),
                "qty": as_float(order.get("qty")),
                "notional": as_float(order.get("notional")),
            },
        }
        if best is None or score > best[0]:
            best = (score, candidate)
    return best[1] if best else {}


def submitted_order_sources() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in sorted(BASE.glob("paper-execution-result*.json")):
        payload = load_payload(path)
        if payload.get("artifact_type") != "wf67_paper_execution_result":
            continue
        if payload.get("action") != "submit" or payload.get("status") != "submitted":
            continue
        redacted = as_dict(payload.get("broker_redacted_result"))
        symbol = str(redacted.get("paper_order_symbol") or redacted.get("symbol") or "").upper()
        side = str(redacted.get("side") or "").lower()
        submitted_at = parse_time(payload.get("generated_at_utc"))
        request = latest_request_for(symbol, side, submitted_at)
        rows.append(
            {
                "source_path": rel(path),
                "generated_at_utc": payload.get("generated_at_utc"),
                "symbol": symbol,
                "side": side,
                "paper_order_status_at_submit": redacted.get("paper_order_status"),
                "paper_order_id_present": redacted.get("paper_order_id_present") is True,
                "paper_order_id_hash": stable_hash(redacted.get("paper_order_id") or redacted.get("id") or redacted.get("order_id")),
                "request": request,
            }
        )
    return rows


def sanitize_order(order: dict[str, Any]) -> dict[str, Any]:
    return {
        "broker_order_id_hash": stable_hash(order.get("id")),
        "client_order_id_hash": stable_hash(order.get("client_order_id")),
        "symbol": str(order.get("symbol") or "").upper(),
        "side": order.get("side"),
        "type": order.get("type"),
        "time_in_force": order.get("time_in_force"),
        "status": order.get("status"),
        "submitted_at": order.get("submitted_at"),
        "created_at": order.get("created_at"),
        "updated_at": order.get("updated_at"),
        "filled_at": order.get("filled_at"),
        "expired_at": order.get("expired_at"),
        "canceled_at": order.get("canceled_at") or order.get("cancelled_at"),
        "failed_at": order.get("failed_at"),
        "replaced_at": order.get("replaced_at"),
        "qty": as_float(order.get("qty")),
        "notional": as_float(order.get("notional")),
        "filled_qty": as_float(order.get("filled_qty")),
        "filled_avg_price": as_float(order.get("filled_avg_price")),
        "limit_price": as_float(order.get("limit_price")),
        "hwm": as_float(order.get("hwm")),
        "extended_hours": order.get("extended_hours"),
    }


def status_bucket(status: Any) -> str:
    value = str(status or "").lower()
    if value == "partially_filled":
        return "partially_filled"
    if value in OPEN_STATUSES:
        return "open_or_pending"
    if value in {"canceled", "cancelled"}:
        return "canceled"
    if value in {"filled", "expired", "rejected", "replaced"}:
        return value
    if value in TERMINAL_STATUSES:
        return "terminal_other"
    return "unresolved"


def score_match(source: dict[str, Any], order: dict[str, Any]) -> int:
    score = 0
    if source.get("paper_order_id_hash") and source.get("paper_order_id_hash") == stable_hash(order.get("id")):
        score += 1000
    symbol = str(source.get("symbol") or "").upper()
    side = str(source.get("side") or "").lower()
    if symbol and str(order.get("symbol") or "").upper() == symbol:
        score += 80
    if side and str(order.get("side") or "").lower() == side:
        score += 25
    request_order = as_dict(as_dict(source.get("request")).get("order"))
    if request_order:
        if request_order.get("type") == order.get("type"):
            score += 15
        if request_order.get("time_in_force") == order.get("time_in_force"):
            score += 10
        limit_a = as_float(request_order.get("limit_price"))
        limit_b = as_float(order.get("limit_price"))
        if limit_a is not None and limit_b is not None and abs(limit_a - limit_b) < 0.01:
            score += 20
        qty_a = as_float(request_order.get("qty"))
        qty_b = as_float(order.get("qty"))
        if qty_a is not None and qty_b is not None and abs(qty_a - qty_b) < 0.0001:
            score += 12
        notional_a = as_float(request_order.get("notional"))
        notional_b = as_float(order.get("notional"))
        if notional_a is not None and notional_b is not None and abs(notional_a - notional_b) < 0.01:
            score += 12
    submitted = parse_time(source.get("generated_at_utc"))
    order_time = parse_time(order.get("submitted_at")) or parse_time(order.get("created_at"))
    if submitted and order_time:
        delta = abs((order_time - submitted).total_seconds())
        if delta <= 300:
            score += 60
        elif delta <= 3600:
            score += 30
        elif delta <= 86400:
            score += 10
    return score


def classify_source(source: dict[str, Any], orders: list[dict[str, Any]], positions: list[dict[str, Any]]) -> dict[str, Any]:
    scored = sorted(((score_match(source, order), order) for order in orders), key=lambda item: item[0], reverse=True)
    best_score, best_order = scored[0] if scored else (0, {})
    position = next((row for row in positions if str(row.get("symbol") or "").upper() == source.get("symbol")), None)
    matched = best_score >= 100
    sanitized = sanitize_order(best_order) if matched else {}
    bucket = status_bucket(sanitized.get("status")) if matched else "unresolved"
    evidence = "alpaca_order_history_match" if matched else "no_order_history_match"
    if not matched and position and source.get("side") == "buy":
        bucket = "filled_position_observed_unmatched_order_history"
        evidence = "current_position_observed_without_order_history_match"
    return {
        "source_path": source.get("source_path"),
        "submitted_at_utc": source.get("generated_at_utc"),
        "symbol": source.get("symbol"),
        "side": source.get("side"),
        "paper_order_status_at_submit": source.get("paper_order_status_at_submit"),
        "request": source.get("request"),
        "classification": bucket,
        "match_status": "matched" if matched else "unmatched",
        "match_score": best_score,
        "evidence": evidence,
        "order_history": sanitized,
        "position_cross_check": {
            "position_observed": bool(position),
            "qty": as_float(as_dict(position).get("qty") or as_dict(position).get("quantity")),
            "avg_entry_price": as_float(as_dict(position).get("avg_entry_price") or as_dict(position).get("average_entry_price")),
        },
        "next_safe_action": next_safe_action(bucket),
    }


def next_safe_action(bucket: str) -> str:
    if bucket in {"filled", "partially_filled", "filled_position_observed_unmatched_order_history"}:
        return "Update review-only paper lifecycle/outcome proof; any sell still needs exact owner approval and WF67 guard proof."
    if bucket in {"open_or_pending"}:
        return "Continue GET-only reconciliation; do not cancel or replace without exact owner approval."
    if bucket in {"expired", "canceled", "rejected", "replaced", "terminal_other"}:
        return "Record terminal paper-order outcome; any resubmission requires a new exact owner-approved request."
    return "Keep unresolved and continue GET-only order-history drilldown before making lifecycle claims."


def classify_orders(submitted: list[dict[str, Any]], orders: list[dict[str, Any]], positions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [classify_source(source, orders, positions) for source in submitted if source.get("symbol")]


def summary(classifications: list[dict[str, Any]]) -> dict[str, Any]:
    by_status: dict[str, int] = {}
    by_symbol: dict[str, dict[str, int]] = {}
    material_changes: list[dict[str, Any]] = []
    for row in classifications:
        status = str(row.get("classification") or "unresolved")
        symbol = str(row.get("symbol") or "UNKNOWN")
        by_status[status] = by_status.get(status, 0) + 1
        by_symbol.setdefault(symbol, {})
        by_symbol[symbol][status] = by_symbol[symbol].get(status, 0) + 1
        if status not in {"open_or_pending", "unresolved"}:
            material_changes.append({"symbol": symbol, "classification": status, "source_path": row.get("source_path")})
    return {
        "submitted_order_count": len(classifications),
        "classification_counts": dict(sorted(by_status.items())),
        "symbol_counts": dict(sorted(by_symbol.items())),
        "material_change_count": len(material_changes),
        "material_changes": material_changes,
        "open_or_pending_count": by_status.get("open_or_pending", 0),
        "filled_count": by_status.get("filled", 0) + by_status.get("filled_position_observed_unmatched_order_history", 0),
        "partially_filled_count": by_status.get("partially_filled", 0),
        "terminal_non_fill_count": sum(by_status.get(key, 0) for key in ("expired", "canceled", "rejected", "replaced", "terminal_other")),
        "unresolved_count": by_status.get("unresolved", 0),
    }


def validate_payload(payload: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    boundary = as_dict(payload.get("authority_boundary"))
    for key, expected in authority_boundary().items():
        if boundary.get(key) != expected:
            errors.append(f"authority_boundary_{key}_invalid")
    if payload.get("endpoint") != PAPER_BASE_URL:
        errors.append("endpoint_not_exact_paper")
    if payload.get("method") != "GET_only":
        errors.append("method_not_get_only")
    if as_dict(payload.get("summary")).get("unresolved_count", 0) > 0:
        warnings.append("unresolved_submitted_paper_orders_present")
    return {"status": "error" if errors else "warning" if warnings else "ok", "errors": errors, "warnings": warnings}


def build_payload(submitted: list[dict[str, Any]], orders: list[dict[str, Any]], positions: list[dict[str, Any]], *, blocked_reason: str | None = None) -> dict[str, Any]:
    classifications = [] if blocked_reason else classify_orders(submitted, orders, positions)
    payload = {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "blocked" if blocked_reason else "draft",
        "blocked_reason": blocked_reason,
        "endpoint": PAPER_BASE_URL,
        "method": "GET_only",
        "authority_boundary": authority_boundary(),
        "submitted_sources": submitted,
        "classifications": classifications,
        "summary": summary(classifications),
        "source_artifacts": {
            "submitted_execution_results_glob": "tmp/alpaca-paper-readiness/paper-execution-result*.json",
            "paper_trade_requests_glob": "tmp/alpaca-paper-readiness/paper-trade-request*.json",
            "audit_log": rel(DEFAULT_AUDIT_LOG),
        },
    }
    validation = validate_payload(payload)
    payload["validation"] = validation
    if blocked_reason:
        payload["status"] = "blocked"
    elif validation["status"] == "error":
        payload["status"] = "blocked"
    elif validation["status"] == "warning":
        payload["status"] = "warning"
    else:
        payload["status"] = "ok"
    return payload


def run_live(args: argparse.Namespace) -> dict[str, Any]:
    artifact_paths = [rel(args.out if args.out.is_absolute() else ROOT / args.out)]
    submitted = submitted_order_sources()
    try:
        session = make_session()
        since = (datetime.now(timezone.utc) - timedelta(days=args.days)).date().isoformat()
        orders_raw = get_json(
            session,
            "/v2/orders",
            params={"status": "all", "limit": args.limit, "direction": "desc", "after": since},
            timeout=args.timeout_seconds,
        )
        append_audit(audit_event("read_order_history", "observed", "ok", artifact_paths), Path(args.audit_log))
        positions_raw = get_json(session, "/v2/positions", params=None, timeout=args.timeout_seconds)
        append_audit(audit_event("read_positions", "observed", "ok", artifact_paths), Path(args.audit_log))
        orders = [item for item in as_list(orders_raw) if isinstance(item, dict)]
        positions = [item for item in as_list(positions_raw) if isinstance(item, dict)]
        payload = build_payload(submitted, orders, positions)
    except BlockedRun as exc:
        append_audit(audit_event("read_order_history", "blocked", str(exc), artifact_paths), Path(args.audit_log))
        payload = build_payload(submitted, [], [], blocked_reason=str(exc))
    return payload


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--audit-log", type=Path, default=DEFAULT_AUDIT_LOG)
    parser.add_argument("--days", type=int, default=45)
    parser.add_argument("--limit", type=int, default=500)
    parser.add_argument("--timeout-seconds", type=int, default=20)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    payload = run_live(args)
    out = args.out if args.out.is_absolute() else ROOT / args.out
    if args.write:
        atomic_write_json(out, payload)
    summary_payload = as_dict(payload.get("summary"))
    validation = as_dict(payload.get("validation"))
    print(
        "status={status} validation={validation} submitted={submitted} filled={filled} "
        "partial={partial} open={open_count} terminal={terminal} unresolved={unresolved}".format(
            status=payload.get("status"),
            validation=validation.get("status"),
            submitted=summary_payload.get("submitted_order_count"),
            filled=summary_payload.get("filled_count"),
            partial=summary_payload.get("partially_filled_count"),
            open_count=summary_payload.get("open_or_pending_count"),
            terminal=summary_payload.get("terminal_non_fill_count"),
            unresolved=summary_payload.get("unresolved_count"),
        )
    )
    for error in as_list(validation.get("errors")):
        print(f"  [error] {error}")
    for warning in as_list(validation.get("warnings")):
        print(f"  [warning] {warning}")
    return 1 if args.validate and validation.get("status") == "error" else 0


if __name__ == "__main__":
    raise SystemExit(main())
