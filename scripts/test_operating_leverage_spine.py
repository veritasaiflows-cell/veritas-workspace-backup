#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "operating_leverage_spine.py"


def load_module():
    spec = importlib.util.spec_from_file_location("operating_leverage_spine", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_warning_digest_with_blocked_stop_line_text_is_not_blocked() -> None:
    module = load_module()
    row = module.classify_digest(
        "morning_control_digest",
        {
            "status": "warning",
            "operator_action": "MAIN_HANDOFF_REQUIRED",
            "critical_findings": [],
            "warning_findings": ["cron_operator_ledger:status_warning"],
            "stop_lines": [
                "Blocked source artifacts remain blocked until their owner producer repairs them."
            ],
        },
        ROOT / "tmp" / "morning-control-digest.json",
    )
    assert row["class"] == "MAIN_SESSION_REQUIRED"
    assert row["reason"] == "digest_requests_main_handoff"


def test_critical_digest_stays_blocked() -> None:
    module = load_module()
    row = module.classify_digest(
        "post_close_control_digest",
        {
            "status": "critical",
            "operator_action": "BLOCKED",
            "critical_findings": ["post_close_run:status_blocked"],
        },
        ROOT / "tmp" / "post-close-control-digest.json",
    )
    assert row["class"] == "BLOCKED"
    assert row["reason"] == "digest_structured_blocked"


def main() -> int:
    test_warning_digest_with_blocked_stop_line_text_is_not_blocked()
    test_critical_digest_stays_blocked()
    print("operating_leverage_spine tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
