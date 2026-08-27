from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "ticker_answer_packet_versioned_archive_packet.py"

spec = importlib.util.spec_from_file_location("ticker_answer_packet_versioned_archive_packet", SCRIPT)
assert spec and spec.loader
packet_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(packet_module)


def test_versioned_archive_packet_names_all_candidates_without_apply() -> None:
    packet = packet_module.build_packet(archive_label="legacy-42-regenerated-20260620")
    assert packet["status"] in {
        "versioned_archive_owner_review_ready_apply_blocked",
        "versioned_archive_completed",
    }
    assert packet["authority_boundary"]["archive_allowed_now"] is False
    assert packet["authority_boundary"]["delete_allowed_now"] is False
    assert packet["authority_boundary"]["move_allowed_now"] is False
    assert packet["authority_boundary"]["overwrite_allowed_now"] is False
    assert packet["authority_boundary"]["apply_allowed_now"] is False
    assert packet["summary"]["candidate_count"] == 42
    if packet["status"] == "versioned_archive_completed":
        assert packet["summary"]["source_exists_count"] == 0
        assert packet["summary"]["source_hash_count"] == 0
        assert packet["summary"]["versioned_destination_existing_count"] == 42
        assert packet["summary"]["move_count_after_approval"] == 0
        assert packet["approval_required"]["owner_exact_approval_required"] is False
    else:
        assert packet["summary"]["source_exists_count"] == 42
        assert packet["summary"]["source_hash_count"] == 42
        assert packet["summary"]["versioned_destination_clear_count"] == 42
        assert packet["summary"]["move_count_after_approval"] == 42
        assert packet["approval_required"]["owner_exact_approval_required"] is True
    assert packet["summary"]["delete_count_after_approval"] == 0
    assert packet["summary"]["overwrite_count_after_approval"] == 0
    assert packet["summary"]["apply_performed"] is False
    assert packet["validation"]["status"] == "ok"
    assert "legacy-42-regenerated-20260620" in packet["future_apply_command_after_exact_approval"]


def test_versioned_archive_packet_sanitizes_archive_label() -> None:
    packet = packet_module.build_packet(archive_label="../bad label")
    assert ".." not in packet["archive_label"]
    assert "/" not in packet["archive_label"]
    assert packet["proposed_versioned_archive_root"].startswith(
        "09. Archive/WF85 Legacy Ticker Answer Packets/versioned/"
    )


if __name__ == "__main__":
    test_versioned_archive_packet_names_all_candidates_without_apply()
    test_versioned_archive_packet_sanitizes_archive_label()
