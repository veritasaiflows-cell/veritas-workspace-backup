from __future__ import annotations

import ast
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


HELPER = Path(__file__).resolve().with_name("portfolio_mutation_apply_helper.py")
RETIRED_MARKER = "portfolio_mutation_surface_retired_tombstone_v1"
EXPECTED_RESULT = {
    "status": "blocked",
    "reason": "retired_surface",
    "marker": RETIRED_MARKER,
    "retired": True,
    "tombstone": True,
    "approval_artifact_read_allowed": False,
    "backup_creation_allowed": False,
    "owner_or_canon_write_allowed": False,
    "portfolio_mutation_allowed": False,
    "filesystem_mutation_allowed": False,
    "network_allowed": False,
}


def expect(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def call_name(node: ast.Call) -> str:
    if isinstance(node.func, ast.Name):
        return node.func.id
    if isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name):
        return f"{node.func.value.id}.{node.func.attr}"
    return "<dynamic>"


def snapshot_tree(root: Path) -> dict[str, tuple[str, int, str]]:
    snapshot: dict[str, tuple[str, int, str]] = {}
    for path in sorted(root.rglob("*"), key=lambda item: str(item.relative_to(root))):
        relative = path.relative_to(root).as_posix()
        if path.is_dir():
            snapshot[relative] = ("directory", 0, "")
        elif path.is_file():
            data = path.read_bytes()
            snapshot[relative] = ("file", len(data), hashlib.sha256(data).hexdigest())
        else:
            snapshot[relative] = ("other", 0, "")
    return snapshot


def run_helper(helper: Path, cwd: Path, argv: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-B", str(helper), *argv],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
    )


def test_static_fail_closed_contract(errors: list[str]) -> None:
    source = HELPER.read_text(encoding="utf-8")
    try:
        tree = ast.parse(source, filename=str(HELPER))
    except SyntaxError as exc:
        errors.append(f"helper must be parseable: {exc}")
        return

    lower_source = source.lower()
    expect("retired" in lower_source, "helper must declare that the surface is retired", errors)
    expect("tombstone" in lower_source, "helper must declare itself a tombstone", errors)
    expect("--apply" not in source, "former apply flag must not exist", errors)
    expect("--execute" not in source, "execution flag must not exist", errors)
    expect("http://" not in lower_source and "https://" not in lower_source, "helper must contain no network URL", errors)

    imports: list[tuple[str, tuple[str, ...]]] = []
    for node in tree.body:
        if isinstance(node, ast.Import):
            imports.extend((alias.name, ()) for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imports.append((node.module or "", tuple(alias.name for alias in node.names)))
    expect(
        imports == [("__future__", ("annotations",)), ("json", ())],
        f"helper imports must be limited to __future__/json, got {imports}",
        errors,
    )

    functions = [node for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))]
    expect([node.name for node in functions] == ["main"], f"only main may remain, got {[node.name for node in functions]}", errors)

    calls = [call_name(node) for node in ast.walk(tree) if isinstance(node, ast.Call)]
    allowed_calls = {"json.dumps", "print", "main", "SystemExit"}
    expect(set(calls) == allowed_calls, f"unexpected or missing helper calls: {calls}", errors)
    expect("<dynamic>" not in calls, "dynamic calls must not exist", errors)

    main_function = next((node for node in functions if node.name == "main"), None)
    if main_function is not None:
        return_values = [
            node.value.value
            for node in ast.walk(main_function)
            if isinstance(node, ast.Return) and isinstance(node.value, ast.Constant) and isinstance(node.value.value, int)
        ]
        expect(2 in return_values, f"main must return 2, got {return_values}", errors)
        expect(0 not in return_values, "main must have no zero return", errors)

    forbidden_text = (
        "portfolio_mutation_proposal_schema_validator",
        "proposal_patch_scope_validator",
        "execute_apply",
        "build_apply_plan",
        "build_preview",
        "write_apply_result",
        "write_outputs",
        "atomic_write_text",
        "subprocess",
        "socket",
        "urllib",
        "requests",
        "eval(",
        "exec(",
        "__import__(",
    )
    for item in forbidden_text:
        expect(item not in source, f"forbidden capability remains in helper: {item}", errors)


def test_subprocess_is_stable_and_effect_free(errors: list[str]) -> None:
    with tempfile.TemporaryDirectory() as temporary_directory:
        sandbox = Path(temporary_directory)
        scripts_directory = sandbox / "scripts"
        scripts_directory.mkdir()
        helper_copy = scripts_directory / HELPER.name
        shutil.copyfile(HELPER, helper_copy)

        inputs_directory = sandbox / "inputs"
        inputs_directory.mkdir()
        proposal = inputs_directory / "proposal.json"
        approval = inputs_directory / "approval.json"
        proposal.write_text('{"sentinel":"proposal-must-not-be-read-or-written"}\n', encoding="utf-8")
        approval.write_text('{"sentinel":"approval-must-not-be-read-or-written"}\n', encoding="utf-8")

        owner_directory = sandbox / "owner"
        owner_directory.mkdir()
        owner_surface = owner_directory / "canon.md"
        owner_surface.write_text("OWNER CANON SENTINEL\n", encoding="utf-8")
        backup_directory = sandbox / "tmp" / "portfolio-mutation-proposals" / "apply-backups"

        cases = {
            "no_args": [],
            "harmless_legacy_args": [
                "--proposal-bundle",
                str(proposal),
                "--proposal-id",
                "legacy-proposal",
                "--window",
                "post-close",
                "--write",
            ],
            "retired_operational_args": [
                "--apply",
                "--approval-artifact",
                str(approval),
                "--plan-apply",
                "--execute",
                str(owner_surface),
            ],
            "arbitrary_args": ["--unknown-option", "ignored-value", "positional-value"],
        }

        before = snapshot_tree(sandbox)
        expected_stdout = json.dumps(EXPECTED_RESULT, sort_keys=True) + "\n"
        for name, argv in cases.items():
            completed = run_helper(helper_copy, sandbox, argv)
            expect(completed.returncode == 2, f"{name}: expected exit 2, got {completed.returncode}", errors)
            expect(completed.stdout == expected_stdout, f"{name}: unstable blocked JSON: {completed.stdout!r}", errors)
            expect(completed.stderr == "", f"{name}: unexpected stderr: {completed.stderr!r}", errors)
            try:
                payload = json.loads(completed.stdout)
            except json.JSONDecodeError as exc:
                errors.append(f"{name}: stdout must be JSON: {exc}")
            else:
                expect(payload == EXPECTED_RESULT, f"{name}: wrong blocked payload: {payload}", errors)
            expect(snapshot_tree(sandbox) == before, f"{name}: subprocess changed the sandbox", errors)

        expect(not backup_directory.exists(), "retired helper must not create a backup directory", errors)
        expect(owner_surface.read_text(encoding="utf-8") == "OWNER CANON SENTINEL\n", "owner/canon sentinel changed", errors)
        expect(
            approval.read_text(encoding="utf-8") == '{"sentinel":"approval-must-not-be-read-or-written"}\n',
            "approval sentinel changed",
            errors,
        )
        expect(
            proposal.read_text(encoding="utf-8") == '{"sentinel":"proposal-must-not-be-read-or-written"}\n',
            "proposal sentinel changed",
            errors,
        )


def main() -> int:
    errors: list[str] = []
    test_static_fail_closed_contract(errors)
    test_subprocess_is_stable_and_effect_free(errors)
    if errors:
        print("portfolio_mutation_apply_helper_tests_failed")
        for error in errors:
            print(f"- {error}")
        return 1
    print("portfolio_mutation_apply_helper_tests_passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
