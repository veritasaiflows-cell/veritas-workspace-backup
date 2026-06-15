from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, atomic_write_text, load_json_artifact

WORKSPACE = Path(__file__).resolve().parents[1]
TMP = WORKSPACE / "tmp"
AUDITS = WORKSPACE / "08. Audits"
OUT_JSON = TMP / "cron-notes-flattening-plan.json"
OUT_MD = TMP / "cron-notes-flattening-plan.md"
SCHEMA_VERSION = 1

BLOCKED_AUTHORITY = {
    "cron_schedule_mutation_allowed": False,
    "cron_job_mutation_allowed": False,
    "archive_move_delete_allowed": False,
    "canonical_mutation_allowed": False,
    "portfolio_mutation_allowed": False,
    "customer_external_delivery_allowed": False,
    "paper_trade_submit_cancel_allowed": False,
    "live_trade_or_account_action_allowed": False,
    "owner_approval_inferred": False,
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    return path.relative_to(WORKSPACE).as_posix()


def latest_audit() -> Path | None:
    if not AUDITS.exists():
        return None
    candidates = [path for path in AUDITS.glob("*.md") if path.is_file()]
    if not candidates:
        return None
    return max(candidates, key=lambda path: path.stat().st_mtime)


def file_surface(path_text: str, role: str, migration_target: str) -> dict[str, Any]:
    path = WORKSPACE / path_text
    return {
        "path": path_text,
        "role": role,
        "migration_target": migration_target,
        "exists": path.exists(),
        "bytes": path.stat().st_size if path.exists() else 0,
    }


def load_json(path_text: str) -> dict[str, Any] | None:
    data = load_json_artifact(WORKSPACE / path_text)
    return data if isinstance(data, dict) else None


def phase(
    number: int,
    name: str,
    target_state: str,
    work: list[str],
    acceptance: list[str],
    blocked: list[str],
) -> dict[str, Any]:
    return {
        "phase": number,
        "name": name,
        "target_state": target_state,
        "work": work,
        "acceptance_criteria": acceptance,
        "blocked_actions": blocked,
    }


def build_plan() -> dict[str, Any]:
    audit = latest_audit()
    current_ledger = load_json("tmp/cron-operator-ledger.json")
    current_window = load_json("tmp/current-window-artifacts.json")
    run_summaries = {
        window: load_json(f"tmp/run-summary-{window}.json")
        for window in ("morning", "post-close", "post-earnings", "sunday")
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": utc_now(),
        "status": "plan_ready",
        "latest_audit": {
            "path": rel(audit) if audit else "",
            "exists": audit is not None,
            "principle_applied": "human markdown should be thin operator prose; machine consumers should read structured JSON/canon blocks owned by a single truth surface",
        },
        "objective": "Migrate cron notes from large mixed Markdown truth surfaces into a JSON-first truth system with compact human digests.",
        "target_truth_system": {
            "procedure": "06. Playbooks/Cron Job Protocol.md",
            "current_cron_operator_status": "tmp/cron-operator-ledger.json",
            "human_cron_digest": "optional Markdown digest beside tmp/cron-operator-ledger.json",
            "window_closure_truth": "tmp/run-summary-<window>.json",
            "raw_step_trace": "tmp/run-chain-<window>.json",
            "artifact_routing_truth": "tmp/current-window-artifacts.json",
            "legacy_historical_ledger": "06. Playbooks/Cron Run Ledger.md",
            "rule": "Markdown may render or route; JSON owns current machine truth.",
        },
        "current_state": {
            "cron_operator_ledger_present": current_ledger is not None,
            "cron_operator_ledger_status": (current_ledger or {}).get("status", ""),
            "current_window_status": (current_window or {}).get("status", ""),
            "run_summary_statuses": {
                window: (data or {}).get("status", "missing")
                for window, data in run_summaries.items()
            },
            "stop_line_windows": [
                window
                for window, data in run_summaries.items()
                if isinstance(data, dict) and data.get("stop_line")
            ],
        },
        "markdown_surfaces": [
            file_surface("06. Playbooks/Cron Run Ledger.md", "mixed_status_history_procedure", "thin_to_current_operator_index"),
            file_surface("06. Playbooks/Cron Job Protocol.md", "procedure", "keep_procedure_only"),
            file_surface("06. Playbooks/Automation Run Summary Contract.md", "contract", "keep_contract_only"),
            file_surface("tmp/current-window-artifacts.json", "current_window_index", "json_first"),
            file_surface("tmp/cron-operator-ledger.json", "generated_digest", "json_first"),
            file_surface("tmp/wf75-cron-automation-authority-plan.json", "decision_plan", "keep_json_source; optional Markdown digest only when explicitly requested"),
            file_surface("tmp/wf75-pm-weekly-update.json", "weekly_pm_packet", "keep_json_source; PM presentation handled by PDF/HTML surfaces"),
        ],
        "phases": [
            phase(
                0,
                "Freeze and Inventory",
                "Known cron Markdown surfaces, JSON proof surfaces, stop lines, and duplicate truth clusters are inventoried.",
                [
                    "Read latest audit and apply the single-truth/two-reader principle to cron notes.",
                    "Inventory active Markdown cron surfaces and generated JSON proof surfaces.",
                    "Record current blocked/warning windows without editing cron jobs.",
                ],
                [
                    "Latest audit path is captured.",
                    "Cron Run Ledger and current-window Markdown duplication are explicitly classified.",
                    "No cron/config/archive/canon/portfolio mutation occurred.",
                ],
                ["delete/archive historical Markdown", "edit live cron schedules", "change authority boundaries"],
            ),
            phase(
                1,
                "JSON Current Ledger",
                "A structured current cron operator ledger owns job inventory, window status, proof pointers, blockers, and next actions.",
                [
                    "Generate tmp/cron-operator-ledger.json from cron job store, run summaries, run-chain pointers, and current-window artifact index.",
                    "Generate compact Markdown cron digests only on demand from JSON.",
                    "Validate hard-false authority flags and source coverage.",
                ],
                [
                    "tmp/cron-operator-ledger.json validates.",
                    "Human digest is generated from JSON and remains compact.",
                    "Stop-line windows and blocked windows are represented in JSON before any legacy thinning.",
                ],
                ["make cron scheduler changes", "treat digest as authority", "hide post-close blocked state"],
            ),
            phase(
                2,
                "Protocol Routing Update",
                "Human docs route operators to JSON truth surfaces instead of duplicating live proof.",
                [
                    "Patch Cron Run Ledger with a top-level thin-ledger notice and pointer to tmp/cron-operator-ledger.json/.md.",
                    "Patch Cron Job Protocol to name the JSON-first ledger as the current operator status route.",
                    "Patch scripts README so supported commands include cron_operator_ledger.py and this plan generator.",
                ],
                [
                    "Docs preserve procedure and authority boundaries.",
                    "No historical entries are removed yet.",
                    "Boot surface and workflow hygiene validators still pass.",
                ],
                ["remove stop-line text without JSON parity", "move/delete old ledger", "weaken cron authority language"],
            ),
            phase(
                3,
                "Duplicate Markdown Suppression",
                "Routine chains stop creating heavy duplicate Markdown tables; Markdown rendering becomes on-demand or compact.",
                [
                    "Keep current_window_artifact_index.py JSON-first; use --write-md only for explicit human review.",
                    "If needed, add size caps/compact rendering to current-window Markdown output.",
                    "Add validator checks that routine chains do not require current-window Markdown digests.",
                ],
                [
                    "chain_manifest continues to call current_window_artifact_index.py --write without --write-md.",
                    "No downstream consumer requires current-window Markdown digests.",
                    "Generated MD sidecars are either presentation packets or compact digests.",
                ],
                ["delete legacy MD before reference checks", "break human presentation packets", "remove JSON artifacts"],
            ),
            phase(
                4,
                "Registry Split",
                "Schedules/job cards and current run status are split into durable structured fields.",
                [
                    "Promote job card fields from live cron store into a validated review-only registry if live cron store shape proves unstable.",
                    "Keep run status in run summaries/current ledger, not in procedure docs.",
                    "Add parity checks for job ID, schedule, owner, stop line, and expected artifact pointers.",
                ],
                [
                    "Every active job has a structured ID/schedule/owner/proof pointer.",
                    "Cron Run Ledger no longer needs to carry live schedule prose.",
                    "Registry remains review-only and does not mutate cron.",
                ],
                ["make registry a second scheduler", "infer owner approval from registry", "edit cron config from registry"],
            ),
            phase(
                5,
                "Legacy Ledger Thinning",
                "Cron Run Ledger becomes a short routing/index page; historical material is linked or archived through owner-reviewed moves.",
                [
                    "After JSON parity, replace large active ledger body with compact current routing, latest status pointer, and historical proof index.",
                    "Move historical proof chunks only through an approved archive/move plan with hashes and rollback.",
                    "Keep procedure in Cron Job Protocol and contract in Automation Run Summary Contract.",
                ],
                [
                    "No unique live job ID, stop line, overlap rule, or authority boundary is lost.",
                    "Reference scans prove old sections are either migrated or intentionally retained.",
                    "Archive/move/delete actions require separate exact approval.",
                ],
                ["perform destructive cleanup in this plan", "lose historical proof", "mix procedure back into current ledger"],
            ),
            phase(
                6,
                "Fully Migrated Operating Mode",
                "Main session consumes JSON proof, Randall receives concise intelligence, and Markdown remains thin human context.",
                [
                    "Cron jobs refresh proof artifacts.",
                    "Main-session Veritas reads structured ledger/run summaries and reports material intelligence only.",
                    "Weekly/PM/PDF packets remain human presentation surfaces, not machine truth.",
                    "Add hygiene checks for accidental heavy Markdown truth growth.",
                ],
                [
                    "Current cron state can be answered from tmp/cron-operator-ledger.json plus run-summary JSON.",
                    "Markdown docs are procedure, compact digest, or presentation packets only.",
                    "Finance/customer/execution/account boundaries remain unchanged.",
                ],
                ["customer/public delivery", "canon/portfolio mutation from cron", "paper/live/account action", "owner approval inference"],
            ),
        ],
        "immediate_next_actions": [
            "Use cron_operator_ledger.py --write --write-md --validate as the new current cron status refresh.",
            "Patch cron docs to point at the JSON-first ledger before thinning old material.",
            "Only after parity validation, prepare a separate owner-reviewed archive/move packet for historical ledger material.",
        ],
        "authority": BLOCKED_AUTHORITY,
    }


def validate(plan: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if plan.get("schema_version") != SCHEMA_VERSION:
        errors.append("schema_version_mismatch")
    if not plan.get("latest_audit", {}).get("exists"):
        errors.append("latest_audit_missing")
    if len(plan.get("phases", [])) < 7:
        errors.append("missing_full_migration_phase_set")
    for key, value in BLOCKED_AUTHORITY.items():
        if value is False and plan.get("authority", {}).get(key) is not False:
            errors.append(f"authority_not_false:{key}")
    target = plan.get("target_truth_system", {})
    for required in ("current_cron_operator_status", "window_closure_truth", "artifact_routing_truth", "legacy_historical_ledger"):
        if not target.get(required):
            errors.append(f"target_missing:{required}")
    return errors


def render_md(plan: dict[str, Any]) -> str:
    lines = ["# Cron Notes Flattening Plan", ""]
    lines.append(f"- Generated: `{plan['generated_at_utc']}`")
    lines.append(f"- Status: **{plan['status']}**")
    lines.append(f"- Latest audit: `{plan['latest_audit']['path']}`")
    lines.append(f"- Objective: {plan['objective']}")
    lines.append("")
    lines.append("## Target Truth System")
    for key, value in plan["target_truth_system"].items():
        lines.append(f"- `{key}`: `{value}`")
    lines.append("")
    lines.append("## Phases")
    for item in plan["phases"]:
        lines.append(f"### Phase {item['phase']} - {item['name']}")
        lines.append(item["target_state"])
        lines.append("")
        lines.append("Work:")
        for work in item["work"]:
            lines.append(f"- {work}")
        lines.append("")
        lines.append("Acceptance:")
        for acceptance in item["acceptance_criteria"]:
            lines.append(f"- {acceptance}")
        lines.append("")
    lines.append("## Authority")
    lines.append("Review-only planning and proof. No cron mutation, archive move/delete, canon/portfolio mutation, customer delivery, paper/live/account action, or owner approval inference.")
    return "\n".join(lines) + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a full phased plan for JSON-first cron-note flattening.")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--write-md", action="store_true")
    parser.add_argument("--validate", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    plan = build_plan()
    errors = validate(plan) if args.validate else []
    if args.write:
        atomic_write_json(OUT_JSON, plan, indent=2)
        if args.write_md:
            atomic_write_text(OUT_MD, render_md(plan))
    print(json.dumps({"status": "error" if errors else "ok", "out": rel(OUT_JSON), "md": rel(OUT_MD), "errors": errors}, indent=2))
    return 2 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
