from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, atomic_write_text

WORKSPACE = Path(__file__).resolve().parents[1]
DEFAULT_JSON = WORKSPACE / "tmp" / "wf75-cron-automation-authority-plan.json"
DEFAULT_MD = DEFAULT_JSON.with_suffix(".md")
CRON_STORE = Path.home() / ".openclaw" / "cron" / "jobs.json"
WF75_OPERATOR_CONSOLE_JSON = "tmp/wf75-operator-console.json"
WF75_OPERATOR_CONSOLE_HTML = str(Path(WF75_OPERATOR_CONSOLE_JSON).with_suffix(".html")).replace("\\", "/")

BUILDER_NAME = "WF75 PM Weekly Artifact Builder"
HANDOFF_NAME = "WF75 PM Weekly Main Intelligence Handoff"
DISPATCHER_NAME = "PM - Main Session Continuation Dispatcher"
RECOMMENDED_SCENARIO_ID = "anon-risk-freshness-edge-cases-v1"


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_live_cron_jobs() -> list[dict[str, Any]]:
    if not CRON_STORE.exists():
        return []
    data = json.loads(CRON_STORE.read_text(encoding="utf-8"))
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        jobs = data.get("jobs")
        return jobs if isinstance(jobs, list) else []
    return []


def live_job_summary() -> dict[str, Any]:
    jobs = load_live_cron_jobs()
    names = {str(job.get("name")): job for job in jobs}
    return {
        "cron_store": str(CRON_STORE),
        "job_count": len(jobs),
        "builder_present": BUILDER_NAME in names,
        "handoff_present": HANDOFF_NAME in names,
        "dispatcher_present": DISPATCHER_NAME in names,
        "builder_job_id": names.get(BUILDER_NAME, {}).get("id"),
        "handoff_job_id": names.get(HANDOFF_NAME, {}).get("id"),
        "dispatcher_job_id": names.get(DISPATCHER_NAME, {}).get("id"),
    }


def builder_job_card() -> dict[str, Any]:
    return {
        "name": BUILDER_NAME,
        "window_family": "weekly / PM",
        "schedule": {"kind": "cron", "expr": "30 16 * * 5", "tz": "America/Phoenix"},
        "session_target": "isolated",
        "owner": "veritas-pm-department",
        "trigger_goal": "Refresh the full WF75 PM artifact chain: public price evidence, macro-event calendar, macro metrics, macro judgment, JSON-to-SQL promotion index, renderer/scenario proof, service state, SQLite WAL control plane, operator console/control cockpit, operator packet, PM update, artifact-only handoff, PDF brief, heartbeat pickup, and cron ledger.",
        "read_first": [
            "06. Playbooks/Cron Job Protocol.md",
            "skills/cron-automation-manager/SKILL.md",
            "skills/veritas-pm-department/SKILL.md",
            "skills/veritas-pdf-brief/SKILL.md",
            "tmp/operator-packets/retail-saas-wf75.json",
        ],
        "execute_in_order": [
            "python scripts\\wf77_supplemental_price_evidence.py --write --validate",
            "python scripts\\wf77_price_freshness_bridge.py --write --validate",
            "python scripts\\macro_event_calendar.py --write --validate",
            "python scripts\\macro_metrics_ingest.py --write --validate",
            "python scripts\\macro_judgment_draft.py --write --validate",
            "python scripts\\generic_intelligence_saas_pivot.py --write --write-db --validate",
            "python scripts\\wf75_scenario_template_library.py --write --validate",
            "python scripts\\wf75_renderer_export_regression.py --write --validate",
            f"python scripts\\wf75_service_state.py --scenario-id {RECOMMENDED_SCENARIO_ID} --write --validate",
            "python scripts\\wf75_service_state_sqlite.py --write --validate",
            "python scripts\\wf75_operator_console.py --write --validate",
            f"python scripts\\wf75_service_state.py --scenario-id {RECOMMENDED_SCENARIO_ID} --write --validate",
            "python scripts\\wf75_service_state_sqlite.py --write --validate",
            "python scripts\\wf75_operator_console.py --write --validate",
            "python scripts\\veritas_pm_department_validate.py --write",
            "python scripts\\operator_packet.py --workflow all --write --validate",
            "python scripts\\wf75_pm_weekly_update.py --write --validate",
            "python scripts\\wf75_artifact_only_pm_handoff.py --write --validate",
            "python scripts\\wf75_pm_readiness_pdf.py --write --validate",
            "python scripts\\wf75_pm_weekly_update.py --write --validate",
            "python scripts\\wf75_artifact_only_pm_handoff.py --write --validate",
            "python scripts\\json_sql_promotion_index.py --write --validate",
            "python scripts\\wf75_closeout_refresh.py --validation-budget shared --write --validate",
            "python scripts\\pm_control_packet.py --write --write-db --validate",
            "python scripts\\cron_operator_ledger.py --write --validate",
        ],
        "inspect_after_execution": [
            "tmp/wf77-supplemental-price-evidence.json",
            "tmp/wf77-price-freshness-bridge.json",
            "tmp/macro-event-calendar.json",
            "tmp/macro-metrics-current.json",
            "tmp/macro-judgment-draft.json",
            "tmp/json-sql-promotion-index.json",
            "tmp/json-sql-promotion-registry.json",
            "tmp/generic-service-run-contract.json",
            "tmp/wf75-smb-workflow-scenario-library.json",
            "tmp/wf75-smb-pivot-pm-decision-packet.json",
            "tmp/wf75-smb-customer-preview.json",
            "tmp/wf75-smb-customer-preview-validation.json",
            "tmp/wf75-smb-pilot-decision-packet.json",
            "tmp/wf75-smb-automation-blueprints.json",
            "tmp/wf75-smb-automation-blueprints-validation.json",
            "tmp/generic-service-state.sqlite",
            "tmp/wf75-scenario-template-library.json",
            "tmp/wf75-renderer-export-regression.json",
            "tmp/wf75-service-state-current.json",
            "tmp/wf75-service-state-sqlite.json",
            WF75_OPERATOR_CONSOLE_JSON,
            f"optional proof render: {WF75_OPERATOR_CONSOLE_HTML}",
            "optional operator-console Markdown digest when --write-md is supplied",
            "tmp/wf75-artifact-only-pm-handoff.json",
            "tmp/veritas-pm-department-validation.json",
            "tmp/wf75-pm-weekly-update.json",
            "optional PM-weekly-update Markdown digest when --write-md is supplied",
            "tmp/wf75-pm-readiness-brief.json",
            "tmp/wf75-pm-readiness-brief.html",
            "tmp/wf75-pm-readiness-brief.pdf",
            "tmp/operator-packets/retail-saas-wf75.json",
            "tmp/pm-control-packet.json",
            "tmp/wf75-closeout-refresh.json",
            "tmp/cron-operator-ledger.json",
            "optional cron-operator-ledger Markdown digest",
        ],
        "response_contract": [
            "status",
            "PM validation status",
            "weekly update status",
            "artifact-only handoff status",
            "PDF readiness status",
            "operator console status",
            "required proof count",
            "blockers/trust gates",
            "MAIN_HANDOFF_REQUIRED if blocked/warning/missing/stale",
            "NO_ESCALATION_NEEDED if clean",
        ],
        "spawn_recommendation": "stay in-run; do not spawn unless a validator fails and the failure is bounded to artifact repair",
        "delivery_mode": "none",
        "trust_grade": "internal-only / automation-ready artifact generation",
        "stop_line": "Stop before public/customer/external delivery, real customer data, customer-data retention, automation-platform/customer-system credentials, outbound automation, customer-system implementation/writeback, legal/source/security readiness claims, SQL import, portfolio/canon mutation, paper/live/account action, config/auth/runtime mutation, or owner approval inference.",
    }


def dispatcher_job_card() -> dict[str, Any]:
    return {
        "name": DISPATCHER_NAME,
        "window_family": "PM / main-session continuation",
        "schedule": {"kind": "cron", "expr": "*/20 6-18 * * *", "tz": "America/Phoenix"},
        "session_target": "main",
        "owner": "Veritas main session",
        "trigger_goal": "Wake the main session to inspect the PM main-session handoff packet and continue only the selected bounded review-only action when it is ready.",
        "read_first": [
            "HEARTBEAT.md",
            "skills/veritas-pm-department/SKILL.md",
            "skills/automation-hardening-manager/SKILL.md",
            "skills/cron-automation-manager/SKILL.md",
            "tmp/pm-control-packet.json",
        ],
        "execute_in_order": [
            "Run `python scripts\\pm_control_packet.py --write --write-db --validate` if the packet is missing or stale.",
            "If `tmp/pm-control-packet.json` section `pm_main_session_handoff` status is `ready_for_main_session`, continue only the selected bounded review-only action.",
            "For `smb_workflow_clarity`, refresh `python scripts\\generic_intelligence_saas_pivot.py --write --write-db --validate`, inspect SMB customer-preview validation / automation-blueprint validation / pilot packet / PM next action, and advance only review-only queue, product-roadmap, dry-run automation blueprint, renderer/validator, or local-cockpit proof.",
            "If the action touches WF75 or SMB artifacts materially, finish with `python scripts\\wf75_closeout_refresh.py --validation-budget shared --write --validate`.",
            "Refresh the PM control packet and harness scorecard after meaningful PM/WF75/SMB work.",
            "If not ready, blocked, unchanged, or outside authority, reply `NO_REPLY` or report only the blocker.",
        ],
        "inspect_after_execution": [
            "tmp/pm-control-packet.json",
            "tmp/wf75-closeout-refresh.json when WF75 work changed artifacts",
        "tmp/wf75-smb-customer-preview-validation.json when SMB work changed artifacts",
        "tmp/wf75-smb-pilot-decision-packet.json when SMB work changed artifacts",
        "tmp/wf75-smb-automation-blueprints-validation.json when SMB automation design changed artifacts",
        ],
        "response_contract": [
            "selected PM action",
            "whether main-session continuation ran",
            "validation result",
            "updated PM readiness",
            "next queued action or blocker",
            "authority boundary preserved",
        ],
        "spawn_recommendation": "main session may spawn one bounded helper only from the handoff packet; heartbeat/cron must not spawn broad helpers",
        "delivery_mode": "main-session system event",
        "trust_grade": "internal-only / review-required when blockers exist",
        "stop_line": "No launch, real customer data, customer-data retention, automation-platform/customer-system credential access, outbound calls/texts/emails/social messages or automated campaigns, external delivery, customer-system implementation/writeback, SQL import, archive/delete, canon/portfolio mutation, paper/live/account action, config/auth/runtime mutation, guaranteed ROI/revenue/legal/compliance/security claim, or owner approval inference.",
    }


def handoff_job_card() -> dict[str, Any]:
    return {
        "name": HANDOFF_NAME,
        "window_family": "weekly / PM / main intelligence",
        "schedule": {"kind": "cron", "expr": "40 16 * * 5", "tz": "America/Phoenix"},
        "session_target": "main",
        "owner": "Veritas main session",
        "trigger_goal": "Main session reads the WF75 PM weekly update, macro-event calendar, macro metrics, macro judgment, JSON-to-SQL promotion index, operator console/control cockpit, and PM proof surfaces, then decides whether Randall needs a concise intelligence update.",
        "read_first": [
            "tmp/wf75-pm-weekly-update.json",
            "tmp/macro-event-calendar.json",
            "tmp/macro-metrics-current.json",
            "tmp/macro-judgment-draft.json",
            "tmp/json-sql-promotion-index.json",
            WF75_OPERATOR_CONSOLE_JSON,
            f"optional proof render: {WF75_OPERATOR_CONSOLE_HTML}",
            "tmp/wf75-pm-readiness-brief.json",
            "tmp/wf75-pm-readiness-brief.pdf",
            "tmp/wf75-artifact-only-pm-handoff.json",
            "tmp/veritas-pm-department-validation.json",
            "tmp/operator-packets/retail-saas-wf75.json",
            "tmp/pm-control-packet.json",
        ],
        "execute_in_order": [
            "Inspect the artifacts.",
            "If clean and unchanged, reply NO_REPLY.",
            "If materially changed, blocked, stale, or decision-needed, summarize for Randall.",
        ],
        "inspect_after_execution": [
            "same artifacts as read_first",
        ],
        "response_contract": [
            "active item",
            "completion decision",
            "trust state",
            "fresh outputs checked",
            "macro-event calendar state",
            "macro judgment/index state",
            "current project status",
            "next queued item",
            "next action",
            "blocker, if any",
        ],
        "spawn_recommendation": "main session may spawn one bounded helper only for artifact QA or proposal drafting; no runtime/config/customer/canon/execution mutation",
        "delivery_mode": "main-session intelligence only",
        "trust_grade": "internal-only / review-required when blockers exist",
        "stop_line": "No launch/customer/external/source/legal/execution authority; generated artifacts are intelligence surfaces, not approvals.",
    }


def build_payload() -> dict[str, Any]:
    live = live_job_summary()
    installed = live["builder_present"] and live["handoff_present"] and live["dispatcher_present"]
    plan = {
        "schema": "veritas.wf75.cron_automation_authority_plan.v1",
        "generated_at_utc": utc_now_iso(),
        "status": "ready_for_cron_install" if not installed else "installed_or_present",
        "operating_model": {
            "cron_role": "produce bounded proof artifacts and scheduled PM surfaces",
            "main_session_role": "read artifacts, synthesize intelligence, decide escalation, and preserve authority boundaries",
            "randall_role": "receiver of distilled intelligence and owner decisions, not raw cron noise",
        },
        "automation_lanes": [
            {
                "lane": "WF75 PM weekly update",
                "cron_capability": "artifact generation, PDF brief rendering, and proof refresh",
                "main_session_capability": "intelligence synthesis and decision escalation",
                "randall_receives": "concise weekly status only when material or requested",
            },
            {
                "lane": "WF75 infrastructure proof packets",
                "cron_capability": "refresh fixture-only service-state, renderer/export, QA regression, and PM proof surfaces when scripts exist",
                "main_session_capability": "final integration and infrastructure sprint escalation",
                "randall_receives": "decision-grade infrastructure status, not implementation noise",
            },
        ],
        "job_cards": [builder_job_card(), handoff_job_card(), dispatcher_job_card()],
        "live_cron_state": live,
        "authority_boundary": {
            "public_launch_allowed": False,
            "real_customer_data_allowed": False,
            "external_delivery_allowed": False,
            "legal_or_compliance_ready": False,
            "source_licensing_assumed": False,
            "paper_live_or_account_action_allowed": False,
            "portfolio_or_canon_mutation_allowed": False,
            "owner_approval_inferred": False,
        },
        "next_install_action": (
            "WF75 PM cron jobs and PM dispatcher are installed. Keep the builder artifact-only, handoff main-session-only, and dispatcher bounded to `tmp/pm-control-packet.json`; inspect run history and artifacts after the next scheduled or forced run."
            if installed
            else "Install the WF75 PM builder, weekly handoff, and PM main-session dispatcher if absent, then run the builder/dispatcher once and inspect artifacts before relying on the schedule."
        ),
    }
    return plan


def render_markdown(plan: dict[str, Any]) -> str:
    lines = [
        "# WF75 Cron Automation Authority Plan",
        "",
        f"- Generated: `{plan['generated_at_utc']}`",
        f"- Status: `{plan['status']}`",
        "",
        "## Operating Model",
        "",
    ]
    for key, value in plan["operating_model"].items():
        lines.append(f"- {key}: {value}")
    lines.extend(["", "## Jobs", ""])
    for job in plan["job_cards"]:
        lines.append(f"### {job['name']}")
        lines.append(f"- Schedule: `{job['schedule']['expr']}` `{job['schedule']['tz']}`")
        lines.append(f"- Session target: `{job['session_target']}`")
        lines.append(f"- Goal: {job['trigger_goal']}")
        lines.append(f"- Stop line: {job['stop_line']}")
        lines.append("")
    lines.extend(["## Boundary", ""])
    for key, value in plan["authority_boundary"].items():
        lines.append(f"- {key}: `{str(value).lower()}`")
    lines.extend(["", "## Next Install Action", "", plan["next_install_action"], ""])
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate WF75 cron automation authority plan and job cards.")
    parser.add_argument("--write", action="store_true", help="Write the JSON plan artifact.")
    parser.add_argument("--write-md", action="store_true", help="Also write the optional Markdown rendering.")
    parser.add_argument("--validate", action="store_true", help="Validate authority flags and job cards.")
    parser.add_argument("--json-out", default=str(DEFAULT_JSON))
    parser.add_argument("--md-out", default=str(DEFAULT_MD))
    return parser.parse_args()


def validate(plan: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for key, value in plan["authority_boundary"].items():
        if value is not False:
            errors.append(f"authority boundary not false: {key}")
    names = [job["name"] for job in plan["job_cards"]]
    if len(names) != len(set(names)):
        errors.append("duplicate job names")
    for job in plan["job_cards"]:
        if not job.get("read_first") or not job.get("execute_in_order") or not job.get("stop_line"):
            errors.append(f"incomplete job card: {job.get('name')}")
    return errors


def main() -> int:
    args = parse_args()
    plan = build_payload()
    errors = validate(plan) if args.validate else []
    plan["validation"] = {"status": "ok" if not errors else "blocked", "errors": errors}
    if errors:
        plan["status"] = "blocked"
    if args.write:
        json_out = Path(args.json_out)
        md_out = Path(args.md_out)
        if not json_out.is_absolute():
            json_out = WORKSPACE / json_out
        if not md_out.is_absolute():
            md_out = WORKSPACE / md_out
        atomic_write_json(json_out, plan)
        outputs = {"json": str(json_out)}
        if args.write_md:
            atomic_write_text(md_out, render_markdown(plan))
            outputs["markdown"] = str(md_out)
        plan["outputs"] = outputs
    print(json.dumps(plan, indent=2))
    return 0 if not errors else 2


if __name__ == "__main__":
    raise SystemExit(main())
