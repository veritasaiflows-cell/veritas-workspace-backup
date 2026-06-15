from __future__ import annotations

import json
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import portfolio_mutation_approval_artifact_validator as approval_validator
import write_wf64_approval_templates as templates

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_DIR = ROOT / "tmp" / "portfolio-mutation-proposals" / "approvals" / "templates"
CATEGORIES = {"entry_band", "sleeve", "sizing", "sector_posture"}


def expect(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def load_template(category: str) -> dict:
    path = TEMPLATE_DIR / f"wf64-{category}-approval-template.json"
    return json.loads(path.read_text(encoding="utf-8"))


def test_templates(errors: list[str]) -> None:
    existing = sorted(TEMPLATE_DIR.glob("wf64-*-approval-template.json"))
    expect({path.name for path in existing} == {f"wf64-{category}-approval-template.json" for category in CATEGORIES}, "unexpected template file set", errors)
    for category in CATEGORIES:
        payload = load_template(category)
        expect(payload.get("template_family") == "WF64_guarded_apply_category_template", f"{category}: wrong template family", errors)
        expect(payload.get("approval_status") == "draft_pending_randall_approval", f"{category}: template must remain draft", errors)
        expect(payload.get("owner_approval_granted") is False, f"{category}: owner approval must default false", errors)
        expect(payload.get("scoped_owner_file_write_allowed") is False, f"{category}: scoped write must default false", errors)
        expect(payload.get("canonical_note_write_allowed") is False, f"{category}: canonical write must default false", errors)
        for key in (
            "trade_or_account_action_allowed",
            "trade_execution_allowed",
            "brokerage_order_allowed",
            "money_movement_allowed",
            "sizing_sleeve_cash_risk_rule_allowed",
            "execution_entitlement_allowed",
            "owner_approval_inferred",
            "apply_allowed_without_valid_approval_artifact",
        ):
            expect(payload.get(key) is False, f"{category}: {key} must be false", errors)
        expect(payload.get("source_proposal_id") == templates.PROPOSAL_ID, f"{category}: missing exact source proposal id", errors)
        expect(payload.get("proposal_id") == templates.PROPOSAL_ID, f"{category}: missing proposal id", errors)
        expect(payload.get("expires_at_utc"), f"{category}: expiry is required", errors)
        expect(payload.get("expiry_required") is True, f"{category}: expiry_required must be true", errors)
        expect(payload.get("category_owner"), f"{category}: category owner required", errors)
        expect(payload.get("approved_adjustment_categories") == [category], f"{category}: category scope must be exact", errors)
        exact = payload.get("exact_patch_preview") or {}
        expect(exact.get("source_proposal_id") == templates.PROPOSAL_ID, f"{category}: exact preview source id missing", errors)
        expect(exact.get("approved_adjustment_categories") == [category], f"{category}: exact preview category mismatch", errors)
        expect(exact.get("approved_target_files") == payload.get("approved_target_files"), f"{category}: target file mismatch", errors)
        expect(exact.get("approved_diff_sha256") == payload.get("approved_diff_sha256"), f"{category}: hash mismatch", errors)
        preview = approval_validator.load_json(ROOT / payload["preview_artifact"])
        expect(payload.get("approved_target_files") == approval_validator.preview_target_files(preview), f"{category}: target files must match live preview", errors)
        expect(payload.get("approved_diff_sha256") == approval_validator.preview_diff_hash(preview), f"{category}: diff hash must match live preview", errors)
        expect(len(payload.get("validator_proof_requirements") or []) >= 5, f"{category}: validator proof requirements missing", errors)
        guards = payload.get("guards") or {}
        for key in (
            "no_trade",
            "no_account_action",
            "no_brokerage_order",
            "no_money_movement",
            "no_inferred_owner_approval",
            "no_execution_entitlement_change",
            "no_unscoped_portfolio_mutation",
        ):
            expect(guards.get(key) is True, f"{category}: guard {key} missing", errors)
        report = approval_validator.validate_approval(TEMPLATE_DIR / f"wf64-{category}-approval-template.json")
        expect(report.get("status") == "blocked", f"{category}: draft template should remain blocked until approval", errors)
        issues = {item.get("issue") for item in report.get("findings", [])}
        expect("owner_approval_granted must be true on the approval artifact" in issues, f"{category}: validator must require explicit owner approval", errors)
        expect("scoped_owner_file_write_allowed must be true" in issues, f"{category}: validator must require scoped write gate", errors)
        expect("canonical_note_write_allowed must be true" in issues, f"{category}: validator must require canonical write gate", errors)


def main() -> int:
    errors: list[str] = []
    test_templates(errors)
    if errors:
        print("wf64_approval_template_tests_failed")
        for error in errors:
            print(f"- {error}")
        return 1
    print("wf64_approval_template_tests_passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
