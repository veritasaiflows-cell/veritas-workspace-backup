#!/usr/bin/env python3
"""Targeted tests for cron control digest runner routing."""
from __future__ import annotations

from pathlib import Path
import json
import tempfile
from datetime import datetime, timedelta, timezone

import cron_control_digest_runner as runner


def test_default_output_path_tracks_window() -> None:
    assert runner.output_path_for_window("control", None) == Path("tmp/cron-control-digest-runner-control.json")
    assert runner.output_path_for_window("morning", None) == Path("tmp/cron-control-digest-runner-morning.json")
    assert runner.output_path_for_window("post-close", None) == Path("tmp/cron-control-digest-runner-post-close.json")
    assert runner.output_path_for_window("all", None) == Path("tmp/cron-control-digest-runner.json")


def test_explicit_output_path_wins() -> None:
    requested = Path("tmp/custom-runner.json")
    assert runner.output_path_for_window("control", requested) == requested


def test_prefilter_reuses_fresh_ok_packet() -> None:
    now = datetime.now(timezone.utc).replace(microsecond=0)
    signature = {"hash": "abc123", "source_count": 1, "sources": []}
    with tempfile.TemporaryDirectory() as tmpdir:
        out = Path(tmpdir) / "control.json"
        out.write_text(
            json.dumps(
                {
                    "generated_at_utc": now.isoformat().replace("+00:00", "Z"),
                    "status": "ok",
                    "validation": {"status": "ok"},
                    "input_signature": signature,
                }
            ),
            encoding="utf-8",
        )

        decision = runner.prefilter_decision(out, signature, now=now)

    assert decision["can_reuse_existing_packet"] is True
    assert decision["reason"] == "unchanged_inputs_and_fresh_control_digest"


def test_reuse_does_not_renew_persisted_evidence_timestamp() -> None:
    now = datetime.now(timezone.utc).replace(microsecond=0)
    evidence_time = now - timedelta(minutes=5)
    evidence_time_text = evidence_time.isoformat().replace("+00:00", "Z")
    signature = {"hash": "abc123", "source_count": 1, "sources": []}
    with tempfile.TemporaryDirectory() as tmpdir:
        out = Path(tmpdir) / "control.json"
        out.write_text(
            json.dumps(
                {
                    "generated_at_utc": evidence_time_text,
                    "runner": "cron_control_digest_runner",
                    "status": "ok",
                    "validation": {"status": "ok"},
                    "input_signature": signature,
                },
                sort_keys=True,
            ),
            encoding="utf-8",
        )
        before = out.read_bytes()
        decision = runner.prefilter_decision(out, signature, now=now)
        payload = runner.reuse_existing_payload(out, decision)

        assert out.read_bytes() == before
        assert payload["generated_at_utc"] == evidence_time_text
        assert payload["runtime_reuse_check"]["persisted_packet_rewritten"] is False
        assert payload["runtime_reuse_check"]["evidence_generated_at_utc"] == evidence_time_text


def test_prefilter_ttl_is_shorter_than_scheduled_control_gap() -> None:
    now = datetime.now(timezone.utc).replace(microsecond=0)
    signature = {"hash": "abc123", "source_count": 1, "sources": []}
    with tempfile.TemporaryDirectory() as tmpdir:
        out = Path(tmpdir) / "control.json"
        out.write_text(
            json.dumps(
                {
                    "generated_at_utc": (now - timedelta(hours=1)).isoformat().replace("+00:00", "Z"),
                    "status": "ok",
                    "validation": {"status": "ok"},
                    "input_signature": signature,
                }
            ),
            encoding="utf-8",
        )
        decision = runner.prefilter_decision(out, signature, now=now)

    assert runner.PREFILTER_MAX_AGE_HOURS < 7
    assert decision["can_reuse_existing_packet"] is False
    assert decision["reason"] == "previous_packet_not_fresh"


def test_prefilter_refreshes_stale_or_blocked_packet() -> None:
    now = datetime.now(timezone.utc).replace(microsecond=0)
    stale = now - timedelta(hours=runner.PREFILTER_MAX_AGE_HOURS + 1)
    signature = {"hash": "abc123", "source_count": 1, "sources": []}
    with tempfile.TemporaryDirectory() as tmpdir:
        out = Path(tmpdir) / "control.json"
        out.write_text(
            json.dumps(
                {
                    "generated_at_utc": stale.isoformat().replace("+00:00", "Z"),
                    "status": "ok",
                    "validation": {"status": "ok"},
                    "input_signature": signature,
                }
            ),
            encoding="utf-8",
        )
        stale_decision = runner.prefilter_decision(out, signature, now=now)

        out.write_text(
            json.dumps(
                {
                    "generated_at_utc": now.isoformat().replace("+00:00", "Z"),
                    "status": "blocked",
                    "validation": {"status": "blocked"},
                    "input_signature": signature,
                }
            ),
            encoding="utf-8",
        )
        blocked_decision = runner.prefilter_decision(out, signature, now=now)

    assert stale_decision["can_reuse_existing_packet"] is False
    assert stale_decision["reason"] == "previous_packet_not_fresh"
    assert blocked_decision["can_reuse_existing_packet"] is False
    assert blocked_decision["reason"] == "previous_packet_not_ok"


def test_window_digest_artifacts_allow_classified_critical_blockers() -> None:
    morning_artifacts = {artifact["name"]: artifact for artifact in runner.artifact_plan("morning")}
    post_close_artifacts = {artifact["name"]: artifact for artifact in runner.artifact_plan("post-close")}

    assert "critical" in morning_artifacts["morning_control_digest"]["allowed_statuses"]
    assert "critical" in post_close_artifacts["post_close_control_digest"]["allowed_statuses"]


def test_contract_validator_warning_does_not_block_control_digest() -> None:
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "contract-validator.json"
        path.write_text(
            json.dumps(
                {
                    "generated_at_utc": now,
                    "status": "warning",
                    "validation": {"warnings": ["cron_prompt_bloat_present"]},
                }
            ),
            encoding="utf-8",
        )
        record = runner.contract_validator_artifact_record(path)

    assert record["ok"] is True
    assert record["accepted_warning_codes"] == ["cron_prompt_bloat_present"]


def test_contract_validator_unaccepted_warning_blocks_control_digest() -> None:
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "contract-validator.json"
        path.write_text(
            json.dumps(
                {
                    "generated_at_utc": now,
                    "status": "warning",
                    "validation": {"warnings": ["invalid_contract_json:broken.json"]},
                }
            ),
            encoding="utf-8",
        )
        record = runner.contract_validator_artifact_record(path)

    assert record["ok"] is False
    assert record["unaccepted_warning_codes"] == ["invalid_contract_json:broken.json"]


def main() -> int:
    test_default_output_path_tracks_window()
    test_explicit_output_path_wins()
    test_prefilter_reuses_fresh_ok_packet()
    test_reuse_does_not_renew_persisted_evidence_timestamp()
    test_prefilter_ttl_is_shorter_than_scheduled_control_gap()
    test_prefilter_refreshes_stale_or_blocked_packet()
    test_window_digest_artifacts_allow_classified_critical_blockers()
    test_contract_validator_warning_does_not_block_control_digest()
    test_contract_validator_unaccepted_warning_blocks_control_digest()
    print("cron_control_digest_runner targeted tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
