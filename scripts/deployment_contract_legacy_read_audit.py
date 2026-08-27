"""Report-only audit for legacy deployment-state field reads.

Slice 5 of the deployment-state contract migration. This does not remove
legacy aliases and does not fail normal validation by default. It classifies
direct reads of legacy top-level fields so future work can migrate readers to
`deployment_status` / `deployment_contract`, or reconstruct from
`deployment_contract.raw_context` when raw trace is required.

Authority: review/proof only. No canon/portfolio mutation, no SQL promotion,
no paper/live/brokerage/account action, no owner-approval inference.
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
OUT = ROOT / "tmp" / "deployment-contract-legacy-read-audit.json"

LEGACY_FIELDS = (
    "workflow_state",
    "action_state",
    "machine_state",
    "surface_state",
    "base_surface_state",
)

FIELD_PATTERN = re.compile(r"(?P<quote>['\"])(workflow_state|action_state|machine_state|surface_state|base_surface_state)(?P=quote)")
DIRECT_READ_PATTERN = re.compile(
    r"(?:\.get\(\s*(?P<q1>['\"])(?P<get>workflow_state|action_state|machine_state|surface_state|base_surface_state)(?P=q1)"
    r"|\[\s*(?P<q2>['\"])(?P<index>workflow_state|action_state|machine_state|surface_state|base_surface_state)(?P=q2)\s*\])"
)

# Files where direct legacy reads are part of the contract, a validator, or an
# intentional compatibility writer. They should not trigger deprecation debt.
ALLOWED_EXACT: dict[str, str] = {
    "board_state_contract.py": "contract_core",
    "deployment_contract_agreement_validator.py": "agreement_validator_raw_context_gate",
    "deployment_contract_legacy_read_audit.py": "slice5_audit_tool",
    "deployment_readiness_surface.py": "additive_writer_compatibility_aliases",
    "trigger_sheet_refresh.py": "additive_writer_trigger_aliases",
    "deployment_check.py": "raw_deployment_machine_writer",
    "board_canon_guardrail.py": "raw_invariant_validator",
    "candidate_packet_validator.py": "raw_invariant_validator",
    "canonical_status_invariant_validator.py": "raw_invariant_validator",
    "validate_portfolio_config.py": "owner_config_validator",
    "band_refresh.py": "owner_config_proposal_generator",
    "watchlist_promotion_radar.py": "intentional_or_across_raw_repair_logic",
    "ticker_monitoring_performance.py": "raw_vocabulary_aggregator",
    "wf78_production_tier_adjudication.py": "deprecated_for_authority_archive_candidate",
    "canon_drift_freshness_gate.py": "raw_freshness_drift_guard",
    "finance_data_coverage.py": "coverage_field_registry",
    "fundamental_metrics_refresh.py": "owner_metadata_state_propagation",
    "portfolio_mutation_semantic_patch_generator.py": "portfolio_note_raw_patch_context",
    "state_history_capture.py": "raw_state_history_capture",
    "sql_source_truth_ab_consumer_probe.py": "sql_source_truth_field_probe",
    "sql_source_truth_exact_apply_packet.py": "sql_source_truth_apply_packet",
    "sql_source_truth_field_family_decision_packet.py": "sql_source_truth_field_family_packet",
    "stale_intelligence_guardrail.py": "raw_staleness_guardrail",
    "wf78_auto_tier_router.py": "tier_router_workflow_state_input",
    "wf78_tier_b_final_promotion_packet.py": "deprecated_for_authority_archive_candidate",
}

# Readers/exporters that may remain behaviorally correct, but should be warned
# because direct legacy reads are now deprecation debt unless they explicitly
# move to the shared contract or raw_context.
WARNING_EXACT: dict[str, str] = {
    "artifact_index.py": "reader_index_should_prefer_canonical_contract_when_practical",
    "auto_apply_entry_band_maintenance.py": "gated_entry_band_apply_proposal_trace",
    "band_hygiene_freshness_controller.py": "entry_band_hygiene_proposal_trace",
    "call_log_sync.py": "reader_sync_should_prefer_canonical_contract_when_practical",
    "dashboard_payload.py": "ui_reader_should_prefer_canonical_contract_when_practical",
    "daily_executive_brief.py": "brief_reader_should_prefer_canonical_contract_when_practical",
    "daily_price_trend_signals.py": "signal_reader_should_prefer_canonical_contract_when_practical",
    "daily_review_objects.py": "scorer_reader_should_prefer_canonical_contract_when_practical",
    "ticker_intelligence_card.py": "ticker_card_reader_has_contract_but_still_reads_legacy_trace",
    "today_card_generator.py": "user_facing_reader_should_prefer_canonical_contract_when_practical",
    "weekly_intelligence_brief.py": "brief_reader_should_prefer_canonical_contract_when_practical",
    "weekly_review_skeleton.py": "brief_reader_should_prefer_canonical_contract_when_practical",
    "workbook_export.py": "export_reader_should_prefer_canonical_contract_when_practical",
    "chief_intelligence_promotion_gate.py": "promotion_gate_reader_should_prefer_canonical_contract_when_practical",
    "finance_stack_snapshot.py": "snapshot_reader_should_prefer_canonical_contract_when_practical",
    "finance_intelligence_router_qa.py": "qa_reader_should_prefer_canonical_contract_when_practical",
    "finance_intelligence_state.py": "front_door_reader_should_prefer_canonical_contract_when_practical",
    "full_portfolio_view.py": "portfolio_view_reader_should_prefer_canonical_contract_when_practical",
    "full_intelligence_answer_parity.py": "parity_validator_compatibility_reader",
    "generate_entry_band_status.py": "entry_band_reader_should_prefer_canonical_contract_when_practical",
    "intraday_entry_watcher.py": "intraday_reader_should_prefer_canonical_contract_when_practical",
    "market_intelligence_event_router.py": "event_router_reader_should_prefer_canonical_contract_when_practical",
    "portfolio_mutation_proposal_generator.py": "proposal_reader_should_prefer_canonical_contract_when_practical",
    "positioning_ranking_refresh.py": "ranking_reader_should_prefer_canonical_contract_when_practical",
    "post_earnings_note_targets.py": "post_earnings_reader_should_prefer_canonical_contract_when_practical",
    "post_earnings_prep.py": "post_earnings_reader_should_prefer_canonical_contract_when_practical",
    "premarket_snapshot.py": "premarket_reader_should_prefer_canonical_contract_when_practical",
    "regime_scoring_refresh.py": "regime_reader_should_prefer_canonical_contract_when_practical",
    "render_composite_regime_sector_pdf.py": "pdf_reader_should_prefer_canonical_contract_when_practical",
    "sector_allocation_decision_matrix.py": "sector_reader_should_prefer_canonical_contract_when_practical",
    "sector_expansion_board.py": "sector_reader_should_prefer_canonical_contract_when_practical",
    "canon_volatile_execution_board_sync.py": "canon_sync_reader_should_prefer_canonical_contract_when_practical",
    "post_earnings_scorecard.py": "post_earnings_reader_should_prefer_canonical_contract_when_practical",
    "reference_band_note_sync.py": "note_sync_reader_should_prefer_canonical_contract_when_practical",
    "research_freshness_opportunity_review.py": "research_review_reader_should_prefer_canonical_contract_when_practical",
    "ticker_answer_packet.py": "legacy_answer_packet_compatibility_writer",
    "trade_grade_full_answer_assembler.py": "wf85_full_answer_compatibility_reader",
    "wf78_tier_label_sync_preview.py": "tier_label_sync_reader_should_prefer_canonical_contract_when_practical",
    "wf78_source_open_work_packet.py": "source_open_repair_reader_should_prefer_canonical_contract_when_practical",
}

ALLOWED_NAME_PARTS = (
    "validator",
    "validation",
    "check",
    "preflight",
    "scaffold",
    "test_",
)

WARNING_NAME_PARTS = (
    "dashboard",
    "brief",
    "card",
    "review",
    "workbook",
    "signal",
    "sync",
)


def relpath(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        return str(path)


def classify(path: Path) -> tuple[str, str]:
    name = path.name
    lower = name.lower()
    if name in ALLOWED_EXACT:
        return "allowed", ALLOWED_EXACT[name]
    if name in WARNING_EXACT:
        return "warning", WARNING_EXACT[name]
    if lower.startswith("test_") or "\\test_" in str(path).lower():
        return "allowed", "test_or_fixture"
    if any(part in lower for part in ALLOWED_NAME_PARTS):
        return "allowed", "validator_or_preflight_by_name"
    if any(part in lower for part in WARNING_NAME_PARTS):
        return "warning", "probable_reader_or_user_facing_surface"
    return "warning", "unclassified_direct_legacy_read"


def iter_hits() -> list[dict[str, Any]]:
    hits: list[dict[str, Any]] = []
    for path in sorted(SCRIPTS.rglob("*.py")):
        # Skip obvious generated/cache folders if they ever appear below scripts.
        if "__pycache__" in path.parts:
            continue
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except UnicodeDecodeError:
            lines = path.read_text(errors="replace").splitlines()
        disposition, reason = classify(path)
        for lineno, line in enumerate(lines, start=1):
            fields = sorted({match.group("get") or match.group("index") for match in DIRECT_READ_PATTERN.finditer(line)})
            if not fields:
                continue
            hits.append(
                {
                    "path": relpath(path),
                    "line": lineno,
                    "fields": fields,
                    "disposition": disposition,
                    "reason": reason,
                    "text": line.strip()[:240],
                }
            )
    return hits


def build_report() -> dict[str, Any]:
    hits = iter_hits()
    by_disposition = Counter(hit["disposition"] for hit in hits)
    by_reason = Counter(hit["reason"] for hit in hits)
    by_file: dict[str, dict[str, Any]] = {}
    for hit in hits:
        entry = by_file.setdefault(
            hit["path"],
            {
                "path": hit["path"],
                "disposition": hit["disposition"],
                "reason": hit["reason"],
                "hit_count": 0,
                "fields": set(),
            },
        )
        entry["hit_count"] += 1
        entry["fields"].update(hit["fields"])

    files_out = []
    for entry in sorted(by_file.values(), key=lambda item: (item["disposition"], item["path"])):
        files_out.append({**entry, "fields": sorted(entry["fields"])})

    warning_hits = [hit for hit in hits if hit["disposition"] == "warning"]
    allowed_hits = [hit for hit in hits if hit["disposition"] == "allowed"]
    unclassified = [hit for hit in hits if hit["reason"] == "unclassified_direct_legacy_read"]

    return {
        "schema_version": "deployment_contract_legacy_read_audit.v1",
        "generated_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "status": "warning" if warning_hits else "ok",
        "authority": {
            "review_only": True,
            "canonical_mutation_allowed": False,
            "portfolio_mutation_allowed": False,
            "sql_canon_promotion_allowed": False,
            "paper_or_live_execution_allowed": False,
            "brokerage_or_account_action_allowed": False,
            "owner_approval_inferred": False,
        },
        "policy": {
            "top_level_legacy_fields_are_deprecated_for_readers": True,
            "legacy_fields": list(LEGACY_FIELDS),
            "preferred_reader_route": "read deployment_status / deployment_contract directly",
            "preferred_reconstruction_route": "deployment_contract(record['deployment_contract']['raw_context'])",
            "forbidden_reconstruction_route": "deployment_contract(top_level_record)",
            "why": "top-level legacy fields are lossy for below-stop/no-chase overrides; raw_context is the authoritative reconstruction source",
            "report_only": True,
        },
        "summary": {
            "hit_count": len(hits),
            "file_count": len(by_file),
            "allowed_hit_count": len(allowed_hits),
            "warning_hit_count": len(warning_hits),
            "unclassified_warning_hit_count": len(unclassified),
            "by_disposition": dict(sorted(by_disposition.items())),
            "by_reason": dict(sorted(by_reason.items())),
        },
        "files": files_out,
        "warning_hits": warning_hits,
        "allowed_hits_sample": allowed_hits[:40],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit direct legacy deployment-state reads (report-only).")
    parser.add_argument("--write", action="store_true", help="Write tmp/deployment-contract-legacy-read-audit.json.")
    parser.add_argument(
        "--fail-on-unclassified",
        action="store_true",
        help="Exit non-zero if unclassified warning reads are found. Normal slice-5 mode is warning-only.",
    )
    args = parser.parse_args()
    report = build_report()
    if args.write:
        OUT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(f"wrote {relpath(OUT)}")
    summary = report["summary"]
    print(
        "deployment_contract_legacy_read_audit: "
        f"{report['status']} ({summary['file_count']} files, {summary['hit_count']} hits, "
        f"{summary['warning_hit_count']} warning hits, "
        f"{summary['unclassified_warning_hit_count']} unclassified warning hits)"
    )
    if args.fail_on_unclassified and summary["unclassified_warning_hit_count"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
