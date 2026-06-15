#!/usr/bin/env python3
"""Build the WF86 paper autotrader readiness packet.

The packet separates shadow readiness, assisted-mode readiness, and autonomous
paper execution readiness. It deliberately fails closed for execution until
WF67 guard proof, cap alignment, kill switch, audit, reconciliation, and scoped
pilot approval are all present.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, load_json_artifact
import alpaca_paper_trade_executor as wf67

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
POLICY = TMP / "paper-autotrader" / "policy.json"
ELIGIBILITY = TMP / "paper-autotrader" / "shadow-eligibility.json"
LEDGER = TMP / "paper-autotrader" / "shadow-decisions.json"
WF67_GUARD = TMP / "alpaca-paper-readiness" / "paper-execution-guard-validation.json"
WF67_MANAGER = TMP / "alpaca-paper-readiness" / "wf67-autonomous-paper-manager-current.json"
PILOT_APPROVAL = TMP / "paper-autotrader" / "autonomous-pilot-approval.json"
OUT = TMP / "paper-autotrader" / "autotrader-readiness.json"
GUARD_OUT = TMP / "paper-autotrader" / "guard-readiness.json"
SCHEMA = "veritas.wf86_autotrader_readiness.v1"

WF67_EXECUTOR_PILOT_CAP_USD = 500.0

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "paper_only_design": True,
    "shadow_logging_allowed": True,
    "assisted_request_generation_allowed": True,
    "autonomous_paper_execution_allowed_now": False,
    "paper_submit_allowed_now": False,
    "paper_cancel_allowed_now": False,
    "paper_sell_allowed_now": False,
    "live_trade_allowed": False,
    "live_endpoint_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "money_movement_allowed": False,
    "portfolio_or_canon_mutation_allowed": False,
    "owner_approval_inferred": False,
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


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


def resolve(path: Path) -> Path:
    return path if path.is_absolute() else ROOT / path


def validate_pilot_approval(approval: dict[str, Any]) -> tuple[bool, list[str]]:
    if not approval:
        return False, ["missing_pilot_approval_artifact"]
    errors: list[str] = []
    if approval.get("schema") != "veritas.wf86_autonomous_paper_pilot_approval.v1":
        errors.append("pilot_approval_schema_invalid")
    if approval.get("workflow_id") != "WF86":
        errors.append("pilot_approval_workflow_invalid")
    if approval.get("status") != "approved_scoped_pilot":
        errors.append("pilot_approval_status_invalid")
    if approval.get("approved_by") != "Randall":
        errors.append("pilot_approval_not_by_randall")
    scope = as_dict(approval.get("scope"))
    expected_scope = {
        "paper_only": True,
        "tier_a_buy_candidates_only": True,
        "limit_day_orders_only": True,
        "max_notional_per_order_usd": 5000,
        "max_orders_per_day": 3,
        "market_hours_only": True,
        "live_trading_allowed": False,
        "brokerage_or_account_actions_allowed": False,
        "stop_on_any_guard_warning": True,
    }
    for field, expected in expected_scope.items():
        if scope.get(field) != expected:
            errors.append(f"pilot_approval_scope_invalid:{field}")
    boundary = as_dict(approval.get("authority_boundary"))
    required_boundary = {
        "paper_only": True,
        "wf67_wrapper_required": True,
        "fresh_short_lived_kill_switch_required": True,
        "pre_submit_guard_validation_required": True,
        "redacted_audit_required": True,
        "post_trade_reconciliation_required": True,
        "live_trade_allowed": False,
        "live_endpoint_allowed": False,
        "brokerage_or_account_action_allowed": False,
        "money_movement_allowed": False,
        "portfolio_or_canon_mutation_allowed": False,
        "owner_approval_inferred": False,
    }
    for field, expected in required_boundary.items():
        if boundary.get(field) is not expected:
            errors.append(f"pilot_approval_boundary_invalid:{field}")
    return not errors, errors


def build_guard_packet(
    policy: dict[str, Any],
    wf67_guard: dict[str, Any],
    wf67_manager: dict[str, Any],
    ledger: dict[str, Any],
    pilot_approval: dict[str, Any],
    pilot_approval_path: Path,
) -> dict[str, Any]:
    policy_cap = as_dict(policy.get("initial_caps")).get("max_notional_per_order_usd")
    guard_findings = as_list(wf67_guard.get("findings"))
    cap_bridge_validated = False
    cap_bridge_error = None
    try:
        cap_bridge_validated = wf67.validate_wf86_cap_policy("tmp/paper-autotrader/policy.json") == float(policy_cap or 0)
    except Exception as exc:  # noqa: BLE001 - report fail-closed proof text.
        cap_bridge_error = str(exc)
    cap_aligned = float(policy_cap or 0) <= WF67_EXECUTOR_PILOT_CAP_USD or cap_bridge_validated
    guard_clean = wf67_guard.get("status") == "ok" and wf67_guard.get("ready_for_paper_submit_cancel") is True
    ledger_summary = as_dict(ledger.get("summary"))
    shadow_threshold_met = ledger_summary.get("shadow_threshold_met") is True
    pilot_approval_valid, pilot_approval_errors = validate_pilot_approval(pilot_approval)
    blockers: list[str] = []
    if not cap_aligned:
        blockers.append(f"wf67_executor_cap_bridge_required:{WF67_EXECUTOR_PILOT_CAP_USD}_to_{policy_cap}")
    if not guard_clean:
        blockers.append("wf67_guard_not_clean")
    if not shadow_threshold_met:
        blockers.append("shadow_threshold_not_met")
    if not guard_clean:
        blockers.extend([
            "fresh_short_lived_kill_switch_not_active",
            "redacted_audit_schema_not_clean_for_autonomy",
        ])
    blockers.append("post_trade_reconciliation_not_proven_for_autonomy")
    if not pilot_approval_valid:
        blockers.append("separate_scoped_randall_autonomous_paper_pilot_approval_missing")
    return {
        "schema": "veritas.wf86_guard_readiness.v1",
        "generated_at_utc": utc_now(),
        "status": "blocked" if blockers else "ok",
        "workflow_id": "WF86",
        "authority_boundary": AUTHORITY_BOUNDARY,
        "wf67": {
            "manager_status": wf67_manager.get("status"),
            "guard_status": wf67_guard.get("status"),
            "ready_for_paper_submit_cancel": wf67_guard.get("ready_for_paper_submit_cancel") is True,
            "current_executor_pilot_cap_usd": WF67_EXECUTOR_PILOT_CAP_USD,
            "wf86_policy_cap_usd": policy_cap,
            "cap_aligned_for_wf86_policy": cap_aligned,
            "wf86_full_scope_cap_bridge_validated": cap_bridge_validated,
            "wf86_full_scope_cap_bridge_error": cap_bridge_error,
            "critical_findings": [
                item for item in guard_findings
                if as_dict(item).get("severity") == "critical"
            ],
        },
        "shadow_threshold": {
            "clean_shadow_decision_count": ledger_summary.get("clean_shadow_decision_count"),
            "unique_clean_market_sessions": ledger_summary.get("unique_clean_market_sessions"),
            "required_clean_decisions": ledger_summary.get("required_clean_decisions"),
            "required_clean_market_sessions": ledger_summary.get("required_clean_market_sessions"),
            "threshold_met": shadow_threshold_met,
        },
        "pilot_approval": {
            "path": rel(pilot_approval_path),
            "present": bool(pilot_approval),
            "valid": pilot_approval_valid,
            "errors": pilot_approval_errors,
            "approved_by": pilot_approval.get("approved_by"),
            "approved_at_mst": pilot_approval.get("approved_at_mst"),
            "scope": as_dict(pilot_approval.get("scope")),
        },
        "blockers": blockers,
        "next_safe_action": "Keep WF86 in shadow mode; implement WF67 cap bridge and guard/audit/reconciliation proof before assisted or autonomous paper execution.",
    }


def build_readiness(
    policy_path: Path,
    eligibility_path: Path,
    ledger_path: Path,
    guard_path: Path,
    manager_path: Path,
    pilot_approval_path: Path,
) -> tuple[dict[str, Any], dict[str, Any]]:
    policy = load_dict(policy_path)
    eligibility = load_dict(eligibility_path)
    ledger = load_dict(ledger_path)
    wf67_guard = load_dict(guard_path)
    wf67_manager = load_dict(manager_path)
    pilot_approval = load_dict(pilot_approval_path)
    guard_packet = build_guard_packet(policy, wf67_guard, wf67_manager, ledger, pilot_approval, pilot_approval_path)
    eligibility_summary = as_dict(eligibility.get("summary"))
    ledger_summary = as_dict(ledger.get("summary"))
    guard_blockers = as_list(guard_packet.get("blockers"))
    shadow_ready = eligibility.get("status") == "ok" and ledger.get("status") == "ok"
    assisted_ready = (
        shadow_ready
        and eligibility_summary.get("would_buy_shadow_count", 0) > 0
        and "wf67_guard_not_clean" not in guard_blockers
        and not any(str(item).startswith("wf67_executor_cap_bridge_required") for item in guard_blockers)
    )
    autonomous_ready = False

    warnings: list[str] = []
    if eligibility_summary.get("execution_ready_count") != 0:
        warnings.append("eligibility_execution_ready_count_nonzero_ignored")
    next_steps = []
    if "wf67_guard_not_clean" in guard_blockers:
        next_steps.append("Repair WF67 guard critical findings: kill switch freshness, audit required fields, and audit guard status.")
    if assisted_ready:
        next_steps.append("Use assisted mode only through WF67 execution-channel controls; readiness packets and builders do not submit orders.")
    else:
        next_steps.append("Complete assisted-mode request proof for VRT using WF86 policy, while keeping owner exact approval required.")
    if not ledger_summary.get("shadow_threshold_met"):
        next_steps.append("Continue shadow logging until at least 5 market sessions and 20 clean shadow decisions are recorded before autonomous paper buy activation.")
    if "post_trade_reconciliation_not_proven_for_autonomy" in guard_blockers:
        next_steps.append("Prove post-trade reconciliation after any assisted paper execution before autonomous paper execution can be considered ready.")

    report = {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "shadow_ready" if shadow_ready else "blocked",
        "workflow_id": "WF86",
        "purpose": "Single readiness packet for the paper autotrader next-step gate.",
        "authority_boundary": AUTHORITY_BOUNDARY,
        "phase_readiness": {
            "shadow_mode_ready": shadow_ready,
            "assisted_paper_mode_ready": assisted_ready,
            "autonomous_paper_buy_ready": autonomous_ready,
            "autonomous_paper_sell_ready": autonomous_ready,
            "live_trading_ready": False,
        },
        "policy": {
            "path": rel(policy_path),
            "mode": policy.get("mode"),
            "wf86_max_notional_per_order_usd": as_dict(policy.get("initial_caps")).get("max_notional_per_order_usd"),
            "wf67_current_executor_pilot_cap_usd": WF67_EXECUTOR_PILOT_CAP_USD,
            "wf67_wf86_full_scope_cap_bridge_available": as_dict(guard_packet.get("wf67")).get("wf86_full_scope_cap_bridge_validated"),
        },
        "shadow": {
            "eligibility_status": eligibility.get("status"),
            "candidate_count": eligibility_summary.get("candidate_count"),
            "shadow_eligible_count": eligibility_summary.get("shadow_eligible_count"),
            "would_buy_shadow_tickers": eligibility_summary.get("would_buy_shadow_tickers"),
            "ledger_decision_count": ledger_summary.get("decision_count"),
            "clean_shadow_decision_count": ledger_summary.get("clean_shadow_decision_count"),
            "unique_clean_market_sessions": ledger_summary.get("unique_clean_market_sessions"),
            "threshold_met": ledger_summary.get("shadow_threshold_met"),
        },
        "guard": guard_packet,
        "blockers_before_assisted_mode": [
            item for item in guard_blockers
            if item in {"wf67_guard_not_clean"} or str(item).startswith("wf67_executor_cap_bridge_required")
        ],
        "blockers_before_autonomous_paper_execution": guard_blockers,
        "source_artifacts": [
            rel(policy_path),
            rel(eligibility_path),
            rel(ledger_path),
            rel(guard_path),
            rel(manager_path),
            rel(pilot_approval_path),
        ],
        "validation": {
            "status": "ok" if shadow_ready and not autonomous_ready else "error",
            "errors": [] if shadow_ready and not autonomous_ready else ["shadow_inputs_not_ready_or_execution_unexpectedly_ready"],
            "warnings": warnings,
        },
        "next_implementation_steps": next_steps,
        "stop_lines": [
            "No order execution from WF86 readiness packets.",
            "No live endpoint, live credentials, account action, money movement, or owner approval inference.",
            "Cron and Telegram cannot submit/cancel/sell orders.",
        ],
    }
    return report, guard_packet


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--policy", type=Path, default=POLICY)
    parser.add_argument("--eligibility", type=Path, default=ELIGIBILITY)
    parser.add_argument("--ledger", type=Path, default=LEDGER)
    parser.add_argument("--wf67-guard", type=Path, default=WF67_GUARD)
    parser.add_argument("--wf67-manager", type=Path, default=WF67_MANAGER)
    parser.add_argument("--pilot-approval", type=Path, default=PILOT_APPROVAL)
    parser.add_argument("--out", type=Path, default=OUT)
    parser.add_argument("--guard-out", type=Path, default=GUARD_OUT)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    args = parser.parse_args()

    policy = resolve(args.policy)
    eligibility = resolve(args.eligibility)
    ledger = resolve(args.ledger)
    wf67_guard = resolve(args.wf67_guard)
    wf67_manager = resolve(args.wf67_manager)
    pilot_approval = resolve(args.pilot_approval)
    out = resolve(args.out)
    guard_out = resolve(args.guard_out)
    report, guard_packet = build_readiness(policy, eligibility, ledger, wf67_guard, wf67_manager, pilot_approval)
    if args.write:
        out.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_json(out, report)
        guard_out.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_json(guard_out, guard_packet)
    print(json.dumps({
        "status": report["status"],
        "out": rel(out) if args.write else None,
        "guard_out": rel(guard_out) if args.write else None,
        "phase_readiness": report["phase_readiness"],
        "blockers_before_autonomous_paper_execution": report["blockers_before_autonomous_paper_execution"],
        "validation": report["validation"],
    }, indent=2, sort_keys=True))
    return 1 if args.validate and report["validation"]["status"] != "ok" else 0


if __name__ == "__main__":
    raise SystemExit(main())
