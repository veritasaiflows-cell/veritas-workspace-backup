#!/usr/bin/env python3
"""Report-only OpenClaw cache and prompt efficiency scorecard.

This script inspects workspace-owned prompt/context surfaces and optional
transcript/session JSON exports to identify cache-prefix stability risks,
bootstrap bloat, and old tool-result bloat. It writes review artifacts only under
`tmp/` and never mutates OpenClaw config, auth, runtime, transcripts, or notes.
"""
from __future__ import annotations

import argparse
import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
JSON_REPORT = TMP / "openclaw-cache-efficiency-scorecard.json"
MD_REPORT = TMP / "openclaw-cache-efficiency-scorecard.md"
REDACTED_TOOL_TELEMETRY_JSON = TMP / "redacted-tool-result-telemetry.json"
REDACTED_TOOL_TELEMETRY_MD = TMP / "redacted-tool-result-telemetry.md"

BOOTSTRAP_FILES = [
    "AGENTS.md",
    "SOUL.md",
    "TOOLS.md",
    "IDENTITY.md",
    "USER.md",
    "HEARTBEAT.md",
    "BOOTSTRAP.md",
    "MEMORY.md",
]
STABLE_PREFIX_FILES = ["AGENTS.md", "SOUL.md", "TOOLS.md", "IDENTITY.md", "USER.md", "BOOTSTRAP.md", "MEMORY.md"]
VOLATILE_PATTERN = re.compile(
    r"\b(today|yesterday|tomorrow|current date|current time|right now|latest available|as of now)\b",
    re.IGNORECASE,
)
TOKEN_DIVISOR = 4
DEFAULT_BOOTSTRAP_FILE_CAP_CHARS = 12_000
DEFAULT_BOOTSTRAP_TOTAL_CAP_CHARS = 60_000
TOOL_RESULT_SOFT_WARN_CHARS = 8_000
TOOL_RESULT_HARD_WARN_CHARS = 20_000
BOOTSTRAP_LARGE_FILE_WARN_CHARS = 10_000


@dataclass
class FileScore:
    path: str
    exists: bool
    chars: int = 0
    approx_tokens: int = 0
    truncated_by_default_file_cap: bool = False
    cache_prefix_role: str = "unknown"
    warnings: list[str] | None = None


@dataclass
class ToolResultScore:
    source: str
    index: int
    chars: int
    approx_tokens: int
    locator: str
    severity: str
    tool_name: str
    target: str
    preview: str
    recommendation: str


@dataclass
class RepeatedReadScore:
    target: str
    occurrences: int
    total_chars: int
    approx_total_tokens: int
    largest_chars: int
    sources: list[str]
    recommendation: str


@dataclass
class TranscriptToolEvent:
    source: str
    locator: str
    tool_name: str
    target: str
    text: str
    status: str = "unknown"
    duration_ms: int | None = None
    truncated: bool | None = None


@dataclass
class RedactedToolTelemetry:
    source: str
    locator: str
    tool_name: str
    status: str
    duration_ms: int | None
    output_chars: int
    approx_tokens: int
    target_redacted: str
    path_category: str
    truncated: bool
    severity: str
    recommendation: str




def discover_latest_main_session_transcript() -> Path | None:
    """Return the newest main-session transcript path when OpenClaw stores one locally.

    Read-only discovery only. This does not inspect auth/config state and does not
    mutate sessions or transcripts.
    """
    sessions_dir = Path.home() / ".openclaw" / "agents" / "main" / "sessions"
    if not sessions_dir.exists():
        return None
    candidates = [path for path in sessions_dir.glob("*.jsonl") if path.is_file()]
    if not candidates:
        return None
    return max(candidates, key=lambda path: path.stat().st_mtime)


def resolve_transcript_paths(paths: list[Path], include_latest_main: bool = False) -> list[Path]:
    resolved: list[Path] = []
    seen: set[Path] = set()
    for path in paths:
        candidate = path.resolve()
        if candidate not in seen:
            resolved.append(candidate)
            seen.add(candidate)
    if include_latest_main:
        latest = discover_latest_main_session_transcript()
        if latest is not None:
            candidate = latest.resolve()
            if candidate not in seen:
                resolved.append(candidate)
                seen.add(candidate)
    return resolved


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def approx_tokens(chars: int) -> int:
    return max(1, round(chars / TOKEN_DIVISOR)) if chars else 0


def rel(path: Path, root: Path = ROOT) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return str(path)


def read_text_len(path: Path) -> tuple[int, str]:
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return 0, ""
    return len(text), text


def score_bootstrap_files(root: Path) -> list[FileScore]:
    scores: list[FileScore] = []
    for name in BOOTSTRAP_FILES:
        path = root / name
        role = "volatile_suffix" if name == "HEARTBEAT.md" else "stable_prefix_candidate"
        if not path.exists():
            scores.append(FileScore(path=name, exists=False, cache_prefix_role=role, warnings=["missing/no injection cost"]))
            continue
        chars, text = read_text_len(path)
        warnings: list[str] = []
        if chars >= BOOTSTRAP_LARGE_FILE_WARN_CHARS:
            warnings.append("large bootstrap file; likely consumes most or all of the default per-file cap")
        if name in STABLE_PREFIX_FILES and VOLATILE_PATTERN.search(text):
            warnings.append("contains time-sensitive wording in a stable-prefix candidate; verify it is durable doctrine, not per-turn status")
        if "OPENCLAW_CACHE_BOUNDARY" in text:
            warnings.append("contains explicit cache-boundary marker; inspect placement if cache hit rate regresses")
        scores.append(
            FileScore(
                path=name,
                exists=True,
                chars=chars,
                approx_tokens=approx_tokens(chars),
                truncated_by_default_file_cap=chars > DEFAULT_BOOTSTRAP_FILE_CAP_CHARS,
                cache_prefix_role=role,
                warnings=warnings,
            )
        )
    return scores


def count_workspace_skill_metadata(root: Path) -> dict[str, Any]:
    skill_dirs = [root / "skills", root / "plugin-skills"]
    names: list[str] = []
    total_skill_md_chars = 0
    for base in skill_dirs:
        if not base.exists():
            continue
        for skill_file in sorted(base.glob("*/SKILL.md")):
            names.append(skill_file.parent.name)
            chars, _ = read_text_len(skill_file)
            total_skill_md_chars += chars
    return {
        "workspace_skill_count": len(names),
        "workspace_skill_names": names,
        "skill_md_total_chars_not_prompt_injected": total_skill_md_chars,
        "note": "OpenClaw injects bounded skill metadata by default; full SKILL.md text is loaded on demand.",
    }


def stringify_result(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        parts: list[str] = []
        for item in value:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                for key in ["text", "content", "result", "output"]:
                    if isinstance(item.get(key), str):
                        parts.append(item[key])
                        break
                else:
                    parts.append(json.dumps(item, ensure_ascii=False, sort_keys=True))
            else:
                parts.append(str(item))
        return "\n".join(parts)
    if value is None:
        return ""
    return json.dumps(value, ensure_ascii=False, sort_keys=True) if isinstance(value, dict) else str(value)


def infer_tool_name(node: dict[str, Any], roleish: str) -> str:
    for key in ["tool", "tool_name", "toolName", "name", "function", "function_name"]:
        value = node.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
        if isinstance(value, dict) and isinstance(value.get("name"), str):
            return value["name"].strip()
    if "tool" in roleish:
        return "tool"
    if "function" in roleish:
        return "function"
    return "unknown"


def infer_target(node: dict[str, Any], text: str) -> str:
    for arg_key in ["input", "args", "arguments", "parameters", "request"]:
        args = node.get(arg_key)
        if isinstance(args, dict):
            for key in ["path", "file", "url", "query", "command"]:
                value = args.get(key)
                if isinstance(value, str) and value.strip():
                    return value.strip()
        elif isinstance(args, str) and args.strip():
            try:
                parsed = json.loads(args)
                if isinstance(parsed, dict):
                    for key in ["path", "file", "url", "query", "command"]:
                        value = parsed.get(key)
                        if isinstance(value, str) and value.strip():
                            return value.strip()
            except json.JSONDecodeError:
                if len(args) < 260:
                    return args.strip()
    match = re.search(r"(?:path|file|url|query|command)['\" ]*[:=]['\" ]+([^'\"\n|]{3,260})", text[:1000], re.IGNORECASE)
    return match.group(1).strip() if match else "unknown"


def infer_status(node: dict[str, Any]) -> str:
    for key in ["status", "state", "exit_status", "exitStatus", "result_status"]:
        value = node.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip().lower()[:80]
    for key in ["ok", "success", "succeeded"]:
        value = node.get(key)
        if isinstance(value, bool):
            return "success" if value else "failed"
    for key in ["is_error", "isError", "error"]:
        value = node.get(key)
        if isinstance(value, bool):
            return "error" if value else "success"
        if isinstance(value, str) and value.strip():
            return "error"
    for key in ["exit_code", "exitCode", "code"]:
        value = node.get(key)
        if isinstance(value, int):
            return "success" if value == 0 else f"exit_{value}"
    return "unknown"


def infer_duration_ms(node: dict[str, Any]) -> int | None:
    for key in ["duration_ms", "durationMs", "elapsed_ms", "elapsedMs", "latency_ms", "latencyMs"]:
        value = node.get(key)
        if isinstance(value, (int, float)) and value >= 0:
            return round(value)
    for key in ["duration", "elapsed", "latency"]:
        value = node.get(key)
        if isinstance(value, (int, float)) and value >= 0:
            return round(value * 1000) if value < 10_000 else round(value)
        if isinstance(value, str):
            match = re.fullmatch(r"\s*(\d+(?:\.\d+)?)\s*(ms|s|sec|seconds)?\s*", value, re.IGNORECASE)
            if match:
                amount = float(match.group(1))
                unit = (match.group(2) or "ms").lower()
                return round(amount * 1000) if unit.startswith("s") else round(amount)
    return None


def infer_truncated(node: dict[str, Any], text: str) -> bool | None:
    for key in ["truncated", "is_truncated", "isTruncated", "was_truncated", "wasTruncated"]:
        value = node.get(key)
        if isinstance(value, bool):
            return value
    if re.search(r"\[\.\.\.\s*\d+\s+more characters truncated\]", text, re.IGNORECASE):
        return True
    return None


def looks_like_tool_result(node: dict[str, Any], roleish: str) -> bool:
    if any(term in roleish for term in ["tool", "function"]):
        return True
    return any(key in node for key in ["toolResult", "tool_result", "toolUseResult", "function_result"])


def iter_jsonish_tool_events(node: Any, source: str, locator: str = "$", found: list[TranscriptToolEvent] | None = None) -> list[TranscriptToolEvent]:
    """Find likely tool-result text blocks in OpenClaw or provider transcript JSON shapes."""
    if found is None:
        found = []
    if isinstance(node, dict):
        lower_key_map = {str(k).lower(): k for k in node}
        roleish = str(node.get(lower_key_map.get("role", "role"), node.get(lower_key_map.get("type", "type"), node.get(lower_key_map.get("kind", "kind"), "")))).lower()
        if looks_like_tool_result(node, roleish):
            for key in ["content", "result", "output", "text", "message", "toolResult", "tool_result", "toolUseResult", "function_result"]:
                real_key = lower_key_map.get(key.lower(), key)
                if real_key in node:
                    text = stringify_result(node[real_key]).strip()
                    if text:
                        found.append(
                            TranscriptToolEvent(
                                source,
                                f"{locator}.{real_key}",
                                infer_tool_name(node, roleish),
                                infer_target(node, text),
                                text,
                                infer_status(node),
                                infer_duration_ms(node),
                                infer_truncated(node, text),
                            )
                        )
                        break
        for key, value in node.items():
            iter_jsonish_tool_events(value, source, f"{locator}.{key}", found)
    elif isinstance(node, list):
        for idx, value in enumerate(node):
            iter_jsonish_tool_events(value, source, f"{locator}[{idx}]", found)
    return found


def iter_jsonish_tool_results(node: Any, source: str, locator: str = "$", found: list[tuple[str, str]] | None = None) -> list[tuple[str, str]]:
    """Backward-compatible tuple view for older tests/imports."""
    return [(event.locator, event.text) for event in iter_jsonish_tool_events(node, source, locator)]


def parse_text_tool_markers(text: str) -> list[tuple[str, str]]:
    markers: list[tuple[str, str]] = []
    pattern = re.compile(r"(?is)(tool(?:_| )?(?:result|output)|function(?:_| )?result)[:\n]+(.{200,}?)(?=\n\s*(?:assistant|user|tool|function)[:\n]|\Z)")
    for idx, match in enumerate(pattern.finditer(text)):
        markers.append((f"text_marker[{idx}]", match.group(2).strip()))
    return markers


def parse_text_tool_events(text: str, source: str) -> list[TranscriptToolEvent]:
    return [TranscriptToolEvent(source, locator, "unknown", "unknown", result) for locator, result in parse_text_tool_markers(text)]


def tool_result_recommendation(event: TranscriptToolEvent, chars: int) -> str:
    tool = event.tool_name.lower()
    if tool == "read" or event.target.lower().endswith(('.md', '.txt', '.json', '.html', '.csv')):
        return "Use a smaller read offset/limit or a targeted search/excerpt; avoid re-reading the full file after the useful locator is known."
    if tool in {"exec", "shell", "process"}:
        return "Constrain command output, redirect large artifacts to files, then read only targeted excerpts."
    if tool in {"web_search", "web_fetch", "search"}:
        return "Fetch fewer results or lower extraction limits; preserve URLs/provenance and summarize only decision-relevant excerpts."
    return "Keep the raw artifact on disk and bring only bounded, task-relevant excerpts back into chat."


SECRETISH_PATTERN = re.compile(
    r"(?i)(api[_-]?key|authorization|bearer\s+[a-z0-9._~+/=-]+|token|secret|password|credential|oauth|encrypted_content)"
)


def safe_preview(text: str, max_chars: int = 220) -> str:
    """Return a bounded preview that avoids carrying obvious secret-bearing text into reports."""
    preview = " ".join(text[:max_chars].split())
    if SECRETISH_PATTERN.search(preview):
        return "[redacted: preview matched secret/credential-like text]"
    return preview


def redact_secretish(value: str, max_chars: int = 220) -> str:
    """Bound and redact a target/locator-like value before writing telemetry artifacts."""
    if not value or value == "unknown":
        return "unknown"
    compact = " ".join(value[:max_chars].split())
    if SECRETISH_PATTERN.search(compact):
        return "[redacted: target matched secret/credential-like text]"
    compact = re.sub(r"(?i)([?&](?:token|api[_-]?key|key|secret|password|code)=)[^&\s]+", r"\1[redacted]", compact)
    return compact


def path_category(target: str, root: Path = ROOT) -> str:
    low = target.lower().strip()
    if not low or low == "unknown":
        return "unknown"
    if low.startswith(("http://", "https://")):
        return "external_url"
    if re.search(r"\b(rg|python|node|openclaw|git|sqlite3|Get-ChildItem|Select-String)\b", target):
        return "command_or_query"
    try:
        path = Path(target)
        candidate = path if path.is_absolute() else root / path
        resolved = candidate.resolve(strict=False)
        root_resolved = root.resolve(strict=False)
        if resolved == root_resolved or root_resolved in resolved.parents:
            rel_target = resolved.relative_to(root_resolved).as_posix()
            if rel_target.startswith("tmp/"):
                return "workspace_tmp"
            if rel_target.startswith("memory/"):
                return "workspace_memory"
            if rel_target.startswith("scripts/"):
                return "workspace_script"
            return "workspace_file"
        if path.is_absolute():
            return "absolute_outside_workspace"
    except OSError:
        pass
    if re.search(r"\.(md|txt|json|jsonl|csv|html|py|ps1)$", target, re.IGNORECASE):
        return "relative_file_unknown_root"
    return "query_or_text"


def severity_for_chars(chars: int) -> str:
    if chars >= TOOL_RESULT_HARD_WARN_CHARS:
        return "high"
    if chars >= TOOL_RESULT_SOFT_WARN_CHARS:
        return "medium"
    return "low"


def load_transcript_tool_events(source_path: Path) -> list[TranscriptToolEvent]:
    """Load tool events from JSON, JSONL, or text transcript/session exports."""
    source = source_path.as_posix()
    raw = source_path.read_text(encoding="utf-8", errors="ignore")
    try:
        parsed = json.loads(raw)
        return iter_jsonish_tool_events(parsed, source)
    except json.JSONDecodeError:
        pass

    events: list[TranscriptToolEvent] = []
    jsonl_decode_failed = False
    for line_no, line in enumerate(raw.splitlines(), start=1):
        stripped = line.strip()
        if not stripped:
            continue
        if not stripped.startswith(("{", "[")):
            jsonl_decode_failed = True
            break
        try:
            parsed_line = json.loads(stripped)
        except json.JSONDecodeError:
            jsonl_decode_failed = True
            break
        events.extend(iter_jsonish_tool_events(parsed_line, source, f"$line[{line_no}]"))
    if events or not jsonl_decode_failed:
        return events
    return parse_text_tool_events(raw, source)


def score_tool_results(paths: Iterable[Path]) -> list[ToolResultScore]:
    scores: list[ToolResultScore] = []
    for source_path in paths:
        if not source_path.exists() or not source_path.is_file():
            continue
        events = load_transcript_tool_events(source_path)
        for idx, event in enumerate(events):
            text = event.text
            chars = len(text)
            if chars < TOOL_RESULT_SOFT_WARN_CHARS:
                continue
            severity = "high" if chars >= TOOL_RESULT_HARD_WARN_CHARS else "medium"
            scores.append(
                ToolResultScore(
                    source=source_path.as_posix(),
                    index=idx,
                    chars=chars,
                    approx_tokens=approx_tokens(chars),
                    locator=event.locator,
                    severity=severity,
                    tool_name=event.tool_name,
                    target=event.target,
                    preview=safe_preview(text),
                    recommendation=tool_result_recommendation(event, chars),
                )
            )
    return sorted(scores, key=lambda item: item.chars, reverse=True)


def build_redacted_tool_telemetry(root: Path, transcript_paths: list[Path]) -> dict[str, Any]:
    """Build a body-free, secret-redacted summary of tool-result events."""
    events: list[RedactedToolTelemetry] = []
    for source_path in transcript_paths:
        if not source_path.exists() or not source_path.is_file():
            continue
        for event in load_transcript_tool_events(source_path):
            chars = len(event.text)
            truncated = bool(event.truncated) or chars >= TOOL_RESULT_HARD_WARN_CHARS
            events.append(
                RedactedToolTelemetry(
                    source=redact_secretish(source_path.as_posix(), 260),
                    locator=redact_secretish(event.locator, 180),
                    tool_name=redact_secretish(event.tool_name, 80),
                    status=redact_secretish(event.status, 80),
                    duration_ms=event.duration_ms,
                    output_chars=chars,
                    approx_tokens=approx_tokens(chars),
                    target_redacted=redact_secretish(event.target, 220),
                    path_category=path_category(event.target, root),
                    truncated=truncated,
                    severity=severity_for_chars(chars),
                    recommendation=tool_result_recommendation(event, chars),
                )
            )
    events_sorted = sorted(events, key=lambda item: item.output_chars, reverse=True)
    by_tool: dict[str, dict[str, Any]] = {}
    by_category: dict[str, dict[str, Any]] = {}
    for item in events_sorted:
        tool_bucket = by_tool.setdefault(item.tool_name, {"count": 0, "total_output_chars": 0, "max_output_chars": 0})
        tool_bucket["count"] += 1
        tool_bucket["total_output_chars"] += item.output_chars
        tool_bucket["max_output_chars"] = max(tool_bucket["max_output_chars"], item.output_chars)
        cat_bucket = by_category.setdefault(item.path_category, {"count": 0, "total_output_chars": 0, "max_output_chars": 0})
        cat_bucket["count"] += 1
        cat_bucket["total_output_chars"] += item.output_chars
        cat_bucket["max_output_chars"] = max(cat_bucket["max_output_chars"], item.output_chars)
    return {
        "generated_at_utc": utc_now(),
        "report_only": True,
        "mutations_performed": False,
        "authority_boundary": "No config/auth/runtime mutation, no canon mutation, no approval or execution authority.",
        "redaction_contract": "No raw tool-result bodies are exported. Target/source/locator fields are bounded and secret-like strings are redacted before writing.",
        "transcripts_scanned": [redact_secretish(path.as_posix(), 260) for path in transcript_paths],
        "events_count": len(events_sorted),
        "events_with_medium_or_high_output": sum(1 for item in events_sorted if item.severity in {"medium", "high"}),
        "events_truncated_or_hard_warn": sum(1 for item in events_sorted if item.truncated),
        "summary_by_tool": by_tool,
        "summary_by_path_category": by_category,
        "events": [asdict(item) for item in events_sorted],
    }


def render_redacted_tool_telemetry_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Redacted Tool-Result Telemetry",
        "",
        f"Generated: `{report['generated_at_utc']}`",
        "",
        "## Boundary",
        "",
        f"- report_only: `{report['report_only']}`",
        f"- mutations_performed: `{report['mutations_performed']}`",
        f"- authority: {report['authority_boundary']}",
        f"- redaction: {report['redaction_contract']}",
        "",
        "## Summary",
        "",
        f"- Transcripts scanned: `{len(report['transcripts_scanned'])}`",
        f"- Tool-result events: `{report['events_count']}`",
        f"- Medium/high output events: `{report['events_with_medium_or_high_output']}`",
        f"- Truncated or hard-warn events: `{report['events_truncated_or_hard_warn']}`",
        "",
        "## By tool",
        "",
        "| Tool | Count | Total output chars | Max output chars |",
        "|---|---:|---:|---:|",
    ]
    for tool, item in sorted(report["summary_by_tool"].items(), key=lambda pair: pair[1]["total_output_chars"], reverse=True):
        lines.append(f"| `{tool}` | {item['count']} | {item['total_output_chars']} | {item['max_output_chars']} |")
    lines.extend(["", "## By path category", "", "| Category | Count | Total output chars | Max output chars |", "|---|---:|---:|---:|"])
    for category, item in sorted(report["summary_by_path_category"].items(), key=lambda pair: pair[1]["total_output_chars"], reverse=True):
        lines.append(f"| `{category}` | {item['count']} | {item['total_output_chars']} | {item['max_output_chars']} |")
    lines.extend(["", "## Largest events (content-free)", "", "| Tool | Status | Duration ms | Output chars | Category | Target | Truncated | Recommendation |", "|---|---|---:|---:|---|---|---:|---|"])
    for item in report["events"][:25]:
        target = item["target_redacted"].replace("|", "\\|")
        recommendation = item["recommendation"].replace("|", "\\|")
        duration = "" if item["duration_ms"] is None else item["duration_ms"]
        lines.append(f"| `{item['tool_name']}` | `{item['status']}` | {duration} | {item['output_chars']} | `{item['path_category']}` | `{target}` | {item['truncated']} | {recommendation} |")
    lines.append("")
    return "\n".join(lines)


def write_redacted_tool_telemetry(report: dict[str, Any], json_path: Path = REDACTED_TOOL_TELEMETRY_JSON, md_path: Path | None = REDACTED_TOOL_TELEMETRY_MD) -> None:
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if md_path is not None:
        md_path.write_text(render_redacted_tool_telemetry_markdown(report), encoding="utf-8")


def score_repeated_large_reads(tool_scores: list[ToolResultScore], min_occurrences: int = 2) -> list[RepeatedReadScore]:
    grouped: dict[str, list[ToolResultScore]] = {}
    for item in tool_scores:
        if item.target == "unknown":
            continue
        if item.tool_name.lower() == "read" or re.search(r"\.(md|txt|json|html|csv)$", item.target, re.IGNORECASE):
            grouped.setdefault(item.target, []).append(item)
    repeated: list[RepeatedReadScore] = []
    for target, items in grouped.items():
        if len(items) < min_occurrences:
            continue
        total = sum(item.chars for item in items)
        repeated.append(
            RepeatedReadScore(
                target=target,
                occurrences=len(items),
                total_chars=total,
                approx_total_tokens=approx_tokens(total),
                largest_chars=max(item.chars for item in items),
                sources=sorted({item.source for item in items}),
                recommendation="After the first large read, switch to targeted offset/limit reads, rg/search locators, or a durable summary artifact instead of repeated whole-surface reads.",
            )
        )
    return sorted(repeated, key=lambda item: item.total_chars, reverse=True)


def score_tmp_artifact_bloat(root: Path) -> dict[str, Any]:
    tmp = root / "tmp"
    files: list[dict[str, Any]] = []
    if tmp.exists():
        for path in sorted(tmp.glob("*")):
            if path.is_file() and path.suffix.lower() in {".json", ".md", ".txt", ".html", ".csv"}:
                size = path.stat().st_size
                if size >= 100_000:
                    files.append({"path": rel(path, root), "bytes": size, "approx_tokens_if_read": approx_tokens(size)})
    return {
        "large_tmp_artifacts_count": len(files),
        "largest_tmp_artifacts": sorted(files, key=lambda item: item["bytes"], reverse=True)[:25],
        "note": "Large tmp artifacts are fine as files; avoid pasting/reading whole artifacts into chat unless needed.",
    }


def build_report(root: Path, transcript_paths: list[Path]) -> dict[str, Any]:
    bootstrap = score_bootstrap_files(root)
    existing_chars = sum(item.chars for item in bootstrap if item.exists)
    default_capped_chars = sum(min(item.chars, DEFAULT_BOOTSTRAP_FILE_CAP_CHARS) for item in bootstrap if item.exists)
    total_default_cap_pressure = default_capped_chars / DEFAULT_BOOTSTRAP_TOTAL_CAP_CHARS
    tool_scores = score_tool_results(transcript_paths)
    high_tool_results = [item for item in tool_scores if item.severity == "high"]
    recommendations: list[str] = []
    if total_default_cap_pressure >= 0.8:
        recommendations.append("Reduce or route large bootstrap surfaces; default capped bootstrap content is near the total cap.")
    if any(item.truncated_by_default_file_cap for item in bootstrap):
        recommendations.append("At least one bootstrap file exceeds the default per-file cap; keep top sections dense and route details to owner notes.")
    if high_tool_results:
        recommendations.append("Use bounded reads/excerpts and cache-ttl pruning for sessions with very large old tool results.")
    repeated_reads = score_repeated_large_reads(tool_scores)
    if repeated_reads:
        recommendations.append("Repeated large file reads detected; cache the locator/summary and use offset/limit reads or search on follow-up turns.")
    if not transcript_paths:
        recommendations.append("Pass one or more transcript/session JSON exports with --transcript path\\to\\session.json to measure actual tool-result bloat; if unavailable, run the synthetic fixture tests as the operator smoke path.")
    recommendations.append("Keep config/auth/runtime changes out of this report path; treat findings as review-only routing evidence.")
    return {
        "generated_at_utc": utc_now(),
        "report_only": True,
        "mutations_performed": False,
        "authority_boundary": "No config/auth/runtime mutation, no canon mutation, no approval or execution authority.",
        "root": str(root),
        "docs_basis": [
            "OpenClaw prompt-caching.md: stable prefix, cacheRetention, cache-ttl pruning, heartbeat keep-warm",
            "OpenClaw token-use.md: bootstrap files, caps, context/tool-result limits, usage counters",
            "OpenClaw session-pruning.md: old tool-result trimming and cache TTL behavior",
        ],
        "thresholds": {
            "token_divisor_chars_per_token": TOKEN_DIVISOR,
            "default_bootstrap_file_cap_chars": DEFAULT_BOOTSTRAP_FILE_CAP_CHARS,
            "default_bootstrap_total_cap_chars": DEFAULT_BOOTSTRAP_TOTAL_CAP_CHARS,
            "tool_result_soft_warn_chars": TOOL_RESULT_SOFT_WARN_CHARS,
            "tool_result_hard_warn_chars": TOOL_RESULT_HARD_WARN_CHARS,
        },
        "bootstrap": {
            "total_existing_chars": existing_chars,
            "approx_total_existing_tokens": approx_tokens(existing_chars),
            "default_capped_chars": default_capped_chars,
            "approx_default_capped_tokens": approx_tokens(default_capped_chars),
            "default_total_cap_pressure": round(total_default_cap_pressure, 3),
            "files": [asdict(item) for item in bootstrap],
        },
        "skills": count_workspace_skill_metadata(root),
        "tool_results": {
            "transcripts_scanned": [path.as_posix() for path in transcript_paths],
            "oversized_results_count": len(tool_scores),
            "high_severity_count": len(high_tool_results),
            "largest_results": [asdict(item) for item in tool_scores[:25]],
            "repeated_large_reads": [asdict(item) for item in repeated_reads[:25]],
            "transcript_format_support": "Scans JSON exports, OpenClaw session JSONL files, and plain-text transcripts with tool-result markers.",
            "operator_command_path": [
                "python scripts/openclaw_cache_efficiency_scorecard.py --write --transcript path\\to\\session.jsonl",
                "python scripts/openclaw_cache_efficiency_scorecard.py --write-redacted-tool-telemetry --transcript path\\to\\session.jsonl",
                "OpenClaw local session index: C:\\Users\\Veritas\\.openclaw\\agents\\main\\sessions\\sessions.json (read-only discovery; do not include auth-state files)",
                "python scripts/test_openclaw_cache_efficiency_scorecard.py",
            ],
        },
        "tmp_artifact_bloat": score_tmp_artifact_bloat(root),
        "recommendations": recommendations,
    }


def render_markdown(report: dict[str, Any]) -> str:
    bootstrap = report["bootstrap"]
    lines = [
        "# OpenClaw Cache Efficiency Scorecard",
        "",
        f"Generated: `{report['generated_at_utc']}`",
        "",
        "## Boundary",
        "",
        f"- report_only: `{report['report_only']}`",
        f"- mutations_performed: `{report['mutations_performed']}`",
        f"- authority: {report['authority_boundary']}",
        "",
        "## Bootstrap / stable-prefix pressure",
        "",
        f"- Existing bootstrap chars: `{bootstrap['total_existing_chars']}` (~`{bootstrap['approx_total_existing_tokens']}` tokens)",
        f"- Default-capped bootstrap chars: `{bootstrap['default_capped_chars']}` (~`{bootstrap['approx_default_capped_tokens']}` tokens)",
        f"- Default total cap pressure: `{bootstrap['default_total_cap_pressure']}`",
        "",
        "| File | Role | Chars | Approx tokens | Default cap truncates? | Warnings |",
        "|---|---:|---:|---:|---:|---|",
    ]
    for item in bootstrap["files"]:
        warnings = "; ".join(item.get("warnings") or [])
        lines.append(
            f"| `{item['path']}` | {item['cache_prefix_role']} | {item['chars']} | {item['approx_tokens']} | {item['truncated_by_default_file_cap']} | {warnings} |"
        )
    lines.extend(["", "## Skill metadata", ""])
    skills = report["skills"]
    lines.append(f"- Workspace skill count: `{skills['workspace_skill_count']}`")
    lines.append(f"- Full SKILL.md chars not prompt-injected by default: `{skills['skill_md_total_chars_not_prompt_injected']}`")
    lines.append(f"- Note: {skills['note']}")
    lines.extend(["", "## Tool-result bloat", ""])
    tool = report["tool_results"]
    lines.append(f"- Transcripts scanned: `{len(tool['transcripts_scanned'])}`")
    lines.append(f"- Oversized tool results: `{tool['oversized_results_count']}`")
    lines.append(f"- High severity tool results: `{tool['high_severity_count']}`")
    if tool.get("transcript_format_support"):
        lines.append(f"- Format support: {tool['transcript_format_support']}")
    if tool["largest_results"]:
        lines.extend(["", "| Source | Locator | Tool | Target | Severity | Chars | Recommendation | Preview |", "|---|---|---:|---|---:|---:|---|---|"])
        for item in tool["largest_results"][:10]:
            preview = item["preview"].replace("|", "\\|")
            recommendation = item["recommendation"].replace("|", "\\|")
            lines.append(f"| `{item['source']}` | `{item['locator']}` | {item['tool_name']} | `{item['target']}` | {item['severity']} | {item['chars']} | {recommendation} | {preview} |")
    if tool.get("repeated_large_reads"):
        lines.extend(["", "### Repeated large reads", "", "| Target | Occurrences | Total chars | Recommendation |", "|---|---:|---:|---|"])
        for item in tool["repeated_large_reads"][:10]:
            lines.append(f"| `{item['target']}` | {item['occurrences']} | {item['total_chars']} | {item['recommendation']} |")
    lines.extend(["", "### Operator command path", ""])
    for command in tool.get("operator_command_path", []):
        lines.append(f"- `{command}`")
    lines.extend(["", "## Large tmp artifacts", ""])
    tmp = report["tmp_artifact_bloat"]
    lines.append(f"- Large tmp artifacts count: `{tmp['large_tmp_artifacts_count']}`")
    for item in tmp["largest_tmp_artifacts"][:10]:
        lines.append(f"  - `{item['path']}`: `{item['bytes']}` bytes (~`{item['approx_tokens_if_read']}` tokens if fully read)")
    lines.extend(["", "## Recommendations", ""])
    for rec in report["recommendations"]:
        lines.append(f"- {rec}")
    lines.append("")
    return "\n".join(lines)


def write_reports(report: dict[str, Any], json_path: Path = JSON_REPORT, md_path: Path = MD_REPORT, write_md: bool = False) -> None:
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if write_md:
        md_path.write_text(render_markdown(report), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate a report-only OpenClaw cache/prompt efficiency scorecard.")
    parser.add_argument("--root", type=Path, default=ROOT, help="Workspace root to inspect. Defaults to this script's workspace root.")
    parser.add_argument("--transcript", type=Path, action="append", default=[], help="Optional transcript/session JSON or text file to scan for tool-result bloat. May be repeated.")
    parser.add_argument("--latest-main-session", action="store_true", help="Also scan the newest local main-session JSONL transcript, read-only, when available.")
    parser.add_argument("--write", action="store_true", help="Write tmp/openclaw-cache-efficiency-scorecard.json")
    parser.add_argument("--write-md", action="store_true", help="Also write legacy human-readable Markdown scorecard/telemetry sidecars")
    parser.add_argument("--write-redacted-tool-telemetry", action="store_true", help="Write tmp/redacted-tool-result-telemetry.json with body-free redacted tool-result summaries.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = args.root.resolve()
    transcript_paths = resolve_transcript_paths(args.transcript, include_latest_main=args.latest_main_session)
    report = build_report(root, transcript_paths)
    wrote_any = False
    if args.write:
        write_reports(report, root / "tmp" / JSON_REPORT.name, root / "tmp" / MD_REPORT.name, write_md=args.write_md)
        print(f"wrote {rel(root / 'tmp' / JSON_REPORT.name, root)}")
        if args.write_md:
            print(f"wrote {rel(root / 'tmp' / MD_REPORT.name, root)}")
        wrote_any = True
    if args.write_redacted_tool_telemetry:
        telemetry = build_redacted_tool_telemetry(root, transcript_paths)
        write_redacted_tool_telemetry(telemetry, root / "tmp" / REDACTED_TOOL_TELEMETRY_JSON.name, root / "tmp" / REDACTED_TOOL_TELEMETRY_MD.name if args.write_md else None)
        print(f"wrote {rel(root / 'tmp' / REDACTED_TOOL_TELEMETRY_JSON.name, root)}")
        if args.write_md:
            print(f"wrote {rel(root / 'tmp' / REDACTED_TOOL_TELEMETRY_MD.name, root)}")
        wrote_any = True
    if not wrote_any:
        print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
