from __future__ import annotations

import ast
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


MODULE = Path(__file__).resolve().with_name("wf67_order_card_request_generator.py")
EXPECTED_PAYLOAD = {
    "status": "blocked",
    "reason": "retired_surface",
    "retired": True,
    "tombstone": True,
    "network_allowed": False,
    "filesystem_mutation_allowed": False,
    "paper_authority": False,
    "order_authority": False,
    "account_authority": False,
}
LEGACY_FLAGS = (
    "--card",
    "--output",
    "--promotion-gate",
    "--require-promotion-gate",
)


def call_name(node: ast.Call) -> str:
    current: ast.AST = node.func
    pieces: list[str] = []
    while isinstance(current, ast.Attribute):
        pieces.append(current.attr)
        current = current.value
    if isinstance(current, ast.Name):
        pieces.append(current.id)
    return ".".join(reversed(pieces))


def assignment_literal(tree: ast.Module, name: str) -> object:
    for node in tree.body:
        if (
            isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
            and node.targets[0].id == name
        ):
            return ast.literal_eval(node.value)
    raise AssertionError(f"missing literal assignment: {name}")


def tree_state(root: Path) -> list[tuple[str, bool, bytes | None]]:
    return [
        (path.relative_to(root).as_posix(), path.is_dir(), None if path.is_dir() else path.read_bytes())
        for path in sorted(root.rglob("*"))
    ]


class Wf67OrderCardRequestGeneratorRetirementTests(unittest.TestCase):
    def test_source_is_a_minimal_fail_closed_tombstone(self) -> None:
        source = MODULE.read_text(encoding="utf-8")
        lowered = source.lower()
        tree = ast.parse(source, filename=str(MODULE))

        imports: list[tuple[str, tuple[str, ...]]] = []
        for node in ast.walk(tree):
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
        main = functions[0]
        self.assertEqual([argument.arg for argument in main.args.args], ["_argv"])
        self.assertEqual(len(main.args.defaults), 1)
        self.assertIsNone(ast.literal_eval(main.args.defaults[0]))
        self.assertFalse(
            any(
                isinstance(node, ast.Name)
                and node.id == "_argv"
                and isinstance(node.ctx, ast.Load)
                for node in ast.walk(main)
            ),
            "main must ignore every supplied argv shape",
        )

        calls = {call_name(node) for node in ast.walk(tree) if isinstance(node, ast.Call)}
        self.assertEqual(calls, {"print", "json.dumps", "SystemExit", "main"})
        self.assertEqual(assignment_literal(tree, "EXIT_BLOCKED"), 2)
        self.assertEqual(assignment_literal(tree, "BLOCKED_PAYLOAD"), EXPECTED_PAYLOAD)

        self.assertIn("retired", lowered)
        self.assertIn("tombstone", lowered)
        forbidden = (
            *LEGACY_FLAGS,
            "--apply",
            "--execute",
            "argparse",
            "pathlib",
            "subprocess",
            "socket",
            "requests",
            "httpx",
            "urllib",
            "http://",
            "https://",
            "credential",
            "os.environ",
            "sys.argv",
            "__import__",
            "importlib",
            "eval(",
            "exec(",
            "open(",
            "read_text",
            "read_bytes",
            "write_text",
            "write_bytes",
            "mkdir(",
            "unlink(",
            "rename(",
            "replace(",
        )
        for token in forbidden:
            self.assertNotIn(token, lowered, token)

    def test_all_argv_shapes_block_with_stable_json_and_no_effects(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            sandbox = Path(temporary_directory)
            sentinel = sandbox / "input-sentinel.json"
            sentinel.write_text('{"sentinel":"must-remain-unchanged"}\n', encoding="utf-8")
            nested = sandbox / "nested"
            nested.mkdir()
            nested_sentinel = nested / "owner-sentinel.txt"
            nested_sentinel.write_text("OWNER SENTINEL\n", encoding="utf-8")
            target = sandbox / "must-not-exist.json"
            before = tree_state(sandbox)
            expected_stdout = json.dumps(EXPECTED_PAYLOAD, sort_keys=True) + "\n"
            invocations = (
                (),
                ("--help",),
                ("--unknown-legacy-flag", "ignored", str(sentinel)),
                (
                    "--card",
                    str(sentinel),
                    "--output",
                    str(target),
                    "--promotion-gate",
                    str(nested_sentinel),
                    "--require-promotion-gate",
                ),
                ("--execute", "--submit-order", "--account", str(target), "positional-value"),
            )

            for argv in invocations:
                with self.subTest(argv=argv):
                    completed = subprocess.run(
                        [sys.executable, "-B", str(MODULE), *argv],
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

            self.assertFalse(target.exists())
            self.assertEqual(sentinel.read_text(encoding="utf-8"), '{"sentinel":"must-remain-unchanged"}\n')
            self.assertEqual(nested_sentinel.read_text(encoding="utf-8"), "OWNER SENTINEL\n")


if __name__ == "__main__":
    unittest.main()
