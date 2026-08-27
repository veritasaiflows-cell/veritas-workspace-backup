"""Report-only outcome-quality cohort ledger over the concurrent lane register.

Complements token_usage_ledger.efficiency_measurement(): that function owns the
economics side (creditable tokens, baselines, savings gating). This ledger owns
the outcome-quality side (first-pass acceptance, retry tax, incidents, elapsed)
from Main-verified lane stamps, and embeds the economics block by reference
instead of recomputing credit.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from concurrent_lane_manager import (
    EFFICIENCY_ENFORCEMENT_START_UTC,
    efficiency_enforcement_applies,
)
from market_data_utils import atomic_write_json
from lib.terminal_outcome import (
    MAIN_ACCEPTED_STATES,
    validate_closure_durability,
    validate_validator_result,
)
from token_usage_ledger import (
    EFFICIENCY_MIN_COMPARABLE_MAIN_ACCEPTED_JOBS,
    UNSUPPORTED_MODEL_ROUTES,
)

SCHEMA = "veritas.efficiency_cohort_ledger.v1"
WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_REGISTER_PATH = WORKSPACE_ROOT / "tmp" / "concurrent-lane-register.json"
DEFAULT_TOKEN_LEDGER_PATH = WORKSPACE_ROOT / "tmp" / "token-usage-ledger-current.json"
DEFAULT_OUTPUT_PATH = WORKSPACE_ROOT / "tmp" / "efficiency-cohort-ledger.json"

TERMINAL_STATUSES = ("complete", "blocked", "cancelled")
IDENTITY_GAP_LIST_LIMIT = 20


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha256_file(path: Path) -> str | None:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return None


def typed_int(value: Any, minimum: int) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value if value >= minimum else None


def normalize_acceptance(value: Any) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    return value.strip().lower().replace("-", "_")


def lane_label(lane: dict[str, Any]) -> str:
    workflow = lane.get("workflow_id") or lane.get("workflow")
    workstream = lane.get("workstream_id") or lane.get("workstream")
    return f"{workflow}::{workstream}"


def lane_in_outcome_scope(lane: dict[str, Any]) -> bool:
    runtime = lane.get("runtime") or {}
    return (
        str(lane.get("status") or "") in TERMINAL_STATUSES
        and bool(runtime.get("model_path"))
        and efficiency_enforcement_applies(lane)
    )


def lane_typed_identity(lane: dict[str, Any]) -> dict[str, Any] | None:
    runtime = lane.get("runtime") or {}
    parent_job_id = runtime.get("parent_job_id")
    phase = runtime.get("phase")
    attempt_number = typed_int(runtime.get("attempt_number"), minimum=1)
    retry_count = typed_int(runtime.get("retry_count"), minimum=0)
    if not isinstance(parent_job_id, str) or not parent_job_id.strip():
        return None
    if not isinstance(phase, str) or not phase.strip():
        return None
    if attempt_number is None or retry_count is None:
        return None
    return {
        "parent_job_id": parent_job_id.strip(),
        "phase": phase.strip(),
        "attempt_number": attempt_number,
        "retry_count": retry_count,
    }


def route_countability(model_path: str) -> tuple[bool, str | None]:
    route = UNSUPPORTED_MODEL_ROUTES.get(model_path)
    if route is None:
        return True, None
    countable = bool(route.get("active_route_countable"))
    return countable, str(route.get("reason") or route.get("status") or "unsupported_route")


def lane_accepted(runtime: dict[str, Any]) -> bool:
    return normalize_acceptance(runtime.get("main_acceptance_status")) in MAIN_ACCEPTED_STATES


def build_cohorts(
    lanes: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[str], int, dict[str, Any]]:
    grouped: dict[tuple[str, str, str], list[tuple[dict[str, Any], dict[str, Any]]]] = {}
    identity_gaps: list[str] = []
    scoped = 0
    for lane in lanes:
        if not lane_in_outcome_scope(lane):
            continue
        scoped += 1
        identity = lane_typed_identity(lane)
        if identity is None:
            identity_gaps.append(lane_label(lane))
            continue
        runtime = lane.get("runtime") or {}
        backend = str(runtime.get("actual_execution_backend") or "undeclared")
        model_path = str(runtime.get("model_path"))
        grouped.setdefault((backend, model_path, identity["phase"]), []).append((lane, identity))

    # Comparable = distinct Main-accepted parent jobs whose accepted lanes all sit in one
    # cohort; mixed-route jobs are excluded, mirroring efficiency_measurement semantics.
    job_routes: dict[str, set[tuple[str, str, str]]] = {}
    accepted_lane_total = 0
    for key, members in grouped.items():
        for lane, identity in members:
            if lane_accepted(lane.get("runtime") or {}):
                accepted_lane_total += 1
                job_routes.setdefault(identity["parent_job_id"], set()).add(key)
    mixed_route_jobs = {job for job, keys in job_routes.items() if len(keys) > 1}
    comparable_jobs_by_cohort: dict[tuple[str, str, str], int] = {}
    for job, keys in job_routes.items():
        if job in mixed_route_jobs:
            continue
        (key,) = keys
        comparable_jobs_by_cohort[key] = comparable_jobs_by_cohort.get(key, 0) + 1

    cohorts: list[dict[str, Any]] = []
    comparable_countable_total = 0
    for (backend, model_path, phase), members in sorted(grouped.items()):
        accepted = 0
        first_pass = 0
        after_retry = 0
        rejected = 0
        pending = 0
        accepted_with_incident = 0
        retry_tax = 0
        incident_counts: dict[str, int] = {}
        elapsed_values: list[int] = []
        missing_elapsed = 0
        validator_result_counts: dict[str, int] = {}
        closure_durability_counts: dict[str, int] = {}
        for lane, identity in members:
            runtime = lane.get("runtime") or {}
            retry_tax += identity["retry_count"]
            validator_result = validate_validator_result(runtime.get("validator_result"))
            validator_result_counts[validator_result or "unrecorded"] = (
                validator_result_counts.get(validator_result or "unrecorded", 0) + 1
            )
            closure_durability = validate_closure_durability(runtime.get("closure_durability"))
            closure_durability_counts[closure_durability or "unrecorded"] = (
                closure_durability_counts.get(closure_durability or "unrecorded", 0) + 1
            )
            incident_code = runtime.get("incident_code")
            has_incident = isinstance(incident_code, str) and bool(incident_code.strip())
            if has_incident:
                incident_counts[incident_code.strip()] = incident_counts.get(incident_code.strip(), 0) + 1
            acceptance = normalize_acceptance(runtime.get("main_acceptance_status"))
            if acceptance in MAIN_ACCEPTED_STATES:
                accepted += 1
                if has_incident:
                    accepted_with_incident += 1
                elif identity["attempt_number"] == 1 and identity["retry_count"] == 0:
                    first_pass += 1
                if identity["retry_count"] >= 1:
                    after_retry += 1
            elif acceptance == "rejected":
                rejected += 1
            else:
                pending += 1
            elapsed = typed_int(runtime.get("observed_elapsed_seconds"), minimum=0)
            if elapsed is None:
                missing_elapsed += 1
            else:
                elapsed_values.append(elapsed)
        countable, route_note = route_countability(model_path)
        comparable_jobs = comparable_jobs_by_cohort.get((backend, model_path, phase), 0)
        if countable:
            comparable_countable_total += comparable_jobs
        cohorts.append(
            {
                "key": f"{backend}|{model_path}|{phase}",
                "execution_backend": backend,
                "model_path": model_path,
                "phase": phase,
                "route_countable": countable,
                "route_note": route_note,
                "lane_count": len(members),
                "comparable_main_accepted_job_count": comparable_jobs,
                "main_accepted_count": accepted,
                "first_pass_accepted_count": first_pass,
                "accepted_after_retry_count": after_retry,
                "accepted_with_incident_count": accepted_with_incident,
                "rejected_count": rejected,
                "pending_or_unreviewed_count": pending,
                "incident_count": sum(incident_counts.values()),
                "incident_counts_by_code": dict(sorted(incident_counts.items())),
                "validator_result_counts": dict(sorted(validator_result_counts.items())),
                "validator_result_recorded_count": sum(
                    count for key, count in validator_result_counts.items() if key != "unrecorded"
                ),
                "closure_durability_counts": dict(sorted(closure_durability_counts.items())),
                "retry_tax_total_retries": retry_tax,
                "elapsed_seconds": {
                    "observed_lane_count": len(elapsed_values),
                    "missing_lane_count": missing_elapsed,
                    "total_observed_seconds": sum(elapsed_values),
                    "mean_observed_seconds": (
                        round(sum(elapsed_values) / len(elapsed_values), 1) if elapsed_values else None
                    ),
                },
                "gate": {
                    "minimum_comparable_main_accepted_jobs": EFFICIENCY_MIN_COMPARABLE_MAIN_ACCEPTED_JOBS,
                    "progress": comparable_jobs if countable else 0,
                    "met": countable and comparable_jobs >= EFFICIENCY_MIN_COMPARABLE_MAIN_ACCEPTED_JOBS,
                },
            }
        )
    job_summary = {
        "comparable_main_accepted_job_total": comparable_countable_total,
        "mixed_route_parent_job_count_excluded": len(mixed_route_jobs),
        "main_accepted_lane_total": accepted_lane_total,
    }
    return cohorts, identity_gaps, scoped, job_summary


def load_economics_reference(token_ledger_path: Path) -> dict[str, Any]:
    reference: dict[str, Any] = {
        "source_path": str(token_ledger_path),
        "source_sha256": sha256_file(token_ledger_path),
        "source_generated_at_utc": None,
        "efficiency_measurement": None,
        "note": (
            "Economics (creditable tokens, baselines, savings gating) is owned by "
            "token_usage_ledger.efficiency_measurement; this ledger never recomputes credit."
        ),
    }
    try:
        payload = json.loads(token_ledger_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return reference
    reference["source_generated_at_utc"] = payload.get("generated_at_utc")
    measurement = payload.get("efficiency_measurement")
    if isinstance(measurement, dict):
        reference["efficiency_measurement"] = measurement
    return reference


def build_ledger(register_path: Path, token_ledger_path: Path) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    lanes: list[dict[str, Any]] = []
    total_lanes = 0
    try:
        register = json.loads(register_path.read_text(encoding="utf-8"))
        raw_lanes = register.get("lanes")
        if isinstance(raw_lanes, list):
            lanes = [lane for lane in raw_lanes if isinstance(lane, dict)]
            total_lanes = len(lanes)
        else:
            errors.append("register_schema_unexpected")
    except (OSError, json.JSONDecodeError):
        errors.append("register_missing_or_unreadable")

    cohorts, identity_gaps, scoped, job_summary = build_cohorts(lanes)
    comparable_job_total = job_summary["comparable_main_accepted_job_total"]
    gate_met = comparable_job_total >= EFFICIENCY_MIN_COMPARABLE_MAIN_ACCEPTED_JOBS

    economics = load_economics_reference(token_ledger_path)
    if economics["efficiency_measurement"] is None:
        warnings.append("economics_reference_missing")
    if identity_gaps:
        warnings.append("identity_gap_lanes_present")
    if not errors and not cohorts:
        warnings.append("no_cohorts_in_scope")
    if not errors and not gate_met:
        warnings.append("observation_gate_not_met")

    status = "blocked" if errors else ("warning" if warnings else "ok")
    return {
        "schema": SCHEMA,
        "generated_at_utc": utc_now_iso(),
        "status": status,
        "purpose": (
            "Report-only outcome-quality cohorts (first-pass acceptance, retry tax, incidents, "
            "elapsed) per execution backend/model/phase from Main-verified lane stamps, toward "
            "the like-for-like efficiency observation gate."
        ),
        "scope": {
            "register_path": str(register_path),
            "register_sha256": sha256_file(register_path),
            "efficiency_enforcement_start_utc": EFFICIENCY_ENFORCEMENT_START_UTC,
            "terminal_statuses": list(TERMINAL_STATUSES),
            "total_register_lanes": total_lanes,
            "enforcement_scope_terminal_model_lanes": scoped,
            "cohorted_lane_count": scoped - len(identity_gaps),
            "identity_gap_lane_count": len(identity_gaps),
            "identity_gap_lanes": identity_gaps[:IDENTITY_GAP_LIST_LIMIT],
        },
        "cohorts": cohorts,
        "observation_gate": {
            "minimum_comparable_main_accepted_jobs": EFFICIENCY_MIN_COMPARABLE_MAIN_ACCEPTED_JOBS,
            "comparable_main_accepted_job_total": comparable_job_total,
            "mixed_route_parent_job_count_excluded": job_summary["mixed_route_parent_job_count_excluded"],
            "main_accepted_lane_total": job_summary["main_accepted_lane_total"],
            "gate_unit": (
                "distinct single-route Main-accepted parent jobs on countable routes; "
                "mixed-route jobs are excluded, mirroring efficiency_measurement"
            ),
            "met": gate_met,
            "automatic_route_promotion_allowed": False,
            "promotion_allowed": False,
            "note": (
                "Observation only. No route ranking, promotion, or default change may be derived "
                "from this ledger; promotion stays a Main/owner decision after the gate and "
                "economics baseline are both satisfied."
            ),
        },
        "economics_reference": economics,
        "semantics": {
            "incident_success_credit": (
                "Lanes carrying an incident_code receive no first-pass success credit even when "
                "later accepted; they are reported under accepted_with_incident_count."
            ),
            "missing_elapsed": (
                "Lanes without a typed observed_elapsed_seconds are excluded from elapsed "
                "statistics; missing duration is never treated as zero latency."
            ),
            "acceptance_vocabulary": list(MAIN_ACCEPTED_STATES),
            "acceptance_normalization": "lowercase, hyphens normalized to underscores",
            "terminal_outcome_contract": (
                "validator_result and closure_durability come from the "
                "veritas.terminal_outcome_contract.v1 closeout fields; lanes stamped "
                "before the contract report them under the 'unrecorded' bucket and are "
                "never inferred."
            ),
        },
        "authority_boundary": {
            "review_only": True,
            "report_only": True,
            "register_mutation_allowed": False,
            "route_promotion_allowed": False,
            "automatic_route_promotion_allowed": False,
            "savings_claim_allowed": False,
            "canon_or_portfolio_mutation_allowed": False,
            "capital_deployment_approved": False,
            "trade_or_execution_approved": False,
            "paper_or_live_execution_allowed": False,
            "brokerage_or_account_action_allowed": False,
            "owner_approval_inferred": False,
        },
        "stop_lines": [
            "This ledger reads the lane register and token-usage ledger read-only; it never "
            "mutates lanes, credit, routing defaults, cron, config, canon, or portfolio state.",
            "Cohort counts are observation evidence only and grant no promotion, savings, "
            "approval, or execution authority.",
        ],
        "validation": {
            "status": status,
            "errors": errors,
            "warnings": warnings,
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Report-only efficiency cohort ledger")
    parser.add_argument("--register", default=str(DEFAULT_REGISTER_PATH))
    parser.add_argument("--token-ledger", default=str(DEFAULT_TOKEN_LEDGER_PATH))
    parser.add_argument("--json-out", default=str(DEFAULT_OUTPUT_PATH))
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    args = parser.parse_args(argv)

    ledger = build_ledger(Path(args.register), Path(args.token_ledger))
    if args.write:
        atomic_write_json(Path(args.json_out), ledger)
        print(f"wrote {args.json_out}")
    gate = ledger["observation_gate"]
    print(
        "efficiency cohort ledger: status={status} cohorts={cohorts} "
        "comparable_jobs={jobs}/{minimum} mixed_excluded={mixed} gate_met={met}".format(
            status=ledger["status"],
            cohorts=len(ledger["cohorts"]),
            jobs=gate["comparable_main_accepted_job_total"],
            minimum=gate["minimum_comparable_main_accepted_jobs"],
            mixed=gate["mixed_route_parent_job_count_excluded"],
            met=gate["met"],
        )
    )
    if args.validate:
        validation = ledger["validation"]
        print(
            f"validation: {validation['status']} errors={validation['errors']} "
            f"warnings={validation['warnings']}"
        )
        if validation["status"] == "blocked":
            return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
