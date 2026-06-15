from __future__ import annotations

import argparse
import html
import json
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, atomic_write_text

WORKSPACE = Path(__file__).resolve().parents[1]
DEFAULT_HTML = WORKSPACE / "tmp" / "wf75-pm-readiness-brief.html"
DEFAULT_PDF = WORKSPACE / "tmp" / "wf75-pm-readiness-brief.pdf"
DEFAULT_MANIFEST = WORKSPACE / "tmp" / "wf75-pm-readiness-brief.json"

SOURCE_PATHS = {
    "pm_update": WORKSPACE / "tmp" / "wf75-pm-weekly-update.json",
    "artifact_handoff": WORKSPACE / "tmp" / "wf75-artifact-only-pm-handoff.json",
    "sqlite_control_plane": WORKSPACE / "tmp" / "wf75-service-state-sqlite.json",
    "operator_console": WORKSPACE / "tmp" / "wf75-operator-console.json",
    "operator_packet": WORKSPACE / "tmp" / "operator-packets" / "retail-saas-wf75.json",
}


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def relpath(path: Path) -> str:
    try:
        return str(path.relative_to(WORKSPACE)).replace("\\", "/")
    except ValueError:
        return str(path)


def esc(value: Any) -> str:
    return html.escape("" if value is None else str(value))


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def find_browser() -> str | None:
    candidates = [
        shutil.which("msedge"),
        shutil.which("chrome"),
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    ]
    for candidate in candidates:
        if candidate and Path(candidate).exists():
            return candidate
    return None


def badge_class(value: Any) -> str:
    text = str(value or "").lower()
    if text in {"ok", "ready_for_internal_pm_review", "ready_for_internal_artifact_only_pm_handoff", "control_plane_ready"}:
        return "good"
    if "blocked" in text or "missing" in text or "failed" in text:
        return "bad"
    if "review" in text or "warning" in text or "internal" in text:
        return "warn"
    return "neutral"


def badge(value: Any) -> str:
    label = "unknown" if value in (None, "") else str(value)
    return f"<span class='badge {badge_class(label)}'>{esc(label)}</span>"


def rows(items: list[tuple[Any, Any]]) -> str:
    return "\n".join(f"<tr><td>{esc(k)}</td><td>{v}</td></tr>" for k, v in items)


def list_items(items: list[Any], limit: int = 8) -> str:
    clean = [str(item) for item in items[:limit] if item]
    if not clean:
        return "<li>No items surfaced.</li>"
    return "\n".join(f"<li>{esc(item)}</li>" for item in clean)


def build_html(sources: dict[str, dict[str, Any]], manifest: dict[str, Any]) -> str:
    pm_update = sources["pm_update"]
    artifact_handoff = sources["artifact_handoff"]
    sqlite_control = sources["sqlite_control_plane"]
    operator_console = sources["operator_console"]
    operator_packet = sources["operator_packet"]

    validation = pm_update.get("validation_status") or {}
    proof_present = f"{validation.get('proof_required_present')}/{validation.get('proof_required_total')}"
    queue_rows = sqlite_control.get("queue_items") or []
    latest_queue = queue_rows[0] if queue_rows and isinstance(queue_rows[0], dict) else {}
    handoff_validation = artifact_handoff.get("validation") or {}
    console_validation = operator_console.get("validation") or {}
    trust_gates = operator_packet.get("trust_gates_missing") or []
    completed = pm_update.get("completed_this_week") or []
    upcoming = [
        f"{item.get('timing')} / Phase {item.get('phase')}: {item.get('enhancement')}"
        for item in (pm_update.get("upcoming_enhancements") or [])
        if isinstance(item, dict)
    ]
    blockers = [
        f"{item.get('id')}: {item.get('blocker')} Resolution: {item.get('required_resolution')}"
        for item in (pm_update.get("blockers_and_decisions") or [])
        if isinstance(item, dict)
    ]
    source_lines = [f"{name}: {relpath(path)}" for name, path in SOURCE_PATHS.items()]

    return f"""<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>WF75 PM Readiness Brief</title>
<style>
  @page {{ size: Letter; margin: 0.42in; }}
  * {{ box-sizing: border-box; }}
  body {{ margin: 0; font-family: Arial, Helvetica, sans-serif; color: #162033; background: #fff; font-size: 10px; line-height: 1.34; }}
  .page {{ min-height: 9.7in; page-break-after: always; position: relative; padding-bottom: 0.18in; }}
  .page:last-child {{ page-break-after: auto; }}
  .top {{ border-bottom: 3px solid #12345c; padding-bottom: 9px; margin-bottom: 10px; display:flex; justify-content:space-between; gap: 18px; }}
  h1 {{ margin: 0; color: #0e294a; font-size: 25px; line-height: 1.02; }}
  h2 {{ margin: 0 0 7px; color: #0e294a; font-size: 17px; }}
  h3 {{ margin: 10px 0 5px; color: #284f7a; text-transform: uppercase; letter-spacing: .08em; font-size: 9px; }}
  ul {{ margin: 5px 0 8px 16px; padding: 0; }}
  li {{ margin: 3px 0; }}
  table {{ width:100%; border-collapse: collapse; table-layout: fixed; margin: 6px 0 9px; }}
  td, th {{ border: 1px solid #d7e0ea; padding: 6px; vertical-align: top; }}
  th {{ background:#12345c; color:white; text-align:left; }}
  .kicker {{ color:#5a6f88; font-size:8px; text-transform:uppercase; letter-spacing:.12em; font-weight:bold; }}
  .subtitle {{ color:#50647c; margin-top:4px; }}
  .panel {{ border:1px solid #d7e0ea; border-radius:8px; padding:8px; background:#f7f9fc; margin:6px 0; }}
  .panel.dark {{ background:#102a4a; color:white; border-color:#102a4a; font-size:12px; }}
  .panel.warn {{ background:#fff7dd; border-color:#d5a736; }}
  .grid {{ display:grid; grid-template-columns: repeat(4, 1fr); gap: 7px; margin: 7px 0; }}
  .metric {{ border:1px solid #d7e0ea; border-radius:8px; padding:7px; background:white; min-height:.58in; }}
  .label {{ color:#5a6f88; font-size:7.5px; text-transform:uppercase; letter-spacing:.08em; margin-bottom:3px; }}
  .value {{ font-weight:700; color:#0e294a; font-size:14px; line-height:1.1; }}
  .muted {{ color:#65778c; font-size:8px; }}
  .badge {{ display:inline-block; border-radius:999px; padding:2px 7px; font-size:7.5px; font-weight:bold; background:#e8eef7; color:#244b73; }}
  .badge.good {{ background:#e5f4ea; color:#176238; }}
  .badge.warn {{ background:#fff0c6; color:#765200; }}
  .badge.bad {{ background:#fde8e8; color:#8f1d1d; }}
  .footer {{ position:absolute; left:0; right:0; bottom:0; border-top:1px solid #e3e8f1; padding-top:4px; display:flex; justify-content:space-between; color:#6b7b91; font-size:7.5px; }}
</style>
</head>
<body>
<section class="page">
  <div class="top">
    <div>
      <div class="kicker">Internal PM artifact-only brief</div>
      <h1>WF75 PM Readiness Brief</h1>
      <div class="subtitle">Generated {esc(manifest['generated_at_utc'])} from validated workspace artifacts</div>
    </div>
    <div>{badge(pm_update.get('status'))}</div>
  </div>
  <div class="panel dark"><strong>Verdict:</strong> {esc(pm_update.get('headline'))}</div>
  <div class="grid">
    <div class="metric"><div class="label">PM update</div><div class="value">{badge(pm_update.get('status'))}</div></div>
    <div class="metric"><div class="label">Artifact handoff</div><div class="value">{badge(artifact_handoff.get('status'))}</div></div>
    <div class="metric"><div class="label">SQLite WAL</div><div class="value">{badge(sqlite_control.get('status'))}</div><div class="muted">journal {esc(sqlite_control.get('journal_mode'))}</div></div>
    <div class="metric"><div class="label">Required proof</div><div class="value">{esc(proof_present)}</div></div>
  </div>
  <div class="panel"><strong>Operator console:</strong> {badge(operator_console.get('status'))} validation {badge(console_validation.get('status'))}. Use `tmp/wf75-operator-console.json` as the required source for queue, lifecycle, artifact health, scenario, renderer, and PM handoff review; rendered HTML is optional proof only.</div>
  <h3>Completed this week</h3>
  <ul>{list_items(completed, 10)}</ul>
  <h3>Control-plane queue</h3>
  <table><tr><th>Field</th><th>Current value</th></tr>{rows([
      ('Queue item', esc(latest_queue.get('item_id'))),
      ('Status', badge(latest_queue.get('status'))),
      ('Claim owner', esc(latest_queue.get('claim_owner'))),
      ('Claim validation', badge((sqlite_control.get('validation') or {}).get('status'))),
  ])}</table>
  <div class="footer"><span>WF75 PM Readiness Brief</span><span>Page 1</span></div>
</section>
<section class="page">
  <div class="top"><div><div class="kicker">Next sprint</div><h2>Enhancements, blockers, and proof</h2></div><div>{badge(handoff_validation.get('status'))}</div></div>
  <h3>Upcoming enhancements</h3>
  <ul>{list_items(upcoming, 12)}</ul>
  <h3>Blockers and decisions</h3>
  <ul>{list_items(blockers, 8)}</ul>
  <h3>Trust gates</h3>
  <ul>{list_items(trust_gates, 8)}</ul>
  <div class="panel warn"><strong>Boundary:</strong> {esc(pm_update.get('authority_boundary'))}</div>
  <h3>Source stack</h3>
  <ul>{list_items(source_lines, 10)}</ul>
  <div class="footer"><span>Review/proof only. No launch, customer, account, trade, or approval authority.</span><span>Page 2</span></div>
</section>
</body>
</html>"""


def render_pdf(html_path: Path, pdf_path: Path) -> dict[str, Any]:
    browser = find_browser()
    if not browser:
        return {"status": "pdf_unavailable", "reason": "no headless Edge/Chrome browser found"}
    cmd = [
        browser,
        "--headless=new",
        "--disable-gpu",
        "--no-first-run",
        "--disable-extensions",
        f"--print-to-pdf={pdf_path}",
        str(html_path),
    ]
    proc = subprocess.run(cmd, cwd=str(WORKSPACE), text=True, capture_output=True, timeout=90)
    pdf_ok = proc.returncode == 0 and pdf_path.exists() and pdf_path.stat().st_size > 0
    return {
        "status": "ok" if pdf_ok else "pdf_failed",
        "browser": browser,
        "returncode": proc.returncode,
        "stdout_tail": proc.stdout[-1000:],
        "stderr_tail": proc.stderr[-1000:],
        "pdf_size_bytes": pdf_path.stat().st_size if pdf_path.exists() else 0,
    }


def build_manifest(html_out: Path, pdf_out: Path, *, html_only: bool) -> dict[str, Any]:
    source_checks: dict[str, dict[str, Any]] = {}
    errors: list[str] = []
    sources: dict[str, dict[str, Any]] = {}
    for name, path in SOURCE_PATHS.items():
        exists = path.exists()
        source_checks[name] = {"path": relpath(path), "exists": exists}
        if not exists:
            errors.append(f"missing source: {relpath(path)}")
            continue
        try:
            sources[name] = load_json(path)
            source_checks[name]["parseable"] = True
        except Exception as exc:
            source_checks[name]["parseable"] = False
            errors.append(f"unparseable source {relpath(path)}: {exc}")

    manifest = {
        "schema": "veritas.wf75.pm_readiness_pdf.v1",
        "generated_at_utc": utc_now_iso(),
        "status": "pending",
        "outputs": {"html": relpath(html_out), "pdf": relpath(pdf_out), "manifest": relpath(DEFAULT_MANIFEST)},
        "source_checks": source_checks,
        "html_only": html_only,
        "authority_boundary": {
            "public_launch_allowed": False,
            "real_customer_data_allowed": False,
            "external_delivery_allowed": False,
            "source_licensing_assumed": False,
            "legal_or_compliance_ready": False,
            "portfolio_or_canon_mutation_allowed": False,
            "paper_live_or_account_action_allowed": False,
            "owner_approval_inferred": False,
        },
        "errors": errors,
    }
    if errors:
        manifest["status"] = "blocked"
        return manifest

    html_doc = build_html(sources, manifest)
    atomic_write_text(html_out, html_doc)
    manifest["html_size_bytes"] = html_out.stat().st_size
    if html_only:
        manifest["status"] = "html_ready"
    else:
        pdf_result = render_pdf(html_out, pdf_out)
        manifest["pdf_result"] = pdf_result
        manifest["status"] = "ready" if pdf_result.get("status") == "ok" else "blocked"
    return manifest


def validate(manifest: dict[str, Any]) -> list[str]:
    errors = list(manifest.get("errors") or [])
    for key, value in (manifest.get("authority_boundary") or {}).items():
        if value is not False:
            errors.append(f"authority boundary not false: {key}")
    if manifest.get("status") not in {"ready", "html_ready"}:
        errors.append(f"unexpected status: {manifest.get('status')}")
    html_path = WORKSPACE / str((manifest.get("outputs") or {}).get("html", ""))
    if not html_path.exists() or html_path.stat().st_size <= 0:
        errors.append("html output missing or empty")
    if not manifest.get("html_only"):
        pdf_path = WORKSPACE / str((manifest.get("outputs") or {}).get("pdf", ""))
        if not pdf_path.exists() or pdf_path.stat().st_size <= 0:
            errors.append("pdf output missing or empty")
    return errors


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render the WF75 PM readiness brief as HTML and PDF.")
    parser.add_argument("--write", action="store_true", help="Write HTML/PDF and manifest.")
    parser.add_argument("--validate", action="store_true", help="Validate source, outputs, and authority boundaries.")
    parser.add_argument("--html-only", action="store_true", help="Skip PDF rendering.")
    parser.add_argument("--html-out", default=str(DEFAULT_HTML))
    parser.add_argument("--pdf-out", default=str(DEFAULT_PDF))
    parser.add_argument("--manifest-out", default=str(DEFAULT_MANIFEST))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    html_out = Path(args.html_out)
    pdf_out = Path(args.pdf_out)
    manifest_out = Path(args.manifest_out)
    if not html_out.is_absolute():
        html_out = WORKSPACE / html_out
    if not pdf_out.is_absolute():
        pdf_out = WORKSPACE / pdf_out
    if not manifest_out.is_absolute():
        manifest_out = WORKSPACE / manifest_out

    manifest = build_manifest(html_out, pdf_out, html_only=args.html_only)
    errors = validate(manifest) if args.validate else []
    manifest["validation"] = {"status": "ok" if not errors else "blocked", "errors": errors}
    if errors:
        manifest["status"] = "blocked"

    if args.write:
        manifest["outputs"]["manifest"] = relpath(manifest_out)
        atomic_write_json(manifest_out, manifest)
    print(json.dumps(manifest, indent=2))
    return 0 if not errors else 2


if __name__ == "__main__":
    raise SystemExit(main())
