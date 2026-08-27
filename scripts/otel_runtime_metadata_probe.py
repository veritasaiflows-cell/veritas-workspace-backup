#!/usr/bin/env python3
"""Probe local OTEL output for approved runtime metadata only.

This is the Phase 2 pilot proof surface for OpenClaw runtime metadata capture.
It parses local collector file-exporter JSONL output plus debug logs for
documented model/tool metric and span field names, then runs a strict marker
scan for raw prompt, response, tool payload, system-prompt, secret, credential,
and header content.

It does not start collectors, edit config, decode OTLP payloads, export data, or
claim model ranking / finance correctness.
"""
from __future__ import annotations

import argparse
import glob
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, atomic_write_text, load_json_artifact

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
COLLECTOR_DIR = TMP / "otel-collector"
DEFAULT_LOG = COLLECTOR_DIR / "collector.err.log"
DEFAULT_LOG_GLOB = "tmp/otel-collector/*.err.log"
DEFAULT_TRACE_JSONL = COLLECTOR_DIR / "traces.jsonl"
DEFAULT_METRIC_JSONL = COLLECTOR_DIR / "metrics.jsonl"
OUT_JSON = TMP / "otel-runtime-metadata-probe.json"
OUT_MD = TMP / "otel-runtime-metadata-probe.md"
OWNER_PACKET = TMP / "otel-field-depth-limited-owner-packet.json"
SCHEMA = "veritas.otel_runtime_metadata_probe.v1"

ALLOWED_RUNTIME_FIELDS = [
    "openclaw.tokens",
    "openclaw.cost.usd",
    "openclaw.run.duration_ms",
    "openclaw.context.tokens",
    "openclaw.context.prompt_chars",
    "openclaw.context.system_prompt_chars",
    "gen_ai.client.token.usage",
    "gen_ai.client.operation.duration",
    "gen_ai.request.model",
    "gen_ai.operation.name",
    "openclaw.channel",
    "openclaw.provider",
    "openclaw.model",
    "openclaw.model_call.duration_ms",
    "openclaw.model_call.request_bytes",
    "openclaw.model_call.response_bytes",
    "openclaw.model_call.time_to_first_byte_ms",
    "openclaw.provider.request_id_hash",
    "openclaw.errorCategory",
    "openclaw.failureKind",
    "openclaw.model.failover",
    "openclaw.skill.used",
    "openclaw.skill.name",
    "openclaw.skill.source",
    "openclaw.tool.execution.duration_ms",
    "openclaw.tool.execution.blocked",
    "openclaw.tool.loop.iterations",
    "openclaw.tool.loop.duration_ms",
    "openclaw.toolName",
    "openclaw.tool.source",
    "openclaw.tool.owner",
    "openclaw.tool.params.kind",
    "gen_ai.tool.name",
    "openclaw.deniedReason",
]

COUNT_ONLY_SUFFIXES = (
    "_chars",
    "_bytes",
    "_count",
    "_tokens",
    "chars",
    "bytes",
    "count",
    "tokens",
)

RAW_CONTENT_MARKERS = [
    "openclaw.content",
    "gen_ai.prompt",
    "gen_ai.completion",
    "inputMessages",
    "outputMessages",
    "toolInputs",
    "toolOutputs",
    "toolDefinitions",
    "systemPrompt",
    "message_content",
    "response_text",
    "tool_input",
    "tool_output",
    "system_prompt",
]

SECRET_MARKERS = [
    "authorization",
    "bearer ",
    "api_key",
    "apikey",
    "oauth_token",
    "access_token",
    "refresh_token",
    "cookie",
    "set-cookie",
    "credential",
    "password",
    "private_key",
]

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "local_only": True,
    "metadata_only": True,
    "external_export_allowed": False,
    "runtime_config_mutation_allowed": False,
    "collector_start_or_stop_allowed": False,
    "raw_prompt_capture_allowed": False,
    "raw_response_capture_allowed": False,
    "tool_payload_capture_allowed": False,
    "system_prompt_capture_allowed": False,
    "secret_or_header_capture_allowed": False,
    "model_ranking_claim_allowed": False,
    "investment_correctness_from_runtime_metrics_allowed": False,
    "canon_or_portfolio_mutation_allowed": False,
    "paper_or_live_or_account_action_allowed": False,
    "owner_approval_inferred": False,
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def utc_from_timestamp(timestamp: float) -> str:
    return datetime.fromtimestamp(timestamp, timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def read_log(path: Path, max_bytes: int) -> str:
    if not path.exists():
        return ""
    data = path.read_bytes()
    if len(data) > max_bytes:
        data = data[-max_bytes:]
    return data.decode("utf-8", errors="replace")


def resolve_log_paths(primary: Path, pattern: str | None) -> list[Path]:
    paths = [primary]
    if pattern:
        pattern_path = Path(pattern)
        if not pattern_path.is_absolute():
            pattern_path = ROOT / pattern_path
        paths.extend(Path(match) for match in glob.glob(str(pattern_path)))
    unique: dict[str, Path] = {}
    for path in paths:
        resolved = path if path.is_absolute() else ROOT / path
        unique[str(resolved.resolve())] = resolved
    return sorted(unique.values(), key=lambda item: (item.exists(), item.stat().st_mtime if item.exists() else 0), reverse=True)


def resolve_exporter_paths(trace_jsonl: Path | None, metric_jsonl: Path | None) -> list[Path]:
    paths = [path for path in (trace_jsonl, metric_jsonl) if path is not None]
    unique: dict[str, Path] = {}
    for path in paths:
        resolved = path if path.is_absolute() else ROOT / path
        unique[str(resolved.resolve())] = resolved
    return sorted(unique.values(), key=lambda item: (item.exists(), item.stat().st_mtime if item.exists() else 0), reverse=True)


def read_log_sources(paths: list[Path], max_bytes: int, source_kind: str = "debug_log") -> list[dict[str, Any]]:
    sources: list[dict[str, Any]] = []
    for path in paths:
        text = read_log(path, max_bytes=max_bytes)
        sources.append({"path": path, "text": text, "source_kind": source_kind})
    return sources


def combine_source_text(sources: list[dict[str, Any]]) -> str:
    parts: list[str] = []
    for source in sources:
        path = source["path"]
        text = source["text"]
        if text:
            parts.append(f"\n# source: {rel(path)}\n{text}")
    return "\n".join(parts)


def source_file_metadata(source: dict[str, Any], max_bytes: int, now: datetime) -> dict[str, Any]:
    path = source["path"]
    text = source["text"]
    last_write_utc = None
    age_hours = None
    if path.exists():
        modified = datetime.fromtimestamp(path.stat().st_mtime, timezone.utc)
        last_write_utc = utc_from_timestamp(path.stat().st_mtime)
        age_hours = round(max(0.0, (now - modified).total_seconds() / 3600), 2)
    return {
        "collector_log": rel(path),
        "path": rel(path),
        "source_kind": source.get("source_kind") or "debug_log",
        "exists": path.exists(),
        "last_write_utc": last_write_utc,
        "age_hours": age_hours,
        "bytes_read": len(text.encode("utf-8", errors="replace")),
        "line_count": len(text.splitlines()),
        "max_bytes": max_bytes,
    }


def source_metadata(primary: Path, pattern: str | None, sources: list[dict[str, Any]], combined_text: str, max_bytes: int, now: datetime) -> dict[str, Any]:
    files = [source_file_metadata(source, max_bytes, now) for source in sources]
    present = sorted(
        [item for item in files if item.get("exists")],
        key=lambda item: item.get("last_write_utc") or "",
        reverse=True,
    )
    fresh = [item for item in present if isinstance(item.get("age_hours"), (int, float)) and float(item["age_hours"]) <= 24]
    debug_files = [item for item in files if item.get("source_kind") == "debug_log"]
    debug_present = sorted(
        [item for item in debug_files if item.get("exists")],
        key=lambda item: item.get("last_write_utc") or "",
        reverse=True,
    )
    debug_fresh = [item for item in debug_present if isinstance(item.get("age_hours"), (int, float)) and float(item["age_hours"]) <= 24]
    exporter_files = [item for item in files if item.get("source_kind") == "file_exporter"]
    exporter_present = sorted(
        [item for item in exporter_files if item.get("exists")],
        key=lambda item: item.get("last_write_utc") or "",
        reverse=True,
    )
    exporter_fresh = [item for item in exporter_present if isinstance(item.get("age_hours"), (int, float)) and float(item["age_hours"]) <= 24]
    freshest = debug_present[0] if debug_present else None
    freshest_source = present[0] if present else None
    return {
        "collector_log": rel(primary),
        "collector_log_glob": pattern,
        "exists": bool(debug_present),
        "file_count": len(debug_files),
        "present_file_count": len(debug_present),
        "fresh_file_count": len(debug_fresh),
        "stale_file_count": max(0, len(debug_present) - len(debug_fresh)),
        "freshest_log": freshest.get("collector_log") if freshest else None,
        "last_write_utc": freshest.get("last_write_utc") if freshest else None,
        "age_hours": freshest.get("age_hours") if freshest else None,
        "file_exporter_count": len(exporter_files),
        "file_exporter_present_file_count": len(exporter_present),
        "file_exporter_fresh_file_count": len(exporter_fresh),
        "file_exporter_stale_file_count": max(0, len(exporter_present) - len(exporter_fresh)),
        "freshest_file_exporter": exporter_present[0].get("path") if exporter_present else None,
        "freshest_file_exporter_last_write_utc": exporter_present[0].get("last_write_utc") if exporter_present else None,
        "freshest_file_exporter_age_hours": exporter_present[0].get("age_hours") if exporter_present else None,
        "evidence_exists": bool(present),
        "evidence_file_count": len(files),
        "evidence_present_file_count": len(present),
        "evidence_fresh_file_count": len(fresh),
        "evidence_stale_file_count": max(0, len(present) - len(fresh)),
        "freshest_evidence_source": freshest_source.get("path") if freshest_source else None,
        "freshest_evidence_last_write_utc": freshest_source.get("last_write_utc") if freshest_source else None,
        "freshest_evidence_age_hours": freshest_source.get("age_hours") if freshest_source else None,
        "bytes_read": len(combined_text.encode("utf-8", errors="replace")),
        "line_count": len(combined_text.splitlines()),
        "max_bytes_per_file": max_bytes,
        "files": files,
    }


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def owner_packet_state(path: Path) -> dict[str, Any]:
    packet = as_dict(load_json_artifact(path)) if path.exists() else {}
    boundary = as_dict(packet.get("authority_boundary"))
    enabled = packet.get("status") == "approved_enabled" or boundary.get("owner_approved_local_depth_expansion") is True
    return {
        "path": rel(path),
        "present": path.exists(),
        "status": packet.get("status") if packet else "missing",
        "validation_status": as_dict(packet.get("validation")).get("status"),
        "owner_approved_local_depth_expansion": boundary.get("owner_approved_local_depth_expansion") is True,
        "metadata_depth_approved_enabled": enabled if packet else None,
    }


def line_samples(text: str, fields: list[str], limit: int = 24) -> list[dict[str, Any]]:
    samples: list[dict[str, Any]] = []
    for line_no, line in enumerate(text.splitlines(), 1):
        hits = [field for field in fields if field in line]
        if hits:
            samples.append({"line": line_no, "fields": hits[:5], "snippet": line.strip()[:260]})
            if len(samples) >= limit:
                break
    return samples


def marker_token(text: str, start: int, end: int) -> str:
    token_start = start
    while token_start > 0 and re.match(r"[\w.\-]", text[token_start - 1]):
        token_start -= 1
    token_end = end
    while token_end < len(text) and re.match(r"[\w.\-]", text[token_end]):
        token_end += 1
    return text[token_start:token_end]


def is_count_only_token(token: str) -> bool:
    normalized = token.lower().replace("-", "_")
    return normalized.endswith(COUNT_ONLY_SUFFIXES)


def marker_findings(text: str, markers: list[str], marker_type: str) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    lowered = text.lower()
    for marker in markers:
        needle = marker.lower()
        occurrences = []
        for match in re.finditer(re.escape(needle), lowered):
            token = marker_token(text, match.start(), match.end())
            if is_count_only_token(token):
                continue
            occurrences.append(match)
        if occurrences:
            first = occurrences[0].start()
            start = max(0, first - 80)
            end = min(len(text), first + len(marker) + 80)
            findings.append({
                "marker": marker,
                "type": marker_type,
                "count": len(occurrences),
                "first_snippet": text[start:end].replace("\r", " ").replace("\n", " ")[:220],
            })
    return findings


def observed_fields(text: str) -> dict[str, Any]:
    counts = Counter()
    for field in ALLOWED_RUNTIME_FIELDS:
        # Deliberately search by exact string, not loose token names, to avoid
        # mistaking prose or unrelated labels for OpenClaw runtime metadata.
        counts[field] = text.count(field)
    observed = {field: count for field, count in counts.items() if count > 0}
    categories = {
        "model": any(field.startswith("openclaw.model") or field.startswith("gen_ai.") for field in observed),
        "tool": any(field.startswith("openclaw.tool") or field.startswith("gen_ai.tool") for field in observed),
        "tokens_or_cost": any(field in observed for field in ("openclaw.tokens", "openclaw.cost.usd", "gen_ai.client.token.usage")),
        "latency": any("duration_ms" in field or "time_to_first_byte" in field for field in observed),
        "privacy_safe_request_id": "openclaw.provider.request_id_hash" in observed,
    }
    return {
        "allowed_field_count": len(observed),
        "observed_allowed_fields": observed,
        "observed_categories": categories,
        "sample_lines": line_samples(text, list(observed)),
    }


def source_observation_metadata(sources: list[dict[str, Any]]) -> dict[str, Any]:
    observations: list[dict[str, Any]] = []
    by_kind: dict[str, dict[str, Any]] = {}
    for source in sources:
        kind = str(source.get("source_kind") or "debug_log")
        fields = observed_fields(str(source.get("text") or ""))
        allowed_count = int(fields.get("allowed_field_count") or 0)
        observations.append({
            "path": rel(source["path"]),
            "source_kind": kind,
            "allowed_field_count": allowed_count,
            "runtime_metadata_observed": allowed_count > 0,
            "observed_allowed_fields": fields.get("observed_allowed_fields") or {},
        })
        current = by_kind.setdefault(kind, {
            "source_kind": kind,
            "source_count": 0,
            "allowed_field_count": 0,
            "runtime_metadata_observed": False,
        })
        current["source_count"] += 1
        current["allowed_field_count"] += allowed_count
        current["runtime_metadata_observed"] = bool(current["runtime_metadata_observed"] or allowed_count > 0)
    return {
        "source_observations": observations,
        "debug_log_observed": bool(by_kind.get("debug_log", {}).get("runtime_metadata_observed")),
        "file_exporter_observed": bool(by_kind.get("file_exporter", {}).get("runtime_metadata_observed")),
        "observation_by_source_kind": by_kind,
    }


def reconciliation_status(*, forbidden: bool, enabled: bool | None, observed: bool) -> str:
    if forbidden:
        return "blocked_forbidden_marker_observed"
    if enabled is True and observed:
        return "approved_enabled_and_observed"
    if enabled is True and not observed:
        return "approved_enabled_not_observed"
    if enabled is False and observed:
        return "observed_without_enabled_owner_packet"
    if enabled is False and not observed:
        return "not_enabled_not_observed"
    if observed:
        return "observed_without_owner_packet_context"
    return "owner_packet_missing_not_observed"


def emission_path_diagnosis(*, forbidden: bool, source: dict[str, Any], enabled: bool | None, observed: bool) -> str:
    if forbidden:
        return "forbidden_marker_observed"
    if observed:
        if source.get("file_exporter_observed") and not source.get("debug_log_observed"):
            return "debug_basic_attributes_hidden_file_export_observed"
        return "approved_runtime_metadata_observed" if enabled is True else "runtime_metadata_observed_without_enabled_owner_packet"
    if not source.get("evidence_exists"):
        return "collector_debug_log_missing"
    age_hours = source.get("age_hours")
    if isinstance(age_hours, (int, float)) and age_hours > 24:
        return "collector_debug_log_stale_no_current_runtime_metadata_source"
    return "collector_debug_log_current_allowed_fields_absent"


def emission_path_repair_packet(
    *,
    reconciled: str,
    diagnosis: str,
    observed: bool,
    forbidden: bool,
    fields: dict[str, Any],
    source: dict[str, Any],
    owner: dict[str, Any],
    owner_packet_path: Path,
) -> dict[str, Any]:
    observed_allowed = as_dict(fields.get("observed_allowed_fields"))
    missing_allowed = [field for field in ALLOWED_RUNTIME_FIELDS if field not in observed_allowed]
    if forbidden:
        status = "blocked_forbidden_marker_observed"
        next_action = "Stop this metadata stream and prove forbidden markers are removed before any repair lane proceeds."
    elif reconciled == "approved_enabled_not_observed":
        status = "owner_gated_repair_required"
        next_action = (
            "Open a scoped producer/emission-path repair lane: generate one local runtime event, verify approved "
            "metadata reaches collector file exporters, then rerun this probe."
        )
    elif observed:
        status = "not_required"
        next_action = "No emission-path repair is required; keep metadata-only proof in the learning loop."
    else:
        status = "not_authorized_not_observed"
        next_action = "Keep observing; do not widen metadata depth or mutate runtime/collector config from this probe."
    return {
        "schema": "veritas.otel_runtime_metadata_emission_path_repair.v1",
        "status": status,
        "owner_packet_path": rel(owner_packet_path),
        "owner_packet_status": owner.get("status"),
        "metadata_depth_approved_enabled": owner.get("metadata_depth_approved_enabled"),
        "reconciliation": reconciled,
        "emission_path_diagnosis": diagnosis,
        "runtime_metadata_learning_ready": bool(observed and not forbidden),
        "producer_expected": "OpenClaw runtime/tool/model producers emit approved metadata attributes into local OTEL collector file-exporter evidence.",
        "expected_allowed_fields": ALLOWED_RUNTIME_FIELDS,
        "observed_allowed_fields": observed_allowed,
        "missing_allowed_field_sample": missing_allowed[:12],
        "freshest_evidence_source": source.get("freshest_evidence_source"),
        "freshest_evidence_age_hours": source.get("freshest_evidence_age_hours"),
        "owner_gated_repair_required": status == "owner_gated_repair_required",
        "blocked_mutations": [
            "collector/runtime config mutation",
            "collector start/stop",
            "raw prompt/response/tool payload capture",
            "secret/header capture",
            "external export",
            "model ranking or finance-correctness inference",
        ],
        "proof_commands": [
            "python scripts\\otel_runtime_metadata_probe.py --write --write-md --validate",
            "python scripts\\otel_learning_loop.py --write --validate",
            "python scripts\\wf74_improvement_opportunity_queue.py --write --write-md --validate",
        ],
        "next_owner_gated_action": next_action,
    }


def build_probe(
    log_path: Path,
    max_bytes: int,
    owner_packet_path: Path = OWNER_PACKET,
    log_glob: str | None = DEFAULT_LOG_GLOB,
    trace_jsonl: Path | None = DEFAULT_TRACE_JSONL,
    metric_jsonl: Path | None = DEFAULT_METRIC_JSONL,
) -> dict[str, Any]:
    now = datetime.now(timezone.utc).replace(microsecond=0)
    log_paths = resolve_log_paths(log_path, log_glob)
    exporter_paths = resolve_exporter_paths(trace_jsonl, metric_jsonl)
    log_sources = read_log_sources(log_paths, max_bytes=max_bytes, source_kind="debug_log")
    exporter_sources = read_log_sources(exporter_paths, max_bytes=max_bytes, source_kind="file_exporter")
    sources = log_sources + exporter_sources
    text = combine_source_text(sources)
    source = source_metadata(log_path, log_glob, sources, text, max_bytes, now)
    source.update(source_observation_metadata(sources))
    fields = observed_fields(text)
    owner = owner_packet_state(owner_packet_path)
    raw_findings = marker_findings(text, RAW_CONTENT_MARKERS, "raw_content")
    secret_findings = marker_findings(text, SECRET_MARKERS, "secret_or_header")
    forbidden = raw_findings + secret_findings
    warning = not text or fields["allowed_field_count"] == 0
    status = "blocked" if forbidden else ("warning" if warning else "ok")
    observed = fields["allowed_field_count"] > 0
    enabled = owner.get("metadata_depth_approved_enabled")
    reconciled = reconciliation_status(forbidden=bool(forbidden), enabled=enabled, observed=observed)
    diagnosis = emission_path_diagnosis(forbidden=bool(forbidden), source=source, enabled=enabled, observed=observed)
    repair = emission_path_repair_packet(
        reconciled=reconciled,
        diagnosis=diagnosis,
        observed=observed,
        forbidden=bool(forbidden),
        fields=fields,
        source=source,
        owner=owner,
        owner_packet_path=owner_packet_path,
    )
    if forbidden:
        status_meaning = "forbidden marker observed; stop and rollback collector capture"
        next_safe_action = "Stop using this runtime metadata stream until forbidden markers are removed and rollback proof is clean."
    elif diagnosis == "debug_basic_attributes_hidden_file_export_observed":
        status_meaning = "approved metadata is visible in collector file exporters; debug stderr is likely hiding attributes at basic verbosity"
        next_safe_action = "No runtime/config mutation needed for this probe; keep validating metadata-only file exporters and leave collector config unchanged."
    elif reconciled == "approved_enabled_not_observed":
        status_meaning = "owner packet is approved/enabled but local collector evidence has not emitted approved runtime metadata fields yet"
        next_safe_action = "No runtime/config mutation here; generate a fresh local runtime event or inspect collector emission path, then rerun this probe."
    elif warning:
        status_meaning = "collector evidence present but no approved runtime metadata fields observed yet"
        next_safe_action = "Continue local metadata-only validation; no capture-depth or runtime change is authorized by this probe."
    else:
        status_meaning = "approved runtime metadata fields observed with no forbidden markers"
        next_safe_action = "Continue local metadata-only validation; no capture-depth or runtime change is authorized by this probe."
    return {
        "schema": SCHEMA,
        "generated_at_utc": now.isoformat().replace("+00:00", "Z"),
        "status": status,
        "source": source,
        "owner_packet": owner,
        "summary": {
            "runtime_metadata_observed": observed,
            "allowed_field_count": fields["allowed_field_count"],
            "raw_content_marker_count": sum(item["count"] for item in raw_findings),
            "secret_or_header_marker_count": sum(item["count"] for item in secret_findings),
            "metadata_depth_approved_enabled": enabled,
            "owner_packet_status": owner.get("status"),
            "owner_packet_validation_status": owner.get("validation_status"),
            "enabled_vs_observed_reconciliation": reconciled,
            "emission_path_diagnosis": diagnosis,
            "collector_log_age_hours": source.get("age_hours"),
            "freshest_evidence_source": source.get("freshest_evidence_source"),
            "freshest_evidence_age_hours": source.get("freshest_evidence_age_hours"),
            "file_exporter_observed": source.get("file_exporter_observed"),
            "debug_log_observed": source.get("debug_log_observed"),
            "owner_gated_repair_packet_status": repair.get("status"),
            "runtime_metadata_learning_ready": repair.get("runtime_metadata_learning_ready"),
            "status_meaning": status_meaning,
            "next_safe_action": next_safe_action,
        },
        **fields,
        "emission_path_repair": repair,
        "forbidden_findings": forbidden[:50],
        "allowed_runtime_fields": ALLOWED_RUNTIME_FIELDS,
        "blocked_markers": {
            "raw_content": RAW_CONTENT_MARKERS,
            "secret_or_header": SECRET_MARKERS,
        },
        "authority_boundary": AUTHORITY_BOUNDARY.copy(),
        "limits": [
            "Probe parses local collector JSONL file exporters and debug output only; it does not decode OTLP protobuf payloads.",
            "Collector debug stderr may hide attributes when verbosity is basic; JSONL file exporters are the stronger local proof surface.",
            "A warning means local evidence has not yet shown detailed approved fields, not that telemetry is broken.",
            "Any forbidden marker blocks the pilot and requires rollback before using runtime metadata.",
            "Observed runtime metadata is operational evidence only; it does not rank models or score investment correctness.",
        ],
    }


def validate(probe: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    boundary = probe.get("authority_boundary") if isinstance(probe.get("authority_boundary"), dict) else {}
    for key, expected in AUTHORITY_BOUNDARY.items():
        if boundary.get(key) is not expected:
            errors.append(f"authority boundary mismatch: {key}")
    summary = probe.get("summary") if isinstance(probe.get("summary"), dict) else {}
    if summary.get("raw_content_marker_count"):
        errors.append("raw content marker observed in collector debug log")
    if summary.get("secret_or_header_marker_count"):
        errors.append("secret/header marker observed in collector debug log")
    if probe.get("status") == "warning":
        warnings.append(str(summary.get("status_meaning") or "runtime metadata not observed yet"))
    reconciliation = summary.get("enabled_vs_observed_reconciliation")
    if reconciliation == "approved_enabled_not_observed":
        warnings.append("otel_depth_enabled_but_runtime_metadata_not_observed")
    if summary.get("emission_path_diagnosis") == "collector_debug_log_stale_no_current_runtime_metadata_source":
        warnings.append("collector_debug_log_stale_no_current_runtime_metadata_source")
    if reconciliation == "observed_without_enabled_owner_packet":
        warnings.append("runtime_metadata_observed_without_enabled_owner_packet")
    for field in probe.get("allowed_runtime_fields", []):
        if is_count_only_token(str(field)):
            continue
        if re.search(r"prompt|response_text|tool_input|tool_output|system_prompt|secret|credential|authorization", field, re.I):
            errors.append(f"allowed runtime field contains forbidden semantic marker: {field}")
    return {"status": "failed" if errors else "ok", "errors": errors, "warnings": warnings}


def render_md(probe: dict[str, Any]) -> str:
    summary = probe.get("summary") if isinstance(probe.get("summary"), dict) else {}
    source = probe.get("source") if isinstance(probe.get("source"), dict) else {}
    fields = probe.get("observed_allowed_fields") if isinstance(probe.get("observed_allowed_fields"), dict) else {}
    repair = probe.get("emission_path_repair") if isinstance(probe.get("emission_path_repair"), dict) else {}
    lines = [
        "# OTEL Runtime Metadata Probe",
        "",
        f"- Generated: {probe.get('generated_at_utc')}",
        f"- Status: {probe.get('status')}",
        f"- Collector log: {source.get('collector_log')} / last write: {source.get('last_write_utc')} / age hours: {source.get('age_hours')}",
        f"- File exporter observed: {summary.get('file_exporter_observed')} / freshest evidence: {summary.get('freshest_evidence_source')} / age hours: {summary.get('freshest_evidence_age_hours')}",
        f"- Runtime metadata observed: {summary.get('runtime_metadata_observed')}",
        f"- Allowed fields observed: {summary.get('allowed_field_count')}",
        f"- Owner packet: {summary.get('owner_packet_status')} / metadata enabled: {summary.get('metadata_depth_approved_enabled')}",
        f"- Enabled vs observed: {summary.get('enabled_vs_observed_reconciliation')}",
        f"- Emission diagnosis: {summary.get('emission_path_diagnosis')}",
        f"- Emission repair packet: {repair.get('status')} / learning ready: {repair.get('runtime_metadata_learning_ready')}",
        f"- Next owner-gated action: {repair.get('next_owner_gated_action')}",
        f"- Raw content markers: {summary.get('raw_content_marker_count')}",
        f"- Secret/header markers: {summary.get('secret_or_header_marker_count')}",
        "",
        "## Observed Fields",
    ]
    if fields:
        for field, count in sorted(fields.items()):
            lines.append(f"- `{field}`: {count}")
    else:
        lines.append("- None yet.")
    lines.append("")
    lines.append("## Limits")
    for item in probe.get("limits", []):
        lines.append(f"- {item}")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--log", default=str(DEFAULT_LOG))
    parser.add_argument("--log-glob", default=DEFAULT_LOG_GLOB, help="Optional collector log glob to include with --log. Use an empty string to disable.")
    parser.add_argument("--trace-jsonl", default=str(DEFAULT_TRACE_JSONL), help="Collector trace file-export JSONL to inspect. Use an empty string to disable.")
    parser.add_argument("--metric-jsonl", default=str(DEFAULT_METRIC_JSONL), help="Collector metric file-export JSONL to inspect. Use an empty string to disable.")
    parser.add_argument("--max-bytes", type=int, default=2_000_000)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--write-md", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--json-out", default=str(OUT_JSON))
    parser.add_argument("--owner-packet", default=str(OWNER_PACKET))
    args = parser.parse_args(argv)

    probe = build_probe(
        Path(args.log),
        max_bytes=args.max_bytes,
        owner_packet_path=Path(args.owner_packet),
        log_glob=args.log_glob or None,
        trace_jsonl=Path(args.trace_jsonl) if args.trace_jsonl else None,
        metric_jsonl=Path(args.metric_jsonl) if args.metric_jsonl else None,
    )
    validation = validate(probe)
    probe["validation"] = validation
    out = Path(args.json_out)
    if args.write:
        atomic_write_json(out, probe)
    if args.write_md:
        atomic_write_text(out.with_suffix(".md") if out != OUT_JSON else OUT_MD, render_md(probe))
    if args.validate:
        print(json.dumps({"status": validation["status"], "probe_status": probe["status"], "json": rel(out), "errors": validation["errors"], "warnings": validation["warnings"]}, indent=2))
        return 1 if validation["errors"] else 0
    if not args.write and not args.write_md:
        print(json.dumps(probe, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
