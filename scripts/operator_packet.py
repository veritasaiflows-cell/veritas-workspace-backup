#!/usr/bin/env python3
"""Build standardized operator packets for long-running high-risk workflows.

The packets are recovery and orchestration surfaces. They do not grant
approval, mutation, execution, launch, delivery, import, or account authority.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
DEFAULT_OUTPUT_DIR = TMP / "operator-packets"
SCHEMA_VERSION = "operator_packet.v1"


COMMON_FALSE_FLAGS = {
    "owner_approval_inferred": False,
    "live_trade_or_account_action_allowed": False,
    "money_movement_allowed": False,
    "external_delivery_allowed": False,
    "config_auth_channel_service_runtime_mutation_allowed": False,
    "destructive_cleanup_allowed": False,
}


WORKFLOWS: dict[str, dict[str, Any]] = {
    "sql-wf78": {
        "workflow_name": "SQL support-mode hardening and WF78 live-pilot staging",
        "owner_surface": "06. Playbooks/Project Continuity/WF78 SQL Retail Expansion.md",
        "current_phase": "SQL retail-grade promotion and WF78 import frozen; SQL retained as on-demand proof/index/support substrate",
        "recommended_next_phase": "Run SQL retail-grade and WF78 gates only after SQL/helper/ticker-card changes or explicit owner review; redirect recurring effort to WF75 service-led SaaS readiness",
        "operator_mode": "on_demand_support_mode_gate",
        "safe_automation_boundary": "Generate and validate SQL proof, backup, rollback, consumer-diff, archive-readiness, and post-apply validator packets only when a scoped SQL review or code change requires them; do not add ticker rows, expand SQL-canon, import providers, or change production answer paths from this packet.",
        "proof_artifacts": [
            "tmp/sql-hardening-flattening-phased-plan-2026-05-29.json",
            "tmp/sql-pre-phase5-hardening-gate.json",
            "tmp/sql-phase5-readiness-design-2026-05-29.json",
            "tmp/wf78-100-ticker-provider-runtime-proof.json",
            "tmp/sql-source-truth-promotion-readiness-gate.json",
            "tmp/sql-source-truth-field-family-decision-packet.json",
            "tmp/sql-source-truth-apply-scaffold.json",
            "tmp/sql-source-truth-preapply-backup-manifest.json",
            "tmp/sql-source-truth-rollback-plan.json",
            "tmp/sql-source-truth-sql-first-consumer-diff.json",
            "tmp/sql-source-truth-post-apply-validators.json",
            "tmp/sql-source-truth-archive-readiness.json",
            "tmp/sql-source-truth-exact-apply-packet.json",
            "tmp/sql-first-consumer-wiring-preflight.json",
            "tmp/wf78-100-ticker-candidate-scope-packet.json",
        ],
        "optional_artifacts": [
            "tmp/sql-command-surface-flattening-audit-2026-05-29.json",
            "tmp/sql-current-proof-routing-archive-proposal-2026-05-29.json",
            "tmp/operator-packet-standard-audit-2026-05-29.json",
        ],
        "validators": [
            "python scripts\\sql_hardening_flattening_plan.py --write --validate",
            "python scripts\\sql_pre_phase5_hardening_gate.py --write --validate --run-gates --max-provider-age-hours 2",
            "python scripts\\sql_retail_grade_validation_bundle.py --write --validate",
            "python scripts\\sql_retail_expansion_phase_gate.py --write --validate",
            "python scripts\\sql_500_ticker_expansion_design_gate.py --write --validate",
            "python scripts\\sql_source_truth_promotion_readiness_gate.py --write --validate --run-gates",
            "python scripts\\sql_source_truth_field_family_decision_packet.py --write --validate",
            "python scripts\\sql_source_truth_apply_scaffold.py --write --validate --run-gates",
            "python scripts\\sql_source_truth_exact_apply_packet.py --write --validate",
            "python scripts\\sql_first_consumer_wiring_preflight.py --write --validate",
            "python scripts\\wf78_100_ticker_candidate_scope_packet.py --write --validate",
        ],
        "read_only_checks": [
            "python -m json.tool tmp\\operator-packets\\sql-wf78.json",
            "python scripts\\wf78_live_pilot_import_gate.py",
            "python scripts\\artifact_index.py validate",
        ],
        "authority_false_flags": {
            "sql_canon_expansion_allowed": False,
            "provider_import_allowed": False,
            "production_answer_path_change_allowed": False,
            "ticker_universe_write_allowed": False,
            "phase5_import_allowed": False,
            "source_of_truth_promotion_allowed": False,
            "apply_packet_execution_allowed": False,
            "archive_moves_allowed": False,
            "recurring_finance_chain_sql_readiness_churn_allowed": False,
        },
        "stop_lines": [
            "Stop before any recurring finance-chain reintroduction of SQL retail-grade/readiness churn.",
            "Stop before any SQL-canon/cache row addition or effective-row promotion.",
            "Stop before any provider/runtime import or ticker universe write.",
            "Stop before changing production 42-card answer behavior.",
            "Stop if provider/runtime budget proof or A/B no-regression proof is absent.",
            "Stop before archive/move/delete unless an exact microbatch has reference scans, hashes, rollback, and post-action validators.",
        ],
        "trust_gates_missing": [
            "Product demand or explicit owner review that justifies reopening SQL source-of-truth promotion",
            "Randall approval of exact SQL source-of-truth apply packet scope",
            "fresh provider/runtime budget proof for selected scope",
            "production-42 A/B no-regression proof for selected scope",
            "approved production consumer patch/diff and rollback trigger",
        ],
        "next_allowed_action": "Keep SQL retail-grade/WF78 gates on-demand and change-triggered; hold promotion, SQL writes, archive moves, import, and consumer migration while WF75 product readiness is the active sprint lane.",
    },
    "retail-saas-wf75": {
        "workflow_name": "Retail Investor Finance Intelligence SaaS",
        "owner_surface": "06. Playbooks/Project Continuity/Workflow 75 - AI Productivity and Business Opportunity Intelligence Expansion.md",
        "current_phase": "anonymous-scenario customer-safe prototype plus Phase C/D service-state, SQLite WAL control-plane, artifact-only PM handoff, and movement proof with WF77 supplemental public price evidence",
        "recommended_next_phase": "continue the 55-65% infrastructure-first sprint: use the WAL control plane and artifact-only PM handoff to drive the next operator-console/service-state slice",
        "operator_mode": "infrastructure_first_anonymous_scenario_review_surface",
        "safe_automation_boundary": "Generate anonymous scenario exports, local service-state proof, renderer/export proof, QA regression proof, and PM handoff artifacts only; public company/market evidence may be used when source-labeled, but real customer data and external delivery remain blocked.",
        "proof_artifacts": [
            "tmp/retail-saas-fixture-demo.customer-export-validation.json",
            "tmp/retail-saas-fixture-demo.html-validation.json",
            "tmp/retail-saas-customer-export-contract.json",
            "tmp/retail-saas-mvp-ux-service-state-contract.json",
            "tmp/wf75-retail-investor-saas-pivot-plan.json",
            "tmp/wf75-service-led-saas-readiness-plan.json",
            "tmp/wf77-supplemental-price-evidence.json",
            "tmp/wf77-price-freshness-bridge.json",
            "tmp/macro-event-calendar.json",
            "data/market/price-snapshots/wf77-supplemental-price-evidence-current.json",
            "data/market/price-snapshots/wf77-price-state-current.json",
            "tmp/wf75-service-state-current.json",
            "tmp/wf75-service-state-sqlite.json",
            "tmp/wf75-service-state.sqlite",
            "tmp/wf75-service-runs/wf75-anon-watchlist-ai-infrastructure-v1.json",
            "tmp/wf75-operator-queue.json",
            "tmp/wf75-operator-console.json",
            "tmp/wf75-automation-movement.json",
            "tmp/wf75-artifact-only-pm-handoff.json",
            "tmp/veritas-harness-scorecard.json",
            "tmp/veritas-harness-failure-classification.json",
            "tmp/veritas-pm-department-validation.json",
            "tmp/wf75-pm-weekly-update.json",
        ],
        "optional_artifacts": [
            "tmp/wf75-real-functioning-overnight-plan.json",
            "tmp/wf75-pm-readiness-brief.json",
            "tmp/wf75-pm-readiness-brief.html",
            "tmp/wf75-pm-readiness-brief.pdf",
            str(Path("tmp/wf75-operator-console.json").with_suffix(".html")),
            "tmp/operator-packet-lane-audit-wf75-wf68-2026-05-29.json",
        ],
        "validators": [
            "python scripts\\wf77_supplemental_price_evidence.py --write --validate",
            "python scripts\\wf77_price_freshness_bridge.py --write --validate",
            "python scripts\\macro_event_calendar.py --write --validate",
            "python scripts\\wf75_renderer_export_regression.py --write --validate",
            "python scripts\\wf75_scenario_template_library.py --write --validate",
            "python scripts\\wf75_service_state.py --write --validate",
            "python scripts\\wf75_service_state_sqlite.py --write --validate",
            "python scripts\\wf75_operator_console.py --write --validate",
            "python scripts\\retail_saas_customer_output_validator.py tmp\\retail-saas-fixture-demo.customer-export.json --out tmp\\retail-saas-fixture-demo.customer-export-validation.json",
            "python scripts\\retail_saas_customer_output_validator.py tmp\\retail-saas-fixture-demo.json --rendered-text tmp\\retail-saas-fixture-demo.md --out tmp\\retail-saas-fixture-demo-validation.rerun.json",
            "python scripts\\retail_saas_html_report.py",
            "python scripts\\wf75_service_led_saas_readiness_plan.py --write --validate",
            "python scripts\\veritas_pm_department_validate.py --write",
            "python scripts\\wf75_pm_weekly_update.py --write --validate",
            "python scripts\\wf75_artifact_only_pm_handoff.py --write --validate",
            "python scripts\\wf75_pm_readiness_pdf.py --write --validate",
            "python scripts\\veritas_harness_scorecard.py --run --write --validate",
            "python scripts\\veritas_harness_failure_classifier.py --text \"rg wildcard failed with Windows path syntax\" --write",
        ],
        "read_only_checks": [
            "python -m json.tool tmp\\operator-packets\\retail-saas-wf75.json",
            "python -m json.tool tmp\\retail-saas-fixture-demo.customer-export-validation.json",
            "python -m json.tool tmp\\retail-saas-fixture-demo.html-validation.json",
            "python -m json.tool tmp\\wf75-service-led-saas-readiness-plan.json",
            "python -m json.tool tmp\\wf77-supplemental-price-evidence.json",
            "python -m json.tool tmp\\wf77-price-freshness-bridge.json",
            "python -m json.tool tmp\\macro-event-calendar.json",
            "python -m json.tool data\\market\\price-snapshots\\wf77-supplemental-price-evidence-current.json",
            "python -m json.tool data\\market\\price-snapshots\\wf77-price-state-current.json",
            "python -m json.tool tmp\\wf75-service-state-current.json",
            "python -m json.tool tmp\\wf75-service-state-sqlite.json",
            "python -m json.tool tmp\\wf75-operator-queue.json",
            "python -m json.tool tmp\\wf75-operator-console.json",
            "python -m json.tool tmp\\wf75-automation-movement.json",
            "python -m json.tool tmp\\wf75-pm-weekly-update.json",
            "python -m json.tool tmp\\wf75-artifact-only-pm-handoff.json",
            "python -m json.tool tmp\\wf75-pm-readiness-brief.json",
            "python -m json.tool tmp\\veritas-harness-scorecard.json",
            "python -m json.tool tmp\\veritas-harness-failure-classification.json",
        ],
        "authority_false_flags": {
            "real_customer_data_allowed": False,
            "customer_data_retention_allowed": False,
            "regulated_personalized_advice_allowed": False,
            "public_launch_allowed": False,
            "brokerage_connection_allowed": False,
        },
        "stop_lines": [
            "Stop before real customer intake, storage, retention, or access-control claims.",
            "Stop before external delivery, public launch, or paid customer use.",
            "Stop before personalized regulated advice, performance claims, or brokerage connection.",
            "Stop if customer-safe export/rendered-output validation is absent or failing.",
        ],
        "trust_gates_missing": [],
        "next_allowed_action": "Use the Phase C/D service-state, SQLite WAL control plane, artifact-only PM handoff, supplemental WF77 price evidence, renderer/export regression, and scenario-template proof to drive the next operator-console/service-state slice without customer/external/account authority.",
    },
    "generic-smb-wf75": {
        "workflow_name": "SMB Workflow Clarity / Marketing Ops Automation",
        "owner_surface": "06. Playbooks/Project Continuity/Workflow 75 - AI Productivity and Business Opportunity Intelligence Expansion.md",
        "current_phase": "internal phased parallel artifacts implemented for offer/ICP, demos, marketing-ops blueprints, cockpit panel, sales practice, and closeout proof",
        "recommended_next_phase": "review the internal phase packets and decide whether to prepare approval-gated outreach material; do not contact real prospects yet",
        "operator_mode": "service_led_smb_workflow_clarity_review_surface",
        "safe_automation_boundary": "Generate generic service-run contracts, anonymous SMB scenarios, derived SQLite lookup, local PM/customer-preview render proof, and handoff packets only; do not ingest real customer data, access phone/CRM/ad/email/payment credentials, send messages, implement in customer systems, or claim public/customer readiness.",
        "proof_artifacts": [
            "tmp/generic-service-run-contract.json",
            "tmp/wf75-smb-workflow-scenario-library.json",
            "tmp/wf75-smb-pivot-pm-decision-packet.json",
            "tmp/wf75-smb-customer-preview.json",
            "tmp/wf75-smb-customer-preview.md",
            "tmp/wf75-smb-customer-preview-validation.json",
            "tmp/wf75-smb-pilot-decision-packet.json",
            "tmp/wf79-smb-offer-icp-packet.json",
            "tmp/wf79-smb-demo-packets-validation.json",
            "tmp/wf79-smb-marketing-ops-blueprints-validation.json",
            "tmp/wf79-smb-cockpit-panel.json",
            "tmp/wf79-smb-sales-practice-packet.json",
            "tmp/wf79-smb-phase-closeout.json",
            "tmp/generic-service-state.sqlite",
            "tmp/pm-control-packet.json",
        ],
        "optional_artifacts": [],
        "validators": [
            "python scripts\\generic_intelligence_saas_pivot.py --write --write-db --validate",
            "python scripts\\pm_control_packet.py --write --write-db --validate",
        ],
        "read_only_checks": [
            "python -m json.tool tmp\\generic-service-run-contract.json",
            "python -m json.tool tmp\\wf75-smb-workflow-scenario-library.json",
            "python -m json.tool tmp\\wf75-smb-pivot-pm-decision-packet.json",
            "python -m json.tool tmp\\wf75-smb-customer-preview.json",
            "python -m json.tool tmp\\wf75-smb-customer-preview-validation.json",
            "python -m json.tool tmp\\wf75-smb-pilot-decision-packet.json",
            "python -m json.tool tmp\\wf79-smb-offer-icp-packet.json",
            "python -m json.tool tmp\\wf79-smb-demo-packets-validation.json",
            "python -m json.tool tmp\\wf79-smb-marketing-ops-blueprints-validation.json",
            "python -m json.tool tmp\\wf79-smb-phase-closeout.json",
            "python -m json.tool tmp\\pm-control-packet.json",
        ],
        "authority_false_flags": {
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
            "guaranteed_revenue_or_roi_claim_allowed": False,
        },
        "stop_lines": [
            "Stop before real customer identity, lead, caller, prospect, employee, or private business data is ingested or retained.",
            "Stop before accessing phone, CRM, ad, email, form, payment, POS, payroll, or website credentials.",
            "Stop before sending calls, texts, emails, social messages, review requests, or any external customer/prospect communication.",
            "Stop before implementing changes inside customer systems or claiming legal, compliance, security, or ROI readiness.",
            "Stop if renderer/validator/customer-preview proof is absent or failing.",
        ],
        "trust_gates_missing": [
            "explicit Randall approval before any real customer/pilot use",
            "separate intake/privacy/security terms before real customer data",
            "manual sales/pilot decision packet before outreach or paid use",
        ],
        "next_allowed_action": "Review the SMB renderer/validator, local TypeScript cockpit preview, and pilot decision packet; stop before any real customer data, outreach, or paid use.",
    },
    "wf68-alerts": {
        "workflow_name": "WF68 intraday advisor alerts",
        "owner_surface": "06. Playbooks/Project Continuity/WF68 Intraday Advisor Alerts.md",
        "current_phase": "review-only alert packet and runtime handoff hardening",
        "recommended_next_phase": "standardize alert packet generation and handoff validation without execution or channel authority",
        "operator_mode": "review_only_alert_packet",
        "safe_automation_boundary": "Generate advisor alert packets and validation/handoff status only; do not execute, size, mutate canon, or deliver externally.",
        "proof_artifacts": [
            "tmp/intraday-alerts/runtime-handoff-status.json",
            "tmp/intraday-alerts/advisor-alert-packet-validation.json",
            "tmp/intraday-alerts/current-alerts.json",
            "tmp/intraday-alerts/main-session-handoff-validation.json",
        ],
        "optional_artifacts": [
            "tmp/operator-packet-lane-audit-wf75-wf68-2026-05-29.json",
        ],
        "validators": [
            "python scripts\\intraday_alert_packet_validator.py --write",
            "python scripts\\wf68_runtime_wiring_plan_validator.py --write --validate",
        ],
        "read_only_checks": [
            "python -m json.tool tmp\\operator-packets\\wf68-alerts.json",
            "python scripts\\intraday_alert_packet_validator.py tmp\\intraday-alerts\\advisor-alert-packet.json",
        ],
        "authority_false_flags": {
            "paper_trade_allowed": False,
            "canonical_note_mutation_allowed": False,
            "portfolio_mutation_allowed": False,
            "external_channel_delivery_allowed": False,
            "sizing_sleeve_cash_risk_rule_change_allowed": False,
        },
        "stop_lines": [
            "Stop before any paper/live trade action or approval inference.",
            "Stop before canonical note or portfolio mutation.",
            "Stop before external chat/channel delivery unless channel policy is deliberately restored.",
            "Stop if alert packet authority flags are not hard false.",
        ],
        "trust_gates_missing": [
            "fresh alert source proof for any market-moving claim",
            "channel-delivery policy if alerts leave local review surfaces",
            "exact owner approval for any paper-order conversion",
        ],
        "next_allowed_action": "Continue review-only alert packet validation and handoff hardening.",
    },
    "wf67-paper": {
        "workflow_name": "WF67 paper trading operator",
        "owner_surface": "06. Playbooks/Project Continuity/WF67 Paper Trading Operator.md",
        "current_phase": "paper-only request/guard surface with execution blocked until exact order approval",
        "recommended_next_phase": "standardize exact approval-card and guard-proof packet before any paper submit",
        "operator_mode": "paper_request_review_only",
        "safe_automation_boundary": "Prepare paper-only order cards, previews, and guard proof; do not submit, cancel, sell, or touch live endpoints.",
        "proof_artifacts": [
            "tmp/alpaca-paper-readiness/wf63-readiness-report.json",
            "tmp/alpaca-paper-readiness/no-submit-guard-report.json",
            "tmp/alpaca-paper-readiness/paper-execution-guard-validation.json",
            "tmp/alpaca-paper-readiness/paper-pilot-status-surface.json",
            "tmp/wf67-paper-position-state.sqlite",
        ],
        "optional_artifacts": [
            "tmp/operator-packet-lane-audit-wf67-wf64-wf56-2026-05-29.json",
        ],
        "validators": [
            "python scripts\\wf67_order_card_request_generator.py --help",
            "python scripts\\wf67_advisor_paper_request_generator.py --help",
            "python scripts\\wf67_full_portfolio_scope_validator.py --write --validate",
        ],
        "read_only_checks": [
            "python -m json.tool tmp\\operator-packets\\wf67-paper.json",
            "python -m json.tool tmp\\alpaca-paper-readiness\\paper-execution-guard-validation.json",
            "python -m json.tool tmp\\alpaca-paper-readiness\\no-submit-guard-report.json",
        ],
        "authority_false_flags": {
            "paper_execution_allowed": False,
            "paper_cancel_or_sell_allowed": False,
            "live_endpoint_allowed": False,
            "live_brokerage_authority_allowed": False,
            "paper_to_live_promotion_allowed": False,
        },
        "stop_lines": [
            "Stop before any paper submit/cancel/sell unless Randall approves the exact order and fresh guard proof exists.",
            "Stop before any live endpoint, live credential, account, liquidation, or money-movement action.",
            "Stop if kill switch, paper/live isolation, audit log redaction, or order preview is absent.",
            "Stop if generated request terms imply owner approval.",
        ],
        "trust_gates_missing": [
            "Randall exact order approval",
            "fresh short-lived kill switch",
            "fresh paper/live isolation and no-submit guard proof",
            "order preview/risk proof tied to exact ticker/side/size/order type",
        ],
        "next_allowed_action": "Prepare exact paper-order approval cards and rerun paper-only guard proof.",
    },
    "wf64-wf56-bounded-portfolio-canon": {
        "workflow_name": "bounded portfolio and canon maintenance",
        "owner_surface": "06. Playbooks/Project Continuity/WF64 Portfolio Maintenance.md; 06. Playbooks/Project Continuity/WF56 Canon Maintenance.md",
        "current_phase": "review/proposal and bounded validator-backed maintenance only",
        "recommended_next_phase": "standardize proposal/apply packet split for standing-approved categories",
        "operator_mode": "proposal_review_surface",
        "safe_automation_boundary": "Prepare proposals, previews, diffs, validators, and rollback proof; do not apply canonical/portfolio mutations without exact gated authority.",
        "proof_artifacts": [
            "tmp/portfolio-mutation-proposals/current-capital-deployment-recommendations.json",
            "tmp/capital-deployment-recommendation-validation.json",
            "tmp/portfolio-mutation-proposals/semantic-preview-bundle.json",
            "tmp/post-apply-validation-chain.json",
            "tmp/portfolio-mutation-proposal-posture.json",
        ],
        "optional_artifacts": [
            "tmp/operator-packet-lane-audit-wf67-wf64-wf56-2026-05-29.json",
        ],
        "validators": [
            "python scripts\\portfolio_mutation_proposal_schema_validator.py tmp\\portfolio-mutation-proposals\\current-capital-deployment-recommendations.json",
            "python scripts\\portfolio_mutation_semantic_preview.py --write --validate",
            "python scripts\\post_apply_validation_chain.py --write --validate",
        ],
        "read_only_checks": [
            "python -m json.tool tmp\\operator-packets\\wf64-wf56-bounded-portfolio-canon.json",
            "python scripts\\portfolio_mutation_proposal_schema_validator.py tmp\\portfolio-mutation-proposals\\current-capital-deployment-recommendations.json",
            "python -m json.tool tmp\\post-apply-validation-chain.json",
        ],
        "authority_false_flags": {
            "portfolio_mutation_allowed": False,
            "canonical_note_mutation_allowed": False,
            "apply_allowed": False,
            "cron_direct_apply_allowed": False,
            "cash_risk_rule_execution_entitlement_change_allowed": False,
        },
        "stop_lines": [
            "Stop before apply unless scoped proposal, standing approval, diff hash, backup/rollback, validator proof, and audit trail all exist.",
            "Stop before cash, risk-rule, sizing entitlement, account, or execution-authority changes.",
            "Stop if generated artifacts conflict with owner/canonical notes.",
            "Stop if proposal validation or post-apply validation chain is absent or failing.",
        ],
        "trust_gates_missing": [
            "exact scoped apply packet for any mutation",
            "fresh backup and rollback proof",
            "validator proof tied to the exact proposal/diff hash",
            "main-session final review before apply",
        ],
        "next_allowed_action": "Prepare proposal packets and validation previews; hold apply at the exact approval gate.",
    },
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def resolve_workspace_path(path: str) -> Path:
    candidate = Path(path)
    return candidate if candidate.is_absolute() else ROOT / candidate


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> Any | None:
    if path.suffix.lower() not in {".json", ".jsonl"}:
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001 - validation artifact should capture exact issue.
        return {"_parse_error": f"{type(exc).__name__}: {exc}"}


def nested_get(payload: Any, keys: tuple[str, ...]) -> Any:
    cur = payload
    for key in keys:
        if not isinstance(cur, dict):
            return None
        cur = cur.get(key)
    return cur


def extract_artifact_status(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {}
    if "_parse_error" in payload:
        return {"parse_error": payload["_parse_error"]}
    result: dict[str, Any] = {}
    for key in ("schema", "schema_version", "status", "ok", "generated_at_utc", "updated_at_utc", "critical_count", "warning_count", "blocker_count"):
        if key in payload:
            result[key] = payload[key]
    for label, keys in {
        "validation_status": ("validation", "status"),
        "summary_status": ("summary", "status"),
        "gate_status": ("gate", "status"),
    }.items():
        value = nested_get(payload, keys)
        if value is not None:
            result[label] = value
    return result


def artifact_state(path_text: str, *, required: bool) -> dict[str, Any]:
    path = resolve_workspace_path(path_text)
    exists = path.exists()
    state: dict[str, Any] = {
        "path": rel(path),
        "required": required,
        "exists": exists,
    }
    if not exists:
        return state
    state["size_bytes"] = path.stat().st_size
    state["sha256"] = sha256_file(path)
    payload = load_json(path)
    state.update(extract_artifact_status(payload))
    return state


def validate_packet(packet: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []

    if packet.get("schema_version") != SCHEMA_VERSION:
        errors.append("schema_version_mismatch")
    if not packet.get("workflow_id"):
        errors.append("missing_workflow_id")
    if not packet.get("owner_surface"):
        errors.append("missing_owner_surface")
    if not packet.get("safe_automation_boundary"):
        errors.append("missing_safe_automation_boundary")
    if not packet.get("next_allowed_action"):
        errors.append("missing_next_allowed_action")
    if not packet.get("stop_lines"):
        errors.append("missing_stop_lines")
    if not packet.get("validators"):
        errors.append("missing_validators")
    if not packet.get("read_only_checks"):
        errors.append("missing_read_only_checks")

    for artifact in packet.get("proof_artifacts", []):
        if artifact.get("required") and not artifact.get("exists"):
            errors.append(f"required_proof_missing:{artifact.get('path')}")
        if artifact.get("parse_error"):
            errors.append(f"proof_parse_error:{artifact.get('path')}")

    authority = packet.get("authority_boundary")
    if not isinstance(authority, dict):
        errors.append("missing_authority_boundary")
    else:
        for key, value in authority.items():
            if key.endswith("_allowed") or key.endswith("_inferred"):
                if value is not False:
                    errors.append(f"authority_flag_not_false:{key}")

    lane = packet.get("parallel_lane_contract")
    if not isinstance(lane, dict):
        errors.append("missing_parallel_lane_contract")
    else:
        if lane.get("main_session_verifies_before_claiming_ready") is not True:
            errors.append("main_session_verification_not_required")
        if lane.get("helpers_may_mutate_canonical_surfaces") is not False:
            errors.append("helper_canonical_mutation_not_blocked")
        if lane.get("helpers_may_take_external_or_account_actions") is not False:
            errors.append("helper_external_or_account_actions_not_blocked")

    optional_missing = [a["path"] for a in packet.get("optional_artifacts", []) if not a.get("exists")]
    if optional_missing:
        warnings.append(f"optional_artifacts_missing:{len(optional_missing)}")

    return {
        "status": "ok" if not errors else "error",
        "error_count": len(errors),
        "warning_count": len(warnings),
        "errors": errors,
        "warnings": warnings,
    }


def build_packet(workflow_id: str, config: dict[str, Any]) -> dict[str, Any]:
    proof_artifacts = [artifact_state(path, required=True) for path in config["proof_artifacts"]]
    optional_artifacts = [artifact_state(path, required=False) for path in config.get("optional_artifacts", [])]
    authority = dict(COMMON_FALSE_FLAGS)
    authority.update(config["authority_false_flags"])
    packet = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": utc_now(),
        "workflow_id": workflow_id,
        "workflow_name": config["workflow_name"],
        "owner_surface": config["owner_surface"],
        "current_phase": config["current_phase"],
        "recommended_next_phase": config["recommended_next_phase"],
        "operator_mode": config["operator_mode"],
        "safe_automation_boundary": config["safe_automation_boundary"],
        "authority_boundary": authority,
        "proof_artifacts": proof_artifacts,
        "optional_artifacts": optional_artifacts,
        "validators": config["validators"],
        "read_only_checks": config["read_only_checks"],
        "stop_lines": config["stop_lines"],
        "trust_gates_missing": config["trust_gates_missing"],
        "next_allowed_action": config["next_allowed_action"],
        "decision_required_before": [
            "mutation",
            "import",
            "external delivery",
            "customer data use",
            "paper execution",
            "live/account action",
        ],
        "parallel_lane_contract": {
            "helper_outputs_are_untrusted_until_main_verifies": True,
            "main_session_verifies_before_claiming_ready": True,
            "helpers_may_mutate_canonical_surfaces": False,
            "helpers_may_take_external_or_account_actions": False,
            "artifact_first_partial_output_required": True,
            "one_writer_per_canonical_surface_required": True,
            "acceptance_proof_required": True,
            "stop_lines_required": True,
        },
    }
    packet["validation"] = validate_packet(packet)
    packet["packet_status"] = "structurally_valid" if packet["validation"]["status"] == "ok" else "blocked_invalid_packet"
    return packet


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temp.replace(path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build standardized high-risk workflow operator packets.")
    parser.add_argument("--workflow", choices=["all", *WORKFLOWS.keys()], default="all", help="Workflow packet to generate.")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR), help="Output directory for generated packets.")
    parser.add_argument("--write", action="store_true", help="Write packet JSON artifacts.")
    parser.add_argument("--validate", action="store_true", help="Fail nonzero if any generated packet is structurally invalid.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    workflow_ids = list(WORKFLOWS) if args.workflow == "all" else [args.workflow]
    packets = {workflow_id: build_packet(workflow_id, WORKFLOWS[workflow_id]) for workflow_id in workflow_ids}
    output_dir = resolve_workspace_path(args.output_dir)

    if args.write:
        for workflow_id, packet in packets.items():
            write_json(output_dir / f"{workflow_id}.json", packet)
        if args.workflow == "all":
            index = {
                "schema_version": "operator_packet_index.v1",
                "generated_at_utc": utc_now(),
                "status": "ok" if all(p["validation"]["status"] == "ok" for p in packets.values()) else "error",
                "packet_count": len(packets),
                "packets": [
                    {
                        "workflow_id": workflow_id,
                        "path": rel(output_dir / f"{workflow_id}.json"),
                        "packet_status": packet["packet_status"],
                        "validation_status": packet["validation"]["status"],
                        "next_allowed_action": packet["next_allowed_action"],
                    }
                    for workflow_id, packet in packets.items()
                ],
            }
            write_json(output_dir / "operator-packet-index.json", index)

    summary = {
        "status": "ok" if all(p["validation"]["status"] == "ok" for p in packets.values()) else "error",
        "packet_count": len(packets),
        "packets": {
            workflow_id: {
                "packet_status": packet["packet_status"],
                "validation": packet["validation"],
                "output": rel(output_dir / f"{workflow_id}.json") if args.write else None,
            }
            for workflow_id, packet in packets.items()
        },
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    if args.validate and summary["status"] != "ok":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
