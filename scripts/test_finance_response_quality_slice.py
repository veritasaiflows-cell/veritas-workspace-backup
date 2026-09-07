from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "finance_response_quality_slice.py"
REPORT = ROOT / "tmp" / "finance-response-quality-slice.json"


def main() -> int:
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--write", "--write-md", "--validate"],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    errors: list[str] = []
    if result.returncode != 0:
        errors.append(f"command failed: {result.stdout} {result.stderr}")
    if not REPORT.is_file():
        errors.append("report missing")
    else:
        report = json.loads(REPORT.read_text(encoding="utf-8"))
        summary = report.get("summary", {})
        boundary = report.get("authority_boundary", {})
        if report.get("schema") != "veritas.finance_response_quality_slice.v1":
            errors.append("schema mismatch")
        if report.get("status") != "ok" or report.get("validation", {}).get("status") != "ok":
            errors.append("quality slice not green")
        if summary.get("alerts_os_answer_path_ok") is not True:
            errors.append("alerts OS answer path not green")
        if summary.get("blocked_archetype_count") != 0:
            errors.append("blocked archetypes present")
        if float(summary.get("average_quality_score") or 0) < 0.8:
            errors.append("average score below threshold")
        if summary.get("ticker_count") != 18:
            errors.append("expected 18 high-attention tickers")
        if report.get("privacy_scan", {}).get("status") != "ok":
            errors.append("privacy scan failed")
        for key in (
            "customer_or_public_output_allowed",
            "external_delivery_allowed",
            "raw_prompt_or_response_capture_allowed",
            "writes_finance_canon",
            "maintains_account_or_capital_state",
            "maintains_order_or_execution_state",
            "maintains_simulated_account_state",
            "capital_or_order_authority",
            "paper_or_live_execution_allowed",
            "brokerage_or_account_action_allowed",
            "owner_approval_inferred",
        ):
            if boundary.get(key) is not False:
                errors.append(f"authority flag must be false: {key}")
        expected = {
            "ticker_alert_answer",
            "recommendation_review_answer",
            "technical_context_answer",
            "macro_signal_warning_answer",
            "risk_invalidation_answer",
            "staleness_refusal_answer",
            "routing_boundary_answer",
        }
        actual = {row.get("archetype_id") for row in report.get("archetypes", [])}
        if actual != expected:
            errors.append(f"archetype mismatch: {sorted(actual)}")

    if errors:
        for error in errors:
            print(f"FAIL: {error}")
        return 1
    print("finance response quality slice tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
