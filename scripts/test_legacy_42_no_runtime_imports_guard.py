from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "legacy_42_no_runtime_imports_guard.py"

spec = importlib.util.spec_from_file_location("legacy_42_no_runtime_imports_guard", SCRIPT)
assert spec and spec.loader
guard_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(guard_module)


def test_classifies_active_runtime_import_as_blocker() -> None:
    path = ROOT / "scripts" / "ticker_answer_packet.py"
    classification, rationale, matched = guard_module.classify_script(
        path,
        "from wf78_legacy_42_tier_state import production_tickers\n",
    )
    assert classification == "active_runtime_import_blocker"
    assert "Legacy 42 tier-state helper" in rationale
    assert matched == ["legacy_tier_state_import"]


def test_classifies_governance_script_as_allowed_reference() -> None:
    path = ROOT / "scripts" / "legacy_42_lifecycle_gate_packet.py"
    classification, _, matched = guard_module.classify_script(
        path,
        '"python scripts\\\\wf78_legacy_42_tier_migration_planner.py --write --validate"\n',
    )
    assert classification == "archive_governance_or_test_reference"
    assert "legacy_migration_planner_runtime_call" in matched


def test_classifies_archive_relocation_map_as_allowed_reference() -> None:
    path = ROOT / "scripts" / "concurrent_lane_manager.py"
    classification, _, matched = guard_module.classify_script(
        path,
        '"scripts/wf78_legacy_42_tier_migration_planner.py": "09. Archive/..."\n',
    )
    assert classification == "archive_governance_or_test_reference"
    assert "legacy_migration_planner_runtime_call" in matched


def test_classifies_production_scope_retirement_plan_as_governance_reference() -> None:
    path = ROOT / "scripts" / "production_scope_schema_retirement_plan.py"
    classification, _, matched = guard_module.classify_script(
        path,
        "legacy_production_42 = 1\nuniverse_scope = 'production_current_42'\n",
    )
    assert classification == "archive_governance_or_test_reference"
    assert matched == ["legacy_production_42_field", "production_current_42_label"]


def test_guard_preserves_archive_and_finance_boundaries() -> None:
    packet = guard_module.build_packet()
    errors = guard_module.validate_packet(packet)
    assert not errors
    boundary = packet["authority_boundary"]
    assert boundary["review_only"] is True
    assert boundary["archive_prep_only"] is True
    assert boundary["archive_allowed_now"] is False
    assert boundary["delete_allowed_now"] is False
    assert boundary["move_allowed_now"] is False
    assert boundary["apply_allowed_now"] is False
    assert boundary["sql_write_allowed"] is False
    assert boundary["portfolio_or_canon_mutation_allowed"] is False
    assert boundary["capital_deployment_allowed"] is False
    assert boundary["paper_or_live_execution_allowed"] is False
    assert boundary["brokerage_or_account_action_allowed"] is False
    assert boundary["owner_approval_inferred"] is False


if __name__ == "__main__":
    test_classifies_active_runtime_import_as_blocker()
    test_classifies_governance_script_as_allowed_reference()
    test_classifies_archive_relocation_map_as_allowed_reference()
    test_classifies_production_scope_retirement_plan_as_governance_reference()
    test_guard_preserves_archive_and_finance_boundaries()
