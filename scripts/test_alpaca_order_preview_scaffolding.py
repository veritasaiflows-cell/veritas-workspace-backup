from __future__ import annotations

import ast
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


MODULES = (
    Path(__file__).resolve().with_name("alpaca_paper_execution_guard_validator.py"),
    Path(__file__).resolve().with_name("alpaca_paper_readiness_validator.py"),
)
EXPECTED_PAYLOAD = {
    "schema": "veritas.retired_paper_validator.v1",
    "status": "blocked",
    "reason": "retired_surface",
    "retired": True,
    "tombstone": True,
    "ready_for_paper_submit_cancel": False,
    "network_allowed": False,
    "filesystem_mutation_allowed": False,
    "paper_execution_allowed": False,
    "order_action_allowed": False,
    "account_action_allowed": False,
    "owner_approval_inferred": False,
    "maintains_simulated_account_state": False,
}


def call_name(node: ast.Call) -> str:
    current: ast.AST = node.func
    pieces: list[str] = []
    while isinstance(current, ast.Attribute):
        pieces.append(current.attr)
        current = current.value
    if isinstance(current, ast.Name):
        pieces.append(current.id)
    return ".".join(reversed(pieces)) or "<dynamic>"


def tree_state(root: Path) -> list[tuple[str, bool, bytes | None]]:
    return [
        (path.relative_to(root).as_posix(), path.is_dir(), None if path.is_dir() else path.read_bytes())
        for path in sorted(root.rglob("*"), key=lambda item: item.relative_to(root).as_posix())
    ]


class RetiredOrderPreviewScaffoldingTests(unittest.TestCase):
    def test_both_validator_surfaces_are_retired_tombstones(self) -> None:
        removed_apis = {
            "build_no_submit_guard_report",
            "validate",
            "validate_order_preview",
            "validate_order_previews",
            "validate_read_only_connection_proof",
            "validate_shadow_report",
        }
        for module in MODULES:
            with self.subTest(module=module.name):
                source = module.read_text(encoding="utf-8")
                tree = ast.parse(source, filename=str(module))
                functions = {
                    node.name
                    for node in ast.walk(tree)
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                }
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
                calls = {call_name(node) for node in ast.walk(tree) if isinstance(node, ast.Call)}

                self.assertEqual(imports, {"__future__", "json"})
                self.assertEqual(functions, {"main"})
                self.assertTrue(functions.isdisjoint(removed_apis))
                self.assertEqual(calls, {"SystemExit", "json.dumps", "main", "print"})
                self.assertIn('"status": "blocked"', source)
                self.assertIn('"reason": "retired_surface"', source)
                self.assertIn('"retired": True', source)
                self.assertIn('"tombstone": True', source)
                for key in (
                    "ready_for_paper_submit_cancel",
                    "network_allowed",
                    "filesystem_mutation_allowed",
                    "paper_execution_allowed",
                    "order_action_allowed",
                    "account_action_allowed",
                    "owner_approval_inferred",
                    "maintains_simulated_account_state",
                ):
                    self.assertIn(f'"{key}": False', source)

    def test_retired_scaffolding_flags_cannot_restore_behavior_or_write(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            sandbox = Path(temporary_directory)
            input_directory = sandbox / "inputs"
            input_directory.mkdir()
            preview = input_directory / "preview.json"
            shadow = input_directory / "shadow.json"
            preview.write_text('{"sentinel":"preview-unchanged"}\n', encoding="utf-8")
            shadow.write_text('{"sentinel":"shadow-unchanged"}\n', encoding="utf-8")
            output = sandbox / "outputs" / "must-not-exist.json"
            before = tree_state(sandbox)
            expected_stdout = json.dumps(EXPECTED_PAYLOAD, sort_keys=True) + "\n"

            argv = [
                "--validate-order-previews",
                "--preview-dir",
                str(input_directory),
                "--validate-shadow-mode",
                "--shadow-report",
                str(shadow),
                "--write-no-submit-guard-report",
                "--no-submit-guard-output",
                str(output),
                "--wrapper",
                str(preview),
                "--write",
                "--output",
                str(output),
                "--arbitrary-retired-override",
                "enabled",
            ]
            for module in MODULES:
                with self.subTest(module=module.name):
                    completed = subprocess.run(
                        [sys.executable, "-B", str(module), *argv],
                        cwd=sandbox,
                        capture_output=True,
                        text=True,
                        check=False,
                        timeout=10,
                    )
                    self.assertEqual(completed.returncode, 2, completed)
                    self.assertEqual(completed.stdout, expected_stdout)
                    self.assertEqual(completed.stderr, "")
                    self.assertEqual(json.loads(completed.stdout), EXPECTED_PAYLOAD)
                    self.assertEqual(tree_state(sandbox), before)

            self.assertFalse(output.exists())
            self.assertEqual(preview.read_text(encoding="utf-8"), '{"sentinel":"preview-unchanged"}\n')
            self.assertEqual(shadow.read_text(encoding="utf-8"), '{"sentinel":"shadow-unchanged"}\n')


if __name__ == "__main__":
    unittest.main()
