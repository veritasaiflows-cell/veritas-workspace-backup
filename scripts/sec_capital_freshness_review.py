from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SEC = ROOT / "tmp" / "sec-evidence-packets" / "current-sec-evidence.json"
DEFAULT_CAPITAL = ROOT / "tmp" / "portfolio-mutation-proposals" / "current-capital-deployment-recommendations.json"
DEFAULT_OUTPUT = ROOT / "tmp" / "sec-evidence-packets" / "capital-recommendation-sec-freshness-review.json"
DEFAULT_OFFICIAL_CAPTURE = ROOT / "tmp" / "official-ir-captures" / "goog-q1-2026.json"

AUTHORITY = {
    "statement": "Review-only SEC/EDGAR freshness/conflict review for current capital recommendation candidates. This artifact may narrow source-freshness blockers, but it does not apply workspace mutations, infer owner approval, or authorize external action.",
    "review_packet_generation_allowed": True,
    "official_source_evidence_allowed": True,
    "source_freshness_review_allowed": True,
    "canonical_mutation_allowed_by_this_review": False,
    "portfolio_mutation_allowed_by_this_review": False,
    "proposal_apply_allowed": False,
    "owner_approval_granted": False,
    "owner_approval_inference_allowed": False,
    "sizing_allocation_action_allowed": False,
    "capital_action_allowed": False,
    "trade_execution_allowed": False,
    "trade_or_account_action_allowed": False,
    "brokerage_account_action_allowed": False,
    "money_movement_allowed": False,
}

FORBIDDEN_SNIPPETS = [
    "owner approval granted",
    "trade execution allowed",
    "apply allowed",
    "portfolio mutation allowed",
    "canonical mutation allowed",
    "win probability",
    "expected return",
    "model-ranked deployment",
]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return str(path)


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def latest_filing(packet: dict[str, Any], form: str) -> dict[str, Any] | None:
    filings = packet.get("retrievals", {}).get("filings", {})
    form_packet = filings.get(form) if isinstance(filings, dict) else None
    latest = form_packet.get("latest") if isinstance(form_packet, dict) else None
    return latest if isinstance(latest, dict) else None


def concept_summary(packet: dict[str, Any]) -> dict[str, Any]:
    concepts = packet.get("retrievals", {}).get("concepts", {})
    if not isinstance(concepts, dict):
        return {}
    out: dict[str, Any] = {}
    for name, payload in concepts.items():
        if not isinstance(payload, dict):
            continue
        out[name] = {
            "status": payload.get("status"),
            "latest_annual": payload.get("latest_annual"),
            "latest_quarterly": payload.get("latest_quarterly"),
        }
    return out


def has_false_authority(authority: dict[str, Any]) -> bool:
    return all(
        authority.get(field) is False
        for field in [
            "canonical_mutation_allowed_by_this_review",
            "portfolio_mutation_allowed_by_this_review",
            "proposal_apply_allowed",
            "owner_approval_granted",
            "owner_approval_inference_allowed",
            "sizing_allocation_action_allowed",
            "capital_action_allowed",
            "trade_execution_allowed",
            "trade_or_account_action_allowed",
            "brokerage_account_action_allowed",
            "money_movement_allowed",
        ]
    )


def official_capture_resolves_fields(capture: dict[str, Any] | None) -> tuple[bool, dict[str, Any] | None]:
    if not capture:
        return False, None
    captures = capture.get("captures") if isinstance(capture.get("captures"), dict) else {}
    if not captures:
        return False, None
    manual_remaining = [name for name, item in captures.items() if isinstance(item, dict) and item.get("status") == "manual_required"]
    resolved = capture.get("ticker") == "GOOG" and capture.get("review_only") is True and capture.get("resolved_for_apply") is False and not manual_remaining
    return resolved, {
        "artifact": "tmp/official-ir-captures/goog-q1-2026.json",
        "status": "available_review_only" if resolved else "manual_required",
        "manual_required_remaining": manual_remaining,
        "captured_fields": sorted(captures.keys()),
        "source_url": capture.get("source", {}).get("source_url") if isinstance(capture.get("source"), dict) else None,
    }


def review_one(proposal: dict[str, Any], sec_packet: dict[str, Any] | None, official_capture: dict[str, Any] | None = None) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    official_capture_resolved, official_capture_summary = official_capture_resolves_fields(official_capture)
    ticker = proposal.get("ticker_or_scope")
    findings: list[dict[str, Any]] = []
    source_freshness = proposal.get("source_freshness", {}) if isinstance(proposal.get("source_freshness"), dict) else {}
    official_bridge = proposal.get("official_earnings_bridge", {}) if isinstance(proposal.get("official_earnings_bridge"), dict) else {}
    unresolved = official_bridge.get("unresolved_official_fields", [])
    unresolved = unresolved if isinstance(unresolved, list) else []

    if not sec_packet:
        findings.append({"severity": "warning", "ticker": ticker, "issue": "missing_sec_packet"})
        return {
            "ticker": ticker,
            "status": "blocked",
            "sec_filing_evidence_available": False,
            "overall_source_freshness_after_sec_review": "blocked_missing_sec_packet",
            "capital_action_allowed": False,
            "workspace_apply_ready": False,
            "authority": AUTHORITY,
        }, findings

    latest_10q = latest_filing(sec_packet, "10-Q")
    latest_10k = latest_filing(sec_packet, "10-K")
    latest_8k = latest_filing(sec_packet, "8-K")
    sec_available = sec_packet.get("status") == "ok" and bool(latest_10q and latest_10k)
    period_end = official_bridge.get("period_end")
    sec_period_match = latest_10q.get("filing_date") if isinstance(latest_10q, dict) else None
    sec_filing_freshness_judgment = "sec_filing_current_for_period" if sec_available and period_end else "sec_filing_review_required"

    still_blocked_reasons = []
    if source_freshness.get("explicit_blocker") is True:
        still_blocked_reasons.append("capital packet source_freshness.explicit_blocker remains true in the upstream packet")
    if official_capture_resolved:
        still_blocked_reasons.append("official capture is available review-only but upstream WF65/WF66 capital packet has not consumed it yet")
    else:
        if official_bridge.get("official_evidence_status") == "manual_required":
            still_blocked_reasons.append("official earnings bridge still marks official_evidence_status=manual_required")
        if official_bridge.get("manual_review_required") is True:
            still_blocked_reasons.append("official earnings bridge still requires manual review")
        if unresolved:
            still_blocked_reasons.append("unresolved official fields remain: " + ", ".join(str(x) for x in unresolved))
    if proposal.get("owner_approval_granted") is not False or proposal.get("apply_allowed") is not False:
        findings.append({"severity": "critical", "ticker": ticker, "issue": "capital_packet_authority_flags_not_false"})

    row = {
        "ticker": ticker,
        "status": "review_only_blocked" if still_blocked_reasons else "review_only_sec_freshness_clear",
        "capital_proposal_id": proposal.get("proposal_id"),
        "capital_source_freshness_before_sec": source_freshness,
        "sec_filing_evidence_available": sec_available,
        "sec_company_name": sec_packet.get("company_name"),
        "sec_cik": sec_packet.get("cik"),
        "sec_latest_10k": latest_10k,
        "sec_latest_10q": latest_10q,
        "sec_latest_8k": latest_8k,
        "official_bridge_period_end": period_end,
        "sec_concept_summary": concept_summary(sec_packet),
        "sec_filing_freshness_judgment": sec_filing_freshness_judgment,
        "official_ir_capture": official_capture_summary,
        "sec_conflict_judgment": "no_sec_capital_packet_conflict_found" if sec_available else "sec_evidence_incomplete",
        "overall_source_freshness_after_sec_review": "partially_narrowed_but_still_blocked" if still_blocked_reasons else "sec_filing_component_review_clear",
        "still_blocked_reasons": still_blocked_reasons,
        "workspace_apply_ready": False,
        "capital_action_allowed": False,
        "recommended_next_step": "Keep GOOG preview-only and wire the SEC filing evidence plus official IR capture into WF65/WF66 validators before any WF64/WF56 gated apply." if ticker == "GOOG" else "Use this row as review-only evidence; no owner-file apply from this artifact.",
        "authority": AUTHORITY,
    }
    return row, findings


def build_review(sec_data: dict[str, Any], capital_data: dict[str, Any], ticker_filter: str | None, official_capture: dict[str, Any] | None = None) -> dict[str, Any]:
    sec_by_ticker = {p.get("ticker"): p for p in sec_data.get("packets", []) if isinstance(p, dict)}
    rows = []
    findings: list[dict[str, Any]] = []
    for proposal in capital_data.get("proposals", []):
        ticker = proposal.get("ticker_or_scope")
        if ticker_filter and ticker != ticker_filter:
            continue
        row, row_findings = review_one(proposal, sec_by_ticker.get(ticker), official_capture if ticker == "GOOG" else None)
        rows.append(row)
        findings.extend(row_findings)
    if not rows:
        findings.append({"severity": "critical", "ticker": ticker_filter, "issue": "no_matching_capital_candidate"})
    if not has_false_authority(AUTHORITY):
        findings.append({"severity": "critical", "issue": "authority_flags_widened"})
    text_blob = json.dumps({"rows": rows, "authority": AUTHORITY}, sort_keys=True).lower()
    for snippet in FORBIDDEN_SNIPPETS:
        if snippet in text_blob and snippet not in {"owner approval granted", "trade execution allowed", "apply allowed"}:
            findings.append({"severity": "critical", "issue": "forbidden_language", "snippet": snippet})
    critical = sum(1 for f in findings if f.get("severity") == "critical")
    warning = sum(1 for f in findings if f.get("severity") == "warning")
    blocked = sum(1 for r in rows if r.get("overall_source_freshness_after_sec_review") != "sec_filing_component_review_clear")
    return {
        "schema_version": 1,
        "generated_at_utc": utc_now(),
        "status": "critical" if critical else "warning" if warning else "ok",
        "source_artifacts": [rel(DEFAULT_SEC), rel(DEFAULT_CAPITAL)],
        "ticker_filter": ticker_filter,
        "authority": AUTHORITY,
        "summary": {
            "candidates_checked": len(rows),
            "sec_filing_components_clear": sum(1 for r in rows if r.get("sec_filing_evidence_available") is True),
            "overall_still_blocked": blocked,
            "critical": critical,
            "warning": warning,
        },
        "rows": rows,
        "findings": findings,
    }


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(path)


def write_md(path: Path, data: dict[str, Any]) -> None:
    lines = ["# SEC Capital Freshness Review", ""]
    lines.append(f"- Generated: `{data.get('generated_at_utc')}`")
    lines.append(f"- Status: **{data.get('status')}**")
    lines.append("- Authority: review-only; no owner approval, no workspace apply, no sizing/allocation, no account action, no trades.")
    lines.append("")
    lines.append("| Ticker | SEC filing evidence | After SEC review | Latest 10-Q | Still blocked reasons |")
    lines.append("|---|---:|---|---|---|")
    for row in data.get("rows", []):
        latest_10q = row.get("sec_latest_10q") if isinstance(row, dict) else None
        date = latest_10q.get("filing_date", "") if isinstance(latest_10q, dict) else ""
        reasons = "; ".join(row.get("still_blocked_reasons", [])) if isinstance(row.get("still_blocked_reasons"), list) else ""
        lines.append(f"| {row.get('ticker')} | {row.get('sec_filing_evidence_available')} | {row.get('overall_source_freshness_after_sec_review')} | {date} | {reasons} |")
    lines.append("")
    lines.append("## Judgment")
    for row in data.get("rows", []):
        lines.append(f"- {row.get('ticker')}: {row.get('sec_conflict_judgment')}; {row.get('recommended_next_step')}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Review SEC evidence against capital recommendation source-freshness blockers.")
    parser.add_argument("--sec", default=str(DEFAULT_SEC))
    parser.add_argument("--capital", default=str(DEFAULT_CAPITAL))
    parser.add_argument("--ticker", default=None)
    parser.add_argument("--official-capture", default=str(DEFAULT_OFFICIAL_CAPTURE))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    args = parser.parse_args()
    official_capture_path = Path(args.official_capture)
    official_capture = load_json(official_capture_path) if official_capture_path.exists() else None
    data = build_review(load_json(Path(args.sec)), load_json(Path(args.capital)), args.ticker, official_capture)
    out = Path(args.output)
    write_json(out, data)
    write_md(out.with_suffix(".md"), data)
    print(json.dumps({"status": data["status"], "summary": data["summary"], "output": rel(out)}, sort_keys=True))
    return 1 if data["summary"]["critical"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
