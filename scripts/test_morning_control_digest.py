#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "morning_control_digest.py"


def load_module():
    spec = importlib.util.spec_from_file_location("morning_control_digest", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_non_morning_warning_windows_do_not_block_morning_digest() -> None:
    module = load_module()
    payload = {
        "status": "warning",
        "operator_attention": {
            "stop_line_windows": [],
            "blocked_windows": [],
            "warning_windows": ["post-earnings", "sunday"],
        },
        "run_summaries": [
            {"window": "morning", "status": "ok", "stop_line": False, "warnings": []},
            {"window": "post-earnings", "status": "warning", "stop_line": False, "warnings": ["review-only warning"]},
        ],
    }
    assert module.cron_ledger_warning_is_expected(payload) is True


def test_morning_warning_still_requires_expected_warning() -> None:
    module = load_module()
    payload = {
        "status": "warning",
        "operator_attention": {
            "stop_line_windows": [],
            "blocked_windows": [],
            "warning_windows": ["morning"],
        },
        "run_summaries": [
            {"window": "morning", "status": "warning", "stop_line": False, "warnings": ["unexpected morning warning"]},
        ],
    }
    assert module.cron_ledger_warning_is_expected(payload) is False


def test_morning_expected_suspended_weight_warning_is_quiet() -> None:
    module = load_module()
    payload = {
        "status": "warning",
        "operator_attention": {
            "stop_line_windows": [],
            "blocked_windows": [],
            "warning_windows": ["morning"],
        },
        "run_summaries": [
            {
                "window": "morning",
                "status": "warning",
                "stop_line": False,
                "execution": {"chain_status": "ok"},
                "validation": {"acceptance_passed": True},
                "warnings": [module.EXPECTED_SUSPENDED_WEIGHT_WARNING],
            },
        ],
    }
    assert module.cron_ledger_warning_is_expected(payload) is True


def main() -> int:
    test_non_morning_warning_windows_do_not_block_morning_digest()
    test_morning_warning_still_requires_expected_warning()
    test_morning_expected_suspended_weight_warning_is_quiet()
    print("morning_control_digest tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
