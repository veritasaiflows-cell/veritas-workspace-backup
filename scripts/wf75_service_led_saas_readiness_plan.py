#!/usr/bin/env python3
"""Generate a bounded WF75 service-led SaaS readiness plan.

This planner is internal/service-led only. It does not grant public launch,
customer data, external delivery, legal/compliance, source licensing, or
finance execution authority. The active WF75 route is infrastructure-first:
build the local service substrate for the 6-10 week plan instead of spending
the sprint on privacy/licensing/counsel decision packets.

Current fixture posture: do not build fake-person customer personas. Use
anonymous service request scenarios with real public market/reference evidence
where available, while keeping real customer data, suitability data, external
delivery, and personalized advice blocked.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
DEFAULT_OUTPUT = TMP / "wf75-service-led-saas-readiness-plan.json"
DEFAULT_FRESHNESS_HOURS = 24.0
SERVICE_STATE_EVIDENCE = {
    "service_state_store": {
        "artifact": "tmp/wf75-service-state-current.json",
        "schema": "veritas.wf75.service_state.v1",
        "statuses": {"ok"},
    },
    "operator_console_work_queue": {
        "artifact": "tmp/wf75-operator-queue.json",
        "schema": "veritas.wf75.operator_queue.v1",
        "statuses": {"ok"},
    },
    "operator_console_control_cockpit": {
        "artifact": "tmp/wf75-operator-console.json",
        "schema": "veritas.wf75.operator_console.v1",
        "statuses": {"ready"},
    },
    "sqlite_wal_control_plane": {
        "artifact": "tmp/wf75-service-state-sqlite.json",
        "schema": "veritas.wf75.service_state_sqlite_control_plane.v1",
        "statuses": {"control_plane_ready"},
    },
    "customer_safe_renderer_export_pipeline": {
        "artifact": "tmp/wf75-renderer-export-regression.json",
        "schema": "veritas.wf75.renderer_export_regression.v1",
        "statuses": {"ok"},
    },
    # One proof artifact supports two distinct capabilities. Counts must expose
    # that distinction instead of presenting nine capabilities as nine files.
    "qa_regression_harness": {
        "artifact": "tmp/wf75-renderer-export-regression.json",
        "schema": "veritas.wf75.renderer_export_regression.v1",
        "statuses": {"ok"},
    },
    "scenario_template_library": {
        "artifact": "tmp/wf75-scenario-template-library.json",
        "schema": "veritas.wf75.scenario_template_library.v1",
        "statuses": {"ok"},
    },
    "artifact_only_pm_handoff": {
        "artifact": "tmp/wf75-artifact-only-pm-handoff.json",
        "schema": "veritas.wf75.artifact_only_pm_handoff.v1",
        "statuses": {"ready_for_internal_artifact_only_pm_handoff"},
    },
    "cron_main_handoff_expansion": {
        "artifact": "tmp/wf75-automation-movement.json",
        "schema": "veritas.wf75.automation_movement.v1",
        "statuses": {"ok"},
    },
}

REQUIRED_BOUNDARY_FALSE = [
    "public_launch_ready",
    "real_customer_data_allowed",
    "external_delivery_allowed",
    "legal_or_compliance_ready",
    "trading_account_or_paper_execution_allowed",
    "source_licensing_assumed",
]

REQUIRED_INFRASTRUCTURE_GAPS = [
    "service_state_store",
    "operator_console_work_queue",
    "operator_console_control_cockpit",
    "sqlite_wal_control_plane",
    "customer_safe_renderer_export_pipeline",
    "qa_regression_harness",
    "scenario_template_library",
    "artifact_only_pm_handoff",
    "cron_main_handoff_expansion",
]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_utc(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc)


def inspect_evidence(
    capability: str,
    contract: dict[str, Any],
    *,
    root: Path,
    now: datetime,
    freshness_hours: float,
) -> dict[str, Any]:
    artifact = str(contract["artifact"])
    path = root / Path(artifact)
    expected_schema = str(contract["schema"])
    allowed_statuses = sorted(str(value) for value in contract["statuses"])
    row: dict[str, Any] = {
        "capability": capability,
        "artifact": artifact.replace("\\", "/"),
        "exists": path.is_file(),
        "json_object_valid": False,
        "expected_schema": expected_schema,
        "schema": None,
        "schema_valid": False,
        "allowed_statuses": allowed_statuses,
        "status": None,
        "status_valid": False,
        "validation_status": None,
        "validation_valid": False,
        "generated_at_utc": None,
        "age_hours": None,
        "freshness_limit_hours": freshness_hours,
        "fresh": False,
        "evidence_state": "missing",
        "errors": [],
    }
    errors = row["errors"]
    if not row["exists"]:
        errors.append("artifact missing")
        return row

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        row["evidence_state"] = "invalid_json"
        errors.append(f"invalid JSON: {exc}")
        return row
    if not isinstance(payload, dict):
        row["evidence_state"] = "invalid_json_object"
        errors.append("JSON root must be an object")
        return row
    row["json_object_valid"] = True

    row["schema"] = payload.get("schema")
    row["schema_valid"] = row["schema"] == expected_schema
    if not row["schema_valid"]:
        errors.append(f"schema mismatch: expected {expected_schema!r}, got {row['schema']!r}")

    row["status"] = payload.get("status")
    row["status_valid"] = row["status"] in allowed_statuses
    if not row["status_valid"]:
        errors.append(f"status not allowed: {row['status']!r}")

    validation = payload.get("validation")
    if isinstance(validation, dict):
        row["validation_status"] = validation.get("status")
        row["validation_valid"] = row["validation_status"] == "ok" and not (validation.get("errors") or [])
    if not row["validation_valid"]:
        errors.append("nested validation must be status=ok with no errors")

    row["generated_at_utc"] = payload.get("generated_at_utc")
    generated_at = parse_utc(row["generated_at_utc"])
    if generated_at is None:
        errors.append("generated_at_utc must be a timezone-aware timestamp")
    else:
        age_hours = (now - generated_at).total_seconds() / 3600.0
        row["age_hours"] = round(age_hours, 3)
        # Permit only a small producer/clock skew; future-dated proof is not
        # fresh operational evidence.
        row["fresh"] = -5.0 / 60.0 <= age_hours <= freshness_hours
        if not row["fresh"]:
            errors.append(
                f"artifact stale or future-dated: age_hours={row['age_hours']} limit={freshness_hours}"
            )

    if errors:
        row["evidence_state"] = "evidence_gap"
    else:
        row["evidence_state"] = "evidence_current"
    return row


def build_plan(
    *,
    root: Path = ROOT,
    now: datetime | None = None,
    freshness_hours: float = DEFAULT_FRESHNESS_HOURS,
) -> dict[str, Any]:
    observed_at = now or datetime.now(timezone.utc)
    if observed_at.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    observed_at = observed_at.astimezone(timezone.utc)
    implementation_progress = {
        capability: inspect_evidence(
            capability,
            contract,
            root=root,
            now=observed_at,
            freshness_hours=freshness_hours,
        )
        for capability, contract in SERVICE_STATE_EVIDENCE.items()
    }
    unique_artifacts = {row["artifact"] for row in implementation_progress.values()}
    current_capabilities = [
        capability
        for capability, row in implementation_progress.items()
        if row["evidence_state"] == "evidence_current"
    ]
    gap_capabilities = sorted(set(implementation_progress) - set(current_capabilities))
    current_unique_artifacts = {
        row["artifact"]
        for row in implementation_progress.values()
        if row["evidence_state"] == "evidence_current"
    }
    all_evidence_current = not gap_capabilities
    plan_status = (
        "internal_service_led_readiness_plan_ready"
        if all_evidence_current
        else "internal_service_led_evidence_gaps"
    )
    next_safe_action = (
        "Use this as the internal WF75 infrastructure sequence while keeping every evidence contract current and validator-clean. Do not advance to real customer data, external delivery, legal/compliance claims, source-licensing claims, or trading/account/paper execution."
        if all_evidence_current
        else "Repair and regenerate the evidence gaps listed in evidence_summary before treating the internal plan as current. Do not infer implementation or readiness from file presence."
    )
    return {
        "schema": "veritas.wf75.service_led_saas_readiness_plan.v1",
        "generated_at_utc": observed_at.replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "workflow": "WF75",
        "status": plan_status,
        "readiness_target": {
            "band": "55-65%",
            "classification": "future_target_only",
            "current_readiness_percentage": None,
            "meaning": "Future target only for internal/service-led SaaS readiness over 6-10 weeks. It is not a claim of current readiness and not public launch readiness, customer-data readiness, legal/compliance readiness, source-licensing readiness, or execution readiness.",
            "current_target_posture": "Build the local infrastructure substrate for a manually operated, internally validated, service-led retail finance intelligence workflow.",
        },
        "product_scope": {
            "name": "Retail Investor Finance Intelligence SaaS",
            "shape": "infrastructure-first service-led SaaS readiness plan, internal/operator-led first",
            "audience": "self-directed retail investors as a future target, not current real users",
            "value_boundary": "Evidence organization, freshness labels, watchlist research, and customer-safe educational briefings.",
            "fixture_posture": "Use anonymous service request scenarios backed by real public ticker/evidence data where available. Do not create fake-person personas, fake portfolio balances, fake suitability profiles, or fake risk profiles as product truth.",
            "not_in_scope": [
                "public launch",
                "real customer intake",
                "external delivery",
                "brokerage or account connection",
                "paper or live trading",
                "personalized regulated investment advice",
                "tax/legal/retirement planning",
                "source-licensing or compliance claims",
            ],
        },
        "authority_boundaries": {
            "public_launch_ready": False,
            "real_customer_data_allowed": False,
            "external_delivery_allowed": False,
            "legal_or_compliance_ready": False,
            "trading_account_or_paper_execution_allowed": False,
            "source_licensing_assumed": False,
            "customer_safe_exports_only_after_validator": True,
            "generated_artifact_is_review_surface_only": True,
            "notes": [
                "No customer data may be used in this plan.",
                "Anonymous service request scenarios may use real public company/market/reference evidence; they must not include personal identity, customer portfolio, suitability, income, net-worth, tax, retirement, brokerage, account, or credential data.",
                "Fake-person customer personas are deprecated for the active sprint; model service jobs, request types, scenarios, ticker sets, evidence inputs, validation state, blockers, and next operator action instead.",
                "No external delivery is authorized by this plan.",
                "No artifact produced here authorizes outreach, delivery, account setup, source use, legal claims, compliance claims, trading, account action, paper execution, or portfolio/canon mutation.",
                "Privacy/licensing/counsel decision-packet work is not the active route for the sprint; the current route is infrastructure buildout with anonymous service scenarios and real public evidence only where safe.",
                "All finance content remains educational/research support until separate qualified review and owner approval gates exist.",
            ],
        },
        "implementation_progress": implementation_progress,
        "evidence_summary": {
            "all_evidence_current": all_evidence_current,
            "freshness_limit_hours": freshness_hours,
            "capability_count": len(implementation_progress),
            "unique_artifact_count": len(unique_artifacts),
            "current_capability_count": len(current_capabilities),
            "current_unique_artifact_count": len(current_unique_artifacts),
            "gap_count": len(gap_capabilities),
            "gap_capabilities": gap_capabilities,
        },
        "blockers": [
            {
                "id": "service_state_store",
                "blocker": "JSON v0 service-state is evidenced only when tmp/wf75-service-state-current.json is a current object with the expected schema, allowed status, and clean nested validation.",
                "blocks": ["repeatable operator workflow", "multi-run status tracking", "service dashboard readiness"],
                "required_resolution": "Keep JSON v0 validator clean and keep supplemental WF77 public price evidence fresh; use SQLite WAL only as a local control-plane index/queue, not as customer/canon truth.",
            },
            {
                "id": "operator_console_work_queue",
                "blocker": "JSON v0 operator queue is evidenced only when tmp/wf75-operator-queue.json passes schema, status, nested-validation, and freshness checks.",
                "blocks": ["efficient service operation", "manual QA throughput", "weekly readiness proof"],
                "required_resolution": "Keep the queue validator clean and consume it through the local operator console/control cockpit.",
            },
            {
                "id": "operator_console_control_cockpit",
                "blocker": "Local operator console/control cockpit is evidenced only when the JSON proof passes schema, status, nested-validation, and freshness checks; file presence alone is insufficient.",
                "blocks": ["repeatable service operation", "operator visibility", "control-plane adoption"],
                "required_resolution": "Use the console as the primary internal WF75 operating view while keeping it local-only and artifact-backed.",
            },
            {
                "id": "sqlite_wal_control_plane",
                "blocker": "SQLite WAL control-plane proof is evidenced only when tmp/wf75-service-state-sqlite.json is current and validator-clean with the expected schema and status; database presence alone is insufficient.",
                "blocks": ["multi-request rehearsal", "safe worker-claim proof", "faster status/control-plane queries"],
                "required_resolution": "Keep WAL, busy_timeout, foreign_keys, artifact refs, queue rows, and one-worker claim exclusion validating; do not treat the DB as finance canon, customer DB, approval authority, SQL/ticker import, or execution surface.",
            },
            {
                "id": "customer_safe_renderer_export_pipeline",
                "blocker": "Reusable local renderer/export regression proof is evidenced only by a current, schema-correct, allowed-status, validator-clean JSON object; a full UI/operator console remains future work.",
                "blocks": ["repeatable customer-safe brief generation", "demo packet production", "renderer regression testing"],
                "required_resolution": "Keep the renderer/export regression harness clean and fail-closed before any new scenario, UI surface, or PM handoff consumes the outputs.",
            },
            {
                "id": "qa_regression_harness",
                "blocker": "Compact repeated-run regression proof shares the renderer artifact and is evidenced only when that artifact is current and validator-clean; future expansion should add seeded edge cases only for real failure modes.",
                "blocks": ["safe automation cadence", "confidence in repeated demos", "main-session handoff quality"],
                "required_resolution": "Keep clean scenarios passing and seeded-bad scenarios failing before treating any regenerated output as review-ready.",
            },
            {
                "id": "scenario_template_library",
                "blocker": "Anonymous scenario-template library is evidenced only when its JSON proof is current, schema-correct, allowed-status, and validator-clean; future work should expand it only with validator-backed scenario needs.",
                "blocks": ["demo realism", "QA coverage", "presentation-ready readiness proof"],
                "required_resolution": "Maintain at least three anonymous scenarios covering AI infrastructure, Materials diversification, and supplemental-price/risk edge cases without fake-person profiles.",
            },
            {
                "id": "artifact_only_pm_handoff",
                "blocker": "Artifact-only PM handoff is evidenced only when its JSON proof is current, schema-correct, allowed-status, and validator-clean.",
                "blocks": ["PM/operator pickup", "main-session handoff clarity", "low-noise sprint continuation"],
                "required_resolution": "Keep the handoff fed by WF77 bridge, renderer regression, scenario library, service state, operator queue, PM weekly update, and SQLite WAL control-plane proof.",
            },
            {
                "id": "cron_main_handoff_expansion",
                "blocker": "Phase D movement is evidenced only when its JSON proof is current, schema-correct, allowed-status, and validator-clean; scheduled cron expansion remains blocked until a job card is deliberately approved.",
                "blocks": ["steady 6-10 week execution cadence", "low-noise progress reporting", "regression escalation"],
                "required_resolution": "Use heartbeat/main-session pickup first; only add cron after script/validator behavior is stable and a job card proves owner, artifacts, stop lines, and overlap rules.",
            },
        ],
        "phases": [
            {
                "phase": 1,
                "weeks": "1-2",
                "name": "Infrastructure Contract And State Model",
                "objective": "Freeze the service-state, artifact, renderer, and QA contracts before building more UI or automation.",
                "deliverables": [
                    "service-state table/JSON contract",
                    "run lifecycle state model",
                    "renderer/export contract",
                    "QA event contract",
                    "infrastructure backlog with stop lines",
                ],
                "acceptance_criteria": [
                    "Plan states internal/service-led only and repeats 55-65% readiness target as non-launch readiness.",
                    "All six authority boundary flags are false.",
                    "No wording implies legal, compliance, source, trading, account, paper, or customer-data authority.",
                    "Infrastructure contracts use anonymous service scenarios only, may reference real public market/evidence inputs, and do not touch finance canon or customer data.",
                ],
            },
            {
                "phase": 2,
                "weeks": "2-4",
                "name": "Anonymous-Scenario Service-State Prototype",
                "objective": "Implement the local service-state substrate and query packet for repeated internal demo runs.",
                "deliverables": [
                    "anonymous-scenario service-state SQLite or JSON store",
                    "SQLite WAL control-plane proof",
                    "service run writer",
                    "current status query packet",
                    "rollback/backup proof",
                    "production finance-canon isolation proof",
                ],
                "acceptance_criteria": [
                    "Runs use anonymous request scenarios with no personal/suitability/customer data; public ticker/evidence inputs are allowed when source-labeled.",
                    "Service-state writes are isolated from portfolio/canon/cache DBs.",
                    "Query packets expose status, QA state, failures, and next operator action.",
                    "Backups and rollback are proven before any repeated-run automation.",
                ],
            },
            {
                "phase": 3,
                "weeks": "4-6",
                "name": "Operator Console And Renderer Pipeline",
                "objective": "Build the local operator work queue and reusable customer-safe renderer/export pipeline.",
                "deliverables": [
                    "local operator queue/report",
                    "artifact-only PM handoff",
                    "renderer/export pipeline",
                    "QA failure reason taxonomy",
                    "non-advice disclaimer block",
                    "artifact index routing for WF75 outputs",
                ],
                "acceptance_criteria": [
                    "Every rendered field has a source category or explicit gap label.",
                    "QA blocks imperative buy/sell/hold language, price-target/upside framing, guaranteed returns, probability/win-rate claims, and execution urgency.",
                    "Operator status never exposes approval, trade readiness, account readiness, or paper execution readiness.",
                    "Service workflow can stop safely at validator_failed, source_gap, or needs_manual_review.",
                ],
            },
            {
                "phase": 4,
                "weeks": "6-8",
                "name": "Regression Harness And Demo Library",
                "objective": "Prove repeated scenario runs, seeded-bad failures, and multiple anonymous request templates without customer exposure.",
                "deliverables": [
                    "two to three additional anonymous service request scenarios",
                    "clean/seeded-bad regression harness",
                    "QA pass/fail summaries",
                    "operator effort/time log",
                    "manual improvement backlog",
                ],
                "acceptance_criteria": [
                    "Repeated demo runs are parseable, validator-clean, and manually reviewable.",
                    "Failures produce actionable blocker labels rather than green status.",
                    "No delivery, outreach, signup, real customer data, or external channel is used.",
                    "Readiness remains described as internal/service-led, not public launch.",
                ],
            },
            {
                "phase": 5,
                "weeks": "8-10",
                "name": "Infrastructure Automation And PM Handoff",
                "objective": "Wire the artifact-only builder/main-session handoff pattern around the new infrastructure proof.",
                "deliverables": [
                    "artifact-only infrastructure proof builder",
                    "main-session infrastructure handoff summary",
                    "readiness dashboard packet",
                    "cron-safe validation checklist",
                    "go/no-go infrastructure readiness summary",
                ],
                "acceptance_criteria": [
                    "Packet clearly says infrastructure is internal/anonymous-scenario only and not real-user readiness.",
                    "No legal/compliance readiness, source-licensing readiness, public launch readiness, or customer-data authority is claimed.",
                    "No trading, brokerage, account, paper-execution, or portfolio mutation feature is included.",
                    "Result can support the next infrastructure sprint without silently applying any external action.",
                ],
            },
        ],
        "validation_requirements": [
            "JSON artifact parses.",
            "Required phases 1-5 are present and cover weeks 1-10.",
            "Readiness target is exactly 55-65%, explicitly future-only, and scoped to internal/service-led readiness.",
            "Every capability artifact is a current JSON object with the expected schema, allowed status, and clean nested validation.",
            "Capability count and unique artifact count are reported separately.",
            "Required infrastructure gaps are present.",
            "Required authority flags remain false.",
            "Forbidden launch/customer/legal/source/execution authority is not asserted.",
        ],
        "next_safe_action": next_safe_action,
    }


def validate_plan(plan: dict[str, Any]) -> tuple[bool, list[str]]:
    errors: list[str] = []
    if plan.get("schema") != "veritas.wf75.service_led_saas_readiness_plan.v1":
        errors.append("schema mismatch")
    if plan.get("workflow") != "WF75":
        errors.append("workflow must be WF75")
    target = plan.get("readiness_target")
    if not isinstance(target, dict) or target.get("band") != "55-65%":
        errors.append("readiness target band must be 55-65%")
    elif target.get("classification") != "future_target_only" or target.get("current_readiness_percentage") is not None:
        errors.append("55-65% must remain a future target only, not a current-readiness claim")
    target_text = json.dumps(target, sort_keys=True).lower()
    if (
        "internal/service-led" not in target_text
        or "future target only" not in target_text
        or "not public launch" not in target_text
    ):
        errors.append("readiness target must be future-only, internal/service-led, and not public launch readiness")

    implementation_progress = plan.get("implementation_progress")
    current_capabilities: set[str] = set()
    if not isinstance(implementation_progress, dict):
        errors.append("implementation_progress must be an object")
        implementation_progress = {}
    for capability, contract in SERVICE_STATE_EVIDENCE.items():
        row = implementation_progress.get(capability)
        if not isinstance(row, dict):
            errors.append(f"missing evidence row: {capability}")
            continue
        expected_artifact = str(contract["artifact"]).replace("\\", "/")
        if row.get("artifact") != expected_artifact:
            errors.append(f"evidence artifact mismatch for {capability}")
        if row.get("expected_schema") != contract["schema"]:
            errors.append(f"expected schema contract mismatch for {capability}")
        if sorted(row.get("allowed_statuses") or []) != sorted(contract["statuses"]):
            errors.append(f"allowed status contract mismatch for {capability}")
        if row.get("evidence_state") == "evidence_current":
            required_true = (
                "exists",
                "json_object_valid",
                "schema_valid",
                "status_valid",
                "validation_valid",
                "fresh",
            )
            if all(row.get(field) is True for field in required_true) and not (row.get("errors") or []):
                current_capabilities.add(capability)
            else:
                errors.append(f"inconsistent current-evidence row: {capability}")
        else:
            detail = "; ".join(str(item) for item in (row.get("errors") or [])) or "evidence not current"
            errors.append(f"evidence gap for {capability}: {detail}")

    summary = plan.get("evidence_summary")
    expected_capability_count = len(SERVICE_STATE_EVIDENCE)
    expected_unique_artifact_count = len({str(row["artifact"]) for row in SERVICE_STATE_EVIDENCE.values()})
    all_evidence_current = len(current_capabilities) == expected_capability_count
    if not isinstance(summary, dict):
        errors.append("evidence_summary must be an object")
    else:
        expected_values = {
            "all_evidence_current": all_evidence_current,
            "capability_count": expected_capability_count,
            "unique_artifact_count": expected_unique_artifact_count,
            "current_capability_count": len(current_capabilities),
            "gap_count": expected_capability_count - len(current_capabilities),
            "gap_capabilities": sorted(set(SERVICE_STATE_EVIDENCE) - current_capabilities),
        }
        for field, expected in expected_values.items():
            if summary.get(field) != expected:
                errors.append(f"evidence summary mismatch for {field}: expected {expected!r}")
        freshness_limit = summary.get("freshness_limit_hours")
        if not isinstance(freshness_limit, (int, float)) or isinstance(freshness_limit, bool) or freshness_limit <= 0:
            errors.append("evidence freshness limit must be positive")
        expected_current_unique = len(
            {
                str(SERVICE_STATE_EVIDENCE[capability]["artifact"])
                for capability in current_capabilities
            }
        )
        if summary.get("current_unique_artifact_count") != expected_current_unique:
            errors.append("evidence summary mismatch for current_unique_artifact_count")

    expected_status = (
        "internal_service_led_readiness_plan_ready"
        if all_evidence_current
        else "internal_service_led_evidence_gaps"
    )
    if plan.get("status") != expected_status:
        errors.append(f"status must be derived from evidence: expected {expected_status}")

    boundaries = plan.get("authority_boundaries")
    if not isinstance(boundaries, dict):
        errors.append("authority_boundaries must be an object")
    else:
        for key in REQUIRED_BOUNDARY_FALSE:
            if boundaries.get(key) is not False:
                errors.append(f"authority boundary must remain false: {key}")

    blockers = plan.get("blockers")
    blocker_ids = {row.get("id") for row in blockers if isinstance(row, dict)} if isinstance(blockers, list) else set()
    for blocker_id in REQUIRED_INFRASTRUCTURE_GAPS:
        if blocker_id not in blocker_ids:
            errors.append(f"missing infrastructure gap: {blocker_id}")

    phases = plan.get("phases")
    if not isinstance(phases, list) or len(phases) != 5:
        errors.append("expected exactly five phases")
    else:
        phase_numbers = [row.get("phase") for row in phases if isinstance(row, dict)]
        if phase_numbers != [1, 2, 3, 4, 5]:
            errors.append("phases must be numbered 1-5")
        weeks = [str(row.get("weeks") or "") for row in phases if isinstance(row, dict)]
        if weeks[0] != "1-2" or weeks[-1] != "8-10":
            errors.append("phases must span 1-10 weeks")
        for row in phases:
            if not isinstance(row, dict):
                continue
            if not row.get("acceptance_criteria"):
                errors.append(f"phase {row.get('phase')} missing acceptance criteria")

    all_text = json.dumps(plan, sort_keys=True).lower()
    required_phrases = [
        "no customer data",
        "no external delivery",
        "no legal/compliance",
        "no trading",
        "source-licensing",
        "not public launch",
    ]
    for phrase in required_phrases:
        if phrase not in all_text:
            errors.append(f"missing guardrail phrase: {phrase}")
    forbidden_greenlights = [
        "public launch ready",
        "real customer data allowed",
        "external delivery allowed",
        "compliance ready",
        "legal ready",
        "source licensing ready",
        "trading allowed",
        "paper execution allowed",
    ]
    for phrase in forbidden_greenlights:
        if phrase in all_text:
            errors.append(f"forbidden readiness claim present: {phrase}")
    return not errors, errors


def load_plan(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise SystemExit(f"Missing plan artifact: {path}") from exc
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Invalid JSON in {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise SystemExit(f"Plan artifact must be a JSON object: {path}")
    return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="JSON artifact output path.")
    parser.add_argument("--write", action="store_true", help="Write the plan artifact.")
    parser.add_argument("--validate", action="store_true", help="Validate the generated or existing plan artifact.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.write:
        plan = build_plan()
        atomic_write_json(args.output, plan)
    elif args.validate:
        plan = load_plan(args.output)
    else:
        plan = build_plan()
        print(json.dumps(plan, indent=2, sort_keys=True))
        return 0

    if args.validate or args.write:
        ok, errors = validate_plan(plan)
        if not ok:
            for error in errors:
                print(f"ERROR: {error}")
            return 1
        print(f"ok: {args.output}" if args.validate else f"wrote: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
