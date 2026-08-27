#!/usr/bin/env python3
"""Build a review-only packet for OpenClaw Dreaming readiness and signal quality."""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json


ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
OUT = TMP / "dream-review-packet.json"
SCHEMA = "veritas.dream_review_packet.v1"
APPROVED_TZ = "America/Phoenix"
APPROVED_WINDOW = {"start_hour": 2, "end_hour": 6}

AUTHORITY_BOUNDARY: dict[str, bool] = {
    "review_only": True,
    "reads_openclaw_memory_status": True,
    "runs_read_only_rem_harness_when_requested": True,
    "writes_tmp_proof_packet_only": True,
    "dream_or_memory_mutation_allowed": False,
    "memory_promotion_authority_granted_by_this_script": False,
    "canon_or_portfolio_mutation_allowed": False,
    "sql_canon_mutation_allowed": False,
    "config_auth_runtime_mutation_allowed": False,
    "cron_schedule_mutation_allowed": False,
    "capital_deployment_allowed": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "customer_or_external_delivery_allowed": False,
    "owner_approval_inferred": False,
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def openclaw_command_prefix() -> list[str]:
    appdata = os.environ.get("APPDATA")
    if appdata:
        npm_dir = Path(appdata) / "npm"
        mjs = npm_dir / "node_modules" / "openclaw" / "openclaw.mjs"
        node = shutil.which("node") or str(npm_dir / "node.exe")
        if mjs.exists() and node:
            return [node, str(mjs)]

    for candidate in ("openclaw.exe", "openclaw.cmd", "openclaw"):
        resolved = shutil.which(candidate)
        if resolved:
            return [resolved]

    if appdata:
        ps1 = Path(appdata) / "npm" / "openclaw.ps1"
        if ps1.exists():
            return ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(ps1)]

    return ["openclaw"]


def run_openclaw_json(args: list[str], timeout: int) -> tuple[Any | None, dict[str, Any]]:
    command = [*openclaw_command_prefix(), *args, "--json"]
    try:
        proc = subprocess.run(
            command,
            cwd=ROOT,
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            timeout=timeout,
            check=False,
        )
    except FileNotFoundError as exc:
        return None, {"ok": False, "command": command, "error": f"openclaw not found: {exc}"}
    except subprocess.TimeoutExpired as exc:
        return None, {"ok": False, "command": command, "error": f"timeout after {timeout}s", "stdout": exc.stdout}

    meta: dict[str, Any] = {"ok": proc.returncode == 0, "command": command, "returncode": proc.returncode}
    stdout = proc.stdout or ""
    stderr = proc.stderr or ""
    if stderr.strip():
        meta["stderr"] = stderr.strip()[:1000]
    if proc.returncode != 0:
        meta["stdout"] = stdout.strip()[:1000]
        return None, meta
    try:
        return json.loads(stdout), meta
    except json.JSONDecodeError as exc:
        meta["ok"] = False
        meta["error"] = f"json decode failed: {exc}"
        meta["stdout"] = stdout.strip()[:1000]
        return None, meta


def cron_hour_in_window(cron: str, start_hour: int = 2, end_hour: int = 6) -> dict[str, Any]:
    parts = str(cron or "").strip().split()
    if len(parts) < 5:
        return {"ok": False, "hour": None, "reason": "cron expression must have at least five fields"}
    hour_field = parts[1]
    try:
        hour = int(hour_field)
    except ValueError:
        return {"ok": False, "hour": None, "reason": f"unsupported hour field: {hour_field}"}
    inside = start_hour <= hour < end_hour
    return {
        "ok": inside,
        "hour": hour,
        "window": {"start_hour": start_hour, "end_hour": end_hour},
        "reason": "inside approved quiet window" if inside else "outside approved quiet window",
    }


def config_summary(config_payload: Any) -> dict[str, Any]:
    config = as_dict(as_dict(config_payload).get("config"))
    dreaming = as_dict(config.get("dreaming"))
    return {
        "enabled": dreaming.get("enabled") is True,
        "timezone": dreaming.get("timezone"),
        "frequency": dreaming.get("frequency"),
        "deep": as_dict(as_dict(dreaming.get("phases")).get("deep")),
    }


def memory_status_summary(status_payload: Any) -> dict[str, Any]:
    rows = as_list(status_payload)
    row = as_dict(rows[0]) if rows else as_dict(status_payload)
    status = as_dict(row.get("status"))
    audit = as_dict(row.get("audit"))
    dreaming = as_dict(row.get("dreamingAudit"))
    vector = as_dict(status.get("vector"))
    return {
        "agent_id": row.get("agentId"),
        "backend": status.get("backend"),
        "files": status.get("files"),
        "chunks": status.get("chunks"),
        "dirty": status.get("dirty"),
        "provider": status.get("provider"),
        "model": status.get("model"),
        "embedding_probe_ok": as_dict(row.get("embeddingProbe")).get("ok"),
        "vector_available": vector.get("available"),
        "recall_entry_count": audit.get("entryCount"),
        "promoted_count": audit.get("promotedCount"),
        "concept_tagged_entry_count": audit.get("conceptTaggedEntryCount"),
        "dream_session_corpus_files": dreaming.get("sessionCorpusFileCount"),
        "dream_session_ingestion_exists": dreaming.get("sessionIngestionExists"),
        "dreaming_issues": dreaming.get("issues") or [],
    }


def rem_harness_summary(rem_payload: Any) -> dict[str, Any]:
    payload = as_dict(rem_payload)
    rem = as_dict(payload.get("rem"))
    deep = as_dict(payload.get("deep"))
    candidates = as_list(deep.get("candidates"))
    top_candidates = []
    for candidate in candidates[:5]:
        item = as_dict(candidate)
        top_candidates.append(
            {
                "path": item.get("path"),
                "start_line": item.get("startLine"),
                "end_line": item.get("endLine"),
                "score": item.get("score"),
                "recall_count": item.get("recallCount"),
                "unique_queries": item.get("uniqueQueries"),
                "concept_tags": as_list(item.get("conceptTags"))[:8],
            }
        )
    return {
        "enabled": as_dict(payload.get("remConfig")).get("enabled"),
        "cron": as_dict(payload.get("remConfig")).get("cron"),
        "timezone": as_dict(payload.get("remConfig")).get("timezone"),
        "source_entry_count": rem.get("sourceEntryCount"),
        "reflection_count": len(as_list(rem.get("reflections"))),
        "candidate_truth_count": len(as_list(rem.get("candidateTruths"))),
        "candidate_key_count": len(as_list(rem.get("candidateKeys"))),
        "deep_candidate_count": deep.get("candidateCount"),
        "top_candidates": top_candidates,
    }


def dream_artifact_summary() -> dict[str, Any]:
    dream_dir = ROOT / "memory" / ".dreams"
    diary = ROOT / "DREAMS.md"
    corpus = dream_dir / "session-corpus"
    ingestion = dream_dir / "session-ingestion.json"
    event_log = dream_dir / "events.jsonl"
    corpus_files = list(corpus.glob("*")) if corpus.exists() else []
    event_lines = 0
    if event_log.exists():
        try:
            event_lines = sum(1 for _ in event_log.open("r", encoding="utf-8", errors="replace"))
        except OSError:
            event_lines = 0
    return {
        "dream_dir": {"path": rel(dream_dir), "exists": dream_dir.exists()},
        "diary": {"path": rel(diary), "exists": diary.exists(), "size_bytes": diary.stat().st_size if diary.exists() else 0},
        "session_corpus": {"path": rel(corpus), "exists": corpus.exists(), "file_count": len(corpus_files)},
        "session_ingestion": {"path": rel(ingestion), "exists": ingestion.exists()},
        "events": {"path": rel(event_log), "exists": event_log.exists(), "line_count": event_lines},
    }


def validate_payload(payload: dict[str, Any]) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []

    def check(name: str, ok: bool, detail: Any = None, severity: str = "critical") -> None:
        checks.append({"name": name, "ok": bool(ok), "status": "ok" if ok else "fail", "severity": severity, "detail": detail})

    boundary = as_dict(payload.get("authority_boundary"))
    for key, expected in AUTHORITY_BOUNDARY.items():
        check(f"authority_{key}", boundary.get(key) is expected, boundary.get(key))

    config = as_dict(payload.get("config"))
    schedule = as_dict(payload.get("schedule"))
    memory = as_dict(payload.get("memory_status"))
    rem = as_dict(payload.get("rem_harness"))

    check("dreaming_enabled", config.get("enabled") is True, config)
    check("timezone_approved", config.get("timezone") == APPROVED_TZ, config.get("timezone"))
    check("frequency_inside_approved_window", schedule.get("inside_approved_window") is True, schedule)
    check("memory_index_clean", memory.get("dirty") is False, memory.get("dirty"), "warning")
    check("embedding_probe_ok", memory.get("embedding_probe_ok") is True, memory.get("embedding_probe_ok"), "warning")
    check("rem_harness_read_only_summary_present", rem.get("status") in {"captured", "not_requested"}, rem.get("status"))

    errors = [item for item in checks if item["severity"] == "critical" and not item["ok"]]
    warnings = [item for item in checks if item["severity"] == "warning" and not item["ok"]]
    return {"status": "ok" if not errors else "critical", "errors": errors, "warnings": warnings, "checks": checks}


def build_payload(include_rem_harness: bool, timeout: int) -> dict[str, Any]:
    config_payload, config_meta = run_openclaw_json(["config", "get", "plugins.entries.memory-core"], timeout)
    status_payload, status_meta = run_openclaw_json(["memory", "status", "--deep"], timeout)
    config = config_summary(config_payload)
    memory_status = memory_status_summary(status_payload)
    schedule_window = cron_hour_in_window(str(config.get("frequency") or ""))

    rem_summary: dict[str, Any] = {"status": "not_requested"}
    rem_meta: dict[str, Any] = {"ok": True, "command": None}
    if include_rem_harness:
        rem_payload, rem_meta = run_openclaw_json(["memory", "rem-harness"], max(timeout, 120))
        rem_summary = rem_harness_summary(rem_payload)
        rem_summary["status"] = "captured" if rem_meta.get("ok") else "unavailable"

    artifacts = dream_artifact_summary()
    diary_exists = as_dict(artifacts.get("diary")).get("exists") is True
    corpus_count = as_dict(artifacts.get("session_corpus")).get("file_count") or 0
    if config.get("enabled") and not diary_exists and corpus_count == 0:
        status = "active_waiting_first_overnight_sweep"
    elif config.get("enabled"):
        status = "active_with_artifacts"
    else:
        status = "disabled"

    payload = {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": status,
        "purpose": "Review-only proof packet for OpenClaw Dreaming schedule, memory health, and learning-signal readiness.",
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "approved_window": APPROVED_WINDOW | {"timezone": APPROVED_TZ},
        "config": config,
        "schedule": {
            "frequency": config.get("frequency"),
            "timezone": config.get("timezone"),
            "inside_approved_window": schedule_window.get("ok"),
            "parsed_hour": schedule_window.get("hour"),
            "detail": schedule_window,
        },
        "memory_status": memory_status,
        "dream_artifacts": artifacts,
        "rem_harness": rem_summary,
        "source_commands": {
            "config": config_meta,
            "memory_status": status_meta,
            "rem_harness": rem_meta if include_rem_harness else {"ok": True, "command": None, "skipped": True},
        },
        "measurements_to_track": [
            "diary_exists",
            "session_corpus_file_count",
            "session_ingestion_exists",
            "short_term_candidate_truth_count",
            "deep_candidate_count",
            "promoted_count",
            "dreaming_issues",
        ],
        "next_safe_action": (
            "Let the 3 AM America/Phoenix sweep run, then rerun this packet and compare diary, corpus, promoted, and candidate counts. "
            "Escalate only if Dreaming is disabled, outside the quiet window, memory index is dirty, or Dreaming issues appear."
        ),
    }
    payload["validation"] = validate_payload(payload)
    if payload["validation"]["status"] != "ok":
        payload["status"] = "critical"
    return payload


def render_text(payload: dict[str, Any]) -> str:
    config = as_dict(payload.get("config"))
    schedule = as_dict(payload.get("schedule"))
    memory = as_dict(payload.get("memory_status"))
    artifacts = as_dict(payload.get("dream_artifacts"))
    rem = as_dict(payload.get("rem_harness"))
    validation = as_dict(payload.get("validation"))
    return "\n".join(
        [
            f"status={payload.get('status')} validation={validation.get('status')}",
            f"dreaming_enabled={config.get('enabled')} frequency={config.get('frequency')} timezone={config.get('timezone')} inside_window={schedule.get('inside_approved_window')}",
            f"memory_dirty={memory.get('dirty')} embeddings={memory.get('embedding_probe_ok')} recall_entries={memory.get('recall_entry_count')} promoted={memory.get('promoted_count')}",
            f"diary_exists={as_dict(artifacts.get('diary')).get('exists')} corpus_files={as_dict(artifacts.get('session_corpus')).get('file_count')} ingestion_exists={as_dict(artifacts.get('session_ingestion')).get('exists')}",
            f"rem_status={rem.get('status')} candidate_truths={rem.get('candidate_truth_count')} deep_candidates={rem.get('deep_candidate_count')}",
            f"next={payload.get('next_safe_action')}",
        ]
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--json", action="store_true", dest="print_json")
    parser.add_argument("--include-rem-harness", action="store_true")
    parser.add_argument("--timeout", type=int, default=45)
    parser.add_argument("--out", type=Path, default=OUT)
    args = parser.parse_args()

    payload = build_payload(include_rem_harness=args.include_rem_harness, timeout=args.timeout)
    if args.write:
        atomic_write_json(args.out, payload)
    if args.print_json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(render_text(payload))
    if args.validate and as_dict(payload.get("validation")).get("status") != "ok":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
