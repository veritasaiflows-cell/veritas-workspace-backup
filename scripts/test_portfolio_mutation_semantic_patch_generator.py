from __future__ import annotations

import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import portfolio_mutation_semantic_patch_generator as generator

ROOT = Path(__file__).resolve().parents[1]
BUNDLE = ROOT / "tmp" / "portfolio-mutation-proposals" / "current-capital-deployment-recommendations.json"
PORTFOLIO_SNAPSHOT = ROOT / "03. Portfolio" / "Portfolio Snapshot.md"
CATEGORIES = ("entry_band", "earnings_state", "ticker_state", "sleeve", "sizing", "sector_posture")
FORBIDDEN_TEXT = ("owner-approved", "owner approved", "approved add", " trade ", " execute ", " buy ", " sell ", " trim ")


def expect(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def test_category(category: str, errors: list[str]) -> None:
    try:
        packet = generator.build_augmented_packet(BUNDLE, None, "ETN", category)
    except ValueError as exc:
        message = str(exc)
        if category in {"entry_band", "sizing"} and "semantic note already current" in message:
            return
        if category == "earnings_state" and "no anchor line found" in message:
            return
        errors.append(f"{category}: unexpected generation failure: {exc}")
        return
    validation = generator.validation_summary(packet, BUNDLE)
    expect(validation["critical_count"] == 0, f"{category}: validation criticals {validation}", errors)
    patch = packet.get("exact_patch_preview") or {}
    expect(patch.get("adjustment_category") == category, f"{category}: patch category mismatch", errors)
    expect(patch.get("apply_allowed") is False, f"{category}: patch apply_allowed must be false", errors)
    expect(patch.get("owner_approval_granted") is False, f"{category}: patch owner_approval_granted must be false", errors)
    expect(patch.get("trade_or_account_action_allowed") is False, f"{category}: patch trade_or_account_action_allowed must be false", errors)
    changes = patch.get("changes") or []
    expect(len(changes) == 1, f"{category}: expected one exact change", errors)
    change = changes[0] if changes else {}
    expect(change.get("adjustment_category") == category, f"{category}: change category mismatch", errors)
    expect(change.get("operation") == "exact_text_replace", f"{category}: operation mismatch", errors)
    target = change.get("target_file")
    if category in {"entry_band", "earnings_state", "ticker_state"}:
        expect(target == "03. Portfolio/Execution Board.md", f"{category}: expected Execution Board target, got {target}", errors)
    else:
        expect(target == "03. Portfolio/Portfolio Snapshot.md", f"{category}: expected Portfolio Snapshot target, got {target}", errors)
    combined = "\n".join(str(change.get(key) or "") for key in ("old_text", "new_text", "rationale"))
    lowered = f" {combined.lower()} "
    for term in FORBIDDEN_TEXT:
        expect(term not in lowered, f"{category}: forbidden text leaked: {term.strip()}", errors)


def test_snapshot_append_reuses_single_section(errors: list[str]) -> None:
    original = PORTFOLIO_SNAPSHOT.read_text(encoding="utf-8")
    try:
        PORTFOLIO_SNAPSHOT.write_text(
            "# Snapshot\n\n## WF64 semantic sync notes\n\n- WF64 sizing semantic sync (ETN): existing\n\n## Freshness and refresh policy\n",
            encoding="utf-8",
        )
        change = generator.upsert_snapshot_note(
            "MSFT",
            "- WF64 sizing semantic sync (MSFT):",
            "- WF64 sizing semantic sync (MSFT): appended",
        )
        expect(change.get("old_text", "").count("## WF64 semantic sync notes") == 1, "snapshot append should target the existing single WF64 section", errors)
        expect("WF64 sizing semantic sync (ETN): existing" in str(change.get("old_text") or ""), "existing note should remain inside the replaced section block", errors)
        expect(str(change.get("new_text") or "").count("## WF64 semantic sync notes") == 1, "snapshot append should not duplicate the WF64 section header", errors)
        expect("WF64 sizing semantic sync (MSFT): appended" in str(change.get("new_text") or ""), "new sizing line should append into the existing section", errors)
    finally:
        PORTFOLIO_SNAPSHOT.write_text(original, encoding="utf-8")


def main() -> int:
    errors: list[str] = []
    for category in CATEGORIES:
        test_category(category, errors)
    test_snapshot_append_reuses_single_section(errors)
    if errors:
        print("portfolio_mutation_semantic_patch_generator_tests_failed")
        for error in errors:
            print(f"- {error}")
        return 1
    print("portfolio_mutation_semantic_patch_generator_tests_passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
