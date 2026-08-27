from __future__ import annotations

import copy

from wf75_artifact_only_pm_handoff import validate


def base_handoff() -> dict:
    return {
        "schema": "veritas.wf75.artifact_only_pm_handoff.v1",
        "artifact_inputs": [],
        "validation_status": {
            "wf77_bridge": "warning",
            "renderer_regression": "ok",
            "scenario_library": "ok",
            "service_state": "ok",
            "operator_queue": "ok",
            "operator_console": "ok",
            "automation_movement": "ok",
            "pm_weekly_update": "ready_for_internal_pm_review",
            "sqlite_wal_control_plane": "ok",
            "veritas_harness_scorecard": "ok",
            "macro_event_calendar": "ok",
        },
        "wf77_price_evidence": {
            "missing_price_rows": [],
            "excluded_price_rows": [],
            "price_unavailable_rows": [],
            "valid_price_row_count": 4,
            "row_count": 4,
        },
        "renderer_export_regression": {
            "clean_scenarios_passed": 8,
            "clean_scenarios_total": 8,
        },
        "scenario_template_library": {
            "scenario_count": 8,
        },
        "sqlite_wal_control_plane": {
            "journal_mode": "wal",
            "claim_rows": [
                {"claim_status": "claimed"},
                {"claim_status": "already_claimed"},
            ],
        },
        "authority_boundary": {
            "public_launch_ready": False,
            "real_customer_data_allowed": False,
            "customer_data_retention_allowed": False,
            "external_delivery_allowed": False,
            "legal_or_compliance_ready": False,
            "source_licensing_assumed": False,
            "personalized_regulated_advice_allowed": False,
            "brokerage_or_account_connection_allowed": False,
            "paper_or_live_execution_allowed": False,
            "portfolio_or_canon_mutation_allowed": False,
            "sql_or_ticker_import_allowed": False,
            "owner_approval_inferred": False,
        },
    }


def expect(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def test_unavailable_price_rows_are_warning_only() -> None:
    handoff = base_handoff()
    handoff["wf77_price_evidence"]["excluded_price_rows"] = ["ADSK"]
    handoff["wf77_price_evidence"]["price_unavailable_rows"] = ["ADSK"]
    handoff["wf77_price_evidence"]["valid_price_row_count"] = 0

    result = validate(handoff)

    errors: list[str] = []
    expect(result["status"] == "ok", "unavailable rows should not block artifact-only handoff", errors)
    expect(not result["errors"], f"unexpected errors: {result['errors']}", errors)
    expect("wf77 price evidence has excluded rows" in result["warnings"], "excluded-row warning missing", errors)
    expect("wf77 price evidence has unavailable rows" in result["warnings"], "unavailable-row warning missing", errors)
    expect("wf77 valid price row count does not match row count" in result["warnings"], "row-count warning missing", errors)
    if errors:
        raise AssertionError("; ".join(errors))


def test_missing_price_rows_still_block() -> None:
    handoff = copy.deepcopy(base_handoff())
    handoff["wf77_price_evidence"]["missing_price_rows"] = ["XYZ"]

    result = validate(handoff)

    errors: list[str] = []
    expect(result["status"] == "error", "missing rows must still block", errors)
    expect("wf77 price evidence still has missing rows" in result["errors"], "missing-row error missing", errors)
    if errors:
        raise AssertionError("; ".join(errors))


if __name__ == "__main__":
    test_unavailable_price_rows_are_warning_only()
    test_missing_price_rows_still_block()
    print("ok")
