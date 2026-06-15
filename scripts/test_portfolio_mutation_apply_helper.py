from __future__ import annotations

import json
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import portfolio_mutation_apply_helper as helper

ROOT = Path(__file__).resolve().parents[1]


def expect(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def base_packet() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "generated_at_utc": "2026-05-14T00:00:00Z",
        "proposal_id": "test-phase3-preview",
        "mutation_type": "canonical_status_move",
        "ticker_or_scope": "TEST",
        "current_state": {},
        "proposed_state": {},
        "why_now": "review-only proposal; no authority granted",
        "evidence": ["manual review evidence"],
        "source_freshness": {"overall_classification": "current", "trust_level": "clean"},
        "base_case": "review only",
        "bear_case": "review only",
        "risk_rule_check": {"status": "pass", "references": ["25% sector cap", "15% normal single-name ceiling", "speculative sleeve cap", "catalyst-window exception"]},
        "concentration_check": {"status": "pass", "single_name_after_pct": 10},
        "technical_gate": {"status": "pass"},
        "catalyst_gate": {"status": "clear"},
        "proposed_files_to_edit": ["tmp/portfolio-mutation-proposals/test-owner-surface.md"],
        "rollback_or_reversal_note": "discard preview artifact if rejected",
        "stop_lines_triggered": ["owner decision required"],
        "owner_decision_required": True,
        "owner_approval_granted": False,
        "apply_allowed": False,
        "canonical_mutation_allowed": False,
        "portfolio_mutation_allowed": False,
        "trade_or_account_action_allowed": False,
        "main_session_final_action_required": True,
        "current_status_tuple": {
            "coverage_watchlist": "tracked",
            "execution_board": "watch",
            "portfolio_snapshot": "watch",
            "portfolio_config": "WATCH",
        },
        "proposed_status_tuple": {
            "coverage_watchlist": "tracked",
            "execution_board": "watch",
            "portfolio_snapshot": "watch",
            "portfolio_config": "WATCH",
        },
        "affected_owner_surfaces": ["coverage_watchlist", "execution_board", "portfolio_snapshot", "portfolio_config"],
        "field_level_deltas": [{"owner_surface": "execution_board", "field": "note", "from": "old", "to": "new", "mutation_class": "review_only"}],
        "canonical_invariant_checks": {"status": "pass"},
        "exact_patch_preview": {
            "adjustment_category": "review_note",
            "apply_allowed": False,
            "owner_approval_granted": False,
            "trade_or_account_action_allowed": False,
            "main_session_final_action_required": True,
            "changes": [
                {
                    "path": "tmp/portfolio-mutation-proposals/test-owner-surface.md",
                    "adjustment_category": "review_note",
                    "old_text": "Old owner-reviewed sentence.",
                    "new_text": "New owner-reviewed sentence.",
                    "rationale": "test exact preview",
                }
            ]
        },
    }


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def preview_diff_hash(preview: dict[str, Any]) -> str:
    diffs = []
    for item in preview.get("file_previews") or []:
        if isinstance(item, dict):
            diffs.append(str(item.get("path") or ""))
            diffs.append(str(item.get("diff") or ""))
    return helper.sha256_text("\n".join(diffs))


def approval_artifact(proposal_path: Path, preview_path: Path, preview: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "artifact_type": "wf56_scoped_apply_approval",
        "approval_status": "approved",
        "owner_approval_granted": True,
        "scoped_owner_file_write_allowed": True,
        "canonical_note_write_allowed": True,
        "trade_or_account_action_allowed": False,
        "trade_execution_allowed": False,
        "brokerage_order_allowed": False,
        "money_movement_allowed": False,
        "execution_entitlement_allowed": False,
        "owner_approval_inferred": False,
        "sizing_sleeve_cash_risk_rule_allowed": False,
        "approved_adjustment_categories": ["review_note"],
        "expires_at_utc": "2099-01-01T00:00:00Z",
        "proposal_id": "test-phase3-preview",
        "proposal_artifact": str(proposal_path.relative_to(ROOT)).replace("\\", "/"),
        "preview_artifact": str(preview_path.relative_to(ROOT)).replace("\\", "/"),
        "approved_diff_sha256": preview_diff_hash(preview),
        "approved_target_files": [item["path"] for item in preview.get("file_previews") or []],
    }


def test_exact_preview(errors: list[str]) -> None:
    target = ROOT / "tmp" / "portfolio-mutation-proposals" / "test-owner-surface.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    original = "Header\nOld owner-reviewed sentence.\nFooter\n"
    target.write_text(original, encoding="utf-8")
    try:
        with tempfile.TemporaryDirectory() as td:
            bundle_path = Path(td) / "proposal.json"
            write_json(bundle_path, base_packet())
            preview = helper.build_preview(bundle_path, "test-phase3-preview", "post-close")
            expect(preview["status"] == "ready_for_scoped_main_session_review", f"preview should be ready: {preview}", errors)
            expect(preview["summary"]["previewed_file_changes"] == 1, "one file preview expected", errors)
            expect(preview["authority"]["apply_allowed_by_this_helper"] is False, "helper must not grant apply authority", errors)
            expect(preview["authority"]["write_owner_files_allowed"] is False, "helper must not write owner files", errors)
            expect("New owner-reviewed sentence." in preview["file_previews"][0]["diff"], "diff should include new text", errors)
            expect(target.read_text(encoding="utf-8") == original, "dry-run preview must not mutate target file", errors)
    finally:
        target.unlink(missing_ok=True)


def test_missing_exact_patch_is_noop(errors: list[str]) -> None:
    with tempfile.TemporaryDirectory() as td:
        packet = base_packet()
        packet.pop("exact_patch_preview")
        bundle_path = Path(td) / "proposal.json"
        write_json(bundle_path, packet)
        preview = helper.build_preview(bundle_path, "test-phase3-preview", "post-close")
        expect(preview["status"] == "blocked_missing_exact_patch_material", "missing exact patch should fail closed", errors)
        expect(preview["summary"]["ready_for_main_session_portfolio_mutation_review"] is False, "missing exact patch is not mutation-ready", errors)
        expect(preview["summary"]["approval_artifact_required"] is True, "approval artifact should remain required", errors)


def test_forbidden_apply_flag_blocks(errors: list[str]) -> None:
    with tempfile.TemporaryDirectory() as td:
        packet = base_packet()
        packet["apply_allowed"] = True
        bundle_path = Path(td) / "proposal.json"
        write_json(bundle_path, packet)
        preview = helper.build_preview(bundle_path, "test-phase3-preview", "post-close")
        expect(preview["status"] == "blocked", "apply_allowed=true must block", errors)
        expect(preview["validation"]["schema_validator_ok"] is False, "schema validator should fail apply_allowed=true", errors)


def test_apply_requires_valid_approval(errors: list[str]) -> None:
    with tempfile.TemporaryDirectory(dir=ROOT / "tmp" / "portfolio-mutation-proposals") as td:
        fixture = Path(td)
        target = fixture / "test-owner-surface.md"
        target.write_text("Header\nOld owner-reviewed sentence.\nFooter\n", encoding="utf-8")
        packet = base_packet()
        rel_target = str(target.relative_to(ROOT)).replace("\\", "/")
        packet["proposed_files_to_edit"] = [rel_target]
        packet["exact_patch_preview"]["changes"][0]["path"] = rel_target
        proposal_path = fixture / "proposal.json"
        write_json(proposal_path, packet)
        preview = helper.build_preview(proposal_path, "test-phase3-preview", "post-close")
        preview_path = fixture / "preview.json"
        write_json(preview_path, preview)
        approval = approval_artifact(proposal_path, preview_path, preview)
        approval["approved_diff_sha256"] = "bad-hash"
        approval_path = fixture / "approval.json"
        write_json(approval_path, approval)
        plan = helper.build_apply_plan(approval_path, "post-close")
        expect(plan["status"] == "blocked", "bad approval hash must block apply plan", errors)
        expect(plan["authority"]["apply_allowed"] is False, "invalid approval must keep apply_allowed false", errors)
        expect(target.read_text(encoding="utf-8") == "Header\nOld owner-reviewed sentence.\nFooter\n", "blocked plan must not mutate target", errors)


def test_approval_gated_apply_creates_backup_and_writes_fixture(errors: list[str]) -> None:
    with tempfile.TemporaryDirectory(dir=ROOT / "tmp" / "portfolio-mutation-proposals") as td:
        fixture = Path(td)
        target = fixture / "test-owner-surface.md"
        original = "Header\nOld owner-reviewed sentence.\nFooter\n"
        target.write_text(original, encoding="utf-8")
        packet = base_packet()
        rel_target = str(target.relative_to(ROOT)).replace("\\", "/")
        packet["proposed_files_to_edit"] = [rel_target]
        packet["exact_patch_preview"]["changes"][0]["path"] = rel_target
        proposal_path = fixture / "proposal.json"
        write_json(proposal_path, packet)
        preview = helper.build_preview(proposal_path, "test-phase3-preview", "post-close")
        preview_path = fixture / "preview.json"
        write_json(preview_path, preview)
        approval_path = fixture / "approval.json"
        write_json(approval_path, approval_artifact(proposal_path, preview_path, preview))
        result = helper.execute_apply(approval_path, "post-close")
        expect(result["status"] == "applied_pending_post_apply_validation", f"valid approval should apply fixture: {result}", errors)
        expect(result["summary"]["writes_performed"] is True, "valid approved apply should write fixture", errors)
        expect("New owner-reviewed sentence." in target.read_text(encoding="utf-8"), "target fixture should contain approved new text", errors)
        backup_files = result.get("applied_files") or []
        expect(len(backup_files) == 1, "one backup/apply record expected", errors)
        if backup_files:
            backup_path = ROOT / backup_files[0]["backup_path"]
            expect(backup_path.exists(), "backup file should exist", errors)
            if backup_path.exists():
                expect(backup_path.read_text(encoding="utf-8") == original, "backup must preserve original content", errors)
        backup_root = result.get("rollback_plan", {}).get("backup_root")
        if backup_root:
            shutil.rmtree(ROOT / backup_root, ignore_errors=True)


def main() -> int:
    errors: list[str] = []
    test_exact_preview(errors)
    test_missing_exact_patch_is_noop(errors)
    test_forbidden_apply_flag_blocks(errors)
    test_apply_requires_valid_approval(errors)
    test_approval_gated_apply_creates_backup_and_writes_fixture(errors)
    if errors:
        print("portfolio_mutation_apply_helper_tests_failed")
        for error in errors:
            print(f"- {error}")
        return 1
    print("portfolio_mutation_apply_helper_tests_passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
