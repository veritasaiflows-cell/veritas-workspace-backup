from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import probability_readiness_report as report_mod
import probability_readiness_validator as validator_mod


def expect(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def test_state_history_empty_outcomes(errors: list[str]) -> None:
    rows = [
        {
            "captured_at_utc": "2026-05-10T00:00:00Z",
            "window": "post-close",
            "future_outcomes": {"realized_outcomes": [], "owner_decision": None},
        },
        {
            "captured_at_utc": "2026-05-11T00:00:00Z",
            "window": "post-close",
            "future_outcomes": {"realized_outcomes": [], "owner_decision": None},
        },
    ]
    summary = report_mod.state_history_summary(rows)
    expect(summary["row_count"] == 2, "state-history row count should be direct", errors)
    expect(summary["realized_outcome_count"] == 0, "empty realized_outcomes should count as zero", errors)
    expect(summary["owner_decision_count"] == 0, "null owner_decision should not count", errors)
    expect(summary["outcome_analytics_ready"] is False, "outcome analytics must remain blocked", errors)


def test_report_verdict_and_sections(errors: list[str]) -> None:
    report = report_mod.build_report()
    expect(report.get("verdict") in {"SAFE_WITH_GAPS", "NOT_READY"}, "report verdict must be SAFE_WITH_GAPS or NOT_READY", errors)
    expect(report.get("verdict") != "READY", "report must not emit READY", errors)
    for section in (
        "forecast_question_inventory",
        "outcome_label_taxonomy",
        "source_quality_gates",
        "probability_language_audit",
        "data_readiness_gaps",
        "limits",
        "historical_regime_analog_summary",
    ):
        expect(section in report, f"report missing {section}", errors)
    historical = report.get("historical_regime_analog_summary") or {}
    expect(historical.get("calibrated_probability_allowed") is False, "historical analog summary must block calibrated probability output", errors)
    expect(historical.get("predictive_or_model_claims_allowed") is False, "historical analog summary must block predictive/model claims", errors)
    authority = report.get("authority") or {}
    expect(authority.get("hard_false_authority_block") is True, "report must carry hard-false authority block", errors)
    for key, value in authority.items():
        if key.endswith("allowed") or key.endswith("granted"):
            expect(value is False, f"authority field {key} must be false", errors)


def test_forbidden_scan_nested_fields(errors: list[str]) -> None:
    nested = {
        "safe": {"items": [{"deep": {"text": "this claims a 55% chance of success"}}]},
        "authority": {"model_ranked_deployment_allowed": False},
    }
    findings: list[dict] = []
    validator_mod.scan_forbidden(Path("tmp/example.json"), nested, findings)
    expect(any(item.get("label") == "percent_chance" for item in findings), "nested forbidden language should be detected", errors)
    expect(not any(item.get("label") == "model_ranked_key" for item in findings), "false hard-authority key should be allowed as a block flag", errors)


def test_authority_widening_detection(errors: list[str]) -> None:
    findings: list[dict] = []
    validator_mod.audit_authority(Path("tmp/example.json"), {"authority": {"trade_execution_allowed": True}}, findings)
    expect(any(item.get("issue") == "authority_widening_detected" for item in findings), "true authority flags must hard fail", errors)


def test_borderline_annotation_detection(errors: list[str]) -> None:
    missing = {"capital_deployment_recommendations": [{"ticker": "ABC", "confidence": "moderate", "signal_score": 81}]}
    findings: list[dict] = []
    validator_mod.borderline_annotation_checks(Path("tmp/example.json"), missing, findings)
    expect(len(findings) == 2, "missing confidence/signal annotations should warn", errors)

    annotated = {
        "capital_deployment_recommendations": [
            {
                "ticker": "ABC",
                "confidence": "moderate",
                "confidence_basis": "Heuristic-only qualitative confidence; uncalibrated, non-predictive, and not_probability.",
                "signal_score": 81,
                "signal_score_basis": "Heuristic-only triage score; uncalibrated, non-predictive, and not_probability.",
            }
        ]
    }
    findings = []
    validator_mod.borderline_annotation_checks(Path("tmp/example.json"), annotated, findings)
    expect(not findings, f"annotated borderline fields should not warn: {findings}", errors)


def test_future_timestamp_hard_fail(errors: list[str]) -> None:
    rows = [
        {
            "captured_at_utc": "2026-05-10T12:00:00Z",
            "future_outcomes": {"realized_outcomes_updated_at_utc": "2026-05-10T12:00:00Z", "realized_outcomes": ["band_reclaim_lost"]},
        }
    ]
    findings: list[dict] = []
    validator_mod.state_history_checks(rows, report_mod.state_history_summary(rows), findings)
    expect(any(item.get("issue") == "future_outcome_timestamp_not_after_capture" for item in findings), "future outcome timestamps must be after capture", errors)


def main() -> int:
    errors: list[str] = []
    test_state_history_empty_outcomes(errors)
    test_report_verdict_and_sections(errors)
    test_forbidden_scan_nested_fields(errors)
    test_authority_widening_detection(errors)
    test_borderline_annotation_detection(errors)
    test_future_timestamp_hard_fail(errors)
    if errors:
        print("probability_readiness_tests_failed")
        for error in errors:
            print(f"- {error}")
        return 1
    print("probability_readiness_tests_passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
