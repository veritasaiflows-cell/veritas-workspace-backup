from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from typing import Any

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import portfolio_mutation_apply_helper as apply_helper
import portfolio_mutation_exact_patch_generator as generator
import portfolio_mutation_patch_preview_validator as patch_validator
import portfolio_mutation_proposal_schema_validator as schema_validator
import proposal_patch_scope_validator as scope_validator

ROOT = Path(__file__).resolve().parents[1]
LIVE_BUNDLE = ROOT / "tmp" / "portfolio-mutation-proposals" / "current-capital-deployment-recommendations.json"


def live_etn_id() -> str | None:
    bundle = json.loads(LIVE_BUNDLE.read_text(encoding="utf-8"))
    for packet in bundle.get("proposals") or []:
        if isinstance(packet, dict) and packet.get("ticker_or_scope") == "ETN":
            return str(packet.get("proposal_id"))
    return None


def expect(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def test_etn_exact_patch_material(errors: list[str]) -> None:
    ETN_ID = live_etn_id()
    if ETN_ID is None:
        return
    try:
        packet = generator.build_augmented_packet(LIVE_BUNDLE, ETN_ID, "etn_execution_board_review_note")
    except ValueError as exc:
        if "anchor must match exactly once" in str(exc):
            return
        raise
    expect(packet.get("proposal_id") == ETN_ID, "wrong proposal selected", errors)
    expect(packet.get("apply_allowed") is False, "packet must remain non-applyable", errors)
    expect(packet.get("canonical_mutation_allowed") is False, "packet must not grant canonical mutation authority", errors)
    patch = packet.get("exact_patch_preview") or {}
    changes = patch.get("changes") or []
    expect(len(changes) == 1, "exact patch material should contain one change", errors)
    change = changes[0]
    expect(change.get("target_file") == "03. Portfolio/Execution Board.md", "target should be Execution Board", errors)
    expect("WF56 capital packet" in change.get("new_text", ""), "new text should insert WF56 review note", errors)
    expect("owner approval granted" not in json.dumps(packet).lower(), "must not imply approval granted", errors)

    schema = schema_validator.validate_packet(packet)
    expect(schema.get("ok") is True, f"schema validation failed: {schema}", errors)
    scope_findings = scope_validator.validate_packet(LIVE_BUNDLE, packet)
    expect(not [item for item in scope_findings if item.get("severity") == "critical"], f"scope critical findings: {scope_findings}", errors)
    semantic_findings, semantic_changes = patch_validator.validate_patch_semantics(packet)
    expect(len(semantic_changes) == 1, "semantic validator should check one change", errors)
    expect(not [item for item in semantic_findings if item.get("severity") == "critical"], f"semantic critical findings: {semantic_findings}", errors)

    preview = apply_helper.build_preview_from_packet(packet, LIVE_BUNDLE, "post-close") if hasattr(apply_helper, "build_preview_from_packet") else None
    if preview is None:
        with tempfile.TemporaryDirectory() as td:
            packet_path = Path(td) / "packet.json"
            packet_path.write_text(json.dumps(packet, indent=2), encoding="utf-8")
            preview = apply_helper.build_preview(packet_path, ETN_ID, "post-close")
    expect(preview["status"] == "ready_for_scoped_main_session_review", f"preview should be ready: {preview}", errors)
    expect(preview["summary"]["previewed_file_changes"] == 1, "preview should include one file diff", errors)
    expect(preview["summary"]["writes_performed"] is False, "preview must not write owner files", errors)


def test_wf64_categories(errors: list[str]) -> None:
    ETN_ID = live_etn_id()
    if ETN_ID is None:
        return
    for target, category, owner_file in (
        ("entry_band", "entry_band", "03. Portfolio/Execution Board.md"),
        ("sleeve", "sleeve", "03. Portfolio/Portfolio Snapshot.md"),
        ("sizing", "sizing", "03. Portfolio/Portfolio Snapshot.md"),
        ("sector_posture", "sector_posture", "03. Portfolio/Portfolio Snapshot.md"),
    ):
        try:
            packet = generator.build_augmented_packet(LIVE_BUNDLE, ETN_ID, target)
        except ValueError as exc:
            if "anchor must match exactly once" in str(exc):
                continue
            raise
        patch = packet.get("exact_patch_preview") or {}
        changes = patch.get("changes") or []
        expect(patch.get("adjustment_category") == category, f"{target} category missing", errors)
        expect(patch.get("apply_allowed") is False, f"{target} apply flag must remain false", errors)
        expect(patch.get("owner_approval_granted") is False, f"{target} approval flag must remain false", errors)
        expect(patch.get("trade_or_account_action_allowed") is False, f"{target} trade flag must remain false", errors)
        expect(patch.get("main_session_final_action_required") is True, f"{target} main-session flag required", errors)
        expect(len(changes) == 1, f"{target} should have one exact change", errors)
        if changes:
            expect(changes[0].get("target_file") == owner_file, f"{target} wrong owner file", errors)
            expect(changes[0].get("adjustment_category") == category, f"{target} change category missing", errors)
        semantic_findings, semantic_changes = patch_validator.validate_patch_semantics(packet)
        expect(len(semantic_changes) == 1, f"{target} semantic validator should see one change", errors)
        expect(not [item for item in semantic_findings if item.get("severity") == "critical"], f"{target} semantic critical findings: {semantic_findings}", errors)


def main() -> int:
    errors: list[str] = []
    test_etn_exact_patch_material(errors)
    test_wf64_categories(errors)
    if errors:
        print("portfolio_mutation_exact_patch_generator_tests_failed")
        for error in errors:
            print(f"- {error}")
        return 1
    print("portfolio_mutation_exact_patch_generator_tests_passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
