from __future__ import annotations

import ast
import hashlib
import importlib.util
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "sql_retail_expansion_phase_gate.py"
HISTORICAL_ARTIFACT = ROOT / "tmp" / "sql-retail-expansion-phases-1-4-gate.json"
HISTORICAL_SHA256 = "bcfbeeaf93e285aa0c5d00b379b3c2fcdc96133df525ed192a8949721275b192"
HISTORICAL_SIZE = 5192

EXPECTED_PAYLOAD: dict[str, object] = {
    "schema": "veritas.sql_retail_expansion_phase_gate.retired_compatibility.v1",
    "status": "blocked",
    "reason": "retired_surface",
    "surface": "sql_retail_expansion_phase_gate",
    "retired": True,
    "tombstone": True,
    "compatibility_mode": "deny_only",
    "legacy_write_allowed": False,
    "legacy_validate_allowed": False,
    "ticker_card_generation_allowed": False,
    "retail_expansion_allowed": False,
    "retail_import_allowed": False,
    "phase5_import_allowed": False,
    "sql_read_allowed": False,
    "sql_write_allowed": False,
    "subprocess_allowed": False,
    "filesystem_read_allowed": False,
    "filesystem_write_allowed": False,
    "network_allowed": False,
    "schedule_mutation_allowed": False,
    "canon_mutation_allowed": False,
    "tier_mutation_allowed": False,
    "portfolio_state_or_mutation_allowed": False,
    "capital_deployment_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "trade_order_or_execution_allowed": False,
    "paper_or_live_execution_allowed": False,
    "owner_approval_inferred": False,
    "exit_code": 2,
}
EXPECTED_STDOUT = json.dumps(EXPECTED_PAYLOAD, sort_keys=True, separators=(",", ":")) + "\n"


def load_script(name: str):
    script = ROOT / "scripts" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, script)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


validation_bundle = load_script("sql_retail_grade_validation_bundle")


def file_state(path: Path) -> tuple[str, int, int]:
    stat = path.stat()
    return hashlib.sha256(path.read_bytes()).hexdigest(), stat.st_size, stat.st_mtime_ns


def test_every_legacy_cli_shape_is_the_same_zero_write_denial() -> None:
    before = file_state(HISTORICAL_ARTIFACT)
    assert before[:2] == (HISTORICAL_SHA256, HISTORICAL_SIZE)
    historical = json.loads(HISTORICAL_ARTIFACT.read_text(encoding="utf-8"))
    assert historical.get("status") == "blocked"

    cli_shapes = [
        [],
        ["--write"],
        ["--validate"],
        ["--write", "--validate"],
        ["--phase", "5", "--ticker", "NVDA"],
        ["--unknown", "value", "--import", "--output", "C:\\outside\\result.json"],
    ]
    outputs: list[str] = []
    for args in cli_shapes:
        proc = subprocess.run(
            [sys.executable, "-B", str(SCRIPT), *args],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        assert proc.returncode == 2
        assert proc.stderr == ""
        assert proc.stdout == EXPECTED_STDOUT
        assert json.loads(proc.stdout) == EXPECTED_PAYLOAD
        outputs.append(proc.stdout)

    assert len(set(outputs)) == 1
    assert file_state(HISTORICAL_ARTIFACT) == before


def test_tombstone_has_no_operational_or_write_capability() -> None:
    source = SCRIPT.read_text(encoding="utf-8")
    tree = ast.parse(source)

    imported_modules: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_modules.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imported_modules.append(node.module or "")
    assert sorted(imported_modules) == ["__future__", "json"]

    forbidden_calls = {
        "open",
        "read_text",
        "write_text",
        "read_bytes",
        "write_bytes",
        "mkdir",
        "unlink",
        "rename",
        "replace",
        "run",
        "Popen",
        "connect",
        "urlopen",
    }
    invoked: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if isinstance(node.func, ast.Name):
            invoked.add(node.func.id)
        elif isinstance(node.func, ast.Attribute):
            invoked.add(node.func.attr)
    assert invoked.isdisjoint(forbidden_calls)

    retired_operational_tokens = {
        "wf72_entry_stop_reference_helper",
        "NO_DRIFT_FIELDS",
        "finance-intelligence-state.sqlite",
        "build_42_no_drift_review",
        "classify_retail_blockers",
        "ready_for_phase5_design_no_import",
        "sql-retail-expansion-phases-1-4-gate.json",
        "subprocess.run",
        "Path(",
    }
    assert all(token not in source for token in retired_operational_tokens)


def test_validation_bundle_keeps_retired_gate_visible_as_warning() -> None:
    ticker_step = next(item for item in validation_bundle.COMMANDS if item["name"] == "ticker_card_validate_only_pilot")
    assert "--validate-only" in ticker_step["args"]
    assert validation_bundle.AUTHORITY["production_answer_path_writes_allowed"] is False

    gate_step = next(item for item in validation_bundle.COMMANDS if item["name"] == "sql_retail_expansion_phases_1_4_gate")
    assert gate_step["args"] == ["scripts\\sql_retail_expansion_phase_gate.py", "--write", "--validate"]
    assert gate_step["nonzero_allowed"] is True
    result = validation_bundle.run_command(gate_step)
    assert result["returncode"] == 2
    assert result["nonzero_allowed"] is True
    assert result["ok"] is True
    assert json.loads(result["stdout_tail"])["status"] == "blocked"
    warning_steps = [result] if result["returncode"] != 0 and result["ok"] else []
    assert warning_steps == [result]
