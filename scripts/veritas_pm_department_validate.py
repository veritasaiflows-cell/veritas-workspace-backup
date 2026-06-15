from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json

WORKSPACE = Path(__file__).resolve().parents[1]
DEFAULT_OUT = WORKSPACE / "tmp" / "veritas-pm-department-validation.json"

PM_SKILL = WORKSPACE / "skills" / "veritas-pm-department" / "SKILL.md"
PDF_SKILL = WORKSPACE / "skills" / "veritas-pdf-brief" / "SKILL.md"

REQUIRED_FILES = [
    "06. Playbooks/Active Workflows.md",
    "06. Playbooks/Project Continuity/Workflow 75 - AI Productivity and Business Opportunity Intelligence Expansion.md",
    "tmp/wf75-service-led-saas-readiness-plan.json",
    "tmp/wf75-service-state-current.json",
    "tmp/wf75-service-state-sqlite.json",
    "tmp/wf75-artifact-only-pm-handoff.json",
    "tmp/wf75-operator-queue.json",
    "tmp/wf75-operator-console.json",
    "tmp/wf75-automation-movement.json",
    "tmp/operator-packets/retail-saas-wf75.json",
    "tmp/workflow-automation-autonomy-review.json",
    "tmp/pm-control-packet.json",
]

OPTIONAL_PROOF_FILES = [
    str(Path("tmp/wf75-operator-console.json").with_suffix(".html")).replace("\\", "/"),
]

PM_REQUIRED_PHRASES = [
    "weekly project updates",
    "upcoming enhancement roadmaps",
    "WF75 readiness timelines",
    "Presentation/PDF Handoff Brief",
    "55-65% internal/service-led SaaS readiness",
    "owner approval inferred from clean validation",
]

PDF_REQUIRED_PHRASES = [
    "PM / Product Readiness PDF or Presentation Packet",
    "weekly PM department updates",
    "WF75 readiness and 6-10 week timeline packaging",
    "Read first through `veritas-pm-department`",
    "Useful PM visuals",
    "Do not turn this into a launch announcement or customer-facing claim.",
]

FORBIDDEN_PM_SECTION_PHRASES = [
    "leadership / underexposure heatmap",
    "strict deployment-surface distribution chart",
    "sector exposure-vs-cap chart",
]

AUTHORITY_FALSE_KEYS = [
    "public_launch_ready",
    "real_customer_data_allowed",
    "external_delivery_allowed",
    "legal_or_compliance_ready",
    "trading_account_or_paper_execution_allowed",
    "source_licensing_assumed",
]


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def relpath(path: Path) -> str:
    try:
        return str(path.relative_to(WORKSPACE)).replace("\\", "/")
    except ValueError:
        return str(path)


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def missing_phrases(text: str, phrases: list[str]) -> list[str]:
    return [phrase for phrase in phrases if phrase not in text]


def section_after(text: str, marker: str) -> str:
    if marker not in text:
        return ""
    return text.split(marker, 1)[1]


def build_result() -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    errors: list[str] = []

    for file_name in REQUIRED_FILES:
        path = WORKSPACE / file_name
        exists = path.exists()
        checks.append({"path": file_name, "exists": exists})
        if not exists:
            errors.append(f"missing required PM source: {file_name}")

    optional_checks: list[dict[str, Any]] = []
    for file_name in OPTIONAL_PROOF_FILES:
        path = WORKSPACE / file_name
        optional_checks.append({"path": file_name, "exists": path.exists(), "required": False})

    pm_exists = PM_SKILL.exists()
    pdf_exists = PDF_SKILL.exists()
    checks.extend(
        [
            {"path": relpath(PM_SKILL), "exists": pm_exists},
            {"path": relpath(PDF_SKILL), "exists": pdf_exists},
        ]
    )
    if not pm_exists:
        errors.append("missing veritas-pm-department skill")
    if not pdf_exists:
        errors.append("missing veritas-pdf-brief skill")

    pm_missing: list[str] = []
    pdf_missing: list[str] = []
    forbidden_in_pm_section: list[str] = []
    if pm_exists:
        pm_missing = missing_phrases(read_text(PM_SKILL), PM_REQUIRED_PHRASES)
        errors.extend(f"PM skill missing required phrase: {phrase}" for phrase in pm_missing)

    if pdf_exists:
        pdf_text = read_text(PDF_SKILL)
        pdf_missing = missing_phrases(pdf_text, PDF_REQUIRED_PHRASES)
        errors.extend(f"PDF skill missing required phrase: {phrase}" for phrase in pdf_missing)
        pm_pdf_section = section_after(pdf_text, "### PM / Product Readiness PDF or Presentation Packet")
        forbidden_in_pm_section = [phrase for phrase in FORBIDDEN_PM_SECTION_PHRASES if phrase in pm_pdf_section]
        errors.extend(f"PDF PM section contains sector-only visual phrase: {phrase}" for phrase in forbidden_in_pm_section)

    plan_path = WORKSPACE / "tmp" / "wf75-service-led-saas-readiness-plan.json"
    plan_authority_errors: list[str] = []
    if plan_path.exists():
        plan = load_json(plan_path)
        boundaries = plan.get("authority_boundaries") if isinstance(plan.get("authority_boundaries"), dict) else {}
        for key in AUTHORITY_FALSE_KEYS:
            if boundaries.get(key) is not False:
                plan_authority_errors.append(key)
        errors.extend(f"WF75 readiness plan authority flag not false: {key}" for key in plan_authority_errors)

    status = "ok" if not errors else "blocked"
    return {
        "schema": "veritas.pm_department.validation.v1",
        "generated_at_utc": utc_now_iso(),
        "status": status,
        "skill_contracts": {
            "pm_skill": relpath(PM_SKILL),
            "pdf_skill": relpath(PDF_SKILL),
            "pm_missing_required_phrases": pm_missing,
            "pdf_missing_required_phrases": pdf_missing,
            "forbidden_sector_visuals_in_pm_pdf_section": forbidden_in_pm_section,
        },
        "required_sources": checks,
        "optional_proof_sources": optional_checks,
        "wf75_authority_false_flags_checked": AUTHORITY_FALSE_KEYS,
        "wf75_authority_flag_errors": plan_authority_errors,
        "errors": errors,
        "authority_boundary": "Review/proof validator only. No launch, customer, external delivery, SQL import, canon/portfolio mutation, paper/live/account action, or owner approval authority.",
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate Veritas PM department and PDF-readiness skill posture.")
    parser.add_argument("--write", action="store_true", help="Write validation JSON.")
    parser.add_argument("--out", default=str(DEFAULT_OUT), help="Output path for --write.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = build_result()
    if args.write:
        out = Path(args.out)
        if not out.is_absolute():
            out = WORKSPACE / out
        atomic_write_json(out, result)
        result["out"] = relpath(out)
    print(json.dumps(result, indent=2))
    return 0 if result["status"] == "ok" else 2


if __name__ == "__main__":
    raise SystemExit(main())
