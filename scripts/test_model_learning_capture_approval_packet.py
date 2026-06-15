from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "model_learning_capture_approval_packet.py"
REPORT = ROOT / "tmp" / "model-learning-capture-approval-packet.json"


def expect(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def main() -> int:
    errors: list[str] = []
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--write", "--write-md", "--validate"],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    expect(result.returncode == 0, f"packet command failed: {result.stdout} {result.stderr}", errors)
    expect(REPORT.exists(), "approval packet JSON missing", errors)
    if REPORT.exists():
        packet = json.loads(REPORT.read_text(encoding="utf-8"))
        expect(packet.get("schema") == "veritas.model_learning_capture_approval_packet.v1", "schema mismatch", errors)
        expect(packet.get("validation", {}).get("status") == "ok", "validation should be ok", errors)
        boundary = packet.get("authority_boundary", {})
        for flag in (
            "external_export_allowed",
            "raw_prompt_capture_allowed",
            "raw_response_capture_allowed",
            "tool_payload_capture_allowed",
            "system_prompt_capture_allowed",
            "secret_or_header_capture_allowed",
            "base_model_self_modification_allowed",
            "model_ranking_claim_allowed_now",
            "investment_correctness_from_runtime_metrics_allowed",
            "canon_or_portfolio_mutation_allowed",
            "paper_or_live_or_account_action_allowed",
            "owner_approval_inferred",
        ):
            expect(boundary.get(flag) is False, f"authority flag must remain false: {flag}", errors)
        domains = {row.get("domain") for row in packet.get("capture_plan_after_explicit_approval_only", [])}
        for domain in {"model", "tools", "failures", "coding"}:
            expect(domain in domains, f"missing capture domain: {domain}", errors)
        for row in packet.get("capture_plan_after_explicit_approval_only", []):
            expect(row.get("payload_capture") is False, f"payload capture must be false: {row.get('domain')}", errors)
        tracks = {row.get("track") for row in packet.get("scoring_tracks", [])}
        for track in {"implementation_quality", "performance", "tool_reliability", "decision_quality"}:
            expect(track in tracks, f"missing scoring track: {track}", errors)
        approval_language = packet.get("approval_language", "")
        expect("Raw prompts" in approval_language, "approval language must explicitly mention raw prompts", errors)
        expect("remain blocked" in approval_language, "approval language must preserve blocked boundary", errors)
    if errors:
        for error in errors:
            print(f"FAIL: {error}")
        return 1
    print("ok: model learning capture approval packet is bounded")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
