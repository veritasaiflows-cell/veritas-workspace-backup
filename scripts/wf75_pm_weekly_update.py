from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, atomic_write_text

WORKSPACE = Path(__file__).resolve().parents[1]
DEFAULT_JSON = WORKSPACE / "tmp" / "wf75-pm-weekly-update.json"
DEFAULT_MD = DEFAULT_JSON.with_suffix(".md")

PLAN_PATH = WORKSPACE / "tmp" / "wf75-service-led-saas-readiness-plan.json"
PACKET_PATH = WORKSPACE / "tmp" / "operator-packets" / "retail-saas-wf75.json"
PM_VALIDATION_PATH = WORKSPACE / "tmp" / "veritas-pm-department-validation.json"
SERVICE_STATE_PATH = WORKSPACE / "tmp" / "wf75-service-state-current.json"
SQLITE_CONTROL_PLANE_PATH = WORKSPACE / "tmp" / "wf75-service-state-sqlite.json"
OPERATOR_QUEUE_PATH = WORKSPACE / "tmp" / "wf75-operator-queue.json"
OPERATOR_CONSOLE_PATH = WORKSPACE / "tmp" / "wf75-operator-console.json"
MOVEMENT_PATH = WORKSPACE / "tmp" / "wf75-automation-movement.json"
ARTIFACT_ONLY_HANDOFF_PATH = WORKSPACE / "tmp" / "wf75-artifact-only-pm-handoff.json"
PM_READINESS_BRIEF_PATH = WORKSPACE / "tmp" / "wf75-pm-readiness-brief.json"
HARNESS_SCORECARD_PATH = WORKSPACE / "tmp" / "veritas-harness-scorecard.json"
MACRO_EVENT_CALENDAR_PATH = WORKSPACE / "tmp" / "macro-event-calendar.json"
ACTIVE_WORKFLOWS = WORKSPACE / "06. Playbooks" / "Active Workflows.md"
WF75_CONTINUITY = (
    WORKSPACE
    / "06. Playbooks"
    / "Project Continuity"
    / "Workflow 75 - AI Productivity and Business Opportunity Intelligence Expansion.md"
)

AUTHORITY_FALSE_KEYS = [
    "public_launch_ready",
    "real_customer_data_allowed",
    "external_delivery_allowed",
    "legal_or_compliance_ready",
    "trading_account_or_paper_execution_allowed",
    "source_licensing_assumed",
]


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def relpath(path: Path) -> str:
    try:
        return str(path.relative_to(WORKSPACE)).replace("\\", "/")
    except ValueError:
        return str(path)


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def require_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise SystemExit(f"required artifact missing: {path}")
    return load_json(path)


def first_items(items: list[Any], limit: int) -> list[Any]:
    return items[:limit]


def proof_summary(packet: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in packet.get("proof_artifacts") or []:
        if not isinstance(item, dict):
            continue
        rows.append(
            {
                "path": item.get("path"),
                "status": item.get("status", "present" if item.get("exists") else "missing"),
                "required": bool(item.get("required")),
                "exists": bool(item.get("exists")),
            }
        )
    return rows


def build_update() -> dict[str, Any]:
    plan = require_json(PLAN_PATH)
    packet = require_json(PACKET_PATH)
    service_state = require_json(SERVICE_STATE_PATH)
    sqlite_control_plane = require_json(SQLITE_CONTROL_PLANE_PATH)
    operator_queue = require_json(OPERATOR_QUEUE_PATH)
    operator_console = load_json(OPERATOR_CONSOLE_PATH) if OPERATOR_CONSOLE_PATH.exists() else {"status": "missing"}
    movement = require_json(MOVEMENT_PATH)
    artifact_handoff = load_json(ARTIFACT_ONLY_HANDOFF_PATH) if ARTIFACT_ONLY_HANDOFF_PATH.exists() else {"status": "missing"}
    pm_readiness_brief = load_json(PM_READINESS_BRIEF_PATH) if PM_READINESS_BRIEF_PATH.exists() else {"status": "not_yet_rendered"}
    harness_scorecard = load_json(HARNESS_SCORECARD_PATH) if HARNESS_SCORECARD_PATH.exists() else {"status": "missing"}
    macro_calendar = load_json(MACRO_EVENT_CALENDAR_PATH) if MACRO_EVENT_CALENDAR_PATH.exists() else {"status": "missing"}
    pm_validation = load_json(PM_VALIDATION_PATH) if PM_VALIDATION_PATH.exists() else {"status": "missing"}

    boundaries = plan.get("authority_boundaries") if isinstance(plan.get("authority_boundaries"), dict) else {}
    authority_errors = [key for key in AUTHORITY_FALSE_KEYS if boundaries.get(key) is not False]

    phases = [phase for phase in plan.get("phases") or [] if isinstance(phase, dict)]
    blockers = [item for item in plan.get("blockers") or [] if isinstance(item, dict)]
    trust_gates = packet.get("trust_gates_missing") or []

    phase_now = first_items(phases, 2)
    upcoming = []
    for phase in phase_now:
        for deliverable in phase.get("deliverables") or []:
            upcoming.append(
                {
                    "enhancement": deliverable,
                    "phase": phase.get("phase"),
                    "timing": phase.get("weeks"),
                    "source": phase.get("name"),
                    "status": "planned_internal_service_led",
                }
            )

    proof = proof_summary(packet)
    validation_status = {
        "operator_packet": (packet.get("validation") or {}).get("status"),
        "service_state": (service_state.get("validation") or {}).get("status"),
        "sqlite_wal_control_plane": (sqlite_control_plane.get("validation") or {}).get("status"),
        "operator_queue": (operator_queue.get("validation") or {}).get("status"),
        "operator_console": (operator_console.get("validation") or {}).get("status"),
        "automation_movement": (movement.get("validation") or {}).get("status"),
        "artifact_only_pm_handoff": (artifact_handoff.get("validation") or {}).get("status"),
        "pm_readiness_brief": (pm_readiness_brief.get("validation") or {}).get("status", pm_readiness_brief.get("status")),
        "veritas_harness_scorecard": harness_scorecard.get("status"),
        "veritas_harness_summary": harness_scorecard.get("summary") or {},
        "macro_event_calendar": (macro_calendar.get("validation") or {}).get("status", macro_calendar.get("status")),
        "macro_event_calendar_summary": macro_calendar.get("summary") or {},
        "pm_department_validation": pm_validation.get("status"),
        "proof_required_present": sum(1 for row in proof if row["required"] and row["exists"]),
        "proof_required_total": sum(1 for row in proof if row["required"]),
        "authority_errors": authority_errors,
    }

    status = "ready_for_internal_pm_review" if not authority_errors and pm_validation.get("status") == "ok" else "blocked"

    return {
        "schema": "veritas.wf75.pm_weekly_update.v1",
        "generated_at_utc": utc_now_iso(),
        "workflow": "WF75",
        "status": status,
        "headline": "WF75 is the active product-readiness sprint: anonymous-scenario internal/service-led work can advance with real public evidence; public/customer/external use remains blocked.",
        "readiness": plan.get("readiness_target"),
        "current_phase": packet.get("current_phase"),
        "timeline": [
            {
                "phase": phase.get("phase"),
                "weeks": phase.get("weeks"),
                "name": phase.get("name"),
                "objective": phase.get("objective"),
                "acceptance_criteria": phase.get("acceptance_criteria") or [],
            }
            for phase in phases
        ],
        "completed_this_week": [
            "PM department skill created and routed for weekly updates, WF75 timelines, roadmaps, and PDF/presentation handoffs.",
            "PDF skill updated so WF75 PM/readiness packets are first-class internal deliverables.",
            "WF75 service-led readiness plan exists and validates as internal_service_led_readiness_plan_ready.",
            "Phase C/D JSON service-state, service-run, operator queue, and movement proof exist for anonymous-scenario handoff.",
            "SQLite WAL control-plane proof exists for local Veritas artifact refs, queue state, and one-worker claim exclusion.",
            "Artifact-only PM handoff exists and validates from WF77 bridge, renderer regression, scenario library, service state, operator queue, PM update, and SQLite control-plane proof.",
            "Retail SaaS operator packet is structurally valid and keeps all customer/external/execution authority false.",
            "Veritas harness scorecard now classifies command/tool failures separately from validator and authority failures.",
            "Macro-event calendar is now a first-class proof artifact for CPI, PPI, labor, FOMC, and PCE tracking.",
        ],
        "upcoming_enhancements": upcoming,
        "blockers_and_decisions": [
            {
                "id": blocker.get("id"),
                "blocker": blocker.get("blocker"),
                "blocks": blocker.get("blocks") or [],
                "required_resolution": blocker.get("required_resolution"),
            }
            for blocker in blockers
        ],
        "trust_gates_missing": trust_gates,
        "proof": proof,
        "validation_status": validation_status,
        "presentation_handoff": {
            "audience": "Randall / internal operator review",
            "purpose": "Weekly WF75 PM readiness update and enhancement roadmap.",
            "slide_outline": [
                "Current verdict and readiness target",
                "6-10 week timeline",
                "Completed this week",
                "Upcoming enhancements",
                "Blockers and owner decisions",
                "Proof and validation status",
                "Next sprint focus",
            ],
            "source_stack": [
                relpath(ACTIVE_WORKFLOWS),
                relpath(WF75_CONTINUITY),
                relpath(PLAN_PATH),
                relpath(PACKET_PATH),
                relpath(SERVICE_STATE_PATH),
                relpath(SQLITE_CONTROL_PLANE_PATH),
                relpath(OPERATOR_QUEUE_PATH),
                relpath(OPERATOR_CONSOLE_PATH),
                relpath(MOVEMENT_PATH),
                relpath(ARTIFACT_ONLY_HANDOFF_PATH),
                relpath(PM_READINESS_BRIEF_PATH),
                relpath(HARNESS_SCORECARD_PATH),
                relpath(MACRO_EVENT_CALENDAR_PATH),
                relpath(PM_VALIDATION_PATH),
            ],
        },
        "next_safe_action": "Use this weekly PM surface to drive the next WF75 sprint: keep supplemental WF77 price evidence, macro-event calendar, renderer/export regression, scenario-template library, service-state, SQLite WAL control-plane, operator queue, and artifact-only PM handoff proof fresh, then build the next operator-console/service-state slice.",
        "authority_boundary": "Internal review/proof only. No public launch, real customer data, external delivery, source-licensing claim, legal/compliance claim, portfolio/canon mutation, trading, account, paper/live action, or owner approval inference.",
    }


def render_markdown(update: dict[str, Any]) -> str:
    lines = [
        "# WF75 PM Weekly Update",
        "",
        f"- Generated: `{update['generated_at_utc']}`",
        f"- Status: `{update['status']}`",
        f"- Current phase: {update.get('current_phase')}",
        "",
        "## Verdict",
        "",
        update["headline"],
        "",
        "## Timeline",
        "",
    ]
    for phase in update.get("timeline") or []:
        lines.append(f"- Phase {phase.get('phase')} ({phase.get('weeks')}): {phase.get('name')} - {phase.get('objective')}")
    lines.extend(["", "## Completed This Week", ""])
    lines.extend(f"- {item}" for item in update.get("completed_this_week") or [])
    lines.extend(["", "## Upcoming Enhancements", ""])
    for item in update.get("upcoming_enhancements") or []:
        lines.append(f"- {item.get('timing')} / Phase {item.get('phase')}: {item.get('enhancement')}")
    lines.extend(["", "## Blockers And Decisions", ""])
    for item in update.get("blockers_and_decisions") or []:
        lines.append(f"- {item.get('id')}: {item.get('blocker')} Resolution: {item.get('required_resolution')}")
    lines.extend(["", "## Proof", ""])
    validation = update.get("validation_status") or {}
    lines.append(f"- Operator packet validation: `{validation.get('operator_packet')}`")
    lines.append(f"- Service-state validation: `{validation.get('service_state')}`")
    lines.append(f"- SQLite WAL control-plane validation: `{validation.get('sqlite_wal_control_plane')}`")
    lines.append(f"- Operator queue validation: `{validation.get('operator_queue')}`")
    lines.append(f"- Operator console validation: `{validation.get('operator_console')}`")
    lines.append(f"- Automation movement validation: `{validation.get('automation_movement')}`")
    lines.append(f"- Artifact-only PM handoff validation: `{validation.get('artifact_only_pm_handoff')}`")
    lines.append(f"- PM readiness brief validation: `{validation.get('pm_readiness_brief')}`")
    harness = validation.get("veritas_harness_summary") or {}
    lines.append(f"- Veritas harness scorecard: `{validation.get('veritas_harness_scorecard')}` ({harness.get('pass_count')} pass / {harness.get('warning_count')} warn / {harness.get('failure_count')} fail)")
    macro = validation.get("macro_event_calendar_summary") or {}
    lines.append(f"- Macro event calendar: `{validation.get('macro_event_calendar')}` / next `{macro.get('next_event_date')}` `{macro.get('next_event_metric')}` / next 14 days `{macro.get('next_14_day_count')}`")
    lines.append(f"- PM department validation: `{validation.get('pm_department_validation')}`")
    lines.append(f"- Required proof present: `{validation.get('proof_required_present')}/{validation.get('proof_required_total')}`")
    lines.extend(["", "## Next Safe Action", "", update["next_safe_action"], "", "## Boundary", "", update["authority_boundary"], ""])
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate the WF75 PM weekly update from live readiness artifacts.")
    parser.add_argument("--write", action="store_true", help="Write JSON output.")
    parser.add_argument("--write-md", action="store_true", help="Also write the optional human-readable Markdown digest.")
    parser.add_argument("--validate", action="store_true", help="Fail if generated update is blocked or malformed.")
    parser.add_argument("--json-out", default=str(DEFAULT_JSON), help="JSON output path for --write.")
    parser.add_argument("--md-out", default=str(DEFAULT_MD), help="Markdown output path for --write-md.")
    return parser.parse_args()


def validate(update: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if update.get("status") != "ready_for_internal_pm_review":
        errors.append(f"unexpected status: {update.get('status')}")
    validation = update.get("validation_status") or {}
    if validation.get("authority_errors"):
        errors.append(f"authority errors present: {validation.get('authority_errors')}")
    for key in ("service_state", "sqlite_wal_control_plane", "operator_queue", "operator_console", "automation_movement", "artifact_only_pm_handoff"):
        if validation.get(key) != "ok":
            errors.append(f"{key} validation not ok: {validation.get(key)}")
    if validation.get("macro_event_calendar") != "ok":
        errors.append(f"macro event calendar not ok: {validation.get('macro_event_calendar')}")
    if validation.get("proof_required_present") != validation.get("proof_required_total"):
        errors.append("not all required proof artifacts are present")
    if not update.get("timeline"):
        errors.append("timeline missing")
    if not update.get("upcoming_enhancements"):
        errors.append("upcoming enhancements missing")
    return errors


def main() -> int:
    args = parse_args()
    update = build_update()
    errors = validate(update) if args.validate else []
    update["validation_errors"] = errors
    if errors:
        update["status"] = "blocked"

    if args.write:
        json_out = Path(args.json_out)
        if not json_out.is_absolute():
            json_out = WORKSPACE / json_out
        atomic_write_json(json_out, update)
        update["outputs"] = {"json": relpath(json_out)}
    if args.write_md:
        md_out = Path(args.md_out)
        if not md_out.is_absolute():
            md_out = WORKSPACE / md_out
        atomic_write_text(md_out, render_markdown(update))
        outputs = update.setdefault("outputs", {})
        if isinstance(outputs, dict):
            outputs["markdown"] = relpath(md_out)

    print(json.dumps(update, indent=2))
    return 0 if not errors else 2


if __name__ == "__main__":
    raise SystemExit(main())
