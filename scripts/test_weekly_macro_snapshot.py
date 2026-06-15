from __future__ import annotations

from weekly_macro_snapshot import validate_snapshot_markdown


BASE_MD = """# Weekly Macro Snapshot — 2026-W20

**Authority:** Review-only. No trade, sizing, account, or execution authority.

## 1) Macro Regime Assessment

- Complete.
"""


CLEAN_VALIDATION = {
    "overall": "warning",
    "summary": {"critical": 0, "warning": 1, "info": 0},
    "source_freshness": {
        "presentation_allowed": True,
        "stop_line": False,
        "capital_action_allowed": False,
    },
}


def test_placeholders_block_completion() -> None:
    md = BASE_MD + "\n**Posture call (judgment):** _[Offensive / Defensive-neutral / Defensive — state basis]_.\n"
    result = validate_snapshot_markdown(md, CLEAN_VALIDATION)
    assert result["complete"] is False
    assert result["macro_canonical_write_allowed"] is False
    assert result["placeholder_count"] == 1
    assert any("placeholder" in blocker for blocker in result["blockers"])


def test_dashboard_warning_does_not_block_macro_completion() -> None:
    result = validate_snapshot_markdown(BASE_MD, CLEAN_VALIDATION)
    assert result["complete"] is True
    assert result["macro_canonical_write_allowed"] is True
    assert result["warnings"]


def test_presentation_stop_line_blocks_completion() -> None:
    validation = {
        **CLEAN_VALIDATION,
        "source_freshness": {
            **CLEAN_VALIDATION["source_freshness"],
            "stop_line": True,
        },
    }
    result = validate_snapshot_markdown(BASE_MD, validation)
    assert result["complete"] is False
    assert any("stop-line" in blocker for blocker in result["blockers"])


def test_missing_authority_blocks_completion() -> None:
    result = validate_snapshot_markdown("# Weekly Macro Snapshot\n\nNo placeholders here.\n", CLEAN_VALIDATION)
    assert result["complete"] is False
    assert any("authority" in blocker for blocker in result["blockers"])


def test_broader_placeholder_terms_block_completion() -> None:
    result = validate_snapshot_markdown(BASE_MD + "\nTBD macro judgment.\n", CLEAN_VALIDATION)
    assert result["complete"] is False
    assert result["placeholder_count"] == 1


def test_deployment_surface_presentation_false_warns_when_no_stop_line() -> None:
    deployment_surface = {"system": {"stop_line": False, "presentation_allowed": False}}
    result = validate_snapshot_markdown(BASE_MD, CLEAN_VALIDATION, deployment_surface=deployment_surface)
    assert result["complete"] is True
    assert result["macro_canonical_write_allowed"] is True
    assert any("deployment surface presentation_allowed=false" in warning for warning in result["warnings"])


def test_deployment_surface_stop_line_blocks_completion() -> None:
    deployment_surface = {"system": {"stop_line": True, "presentation_allowed": False}}
    result = validate_snapshot_markdown(BASE_MD, CLEAN_VALIDATION, deployment_surface=deployment_surface)
    assert result["complete"] is False
    assert any("deployment surface stop-line" in blocker for blocker in result["blockers"])


def test_capital_action_allowed_blocks_completion() -> None:
    validation = {
        **CLEAN_VALIDATION,
        "source_freshness": {
            **CLEAN_VALIDATION["source_freshness"],
            "capital_action_allowed": True,
        },
    }
    result = validate_snapshot_markdown(BASE_MD, validation)
    assert result["complete"] is False
    assert any("capital_action_allowed" in blocker for blocker in result["blockers"])


def test_authority_fields_remain_false_for_macro_note() -> None:
    result = validate_snapshot_markdown(BASE_MD, CLEAN_VALIDATION)
    authority = result["authority"]
    assert authority["canonical_mutation_allowed"] is False
    assert authority["generated_macro_note_write_allowed"] is True
    assert authority["portfolio_mutation_allowed"] is False
    assert authority["trade_execution_allowed"] is False
    assert authority["owner_approval_granted"] is False


if __name__ == "__main__":
    test_placeholders_block_completion()
    test_dashboard_warning_does_not_block_macro_completion()
    test_presentation_stop_line_blocks_completion()
    test_missing_authority_blocks_completion()
    test_broader_placeholder_terms_block_completion()
    test_deployment_surface_presentation_false_warns_when_no_stop_line()
    test_deployment_surface_stop_line_blocks_completion()
    test_capital_action_allowed_blocks_completion()
    test_authority_fields_remain_false_for_macro_note()
    print("ok")
