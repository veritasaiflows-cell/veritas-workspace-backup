from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "otel_tool_workflow_metadata.py"
TMP = ROOT / "tmp" / "test-otel-tool-workflow-metadata"


def expect(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def main() -> int:
    errors: list[str] = []
    lane_register = TMP / "lanes.json"
    wf74_runner = TMP / "wf74-runner.json"
    cron_runner = TMP / "telegram-runner.json"
    cron_ledger = TMP / "cron-ledger.json"
    out = TMP / "out.json"
    write_json(
        lane_register,
        {
            "lanes": [
                {
                    "lane_id": "WF74::sample",
                    "workflow_id": "WF74",
                    "workstream_id": "sample",
                    "owner": "main",
                    "status": "complete",
                    "acceptance_commands": ["python scripts\\sample_validator.py --validate"],
                    "proof_artifacts": ["tmp/sample.json"],
                    "allowed_writes": ["tmp/sample.json"],
                    "runtime": {
                        "session_id": "2596",
                        "session_key": "telegram:8650152206",
                        "session_label": "telegram-direct",
                        "model_path": "openai/gpt-5.5",
                    },
                }
            ]
        },
    )
    write_json(
        wf74_runner,
        {
            "steps": [
                {
                    "name": "otel_ops_control",
                    "command": ["python", "scripts\\otel_ops_control.py", "--validate"],
                    "status": "ok",
                    "returncode": 0,
                    "duration_ms": 123.4,
                    "stdout_tail": "redacted presence only",
                }
            ]
        },
    )
    write_json(
        cron_runner,
        {
            "steps": [
                {
                    "name": "wf74_learning_loop_telegram_digest",
                    "command": ["python", "scripts\\wf74_learning_loop_telegram_digest.py", "--validate"],
                    "ok": True,
                    "returncode": 0,
                }
            ]
        },
    )
    write_json(
        cron_ledger,
        {
            "jobs": [
                {"id": "1", "name": "Ops - OTEL Local Digest", "enabled": True, "status": "fresh", "schedule": {"expr": "40 7 * * *"}}
            ]
        },
    )
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--lane-register",
            str(lane_register),
            "--wf74-runner",
            str(wf74_runner),
            "--cron-runner",
            str(cron_runner),
            "--cron-ledger",
            str(cron_ledger),
            "--json-out",
            str(out),
            "--write",
            "--validate",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    expect(result.returncode == 0, f"metadata command failed: {result.stdout} {result.stderr}", errors)
    payload = json.loads(out.read_text(encoding="utf-8"))
    expect(payload.get("schema") == "veritas.otel_tool_workflow_metadata.v1", "schema mismatch", errors)
    expect(payload.get("validation", {}).get("status") == "ok", "validation should be ok", errors)
    expect(payload.get("privacy_scan", {}).get("status") == "ok", "privacy scan should pass", errors)
    summary = payload.get("summary", {})
    expect(summary.get("row_count", 0) >= 4, "expected rows from lane, runner, cron runner, and cron ledger", errors)
    expect(summary.get("session_attributed_count", 0) > 0, "session attribution should be counted", errors)
    expect(summary.get("workflow_attributed_count", 0) > 0, "workflow attribution should be counted", errors)
    boundary = payload.get("authority_boundary", {})
    for flag in (
        "collector_config_mutation_allowed",
        "runtime_config_mutation_allowed",
        "cron_schedule_mutation_allowed",
        "raw_prompt_capture_allowed",
        "raw_response_capture_allowed",
        "tool_payload_capture_allowed",
        "secret_or_header_capture_allowed",
        "finance_canon_or_portfolio_mutation_allowed",
        "paper_or_live_execution_allowed",
        "owner_approval_inferred",
    ):
        expect(boundary.get(flag) is False, f"authority flag must be false: {flag}", errors)
    for row in payload.get("rows", []):
        expect(row.get("payload_capture") is False, "payload_capture must stay false", errors)
        expect("stdout_tail" not in row and "stderr_tail" not in row, "raw output tails must not be stored", errors)
        expect("command" not in row, "raw command list must not be stored", errors)
    if errors:
        for error in errors:
            print(f"FAIL: {error}")
        return 1
    print("ok: otel tool workflow metadata is bounded")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
