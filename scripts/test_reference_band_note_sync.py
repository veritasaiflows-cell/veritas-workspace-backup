from __future__ import annotations

import reference_band_note_sync as ref_sync
from chain_manifest import manifest_steps


def expect(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def proposal_fixture(**overrides):
    base = {
        "ticker": "AMD",
        "suggested_band_low": 298.49,
        "suggested_band_high": 364.13,
        "suggested_stop": 259.21,
        "entry_band_method": "KELTNER_MA_CONSTRAINED",
        "band_status": "ABOVE_BAND_WAIT",
        "trend_stack": "BULLISH_20_50_200",
        "coverage_lane": "watch",
        "workflow_state": "WATCH",
        "entry_policy": "underdefined",
        "earnings_state": "CLEAR",
        "canonical_apply_eligible": False,
        "data_date": "2026-05-12",
    }
    base.update(overrides)
    return base


def test_restriction_label_preserves_non_execution_authority(errors: list[str]) -> None:
    label = ref_sync.restriction_label(proposal_fixture())
    expect("reference only / no execution entitlement" in label, f"expected reference-only label, got {label}", errors)
    expect("watch/reference lane" in label, f"expected watch-lane blocker, got {label}", errors)
    expect("ABOVE_BAND_WAIT" in label, f"expected band status blocker, got {label}", errors)


def test_note_sync_inserts_reference_band_without_touching_preferred_band(errors: list[str]) -> None:
    original = """# Sheet

### AMD
- Close: **448.29**
- Preferred entry band: **295.33 to 342.53**
- Explicit stop: **271.73**
- Stance: **Watch-only / no chase**.

---
"""
    change = ref_sync.build_change(proposal_fixture())
    updated, missing = ref_sync.sync_sheet(original, [change], "2026-05-12")
    expect(missing == [], f"expected no missing sections, got {missing}", errors)
    expect("Preferred entry band: **295.33 to 342.53**" in updated, "preferred/execution band should not be rewritten", errors)
    expect("Reference band: **298.49 to 364.13** / reference stop **259.21**" in updated, "reference band should be inserted", errors)
    expect("Reference-band authority: **reference only / no execution entitlement" in updated, "authority label should be inserted", errors)
    expect("do not create trade, sizing, sleeve, owner-approval, or execution authority" in updated, "authority boundary should be explicit", errors)


def test_missing_watch_sections_do_not_block(errors: list[str]) -> None:
    changes = [
        ref_sync.build_change(proposal_fixture(ticker="AMD", coverage_lane="watch")),
        ref_sync.build_change(proposal_fixture(ticker="GOOG", coverage_lane="execution")),
    ]
    expect(
        ref_sync.missing_execution_sections(["AMD"], changes) == [],
        "missing watch/reference sections should remain audit-visible but nonblocking",
        errors,
    )
    expect(
        ref_sync.missing_execution_sections(["AMD", "GOOG"], changes) == ["GOOG"],
        "missing execution-lane sections should still block",
        errors,
    )


def test_sql_first_thin_board_short_circuits_markdown_mutation(errors: list[str]) -> None:
    ok = ref_sync.sql_first_thin_board_sync_decision(
        {
            "sql_first_thin_board_detected": True,
            "sql_first_thin_board_allowed": True,
        }
    )
    expect(ok["short_circuit_note_mutation"] is True, f"thin board should short-circuit note mutation, got {ok}", errors)
    expect(ok["status"] == "ok", f"allowed thin board should be ok, got {ok}", errors)
    blocked = ref_sync.sql_first_thin_board_sync_decision(
        {
            "sql_first_thin_board_detected": True,
            "sql_first_thin_board_allowed": False,
        }
    )
    expect(blocked["status"] == "blocked", f"blocked thin board contract should block, got {blocked}", errors)
    legacy = ref_sync.sql_first_thin_board_sync_decision({"sql_first_thin_board_detected": False})
    expect(
        legacy["short_circuit_note_mutation"] is False and legacy["status"] == "legacy_markdown_sections",
        f"non-thin board should use legacy section sync, got {legacy}",
        errors,
    )


def test_manifest_runs_reference_sync_after_auto_apply(errors: list[str]) -> None:
    for window in ("morning", "post-close", "sunday"):
        scripts = [step["script"] for step in manifest_steps(window)]
        expect("reference_band_note_sync.py" in scripts, f"{window} manifest missing reference-band note sync", errors)
        if "reference_band_note_sync.py" in scripts:
            expect(
                scripts.index("auto_apply_entry_band_maintenance.py") < scripts.index("reference_band_note_sync.py") < scripts.index("entry_band_fetch.py"),
                f"{window} reference sync should run after auto-apply and before entry-band/status consumers",
                errors,
            )


def main() -> int:
    errors: list[str] = []
    test_restriction_label_preserves_non_execution_authority(errors)
    test_note_sync_inserts_reference_band_without_touching_preferred_band(errors)
    test_missing_watch_sections_do_not_block(errors)
    test_sql_first_thin_board_short_circuits_markdown_mutation(errors)
    test_manifest_runs_reference_sync_after_auto_apply(errors)
    if errors:
        print("reference_band_note_sync_tests_failed")
        for error in errors:
            print(f"- {error}")
        return 1
    print("reference_band_note_sync_tests_passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
