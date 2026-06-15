#!/usr/bin/env python3
"""Plain-English workspace boundary check for WF34.

This reports drift only. It does not move, delete, or rewrite workspace files.
"""
from __future__ import annotations

import json
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
SCRIPTS = ROOT / "scripts"
REPORT = TMP / "workspace-boundary-check.json"

ROOT_ALLOWED_FILES = {
    ".gitignore",
    "AGENTS.md",
    "CLAUDE.md",
    "Continuity Protocol.md",
    "GEMINI.md",
    "HEARTBEAT.md",
    "Home.md",
    "IDENTITY.md",
    "MEMORY.md",
    "migration-review.md",
    "SOUL.md",
    "TOOLS.md",
    "USER.md",
}
ROOT_ALLOWED_DIRS = {
    ".backups",
    ".claude",  # documented runtime/tool-settings exception; do not archive/move without exact runtime approval
    ".clawhub",
    ".git",
    ".obsidian",
    ".openclaw",
    "01. Dashboards",
    "02. Markets",
    "03. Portfolio",
    "04. Research",
    "05. Intelligence",
    "06. Playbooks",
    "07. Risk",
    "08. Audits",
    "09. Archive",
    "apps",  # local app surfaces such as the PM TypeScript/Node control cockpit
    "attachments",
    "backups",
    "data",
    "memory",
    "migration-backups",
    "scripts",
    "skills",
    "skills-backup",  # documented non-runtime skill backup/provenance exception; active skills remain under skills/
    "state",
    "tools",  # documented local tool-runtime exception such as tools/otelcol
    "training",  # durable Randall-facing internal training assets; source/proof remains in scripts/tmp
    "tmp",
}

PY_EXCEPTIONS_IN_TMP = {
    # Audited 2026-06-07 as one-off diagnostic/proof helpers. They are not
    # durable tooling and should be deleted or archived only after explicit
    # cleanup approval if they stop supporting current proof review.
    "health_detail.py",
    "parity_diag.py",
}
SCRIPT_BACKUP_SUFFIX_MARKERS = (".bak-", ".backup-")


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def classify_data_surface() -> list[dict]:
    findings: list[dict] = []
    data_dir = ROOT / "data"
    if not data_dir.exists():
        return findings
    approved = {"state-history", "fundamentals", "finance", "market"}
    for child in sorted(data_dir.iterdir(), key=lambda p: p.name.lower()):
        if child.is_file() and child.name == "README.md":
            continue
        if child.name not in approved:
            findings.append({
                "path": rel(child) + ("/" if child.is_dir() else ""),
                "severity": "warning",
                "issue": "data/ contains an undocumented durable-derived surface",
                "recommended_action": "document authority/README or archive after reference check",
            })
        elif child.is_dir() and not (child / "README.md").exists():
            findings.append({
                "path": rel(child) + "/",
                "severity": "warning",
                "issue": "approved data/ surface is missing README authority boundary",
                "recommended_action": "add README with producer, authority, proof, and retention posture",
            })
    return findings


def classify_root() -> list[dict]:
    findings: list[dict] = []
    for item in sorted(ROOT.iterdir(), key=lambda p: p.name.lower()):
        if item.is_dir() and item.name not in ROOT_ALLOWED_DIRS:
            findings.append({
                "path": item.name + "/",
                "severity": "warning",
                "issue": "root directory has no documented active entitlement",
                "recommended_action": "verify runtime ownership; document, archive, or remove-later",
            })
        elif item.is_file() and item.name not in ROOT_ALLOWED_FILES:
            findings.append({
                "path": item.name,
                "severity": "warning",
                "issue": "root file has no active-root entitlement in the allowlist",
                "recommended_action": "reference-check; move to audit/archive or document exception",
            })
    for name in ("state",):
        path = ROOT / name
        if path.exists() and path.is_dir() and not any(path.iterdir()):
            findings.append({
                "path": name + "/",
                "severity": "warning",
                "issue": "empty root directory without current documented entitlement",
                "recommended_action": "verify not runtime-owned; then remove-later or document exception",
            })
    return findings


def classify_tmp_scripts() -> list[dict]:
    findings: list[dict] = []
    if not TMP.exists():
        return findings
    for path in sorted(TMP.glob("*.py")):
        if path.name in PY_EXCEPTIONS_IN_TMP:
            continue
        findings.append({
            "path": rel(path),
            "severity": "warning",
            "issue": "executable Python helper lives in generated-artifact tmp/ surface",
            "recommended_action": "move to scripts/ if durable; otherwise archive out of active tmp/",
        })
    return findings


def classify_script_debris() -> list[dict]:
    findings: list[dict] = []
    for path in sorted(SCRIPTS.iterdir(), key=lambda p: p.name.lower()):
        if path.is_file() and any(marker in path.name for marker in SCRIPT_BACKUP_SUFFIX_MARKERS):
            findings.append({
                "path": rel(path),
                "severity": "info",
                "issue": "backup file in active scripts/ surface",
                "recommended_action": "move to migration-backups/ or archive surface after current script parity is verified",
            })
    for cache in sorted(SCRIPTS.rglob("__pycache__")):
        findings.append({
            "path": rel(cache) + "/",
            "severity": "info",
            "issue": "Python runtime cache; non-canonical debris",
            "recommended_action": "keep ignored or remove when safe; never treat as operating evidence",
        })
    return findings


def artifact_observations() -> list[dict]:
    findings: list[dict] = []
    if (TMP / "workspace-index.sqlite").exists():
        findings.append({
            "path": "tmp/workspace-index.sqlite",
            "severity": "info",
            "issue": "generated SQLite retrieval cache",
            "recommended_action": "retain ignored; source Markdown remains canonical",
        })
    if (TMP / "veritas-command-center.last-good.html").exists():
        findings.append({
            "path": "tmp/veritas-command-center.last-good.html",
            "severity": "info",
            "issue": "last-known-good dashboard fallback generated by finance chain",
            "recommended_action": "retain while run_finance_refresh_chain.py references it as fallback",
        })
    brk_dash = TMP / "entry-band-reports" / "BRK.B_entry_band.html"
    brk_hyphen = TMP / "entry-band-reports" / "BRK-B_entry_band.html"
    if brk_dash.exists() and brk_hyphen.exists():
        findings.append({
            "path": "tmp/entry-band-reports/BRK.B_entry_band.html and BRK-B_entry_band.html",
            "severity": "warning",
            "issue": "duplicate BRK.B/BRK-B report naming variants coexist",
            "recommended_action": "verify current consumers use BRK.B; archive/remove stale variant only after reference check",
        })
    return findings


def build_report() -> dict:
    findings = classify_root() + classify_data_surface() + classify_tmp_scripts() + classify_script_debris() + artifact_observations()
    status = "warning" if any(f["severity"] == "warning" for f in findings) else "ok"
    return {
        "status": status,
        "generated_at_utc": utc_now(),
        "canonical_truth_note": "This report is a boundary-audit aid only. Source files and governance notes remain authoritative.",
        "counts": {
            "findings": len(findings),
            "warnings": sum(1 for f in findings if f["severity"] == "warning"),
            "info": sum(1 for f in findings if f["severity"] == "info"),
        },
        "findings": findings,
    }


def main() -> int:
    report = build_report()
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 1 if report["status"] == "warning" else 0


if __name__ == "__main__":
    raise SystemExit(main())
