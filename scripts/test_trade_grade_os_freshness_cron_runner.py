from __future__ import annotations

import trade_grade_os_freshness_cron_runner as runner


def expect(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def main() -> int:
    errors: list[str] = []
    names = [step[0] for step in runner.command_plan()]
    cards_only = [step[0] for step in runner.command_plan(["cards"])]

    required = [
        "wf78_auto_tier_router_post_promotion_gates",
        "wf78_tier_a_technical_refresh",
        "wf78_routing_delta",
        "wf78_event_triggered_rerouting",
        "wf78_evidence_drag_reducer",
        "wf78_source_open_repair_executor",
        "wf78_ticker_freshness_ledger",
        "wf78_source_open_work_packet",
        "wf78_deployment_readiness_review",
        "wf78_tier_weighted_freshness_resolver",
        "wf78_clean_tier_roster_final_publish",
        "wf78_truth_layer_map_final_publish",
        "wf78_tier_semantics_guard_final_publish",
        "wf84_canonical_data_plane",
        "wf85_decision_cards",
        "wf85_full_answer_assembler",
        "wf84_canonical_data_plane_post_full_answer",
        "finance_cache_frontdoor",
        "wf85_source_open_reconciliation_contract",
        "wf84_wf85_full_answer_parity",
    ]
    for name in required:
        expect(name in names, f"missing runner step: {name}", errors)

    if not errors:
        wf78_safe_order = [
            "wf78_auto_tier_router_post_promotion_gates",
            "wf78_tier_a_technical_refresh",
            "wf78_routing_delta",
            "wf78_event_triggered_rerouting",
            "wf78_evidence_drag_reducer",
            "wf78_source_open_repair_executor",
            "wf78_ticker_freshness_ledger",
            "wf78_source_open_work_packet",
            "wf78_deployment_readiness_review",
            "wf78_tier_weighted_freshness_resolver",
        ]
        expect(
            [names.index(name) for name in wf78_safe_order]
            == sorted(names.index(name) for name in wf78_safe_order),
            "WF78 evidence and deployment-readiness producers must follow the final router in dependency order",
            errors,
        )
        final_publish_order = [
            "wf78_clean_tier_roster_final_publish",
            "wf78_truth_layer_map_final_publish",
            "wf78_tier_semantics_guard_final_publish",
        ]
        expect(
            names.index("wf78_auto_tier_router_post_promotion_gates") < names.index(final_publish_order[0]),
            "tier-truth publication must start after the final router write",
            errors,
        )
        expect(
            [names.index(name) for name in final_publish_order]
            == sorted(names.index(name) for name in final_publish_order),
            "tier-truth publication must run roster, then map, then semantics guard",
            errors,
        )
        expect(
            names[-3:] == final_publish_order,
            "tier-truth publication must be terminal so later runner steps cannot invalidate its router lineage",
            errors,
        )
        expect(
            names.index("wf84_canonical_data_plane") < names.index("wf85_decision_cards"),
            "WF84 must rebuild before WF85 cards",
            errors,
        )
        expect(
            names.index("wf85_decision_cards") < names.index("wf85_full_answer_assembler"),
            "WF85 cards must rebuild before full-answer assembler",
            errors,
        )
        expect(
            names.index("wf85_full_answer_assembler") < names.index("wf84_canonical_data_plane_post_full_answer"),
            "WF84 section context must refresh after full-answer assembler",
            errors,
        )
        expect(
            names.index("wf84_canonical_data_plane_post_full_answer") < names.index("finance_cache_frontdoor"),
            "finance cache must run after the post-assembler WF84 rebuild creates its decision overview view",
            errors,
        )
        expect(
            names.index("finance_cache_frontdoor") < names.index("wf85_source_open_reconciliation_contract"),
            "Source-open reconciliation must consume the finance cache refreshed after the post-assembler WF84 rebuild",
            errors,
        )
        expect(
            names.index("wf85_source_open_reconciliation_contract") < names.index("wf84_wf85_full_answer_parity"),
            "Full-answer parity must run after source-open reconciliation validates the refreshed cache generation",
            errors,
        )

    expect(
        "wf85_full_answer_assembler" in runner.EXPECTED_ARTIFACTS,
        "runner expected artifacts must include the full-answer assembler rollup",
        errors,
    )
    for artifact in (
        "wf78_tier_a_technical_refresh",
        "wf78_event_triggered_rerouting",
        "wf78_evidence_drag_reduction",
        "wf78_source_open_repair_execution",
        "wf78_ticker_freshness_ledger",
        "wf78_source_open_work_packets",
        "wf78_deployment_readiness_review",
        "wf78_tier_weighted_freshness_resolution",
        "wf78_clean_tier_roster",
        "wf78_truth_layer_map",
        "wf78_tier_semantics_guard",
    ):
        expect(artifact in runner.EXPECTED_ARTIFACTS, f"missing WF78 proof artifact: {artifact}", errors)

    wf78_steps = {name: command for name, command, _timeout in runner.command_plan(["wf78"])}
    expect(
        wf78_steps.get("wf78_tier_a_technical_refresh", [None, None])[1] == "scripts\\technical_refresh.py",
        "WF78 promotion chain must refresh current Tier A technicals before routing consumers",
        errors,
    )
    expect(
        wf78_steps.get("wf78_source_open_repair_executor", [])[2:4] == ["--tier", "all"],
        "WF78 source-open repair executor must stay bounded to the explicit all-tier review chain",
        errors,
    )
    forbidden_step_paths = {
        "scripts\\deployment_readiness_surface.py",
        "scripts\\wf78_source_open_patch_orchestrator.py",
    }
    planned_step_paths = {
        command[1]
        for _name, command, _timeout in runner.command_plan()
        if len(command) > 1
    }
    expect(
        not (planned_step_paths & forbidden_step_paths),
        "review-only runner must exclude deployment-readiness surface and source-open patch orchestrator",
        errors,
    )
    expect("wf85_decision_cards" in cards_only, "cards component must include decision-card build", errors)
    expect("wf85_full_answer_assembler" not in cards_only, "cards component must not include full-answer assembler", errors)

    digest_a = runner.semantic_digest({"generated_at_utc": "one", "rows": [{"ticker": "A", "score": 1}]})
    digest_b = runner.semantic_digest({"generated_at_utc": "two", "rows": [{"ticker": "A", "score": 1}]})
    digest_c = runner.semantic_digest({"generated_at_utc": "two", "rows": [{"ticker": "A", "score": 2}]})
    expect(digest_a == digest_b, "semantic digest must ignore volatile timestamps", errors)
    expect(digest_a != digest_c, "semantic digest must change on semantic input changes", errors)

    unchanged = runner.full_answer_rebuild_decision("changed", digest_a, digest_b)
    changed = runner.full_answer_rebuild_decision("changed", digest_a, digest_c)
    expect(unchanged["command_run"] is False, "changed mode must skip unchanged full-answer inputs", errors)
    expect(changed["command_run"] is True, "changed mode must run changed full-answer inputs", errors)

    clean_review_only_summary = {
        "finance_state_status": "ok",
        "wf84_status": "ok",
        "wf84_phase6_10_status": "ok",
        "wf84_phase6_10_critical_error_count": 0,
        "wf84_wf85_full_answer_parity_status": "ok",
        "wf85_wf84_json_sqlite_parity": "ok",
        "trade_grade_data_ready_for_decisions": True,
        "wf85_deployment_timing_gate_status": "ok",
        "wf85_deployment_timing_gate_validation": "ok",
        "wf85_tier_a_b_timing_row_count": 1,
        "tier_a_b_band_cron_guard_validation": "ok",
        "tier_a_b_stale_complete_band_context_count": 0,
        "tier_a_b_cron_contracts_ok": True,
        "wf85_full_answer_assembler_status": "ok",
        "finance_cache_frontdoor_status": "ok",
        "wf78_route_readiness_p3_status": "ok",
        "wf78_clean_tier_roster_status": "ok",
        "wf78_clean_tier_roster_validation": "ok",
        "wf78_truth_layer_map_status": "ok",
        "wf78_truth_layer_map_validation": "ok",
        "wf78_tier_semantics_guard_status": "ok",
        "wf78_tier_semantics_guard_validation": "ok",
        "wf85_source_open_reconciliation_status": "ok",
        "wf85_source_open_reconciliation_unnecessary_blocker_count": 0,
        "wf85_source_open_reconciliation_mismatch_error_count": 0,
        "wf85_source_open_reconciliation_producer_order_error_count": 0,
        "wf84_forbidden_authority_true_count": 0,
        "wf85_authority_violation_count": 0,
        "wf85_forbidden_action_phrase_count": 0,
        "wf85_approval_card_draft_count": 0,
        "wf85_review_ready_count": 0,
        "wf67_paper_guard_fresh": False,
        "wf67_paper_guard_clean": False,
    }

    no_drafts_validation = runner.validate_payload({
        "authority_boundary": runner.AUTHORITY_BOUNDARY,
        "steps": [],
        "artifact_records": [],
        "summary": clean_review_only_summary,
    })
    expect(no_drafts_validation["status"] == "ok", f"stale WF67 guard without drafts should be info-only: {no_drafts_validation}", errors)
    expect(no_drafts_validation["warning_count"] == 0, f"unexpected warnings: {no_drafts_validation}", errors)
    expect(
        "wf67_guard_stale_with_no_approval_drafts_no_operator_action" in no_drafts_validation.get("info", []),
        f"expected WF67 no-drafts info marker: {no_drafts_validation}",
        errors,
    )

    tolerated_refresh_step_validation = runner.validate_payload({
        "authority_boundary": runner.AUTHORITY_BOUNDARY,
        "steps": [{"name": "finance_intelligence_state_refresh_100", "ok": False, "returncode": 1}],
        "artifact_records": [
            {
                "name": "finance_state_refresh_100",
                "exists": True,
                "status": "ok",
                "authority_widened": False,
            }
        ],
        "summary": clean_review_only_summary,
    })
    expect(
        tolerated_refresh_step_validation["status"] == "ok",
        f"review-only refresh-100 returncode mismatch should be tolerated when artifacts are clean: {tolerated_refresh_step_validation}",
        errors,
    )
    expect(
        "tolerated_review_only_step_returncode:finance_intelligence_state_refresh_100" in tolerated_refresh_step_validation.get("info", []),
        f"expected tolerated returncode info marker: {tolerated_refresh_step_validation}",
        errors,
    )

    unsafe_refresh_step_validation = runner.validate_payload({
        "authority_boundary": runner.AUTHORITY_BOUNDARY,
        "steps": [{"name": "finance_intelligence_state_refresh_100", "ok": False, "returncode": 1}],
        "artifact_records": [
            {
                "name": "finance_state_refresh_100",
                "exists": True,
                "status": "ok",
                "authority_widened": False,
            }
        ],
        "summary": {**clean_review_only_summary, "wf85_approval_card_draft_count": 1},
    })
    expect(
        "failed_steps:finance_intelligence_state_refresh_100" in unsafe_refresh_step_validation["errors"],
        f"refresh-100 failure must remain hard-blocked when approval drafts are present: {unsafe_refresh_step_validation}",
        errors,
    )

    draft_validation = runner.validate_payload({
        "authority_boundary": runner.AUTHORITY_BOUNDARY,
        "steps": [],
        "artifact_records": [],
        "summary": {**clean_review_only_summary, "wf85_approval_card_draft_count": 1},
    })
    expect(
        "wf85_approval_card_drafts_present_without_clean_fresh_wf67_guard" in draft_validation["errors"],
        f"approval drafts must still require a clean fresh WF67 guard: {draft_validation}",
        errors,
    )

    finance_debt_validation = runner.validate_payload({
        "authority_boundary": runner.AUTHORITY_BOUNDARY,
        "steps": [],
        "artifact_records": [],
        "summary": {
            **clean_review_only_summary,
            "tier_a_b_band_cron_guard_validation": "warning",
            "tier_a_b_stale_complete_band_context_count": 2,
        },
    })
    expect(finance_debt_validation["status"] == "warning", f"finance-domain debt should warn, not block: {finance_debt_validation}", errors)
    expect(
        "tier_a_b_complete_band_context_finance_domain_debt_present" in finance_debt_validation["warnings"],
        f"expected stale Tier A/B debt warning: {finance_debt_validation}",
        errors,
    )
    expect(
        "tier_a_b_complete_band_context_stale" not in finance_debt_validation["errors"],
        f"stale Tier A/B debt must not hard-block when the guard is warning-grade: {finance_debt_validation}",
        errors,
    )

    if errors:
        print("trade_grade_os_freshness_cron_runner_tests_failed")
        for error in errors:
            print(f"- {error}")
        return 1
    print("trade_grade_os_freshness_cron_runner_tests_passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
