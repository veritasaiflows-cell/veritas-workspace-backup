#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "veritas_harness_scorecard.py"


def load_module():
    spec = importlib.util.spec_from_file_location("veritas_harness_scorecard", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_source_truth_parity_sql_first_pending_shape() -> None:
    module = load_module()
    payload = {
        "status": "phase2_parity_not_ready",
        "summary": {
            "markdown_rows": 0,
            "finance_sql_rows": 42,
            "canon_cache_tickers": 42,
            "mismatch_rows": 0,
            "missing_finance_rows": 0,
            "missing_canon_rows": 0,
        },
    }
    assert module.source_truth_parity_sql_first_pending(payload) is True
    payload["summary"]["mismatch_rows"] = 1
    assert module.source_truth_parity_sql_first_pending(payload) is False
    assert module.source_truth_parity_sql_first_pending({"status": "phase2_sql_first_thin_board_contract_ok"}) is True


def test_source_truth_parity_expected_pending_reclassifies_command_and_artifact() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        artifact = root / "go-source-truth-parity-validation.json"
        artifact.write_text(
            json.dumps(
                {
                    "status": "phase2_parity_not_ready",
                    "summary": {
                        "markdown_rows": 0,
                        "finance_sql_rows": 42,
                        "canon_cache_tickers": 42,
                        "mismatch_rows": 0,
                        "missing_finance_rows": 0,
                        "missing_canon_rows": 0,
                    },
                }
            ),
            encoding="utf-8",
        )
        original = module.EXPECTED_PENDING_GATES["go_source_truth_parity_validator"]
        module.EXPECTED_PENDING_GATES["go_source_truth_parity_validator"] = {
            **original,
            "artifact": artifact,
        }
        try:
            checks = [
                {
                    "name": "go_source_truth_parity_validator",
                    "type": "command",
                    "status": "fail",
                    "returncode": 2,
                },
                {
                    "name": "go_source_truth_parity_validator",
                    "type": "artifact",
                    "status": "fail",
                    "observed": "phase2_parity_not_ready",
                },
            ]
            reclassified = module.apply_expected_pending(checks)
            assert len(reclassified) == 2
            assert {row["status"] for row in checks} == {"expected_pending"}
        finally:
            module.EXPECTED_PENDING_GATES["go_source_truth_parity_validator"] = original


def test_fast_checks_refresh_artifact_index_before_validate() -> None:
    module = load_module()
    seen: list[tuple[str, list[str]]] = []

    def fake_run_command(name, command, timeout=120, cwd=None):
        seen.append((name, command))
        return {"name": name, "status": "pass", "returncode": 0}

    module.run_command = fake_run_command
    checks = module.fast_command_checks()
    names = [row["name"] for row in checks]
    assert "artifact_index_incremental" in names
    assert "artifact_index_validate" in names
    assert names.index("artifact_index_incremental") < names.index("artifact_index_validate")
    incremental_command = dict(seen)["artifact_index_incremental"]
    assert incremental_command[-1] == "incremental"
