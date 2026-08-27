#!/usr/bin/env python3
"""WF87 fail-closed portfolio circuit breakers for WF86 paper runtime."""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "tmp" / "wf87-portfolio-circuit-breakers.json"
DEFAULT_POLICY = ROOT / "tmp" / "paper-autotrader" / "policy.json"
DEFAULT_POSITIONS = ROOT / "tmp" / "finance-intelligence-state-paper-positions.json"
DEFAULT_GUARD = ROOT / "tmp" / "alpaca-paper-readiness" / "paper-execution-guard-validation.json"
DEFAULT_ORDER_HISTORY = ROOT / "tmp" / "alpaca-paper-readiness" / "paper-order-history-classifier.json"
DEFAULT_HALT_STATUS = ROOT / "tmp" / "paper-autotrader" / "market-anomaly-halt-status.json"
DEFAULT_INTRADAY_MONITOR = ROOT / "tmp" / "wf87-intraday-monitor.json"

SCHEMA = "veritas.wf87_portfolio_circuit_breakers.v1"
MAX_INPUT_AGE_SECONDS = 8 * 60 * 60
MAX_POLICY_AGE_SECONDS = 30 * 24 * 60 * 60
DEFAULT_DAILY_LOSS_CAP_USD = 1500.0
DEFAULT_GROSS_EXPOSURE_CAP_PCT = 0.25
DEFAULT_CONCENTRATION_CAP_PCT = 0.10

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "runtime_guard_only": True,
    "paper_execution_allowed": False,
    "paper_order_submit_allowed": False,
    "paper_order_cancel_allowed": False,
    "paper_order_sell_allowed": False,
    "live_execution_allowed": False,
    "live_endpoint_allowed": False,
    "account_action_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "money_movement_allowed": False,
    "owner_approval_inferred": False,
    "canon_or_portfolio_mutation_allowed": False,
    "portfolio_mutation_allowed": False,
}


def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def utc_stamp(now: datetime | None = None) -> str:
    return (now or utc_now()).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def resolve(path: Path) -> Path:
    return path if path.is_absolute() else ROOT / path


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def to_float(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def parse_utc(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def load_json(path: Path, findings: list[dict[str, Any]], code: str, *, required: bool = True) -> dict[str, Any] | None:
    if not path.exists():
        if required:
            findings.append({"severity": "critical", "code": f"missing_{code}", "path": rel(path)})
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        findings.append({"severity": "critical", "code": f"invalid_json_{code}", "path": rel(path), "error": str(exc)})
        return None
    if not isinstance(payload, dict):
        findings.append({"severity": "critical", "code": f"non_object_{code}", "path": rel(path)})
        return None
    return payload


def check_fresh(
    payload: dict[str, Any] | None,
    path: Path,
    code: str,
    findings: list[dict[str, Any]],
    now: datetime,
    *,
    max_age_seconds: int = MAX_INPUT_AGE_SECONDS,
) -> None:
    if payload is None:
        return
    generated = parse_utc(payload.get("generated_at_utc") or payload.get("created_at_utc"))
    if generated is None:
        findings.append({"severity": "critical", "code": f"{code}_missing_timestamp", "path": rel(path)})
        return
    age = (now - generated).total_seconds()
    if age < 0:
        findings.append({"severity": "critical", "code": f"{code}_timestamp_in_future", "path": rel(path), "timestamp": utc_stamp(generated)})
    elif age > max_age_seconds:
        findings.append({"severity": "critical", "code": f"{code}_expired", "path": rel(path), "age_seconds": int(age)})


def risk_caps(policy: dict[str, Any]) -> dict[str, Any]:
    return as_dict(policy.get("portfolio_circuit_breakers") or policy.get("runtime_risk_caps") or policy.get("risk_caps"))


def authority_ok(payload: dict[str, Any] | None, fields: list[str], code: str, findings: list[dict[str, Any]]) -> None:
    if payload is None:
        return
    authority = as_dict(payload.get("authority_boundary") or payload.get("authority"))
    for field in fields:
        aliases = {
            "paper_order_execution_allowed": ("paper_or_live_execution_allowed", "paper_submit_allowed"),
            "live_trade_or_account_action_allowed": ("live_endpoint_detected", "live_endpoint_allowed"),
            "trade_or_account_action_allowed": ("brokerage_or_account_action_allowed",),
            "portfolio_mutation_allowed": ("portfolio_or_canon_mutation_allowed",),
        }.get(field, ())
        values = [authority.get(field), payload.get(field)]
        values.extend(authority.get(alias) for alias in aliases)
        values.extend(payload.get(alias) for alias in aliases)
        if not any(value is False for value in values):
            findings.append({"severity": "critical", "code": f"{code}_authority_not_false", "field": field, "value": authority.get(field, payload.get(field))})


def account_values(positions: dict[str, Any]) -> tuple[float | None, float | None]:
    summary = as_dict(positions.get("account_summary"))
    equity = to_float(summary.get("equity") or summary.get("portfolio_value"))
    portfolio_value = to_float(summary.get("portfolio_value") or summary.get("equity"))
    return equity, portfolio_value


def position_rows(positions: dict[str, Any]) -> list[dict[str, Any]]:
    return [as_dict(row) for row in as_list(positions.get("positions"))]


def check_halt_status(payload: dict[str, Any] | None, findings: list[dict[str, Any]]) -> dict[str, Any]:
    if payload is None:
        findings.append({"severity": "critical", "code": "missing_anomaly_halt_status"})
        return {"status": "missing", "halted": True, "anomaly_count": None, "halt_count": None, "source": None}
    status = str(payload.get("status") or "").lower()
    anomalies = as_list(payload.get("anomalies"))
    halts = as_list(payload.get("halts") or payload.get("halted_symbols"))
    circuit_open = payload.get("circuit_open") is True or payload.get("halted") is True
    if status not in {"ok", "clear", "no_halt"}:
        findings.append({"severity": "critical", "code": "anomaly_halt_status_not_clear", "status": payload.get("status")})
    if anomalies:
        findings.append({"severity": "critical", "code": "market_anomalies_present", "count": len(anomalies)})
    if halts or circuit_open:
        findings.append({"severity": "critical", "code": "market_halt_or_circuit_open", "halt_count": len(halts), "circuit_open": circuit_open})
    return {
        "status": payload.get("status"),
        "halted": bool(halts or circuit_open),
        "anomaly_count": len(anomalies),
        "halt_count": len(halts),
        "source": payload.get("source"),
    }


def halt_status_from_intraday_monitor(payload: dict[str, Any] | None) -> dict[str, Any] | None:
    if payload is None:
        return None
    signals = as_dict(payload.get("signals"))
    anomalies = as_list(signals.get("anomaly_halts"))
    if not anomalies:
        return {
            "generated_at_utc": payload.get("generated_at_utc"),
            "status": "ok",
            "anomalies": [],
            "halts": [],
            "source": "wf87_intraday_monitor",
        }
    return {
        "generated_at_utc": payload.get("generated_at_utc"),
        "status": "halt",
        "anomalies": anomalies,
        "halts": [],
        "source": "wf87_intraday_monitor",
    }


def build_report(args: argparse.Namespace, now: datetime | None = None) -> dict[str, Any]:
    now = now or utc_now()
    findings: list[dict[str, Any]] = []
    policy_path = resolve(Path(args.policy))
    positions_path = resolve(Path(args.paper_positions))
    guard_path = resolve(Path(args.guard_validation))
    order_history_path = resolve(Path(args.order_history))
    halt_path = resolve(Path(args.halt_status))
    intraday_monitor_path = resolve(Path(args.intraday_monitor))

    policy = load_json(policy_path, findings, "policy")
    positions = load_json(positions_path, findings, "paper_positions")
    guard = load_json(guard_path, findings, "wf67_guard_validation")
    order_history = load_json(order_history_path, findings, "order_history_classifier")
    halt_status = load_json(halt_path, findings, "anomaly_halt_status", required=False)
    intraday_monitor = load_json(intraday_monitor_path, findings, "intraday_monitor", required=False)
    if halt_status is None:
        halt_status = halt_status_from_intraday_monitor(intraday_monitor)

    for code, path, payload, max_age in (
        ("policy", policy_path, policy, MAX_POLICY_AGE_SECONDS),
        ("paper_positions", positions_path, positions, MAX_INPUT_AGE_SECONDS),
        ("wf67_guard_validation", guard_path, guard, MAX_INPUT_AGE_SECONDS),
        ("order_history_classifier", order_history_path, order_history, MAX_INPUT_AGE_SECONDS),
        ("anomaly_halt_status", halt_path if halt_path.exists() else intraday_monitor_path, halt_status, MAX_INPUT_AGE_SECONDS),
    ):
        check_fresh(payload, path, code, findings, now, max_age_seconds=max_age)

    authority_ok(policy, [
        "autonomous_paper_execution_allowed_now",
        "live_endpoint_allowed",
        "brokerage_or_account_action_allowed",
        "money_movement_allowed",
        "portfolio_or_canon_mutation_allowed",
        "owner_approval_inferred",
    ], "policy", findings)
    authority_ok(positions, [
        "paper_order_execution_allowed",
        "live_trade_or_account_action_allowed",
        "trade_or_account_action_allowed",
        "money_movement_allowed",
        "portfolio_mutation_allowed",
        "owner_approval_inferred",
    ], "paper_positions", findings)
    if guard is not None and guard.get("status") != "ok":
        findings.append({"severity": "critical", "code": "wf67_guard_not_ok", "status": guard.get("status")})
    if order_history is not None and order_history.get("status") != "ok":
        findings.append({"severity": "critical", "code": "order_history_classifier_not_ok", "status": order_history.get("status")})

    caps = risk_caps(policy or {})
    daily_loss_cap = to_float(caps.get("daily_loss_cap_usd")) or DEFAULT_DAILY_LOSS_CAP_USD
    gross_cap = to_float(caps.get("gross_exposure_cap_pct")) or DEFAULT_GROSS_EXPOSURE_CAP_PCT
    concentration_cap = to_float(caps.get("concentration_cap_pct")) or DEFAULT_CONCENTRATION_CAP_PCT
    equity, portfolio_value = account_values(positions or {})
    rows = position_rows(positions or {})
    if equity is None or equity <= 0:
        findings.append({"severity": "critical", "code": "missing_paper_account_equity"})
        equity = 0.0
    if not rows:
        findings.append({"severity": "critical", "code": "missing_paper_positions"})

    gross_exposure = sum(abs(to_float(row.get("market_value")) or 0.0) for row in rows)
    daily_loss = sum(abs(to_float(row.get("unrealized_pl")) or 0.0) for row in rows if (to_float(row.get("unrealized_pl")) or 0.0) < 0)
    largest = max((abs(to_float(row.get("market_value")) or 0.0), str(row.get("symbol") or "")) for row in rows) if rows else (0.0, "")
    gross_pct = gross_exposure / equity if equity else None
    concentration_pct = largest[0] / equity if equity else None
    if daily_loss > daily_loss_cap:
        findings.append({"severity": "critical", "code": "daily_loss_cap_breached", "value": daily_loss, "cap": daily_loss_cap})
    if gross_pct is not None and gross_pct > gross_cap:
        findings.append({"severity": "critical", "code": "gross_exposure_cap_breached", "value": gross_pct, "cap": gross_cap})
    if concentration_pct is not None and concentration_pct > concentration_cap:
        findings.append({"severity": "critical", "code": "concentration_cap_breached", "ticker": largest[1], "value": concentration_pct, "cap": concentration_cap})
    halt_snapshot = check_halt_status(halt_status, findings)

    critical = sum(1 for item in findings if item.get("severity") == "critical")
    status = "ok" if critical == 0 else "blocked"
    return {
        "schema": SCHEMA,
        "generated_at_utc": utc_stamp(now),
        "status": status,
        "workflow_id": "WF87",
        "authority_boundary": AUTHORITY_BOUNDARY,
        "caps": {
            "daily_loss_cap_usd": daily_loss_cap,
            "gross_exposure_cap_pct": gross_cap,
            "concentration_cap_pct": concentration_cap,
        },
        "portfolio_snapshot": {
            "equity": equity,
            "portfolio_value": portfolio_value,
            "positions_count": len(rows),
            "gross_exposure_usd": gross_exposure,
            "gross_exposure_pct": gross_pct,
            "daily_loss_proxy_usd": daily_loss,
            "largest_position": {"ticker": largest[1] or None, "market_value": largest[0], "concentration_pct": concentration_pct},
            "anomaly_halt_status": halt_snapshot,
        },
        "summary": {
            "critical_finding_count": critical,
            "next_safe_action": "Keep paper execution blocked when this report status is blocked.",
        },
        "findings": findings,
        "source_artifacts": [rel(policy_path), rel(positions_path), rel(guard_path), rel(order_history_path), rel(halt_path), rel(intraday_monitor_path)],
        "validation": {
            "status": "ok" if all(value is False for key, value in AUTHORITY_BOUNDARY.items() if key not in {"review_only", "runtime_guard_only"}) else "error",
            "errors": [],
            "warnings": [],
        },
        "stop_lines": [
            "This validator grants no paper/live execution authority.",
            "Missing paper data, cap breaches, anomalies, or halts block runtime execution.",
            "No live endpoint, account action, money movement, owner approval inference, or canon/portfolio mutation.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--policy", default=str(DEFAULT_POLICY))
    parser.add_argument("--paper-positions", default=str(DEFAULT_POSITIONS))
    parser.add_argument("--guard-validation", default=str(DEFAULT_GUARD))
    parser.add_argument("--order-history", default=str(DEFAULT_ORDER_HISTORY))
    parser.add_argument("--halt-status", default=str(DEFAULT_HALT_STATUS))
    parser.add_argument("--intraday-monitor", default=str(DEFAULT_INTRADAY_MONITOR))
    parser.add_argument("--output", default=str(OUT))
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    args = parser.parse_args()
    report = build_report(args)
    if args.write:
        out = resolve(Path(args.output))
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": report["status"], "summary": report["summary"], "validation": report["validation"]}, indent=2, sort_keys=True))
    return 1 if args.validate and report["validation"]["status"] != "ok" else 0


if __name__ == "__main__":
    raise SystemExit(main())
