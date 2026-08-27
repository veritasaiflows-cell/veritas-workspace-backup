#!/usr/bin/env python3
"""Render WF75 AI Drop-Service OS isolated-agent training artifacts.

This is an internal training renderer. It packages the already-created
Research Scout and QA Red-Team agent setup into Markdown, HTML, PDF, and a
manifest. It does not bind channels, schedule cron jobs, contact customers,
or expand runtime authority.
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, atomic_write_text

ROOT = Path(__file__).resolve().parents[1]
PROJECT_NOTE = ROOT / "06. Playbooks" / "Project Continuity" / "Workflow 75 - AI Drop-Service OS Agent Training.md"
DELIVERABLE_DIR = ROOT / "10. Deliverables" / "AI Drop-Service OS"
HTML_OUT = DELIVERABLE_DIR / "AI Drop-Service OS Agent Training - 2026-07-03.html"
PDF_OUT = DELIVERABLE_DIR / "AI Drop-Service OS Agent Training - 2026-07-03.pdf"
MANIFEST_OUT = ROOT / "tmp" / "wf75-ai-drop-service-os-agent-training-render.json"
TEAM_BOARD = ROOT / "state" / "ai-drop-service-os" / "team-board.json"
PACKET = ROOT / "tmp" / "wf75-ai-drop-service-os-persistent-agent-training-packet.json"

BROWSER_CANDIDATES = [
    "msedge",
    "chrome",
    "chromium",
    "google-chrome",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
]

AUTHORITY_BOUNDARY = {
    "internal_training_only": True,
    "external_channel_binding_allowed": False,
    "cron_dispatch_allowed": False,
    "customer_public_delivery_allowed": False,
    "credential_or_plugin_mutation_allowed": False,
    "finance_portfolio_or_account_action_allowed": False,
    "owner_approval_inferred": False,
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path | None) -> str | None:
    if path is None:
        return None
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def sha256_file(path: Path) -> str | None:
    if not path.exists():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def esc(value: Any) -> str:
    return html.escape("" if value is None else str(value))


def code(value: str) -> str:
    return f"<code>{esc(value)}</code>"


def list_items(items: list[str]) -> str:
    return "\n".join(f"<li>{esc(item)}</li>" for item in items)


def build_training_model() -> dict[str, Any]:
    board = load_json(TEAM_BOARD)
    packet = load_json(PACKET)
    agents = packet.get("created_agents") or board.get("persistent_agents") or []
    return {
        "generated_at_utc": utc_now(),
        "board_status": board.get("status", "unknown"),
        "workstream_id": packet.get("workstream_id", "AI-DROP-SERVICE-PERSISTENT-AGENTS-20260703"),
        "agents": agents,
        "communication_options": packet.get("communication_options") or board.get("communication_options") or [],
        "stop_lines": packet.get("stop_lines") or [],
        "authority_boundary": AUTHORITY_BOUNDARY,
    }


def architecture_svg() -> str:
    return """
<svg viewBox="0 0 980 250" role="img" aria-label="Agent architecture diagram">
  <defs>
    <marker id="arrow" markerWidth="10" markerHeight="10" refX="7" refY="3" orient="auto">
      <path d="M0,0 L0,6 L8,3 z" fill="#2f5f8f"></path>
    </marker>
  </defs>
  <rect x="24" y="38" width="170" height="70" rx="8" fill="#12345c"></rect>
  <text x="109" y="68" text-anchor="middle" fill="#fff" font-size="18" font-weight="700">Randall</text>
  <text x="109" y="91" text-anchor="middle" fill="#d7e7f7" font-size="13">owner context and final decisions</text>
  <rect x="270" y="24" width="190" height="96" rx="8" fill="#0f766e"></rect>
  <text x="365" y="60" text-anchor="middle" fill="#fff" font-size="18" font-weight="700">Veritas Main</text>
  <text x="365" y="85" text-anchor="middle" fill="#d6fffb" font-size="13">orchestrator, verifier, final answer</text>
  <rect x="542" y="18" width="178" height="82" rx="8" fill="#2563eb"></rect>
  <text x="631" y="52" text-anchor="middle" fill="#fff" font-size="17" font-weight="700">Research Scout</text>
  <text x="631" y="76" text-anchor="middle" fill="#dce9ff" font-size="13">public evidence and source tables</text>
  <rect x="542" y="144" width="178" height="82" rx="8" fill="#b45309"></rect>
  <text x="631" y="178" text-anchor="middle" fill="#fff" font-size="17" font-weight="700">QA Red-Team</text>
  <text x="631" y="202" text-anchor="middle" fill="#fff3df" font-size="13">risk, claims, proof gaps</text>
  <rect x="790" y="66" width="164" height="118" rx="8" fill="#f8fafc" stroke="#b8c6d8" stroke-width="2"></rect>
  <text x="872" y="102" text-anchor="middle" fill="#183654" font-size="17" font-weight="700">Verified Output</text>
  <text x="872" y="128" text-anchor="middle" fill="#41566e" font-size="13">team board</text>
  <text x="872" y="148" text-anchor="middle" fill="#41566e" font-size="13">training packet</text>
  <text x="872" y="168" text-anchor="middle" fill="#41566e" font-size="13">demo deliverables</text>
  <line x1="194" y1="74" x2="270" y2="74" stroke="#2f5f8f" stroke-width="3" marker-end="url(#arrow)"></line>
  <line x1="460" y1="66" x2="542" y2="58" stroke="#2f5f8f" stroke-width="3" marker-end="url(#arrow)"></line>
  <line x1="460" y1="92" x2="542" y2="174" stroke="#2f5f8f" stroke-width="3" marker-end="url(#arrow)"></line>
  <line x1="720" y1="58" x2="790" y2="102" stroke="#2f5f8f" stroke-width="3" marker-end="url(#arrow)"></line>
  <line x1="720" y1="184" x2="790" y2="150" stroke="#2f5f8f" stroke-width="3" marker-end="url(#arrow)"></line>
  <path d="M872 184 C872 225 365 238 365 124" fill="none" stroke="#64748b" stroke-width="2" stroke-dasharray="6 6" marker-end="url(#arrow)"></path>
  <text x="600" y="238" text-anchor="middle" fill="#64748b" font-size="12">helper output loops back through Veritas before Randall relies on it</text>
</svg>
"""


def communication_svg() -> str:
    return """
<svg viewBox="0 0 980 230" role="img" aria-label="Communication options diagram">
  <rect x="28" y="40" width="195" height="120" rx="8" fill="#e8f4ff" stroke="#8bb7e0"></rect>
  <text x="125" y="76" text-anchor="middle" fill="#12345c" font-size="18" font-weight="700">Option 1</text>
  <text x="125" y="104" text-anchor="middle" fill="#12345c" font-size="15">Ask Veritas to route</text>
  <text x="125" y="130" text-anchor="middle" fill="#41566e" font-size="12">safest daily path</text>
  <rect x="272" y="40" width="195" height="120" rx="8" fill="#ecfdf5" stroke="#7ac7a4"></rect>
  <text x="369" y="76" text-anchor="middle" fill="#115e42" font-size="18" font-weight="700">Option 2</text>
  <text x="369" y="104" text-anchor="middle" fill="#115e42" font-size="15">Use CLI agent turn</text>
  <text x="369" y="130" text-anchor="middle" fill="#41566e" font-size="12">direct, internal, no channel binding</text>
  <rect x="516" y="40" width="195" height="120" rx="8" fill="#fff7ed" stroke="#e6b675"></rect>
  <text x="613" y="76" text-anchor="middle" fill="#8a4b05" font-size="18" font-weight="700">Option 3</text>
  <text x="613" y="104" text-anchor="middle" fill="#8a4b05" font-size="15">Persistent session key</text>
  <text x="613" y="130" text-anchor="middle" fill="#41566e" font-size="12">good for continuing a lane</text>
  <rect x="760" y="40" width="195" height="120" rx="8" fill="#fef2f2" stroke="#eba5a5"></rect>
  <text x="857" y="76" text-anchor="middle" fill="#8f1d1d" font-size="18" font-weight="700">Later</text>
  <text x="857" y="104" text-anchor="middle" fill="#8f1d1d" font-size="15">External channels or cron</text>
  <text x="857" y="130" text-anchor="middle" fill="#41566e" font-size="12">owner-gated, not enabled</text>
</svg>
"""


def role_table_html(agents: list[dict[str, Any]]) -> str:
    rows = []
    for agent in agents:
        rows.append(
            "<tr>"
            f"<td><strong>{esc(agent.get('agent_id'))}</strong><br><span class='muted'>{esc(agent.get('identity'))}</span></td>"
            f"<td>{esc(agent.get('model'))}</td>"
            f"<td>{esc(agent.get('role'))}</td>"
            f"<td>{esc(agent.get('first_use'))}</td>"
            "</tr>"
        )
    return "\n".join(rows)


def markdown_doc(model: dict[str, Any]) -> str:
    return f"""# Workflow 75 - AI Drop-Service OS Agent Training

Generated: {model['generated_at_utc']}

## Bottom Line

Two persistent isolated OpenClaw agents now exist for the WF75 AI Drop-Service OS:

- `research-scout`: public-source market, competitor, trend, and vendor research.
- `qa-redteam`: independent critique, risk review, proof gaps, and acceptance checks.

Both agents have isolated workspaces and zero external routing bindings. Veritas main remains the orchestrator and final verifier.

## How To Communicate

### Safest daily path

Tell Veritas main exactly what to send:

```text
Veritas, send this to research-scout: Find 8 sourced examples of AI workflow audit or AI automation sprint offers for small service businesses. Return source links, pricing if available, promise, deliverables, and risk notes.
```

```text
Veritas, send this to qa-redteam: Challenge the AI Workflow Clarity Sprint offer. Find the top 10 claims, privacy, delivery, pricing, and proof risks. Return blockers first.
```

### Direct CLI path

Use a direct internal agent turn:

```powershell
openclaw agent --agent research-scout --message "Find 8 sourced examples of AI workflow audit offers. Return a source table and cite URLs." --json
```

```powershell
openclaw agent --agent qa-redteam --message "Review this offer for weak claims, privacy risk, delivery risk, and missing proof. Return severity-ranked findings." --json
```

Use a persistent session key when you want continuity:

```powershell
openclaw agent --agent research-scout --session-key agent:research-scout:wf75-research --message "Continue the AI workflow audit competitor scan. Add 5 more examples and dedupe against prior notes." --json
```

List stored sessions:

```powershell
openclaw sessions --agent research-scout --json
openclaw sessions --agent qa-redteam --json
```

### Current WebChat limitation

Do not expect `@research-scout` or `@qa-redteam` mentions in this WebChat to route directly yet. The OpenClaw agent-to-agent session tool currently blocks cross-agent sends until cross-agent visibility is enabled in config. I did not change that config in this slice. The direct CLI route above works now, and Veritas can still route tasks for you from the main session.

## Randall's Role

- Set the business objective and quality bar.
- Provide what is real, unknown, blocked, or owner-gated.
- Decide whether outputs are worth turning into a demo, offer, or build lane.
- Never treat helper output as final until Veritas integrates and verifies it.
- Approve any external channel binding, customer use, cron automation, payment/vendor setup, or runtime expansion separately.

## Agent Rules

- Research Scout gathers evidence. It does not decide strategy.
- QA Red-Team challenges claims. It does not approve final delivery.
- Veritas main integrates, verifies, and produces the final user-facing answer.
- External routing, cron dispatch, customer/public use, credentials, vendor/payment accounts, and finance/account actions remain blocked unless explicitly approved.

## Prompt Recipes

Research prompt:

```text
Find [number] sourced examples of [market/offer/tool]. Return: source URL, buyer, promise, price if public, deliverables, evidence quality, and what we can learn for WF75. Do not contact anyone.
```

QA prompt:

```text
Review [artifact/offer/workflow]. Return blockers first, then severity-ranked risks, missing proof, privacy concerns, weak claims, and acceptance criteria. No edits unless assigned.
```

Veritas routing prompt:

```text
Veritas, send Research Scout this exact research task, then send the result to QA Red-Team for critique, then integrate both into a recommendation.
```

## Trend Radar

- Vertical AI services are moving from generic chatbots to specific workflow outcomes.
- SMB lead intake, missed follow-up, support triage, SOP cleanup, and weekly research briefs are practical first offers.
- Buyers will care about trust, privacy, proof, and clear ROI more than the word AI.
- Multi-agent systems need memory, task ownership, stop lines, and QA gates to avoid producing polished confusion.
- Human review remains a selling point, not a weakness.
"""


def html_doc(model: dict[str, Any]) -> str:
    agents = model["agents"]
    stop_lines = model["stop_lines"]
    return f"""<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>AI Drop-Service OS Agent Training</title>
<style>
  @page {{ size: Letter; margin: 0.42in; }}
  * {{ box-sizing: border-box; }}
  body {{ margin: 0; font-family: Arial, Helvetica, sans-serif; color: #172033; background: #fff; font-size: 10px; line-height: 1.36; }}
  .page {{ min-height: 9.7in; page-break-after: always; position: relative; padding-bottom: 0.2in; }}
  .page:last-child {{ page-break-after: auto; }}
  .top {{ border-bottom: 3px solid #12345c; padding-bottom: 9px; margin-bottom: 10px; display: flex; justify-content: space-between; gap: 16px; align-items: flex-start; }}
  h1 {{ margin: 0; color: #0e294a; font-size: 27px; line-height: 1.02; letter-spacing: 0; }}
  h2 {{ margin: 0 0 8px; color: #0e294a; font-size: 18px; letter-spacing: 0; }}
  h3 {{ margin: 10px 0 5px; color: #284f7a; text-transform: uppercase; letter-spacing: .08em; font-size: 9px; }}
  p {{ margin: 4px 0 7px; }}
  ul {{ margin: 5px 0 8px 16px; padding: 0; }}
  li {{ margin: 3px 0; }}
  table {{ width: 100%; border-collapse: collapse; table-layout: fixed; margin: 6px 0 9px; }}
  th, td {{ border: 1px solid #d7e0ea; padding: 6px; vertical-align: top; }}
  th {{ background: #12345c; color: #fff; text-align: left; }}
  code {{ font-family: Consolas, Menlo, monospace; background: #eef3f8; border: 1px solid #d6e0ec; border-radius: 4px; padding: 1px 3px; color: #12345c; }}
  pre {{ white-space: pre-wrap; font-family: Consolas, Menlo, monospace; background: #0f172a; color: #e5eef9; border-radius: 7px; padding: 8px; font-size: 8.3px; line-height: 1.35; margin: 5px 0 8px; }}
  svg {{ width: 100%; height: auto; display: block; }}
  .kicker {{ color: #5a6f88; font-size: 8px; text-transform: uppercase; letter-spacing: .12em; font-weight: bold; }}
  .subtitle {{ color: #50647c; margin-top: 4px; }}
  .panel {{ border: 1px solid #d7e0ea; border-radius: 8px; padding: 8px; background: #f7f9fc; margin: 6px 0; }}
  .panel.dark {{ background: #102a4a; color: #fff; border-color: #102a4a; font-size: 12px; }}
  .panel.warn {{ background: #fff7dd; border-color: #d5a736; }}
  .panel.good {{ background: #eaf8f1; border-color: #91cfae; }}
  .grid2 {{ display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }}
  .grid3 {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; }}
  .metric {{ border: 1px solid #d7e0ea; border-radius: 8px; padding: 7px; background: #fff; min-height: .58in; }}
  .label {{ color: #5a6f88; font-size: 7.5px; text-transform: uppercase; letter-spacing: .08em; margin-bottom: 3px; }}
  .value {{ font-weight: 700; color: #0e294a; font-size: 13px; line-height: 1.15; }}
  .muted {{ color: #65778c; font-size: 8px; }}
  .badge {{ display: inline-block; border-radius: 999px; padding: 2px 7px; font-size: 7.5px; font-weight: bold; background: #e8eef7; color: #244b73; }}
  .goodbadge {{ background: #e5f4ea; color: #176238; }}
  .warnbadge {{ background: #fff0c6; color: #765200; }}
  .badbadge {{ background: #fde8e8; color: #8f1d1d; }}
  .footer {{ position: absolute; left: 0; right: 0; bottom: 0; border-top: 1px solid #e3e8f1; padding-top: 4px; display: flex; justify-content: space-between; color: #6b7b91; font-size: 7.5px; }}
</style>
</head>
<body>
<section class="page">
  <div class="top">
    <div>
      <div class="kicker">WF75 internal training packet</div>
      <h1>AI Drop-Service OS Agent Training</h1>
      <div class="subtitle">Generated {esc(model['generated_at_utc'])} from team board and persistent-agent packet</div>
    </div>
    <span class="badge goodbadge">internal only</span>
  </div>
  <div class="panel dark"><strong>Bottom line:</strong> Research Scout and QA Red-Team now exist as persistent isolated OpenClaw agents. Use them as bounded departments. Veritas main remains the orchestrator, verifier, and final truth surface.</div>
  <div class="grid3">
    <div class="metric"><div class="label">Owner workflow</div><div class="value">WF75</div><div class="muted">AI Drop-Service OS</div></div>
    <div class="metric"><div class="label">Agents created</div><div class="value">{len(agents)}</div><div class="muted">zero external bindings</div></div>
    <div class="metric"><div class="label">Status</div><div class="value">{esc(model['board_status'])}</div></div>
  </div>
  <h3>Architecture</h3>
  <div class="panel">{architecture_svg()}</div>
  <h3>Agent profiles</h3>
  <table>
    <tr><th>Agent</th><th>Model</th><th>Role</th><th>Best first use</th></tr>
    {role_table_html(agents)}
  </table>
  <div class="footer"><span>AI Drop-Service OS Agent Training</span><span>Page 1</span></div>
</section>

<section class="page">
  <div class="top"><div><div class="kicker">Operating model</div><h2>How You Communicate With Agents</h2></div><span class="badge goodbadge">available now</span></div>
  <div class="panel">{communication_svg()}</div>
  <h3>Safest daily path</h3>
  <p>Talk to Veritas main and ask me to route the task. This gives you agent leverage without losing integration, memory, and QA control.</p>
  <pre>Veritas, send this to research-scout:
Find 8 sourced examples of AI workflow audit or AI automation sprint offers for small service businesses. Return source links, pricing if available, promise, deliverables, and risk notes.</pre>
  <pre>Veritas, send this to qa-redteam:
Challenge the AI Workflow Clarity Sprint offer. Find the top 10 claims, privacy, delivery, pricing, and proof risks. Return blockers first.</pre>
  <h3>Direct CLI path</h3>
  <p>Use this when you want to message a configured isolated agent directly through OpenClaw Gateway.</p>
  <pre>openclaw agent --agent research-scout --message "Find 8 sourced examples of AI workflow audit offers. Return a source table and cite URLs." --json</pre>
  <pre>openclaw agent --agent qa-redteam --message "Review this offer for weak claims, privacy risk, delivery risk, and missing proof. Return severity-ranked findings." --json</pre>
  <div class="panel warn"><strong>Current WebChat limitation:</strong> direct <code>@research-scout</code> or <code>@qa-redteam</code> style routing is not enabled in this chat. OpenClaw blocked the agent-to-agent session-send tool until cross-agent visibility is enabled in config. I did not change that config in this slice. Use the CLI path, or ask Veritas main to route the task for you.</div>
  <h3>Persistent session key</h3>
  <p>Use a stable session key when a line of work should continue across turns.</p>
  <pre>openclaw agent --agent research-scout --session-key agent:research-scout:wf75-research --message "Continue the competitor scan. Add 5 examples and dedupe against prior notes." --json</pre>
  <pre>openclaw sessions --agent research-scout --json
openclaw sessions --agent qa-redteam --json</pre>
  <div class="footer"><span>Direct internal use is enabled; external routing remains off.</span><span>Page 2</span></div>
</section>

<section class="page">
  <div class="top"><div><div class="kicker">Training</div><h2>Your Role, Responsibilities, And Prompt Recipes</h2></div><span class="badge warnbadge">human-in-loop</span></div>
  <div class="grid2">
    <div class="panel good"><h3>Randall owns</h3><ul>{list_items([
        "Objective and priority.",
        "Truth about constraints, budget, customer access, and risk tolerance.",
        "Final approval for external channels, cron schedules, customer use, vendors, payments, domains, and outreach.",
        "Decision on whether an output becomes an offer, demo, or build lane.",
    ])}</ul></div>
    <div class="panel"><h3>Veritas owns</h3><ul>{list_items([
        "Routing work to the right agent.",
        "Checking helper output against source artifacts.",
        "Integrating final answers and preserving memory.",
        "Stopping work when authority, privacy, proof, or external-action boundaries are unclear.",
    ])}</ul></div>
  </div>
  <h3>Prompt recipes</h3>
  <table>
    <tr><th>Use case</th><th>Prompt shape</th></tr>
    <tr><td>Research Scout</td><td>{code('Find [number] sourced examples of [market/offer/tool]. Return source URL, buyer, promise, price if public, deliverables, evidence quality, and what we can learn for WF75. Do not contact anyone.')}</td></tr>
    <tr><td>QA Red-Team</td><td>{code('Review [artifact/offer/workflow]. Return blockers first, severity-ranked risks, missing proof, privacy concerns, weak claims, and acceptance criteria. No edits unless assigned.')}</td></tr>
    <tr><td>Multi-agent chain</td><td>{code('Veritas, send Research Scout this research task, then send the result to QA Red-Team for critique, then integrate both into a recommendation.')}</td></tr>
  </table>
  <h3>Trend radar</h3>
  <ul>{list_items([
      "Vertical AI services are moving from generic chatbot promises to specific workflow outcomes.",
      "SMB missed-lead intake, follow-up rescue, SOP cleanup, support triage, and weekly research briefs are practical first offers.",
      "Buyers care about trust, privacy, proof, and ROI more than the word AI.",
      "Multi-agent systems need task ownership, memory, stop lines, and QA gates.",
      "Human review is part of the moat because it prevents polished but unreliable output.",
  ])}</ul>
  <div class="footer"><span>Training page</span><span>Page 3</span></div>
</section>

<section class="page">
  <div class="top"><div><div class="kicker">Boundaries</div><h2>Stop Lines And Next Safe Exercise</h2></div><span class="badge badbadge">do not bypass</span></div>
  <h3>Hard stop lines</h3>
  <ul>{list_items([str(item) for item in stop_lines])}</ul>
  <div class="panel warn"><strong>Current authority:</strong> internal training and bounded internal agent use only. No Telegram, Discord, email, webhook, customer-facing routing, cron dispatch, real customer data, vendor/payment setup, ads, domains, credentials, finance/account action, or external delivery has been approved or enabled.</div>
  <h3>First training exercise</h3>
  <ol>
    <li>Ask Research Scout for a source table on missed-lead automation offers for local service businesses.</li>
    <li>Ask Veritas to summarize what is usable and what is weak.</li>
    <li>Send the summary to QA Red-Team for blockers and acceptance criteria.</li>
    <li>Have Veritas integrate both into a fictional demo brief for the AI Workflow Clarity Sprint.</li>
  </ol>
  <h3>What success looks like</h3>
  <ul>{list_items([
      "Research contains real sources and a clear source-quality column.",
      "QA catches hype, privacy, delivery, pricing, and proof problems.",
      "Veritas produces the final answer and records the durable next action.",
      "No external action happens until you explicitly approve that separate step.",
  ])}</ul>
  <div class="footer"><span>Review/proof only. No external delivery or autonomous dispatch.</span><span>Page 4</span></div>
</section>
</body>
</html>
"""


def browser_candidates() -> list[str]:
    resolved: list[str] = []
    for candidate in BROWSER_CANDIDATES:
        if "\\" in candidate or ":" in candidate:
            if Path(candidate).exists():
                resolved.append(candidate)
        else:
            which = shutil.which(candidate)
            if which:
                resolved.append(which)
    return resolved


def render_pdf(html_path: Path, pdf_path: Path) -> dict[str, Any]:
    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    html_uri = html_path.resolve().as_uri()
    attempts: list[str] = []
    for browser in browser_candidates():
        command = [
            browser,
            "--headless=new",
            "--disable-gpu",
            "--no-first-run",
            "--disable-extensions",
            f"--print-to-pdf={str(pdf_path.resolve())}",
            html_uri,
        ]
        try:
            result = subprocess.run(command, cwd=str(ROOT), capture_output=True, text=True, timeout=90)
        except Exception as exc:
            attempts.append(f"{browser}: {exc}")
            continue
        if result.returncode == 0 and pdf_path.exists() and pdf_path.stat().st_size > 0:
            return {
                "status": "created",
                "renderer": browser,
                "path": rel(pdf_path),
                "size_bytes": pdf_path.stat().st_size,
                "sha256": sha256_file(pdf_path),
            }
        attempts.append(f"{browser}: exit={result.returncode} stderr={(result.stderr or '')[-300:]}")
    return {
        "status": "blocked",
        "reason": "No local Edge/Chrome/Chromium renderer produced a PDF.",
        "attempts": attempts,
    }


def validate_manifest(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for label in ("markdown", "html", "pdf"):
        output = payload["outputs"].get(label)
        if not output:
            errors.append(f"missing output field: {label}")
            continue
        path = ROOT / output
        if not path.exists() or path.stat().st_size <= 0:
            errors.append(f"missing or empty output: {output}")
    if payload.get("pdf", {}).get("status") != "created":
        errors.append("pdf_not_created")
    boundary = payload.get("authority_boundary") or {}
    if boundary.get("internal_training_only") is not True:
        errors.append("training_boundary_not_true")
    for key, value in boundary.items():
        if key != "internal_training_only" and value is not False:
            errors.append(f"authority_boundary_unexpected_true: {key}")
    if len(payload.get("agents") or []) != 2:
        errors.append("expected_two_agents")
    return errors


def build_payload(write: bool) -> dict[str, Any]:
    model = build_training_model()
    md = markdown_doc(model)
    html_text = html_doc(model)
    if write:
        PROJECT_NOTE.parent.mkdir(parents=True, exist_ok=True)
        DELIVERABLE_DIR.mkdir(parents=True, exist_ok=True)
        atomic_write_text(PROJECT_NOTE, md)
        atomic_write_text(HTML_OUT, html_text)
    pdf_result = render_pdf(HTML_OUT, PDF_OUT) if write else {"status": "not_written"}
    payload = {
        "schema": "veritas.wf75.ai_drop_service_agent_training_render.v1",
        "generated_at_utc": model["generated_at_utc"],
        "workflow": "WF75",
        "workstream_id": model["workstream_id"],
        "status": "pending",
        "agents": model["agents"],
        "outputs": {
            "markdown": rel(PROJECT_NOTE),
            "html": rel(HTML_OUT),
            "pdf": rel(PDF_OUT),
            "manifest": rel(MANIFEST_OUT),
        },
        "source_artifacts": {
            "team_board": rel(TEAM_BOARD),
            "persistent_agent_packet": rel(PACKET),
        },
        "pdf": pdf_result,
        "authority_boundary": AUTHORITY_BOUNDARY,
        "validation": {},
    }
    errors = validate_manifest(payload) if write else []
    payload["validation"] = {
        "status": "ok" if not errors else "blocked",
        "errors": errors,
    }
    payload["status"] = "ready" if not errors else "blocked"
    if write:
        atomic_write_json(MANIFEST_OUT, payload)
    return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render WF75 isolated-agent training artifacts.")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    payload = build_payload(write=args.write)
    if args.validate and payload["validation"]["status"] != "ok":
        print(json.dumps(payload, indent=2))
        return 2
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
