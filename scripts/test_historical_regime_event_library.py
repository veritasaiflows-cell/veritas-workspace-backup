from __future__ import annotations

import json
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import historical_regime_event_library as hist
import probability_readiness_report as report_mod


def expect(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def sample_payload() -> dict:
    events = []
    for idx in range(10):
        start_year = 1970 + idx * 4
        events.append({
            "event_id": f"event_{idx}",
            "start": f"{start_year}-01-01",
            "outcomes": {"large_cap": {"status": "ok"}},
            "small_vs_large": {"status": "ok" if idx >= 2 else "unavailable"},
        })
    return {"authority": dict(hist.AUTHORITY), "events": events}


def test_validation_contract(errors: list[str]) -> None:
    payload = sample_payload()
    checks = hist.validate_payload(payload)
    critical = [check for check in checks if not check["ok"] and check["severity"] == "critical"]
    expect(not critical, f"sample payload should not have critical validation failures: {critical}", errors)


def test_authority_false_contract(errors: list[str]) -> None:
    payload = sample_payload()
    payload["authority"]["capital_action_allowed"] = True
    checks = hist.validate_payload(payload)
    expect(any(check["name"] == "authority_capital_action_allowed" and not check["ok"] for check in checks), "capital action authority drift must fail", errors)


def test_report_summary_contract(errors: list[str]) -> None:
    summary = report_mod.historical_regime_summary(Path("tmp/does-not-exist-historical-regime.json"))
    expect(summary["exists"] is False, "missing historical library should report exists false", errors)
    expect(summary["calibrated_probability_allowed"] is False, "summary must keep probability claims blocked", errors)
    expect(summary["predictive_or_model_claims_allowed"] is False, "summary must keep model claims blocked", errors)


def test_forbidden_wording_guard(errors: list[str]) -> None:
    payload = sample_payload()
    text = json.dumps(payload, sort_keys=True).lower()
    for phrase in ("win probability", "expected return", "model-ranked", "% chance", "trade approval"):
        expect(phrase not in text, f"sample payload should avoid forbidden phrase {phrase}", errors)


def main() -> int:
    errors: list[str] = []
    test_validation_contract(errors)
    test_authority_false_contract(errors)
    test_report_summary_contract(errors)
    test_forbidden_wording_guard(errors)
    if errors:
        print("historical_regime_event_library_tests_failed")
        for error in errors:
            print(f"- {error}")
        return 1
    print("historical_regime_event_library_tests_passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
