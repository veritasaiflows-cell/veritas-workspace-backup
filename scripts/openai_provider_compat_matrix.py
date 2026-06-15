#!/usr/bin/env python3
"""Report-only OpenAI/OpenClaw provider compatibility matrix.

This script inspects the installed OpenClaw package and bundled docs/code to
summarize OpenAI-family SDK/provider compatibility. It writes review artifacts
only under tmp/ and never mutates OpenClaw config, auth, packages, runtime, or
provider state.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

WORKSPACE = Path(__file__).resolve().parents[1]
OPENCLAW_PACKAGE = Path(r"C:\Users\Veritas\AppData\Roaming\npm\node_modules\openclaw")
TMP = WORKSPACE / "tmp"
JSON_OUT = TMP / "openai-provider-compat-matrix.json"
MD_OUT = TMP / "openai-provider-compat-matrix.md"

NO_AUTHORITY = {
    "report_only": True,
    "writes_performed": False,
    "config_mutation_allowed": False,
    "auth_mutation_allowed": False,
    "package_install_allowed": False,
    "runtime_mutation_allowed": False,
    "secret_collection_allowed": False,
    "external_api_calls_performed": False,
    "portfolio_or_trading_authority": False,
}

SOURCE_FILES = {
    "openclaw_package": OPENCLAW_PACKAGE / "package.json",
    "openai_installed_package": OPENCLAW_PACKAGE / "node_modules" / "openai" / "package.json",
    "anthropic_installed_package": OPENCLAW_PACKAGE / "node_modules" / "@anthropic-ai" / "sdk" / "package.json",
    "google_genai_installed_package": OPENCLAW_PACKAGE / "node_modules" / "@google" / "genai" / "package.json",
    "openai_docs": OPENCLAW_PACKAGE / "docs" / "providers" / "openai.md",
    "prompt_caching_docs": OPENCLAW_PACKAGE / "docs" / "reference" / "prompt-caching.md",
    "gateway_chat_docs": OPENCLAW_PACKAGE / "docs" / "gateway" / "openai-http-api.md",
    "gateway_responses_docs": OPENCLAW_PACKAGE / "docs" / "gateway" / "openresponses-http-api.md",
    "otel_docs": OPENCLAW_PACKAGE / "docs" / "gateway" / "opentelemetry.md",
    "configuration_docs": OPENCLAW_PACKAGE / "docs" / "gateway" / "configuration.md",
    "models_docs": OPENCLAW_PACKAGE / "docs" / "concepts" / "models.md",
    "openai_provider_dist": OPENCLAW_PACKAGE / "dist" / "openai-provider-Djip0BEA.js",
    "openai_codex_provider_dist": OPENCLAW_PACKAGE / "dist" / "openai-codex-provider-DRG3_qhN.js",
    "openai_base_url_dist": OPENCLAW_PACKAGE / "dist" / "base-url-BQl3uO0O.js",
    "attempt_thread_helpers_dist": OPENCLAW_PACKAGE / "dist" / "attempt.thread-helpers-SEwxPnq-.js",
}


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except FileNotFoundError:
        return ""


def read_json(path: Path) -> dict[str, Any]:
    text = read_text(path)
    if not text:
        return {}
    return json.loads(text)


def sha256(path: Path) -> str | None:
    if not path.exists():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()


def find_line(path: Path, needle: str) -> dict[str, Any]:
    text = read_text(path)
    for idx, line in enumerate(text.splitlines(), 1):
        if needle in line:
            return {
                "path": str(path),
                "line": idx,
                "needle": needle,
                "snippet": line.strip()[:260],
            }
    return {"path": str(path), "line": None, "needle": needle, "snippet": "NOT_FOUND"}


def source_inventory() -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for key, path in SOURCE_FILES.items():
        out.append(
            {
                "key": key,
                "path": str(path),
                "exists": path.exists(),
                "sha256": sha256(path),
            }
        )
    return out


def package_state() -> dict[str, Any]:
    openclaw = read_json(SOURCE_FILES["openclaw_package"])
    deps = openclaw.get("dependencies", {}) if isinstance(openclaw.get("dependencies"), dict) else {}
    def installed(name: str) -> str | None:
        data = read_json(SOURCE_FILES[name])
        return data.get("version") if isinstance(data, dict) else None

    return {
        "openclaw_version": openclaw.get("version"),
        "declared_dependencies": {
            key: deps.get(key)
            for key in [
                "openai",
                "@anthropic-ai/sdk",
                "@anthropic-ai/vertex-sdk",
                "@google/genai",
                "@modelcontextprotocol/sdk",
                "@agentclientprotocol/sdk",
                "@mariozechner/pi-ai",
            ]
            if key in deps
        },
        "installed_versions": {
            "openai": installed("openai_installed_package"),
            "@anthropic-ai/sdk": installed("anthropic_installed_package"),
            "@google/genai": installed("google_genai_installed_package"),
        },
        "type": openclaw.get("type"),
        "main": openclaw.get("main"),
        "bin": openclaw.get("bin"),
    }


def evidence() -> dict[str, Any]:
    return {
        "openai_route_choices": find_line(SOURCE_FILES["openai_docs"], "OpenClaw supports three OpenAI-family routes"),
        "openai_feature_coverage": find_line(SOURCE_FILES["openai_docs"], "| Chat / Responses"),
        "codex_route_warning": find_line(SOURCE_FILES["openai_docs"], "Use only when you intentionally want the normal PI runner"),
        "direct_openai_transport_normalization": find_line(SOURCE_FILES["openai_provider_dist"], "api: \"openai-responses\""),
        "codex_transport_normalization": find_line(SOURCE_FILES["openai_codex_provider_dist"], "api: \"openai-codex-responses\""),
        "codex_base_url": find_line(SOURCE_FILES["openai_base_url_dist"], "OPENAI_CODEX_RESPONSES_BASE_URL"),
        "gateway_chat_disabled_default": find_line(SOURCE_FILES["gateway_chat_docs"], "This endpoint is **disabled by default**"),
        "gateway_responses_disabled_default": find_line(SOURCE_FILES["gateway_responses_docs"], "This endpoint is **disabled by default**"),
        "gateway_operator_boundary": find_line(SOURCE_FILES["gateway_chat_docs"], "Treat this endpoint as a **full operator-access** surface"),
        "prompt_cache_openai_auto": find_line(SOURCE_FILES["prompt_caching_docs"], "Prompt caching is automatic on supported recent models"),
        "prompt_cache_key": find_line(SOURCE_FILES["prompt_caching_docs"], "OpenClaw uses `prompt_cache_key`"),
        "cache_read_mapping": find_line(SOURCE_FILES["prompt_caching_docs"], "OpenAI responses expose cached prompt tokens"),
        "cache_write_zero": find_line(SOURCE_FILES["prompt_caching_docs"], "OpenAI does not expose a separate cache-write token counter"),
        "websocket_transport": find_line(SOURCE_FILES["attempt_thread_helpers_dist"], "params.modelApi !== \"openai-responses\""),
        "otel_export": find_line(SOURCE_FILES["otel_docs"], "using **OTLP/HTTP (protobuf)**"),
        "otel_privacy": find_line(SOURCE_FILES["otel_docs"], "Raw model/tool content is **not** exported by default"),
        "config_schema_lookup": find_line(SOURCE_FILES["configuration_docs"], "Agents and automation should use `config.schema.lookup`"),
        "models_runtime_separation": find_line(SOURCE_FILES["models_docs"], "Model refs choose a provider and model"),
        "runtime_current_session_status": find_line(SOURCE_FILES["openai_docs"], "`/status` shows which model runtime is active"),
        "codex_auth_order": find_line(SOURCE_FILES["openai_docs"], "The native Codex app-server harness uses"),
        "responses_previous_response_id": find_line(SOURCE_FILES["gateway_responses_docs"], "previous_response_id"),
    }


def compatibility_matrix(pkg: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "surface": "OpenClaw core package",
            "current_state": f"Pinned install reports version {pkg.get('openclaw_version')}.",
            "compatibility": "Baseline stable pin; do not upgrade as part of this report.",
            "risk": "Package/version changes could shift provider transports, model catalogs, auth, cache semantics, and Gateway endpoint behavior.",
            "safe_recommendation": "Keep 2026.5.4 pinned unless Randall intentionally revisits stability; use this report as read-only routing evidence.",
        },
        {
            "surface": "OpenAI Node SDK dependency",
            "current_state": f"Declared {pkg['declared_dependencies'].get('openai')}; installed {pkg['installed_versions'].get('openai')}.",
            "compatibility": "Modern official OpenAI SDK is bundled and suitable for Responses-era APIs; report did not import or call it.",
            "risk": "Installed patch can exceed the semver declaration; compatibility should be judged by OpenClaw's pinned dist code, not only package.json ranges.",
            "safe_recommendation": "Do not install/update SDKs manually; if a feature gap appears, verify with OpenClaw release notes and a staged test before changing packages.",
        },
        {
            "surface": "Direct OpenAI Platform route (`openai/*`)",
            "current_state": "OpenClaw normalizes direct OpenAI/default API base URLs to `openai-responses` transport for modern models.",
            "compatibility": "Best fit for API-key billing and native Responses features through OpenClaw's provider layer.",
            "risk": "Requires valid API-key auth; direct API spend and rate limits are separate from ChatGPT/Codex subscription usage.",
            "safe_recommendation": "Use only after auth/route verification; avoid conflating this with `openai-codex/*` subscription route.",
        },
        {
            "surface": "Codex subscription through PI (`openai-codex/*`)",
            "current_state": "OpenClaw has a separate `openai-codex` provider and canonical Codex Responses base URL.",
            "compatibility": "Suitable when using ChatGPT/Codex OAuth through the normal OpenClaw PI runner.",
            "risk": "Not the same as native Codex app-server runtime; route labels can be confused easily.",
            "safe_recommendation": "Keep current default allowed model policy unless intentionally migrating to native Codex runtime.",
        },
        {
            "surface": "Native Codex app-server runtime",
            "current_state": "Docs recommend `openai/gpt-5.5` plus `agents.defaults.agentRuntime.id: codex` for most subscription-native Codex use.",
            "compatibility": "Supported, but it is a runtime change rather than a provider-prefix swap.",
            "risk": "Config/runtime mutation, plugin enablement, auth state, and route behavior would change; outside this report-only lane.",
            "safe_recommendation": "If Randall wants this, make it a separate approved config-change packet with schema lookup, backup, hot-reload/restart proof, and rollback.",
        },
        {
            "surface": "Gateway OpenAI-compatible Chat Completions endpoint",
            "current_state": "`/v1/chat/completions` exists but is disabled by default and treated as operator-access when enabled.",
            "compatibility": "Useful for Open WebUI/LobeChat/LibreChat and other Chat Completions clients.",
            "risk": "Enabling it can expose full operator capability if auth/network boundaries are wrong.",
            "safe_recommendation": "Do not enable in this lane; any future enablement must stay loopback/private and use exact Gateway config-schema proof.",
        },
        {
            "surface": "Gateway OpenResponses endpoint",
            "current_state": "`/v1/responses` exists but is disabled by default; supports item-based input, client tools, SSE, files/images limits, and previous_response_id session reuse.",
            "compatibility": "Good compatibility target for agent-native clients preferring Responses semantics.",
            "risk": "Same operator-access security boundary as chat completions; URL/file fetch limits require careful policy choices.",
            "safe_recommendation": "Treat as future integration surface only; require explicit approval before enabling or exposing.",
        },
        {
            "surface": "Prompt cache knobs and accounting",
            "current_state": "OpenAI caching is automatic on recent models; OpenClaw can send `prompt_cache_key` and `prompt_cache_retention: 24h` for long retention on direct OpenAI hosts; `cacheRead` maps from cached token usage while `cacheWrite` stays 0.",
            "compatibility": "Works best with stable prompt prefixes and cache-TTL pruning; current docs note boundary-aware shaping for Codex Responses.",
            "risk": "Cache metrics can be misread because OpenAI lacks a separate cache-write counter and behavior may plateau by prefix size.",
            "safe_recommendation": "Prefer measurement via `/status`/usage artifacts before tuning; do not assume `cacheWrite=0` means no cache construction.",
        },
        {
            "surface": "Telemetry / OpenTelemetry",
            "current_state": "Diagnostics can export OTLP/HTTP metrics, traces, and logs through `diagnostics-otel`; raw content capture is off by default.",
            "compatibility": "Available as an official plugin path for model usage, cost, duration, message flow, queues, exec, and context metrics.",
            "risk": "Requires plugin/config changes and approved collector/privacy posture; content capture can leak prompts/tool data if enabled.",
            "safe_recommendation": "Do not enable here; prepare a separate privacy-reviewed telemetry packet if Randall wants live observability.",
        },
    ]


def recommendations() -> list[dict[str, str]]:
    return [
        {"priority": "high", "recommendation": "Keep OpenClaw 2026.5.4 and bundled SDKs pinned; do not run npm/package upgrades from this lane."},
        {"priority": "high", "recommendation": "Before any OpenAI route change, verify provider/model/runtime separately: provider prefix, backend model, auth method, and agent runtime are independent layers."},
        {"priority": "high", "recommendation": "Do not enable Gateway `/v1/chat/completions` or `/v1/responses` without a separate owner-approved config/security packet; both are operator-access surfaces."},
        {"priority": "medium", "recommendation": "For cache work, measure `cacheRead` and latency over repeated same-prefix turns; do not treat OpenAI `cacheWrite=0` as a failure signal."},
        {"priority": "medium", "recommendation": "If telemetry is desired, use diagnostics-otel with captureContent disabled first, approved collector retention, and no prompt/tool content export by default."},
        {"priority": "medium", "recommendation": "For native Codex runtime evaluation, build a separate reversible config proposal using `config.schema.lookup`, backups, route proof, and rollback."},
    ]


def runtime_gateway_evaluation() -> list[dict[str, str]]:
    return [
        {
            "option": "Current `openai-codex/*` through PI",
            "model_runtime_shape": "Provider/model ref selects `openai-codex`; default PI harness executes the agent loop unless a different runtime is explicitly selected.",
            "auth_and_billing": "ChatGPT/Codex OAuth/subscription route, not direct OpenAI API-key billing.",
            "fit": "Best no-change baseline for the current workspace default model policy.",
            "change_required": "None for status quo.",
            "primary_risk": "Confusing this with native Codex app-server runtime; enabling the Codex plugin alone does not move `openai-codex/*` off PI.",
            "verification": "Session `/status` or `openclaw models status` should show the selected model; native runtime is not proven unless runtime reports OpenAI Codex.",
        },
        {
            "option": "Direct OpenAI Responses route (`openai/*` via PI)",
            "model_runtime_shape": "Provider/model ref selects `openai`; PI harness calls the OpenAI Responses transport for modern OpenAI models.",
            "auth_and_billing": "Requires OpenAI Platform API-key auth or explicit provider config; usage-based API billing is separate from Codex subscription.",
            "fit": "Good for direct OpenAI API features, server-side compaction, and API-key controlled environments.",
            "change_required": "Config/model/auth change only after approval; no Gateway endpoint enablement is needed for internal PI use.",
            "primary_risk": "Accidentally shifting spend/auth from subscription OAuth to API-key billing or assuming `openai/*` means Codex subscription without runtime override.",
            "verification": "Use config-schema lookup, models status/check, a non-sensitive smoke turn, and usage/status inspection; do not expose API keys in logs.",
        },
        {
            "option": "Native Codex app-server runtime (`openai/*` + `agentRuntime.id: codex`)",
            "model_runtime_shape": "Provider/model ref stays `openai/gpt-5.5`; `agents.defaults.agentRuntime.id` selects Codex app-server harness.",
            "auth_and_billing": "Uses explicit OpenClaw `openai-codex` auth profile first, then local Codex app-server account, with limited local env fallback only when no account exists.",
            "fit": "Docs call this the recommended subscription-native Codex setup for most users who want Codex behavior.",
            "change_required": "Separate approved config packet: enable bundled codex plugin if needed, set primary model to `openai/gpt-5.5`, set `agentRuntime.id: codex`, validate, and use new/reset sessions.",
            "primary_risk": "Runtime/config mutation and auth-path changes; existing sessions may keep their recorded harness until reset/new session.",
            "verification": "`/status` should report Runtime: OpenAI Codex; `/codex status` or `/codex models` can verify app-server controls after Gateway is running.",
        },
        {
            "option": "Gateway OpenAI-compatible `/v1` endpoints",
            "model_runtime_shape": "External HTTP clients hit Gateway; `model` is an OpenClaw agent target (`openclaw/default`), while `x-openclaw-model` can override backend provider/model.",
            "auth_and_billing": "Uses Gateway auth; bearer token/password is full operator access, not a narrow OpenAI API key scope.",
            "fit": "Compatibility layer for Open WebUI/LobeChat/LibreChat, RAG clients, embeddings, Chat Completions, and OpenResponses-style clients.",
            "change_required": "Separate owner-approved security/config packet to enable `gateway.http.endpoints.chatCompletions.enabled` and/or `gateway.http.endpoints.responses.enabled`.",
            "primary_risk": "Operator-access exposure if bound beyond loopback/private ingress or if token/password leaks; URL file/image fetch policy for Responses needs careful review.",
            "verification": "Loopback-only smoke: `/v1/models` returns `openclaw/default`; endpoint auth/rate limits/private-ingress assumptions are documented; no public exposure.",
        },
    ]


def config_change_packet_requirements() -> list[dict[str, Any]]:
    common = [
        "explicit Randall approval for exact scope",
        "config.schema.lookup evidence for every config path before patching",
        "pre-change backup of OpenClaw config and relevant agent models/auth metadata without printing secrets",
        "semantic diff / patch preview with no credentials or bearer tokens exposed",
        "rollback command or restore path",
        "post-change validation and session reset/new-session note when runtime changes",
    ]
    return [
        {
            "packet": "Native Codex runtime migration",
            "paths": ["plugins.entries.codex.enabled", "agents.defaults.model.primary", "agents.defaults.agentRuntime.id", "agents.defaults.models allowlist if active"],
            "required_contents": common + [
                "auth proof that `openai-codex` profile or Codex app-server account is available, redacted",
                "confirmation that `openai-codex/*` PI fallback remains intentionally allowed or removed from default policy",
                "runtime proof from `/status` after a new/reset session showing Runtime: OpenAI Codex",
            ],
        },
        {
            "packet": "Direct OpenAI Responses route",
            "paths": ["agents.defaults.model.primary", "agents.defaults.models", "models.providers.openai or env-backed OPENAI_API_KEY posture"],
            "required_contents": common + [
                "billing/auth acceptance that direct OpenAI API-key usage is intended",
                "model availability proof from `openclaw models status --check` or equivalent",
                "non-sensitive smoke turn and usage/status check",
            ],
        },
        {
            "packet": "Gateway `/v1/chat/completions` and/or `/v1/responses` enablement",
            "paths": ["gateway.http.endpoints.chatCompletions.enabled", "gateway.http.endpoints.responses.enabled", "gateway.auth.*", "gateway host/bind/remote-access posture"],
            "required_contents": common + [
                "operator-access risk acceptance and loopback/private-ingress-only network proof",
                "auth mode/token/password/trusted-proxy decision with redaction",
                "Responses URL/file/image policy decision: allowUrl, allowlists, size limits, redirects, timeouts",
                "loopback smoke for `/v1/models` and chosen endpoint; no public internet exposure",
            ],
        },
    ]


def security_stop_lines() -> list[str]:
    return [
        "Do not mutate `~/.openclaw/openclaw.json`, auth stores, plugins, runtime defaults, packages, Gateway endpoint flags, service lifecycle, or credentials from this report-only lane.",
        "Do not print or collect API keys, OAuth tokens, Gateway tokens/passwords, auth-profile secrets, or bearer headers.",
        "Do not enable Gateway `/v1` endpoints without explicit owner approval; docs classify them as full operator-access surfaces.",
        "Do not expose Gateway `/v1` endpoints directly to the public internet; require loopback, tailnet, or private trusted ingress plus auth review.",
        "Do not treat `openai-codex/*`, `openai/*`, and `agentRuntime.id: codex` as interchangeable; provider, model, auth, and runtime are separate layers.",
        "Do not infer live finance/trading/account authority from any model/runtime/Gateway compatibility result.",
    ]


def validation_checklist() -> list[dict[str, str]]:
    return [
        {"gate": "artifact integrity", "check": "JSON and Markdown artifacts regenerate from local docs/dist only and validate cleanly."},
        {"gate": "source evidence", "check": "All evidence pointers resolve to installed OpenClaw package files; missing evidence is a failure."},
        {"gate": "no mutation", "check": "Validator does not read/write config unless future approved packet explicitly scopes it; this script writes only tmp artifacts with --write."},
        {"gate": "route clarity", "check": "Each option names provider/model/runtime/auth separately and labels current status quo vs proposed change."},
        {"gate": "Gateway safety", "check": "Any endpoint enablement packet includes operator-access warning, auth mode, network binding, and loopback/private-ingress proof."},
        {"gate": "runtime proof", "check": "Native Codex cannot be claimed until a new/reset session reports Runtime: OpenAI Codex."},
    ]


def build_report() -> dict[str, Any]:
    pkg = package_state()
    generated_at = datetime.now(ZoneInfo("America/Phoenix")).isoformat(timespec="seconds")
    return {
        "generated_at": generated_at,
        "title": "OpenAI / OpenClaw SDK and Provider Compatibility Matrix",
        "scope": "OpenClaw 2026.5.4 local package, bundled OpenAI-family provider docs/dist code, cache knobs, telemetry availability, and safe enhancement recommendations.",
        "authority": NO_AUTHORITY,
        "package_state": pkg,
        "compatibility_matrix": compatibility_matrix(pkg),
        "safe_enhancement_recommendations": recommendations(),
        "runtime_gateway_evaluation": runtime_gateway_evaluation(),
        "config_change_packet_requirements": config_change_packet_requirements(),
        "security_stop_lines": security_stop_lines(),
        "validation_checklist": validation_checklist(),
        "evidence": evidence(),
        "source_inventory": source_inventory(),
        "validation_expectations": [
            "Script performs local read-only inspection and writes only tmp/openai-provider-compat-matrix.json/.md when --write is supplied.",
            "No config, auth, package, runtime, gateway, plugin, credential, finance, or trading surfaces are mutated.",
            "External API calls are not made; all evidence comes from installed local package/docs/dist files.",
        ],
    }


def md_table(rows: list[dict[str, Any]]) -> str:
    lines = ["| Surface | Current state | Compatibility | Risk | Safe recommendation |", "|---|---|---|---|---|"]
    for row in rows:
        def cell(value: str) -> str:
            return value.replace("\n", " ").replace("|", "\\|")
        lines.append(
            f"| {cell(row['surface'])} | {cell(row['current_state'])} | {cell(row['compatibility'])} | {cell(row['risk'])} | {cell(row['safe_recommendation'])} |"
        )
    return "\n".join(lines)


def render_markdown(report: dict[str, Any]) -> str:
    pkg = report["package_state"]
    lines = [
        "# OpenAI / OpenClaw SDK and Provider Compatibility Matrix",
        "",
        f"Generated: {report['generated_at']} (America/Phoenix)",
        "",
        "## Boundary",
        "",
        "Report-only local inspection. No config/auth/runtime/package mutation, no secret collection, no external API calls, and no finance/trading authority.",
        "",
        "## Package state",
        "",
        f"- OpenClaw package version: `{pkg.get('openclaw_version')}`",
        f"- Declared OpenAI SDK dependency: `{pkg['declared_dependencies'].get('openai')}`",
        f"- Installed OpenAI SDK package: `{pkg['installed_versions'].get('openai')}`",
        f"- Installed Anthropic SDK package: `{pkg['installed_versions'].get('@anthropic-ai/sdk')}`",
        f"- Installed Google GenAI package: `{pkg['installed_versions'].get('@google/genai')}`",
        "",
        "## Compatibility matrix",
        "",
        md_table(report["compatibility_matrix"]),
        "",
        "## Safe enhancement recommendations",
        "",
    ]
    for item in report["safe_enhancement_recommendations"]:
        lines.append(f"- **{item['priority']}** - {item['recommendation']}")

    lines.extend(["", "## Runtime and Gateway endpoint evaluation", ""])
    for row in report["runtime_gateway_evaluation"]:
        lines.extend([
            f"### {row['option']}",
            "",
            f"- **Model/runtime shape:** {row['model_runtime_shape']}",
            f"- **Auth/billing:** {row['auth_and_billing']}",
            f"- **Fit:** {row['fit']}",
            f"- **Change required:** {row['change_required']}",
            f"- **Primary risk:** {row['primary_risk']}",
            f"- **Verification:** {row['verification']}",
            "",
        ])

    lines.extend(["", "## Exact config-change packet requirements", ""])
    for packet in report["config_change_packet_requirements"]:
        lines.extend([f"### {packet['packet']}", "", "Config paths:"])
        for path in packet["paths"]:
            lines.append(f"- `{path}`")
        lines.extend(["", "Required packet contents:"])
        for req in packet["required_contents"]:
            lines.append(f"- {req}")
        lines.append("")

    lines.extend(["", "## Security stop lines", ""])
    for stop in report["security_stop_lines"]:
        lines.append(f"- {stop}")

    lines.extend(["", "## Non-mutating local compatibility validator checklist", ""])
    for item in report["validation_checklist"]:
        lines.append(f"- **{item['gate']}** - {item['check']}")

    lines.extend(["", "## Evidence pointers", ""])
    for key, ev in report["evidence"].items():
        line = ev.get("line")
        loc = f"{ev.get('path')}:{line}" if line else f"{ev.get('path')}:NOT_FOUND"
        lines.append(f"- `{key}` - {loc} - {ev.get('snippet')}")
    lines.extend([
        "",
        "## Validation expectations",
        "",
    ])
    for val in report["validation_expectations"]:
        lines.append(f"- {val}")
    lines.append("")
    return "\n".join(lines)


def validate_report(report: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    auth = report.get("authority", {})
    for key in [
        "config_mutation_allowed",
        "auth_mutation_allowed",
        "package_install_allowed",
        "runtime_mutation_allowed",
        "secret_collection_allowed",
        "external_api_calls_performed",
        "portfolio_or_trading_authority",
    ]:
        if auth.get(key) is not False:
            errors.append(f"authority.{key} must be false")
    if auth.get("report_only") is not True:
        errors.append("authority.report_only must be true")
    if report.get("package_state", {}).get("openclaw_version") != "2026.5.4":
        errors.append("expected OpenClaw package version 2026.5.4")
    if not report.get("compatibility_matrix"):
        errors.append("compatibility_matrix is empty")
    for section in ["runtime_gateway_evaluation", "config_change_packet_requirements", "security_stop_lines", "validation_checklist"]:
        if not report.get(section):
            errors.append(f"{section} is empty")
    stop_text = "\n".join(report.get("security_stop_lines", []))
    for required in ["Do not mutate", "Do not print or collect", "full operator-access"]:
        if required not in stop_text:
            errors.append(f"security stop lines missing: {required}")
    evidence_map = report.get("evidence", {})
    missing = [key for key, value in evidence_map.items() if value.get("line") is None]
    if missing:
        errors.append("missing evidence lines: " + ", ".join(missing))
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true", help="write tmp/openai-provider-compat-matrix.json/.md")
    parser.add_argument("--validate-only", action="store_true", help="validate existing artifacts instead of regenerating")
    args = parser.parse_args()

    if args.validate_only:
        report = read_json(JSON_OUT)
        if not report:
            print(f"missing report: {JSON_OUT}")
            return 1
        errors = validate_report(report)
        if errors:
            print("validation failed:")
            for err in errors:
                print(f"- {err}")
            return 1
        print(f"validation ok: {JSON_OUT}")
        return 0

    report = build_report()
    errors = validate_report(report)
    if errors:
        print("validation failed:")
        for err in errors:
            print(f"- {err}")
        return 1

    if args.write:
        TMP.mkdir(parents=True, exist_ok=True)
        JSON_OUT.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        MD_OUT.write_text(render_markdown(report), encoding="utf-8")
        print(f"wrote {JSON_OUT}")
        print(f"wrote {MD_OUT}")
    else:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
