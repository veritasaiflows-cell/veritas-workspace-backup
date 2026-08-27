from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from chain_manifest import manifest_steps, window_names


def _steps_for_script(script: str) -> list[tuple[str, dict[str, object]]]:
    matches: list[tuple[str, dict[str, object]]] = []
    for window in window_names():
        for step in manifest_steps(window):
            if step.get("script") == script:
                matches.append((window, step))
    return matches


def test_bank_native_probe_is_not_incrementally_skipped() -> None:
    steps = _steps_for_script("bank_native_sec_concept_probe.py")

    assert steps
    for window, step in steps:
        assert step.get("incremental_skip") is False, window


def test_fundamental_metrics_refresh_keeps_extended_timeout() -> None:
    steps = _steps_for_script("fundamental_metrics_refresh.py")

    assert steps
    for window, step in steps:
        assert int(step.get("timeout_seconds") or 0) >= 900, window


def test_bank_native_probe_precedes_fundamental_metrics_refresh() -> None:
    for window in window_names():
        steps = manifest_steps(window)
        probe_index = next(
            (index for index, step in enumerate(steps) if step.get("script") == "bank_native_sec_concept_probe.py"),
            None,
        )
        refresh_index = next(
            (index for index, step in enumerate(steps) if step.get("script") == "fundamental_metrics_refresh.py"),
            None,
        )
        if probe_index is None or refresh_index is None:
            continue
        assert probe_index < refresh_index, window
