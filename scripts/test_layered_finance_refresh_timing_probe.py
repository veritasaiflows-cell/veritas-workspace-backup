from __future__ import annotations

import ast
import json
import subprocess
import sys
import tempfile
from pathlib import Path


MODULE = Path(__file__).with_name("layered_finance_refresh_timing_probe.py")


def call_name(node: ast.Call) -> str:
    current: ast.AST = node.func
    pieces: list[str] = []
    while isinstance(current, ast.Attribute):
        pieces.append(current.attr)
        current = current.value
    if isinstance(current, ast.Name):
        pieces.append(current.id)
    return ".".join(reversed(pieces))


def tree_state(root: Path) -> list[tuple[str, bool, bytes | None]]:
    return [
        (path.relative_to(root).as_posix(), path.is_dir(), None if path.is_dir() else path.read_bytes())
        for path in sorted(root.rglob("*"))
    ]


def test_source_is_a_minimal_fail_closed_tombstone() -> None:
    source = MODULE.read_text(encoding="utf-8")
    lowered = source.lower()
    tree = ast.parse(source)

    imports = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    imports.update(node.module or "" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom))
    assert imports == {"__future__", "json"}
    functions = [node.name for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))]
    assert functions == ["main"]
    calls = {call_name(node) for node in ast.walk(tree) if isinstance(node, ast.Call)}
    assert calls == {"print", "json.dumps", "SystemExit", "main"}

    for marker in (
        '"status": "blocked"',
        '"reason": "retired_surface"',
        '"retired": True',
        '"tombstone": True',
        '"timing_probe_allowed": False',
        '"finance_chain_execution_allowed": False',
        '"subprocess_execution_allowed": False',
        '"network_allowed": False',
        '"filesystem_mutation_allowed": False',
        '"cron_schedule_mutation_allowed": False',
        '"sql_or_canon_mutation_allowed": False',
        '"tier_mutation_allowed": False',
        '"capital_account_order_or_execution_allowed": False',
        '"paper_or_live_execution_allowed": False',
        '"owner_approval_inferred": False',
    ):
        assert marker in source

    for token in (
        "import subprocess",
        "subprocess.run",
        "atomic_write",
        "pathlib",
        "socket",
        "requests",
        "urllib",
        "run_finance_refresh_chain",
        "layered_finance_refresh_chain",
        "workflow_advancement_scorecard",
    ):
        assert token not in lowered


def test_all_legacy_cli_shapes_block_nonzero_without_writes() -> None:
    with tempfile.TemporaryDirectory() as tmp_name:
        tmp = Path(tmp_name)
        marker = tmp / "preexisting.txt"
        marker.write_text("unchanged\n", encoding="utf-8")
        before = tree_state(tmp)
        invocations = (
            (),
            ("--help",),
            ("--window", "morning", "--window", "post-close"),
            ("--max-workers", "4", "--timeout-seconds", "300", "--write", "--validate"),
            ("--out", str(tmp / "must-not-exist.json")),
            ("--unknown-legacy-flag", "value"),
        )
        expected_stdout: str | None = None
        for args in invocations:
            completed = subprocess.run(
                [sys.executable, "-B", str(MODULE), *args],
                cwd=tmp,
                capture_output=True,
                text=True,
                check=False,
                timeout=10,
            )
            assert completed.returncode == 2, completed
            expected_stdout = expected_stdout or completed.stdout
            assert completed.stdout == expected_stdout
            payload = json.loads(completed.stdout)
            assert payload["status"] == "blocked"
            assert payload["reason"] == "retired_surface"
            assert payload["surface"] == "layered_finance_refresh_timing_probe"
            assert payload["retired"] is True
            assert payload["tombstone"] is True
            assert payload["timing_probe_allowed"] is False
            assert payload["subprocess_execution_allowed"] is False
            assert payload["filesystem_mutation_allowed"] is False
            assert tree_state(tmp) == before


if __name__ == "__main__":
    test_source_is_a_minimal_fail_closed_tombstone()
    test_all_legacy_cli_shapes_block_nonzero_without_writes()
    print("layered_finance_refresh_timing_probe retirement tests passed")
