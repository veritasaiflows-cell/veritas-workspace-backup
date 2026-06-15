#!/usr/bin/env python3
"""Probe local OTEL debug output for approved runtime metadata only.

This is the Phase 2 pilot proof surface for OpenClaw runtime metadata capture.
It parses local collector debug logs for documented model/tool metric and span
field names, then runs a strict marker scan for raw prompt, response, tool
payload, system-prompt, secret, credential, and header content.

It does not start collectors, edit config, decode OTLP payloads, export data, or
claim model ranking / finance correctness.
"""
from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, atomic_write_text

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
COLLECTOR_DIR = TMP / "otel-collector"
DEFAULT_LOG = COLLECTOR_DIR / "collector.err.log"
OUT_JSON = TMP / "otel-runtime-metadata-probe.json"
OUT_MD = TMP / "otel-runtime-metadata-probe.md"
SCHEMA = "veritas.otel_runtime_metadata_probe.v1"

ALLOWED_RUNTIME_FIELDS = [
    "openclaw.tokens",
    "openclaw.cost.usd",
    "openclaw.run.duration_ms",
    "openclaw.context.tokens",
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


def line_samples(text: str, fields: list[str], limit: int = 24) -> list[dict[str, Any]]:
    samples: list[dict[str, Any]] = []
    for line_no, line in enumerate(text.splitlines(), 1):
        hits = [field for field in fields if field in line]
        if hits:
            samples.append({"line": line_no, "fields": hits[:5], "snippet": line.strip()[:260]})
            if len(samples) >= limit:
                break
    return samples


def marker_findings(text: str, markers: list[str], marker_type: str) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    lowered = text.lower()
    for marker in markers:
        needle = marker.lower()
        count = lowered.count(needle)
        if count:
            first = lowered.find(needle)
            start = max(0, first - 80)
            end = min(len(text), first + len(marker) + 80)
            findings.append({
                "marker": marker,
                "type": marker_type,
                "count": count,
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


def build_probe(log_path: Path, max_bytes: int) -> dict[str, Any]:
    text = read_log(log_path, max_bytes=max_bytes)
    fields = observed_fields(text)
    raw_findings = marker_findings(text, RAW_CONTENT_MARKERS, "raw_content")
    secret_findings = marker_findings(text, SECRET_MARKERS, "secret_or_header")
    forbidden = raw_findings + secret_findings
    warning = not text or fields["allowed_field_count"] == 0
    status = "blocked" if forbidden else ("warning" if warning else "ok")
    return {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": status,
        "source": {
            "collector_log": rel(log_path),
            "exists": log_path.exists(),
            "bytes_read": len(text.encode("utf-8", errors="replace")),
            "line_count": len(text.splitlines()),
            "max_bytes": max_bytes,
        },
        "summary": {
            "runtime_metadata_observed": fields["allowed_field_count"] > 0,
            "allowed_field_count": fields["allowed_field_count"],
            "raw_content_marker_count": sum(item["count"] for item in raw_findings),
            "secret_or_header_marker_count": sum(item["count"] for item in secret_findings),
            "status_meaning": (
                "forbidden marker observed; stop and rollback collector capture"
                if forbidden else (
                    "collector log present but no approved runtime metadata fields observed yet"
                    if warning else "approved runtime metadata fields observed with no forbidden markers"
                )
            ),
        },
        **fields,
        "forbidden_findings": forbidden[:50],
        "allowed_runtime_fields": ALLOWED_RUNTIME_FIELDS,
        "blocked_markers": {
            "raw_content": RAW_CONTENT_MARKERS,
            "secret_or_header": SECRET_MARKERS,
        },
        "authority_boundary": AUTHORITY_BOUNDARY.copy(),
        "limits": [
            "Probe parses local collector debug output only; it does not decode OTLP protobuf payloads.",
            "A warning means the runtime stream has not yet emitted detailed approved fields, not that telemetry is broken.",
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
    for field in probe.get("allowed_runtime_fields", []):
        if re.search(r"prompt|response_text|tool_input|tool_output|system_prompt|secret|credential|authorization", field, re.I):
            errors.append(f"allowed runtime field contains forbidden semantic marker: {field}")
    return {"status": "failed" if errors else "ok", "errors": errors, "warnings": warnings}


def render_md(probe: dict[str, Any]) -> str:
    summary = probe.get("summary") if isinstance(probe.get("summary"), dict) else {}
    fields = probe.get("observed_allowed_fields") if isinstance(probe.get("observed_allowed_fields"), dict) else {}
    lines = [
        "# OTEL Runtime Metadata Probe",
        "",
        f"- Generated: {probe.get('generated_at_utc')}",
        f"- Status: {probe.get('status')}",
        f"- Runtime metadata observed: {summary.get('runtime_metadata_observed')}",
        f"- Allowed fields observed: {summary.get('allowed_field_count')}",
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
    parser.add_argument("--max-bytes", type=int, default=2_000_000)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--write-md", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--json-out", default=str(OUT_JSON))
    args = parser.parse_args(argv)

    probe = build_probe(Path(args.log), max_bytes=args.max_bytes)
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
