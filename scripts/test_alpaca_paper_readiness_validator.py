from __future__ import annotations

import ast
import json
import shutil
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


class RetiredPaperValidatorTests(unittest.TestCase):
    def test_sources_are_minimal_fail_closed_tombstones(self) -> None:
        forbidden_text = (
            "--apply",
            "--execute",
            "--output",
            "--policy",
            "--proof",
            "--validate",
            "--wrapper",
            "--write",
            "__import__",
            "argparse",
            "compile(",
            "credential",
            "eval(",
            "exec(",
            "http://",
            "https://",
            "httpx",
            "importlib",
            "input(",
            "mkdir",
            "open(",
            "os.environ",
            "pathlib",
            "read_bytes",
            "read_text",
            "rename(",
            "replace(",
            "requests",
            "rmdir",
            "secret",
            "socket",
            "subprocess",
            "token",
            "touch(",
            "unlink",
            "urllib",
            "write_bytes",
            "write_text",
        )

        for module in MODULES:
            with self.subTest(module=module.name):
                source = module.read_text(encoding="utf-8")
                lowered = source.lower()
                tree = ast.parse(source, filename=str(module))

                self.assertIn("retired", lowered)
                self.assertIn("tombstone", lowered)
                for token in forbidden_text:
                    self.assertNotIn(token, lowered, token)

                imports: list[tuple[str, tuple[str, ...]]] = []
                for node in tree.body:
                    if isinstance(node, ast.Import):
                        imports.extend((alias.name, ()) for alias in node.names)
                    elif isinstance(node, ast.ImportFrom):
                        imports.append((node.module or "", tuple(alias.name for alias in node.names)))
                self.assertEqual(imports, [("__future__", ("annotations",)), ("json", ())])

                functions = [
                    node
                    for node in ast.walk(tree)
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                ]
                self.assertEqual([node.name for node in functions], ["main"])
                self.assertEqual([node for node in ast.walk(tree) if isinstance(node, ast.ClassDef)], [])

                calls = {call_name(node) for node in ast.walk(tree) if isinstance(node, ast.Call)}
                self.assertEqual(calls, {"SystemExit", "json.dumps", "main", "print"})
                self.assertNotIn("<dynamic>", calls)

                main_function = functions[0]
                self.assertEqual([argument.arg for argument in main_function.args.args], ["_argv"])
                self.assertNotIn(
                    "_argv",
                    {node.id for node in ast.walk(main_function) if isinstance(node, ast.Name)},
                )
                returns = [node.value for node in ast.walk(main_function) if isinstance(node, ast.Return)]
                self.assertEqual(len(returns), 1)
                self.assertIsInstance(returns[0], ast.Name)
                self.assertEqual(returns[0].id, "EXIT_BLOCKED")

                exit_assignments = [
                    node
                    for node in tree.body
                    if isinstance(node, ast.Assign)
                    and any(isinstance(target, ast.Name) and target.id == "EXIT_BLOCKED" for target in node.targets)
                ]
                self.assertEqual(len(exit_assignments), 1)
                self.assertEqual(ast.literal_eval(exit_assignments[0].value), 2)

                dumps_calls = [
                    node
                    for node in ast.walk(main_function)
                    if isinstance(node, ast.Call) and call_name(node) == "json.dumps"
                ]
                self.assertEqual(len(dumps_calls), 1)
                self.assertEqual(ast.literal_eval(dumps_calls[0].args[0]), EXPECTED_PAYLOAD)
                sort_keys = next(
                    (keyword.value for keyword in dumps_calls[0].keywords if keyword.arg == "sort_keys"),
                    None,
                )
                self.assertIsInstance(sort_keys, ast.Constant)
                self.assertIs(sort_keys.value, True)

    def test_every_cli_shape_is_stable_blocked_and_filesystem_neutral(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            sandbox = Path(temporary_directory)
            scripts_directory = sandbox / "scripts"
            scripts_directory.mkdir()
            module_copies = []
            for module in MODULES:
                module_copy = scripts_directory / module.name
                shutil.copyfile(module, module_copy)
                module_copies.append(module_copy)

            inputs = sandbox / "inputs"
            inputs.mkdir()
            policy = inputs / "policy.json"
            proof = inputs / "proof.json"
            wrapper = inputs / "legacy-wrapper.py"
            policy.write_text('{"sentinel":"policy-must-stay-unchanged"}\n', encoding="utf-8")
            proof.write_text('{"sentinel":"proof-must-stay-unchanged"}\n', encoding="utf-8")
            wrapper.write_text("WRAPPER SENTINEL\n", encoding="utf-8")

            output = sandbox / "must-not-exist.json"
            guard_output = sandbox / "nested" / "guard-must-not-exist.json"
            cases = {
                "no_args": [],
                "help_is_not_operational": ["--help"],
                "legacy_wrapper_output_write": [
                    "--wrapper",
                    str(wrapper),
                    "--write",
                    "--output",
                    str(output),
                    "--guard-report",
                    str(guard_output),
                ],
                "legacy_readiness_paths_and_writes": [
                    "--policy",
                    str(policy),
                    "--proof",
                    str(proof),
                    "--require-read-only-proof",
                    "--validate-order-previews",
                    "--preview-dir",
                    str(inputs),
                    "--validate-shadow-mode",
                    "--shadow-report",
                    str(proof),
                    "--write-no-submit-guard-report",
                    "--no-submit-guard-output",
                    str(guard_output),
                    "--write",
                    "--output",
                    str(output),
                ],
                "caller_cannot_override_payload": [
                    "--status",
                    "ok",
                    "--reason",
                    "active_surface",
                    "--retired",
                    "false",
                    "--tombstone",
                    "false",
                    "--ready-for-paper-submit-cancel",
                    "true",
                    "--output",
                    str(output),
                ],
                "arbitrary_args": ["positional-value", "--unknown-option", "ignored-value", "{}"],
            }

            before = tree_state(sandbox)
            expected_stdout = json.dumps(EXPECTED_PAYLOAD, sort_keys=True) + "\n"
            for module in module_copies:
                for case_name, argv in cases.items():
                    with self.subTest(module=module.name, case=case_name):
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
            self.assertFalse(guard_output.exists())
            self.assertEqual(policy.read_text(encoding="utf-8"), '{"sentinel":"policy-must-stay-unchanged"}\n')
            self.assertEqual(proof.read_text(encoding="utf-8"), '{"sentinel":"proof-must-stay-unchanged"}\n')
            self.assertEqual(wrapper.read_text(encoding="utf-8"), "WRAPPER SENTINEL\n")


if __name__ == "__main__":
    unittest.main()
