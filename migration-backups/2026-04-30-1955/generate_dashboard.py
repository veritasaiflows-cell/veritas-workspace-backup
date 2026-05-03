from __future__ import annotations

import json
from typing import Any

from dashboard_core import TMP, SCRIPTS, load_sources, write_json
from dashboard_payload import build_payload, compute_delta

TEMPLATE_PATH = SCRIPTS / "dashboard-template.html"
OUT_PATH = TMP / "veritas-command-center.html"
DATA_PATH = TMP / "dashboard-data.json"
DELTA_PATH = TMP / "dashboard-delta.json"
LAST_PATH = TMP / "dashboard-last.json"
VALIDATION_PATH = TMP / "dashboard-validation.json"


def inject_into_template(payload: dict[str, Any], delta: dict[str, Any]) -> str:
    if not TEMPLATE_PATH.exists():
        raise FileNotFoundError(f"Dashboard template not found at {TEMPLATE_PATH}")
    styles_path = SCRIPTS / "dashboard-styles.css"
    js_dir = SCRIPTS / "dashboard-js"
    css = f"<style>\n{styles_path.read_text(encoding='utf-8')}\n</style>" if styles_path.exists() else ""
    js_files = sorted(js_dir.glob("*.js")) if js_dir.exists() else []
    js_content = "\n\n".join(f.read_text(encoding="utf-8") for f in js_files)
    js = f"<script>\n{js_content}\n</script>" if js_content else ""
    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    template = template.replace("%%STYLES%%", css)
    template = template.replace("%%SCRIPTS%%", js)
    html = template.replace("%%DASHBOARD_DATA%%", json.dumps(payload, indent=2, default=str))
    html = html.replace("%%DASHBOARD_DELTA%%", json.dumps(delta, indent=2, default=str))
    return html


def generate() -> None:
    sources = load_sources()
    payload = build_payload(sources)

    previous = None
    if LAST_PATH.exists():
        try:
            previous = json.loads(LAST_PATH.read_text(encoding="utf-8"))
        except Exception as exc:
            print(f"  WARN: Could not load prior snapshot: {exc}")

    delta = compute_delta(payload, previous)
    write_json(DATA_PATH, payload)
    write_json(DELTA_PATH, delta)
    write_json(VALIDATION_PATH, payload["validation"])

    html = inject_into_template(payload, delta)
    OUT_PATH.write_text(html, encoding="utf-8")
    write_json(LAST_PATH, payload)

    print(f"  [ok] dashboard-data.json written ({len(payload.get('technical', []))} tech records)")
    print(f"  [ok] dashboard-delta.json written ({len(delta.get('changes', []))} changes: {delta.get('summary', '')})")
    print(f"  [ok] dashboard-validation.json written ({payload['validation']['summary']['critical']} critical, {payload['validation']['summary']['warning']} warning)")
    print(f"  [ok] Dashboard written to {OUT_PATH}")
    print(f"  [ok] Generated at {payload['generated_at']}")
    print(f"  [ok] Data from: {payload['last_trade_date']}")
    print(f"  [ok] Exec freshness: {payload['exec_freshness']}")


if __name__ == "__main__":
    generate()
