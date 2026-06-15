#!/usr/bin/env python3
"""Workspace governance truth check.

Read-only validator for drift between boot files, control surfaces, workspace
structure policy, and safe read-only OpenClaw config snippets. Prints JSON to
stdout by default; use --write to save tmp/workspace-governance-truth-check.json.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "tmp" / "workspace-governance-truth-check.json"
WORKSPACE_PATH = str(ROOT)
OPENCLAW_CLI = shutil.which("openclaw.cmd") or shutil.which("openclaw") or str(Path.home() / "AppData" / "Roaming" / "npm" / "openclaw.cmd")

CORE_FILES = {
    "AGENTS.md": ROOT / "AGENTS.md",
    "TOOLS.md": ROOT / "TOOLS.md",
    "Workspace Structure Protocol": ROOT / "06. Playbooks" / "Workspace Structure Protocol.md",
    "OpenClaw Parallel Pilot Queue": ROOT / "06. Playbooks" / "OpenClaw Parallel Pilot Queue.md",
    "IC Project Registry": ROOT / "06. Playbooks" / "IC Project Registry.md",
}

DB_LIFECYCLE_MANIFEST = ROOT / "tmp" / "db-lifecycle-manifest.json"
DB_LIFECYCLE_SCRIPT = ROOT / "scripts" / "db_lifecycle_manifest.py"
DB_LIFECYCLE_ARCHIVE_SCRIPT = ROOT / "scripts" / "db_lifecycle_archive_apply.py"
SQL_LATENCY_BENCHMARK_SCRIPT = ROOT / "scripts" / "sql_latency_benchmark.py"

SENSITIVE_OUTSIDE_WORKSPACE_TERMS = (
    "config",
    "credential",
    "startup",
    "service",
    "plugin",
    "runtime",
)

STRUCTURE_DOMAIN_TERMS = (
    "01. Dashboards/",
    "02. Markets/",
    "03. Portfolio/",
    "04. Research/",
    "05. Intelligence/",
    "06. Playbooks/",
    "07. Risk/",
    "08. Audits/",
    "09. Archive/",
    "memory/",
    "scripts/",
    "skills/",
    "tmp/",
)

ROOT_EXCEPTION_TERMS = ("migration-backups/", "attachments/", "migration-review.md")

MODEL_POLICY_SURFACES = {
    "SOUL.md": ROOT / "SOUL.md",
    "AGENTS.md": ROOT / "AGENTS.md",
    "USER.md": ROOT / "USER.md",
    "TOOLS.md": ROOT / "TOOLS.md",
    "MEMORY.md": ROOT / "MEMORY.md",
    "OpenClaw Parallel Pilot Queue": ROOT / "06. Playbooks" / "OpenClaw Parallel Pilot Queue.md",
    "IC Project Registry": ROOT / "06. Playbooks" / "IC Project Registry.md",
    "OpenClaw Parallel Work Plan": ROOT / "06. Playbooks" / "OpenClaw Parallel Work Plan.md",
    "Spawn and Closeout Governance Matrix": ROOT / "06. Playbooks" / "Spawn and Closeout Governance Matrix.md",
    "Subagent Spawn Handoff Template": ROOT / "06. Playbooks" / "Subagent Spawn Handoff Template.md",
}

DISALLOWED_MODEL_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("legacy_provider_model_openai_codex_gpt_5_5", re.compile(r"(?<![\w-])openai-codex/gpt-5\.5(?![\w.-])", re.IGNORECASE)),
    ("disallowed_chatgpt_5_5", re.compile(r"(?<![\w-])chatgpt-5\.5(?![\w.-])", re.IGNORECASE)),
)

LIVE_DEPLOYMENT_SURFACES = (
    ROOT / "03. Portfolio" / "Portfolio Snapshot.md",
    ROOT / "03. Portfolio" / "Execution Board.md",
    ROOT / "04. Research" / "Coverage and Watchlist.md",
    ROOT / "05. Intelligence" / "Weekly Positioning Review.md",
    ROOT / "05. Intelligence" / "Weekly Intelligence Brief.md",
    ROOT / "01. Dashboards" / "Executive Brief.md",
    ROOT / "01. Dashboards" / "Next Actions.md",
)

ZERO_DEPLOYABLE_PATTERNS = (
    re.compile(r"deployable-now is zero", re.IGNORECASE),
    re.compile(r"zero deployable-now names", re.IGNORECASE),
    re.compile(r"no names are deployable now", re.IGNORECASE),
)

JPM_PREAPPROVAL_PATTERNS = (
    re.compile(r"\*\*jpm\*\*\s*—\s*promotion[- ]review only", re.IGNORECASE),
    re.compile(r"\*\*jpm\*\*\s+and\s+\*\*nvda\*\*\s+are\s+\*\*promotion[- ]review", re.IGNORECASE),
    re.compile(r"keep\s+\*\*?jpm\*\*?\s+in promotion review", re.IGNORECASE),
    re.compile(r"jpm[^\n]{0,100}blocked pending explicit decision", re.IGNORECASE),
    re.compile(r"jpm[^\n]{0,100}deployment still requires explicit owner decision", re.IGNORECASE),
    re.compile(r"jpm[^\n]{0,100}artifact-level auto-approved[^\n]{0,80}only", re.IGNORECASE),
)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace") if path.exists() else ""


def load_json(path: Path) -> tuple[Any | None, str | None]:
    if not path.exists():
        return None, "missing"
    try:
        return json.loads(path.read_text(encoding="utf-8")), None
    except Exception as exc:
        return None, f"{exc.__class__.__name__}: {exc}"


def add(findings: list[dict[str, Any]], check_id: str, severity: str, issue: str, recommendation: str, evidence: dict[str, Any] | None = None) -> None:
    finding: dict[str, Any] = {
        "check_id": check_id,
        "severity": severity,
        "issue": issue,
        "recommendation": recommendation,
    }
    if evidence:
        finding["evidence"] = evidence
    findings.append(finding)


def normalize(text: str) -> str:
    return text.lower().replace("\\\\", "\\")


def has_workspace_path(text: str) -> bool:
    lowered = normalize(text)
    candidates = {
        normalize(WORKSPACE_PATH),
        r"c:\users\veritas\.openclaw\workspace",
    }
    return any(candidate in lowered for candidate in candidates)


def check_approval_gating(findings: list[dict[str, Any]]) -> None:
    for name in ("AGENTS.md", "TOOLS.md"):
        text = read_text(CORE_FILES[name])
        lowered = normalize(text)
        missing_terms = [term for term in SENSITIVE_OUTSIDE_WORKSPACE_TERMS if term not in lowered]
        approval_language = any(term in lowered for term in ("ask first", "ask before", "approval-gated", "approval gated"))
        outside_workspace = ("outside the workspace" in lowered) or ("outside" in lowered and has_workspace_path(text))
        if missing_terms or not approval_language or not outside_workspace:
            add(
                findings,
                f"approval_gating_{name.lower()}",
                "critical",
                f"{name} does not clearly preserve approval gating for sensitive edits outside the workspace",
                "Restore explicit approval-gated wording for config/credential/startup/service/plugin/runtime edits outside the workspace path.",
                {
                    "missing_terms": missing_terms,
                    "approval_language_present": approval_language,
                    "outside_workspace_path_present": outside_workspace,
                },
            )


def check_structure_protocol(findings: list[dict[str, Any]]) -> None:
    text = read_text(CORE_FILES["Workspace Structure Protocol"])
    missing_domains = [term for term in STRUCTURE_DOMAIN_TERMS if term not in text]
    missing_exceptions = [term for term in ROOT_EXCEPTION_TERMS if term not in text]
    has_exception_heading = "Current documented root exceptions" in text
    has_no_00_rule = "root `00/`" in text or "root 00/" in text
    if missing_domains:
        add(
            findings,
            "workspace_structure_domain_ownership",
            "warning",
            "Workspace Structure Protocol no longer defines the full numbered-domain / implementation-folder ownership set",
            "Re-add explicit ownership lines for numbered domains plus memory/, scripts/, skills/, and tmp/.",
            {"missing_terms": missing_domains},
        )
    if missing_exceptions or not has_exception_heading:
        add(
            findings,
            "workspace_structure_root_exceptions",
            "warning",
            "Workspace Structure Protocol no longer clearly documents the approved root exceptions",
            "Keep root exceptions explicit so root-drift validators do not become folklore.",
            {"missing_exceptions": missing_exceptions, "exception_heading_present": has_exception_heading},
        )
    if not has_no_00_rule:
        add(
            findings,
            "workspace_structure_no_00_layer",
            "warning",
            "Workspace Structure Protocol no longer states that a root 00/ layer is disallowed",
            "Restore the no-root-00 rule or document the approved structural change.",
        )


def check_db_lifecycle_route(findings: list[dict[str, Any]]) -> None:
    tools_text = read_text(CORE_FILES["TOOLS.md"])
    lowered_tools = normalize(tools_text)
    route_terms = (
        "db lifecycle route",
        "db_lifecycle_manifest.py",
        "tmp/db-lifecycle-manifest.json",
        "db_lifecycle_archive_apply.py",
        "explicit owner approval",
        "delete",
    )
    missing_route_terms = [term for term in route_terms if normalize(term) not in lowered_tools]
    if missing_route_terms:
        add(
            findings,
            "db_lifecycle_tools_route_missing",
            "warning",
            "TOOLS.md does not make the DB lifecycle manifest discoverable enough for weekly hygiene",
            "Add a DB lifecycle route that points at db_lifecycle_manifest.py --write --validate and preserves owner approval before archive/delete.",
            {"missing_terms": missing_route_terms},
        )

    missing_scripts = [
        path.relative_to(ROOT).as_posix()
        for path in (DB_LIFECYCLE_SCRIPT, DB_LIFECYCLE_ARCHIVE_SCRIPT, SQL_LATENCY_BENCHMARK_SCRIPT)
        if not path.exists()
    ]
    if missing_scripts:
        add(
            findings,
            "db_lifecycle_support_scripts_missing",
            "warning",
            "One or more DB lifecycle support scripts are missing",
            "Keep the manifest builder, owner-approved archive helper, and manual latency benchmark as routed scripts instead of tmp-only residue.",
            {"missing_scripts": missing_scripts},
        )

    manifest, manifest_error = load_json(DB_LIFECYCLE_MANIFEST)
    if manifest_error:
        add(
            findings,
            "db_lifecycle_manifest_unavailable",
            "warning",
            "DB lifecycle manifest is missing or unreadable",
            "Run python scripts\\db_lifecycle_manifest.py --write --validate before relying on DB hygiene status.",
            {"error": manifest_error},
        )
        return

    if not isinstance(manifest, dict):
        add(
            findings,
            "db_lifecycle_manifest_shape",
            "warning",
            "DB lifecycle manifest has an unexpected JSON shape",
            "Regenerate the manifest and inspect the writer if the shape remains non-object.",
        )
        return

    summary = manifest.get("summary") or {}
    validation_errors = manifest.get("validation_errors") or []
    bad_counts = {
        "unknown_count": summary.get("unknown_count"),
        "integrity_error_count": summary.get("integrity_error_count"),
        "delete_ready_count": summary.get("delete_ready_count"),
    }
    if manifest.get("status") == "validation_error" or validation_errors:
        add(
            findings,
            "db_lifecycle_manifest_validation_error",
            "critical",
            "DB lifecycle manifest reports validation errors",
            "Fix manifest classification/integrity errors before archive or cleanup decisions.",
            {"validation_errors": validation_errors[:20], "truncated": len(validation_errors) > 20},
        )
    if any((value or 0) != 0 for value in bad_counts.values()):
        add(
            findings,
            "db_lifecycle_manifest_bad_counts",
            "critical",
            "DB lifecycle manifest reports unknown, integrity-error, or delete-ready databases",
            "Stop cleanup automation and inspect the manifest before making archive/delete decisions.",
            bad_counts,
        )
    if (summary.get("archive_ready_count") or 0) > 0:
        add(
            findings,
            "db_lifecycle_archive_ready_owner_decision",
            "warning",
            "DB lifecycle manifest has archive-ready candidates awaiting owner decision",
            "Review the manifest and use db_lifecycle_archive_apply.py only after explicit owner approval.",
            {"archive_ready_count": summary.get("archive_ready_count")},
        )

    entries = manifest.get("entries") if isinstance(manifest.get("entries"), list) else []
    snapshot = next((entry for entry in entries if entry.get("path") == "tmp/finance-stack-snapshot.sqlite"), None)
    if not snapshot:
        add(
            findings,
            "db_lifecycle_finance_snapshot_missing",
            "warning",
            "finance-stack-snapshot.sqlite is not represented in the DB lifecycle manifest",
            "Regenerate the manifest or update lifecycle rules if the snapshot was intentionally archived.",
        )
    elif snapshot.get("lifecycle") != "snapshot" or snapshot.get("status") != "conditional_keep":
        add(
            findings,
            "db_lifecycle_finance_snapshot_label_drift",
            "warning",
            "finance-stack-snapshot.sqlite no longer carries the expected snapshot/conditional_keep label",
            "Keep it labeled as a review-only snapshot or archive it with owner approval if superseded.",
            {"lifecycle": snapshot.get("lifecycle"), "status": snapshot.get("status")},
        )
    elif not snapshot.get("rebuild_command") or not snapshot.get("retention_policy"):
        add(
            findings,
            "db_lifecycle_finance_snapshot_retention_missing",
            "warning",
            "finance-stack-snapshot.sqlite is labeled but lacks explicit rebuild/retention metadata",
            "Regenerate the manifest after the snapshot lifecycle rule is updated.",
        )


def section_after_heading(text: str, heading: str) -> str:
    pattern = re.compile(rf"^###\s+{re.escape(heading)}\s*$", re.MULTILINE)
    match = pattern.search(text)
    if not match:
        return ""
    rest = text[match.end():]
    next_heading = re.search(r"^###\s+", rest, re.MULTILINE)
    return rest[: next_heading.start()] if next_heading else rest


def row_containing(text: str, needle: str) -> str:
    for line in text.splitlines():
        if line.lstrip().startswith("|") and needle.lower() in line.lower():
            return line
    return ""


def words_present(text: str, words: tuple[str, ...]) -> bool:
    lowered = text.lower()
    return all(word.lower() in lowered for word in words)


def contains_any(text: str, patterns: tuple[re.Pattern[str], ...]) -> bool:
    return any(pattern.search(text) for pattern in patterns)


def check_workflow_alignment(findings: list[dict[str, Any]]) -> None:
    queue = read_text(CORE_FILES["OpenClaw Parallel Pilot Queue"])
    registry = read_text(CORE_FILES["IC Project Registry"])

    active_section = section_after_heading(queue, "Active workflow")
    next_section = section_after_heading(queue, "Next approved queue item")
    paused_section = section_after_heading(queue, "Paused follow-up lane")

    active_match = re.search(r"Workflow\s+(\d+)", active_section, re.IGNORECASE)
    active_workflow = active_match.group(1) if active_match else None
    wf40_row = row_containing(registry, "Cyber-Security Hardening and Bounded Daily Audit")
    wf38_row = row_containing(registry, "Sector Expansion and Promotion Review Hardening")
    wf37_row = row_containing(registry, "Daily Summary Commercial Brief Hardening")
    wf39_row = row_containing(registry, "Mission Posture and SOP Optimization Hardening")
    wf40_registry_ok = words_present(wf40_row, ("active", "cron", "audit")) or words_present(
        wf40_row,
        ("closed", "scheduled", "confirmation", "audit"),
    )
    wf40_residual_exception = (
        active_workflow not in (None, "40")
        and wf40_registry_ok
        and words_present(queue, ("wf40", "residual", "scheduled", "proof"))
        and words_present(queue, ("ordinary", "scheduled-repeat", "active queue blocker"))
    )

    if active_workflow != "40" and not wf40_residual_exception:
        add(
            findings,
            "wf40_active_queue_status",
            "critical",
            "Queue active-workflow section does not identify WF40 as the active workflow",
            "Reconcile OpenClaw Parallel Pilot Queue before using it as the live control surface, or document the WF40 residual-proof exception while another workflow is active.",
            {"active_workflow_found": active_workflow},
        )
    if not wf40_registry_ok:
        add(
            findings,
            "wf40_registry_status_next_pass",
            "critical",
            "IC Project Registry does not preserve WF40 cron/audit residue as either active watch or closed scheduled-confirmation watch",
            "Update the WF40 registry row or queue entry so WF40 residual scheduled-proof status is explicit.",
            {"row_found": bool(wf40_row), "coarse_terms_expected": ["active/cron/audit or closed/scheduled/confirmation/audit"]},
        )
    if not words_present(next_section, ("wf40", "cron", "stable")) and not wf40_residual_exception:
        add(
            findings,
            "wf40_queue_next_pass",
            "critical",
            "Queue next approved item does not match the WF40 cron-proof / repeated-stability residue recorded in the registry",
            "Reconcile the queue next-approved item and registry next-pass text before spawning the next lane, or document the WF40 residual-proof exception while another workflow is active.",
            {"coarse_terms_expected": ["wf40", "cron", "stable"]},
        )
    if wf40_residual_exception:
        add(
            findings,
            "wf40_residual_proof_exception_active",
            "info",
            "WF40 is intentionally left as residual scheduled-proof watch while another approved workflow remains active",
            "Keep this confirmation watch documented until one ordinary scheduled WF40 proof is clean, then record the confirmation explicitly.",
            {"active_workflow_found": active_workflow, "wf40_registry_row_found": bool(wf40_row)},
        )
    if not words_present(wf38_row, ("closed", "weekly", "lly", "cat")):
        add(
            findings,
            "wf38_registry_closed_handoff",
            "critical",
            "IC Project Registry does not agree that WF38 is closed after the weekly-review / diversification-coverage closeout",
            "Update the WF38 registry row so closeout state and handoff truth remain explicit.",
            {"row_found": bool(wf38_row), "coarse_terms_expected": ["closed", "weekly", "LLY", "CAT"]},
        )

    if not words_present(paused_section, ("workflow 37", "review-only", "delivery", "cron promotion")):
        add(
            findings,
            "wf37_queue_paused_followup",
            "critical",
            "Queue paused-follow-up section does not preserve WF37 review-only/delivery/fail-closed scheduler posture",
            "Restore WF37 as paused follow-up, not active or scheduler-promoted.",
            {"coarse_terms_expected": ["workflow 37", "review-only", "delivery", "cron promotion"]},
        )
    if not words_present(wf37_row, ("paused", "review-only", "delivery", "cron promotion")):
        add(
            findings,
            "wf37_registry_paused_followup",
            "critical",
            "IC Project Registry does not agree that WF37 is paused with review-only proof and delivery-posture residue",
            "Reconcile WF37 registry status before treating the daily-summary lane as promotable.",
            {"row_found": bool(wf37_row), "coarse_terms_expected": ["paused", "review-only", "delivery", "cron promotion"]},
        )

    if not words_present(queue, ("Workflow 39", "closed", "WF38")):
        add(
            findings,
            "wf39_queue_closed_handoff",
            "critical",
            "Queue does not clearly preserve WF39 as closed with handoff back to WF38",
            "Restore WF39 closeout/handoff text or update both queue and registry if the workflow was intentionally reopened.",
            {"coarse_terms_expected": ["Workflow 39", "closed", "WF38"]},
        )
    wf39_handoff_ok = words_present(wf39_row, ("closed", "wf39", "wf38")) and (
        words_present(wf39_row, ("gs", "cash"))
        or words_present(wf39_row, ("weekly", "proof", "diversification"))
    )
    if not wf39_handoff_ok:
        add(
            findings,
            "wf39_registry_closed_handoff",
            "critical",
            "IC Project Registry does not agree that WF39 is closed and handed back to the current WF38 residue",
            "Reconcile the WF39 registry row with the queue before relying on current workflow order.",
            {"row_found": bool(wf39_row), "coarse_terms_expected": ["closed", "wf39", "wf38", "gs/cash or weekly proof/diversification residue"]},
        )


def bounded_snippet(line: str, limit: int = 180) -> str:
    cleaned = re.sub(r"\s+", " ", line).strip()
    return cleaned if len(cleaned) <= limit else cleaned[: limit - 1] + "…"


def check_model_routing_policy(findings: list[dict[str, Any]]) -> None:
    hits: list[dict[str, Any]] = []
    allowed_legacy_context = ("legacy", "old route", "historical", "unless explicitly re-approved")
    for name, path in MODEL_POLICY_SURFACES.items():
        text = read_text(path)
        if not text:
            continue
        for line_number, line in enumerate(text.splitlines(), 1):
            for label, pattern in DISALLOWED_MODEL_PATTERNS:
                if pattern.search(line):
                    if label == "legacy_provider_model_openai_codex_gpt_5_5" and any(term in line.lower() for term in allowed_legacy_context):
                        continue
                    hits.append({
                        "file": path.relative_to(ROOT).as_posix(),
                        "line": line_number,
                        "pattern": label,
                        "snippet": bounded_snippet(line),
                    })
    if hits:
        add(
            findings,
            "model_routing_policy_drift",
            "critical",
            "Active governance/control surfaces contain disallowed or stale model-routing language",
            "Replace stale provider/runtime wording with the approved `openai/gpt-5.5` through Codex-runtime posture; keep only explicitly historical legacy-route mentions.",
            {"hits": hits[:25], "truncated": len(hits) > 25, "hit_count": len(hits)},
        )


def check_jpm_owner_truth(findings: list[dict[str, Any]]) -> None:
    trigger = read_text(ROOT / "03. Portfolio" / "Execution Board.md")
    jpm_deployable_now = bool(re.search(r"\|\s*JPM\s*\|.*\*\*Deployable now\*\*", trigger, re.IGNORECASE)) and "sole deployable-now name" in trigger.lower()
    if not jpm_deployable_now:
        return

    for path in LIVE_DEPLOYMENT_SURFACES:
        text = read_text(path)
        if not text:
            continue
        if contains_any(text, ZERO_DEPLOYABLE_PATTERNS):
            add(
                findings,
                f"jpm_live_surface_zero_deployable_{path.stem.lower().replace(' ', '_')}",
                "critical",
                f"{path.relative_to(ROOT).as_posix()} still says no names are deployable now even though Execution Board shows JPM deployable now",
                "Update the live surface so JPM's explicit owner approval is reflected consistently.",
            )
        if contains_any(text, JPM_PREAPPROVAL_PATTERNS):
            add(
                findings,
                f"jpm_live_surface_preapproval_{path.stem.lower().replace(' ', '_')}",
                "critical",
                f"{path.relative_to(ROOT).as_posix()} still describes JPM as pre-approval / promotion-review-only after the owner decision landed",
                "Remove stale pre-approval wording so the live owner/deployment surfaces agree.",
            )


def parse_jsonish(stdout: str) -> Any:
    text = stdout.strip()
    if not text:
        raise ValueError("empty output")
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    starts = [idx for idx in (text.find("{"), text.find("[")) if idx != -1]
    if not starts:
        raise ValueError("no JSON object or array found")
    start = min(starts)
    for end_char in ("}", "]"):
        end = text.rfind(end_char)
        if end > start:
            try:
                return json.loads(text[start : end + 1])
            except json.JSONDecodeError:
                continue
    raise ValueError("could not parse JSON from command output")


def config_get(path: str, timeout: int) -> tuple[bool, Any | None, str | None]:
    exe = OPENCLAW_CLI
    if exe:
        try:
            proc = subprocess.run(
                [exe, "config", "get", path, "--json"],
                cwd=ROOT,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=timeout,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            proc = None
            cli_error = f"openclaw config get {path} unavailable: {exc.__class__.__name__}"
        else:
            cli_error = f"openclaw config get {path} returned rc={proc.returncode}" if proc.returncode != 0 else None
            if proc.returncode == 0:
                try:
                    return True, parse_jsonish(proc.stdout), None
                except ValueError as exc:
                    return False, None, f"openclaw config get {path} output was not parseable JSON: {exc}"
    else:
        cli_error = "openclaw CLI not found on PATH"

    # Missing optional config paths such as channels or commands.ownerAllowFrom
    # are valid hardening states. Fall back to the local config file so removal
    # does not look like an unavailable read.
    config_path = Path.home() / ".openclaw" / "openclaw.json"
    try:
        obj = json.loads(config_path.read_text(encoding="utf-8"))
        current: Any = obj
        for part in path.split("."):
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                return True, None, None
        return True, current, None
    except Exception as exc:
        return False, None, f"{cli_error}; local config fallback failed: {exc.__class__.__name__}"


def is_truthy_config(value: Any) -> bool:
    if value in (None, False, "", [], {}):
        return False
    if isinstance(value, dict):
        if value.get("enabled") is False or value.get("disabled") is True:
            return False
        return bool(value)
    return True


def dict_get_casefold(mapping: dict[str, Any], key: str) -> Any:
    for existing, value in mapping.items():
        if existing.lower() == key.lower():
            return value
    return None


def json_contains_nonempty_owner(value: Any, provider: str) -> bool:
    if isinstance(value, dict):
        for key, item in value.items():
            if provider in str(key).lower() and is_truthy_config(item):
                return True
            if json_contains_nonempty_owner(item, provider):
                return True
    elif isinstance(value, list):
        return any(json_contains_nonempty_owner(item, provider) for item in value)
    elif isinstance(value, str):
        return provider in value.lower()
    return False


def plugin_enabled(value: Any, provider: str) -> bool:
    if isinstance(value, dict):
        for key, item in value.items():
            lowered = str(key).lower()
            if provider in lowered:
                if any(marker in lowered for marker in ("disabled", "deny", "block")):
                    continue
                return is_truthy_config(item)
            if plugin_enabled(item, provider):
                return True
    elif isinstance(value, list):
        for item in value:
            if isinstance(item, str):
                lowered = item.lower()
                if provider in lowered and not any(marker in lowered for marker in ("disabled", "deny", "block")):
                    return True
            elif plugin_enabled(item, provider):
                return True
    return False


def json_contains_nonempty_discord_owner(value: Any) -> bool:
    return json_contains_nonempty_owner(value, "discord")


def json_contains_nonempty_telegram_owner(value: Any) -> bool:
    return json_contains_nonempty_owner(value, "telegram")


def discord_plugin_enabled(value: Any) -> bool:
    return plugin_enabled(value, "discord")


def telegram_plugin_enabled(value: Any) -> bool:
    return plugin_enabled(value, "telegram")


def check_channel_config(findings: list[dict[str, Any]], cli_timeout: int) -> None:
    tools_text = read_text(CORE_FILES["TOOLS.md"])
    lowered_tools = tools_text.lower()
    telegram_policy_terms = (
        "telegram",
        "randall",
        "owner allowlisting",
        "mention-gating",
    )
    telegram_approved = all(term in lowered_tools for term in telegram_policy_terms) and any(
        term in lowered_tools for term in ("enabled", "explicitly approved", "approved telegram exception")
    )
    local_control_claim_present = "local control ui remains trusted" in lowered_tools or "local control ui remains the trusted operating surface" in lowered_tools
    discord_disabled_claim_present = (
        "discord remains disabled" in lowered_tools
        or "discord/other chat remains disabled" in lowered_tools
        or "discord and any other chat channel remain disabled" in lowered_tools
    )
    no_channel_claim_present = words_present(
        tools_text,
        ("all chat channels are intentionally disabled", "channels", "{}", "telegram.enabled=false", "discord.enabled=false", "ownerAllowFrom"),
    )
    if not (no_channel_claim_present or (telegram_approved and local_control_claim_present and discord_disabled_claim_present)):
        add(
            findings,
            "tools_channel_hardening_claim",
            "warning",
            "TOOLS.md no longer states the current channel hardening posture clearly enough to verify",
            "Keep the no-channel posture or the approved Telegram exception explicit before trusting channel expansion.",
        )

    ok_channels, channels, channel_error = config_get("channels", cli_timeout)
    ok_plugins, plugins, plugin_error = config_get("plugins", cli_timeout)
    ok_owner, owner_allow, owner_error = config_get("commands.ownerAllowFrom", cli_timeout)

    if not ok_channels and not ok_plugins and not ok_owner:
        add(
            findings,
            "openclaw_config_read_unavailable",
            "warning",
            "Safe read-only OpenClaw config snippets were unavailable, so TOOLS.md channel/plugin claims could not be live-checked",
            "Run this validator again from a session where `openclaw config get <path> --json` is available.",
            {"channels": channel_error, "plugins": plugin_error, "commands.ownerAllowFrom": owner_error},
        )
        return

    if not ok_channels:
        add(findings, "channels_config_unavailable", "warning", "Could not read OpenClaw channels config snippet", "Verify channel hardening manually or rerun after CLI access is fixed.", {"error": channel_error})
    elif channels is None:
        pass  # removed channels config is the desired no-channel posture
    elif isinstance(channels, dict):
        for name, value in channels.items():
            if is_truthy_config(value):
                if name.lower() == "telegram" and telegram_approved:
                    continue
                else:
                    add(findings, "chat_channel_enabled", "critical", "An enabled chat channel appears in config without a matching approved exception", "Disable the channel again or update TOOLS.md only after intentional operator approval.", {"channel": name})
    else:
        add(findings, "channels_config_shape_unknown", "warning", "OpenClaw channels config snippet had an unexpected shape", "Inspect channels config manually; validator only checks object-shaped channel maps.", {"type": type(channels).__name__})

    if not ok_plugins:
        add(findings, "plugins_config_unavailable", "warning", "Could not read OpenClaw plugins config snippet", "Verify disabled channel-plugin posture manually or rerun after CLI access is fixed.", {"error": plugin_error})
    else:
        if discord_plugin_enabled(plugins):
            add(findings, "discord_plugin_enabled", "critical", "TOOLS.md says Discord plugin is disabled, but plugins config appears to expose enabled Discord plugin state", "Disable Discord plugin again or update TOOLS.md only after intentional operator approval.")
        if telegram_plugin_enabled(plugins):
            if not telegram_approved:
                add(findings, "telegram_plugin_enabled", "critical", "Telegram plugin appears enabled without a matching approved exception", "Disable Telegram plugin again or update TOOLS.md only after intentional operator approval.")

    if not ok_owner:
        add(findings, "owner_allow_config_unavailable", "warning", "Could not read OpenClaw commands.ownerAllowFrom config snippet", "Verify owner authority remains local Control UI only or the explicitly approved Telegram setup path.", {"error": owner_error})
    elif json_contains_nonempty_discord_owner(owner_allow):
        add(findings, "discord_owner_allow_present", "critical", "TOOLS.md says Discord owner allow entries were removed, but commands.ownerAllowFrom still appears to contain Discord authority", "Remove stale Discord owner authority or document the approved policy change.")
    elif json_contains_nonempty_telegram_owner(owner_allow):
        if not telegram_approved:
            add(findings, "telegram_owner_allow_present", "critical", "Telegram owner allow entries appear without a matching approved exception", "Remove stale Telegram owner authority or document the approved policy change.")


def build_report(cli_timeout: int) -> dict[str, Any]:
    findings: list[dict[str, Any]] = []
    missing_files = [name for name, path in CORE_FILES.items() if not path.exists()]
    for name in missing_files:
        add(
            findings,
            f"missing_required_file_{re.sub(r'[^a-z0-9]+', '_', name.lower()).strip('_')}",
            "critical",
            f"Required governance file is missing: {name}",
            "Restore the file or update the validator contract intentionally.",
        )
    if not missing_files:
        check_approval_gating(findings)
        check_workflow_alignment(findings)
        check_jpm_owner_truth(findings)
        check_structure_protocol(findings)
        check_db_lifecycle_route(findings)
        check_model_routing_policy(findings)
        check_channel_config(findings, cli_timeout=cli_timeout)

    status = "critical" if any(f["severity"] == "critical" for f in findings) else "warning" if any(f["severity"] == "warning" for f in findings) else "ok"
    return {
        "status": status,
        "generated_at_utc": utc_now(),
        "workspace_root": WORKSPACE_PATH,
        "canonical_truth_note": "This validator detects governance drift only. Source notes and approved config remain authoritative.",
        "counts": {
            "findings": len(findings),
            "critical": sum(1 for f in findings if f["severity"] == "critical"),
            "warnings": sum(1 for f in findings if f["severity"] == "warning"),
            "info": sum(1 for f in findings if f["severity"] == "info"),
        },
        "findings": findings,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate workspace governance truth and control-surface drift.")
    parser.add_argument("--write", action="store_true", help=f"write JSON report to {REPORT.relative_to(ROOT).as_posix()}")
    parser.add_argument("--cli-timeout", type=int, default=8, help="seconds to wait for each read-only openclaw config get call")
    args = parser.parse_args()

    report = build_report(cli_timeout=max(1, args.cli_timeout))
    if args.write:
        REPORT.parent.mkdir(parents=True, exist_ok=True)
        REPORT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 1 if report["status"] == "critical" else 0


if __name__ == "__main__":
    raise SystemExit(main())
