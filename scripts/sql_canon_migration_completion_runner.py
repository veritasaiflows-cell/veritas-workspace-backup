#!/usr/bin/env python3
"""Run the SQL-canon migration completion proof bundle.

This runner is intentionally a proof/classification wrapper. It refreshes the
existing SQL Canon, WF84, WF85, retirement, and owner-decision packets, then
writes one consolidated completion surface. It does not patch consumers, write
SQL rows, archive/delete files, change cron schedules, promote answer-path
ownership, mutate portfolio/canon notes, or authorize capital/execution.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCRIPTS = Path(__file__).resolve().parent
ROOT = SCRIPTS.parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from market_data_utils import atomic_write_json, atomic_write_text  # noqa: E402


SCHEMA = "veritas.sql_canon_migration_completion_runner.v1"
OUT = ROOT / "tmp" / "sql-canon-migration-completion-runner.json"
MD_OUT = ROOT / "tmp" / "sql-canon-migration-completion-runner.md"

ARTIFACTS = {
    "finance_sql_canon_access": ROOT / "tmp" / "finance-sql-canon-access-validation.json",
    "consumer_inventory": ROOT / "tmp" / "sql-canon-consumer-inventory.json",
    "consumer_backlog": ROOT / "tmp" / "sql-canon-consumer-migration-backlog.json",
    "consumer_registry_guard": ROOT / "tmp" / "sql-canon-consumer-registry-guard.json",
    "answer_path_ab_harness": ROOT / "tmp" / "sql-canon-answer-path-ab-harness.json",
    "production_grade_policy_gate": ROOT / "tmp" / "finance-production-grade-policy-gate.json",
    "full_answer_assembler": ROOT / "tmp" / "trade-grade-full-answer-assembler.json",
    "full_answer_parity": ROOT / "tmp" / "full-answer-parity" / "full-answer-parity-rollup.json",
    "retirement_readiness": ROOT / "tmp" / "canonical-finance-data-plane-retirement-readiness.json",
    "wf78_sidecar_retirement_candidates": ROOT / "tmp" / "wf78-sidecar-retirement-candidates.json",
    "ticker_answer_packet_retirement": ROOT / "tmp" / "ticker-answer-packet-retirement-approval-plan-20260609.json",
    "burndown": ROOT / "tmp" / "finance-sql-consumer-migration-burndown.json",
    "phase_executor": ROOT / "tmp" / "sql-canon-migration-phase-executor.json",
    "phase_owner_decision": ROOT / "tmp" / "sql-canon-migration-owner-decision-packet.json",
    "owner_decision": ROOT / "tmp" / "sql-canon-owner-decision-packet.json",
    "control_closeout_bundle": ROOT / "tmp" / "control-closeout-bundle.json",
}

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "proof_bundle_only": True,
    "consumer_files_modified": False,
    "sql_writes_performed": False,
    "db_row_mutation_performed": False,
    "schema_mutation_performed": False,
    "archive_moves_performed": False,
    "delete_performed": False,
    "cron_schedule_mutation_performed": False,
    "source_feeder_retirement_allowed": False,
    "python_fallback_retirement_allowed": False,
    "answer_path_sql_first_promotion_allowed": False,
    "duplicate_surface_cleanup_apply_allowed": False,
    "portfolio_or_canon_mutation_allowed": False,
    "capital_deployment_allowed": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "money_movement_allowed": False,
    "owner_approval_inferred": False,
}

REQUIRED_FALSE_FLAGS = {
    key for key, value in AUTHORITY_BOUNDARY.items() if value is False
}


@dataclass(frozen=True)
class CommandSpec:
    name: str
    args: tuple[str, ...]
    required: bool = True
    timeout_seconds: int = 240


COMMANDS = (
    CommandSpec(
        "finance_sql_canon_access",
        ("scripts/finance_sql_canon_access.py", "--write", "--validate"),
    ),
    CommandSpec(
        "consumer_inventory",
        ("scripts/sql_canon_consumer_inventory.py", "--write", "--validate"),
    ),
    CommandSpec(
        "consumer_registry_guard",
        ("scripts/sql_canon_consumer_registry_guard.py", "--write", "--validate"),
    ),
    CommandSpec(
        "answer_path_ab_harness",
        ("scripts/sql_canon_answer_path_ab_harness.py", "--scope", "production-42", "--write", "--validate"),
    ),
    CommandSpec(
        "production_grade_policy_gate",
        ("scripts/finance_production_grade_policy_gate.py", "--write", "--validate"),
    ),
    CommandSpec(
        "full_answer_assembler",
        (
            "scripts/trade_grade_full_answer_assembler.py",
            "--all-wf84",
            "--write",
            "--validate",
        ),
        timeout_seconds=420,
    ),
    CommandSpec(
        "full_answer_parity",
        ("scripts/full_intelligence_answer_parity.py", "--all", "--write", "--validate", "--pretty"),
        timeout_seconds=420,
    ),
    CommandSpec(
        "retirement_readiness",
        ("scripts/canonical_finance_data_plane_retirement_readiness.py", "--write", "--validate"),
    ),
    CommandSpec(
        "wf78_sidecar_retirement_candidates",
        (
            "scripts/canonical_finance_data_plane_retirement_readiness.py",
            "--write",
            "--validate",
            "--out",
            "tmp/wf78-sidecar-retirement-candidates.json",
        ),
    ),
    CommandSpec(
        "ticker_answer_packet_retirement",
        ("scripts/ticker_answer_packet_retirement_plan.py", "--write", "--validate"),
    ),
    CommandSpec(
        "burndown",
        ("scripts/finance_sql_consumer_migration_burndown.py", "--write", "--write-md", "--validate"),
    ),
    CommandSpec(
        "phase_executor",
        ("scripts/sql_canon_migration_phase_executor.py", "--write", "--validate"),
    ),
    CommandSpec(
        "owner_decision",
        ("scripts/sql_canon_owner_decision_packet.py", "--write", "--validate"),
    ),
    CommandSpec(
        "control_closeout_bundle",
        (
            "scripts/control_closeout_bundle.py",
            "--validation-budget",
            "shared",
            "--continue-on-failure",
            "--skip-cockpit-validate",
            "--write",
            "--validate",
        ),
        required=False,
        timeout_seconds=420,
    ),
)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def short_text(value: str, limit: int = 1200) -> str:
    text = value.strip()
    if len(text) <= limit:
        return text
    return text[-limit:]


def read_json(path: Path, errors: list[str]) -> dict[str, Any]:
    if not path.exists():
        errors.append(f"missing_artifact:{rel(path)}")
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        errors.append(f"invalid_json:{rel(path)}:{exc}")
        return {}
    return value if isinstance(value, dict) else {}


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def nested(data: dict[str, Any], *keys: str) -> Any:
    current: Any = data
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def command_text(spec: CommandSpec) -> str:
    return "python " + " ".join(spec.args)


def run_command(spec: CommandSpec) -> dict[str, Any]:
    started = time.monotonic()
    try:
        completed = subprocess.run(
            [sys.executable, *spec.args],
            cwd=ROOT,
            text=True,
            capture_output=True,
            timeout=spec.timeout_seconds,
            check=False,
        )
        elapsed = round(time.monotonic() - started, 3)
        return {
            "name": spec.name,
            "command": command_text(spec),
            "required": spec.required,
            "returncode": completed.returncode,
            "elapsed_seconds": elapsed,
            "status": "ok" if completed.returncode == 0 else ("error" if spec.required else "warning"),
            "stdout_tail": short_text(completed.stdout),
            "stderr_tail": short_text(completed.stderr),
        }
    except subprocess.TimeoutExpired as exc:
        elapsed = round(time.monotonic() - started, 3)
        return {
            "name": spec.name,
            "command": command_text(spec),
            "required": spec.required,
            "returncode": None,
            "elapsed_seconds": elapsed,
            "status": "timeout" if spec.required else "warning",
            "stdout_tail": short_text(exc.stdout or ""),
            "stderr_tail": short_text(exc.stderr or ""),
        }


def run_refresh(skip_refresh: bool) -> list[dict[str, Any]]:
    if skip_refresh:
        return []
    return [run_command(spec) for spec in COMMANDS]


def artifact_inventory(errors: list[str]) -> dict[str, dict[str, Any]]:
    loaded: dict[str, dict[str, Any]] = {}
    for name, path in ARTIFACTS.items():
        if name == "control_closeout_bundle" and not path.exists():
            loaded[name] = {"exists": False, "path": rel(path)}
            continue
        payload = read_json(path, errors)
        loaded[name] = {
            "exists": path.exists(),
            "path": rel(path),
            "status": payload.get("status"),
            "validation_status": nested(payload, "validation", "status"),
            "payload": payload,
        }
    return loaded


def compact_artifacts(artifacts: dict[str, dict[str, Any]]) -> dict[str, Any]:
    return {
        name: {
            "path": value.get("path"),
            "exists": value.get("exists"),
            "status": value.get("status"),
            "validation_status": value.get("validation_status"),
        }
        for name, value in sorted(artifacts.items())
    }


def derive_tracks(artifacts: dict[str, dict[str, Any]]) -> dict[str, Any]:
    inventory = as_dict(artifacts["consumer_inventory"].get("payload"))
    registry_guard = as_dict(artifacts["consumer_registry_guard"].get("payload"))
    burndown = as_dict(artifacts["burndown"].get("payload"))
    phase = as_dict(artifacts["phase_executor"].get("payload"))
    owner = as_dict(artifacts["owner_decision"].get("payload"))
    retirement = as_dict(artifacts["retirement_readiness"].get("payload"))
    parity = as_dict(artifacts["full_answer_parity"].get("payload"))
    assembler = as_dict(artifacts["full_answer_assembler"].get("payload"))
    answer_ab = as_dict(artifacts["answer_path_ab_harness"].get("payload"))
    policy = as_dict(artifacts["production_grade_policy_gate"].get("payload"))
    ticker_retirement = as_dict(artifacts["ticker_answer_packet_retirement"].get("payload"))

    inventory_summary = as_dict(inventory.get("summary"))
    burndown_summary = as_dict(burndown.get("summary"))
    phase_readiness = as_dict(phase.get("phase_readiness"))
    source_partition = as_dict(phase.get("source_producer_partition"))
    raw_sql = as_dict(phase.get("raw_sql_classification"))
    answer_path = as_dict(phase.get("sql_first_front_door_readiness"))
    duplicate = as_dict(phase.get("duplicate_surface_schema_cleanup_plan"))
    fallback = as_dict(phase.get("python_fallback_retirement_audit"))
    owner_evidence = as_dict(owner.get("evidence_summary"))

    source_count = int(burndown_summary.get("source_producer") or 0)
    partition_count = int(source_partition.get("source_producer_count") or 0)
    source_retirement_ready = int(source_partition.get("source_feeder_retirement_ready_count") or 0)
    duplicate_ready = int(duplicate.get("duplicate_surface_retirement_ready_count") or 0)

    return {
        "live_state": {
            "consumer_count": inventory_summary.get("consumer_count"),
            "backlog_count": inventory_summary.get("backlog_count"),
            "sql_primary_guarded": burndown_summary.get("sql_primary_guarded"),
            "sql_shadow_validated": burndown_summary.get("sql_shadow_validated"),
            "source_producer": source_count,
            "raw_sql_present_count": inventory_summary.get("raw_sql_present_count"),
            "raw_sql_review_count": raw_sql.get("raw_sql_review_count"),
            "raw_sql_actionable_typed_replacement_review_count": raw_sql.get("actionable_typed_replacement_review_count"),
            "full_answer_parity_status": parity.get("status"),
            "owner_decision_status": owner.get("status"),
            "hard_gate_actions_allowed": owner.get("hard_gate_actions_allowed") or [],
        },
        "track_a_consumer_classification_and_typed_access": {
            "status": "complete" if int(raw_sql.get("raw_sql_review_count") or 0) == 0 else "blocked",
            "phase_1": phase_readiness.get("phase_1_classification_freeze"),
            "phase_2": phase_readiness.get("phase_2_typed_access_guard_expansion"),
            "phase_4_raw_sql": phase_readiness.get("phase_4_raw_sql_review"),
            "raw_sql_present_count": raw_sql.get("raw_sql_present_count"),
            "raw_sql_review_count": raw_sql.get("raw_sql_review_count"),
            "raw_sql_retained_guarded_count": inventory_summary.get("raw_sql_retained_guarded_count"),
            "registry_guard_status": registry_guard.get("status"),
            "code_patch_required_now": False,
            "why": "0 actionable raw-SQL review surfaces; retained raw SQL is classified/guarded or source-producer proof.",
        },
        "track_b_source_producer_partition_and_burndown": {
            "status": "complete_retained" if source_retirement_ready == 0 and duplicate_ready == 0 else "owner_review_required",
            "phase_3_shadow": phase_readiness.get("phase_3_shadow_registry_promotion"),
            "phase_5_source_partition": phase_readiness.get("phase_5_source_producer_partition"),
            "source_producer_registry_count": source_count,
            "source_producer_partition_count": partition_count,
            "partition_counts": source_partition.get("partition_counts"),
            "retirement_candidate_count": source_partition.get("retirement_candidate_count"),
            "source_feeder_retirement_ready_count": source_retirement_ready,
            "duplicate_surface_retirement_ready_count": duplicate_ready,
            "burndown_status": burndown.get("status"),
            "consumer_cutover_allowed": nested(burndown, "validation", "consumer_cutover_allowed"),
            "apply_blocker": nested(burndown, "validation", "apply_blocker"),
            "why": "Source producers are partitioned and retained; no feeder/fallback/archive retirement is eligible.",
        },
        "track_c_answer_path_owner_packet_and_closeout": {
            "status": "owner_packet_ready" if owner.get("status") == "ready_for_owner_review" else "blocked",
            "phase_6_answer_path": phase_readiness.get("phase_6_p0_answer_path_closeout"),
            "phase_7_burndown_closeout": phase_readiness.get("phase_7_burndown_closeout"),
            "phase_8_owner_decision_packet": phase_readiness.get("phase_8_owner_decision_packet"),
            "answer_path_ab_status": answer_ab.get("status"),
            "answer_path_ab_scope": answer_ab.get("scope"),
            "full_answer_assembler_status": assembler.get("status"),
            "full_answer_parity_status": parity.get("status"),
            "production_grade_policy_gate_status": policy.get("status"),
            "ticker_answer_packet_retirement_status": ticker_retirement.get("status"),
            "sql_first_promotion_allowed_now": answer_path.get("sql_first_promotion_allowed_now"),
            "python_fallback_retirement_ready": fallback.get("retirement_ready"),
            "hard_gate_actions_allowed": owner.get("hard_gate_actions_allowed") or [],
            "owner_evidence": {
                "raw_sql": owner_evidence.get("raw_sql"),
                "source_producers": owner_evidence.get("source_producers"),
            },
            "why": "WF85 can remain the guarded answer surface while WF78 shrinks to feeder/repair/event-routing; promotion remains owner-gated.",
        },
        "owner_gates": owner.get("owner_decisions") or [],
        "retirement_summary": retirement.get("summary") or {},
    }


def validate_packet(packet: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    boundary = as_dict(packet.get("authority_boundary"))
    for key, expected in AUTHORITY_BOUNDARY.items():
        if boundary.get(key) is not expected:
            errors.append(f"authority_boundary_drift:{key}")
    for key in REQUIRED_FALSE_FLAGS:
        if boundary.get(key) is not False:
            errors.append(f"required_false_boundary_not_false:{key}")

    for step in packet.get("commands", []):
        if step.get("required") and step.get("status") != "ok":
            errors.append(f"required_command_failed:{step.get('name')}:{step.get('status')}")

    artifacts = as_dict(packet.get("artifacts"))
    for name, artifact in artifacts.items():
        if name == "control_closeout_bundle":
            continue
        if artifact.get("exists") is not True:
            errors.append(f"missing_required_artifact:{name}")

    tracks = as_dict(packet.get("tracks"))
    live = as_dict(tracks.get("live_state"))
    if int(live.get("raw_sql_review_count") or 0) != 0:
        errors.append("raw_sql_review_count_not_zero")
    if live.get("hard_gate_actions_allowed"):
        errors.append("hard_gate_actions_allowed")

    track_a = as_dict(tracks.get("track_a_consumer_classification_and_typed_access"))
    if track_a.get("code_patch_required_now") is not False:
        errors.append("track_a_code_patch_required")
    track_b = as_dict(tracks.get("track_b_source_producer_partition_and_burndown"))
    if int(track_b.get("source_feeder_retirement_ready_count") or 0) != 0:
        errors.append("source_feeder_retirement_ready_count_not_zero")
    if int(track_b.get("duplicate_surface_retirement_ready_count") or 0) != 0:
        errors.append("duplicate_surface_retirement_ready_count_not_zero")
    if track_b.get("consumer_cutover_allowed") is not False:
        errors.append("consumer_cutover_allowed")
    track_c = as_dict(tracks.get("track_c_answer_path_owner_packet_and_closeout"))
    if track_c.get("sql_first_promotion_allowed_now") is not False:
        errors.append("sql_first_promotion_allowed_now")
    if track_c.get("python_fallback_retirement_ready") not in {False, None}:
        errors.append("python_fallback_retirement_ready")
    if track_c.get("hard_gate_actions_allowed"):
        errors.append("track_c_hard_gate_actions_allowed")
    return errors


def build_packet(skip_refresh: bool = False) -> dict[str, Any]:
    generated_at = utc_now()
    commands = run_refresh(skip_refresh)
    artifact_errors: list[str] = []
    artifacts_loaded = artifact_inventory(artifact_errors)
    tracks = derive_tracks(artifacts_loaded)

    advisory_residue = []
    for step in commands:
        if not step.get("required") and step.get("status") != "ok":
            advisory_residue.append(f"advisory_command_warning:{step.get('name')}:{step.get('status')}")
    advisory_residue.extend(artifact_errors)
    if int(nested(tracks, "live_state", "source_producer") or 0):
        advisory_residue.append(f"{nested(tracks, 'live_state', 'source_producer')} source_producer rows remain intentionally retained.")
    if as_dict(tracks.get("retirement_summary")).get("archive_ready_count"):
        advisory_residue.append("archive_ready_count_seen_but_apply_still_blocked")

    packet = {
        "schema": SCHEMA,
        "generated_at_utc": generated_at,
        "status": "ok",
        "purpose": "Consolidated SQL Canon migration completion proof for Tracks A/B/C.",
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "commands": commands,
        "artifacts": compact_artifacts(artifacts_loaded),
        "tracks": tracks,
        "recommendation": (
            "Safe proof/classification implementation is complete. Continue with WF78 as feeder/repair/event-routing "
            "and WF85 as guarded full-answer surface; hold hard-gated retirement/promotion/apply actions."
        ),
        "next_steps": [
            "Keep WF78 upstream routing/repair outputs feeding WF84/WF85.",
            "Keep legacy ticker answer packet snapshots archived unless an explicitly approved compatibility write is required.",
            "Only consider legacy packet delete after exact lifecycle approval, active-reference review, and rollback proof.",
            "Only consider SQL-first front-door promotion after a separate promotion packet, patch/diff, rollback, and owner approval.",
            "Rerun this runner after material WF78/WF85/SQL Canon route changes.",
        ],
        "advisory_residue": advisory_residue,
        "stop_lines": [
            "No source-feeder retirement.",
            "No Python fallback retirement.",
            "No SQL-first/front-door promotion.",
            "No delete, schema cleanup, or cron schedule mutation.",
            "No portfolio/canon/cash/sizing/risk mutation.",
            "No capital deployment, paper/live execution, brokerage/account action, or money movement.",
        ],
        "validation": {
            "status": "pending",
            "errors": [],
            "warnings": [],
        },
    }
    errors = validate_packet(packet)
    packet["validation"] = {
        "status": "ok" if not errors else "error",
        "errors": errors,
        "warnings": [],
    }
    packet["status"] = "ok" if not errors else "blocked"
    return packet


def render_md(packet: dict[str, Any]) -> str:
    tracks = as_dict(packet.get("tracks"))
    live = as_dict(tracks.get("live_state"))
    track_a = as_dict(tracks.get("track_a_consumer_classification_and_typed_access"))
    track_b = as_dict(tracks.get("track_b_source_producer_partition_and_burndown"))
    track_c = as_dict(tracks.get("track_c_answer_path_owner_packet_and_closeout"))
    validation = as_dict(packet.get("validation"))
    lines = [
        "# SQL Canon Migration Completion Runner",
        "",
        f"- Status: `{packet.get('status')}`",
        f"- Generated: `{packet.get('generated_at_utc')}`",
        f"- Consumers: `{live.get('consumer_count')}`",
        f"- Backlog: `{live.get('backlog_count')}`",
        f"- SQL-primary guarded: `{live.get('sql_primary_guarded')}`",
        f"- Shadow validated: `{live.get('sql_shadow_validated')}`",
        f"- Source producers retained: `{live.get('source_producer')}`",
        f"- Raw SQL actionable review: `{live.get('raw_sql_actionable_typed_replacement_review_count')}`",
        "",
        "## Tracks",
        "",
        "| Track | Status | Proof |",
        "|---|---|---|",
        f"| A Consumer classification/typed access | `{track_a.get('status')}` | raw_sql_review=`{track_a.get('raw_sql_review_count')}`, code_patch_required=`{track_a.get('code_patch_required_now')}` |",
        f"| B Source-producer partition/burndown | `{track_b.get('status')}` | source_producer=`{track_b.get('source_producer_registry_count')}`, retirement_ready=`{track_b.get('source_feeder_retirement_ready_count')}` |",
        f"| C Answer path/owner packet/closeout | `{track_c.get('status')}` | owner_packet=`{track_c.get('status')}`, sql_first_allowed=`{track_c.get('sql_first_promotion_allowed_now')}` |",
        "",
        "## Stop Lines",
        "",
    ]
    lines.extend(f"- {line}" for line in packet.get("stop_lines", []))
    if packet.get("advisory_residue"):
        lines.extend(["", "## Advisory Residue", ""])
        lines.extend(f"- {warning}" for warning in packet.get("advisory_residue", []))
    if validation.get("warnings"):
        lines.extend(["", "## Validation Warnings", ""])
        lines.extend(f"- {warning}" for warning in validation.get("warnings", []))
    if validation.get("errors"):
        lines.extend(["", "## Errors", ""])
        lines.extend(f"- {error}" for error in validation.get("errors", []))
    lines.append("")
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--write-md", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--skip-refresh", action="store_true")
    parser.add_argument("--out", type=Path, default=OUT)
    parser.add_argument("--md-out", type=Path, default=MD_OUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    out = args.out if args.out.is_absolute() else ROOT / args.out
    md_out = args.md_out if args.md_out.is_absolute() else ROOT / args.md_out
    packet = build_packet(skip_refresh=args.skip_refresh)
    if args.write:
        atomic_write_json(out, packet)
    if args.write_md:
        atomic_write_text(md_out, render_md(packet))
    print(
        json.dumps(
            {
                "status": packet["status"],
                "out": rel(out) if args.write else None,
                "md_out": rel(md_out) if args.write_md else None,
                "validation": packet["validation"],
                "live_state": nested(packet, "tracks", "live_state"),
                "track_statuses": {
                    "A": nested(packet, "tracks", "track_a_consumer_classification_and_typed_access", "status"),
                    "B": nested(packet, "tracks", "track_b_source_producer_partition_and_burndown", "status"),
                    "C": nested(packet, "tracks", "track_c_answer_path_owner_packet_and_closeout", "status"),
                },
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 1 if args.validate and packet["validation"]["status"] != "ok" else 0


if __name__ == "__main__":
    raise SystemExit(main())
