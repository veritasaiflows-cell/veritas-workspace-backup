from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def run_script(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, *args], cwd=ROOT, text=True, capture_output=True)


def test_legacy_anchor_dry_run_defaults_fail_closed() -> None:
    result = run_script("scripts/reference_levels_derived_refresh_dry_run.py", "--write", "--validate")

    assert result.returncode == 1
    assert "blocked_legacy_anchor_compat_flag_required" in result.stdout


def test_legacy_anchor_expected_parity_defaults_fail_closed() -> None:
    result = run_script("scripts/reference_levels_expected_parity_validator.py", "--write", "--validate")

    assert result.returncode == 1
    assert "blocked_legacy_anchor_compat_flag_required" in result.stdout
