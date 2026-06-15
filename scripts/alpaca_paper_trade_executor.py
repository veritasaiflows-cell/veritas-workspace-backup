#!/usr/bin/env python3
"""WF67 Alpaca paper-only submit/cancel wrapper.

Default mode is dry-run validation. Actual paper submit/cancel requires:
- --execute
- exact WF67 approval artifact
- short-lived WF67 kill switch enabling paper submit/cancel
- scoped paper-trade or paper-cancel request artifact
- paper-specific credential env names only
- exact paper endpoint only

This script must never use live endpoints, live credentials, money movement,
account settings, replace orders, close-position, liquidation, margin/options,
or inferred approval.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import requests

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "tmp" / "alpaca-paper-readiness"
DEFAULT_APPROVAL = BASE / "phase-6-paper-execution-approval.json"
DEFAULT_KILL_SWITCH = BASE / "kill-switch.json"
DEFAULT_AUDIT_LOG = BASE / "audit-log.jsonl"
DEFAULT_DRY_RUN_OUTPUT = BASE / "paper-execution-dry-run-result.json"
DEFAULT_EXECUTION_OUTPUT = BASE / "paper-execution-result.json"
DEFAULT_TRADE_REQUEST = BASE / "paper-trade-request.sample.json"
DEFAULT_CANCEL_REQUEST = BASE / "paper-cancel-request.sample.json"

WORKFLOW = "WF67 - Alpaca Paper Execution Guardrail"
PHASE = "phase_6_paper_execution_guardrail"
PAPER_BASE_URL = "https://paper-api.alpaca.markets"
LIVE_BASE_URL = "https://" + "api.alpaca.markets"
KEY_ENV = "ALPACA_PAPER_API_KEY_ID"
SECRET_ENV = "ALPACA_PAPER_API_SECRET_KEY"
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
MAX_KILL_SWITCH_MINUTES = 60
ALLOWED_SUBMIT_METHOD = "POST"
ALLOWED_CANCEL_METHOD = "DELETE"
ALLOWED_SUBMIT_PATH = "/v2/orders"
ALLOWED_CANCEL_PREFIX = "/v2/orders/"
ALLOWED_TIME_IN_FORCE = {"day", "gtc"}
MAX_PILOT_QTY = 1
MAX_PILOT_NOTIONAL_USD = 500.0
MAX_WF86_POLICY_NOTIONAL_USD = 5000.0


class BlockedRun(Exception):
    """Expected fail-closed block."""


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_utc(ts: str) -> datetime:
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        return str(path)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def load_json(path: Path, code: str) -> dict[str, Any]:
    if not path.exists():
        raise BlockedRun(f"missing_{code}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise BlockedRun(f"invalid_json_{code}") from exc


def resolve_workspace_path(path_value: Any, code: str) -> Path:
    if not isinstance(path_value, str) or not path_value.strip():
        raise BlockedRun(f"{code}_missing")
    candidate = Path(path_value)
    resolved = candidate if candidate.is_absolute() else ROOT / candidate
    try:
        resolved.relative_to(ROOT)
    except ValueError as exc:
        raise BlockedRun(f"{code}_outside_workspace") from exc
    return resolved


def validate_wf86_cap_policy(path_value: Any) -> float:
    """Return the approved WF86 paper cap when a request uses full-scope policy.

    This validates only notional scope. It does not grant autonomous execution,
    owner approval, kill-switch authority, or any live-account permission.
    """
    path = resolve_workspace_path(path_value, "full_scope_artifact")
    policy = load_json(path, "full_scope_artifact")
    if policy.get("schema") != "veritas.paper_autotrader_policy.v0":
        raise BlockedRun("full_scope_artifact_schema_invalid")
    if policy.get("workflow_id") != "WF86":
        raise BlockedRun("full_scope_artifact_workflow_not_wf86")
    authority = policy.get("authority_boundary") or {}
    expected = {
        "paper_only": True,
        "live_trade_allowed": False,
        "live_endpoint_allowed": False,
        "brokerage_or_account_action_allowed": False,
        "money_movement_allowed": False,
        "owner_approval_inferred": False,
    }
    for field, expected_value in expected.items():
        if authority.get(field) is not expected_value:
            raise BlockedRun(f"full_scope_artifact_authority_invalid:{field}")
    phase = policy.get("phase_1_decisions") or {}
    if phase.get("approved_by") != "Randall":
        raise BlockedRun("full_scope_artifact_not_owner_approved")
    cap = (policy.get("initial_caps") or {}).get("max_notional_per_order_usd")
    if not isinstance(cap, (int, float)) or cap <= MAX_PILOT_NOTIONAL_USD or cap > MAX_WF86_POLICY_NOTIONAL_USD:
        raise BlockedRun("full_scope_artifact_cap_invalid")
    return float(cap)


def allowed_notional_cap(payload: dict[str, Any]) -> float:
    risk = payload.get("risk_check") or {}
    cap = MAX_PILOT_NOTIONAL_USD
    if risk.get("full_scope_artifact"):
        cap = validate_wf86_cap_policy(risk.get("full_scope_artifact"))
    pilot_cap = risk.get("pilot_notional_cap_usd")
    if pilot_cap is not None and float(pilot_cap) != cap:
        raise BlockedRun("request_pilot_notional_cap_mismatch")
    return cap


def append_audit(event: dict[str, Any], audit_log: Path) -> None:
    audit_log.parent.mkdir(parents=True, exist_ok=True)
    with audit_log.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(event, sort_keys=True) + "\n")


def audit_event(
    *,
    action: str,
    method_class: str,
    endpoint_path_class: str,
    request_intent: str,
    result: str,
    reason_code: str,
    artifact_paths: list[str],
    approval_artifact_id: str | None,
    preview_id: str | None = None,
    validator_statuses: dict[str, Any] | None = None,
    kill_switch_status: str = "unknown",
    guard_status: str = "unknown",
) -> dict[str, Any]:
    return {
        "timestamp_utc": utc_now(),
        "workflow": WORKFLOW,
        "phase": PHASE,
        "event_id": f"wf67-{uuid.uuid4().hex[:12]}",
        "actor": "script",
        "action": action,
        "method_class": method_class,
        "endpoint_mode": "paper",
        "endpoint_path_class": endpoint_path_class,
        "request_intent": request_intent,
        "preview_id": preview_id,
        "approval_artifact_id": approval_artifact_id,
        "validator_statuses": validator_statuses or {},
        "kill_switch_status": kill_switch_status,
        "guard_status": guard_status,
        "result": result,
        "reason_code": reason_code,
        "artifact_paths": artifact_paths,
        "redaction_status": "redacted",
        "secret_material_present": False,
    }


def create_execution_kill_switch(path: Path, *, expires_minutes: int, approval_note: str) -> dict[str, Any]:
    if expires_minutes < 1 or expires_minutes > MAX_KILL_SWITCH_MINUTES:
        raise BlockedRun("kill_switch_ttl_out_of_bounds")
    payload = {
        "schema_version": 1,
        "workflow": WORKFLOW,
        "phase": PHASE,
        "generated_at_utc": utc_now(),
        "alpaca_access_enabled": True,
        "read_only_enabled": True,
        "paper_submit_enabled": True,
        "paper_cancel_enabled": True,
        "live_submit_enabled": False,
        "live_cancel_enabled": False,
        "endpoint": PAPER_BASE_URL,
        "allowed_methods": ["GET", ALLOWED_SUBMIT_METHOD, ALLOWED_CANCEL_METHOD],
        "allowed_paths": [ALLOWED_SUBMIT_PATH, ALLOWED_CANCEL_PREFIX + "{paper_order_id}"],
        "expires_at_utc": (datetime.now(timezone.utc) + timedelta(minutes=expires_minutes)).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "approved_by": "Randall",
        "approval_note": approval_note,
        "trade_or_account_action_allowed": True,
        "paper_only": True,
        "live_endpoint_forbidden": True,
        "no_inferred_approval": True,
    }
    write_json(path, payload)
    return payload


def validate_approval(payload: dict[str, Any]) -> str:
    approval_status = payload.get("approval_status")
    allowed_statuses = {
        "approved_in_principle_pending_guardrail_implementation",
        "approved_guardrails_implemented_pending_scoped_pilot",
        "approved_full_paper_trading_when_randall_approves_order_under_wf67_guardrails",
    }
    if payload.get("workflow") != WORKFLOW:
        raise BlockedRun("approval_wrong_workflow")
    if approval_status not in allowed_statuses:
        raise BlockedRun("approval_status_not_expected")

    if approval_status == "approved_full_paper_trading_when_randall_approves_order_under_wf67_guardrails":
        if payload.get("paper_only") is not True:
            raise BlockedRun("approval_required_true_missing:paper_only")
        for field in ("live_submit_allowed", "live_cancel_allowed", "money_movement_allowed", "account_settings_mutation_allowed"):
            if payload.get(field) is not False:
                raise BlockedRun(f"approval_forbidden_field_not_false:{field}")
        if payload.get("live_endpoint_forbidden") is not True:
            raise BlockedRun("approval_required_true_missing:live_endpoint_forbidden")
        if payload.get("owner_approval_inference_allowed") is not False:
            raise BlockedRun("approval_owner_approval_inference_not_false")
        if payload.get("per_order_owner_approval_required") is not True:
            raise BlockedRun("approval_per_order_owner_approval_required_missing")
        if payload.get("standing_autonomous_order_authority") is not False:
            raise BlockedRun("approval_autonomous_order_authority_not_false")
        if payload.get("required_endpoint") != PAPER_BASE_URL:
            raise BlockedRun("approval_endpoint_not_exact_paper")
        supported = (((payload.get("implementation_truth") or {}).get("current_single_order_wrapper_supports") or {}).get("time_in_force") or [])
        if "gtc" not in supported:
            raise BlockedRun("approval_gtc_not_enabled")
        return "ok"

    required_true = [
        "doctrine_exception_acknowledged",
        "paper_only",
        "paper_submit_allowed",
        "paper_cancel_allowed",
        "live_endpoint_forbidden",
        "live_credentials_forbidden",
        "secret_redaction_required",
        "scoped_paper_trade_artifact_required",
        "per_order_or_bounded_pilot_scope_required",
        "no_inferred_approval",
    ]
    required_false = [
        "live_submit_allowed",
        "live_cancel_allowed",
        "money_movement_allowed",
        "account_settings_mutation_allowed",
        "replace_order_allowed",
        "close_position_allowed",
        "liquidation_allowed",
        "paper_results_promote_to_live_allowed",
    ]
    if payload.get("allowed_endpoint") != PAPER_BASE_URL:
        raise BlockedRun("approval_endpoint_not_exact_paper")
    if set(payload.get("required_credential_names") or []) != {KEY_ENV, SECRET_ENV}:
        raise BlockedRun("approval_credentials_not_paper_specific")
    for field in required_true:
        if payload.get(field) is not True:
            raise BlockedRun(f"approval_required_true_missing:{field}")
    for field in required_false:
        if payload.get(field) is not False:
            raise BlockedRun(f"approval_forbidden_field_not_false:{field}")
    return "ok"


def validate_kill_switch(payload: dict[str, Any], *, action: str) -> str:
    if payload.get("workflow") != WORKFLOW or payload.get("phase") != PHASE:
        raise BlockedRun("kill_switch_wrong_workflow_or_phase")
    if payload.get("alpaca_access_enabled") is not True or payload.get("read_only_enabled") is not True:
        raise BlockedRun("kill_switch_access_disabled")
    if payload.get("endpoint") != PAPER_BASE_URL:
        raise BlockedRun("kill_switch_endpoint_not_exact_paper")
    if payload.get("live_submit_enabled") is not False or payload.get("live_cancel_enabled") is not False:
        raise BlockedRun("kill_switch_live_enabled")
    if payload.get("paper_only") is not True or payload.get("live_endpoint_forbidden") is not True:
        raise BlockedRun("kill_switch_not_paper_only")
    if payload.get("no_inferred_approval") is not True:
        raise BlockedRun("kill_switch_allows_inferred_approval")
    if action == "submit" and payload.get("paper_submit_enabled") is not True:
        raise BlockedRun("kill_switch_paper_submit_disabled")
    if action == "cancel" and payload.get("paper_cancel_enabled") is not True:
        raise BlockedRun("kill_switch_paper_cancel_disabled")
    methods = set(payload.get("allowed_methods") or [])
    if "GET" not in methods or ALLOWED_SUBMIT_METHOD not in methods or ALLOWED_CANCEL_METHOD not in methods:
        raise BlockedRun("kill_switch_methods_incomplete")
    expires = payload.get("expires_at_utc")
    if not isinstance(expires, str) or parse_utc(expires) <= datetime.now(timezone.utc):
        raise BlockedRun("kill_switch_missing_or_expired")
    return "ok"


def validate_credentials() -> str:
    ambiguous = sorted(name for name in AMBIGUOUS_OR_LIVE_NAMES if os.environ.get(name))
    if ambiguous:
        raise BlockedRun("ambiguous_or_live_credential_names_present")
    if not os.environ.get(KEY_ENV) or not os.environ.get(SECRET_ENV):
        raise BlockedRun("paper_credentials_absent")
    return "ok"


def validate_common_request(payload: dict[str, Any], artifact_type: str) -> str:
    if payload.get("schema_version") != 1:
        raise BlockedRun("request_schema_version_invalid")
    if payload.get("workflow") != WORKFLOW:
        raise BlockedRun("request_wrong_workflow")
    if payload.get("artifact_type") != artifact_type:
        raise BlockedRun("request_wrong_artifact_type")
    if not payload.get("request_id"):
        raise BlockedRun("request_id_missing")
    authority = payload.get("authority") or {}
    for field in ("paper_only", "live_endpoint_forbidden", "no_inferred_approval"):
        if authority.get(field) is not True:
            raise BlockedRun(f"request_authority_true_missing:{field}")
    for field in ("live_submit_allowed", "live_cancel_allowed", "money_movement_allowed", "account_settings_mutation_allowed"):
        if authority.get(field) is not False:
            raise BlockedRun(f"request_authority_false_missing:{field}")
    source = payload.get("source") or {}
    if source.get("scoped_paper_trade_or_pilot") is not True:
        raise BlockedRun("scoped_paper_trade_or_pilot_missing")
    if source.get("owner_or_pilot_scope") in (None, ""):
        raise BlockedRun("owner_or_pilot_scope_missing")
    audit = payload.get("audit") or {}
    if audit.get("secret_material_present") is not False:
        raise BlockedRun("request_secret_material_present")
    return "ok"


def validate_trade_request(payload: dict[str, Any]) -> str:
    validate_common_request(payload, "wf67_paper_trade_request")
    authority = payload.get("authority") or {}
    if authority.get("paper_submit_allowed") is not True:
        raise BlockedRun("request_paper_submit_not_allowed")
    order = payload.get("order") or {}
    order_type = order.get("type")
    time_in_force = order.get("time_in_force")
    if order_type not in {"limit", "market"} or time_in_force not in ALLOWED_TIME_IN_FORCE:
        raise BlockedRun("request_order_scope_not_limit_or_market_day_or_gtc")
    if time_in_force == "gtc" and order_type != "limit":
        raise BlockedRun("request_gtc_requires_limit_order")
    source = payload.get("source") or {}
    if order_type == "market" and source.get("market_order_owner_approved") is not True:
        raise BlockedRun("request_market_order_missing_explicit_owner_approval")
    symbol = order.get("symbol")
    if not isinstance(symbol, str) or not symbol or symbol.upper() != symbol:
        raise BlockedRun("request_symbol_invalid")
    if order.get("side") not in {"buy", "sell"}:
        raise BlockedRun("request_side_invalid")
    limit_price = order.get("limit_price")
    if order_type == "limit" and (not isinstance(limit_price, (int, float)) or limit_price <= 0):
        raise BlockedRun("request_limit_price_invalid")
    if order_type == "market" and limit_price is not None:
        raise BlockedRun("request_market_order_limit_price_must_be_null_or_absent")
    qty = order.get("qty")
    notional = order.get("notional")
    if (qty is None and notional is None) or (qty is not None and notional is not None):
        raise BlockedRun("request_exactly_one_qty_or_notional_required")
    if qty is not None and (not isinstance(qty, (int, float)) or qty <= 0):
        raise BlockedRun("request_qty_invalid")
    if notional is not None and (not isinstance(notional, (int, float)) or notional <= 0):
        raise BlockedRun("request_notional_invalid")
    risk = payload.get("risk_check") or {}
    notional_cap = allowed_notional_cap(payload)
    if order_type == "market":
        estimated_notional = float(risk.get("estimated_notional_usd") or risk.get("max_notional_usd") or 0)
    else:
        estimated_notional = float(notional if notional is not None else qty * order["limit_price"])
    if qty is not None and float(qty) > MAX_PILOT_QTY:
        raise BlockedRun("request_qty_exceeds_pilot_cap")
    if estimated_notional > notional_cap:
        raise BlockedRun("request_notional_exceeds_pilot_cap")
    if risk.get("status") != "ok":
        raise BlockedRun("request_risk_check_not_ok")
    if risk.get("position_size_reviewed") is not True:
        raise BlockedRun("request_position_size_not_reviewed")
    max_loss = risk.get("max_loss_usd")
    max_notional = risk.get("max_notional_usd")
    if not isinstance(max_loss, (int, float)) or max_loss < 0:
        raise BlockedRun("request_max_loss_invalid")
    if not isinstance(max_notional, (int, float)) or max_notional <= 0:
        raise BlockedRun("request_max_notional_invalid")
    if float(max_notional) > notional_cap or estimated_notional > float(max_notional):
        raise BlockedRun("request_risk_notional_cap_failed")
    if float(max_loss) > float(max_notional):
        raise BlockedRun("request_max_loss_exceeds_notional")
    return "ok"


def validate_cancel_request(payload: dict[str, Any]) -> str:
    validate_common_request(payload, "wf67_paper_cancel_request")
    authority = payload.get("authority") or {}
    if authority.get("paper_cancel_allowed") is not True:
        raise BlockedRun("request_paper_cancel_not_allowed")
    cancel = payload.get("cancel") or {}
    if not cancel.get("paper_order_id") or not isinstance(cancel.get("paper_order_id"), str):
        raise BlockedRun("cancel_order_id_missing")
    if not cancel.get("reason") or len(str(cancel.get("reason"))) < 5:
        raise BlockedRun("cancel_reason_missing")
    return "ok"


def validate_not_sample_for_execute(payload: dict[str, Any]) -> str:
    request_id = str(payload.get("request_id") or "").lower()
    scope = str((payload.get("source") or {}).get("owner_or_pilot_scope") or "").lower()
    if "sample" in request_id or "do not execute" in scope or "sample only" in scope:
        raise BlockedRun("sample_request_cannot_execute")
    return "ok"


def validate_exact_order_owner_approval_for_execute(payload: dict[str, Any]) -> str:
    """Require per-order owner approval before any submit/sell execution.

    Standing WF67 approval permits the guarded paper lane, but it does not let a
    generated recommendation/request artifact execute itself. Dry-runs may use a
    pending approval status; --execute must carry exact order approval metadata.
    """
    source = payload.get("source") or {}
    status = source.get("exact_order_owner_approval_status")
    if status not in {"approved", "approved_exact_order"}:
        raise BlockedRun("exact_order_owner_approval_missing_for_execute")
    if source.get("approved_by") != "Randall":
        raise BlockedRun("exact_order_owner_approval_not_randall")
    approval_text = str(source.get("exact_order_owner_approval_text") or "").strip()
    if len(approval_text) < 20:
        raise BlockedRun("exact_order_owner_approval_text_missing")
    order = payload.get("order") or {}
    required_terms = [order.get("symbol"), order.get("side"), order.get("type"), order.get("time_in_force")]
    if not all(required_terms):
        raise BlockedRun("exact_order_owner_approval_order_terms_incomplete")
    if order.get("qty") is None and order.get("notional") is None:
        raise BlockedRun("exact_order_owner_approval_size_missing")
    return "ok"


def make_session() -> requests.Session:
    session = requests.Session()
    session.headers.update({
        "APCA-API-KEY-ID": os.environ[KEY_ENV],
        "APCA-API-SECRET-KEY": os.environ[SECRET_ENV],
        "Accept": "application/json",
        "Content-Type": "application/json",
    })
    return session


def post_paper_order(session: requests.Session, request_payload: dict[str, Any], *, timeout: int) -> tuple[int, dict[str, Any]]:
    url = PAPER_BASE_URL + ALLOWED_SUBMIT_PATH
    if not url.startswith(PAPER_BASE_URL) or url.startswith(LIVE_BASE_URL):
        raise BlockedRun("endpoint_not_exact_paper")
    order = request_payload["order"]
    order_type = order["type"]
    body = {
        "symbol": order["symbol"],
        "side": order["side"],
        "type": order_type,
        "time_in_force": order["time_in_force"],
    }
    if order_type == "limit":
        body["limit_price"] = str(order["limit_price"])
    if order.get("qty") is not None:
        body["qty"] = str(order["qty"])
    else:
        body["notional"] = str(order["notional"])
    response = session.request(ALLOWED_SUBMIT_METHOD, url, json=body, timeout=timeout)
    redacted = {"http_status": response.status_code, "paper_order_id_present": False, "symbol": order["symbol"], "side": order["side"]}
    if 200 <= response.status_code < 300:
        try:
            data = response.json()
            redacted["paper_order_id_present"] = bool(data.get("id"))
            redacted["paper_order_status"] = data.get("status")
            redacted["paper_order_symbol"] = data.get("symbol")
        except Exception:  # noqa: BLE001
            redacted["paper_order_parse_status"] = "unavailable"
    return response.status_code, redacted


def delete_paper_order(session: requests.Session, request_payload: dict[str, Any], *, timeout: int) -> tuple[int, dict[str, Any]]:
    order_id = request_payload["cancel"]["paper_order_id"]
    endpoint_path = ALLOWED_CANCEL_PREFIX + order_id
    url = PAPER_BASE_URL + endpoint_path
    if not url.startswith(PAPER_BASE_URL) or url.startswith(LIVE_BASE_URL):
        raise BlockedRun("endpoint_not_exact_paper")
    response = session.request(ALLOWED_CANCEL_METHOD, url, timeout=timeout)
    return response.status_code, {"http_status": response.status_code, "paper_order_id_present": bool(order_id)}


def sample_trade_request() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "workflow": WORKFLOW,
        "artifact_type": "wf67_paper_trade_request",
        "request_id": "sample-not-executable",
        "created_at_utc": utc_now(),
        "authority": {
            "paper_only": True,
            "paper_submit_allowed": True,
            "paper_cancel_allowed": True,
            "live_submit_allowed": False,
            "live_cancel_allowed": False,
            "live_endpoint_forbidden": True,
            "money_movement_allowed": False,
            "account_settings_mutation_allowed": False,
            "no_inferred_approval": True,
        },
        "order": {"symbol": "MSFT", "side": "buy", "type": "limit", "time_in_force": "day", "limit_price": 1.0, "qty": 1, "notional": None},
        "risk_check": {"status": "ok", "max_loss_usd": 1.0, "max_notional_usd": 1.0, "position_size_reviewed": True, "pilot_qty_cap": MAX_PILOT_QTY, "pilot_notional_cap_usd": MAX_PILOT_NOTIONAL_USD},
        "source": {"scoped_paper_trade_or_pilot": True, "owner_or_pilot_scope": "sample only - do not execute", "recommendation_source": "manual_sample"},
        "audit": {"secret_material_present": False, "raw_response_persistence_allowed": False},
    }


def sample_cancel_request() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "workflow": WORKFLOW,
        "artifact_type": "wf67_paper_cancel_request",
        "request_id": "sample-cancel-not-executable",
        "created_at_utc": utc_now(),
        "authority": {
            "paper_only": True,
            "paper_submit_allowed": False,
            "paper_cancel_allowed": True,
            "live_submit_allowed": False,
            "live_cancel_allowed": False,
            "live_endpoint_forbidden": True,
            "money_movement_allowed": False,
            "account_settings_mutation_allowed": False,
            "no_inferred_approval": True,
        },
        "cancel": {"paper_order_id": "sample-order-id", "symbol": "MSFT", "reason": "sample only - do not execute"},
        "source": {"scoped_paper_trade_or_pilot": True, "owner_or_pilot_scope": "sample only - do not execute"},
        "audit": {"secret_material_present": False, "raw_response_persistence_allowed": False},
    }


def run(args: argparse.Namespace) -> int:
    BASE.mkdir(parents=True, exist_ok=True)
    if args.init_samples:
        write_json(DEFAULT_TRADE_REQUEST, sample_trade_request())
        write_json(DEFAULT_CANCEL_REQUEST, sample_cancel_request())
        print(json.dumps({"status": "ok", "created": [rel(DEFAULT_TRADE_REQUEST), rel(DEFAULT_CANCEL_REQUEST)], "execute_allowed": False}, indent=2))
        return 0

    action = "cancel" if args.cancel_request else "submit"
    request_path = Path(args.cancel_request or args.trade_request)
    approval_path = Path(args.approval)
    kill_switch_path = Path(args.kill_switch)
    output_path = Path(args.output or (DEFAULT_EXECUTION_OUTPUT if args.execute else DEFAULT_DRY_RUN_OUTPUT))
    audit_log = Path(args.audit_log)
    artifacts = [rel(request_path), rel(output_path)]
    approval_artifact_id = rel(approval_path)
    generated_at = utc_now()

    try:
        if args.create_execution_kill_switch:
            create_execution_kill_switch(kill_switch_path, expires_minutes=args.expires_minutes, approval_note=args.approval_note)

        approval = load_json(approval_path, "approval")
        approval_status = validate_approval(approval)
        request_payload = load_json(request_path, "request")
        request_status = validate_cancel_request(request_payload) if action == "cancel" else validate_trade_request(request_payload)
        if args.execute:
            validate_not_sample_for_execute(request_payload)
            if action == "submit":
                validate_exact_order_owner_approval_for_execute(request_payload)
        kill_switch = load_json(kill_switch_path, "kill_switch")
        kill_switch_status = validate_kill_switch(kill_switch, action=action)
        credential_status = "not_required_for_dry_run"
        if args.execute:
            credential_status = validate_credentials()

        result_payload: dict[str, Any] = {
            "schema_version": 1,
            "workflow": WORKFLOW,
            "phase": PHASE,
            "artifact_type": "wf67_paper_execution_result",
            "generated_at_utc": generated_at,
            "status": "validated_dry_run" if not args.execute else "pending",
            "action": action,
            "execute_requested": bool(args.execute),
            "endpoint": PAPER_BASE_URL,
            "live_endpoint_detected": False,
            "approval_status": approval_status,
            "request_status": request_status,
            "kill_switch_status": kill_switch_status,
            "credential_status": credential_status,
            "secrets_persisted": False,
            "headers_persisted": False,
            "raw_response_bodies_persisted": False,
            "money_movement_allowed": False,
            "account_settings_mutation_allowed": False,
            "live_submit_allowed": False,
            "no_inferred_approval": True,
        }

        if args.execute:
            session = make_session()
            if action == "cancel":
                http_status, redacted = delete_paper_order(session, request_payload, timeout=args.timeout_seconds)
                ok = 200 <= http_status < 300
                result_payload.update({"status": "cancelled" if ok else "blocked", "broker_redacted_result": redacted})
            else:
                http_status, redacted = post_paper_order(session, request_payload, timeout=args.timeout_seconds)
                ok = 200 <= http_status < 300
                result_payload.update({"status": "submitted" if ok else "blocked", "broker_redacted_result": redacted})
        write_json(output_path, result_payload)
        append_audit(audit_event(
            action=f"paper_{action}",
            method_class=ALLOWED_CANCEL_METHOD if action == "cancel" else ALLOWED_SUBMIT_METHOD,
            endpoint_path_class=ALLOWED_CANCEL_PREFIX + "{paper_order_id}" if action == "cancel" else ALLOWED_SUBMIT_PATH,
            request_intent=f"paper_{action}_dry_run" if not args.execute else f"paper_{action}_execute",
            result=result_payload["status"],
            reason_code="validated" if not args.execute else result_payload["status"],
            artifact_paths=artifacts,
            approval_artifact_id=approval_artifact_id,
            validator_statuses={"approval": approval_status, "request": request_status},
            kill_switch_status=kill_switch_status,
            guard_status="wf67_wrapper_gate_passed",
        ), audit_log)
        print(json.dumps({"status": result_payload["status"], "result_path": rel(output_path), "action": action, "execute_requested": bool(args.execute)}, indent=2))
        return 0 if result_payload["status"] in {"validated_dry_run", "submitted", "cancelled"} else 2

    except BlockedRun as exc:
        reason = str(exc)
        blocked = {
            "schema_version": 1,
            "workflow": WORKFLOW,
            "phase": PHASE,
            "artifact_type": "wf67_paper_execution_result",
            "generated_at_utc": generated_at,
            "status": "blocked",
            "action": action,
            "execute_requested": bool(args.execute),
            "blocked_reason": reason,
            "endpoint": PAPER_BASE_URL,
            "live_endpoint_detected": False,
            "secrets_persisted": False,
            "raw_response_bodies_persisted": False,
            "no_inferred_approval": True,
        }
        write_json(output_path, blocked)
        append_audit(audit_event(
            action=f"block_paper_{action}",
            method_class="NONE",
            endpoint_path_class="none",
            request_intent=f"paper_{action}",
            result="blocked",
            reason_code=reason,
            artifact_paths=artifacts,
            approval_artifact_id=approval_artifact_id,
            kill_switch_status="blocked",
            guard_status="blocked",
        ), audit_log)
        print(json.dumps({"status": "blocked", "blocked_reason": reason, "result_path": rel(output_path)}, indent=2))
        return 2


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--trade-request", default=str(DEFAULT_TRADE_REQUEST))
    parser.add_argument("--cancel-request", default=None)
    parser.add_argument("--approval", default=str(DEFAULT_APPROVAL))
    parser.add_argument("--kill-switch", default=str(DEFAULT_KILL_SWITCH))
    parser.add_argument("--audit-log", default=str(DEFAULT_AUDIT_LOG))
    parser.add_argument("--output", default=None)
    parser.add_argument("--timeout-seconds", type=int, default=15)
    parser.add_argument("--execute", action="store_true", help="Actually submit/cancel a paper order after all gates validate.")
    parser.add_argument("--create-execution-kill-switch", action="store_true", help="Create a short-lived WF67 paper execution kill switch.")
    parser.add_argument("--expires-minutes", type=int, default=30)
    parser.add_argument("--approval-note", default="Randall approved WF67 paper-only submit/cancel readiness; this kill switch is paper-only and scoped by request artifacts.")
    parser.add_argument("--init-samples", action="store_true")
    return run(parser.parse_args())


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001
        print(json.dumps({"status": "blocked", "blocked_reason": "unexpected_runner_error", "error_type": type(exc).__name__, "secrets_redacted": True}, indent=2), file=sys.stderr)
        raise SystemExit(2)
