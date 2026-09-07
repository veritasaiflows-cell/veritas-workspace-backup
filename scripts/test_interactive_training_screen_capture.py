#!/usr/bin/env python3
"""Focused tests for interactive_training_screen_capture.py (no GUI)."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import interactive_training_screen_capture as capture


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def test_write_validate_temp_dir() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        recordings = Path(tmp) / "recordings"
        recordings.mkdir()
        (recordings / "walkthrough-01.webm").write_bytes(b"fake-clip-bytes")
        proof_path = Path(tmp) / "proof.json"
        proof = capture.build(write=True, recordings_dir=recordings, proof_path=proof_path)
        assert_true(proof["status"] == "ok", f"expected ok proof, got {proof}")
        assert_true(proof["counts"]["clips"] == 1, "expected one inventoried clip")
        assert_true(proof["clips"][0]["file"] == "recordings/walkthrough-01.webm", "clip file path wrong")
        assert_true(proof["authority_boundary"]["external_upload_allowed"] is False, "upload must be false")
        assert_true(proof["authority_boundary"]["lms_configured"] is False, "lms must be false")
        assert_true((recordings / "manifest.json").exists(), "manifest not written")
        assert_true((recordings / "README.md").exists(), "recordings README not written")
        assert_true(proof_path.exists(), "proof not written")
        manifest = json.loads((recordings / "manifest.json").read_text(encoding="utf-8"))
        assert_true(len(manifest["clips"]) == 1, "manifest clip missing")


def test_empty_dir_is_ok_with_placeholder() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        recordings = Path(tmp) / "recordings"
        proof = capture.build(write=True, recordings_dir=recordings, proof_path=Path(tmp) / "proof.json")
        assert_true(proof["status"] == "ok", f"empty dir should be ok, got {proof}")
        assert_true(proof["counts"]["clips"] == 0, "expected zero clips")
        readme = (recordings / "README.md").read_text(encoding="utf-8")
        assert_true("Snipping Tool" in readme, "README should name Snipping Tool")


def test_http_path_rejected() -> None:
    assert_true(capture.is_safe_clip_name("https://example.com/clip.mp4") is False, "http URL must be rejected")
    assert_true(capture.is_safe_clip_name("recordings/clip.mp4") is False, "nested path must be rejected")
    assert_true(capture.is_safe_clip_name("../clip.mp4") is False, "traversal must be rejected")
    assert_true(capture.is_safe_clip_name("clip.mp4") is True, "plain clip name should pass")
    assert_true(capture.is_safe_clip_name("walkthrough-01.webm") is True, "webm name should pass")


def test_no_gui_in_validate_path() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        recordings = Path(tmp) / "recordings"
        recordings.mkdir()
        proof = capture.build(write=False, recordings_dir=recordings, proof_path=Path(tmp) / "proof.json")
        assert_true(proof["status"] == "ok", f"validate-only should pass without GUI, got {proof}")


def main() -> int:
    tests = [
        test_write_validate_temp_dir,
        test_empty_dir_is_ok_with_placeholder,
        test_http_path_rejected,
        test_no_gui_in_validate_path,
    ]
    for test in tests:
        test()
    print(json.dumps({"status": "ok", "tests": len(tests)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
