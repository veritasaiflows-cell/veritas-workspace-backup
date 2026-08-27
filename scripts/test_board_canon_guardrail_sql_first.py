from __future__ import annotations

import board_canon_guardrail as guard


def expect(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def test_sql_first_thin_board_does_not_require_markdown_sections(errors: list[str]) -> None:
    original_eval = guard.evaluate_sql_first_thin_board_contract
    original_build_risks = guard.build_risk_records
    original_build_alerts = guard.build_risk_alerts
    original_read_text = guard.read_text
    original_records = guard.records_by_ticker
    try:
        guard.evaluate_sql_first_thin_board_contract = lambda _path: {  # type: ignore[assignment]
            "sql_first_thin_board_detected": True,
            "sql_first_thin_board_allowed": True,
        }
        risks = [
            {
                "ticker": "AMZN",
                "risk_state": "below_stop",
                "coverage_lane": "watch",
                "workflow_state": "WATCH",
            }
        ]
        guard.build_risk_records = lambda: risks  # type: ignore[assignment]
        guard.build_risk_alerts = lambda _risks: [  # type: ignore[assignment]
            {
                "severity": "warning",
                "ticker": "AMZN",
                "risk_state": "below_stop",
                "message": "AMZN is below stop.",
                "deployment_blocking": False,
                "risk_record": risks[0],
            }
        ]
        guard.read_text = lambda _path: ""  # type: ignore[assignment]
        guard.records_by_ticker = lambda _payload: {  # type: ignore[assignment]
            "AMZN": {
                "stance": "Do not touch",
                "band_note": "stop breached",
                "action_state": "DO NOT TOUCH",
            }
        }
        report = guard.evaluate()
        expect(report["status"] == "warning", f"risk alert should warn but not critical, got {report}", errors)
        expect(report["summary"]["critical"] == 0, f"missing thin-board section should not be critical, got {report['summary']}", errors)
        expect(report["technical_sheet_mode"] == "sql_first_thin_board", f"expected thin-board mode, got {report.get('technical_sheet_mode')}", errors)
    finally:
        guard.evaluate_sql_first_thin_board_contract = original_eval  # type: ignore[assignment]
        guard.build_risk_records = original_build_risks  # type: ignore[assignment]
        guard.build_risk_alerts = original_build_alerts  # type: ignore[assignment]
        guard.read_text = original_read_text  # type: ignore[assignment]
        guard.records_by_ticker = original_records  # type: ignore[assignment]


def main() -> int:
    errors: list[str] = []
    test_sql_first_thin_board_does_not_require_markdown_sections(errors)
    if errors:
        print("board_canon_guardrail_sql_first_tests_failed")
        for error in errors:
            print(f"- {error}")
        return 1
    print("board_canon_guardrail_sql_first_tests_passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
