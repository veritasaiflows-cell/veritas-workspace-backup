#!/usr/bin/env python3
"""WF67 full-portfolio / basket paper-scope validator.

This validator performs no Alpaca API calls and never submits, cancels,
replaces, closes, liquidates, transfers, or mutates account state. It validates
whether a proposed WF67 full-portfolio paper scope is review-ready and whether a
basket request is dry-run-safe. Execution remains blocked unless a later exact
owner-approved scope and basket request explicitly allow it.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "tmp" / "alpaca-paper-readiness"
WORKFLOW = "WF67 - Alpaca Paper Execution Guardrail"
PHASE = "phase_6_paper_execution_guardrail"
PAPER_ENDPOINT = "https://paper-api.alpaca.markets"
LIVE_ENDPOINT = "https://" + "api.alpaca.markets"
DEFAULT_SCOPE = BASE / "full-portfolio-scope.wf67-100k-v1.json"
DEFAULT_BASKET = BASE / "paper-basket-request.tranche0-dry-run.json"
DEFAULT_OUTPUT = BASE / "full-portfolio-scope-validation.json"
DEFAULT_MD_OUTPUT = BASE / "full-portfolio-scope-validation.md"

EXPECTED_MODEL_NOTIONAL = 100000.0
EXPECTED_TRANCHE_MAX = 20000.0
EXPECTED_TRANCHES = 5
EXPECTED_SLEEVES = {
    "stock_quality": 54000.0,
    "equity_etf": 36000.0,
}
REQUIRED_ALLOWED_SYMBOLS = {
    "ETN", "LIN", "CME", "PH", "WMB", "TMUS",
    "SGOV", "SHY", "BND", "SCHP",
    "VTI", "VXUS", "ITA", "XLI", "XLB", "PAVE", "XLE", "XLC",
}
REQUIRED_BLOCKED_SYMBOLS = {
    "NVDA", "MSFT", "JPM", "BRK.B", "LMT", "RTX", "GE", "XOM", "LNG", "BKNG", "PLTR", "KTOS", "HYG", "JNK",
}
REQUIRED_FALSE_AUTHORITY = {
    "live_submit_allowed",
    "live_cancel_allowed",
    "live_endpoint_allowed",
    "live_credentials_allowed",
    "money_movement_allowed",
    "account_settings_mutation_allowed",
    "replace_order_allowed",
    "close_position_allowed",
    "liquidation_allowed",
    "short_sales_allowed",
    "margin_allowed",
    "leverage_allowed",
    "options_allowed",
    "crypto_allowed",
    "market_orders_allowed",
    "multi_leg_orders_allowed",
    "paper_results_promote_to_live_allowed",
    "owner_approval_inferred_from_validation",
    "execution_authorized",
}
REQUIRED_TRUE_AUTHORITY = {
    "paper_only",
    "paper_endpoint_required",
    "paper_credentials_only",
    "dry_run_first_required",
    "explicit_owner_confirm_after_dry_run_required",
    "wf67_guard_required",
    "wf63_isolation_required",
    "kill_switch_required",
    "redacted_audit_required",
    "wf55_outcome_logging_required",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        return str(path)


def load_json(path: Path, findings: list[dict[str, Any]], code: str) -> dict[str, Any] | None:
    if not path.exists():
        findings.append({"severity": "critical", "code": f"missing_{code}", "path": rel(path)})
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        findings.append({"severity": "critical", "code": f"invalid_json_{code}", "path": rel(path), "error": str(exc)})
        return None


def as_float(value: Any) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    return None


def validate_scope(scope: dict[str, Any] | None, findings: list[dict[str, Any]]) -> None:
    if scope is None:
        return
    if scope.get("workflow") != WORKFLOW:
        findings.append({"severity": "critical", "code": "scope_wrong_workflow", "value": scope.get("workflow")})
    if scope.get("phase") != PHASE:
        findings.append({"severity": "critical", "code": "scope_wrong_phase", "value": scope.get("phase")})
    if scope.get("artifact_type") != "wf67_full_portfolio_paper_scope":
        findings.append({"severity": "critical", "code": "scope_wrong_artifact_type", "value": scope.get("artifact_type")})
    if not str(scope.get("scope_id") or "").startswith("wf67-full-portfolio"):
        findings.append({"severity": "critical", "code": "scope_id_missing_or_unexpected", "value": scope.get("scope_id")})
    approval_status = scope.get("approval_status")
    if approval_status not in {"review_ready_pending_owner_approval", "approved_full_portfolio_paper_scope"}:
        findings.append({"severity": "critical", "code": "scope_approval_status_invalid", "value": approval_status})
    if approval_status == "approved_full_portfolio_paper_scope" and scope.get("owner_approval_granted") is not True:
        findings.append({"severity": "critical", "code": "approved_scope_missing_owner_approval_true"})
    if approval_status == "review_ready_pending_owner_approval" and scope.get("owner_approval_granted") is not False:
        findings.append({"severity": "critical", "code": "review_scope_must_not_mark_owner_approved"})

    authority = scope.get("authority") or {}
    for field in REQUIRED_TRUE_AUTHORITY:
        if authority.get(field) is not True:
            findings.append({"severity": "critical", "code": "scope_authority_true_missing", "field": field, "value": authority.get(field)})
    for field in REQUIRED_FALSE_AUTHORITY:
        if authority.get(field) is not False:
            findings.append({"severity": "critical", "code": "scope_authority_false_missing", "field": field, "value": authority.get(field)})
    if authority.get("paper_endpoint") != PAPER_ENDPOINT:
        findings.append({"severity": "critical", "code": "scope_endpoint_not_exact_paper", "value": authority.get("paper_endpoint")})
    if authority.get("live_endpoint") == LIVE_ENDPOINT:
        findings.append({"severity": "critical", "code": "scope_contains_live_endpoint_literal"})
    if authority.get("paper_submit_allowed") is not True or authority.get("paper_cancel_allowed") is not True:
        findings.append({"severity": "critical", "code": "scope_paper_submit_cancel_not_acknowledged"})
    if authority.get("basket_submit_allowed") is not False:
        findings.append({"severity": "critical", "code": "scope_must_keep_basket_submit_blocked_until_exact_approval"})
    if authority.get("dry_run_basket_generation_allowed") is not True:
        findings.append({"severity": "critical", "code": "scope_dry_run_generation_not_allowed"})

    model = scope.get("portfolio_model") or {}
    if as_float(model.get("model_notional_usd")) != EXPECTED_MODEL_NOTIONAL:
        findings.append({"severity": "critical", "code": "scope_model_notional_unexpected", "value": model.get("model_notional_usd")})
    if model.get("model_notional_role") != "ceiling_not_deployment_target":
        findings.append({"severity": "critical", "code": "scope_model_notional_role_unexpected", "value": model.get("model_notional_role")})
    sleeves = {row.get("sleeve"): as_float(row.get("target_notional_usd")) for row in model.get("target_sleeves") or []}
    for sleeve, expected in EXPECTED_SLEEVES.items():
        if sleeves.get(sleeve) != expected:
            findings.append({"severity": "critical", "code": "scope_sleeve_target_unexpected", "sleeve": sleeve, "value": sleeves.get(sleeve), "expected": expected})
    unexpected_fixed_sleeves = sorted(set(sleeves) - set(EXPECTED_SLEEVES))
    if unexpected_fixed_sleeves:
        findings.append({"severity": "critical", "code": "scope_unexpected_fixed_sleeve_target", "sleeves": unexpected_fixed_sleeves})
    sleeve_total = sum(value for value in sleeves.values() if value is not None)
    if sleeve_total > EXPECTED_MODEL_NOTIONAL:
        findings.append({"severity": "critical", "code": "scope_sleeve_targets_exceed_ceiling", "value": sleeve_total})
    if model.get("cash_unallocated_allowed") is not True:
        findings.append({"severity": "critical", "code": "scope_cash_unallocated_not_allowed"})

    tranche = scope.get("tranche_controls") or {}
    if tranche.get("tranche_count") != EXPECTED_TRANCHES:
        findings.append({"severity": "critical", "code": "scope_tranche_count_unexpected", "value": tranche.get("tranche_count")})
    if as_float(tranche.get("max_tranche_notional_usd")) != EXPECTED_TRANCHE_MAX:
        findings.append({"severity": "critical", "code": "scope_tranche_max_unexpected", "value": tranche.get("max_tranche_notional_usd")})
    if as_float(tranche.get("max_total_submitted_notional_per_day_usd")) != EXPECTED_TRANCHE_MAX:
        findings.append({"severity": "critical", "code": "scope_daily_notional_unexpected", "value": tranche.get("max_total_submitted_notional_per_day_usd")})
    if as_float(tranche.get("max_aggregate_open_order_notional_usd")) != EXPECTED_TRANCHE_MAX:
        findings.append({"severity": "critical", "code": "scope_open_order_notional_unexpected", "value": tranche.get("max_aggregate_open_order_notional_usd")})
    for field in ("post_submit_reconciliation_required", "post_close_reconciliation_required", "wf55_outcome_logging_required"):
        if tranche.get(field) is not True:
            findings.append({"severity": "critical", "code": "scope_tranche_required_field_missing", "field": field})

    allowed_rows = scope.get("allowed_symbols") or []
    allowed = {row.get("symbol") for row in allowed_rows}
    missing_allowed = sorted(REQUIRED_ALLOWED_SYMBOLS - allowed)
    extra_allowed = sorted(symbol for symbol in allowed if symbol and symbol not in REQUIRED_ALLOWED_SYMBOLS)
    if missing_allowed:
        findings.append({"severity": "critical", "code": "scope_missing_allowed_symbols", "symbols": missing_allowed})
    if extra_allowed:
        findings.append({"severity": "critical", "code": "scope_extra_allowed_symbols", "symbols": extra_allowed})
    blocked = set(scope.get("blocked_symbols") or [])
    missing_blocked = sorted(REQUIRED_BLOCKED_SYMBOLS - blocked)
    if missing_blocked:
        findings.append({"severity": "critical", "code": "scope_missing_blocked_symbols", "symbols": missing_blocked})
    if allowed & blocked:
        findings.append({"severity": "critical", "code": "scope_symbol_both_allowed_and_blocked", "symbols": sorted(allowed & blocked)})

    for row in allowed_rows:
        symbol = row.get("symbol")
        if row.get("allowed_side") != "buy":
            findings.append({"severity": "critical", "code": "scope_symbol_side_not_buy", "symbol": symbol})
        for field in ("entry_band_required", "limit_price_required", "no_chase_required", "fresh_source_required", "technical_state_required", "owner_confirmation_required"):
            if row.get(field) in (None, False):
                findings.append({"severity": "critical", "code": "scope_symbol_gate_missing", "symbol": symbol, "field": field})
        max_order = as_float(row.get("max_order_notional_usd"))
        max_cumulative = as_float(row.get("max_cumulative_notional_usd"))
        if max_order is None or max_order <= 0 or max_order > 5000.0:
            findings.append({"severity": "critical", "code": "scope_symbol_order_cap_invalid", "symbol": symbol, "value": row.get("max_order_notional_usd")})
        if max_cumulative is None or max_cumulative <= 0 or max_cumulative > EXPECTED_MODEL_NOTIONAL:
            findings.append({"severity": "critical", "code": "scope_symbol_cumulative_cap_invalid", "symbol": symbol, "value": row.get("max_cumulative_notional_usd")})

    order_constraints = scope.get("order_constraints") or {}
    expected = {
        "allowed_order_types": ["limit"],
        "allowed_time_in_force": ["day"],
        "regular_hours_only": True,
        "extended_hours_allowed": False,
        "market_orders_allowed": False,
        "buy_only_initial_scope": True,
        "sell_allowed": False,
        "replace_allowed": False,
        "cancel_allowed_for_scope_order_ids_only": True,
    }
    for field, expected_value in expected.items():
        if order_constraints.get(field) != expected_value:
            findings.append({"severity": "critical", "code": "scope_order_constraint_unexpected", "field": field, "value": order_constraints.get(field), "expected": expected_value})


def validate_basket(basket: dict[str, Any] | None, scope: dict[str, Any] | None, findings: list[dict[str, Any]]) -> None:
    if basket is None:
        return
    if basket.get("workflow") != WORKFLOW:
        findings.append({"severity": "critical", "code": "basket_wrong_workflow", "value": basket.get("workflow")})
    if basket.get("artifact_type") != "wf67_paper_basket_request":
        findings.append({"severity": "critical", "code": "basket_wrong_artifact_type", "value": basket.get("artifact_type")})
    if basket.get("execution_mode") != "dry_run_only":
        findings.append({"severity": "critical", "code": "basket_execution_mode_not_dry_run_only", "value": basket.get("execution_mode")})
    authority = basket.get("authority") or {}
    for field in ("paper_only", "dry_run_only", "live_endpoint_forbidden", "no_inferred_approval"):
        if authority.get(field) is not True:
            findings.append({"severity": "critical", "code": "basket_authority_true_missing", "field": field})
    for field in ("owner_approval_granted", "execute_allowed", "live_submit_allowed", "live_cancel_allowed", "money_movement_allowed", "account_settings_mutation_allowed"):
        if authority.get(field) is not False:
            findings.append({"severity": "critical", "code": "basket_authority_false_missing", "field": field, "value": authority.get(field)})

    if scope is not None and basket.get("portfolio_scope_id") != scope.get("scope_id"):
        findings.append({"severity": "critical", "code": "basket_scope_id_mismatch", "basket": basket.get("portfolio_scope_id"), "scope": scope.get("scope_id")})
    tranche = basket.get("tranche") or {}
    if tranche.get("tranche_number") != 0:
        findings.append({"severity": "critical", "code": "basket_tranche0_expected_for_review_ready_scope", "value": tranche.get("tranche_number")})
    if as_float(tranche.get("max_new_submitted_notional_usd")) != 0.0:
        findings.append({"severity": "critical", "code": "basket_tranche0_must_have_zero_notional", "value": tranche.get("max_new_submitted_notional_usd")})
    orders = basket.get("orders") or []
    if orders:
        findings.append({"severity": "critical", "code": "basket_tranche0_must_have_no_orders", "count": len(orders)})
    risk = basket.get("risk_check") or {}
    if risk.get("status") != "ok" or as_float(risk.get("basket_estimated_notional_usd")) != 0.0:
        findings.append({"severity": "critical", "code": "basket_risk_not_tranche0_ok", "value": risk})


def build_markdown(report: dict[str, Any]) -> str:
    summary = report["summary"]
    return "\n".join([
        "# WF67 Full-Portfolio Scope Validation",
        "",
        f"- Generated: `{report['generated_at_utc']}`",
        f"- Status: **{report['status']}**",
        f"- Critical: `{summary['critical']}`",
        f"- Warning: `{summary['warning']}`",
        f"- Review-ready scope: `{str(report['review_ready_scope']).lower()}`",
        f"- Ready for paper execution: `{str(report['ready_for_paper_execution']).lower()}`",
        f"- Owner approval required: `{str(report['owner_approval_required']).lower()}`",
        "",
        "## Verdict",
        "",
        report["verdict"],
        "",
        "## Findings",
        "",
        "No findings." if not report["findings"] else "\n".join(f"- `{f.get('severity')}` `{f.get('code')}` {f}" for f in report["findings"]),
        "",
    ])


def validate(args: argparse.Namespace) -> dict[str, Any]:
    findings: list[dict[str, Any]] = []
    scope_path = Path(args.scope)
    basket_path = Path(args.basket) if args.basket else None
    scope = load_json(scope_path, findings, "scope")
    basket = load_json(basket_path, findings, "basket") if basket_path else None
    validate_scope(scope, findings)
    validate_basket(basket, scope, findings)
    critical = sum(1 for f in findings if f.get("severity") == "critical")
    warning = sum(1 for f in findings if f.get("severity") == "warning")
    status = "ok" if critical == 0 else "blocked"
    approval_status = scope.get("approval_status") if scope else None
    owner_approved = bool(scope and scope.get("owner_approval_granted") is True and approval_status == "approved_full_portfolio_paper_scope")
    return {
        "schema_version": 1,
        "workflow": WORKFLOW,
        "artifact_type": "wf67_full_portfolio_scope_validation",
        "generated_at_utc": utc_now(),
        "status": status,
        "summary": {"critical": critical, "warning": warning},
        "findings": findings,
        "artifacts": {
            "scope": rel(scope_path),
            "basket_request": rel(basket_path) if basket_path else None,
        },
        "review_ready_scope": status == "ok" and approval_status == "review_ready_pending_owner_approval",
        "ready_for_basket_dry_run": status == "ok" and basket is not None,
        "ready_for_paper_execution": status == "ok" and owner_approved and False,
        "owner_approval_required": not owner_approved,
        "paper_only": True,
        "live_trading_allowed": False,
        "money_movement_allowed": False,
        "canonical_portfolio_apply_allowed": False,
        "verdict": (
            "WF67 full-portfolio paper scope is review-ready and dry-run-scaffolded, but paper execution remains blocked pending explicit owner approval, fresh validators, kill switch, and exact tranche/basket order terms."
            if status == "ok" else
            "WF67 full-portfolio paper scope remains blocked until critical findings are resolved."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scope", default=str(DEFAULT_SCOPE))
    parser.add_argument("--basket", default=str(DEFAULT_BASKET))
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--md-output", default=str(DEFAULT_MD_OUTPUT))
    args = parser.parse_args()
    report = validate(args)
    if args.write:
        out = Path(args.output)
        if not out.is_absolute():
            out = ROOT / out
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        md = Path(args.md_output)
        if not md.is_absolute():
            md = ROOT / md
        md.parent.mkdir(parents=True, exist_ok=True)
        md.write_text(build_markdown(report), encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["status"] == "ok" else 2


if __name__ == "__main__":
    raise SystemExit(main())
