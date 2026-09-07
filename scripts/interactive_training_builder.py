#!/usr/bin/env python3
"""Build static interactive HTML training modules with local xAPI proof.

This is an internal training asset builder. It creates local files only:
HTML runtime, module JSON, xAPI seed statements, SCORM package scaffold,
standards evaluation notes, and validation proof. It does not host content,
send learner data externally, configure an LMS/LRS, collect customer data, or
grant outreach, finance, account, paper/live, or owner-approval authority.
"""
from __future__ import annotations

import argparse
import html
import json
import re
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape as xml_escape

from market_data_utils import atomic_write_json, atomic_write_text


ROOT = Path(__file__).resolve().parents[1]
TRAINING = ROOT / "training" / "interactive-training-builder"
SCHEMA = ROOT / "schemas" / "interactive_training_module.schema.json"
TMP_PROOF = ROOT / "tmp" / "interactive-training-builder-proof.json"
CONTRACT = ROOT / "08. Audits" / "Interactive Training Builder Implementation Contract - 2026-07-03.md"

MODULE_JSON = TRAINING / "sample-wf75-boundary-module.json"
MODULE_HTML = TRAINING / "sample-wf75-boundary-module.html"
MODULE_XAPI = TRAINING / "sample-wf75-boundary-module.xapi.json"
MODULE_MANIFEST = TRAINING / "sample-wf75-boundary-module-manifest.json"
MODULE_STANDARDS = TRAINING / "standards-upgrade-evaluation.json"
MODULE_STANDARDS_MD = TRAINING / "standards-upgrade-evaluation.md"
SCORM_DIR = TRAINING / "scorm-sample-wf75-boundary-module"
SCORM_MANIFEST = SCORM_DIR / "imsmanifest.xml"
SCORM_ZIP = TRAINING / "sample-wf75-boundary-module-scorm.zip"
HVAC_STACK = ROOT / "training" / "wf75-academy" / "hvac-prospect-outreach-training-stack-2026-07-03.json"
HVAC_MODULE_PREFIX = "wf75-hvac-outreach-module"
SEC_MODULE_PREFIX = "sec-evidence-review-module"
OTEL_MODULE_PREFIX = "otel-proof-validator-module"
OPENCLAW_DAY1_PREFIX = "openclaw-day1-gateway-module"
AUTHORING_CHECKLIST = TRAINING / "authoring-checklist.md"
COMPONENT_LIBRARY_JSON = TRAINING / "component-library.json"
COMPONENT_LIBRARY_MD = TRAINING / "component-library.md"

BLOCKED_AUTHORITY_FLAGS = [
    "external_delivery_approved",
    "customer_data_allowed",
    "credential_access_allowed",
    "owner_approval_inferred",
]

REQUIRED_XAPI_VERBS = {
    "started",
    "answered",
    "completed",
    "passed",
    "failed",
    "reviewed_boundary",
}

VIDEO_SRC_RE = re.compile(r"^recordings/[a-z0-9][a-z0-9._-]{1,80}\.(webm|mp4)$")
POSTER_SRC_RE = re.compile(r"^recordings/[a-z0-9][a-z0-9._-]{1,80}\.(png|jpg|svg)$")
WALKTHROUGH_SRC_RE = re.compile(r"^walkthroughs/[a-z0-9][a-z0-9._-]{1,80}\.html$")


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def is_safe_media_src(value: Any, kind: str) -> bool:
    if not isinstance(value, str) or not value:
        return False
    if "://" in value or ".." in value or "\\" in value:
        return False
    if value.startswith("/") or re.match(r"^[A-Za-z]:", value):
        return False
    if kind == "video":
        pattern = VIDEO_SRC_RE
    elif kind == "walkthrough":
        pattern = WALKTHROUGH_SRC_RE
    else:
        pattern = POSTER_SRC_RE
    return pattern.match(value) is not None


def screen_recording_warnings(module: dict[str, Any]) -> list[str]:
    warnings: list[str] = []
    for item in module.get("interactions", []):
        if item.get("type") != "screen_recording":
            continue
        walkthrough_src = item.get("walkthrough_src")
        if walkthrough_src and is_safe_media_src(walkthrough_src, "walkthrough"):
            if not (TRAINING / walkthrough_src).exists():
                warnings.append(f"screen_recording_walkthrough_missing:{item.get('id')}")
            continue
        video_src = item.get("video_src")
        if not video_src:
            warnings.append(f"screen_recording_placeholder_no_clip:{item.get('id')}")
        elif is_safe_media_src(video_src, "video"):
            clip_path = TRAINING / video_src
            if not clip_path.exists():
                warnings.append(f"screen_recording_clip_missing_placeholder:{item.get('id')}")
    return warnings


def rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def esc(value: Any) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def js_template(value: str) -> str:
    return value.replace("\\", "\\\\").replace("`", "\\`").replace("${", "\\${")


def pretty_json(data: Any) -> str:
    return json.dumps(data, indent=2, sort_keys=True) + "\n"


def clean_text(text: str) -> str:
    return "\n".join(line.rstrip() for line in text.splitlines()).strip() + "\n"


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "item"


def artifact_paths(prefix: str) -> dict[str, Path]:
    scorm_dir = TRAINING / f"scorm-{prefix}"
    return {
        "module_json": TRAINING / f"{prefix}.json",
        "module_html": TRAINING / f"{prefix}.html",
        "xapi_seed": TRAINING / f"{prefix}.xapi.json",
        "manifest": TRAINING / f"{prefix}-manifest.json",
        "scorm_dir": scorm_dir,
        "scorm_manifest": scorm_dir / "imsmanifest.xml",
        "scorm_zip": TRAINING / f"{prefix}-scorm.zip",
    }


def build_sample_module() -> dict[str, Any]:
    return {
        "schema": "veritas.interactive_training_module.v1",
        "module_id": "wf75-boundary-practice",
        "title": "WF75 Boundary Practice Lab",
        "audience": "Randall internal operator training",
        "summary": (
            "Hands-on practice for explaining a service-led AI workflow review "
            "without overpromising, collecting customer data, or implying outreach approval."
        ),
        "authority_boundary": {
            "internal_training_only": True,
            "external_delivery_approved": False,
            "customer_data_allowed": False,
            "credential_access_allowed": False,
            "owner_approval_inferred": False,
        },
        "learning_objectives": [
            "Explain the offer in plain English without hype.",
            "Identify unsafe claims before they reach a prospect.",
            "Separate internal training readiness from external outreach approval.",
            "Export local xAPI-style practice events for review without sending data externally.",
        ],
        "lessons": [
            {
                "id": "offer-scope",
                "title": "Offer Scope",
                "body": (
                    "The AI Workflow Clarity Sprint is a narrow diagnostic review of one workflow. "
                    "It creates a map and improvement checklist. It is not a live automation build, "
                    "not a revenue guarantee, and not a request for credentials or customer data."
                ),
                "key_points": [
                    "Lead with the workflow problem, not the tool.",
                    "Keep claims diagnostic and evidence-bound.",
                    "Never imply outreach approval from a training score.",
                ],
            },
            {
                "id": "boundary-discipline",
                "title": "Boundary Discipline",
                "body": (
                    "Training artifacts help Randall rehearse. They do not approve contact, public launch, "
                    "CRM import, phone/SMS outreach, payment collection, customer-data intake, or production access."
                ),
                "key_points": [
                    "Owner approval must name batch, channel, and copy.",
                    "Customer data and credentials stay blocked in first-scope training.",
                    "High scores mean readiness for review, not permission to act.",
                ],
            },
        ],
        "interactions": [
            {
                "id": "plain-english-offer",
                "type": "scenario",
                "title": "Explain The Offer",
                "prompt": "A business owner asks what Randall is offering. Write the 30-second version.",
                "expected": (
                    "A five-day review of one intake or callback workflow that returns a practical "
                    "map and improvement checklist, without production access, customer data, or revenue promises."
                ),
                "rubric": [
                    "Names one workflow.",
                    "Says diagnostic review or map/checklist.",
                    "Avoids revenue and automation guarantees.",
                    "Avoids requesting credentials or customer data.",
                ],
                "xapi_object": "activity/plain-english-offer",
            },
            {
                "id": "unsafe-claim-check",
                "type": "multiple_choice",
                "title": "Spot The Unsafe Claim",
                "prompt": "Which sentence should be blocked before it reaches a prospect?",
                "choices": [
                    {
                        "id": "safe",
                        "text": "I noticed your site emphasizes fast service, so intake and callback handoffs may be worth reviewing.",
                        "correct": False,
                        "feedback": "This is framed as a possible review angle from public evidence.",
                    },
                    {
                        "id": "unsafe",
                        "text": "Your company is losing calls and our AI can recover that revenue.",
                        "correct": True,
                        "feedback": "Correct. This asserts loss, promises AI recovery, and implies revenue lift.",
                    },
                    {
                        "id": "neutral",
                        "text": "The first step would be a narrow workflow map, not a system change.",
                        "correct": False,
                        "feedback": "This is a safe scope statement.",
                    },
                ],
                "xapi_object": "activity/unsafe-claim-check",
            },
            {
                "id": "approval-minimums",
                "type": "checklist",
                "title": "Approval Card Minimums",
                "prompt": "Check every field required before any first-batch outreach can be treated as approved.",
                "checklist_items": [
                    "Named prospect batch",
                    "Approved channel",
                    "Approved copy",
                    "Explicit not-approved list",
                    "Owner approval is current and exact",
                ],
                "xapi_object": "activity/approval-minimums",
            },
            {
                "id": "boundary-review",
                "type": "boundary_ack",
                "title": "Boundary Review",
                "prompt": (
                    "Confirm that this training lab is internal only and does not approve outreach, "
                    "customer data collection, CRM import, payment collection, credentials, or production access."
                ),
                "expected": "I confirm this is internal readiness training only.",
                "xapi_object": "activity/boundary-review",
            },
            {
                "id": "reflection-next-step",
                "type": "reflection",
                "title": "Operator Reflection",
                "prompt": "What should Randall do after passing this module, and what remains blocked?",
                "rubric": [
                    "Names review or approval-card prep as next step.",
                    "States outreach remains owner-gated.",
                    "Keeps customer data, credentials, and production access blocked.",
                ],
                "xapi_object": "activity/reflection-next-step",
            },
            {
                "id": "boundary-walkthrough-clip",
                "type": "screen_recording",
                "title": "Boundary Walkthrough Clip",
                "prompt": "Watch the short local screen recording that walks through the approval-card minimums, then mark the clip reviewed.",
                "capture_hint": (
                    "No clip recorded yet. Capture one with Windows Snipping Tool screen recording "
                    "(Win+Shift+R), save the file under training/interactive-training-builder/recordings/ "
                    "as a .webm or .mp4, then rerun the builder so the player picks it up."
                ),
                "caption": "Walkthrough of the approval-card minimums inside the local training runtime.",
                "xapi_object": "activity/boundary-walkthrough-clip",
            },
        ],
        "xapi": {
            "activity_id": "https://veritas.local/training/wf75-boundary-practice",
            "verbs": sorted(REQUIRED_XAPI_VERBS),
        },
    }


def build_hvac_module() -> dict[str, Any]:
    if not HVAC_STACK.exists():
        raise FileNotFoundError(f"HVAC training stack missing: {HVAC_STACK}")
    stack = json.loads(HVAC_STACK.read_text(encoding="utf-8"))
    offer = stack["offer"]
    authority = stack["authority_boundary"]
    prospects = stack.get("first_batch", [])
    simulations = stack.get("simulations", [])
    prospect_names = ", ".join(row["business_name"] for row in prospects[:5])
    lessons = [
        {
            "id": "offer-scope",
            "title": "Offer Scope",
            "body": offer["plain_english"],
            "key_points": [
                f"Included: {', '.join(offer['included'][:3])}.",
                f"Not included: {', '.join(offer['not_included'][:4])}.",
                "Keep this diagnostic and fixed-scope; do not imply implementation or revenue lift.",
            ],
        },
        {
            "id": "first-batch-boundary",
            "title": "First Batch Boundary",
            "body": (
                "The current HVAC packet prepares an internal first-batch approval card. It does not approve sending, "
                "calling, texting, CRM import, payment collection, customer data, credentials, production access, or bulk automation."
            ),
            "key_points": [
                f"First batch practice names: {prospect_names}.",
                "Real outreach still requires Randall's exact approval of batch, channel, and copy.",
                "Phone/SMS and automation remain separately blocked.",
            ],
        },
        {
            "id": "safe-copy",
            "title": "Safe Copy Discipline",
            "body": stack["safe_copy"]["initial"],
            "key_points": [
                "Frame fit from public website signals only.",
                "Avoid accusations such as lost leads or broken workflows.",
                "Never ask for recordings, CRM access, customer data, or payment in first-scope training.",
            ],
        },
    ]
    interactions = [
        {
            "id": "boundary-confirmation",
            "type": "boundary_ack",
            "title": "Boundary Confirmation",
            "prompt": (
                "Confirm this module is internal readiness training only and does not approve outreach, "
                "customer data, CRM import, phone/SMS, payment, credentials, production access, or public delivery."
            ),
            "expected": "I confirm this is internal readiness training only.",
            "xapi_object": "activity/boundary-confirmation",
        },
        {
            "id": "unsafe-pattern-check",
            "type": "multiple_choice",
            "title": "Unsafe Pattern Check",
            "prompt": "Which phrase must be blocked before outreach?",
            "choices": [
                {
                    "id": "safe-fit",
                    "text": "Possible fit for a workflow review because the public site emphasizes response speed.",
                    "correct": False,
                    "feedback": "This is cautious and source-bound.",
                },
                {
                    "id": "unsafe-revenue",
                    "text": "Your HVAC company is probably losing calls and revenue.",
                    "correct": True,
                    "feedback": "Correct. That is an accusation and revenue claim.",
                },
                {
                    "id": "safe-scope",
                    "text": "The first Sprint is a diagnostic review, not a software install.",
                    "correct": False,
                    "feedback": "This is a safe scope boundary.",
                },
            ],
            "xapi_object": "activity/unsafe-pattern-check",
        },
        {
            "id": "approval-fields",
            "type": "checklist",
            "title": "Approval Card Fields",
            "prompt": "Check every field required before first-batch outreach can be treated as approved.",
            "checklist_items": [
                "Named prospect batch",
                "Approved channel",
                "Approved copy",
                "Explicit not-approved list",
                "Current exact owner approval",
            ],
            "xapi_object": "activity/approval-fields",
        },
    ]
    for simulation in simulations:
        interactions.append(
            {
                "id": slugify(simulation["id"]),
                "type": "scenario",
                "title": simulation["title"],
                "prompt": f"{simulation['scenario']}\n\nTask: {simulation['task']}",
                "expected": simulation["expected"],
                "rubric": [
                    f"Difficulty: {simulation['difficulty']}",
                    f"Category: {simulation['category']}",
                    "Avoid fail triggers: " + "; ".join(simulation.get("fail_triggers", [])),
                ],
                "xapi_object": f"activity/{slugify(simulation['id'])}",
            }
        )
    return {
        "schema": "veritas.interactive_training_module.v1",
        "module_id": "wf75-hvac-prospect-outreach-practice",
        "title": "WF75 HVAC Prospect Outreach Practice Lab",
        "audience": "Randall internal operator training",
        "summary": (
            "Practice module converted from the HVAC prospect outreach training stack. It trains offer clarity, "
            "claim discipline, data boundaries, channel boundaries, and exact owner-approval separation."
        ),
        "authority_boundary": {
            "internal_training_only": True,
            "external_delivery_approved": False,
            "customer_data_allowed": False,
            "credential_access_allowed": False,
            "owner_approval_inferred": False,
            "customer_outreach_approved": authority.get("customer_outreach_approved", False),
            "payment_collection_approved": authority.get("payment_collection_approved", False),
            "crm_import_approved": authority.get("crm_import_approved", False),
            "phone_sms_approved": authority.get("phone_sms_approved", False),
            "bulk_automation_approved": authority.get("bulk_automation_approved", False),
        },
        "learning_objectives": [
            "Explain the AI Workflow Clarity Sprint without hype or revenue promises.",
            "Repair unsafe HVAC outreach copy before it becomes external action.",
            "Handle data, channel, and objection scenarios without widening authority.",
            "Build a minimum approval card while preserving the not-approved list.",
        ],
        "lessons": lessons,
        "interactions": interactions,
        "xapi": {
            "activity_id": "https://veritas.local/training/wf75-hvac-prospect-outreach-practice",
            "verbs": sorted(REQUIRED_XAPI_VERBS),
        },
        "source_stack": rel(HVAC_STACK),
    }


def build_sec_evidence_module() -> dict[str, Any]:
    return {
        "schema": "veritas.interactive_training_module.v1",
        "module_id": "sec-evidence-review-practice",
        "title": "SEC Evidence Review Practice Lab",
        "audience": "Randall internal finance research operator training",
        "summary": (
            "Practice module for reviewing SEC/EDGAR evidence packets without treating filings, "
            "tool output, or training completion as portfolio, canon, trade, account, or capital authority."
        ),
        "authority_boundary": {
            "internal_training_only": True,
            "external_delivery_approved": False,
            "customer_data_allowed": False,
            "credential_access_allowed": False,
            "owner_approval_inferred": False,
            "live_sec_retrieval_approved": False,
            "venv_rebuild_approved": False,
            "portfolio_canon_mutation_approved": False,
            "trade_account_action_approved": False,
            "capital_deployment_approved": False,
        },
        "learning_objectives": [
            "Classify SEC filings by evidence use without overstating decision authority.",
            "Check SEC environment readiness before any evidence packet run.",
            "Separate official-source evidence from portfolio/canon mutation or trade approval.",
            "Identify freshness, source, and User-Agent failures that block evidence use.",
        ],
        "lessons": [
            {
                "id": "sec-evidence-role",
                "title": "What SEC Evidence Can And Cannot Do",
                "body": (
                    "SEC filings are official-source evidence for research. They can support a later "
                    "finance review, but they do not approve portfolio-note edits, capital deployment, "
                    "paper/live orders, account action, or owner approval."
                ),
                "key_points": [
                    "10-K and 10-Q filings support fundamentals and risk review.",
                    "8-K filings support event freshness and material updates.",
                    "DEF 14A, 13D/13G, and insider filings support governance and ownership review.",
                    "Evidence packets are inputs to judgment, not execution authority.",
                ],
            },
            {
                "id": "sec-environment-gate",
                "title": "Environment Gate",
                "body": (
                    "Before relying on SEC evidence tooling, run the local environment audit. It proves "
                    "the SEC venv exists, imports work, expected methods are exposed, the User-Agent is real, "
                    "and the docs preserve the review-only boundary."
                ),
                "key_points": [
                    "Use `python scripts\\sec_env_audit_validator.py --write --validate` before packet generation.",
                    "The expected User-Agent is `Veritas OpenClaw Research veritasaiflows@gmail.com`.",
                    "A clean audit still does not approve live retrieval, finance mutation, or account action.",
                ],
            },
            {
                "id": "review-lane-handoff",
                "title": "Review Lane Handoff",
                "body": (
                    "A clean SEC evidence packet should move into a review lane with source freshness, "
                    "filing type, conflict notes, and downstream authority flags. If evidence is stale, "
                    "missing, contradictory, or produced with a broken environment, stop and repair proof first."
                ),
                "key_points": [
                    "Name the ticker, filing type, filing date, source URL, and producer proof.",
                    "Mark stale or contradictory evidence as review debt, not as a recommendation.",
                    "Keep trade/account/capital and canon mutation flags false unless a separate gate applies.",
                ],
            },
        ],
        "interactions": [
            {
                "id": "filing-purpose-match",
                "type": "multiple_choice",
                "title": "Match Filing To Use",
                "prompt": "Which filing is the best first source for annual audited business, risk, and financial statement review?",
                "choices": [
                    {
                        "id": "ten-k",
                        "text": "10-K",
                        "correct": True,
                        "feedback": "Correct. The 10-K is the annual audited filing and a primary fundamentals/risk source.",
                    },
                    {
                        "id": "eight-k",
                        "text": "8-K",
                        "correct": False,
                        "feedback": "8-Ks are important for material events, but not the first annual fundamentals source.",
                    },
                    {
                        "id": "def-fourteen-a",
                        "text": "DEF 14A",
                        "correct": False,
                        "feedback": "Proxy statements are useful for governance, compensation, and voting matters.",
                    },
                ],
                "xapi_object": "activity/filing-purpose-match",
            },
            {
                "id": "environment-preflight",
                "type": "checklist",
                "title": "SEC Evidence Preflight",
                "prompt": "Check each item that must be true before treating a local SEC packet as usable review evidence.",
                "checklist_items": [
                    "SEC venv exists and imports cleanly",
                    "Expected SEC methods are exposed",
                    "User-Agent is real and not a placeholder",
                    "Packet includes filing date and source lineage",
                    "Authority flags remain review-only",
                ],
                "xapi_object": "activity/environment-preflight",
            },
            {
                "id": "authority-boundary-check",
                "type": "multiple_choice",
                "title": "Authority Boundary Check",
                "prompt": "A packet finds a fresh 10-Q and clean company facts. What does that approve?",
                "choices": [
                    {
                        "id": "research-only",
                        "text": "Review-only research evidence for a later finance judgment.",
                        "correct": True,
                        "feedback": "Correct. Evidence supports judgment but does not approve mutation or execution.",
                    },
                    {
                        "id": "portfolio-edit",
                        "text": "Immediate portfolio/canon edits because the source is official.",
                        "correct": False,
                        "feedback": "Official source quality does not bypass the separate gated apply path.",
                    },
                    {
                        "id": "trade-order",
                        "text": "A paper or live trade because SEC data is fresh.",
                        "correct": False,
                        "feedback": "Fresh evidence never creates paper/live/account authority.",
                    },
                ],
                "xapi_object": "activity/authority-boundary-check",
            },
            {
                "id": "stale-evidence-scenario",
                "type": "scenario",
                "title": "Stale Evidence Scenario",
                "prompt": (
                    "You open an SEC packet and see the latest 10-Q field is missing while the summary still "
                    "claims the evidence is ready. Write the safe operator response."
                ),
                "expected": (
                    "Mark the packet as blocked or warning-grade, identify the missing 10-Q evidence, rerun or repair "
                    "the SEC proof path, and do not use it for a material recommendation until source freshness is clean."
                ),
                "rubric": [
                    "Names the missing or stale evidence.",
                    "Blocks or downgrades the packet instead of smoothing it over.",
                    "Calls for rerun/repair proof before material use.",
                    "Does not infer finance, canon, or execution authority.",
                ],
                "xapi_object": "activity/stale-evidence-scenario",
            },
            {
                "id": "conflict-review-scenario",
                "type": "scenario",
                "title": "Conflict Review Scenario",
                "prompt": (
                    "A generated summary says revenue accelerated, but the 10-Q source line shows a decline. "
                    "What should the review note say?"
                ),
                "expected": (
                    "Treat the official filing/source line as the evidence anchor, flag the generated summary conflict, "
                    "and route the item for review or repair before it influences a recommendation."
                ),
                "rubric": [
                    "Uses official filing/source line as anchor.",
                    "Flags generated-summary conflict explicitly.",
                    "Routes repair or review before recommendation use.",
                    "Avoids hiding uncertainty.",
                ],
                "xapi_object": "activity/conflict-review-scenario",
            },
            {
                "id": "user-agent-check",
                "type": "multiple_choice",
                "title": "User-Agent Gate",
                "prompt": "Which User-Agent state is acceptable before SEC evidence retrieval is considered?",
                "choices": [
                    {
                        "id": "real-contact",
                        "text": "Veritas OpenClaw Research veritasaiflows@gmail.com",
                        "correct": True,
                        "feedback": "Correct. The workspace expects a real research identity and contact.",
                    },
                    {
                        "id": "placeholder",
                        "text": "my-app",
                        "correct": False,
                        "feedback": "Placeholder identity is not acceptable for SEC retrieval.",
                    },
                    {
                        "id": "blank",
                        "text": "Blank or omitted User-Agent",
                        "correct": False,
                        "feedback": "Blank identity fails the SEC environment gate.",
                    },
                ],
                "xapi_object": "activity/user-agent-check",
            },
            {
                "id": "boundary-ack",
                "type": "boundary_ack",
                "title": "SEC Boundary Acknowledgement",
                "prompt": (
                    "Confirm this module is internal SEC evidence review training only and does not approve "
                    "live SEC retrieval, venv rebuild, portfolio/canon mutation, capital deployment, paper/live orders, "
                    "account action, or owner approval."
                ),
                "expected": "I confirm this is internal SEC evidence review training only.",
                "xapi_object": "activity/boundary-ack",
            },
            {
                "id": "handoff-checklist",
                "type": "checklist",
                "title": "Review Handoff Checklist",
                "prompt": "Check every field that belongs in a clean SEC evidence handoff.",
                "checklist_items": [
                    "Ticker or entity identifier",
                    "Filing type and filing date",
                    "Source URL or accession pointer",
                    "Producer script/proof path",
                    "Freshness/conflict status",
                    "Review-only authority flags",
                ],
                "xapi_object": "activity/handoff-checklist",
            },
            {
                "id": "operator-reflection",
                "type": "reflection",
                "title": "Operator Reflection",
                "prompt": "After passing this module, what is the next safe use of SEC evidence and what remains blocked?",
                "rubric": [
                    "Names review packet or finance research support as safe use.",
                    "States live retrieval requires its own approved run path.",
                    "Keeps portfolio/canon mutation and paper/live/account action blocked.",
                    "Mentions freshness/conflict proof before material recommendations.",
                ],
                "xapi_object": "activity/operator-reflection",
            },
        ],
        "xapi": {
            "activity_id": "https://veritas.local/training/sec-evidence-review-practice",
            "verbs": sorted(REQUIRED_XAPI_VERBS),
        },
    }


def build_otel_proof_validator_module() -> dict[str, Any]:
    return {
        "schema": "veritas.interactive_training_module.v1",
        "module_id": "otel-proof-validator-practice",
        "title": "OTEL Proof Validator Practice Lab",
        "audience": "Randall internal operations proof and validator training",
        "summary": (
            "Practice module for reading local OTEL control packets, selecting the right proof window, "
            "and routing telemetry findings without changing collector, runtime, cron, external export, "
            "finance, paper, live, or account authority."
        ),
        "authority_boundary": {
            "internal_training_only": True,
            "external_delivery_approved": False,
            "customer_data_allowed": False,
            "credential_access_allowed": False,
            "owner_approval_inferred": False,
            "collector_config_mutation_approved": False,
            "runtime_config_mutation_approved": False,
            "cron_schedule_mutation_approved": False,
            "telemetry_capture_depth_expansion_approved": False,
            "external_telemetry_export_approved": False,
            "raw_prompt_tool_payload_capture_approved": False,
            "finance_canon_portfolio_mutation_approved": False,
            "paper_live_account_action_approved": False,
        },
        "learning_objectives": [
            "Run and interpret the local OTEL ops control proof path.",
            "Choose the smallest honest OTEL window for the operating question.",
            "Classify OTEL findings as healthy, monitor, repair, or owner-gated.",
            "Preserve privacy and authority boundaries while using telemetry evidence.",
        ],
        "lessons": [
            {
                "id": "otel-first-hop",
                "title": "First-Hop OTEL Proof Surface",
                "body": (
                    "The canonical OTEL operating proof is the local control packet. Use "
                    "`python scripts\\otel_ops_control.py --write --write-db --multi-window --validate` "
                    "before broad log reading. The packet writes local JSON, JSONL, and SQLite proof only."
                ),
                "key_points": [
                    "Read `tmp\\otel-ops-control.json` for collector health, validation, drift, and actions.",
                    "Read `tmp\\otel-ops-window-summary.json` for 1h, 6h, 24h, 7d, and 30d windows.",
                    "Use `tmp\\otel-tool-workflow-metadata.json` only when tool/workflow attribution matters.",
                    "A clean OTEL packet proves operating telemetry health, not model quality or finance correctness.",
                ],
            },
            {
                "id": "otel-window-selection",
                "title": "Window Selection",
                "body": (
                    "Use the smallest window that answers the question. A 1h window is for post-change checks, "
                    "6h is same-session review, 24h is the daily control packet, 7d is recurring friction, "
                    "and 30d is a baseline only."
                ),
                "key_points": [
                    "Do not use a long window to hide a current collector failure.",
                    "Do not use a short window as proof of long-run stability.",
                    "Warning/error counts and drift status are repair signals, not approval signals.",
                ],
            },
            {
                "id": "otel-boundaries",
                "title": "Telemetry Boundaries",
                "body": (
                    "OTEL review is local and metadata-bounded. It can route repairs and trend reviews, "
                    "but it does not approve collector config edits, runtime config edits, cron schedule edits, "
                    "external export, raw prompt or tool-payload capture, finance mutation, or paper/live action."
                ),
                "key_points": [
                    "Collector down, warning/error rows, failed validation, or SQLite integrity failure route to repair.",
                    "Capture-depth expansion is owner-gated and requires a separate proposal, diff, rollback, and privacy scan.",
                    "OTEL event volume is operational evidence only; it is not coding-skill, model-ranking, or trade-readiness proof.",
                ],
            },
        ],
        "interactions": [
            {
                "id": "canonical-command-check",
                "type": "multiple_choice",
                "title": "Canonical Proof Command",
                "prompt": "Which command is the correct first-hop OTEL proof route for a local operating review?",
                "choices": [
                    {
                        "id": "ops-control",
                        "text": "python scripts\\otel_ops_control.py --write --write-db --multi-window --validate",
                        "correct": True,
                        "feedback": "Correct. This refreshes the control packet, SQLite index, and multi-window summary.",
                    },
                    {
                        "id": "raw-log-first",
                        "text": "Open raw collector logs first and summarize by hand.",
                        "correct": False,
                        "feedback": "Raw logs are drilldown. The control packet is the first-hop proof surface.",
                    },
                    {
                        "id": "change-config",
                        "text": "Edit collector verbosity before checking the packet.",
                        "correct": False,
                        "feedback": "Config mutation is owner-gated and not a first-hop proof action.",
                    },
                ],
                "xapi_object": "activity/canonical-command-check",
            },
            {
                "id": "packet-field-checklist",
                "type": "checklist",
                "title": "Packet Fields To Read",
                "prompt": "Check every field family that belongs in an OTEL proof interpretation.",
                "checklist_items": [
                    "Collector health and loopback endpoint",
                    "Validation errors and warnings",
                    "Metric batches, trace batches, data points, and spans",
                    "Warning/error counts",
                    "Drift status and drift reasons",
                    "SQLite integrity when the DB is written",
                    "Authority boundary flags",
                ],
                "xapi_object": "activity/packet-field-checklist",
            },
            {
                "id": "window-choice-post-change",
                "type": "multiple_choice",
                "title": "Post-Change Window",
                "prompt": "After an implementation patch, which OTEL window should be checked first?",
                "choices": [
                    {
                        "id": "one-hour",
                        "text": "1h intraday window",
                        "correct": True,
                        "feedback": "Correct. The 1h window is the post-change or suspected-incident check.",
                    },
                    {
                        "id": "thirty-day",
                        "text": "30d baseline",
                        "correct": False,
                        "feedback": "The 30d view is too broad for post-change verification.",
                    },
                    {
                        "id": "skip-window",
                        "text": "Skip windows if the daily packet was green yesterday.",
                        "correct": False,
                        "feedback": "A prior green daily packet does not prove current post-change health.",
                    },
                ],
                "xapi_object": "activity/window-choice-post-change",
            },
            {
                "id": "collector-down-scenario",
                "type": "scenario",
                "title": "Collector Down Scenario",
                "prompt": (
                    "The OTEL packet reports `collector_health.status=blocked` and validation errors. "
                    "Write the safe operator response."
                ),
                "expected": (
                    "Classify OTEL as repair, state that the local collector appears down, preserve the boundary, "
                    "and route the next check through collector/runtime review without changing runtime or collector config."
                ),
                "rubric": [
                    "Names collector health as blocked.",
                    "Classifies the state as repair rather than healthy.",
                    "Does not start or reconfigure services without approval.",
                    "Names the follow-up proof path or owner-gated review.",
                ],
                "xapi_object": "activity/collector-down-scenario",
            },
            {
                "id": "telemetry-meaning-check",
                "type": "multiple_choice",
                "title": "What Clean OTEL Means",
                "prompt": "A 24h OTEL packet is validation-clean with zero warnings/errors. What does that prove?",
                "choices": [
                    {
                        "id": "ops-health",
                        "text": "Local telemetry collection and operating proof are healthy for that window.",
                        "correct": True,
                        "feedback": "Correct. It proves OTEL operating health, not the quality of every downstream decision.",
                    },
                    {
                        "id": "model-quality",
                        "text": "The model produced high-quality answers.",
                        "correct": False,
                        "feedback": "OTEL volume and validation are not model-quality proof.",
                    },
                    {
                        "id": "trade-ready",
                        "text": "Finance decisions are ready for execution.",
                        "correct": False,
                        "feedback": "OTEL never creates finance, account, paper, live, or capital authority.",
                    },
                ],
                "xapi_object": "activity/telemetry-meaning-check",
            },
            {
                "id": "warning-error-scenario",
                "type": "scenario",
                "title": "Warning/Error Scenario",
                "prompt": (
                    "The packet validates but the daily warning/error count is nonzero. "
                    "How should the closeout characterize OTEL?"
                ),
                "expected": (
                    "Call it warning-grade or repair depending on severity, list the warning/error count, "
                    "route operator review, and avoid claiming clean OTEL closeout until the issue is classified or fixed."
                ),
                "rubric": [
                    "States the warning/error count matters.",
                    "Avoids calling OTEL clean.",
                    "Routes operator review or repair.",
                    "Does not mutate collector or runtime config from the packet.",
                ],
                "xapi_object": "activity/warning-error-scenario",
            },
            {
                "id": "privacy-stop-lines",
                "type": "checklist",
                "title": "Telemetry Stop Lines",
                "prompt": "Check every action that remains blocked by OTEL training alone.",
                "checklist_items": [
                    "Collector config mutation",
                    "Runtime config mutation",
                    "Cron schedule mutation",
                    "External telemetry export",
                    "Raw prompt or tool-payload capture",
                    "Finance/canon/portfolio mutation",
                    "Paper/live/account action",
                ],
                "xapi_object": "activity/privacy-stop-lines",
            },
            {
                "id": "field-depth-decision",
                "type": "multiple_choice",
                "title": "Capture-Depth Decision",
                "prompt": "OTEL lacks a field you want for model-routing economics. What is the safe next step?",
                "choices": [
                    {
                        "id": "proposal-first",
                        "text": "Prepare a local metadata-depth proposal with scope, privacy scan, diff, rollback, and owner approval requirement.",
                        "correct": True,
                        "feedback": "Correct. Depth expansion needs a separate proposal and approval path.",
                    },
                    {
                        "id": "capture-now",
                        "text": "Enable broader capture immediately because the current packet is green.",
                        "correct": False,
                        "feedback": "Green collection health does not approve capture-depth expansion.",
                    },
                    {
                        "id": "external-export",
                        "text": "Send OTEL data to an external backend for easier dashboards.",
                        "correct": False,
                        "feedback": "External telemetry export remains owner-gated and outside this training slice.",
                    },
                ],
                "xapi_object": "activity/field-depth-decision",
            },
            {
                "id": "otel-boundary-ack",
                "type": "boundary_ack",
                "title": "OTEL Boundary Acknowledgement",
                "prompt": (
                    "Confirm this module is internal OTEL proof training only and does not approve collector config edits, "
                    "runtime config edits, cron schedule edits, external export, capture-depth expansion, finance mutation, "
                    "paper/live/account action, or owner approval."
                ),
                "expected": "I confirm this is internal OTEL proof training only.",
                "xapi_object": "activity/otel-boundary-ack",
            },
            {
                "id": "operator-reflection",
                "type": "reflection",
                "title": "Operator Reflection",
                "prompt": "After passing this module, what is the next safe use of OTEL proof and what remains blocked?",
                "rubric": [
                    "Names OTEL status/closeout/routing interpretation as safe use.",
                    "Mentions the correct control packet and window summary surfaces.",
                    "Keeps collector/runtime/cron/external export changes owner-gated.",
                    "States OTEL is not model-quality, finance-correctness, or execution authority.",
                ],
                "xapi_object": "activity/operator-reflection",
            },
        ],
        "xapi": {
            "activity_id": "https://veritas.local/training/otel-proof-validator-practice",
            "verbs": sorted(REQUIRED_XAPI_VERBS),
        },
        "source_surfaces": [
            "scripts/otel_ops_control.py",
            "tmp/otel-ops-control.json",
            "tmp/otel-ops-window-summary.json",
            "skills/otel-operations-analyst/SKILL.md",
        ],
    }


def build_openclaw_day1_module() -> dict[str, Any]:
    return {
        "schema": "veritas.interactive_training_module.v1",
        "module_id": "openclaw-day1-gateway-control-ui",
        "title": "OpenClaw Day 1: Gateway, Session, and Control UI",
        "audience": "Randall internal OpenClaw operator training",
        "summary": (
            "Fifteen-minute practice for naming Gateway, agent, session, and Control UI correctly, "
            "inspecting this WebChat without changing settings, and keeping updates/config owner-gated."
        ),
        "authority_boundary": {
            "internal_training_only": True,
            "external_delivery_approved": False,
            "customer_data_allowed": False,
            "credential_access_allowed": False,
            "owner_approval_inferred": False,
            "runtime_config_mutation_approved": False,
            "channel_expansion_approved": False,
            "gateway_update_approved": False,
            "pairing_or_allowlist_mutation_approved": False,
        },
        "learning_objectives": [
            "Name Gateway, agent, session, and Control UI without mixing them up.",
            "Describe the path from a WebChat message to an agent reply.",
            "Keep install/update, config, and channel changes owner-run and out of this lab.",
        ],
        "lessons": [
            {
                "id": "four-parts",
                "title": "Four Parts, One Box",
                "body": (
                    "OpenClaw is a local Gateway that owns chat surfaces. The Control UI is the browser app "
                    "the Gateway serves, usually on 127.0.0.1:18789. An agent is the model-plus-tools persona "
                    "(here, Veritas Main). A session is one conversation's memory and tool loop. This WebChat "
                    "is Control UI talking to the Gateway, which starts an agent run in this session."
                ),
                "key_points": [
                    "Gateway: long-lived daemon; one per host; owns channels and the WebSocket API.",
                    "Control UI: browser dashboard served by that Gateway, not a second product.",
                    "Agent: who answers. Session: which thread they are answering in.",
                    "A clean training score does not approve config, updates, or new channels.",
                ],
            },
            {
                "id": "inspect-only-day1",
                "title": "Day 1 Is Inspect-Only",
                "body": (
                    "Day 1 practice is look, name, and stop. You may open Control UI, read a session, and "
                    "run read-only status. You do not patch openclaw.json, pair a new channel, or run "
                    "openclaw update from this lab. Randall runs updates in a terminal or Control UI when "
                    "he chooses. Completing this module is not that approval."
                ),
                "key_points": [
                    "Live inspect: this chat, the session list, and `openclaw status` if needed.",
                    "Blocked here: config, auth, channels, pairing, plugins, runtime, and updates.",
                    "Message in, Gateway accepts a run, agent replies. That is the whole loop.",
                ],
            },
        ],
        "interactions": [
            {
                "id": "what-is-gateway",
                "type": "multiple_choice",
                "title": "What Is The Gateway?",
                "prompt": "Which statement is accurate?",
                "choices": [
                    {
                        "id": "daemon",
                        "text": "The Gateway is the local long-lived process that owns channels, WebChat, and the Control UI WebSocket.",
                        "correct": True,
                        "feedback": "Correct. One Gateway per host; Control UI and chats connect to it.",
                    },
                    {
                        "id": "model",
                        "text": "The Gateway is the LLM vendor, such as xAI or OpenAI.",
                        "correct": False,
                        "feedback": "Vendors supply models. The Gateway is the local OpenClaw daemon.",
                    },
                    {
                        "id": "session",
                        "text": "The Gateway is this single chat thread and its transcript.",
                        "correct": False,
                        "feedback": "That is a session. Many sessions can share one Gateway.",
                    },
                ],
                "xapi_object": "activity/what-is-gateway",
            },
            {
                "id": "who-runs-update",
                "type": "multiple_choice",
                "title": "Who Runs Updates?",
                "prompt": "This training lab finishes with a passing score. What is still true?",
                "choices": [
                    {
                        "id": "randall-update",
                        "text": "Randall still has to run `openclaw update` himself if he wants an update; the lab does not authorize it.",
                        "correct": True,
                        "feedback": "Correct. Updates and config stay owner-gated.",
                    },
                    {
                        "id": "agent-update",
                        "text": "The agent should now run npm install -g openclaw and restart the Gateway.",
                        "correct": False,
                        "feedback": "Agents must not install or restart the Gateway from training completion.",
                    },
                    {
                        "id": "auto-channel",
                        "text": "A passing score lets the agent pair Telegram or Discord next.",
                        "correct": False,
                        "feedback": "Channel pairing stays owner-gated and is not Day 1 work.",
                    },
                ],
                "xapi_object": "activity/who-runs-update",
            },
            {
                "id": "inspect-only-checklist",
                "type": "checklist",
                "title": "Day 1 Inspect-Only Minimums",
                "prompt": "Check every item that stays true for this lab.",
                "checklist_items": [
                    "I can name Gateway, Control UI, agent, and session.",
                    "This WebChat is Control UI talking to the local Gateway.",
                    "I will not change config, pairing, channels, or plugins from this lab.",
                    "I will not treat a training score as approval to update OpenClaw.",
                ],
                "xapi_object": "activity/inspect-only-checklist",
            },
            {
                "id": "control-ui-walkthrough-clip",
                "type": "screen_recording",
                "title": "Day 1 Teaching Walkthrough",
                "prompt": "Watch the local teaching walkthrough, then mark it reviewed. You do not record anything.",
                "walkthrough_src": "walkthroughs/openclaw-day1.html",
                "capture_hint": "Teaching walkthrough is embedded. You watch it; you do not record a clip.",
                "caption": "Watch-only map of Gateway, Control UI, agent, and session.",
                "xapi_object": "activity/control-ui-walkthrough-clip",
            },
            {
                "id": "day1-boundary-ack",
                "type": "boundary_ack",
                "title": "Day 1 Boundary Acknowledgement",
                "prompt": (
                    "Confirm this module is internal OpenClaw literacy only and does not approve Gateway "
                    "updates, config edits, channel pairing, allowlist changes, or runtime mutation."
                ),
                "expected": "I confirm this is internal OpenClaw Day 1 training only.",
                "xapi_object": "activity/day1-boundary-ack",
            },
        ],
        "xapi": {
            "activity_id": "https://veritas.local/training/openclaw-day1-gateway-control-ui",
            "verbs": sorted(REQUIRED_XAPI_VERBS),
        },
    }


def validate_module(module: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if module.get("schema") != "veritas.interactive_training_module.v1":
        errors.append("schema_mismatch")
    if not SCHEMA.exists():
        errors.append("schema_file_missing")
    boundary = module.get("authority_boundary", {})
    if boundary.get("internal_training_only") is not True:
        errors.append("internal_training_boundary_missing")
    for key in BLOCKED_AUTHORITY_FLAGS:
        if boundary.get(key) is not False:
            errors.append(f"blocked_authority_flag_not_false:{key}")
    lessons = module.get("lessons", [])
    interactions = module.get("interactions", [])
    if len(lessons) < 1:
        errors.append("lesson_count_below_1")
    if len(interactions) < 3:
        errors.append("interaction_count_below_3")
    interaction_ids = [item.get("id") for item in interactions]
    if len(interaction_ids) != len(set(interaction_ids)):
        errors.append("duplicate_interaction_ids")
    verbs = set(module.get("xapi", {}).get("verbs", []))
    missing_verbs = sorted(REQUIRED_XAPI_VERBS - verbs)
    for verb in missing_verbs:
        errors.append(f"xapi_verb_missing:{verb}")
    for item in interactions:
        item_type = item.get("type")
        if item_type == "multiple_choice":
            choices = item.get("choices", [])
            if not choices:
                errors.append(f"multiple_choice_missing_choices:{item.get('id')}")
            if not any(choice.get("correct") is True for choice in choices):
                errors.append(f"multiple_choice_missing_correct:{item.get('id')}")
        if item_type == "checklist" and not item.get("checklist_items"):
            errors.append(f"checklist_missing_items:{item.get('id')}")
        if item_type in {"scenario", "boundary_ack"} and not item.get("expected"):
            errors.append(f"expected_answer_missing:{item.get('id')}")
        if item_type == "screen_recording":
            hint = item.get("capture_hint")
            if not isinstance(hint, str) or len(hint.strip()) < 10:
                errors.append(f"screen_recording_capture_hint_missing:{item.get('id')}")
            for field, kind in (("video_src", "video"), ("poster_src", "poster"), ("walkthrough_src", "walkthrough")):
                value = item.get(field)
                if value is None:
                    continue
                if not isinstance(value, str) or "://" in value or ".." in value or "\\" in value:
                    errors.append(f"screen_recording_unsafe_src:{item.get('id')}:{field}")
                elif value.startswith("/") or re.match(r"^[A-Za-z]:", value):
                    errors.append(f"screen_recording_unsafe_src:{item.get('id')}:{field}")
                elif not is_safe_media_src(value, kind):
                    errors.append(f"screen_recording_invalid_src:{item.get('id')}:{field}")
    return errors


def render_lessons(module: dict[str, Any]) -> str:
    parts = []
    for lesson in module["lessons"]:
        points = "".join(f"<li>{esc(point)}</li>" for point in lesson["key_points"])
        parts.append(
            f"""
      <section class="lesson" id="lesson-{esc(lesson['id'])}">
        <h3>{esc(lesson['title'])}</h3>
        <p>{esc(lesson['body'])}</p>
        <ul>{points}</ul>
      </section>"""
        )
    return "\n".join(parts)


def render_html(module: dict[str, Any]) -> str:
    data = json.dumps(module, ensure_ascii=False)
    objective_items = js_template("".join(f"<li>{esc(item)}</li>" for item in module["learning_objectives"]))
    lesson_html = js_template(render_lessons(module))
    return clean_text(
        f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{esc(module['title'])}</title>
  <style>
    :root {{
      color-scheme: light dark;
      --ink: #15202b;
      --muted: #596574;
      --paper: #f7f8fa;
      --panel: #ffffff;
      --line: #d9dee7;
      --accent: #0f766e;
      --accent-2: #2457a6;
      --warn: #9a6700;
      --bad: #a53b3b;
      --good: #267047;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      background: var(--paper);
      color: var(--ink);
      font-family: Inter, Segoe UI, Arial, sans-serif;
      line-height: 1.5;
    }}
    .skip {{
      position: absolute;
      left: -999px;
      top: 8px;
      background: var(--ink);
      color: white;
      padding: 8px 10px;
      z-index: 10;
    }}
    .skip:focus {{ left: 8px; }}
    header {{
      background: linear-gradient(135deg, #101820 0%, #16324a 55%, #0f766e 130%);
      background-color: #101820;
      color: white;
      padding: 26px clamp(16px, 4vw, 46px);
      border-bottom: 4px solid var(--accent);
      display: grid;
      gap: 8px;
    }}
    .visual-rail {{
      height: 6px;
      border-radius: 999px;
      background: linear-gradient(90deg, var(--accent), var(--accent-2));
    }}
    header h1 {{
      margin: 0 0 6px;
      font-size: clamp(1.45rem, 3vw, 2.35rem);
      letter-spacing: 0;
    }}
    header p {{ margin: 0; max-width: 980px; color: #dbe4ee; }}
    main {{
      display: grid;
      grid-template-columns: minmax(230px, 300px) minmax(0, 1fr);
      min-height: calc(100vh - 112px);
    }}
    nav {{
      border-right: 1px solid var(--line);
      background: #eef2f7;
      padding: 18px;
    }}
    nav h2, .workspace h2 {{ font-size: 1rem; margin: 0 0 10px; }}
    .nav-button {{
      width: 100%;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 8px;
      margin: 6px 0;
      padding: 10px 11px;
      border: 1px solid var(--line);
      background: white;
      color: var(--ink);
      border-radius: 8px;
      text-align: left;
      cursor: pointer;
      min-height: 44px;
    }}
    .nav-button[aria-pressed="true"] {{
      border-color: var(--accent);
      box-shadow: inset 4px 0 0 var(--accent);
      font-weight: 700;
    }}
    .workspace {{ padding: clamp(16px, 4vw, 34px); }}
    .band {{
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 12px;
      margin-bottom: 18px;
    }}
    .metric {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 12px;
      min-height: 82px;
    }}
    .metric strong {{ display: block; font-size: 1.4rem; }}
    .lesson, .interaction, .review-panel {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-left: 6px solid var(--accent-2);
      border-radius: 12px;
      padding: clamp(14px, 3vw, 22px);
      margin-bottom: 16px;
    }}
    .lesson:nth-of-type(even) {{ border-left-color: var(--accent); }}
    :focus-visible {{
      outline: 3px solid var(--accent-2);
      outline-offset: 2px;
      border-radius: 6px;
    }}
    .media-card {{
      border-left-color: var(--accent);
    }}
    .media-card video {{
      width: 100%;
      max-height: 480px;
      border-radius: 14px;
      background: #000;
      border: 1px solid var(--line);
    }}
    .media-card figcaption {{
      color: var(--muted);
      font-size: 0.92rem;
      margin-top: 8px;
    }}
    .capture-card {{
      border: 1px dashed var(--accent-2);
      border-left: 6px solid var(--accent-2);
      border-radius: 12px;
      background: #f2f6fc;
      padding: 14px;
      margin: 12px 0;
    }}
    .capture-card ol {{
      margin: 8px 0 0;
      padding-left: 20px;
    }}
    .capture-card code {{
      background: #e4eaf4;
    }}
    @media (prefers-color-scheme: dark) {{
      :root {{
        --ink: #e8edf3;
        --muted: #aab6c4;
        --paper: #0e141b;
        --panel: #17202b;
        --line: #2c3a4a;
        --accent: #2dd4bf;
        --accent-2: #7aa7f0;
        --warn: #e0a63c;
        --bad: #e08a8a;
        --good: #5ec596;
      }}
      nav {{ background: #111a24; }}
      .nav-button {{ background: #1c2836; color: var(--ink); }}
      .choice, .check-row {{ background: #1c2836; }}
      .result {{ background: #16211c; }}
      .boundary {{ background: #2a2313; color: #f0dfb8; }}
      .capture-card {{ background: #14202f; }}
      .capture-card code, code {{ background: #243242; color: var(--ink); }}
      .progress {{ background: #2c3a4a; }}
      textarea, input {{ background: #101820; color: var(--ink); border-color: var(--line); }}
      button.secondary {{ background: #1c2836; color: var(--ink); }}
    }}
    .interaction h3 {{ margin-top: 0; }}
    .choice, .check-row {{
      display: flex;
      gap: 10px;
      align-items: flex-start;
      padding: 10px;
      border: 1px solid var(--line);
      border-radius: 8px;
      margin: 8px 0;
      background: #fbfcfe;
      min-height: 44px;
    }}
    textarea {{
      width: 100%;
      min-height: 112px;
      resize: vertical;
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 10px;
      font: inherit;
    }}
    .toolbar {{
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin-top: 14px;
    }}
    button.primary, button.secondary {{
      min-height: 42px;
      border-radius: 8px;
      border: 1px solid var(--line);
      padding: 9px 12px;
      font-weight: 700;
      cursor: pointer;
    }}
    button.primary {{ background: var(--accent); color: white; border-color: var(--accent); }}
    button.secondary {{ background: white; color: var(--ink); }}
    .result {{
      margin-top: 10px;
      padding: 10px;
      border-radius: 8px;
      border: 1px solid var(--line);
      background: #f7faf8;
    }}
    .result.good {{ border-color: var(--good); }}
    .result.bad {{ border-color: var(--bad); }}
    .boundary {{
      border-left: 5px solid var(--warn);
      background: #fff8e5;
      padding: 12px;
      border-radius: 8px;
      margin: 12px 0;
    }}
    .progress {{
      height: 12px;
      background: #dfe5ed;
      border-radius: 999px;
      overflow: hidden;
    }}
    .progress span {{ display: block; height: 100%; background: var(--accent-2); width: 0%; }}
    code {{ background: #eef2f7; padding: 2px 4px; border-radius: 4px; }}
    @media (max-width: 820px) {{
      main {{ grid-template-columns: 1fr; }}
      nav {{ border-right: 0; border-bottom: 1px solid var(--line); }}
      .band {{ grid-template-columns: 1fr; }}
    }}
  </style>
</head>
<body>
  <a class="skip" href="#workspace">Skip to training workspace</a>
  <header>
    <div class="visual-rail" aria-hidden="true"></div>
    <h1>{esc(module['title'])}</h1>
    <p>{esc(module['summary'])}</p>
  </header>
  <main>
    <nav aria-label="Training sections">
      <h2>Sections</h2>
      <button class="nav-button" type="button" data-view="briefing" aria-pressed="true">Briefing <span aria-hidden="true">&gt;</span></button>
      <button class="nav-button" type="button" data-view="practice" aria-pressed="false">Practice <span aria-hidden="true">&gt;</span></button>
      <button class="nav-button" type="button" data-view="review" aria-pressed="false">Review <span aria-hidden="true">&gt;</span></button>
      <button class="nav-button" type="button" data-view="events" aria-pressed="false">Events <span aria-hidden="true">&gt;</span></button>
    </nav>
    <section class="workspace" id="workspace" tabindex="-1">
      <div class="band" aria-label="Training status">
        <div class="metric"><strong id="scoreText">0%</strong><span>score</span></div>
        <div class="metric"><strong id="doneText">0/{len(module['interactions'])}</strong><span>completed</span></div>
        <div class="metric"><strong id="eventText">0</strong><span>xAPI events</span></div>
      </div>
      <div class="progress" id="progressShell" role="progressbar" aria-label="Completion progress" aria-valuemin="0" aria-valuemax="100" aria-valuenow="0"><span id="progressBar"></span></div>
      <div id="announce" aria-live="polite" class="result" hidden></div>
      <div id="view"></div>
    </section>
  </main>
  <script>
    const DATA = {data};
    const STORE_KEY = "veritas.training." + DATA.module_id;
    const LEDGER_ENABLED_KEY = "veritas.training.xapiLedger.enabled";
    const LEDGER_ENDPOINT_KEY = "veritas.training.xapiLedger.endpoint";
    const state = JSON.parse(localStorage.getItem(STORE_KEY) || '{{"answers":{{}},"events":[],"view":"briefing"}}');
    const scorm = {{ api: null, initialized: false, completed: false, lastError: "0" }};

    function findScormApi(win) {{
      let current = win;
      for (let depth = 0; depth < 8 && current; depth += 1) {{
        if (current.API && typeof current.API.LMSInitialize === "function") return current.API;
        if (current.parent && current.parent !== current) current = current.parent;
        else break;
      }}
      if (win.opener && win.opener.API && typeof win.opener.API.LMSInitialize === "function") return win.opener.API;
      return null;
    }}

    function scormInitialize() {{
      if (scorm.initialized) return true;
      scorm.api = findScormApi(window);
      if (!scorm.api) return false;
      try {{
        scorm.initialized = scorm.api.LMSInitialize("") === "true";
        if (scorm.initialized) {{
          scorm.api.LMSSetValue("cmi.core.lesson_status", "incomplete");
          scorm.api.LMSSetValue("cmi.core.score.min", "0");
          scorm.api.LMSSetValue("cmi.core.score.max", "100");
          scorm.api.LMSCommit("");
        }}
      }} catch (error) {{
        scorm.lastError = String(error);
        scorm.initialized = false;
      }}
      return scorm.initialized;
    }}

    function scormSetValue(key, value) {{
      if (scorm.completed) return false;
      if (!scormInitialize()) return false;
      try {{
        return scorm.api.LMSSetValue(key, String(value)) === "true";
      }} catch (error) {{
        scorm.lastError = String(error);
        return false;
      }}
    }}

    function scormCommit() {{
      if (scorm.completed) return false;
      if (!scorm.initialized || !scorm.api) return false;
      try {{
        return scorm.api.LMSCommit("") === "true";
      }} catch (error) {{
        scorm.lastError = String(error);
        return false;
      }}
    }}

    function scormSyncStatus(done, pct, rawScore) {{
      if (scorm.completed) {{
        return;
      }}
      const status = done >= DATA.interactions.length ? (rawScore >= 80 ? "passed" : "completed") : "incomplete";
      scormSetValue("cmi.core.lesson_status", status);
      scormSetValue("cmi.core.score.raw", rawScore);
      scormSetValue("cmi.core.lesson_location", state.view || "briefing");
      scormSetValue("cmi.suspend_data", JSON.stringify({{ answers: state.answers, event_count: state.events.length }}).slice(0, 3900));
      scormCommit();
    }}

    function scormFinish(passed, rawScore) {{
      if (scorm.completed) return;
      scormSetValue("cmi.core.lesson_status", passed ? "passed" : "completed");
      scormSetValue("cmi.core.score.raw", rawScore);
      scormSetValue("cmi.core.lesson_location", state.view || "review");
      scormSetValue("cmi.suspend_data", JSON.stringify({{ answers: state.answers, event_count: state.events.length }}).slice(0, 3900));
      scormCommit();
      if (scorm.initialized && scorm.api) {{
        try {{ scorm.api.LMSFinish(""); }} catch (error) {{ scorm.lastError = String(error); }}
      }}
      scorm.completed = true;
    }}

    function save() {{
      localStorage.setItem(STORE_KEY, JSON.stringify(state));
      updateStatus();
    }}

    function localLedgerEnabled() {{
      return localStorage.getItem(LEDGER_ENABLED_KEY) === "true";
    }}

    function localLedgerEndpoint() {{
      return localStorage.getItem(LEDGER_ENDPOINT_KEY) || "http://127.0.0.1:8766/xapi";
    }}

    function statement(verb, objectId, result) {{
      return {{
        id: crypto.randomUUID ? crypto.randomUUID() : String(Date.now()) + Math.random(),
        timestamp: new Date().toISOString(),
        actor: {{ name: "local learner", account: {{ homePage: "https://veritas.local", name: "local" }} }},
        verb: {{ id: "https://adlnet.gov/expapi/verbs/" + verb, display: {{ "en-US": verb }} }},
        object: {{ id: DATA.xapi.activity_id + "/" + objectId, definition: {{ name: {{ "en-US": objectId }} }} }},
        result: result || {{}},
        context: {{ platform: "Veritas local HTML training runtime", extensions: {{ "https://veritas.local/extensions/internal_training_only": true }} }}
      }};
    }}

    function record(verb, objectId, result) {{
      const entry = statement(verb, objectId, result);
      state.events.push(entry);
      save();
      if (localLedgerEnabled()) {{
        fetch(localLedgerEndpoint(), {{
          method: "POST",
          headers: {{ "Content-Type": "application/json" }},
          body: JSON.stringify(entry),
          keepalive: true
        }}).catch(() => {{
          state.ledger_warning = "local_xapi_ledger_unavailable";
          save();
        }});
      }}
    }}

    function setView(view) {{
      state.view = view;
      document.querySelectorAll(".nav-button").forEach(button => {{
        button.setAttribute("aria-pressed", button.dataset.view === view ? "true" : "false");
      }});
      render();
      save();
      document.getElementById("workspace").focus();
    }}

    function completedInteractions() {{
      return DATA.interactions.filter(item => state.answers[item.id] && state.answers[item.id].completed).length;
    }}

    function score() {{
      const graded = DATA.interactions.filter(item => ["multiple_choice", "checklist", "boundary_ack"].includes(item.type));
      if (!graded.length) return 0;
      const points = graded.filter(item => state.answers[item.id] && state.answers[item.id].passed).length;
      return Math.round((points / graded.length) * 100);
    }}

    function updateStatus() {{
      const done = completedInteractions();
      const pct = Math.round((done / DATA.interactions.length) * 100);
      const rawScore = score();
      document.getElementById("scoreText").textContent = rawScore + "%";
      document.getElementById("doneText").textContent = done + "/" + DATA.interactions.length;
      document.getElementById("eventText").textContent = state.events.length;
      document.getElementById("progressBar").style.width = pct + "%";
      document.getElementById("progressShell").setAttribute("aria-valuenow", String(pct));
      scormSyncStatus(done, pct, rawScore);
    }}

    function announce(text) {{
      const node = document.getElementById("announce");
      node.textContent = text;
      node.hidden = false;
    }}

    function briefingView() {{
      return `
        <section class="review-panel">
          <h2>Objectives</h2>
          <ul>{objective_items}</ul>
          <div class="boundary"><strong>Boundary:</strong> Internal training only. A clean score does not approve outreach, customer data, credentials, production access, or external delivery.</div>
        </section>
        {lesson_html}
        <div class="toolbar">
          <button class="primary" type="button" onclick="record('started', 'module', {{ completion: false }}); setView('practice')">Start practice</button>
        </div>`;
    }}

    function renderInteraction(item, index) {{
      const answer = state.answers[item.id] || {{}};
      if (item.type === "screen_recording") return renderScreenRecording(item, index);
      if (item.type === "multiple_choice") {{
        const choices = item.choices.map(choice => `
          <label class="choice">
            <input type="radio" name="${{item.id}}" value="${{choice.id}}" ${{answer.choice === choice.id ? "checked" : ""}}>
            <span>${{choice.text}}</span>
          </label>`).join("");
        return interactionShell(item, index, choices, `<button class="primary" type="button" onclick="gradeChoice('${{item.id}}')">Check answer</button>`);
      }}
      if (item.type === "checklist") {{
        const rows = item.checklist_items.map((text, idx) => `
          <label class="check-row">
            <input type="checkbox" data-check="${{item.id}}" value="${{idx}}" ${{(answer.checked || []).includes(idx) ? "checked" : ""}}>
            <span>${{text}}</span>
          </label>`).join("");
        return interactionShell(item, index, rows, `<button class="primary" type="button" onclick="gradeChecklist('${{item.id}}')">Check checklist</button>`);
      }}
      if (item.type === "boundary_ack") {{
        return interactionShell(item, index, `<div class="boundary">${{item.prompt}}</div>`, `<button class="primary" type="button" onclick="ackBoundary('${{item.id}}')">Confirm boundary</button>`);
      }}
      const text = answer.text || "";
      const rubric = (item.rubric || []).map(row => `<li>${{row}}</li>`).join("");
      return interactionShell(item, index, `
        <textarea id="text-${{item.id}}" aria-label="${{item.title}} response">${{text}}</textarea>
        <h4>Rubric</h4><ul>${{rubric}}</ul>`,
        `<button class="primary" type="button" onclick="saveText('${{item.id}}')">Save response</button>`);
    }}

    function renderScreenRecording(item, index) {{
      const answer = state.answers[item.id] || {{}};
      const result = answer.completed ? `<div class="result good">${{answer.message || "Clip reviewed."}}</div>` : "";
      const safeWalk = (typeof item.walkthrough_src === "string" && /^walkthroughs\\/[a-z0-9][a-z0-9._-]{1,80}\\.html$/.test(item.walkthrough_src)) ? item.walkthrough_src : "";
      const safeSrc = (typeof item.video_src === "string" && /^recordings\\/[a-z0-9][a-z0-9._-]{1,80}\\.(webm|mp4)$/.test(item.video_src)) ? item.video_src : "";
      const safePoster = (typeof item.poster_src === "string" && /^recordings\\/[a-z0-9][a-z0-9._-]{1,80}\\.(png|jpg|svg)$/.test(item.poster_src)) ? item.poster_src : "";
      const caption = item.caption ? `<figcaption>${{item.caption}}</figcaption>` : "";
      let player = `<div class="capture-card" role="note"><strong>No teaching walkthrough is wired yet.</strong><p>${{item.capture_hint || "A local watch-only walkthrough will appear here."}}</p></div>`;
      if (safeWalk) {{
        player = `<figure style="margin:0"><iframe class="walkthrough-frame" title="${{item.title}}" src="${{safeWalk}}" style="width:100%;min-height:360px;border:1px solid var(--line);border-radius:12px;background:#0b1220"></iframe>${{caption}}</figure>`;
      }} else if (safeSrc) {{
        player = `<figure style="margin:0"><video class="media-card" controls preload="metadata" src="${{safeSrc}}"${{safePoster ? ` poster="${{safePoster}}"` : ""}}></video>${{caption}}</figure>`;
      }}
      return `<article class="interaction media-card" id="${{item.id}}">
        <h3>${{index + 1}}. ${{item.title}}</h3>
        <p>${{item.prompt}}</p>
        ${{player}}
        <div class="toolbar"><button class="primary" type="button" onclick="markClipReviewed('${{item.id}}')">Mark clip reviewed</button><button class="secondary" type="button" onclick="showExpected('${{item.id}}')">Show guide</button></div>
        ${{result}}
      </article>`;
    }}

    function markClipReviewed(id) {{
      const item = findItem(id);
      state.answers[id] = {{ completed: true, passed: true, message: "Clip reviewed." }};
      record("answered", item.xapi_object || id, {{ completion: true }});
      record("completed", item.xapi_object || id, {{ completion: true }});
      announce("Clip marked reviewed.");
      render();
    }}

    function interactionShell(item, index, body, action) {{
      const answer = state.answers[item.id] || {{}};
      const result = answer.completed ? `<div class="result ${{answer.passed ? "good" : ""}}">${{answer.message || "Saved."}}</div>` : "";
      return `<article class="interaction" id="${{item.id}}">
        <h3>${{index + 1}}. ${{item.title}}</h3>
        <p>${{item.prompt}}</p>
        ${{body}}
        <div class="toolbar">${{action}}<button class="secondary" type="button" onclick="showExpected('${{item.id}}')">Show guide</button></div>
        ${{result}}
      </article>`;
    }}

    function practiceView() {{
      return DATA.interactions.map(renderInteraction).join("");
    }}

    function reviewView() {{
      const rows = DATA.interactions.map(item => {{
        const answer = state.answers[item.id] || {{}};
        return `<li><strong>${{item.title}}:</strong> ${{answer.completed ? (answer.passed ? "passed" : "saved") : "open"}}</li>`;
      }}).join("");
      return `<section class="review-panel"><h2>Review</h2><ul>${{rows}}</ul><div class="toolbar"><button class="primary" type="button" onclick="completeModule()">Complete module</button><button class="secondary" type="button" onclick="resetModule()">Reset local progress</button></div></section>`;
    }}

    function eventsView() {{
      return `<section class="review-panel"><h2>Local xAPI Events</h2><p>Events are stored locally in this browser until exported or reset.</p><pre>${{JSON.stringify(state.events, null, 2)}}</pre><div class="toolbar"><button class="primary" type="button" onclick="downloadEvents()">Download events</button></div></section>`;
    }}

    function render() {{
      const view = document.getElementById("view");
      if (state.view === "practice") view.innerHTML = practiceView();
      else if (state.view === "review") view.innerHTML = reviewView();
      else if (state.view === "events") view.innerHTML = eventsView();
      else view.innerHTML = briefingView();
      document.querySelectorAll(".nav-button").forEach(button => button.setAttribute("aria-pressed", button.dataset.view === state.view ? "true" : "false"));
      updateStatus();
    }}

    function findItem(id) {{ return DATA.interactions.find(item => item.id === id); }}

    function gradeChoice(id) {{
      const item = findItem(id);
      const selected = document.querySelector(`input[name="${{id}}"]:checked`);
      if (!selected) {{ announce("Choose an answer first."); return; }}
      const choice = item.choices.find(row => row.id === selected.value);
      state.answers[id] = {{ choice: choice.id, completed: true, passed: choice.correct, message: choice.feedback || "" }};
      record("answered", item.xapi_object || id, {{ success: choice.correct, response: choice.id }});
      announce(choice.correct ? "Correct." : "Saved. Review the guide.");
      render();
    }}

    function gradeChecklist(id) {{
      const item = findItem(id);
      const checked = Array.from(document.querySelectorAll(`input[data-check="${{id}}"]:checked`)).map(input => Number(input.value));
      const passed = checked.length === item.checklist_items.length;
      state.answers[id] = {{ checked, completed: true, passed, message: passed ? "All minimums checked." : "Missing one or more minimum fields." }};
      record("answered", item.xapi_object || id, {{ success: passed, response: checked.join(",") }});
      render();
    }}

    function ackBoundary(id) {{
      const item = findItem(id);
      state.answers[id] = {{ completed: true, passed: true, message: item.expected || "Boundary confirmed." }};
      record("reviewed_boundary", item.xapi_object || id, {{ success: true }});
      render();
    }}

    function saveText(id) {{
      const item = findItem(id);
      const value = document.getElementById("text-" + id).value.trim();
      state.answers[id] = {{ text: value, completed: value.length > 0, passed: value.length > 0, message: value.length > 0 ? "Response saved for review." : "Write a response first." }};
      if (value.length > 0) record("answered", item.xapi_object || id, {{ response: value.slice(0, 240), completion: true }});
      render();
    }}

    function showExpected(id) {{
      const item = findItem(id);
      alert(item.expected || item.capture_hint || (item.rubric || []).join("\\n"));
    }}

    function completeModule() {{
      const pct = score();
      const passed = pct >= 80;
      record("completed", "module", {{ completion: true, score: {{ scaled: pct / 100 }} }});
      record(passed ? "passed" : "failed", "module", {{ success: passed, score: {{ raw: pct }} }});
      scormFinish(passed, pct);
      announce(passed ? "Module complete." : "Module complete with review needed.");
      render();
    }}

    function downloadEvents() {{
      const blob = new Blob([JSON.stringify(state.events, null, 2)], {{ type: "application/json" }});
      const link = document.createElement("a");
      link.href = URL.createObjectURL(blob);
      link.download = DATA.module_id + "-xapi-events.json";
      link.click();
      URL.revokeObjectURL(link.href);
    }}

    function resetModule() {{
      localStorage.removeItem(STORE_KEY);
      state.answers = {{}};
      state.events = [];
      state.view = "briefing";
      render();
      save();
    }}

    document.querySelectorAll(".nav-button").forEach(button => button.addEventListener("click", () => setView(button.dataset.view)));
    document.addEventListener("keydown", event => {{
      const order = ["briefing", "practice", "review", "events"];
      const idx = order.indexOf(state.view);
      if (event.altKey && event.key === "ArrowRight" && idx < order.length - 1) setView(order[idx + 1]);
      if (event.altKey && event.key === "ArrowLeft" && idx > 0) setView(order[idx - 1]);
    }});
    if (!state.events.length) record("started", "module", {{ completion: false }});
    render();
  </script>
</body>
</html>"""
    )


def seed_xapi_statements(module: dict[str, Any]) -> list[dict[str, Any]]:
    now = utc_now()
    activity = module["xapi"]["activity_id"]
    return [
        {
            "id": "seed-started",
            "timestamp": now,
            "actor": {"name": "local learner"},
            "verb": {"id": "https://adlnet.gov/expapi/verbs/started", "display": {"en-US": "started"}},
            "object": {"id": activity, "definition": {"name": {"en-US": module["title"]}}},
            "context": {"platform": "Veritas local HTML training runtime"},
        },
        {
            "id": "seed-reviewed-boundary",
            "timestamp": now,
            "actor": {"name": "local learner"},
            "verb": {
                "id": "https://adlnet.gov/expapi/verbs/reviewed_boundary",
                "display": {"en-US": "reviewed_boundary"},
            },
            "object": {"id": f"{activity}/authority-boundary"},
            "result": {"completion": True, "success": True},
            "context": {
                "extensions": {
                    "https://veritas.local/extensions/internal_training_only": True,
                    "https://veritas.local/extensions/external_delivery_approved": False,
                }
            },
        },
    ]


def render_scorm_manifest(module: dict[str, Any]) -> str:
    title = xml_escape(module["title"])
    identifier = xml_escape(module["module_id"])
    return clean_text(
        f"""<?xml version="1.0" encoding="UTF-8"?>
<manifest identifier="{identifier}" version="1.0"
  xmlns="http://www.imsproject.org/xsd/imscp_rootv1p1p2"
  xmlns:adlcp="http://www.adlnet.org/xsd/adlcp_rootv1p2"
  xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
  <metadata>
    <schema>ADL SCORM</schema>
    <schemaversion>1.2</schemaversion>
  </metadata>
  <organizations default="org-{identifier}">
    <organization identifier="org-{identifier}">
      <title>{title}</title>
      <item identifier="item-{identifier}" identifierref="res-{identifier}">
        <title>{title}</title>
      </item>
    </organization>
  </organizations>
  <resources>
    <resource identifier="res-{identifier}" type="webcontent" adlcp:scormtype="sco" href="index.html">
      <file href="index.html" />
      <file href="module.json" />
      <file href="xapi-seed.json" />
    </resource>
  </resources>
</manifest>"""
    )


def standards_evaluation() -> dict[str, Any]:
    return {
        "generated_at_utc": utc_now(),
        "status": "implemented_local_first",
        "standards": [
            {
                "name": "H5P",
                "fit": "P2 evaluation",
                "use_when": "Need LMS/CMS-native reusable interaction types or easy author editing.",
                "current_action": "Do not adopt yet; keep as import/export candidate after internal schema stabilizes.",
            },
            {
                "name": "Adapt Learning",
                "fit": "P2 evaluation",
                "use_when": "Need responsive course authoring, SCORM delivery, localization, and larger course assembly.",
                "current_action": "Do not migrate yet; compare against local builder after two modules exist.",
            },
            {
                "name": "xAPI",
                "fit": "P1 implemented locally",
                "use_when": "Need event-level learning telemetry beyond completion.",
                "current_action": "Generate local statements only; no external LRS endpoint configured.",
            },
            {
                "name": "SCORM 1.2",
                "fit": "P1 package, runtime bridge, and local smoke validator implemented",
                "use_when": "Need a zip package shape for LMS upload tests.",
                "current_action": "Generate manifest/package scaffold, SCO runtime calls, and local mock-LMS smoke proof; external LMS import testing remains deferred.",
            },
            {
                "name": "cmi5",
                "fit": "P3 later",
                "use_when": "Need modern LMS launch rules plus xAPI tracking.",
                "current_action": "Defer until xAPI and SCORM package tests prove useful.",
            },
            {
                "name": "WCAG 2.2 / Playwright / axe",
                "fit": "P1 local validator implemented",
                "use_when": "Need automated browser accessibility gates.",
                "current_action": "Use local Playwright and axe-core against generated HTML; no external service required.",
            },
        ],
        "authority_boundary": {
            "local_files_only": True,
            "external_lms_configured": False,
            "external_lrs_configured": False,
            "customer_data_allowed": False,
            "public_delivery_approved": False,
        },
    }


def render_standards_md(evaluation: dict[str, Any]) -> str:
    lines = [
        "# Interactive Training Standards Upgrade Evaluation",
        "",
        f"Generated UTC: {evaluation['generated_at_utc']}",
        "",
        "This is a local-first implementation record. It does not configure an external LMS, LRS, hosting surface, subscription, or public delivery path.",
        "",
        "| Standard | Fit | Current action |",
        "|---|---|---|",
    ]
    for row in evaluation["standards"]:
        lines.append(f"| {row['name']} | {row['fit']} | {row['current_action']} |")
    lines.extend(
        [
            "",
            "## Boundary",
            "",
            "- Local files only.",
            "- No external learner data transport.",
            "- No customer data.",
            "- No public delivery approval.",
            "- No LMS/LRS account or runtime configuration mutation.",
        ]
    )
    return "\n".join(lines) + "\n"


def component_library() -> dict[str, Any]:
    return {
        "schema": "veritas.interactive_training_component_library.v1",
        "generated_at_utc": utc_now(),
        "status": "ok",
        "purpose": "Reusable component contract for local interactive training modules.",
        "components": [
            {
                "id": "lesson",
                "label": "Lesson",
                "purpose": "Teach a compact concept before practice.",
                "required_fields": ["id", "title", "body", "key_points"],
                "validation": ["at least one lesson", "at least two key points"],
                "reuse_notes": "Keep bodies concise and tie every lesson to a later interaction.",
            },
            {
                "id": "multiple_choice",
                "label": "Multiple Choice",
                "purpose": "Check recognition of the safest or most accurate path.",
                "required_fields": ["id", "type", "title", "prompt", "choices", "xapi_object"],
                "validation": ["at least one correct choice", "choice feedback explains why"],
                "reuse_notes": "Use for command selection, source classification, and unsafe-claim spotting.",
                "xapi_verbs": ["answered"],
            },
            {
                "id": "checklist",
                "label": "Checklist",
                "purpose": "Train minimum proof, approval, or handoff fields.",
                "required_fields": ["id", "type", "title", "prompt", "checklist_items", "xapi_object"],
                "validation": ["all checklist items must be selected for a pass"],
                "reuse_notes": "Use when a task has non-negotiable completeness fields.",
                "xapi_verbs": ["answered"],
            },
            {
                "id": "scenario",
                "label": "Scenario",
                "purpose": "Practice written operator judgment under uncertainty.",
                "required_fields": ["id", "type", "title", "prompt", "expected", "rubric", "xapi_object"],
                "validation": ["expected answer present", "rubric names the required judgment"],
                "reuse_notes": "Use for stale proof, conflict, warning-grade, and boundary-repair cases.",
                "xapi_verbs": ["answered"],
            },
            {
                "id": "reflection",
                "label": "Reflection",
                "purpose": "Capture explain-back and next-safe-action thinking.",
                "required_fields": ["id", "type", "title", "prompt", "rubric", "xapi_object"],
                "validation": ["rubric names safe use and blocked use"],
                "reuse_notes": "Use as the final practice item for each module.",
                "xapi_verbs": ["answered"],
            },
            {
                "id": "boundary_ack",
                "label": "Boundary Acknowledgement",
                "purpose": "Force explicit recognition of authority limits.",
                "required_fields": ["id", "type", "title", "prompt", "expected", "xapi_object"],
                "validation": ["expected confirmation present", "module-level blocked flags remain false"],
                "reuse_notes": "Every module that touches action authority should include one.",
                "xapi_verbs": ["reviewed_boundary"],
            },
            {
                "id": "local_xapi",
                "label": "Local xAPI Events",
                "purpose": "Record local started, answered, completed, passed, failed, and boundary review events.",
                "required_fields": ["xapi.activity_id", "xapi.verbs"],
                "validation": ["all required verbs present", "no external LRS configured"],
                "reuse_notes": "Default storage is browser-local; loopback ledger is optional and local-only.",
                "xapi_verbs": sorted(REQUIRED_XAPI_VERBS),
            },
            {
                "id": "scorm_package",
                "label": "SCORM Package",
                "purpose": "Package the module for later LMS smoke/import testing.",
                "required_fields": ["index.html", "module.json", "xapi-seed.json", "imsmanifest.xml"],
                "validation": ["LMSInitialize", "LMSSetValue", "LMSCommit", "LMSFinish"],
                "reuse_notes": "External LMS import remains owner-gated; local mock-LMS smoke is the proof path.",
            },
            {
                "id": "browser_qa",
                "label": "Browser QA",
                "purpose": "Prove desktop/mobile rendering, accessibility, console, and overflow behavior.",
                "required_fields": ["desktop screenshot", "mobile screenshot", "axe result", "console result"],
                "validation": ["severe axe violations 0", "console errors 0", "overflow 0"],
                "reuse_notes": "Run after each new module or runtime change.",
            },
            {
                "id": "screen_recording",
                "label": "Screen Recording",
                "purpose": "Play a local screen-capture clip inside the module, or show $0 capture steps when no clip exists yet.",
                "required_fields": ["id", "type", "title", "prompt", "capture_hint", "xapi_object"],
                "validation": ["capture_hint at least 10 chars", "video_src stays under recordings/ when present", "missing clip is a placeholder warning, not an error"],
                "reuse_notes": "Use for walkthroughs. Capture with Snipping Tool (Win+Shift+R) into training/interactive-training-builder/recordings/.",
                "xapi_verbs": ["answered", "completed"],
            },
            {
                "id": "local_capture_helper",
                "label": "Local Capture Helper",
                "purpose": "Inventory local recordings and print $0 Windows capture steps without any upload or LMS.",
                "required_fields": ["recordings manifest", "recordings README"],
                "validation": ["external_upload_allowed false", "lms_configured false"],
                "reuse_notes": "Run scripts/interactive_training_screen_capture.py --write --validate before catalog builds.",
            },
        ],
        "authority_boundary": {
            "local_files_only": True,
            "external_lms_lrs_configured": False,
            "customer_data_allowed": False,
            "public_delivery_approved": False,
            "owner_approval_inferred": False,
        },
    }


def render_component_library_md(library: dict[str, Any]) -> str:
    lines = [
        "# Interactive Training Component Library",
        "",
        f"Generated UTC: {library['generated_at_utc']}",
        "",
        "Reusable local components for schema-backed HTML training modules.",
        "",
        "| Component | Purpose | Required fields |",
        "|---|---|---|",
    ]
    for component in library["components"]:
        lines.append(
            "| "
            + component["label"]
            + " | "
            + component["purpose"]
            + " | "
            + ", ".join(component["required_fields"])
            + " |"
        )
    lines.extend(
        [
            "",
            "## Boundary",
            "",
            "- Local files only.",
            "- No external LMS/LRS configuration.",
            "- No learner/customer data external transport.",
            "- No public delivery approval.",
            "- No owner approval inference.",
        ]
    )
    return "\n".join(lines) + "\n"


def render_authoring_checklist(library: dict[str, Any]) -> str:
    component_ids = ", ".join(component["id"] for component in library["components"])
    return clean_text(
        f"""# Interactive Training Authoring Checklist

Generated UTC: {library['generated_at_utc']}

Use this checklist before adding or revising a local interactive training module.

## Module Contract

- Define `module_id`, `title`, `audience`, `summary`, `learning_objectives`, lessons, interactions, and xAPI metadata.
- Set `authority_boundary.internal_training_only=true`.
- Keep `external_delivery_approved`, `customer_data_allowed`, `credential_access_allowed`, and `owner_approval_inferred` false.
- Add any domain-specific blocked flags such as collector/runtime/config, finance/canon, outreach, account, paper/live, or capital authority.
- Use only supported interaction types: scenario, multiple_choice, checklist, reflection, screen_recording, and boundary_ack.
- Include at least one boundary acknowledgement when the module touches action authority.
- For screen_recording items, write a capture_hint (10+ chars) naming Snipping Tool and the recordings folder; a missing clip renders a placeholder.

## Component Choices

- Available components: {component_ids}.
- Use lessons for concise concepts, multiple choice for recognition, checklist for minimum proof fields, scenario for operator judgment, reflection for explain-back, and boundary_ack for stop-line confirmation.
- Every interaction needs a stable `id`, clear prompt, and `xapi_object`.
- Multiple-choice items need one correct choice and feedback for each option.
- Scenario and boundary acknowledgement items need an expected answer.

## Proof And Packaging

- Run `python scripts\\interactive_training_screen_capture.py --write --validate` when a module uses screen_recording.
- Run `python scripts\\interactive_training_builder.py --write --validate`.
- Run `python scripts\\test_interactive_training_builder.py`.
- Run `python scripts\\interactive_training_qa_validator.py --write --validate`.
- Run `python scripts\\interactive_training_scorm_smoke_validator.py --write --validate`.
- Run `python scripts\\interactive_training_catalog_builder.py --write --validate`.
- Review `tmp\\interactive-training-builder-proof.json`, `tmp\\interactive-training-qa-validation.json`, `tmp\\interactive-training-scorm-smoke-validation.json`, and `tmp\\interactive-training-catalog-proof.json`.

## Stop Lines

- Do not configure an external LMS or LRS from module authoring.
- Do not add learner/customer data transport.
- Do not approve public delivery, outreach, account action, portfolio/canon mutation, paper/live execution, or capital deployment.
- Do not broaden runtime, collector, cron, channel, credential, or config authority through training content.
"""
    )


def render_contract() -> str:
    return clean_text(
        """# Interactive Training Builder Implementation Contract - 2026-07-03

## Objective

Create a reusable local full-stack foundation for HTML interactive trainings.

## Interpretation

Implement the first durable builder, not a public training platform. The current release produces schema-backed modules, static interactive HTML runtime, local xAPI-style events, SCORM package scaffolds with runtime API bridge calls, local SCORM smoke proof, standards evaluation notes, browser/accessibility validation proof, WF75 sample/HVAC, SEC evidence, OTEL proof modules, and generated authoring resources.

## Non-Goals

- No external hosting.
- No LMS or LRS account setup.
- No paid-tool subscription.
- No cron schedule mutation.
- No runtime/config/auth/channel mutation.
- No real customer data.
- No outreach, public delivery, payment collection, CRM import, credentials, or production access approval.

## Authority Class

Safe local implementation, internal training only. Public/customer delivery remains owner-gated.

## Source Surfaces

- `training/README.md`
- `scripts/wf75_training_desk.py`
- `scripts/wf75_hvac_outreach_training_stack.py`
- `scripts/otel_ops_control.py`
- `skills/otel-operations-analyst/SKILL.md`
- `memory/2026-05-31.md`
- `memory/2026-07-03.md`
- `memory/2026-07-04.md`

## Deliverables

- `schemas/interactive_training_module.schema.json`
- `scripts/interactive_training_builder.py`
- `scripts/test_interactive_training_builder.py`
- `training/interactive-training-builder/sample-wf75-boundary-module.html`
- `training/interactive-training-builder/sample-wf75-boundary-module.json`
- `training/interactive-training-builder/sample-wf75-boundary-module.xapi.json`
- `training/interactive-training-builder/sample-wf75-boundary-module-scorm.zip`
- `training/interactive-training-builder/wf75-hvac-outreach-module.html`
- `training/interactive-training-builder/wf75-hvac-outreach-module.json`
- `training/interactive-training-builder/wf75-hvac-outreach-module.xapi.json`
- `training/interactive-training-builder/wf75-hvac-outreach-module-scorm.zip`
- `training/interactive-training-builder/sec-evidence-review-module.html`
- `training/interactive-training-builder/sec-evidence-review-module.json`
- `training/interactive-training-builder/sec-evidence-review-module.xapi.json`
- `training/interactive-training-builder/sec-evidence-review-module-scorm.zip`
- `training/interactive-training-builder/otel-proof-validator-module.html`
- `training/interactive-training-builder/otel-proof-validator-module.json`
- `training/interactive-training-builder/otel-proof-validator-module.xapi.json`
- `training/interactive-training-builder/otel-proof-validator-module-scorm.zip`
- `training/interactive-training-builder/authoring-checklist.md`
- `training/interactive-training-builder/component-library.json`
- `training/interactive-training-builder/component-library.md`
- `training/interactive-training-builder/standards-upgrade-evaluation.json`
- `scripts/interactive_training_qa_validator.py`
- `scripts/interactive_training_qa_runner.mjs`
- `scripts/interactive_training_scorm_smoke_validator.py`
- `scripts/interactive_training_scorm_smoke_runner.mjs`
- `tmp/interactive-training-qa-validation.json`
- `tmp/interactive-training-scorm-smoke-validation.json`
- `tmp/interactive-training-builder-proof.json`

## Acceptance Proof

- Builder validates module structure and authority flags.
- HTML includes local scoring, progress, keyboard path, aria-live updates, and xAPI event export.
- SCORM packages are generated without external calls.
- SCORM runtime bridge calls are present and local fallback still works without an LMS.
- Local SCORM smoke test passes with mock LMS initialization, status/score/location/suspend-data writes, commit, finish, and no post-finish completion downgrade.
- Playwright/axe local QA passes on desktop and mobile screenshots.
- Tests pass.
- Changed-file validation and release contract are run before closeout.

## Stop Lines

Stop before any external delivery, LMS/LRS account mutation, customer data capture, credentials, config/runtime changes, public launch, paid subscription, or authority expansion.
"""
    )


def write_scorm_package(
    module: dict[str, Any],
    html_text: str,
    xapi_seed: list[dict[str, Any]],
    paths: dict[str, Path],
) -> None:
    scorm_dir = paths["scorm_dir"]
    scorm_manifest = paths["scorm_manifest"]
    scorm_zip = paths["scorm_zip"]
    scorm_dir.mkdir(parents=True, exist_ok=True)
    atomic_write_text(scorm_dir / "index.html", html_text)
    atomic_write_json(scorm_dir / "module.json", module)
    atomic_write_json(scorm_dir / "xapi-seed.json", xapi_seed)
    atomic_write_text(scorm_manifest, render_scorm_manifest(module))
    extra_paths = []
    for item in module.get("interactions", []):
        walkthrough_src = item.get("walkthrough_src")
        if walkthrough_src and is_safe_media_src(walkthrough_src, "walkthrough"):
            source = TRAINING / walkthrough_src
            if source.exists():
                dest = scorm_dir / walkthrough_src
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
                extra_paths.append(dest)
    with zipfile.ZipFile(scorm_zip, "w", compression=zipfile.ZIP_DEFLATED) as package:
        for path in [scorm_dir / "index.html", scorm_dir / "module.json", scorm_dir / "xapi-seed.json", scorm_manifest, *extra_paths]:
            package.write(path, arcname=path.relative_to(scorm_dir).as_posix())


def validate_outputs(html_text: str, module: dict[str, Any]) -> list[str]:
    errors = validate_module(module)
    required_html_markers = {
        "doctype": "<!doctype html>",
        "lang": '<html lang="en">',
        "viewport": 'name="viewport"',
        "aria_live": 'aria-live="polite"',
        "local_storage": "localStorage",
        "xapi_statement": "https://adlnet.gov/expapi/verbs/",
        "local_xapi_ledger": "localLedgerEnabled",
        "keyboard": "ArrowRight",
        "download_events": "downloadEvents",
        "scorm_api": "LMSInitialize",
        "scorm_status": "cmi.core.lesson_status",
    }
    lower_html = html_text.lower()
    for name, marker in required_html_markers.items():
        haystack = lower_html if name in {"doctype", "lang"} else html_text
        needle = marker.lower() if name in {"doctype", "lang"} else marker
        if needle not in haystack:
            errors.append(f"html_marker_missing:{name}")
    external_urls = re.findall(r"https?://(?!(?:adlnet.gov|veritas.local|127\.0\.0\.1:8766))[^\"')< ]+", html_text)
    if external_urls:
        errors.append("unexpected_external_url:" + ",".join(sorted(set(external_urls))[:3]))
    blocked_markers = ["api_key", "authorization:", "bearer ", "password", "secret"]
    for marker in blocked_markers:
        if marker in lower_html:
            errors.append(f"blocked_marker_present:{marker.strip()}")
    return errors


def build_module_artifacts(module: dict[str, Any], prefix: str, write: bool = False) -> dict[str, Any]:
    paths = artifact_paths(prefix)
    html_text = render_html(module)
    xapi_seed = seed_xapi_statements(module)
    validation_errors = validate_outputs(html_text, module)
    validation_warnings = screen_recording_warnings(module)
    manifest = {
        "schema": "veritas.interactive_training_module_manifest.v1",
        "generated_at_utc": utc_now(),
        "status": "ok" if not validation_errors else "blocked",
        "module_id": module["module_id"],
        "outputs": {
            "module_json": rel(paths["module_json"]),
            "module_html": rel(paths["module_html"]),
            "xapi_seed": rel(paths["xapi_seed"]),
            "scorm_manifest": rel(paths["scorm_manifest"]),
            "scorm_zip": rel(paths["scorm_zip"]),
            "module_manifest": rel(paths["manifest"]),
        },
        "capabilities": {
            "schema_backed_module": True,
            "static_html_runtime": True,
            "local_scoring": True,
            "local_progress_storage": True,
            "xapi_style_events": True,
            "local_xapi_ledger_optional": True,
            "scorm_package_scaffold": True,
            "scorm_runtime_api_adapter": True,
            "external_lms_lrs_configured": False,
            "customer_data_allowed": False,
        },
        "counts": {
            "lessons": len(module["lessons"]),
            "interactions": len(module["interactions"]),
            "xapi_seed_statements": len(xapi_seed),
            "standards_reviewed": 0,
        },
        "validation": {
            "errors": validation_errors,
            "warnings": validation_warnings,
        },
        "authority_boundary": module["authority_boundary"],
    }
    if write:
        TRAINING.mkdir(parents=True, exist_ok=True)
        atomic_write_json(paths["module_json"], module)
        atomic_write_text(paths["module_html"], html_text)
        atomic_write_json(paths["xapi_seed"], xapi_seed)
        write_scorm_package(module, html_text, xapi_seed, paths)
        atomic_write_json(paths["manifest"], manifest)
    return manifest


def build(write: bool = False) -> dict[str, Any]:
    modules = [
        build_module_artifacts(build_sample_module(), "sample-wf75-boundary-module", write=write),
        build_module_artifacts(build_hvac_module(), HVAC_MODULE_PREFIX, write=write),
        build_module_artifacts(build_sec_evidence_module(), SEC_MODULE_PREFIX, write=write),
        build_module_artifacts(build_otel_proof_validator_module(), OTEL_MODULE_PREFIX, write=write),
        build_module_artifacts(build_openclaw_day1_module(), OPENCLAW_DAY1_PREFIX, write=write),
    ]
    evaluation = standards_evaluation()
    library = component_library()
    validation_errors = [error for module in modules for error in module["validation"]["errors"]]
    warnings = [warning for module in modules for warning in module["validation"]["warnings"]]
    manifest = {
        "schema": "veritas.interactive_training_builder_manifest.v2",
        "generated_at_utc": utc_now(),
        "status": "ok" if not validation_errors else "blocked",
        "outputs": {
            "standards_evaluation": rel(MODULE_STANDARDS),
            "implementation_contract": rel(CONTRACT),
            "authoring_checklist": rel(AUTHORING_CHECKLIST),
            "component_library": rel(COMPONENT_LIBRARY_JSON),
            "component_library_md": rel(COMPONENT_LIBRARY_MD),
        },
        "modules": modules,
        "capabilities": {
            "schema_backed_module": True,
            "static_html_runtime": True,
            "local_scoring": True,
            "local_progress_storage": True,
            "xapi_style_events": True,
            "local_xapi_ledger_optional": True,
            "scorm_package_scaffold": True,
            "scorm_runtime_api_adapter": True,
            "scorm_local_smoke_validator": True,
            "h5p_adapt_evaluation": True,
            "playwright_axe_local_qa": True,
            "authoring_checklist": True,
            "component_library": True,
            "screen_recording_player": True,
            "local_screen_capture_helper": True,
            "external_lms_lrs_configured": False,
            "customer_data_allowed": False,
        },
        "counts": {
            "modules": len(modules),
            "lessons": sum(module["counts"]["lessons"] for module in modules),
            "interactions": sum(module["counts"]["interactions"] for module in modules),
            "xapi_seed_statements": sum(module["counts"]["xapi_seed_statements"] for module in modules),
            "standards_reviewed": len(evaluation["standards"]),
            "components": len(library["components"]),
        },
        "validation": {
            "errors": validation_errors,
            "warnings": warnings,
        },
        "authority_boundary": {
            "internal_training_only": True,
            "external_delivery_approved": False,
            "customer_data_allowed": False,
            "credential_access_allowed": False,
            "owner_approval_inferred": False,
        },
    }
    if write:
        atomic_write_json(MODULE_STANDARDS, evaluation)
        atomic_write_text(MODULE_STANDARDS_MD, render_standards_md(evaluation))
        atomic_write_text(AUTHORING_CHECKLIST, render_authoring_checklist(library))
        atomic_write_json(COMPONENT_LIBRARY_JSON, library)
        atomic_write_text(COMPONENT_LIBRARY_MD, render_component_library_md(library))
        atomic_write_json(TMP_PROOF, manifest)
        atomic_write_text(CONTRACT, render_contract())
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    args = parser.parse_args()
    manifest = build(write=args.write)
    print(json.dumps(manifest, indent=2, sort_keys=True))
    if args.validate and manifest["validation"]["errors"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
