#!/usr/bin/env python3
"""Audit core workspace skills for Tier 2 local proof eligibility.

This validator is review-only. It reads selected live `skills/*/SKILL.md`
files, verifies that core contract anchors and authority stop-line language are
still present, and writes a JSON proof surface for the governance index.
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
DEFAULT_OUT = ROOT / "tmp" / "skill-core-proof-tier-audit.json"
SCHEMA = "veritas.skill_core_proof_tier_audit.v1"

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "lint_only": True,
    "mutates_skill_files": False,
    "creates_skill_proposals": False,
    "applies_skill_proposals": False,
    "cron_schedule_mutation_allowed": False,
    "config_auth_runtime_mutation_allowed": False,
    "finance_canon_or_portfolio_mutation_allowed": False,
    "cash_sizing_or_risk_mutation_allowed": False,
    "capital_deployment_allowed": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "external_delivery_allowed": False,
    "owner_approval_inferred": False,
}

SHELL_WRAPPER_RE = re.compile(r"^(Exit code|Wall time|Output):", re.MULTILINE)
PROPOSED_UPDATE_RE = re.compile(r"^#\s+Proposed\s+Update\b", re.IGNORECASE | re.MULTILINE)
H1_RE = re.compile(r"^#\s+(.+?)\s*$", re.MULTILINE)
HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$", re.MULTILINE)
NAME_RE = re.compile(r'^name:\s*["\']?([^\r\n"\']+)["\']?\s*$', re.MULTILINE)
MOJIBAKE_MARKERS = ("â€”", "â€“", "â€", "ï¿½")


CORE_CONTRACTS: dict[str, dict[str, Any]] = {
    "task-intake-contract": {
        "cluster": "task_intake",
        "required_terms": [
            "Authority class",
            "Acceptance proof",
            "Debugging loop",
            "Cleanup scope",
            "Response contract",
        ],
        "required_groups": {
            "stop_line": ("Stop line", "Stop if"),
            "finance_boundary": ("paper/live/account", "capital deployment"),
            "config_boundary": ("config/runtime", "Config / Auth / Runtime"),
        },
    },
    "disciplined-implementation": {
        "cluster": "implementation",
        "required_terms": [
            "concurrent_lane_manager.py",
            "changed_file_validator_router.py",
            "validator_bundle_router.py",
            "implementation_release_contract.py",
            "Stop Lines",
        ],
        "required_groups": {
            "lane_lease": ("Lease exact writable surfaces", "lease exact writable"),
            "producer_order": ("producer", "downstream proof"),
            "authority_boundary": ("explicit owner approval", "portfolio/canon", "paper/live"),
        },
    },
    "workspace-qa-pass": {
        "cluster": "qa",
        "required_terms": [
            "claim",
            "proof",
            "validators",
            "authority",
            "Findings",
            "Stop Lines",
        ],
        "required_groups": {
            "not_execution_authority": ("QA is not execution authority", "Do not approve finance"),
            "owner_approval": ("owner approval", "Randall approval"),
            "canon_boundary": ("portfolio/canon", "generated artifacts as canon"),
        },
    },
    "veritas-response-contract": {
        "cluster": "response",
        "required_terms": [
            "Bottom line",
            "Evidence summary",
            "Top recommendations",
            "Do:",
            "Don't:",
            "Skill/runtime check",
            "owner-gated",
        ],
        "required_groups": {
            "finance_boundary": ("paper/live execution", "owner approval"),
            "recommendation_contract": ("Auto-safe now", "Review-only", "Blocked"),
            "proof_rollup": ("pass/warning/fail", "validator proof"),
        },
    },
    "cron-automation-manager": {
        "cluster": "cron",
        "required_terms": [
            "cron_contract_validator.py",
            "cron_freshness_spine.py",
            "Phase 2A",
            "delivery.mode",
            "NO_REPLY",
        ],
        "required_groups": {
            "schedule_boundary": ("schedule mutation", "Schedule changes require"),
            "finance_boundary": ("capital deployment", "paper/live", "owner approval inference"),
            "domain_vs_technical": ("Technical cron failure", "Domain blocker"),
        },
    },
    "openclaw-operator": {
        "cluster": "operator",
        "required_terms": [
            "status_card_packet.py",
            "startup_brief_packet.py",
            "concurrent_lane_manager.py",
            "openclaw skills check",
            "Stop Lines",
        ],
        "required_groups": {
            "cached_status": ("Cached Status Card", "shallow status"),
            "blocked_operator_work": ("Blocked Operator Work", "config/auth/network"),
            "authority_boundary": ("paper/live execution", "owner approval inference"),
        },
    },
    "veritas-model-routing-helper-lanes": {
        "cluster": "model_routing",
        "required_terms": [
            "Veritas main remains",
            "Smoke proof",
            "NO_REPLY",
            "MiniMaxM3",
            "Kimi",
            "Stop lines",
        ],
        "required_groups": {
            "helper_authority": ("main verifies", "final integrator"),
            "fallback_boundary": ("Fallback changes the evidence source", "not the authority level"),
            "finance_boundary": ("paper/live/brokerage/account", "capital deployment"),
        },
    },
    "veritas-intelligence-effort-router": {
        "cluster": "intelligence_routing",
        "required_terms": [
            "finance_sql_canon_access.py",
            "canonical_finance_data_plane.py",
            "tier_a_trade_grade_coverage_gate.py",
            "Scarce-Attention Policy",
            "Stop Lines",
        ],
        "required_groups": {
            "wf78_route": ("current WF78 router", "WF78 lane-qualified truth"),
            "capital_boundary": ("capital deployment", "paper/live orders"),
            "tier_a_depth": ("Tier A Coverage", "depth blockers"),
        },
    },
    "wf67-paper-trading-operator": {
        "cluster": "paper_trading",
        "required_terms": [
            "paper-api.alpaca.markets",
            "ALPACA_PAPER_API_KEY_ID",
            "Execution Stop Line",
            "fresh short-lived paper kill switch",
            "WF67 paper-only wrapper",
            "Randall's exact approval",
        ],
        "required_groups": {
            "live_block": ("Forbidden endpoint", "live credentials"),
            "paper_only": ("paper-only", "simulation system"),
            "approval_separation": ("recommendation object", "execution decision"),
        },
    },
    "veritas-fundamental-pass": {
        "cluster": "finance_fundamental",
        "required_terms": [
            "finance_sql_canon_access.py",
            "source-open",
            "SQL/JSON proof is not approval authority",
            "decision-grade",
            "portfolio-quality",
        ],
        "required_groups": {
            "official_source": ("official-source", "SEC", "IR"),
            "freshness_boundary": ("source lineage", "evidence freshness"),
            "capital_boundary": ("capital deployment", "paper/live execution"),
        },
    },
    "veritas-technical-pass": {
        "cluster": "finance_technical",
        "required_terms": [
            "finance_sql_canon_access.py",
            "capital_deployment_band_integrity_validator.py",
            "preferred entry band",
            "stop or invalidation",
            "Sidecar validator pilot",
            "four-state",
        ],
        "required_groups": {
            "sql_first": ("SQL-First Technical Context", "SQL-first reference levels"),
            "review_only": ("review readiness only", "owner approval inference"),
            "propagation": ("validate_portfolio_config.py", "deployment_check.py"),
        },
    },
    "veritas-positioning-pass": {
        "cluster": "finance_positioning",
        "required_terms": [
            "veritas-intelligence-effort-router",
            "portfolio posture",
            "capital efficiency",
            "conditional portfolio actions",
            "review-ready, deployable, or paper-ready",
        ],
        "required_groups": {
            "capital_boundary": ("Capital deployment", "owner approval"),
            "risk_rules": ("risk rules", "invalidation clarity"),
            "handoff": ("veritas-fundamental-pass", "veritas-technical-pass"),
        },
    },
    "veritas-bounded-portfolio-agent": {
        "cluster": "bounded_portfolio",
        "required_terms": [
            "standing approval",
            "entry_band",
            "Proposal lane",
            "Verifier/challenger lane",
            "Autonomous workspace apply lane",
            "Minimum proof before closure",
        ],
        "required_groups": {
            "apply_requirements": ("exact proposal", "backup/rollback", "validator-clean"),
            "execution_boundary": ("does not itself authorize trades", "live order placement"),
            "wf78_boundary": ("WF78 tier-funnel artifacts", "not portfolio/canon mutation authority"),
        },
    },
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit core workspace skills for Tier 2 local-proof eligibility.")
    parser.add_argument("--skills-dir", default=str(SKILLS_DIR), help="Path to the workspace skills directory.")
    parser.add_argument("--write", action="store_true", help="Write JSON proof to tmp/ or --out.")
    parser.add_argument("--out", default=str(DEFAULT_OUT), help="Output JSON path for --write.")
    parser.add_argument("--validate", action="store_true", help="Return non-zero if the audit is blocked.")
    return parser.parse_args()


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


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


def heading_count(text: str) -> int:
    return len(HEADING_RE.findall(strip_frontmatter(text)))


def word_count(text: str) -> int:
    return len(re.findall(r"\b\w+\b", strip_frontmatter(text)))


def contains(text: str, term: str) -> bool:
    return term.casefold() in text.casefold()


def add_finding(findings: list[dict[str, Any]], severity: str, code: str, message: str, **detail: Any) -> None:
    finding: dict[str, Any] = {"severity": severity, "code": code, "message": message}
    if detail:
        finding["detail"] = detail
    findings.append(finding)


def audit_skill(skills_dir: Path, skill: str, contract: dict[str, Any]) -> dict[str, Any]:
    skill_path = skills_dir / skill / "SKILL.md"
    findings: list[dict[str, Any]] = []

    if not skill_path.exists():
        add_finding(findings, "critical", "skill_file_missing", "Core skill file is missing.", skill=skill)
        return {
            "skill": skill,
            "cluster": contract["cluster"],
            "path": rel(skill_path),
            "status": "blocked",
            "validation_tier": "not eligible",
            "findings": findings,
        }

    text = skill_path.read_text(encoding="utf-8")
    name = frontmatter_name(text)
    title = first_h1(text)
    words = word_count(text)
    headings = heading_count(text)

    if name != skill:
        add_finding(findings, "critical", "frontmatter_name_mismatch", "Skill frontmatter name does not match the directory.", expected=skill, actual=name)
    if not title:
        add_finding(findings, "critical", "h1_missing", "Core skill is missing an H1 title.")
    if PROPOSED_UPDATE_RE.search(text):
        add_finding(findings, "critical", "proposed_update_wrapper", "Core skill still contains a Proposed Update wrapper.")
    if SHELL_WRAPPER_RE.search(text):
        add_finding(findings, "critical", "shell_output_wrapper_residue", "Core skill contains shell-command output wrapper residue.")

    mojibake = [marker for marker in MOJIBAKE_MARKERS if marker in text]
    if mojibake:
        add_finding(findings, "critical", "mojibake_residue", "Core skill contains mojibake/encoding residue.", markers=mojibake)

    if words < 120:
        add_finding(findings, "critical", "core_skill_body_too_short", "Core skill body is too short for a Tier 2 governance proof.", word_count=words)
    if headings < 3:
        add_finding(findings, "critical", "core_skill_heading_count_low", "Core skill has too few headings for a Tier 2 governance proof.", heading_count=headings)

    missing_terms = [term for term in contract["required_terms"] if not contains(text, term)]
    for term in missing_terms:
        add_finding(findings, "critical", "required_term_missing", "Core skill is missing a required contract term.", term=term)

    missing_groups: dict[str, tuple[str, ...]] = {}
    for group_name, options in contract["required_groups"].items():
        if not any(contains(text, option) for option in options):
            missing_groups[group_name] = tuple(options)
            add_finding(
                findings,
                "critical",
                "required_group_missing",
                "Core skill is missing a required contract group.",
                group=group_name,
                options=list(options),
            )

    critical_count = len([item for item in findings if item["severity"] == "critical"])
    warning_count = len([item for item in findings if item["severity"] == "warning"])
    status = "ok" if critical_count == 0 else "blocked"
    return {
        "skill": skill,
        "cluster": contract["cluster"],
        "path": rel(skill_path),
        "status": status,
        "validation_tier": "Tier 2 functional local proof" if status == "ok" else "not eligible",
        "frontmatter_name": name,
        "h1": title,
        "word_count": words,
        "heading_count": headings,
        "required_terms": {
            "expected": contract["required_terms"],
            "missing": missing_terms,
        },
        "required_groups": {
            "expected": {key: list(value) for key, value in contract["required_groups"].items()},
            "missing": {key: list(value) for key, value in missing_groups.items()},
        },
        "finding_counts": {
            "critical": critical_count,
            "warning": warning_count,
        },
        "findings": findings,
    }


def build_payload(skills_dir: Path) -> dict[str, Any]:
    results = [audit_skill(skills_dir, skill, contract) for skill, contract in CORE_CONTRACTS.items()]
    blocked = [item for item in results if item["status"] != "ok"]
    ok = [item for item in results if item["status"] == "ok"]
    all_findings = [
        {**finding, "skill": item["skill"]}
        for item in results
        for finding in item.get("findings", [])
    ]
    critical = [item for item in all_findings if item["severity"] == "critical"]
    warnings = [item for item in all_findings if item["severity"] == "warning"]
    status = "ok" if not critical else "blocked"
    return {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": status,
        "authority_boundary": AUTHORITY_BOUNDARY,
        "parameters": {
            "skills_dir": rel(skills_dir),
            "core_skill_count": len(CORE_CONTRACTS),
        },
        "summary": {
            "audited_core_skill_count": len(results),
            "tier2_local_proof_count": len(ok),
            "blocked_core_skill_count": len(blocked),
            "critical_count": len(critical),
            "warning_count": len(warnings),
            "next_safe_action": "Update governance rows only for skills with status=ok; route blocked rows to Skill Workshop proposals before promotion.",
        },
        "tier2_promoted_skills": [item["skill"] for item in ok],
        "blocked_skills": [item["skill"] for item in blocked],
        "results": results,
        "validation": {
            "status": status,
            "errors": critical,
            "warnings": warnings,
        },
        "validator_note": "Tier 2 here means local machine proof of skill contract anchors and authority boundaries. It is not Tier 3 live workflow proof and does not apply skills or widen authority.",
    }


def main() -> int:
    args = parse_args()
    skills_dir = Path(args.skills_dir)
    if not skills_dir.is_absolute():
        skills_dir = ROOT / skills_dir
    payload = build_payload(skills_dir)

    if args.write:
        out = Path(args.out)
        if not out.is_absolute():
            out = ROOT / out
        atomic_write_json(out, payload)
        payload["out"] = rel(out)

    print(json.dumps(payload, indent=2))
    if args.validate and payload["status"] != "ok":
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
