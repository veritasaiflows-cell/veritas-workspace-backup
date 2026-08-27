#!/usr/bin/env python3
"""Build the Veritas harness scorecard for active workflow proof surfaces.

The scorecard is a local operator artifact. It checks readiness and proof
surfaces, but it does not mutate finance canon, infer approval, deliver
externally, or authorize paper/live actions.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from go_sql_helper_route_registry import GO_BIN_DIR, SELECTED_INPROCESS_BINARY_HELPERS, binary_default_command, build_command
from market_data_utils import atomic_write_json, atomic_write_text, load_json_artifact

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
GO_SCRIPT_BIN = ROOT / "scripts" / "go" / "bin"
DEFAULT_JSON = TMP / "veritas-harness-scorecard.json"
DEFAULT_MD = DEFAULT_JSON.with_suffix(".md")

SCHEMA = "veritas.harness.scorecard.v1"

ARTIFACT_CHECKS = [
    ("wf75_service_state", TMP / "wf75-service-state-current.json", "validation.status", {"ok"}),
    ("wf75_sqlite_control_plane", TMP / "wf75-service-state-sqlite.json", "validation.status", {"ok"}),
    ("wf75_operator_queue", TMP / "wf75-operator-queue.json", "validation.status", {"ok"}),
    ("wf75_operator_console", TMP / "wf75-operator-console.json", "validation.status", {"ok"}),
    ("wf75_renderer_regression", TMP / "wf75-renderer-export-regression.json", "validation.status", {"ok"}),
    ("wf75_scenario_library", TMP / "wf75-scenario-template-library.json", "validation.status", {"ok"}),
    ("generic_service_run_contract", TMP / "generic-service-run-contract.json", "validation.status", {"ok"}),
    ("smb_workflow_scenario_library", TMP / "wf75-smb-workflow-scenario-library.json", "validation.status", {"ok"}),
    ("smb_customer_preview", TMP / "wf75-smb-customer-preview.json", "validation.status", {"ok"}),
    ("smb_customer_preview_validation", TMP / "wf75-smb-customer-preview-validation.json", "validation.status", {"ok"}),
    ("smb_pilot_decision_packet", TMP / "wf75-smb-pilot-decision-packet.json", "validation.status", {"ok"}),
    ("smb_automation_blueprints", TMP / "wf75-smb-automation-blueprints.json", "validation.status", {"ok"}),
    ("smb_automation_blueprints_validation", TMP / "wf75-smb-automation-blueprints-validation.json", "validation.status", {"ok"}),
    ("smb_offer_icp_packet", TMP / "wf79-smb-offer-icp-packet.json", "validation.status", {"ok"}),
    ("smb_demo_packets_validation", TMP / "wf79-smb-demo-packets-validation.json", "validation.status", {"ok"}),
    ("smb_marketing_ops_blueprints_validation", TMP / "wf79-smb-marketing-ops-blueprints-validation.json", "validation.status", {"ok"}),
    ("smb_cockpit_panel", TMP / "wf79-smb-cockpit-panel.json", "validation.status", {"ok"}),
    ("smb_sales_practice_packet", TMP / "wf79-smb-sales-practice-packet.json", "validation.status", {"ok"}),
    ("smb_phase_closeout", TMP / "wf79-smb-phase-closeout.json", "validation.status", {"ok"}),
    ("smb_go_boundary_lint", TMP / "wf75-smb-boundary-lint.json", "status", {"ok"}),
    ("wf75_pm_update", TMP / "wf75-pm-weekly-update.json", "status", {"ready_for_internal_pm_review"}),
    ("wf75_pm_handoff", TMP / "wf75-artifact-only-pm-handoff.json", "validation.status", {"ok"}),
    ("wf75_pm_readiness_pdf_manifest", TMP / "wf75-pm-readiness-brief.json", "validation.status", {"ok"}),
    ("macro_event_calendar", TMP / "macro-event-calendar.json", "validation.status", {"ok"}),
    ("macro_metrics_current", TMP / "macro-metrics-current.json", "validation.status", {"ok"}),
    ("macro_judgment_draft", TMP / "macro-judgment-draft.json", "validation.status", {"ok"}),
    ("json_sql_promotion_index", TMP / "json-sql-promotion-index.json", "validation.status", {"ok"}),
    ("finance_sql_go_boundary_lint", TMP / "finance-sql-boundary-lint.json", "status", {"ok"}),
    ("python_sql_contract_lint", TMP / "python-sql-contract-lint.json", "status", {"ok", "warning"}),
    ("sql_schema_drift_lint", TMP / "sql-schema-drift-lint.json", "status", {"ok"}),
    ("sql_proof_probe", TMP / "sql-proof-probe.json", "status", {"ok"}),
    ("go_sql_latency_probe", TMP / "go-sql-latency-probe.json", "status", {"ok"}),
    ("go_sql_latency_probe_inprocess_driver", TMP / "go-sql-latency-probe.json", "sqlite_driver", {"inprocess"}),
    ("go_sql_inventory_helper", TMP / "go-sql-inventory-helper.json", "status", {"ok"}),
    ("go_sql_inventory_helper_inprocess_driver", TMP / "go-sql-inventory-helper.json", "sqlite_driver", {"inprocess"}),
    ("python_go_sql_parity_check", TMP / "python-go-sql-parity-check.json", "status", {"ok"}),
    ("python_go_sql_migration_candidates", TMP / "python-go-sql-migration-candidates.json", "status", {"ok", "warning"}),
    ("go_sql_source_truth_manifest", TMP / "go-sql-source-truth-authority-manifest.json", "status", {"ready_for_phase2_parity_scaffold"}),
    ("python_go_source_truth_manifest_parity", TMP / "python-go-source-truth-manifest-parity.json", "status", {"ok"}),
    ("go_source_truth_parity_validator", TMP / "go-source-truth-parity-validation.json", "status", {"phase2_parity_green_for_entry_stop_reference_metadata", "phase2_sql_first_thin_board_contract_ok"}),
    ("python_go_source_truth_parity_validator_parity", TMP / "python-go-source-truth-parity-validator-parity.json", "status", {"ok"}),
    ("go_sql_500_expansion_gate", TMP / "go-sql-500-ticker-expansion-design-gate.json", "status", {"ready_for_source_open_cleanup"}),
    ("python_go_sql_500_expansion_gate_parity", TMP / "python-go-sql-500-expansion-gate-parity.json", "status", {"ok"}),
    ("go_finance_data_coverage_probe", TMP / "go-finance-data-coverage-probe.json", "status", {"ok", "warning"}),
    ("python_go_finance_data_coverage_probe_parity", TMP / "python-go-finance-data-coverage-probe-parity.json", "status", {"ok"}),
    ("go_finance_human_notes_sql_check", TMP / "go-finance-human-notes-sql-check.json", "status", {"ok"}),
    ("go_finance_human_notes_sql_check_inprocess_driver", TMP / "go-finance-human-notes-sql-check.json", "sql_canon_check.sqlite_driver", {"inprocess"}),
    ("python_go_finance_human_notes_sql_check_parity", TMP / "python-go-finance-human-notes-sql-check-parity.json", "status", {"ok"}),
    ("go_finance_universe_validation_probe", TMP / "go-finance-universe-validation-probe.json", "status", {"ok"}),
    ("python_go_finance_universe_validation_parity", TMP / "python-go-finance-universe-validation-parity.json", "status", {"ok"}),
    ("go_wf78_sql_phase2_readiness_probe", TMP / "go-wf78-sql-phase2-readiness-probe.json", "status", {"ok"}),
    ("python_go_wf78_sql_phase2_readiness_parity", TMP / "python-go-wf78-sql-phase2-readiness-parity.json", "status", {"ok"}),
    ("python_go_durable_output_parity_repeated_gate", TMP / "python-go-durable-output-parity-repeated-gate.json", "status", {"ok"}),
    ("go_sql_consumer_authority_guard", TMP / "go-sql-consumer-authority-guard.json", "status", {"ok", "fail_closed"}),
    ("python_go_sql_consumer_authority_guard_parity", TMP / "python-go-sql-consumer-authority-guard-parity.json", "status", {"ok"}),
    ("python_go_sql_consumer_authority_guard_fixture_parity", TMP / "python-go-sql-consumer-authority-guard-fixture-parity.json", "status", {"ok"}),
    ("python_go_sql_consumer_authority_dashboard_ab", TMP / "python-go-sql-consumer-authority-dashboard-ab.json", "status", {"ok"}),
    ("python_go_sql_consumer_authority_demotion_dry_run", TMP / "python-go-sql-consumer-authority-demotion-dry-run.json", "status", {"ok"}),
    ("python_go_sql_consumer_authority_controlled_router", TMP / "python-go-sql-consumer-authority-controlled-router.json", "status", {"ok"}),
    ("python_go_sql_helper_demotion_readiness_gate", TMP / "python-go-sql-helper-demotion-readiness-gate.json", "status", {"ok", "warning"}),
    ("python_go_sql_helper_demotion_queue", TMP / "python-go-sql-helper-demotion-queue.json", "status", {"ok"}),
    ("python_go_sql_helper_contract_gate", TMP / "python-go-sql-helper-contract-gate.json", "status", {"ok"}),
    ("python_go_sql_helper_controlled_router_batch", TMP / "python-go-sql-helper-controlled-router-batch.json", "status", {"ok"}),
    ("python_go_sql_helper_go_primary_history_gate", TMP / "python-go-sql-helper-go-primary-history-gate.json", "status", {"ok"}),
    ("python_go_sql_helper_default_route_promotion", TMP / "python-go-sql-helper-default-route-promotion.json", "status", {"ok"}),
    ("python_go_sql_helper_default_route_history_gate", TMP / "python-go-sql-helper-default-route-history-gate.json", "status", {"ok"}),
    ("python_go_sql_helper_fallback_removal_readiness_gate", TMP / "python-go-sql-helper-fallback-removal-readiness-gate.json", "status", {"ok"}),
    ("python_go_sql_helper_retirement_gate", TMP / "python-go-sql-helper-retirement-gate.json", "status", {"ok"}),
    ("go_sql_inprocess_driver_pilot_gate", TMP / "go-sql-inprocess-driver-pilot-gate.json", "status", {"ok"}),
    ("runtime_performance_scorecard", TMP / "runtime-performance-scorecard.json", "status", {"ok", "warning"}),
    ("wf55_recommendation_outcome_ledger", TMP / "recommendation-outcome-ledger-current.json", "status", {"ok"}),
    ("wf55_outcome_ledger_validation", TMP / "wf55-outcome-ledger-v2-validation.json", "status", {"ok"}),
    ("wf77_price_bridge", TMP / "wf77-price-freshness-bridge.json", "status", {"ok", "warning"}),
    ("retail_truth_routing_contract", TMP / "retail-truth-routing-contract.json", "validation.status", {"ok"}),
    ("retail_answer_harness", TMP / "retail-answer-harness.json", "validation.status", {"ok"}),
    ("retail_automation_control_plane", TMP / "retail-automation-control-plane.json", "validation.status", {"ok"}),
]

READINESS_WARNING_ARTIFACTS = [
    ("wf55_probability_readiness", TMP / "probability-readiness-report.json", "verdict", {"READY", "NOT_READY", "SAFE_WITH_GAPS"}),
]

AUTHORITY_FALSE_KEYS = [
    "public_launch_allowed",
    "public_launch_ready",
    "real_customer_data_allowed",
    "customer_data_retention_allowed",
    "external_delivery_allowed",
    "legal_or_compliance_ready",
    "source_licensing_assumed",
    "personalized_regulated_advice_allowed",
    "brokerage_or_account_connection_allowed",
    "paper_or_live_execution_allowed",
    "trading_account_or_paper_execution_allowed",
    "portfolio_or_canon_mutation_allowed",
    "sql_or_ticker_import_allowed",
    "owner_approval_inferred",
    "customer_identity_allowed",
    "customer_outreach_allowed",
    "message_sending_allowed",
    "phone_system_or_crm_credential_access_allowed",
    "payment_pos_payroll_account_access_allowed",
    "implementation_in_customer_systems_allowed",
    "guaranteed_revenue_or_roi_claim_allowed",
    "legal_tax_compliance_security_readiness_claim_allowed",
    "automation_platform_credential_access_allowed",
    "outbound_automation_allowed",
    "customer_system_writeback_allowed",
]


# Gates that are intentionally in a non-promoted / fail-closed-by-design state.
# A matching failing check is reclassified from "fail" to "expected_pending" so a
# known, deliberate gate does not flip the whole scorecard to "blocked". The
# reclassify only applies while the gate artifact still proves its intentional
# shape; any other value, a real breakage, or a crash/timeout stays "fail".
EXPECTED_PENDING_GATES: dict[str, dict[str, Any]] = {
    "go_sql_inprocess_driver_pilot_gate": {
        "reason": (
            "In-process SQLite driver pilot is intentionally not promoted to the "
            "default route; Python fallback retained. Gate is blocked by design "
            "until the compiled-binary default route is owner-promoted."
        ),
        "artifact": TMP / "go-sql-inprocess-driver-pilot-gate.json",
        "pending_work": "In-process SQL driver promotion (compiled-binary default route).",
        "expected_command_returncode": 2,
    },
    "python_go_sql_consumer_authority_guard_parity": {
        "reason": (
            "Live A2 SQL consumer guard is intentionally fail-closed while clean "
            "fixtures prove parity. Validation is ok and critical count is zero."
        ),
        "artifact": TMP / "python-go-sql-consumer-authority-guard-parity.json",
        "pending_work": "Resolve live A2 stale/unsafe read posture before promoting beyond fail-closed proof.",
    },
    "python_go_sql_consumer_authority_dashboard_ab": {
        "reason": (
            "Dashboard A/B gate intentionally reports expected fail-closed live "
            "posture while synthetic clean fixtures pass."
        ),
        "artifact": TMP / "python-go-sql-consumer-authority-dashboard-ab.json",
        "pending_work": "Accrue longer clean A/B history before any default-route promotion.",
    },
    "python_go_sql_consumer_authority_demotion_dry_run": {
        "reason": (
            "Demotion dry-run is proof-only and intentionally warning until live "
            "A2 is ready for Go-primary read without widening authority."
        ),
        "artifact": TMP / "python-go-sql-consumer-authority-demotion-dry-run.json",
        "pending_work": "Keep Python fallback retained and resolve live fail-closed posture.",
    },
    "python_go_sql_consumer_authority_controlled_router": {
        "reason": (
            "Controlled router remains proof-only; warning means live A2 is safely "
            "fail-closed and not ready for default promotion."
        ),
        "artifact": TMP / "python-go-sql-consumer-authority-controlled-router.json",
        "pending_work": "Keep default route Python-owned until controlled history is clean.",
    },
    "python_go_sql_helper_demotion_queue": {
        "reason": (
            "Demotion queue records the expected fail-closed first helper state; "
            "this is migration backlog, not a harness break."
        ),
        "artifact": TMP / "python-go-sql-helper-demotion-queue.json",
        "pending_work": "Work the queued helper contracts before any Python retirement.",
    },
    "go_source_truth_parity_validator": {
        "reason": (
            "Source-truth parity validator still targets Markdown Execution Board rows, "
            "but the board is intentionally SQL-first/thin during migration. This is a "
            "known source-truth migration backlog item, not a retail truth-routing break."
        ),
        "artifact": TMP / "go-source-truth-parity-validation.json",
        "pending_work": "Retarget the Go source-truth parity validator to SQL-native reference/source lineage proof before using it as a hard promotion gate.",
        "expected_command_returncodes": {1, 2},
    },
}


def pilot_gate_intentional_pending(payload: Any) -> bool:
    """True when the in-process driver pilot gate is blocked only because it is
    deliberately not promoted (every helper comparison passed, fallback retained)."""
    if not isinstance(payload, dict) or payload.get("status") != "blocked":
        return False
    summary = as_dict(payload.get("summary"))
    validation = as_dict(payload.get("validation"))
    helpers_compared = summary.get("helpers_compared")
    return (
        helpers_compared is not None
        and helpers_compared == summary.get("helpers_ok")
        and int(summary.get("critical") or 0) == 0
        and not validation.get("errors")
        and summary.get("python_fallback_retained") is True
        and summary.get("compiled_binary_default_route_active") is False
        and summary.get("routing_changed_by_this_gate") is False
    )


EXPECTED_PENDING_PREDICATES = {
    "go_sql_inprocess_driver_pilot_gate": pilot_gate_intentional_pending,
}


def source_truth_parity_sql_first_pending(payload: Any) -> bool:
    if isinstance(payload, dict) and payload.get("status") == "phase2_sql_first_thin_board_contract_ok":
        return True
    if not isinstance(payload, dict) or payload.get("status") != "phase2_parity_not_ready":
        return False
    summary = as_dict(payload.get("summary"))
    return (
        int(summary.get("markdown_rows") or 0) == 0
        and int(summary.get("finance_sql_rows") or 0) > 0
        and int(summary.get("canon_cache_tickers") or 0) > 0
        and int(summary.get("mismatch_rows") or 0) == 0
        and int(summary.get("missing_finance_rows") or 0) == 0
        and int(summary.get("missing_canon_rows") or 0) == 0
    )


def expected_fail_closed_warning(payload: Any) -> bool:
    if not isinstance(payload, dict) or payload.get("status") != "warning":
        return False
    summary = as_dict(payload.get("summary"))
    validation = as_dict(payload.get("validation"))
    if validation.get("status") != "ok" or int(summary.get("critical") or 0) != 0:
        return False
    signal = (
        summary.get("demotion_readiness_signal")
        or summary.get("dry_run_signal")
        or summary.get("controlled_router_signal")
        or summary.get("queue_signal")
        or summary.get("demotion_gate_signal")
        or ""
    )
    if str(signal).startswith("expected_fail_closed"):
        return True
    findings = [row for row in as_list(payload.get("findings")) if isinstance(row, dict)]
    return any(row.get("severity") == "warning" and "expected_fail_closed" in str(row.get("check") or "") for row in findings)


for gate_name in (
    "python_go_sql_consumer_authority_guard_parity",
    "python_go_sql_consumer_authority_dashboard_ab",
    "python_go_sql_consumer_authority_demotion_dry_run",
    "python_go_sql_consumer_authority_controlled_router",
    "python_go_sql_helper_demotion_queue",
):
    EXPECTED_PENDING_PREDICATES[gate_name] = expected_fail_closed_warning

EXPECTED_PENDING_PREDICATES["go_source_truth_parity_validator"] = source_truth_parity_sql_first_pending


def apply_expected_pending(checks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Reclassify failing checks that are known intentional / not-yet-promoted
    gates from 'fail' to 'expected_pending' so they do not force the scorecard to
    'blocked'. Each reclassified row stays visible in checks. Returns the
    reclassified rows."""
    reclassified: list[dict[str, Any]] = []
    for row in checks:
        cfg = EXPECTED_PENDING_GATES.get(row.get("name", ""))
        if not cfg or row.get("status") != "fail":
            continue
        predicate = EXPECTED_PENDING_PREDICATES.get(row.get("name", ""))
        payload = load_json_artifact(cfg["artifact"])
        if predicate is None or not predicate(payload):
            continue
        if row.get("type") == "command":
            expected_returncodes = cfg.get("expected_command_returncodes")
            if expected_returncodes is not None:
                if row.get("returncode") not in expected_returncodes:
                    continue
            elif row.get("returncode") != cfg.get("expected_command_returncode"):
                continue
        row["status"] = "expected_pending"
        row["expected_pending_reason"] = cfg["reason"]
        row["pending_work"] = cfg["pending_work"]
        reclassified.append(row)
    return reclassified


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def nested_get(payload: dict[str, Any], dotted: str) -> Any:
    value: Any = payload
    for part in dotted.split("."):
        if not isinstance(value, dict):
            return None
        value = value.get(part)
    return value


def find_authority_regressions(value: Any, prefix: str = "") -> list[str]:
    findings: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            path = f"{prefix}.{key}" if prefix else str(key)
            if key in AUTHORITY_FALSE_KEYS and item not in (False, 0):
                findings.append(f"{path}={item!r}")
            findings.extend(find_authority_regressions(item, path))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            findings.extend(find_authority_regressions(item, f"{prefix}[{index}]"))
    return findings


def artifact_check(name: str, path: Path, field: str, accepted: set[str], warning_only: bool = False) -> dict[str, Any]:
    payload = load_json_artifact(path)
    row: dict[str, Any] = {
        "name": name,
        "type": "artifact",
        "path": rel(path),
        "exists": path.exists(),
        "parseable_json": isinstance(payload, dict),
        "field": field,
        "accepted": sorted(accepted),
    }
    if not isinstance(payload, dict):
        row.update({"status": "fail", "observed": None, "notes": "missing or unparseable JSON"})
        return row
    observed = nested_get(payload, field)
    regressions = find_authority_regressions(payload)
    row["observed"] = observed
    if regressions:
        row.update({"status": "fail", "notes": "authority regression", "authority_regressions": regressions[:20]})
    elif str(observed) in accepted:
        row.update({"status": "pass", "notes": "accepted"})
    elif warning_only:
        row.update({"status": "warn", "notes": "readiness gap"})
    else:
        row.update({"status": "fail", "notes": "unexpected status"})
    return row


def terminate_process_tree(process: subprocess.Popen[str]) -> dict[str, Any]:
    """Best-effort child cleanup after a timeout.

    Windows process shims can leave grandchildren running after
    subprocess.communicate(timeout=...). Use taskkill /T where available so a
    timed-out harness check does not keep running silently in the background.
    """
    result: dict[str, Any] = {"attempted": True, "pid": process.pid}
    try:
        if os.name == "nt":
            completed = subprocess.run(
                ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                text=True,
                encoding="utf-8",
                errors="replace",
                capture_output=True,
                timeout=15,
            )
            result.update(
                {
                    "method": "taskkill_tree",
                    "returncode": completed.returncode,
                    "stdout_tail": (completed.stdout or "")[-1000:],
                    "stderr_tail": (completed.stderr or "")[-1000:],
                }
            )
        else:
            process.kill()
            result.update({"method": "process_kill"})
    except Exception as exc:  # pragma: no cover - defensive cleanup path
        result.update({"error": str(exc)})
    return result


def run_command(name: str, command: list[str], timeout: int = 120, cwd: Path = ROOT) -> dict[str, Any]:
    row: dict[str, Any] = {
        "name": name,
        "type": "command",
        "command": command,
        "timeout_seconds": timeout,
        "cwd": rel(cwd),
    }
    executable = shutil.which(command[0])
    if executable is None and not Path(command[0]).exists():
        row.update({"status": "warn", "returncode": None, "notes": f"binary not found: {command[0]}"})
        return row
    resolved_command = [executable or command[0], *command[1:]]
    started = time.perf_counter()
    row["started_at_utc"] = utc_now()
    print(f"running_check={name} timeout={timeout}s", flush=True)
    try:
        process = subprocess.Popen(
            resolved_command,
            cwd=str(cwd),
            text=True,
            encoding="utf-8",
            errors="replace",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        stdout, stderr = process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        cleanup = terminate_process_tree(process)
        duration = round(time.perf_counter() - started, 3)
        row.update(
            {
                "status": "fail",
                "returncode": None,
                "duration_seconds": duration,
                "notes": f"timeout after {timeout}s",
                "stdout_tail": ((exc.stdout or "") if isinstance(exc.stdout, str) else "").encode("utf-8", errors="replace").decode("utf-8", errors="replace")[-3000:],
                "stderr_tail": ((exc.stderr or "") if isinstance(exc.stderr, str) else "").encode("utf-8", errors="replace").decode("utf-8", errors="replace")[-3000:],
                "timeout_cleanup": cleanup,
            }
        )
        return row
    duration = round(time.perf_counter() - started, 3)
    status = "pass" if process.returncode == 0 else "fail"
    row.update(
        {
            "status": status,
            "returncode": process.returncode,
            "duration_seconds": duration,
            "stdout_tail": (stdout or "")[-3000:],
            "stderr_tail": (stderr or "")[-3000:],
            "notes": "ok" if status == "pass" else "command failed",
        }
    )
    return row


def go_script_bin_command(name: str, *args: str) -> list[str]:
    return [str(GO_SCRIPT_BIN / f"{name}.exe"), *args]


def fast_command_checks() -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = [
        run_command("python_compile_harness_classifier", [sys.executable, "-m", "py_compile", "scripts\\veritas_harness_failure_classifier.py"]),
        run_command("python_compile_harness_scorecard", [sys.executable, "-m", "py_compile", "scripts\\veritas_harness_scorecard.py"]),
        run_command("artifact_index_incremental", [sys.executable, "scripts\\artifact_index.py", "incremental"], timeout=180),
        run_command("artifact_index_validate", [sys.executable, "scripts\\artifact_index.py", "validate"], timeout=180),
    ]
    if (ROOT / "scripts" / "wf74_clawhub_inspect.mjs").exists():
        checks.append(run_command("node_clawhub_inspector_syntax", ["node", "--check", "scripts\\wf74_clawhub_inspect.mjs"], timeout=60))
    return checks


def openclaw_command_checks() -> list[dict[str, Any]]:
    if shutil.which("openclaw"):
        return [run_command("openclaw_skills_check", ["openclaw", "skills", "check"], timeout=180)]
    return [{"name": "openclaw_skills_check", "type": "command", "status": "warn", "notes": "openclaw CLI not found on PATH"}]


def go_command_checks() -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    if not (ROOT / "scripts" / "go" / "go.mod").exists():
        return checks
    checks.append(run_command("go_boundary_lint_tests", ["go", "test", ".\\..."], timeout=180, cwd=ROOT / "scripts" / "go"))
    for helper in SELECTED_INPROCESS_BINARY_HELPERS:
        checks.append(run_command(f"build_{helper['key']}_binary", build_command(helper), timeout=300, cwd=ROOT / "scripts" / "go"))
    checks.append(
        run_command(
            "go_wf75_smb_boundary_lint",
            ["go", "run", ".\\cmd\\wf75-smb-boundary-lint", "--root", "..\\..", "--out", "..\\..\\tmp\\wf75-smb-boundary-lint.json"],
            timeout=180,
            cwd=ROOT / "scripts" / "go",
        )
    )
    checks.append(
        run_command(
            "go_finance_sql_boundary_lint",
            ["go", "run", ".\\cmd\\finance-sql-boundary-lint", "--root", "..\\..", "--out", "..\\..\\tmp\\finance-sql-boundary-lint.json"],
            timeout=180,
            cwd=ROOT / "scripts" / "go",
        )
    )
    checks.append(
        run_command(
            "go_python_sql_contract_lint",
            ["go", "run", ".\\cmd\\python-sql-contract-lint", "--root", "..\\..", "--out", "..\\..\\tmp\\python-sql-contract-lint.json"],
            timeout=180,
            cwd=ROOT / "scripts" / "go",
        )
    )
    checks.append(
        run_command(
            "go_sql_schema_drift_lint",
            ["go", "run", ".\\cmd\\sql-schema-drift-lint", "--root", "..\\..", "--out", "..\\..\\tmp\\sql-schema-drift-lint.json"],
            timeout=180,
            cwd=ROOT / "scripts" / "go",
        )
    )
    checks.append(
        run_command(
            "go_sql_proof_probe",
            ["go", "run", ".\\cmd\\sql-proof-probe", "--root", "..\\..", "--out", "..\\..\\tmp\\sql-proof-probe.json"],
            timeout=180,
            cwd=ROOT / "scripts" / "go",
        )
    )
    for helper in SELECTED_INPROCESS_BINARY_HELPERS:
        checks.append(run_command(helper["key"], binary_default_command(helper), timeout=180, cwd=ROOT))
    checks.append(
        run_command(
            "go_sql_source_truth_manifest",
            ["go", "run", ".\\cmd\\go-sql-source-truth-manifest", "--root", "..\\..", "--out", "..\\..\\tmp\\go-sql-source-truth-authority-manifest.json"],
            timeout=180,
            cwd=ROOT / "scripts" / "go",
        )
    )
    checks.append(
        run_command(
            "go_source_truth_parity_validator",
            ["go", "run", ".\\cmd\\go-source-truth-parity-validator", "--root", "..\\..", "--out", "..\\..\\tmp\\go-source-truth-parity-validation.json"],
            timeout=180,
            cwd=ROOT / "scripts" / "go",
        )
    )
    checks.append(
        run_command(
            "go_sql_500_expansion_gate",
            go_script_bin_command(
                "go-sql-500-expansion-design-gate",
                "--root",
                str(ROOT),
                "--out",
                str(TMP / "go-sql-500-ticker-expansion-design-gate.json"),
            ),
            timeout=180,
            cwd=ROOT,
        )
    )
    return checks


def slow_command_checks() -> list[dict[str, Any]]:
    return [run_command("wf75_renderer_regression", [sys.executable, "scripts\\wf75_renderer_export_regression.py", "--write", "--validate"], timeout=240)]


def command_checks(lanes: set[str]) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    if "fast" in lanes:
        checks.extend(fast_command_checks())
    if "openclaw" in lanes:
        checks.extend(openclaw_command_checks())
    if "go" in lanes:
        checks.extend(go_command_checks())
    if "slow" in lanes:
        checks.extend(slow_command_checks())
    return checks


def build_scorecard(command_lanes: set[str] | None = None) -> dict[str, Any]:
    command_lanes = command_lanes or set()
    checks: list[dict[str, Any]] = []
    checks.extend(command_checks(command_lanes))
    checks.extend(artifact_check(name, path, field, accepted) for name, path, field, accepted in ARTIFACT_CHECKS)
    checks.extend(artifact_check(name, path, field, accepted, warning_only=True) for name, path, field, accepted in READINESS_WARNING_ARTIFACTS)

    expected_pending = apply_expected_pending(checks)
    pass_count = sum(1 for row in checks if row.get("status") == "pass")
    warn_count = sum(1 for row in checks if row.get("status") == "warn")
    fail_count = sum(1 for row in checks if row.get("status") == "fail")
    expected_pending_count = len(expected_pending)
    status = "ok" if fail_count == 0 and warn_count == 0 else "warning" if fail_count == 0 else "blocked"

    recommendation_ledger = as_dict(load_json_artifact(TMP / "recommendation-outcome-ledger-current.json"))
    rec_summary = as_dict(recommendation_ledger.get("recommendation_tracking_summary"))
    scenario_library = as_dict(load_json_artifact(TMP / "wf75-scenario-template-library.json"))
    smb_scenario_library = as_dict(load_json_artifact(TMP / "wf75-smb-workflow-scenario-library.json"))
    console = as_dict(load_json_artifact(TMP / "wf75-operator-console.json"))

    scorecard = {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": status,
        "summary": {
            "checks_total": len(checks),
            "pass_count": pass_count,
            "warning_count": warn_count,
            "failure_count": fail_count,
            "expected_pending_count": expected_pending_count,
            "scenario_count": scenario_library.get("template_count"),
            "smb_scenario_count": smb_scenario_library.get("scenario_count"),
            "recommendation_tracking_rows": rec_summary.get("tracking_row_count"),
            "pending_paper_card_rows": rec_summary.get("pending_paper_card_rows"),
            "operator_console_status": console.get("status"),
        },
        "checks": checks,
        "open_readiness_gaps": [
            row for row in checks if row.get("status") in {"warn", "fail"}
        ],
        "expected_pending_gates": [
            {
                "name": row.get("name"),
                "type": row.get("type"),
                "observed": row.get("observed"),
                "returncode": row.get("returncode"),
                "reason": row.get("expected_pending_reason"),
                "pending_work": row.get("pending_work"),
            }
            for row in expected_pending
        ],
        "operator_guidance": {
            "report_errors": True,
            "harmless_shell_errors": "Report them, but classify separately from validator failures. Prefer exact command/output and any referenced artifact path.",
            "real_breakage": "Fix the producer or validator before relying on the consuming workflow.",
            "readiness_warning": "Allowed only when downstream surfaces explicitly permit warning status; otherwise refresh evidence/history first.",
        },
        "authority_boundary": {
            "workflow_mutation_allowed": False,
            "external_delivery_allowed": False,
            "public_launch_allowed": False,
            "real_customer_data_allowed": False,
            "portfolio_or_canon_mutation_allowed": False,
            "paper_or_live_execution_allowed": False,
            "owner_approval_inferred": False,
        },
        "command_lanes": sorted(command_lanes),
    }
    scorecard["validation"] = validate(scorecard)
    if scorecard["validation"]["status"] != "ok" and scorecard["status"] == "ok":
        scorecard["status"] = "warning"
    return scorecard


def validate(scorecard: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    if scorecard.get("schema") != SCHEMA:
        errors.append("schema mismatch")
    boundary = as_dict(scorecard.get("authority_boundary"))
    for key, value in boundary.items():
        if value is not False:
            errors.append(f"authority flag must be false: {key}")
    summary = as_dict(scorecard.get("summary"))
    if int(summary.get("failure_count") or 0) > 0:
        warnings.append("one_or_more_checks_failed")
    if int(summary.get("warning_count") or 0) > 0:
        warnings.append("one_or_more_checks_warned")
    return {"status": "ok" if not errors else "error", "errors": errors, "warnings": warnings}


def render_markdown(scorecard: dict[str, Any]) -> str:
    summary = as_dict(scorecard.get("summary"))
    lines = [
        "# Veritas Harness Scorecard",
        "",
        f"- Generated: `{scorecard.get('generated_at_utc')}`",
        f"- Status: `{scorecard.get('status')}`",
        f"- Checks: `{summary.get('pass_count')}` pass / `{summary.get('warning_count')}` warn / `{summary.get('failure_count')}` fail / `{summary.get('expected_pending_count')}` expected-pending",
        f"- WF75 scenarios: `{summary.get('scenario_count')}`",
        f"- SMB workflow scenarios: `{summary.get('smb_scenario_count')}`",
        f"- Recommendation tracking rows: `{summary.get('recommendation_tracking_rows')}`",
        f"- Pending paper-card rows: `{summary.get('pending_paper_card_rows')}`",
        "",
        "## Checks",
        "",
    ]
    for row in as_list(scorecard.get("checks")):
        if not isinstance(row, dict):
            continue
        target = row.get("path") or " ".join(row.get("command") or [])
        lines.append(f"- `{row.get('status')}` {row.get('name')}: {target} ({row.get('notes')})")
    lines.extend(
        [
            "",
            "## Boundary",
            "",
            "Local review/proof only. No public launch, real customer data, external delivery, portfolio/canon mutation, paper/live action, or owner approval inference.",
            "",
        ]
    )
    return "\n".join(lines)


def render_summary(scorecard: dict[str, Any]) -> str:
    summary = as_dict(scorecard.get("summary"))
    validation = as_dict(scorecard.get("validation"))
    return (
        "veritas_harness_scorecard "
        f"status={scorecard.get('status')} "
        f"checks={summary.get('pass_count')}/{summary.get('checks_total')} "
        f"warn={summary.get('warning_count')} "
        f"fail={summary.get('failure_count')} "
        f"expected_pending={summary.get('expected_pending_count')} "
        f"validation={validation.get('status')} "
        f"path={rel(DEFAULT_JSON)}"
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the Veritas harness scorecard.")
    parser.add_argument("--run", action="store_true", help="Legacy alias for --full.")
    parser.add_argument("--include-slow", action="store_true", help="Legacy option; with --run, include the slow lane. Prefer --full.")
    parser.add_argument("--fast", action="store_true", help="Run chat-safe command checks: Python compile, artifact index validate, and Node syntax.")
    parser.add_argument("--go", action="store_true", help="Run Go/build/SQL helper command checks only.")
    parser.add_argument("--full", action="store_true", help="Run all command lanes: fast, OpenClaw, Go, and slow/product regression.")
    parser.add_argument("--write", action="store_true", help="Write JSON scorecard.")
    parser.add_argument("--write-md", action="store_true", help="Also write the optional human-readable Markdown digest.")
    parser.add_argument("--validate", action="store_true", help="Fail if hard failures exist.")
    parser.add_argument("--json-out", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--md-out", type=Path, default=DEFAULT_MD)
    parser.add_argument("--print-json", action="store_true", help="Print the full JSON scorecard to stdout. Default output is a compact summary.")
    parser.add_argument("--quiet", action="store_true", help="Suppress stdout unless validation fails through the process exit code.")
    return parser.parse_args()


def selected_command_lanes(args: argparse.Namespace) -> set[str]:
    lanes: set[str] = set()
    if args.full:
        return {"fast", "openclaw", "go", "slow"}
    if args.fast:
        lanes.add("fast")
    if args.go:
        lanes.add("go")
    if args.run:
        lanes.update({"fast", "openclaw", "go"})
        if args.include_slow:
            lanes.add("slow")
    elif args.include_slow:
        lanes.add("slow")
    return lanes


def main() -> int:
    args = parse_args()
    scorecard = build_scorecard(command_lanes=selected_command_lanes(args))
    if args.write:
        json_out = args.json_out if args.json_out.is_absolute() else ROOT / args.json_out
        atomic_write_json(json_out, scorecard)
    if args.write_md:
        md_out = args.md_out if args.md_out.is_absolute() else ROOT / args.md_out
        atomic_write_text(md_out, render_markdown(scorecard))
    if args.print_json:
        print(json.dumps(scorecard, indent=2, sort_keys=True))
    elif not args.quiet:
        print(render_summary(scorecard))
    if args.validate and int(as_dict(scorecard.get("summary")).get("failure_count") or 0) > 0:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
