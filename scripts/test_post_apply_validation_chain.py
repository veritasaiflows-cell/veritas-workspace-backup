from __future__ import annotations

import ast
import hashlib
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "post_apply_validation_chain.py"
OLD_ARTIFACT = ROOT / "tmp" / "post-apply-validation-chain.json"
OLD_ARTIFACT_SHA256 = "28539ff7aa2d8fa700de1f68c0bb5080d78077b890748b05541b3ebe4eb73e78"
OLD_ARTIFACT_SIZE = 4632

EXPECTED_PAYLOAD: dict[str, object] = {
    "schema": "veritas.post_apply_validation_chain.retired_compatibility.v1",
    "status": "blocked",
    "reason": "retired_surface",
    "surface": "post_apply_validation_chain",
    "retired": True,
    "tombstone": True,
    "compatibility_mode": "deny_only",
    "legacy_execute_allowed": False,
    "legacy_write_allowed": False,
    "validation_chain_execution_allowed": False,
    "subprocess_allowed": False,
    "filesystem_read_allowed": False,
    "filesystem_write_allowed": False,
    "network_allowed": False,
    "proposal_apply_allowed": False,
    "portfolio_state_or_mutation_allowed": False,
    "sql_mutation_allowed": False,
    "canon_mutation_allowed": False,
    "tier_mutation_allowed": False,
    "schedule_mutation_allowed": False,
    "capital_deployment_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "trade_order_or_execution_allowed": False,
    "paper_or_live_execution_allowed": False,
    "owner_approval_inferred": False,
    "exit_code": 2,
}
EXPECTED_STDOUT = json.dumps(EXPECTED_PAYLOAD, sort_keys=True, separators=(",", ":")) + "\n"


def file_state(path: Path) -> tuple[str, int, int]:
    stat = path.stat()
    return hashlib.sha256(path.read_bytes()).hexdigest(), stat.st_size, stat.st_mtime_ns


def test_every_legacy_cli_shape_is_the_same_zero_write_denial() -> None:
    before = file_state(OLD_ARTIFACT)
    assert before[:2] == (OLD_ARTIFACT_SHA256, OLD_ARTIFACT_SIZE)

    cli_shapes = [
        [],
        ["--execute"],
        ["--write"],
        ["--window", "morning"],
        ["--window", "not-a-window", "--approval-artifact", "C:\\outside\\approval.json"],
        ["--execute", "--write", "--unknown", "value", "--approval-artifact"],
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
    assert file_state(OLD_ARTIFACT) == before


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
        "portfolio_mutation_approval_artifact_validator",
        "post_apply_board_snapshot_config_coherence.py",
        "validate_canonical_ownership.py",
        "validate_portfolio_config.py",
        "full_portfolio_view.py",
        "proposal_patch_scope_validator.py",
        "portfolio_pro_forma_risk_validator.py",
        "post-apply-validation-chain.json",
        "APPLY_RESULTS_ROOT",
        "APPROVAL_ROOT",
        "validation_failed_only_because_applied",
    }
    assert all(token not in source for token in retired_operational_tokens)


def test_stale_historical_artifact_is_not_an_active_input() -> None:
    assert file_state(OLD_ARTIFACT)[:2] == (OLD_ARTIFACT_SHA256, OLD_ARTIFACT_SIZE)
    historical = json.loads(OLD_ARTIFACT.read_text(encoding="utf-8"))
    assert historical.get("status") == "ok"
    assert "post-apply-validation-chain.json" not in SCRIPT.read_text(encoding="utf-8")
