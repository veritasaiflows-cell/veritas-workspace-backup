from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import board_canon_guardrail
import stale_intelligence_guardrail

WORKSPACE = Path(__file__).resolve().parents[1]
TMP = WORKSPACE / "tmp"
OUT_JSON = TMP / "canonical-note-patch-proposal.json"
OUT_MD = TMP / "canonical-note-patch-proposal.md"
SCHEMA_VERSION = 1

MUTATION_BLOCKERS = re.compile(
    r"\b(weight|sizing|allocation|cash|sleeve|promot(?:e|ion)|demot(?:e|ion)|owner[- ]approval|execution entitlement|trade|buy|sell|trim|add shares?)\b",
    re.IGNORECASE,
)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat(timespec="seconds").replace("+00:00", "Z")


def money(value: Any) -> str:
    try:
        return f"{float(value):.2f}"
    except (TypeError, ValueError):
        return "n/a"


def risk_by_ticker(report: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(r.get("ticker")): r for r in report.get("risks", []) if r.get("ticker")}


def classify_issue(issue: dict[str, Any]) -> str:
    code = str(issue.get("code") or "")
    if code.endswith("contraction") or "contradiction" in code:
        return "cross_surface_contradiction"
    if "missing" in code or "not_visible" in code:
        return "canonical_visibility_gap"
    if "artifact" in str(issue.get("surface") or "") or str(issue.get("surface") or "").startswith("tmp/"):
        return "artifact_authority_gap"
    return "canonical_note_freshness"


def candidate_status(issue: dict[str, Any]) -> str:
    if issue.get("severity") == "critical":
        return "proposed_for_main_session_review"
    return "review_optional"


def proposed_replacement_hint(issue: dict[str, Any], risk: dict[str, Any] | None) -> str:
    ticker = issue.get("ticker") or "UNKNOWN"
    risk_state = (risk or {}).get("risk_state") or "risk"
    close = money((risk or {}).get("close"))
    stop = money((risk or {}).get("stop"))
    band_low = money((risk or {}).get("band_low"))
    if risk_state == "below_stop":
        return (
            f"Make `{ticker}` visibly read as **do not touch / stop-breached** on this surface. "
            f"Required factual line: close `{close}` is below stop `{stop}` and below/against band low `{band_low}`; "
            "no deployment entitlement, promotion, sizing, or execution authority is implied."
        )
    return (
        f"Make `{ticker}` visibly read as **near-stop / repair-watch** on this surface. "
        f"Required factual line: close `{close}` is within the stop-risk zone above stop `{stop}`; "
        "do not soften this into deployable/watch-active language without main-session review."
    )


def build_candidates(report: dict[str, Any]) -> list[dict[str, Any]]:
    risks = risk_by_ticker(report)
    candidates: list[dict[str, Any]] = []
    for idx, issue in enumerate(report.get("issues", []) or [], start=1):
        ticker = str(issue.get("ticker") or "UNKNOWN")
        surface = str(issue.get("surface") or "")
        hint = proposed_replacement_hint(issue, risks.get(ticker))
        blocked_terms = sorted(set(m.group(0).lower() for m in MUTATION_BLOCKERS.finditer(hint)))
        candidates.append({
            "candidate_id": f"cnpp_{utc_now().replace(':', '').replace('-', '')}_{idx:03d}_{ticker}",
            "ticker": ticker,
            "target_note": surface,
            "issue_code": issue.get("code"),
            "severity": issue.get("severity"),
            "proposal_class": classify_issue(issue),
            "status": candidate_status(issue),
            "main_session_approval_required": True,
            "cron_apply_allowed": False,
            "portfolio_mutation_allowed": False,
            "deployment_authority_allowed": False,
            "trade_execution_allowed": False,
            "mutation_blockers_detected_in_hint": blocked_terms,
            "stale_or_contradictory_claim": issue.get("evidence") or issue.get("message"),
            "why_patch_is_needed": issue.get("message"),
            "proposed_replacement_hint": hint,
            "apply_instruction": "Main session must inspect target note context and apply the smallest exact-text edit only if the evidence is still current. Cron must not apply this candidate.",
            "rollback_note": "Revert the exact text edit if the source artifact was stale, contradicted by primary evidence, or the edit accidentally changes owner approval, sizing, sleeve, execution, or thesis posture.",
            "evidence": {
                "guardrail_generated_at_utc": report.get("generated_at_utc"),
                "guardrail_status": report.get("status"),
                "surface": surface,
                "message": issue.get("message"),
                "excerpt": issue.get("evidence"),
                "risk_record": risks.get(ticker),
            },
        })
    return candidates


def build_stale_intelligence_candidates(report: dict[str, Any], start_index: int = 1) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for offset, finding in enumerate(report.get("findings", []) or [], start=start_index):
        surface = str(finding.get("surface") or "")
        hint = (
            "Review this stale-intelligence finding against current artifacts, then apply the smallest note edit that either "
            "updates the stale state or labels the section draft-only / not canonical. Do not change portfolio weights, owner "
            "approval, sizing, sleeves, execution entitlement, or trade/action authority."
        )
        candidates.append({
            "candidate_id": f"cnpp_{utc_now().replace(':', '').replace('-', '')}_{offset:03d}_STALE_INTEL",
            "ticker": "MULTI" if "ticker" not in finding else finding.get("ticker"),
            "target_note": surface,
            "issue_code": finding.get("code"),
            "severity": finding.get("severity"),
            "proposal_class": "stale_intelligence_guardrail",
            "status": candidate_status(finding),
            "main_session_approval_required": True,
            "cron_apply_allowed": False,
            "portfolio_mutation_allowed": False,
            "deployment_authority_allowed": False,
            "trade_execution_allowed": False,
            "mutation_blockers_detected_in_hint": [],
            "stale_or_contradictory_claim": finding.get("evidence") or finding.get("message"),
            "why_patch_is_needed": finding.get("message"),
            "proposed_replacement_hint": hint,
            "apply_instruction": "Main session must inspect target note context and apply the smallest exact-text edit only if the finding is still current. Cron must not apply this candidate.",
            "rollback_note": "Revert the exact text edit if the source artifact was stale, contradicted by current evidence, or the edit accidentally changes owner approval, sizing, sleeve, execution, or thesis posture.",
            "evidence": {
                "guardrail": "stale_intelligence_guardrail",
                "guardrail_generated_at_utc": report.get("generated_at_utc"),
                "guardrail_status": report.get("status"),
                "surface": surface,
                "message": finding.get("message"),
                "excerpt": finding.get("evidence"),
            },
        })
    return candidates


def build_report() -> dict[str, Any]:
    guardrail = board_canon_guardrail.evaluate()
    stale_guardrail = stale_intelligence_guardrail.evaluate()
    candidates = build_candidates(guardrail)
    candidates.extend(build_stale_intelligence_candidates(stale_guardrail, start_index=len(candidates) + 1))
    summary = {
        "candidate_count": len(candidates),
        "critical_candidates": sum(1 for c in candidates if c.get("severity") == "critical"),
        "warning_candidates": sum(1 for c in candidates if c.get("severity") == "warning"),
        "guardrail_status": guardrail.get("status"),
        "stale_intelligence_status": stale_guardrail.get("status"),
        "below_stop": guardrail.get("summary", {}).get("below_stop", []),
        "near_stop": guardrail.get("summary", {}).get("near_stop", []),
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": utc_now(),
        "status": "proposals_pending_review" if candidates else "no_patch_candidates",
        "authority": {
            "posture": "cron_generates_review_only_canonical_note_patch_proposals",
            "cron_generation_allowed": True,
            "cron_apply_allowed": False,
            "main_session_may_apply_after_review": True,
            "canonical_mutation_scope": "bounded review-only freshness/source-confidence/catalyst-state/technical-state/watch-repair-deployment-state sync only",
            "portfolio_mutation_allowed": False,
            "owner_judgment_promotion_demotion_allowed": False,
            "sizing_or_weight_change_allowed": False,
            "deployment_authority_allowed": False,
            "trade_execution_allowed": False,
        },
        "summary": summary,
        "guardrail": {
            "schema_version": guardrail.get("schema_version"),
            "generated_at_utc": guardrail.get("generated_at_utc"),
            "status": guardrail.get("status"),
            "summary": guardrail.get("summary"),
            "issue_count": len(guardrail.get("issues", []) or []),
        },
        "stale_intelligence_guardrail": {
            "schema_version": stale_guardrail.get("schema_version"),
            "generated_at_utc": stale_guardrail.get("generated_at_utc"),
            "status": stale_guardrail.get("status"),
            "summary": stale_guardrail.get("summary"),
            "finding_count": len(stale_guardrail.get("findings", []) or []),
        },
        "candidates": candidates,
    }


def render_md(report: dict[str, Any]) -> str:
    lines = ["# Canonical Note Patch Proposal", ""]
    lines.append(f"- Generated: `{report['generated_at_utc']}`")
    lines.append(f"- Status: **{report['status']}**")
    auth = report["authority"]
    lines.append("- Authority: cron may generate this proposal; cron may **not** apply it")
    lines.append("- Main-session apply boundary: bounded review-only note freshness/status sync only; no portfolio mutation, approval, sizing, sleeve, execution entitlement, or trade action")
    summary = report["summary"]
    lines.append(f"- Summary: {summary['candidate_count']} candidates; board_guardrail={summary['guardrail_status']}; stale_intelligence={summary['stale_intelligence_status']}; below-stop={', '.join(summary['below_stop']) or '-'}; near-stop={', '.join(summary['near_stop']) or '-'}")
    lines.append("")
    if not report["candidates"]:
        lines.append("No canonical-note patch candidates were generated.")
        lines.append("")
        return "\n".join(lines)
    lines.append("## Candidates")
    for candidate in report["candidates"]:
        lines.append("")
        lines.append(f"### {candidate['ticker']} — {candidate['target_note']}")
        lines.append(f"- Severity: **{candidate['severity']}**")
        lines.append(f"- Issue: `{candidate['issue_code']}`")
        lines.append(f"- Status: `{candidate['status']}`")
        lines.append(f"- Why: {candidate['why_patch_is_needed']}")
        lines.append(f"- Proposed replacement hint: {candidate['proposed_replacement_hint']}")
        lines.append("- Apply instruction: main session must inspect and apply exact text only after review; cron must not apply.")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate review-only canonical-note patch proposals from board/canon guardrail findings.")
    parser.add_argument("--write", action="store_true", help="Write tmp/canonical-note-patch-proposal.json and .md")
    args = parser.parse_args()

    report = build_report()
    if args.write:
        OUT_JSON.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
        OUT_MD.write_text(render_md(report), encoding="utf-8")
        print(f"wrote {OUT_JSON}")
        print(f"wrote {OUT_MD}")
    summary = report["summary"]
    print(
        "canonical_note_patch_proposal: "
        f"{report['status']} ({summary['candidate_count']} candidates; guardrail={summary['guardrail_status']})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
