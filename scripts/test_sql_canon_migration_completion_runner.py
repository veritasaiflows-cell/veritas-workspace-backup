from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "sql_canon_migration_completion_runner.py"

spec = importlib.util.spec_from_file_location("sql_canon_migration_completion_runner", SCRIPT)
assert spec and spec.loader
runner = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = runner
spec.loader.exec_module(runner)


def test_completion_runner_preserves_hard_boundaries() -> None:
    packet = runner.build_packet(skip_refresh=True)
    errors = runner.validate_packet(packet)
    assert not errors
    boundary = packet["authority_boundary"]
    assert boundary["review_only"] is True
    assert boundary["proof_bundle_only"] is True
    assert boundary["consumer_files_modified"] is False
    assert boundary["sql_writes_performed"] is False
    assert boundary["db_row_mutation_performed"] is False
    assert boundary["schema_mutation_performed"] is False
    assert boundary["archive_moves_performed"] is False
    assert boundary["delete_performed"] is False
    assert boundary["cron_schedule_mutation_performed"] is False
    assert boundary["source_feeder_retirement_allowed"] is False
    assert boundary["python_fallback_retirement_allowed"] is False
    assert boundary["answer_path_sql_first_promotion_allowed"] is False
    assert boundary["duplicate_surface_cleanup_apply_allowed"] is False
    assert boundary["portfolio_or_canon_mutation_allowed"] is False
    assert boundary["capital_deployment_allowed"] is False
    assert boundary["paper_or_live_execution_allowed"] is False
    assert boundary["brokerage_or_account_action_allowed"] is False
    assert boundary["money_movement_allowed"] is False
    assert boundary["owner_approval_inferred"] is False


def test_completion_runner_does_not_regenerate_archived_legacy_packets() -> None:
    command_args = {
        arg
        for spec in runner.COMMANDS
        if spec.name == "full_answer_assembler"
        for arg in spec.args
    }
    assert "--write" in command_args
    assert "--validate" in command_args
    assert "--write-legacy-packets" not in command_args


def test_completion_tracks_match_current_sql_canon_posture() -> None:
    packet = runner.build_packet(skip_refresh=True)
    tracks = packet["tracks"]
    live = tracks["live_state"]
    track_a = tracks["track_a_consumer_classification_and_typed_access"]
    track_b = tracks["track_b_source_producer_partition_and_burndown"]
    track_c = tracks["track_c_answer_path_owner_packet_and_closeout"]

    assert packet["status"] == "ok"
    assert packet["validation"]["status"] == "ok"
    assert live["raw_sql_review_count"] == 0
    assert live["hard_gate_actions_allowed"] == []
    assert track_a["code_patch_required_now"] is False
    assert track_a["status"] == "complete"
    assert track_b["source_feeder_retirement_ready_count"] == 0
    assert track_b["duplicate_surface_retirement_ready_count"] == 0
    assert track_b["consumer_cutover_allowed"] is False
    assert track_c["sql_first_promotion_allowed_now"] is False
    assert track_c["hard_gate_actions_allowed"] == []


if __name__ == "__main__":
    test_completion_runner_preserves_hard_boundaries()
    test_completion_tracks_match_current_sql_canon_posture()
