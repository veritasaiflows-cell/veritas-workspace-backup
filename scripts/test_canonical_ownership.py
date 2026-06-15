#!/usr/bin/env python3
"""Targeted tests for canonical ownership validator."""

from __future__ import annotations

import importlib.util
import sys
import tempfile
from pathlib import Path

MODULE_PATH = Path(__file__).with_name("validate_canonical_ownership.py")
spec = importlib.util.spec_from_file_location("validate_canonical_ownership", MODULE_PATH)
assert spec and spec.loader
validator = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = validator
spec.loader.exec_module(validator)


def test_execution_board_row_and_section_required() -> None:
    text = """# Execution Board

| Ticker | Lane | Action state | Close/date | Band | Stop | Technical posture | Blocker/condition | Authority note | Source/freshness |
|---|---|---|---|---|---|---|---|---|---|
| ABC | Execution | Watch-only | 1 / today | - | - | - | - | - | - |
"""
    findings = validator.validate_execution_board({"tracked_universe": {"ABC": {"coverage_lane": "execution"}}}, ["ABC"], text)
    assert any("parser-compatible" in f.message for f in findings), findings


def test_execution_board_header_required() -> None:
    findings = validator.validate_execution_board({}, [], "# Execution Board\n")
    assert any(f.severity == "critical" and "table header" in f.message for f in findings), findings


def test_coverage_heading_required() -> None:
    text = """# Coverage and Watchlist

| Ticker | Sector | Coverage Tier | Thesis pointer | Deployment/action pointer | Source lineage |
|---|---|---|---|---|---|
| ABC | Tech | Tactical | thesis | board | source |
"""
    findings = validator.validate_coverage_watchlist(["ABC"], text)
    assert any(f.severity == "critical" and "thesis section" in f.message for f in findings), findings


def test_coverage_current_deployment_state_rejected() -> None:
    text = """# Coverage and Watchlist

| Ticker | Sector | Coverage Tier | Current Deployment State | Thesis pointer | Deployment/action pointer | Source lineage |
|---|---|---|---|---|---|---|
| ABC | Tech | Tactical | Deployable now | thesis | board | source |
### ABC
"""
    findings = validator.validate_coverage_watchlist(["ABC"], text)
    assert any("Current Deployment State" in f.message for f in findings), findings


def test_retired_stub_parseable_content_rejected() -> None:
    findings = validator.validate_retired_stub(Path("Old.md"), "# Old\n\n[[New]]\n\n### ABC\n", "[[New]]")
    assert any("parseable current finance content" in f.message for f in findings), findings


def test_active_legacy_path_rejected_when_present(tmp_path: Path) -> None:
    tmp_path.mkdir(parents=True, exist_ok=True)
    old_active = tmp_path / "old-active.md"
    old_active.write_text("# old", encoding="utf-8")
    original_paths = validator.RETIRED_ACTIVE_PATHS
    original_archived = validator.ARCHIVED_ORIGINALS
    original_retired = (
        validator.TECHNICAL_RETIRED,
        validator.TRIGGER_RETIRED,
        validator.WATCHLIST_RETIRED,
        validator.COVERAGE_RETIRED,
    )
    try:
        validator.RETIRED_ACTIVE_PATHS = [old_active]
        validator.ARCHIVED_ORIGINALS = []
        validator.TECHNICAL_RETIRED = tmp_path / "technical.md"
        validator.TRIGGER_RETIRED = tmp_path / "trigger.md"
        validator.WATCHLIST_RETIRED = tmp_path / "watchlist.md"
        validator.COVERAGE_RETIRED = tmp_path / "coverage.md"
        for path, target in [
            (validator.TECHNICAL_RETIRED, "[[03. Portfolio/Execution Board]]"),
            (validator.TRIGGER_RETIRED, "[[03. Portfolio/Execution Board]]"),
            (validator.WATCHLIST_RETIRED, "[[04. Research/Coverage and Watchlist]]"),
            (validator.COVERAGE_RETIRED, "[[04. Research/Coverage and Watchlist]]"),
        ]:
            path.write_text(f"# retired\n\n{target}\n", encoding="utf-8")
        findings = validator.validate_retired_legacy_files()
    finally:
        validator.RETIRED_ACTIVE_PATHS = original_paths
        validator.ARCHIVED_ORIGINALS = original_archived
        (
            validator.TECHNICAL_RETIRED,
            validator.TRIGGER_RETIRED,
            validator.WATCHLIST_RETIRED,
            validator.COVERAGE_RETIRED,
        ) = original_retired
    assert any("active canon folder" in f.message for f in findings), findings


def main() -> int:
    test_execution_board_row_and_section_required()
    test_execution_board_header_required()
    test_coverage_heading_required()
    test_coverage_current_deployment_state_rejected()
    test_retired_stub_parseable_content_rejected()
    with tempfile.TemporaryDirectory() as tmpdir:
        test_active_legacy_path_rejected_when_present(Path(tmpdir))
    print("canonical_ownership_tests_passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
