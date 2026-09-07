#!/usr/bin/env python3
"""Build the local interactive training catalog / launcher.

The catalog is a static local dashboard generated from existing training
manifests and QA proof. It does not host content, configure an LMS/LRS, send
learner data externally, collect customer data, or infer outreach approval.
"""
from __future__ import annotations

import argparse
import html
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, atomic_write_text


ROOT = Path(__file__).resolve().parents[1]
TRAINING_ROOT = ROOT / "training"
BUILDER_DIR = TRAINING_ROOT / "interactive-training-builder"
BUILDER_PROOF = ROOT / "tmp" / "interactive-training-builder-proof.json"
QA_PROOF = ROOT / "tmp" / "interactive-training-qa-validation.json"
SCORM_PROOF = ROOT / "tmp" / "interactive-training-scorm-smoke-validation.json"
LEDGER_PROOF = ROOT / "tmp" / "interactive-training-xapi-ledger-proof.json"
CATALOG_JSON = BUILDER_DIR / "catalog.json"
CATALOG_HTML = TRAINING_ROOT / "index.html"
PROOF = ROOT / "tmp" / "interactive-training-catalog-proof.json"
RECORDINGS_MANIFEST = BUILDER_DIR / "recordings" / "manifest.json"
RECORDINGS_README_HREF = "interactive-training-builder/recordings/README.md"
WALKTHROUGHS_DIR = BUILDER_DIR / "walkthroughs"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def href_from_catalog(path: str | Path) -> str:
    path_obj = ROOT / path if isinstance(path, str) and not Path(path).is_absolute() else Path(path)
    try:
        return path_obj.resolve().relative_to(TRAINING_ROOT.resolve()).as_posix()
    except ValueError:
        try:
            return "../" + path_obj.resolve().relative_to(ROOT.resolve()).as_posix()
        except ValueError:
            return path_obj.as_posix()


def esc(value: Any) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def load_json(path: Path, default: Any | None = None) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def module_source(module_manifest: dict[str, Any]) -> dict[str, Any]:
    module_path = ROOT / module_manifest["outputs"]["module_json"]
    return load_json(module_path, default={}) or {}


def qa_by_module(qa_proof: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    for item in qa_proof.get("files", []) if isinstance(qa_proof, dict) else []:
        rows[str(item.get("name") or "")] = item
    return rows


def scorm_by_module(scorm_proof: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    if not isinstance(scorm_proof, dict):
        return rows
    for item in scorm_proof.get("static_checks", []):
        rows.setdefault(str(item.get("module_id") or ""), {})["static"] = item
    for item in scorm_proof.get("dynamic_checks", []):
        rows.setdefault(str(item.get("module_id") or ""), {})["dynamic"] = item
    return rows


def qa_summary(row: dict[str, Any] | None) -> dict[str, Any]:
    if not row:
        return {"status": "missing", "severe_axe_violations": None, "console_errors": None, "overflow": None}
    severe = 0
    console = 0
    overflow = 0
    screenshots: list[dict[str, str]] = []
    for viewport in row.get("viewports", []):
        severe += int(viewport.get("severe_axe_violation_count") or 0)
        console += len(viewport.get("console_errors") or [])
        overflow += len(viewport.get("facts", {}).get("overflowing") or [])
        if viewport.get("screenshot"):
            screenshots.append({"viewport": str(viewport.get("viewport")), "href": href_from_catalog(viewport["screenshot"])})
    errors = list(row.get("errors") or [])
    status = "ok" if row.get("status") == "ok" and not errors and severe == 0 and console == 0 and overflow == 0 else "warning"
    return {
        "status": status,
        "severe_axe_violations": severe,
        "console_errors": console,
        "overflow": overflow,
        "screenshots": screenshots,
    }


def scorm_summary(row: dict[str, Any] | None) -> dict[str, Any]:
    if not row:
        return {"status": "missing", "runtime_finished": False}
    static = row.get("static", {})
    dynamic = row.get("dynamic", {})
    errors = list(static.get("errors") or []) + list(dynamic.get("errors") or [])
    status = "ok" if static.get("status") == "ok" and dynamic.get("status") == "ok" and not errors else "warning"
    return {
        "status": status,
        "runtime_initialized": bool(dynamic.get("initialized")),
        "runtime_finished": bool(dynamic.get("finished")),
        "lesson_status": (dynamic.get("values") or {}).get("cmi.core.lesson_status"),
        "screenshot": href_from_catalog(dynamic["screenshot"]) if dynamic.get("screenshot") else None,
    }


def build_catalog() -> dict[str, Any]:
    builder = load_json(BUILDER_PROOF, default={}) or {}
    qa = load_json(QA_PROOF, default={}) or {}
    scorm = load_json(SCORM_PROOF, default={}) or {}
    ledger = load_json(LEDGER_PROOF, default={}) or {}
    qa_rows = qa_by_module(qa)
    scorm_rows = scorm_by_module(scorm)
    modules = []
    errors: list[str] = []
    warnings: list[str] = []
    if builder.get("status") != "ok":
        errors.append("builder_proof_not_ok")
    for module_manifest in builder.get("modules", []):
        source = module_source(module_manifest)
        outputs = module_manifest.get("outputs", {})
        module_id = module_manifest.get("module_id")
        qa_status = qa_summary(qa_rows.get(str(module_id)))
        scorm_status = scorm_summary(scorm_rows.get(str(module_id)))
        module_errors = []
        for key in ["module_html", "module_json", "xapi_seed", "scorm_zip", "module_manifest"]:
            path = ROOT / outputs.get(key, "")
            if not path.exists():
                module_errors.append(f"missing_output:{key}")
        if qa_status["status"] != "ok":
            module_errors.append("qa_not_ok")
        if scorm_status["status"] != "ok":
            module_errors.append("scorm_not_ok")
        modules.append(
            {
                "module_id": module_id,
                "title": source.get("title") or module_id,
                "summary": source.get("summary") or "",
                "audience": source.get("audience") or "",
                "lessons": module_manifest.get("counts", {}).get("lessons"),
                "interactions": module_manifest.get("counts", {}).get("interactions"),
                "generated_at_utc": module_manifest.get("generated_at_utc"),
                "status": "ok" if not module_errors else "warning",
                "errors": module_errors,
                "links": {
                    "launch": href_from_catalog(outputs.get("module_html", "")),
                    "source_json": href_from_catalog(outputs.get("module_json", "")),
                    "manifest": href_from_catalog(outputs.get("module_manifest", "")),
                    "xapi_seed": href_from_catalog(outputs.get("xapi_seed", "")),
                    "scorm_zip": href_from_catalog(outputs.get("scorm_zip", "")),
                },
                "qa": qa_status,
                "scorm": scorm_status,
                "authority_boundary": source.get("authority_boundary") or module_manifest.get("authority_boundary"),
            }
        )
    if not modules:
        errors.append("no_modules_found")
    if qa.get("status") != "ok":
        warnings.append("qa_proof_not_ok_or_missing")
    if scorm.get("status") != "ok":
        warnings.append("scorm_proof_not_ok_or_missing")
    builder_outputs = builder.get("outputs", {}) if isinstance(builder, dict) else {}
    authoring_resources = {
        "authoring_checklist": href_from_catalog(builder_outputs.get("authoring_checklist", "training/interactive-training-builder/authoring-checklist.md")),
        "component_library": href_from_catalog(builder_outputs.get("component_library", "training/interactive-training-builder/component-library.json")),
        "component_library_md": href_from_catalog(builder_outputs.get("component_library_md", "training/interactive-training-builder/component-library.md")),
        "standards_evaluation": href_from_catalog(builder_outputs.get("standards_evaluation", "training/interactive-training-builder/standards-upgrade-evaluation.json")),
    }
    clips = load_recordings()
    walkthroughs = load_walkthroughs()
    catalog = {
        "schema": "veritas.interactive_training_catalog.v1",
        "generated_at_utc": utc_now(),
        "status": "ok" if not errors and all(module["status"] == "ok" for module in modules) else "warning",
        "modules": modules,
        "authoring_resources": authoring_resources,
        "proof": {
            "builder": rel(BUILDER_PROOF),
            "qa": rel(QA_PROOF),
            "scorm": rel(SCORM_PROOF),
            "ledger": rel(LEDGER_PROOF),
        },
        "xapi_ledger": {
            "optional": True,
            "default_endpoint": ledger.get("default_endpoint") or "http://127.0.0.1:8766/xapi",
            "serve_command": (ledger.get("usage") or {}).get(
                "serve",
                "python scripts\\interactive_training_xapi_ledger.py --serve",
            ),
            "external_lrs_configured": False,
        },
        "counts": {
            "modules": len(modules),
            "lessons": sum(int(module.get("lessons") or 0) for module in modules),
            "interactions": sum(int(module.get("interactions") or 0) for module in modules),
            "qa_ok": sum(1 for module in modules if module["qa"]["status"] == "ok"),
            "scorm_ok": sum(1 for module in modules if module["scorm"]["status"] == "ok"),
            "local_clips": len(clips),
            "teaching_walkthroughs": len(walkthroughs),
        },
        "recordings": {
            "manifest": rel(RECORDINGS_MANIFEST),
            "readme": RECORDINGS_README_HREF,
            "clips": clips,
        },
        "walkthroughs": walkthroughs,
        "capabilities": {
            "screen_recording_player": True,
            "local_screen_capture_helper": True,
            "external_lms_lrs_configured": False,
        },
        "validation": {"errors": errors, "warnings": warnings},
        "authority_boundary": {
            "local_files_only": True,
            "external_lms_lrs_configured": False,
            "learner_data_external_transport": False,
            "customer_data_allowed": False,
            "public_delivery_approved": False,
            "owner_approval_inferred": False,
        },
    }
    return catalog


def load_walkthroughs() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not WALKTHROUGHS_DIR.exists():
        return rows
    for path in sorted(WALKTHROUGHS_DIR.glob("*.html")):
        rows.append(
            {
                "file": f"interactive-training-builder/walkthroughs/{path.name}",
                "title": path.stem.replace("-", " "),
                "watch_only": True,
            }
        )
    return rows


def load_recordings() -> list[dict[str, Any]]:
    manifest = load_json(RECORDINGS_MANIFEST, default={}) or {}
    clips = manifest.get("clips") or []
    return [clip for clip in clips if isinstance(clip, dict)]


def render_status(value: str) -> str:
    label = value.upper()
    cls = "ok" if value == "ok" else "warn"
    return f'<span class="badge {cls}">{esc(label)}</span>'


def render_walkthroughs_section(walkthroughs: list[dict[str, Any]]) -> str:
    items = "\n".join(
        f'        <li><a href="{esc(item.get("file"))}">Watch {esc(item.get("title"))}</a></li>'
        for item in walkthroughs
    ) or "        <li>No teaching walkthroughs are published yet.</li>"
    return (
        '    <section class="ledger recordings" aria-label="Teaching walkthroughs">\n'
        '      <h2>Teaching walkthroughs</h2>\n'
        '      <p>Watch-only local lessons. You do not record these. Open one, then return to the Day 1 module and mark it reviewed.</p>\n'
        '      <ul class="clip-list">\n'
        f'{items}\n'
        '      </ul>\n'
        '    </section>\n'
    )


def render_recordings_section(clips: list[dict[str, Any]]) -> str:
    if clips:
        items = "\n".join(
            f'        <li><code>{esc(clip.get("file"))}</code> ({esc(clip.get("size_bytes"))} bytes)</li>'
            for clip in clips
        )
        return (
            '    <section class="ledger recordings" aria-label="Local screen recordings">\n'
            '      <h2>Local screen recordings</h2>\n'
            f'      <p>{len(clips)} local clip(s) available to module players. Files stay on this machine.</p>\n'
            '      <ul class="clip-list">\n'
            f'{items}\n'
            '      </ul>\n'
            '    </section>\n'
        )
    return (
        '    <section class="ledger recordings" aria-label="Local screen recordings">\n'
        '      <h2>Local screen recordings</h2>\n'
        '      <p>Optional later. Teaching walkthroughs above are what you watch. A raw clip is not required for Day 1. '
        'If one is captured later, Windows Snipping Tool (<code>ms-screenclip</code> / <code>Win+Shift+R</code>) '
        'can save <code>.webm</code> or <code>.mp4</code> under recordings/.</p>\n'
        '      <div class="actions">\n'
        f'        <a class="button" href="{esc(RECORDINGS_README_HREF)}">Capture instructions</a>\n'
        '      </div>\n'
        '    </section>\n'
    )


def render_catalog_html(catalog: dict[str, Any]) -> str:
    data = json.dumps(catalog, ensure_ascii=False)
    resources = catalog.get("authoring_resources", {})
    recordings = render_recordings_section(catalog.get("recordings", {}).get("clips", []))
    walkthroughs = render_walkthroughs_section(catalog.get("walkthroughs") or [])
    module_cards = []
    for module in catalog["modules"]:
        screenshots = " ".join(
            f'<a href="{esc(item["href"])}">{esc(item["viewport"])} screenshot</a>'
            for item in module["qa"].get("screenshots", [])
        )
        scorm_screenshot = (
            f'<a href="{esc(module["scorm"]["screenshot"])}">SCORM smoke screenshot</a>'
            if module["scorm"].get("screenshot")
            else ""
        )
        module_cards.append(
            f"""
    <article class="module-card" data-module="{esc(module['module_id'])}">
      <div class="module-main">
        <div>
          <p class="eyebrow">{esc(module['audience'])}</p>
          <h2>{esc(module['title'])}</h2>
          <p>{esc(module['summary'])}</p>
        </div>
        <div class="status-stack">
          {render_status(module['status'])}
          <span>{esc(module['lessons'])} lessons</span>
          <span>{esc(module['interactions'])} interactions</span>
        </div>
      </div>
      <dl class="facts">
        <div><dt>QA</dt><dd>{render_status(module['qa']['status'])}</dd></div>
        <div><dt>SCORM</dt><dd>{render_status(module['scorm']['status'])}</dd></div>
        <div><dt>Local progress</dt><dd><span id="progress-{esc(module['module_id'])}">Not started</span></dd></div>
        <div><dt>Events</dt><dd><span id="events-{esc(module['module_id'])}">0</span></dd></div>
      </dl>
      <div class="actions">
        <a class="button primary" href="{esc(module['links']['launch'])}">Launch</a>
        <a class="button" href="{esc(module['links']['scorm_zip'])}" download>Download SCORM</a>
        <a class="button" href="{esc(module['links']['manifest'])}">Manifest</a>
        <a class="button" href="{esc(module['links']['xapi_seed'])}">xAPI seed</a>
        <a class="button" href="{esc(module['links']['source_json'])}">Source JSON</a>
      </div>
      <div class="proof-links">{screenshots} {scorm_screenshot}</div>
    </article>"""
        )
    cards = "\n".join(module_cards)
    return (
        "<!doctype html>\n"
        '<html lang="en">\n'
        "<head>\n"
        '  <meta charset="utf-8">\n'
        '  <meta name="viewport" content="width=device-width, initial-scale=1">\n'
        "  <title>Veritas Local Training Catalog</title>\n"
        "  <style>\n"
        "    :root { color-scheme: light dark; --ink:#17202a; --muted:#5a6472; --line:#d8dde6; --paper:#f6f7f9; --panel:#fff; --green:#0b6b4f; --blue:#2457a6; --amber:#9a5b00; --red:#a33a2a; }\n"
        "    * { box-sizing: border-box; }\n"
        "    body { margin:0; font-family: Segoe UI, Arial, sans-serif; background:var(--paper); color:var(--ink); line-height:1.45; }\n"
        "    header.catalog-hero { background:linear-gradient(135deg, #101820 0%, #1b3a55 60%, #0b6b4f 130%); background-color:#101820; color:#fff; border-bottom:4px solid var(--green); }\n"
        "    header.catalog-hero p { color:#dbe4ee; }\n"
        "    header.catalog-hero .summary div { border-left:6px solid var(--blue); }\n"
        "    .visual-rail { height:6px; border-radius:999px; background:linear-gradient(90deg, var(--green), var(--blue)); margin-bottom:12px; }\n"
        "    header, main { max-width:1180px; margin:0 auto; padding:24px; }\n"
        "    header { padding-top:28px; }\n"
        "    h1 { margin:0 0 8px; font-size:clamp(28px, 4vw, 44px); letter-spacing:0; }\n"
        "    h2 { margin:0 0 8px; font-size:22px; letter-spacing:0; }\n"
        "    p { margin:0 0 12px; color:var(--muted); }\n"
        "    .summary { display:grid; grid-template-columns:repeat(auto-fit, minmax(180px, 1fr)); gap:10px; margin-top:18px; }\n"
        "    .summary div, .ledger, .module-card { background:var(--panel); border:1px solid var(--line); border-radius:8px; }\n"
        "    .summary div { padding:14px; border-left:6px solid var(--green); }\n"
        "    .summary strong { display:block; font-size:24px; }\n"
        "    .summary .chip { display:inline-block; padding:2px 10px; border-radius:999px; background:#e8eef6; color:var(--blue); font-size:12px; font-weight:700; }\n"
        "    .ledger { padding:16px; margin:4px 0 18px; }\n"
        "    .ledger-grid { display:grid; grid-template-columns:minmax(180px, 1fr) auto auto; gap:10px; align-items:end; }\n"
        "    label { display:block; color:var(--muted); font-size:13px; margin-bottom:4px; }\n"
        "    input { width:100%; padding:10px 12px; border:1px solid var(--line); border-radius:6px; font:inherit; }\n"
        "    code { background:#edf0f5; padding:2px 5px; border-radius:4px; }\n"
        "    .module-grid { display:grid; gap:14px; }\n"
        "    .module-card { padding:18px; border-left:6px solid var(--blue); border-radius:12px; }\n"
        "    .recordings { border-left:6px solid var(--green); border-radius:12px; }\n"
        "    .clip-list { margin:8px 0 0; padding-left:20px; color:var(--muted); }\n"
        "    :focus-visible { outline:3px solid var(--blue); outline-offset:2px; border-radius:6px; }\n"
        "    @media (prefers-color-scheme: dark) { :root { --ink:#e8edf3; --muted:#aab6c4; --line:#2c3a4a; --paper:#0e141b; --panel:#17202b; --green:#2dd4bf; --blue:#7aa7f0; --amber:#e0a63c; --red:#e08a8a; } header.catalog-hero { background:#101820; } code { background:#243242; color:var(--ink); } .summary div, .ledger, .module-card { background:var(--panel); } .button { background:#1c2836; color:var(--ink); } input { background:#101820; color:var(--ink); border-color:var(--line); } .facts div { border-color:var(--line); } }\n"
        "    .module-main { display:grid; grid-template-columns:1fr auto; gap:16px; align-items:start; }\n"
        "    .eyebrow { margin:0 0 6px; color:var(--blue); font-weight:700; font-size:13px; }\n"
        "    .status-stack { display:flex; flex-direction:column; gap:6px; align-items:flex-end; color:var(--muted); white-space:nowrap; }\n"
        "    .badge { display:inline-block; min-width:64px; text-align:center; padding:4px 8px; border-radius:999px; font-size:12px; font-weight:700; }\n"
        "    .badge.ok { color:#fff; background:var(--green); }\n"
        "    .badge.warn { color:#fff; background:var(--amber); }\n"
        "    .facts { display:grid; grid-template-columns:repeat(auto-fit, minmax(150px, 1fr)); gap:10px; margin:14px 0; }\n"
        "    .facts div { border:1px solid var(--line); border-radius:6px; padding:10px; }\n"
        "    dt { color:var(--muted); font-size:13px; }\n"
        "    dd { margin:4px 0 0; font-weight:700; }\n"
        "    .actions, .proof-links { display:flex; flex-wrap:wrap; gap:8px; margin-top:10px; }\n"
        "    .button { display:inline-flex; align-items:center; min-height:38px; padding:8px 12px; border-radius:6px; border:1px solid var(--line); background:#fff; color:var(--ink); text-decoration:none; font-weight:700; cursor:pointer; }\n"
        "    .button.primary { background:var(--blue); color:#fff; border-color:var(--blue); }\n"
        "    .button.danger { border-color:var(--red); color:var(--red); }\n"
        "    .proof-links a { color:var(--blue); }\n"
        "    .note { color:var(--muted); margin-top:10px; }\n"
        "    @media (max-width:680px) { header, main { padding:18px; } .module-main, .ledger-grid { grid-template-columns:1fr; } .status-stack { align-items:flex-start; } .button { width:100%; justify-content:center; } }\n"
        "  </style>\n"
        "</head>\n"
        "<body>\n"
        "  <header class=\"catalog-hero\">\n"
        "    <div class=\"visual-rail\" aria-hidden=\"true\"></div>\n"
        "    <h1>Veritas Local Training Catalog</h1>\n"
        "    <p>Internal training launcher for local HTML modules, QA proof, SCORM packages, and optional loopback xAPI capture.</p>\n"
        "    <section class=\"summary\" aria-label=\"Catalog summary\">\n"
        f"      <div><span>Modules</span><strong>{esc(catalog['counts']['modules'])}</strong><span class=\"chip\">local</span></div>\n"
        f"      <div><span>Lessons</span><strong>{esc(catalog['counts']['lessons'])}</strong><span class=\"chip\">local</span></div>\n"
        f"      <div><span>Interactions</span><strong>{esc(catalog['counts']['interactions'])}</strong><span class=\"chip\">local</span></div>\n"
        f"      <div><span>Catalog status</span><strong>{esc(catalog['status'].upper())}</strong><span class=\"chip\">internal only</span></div>\n"
        "    </section>\n"
        "  </header>\n"
        "  <main>\n"
        f"{walkthroughs}\n"
        f"{recordings}\n"
        "    <section class=\"ledger\" aria-label=\"Local xAPI ledger controls\">\n"
        "      <h2>Local xAPI Ledger</h2>\n"
        "      <p>Optional. Start the collector in PowerShell, then enable capture here. Events stay on this machine.</p>\n"
        f"      <p><code>{esc(catalog['xapi_ledger']['serve_command'])}</code></p>\n"
        "      <div class=\"ledger-grid\">\n"
        "        <div><label for=\"endpoint\">Endpoint</label><input id=\"endpoint\" value=\"http://127.0.0.1:8766/xapi\"></div>\n"
        "        <button class=\"button primary\" type=\"button\" id=\"toggleLedger\">Enable ledger</button>\n"
        "        <button class=\"button\" type=\"button\" id=\"exportProgress\">Export local progress</button>\n"
        "      </div>\n"
        "      <p class=\"note\" id=\"ledgerState\">Ledger capture is off.</p>\n"
        "    </section>\n"
        "    <section class=\"ledger\" aria-label=\"Authoring resources\">\n"
        "      <h2>Authoring Resources</h2>\n"
        "      <p>Use these local files when creating the next schema-backed module.</p>\n"
        "      <div class=\"actions\">\n"
        f"        <a class=\"button\" href=\"{esc(resources.get('authoring_checklist', 'interactive-training-builder/authoring-checklist.md'))}\">Authoring checklist</a>\n"
        f"        <a class=\"button\" href=\"{esc(resources.get('component_library_md', 'interactive-training-builder/component-library.md'))}\">Component library</a>\n"
        f"        <a class=\"button\" href=\"{esc(resources.get('component_library', 'interactive-training-builder/component-library.json'))}\">Component JSON</a>\n"
        f"        <a class=\"button\" href=\"{esc(resources.get('standards_evaluation', 'interactive-training-builder/standards-upgrade-evaluation.json'))}\">Standards evaluation</a>\n"
        "      </div>\n"
        "    </section>\n"
        "    <section class=\"module-grid\" aria-label=\"Training modules\">\n"
        f"{cards}\n"
        "    </section>\n"
        "    <p class=\"note\">Boundary: local/internal only. No external LMS/LRS, public delivery, customer data, outreach, payment, credentials, or production access is approved by this catalog.</p>\n"
        "  </main>\n"
        "  <script>\n"
        f"    const CATALOG = {data};\n"
        "    const LEDGER_ENABLED_KEY = 'veritas.training.xapiLedger.enabled';\n"
        "    const LEDGER_ENDPOINT_KEY = 'veritas.training.xapiLedger.endpoint';\n"
        "    const endpoint = document.getElementById('endpoint');\n"
        "    const toggle = document.getElementById('toggleLedger');\n"
        "    const ledgerState = document.getElementById('ledgerState');\n"
        "    endpoint.value = localStorage.getItem(LEDGER_ENDPOINT_KEY) || CATALOG.xapi_ledger.default_endpoint;\n"
        "    function ledgerEnabled() { return localStorage.getItem(LEDGER_ENABLED_KEY) === 'true'; }\n"
        "    function saveLedgerState(enabled) { localStorage.setItem(LEDGER_ENABLED_KEY, enabled ? 'true' : 'false'); localStorage.setItem(LEDGER_ENDPOINT_KEY, endpoint.value); renderLedgerState(); }\n"
        "    function renderLedgerState() { const enabled = ledgerEnabled(); toggle.textContent = enabled ? 'Disable ledger' : 'Enable ledger'; ledgerState.textContent = enabled ? 'Ledger capture is on for modules opened from this browser.' : 'Ledger capture is off.'; }\n"
        "    function moduleState(moduleId) { try { return JSON.parse(localStorage.getItem('veritas.training.' + moduleId) || '{}'); } catch { return {}; } }\n"
        "    function renderProgress() { CATALOG.modules.forEach(module => { const state = moduleState(module.module_id); const answers = state.answers || {}; const done = Object.values(answers).filter(row => row && row.completed).length; const progress = document.getElementById('progress-' + module.module_id); const events = document.getElementById('events-' + module.module_id); if (progress) progress.textContent = done ? done + '/' + module.interactions + ' complete' : 'Not started'; if (events) events.textContent = String((state.events || []).length); }); }\n"
        "    function exportProgress() { const payload = { exported_at_utc: new Date().toISOString(), modules: CATALOG.modules.map(module => ({ module_id: module.module_id, title: module.title, state: moduleState(module.module_id) })) }; const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' }); const link = document.createElement('a'); link.href = URL.createObjectURL(blob); link.download = 'veritas-training-local-progress.json'; link.click(); URL.revokeObjectURL(link.href); }\n"
        "    toggle.addEventListener('click', () => saveLedgerState(!ledgerEnabled()));\n"
        "    endpoint.addEventListener('change', () => localStorage.setItem(LEDGER_ENDPOINT_KEY, endpoint.value));\n"
        "    document.getElementById('exportProgress').addEventListener('click', exportProgress);\n"
        "    renderLedgerState(); renderProgress(); window.addEventListener('storage', renderProgress);\n"
        "  </script>\n"
        "</body>\n"
        "</html>\n"
    )


def validate_catalog(catalog: dict[str, Any], html_text: str) -> list[str]:
    errors = list(catalog.get("validation", {}).get("errors") or [])
    if '<html lang="en">' not in html_text:
        errors.append("html_lang_missing")
    for marker in ["Enable ledger", "Authoring checklist", "Component library", "Launch", "Download SCORM", "Teaching walkthroughs", "Local screen recordings", "veritas.training.xapiLedger.enabled"]:
        if marker not in html_text:
            errors.append(f"html_marker_missing:{marker}")
    if catalog["authority_boundary"]["external_lms_lrs_configured"] is not False:
        errors.append("external_lms_lrs_boundary_not_false")
    return errors


def build(write: bool = False) -> dict[str, Any]:
    catalog = build_catalog()
    html_text = render_catalog_html(catalog)
    errors = validate_catalog(catalog, html_text)
    proof = {
        "schema": "veritas.interactive_training_catalog_builder_proof.v1",
        "generated_at_utc": utc_now(),
        "status": "ok" if not errors else "blocked",
        "catalog": rel(CATALOG_JSON),
        "launcher": rel(CATALOG_HTML),
        "counts": catalog["counts"],
        "validation": {"errors": errors, "warnings": catalog["validation"]["warnings"]},
        "authority_boundary": catalog["authority_boundary"],
    }
    catalog["status"] = "ok" if proof["status"] == "ok" else "warning"
    if write:
        BUILDER_DIR.mkdir(parents=True, exist_ok=True)
        TRAINING_ROOT.mkdir(parents=True, exist_ok=True)
        atomic_write_json(CATALOG_JSON, catalog)
        atomic_write_text(CATALOG_HTML, html_text)
        atomic_write_json(PROOF, proof)
    return proof


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    args = parser.parse_args()
    proof = build(write=args.write)
    print(json.dumps(proof, indent=2, sort_keys=True))
    if args.validate and proof["validation"]["errors"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
