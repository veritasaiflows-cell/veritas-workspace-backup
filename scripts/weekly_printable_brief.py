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
WEEKLY_JSON = TMP / "weekly-intelligence-brief.json"
WEEKLY_MD = WORKSPACE / "05. Intelligence" / "Weekly Intelligence Brief.md"
WEEKLY_MACHINE_MD = WORKSPACE / "05. Intelligence" / "Weekly Intelligence Brief - machine.md"
SCHEMA_VERSION = 1


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a print-ready weekly intelligence brief scaffold under tmp/reports/.")
    parser.add_argument("--source-md", type=Path, default=None, help="Optional markdown source override.")
    return parser.parse_args()


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    return str(path.relative_to(WORKSPACE)).replace("\\", "/")


def read_json(path: Path) -> dict[str, Any]:
    data = load_json_artifact(path)
    return data if isinstance(data, dict) else {}


def choose_source_md(args: argparse.Namespace, summary: dict[str, Any]) -> Path | None:
    if args.source_md:
        return args.source_md if args.source_md.is_absolute() else WORKSPACE / args.source_md
    wrote_to = str(summary.get("wrote_to") or "").strip()
    if wrote_to:
        candidate = WORKSPACE / wrote_to
        if candidate.exists():
            return candidate
    if WEEKLY_MD.exists():
        return WEEKLY_MD
    if WEEKLY_MACHINE_MD.exists():
        return WEEKLY_MACHINE_MD
    return None


def extract_section(markdown: str, heading: str) -> str:
    if heading and heading in markdown:
        start = markdown.find(heading)
        next_start = markdown.find("\n## Week of ", start + len(heading))
        return markdown[start:].strip() if next_start == -1 else markdown[start:next_start].strip()
    return markdown.strip()


def render_markdown(summary: dict[str, Any], source_text: str, source_path: Path | None, generated_at: str) -> str:
    heading = str(summary.get("week_heading") or "Weekly Intelligence Brief")
    section = extract_section(source_text, heading)
    lines: list[str] = []
    lines.append(f"# Printable {heading.lstrip('# ').strip()}")
    lines.append("")
    lines.append(f"Generated: {generated_at}")
    lines.append(f"Market data as of: {summary.get('market_data_as_of') or 'unknown'}")
    lines.append(f"Source: `{rel(source_path) if source_path else 'missing'}`")
    lines.append("")
    lines.append("## Authority")
    lines.append("- Review-support only.")
    lines.append("- Canonical note mutation allowed: false for this printable artifact.")
    lines.append("- Portfolio/deployment mutation allowed: false.")
    lines.append("- Trade execution allowed: false.")
    lines.append("- Owner approval granted: false.")
    lines.append("")
    lines.append("## PDF status")
    lines.append("- PDF binary generation is not assumed in v1; this Markdown plus the paired HTML is the print/PDF source.")
    lines.append("- If an approved PDF renderer is later proven, render the paired HTML without changing the review-only authority block.")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append(section or "_Weekly source markdown missing or empty._")
    lines.append("")
    return "\n".join(lines)


def render_html(markdown: str, title: str) -> str:
    escaped = html.escape(markdown)
    return f"""<!doctype html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\">
  <title>{html.escape(title)}</title>
  <style>
    body {{ margin: 40px auto; max-width: 1080px; font-family: Segoe UI, Arial, sans-serif; line-height: 1.46; color: #111827; }}
    pre {{ white-space: pre-wrap; font-family: inherit; }}
    @page {{ margin: 18mm; }}
    @media print {{ body {{ margin: 0; }} }}
  </style>
</head>
<body><pre>{escaped}</pre></body>
</html>
"""


def main() -> int:
    args = parse_args()
    REPORTS.mkdir(parents=True, exist_ok=True)
    generated_at = utc_now()
    summary = read_json(WEEKLY_JSON)
    source_path = choose_source_md(args, summary)
    source_text = source_path.read_text(encoding="utf-8", errors="replace") if source_path and source_path.exists() else ""
    week_start = str(summary.get("week_start") or datetime.now().date().isoformat())
    slug = "weekly-intelligence-brief-printable"
    dated_base = f"{slug}-{week_start}"

    md = render_markdown(summary, source_text, source_path, generated_at)
    latest_md = REPORTS / f"{slug}-latest.md"
    latest_html = REPORTS / f"{slug}-latest.html"
    dated_md = REPORTS / f"{dated_base}.md"
    dated_html = REPORTS / f"{dated_base}.html"
    latest_json = REPORTS / f"{slug}-latest.json"

    atomic_write_text(latest_md, md, encoding="utf-8")
    atomic_write_text(dated_md, md, encoding="utf-8")
    html_text = render_html(md, "Printable Weekly Intelligence Brief")
    atomic_write_text(latest_html, html_text, encoding="utf-8")
    atomic_write_text(dated_html, html_text, encoding="utf-8")

    manifest = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": generated_at,
        "status": "print_ready_html_markdown",
        "source_summary": rel(WEEKLY_JSON),
        "source_markdown": rel(source_path) if source_path else "",
        "authority": {
            "consumer_posture": "review_only",
            "canonical_note_mutation_allowed": False,
            "portfolio_mutation_allowed": False,
            "deployment_state_mutation_allowed": False,
            "trade_execution_allowed": False,
            "owner_approval_granted": False,
        },
        "outputs": {
            "latest_markdown": rel(latest_md),
            "latest_html": rel(latest_html),
            "dated_markdown": rel(dated_md),
            "dated_html": rel(dated_html),
        },
        "pdf_generation": {
            "implemented": False,
            "reason": "No safe installed PDF renderer was assumed; HTML is print-ready and can be printed to PDF manually.",
            "follow_up_contract": "Approve/prove a renderer, then render latest_html to tmp/reports/ with identical authority flags.",
        },
    }
    atomic_write_json(latest_json, manifest)
    print(json.dumps({"status": "ok", "outputs": manifest["outputs"], "pdf_generation": manifest["pdf_generation"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
