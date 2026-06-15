from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

WORKSPACE = Path(__file__).resolve().parents[1]
TMP = WORKSPACE / "tmp"
OPENCLAW_HOME = Path.home() / ".openclaw"
CONFIG_PATH = OPENCLAW_HOME / "openclaw.json"
EXEC_APPROVALS_PATH = OPENCLAW_HOME / "exec-approvals.json"
DEFAULT_JSON_OUT = TMP / "cyber-security-daily-audit.json"
DEFAULT_MD_OUT = TMP / "cyber-security-daily-audit.md"
OPENCLAW_CLI = shutil.which("openclaw.cmd") or shutil.which("openclaw") or str(Path.home() / "AppData" / "Roaming" / "npm" / "openclaw.cmd")
EXPECTED_LOCAL_SENDERS = {"webchat:openclaw-control-ui", "openclaw-control-ui"}
APPROVED_CHAT_CHANNELS = {"telegram"}
APPROVED_NONLOCAL_OWNER_SENDERS = {"telegram:8650152206"}
REQUIRED_SKILLS = {
    "automation-hardening-manager",
    "cron-automation-manager",
    "healthcheck",
    "openclaw-operator",
    "openclaw-troubleshooter",
    "workspace-governor",
    "workspace-qa-pass",
}
BROAD_EXEC_TOKENS = ("python", "node", "powershell", "pwsh", "cmd", "bash")
SEVERITY_ORDER = {"ok": 0, "info": 1, "warning": 2, "critical": 3, "error": 4}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def append_finding(findings: list[dict[str, Any]], severity: str, source: str, message: str, remediation: str | None = None, evidence: Any | None = None) -> None:
    item: dict[str, Any] = {
        "severity": severity,
        "source": source,
        "message": message,
    }
    if remediation:
        item["remediation"] = remediation
    if evidence is not None:
        item["evidence"] = evidence
    findings.append(item)


def status_from_findings(findings: list[dict[str, Any]]) -> str:
    worst = "ok"
    for finding in findings:
        severity = finding.get("severity", "info")
        label = severity if severity in SEVERITY_ORDER else "info"
        if SEVERITY_ORDER[label] > SEVERITY_ORDER[worst]:
            worst = label
    return worst


def normalize_output(value: str | bytes | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value


def run_command(command: list[str], timeout_seconds: int) -> dict[str, Any]:
    try:
        completed = subprocess.run(
            command,
            cwd=WORKSPACE,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
        return {
            "command": command,
            "returncode": completed.returncode,
            "stdout": completed.stdout,
            "stderr": completed.stderr,
            "timed_out": False,
            "error": None,
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "command": command,
            "returncode": None,
            "stdout": normalize_output(exc.stdout),
            "stderr": normalize_output(exc.stderr),
            "timed_out": True,
            "error": f"timeout after {timeout_seconds}s",
        }
    except Exception as exc:  # fail closed
        return {
            "command": command,
            "returncode": None,
            "stdout": "",
            "stderr": "",
            "timed_out": False,
            "error": str(exc),
        }


def run_json_command(command: list[str], timeout_seconds: int) -> tuple[dict[str, Any], Any | None, str | None]:
    result = run_command(command, timeout_seconds)
    stdout = (result.get("stdout") or "").strip()
    if not stdout:
        return result, None, "no stdout"
    try:
        return result, json.loads(stdout), None
    except json.JSONDecodeError as exc:
        return result, None, f"json decode failed: {exc}"


def run_powershell_json(script: str, timeout_seconds: int = 30) -> tuple[dict[str, Any], Any | None, str | None]:
    return run_json_command(["powershell", "-NoProfile", "-Command", script], timeout_seconds)


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def summarize_counts(findings: list[dict[str, Any]]) -> dict[str, int]:
    counts = {"critical": 0, "warning": 0, "info": 0}
    for finding in findings:
        severity = finding.get("severity")
        if severity in counts:
            counts[severity] += 1
    return counts


def parse_doctor_output(text: str) -> dict[str, Any]:
    info = {
        "orphan_transcripts": None,
        "codex_runtime_warning": False,
        "session_lock_stale": False,
        "raw_excerpt": text[:4000],
    }
    for line in text.splitlines():
        stripped = line.strip()
        if "orphan transcript files" in stripped:
            parts = stripped.split()
            for i, token in enumerate(parts):
                if token == "Found" and i + 1 < len(parts):
                    try:
                        info["orphan_transcripts"] = int(parts[i + 1])
                    except ValueError:
                        pass
                    break
        if 'runtime "pi"' in stripped or "agentRuntime.id" in stripped:
            info["codex_runtime_warning"] = True
        if "stale=yes" in stripped:
            info["session_lock_stale"] = True
    return info


def build_config_check(global_findings: list[dict[str, Any]]) -> dict[str, Any]:
    config = load_json(CONFIG_PATH)
    plugins = ((config.get("plugins") or {}).get("entries") or {})
    plugins_allow = set((config.get("plugins") or {}).get("allow") or [])
    channels = config.get("channels") or {}
    owner_allow_from = set((config.get("commands") or {}).get("ownerAllowFrom") or [])
    gateway = config.get("gateway") or {}
    bind = gateway.get("bind")
    trusted_proxies = gateway.get("trustedProxies") or []
    defaults = ((config.get("agents") or {}).get("defaults") or {})
    model_primary = (((defaults.get("model") or {}).get("primary")) or "")
    runtime_id = (((defaults.get("agentRuntime") or {}).get("id")) or "")

    local: list[dict[str, Any]] = []
    channel_names = set(channels.keys()) if isinstance(channels, dict) else set()
    unexpected_channels = sorted(channel_names - APPROVED_CHAT_CHANNELS)
    if unexpected_channels:
        append_finding(local, "warning", "config.channels", "Unexpected chat channels are enabled.", "Keep only explicitly approved channels enabled.", unexpected_channels)
    elif channel_names:
        append_finding(local, "info", "config.channels", "Approved chat channel posture is active.", evidence=sorted(channel_names))
    else:
        append_finding(local, "info", "config.channels", "Channel surface is local-only: channels={}")

    expected_owner_senders = EXPECTED_LOCAL_SENDERS | APPROVED_NONLOCAL_OWNER_SENDERS
    extra_senders = sorted(owner_allow_from - expected_owner_senders)
    missing_senders = sorted(EXPECTED_LOCAL_SENDERS - owner_allow_from)
    if extra_senders:
        append_finding(local, "warning", "config.commands.ownerAllowFrom", "Owner allowlist includes unapproved sender identifiers.", "Keep `ownerAllowFrom` limited to the local Control UI identifiers plus approved Telegram owner entry.", extra_senders)
    if missing_senders:
        append_finding(local, "warning", "config.commands.ownerAllowFrom", "Local Control UI sender allowlist is incomplete.", "Restore the expected local sender identifiers.", missing_senders)

    browser_enabled = bool((plugins.get("browser") or {}).get("enabled"))
    browser_allowlisted = "browser" in plugins_allow
    if browser_enabled or browser_allowlisted:
        append_finding(local, "warning", "config.browser", "Browser surface is enabled or allowlisted.", "Keep browser disabled and off the allowlist unless interactive automation is intentionally needed.", {"enabled": browser_enabled, "allowlisted": browser_allowlisted})
    else:
        append_finding(local, "info", "config.browser", "Browser plugin is disabled and excluded from the allowlist.")

    if model_primary.startswith("openai-codex/") and runtime_id != "codex":
        append_finding(local, "warning", "config.model_runtime", "Default OpenAI model still routes through PI instead of the native Codex runtime.", "If native Codex execution is intended, use `openai/<model>` plus `agents.defaults.agentRuntime.id = \"codex\"`.", {"model": model_primary, "agentRuntime.id": runtime_id or None})

    if bind != "loopback" and not trusted_proxies:
        append_finding(local, "warning", "config.gateway", "Gateway bind is broader than loopback and `trustedProxies` is empty.", "Keep Gateway loopback-only or define trusted proxies before reverse-proxy exposure.", {"bind": bind})
    else:
        append_finding(local, "info", "config.gateway", "Gateway bind remains loopback with no reverse-proxy requirement.", evidence={"bind": bind})

    global_findings.extend(local)
    return {
        "id": "config_posture",
        "status": status_from_findings(local),
        "details": {
            "model_primary": model_primary,
            "agent_runtime_id": runtime_id or None,
            "plugins_allow": sorted(plugins_allow),
            "channels_enabled": sorted(channels.keys()),
            "owner_allow_from": sorted(owner_allow_from),
            "gateway_bind": bind,
        },
    }


def build_exec_approvals_check(global_findings: list[dict[str, Any]]) -> dict[str, Any]:
    approvals = load_json(EXEC_APPROVALS_PATH)
    allowlist = (((approvals.get("agents") or {}).get("main") or {}).get("allowlist") or [])
    risky_patterns: list[str] = []
    for entry in allowlist:
        pattern = str(entry.get("pattern") or "")
        lower = pattern.lower()
        if "*" in pattern or "?" in pattern:
            risky_patterns.append(pattern)
        elif not pattern.startswith("=command:") and any(token in lower for token in BROAD_EXEC_TOKENS):
            risky_patterns.append(pattern)

    local: list[dict[str, Any]] = []
    if risky_patterns:
        append_finding(local, "warning", "exec_approvals", "Exec approvals include broad or interpreter-like allowlist patterns.", "Prefer narrow exact-command approvals for scheduled autonomy.", risky_patterns)
    else:
        append_finding(local, "info", "exec_approvals", "Main-agent exec approvals remain narrow exact-command entries.", evidence={"allowlist_count": len(allowlist)})

    global_findings.extend(local)
    return {
        "id": "exec_approvals_posture",
        "status": status_from_findings(local),
        "details": {
            "exists": EXEC_APPROVALS_PATH.exists(),
            "allowlist_count": len(allowlist),
            "risky_patterns": risky_patterns,
        },
    }


def build_security_audit_check(global_findings: list[dict[str, Any]], deep: bool) -> dict[str, Any]:
    check_id = "openclaw_security_audit_deep" if deep else "openclaw_security_audit_basic"
    command = [OPENCLAW_CLI, "security", "audit"]
    if deep:
        command.append("--deep")
    command.append("--json")
    result, payload, parse_error = run_json_command(command, 90 if deep else 60)

    local: list[dict[str, Any]] = []
    if result.get("error"):
        append_finding(local, "warning", check_id, f"Command error: {result['error']}", "Verify CLI/runtime health and rerun the audit.")
    if parse_error:
        append_finding(local, "warning", check_id, f"Audit output was not usable JSON: {parse_error}", "Inspect the raw stdout/stderr and rerun the audit.")
    if isinstance(payload, dict):
        for item in payload.get("findings", []) or []:
            severity = item.get("severity") or "info"
            mapped = "warning" if severity == "warn" else severity
            append_finding(local, mapped, check_id, item.get("title") or item.get("checkId") or "security finding", item.get("remediation"), item.get("detail"))
    if result.get("timed_out"):
        append_finding(local, "warning", check_id, "Audit timed out.", "Rerun the audit manually and inspect Gateway health.")

    global_findings.extend(local)
    return {
        "id": check_id,
        "status": status_from_findings(local),
        "details": {
            "returncode": result.get("returncode"),
            "timed_out": result.get("timed_out"),
            "summary": (payload or {}).get("summary") if isinstance(payload, dict) else None,
            "deep": (payload or {}).get("deep") if isinstance(payload, dict) and deep else None,
            "stdout_excerpt": (result.get("stdout") or "")[:3000],
            "stderr_excerpt": (result.get("stderr") or "")[:1500],
        },
    }


def build_skills_check(global_findings: list[dict[str, Any]]) -> dict[str, Any]:
    result, payload, parse_error = run_json_command([OPENCLAW_CLI, "skills", "check", "--json"], 60)
    local: list[dict[str, Any]] = []
    if result.get("error") or parse_error or not isinstance(payload, dict):
        append_finding(local, "warning", "skills_check", "Could not parse `openclaw skills check --json`.", "Verify the CLI/runtime and rerun the skill inventory check.", {"error": result.get("error"), "parse_error": parse_error})
    else:
        eligible = set(payload.get("eligible") or [])
        missing = sorted(REQUIRED_SKILLS - eligible)
        if missing:
            append_finding(local, "warning", "skills_check", "Required hardening skills are not all eligible in the current runtime.", "Restore or allowlist the missing skills before relying on the daily hardening lane.", missing)
        summary = payload.get("summary") or {}
        if summary.get("missingRequirements"):
            append_finding(local, "warning", "skills_check", "Some skills are missing runtime requirements.", "Fix missing requirements before relying on those skills.", summary)
        append_finding(local, "info", "skills_check", "Skill inventory check completed.", evidence=summary)

    global_findings.extend(local)
    return {
        "id": "skills_inventory",
        "status": status_from_findings(local),
        "details": {
            "returncode": result.get("returncode"),
            "summary": (payload or {}).get("summary") if isinstance(payload, dict) else None,
            "eligible": (payload or {}).get("eligible") if isinstance(payload, dict) else None,
        },
    }


def build_doctor_check(global_findings: list[dict[str, Any]]) -> dict[str, Any]:
    result = run_command([OPENCLAW_CLI, "doctor"], 60)
    info = parse_doctor_output(result.get("stdout") or "")
    local: list[dict[str, Any]] = []
    if result.get("error") and not result.get("timed_out"):
        append_finding(local, "warning", "openclaw_doctor", f"Doctor failed: {result['error']}", "Run `openclaw doctor` manually and inspect runtime health.")
    if info.get("codex_runtime_warning"):
        append_finding(local, "warning", "openclaw_doctor", "Doctor still reports PI/Codex runtime routing drift.", "Use `openai/<model>` plus `agentRuntime.id='codex'` if native Codex execution is intended.")
    orphan_count = info.get("orphan_transcripts")
    if isinstance(orphan_count, int) and orphan_count > 0:
        append_finding(local, "warning", "openclaw_doctor", f"Doctor found {orphan_count} orphan transcript files.", "Archive or clean orphan transcripts intentionally instead of letting them accumulate.")
    if info.get("session_lock_stale"):
        append_finding(local, "warning", "openclaw_doctor", "Doctor found a stale session lock.", "Inspect and clear stale session locks before they cause session confusion.")
    if result.get("timed_out"):
        append_finding(local, "warning", "openclaw_doctor", "Doctor did not exit cleanly inside the timeout window.", "Treat the partial output as advisory and rerun manually if runtime health is in doubt.")
    if not local:
        append_finding(local, "info", "openclaw_doctor", "Doctor surfaced no material warnings in the bounded window.")

    global_findings.extend(local)
    return {
        "id": "doctor_posture",
        "status": status_from_findings(local),
        "details": {
            "returncode": result.get("returncode"),
            "timed_out": result.get("timed_out"),
            "parsed": info,
            "stdout_excerpt": (result.get("stdout") or "")[:4000],
            "stderr_excerpt": (result.get("stderr") or "")[:1000],
        },
    }


def build_workspace_json_check(global_findings: list[dict[str, Any]], check_id: str, command: list[str], timeout_seconds: int) -> dict[str, Any]:
    result, payload, parse_error = run_json_command(command, timeout_seconds)
    local: list[dict[str, Any]] = []
    if result.get("error") or parse_error or not isinstance(payload, dict):
        append_finding(local, "warning", check_id, f"Could not parse output for {' '.join(command)}.", "Inspect the command output and rerun the audit step.", {"error": result.get("error"), "parse_error": parse_error})
    else:
        status = str(payload.get("status") or "").lower()
        if status in {"critical", "error"}:
            append_finding(local, "critical", check_id, f"{check_id} returned {status}.", "Inspect the attached findings before trusting the workspace posture.", payload.get("findings"))
        elif status == "warning" or result.get("returncode") not in (0, None):
            append_finding(local, "warning", check_id, f"{check_id} returned warning-grade output.", "Review the listed findings and decide whether cleanup or documentation is needed.", payload.get("findings"))
        else:
            append_finding(local, "info", check_id, f"{check_id} passed cleanly.", evidence=payload.get("counts") or payload.get("summary"))

    global_findings.extend(local)
    return {
        "id": check_id,
        "status": status_from_findings(local),
        "details": {
            "returncode": result.get("returncode"),
            "payload": payload,
            "stdout_excerpt": (result.get("stdout") or "")[:4000],
            "stderr_excerpt": (result.get("stderr") or "")[:1000],
        },
    }


def build_firewall_check(global_findings: list[dict[str, Any]]) -> dict[str, Any]:
    script = "Get-NetFirewallProfile | Select-Object Name,Enabled,DefaultInboundAction,DefaultOutboundAction | ConvertTo-Json -Compress"
    result, payload, parse_error = run_powershell_json(script, 30)
    local: list[dict[str, Any]] = []
    profiles = payload if isinstance(payload, list) else ([payload] if payload else [])
    if result.get("error") or parse_error:
        append_finding(local, "warning", "windows_firewall", "Could not read firewall profile state.", "Inspect Windows Firewall manually.", {"error": result.get("error"), "parse_error": parse_error})
    else:
        disabled = [p.get("Name") for p in profiles if not bool(p.get("Enabled"))]
        if disabled:
            append_finding(local, "critical", "windows_firewall", "One or more firewall profiles are disabled.", "Re-enable all Windows Firewall profiles unless an intentional compensating control exists.", disabled)
        else:
            append_finding(local, "info", "windows_firewall", "All Windows Firewall profiles are enabled.", evidence=profiles)

    global_findings.extend(local)
    return {
        "id": "windows_firewall",
        "status": status_from_findings(local),
        "details": {
            "profiles": profiles,
            "returncode": result.get("returncode"),
            "stderr_excerpt": (result.get("stderr") or "")[:1000],
        },
    }


def build_antivirus_check(global_findings: list[dict[str, Any]]) -> dict[str, Any]:
    mp_script = "Get-MpComputerStatus | Select-Object AMServiceEnabled,AntispywareEnabled,AntivirusEnabled,BehaviorMonitorEnabled,IoavProtectionEnabled,NISEnabled,RealTimeProtectionEnabled,AntivirusSignatureLastUpdated,QuickScanAge | ConvertTo-Json -Compress"
    av_script = "Get-CimInstance -Namespace root/SecurityCenter2 -ClassName AntivirusProduct | Select-Object displayName,pathToSignedProductExe,productState,timestamp | ConvertTo-Json -Compress"
    mp_result, mp_payload, mp_error = run_powershell_json(mp_script, 30)
    av_result, av_payload, av_error = run_powershell_json(av_script, 30)

    local: list[dict[str, Any]] = []
    products = av_payload if isinstance(av_payload, list) else ([av_payload] if av_payload else [])
    product_names = [p.get("displayName") for p in products if p.get("displayName")]
    defender_active = bool((mp_payload or {}).get("RealTimeProtectionEnabled")) if isinstance(mp_payload, dict) else False
    non_defender_products = [name for name in product_names if name and name.lower() != "windows defender"]

    if mp_result.get("error") or mp_error:
        append_finding(local, "warning", "windows_antivirus", "Could not read Microsoft Defender status.", "Inspect Windows security posture manually.", {"error": mp_result.get("error"), "parse_error": mp_error})
    if av_result.get("error") or av_error:
        append_finding(local, "warning", "windows_antivirus", "Could not read registered antivirus products.", "Inspect SecurityCenter2 / installed antivirus manually.", {"error": av_result.get("error"), "parse_error": av_error})

    if not product_names and not defender_active:
        append_finding(local, "critical", "windows_antivirus", "No active antivirus posture was visible in the bounded checks.", "Confirm that Defender or a third-party antivirus product is actively protecting the host.")
    elif defender_active:
        append_finding(local, "info", "windows_antivirus", "Microsoft Defender realtime protection is active.", evidence=mp_payload)
    elif non_defender_products:
        append_finding(local, "info", "windows_antivirus", "A third-party antivirus product is registered while Defender realtime protection is off.", evidence={"products": product_names})
    else:
        append_finding(local, "warning", "windows_antivirus", "Defender realtime protection is off and no clear third-party antivirus product was detected.", "Confirm the intended antivirus product and verify it is active.", {"products": product_names, "defender": mp_payload})

    global_findings.extend(local)
    return {
        "id": "windows_antivirus",
        "status": status_from_findings(local),
        "details": {
            "defender": mp_payload,
            "products": products,
            "defender_stderr_excerpt": (mp_result.get("stderr") or "")[:1000],
            "products_stderr_excerpt": (av_result.get("stderr") or "")[:1000],
        },
    }


def select_next_action(findings: list[dict[str, Any]]) -> str:
    for severity in ("critical", "warning"):
        for finding in findings:
            if finding.get("severity") == severity:
                return finding.get("remediation") or finding.get("message") or "Review the first material finding."
    return "Keep the bounded daily hardening audit running; no immediate operator action is required."


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Cyber-Security Daily Audit",
        "",
        f"- Generated at: {report['generated_at_utc']}",
        f"- Status: **{report['status'].upper()}**",
        f"- Stop line: **{str(report['stop_line']).lower()}**",
        f"- Operator action required: **{str(report['operator_action_required']).lower()}**",
        f"- Next action: {report['next_action']}",
        "",
        "## Summary",
        f"- Critical findings: {report['summary']['critical']}",
        f"- Warning findings: {report['summary']['warning']}",
        f"- Info findings: {report['summary']['info']}",
        "",
        "## Checks",
    ]
    for check in report["checks"]:
        lines.append(f"- **{check['id']}** — {check['status']}")
    lines.extend(["", "## Findings"])
    if not report["findings"]:
        lines.append("- No material findings.")
    else:
        for finding in report["findings"]:
            line = f"- **{finding['severity']}** `{finding['source']}` — {finding['message']}"
            if finding.get("remediation"):
                line += f" | Next: {finding['remediation']}"
            lines.append(line)
    return "\n".join(lines) + "\n"


def build_report() -> dict[str, Any]:
    TMP.mkdir(parents=True, exist_ok=True)
    findings: list[dict[str, Any]] = []
    checks = [
        build_config_check(findings),
        build_exec_approvals_check(findings),
        build_security_audit_check(findings, deep=False),
        build_security_audit_check(findings, deep=True),
        build_skills_check(findings),
        build_doctor_check(findings),
        build_workspace_json_check(findings, "workspace_boundary_check", [sys.executable, str(WORKSPACE / "scripts" / "workspace_boundary_check.py")], 90),
        build_workspace_json_check(findings, "dashboard_truth_lint", [sys.executable, str(WORKSPACE / "scripts" / "dashboard_truth_lint.py")], 90),
        build_workspace_json_check(findings, "workspace_governance_truth_check", [sys.executable, str(WORKSPACE / "scripts" / "workspace_governance_truth_check.py"), "--write"], 90),
        build_firewall_check(findings),
        build_antivirus_check(findings),
    ]

    summary = summarize_counts(findings)
    status = "ok"
    if summary["critical"]:
        status = "critical"
    elif summary["warning"]:
        status = "warning"

    return {
        "generated_at_utc": utc_now(),
        "status": status,
        "stop_line": status in {"critical", "error"},
        "operator_action_required": status != "ok",
        "next_action": select_next_action(findings),
        "workspace_root": str(WORKSPACE),
        "openclaw_home": str(OPENCLAW_HOME),
        "trust_boundary": {
            "mode": "read_only_audit",
            "canonical_note_mutation_allowed": False,
            "config_mutation_allowed": False,
            "external_delivery": "none",
        },
        "summary": summary,
        "checks": checks,
        "findings": findings,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Bounded daily cyber-security and workspace hardening audit.")
    parser.add_argument("--json-out", default=str(DEFAULT_JSON_OUT), help="Path to the JSON report output")
    parser.add_argument("--markdown-out", default=str(DEFAULT_MD_OUT), help="Path to the Markdown report output")
    args = parser.parse_args()

    report = build_report()
    json_out = Path(args.json_out)
    markdown_out = Path(args.markdown_out)
    json_out.parent.mkdir(parents=True, exist_ok=True)
    markdown_out.parent.mkdir(parents=True, exist_ok=True)
    json_out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    markdown_out.write_text(render_markdown(report), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 1 if report["stop_line"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
