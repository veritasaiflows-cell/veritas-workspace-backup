#!/usr/bin/env python3
"""Proactive implementation release contract.

This is a release gate over existing proof surfaces. It does not execute
validators, mutate cron, mutate SQL/canon state, or infer approval. Its job is
to make the implementation closeout contract explicit before a lane is treated
as done.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import changed_file_validator_router as changed_router
from market_data_utils import atomic_write_json, load_json_artifact


ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
DEFAULT_OUT = TMP / "implementation-release-contract.json"
SCHEMA = "veritas.implementation_release_contract.v1"
PRODUCER_MANIFEST = ROOT / "state" / "control" / "producer-consumer-contracts.json"

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "release_gate_only": True,
    "executes_validators": False,
    "cron_state_mutation_allowed": False,
    "cron_schedule_mutation_allowed": False,
    "sql_canon_mutation_allowed": False,
    "canon_or_portfolio_mutation_allowed": False,
    "cash_sizing_or_risk_mutation_allowed": False,
    "config_auth_runtime_mutation_allowed": False,
    "archive_or_delete_allowed": False,
    "customer_or_external_delivery_allowed": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "provider_mutation_allowed_without_clean_policy": False,
    "pm_queue_execution_allowed": False,
    "money_movement_allowed": False,
    "owner_approval_inferred": False,
}

WARNING_CLASSES = {
    "hard_blocker",
    "provider_unavailable_noop",
    "stale_input",
    "market_risk_signal",
    "monitor_only",
    "legacy_superseded",
    "expected_runtime_limit",
    "validation_defect",
}

BLOCKING_WARNING_CLASSES = {"hard_blocker", "validation_defect"}

ARTIFACT_PATHS = {
    "cron_contract": TMP / "cron-contract-validator.json",
    "go_binary": TMP / "go-binary-freshness-guard.json",
    "go_fast": TMP / "go-fast-proof-validators.json",
    "source_freshness": TMP / "go-sql-source-artifact-freshness-lint.json",
    "source_producer": TMP / "go-sql-source-lineage-producer-contract-lint.json",
    "warning_residue": TMP / "go-json-proof-warning-residue-lint.json",
    "pm_control": TMP / "pm-control-packet.json",
    "control_closeout": TMP / "control-closeout-bundle.json",
    "automation_stack": TMP / "automation-stack-hardening-pass.json",
    "producer_manifest": PRODUCER_MANIFEST,
    "earnings_calendar": TMP / "earnings-calendar.json",
    "post_close_quote_ledger": TMP / "post-close-final-quote-ledger.json",
    "lane_register": TMP / "concurrent-lane-register.json",
    "skill_workshop_body_guard": TMP / "skill-workshop-body-guard.json",
}

# Generated proof artifacts that must be at least as new as the changed source
# surfaces they claim to validate.  Canonical/static contracts (for example the
# producer manifest) are intentionally excluded because they are inputs to a
# release evaluation, not generated post-change proof.
GATE_PROOF_REQUIREMENTS: dict[str, tuple[tuple[str, frozenset[str]], ...]] = {
    "cron_live_roundtrip_clean": (
        ("cron_contract", frozenset({"cron_contracts", "cron_runtime_roundtrip"})),
    ),
    "go_implementation_proof_clean": (
        ("go_binary", frozenset({"go_validators"})),
        (
            "go_fast",
            frozenset({"go_validators", "sql_canon", "source_lineage", "finance_proof", "closeout", "paper_guard"}),
        ),
        (
            "warning_residue",
            frozenset({"go_validators", "sql_canon", "source_lineage", "finance_proof", "closeout", "paper_guard"}),
        ),
    ),
    "source_lineage_post_producer_clean": (
        ("source_freshness", frozenset({"sql_canon", "source_lineage"})),
        ("source_producer", frozenset({"sql_canon", "source_lineage"})),
        ("warning_residue", frozenset({"sql_canon", "source_lineage"})),
    ),
    "provider_failure_policy_clean": (
        ("earnings_calendar", frozenset({"provider_failure_policy"})),
        ("post_close_quote_ledger", frozenset({"provider_failure_policy"})),
    ),
    "pm_queue_authority_current": (
        ("pm_control", frozenset({"pm_queue"})),
    ),
    "skill_workshop_body_guard_clean": (
        ("skill_workshop_body_guard", frozenset({"skill_workshop_guard"})),
    ),
    "control_closeout_current": (
        ("control_closeout", frozenset({"closeout"})),
    ),
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def normalize(path: str) -> str:
    return path.replace("\\", "/").strip()


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def int_or(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def bool_or(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"true", "yes", "1", "ok"}:
            return True
        if lowered in {"false", "no", "0", "error", "blocked"}:
            return False
    return default


def load_artifacts(overrides: dict[str, Any] | None = None) -> dict[str, Any]:
    artifacts = {name: load_json_artifact(path) for name, path in ARTIFACT_PATHS.items()}
    if overrides:
        artifacts.update(overrides)
    return artifacts


def artifact_status(artifact: Any) -> str | None:
    data = as_dict(artifact)
    validation = as_dict(data.get("validation"))
    return str(validation.get("status") or data.get("status") or "") or None


def classify_path(path: str) -> set[str]:
    p = normalize(path)
    name = Path(p).name.lower()
    surfaces: set[str] = set()
    if p.startswith("tmp/"):
        return surfaces
    if p == "state/control/producer-consumer-contracts.json":
        surfaces.add("release_contract")
    if p.startswith("state/cron-contracts/") or name == "cron_contract_validator.py" or name.startswith("cron_"):
        surfaces.update({"cron_contracts", "cron_runtime_roundtrip"})
    if p.startswith("scripts/go/") or name in {"go_fast_proof_validators.py", "go_binary_freshness_guard.py"}:
        surfaces.add("go_validators")
    if "sql_source_lineage" in name or "source-lineage" in p or "source_artifact" in name:
        surfaces.add("source_lineage")
    if (
        "sql" in name
        or "sqlite" in name
        or "canon" in name
        or "reference_levels" in name
        or p.startswith("state/finance/")
    ):
        surfaces.add("sql_canon")
    if name.startswith("pm_") or "pm_" in name or "main_session_handoff" in name:
        surfaces.add("pm_queue")
    if (
        p.startswith("skills/")
        or p == "06. Playbooks/Skills Governance Index.md"
        or name in {"skill_workshop_body_guard.py", "test_skill_workshop_body_guard.py", "skill_git_checkpoint.py"}
    ):
        surfaces.add("skill_workshop_guard")
    if (
        "finance" in name
        or "ticker" in name
        or "wf78" in name
        or "wf84" in name
        or "wf85" in name
        or "trade_grade" in name
    ):
        surfaces.add("finance_proof")
    if "wf67" in name or "paper" in name:
        surfaces.add("paper_guard")
    if "event_calendar" in name or "quote_ledger" in name or "provider" in name:
        surfaces.add("provider_failure_policy")
    if name in {"response_recommendation_contract_lint.py", "test_response_recommendation_contract_lint.py"}:
        surfaces.add("closeout")
    if "closeout" in name or "validator" in name or "fast_path" in name:
        surfaces.add("closeout")
    if name == "implementation_release_contract.py":
        surfaces.add("release_contract")
    return surfaces


def classify_paths(paths: list[str]) -> list[str]:
    surfaces: set[str] = set()
    for path in paths:
        surfaces.update(classify_path(path))
    return sorted(surfaces)


def mtime_utc(mtime_ns: int | None) -> str | None:
    if mtime_ns is None:
        return None
    return (
        datetime.fromtimestamp(mtime_ns / 1_000_000_000, tz=timezone.utc)
        .isoformat(timespec="microseconds")
        .replace("+00:00", "Z")
    )


def iso_utc_mtime_ns(value: Any) -> int | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return int(parsed.timestamp() * 1_000_000_000)


def source_mtime_rows(surface_paths: list[str]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for raw_path in surface_paths:
        normalized = normalize(raw_path)
        surfaces = classify_path(normalized)
        if not surfaces:
            continue
        path = Path(normalized)
        if not path.is_absolute():
            path = ROOT / path
        exists = path.is_file()
        mtime_ns = path.stat().st_mtime_ns if exists else None
        rows.append({
            "path": normalized,
            "surfaces": sorted(surfaces),
            "exists": exists,
            "mtime_ns": mtime_ns,
            "mtime_utc": mtime_utc(mtime_ns),
        })
    return rows


def proof_freshness_evaluation(
    gates: list[dict[str, Any]],
    surface_paths: list[str],
    artifacts: dict[str, Any],
    artifact_overrides: dict[str, Any] | None,
    test_metadata: dict[str, Any] | None,
) -> dict[str, Any]:
    """Compare generated proof mtimes with the changed source they cover.

    ``test_metadata`` is deliberately an in-process-only deterministic seam;
    the CLI does not expose it.  Artifact overrides do not inherit filesystem
    mtimes and therefore remain unproven unless tests explicitly supply this
    metadata.  This prevents fixture payloads from silently borrowing the age
    of unrelated real proof files.
    """
    source_rows = source_mtime_rows(surface_paths)
    override_names = set((artifact_overrides or {}).keys())
    metadata = as_dict(test_metadata)
    per_artifact_metadata = as_dict(metadata.get("artifacts"))
    global_test_source_mtime = metadata.get("source_mtime_ns")
    global_test_artifact_mtime = metadata.get("artifact_mtime_ns")
    gate_evaluations: dict[str, dict[str, Any]] = {}

    for release_gate in gates:
        gate_name = str(release_gate.get("name") or "")
        if not release_gate.get("required") or gate_name not in GATE_PROOF_REQUIREMENTS:
            continue
        proof_rows: list[dict[str, Any]] = []
        for artifact_name, relevant_surfaces in GATE_PROOF_REQUIREMENTS[gate_name]:
            matching_sources = [
                row
                for row in source_rows
                if set(as_list(row.get("surfaces"))) & set(relevant_surfaces)
            ]
            test_artifact_metadata = as_dict(per_artifact_metadata.get(artifact_name))
            test_source_mtime = test_artifact_metadata.get("source_mtime_ns", global_test_source_mtime)
            if test_source_mtime is not None:
                source_mtime_ns = int_or(test_source_mtime, -1)
                source_metadata_source = "explicit_test_metadata"
                source_paths_considered = [str(row.get("path")) for row in matching_sources]
            else:
                existing_source_mtimes = [
                    int(row["mtime_ns"])
                    for row in matching_sources
                    if row.get("mtime_ns") is not None
                ]
                source_mtime_ns = max(existing_source_mtimes) if existing_source_mtimes else None
                source_metadata_source = "filesystem" if source_mtime_ns is not None else "unavailable"
                source_paths_considered = [str(row.get("path")) for row in matching_sources]

            artifact_path = ARTIFACT_PATHS.get(artifact_name)
            artifact_generated_at_utc = as_dict(artifacts.get(artifact_name)).get("generated_at_utc")
            artifact_generated_mtime_ns = iso_utc_mtime_ns(artifact_generated_at_utc)
            artifact_filesystem_mtime_ns: int | None = None
            if artifact_name in override_names:
                explicit_artifact_mtime = test_artifact_metadata.get("artifact_mtime_ns", global_test_artifact_mtime)
                artifact_mtime_ns = int_or(explicit_artifact_mtime, -1) if explicit_artifact_mtime is not None else None
                artifact_metadata_source = "explicit_test_metadata" if explicit_artifact_mtime is not None else "override_metadata_required"
            elif artifact_path is not None and artifact_path.is_file():
                artifact_filesystem_mtime_ns = artifact_path.stat().st_mtime_ns
                artifact_mtime_ns = (
                    min(artifact_filesystem_mtime_ns, artifact_generated_mtime_ns)
                    if artifact_generated_mtime_ns is not None else
                    artifact_filesystem_mtime_ns
                )
                artifact_metadata_source = (
                    "filesystem_and_generated_at_utc_earliest"
                    if artifact_generated_mtime_ns is not None else
                    "filesystem"
                )
            else:
                artifact_mtime_ns = None
                artifact_metadata_source = "unavailable"

            applicable = bool(matching_sources) or test_source_mtime is not None
            fresh = (
                applicable
                and source_mtime_ns is not None
                and source_mtime_ns >= 0
                and artifact_mtime_ns is not None
                and artifact_mtime_ns >= source_mtime_ns
            )
            status = (
                "not_applicable"
                if not applicable else
                "fresh"
                if fresh else
                "stale"
                if artifact_mtime_ns is not None and source_mtime_ns is not None else
                "unproven"
            )
            proof_rows.append({
                "artifact": artifact_name,
                "artifact_path": rel(artifact_path) if artifact_path is not None else None,
                "relevant_surfaces": sorted(relevant_surfaces),
                "source_paths_considered": source_paths_considered,
                "source_metadata_source": source_metadata_source,
                "source_newest_mtime_ns": source_mtime_ns,
                "source_newest_mtime_utc": mtime_utc(source_mtime_ns),
                "artifact_metadata_source": artifact_metadata_source,
                "artifact_generated_at_utc": artifact_generated_at_utc,
                "artifact_generated_mtime_ns": artifact_generated_mtime_ns,
                "artifact_filesystem_mtime_ns": artifact_filesystem_mtime_ns,
                "artifact_mtime_ns": artifact_mtime_ns,
                "artifact_mtime_utc": mtime_utc(artifact_mtime_ns),
                "status": status,
                "ok": fresh if applicable else True,
            })
        applicable_rows = [row for row in proof_rows if row["status"] != "not_applicable"]
        gate_evaluations[gate_name] = {
            "ok": bool(applicable_rows) and all(row["ok"] for row in applicable_rows),
            "artifact_count": len(applicable_rows),
            "fresh_artifact_count": sum(1 for row in applicable_rows if row["status"] == "fresh"),
            "stale_artifact_count": sum(1 for row in applicable_rows if row["status"] == "stale"),
            "unproven_artifact_count": sum(1 for row in applicable_rows if row["status"] == "unproven"),
            "artifacts": proof_rows,
        }

    return {
        "source_paths": source_rows,
        "gates": gate_evaluations,
        "summary": {
            "evaluated_gate_count": len(gate_evaluations),
            "fresh_gate_count": sum(1 for row in gate_evaluations.values() if row["ok"]),
            "stale_or_unproven_gate_count": sum(1 for row in gate_evaluations.values() if not row["ok"]),
            "fresh_artifact_count": sum(int(row["fresh_artifact_count"]) for row in gate_evaluations.values()),
            "stale_artifact_count": sum(int(row["stale_artifact_count"]) for row in gate_evaluations.values()),
            "unproven_artifact_count": sum(int(row["unproven_artifact_count"]) for row in gate_evaluations.values()),
        },
    }


def apply_proof_freshness(gates: list[dict[str, Any]], freshness: dict[str, Any]) -> None:
    evaluations = as_dict(freshness.get("gates"))
    for release_gate in gates:
        gate_name = str(release_gate.get("name") or "")
        evaluation = as_dict(evaluations.get(gate_name))
        if not evaluation:
            continue
        content_ok = bool(release_gate.get("ok"))
        detail = as_dict(release_gate.get("detail"))
        detail["content_ok_before_freshness"] = content_ok
        detail["proof_freshness"] = evaluation
        release_gate["detail"] = detail
        release_gate["ok"] = content_ok and bool(evaluation.get("ok"))


def active_lane_surface_paths(artifacts: dict[str, Any]) -> tuple[list[str], dict[str, Any]] | None:
    lane_register = as_dict(artifacts.get("lane_register"))
    lanes = as_list(lane_register.get("lanes"))
    active = [
        as_dict(lane)
        for lane in lanes
        if str(as_dict(lane).get("status") or "") in {"planned", "leased", "running"}
    ]
    if len(active) != 1:
        return None
    lane = active[0]
    allowed_writes = [normalize(str(path)) for path in as_list(lane.get("allowed_writes")) if str(path).strip()]
    if not allowed_writes:
        return None
    return allowed_writes, {
        "source": "active_lane_allowed_writes",
        "lane_id": lane.get("lane_id"),
        "allowed_write_count": len(allowed_writes),
    }


def surface_paths_for_scope(
    changed_paths: list[str],
    artifacts: dict[str, Any],
    explicit_paths: list[str] | None,
) -> tuple[list[str], dict[str, Any]]:
    if explicit_paths:
        return changed_paths, {"source": "explicit_paths", "path_count": len(changed_paths)}
    active = active_lane_surface_paths(artifacts)
    if active is not None:
        return active
    return changed_paths, {"source": "changed_file_route", "path_count": len(changed_paths)}


def command(name: str, reason: str) -> dict[str, str]:
    return {"command": name, "reason": reason}


def required_commands(surfaces: list[str]) -> list[dict[str, str]]:
    commands: list[dict[str, str]] = [
        command("python scripts\\changed_file_validator_router.py --write --validate", "change route must be current"),
        command("python scripts\\implementation_release_contract.py --write --validate", "release contract must be regenerated"),
    ]
    if any(surface in surfaces for surface in {"cron_contracts", "cron_runtime_roundtrip"}):
        commands.append(command("python scripts\\cron_contract_validator.py --require-contracts --fail-on-drift --write --validate", "cron local/live contract drift must be zero"))
        commands.append(command("python scripts\\cron_control_packet.py --write --validate", "cron control visibility must remain current"))
    if "go_validators" in surfaces:
        commands.append(command("python scripts\\go_binary_freshness_guard.py --write --validate", "Go validator binaries must be fresh"))
    if any(surface in surfaces for surface in {"sql_canon", "source_lineage", "finance_proof", "closeout", "go_validators"}):
        commands.append(command("python scripts\\go_fast_proof_validators.py --profile implementation --write --validate", "compiled implementation proof must be clean or classified"))
    if any(surface in surfaces for surface in {"sql_canon", "source_lineage"}):
        commands.append(command("python scripts\\finance_sql_canon_access.py --write --validate", "SQL canon front door must remain readable"))
    if "pm_queue" in surfaces:
        commands.append(command("python scripts\\pm_control_packet.py --write --write-db --validate", "PM control and queue authority must be current"))
        commands.append(command("python scripts\\pm_implementation_job_queue.py --write --write-db --validate", "PM implementation queue must agree with ledger state"))
    if "skill_workshop_guard" in surfaces:
        commands.append(command("python scripts\\skill_workshop_body_guard.py --write --validate", "Skill Workshop body-replacement guard must be current"))
        commands.append(command("python scripts\\test_skill_workshop_body_guard.py", "Skill Workshop body guard regression tests must pass"))
        commands.append(command("openclaw skills check", "workspace skill surface must remain loadable"))
    if "closeout" in surfaces or "skill_workshop_guard" in surfaces:
        commands.append(command("python scripts\\response_recommendation_contract_lint.py --self-test --write --validate", "response closeout lint must catch missing recommendations"))
    if "provider_failure_policy" in surfaces:
        commands.append(command("python scripts\\test_event_calendar_apply.py", "provider-unavailable no-op and mutation refusal policy must hold"))
        commands.append(command("python scripts\\test_implementation_release_contract.py", "release-level provider policy regression tests must pass"))
    if "paper_guard" in surfaces:
        commands.append(command("python scripts\\go_fast_proof_validators.py --profile implementation --write --validate", "paper guard warning residue must remain classified"))
    if any(surface in surfaces for surface in {"closeout", "release_contract"}):
        commands.append(command("python scripts\\control_closeout_bundle.py --validation-budget shared --write --validate", "closeout must run after implementation proof"))
    seen: set[str] = set()
    deduped: list[dict[str, str]] = []
    for item in commands:
        if item["command"] not in seen:
            seen.add(item["command"])
            deduped.append(item)
    return deduped


def finalization_order(surfaces: list[str]) -> list[str]:
    order = [
        "changed_file_route",
        "targeted_regression_tests",
    ]
    if "cron_contracts" in surfaces or "cron_runtime_roundtrip" in surfaces:
        order.extend(["cron_contract_live_readback", "cron_control_packet"])
    if "go_validators" in surfaces:
        order.append("go_binary_freshness")
    if any(surface in surfaces for surface in {"sql_canon", "source_lineage", "finance_proof"}):
        order.append("finance_sql_front_door")
    order.append("go_implementation_profile")
    if "pm_queue" in surfaces:
        order.extend(["pm_queue_authority", "pm_control_packet"])
    if "skill_workshop_guard" in surfaces:
        order.append("skill_workshop_body_guard")
    if "closeout" in surfaces or "release_contract" in surfaces:
        order.append("control_closeout_bundle")
    if "source_lineage" in surfaces or "sql_canon" in surfaces or "closeout" in surfaces:
        order.append("post_producer_source_lineage_proof")
    order.append("implementation_release_contract_post_producers")
    return order


def classify_warning(text: str) -> str | None:
    lowered = text.lower()
    if any(token in lowered for token in ("approval", "execution", "money movement", "brokerage", "authority flag")):
        return "hard_blocker"
    if any(token in lowered for token in ("legacy", "superseded", "retired")):
        return "legacy_superseded"
    if "terminal_forbidden_write_paths" in lowered or "historical terminal" in lowered:
        return "legacy_superseded"
    if any(token in lowered for token in ("provider", "rate limit", "rate-limit", "unavailable", "cached overlay", "noop", "no-op")):
        return "provider_unavailable_noop"
    if "stale" in lowered or "freshness" in lowered:
        return "stale_input"
    if any(token in lowered for token in ("source_artifact_hash_matches_lineage", "source_artifact_hash_drift", "hash_mismatch")):
        return "stale_input"
    if any(token in lowered for token in ("breadth", "market risk", "risk warning", "deployment confidence")):
        return "market_risk_signal"
    if any(token in lowered for token in ("monitor", "no_action", "no action", "no_reply", "quiet_success", "no_repair", "post_optimization_cap", "skill_has_stop_line_language")):
        return "monitor_only"
    if "main_session_greenkeeper_status:warning" in lowered:
        return "monitor_only"
    if "main_session_escalation_consumer_unresolved_residue" in lowered:
        return "monitor_only"
    if "handoff_action_present" in lowered or "main_handoff_action_present" in lowered:
        return "monitor_only"
    if "advisory" in lowered:
        return "monitor_only"
    if any(token in lowered for token in ("timeout", "runtime limit", "window limit")):
        return "expected_runtime_limit"
    if any(token in lowered for token in ("drift", "missing", "failed", "error", "critical", "prompt_bloat", "unclassified", "validation")):
        return "validation_defect"
    return None


def warning_strings_from_artifact(name: str, artifact: Any) -> list[dict[str, str]]:
    data = as_dict(artifact)
    warnings: list[str] = []
    validation = as_dict(data.get("validation"))
    warnings.extend(str(item) for item in as_list(validation.get("warnings")))
    summary = as_dict(data.get("summary"))
    for detail in as_list(summary.get("warning_details")):
        detail_dict = as_dict(detail)
        examples = as_list(detail_dict.get("examples"))
        if examples:
            warnings.extend(json.dumps(example, sort_keys=True, default=str) for example in examples[:3])
        elif detail_dict:
            warnings.append(json.dumps(detail_dict, sort_keys=True, default=str))
    return [{"source": name, "text": warning} for warning in warnings if warning]


def relevant_warning_sources(surfaces: list[str]) -> set[str]:
    sources = {"producer_manifest"}
    if "go_validators" in surfaces:
        sources.update({"go_binary", "go_fast"})
    if "cron_contracts" in surfaces or "cron_runtime_roundtrip" in surfaces:
        sources.add("cron_contract")
    if "source_lineage" in surfaces or "sql_canon" in surfaces:
        sources.update({"source_freshness", "source_producer"})
    if "pm_queue" in surfaces:
        sources.update({"pm_control", "pm_queue", "pm_handoff"})
    if "provider_failure_policy" in surfaces:
        sources.update({"earnings_calendar", "post_close_quote_ledger"})
    if "closeout" in surfaces:
        sources.add("control_closeout")
    return sources


def classify_warnings(artifacts: dict[str, Any], surfaces: list[str]) -> list[dict[str, str | None]]:
    rows: list[dict[str, str | None]] = []
    relevant = relevant_warning_sources(surfaces)
    for name in sorted(artifacts):
        if name not in relevant:
            continue
        for item in warning_strings_from_artifact(name, artifacts[name]):
            warning_class = classify_warning(item["text"])
            rows.append({**item, "class": warning_class})
    return rows


def gate(name: str, required: bool, ok: bool, command_text: str, detail: Any) -> dict[str, Any]:
    return {
        "name": name,
        "required": required,
        "ok": ok if required else True,
        "command": command_text,
        "detail": detail,
    }


def provider_proposal_count(data: dict[str, Any], summary: dict[str, Any]) -> int:
    count = 0
    for key in (
        "proposal_count",
        "staged_proposal_count",
        "staged_mutation_count",
        "mutation_count",
        "proposed_mutation_count",
        "staged_card_count",
    ):
        count = max(count, int_or(summary.get(key)), int_or(data.get(key)))
    for key in ("proposals", "staged_proposals", "mutations", "staged_mutations", "cards", "staged_cards"):
        count = max(count, len(as_list(summary.get(key))), len(as_list(data.get(key))))
    return count


def provider_policy_evaluation(artifacts: dict[str, Any]) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    blockers: list[dict[str, Any]] = []
    for name, raw in sorted(artifacts.items()):
        if not any(token in name for token in ("provider", "calendar", "quote_ledger")):
            continue
        data = as_dict(raw)
        if not data:
            continue
        validation = as_dict(data.get("validation"))
        summary = as_dict(data.get("summary"))
        status = str(validation.get("status") or data.get("status") or "")
        warning_text = " ".join(str(item) for item in as_list(validation.get("warnings")))
        error_text = " ".join(str(item) for item in as_list(validation.get("errors")))
        provider_warning_count = int_or(summary.get("provider_warning_count"))
        unavailable = (
            status in {"error", "blocked"}
            or provider_warning_count > 0
            or any(token in f"{warning_text} {error_text}".lower() for token in ("rate limit", "rate-limit", "unavailable", "provider error"))
        )
        proposals = provider_proposal_count(data, summary)
        target_count = int_or(summary.get("target_count"))
        ok_count = int_or(summary.get("ok_count"))
        error_count = int_or(summary.get("error_count"))
        cached_overlay_count = int_or(summary.get("cached_overlay_count"))
        provider_complete = target_count > 0 and ok_count == target_count and error_count == 0
        cached_complete = (
            provider_complete
            or
            cached_overlay_count == 0
            or (
                target_count > 0
                and ok_count == target_count
                and cached_overlay_count == target_count
                and error_count == 0
            )
        )
        row = {
            "artifact": name,
            "status": status or None,
            "unavailable": unavailable,
            "proposal_count": proposals,
            "target_count": target_count,
            "ok_count": ok_count,
            "error_count": error_count,
            "cached_overlay_count": cached_overlay_count,
            "cached_overlay_complete": cached_complete,
        }
        rows.append(row)
        if unavailable and proposals > 0:
            blockers.append({**row, "reason": "provider_unavailable_with_staged_mutation"})
        if not cached_complete:
            blockers.append({**row, "reason": "cached_overlay_coverage_not_proven"})
    return {"ok": not blockers and bool(rows), "artifacts": rows, "blockers": blockers}


def producer_manifest_evaluation(artifact: Any) -> dict[str, Any]:
    data = as_dict(artifact)
    summary = as_dict(data.get("summary"))
    producers = data.get("producers")
    producer_count = len(producers) if isinstance(producers, dict) else len(as_list(producers))
    required_surface_families = set(str(item) for item in as_list(summary.get("required_surface_families")))
    expected = {
        "cron_contracts",
        "provider_failure_policy",
        "pm_queue",
        "source_lineage",
        "closeout",
        "go_validators",
        "finance_proof",
    }
    missing_expected = sorted(expected - required_surface_families)
    final_after_producers = bool_or(summary.get("final_proof_after_last_producer"))
    ok = (
        artifact_status(data) == "ok"
        and data.get("schema") == "veritas.producer_consumer_contracts.v1"
        and producer_count >= 5
        and final_after_producers
        and not missing_expected
    )
    return {
        "ok": ok,
        "status": artifact_status(data),
        "producer_count": producer_count,
        "final_proof_after_last_producer": final_after_producers,
        "missing_expected_surface_families": missing_expected,
    }


def ids_from_jobs(payload: dict[str, Any], *statuses: str) -> set[str]:
    wanted = {status.lower() for status in statuses}
    out: set[str] = set()
    for job in as_list(payload.get("jobs")):
        job_dict = as_dict(job)
        status = str(job_dict.get("status") or job_dict.get("queue_status") or job_dict.get("allowed_execution_mode") or "").lower()
        if wanted and status not in wanted and not any(token in status for token in wanted):
            continue
        for key in ("job_id", "id", "action_id"):
            value = str(job_dict.get(key) or "").strip()
            if value:
                out.add(value)
    return out


def pm_job_rows(*payloads: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for payload in payloads:
        candidates = [
            as_list(payload.get("jobs")),
            as_list(as_dict(payload.get("implementation_queue")).get("jobs")),
            as_list(as_dict(as_dict(payload.get("sections")).get("pm_implementation_job_queue")).get("jobs")),
        ]
        for candidate_rows in candidates:
            for raw in candidate_rows:
                job = as_dict(raw)
                job_id = str(job.get("job_id") or job.get("id") or job.get("action_id") or "").strip()
                key = job_id or json.dumps(job, sort_keys=True, default=str)
                if key in seen:
                    continue
                seen.add(key)
                rows.append(job)
    return rows


def pm_job_status(job: dict[str, Any]) -> str:
    return str(job.get("status") or job.get("queue_status") or "").strip().lower()


def pm_job_summary(job: dict[str, Any]) -> dict[str, Any]:
    return {
        "job_id": job.get("job_id") or job.get("id") or job.get("action_id"),
        "status": job.get("status") or job.get("queue_status"),
        "allowed_execution_mode": job.get("allowed_execution_mode"),
        "closeout_mode": job.get("closeout_mode"),
        "department": job.get("department"),
        "owner_gate_required": bool_or(job.get("owner_gate_required")),
    }


def review_only_blocked_pm_job(job: dict[str, Any]) -> bool:
    mode = str(job.get("allowed_execution_mode") or "").strip().lower()
    closeout_mode = str(job.get("closeout_mode") or "").strip().lower()
    owner_gate_required = bool_or(job.get("owner_gate_required"))
    return (
        mode in {"main_session_review", "main_review_only_proof_refresh", "main_or_helper_plan_only"}
        and closeout_mode in {"queue_only", "pm_state", "handoff"}
        and not owner_gate_required
    )


def pm_blocked_job_evaluation(pm_control: dict[str, Any], pm_queue: dict[str, Any], blocked_count: int) -> dict[str, Any]:
    blocked_jobs = [job for job in pm_job_rows(pm_control, pm_queue) if "blocked" in pm_job_status(job)]
    review_only = [pm_job_summary(job) for job in blocked_jobs if review_only_blocked_pm_job(job)]
    blocking = [pm_job_summary(job) for job in blocked_jobs if not review_only_blocked_pm_job(job)]
    unknown_blocked = max(0, blocked_count - len(blocked_jobs))
    return {
        "blocked_jobs": [pm_job_summary(job) for job in blocked_jobs],
        "blocking_blocked_jobs": blocking,
        "review_only_blocked_jobs": review_only,
        "blocked_job_detail_count": len(blocked_jobs),
        "blocking_blocked_job_count": len(blocking),
        "review_only_blocked_job_count": len(review_only),
        "unknown_blocked_job_count": unknown_blocked,
        "blocking_blocked_clean": len(blocking) == 0 and unknown_blocked == 0,
    }


def selected_handoff_ids(*payloads: dict[str, Any]) -> set[str]:
    out: set[str] = set()
    for payload in payloads:
        for source in (payload, as_dict(payload.get("summary")), as_dict(as_dict(payload.get("summary")).get("main_session_handoff"))):
            for key in ("selected_job_id", "selected_pm_job_id", "parallel_helper_pm_job_id", "job_id", "top_ready_job_id"):
                value = str(source.get(key) or "").strip()
                if value:
                    out.add(value)
            selected = as_dict(source.get("selected_pm_job"))
            for key in ("job_id", "id"):
                value = str(selected.get(key) or "").strip()
                if value:
                    out.add(value)
    return out


def pm_authority_evaluation(artifacts: dict[str, Any]) -> dict[str, Any]:
    pm_control = as_dict(artifacts.get("pm_control"))
    pm_queue = as_dict(artifacts.get("pm_queue"))
    pm_handoff = as_dict(artifacts.get("pm_handoff"))
    pm_summary = as_dict(pm_control.get("summary"))
    control_queue = as_dict(pm_summary.get("implementation_queue"))
    queue_summary = as_dict(pm_queue.get("summary")) or control_queue
    job_count = int_or(queue_summary.get("job_count"))
    ready = int_or(queue_summary.get("ready_job_count"))
    owner_decision = int_or(queue_summary.get("owner_decision_job_count"))
    blocked = int_or(queue_summary.get("blocked_job_count"))
    completed = int_or(queue_summary.get("completed_by_ledger_job_count"))
    active = int_or(queue_summary.get("active_job_count"), ready)
    accounted = ready + owner_decision + blocked + completed
    top_ready = str(queue_summary.get("top_ready_job_id") or "").strip()
    top_completed = str(queue_summary.get("top_completed_job_id") or "").strip()
    handoff_summary = as_dict(pm_summary.get("main_session_handoff"))
    handoff_status = str(pm_handoff.get("status") or handoff_summary.get("status") or "").strip()
    selected_ids = selected_handoff_ids(pm_handoff, pm_control)
    if not selected_ids and handoff_status == "ready_for_main_session" and top_ready:
        selected_ids.add(top_ready)
    completed_ids = ids_from_jobs(pm_queue, "completed", "completed_by_ledger")
    if top_completed:
        completed_ids.add(top_completed)
    selected_completed = sorted(selected_ids & completed_ids)
    coverage_ok = job_count == 0 or accounted == job_count
    blocked_detail = pm_blocked_job_evaluation(pm_control, pm_queue, blocked)
    no_action_statuses = {"", "ok", "no_action", "quiet_success", "no_repair"}
    no_action_clean = handoff_status in no_action_statuses and ready == 0 and active == 0
    drained_clean = (
        handoff_status in {"ready_for_main_session", "recently_dispatched"}
        and ready == 0
        and active == 0
        and not selected_ids
    )
    review_only_drained_clean = (
        handoff_status in {*no_action_statuses, "ready_for_main_session", "recently_dispatched"}
        and ready == 0
        and owner_decision == 0
        and active > 0
        and active == blocked_detail["review_only_blocked_job_count"]
        and blocked_detail["blocking_blocked_clean"]
        and not selected_completed
    )
    ready_clean = handoff_status == "ready_for_main_session" and ready > 0 and bool(top_ready) and top_ready != top_completed and not selected_completed
    recent_dispatch_clean = handoff_status == "recently_dispatched" and not selected_completed
    pm_queue_status = artifact_status(pm_queue) if pm_queue else artifact_status(pm_control)
    ok = (
        artifact_status(pm_control) == "ok"
        and pm_queue_status == "ok"
        and blocked_detail["blocking_blocked_clean"]
        and coverage_ok
        and (ready_clean or no_action_clean or drained_clean or review_only_drained_clean or recent_dispatch_clean)
    )
    return {
        "ok": ok,
        "pm_control_status": artifact_status(pm_control),
        "pm_queue_status": pm_queue_status,
        "handoff_status": handoff_status or None,
        "job_count": job_count,
        "ready_job_count": ready,
        "owner_decision_job_count": owner_decision,
        "blocked_job_count": blocked,
        "blocking_blocked_job_count": blocked_detail["blocking_blocked_job_count"],
        "review_only_blocked_job_count": blocked_detail["review_only_blocked_job_count"],
        "unknown_blocked_job_count": blocked_detail["unknown_blocked_job_count"],
        "blocking_blocked_clean": blocked_detail["blocking_blocked_clean"],
        "blocking_blocked_jobs": blocked_detail["blocking_blocked_jobs"],
        "review_only_blocked_jobs": blocked_detail["review_only_blocked_jobs"],
        "completed_by_ledger_job_count": completed,
        "active_job_count": active,
        "accounted_job_count": accounted,
        "coverage_ok": coverage_ok,
        "top_ready_job_id": top_ready or None,
        "top_completed_job_id": top_completed or None,
        "selected_handoff_ids": sorted(selected_ids),
        "selected_completed_ids": selected_completed,
        "no_action_clean": no_action_clean,
        "drained_clean": drained_clean,
        "review_only_drained_clean": review_only_drained_clean,
        "ready_clean": ready_clean,
        "recent_dispatch_clean": recent_dispatch_clean,
    }


def evaluate_gates(surfaces: list[str], artifacts: dict[str, Any]) -> list[dict[str, Any]]:
    gates: list[dict[str, Any]] = []
    manifest_required = bool(
        set(surfaces)
        & {
            "cron_contracts",
            "cron_runtime_roundtrip",
            "go_validators",
            "source_lineage",
            "sql_canon",
            "finance_proof",
            "pm_queue",
            "provider_failure_policy",
            "closeout",
            "release_contract",
            "skill_workshop_guard",
        }
    )
    manifest_detail = producer_manifest_evaluation(artifacts.get("producer_manifest"))
    gates.append(gate(
        "producer_consumer_manifest_current",
        manifest_required,
        manifest_detail["ok"],
        "state\\control\\producer-consumer-contracts.json must be present and validation-clean",
        manifest_detail,
    ))

    cron = as_dict(artifacts.get("cron_contract"))
    cron_summary = as_dict(cron.get("summary"))
    cron_live = as_dict(as_dict(cron.get("sources")).get("live"))
    cron_validation = as_dict(cron.get("validation"))
    cron_required = "cron_contracts" in surfaces or "cron_runtime_roundtrip" in surfaces
    cron_hard_error_count_names = (
        "drift_count",
        "missing_live_job_count",
        "unsupported_model_route_count",
        "contract_prompt_integrity_error_count",
        "live_prompt_integrity_error_count",
        "prompt_bloat_count",
        "multiline_truncation_risk_count",
    )
    cron_hard_error_counts = {
        name: cron_summary.get(name)
        for name in cron_hard_error_count_names
    }
    cron_hard_error_counts_clean = all(
        isinstance(count, int) and not isinstance(count, bool) and count == 0
        for count in cron_hard_error_counts.values()
    )
    gates.append(gate(
        "cron_live_roundtrip_clean",
        cron_required,
        bool(cron)
        and cron.get("status") == "ok"
        and cron_validation.get("status") == "ok"
        and not as_list(cron_validation.get("errors"))
        and not as_list(cron_validation.get("warnings"))
        and cron_hard_error_counts_clean
        and cron_live.get("ok") is True,
        "python scripts\\cron_contract_validator.py --require-contracts --fail-on-drift --write --validate",
        {
            "status": cron.get("status"),
            "validation": cron_validation,
            "hard_error_counts": cron_hard_error_counts,
            "summary": cron_summary,
            "live": cron_live,
        },
    ))

    go_binary = as_dict(artifacts.get("go_binary"))
    go_fast = as_dict(artifacts.get("go_fast"))
    go_summary = as_dict(go_fast.get("summary"))
    go_profile = str(go_fast.get("profile") or "")
    warning_residue = as_dict(artifacts.get("warning_residue"))
    warning_residue_summary = as_dict(warning_residue.get("summary"))
    go_warning_count = int_or(go_summary.get("warning_count"))
    classifiable_key_present = "residue_classifiable_warning_count" in go_summary
    post_residue_key_present = "post_residue_warning_count" in go_summary
    go_warning_partition_declared = classifiable_key_present or post_residue_key_present
    if classifiable_key_present and post_residue_key_present:
        go_residue_classifiable_warning_count = int_or(go_summary.get("residue_classifiable_warning_count"), -1)
        go_post_residue_warning_count = int_or(go_summary.get("post_residue_warning_count"), -1)
        go_warning_partition_valid = (
            go_residue_classifiable_warning_count >= 0
            and go_post_residue_warning_count >= 0
            and go_residue_classifiable_warning_count + go_post_residue_warning_count == go_warning_count
        )
    elif not go_warning_partition_declared:
        # Backward compatibility for wrapper v2 artifacts generated before the
        # additive warning partition existed. Preserve the stricter legacy
        # behavior by treating every warning as residue-classifiable.
        go_residue_classifiable_warning_count = go_warning_count
        go_post_residue_warning_count = 0
        go_warning_partition_valid = True
    else:
        # A partial partition is ambiguous and must fail closed.
        go_residue_classifiable_warning_count = go_warning_count
        go_post_residue_warning_count = 0
        go_warning_partition_valid = False
    go_warning_residue_count_matches = (
        not go_warning_partition_declared
        or go_residue_classifiable_warning_count == 0
        or int_or(warning_residue_summary.get("warning_finding_count"), -1) == go_residue_classifiable_warning_count
    )
    go_warnings_classified = go_warning_partition_valid and go_warning_residue_count_matches and (
        go_residue_classifiable_warning_count == 0
        or (
            artifact_status(warning_residue) == "ok"
            and int_or(warning_residue_summary.get("critical")) == 0
            and int_or(warning_residue_summary.get("critical_finding_count")) == 0
            and int_or(warning_residue_summary.get("unclassified_count")) == 0
            and int_or(warning_residue_summary.get("classified_warning_count")) >= go_residue_classifiable_warning_count
            and sum(int_or(count) for count in as_dict(warning_residue_summary.get("class_counts")).values()) >= go_residue_classifiable_warning_count
        )
    )
    go_required = "go_validators" in surfaces or any(surface in surfaces for surface in {"sql_canon", "source_lineage", "finance_proof", "closeout", "paper_guard"})
    gates.append(gate(
        "go_implementation_proof_clean",
        go_required,
        artifact_status(go_binary) in {"ok", "warning"}
        and artifact_status(go_fast) in {"ok", "warning"}
        and go_profile == "implementation"
        and int_or(go_summary.get("failed_count")) == 0
        and int_or(go_summary.get("critical_count")) == 0
        and go_warnings_classified,
        "python scripts\\go_binary_freshness_guard.py --write --validate; python scripts\\go_fast_proof_validators.py --profile implementation --write --validate",
        {
            "go_binary_status": artifact_status(go_binary),
            "go_fast_profile": go_profile,
            "go_fast_summary": go_summary,
            "go_warning_count": go_warning_count,
            "go_warning_partition_declared": go_warning_partition_declared,
            "go_warning_partition_valid": go_warning_partition_valid,
            "go_warning_residue_count_matches": go_warning_residue_count_matches,
            "go_residue_classifiable_warning_count": go_residue_classifiable_warning_count,
            "go_post_residue_warning_count": go_post_residue_warning_count,
            "go_warnings_classified": go_warnings_classified,
            "warning_residue_status": artifact_status(warning_residue),
            "warning_residue_summary": warning_residue_summary,
        },
    ))

    source_freshness = as_dict(artifacts.get("source_freshness"))
    source_producer = as_dict(artifacts.get("source_producer"))
    source_summary = as_dict(source_freshness.get("summary"))
    producer_summary = as_dict(source_producer.get("summary"))
    warning_residue_classes = as_dict(warning_residue_summary.get("class_counts"))
    source_hash_mismatch_count = int_or(source_summary.get("hash_mismatch_count"))
    producer_hash_drift_count = max(
        int_or(producer_summary.get("hash_drift_count")),
        int_or(producer_summary.get("source_artifact_drift_count")),
    )
    classified_source_hash_drift = (
        source_hash_mismatch_count == 0
        and producer_hash_drift_count == 0
    ) or (
        source_hash_mismatch_count > 0
        and producer_hash_drift_count == source_hash_mismatch_count
        and int_or(warning_residue_classes.get("source_artifact_hash_drift")) >= source_hash_mismatch_count
    )
    source_required = any(surface in surfaces for surface in {"sql_canon", "source_lineage"})
    classified_source_freshness_residue = (
        artifact_status(source_freshness) == "warning"
        and int_or(source_summary.get("critical")) == 0
        and classified_source_hash_drift
        and int_or(source_summary.get("missing_source_artifact_row_count")) == 0
        and int_or(source_summary.get("blocked_source_status_count")) == 0
        and int_or(source_summary.get("forbidden_authority_status_count")) == 0
        and artifact_status(warning_residue) == "ok"
        and int_or(warning_residue_summary.get("critical")) == 0
        and int_or(warning_residue_summary.get("unclassified_count")) == 0
        and int_or(warning_residue_classes.get("source_artifact_freshness_residue")) >= int_or(source_summary.get("stale_artifact_count"))
    )
    gates.append(gate(
        "source_lineage_post_producer_clean",
        source_required,
        (
            (
                artifact_status(source_freshness) == "ok"
                and source_hash_mismatch_count == 0
                and producer_hash_drift_count == 0
            )
            or classified_source_freshness_residue
        )
        and artifact_status(source_producer) == "ok"
        and int_or(producer_summary.get("registry_gap_count")) == 0,
        "python scripts\\go_fast_proof_validators.py --profile implementation --write --validate",
        {"source_freshness": source_summary, "source_producer": producer_summary, "warning_residue": warning_residue_summary},
    ))

    provider_required = "provider_failure_policy" in surfaces
    provider_detail = provider_policy_evaluation(artifacts)
    gates.append(gate(
        "provider_failure_policy_clean",
        provider_required,
        provider_detail["ok"],
        "python scripts\\test_implementation_release_contract.py",
        provider_detail,
    ))

    pm_required = "pm_queue" in surfaces
    pm_detail = pm_authority_evaluation(artifacts)
    gates.append(gate(
        "pm_queue_authority_current",
        pm_required,
        pm_detail["ok"],
        "python scripts\\pm_control_packet.py --write --write-db --validate",
        pm_detail,
    ))

    skill_guard = as_dict(artifacts.get("skill_workshop_body_guard"))
    skill_guard_summary = as_dict(skill_guard.get("summary"))
    skill_guard_required = "skill_workshop_guard" in surfaces
    gates.append(gate(
        "skill_workshop_body_guard_clean",
        skill_guard_required,
        artifact_status(skill_guard) in {"ok", "warning"}
        and int_or(skill_guard_summary.get("critical_count")) == 0
        and int_or(skill_guard_summary.get("live_error_count")) == 0
        and as_dict(skill_guard.get("pair_result")).get("status") not in {"error"},
        "python scripts\\skill_workshop_body_guard.py --write --validate",
        {"summary": skill_guard_summary, "pair_status": as_dict(skill_guard.get("pair_result")).get("status")},
    ))

    closeout = as_dict(artifacts.get("control_closeout"))
    closeout_required = "closeout" in surfaces
    gates.append(gate(
        "control_closeout_current",
        closeout_required,
        artifact_status(closeout) == "ok",
        "python scripts\\control_closeout_bundle.py --validation-budget shared --write --validate",
        {"control_closeout_status": artifact_status(closeout), "summary": as_dict(closeout.get("summary"))},
    ))
    return gates


def build_payload(
    *,
    base: str = "HEAD",
    include_untracked: bool = True,
    paths: list[str] | None = None,
    phase: str = "advisory",
    artifact_overrides: dict[str, Any] | None = None,
    proof_freshness_test_metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    route = changed_router.build_payload(base, include_untracked, paths)
    changed_paths = [normalize(path) for path in as_list(route.get("changed_paths"))]
    artifacts = load_artifacts(artifact_overrides)
    surface_paths, surface_scope = surface_paths_for_scope(changed_paths, artifacts, paths)
    surfaces = classify_paths(surface_paths)
    gates = evaluate_gates(surfaces, artifacts)
    proof_freshness = proof_freshness_evaluation(
        gates,
        surface_paths,
        artifacts,
        artifact_overrides,
        proof_freshness_test_metadata,
    )
    apply_proof_freshness(gates, proof_freshness)
    warnings = classify_warnings(artifacts, surfaces)
    unknown_warnings = [row for row in warnings if row.get("class") is None]
    blocking_warnings = [row for row in warnings if row.get("class") in BLOCKING_WARNING_CLASSES]
    missing_gates = [item for item in gates if item["required"] and not item["ok"]]
    ready_to_close = not missing_gates and not unknown_warnings and not blocking_warnings

    errors: list[str] = []
    validation_warnings: list[str] = []
    if missing_gates:
        validation_warnings.append("required_release_gates_not_proven")
    if unknown_warnings:
        validation_warnings.append("unknown_warning_residue_present")
    if blocking_warnings:
        validation_warnings.append("blocking_warning_residue_present")
    if phase == "blocking":
        errors.extend(f"missing_gate:{item['name']}" for item in missing_gates)
        errors.extend(f"unknown_warning:{item['source']}" for item in unknown_warnings)
        errors.extend(f"blocking_warning:{item['source']}:{item['class']}" for item in blocking_warnings)

    status = "ok" if ready_to_close else "warning"
    if errors:
        status = "blocked"

    return {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": status,
        "phase": phase,
        "authority_boundary": AUTHORITY_BOUNDARY,
        "summary": {
            "changed_path_count": len(changed_paths),
            "surface_path_count": len(surface_paths),
            "surface_count": len(surfaces),
            "required_gate_count": sum(1 for item in gates if item["required"]),
            "missing_gate_count": len(missing_gates),
            "warning_count": len(warnings),
            "unknown_warning_count": len(unknown_warnings),
            "blocking_warning_count": len(blocking_warnings),
            "proof_freshness_evaluated_gate_count": int_or(as_dict(proof_freshness.get("summary")).get("evaluated_gate_count")),
            "stale_or_unproven_proof_gate_count": int_or(as_dict(proof_freshness.get("summary")).get("stale_or_unproven_gate_count")),
            "stale_proof_artifact_count": int_or(as_dict(proof_freshness.get("summary")).get("stale_artifact_count")),
            "unproven_proof_artifact_count": int_or(as_dict(proof_freshness.get("summary")).get("unproven_artifact_count")),
            "ready_to_close": ready_to_close,
            "next_safe_action": (
                "Closeout can proceed through normal proof."
                if ready_to_close
                else "Run missing proof in finalization_order, classify warning residue, then regenerate this contract."
            ),
        },
        "changed_file_route": route,
        "surface_scope": surface_scope,
        "surface_paths": surface_paths,
        "surfaces": surfaces,
        "required_commands": required_commands(surfaces),
        "finalization_order": finalization_order(surfaces),
        "release_gates": gates,
        "proof_freshness": proof_freshness,
        "warning_taxonomy": {
            "allowed_classes": sorted(WARNING_CLASSES),
            "blocking_classes": sorted(BLOCKING_WARNING_CLASSES),
            "classified_warnings": warnings,
        },
        "stop_lines": [
            "This contract is proof-only and may not mutate cron schedules, runtime config, SQL/canon, portfolio, customer, paper/live, brokerage, account, or money-movement surfaces.",
            "Unknown warning residue blocks blocking-phase closeout until classified or repaired.",
            "Source-lineage metadata repair remains separately gated; this script only detects missing post-producer proof.",
        ],
        "validation": {
            "status": "error" if errors else "warning" if validation_warnings else "ok",
            "errors": errors,
            "warnings": validation_warnings,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", default="HEAD")
    parser.add_argument("--include-untracked", action="store_true")
    parser.add_argument("--no-untracked", action="store_false", dest="include_untracked")
    parser.set_defaults(include_untracked=True)
    parser.add_argument("--path", action="append", dest="paths")
    parser.add_argument("--phase", choices=["advisory", "blocking"], default="advisory")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    payload = build_payload(base=args.base, include_untracked=args.include_untracked, paths=args.paths, phase=args.phase)
    out = args.out if args.out.is_absolute() else ROOT / args.out
    if args.write:
        atomic_write_json(out, payload)
    print(
        f"status={payload['status']} phase={payload['phase']} surfaces={payload['summary']['surface_count']} "
        f"missing_gates={payload['summary']['missing_gate_count']} unknown_warnings={payload['summary']['unknown_warning_count']} "
        f"ready_to_close={payload['summary']['ready_to_close']} out={rel(out)}"
    )
    if args.validate and payload["validation"]["status"] == "error":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
