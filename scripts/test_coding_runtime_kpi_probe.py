from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "coding_runtime_kpi_probe.py"
REPORT = ROOT / "tmp" / "coding-runtime-kpi-probe.json"


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
    expect(result.returncode == 0, f"probe failed: {result.stdout} {result.stderr}", errors)
    expect(REPORT.exists(), "coding runtime report missing", errors)
    if REPORT.exists():
        report = json.loads(REPORT.read_text(encoding="utf-8"))
        expect(report.get("schema") == "veritas.coding_runtime_kpi_probe.v1", "schema mismatch", errors)
        expect(report.get("validation", {}).get("status") == "ok", "validation should be ok", errors)
        expect(report.get("git_metadata", {}).get("captures_raw_diff") is False, "raw diff capture must be false", errors)
        kpis = report.get("kpis", {})
        for field in (
            "changed_path_count",
            "recommended_budget",
            "validator_failed_count",
            "closeout_failed_count",
            "first_pass_validation_clean",
            "rework_required",
            "failure_bucket_counts",
            "coding_outcome_ledger_rows",
            "coding_outcome_session_attributed_count",
            "coding_outcome_validator_proxy_passed_count",
            "coding_outcome_total_retry_count",
        ):
            expect(field in kpis, f"missing KPI field: {field}", errors)
        boundary = report.get("authority_boundary", {})
        for flag in (
            "external_export_allowed",
            "raw_diff_capture_allowed",
            "raw_file_content_capture_allowed",
            "raw_prompt_capture_allowed",
            "raw_response_capture_allowed",
            "tool_payload_capture_allowed",
            "secret_or_header_capture_allowed",
            "model_ranking_claim_allowed",
            "investment_correctness_from_runtime_metrics_allowed",
            "paper_or_live_or_account_action_allowed",
            "owner_approval_inferred",
        ):
            expect(boundary.get(flag) is False, f"authority flag must be false: {flag}", errors)
    if errors:
        for error in errors:
            print(f"FAIL: {error}")
        return 1
    print("ok: coding runtime KPI probe is bounded")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
