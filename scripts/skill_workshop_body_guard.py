#!/usr/bin/env python3
"""Guard Skill Workshop updates against accidental skill-body replacement.

The guard is review-only. It checks live skill files and optional live/proposal
pairs for thin proposal wrappers that would replace a full SKILL.md body.
"""
from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json


ROOT = Path(__file__).resolve().parents[1]
SKILLS_DIR = ROOT / "skills"
OUT = ROOT / "tmp" / "skill-workshop-body-guard.json"
SCHEMA = "veritas.skill_workshop_body_guard.v1"

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "lint_only": True,
    "applies_skill_proposals": False,
    "creates_skill_proposals": False,
    "mutates_skill_files": False,
    "cron_schedule_mutation_allowed": False,
    "config_auth_runtime_mutation_allowed": False,
    "canon_or_portfolio_mutation_allowed": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "owner_approval_inferred": False,
}

PROPOSED_UPDATE_RE = re.compile(r"^#\s+Proposed\s+Update\b", re.IGNORECASE | re.MULTILINE)
H1_RE = re.compile(r"^#\s+(.+?)\s*$", re.MULTILINE)
HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$", re.MULTILINE)
NAME_RE = re.compile(r'^name:\s*["\']?([^\r\n"\']+)["\']?\s*$', re.MULTILINE)
PRESERVE_RE = re.compile(r"\b(preserve|keep existing|existing behavior|existing doctrine)\b", re.IGNORECASE)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def strip_frontmatter(text: str) -> str:
    if not text.startswith("---"):
        return text
    match = re.match(r"^---\s*\n.*?\n---\s*\n", text, re.DOTALL)
    return text[match.end():] if match else text


def frontmatter_name(text: str) -> str:
    if not text.startswith("---"):
        return ""
    end = text.find("\n---", 3)
    if end == -1:
        return ""
    match = NAME_RE.search(text[:end])
    return match.group(1).strip() if match else ""


def first_h1(text: str) -> str:
    body = strip_frontmatter(text)
    match = H1_RE.search(body)
    return match.group(1).strip() if match else ""


def headings(text: str) -> list[str]:
    body = strip_frontmatter(text)
    return [f"{match.group(1)} {match.group(2).strip()}" for match in HEADING_RE.finditer(body)]


def heading_titles(text: str, *, min_level: int = 2) -> set[str]:
    titles: set[str] = set()
    for heading in headings(text):
        hashes, title = heading.split(" ", 1)
        if len(hashes) >= min_level:
            titles.add(title.strip().lower())
    return titles


def word_count(text: str) -> int:
    return len(re.findall(r"\b\w+\b", strip_frontmatter(text)))


def add_finding(findings: list[dict[str, Any]], severity: str, code: str, message: str, **detail: Any) -> None:
    finding: dict[str, Any] = {"severity": severity, "code": code, "message": message}
    if detail:
        finding["detail"] = detail
    findings.append(finding)


def analyze_live_skill(path: Path) -> dict[str, Any]:
    text = read_text(path)
    findings: list[dict[str, Any]] = []
    title = first_h1(text)
    name = frontmatter_name(text)
    words = word_count(text)

    if not name:
        add_finding(findings, "warning", "frontmatter_name_missing", "Skill frontmatter is missing a name.")
    if not title:
        add_finding(findings, "warning", "h1_missing", "Skill body is missing an H1 title.")
    if title.lower().startswith("proposed update") or PROPOSED_UPDATE_RE.search(text):
        add_finding(findings, "critical", "live_proposed_update_wrapper", "Live skill still contains a Proposed Update wrapper.")
    if words < 60:
        add_finding(findings, "warning", "live_skill_body_short", "Live skill body is short enough to deserve manual review.", words=words)

    critical = [item for item in findings if item["severity"] == "critical"]
    warnings = [item for item in findings if item["severity"] == "warning"]
    return {
        "path": rel(path),
        "frontmatter_name": name,
        "h1": title,
        "word_count": words,
        "heading_count": len(headings(text)),
        "status": "error" if critical else ("warning" if warnings else "ok"),
        "findings": findings,
    }


def analyze_pair(
    live_path: Path,
    proposal_path: Path,
    *,
    min_size_ratio: float,
    allow_replacement: bool,
) -> dict[str, Any]:
    live_text = read_text(live_path)
    proposal_text = read_text(proposal_path)
    findings: list[dict[str, Any]] = []

    live_title = first_h1(live_text)
    proposal_title = first_h1(proposal_text)
    live_words = word_count(live_text)
    proposal_words = word_count(proposal_text)
    ratio = round(proposal_words / live_words, 3) if live_words else 0.0
    missing_headings = sorted(heading_titles(live_text) - heading_titles(proposal_text))

    if not proposal_title:
        add_finding(findings, "critical", "proposal_h1_missing", "Proposal body is missing an H1 title.")
    if proposal_title.lower().startswith("proposed update") or PROPOSED_UPDATE_RE.search(proposal_text):
        add_finding(findings, "critical", "proposal_proposed_update_wrapper", "Proposal appears to be a thin Proposed Update wrapper.")
    if live_title and proposal_title and live_title != proposal_title and not allow_replacement:
        add_finding(
            findings,
            "warning",
            "proposal_h1_differs_from_live",
            "Proposal H1 differs from the live skill title.",
            live_h1=live_title,
            proposal_h1=proposal_title,
        )
    if ratio < min_size_ratio and not allow_replacement:
        add_finding(
            findings,
            "critical",
            "proposal_body_materially_shorter_than_live",
            "Proposal body is materially shorter than the live skill body.",
            live_words=live_words,
            proposal_words=proposal_words,
            ratio=ratio,
            min_size_ratio=min_size_ratio,
        )
    if PRESERVE_RE.search(proposal_text) and missing_headings and not allow_replacement:
        severity = "critical" if len(missing_headings) >= 2 else "warning"
        add_finding(
            findings,
            severity,
            "proposal_preserve_claim_missing_live_headings",
            "Proposal claims preservation but omits live skill headings.",
            missing_headings=missing_headings[:20],
            missing_heading_count=len(missing_headings),
        )

    critical = [item for item in findings if item["severity"] == "critical"]
    warnings = [item for item in findings if item["severity"] == "warning"]
    return {
        "live_path": rel(live_path),
        "proposal_path": rel(proposal_path),
        "live_h1": live_title,
        "proposal_h1": proposal_title,
        "live_word_count": live_words,
        "proposal_word_count": proposal_words,
        "proposal_to_live_word_ratio": ratio,
        "missing_live_heading_count": len(missing_headings),
        "status": "error" if critical else ("warning" if warnings else "ok"),
        "findings": findings,
    }


def scan_live_skills(skills_dir: Path) -> list[dict[str, Any]]:
    if not skills_dir.exists():
        return []
    return [analyze_live_skill(path) for path in sorted(skills_dir.glob("*/SKILL.md"))]


def build_payload(
    *,
    skills_dir: Path,
    live_skill: Path | None = None,
    proposal_file: Path | None = None,
    min_size_ratio: float = 0.65,
    allow_replacement: bool = False,
) -> dict[str, Any]:
    live_results = scan_live_skills(skills_dir)
    pair_result = None
    if live_skill and proposal_file:
        pair_result = analyze_pair(
            live_skill,
            proposal_file,
            min_size_ratio=min_size_ratio,
            allow_replacement=allow_replacement,
        )

    all_findings: list[dict[str, Any]] = []
    for result in live_results:
        for finding in result["findings"]:
            all_findings.append({**finding, "path": result["path"]})
    if pair_result:
        for finding in pair_result["findings"]:
            all_findings.append({**finding, "path": pair_result["proposal_path"]})

    critical = [item for item in all_findings if item["severity"] == "critical"]
    warnings = [item for item in all_findings if item["severity"] == "warning"]
    status = "error" if critical else ("warning" if warnings else "ok")
    return {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": status,
        "authority_boundary": AUTHORITY_BOUNDARY,
        "parameters": {
            "skills_dir": rel(skills_dir),
            "live_skill": rel(live_skill) if live_skill else None,
            "proposal_file": rel(proposal_file) if proposal_file else None,
            "min_size_ratio": min_size_ratio,
            "allow_replacement": allow_replacement,
        },
        "summary": {
            "live_skill_count": len(live_results),
            "live_error_count": len([item for item in live_results if item["status"] == "error"]),
            "live_warning_count": len([item for item in live_results if item["status"] == "warning"]),
            "pair_status": pair_result["status"] if pair_result else None,
            "critical_count": len(critical),
            "warning_count": len(warnings),
            "next_safe_action": "Do not apply existing-skill update proposals unless this guard is ok or warnings are manually reviewed.",
        },
        "live_skill_results": live_results,
        "pair_result": pair_result,
        "validation": {
            "status": status,
            "errors": critical,
            "warnings": warnings,
        },
        "stop_lines": [
            "This guard is review-only and does not apply Skill Workshop proposals.",
            "Existing-skill update proposals that fail this guard must be revised into full-body merged proposals before apply.",
        ],
    }


def resolve(path: Path) -> Path:
    return path if path.is_absolute() else ROOT / path


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skills-dir", type=Path, default=SKILLS_DIR)
    parser.add_argument("--live-skill", type=Path)
    parser.add_argument("--proposal-file", type=Path)
    parser.add_argument("--min-size-ratio", type=float, default=0.65)
    parser.add_argument("--allow-replacement", action="store_true")
    parser.add_argument("--out", type=Path, default=OUT)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--pretty", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if bool(args.live_skill) ^ bool(args.proposal_file):
        raise SystemExit("--live-skill and --proposal-file must be provided together")

    payload = build_payload(
        skills_dir=resolve(args.skills_dir),
        live_skill=resolve(args.live_skill) if args.live_skill else None,
        proposal_file=resolve(args.proposal_file) if args.proposal_file else None,
        min_size_ratio=args.min_size_ratio,
        allow_replacement=args.allow_replacement,
    )
    if args.write:
        out = resolve(args.out)
        atomic_write_json(out, payload)
    if args.pretty:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(json.dumps({
            "status": payload["status"],
            "summary": payload["summary"],
            "out": rel(resolve(args.out)) if args.write else None,
        }, indent=2, sort_keys=True))
    if args.validate and payload["status"] == "error":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
