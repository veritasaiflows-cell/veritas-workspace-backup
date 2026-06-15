from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "improvement_ledger.py"


def expect(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    errors: list[str] = []
    out = ROOT / "tmp" / "test-improvement-ledger-current.json"
    md = ROOT / "tmp" / "test-improvement-ledger-current.md"
    ledger = ROOT / "tmp" / "test-improvement-ledger.jsonl"
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
    expect(payload.get("schema") == "veritas.improvement_ledger_current.v1", "schema mismatch", errors)
    expect(payload.get("validation", {}).get("status") == "ok", "validation should be ok", errors)
    expect(payload.get("privacy_scan", {}).get("status") == "ok", "privacy scan should be ok", errors)
    summary = payload.get("summary", {})
    expect(summary.get("latest_open_count", 0) > 0, "expected open improvements", errors)
    expect(summary.get("appended_event_count", 0) > 0, "expected first run to append events", errors)
    boundary = payload.get("authority_boundary", {})
    for flag in (
        "code_mutation_allowed",
        "skill_application_allowed",
        "collector_config_mutation_allowed",
        "runtime_config_mutation_allowed",
        "cron_schedule_mutation_allowed",
        "finance_canon_or_portfolio_mutation_allowed",
        "capital_deployment_allowed",
        "paper_or_live_execution_allowed",
        "brokerage_or_account_action_allowed",
        "owner_approval_inferred",
    ):
        expect(boundary.get(flag) is False, f"boundary must stay false: {flag}", errors)
    expect(boundary.get("append_only") is True, "append_only must stay true", errors)
    expect(ledger.exists(), "ledger file missing", errors)
    first_line_count = len([line for line in ledger.read_text(encoding="utf-8").splitlines() if line.strip()])

    second = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True)
    expect(second.returncode == 0, f"second run failed: {second.stdout} {second.stderr}", errors)
    second_payload = load_json(out)
    expect(second_payload.get("summary", {}).get("appended_event_count") == 0, "second run should be idempotent for same source snapshot", errors)
    second_line_count = len([line for line in ledger.read_text(encoding="utf-8").splitlines() if line.strip()])
    expect(first_line_count == second_line_count, "idempotent run changed ledger length", errors)
    expect(md.exists(), "markdown output missing", errors)

    check_out = ROOT / "tmp" / "test-improvement-ledger-check.json"
    check_cmd = [
        sys.executable,
        str(SCRIPT),
        "--check",
        "--write",
        "--validate",
        "--json-out",
        str(check_out),
        "--ledger-out",
        str(ledger),
    ]
    check = subprocess.run(check_cmd, cwd=ROOT, text=True, capture_output=True)
    expect(check.returncode == 0, f"check run failed: {check.stdout} {check.stderr}", errors)
    check_payload = load_json(check_out)
    expect(check_payload.get("mode") == "check", "check run should declare check mode", errors)
    expect(check_payload.get("summary", {}).get("appended_event_count") == 0, "check run must not append events", errors)
    check_line_count = len([line for line in ledger.read_text(encoding="utf-8").splitlines() if line.strip()])
    expect(second_line_count == check_line_count, "check run changed ledger length", errors)
    expect("overdue_open_count" in check_payload.get("summary", {}), "SLA overdue count missing", errors)
    expect("escalation_level" in check_payload.get("summary", {}), "SLA escalation level missing", errors)

    if errors:
        for error in errors:
            print(f"FAIL: {error}")
        return 1
    print("ok: improvement ledger is append-only, idempotent per source snapshot, and bounded")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
