#!/usr/bin/env python3
"""Focused tests for WF74 response self-review sampler."""
from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory

import wf74_response_self_review_sampler as sampler


def write_json(path: Path, payload: dict) -> Path:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return path


def clean_eval_payload() -> dict:
    return {
        "status": "ok",
        "summary": {
            "case_count": 18,
            "passed_count": 18,
            "failed_count": 0,
            "state_counts": {"skill_proposal": 4},
            "dispatch_destination_counts": {"skill_workshop_proposal": 2},
        },
        "results": [
            {
                "case_id": "active_self_review_skill_gap_routes_to_skill_proposal",
                "passed": True,
                "actual_action_state": "skill_proposal",
            },
            {
                "case_id": "wf74_dispatch_active_self_review_skill_gap_to_skill_workshop",
                "passed": True,
                "actual_action_state": "skill_proposal",
                "actual_dispatch_destination": "skill_workshop_proposal",
                "dispatch_direct_apply_allowed": False,
                "dispatch_direct_skill_write_allowed": False,
            },
        ],
        "validation": {"status": "ok", "errors": [], "warnings": []},
    }


def clean_response_lint_payload() -> dict:
    return {
        "status": "ok",
        "summary": {
            "text_count": 0,
            "blocked_count": 0,
            "warning_count": 0,
            "ok_count": 0,
        },
        "self_test": {"status": "ok"},
        "validation": {"status": "ok", "errors": [], "warnings": []},
    }


def clean_docket_payload() -> dict:
    return {
        "status": "ok",
        "summary": {
            "row_count": 10,
            "active_action_count": 0,
            "fix_now_count": 0,
            "hard_stop_count": 0,
            "market_session_accrual_count": 5,
            "monitor_only_count": 5,
            "next_safe_action": "No active implementation action.",
        },
        "authority_boundary": {
            "auto_apply_allowed": False,
            "skill_application_allowed": False,
            "cron_schedule_mutation_allowed": False,
            "owner_approval_inferred": False,
        },
        "validation": {"status": "ok", "errors": [], "warnings": []},
    }


def write_clean_inputs(root: Path) -> dict[str, Path]:
    eval_path = write_json(root / "eval.json", clean_eval_payload())
    lint_path = write_json(root / "lint.json", clean_response_lint_payload())
    docket_path = write_json(root / "docket.json", clean_docket_payload())
    skill_path = root / "SKILL.md"
    skill_path.write_text("# Test\n\n## Active Post-Response Self-Review Trigger\n", encoding="utf-8")
    return {
        "eval": eval_path,
        "lint": lint_path,
        "docket": docket_path,
        "skill": skill_path,
    }


def build(paths: dict[str, Path]) -> dict:
    return sampler.build_payload(
        eval_harness_path=paths["eval"],
        response_lint_path=paths["lint"],
        docket_path=paths["docket"],
        skill_path=paths["skill"],
    )


def test_clean_metadata_warns_only_for_no_draft_sample() -> None:
    with TemporaryDirectory() as raw:
        paths = write_clean_inputs(Path(raw))
        payload = build(paths)
        assert payload["status"] == "warning", payload
        assert payload["summary"]["error_count"] == 0, payload
        assert payload["summary"]["cron_schedule_mutated"] is False, payload
        assert payload["authority_boundary"]["reads_raw_prompts"] is False, payload
        assert payload["cron_candidate"]["not_installed"] is True, payload
        warnings = {row["code"] for row in payload["findings"]}
        assert warnings == {"no_response_draft_sampled"}, payload


def test_missing_eval_case_blocks_sampler() -> None:
    with TemporaryDirectory() as raw:
        paths = write_clean_inputs(Path(raw))
        eval_payload = clean_eval_payload()
        eval_payload["results"] = eval_payload["results"][:1]
        write_json(paths["eval"], eval_payload)
        payload = build(paths)
        assert payload["status"] == "blocked", payload
        errors = {row["code"] for row in payload["findings"] if row["severity"] == "error"}
        assert "missing_required_eval_case" in errors, payload


def test_response_lint_failure_blocks_sampler() -> None:
    with TemporaryDirectory() as raw:
        paths = write_clean_inputs(Path(raw))
        lint_payload = clean_response_lint_payload()
        lint_payload["self_test"]["status"] = "blocked"
        write_json(paths["lint"], lint_payload)
        payload = build(paths)
        assert payload["status"] == "blocked", payload
        errors = {row["code"] for row in payload["findings"] if row["severity"] == "error"}
        assert "response_lint_self_test_not_ok" in errors, payload


def main() -> int:
    test_clean_metadata_warns_only_for_no_draft_sample()
    test_missing_eval_case_blocks_sampler()
    test_response_lint_failure_blocks_sampler()
    print("ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
