#!/usr/bin/env python3
"""Formal WF78 tier-label apply-closeout (no universe/canon mutation).

Owner approved Tier B research-bench labels in the decision register, but only a
top-3 batch had a formal apply-closeout recorded. This produces the full-set
closeout that formally acknowledges every owner-approved label in the DERIVED
routing layer. The former legacy tier-label divergence metric was retired on
2026-08-20; legacy-seeded tiers are now tracked by the legacy-label retirement
guard. It does not mutate universe-v1.json, canon, portfolio notes, SQL, or
ticker cards.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, load_json_artifact

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
REGISTER = TMP / "wf78-tier-label-decision-register.json"
SYNC_PREVIEW = TMP / "wf78-tier-label-sync-preview.json"
AUTO_ROUTER = TMP / "wf78-auto-tier-routing.json"
RETIREMENT_GUARD = TMP / "wf78-legacy-label-retirement-guard.json"
DEFAULT_OUT = TMP / "wf78-tier-label-apply-closeout.json"
SCHEMA = "veritas.wf78_tier_label_apply_closeout.v1"

OWNER_APPROVAL_REFERENCE = "webchat 2026-08-16 18:33 MST Randall: Yes continue 1, 2 and 3 (label-only, no universe mutation)"

AUTHORITY_BOUNDARY: dict[str, bool] = {
    "review_only": True,
    "derived_non_capital_routing_state_updated": True,
    "auto_router_is_current_tier_authority": True,
    "owner_approval_inferred_beyond_exact_label_scope": False,
    "universe_mutation_allowed": False,
    "canon_or_portfolio_mutation_allowed": False,
    "ticker_card_mutation_allowed": False,
    "sql_canon_mutation_allowed": False,
    "capital_deployment_allowed": False,
    "capital_deployment_approved": False,
    "trade_or_execution_allowed": False,
    "trade_or_execution_approved": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "money_movement_allowed": False,
}
REQUIRED_TRUE_FLAGS = {
    "review_only",
    "derived_non_capital_routing_state_updated",
    "auto_router_is_current_tier_authority",
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


def sym(value: Any) -> str:
    return str(value or "").strip().upper()


def add_check(checks: list[dict[str, Any]], name: str, ok: bool, detail: Any = None, severity: str = "critical") -> None:
    checks.append({"name": name, "ok": bool(ok), "status": "ok" if ok else "fail", "severity": severity, "detail": detail})


def router_map(router: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {sym(row.get("ticker")): row for row in as_list(router.get("rows")) if isinstance(row, dict) and sym(row.get("ticker"))}


def build_report() -> dict[str, Any]:
    register = as_dict(load_json_artifact(REGISTER))
    preview = as_dict(load_json_artifact(SYNC_PREVIEW))
    router = as_dict(load_json_artifact(AUTO_ROUTER))
    retirement_guard = as_dict(load_json_artifact(RETIREMENT_GUARD))
    routes = router_map(router)

    preview_rows = {sym(row.get("ticker")): row for row in as_list(preview.get("rows")) if isinstance(row, dict)}

    rows: list[dict[str, Any]] = []
    for ticker, prow in sorted(preview_rows.items()):
        route = routes.get(ticker, {})
        already_legacy_b = prow.get("proposed_sync_action") == "no_legacy_tier_change_needed"
        rows.append({
            "ticker": ticker,
            "name": prow.get("name"),
            "auto_tier": route.get("auto_tier"),
            "auto_state": route.get("auto_state"),
            "approved_label": "Tier B",
            "approved_role": "research_bench",
            "deployment_ready": False,
            "capital_deployment_approved": False,
            "trade_or_execution_approved": False,
            "requires_separate_capital_or_execution_approval": True,
            "would_mutate_universe": False,
            "closeout_disposition": (
                "already_legacy_b_no_change" if already_legacy_b
                else "label_acknowledged_derived_legacy_divergence_accepted"
            ),
        })

    newly_recorded = [r for r in rows if r["closeout_disposition"] == "label_acknowledged_derived_legacy_divergence_accepted"]
    already_b = [r for r in rows if r["closeout_disposition"] == "already_legacy_b_no_change"]
    guard_summary = as_dict(retirement_guard.get("summary"))

    checks: list[dict[str, Any]] = []
    add_check(checks, "register_present", bool(register), rel(REGISTER))
    add_check(checks, "register_validation_ok", as_dict(register.get("validation")).get("status") == "ok", as_dict(register.get("validation")).get("status"))
    add_check(checks, "sync_preview_present", bool(preview), rel(SYNC_PREVIEW))
    add_check(checks, "sync_preview_status_ready", preview.get("status") == "preview_ready", preview.get("status"))
    add_check(checks, "auto_router_status_ok", router.get("status") == "ok", router.get("status"))
    add_check(checks, "retirement_guard_present_and_ok", retirement_guard.get("status") == "ok", retirement_guard.get("status"))
    add_check(checks, "legacy_label_refs_zero", guard_summary.get("active_legacy_label_refs") == 0, guard_summary.get("active_legacy_label_refs"))
    add_check(checks, "all_rows_label_only_no_universe_mutation", all(r["would_mutate_universe"] is False for r in rows), len(rows))
    add_check(checks, "all_rows_capital_execution_gated", all(r["capital_deployment_approved"] is False and r["trade_or_execution_approved"] is False for r in rows), len(rows))
    for flag in sorted(REQUIRED_TRUE_FLAGS):
        add_check(checks, f"authority_{flag}_true", AUTHORITY_BOUNDARY.get(flag) is True, AUTHORITY_BOUNDARY.get(flag))
    for flag in sorted(REQUIRED_FALSE_FLAGS):
        add_check(checks, f"authority_{flag}_false", AUTHORITY_BOUNDARY.get(flag) is False, AUTHORITY_BOUNDARY.get(flag))

    errors = [check for check in checks if check["severity"] == "critical" and not check["ok"]]
    return {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "complete" if not errors else "blocked",
        "workflow": "WF78 - Tier Label Apply Closeout (label-only, no universe mutation)",
        "purpose": (
            "Formally acknowledge every owner-approved Tier B research-bench label in the derived "
            "routing layer. The legacy tier label was retired from the active data plane on "
            "2026-08-20 and is now tracked by the legacy-label retirement guard. No universe/canon mutation."
        ),
        "owner_approval_reference": OWNER_APPROVAL_REFERENCE,
        "authority_boundary": AUTHORITY_BOUNDARY,
        "proof_artifacts": [rel(REGISTER), rel(SYNC_PREVIEW), rel(AUTO_ROUTER), rel(RETIREMENT_GUARD)],
        "summary": {
            "approved_label_count": len(rows),
            "newly_recorded_closeout_count": len(newly_recorded),
            "already_legacy_b_count": len(already_b),
            "universe_mutation_executed": False,
            "canon_mutation_executed": False,
            "legacy_tier_divergence_disposition": "retired_2026_08_20_tracked_by_legacy_label_retirement_guard",
            "active_legacy_label_refs": guard_summary.get("active_legacy_label_refs"),
            "legacy_seeded_tier_count": guard_summary.get("legacy_seeded_tier_count"),
            "escalation_note": (
                "Reducing the sync-preview would_add count to zero requires a separate, explicitly "
                "owner-approved universe-v1.json registry mutation (backup + diff/hash + rollback + "
                "audit). That is intentionally NOT executed here."
            ),
            "next_action": "Tier-label backlog dispositioned. Any canon legacy-tier reconciliation is a separate owner-gated universe mutation.",
        },
        "rows": rows,
        "validation": {
            "status": "ok" if not errors else "error",
            "errors": errors,
            "warnings": [],
            "checks": checks,
        },
        "stop_lines": [
            "This closeout does not mutate universe-v1.json, canon, portfolio notes, SQL, or ticker cards.",
            "Tier B here means research-bench label only, not deployment readiness or coverage promotion.",
            "No capital deployment, trade, paper/live order, account action, or money movement authority is created.",
            "A recorded closeout is not owner approval to mutate the canonical legacy tier field.",
        ],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = build_report()
    out = args.out if args.out.is_absolute() else ROOT / args.out
    if args.write:
        atomic_write_json(out, report)
    print(json.dumps({
        "status": report.get("status"),
        "out": rel(out),
        "summary": report.get("summary"),
        "validation": {
            "status": as_dict(report.get("validation")).get("status"),
            "errors": len(as_list(as_dict(report.get("validation")).get("errors"))),
        },
    }, indent=2))
    if args.validate and as_dict(report.get("validation")).get("status") != "ok":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
