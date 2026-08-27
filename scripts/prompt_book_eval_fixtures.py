#!/usr/bin/env python3
"""Build deterministic metadata-only eval fixtures for Prompt Book entries."""
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from prompt_book_common import (
    AUTHORITY_BOUNDARY,
    EVAL_FIXTURE_MD_PATH,
    EVAL_FIXTURE_PATH,
    ROOT,
    STATIC_PROMPT_ENTRIES,
    scan_forbidden,
    utc_now,
    write_json,
    write_text,
)

SCHEMA = "veritas.prompt_book.eval_fixtures.v1"

P0_FIXTURE_PROMPT_IDS = [
    "task-intake-contract-v1",
    "agi-harness-mode-v1",
    "finance-response-contract-v1",
    "helper-lane-contract-v1",
    "wf88-wiki-synthesis-contract-v1",
]

FIXTURE_PROMPT_IDS = [
    *P0_FIXTURE_PROMPT_IDS,
    "current-opportunity-approval-brief-v1",
    "question-route-catalog-v1",
    "question-route-usage-ledger-v1",
    "pm-control-intake-v1",
    "retail-truth-routing-stop-lines-v1",
    "smb-service-packet-v1",
]

REQUIRED_CHECKS = [
    "required fields present",
    "forbidden authority claims absent",
    "raw prompt/response/tool payload absent",
    "stop lines preserved",
]


def _entries_by_id() -> dict[str, dict[str, Any]]:
    return {
        entry["prompt_id"]: entry
        for entry in STATIC_PROMPT_ENTRIES
        if isinstance(entry, dict) and entry.get("prompt_id")
    }


def _fixture_for(entry: dict[str, Any]) -> dict[str, Any]:
    contract = entry.get("template_contract") or {}
    return {
        "fixture_id": f"fixture-{entry['prompt_id']}",
        "prompt_id": entry["prompt_id"],
        "fixture_status": "covered",
        "coverage_type": "deterministic_metadata_contract",
        "synthetic_source_packet": {
            "packet_id": f"synthetic-{entry['prompt_id']}",
            "source_type": "metadata_only_contract_probe",
            "contains_user_request_body": False,
            "contains_model_response_body": False,
            "contains_tool_io_body": False,
            "contains_sensitive_material": False,
            "authority_boundary_required": True,
        },
        "expected_output_required_fields": list(contract.get("output_schema") or []),
        "expected_checks": list(REQUIRED_CHECKS),
        "expected_stop_lines": list(entry.get("stop_lines") or []),
        "authority_assertions": dict(AUTHORITY_BOUNDARY),
        "proof_commands": [
            "python scripts\\prompt_book_eval_fixtures.py --write --write-md --validate",
            "python scripts\\test_prompt_book_eval_fixtures.py",
        ],
    }


def build_fixture_packet(root: Path = ROOT) -> dict[str, Any]:
    entries = _entries_by_id()
    fixtures: list[dict[str, Any]] = []
    missing_prompt_ids: list[str] = []
    for prompt_id in FIXTURE_PROMPT_IDS:
        entry = entries.get(prompt_id)
        if not entry:
            missing_prompt_ids.append(prompt_id)
            continue
        fixtures.append(_fixture_for(entry))

    covered_prompt_ids = [fixture["prompt_id"] for fixture in fixtures if fixture.get("fixture_status") == "covered"]
    packet = {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "ok",
        "summary": {
            "fixture_count": len(fixtures),
            "fixture_target_count": len(FIXTURE_PROMPT_IDS),
            "p0_target_count": len(P0_FIXTURE_PROMPT_IDS),
            "covered_prompt_ids": covered_prompt_ids,
            "missing_prompt_ids": missing_prompt_ids,
            "raw_capture_blocked": True,
            "prompt_text_stored": False,
            "next_safe_action": "Keep full prompt-book fixture coverage green; apply approved skill proposals only through Skill Workshop.",
        },
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "fixtures": fixtures,
    }
    packet["validation"] = validate_fixture_packet(packet, root=root)
    if packet["validation"]["status"] == "blocked":
        packet["status"] = "blocked"
    return packet


def validate_fixture_packet(packet: dict[str, Any], root: Path = ROOT) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []

    fixtures = packet.get("fixtures")
    if not isinstance(fixtures, list):
        errors.append("fixtures_missing")
        fixtures = []

    covered = {
        fixture.get("prompt_id")
        for fixture in fixtures
        if isinstance(fixture, dict) and fixture.get("fixture_status") == "covered"
    }
    missing_p0 = sorted(set(P0_FIXTURE_PROMPT_IDS) - covered)
    if missing_p0:
        errors.append("missing_p0_fixture_coverage:" + ",".join(missing_p0))
    missing_fixture_targets = sorted(set(FIXTURE_PROMPT_IDS) - covered)
    if missing_fixture_targets:
        errors.append("missing_fixture_coverage:" + ",".join(missing_fixture_targets))

    for fixture in fixtures:
        if not isinstance(fixture, dict):
            errors.append("fixture_not_object")
            continue
        prompt_id = fixture.get("prompt_id") or "unknown"
        checks = fixture.get("expected_checks") or []
        for check in REQUIRED_CHECKS:
            if check not in checks:
                errors.append(f"{prompt_id}:missing_required_check:{check}")
        source_packet = fixture.get("synthetic_source_packet") or {}
        for key in [
            "contains_user_request_body",
            "contains_model_response_body",
            "contains_tool_io_body",
            "contains_sensitive_material",
        ]:
            if source_packet.get(key) is not False:
                errors.append(f"{prompt_id}:source_packet_{key}_not_false")
        boundary = fixture.get("authority_assertions") or {}
        for key in [
            "raw_prompt_capture",
            "raw_response_capture",
            "tool_payload_capture",
            "secret_capture",
            "skill_auto_apply",
            "doctrine_auto_apply",
            "cron_schedule_mutation",
            "runtime_config_mutation",
            "finance_canon_portfolio_mutation",
            "capital_deployment",
            "paper_live_account_action",
            "external_delivery",
            "owner_approval_inference",
        ]:
            if boundary.get(key) is not False:
                errors.append(f"{prompt_id}:authority_boundary_not_false:{key}")

    summary = packet.get("summary") or {}
    if summary.get("prompt_text_stored") is not False:
        errors.append("summary_prompt_text_stored_not_false")
    if summary.get("raw_capture_blocked") is not True:
        errors.append("summary_raw_capture_blocked_not_true")

    forbidden = scan_forbidden(packet)
    if forbidden:
        errors.extend(forbidden)

    return {
        "status": "blocked" if errors else "ok",
        "errors": errors,
        "warnings": warnings,
        "error_count": len(errors),
        "warning_count": len(warnings),
    }


def render_markdown(packet: dict[str, Any]) -> str:
    summary = packet.get("summary") or {}
    lines = [
        "# Prompt Book Eval Fixtures",
        "",
        f"- Status: `{packet.get('status')}`",
        f"- Fixtures: `{summary.get('fixture_count')}`",
        f"- P0 targets: `{summary.get('p0_target_count')}`",
        "- Raw prompt/response/tool payload storage: `false`",
        "",
        "| Prompt ID | Fixture | Status |",
        "|---|---|---|",
    ]
    for fixture in packet.get("fixtures") or []:
        lines.append(
            f"| `{fixture.get('prompt_id')}` | `{fixture.get('fixture_id')}` | {fixture.get('fixture_status')} |"
        )
    lines.extend([
        "",
        "These fixtures are deterministic metadata probes. They assert output fields, authority boundaries, stop lines, and absence of raw capture; they do not store prompt or response bodies.",
    ])
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--write-md", action="store_true")
    parser.add_argument("--validate", action="store_true")
    args = parser.parse_args()

    packet = build_fixture_packet(ROOT)
    if args.write:
        write_json(EVAL_FIXTURE_PATH, packet)
    if args.write_md:
        write_text(EVAL_FIXTURE_MD_PATH, render_markdown(packet))
    print(
        f"status={packet['status']} fixtures={packet['summary']['fixture_count']} "
        f"validation={packet['validation']['status']}"
    )
    if args.validate and packet["validation"]["status"] == "blocked":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
