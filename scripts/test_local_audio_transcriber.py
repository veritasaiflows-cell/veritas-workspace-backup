#!/usr/bin/env python3
"""Focused tests for local_audio_transcriber path resolution and tooling guards."""
from __future__ import annotations

import importlib.util
import os
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "local_audio_transcriber.py"


def load_module():
    spec = importlib.util.spec_from_file_location("local_audio_transcriber", MODULE_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_resolve_latest_and_media_uri() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as raw:
        media_dir = Path(raw)
        first = media_dir / "first.ogg"
        second = media_dir / "second.ogg"
        first.write_bytes(b"old")
        os.utime(first, (time.time() - 10, time.time() - 10))
        second.write_bytes(b"new")
        os.utime(second, (time.time(), time.time()))

        resolved_latest = module.resolve_audio_path(None, media_dir=media_dir)
        assert resolved_latest == second

        resolved_uri = module.resolve_audio_path("media://inbound/first.ogg", media_dir=media_dir)
        assert resolved_uri == first


def test_dependency_guard_reports_missing_without_bootstrap() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as raw:
        result = module.bootstrap_tools(allow=False, tools_dir=Path(raw) / "tools")
        assert result["status"] == "missing"
        assert "npm install" in result["install_command"]


def main() -> int:
    test_resolve_latest_and_media_uri()
    test_dependency_guard_reports_missing_without_bootstrap()
    print("local_audio_transcriber_tests_passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
