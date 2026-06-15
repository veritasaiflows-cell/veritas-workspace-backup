from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

WORKSPACE = Path(__file__).resolve().parents[1]
TMP = WORKSPACE / "tmp"
SNAPSHOT = WORKSPACE / "03. Portfolio" / "Portfolio Snapshot.md"
FULL_VIEW = TMP / "full-portfolio-view.json"
OUT_JSON = TMP / "portfolio-snapshot-patch-proposal.json"
OUT_MD = TMP / "portfolio-snapshot-patch-proposal.md"
SCHEMA_VERSION = 1

DATE_RE = re.compile(r"- \*\*Date:\*\*\s*([^\n]+)")
DATA_AS_OF_RE = re.compile(r"- \*\*Data as of:\*\*\s*([^\n]+)")
LAST_UPDATED_RE = re.compile(r"- \*\*Last updated:\*\*\s*([^\n]+)")


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat(timespec="seconds").replace("+00:00", "Z")


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace") if path.exists() else ""


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def extract(pattern: re.Pattern[str], text: str) -> str | None:
    match = pattern.search(text)
    return match.group(1).strip() if match else None


def clean_date(value: str | None) -> str | None:
    if not value:
        return None
    match = re.search(r"(20\d{2}-\d{2}-\d{2})", value)
    return match.group(1) if match else value.strip()


def note_freshness(note_text: str) -> dict[str, str | None]:
    return {
        "date": extract(DATE_RE, note_text),
        "date_clean": clean_date(extract(DATE_RE, note_text)),
        "data_as_of": extract(DATA_AS_OF_RE, note_text),
        "data_as_of_clean": clean_date(extract(DATA_AS_OF_RE, note_text)),
        "last_updated": extract(LAST_UPDATED_RE, note_text),
        "last_updated_clean": clean_date(extract(LAST_UPDATED_RE, note_text)),
    }


def current_priority_summary(full_view: dict[str, Any]) -> str:
    summary = full_view.get("summary", {}) if isinstance(full_view.get("summary"), dict) else {}
    deployable = ", ".join(summary.get("deployable_now_review_only", []) or []) or "none"
    prepare = ", ".join(summary.get("prepare_or_wait", []) or []) or "none"
    below_stop = ", ".join(summary.get("below_stop", []) or []) or "none"
    near_stop = ", ".join(summary.get("near_stop", []) or []) or "none"
    return (
        f"Machine view shows deployable-now/review-only: {deployable}; prepare/wait: {prepare}; "
        f"below-stop/do-not-touch: {below_stop}; near-stop: {near_stop}."
    )


def build_freshness_candidate(note_text: str, full_view: dict[str, Any]) -> dict[str, Any] | None:
    market_data_as_of = str(full_view.get("market_data_as_of") or "").strip()
    if not market_data_as_of:
        return None
    freshness = note_freshness(note_text)
    stale_fields = [
        field for field in ("date_clean", "data_as_of_clean", "last_updated_clean")
        if freshness.get(field) and freshness.get(field) != market_data_as_of
    ]
    missing_fields = [field for field in ("date", "data_as_of", "last_updated") if not freshness.get(field)]
    if not stale_fields and not missing_fields:
        return None
    old_header_lines = []
    new_header_lines = []
    date_match = DATE_RE.search(note_text)
    data_match = DATA_AS_OF_RE.search(note_text)
    last_match = LAST_UPDATED_RE.search(note_text)
    if date_match:
        old_header_lines.append(date_match.group(0))
        new_header_lines.append(f"- **Date:** {market_data_as_of}")
    if data_match:
        old_header_lines.append(data_match.group(0))
        new_header_lines.append(f"- **Data as of:** {market_data_as_of} close")
    if last_match:
        old_header_lines.append(last_match.group(0))
        new_header_lines.append(f"- **Last updated:** {market_data_as_of} — review-only freshness/status sync candidate from full portfolio machine view; no weight, cash, sleeve, owner-approval, execution entitlement, or trade change")
    return {
        "candidate_id": f"pspp_{utc_now().replace(':', '').replace('-', '')}_001_freshness_header",
        "target_note": str(SNAPSHOT.relative_to(WORKSPACE)),
        "proposal_class": "portfolio_snapshot_freshness_sync",
        "severity": "warning",
        "status": "proposed_for_main_session_review",
        "main_session_approval_required": True,
        "cron_apply_allowed": False,
        "canonical_auto_apply_allowed": False,
        "portfolio_mutation_allowed": False,
        "owner_judgment_promotion_demotion_allowed": False,
        "sizing_or_weight_change_allowed": False,
        "deployment_authority_allowed": False,
        "trade_execution_allowed": False,
        "why_patch_is_needed": f"Portfolio Snapshot freshness fields do not match full portfolio machine view market_data_as_of={market_data_as_of}.",
        "current_note_freshness": freshness,
        "target_market_data_as_of": market_data_as_of,
        "current_machine_summary": current_priority_summary(full_view),
        "exact_old_text": "\n".join(old_header_lines),
        "proposed_new_text": "\n".join(new_header_lines),
        "apply_instruction": "Main session may apply only after inspecting current artifacts and confirming this is a freshness/status sync. Do not change draft weights, cash, sleeves, owner approval, sizing, execution entitlement, or trade action.",
        "rollback_note": "Restore the previous header/freshness lines if the machine view was stale or contradicted by live artifacts.",
        "evidence": {
            "full_portfolio_view_generated_at_utc": full_view.get("generated_at_utc"),
            "full_portfolio_view_market_data_as_of": market_data_as_of,
            "source_artifacts": full_view.get("source_artifacts"),
            "summary": full_view.get("summary"),
        },
    }


def build_report() -> dict[str, Any]:
    note_text = read_text(SNAPSHOT)
    full_view = read_json(FULL_VIEW)
    candidates = []
    freshness_candidate = build_freshness_candidate(note_text, full_view)
    if freshness_candidate:
        candidates.append(freshness_candidate)
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": utc_now(),
        "status": "proposals_pending_review" if candidates else "no_patch_candidates",
        "authority": {
            "posture": "review_only_portfolio_snapshot_patch_proposals",
            "cron_generation_allowed": True,
            "cron_apply_allowed": False,
            "main_session_may_apply_after_review": True,
            "canonical_mutation_scope": "bounded freshness/status sync only",
            "portfolio_mutation_allowed": False,
            "owner_judgment_promotion_demotion_allowed": False,
            "sizing_or_weight_change_allowed": False,
            "deployment_authority_allowed": False,
            "trade_execution_allowed": False,
        },
        "summary": {
            "candidate_count": len(candidates),
            "target_note": str(SNAPSHOT.relative_to(WORKSPACE)),
            "full_portfolio_view_market_data_as_of": full_view.get("market_data_as_of"),
            "note_freshness": note_freshness(note_text),
        },
        "candidates": candidates,
    }


def render_md(report: dict[str, Any]) -> str:
    lines = ["# Portfolio Snapshot Patch Proposal", ""]
    lines.append(f"- Generated: `{report['generated_at_utc']}`")
    lines.append(f"- Status: **{report['status']}**")
    lines.append("- Authority: review-only proposal; cron may generate but must not apply")
    lines.append("- Boundary: no weight, cash, sleeve, owner-approval, execution entitlement, or trade/action changes")
    lines.append("")
    if not report["candidates"]:
        lines.append("No Portfolio Snapshot patch candidates were generated.")
        return "\n".join(lines) + "\n"
    lines.append("## Candidates")
    for candidate in report["candidates"]:
        lines.append("")
        lines.append(f"### {candidate['proposal_class']}")
        lines.append(f"- Severity: **{candidate['severity']}**")
        lines.append(f"- Why: {candidate['why_patch_is_needed']}")
        lines.append(f"- Current machine summary: {candidate['current_machine_summary']}")
        lines.append("- Exact old text:")
        lines.append("```markdown")
        lines.append(candidate.get("exact_old_text") or "")
        lines.append("```")
        lines.append("- Proposed new text:")
        lines.append("```markdown")
        lines.append(candidate.get("proposed_new_text") or "")
        lines.append("```")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate review-only Portfolio Snapshot patch proposals from full portfolio view evidence.")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    report = build_report()
    if args.write:
        OUT_JSON.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
        OUT_MD.write_text(render_md(report), encoding="utf-8")
        print(f"wrote {OUT_JSON}")
        print(f"wrote {OUT_MD}")
    print(f"portfolio_snapshot_patch_proposal: {report['status']} ({report['summary']['candidate_count']} candidates)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
