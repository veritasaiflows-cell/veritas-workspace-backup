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


def minimal_good_model_routing_body() -> str:
    return """---
name: "veritas-model-routing-helper-lanes"
description: "test"
---

# Veritas Model Routing And Helper Lanes

## Purpose

Veritas main remains the queue owner, final integrator, QC owner, acceptance owner, finance truth surface, and user-facing judgment owner. A route changes capability and cost, never authority.

## Required Route Order

1. `model_free_command` — use when an explicit deterministic command and proof are both available.
2. `codex_native_subagent` — native rollout provenance must remain `codex_native_subagent`; a later update cannot relabel it.
3. `persistent_isolated_agent` — resolve stable IDs through `scripts/agent_fleet_policy.py` with fresh strict agent-matched transport proof; model-family substitution blocks dispatch.

## Role And Model Contract

Engineering Builder is Muse Spark 1.3 Contributor for code implementation, including one-file fixes. Finance Evidence and Knowledge and Continuity run GLM 5.3 Flash. Engineering QA and independent review run GLM 5.3. Main integration, acceptance, and authority-sensitive judgment use Grok 4.6. Review cannot use the patch-author model. Verify actual model and runtime per task; aliases are not provenance. Command-backed deterministic work stays model-free.

## Boundaries

Stop lines: stop when transport, model, lease, or scope proof is missing, stale, or mismatched. Helpers never execute paper/live trades, act on brokerage/account state, move money, or infer owner approval. Closeout records authoritative usage or `provider_usage_unavailable`, route conformance, and Main acceptance.

## Procedure

This body contains enough words to represent a real routing skill contract. The validator should accept it only when all required role, model, authority, and boundary anchors remain present. This text is intentionally compact but above the minimum word count because the real validator should fail thin placeholder skills that would otherwise look structurally valid while lacking role discipline, route order, and authority language.
"""


def test_current_workspace_model_routing_skill_ok(errors: list[str]) -> None:
    module = load_module()
    result = module.audit_skill(
        ROOT / "skills",
        "veritas-model-routing-helper-lanes",
        module.CORE_CONTRACTS["veritas-model-routing-helper-lanes"],
    )
    expect(
        result["status"] == "ok",
        f"live routing skill should pass the updated contract: {result['findings'][:3]}",
        errors,
    )


def test_model_routing_role_omission_blocks(errors: list[str]) -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        skills_dir = Path(tmpdir) / "skills"
        body = minimal_good_model_routing_body().replace(
            "Muse Spark 1.3 Contributor", "a generic coding model"
        )
        write_skill(skills_dir, "veritas-model-routing-helper-lanes", body)
        result = module.audit_skill(
            skills_dir,
            "veritas-model-routing-helper-lanes",
            module.CORE_CONTRACTS["veritas-model-routing-helper-lanes"],
        )
        codes = {finding["code"] for finding in result["findings"]}
        expect(result["status"] == "blocked", "omitting the builder role should block promotion", errors)
        expect("required_term_missing" in codes, "expected missing required term finding", errors)


def test_model_routing_patch_author_review_permitted_blocks(errors: list[str]) -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        skills_dir = Path(tmpdir) / "skills"
        body = minimal_good_model_routing_body().replace(
            "Review cannot use the patch-author model",
            "Review may use the patch-author model",
        )
        write_skill(skills_dir, "veritas-model-routing-helper-lanes", body)
        result = module.audit_skill(
            skills_dir,
            "veritas-model-routing-helper-lanes",
            module.CORE_CONTRACTS["veritas-model-routing-helper-lanes"],
        )
        codes = {finding["code"] for finding in result["findings"]}
        expect(
            result["status"] == "blocked",
            "permitting patch-author review should block promotion",
            errors,
        )
        expect("required_group_missing" in codes, "expected missing required contract group finding", errors)


def test_model_routing_model_substitution_permitted_blocks(errors: list[str]) -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        skills_dir = Path(tmpdir) / "skills"
        body = minimal_good_model_routing_body().replace(
            "model-family substitution blocks dispatch",
            "model-family substitution is acceptable",
        )
        write_skill(skills_dir, "veritas-model-routing-helper-lanes", body)
        result = module.audit_skill(
            skills_dir,
            "veritas-model-routing-helper-lanes",
            module.CORE_CONTRACTS["veritas-model-routing-helper-lanes"],
        )
        codes = {finding["code"] for finding in result["findings"]}
        expect(
            result["status"] == "blocked",
            "permitting model-family substitution should block promotion",
            errors,
        )
        expect("required_group_missing" in codes, "expected missing required contract group finding", errors)


def test_current_workspace_core_audit_ok(errors: list[str]) -> None:
    module = load_module()
    payload = module.build_payload(ROOT / "skills")
    expect(payload["status"] == "ok", f"workspace core audit should pass: {payload['validation']['errors'][:3]}", errors)
    expect(payload["summary"]["audited_core_skill_count"] == 13, "expected 13 active core skills", errors)
    expect(payload["summary"]["tier2_local_proof_count"] == 13, "expected all active core skills to qualify", errors)

    candidates = set(module.CORE_CONTRACTS)
    retired = set(module.RETIRED_FORMER_CORE_CANDIDATES)
    expected_alerts_os_owners = {
        "veritas-entry-policy-opportunity-surface",
        "veritas-macro-pass",
        "veritas-post-earnings-sync",
    }
    expect(not candidates.intersection(retired), "retired compatibility tombstones must not be promotion candidates", errors)
    expect(expected_alerts_os_owners.issubset(candidates), "expected current alerts-OS owners in the core audit", errors)
    expect(
        set(payload["parameters"]["retired_former_core_candidates_excluded"]) == retired,
        "proof metadata should name the excluded former core candidates",
        errors,
    )


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


def test_retired_candidate_overlap_blocks(errors: list[str]) -> None:
    module = load_module()
    retired_skill = "wf67-paper-trading-operator"
    module.CORE_CONTRACTS[retired_skill] = module.CORE_CONTRACTS["veritas-macro-pass"]
    payload = module.build_payload(ROOT / "skills")
    codes = {finding["code"] for finding in payload["scope_findings"]}
    expect(payload["status"] == "blocked", "retired promotion-candidate overlap should block the audit", errors)
    expect("retired_tombstone_is_promotion_candidate" in codes, "expected retired tombstone scope finding", errors)
    expect(retired_skill not in payload["tier2_promoted_skills"], "retired tombstone must never be promoted", errors)


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
        test_current_workspace_model_routing_skill_ok,
        test_missing_required_term_blocks,
        test_retired_candidate_overlap_blocks,
        test_shell_wrapper_residue_blocks,
        test_mojibake_residue_blocks,
        test_model_routing_role_omission_blocks,
        test_model_routing_patch_author_review_permitted_blocks,
        test_model_routing_model_substitution_permitted_blocks,
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
