from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "otel_runtime_metadata_probe.py"
TMP_LOG = ROOT / "tmp" / "test-otel-runtime-metadata-probe.log"
OUT = ROOT / "tmp" / "test-otel-runtime-metadata-probe.json"


def expect(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def run_probe(text: str) -> tuple[subprocess.CompletedProcess[str], dict]:
    TMP_LOG.parent.mkdir(parents=True, exist_ok=True)
    TMP_LOG.write_text(text, encoding="utf-8")
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--log", str(TMP_LOG), "--json-out", str(OUT), "--write", "--validate"],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    payload = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else {}
    return result, payload


def main() -> int:
    errors: list[str] = []
    ok_result, ok_payload = run_probe(
        """
        Name: openclaw.model_call.duration_ms
        Attributes: openclaw.provider="openai" openclaw.model="gpt-5.5"
        Name: openclaw.tool.execution.duration_ms
        Attributes: gen_ai.tool.name="shell_command" openclaw.tool.params.kind="metadata"
        Name: openclaw.provider.request_id_hash
        """
    )
    expect(ok_result.returncode == 0, f"expected ok probe: {ok_result.stdout} {ok_result.stderr}", errors)
    expect(ok_payload.get("validation", {}).get("status") == "ok", "ok probe validation should pass", errors)
    expect(ok_payload.get("status") == "ok", "ok probe status should be ok", errors)
    expect(ok_payload.get("summary", {}).get("allowed_field_count", 0) >= 3, "allowed fields not counted", errors)
    boundary = ok_payload.get("authority_boundary", {})
    for flag in (
        "external_export_allowed",
        "runtime_config_mutation_allowed",
        "raw_prompt_capture_allowed",
        "tool_payload_capture_allowed",
        "secret_or_header_capture_allowed",
        "model_ranking_claim_allowed",
        "paper_or_live_or_account_action_allowed",
        "owner_approval_inferred",
    ):
        expect(boundary.get(flag) is False, f"authority flag must be false: {flag}", errors)

    blocked_result, blocked_payload = run_probe(
        """
        Name: openclaw.model_call.duration_ms
        openclaw.content.prompt="raw user text"
        authorization="Bearer token-value"
        """
    )
    expect(blocked_result.returncode != 0, "blocked probe should fail validation", errors)
    expect(blocked_payload.get("status") == "blocked", "blocked probe status should be blocked", errors)
    expect(blocked_payload.get("summary", {}).get("raw_content_marker_count", 0) > 0, "raw marker not found", errors)
    expect(blocked_payload.get("summary", {}).get("secret_or_header_marker_count", 0) > 0, "secret marker not found", errors)

    if errors:
        for error in errors:
            print(f"FAIL: {error}")
        return 1
    print("ok: otel runtime metadata probe is bounded")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
