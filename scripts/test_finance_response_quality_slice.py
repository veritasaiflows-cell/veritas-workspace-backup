from __future__ import annotations

import argparse
import copy
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "finance_response_quality_slice.py"
REPORT = ROOT / "tmp" / "finance-response-quality-slice.json"
sys.path.insert(0, str(ROOT / "scripts"))

from finance_response_quality_slice import (  # noqa: E402
    classify_source_freshness_debt,
    wf72_support_only_status,
)


def expect(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def structural_source_row(ticker: str = "TEST") -> dict[str, Any]:
    return {
        "ticker": ticker,
        "freshness_status": "blocked",
        "source_open_status": "verified",
        "missing_or_stale_families": [
            {
                "family_id": "tier_weighted_freshness",
                "status": "blocked_structural_or_candidate_hold",
                "resolution_state": "blocked_structural_or_candidate_hold",
            }
        ],
    }


def structural_decision_card(ticker: str = "TEST") -> dict[str, Any]:
    return {
        "ticker": ticker,
        "auto_state": "C-CANDIDATE-HOLD",
        "decision_state": "monitor_only",
        "wf84_scope": {"production_answer_path_member": False},
        "evidence_family_status": [
            {
                "family_id": "tier_weighted_freshness",
                "tier_weighted_resolved": True,
            }
        ],
    }


def expect_collection_blocking(
    result: dict[str, Any],
    label: str,
    errors: list[str],
) -> None:
    expect(result.get("source_freshness_raw_blocked_count") == 1, f"{label}: raw count should stay 1", errors)
    expect(
        result.get("source_freshness_structural_hold_non_collection_count") == 0,
        f"{label}: structural count should stay 0",
        errors,
    )
    expect(
        result.get("source_freshness_collection_blocked_count") == 1,
        f"{label}: effective collection count should stay 1",
        errors,
    )


def run_unit_regressions(errors: list[str]) -> None:
    expect(wf72_support_only_status("support_only") is True, "plain support_only should be accepted", errors)
    expect(
        wf72_support_only_status("support_only_with_active_sql_primary_migration") is True,
        "support-only SQL migration state should be accepted",
        errors,
    )
    expect(wf72_support_only_status("sql_primary_answer_front_door") is False, "answer front-door state must not be accepted", errors)

    source_row = structural_source_row()
    decision_card = structural_decision_card()
    positive = classify_source_freshness_debt([source_row], [decision_card])
    expect(positive.get("source_freshness_raw_blocked_count") == 1, "positive: raw blocked row should remain visible", errors)
    expect(
        positive.get("source_freshness_structural_hold_non_collection_count") == 1,
        "positive: exact structural hold should be non-collection debt",
        errors,
    )
    expect(
        positive.get("source_freshness_collection_blocked_count") == 0,
        "positive: exact structural hold should clear only the effective collection count",
        errors,
    )

    expect_collection_blocking(
        classify_source_freshness_debt([source_row], []),
        "missing matching card",
        errors,
    )

    unknown_state_row = copy.deepcopy(source_row)
    unknown_state_row["missing_or_stale_families"][0]["resolution_state"] = "blocked_future_resolution_state"
    expect_collection_blocking(
        classify_source_freshness_debt([unknown_state_row], [decision_card]),
        "unknown resolution state",
        errors,
    )

    unresolved_card = copy.deepcopy(decision_card)
    unresolved_card["evidence_family_status"][0]["tier_weighted_resolved"] = False
    expect_collection_blocking(
        classify_source_freshness_debt([source_row], [unresolved_card]),
        "tier weighted unresolved false",
        errors,
    )

    extra_family_row = copy.deepcopy(source_row)
    extra_family_row["missing_or_stale_families"].append(
        {
            "family_id": "technical_posture",
            "status": "stale",
            "resolution_state": "stale",
        }
    )
    expect_collection_blocking(
        classify_source_freshness_debt([extra_family_row], [decision_card]),
        "extra stale family",
        errors,
    )

    review_ready_card = copy.deepcopy(decision_card)
    review_ready_card["decision_state"] = "review_ready"
    expect_collection_blocking(
        classify_source_freshness_debt([source_row], [review_ready_card]),
        "review ready card",
        errors,
    )

    unknown_auto_state_card = copy.deepcopy(decision_card)
    unknown_auto_state_card["auto_state"] = "C-CANDIDATE-HOLD-FUTURE"
    expect_collection_blocking(
        classify_source_freshness_debt([source_row], [unknown_auto_state_card]),
        "unknown auto state",
        errors,
    )

    production_card = copy.deepcopy(decision_card)
    production_card["wf84_scope"]["production_answer_path_member"] = True
    expect_collection_blocking(
        classify_source_freshness_debt([source_row], [production_card]),
        "production answer path member",
        errors,
    )

    unverified_row = copy.deepcopy(source_row)
    unverified_row["source_open_status"] = "blocked"
    expect_collection_blocking(
        classify_source_freshness_debt([unverified_row], [decision_card]),
        "source open not verified",
        errors,
    )

    expect_collection_blocking(
        classify_source_freshness_debt([source_row], [decision_card, copy.deepcopy(decision_card)]),
        "duplicate matching cards",
        errors,
    )

    nonblocked_row = copy.deepcopy(source_row)
    nonblocked_row["freshness_status"] = "fresh"
    nonblocked = classify_source_freshness_debt([nonblocked_row], [decision_card])
    expect(nonblocked.get("source_freshness_raw_blocked_count") == 0, "fresh row must not enter blocked counts", errors)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--unit-only", action="store_true")
    args = parser.parse_args(argv)

    errors: list[str] = []
    run_unit_regressions(errors)
    if args.unit_only:
        if errors:
            for error in errors:
                print(f"FAIL: {error}")
            return 1
        print("ok: finance response quality structural-hold unit regressions")
        return 0

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
        raw_freshness = summary.get("source_freshness_raw_blocked_count")
        structural_freshness = summary.get("source_freshness_structural_hold_non_collection_count")
        collection_freshness = summary.get("source_freshness_collection_blocked_count")
        expect(
            summary.get("source_freshness_blocked_count") == raw_freshness,
            "legacy source freshness blocked count should remain the raw WF85 count",
            errors,
        )
        expect(
            raw_freshness == structural_freshness + collection_freshness,
            "raw freshness count should reconcile to structural plus effective collection debt",
            errors,
        )
        blocker_counts = summary.get("blocker_category_counts", {})
        expect("source_freshness_blocked" in blocker_counts, "source freshness blocker count should be split out", errors)
        expect(
            blocker_counts.get("source_freshness_raw_blocked") == raw_freshness,
            "raw source freshness category should reconcile",
            errors,
        )
        expect(
            blocker_counts.get("source_freshness_structural_hold_non_collection") == structural_freshness,
            "structural-hold source freshness category should reconcile",
            errors,
        )
        expect(
            blocker_counts.get("source_freshness_collection_blocked") == collection_freshness,
            "effective collection source freshness category should reconcile",
            errors,
        )
        expect("source_open_blocked" in blocker_counts, "source-open blocker count should be split out", errors)
        expect("primary_state_blocked" in blocker_counts, "primary-state blocker count should be split out", errors)
        expect("below_stop_blocked" in blocker_counts, "below-stop blocker count should be split out", errors)
        expect("tier_c_thin_monitor_non_blocking" in blocker_counts, "Tier C thin-monitor count should be split out", errors)
        expect("scoped_thin_monitor_not_required_non_blocking" in blocker_counts, "scoped thin-monitor-not-required count should be split out", errors)
        semantics = summary.get("scorecard_blocker_semantics", {})
        expect(
            "source_freshness_collection_blocked" in semantics.get("blocking_categories", []),
            "only effective collection freshness should be a blocking category",
            errors,
        )
        expect(
            "source_freshness_structural_hold_non_collection" in semantics.get("decision_readiness_categories", []),
            "structural holds should remain decision-readiness debt",
            errors,
        )
        expect(
            "source_freshness_structural_hold_non_collection" in semantics.get("non_blocking_categories", []),
            "structural holds should remain explicitly non-collection/nonblocking debt",
            errors,
        )
        expect("primary_state_blocked" in semantics.get("decision_readiness_categories", []), "primary-state blocker should be decision-readiness debt", errors)
        expect("below_stop_blocked" in semantics.get("decision_readiness_categories", []), "below-stop blocker should be decision-readiness debt", errors)
        expect("tier_c_thin_monitor_non_blocking" in semantics.get("non_blocking_categories", []), "Tier C thin-monitor should be non-blocking", errors)
        expect("scoped_thin_monitor_not_required_non_blocking" in semantics.get("non_blocking_categories", []), "scoped thin-monitor-not-required should be non-blocking", errors)
        expect(
            summary.get("tier_c_thin_monitor_non_blocking_count") == blocker_counts.get("tier_c_thin_monitor_non_blocking"),
            "Tier C thin-monitor summary should reconcile to blocker split",
            errors,
        )
        expect(
            summary.get("scoped_thin_monitor_not_required_non_blocking_count") == blocker_counts.get("scoped_thin_monitor_not_required_non_blocking"),
            "scoped thin-monitor-not-required summary should reconcile to blocker split",
            errors,
        )
        tracks = {row.get("track_id"): row for row in report.get("remediation_tracks", [])}
        source_track = tracks.get("source_freshness_repair", {})
        expect(
            source_track.get("source_freshness_collection_blocked_count") == collection_freshness,
            "source remediation track should expose the effective collection count",
            errors,
        )
        expect(
            source_track.get("freshness_blocked_count") == collection_freshness,
            "source remediation legacy freshness field should use effective collection debt",
            errors,
        )
        expect(
            source_track.get("current_gap_count")
            == collection_freshness + summary.get("source_open_blocked_count"),
            "source remediation gap should use effective collection freshness plus source-open debt",
            errors,
        )
        expect(tracks.get("tier_c_thin_monitor_visibility", {}).get("status") == "monitor_only", "Tier C thin-monitor track should be monitor-only", errors)
        expect("repair_conveyor" in report.get("source_artifacts", {}), "repair conveyor source artifact should be listed", errors)
    if errors:
        for error in errors:
            print(f"FAIL: {error}")
        return 1
    print("ok: finance response quality slice is bounded")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
