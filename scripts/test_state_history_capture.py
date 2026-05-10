from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[1]
SCRIPT = WORKSPACE / "scripts" / "state_history_capture.py"
TMP_OUT = WORKSPACE / "tmp" / "state-history-test.jsonl"


def run_cmd(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=WORKSPACE,
        text=True,
        capture_output=True,
    )


def expect(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def main() -> int:
    errors: list[str] = []
    if TMP_OUT.exists():
        TMP_OUT.unlink()

    sample = run_cmd(["sample", "--window", "post-close", "--output", str(TMP_OUT)])
    expect(sample.returncode == 0, f"sample command failed: {sample.stderr or sample.stdout}", errors)
    expect(not TMP_OUT.exists(), "sample command must not write output", errors)
    if sample.stdout.strip():
        row = json.loads(sample.stdout)
        expect(row.get("row_type") == "state_snapshot_v1", "sample row_type should be state_snapshot_v1", errors)
        expect(row.get("known_at_time"), "sample must contain known_at_time", errors)
        future = row.get("future_outcomes") or {}
        expect(future.get("owner_decision") is None, "owner decision must be future-only/empty", errors)
        expect(future.get("realized_outcomes") == [], "realized outcomes must start empty", errors)
        authority = row.get("authority") or {}
        for field in [
            "model_training_enabled",
            "model_driven_deployment_allowed",
            "canonical_note_mutation_allowed",
            "portfolio_mutation_allowed",
            "deployment_state_mutation_allowed",
            "trade_execution_allowed",
            "owner_approval_granted",
        ]:
            expect(authority.get(field) is False, f"authority.{field} must be false", errors)
        expect((row.get("provenance") or {}).get("source_artifacts"), "sample must include source provenance", errors)

    first = run_cmd(["append", "--window", "post-close", "--output", str(TMP_OUT)])
    expect(first.returncode == 0, f"first append failed: {first.stderr or first.stdout}", errors)
    before = TMP_OUT.read_text(encoding="utf-8") if TMP_OUT.exists() else ""
    second = run_cmd(["append", "--window", "post-close", "--output", str(TMP_OUT)])
    expect(second.returncode == 0, f"second append failed: {second.stderr or second.stdout}", errors)
    after = TMP_OUT.read_text(encoding="utf-8") if TMP_OUT.exists() else ""
    expect(after.startswith(before), "second append must preserve the original file prefix exactly", errors)
    rows = [json.loads(line) for line in after.splitlines() if line.strip()]
    expect(len(rows) == 2, "test history should contain exactly two appended rows", errors)
    expect(rows[0] != rows[1], "two appends should be distinct point-in-time rows", errors)

    validate = run_cmd(["validate", "--output", str(TMP_OUT)])
    expect(validate.returncode == 0, f"validate failed: {validate.stderr or validate.stdout}", errors)

    if errors:
        print("state_history_capture_tests_failed")
        for error in errors:
            print(f"- {error}")
        return 1
    print("state_history_capture_tests_passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
