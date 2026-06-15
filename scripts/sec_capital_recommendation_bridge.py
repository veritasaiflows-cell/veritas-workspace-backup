from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SEC = ROOT / "tmp" / "sec-evidence-packets" / "current-sec-evidence.json"
DEFAULT_CAPITAL = ROOT / "tmp" / "portfolio-mutation-proposals" / "current-capital-deployment-recommendations.json"
DEFAULT_OUTPUT = ROOT / "tmp" / "sec-evidence-packets" / "capital-recommendation-sec-bridge.json"

AUTHORITY = {
    "statement": "Review-only bridge from SEC evidence packets to current capital recommendations. This bridge may support later WF64/WF56 main-session gated workspace maintenance, but it does not clear all freshness gates, apply mutations, infer owner approval, or authorize external action.",
    "review_packet_generation_allowed": True,
    "official_source_evidence_allowed": True,
    "canonical_mutation_allowed_by_this_bridge": False,
    "portfolio_mutation_allowed_by_this_bridge": False,
    "proposal_apply_allowed": False,
    "owner_approval_granted": False,
    "owner_approval_inference_allowed": False,
    "trade_execution_allowed": False,
    "trade_or_account_action_allowed": False,
    "brokerage_account_action_allowed": False,
    "money_movement_allowed": False,
    "capital_action_allowed": False,
}


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


def build_bridge(sec_data: dict[str, Any], capital_data: dict[str, Any]) -> dict[str, Any]:
    sec_by_ticker = {p.get("ticker"): p for p in sec_data.get("packets", []) if isinstance(p, dict)}
    rows = []
    findings = []
    for proposal in capital_data.get("proposals", []):
        ticker = proposal.get("ticker_or_scope")
        sec_packet = sec_by_ticker.get(ticker)
        source_freshness = proposal.get("source_freshness", {}) if isinstance(proposal, dict) else {}
        if not sec_packet:
            findings.append({"severity": "warning", "ticker": ticker, "issue": "missing_sec_packet_for_capital_candidate"})
            rows.append({"ticker": ticker, "status": "missing_sec_packet"})
            continue
        row = {
            "ticker": ticker,
            "status": "ok" if sec_packet.get("status") == "ok" else "warning",
            "capital_proposal_id": proposal.get("proposal_id"),
            "capital_source_freshness_before_sec": source_freshness,
            "sec_evidence_available": sec_packet.get("status") == "ok",
            "sec_company_name": sec_packet.get("company_name"),
            "sec_cik": sec_packet.get("cik"),
            "latest_10k": latest_filing(sec_packet, "10-K"),
            "latest_10q": latest_filing(sec_packet, "10-Q"),
            "latest_8k": latest_filing(sec_packet, "8-K"),
            "sec_concepts_available": sorted((sec_packet.get("retrievals", {}).get("concepts", {}) or {}).keys()),
            "bridge_judgment": "SEC filing/company-fact evidence is available for review. Do not mark the capital packet fully fresh or apply-ready until downstream WF65/WF66 freshness/conflict validators consume this evidence and any non-SEC stale/manual blockers are resolved.",
            "recommended_next_step": f"Use this {ticker} row as Option D input for WF65/WF66 freshness/conflict validation; do not change owner files unless a separate WF64/WF56 gated apply passes.",
            "authority": AUTHORITY,
        }
        rows.append(row)
    critical = 0
    warning = len([f for f in findings if f.get("severity") == "warning"])
    return {
        "schema_version": 1,
        "generated_at_utc": utc_now(),
        "status": "warning" if warning else "ok",
        "source_artifacts": [rel(DEFAULT_SEC), rel(DEFAULT_CAPITAL)],
        "authority": AUTHORITY,
        "summary": {"capital_candidates_checked": len(rows), "critical": critical, "warning": warning},
        "rows": rows,
        "findings": findings,
    }


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(path)


def write_md(path: Path, data: dict[str, Any]) -> None:
    lines = ["# Capital Recommendation SEC Bridge", ""]
    lines.append(f"- Generated: `{data.get('generated_at_utc')}`")
    lines.append(f"- Status: **{data.get('status')}**")
    lines.append("- Authority: review-only bridge; no owner approval, no direct workspace mutation, no account action, no trade authority.")
    lines.append("")
    lines.append("| Ticker | Status | CIK | Latest 10-K | Latest 10-Q | Latest 8-K | Next step |")
    lines.append("|---|---|---|---|---|---|---|")
    for row in data.get("rows", []):
        def date(field: str) -> str:
            value = row.get(field)
            return value.get("filing_date", "") if isinstance(value, dict) else ""
        lines.append(f"| {row.get('ticker')} | {row.get('status')} | {row.get('sec_cik','')} | {date('latest_10k')} | {date('latest_10q')} | {date('latest_8k')} | {row.get('recommended_next_step','')} |")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Bridge SEC evidence packets into current capital recommendation review candidates.")
    parser.add_argument("--sec", default=str(DEFAULT_SEC))
    parser.add_argument("--capital", default=str(DEFAULT_CAPITAL))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    args = parser.parse_args()
    data = build_bridge(load_json(Path(args.sec)), load_json(Path(args.capital)))
    out = Path(args.output)
    write_json(out, data)
    write_md(out.with_suffix(".md"), data)
    print(json.dumps({"status": data["status"], "summary": data["summary"], "output": rel(out)}, sort_keys=True))
    return 1 if data["summary"]["critical"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
