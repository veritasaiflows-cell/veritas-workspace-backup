from __future__ import annotations

import human_canon_thinning_retirement_inventory as inv


def test_inventory_has_required_categories_and_no_apply_authority() -> None:
    payload = inv.build_inventory()
    validation = inv.validate_inventory(payload)

    assert validation["status"] == "ok"
    assert set(payload["categories"]) == {"keep", "narrow_on_demand", "retire_candidate", "do_not_retire"}
    assert payload["summary"]["archive_or_delete_candidates_ready_now"] == 0
    assert payload["summary"]["cron_schedule_mutation_ready_now"] == 0
    assert payload["authority_boundary"]["archive_allowed"] is False
    assert payload["authority_boundary"]["delete_allowed"] is False
    assert payload["authority_boundary"]["cron_schedule_mutation_allowed"] is False
    assert payload["authority_boundary"]["sql_mutation_allowed"] is False
    assert payload["authority_boundary"]["canonical_note_mutation_allowed"] is False
    assert payload["authority_boundary"]["portfolio_mutation_allowed"] is False
    assert payload["authority_boundary"]["paper_or_live_execution_allowed"] is False


def test_inventory_classifies_expected_targets() -> None:
    payload = inv.build_inventory()
    categories = payload["categories"]

    keep_paths = {row["path"] for row in categories["keep"]}
    narrow_paths = {row["path"] for row in categories["narrow_on_demand"]}
    retire_paths = {row["path"] for row in categories["retire_candidate"]}
    do_not_retire_paths = {row["path"] for row in categories["do_not_retire"]}

    assert "scripts/finance_sql_markdown_field_ownership.py" in keep_paths
    assert "scripts/md_finance_structured_drift_lint.py" in keep_paths
    assert "scripts/ticker_answer_packet.py" in narrow_paths
    assert "go-finance-human-notes-sql-check" in narrow_paths
    assert "runtime_performance_scorecard.py:default_human_note_parity_commands" in retire_paths
    assert "03. Portfolio/Execution Board.md" in do_not_retire_paths
