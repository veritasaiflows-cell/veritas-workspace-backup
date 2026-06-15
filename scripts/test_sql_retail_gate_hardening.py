from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))


def load_script(name: str):
    script = ROOT / "scripts" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, script)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


phase_gate = load_script("sql_retail_expansion_phase_gate")
validation_bundle = load_script("sql_retail_grade_validation_bundle")


def test_phase_gate_non_write_preserves_existing_artifacts() -> None:
    targets = [phase_gate.NO_DRIFT_OUT, phase_gate.BLOCKERS_OUT, phase_gate.PHASES_OUT]
    before = {path: path.read_bytes() if path.exists() else None for path in targets}

    no_drift = phase_gate.build_42_no_drift_review(write=False)
    blockers = phase_gate.classify_retail_blockers(write=False)
    report = phase_gate.build_phase_gate(no_drift, blockers, write=False)

    assert report["validation"]["status"] == "ok"
    after = {path: path.read_bytes() if path.exists() else None for path in targets}
    assert after == before


def test_phase3_blocker_check_is_semantic_not_row_count_only() -> None:
    malformed = {
        "status": "classified_ready",
        "summary": {
            "readiness_status": "ready",
            "cache_rows": 265,
            "sql_effective_allowed_rows": 1,
            "fallback_or_blocked_rows": 264,
        },
    }
    assert phase_gate.phase3_blockers_ok(malformed) is False


def test_validation_bundle_ticker_card_step_is_validate_only() -> None:
    step = next(item for item in validation_bundle.COMMANDS if item["name"] == "ticker_card_validate_only_pilot")
    assert "--validate-only" in step["args"]
    assert "production_answer_path_writes_allowed" in validation_bundle.AUTHORITY
    assert validation_bundle.AUTHORITY["production_answer_path_writes_allowed"] is False
