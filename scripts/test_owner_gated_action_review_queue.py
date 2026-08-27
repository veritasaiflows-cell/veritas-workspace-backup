from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "owner_gated_action_review_queue.py"

REQUIRED_GATES = {
    "skill_approval",
    "cron_schedule_mutation",
    "finance_canon_portfolio_mutation",
    "capital_deployment",
    "execution",
}

FALSE_FLAGS = (
    "skill_application_allowed",
    "skill_approval_allowed",
    "cron_schedule_mutation_allowed",
    "cron_state_mutation_allowed",
    "runtime_config_mutation_allowed",
    "finance_canon_or_portfolio_mutation_allowed",
    "cash_sizing_sleeve_risk_rule_mutation_allowed",
    "capital_deployment_allowed",
    "capital_deployment_approved",
    "trade_or_execution_allowed",
    "trade_or_execution_approved",
    "paper_or_live_execution_allowed",
    "brokerage_or_account_action_allowed",
    "money_movement_allowed",
    "owner_approval_inferred",
    "auto_apply_allowed",
)


def expect(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def main() -> int:
    errors: list[str] = []
    out = ROOT / "tmp" / "test-owner-gated-action-review-queue.json"
    md = ROOT / "tmp" / "test-owner-gated-action-review-queue.md"
    cmd = [
        sys.executable,
        str(SCRIPT),
        "--write",
        "--write-md",
        "--validate",
        "--json-out",
        str(out),
        "--md-out",
        str(md),
    ]
    completed = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True)
    expect(completed.returncode == 0, f"queue script failed: {completed.stdout} {completed.stderr}", errors)
    payload = json.loads(out.read_text(encoding="utf-8"))
    expect(payload.get("schema") == "veritas.owner_gated_action_review_queue.v1", "schema mismatch", errors)
    expect(payload.get("validation", {}).get("status") == "ok", "validation should be ok", errors)
    gates = {item.get("gate") for item in payload.get("review_items", [])}
    expect(REQUIRED_GATES.issubset(gates), f"missing gates: {sorted(REQUIRED_GATES - gates)}", errors)
    summary = payload.get("summary", {})
    expect(summary.get("owner_decision_required_count", 0) > 0, "expected owner decision items", errors)
    boundary = payload.get("authority_boundary", {})
    expect(boundary.get("review_only") is True, "queue must stay review-only", errors)
    for flag in FALSE_FLAGS:
        expect(boundary.get(flag) is False, f"queue boundary must stay false: {flag}", errors)
    for item in payload.get("review_items", []):
        item_boundary = item.get("authority_boundary", {})
        for flag in FALSE_FLAGS:
            expect(item_boundary.get(flag) is False, f"item boundary must stay false: {item.get('item_id')} {flag}", errors)
    capital_items = [item for item in payload.get("review_items", []) if item.get("gate") == "capital_deployment"]
    expect(capital_items, "expected capital deployment review items", errors)
    for item in capital_items:
        if item.get("risk") == "review_advance_approved_execution_blocked":
            title = str(item.get("title") or "")
            recommendation = str(item.get("recommendation") or "")
            expect("approved for review advance" in title, "review-approved item title must be plain", errors)
            expect("exact order card" in recommendation, "review-approved item must block execution until exact order card", errors)
            expect(item.get("decision_state") == "owner_review_advance_approved_execution_blocked", "review-approved item must remain execution-blocked", errors)
            expect(
                "exact ticker/side/quantity-or-notional/order-type/TIF/limit owner approval" in item.get("required_before_apply", []),
                "review-approved item must require exact order terms",
                errors,
            )
        elif item.get("risk") == "wf78_wf85_decision_contract_conflict":
            title = str(item.get("title") or "")
            recommendation = str(item.get("recommendation") or "")
            expect("Routing candidate needs WF85 decision reconciliation" in title, "conflict title must be explicit", errors)
            expect("approval-ready" in recommendation, "conflict recommendation must name blocked approval-ready language", errors)
            expect(
                "WF85 decision_state and decision-grade gate must clear" in item.get("required_before_apply", []),
                "conflict item must require WF85 gate clearance",
                errors,
            )
        else:
            expect(
                "Capital review card ready" not in str(item.get("title") or "") or item.get("risk") == "capital_review_only",
                "card-ready language must be reserved for capital_review_only items",
                errors,
            )
    expect(md.exists(), "markdown output missing", errors)

    if errors:
        for error in errors:
            print(f"FAIL: {error}")
        return 1
    print("ok: owner-gated action review queue is complete and non-authorizing")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
