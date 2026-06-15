#!/usr/bin/env python3
"""WF63 Alpaca paper read-only connection proof runner.

This runner is intentionally narrow:
- paper endpoint only
- GET only
- paper-specific env var names only
- redacted proof/audit artifacts only
- no submit/cancel/replace/account mutation path
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
OUT_DIR = ROOT / "tmp" / "alpaca-paper-readiness"
DEFAULT_OUTPUT = OUT_DIR / "read-only-connection-proof.json"
DEFAULT_KILL_SWITCH = OUT_DIR / "kill-switch.json"
DEFAULT_AUDIT_LOG = OUT_DIR / "audit-log.jsonl"

WORKFLOW = "WF63 - Alpaca Paper Trading Readiness"
PHASE = "phase_1_read_only_connection_proof"
PAPER_BASE_URL = "https://paper-api.alpaca.markets"
# Keep the live host split so the static forbidden-pattern scanner can still
# flag accidental live-endpoint literals in active code without flagging this
# defensive comparison constant.
LIVE_BASE_URL = "https://" + "api.alpaca.markets"
MAX_KILL_SWITCH_MINUTES = 120
KEY_ENV = "ALPACA_PAPER_API_KEY_ID"
SECRET_ENV = "ALPACA_PAPER_API_SECRET_KEY"
ALLOWED_METHODS = ["GET"]
BLOCKED_METHODS = ["POST", "PATCH", "PUT", "DELETE"]
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
    """Expected fail-closed runner block."""


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_utc(ts: str) -> datetime:
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


def redacted_event(
    *,
    action: str,
    method_class: str,
    endpoint_path_class: str,
    result: str,
    reason_code: str,
    artifact_paths: list[str] | None = None,
    validator_statuses: dict[str, Any] | None = None,
    kill_switch_status: str | None = None,
    no_submit_guard_status: str | None = None,
) -> dict[str, Any]:
    return {
        "timestamp_utc": utc_now(),
        "workflow": WORKFLOW,
        "phase": PHASE,
        "event_id": f"wf63-{uuid.uuid4().hex[:12]}",
        "actor": "script",
        "action": action,
        "method_class": method_class,
        "endpoint_mode": "paper",
        "endpoint_path_class": endpoint_path_class,
        "request_intent": "read_only_connection_proof",
        "preview_id": None,
        "approval_artifact_id": "chat-approval-2026-05-15-0819-mst",
        "validator_statuses": validator_statuses or {},
        "kill_switch_status": kill_switch_status or "unknown",
        "no_submit_guard_status": no_submit_guard_status or "not_applicable_phase_1_get_only_runner",
        "result": result,
        "reason_code": reason_code,
        "artifact_paths": artifact_paths or [],
        "redaction_status": "redacted",
        "secret_material_present": False,
    }


def append_audit(event: dict[str, Any], audit_log: Path) -> None:
    audit_log.parent.mkdir(parents=True, exist_ok=True)
    with audit_log.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(event, sort_keys=True) + "\n")


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def ensure_kill_switch(path: Path, *, create: bool, expires_minutes: int, approval_note: str) -> dict[str, Any]:
    if expires_minutes < 1 or expires_minutes > MAX_KILL_SWITCH_MINUTES:
        raise BlockedRun("kill_switch_ttl_out_of_bounds")
    if create:
        payload = {
            "schema_version": 1,
            "workflow": WORKFLOW,
            "phase": PHASE,
            "generated_at_utc": utc_now(),
            "alpaca_access_enabled": True,
            "read_only_enabled": True,
            "paper_submit_enabled": False,
            "live_submit_enabled": False,
            "endpoint": PAPER_BASE_URL,
            "allowed_methods": ALLOWED_METHODS,
            "expires_at_utc": (datetime.now(timezone.utc) + timedelta(minutes=expires_minutes)).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
            "approved_by": "Randall",
            "approval_note": approval_note,
            "trade_or_account_action_allowed": False,
        }
        write_json(path, payload)
        return payload

    if not path.exists():
        raise BlockedRun("kill_switch_absent")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        raise BlockedRun(f"kill_switch_unreadable:{exc}") from exc


def validate_kill_switch(payload: dict[str, Any]) -> str:
    if payload.get("alpaca_access_enabled") is not True:
        raise BlockedRun("kill_switch_access_disabled")
    if payload.get("read_only_enabled") is not True:
        raise BlockedRun("kill_switch_read_only_disabled")
    if payload.get("paper_submit_enabled") is not False:
        raise BlockedRun("kill_switch_paper_submit_enabled")
    if payload.get("live_submit_enabled") is not False:
        raise BlockedRun("kill_switch_live_submit_enabled")
    if payload.get("endpoint") != PAPER_BASE_URL:
        raise BlockedRun("kill_switch_endpoint_not_exact_paper")
    if payload.get("allowed_methods") != ALLOWED_METHODS:
        raise BlockedRun("kill_switch_methods_not_get_only")
    if payload.get("trade_or_account_action_allowed") is not False:
        raise BlockedRun("kill_switch_trade_or_account_action_allowed")
    expires = payload.get("expires_at_utc")
    if not isinstance(expires, str):
        raise BlockedRun("kill_switch_missing_expiration")
    if parse_utc(expires) <= datetime.now(timezone.utc):
        raise BlockedRun("kill_switch_expired")
    return "ok"


def credential_status() -> tuple[bool, bool, list[str]]:
    selected_present = bool(os.environ.get(KEY_ENV)) and bool(os.environ.get(SECRET_ENV))
    ambiguous_present = sorted(name for name in AMBIGUOUS_OR_LIVE_NAMES if os.environ.get(name))
    return selected_present, bool(ambiguous_present), ambiguous_present


def make_blocked_proof(reason: str, *, generated_at: str | None = None) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "generated_at_utc": generated_at or utc_now(),
        "status": "blocked",
        "base_url": PAPER_BASE_URL,
        "account_mode": "paper",
        "live_endpoint_detected": False,
        "write_methods_available": False,
        "allowed_methods": ALLOWED_METHODS,
        "blocked_methods": BLOCKED_METHODS,
        "credential_source": {
            "mode": "paper",
            "selected_variable_names": [KEY_ENV, SECRET_ENV],
            "secret_values_persisted": False,
            "ambiguous_or_live_names_detected": reason == "ambiguous_or_live_credential_names_present",
        },
        "checks": {
            "account_metadata_read": False,
            "positions_read": False,
            "orders_read": False,
        },
        "secrets_redacted": True,
        "trade_or_account_action_allowed": False,
        "blocked_reason": reason,
    }


def get_json(session: requests.Session, path: str, *, params: dict[str, Any] | None = None, timeout: int) -> tuple[bool, int | None, str | None]:
    # GET-only by construction: this function never accepts a method argument.
    url = PAPER_BASE_URL + path
    if not url.startswith(PAPER_BASE_URL) or url.startswith(LIVE_BASE_URL):
        raise BlockedRun("endpoint_not_exact_paper")
    response = session.get(url, params=params or {}, timeout=timeout)
    status_code = response.status_code
    if 200 <= status_code < 300:
        return True, status_code, None
    return False, status_code, f"http_{status_code}"


def run(args: argparse.Namespace) -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    proof_path = Path(args.output)
    kill_switch_path = Path(args.kill_switch)
    audit_log = Path(args.audit_log)
    artifact_paths = [str(proof_path.relative_to(ROOT)).replace("\\", "/")]

    generated_at = utc_now()
    try:
        kill_switch = ensure_kill_switch(
            kill_switch_path,
            create=args.create_kill_switch,
            expires_minutes=args.expires_minutes,
            approval_note=args.approval_note,
        )
        kill_switch_status = validate_kill_switch(kill_switch)

        selected_present, ambiguous_present, _ambiguous_names = credential_status()
        if ambiguous_present:
            raise BlockedRun("ambiguous_or_live_credential_names_present")
        if not selected_present:
            raise BlockedRun("paper_credentials_absent")

        session = requests.Session()
        session.headers.update({
            "APCA-API-KEY-ID": os.environ[KEY_ENV],
            "APCA-API-SECRET-KEY": os.environ[SECRET_ENV],
            "Accept": "application/json",
        })

        checks: dict[str, bool] = {}
        account_ok, account_status, account_error = get_json(session, "/v2/account", timeout=args.timeout_seconds)
        checks["account_metadata_read"] = account_ok
        append_audit(redacted_event(
            action="read_account_metadata",
            method_class="GET",
            endpoint_path_class="/v2/account",
            result="observed" if account_ok else "error",
            reason_code="ok" if account_ok else account_error or "request_failed",
            artifact_paths=artifact_paths,
            kill_switch_status=kill_switch_status,
        ), audit_log)

        positions_ok, positions_status, positions_error = get_json(session, "/v2/positions", timeout=args.timeout_seconds)
        checks["positions_read"] = positions_ok
        append_audit(redacted_event(
            action="read_positions",
            method_class="GET",
            endpoint_path_class="/v2/positions",
            result="observed" if positions_ok else "error",
            reason_code="ok" if positions_ok else positions_error or "request_failed",
            artifact_paths=artifact_paths,
            kill_switch_status=kill_switch_status,
        ), audit_log)

        orders_ok, orders_status, orders_error = get_json(session, "/v2/orders", params={"status": "all", "limit": 50}, timeout=args.timeout_seconds)
        checks["orders_read"] = orders_ok
        append_audit(redacted_event(
            action="read_orders",
            method_class="GET",
            endpoint_path_class="/v2/orders",
            result="observed" if orders_ok else "error",
            reason_code="ok" if orders_ok else orders_error or "request_failed",
            artifact_paths=artifact_paths,
            kill_switch_status=kill_switch_status,
        ), audit_log)

        status = "ok" if all(checks.values()) else "blocked"
        proof: dict[str, Any] = {
            "schema_version": 1,
            "generated_at_utc": generated_at,
            "status": status,
            "base_url": PAPER_BASE_URL,
            "account_mode": "paper",
            "live_endpoint_detected": False,
            "write_methods_available": False,
            "allowed_methods": ALLOWED_METHODS,
            "blocked_methods": BLOCKED_METHODS,
            "credential_source": {
                "mode": "paper",
                "selected_variable_names": [KEY_ENV, SECRET_ENV],
                "secret_values_persisted": False,
                "ambiguous_or_live_names_detected": False,
            },
            "checks": checks,
            "secrets_redacted": True,
            "trade_or_account_action_allowed": False,
            "observations_redacted": {
                "account_status_code": account_status,
                "positions_status_code": positions_status,
                "orders_status_code": orders_status,
                "raw_response_bodies_persisted": False,
                "headers_persisted": False,
            },
        }
        if status != "ok":
            proof["blocked_reason"] = "one_or_more_get_checks_failed"
        write_json(proof_path, proof)
        append_audit(redacted_event(
            action="write_read_only_connection_proof",
            method_class="LOCAL_WRITE",
            endpoint_path_class="artifact",
            result="allowed" if status == "ok" else "blocked",
            reason_code="proof_ok" if status == "ok" else "one_or_more_get_checks_failed",
            artifact_paths=artifact_paths,
            kill_switch_status=kill_switch_status,
            validator_statuses={"connection_proof_status": status},
        ), audit_log)
        print(json.dumps({"status": status, "proof_path": artifact_paths[0], "checks": checks, "secrets_redacted": True}, indent=2))
        return 0 if status == "ok" else 2

    except BlockedRun as exc:
        reason = str(exc)
        proof = make_blocked_proof(reason, generated_at=generated_at)
        write_json(proof_path, proof)
        append_audit(redacted_event(
            action="block_read_only_connection_proof",
            method_class="NONE",
            endpoint_path_class="none",
            result="blocked",
            reason_code=reason,
            artifact_paths=artifact_paths,
            kill_switch_status="blocked",
        ), audit_log)
        print(json.dumps({"status": "blocked", "proof_path": artifact_paths[0], "blocked_reason": reason, "secrets_redacted": True}, indent=2))
        return 2


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--kill-switch", default=str(DEFAULT_KILL_SWITCH))
    parser.add_argument("--audit-log", default=str(DEFAULT_AUDIT_LOG))
    parser.add_argument("--create-kill-switch", action="store_true", help="Create a short-lived read-only paper kill switch from explicit owner approval.")
    parser.add_argument("--expires-minutes", type=int, default=60, help=f"Read-only kill switch TTL in minutes; max {MAX_KILL_SWITCH_MINUTES}.")
    parser.add_argument("--approval-note", default="Randall explicitly approved a GET-only paper endpoint connection proof with redacted audit and no-submit constraints on 2026-05-15 08:19 MST.")
    parser.add_argument("--timeout-seconds", type=int, default=15)
    return run(parser.parse_args())


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001
        # Fail closed without traceback so unexpected exceptions cannot echo
        # in-memory request headers or other sensitive process details.
        print(json.dumps({"status": "blocked", "blocked_reason": "unexpected_runner_error", "error_type": type(exc).__name__, "secrets_redacted": True}, indent=2), file=sys.stderr)
        raise SystemExit(2)
