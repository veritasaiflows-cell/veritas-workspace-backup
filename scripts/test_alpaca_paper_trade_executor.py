from __future__ import annotations

import ast
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


MODULE = Path(__file__).with_name("alpaca_paper_trade_executor.py")


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


class AlpacaPaperTradeExecutorRetirementTests(unittest.TestCase):
    def test_source_is_a_minimal_fail_closed_tombstone(self) -> None:
        source = MODULE.read_text(encoding="utf-8")
        lowered = source.lower()
        tree = ast.parse(source)

        forbidden_text = (
            "import requests",
            "from requests",
            "http://",
            "https://",
            "credential",
            "endpoint",
            "--execute",
            "--apply",
            "submit",
            "cancel",
            "sell",
            "order",
            "kill_switch",
            "kill-switch",
            "make_session",
            "urlopen",
            "socket",
            "subprocess",
            "pathlib",
            "write_text",
            "write_bytes",
            "os.environ",
        )
        for token in forbidden_text:
            self.assertNotIn(token, lowered, token)

        imports = {
            alias.name
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
            for alias in node.names
        }
        imports.update(
            node.module or ""
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom)
        )
        self.assertEqual(imports, {"__future__", "json"})
        functions = [node.name for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))]
        self.assertEqual(functions, ["main"])
        calls = {call_name(node) for node in ast.walk(tree) if isinstance(node, ast.Call)}
        self.assertEqual(calls, {"print", "json.dumps", "SystemExit", "main"})
        self.assertIn('"status": "blocked"', source)
        self.assertIn('"reason": "retired_surface"', source)
        self.assertIn('"network_allowed": False', source)
        self.assertIn('"filesystem_mutation_allowed": False', source)

    def test_all_cli_shapes_block_nonzero_without_writes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_name:
            tmp = Path(tmp_name)
            marker = tmp / "preexisting.txt"
            marker.write_text("unchanged\n", encoding="utf-8")
            target = tmp / "must-not-exist.json"
            before = tree_state(tmp)
            invocations = (
                (),
                ("--help",),
                ("--unknown-legacy-flag", "value"),
                ("--execute", "--create-execution-kill-switch", "--output", str(target)),
                ("--apply", "--audit-log", str(target)),
            )
            for args in invocations:
                with self.subTest(args=args):
                    completed = subprocess.run(
                        [sys.executable, "-B", str(MODULE), *args],
                        cwd=tmp,
                        capture_output=True,
                        text=True,
                        check=False,
                    )
                    self.assertEqual(completed.returncode, 2, completed)
                    payload = json.loads(completed.stdout)
                    self.assertEqual(payload["status"], "blocked")
                    self.assertEqual(payload["reason"], "retired_surface")
                    self.assertIs(payload["network_allowed"], False)
                    self.assertIs(payload["filesystem_mutation_allowed"], False)
                    self.assertEqual(tree_state(tmp), before)


if __name__ == "__main__":
    unittest.main()
