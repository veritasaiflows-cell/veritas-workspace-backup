from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "model_quality_scorecard.py"
REPORT = ROOT / "tmp" / "model-quality-scorecard.json"
sys.path.insert(0, str(ROOT / "scripts"))

from model_quality_scorecard import finance_response_blocker_metrics


def expect(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def check_finance_response_blocker_metrics(errors: list[str]) -> None:
    legacy_blocker = finance_response_blocker_metrics({
        "status": "ok",
        "summary": {
            "source_freshness_blocked_count": 1,
            "remediation_tracks_needing_repair": 4,
        },
    })
    expect(
        legacy_blocker.get("collection_blocker_count") == 1,
        "the legacy source-freshness count must remain a blocking fallback",
        errors,
    )
    expect(
        legacy_blocker.get("blocking_status") == "collection_blocking_source_or_technical_repair",
        "a legacy real blocker with top-level ok must remain collection-blocking",
        errors,
    )

    explicit_effective = finance_response_blocker_metrics({
        "status": "ok",
        "summary": {
            "source_freshness_blocked_count": 5,
            "source_freshness_raw_blocked_count": 5,
            "source_freshness_structural_hold_non_collection_count": 5,
            "source_freshness_collection_blocked_count": 0,
        },
    })
    expect(
        explicit_effective.get("collection_blocker_count") == 0,
        "explicit effective freshness count must override the raw legacy count",
        errors,
    )
    expect(
        explicit_effective.get("source_freshness_raw_blocked_count") == 5,
        "raw freshness blockers must remain visible",
        errors,
    )
    expect(
        explicit_effective.get("source_freshness_structural_hold_non_collection_count") == 5,
        "structural non-collection holds must remain visible",
        errors,
    )
    expect(
        explicit_effective.get("source_freshness_collection_blocked_count") == 0,
        "effective collection freshness count must remain visible",
        errors,
    )
    expect(
        explicit_effective.get("blocking_status") == "ok",
        "raw structural holds with explicit effective zero must not block collection",
        errors,
    )

    remediation_only = finance_response_blocker_metrics({
        "status": "ok",
        "summary": {"remediation_tracks_needing_repair": 3},
    })
    expect(
        remediation_only.get("collection_blocker_count") == 0,
        "remediation track metadata must not inflate the effective collection blocker count",
        errors,
    )
    expect(
        remediation_only.get("remediation_tracks_needing_repair") == 3,
        "remediation track metadata must remain visible",
        errors,
    )

    decision_debt_only = finance_response_blocker_metrics({
        "status": "blocked",
        "summary": {"primary_state_blocked_count": 2, "below_stop_blocked_count": 1},
    })
    expect(
        decision_debt_only.get("collection_blocker_count") == 0,
        "decision-readiness debt must not become collection debt",
        errors,
    )
    expect(
        decision_debt_only.get("blocking_status") == "decision_readiness_debt_nonblocking",
        "decision-readiness debt alone must remain nonblocking for collection",
        errors,
    )

    clean = finance_response_blocker_metrics({"status": "ok", "summary": {}})
    expect(clean.get("collection_blocker_count") == 0, "clean proof must have zero collection blockers", errors)
    expect(clean.get("blocking_status") == "ok", "clean proof must classify as ok", errors)

    unclassified = finance_response_blocker_metrics({"status": "blocked", "summary": {}})
    expect(
        unclassified.get("blocking_status") == "unclassified_blocked_status",
        "a non-ok proof with no classified debt must fail closed as unclassified",
        errors,
    )


def main(argv: list[str] | None = None) -> int:
    errors: list[str] = []
    check_finance_response_blocker_metrics(errors)
    if argv is not None and "--unit-only" in argv:
        if errors:
            for error in errors:
                print(f"FAIL: {error}")
            return 1
        print("ok: model quality scorecard blocker semantics regressions passed")
        return 0

    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--write", "--validate"],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    expect(result.returncode == 0, f"scorecard command failed: {result.stdout} {result.stderr}", errors)
    expect(REPORT.exists(), "model quality scorecard report missing", errors)

    if REPORT.exists():
        report = json.loads(REPORT.read_text(encoding="utf-8"))
        expect(report.get("schema") == "wf74.model_quality_scorecard.v1", "unexpected scorecard schema", errors)
        expect(report.get("validation", {}).get("status") == "ok", "scorecard validation should be ok", errors)

        loops = report.get("efficiency_loops", {})
        expect(loops.get("schema") == "wf74.efficiency_loops.v1", "efficiency loop schema missing", errors)
        expect(loops.get("status") == "active_partial", "efficiency loop status should be active_partial", errors)
        loop_rows = [row for row in loops.get("loops", []) if isinstance(row, dict)]
        domains = {row.get("domain") for row in loop_rows}
        for domain in {"coding", "models", "implementation", "routing", "operations"}:
            expect(domain in domains, f"missing efficiency loop domain: {domain}", errors)
        for row in loop_rows:
            loop_id = row.get("loop_id") or "<unknown>"
            for field in ("owner_surface", "status", "meaning", "next_safe_action", "feedback_sink", "proof_sources"):
                expect(bool(row.get(field)), f"{loop_id} missing {field}", errors)

        queue = loops.get("enhancement_queue", [])
        expect(len(queue) >= 3, "enhancement queue should name at least three next actions", errors)
        owners = {row.get("owner") for row in queue if isinstance(row, dict)}
        expect("WF74 / model-quality-scorecard" in owners, "WF74 owner missing from enhancement queue", errors)
        expect("WF55 / WF74" in owners, "WF55/WF74 owner gate missing from enhancement queue", errors)

        rules = loops.get("standing_rules", [])
        rule_ids = {row.get("rule_id") for row in rules if isinstance(row, dict)}
        for rule_id in {
            "input_changed_not_broken",
            "producer_before_consumer",
            "operational_telemetry_only",
            "freshness_precision",
            "self_contained_when_possible",
        }:
            expect(rule_id in rule_ids, f"missing efficiency loop standing rule: {rule_id}", errors)
        for row in rules:
            if not isinstance(row, dict):
                continue
            rule_id = row.get("rule_id") or "<unknown>"
            for field in ("principle", "meaning", "owner_surface", "next_safe_action"):
                expect(bool(row.get(field)), f"{rule_id} missing {field}", errors)

        boundary = report.get("authority_boundary", {})
        for flag in (
            "model_ranking_claim",
            "investment_correctness_from_runtime_metrics",
            "base_model_self_modification",
            "owner_approval_inference",
            "portfolio_or_canon_mutation",
            "paper_or_live_or_account_action",
            "otel_backend_enablement_in_this_lane",
        ):
            expect(boundary.get(flag) is False, f"authority flag must remain false: {flag}", errors)

        perf = report.get("tracks", {}).get("performance", {})
        perf_metrics = perf.get("metrics", {}) if isinstance(perf, dict) else {}
        expect(len(perf_metrics) > 0, "performance track should expose normalized metrics", errors)
        for field in (
            "runtime_checks_total",
            "otel_window_count",
            "model_run_row_count",
            "cost_metric_available",
            "token_metric_available",
        ):
            expect(field in perf_metrics, f"performance metrics missing {field}", errors)
        # Cost/token economics now source from the authoritative token_usage_ledger
        # (Gateway usage-cost path) per the 2026-08-13 telemetry role split, not from
        # the thin OTEL debug log. Availability is allowed, but the honesty constraints
        # below must stay locked: API-equivalent only (never an invoice), partial
        # coverage, and cross-model economic claims remain gated.
        expect(
            isinstance(perf_metrics.get("cost_metric_available"), bool),
            "cost_metric_available must be a bool sourced from token_usage_ledger presence",
            errors,
        )
        expect(
            isinstance(perf_metrics.get("token_metric_available"), bool),
            "token_metric_available must be a bool sourced from token_usage_ledger presence",
            errors,
        )
        economics = perf.get("token_cost_economics", {}) if isinstance(perf, dict) else {}
        expect(
            economics.get("actual_billed_cost_known") is False,
            "token/cost must stay API-equivalent benchmark, never a claimed invoice",
            errors,
        )
        if perf_metrics.get("cost_metric_available") is True:
            expect(
                float(economics.get("api_equivalent_cost_event_coverage_percent") or 0) > 0,
                "when cost metric is available, coverage percent must be positive and provenance-backed",
                errors,
            )
            expect(
                bool(economics.get("authority_note")),
                "cost economics must carry an authority_note keeping cross-model claims gated",
                errors,
            )
        otel_local = perf.get("otel_local_ops", {}) if isinstance(perf, dict) else {}
        expect(otel_local.get("window_summary_status") == "ok", "OTEL window summary should be ok", errors)
        expect(otel_local.get("window_count") == 5, "OTEL window summary should expose five windows", errors)
        for window_id in {"intraday_1h", "intraday_6h", "daily_24h", "weekly_7d", "monthly_30d"}:
            expect(window_id in set(otel_local.get("window_ids") or []), f"missing OTEL window in scorecard: {window_id}", errors)

        decision = report.get("tracks", {}).get("decision_quality", {})
        decision_metrics = decision.get("metrics", {}) if isinstance(decision, dict) else {}
        expect(
            decision.get("readiness") in {
                "active_measurement_only_semantic_claims_gated",
                "partial_ex_ante_and_wf55_measurement_active_durable_enabled",
                "partial_ex_ante_active_outcomes_blocked",
                "partial_ex_ante_and_wf55_measurement_active_durable_blocked",
                "blocked_on_wf55",
            },
            "decision quality readiness should remain bounded",
            errors,
        )
        expect(decision_metrics.get("scorecard_active_now") is True, "decision quality scorecard should be active now", errors)
        expect("wf55_measurement_grade_count" in decision_metrics, "decision quality should include WF55 measurement grade count", errors)
        expect(decision_metrics.get("wf55_decision_quality_claim_allowed_now") is False, "WF55 measurement must not allow decision-quality claims", errors)
        expect(decision_metrics.get("wf55_durable_v2_append_allowed") is True, "WF55 measurement should expose review-only durable append approval", errors)
        expect(decision_metrics.get("semantic_outcome_claim_allowed") is False, "semantic outcome claims should remain gated", errors)
        expect(decision_metrics.get("predictive_or_model_ranking_allowed") is False, "predictive/model-ranking claims should remain blocked", errors)
        expect(
            decision_metrics.get("finance_response_quality_blocking_status") in {
                "ok",
                "decision_readiness_debt_nonblocking",
            },
            "finance response quality must block only on source/technical repair debt in the scorecard",
            errors,
        )
        expect(
            decision_metrics.get("finance_response_collection_blocker_count") == 0,
            "current finance response quality proof should not expose collection-blocking source/technical debt",
            errors,
        )
        expect(
            "finance_response_decision_readiness_debt_count" in decision_metrics,
            "decision quality should expose nonblocking finance decision-readiness debt",
            errors,
        )
        claim_blockers = decision.get("claim_blockers", [])
        expect(any("semantic outcome grades" in str(item) for item in claim_blockers), "semantic outcome claim blocker should be explicit", errors)
        gates = {gate.get("gate"): gate for gate in report.get("readiness_gates", []) if isinstance(gate, dict)}
        wf55_gate = gates.get("wf55_outcome_grades", {})
        expect(wf55_gate.get("status") == "claim_maturity_gated", "WF55 outcome gate should be claim-maturity gated", errors)
        expect(wf55_gate.get("blocks_track") == "none", "WF55 outcome gate should not block active decision_quality track", errors)
        expect(
            wf55_gate.get("blocks_claim") == "semantic_predictive_decision_quality",
            "WF55 outcome gate should block only semantic/predictive decision-quality claims",
            errors,
        )

        learning = report.get("tracks", {}).get("learning_capture", {})
        expect(learning.get("readiness") == "active_metadata_only", "learning capture should be active metadata-only", errors)
        learning_metrics = learning.get("metrics", {})
        expect(learning_metrics.get("privacy_scan_status") == "ok", "learning capture privacy scan should be ok", errors)
        expect((learning_metrics.get("tool_rows") or 0) > 0, "learning capture should include tool rows", errors)
        expect((learning_metrics.get("coding_rows") or 0) > 0, "learning capture should include coding rows", errors)
        expect("improvement_open_count" in learning_metrics, "learning capture should include improvement open count", errors)
        expect("improvement_closed_count" in learning_metrics, "learning capture should include improvement closed count", errors)
        expect("improvement_closure_rate" in learning_metrics, "learning capture should include improvement closure rate", errors)
        expect(learning_metrics.get("improvement_anti_theater_status") in {
            "blocked_by_overdue_backlog",
            "proposal_loop_active_no_closure_proof",
            "proposal_loop_with_closure_proof",
        }, "learning capture anti-theater status missing", errors)

    if errors:
        for error in errors:
            print(f"FAIL: {error}")
        return 1
    print("ok: model quality scorecard efficiency loops are present and bounded")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
