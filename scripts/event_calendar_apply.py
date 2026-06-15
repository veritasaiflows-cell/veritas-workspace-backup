"""event_calendar_apply.py

Bounded Event Calendar maintenance helper.

Consumes tmp/event-calendar-rollforward.json and tmp/earnings-date-source-confidence.json,
then updates only an auto-managed provider-estimated earnings block plus narrow
source-confidence wording for already-dated timing-sensitive events.

Randall explicitly approved this daily-chain Event Calendar maintenance on
2026-05-10. This helper does not mutate portfolio/deployment/watchlist authority.

Usage:
    python scripts/event_calendar_apply.py --dry-run
    python scripts/event_calendar_apply.py --apply

Outputs:
    tmp/event-calendar-apply.json
    optional Markdown digest when --write-md is supplied
"""

from __future__ import annotations

import argparse
import json
import re
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

WORKSPACE = Path(__file__).resolve().parents[1]
TMP = WORKSPACE / "tmp"
ROLLFORWARD_PATH = TMP / "event-calendar-rollforward.json"
SOURCE_CONFIDENCE_PATH = TMP / "earnings-date-source-confidence.json"
EVENT_CALENDAR_PATH = WORKSPACE / "05. Intelligence" / "Event Calendar.md"
OUT_JSON = TMP / "event-calendar-apply.json"
OUT_MD = OUT_JSON.with_suffix(".md")

APPROVAL = "Randall approved bounded daily-chain Event Calendar maintenance on 2026-05-10."
START_MARKER = "<!-- VERITAS_AUTO_EVENT_CALENDAR_ROLLFORWARD_START -->"
END_MARKER = "<!-- VERITAS_AUTO_EVENT_CALENDAR_ROLLFORWARD_END -->"
ANCHOR = "## Standing watch list (no date yet — add when confirmed)"

MONTH_ABBR = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
DAY_ABBR = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def parse_iso_date(value: Any) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except Exception:
        return None


def clean_event_title(event: str) -> str:
    text = re.sub(r"\*", "", event or "").strip()
    text = re.sub(r"\s+—\s+Reported.*$", "", text)
    text = re.sub(r"\s+—\s+After close\??$", "", text)
    text = re.sub(r"\s+Earnings$", " Earnings", text)
    return text or "Earnings"


def confidence_records_by_ticker(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(row.get("ticker")).upper(): row
        for row in payload.get("records", [])
        if isinstance(row, dict) and row.get("ticker")
    }


def row_priority(proposal: dict[str, Any]) -> str:
    role = str(proposal.get("portfolio_role") or "")
    lane = str(proposal.get("coverage_lane") or "")
    if role in {"core", "tactical"} or lane == "execution":
        return "**[HIGH]**"
    return "**[MONITOR]**"


def build_auto_block(rollforward: dict[str, Any], source_confidence: dict[str, Any]) -> tuple[str, list[dict[str, Any]]]:
    confidence_by_ticker = confidence_records_by_ticker(source_confidence)
    rows: list[dict[str, Any]] = []

    for proposal in rollforward.get("proposals", []):
        if not isinstance(proposal, dict):
            continue
        ticker = str(proposal.get("ticker") or "").upper()
        provider_date = parse_iso_date(proposal.get("provider_next_earnings_date"))
        if not ticker or provider_date is None:
            continue
        confidence = str(proposal.get("confidence") or "provider_estimate_unconfirmed")
        if confidence != "primary_confirmed":
            confidence = "provider_estimate_unconfirmed"
        source = str(proposal.get("source") or "provider")
        fetched = str(proposal.get("fetched_at_utc") or "unknown fetch time")
        event_title = clean_event_title(str(proposal.get("event_calendar_event") or f"{ticker} Earnings"))
        conf_row = confidence_by_ticker.get(ticker, {})
        verification_sites = conf_row.get("verification_sites") if isinstance(conf_row.get("verification_sites"), list) else []
        verify_hint = ""
        if verification_sites:
            labels = [str(site.get("label") or site.get("url") or "").strip() for site in verification_sites if isinstance(site, dict)]
            labels = [label for label in labels if label]
            if labels:
                verify_hint = " Check: " + "; ".join(labels[:3]) + "."
        if confidence == "primary_confirmed":
            confidence_text = "primary-confirmed"
        else:
            confidence_text = f"provider estimate from {source}; not primary-confirmed"
        notes = (
            f"Auto-maintained from `{ROLLFORWARD_PATH.relative_to(WORKSPACE).as_posix()}`. "
            f"Confidence: {confidence_text}. Provider fetched: {fetched}. "
            "Review support only; no deployment, promotion, sizing, or trade authority."
            f"{verify_hint}"
        )
        rows.append({
            "ticker": ticker,
            "date": provider_date,
            "event": f"**{ticker} next expected earnings — {confidence_text}**",
            "priority": row_priority(proposal),
            "notes": notes,
            "source_event": event_title,
            "confidence": confidence,
        })

    rows.sort(key=lambda row: (row["date"], row["ticker"]))
    generated = utc_now_iso()
    lines = [
        START_MARKER,
        "## Auto-maintained provider-estimated earnings roll-forward",
        "",
        f"Generated: {generated}",
        f"Approval: {APPROVAL}",
        "",
        "Boundary: this block keeps the Event Calendar fresh. It does not authorize portfolio mutation, deployment, sizing, promotion, trade execution, or owner-approval inference.",
        "",
        "| Date | Day | Event | Priority | Notes |",
        "|---|---|---|---|---|",
    ]
    if rows:
        for row in rows:
            d = row["date"]
            lines.append(
                f"| {MONTH_ABBR[d.month - 1]} {d.day} | {DAY_ABBR[d.weekday()]} | {row['event']} | {row['priority']} | {row['notes']} |"
            )
    else:
        lines.append("| — | — | No provider-estimated roll-forwards currently staged | — | — |")
    lines.extend(["", END_MARKER])
    return "\n".join(lines), rows


def replace_auto_block(text: str, block: str) -> tuple[str, str]:
    pattern = re.compile(re.escape(START_MARKER) + r".*?" + re.escape(END_MARKER), re.DOTALL)
    if pattern.search(text):
        return pattern.sub(block, text), "updated_existing_block"
    if ANCHOR not in text:
        raise RuntimeError(f"anchor not found: {ANCHOR}")
    return text.replace(ANCHOR, block + "\n\n" + ANCHOR, 1), "inserted_new_block"


def update_freshness_header(text: str) -> str:
    today = date.today().isoformat()
    text = re.sub(r"- Last updated: .*", f"- Last updated: {today}", text, count=1)
    text = re.sub(
        r"- Data as of: .*",
        "- Data as of: daily chain-maintained earnings/calendar evidence plus bounded Event Calendar roll-forward automation",
        text,
        count=1,
    )
    text = re.sub(
        r"- Next refresh due: .*",
        "- Next refresh due: next scheduled finance refresh chain or immediately after a material catalyst/date discrepancy.",
        text,
        count=1,
    )
    return text


def update_timing_governance(text: str, source_confidence: dict[str, Any]) -> str:
    confidence_by_ticker = confidence_records_by_ticker(source_confidence)
    nvda = confidence_by_ticker.get("NVDA")
    if not nvda or nvda.get("source_confidence") != "primary_confirmed":
        return text
    evidence = nvda.get("configured_primary_evidence") if isinstance(nvda.get("configured_primary_evidence"), dict) else {}
    matched = str(evidence.get("matched_text") or "official NVIDIA IR evidence").strip()
    url = str(evidence.get("url") or "").strip()
    replacement = (
        f"- Current timing dependency update: **NVDA May 20, 2026 is primary-confirmed** from NVIDIA Investor Relations evidence ({matched}; {url}). "
        "Keep yfinance/provider evidence secondary and continue using official company/SEC sources for timing disputes."
    )
    text = re.sub(
        r"- Current unresolved manual timing dependencies are now narrower\..*",
        replacement,
        text,
        count=1,
    )
    text = re.sub(
        r"- Close rule for \*\*NVDA\*\*:.*",
        "- Close rule for **NVDA**: resolved on 2026-05-10 by Randall-provided official NVIDIA IR evidence; future date changes still require company IR/newsroom/SEC confirmation or explicit provider-estimate wording.",
        text,
        count=1,
    )
    return text


def update_nvda_row(text: str, source_confidence: dict[str, Any]) -> str:
    nvda = confidence_records_by_ticker(source_confidence).get("NVDA")
    if not nvda or nvda.get("source_confidence") != "primary_confirmed":
        return text
    evidence = nvda.get("configured_primary_evidence") if isinstance(nvda.get("configured_primary_evidence"), dict) else {}
    matched = str(evidence.get("matched_text") or "official NVIDIA IR evidence").strip()
    url = str(evidence.get("url") or "").strip()
    # Once primary-confirmed, remove the old operational deadline row so the
    # calendar does not preserve a stale blocker after the source question closes.
    text = re.sub(r"^\| May 13 \| Wed \| \*\*NVDA timing-confirmation deadline\*\*.*\n", "", text, count=1, flags=re.MULTILINE)
    new_line = (
        "| May 20 | Wed | **NVDA Q1 FY2027 Earnings — Primary-confirmed by NVIDIA IR** | **[CRITICAL]** | "
        f"Official NVIDIA Investor Relations evidence confirms {matched}. Source: {url}. "
        "Watch: Blackwell demand, data center revenue, forward guidance. Single most important earnings call for the AI infrastructure thesis. |"
    )
    return re.sub(r"^\| May 20 \| Wed \| \*\*NVDA Q1 FY2027 Earnings.*$", new_line, text, count=1, flags=re.MULTILINE)


def append_last_updated_entry(text: str, applied_count: int, nvda_primary: bool) -> str:
    today = date.today().isoformat()
    # Keep repeated daily-chain runs idempotent for a given day instead of
    # appending a new identical maintenance entry on every execution.
    text = re.sub(
        rf"^- {re.escape(today)} — daily-chain Event Calendar maintenance approved by Randall and applied through `scripts/event_calendar_apply\.py`:.*\n?",
        "",
        text,
        flags=re.MULTILINE,
    )
    entry = (
        f"- {today} — daily-chain Event Calendar maintenance approved by Randall and applied through `scripts/event_calendar_apply.py`: "
        f"auto-managed provider-estimated roll-forward block refreshed with {applied_count} staged next-earnings dates. "
        "Provider-estimated entries remain explicitly non-primary-confirmed unless primary evidence is attached; no portfolio/deployment/trade authority widened."
    )
    if nvda_primary:
        entry += " NVDA May 20 was updated to primary-confirmed from Randall-provided NVIDIA IR evidence."
    return text.rstrip() + "\n" + entry + "\n"


def build_updated_text(text: str, rollforward: dict[str, Any], source_confidence: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    if rollforward.get("status") not in {"ok", "partial"}:
        raise RuntimeError("roll-forward packet is not usable")
    if rollforward.get("warnings"):
        raise RuntimeError("roll-forward packet has warnings; refusing canonical calendar update")
    block, rows = build_auto_block(rollforward, source_confidence)
    updated, block_action = replace_auto_block(text, block)
    updated = update_freshness_header(updated)
    updated = update_timing_governance(updated, source_confidence)
    updated = update_nvda_row(updated, source_confidence)
    nvda_primary = confidence_records_by_ticker(source_confidence).get("NVDA", {}).get("source_confidence") == "primary_confirmed"
    updated = append_last_updated_entry(updated, len(rows), bool(nvda_primary))
    return updated, {
        "block_action": block_action,
        "applied_rollforward_count": len(rows),
        "nvda_primary_confirmed": bool(nvda_primary),
        "tickers": [row["ticker"] for row in rows],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="Write the bounded update to Event Calendar.md")
    parser.add_argument("--dry-run", action="store_true", help="Generate proof artifacts without editing Event Calendar.md")
    parser.add_argument("--write-md", action="store_true", help="Also write optional Markdown digest.")
    args = parser.parse_args()
    if args.apply and args.dry_run:
        parser.error("choose only one of --apply or --dry-run")
    apply = args.apply

    rollforward = load_json(ROLLFORWARD_PATH)
    source_confidence = load_json(SOURCE_CONFIDENCE_PATH) if SOURCE_CONFIDENCE_PATH.exists() else {}
    before = EVENT_CALENDAR_PATH.read_text(encoding="utf-8")
    after, summary = build_updated_text(before, rollforward, source_confidence)

    changed = before != after
    if apply and changed:
        EVENT_CALENDAR_PATH.write_text(after, encoding="utf-8")

    payload = {
        "generated_at_utc": utc_now_iso(),
        "status": "ok",
        "mode": "apply" if apply else "dry_run",
        "changed": changed,
        "approval": APPROVAL,
        "authority": {
            "event_calendar_mutation": bool(apply),
            "portfolio_mutation": False,
            "deployment_mutation": False,
            "watchlist_promotion": False,
            "trade_or_account_action": False,
            "owner_approval_inference": False,
        },
        "inputs": {
            "rollforward": ROLLFORWARD_PATH.relative_to(WORKSPACE).as_posix(),
            "source_confidence": SOURCE_CONFIDENCE_PATH.relative_to(WORKSPACE).as_posix(),
            "event_calendar": EVENT_CALENDAR_PATH.relative_to(WORKSPACE).as_posix(),
        },
        **summary,
    }
    OUT_JSON.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    lines = [
        "# Event Calendar Apply Proof",
        "",
        f"Generated: {payload['generated_at_utc']}",
        f"Mode: {payload['mode']}",
        f"Changed: {payload['changed']}",
        f"Applied roll-forward count: {payload['applied_rollforward_count']}",
        f"NVDA primary confirmed: {payload['nvda_primary_confirmed']}",
        "",
        "Authority: Event Calendar maintenance only; no portfolio/deployment/watchlist/trade authority.",
        "",
        "Tickers: " + (", ".join(payload["tickers"]) if payload["tickers"] else "none"),
    ]
    if args.write_md:
        OUT_MD.write_text("\n".join(lines), encoding="utf-8")

    print("event calendar apply mode:", payload["mode"])
    print("changed:", changed)
    print("roll-forward rows:", payload["applied_rollforward_count"])
    print("wrote", OUT_JSON)
    if args.write_md:
        print("wrote", OUT_MD)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
