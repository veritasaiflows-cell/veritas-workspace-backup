#!/usr/bin/env python3
"""Build deterministic Tier A data/fundamentals confidence for WF78.

This is a derived, review-only confidence gate. It consumes the existing WF78
Tier A routing and fundamentals/reconciliation artifacts, then writes one row
per current Tier A name. It does not admit, promote, demote, mutate canon,
approve capital, or authorize paper/live/account action.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, load_json_artifact


ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"

AUTO_ROUTING = TMP / "wf78-auto-tier-routing.json"
FUNDAMENTALS = TMP / "fundamental-metrics-current.json"
IR_PACKETS = TMP / "fundamental-ir-reconciliation-packets.json"
SEC_SCALER = TMP / "wf78-sec-reconciliation-scaler-current.json"
DEFAULT_OUT = TMP / "wf78-tier-a-confidence-gate.json"
SCHEMA = "veritas.wf78_tier_a_confidence_gate.v1"

MAX_OPERATING_COMPANY_PERIOD_AGE_DAYS = 170

# finance_sql_canon.resolve_production_scope admits Tier A and Tier B, and requires
# tier_a_confidence_status == "ready". Scoping this gate to Tier A alone left every
# Tier B name with a null verdict, which that join reads as confidence_status_not_ready.
CONFIDENCE_SCOPE_TIERS = {"Tier A", "Tier B"}

AUTHORITY_BOUNDARY: dict[str, bool] = {
    "review_only": True,
    "derived_confidence_only": True,
    "automated_non_capital_routing_input_allowed": True,
    "tier_a_admission_allowed": False,
    "promotion_by_confidence_score_allowed": False,
    "universe_mutation_allowed": False,
    "canon_or_portfolio_mutation_allowed": False,
    "ticker_card_mutation_allowed": False,
    "sql_canon_mutation_allowed": False,
    "capital_deployment_allowed": False,
    "trade_execution_allowed": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "money_movement_allowed": False,
    "owner_approval_inferred": False,
}

REQUIRED_TRUE_FLAGS = {
    "review_only",
    "derived_confidence_only",
    "automated_non_capital_routing_input_allowed",
}
REQUIRED_FALSE_FLAGS = {flag for flag in AUTHORITY_BOUNDARY if flag not in REQUIRED_TRUE_FLAGS}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def load_dict(path: Path) -> dict[str, Any]:
    payload = load_json_artifact(path)
    return payload if isinstance(payload, dict) else {}


def add_check(checks: list[dict[str, Any]], name: str, ok: bool, detail: Any = None, severity: str = "critical") -> None:
    checks.append({"name": name, "ok": bool(ok), "status": "ok" if ok else "fail", "severity": severity, "detail": detail})


def by_ticker(rows: list[Any]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for row in rows:
        if isinstance(row, dict) and row.get("ticker"):
            result[str(row.get("ticker")).upper()] = row
    return result


def parse_date(value: Any) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def period_age_days(row: dict[str, Any]) -> int | None:
    parsed = parse_date(row.get("period_end"))
    if parsed is None:
        return None
    return (datetime.now(timezone.utc).date() - parsed).days


def metric_conflicts(sec: dict[str, Any]) -> list[str]:
    conflicts = [str(item) for item in as_list(sec.get("conflicts")) if str(item).strip()]
    for metric, payload in as_dict(sec.get("metrics")).items():
        status = as_dict(payload).get("status")
        if status == "conflict" and metric not in conflicts:
            conflicts.append(str(metric))
    return sorted(set(conflicts))


def ir_status_from_packets(ticker: str, ir_packets: dict[str, Any]) -> str | None:
    for packet in as_list(ir_packets.get("packets")):
        if isinstance(packet, dict) and str(packet.get("ticker") or "").upper() == ticker:
            status = packet.get("status") or as_dict(packet.get("company_ir_reconciliation")).get("status")
            return str(status) if status else None
    return None


def sec_scaler_status(ticker: str, sec_scaler: dict[str, Any]) -> str | None:
    for row in as_list(sec_scaler.get("results")):
        if isinstance(row, dict) and str(row.get("ticker") or "").upper() == ticker:
            status = row.get("status")
            return str(status) if status else None
    return None


def is_etf_or_proxy(row: dict[str, Any], routing_row: dict[str, Any]) -> bool:
    instrument = str(row.get("instrument_type") or routing_row.get("instrument_type") or "").lower()
    source_tier = str(row.get("source_tier") or "").lower()
    return "etf" in instrument or row.get("data_quality") == "not_applicable" or source_tier in {"etf", "macro_proxy"}


def is_bank_like(row: dict[str, Any]) -> bool:
    sector = str(row.get("sector") or "").lower()
    quality = str(row.get("capital_allocation_quality") or "").lower()
    return "financial" in sector or quality == "bank_manual_review"


def classify_confidence(
    ticker: str,
    routing_row: dict[str, Any],
    fundamental_row: dict[str, Any] | None,
    ir_packets: dict[str, Any],
    sec_scaler: dict[str, Any],
) -> dict[str, Any]:
    critical: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    reasons: list[str] = []

    if fundamental_row is None:
        critical.append({"code": "missing_fundamental_row", "message": "No current fundamentals row exists for this Tier A ticker."})
        return finish_row(ticker, routing_row, {}, critical, warnings, reasons)

    row = fundamental_row
    sec = as_dict(row.get("sec_reconciliation"))
    company_ir = as_dict(row.get("company_ir_reconciliation"))
    valuation_context = str(row.get("valuation_context") or "")
    data_quality = str(row.get("data_quality") or "")
    sec_status = str(sec.get("status") or "")
    company_ir_status = str(company_ir.get("status") or ir_status_from_packets(ticker, ir_packets) or "")
    scaler_status = sec_scaler_status(ticker, sec_scaler)
    conflicts = metric_conflicts(sec)
    age_days = period_age_days(row)
    etf_or_proxy = is_etf_or_proxy(row, routing_row)
    bank_like = is_bank_like(row)

    if row.get("fetch_error"):
        critical.append({"code": "fetch_error", "message": str(row.get("fetch_error"))})
    if not data_quality:
        warnings.append({"code": "missing_data_quality", "message": "Fundamentals row has no data_quality label."})
    elif data_quality not in {"clean", "not_applicable"}:
        critical.append({"code": "data_quality_not_clean", "message": f"data_quality={data_quality}"})

    if etf_or_proxy:
        if sec_status != "not_applicable":
            warnings.append({"code": "unexpected_etf_sec_status", "message": f"ETF/proxy SEC status is {sec_status or 'missing'}."})
        warnings.append({"code": "lookthrough_required", "message": "ETF/proxy needs holdings look-through confidence before A-READY."})
        reasons.append("Operating-company SEC metrics are not applicable to this ETF/proxy.")
    else:
        if sec_status != "matched":
            critical.append({"code": "sec_reconciliation_not_matched", "message": f"SEC reconciliation status is {sec_status or 'missing'}."})
        if conflicts:
            critical.append({"code": "sec_metric_conflicts", "message": f"Conflicting SEC metric(s): {', '.join(conflicts)}.", "metrics": conflicts})
        if age_days is None:
            critical.append({"code": "missing_period_end", "message": "Current fundamentals row has no period_end."})
        elif age_days > MAX_OPERATING_COMPANY_PERIOD_AGE_DAYS:
            critical.append({"code": "stale_fundamental_period", "message": f"period_end age is {age_days} days.", "age_days": age_days})
        if valuation_context != "available":
            critical.append({"code": "valuation_context_unavailable", "message": f"valuation_context={valuation_context or 'missing'}"})
        if sec_status == "matched" and not conflicts:
            reasons.append("SEC companyfacts reconciliation matched with no metric conflicts.")
        if bank_like:
            warnings.append({"code": "bank_specific_review_required", "message": "Bank/financial names need bank-specific fundamentals review beyond industrial FCF metrics."})

    if company_ir_status in {"configured_manual_review_required", "manual_required", ""}:
        warnings.append({"code": "company_ir_manual_review_required", "message": "Official IR/guidance reconciliation still requires manual review."})
    if scaler_status in {"local_repair_required", "blocked"}:
        critical.append({"code": "sec_scaler_repair_required", "message": f"SEC scaler status is {scaler_status}."})
    elif scaler_status:
        reasons.append(f"SEC scaler status: {scaler_status}.")

    anomaly_rows = as_list(row.get("capital_allocation_anomalies"))
    warning_anomalies = [
        as_dict(item)
        for item in anomaly_rows
        if as_dict(item).get("severity") == "warning"
    ]
    if warning_anomalies:
        warnings.append({"code": "capital_allocation_warnings", "message": f"{len(warning_anomalies)} capital-allocation warning(s) present."})

    if age_days is not None:
        reasons.append(f"Latest fundamentals period_end={row.get('period_end')} ({age_days} days old).")

    return finish_row(ticker, routing_row, row, critical, warnings, reasons)


def finish_row(
    ticker: str,
    routing_row: dict[str, Any],
    fundamental_row: dict[str, Any],
    critical: list[dict[str, Any]],
    warnings: list[dict[str, Any]],
    reasons: list[str],
) -> dict[str, Any]:
    etf_or_proxy = is_etf_or_proxy(fundamental_row, routing_row) if fundamental_row else False
    critical_count = len(critical)
    warning_count = len(warnings)
    sec = as_dict(fundamental_row.get("sec_reconciliation"))
    company_ir = as_dict(fundamental_row.get("company_ir_reconciliation"))
    sec_status = str(sec.get("status") or "missing")
    data_quality = str(fundamental_row.get("data_quality") or "missing")

    if critical_count:
        data_confidence_rating = "conflicted"
        tier_a_confidence_status = "challenged"
        promotion_effect = "force_a_challenged"
    elif etf_or_proxy:
        data_confidence_rating = "not_applicable"
        tier_a_confidence_status = "manual_review"
        promotion_effect = "force_a_challenged"
    elif data_quality == "clean" and sec_status == "matched":
        data_confidence_rating = "high"
        tier_a_confidence_status = "ready"
        promotion_effect = "allow_a_ready"
    else:
        data_confidence_rating = "medium"
        tier_a_confidence_status = "manual_review"
        promotion_effect = "force_a_challenged"

    if critical_count:
        fundamentals_confidence = "conflicted"
    elif etf_or_proxy:
        fundamentals_confidence = "not_applicable"
    elif warning_count:
        fundamentals_confidence = "medium_high"
    else:
        fundamentals_confidence = "high"

    return {
        "ticker": ticker,
        "name": routing_row.get("name"),
        "auto_state": routing_row.get("auto_state"),
        "route_reason": routing_row.get("route_reason"),
        "instrument_type": routing_row.get("instrument_type") or fundamental_row.get("instrument_type"),
        "period_end": fundamental_row.get("period_end"),
        "period_age_days": period_age_days(fundamental_row) if fundamental_row else None,
        "data_quality": data_quality,
        "sec_reconciliation_status": sec_status,
        "sec_conflicts": metric_conflicts(sec),
        "company_ir_reconciliation_status": company_ir.get("status") or "missing",
        "valuation_context": fundamental_row.get("valuation_context"),
        "capital_allocation_quality": fundamental_row.get("capital_allocation_quality"),
        "critical_conflict_count": critical_count,
        "warning_count": warning_count,
        "critical_conflicts": critical,
        "warnings": warnings,
        "data_confidence_rating": data_confidence_rating,
        "fundamentals_confidence": fundamentals_confidence,
        "tier_a_confidence_status": tier_a_confidence_status,
        "promotion_effect": promotion_effect,
        "manual_review_required": tier_a_confidence_status in {"manual_review", "challenged"},
        "confidence_reasons": reasons,
        "capital_deployment_approved": False,
        "trade_or_execution_approved": False,
    }


def build_report() -> dict[str, Any]:
    routing = load_dict(AUTO_ROUTING)
    fundamentals = load_dict(FUNDAMENTALS)
    ir_packets = load_dict(IR_PACKETS)
    sec_scaler = load_dict(SEC_SCALER)

    routing_rows = [
        row for row in as_list(routing.get("rows"))
        if isinstance(row, dict) and row.get("auto_tier") in CONFIDENCE_SCOPE_TIERS and row.get("ticker")
    ]
    fundamental_rows = by_ticker(as_list(fundamentals.get("rows")))
    rows = [
        classify_confidence(str(row.get("ticker")).upper(), row, fundamental_rows.get(str(row.get("ticker")).upper()), ir_packets, sec_scaler)
        for row in routing_rows
    ]
    rows.sort(key=lambda row: (row["promotion_effect"], row["ticker"]))

    rating_counts = Counter(row["data_confidence_rating"] for row in rows)
    status_counts = Counter(row["tier_a_confidence_status"] for row in rows)
    effect_counts = Counter(row["promotion_effect"] for row in rows)
    conflicted = sorted(row["ticker"] for row in rows if row["critical_conflict_count"])
    force_challenged = sorted(row["ticker"] for row in rows if row["promotion_effect"] == "force_a_challenged")
    allow_ready = sorted(row["ticker"] for row in rows if row["promotion_effect"] == "allow_a_ready")

    checks: list[dict[str, Any]] = []
    add_check(checks, "auto_routing_present", bool(routing), rel(AUTO_ROUTING))
    # This gate is an input to wf78_auto_tier_router.py. Requiring the
    # downstream router to already be green creates a false-red cycle.
    add_check(
        checks,
        "auto_routing_validation_available",
        as_dict(routing.get("validation")).get("status") in {"ok", "error"},
        as_dict(routing.get("validation")).get("status"),
        severity="warning",
    )
    add_check(checks, "fundamentals_present", bool(fundamentals), rel(FUNDAMENTALS))
    add_check(checks, "fundamentals_rows_present", bool(fundamental_rows), len(fundamental_rows))
    add_check(checks, "tier_a_rows_present", bool(routing_rows), len(routing_rows))
    add_check(checks, "one_confidence_row_per_tier_a", len(rows) == len(routing_rows), {"tier_a": len(routing_rows), "confidence_rows": len(rows)})
    add_check(checks, "no_conflicted_rows_allowed_ready", all(row["promotion_effect"] != "allow_a_ready" or row["critical_conflict_count"] == 0 for row in rows), None)
    add_check(checks, "no_missing_fundamental_rows", all("missing_fundamental_row" not in {c.get("code") for c in row["critical_conflicts"]} for row in rows), conflicted)
    add_check(checks, "no_capital_deployment_approved", all(row["capital_deployment_approved"] is False for row in rows), None)
    add_check(checks, "no_trade_or_execution_approved", all(row["trade_or_execution_approved"] is False for row in rows), None)
    for flag in REQUIRED_TRUE_FLAGS:
        add_check(checks, f"authority_{flag}_true", AUTHORITY_BOUNDARY.get(flag) is True, AUTHORITY_BOUNDARY.get(flag))
    for flag in REQUIRED_FALSE_FLAGS:
        add_check(checks, f"authority_{flag}_false", AUTHORITY_BOUNDARY.get(flag) is False, AUTHORITY_BOUNDARY.get(flag))

    errors = [check for check in checks if check["severity"] == "critical" and not check["ok"]]
    return {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "ok" if not errors else "blocked",
        "workflow": "WF78 - Tier A Confidence Gate",
        "purpose": "Attach repeatable data/fundamentals confidence and data-conflict routing effects to current Tier A names.",
        "authority_boundary": AUTHORITY_BOUNDARY,
        "source_artifacts": {
            "auto_tier_routing": rel(AUTO_ROUTING),
            "fundamentals": rel(FUNDAMENTALS),
            "ir_reconciliation_packets": rel(IR_PACKETS),
            "sec_reconciliation_scaler": rel(SEC_SCALER),
        },
        "summary": {
            "tier_a_count": len(rows),
            "data_confidence_rating_counts": dict(sorted(rating_counts.items())),
            "tier_a_confidence_status_counts": dict(sorted(status_counts.items())),
            "promotion_effect_counts": dict(sorted(effect_counts.items())),
            "allow_a_ready_tickers": allow_ready,
            "force_a_challenged_tickers": force_challenged,
            "conflicted_tickers": conflicted,
            "next_safe_action": "Use promotion_effect as a downstream auto-router constraint; critical data conflicts force A-CHALLENGED, never A-READY.",
        },
        "rows": rows,
        "validation": {
            "status": "ok" if not errors else "error",
            "errors": errors,
            "warnings": [],
            "checks": checks,
        },
        "stop_lines": [
            "Confidence rows do not admit or promote Tier A names by themselves.",
            "Critical SEC/data conflicts must not be labeled A-READY.",
            "ETF/proxy rows need look-through review before A-READY.",
            "No capital deployment, paper/live execution, brokerage/account action, money movement, or owner approval inference.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    report = build_report()
    out = args.out if args.out.is_absolute() else ROOT / args.out
    if args.write:
        atomic_write_json(out, report)
    print(
        json.dumps(
            {
                "status": report.get("status"),
                "out": rel(out),
                "summary": report.get("summary"),
                "validation": {
                    "status": as_dict(report.get("validation")).get("status"),
                    "errors": len(as_list(as_dict(report.get("validation")).get("errors"))),
                },
            },
            indent=2,
        )
    )
    if args.validate and as_dict(report.get("validation")).get("status") != "ok":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
