#!/usr/bin/env python3
"""Metadata-only sampler for the active WF74 response self-review trigger.

This script does not read chat transcripts, raw prompts, raw responses, hidden
reasoning, tool payloads, secrets, account data, or customer data. It samples
only local proof metadata that already exists in WF74/response-quality surfaces
and reports whether the active self-review loop is wired safely.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json


ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
DEFAULT_OUT = TMP / "wf74-response-self-review-sampler.json"
SCHEMA = "veritas.wf74_response_self_review_sampler.v1"

REQUIRED_EVAL_CASES = {
    "active_self_review_skill_gap_routes_to_skill_proposal": "skill_proposal",
    "wf74_dispatch_active_self_review_skill_gap_to_skill_workshop": "skill_workshop_proposal",
}

REQUIRED_SKILL_MARKER = "## Active Post-Response Self-Review Trigger"

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "metadata_only": True,
    "reads_raw_prompts": False,
    "reads_raw_responses": False,
    "reads_hidden_reasoning": False,
    "reads_tool_payloads": False,
    "captures_secrets_or_credentials": False,
    "captures_customer_or_account_data": False,
    "sends_messages": False,
    "applies_skill_proposals": False,
    "cron_schedule_mutation_allowed": False,
    "config_auth_runtime_mutation_allowed": False,
    "finance_canon_or_portfolio_mutation_allowed": False,
    "cash_sizing_or_risk_mutation_allowed": False,
    "capital_deployment_allowed": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "owner_approval_inferred": False,
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def workspace_path(value: str | None, default: Path) -> Path:
    if not value:
        return default
    path = Path(value)
    return path if path.is_absolute() else ROOT / path


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def finding(severity: str, code: str, message: str, source: Path) -> dict[str, str]:
    return {
        "severity": severity,
        "code": code,
        "message": message,
        "source": rel(source),
    }


def result_by_case(eval_payload: dict[str, Any], case_id: str) -> dict[str, Any] | None:
    for row in eval_payload.get("results", []):
        if row.get("case_id") == case_id:
            return row
    return None


def check_eval_harness(path: Path) -> tuple[dict[str, Any], list[dict[str, str]]]:
    payload = load_json(path)
    findings: list[dict[str, str]] = []
    summary = payload.get("summary", {})

    if payload.get("status") != "ok":
        findings.append(finding("error", "eval_harness_not_ok", "WF74 eval harness status is not ok.", path))
    if payload.get("validation", {}).get("status") != "ok":
        findings.append(finding("error", "eval_harness_validation_not_ok", "WF74 eval harness validation is not ok.", path))

    case_results: dict[str, dict[str, Any]] = {}
    for case_id, expected in REQUIRED_EVAL_CASES.items():
        row = result_by_case(payload, case_id)
        if row is None:
            findings.append(finding("error", "missing_required_eval_case", f"Missing required eval case: {case_id}", path))
            continue
        case_results[case_id] = {
            "passed": bool(row.get("passed")),
            "actual_action_state": row.get("actual_action_state"),
            "actual_dispatch_destination": row.get("actual_dispatch_destination"),
            "dispatch_direct_apply_allowed": row.get("dispatch_direct_apply_allowed"),
            "dispatch_direct_skill_write_allowed": row.get("dispatch_direct_skill_write_allowed"),
        }
        if not row.get("passed"):
            findings.append(finding("error", "required_eval_case_failed", f"Required eval case failed: {case_id}", path))
        actual = row.get("actual_dispatch_destination") if case_id.startswith("wf74_dispatch_") else row.get("actual_action_state")
        if actual != expected:
            findings.append(
                finding(
                    "error",
                    "required_eval_case_wrong_route",
                    f"Required eval case {case_id} routed to {actual!r}, expected {expected!r}.",
                    path,
                )
            )
        if case_id.startswith("wf74_dispatch_"):
            if row.get("dispatch_direct_apply_allowed") is not False:
                findings.append(finding("error", "dispatch_direct_apply_not_false", f"{case_id} allows direct apply.", path))
            if row.get("dispatch_direct_skill_write_allowed") is not False:
                findings.append(finding("error", "dispatch_direct_skill_write_not_false", f"{case_id} allows direct skill write.", path))

    return {
        "path": rel(path),
        "status": payload.get("status"),
        "validation_status": payload.get("validation", {}).get("status"),
        "case_count": summary.get("case_count"),
        "passed_count": summary.get("passed_count"),
        "failed_count": summary.get("failed_count"),
        "dispatch_destination_counts": summary.get("dispatch_destination_counts", {}),
        "state_counts": summary.get("state_counts", {}),
        "required_cases": case_results,
    }, findings


def check_response_lint(path: Path) -> tuple[dict[str, Any], list[dict[str, str]]]:
    payload = load_json(path)
    findings: list[dict[str, str]] = []
    summary = payload.get("summary", {})

    if payload.get("status") != "ok":
        findings.append(finding("error", "response_lint_not_ok", "Response recommendation lint status is not ok.", path))
    if payload.get("validation", {}).get("status") != "ok":
        findings.append(finding("error", "response_lint_validation_not_ok", "Response recommendation lint validation is not ok.", path))
    if payload.get("self_test", {}).get("status") != "ok":
        findings.append(finding("error", "response_lint_self_test_not_ok", "Response recommendation lint self-test is not ok.", path))
    if summary.get("text_count", 0) == 0:
        findings.append(
            finding(
                "warning",
                "no_response_draft_sampled",
                "No response draft was linted in this sampler run; current proof is self-test and routing metadata only.",
                path,
            )
        )

    return {
        "path": rel(path),
        "status": payload.get("status"),
        "validation_status": payload.get("validation", {}).get("status"),
        "self_test_status": payload.get("self_test", {}).get("status"),
        "text_count": summary.get("text_count", 0),
        "blocked_count": summary.get("blocked_count", 0),
        "warning_count": summary.get("warning_count", 0),
        "ok_count": summary.get("ok_count", 0),
    }, findings


def check_docket(path: Path) -> tuple[dict[str, Any], list[dict[str, str]]]:
    payload = load_json(path)
    findings: list[dict[str, str]] = []
    summary = payload.get("summary", {})
    boundary = payload.get("authority_boundary", {})

    if payload.get("status") != "ok":
        findings.append(finding("error", "docket_not_ok", "WF74 decision docket status is not ok.", path))
    if payload.get("validation", {}).get("status") != "ok":
        findings.append(finding("error", "docket_validation_not_ok", "WF74 decision docket validation is not ok.", path))
    for field in ("auto_apply_allowed", "skill_application_allowed", "cron_schedule_mutation_allowed", "owner_approval_inferred"):
        if boundary.get(field) is not False:
            findings.append(finding("error", f"docket_{field}_not_false", f"WF74 docket boundary {field} is not false.", path))
    if summary.get("hard_stop_count", 0):
        findings.append(finding("error", "docket_hard_stop_present", "WF74 docket has hard-stop rows.", path))
    if summary.get("fix_now_count", 0):
        findings.append(finding("warning", "docket_fix_now_present", "WF74 docket has fix-now rows that should be handled before scheduling.", path))

    return {
        "path": rel(path),
        "status": payload.get("status"),
        "validation_status": payload.get("validation", {}).get("status"),
        "row_count": summary.get("row_count"),
        "active_action_count": summary.get("active_action_count"),
        "fix_now_count": summary.get("fix_now_count"),
        "hard_stop_count": summary.get("hard_stop_count"),
        "market_session_accrual_count": summary.get("market_session_accrual_count"),
        "monitor_only_count": summary.get("monitor_only_count"),
        "next_safe_action": summary.get("next_safe_action"),
    }, findings


def check_skill(path: Path) -> tuple[dict[str, Any], list[dict[str, str]]]:
    text = path.read_text(encoding="utf-8")
    findings: list[dict[str, str]] = []
    marker_present = REQUIRED_SKILL_MARKER in text
    if not marker_present:
        findings.append(finding("error", "active_self_review_skill_marker_missing", "Live skill is missing active self-review trigger.", path))
    return {
        "path": rel(path),
        "active_self_review_trigger_present": marker_present,
    }, findings


def build_payload(
    *,
    eval_harness_path: Path,
    response_lint_path: Path,
    docket_path: Path,
    skill_path: Path,
) -> dict[str, Any]:
    surfaces: dict[str, Any] = {}
    findings: list[dict[str, str]] = []

    for name, checker, path in (
        ("eval_harness", check_eval_harness, eval_harness_path),
        ("response_lint", check_response_lint, response_lint_path),
        ("decision_docket", check_docket, docket_path),
        ("live_skill", check_skill, skill_path),
    ):
        if not path.exists():
            findings.append(finding("error", f"{name}_missing", f"Required sampler input is missing: {rel(path)}", path))
            surfaces[name] = {"path": rel(path), "exists": False}
            continue
        surface, surface_findings = checker(path)
        surface["exists"] = True
        surfaces[name] = surface
        findings.extend(surface_findings)

    error_count = sum(1 for row in findings if row["severity"] == "error")
    warning_count = sum(1 for row in findings if row["severity"] == "warning")
    status = "blocked" if error_count else "warning" if warning_count else "ok"

    return {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": status,
        "purpose": "Metadata-only sampling of the active WF74 post-response self-review loop.",
        "summary": {
            "sampled_surface_count": len(surfaces),
            "error_count": error_count,
            "warning_count": warning_count,
            "blocked": error_count > 0,
            "cron_schedule_mutated": False,
            "next_safe_action": (
                "Fix blocked self-review proof before any sampler cron proposal."
                if error_count
                else "Manual sampler proof is usable; keep any schedule as owner-reviewed cron proposal until repeated clean runs."
            ),
        },
        "surfaces": surfaces,
        "findings": findings,
        "cron_candidate": {
            "review_only": True,
            "not_installed": True,
            "recommended_command": "python scripts\\wf74_response_self_review_sampler.py --write --validate",
            "expected_artifact": "tmp\\wf74-response-self-review-sampler.json",
            "suggested_cadence": "After substantive closeout batches or daily review, not after every message.",
            "promotion_requirements": [
                "At least two manual runs with error_count=0.",
                "Cron contract proposal with expected artifact and rollback notes.",
                "No raw prompt, response, hidden reasoning, or tool payload capture.",
                "Explicit Randall approval before cron schedule mutation.",
            ],
        },
        "top_recommendations": [
            {
                "priority": "P0",
                "action_class": "Auto-safe now" if not error_count else "Blocked",
                "recommendation": "Use the sampler as manual metadata proof after substantive closeout batches.",
                "why": "It confirms the live skill, eval harness, linter, and docket boundaries without reading raw transcripts.",
            },
            {
                "priority": "P1",
                "action_class": "Review-only",
                "recommendation": "Keep the cron candidate as a proposal until repeated manual proof is clean.",
                "why": "A clean script run is not schedule authority.",
            },
            {
                "priority": "P2",
                "action_class": "Owner-gated",
                "recommendation": "Promote to a low-frequency cron only after a cron contract diff and rollback note are reviewed.",
                "why": "Self-review automation should remain bounded and auditable before it becomes scheduled behavior.",
            },
        ],
        "authority_boundary": AUTHORITY_BOUNDARY,
        "validation": {
            "status": "error" if error_count else "warning" if warning_count else "ok",
            "errors": [f"{row['source']}:{row['code']}" for row in findings if row["severity"] == "error"],
            "warnings": [f"{row['source']}:{row['code']}" for row in findings if row["severity"] == "warning"],
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sample active WF74 response self-review proof metadata.")
    parser.add_argument("--eval-harness", default="tmp/wf74-learning-loop-eval-harness.json")
    parser.add_argument("--response-lint", default="tmp/response-recommendation-contract-lint.json")
    parser.add_argument("--docket", default="tmp/wf74-decision-docket.json")
    parser.add_argument("--skill", default="skills/veritas-self-improvement/SKILL.md")
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    payload = build_payload(
        eval_harness_path=workspace_path(args.eval_harness, TMP / "wf74-learning-loop-eval-harness.json"),
        response_lint_path=workspace_path(args.response_lint, TMP / "response-recommendation-contract-lint.json"),
        docket_path=workspace_path(args.docket, TMP / "wf74-decision-docket.json"),
        skill_path=workspace_path(args.skill, ROOT / "skills" / "veritas-self-improvement" / "SKILL.md"),
    )
    out = workspace_path(args.out, DEFAULT_OUT)
    if args.write:
        atomic_write_json(out, payload)

    print(json.dumps({
        "status": payload["status"],
        "summary": payload["summary"],
        "validation": payload["validation"],
        "write_result": {"out": rel(out)} if args.write else None,
    }, indent=2, sort_keys=True))
    if args.validate and payload["validation"]["status"] == "error":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
