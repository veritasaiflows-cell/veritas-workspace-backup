#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "skill_core_proof_tier_audit.py"


def load_module():
    spec = importlib.util.spec_from_file_location("skill_core_proof_tier_audit", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def expect(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def write_skill(skills_dir: Path, name: str, body: str) -> Path:
    path = skills_dir / name / "SKILL.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    return path


def minimal_good_task_intake_body() -> str:
    return """---
name: "task-intake-contract"
description: "test"
---

# Task Intake Contract

Use this skill for material tasks with authority, sources, proof, and closeout.

## Purpose

Authority class is required. Acceptance proof is required. Debugging loop is required. Cleanup scope is required. Response contract is required.

## Boundaries

Stop line: stop if proof or authority is missing. Keep paper/live/account and capital deployment separate from review-only work. Treat Config / Auth / Runtime as sensitive.

## Procedure

This body contains enough words to represent a real skill contract. The validator should accept it only when all required local contract anchors remain present. This text is intentionally compact but above the minimum word count because the real validator should fail thin placeholder skills that would otherwise look structurally valid while lacking operational substance, route discipline, and authority language.
"""


def test_current_workspace_core_audit_ok(errors: list[str]) -> None:
    module = load_module()
    payload = module.build_payload(ROOT / "skills")
    expect(payload["status"] == "ok", f"workspace core audit should pass: {payload['validation']['errors'][:3]}", errors)
    expect(payload["summary"]["audited_core_skill_count"] == 13, "expected 13 P3 core skills", errors)
    expect(payload["summary"]["tier2_local_proof_count"] == 13, "expected all P3 core skills to qualify", errors)


def test_missing_required_term_blocks(errors: list[str]) -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        skills_dir = Path(tmpdir) / "skills"
        body = minimal_good_task_intake_body().replace("Acceptance proof", "Completion evidence")
        write_skill(skills_dir, "task-intake-contract", body)
        result = module.audit_skill(skills_dir, "task-intake-contract", module.CORE_CONTRACTS["task-intake-contract"])
        codes = {finding["code"] for finding in result["findings"]}
        expect(result["status"] == "blocked", "missing required term should block promotion", errors)
        expect("required_term_missing" in codes, "expected missing required term finding", errors)


def test_shell_wrapper_residue_blocks(errors: list[str]) -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        skills_dir = Path(tmpdir) / "skills"
        body = minimal_good_task_intake_body() + "\nExit code: 0\nWall time: 1 second\nOutput:\n"
        write_skill(skills_dir, "task-intake-contract", body)
        result = module.audit_skill(skills_dir, "task-intake-contract", module.CORE_CONTRACTS["task-intake-contract"])
        codes = {finding["code"] for finding in result["findings"]}
        expect(result["status"] == "blocked", "shell wrapper residue should block promotion", errors)
        expect("shell_output_wrapper_residue" in codes, "expected shell wrapper finding", errors)


def test_mojibake_residue_blocks(errors: list[str]) -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        skills_dir = Path(tmpdir) / "skills"
        body = minimal_good_task_intake_body() + "\nTier 1 â€” bad encoding\n"
        write_skill(skills_dir, "task-intake-contract", body)
        result = module.audit_skill(skills_dir, "task-intake-contract", module.CORE_CONTRACTS["task-intake-contract"])
        codes = {finding["code"] for finding in result["findings"]}
        expect(result["status"] == "blocked", "mojibake residue should block promotion", errors)
        expect("mojibake_residue" in codes, "expected mojibake finding", errors)


def main() -> int:
    errors: list[str] = []
    for test in (
        test_current_workspace_core_audit_ok,
        test_missing_required_term_blocks,
        test_shell_wrapper_residue_blocks,
        test_mojibake_residue_blocks,
    ):
        try:
            test(errors)
        except Exception as exc:
            errors.append(f"{test.__name__} raised {type(exc).__name__}: {exc}")
    if errors:
        for error in errors:
            print(f"FAIL: {error}")
        return 1
    print("ok: skill_core_proof_tier_audit tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
