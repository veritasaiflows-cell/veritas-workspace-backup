from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import portfolio_mutation_approval_artifact_validator as approval_validator
import portfolio_mutation_scoped_apply_helper as apply_helper

ROOT = Path(__file__).resolve().parents[1]
APPROVAL_DIR = ROOT / "tmp" / "portfolio-mutation-proposals" / "approvals"
PROPOSAL_PATH = ROOT / "tmp" / "portfolio-mutation-proposals" / "test-phase4-scoped-apply-proposal.json"
PREVIEW_PATH = ROOT / "tmp" / "portfolio-mutation-proposals" / "patch-previews" / "test-phase4-scoped-apply-preview.json"
PROPOSAL = str(PROPOSAL_PATH.relative_to(ROOT)).replace("\\", "/")
PREVIEW = str(PREVIEW_PATH.relative_to(ROOT)).replace("\\", "/")
PROPOSAL_ID = "test-phase4:ETN:entry-band:fixture"


def expect(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def ensure_fixture_files() -> None:
    target = ROOT / "03. Portfolio" / "Execution Board.md"
    row = next(line for line in target.read_text(encoding="utf-8").splitlines() if line.startswith("| ETN |"))
    new_row = row.replace("Manual-only; no chase above approved band;", "Manual-only; no chase above approved band; phase4 fixture visibility only;")
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
                    "rationale": "Dry-run fixture; no execution.",
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
                "diff": "--- a/03. Portfolio/Execution Board.md\n+++ b/03. Portfolio/Execution Board.md\n@@ fixture\n-phase4 fixture old\n+phase4 fixture new\n",
            }
        ],
    }
    PROPOSAL_PATH.parent.mkdir(parents=True, exist_ok=True)
    PREVIEW_PATH.parent.mkdir(parents=True, exist_ok=True)
    PROPOSAL_PATH.write_text(json.dumps(packet, indent=2) + "\n", encoding="utf-8")
    PREVIEW_PATH.write_text(json.dumps(preview, indent=2) + "\n", encoding="utf-8")


def cleanup_fixture_files() -> None:
    PROPOSAL_PATH.unlink(missing_ok=True)
    PREVIEW_PATH.unlink(missing_ok=True)


def approval_payload(*, diff_hash: str | None = None, status: str = "approved", categories: list[str] | None = None) -> dict:
    ensure_fixture_files()
    preview = approval_validator.load_json(ROOT / PREVIEW)
    return {
        "schema_version": 1,
        "artifact_type": "wf56_scoped_apply_approval",
        "approval_artifact_id": "test-etn-scoped-approval",
        "approval_status": status,
        "approved_by": "Randall-test-fixture",
        "approved_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "expires_at_utc": (datetime.now(timezone.utc) + timedelta(days=1)).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "proposal_id": PROPOSAL_ID,
        "proposal_artifact": PROPOSAL,
        "preview_artifact": PREVIEW,
        "approved_target_files": approval_validator.preview_target_files(preview),
        "approved_diff_sha256": diff_hash or approval_validator.preview_diff_hash(preview),
        "owner_approval_granted": True,
        "scoped_owner_file_write_allowed": True,
        "canonical_note_write_allowed": True,
        "trade_or_account_action_allowed": False,
        "trade_execution_allowed": False,
        "brokerage_order_allowed": False,
        "money_movement_allowed": False,
        "sizing_sleeve_cash_risk_rule_allowed": False,
        "approved_adjustment_categories": categories if categories is not None else ["entry_band"],
        "execution_entitlement_allowed": False,
        "owner_approval_inferred": False,
        "scope_note": "Test fixture for dry-run validation only.",
    }


def write_approval(name: str, payload: dict) -> Path:
    APPROVAL_DIR.mkdir(parents=True, exist_ok=True)
    path = APPROVAL_DIR / name
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path


def test_approval_validator_ok(errors: list[str]) -> None:
    path = write_approval("test-valid-etn-approval.json", approval_payload())
    report = approval_validator.validate_approval(path)
    expect(report["status"] == "ok", f"valid approval artifact should pass: {report}", errors)
    path.unlink(missing_ok=True)


def test_approval_validator_blocks_wrong_hash(errors: list[str]) -> None:
    path = write_approval("test-bad-hash-etn-approval.json", approval_payload(diff_hash="bad"))
    report = approval_validator.validate_approval(path)
    expect(report["status"] == "blocked", "wrong diff hash should block", errors)
    path.unlink(missing_ok=True)


def test_approval_validator_blocks_category_mismatch(errors: list[str]) -> None:
    path = write_approval("test-category-mismatch-etn-approval.json", approval_payload(categories=["sizing"]))
    report = approval_validator.validate_approval(path)
    expect(report["status"] == "blocked", "approval categories must cover exact patch categories", errors)
    expect(
        any("approved_adjustment_categories does not cover" in item.get("issue", "") for item in report.get("findings", [])),
        f"expected category mismatch finding, got: {report}",
        errors,
    )
    path.unlink(missing_ok=True)


def test_scoped_apply_dry_run(errors: list[str]) -> None:
    path = write_approval("test-dry-run-etn-approval.json", approval_payload())
    before = (ROOT / "03. Portfolio" / "Execution Board.md").read_text(encoding="utf-8")
    result = apply_helper.build_result(str(path.relative_to(ROOT)).replace("\\", "/"), execute=False, window="post-close", confirm_proposal_id=PROPOSAL_ID)
    after = (ROOT / "03. Portfolio" / "Execution Board.md").read_text(encoding="utf-8")
    expect(result["status"] == "ready_to_apply_with_execute", f"dry run should be ready: {result}", errors)
    expect(result["summary"]["planned_file_changes"] == 1, "dry run should plan one change", errors)
    expect(result["summary"]["writes_performed"] is False, "dry run must not write", errors)
    expect(before == after, "dry run must not mutate Execution Board", errors)
    path.unlink(missing_ok=True)


def test_post_apply_execute_requires_approval(errors: list[str]) -> None:
    proc = subprocess.run([sys.executable, "scripts/post_apply_validation_chain.py", "--execute"], cwd=ROOT, text=True, capture_output=True)
    expect(proc.returncode != 0, "post-apply execute without approval artifact must fail", errors)
    expect("blocked" in proc.stdout, f"expected blocked stdout, got: {proc.stdout}", errors)


def test_post_apply_execute_blocks_invalid_approval(errors: list[str]) -> None:
    proc = subprocess.run([
        sys.executable,
        "scripts/post_apply_validation_chain.py",
        "--execute",
        "--approval-artifact",
        "tmp/portfolio-mutation-proposals/approvals/draft-etn-scoped-apply-approval-2026-05-14.json",
    ], cwd=ROOT, text=True, capture_output=True)
    expect(proc.returncode != 0, "post-apply execute with draft approval artifact must fail", errors)
    expect("blocked" in proc.stdout, f"expected blocked stdout, got: {proc.stdout}", errors)


def main() -> int:
    errors: list[str] = []
    try:
        test_approval_validator_ok(errors)
        test_approval_validator_blocks_wrong_hash(errors)
        test_approval_validator_blocks_category_mismatch(errors)
        test_scoped_apply_dry_run(errors)
        test_post_apply_execute_requires_approval(errors)
        test_post_apply_execute_blocks_invalid_approval(errors)
    finally:
        cleanup_fixture_files()
    if errors:
        print("portfolio_mutation_phase4_scoped_apply_tests_failed")
        for error in errors:
            print(f"- {error}")
        return 1
    print("portfolio_mutation_phase4_scoped_apply_tests_passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
