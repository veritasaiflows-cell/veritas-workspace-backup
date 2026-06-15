from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "otel_learning_loop.py"


def expect(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def main() -> int:
    errors: list[str] = []
    out = ROOT / "tmp" / "test-otel-learning-loop.json"
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--json-out", str(out), "--write", "--validate"],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    expect(result.returncode == 0, f"script failed: {result.stdout} {result.stderr}", errors)
    payload = json.loads(out.read_text(encoding="utf-8"))
    expect(payload.get("schema") == "veritas.otel_learning_loop.v1", "schema mismatch", errors)
    expect(payload.get("validation", {}).get("status") == "ok", "validation should be ok", errors)
    expect(payload.get("privacy_scan", {}).get("status") == "ok", "privacy scan should be ok", errors)
    boundary = payload.get("authority_boundary", {})
    for flag in (
        "raw_prompt_capture_allowed",
        "raw_response_capture_allowed",
        "tool_payload_capture_allowed",
        "system_prompt_capture_allowed",
        "secret_or_header_capture_allowed",
        "content_capture_allowed",
        "external_export_allowed",
        "collector_config_mutation_allowed",
        "runtime_config_mutation_allowed",
        "cron_schedule_mutation_allowed",
        "paper_or_live_execution_allowed",
        "owner_approval_inferred",
    ):
        expect(boundary.get(flag) is False, f"boundary must stay false: {flag}", errors)
    blocked = payload.get("redaction_policy", {}).get("blocked", [])
    expect("raw prompts" in blocked, "raw prompts must be blocked", errors)
    expect("system prompts" in blocked, "system prompts must be blocked", errors)
    recommendations = payload.get("recommendations", [])
    expect(any(item.get("id") == "content_capture_boundary" for item in recommendations), "content boundary recommendation missing", errors)
    if errors:
        for error in errors:
            print(f"FAIL: {error}")
        return 1
    print("ok: otel learning loop is metadata-only")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
