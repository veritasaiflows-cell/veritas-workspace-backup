#!/usr/bin/env python3
"""Audit the local SEC skill environment without live SEC retrieval.

This validator is a local proof gate. It checks that the active SEC venv,
import surface, User-Agent, and docs contract still match the Veritas workspace
expectations. It does not call SEC endpoints.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json


ROOT = Path(__file__).resolve().parents[1]
SEC_DIR = ROOT / "skills" / "sec"
SEC_SCRIPT = SEC_DIR / "scripts" / "sec_finance_ai.py"
SEC_SKILL_DOC = SEC_DIR / "SKILL.md"
SEC_VENV = SEC_DIR / ".venv"
SEC_VENV_PYTHON = SEC_VENV / "Scripts" / "python.exe"
SEC_VENV_CFG = SEC_VENV / "pyvenv.cfg"
README = ROOT / "scripts" / "README.md"
OUT = ROOT / "tmp" / "sec-env-audit-validator.json"

SCHEMA = "veritas.sec_env_audit_validator.v1"
EXPECTED_USER_AGENT = "Veritas OpenClaw Research veritasaiflows@gmail.com"
PLACEHOLDER_USER_AGENT = "SEC-AI-Research-Agent (admin@example.com)"
MIN_METHOD_COUNT = 17
REQUIRED_METHODS = {
    "analyze_8k_filing",
    "get_available_functions",
    "get_beneficial_ownership",
    "get_company_concept",
    "get_company_facts",
    "get_company_filings",
    "get_filing_content",
    "get_insider_transactions",
    "get_latest_10k",
    "get_latest_10q",
    "get_proxy_statements",
    "get_recent_8k_filings",
    "get_recent_ipos",
    "get_sec_api_status",
    "run_self_test",
    "search_filings",
}

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "local_environment_audit_only": True,
    "live_sec_retrieval_allowed": False,
    "dependency_mutation_allowed": False,
    "venv_delete_move_rebuild_allowed": False,
    "canon_or_portfolio_mutation_allowed": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "money_movement_allowed": False,
    "external_delivery_allowed": False,
    "owner_approval_inferred": False,
}

SKILL_DOC_EXPECTATIONS: dict[str, list[str]] = {
    "venv_keep_in_place": [
        "skills\\sec\\.venv",
        "Do not delete, move, rebuild, or update that environment",
    ],
    "windows_first_runtime": [
        "Windows/PowerShell",
        ".\\.venv\\Scripts\\python.exe",
    ],
    "user_agent_gate": [
        "SEC_HEADERS",
        EXPECTED_USER_AGENT,
        PLACEHOLDER_USER_AGENT,
    ],
    "review_only_boundary": [
        "review-only evidence",
        "portfolio/canon mutation",
        "brokerage/account action",
        "paper/live execution",
    ],
}

README_EXPECTATIONS: dict[str, list[str]] = {
    "env_audit_command": [
        "python scripts\\sec_env_audit_validator.py --write --validate",
        "tmp/sec-env-audit-validator.json",
    ],
    "sec_venv_packet_command": [
        "skills\\sec\\.venv\\Scripts\\python.exe scripts\\sec_evidence_packet.py",
    ],
    "current_packet_outputs": [
        "tmp/sec-evidence-packets/current-sec-evidence.json",
        "tmp/sec-evidence-packets/current-sec-evidence-validation.json",
        "tmp/sec-evidence-packets/capital-recommendation-sec-bridge.json",
        "tmp/official-ir-captures/goog-q1-2026.json",
    ],
    "authority_and_stop_lines": [
        "SEC packet alone does not apply canonical/portfolio mutation",
        "invalid/placeholder SEC User-Agent",
    ],
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def add_finding(findings: list[dict[str, Any]], severity: str, code: str, message: str, **detail: Any) -> None:
    row: dict[str, Any] = {"severity": severity, "code": code, "message": message}
    if detail:
        row["detail"] = detail
    findings.append(row)


def validate_user_agent(user_agent: str | None) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    value = (user_agent or "").strip()
    if not value:
        add_finding(findings, "critical", "user_agent_missing", "SEC User-Agent is missing.")
    if value == PLACEHOLDER_USER_AGENT or "admin@example.com" in value:
        add_finding(findings, "critical", "user_agent_placeholder", "SEC User-Agent is still the packaged placeholder.", value=value)
    if value != EXPECTED_USER_AGENT:
        add_finding(findings, "critical", "user_agent_unexpected", "SEC User-Agent does not match the expected local value.", value=value, expected=EXPECTED_USER_AGENT)
    if not re.search(r"[^@\s]+@[^@\s]+\.[^@\s]+", value):
        add_finding(findings, "critical", "user_agent_email_missing", "SEC User-Agent does not include a contact email.", value=value)
    return findings


def check_files(root: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    findings: list[dict[str, Any]] = []
    paths = {
        "sec_dir": root / "skills" / "sec",
        "sec_script": root / "skills" / "sec" / "scripts" / "sec_finance_ai.py",
        "skill_doc": root / "skills" / "sec" / "SKILL.md",
        "venv_dir": root / "skills" / "sec" / ".venv",
        "venv_python": root / "skills" / "sec" / ".venv" / "Scripts" / "python.exe",
        "venv_cfg": root / "skills" / "sec" / ".venv" / "pyvenv.cfg",
        "readme": root / "scripts" / "README.md",
    }
    result: dict[str, Any] = {}
    for key, path in paths.items():
        exists = path.exists()
        result[key] = {"path": rel(path), "exists": exists}
        if not exists:
            add_finding(findings, "critical", f"{key}_missing", f"Required SEC environment path is missing: {rel(path)}")
    if paths["venv_python"].exists() and not paths["venv_python"].is_file():
        add_finding(findings, "critical", "venv_python_not_file", "SEC venv interpreter path is not a file.", path=rel(paths["venv_python"]))
    return result, findings


def parse_pyvenv_cfg(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    data: dict[str, str] = {}
    for line in read_text(path).splitlines():
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        data[key.strip()] = value.strip()
    return data


def import_probe(root: Path, timeout_seconds: int = 30) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    findings: list[dict[str, Any]] = []
    python_exe = root / "skills" / "sec" / ".venv" / "Scripts" / "python.exe"
    script_dir = root / "skills" / "sec" / "scripts"
    code = f"""
import json
import sys
sys.path.insert(0, {str(script_dir)!r})
from sec_finance_ai import Tools, SEC_HEADERS

t = Tools()
methods = [name for name in dir(t) if not name.startswith("_") and callable(getattr(t, name))]
print(json.dumps({{
    "python_version": sys.version,
    "method_count": len(methods),
    "methods": sorted(methods),
    "user_agent": SEC_HEADERS.get("User-Agent"),
}}))
"""
    try:
        proc = subprocess.run(
            [str(python_exe), "-c", code],
            cwd=root,
            text=True,
            capture_output=True,
            timeout=timeout_seconds,
            check=False,
        )
    except Exception as exc:
        add_finding(findings, "critical", "import_probe_exception", "SEC import probe could not run.", error=str(exc))
        return None, findings
    if proc.returncode != 0:
        add_finding(
            findings,
            "critical",
            "import_probe_failed",
            "SEC import probe returned a nonzero exit code.",
            returncode=proc.returncode,
            stderr=proc.stderr.strip()[-1000:],
            stdout=proc.stdout.strip()[-1000:],
        )
        return None, findings
    probe = parse_json_from_output(proc.stdout)
    if probe is None:
        add_finding(findings, "critical", "import_probe_json_missing", "SEC import probe did not emit parseable JSON.", stdout=proc.stdout.strip()[-1000:])
        return None, findings
    methods = set(probe.get("methods") or [])
    missing = sorted(REQUIRED_METHODS - methods)
    if missing:
        add_finding(findings, "critical", "required_methods_missing", "SEC Tools import surface is missing required methods.", missing_methods=missing)
    method_count = int(probe.get("method_count") or 0)
    if method_count < MIN_METHOD_COUNT:
        add_finding(findings, "critical", "method_count_low", "SEC Tools import surface has fewer methods than expected.", method_count=method_count, minimum=MIN_METHOD_COUNT)
    findings.extend(validate_user_agent(probe.get("user_agent")))
    return probe, findings


def parse_json_from_output(output: str) -> dict[str, Any] | None:
    for line in output.splitlines():
        stripped = line.strip()
        if not stripped.startswith("{"):
            continue
        try:
            parsed = json.loads(stripped)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return parsed
    return None


def check_doc_expectations(path: Path, expectations: dict[str, list[str]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    findings: list[dict[str, Any]] = []
    checks: list[dict[str, Any]] = []
    if not path.exists():
        add_finding(findings, "critical", "doc_missing", "Required documentation file is missing.", path=rel(path))
        return checks, findings
    text = read_text(path)
    for name, needles in expectations.items():
        missing = [needle for needle in needles if needle not in text]
        checks.append({
            "name": name,
            "status": "ok" if not missing else "error",
            "missing": missing,
        })
        if missing:
            add_finding(findings, "critical", "doc_expectation_missing", "Required SEC documentation expectation is missing.", path=rel(path), check=name, missing=missing)
    return checks, findings


def build_payload(root: Path = ROOT, *, run_import: bool = True) -> dict[str, Any]:
    findings: list[dict[str, Any]] = []
    path_status, path_findings = check_files(root)
    findings.extend(path_findings)

    pyvenv = parse_pyvenv_cfg(root / "skills" / "sec" / ".venv" / "pyvenv.cfg")
    if pyvenv and not str(pyvenv.get("version", "")).startswith("3.13."):
        add_finding(findings, "warning", "python_version_unexpected", "SEC venv Python version is outside the expected 3.13 family.", version=pyvenv.get("version"))

    probe: dict[str, Any] | None = None
    if run_import and not any(item["severity"] == "critical" and item["code"].startswith("venv_python") for item in findings):
        probe, import_findings = import_probe(root)
        findings.extend(import_findings)

    skill_checks, skill_findings = check_doc_expectations(root / "skills" / "sec" / "SKILL.md", SKILL_DOC_EXPECTATIONS)
    readme_checks, readme_findings = check_doc_expectations(root / "scripts" / "README.md", README_EXPECTATIONS)
    findings.extend(skill_findings)
    findings.extend(readme_findings)

    critical = [item for item in findings if item["severity"] == "critical"]
    warnings = [item for item in findings if item["severity"] == "warning"]
    status = "error" if critical else ("warning" if warnings else "ok")
    return {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": status,
        "authority_boundary": AUTHORITY_BOUNDARY,
        "summary": {
            "critical_count": len(critical),
            "warning_count": len(warnings),
            "venv_exists": path_status.get("venv_dir", {}).get("exists", False),
            "venv_python_exists": path_status.get("venv_python", {}).get("exists", False),
            "python_version": pyvenv.get("version") or (probe or {}).get("python_version"),
            "method_count": (probe or {}).get("method_count"),
            "user_agent": (probe or {}).get("user_agent"),
            "skill_doc_checks": len(skill_checks),
            "readme_checks": len(readme_checks),
            "next_safe_action": "Run this audit before SEC evidence packet generation or after SEC skill/docs changes.",
        },
        "paths": path_status,
        "pyvenv": pyvenv,
        "import_probe": probe,
        "doc_checks": {
            "skill": {"path": rel(root / "skills" / "sec" / "SKILL.md"), "checks": skill_checks},
            "readme": {"path": rel(root / "scripts" / "README.md"), "checks": readme_checks},
        },
        "validation": {
            "status": status,
            "errors": critical,
            "warnings": warnings,
        },
        "stop_lines": [
            "This validator must not delete, move, rebuild, or update skills/sec/.venv.",
            "This validator must not run live SEC network retrieval.",
            "A failed SEC environment audit blocks relying on SEC evidence tooling until repaired.",
            "Clean SEC environment proof does not authorize portfolio/canon mutation, capital deployment, paper/live execution, account action, or external delivery.",
        ],
    }


def resolve(path: Path) -> Path:
    return path if path.is_absolute() else ROOT / path


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=OUT)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--pretty", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    payload = build_payload()
    out = resolve(args.out)
    if args.write:
        atomic_write_json(out, payload)
    if args.pretty:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(json.dumps({
            "status": payload["status"],
            "summary": payload["summary"],
            "out": rel(out) if args.write else None,
        }, indent=2, sort_keys=True))
    if args.validate and payload["status"] == "error":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
