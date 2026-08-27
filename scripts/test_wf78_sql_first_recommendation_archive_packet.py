from __future__ import annotations

import importlib.util
from pathlib import Path


SCRIPT = Path(__file__).with_name("wf78_sql_first_recommendation_archive_packet.py")
spec = importlib.util.spec_from_file_location("wf78_sql_first_recommendation_archive_packet", SCRIPT)
archive = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(archive)


def test_candidates_are_exact_and_move_only() -> None:
    assert archive.AUTHORITY_BOUNDARY["archive_move_only"] is True
    assert archive.AUTHORITY_BOUNDARY["delete_allowed"] is False
    assert archive.AUTHORITY_BOUNDARY["overwrite_allowed"] is False
    assert archive.SCRIPT_CANDIDATES == [
        "scripts/wf78_production_tier_adjudication.py",
        "scripts/wf78_tier_a_final_promotion_packet.py",
        "scripts/wf78_tier_b_final_promotion_packet.py",
    ]
    assert "tmp/wf78-tier-b-final-promotion-packet.production-bench.json" in archive.ARTIFACT_CANDIDATES


def test_apply_requires_approval_reference() -> None:
    payload = archive.build_payload(apply=True, approval_reference=None)
    assert payload["status"] == "blocked"
    assert "approval_reference_required_for_apply" in payload["validation"]["errors"]


def test_dry_run_does_not_execute_apply_without_reference() -> None:
    payload = archive.build_payload(apply=False, approval_reference=None)
    assert payload["summary"]["apply_executed"] is False
    assert payload["summary"]["delete_count"] == 0
    assert payload["summary"]["overwrite_count"] == 0


if __name__ == "__main__":
    test_candidates_are_exact_and_move_only()
    test_apply_requires_approval_reference()
    test_dry_run_does_not_execute_apply_without_reference()
    print("wf78_sql_first_recommendation_archive_packet_tests_passed")
