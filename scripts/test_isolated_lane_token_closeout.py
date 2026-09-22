"""Tests for scripts/isolated_lane_token_closeout.py (new file only).

Fixture shape follows excerpt_existing_import_test.py: real temp dirs, no
weakening of existing manager credit rules (the manager is stubbed, never
edited). Run: python -m pytest scripts/test_isolated_lane_token_closeout.py -q
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import isolated_lane_token_closeout as wrapper


def _proof_path(base: Path) -> Path:
    return base / "tmp" / "isolated-lane-token-closeout.json"


def _base_args(proof: Path) -> list[str]:
    return [
        "--complete", "WF99",
        "--workstream", "closeout-test",
        "--session-id", "session-closeout-1",
        "--session-key", "agent:implementation-builder:main",
        "--agent-id", "implementation-builder",
        "--write", "--validate",
        "--proof-path", str(proof),
    ]


def _flatten_keys(obj: object) -> list[str]:
    if isinstance(obj, dict):
        keys = list(obj.keys())
        for value in obj.values():
            keys.extend(_flatten_keys(value))
        return keys
    if isinstance(obj, list):
        keys: list[str] = []
        for item in obj:
            keys.extend(_flatten_keys(item))
        return keys
    return []


def test_missing_session_identifiers_fail_closed() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        proof = _proof_path(Path(tmpdir))
        calls: list[list[str]] = []
        wrapper.run_manager = lambda cmd: calls.append(cmd) or 0  # type: ignore[method-assign]
        try:
            rc = wrapper.main([
                "--complete", "WF99",
                "--workstream", "closeout-test",
                "--agent-id", "implementation-builder",
                "--write", "--validate",
                "--proof-path", str(proof),
            ])
        finally:
            del wrapper.run_manager  # type: ignore[attr-defined]
        assert rc != 0
        assert calls == [], "manager must not run without session identifiers"
        payload = json.loads(proof.read_text(encoding="utf-8"))
        assert payload["status"] == "failed_closed"
        assert payload["manager_returncode"] is None


def test_wrapper_passes_import_and_binding_flags() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        proof = _proof_path(Path(tmpdir))
        seen: list[list[str]] = []
        wrapper.run_manager = lambda cmd: seen.append(list(cmd)) or 0  # type: ignore[method-assign]
        try:
            rc = wrapper.main(_base_args(proof))
        finally:
            del wrapper.run_manager  # type: ignore[attr-defined]
        assert rc == 0
        assert len(seen) == 1
        cmd = seen[0]
        assert "--import-isolated-session-usage" in cmd
        assert "--require-dispatch-binding" in cmd
        assert "--session-id" in cmd and "session-closeout-1" in cmd
        assert "--session-key" in cmd
        assert "--agent-id" in cmd and "implementation-builder" in cmd
        assert "--isolated-agent-state-root" not in cmd
        payload = json.loads(proof.read_text(encoding="utf-8"))
        assert payload["status"] == "complete"
        assert payload["lane_id"] == "WF99::closeout-test"
        assert payload["flags"]["import_isolated_session_usage"] is True
        assert payload["flags"]["require_dispatch_binding"] is True
        assert payload["manager_returncode"] == 0


def test_manager_nonzero_fails_closed() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        proof = _proof_path(Path(tmpdir))
        wrapper.run_manager = lambda cmd: 3  # type: ignore[method-assign]
        try:
            rc = wrapper.main(_base_args(proof))
        finally:
            del wrapper.run_manager  # type: ignore[attr-defined]
        assert rc == 3
        payload = json.loads(proof.read_text(encoding="utf-8"))
        assert payload["status"] == "failed_closed"
        assert payload["manager_returncode"] == 3


def test_proof_has_no_raw_session_fields() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        proof = _proof_path(Path(tmpdir))
        wrapper.run_manager = lambda cmd: 0  # type: ignore[method-assign]
        try:
            rc = wrapper.main(_base_args(proof))
        finally:
            del wrapper.run_manager  # type: ignore[attr-defined]
        assert rc == 0
        payload = json.loads(proof.read_text(encoding="utf-8"))
        lowered = {key.lower().replace("-", "_") for key in _flatten_keys(payload)}
        assert not (lowered & {key.lower() for key in wrapper.FORBIDDEN_PROOF_KEYS})
        for banned in ("sessionfile", "authprofile", "sessionFile", "authProfile"):
            assert banned not in proof.read_text(encoding="utf-8")
        # Raw identifiers themselves are never persisted, only presence booleans.
        assert "session-closeout-1" not in proof.read_text(encoding="utf-8")
