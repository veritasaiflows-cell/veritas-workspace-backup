from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SEC_SKILL_DIR = ROOT / "skills" / "sec"
SEC_SCRIPT_DIR = SEC_SKILL_DIR / "scripts"
DEFAULT_OUTPUT = ROOT / "tmp" / "sec-evidence-packets" / "current-sec-evidence.json"
DEFAULT_TICKERS = ["GOOG", "GS", "MSFT", "ETN"]
SCHEMA_VERSION = 1

CONCEPTS_BY_TICKER = {
    "GS": ["Assets", "Liabilities", "StockholdersEquity", "NetIncomeLoss"],
    # Keep v1 concept retrieval to USD concepts because the adopted SEC skill's
    # get_company_concept helper currently summarizes USD units only. Share-count
    # concepts can be added after a unit-aware wrapper is implemented.
    "DEFAULT": ["Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax", "NetIncomeLoss", "Assets"],
}

AUTHORITY = {
    "statement": "Official SEC/EDGAR evidence packet for WF65/WF66 review support. It may support later main-session WF64/WF56 workspace portfolio/canon maintenance only through separate exact gated apply artifacts and validators.",
    "review_packet_generation_allowed": True,
    "official_source_evidence_allowed": True,
    "main_session_gated_workspace_mutation_possible_later": True,
    "canonical_mutation_allowed_by_this_packet": False,
    "portfolio_mutation_allowed_by_this_packet": False,
    "proposal_apply_allowed": False,
    "owner_approval_granted": False,
    "owner_approval_inference_allowed": False,
    "trade_execution_allowed": False,
    "trade_or_account_action_allowed": False,
    "brokerage_account_action_allowed": False,
    "money_movement_allowed": False,
    "sizing_allocation_action_allowed": False,
    "model_ranked_deployment_allowed": False,
}

FORBIDDEN_TEXT = [
    "win probability",
    "win rate",
    "expected return",
    "calibrated score",
    "model-ranked",
    "model ranked",
    "owner approved",
    "trade approved",
]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return str(path)


def sha256_file(path: Path) -> str | None:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return None


def latest_fact_unit(metric: dict[str, Any]) -> dict[str, Any] | None:
    if not isinstance(metric, dict):
        return None
    units = metric.get("units")
    if not isinstance(units, dict):
        return None
    candidates: list[dict[str, Any]] = []
    for unit_name, rows in units.items():
        if not isinstance(rows, list):
            continue
        for row in rows:
            if isinstance(row, dict):
                enriched = dict(row)
                enriched["unit"] = unit_name
                candidates.append(enriched)
    if not candidates:
        return None
    return max(candidates, key=lambda row: (str(row.get("end", "")), str(row.get("filed", "")), str(row.get("form", ""))))


def summarize_key_metrics(company_facts: dict[str, Any]) -> dict[str, Any]:
    metrics = company_facts.get("key_metrics")
    if not isinstance(metrics, dict):
        return {}
    out: dict[str, Any] = {}
    for key, value in metrics.items():
        if isinstance(value, dict) and value:
            out[key] = {
                "value": value.get("value"),
                "end_date": value.get("end_date"),
                "form": value.get("form"),
                "filed": value.get("filed"),
            }
    return out


def concept_summary(concept_result: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(concept_result, dict) or concept_result.get("error"):
        return {"status": "missing", "error": concept_result.get("error") if isinstance(concept_result, dict) else "invalid_result"}
    annual = concept_result.get("annual_data") if isinstance(concept_result.get("annual_data"), list) else []
    quarterly = concept_result.get("quarterly_data") if isinstance(concept_result.get("quarterly_data"), list) else []
    latest_annual = annual[0] if annual else None
    latest_quarterly = quarterly[0] if quarterly else None
    return {
        "status": "ok" if (latest_annual or latest_quarterly) else "empty",
        "label": concept_result.get("label"),
        "description": concept_result.get("description"),
        "latest_annual": latest_annual,
        "latest_quarterly": latest_quarterly,
        "annual_rows": len(annual),
        "quarterly_rows": len(quarterly),
    }


async def build_packet_for_ticker(tools: Any, ticker: str, *, forms: list[str], filing_limit: int) -> dict[str, Any]:
    ticker = ticker.upper().strip()
    filings_by_form: dict[str, Any] = {}
    for form in forms:
        filings_by_form[form] = await tools.get_company_filings(ticker=ticker, form_type=form, limit=filing_limit)

    company_facts = await tools.get_company_facts(ticker=ticker)
    concepts = CONCEPTS_BY_TICKER.get(ticker, CONCEPTS_BY_TICKER["DEFAULT"])
    concept_results: dict[str, Any] = {}
    for concept in concepts:
        concept_results[concept] = concept_summary(await tools.get_company_concept(ticker=ticker, concept=concept))

    first_ok = next((value for value in filings_by_form.values() if isinstance(value, dict) and not value.get("error")), {})
    errors = []
    for form, result in filings_by_form.items():
        if isinstance(result, dict) and result.get("error"):
            errors.append({"source": f"filings:{form}", "error": result.get("error")})
    if isinstance(company_facts, dict) and company_facts.get("error"):
        errors.append({"source": "company_facts", "error": company_facts.get("error")})
    for concept, result in concept_results.items():
        if result.get("status") == "missing":
            errors.append({"source": f"concept:{concept}", "error": result.get("error")})

    filings_summary = {}
    for form, result in filings_by_form.items():
        filings = result.get("filings") if isinstance(result, dict) else []
        latest = filings[0] if isinstance(filings, list) and filings else None
        filings_summary[form] = {
            "status": "ok" if latest else "missing",
            "company_name": result.get("company_name") if isinstance(result, dict) else None,
            "cik": result.get("cik") if isinstance(result, dict) else None,
            "latest": latest,
            "count": len(filings) if isinstance(filings, list) else 0,
        }

    return {
        "ticker": ticker,
        "status": "warning" if errors else "ok",
        "company_name": first_ok.get("company_name") or (company_facts.get("company_name") if isinstance(company_facts, dict) else None),
        "cik": first_ok.get("cik") or (company_facts.get("cik") if isinstance(company_facts, dict) else None),
        "evidence_class": "official_sec_edgar",
        "retrievals": {
            "filings": filings_summary,
            "company_facts": {
                "status": "error" if isinstance(company_facts, dict) and company_facts.get("error") else "ok",
                "sic": company_facts.get("sic") if isinstance(company_facts, dict) else None,
                "sic_description": company_facts.get("sic_description") if isinstance(company_facts, dict) else None,
                "key_metrics": summarize_key_metrics(company_facts) if isinstance(company_facts, dict) else {},
            },
            "concepts": concept_results,
        },
        "findings": errors,
        "provenance": {
            "source_system": "SEC EDGAR",
            "producer_script": "scripts/sec_evidence_packet.py",
            "sec_skill_script": rel(SEC_SCRIPT_DIR / "sec_finance_ai.py"),
            "sec_skill_sha256": sha256_file(SEC_SCRIPT_DIR / "sec_finance_ai.py"),
            "retrieved_at_utc": utc_now(),
            "forms_requested": forms,
            "concepts_requested": concepts,
        },
        "authority": AUTHORITY,
    }


async def build_packet(tickers: list[str], *, forms: list[str], filing_limit: int) -> dict[str, Any]:
    if str(SEC_SCRIPT_DIR) not in sys.path:
        sys.path.insert(0, str(SEC_SCRIPT_DIR))
    from sec_finance_ai import SEC_HEADERS, Tools  # type: ignore

    tools = Tools()
    packets = []
    for ticker in tickers:
        packets.append(await build_packet_for_ticker(tools, ticker, forms=forms, filing_limit=filing_limit))
    critical = 0
    warning = sum(1 for packet in packets if packet.get("status") == "warning")
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": utc_now(),
        "status": "warning" if warning else "ok",
        "evidence_class": "official_sec_edgar",
        "tickers": [ticker.upper().strip() for ticker in tickers],
        "authority": AUTHORITY,
        "sec_user_agent": SEC_HEADERS.get("User-Agent"),
        "summary": {"tickers_checked": len(packets), "critical": critical, "warning": warning},
        "packets": packets,
        "option_path": {
            "option_a_status": "implemented_review_only_sidecar",
            "option_b_next": "Use this packet as fallback when provider data is stale, missing, or contradictory.",
            "option_c_next": "Promote SEC as primary source for filing dates, CIK/accession, company facts, and selected official concepts.",
            "option_d_next": "Feed validated SEC evidence into WF65/WF66 and capital recommendation freshness gates; main-session workspace mutation remains only through WF64/WF56 gated apply artifacts.",
        },
    }


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(path)


def write_markdown(path: Path, data: dict[str, Any]) -> None:
    md = ["# SEC Evidence Packet", ""]
    md.append(f"- Generated: `{data.get('generated_at_utc')}`")
    md.append(f"- Status: **{data.get('status')}**")
    md.append("- Authority: review-only official-source evidence; SEC packet alone does not allow canon/portfolio mutation, owner approval, account action, money movement, or trades. Main-session workspace maintenance may occur only later through WF64/WF56 gated apply proof.")
    md.append("")
    md.append("## Tickers")
    md.append("| Ticker | Company | CIK | Status | Latest 10-K | Latest 10-Q | Latest 8-K | Warnings |")
    md.append("|---|---|---|---|---|---|---|---:|")
    for packet in data.get("packets", []):
        filings = packet.get("retrievals", {}).get("filings", {})
        def latest_date(form: str) -> str:
            latest = filings.get(form, {}).get("latest") if isinstance(filings.get(form), dict) else None
            return latest.get("filing_date", "") if isinstance(latest, dict) else ""
        md.append(f"| {packet.get('ticker')} | {packet.get('company_name') or ''} | {packet.get('cik') or ''} | {packet.get('status')} | {latest_date('10-K')} | {latest_date('10-Q')} | {latest_date('8-K')} | {len(packet.get('findings', []))} |")
    md.append("")
    md.append("## Option path")
    option_path = data.get("option_path", {})
    for key, value in option_path.items():
        md.append(f"- `{key}`: {value}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(md) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build review-only SEC/EDGAR evidence packets for Veritas WF65/WF66.")
    parser.add_argument("--tickers", nargs="+", default=DEFAULT_TICKERS)
    parser.add_argument("--forms", nargs="+", default=["10-K", "10-Q", "8-K"])
    parser.add_argument("--filing-limit", type=int, default=2)
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--markdown", default="")
    args = parser.parse_args()
    data = asyncio.run(build_packet(args.tickers, forms=args.forms, filing_limit=args.filing_limit))
    output = Path(args.output)
    write_json(output, data)
    md_path = Path(args.markdown) if args.markdown else output.with_suffix(".md")
    write_markdown(md_path, data)
    print(json.dumps({"status": data.get("status"), "output": rel(output), "markdown": rel(md_path), "summary": data.get("summary")}, sort_keys=True))
    return 0 if data.get("summary", {}).get("critical", 0) == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
