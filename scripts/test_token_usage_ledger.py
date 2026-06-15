from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "token_usage_ledger.py"


def expect(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def line_count(path: Path) -> int:
    if not path.exists():
        return 0
    return len([line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()])


def main() -> int:
    errors: list[str] = []
    out = ROOT / "tmp" / "test-token-usage-ledger-current.json"
    md = ROOT / "tmp" / "test-token-usage-ledger-current.md"
    ledger = ROOT / "tmp" / "test-token-usage-ledger.jsonl"
    if ledger.exists():
        ledger.unlink()

    cmd = [
        sys.executable,
        str(SCRIPT),
        "--write",
        "--write-md",
        "--validate",
        "--json-out",
        str(out),
        "--md-out",
        str(md),
        "--ledger-out",
        str(ledger),
    ]
    first = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True)
    expect(first.returncode == 0, f"first run failed: {first.stdout} {first.stderr}", errors)
    payload = load_json(out)
    expect(payload.get("schema") == "veritas.token_usage_ledger_current.v1", "schema mismatch", errors)
    expect(payload.get("validation", {}).get("status") in {"ok", "warning"}, "validation should be ok or warning", errors)
    expect(payload.get("privacy_scan", {}).get("status") == "ok", "privacy scan should be ok", errors)
    summary = payload.get("summary", {})
    expect(summary.get("token_event_count", 0) > 0, "expected token-bearing rows", errors)
    expect(summary.get("total_tokens", 0) > 0, "expected positive token count", errors)
    expect(summary.get("cron_token_event_count", 0) > 0, "expected cron token attribution", errors)
    expect(payload.get("top_cron_jobs_by_tokens"), "top cron job ranking missing", errors)
    boundary = payload.get("authority_boundary", {})
    for flag in (
        "external_export_allowed",
        "raw_prompt_capture_allowed",
        "raw_response_capture_allowed",
        "tool_payload_capture_allowed",
        "system_prompt_capture_allowed",
        "secret_or_header_capture_allowed",
        "code_mutation_allowed",
        "cron_schedule_mutation_allowed",
        "runtime_config_mutation_allowed",
        "finance_canon_or_portfolio_mutation_allowed",
        "capital_deployment_allowed",
        "paper_or_live_execution_allowed",
        "brokerage_or_account_action_allowed",
        "owner_approval_inferred",
    ):
        expect(boundary.get(flag) is False, f"boundary must stay false: {flag}", errors)
    expect(boundary.get("append_only") is True, "append_only must stay true", errors)
    first_count = line_count(ledger)
    expect(first_count > 0, "ledger should have appended rows", errors)

    second_cmd = [part for part in cmd if part != "--write-md"]
    second = subprocess.run(second_cmd, cwd=ROOT, text=True, capture_output=True)
    expect(second.returncode == 0, f"second run failed: {second.stdout} {second.stderr}", errors)
    second_payload = load_json(out)
    expect(second_payload.get("summary", {}).get("appended_event_count") == 0, "second run should be idempotent for same source snapshot", errors)
    expect(line_count(ledger) == first_count, "idempotent run changed ledger length", errors)
    expect(md.exists(), "markdown output missing", errors)

    if errors:
        for error in errors:
            print(f"FAIL: {error}")
        return 1
    print("ok: token usage ledger is metadata-only and idempotent per source snapshot")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
