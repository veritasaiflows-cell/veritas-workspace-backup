from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "finance_response_quality_slice.py"
REPORT = ROOT / "tmp" / "finance-response-quality-slice.json"


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
    expect(result.returncode == 0, f"finance response quality command failed: {result.stdout} {result.stderr}", errors)
    expect(REPORT.exists(), "finance response quality report missing", errors)
    if REPORT.exists():
        report = json.loads(REPORT.read_text(encoding="utf-8"))
        expect(report.get("schema") == "veritas.finance_response_quality_slice.v1", "schema mismatch", errors)
        expect(report.get("validation", {}).get("status") == "ok", "validation should be ok", errors)
        expect(report.get("privacy_scan", {}).get("status") == "ok", "privacy scan should be ok", errors)
        boundary = report.get("authority_boundary", {})
        for flag in (
            "customer_or_public_saas_output_allowed",
            "real_customer_data_allowed",
            "external_delivery_allowed",
            "raw_chat_or_prompt_capture_allowed",
            "raw_tool_payload_capture_allowed",
            "canon_or_portfolio_mutation_allowed",
            "capital_deployment_approved",
            "trade_or_execution_approved",
            "paper_or_live_execution_allowed",
            "brokerage_or_account_action_allowed",
            "owner_approval_inferred",
            "wf72_finance_answer_front_door_allowed",
        ):
            expect(boundary.get(flag) is False, f"authority flag must be false: {flag}", errors)
        summary = report.get("summary", {})
        expect(summary.get("wf84_wf85_answer_path_ok") is True, "WF84/WF85 answer path should be ok", errors)
        expect(summary.get("wf72_support_only_confirmed") is True, "WF72 support-only status should be confirmed", errors)
        expect(summary.get("wf75_internal_service_slice_only") is True, "WF75 slice must remain internal-only", errors)
        expect(summary.get("sector_timing_warning_available") is True, "sector timing warning fields should be available", errors)
        expect(summary.get("blocked_archetype_count") == 0, "no archetype should be blocked", errors)
        expect(float(summary.get("average_quality_score") or 0) >= 0.8, "average score should be at least 0.8", errors)
        archetype_ids = {row.get("archetype_id") for row in report.get("archetypes", [])}
        for archetype in (
            "ticker_trade_grade_answer",
            "capital_deployment_answer",
            "sector_allocation_answer",
            "technical_timing_warning_answer",
            "macro_signal_warning_answer",
            "risk_invalidation_answer",
            "staleness_refusal_answer",
            "routing_boundary_answer",
        ):
            expect(archetype in archetype_ids, f"missing archetype: {archetype}", errors)
        expect(summary.get("negative_canary_count") == summary.get("negative_canary_pass_count"), "all negative canaries should pass", errors)
        expect(summary.get("negative_canary_count", 0) >= 6, "guard/coverage negative canaries should be present", errors)
        expect(summary.get("remediation_track_count", 0) >= 2, "remediation tracks should be present", errors)
        expect(summary.get("section_coverage_status") in {"ok", "warning"}, "section coverage status should be explicit", errors)
        expect("technical_posture_missing_both_count" in summary, "technical posture coverage gap should be tracked", errors)
    if errors:
        for error in errors:
            print(f"FAIL: {error}")
        return 1
    print("ok: finance response quality slice is bounded")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
