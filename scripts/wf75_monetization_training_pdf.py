#!/usr/bin/env python3
"""Render the WF75 AI Workflow Clarity Sprint monetization training packet.

This is an internal training renderer. It packages the current WF75
monetization plan into Markdown, HTML, PDF, and a manifest. It does not approve
outreach, customer delivery, payment setup, channel binding, cron mutation,
credential use, finance actions, or public launch.
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
DELIVERABLE_DIR = ROOT / "10. Deliverables" / "AI Drop-Service OS"
TITLE = "AI Workflow Clarity Sprint Monetization Training"
DATE = "2026-07-03"
MD_OUT = DELIVERABLE_DIR / f"{TITLE} - {DATE}.md"
HTML_OUT = DELIVERABLE_DIR / f"{TITLE} - {DATE}.html"
PDF_OUT = DELIVERABLE_DIR / f"{TITLE} - {DATE}.pdf"
MANIFEST_OUT = ROOT / "tmp" / "wf75-ai-workflow-clarity-sprint-monetization-training-render.json"
CONTINUITY_OUT = (
    ROOT
    / "06. Playbooks"
    / "Project Continuity"
    / f"Workflow 75 - AI Workflow Clarity Sprint Monetization Training - {DATE}.md"
)
TEAM_BOARD = ROOT / "state" / "ai-drop-service-os" / "team-board.json"
FINDINGS_INDEX = ROOT / "tmp" / "wf75-agent-workspace-findings-index.json"
DEMO_PACKET = ROOT / "tmp" / "wf75-missed-lead-demo-v1" / "packet.json"
IMPLEMENTATION_PLAN = ROOT / "tmp" / "wf75-ai-drop-service-os-full-implementation-plan.json"

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
    "external_outreach_allowed": False,
    "customer_or_public_delivery_allowed": False,
    "payment_or_vendor_account_setup_allowed": False,
    "channel_binding_allowed": False,
    "cron_schedule_mutation_allowed": False,
    "config_auth_runtime_mutation_allowed": False,
    "customer_data_allowed": False,
    "finance_canon_or_portfolio_mutation_allowed": False,
    "paper_or_live_execution_allowed": False,
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


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    value = json.loads(path.read_text(encoding="utf-8"))
    return value if isinstance(value, dict) else {}


def sha256_file(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def esc(value: Any) -> str:
    return html.escape("" if value is None else str(value))


def slug(title: str) -> str:
    return "".join(ch.lower() if ch.isalnum() else "-" for ch in title).strip("-")


def source_status(path: Path) -> dict[str, Any]:
    payload: dict[str, Any] = {"path": rel(path), "exists": path.exists()}
    if not path.exists():
        return payload
    try:
        data = load_json(path)
        payload.update(
            {
                "parseable": True,
                "schema": data.get("schema"),
                "status": data.get("status"),
            }
        )
    except Exception as exc:  # pragma: no cover - defensive manifest detail
        payload.update({"parseable": False, "error": str(exc)})
    return payload


def build_model() -> dict[str, Any]:
    board = load_json(TEAM_BOARD)
    findings = load_json(FINDINGS_INDEX)
    demo = load_json(DEMO_PACKET)
    plan = load_json(IMPLEMENTATION_PLAN)
    research = (findings.get("agent_outputs") or {}).get("research_scout") or {}
    qa = (findings.get("agent_outputs") or {}).get("qa_redteam") or {}
    readiness = qa.get("readiness_gate") or {}
    return {
        "generated_at_utc": utc_now(),
        "board_status": board.get("status", "unknown"),
        "current_slice": board.get("current_slice") or {},
        "private_pilot_ready": bool(readiness.get("private_pilot_prep_ready")),
        "qa_decision": qa.get("decision", "unknown"),
        "research_status": research.get("status", "unknown"),
        "qa_status": qa.get("status", "unknown"),
        "niche_recommendation": research.get("niche_recommendation") or [],
        "required_next_steps": findings.get("required_next_steps") or [],
        "demo_status": demo.get("status", "unknown"),
        "plan_status": plan.get("status", "unknown"),
        "authority_boundary": AUTHORITY_BOUNDARY,
        "sources": {
            "team_board": source_status(TEAM_BOARD),
            "findings_index": source_status(FINDINGS_INDEX),
            "demo_packet": source_status(DEMO_PACKET),
            "implementation_plan": source_status(IMPLEMENTATION_PLAN),
        },
    }


def first_niche_text(model: dict[str, Any]) -> str:
    niches = model.get("niche_recommendation") or []
    if not niches:
        return "HVAC or plumbing"
    names = [str(item.get("niche")) for item in niches[:2] if isinstance(item, dict) and item.get("niche")]
    return " or ".join(names) if names else "HVAC or plumbing"


def key_value_rows(items: list[tuple[str, str]]) -> str:
    return "\n".join(f"| {key} | {value} |" for key, value in items)


def section(title: str, paragraphs: list[str] | None = None, bullets: list[str] | None = None) -> dict[str, Any]:
    return {"title": title, "paragraphs": paragraphs or [], "bullets": bullets or []}


def training_sections(model: dict[str, Any]) -> list[dict[str, Any]]:
    first_niche = first_niche_text(model)
    return [
        section(
            "Blunt Current Verdict",
            [
                "The AI Drop-Service OS foundation is real enough to train on, but it is not yet a customer-ready monetization machine.",
                "The right first offer remains the AI Workflow Clarity Sprint for one low-regulation local service niche, with HVAC or plumbing as the leading first candidates.",
                "The operating goal is simple: sell a fixed-scope diagnostic and implementation-readiness service, not a vague AI agency promise.",
            ],
            [
                f"Current board status: {model['board_status']}.",
                f"Research Scout status: {model['research_status']}. QA Red-Team status: {model['qa_status']}.",
                f"QA decision: {model['qa_decision']}. Private pilot prep ready: {model['private_pilot_ready']}.",
                "Use this training to prepare the operator, offer, demo, and delivery process. Do not use it as launch approval.",
            ],
        ),
        section(
            "What We Are Selling",
            [
                "The Sprint is a five-business-day workflow diagnosis for a small service business that is losing time or leads because intake, follow-up, handoffs, or admin work are messy.",
                "The buyer should understand the pain immediately. The offer should not require them to understand OpenClaw, agents, AI architecture, or no-code tooling.",
            ],
            [
                "One workflow only.",
                "One clear pain point: missed leads, slow intake, weak follow-up, manual handoffs, or admin drag.",
                "One output: a practical workflow map, gap list, automation opportunity map, implementation backlog, and synthetic proof/demo.",
                "No production system change, no credentials, no customer data, and no ROI promise in the first paid version.",
            ],
        ),
        section(
            "Why HVAC Or Plumbing First",
            [
                "HVAC and plumbing are good first niches because the pain is concrete: urgent requests, phone-heavy lead flow, after-hours contact, quote follow-up, and service scheduling friction.",
                "They are easier to explain than broad consulting and less regulated than medical, finance, tax, legal, or insurance workflows.",
            ],
            [
                "A missed call or slow callback is easy for the owner to understand.",
                "The workflow can be diagnosed without touching private customer systems.",
                "A synthetic missed-lead demo is credible as a training tool when all fictional data is labeled.",
                "The offer can stay narrow: response-time workflow, acknowledgement copy, triage rules, escalation path, and owner review report.",
            ],
        ),
        section(
            "What Randall Needs To Know Before Selling",
            [
                "The first risk is not technical. The first risk is overpromising. The pitch must sound practical, grounded, and limited.",
                "You do not need to become a Zapier, Make, n8n, CRM, call tracking, or sales expert before the first test. You do need enough fluency to ask good workflow questions and avoid fake certainty.",
            ],
            [
                "Know the problem: lead leakage, response delays, unclear handoff ownership, and untracked follow-up.",
                "Know the offer: a diagnostic Sprint, not a full automation build.",
                "Know the boundary: no customer credentials, production edits, sensitive data, guarantee, or compliance claim.",
                "Know the close: the first paid pilot buys a clear map and readiness plan, not a magic AI system.",
            ],
        ),
        section(
            "How The OS Will Work",
            [
                "Veritas main stays the control plane. Research Scout gathers public evidence and examples. QA Red-Team challenges claims, proof, privacy, and delivery risk. Veritas integrates the final packet.",
                "This is a deliberate review loop, not always-on autonomous business operation.",
            ],
            [
                "Before offer or niche work: Research Scout gathers source-labeled evidence.",
                "During drafting: Veritas turns findings into the offer, intake script, demo, and delivery SOP.",
                "Before customer-facing use: QA Red-Team reviews every claim, deliverable, and boundary.",
                "After QA: Veritas resolves the blockers and writes the final decision surface.",
            ],
        ),
        section(
            "The Weekly Operating Cadence",
            [
                "While WF75 is active, the minimum cadence should be one short evidence refresh and one QA review each week, plus task-specific agent runs before any material offer change.",
            ],
            [
                "Monday or first work block: Research Scout refreshes one niche, one competitor set, or one proof gap.",
                "Midweek: Veritas drafts or updates the offer, intake questions, demo, and delivery packet.",
                "Before end of week: QA Red-Team reviews claims and readiness.",
                "Veritas closes the loop by updating the board, continuity note, and next action.",
            ],
        ),
        section(
            "Pricing Plan",
            [
                "The first monetization goal is not maximum revenue. It is proof that a real owner will pay for a concrete workflow clarity outcome.",
            ],
            [
                "First 1 to 3 private beta pilots: $500 to $750.",
                "Standard diagnostic after proof: around $1,500.",
                "Optional implementation add-on after repeat proof: $2,500 to $5,000.",
                "Do not offer the implementation add-on until the diagnostic is easy to deliver and QA can keep claims clean.",
            ],
        ),
        section(
            "Five-Day Delivery Model",
            [
                "The Sprint should feel simple to the buyer and disciplined internally. The customer sees clarity. The OS handles research, structure, QA, and proof.",
            ],
            [
                "Day 1: intake call, workflow scope, current-state map, and missing-data list.",
                "Day 2: process reconstruction, failure points, handoff map, and first automation ideas.",
                "Day 3: synthetic demo or example flow using fictional/anonymized data only.",
                "Day 4: implementation backlog, tool-stack options, risk boundaries, and cost/effort notes.",
                "Day 5: final report, walkthrough, recommendations, and optional next-step proposal.",
            ],
        ),
        section(
            "Discovery Call Framework",
            [
                "The discovery call should diagnose whether the owner has a workflow problem worth solving. It should not sound like a technical interrogation.",
            ],
            [
                "Ask what happens when a new service request arrives.",
                "Ask who owns the first response and what happens after hours.",
                "Ask what information is usually missing before a quote or callback.",
                "Ask where leads fall through: calls, forms, email, texts, voicemails, scheduling, or follow-up.",
                "Ask what they already use: website forms, CRM, calendar, phone system, call tracking, email, SMS, spreadsheets.",
                "Ask what they want reduced: missed calls, manual reminders, double entry, status confusion, or slow follow-up.",
            ],
        ),
        section(
            "What Not To Say",
            [
                "The easiest way to damage trust is to make the offer sound more proven than it is. Keep the language conservative until pilot evidence exists.",
            ],
            [
                "Do not claim guaranteed revenue growth.",
                "Do not claim a validated 15-minute SLA as an industry rule.",
                "Do not claim the 5/10/15/1440 cadence is externally proven.",
                "Do not call this compliance-ready, security-vetted, or legally reviewed.",
                "Do not imply we can connect to their systems during the diagnostic without separate approval.",
                "Do not collect sensitive customer data for the first version.",
            ],
        ),
        section(
            "Safe Customer-Facing Language",
            [
                "The first offer can safely use problem-discovery language. It should not use outcome claims that require proof we do not have yet.",
            ],
            [
                "Safe: We map where leads, follow-ups, and handoffs slow down.",
                "Safe: We identify practical automation opportunities and risk boundaries.",
                "Safe: We produce an implementation-ready workflow plan for one process.",
                "Safe: We use a synthetic demo to show the proposed flow without touching live systems.",
                "Avoid: We increase revenue by X percent.",
                "Avoid: We recover every missed lead.",
                "Avoid: This is guaranteed to improve close rates.",
            ],
        ),
        section(
            "Tool Fluency Randall Should Build",
            [
                "You need practical fluency, not mastery. The first Sprint can be delivered as diagnosis and planning while we learn the implementation tooling.",
            ],
            [
                "Forms: Google Forms, Typeform, Tally, website forms, CRM intake forms.",
                "Automation: Zapier for common simple automations, Make for visual workflows, n8n for self-hostable and more technical flows.",
                "Communication: email, SMS providers, voicemail/call tracking, owner notification paths.",
                "CRM basics: lead record, contact fields, status, owner, next action, notes, tags.",
                "Workflow mapping: trigger, input, decision, action, owner, output, exception, audit trail.",
                "Data boundary: what we can see, what we should not see, what must be fictionalized.",
            ],
        ),
        section(
            "Operator Preparation Checklist",
            [
                "Before the first paid pilot, Randall should be able to run the conversation, explain the offer, and know where the system stops.",
            ],
            [
                "Pick one niche: recommended first choice is HVAC or plumbing.",
                "Prepare a one-page offer with conservative language.",
                "Prepare a 20-minute discovery script.",
                "Prepare the synthetic missed-lead demo and explain that it uses fictional data.",
                "Prepare a sample final report so the buyer knows what they receive.",
                "Prepare a clear no-credential and no-production-change boundary.",
                "Prepare a simple price and a simple yes/no private pilot decision.",
            ],
        ),
        section(
            "Private Pilot Readiness Gate",
            [
                "Right now, QA says we are not private-pilot-prep-ready. That is useful. It tells us exactly what must be repaired before outreach or payment collection.",
            ],
            [
                "Replace weak, mirrored, or snippet-only evidence with stronger sources.",
                "Add one public source for the chosen niche on urgency, call dependence, or lead friction.",
                "Draft the one-page offer.",
                "Draft the intake script.",
                "Run QA Red-Team on both before customer-facing use.",
                "Get explicit approval before outreach, customer data, payment, channel setup, or account creation.",
            ],
        ),
        section(
            "What The Final Deliverable Should Contain",
            [
                "The paid Sprint should end with a useful document that a business owner can act on even if they never hire us for implementation.",
            ],
            [
                "Current workflow map.",
                "Failure-point list.",
                "Lead response and handoff risk register.",
                "Automation opportunity map.",
                "Tool-stack recommendation with caveats.",
                "Implementation backlog ranked by effort and value.",
                "Synthetic demo or mock flow.",
                "Boundaries, assumptions, and next-step recommendation.",
            ],
        ),
        section(
            "Internal Prompt Pack",
            [
                "These are working prompts for Veritas-mediated agent use. They are internal only.",
            ],
            [
                "Research Scout: Find 10 public HVAC workflow automation, missed-call, or service-intake sources. Return URL, date, claim, source quality, and what can safely be used in offer language.",
                "Research Scout: Find 8 competitor offers that sell AI workflow audit, automation audit, or lead-response improvement to local businesses. Return price, buyer, promise, deliverables, and proof risk.",
                "QA Red-Team: Review the one-page AI Workflow Clarity Sprint offer. Flag unsupported claims, privacy gaps, delivery risk, scope creep, and owner-gated actions.",
                "QA Red-Team: Review the intake script. Make sure it diagnoses workflow pain without collecting sensitive customer data or implying guaranteed results.",
            ],
        ),
        section(
            "30-Day Preparation Plan",
            [
                "This is the practical path from internal readiness to a credible first paid pilot request.",
            ],
            [
                "Week 1: choose the niche, tighten evidence, build the one-page offer, and QA it.",
                "Week 2: build the intake script, sample final report, and demo walkthrough.",
                "Week 3: practice the discovery call, price framing, and objection handling with synthetic examples.",
                "Week 4: prepare the private pilot approval card for Randall's decision on outreach, payment, and any external account actions.",
            ],
        ),
        section(
            "Stop Lines",
            [
                "These are hard boundaries, not preferences.",
            ],
            [
                "No external outreach until approved.",
                "No payment links or vendor setup until approved.",
                "No customer data, credentials, or production-system access until separately approved.",
                "No public/customer delivery claim until QA clears the exact asset.",
                "No legal, compliance, security, ROI, or guaranteed-performance claims.",
                "No channel binding, cron dispatch, runtime/config/auth mutation, finance/account action, or paper/live execution.",
            ],
        ),
        section(
            "Immediate Next Actions",
            [
                "The next build should convert this training into customer-adjacent assets, but only after the evidence gap is tightened.",
            ],
            [
                f"Pick one first niche: {first_niche}.",
                "Run a narrower Research Scout pass for that niche.",
                "Draft the one-page offer.",
                "Draft the discovery and intake script.",
                "Run QA Red-Team against both.",
                "Prepare a private pilot approval card for outreach and payment decisions.",
            ],
        ),
    ]


def markdown_doc(model: dict[str, Any]) -> str:
    first_niche = first_niche_text(model)
    lines: list[str] = [
        f"# {TITLE} - {DATE}",
        "",
        f"Generated: {model['generated_at_utc']}",
        "",
        "## Source And Trust",
        "",
        "This is an internal WF75 training packet. It packages the current AI Drop-Service OS plan, the Research Scout evidence state, and QA Red-Team readiness gate into a practical operator-training document.",
        "",
        "| Field | Value |",
        "| --- | --- |",
        *key_value_rows(
            [
                ("First offer", "AI Workflow Clarity Sprint"),
                ("Likely first niche", first_niche),
                ("Current state", "Internal-demo-ready, not customer-ready"),
                ("QA decision", str(model["qa_decision"])),
                ("Private pilot prep ready", str(model["private_pilot_ready"])),
                ("Pricing test", "$500-$750 beta, around $1,500 standard diagnostic, $2,500-$5,000 later implementation add-on"),
            ]
        ).splitlines(),
        "",
    ]
    for item in training_sections(model):
        lines.append(f"## {item['title']}")
        lines.append("")
        for paragraph in item["paragraphs"]:
            lines.append(paragraph)
            lines.append("")
        if item["bullets"]:
            lines.extend(f"- {bullet}" for bullet in item["bullets"])
            lines.append("")
    lines.extend(
        [
            "## Source Stack",
            "",
            "| Source | Path | Status |",
            "| --- | --- | --- |",
        ]
    )
    for name, info in model["sources"].items():
        lines.append(f"| {name} | `{info.get('path')}` | `{info.get('status', 'n/a')}` |")
    lines.extend(
        [
            "",
            "## Authority Boundary",
            "",
            "- Internal training only.",
            "- No outreach, customer delivery, payment setup, external channel binding, cron mutation, config/auth/runtime mutation, customer data, finance/account action, or execution authority was created by this packet.",
            "",
        ]
    )
    return "\n".join(lines)


def status_badge(text: str) -> str:
    lower = text.lower()
    class_name = "warn"
    if lower in {"ok", "ready", "complete", "created"}:
        class_name = "good"
    if "blocked" in lower or "false" in lower:
        class_name = "bad"
    return f"<span class='badge {class_name}'>{esc(text)}</span>"


def list_html(items: list[str]) -> str:
    return "<ul>" + "".join(f"<li>{esc(item)}</li>" for item in items) + "</ul>"


def build_html(model: dict[str, Any]) -> str:
    sections = training_sections(model)
    cards = [
        ("Current State", "Internal-demo-ready, not customer-ready", "warn"),
        ("First Offer", "AI Workflow Clarity Sprint", "good"),
        ("First Niche", first_niche_text(model), "good"),
        ("QA Decision", str(model["qa_decision"]), "warn"),
        ("Pilot Ready", str(model["private_pilot_ready"]), "bad"),
        ("Price Test", "$500-$750 beta", "neutral"),
    ]
    cards_html = "".join(
        f"<div class='metric {klass}'><div class='metric-label'>{esc(label)}</div><div class='metric-value'>{esc(value)}</div></div>"
        for label, value, klass in cards
    )
    section_html: list[str] = []
    for index, item in enumerate(sections, start=1):
        break_class = " page-break" if index in {1, 5, 9, 13, 17} else ""
        section_html.append(
            f"<section class='block{break_class}' id='{slug(item['title'])}'>"
            f"<div class='kicker'>Training module {index:02d}</div>"
            f"<h2>{esc(item['title'])}</h2>"
            + "".join(f"<p>{esc(paragraph)}</p>" for paragraph in item["paragraphs"])
            + list_html(item["bullets"])
            + "</section>"
        )
    source_rows = "".join(
        f"<tr><td>{esc(name)}</td><td><code>{esc(info.get('path'))}</code></td><td>{status_badge(str(info.get('status', 'n/a')))}</td></tr>"
        for name, info in model["sources"].items()
    )
    return f"""<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>{esc(TITLE)} - {DATE}</title>
<style>
  @page {{ size: Letter; margin: 0.48in; }}
  * {{ box-sizing: border-box; }}
  body {{ margin: 0; font-family: Arial, Helvetica, sans-serif; color: #152237; background: #fff; font-size: 10.2px; line-height: 1.36; }}
  .cover {{ min-height: 9.25in; display: flex; flex-direction: column; justify-content: space-between; page-break-after: always; }}
  .cover-top {{ border-bottom: 4px solid #163f66; padding-bottom: 16px; }}
  .eyebrow {{ color: #59708b; text-transform: uppercase; letter-spacing: .13em; font-weight: 700; font-size: 9px; }}
  h1 {{ margin: 8px 0 8px; color: #102a43; font-size: 35px; line-height: 1.02; }}
  h2 {{ margin: 4px 0 7px; color: #102a43; font-size: 18px; }}
  p {{ margin: 0 0 7px; }}
  ul {{ margin: 4px 0 8px 17px; padding: 0; }}
  li {{ margin: 3px 0; }}
  table {{ border-collapse: collapse; width: 100%; table-layout: fixed; margin: 7px 0 10px; }}
  th, td {{ border: 1px solid #d5dde8; padding: 7px; vertical-align: top; }}
  th {{ background: #102a43; color: white; text-align: left; }}
  code {{ font-family: Consolas, monospace; font-size: 8.4px; color: #15304d; }}
  .subtitle {{ color: #496077; font-size: 14px; max-width: 7.2in; }}
  .warning {{ background: #fff6db; border: 1px solid #d8a730; border-left: 5px solid #b7791f; padding: 10px; margin: 10px 0; }}
  .grid {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 9px; margin: 14px 0; }}
  .metric {{ border: 1px solid #d4deea; border-radius: 8px; padding: 9px; min-height: .7in; background: #f7fafc; }}
  .metric.good {{ background: #eef8f0; border-color: #9fd1aa; }}
  .metric.warn {{ background: #fff8e5; border-color: #e2c36f; }}
  .metric.bad {{ background: #fdecec; border-color: #e5a0a0; }}
  .metric-label {{ color: #5f7389; text-transform: uppercase; letter-spacing: .08em; font-size: 8px; font-weight: 700; }}
  .metric-value {{ color: #102a43; font-size: 15px; line-height: 1.12; font-weight: 700; margin-top: 4px; }}
  .block {{ break-inside: avoid; margin: 0 0 13px; padding-bottom: 10px; border-bottom: 1px solid #e2e8f0; }}
  .page-break {{ page-break-before: always; }}
  .kicker {{ color: #62748a; text-transform: uppercase; letter-spacing: .11em; font-weight: 700; font-size: 8px; }}
  .badge {{ display: inline-block; padding: 2px 7px; border-radius: 999px; font-size: 8px; font-weight: 700; background: #e8eef7; color: #244b73; }}
  .badge.good {{ background: #e5f5ea; color: #176238; }}
  .badge.warn {{ background: #fff0c2; color: #765200; }}
  .badge.bad {{ background: #fde8e8; color: #8f1d1d; }}
  .footer {{ margin-top: 12px; color: #69798b; border-top: 1px solid #e2e8f0; padding-top: 6px; font-size: 8px; }}
</style>
</head>
<body>
<section class="cover">
  <div class="cover-top">
    <div class="eyebrow">WF75 internal training packet</div>
    <h1>{esc(TITLE)}</h1>
    <div class="subtitle">How the first monetization plan works, what Randall needs to know, and what must be prepared before a private pilot.</div>
    <div class="warning"><strong>Truth status:</strong> This is internal training. WF75 is not customer-ready yet. QA still blocks private-pilot-prep readiness until stronger evidence, one-niche focus, one-page offer, and intake script are complete.</div>
    <div class="grid">{cards_html}</div>
  </div>
  <div>
    <h2>Executive Summary</h2>
    <p>The first monetization plan is a fixed-scope AI Workflow Clarity Sprint for a low-regulation local service business. The likely first target is HVAC or plumbing. The sale is not an AI system, not a guarantee, and not a public SaaS launch. The sale is clarity: map one painful workflow, identify failure points, show a safe synthetic demo, and produce an implementation-ready plan.</p>
    <p>Generated {esc(model['generated_at_utc'])}. Source status: board {esc(model['board_status'])}; Research Scout {esc(model['research_status'])}; QA {esc(model['qa_status'])}; QA decision {esc(model['qa_decision'])}.</p>
  </div>
</section>
{''.join(section_html)}
<section class="block page-break">
  <div class="kicker">Appendix</div>
  <h2>Source Stack And Authority Boundary</h2>
  <table><tr><th>Source</th><th>Path</th><th>Status</th></tr>{source_rows}</table>
  <p><strong>Boundary:</strong> Internal training only. No outreach, customer delivery, payment setup, external channel binding, cron mutation, config/auth/runtime mutation, customer data, finance/account action, paper/live execution, or owner approval was created by this packet.</p>
  <div class="footer">Generated by scripts/wf75_monetization_training_pdf.py from current WF75 workspace artifacts.</div>
</section>
</body>
</html>"""


def find_browser() -> str | None:
    for candidate in BROWSER_CANDIDATES:
        found = shutil.which(candidate) if not Path(candidate).is_absolute() else candidate
        if found and Path(found).exists():
            return str(found)
    return None


def render_pdf(html_path: Path, pdf_path: Path) -> dict[str, Any]:
    browser = find_browser()
    if not browser:
        return {"status": "unavailable", "reason": "No local Edge/Chrome/Chromium renderer found."}
    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    command = [
        browser,
        "--headless=new",
        "--disable-gpu",
        "--no-first-run",
        "--disable-extensions",
        f"--print-to-pdf={str(pdf_path.resolve())}",
        html_path.resolve().as_uri(),
    ]
    completed = subprocess.run(command, cwd=str(ROOT), text=True, capture_output=True, timeout=120)
    created = completed.returncode == 0 and pdf_path.exists() and pdf_path.stat().st_size > 0
    return {
        "status": "created" if created else "failed",
        "browser": browser,
        "returncode": completed.returncode,
        "stdout_tail": (completed.stdout or "")[-1000:],
        "stderr_tail": (completed.stderr or "")[-1000:],
        "path": rel(pdf_path) if created else None,
        "size_bytes": pdf_path.stat().st_size if pdf_path.exists() else 0,
        "sha256": sha256_file(pdf_path) if created else None,
    }


def validate_outputs(markdown: str, rendered_html: str, manifest: dict[str, Any], *, require_pdf: bool) -> dict[str, Any]:
    errors: list[str] = []
    required_phrases = [
        "AI Workflow Clarity Sprint",
        "HVAC",
        "plumbing",
        "Internal training only",
        "No outreach",
        "No customer data",
        "QA decision",
        "$500-$750",
        "$1,500",
        "$2,500-$5,000",
    ]
    combined = markdown + "\n" + rendered_html
    for phrase in required_phrases:
        if phrase not in combined:
            errors.append(f"missing_required_phrase:{phrase}")
    if "private-pilot-prep readiness" not in combined:
        errors.append("missing_private_pilot_readiness_boundary")
    if manifest.get("authority_boundary") != AUTHORITY_BOUNDARY:
        errors.append("authority_boundary_mismatch")
    for name, info in manifest.get("source_checks", {}).items():
        if not info.get("exists") or info.get("parseable") is False:
            errors.append(f"source_not_ready:{name}")
    outputs = manifest.get("outputs") or {}
    for label in ["markdown", "html"]:
        path = ROOT / str(outputs.get(label, ""))
        if not path.exists() or path.stat().st_size <= 0:
            errors.append(f"missing_output:{label}")
    pdf_contract = manifest.get("pdf_contract") or {}
    if require_pdf and pdf_contract.get("status") != "created":
        errors.append("pdf_not_created")
    if require_pdf and PDF_OUT.exists() and PDF_OUT.stat().st_size < 50_000:
        errors.append("pdf_too_small")
    return {"status": "ok" if not errors else "error", "errors": errors}


def update_team_board(model: dict[str, Any], manifest: dict[str, Any]) -> None:
    board = load_json(TEAM_BOARD)
    artifacts = board.setdefault("artifacts", {})
    artifacts["monetization_training_markdown"] = rel(MD_OUT)
    artifacts["monetization_training_html"] = rel(HTML_OUT)
    artifacts["monetization_training_pdf"] = rel(PDF_OUT)
    artifacts["monetization_training_manifest"] = rel(MANIFEST_OUT)
    artifacts["monetization_training_continuity"] = rel(CONTINUITY_OUT)
    board["generated_at_utc"] = model["generated_at_utc"]
    board["latest_monetization_training"] = {
        "generated_at_utc": model["generated_at_utc"],
        "status": manifest.get("status"),
        "first_offer": "AI Workflow Clarity Sprint",
        "first_niche": first_niche_text(model),
        "private_pilot_ready": model["private_pilot_ready"],
        "qa_decision": model["qa_decision"],
        "pdf": rel(PDF_OUT),
        "manifest": rel(MANIFEST_OUT),
    }
    atomic_write_json(TEAM_BOARD, board)


def continuity_note(model: dict[str, Any], manifest: dict[str, Any]) -> str:
    return "\n".join(
        [
            f"# Workflow 75 - AI Workflow Clarity Sprint Monetization Training - {DATE}",
            "",
            "## Bottom Line",
            "",
            "Created the internal PDF training packet for the first monetization plan: AI Workflow Clarity Sprint for one low-regulation local service niche, likely HVAC or plumbing first.",
            "",
            "This is training and preparation only. It does not approve outreach, payment setup, customer delivery, external channel binding, customer data, cron mutation, config/auth/runtime mutation, finance/account action, paper/live execution, or public launch.",
            "",
            "## Outputs",
            "",
            f"- Markdown: `{rel(MD_OUT)}`",
            f"- HTML: `{rel(HTML_OUT)}`",
            f"- PDF: `{rel(PDF_OUT)}`",
            f"- Manifest: `{rel(MANIFEST_OUT)}`",
            "",
            "## Training Coverage",
            "",
            "- Current internal-only readiness state.",
            "- What the Sprint sells and does not sell.",
            "- Why HVAC or plumbing is the recommended first niche path.",
            "- Randall's sales, consulting, workflow diagnosis, and tool-fluency preparation.",
            "- Veritas, Research Scout, and QA Red-Team operating cadence.",
            "- Five-day delivery model, discovery call framework, safe language, and stop lines.",
            "- Private-pilot readiness gate and 30-day preparation plan.",
            "",
            "## Validation",
            "",
            f"- Manifest status: `{manifest.get('status')}`",
            f"- PDF contract: `{(manifest.get('pdf_contract') or {}).get('status')}`",
            f"- QA decision carried forward: `{model['qa_decision']}`",
            f"- Private pilot prep ready: `{model['private_pilot_ready']}`",
            "",
        ]
    )


def build_manifest(args: argparse.Namespace, model: dict[str, Any]) -> dict[str, Any]:
    markdown = markdown_doc(model)
    rendered_html = build_html(model)
    if args.write:
        atomic_write_text(MD_OUT, markdown)
        atomic_write_text(HTML_OUT, rendered_html)
    pdf_contract = {
        "status": "not_requested",
        "path": None,
        "size_bytes": 0,
        "sha256": None,
    }
    if args.write and args.pdf:
        pdf_contract = render_pdf(HTML_OUT, PDF_OUT)
    manifest: dict[str, Any] = {
        "schema": "veritas.wf75.monetization_training_pdf.v1",
        "generated_at_utc": model["generated_at_utc"],
        "workflow": "WF75",
        "status": "pending",
        "title": TITLE,
        "outputs": {
            "markdown": rel(MD_OUT),
            "html": rel(HTML_OUT),
            "pdf": rel(PDF_OUT) if PDF_OUT.exists() else None,
            "manifest": rel(MANIFEST_OUT),
            "continuity": rel(CONTINUITY_OUT),
        },
        "source_checks": model["sources"],
        "pdf_contract": pdf_contract,
        "readiness": {
            "current_state": "internal_demo_ready_training_packet_created",
            "private_pilot_prep_ready": model["private_pilot_ready"],
            "qa_decision": model["qa_decision"],
            "first_offer": "AI Workflow Clarity Sprint",
            "first_niche": first_niche_text(model),
        },
        "authority_boundary": AUTHORITY_BOUNDARY,
    }
    if args.write:
        atomic_write_text(CONTINUITY_OUT, continuity_note(model, manifest))
    validation = validate_outputs(markdown, rendered_html, manifest, require_pdf=args.pdf)
    manifest["validation"] = validation
    manifest["status"] = "ok" if validation["status"] == "ok" else "error"
    if args.write:
        atomic_write_json(MANIFEST_OUT, manifest)
        update_team_board(model, manifest)
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true", help="Write Markdown, HTML, manifest, continuity, and board update.")
    parser.add_argument("--pdf", action="store_true", help="Render the PDF using local Edge/Chrome/Chromium.")
    parser.add_argument("--validate", action="store_true", help="Exit nonzero when validation fails.")
    args = parser.parse_args()

    model = build_model()
    manifest = build_manifest(args, model)
    print(json.dumps(manifest, indent=2))
    if args.validate and manifest.get("status") != "ok":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
