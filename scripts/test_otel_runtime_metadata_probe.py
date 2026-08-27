from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "otel_runtime_metadata_probe.py"
TMP_LOG = ROOT / "tmp" / "test-otel-runtime-metadata-probe.log"
OUT = ROOT / "tmp" / "test-otel-runtime-metadata-probe.json"
GLOB_DIR = ROOT / "tmp" / "test-otel-runtime-metadata-probe-glob"
TRACE_JSONL = ROOT / "tmp" / "test-otel-runtime-metadata-probe-traces.jsonl"
METRIC_JSONL = ROOT / "tmp" / "test-otel-runtime-metadata-probe-metrics.jsonl"


def expect(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def run_probe(text: str) -> tuple[subprocess.CompletedProcess[str], dict]:
    TMP_LOG.parent.mkdir(parents=True, exist_ok=True)
    TMP_LOG.write_text(text, encoding="utf-8")
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--log",
            str(TMP_LOG),
            "--log-glob",
            "",
            "--trace-jsonl",
            "",
            "--metric-jsonl",
            "",
            "--json-out",
            str(OUT),
            "--write",
            "--validate",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    payload = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else {}
    return result, payload


def run_probe_with_owner_packet(text: str, owner_packet: dict, *, stale_seconds: int = 0) -> tuple[subprocess.CompletedProcess[str], dict]:
    owner_path = ROOT / "tmp" / "test-otel-field-depth-owner-packet.json"
    owner_path.write_text(json.dumps(owner_packet), encoding="utf-8")
    TMP_LOG.parent.mkdir(parents=True, exist_ok=True)
    TMP_LOG.write_text(text, encoding="utf-8")
    if stale_seconds:
        stale_time = time.time() - stale_seconds
        os.utime(TMP_LOG, (stale_time, stale_time))
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--log",
            str(TMP_LOG),
            "--owner-packet",
            str(owner_path),
            "--log-glob",
            "",
            "--trace-jsonl",
            "",
            "--metric-jsonl",
            "",
            "--json-out",
            str(OUT),
            "--write",
            "--validate",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    payload = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else {}
    return result, payload


def run_probe_with_glob(owner_packet: dict) -> tuple[subprocess.CompletedProcess[str], dict]:
    owner_path = ROOT / "tmp" / "test-otel-field-depth-owner-packet.json"
    owner_path.write_text(json.dumps(owner_packet), encoding="utf-8")
    GLOB_DIR.mkdir(parents=True, exist_ok=True)
    primary = GLOB_DIR / "collector.err.log"
    restart = GLOB_DIR / "local-restart.err.log"
    primary.write_text("old collector line without runtime metadata fields", encoding="utf-8")
    restart.write_text("fresh restart line without runtime metadata fields", encoding="utf-8")
    stale_time = time.time() - 26 * 3600
    os.utime(primary, (stale_time, stale_time))
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--log",
            str(primary),
            "--log-glob",
            str(GLOB_DIR / "*.err.log"),
            "--trace-jsonl",
            "",
            "--metric-jsonl",
            "",
            "--owner-packet",
            str(owner_path),
            "--json-out",
            str(OUT),
            "--write",
            "--validate",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    payload = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else {}
    return result, payload


def run_probe_with_jsonl_exporters(owner_packet: dict) -> tuple[subprocess.CompletedProcess[str], dict]:
    owner_path = ROOT / "tmp" / "test-otel-field-depth-owner-packet.json"
    owner_path.write_text(json.dumps(owner_packet), encoding="utf-8")
    TMP_LOG.parent.mkdir(parents=True, exist_ok=True)
    TMP_LOG.write_text("debug stderr basic line without expanded attributes", encoding="utf-8")
    TRACE_JSONL.write_text(
        json.dumps({
            "resourceSpans": [{
                "scopeSpans": [{
                    "spans": [{
                        "attributes": [
                            {"key": "openclaw.toolName", "value": {"stringValue": "shell_command"}},
                            {"key": "openclaw.tool.source", "value": {"stringValue": "codex"}},
                            {"key": "gen_ai.tool.name", "value": {"stringValue": "shell_command"}},
                        ]
                    }]
                }]
            }]
        })
        + "\n",
        encoding="utf-8",
    )
    METRIC_JSONL.write_text(
        json.dumps({
            "resourceMetrics": [{
                "scopeMetrics": [{
                    "metrics": [
                        {"name": "openclaw.model_call.duration_ms"},
                        {"name": "openclaw.context.system_prompt_chars"},
                        {"name": "gen_ai.client.token.usage"},
                    ]
                }]
            }]
        })
        + "\n",
        encoding="utf-8",
    )
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--log",
            str(TMP_LOG),
            "--log-glob",
            "",
            "--trace-jsonl",
            str(TRACE_JSONL),
            "--metric-jsonl",
            str(METRIC_JSONL),
            "--owner-packet",
            str(owner_path),
            "--json-out",
            str(OUT),
            "--write",
            "--validate",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    payload = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else {}
    return result, payload


def main() -> int:
    errors: list[str] = []
    ok_result, ok_payload = run_probe(
        """
        Name: openclaw.model_call.duration_ms
        Attributes: openclaw.provider="openai" openclaw.model="gpt-5.5"
        openclaw.context.prompt_chars: Int(211)
        openclaw.context.system_prompt_chars: Int(79623)
        Name: openclaw.tool.execution.duration_ms
        Attributes: gen_ai.tool.name="shell_command" openclaw.tool.params.kind="metadata"
        Name: openclaw.provider.request_id_hash
        """
    )
    expect(ok_result.returncode == 0, f"expected ok probe: {ok_result.stdout} {ok_result.stderr}", errors)
    expect(ok_payload.get("validation", {}).get("status") == "ok", "ok probe validation should pass", errors)
    expect(ok_payload.get("status") == "ok", "ok probe status should be ok", errors)
    expect(ok_payload.get("summary", {}).get("allowed_field_count", 0) >= 5, "allowed fields not counted", errors)
    expect(ok_payload.get("summary", {}).get("raw_content_marker_count") == 0, "count-only prompt fields should not be raw content", errors)
    expect(ok_payload.get("source", {}).get("last_write_utc") is not None, "source last-write timestamp missing", errors)
    expect(ok_payload.get("source", {}).get("age_hours") is not None, "source age missing", errors)
    expect(ok_payload.get("summary", {}).get("emission_path_diagnosis") == "approved_runtime_metadata_observed", "ok probe diagnosis should show observed metadata", errors)
    expect(ok_payload.get("summary", {}).get("owner_gated_repair_packet_status") == "not_required", "observed metadata should not require emission repair", errors)
    expect(ok_payload.get("summary", {}).get("runtime_metadata_learning_ready") is True, "observed metadata should be learning-ready", errors)
    expect(ok_payload.get("emission_path_repair", {}).get("status") == "not_required", "observed repair packet status mismatch", errors)
    boundary = ok_payload.get("authority_boundary", {})
    for flag in (
        "external_export_allowed",
        "runtime_config_mutation_allowed",
        "raw_prompt_capture_allowed",
        "tool_payload_capture_allowed",
        "secret_or_header_capture_allowed",
        "model_ranking_claim_allowed",
        "paper_or_live_or_account_action_allowed",
        "owner_approval_inferred",
    ):
        expect(boundary.get(flag) is False, f"authority flag must be false: {flag}", errors)

    exporter_result, exporter_payload = run_probe_with_jsonl_exporters(
        {
            "status": "approved_enabled",
            "authority_boundary": {"owner_approved_local_depth_expansion": True},
            "validation": {"status": "ok"},
        }
    )
    exporter_summary = exporter_payload.get("summary", {})
    exporter_source = exporter_payload.get("source", {})
    expect(exporter_result.returncode == 0, f"JSONL exporter probe should pass: {exporter_result.stdout} {exporter_result.stderr}", errors)
    expect(exporter_payload.get("status") == "ok", "JSONL exporter probe should be ok", errors)
    expect(exporter_summary.get("runtime_metadata_observed") is True, "JSONL exporter fields should count as observed", errors)
    expect(exporter_summary.get("file_exporter_observed") is True, "file exporter observation flag missing", errors)
    expect(exporter_summary.get("debug_log_observed") is False, "debug log should remain unobserved in JSONL exporter test", errors)
    expect(exporter_summary.get("emission_path_diagnosis") == "debug_basic_attributes_hidden_file_export_observed", "JSONL exporter diagnosis should identify debug-basic false negative", errors)
    expect(exporter_summary.get("enabled_vs_observed_reconciliation") == "approved_enabled_and_observed", "JSONL exporter probe should reconcile enabled and observed", errors)
    expect(exporter_summary.get("raw_content_marker_count") == 0, "count-only system prompt chars should not be raw content", errors)
    expect(exporter_source.get("file_exporter_present_file_count") == 2, "JSONL exporter source count should include traces and metrics", errors)
    expect(exporter_summary.get("owner_gated_repair_packet_status") == "not_required", "JSONL exporter should not require repair", errors)
    expect(exporter_payload.get("emission_path_repair", {}).get("runtime_metadata_learning_ready") is True, "JSONL exporter should be learning-ready", errors)

    blocked_result, blocked_payload = run_probe(
        """
        Name: openclaw.model_call.duration_ms
        openclaw.content.prompt="raw user text"
        system_prompt="raw system prompt text"
        authorization="Bearer token-value"
        """
    )
    expect(blocked_result.returncode != 0, "blocked probe should fail validation", errors)
    expect(blocked_payload.get("status") == "blocked", "blocked probe status should be blocked", errors)
    expect(blocked_payload.get("summary", {}).get("raw_content_marker_count", 0) > 0, "raw marker not found", errors)
    expect(blocked_payload.get("summary", {}).get("secret_or_header_marker_count", 0) > 0, "secret marker not found", errors)
    expect(blocked_payload.get("summary", {}).get("emission_path_diagnosis") == "forbidden_marker_observed", "blocked probe diagnosis should identify forbidden marker", errors)
    expect(blocked_payload.get("emission_path_repair", {}).get("status") == "blocked_forbidden_marker_observed", "blocked probe should emit blocked repair status", errors)
    expect(blocked_payload.get("emission_path_repair", {}).get("runtime_metadata_learning_ready") is False, "blocked probe must not be learning-ready", errors)

    enabled_result, enabled_payload = run_probe_with_owner_packet(
        "collector log line without OpenClaw runtime metadata fields",
        {
            "status": "approved_enabled",
            "authority_boundary": {"owner_approved_local_depth_expansion": True},
            "validation": {"status": "ok"},
        },
    )
    expect(enabled_result.returncode == 0, f"enabled-but-not-observed probe should not fail: {enabled_result.stdout} {enabled_result.stderr}", errors)
    enabled_summary = enabled_payload.get("summary", {})
    expect(enabled_summary.get("metadata_depth_approved_enabled") is True, "enabled owner packet not reflected", errors)
    expect(enabled_summary.get("runtime_metadata_observed") is False, "runtime metadata should be unobserved", errors)
    expect(enabled_summary.get("enabled_vs_observed_reconciliation") == "approved_enabled_not_observed", "enabled vs observed state not reconciled", errors)
    expect(enabled_summary.get("emission_path_diagnosis") == "collector_debug_log_current_allowed_fields_absent", "fresh enabled-but-not-observed diagnosis should cite absent fields", errors)
    expect(enabled_summary.get("owner_gated_repair_packet_status") == "owner_gated_repair_required", "enabled/not-observed should require owner-gated repair", errors)
    expect(enabled_summary.get("runtime_metadata_learning_ready") is False, "enabled/not-observed should not be learning-ready", errors)
    enabled_repair = enabled_payload.get("emission_path_repair", {})
    expect(enabled_repair.get("status") == "owner_gated_repair_required", "enabled/not-observed repair status mismatch", errors)
    expect(enabled_repair.get("owner_gated_repair_required") is True, "enabled/not-observed repair flag missing", errors)
    expect("collector/runtime config mutation" in enabled_repair.get("blocked_mutations", []), "repair packet must keep collector/runtime mutation blocked", errors)
    expect("otel_depth_enabled_but_runtime_metadata_not_observed" in enabled_payload.get("validation", {}).get("warnings", []), "missing enabled/not-observed warning", errors)

    stale_result, stale_payload = run_probe_with_owner_packet(
        "old collector log line without OpenClaw runtime metadata fields",
        {
            "status": "approved_enabled",
            "authority_boundary": {"owner_approved_local_depth_expansion": True},
            "validation": {"status": "ok"},
        },
        stale_seconds=26 * 3600,
    )
    stale_summary = stale_payload.get("summary", {})
    expect(stale_result.returncode == 0, f"stale enabled-but-not-observed probe should not fail: {stale_result.stdout} {stale_result.stderr}", errors)
    expect(stale_summary.get("emission_path_diagnosis") == "collector_debug_log_stale_no_current_runtime_metadata_source", "stale diagnosis missing", errors)
    expect("collector_debug_log_stale_no_current_runtime_metadata_source" in stale_payload.get("validation", {}).get("warnings", []), "missing stale collector warning", errors)

    glob_result, glob_payload = run_probe_with_glob(
        {
            "status": "approved_enabled",
            "authority_boundary": {"owner_approved_local_depth_expansion": True},
            "validation": {"status": "ok"},
        },
    )
    glob_summary = glob_payload.get("summary", {})
    glob_source = glob_payload.get("source", {})
    expect(glob_result.returncode == 0, f"glob probe should not fail: {glob_result.stdout} {glob_result.stderr}", errors)
    expect(glob_source.get("present_file_count") == 2, "glob probe should include primary plus restart log", errors)
    expect(glob_source.get("fresh_file_count") == 1, "glob probe should count the fresh restart log", errors)
    expect(glob_source.get("stale_file_count") == 1, "glob probe should count the stale primary log", errors)
    expect(glob_summary.get("emission_path_diagnosis") == "collector_debug_log_current_allowed_fields_absent", "glob diagnosis should prefer current-source absence over stale-source warning", errors)
    expect("collector_debug_log_stale_no_current_runtime_metadata_source" not in glob_payload.get("validation", {}).get("warnings", []), "glob probe should not emit stale warning when a fresh log exists", errors)

    if errors:
        for error in errors:
            print(f"FAIL: {error}")
        return 1
    print("ok: otel runtime metadata probe is bounded")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
