from __future__ import annotations

import auto_apply_entry_band_maintenance as auto_band
from chain_manifest import manifest_steps


def expect(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def eligible_fixture(**overrides):
    base = {
        "ticker": "ETN",
        "needs_review": True,
        "canonical_apply_eligible": True,
        "entry_band_method": "KELTNER_MA_CONSTRAINED",
        "band_status": "IN_BAND",
        "earnings_state": "CLEAR",
        "suggested_band_low": 368.35,
        "suggested_band_high": 410.45,
        "suggested_stop": 349.21,
        "data_date": "2026-05-12",
    }
    base.update(overrides)
    return base


def test_eligible_proposal_filter(errors: list[str]) -> None:
    eligible, skipped = auto_band.eligible_proposals(
        [
            eligible_fixture(),
            eligible_fixture(ticker="MSFT", canonical_apply_eligible=False),
            eligible_fixture(ticker="AMD", entry_band_method="EARNINGS_FROZEN"),
            eligible_fixture(ticker="NVDA", band_status="ABOVE_BAND"),
            eligible_fixture(ticker="GOOG", earnings_state="BLOCKED"),
        ]
    )
    expect([p["ticker"] for p in eligible] == ["ETN"], f"expected only ETN eligible, got {eligible}", errors)
    skipped_tickers = {item["ticker"] for item in skipped}
    expect({"MSFT", "AMD", "NVDA", "GOOG"}.issubset(skipped_tickers), f"expected skipped tickers, got {skipped_tickers}", errors)


def test_note_sync_updates_band_stop_and_authority_language(errors: list[str]) -> None:
    original = """# Sheet

### ETN
- Close: **398.46**
- Preferred entry band: **395.59 to 420.31** (vault preferred band set 2026-04-30)
- Explicit stop: **383.23**
- Stance: **Deployable now / manual-only**.

---
"""
    updated, missing = auto_band.sync_technical_sheet(
        original,
        [
            {
                "ticker": "ETN",
                "old_low": 395.59,
                "old_high": 420.31,
                "old_stop": 383.23,
                "new_low": 368.35,
                "new_high": 410.45,
                "new_stop": 349.21,
                "method": "KELTNER_PRIMARY",
                "band_status": "IN_BAND",
            }
        ],
        "2026-05-12",
    )
    expect(missing["missing_everywhere"] == [], f"expected no missing sections, got {missing}", errors)
    expect("Preferred entry band: **368.35 to 410.45**" in updated, "preferred band should update", errors)
    expect("Explicit stop: **349.21**" in updated, "explicit stop should update", errors)
    expect("does not create trade, sizing, sleeve, approval, or execution authority" in updated, "authority boundary should be inserted", errors)


def test_table_sync_updates_current_execution_row_without_state_change(errors: list[str]) -> None:
    original = """# Execution Board

## Current execution table

| Ticker | Lane | Action state | Close/date | Band | Stop | Technical posture | Blocker/condition | Authority note | Source/freshness |
|---|---|---|---|---|---|---|---|---|---|
| ETN | Execution | **Deployable now** | 398.46 / 2026-05-12 | 395.59-420.31 | 383.23 | above all MAs | old condition | old authority | old source |

## Parser-compatible technical sections

### ETN
- Preferred entry band: **395.59 to 420.31**
- Explicit stop: **383.23**

---
"""
    updated, missing = auto_band.sync_technical_sheet(
        original,
        [
            {
                "ticker": "ETN",
                "old_low": 395.59,
                "old_high": 420.31,
                "old_stop": 383.23,
                "new_low": 368.35,
                "new_high": 410.45,
                "new_stop": 349.21,
                "method": "KELTNER_PRIMARY",
                "band_status": "IN_BAND",
                "close": 398.46,
                "data_date": "2026-05-12",
            }
        ],
        "2026-05-12",
    )
    expect(missing["missing_everywhere"] == [], f"expected no missing rows/sections, got {missing}", errors)
    expect("| ETN | Execution | **Deployable now** |" in updated, "action state should be preserved", errors)
    expect("| ETN | Execution | **Deployable now** | 398.46 / 2026-05-12 | 368.35-410.45 | 349.21 |" in updated, "table row should update band/stop", errors)
    expect("auto-applied routine technical band maintenance" in updated, "table condition should show automated maintenance", errors)
    expect("no paper/live order authority" in updated, "table authority boundary should be preserved", errors)


def test_table_only_row_is_safe_when_parser_section_missing(errors: list[str]) -> None:
    original = """# Execution Board

## Current execution table

| Ticker | Lane | Action state | Close/date | Band | Stop | Technical posture | Blocker/condition | Authority note | Source/freshness |
|---|---|---|---|---|---|---|---|---|---|
| ETN | Execution | **Deployable now** | 398.46 / 2026-05-12 | 395.59-420.31 | 383.23 | above all MAs | old condition | old authority | old source |

## Parser-compatible technical sections

### JPM
- Preferred entry band: **291.13 to 305.17**
- Explicit stop: **283.33**

---
"""
    updated, missing = auto_band.sync_technical_sheet(
        original,
        [
            {
                "ticker": "ETN",
                "old_low": 395.59,
                "old_high": 420.31,
                "old_stop": 383.23,
                "new_low": 368.35,
                "new_high": 410.45,
                "new_stop": 349.21,
                "method": "KELTNER_PRIMARY",
                "band_status": "IN_BAND",
                "close": 398.46,
                "data_date": "2026-05-12",
            }
        ],
        "2026-05-12",
    )
    expect(missing["missing_table_rows"] == [], f"table row should exist, got {missing}", errors)
    expect(missing["missing_note_sections"] == ["ETN"], f"section should be reported missing, got {missing}", errors)
    expect(missing["missing_everywhere"] == [], f"table-only update should not block, got {missing}", errors)
    expect("| ETN | Execution | **Deployable now** | 398.46 / 2026-05-12 | 368.35-410.45 | 349.21 |" in updated, "table row should still update", errors)


def test_missing_table_and_section_blocks(errors: list[str]) -> None:
    original = """# Execution Board

## Current execution table

| Ticker | Lane | Action state | Close/date | Band | Stop | Technical posture | Blocker/condition | Authority note | Source/freshness |
|---|---|---|---|---|---|---|---|---|---|
| JPM | Execution | **Almost deployable** | 312.37 / 2026-05-12 | 291.13-305.17 | 283.33 | above all MAs | old condition | old authority | old source |

## Parser-compatible technical sections

### JPM
- Preferred entry band: **291.13 to 305.17**
- Explicit stop: **283.33**

---
"""
    _updated, missing = auto_band.sync_technical_sheet(
        original,
        [
            {
                "ticker": "ETN",
                "old_low": 395.59,
                "old_high": 420.31,
                "old_stop": 383.23,
                "new_low": 368.35,
                "new_high": 410.45,
                "new_stop": 349.21,
                "method": "KELTNER_PRIMARY",
                "band_status": "IN_BAND",
            }
        ],
        "2026-05-12",
    )
    expect(missing["missing_table_rows"] == ["ETN"], f"table miss should be reported, got {missing}", errors)
    expect(missing["missing_note_sections"] == ["ETN"], f"section miss should be reported, got {missing}", errors)
    expect(missing["missing_everywhere"] == ["ETN"], f"missing everywhere should block, got {missing}", errors)


def test_manifest_runs_auto_apply_after_band_refresh(errors: list[str]) -> None:
    for window in ("morning", "post-close", "post-earnings"):
        scripts = [step["script"] for step in manifest_steps(window)]
        expect("auto_apply_entry_band_maintenance.py" in scripts, f"{window} missing auto apply step", errors)
        if "auto_apply_entry_band_maintenance.py" in scripts:
            expect(
                scripts.index("band_refresh.py") < scripts.index("auto_apply_entry_band_maintenance.py") < scripts.index("entry_band_fetch.py") if "entry_band_fetch.py" in scripts else scripts.index("band_refresh.py") < scripts.index("auto_apply_entry_band_maintenance.py"),
                f"{window} auto apply should run after band_refresh and before entry-band/status consumers",
                errors,
            )


def test_post_apply_refresh_contract_is_serial_and_fail_closed(errors: list[str]) -> None:
    names = [step["name"] for step in auto_band.POST_APPLY_REFRESH_STEPS]
    expected_prefix = [
        "wf72_entry_stop_worker_refresh",
        "wf72_entry_stop_sql_activate",
        "finance_intelligence_state_build",
        "python_source_truth_parity",
        "go_source_truth_parity",
        "python_go_source_truth_parity",
    ]
    expect(names[: len(expected_prefix)] == expected_prefix, f"post-apply refresh prefix drifted: {names}", errors)
    expect(names.index("canonical_finance_data_plane") < names.index("trade_grade_decision_cards"), "WF84 packet/DB must rebuild before WF85 cards", errors)
    expect(names.index("trade_grade_decision_cards") < names.index("trade_grade_full_answer_assembler"), "WF85 cards must rebuild before full-answer assembler", errors)
    expect(names.index("trade_grade_full_answer_assembler") < names.index("canonical_finance_data_plane_post_wf85_delta"), "WF84 section context must refresh after full-answer delta", errors)
    expect(names.index("canonical_finance_data_plane_post_wf85_delta") < names.index("canonical_finance_data_plane_phase6_10"), "final WF84 packet/DB must rebuild before phase 6-10", errors)
    expect(names.index("canonical_finance_data_plane_phase6_10") < names.index("full_intelligence_answer_parity_delta"), "WF84 phase proof must run before parity delta", errors)
    expect(names[-1] == "cache_dependency_manifest", f"cache dependency manifest should close the refresh chain, got {names[-1]}", errors)
    wf72_step = auto_band.POST_APPLY_REFRESH_STEPS[1]
    expect(wf72_step["args"][-1] == "--apply", f"WF72 refresh must use explicit apply flag: {wf72_step}", errors)
    go_step = auto_band.POST_APPLY_REFRESH_STEPS[4]
    expect(go_step.get("native_executable") is True, "Go parity step should use compiled validator explicitly", errors)
    full_answer_step = auto_band.POST_APPLY_REFRESH_STEPS[names.index("trade_grade_full_answer_assembler")]
    expect(full_answer_step.get("tickers_arg") == "--tickers", "full-answer refresh should use changed-ticker scope", errors)
    expect("tmp\\trade-grade-full-answer-assembler-delta.json" in full_answer_step["args"], "full-answer delta should not overwrite full rollup", errors)
    skipped = auto_band.run_post_apply_refresh([])
    expect(skipped["status"] == "skipped_no_applied_changes", f"no-change refresh should skip cleanly, got {skipped}", errors)


def main() -> int:
    errors: list[str] = []
    test_eligible_proposal_filter(errors)
    test_note_sync_updates_band_stop_and_authority_language(errors)
    test_table_sync_updates_current_execution_row_without_state_change(errors)
    test_table_only_row_is_safe_when_parser_section_missing(errors)
    test_missing_table_and_section_blocks(errors)
    test_manifest_runs_auto_apply_after_band_refresh(errors)
    test_post_apply_refresh_contract_is_serial_and_fail_closed(errors)
    if errors:
        print("auto_apply_entry_band_maintenance_tests_failed")
        for error in errors:
            print(f"- {error}")
        return 1
    print("auto_apply_entry_band_maintenance_tests_passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
