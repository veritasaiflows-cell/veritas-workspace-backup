#!/usr/bin/env python3
"""Build the generic intelligence SaaS pivot control packets.

These packets convert the 2026-05-31 infrastructure pivot audit into
repeatable workflow state. They are planning/control artifacts only: they do
not grant customer data use, external delivery, credential access, outreach,
implementation authority, payment authority, or public launch readiness.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
from datetime import datetime, timezone
from html import escape
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json


ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"

PIVOT_SUMMARY_JSON = TMP / "generic-intelligence-saas-pivot.json"
CONTRACT_JSON = TMP / "generic-service-run-contract.json"
SCENARIO_LIBRARY_JSON = TMP / "wf75-smb-workflow-scenario-library.json"
PM_DECISION_PACKET_JSON = TMP / "wf75-smb-pivot-pm-decision-packet.json"
CUSTOMER_PREVIEW_JSON = TMP / "wf75-smb-customer-preview.json"
CUSTOMER_PREVIEW_MD = TMP / "wf75-smb-customer-preview.md"
CUSTOMER_PREVIEW_VALIDATION_JSON = TMP / "wf75-smb-customer-preview-validation.json"
PILOT_DECISION_PACKET_JSON = TMP / "wf75-smb-pilot-decision-packet.json"
LEAD_RESCUE_SERVICE_PACKET_JSON = TMP / "wf75-smb-lead-rescue-service-packet.json"
LEAD_RESCUE_SERVICE_PACKET_MD = TMP / "wf75-smb-lead-rescue-service-packet.md"
LEAD_RESCUE_SERVICE_PACKET_VALIDATION_JSON = TMP / "wf75-smb-lead-rescue-service-packet-validation.json"
AUTOMATION_BLUEPRINTS_JSON = TMP / "wf75-smb-automation-blueprints.json"
AUTOMATION_BLUEPRINTS_VALIDATION_JSON = TMP / "wf75-smb-automation-blueprints-validation.json"
SMB_SERVICE_STATE_JSON = TMP / "wf75-smb-service-state-current.json"
SMB_SERVICE_STATE_VALIDATION_JSON = TMP / "wf75-smb-service-state-validation.json"
OFFER_ICP_JSON = TMP / "wf79-smb-offer-icp-packet.json"
OFFER_ICP_MD = TMP / "wf79-smb-offer-icp-packet.md"
DEMO_PACKETS_JSON = TMP / "wf79-smb-demo-packets.json"
DEMO_PACKETS_MD = TMP / "wf79-smb-demo-packets.md"
DEMO_PACKETS_VALIDATION_JSON = TMP / "wf79-smb-demo-packets-validation.json"
MARKETING_OPS_BLUEPRINTS_JSON = TMP / "wf79-smb-marketing-ops-blueprints.json"
MARKETING_OPS_BLUEPRINTS_VALIDATION_JSON = TMP / "wf79-smb-marketing-ops-blueprints-validation.json"
COCKPIT_PANEL_JSON = TMP / "wf79-smb-cockpit-panel.json"
COCKPIT_PANEL_HTML = TMP / "wf79-smb-cockpit-panel.html"
SALES_PRACTICE_JSON = TMP / "wf79-smb-sales-practice-packet.json"
SALES_PRACTICE_MD = TMP / "wf79-smb-sales-practice-packet.md"
OUTREACH_KIT_JSON = TMP / "wf79-smb-outreach-kit.json"
OUTREACH_KIT_MD = TMP / "wf79-smb-outreach-kit.md"
PILOT_SCOPE_INTAKE_JSON = TMP / "wf79-smb-pilot-scope-intake.json"
PILOT_SCOPE_INTAKE_MD = TMP / "wf79-smb-pilot-scope-intake.md"
VERTICAL_ICP_TARGETING_JSON = TMP / "wf79-smb-vertical-icp-targeting.json"
VERTICAL_ICP_TARGETING_MD = TMP / "wf79-smb-vertical-icp-targeting.md"
DEMO_POLISH_PACKET_JSON = TMP / "wf79-smb-demo-polish-packet.json"
DEMO_POLISH_PACKET_MD = TMP / "wf79-smb-demo-polish-packet.md"
OUTREACH_PREP_VALIDATION_JSON = TMP / "wf79-smb-outreach-prep-validation.json"
PILOT_READINESS_PACKET_JSON = TMP / "wf79-smb-pilot-readiness-packet.json"
PILOT_READINESS_PACKET_MD = TMP / "wf79-smb-pilot-readiness-packet.md"
SALES_CONVERSATION_DRILL_JSON = TMP / "wf79-smb-sales-conversation-drill.json"
SALES_CONVERSATION_DRILL_MD = TMP / "wf79-smb-sales-conversation-drill.md"
DEMO_SELECTION_TREE_JSON = TMP / "wf79-smb-demo-selection-tree.json"
DEMO_SELECTION_TREE_MD = TMP / "wf79-smb-demo-selection-tree.md"
VERTICAL_TEST_FRAMEWORK_JSON = TMP / "wf79-smb-vertical-test-framework.json"
VERTICAL_TEST_FRAMEWORK_MD = TMP / "wf79-smb-vertical-test-framework.md"
PILOT_READINESS_VALIDATION_JSON = TMP / "wf79-smb-pilot-readiness-validation.json"
ROLLOUT_READINESS_PLAN_JSON = TMP / "wf79-smb-rollout-readiness-plan.json"
ROLLOUT_READINESS_PLAN_MD = TMP / "wf79-smb-rollout-readiness-plan.md"
CLIENT_ROLLOUT_CHECKLIST_JSON = TMP / "wf79-smb-client-rollout-checklist.json"
CLIENT_ROLLOUT_CHECKLIST_MD = TMP / "wf79-smb-client-rollout-checklist.md"
CURRICULUM_MAP_JSON = TMP / "wf79-smb-curriculum-map.json"
CURRICULUM_MAP_MD = TMP / "wf79-smb-curriculum-map.md"
ROLLOUT_READINESS_VALIDATION_JSON = TMP / "wf79-smb-rollout-readiness-validation.json"
DELIVERABLE_GATE_JSON = TMP / "wf75-smb-deliverable-gate-sprint.json"
DELIVERABLE_GATE_MD = TMP / "wf75-smb-deliverable-gate-sprint.md"
DELIVERABLE_GATE_VALIDATION_JSON = TMP / "wf75-smb-deliverable-gate-validation.json"
PHASE_CLOSEOUT_JSON = TMP / "wf79-smb-phase-closeout.json"
DEFAULT_DB = TMP / "generic-service-state.sqlite"

AUDIT_SOURCE = "08. Audits/Generic Intelligence SaaS Infrastructure Pivot Audit - 2026-05-31.md"

AUTHORITY_FALSE_FLAGS = {
    "real_customer_data_allowed": False,
    "customer_identity_allowed": False,
    "customer_data_retention_allowed": False,
    "external_delivery_allowed": False,
    "public_launch_allowed": False,
    "customer_outreach_allowed": False,
    "message_sending_allowed": False,
    "phone_system_or_crm_credential_access_allowed": False,
    "payment_pos_payroll_account_access_allowed": False,
    "implementation_in_customer_systems_allowed": False,
    "legal_tax_compliance_security_readiness_claim_allowed": False,
    "guaranteed_revenue_or_roi_claim_allowed": False,
    "finance_portfolio_or_canon_mutation_allowed": False,
    "paper_or_live_execution_allowed": False,
    "owner_approval_inferred": False,
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def scenario(
    scenario_id: str,
    title: str,
    buyer_pain: str,
    input_signals: list[str],
    outputs: list[str],
    validator_focus: list[str],
) -> dict[str, Any]:
    return {
        "scenario_id": scenario_id,
        "title": title,
        "domain": "workflow_automation",
        "status": "review_ready",
        "priority": "P1_monetization_side_lane",
        "target_customer": "owner-operator or small service business",
        "buyer_pain": buyer_pain,
        "current_bottleneck": buyer_pain,
        "desired_outcome": "; ".join(outputs[:2]),
        "next_best_manual_step": "Use sanitized samples to build the owner attention queue, script draft, and blocker list for human review.",
        "success_criteria": [
            "owner can see who needs attention next",
            "follow-up wording is staged for human approval only",
            "unsafe customer-data, credential, outreach, and ROI claims remain blocked",
        ],
        "allowed_input_mode": "anonymous_fixture_or_customer-provided_sample_only_after_future_gate",
        "input_signals": input_signals,
        "outputs": outputs,
        "validator_focus": validator_focus,
        "stop_lines": [
            "no real customer identity before explicit intake gate",
            "no CRM, phone, ad, email, payment, POS, or payroll credential use",
            "no outbound calls, texts, emails, posts, or lead messages",
            "no guaranteed revenue, ROI, legal, compliance, or security claims",
        ],
        "authority": AUTHORITY_FALSE_FLAGS,
    }


def build_contract(generated_at: str) -> dict[str, Any]:
    return {
        "schema": "veritas.generic_service_run_contract.v1",
        "generated_at_utc": generated_at,
        "status": "ok",
        "audit_source": AUDIT_SOURCE,
        "platform_posture": "Veritas Intelligence Operations Engine",
        "decision": {
            "recommended_default": "retail_finance_p0_continuity_smb_workflow_clarity_p1_monetization_side_lane",
            "why": "The same run-contract, validator, renderer, SQL, and PM-control pattern can serve non-finance workflow automation offers faster than a regulated finance-only SaaS launch.",
            "finance_lane": "kept as high-value P0 continuity vertical",
            "smb_lane": "activated as P1 faster-cash-flow monetization lane",
        },
        "service_run_object": {
            "required_fields": [
                "run_id",
                "domain",
                "scenario_id",
                "request_context",
                "source_inputs",
                "analysis_state",
                "customer_safe_outputs",
                "operator_actions",
                "validation",
                "authority_boundary",
                "created_at_utc",
                "updated_at_utc",
            ],
            "domains": [
                "finance_intelligence",
                "workflow_automation",
                "business_research",
                "learning_plan",
                "document_intelligence",
            ],
            "state_machine": [
                "requested",
                "intake_normalized",
                "analysis_ready",
                "draft_output_ready",
                "validator_passed",
                "operator_review_ready",
                "customer_preview_ready",
                "blocked",
            ],
        },
        "authority_boundary": AUTHORITY_FALSE_FLAGS,
        "validation": {"status": "ok", "errors": [], "warnings": []},
    }


def build_scenarios(generated_at: str) -> dict[str, Any]:
    scenarios = [
        scenario(
            "smb-missed-call-capture-v1",
            "Missed-call capture and callback priority",
            "Missed calls and voicemails turn into lost revenue because nobody knows who needs a fast callback.",
            ["missed call log", "voicemail transcript", "caller number", "timestamp", "business hours"],
            ["voicemail summary", "call reason tag", "callback priority", "suggested callback script"],
            ["no phone credential access", "no outbound call", "no real caller identity in fixtures"],
        ),
        scenario(
            "smb-lead-intake-routing-v1",
            "Lead intake from forms, texts, ads, email, and walk-ins",
            "Leads arrive from too many places and are not normalized into one owner view.",
            ["website form sample", "text inquiry sample", "ad lead sample", "email inquiry sample", "walk-in note"],
            ["normalized lead record", "source tag", "urgency tag", "next touch recommendation"],
            ["no CRM credential use", "no ad platform access", "sample data anonymized"],
        ),
        scenario(
            "smb-lead-status-tracking-v1",
            "Lead status tracking",
            "Teams cannot tell which leads are new, contacted, quoted, scheduled, lost, won, or overdue.",
            ["lead list", "last contact note", "quote status", "appointment status"],
            ["status labels", "stale lead flags", "owner field", "next action"],
            ["no customer data retention", "no system writeback", "status labels are advisory"],
        ),
        scenario(
            "smb-follow-up-sequences-v1",
            "Follow-up automation plan",
            "Follow-up depends on memory instead of repeatable reminder and message sequences.",
            ["lead status", "quote age", "appointment date", "review/referral trigger"],
            ["reminder sequence", "quote follow-up wording", "appointment confirmation", "review/referral ask"],
            ["no message sending", "no spam compliance claim", "operator review required"],
        ),
        scenario(
            "smb-sales-pipeline-cleanup-v1",
            "Sales pipeline cleanup",
            "Owners do not know where leads stall or what message should go out next.",
            ["pipeline export sample", "status history", "owner assignment", "last touch"],
            ["stall points", "owner next-touch list", "message recommendation", "cleanup checklist"],
            ["no CRM mutation", "no revenue guarantee", "no outbound messaging"],
        ),
        scenario(
            "smb-owner-attention-dashboard-v1",
            "Owner/operator attention dashboard",
            "The owner needs a simple daily list of who needs attention without rebuilding a full CRM.",
            ["today's leads", "appointments", "quote queue", "missed calls", "overdue follow-ups"],
            ["attention queue", "priority reasons", "daily owner dashboard", "handoff summary"],
            ["internal preview only", "no production dashboard claim", "no external delivery"],
        ),
        scenario(
            "smb-script-message-pack-v1",
            "Script and message pack",
            "Teams need consistent callback, SMS, email, and quote follow-up language.",
            ["business type", "offer type", "tone preference", "common objections"],
            ["callback script", "SMS templates", "email follow-ups", "quote follow-up wording"],
            ["no legal compliance claim", "operator approves before use", "no message sending"],
        ),
        scenario(
            "smb-tool-stack-recommendation-v1",
            "Tool stack recommendation",
            "Owners need to know what existing tools can handle and when Zapier, Make, CRM, or phone upgrades are worth it.",
            ["current tools", "lead sources", "manual steps", "budget range", "pain points"],
            ["use-existing-tools plan", "automation map", "upgrade recommendation", "implementation sequence"],
            ["no credential access", "no purchase action", "recommendation only"],
        ),
    ]
    return {
        "schema": "veritas.wf75_smb_workflow_scenario_library.v1",
        "generated_at_utc": generated_at,
        "status": "ok",
        "audit_source": AUDIT_SOURCE,
        "recommended_first_offer": "Lead Rescue & Follow-Up Workflow Sprint",
        "alternate_offer_name": "Workflow Clarity Sprint",
        "scenario_count": len(scenarios),
        "scenarios": scenarios,
        "authority_boundary": AUTHORITY_FALSE_FLAGS,
        "validation": {"status": "ok", "errors": [], "warnings": []},
    }


def build_pm_packet(generated_at: str) -> dict[str, Any]:
    phases = [
        {
            "phase": 0,
            "name": "Pivot Contract Lock",
            "objective": "Freeze the generic service-run contract and stop-line boundary.",
            "acceptance": ["contract artifact validates", "Active Workflows/MEMORY/TOOLS updated", "PM sees SMB pivot lane"],
        },
        {
            "phase": 1,
            "name": "Generic Schema And SQL Prep",
            "objective": "Separate generic service-run state from finance canon and prepare derived SQL lookup.",
            "acceptance": ["generic-service-state SQLite design exists", "JSON remains source proof", "SQL has no approval/import/customer authority"],
        },
        {
            "phase": 2,
            "name": "SMB Scenario Library",
            "objective": "Make the missed-call, lead, follow-up, dashboard, script, and tool-stack scenarios repeatable.",
            "acceptance": ["at least 8 SMB scenarios validate", "each scenario has outputs and stop lines", "no real customer data required"],
        },
        {
            "phase": 3,
            "name": "SMB Renderer And Validator",
            "objective": "Render customer-preview packets for the first offer while blocking unsafe claims and data leakage.",
            "acceptance": ["Lead Rescue preview renders", "validator blocks identity/credential/outreach/ROI claims", "operator-only proof exists"],
        },
        {
            "phase": 4,
            "name": "TypeScript PM Cockpit Expansion",
            "objective": "Add local cockpit views for generic runs, SMB scenarios, customer-preview output, and PM next actions.",
            "acceptance": ["local-only routes validate", "source registry includes SMB artifacts", "no public/customer delivery route"],
        },
        {
            "phase": 5,
            "name": "Derived SQL Control Plane",
            "objective": "Create a derived SQL index over generic service runs for PM speed and audit queries.",
            "acceptance": ["SQLite integrity passes", "tables include service_runs/domain_payloads/artifact_refs/operator_queue/qa_events/renderer_outputs/authority_events", "JSON-to-SQL parity proof passes"],
        },
        {
            "phase": 6,
            "name": "Workflow Automation Blueprint Layer",
            "objective": "Translate Lead Rescue scenarios into dry-run workflow blueprints with trigger, dedup, retry, audit log, and human-review queue design.",
            "acceptance": ["automation blueprint artifact validates", "each blueprint has idempotency and audit logging", "no credential, outbound, or customer-system authority"],
        },
        {
            "phase": 7,
            "name": "PM And Cron Automation",
            "objective": "Let PM automatically queue the next safe SMB slice while heartbeat/cron only produce handoff packets.",
            "acceptance": ["PM next action ranks SMB lane when ready", "heartbeat handoff is queue-only", "cron has no external delivery or customer-data authority"],
        },
        {
            "phase": 8,
            "name": "Pilot Decision Packet",
            "objective": "Prepare a service-led paid pilot offer that can be sold manually after owner approval.",
            "acceptance": ["offer scope, price hypothesis, deliverables, exclusions, and manual sales script exist", "no automated outreach", "Randall approval required before customer use"],
        },
    ]
    return {
        "schema": "veritas.wf75_smb_pivot_pm_decision_packet.v1",
        "generated_at_utc": generated_at,
        "status": "ok",
        "audit_source": AUDIT_SOURCE,
        "recommendation": "Keep Retail Finance as P0 continuity; make SMB Workflow Clarity / Lead Rescue the P1 monetization lane and automate the generic service engine underneath both.",
        "why_this_leaps_forward": [
            "The platform stops being finance-only and becomes a reusable intelligence-operations engine.",
            "SMB workflow automation can be sold as a service-led sprint before a regulated finance product is launch-ready.",
            "The same validator, renderer, SQL lookup, PM cockpit, and handoff machinery can support both verticals.",
        ],
        "sql_migration_plan": {
            "default": "derived_control_plane_only",
            "recommended_db": rel(DEFAULT_DB),
            "tables": [
                "service_runs",
                "domain_payloads",
                "artifact_refs",
                "operator_queue",
                "qa_events",
                "renderer_outputs",
                "authority_events",
            ],
            "rules": [
                "JSON artifacts remain source proof until a separate durable-state gate is approved.",
                "Finance canon and SMB workflow service state stay separate.",
                "SQL is for lookup, PM dashboards, history, parity checks, and audit queries only.",
            ],
        },
        "typescript_node_plan": {
            "app": "apps/pm-control-cockpit",
            "local_only": True,
            "routes_to_add": [
                "/generic",
                "/smb",
                "/smb/scenarios",
                "/smb/service-runs",
                "/smb/customer-preview",
                "/api/generic/pivot",
                "/api/smb/scenarios",
                "/api/smb/service-runs",
            ],
            "purpose": "Render operator and customer-preview views from validated JSON contracts without rewriting the Python engines.",
        },
        "pm_automation_plan": {
            "next_pm_lane": "smb_workflow_clarity",
            "heartbeat_role": "queue main-session handoff only",
            "cron_role": "refresh proof packets on a bounded schedule after route is stable",
            "stop_line": "No automatic outreach, external delivery, customer data ingestion, or customer-system implementation.",
        },
        "phases": phases,
        "authority_boundary": AUTHORITY_FALSE_FLAGS,
        "validation": {"status": "ok", "errors": [], "warnings": []},
    }


def build_customer_preview(generated_at: str, scenarios: dict[str, Any]) -> dict[str, Any]:
    lead_rescue_ids = [
        "smb-missed-call-capture-v1",
        "smb-lead-intake-routing-v1",
        "smb-lead-status-tracking-v1",
        "smb-follow-up-sequences-v1",
        "smb-owner-attention-dashboard-v1",
        "smb-script-message-pack-v1",
    ]
    scenario_by_id = {item["scenario_id"]: item for item in scenarios.get("scenarios", [])}
    selected = [scenario_by_id[item] for item in lead_rescue_ids if item in scenario_by_id]
    return {
        "schema": "veritas.wf75_smb_customer_preview.v1",
        "generated_at_utc": generated_at,
        "status": "ok",
        "preview_kind": "operator_review_only_customer_preview",
        "offer_name": "Lead Rescue & Follow-Up Workflow Sprint",
        "target_customer": "owner-operator or small service business",
        "source_scenario_ids": [item["scenario_id"] for item in selected],
        "positioning": {
            "plain_language_offer": "A short service-led sprint that turns anonymous missed-call, lead-intake, quote, and follow-up samples into a daily owner attention queue and reusable follow-up scripts.",
            "best_fit": [
                "service businesses losing leads across phones, forms, texts, ads, and email",
                "owners who need a simple daily next-action view before buying or rebuilding a CRM",
                "teams that want scripts and follow-up sequence drafts for human approval",
            ],
            "not_in_scope": [
                "real customer data ingestion before a future intake/privacy/security gate",
                "credential access to phone, CRM, ad, email, payment, POS, or payroll systems",
                "sending calls, texts, emails, review requests, or social messages",
                "legal, compliance, security, revenue, or ROI readiness claims",
            ],
        },
        "preview_sections": [
            {
                "title": "Lead sources normalized",
                "customer_visible_summary": "Sample missed calls, form leads, emails, texts, and ad inquiries are converted into one review queue with source, urgency, and next-touch labels.",
                "source_scenarios": ["smb-missed-call-capture-v1", "smb-lead-intake-routing-v1"],
            },
            {
                "title": "Owner attention queue",
                "customer_visible_summary": "Each lead gets a status, stale-lead signal, priority reason, and owner-facing next action for manual review.",
                "source_scenarios": ["smb-lead-status-tracking-v1", "smb-owner-attention-dashboard-v1"],
            },
            {
                "title": "Follow-up and script pack",
                "customer_visible_summary": "The preview produces callback wording, quote follow-up drafts, appointment reminders, and referral/review asks for a human operator to approve before use.",
                "source_scenarios": ["smb-follow-up-sequences-v1", "smb-script-message-pack-v1"],
            },
        ],
        "sample_outputs": [
            "daily owner attention queue",
            "lead-status cleanup list",
            "callback priority reasons",
            "quote and appointment follow-up drafts",
            "tool-stack gap notes for manual review",
        ],
        "operator_controls": [
            "review all generated language before use",
            "remove any private customer identifiers from source samples",
            "keep delivery local until explicit external-delivery approval exists",
            "treat recommendations as workflow clarity, not guaranteed sales outcome",
        ],
        "authority_boundary": AUTHORITY_FALSE_FLAGS,
        "validation": {"status": "ok", "errors": [], "warnings": []},
    }


def render_customer_preview_markdown(preview: dict[str, Any]) -> str:
    lines = [
        f"# {preview['offer_name']}",
        "",
        f"Status: {preview['preview_kind']}",
        "",
        "## Offer",
        preview["positioning"]["plain_language_offer"],
        "",
        "## Preview Sections",
    ]
    for section in preview["preview_sections"]:
        lines.extend([
            "",
            f"### {section['title']}",
            section["customer_visible_summary"],
            "",
            "Source scenarios:",
            *[f"- {scenario_id}" for scenario_id in section["source_scenarios"]],
        ])
    lines.extend(["", "## Sample Outputs"])
    lines.extend(f"- {item}" for item in preview["sample_outputs"])
    lines.extend(["", "## Stop Lines"])
    lines.extend(f"- {item}" for item in preview["positioning"]["not_in_scope"])
    lines.extend(["", "## Operator Controls"])
    lines.extend(f"- {item}" for item in preview["operator_controls"])
    lines.extend(["", "Authority: review-only; no real customer data, external delivery, credential access, outreach, guaranteed ROI, or owner approval inference."])
    return "\n".join(lines) + "\n"


def build_pilot_decision_packet(generated_at: str, preview: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema": "veritas.wf75_smb_pilot_decision_packet.v1",
        "generated_at_utc": generated_at,
        "status": "review_ready",
        "decision_needed": "Randall manual review before any real customer or pilot use.",
        "offer_name": preview["offer_name"],
        "pilot_posture": "manual_service_led_pilot_candidate",
        "recommended_scope": [
            "one anonymous or sanitized workflow sample set",
            "lead-source map",
            "owner attention queue preview",
            "follow-up script/message pack draft",
            "manual tool-stack and next-step recommendation",
        ],
        "explicit_exclusions": preview["positioning"]["not_in_scope"],
        "manual_sales_notes": [
            "Sell only as workflow clarity and lead-follow-up cleanup until real intake/privacy/security gates exist.",
            "Use sanitized samples or synthetic fixtures for proof before any customer data gate.",
            "Do not promise revenue lift, conversion rate, compliance coverage, or automated implementation.",
        ],
        "proof_artifacts": [
            rel(SCENARIO_LIBRARY_JSON),
            rel(CUSTOMER_PREVIEW_JSON),
            rel(CUSTOMER_PREVIEW_MD),
            rel(CUSTOMER_PREVIEW_VALIDATION_JSON),
        ],
        "authority_boundary": AUTHORITY_FALSE_FLAGS,
        "validation": {"status": "ok", "errors": [], "warnings": []},
    }


def build_lead_rescue_service_packet(generated_at: str, preview: dict[str, Any], pilot_packet: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema": "veritas.wf75_smb_lead_rescue_service_packet.v1",
        "generated_at_utc": generated_at,
        "status": "review_ready",
        "packet_kind": "owner_facing_internal_service_packet",
        "offer_name": preview["offer_name"],
        "service_posture": "manual_service_led_review_only_pilot_candidate",
        "plain_language_summary": "A short manual sprint that turns sanitized lead and missed-call samples into a practical owner attention queue, follow-up script pack, and workflow cleanup plan.",
        "customer_fit": [
            "small service businesses that miss leads across phone, form, text, email, ads, or quote requests",
            "owner-operators who need a daily next-action list before buying or rebuilding a CRM",
            "teams willing to review and approve every follow-up draft before use",
        ],
        "what_customer_gets": [
            {
                "deliverable": "lead-source and leak map",
                "description": "A simple map of where missed calls, forms, quote requests, texts, and email leads are entering or getting lost.",
            },
            {
                "deliverable": "owner attention queue",
                "description": "A review-only queue with lead status, stale-lead flags, callback priority, blocker reason, and the next manual action.",
            },
            {
                "deliverable": "follow-up script/message pack",
                "description": "Callback, quote follow-up, appointment reminder, and review/referral wording drafts for human approval only.",
            },
            {
                "deliverable": "tool-stack gap notes",
                "description": "A practical list of process gaps and low-risk next steps before any automation or system implementation is considered.",
            },
            {
                "deliverable": "pilot recap and next-action plan",
                "description": "A short owner-facing summary of findings, manual fixes, blocked items, and what would be required for a future automation phase.",
            },
        ],
        "what_we_need_from_customer": [
            "sanitized sample missed-call or lead records with names, phone numbers, emails, addresses, order IDs, and private details removed",
            "a plain-English list of current lead sources and where each source is checked today",
            "current follow-up timing rules or preferences, if they already exist",
            "sample approved tone or phrases the business already uses with customers",
            "business-hours and service-area rules in general terms",
            "no passwords, API keys, CRM logins, phone-system logins, ad accounts, payment/POS/payroll access, or private customer lists",
        ],
        "exact_manual_delivery_steps": [
            {
                "step": 1,
                "name": "intake boundary check",
                "owner_action": "Confirm samples are sanitized and the work is manual review-only.",
                "output": "accepted sample set or blocker list",
            },
            {
                "step": 2,
                "name": "lead-source map",
                "owner_action": "List lead sources, current owner check routine, and known failure points.",
                "output": "lead-source and leak map",
            },
            {
                "step": 3,
                "name": "attention queue draft",
                "owner_action": "Convert sanitized samples into status, priority, stale-lead, and next-action rows.",
                "output": "daily owner attention queue draft",
            },
            {
                "step": 4,
                "name": "script pack draft",
                "owner_action": "Draft callback, quote follow-up, appointment reminder, and review/referral wording.",
                "output": "human-approval-only message/script pack",
            },
            {
                "step": 5,
                "name": "QA and stop-line review",
                "owner_action": "Check every row for private data, unsupported claims, outreach implication, and credential/system access risk.",
                "output": "QA-cleared internal packet or blocked-item list",
            },
            {
                "step": 6,
                "name": "owner recap",
                "owner_action": "Summarize what changed, what remains manual, what is blocked, and what a future automation phase would require.",
                "output": "pilot recap and next-action plan",
            },
        ],
        "price_and_pilot_scope_assumptions": {
            "status": "draft_assumption_only",
            "pilot_shape": "fixed-scope manual sprint using sanitized samples only",
            "suggested_duration": "3 to 5 business days for a narrow first pass",
            "suggested_price_range_usd": "$500 to $1,500 for an initial manual pilot, subject to owner review and scope discipline",
            "included_scope_limit": "one business, one lead-rescue workflow family, one sanitized sample set, one recap packet",
            "excluded_from_price": [
                "live CRM, phone, email, ad, POS, payment, payroll, or automation platform implementation",
                "customer outreach or message sending",
                "custom integrations",
                "legal, compliance, security, revenue, or ROI guarantees",
                "ongoing managed service unless separately scoped later",
            ],
            "pricing_note": "This is a business-model assumption for PM review, not validated market pricing or a customer promise.",
        },
        "hard_stop_lines": [
            "no real customer identity or private customer data before a separate intake/privacy/security gate",
            "no customer-data retention unless explicitly approved in a future customer-data policy",
            "no passwords, API keys, CRM, phone, email, ad, payment, POS, payroll, or automation-platform credentials",
            "no outbound calls, texts, emails, social posts, review requests, or lead messages",
            "no writeback or implementation inside customer systems",
            "no public launch or external client portal exposure from the current cockpit",
            "no guaranteed revenue, ROI, conversion-rate, legal, compliance, or security readiness claims",
            "no subscription spend, platform purchase, or tool change without separate owner approval",
            "no inference that Randall approved a real client delivery, outreach, or system change",
        ],
        "proof_artifacts": [
            rel(SCENARIO_LIBRARY_JSON),
            rel(CUSTOMER_PREVIEW_JSON),
            rel(CUSTOMER_PREVIEW_MD),
            rel(CUSTOMER_PREVIEW_VALIDATION_JSON),
            rel(PILOT_DECISION_PACKET_JSON),
            rel(AUTOMATION_BLUEPRINTS_JSON),
            rel(AUTOMATION_BLUEPRINTS_VALIDATION_JSON),
        ],
        "next_pm_action": "Use this packet to decide whether to prepare an owner-facing pilot offer sheet, still without real customer data, outreach, credentials, external delivery, or cockpit runtime.",
        "authority_boundary": AUTHORITY_FALSE_FLAGS,
        "validation": {"status": "ok", "errors": [], "warnings": []},
    }


def render_lead_rescue_service_packet_markdown(packet: dict[str, Any]) -> str:
    lines = [
        f"# {packet['offer_name']}",
        "",
        f"Status: {packet['status']} / {packet['service_posture']}",
        "",
        "## Summary",
        packet["plain_language_summary"],
        "",
        "## Customer Fit",
    ]
    lines.extend(f"- {item}" for item in packet["customer_fit"])
    lines.extend(["", "## What The Customer Gets"])
    for item in packet["what_customer_gets"]:
        lines.append(f"- {item['deliverable']}: {item['description']}")
    lines.extend(["", "## What We Need From Them"])
    lines.extend(f"- {item}" for item in packet["what_we_need_from_customer"])
    lines.extend(["", "## Exact Manual Delivery Steps"])
    for item in packet["exact_manual_delivery_steps"]:
        lines.append(f"{item['step']}. {item['name']}: {item['owner_action']} Output: {item['output']}.")
    pricing = packet["price_and_pilot_scope_assumptions"]
    lines.extend([
        "",
        "## Price And Pilot Scope Assumptions",
        f"- Status: {pricing['status']}",
        f"- Pilot shape: {pricing['pilot_shape']}",
        f"- Suggested duration: {pricing['suggested_duration']}",
        f"- Suggested price range: {pricing['suggested_price_range_usd']}",
        f"- Included scope limit: {pricing['included_scope_limit']}",
        f"- Pricing note: {pricing['pricing_note']}",
        "",
        "Excluded from price:",
    ])
    lines.extend(f"- {item}" for item in pricing["excluded_from_price"])
    lines.extend(["", "## Hard Stop Lines"])
    lines.extend(f"- {item}" for item in packet["hard_stop_lines"])
    lines.extend(["", "## Proof Artifacts"])
    lines.extend(f"- {item}" for item in packet["proof_artifacts"])
    lines.extend(["", "Authority: review-only; no real customer data, credentials, outreach, external delivery, customer-system implementation, guaranteed ROI, or owner approval inference."])
    return "\n".join(lines) + "\n"


def validate_lead_rescue_service_packet(packet: dict[str, Any], rendered_text: str) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    if packet.get("status") != "review_ready":
        errors.append("service_packet_status_not_review_ready")
    if packet.get("authority_boundary") != AUTHORITY_FALSE_FLAGS:
        errors.append("service_packet_authority_boundary_changed")
    required_sections = [
        "what_customer_gets",
        "what_we_need_from_customer",
        "exact_manual_delivery_steps",
        "price_and_pilot_scope_assumptions",
        "hard_stop_lines",
    ]
    for section in required_sections:
        if not packet.get(section):
            errors.append(f"section_missing:{section}")
    pricing = packet.get("price_and_pilot_scope_assumptions", {})
    pricing_note = " ".join(str(value) for value in pricing.values()).lower()
    if "assumption" not in pricing_note and "draft" not in pricing_note:
        errors.append("pricing_not_marked_as_assumption")
    stop_text = " ".join(packet.get("hard_stop_lines", [])).lower()
    for phrase in (
        "no real customer identity",
        "no passwords",
        "no outbound",
        "no writeback",
        "no public launch",
        "no guaranteed revenue",
        "no inference",
    ):
        if phrase not in stop_text:
            errors.append(f"hard_stop_line_missing:{phrase}")
    rendered_lower = rendered_text.lower()
    forbidden_claims = [
        "guaranteed revenue lift",
        "guaranteed conversion",
        "we guarantee",
        "roi is guaranteed",
        "revenue is guaranteed",
        "will increase revenue",
        "compliance ready",
        "security ready",
        "we will send",
        "connect your crm",
        "connect your phone",
        "connect your email",
    ]
    for claim in forbidden_claims:
        if claim in rendered_lower:
            errors.append(f"forbidden_claim_present:{claim}")
    return {
        "schema": "veritas.wf75_smb_lead_rescue_service_packet_validation.v1",
        "generated_at_utc": packet.get("generated_at_utc"),
        "status": "ok" if not errors else "blocked",
        "validated_artifacts": [rel(LEAD_RESCUE_SERVICE_PACKET_JSON), rel(LEAD_RESCUE_SERVICE_PACKET_MD)],
        "errors": errors,
        "warnings": warnings,
        "authority_boundary": AUTHORITY_FALSE_FLAGS,
        "validation": {"status": "ok" if not errors else "error", "errors": errors, "warnings": warnings},
    }


def build_offer_icp_packet(generated_at: str) -> dict[str, Any]:
    return {
        "schema": "veritas.wf79_smb_offer_icp_packet.v1",
        "generated_at_utc": generated_at,
        "status": "ready",
        "workflow_id": "WF79-SMB",
        "positioning": {
            "category": "SMB lead and marketing follow-up operating system",
            "not_category": "generic marketing agency",
            "plain_language_offer": "We install a simple lead and follow-up operating system so marketing stops leaking through missed calls, stale leads, buried forms, and inconsistent follow-up.",
            "offer_ladder": [
                "Lead Rescue Sprint",
                "Marketing Follow-Up Engine",
                "Monthly Lead + Marketing Ops Packet",
            ],
            "core_promise": "clarity, next actions, and follow-up discipline",
            "disallowed_promises": [
                "guaranteed revenue",
                "guaranteed ROI",
                "compliance readiness",
                "security readiness",
                "automatic customer outreach",
                "full-service ad management",
            ],
        },
        "icp": {
            "best_fit": [
                "local service businesses with inbound calls, web forms, quote requests, and appointment workflows",
                "owner-operated teams using spreadsheets, inboxes, calendars, or lightweight CRMs",
                "businesses with enough leads to feel follow-up pain but not enough process discipline to see leakage clearly",
            ],
            "starting_verticals": ["HVAC/plumbing/electrical", "cleaning/home services", "auto repair", "med spa", "small professional services"],
            "pain_signals": [
                "missed calls do not reliably become callbacks",
                "website forms sit in inboxes",
                "quotes receive one attempt then go stale",
                "review/referral asks happen randomly",
                "owner lacks a daily list of who needs attention",
            ],
            "disqualifiers": [
                "expects guaranteed revenue lift",
                "requires immediate ad account, CRM, phone, or email access",
                "wants us to send customer communications without an approval gate",
                "will not provide sanitized samples or workflow descriptions",
                "needs legal/compliance/security certification claims",
            ],
        },
        "pricing_hypotheses": {
            "status": "assumption_only_not_customer_promise",
            "lead_rescue_sprint": "$750-$2,500 setup depending on sample volume and workflow complexity",
            "marketing_follow_up_engine": "$1,500-$5,000 setup after manual packet proves fit",
            "monthly_ops_packet": "$250-$1,000/month for review-only recap, queue cleanup, and improvement recommendations",
            "pricing_stop_line": "Do not publish, quote, invoice, or promise pricing until Randall approves a specific pilot scope.",
        },
        "authority_boundary": AUTHORITY_FALSE_FLAGS,
        "validation": {"status": "ok", "errors": [], "warnings": []},
    }


def render_offer_icp_markdown(packet: dict[str, Any]) -> str:
    lines = [
        "# SMB Workflow Clarity / Marketing Ops Automation Offer",
        "",
        f"Status: {packet['status']}",
        "",
        "## Positioning",
        packet["positioning"]["plain_language_offer"],
        "",
        f"Category: {packet['positioning']['category']}",
        f"Not category: {packet['positioning']['not_category']}",
        "",
        "## Offer Ladder",
    ]
    lines.extend(f"- {item}" for item in packet["positioning"]["offer_ladder"])
    lines.extend(["", "## Best-Fit ICP"])
    lines.extend(f"- {item}" for item in packet["icp"]["best_fit"])
    lines.extend(["", "## Pain Signals"])
    lines.extend(f"- {item}" for item in packet["icp"]["pain_signals"])
    lines.extend(["", "## Disqualifiers"])
    lines.extend(f"- {item}" for item in packet["icp"]["disqualifiers"])
    lines.extend(["", "## Pricing Hypotheses"])
    for key, value in packet["pricing_hypotheses"].items():
        lines.append(f"- {key}: {value}")
    lines.extend(["", "Boundary: review-only; no real customer data, outreach, credentials, customer-system access, external delivery, spending, ROI guarantee, or owner approval inference."])
    return "\n".join(lines) + "\n"


def build_demo_packets(generated_at: str, offer_packet: dict[str, Any]) -> dict[str, Any]:
    common_stop_lines = [
        "fake or sanitized sample data only",
        "no real customer identity, phone, email, address, order ID, or private business data",
        "no outbound calls, texts, emails, posts, ads, review requests, or lead messages",
        "no CRM, phone, email, ad, website, payment, POS, payroll, or automation-platform credential access",
        "no customer-system writeback or implementation",
        "no guaranteed revenue, ROI, legal, compliance, or security claim",
    ]
    demos = [
        {
            "demo_id": "demo-missed-call-rescue-hvac-v1",
            "title": "Missed-call rescue for HVAC service business",
            "classification": "fake_scenario_internal_demo",
            "sample_fixture": {
                "business_type": "HVAC service company",
                "lead_sources": ["missed calls", "voicemails", "after-hours callbacks"],
                "sample_rows": [
                    {"sample_id": "CALL-001", "time": "08:12", "summary": "No-cool emergency, service area likely valid", "status": "missed"},
                    {"sample_id": "CALL-002", "time": "11:44", "summary": "maintenance quote request, non-urgent", "status": "voicemail"},
                ],
            },
            "manual_packet_summary": {
                "workflow_map": "missed call -> sanitize -> classify reason -> priority -> owner callback queue",
                "failure_mode": "calls are returned late or not at all",
                "next_best_manual_step": "stage a callback queue with urgency and script draft",
                "success_criteria": "owner can identify the first three callbacks without searching phone logs",
            },
            "automation_blueprint": {
                "trigger": "future phone-system missed-call event or manual CSV import",
                "dedupe_key": "sample_call_id",
                "human_review_checkpoint": "operator approves priority and callback script before any use",
                "tool_fit": "Make or n8n for branching; Zapier for simpler phone-to-sheet workflows after credential gate",
                "activation_state": "design_only",
            },
            "stop_lines": common_stop_lines,
        },
        {
            "demo_id": "demo-website-form-follow-up-cleaning-v1",
            "title": "Website form follow-up for cleaning company",
            "classification": "fake_scenario_internal_demo",
            "sample_fixture": {
                "business_type": "residential cleaning company",
                "lead_sources": ["website forms", "email inbox", "calendar requests"],
                "sample_rows": [
                    {"sample_id": "FORM-101", "age_hours": 3, "summary": "recurring cleaning inquiry", "status": "new"},
                    {"sample_id": "FORM-102", "age_hours": 28, "summary": "move-out clean quote request", "status": "stale"},
                ],
            },
            "manual_packet_summary": {
                "workflow_map": "form submit -> source tag -> quote type -> stale threshold -> next-touch draft",
                "failure_mode": "forms sit in email and receive no second touch",
                "next_best_manual_step": "draft quote follow-up and assign owner due dates",
                "success_criteria": "owner sees stale forms and approved next-touch wording",
            },
            "automation_blueprint": {
                "trigger": "future form event or manual sanitized form export",
                "dedupe_key": "sample_form_id",
                "human_review_checkpoint": "operator approves all follow-up wording",
                "tool_fit": "Zapier for form-to-sheet; Make/n8n for quote-type branching after customer-system gate",
                "activation_state": "design_only",
            },
            "stop_lines": common_stop_lines,
        },
        {
            "demo_id": "demo-stale-lead-reactivation-auto-repair-v1",
            "title": "Stale-lead reactivation for auto repair shop",
            "classification": "fake_scenario_internal_demo",
            "sample_fixture": {
                "business_type": "auto repair shop",
                "lead_sources": ["quote requests", "appointment inquiries", "past no-response leads"],
                "sample_rows": [
                    {"sample_id": "QUOTE-201", "age_days": 6, "summary": "brake estimate, no response after first quote", "status": "stale_quote"},
                    {"sample_id": "QUOTE-202", "age_days": 14, "summary": "diagnostic inquiry, no appointment booked", "status": "stale_inquiry"},
                ],
            },
            "manual_packet_summary": {
                "workflow_map": "quote list -> stale threshold -> reason tag -> reactivation sequence draft -> owner review",
                "failure_mode": "quotes disappear after one contact attempt",
                "next_best_manual_step": "stage a reactivation list with human-approved message options",
                "success_criteria": "owner can see stale quotes and decide which to revive",
            },
            "automation_blueprint": {
                "trigger": "manual quote export or future CRM stale-stage event",
                "dedupe_key": "sample_quote_id",
                "human_review_checkpoint": "operator approves reactivation message and do-not-contact filters",
                "tool_fit": "manual-first; CRM/Zapier/Make only after explicit implementation gate",
                "activation_state": "design_only",
            },
            "stop_lines": common_stop_lines,
        },
    ]
    return {
        "schema": "veritas.wf79_smb_demo_packets.v1",
        "generated_at_utc": generated_at,
        "status": "ready",
        "source_offer": offer_packet["positioning"]["offer_ladder"],
        "demo_count": len(demos),
        "demos": demos,
        "authority_boundary": AUTHORITY_FALSE_FLAGS,
        "validation": {"status": "ok", "errors": [], "warnings": []},
    }


def render_demo_packets_markdown(packet: dict[str, Any]) -> str:
    lines = ["# WF79 SMB Demo Packets", "", f"Status: {packet['status']}", ""]
    for demo in packet["demos"]:
        lines.extend([
            f"## {demo['title']}",
            f"- Demo ID: {demo['demo_id']}",
            f"- Classification: {demo['classification']}",
            f"- Workflow map: {demo['manual_packet_summary']['workflow_map']}",
            f"- Failure mode: {demo['manual_packet_summary']['failure_mode']}",
            f"- Next manual step: {demo['manual_packet_summary']['next_best_manual_step']}",
            f"- Tool fit: {demo['automation_blueprint']['tool_fit']}",
            "",
            "Stop lines:",
        ])
        lines.extend(f"- {item}" for item in demo["stop_lines"])
        lines.append("")
    lines.append("Authority: fake/sanitized internal demos only; no real customer data, outreach, credentials, customer-system access, external delivery, or ROI guarantee.")
    return "\n".join(lines) + "\n"


def validate_demo_packets(packet: dict[str, Any], rendered_text: str) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    if packet.get("demo_count") != 3:
        errors.append("demo_count_not_3")
    if packet.get("authority_boundary") != AUTHORITY_FALSE_FLAGS:
        errors.append("authority_boundary_changed")
    required = ["fake or sanitized", "no real customer", "no outbound", "no CRM", "no customer-system", "no guaranteed revenue"]
    for demo in packet.get("demos", []):
        stop_text = " ".join(demo.get("stop_lines", [])).lower()
        for phrase in required:
            if phrase.lower() not in stop_text:
                errors.append(f"demo_stop_line_missing:{demo.get('demo_id')}:{phrase}")
        if demo.get("automation_blueprint", {}).get("activation_state") != "design_only":
            errors.append(f"demo_not_design_only:{demo.get('demo_id')}")
    for claim in ("will increase revenue", "guaranteed", "we will send", "connect your crm"):
        if claim in rendered_text.lower() and claim != "guaranteed":
            errors.append(f"forbidden_rendered_claim:{claim}")
    return {
        "schema": "veritas.wf79_smb_demo_packets_validation.v1",
        "generated_at_utc": packet.get("generated_at_utc"),
        "status": "ok" if not errors else "blocked",
        "validated_artifacts": [rel(DEMO_PACKETS_JSON), rel(DEMO_PACKETS_MD)],
        "errors": errors,
        "warnings": warnings,
        "authority_boundary": AUTHORITY_FALSE_FLAGS,
        "validation": {"status": "ok" if not errors else "error", "errors": errors, "warnings": warnings},
    }


def build_marketing_ops_blueprints(generated_at: str) -> dict[str, Any]:
    stop_lines = [
        "design-only until explicit customer/pilot gate",
        "no real customer data",
        "no customer data retention",
        "no credential or account access",
        "no outbound messages, ads, review requests, or posts",
        "no customer-system writeback",
        "no guaranteed revenue, ROI, legal, compliance, security, or certification claim",
    ]
    blueprints = [
        ("marketing-source-tagging-v1", "Lead source tagging", "new lead sample", "sample_lead_id", "tag lead source, campaign source, urgency, and owner"),
        ("marketing-nurture-sequence-v1", "Nurture sequence draft", "stale or future lead sample", "sample_lead_id:sequence_stage", "stage follow-up copy for human approval"),
        ("marketing-review-request-v1", "Review request workflow draft", "completed-job sample", "sample_job_id", "stage review ask timing and wording for approval only"),
        ("marketing-referral-ask-v1", "Referral ask workflow draft", "satisfied-customer sample", "sample_customer_hash", "stage referral ask wording and timing for approval only"),
        ("marketing-monthly-ops-packet-v1", "Monthly lead and marketing ops packet", "monthly sanitized counts", "sample_month:business_type", "summarize lead sources, stale leads, follow-up debt, and next tests"),
    ]
    rows = []
    for blueprint_id, title, trigger_source, dedupe_key, purpose in blueprints:
        rows.append(
            {
                "blueprint_id": blueprint_id,
                "title": title,
                "purpose": purpose,
                "trigger": {"type": "manual_sample_or_future_event", "source": trigger_source},
                "input_contract": {
                    "required_fields": ["sample_id", "source", "status", "created_at"],
                    "dedup_key": dedupe_key,
                    "validation_rules": ["no private identifiers", "status recognized", "operator approval required"],
                },
                "ordered_steps": [
                    "normalize sanitized input",
                    "classify source/status",
                    "draft recommendation or message",
                    "stage internal review row",
                    "write audit event",
                ],
                "human_review_checkpoint": "Operator approval required before any customer-facing action.",
                "retry_policy": {"max_attempts": 2, "backoff": "fixed_10_minutes", "final_state": "manual_review"},
                "failure_fallback": "Stage blocker row; do not send, post, write back, or trigger external systems.",
                "audit_log": "generic-service-state.sqlite:qa_events",
                "tool_candidate": "manual-first; Zapier/Make/n8n/custom Node only after implementation gate",
                "activation_state": "design_only",
                "stop_lines": stop_lines,
            }
        )
    return {
        "schema": "veritas.wf79_smb_marketing_ops_blueprints.v1",
        "generated_at_utc": generated_at,
        "status": "ready",
        "blueprint_count": len(rows),
        "blueprints": rows,
        "authority_boundary": AUTHORITY_FALSE_FLAGS,
        "validation": {"status": "ok", "errors": [], "warnings": []},
    }


def validate_marketing_ops_blueprints(packet: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    if packet.get("blueprint_count", 0) < 5:
        errors.append("marketing_ops_blueprint_count_below_5")
    if packet.get("authority_boundary") != AUTHORITY_FALSE_FLAGS:
        errors.append("authority_boundary_changed")
    for item in packet.get("blueprints", []):
        blueprint_id = item.get("blueprint_id", "unknown")
        if item.get("activation_state") != "design_only":
            errors.append(f"activation_state_not_design_only:{blueprint_id}")
        for key in ("input_contract", "human_review_checkpoint", "retry_policy", "failure_fallback", "audit_log"):
            if not item.get(key):
                errors.append(f"missing_{key}:{blueprint_id}")
        stop_text = " ".join(item.get("stop_lines", [])).lower()
        for phrase in ("no real customer data", "no credential", "no outbound", "no customer-system", "no guaranteed revenue"):
            if phrase not in stop_text:
                errors.append(f"stop_line_missing:{blueprint_id}:{phrase}")
    return {
        "schema": "veritas.wf79_smb_marketing_ops_blueprints_validation.v1",
        "generated_at_utc": packet.get("generated_at_utc"),
        "status": "ok" if not errors else "blocked",
        "validated_artifacts": [rel(MARKETING_OPS_BLUEPRINTS_JSON)],
        "errors": errors,
        "warnings": warnings,
        "authority_boundary": AUTHORITY_FALSE_FLAGS,
        "validation": {"status": "ok" if not errors else "error", "errors": errors, "warnings": warnings},
    }


def build_sales_practice_packet(generated_at: str, offer_packet: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema": "veritas.wf79_smb_sales_practice_packet.v1",
        "generated_at_utc": generated_at,
        "status": "ready",
        "practice_mode": "internal_randall_training_only",
        "ninety_second_offer": (
            "We help small service businesses stop losing leads in the handoff between calls, forms, quotes, and follow-up. "
            "First we map where leads enter, where they stall, and who owns the next touch. Then we give you a simple owner attention queue, "
            "follow-up drafts for human approval, and a practical automation plan. We start with sanitized samples and do not need your credentials for the first review."
        ),
        "discovery_questions": [
            "Where do new leads come in today?",
            "Which leads most often get missed or delayed?",
            "Who owns callbacks and follow-up right now?",
            "How do you know a quote has gone stale?",
            "What tools already hold your leads or appointments?",
            "What customer communication should never be automated?",
            "What would make a daily owner attention list useful?",
            "Can we start with sanitized samples only?",
        ],
        "objection_handling": [
            {"objection": "We already have a CRM.", "response": "Good. The first pass checks whether the CRM is actually producing next actions, not whether you own software."},
            {"objection": "Can you just run our marketing?", "response": "Not first. We start by fixing lead leakage and follow-up discipline so marketing spend has somewhere clean to land."},
            {"objection": "Can you guarantee more revenue?", "response": "No. We can identify leakage, improve follow-up discipline, and create a measurable process. Revenue claims would be dishonest before proof."},
            {"objection": "Do you need logins?", "response": "No for the first review. Sanitized samples and a workflow description are enough."},
        ],
        "pilot_checklist": [
            "scope one business and one workflow family",
            "use fake or sanitized samples only",
            "confirm no credentials or system access",
            "confirm no external sending",
            "deliver attention queue, scripts, blueprint, and recap",
            "review whether a real pilot gate is worth opening",
        ],
        "authority_boundary": AUTHORITY_FALSE_FLAGS,
        "validation": {"status": "ok", "errors": [], "warnings": []},
    }


def render_sales_practice_markdown(packet: dict[str, Any]) -> str:
    lines = ["# WF79 SMB Sales Practice Packet", "", f"Status: {packet['status']}", "", "## 90-Second Offer", packet["ninety_second_offer"], "", "## Discovery Questions"]
    lines.extend(f"- {item}" for item in packet["discovery_questions"])
    lines.extend(["", "## Objection Handling"])
    for row in packet["objection_handling"]:
        lines.append(f"- {row['objection']} -> {row['response']}")
    lines.extend(["", "## Pilot Checklist"])
    lines.extend(f"- {item}" for item in packet["pilot_checklist"])
    lines.extend(["", "Boundary: internal training only; no outreach, external delivery, real customer data, credentials, or ROI guarantee."])
    return "\n".join(lines) + "\n"


def build_outreach_kit(generated_at: str, offer_packet: dict[str, Any], sales_practice: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema": "veritas.wf79_smb_outreach_kit.v1",
        "generated_at_utc": generated_at,
        "status": "ready",
        "posture": "drafts_only_no_send_authority",
        "source_offer_category": offer_packet["positioning"]["category"],
        "conversation_assets": {
            "thirty_second_opener": (
                "We help local service businesses see whether calls, forms, quotes, and follow-ups are turning into clean next actions, "
                "or whether leads are leaking before more marketing spend can work."
            ),
            "ninety_second_offer": sales_practice["ninety_second_offer"],
            "warm_intro_dm": (
                "I am building a small-business lead-flow review service. The first pass does not need your logins or customer data: "
                "we review a sanitized workflow description and show where calls, forms, quotes, or follow-up may be getting stuck. "
                "Would it be useful to look at a sanitized sample?"
            ),
            "in_person_opener": (
                "Quick question: when a new lead comes in by phone, form, or quote request, do you have a clear daily list of who needs the next touch?"
            ),
            "follow_up_message": (
                "Thanks for the conversation. The safe first step would be a sanitized lead-flow review: no credentials, no customer-system access, "
                "and no message sending. We map the workflow, flag leakage or source-quality issues, and give you a practical next-action packet."
            ),
        },
        "objection_responses": [
            {
                "objection": "That is not my problem; I need more leads.",
                "response": (
                    "More leads may be the right goal. I would first check whether the leads you already have are being handled cleanly. "
                    "If the handoff is leaking, more marketing spend can hide the real issue. If handling is tight, we shift to source quality and growth experiments."
                ),
            },
            {
                "objection": "Our follow-up is already tight.",
                "response": (
                    "Good. Then we should not sell Lead Rescue as the problem. The next useful review is source quality, conversion math, referrals, reviews, "
                    "reactivation, and which growth channel is worth scaling."
                ),
            },
            {
                "objection": "Can you run our marketing?",
                "response": (
                    "Not first. The first offer is a marketing operations clarity pass: lead sources, follow-up discipline, conversion math, and the next safe growth experiment."
                ),
            },
            {
                "objection": "Can you guarantee revenue?",
                "response": "No. We can identify leakage, improve operating discipline, and create measurable follow-up and source-quality checks. Revenue promises would be dishonest before proof.",
            },
        ],
        "first_ask": "Request a sanitized workflow description, fake sample, or owner walkthrough; do not request credentials or real customer exports.",
        "authority_boundary": AUTHORITY_FALSE_FLAGS,
        "validation": {"status": "ok", "errors": [], "warnings": []},
    }


def render_outreach_kit_markdown(packet: dict[str, Any]) -> str:
    lines = ["# WF79 SMB Outreach Kit", "", f"Status: {packet['status']}", "", "## Conversation Assets"]
    for key, value in packet["conversation_assets"].items():
        lines.extend([f"### {key.replace('_', ' ').title()}", value, ""])
    lines.append("## Objection Responses")
    for row in packet["objection_responses"]:
        lines.append(f"- {row['objection']} -> {row['response']}")
    lines.extend(["", "## First Ask", packet["first_ask"], "", "Boundary: drafts only; no customer data, no outreach, no credentials, no external delivery, no sending, no ad action, no spending, no ROI guarantee, and no owner approval inference."])
    return "\n".join(lines) + "\n"


def build_pilot_scope_intake(generated_at: str) -> dict[str, Any]:
    return {
        "schema": "veritas.wf79_smb_pilot_scope_intake.v1",
        "generated_at_utc": generated_at,
        "status": "ready",
        "pilot_posture": "approval_gated_manual_review_candidate",
        "pilot_shape": {
            "name": "Sanitized Lead + Marketing Ops Review",
            "duration": "fixed-scope sprint; exact duration requires Randall approval",
            "business_scope": "one business, one workflow family, one sanitized lead-flow sample",
            "deliverables": [
                "lead-flow map",
                "owner attention queue",
                "source-quality and conversion-math observations",
                "human-approved follow-up draft examples",
                "automation blueprint with activation blocked until later approval",
                "recap with next recommended growth or follow-up experiment",
            ],
        },
        "safe_intake_questions": [
            "Where do leads come from today?",
            "Which source produces the best customers?",
            "What happens after a missed call, web form, quote request, or appointment request?",
            "Who owns the next touch?",
            "How do you know a lead or quote has gone stale?",
            "What communication should never be automated?",
            "Can the first review use sanitized samples only?",
        ],
        "allowed_inputs": [
            "sanitized workflow description",
            "fictional or sample rows",
            "manual owner walkthrough",
            "non-sensitive process screenshots only after separate approval",
        ],
        "blocked_inputs": [
            "real customer identity or contact data",
            "CRM, phone, email, ad, payment, POS, payroll, or automation credentials",
            "customer-system exports with private data",
            "permission to send messages or run ads",
            "legal, compliance, or security certification claims",
        ],
        "exit_decision": "After the packet, decide whether the business needs Lead Rescue, Marketing Follow-Up Engine, Growth Clarity, or no-fit.",
        "authority_boundary": AUTHORITY_FALSE_FLAGS,
        "validation": {"status": "ok", "errors": [], "warnings": []},
    }


def render_pilot_scope_intake_markdown(packet: dict[str, Any]) -> str:
    lines = ["# WF79 SMB Pilot Scope And Intake", "", f"Status: {packet['status']}", "", "## Pilot Shape"]
    for key, value in packet["pilot_shape"].items():
        if isinstance(value, list):
            lines.append(f"- {key}:")
            lines.extend(f"  - {item}" for item in value)
        else:
            lines.append(f"- {key}: {value}")
    lines.extend(["", "## Safe Intake Questions"])
    lines.extend(f"- {item}" for item in packet["safe_intake_questions"])
    lines.extend(["", "## Allowed Inputs"])
    lines.extend(f"- {item}" for item in packet["allowed_inputs"])
    lines.extend(["", "## Blocked Inputs"])
    lines.extend(f"- {item}" for item in packet["blocked_inputs"])
    lines.extend(["", "## Exit Decision", packet["exit_decision"], "", "Boundary: approval-gated pilot planning only; no customer data, no outreach, no credentials, no external delivery, no sending, no implementation, no ad action, no spending, and no ROI guarantee."])
    return "\n".join(lines) + "\n"


def build_vertical_icp_targeting(generated_at: str) -> dict[str, Any]:
    verticals = [
        {
            "vertical": "HVAC / plumbing / electrical",
            "priority": 1,
            "why_fit": "high-value urgent inbound calls, quote follow-up, after-hours leakage, clear callback value",
            "pain_signals": ["missed calls", "after-hours requests", "stale quotes", "unclear callback ownership"],
            "best_opener": "How do you make sure missed calls and quote requests become a next-touch list before the day gets away from you?",
            "offer_path": "Lead Rescue Sprint first",
        },
        {
            "vertical": "auto repair",
            "priority": 2,
            "why_fit": "quote follow-up, diagnostic inquiries, appointment no-shows, repeat service opportunities",
            "pain_signals": ["stale estimates", "no second touch", "appointment gaps", "unclear source quality"],
            "best_opener": "When a quote does not book, do you have a clean way to know who should get a follow-up and when?",
            "offer_path": "Lead Rescue Sprint or Growth Clarity",
        },
        {
            "vertical": "cleaning / home services",
            "priority": 3,
            "why_fit": "form leads, recurring-service conversion, quote timing, review/referral loops",
            "pain_signals": ["forms in inbox", "recurring inquiries not tagged", "slow quote response", "random review asks"],
            "best_opener": "Do web forms and quote requests turn into an owner attention list, or do they live in the inbox?",
            "offer_path": "Marketing Follow-Up Engine",
        },
        {
            "vertical": "med spa / elective services",
            "priority": 4,
            "why_fit": "inquiry routing, treatment-interest branching, consult follow-up, reactivation",
            "pain_signals": ["consult requests stall", "interest tags missing", "reactivation is random", "manual routing inconsistency"],
            "best_opener": "Can you see which inquiries need a consult follow-up versus which need a different next touch?",
            "offer_path": "Marketing Follow-Up Engine",
        },
        {
            "vertical": "small professional services",
            "priority": 5,
            "why_fit": "consult intake, referral quality, follow-up discipline, longer sales cycles",
            "pain_signals": ["referrals not tracked", "consult leads age out", "next step unclear", "no source-quality view"],
            "best_opener": "When a referral or consult inquiry arrives, who owns the next touch and how is it tracked?",
            "offer_path": "Growth Clarity / Monthly Ops Packet",
        },
    ]
    return {
        "schema": "veritas.wf79_smb_vertical_icp_targeting.v1",
        "generated_at_utc": generated_at,
        "status": "ready",
        "ranked_verticals": verticals,
        "universal_disqualifiers": [
            "expects guaranteed lead volume or revenue",
            "requires immediate credential access",
            "wants message sending or ad execution in the first pass",
            "will not use sanitized samples",
            "needs regulated compliance/security certification claims",
        ],
        "authority_boundary": AUTHORITY_FALSE_FLAGS,
        "validation": {"status": "ok", "errors": [], "warnings": []},
    }


def render_vertical_icp_targeting_markdown(packet: dict[str, Any]) -> str:
    lines = ["# WF79 SMB Vertical ICP Targeting", "", f"Status: {packet['status']}", ""]
    for row in packet["ranked_verticals"]:
        lines.extend([
            f"## {row['priority']}. {row['vertical']}",
            f"- Why fit: {row['why_fit']}",
            f"- Best opener: {row['best_opener']}",
            f"- Offer path: {row['offer_path']}",
            "- Pain signals:",
        ])
        lines.extend(f"  - {item}" for item in row["pain_signals"])
        lines.append("")
    lines.append("## Universal Disqualifiers")
    lines.extend(f"- {item}" for item in packet["universal_disqualifiers"])
    lines.extend(["", "Boundary: targeting research only; no customer data, no outreach, no credentials, no external delivery, no scraping, no ad action, no spending, and no ROI guarantee."])
    return "\n".join(lines) + "\n"


def build_demo_polish_packet(generated_at: str, demo_packets: dict[str, Any]) -> dict[str, Any]:
    polished = [
        {
            "demo_id": "polished-lead-rescue-hvac-v1",
            "source_demo_id": "demo-missed-call-rescue-hvac-v1",
            "use_case": "business has follow-up leakage",
            "one_line_story": "A service owner can see the first callbacks to make instead of searching call logs.",
            "show_and_tell_sections": ["lead sources", "leakage map", "owner attention queue", "callback script draft", "automation blueprint"],
            "safe_close": "This is a sample packet using fake/sanitized data; no messages are sent and no systems are connected.",
        },
        {
            "demo_id": "polished-more-leads-marketing-ops-v1",
            "source_demo_id": "demo-website-form-follow-up-cleaning-v1",
            "use_case": "business says it needs more leads",
            "one_line_story": "Before buying more traffic, the owner sees whether current sources convert and where forms or quotes stall.",
            "show_and_tell_sections": ["source-quality snapshot", "conversion-math checklist", "stale opportunity view", "campaign readiness notes", "next growth experiment"],
            "safe_close": "This supports a marketing decision; it does not promise lead volume or revenue.",
        },
        {
            "demo_id": "polished-growth-clarity-tight-follow-up-v1",
            "source_demo_id": "demo-stale-lead-reactivation-auto-repair-v1",
            "use_case": "business has tight follow-up already",
            "one_line_story": "If follow-up is strong, the packet shifts to source quality, referral/review loops, reactivation, and scaling discipline.",
            "show_and_tell_sections": ["lead source breakdown", "quote close-rate questions", "review/referral moments", "reactivation candidates", "monthly ops scorecard"],
            "safe_close": "This is growth clarity and operations review, not ad management or customer-system implementation.",
        },
    ]
    return {
        "schema": "veritas.wf79_smb_demo_polish_packet.v1",
        "generated_at_utc": generated_at,
        "status": "ready",
        "source_demo_count": demo_packets.get("demo_count"),
        "polished_demo_count": len(polished),
        "polished_demos": polished,
        "authority_boundary": AUTHORITY_FALSE_FLAGS,
        "validation": {"status": "ok", "errors": [], "warnings": []},
    }


def render_demo_polish_packet_markdown(packet: dict[str, Any]) -> str:
    lines = ["# WF79 SMB Demo Polish Packet", "", f"Status: {packet['status']}", ""]
    for row in packet["polished_demos"]:
        lines.extend([
            f"## {row['demo_id']}",
            f"- Use case: {row['use_case']}",
            f"- Story: {row['one_line_story']}",
            "- Show-and-tell sections:",
        ])
        lines.extend(f"  - {item}" for item in row["show_and_tell_sections"])
        lines.extend([f"- Safe close: {row['safe_close']}", ""])
    lines.append("Boundary: fake/sanitized demo polish only; no customer data, no outreach, no credentials, no external delivery, no implementation, no ad action, no spending, and no ROI guarantee.")
    return "\n".join(lines) + "\n"


def validate_outreach_prep(
    outreach_kit: dict[str, Any],
    pilot_scope: dict[str, Any],
    vertical_targeting: dict[str, Any],
    demo_polish: dict[str, Any],
    rendered_texts: list[str],
) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    packets = [outreach_kit, pilot_scope, vertical_targeting, demo_polish]
    for packet in packets:
        if packet.get("status") != "ready":
            errors.append(f"packet_not_ready:{packet.get('schema')}")
        if packet.get("authority_boundary") != AUTHORITY_FALSE_FLAGS:
            errors.append(f"authority_boundary_changed:{packet.get('schema')}")
    combined = "\n".join(rendered_texts).lower()
    required_phrases = [
        "no customer data",
        "no outreach",
        "no credentials",
        "no external delivery",
        "no roi guarantee",
    ]
    for phrase in required_phrases:
        if phrase not in combined:
            errors.append(f"outreach_prep_stop_line_missing:{phrase}")
    forbidden_claims = [
        "guarantee more leads",
        "guaranteed revenue",
        "we will send messages",
        "connect your crm",
        "run your ads",
    ]
    for claim in forbidden_claims:
        if claim in combined:
            errors.append(f"forbidden_outreach_claim_present:{claim}")
    return {
        "schema": "veritas.wf79_smb_outreach_prep_validation.v1",
        "generated_at_utc": outreach_kit.get("generated_at_utc"),
        "status": "ok" if not errors else "blocked",
        "validated_artifacts": [
            rel(OUTREACH_KIT_JSON),
            rel(PILOT_SCOPE_INTAKE_JSON),
            rel(VERTICAL_ICP_TARGETING_JSON),
            rel(DEMO_POLISH_PACKET_JSON),
        ],
        "errors": errors,
        "warnings": warnings,
        "authority_boundary": AUTHORITY_FALSE_FLAGS,
        "validation": {"status": "ok" if not errors else "error", "errors": errors, "warnings": warnings},
    }


def build_pilot_readiness_packet(
    generated_at: str,
    offer_packet: dict[str, Any],
    pilot_scope: dict[str, Any],
    outreach_kit: dict[str, Any],
) -> dict[str, Any]:
    return {
        "schema": "veritas.wf79_smb_pilot_readiness_packet.v1",
        "generated_at_utc": generated_at,
        "status": "ready",
        "posture": "internal_owner_review_before_any_real_outreach_or_pilot",
        "one_page_offer": {
            "headline": "Sanitized Lead + Marketing Ops Review",
            "plain_language_offer": offer_packet["positioning"]["plain_language_offer"],
            "first_safe_ask": outreach_kit["first_ask"],
            "best_fit": offer_packet["icp"]["best_fit"],
            "deliverables": pilot_scope["pilot_shape"]["deliverables"],
            "inputs_required": pilot_scope["allowed_inputs"],
            "blocked_inputs": pilot_scope["blocked_inputs"],
        },
        "success_criteria": [
            "business pain is mapped to Lead Rescue, Marketing Follow-Up Engine, Growth Clarity, or no-fit",
            "owner can see the next three manual actions without a new software purchase",
            "all sample data remains fake or sanitized",
            "no credential, sending, ad-spend, or system-implementation request is made",
            "pilot closeout identifies whether a real gated pilot conversation is worth approving",
        ],
        "pilot_closeout_checklist": [
            "confirm no real customer identity/contact data was used",
            "confirm no messages were sent and no systems were connected",
            "summarize lead-flow leakage or source-quality finding",
            "recommend one next experiment or mark no-fit",
            "capture unresolved stop-line or approval needs",
        ],
        "owner_decision_after_review": "Approve a manual no-credential sanitized pilot conversation path, revise the packet, or keep the lane internal.",
        "authority_boundary": AUTHORITY_FALSE_FLAGS,
        "validation": {"status": "ok", "errors": [], "warnings": []},
    }


def render_pilot_readiness_markdown(packet: dict[str, Any]) -> str:
    offer = packet["one_page_offer"]
    lines = ["# WF79 SMB Pilot Readiness Packet", "", f"Status: {packet['status']}", "", "## One-Page Pilot Offer"]
    lines.extend([
        f"- Headline: {offer['headline']}",
        f"- Offer: {offer['plain_language_offer']}",
        f"- First safe ask: {offer['first_safe_ask']}",
        "",
        "### Deliverables",
    ])
    lines.extend(f"- {item}" for item in offer["deliverables"])
    lines.extend(["", "### Inputs Required"])
    lines.extend(f"- {item}" for item in offer["inputs_required"])
    lines.extend(["", "### Blocked Inputs"])
    lines.extend(f"- {item}" for item in offer["blocked_inputs"])
    lines.extend(["", "## Success Criteria"])
    lines.extend(f"- {item}" for item in packet["success_criteria"])
    lines.extend(["", "## Pilot Closeout Checklist"])
    lines.extend(f"- {item}" for item in packet["pilot_closeout_checklist"])
    lines.extend(["", "## Owner Decision", packet["owner_decision_after_review"], "", "Boundary: internal pilot-readiness planning only; no customer data, no outreach, no credentials, no external delivery, no message sending, no ads/spend, no implementation, and no ROI guarantee."])
    return "\n".join(lines) + "\n"


def build_sales_conversation_drill(generated_at: str, outreach_kit: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema": "veritas.wf79_smb_sales_conversation_drill.v1",
        "generated_at_utc": generated_at,
        "status": "ready",
        "mode": "internal_randall_practice_only",
        "five_minute_roleplay": [
            {"minute": 0, "goal": "Open with the lead-flow question, not a tool pitch.", "script": outreach_kit["conversation_assets"]["in_person_opener"]},
            {"minute": 1, "goal": "Classify pain as leakage, more-leads, tight-follow-up, or no-fit.", "script": "Where do leads enter, where do they stall, and who owns the next touch?"},
            {"minute": 2, "goal": "Explain the safe first review.", "script": outreach_kit["conversation_assets"]["thirty_second_opener"]},
            {"minute": 3, "goal": "Handle the main objection without arguing.", "script": outreach_kit["objection_responses"][0]["response"]},
            {"minute": 4, "goal": "Close with a safe next step.", "script": outreach_kit["first_ask"]},
        ],
        "discovery_flow": [
            "lead source",
            "speed to first touch",
            "stale quote or lead definition",
            "owner of next action",
            "current tracking surface",
            "communications that must stay human",
            "sanitized sample availability",
        ],
        "bad_fit_exit_language": (
            "This probably is not the right first step if you need guaranteed lead volume, ad management, credential-based implementation, "
            "or someone to send customer messages for you. Our first step is a safe lead-flow review."
        ),
        "authority_boundary": AUTHORITY_FALSE_FLAGS,
        "validation": {"status": "ok", "errors": [], "warnings": []},
    }


def render_sales_conversation_drill_markdown(packet: dict[str, Any]) -> str:
    lines = ["# WF79 SMB Sales Conversation Drill", "", f"Status: {packet['status']}", "", "## Five-Minute Roleplay"]
    for row in packet["five_minute_roleplay"]:
        lines.append(f"- Minute {row['minute']}: {row['goal']} Script: {row['script']}")
    lines.extend(["", "## Discovery Flow"])
    lines.extend(f"- {item}" for item in packet["discovery_flow"])
    lines.extend(["", "## Bad-Fit Exit Language", packet["bad_fit_exit_language"], "", "Boundary: internal training only; no customer data, no outreach, no credentials, no external delivery, no sending, no ads/spend, no implementation, and no ROI guarantee."])
    return "\n".join(lines) + "\n"


def build_demo_selection_tree(generated_at: str, demo_polish: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema": "veritas.wf79_smb_demo_selection_tree.v1",
        "generated_at_utc": generated_at,
        "status": "ready",
        "decision_tree": [
            {
                "if_business_says": "We miss calls, forms, quotes, or follow-ups.",
                "classify_as": "follow_up_leakage",
                "use_demo_id": "polished-lead-rescue-hvac-v1",
                "show_sections": ["leakage map", "owner attention queue", "callback script draft"],
            },
            {
                "if_business_says": "That is not my problem; I need more leads.",
                "classify_as": "more_leads_or_source_quality",
                "use_demo_id": "polished-more-leads-marketing-ops-v1",
                "show_sections": ["source-quality snapshot", "conversion-math checklist", "campaign readiness notes"],
            },
            {
                "if_business_says": "Our follow-up is already tight.",
                "classify_as": "growth_clarity",
                "use_demo_id": "polished-growth-clarity-tight-follow-up-v1",
                "show_sections": ["lead source breakdown", "review/referral moments", "monthly ops scorecard"],
            },
            {
                "if_business_says": "We want you to run ads, send messages, or connect systems now.",
                "classify_as": "bad_fit_or_later_gate",
                "use_demo_id": None,
                "show_sections": ["boundary language", "pilot scope exclusions"],
            },
        ],
        "available_polished_demos": [row["demo_id"] for row in demo_polish["polished_demos"]],
        "authority_boundary": AUTHORITY_FALSE_FLAGS,
        "validation": {"status": "ok", "errors": [], "warnings": []},
    }


def render_demo_selection_tree_markdown(packet: dict[str, Any]) -> str:
    lines = ["# WF79 SMB Demo Selection Tree", "", f"Status: {packet['status']}", ""]
    for row in packet["decision_tree"]:
        lines.extend([
            f"## {row['classify_as']}",
            f"- If business says: {row['if_business_says']}",
            f"- Use demo: {row['use_demo_id'] or 'none; boundary/no-fit path'}",
            "- Show sections:",
        ])
        lines.extend(f"  - {item}" for item in row["show_sections"])
        lines.append("")
    lines.extend(["Boundary: demo choice support only; no customer data, no outreach, no credentials, no external delivery, no sending, no implementation, no ads/spend, and no ROI guarantee."])
    return "\n".join(lines) + "\n"


def build_vertical_test_framework(generated_at: str, vertical_targeting: dict[str, Any]) -> dict[str, Any]:
    top_verticals = vertical_targeting["ranked_verticals"][:3]
    return {
        "schema": "veritas.wf79_smb_vertical_test_framework.v1",
        "generated_at_utc": generated_at,
        "status": "ready",
        "top_test_verticals": [
            {
                "vertical": row["vertical"],
                "pain_hypothesis": row["why_fit"],
                "opener": row["best_opener"],
                "evidence_needed_before_real_outreach_approval": [
                    "Randall approves the vertical and opener",
                    "pilot-readiness packet passes QA",
                    "no credential, customer-data, ad-spend, or message-sending request is required",
                    "clear no-fit language exists",
                ],
            }
            for row in top_verticals
        ],
        "non_contact_research_allowed": [
            "review internal demo fit",
            "prepare fictional conversation examples",
            "compare vertical pain hypotheses",
            "draft owner approval criteria",
        ],
        "blocked_without_future_approval": [
            "scraping/contacting real businesses",
            "using real customer identities or private data",
            "sending DMs, emails, calls, texts, posts, or ads",
            "quoting pricing externally",
            "requesting credentials or system access",
        ],
        "authority_boundary": AUTHORITY_FALSE_FLAGS,
        "validation": {"status": "ok", "errors": [], "warnings": []},
    }


def render_vertical_test_framework_markdown(packet: dict[str, Any]) -> str:
    lines = ["# WF79 SMB Vertical Test Framework", "", f"Status: {packet['status']}", ""]
    for row in packet["top_test_verticals"]:
        lines.extend([
            f"## {row['vertical']}",
            f"- Pain hypothesis: {row['pain_hypothesis']}",
            f"- Opener: {row['opener']}",
            "- Evidence needed before real outreach approval:",
        ])
        lines.extend(f"  - {item}" for item in row["evidence_needed_before_real_outreach_approval"])
        lines.append("")
    lines.extend(["## Non-Contact Research Allowed"])
    lines.extend(f"- {item}" for item in packet["non_contact_research_allowed"])
    lines.extend(["", "## Blocked Without Future Approval"])
    lines.extend(f"- {item}" for item in packet["blocked_without_future_approval"])
    lines.extend(["", "Boundary: non-contact test framework only; no customer data, no outreach, no credentials, no external delivery, no sending, no ads/spend, no implementation, and no ROI guarantee."])
    return "\n".join(lines) + "\n"


def validate_pilot_readiness(
    pilot_readiness: dict[str, Any],
    sales_drill: dict[str, Any],
    demo_selection: dict[str, Any],
    vertical_test: dict[str, Any],
    rendered_texts: list[str],
) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    packets = [pilot_readiness, sales_drill, demo_selection, vertical_test]
    for packet in packets:
        if packet.get("status") != "ready":
            errors.append(f"packet_not_ready:{packet.get('schema')}")
        if packet.get("authority_boundary") != AUTHORITY_FALSE_FLAGS:
            errors.append(f"authority_boundary_changed:{packet.get('schema')}")
    combined = "\n".join(rendered_texts).lower()
    required_phrases = [
        "no customer data",
        "no outreach",
        "no credentials",
        "no external delivery",
        "no roi guarantee",
    ]
    for phrase in required_phrases:
        if phrase not in combined:
            errors.append(f"pilot_readiness_stop_line_missing:{phrase}")
    forbidden_claims = [
        "guaranteed revenue",
        "we will send",
        "connect your crm",
        "run your ads",
        "scrape businesses",
    ]
    for claim in forbidden_claims:
        if claim in combined:
            errors.append(f"forbidden_pilot_readiness_claim_present:{claim}")
    return {
        "schema": "veritas.wf79_smb_pilot_readiness_validation.v1",
        "generated_at_utc": pilot_readiness.get("generated_at_utc"),
        "status": "ok" if not errors else "blocked",
        "validated_artifacts": [
            rel(PILOT_READINESS_PACKET_JSON),
            rel(SALES_CONVERSATION_DRILL_JSON),
            rel(DEMO_SELECTION_TREE_JSON),
            rel(VERTICAL_TEST_FRAMEWORK_JSON),
        ],
        "errors": errors,
        "warnings": warnings,
        "authority_boundary": AUTHORITY_FALSE_FLAGS,
        "validation": {"status": "ok" if not errors else "error", "errors": errors, "warnings": warnings},
    }


def build_rollout_readiness_plan(
    generated_at: str,
    pilot_readiness: dict[str, Any],
    vertical_test: dict[str, Any],
) -> dict[str, Any]:
    return {
        "schema": "veritas.wf79_smb_rollout_readiness_plan.v1",
        "generated_at_utc": generated_at,
        "status": "ready",
        "target_state": "near_100_percent_internal_pilot_rollout_readiness",
        "estimated_internal_readiness_after_this_packet": "95-98_percent",
        "first_recommended_vertical": vertical_test["top_test_verticals"][0]["vertical"],
        "phased_approach": [
            {
                "phase": 9,
                "name": "Pilot lane selection",
                "objective": "Choose one vertical, one prospect profile, one demo path, and one safe first ask.",
                "outputs": ["vertical decision", "demo path", "first ask", "bad-fit exit"],
                "completion_state": "ready_for_owner_choice",
            },
            {
                "phase": 10,
                "name": "Approval-card preparation",
                "objective": "Prepare the exact owner approval card before any real outreach or pilot use.",
                "outputs": ["exact outreach language", "scope exclusions", "input request", "stop lines"],
                "completion_state": "approval_required_before_external_use",
            },
            {
                "phase": 11,
                "name": "Dry-run rehearsal",
                "objective": "Run a simulated conversation and delivery walkthrough with no real customer data.",
                "outputs": ["roleplay score", "objection handling notes", "delivery timing estimate"],
                "completion_state": "internal_rehearsal_only",
            },
            {
                "phase": 12,
                "name": "Pilot delivery checklist",
                "objective": "Define the manual service delivery sequence for a sanctioned pilot.",
                "outputs": ["intake checklist", "review workflow", "deliverable packet", "closeout questions"],
                "completion_state": "ready_after_owner_approval",
            },
            {
                "phase": 13,
                "name": "Real outreach / pilot",
                "objective": "External execution only after Randall gives exact approval for a named scope.",
                "outputs": ["contact attempt", "discovery notes", "sanitized input", "pilot recap"],
                "completion_state": "blocked_until_exact_owner_approval",
            },
        ],
        "week_by_week_rollout_plan": [
            {
                "week": 1,
                "name": "Internal demo and approval preparation",
                "objective": "Pick the first vertical, choose the demo path, rehearse the offer, and prepare the exact approval card.",
                "training_focus": [
                    "90-second Lead Rescue offer",
                    "bad-fit exit language",
                    "demo selection tree",
                    "stop-line explain-back",
                ],
                "practice_scenarios": [
                    "smb-missed-call-capture-v1",
                    "smb-owner-attention-dashboard-v1",
                ],
                "outputs": [
                    "selected vertical",
                    "selected demo",
                    "approved-or-blocked first ask draft",
                    "owner approval card draft",
                ],
                "external_posture": "internal_only_no_outreach",
            },
            {
                "week": 2,
                "name": "Warm-list and conversation rehearsal",
                "objective": "Practice the discovery call, objection handling, and intake boundary before any real contact.",
                "training_focus": [
                    "discovery questions",
                    "sanitized sample request",
                    "objection handling",
                    "no-ROI-claim language",
                ],
                "practice_scenarios": [
                    "smb-lead-intake-routing-v1",
                    "smb-follow-up-sequences-v1",
                ],
                "outputs": [
                    "roleplay score",
                    "approved language queue",
                    "blocked claims list",
                    "sanitized intake checklist",
                ],
                "external_posture": "blocked_until_randall_approves_exact_scope",
            },
            {
                "week": 3,
                "name": "Paid pilot delivery rehearsal",
                "objective": "Run the manual delivery flow against fake inputs before taking a paid pilot through the same steps.",
                "training_focus": [
                    "lead-flow map",
                    "owner attention queue",
                    "follow-up draft examples",
                    "automation blueprint handoff",
                ],
                "practice_scenarios": [
                    "smb-lead-status-tracking-v1",
                    "smb-script-message-pack-v1",
                ],
                "outputs": [
                    "mock pilot packet",
                    "manual delivery timing estimate",
                    "QA stop-line checklist",
                    "implementation gate notes",
                ],
                "external_posture": "pilot_delivery_only_after_separate_owner_approval",
            },
            {
                "week": 4,
                "name": "Closeout, proof, and retainer offer rehearsal",
                "objective": "Practice pilot recap, no-hype proof framing, retainer fit judgment, and next-step recommendation.",
                "training_focus": [
                    "pilot recap",
                    "case-study-safe summary",
                    "managed follow-up ops offer",
                    "no-fit decision",
                ],
                "practice_scenarios": [
                    "smb-sales-pipeline-cleanup-v1",
                    "smb-tool-stack-recommendation-v1",
                ],
                "outputs": [
                    "pilot closeout summary",
                    "retainer recommendation",
                    "no-fit or continue decision",
                    "next experiment backlog",
                ],
                "external_posture": "internal_closeout_until_real_pilot_is_approved_and_completed",
            },
        ],
        "definition_of_nearly_100_percent": [
            "internal artifacts complete and validator-clean",
            "first vertical and target profile selectable",
            "week-by-week rollout training map ready for fake-scenario rehearsal",
            "approval card can be generated from existing artifacts",
            "all real-world actions remain explicitly owner-gated",
        ],
        "source_pilot_packet": pilot_readiness.get("offer_headline"),
        "authority_boundary": AUTHORITY_FALSE_FLAGS,
        "validation": {"status": "ok", "errors": [], "warnings": []},
    }


def render_rollout_readiness_plan_markdown(packet: dict[str, Any]) -> str:
    lines = [
        "# WF79 SMB Rollout Readiness Plan",
        "",
        f"Status: {packet['status']}",
        f"Target state: {packet['target_state']}",
        f"Estimated internal readiness: {packet['estimated_internal_readiness_after_this_packet']}",
        f"First recommended vertical: {packet['first_recommended_vertical']}",
        "",
        "## Phased Approach",
    ]
    for row in packet["phased_approach"]:
        lines.extend([
            f"### Phase {row['phase']}: {row['name']}",
            f"- Objective: {row['objective']}",
            f"- Completion state: {row['completion_state']}",
            "- Outputs:",
        ])
        lines.extend(f"  - {item}" for item in row["outputs"])
        lines.append("")
    lines.extend(["## 30-Day Week-By-Week Rollout Training Plan"])
    for row in packet["week_by_week_rollout_plan"]:
        lines.extend([
            f"### Week {row['week']}: {row['name']}",
            f"- Objective: {row['objective']}",
            f"- External posture: {row['external_posture']}",
            "- Training focus:",
        ])
        lines.extend(f"  - {item}" for item in row["training_focus"])
        lines.append("- Practice scenarios:")
        lines.extend(f"  - {item}" for item in row["practice_scenarios"])
        lines.append("- Outputs:")
        lines.extend(f"  - {item}" for item in row["outputs"])
        lines.append("")
    lines.extend(["## Definition Of Nearly 100 Percent"])
    lines.extend(f"- {item}" for item in packet["definition_of_nearly_100_percent"])
    lines.extend(["", "Boundary: internal rollout readiness only; no outreach, customer data, credentials, external delivery, ads/spend, implementation, or ROI guarantee."])
    return "\n".join(lines) + "\n"


def build_client_rollout_checklist(generated_at: str) -> dict[str, Any]:
    return {
        "schema": "veritas.wf79_smb_client_rollout_checklist.v1",
        "generated_at_utc": generated_at,
        "status": "ready",
        "checklists": [
            {
                "stage": "before_owner_approval",
                "required": [
                    "choose one vertical",
                    "choose one demo path",
                    "choose one target profile",
                    "approve exact outreach words",
                    "confirm no real customer data is requested",
                    "confirm no credentials, ads, or system access are requested",
                ],
            },
            {
                "stage": "after_owner_approval_before_contact",
                "required": [
                    "use only approved wording",
                    "keep first ask to a conversation or sanitized sample review",
                    "do not claim guaranteed leads, revenue, ROI, legal, security, or compliance readiness",
                    "record outcome as internal notes only",
                ],
            },
            {
                "stage": "after_discovery_if_interested",
                "required": [
                    "request sanitized workflow description only",
                    "map lead source and follow-up path",
                    "produce manual lead/marketing ops review packet",
                    "ask whether a deeper implementation gate is worth considering",
                ],
            },
        ],
        "blocked_actions": [
            "contacting prospects without exact approval",
            "scraping prospect lists",
            "using customer identities or private data",
            "requesting logins or credentials",
            "sending messages on behalf of a business",
            "running ads or spending money",
            "implementing in customer systems",
        ],
        "authority_boundary": AUTHORITY_FALSE_FLAGS,
        "validation": {"status": "ok", "errors": [], "warnings": []},
    }


def render_client_rollout_checklist_markdown(packet: dict[str, Any]) -> str:
    lines = ["# WF79 SMB Client Rollout Checklist", "", f"Status: {packet['status']}", ""]
    for checklist in packet["checklists"]:
        lines.extend([f"## {checklist['stage']}", "Required:"])
        lines.extend(f"- {item}" for item in checklist["required"])
        lines.append("")
    lines.extend(["## Blocked Actions"])
    lines.extend(f"- {item}" for item in packet["blocked_actions"])
    lines.extend(["", "Boundary: checklist only; no outreach, customer data, credentials, external delivery, ads/spend, implementation, or ROI guarantee."])
    return "\n".join(lines) + "\n"


def build_curriculum_map(generated_at: str, sales_drill: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema": "veritas.wf79_smb_curriculum_map.v1",
        "generated_at_utc": generated_at,
        "status": "ready",
        "posture": "ready_to_enhance_training_but_current_lesson_unchanged",
        "current_lesson_preserved": True,
        "learning_map": [
            {
                "module": 1,
                "title": "Offer clarity and boundaries",
                "outcome": "Explain the Lead + Marketing Ops Review without overpromising.",
                "practice": ["30-second opener", "90-second offer", "out-of-scope language"],
            },
            {
                "module": 2,
                "title": "ICP and pain recognition",
                "outcome": "Recognize best-fit businesses and bad-fit conversations quickly.",
                "practice": ["pain signal sorting", "vertical fit scoring", "bad-fit exit"],
            },
            {
                "module": 3,
                "title": "Discovery and diagnosis",
                "outcome": "Ask questions that reveal lead-flow, follow-up, source-quality, or growth-clarity issues.",
                "practice": sales_drill["discovery_flow"],
            },
            {
                "module": 4,
                "title": "Demo selection",
                "outcome": "Choose the correct demo path based on what the owner says.",
                "practice": ["follow-up leakage demo", "more-leads/source-quality demo", "growth-clarity demo"],
            },
            {
                "module": 5,
                "title": "Manual delivery packet",
                "outcome": "Produce a useful sanitized review packet without needing customer credentials.",
                "practice": ["lead-flow map", "next-action queue", "follow-up draft", "source-quality notes"],
            },
            {
                "module": 6,
                "title": "Pilot closeout and next-step judgment",
                "outcome": "Decide whether a business is a fit for deeper work without forcing the sale.",
                "practice": ["pilot recap", "success criteria", "implementation gate discussion"],
            },
            {
                "module": 7,
                "title": "30-day rollout rehearsal",
                "outcome": "Practice the week-by-week path from demo selection to pilot closeout without crossing outreach, data, credential, or ROI-claim stop lines.",
                "practice": [
                    "week 1 demo and approval-card drill",
                    "week 2 discovery roleplay and sanitized intake drill",
                    "week 3 fake pilot delivery walkthrough",
                    "week 4 closeout and retainer-fit judgment",
                ],
            },
        ],
        "lesson_sequence": [
            "complete tonight's current SMB lesson first",
            "run offer clarity practice",
            "run ICP and pain recognition practice",
            "run discovery roleplay",
            "run demo-selection drill",
            "run manual delivery walkthrough",
            "run pilot closeout review",
            "run 30-day rollout rehearsal with fake scenarios",
        ],
        "training_not_changed": "This packet prepares the full curriculum and learning map only. It does not replace or modify the current lesson.",
        "authority_boundary": AUTHORITY_FALSE_FLAGS,
        "validation": {"status": "ok", "errors": [], "warnings": []},
    }


def render_curriculum_map_markdown(packet: dict[str, Any]) -> str:
    lines = [
        "# WF79 SMB Curriculum Map",
        "",
        f"Status: {packet['status']}",
        f"Posture: {packet['posture']}",
        f"Current lesson preserved: {packet['current_lesson_preserved']}",
        "",
        "## Learning Map",
    ]
    for row in packet["learning_map"]:
        lines.extend([
            f"### Module {row['module']}: {row['title']}",
            f"- Outcome: {row['outcome']}",
            "- Practice:",
        ])
        lines.extend(f"  - {item}" for item in row["practice"])
        lines.append("")
    lines.extend(["## Lesson Sequence"])
    lines.extend(f"- {item}" for item in packet["lesson_sequence"])
    lines.extend(["", f"Training note: {packet['training_not_changed']}"])
    lines.extend(["", "Boundary: curriculum planning only; no outreach, customer data, credentials, external delivery, ads/spend, implementation, or ROI guarantee."])
    return "\n".join(lines) + "\n"


def validate_rollout_readiness(
    rollout_plan: dict[str, Any],
    checklist: dict[str, Any],
    curriculum: dict[str, Any],
    rendered_texts: list[str],
) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    for packet in (rollout_plan, checklist, curriculum):
        if packet.get("status") != "ready":
            errors.append(f"packet_not_ready:{packet.get('schema')}")
        if packet.get("authority_boundary") != AUTHORITY_FALSE_FLAGS:
            errors.append(f"authority_boundary_changed:{packet.get('schema')}")
    if not curriculum.get("current_lesson_preserved"):
        errors.append("current_lesson_not_preserved")
    combined = "\n".join(rendered_texts).lower()
    for phrase in ("no outreach", "customer data", "no credentials", "external delivery", "roi guarantee"):
        if phrase not in combined:
            errors.append(f"rollout_stop_line_missing:{phrase}")
    for claim in ("we guarantee leads", "guaranteed revenue", "we will contact", "we will send", "run ads"):
        if claim in combined:
            errors.append(f"forbidden_rollout_claim_present:{claim}")
    return {
        "schema": "veritas.wf79_smb_rollout_readiness_validation.v1",
        "generated_at_utc": rollout_plan.get("generated_at_utc"),
        "status": "ok" if not errors else "blocked",
        "validated_artifacts": [
            rel(ROLLOUT_READINESS_PLAN_JSON),
            rel(CLIENT_ROLLOUT_CHECKLIST_JSON),
            rel(CURRICULUM_MAP_JSON),
        ],
        "errors": errors,
        "warnings": warnings,
        "authority_boundary": AUTHORITY_FALSE_FLAGS,
        "validation": {"status": "ok" if not errors else "error", "errors": errors, "warnings": warnings},
    }


def build_deliverable_gate_sprint(
    generated_at: str,
    smb_service_state: dict[str, Any],
    lead_rescue_service_packet: dict[str, Any],
    automation_blueprints: dict[str, Any],
    pilot_readiness_packet: dict[str, Any],
    rollout_plan: dict[str, Any],
    client_rollout_checklist: dict[str, Any],
    curriculum: dict[str, Any],
) -> dict[str, Any]:
    deliverable_bundle = [
        {
            "name": "Lead Rescue manual service packet",
            "artifact": rel(LEAD_RESCUE_SERVICE_PACKET_JSON),
            "source_status": lead_rescue_service_packet.get("status"),
            "review_focus": "Can Randall understand the manual service promise, deliverables, and no-outreach stop lines without extra explanation?",
            "gate_state": "ready_for_internal_review",
        },
        {
            "name": "Automation blueprint packet",
            "artifact": rel(AUTOMATION_BLUEPRINTS_JSON),
            "source_status": automation_blueprints.get("status"),
            "review_focus": "Confirm each automation idea remains design-only with human review, dedupe, fallback, and no credentials.",
            "gate_state": "ready_for_internal_review",
        },
        {
            "name": "SMB service state packet",
            "artifact": rel(SMB_SERVICE_STATE_JSON),
            "source_status": smb_service_state.get("status"),
            "review_focus": "Verify the selected slice is operator-review-ready and every manual or automation step blocks external action.",
            "gate_state": "ready_for_internal_review",
        },
        {
            "name": "Pilot readiness packet",
            "artifact": rel(PILOT_READINESS_PACKET_JSON),
            "source_status": pilot_readiness_packet.get("status"),
            "review_focus": "Check that pilot use is approval-gated and does not imply real customer readiness.",
            "gate_state": "ready_for_internal_review",
        },
        {
            "name": "Rollout readiness plan",
            "artifact": rel(ROLLOUT_READINESS_PLAN_JSON),
            "source_status": rollout_plan.get("status"),
            "review_focus": "Review the rollout path as internal rehearsal only, including the week-by-week fake-scenario training plan.",
            "gate_state": "ready_for_internal_review",
        },
        {
            "name": "Client rollout checklist",
            "artifact": rel(CLIENT_ROLLOUT_CHECKLIST_JSON),
            "source_status": client_rollout_checklist.get("status"),
            "review_focus": "Use the checklist as owner approval-card input, not as authorization for a live client.",
            "gate_state": "ready_for_internal_review",
        },
        {
            "name": "Curriculum map",
            "artifact": rel(CURRICULUM_MAP_JSON),
            "source_status": curriculum.get("status"),
            "review_focus": "Confirm the learning sequence preserves the current lesson and adds only rehearsal structure.",
            "gate_state": "ready_for_internal_review",
        },
        {
            "name": "Cockpit and phase closeout",
            "artifact": rel(COCKPIT_PANEL_JSON),
            "source_status": "ready",
            "review_focus": "Use the cockpit as the local review index for the deliverable bundle.",
            "gate_state": "ready_for_internal_review",
        },
    ]
    return {
        "schema": "veritas.wf75_smb_deliverable_gate_sprint.v1",
        "generated_at_utc": generated_at,
        "status": "ready",
        "workflow_ids": ["WF75", "WF79-SMB"],
        "gate": "manual_internal_deliverable_review_before_any_external_use",
        "source_audit": AUDIT_SOURCE,
        "current_position": "Internal/operator review is ready. Real outreach, real customer data, external delivery, implementation, credentials, spend, and ROI claims remain blocked without exact owner approval.",
        "deliverable_bundle": deliverable_bundle,
        "operator_review_sequence": [
            {
                "step": 1,
                "name": "Open the Lead Rescue packet",
                "action": "Check the service promise, exact manual outputs, and owner-facing stop lines.",
                "proof_artifacts": [rel(LEAD_RESCUE_SERVICE_PACKET_JSON), rel(LEAD_RESCUE_SERVICE_PACKET_VALIDATION_JSON)],
                "exit_condition": "Accept as internal review-ready or mark revisions before any approval card.",
            },
            {
                "step": 2,
                "name": "Review automation and service-state proof",
                "action": "Confirm the automation blueprints and service-state packet keep all work staged for operator review.",
                "proof_artifacts": [rel(AUTOMATION_BLUEPRINTS_JSON), rel(SMB_SERVICE_STATE_JSON)],
                "exit_condition": "No blueprint may use real data, credentials, outbound delivery, or customer-system writeback.",
            },
            {
                "step": 3,
                "name": "Choose demo and rehearsal path",
                "action": "Use the demo tree, curriculum map, and rollout plan to choose the next fake-scenario rehearsal.",
                "proof_artifacts": [rel(DEMO_SELECTION_TREE_JSON), rel(CURRICULUM_MAP_JSON), rel(ROLLOUT_READINESS_PLAN_JSON)],
                "exit_condition": "Selected path is internal-only and preserves the current lesson sequence.",
            },
            {
                "step": 4,
                "name": "Decide the next business option",
                "action": "Choose continue internal rehearsal, revise packet, prepare an exact owner approval card, or no-go/defer.",
                "proof_artifacts": [rel(CLIENT_ROLLOUT_CHECKLIST_JSON), rel(PILOT_READINESS_PACKET_JSON)],
                "exit_condition": "Any real outreach or pilot path is converted into an exact approval card before action.",
            },
        ],
        "readiness_options": [
            {
                "option": "continue_internal_rehearsal",
                "when_to_choose": "The bundle is useful but needs more fake-scenario reps before any market contact.",
                "allowed_next_action": "Run another sanitized service-state slice or sales drill.",
                "authority": "safe_without_owner_external_approval",
            },
            {
                "option": "revise_deliverable_packet",
                "when_to_choose": "The promise, demo, proof, or stop-line language is unclear.",
                "allowed_next_action": "Patch the local packets and rerun validation.",
                "authority": "safe_without_owner_external_approval",
            },
            {
                "option": "prepare_exact_owner_approval_card",
                "when_to_choose": "Randall wants to consider a specific real outreach or pilot action.",
                "allowed_next_action": "Draft a scoped approval card with target, channel, data, offer, proof, stop lines, and rollback.",
                "authority": "approval_prep_only",
            },
            {
                "option": "no_go_or_defer",
                "when_to_choose": "The offer is not clear enough, the proof is weak, or the external boundary is uncomfortable.",
                "allowed_next_action": "Keep WF75/WF79-SMB internal and return to higher-priority workflow work.",
                "authority": "safe_without_owner_external_approval",
            },
        ],
        "blocked_without_exact_owner_approval": [
            "no real customer data",
            "no outreach, contact, calls, texts, emails, posts, review requests, or ads",
            "no credentials, account access, CRM access, phone access, email access, payment access, POS access, or automation-platform access",
            "no external delivery, public launch, client pilot, or customer-facing implementation",
            "no implementation in customer systems",
            "no ROI guarantee, revenue guarantee, legal readiness claim, compliance readiness claim, security readiness claim, certification claim, or performance claim",
            "no spend, ads, tools purchase, subscription purchase, contractor spend, or account setup",
        ],
        "acceptance_proof": [
            rel(DELIVERABLE_GATE_JSON),
            rel(DELIVERABLE_GATE_MD),
            rel(DELIVERABLE_GATE_VALIDATION_JSON),
            rel(PHASE_CLOSEOUT_JSON),
            rel(DEFAULT_DB),
        ],
        "next_safe_action": "Review the deliverable-gate sprint bundle manually and choose internal rehearsal, revision, exact approval-card prep, or no-go/defer.",
        "authority_boundary": AUTHORITY_FALSE_FLAGS,
        "validation": {"status": "ok", "errors": [], "warnings": []},
    }


def render_deliverable_gate_markdown(packet: dict[str, Any]) -> str:
    lines = [
        "# WF75/WF79-SMB Deliverable Gate Sprint",
        "",
        f"Status: {packet['status']}",
        f"Gate: {packet['gate']}",
        f"Source audit: {packet['source_audit']}",
        "",
        f"Current position: {packet['current_position']}",
        "",
        "## Deliverable Bundle",
    ]
    for item in packet["deliverable_bundle"]:
        lines.extend([
            f"### {item['name']}",
            f"- Artifact: {item['artifact']}",
            f"- Source status: {item['source_status']}",
            f"- Review focus: {item['review_focus']}",
            f"- Gate state: {item['gate_state']}",
            "",
        ])
    lines.extend(["## Operator Review Sequence"])
    for row in packet["operator_review_sequence"]:
        lines.extend([
            f"### Step {row['step']}: {row['name']}",
            f"- Action: {row['action']}",
            f"- Exit condition: {row['exit_condition']}",
            "- Proof artifacts:",
        ])
        lines.extend(f"  - {path}" for path in row["proof_artifacts"])
        lines.append("")
    lines.extend(["## Readiness Options"])
    for row in packet["readiness_options"]:
        lines.extend([
            f"### {row['option']}",
            f"- When: {row['when_to_choose']}",
            f"- Allowed next action: {row['allowed_next_action']}",
            f"- Authority: {row['authority']}",
            "",
        ])
    lines.extend(["## Blocked Without Exact Owner Approval"])
    lines.extend(f"- {item}" for item in packet["blocked_without_exact_owner_approval"])
    lines.extend([
        "",
        "Boundary: manual internal deliverable review only; no real customer data, no outreach, no credentials, no external delivery, no implementation, no ROI guarantee, no spend, no public launch, and no owner approval inference.",
        "",
        f"Next safe action: {packet['next_safe_action']}",
    ])
    return "\n".join(lines) + "\n"


def validate_deliverable_gate_sprint(packet: dict[str, Any], rendered_text: str) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    if packet.get("status") != "ready":
        errors.append("deliverable_gate_status_not_ready")
    if packet.get("authority_boundary") != AUTHORITY_FALSE_FLAGS:
        errors.append("deliverable_gate_authority_boundary_changed")
    if len(packet.get("deliverable_bundle", [])) < 7:
        errors.append("deliverable_bundle_below_7")
    if not packet.get("operator_review_sequence"):
        errors.append("operator_review_sequence_missing")
    if not packet.get("readiness_options"):
        errors.append("readiness_options_missing")
    combined = (json.dumps(packet, sort_keys=True) + "\n" + rendered_text).lower()
    for phrase in (
        "manual internal deliverable review",
        "no real customer data",
        "no outreach",
        "no credentials",
        "external delivery",
        "no implementation",
        "no roi",
        "owner approval",
    ):
        if phrase not in combined:
            errors.append(f"deliverable_gate_stop_line_missing:{phrase}")
    for claim in (
        "we will contact",
        "we will send",
        "guaranteed revenue",
        "compliance ready",
        "security ready",
        "approval granted",
        "customer-ready",
        "public launch ready",
    ):
        if claim in combined:
            errors.append(f"forbidden_deliverable_gate_claim_present:{claim}")
    return {
        "schema": "veritas.wf75_smb_deliverable_gate_validation.v1",
        "generated_at_utc": packet.get("generated_at_utc"),
        "status": "ok" if not errors else "blocked",
        "validated_artifacts": [
            rel(DELIVERABLE_GATE_JSON),
            rel(DELIVERABLE_GATE_MD),
        ],
        "errors": errors,
        "warnings": warnings,
        "authority_boundary": AUTHORITY_FALSE_FLAGS,
        "validation": {"status": "ok" if not errors else "error", "errors": errors, "warnings": warnings},
    }


def build_cockpit_panel(
    generated_at: str,
    offer_packet: dict[str, Any],
    demo_packets: dict[str, Any],
    demo_validation: dict[str, Any],
    marketing_blueprints: dict[str, Any],
    marketing_blueprints_validation: dict[str, Any],
    sales_practice: dict[str, Any],
    outreach_validation: dict[str, Any],
    pilot_readiness_validation: dict[str, Any],
    rollout_readiness_validation: dict[str, Any],
    deliverable_gate_validation: dict[str, Any],
) -> dict[str, Any]:
    phases = [
        ("phase_0_offer_icp", "Offer / ICP", rel(OFFER_ICP_JSON), offer_packet.get("status")),
        ("phase_1_demo_packets", "Sanitized demo packets", rel(DEMO_PACKETS_JSON), demo_validation.get("status")),
        ("phase_2_marketing_ops_blueprints", "Marketing ops blueprints", rel(MARKETING_OPS_BLUEPRINTS_JSON), marketing_blueprints_validation.get("status")),
        ("phase_3_cockpit_panel", "Local cockpit panel", rel(COCKPIT_PANEL_JSON), "ready"),
        ("phase_4_sales_practice", "Training / sales practice", rel(SALES_PRACTICE_JSON), sales_practice.get("status")),
        ("phase_5_stop_line_lint", "QA / stop-line lint", rel(PHASE_CLOSEOUT_JSON), "ready"),
        ("phase_6_outreach_prep", "Approval-gated outreach prep", rel(OUTREACH_PREP_VALIDATION_JSON), outreach_validation.get("status")),
        ("phase_7_pilot_readiness", "Pilot readiness packaging", rel(PILOT_READINESS_VALIDATION_JSON), pilot_readiness_validation.get("status")),
        ("phase_8_rollout_readiness", "Rollout readiness and curriculum map", rel(ROLLOUT_READINESS_VALIDATION_JSON), rollout_readiness_validation.get("status")),
        ("phase_9_deliverable_gate", "Manual deliverable review gate", rel(DELIVERABLE_GATE_VALIDATION_JSON), deliverable_gate_validation.get("status")),
        ("phase_10_real_outreach_gate", "Real outreach / pilot gate", rel(PILOT_READINESS_PACKET_JSON), "approval_required"),
    ]
    return {
        "schema": "veritas.wf79_smb_cockpit_panel.v1",
        "generated_at_utc": generated_at,
        "status": "ready",
        "workflow_id": "WF79-SMB",
        "display_name": "SMB Workflow Clarity / Marketing Ops Automation",
        "offer_ladder": offer_packet["positioning"]["offer_ladder"],
        "phase_statuses": [
            {"phase_id": phase_id, "title": title, "artifact": artifact, "status": status}
            for phase_id, title, artifact, status in phases
        ],
        "counts": {
            "demo_packets": demo_packets.get("demo_count"),
            "marketing_ops_blueprints": marketing_blueprints.get("blueprint_count"),
            "discovery_questions": len(sales_practice.get("discovery_questions", [])),
            "outreach_prep_validation_errors": len(outreach_validation.get("errors", [])),
            "pilot_readiness_validation_errors": len(pilot_readiness_validation.get("errors", [])),
            "rollout_readiness_validation_errors": len(rollout_readiness_validation.get("errors", [])),
            "deliverable_gate_validation_errors": len(deliverable_gate_validation.get("errors", [])),
        },
        "next_safe_action": "Review the deliverable-gate sprint packet; real outreach or pilot use still requires Randall exact approval.",
        "authority_boundary": AUTHORITY_FALSE_FLAGS,
        "validation": {"status": "ok", "errors": [], "warnings": []},
    }


def render_cockpit_panel_html(panel: dict[str, Any]) -> str:
    rows = "\n".join(
        "<tr>"
        f"<td>{escape(row['phase_id'])}</td>"
        f"<td>{escape(row['title'])}</td>"
        f"<td>{escape(str(row['status']))}</td>"
        f"<td>{escape(row['artifact'])}</td>"
        "</tr>"
        for row in panel["phase_statuses"]
    )
    return f"""<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <title>{escape(panel['display_name'])}</title>
  <style>
    body {{ font-family: Segoe UI, Arial, sans-serif; margin: 24px; color: #172033; background: #f6f7f9; }}
    h1 {{ font-size: 24px; margin-bottom: 6px; }}
    .summary {{ margin: 12px 0 20px; padding: 12px; background: #fff; border: 1px solid #d7dce5; border-radius: 6px; }}
    table {{ border-collapse: collapse; width: 100%; background: #fff; }}
    th, td {{ text-align: left; padding: 10px; border-bottom: 1px solid #e2e6ee; font-size: 14px; }}
    th {{ background: #e9edf5; }}
    .boundary {{ margin-top: 18px; font-size: 13px; color: #45536b; }}
  </style>
</head>
<body>
  <h1>{escape(panel['display_name'])}</h1>
  <div class="summary">
    <strong>Status:</strong> {escape(panel['status'])}<br>
    <strong>Next safe action:</strong> {escape(panel['next_safe_action'])}<br>
    <strong>Offer ladder:</strong> {escape(' -> '.join(panel['offer_ladder']))}
  </div>
  <table>
    <thead><tr><th>Phase</th><th>Title</th><th>Status</th><th>Artifact</th></tr></thead>
    <tbody>{rows}</tbody>
  </table>
  <div class="boundary">Review-only local panel. No customer data, outreach, credentials, external delivery, ad action, spending, or ROI guarantee.</div>
</body>
</html>
"""


def build_phase_closeout(
    generated_at: str,
    offer_packet: dict[str, Any],
    demo_validation: dict[str, Any],
    marketing_blueprints_validation: dict[str, Any],
    cockpit_panel: dict[str, Any],
    sales_practice: dict[str, Any],
    outreach_validation: dict[str, Any],
    pilot_readiness_validation: dict[str, Any],
    rollout_readiness_validation: dict[str, Any],
    deliverable_gate_validation: dict[str, Any],
) -> dict[str, Any]:
    phases = [
        {"phase": 0, "name": "Offer / ICP", "status": offer_packet.get("status"), "artifact": rel(OFFER_ICP_JSON)},
        {"phase": 1, "name": "Demo packets", "status": demo_validation.get("status"), "artifact": rel(DEMO_PACKETS_VALIDATION_JSON)},
        {"phase": 2, "name": "Marketing ops blueprints", "status": marketing_blueprints_validation.get("status"), "artifact": rel(MARKETING_OPS_BLUEPRINTS_VALIDATION_JSON)},
        {"phase": 3, "name": "Local cockpit panel", "status": cockpit_panel.get("status"), "artifact": rel(COCKPIT_PANEL_JSON)},
        {"phase": 4, "name": "Training / sales practice", "status": sales_practice.get("status"), "artifact": rel(SALES_PRACTICE_JSON)},
        {"phase": 5, "name": "QA / stop-line lint", "status": "ok" if demo_validation.get("status") == "ok" and marketing_blueprints_validation.get("status") == "ok" and outreach_validation.get("status") == "ok" and pilot_readiness_validation.get("status") == "ok" and rollout_readiness_validation.get("status") == "ok" and deliverable_gate_validation.get("status") == "ok" else "blocked", "artifact": rel(PHASE_CLOSEOUT_JSON)},
        {"phase": 6, "name": "Approval-gated outreach prep", "status": outreach_validation.get("status"), "artifact": rel(OUTREACH_PREP_VALIDATION_JSON)},
        {"phase": 7, "name": "Pilot readiness packaging", "status": pilot_readiness_validation.get("status"), "artifact": rel(PILOT_READINESS_VALIDATION_JSON)},
        {"phase": 8, "name": "Rollout readiness and curriculum map", "status": rollout_readiness_validation.get("status"), "artifact": rel(ROLLOUT_READINESS_VALIDATION_JSON)},
        {"phase": 9, "name": "Manual deliverable review gate", "status": deliverable_gate_validation.get("status"), "artifact": rel(DELIVERABLE_GATE_VALIDATION_JSON)},
        {"phase": 10, "name": "Real outreach / pilot gate", "status": "approval_required", "artifact": rel(PILOT_READINESS_PACKET_JSON)},
    ]
    return {
        "schema": "veritas.wf79_smb_phase_closeout.v1",
        "generated_at_utc": generated_at,
        "status": "ready" if all(row["status"] in {"ready", "ok", "approval_required"} for row in phases) else "blocked",
        "phases": phases,
        "fully_implemented_internal_artifacts": True,
        "remaining_gate": "Manual deliverable-gate review is internal only. Randall exact approval remains required before real outreach, real customer data, credentials, ads, external delivery, spending, customer-system implementation, or any ROI/legal/compliance/security readiness claim.",
        "authority_boundary": AUTHORITY_FALSE_FLAGS,
        "validation": {"status": "ok", "errors": [], "warnings": []},
    }


def build_automation_blueprints(generated_at: str) -> dict[str, Any]:
    reviewed_patterns = [
        {
            "source": "n8n-workflow-automation",
            "useful_patterns": ["dedup keys", "idempotent reruns", "audit logging", "retry/backoff", "human review queue"],
            "installed": False,
        },
        {
            "source": "automation-workflows",
            "useful_patterns": ["automation audit", "tool selection", "testing checklist", "maintenance review", "payback discipline"],
            "installed": False,
        },
        {
            "source": "afrexai-business-automation",
            "useful_patterns": ["process map", "automation scoring", "workflow architecture template", "health dashboard"],
            "installed": False,
            "intake_note": "Reviewed as pattern input only; ClawHub security signal was suspicious, so do not install blindly.",
        },
        {
            "source": "agentic-workflow-automation-hardened",
            "useful_patterns": ["single-purpose steps", "fallback behavior", "external transmission confirmation gate", "destructive-action human gate"],
            "installed": False,
        },
    ]
    shared_stop_lines = [
        "dry-run design only",
        "no real customer data",
        "no customer-data retention",
        "no CRM, phone, email, ad, payment, POS, payroll, or automation-platform credential use",
        "no outbound calls, texts, emails, posts, or review requests",
        "no customer-system implementation",
        "no public launch or external delivery",
        "no guaranteed revenue, ROI, legal, compliance, or security readiness claim",
    ]
    blueprints = [
        {
            "blueprint_id": "lead-rescue-missed-call-to-attention-queue-v1",
            "title": "Missed call to owner attention queue",
            "scenario_ids": ["smb-missed-call-capture-v1", "smb-owner-attention-dashboard-v1"],
            "trigger": {"type": "manual_or_future_webhook", "source": "sanitized missed-call sample", "timezone": "America/Phoenix"},
            "input_contract": {
                "required_fields": ["sample_call_id", "timestamp", "business_hours_flag", "voicemail_summary"],
                "dedup_key": "sample_call_id",
                "validation_rules": ["required fields present", "no private caller identity in fixtures"],
            },
            "steps": [
                {"id": "normalize_call", "action": "transform", "on_failure": "human_review_queue"},
                {"id": "classify_reason", "action": "classify", "on_failure": "human_review_queue"},
                {"id": "rank_callback_priority", "action": "score", "on_failure": "human_review_queue"},
                {"id": "write_owner_attention_row", "action": "stage_review_row", "on_failure": "human_review_queue"},
            ],
            "idempotency": {"store": "tmp/generic-service-state.sqlite", "dedup_key": "sample_call_id", "rerun_behavior": "update_existing_review_row"},
            "observability": {"run_id_required": True, "audit_log": "qa_events", "status_fields": ["started", "completed", "failed", "queued_for_review"]},
            "retry_policy": {"max_attempts": 3, "backoff": "exponential", "final_state": "human_review_queue"},
            "human_review_queue": {"required": True, "review_reason_fields": ["missing_field", "unsafe_identity", "classification_uncertain", "step_failed"]},
            "human_review_checkpoint": "Operator reviews every staged callback-priority row before any customer-facing action.",
            "failure_fallback": "Keep the item in the human review queue with failure reason and do not send or write externally.",
            "tool_candidate": "n8n, Make, Zapier, or local Python after future implementation gate",
            "activation_state": "design_only",
            "stop_lines": shared_stop_lines,
        },
        {
            "blueprint_id": "lead-intake-to-follow-up-reminder-v1",
            "title": "Lead intake to follow-up reminder draft",
            "scenario_ids": ["smb-lead-intake-routing-v1", "smb-lead-status-tracking-v1", "smb-follow-up-sequences-v1"],
            "trigger": {"type": "manual_csv_or_future_form_event", "source": "sanitized lead sample", "timezone": "America/Phoenix"},
            "input_contract": {
                "required_fields": ["sample_lead_id", "lead_source", "created_at", "status", "last_touch_at"],
                "dedup_key": "sample_lead_id",
                "validation_rules": ["lead_source allowed", "status recognized", "no real contact fields before intake gate"],
            },
            "steps": [
                {"id": "normalize_lead", "action": "transform", "on_failure": "human_review_queue"},
                {"id": "detect_status_gap", "action": "decide", "on_failure": "human_review_queue"},
                {"id": "stage_follow_up_recommendation", "action": "draft", "on_failure": "human_review_queue"},
                {"id": "append_review_only_reminder", "action": "stage_review_row", "on_failure": "human_review_queue"},
            ],
            "idempotency": {"store": "tmp/generic-service-state.sqlite", "dedup_key": "sample_lead_id", "rerun_behavior": "replace_review_only_recommendation"},
            "observability": {"run_id_required": True, "audit_log": "qa_events", "status_fields": ["started", "completed", "failed", "queued_for_review"]},
            "retry_policy": {"max_attempts": 2, "backoff": "fixed_5_minutes", "final_state": "human_review_queue"},
            "human_review_queue": {"required": True, "review_reason_fields": ["missing_field", "unsafe_contact_data", "message_needs_operator_approval", "step_failed"]},
            "human_review_checkpoint": "Operator approves status labels and any follow-up wording before use.",
            "failure_fallback": "Stage an internal blocker row and leave follow-up as manual-only until reviewed.",
            "tool_candidate": "Zapier for simple triggers; Make/n8n for branching; local Python for internal fixtures",
            "activation_state": "design_only",
            "stop_lines": shared_stop_lines,
        },
        {
            "blueprint_id": "tool-stack-gap-to-implementation-plan-v1",
            "title": "Tool-stack gap to manual implementation plan",
            "scenario_ids": ["smb-tool-stack-recommendation-v1", "smb-sales-pipeline-cleanup-v1"],
            "trigger": {"type": "manual_workshop_notes", "source": "sanitized tool-stack questionnaire", "timezone": "America/Phoenix"},
            "input_contract": {
                "required_fields": ["sample_business_type", "current_tools", "lead_sources", "manual_steps", "budget_range"],
                "dedup_key": "sample_business_type:current_tools_hash",
                "validation_rules": ["no credentials", "no account URLs or secrets", "budget is range only"],
            },
            "steps": [
                {"id": "map_current_process", "action": "document", "on_failure": "human_review_queue"},
                {"id": "score_automation_candidates", "action": "score", "on_failure": "human_review_queue"},
                {"id": "choose_tool_path", "action": "recommend", "on_failure": "human_review_queue"},
                {"id": "stage_manual_implementation_sequence", "action": "stage_review_row", "on_failure": "human_review_queue"},
            ],
            "idempotency": {"store": "tmp/generic-service-state.sqlite", "dedup_key": "sample_business_type:current_tools_hash", "rerun_behavior": "version_new_plan"},
            "observability": {"run_id_required": True, "audit_log": "qa_events", "status_fields": ["started", "completed", "failed", "queued_for_review"]},
            "retry_policy": {"max_attempts": 1, "backoff": "none", "final_state": "human_review_queue"},
            "human_review_queue": {"required": True, "review_reason_fields": ["unclear_tools", "unsafe_credential_request", "claim_overreach", "step_failed"]},
            "human_review_checkpoint": "Operator checks tool-fit recommendation for credential, spending, and implementation overreach.",
            "failure_fallback": "Return to manual workshop notes and mark automation choice as undecided.",
            "tool_candidate": "manual service design first; automation platform only after customer-system gate",
            "activation_state": "design_only",
            "stop_lines": shared_stop_lines,
        },
    ]
    return {
        "schema": "veritas.wf75_smb_automation_blueprints.v1",
        "generated_at_utc": generated_at,
        "status": "ok",
        "purpose": "Turn reviewed workflow-automation skill patterns into Veritas-owned dry-run automation blueprints for SMB Workflow Clarity.",
        "reviewed_external_skill_patterns": reviewed_patterns,
        "blueprint_count": len(blueprints),
        "blueprints": blueprints,
        "authority_boundary": AUTHORITY_FALSE_FLAGS,
        "validation": {"status": "ok", "errors": [], "warnings": []},
    }


def validate_automation_blueprints(blueprints: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    if blueprints.get("authority_boundary") != AUTHORITY_FALSE_FLAGS:
        errors.append("automation_blueprint_authority_boundary_changed")
    if blueprints.get("blueprint_count", 0) < 3:
        errors.append("automation_blueprint_count_below_3")
    for item in blueprints.get("blueprints", []):
        blueprint_id = item.get("blueprint_id", "unknown")
        if not item.get("title"):
            errors.append(f"title_missing:{blueprint_id}")
        if item.get("activation_state") != "design_only":
            errors.append(f"activation_state_not_design_only:{blueprint_id}")
        if not item.get("input_contract", {}).get("dedup_key"):
            errors.append(f"dedup_key_missing:{blueprint_id}")
        if not item.get("idempotency"):
            errors.append(f"idempotency_missing:{blueprint_id}")
        if not item.get("observability", {}).get("run_id_required"):
            errors.append(f"run_id_required_missing:{blueprint_id}")
        if not item.get("human_review_queue", {}).get("required"):
            errors.append(f"human_review_queue_missing:{blueprint_id}")
        if not item.get("human_review_checkpoint"):
            errors.append(f"human_review_checkpoint_missing:{blueprint_id}")
        if not item.get("failure_fallback"):
            errors.append(f"failure_fallback_missing:{blueprint_id}")
        if not item.get("retry_policy"):
            errors.append(f"retry_policy_missing:{blueprint_id}")
        joined = " ".join(item.get("stop_lines", [])).lower()
        for phrase in ("no real customer data", "no outbound", "no customer-system implementation", "no public launch"):
            if phrase not in joined:
                errors.append(f"stop_line_missing:{blueprint_id}:{phrase}")
    if any(row.get("source") == "afrexai-business-automation" and not row.get("intake_note") for row in blueprints.get("reviewed_external_skill_patterns", [])):
        warnings.append("afrexai_business_automation_reviewed_without_intake_note")
    return {
        "schema": "veritas.wf75_smb_automation_blueprints_validation.v1",
        "generated_at_utc": blueprints.get("generated_at_utc"),
        "status": "ok" if not errors else "blocked",
        "validated_artifacts": [rel(AUTOMATION_BLUEPRINTS_JSON)],
        "errors": errors,
        "warnings": warnings,
        "authority_boundary": AUTHORITY_FALSE_FLAGS,
        "validation": {"status": "ok" if not errors else "error", "errors": errors, "warnings": warnings},
    }


def build_smb_service_state(
    generated_at: str,
    scenarios: dict[str, Any],
    preview: dict[str, Any],
    lead_rescue_service_packet: dict[str, Any],
    lead_rescue_service_packet_validation: dict[str, Any],
    automation_blueprints: dict[str, Any],
    automation_blueprints_validation: dict[str, Any],
) -> dict[str, Any]:
    source_scenario_ids = preview.get("source_scenario_ids", [])
    selected_blueprints = [
        item
        for item in automation_blueprints.get("blueprints", [])
        if set(item.get("scenario_ids", [])) & set(source_scenario_ids)
    ]
    manual_steps: list[dict[str, Any]] = []
    for step in lead_rescue_service_packet.get("exact_manual_delivery_steps", []):
        manual_steps.append(
            {
                "step": step.get("step"),
                "name": step.get("name"),
                "state": "staged_for_operator_review",
                "owner_action": step.get("owner_action"),
                "output": step.get("output"),
                "external_action_allowed": False,
            }
        )
    return {
        "schema": "veritas.wf75_smb_service_state.v1",
        "generated_at_utc": generated_at,
        "status": "ok",
        "workflow": "WF75",
        "lane": "smb_workflow_clarity",
        "service_run_id": "smb-lead-rescue-service-state-v1",
        "scenario_family": "Lead Rescue & Follow-Up Workflow Sprint",
        "current_state": "operator_review_ready",
        "state_machine": [
            "requested",
            "intake_boundary_checked",
            "lead_sources_mapped",
            "attention_queue_drafted",
            "script_pack_drafted",
            "qa_stop_line_reviewed",
            "operator_review_ready",
            "blocked",
        ],
        "selected_slice": {
            "slice_id": "lead-rescue-owner-attention-queue-v1",
            "implementation_posture": "manual_service_state_and_blueprint_review_only",
            "source_scenario_ids": source_scenario_ids,
            "selected_blueprint_ids": [item.get("blueprint_id") for item in selected_blueprints],
            "next_safe_build": "Build a sanitized fixture runner for the owner attention queue, then validate it without real customer data or outbound delivery.",
        },
        "manual_delivery_state": manual_steps,
        "automation_blueprint_state": [
            {
                "blueprint_id": item.get("blueprint_id"),
                "title": item.get("title"),
                "activation_state": item.get("activation_state"),
                "human_review_required": bool(item.get("human_review_queue", {}).get("required")),
                "dedupe_key": item.get("input_contract", {}).get("dedup_key"),
                "audit_log": item.get("observability", {}).get("audit_log"),
                "external_action_allowed": False,
            }
            for item in selected_blueprints
        ],
        "proof_artifacts": [
            rel(SCENARIO_LIBRARY_JSON),
            rel(CUSTOMER_PREVIEW_JSON),
            rel(CUSTOMER_PREVIEW_VALIDATION_JSON),
            rel(LEAD_RESCUE_SERVICE_PACKET_JSON),
            rel(LEAD_RESCUE_SERVICE_PACKET_VALIDATION_JSON),
            rel(AUTOMATION_BLUEPRINTS_JSON),
            rel(AUTOMATION_BLUEPRINTS_VALIDATION_JSON),
            rel(DEFAULT_DB),
        ],
        "validation_inputs": {
            "scenario_count": scenarios.get("scenario_count"),
            "lead_rescue_service_packet_validation": lead_rescue_service_packet_validation.get("status"),
            "automation_blueprints_validation": automation_blueprints_validation.get("status"),
        },
        "authority_boundary": AUTHORITY_FALSE_FLAGS,
        "stop_lines": [
            "no real customer data",
            "no customer-data retention",
            "no credentials or customer system access",
            "no outbound calls, texts, emails, posts, ads, or review requests",
            "no external delivery or public launch",
            "no ROI, revenue, legal, compliance, security, or certification claims",
            "no implementation in customer systems",
            "no owner approval inference",
        ],
        "validation": {"status": "ok", "errors": [], "warnings": []},
    }


def validate_smb_service_state(state: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    if state.get("schema") != "veritas.wf75_smb_service_state.v1":
        errors.append("schema_mismatch")
    if state.get("status") != "ok":
        errors.append("status_not_ok")
    if state.get("current_state") != "operator_review_ready":
        errors.append("current_state_not_operator_review_ready")
    if not state.get("manual_delivery_state"):
        errors.append("manual_delivery_state_missing")
    selected = state.get("selected_slice", {})
    if not selected.get("selected_blueprint_ids"):
        errors.append("selected_blueprint_ids_missing")
    if state.get("authority_boundary") != AUTHORITY_FALSE_FLAGS:
        errors.append("authority_boundary_changed")
    for row in state.get("manual_delivery_state", []):
        if row.get("external_action_allowed") is not False:
            errors.append(f"manual_step_external_action_allowed:{row.get('name')}")
    for row in state.get("automation_blueprint_state", []):
        if row.get("external_action_allowed") is not False:
            errors.append(f"blueprint_external_action_allowed:{row.get('blueprint_id')}")
        if row.get("human_review_required") is not True:
            errors.append(f"blueprint_missing_human_review:{row.get('blueprint_id')}")
    return {
        "schema": "veritas.wf75_smb_service_state_validation.v1",
        "generated_at_utc": state.get("generated_at_utc"),
        "status": "ok" if not errors else "blocked",
        "validated_artifacts": [rel(SMB_SERVICE_STATE_JSON)],
        "errors": errors,
        "warnings": warnings,
        "authority_boundary": AUTHORITY_FALSE_FLAGS,
        "validation": {"status": "ok" if not errors else "error", "errors": errors, "warnings": warnings},
    }


def validate_customer_preview(preview: dict[str, Any], rendered_text: str) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    if preview.get("status") != "ok":
        errors.append("preview_status_not_ok")
    if preview.get("authority_boundary") != AUTHORITY_FALSE_FLAGS:
        errors.append("preview_authority_boundary_changed")
    required_false_phrases = [
        "no real customer data",
        "external delivery",
        "credential access",
        "guaranteed ROI",
        "owner approval inference",
    ]
    rendered_lower = rendered_text.lower()
    for phrase in required_false_phrases:
        if phrase.lower() not in rendered_lower:
            errors.append(f"rendered_stop_line_missing:{phrase}")
    forbidden_claims = [
        "will increase revenue",
        "compliance ready",
        "security ready",
        "we will send",
        "connect your crm",
        "connect your phone",
    ]
    for claim in forbidden_claims:
        if claim in rendered_lower:
            errors.append(f"forbidden_claim_present:{claim}")
    if not preview.get("preview_sections"):
        errors.append("preview_sections_missing")
    if len(preview.get("source_scenario_ids", [])) < 5:
        errors.append("source_scenario_count_below_5")
    return {
        "schema": "veritas.wf75_smb_customer_preview_validation.v1",
        "generated_at_utc": preview.get("generated_at_utc"),
        "status": "ok" if not errors else "blocked",
        "validated_artifacts": [rel(CUSTOMER_PREVIEW_JSON), rel(CUSTOMER_PREVIEW_MD)],
        "errors": errors,
        "warnings": warnings,
        "authority_boundary": AUTHORITY_FALSE_FLAGS,
        "validation": {"status": "ok" if not errors else "error", "errors": errors, "warnings": warnings},
    }


def validate_payloads(payloads: list[dict[str, Any]]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    for payload in payloads:
        if payload.get("status") not in {"ok", "review_ready", "ready"}:
            errors.append(f"status_not_ok:{payload.get('schema')}")
        authority = payload.get("authority_boundary")
        if authority != AUTHORITY_FALSE_FLAGS:
            errors.append(f"authority_boundary_changed:{payload.get('schema')}")
    scenarios = payloads[1].get("scenarios", []) if len(payloads) > 1 else []
    if len(scenarios) < 8:
        errors.append("smb_scenario_count_below_8")
    for item in scenarios:
        if not item.get("outputs") or not item.get("validator_focus"):
            errors.append(f"scenario_missing_outputs_or_validator_focus:{item.get('scenario_id')}")
    if not (ROOT / AUDIT_SOURCE).exists():
        warnings.append("audit_source_path_not_found")
    return {"status": "ok" if not errors else "blocked", "errors": errors, "warnings": warnings}


def rebuild_sqlite(
    contract: dict[str, Any],
    scenarios: dict[str, Any],
    pm_packet: dict[str, Any],
    preview: dict[str, Any],
    preview_validation: dict[str, Any],
    pilot_packet: dict[str, Any],
    lead_rescue_service_packet: dict[str, Any],
    lead_rescue_service_packet_validation: dict[str, Any],
    automation_blueprints: dict[str, Any],
    automation_blueprints_validation: dict[str, Any],
    smb_service_state: dict[str, Any],
    smb_service_state_validation: dict[str, Any],
    offer_icp_packet: dict[str, Any],
    demo_packets: dict[str, Any],
    demo_packets_validation: dict[str, Any],
    marketing_ops_blueprints: dict[str, Any],
    marketing_ops_blueprints_validation: dict[str, Any],
    cockpit_panel: dict[str, Any],
    sales_practice: dict[str, Any],
    outreach_kit: dict[str, Any],
    pilot_scope_intake: dict[str, Any],
    vertical_icp_targeting: dict[str, Any],
    demo_polish_packet: dict[str, Any],
    outreach_prep_validation: dict[str, Any],
    pilot_readiness_packet: dict[str, Any],
    sales_conversation_drill: dict[str, Any],
    demo_selection_tree: dict[str, Any],
    vertical_test_framework: dict[str, Any],
    pilot_readiness_validation: dict[str, Any],
    rollout_readiness_plan: dict[str, Any],
    client_rollout_checklist: dict[str, Any],
    curriculum_map: dict[str, Any],
    rollout_readiness_validation: dict[str, Any],
    deliverable_gate_sprint: dict[str, Any],
    deliverable_gate_validation: dict[str, Any],
    phase_closeout: dict[str, Any],
    db_path: Path,
) -> dict[str, Any]:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if db_path.exists():
        db_path.unlink()
    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(
            """
            CREATE TABLE service_runs (
              run_id TEXT PRIMARY KEY,
              domain TEXT NOT NULL,
              scenario_id TEXT NOT NULL,
              status TEXT NOT NULL,
              created_at_utc TEXT NOT NULL,
              updated_at_utc TEXT NOT NULL
            );
            CREATE TABLE domain_payloads (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              run_id TEXT NOT NULL,
              payload_kind TEXT NOT NULL,
              payload_json TEXT NOT NULL
            );
            CREATE TABLE artifact_refs (
              artifact_key TEXT PRIMARY KEY,
              path TEXT NOT NULL,
              schema_name TEXT NOT NULL,
              generated_at_utc TEXT NOT NULL
            );
            CREATE TABLE operator_queue (
              rank INTEGER PRIMARY KEY,
              lane_id TEXT NOT NULL,
              next_action TEXT NOT NULL,
              authority TEXT NOT NULL
            );
            CREATE TABLE qa_events (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              event_type TEXT NOT NULL,
              status TEXT NOT NULL,
              detail_json TEXT NOT NULL
            );
            CREATE TABLE renderer_outputs (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              run_id TEXT,
              output_kind TEXT NOT NULL,
              status TEXT NOT NULL,
              artifact_path TEXT
            );
            CREATE TABLE authority_events (
              key TEXT PRIMARY KEY,
              expected_value TEXT NOT NULL
            );
            """
        )
        generated_at = contract["generated_at_utc"]
        conn.execute(
            "INSERT INTO service_runs VALUES (?, ?, ?, ?, ?, ?)",
            (
                "generic-pivot-control-run-v1",
                "workflow_automation",
                "smb-owner-attention-dashboard-v1",
                "operator_review_ready",
                generated_at,
                generated_at,
            ),
        )
        conn.execute(
            "INSERT INTO service_runs VALUES (?, ?, ?, ?, ?, ?)",
            (
                smb_service_state["service_run_id"],
                "workflow_automation",
                smb_service_state["selected_slice"]["slice_id"],
                smb_service_state["current_state"],
                generated_at,
                generated_at,
            ),
        )
        for key, payload in {
            "contract": contract,
            "scenario_library": scenarios,
            "pm_decision_packet": pm_packet,
            "customer_preview": preview,
            "customer_preview_validation": preview_validation,
            "pilot_decision_packet": pilot_packet,
            "lead_rescue_service_packet": lead_rescue_service_packet,
            "lead_rescue_service_packet_validation": lead_rescue_service_packet_validation,
            "automation_blueprints": automation_blueprints,
            "automation_blueprints_validation": automation_blueprints_validation,
            "smb_service_state": smb_service_state,
            "smb_service_state_validation": smb_service_state_validation,
            "offer_icp_packet": offer_icp_packet,
            "demo_packets": demo_packets,
            "demo_packets_validation": demo_packets_validation,
            "marketing_ops_blueprints": marketing_ops_blueprints,
            "marketing_ops_blueprints_validation": marketing_ops_blueprints_validation,
            "cockpit_panel": cockpit_panel,
            "sales_practice": sales_practice,
            "outreach_kit": outreach_kit,
            "pilot_scope_intake": pilot_scope_intake,
            "vertical_icp_targeting": vertical_icp_targeting,
            "demo_polish_packet": demo_polish_packet,
            "outreach_prep_validation": outreach_prep_validation,
            "pilot_readiness_packet": pilot_readiness_packet,
            "sales_conversation_drill": sales_conversation_drill,
            "demo_selection_tree": demo_selection_tree,
            "vertical_test_framework": vertical_test_framework,
            "pilot_readiness_validation": pilot_readiness_validation,
            "rollout_readiness_plan": rollout_readiness_plan,
            "client_rollout_checklist": client_rollout_checklist,
            "curriculum_map": curriculum_map,
            "rollout_readiness_validation": rollout_readiness_validation,
            "deliverable_gate_sprint": deliverable_gate_sprint,
            "deliverable_gate_validation": deliverable_gate_validation,
            "phase_closeout": phase_closeout,
        }.items():
            conn.execute(
                "INSERT INTO domain_payloads (run_id, payload_kind, payload_json) VALUES (?, ?, ?)",
                (
                    smb_service_state["service_run_id"] if key.startswith("smb_service_state") else "generic-pivot-control-run-v1",
                    key,
                    json.dumps(payload, sort_keys=True),
                ),
            )
        for key, path, payload in [
            ("generic_service_run_contract", CONTRACT_JSON, contract),
            ("smb_workflow_scenario_library", SCENARIO_LIBRARY_JSON, scenarios),
            ("smb_pivot_pm_decision_packet", PM_DECISION_PACKET_JSON, pm_packet),
            ("smb_customer_preview", CUSTOMER_PREVIEW_JSON, preview),
            ("smb_customer_preview_validation", CUSTOMER_PREVIEW_VALIDATION_JSON, preview_validation),
            ("smb_pilot_decision_packet", PILOT_DECISION_PACKET_JSON, pilot_packet),
            ("smb_lead_rescue_service_packet", LEAD_RESCUE_SERVICE_PACKET_JSON, lead_rescue_service_packet),
            ("smb_lead_rescue_service_packet_validation", LEAD_RESCUE_SERVICE_PACKET_VALIDATION_JSON, lead_rescue_service_packet_validation),
            ("smb_automation_blueprints", AUTOMATION_BLUEPRINTS_JSON, automation_blueprints),
            ("smb_automation_blueprints_validation", AUTOMATION_BLUEPRINTS_VALIDATION_JSON, automation_blueprints_validation),
            ("smb_service_state", SMB_SERVICE_STATE_JSON, smb_service_state),
            ("smb_service_state_validation", SMB_SERVICE_STATE_VALIDATION_JSON, smb_service_state_validation),
            ("smb_offer_icp_packet", OFFER_ICP_JSON, offer_icp_packet),
            ("smb_demo_packets", DEMO_PACKETS_JSON, demo_packets),
            ("smb_demo_packets_validation", DEMO_PACKETS_VALIDATION_JSON, demo_packets_validation),
            ("smb_marketing_ops_blueprints", MARKETING_OPS_BLUEPRINTS_JSON, marketing_ops_blueprints),
            ("smb_marketing_ops_blueprints_validation", MARKETING_OPS_BLUEPRINTS_VALIDATION_JSON, marketing_ops_blueprints_validation),
            ("smb_cockpit_panel", COCKPIT_PANEL_JSON, cockpit_panel),
            ("smb_sales_practice", SALES_PRACTICE_JSON, sales_practice),
            ("smb_outreach_kit", OUTREACH_KIT_JSON, outreach_kit),
            ("smb_pilot_scope_intake", PILOT_SCOPE_INTAKE_JSON, pilot_scope_intake),
            ("smb_vertical_icp_targeting", VERTICAL_ICP_TARGETING_JSON, vertical_icp_targeting),
            ("smb_demo_polish_packet", DEMO_POLISH_PACKET_JSON, demo_polish_packet),
            ("smb_outreach_prep_validation", OUTREACH_PREP_VALIDATION_JSON, outreach_prep_validation),
            ("smb_pilot_readiness_packet", PILOT_READINESS_PACKET_JSON, pilot_readiness_packet),
            ("smb_sales_conversation_drill", SALES_CONVERSATION_DRILL_JSON, sales_conversation_drill),
            ("smb_demo_selection_tree", DEMO_SELECTION_TREE_JSON, demo_selection_tree),
            ("smb_vertical_test_framework", VERTICAL_TEST_FRAMEWORK_JSON, vertical_test_framework),
            ("smb_pilot_readiness_validation", PILOT_READINESS_VALIDATION_JSON, pilot_readiness_validation),
            ("smb_rollout_readiness_plan", ROLLOUT_READINESS_PLAN_JSON, rollout_readiness_plan),
            ("smb_client_rollout_checklist", CLIENT_ROLLOUT_CHECKLIST_JSON, client_rollout_checklist),
            ("smb_curriculum_map", CURRICULUM_MAP_JSON, curriculum_map),
            ("smb_rollout_readiness_validation", ROLLOUT_READINESS_VALIDATION_JSON, rollout_readiness_validation),
            ("smb_deliverable_gate_sprint", DELIVERABLE_GATE_JSON, deliverable_gate_sprint),
            ("smb_deliverable_gate_validation", DELIVERABLE_GATE_VALIDATION_JSON, deliverable_gate_validation),
            ("smb_phase_closeout", PHASE_CLOSEOUT_JSON, phase_closeout),
        ]:
            conn.execute(
                "INSERT INTO artifact_refs VALUES (?, ?, ?, ?)",
                (key, rel(path), payload["schema"], generated_at),
            )
        conn.execute(
            "INSERT INTO operator_queue VALUES (?, ?, ?, ?)",
            (1, "smb_workflow_clarity", "Review the deliverable-gate sprint packet, then choose internal rehearsal, revision, exact approval-card prep, or no-go/defer.", "review_only"),
        )
        conn.execute(
            "INSERT INTO qa_events (event_type, status, detail_json) VALUES (?, ?, ?)",
            (
                "pivot_packet_validation",
                "ok",
                json.dumps(
                    validate_payloads(
                        [
                            contract,
                            scenarios,
                            pm_packet,
                            preview,
                            preview_validation,
                            pilot_packet,
                            lead_rescue_service_packet,
                            lead_rescue_service_packet_validation,
                            automation_blueprints,
                            automation_blueprints_validation,
                            smb_service_state,
                            smb_service_state_validation,
                            offer_icp_packet,
                            demo_packets,
                            demo_packets_validation,
                            marketing_ops_blueprints,
                            marketing_ops_blueprints_validation,
                            cockpit_panel,
                            sales_practice,
                            outreach_kit,
                            pilot_scope_intake,
                            vertical_icp_targeting,
                            demo_polish_packet,
                            outreach_prep_validation,
                            pilot_readiness_packet,
                            sales_conversation_drill,
                            demo_selection_tree,
                            vertical_test_framework,
                            pilot_readiness_validation,
                            rollout_readiness_plan,
                            client_rollout_checklist,
                            curriculum_map,
                            rollout_readiness_validation,
                            deliverable_gate_sprint,
                            deliverable_gate_validation,
                            phase_closeout,
                        ]
                    ),
                    sort_keys=True,
                ),
            ),
        )
        conn.execute(
            "INSERT INTO renderer_outputs (run_id, output_kind, status, artifact_path) VALUES (?, ?, ?, ?)",
            ("generic-pivot-control-run-v1", "customer_preview", preview_validation["status"], rel(CUSTOMER_PREVIEW_JSON)),
        )
        for key, value in AUTHORITY_FALSE_FLAGS.items():
            conn.execute("INSERT INTO authority_events VALUES (?, ?)", (key, json.dumps(value)))
        conn.commit()
        integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
        counts = {
            "service_runs": conn.execute("SELECT COUNT(*) FROM service_runs").fetchone()[0],
            "domain_payloads": conn.execute("SELECT COUNT(*) FROM domain_payloads").fetchone()[0],
            "artifact_refs": conn.execute("SELECT COUNT(*) FROM artifact_refs").fetchone()[0],
            "operator_queue": conn.execute("SELECT COUNT(*) FROM operator_queue").fetchone()[0],
            "qa_events": conn.execute("SELECT COUNT(*) FROM qa_events").fetchone()[0],
            "renderer_outputs": conn.execute("SELECT COUNT(*) FROM renderer_outputs").fetchone()[0],
            "authority_events": conn.execute("SELECT COUNT(*) FROM authority_events").fetchone()[0],
        }
    finally:
        conn.close()
    return {
        "db_path": rel(db_path),
        "status": "ok" if integrity == "ok" else "blocked",
        "integrity_check": integrity,
        "table_counts": counts,
        "authority": "Derived generic service-state lookup only; no source-of-truth, customer, delivery, credential, outreach, payment, finance-canon, or approval authority.",
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build generic intelligence SaaS pivot artifacts.")
    parser.add_argument("--write", action="store_true", help="Write JSON artifacts.")
    parser.add_argument("--write-db", action="store_true", help="Write derived SQLite control-plane scaffold.")
    parser.add_argument("--validate", action="store_true", help="Fail nonzero on validation error.")
    parser.add_argument("--db", default=str(DEFAULT_DB), help="SQLite output path for --write-db.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    generated_at = utc_now()
    contract = build_contract(generated_at)
    scenarios = build_scenarios(generated_at)
    pm_packet = build_pm_packet(generated_at)
    preview = build_customer_preview(generated_at, scenarios)
    rendered_preview = render_customer_preview_markdown(preview)
    preview_validation = validate_customer_preview(preview, rendered_preview)
    pilot_packet = build_pilot_decision_packet(generated_at, preview)
    lead_rescue_service_packet = build_lead_rescue_service_packet(generated_at, preview, pilot_packet)
    rendered_lead_rescue_service_packet = render_lead_rescue_service_packet_markdown(lead_rescue_service_packet)
    lead_rescue_service_packet_validation = validate_lead_rescue_service_packet(lead_rescue_service_packet, rendered_lead_rescue_service_packet)
    automation_blueprints = build_automation_blueprints(generated_at)
    automation_blueprints_validation = validate_automation_blueprints(automation_blueprints)
    offer_icp_packet = build_offer_icp_packet(generated_at)
    rendered_offer_icp = render_offer_icp_markdown(offer_icp_packet)
    demo_packets = build_demo_packets(generated_at, offer_icp_packet)
    rendered_demo_packets = render_demo_packets_markdown(demo_packets)
    demo_packets_validation = validate_demo_packets(demo_packets, rendered_demo_packets)
    marketing_ops_blueprints = build_marketing_ops_blueprints(generated_at)
    marketing_ops_blueprints_validation = validate_marketing_ops_blueprints(marketing_ops_blueprints)
    sales_practice = build_sales_practice_packet(generated_at, offer_icp_packet)
    rendered_sales_practice = render_sales_practice_markdown(sales_practice)
    outreach_kit = build_outreach_kit(generated_at, offer_icp_packet, sales_practice)
    rendered_outreach_kit = render_outreach_kit_markdown(outreach_kit)
    pilot_scope_intake = build_pilot_scope_intake(generated_at)
    rendered_pilot_scope_intake = render_pilot_scope_intake_markdown(pilot_scope_intake)
    vertical_icp_targeting = build_vertical_icp_targeting(generated_at)
    rendered_vertical_icp_targeting = render_vertical_icp_targeting_markdown(vertical_icp_targeting)
    demo_polish_packet = build_demo_polish_packet(generated_at, demo_packets)
    rendered_demo_polish_packet = render_demo_polish_packet_markdown(demo_polish_packet)
    outreach_prep_validation = validate_outreach_prep(
        outreach_kit,
        pilot_scope_intake,
        vertical_icp_targeting,
        demo_polish_packet,
        [
            rendered_outreach_kit,
            rendered_pilot_scope_intake,
            rendered_vertical_icp_targeting,
            rendered_demo_polish_packet,
        ],
    )
    pilot_readiness_packet = build_pilot_readiness_packet(generated_at, offer_icp_packet, pilot_scope_intake, outreach_kit)
    rendered_pilot_readiness_packet = render_pilot_readiness_markdown(pilot_readiness_packet)
    sales_conversation_drill = build_sales_conversation_drill(generated_at, outreach_kit)
    rendered_sales_conversation_drill = render_sales_conversation_drill_markdown(sales_conversation_drill)
    demo_selection_tree = build_demo_selection_tree(generated_at, demo_polish_packet)
    rendered_demo_selection_tree = render_demo_selection_tree_markdown(demo_selection_tree)
    vertical_test_framework = build_vertical_test_framework(generated_at, vertical_icp_targeting)
    rendered_vertical_test_framework = render_vertical_test_framework_markdown(vertical_test_framework)
    pilot_readiness_validation = validate_pilot_readiness(
        pilot_readiness_packet,
        sales_conversation_drill,
        demo_selection_tree,
        vertical_test_framework,
        [
            rendered_pilot_readiness_packet,
            rendered_sales_conversation_drill,
            rendered_demo_selection_tree,
            rendered_vertical_test_framework,
        ],
    )
    rollout_readiness_plan = build_rollout_readiness_plan(generated_at, pilot_readiness_packet, vertical_test_framework)
    rendered_rollout_readiness_plan = render_rollout_readiness_plan_markdown(rollout_readiness_plan)
    client_rollout_checklist = build_client_rollout_checklist(generated_at)
    rendered_client_rollout_checklist = render_client_rollout_checklist_markdown(client_rollout_checklist)
    curriculum_map = build_curriculum_map(generated_at, sales_conversation_drill)
    rendered_curriculum_map = render_curriculum_map_markdown(curriculum_map)
    rollout_readiness_validation = validate_rollout_readiness(
        rollout_readiness_plan,
        client_rollout_checklist,
        curriculum_map,
        [
            rendered_rollout_readiness_plan,
            rendered_client_rollout_checklist,
            rendered_curriculum_map,
        ],
    )
    smb_service_state = build_smb_service_state(
        generated_at,
        scenarios,
        preview,
        lead_rescue_service_packet,
        lead_rescue_service_packet_validation,
        automation_blueprints,
        automation_blueprints_validation,
    )
    smb_service_state_validation = validate_smb_service_state(smb_service_state)
    deliverable_gate_sprint = build_deliverable_gate_sprint(
        generated_at,
        smb_service_state=smb_service_state,
        lead_rescue_service_packet=lead_rescue_service_packet,
        automation_blueprints=automation_blueprints,
        pilot_readiness_packet=pilot_readiness_packet,
        rollout_plan=rollout_readiness_plan,
        client_rollout_checklist=client_rollout_checklist,
        curriculum=curriculum_map,
    )
    rendered_deliverable_gate = render_deliverable_gate_markdown(deliverable_gate_sprint)
    deliverable_gate_validation = validate_deliverable_gate_sprint(deliverable_gate_sprint, rendered_deliverable_gate)
    cockpit_panel = build_cockpit_panel(
        generated_at,
        offer_icp_packet,
        demo_packets,
        demo_packets_validation,
        marketing_ops_blueprints,
        marketing_ops_blueprints_validation,
        sales_practice,
        outreach_prep_validation,
        pilot_readiness_validation,
        rollout_readiness_validation,
        deliverable_gate_validation,
    )
    rendered_cockpit_panel = render_cockpit_panel_html(cockpit_panel)
    phase_closeout = build_phase_closeout(
        generated_at,
        offer_icp_packet,
        demo_packets_validation,
        marketing_ops_blueprints_validation,
        cockpit_panel,
        sales_practice,
        outreach_prep_validation,
        pilot_readiness_validation,
        rollout_readiness_validation,
        deliverable_gate_validation,
    )
    validation = validate_payloads(
        [
            contract,
            scenarios,
            pm_packet,
            preview,
            preview_validation,
            pilot_packet,
            lead_rescue_service_packet,
            lead_rescue_service_packet_validation,
            automation_blueprints,
            automation_blueprints_validation,
            smb_service_state,
            smb_service_state_validation,
            offer_icp_packet,
            demo_packets,
            demo_packets_validation,
            marketing_ops_blueprints,
            marketing_ops_blueprints_validation,
            cockpit_panel,
            sales_practice,
            outreach_kit,
            pilot_scope_intake,
            vertical_icp_targeting,
            demo_polish_packet,
            outreach_prep_validation,
            pilot_readiness_packet,
            sales_conversation_drill,
            demo_selection_tree,
            vertical_test_framework,
            pilot_readiness_validation,
            rollout_readiness_plan,
            client_rollout_checklist,
            curriculum_map,
            rollout_readiness_validation,
            deliverable_gate_sprint,
            deliverable_gate_validation,
            phase_closeout,
        ]
    )
    if preview_validation["status"] != "ok":
        validation["errors"].extend(preview_validation["errors"])
        validation["status"] = "blocked"
    if automation_blueprints_validation["status"] != "ok":
        validation["errors"].extend(automation_blueprints_validation["errors"])
        validation["status"] = "blocked"
    if lead_rescue_service_packet_validation["status"] != "ok":
        validation["errors"].extend(lead_rescue_service_packet_validation["errors"])
        validation["status"] = "blocked"
    if smb_service_state_validation["status"] != "ok":
        validation["errors"].extend(smb_service_state_validation["errors"])
        validation["status"] = "blocked"
    if demo_packets_validation["status"] != "ok":
        validation["errors"].extend(demo_packets_validation["errors"])
        validation["status"] = "blocked"
    if marketing_ops_blueprints_validation["status"] != "ok":
        validation["errors"].extend(marketing_ops_blueprints_validation["errors"])
        validation["status"] = "blocked"
    if outreach_prep_validation["status"] != "ok":
        validation["errors"].extend(outreach_prep_validation["errors"])
        validation["status"] = "blocked"
    if pilot_readiness_validation["status"] != "ok":
        validation["errors"].extend(pilot_readiness_validation["errors"])
        validation["status"] = "blocked"
    if rollout_readiness_validation["status"] != "ok":
        validation["errors"].extend(rollout_readiness_validation["errors"])
        validation["status"] = "blocked"
    if deliverable_gate_validation["status"] != "ok":
        validation["errors"].extend(deliverable_gate_validation["errors"])
        validation["status"] = "blocked"
    if phase_closeout["status"] != "ready":
        validation["errors"].append("phase_closeout_not_ready")
        validation["status"] = "blocked"
    db_result = None
    if args.write:
        atomic_write_json(CONTRACT_JSON, contract)
        atomic_write_json(SCENARIO_LIBRARY_JSON, scenarios)
        atomic_write_json(PM_DECISION_PACKET_JSON, pm_packet)
        atomic_write_json(CUSTOMER_PREVIEW_JSON, preview)
        CUSTOMER_PREVIEW_MD.write_text(rendered_preview, encoding="utf-8")
        atomic_write_json(CUSTOMER_PREVIEW_VALIDATION_JSON, preview_validation)
        atomic_write_json(PILOT_DECISION_PACKET_JSON, pilot_packet)
        atomic_write_json(LEAD_RESCUE_SERVICE_PACKET_JSON, lead_rescue_service_packet)
        LEAD_RESCUE_SERVICE_PACKET_MD.write_text(rendered_lead_rescue_service_packet, encoding="utf-8")
        atomic_write_json(LEAD_RESCUE_SERVICE_PACKET_VALIDATION_JSON, lead_rescue_service_packet_validation)
        atomic_write_json(AUTOMATION_BLUEPRINTS_JSON, automation_blueprints)
        atomic_write_json(AUTOMATION_BLUEPRINTS_VALIDATION_JSON, automation_blueprints_validation)
        atomic_write_json(SMB_SERVICE_STATE_JSON, smb_service_state)
        atomic_write_json(SMB_SERVICE_STATE_VALIDATION_JSON, smb_service_state_validation)
        atomic_write_json(OFFER_ICP_JSON, offer_icp_packet)
        OFFER_ICP_MD.write_text(rendered_offer_icp, encoding="utf-8")
        atomic_write_json(DEMO_PACKETS_JSON, demo_packets)
        DEMO_PACKETS_MD.write_text(rendered_demo_packets, encoding="utf-8")
        atomic_write_json(DEMO_PACKETS_VALIDATION_JSON, demo_packets_validation)
        atomic_write_json(MARKETING_OPS_BLUEPRINTS_JSON, marketing_ops_blueprints)
        atomic_write_json(MARKETING_OPS_BLUEPRINTS_VALIDATION_JSON, marketing_ops_blueprints_validation)
        atomic_write_json(SALES_PRACTICE_JSON, sales_practice)
        SALES_PRACTICE_MD.write_text(rendered_sales_practice, encoding="utf-8")
        atomic_write_json(OUTREACH_KIT_JSON, outreach_kit)
        OUTREACH_KIT_MD.write_text(rendered_outreach_kit, encoding="utf-8")
        atomic_write_json(PILOT_SCOPE_INTAKE_JSON, pilot_scope_intake)
        PILOT_SCOPE_INTAKE_MD.write_text(rendered_pilot_scope_intake, encoding="utf-8")
        atomic_write_json(VERTICAL_ICP_TARGETING_JSON, vertical_icp_targeting)
        VERTICAL_ICP_TARGETING_MD.write_text(rendered_vertical_icp_targeting, encoding="utf-8")
        atomic_write_json(DEMO_POLISH_PACKET_JSON, demo_polish_packet)
        DEMO_POLISH_PACKET_MD.write_text(rendered_demo_polish_packet, encoding="utf-8")
        atomic_write_json(OUTREACH_PREP_VALIDATION_JSON, outreach_prep_validation)
        atomic_write_json(PILOT_READINESS_PACKET_JSON, pilot_readiness_packet)
        PILOT_READINESS_PACKET_MD.write_text(rendered_pilot_readiness_packet, encoding="utf-8")
        atomic_write_json(SALES_CONVERSATION_DRILL_JSON, sales_conversation_drill)
        SALES_CONVERSATION_DRILL_MD.write_text(rendered_sales_conversation_drill, encoding="utf-8")
        atomic_write_json(DEMO_SELECTION_TREE_JSON, demo_selection_tree)
        DEMO_SELECTION_TREE_MD.write_text(rendered_demo_selection_tree, encoding="utf-8")
        atomic_write_json(VERTICAL_TEST_FRAMEWORK_JSON, vertical_test_framework)
        VERTICAL_TEST_FRAMEWORK_MD.write_text(rendered_vertical_test_framework, encoding="utf-8")
        atomic_write_json(PILOT_READINESS_VALIDATION_JSON, pilot_readiness_validation)
        atomic_write_json(ROLLOUT_READINESS_PLAN_JSON, rollout_readiness_plan)
        ROLLOUT_READINESS_PLAN_MD.write_text(rendered_rollout_readiness_plan, encoding="utf-8")
        atomic_write_json(CLIENT_ROLLOUT_CHECKLIST_JSON, client_rollout_checklist)
        CLIENT_ROLLOUT_CHECKLIST_MD.write_text(rendered_client_rollout_checklist, encoding="utf-8")
        atomic_write_json(CURRICULUM_MAP_JSON, curriculum_map)
        CURRICULUM_MAP_MD.write_text(rendered_curriculum_map, encoding="utf-8")
        atomic_write_json(ROLLOUT_READINESS_VALIDATION_JSON, rollout_readiness_validation)
        atomic_write_json(DELIVERABLE_GATE_JSON, deliverable_gate_sprint)
        DELIVERABLE_GATE_MD.write_text(rendered_deliverable_gate, encoding="utf-8")
        atomic_write_json(DELIVERABLE_GATE_VALIDATION_JSON, deliverable_gate_validation)
        atomic_write_json(COCKPIT_PANEL_JSON, cockpit_panel)
        COCKPIT_PANEL_HTML.write_text(rendered_cockpit_panel, encoding="utf-8")
        atomic_write_json(PHASE_CLOSEOUT_JSON, phase_closeout)
    if args.write_db:
        db_path = Path(args.db)
        if not db_path.is_absolute():
            db_path = ROOT / db_path
        db_result = rebuild_sqlite(
            contract,
            scenarios,
            pm_packet,
            preview,
            preview_validation,
            pilot_packet,
            lead_rescue_service_packet,
            lead_rescue_service_packet_validation,
            automation_blueprints,
            automation_blueprints_validation,
            smb_service_state,
            smb_service_state_validation,
            offer_icp_packet,
            demo_packets,
            demo_packets_validation,
            marketing_ops_blueprints,
            marketing_ops_blueprints_validation,
            cockpit_panel,
            sales_practice,
            outreach_kit,
            pilot_scope_intake,
            vertical_icp_targeting,
            demo_polish_packet,
            outreach_prep_validation,
            pilot_readiness_packet,
            sales_conversation_drill,
            demo_selection_tree,
            vertical_test_framework,
            pilot_readiness_validation,
            rollout_readiness_plan,
            client_rollout_checklist,
            curriculum_map,
            rollout_readiness_validation,
            deliverable_gate_sprint,
            deliverable_gate_validation,
            phase_closeout,
            db_path,
        )
    result = {
        "status": validation["status"],
        "generated_at_utc": generated_at,
        "outputs": {
            "contract": rel(CONTRACT_JSON),
            "scenario_library": rel(SCENARIO_LIBRARY_JSON),
            "pm_decision_packet": rel(PM_DECISION_PACKET_JSON),
            "customer_preview": rel(CUSTOMER_PREVIEW_JSON),
            "customer_preview_md": rel(CUSTOMER_PREVIEW_MD),
            "customer_preview_validation": rel(CUSTOMER_PREVIEW_VALIDATION_JSON),
            "pilot_decision_packet": rel(PILOT_DECISION_PACKET_JSON),
            "lead_rescue_service_packet": rel(LEAD_RESCUE_SERVICE_PACKET_JSON),
            "lead_rescue_service_packet_md": rel(LEAD_RESCUE_SERVICE_PACKET_MD),
            "lead_rescue_service_packet_validation": rel(LEAD_RESCUE_SERVICE_PACKET_VALIDATION_JSON),
            "automation_blueprints": rel(AUTOMATION_BLUEPRINTS_JSON),
            "automation_blueprints_validation": rel(AUTOMATION_BLUEPRINTS_VALIDATION_JSON),
            "smb_service_state": rel(SMB_SERVICE_STATE_JSON),
            "smb_service_state_validation": rel(SMB_SERVICE_STATE_VALIDATION_JSON),
            "offer_icp_packet": rel(OFFER_ICP_JSON),
            "offer_icp_packet_md": rel(OFFER_ICP_MD),
            "demo_packets": rel(DEMO_PACKETS_JSON),
            "demo_packets_md": rel(DEMO_PACKETS_MD),
            "demo_packets_validation": rel(DEMO_PACKETS_VALIDATION_JSON),
            "marketing_ops_blueprints": rel(MARKETING_OPS_BLUEPRINTS_JSON),
            "marketing_ops_blueprints_validation": rel(MARKETING_OPS_BLUEPRINTS_VALIDATION_JSON),
            "cockpit_panel": rel(COCKPIT_PANEL_JSON),
            "cockpit_panel_html": rel(COCKPIT_PANEL_HTML),
            "sales_practice_packet": rel(SALES_PRACTICE_JSON),
            "sales_practice_packet_md": rel(SALES_PRACTICE_MD),
            "outreach_kit": rel(OUTREACH_KIT_JSON),
            "outreach_kit_md": rel(OUTREACH_KIT_MD),
            "pilot_scope_intake": rel(PILOT_SCOPE_INTAKE_JSON),
            "pilot_scope_intake_md": rel(PILOT_SCOPE_INTAKE_MD),
            "vertical_icp_targeting": rel(VERTICAL_ICP_TARGETING_JSON),
            "vertical_icp_targeting_md": rel(VERTICAL_ICP_TARGETING_MD),
            "demo_polish_packet": rel(DEMO_POLISH_PACKET_JSON),
            "demo_polish_packet_md": rel(DEMO_POLISH_PACKET_MD),
            "outreach_prep_validation": rel(OUTREACH_PREP_VALIDATION_JSON),
            "pilot_readiness_packet": rel(PILOT_READINESS_PACKET_JSON),
            "pilot_readiness_packet_md": rel(PILOT_READINESS_PACKET_MD),
            "sales_conversation_drill": rel(SALES_CONVERSATION_DRILL_JSON),
            "sales_conversation_drill_md": rel(SALES_CONVERSATION_DRILL_MD),
            "demo_selection_tree": rel(DEMO_SELECTION_TREE_JSON),
            "demo_selection_tree_md": rel(DEMO_SELECTION_TREE_MD),
            "vertical_test_framework": rel(VERTICAL_TEST_FRAMEWORK_JSON),
            "vertical_test_framework_md": rel(VERTICAL_TEST_FRAMEWORK_MD),
            "pilot_readiness_validation": rel(PILOT_READINESS_VALIDATION_JSON),
            "rollout_readiness_plan": rel(ROLLOUT_READINESS_PLAN_JSON),
            "rollout_readiness_plan_md": rel(ROLLOUT_READINESS_PLAN_MD),
            "client_rollout_checklist": rel(CLIENT_ROLLOUT_CHECKLIST_JSON),
            "client_rollout_checklist_md": rel(CLIENT_ROLLOUT_CHECKLIST_MD),
            "curriculum_map": rel(CURRICULUM_MAP_JSON),
            "curriculum_map_md": rel(CURRICULUM_MAP_MD),
            "rollout_readiness_validation": rel(ROLLOUT_READINESS_VALIDATION_JSON),
            "deliverable_gate_sprint": rel(DELIVERABLE_GATE_JSON),
            "deliverable_gate_sprint_md": rel(DELIVERABLE_GATE_MD),
            "deliverable_gate_validation": rel(DELIVERABLE_GATE_VALIDATION_JSON),
            "phase_closeout": rel(PHASE_CLOSEOUT_JSON),
            "summary": rel(PIVOT_SUMMARY_JSON),
            "sqlite": db_result,
        },
        "validation": validation,
    }
    if args.write:
        atomic_write_json(PIVOT_SUMMARY_JSON, result)
    print(json.dumps(result, indent=2))
    if args.validate and (validation["status"] != "ok" or (db_result and db_result["status"] != "ok")):
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
