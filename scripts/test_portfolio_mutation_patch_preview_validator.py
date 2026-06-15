from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from typing import Any

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import portfolio_mutation_patch_preview_validator as validator
from test_portfolio_mutation_apply_helper import base_packet

ROOT = Path(__file__).resolve().parents[1]


def expect(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def with_target() -> Path:
    target = ROOT / "tmp" / "portfolio-mutation-proposals" / "test-owner-surface.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("Header\nOld owner-reviewed sentence.\nFooter\n", encoding="utf-8")
    return target


def run_report(packet: dict[str, Any]) -> dict[str, Any]:
    with tempfile.TemporaryDirectory() as td:
        bundle_path = Path(td) / "proposal.json"
        write_json(bundle_path, packet)
        return validator.build_report(bundle_path, "test-phase3-preview")


def test_valid_patch_preview(errors: list[str]) -> None:
    target = with_target()
    try:
        report = run_report(base_packet())
        expect(report["status"] == "ok", f"valid exact patch preview should pass: {report}", errors)
        expect(report["summary"]["changes_checked"] == 1, "one change checked", errors)
        expect(report["authority"]["apply_ready"] is False, "validator must not mark apply ready", errors)
        expect(report["authority"]["approval_artifact_required"] is True, "approval artifact required", errors)
    finally:
        target.unlink(missing_ok=True)


def test_missing_patch_blocks(errors: list[str]) -> None:
    packet = base_packet()
    packet.pop("exact_patch_preview")
    report = run_report(packet)
    expect(report["status"] == "blocked", "missing exact patch material must block", errors)


def test_duplicate_old_text_blocks(errors: list[str]) -> None:
    target = with_target()
    target.write_text("Old owner-reviewed sentence.\nOld owner-reviewed sentence.\n", encoding="utf-8")
    try:
        report = run_report(base_packet())
        expect(report["status"] == "blocked", "old_text matching twice must block", errors)
    finally:
        target.unlink(missing_ok=True)


def main() -> int:
    errors: list[str] = []
    test_valid_patch_preview(errors)
    test_missing_patch_blocks(errors)
    test_duplicate_old_text_blocks(errors)
    if errors:
        print("portfolio_mutation_patch_preview_validator_tests_failed")
        for error in errors:
            print(f"- {error}")
        return 1
    print("portfolio_mutation_patch_preview_validator_tests_passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
