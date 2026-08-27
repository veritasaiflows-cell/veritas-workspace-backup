#!/usr/bin/env python3
"""Build the WF75 AI Workflow Clarity Sprint synthetic demo stack.

The generated assets are internal proof only. They use fictional data and do
not authorize outreach, payment collection, customer delivery, credentials,
external channel binding, cron dispatch, or finance/account action.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, atomic_write_text, load_json_artifact

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
OUT_DIR = TMP / "wf75-missed-lead-demo-v1"
BOARD_PATH = ROOT / "state" / "ai-drop-service-os" / "team-board.json"
DELIVERABLE_PATH = ROOT / "10. Deliverables" / "AI Drop-Service OS" / "AI Workflow Clarity Sprint Synthetic Demo - 2026-07-03.md"
CONTINUITY_PATH = (
    ROOT
    / "06. Playbooks"
    / "Project Continuity"
    / "Workflow 75 - AI Workflow Clarity Sprint Demo Stack - 2026-07-03.md"
)

SCHEMA = "veritas.wf75.ai_drop_service_os.missed_lead_demo.v1"
GENERATED_AT = "2026-07-03T18:30:00Z"

REQUIRED_FALSE_AUTHORITY = {
    "external_outreach_allowed",
    "customer_or_public_delivery_allowed",
    "payment_collection_allowed",
    "vendor_account_setup_allowed",
    "channel_binding_allowed",
    "cron_dispatch_allowed",
    "config_auth_runtime_mutation_allowed",
    "real_customer_data_allowed",
    "client_credentials_allowed",
    "finance_or_account_action_allowed",
    "paper_or_live_execution_allowed",
    "owner_approval_inferred",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def authority_boundary() -> dict[str, Any]:
    return {
        "internal_build_allowed": True,
        "synthetic_demo_allowed": True,
        "public_research_allowed": True,
        "draft_sales_assets_allowed": True,
        "external_outreach_allowed": False,
        "customer_or_public_delivery_allowed": False,
        "payment_collection_allowed": False,
        "vendor_account_setup_allowed": False,
        "channel_binding_allowed": False,
        "cron_dispatch_allowed": False,
        "config_auth_runtime_mutation_allowed": False,
        "real_customer_data_allowed": False,
        "client_credentials_allowed": False,
        "finance_or_account_action_allowed": False,
        "paper_or_live_execution_allowed": False,
        "owner_approval_inferred": False,
    }


def build_payload() -> dict[str, Any]:
    scenario = {
        "scenario_id": "synthetic-missed-lead-home-services-v1",
        "status": "internal_synthetic_proof_only",
        "fictional_business": "Desert Ridge Home Repair",
        "fictional_contact": "Jordan Sample",
        "fictional_phone": "+1-555-0100",
        "fictional_email": "jordan.sample@example.invalid",
        "buyer_type": "small local home-services operator",
        "pain": "Inbound requests arrive through a web form, voicemail, and shared email, but nobody owns a 15-minute response loop.",
        "business_hours": "08:00-17:00 local time, Monday-Friday",
        "no_real_customer_data": True,
        "sensitive_data_used": False,
    }
    lead_events = [
        {
            "event_id": "form-001",
            "time_local": "2026-07-03 09:02",
            "channel": "website_form",
            "summary": "Customer asks for same-day AC repair estimate.",
            "status_before_demo": "notification buried in shared inbox",
            "expected_response_by": "2026-07-03 09:17",
        },
        {
            "event_id": "voice-001",
            "time_local": "2026-07-03 09:11",
            "channel": "voicemail",
            "summary": "Customer leaves callback number and says home office is getting hot.",
            "status_before_demo": "voicemail checked after lunch",
            "expected_response_by": "2026-07-03 09:26",
        },
        {
            "event_id": "email-001",
            "time_local": "2026-07-03 09:48",
            "channel": "shared_email",
            "summary": "Customer replies with availability window and asks if today is possible.",
            "status_before_demo": "no owner assigned",
            "expected_response_by": "2026-07-03 10:03",
        },
    ]
    workflow_map = [
        {
            "step": "capture",
            "current_state": "Form, voicemail, and email land in separate places.",
            "target_state": "Every inbound request becomes one lead record with timestamp, source, and callback needed flag.",
        },
        {
            "step": "triage",
            "current_state": "Nobody classifies urgency or same-day opportunity.",
            "target_state": "Lead is tagged same-day, routine, or low-fit using a reviewed rule set.",
        },
        {
            "step": "acknowledge",
            "current_state": "Customer may wait hours without knowing the request was received.",
            "target_state": "Safe acknowledgement goes out after human review or approved automation path.",
        },
        {
            "step": "assign",
            "current_state": "No owner or escalation timer exists.",
            "target_state": "One responsible person is assigned before the 15-minute SLA expires.",
        },
        {
            "step": "escalate",
            "current_state": "Unanswered leads remain invisible.",
            "target_state": "Unclaimed leads escalate at 10 and 15 minutes with timestamped proof.",
        },
        {
            "step": "review",
            "current_state": "Lost leads are not reviewed weekly.",
            "target_state": "Weekly review shows response time, dropped requests, and process fixes.",
        },
    ]
    acknowledgement_copy = {
        "status": "draft_internal_only",
        "safe_copy": (
            "Thanks, we received your request. A team member will review it and contact you within "
            "15 minutes during business hours. Please do not send payment details, passwords, or sensitive "
            "personal information through this message thread."
        ),
        "forbidden_copy_patterns": [
            "guaranteed same-day repair",
            "approved estimate before review",
            "send payment details",
            "send account passwords",
            "we guarantee more booked jobs",
        ],
    }
    escalation_path = [
        {
            "minute": 0,
            "event": "lead_received",
            "proof": "capture timestamp and source channel",
        },
        {
            "minute": 5,
            "event": "triage_pending_check",
            "proof": "if no owner, mark at-risk",
        },
        {
            "minute": 10,
            "event": "owner_escalation",
            "proof": "notify owner/operator in internal queue only",
        },
        {
            "minute": 15,
            "event": "sla_breach",
            "proof": "record breach, reason, and next human action",
        },
        {
            "minute": 1440,
            "event": "daily_review",
            "proof": "count missed, delayed, and resolved leads",
        },
    ]
    business_hours_state_machine = {
        "timezone": "America/Phoenix",
        "states": [
            {
                "state": "in_hours",
                "condition": "lead timestamp is Monday-Friday 08:00-17:00 local time",
                "timer_start": "lead_received_at",
                "acknowledgement_copy": "standard_15_minute_business_hours_copy",
            },
            {
                "state": "after_hours",
                "condition": "lead timestamp is outside same-day business hours",
                "timer_start": "next_open_window_start",
                "acknowledgement_copy": "after_hours_copy",
            },
            {
                "state": "closed_or_holiday",
                "condition": "business is closed for a listed holiday or closure",
                "timer_start": "next_open_window_start",
                "acknowledgement_copy": "closed_copy",
            },
        ],
        "after_hours_copy": (
            "Thanks, we received your request after business hours. A team member will review it "
            "when we reopen and contact you during the next business window. Please do not send "
            "payment details, passwords, or sensitive personal information through this message thread."
        ),
        "timer_rule": "The 15-minute first-human-touch timer starts immediately during business hours and at the next open window for after-hours or closed-window leads.",
    }
    triage_rule_set = {
        "status": "internal_demo_rule_set",
        "tags": [
            {
                "tag": "same_day",
                "definition": "Customer asks for help today, mentions urgent comfort/safety loss, or gives immediate availability.",
                "response_target": "first human touch within 15 business-hours minutes",
            },
            {
                "tag": "routine",
                "definition": "Customer requests non-urgent estimate, maintenance, or next-available appointment.",
                "response_target": "same business day when received before 15:00 local time",
            },
            {
                "tag": "low_fit",
                "definition": "Request is outside service area, unrelated to offered services, or lacks enough contact information.",
                "response_target": "human review before rejection or alternate referral",
            },
        ],
        "worked_examples": [
            {
                "event_id": "form-001",
                "input_signal": "same-day AC repair estimate",
                "tag": "same_day",
                "reason": "same-day language and AC repair imply time-sensitive service opportunity",
            },
            {
                "event_id": "voice-001",
                "input_signal": "home office is getting hot",
                "tag": "same_day",
                "reason": "comfort disruption and callback request justify priority review",
            },
            {
                "event_id": "email-001",
                "input_signal": "availability window and asks if today is possible",
                "tag": "same_day",
                "reason": "today availability increases response urgency",
            },
        ],
        "exclusions": [
            "Do not infer safety emergency handling.",
            "Do not quote price or availability without human review.",
            "Do not reject a lead automatically in the demo.",
        ],
    }
    normalized_lead_records = [
        {
            "lead_id": "lead-001",
            "source_event_ids": ["form-001", "voice-001", "email-001"],
            "received_at_local": "2026-07-03 09:02",
            "state": "in_hours",
            "customer_name": "Jordan Sample",
            "phone": "+1-555-0100",
            "email": "jordan.sample@example.invalid",
            "request_summary": "Same-day AC repair estimate; customer has callback number and today availability.",
            "triage_tag": "same_day",
            "owner": "fictional_dispatch_owner",
            "first_touch_due_local": "2026-07-03 09:17",
            "sensitive_data_present": False,
        }
    ]
    acknowledgement_decisions = [
        {
            "lead_id": "lead-001",
            "state": "in_hours",
            "decision": "send_standard_acknowledgement_after_human_review",
            "copy_key": "standard_15_minute_business_hours_copy",
            "blocked_terms_checked": ["guarantee", "price quote", "payment details", "passwords"],
        },
        {
            "lead_id": "lead-after-hours-example",
            "state": "after_hours",
            "decision": "send_after_hours_acknowledgement_after_human_review",
            "copy_key": "after_hours_copy",
            "timer_start": "next_open_window_start",
        },
    ]
    executed_escalation_trail = [
        {
            "lead_id": "lead-001",
            "time_local": "2026-07-03 09:02",
            "event": "lead_received",
            "state": "in_hours",
            "proof": "normalized lead record created",
        },
        {
            "lead_id": "lead-001",
            "time_local": "2026-07-03 09:07",
            "event": "triage_pending_check",
            "state": "in_hours",
            "proof": "lead marked at-risk because no owner acknowledgement recorded",
        },
        {
            "lead_id": "lead-001",
            "time_local": "2026-07-03 09:12",
            "event": "owner_escalation",
            "state": "in_hours",
            "proof": "fictional dispatch owner notification staged internally",
        },
        {
            "lead_id": "lead-001",
            "time_local": "2026-07-03 09:17",
            "event": "sla_breach",
            "state": "in_hours",
            "proof": "breach recorded because no first-human-touch timestamp exists",
        },
    ]
    daily_operational_digest = {
        "digest_id": "daily-digest-20260703",
        "purpose": "Daily operational cleanup, not weekly improvement review.",
        "date_local": "2026-07-03",
        "lead_count": 1,
        "same_day_count": 1,
        "sla_breach_count": 1,
        "oldest_unresolved_lead": "lead-001",
        "operator_next_action": "Call Jordan Sample and record outcome in the fictional demo log.",
    }
    weekly_improvement_backlog = [
        {
            "backlog_id": "weekly-001",
            "purpose": "Weekly retrospective improvement item.",
            "issue": "No single owner for form, voicemail, and shared email intake.",
            "recommended_fix": "Assign one daily dispatch owner and backup owner.",
            "evidence": "lead-001 breached the synthetic first-touch SLA.",
            "risk": "medium",
        },
        {
            "backlog_id": "weekly-002",
            "purpose": "Weekly retrospective improvement item.",
            "issue": "No after-hours acknowledgement branch existed before this demo.",
            "recommended_fix": "Adopt explicit in-hours and after-hours copy paths before any pilot.",
            "evidence": "QA risk from timing ambiguity.",
            "risk": "medium",
        },
    ]
    opportunity_matrix = [
        {
            "rank": 1,
            "candidate": "Unified lead intake checklist",
            "value": "high",
            "effort": "low",
            "risk": "low",
            "demo_output": "structured callback checklist from form or voicemail text",
        },
        {
            "rank": 2,
            "candidate": "15-minute SLA timer",
            "value": "high",
            "effort": "medium",
            "risk": "medium",
            "demo_output": "timestamped escalation trail",
        },
        {
            "rank": 3,
            "candidate": "Safe acknowledgement template",
            "value": "medium",
            "effort": "low",
            "risk": "medium",
            "demo_output": "approved copy with no sensitive-data request",
        },
        {
            "rank": 4,
            "candidate": "Daily missed-lead review digest",
            "value": "medium",
            "effort": "medium",
            "risk": "low",
            "demo_output": "operator digest with lead age and owner",
        },
        {
            "rank": 5,
            "candidate": "Weekly workflow improvement backlog",
            "value": "medium",
            "effort": "low",
            "risk": "low",
            "demo_output": "ranked fixes with owner and next step",
        },
    ]
    claim_register = [
        {
            "claim": "Slow response can plausibly contribute to missed service opportunities.",
            "status": "allowed_as_general_hypothesis",
            "proof_needed_before_customer_claim": "source-backed lead-response evidence and customer-specific baseline",
        },
        {
            "claim": "This workflow can reduce response latency.",
            "status": "internal_demo_only",
            "proof_needed_before_customer_claim": "live pilot timing data",
        },
        {
            "claim": "This will increase booked jobs or revenue.",
            "status": "blocked",
            "reason": "requires historical baseline, pilot data, and cannot be guaranteed",
        },
        {
            "claim": "This is security, legal, tax, or compliance ready.",
            "status": "blocked",
            "reason": "requires separate expert review and implementation proof",
        },
    ]
    source_support = [
        {
            "finding": "CRM forms can centralize lead capture and trigger follow-up actions.",
            "source": "HubSpot form docs",
            "url": "https://knowledge.hubspot.com/forms/create-and-edit-forms",
            "confidence": "high",
            "supports": ["capture", "lead record creation", "follow-up workflow"],
        },
        {
            "finding": "No-code SMS workflows can send and receive texts for follow-up flows.",
            "source": "Twilio Studio SMS quickstart",
            "url": "https://www.twilio.com/docs/messaging/quickstart/no-code-sms-studio-quickstart",
            "confidence": "high",
            "supports": ["acknowledgement", "callback workflow", "workflow prototype"],
        },
        {
            "finding": "Automation platforms can notify owners about workflow errors or task limits.",
            "source": "Zapier Manager docs",
            "url": "https://help.zapier.com/hc/en-us/articles/8496310892301-Manage-your-account-and-Zaps-with-Zapier-Manager",
            "confidence": "high",
            "supports": ["owner notification", "operational monitoring"],
        },
        {
            "finding": "Workflow history can support troubleshooting, audit, and task-usage review.",
            "source": "Zap history docs",
            "url": "https://help.zapier.com/hc/en-us/articles/8496291148685-View-and-manage-your-Zap-history",
            "confidence": "high",
            "supports": ["audit trail", "daily review", "proof packet"],
        },
        {
            "finding": "Log streams can send run-level success, failure, and config-change events.",
            "source": "Zap log streams docs",
            "url": "https://help.zapier.com/hc/en-us/articles/43732241361421-Set-up-log-streams-to-monitor-Zap-activity",
            "confidence": "high",
            "supports": ["monitoring", "alerting", "escalation proof"],
        },
        {
            "finding": "Missed-call reports and quick text replies are plausible category examples.",
            "source": "CallRail unanswered calls and quick texts help pages",
            "url": "https://support.callrail.com/",
            "confidence": "medium_snippet_level",
            "supports": ["missed-call visibility", "text follow-up"],
            "limitation": "Page fetch was blocked by 403 in the Research Scout pass; keep this as snippet-level support only.",
        },
    ]
    research_evidence = [
        {
            "source": "HubSpot form docs",
            "url": "https://knowledge.hubspot.com/forms/create-and-edit-forms",
            "fetched_or_reviewed_at": "2026-07-03",
            "evidence_type": "official_docs_summary",
            "evidence_snippet": "Forms collect visitor information and can create or update CRM records and trigger follow-up actions.",
            "confidence": "high",
        },
        {
            "source": "Twilio Studio SMS quickstart",
            "url": "https://www.twilio.com/docs/messaging/quickstart/no-code-sms-studio-quickstart",
            "fetched_or_reviewed_at": "2026-07-03",
            "evidence_type": "official_docs_summary",
            "evidence_snippet": "Twilio Studio supports visual flows that send and receive SMS messages.",
            "confidence": "high",
        },
        {
            "source": "Zapier Manager docs",
            "url": "https://help.zapier.com/hc/en-us/articles/8496310892301-Manage-your-account-and-Zaps-with-Zapier-Manager",
            "fetched_or_reviewed_at": "2026-07-03",
            "evidence_type": "official_docs_summary",
            "evidence_snippet": "Zapier Manager can notify about Zap errors and task usage limits.",
            "confidence": "high",
        },
        {
            "source": "Zap history docs",
            "url": "https://help.zapier.com/hc/en-us/articles/8496291148685-View-and-manage-your-Zap-history",
            "fetched_or_reviewed_at": "2026-07-03",
            "evidence_type": "official_docs_summary",
            "evidence_snippet": "Zap history logs workflow runs and can support troubleshooting and task review.",
            "confidence": "high",
        },
        {
            "source": "Zap log streams docs",
            "url": "https://help.zapier.com/hc/en-us/articles/43732241361421-Set-up-log-streams-to-monitor-Zap-activity",
            "fetched_or_reviewed_at": "2026-07-03",
            "evidence_type": "official_docs_summary",
            "evidence_snippet": "Log streams can send real-time run outcome and configuration-change events.",
            "confidence": "high",
        },
        {
            "source": "CallRail help pages",
            "url": "https://support.callrail.com/",
            "fetched_or_reviewed_at": "2026-07-03",
            "evidence_type": "public_search_snippet_only",
            "evidence_snippet": "Public search snippets referenced unanswered-call reporting and quick text replies.",
            "confidence": "medium_snippet_level",
            "limitation": "Fetch blocked by 403; do not treat as audit-grade support.",
        },
    ]
    unsupported_claims = [
        "The exact 15-minute first-human-touch SLA as a universal best practice.",
        "The specific 5/10/15/1440-minute escalation schedule as externally validated.",
        "Any guarantee that this workflow will increase booked jobs, revenue, or conversion rate.",
        "Any claim that the synthetic business, contacts, or event times reflect a real customer situation.",
        "Any claim that the safe acknowledgement copy is compliant for all businesses or regulated contexts.",
        "Any claim that weekly review alone will reduce missed leads without pilot data.",
    ]
    data_boundary_manifest = {
        "public": {
            "allowed": True,
            "examples": ["business website copy", "public pricing pages", "published tool docs"],
        },
        "internal_synthetic": {
            "allowed": True,
            "examples": ["fictional lead events", "example.invalid email", "555 phone number"],
        },
        "customer_confidential": {
            "allowed": False,
            "examples": ["real customer names", "real call recordings", "real CRM exports"],
            "gate": "explicit scoped owner approval plus retention/redaction plan",
        },
        "regulated_or_sensitive": {
            "allowed": False,
            "examples": ["tax records", "medical data", "financial account data", "legal matters"],
            "gate": "separate regulated-data workflow and approval",
        },
        "credentials_or_secrets": {
            "allowed": False,
            "examples": ["passwords", "API keys", "OAuth tokens", "brokerage credentials"],
            "gate": "blocked for this demo",
        },
    }
    action_ledger = [
        {
            "action": "build_synthetic_demo",
            "authority_class": "auto_safe_internal",
            "status": "implemented_by_generator",
        },
        {
            "action": "run_research_scout",
            "authority_class": "review_only_internal",
            "status": "completed_internal_source_support_pass",
        },
        {
            "action": "run_qa_redteam",
            "authority_class": "review_only_internal",
            "status": "completed_internal_demo_recheck",
        },
        {
            "action": "send_outreach",
            "authority_class": "owner_gated",
            "status": "not_approved",
        },
        {
            "action": "collect_payment",
            "authority_class": "owner_gated",
            "status": "not_approved",
        },
        {
            "action": "use_real_customer_data",
            "authority_class": "owner_gated_sensitive",
            "status": "not_approved",
        },
    ]
    agent_validation_evidence = {
        "research_scout": {
            "agent_id": "research-scout",
            "session_key": "agent:research-scout:wf75-missed-lead-demo-v1-research-20260703",
            "run_id": "e5ec5065-2e47-4524-abb2-30c5816a6de1",
            "session_id": "c629ca77-ecdf-44ee-9d66-f8bfd038e22f",
            "verdict": "tool_and_source_support_integrated",
            "accepted_findings": [
                "HubSpot, Twilio, Zapier, and Zap log/history docs support the category mechanics.",
                "CallRail support is snippet-level only because direct fetch was blocked.",
            ],
            "limits": [
                "Does not prove buyer demand, conversion lift, revenue lift, or the 15-minute SLA benchmark.",
            ],
        },
        "qa_redteam_initial": {
            "agent_id": "qa-redteam",
            "session_key": "agent:qa-redteam:wf75-missed-lead-demo-v1-qa-20260703",
            "run_id": "61346840-2fe7-4b51-8ece-1817457f4a24",
            "verdict": "blocked_before_synthetic_outputs_and_timing_fixes",
            "resolved_findings": [
                "missing executed synthetic outputs",
                "missing after-hours/weekend timing logic",
                "missing triage rule set",
                "daily versus weekly review ambiguity",
            ],
        },
        "qa_redteam_recheck": {
            "agent_id": "qa-redteam",
            "session_key": "agent:qa-redteam:wf75-missed-lead-demo-v1-qa-recheck-20260703",
            "run_id": "245ae3b5-432f-4f7a-a490-f23757642e83",
            "session_id": "f35eb82e-e67b-4f86-9bf3-988c622aa0f6",
            "verdict": "internal_demo_ready",
            "remaining_findings": [
                "Need problem/outcome evidence before private-pilot-prep-ready.",
                "Keep 15-minute SLA and 5/10/15/1440 cadence framed as internal hypotheses.",
                "No booked-job, revenue, compliance, or conversion claim is supported.",
            ],
        },
    }
    private_pilot_approval_card = {
        "status": "draft_not_approved",
        "decision": "Approve a private beta pilot test for AI Workflow Clarity Sprint.",
        "price": "$500-$750",
        "target": "one low-regulation local service business with missed-lead or slow-intake pain",
        "scope": "one workflow, diagnostic only, no production changes, no credentials",
        "delivery_window": "5 business days",
        "owner_must_approve_before": [
            "choosing a real target/contact",
            "sending outreach",
            "collecting payment",
            "receiving real business data",
            "using any external tool/account",
        ],
    }
    payload = {
        "schema": SCHEMA,
        "generated_at_utc": GENERATED_AT,
        "runtime_generated_at_utc": utc_now(),
        "workflow_id": "WF75",
        "workstream_id": "AI-DROP-SERVICE-OS-DEMO-V1-20260703",
        "status": "internal_demo_ready_private_pilot_not_ready",
        "offer": "AI Workflow Clarity Sprint",
        "scenario": scenario,
        "lead_events": lead_events,
        "sla": {
            "first_human_touch_minutes": 15,
            "business_hours_only": True,
            "approval_status": "internal_demo_rule_not_customer_contract",
        },
        "workflow_map": workflow_map,
        "business_hours_state_machine": business_hours_state_machine,
        "triage_rule_set": triage_rule_set,
        "normalized_lead_records": normalized_lead_records,
        "acknowledgement_decisions": acknowledgement_decisions,
        "acknowledgement_copy": acknowledgement_copy,
        "escalation_path": escalation_path,
        "executed_escalation_trail": executed_escalation_trail,
        "daily_operational_digest": daily_operational_digest,
        "weekly_improvement_backlog": weekly_improvement_backlog,
        "opportunity_matrix": opportunity_matrix,
        "claim_register": claim_register,
        "source_support": source_support,
        "research_evidence": research_evidence,
        "unsupported_claims": unsupported_claims,
        "data_boundary_manifest": data_boundary_manifest,
        "authority_boundary": authority_boundary(),
        "action_ledger": action_ledger,
        "agent_validation_evidence": agent_validation_evidence,
        "private_pilot_approval_card": private_pilot_approval_card,
        "pilot_readiness_gate": {
            "status": "internal_demo_ready_private_pilot_prep_not_ready",
            "required_before_private_pilot_prep": [
                "source-backed evidence for missed-lead and slow-response business impact",
                "source-backed benchmark or explicitly hypothetical framing for the 15-minute SLA",
                "source-backed benchmark or explicitly hypothetical framing for the 5/10/15/1440 cadence",
                "one-page offer and intake/discovery script",
                "Randall exact approval for outreach/payment/customer data",
            ],
            "completed_internal_demo_requirements": [
                "executed synthetic artifacts present",
                "research evidence packet attached",
                "triage rubric and worked examples present",
                "business-hours and after-hours logic present",
                "daily digest and weekly retrospective separated",
                "QA Red-Team recheck classified the packet as internal-demo-ready",
            ],
        },
        "next_agent_loop": [
            "research-scout problem/outcome evidence pass before private-pilot prep",
            "Veritas one-page offer and intake script draft",
            "qa-redteam review before any customer-facing claim or pilot approval card",
        ],
    }
    payload["validation"] = validate_payload(payload)
    return payload


def validate_payload(payload: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    if payload.get("schema") != SCHEMA:
        errors.append("schema_mismatch")
    boundary = payload.get("authority_boundary", {})
    for key in REQUIRED_FALSE_AUTHORITY:
        if boundary.get(key) is not False:
            errors.append(f"authority_{key}_not_false")
    scenario = payload.get("scenario", {})
    if scenario.get("no_real_customer_data") is not True:
        errors.append("scenario_must_mark_no_real_customer_data")
    if scenario.get("sensitive_data_used") is not False:
        errors.append("scenario_sensitive_data_used_not_false")
    if len(payload.get("lead_events", [])) < 3:
        errors.append("lead_event_count_below_3")
    if len(payload.get("workflow_map", [])) < 5:
        errors.append("workflow_map_too_short")
    if not payload.get("business_hours_state_machine", {}).get("states"):
        errors.append("business_hours_state_machine_missing")
    state_names = {row.get("state") for row in payload.get("business_hours_state_machine", {}).get("states", [])}
    for required_state in {"in_hours", "after_hours", "closed_or_holiday"}:
        if required_state not in state_names:
            errors.append(f"business_hours_state_missing={required_state}")
    if len(payload.get("triage_rule_set", {}).get("worked_examples", [])) < 3:
        errors.append("triage_worked_examples_below_3")
    if not payload.get("normalized_lead_records"):
        errors.append("normalized_lead_records_missing")
    if not payload.get("acknowledgement_decisions"):
        errors.append("acknowledgement_decisions_missing")
    if len(payload.get("executed_escalation_trail", [])) < 4:
        errors.append("executed_escalation_trail_too_short")
    if not payload.get("daily_operational_digest"):
        errors.append("daily_operational_digest_missing")
    if not payload.get("weekly_improvement_backlog"):
        errors.append("weekly_improvement_backlog_missing")
    if len(payload.get("opportunity_matrix", [])) < 5:
        errors.append("opportunity_matrix_too_short")
    if len(payload.get("source_support", [])) < 5:
        errors.append("source_support_below_5")
    if len(payload.get("research_evidence", [])) < 5:
        errors.append("research_evidence_below_5")
    if not payload.get("unsupported_claims"):
        errors.append("unsupported_claims_missing")
    agent_evidence = payload.get("agent_validation_evidence", {})
    if agent_evidence.get("qa_redteam_recheck", {}).get("verdict") != "internal_demo_ready":
        errors.append("qa_redteam_recheck_verdict_missing")
    if agent_evidence.get("research_scout", {}).get("verdict") != "tool_and_source_support_integrated":
        errors.append("research_scout_verdict_missing")
    ack = str(payload.get("acknowledgement_copy", {}).get("safe_copy", "")).lower()
    if "guarantee" in ack:
        errors.append("acknowledgement_contains_banned_term=guarantee")
    if "send account passwords" in ack and "do not send" not in ack:
        errors.append("acknowledgement_requests_passwords")
    if "do not send payment details" not in ack:
        warnings.append("acknowledgement_should_warn_against_payment_details")
    blocked_claims = [row for row in payload.get("claim_register", []) if row.get("status") == "blocked"]
    if len(blocked_claims) < 2:
        errors.append("blocked_claims_below_2")
    if payload.get("private_pilot_approval_card", {}).get("status") != "draft_not_approved":
        errors.append("private_pilot_card_must_stay_draft_not_approved")
    if not payload.get("pilot_readiness_gate", {}).get("required_before_private_pilot_prep"):
        errors.append("pilot_readiness_gate_missing")
    if payload.get("pilot_readiness_gate", {}).get("status") != "internal_demo_ready_private_pilot_prep_not_ready":
        errors.append("pilot_readiness_gate_status_must_block_private_pilot_prep")
    return {
        "status": "ok" if not errors else "error",
        "error_count": len(errors),
        "warning_count": len(warnings),
        "errors": errors,
        "warnings": warnings,
    }


def render_deliverable(payload: dict[str, Any]) -> str:
    scenario = payload["scenario"]
    lines = [
        "# AI Workflow Clarity Sprint - Synthetic Missed-Lead Demo",
        "",
        "Status: internal synthetic proof only. Not customer-ready, compliance-ready, security-ready, or conversion proof.",
        "",
        "## Scenario",
        "",
        f"- Fictional business: {scenario['fictional_business']}",
        f"- Buyer type: {scenario['buyer_type']}",
        f"- Pain: {scenario['pain']}",
        "- Data used: fictional fixture only; no real customer data, credentials, or regulated information.",
        "",
        "## Response SLA",
        "",
        "- Target: first human touch within 15 minutes during business hours.",
        "- This is an internal demo rule, not a customer contract or guarantee.",
        "",
        "## Current-State Workflow",
        "",
    ]
    for step in payload["workflow_map"]:
        lines.extend(
            [
                f"### {step['step'].title()}",
                "",
                f"- Current: {step['current_state']}",
                f"- Target: {step['target_state']}",
                "",
            ]
        )
    lines.extend(["## Automation Opportunity Matrix", ""])
    for row in payload["opportunity_matrix"]:
        lines.append(
            f"{row['rank']}. {row['candidate']} - value {row['value']}, effort {row['effort']}, risk {row['risk']}. "
            f"Demo output: {row['demo_output']}."
        )
    lines.extend(
        [
            "",
            "## Safe Acknowledgement Copy",
            "",
            f"> {payload['acknowledgement_copy']['safe_copy']}",
            "",
            "## Escalation Path",
            "",
        ]
    )
    for row in payload["escalation_path"]:
        lines.append(f"- Minute {row['minute']}: {row['event']} ({row['proof']}).")
    lines.extend(
        [
            "",
            "## Executed Synthetic Outputs",
            "",
            "### Normalized Lead Record",
            "",
        ]
    )
    for row in payload["normalized_lead_records"]:
        lines.append(
            f"- {row['lead_id']}: {row['request_summary']} Tag: {row['triage_tag']}. "
            f"First touch due: {row['first_touch_due_local']}."
        )
    lines.extend(["", "### Triage Rule Set", ""])
    for row in payload["triage_rule_set"]["worked_examples"]:
        lines.append(f"- {row['event_id']}: {row['tag']} because {row['reason']}.")
    lines.extend(["", "### Business-Hours Logic", ""])
    lines.append(f"- Timezone: {payload['business_hours_state_machine']['timezone']}")
    lines.append(f"- Timer rule: {payload['business_hours_state_machine']['timer_rule']}")
    for row in payload["business_hours_state_machine"]["states"]:
        lines.append(f"- {row['state']}: {row['condition']}; timer starts at {row['timer_start']}.")
    lines.extend(["", "### Executed Escalation Trail", ""])
    for row in payload["executed_escalation_trail"]:
        lines.append(f"- {row['time_local']}: {row['event']} for {row['lead_id']} ({row['proof']}).")
    lines.extend(["", "### Daily Operational Digest", ""])
    digest = payload["daily_operational_digest"]
    lines.append(
        f"- {digest['date_local']}: {digest['lead_count']} lead, {digest['same_day_count']} same-day, "
        f"{digest['sla_breach_count']} SLA breach. Next action: {digest['operator_next_action']}"
    )
    lines.extend(["", "### Weekly Improvement Backlog", ""])
    for row in payload["weekly_improvement_backlog"]:
        lines.append(f"- {row['backlog_id']}: {row['issue']} Fix: {row['recommended_fix']}")
    lines.extend(
        [
            "",
            "## Public Source Support",
            "",
        ]
    )
    for row in payload["source_support"]:
        limitation = f" Limitation: {row['limitation']}" if row.get("limitation") else ""
        lines.append(f"- {row['source']} ({row['confidence']}): {row['finding']} {row['url']}.{limitation}")
    lines.extend(
        [
            "",
            "## Isolated-Agent Validation",
            "",
            f"- Research Scout: {payload['agent_validation_evidence']['research_scout']['verdict']}.",
            f"- QA Red-Team initial pass: {payload['agent_validation_evidence']['qa_redteam_initial']['verdict']}.",
            f"- QA Red-Team recheck: {payload['agent_validation_evidence']['qa_redteam_recheck']['verdict']}.",
            "- Remaining gap: source-backed problem/outcome evidence before private-pilot prep.",
            "",
            "## Claims Boundary",
            "",
        ]
    )
    for row in payload["claim_register"]:
        suffix = row.get("reason") or row.get("proof_needed_before_customer_claim", "")
        lines.append(f"- {row['status']}: {row['claim']} {suffix}")
    lines.extend(["", "## Unsupported Claims", ""])
    for claim in payload["unsupported_claims"]:
        lines.append(f"- {claim}")
    lines.extend(
        [
            "",
            "## Next Step",
            "",
            "Next internal-safe step: run a Research Scout problem/outcome evidence pass, then draft the one-page offer and intake script. Any private-pilot action still requires Randall's exact approval.",
            "",
        ]
    )
    return "\n".join(lines)


def render_continuity(payload: dict[str, Any]) -> str:
    validation = payload["validation"]
    lines = [
        "# Workflow 75 - AI Workflow Clarity Sprint Demo Stack - 2026-07-03",
        "",
        "## Current State",
        "",
        "- Internal synthetic missed-lead demo stack generated.",
        "- Authority remains internal-build only.",
        "- Outreach, payment, customer delivery, real customer data, credentials, cron dispatch, and channel bindings remain unapproved.",
        "",
        "## Generated Assets",
        "",
        "- `tmp/wf75-missed-lead-demo-v1/packet.json`",
        "- `tmp/wf75-missed-lead-demo-v1/fixture.json`",
        "- `tmp/wf75-missed-lead-demo-v1/workflow-map.json`",
        "- `tmp/wf75-missed-lead-demo-v1/business-hours-state-machine.json`",
        "- `tmp/wf75-missed-lead-demo-v1/triage-rule-set.json`",
        "- `tmp/wf75-missed-lead-demo-v1/executed-synthetic-outputs.json`",
        "- `tmp/wf75-missed-lead-demo-v1/opportunity-matrix.json`",
        "- `tmp/wf75-missed-lead-demo-v1/claim-register.json`",
        "- `tmp/wf75-missed-lead-demo-v1/source-support.json`",
        "- `tmp/wf75-missed-lead-demo-v1/data-boundary-manifest.json`",
        "- `tmp/wf75-missed-lead-demo-v1/authority-matrix.json`",
        "- `tmp/wf75-missed-lead-demo-v1/action-ledger.json`",
        "- `tmp/wf75-missed-lead-demo-v1/agent-validation-evidence.json`",
        "- `tmp/wf75-missed-lead-demo-v1/private-pilot-approval-card.json`",
        "- `10. Deliverables/AI Drop-Service OS/AI Workflow Clarity Sprint Synthetic Demo - 2026-07-03.md`",
        "",
        "## Validation",
        "",
        f"- Status: `{validation['status']}`",
        f"- Errors: `{validation['error_count']}`",
        f"- Warnings: `{validation['warning_count']}`",
        "",
        "## Next Action",
        "",
        "Run a `research-scout` problem/outcome evidence pass, then draft the one-page offer and intake script. Run `qa-redteam` again before any customer-facing claim or private-pilot approval card is treated as decision-ready.",
        "",
    ]
    return "\n".join(lines)


def write_outputs(payload: dict[str, Any], out_dir: Path, update_board: bool) -> dict[str, str]:
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        "packet": out_dir / "packet.json",
        "fixture": out_dir / "fixture.json",
        "workflow_map": out_dir / "workflow-map.json",
        "business_hours_state_machine": out_dir / "business-hours-state-machine.json",
        "triage_rule_set": out_dir / "triage-rule-set.json",
        "executed_synthetic_outputs": out_dir / "executed-synthetic-outputs.json",
        "opportunity_matrix": out_dir / "opportunity-matrix.json",
        "claim_register": out_dir / "claim-register.json",
        "data_boundary_manifest": out_dir / "data-boundary-manifest.json",
        "source_support": out_dir / "source-support.json",
        "research_evidence": out_dir / "research-evidence.json",
        "authority_matrix": out_dir / "authority-matrix.json",
        "action_ledger": out_dir / "action-ledger.json",
        "agent_validation_evidence": out_dir / "agent-validation-evidence.json",
        "private_pilot_approval_card": out_dir / "private-pilot-approval-card.json",
        "pilot_readiness_gate": out_dir / "pilot-readiness-gate.json",
        "validation": out_dir / "validation.json",
    }
    atomic_write_json(paths["packet"], payload)
    atomic_write_json(paths["fixture"], {"scenario": payload["scenario"], "lead_events": payload["lead_events"], "sla": payload["sla"]})
    atomic_write_json(paths["workflow_map"], {"workflow_map": payload["workflow_map"]})
    atomic_write_json(paths["business_hours_state_machine"], payload["business_hours_state_machine"])
    atomic_write_json(paths["triage_rule_set"], payload["triage_rule_set"])
    atomic_write_json(
        paths["executed_synthetic_outputs"],
        {
            "normalized_lead_records": payload["normalized_lead_records"],
            "acknowledgement_decisions": payload["acknowledgement_decisions"],
            "executed_escalation_trail": payload["executed_escalation_trail"],
            "daily_operational_digest": payload["daily_operational_digest"],
            "weekly_improvement_backlog": payload["weekly_improvement_backlog"],
        },
    )
    atomic_write_json(paths["opportunity_matrix"], {"opportunity_matrix": payload["opportunity_matrix"]})
    atomic_write_json(paths["claim_register"], {"claim_register": payload["claim_register"]})
    atomic_write_json(paths["source_support"], {"source_support": payload["source_support"], "unsupported_claims": payload["unsupported_claims"]})
    atomic_write_json(paths["research_evidence"], {"research_evidence": payload["research_evidence"]})
    atomic_write_json(paths["data_boundary_manifest"], payload["data_boundary_manifest"])
    atomic_write_json(paths["authority_matrix"], payload["authority_boundary"])
    atomic_write_json(paths["action_ledger"], {"action_ledger": payload["action_ledger"]})
    atomic_write_json(paths["agent_validation_evidence"], payload["agent_validation_evidence"])
    atomic_write_json(paths["private_pilot_approval_card"], payload["private_pilot_approval_card"])
    atomic_write_json(paths["pilot_readiness_gate"], payload["pilot_readiness_gate"])
    atomic_write_json(paths["validation"], payload["validation"])
    atomic_write_text(DELIVERABLE_PATH, render_deliverable(payload))
    atomic_write_text(CONTINUITY_PATH, render_continuity(payload))
    if update_board:
        update_team_board(payload, out_dir)
    return {key: str(path.relative_to(ROOT)) for key, path in paths.items()}


def update_team_board(payload: dict[str, Any], out_dir: Path) -> None:
    board = load_json_artifact(BOARD_PATH) or {}
    board["generated_at_utc"] = utc_now()
    board["status"] = "phase3_missed_lead_demo_v1_internal_demo_ready"
    current = dict(board.get("current_slice") or {})
    current["phase"] = "phase3_internal_demo_v1"
    current["focus"] = "Synthetic missed-lead demo stack is internal-demo-ready; private-pilot prep still needs problem/outcome evidence, one-page offer, intake script, and Randall approval gates."
    current["default_authority"] = "review_only_internal_build"
    board["current_slice"] = current
    artifacts = dict(board.get("artifacts") or {})
    artifacts.update(
        {
            "missed_lead_demo_packet": str((out_dir / "packet.json").relative_to(ROOT)),
            "missed_lead_demo_validation": str((out_dir / "validation.json").relative_to(ROOT)),
            "missed_lead_demo_deliverable": str(DELIVERABLE_PATH.relative_to(ROOT)),
            "missed_lead_demo_continuity": str(CONTINUITY_PATH.relative_to(ROOT)),
            "missed_lead_demo_generator": "scripts/wf75_ai_drop_service_demo.py",
            "missed_lead_demo_agent_validation": str((out_dir / "agent-validation-evidence.json").relative_to(ROOT)),
        }
    )
    board["artifacts"] = artifacts
    validation_state = dict(board.get("validation_state") or {})
    validation_state["missed_lead_demo_v1"] = (
        f"{payload['validation']['status']}_errors_{payload['validation']['error_count']}"
        f"_warnings_{payload['validation']['warning_count']}"
    )
    board["validation_state"] = validation_state
    board["next_safe_actions"] = [
        "Run research-scout for missed-lead and slow-response problem/outcome evidence.",
        "Draft the one-page AI Workflow Clarity Sprint offer.",
        "Draft the intake/discovery script and no-sensitive-data customer-data rule.",
        "Run qa-redteam before any customer-facing claim or private-pilot approval card is treated as decision-ready.",
    ]
    atomic_write_json(BOARD_PATH, board)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build WF75 AI Drop-Service OS synthetic missed-lead demo assets.")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--out-dir", type=Path, default=OUT_DIR)
    parser.add_argument("--no-board", action="store_true", help="Do not update state/ai-drop-service-os/team-board.json.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    out_dir = args.out_dir if args.out_dir.is_absolute() else ROOT / args.out_dir
    payload = build_payload()
    written: dict[str, str] = {}
    if args.write:
        written = write_outputs(payload, out_dir, update_board=not args.no_board)
    result = {
        "schema": SCHEMA,
        "status": payload["validation"]["status"],
        "generated_at_utc": payload["generated_at_utc"],
        "written": written,
        "validation": payload["validation"],
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    if args.validate and payload["validation"]["status"] != "ok":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
