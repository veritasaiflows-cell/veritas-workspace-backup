from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "wf74_rsi.py"
REPORT = ROOT / "tmp" / "wf74-outcome-eval-suite-v2.json"
EXPECTED_CATEGORIES = 17
EXPECTED_FIXTURES = 34


def expect(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def main() -> int:
    errors: list[str] = []
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--outcome-eval-v2"],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    expect(result.returncode == 0, f"outcome eval command failed: {result.stdout} {result.stderr}", errors)
    expect(REPORT.exists(), "outcome eval report missing", errors)
    if REPORT.exists():
        report = json.loads(REPORT.read_text(encoding="utf-8"))
        expect(report.get("status") == "ok", f"expected ok report, got {report.get('status')}", errors)
        expect(report.get("posture") == "validate_only_report_only", "report posture should be validate_only_report_only", errors)
        summary = report.get("summary", {})
        expect(summary.get("categories") == EXPECTED_CATEGORIES, f"expected {EXPECTED_CATEGORIES} categories, got {summary.get('categories')}", errors)
        expect(summary.get("fixtures") == EXPECTED_FIXTURES, f"expected {EXPECTED_FIXTURES} fixtures, got {summary.get('fixtures')}", errors)
        expect(summary.get("failed_classifications") == 0, "all fixtures should classify correctly", errors)
        categories = {row.get("category") for row in report.get("category_summary", [])}
        for category in [
            "windows_shell_mismatch",
            "taxonomy_alias_mapping_gap",
            "post_compaction_recovery_discipline",
            "skill_sprawl_gate",
            "control_surface_sprawl_gate",
        ]:
            expect(category in categories, f"{category} category missing", errors)
        for row in report.get("category_summary", []):
            expect(row.get("has_valid_fixture") is True, f"{row.get('category')} missing valid fixture", errors)
            expect(row.get("has_invalid_fixture") is True, f"{row.get('category')} missing invalid fixture", errors)
        authority = report.get("authority_boundary", {})
        expect(authority and all(value is False for value in authority.values()), "all authority flags must be false", errors)
    if errors:
        for error in errors:
            print(f"FAIL: {error}")
        return 1
    print("ok: WF74 outcome eval suite v2 fixtures classified correctly")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
