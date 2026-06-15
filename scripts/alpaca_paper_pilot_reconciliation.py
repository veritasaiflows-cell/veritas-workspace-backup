#!/usr/bin/env python3
"""WF67 paper pilot reconciliation.

Read-only paper-account reconciliation for a scoped WF67 submit/cancel pilot.
It fetches only the named paper order, persists only redacted lifecycle fields,
and never submits/cancels/replaces/orders/account mutations.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "tmp" / "alpaca-paper-readiness"
DEFAULT_TRADE_REQUEST = BASE / "paper-trade-request.wf67-pilot-001.json"
DEFAULT_CANCEL_REQUEST = BASE / "paper-cancel-request.wf67-pilot-001.json"
DEFAULT_EXECUTION_RESULT = BASE / "paper-execution-result.json"
DEFAULT_DRY_RUN_RESULT = BASE / "paper-execution-dry-run-result.json"
DEFAULT_GUARD_VALIDATION = BASE / "paper-execution-guard-validation.json"
DEFAULT_WF63_READINESS = BASE / "wf63-readiness-report.json"
DEFAULT_OUTPUT = BASE / "paper-pilot-reconciliation.wf67-pilot-001.json"
DEFAULT_MD_OUTPUT = BASE / "paper-pilot-reconciliation.wf67-pilot-001.md"

WORKFLOW = "WF67 - Alpaca Paper Execution Guardrail"
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


class BlockedRun(Exception):
    pass


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        return str(path)


def load_json(path: Path, code: str) -> dict[str, Any]:
    if not path.exists():
        raise BlockedRun(f"missing_{code}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise BlockedRun(f"invalid_json_{code}") from exc


def validate_credentials() -> None:
    ambiguous = sorted(name for name in AMBIGUOUS_OR_LIVE_NAMES if os.environ.get(name))
    if ambiguous:
        raise BlockedRun("ambiguous_or_live_credential_names_present")
    if not os.environ.get(KEY_ENV) or not os.environ.get(SECRET_ENV):
        raise BlockedRun("paper_credentials_absent")


def fetch_order(order_id: str, *, timeout: int) -> dict[str, Any]:
    validate_credentials()
    endpoint = f"/v2/orders/{order_id}"
    url = PAPER_BASE_URL + endpoint
    if not url.startswith(PAPER_BASE_URL) or url.startswith(LIVE_BASE_URL):
        raise BlockedRun("endpoint_not_exact_paper")
    session = requests.Session()
    session.headers.update({
        "APCA-API-KEY-ID": os.environ[KEY_ENV],
        "APCA-API-SECRET-KEY": os.environ[SECRET_ENV],
        "Accept": "application/json",
    })
    response = session.get(url, timeout=timeout)
    if not 200 <= response.status_code < 300:
        raise BlockedRun(f"order_read_http_{response.status_code}")
    data = response.json()
    return {
        "symbol": data.get("symbol"),
        "side": data.get("side"),
        "type": data.get("type"),
        "time_in_force": data.get("time_in_force"),
        "limit_price": data.get("limit_price"),
        "qty": data.get("qty"),
        "status": data.get("status"),
        "created_at": data.get("created_at"),
        "submitted_at": data.get("submitted_at"),
        "canceled_at": data.get("canceled_at"),
        "expired_at": data.get("expired_at"),
        "expires_at": data.get("expires_at"),
        "filled_at": data.get("filled_at"),
        "filled_qty": data.get("filled_qty"),
        "order_id_present": bool(data.get("id")),
    }


def build_report(args: argparse.Namespace) -> dict[str, Any]:
    trade = load_json(Path(args.trade_request), "trade_request")
    cancel = load_json(Path(args.cancel_request), "cancel_request")
    execution = load_json(Path(args.execution_result), "execution_result")
    dry_run = load_json(Path(args.dry_run_result), "dry_run_result")
    guard = load_json(Path(args.guard_validation), "guard_validation")
    wf63 = load_json(Path(args.wf63_readiness), "wf63_readiness")

    order_id = ((cancel.get("cancel") or {}).get("paper_order_id"))
    if not order_id:
        raise BlockedRun("cancel_artifact_missing_order_id")
    order = fetch_order(order_id, timeout=args.timeout_seconds)

    expected = {
        "symbol": ((trade.get("order") or {}).get("symbol")),
        "side": ((trade.get("order") or {}).get("side")),
        "type": ((trade.get("order") or {}).get("type")),
        "time_in_force": ((trade.get("order") or {}).get("time_in_force")),
        "limit_price": str((trade.get("order") or {}).get("limit_price")).rstrip("0").rstrip("."),
        "qty": str((trade.get("order") or {}).get("qty")),
    }
    findings: list[dict[str, Any]] = []
    if trade.get("artifact_type") != "wf67_paper_trade_request":
        findings.append({"severity": "critical", "code": "trade_artifact_wrong_type"})
    if cancel.get("artifact_type") != "wf67_paper_cancel_request":
        findings.append({"severity": "critical", "code": "cancel_artifact_wrong_type"})
    if dry_run.get("status") != "validated_dry_run" or dry_run.get("execute_requested") is not False:
        findings.append({"severity": "critical", "code": "dry_run_not_clean"})
    if execution.get("status") != "cancelled" or execution.get("execute_requested") is not True:
        findings.append({"severity": "critical", "code": "execution_result_not_cancelled"})
    if guard.get("status") != "ok" or (guard.get("summary") or {}).get("critical") != 0:
        findings.append({"severity": "critical", "code": "wf67_guard_not_clean"})
    if wf63.get("status") != "ok" or (wf63.get("summary") or {}).get("critical") != 0:
        findings.append({"severity": "critical", "code": "wf63_readiness_not_clean"})
    for key in ("symbol", "side", "type", "time_in_force"):
        if order.get(key) != expected[key]:
            findings.append({"severity": "critical", "code": "order_field_mismatch", "field": key, "expected": expected[key], "observed": order.get(key)})
    if str(order.get("limit_price")).rstrip("0").rstrip(".") != expected["limit_price"]:
        findings.append({"severity": "critical", "code": "order_field_mismatch", "field": "limit_price", "expected": expected["limit_price"], "observed": order.get("limit_price")})
    if str(order.get("qty")).rstrip("0").rstrip(".") != expected["qty"]:
        findings.append({"severity": "critical", "code": "order_field_mismatch", "field": "qty", "expected": expected["qty"], "observed": order.get("qty")})
    if order.get("status") != "canceled":
        findings.append({"severity": "critical", "code": "order_not_canceled", "observed": order.get("status")})
    if str(order.get("filled_qty")) not in {"0", "0.0", "0.000000000"}:
        findings.append({"severity": "critical", "code": "unexpected_fill", "filled_qty": order.get("filled_qty")})

    critical = sum(1 for f in findings if f.get("severity") == "critical")
    warning = sum(1 for f in findings if f.get("severity") == "warning")
    return {
        "schema_version": 1,
        "workflow": WORKFLOW,
        "artifact_type": "wf67_paper_pilot_reconciliation",
        "pilot_id": "wf67-pilot-001",
        "generated_at_utc": utc_now(),
        "status": "ok" if critical == 0 else "blocked",
        "summary": {"critical": critical, "warning": warning},
        "findings": findings,
        "order_lifecycle": {
            "expected": expected,
            "observed_redacted": order,
            "submitted": execution.get("status") in {"submitted", "cancelled"},
            "cancelled": order.get("status") == "canceled",
            "filled_qty_zero": str(order.get("filled_qty")) in {"0", "0.0", "0.000000000"},
        },
        "authority": {
            "paper_only": True,
            "live_trading_allowed": False,
            "live_endpoint_allowed": False,
            "live_credentials_allowed": False,
            "money_movement_allowed": False,
            "account_settings_mutation_allowed": False,
            "replace_close_liquidate_allowed": False,
            "inferred_owner_approval_allowed": False,
        },
        "redaction": {
            "secrets_persisted": False,
            "headers_persisted": False,
            "raw_response_bodies_persisted": False,
            "order_id_present_only_in_cancel_artifact": True,
        },
        "artifacts": {
            "trade_request": rel(Path(args.trade_request)),
            "cancel_request": rel(Path(args.cancel_request)),
            "dry_run_result": rel(Path(args.dry_run_result)),
            "execution_result": rel(Path(args.execution_result)),
            "guard_validation": rel(Path(args.guard_validation)),
            "wf63_readiness": rel(Path(args.wf63_readiness)),
        },
    }


def write_markdown(path: Path, report: dict[str, Any]) -> None:
    lifecycle = report["order_lifecycle"]["observed_redacted"]
    lines = [
        "# WF67 Paper Pilot Reconciliation - Pilot 001",
        "",
        f"Status: **{report['status']}**",
        f"Generated: `{report['generated_at_utc']}`",
        "",
        "## Order lifecycle",
        "",
        f"- Symbol: `{lifecycle.get('symbol')}`",
        f"- Side: `{lifecycle.get('side')}`",
        f"- Type / TIF: `{lifecycle.get('type')}` / `{lifecycle.get('time_in_force')}`",
        f"- Limit / qty: `{lifecycle.get('limit_price')}` / `{lifecycle.get('qty')}`",
        f"- Final status: `{lifecycle.get('status')}`",
        f"- Filled qty: `{lifecycle.get('filled_qty')}`",
        f"- Submitted at: `{lifecycle.get('submitted_at')}`",
        f"- Canceled at: `{lifecycle.get('canceled_at')}`",
        "",
        "## Authority boundary",
        "",
        "Paper-only simulation. Live trading, live endpoints/credentials, money movement, account mutation, replace/close/liquidation, and inferred approval remain blocked.",
        "",
        "## Validation",
        "",
        f"- Critical findings: `{report['summary']['critical']}`",
        f"- Warning findings: `{report['summary']['warning']}`",
        "- Secrets/headers/raw response bodies persisted: `false`",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--trade-request", default=str(DEFAULT_TRADE_REQUEST))
    parser.add_argument("--cancel-request", default=str(DEFAULT_CANCEL_REQUEST))
    parser.add_argument("--execution-result", default=str(DEFAULT_EXECUTION_RESULT))
    parser.add_argument("--dry-run-result", default=str(DEFAULT_DRY_RUN_RESULT))
    parser.add_argument("--guard-validation", default=str(DEFAULT_GUARD_VALIDATION))
    parser.add_argument("--wf63-readiness", default=str(DEFAULT_WF63_READINESS))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--md-output", default=str(DEFAULT_MD_OUTPUT))
    parser.add_argument("--timeout-seconds", type=int, default=15)
    args = parser.parse_args()
    try:
        report = build_report(args)
        out = Path(args.output)
        md = Path(args.md_output)
        if not out.is_absolute():
            out = ROOT / out
        if not md.is_absolute():
            md = ROOT / md
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        write_markdown(md, report)
        print(json.dumps({"status": report["status"], "summary": report["summary"], "output": rel(out), "markdown": rel(md)}, indent=2))
        return 0 if report["status"] == "ok" else 2
    except BlockedRun as exc:
        print(json.dumps({"status": "blocked", "blocked_reason": str(exc), "secrets_redacted": True}, indent=2), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
