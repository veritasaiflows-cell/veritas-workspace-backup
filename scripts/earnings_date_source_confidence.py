"""earnings_date_source_confidence.py

Read-only source-confidence packet for timing-sensitive earnings dates.

The script starts from tmp/portfolio-config.json -> earnings_date_watchlist and
compares each configured baseline to provider evidence in tmp/earnings-calendar.json.
It can consume a browser-confirmation sidecar artifact when one exists, then
probes configured primary-source URLs where available. Blocked or inconclusive
primary fetches stay visible as trust limits; yfinance/provider evidence alone
is never promoted to primary confirmation.

Usage:
    python scripts/earnings_date_source_confidence.py [--write-md]

Outputs:
    tmp/earnings-date-source-confidence.json
    optional Markdown digest when --write-md is supplied
"""

from __future__ import annotations

import argparse
import json
import re
import urllib.error
import urllib.request
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from official_capture_period_registry import CAPTURE_SCRIPT_BY_TICKER

WORKSPACE = Path(__file__).resolve().parents[1]
TMP = WORKSPACE / "tmp"
CONFIG_PATH = TMP / "portfolio-config.json"
EARNINGS_PATH = TMP / "earnings-calendar.json"
IR_METADATA_PATH = WORKSPACE / "data" / "fundamentals" / "company-ir-metadata.json"
BROWSER_CONFIRMATION_PATH = TMP / "earnings-date-browser-confirmation.json"
OUT_JSON = TMP / "earnings-date-source-confidence.json"
OUT_MD = OUT_JSON.with_suffix(".md")
TIMEOUT_SECONDS = 12

WATCHLIST_CONFIG_FIELD = "earnings_date_watchlist"

PRIMARY_SOURCE_PROBES: dict[str, list[dict[str, str]]] = {
    "NVDA": [
        {
            "id": "nvidia_ir_events",
            "source_type": "company_ir",
            "url": "https://investor.nvidia.com/events-and-presentations/events-and-presentations/default.aspx",
            "note": "NVIDIA IR events and presentations page; may return bot-protection/403 from this runtime.",
        },
        {
            "id": "nvidia_newsroom",
            "source_type": "company_newsroom",
            "url": "https://nvidianews.nvidia.com/news/",
            "note": "NVIDIA newsroom fallback. Useful only if it names the earnings event/date explicitly.",
        },
    ],
}

DEFAULT_VERIFICATION_SITES: dict[str, list[dict[str, str]]] = {
    "NVDA": [
        {
            "label": "NVIDIA Investor Relations - Events & Presentations",
            "url": "https://investor.nvidia.com/events-and-presentations/events-and-presentations/default.aspx",
            "source_type": "company_ir",
        },
        {
            "label": "NVIDIA Newsroom",
            "url": "https://nvidianews.nvidia.com/news/",
            "source_type": "company_newsroom",
        },
        {
            "label": "SEC EDGAR - NVIDIA filings",
            "url": "https://www.sec.gov/edgar/browse/?CIK=1045810",
            "source_type": "sec",
        },
    ],
}

GENERIC_VERIFICATION_SITES: list[dict[str, str]] = [
    {
        "label": "Company investor relations events page",
        "url": "Use the company's official investor relations events/calendar page.",
        "source_type": "company_ir",
    },
    {
        "label": "Company newsroom / press releases",
        "url": "Use the company's official newsroom or press releases page.",
        "source_type": "company_newsroom",
    },
    {
        "label": "SEC EDGAR company filings",
        "url": "https://www.sec.gov/edgar/searchedgar/companysearch",
        "source_type": "sec",
    },
]

MONTH_NAMES = (
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
)

OFFICIAL_BROWSER_SOURCE_TYPES = {"company_ir", "company_newsroom", "company_release", "sec_filing", "sec"}


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_json(path: Path) -> dict[str, Any]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return raw if isinstance(raw, dict) else {}


def parse_iso_date(value: Any) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except Exception:
        return None


def load_watchlist(config: dict[str, Any], earnings: dict[str, Any]) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    raw = config.get(WATCHLIST_CONFIG_FIELD)
    out: dict[str, dict[str, Any]] = {}
    if isinstance(raw, dict):
        for ticker, value in raw.items():
            if not isinstance(ticker, str) or not ticker.strip():
                continue
            clean = ticker.strip().upper()
            if isinstance(value, dict):
                out[clean] = dict(value)
            else:
                out[clean] = {"date": value}
    if out:
        return out, {"source": "portfolio_config_watchlist", "fallback_used": False}

    # The legacy config is retired.  Keep timing coverage reviewable by using
    # the bounded official-capture scope and provider date only as the target
    # to verify; no provider date is promoted to primary confirmation.
    records = earnings_records_by_ticker(earnings)
    for ticker in sorted(CAPTURE_SCRIPT_BY_TICKER):
        provider = records.get(ticker, {})
        out[ticker] = {
            "date": provider.get("next_earnings_date"),
            "primary_confirmed": False,
            "scope_source": "official_capture_registry_fallback",
        }
    return out, {
        "source": "official_capture_registry_fallback",
        "fallback_used": True,
        "ticker_count": len(out),
    }


def earnings_records_by_ticker(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    records: dict[str, dict[str, Any]] = {}
    for rec in payload.get("records", []):
        if isinstance(rec, dict) and rec.get("ticker"):
            records[str(rec["ticker"]).upper()] = rec
    return records


def browser_records_by_ticker(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    records: dict[str, dict[str, Any]] = {}
    for rec in payload.get("records", []):
        if isinstance(rec, dict) and rec.get("ticker"):
            records[str(rec["ticker"]).upper()] = rec
    return records


def configured_primary_evidence_valid(entry: dict[str, Any], target_date: date | None) -> bool:
    """Accept manual primary-confirmed flags only with explicit evidence metadata."""
    if not bool(entry.get("primary_confirmed")) or target_date is None:
        return False
    evidence = entry.get("primary_evidence")
    if not isinstance(evidence, dict):
        return False
    evidence_date = parse_iso_date(evidence.get("date") or evidence.get("matched_date"))
    source_type = str(evidence.get("source_type") or evidence.get("source") or "").strip()
    url = str(evidence.get("url") or "").strip()
    matched_text = str(evidence.get("matched_text") or evidence.get("title") or "").strip()
    return bool(evidence_date == target_date and source_type in OFFICIAL_BROWSER_SOURCE_TYPES and url and matched_text)


def browser_confirms_target_date(record: dict[str, Any] | None, target_date: date | None) -> bool:
    """Accept only explicit official-source browser evidence.

    The browser sidecar is allowed to help with 403/bot-protected pages, but it
    cannot turn vague provider evidence or a mere page visit into primary truth.
    """
    if not record or target_date is None:
        return False
    status = str(record.get("confirmation_status") or "")
    source_type = str(record.get("source_type") or "")
    evidence_date = parse_iso_date(record.get("evidence_date") or record.get("matched_date"))
    matched_text = str(record.get("matched_text") or "").strip()
    url = str(record.get("url") or "").strip()
    if status != "primary_confirmed":
        return False
    if source_type not in OFFICIAL_BROWSER_SOURCE_TYPES:
        return False
    if evidence_date != target_date:
        return False
    if not matched_text or not url:
        return False
    return True


def metadata_by_ticker(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows = payload.get("tickers") if isinstance(payload.get("tickers"), dict) else {}
    return {
        str(ticker).upper(): value
        for ticker, value in rows.items()
        if isinstance(value, dict)
    }


def verification_sites_for_ticker(ticker: str, metadata: dict[str, Any] | None = None) -> list[dict[str, str]]:
    sites = list(DEFAULT_VERIFICATION_SITES.get(ticker, []))
    metadata = metadata if isinstance(metadata, dict) else {}
    for key, label in (
        ("ir_home_url", "Company investor relations"),
        ("earnings_url", "Company quarterly earnings"),
        ("guidance_url", "Company guidance / investor relations"),
    ):
        url = str(metadata.get(key) or "").strip()
        if url and url.startswith("https://") and not any(site.get("url") == url for site in sites):
            sites.append({"label": label, "url": url, "source_type": "company_ir"})
    return sites or GENERIC_VERIFICATION_SITES


def primary_probes_for_ticker(ticker: str, metadata: dict[str, Any] | None = None) -> list[dict[str, str]]:
    probes = list(PRIMARY_SOURCE_PROBES.get(ticker, []))
    metadata = metadata if isinstance(metadata, dict) else {}
    for key, label in (("earnings_url", "company_earnings"), ("ir_home_url", "company_ir")):
        url = str(metadata.get(key) or "").strip()
        if url and url.startswith("https://") and not any(probe.get("url") == url for probe in probes):
            probes.append({
                "id": f"{ticker.lower()}_{label}",
                "source_type": "company_ir",
                "url": url,
                "note": "Maintained official IR metadata; confirm only an explicit matching earnings date.",
            })
    return probes


def fetch_url(url: str) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "VeritasOpenClaw/1.0 earnings-date-source-confidence; owner=local-workspace",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            raw = response.read(800_000)
            encoding = response.headers.get_content_charset() or "utf-8"
            return {
                "fetch_status": "ok",
                "http_status": int(response.status),
                "body": raw.decode(encoding, errors="replace"),
                "error": None,
            }
    except urllib.error.HTTPError as exc:
        return {
            "fetch_status": "http_error",
            "http_status": int(exc.code),
            "body": "",
            "error": str(exc),
        }
    except Exception as exc:
        return {
            "fetch_status": "error",
            "http_status": None,
            "body": "",
            "error": str(exc),
        }


def body_mentions_target_date(body: str, target: date) -> bool:
    if not body:
        return False
    iso = target.isoformat()
    month = MONTH_NAMES[target.month - 1]
    compact_patterns = [
        iso,
        f"{month} {target.day}, {target.year}",
        f"{month} {target.day} {target.year}",
        f"{month[:3]} {target.day}, {target.year}",
        f"{month[:3]}. {target.day}, {target.year}",
    ]
    lowered = re.sub(r"\s+", " ", body).lower()
    if not any(pattern.lower() in lowered for pattern in compact_patterns):
        return False
    context_terms = ("earnings", "results", "quarter", "financial results", "conference call")
    return any(term in lowered for term in context_terms)


def classify_primary_probes(ticker: str, target_date: date | None, probes: list[dict[str, str]]) -> tuple[str, list[dict[str, Any]], list[str]]:
    probe_results: list[dict[str, Any]] = []
    warnings: list[str] = []
    if not probes:
        return "no_primary_probe_configured", probe_results, warnings
    if target_date is None:
        return "missing_target_date", probe_results, [f"{ticker}: missing configured target date"]

    saw_blocked = False
    saw_ok = False
    for probe in probes:
        result = fetch_url(probe["url"])
        fetch_status = result.get("fetch_status")
        http_status = result.get("http_status")
        body = str(result.get("body") or "")
        matched = fetch_status == "ok" and body_mentions_target_date(body, target_date)
        probe_result = {
            "id": probe.get("id"),
            "source_type": probe.get("source_type"),
            "url": probe.get("url"),
            "note": probe.get("note"),
            "fetch_status": fetch_status,
            "http_status": http_status,
            "matched_target_date": matched,
            "error": result.get("error"),
        }
        probe_results.append(probe_result)
        if matched:
            return "primary_confirmed", probe_results, warnings
        if fetch_status == "ok":
            saw_ok = True
        if http_status in (401, 403, 429) or fetch_status == "error":
            saw_blocked = True

    if saw_blocked:
        warnings.append(f"{ticker}: primary source fetch blocked or errored; keep provider estimate unconfirmed")
        return "blocked_primary_fetch", probe_results, warnings
    if saw_ok:
        warnings.append(f"{ticker}: primary source reachable but target date not confirmed in fetched content")
        return "primary_source_no_date_match", probe_results, warnings
    return "primary_unconfirmed", probe_results, warnings


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write-md", action="store_true", help="Also write optional Markdown digest.")
    args = parser.parse_args(argv)
    config = load_json(CONFIG_PATH)
    earnings = load_json(EARNINGS_PATH)
    ir_metadata = load_json(IR_METADATA_PATH)
    browser_confirmation = load_json(BROWSER_CONFIRMATION_PATH) if BROWSER_CONFIRMATION_PATH.exists() else {}
    watchlist, scope = load_watchlist(config, earnings)
    earnings_records = earnings_records_by_ticker(earnings)
    browser_records = browser_records_by_ticker(browser_confirmation)
    metadata_records = metadata_by_ticker(ir_metadata)

    records: list[dict[str, Any]] = []
    warnings: list[str] = []
    for ticker, entry in sorted(watchlist.items()):
        configured_date = parse_iso_date(entry.get("date"))
        provider_record = earnings_records.get(ticker, {})
        ticker_metadata = metadata_records.get(ticker, {})
        provider_date = parse_iso_date(provider_record.get("next_earnings_date"))
        browser_record = browser_records.get(ticker)
        browser_primary_confirmed = browser_confirms_target_date(browser_record, configured_date)
        existing_primary_flag = bool(entry.get("primary_confirmed"))
        configured_evidence_valid = configured_primary_evidence_valid(entry, configured_date)
        if browser_primary_confirmed:
            primary_status = "browser_primary_confirmed"
            probe_results: list[dict[str, Any]] = []
            probe_warnings: list[str] = []
        elif configured_evidence_valid:
            primary_status = "configured_primary_evidence"
            probe_results = []
            probe_warnings = []
        else:
            primary_status, probe_results, probe_warnings = classify_primary_probes(
                ticker,
                configured_date,
                primary_probes_for_ticker(ticker, ticker_metadata),
            )
        warnings.extend(probe_warnings)

        provider_matches_config = bool(configured_date and provider_date and configured_date == provider_date)
        if existing_primary_flag and not configured_evidence_valid:
            warnings.append(f"{ticker}: primary_confirmed flag ignored because primary_evidence metadata is missing or invalid")
        if browser_primary_confirmed:
            confidence = "primary_confirmed"
        elif primary_status == "primary_confirmed" or configured_evidence_valid:
            confidence = "primary_confirmed"
        elif provider_matches_config:
            confidence = "provider_estimate_unconfirmed"
        elif provider_date:
            confidence = "provider_date_conflicts_with_config"
            warnings.append(f"{ticker}: configured date and provider date differ")
        else:
            confidence = "missing_provider_date"
            warnings.append(f"{ticker}: provider date missing")

        records.append({
            "ticker": ticker,
            "configured_date": configured_date.isoformat() if configured_date else None,
            "configured_primary_confirmed": existing_primary_flag,
            "configured_primary_evidence_valid": configured_evidence_valid,
            "configured_primary_evidence": entry.get("primary_evidence") if isinstance(entry.get("primary_evidence"), dict) else None,
            "provider_next_earnings_date": provider_date.isoformat() if provider_date else None,
            "provider_source": provider_record.get("source"),
            "provider_fetched_at_utc": provider_record.get("fetched_at_utc"),
            "provider_matches_config": provider_matches_config,
            "verification_sites": verification_sites_for_ticker(ticker, ticker_metadata),
            "browser_confirmation": browser_record,
            "browser_primary_confirmed": browser_primary_confirmed,
            "source_confidence": confidence,
            "primary_confirmation_status": primary_status,
            "primary_probe_results": probe_results,
            "recommended_action": (
                "eligible_to_mark_primary_confirmed" if confidence == "primary_confirmed"
                else "keep_timing_sensitive_until_primary_confirmed"
            ),
            "authority": "review_only_no_canonical_mutation",
        })

    if scope.get("fallback_used"):
        warnings.append("portfolio-config watchlist unavailable; using the bounded official-capture scope for review-only date coverage")
    status = "ok" if not warnings else "partial"
    payload = {
        "generated_at_utc": utc_now_iso(),
        "status": status,
        "expected_update_window": "Run after earnings_calendar_enrichment.py for timing-sensitive earnings-date baselines.",
        "authority": "review_only_no_canonical_mutation",
        "source_policy": "Provider dates can support timing review, but only primary company/SEC evidence can justify primary-confirmed language; manual primary-confirmed flags require matching primary_evidence metadata. If yfinance/provider evidence is missing, contradictory, or unconfirmed, responses and review packets should include official sites where Randall can verify the date.",
        "inputs": {
            "portfolio_config": str(CONFIG_PATH.relative_to(WORKSPACE)),
            "earnings_calendar": str(EARNINGS_PATH.relative_to(WORKSPACE)),
            "browser_confirmation": str(BROWSER_CONFIRMATION_PATH.relative_to(WORKSPACE)) if BROWSER_CONFIRMATION_PATH.exists() else None,
            "browser_confirmation_generated_at_utc": browser_confirmation.get("generated_at_utc"),
            "earnings_generated_at_utc": earnings.get("generated_at_utc"),
            "company_ir_metadata": (
                str(IR_METADATA_PATH.relative_to(WORKSPACE))
                if IR_METADATA_PATH.is_relative_to(WORKSPACE)
                else str(IR_METADATA_PATH)
            ),
        },
        "scope": scope,
        "summary": {
            "ticker_count": len(records),
            "primary_confirmed_count": sum(1 for row in records if row.get("source_confidence") == "primary_confirmed"),
            "primary_unconfirmed_count": sum(1 for row in records if row.get("source_confidence") != "primary_confirmed"),
            "missing_provider_date_count": sum(1 for row in records if row.get("source_confidence") == "missing_provider_date"),
        },
        "warnings": warnings,
        "records": records,
    }
    OUT_JSON.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    lines = [
        "# Earnings Date Source Confidence",
        "",
        f"Generated: {payload['generated_at_utc']}",
        f"Status: {status}",
        "",
        "Review-only. This packet does not edit the Event Calendar or promote provider evidence to primary confirmation.",
        "",
    ]
    if warnings:
        lines.extend(["## Warnings", ""])
        lines.extend(f"- {warning}" for warning in warnings)
        lines.append("")
    lines.extend([
        "## Timing-sensitive dates",
        "",
        "| Ticker | Configured date | Provider date | Source confidence | Primary status | Action |",
        "|---|---:|---:|---|---|---|",
    ])
    if records:
        for row in records:
            lines.append(
                f"| {row['ticker']} | {row['configured_date'] or '—'} | {row['provider_next_earnings_date'] or '—'} "
                f"| {row['source_confidence']} | {row['primary_confirmation_status']} | {row['recommended_action']} |"
            )
    else:
        lines.append("| — | — | — | — | — | No timing-sensitive dates configured |")
    lines.append("")
    lines.extend(["## Verification sites", ""])
    if records:
        for row in records:
            lines.append(f"### {row['ticker']}")
            for site in row.get("verification_sites") or []:
                lines.append(f"- {site['label']}: {site['url']}")
            lines.append("")
    else:
        lines.append("- No timing-sensitive dates configured.")
    lines.extend([
        "",
        "## Boundary",
        "",
        "If primary fetch is blocked or inconclusive, keep Event Calendar wording as `per provider estimate; not primary-confirmed`.",
    ])
    if args.write_md:
        OUT_MD.write_text("\n".join(lines), encoding="utf-8")

    print("earnings date source-confidence records:", len(records))
    for row in records:
        print(f"  {row['ticker']}: {row['source_confidence']} ({row['primary_confirmation_status']})")
    if warnings:
        print("warnings:")
        for warning in warnings:
            print("  -", warning)
    print("wrote", OUT_JSON)
    if args.write_md:
        print("wrote", OUT_MD)


if __name__ == "__main__":
    main()
