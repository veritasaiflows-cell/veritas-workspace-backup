from __future__ import annotations

import json
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import portfolio_mutation_approval_artifact_validator as approval_validator
import portfolio_mutation_standing_approval_artifact as standing

ROOT = Path(__file__).resolve().parents[1]
PROPOSAL_ID = "test-standing:ETN:entry-band:fixture"
FIXTURE_PROPOSAL = ROOT / "tmp" / "portfolio-mutation-proposals" / "test-standing-approval-proposal.json"
FIXTURE_PREVIEW = ROOT / "tmp" / "portfolio-mutation-proposals" / "patch-previews" / "test-standing-approval-preview.json"


def expect(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def build_fixture_files() -> tuple[str, str]:
    target = ROOT / "03. Portfolio" / "Execution Board.md"
    row = next(line for line in target.read_text(encoding="utf-8").splitlines() if line.startswith("| ETN |"))
    new_row = row.replace(
        "Volatile canon freshness sync only;",
        "Volatile canon freshness sync only; test fixture visibility only;",
    )
    packet = {
        "proposal_id": PROPOSAL_ID,
        "owner_approval_granted": False,
        "apply_allowed": False,
        "canonical_mutation_allowed": False,
        "portfolio_mutation_allowed": False,
        "trade_or_account_action_allowed": False,
        "main_session_final_action_required": True,
        "source_freshness": {"overall_classification": "fresh"},
        "exact_patch_preview": {
            "adjustment_category": "entry_band",
            "changes": [
                {
                    "target_file": "03. Portfolio/Execution Board.md",
                    "operation": "exact_text_replace",
                    "old_text": row,
                    "new_text": new_row,
                    "adjustment_category": "entry_band",
                }
            ],
        },
    }
    preview = {
        "schema_version": 1,
        "status": "ready_for_scoped_main_session_review",
        "proposal_id": PROPOSAL_ID,
        "summary": {"writes_performed": False},
        "file_previews": [
            {
                "path": "03. Portfolio/Execution Board.md",
                "diff": "--- a/03. Portfolio/Execution Board.md\n+++ b/03. Portfolio/Execution Board.md\n@@ fixture\n-test fixture old\n+test fixture new\n",
            }
        ],
    }
    FIXTURE_PROPOSAL.parent.mkdir(parents=True, exist_ok=True)
    FIXTURE_PREVIEW.parent.mkdir(parents=True, exist_ok=True)
    FIXTURE_PROPOSAL.write_text(json.dumps(packet, indent=2) + "\n", encoding="utf-8")
    FIXTURE_PREVIEW.write_text(json.dumps(preview, indent=2) + "\n", encoding="utf-8")
    return str(FIXTURE_PROPOSAL.relative_to(ROOT)), str(FIXTURE_PREVIEW.relative_to(ROOT))


def test_standing_artifact_builds_valid_approval(errors: list[str]) -> None:
    proposal, preview = build_fixture_files()
    payload = standing.build_artifact(proposal, preview, PROPOSAL_ID, expires_hours=24, approved_by="Randall-test-fixture")
    expect(payload.get("approval_status") == "approved", "standing artifact should be approved", errors)
    expect(payload.get("owner_approval_granted") is True, "owner approval gate should be true in approval artifact", errors)
    expect(payload.get("scoped_owner_file_write_allowed") is True, "scoped write gate should be true", errors)
    expect(payload.get("canonical_note_write_allowed") is True, "canonical note write gate should be true", errors)
    expect(payload.get("approved_adjustment_categories") == ["entry_band"], "entry_band category expected", errors)
    for key in ("trade_or_account_action_allowed", "trade_execution_allowed", "brokerage_order_allowed", "money_movement_allowed", "execution_entitlement_allowed", "owner_approval_inferred"):
        expect(payload.get(key) is False, f"{key} must remain false", errors)
    path = ROOT / "tmp" / "portfolio-mutation-proposals" / "approvals" / "test-standing-approval-artifact.json"
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    try:
        report = approval_validator.validate_approval(path)
        expect(report.get("status") == "ok", f"standing artifact should validate: {report}", errors)
    finally:
        path.unlink(missing_ok=True)
        FIXTURE_PROPOSAL.unlink(missing_ok=True)
        FIXTURE_PREVIEW.unlink(missing_ok=True)


def main() -> int:
    errors: list[str] = []
    test_standing_artifact_builds_valid_approval(errors)
    if errors:
        print("portfolio_mutation_standing_approval_artifact_tests_failed")
        for error in errors:
            print(f"- {error}")
        return 1
    print("portfolio_mutation_standing_approval_artifact_tests_passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
