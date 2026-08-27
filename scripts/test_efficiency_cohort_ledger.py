"""Tests for the report-only efficiency cohort ledger."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import efficiency_cohort_ledger as module


def make_lane(
    *,
    created: str = "2026-08-13T00:00:00Z",
    status: str = "complete",
    model: str | None = "openai/gpt-5.6-terra",
    backend: str = "persistent_isolated_agent",
    phase: str | None = "implementation",
    parent: str | None = "JOB-1",
    attempt: object = 1,
    retry: object = 0,
    acceptance: str | None = "accepted",
    incident: str | None = None,
    elapsed: object = None,
    workflow: str = "WFT",
    workstream: str = "ws",
) -> dict:
    runtime: dict = {
        "actual_execution_backend": backend,
    }
    if model is not None:
        runtime["model_path"] = model
    if phase is not None:
        runtime["phase"] = phase
    if parent is not None:
        runtime["parent_job_id"] = parent
    if attempt is not None:
        runtime["attempt_number"] = attempt
    if retry is not None:
        runtime["retry_count"] = retry
    if acceptance is not None:
        runtime["main_acceptance_status"] = acceptance
    if incident is not None:
        runtime["incident_code"] = incident
    if elapsed is not None:
        runtime["observed_elapsed_seconds"] = elapsed
    return {
        "workflow_id": workflow,
        "workstream_id": workstream,
        "status": status,
        "created_at_utc": created,
        "runtime": runtime,
    }


def write_fixture(tmp: Path, lanes: list[dict], measurement: dict | None = "default") -> tuple[Path, Path]:
    register_path = tmp / "register.json"
    register_path.write_text(json.dumps({"lanes": lanes}), encoding="utf-8")
    token_path = tmp / "token-ledger.json"
    if measurement == "default":
        measurement = {
            "schema": "veritas.efficiency_measurement.v1",
            "status": "insufficient_attributable_comparable_cohort",
            "savings_claim_allowed": False,
        }
    if measurement is not None:
        token_path.write_text(
            json.dumps({"generated_at_utc": "2026-08-14T00:00:00Z", "efficiency_measurement": measurement}),
            encoding="utf-8",
        )
    return register_path, token_path


def build(lanes: list[dict], measurement: dict | None = "default") -> dict:
    with tempfile.TemporaryDirectory() as raw:
        tmp = Path(raw)
        register_path, token_path = write_fixture(tmp, lanes, measurement)
        return module.build_ledger(register_path, token_path)


def only_cohort(ledger: dict) -> dict:
    assert len(ledger["cohorts"]) == 1, ledger["cohorts"]
    return ledger["cohorts"][0]


def test_pre_cutover_lane_excluded() -> None:
    ledger = build(
        [
            make_lane(created="2026-08-10T00:00:00Z", workstream="old"),
            make_lane(workstream="new"),
        ]
    )
    assert ledger["scope"]["enforcement_scope_terminal_model_lanes"] == 1
    assert only_cohort(ledger)["lane_count"] == 1


def test_non_terminal_and_model_free_lanes_excluded() -> None:
    ledger = build(
        [
            make_lane(status="leased", workstream="live"),
            make_lane(model=None, workstream="modelfree"),
            make_lane(workstream="kept"),
        ]
    )
    assert ledger["scope"]["enforcement_scope_terminal_model_lanes"] == 1
    assert only_cohort(ledger)["lane_count"] == 1


def test_identity_gap_counted_not_cohorted() -> None:
    ledger = build(
        [
            make_lane(parent=None, workstream="gap"),
            make_lane(attempt="1", retry="0", workstream="untyped"),
            make_lane(workstream="ok"),
        ]
    )
    scope = ledger["scope"]
    assert scope["identity_gap_lane_count"] == 2
    assert scope["cohorted_lane_count"] == 1
    assert "WFT::gap" in scope["identity_gap_lanes"]
    assert "identity_gap_lanes_present" in ledger["validation"]["warnings"]
    assert only_cohort(ledger)["lane_count"] == 1


def test_first_pass_vs_retry_classification() -> None:
    ledger = build(
        [
            make_lane(workstream="fp"),
            make_lane(attempt=2, retry=1, workstream="retry"),
            make_lane(acceptance="rejected", workstream="rej"),
            make_lane(acceptance=None, workstream="pend"),
        ]
    )
    cohort = only_cohort(ledger)
    assert cohort["main_accepted_count"] == 2
    assert cohort["first_pass_accepted_count"] == 1
    assert cohort["accepted_after_retry_count"] == 1
    assert cohort["rejected_count"] == 1
    assert cohort["pending_or_unreviewed_count"] == 1
    assert cohort["retry_tax_total_retries"] == 1


def test_incident_gets_no_first_pass_credit() -> None:
    ledger = build(
        [
            make_lane(incident="provider_error", workstream="inc"),
        ]
    )
    cohort = only_cohort(ledger)
    assert cohort["main_accepted_count"] == 1
    assert cohort["first_pass_accepted_count"] == 0
    assert cohort["accepted_with_incident_count"] == 1
    assert cohort["incident_counts_by_code"] == {"provider_error": 1}


def test_missing_elapsed_is_not_zero() -> None:
    ledger = build(
        [
            make_lane(elapsed=600, workstream="timed"),
            make_lane(workstream="untimed"),
        ]
    )
    elapsed = only_cohort(ledger)["elapsed_seconds"]
    assert elapsed["observed_lane_count"] == 1
    assert elapsed["missing_lane_count"] == 1
    assert elapsed["total_observed_seconds"] == 600
    assert elapsed["mean_observed_seconds"] == 600.0


def test_hyphenated_acceptance_normalized() -> None:
    ledger = build(
        [
            make_lane(acceptance="accepted-with-documented-limits", workstream="hyph"),
        ]
    )
    assert only_cohort(ledger)["main_accepted_count"] == 1


def test_gate_counts_jobs_not_lanes() -> None:
    lanes = [
        make_lane(parent="JOB-A", workstream="a1"),
        make_lane(parent="JOB-A", attempt=2, retry=1, workstream="a2"),
        make_lane(parent="JOB-B", workstream="b1"),
    ]
    ledger = build(lanes)
    gate = ledger["observation_gate"]
    assert gate["main_accepted_lane_total"] == 3
    assert gate["comparable_main_accepted_job_total"] == 2
    assert only_cohort(ledger)["comparable_main_accepted_job_count"] == 2


def test_mixed_route_job_excluded_from_gate() -> None:
    lanes = [
        make_lane(parent="JOB-MIX", phase="implementation", workstream="m1"),
        make_lane(parent="JOB-MIX", phase="qa", workstream="m2"),
        make_lane(parent="JOB-SOLO", workstream="solo"),
    ]
    ledger = build(lanes)
    gate = ledger["observation_gate"]
    assert gate["mixed_route_parent_job_count_excluded"] == 1
    assert gate["comparable_main_accepted_job_total"] == 1


def test_gate_math_at_ten() -> None:
    lanes = [
        make_lane(parent=f"JOB-{i}", workstream=f"ws{i}")
        for i in range(module.EFFICIENCY_MIN_COMPARABLE_MAIN_ACCEPTED_JOBS)
    ]
    ledger = build(lanes)
    gate = ledger["observation_gate"]
    assert gate["comparable_main_accepted_job_total"] == module.EFFICIENCY_MIN_COMPARABLE_MAIN_ACCEPTED_JOBS
    assert gate["met"] is True
    assert gate["promotion_allowed"] is False
    assert gate["automatic_route_promotion_allowed"] is False
    assert "observation_gate_not_met" not in ledger["validation"]["warnings"]

    below = build(lanes[:-1])
    assert below["observation_gate"]["met"] is False
    assert "observation_gate_not_met" in below["validation"]["warnings"]


def test_unsupported_route_not_countable() -> None:
    ledger = build(
        [
            make_lane(model="claude-cli/claude-fable-5", backend="main", workstream="fable"),
        ]
    )
    cohort = only_cohort(ledger)
    assert cohort["route_countable"] is False
    assert cohort["main_accepted_count"] == 1
    assert cohort["gate"]["progress"] == 0
    assert ledger["observation_gate"]["comparable_main_accepted_job_total"] == 0


def test_missing_register_blocks() -> None:
    with tempfile.TemporaryDirectory() as raw:
        tmp = Path(raw)
        _, token_path = write_fixture(tmp, [])
        ledger = module.build_ledger(tmp / "absent.json", token_path)
    assert ledger["status"] == "blocked"
    assert "register_missing_or_unreadable" in ledger["validation"]["errors"]


def test_economics_reference_embedded_and_missing_warned() -> None:
    measurement = {"schema": "veritas.efficiency_measurement.v1", "savings_claim_allowed": False}
    ledger = build([make_lane()], measurement=measurement)
    assert ledger["economics_reference"]["efficiency_measurement"] == measurement

    absent = build([make_lane()], measurement=None)
    assert absent["economics_reference"]["efficiency_measurement"] is None
    assert "economics_reference_missing" in absent["validation"]["warnings"]


def test_authority_boundary_stays_report_only() -> None:
    ledger = build([make_lane()])
    boundary = ledger["authority_boundary"]
    assert boundary["report_only"] is True
    assert boundary["register_mutation_allowed"] is False
    assert boundary["route_promotion_allowed"] is False
    assert boundary["savings_claim_allowed"] is False
    assert boundary["owner_approval_inferred"] is False


def main() -> None:
    test_pre_cutover_lane_excluded()
    test_non_terminal_and_model_free_lanes_excluded()
    test_identity_gap_counted_not_cohorted()
    test_first_pass_vs_retry_classification()
    test_incident_gets_no_first_pass_credit()
    test_missing_elapsed_is_not_zero()
    test_hyphenated_acceptance_normalized()
    test_gate_counts_jobs_not_lanes()
    test_mixed_route_job_excluded_from_gate()
    test_gate_math_at_ten()
    test_unsupported_route_not_countable()
    test_missing_register_blocks()
    test_economics_reference_embedded_and_missing_warned()
    test_authority_boundary_stays_report_only()
    print("efficiency cohort ledger tests passed")


if __name__ == "__main__":
    main()
