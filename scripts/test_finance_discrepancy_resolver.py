from __future__ import annotations

import finance_discrepancy_resolver as resolver


def expect(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def main() -> int:
    errors: list[str] = []

    inputs = {
        "earnings_date_source_confidence": {
            "status": "ok",
            "records": [
                {
                    "ticker": "ABC",
                    "configured_date": "2026-05-20",
                    "provider_next_earnings_date": "2026-05-21",
                    "source_confidence": "provider_estimate",
                    "primary_confirmation_status": "provider_only",
                    "verification_sites": [{"label": "ABC IR", "url": "https://example.com"}],
                }
            ],
        },
        "event_calendar_rollforward": {"status": "ok"},
        "event_calendar_apply": {"status": "ok"},
        "board_canon_guardrail": {
            "status": "warning",
            "risk_alerts": [
                {
                    "ticker": "XYZ",
                    "risk_state": "below_stop",
                    "message": "XYZ is below stop",
                    "deployment_blocking": True,
                }
            ],
        },
        "stale_intelligence_guardrail": {"status": "ok", "findings": []},
        "canonical_note_patch_proposal": {"status": "ok", "candidates": []},
        "portfolio_snapshot_patch_proposal": {"status": "ok", "proposals": [{"id": "p1"}]},
    }

    rows = []
    rows.extend(resolver.collect_input_health(inputs))
    rows.extend(resolver.collect_earnings_discrepancies(inputs))
    rows.extend(resolver.collect_guardrail_discrepancies(inputs))
    rows.extend(resolver.collect_patch_proposal_discrepancies(inputs))

    classes = {row["class"] for row in rows}
    expect("earnings_date" in classes, "provider/configured date mismatch should produce earnings_date discrepancy", errors)
    expect("source_confidence" in classes, "provider-only confidence should stay visible", errors)
    expect("board_canon" in classes, "below-stop guardrail alert should produce board_canon discrepancy", errors)
    expect("patch_proposal" in classes, "patch proposal candidates should produce patch_proposal discrepancy", errors)
    expect(all(row["cron_apply_allowed"] is False for row in rows), "cron apply must be false for every row", errors)
    expect(all(row["main_session_review_required"] is True for row in rows), "main-session review must be required for every row", errors)
    expect(all(row["authority"]["trade_or_account_action_allowed"] is False for row in rows), "trade/account authority must remain false", errors)
    expect(all(row["authority"]["portfolio_mutation_allowed"] is False for row in rows), "portfolio mutation authority must remain false", errors)

    if errors:
        print("finance_discrepancy_resolver_tests_failed")
        for error in errors:
            print(f"- {error}")
        return 1
    print("finance_discrepancy_resolver_tests_passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
