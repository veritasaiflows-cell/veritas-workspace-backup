#!/usr/bin/env python3
"""Render the fixture-only retail investor SaaS customer export as local HTML."""
from __future__ import annotations

import argparse
import html
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_text, load_json_artifact
from retail_saas_customer_output_validator import validate_payload, validate_rendered_text

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
DEFAULT_INPUT = TMP / "retail-saas-fixture-demo.customer-export.json"
DEFAULT_HTML = TMP / "retail-saas-fixture-demo.html"
DEFAULT_VALIDATION = TMP / "retail-saas-fixture-demo.html-validation.json"


def e(value: Any) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def render_list(items: list[Any]) -> str:
    return "\n".join(f"<li>{e(item)}</li>" for item in items)


def render_html(export: dict[str, Any]) -> str:
    rows = []
    for item in export.get("watchlist_items", []):
        price = item.get("price_context") if isinstance(item.get("price_context"), dict) else {}
        rows.append(
            f"""
            <article class="ticker">
              <div class="ticker-head">
                <div>
                  <h2>{e(item.get('ticker'))}</h2>
                  <p>{e(item.get('company_name'))}</p>
                </div>
                <span>{e(item.get('evidence_freshness'))}</span>
              </div>
              <p class="posture">{e(item.get('research_posture'))}</p>
              <p>{e(item.get('plain_language_summary'))}</p>
              <div class="metrics">
                <div><strong>{e(price.get('latest_known_price'))}</strong><small>latest known price</small></div>
                <div><strong>{e(price.get('watch_zone_low'))} - {e(price.get('watch_zone_high'))}</strong><small>research watch zone</small></div>
                <div><strong>{e(price.get('risk_review_level'))}</strong><small>risk review level</small></div>
              </div>
              <p class="warning">{e(price.get('staleness_note'))}</p>
              <section>
                <h3>What To Watch</h3>
                <ul>{render_list(item.get('what_to_watch', []))}</ul>
              </section>
              <section>
                <h3>Risk Flags</h3>
                <ul>{render_list(item.get('risk_flags', []))}</ul>
              </section>
              <section>
                <h3>Stale Or Missing Evidence</h3>
                <ul>{render_list(item.get('stale_or_missing_evidence', []))}</ul>
              </section>
            </article>
            """
        )

    disclaimers = render_list(export.get("disclaimers", []))
    notes = render_list(export.get("portfolio_level_notes", []))
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{e(export.get('brief_title'))}</title>
  <style>
    :root {{
      color-scheme: light;
      --ink: #17202a;
      --muted: #5d6673;
      --line: #d7dde4;
      --panel: #f7f9fb;
      --accent: #0f766e;
      --warn: #8a4b08;
      --warn-bg: #fff7e6;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font: 15px/1.45 "Segoe UI", Arial, sans-serif;
      color: var(--ink);
      background: white;
    }}
    header {{
      padding: 32px max(24px, 7vw) 24px;
      border-bottom: 1px solid var(--line);
      background: var(--panel);
    }}
    main {{
      padding: 24px max(24px, 7vw) 40px;
      display: grid;
      gap: 18px;
    }}
    h1, h2, h3, p {{ margin-top: 0; }}
    h1 {{ font-size: clamp(28px, 4vw, 44px); margin-bottom: 8px; }}
    h2 {{ font-size: 24px; margin-bottom: 0; }}
    h3 {{ font-size: 15px; margin-bottom: 8px; }}
    .meta, .posture, small {{ color: var(--muted); }}
    .ticker {{
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 18px;
      display: grid;
      gap: 12px;
    }}
    .ticker-head {{
      display: flex;
      justify-content: space-between;
      gap: 12px;
      align-items: start;
    }}
    .ticker-head span {{
      border: 1px solid var(--line);
      color: var(--accent);
      padding: 4px 8px;
      border-radius: 999px;
      font-size: 12px;
      text-transform: uppercase;
      white-space: nowrap;
    }}
    .metrics {{
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 10px;
    }}
    .metrics div {{
      border: 1px solid var(--line);
      border-radius: 6px;
      padding: 10px;
      min-width: 0;
    }}
    .metrics strong, .metrics small {{ display: block; overflow-wrap: anywhere; }}
    .warning {{
      background: var(--warn-bg);
      color: var(--warn);
      border: 1px solid #f0d69a;
      border-radius: 6px;
      padding: 10px;
    }}
    ul {{ margin: 0; padding-left: 20px; }}
    footer {{
      padding: 24px max(24px, 7vw) 40px;
      border-top: 1px solid var(--line);
      color: var(--muted);
    }}
    @media (max-width: 720px) {{
      .metrics {{ grid-template-columns: 1fr; }}
      .ticker-head {{ flex-direction: column; }}
    }}
  </style>
</head>
<body>
  <header>
    <p class="meta">{e(export.get('product_name'))}</p>
    <h1>{e(export.get('brief_title'))}</h1>
    <p>{e(export.get('fixture_notice'))}</p>
    <p class="meta">Generated: {e(export.get('generated_at'))}</p>
  </header>
  <main>
    <section>
      <h2>Portfolio-Level Notes</h2>
      <ul>{notes}</ul>
    </section>
    {''.join(rows)}
  </main>
  <footer>
    <h2>Important Limitations</h2>
    <ul>{disclaimers}</ul>
  </footer>
</body>
</html>
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render fixture-only retail SaaS customer export as local HTML.")
    parser.add_argument("--input", default=str(DEFAULT_INPUT), help="Customer-only export JSON")
    parser.add_argument("--html-out", default=str(DEFAULT_HTML), help="HTML output")
    parser.add_argument("--validation-out", default=str(DEFAULT_VALIDATION), help="Validation output JSON")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    export = load_json_artifact(Path(args.input))
    validation = validate_payload(export)
    rendered = render_html(export)
    html_findings = validate_rendered_text(rendered, Path(args.html_out).name)
    validation["findings"].extend(html_findings)
    validation["critical_count"] = sum(1 for f in validation["findings"] if f["severity"] == "critical")
    validation["warning_count"] = sum(1 for f in validation["findings"] if f["severity"] == "warning")
    validation["status"] = "ok" if validation["critical_count"] == 0 else "error"
    validation["rendered_html_validated"] = str(args.html_out)
    atomic_write_text(args.html_out, rendered)
    from market_data_utils import atomic_write_json

    atomic_write_json(args.validation_out, validation)
    print(f"status={validation['status']} critical={validation['critical_count']} warning={validation['warning_count']} html={args.html_out}")
    return 0 if validation["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
