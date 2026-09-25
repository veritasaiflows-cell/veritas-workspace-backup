#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import os
import sys
import tempfile
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "wf88_daily_actionability_refresh.py"


def load_module():
    spec = importlib.util.spec_from_file_location("wf88_daily_actionability_refresh", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def write_dep_artifact(path: Path, payload: dict) -> str:
    path.write_text(json.dumps(payload), encoding="utf-8")
    return str(path)


def test_runner_completes_successful_sequence() -> None:
    module = load_module()
    commands = [
        {"id": "one", "command": [sys.executable, "-c", "print('one')"]},
        {"id": "two", "command": [sys.executable, "-c", "print('two')"]},
    ]
    results, ok = module.run_sequence(commands, execute=True, timeout_seconds=30)
    assert ok is True
    assert len(results) == 2
    assert results[0]["returncode"] == 0
    assert "one" in results[0]["stdout_tail"]


def test_runner_stops_on_first_failure() -> None:
    module = load_module()
    commands = [
        {"id": "ok", "command": [sys.executable, "-c", "print('ok')"]},
        {"id": "fail", "command": [sys.executable, "-c", "raise SystemExit(3)"]},
        {"id": "skip", "command": [sys.executable, "-c", "print('skip')"]},
    ]
    results, ok = module.run_sequence(commands, execute=True, timeout_seconds=30)
    assert ok is False
    assert len(results) == 2
    assert results[-1]["id"] == "fail"
    assert results[-1]["returncode"] == 3


def test_dry_run_does_not_execute_commands() -> None:
    module = load_module()
    commands = [{"id": "dry", "command": [sys.executable, "-c", "raise SystemExit(9)"]}]
    results, ok = module.run_sequence(commands, execute=False, timeout_seconds=30)
    assert ok is True
    assert results[0]["executed"] is False
    assert results[0]["returncode"] is None


def test_fresh_wf74_artifact_reuse_skips_command() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as td:
        artifact = Path(td) / "fresh.json"
        artifact.write_text(json.dumps({
            "status": "ok",
            "generated_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
            "validation": {"status": "ok"},
        }), encoding="utf-8")
        commands = [{
            "id": "reuse",
            "command": [sys.executable, "-c", "raise SystemExit(9)"],
            "reuse_fresh_artifacts": [str(artifact)],
        }]
        results, ok = module.run_sequence(commands, execute=True, timeout_seconds=30, reuse_fresh_wf74=True)
        assert ok is True
        assert results[0]["executed"] is False
        assert results[0]["skipped"] is True
        assert results[0]["returncode"] == 0
        assert results[0]["skip_reason"] == "fresh_validated_wf74_artifact_reused"


def test_stale_wf74_artifact_does_not_skip_command() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as td:
        artifact = Path(td) / "stale.json"
        stale_at = datetime.now(timezone.utc) - timedelta(hours=5)
        artifact.write_text(json.dumps({
            "status": "ok",
            "generated_at_utc": stale_at.replace(microsecond=0).isoformat().replace("+00:00", "Z"),
            "validation": {"status": "ok"},
        }), encoding="utf-8")
        commands = [{
            "id": "stale",
            "command": [sys.executable, "-c", "raise SystemExit(7)"],
            "reuse_fresh_artifacts": [str(artifact)],
        }]
        results, ok = module.run_sequence(
            commands,
            execute=True,
            timeout_seconds=30,
            reuse_fresh_wf74=True,
            fresh_max_age_minutes=60,
        )
        assert ok is False
        assert results[0]["executed"] is True
        assert results[0]["skipped"] is False
        assert results[0]["returncode"] == 7


def test_no_reuse_mode_runs_even_with_fresh_artifact() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as td:
        artifact = Path(td) / "fresh.json"
        artifact.write_text(json.dumps({
            "status": "ok",
            "generated_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
            "validation": {"status": "ok"},
        }), encoding="utf-8")
        commands = [{
            "id": "no-reuse",
            "command": [sys.executable, "-c", "raise SystemExit(6)"],
            "reuse_fresh_artifacts": [str(artifact)],
        }]
        results, ok = module.run_sequence(commands, execute=True, timeout_seconds=30, reuse_fresh_wf74=False)
        assert ok is False
        assert results[0]["executed"] is True
        assert results[0]["skipped"] is False
        assert results[0]["returncode"] == 6


def test_wiki_bootstrap_validator_runs_after_wiki_synthesis() -> None:
    module = load_module()
    ids = [row["id"] for row in module.COMMANDS]
    assert "wf88_wiki_synthesis" in ids
    assert "wiki_bootstrap_validator" in ids
    synthesis_index = ids.index("wf88_wiki_synthesis")
    bootstrap_index = ids.index("wiki_bootstrap_validator")
    assert bootstrap_index == synthesis_index + 1
    synthesis_command = module.COMMANDS[synthesis_index]["command"]
    bootstrap_command = module.COMMANDS[bootstrap_index]["command"]
    assert "--write-wiki" in synthesis_command
    assert "scripts\\wiki_bootstrap_validator.py" in bootstrap_command
    assert "--write" in bootstrap_command
    assert "--validate" in bootstrap_command


def test_command_plan_has_no_retired_finance_route() -> None:
    module = load_module()
    serialized = json.dumps(module.COMMANDS).lower()
    for marker in ("wf67", "wf87", "paper-autotrader", "trade-grade", "deployment-readiness", "capital-deployment"):
        assert marker not in serialized


def test_producer_refresh_runs_before_wiki_consumers() -> None:
    module = load_module()
    ids = [row["id"] for row in module.COMMANDS]
    for producer in ("retrieval_quality_scorecard", "wf88_decision_compiler", "rsi_outcome_scorecard"):
        assert producer in ids
    queue_index = ids.index("actionable_improvement_queue")
    retrieval_index = ids.index("retrieval_quality_scorecard")
    compiler_index = ids.index("wf88_decision_compiler")
    rsi_index = ids.index("rsi_outcome_scorecard")
    orphan_index = ids.index("no_orphan_validator")
    wiki_index = ids.index("wf88_wiki_synthesis")
    # Producers run after their last upstream (actionable queue feeds the
    # decision compiler) and before every wiki/OS2 consumer, with the orphan
    # validator covering the newly produced artifacts.
    assert queue_index < retrieval_index < compiler_index < rsi_index < orphan_index < wiki_index


def test_producer_commands_use_supported_local_cli() -> None:
    module = load_module()
    by_id = {row["id"]: row for row in module.COMMANDS}
    allowed_flags = {"--write", "--write-md", "--validate"}
    for producer in ("retrieval_quality_scorecard", "wf88_decision_compiler", "rsi_outcome_scorecard"):
        spec = by_id[producer]
        assert "reuse_fresh_artifacts" not in spec
        assert "requires_fresh_artifacts" not in spec
        flags = [part for part in spec["command"][2:] if part.startswith("--")]
        assert flags
        assert set(flags) <= allowed_flags, f"{producer}: {flags}"


def test_wiki_consumer_declares_producer_dependencies() -> None:
    module = load_module()
    by_id = {row["id"]: row for row in module.COMMANDS}
    deps = " ".join(by_id["wf88_wiki_synthesis"].get("requires_fresh_artifacts") or []).replace("\\", "/")
    assert "retrieval-quality-scorecard.json" in deps
    assert "wf88-decision-compiler.json" in deps
    assert "rsi-outcome-scorecard.json" in deps


def test_reuse_invalidated_when_producer_script_changed() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as td:
        producer = Path(td) / "producer.py"
        producer.write_text("raise SystemExit(7)", encoding="utf-8")
        artifact = Path(td) / "artifact.json"
        # Artifact timestamp is 10 minutes old (inside the 120-minute reuse
        # window) but the producer script was just written: reuse must not
        # green pre-fix output.
        older = datetime.now(timezone.utc) - timedelta(minutes=10)
        artifact.write_text(json.dumps({
            "status": "ok",
            "generated_at_utc": older.replace(microsecond=0).isoformat().replace("+00:00", "Z"),
            "validation": {"status": "ok"},
        }), encoding="utf-8")
        commands = [{
            "id": "changed-producer",
            "command": [sys.executable, str(producer)],
            "reuse_fresh_artifacts": [str(artifact)],
        }]
        results, ok = module.run_sequence(commands, execute=True, timeout_seconds=30, reuse_fresh_wf74=True)
        assert ok is False
        assert results[0]["executed"] is True
        assert results[0]["skipped"] is False
        assert results[0]["returncode"] == 7


def test_stale_dependency_blocks_consumer_with_typed_proof() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as td:
        missing = str(Path(td) / "missing-producer.json")
        commands = [
            {"id": "producer", "command": [sys.executable, "-c", "print('p')"]},
            {
                "id": "consumer",
                "command": [sys.executable, "-c", "print('c')"],
                "requires_fresh_artifacts": [missing],
            },
        ]
        results, ok = module.run_sequence(commands, execute=True, timeout_seconds=30)
        assert ok is False
        assert len(results) == 2
        assert results[0]["returncode"] == 0
        blocked = results[1]
        assert blocked["id"] == "consumer"
        assert blocked["blocked"] is True
        assert blocked["executed"] is False
        assert blocked["returncode"] is None
        assert "stale_or_missing_producer_evidence" in (blocked["block_reason"] or "")
        assert any(
            entry.get("path") == missing and not entry.get("fresh")
            for entry in blocked["dependencies"]
        )


def test_timeout_recorded_as_typed_failed_proof() -> None:
    module = load_module()
    commands = [{
        "id": "slow",
        "command": [sys.executable, "-c", "import time; time.sleep(30)"],
    }]
    results, ok = module.run_sequence(commands, execute=True, timeout_seconds=1)
    assert ok is False
    assert len(results) == 1
    assert results[0]["timeout"] is True
    assert results[0]["returncode"] == "timeout"
    assert "command_timeout_after_" in results[0]["stderr_tail"]


def test_warning_output_does_not_fail_consumer_chain() -> None:
    module = load_module()
    commands = [
        {"id": "warn", "command": [sys.executable, "-c", "print('live_rsi_outcome_maturity_not_met')"]},
        {"id": "next", "command": [sys.executable, "-c", "print('next')"]},
    ]
    results, ok = module.run_sequence(commands, execute=True, timeout_seconds=30)
    assert ok is True
    assert [row["id"] for row in results] == ["warn", "next"]
    assert all(row.get("blocked") is False for row in results)


def test_dependency_rejects_missing_blank_or_failure_status() -> None:
    module = load_module()
    bad_statuses = [None, "", "   ", 0, "critical", "failed", "fail_open", "fail_closed", "error", "blocked"]
    with tempfile.TemporaryDirectory() as td:
        for index, bad in enumerate(bad_statuses):
            artifact = Path(td) / f"dep-status-{index}.json"
            write_dep_artifact(artifact, {
                "status": bad,
                "validation": {"status": "ok"},
                "generated_at_utc": now_utc(),
            })
            result = module.dependency_status(str(artifact), max_age_minutes=1440)
            assert result["fresh"] is False, f"status={bad!r} greened the dependency guard"
            assert result["reason"] in {"dependency_status_missing_or_blank", "dependency_status_blocked"}, result


def test_dependency_rejects_non_allowlisted_validation() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as td:
        for index, bad in enumerate(["critical", "unknown", "failed", "blocked", ""]):
            artifact = Path(td) / f"dep-validation-{index}.json"
            write_dep_artifact(artifact, {
                "status": "ok",
                "validation": {"status": bad},
                "generated_at_utc": now_utc(),
            })
            result = module.dependency_status(str(artifact), max_age_minutes=1440)
            assert result["fresh"] is False, f"validation={bad!r} greened the dependency guard"
            assert result["reason"] == "dependency_validation_not_ok", result
        artifact = Path(td) / "dep-validation-absent.json"
        write_dep_artifact(artifact, {"status": "ok", "generated_at_utc": now_utc()})
        result = module.dependency_status(str(artifact), max_age_minutes=1440)
        assert result["fresh"] is False
        assert result["reason"] == "dependency_validation_not_ok", result


def test_dependency_rejects_banana_unknown_hyphenated_and_malformed() -> None:
    module = load_module()
    # Bytes are not JSON-representable, so b"ok" cannot travel through a
    # dependency artifact; its type rejection is probed directly here.
    assert module.valid_evidence_status(b"ok") is False
    strict_bad = ["banana", "unknown", "fail-open", "fail-closed", "Fail_Open", "FAIL-CLOSED",
                  "WARNING", "Ok", "decision-objects-warning-review-only",
                  "", "   ", None, 0, 1, True, False, [], {}, 3.14]
    with tempfile.TemporaryDirectory() as td:
        for index, bad_value in enumerate(strict_bad):
            artifact = Path(td) / ("dep-regression-%d.json" % index)
            write_dep_artifact(artifact, {
                "status": bad_value,
                "validation": {"status": "ok"},
                "generated_at_utc": now_utc(),
            })
            result = module.dependency_status(str(artifact), max_age_minutes=1440)
            assert result["fresh"] is False, "status=%r greened the guard" % (bad_value,)


def test_dependency_accepts_padded_legitimate_statuses() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as td:
        for index, padded in enumerate(["ok ", " ok", "  warning  "]):
            artifact = Path(td) / ("dep-padded-%d.json" % index)
            write_dep_artifact(artifact, {
                "status": padded,
                "validation": {"status": "ok"},
                "generated_at_utc": now_utc(),
            })
            result = module.dependency_status(str(artifact), max_age_minutes=1440)
            assert result["fresh"] is True, "status=%r should pass via stripped match" % (padded,)


def test_dependency_accepts_known_review_only_statuses() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as td:
        cases = [
            ("ok", "ok"),
            ("warning", "warning"),
            ("decision_objects_warning_review_only", "warning"),
        ]
        for status, validation in cases:
            artifact = Path(td) / f"dep-good-{abs(hash(status))}.json"
            write_dep_artifact(artifact, {
                "status": status,
                "validation": {"status": validation},
                "generated_at_utc": now_utc(),
            })
            result = module.dependency_status(str(artifact), max_age_minutes=1440)
            assert result["fresh"] is True, result
            assert result["reason"] is None, result


def test_finance_producers_run_before_followup_triage() -> None:
    module = load_module()
    ids = [row["id"] for row in module.COMMANDS]
    queue_index = ids.index("wf74_improvement_queue")
    repair_index = ids.index("finance_response_quality_repair_loop")
    triage_index = ids.index("wf88_followup_triage")
    # Repair-loop consumes the improvement queue; WF85 reconciliation was
    # retired, so the repair loop now sits directly ahead of triage.
    assert "wf85_source_open_reconciliation_contract" not in ids
    assert queue_index < repair_index < triage_index


def test_finance_producer_commands_use_supported_flags_and_always_execute() -> None:
    module = load_module()
    by_id = {row["id"]: row for row in module.COMMANDS}
    repair = by_id["finance_response_quality_repair_loop"]
    assert repair["command"][1] == "scripts\\finance_response_quality_repair_loop.py"
    assert repair["command"][2:] == ["--write", "--write-md", "--validate"]
    for spec in (repair,):
        assert "reuse_fresh_artifacts" not in spec
        assert "requires_fresh_artifacts" not in spec
    serialized = json.dumps([repair]).lower()
    for marker in ("wf67", "wf87", "paper-autotrader", "trade-grade", "capital-deployment"):
        assert marker not in serialized


def test_finance_producer_failure_stops_before_triage() -> None:
    module = load_module()
    order = [
        "wf74_improvement_queue",
        "finance_response_quality_repair_loop",
        "wf88_followup_triage",
    ]
    commands = []
    for ident in order:
        if ident == "finance_response_quality_repair_loop":
            commands.append({"id": ident, "command": [sys.executable, "-c", "raise SystemExit(4)"]})
        else:
            commands.append({"id": ident, "command": [sys.executable, "-c", f"print('{ident}')"]})
    results, ok = module.run_sequence(commands, execute=True, timeout_seconds=30)
    assert ok is False
    assert [row["id"] for row in results] == order[:2]
    assert results[1]["returncode"] == 4


def test_os2_control_producers_run_before_os2_in_dependency_order() -> None:
    module = load_module()
    ids = [row["id"] for row in module.COMMANDS]
    ordered = [
        "pm_implementation_jobs",
        "wf88_retired_surface_cleanup_plan",
        "wf88_route_contraction_packet",
        "wf88_delete_readiness_packet",
        "wf74_wf88_loop_trace",
        "long_work_job_status",
        "skill_workshop_body_guard",
        "wf88_os2_before_wiki",
    ]
    positions = [ids.index(ident) for ident in ordered]
    assert positions == sorted(positions), positions


def test_os2_required_inputs_have_producer_coverage_within_sla() -> None:
    module = load_module()
    by_id = {row["id"]: row for row in module.COMMANDS}
    ids = [row["id"] for row in module.COMMANDS]
    os2_index = ids.index("wf88_os2_before_wiki")
    # (artifact, producer id, sla minutes). Route-contraction is OS2
    # required=False but still covered by its producer + stop-on-fail.
    coverage = {
        "tmp/wf88-retired-surface-cleanup-plan.json": ("wf88_retired_surface_cleanup_plan", 24 * 60),
        "tmp/wf88-route-contraction-packet.json": ("wf88_route_contraction_packet", 24 * 60),
        "tmp/wf88-delete-readiness-packet.json": ("wf88_delete_readiness_packet", 24 * 60),
        "tmp/recommendation-outcome-ledger-current.json": ("recommendation_outcome_grading", 168 * 60),
        "tmp/wf74-wf88-loop-trace.json": ("wf74_wf88_loop_trace", 24 * 60),
        "tmp/long-work-job-status-packet.json": ("long_work_job_status", 24 * 60),
        "tmp/skill-workshop-body-guard.json": ("skill_workshop_body_guard", 24 * 60),
    }
    allowed_flags = {"--write", "--write-md", "--validate"}
    for artifact, (producer, sla_minutes) in coverage.items():
        assert sla_minutes <= 168 * 60, artifact
        assert producer in by_id, artifact
        spec = by_id[producer]
        assert ids.index(producer) < os2_index, artifact
        flags = [part for part in spec["command"][2:] if part.startswith("--")]
        assert flags and set(flags) <= allowed_flags, (artifact, flags)
        assert "reuse_fresh_artifacts" not in spec, artifact
        assert "requires_fresh_artifacts" not in spec, artifact
        assert spec["command"][1].endswith(".py"), artifact


def test_os2_producer_failure_stops_before_os2() -> None:
    module = load_module()
    order = [
        "wf88_retired_surface_cleanup_plan",
        "wf88_route_contraction_packet",
        "wf88_delete_readiness_packet",
        "wf74_wf88_loop_trace",
        "wf88_os2_before_wiki",
    ]
    commands = []
    for ident in order:
        if ident == "wf88_route_contraction_packet":
            commands.append({"id": ident, "command": [sys.executable, "-c", "raise SystemExit(5)"]})
        else:
            commands.append({"id": ident, "command": [sys.executable, "-c", f"print('{ident}')"]})
    results, ok = module.run_sequence(commands, execute=True, timeout_seconds=30)
    assert ok is False
    assert [row["id"] for row in results] == order[:2]
    assert results[1]["returncode"] == 5
    assert all(row.get("blocked") is False for row in results)


def test_obsolete_wf85_producer_removed_chain_order_preserved() -> None:
    module = load_module()
    ids = [row["id"] for row in module.COMMANDS]
    assert "wf85_source_open_reconciliation_contract" not in ids
    assert len(ids) == 45
    assert ids == [
        "recommendation_outcome_grading",
        "wf55_outcome_ledger_current",
        "finance_decision_performance",
        "cron_contract_validator",
        "cron_freshness_spine",
        "cron_control_packet",
        "coding_outcome_ledger",
        "token_usage_ledger",
        "implementation_token_attribution_bridge",
        "wf74_improvement_queue",
        "finance_response_quality_repair_loop",
        "wf74_reflection_proposals",
        "wf74_auto_patch_proposer",
        "pm_control_packet",
        "wf74_autonomy_router",
        "wf88_followup_triage",
        "improvement_ledger",
        "wf74_decision_docket",
        "owner_gated_queue",
        "pm_implementation_jobs",
        "workflow_routing_index",
        "wf88_retired_surface_cleanup_plan",
        "wf88_route_contraction_packet",
        "wf88_delete_readiness_packet",
        "wf74_wf88_loop_trace",
        "long_work_job_status",
        "skill_workshop_body_guard",
        "otel_ops_control",
        "wf88_os2_before_wiki",
        "actionable_improvement_queue",
        "retrieval_live_eval",
        "retrieval_quality_scorecard",
        "wf88_decision_compiler",
        "rsi_outcome_scorecard",
        "no_orphan_validator",
        "wf88_wiki_synthesis",
        "wiki_bootstrap_validator",
        "wf88_os2_after_wiki",
        "wf88_wiki_cron_gate",
        "workflow_routing_index_final",
        "wf74_workflow_router_capsules",
        "wf88_workflow_router_capsules",
        "future_session_packet",
        "startup_brief",
        "status_card",
    ]


def test_routing_index_producer_runs_before_cleanup_contraction() -> None:
    module = load_module()
    ids = [row["id"] for row in module.COMMANDS]
    assert len(ids) == 45
    assert "wf85_source_open_reconciliation_contract" not in ids
    index_pos = ids.index("workflow_routing_index")
    assert index_pos < ids.index("wf88_retired_surface_cleanup_plan") < ids.index("wf88_route_contraction_packet")
    spec = {row["id"]: row for row in module.COMMANDS}["workflow_routing_index"]
    assert spec["command"][1] == "scripts\\workflow_routing_index.py"
    assert spec["command"][2:] == ["--write", "--write-db", "--validate"]
    assert "reuse_fresh_artifacts" not in spec
    assert "requires_fresh_artifacts" not in spec


def test_pm_control_packet_producer_runs_before_autonomy_router() -> None:
    module = load_module()
    ids = [row["id"] for row in module.COMMANDS]
    assert "pm_control_packet" in ids
    assert "wf74_autonomy_router" in ids
    packet_index = ids.index("pm_control_packet")
    router_index = ids.index("wf74_autonomy_router")
    # Producer-before-consumer: the router fails closed on a stale/blocked
    # pm-control-packet, so the chain must regenerate it in-step immediately
    # ahead of the router (same minimal --write --validate pattern as the
    # cron_control_packet step; DB writes stay with workflow_routing_index).
    assert packet_index == router_index - 1
    assert ids.index("wf74_auto_patch_proposer") < packet_index
    assert packet_index < ids.index("wf88_followup_triage")
    by_id = {row["id"]: row for row in module.COMMANDS}
    spec = by_id["pm_control_packet"]
    assert spec["command"][1] == "scripts\\pm_control_packet.py"
    assert spec["command"][2:] == ["--write", "--validate"]
    assert "reuse_fresh_artifacts" not in spec
    assert "reuse_max_age_minutes" not in spec
    assert "requires_fresh_artifacts" not in spec


def test_final_producer_coverage_order_flags_and_windows() -> None:
    module = load_module()
    ids = [row["id"] for row in module.COMMANDS]
    assert len(ids) == 45
    assert ids.index("recommendation_outcome_grading") < ids.index("wf55_outcome_ledger_current") < ids.index("wf74_improvement_queue")
    queue_index = ids.index("wf74_improvement_queue")
    trio = ["cron_contract_validator", "cron_freshness_spine", "cron_control_packet"]
    assert [ids.index(ident) for ident in trio] == [queue_index - 6, queue_index - 5, queue_index - 4]
    assert ids.index("cron_control_packet") < ids.index("coding_outcome_ledger") < ids.index("token_usage_ledger") < ids.index("implementation_token_attribution_bridge") < queue_index
    assert ids.index("retrieval_live_eval") < ids.index("retrieval_quality_scorecard") < ids.index("wf88_wiki_synthesis")
    assert ids.index("otel_ops_control") < ids.index("wf88_os2_before_wiki")
    by_id = {row["id"]: row for row in module.COMMANDS}
    assert by_id["wf55_outcome_ledger_current"]["command"][1:] == ["scripts\\wf55_outcome_ledger_v2.py", "preview"]
    assert by_id["cron_contract_validator"]["command"][2:] == ["--write", "--validate"]
    assert by_id["cron_freshness_spine"]["command"][2:] == ["--write", "--validate"]
    assert by_id["cron_control_packet"]["command"][2:] == ["--write", "--validate"]
    assert by_id["retrieval_live_eval"]["command"][2:] == ["--write", "--write-md", "--validate"]
    assert by_id["otel_ops_control"]["command"][2:] == ["--write", "--write-db", "--multi-window", "--validate"]
    live = by_id["retrieval_live_eval"]
    assert "reuse_fresh_artifacts" not in live
    assert "reuse_max_age_minutes" not in live
    for ident in ("wf55_outcome_ledger_current", "cron_contract_validator", "cron_freshness_spine", "cron_control_packet", "otel_ops_control"):
        spec = by_id[ident]
        assert "reuse_fresh_artifacts" not in spec, ident
        assert "reuse_max_age_minutes" not in spec, ident


def test_per_spec_reuse_window_with_source_mtime_invalidation() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as td:
        producer = Path(td) / "live_eval.py"
        producer.write_text("raise SystemExit(7)", encoding="utf-8")
        artifact = Path(td) / "live-eval.json"
        older = datetime.now(timezone.utc) - timedelta(hours=10)
        artifact.write_text(json.dumps({
            "status": "ok",
            "generated_at_utc": older.replace(microsecond=0).isoformat().replace("+00:00", "Z"),
            "validation": {"status": "ok"},
        }), encoding="utf-8")
        aged = time.time() - 11 * 3600
        os.utime(producer, (aged, aged))
        spec_windowed = {
            "id": "windowed",
            "command": [sys.executable, str(producer)],
            "reuse_fresh_artifacts": [str(artifact)],
            "reuse_max_age_minutes": 4320,
        }
        results, ok = module.run_sequence([spec_windowed], execute=True, timeout_seconds=30, reuse_fresh_wf74=True)
        assert ok is True
        assert results[0]["skipped"] is True
        assert results[0]["reuse_window_minutes"] == 4320
        spec_default = {
            "id": "default-window",
            "command": [sys.executable, "-c", "raise SystemExit(9)"],
            "reuse_fresh_artifacts": [str(artifact)],
        }
        results, ok = module.run_sequence([spec_default], execute=True, timeout_seconds=30, reuse_fresh_wf74=True, fresh_max_age_minutes=120)
        assert ok is False
        assert results[0]["executed"] is True
        assert results[0].get("reuse_window_minutes") == 120
        future = time.time() + 60
        os.utime(producer, (future, future))
        results, ok = module.run_sequence([spec_windowed], execute=True, timeout_seconds=30, reuse_fresh_wf74=True)
        assert ok is False
        assert results[0]["executed"] is True
        assert results[0]["returncode"] == 7


def test_os2_and_wiki_stale_source_producers_all_covered() -> None:
    module = load_module()
    ids = [row["id"] for row in module.COMMANDS]
    os2_index = ids.index("wf88_os2_before_wiki")
    wiki_index = ids.index("wf88_wiki_synthesis")
    for ident in ("wf55_outcome_ledger_current", "cron_control_packet", "otel_ops_control", "wf74_wf88_loop_trace", "wf88_retired_surface_cleanup_plan", "long_work_job_status", "skill_workshop_body_guard"):
        assert ids.index(ident) < os2_index, ident
    assert ids.index("retrieval_live_eval") < ids.index("retrieval_quality_scorecard") < wiki_index


def test_no_commands_declare_reuse_always_execute_by_default() -> None:
    module = load_module()
    ids = [row["id"] for row in module.COMMANDS]
    assert len(ids) == 45
    for spec in module.COMMANDS:
        assert "reuse_fresh_artifacts" not in spec, spec.get("id")
        assert "reuse_max_age_minutes" not in spec, spec.get("id")


def test_default_run_executes_every_command_without_skips() -> None:
    module = load_module()
    commands = [
        {"id": f"step-{index:02d}", "command": [sys.executable, "-c", f"print('step-{index:02d}')"]}
        for index in range(1, 45)
    ]
    results, ok = module.run_sequence(commands, execute=True, timeout_seconds=30)
    assert ok is True
    assert len(results) == 44
    assert all(row["executed"] is True for row in results)
    assert all(row["skipped"] is False for row in results)
    assert all(row["returncode"] == 0 for row in results)


def test_loop_repair_token_attribution_producers_before_wf74_queue() -> None:
    module = load_module()
    ids = [row["id"] for row in module.COMMANDS]
    assert len(ids) == 45
    by_id = {row["id"]: row for row in module.COMMANDS}
    assert ids.index("cron_control_packet") < ids.index("coding_outcome_ledger") < ids.index("token_usage_ledger") < ids.index("implementation_token_attribution_bridge") < ids.index("wf74_improvement_queue") < ids.index("wf88_followup_triage")
    assert by_id["coding_outcome_ledger"]["command"][1:] == ["scripts\\coding_outcome_ledger.py", "--write", "--validate"]
    assert by_id["token_usage_ledger"]["command"][1:] == ["scripts\\token_usage_ledger.py", "--write", "--write-md", "--validate"]
    assert by_id["implementation_token_attribution_bridge"]["command"][1:] == ["scripts\\implementation_token_attribution_bridge.py", "--write", "--write-md", "--validate"]
    for ident in ("coding_outcome_ledger", "token_usage_ledger", "implementation_token_attribution_bridge"):
        spec = by_id[ident]
        assert "reuse_fresh_artifacts" not in spec, ident
        assert "reuse_max_age_minutes" not in spec, ident
        assert "requires_fresh_artifacts" not in spec, ident


def test_loop_repair_final_routing_index_and_capsules_after_gate() -> None:
    module = load_module()
    ids = [row["id"] for row in module.COMMANDS]
    assert len(ids) == 45
    by_id = {row["id"]: row for row in module.COMMANDS}
    assert ids.index("wf88_os2_after_wiki") < ids.index("wf88_wiki_cron_gate") < ids.index("workflow_routing_index_final") < ids.index("wf74_workflow_router_capsules") < ids.index("wf88_workflow_router_capsules") < ids.index("future_session_packet") < ids.index("startup_brief") < ids.index("status_card")
    assert by_id["workflow_routing_index_final"]["command"][1:] == ["scripts\\workflow_routing_index.py", "--write", "--write-db", "--validate"]
    assert by_id["wf74_workflow_router_capsules"]["command"][1:] == ["scripts\\workflow_router.py", "WF74", "--answer", "all", "--write-capsules", "--validate"]
    assert by_id["wf88_workflow_router_capsules"]["command"][1:] == ["scripts\\workflow_router.py", "WF88", "--answer", "all", "--write-capsules", "--validate"]
    for ident in ("workflow_routing_index_final", "wf74_workflow_router_capsules", "wf88_workflow_router_capsules"):
        spec = by_id[ident]
        assert "reuse_fresh_artifacts" not in spec, ident
        assert "reuse_max_age_minutes" not in spec, ident
        assert "requires_fresh_artifacts" not in spec, ident


def test_loop_repair_all_45_always_execute_no_reuse() -> None:
    module = load_module()
    ids = [row["id"] for row in module.COMMANDS]
    assert len(ids) == 45
    for spec in module.COMMANDS:
        assert "reuse_fresh_artifacts" not in spec, spec.get("id")
        assert "reuse_max_age_minutes" not in spec, spec.get("id")



def test_closure_chain_ledger_appends_not_checks() -> None:
    module = load_module()
    by_id = {row["id"]: row for row in module.COMMANDS}
    spec = by_id["improvement_ledger"]
    flags = [part for part in spec["command"][2:] if part.startswith("--")]
    assert "--write" in flags
    assert "--check" not in flags, "ledger must append (--write without --check); --check never appends"
    assert flags == ["--write", "--write-md", "--validate"], flags
    assert "reuse_fresh_artifacts" not in spec
    assert "reuse_max_age_minutes" not in spec
    assert "requires_fresh_artifacts" not in spec


def test_closure_chain_order_triage_ledger_downstream_capsules() -> None:
    module = load_module()
    ids = [row["id"] for row in module.COMMANDS]
    assert len(ids) == 45
    tri = ids.index("wf88_followup_triage")
    led = ids.index("improvement_ledger")
    aiq = ids.index("actionable_improvement_queue")
    rif = ids.index("workflow_routing_index_final")
    c74 = ids.index("wf74_workflow_router_capsules")
    c88 = ids.index("wf88_workflow_router_capsules")
    assert tri < led < aiq < rif < c74 < c88
    assert ids.index("wf74_improvement_queue") < tri


def test_closure_chain_fail_closed_triage_before_ledger() -> None:
    module = load_module()
    commands = [
        {"id": "wf88_followup_triage", "command": [sys.executable, "-c", "raise SystemExit(4)"]},
        {"id": "improvement_ledger", "command": [sys.executable, "-c", "print('must_not_run')"]},
        {"id": "actionable_improvement_queue", "command": [sys.executable, "-c", "print('must_not_run')"]},
    ]
    results, ok = module.run_sequence(commands, execute=True, timeout_seconds=30)
    assert ok is False
    assert [row["id"] for row in results] == ["wf88_followup_triage"]
    assert results[0]["returncode"] == 4


def test_closure_chain_stable_plan_idempotent_single_ledger() -> None:
    module = load_module()
    ids = [row["id"] for row in module.COMMANDS]
    assert ids.count("improvement_ledger") == 1
    first = module.build_packet(execute=False, timeout_seconds=30)
    second = module.build_packet(execute=False, timeout_seconds=30)
    assert first["command_count"] == second["command_count"] == 45
    assert [r["id"] for r in first["results"]] == [r["id"] for r in second["results"]] == ids
    assert all(r.get("executed") is False and r.get("returncode") is None for r in first["results"])
    assert first["results"][ids.index("improvement_ledger")]["command"][2:] == ["--write", "--write-md", "--validate"]


def test_closure_chain_dry_run_no_execution_no_reuse() -> None:
    module = load_module()
    args = module.parse_args(["--dry-run"])
    assert args.dry_run is True
    packet = module.build_packet(execute=not args.dry_run, timeout_seconds=30)
    assert packet["execute"] is False
    assert all(row.get("executed") is False for row in packet["results"])
    assert all(row.get("skipped") is False for row in packet["results"])
    for spec in module.COMMANDS:
        assert "reuse_fresh_artifacts" not in spec, spec.get("id")


def test_transient_failure_is_retried_once_and_chain_continues() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as td:
        marker = Path(td) / "marker.txt"
        flaky = Path(td) / "flaky.py"
        flaky.write_text(
            "import sys\n"
            "from pathlib import Path\n"
            f"marker = Path(r'{marker}')\n"
            "if marker.exists():\n"
            "    sys.exit(0)\n"
            "marker.write_text('failed once', encoding='utf-8')\n"
            "sys.exit(3)\n",
            encoding="utf-8",
        )
        commands = [
            {"id": "flaky", "command": [sys.executable, str(flaky)]},
            {"id": "next", "command": [sys.executable, "-c", "print('next')"]},
        ]
        results, ok = module.run_sequence(
            commands,
            execute=True,
            timeout_seconds=30,
            retry_limit=1,
            retry_wait_seconds=0,
        )
        assert ok is True
        assert [row["id"] for row in results] == ["flaky", "next"]
        row = results[0]
        assert row["returncode"] == 0
        assert row["retry_attempted"] is True
        assert row["retry_attempts"] == 1
        assert row["first_attempt_returncode"] == 3


def test_persistent_failure_stops_chain_after_retry() -> None:
    module = load_module()
    commands = [
        {"id": "bad", "command": [sys.executable, "-c", "raise SystemExit(5)"]},
        {"id": "never", "command": [sys.executable, "-c", "print('must_not_run')"]},
    ]
    results, ok = module.run_sequence(
        commands,
        execute=True,
        timeout_seconds=30,
        retry_limit=1,
        retry_wait_seconds=0,
    )
    assert ok is False
    assert len(results) == 1
    row = results[0]
    assert row["returncode"] == 5
    assert row["retry_attempted"] is True
    assert row["retry_attempts"] == 1
    assert row["first_attempt_returncode"] == 5


def test_timeout_failure_is_not_retried() -> None:
    module = load_module()
    commands = [{"id": "slow", "command": [sys.executable, "-c", "import time; time.sleep(30)"]}]
    results, ok = module.run_sequence(
        commands,
        execute=True,
        timeout_seconds=1,
        retry_limit=1,
        retry_wait_seconds=0,
    )
    assert ok is False
    assert len(results) == 1
    assert results[0]["timeout"] is True
    assert results[0]["returncode"] == "timeout"
    assert "retry_attempted" not in results[0]


def test_default_run_sequence_keeps_fail_fast_no_retry() -> None:
    module = load_module()
    commands = [
        {"id": "fail", "command": [sys.executable, "-c", "raise SystemExit(7)"]},
        {"id": "never", "command": [sys.executable, "-c", "print('must_not_run')"]},
    ]
    results, ok = module.run_sequence(commands, execute=True, timeout_seconds=30)
    assert ok is False
    assert len(results) == 1
    assert results[0]["returncode"] == 7
    assert "retry_attempted" not in results[0]


def test_build_packet_reports_retry_telemetry_fields() -> None:
    module = load_module()
    packet = module.build_packet(execute=False, timeout_seconds=30)
    assert packet["retried_count"] == 0
    assert packet["recovered_after_retry_count"] == 0


def main() -> int:
    test_runner_completes_successful_sequence()
    test_runner_stops_on_first_failure()
    test_dry_run_does_not_execute_commands()
    test_fresh_wf74_artifact_reuse_skips_command()
    test_stale_wf74_artifact_does_not_skip_command()
    test_no_reuse_mode_runs_even_with_fresh_artifact()
    test_wiki_bootstrap_validator_runs_after_wiki_synthesis()
    test_command_plan_has_no_retired_finance_route()
    test_producer_refresh_runs_before_wiki_consumers()
    test_producer_commands_use_supported_local_cli()
    test_wiki_consumer_declares_producer_dependencies()
    test_reuse_invalidated_when_producer_script_changed()
    test_stale_dependency_blocks_consumer_with_typed_proof()
    test_timeout_recorded_as_typed_failed_proof()
    test_warning_output_does_not_fail_consumer_chain()
    test_dependency_rejects_missing_blank_or_failure_status()
    test_dependency_rejects_non_allowlisted_validation()
    test_dependency_accepts_known_review_only_statuses()
    test_finance_producers_run_before_followup_triage()
    test_finance_producer_commands_use_supported_flags_and_always_execute()
    test_finance_producer_failure_stops_before_triage()
    test_os2_control_producers_run_before_os2_in_dependency_order()
    test_os2_required_inputs_have_producer_coverage_within_sla()
    test_os2_producer_failure_stops_before_os2()
    test_obsolete_wf85_producer_removed_chain_order_preserved()
    test_pm_control_packet_producer_runs_before_autonomy_router()
    test_routing_index_producer_runs_before_cleanup_contraction()
    test_final_producer_coverage_order_flags_and_windows()
    test_per_spec_reuse_window_with_source_mtime_invalidation()
    test_os2_and_wiki_stale_source_producers_all_covered()
    test_no_commands_declare_reuse_always_execute_by_default()
    test_default_run_executes_every_command_without_skips()
    test_loop_repair_token_attribution_producers_before_wf74_queue()
    test_loop_repair_final_routing_index_and_capsules_after_gate()
    test_loop_repair_all_45_always_execute_no_reuse()
    test_closure_chain_ledger_appends_not_checks()
    test_closure_chain_order_triage_ledger_downstream_capsules()
    test_closure_chain_fail_closed_triage_before_ledger()
    test_closure_chain_stable_plan_idempotent_single_ledger()
    test_closure_chain_dry_run_no_execution_no_reuse()
    test_transient_failure_is_retried_once_and_chain_continues()
    test_persistent_failure_stops_chain_after_retry()
    test_timeout_failure_is_not_retried()
    test_default_run_sequence_keeps_fail_fast_no_retry()
    test_build_packet_reports_retry_telemetry_fields()
    print("wf88 daily actionability refresh tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


SCORECARD_STEP = r'''
import json, pathlib, sys
root = pathlib.Path(".")
(root / "tmp").mkdir(exist_ok=True)
recovered = (root / "recovered.txt").exists()
bad = sys.argv[1]
fixtures = [{"fixture_id": "rq_other_fixture", "status": "fail" if bad == "other" else "pass"},
            {"fixture_id": "rq_freshness_current_descriptor_accepted",
             "status": "pass" if recovered or bad != "freshness" else "fail"}]
(root / "tmp" / "retrieval-quality-scorecard.json").write_text(json.dumps({"fixtures": fixtures}))
raise SystemExit(0 if all(f["status"] == "pass" for f in fixtures) else 1)
'''


def _recovery_harness(tmp_path, monkeypatch, bad: str, step_id: str = "retrieval_quality_scorecard"):
    module = load_module()
    monkeypatch.setattr(module, "ROOT", tmp_path)
    monkeypatch.setattr(module, "WIKI_SYNTHESIS_RECOVERY", {
        "id": "wf88_wiki_synthesis_recovery",
        "command": [sys.executable, "-c", "import pathlib; pathlib.Path('recovered.txt').write_text('x')"],
    })
    commands = [{"id": step_id, "command": [sys.executable, "-c", SCORECARD_STEP, bad]}]
    return module.run_sequence(commands, execute=True, timeout_seconds=30, reuse_fresh_wf74=False,
                               retry_limit=1, retry_wait_seconds=0)


def test_wiki_freshness_only_failure_rebuilds_wiki_then_retries(tmp_path, monkeypatch) -> None:
    # 2026-09-24 deadlock: a stale wiki packet failed the scorecard, which runs
    # before the only step that rebuilds the packet.
    results, ok = _recovery_harness(tmp_path, monkeypatch, "freshness")
    assert ok is True
    row = results[0]
    assert row["returncode"] == 0 and row["retry_attempted"] is True
    assert row["recovery"]["id"] == "wf88_wiki_synthesis_recovery" and row["recovery"]["returncode"] == 0
    assert (tmp_path / "recovered.txt").exists()


def test_other_scorecard_failure_does_not_trigger_wiki_rebuild(tmp_path, monkeypatch) -> None:
    results, ok = _recovery_harness(tmp_path, monkeypatch, "other")
    assert ok is False
    assert "recovery" not in results[0]
    assert not (tmp_path / "recovered.txt").exists()


def test_recovery_only_applies_to_retrieval_scorecard_step(tmp_path, monkeypatch) -> None:
    results, ok = _recovery_harness(tmp_path, monkeypatch, "freshness", step_id="some_other_step")
    assert ok is False
    assert "recovery" not in results[0]


def test_production_recovery_rebuilds_pages_and_packet_together() -> None:
    module = load_module()
    command = module.WIKI_SYNTHESIS_RECOVERY["command"]
    assert command[1].endswith("wf88_wiki_synthesis_packet.py")
    assert "--write-wiki" in command and "--write" in command
    assert [row["id"] for row in module.COMMANDS].count("wf88_wiki_synthesis") == 1
    assert len(module.COMMANDS) == 45
