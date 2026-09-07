from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import python_go_durable_output_parity_repeated_gate as gate


MODULE = Path(__file__).with_name("python_go_durable_output_parity_repeated_gate.py")


def test_current_case_contract_runs_one_stable_case_without_retired_wf78() -> None:
    def fake_run(command: list[str], cwd: Path) -> dict:
        return {
            "command": command,
            "cwd": cwd.relative_to(gate.ROOT).as_posix() if cwd != gate.ROOT else ".",
            "returncode": 0,
            "ok": True,
            "stdout_tail": "",
            "stderr_tail": "",
        }

    def fake_load(path: Path) -> dict:
        if "parity" in path.name:
            return {"status": "ok", "summary": {"checks": 4, "critical": 0}}
        return {
            "status": "ok",
            "mode": "fixture",
            "source_shape": {"rows": 32},
            "semantic_summary": {"active_ticker_count": 32},
            "validation": {"status": "ok", "errors": [], "warnings": []},
        }

    with patch.object(gate, "run_command", side_effect=fake_run), patch.object(gate, "load", side_effect=fake_load):
        report = gate.build_report(2)

    assert gate.SCHEMA == "veritas.python_go_durable_output_parity_repeated_gate.v2"
    assert gate.ACTIVE_CASE_NAMES == ("finance_universe_validation",)
    assert [row["name"] for row in gate.CASES] == ["finance_universe_validation"]
    assert report["status"] == "ok"
    assert report["summary"]["cycles"] == 2
    assert report["summary"]["cases"] == 1
    assert report["summary"]["case_names"] == ["finance_universe_validation"]
    assert report["summary"]["case_contract_status"] == "ok"
    assert report["summary"]["stable_case_fingerprints"] == 1
    assert report["summary"]["checks"] == 10
    assert {row["case"] for row in report["cycle_rows"]} == {"finance_universe_validation"}
    assert report["authority_boundary"]["live_sql_write_or_import_allowed"] is False
    assert report["authority_boundary"]["canon_or_portfolio_mutation"] is False
    assert report["authority_boundary"]["paper_or_live_execution"] is False
    assert "wf78" not in MODULE.read_text(encoding="utf-8").lower()
    assert "wf78" not in json.dumps(report, sort_keys=True).lower()
