#!/usr/bin/env python3
"""Regression checks for WF72 major closeout telemetry delta helper."""
from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "major_closeout_delta.py"


def load_module():
    spec = importlib.util.spec_from_file_location("major_closeout_delta", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


def main() -> int:
    m = load_module()
    report = m.build()
    errors = m.validate(report)
    assert errors == [], errors
    assert report["report_only"] is True
    assert report["mutations_performed"] is False
    assert report["summary"]["external_export"] is False
    md = m.render(report)
    required = [
        "Medium tool events",
        "High tool events",
        "Truncated tool events",
        "OTEL logs enabled now",
        "OTEL content capture enabled now",
        "External export",
        "review-only evidence",
    ]
    missing = [needle for needle in required if needle not in md]
    assert not missing, missing
    print("major_closeout_delta_tests_passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
