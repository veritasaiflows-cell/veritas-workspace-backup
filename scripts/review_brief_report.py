from __future__ import annotations

import argparse
import html
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, atomic_write_text, load_json_artifact

WORKSPACE = Path(__file__).resolve().parents[1]
TMP = WORKSPACE / "tmp"
REPORTS = TMP / "reports"
SCHEMA_VERSION = 1

PACKETS = {
    "morning": TMP / "premarket-brief-input.json",
    "post-close": TMP / "postclose-brief-input.json",
}
SLUGS = {
    "morning": "premarket-review-brief",
    "post-close": "postclose-review-brief",
}
TITLES = {
    "morning": "Pre-Market Review Brief",
    "post-close": "Post-Close Review Brief",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render a review-only daily brief scaffold from summary_brief_packet.py output.")
    parser.add_argument("--window", required=True, choices=sorted(PACKETS.keys()))
    return parser.parse_args()


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def read_packet(window: str) -> dict[str, Any]:
    data = load_json_artifact(PACKETS[window])
    if not isinstance(data, dict):
        raise SystemExit(f"brief packet missing or invalid at {PACKETS[window].relative_to(WORKSPACE)}")
    return data


def rel(path: Path) -> str:
    return str(path.relative_to(WORKSPACE)).replace("\\", "/")


def bullets(items: list[Any]) -> str:
    if not items:
        return "- None reported."
    return "\n".join(f"- {item}" for item in items)


def compact_list(items: list[Any]) -> str:
    return ", ".join(str(item) for item in items) if items else "None"


def authority_block() -> dict[str, Any]:
    return {
        "consumer_posture": "review_only",
        "ai_review_completed": False,
        "ai_review_status": "scaffold_ready_pending_veritas_or_owner_review",
        "canonical_note_mutation_allowed": False,
        "portfolio_mutation_allowed": False,
        "deployment_state_mutation_allowed": False,
        "trade_execution_allowed": False,
        "owner_approval_granted": False,
    }


def render_markdown(window: str, packet: dict[str, Any], generated_at: str) -> str:
    state = packet.get("state_summary") or {}
    trust = packet.get("trust") or {}
    validation = trust.get("validation") or {}
    delivery = packet.get("delivery_readiness") or {}
    title = TITLES[window]
    note_date = packet.get("note_date") or "unknown"
    market_as_of = packet.get("market_data_as_of") or "unknown"
    authority = authority_block()

    lines: list[str] = []
    lines.append(f"# {title} — {note_date}")
    lines.append("")
    lines.append(f"Generated: {generated_at}  ")
    lines.append(f"Market data as of: {market_as_of}  ")
    lines.append("Posture: **review-only scaffold; AI/human narrative review still required.**")
    lines.append("")
    lines.append("## Authority")
    lines.append("- Consumer posture: review-only")
    lines.append("- AI review completed: false — this artifact is ready for Veritas/manual review, not a completed autonomous AI sign-off")
    lines.append("- Canonical note mutation allowed: false")
    lines.append("- Portfolio/deployment mutation allowed: false")
    lines.append("- Trade execution allowed: false")
    lines.append("- Owner approval granted: false")
    lines.append("")
    lines.append("## Trust state")
    lines.append(f"- Trust level: {trust.get('trust_level', 'unknown')}")
    lines.append(f"- Trust gate blocked: {bool(trust.get('trust_gate_blocked'))}")
    lines.append(f"- Dashboard validation: {validation.get('overall', 'unknown')} ({validation.get('critical', 0)} critical / {validation.get('warning', 0)} warning)")
    lines.append(f"- Trust reason: {trust.get('trust_reason', 'not provided')}")
    lines.append("")
    lines.append("## Market setup snapshot")
    lines.append(f"- Deployable-now candidates in source packet: {compact_list(state.get('deployable_now') or [])}")
    lines.append(f"- Almost deployable / watch: {compact_list(state.get('almost_deployable') or [])}")
    lines.append(f"- Blocked: {compact_list(state.get('blocked') or [])}")
    if window == "post-close":
        lines.append(f"- Bench: {compact_list(state.get('bench') or [])}")
        lines.append(f"- Below stop: {compact_list(state.get('below_stop') or [])}")
    lines.append("")
    lines.append("## Focus questions for review")
    lines.append(bullets(packet.get("focus_questions") or []))
    lines.append("")
    lines.append("## Unresolved truths / blockers")
    lines.append(bullets(packet.get("unresolved_truths") or []))
    lines.append("")
    lines.append("## Narrative draft slots")
    lines.append("1. **What matters now:** _[Veritas/manual review fills concise synthesis]._ ")
    lines.append("2. **What not to overstate:** _[Name stale data, warnings, or owner-note dependencies]._ ")
    lines.append("3. **Owner next action:** _[Review action only; no inferred approval]._ ")
    lines.append("")
    lines.append("## Allowed / forbidden claims")
    lines.append("**Allowed:**")
    lines.append(bullets(packet.get("allowed_claims") or []))
    lines.append("")
    lines.append("**Forbidden:**")
    lines.append(bullets(packet.get("forbidden_claims") or []))
    lines.append("")
    lines.append("## Source artifacts")
    for group_name, records in (packet.get("source_artifacts") or {}).items():
        if not isinstance(records, dict):
            continue
        lines.append(f"### {group_name.title()}")
        for name, record in records.items():
            if not isinstance(record, dict):
                continue
            lines.append(f"- {name}: {record.get('status')} — `{record.get('path')}`")
    lines.append("")
    lines.append("---")
    lines.append(f"Machine contract: `{rel(REPORTS / (SLUGS[window] + '-latest.json'))}`. Delivery mode: {delivery.get('mode', 'internal_review_only')}.")
    _ = authority
    return "\n".join(lines) + "\n"


def render_html(markdown: str, title: str) -> str:
    escaped = html.escape(markdown)
    return f"""<!doctype html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\">
  <title>{html.escape(title)}</title>
  <style>
    body {{ margin: 40px auto; max-width: 980px; font-family: Segoe UI, Arial, sans-serif; line-height: 1.45; color: #111827; }}
    pre {{ white-space: pre-wrap; font-family: inherit; }}
    @media print {{ body {{ margin: 18mm; }} }}
  </style>
</head>
<body><pre>{escaped}</pre></body>
</html>
"""


def main() -> int:
    args = parse_args()
    packet = read_packet(args.window)
    REPORTS.mkdir(parents=True, exist_ok=True)
    generated_at = utc_now()
    slug = SLUGS[args.window]
    note_date = str(packet.get("note_date") or datetime.now().date().isoformat())
    dated_base = f"{slug}-{note_date}"

    md = render_markdown(args.window, packet, generated_at)
    latest_md = REPORTS / f"{slug}-latest.md"
    latest_html = REPORTS / f"{slug}-latest.html"
    dated_md = REPORTS / f"{dated_base}.md"
    dated_html = REPORTS / f"{dated_base}.html"
    latest_json = REPORTS / f"{slug}-latest.json"

    atomic_write_text(latest_md, md, encoding="utf-8")
    atomic_write_text(dated_md, md, encoding="utf-8")
    html_text = render_html(md, TITLES[args.window])
    atomic_write_text(latest_html, html_text, encoding="utf-8")
    atomic_write_text(dated_html, html_text, encoding="utf-8")

    manifest = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": generated_at,
        "window": args.window,
        "status": "review_scaffold_ready",
        "authority": authority_block(),
        "source_packet": rel(PACKETS[args.window]),
        "outputs": {
            "latest_markdown": rel(latest_md),
            "latest_html": rel(latest_html),
            "dated_markdown": rel(dated_md),
            "dated_html": rel(dated_html),
        },
        "pdf_generation": {
            "implemented": False,
            "reason": "No safe installed HTML-to-PDF path was assumed in this pass; use the printable HTML as the PDF source.",
            "follow_up_contract": "If PDF tooling is approved/proven, render this exact HTML to tmp/reports/ without changing authority flags.",
        },
    }
    atomic_write_json(latest_json, manifest)
    print(json.dumps({"status": "ok", "window": args.window, "outputs": manifest["outputs"], "authority": manifest["authority"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
