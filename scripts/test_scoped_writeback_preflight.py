from __future__ import annotations

import datetime
import hashlib
import json

import scoped_writeback_preflight as preflight


UTC = datetime.timezone.utc


def test_v1_matches_agent_projection_fingerprint(tmp_path):
    config = tmp_path / "openclaw.json"
    config.write_text("{}", encoding="utf-8")
    proof = {
        "schema": "veritas.persistent_transport_proof.v1",
        "evidence": {"config_fingerprint": {"sha256": "a" * 64}},
    }
    assert preflight.proof_config_matches(
        proof, live_entry_fingerprint="a" * 64, config_path=config
    )
    assert not preflight.proof_config_matches(
        proof, live_entry_fingerprint="b" * 64, config_path=config
    )


def test_v3_matches_exact_config_bytes_and_rejects_drift(tmp_path):
    config = tmp_path / "openclaw.json"
    payload = {"agents": {"entries": {"implementation-builder": {}}}}
    config.write_text(json.dumps(payload), encoding="utf-8")
    digest = hashlib.sha256(config.read_bytes()).hexdigest()
    proof = {
        "schema": "veritas.persistent_transport_proof.v3",
        "runtime": {"config_sha256": digest},
    }
    assert preflight.proof_config_matches(
        proof, live_entry_fingerprint="unused", config_path=config
    )
    config.write_text(json.dumps({"drift": True}), encoding="utf-8")
    assert not preflight.proof_config_matches(
        proof, live_entry_fingerprint="unused", config_path=config
    )


def test_v3_requires_unexpired_recent_proof():
    now = datetime.datetime(2026, 9, 27, 2, 0, tzinfo=UTC)
    proof = {
        "schema": "veritas.persistent_transport_proof.v3",
        "observed_at_utc": "2026-09-27T01:00:00Z",
        "expires_at_utc": "2026-09-27T03:00:00Z",
    }
    assert preflight.proof_time_is_valid(proof, now=now)
    proof["expires_at_utc"] = "2026-09-27T01:30:00Z"
    assert not preflight.proof_time_is_valid(proof, now=now)


def test_v1_keeps_seven_day_window_without_expiry():
    now = datetime.datetime(2026, 9, 27, 2, 0, tzinfo=UTC)
    proof = {
        "schema": "veritas.persistent_transport_proof.v1",
        "observed_at_utc": "2026-09-26T02:00:00Z",
    }
    assert preflight.proof_time_is_valid(proof, now=now)
    proof["observed_at_utc"] = "2026-09-19T01:59:59Z"
    assert not preflight.proof_time_is_valid(proof, now=now)
