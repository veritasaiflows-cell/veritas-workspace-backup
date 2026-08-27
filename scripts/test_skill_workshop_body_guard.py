#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "skill_workshop_body_guard.py"


def load_module():
    spec = importlib.util.spec_from_file_location("skill_workshop_body_guard", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write_skill(path: Path, name: str, title: str, sections: list[str]) -> None:
    body = [
        "---",
        f'name: "{name}"',
        'description: "test skill"',
        "---",
        "",
        f"# {title}",
        "",
        "Use this skill for a realistic test body with enough content to avoid short-body warnings.",
        "",
    ]
    for section in sections:
        body.extend([
            f"## {section}",
            "",
            "- This section preserves important operational guidance.",
            "- This section has enough detail for body preservation checks.",
            "",
        ])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(body), encoding="utf-8")


def expect(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def test_live_scan_flags_proposed_update_wrapper(errors: list[str]) -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        skill_path = root / "skills" / "thin-skill" / "SKILL.md"
        write_skill(skill_path, "thin-skill", "Proposed Update: Thin Skill", ["Goal", "Preserve"])
        payload = module.build_payload(skills_dir=root / "skills")
        codes = {finding["code"] for finding in payload["validation"]["errors"]}
        expect(payload["status"] == "error", "live proposed-update wrapper should fail", errors)
        expect("live_proposed_update_wrapper" in codes, "expected live wrapper error", errors)


def test_pair_flags_thin_preserve_addendum(errors: list[str]) -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        live = root / "live.md"
        proposal = root / "proposal.md"
        write_skill(live, "qa-skill", "QA Skill", ["Purpose", "Steps", "Validation", "Closeout"])
        proposal.write_text(
            "\n".join([
                "---",
                'name: "qa-skill"',
                "---",
                "",
                "# Proposed Update: QA Skill Heading Hygiene",
                "",
                "## Goal",
                "",
                "Preserve existing behavior while adding headings.",
                "",
            ]),
            encoding="utf-8",
        )
        payload = module.build_payload(skills_dir=root / "empty", live_skill=live, proposal_file=proposal)
        codes = {finding["code"] for finding in payload["validation"]["errors"]}
        expect(payload["status"] == "error", "thin preserve addendum should fail", errors)
        expect("proposal_proposed_update_wrapper" in codes, "expected proposed-update proposal error", errors)
        expect("proposal_body_materially_shorter_than_live" in codes, "expected short-body error", errors)
        expect("proposal_preserve_claim_missing_live_headings" in codes, "expected preserve-heading error", errors)


def test_pair_accepts_full_body_merge(errors: list[str]) -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        live = root / "live.md"
        proposal = root / "proposal.md"
        sections = ["Purpose", "Steps", "Validation", "Closeout"]
        write_skill(live, "qa-skill", "QA Skill", sections)
        write_skill(proposal, "qa-skill", "QA Skill", sections + ["Stop Lines"])
        payload = module.build_payload(skills_dir=root / "empty", live_skill=live, proposal_file=proposal)
        expect(payload["status"] == "ok", f"full body merge should pass: {payload['validation']}", errors)
        expect(payload["pair_result"]["proposal_to_live_word_ratio"] >= 1.0, "full merge should not shrink body", errors)


def test_current_workspace_live_scan_is_not_error(errors: list[str]) -> None:
    module = load_module()
    payload = module.build_payload(skills_dir=ROOT / "skills")
    expect(payload["summary"]["live_error_count"] == 0, f"workspace live skills should have no body-replacement errors: {payload['validation']['errors'][:3]}", errors)


def main() -> int:
    errors: list[str] = []
    for test in (
        test_live_scan_flags_proposed_update_wrapper,
        test_pair_flags_thin_preserve_addendum,
        test_pair_accepts_full_body_merge,
        test_current_workspace_live_scan_is_not_error,
    ):
        try:
            test(errors)
        except Exception as exc:
            errors.append(f"{test.__name__} raised {type(exc).__name__}: {exc}")
    if errors:
        for error in errors:
            print(f"FAIL: {error}")
        return 1
    print("ok: skill_workshop_body_guard tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
