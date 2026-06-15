#!/usr/bin/env python3
"""WF87 fail-closed position sizing runtime check for WF86 paper candidates."""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "tmp" / "wf87-position-sizing-runtime-check.json"
DEFAULT_POLICY = ROOT / "tmp" / "paper-autotrader" / "policy.json"
DEFAULT_ASSISTED = ROOT / "tmp" / "paper-autotrader" / "assisted-order-cards.json"
DEFAULT_QUEUE = ROOT / "tmp" / "wf78-capital-review-queue.json"
DEFAULT_GUARD = ROOT / "tmp" / "alpaca-paper-readiness" / "paper-execution-guard-validation.json"

SCHEMA = "veritas.wf87_position_sizing_runtime_check.v1"
MAX_INPUT_AGE_SECONDS = 24 * 60 * 60
DEFAULT_MAX_ENTRY_TO_STOP_RISK_PCT = 0.25

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


def resolve(path: Path) -> Path:
    return path if path.is_absolute() else ROOT / path


def load_json(path: Path, findings: list[dict[str, Any]], code: str) -> dict[str, Any] | None:
    if not path.exists():
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


def check_fresh(payload: dict[str, Any] | None, path: Path, code: str, findings: list[dict[str, Any]], now: datetime) -> None:
    if payload is None:
        return
    generated = parse_utc(payload.get("generated_at_utc") or payload.get("created_at_utc"))
    if generated is None:
        findings.append({"severity": "critical", "code": f"{code}_missing_timestamp", "path": rel(path)})
        return
    age = (now - generated).total_seconds()
    if age < 0:
        findings.append({"severity": "critical", "code": f"{code}_timestamp_in_future", "path": rel(path), "timestamp": utc_stamp(generated)})
    elif age > MAX_INPUT_AGE_SECONDS:
        findings.append({"severity": "critical", "code": f"{code}_expired", "path": rel(path), "age_seconds": int(age)})


def policy_caps(policy: dict[str, Any]) -> dict[str, Any]:
    return as_dict(policy.get("initial_caps"))


def risk_caps(policy: dict[str, Any]) -> dict[str, Any]:
    return as_dict(policy.get("runtime_risk_caps") or policy.get("risk_caps"))


def policy_authority_ok(policy: dict[str, Any] | None, findings: list[dict[str, Any]]) -> None:
    if policy is None:
        return
    authority = as_dict(policy.get("authority_boundary"))
    expected_false = [
        "autonomous_paper_execution_allowed_now",
        "paper_order_submit_allowed_now",
        "paper_order_cancel_allowed_now",
        "paper_order_sell_allowed_now",
        "live_trade_allowed",
        "live_endpoint_allowed",
        "brokerage_or_account_action_allowed",
        "money_movement_allowed",
        "portfolio_or_canon_mutation_allowed",
        "owner_approval_inferred",
    ]
    if policy.get("workflow_id") != "WF86":
        findings.append({"severity": "critical", "code": "policy_wrong_workflow", "value": policy.get("workflow_id")})
    for field in expected_false:
        if authority.get(field) is not False:
            findings.append({"severity": "critical", "code": "policy_authority_not_false", "field": field, "value": authority.get(field)})


def guard_ok(guard: dict[str, Any] | None, findings: list[dict[str, Any]]) -> None:
    if guard is None:
        return
    if guard.get("status") != "ok":
        findings.append({"severity": "critical", "code": "wf67_guard_not_ok", "status": guard.get("status")})
    for field in ("live_trading_allowed", "money_movement_allowed"):
        if guard.get(field) is not False:
            findings.append({"severity": "critical", "code": "wf67_guard_authority_not_false", "field": field, "value": guard.get(field)})


def candidate_date(value: dict[str, Any], fallback: str) -> str:
    parsed = parse_utc(value.get("created_at_utc") or value.get("generated_at_utc"))
    return parsed.date().isoformat() if parsed else fallback


def load_request(path_value: Any, findings: list[dict[str, Any]]) -> tuple[dict[str, Any] | None, str | None]:
    if not isinstance(path_value, str) or not path_value.strip():
        return None, None
    path = resolve(Path(path_value))
    payload = load_json(path, findings, "candidate_request")
    return payload, rel(path)


def collect_candidates(assisted: dict[str, Any] | None, queue: dict[str, Any] | None, findings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for card in as_list(as_dict(assisted).get("cards")):
        card_dict = as_dict(card)
        request, request_path = load_request(card_dict.get("request_path"), findings)
        if request is None:
            order = {}
            risk = {}
        else:
            order = as_dict(request.get("order"))
            risk = as_dict(request.get("risk_check"))
        candidates.append({
            "source": "wf86_assisted_order_card",
            "card": card_dict,
            "request": request or {},
            "request_path": request_path,
            "ticker": str(order.get("symbol") or card_dict.get("ticker") or "").upper(),
            "created_at_utc": (request or card_dict).get("created_at_utc") or as_dict(assisted).get("generated_at_utc"),
            "order": order,
            "risk_check": risk,
        })

    for row in as_list(as_dict(queue).get("rows")):
        row_dict = as_dict(row)
        order = as_dict(row_dict.get("order"))
        risk = as_dict(row_dict.get("risk_check"))
        if not order and not risk:
            continue
        candidates.append({
            "source": "wf78_capital_review_queue_order_candidate",
            "card": {},
            "request": row_dict,
            "request_path": None,
            "ticker": str(order.get("symbol") or row_dict.get("ticker") or "").upper(),
            "created_at_utc": row_dict.get("created_at_utc") or as_dict(queue).get("generated_at_utc"),
            "order": order,
            "risk_check": risk,
        })
    return candidates


def estimated_notional(order: dict[str, Any], risk: dict[str, Any]) -> float | None:
    for value in (order.get("notional"), risk.get("estimated_notional_usd"), risk.get("max_notional_usd")):
        number = to_float(value)
        if number is not None:
            return number
    qty = to_float(order.get("qty"))
    price = to_float(order.get("limit_price") or risk.get("observed_price"))
    return qty * price if qty is not None and price is not None else None


def check_candidate(candidate: dict[str, Any], max_notional: float, max_risk_pct: float) -> dict[str, Any]:
    order = as_dict(candidate.get("order"))
    risk = as_dict(candidate.get("risk_check"))
    ticker = str(candidate.get("ticker") or "").upper()
    blockers: list[str] = []
    notional = estimated_notional(order, risk)
    entry = to_float(risk.get("observed_price") or order.get("limit_price"))
    stop = to_float(risk.get("stop") or risk.get("stop_or_invalidation") or risk.get("invalidation"))
    max_loss = to_float(risk.get("max_loss_usd"))

    if not ticker:
        blockers.append("missing_ticker")
    if notional is None or notional <= 0:
        blockers.append("missing_notional")
    elif notional > max_notional:
        blockers.append("max_notional_breached")
    if risk.get("status") not in {"ok", "pass", "ready"}:
        blockers.append("risk_check_not_ok")
    if risk.get("position_size_reviewed") is not True:
        blockers.append("position_size_not_reviewed")
    if stop is None or stop <= 0:
        blockers.append("missing_stop")
    if entry is None or entry <= 0:
        blockers.append("missing_entry_price")
    if max_loss is None or max_loss <= 0:
        blockers.append("missing_entry_to_stop_risk")
    if entry is not None and stop is not None and entry > 0:
        risk_pct = (entry - stop) / entry
        if risk_pct <= 0:
            blockers.append("entry_to_stop_risk_not_positive")
        elif risk_pct > max_risk_pct:
            blockers.append("entry_to_stop_risk_pct_breached")
    else:
        risk_pct = None
    if max_loss is not None and notional is not None and max_loss > notional:
        blockers.append("max_loss_exceeds_notional")

    return {
        "ticker": ticker or None,
        "source": candidate.get("source"),
        "request_path": candidate.get("request_path"),
        "created_at_utc": candidate.get("created_at_utc"),
        "notional_usd": notional,
        "entry_price": entry,
        "stop": stop,
        "max_loss_usd": max_loss,
        "entry_to_stop_risk_pct": risk_pct,
        "status": "ok" if not blockers else "blocked",
        "blockers": sorted(set(blockers)),
    }


def build_report(args: argparse.Namespace, now: datetime | None = None) -> dict[str, Any]:
    now = now or utc_now()
    findings: list[dict[str, Any]] = []
    policy_path = resolve(Path(args.policy))
    assisted_path = resolve(Path(args.assisted_cards))
    queue_path = resolve(Path(args.capital_queue))
    guard_path = resolve(Path(args.guard_validation))
    policy = load_json(policy_path, findings, "policy")
    assisted = load_json(assisted_path, findings, "assisted_order_cards")
    queue = load_json(queue_path, findings, "capital_review_queue")
    guard = load_json(guard_path, findings, "wf67_guard_validation")
    for code, path, payload in (
        ("policy", policy_path, policy),
        ("assisted_order_cards", assisted_path, assisted),
        ("capital_review_queue", queue_path, queue),
        ("wf67_guard_validation", guard_path, guard),
    ):
        check_fresh(payload, path, code, findings, now)
    policy_authority_ok(policy, findings)
    guard_ok(guard, findings)

    caps = policy_caps(policy or {})
    max_notional = to_float(caps.get("max_notional_per_order_usd"))
    max_orders_day = int(caps.get("max_orders_per_day") or 0)
    max_same_ticker_day = int(caps.get("max_same_ticker_orders_per_day") or 0)
    if max_notional is None or max_notional <= 0:
        findings.append({"severity": "critical", "code": "policy_missing_max_notional_per_order"})
        max_notional = 0.0
    if max_orders_day <= 0:
        findings.append({"severity": "critical", "code": "policy_missing_max_orders_per_day"})
    if max_same_ticker_day <= 0:
        findings.append({"severity": "critical", "code": "policy_missing_max_same_ticker_orders_per_day"})
    max_risk_pct = to_float(risk_caps(policy or {}).get("max_entry_to_stop_risk_pct")) or DEFAULT_MAX_ENTRY_TO_STOP_RISK_PCT

    candidates = collect_candidates(assisted, queue, findings)
    if not candidates:
        findings.append({"severity": "critical", "code": "no_order_candidates"})
    rows = [check_candidate(candidate, max_notional, max_risk_pct) for candidate in candidates]
    today = now.date().isoformat()
    todays = [row for row in rows if candidate_date(row, today) == today]
    if max_orders_day and len(todays) > max_orders_day:
        findings.append({"severity": "critical", "code": "max_orders_per_day_breached", "count": len(todays), "cap": max_orders_day})
    ticker_counts: dict[str, int] = {}
    for row in todays:
        ticker = row.get("ticker")
        if ticker:
            ticker_counts[str(ticker)] = ticker_counts.get(str(ticker), 0) + 1
    for ticker, count in sorted(ticker_counts.items()):
        if max_same_ticker_day and count > max_same_ticker_day:
            findings.append({"severity": "critical", "code": "max_same_ticker_orders_per_day_breached", "ticker": ticker, "count": count, "cap": max_same_ticker_day})

    candidate_blockers = sum(1 for row in rows if row["status"] != "ok")
    critical = sum(1 for item in findings if item.get("severity") == "critical") + candidate_blockers
    status = "ok" if critical == 0 else "blocked"
    return {
        "schema": SCHEMA,
        "generated_at_utc": utc_stamp(now),
        "status": status,
        "workflow_id": "WF87",
        "authority_boundary": AUTHORITY_BOUNDARY,
        "policy_caps": {
            "max_notional_per_order_usd": max_notional,
            "max_orders_per_day": max_orders_day,
            "max_same_ticker_orders_per_day": max_same_ticker_day,
            "max_entry_to_stop_risk_pct": max_risk_pct,
        },
        "summary": {
            "candidate_count": len(rows),
            "blocked_candidate_count": candidate_blockers,
            "critical_finding_count": critical,
            "next_safe_action": "Keep paper execution blocked when this report status is blocked.",
        },
        "candidates": rows,
        "findings": findings,
        "source_artifacts": [rel(policy_path), rel(assisted_path), rel(queue_path), rel(guard_path)],
        "validation": {
            "status": "ok" if all(value is False for key, value in AUTHORITY_BOUNDARY.items() if key not in {"review_only", "runtime_guard_only"}) else "error",
            "errors": [],
            "warnings": [],
        },
        "stop_lines": [
            "This validator grants no paper/live execution authority.",
            "Missing, stale, or cap-breaching inputs block runtime sizing.",
            "No live endpoint, account action, money movement, owner approval inference, or canon/portfolio mutation.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--policy", default=str(DEFAULT_POLICY))
    parser.add_argument("--assisted-cards", default=str(DEFAULT_ASSISTED))
    parser.add_argument("--capital-queue", default=str(DEFAULT_QUEUE))
    parser.add_argument("--guard-validation", default=str(DEFAULT_GUARD))
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
