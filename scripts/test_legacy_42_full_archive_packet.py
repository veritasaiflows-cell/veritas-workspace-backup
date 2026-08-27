from __future__ import annotations

import importlib.util
from pathlib import Path


MODULE_PATH = Path(__file__).with_name("legacy_42_full_archive_packet.py")
spec = importlib.util.spec_from_file_location("legacy_42_full_archive_packet", MODULE_PATH)
module = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(module)


def test_archive_candidates_are_exact_and_move_only() -> None:
    assert module.SCRIPT_CANDIDATES == [
        "scripts/wf78_legacy_42_tier_migration_planner.py",
        "scripts/wf78_legacy_42_archive_readiness_packet.py",
        "scripts/wf78_legacy_42_tier_state.py",
        "scripts/legacy_42_lifecycle_gate_packet.py",
        "scripts/test_legacy_42_lifecycle_gate_packet.py",
    ]
    assert len(module.ARTIFACT_CANDIDATES) == 4
    boundary = module.AUTHORITY_BOUNDARY
    assert boundary["archive_move_only"] is True
    assert boundary["delete_allowed"] is False
    assert boundary["overwrite_allowed"] is False
    assert boundary["sql_schema_mutation_allowed"] is False
    assert boundary["paper_or_live_execution_allowed"] is False


def test_archive_destination_stays_under_archive_root() -> None:
    dest = module.archive_destination("scripts/wf78_legacy_42_tier_state.py")
    assert module.ARCHIVE_ROOT.resolve() in dest.resolve().parents
    assert dest.as_posix().endswith("scripts/wf78_legacy_42_tier_state.py")


def test_preview_packet_is_fail_closed() -> None:
    packet = module.build_packet(apply=False)
    assert packet["apply"] is False
    assert packet["summary"]["delete_count"] == 0
    assert packet["summary"]["overwrite_count"] == 0
    assert packet["authority_boundary"]["owner_approval_inferred"] is False
    assert "post_archive_validation_plan" in packet
