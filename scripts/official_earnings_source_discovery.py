"""Read-only SEC filing discovery for missed official earnings periods.

The existing official-capture registry can only see files that already exist.
This module supplies the missing upstream signal: the latest reported period
visible in SEC submissions and, when available, its 8-K Exhibit 99 earnings
release.  It never writes workspace state or grants finance authority.
"""

from __future__ import annotations

import re
from datetime import date, datetime, timedelta
from typing import Any, Callable

import requests

SEC_USER_AGENT = "Veritas OpenClaw Research veritasaiflows@gmail.com"
SEC_SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"
SEC_ARCHIVE_ROOT = "https://www.sec.gov/Archives/edgar/data"
EARNINGS_SIGNALS = (
    "earnings",
    "financial results",
    "quarterly results",
    "results of operations",
    "news release",
)
IRRELEVANT_EXHIBIT_SIGNALS = (
    "employment",
    "compensation",
    "credit agreement",
    "indenture",
    "governance",
    "proxy",
    "agreement",
)


def normalize_cik(value: str | int) -> str:
    digits = re.sub(r"\D", "", str(value))
    return digits.zfill(10)


def cik_from_source_url(source_url: str | None) -> str | None:
    if not source_url:
        return None
    match = re.search(r"/data/(\d{4,})/", source_url, flags=re.I)
    return normalize_cik(match.group(1)) if match else None


def parse_date(value: Any) -> date | None:
    if not value:
        return None
    try:
        return datetime.strptime(str(value)[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def period_slug(period_end: str) -> str:
    parsed = parse_date(period_end)
    if not parsed:
        return "period-" + str(period_end).replace("-", "")
    quarter = ((parsed.month - 1) // 3) + 1
    return f"q{quarter}-{parsed.year}"


def period_label(period_end: str) -> str:
    slug = period_slug(period_end)
    if slug.startswith("q") and "-" in slug:
        quarter, year = slug.split("-", 1)
        return f"Q{quarter[1:]} {year}"
    return str(period_end)


def _fetch_json(url: str, timeout_seconds: int) -> dict[str, Any]:
    response = requests.get(url, headers={"User-Agent": SEC_USER_AGENT}, timeout=timeout_seconds)
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, dict):
        raise ValueError(f"SEC response was not an object: {url}")
    return payload


def _archive_url(cik: str, accession: str, filename: str) -> str:
    accession_path = accession.replace("-", "")
    return f"{SEC_ARCHIVE_ROOT}/{int(cik)}/{accession_path}/{filename}"


def _filing_url(accession: str, cik: str) -> str:
    accession_path = accession.replace("-", "")
    return f"{SEC_ARCHIVE_ROOT}/{int(cik)}/{accession_path}/{accession}-index.htm"


def _exhibit_candidate(item: dict[str, Any], *, report_date: date, filing_date: date) -> dict[str, Any] | None:
    """Return a ranked, fail-closed candidate for a contemporaneous 8-K earnings exhibit.

    SEC archive filenames are inconsistent.  The filename is only a candidate
    signal: normalised Exhibit 99 forms are accepted only after obvious
    non-earnings exhibits are rejected and deterministic contemporaneous-score
    checks pass.  This function does not fetch or interpret financial values.
    """

    name = str(item.get("name") or "")
    lower = name.lower()
    if not lower.endswith((".htm", ".html")) or "index" in lower or "header" in lower:
        return None
    normalized = re.sub(r"[^a-z0-9]", "", lower)
    # Covers ex99.htm, ex991.htm, ex99_1.htm, exhibit99.htm, and
    # exhibit99_1.htm while rejecting arbitrary references to 99 elsewhere.
    exhibit_match = re.search(r"(?:exhibit|ex)99[0-9]*(?:htm|html)$", normalized)
    if not exhibit_match:
        return None

    description = " ".join(
        str(item.get(key) or "")
        for key in ("description", "type", "title", "content", "text")
    ).lower()
    combined = f"{lower} {description}"
    if any(signal in combined for signal in IRRELEVANT_EXHIBIT_SIGNALS):
        return None

    modified = parse_date(item.get("last-modified") or item.get("last_modified") or item.get("date"))
    if modified and abs((modified - filing_date).days) > 21:
        return None

    score = 10  # Candidate belongs to an 8-K selected inside the filing window.
    signals = ["form_8k"]
    if "exhibit99" in normalized:
        score += 48
        signals.append("literal_exhibit_99")
    else:
        score += 44
        signals.append("normalized_ex99_variant")
    if report_date.strftime("%Y%m%d") in normalized:
        score += 15
        signals.append("report_date_in_filename")
    if any(signal in combined for signal in EARNINGS_SIGNALS):
        score += 25
        signals.append("earnings_content_signal")
    if modified:
        score += 5
        signals.append("archive_item_date_near_filing")
    # A filename-only normalized ex99 variant still needs its 8-K filing-window
    # context.  This threshold rejects weak or malformed names without guessing.
    if score < 54:
        return None
    return {"name": name, "score": score, "signals": signals}


def _index_exhibit(index_payload: dict[str, Any], *, report_date: date, filing_date: date) -> dict[str, Any] | None:
    directory = index_payload.get("directory")
    items = directory.get("item") if isinstance(directory, dict) else []
    candidates: list[dict[str, Any]] = []
    for item in items if isinstance(items, list) else []:
        if isinstance(item, dict):
            candidate = _exhibit_candidate(item, report_date=report_date, filing_date=filing_date)
            if candidate:
                candidates.append(candidate)
    if not candidates:
        return None
    candidates.sort(key=lambda item: (-int(item["score"]), str(item["name"]).lower()))
    return candidates[0]


def _submission_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    recent = payload.get("filings", {}).get("recent") if isinstance(payload.get("filings"), dict) else {}
    if not isinstance(recent, dict):
        return []
    keys = ("form", "filingDate", "accessionNumber", "primaryDocument", "primaryDocDescription", "reportDate")
    length = max((len(recent.get(key, [])) for key in keys), default=0)
    rows: list[dict[str, Any]] = []
    for index in range(length):
        rows.append({key: (recent.get(key, [None] * length)[index] if index < len(recent.get(key, [])) else None) for key in keys})
    return rows


def discover_from_sec_payload(
    *,
    ticker: str,
    cik: str,
    submissions: dict[str, Any],
    index_payloads: dict[str, dict[str, Any]] | None = None,
    current_period_end: str | None = None,
    index_fetcher: Callable[[str], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Resolve a newer SEC quarterly report and a same-window earnings release."""

    current = parse_date(current_period_end)
    rows = _submission_rows(submissions)
    reports: list[dict[str, Any]] = []
    for row in rows:
        form = str(row.get("form") or "").upper()
        report_date = parse_date(row.get("reportDate"))
        filing_date = parse_date(row.get("filingDate"))
        accession = str(row.get("accessionNumber") or "")
        if form not in {"10-Q", "10-K"} or not report_date or not filing_date or not accession:
            continue
        if current and report_date <= current:
            continue
        reports.append({**row, "form": form, "report_date": report_date.isoformat(), "filing_date": filing_date.isoformat()})

    if not reports:
        return {
            "status": "current",
            "ticker": ticker,
            "cik": normalize_cik(cik),
            "current_period_end": current_period_end,
            "latest_detected_period_end": current_period_end,
            "source_discovery": "sec_submissions",
        }

    reports.sort(key=lambda row: (str(row["report_date"]), str(row["filing_date"]), str(row["accessionNumber"])))
    report = reports[-1]
    report_date = parse_date(report["report_date"])
    filing_date = parse_date(report["filing_date"])
    release_rows = []
    for row in rows:
        if str(row.get("form") or "").upper() != "8-K":
            continue
        release_date = parse_date(row.get("filingDate"))
        accession = str(row.get("accessionNumber") or "")
        if not release_date or not accession or not filing_date:
            continue
        if abs((release_date - filing_date).days) <= 7:
            release_rows.append({**row, "form": "8-K", "release_date": release_date.isoformat()})
    release_rows.sort(key=lambda row: (abs((parse_date(row["release_date"]) - filing_date).days), str(row["release_date"]), str(row.get("accessionNumber"))))

    index_payloads = index_payloads or {}
    for release in release_rows:
        accession = str(release["accessionNumber"])
        index_url = f"{_archive_url(normalize_cik(cik), accession, 'index.json')}"
        try:
            index_payload = index_payloads.get(accession)
            if index_payload is None and index_fetcher:
                index_payload = index_fetcher(index_url)
            exhibit = _index_exhibit(index_payload or {}, report_date=report_date, filing_date=filing_date)
        except Exception:
            exhibit = None
        if not exhibit:
            continue
        release_source = _archive_url(normalize_cik(cik), accession, str(exhibit["name"]))
        return {
            "status": "new_source_detected",
            "ticker": ticker,
            "cik": normalize_cik(cik),
            "current_period_end": current_period_end,
            "latest_detected_period_end": report["report_date"],
            "period_slug": period_slug(report["report_date"]),
            "period_label": period_label(report["report_date"]),
            "report_form": report["form"],
            "report_filing_date": report["filing_date"],
            "report_accession_number": report["accessionNumber"],
            "report_source_url": _archive_url(
                normalize_cik(cik),
                str(report["accessionNumber"]),
                str(report.get("primaryDocument") or ""),
            ),
            "report_filing_url": _filing_url(str(report["accessionNumber"]), normalize_cik(cik)),
            "report_source_type": "sec_10q_official_report" if report["form"] == "10-Q" else "sec_10k_official_report",
            "release_filing_date": release["release_date"],
            "accession_number": accession,
            "source_url": release_source,
            "filing_url": _filing_url(accession, normalize_cik(cik)),
            "source_title": f"{ticker} {period_label(report['report_date'])} SEC earnings release",
            "source_type": "sec_8k_exhibit_99_1",
            "source_discovery": "sec_submissions_and_archive_index",
            "candidate_score": exhibit["score"],
            "candidate_evidence": exhibit["signals"],
        }

    primary = str(report.get("primaryDocument") or "")
    if primary:
        accession = str(report["accessionNumber"])
        return {
            "status": "new_period_source_manual_required",
            "ticker": ticker,
            "cik": normalize_cik(cik),
            "current_period_end": current_period_end,
            "latest_detected_period_end": report["report_date"],
            "period_slug": period_slug(report["report_date"]),
            "period_label": period_label(report["report_date"]),
            "report_form": report["form"],
            "report_filing_date": report["filing_date"],
            "report_accession_number": accession,
            "accession_number": accession,
            "source_url": _archive_url(normalize_cik(cik), accession, primary),
            "filing_url": _filing_url(accession, normalize_cik(cik)),
            "source_title": f"{ticker} {period_label(report['report_date'])} SEC filing",
            "source_type": "sec_10q_official_report" if report["form"] == "10-Q" else "sec_10k_official_report",
            "source_discovery": "sec_submissions_without_8k_exhibit",
        }
    return {
        "status": "new_period_source_manual_required",
        "ticker": ticker,
        "cik": normalize_cik(cik),
        "current_period_end": current_period_end,
        "latest_detected_period_end": report["report_date"],
        "period_slug": period_slug(report["report_date"]),
        "period_label": period_label(report["report_date"]),
        "report_form": report["form"],
        "report_filing_date": report["filing_date"],
        "report_accession_number": report["accessionNumber"],
        "source_discovery": "sec_submissions_without_source_document",
    }


def discover_latest_sec_report(
    *,
    ticker: str,
    cik: str,
    current_period_end: str | None = None,
    timeout_seconds: int = 20,
) -> dict[str, Any]:
    normalized = normalize_cik(cik)
    try:
        submissions_url = SEC_SUBMISSIONS_URL.format(cik=normalized)
        submissions = _fetch_json(submissions_url, timeout_seconds)
        return discover_from_sec_payload(
            ticker=ticker,
            cik=normalized,
            submissions=submissions,
            current_period_end=current_period_end,
            index_fetcher=lambda url: _fetch_json(url, timeout_seconds),
        )
    except Exception as exc:  # fail closed at the guard layer; preserve the cause in its artifact
        return {
            "status": "discovery_error",
            "ticker": ticker,
            "cik": normalized,
            "current_period_end": current_period_end,
            "source_discovery": "sec_submissions",
            "error": f"{type(exc).__name__}: {exc}",
        }
