from __future__ import annotations

import auto_apply_position_sizing_semantic_sync as auto_sync
from chain_manifest import manifest_steps


def expect(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def test_manifest_runs_sizing_sync_after_capital_validator(errors: list[str]) -> None:
    for window in ("morning", "post-close", "sunday"):
        scripts = [step["script"] for step in manifest_steps(window)]
        expect("auto_apply_position_sizing_semantic_sync.py" in scripts, f"{window} missing sizing semantic sync step", errors)
        if "auto_apply_position_sizing_semantic_sync.py" in scripts:
            expect(
                scripts.index("capital_deployment_recommendation_validator.py")
                < scripts.index("auto_apply_position_sizing_semantic_sync.py")
                < scripts.index("probability_readiness_report.py"),
                f"{window} sizing semantic sync should run after capital validator and before probability readiness report",
                errors,
            )


def test_wrapper_reports_ok_when_no_proposals(errors: list[str]) -> None:
    empty_bundle = auto_sync.TMP / "test-empty-position-sizing-bundle.json"
    empty_bundle.write_text('{"proposals": []}\n', encoding="utf-8")
    try:
        audit = auto_sync.build_audit(empty_bundle, "morning", apply_mode=False, expires_hours=24)
        expect(audit.get("status") == "ok_no_changes", f"expected ok_no_changes, got {audit.get('status')}", errors)
        expect(audit.get("summary", {}).get("proposal_count") == 0, f"expected zero proposals, got {audit.get('summary')}", errors)
    finally:
        empty_bundle.unlink(missing_ok=True)


def test_sql_first_thin_snapshot_short_circuits_snapshot_mutation(errors: list[str]) -> None:
    ok = auto_sync.sql_first_thin_snapshot_sync_decision(
        {
            "sql_first_thin_board_detected": True,
            "sql_first_thin_board_allowed": True,
        }
    )
    expect(ok["short_circuit_snapshot_mutation"] is True, f"thin snapshot should short-circuit writes, got {ok}", errors)
    expect(ok["status"] == "ok_no_changes", f"allowed thin snapshot should be ok_no_changes, got {ok}", errors)
    blocked = auto_sync.sql_first_thin_snapshot_sync_decision(
        {
            "sql_first_thin_board_detected": True,
            "sql_first_thin_board_allowed": False,
        }
    )
    expect(blocked["status"] == "blocked", f"blocked thin snapshot contract should block, got {blocked}", errors)
    legacy = auto_sync.sql_first_thin_snapshot_sync_decision({"sql_first_thin_board_detected": False})
    expect(
        legacy["short_circuit_snapshot_mutation"] is False and legacy["status"] == "legacy_portfolio_snapshot_note",
        f"non-thin snapshot should use legacy exact-diff sync, got {legacy}",
        errors,
    )


def main() -> int:
    errors: list[str] = []
    test_manifest_runs_sizing_sync_after_capital_validator(errors)
    test_wrapper_reports_ok_when_no_proposals(errors)
    test_sql_first_thin_snapshot_short_circuits_snapshot_mutation(errors)
    if errors:
        print("auto_apply_position_sizing_semantic_sync_tests_failed")
        for error in errors:
            print(f"- {error}")
        return 1
    print("auto_apply_position_sizing_semantic_sync_tests_passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
