from __future__ import annotations

"""Shared WF70 helpers for review-only official SEC/IR capture scripts.

This module centralizes repeated capture plumbing (authority block, source fetch,
HTML extraction, evidence claims, artifact writing, and batch execution) without
adding ticker coverage or granting portfolio/canon/trade/account authority.
Existing ticker-specific scripts can import these helpers incrementally while
preserving their field-level capture logic and output semantics.
"""

import hashlib
import html
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

import requests

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "tmp" / "official-ir-captures"
USER_AGENT = "Veritas OpenClaw Research veritasaiflows@gmail.com"

AUTHORITY: dict[str, Any] = {
    "statement": "Review-only official SEC/IR earnings capture. This artifact captures official-source evidence only and does not apply workspace changes, infer approval, or authorize external action.",
    "review_packet_generation_allowed": True,
    "official_source_evidence_allowed": True,
    "canonical_note_mutation_allowed": False,
    "portfolio_mutation_allowed": False,
    "deployment_authority_allowed": False,
    "owner_approval_inferred": False,
    "owner_approval_granted": False,
    "proposal_apply_allowed": False,
    "sizing_allocation_action_allowed": False,
    "sizing_sleeve_cash_risk_rule_authority": False,
    "trade_execution_allowed": False,
    "trade_or_account_action_allowed": False,
    "brokerage_account_action_allowed": False,
    "money_movement_allowed": False,
}

AUTHORITY_SUMMARY_MD = "Authority: review-only; no owner approval, no workspace apply, no sizing/allocation, no account action, no trades."


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return str(path)


def fetch_source(url: str, timeout: int = 45) -> str:
    response = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=timeout)
    response.raise_for_status()
    return response.text


def html_to_text(raw: str) -> str:
    text = re.sub(r"(?is)<script.*?</script>|<style.*?</style>", " ", raw)
    text = re.sub(r"(?i)<br\s*/?>|</p>|</div>|</tr>|</li>|</td>|</th>", "\n", text)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text).replace("\xa0", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n", text)
    return text.strip()


def compact(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def excerpt_around(text: str, needle: str, chars: int = 1000, fallback_to_start: bool = False) -> str:
    idx = text.lower().find(needle.lower())
    if idx < 0:
        return compact(text[:chars]) if fallback_to_start else ""
    start = max(0, idx - chars // 3)
    end = min(len(text), idx + chars)
    return compact(text[start:end])


def first_excerpt(text: str, *needles: str, chars: int = 1000, fallback_to_start: bool = False) -> str:
    for needle in needles:
        found = excerpt_around(text, needle, chars=chars, fallback_to_start=False)
        if found:
            return found
    return compact(text[:chars]) if fallback_to_start else ""


def claim(source_url: str, status: str, value: Any, section: str, excerpt: str, note: str | None = None) -> dict[str, Any]:
    return {
        "status": status,
        "value": value,
        "source_url": source_url,
        "source_section": section,
        "excerpt": excerpt,
        "capture_date_utc": utc_now(),
        "inferred": False,
        "note": note,
    }


def apply_period_to_captures(captures: dict[str, Any], period: str) -> dict[str, Any]:
    for block in captures.values():
        if isinstance(block, dict):
            block.setdefault("period", period)
    return captures


def official_source_metadata(meta: Mapping[str, Any], text: str, raw_html: str) -> dict[str, Any]:
    return {
        "source_type": meta["source_type"],
        "source_url": meta["source_url"],
        "filing_url": meta["filing_url"],
        "accession_number": meta["accession_number"],
        "source_title": meta["source_title"],
        "retrieved_at_utc": utc_now(),
        "sec_user_agent": USER_AGENT,
        "source_text_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "source_html_sha256": hashlib.sha256(raw_html.encode("utf-8")).hexdigest(),
    }


def capture_summary(captures: Mapping[str, Mapping[str, Any]], note: str) -> dict[str, Any]:
    return {
        "official_fields_checked": len(captures),
        "official_captured_or_not_disclosed": sum(
            1 for capture in captures.values()
            if capture.get("status") in {"official_captured", "not_disclosed_in_release", "partial", "not_applicable"}
        ),
        "manual_required_remaining": sum(1 for capture in captures.values() if capture.get("status") == "manual_required"),
        "apply_ready": False,
        "note": note,
    }


def build_capture_document(
    *,
    ticker: str,
    meta: Mapping[str, Any],
    captures: dict[str, Any],
    text: str,
    raw_html: str,
    summary_note: str,
) -> dict[str, Any]:
    apply_period_to_captures(captures, str(meta["period_end"]))
    return {
        "schema_version": 1,
        "ticker": ticker,
        "company_name": meta["company_name"],
        "period_end": meta["period_end"],
        "generated_at_utc": utc_now(),
        "review_only": True,
        "resolved_for_apply": False,
        "source": official_source_metadata(meta, text, raw_html),
        "authority": AUTHORITY,
        "captures": captures,
        "summary": capture_summary(captures, summary_note),
    }


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(path)


def write_md(path: Path, data: dict[str, Any], authority_line: str = AUTHORITY_SUMMARY_MD, period_label: str = "Q1 2026") -> None:
    lines = [f"# {data['ticker']} {period_label} Official IR Capture", ""]
    lines.append(f"- Generated: `{data.get('generated_at_utc')}`")
    lines.append(f"- Source: `{data.get('source', {}).get('source_url')}`")
    lines.append(f"- {authority_line}")
    lines.append("")
    lines.append("| Field | Status | Value / note |")
    lines.append("|---|---|---|")
    for name, capture in data.get("captures", {}).items():
        value = capture.get("value")
        note = capture.get("note") or ""
        compact_value = json.dumps(value, sort_keys=True) if isinstance(value, (dict, list)) else str(value)
        compact_value = compact_value.replace("|", "\\|")[:650]
        lines.append(f"| `{name}` | {capture.get('status')} | {compact_value}; {note} |")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_capture_batch(
    *,
    sources: Mapping[str, Mapping[str, Any]],
    selected_tickers: Sequence[str] | None,
    build_capture: Callable[[str, str, str], dict[str, Any]],
    text_converter: Callable[[str], str] = html_to_text,
    period_slug: str = "q1-2026",
    period_label: str = "Q1 2026",
    write_markdown: bool = False,
) -> dict[str, Any]:
    tickers = list(selected_tickers) if selected_tickers else sorted(sources)
    outputs: list[dict[str, Any]] = []
    for ticker in tickers:
        raw = fetch_source(str(sources[ticker]["source_url"]))
        text = text_converter(raw)
        data = build_capture(ticker, text, raw)
        out = OUT_DIR / f"{ticker.lower()}-{period_slug}.json"
        write_json(out, data)
        if write_markdown:
            write_md(out.with_suffix(".md"), data, period_label=period_label)
        outputs.append({"ticker": ticker, "output": rel(out), "summary": data["summary"]})
    return {"status": "ok", "outputs": outputs}
