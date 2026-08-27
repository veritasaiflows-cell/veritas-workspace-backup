"""auto_apply_position_sizing_semantic_sync.py

Apply bounded position-sizing semantic sync notes through the existing
WF64/WF56 exact-diff approval, backup, and validation rails.

Authority boundary:
- reads the current capital-deployment recommendation bundle to choose tickers
- syncs only current draft-weight and sizing-tier context already present in
  tmp/portfolio-config.json into 03. Portfolio/Portfolio Snapshot.md
- writes only through generated exact previews, standing approval artifacts,
  the approval-gated apply helper, and post-apply validation
- does not invent new allocations, change portfolio-config sizing, mutate cash,
  risk rules, sleeves, execution entitlement, trade/account authority, or money
  movement

Usage:
    python scripts/auto_apply_position_sizing_semantic_sync.py --dry-run --window morning
    python scripts/auto_apply_position_sizing_semantic_sync.py --apply --window morning
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, atomic_write_text
from sql_first_thin_board_contract import evaluate_sql_first_thin_board_contract

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import portfolio_mutation_apply_helper as apply_helper
import portfolio_mutation_approval_artifact_validator as approval_validator
import portfolio_mutation_semantic_patch_generator as semantic_generator
import portfolio_mutation_standing_approval_artifact as standing

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
DEFAULT_BUNDLE = TMP / "portfolio-mutation-proposals" / "current-capital-deployment-recommendations.json"
OUT_JSON = TMP / "auto-position-sizing-semantic-sync.json"
OUT_MD = TMP / "auto-position-sizing-semantic-sync.md"
PORTFOLIO_SNAPSHOT = ROOT / "03. Portfolio" / "Portfolio Snapshot.md"
CATEGORY = "sizing"
APPROVED_BY = "Randall-standing-approval-2026-05-16-position-sizing-sync"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path | None) -> str | None:
    if path is None:
        return None
    try:
        return str(path.relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Auto-apply bounded position-sizing semantic sync through the existing exact-diff approval rails.")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--apply", action="store_true", help="Write the bounded sizing semantic sync into Portfolio Snapshot using standing exact-diff approval artifacts.")
    mode.add_argument("--dry-run", action="store_true", help="Generate material, previews, and approval artifacts without applying writes.")
    parser.add_argument("--window", default="post-close", choices=["morning", "post-close", "sunday"], help="Finance window used for post-apply validation context.")
    parser.add_argument("--proposal-bundle", default=str(DEFAULT_BUNDLE), help="Path to the capital-deployment recommendation bundle.")
    parser.add_argument("--expires-hours", type=int, default=24, help="Approval artifact expiry horizon for the generated standing approval artifacts.")
    return parser.parse_args()


def load_json(path: Path, label: str) -> dict[str, Any]:
    if not path.exists():
        raise SystemExit(f"ERROR: {label} missing at {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise SystemExit(f"ERROR: {label} must be a JSON object at {path}")
    return data


def proposal_packets(bundle_path: Path) -> list[dict[str, Any]]:
    bundle = load_json(bundle_path, "proposal bundle")
    packets = apply_helper.proposal_packets(bundle)
    return [packet for packet in packets if isinstance(packet, dict) and packet.get("proposal_id")]


def portfolio_snapshot_thin_contract() -> dict[str, Any]:
    return evaluate_sql_first_thin_board_contract(
        PORTFOLIO_SNAPSHOT,
        route_tokens=[
            "finance_sql_canon_access.py",
            "finance_intelligence_state.py",
            "trade_grade_os_freshness_cron_runner.py",
            "full_intelligence_answer_parity.py",
        ],
        proof_files=[
            "tmp/trade-grade-os-freshness-cron-runner.json",
            "tmp/full-answer-parity/full-answer-parity-rollup.json",
            "tmp/canonical-finance-data-plane-retirement-readiness.json",
        ],
        authority_phrases=[
            "no execution",
            "account action",
            "archive/delete/apply authority",
            "inferred approval",
        ],
    )


def sql_first_thin_snapshot_sync_decision(thin_contract: dict[str, Any]) -> dict[str, Any]:
    detected = thin_contract.get("sql_first_thin_board_detected") is True
    allowed = thin_contract.get("sql_first_thin_board_allowed") is True
    return {
        "short_circuit_snapshot_mutation": detected,
        "status": "ok_no_changes" if detected and allowed else "blocked" if detected else "legacy_portfolio_snapshot_note",
        "reason": (
            "SQL-first thin Portfolio Snapshot uses SQL/JSON proof for current sizing semantics; the old freshness anchor is intentionally absent."
            if detected and allowed
            else "SQL-first thin Portfolio Snapshot detected but its proof contract is blocked."
            if detected
            else "Legacy Portfolio Snapshot exact-diff note sync remains active."
        ),
    }


def ticker_from_packet(packet: dict[str, Any]) -> str:
    return str(packet.get("ticker_or_scope") or packet.get("ticker") or "UNKNOWN").upper()


def run_post_apply_validation(window: str, approval_artifact: str) -> dict[str, Any]:
    cmd = [
        sys.executable,
        "scripts/post_apply_validation_chain.py",
        "--execute",
        "--write",
        "--window",
        window,
        "--approval-artifact",
        approval_artifact,
    ]
    proc = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True)
    return {
        "cmd": cmd,
        "status": "ok" if proc.returncode == 0 else "failed",
        "returncode": proc.returncode,
        "stdout_tail": proc.stdout[-2000:],
        "stderr_tail": proc.stderr[-2000:],
    }


def material_and_preview(bundle_path: Path, proposal_id: str, window: str) -> tuple[dict[str, Any], Path, Path, dict[str, Any], Path, Path]:
    packet = semantic_generator.build_augmented_packet(bundle_path, proposal_id, None, CATEGORY)
    validation = semantic_generator.validation_summary(packet, bundle_path)
    material_json, material_md = semantic_generator.write_outputs(packet, CATEGORY)
    preview = apply_helper.build_preview(material_json, proposal_id, window)
    preview_json, preview_md = apply_helper.write_outputs(preview)
    return packet, material_json, material_md, preview, preview_json, preview_md


def build_approval(material_json: Path, preview_json: Path, proposal_id: str, expires_hours: int) -> tuple[dict[str, Any], Path, dict[str, Any]]:
    approval = standing.build_artifact(rel(material_json) or "", rel(preview_json) or "", proposal_id, expires_hours, APPROVED_BY)
    approval_path = standing.write_artifact(approval)
    approval_validation = approval_validator.validate_approval(approval_path)
    return approval, approval_path, approval_validation


def process_proposal(packet: dict[str, Any], bundle_path: Path, window: str, apply_mode: bool, expires_hours: int) -> dict[str, Any]:
    proposal_id = str(packet.get("proposal_id") or "")
    ticker = ticker_from_packet(packet)
    record: dict[str, Any] = {
        "proposal_id": proposal_id,
        "ticker": ticker,
        "status": "blocked",
        "category": CATEGORY,
        "writes_performed": False,
    }
    try:
        generated, material_json, material_md, preview, preview_json, preview_md = material_and_preview(bundle_path, proposal_id, window)
        validation = semantic_generator.validation_summary(generated, bundle_path)
        approval, approval_path, approval_validation = build_approval(material_json, preview_json, proposal_id, expires_hours)
        source_gate = ((generated.get("semantic_patch_generator") or {}).get("source_gate") or {})
        preview_status = str(preview.get("status") or "blocked")
        critical_count = int(validation.get("critical_count") or 0)
        if preview_status != "ready_for_scoped_main_session_review":
            critical_count += 1
        if approval_validation.get("status") != "ok":
            critical_count += 1
        record.update(
            {
                "source_freshness_classification": source_gate.get("classification"),
                "source_manual_review_required": source_gate.get("manual_review_required_before_apply"),
                "material_json": rel(material_json),
                "material_md": rel(material_md),
                "preview_json": rel(preview_json),
                "preview_md": rel(preview_md),
                "approval_artifact": rel(approval_path),
                "approved_adjustment_categories": approval.get("approved_adjustment_categories"),
                "preview_status": preview_status,
                "approval_validation_status": approval_validation.get("status"),
                "critical": critical_count,
            }
        )
        if critical_count:
            record["status"] = "blocked"
            return record
        if not apply_mode:
            record["status"] = "ready_to_apply"
            return record
        apply_result = apply_helper.execute_apply(approval_path, window)
        apply_result_path = apply_helper.write_apply_result(apply_result)
        record.update(
            {
                "apply_result": rel(apply_result_path),
                "apply_status": apply_result.get("status"),
                "writes_performed": bool((apply_result.get("summary") or {}).get("writes_performed")),
            }
        )
        record["status"] = "applied_pending_batch_validation" if apply_result.get("status") == "applied_pending_post_apply_validation" else "blocked"
        return record
    except Exception as exc:  # noqa: BLE001 - fail closed into the audit artifact
        message = str(exc)
        record["error"] = message[:800]
        if "semantic note already current" in message:
            record["status"] = "already_current"
            record["critical"] = 0
            return record
        record["critical"] = 1
        return record


def build_audit(bundle_path: Path, window: str, apply_mode: bool, expires_hours: int) -> dict[str, Any]:
    packets = proposal_packets(bundle_path)
    thin_contract = portfolio_snapshot_thin_contract()
    thin_decision = sql_first_thin_snapshot_sync_decision(thin_contract)
    if thin_decision["short_circuit_snapshot_mutation"]:
        records = [
            {
                "proposal_id": str(packet.get("proposal_id") or ""),
                "ticker": ticker_from_packet(packet),
                "status": "sql_first_thin_snapshot_noop" if thin_decision["status"] == "ok_no_changes" else "blocked",
                "category": CATEGORY,
                "writes_performed": False,
                "critical": 0 if thin_decision["status"] == "ok_no_changes" else 1,
                "reason": thin_decision["reason"],
            }
            for packet in packets
        ]
        blocked_count = sum(1 for record in records if record.get("status") == "blocked")
        status = "blocked" if blocked_count else "ok_no_changes"
        return {
            "generated_at_utc": utc_now(),
            "mode": "apply" if apply_mode else "dry_run",
            "window": window,
            "status": status,
            "category": CATEGORY,
            "technical_sheet_mode": "sql_first_thin_portfolio_snapshot",
            "sql_first_thin_portfolio_snapshot_contract": thin_contract,
            "sync_decision": thin_decision,
            "authority": {
                "exact_diff_workspace_note_sync_only": False,
                "reads_current_portfolio_config_only": True,
                "writes_portfolio_snapshot_only": False,
                "portfolio_config_weight_mutation_allowed": False,
                "cash_risk_rule_sleeve_execution_mutation_allowed": False,
                "trade_or_account_action_allowed": False,
                "owner_approval_inferred": False,
            },
            "inputs": {
                "proposal_bundle": rel(bundle_path),
                "portfolio_snapshot": "03. Portfolio/Portfolio Snapshot.md",
                "portfolio_config": "tmp/portfolio-config.json",
            },
            "summary": {
                "proposal_count": len(packets),
                "ready_to_apply_count": 0,
                "applied_count": 0,
                "already_current_count": 0,
                "sql_first_thin_snapshot_noop_count": sum(1 for record in records if record.get("status") == "sql_first_thin_snapshot_noop"),
                "blocked_count": blocked_count,
                "writes_performed": 0,
            },
            "records": records,
            "post_apply_validation": None,
            "stop_lines": [
                "Portfolio Snapshot is thin; current sizing semantics live in SQL/JSON proof surfaces.",
                "No Portfolio Snapshot write, portfolio-config weight mutation, cash, risk-rule, sleeve, execution, trade, account, or money-movement action was performed.",
                "Any blocked proposal record requires source-open inspection or note-surface repair before unattended reuse.",
            ],
        }
    records: list[dict[str, Any]] = []
    last_applied_approval: str | None = None
    for packet in packets:
        record = process_proposal(packet, bundle_path, window, apply_mode, expires_hours)
        records.append(record)
        if apply_mode and record.get("status") == "applied_pending_batch_validation" and record.get("approval_artifact"):
            last_applied_approval = str(record["approval_artifact"])

    post_apply = None
    if apply_mode and last_applied_approval:
        post_apply = run_post_apply_validation(window, last_applied_approval)

    status = "ok"
    if any(record.get("status") == "blocked" for record in records):
        status = "blocked"
    elif apply_mode and post_apply and post_apply.get("status") != "ok":
        status = "blocked"
    elif all(record.get("status") == "already_current" for record in records) and records:
        status = "ok_no_changes"
    elif not apply_mode:
        status = "ready_to_apply" if records else "ok_no_changes"

    return {
        "generated_at_utc": utc_now(),
        "mode": "apply" if apply_mode else "dry_run",
        "window": window,
        "status": status,
        "category": CATEGORY,
        "authority": {
            "exact_diff_workspace_note_sync_only": True,
            "reads_current_portfolio_config_only": True,
            "writes_portfolio_snapshot_only": True,
            "portfolio_config_weight_mutation_allowed": False,
            "cash_risk_rule_sleeve_execution_mutation_allowed": False,
            "trade_or_account_action_allowed": False,
            "owner_approval_inferred": False,
        },
        "inputs": {
            "proposal_bundle": rel(bundle_path),
            "portfolio_snapshot": "03. Portfolio/Portfolio Snapshot.md",
            "portfolio_config": "tmp/portfolio-config.json",
        },
        "summary": {
            "proposal_count": len(packets),
            "ready_to_apply_count": sum(1 for record in records if record.get("status") == "ready_to_apply"),
            "applied_count": sum(1 for record in records if record.get("status") == "applied_pending_batch_validation"),
            "already_current_count": sum(1 for record in records if record.get("status") == "already_current"),
            "blocked_count": sum(1 for record in records if record.get("status") == "blocked"),
            "writes_performed": sum(1 for record in records if record.get("writes_performed")),
        },
        "records": records,
        "post_apply_validation": post_apply,
        "stop_lines": [
            "This helper syncs only existing draft-weight and sizing-tier semantics into Portfolio Snapshot through exact-diff approval artifacts.",
            "It does not create new allocations, change portfolio-config weights, or authorize cash, risk-rule, sleeve, execution, trade, account, or money-movement actions.",
            "Any blocked proposal record requires source-open inspection or note-surface repair before unattended reuse.",
        ],
    }


def write_markdown(audit: dict[str, Any]) -> None:
    lines = [
        f"# Auto Position Sizing Semantic Sync - {audit['window']}",
        "",
        f"Mode: **{audit['mode']}**",
        f"Status: **{audit['status']}**",
        f"Proposal count: **{audit['summary']['proposal_count']}**",
        f"Applied: **{audit['summary']['applied_count']}**",
        f"Ready to apply: **{audit['summary']['ready_to_apply_count']}**",
        f"Already current: **{audit['summary']['already_current_count']}**",
        f"Blocked: **{audit['summary']['blocked_count']}**",
        "",
        "Authority: exact-diff Portfolio Snapshot sizing semantic sync only; no portfolio-config, cash, risk-rule, sleeve, execution, trade, or account mutation.",
        "",
        "## Records",
    ]
    for record in audit["records"]:
        lines.append(
            f"- {record.get('ticker')} / {record.get('proposal_id')}: {record.get('status')} "
            f"(preview={record.get('preview_status')}, approval={record.get('approval_validation_status')}, writes={record.get('writes_performed')})"
        )
        if record.get("error"):
            lines.append(f"  error: {record['error']}")
    if audit.get("post_apply_validation"):
        lines.extend(
            [
                "",
                "## Post-apply validation",
                f"- status: `{audit['post_apply_validation'].get('status')}`",
                f"- returncode: `{audit['post_apply_validation'].get('returncode')}`",
            ]
        )
    atomic_write_text(OUT_MD, "\n".join(lines).rstrip() + "\n", encoding="utf-8")


def main() -> int:
    args = parse_args()
    bundle_path = Path(args.proposal_bundle)
    if not bundle_path.is_absolute():
        bundle_path = ROOT / bundle_path
    audit = build_audit(bundle_path, args.window, args.apply, args.expires_hours)
    atomic_write_json(OUT_JSON, audit, indent=2, ensure_ascii=False)
    write_markdown(audit)
    print(
        "auto_position_sizing_semantic_sync_status="
        f"{audit['status']} mode={audit['mode']} proposals={audit['summary']['proposal_count']} "
        f"applied={audit['summary']['applied_count']} blocked={audit['summary']['blocked_count']}"
    )
    print(f"audit={rel(OUT_JSON)}")
    return 0 if audit["status"] in {"ok", "ok_no_changes", "ready_to_apply"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
