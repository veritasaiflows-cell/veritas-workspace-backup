#!/usr/bin/env python3
"""Build and validate a privacy-reviewed OpenClaw OTEL telemetry packet.

Report/prototype only. This script writes tmp artifacts and validates their
privacy/authority contract. It never edits OpenClaw config, installs plugins,
starts services, reads secrets, or calls external APIs.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

WORKSPACE = Path(__file__).resolve().parents[1]
OPENCLAW_PACKAGE = Path(r"C:\Users\Veritas\AppData\Roaming\npm\node_modules\openclaw")
TMP = WORKSPACE / "tmp"
JSON_OUT = TMP / "openclaw-otel-privacy-packet.json"
MD_OUT = TMP / "openclaw-otel-privacy-packet.md"

SOURCE_FILES = {
    "compat_matrix": WORKSPACE / "tmp" / "openai-provider-compat-matrix.md",
    "otel_docs": OPENCLAW_PACKAGE / "docs" / "gateway" / "opentelemetry.md",
    "prompt_caching_docs": OPENCLAW_PACKAGE / "docs" / "reference" / "prompt-caching.md",
    "token_use_docs": OPENCLAW_PACKAGE / "docs" / "reference" / "token-use.md",
    "tools": WORKSPACE / "AGENTS.md",
    "soul": WORKSPACE / "SOUL.md",
}

FORBIDDEN_CAPTURE_KEYS = [
    "inputMessages",
    "outputMessages",
    "toolInputs",
    "toolOutputs",
    "systemPrompt",
]

SENSITIVE_FIELD_MARKERS = [
    "prompt",
    "message_content",
    "completion",
    "response_text",
    "tool_input",
    "tool_output",
    "system_prompt",
    "api_key",
    "auth_token",
    "oauth_token",
    "bearer",
    "secret",
    "credential",
    "authorization",
]


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except FileNotFoundError:
        return ""


def sha256(path: Path) -> str | None:
    if not path.exists():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()


def find_line(path: Path, needle: str) -> dict[str, Any]:
    for idx, line in enumerate(read_text(path).splitlines(), 1):
        if needle in line:
            return {
                "path": str(path),
                "line": idx,
                "needle": needle,
                "snippet": line.strip()[:260],
            }
    return {"path": str(path), "line": None, "needle": needle, "snippet": "NOT_FOUND"}


def source_inventory() -> list[dict[str, Any]]:
    return [
        {"key": key, "path": str(path), "exists": path.exists(), "sha256": sha256(path)}
        for key, path in SOURCE_FILES.items()
    ]


def build_packet() -> dict[str, Any]:
    generated_at = datetime.now(ZoneInfo("America/Phoenix")).isoformat(timespec="seconds")
    proposed_config = {
        "plugins": {
            "allow": ["diagnostics-otel"],
            "entries": {"diagnostics-otel": {"enabled": True}},
        },
        "diagnostics": {
            "enabled": True,
            "otel": {
                "enabled": True,
                "endpoint": "http://127.0.0.1:4318",
                "protocol": "http/protobuf",
                "serviceName": "openclaw-gateway-local",
                "traces": True,
                "metrics": True,
                "logs": False,
                "sampleRate": 0.2,
                "flushIntervalMs": 60000,
                "captureContent": {
                    "enabled": False,
                    "inputMessages": False,
                    "outputMessages": False,
                    "toolInputs": False,
                    "toolOutputs": False,
                    "systemPrompt": False,
                },
            },
        },
    }
    allowed_metric_fields = [
        "openclaw.tokens",
        "openclaw.cost.usd",
        "openclaw.run.duration_ms",
        "openclaw.context.tokens",
        "gen_ai.client.token.usage",
        "gen_ai.client.operation.duration",
        "openclaw.model_call.duration_ms",
        "openclaw.model_call.request_bytes",
        "openclaw.model_call.response_bytes",
        "openclaw.model_call.time_to_first_byte_ms",
        "openclaw.provider.request_id_hash",
        "openclaw.tokens.cache_read",
        "openclaw.tokens.cache_write",
        "openclaw.errorCategory",
        "openclaw.failureKind",
    ]
    proposed_json_patch = [
        {"op": "add", "path": "/plugins/allow", "value": ["diagnostics-otel"]},
        {"op": "add", "path": "/plugins/entries/diagnostics-otel", "value": {"enabled": True}},
        {"op": "add", "path": "/diagnostics", "value": proposed_config["diagnostics"]},
    ]
    return {
        "generated_at": generated_at,
        "title": "OpenClaw diagnostics-otel privacy and approval packet",
        "status": "approval_ready_packet_only_not_enabled",
        "scope": {
            "goal": "Prepare a safe path to capture request correlation, model-call latency, token/cache usage, and bounded error/rate-limit state without exporting prompts, responses, tool payloads, system prompts, secrets, or credentials.",
            "in_scope": [
                "OpenTelemetry OTLP/HTTP proposal for local/private collector only",
                "metrics and traces for model usage, duration, request/response byte sizes, time-to-first-byte, cacheRead/cacheWrite, hashed provider request ids, and error/failure classifications",
                "privacy validator/prototype for packet/config review",
                "approval language and rollback plan",
            ],
            "out_of_scope": [
                "No config edit, plugin install/enable, Gateway restart, service start, collector start, or external API call in this lane",
                "No raw prompt, response, tool input/output, system prompt, session key, API key, OAuth token, auth header, or credential capture",
                "No public/external collector endpoint until separately approved",
                "No finance/trading/account authority of any kind",
            ],
        },
        "authority": {
            "packet_only": True,
            "config_mutation_allowed": False,
            "plugin_enablement_allowed": False,
            "service_start_allowed": False,
            "external_export_allowed": False,
            "secret_collection_allowed": False,
            "content_capture_allowed": False,
            "finance_or_trading_authority": False,
        },
        "proposed_config_patch_after_approval_only": proposed_config,
        "proposed_config_json_patch_after_approval_only": proposed_json_patch,
        "privacy_controls": {
            "collector_boundary": "Use loopback/local collector endpoint first: http://127.0.0.1:4318. No public tunnel, SaaS backend, or LAN bind without a separate endpoint/retention approval.",
            "content_capture": proposed_config["diagnostics"]["otel"]["captureContent"],
            "logs_default": "OTLP logs disabled in the first pass because logs can have higher accidental-disclosure risk than bounded metrics/traces. Enable later only after reviewing redaction and retention.",
            "request_ids": "Use only openclaw.provider.request_id_hash. Raw upstream x-request-id values must not be exported or stored in workspace artifacts.",
            "headers": "Do not export arbitrary HTTP headers. Only allow documented low-cardinality, non-secret fields. Authorization, cookies, API keys, bearer tokens, and raw request ids are forbidden.",
            "retention": "Initial collector retention should be short, local, and reviewable: recommended 7 days or less for prototype data, with deletion proof before SaaS/export expansion.",
            "cardinality": "Keep labels bounded to provider/model/api/transport/channel/error category. Do not label spans/metrics by user text, prompt hashes that can be joined to content, file paths containing secrets, or raw session keys.",
        },
        "metric_capture_plan": [
            {
                "need": "request correlation",
                "supported_path": "openclaw.model.call span attribute openclaw.provider.request_id_hash",
                "privacy_posture": "hash-only provider request id; raw ids blocked",
                "status": "supported_by_docs",
            },
            {
                "need": "latency",
                "supported_path": "openclaw.model_call.duration_ms, gen_ai.client.operation.duration, openclaw.model_call.time_to_first_byte_ms, openclaw.run.duration_ms",
                "privacy_posture": "numeric histograms only; no prompt/response body",
                "status": "supported_by_docs",
            },
            {
                "need": "cache/token usage",
                "supported_path": "openclaw.tokens with cache_read/cache_write plus gen_ai.client.token.usage; OpenAI cacheWrite remains 0 by provider design while cacheRead maps from cached_tokens",
                "privacy_posture": "token counts only; cache-hit accounting from usage payload, not raw headers",
                "status": "supported_by_docs",
            },
            {
                "need": "rate-limit visibility",
                "supported_path": "error/failure classification via openclaw.errorCategory/openclaw.failureKind and provider quota/status surfaces where available",
                "privacy_posture": "classification/window metadata only; no raw headers or auth-bearing payloads",
                "status": "partial_gap_rate_limit_headers_not_confirmed_in_diagnostics_otel_docs",
                "gap": "OpenAI x-ratelimit-* headers are documented as useful provider headers, but diagnostics-otel docs do not list exported x-ratelimit metrics. Treat exact remaining/reset header export as blocked until a separate allowlisted implementation is reviewed.",
            },
        ],
        "allowed_telemetry_fields": allowed_metric_fields,
        "forbidden_telemetry_markers": SENSITIVE_FIELD_MARKERS,
        "collector_acceptance_criteria": [
            "Collector endpoint is loopback/private and approved before config change.",
            "diagnostics.otel.captureContent.enabled and all captureContent subkeys are false.",
            "OTLP logs remain false for phase 1 unless a separate log-redaction review approves them.",
            "A dry-run/schema review confirms diagnostics and plugin fields before apply.",
            "Post-apply verification shows metrics/traces arriving and no openclaw.content.* attributes present.",
            "Provider request ids appear only as openclaw.provider.request_id_hash, never raw x-request-id.",
            "Rate-limit exact-header metrics are not claimed unless a later reviewed implementation proves allowlisted redacted export.",
        ],
        "approval_language": "Randall approves a local-only OpenClaw diagnostics-otel telemetry prototype using endpoint http://127.0.0.1:4318, metrics/traces enabled, OTLP logs disabled, sampleRate 0.2, flushIntervalMs 60000, and diagnostics.otel.captureContent.enabled plus inputMessages/outputMessages/toolInputs/toolOutputs/systemPrompt all false. Approval covers config/plugin enablement and verification only for this local privacy-reviewed telemetry lane. It does not approve prompt/response/tool/system-prompt capture, public/SaaS export, credential/header capture, package upgrades, unrelated runtime changes, finance/trading/account actions, or inferred future expansion.",
        "implementation_sequence_after_approval": [
            "Use config schema lookup / approved Gateway config tooling before editing.",
            "Back up current OpenClaw config and record hash/path.",
            "Confirm diagnostics-otel plugin availability or install only if approval explicitly covers plugin install.",
            "Apply the proposed JSON Patch operations exactly, preserving existing provider plugin entries and substituting only the approved collector endpoint/serviceName if Randall names a different local collector.",
            "Restart/hot-reload Gateway only through approved first-class Gateway action.",
            "Send one low-risk local test request and inspect collector output for allowed fields plus absence of openclaw.content.* and forbidden markers.",
            "Run this validator against the packet/config snapshot and save proof under tmp/.",
        ],
        "rollback_plan": [
            "Set diagnostics.otel.enabled=false or remove the diagnostics.otel block.",
            "Disable/remove diagnostics-otel from plugins.entries and plugins.allow if it was added only for this prototype.",
            "Hot-reload/restart Gateway through approved Gateway action.",
            "Verify no new OTLP records arrive after rollback and preserve before/after config hashes.",
            "Delete local collector prototype data if Randall wants a clean privacy reset.",
        ],
        "known_limits": [
            "This packet does not prove the plugin is installed or enabled; it intentionally did not mutate runtime state.",
            "Rate-limit exact remaining/reset header telemetry is not confirmed as an out-of-the-box diagnostics-otel metric in the inspected docs.",
            "A collector retention/export policy is still required before any non-loopback or SaaS destination.",
        ],
        "evidence": {
            "otel_export": find_line(SOURCE_FILES["otel_docs"], "using **OTLP/HTTP (protobuf)**"),
            "otel_privacy_default": find_line(SOURCE_FILES["otel_docs"], "Raw model/tool content is **not** exported by default"),
            "otel_capture_content_keys": find_line(SOURCE_FILES["otel_docs"], "captureContent"),
            "otel_request_id_hash": find_line(SOURCE_FILES["otel_docs"], "openclaw.provider.request_id_hash"),
            "otel_model_duration": find_line(SOURCE_FILES["otel_docs"], "openclaw.model_call.duration_ms"),
            "otel_ttfb": find_line(SOURCE_FILES["otel_docs"], "openclaw.model_call.time_to_first_byte_ms"),
            "prompt_cache_mapping": find_line(SOURCE_FILES["prompt_caching_docs"], "OpenAI responses expose cached prompt tokens"),
            "openai_rate_limit_headers": find_line(SOURCE_FILES["prompt_caching_docs"], "x-ratelimit-*"),
            "token_usage_surfaces": find_line(SOURCE_FILES["token_use_docs"], "OpenClaw tracks **tokens**"),
            "config_mutation_boundary": find_line(SOURCE_FILES["tools"], "Ask first before config, auth, credentials, network exposure"),
            "secrets_boundary": find_line(SOURCE_FILES["soul"], "expose secrets, keys, tokens, or credentials"),
        },
        "source_inventory": source_inventory(),
    }


def validate_packet(packet: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    authority = packet.get("authority", {})
    for key in [
        "config_mutation_allowed",
        "plugin_enablement_allowed",
        "service_start_allowed",
        "external_export_allowed",
        "secret_collection_allowed",
        "content_capture_allowed",
        "finance_or_trading_authority",
    ]:
        if authority.get(key) is not False:
            errors.append(f"authority.{key} must be false")
    cfg = packet.get("proposed_config_patch_after_approval_only", {})
    otel = cfg.get("diagnostics", {}).get("otel", {})
    capture = otel.get("captureContent", {})
    if capture.get("enabled") is not False:
        errors.append("captureContent.enabled must be false")
    for key in FORBIDDEN_CAPTURE_KEYS:
        if capture.get(key) is not False:
            errors.append(f"captureContent.{key} must be false")
    endpoint = str(otel.get("endpoint", ""))
    if not (endpoint.startswith("http://127.0.0.1:") or endpoint.startswith("http://localhost:")):
        errors.append("phase-1 endpoint must be loopback http://127.0.0.1 or localhost")
    if otel.get("logs") is not False:
        errors.append("diagnostics.otel.logs must be false for phase 1")
    json_patch = packet.get("proposed_config_json_patch_after_approval_only", [])
    if not any(op.get("path") == "/plugins/entries/diagnostics-otel" for op in json_patch):
        errors.append("non-destructive JSON Patch must add /plugins/entries/diagnostics-otel")
    if not any(op.get("path") == "/diagnostics" for op in json_patch):
        errors.append("non-destructive JSON Patch must add /diagnostics")
    if not (0 <= float(otel.get("sampleRate", -1)) <= 1):
        errors.append("sampleRate must be between 0 and 1")
    serialized_allowed = json.dumps(packet.get("allowed_telemetry_fields", []), sort_keys=True).lower()
    for marker in SENSITIVE_FIELD_MARKERS:
        if marker in serialized_allowed:
            errors.append(f"allowed telemetry fields include forbidden marker: {marker}")
    if "openclaw.provider.request_id_hash" not in packet.get("allowed_telemetry_fields", []):
        errors.append("hashed provider request id field must be explicitly allowed")
    if "partial_gap_rate_limit_headers_not_confirmed_in_diagnostics_otel_docs" not in json.dumps(packet):
        errors.append("rate-limit header export gap must be disclosed")
    return errors


def render_md(packet: dict[str, Any], validation_errors: list[str]) -> str:
    lines: list[str] = []
    lines.append(f"# {packet['title']}")
    lines.append("")
    lines.append(f"Generated: {packet['generated_at']} (America/Phoenix)")
    lines.append("")
    lines.append("## Bottom line")
    lines.append("")
    lines.append("Approval-ready packet only. It proposes local/private diagnostics-otel metrics/traces with content capture off; it did not enable telemetry, edit config, install plugins, start services, collect secrets, or call external APIs.")
    lines.append("")
    lines.append("## Proposed first-pass posture")
    lines.append("")
    lines.append("- Endpoint: `http://127.0.0.1:4318` only unless Randall approves another collector.")
    lines.append("- Signals: metrics + traces on; OTLP logs off for phase 1.")
    lines.append("- Content capture: `enabled=false`; user prompts, model outputs, tool inputs/outputs, and system prompt all false.")
    lines.append("- Request IDs: hashed only via `openclaw.provider.request_id_hash`; raw `x-request-id` blocked.")
    lines.append("- Rate limits: classify/observe bounded rate-limit errors now; exact `x-ratelimit-*` header metrics are a disclosed gap, not an enabled claim.")
    lines.append("")
    lines.append("## Capture plan")
    lines.append("")
    lines.append("| Need | Supported path | Privacy posture | Status |")
    lines.append("|---|---|---|---|")
    for row in packet["metric_capture_plan"]:
        lines.append(f"| {row['need']} | {row['supported_path']} | {row['privacy_posture']} | {row['status']} |")
    lines.append("")
    lines.append("## Proposed config patch after approval only")
    lines.append("")
    lines.append("Non-destructive JSON Patch operations (preferred because they preserve existing plugin entries):")
    lines.append("")
    lines.append("```json")
    lines.append(json.dumps(packet["proposed_config_json_patch_after_approval_only"], indent=2))
    lines.append("```")
    lines.append("")
    lines.append("Equivalent target config fragment:")
    lines.append("")
    lines.append("```json")
    lines.append(json.dumps(packet["proposed_config_patch_after_approval_only"], indent=2))
    lines.append("```")
    lines.append("")
    lines.append("## Exact approval language")
    lines.append("")
    lines.append(f"> {packet['approval_language']}")
    lines.append("")
    lines.append("## Rollback plan")
    lines.append("")
    for item in packet["rollback_plan"]:
        lines.append(f"- {item}")
    lines.append("")
    lines.append("## Acceptance criteria")
    lines.append("")
    for item in packet["collector_acceptance_criteria"]:
        lines.append(f"- {item}")
    lines.append("")
    lines.append("## Known limits")
    lines.append("")
    for item in packet["known_limits"]:
        lines.append(f"- {item}")
    lines.append("")
    lines.append("## Validator result")
    lines.append("")
    if validation_errors:
        lines.append("FAILED")
        for err in validation_errors:
            lines.append(f"- {err}")
    else:
        lines.append("PASSED - packet preserves no-content-capture, loopback-only, no-authority posture.")
    lines.append("")
    lines.append("## Evidence pointers")
    lines.append("")
    for key, ev in packet["evidence"].items():
        lines.append(f"- `{key}` - {ev['path']}:{ev['line']} - {ev['snippet']}")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true", help="write packet JSON/MD under tmp/")
    parser.add_argument("--validate", action="store_true", help="validate packet privacy/authority contract")
    args = parser.parse_args()

    packet = build_packet()
    errors = validate_packet(packet)
    if args.write:
        TMP.mkdir(parents=True, exist_ok=True)
        JSON_OUT.write_text(json.dumps(packet, indent=2) + "\n", encoding="utf-8")
        MD_OUT.write_text(render_md(packet, errors), encoding="utf-8")
    if args.validate:
        if errors:
            print(json.dumps({"status": "failed", "errors": errors}, indent=2))
            return 1
        print(json.dumps({"status": "passed", "json": str(JSON_OUT), "md": str(MD_OUT)}, indent=2))
    elif not args.write:
        print(json.dumps(packet, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
