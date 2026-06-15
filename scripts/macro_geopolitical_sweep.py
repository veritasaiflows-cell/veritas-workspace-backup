#!/usr/bin/env python3
"""Build a cron-fed review-only geopolitical official-source sweep.

The sweep collects titles/links from official RSS/Atom surfaces and labels
macro-relevant keywords. It is a routing artifact only; it does not assert that
an event is market-moving, true beyond the source, or actionable.
"""
from __future__ import annotations

import argparse
import json
import re
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from market_data_utils import atomic_write_json, atomic_write_text

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
DEFAULT_JSON = TMP / "macro-geopolitical-sweep.json"
DEFAULT_MD = TMP / "macro-geopolitical-sweep.md"

SCHEMA = "veritas.macro_geopolitical_sweep.v1"
USER_AGENT = "Veritas OpenClaw Macro Geopolitical Sweep veritasaiflows@gmail.com"

SOURCES = [
    {
        "source_id": "white_house",
        "label": "White House Briefing Room",
        "url": "https://www.whitehouse.gov/briefing-room/feed/",
        "source_type": "official_government_feed",
    },
    {
        "source_id": "state_department",
        "label": "U.S. State Department",
        "url": "https://www.state.gov/rss-feed/",
        "source_type": "official_government_feed",
    },
    {
        "source_id": "treasury_press",
        "label": "U.S. Treasury Press Releases",
        "url": "https://home.treasury.gov/news/press-releases/rss",
        "source_type": "official_government_feed",
    },
    {
        "source_id": "defense_news",
        "label": "U.S. Department of Defense News",
        "url": "https://www.defense.gov/DesktopModules/ArticleCS/RSS.ashx?ContentType=1&Site=945",
        "source_type": "official_government_feed",
    },
]

KEYWORD_BUCKETS = {
    "energy_supply": ["oil", "crude", "energy", "opec", "lng", "gas", "shipping", "strait", "hormuz"],
    "trade_tariff": ["tariff", "trade", "export control", "import", "semiconductor", "sanction"],
    "defense_conflict": ["ukraine", "russia", "china", "taiwan", "middle east", "iran", "israel", "nato", "missile", "defense"],
    "financial_sanctions": ["sanction", "ofac", "treasury", "blocked property", "financial network"],
}

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "headline_truth_claim_allowed": False,
    "forecast_or_probability_claim_allowed": False,
    "portfolio_or_canon_mutation_allowed": False,
    "paper_or_live_execution_allowed": False,
    "owner_approval_inferred": False,
    "capital_action_allowed": False,
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_date(value: str | None) -> str | None:
    if not value:
        return None
    try:
        dt = parsedate_to_datetime(value)
    except Exception:
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except Exception:
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def fetch_source(source: dict[str, Any], timeout: int) -> dict[str, Any]:
    started = time.monotonic()
    result: dict[str, Any] = {
        "source_id": source["source_id"],
        "label": source["label"],
        "url": source["url"],
        "source_type": source["source_type"],
        "status": "ok",
        "duration_seconds": None,
        "error_class": None,
        "error": None,
        "items": [],
    }
    try:
        req = Request(source["url"], headers={"User-Agent": USER_AGENT})
        with urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", errors="replace")
    except (HTTPError, URLError, TimeoutError, OSError) as exc:
        result["status"] = "unavailable"
        result["duration_seconds"] = round(time.monotonic() - started, 3)
        result["error_class"] = exc.__class__.__name__
        result["error"] = str(exc)
        return result

    try:
        root = ET.fromstring(body)
    except ET.ParseError as exc:
        result["status"] = "unavailable"
        result["duration_seconds"] = round(time.monotonic() - started, 3)
        result["error_class"] = exc.__class__.__name__
        result["error"] = str(exc)
        return result

    items = []
    for node in root.findall(".//item")[:30]:
        title = (node.findtext("title") or "").strip()
        link = (node.findtext("link") or "").strip()
        published = parse_date(node.findtext("pubDate"))
        if title:
            items.append(classify_item(source, title, link, published))
    if not items:
        ns = {"atom": "http://www.w3.org/2005/Atom"}
        for node in root.findall(".//atom:entry", ns)[:30]:
            title = (node.findtext("atom:title", default="", namespaces=ns) or "").strip()
            link_node = node.find("atom:link", ns)
            link = link_node.attrib.get("href", "") if link_node is not None else ""
            published = parse_date(node.findtext("atom:updated", default="", namespaces=ns))
            if title:
                items.append(classify_item(source, title, link, published))
    result["items"] = items
    result["duration_seconds"] = round(time.monotonic() - started, 3)
    if not items:
        result["status"] = "empty"
    return result


def classify_item(source: dict[str, Any], title: str, link: str, published_at_utc: str | None) -> dict[str, Any]:
    text = title.lower()
    buckets = []
    matched = []
    for bucket, keywords in KEYWORD_BUCKETS.items():
        hits = [keyword for keyword in keywords if keyword in text]
        if hits:
            buckets.append(bucket)
            matched.extend(hits)
    return {
        "source_id": source["source_id"],
        "source_label": source["label"],
        "title": title,
        "link": link,
        "published_at_utc": published_at_utc,
        "keyword_buckets": sorted(set(buckets)),
        "matched_keywords": sorted(set(matched)),
        "macro_relevance": "watch" if buckets else "background",
        "action_allowed": False,
    }


def validate(payload: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    if payload.get("schema") != SCHEMA:
        errors.append("schema mismatch")
    boundary = payload.get("authority_boundary") if isinstance(payload.get("authority_boundary"), dict) else {}
    for key, expected in AUTHORITY_BOUNDARY.items():
        if boundary.get(key) is not expected:
            errors.append(f"authority boundary mismatch: {key}")
    ok_sources = [source for source in payload.get("sources", []) if isinstance(source, dict) and source.get("status") == "ok"]
    if not ok_sources:
        warnings.append("no geopolitical official feeds were fetched successfully")
    return {"status": "ok" if not errors else "error", "errors": errors, "warnings": warnings}


def build_payload(timeout: int) -> dict[str, Any]:
    sources = [fetch_source(source, timeout) for source in SOURCES]
    items = []
    for source in sources:
        items.extend(source.get("items") or [])
    watch_items = [item for item in items if item.get("macro_relevance") == "watch"]
    payload: dict[str, Any] = {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "ok",
        "source_posture": "official_feed_titles_review_only",
        "authority_boundary": AUTHORITY_BOUNDARY,
        "sources": sources,
        "items": items[:80],
        "watch_items": watch_items[:30],
        "summary": {
            "source_count": len(sources),
            "ok_source_count": sum(1 for source in sources if source.get("status") == "ok"),
            "item_count": len(items),
            "watch_item_count": len(watch_items),
            "buckets": {
                bucket: sum(1 for item in watch_items if bucket in (item.get("keyword_buckets") or []))
                for bucket in KEYWORD_BUCKETS
            },
            "next_safe_action": "Review watch items manually before any macro/portfolio claim; titles are routing signals, not verified market conclusions.",
        },
    }
    payload["validation"] = validate(payload)
    if payload["validation"]["status"] != "ok":
        payload["status"] = "error"
    elif payload["validation"]["warnings"]:
        payload["status"] = "warning"
    return payload


def render_markdown(payload: dict[str, Any]) -> str:
    summary = payload.get("summary") or {}
    lines = [
        "# Macro Geopolitical Sweep",
        "",
        f"- Generated: `{payload.get('generated_at_utc')}`",
        f"- Status: `{payload.get('status')}`",
        f"- Sources ok: `{summary.get('ok_source_count')}/{summary.get('source_count')}`",
        f"- Watch items: `{summary.get('watch_item_count')}`",
        "",
        "## Watch Items",
        "",
    ]
    for item in payload.get("watch_items", [])[:12]:
        lines.append(f"- `{item.get('source_id')}` {item.get('published_at_utc') or 'date n/a'}: {item.get('title')}")
    if not payload.get("watch_items"):
        lines.append("- None.")
    warnings = (payload.get("validation") or {}).get("warnings") or []
    if warnings:
        lines.extend(["", "## Warnings", ""])
        lines.extend(f"- {warning}" for warning in warnings)
    lines.extend(["", "Review-only routing artifact. No action authority.", ""])
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build review-only official-source geopolitical sweep.")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--json-out", default=str(DEFAULT_JSON))
    parser.add_argument("--md-out", default=str(DEFAULT_MD))
    parser.add_argument("--timeout", type=int, default=15)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    payload = build_payload(max(1, args.timeout))
    if args.write:
        atomic_write_json(Path(args.json_out), payload)
        atomic_write_text(Path(args.md_out), render_markdown(payload))
    if args.validate and payload["validation"]["status"] != "ok":
        print("\n".join(payload["validation"]["errors"]))
        return 1
    print(payload["status"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
