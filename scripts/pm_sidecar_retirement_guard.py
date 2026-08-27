#!/usr/bin/env python3
"""Guard retirement of legacy PM sidecars.

The consolidated PM packet is the routine operating surface. This validator
keeps old PM/queue/heartbeat/handoff sidecars out of active readers while
allowing legacy producers and explicit compatibility/debug references.
"""
from __future__ import annotations

import argparse
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
OUT = TMP / "pm-sidecar-retirement-guard.json"
SCHEMA = "veritas.pm_sidecar_retirement_guard.v1"

SIDECARS = {
    "pm-program-state.json",
    "pm-lane-scoreboard.json",
    "pm-next-actions.json",
    "pm-blocker-register.json",
    "heartbeat-continuation-candidates.json",
    "pm-main-session-handoff.json",
    "pm-dispatch-ledger.json",
}

CURRENT_DERIVED_PM_SURFACES = {
    "pm-implementation-job-queue.json",
}

ALLOWED_FILES = {
    "scripts/lib/pm_control_reader.py",
    "scripts/pm_control_packet.py",
    "scripts/pm_program_state.py",
    "scripts/pm_implementation_job_queue.py",
    "scripts/pm_autonomy_dispatcher.py",
    "scripts/pm_main_session_handoff.py",
    "scripts/heartbeat_continuation_candidates.py",
    "scripts/pm_execution_loop.py",
    "scripts/pm_post_repair_quiescence_refresh.py",
    "scripts/test_pm_implementation_job_queue_control_packet_preference.py",
    "scripts/test_pm_main_session_handoff.py",
    "scripts/test_pm_sidecar_retirement_guard.py",
    "scripts/test_status_card_packet.py",
    "scripts/operating_leverage_spine.py",
    "scripts/startup_brief_packet.py",
    "scripts/status_card_packet.py",
    "scripts/wf74_autonomy_work_router.py",
    "scripts/wf74_improvement_opportunity_queue.py",
    "scripts/wf75_closeout_refresh.py",
    "scripts/db_lifecycle_manifest.py",
    "scripts/pm_sidecar_retirement_guard.py",
    "state/cron-contracts/pm-auto-implementation-gpt55.json",
}

WARNING_ONLY_FILES = {
    "scripts/README.md",
    "TOOLS.md",
    "06. Playbooks/Startup Truth Index.md",
    "06. Playbooks/Active Workflows.md",
    "state/pm-cockpit-source-registry.json",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def scan_file(path: Path) -> list[dict[str, Any]]:
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return []
    matches: list[dict[str, Any]] = []
    for line_no, line in enumerate(text.splitlines(), start=1):
        for sidecar in SIDECARS:
            if sidecar in line:
                matches.append({
                    "path": rel(path),
                    "line": line_no,
                    "sidecar": sidecar,
                    "text": line.strip()[:240],
                })
    return matches


def is_current_derived_pm_surface(sidecar: str) -> bool:
    return sidecar in CURRENT_DERIVED_PM_SURFACES


def source_files() -> list[Path]:
    roots = [ROOT / "scripts", ROOT / "state", ROOT / "06. Playbooks"]
    files: list[Path] = [ROOT / "TOOLS.md"]
    for base in roots:
        if not base.exists():
            continue
        for path in base.rglob("*"):
            if path.is_file() and path.suffix.lower() in {".py", ".json", ".md"}:
                files.append(path)
    return files


def is_generated_capsule(path: str) -> bool:
    return bool(re.match(r"state/workflows/[^/]+\.json$", path))


def is_completion_ledger_proof(path: str) -> bool:
    return (
        bool(re.match(r"state/implementation-completion-backfill-[^/]+\.json$", path))
        or bool(re.match(r"state/implementation-completion-ledger-snapshots/[^/]+\.json$", path))
    )


def is_tmp_lifecycle_rollback_proof(path: str) -> bool:
    return path.startswith("state/tmp-lifecycle-rollback/")


def build_report() -> dict[str, Any]:
    findings: list[dict[str, Any]] = []
    for path in source_files():
        findings.extend(scan_file(path))
    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    allowed: list[dict[str, Any]] = []
    for finding in findings:
        path = str(finding.get("path"))
        sidecar = str(finding.get("sidecar") or "")
        if is_current_derived_pm_surface(sidecar):
            allowed.append({**finding, "reason": "current derived PM lookup, not retired sidecar"})
        elif path in ALLOWED_FILES or is_generated_capsule(path):
            allowed.append({**finding, "reason": "legacy producer/fallback or generated capsule"})
        elif is_completion_ledger_proof(path):
            allowed.append({**finding, "reason": "historical completion-ledger proof snapshot, not active PM consumer"})
        elif is_tmp_lifecycle_rollback_proof(path):
            allowed.append({**finding, "reason": "historical tmp lifecycle rollback proof, not active PM consumer"})
        elif path in WARNING_ONLY_FILES:
            warnings.append({**finding, "reason": "documentation/source-registry cleanup pending"})
        else:
            errors.append(finding)
    return {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "ok" if not errors else "blocked",
        "purpose": "Ensure active PM consumers use tmp/pm-control-packet.json instead of legacy sidecars.",
        "summary": {
            "finding_count": len(findings),
            "error_count": len(errors),
            "warning_count": len(warnings),
            "allowed_count": len(allowed),
            "retired_primary_surface": "tmp/pm-control-packet.json",
        },
        "errors": errors,
        "warnings": warnings,
        "allowed_legacy_references": allowed,
        "validation": {
            "status": "ok" if not errors else "blocked",
            "errors": [f"{row['path']}:{row['line']}:{row['sidecar']}" for row in errors],
            "warnings": [f"{row['path']}:{row['line']}:{row['sidecar']}" for row in warnings],
        },
        "authority_boundary": {
            "review_only": True,
            "guard_only": True,
            "executes_work": False,
            "spawns_helpers": False,
            "mutates_canon_or_portfolio": False,
            "paper_or_live_execution_allowed": False,
            "owner_approval_inferred": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Guard PM sidecar retirement.")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    args = parser.parse_args()
    report = build_report()
    if args.write:
        atomic_write_json(OUT, report)
        print(f"wrote {rel(OUT)} status={report['status']} errors={report['summary']['error_count']} warnings={report['summary']['warning_count']}")
    else:
        print(report["summary"])
    if args.validate and report["status"] != "ok":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
