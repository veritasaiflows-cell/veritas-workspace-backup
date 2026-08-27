#!/usr/bin/env python3
"""Regression checks for compact_exec."""
from __future__ import annotations

import importlib.util
import sys
import tempfile
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "compact_exec.py"


def load_module():
    spec = importlib.util.spec_from_file_location("compact_exec", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


def assert_rejected(m, cwd, message: str, test_tmp: Path, label: str) -> None:
    """Prove invalid CWDs fail before subprocess execution or log creation."""
    blocked_out_dir = test_tmp / f"{label}-logs"
    assert not blocked_out_dir.exists()
    m.OUT_DIR = blocked_out_dir
    with mock.patch.object(
        m.subprocess,
        "run",
        side_effect=AssertionError("subprocess must not run for a rejected cwd"),
    ) as run_mock:
        try:
            m.run_command([sys.executable, "-c", "pass"], label, cwd)
        except ValueError as exc:
            assert message in str(exc)
        else:
            raise AssertionError(f"expected cwd rejection for {cwd}")
        run_mock.assert_not_called()
    assert not blocked_out_dir.exists()


def main() -> int:
    m = load_module()
    tmp_root = ROOT / "tmp"
    tmp_root.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(dir=tmp_root) as tmp:
        test_tmp = Path(tmp)
        m.OUT_DIR = test_tmp / "compact-exec-logs"
        report = m.run_command([sys.executable, "-c", "print('X' * 12000)"], "fixture", ROOT)
        assert report["ok"] is True
        assert report["stdout"]["chars"] >= 12000
        assert report["stderr"]["chars"] == 0
        assert report["stdout"]["path"].endswith(".stdout.txt")
        assert report["report_path"].endswith(".json")
        assert "config/auth/runtime" in report["authority_boundary"]

        child = test_tmp / "child"
        child.mkdir()
        assert m.run_command([sys.executable, "-c", "pass"], "child", child)["ok"] is True

        assert_rejected(m, test_tmp / "missing", "does not exist", test_tmp, "missing")

        outside = ROOT.resolve().parent
        assert_rejected(m, outside, "outside workspace root", test_tmp, "outside")

        file_cwd = test_tmp / "not-a-directory"
        file_cwd.write_text("fixture\n", encoding="utf-8")
        assert_rejected(m, file_cwd, "not a directory", test_tmp, "file-cwd")

        escape_link = test_tmp / "outside-link"
        try:
            escape_link.symlink_to(outside, target_is_directory=True)
        except OSError:
            # A privilege-independent fallback exercises the same resolved-path
            # containment decision used for Windows junctions and symlinks.
            class ResolvedLinkEscape:
                def resolve(self, *, strict: bool = False) -> Path:
                    assert strict is True
                    return outside

            escape_cwd = ResolvedLinkEscape()
        else:
            escape_cwd = escape_link
        assert_rejected(
            m,
            escape_cwd,
            "outside workspace root",
            test_tmp,
            "link-escape",
        )
    print("compact_exec_tests_passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
