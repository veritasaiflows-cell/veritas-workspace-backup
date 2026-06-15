#!/usr/bin/env python3
"""Regression checks for compact_exec."""
from __future__ import annotations

import importlib.util
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "compact_exec.py"


def load_module():
    spec = importlib.util.spec_from_file_location("compact_exec", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


def main() -> int:
    m = load_module()
    with tempfile.TemporaryDirectory() as tmp:
        cwd = Path(tmp)
        report = m.run_command([sys.executable, "-c", "print('X' * 12000)"], "fixture", cwd)
    assert report["ok"] is True
    assert report["stdout"]["chars"] >= 12000
    assert report["stderr"]["chars"] == 0
    assert report["stdout"]["path"].endswith(".stdout.txt")
    assert report["report_path"].endswith(".json")
    assert "config/auth/runtime" in report["authority_boundary"]
    print("compact_exec_tests_passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
