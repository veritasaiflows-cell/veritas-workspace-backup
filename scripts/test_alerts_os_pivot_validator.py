import unittest
import tempfile
from pathlib import Path

import alerts_os_pivot_validator as pivot


def scan_text(text: str, suffix: str = ".md") -> list[dict]:
    with tempfile.TemporaryDirectory() as tmp_name:
        path = Path(tmp_name) / f"probe{suffix}"
        path.write_text(text, encoding="utf-8")
        return pivot.active_semantic_hits(path)


def scan_skill_text(text: str) -> list[dict]:
    with tempfile.TemporaryDirectory() as tmp_name:
        path = Path(tmp_name) / "SKILL.md"
        path.write_text(text, encoding="utf-8")
        return pivot.active_retired_workflow_skill_hits(path)


class AlertsOsPivotValidatorTests(unittest.TestCase):
    def test_active_playbook_scope_includes_operating_procedures_and_qa_surfaces(self) -> None:
        relative = {
            path.relative_to(pivot.ROOT).as_posix()
            for path in (
                *pivot.ACTIVE_SEMANTIC_SURFACES,
                *pivot.ACTIVE_OPERATING_PROCEDURES,
                *pivot.ACTIVE_RESEARCH_DEPARTMENT_REVIEWS,
            )
        }
        self.assertIn("06. Playbooks/Active Model Prompt Queue.md", relative)
        self.assertIn("06. Playbooks/Market Data Coverage Matrix.md", relative)
        self.assertIn("scripts/README.md", relative)
        self.assertIn("scripts/veritas_question_router.py", relative)
        self.assertIn("scripts/wf88_os2_control_packet.py", relative)
        self.assertIn(
            "06. Playbooks/Operating Procedures/Subagent Load Budget and Staff Handoff Standard.md",
            relative,
        )
        self.assertIn("06. Playbooks/Operating Procedures/Veritas Encounter Contract.md", relative)
        self.assertIn(
            "06. Playbooks/Operating Procedures/Weekly Sector Expansion Review Procedure.md",
            relative,
        )

    def test_active_semantic_hits_detects_affirmative_legacy_state(self) -> None:
        path = Path(self.id().replace(".", "-") + ".md")
        try:
            path.write_text("# Active route\nMaintain portfolio allocations and paper positions.\n", encoding="utf-8")
            hits = pivot.active_semantic_hits(path)
        finally:
            path.unlink(missing_ok=True)
        self.assertEqual(len(hits), 1)

    def test_active_semantic_hits_scans_details_and_dated_lines(self) -> None:
        details_hits = scan_text(
            "<details>\n<summary>Implementation</summary>\n"
            "Maintain portfolio allocations and paper positions.\n</details>\n"
        )
        self.assertEqual(len(details_hits), 1, details_hits)
        dated_hits = scan_text("2026-08-30 Maintain portfolio allocations.\n")
        self.assertEqual(len(dated_hits), 1, dated_hits)

    def test_active_semantic_hits_scans_after_same_line_historical_details(self) -> None:
        for closing_tag in ("</details>", "</details >", "</details   >", "</details\n>"):
            with self.subTest(closing_tag=closing_tag):
                hits = scan_text(
                    "<details><summary>Historical archive</summary>"
                    f"Paper execution was retired.{closing_tag} Maintain portfolio allocations.\n"
                )
                self.assertEqual(len(hits), 1, hits)
                self.assertIn("Maintain portfolio allocations", hits[0]["text"])

    def test_active_semantic_hits_does_not_treat_legacy_input_as_action_negation(self) -> None:
        hits = scan_text("Use legacy data to maintain portfolio allocations.\n")
        self.assertEqual(len(hits), 1, hits)

    def test_active_semantic_hits_catches_actions_after_historical_legacy_terms(self) -> None:
        probes = (
            "Historical data feeds portfolio allocations maintained by the active workflow.\n",
            "Legacy records support paper positions managed by the current workflow.\n",
            "Archived evidence informs portfolio state maintained by the system.\n",
        )
        for text in probes:
            with self.subTest(text=text):
                self.assertTrue(scan_text(text))

    def test_active_semantic_hits_does_not_let_historical_adjective_mask_reactivation(self) -> None:
        hits = scan_text("Historical portfolio allocations are maintained now.\n")
        self.assertEqual(len(hits), 1, hits)

    def test_active_semantic_hits_scans_nonhistorical_summary_content(self) -> None:
        probes = (
            "<details><summary>Maintain portfolio allocations</summary>Current implementation.</details>\n",
            "<details><summary>Portfolio allocations are active</summary>Current implementation.</details>\n",
            "<details><summary>Implementation\nMaintain portfolio allocations.\n</details>\n",
            "<details><summary>Non-historical current route: Maintain portfolio allocations</summary></details>\n",
        )
        for text in probes:
            with self.subTest(text=text):
                self.assertTrue(scan_text(text))

    def test_active_semantic_hits_does_not_let_inert_tags_hold_history_open(self) -> None:
        probes = (
            "<details><summary>Historical archive</summary>\nMaintain portfolio allocations.\n",
            "<!-- <details><summary>Historical archive</summary> -->\nMaintain portfolio allocations.\n",
            "```html\n<details><summary>Historical archive</summary>\n```\nMaintain portfolio allocations.\n",
        )
        for text in probes:
            with self.subTest(text=text):
                self.assertTrue(scan_text(text))

    def test_active_semantic_hits_does_not_let_evidence_marker_mask_active_state(self) -> None:
        probes = (
            "Use company capital allocation research to maintain portfolio allocations.\n",
            "Maintain portfolio allocations using company capital allocation quality evidence.\n",
        )
        for text in probes:
            with self.subTest(text=text):
                self.assertTrue(scan_text(text))

    def test_active_semantic_hits_covers_plural_sector_and_trade_grade_terms(self) -> None:
        self.assertTrue(scan_text("Maintain sector allocations.\n"))
        self.assertTrue(scan_text("Generate trade grades.\n"))

    def test_active_semantic_hits_covers_natural_legacy_variants(self) -> None:
        probes = (
            "Execute paper trades.\n",
            "Maintain simulated account state.\n",
            "Maintain portfolio holdings.\n",
            "Maintain position sizes.\n",
            "Maintain capital deployments.\n",
            "Use paper brokerage.\n",
            "Manage the portfolio.\n",
            "Maintain holdings.\n",
            "Allocate capital.\n",
            "Publish a model portfolio.\n",
            "Maintain a paper account.\n",
            "Deploy capital.\n",
            "Maintain simulated orders.\n",
            "Publish model portfolios.\n",
            "Manage portfolios.\n",
            "The alert OS currently holds investment positions.\n",
            "AAPL allocation is 10%.\n",
            "The OS holds 50 shares of AAPL.\n",
            "portfo\nlio state is active.\n",
        )
        for text in probes:
            with self.subTest(text=text):
                self.assertTrue(scan_text(text))

    def test_active_semantic_hits_does_not_allow_unrelated_false_assignment_to_cloak_action(self) -> None:
        probes = (
            "Maintain portfolio allocations when dry_run=false.\n",
            "Maintain paper positions while execution_allowed=false.\n",
        )
        for text in probes:
            with self.subTest(text=text):
                self.assertTrue(scan_text(text))

    def test_active_semantic_hits_catches_negated_retirement_and_current_activation(self) -> None:
        probes = (
            "Portfolio management is not retired and remains active.\n",
            "Portfolio management was retired but is now active.\n",
            "Paper execution is not prohibited and is enabled.\n",
            "# Historical archive\nPaper execution is active.\n",
            "# Historical archive\nPaper execution is currently enabled.\n",
            "Portfolio management isn't retired.\n",
            "Paper execution is not false.\n",
            "Paper execution != false\n",
            "Portfolio management is not inactive.\n",
            "Paper execution is not disabled.\n",
            "Never fail to maintain portfolio allocations.\n",
            "Do not stop maintaining paper positions.\n",
            "# Historical archive\nWF67 route is active.\n",
            "# Historical archive\nPaper execution may proceed.\n",
            "# Historical archive\nPaper execution is permitted.\n",
            "# Historical archive\nPaper trading is authorized.\n",
            "# Historical archive\nWF67 accepts requests.\n",
            "# Historical archive\nPortfolio state persists.\n",
            "Retired paper trading is live.\n",
            "Former WF67 remains usable.\n",
            "WF67 was retired in 2026 but accepts requests today.\n",
            "Paper execution was blocked in 2024 but works today.\n",
            "Portfolio management was retired but has returned.\n",
            "Paper execution was retired but is now authorized.\n",
            "# Historical archive\nPaper execution can continue.\n",
            "# Historical archive\nPaper execution can be used.\n",
            "# Historical archive\nPaper execution is still available.\n",
            "# Historical archive\nWF67 handles requests.\n",
        )
        for text in probes:
            with self.subTest(text=text):
                self.assertTrue(scan_text(text))

    def test_active_semantic_hits_does_not_treat_without_delay_as_negation(self) -> None:
        self.assertTrue(scan_text("Without delay maintain portfolio allocations.\n"))
        self.assertEqual(scan_text("Operate without paper positions.\n"), [])
        self.assertEqual(
            scan_text("Calibrate recommendations without maintaining account or portfolio state.\n"),
            [],
        )

    def test_active_semantic_hits_catches_affirmative_mixed_clauses(self) -> None:
        probes = (
            "Never maintain portfolio allocations; maintain paper positions.\n",
            "Operate without paper positions, maintain portfolio allocations.\n",
            "No portfolio state, but maintain paper positions now.\n",
            "# Retired\nDo not maintain portfolio state; run paper execution now.\n",
            "| No portfolio state | Maintain paper positions |\n",
            "No portfolio state / maintain paper positions.\n",
            "No portfolio state, paper positions exist.\n",
        )
        for text in probes:
            with self.subTest(text=text):
                hits = scan_text(text)
                self.assertEqual(len(hits), 1, hits)

    def test_active_semantic_hits_allows_structured_boundary_and_history(self) -> None:
        hits = scan_text(
            "# Authority Boundary\n"
            "Do not maintain portfolio allocations or paper positions.\n"
            "Operate without paper positions.\n"
            "Historical paper execution records remain archive evidence only.\n"
        )
        self.assertEqual(hits, [])

    def test_active_semantic_hits_allows_affirmative_wording_only_in_structured_history(self) -> None:
        self.assertEqual(scan_text("# Historical archive\nMaintain portfolio allocations.\n"), [])
        self.assertEqual(scan_text("# Forbidden Actions\n- Maintain portfolio allocations.\n"), [])
        self.assertEqual(scan_text("# Prohibited Actions\n- Maintain portfolio allocations.\n"), [])
        self.assertEqual(scan_text("# Deny-only Routes\n- Maintain portfolio allocations.\n"), [])
        self.assertEqual(scan_text("# Out of Scope\n- Maintain portfolio allocations.\n"), [])
        self.assertTrue(scan_text("# Historical archive\nMaintain portfolio allocations now.\n"))

    def test_active_semantic_hits_uses_word_aware_structured_labels(self) -> None:
        probes = (
            "# Current non-historical behavior\nMaintain portfolio allocations.\n",
            "# Current unarchived route\nRun paper execution.\n",
            "# Active routes\n\"wf67\",\n",
        )
        for text in probes:
            with self.subTest(text=text):
                self.assertTrue(scan_text(text))

    def test_active_semantic_hits_does_not_let_inert_or_unbalanced_structure_mask_state(self) -> None:
        probes = (
            "<!-- # Historical archive -->\nMaintain portfolio allocations.\n",
            "<!-- <details><summary>Historical archive</summary> -->\nMaintain portfolio allocations.\n",
            "```md\n# Historical archive\n```\nMaintain portfolio allocations.\n",
            "forbidden_tools = [\n# Active\nMaintain portfolio allocations.\n",
            "<details-note><summary>Historical archive</summary></details-note>\nMaintain portfolio allocations.\n",
        )
        for text in probes:
            with self.subTest(text=text):
                self.assertTrue(scan_text(text))

    def test_active_semantic_hits_scopes_state_to_the_legacy_match(self) -> None:
        probes = (
            "# Historical archive\nPaper execution was active in 2024.\n",
            "# Historical archive\nPaper execution was enabled in 2024.\n",
            "# Authority Boundary\nDo not maintain portfolio allocations while alerts are active.\n",
            "Portfolio management is prohibited while alert routing is active.\n",
            "Paper execution is disabled.\n",
            "Paper execution is unavailable.\n",
            "Portfolio management is inactive.\n",
            "Paper execution cannot proceed.\n",
            "Paper execution is impossible.\n",
            "WF67 is unusable.\n",
            "Paper execution is never authorized.\n",
            "Paper execution cannot be authorized.\n",
            "Paper execution is unauthorized.\n",
            "WF67 must not accept requests.\n",
            "Paper execution is disallowed.\n",
            "Paper execution is permanently disabled.\n",
        )
        for text in probes:
            with self.subTest(text=text):
                self.assertEqual(scan_text(text), [])

    def test_active_semantic_hits_allows_historical_company_and_educational_evidence(self) -> None:
        probes = (
            "Historical paper trades remain archive evidence only.\n",
            "Historical paper trading records remain archive evidence only.\n",
            "Trade grades are historical evidence only.\n",
            "Historical paper positions inform the retirement audit.\n",
            "Archived portfolio snapshots support historical analysis.\n",
            "The company manages the portfolio of acquired brands.\n",
            "The company allocates capital to R&D.\n",
            "Synthetic positions can hedge risk.\n",
        )
        for text in probes:
            with self.subTest(text=text):
                self.assertEqual(scan_text(text), [])

    def test_semantic_acceptance_matrix_hits_affirmative_operations(self) -> None:
        probes = (
            "Use legacy data to maintain a carefully reviewed risk conscious owner approved set of portfolio allocations.\n",
            "Do not delete old records because we maintain portfolio allocations.\n",
            "Paper execution is no longer disabled.\n",
            "Portfolio management has not been retired.\n",
            "We not only maintain portfolio allocations but also publish alerts.\n",
            "Maintain the holdings.\n",
            "Maintain asset allocations.\n",
            "Maintain target weights.\n",
            "Update our allocations.\n",
            "Rebalance holdings.\n",
            "Rebalance sector weights.\n",
            "Paper execution when feature flag: false.\n",
            "Portfolio state when audit mode = false.\n",
            "Do not maintain portfolio allocations (run paper execution instead).\n",
            "No portfolio state, paper positions are active.\n",
            "Historical paper records support alerts; current paper positions are maintained.\n",
            "The company allocated capital to R&D; Veritas allocates capital.\n",
            "What is position sizing? The workflow maintains position sizes.\n",
            "paperPositions are enabled.\n",
            "paper\u200bPositions are enabled.\n",
            "paper\npositions are enabled.\n",
        )
        for text in probes:
            with self.subTest(text=text):
                self.assertTrue(scan_text(text))

    def test_semantic_acceptance_matrix_allows_explicitly_inactive_state(self) -> None:
        probes = (
            "Paper execution remains unavailable.\n",
            "Paper execution has stopped.\n",
            "Portfolio management is paused.\n",
            "Don't maintain portfolio allocations.\n",
            "Don\u2019t maintain portfolio allocations.\n",
            "We can't run paper execution.\n",
            "We won't maintain portfolio allocations.\n",
            "We aren't maintaining portfolio allocations.\n",
            "We are forbidden to maintain portfolio allocations.\n",
            "Forbidden: Maintain portfolio allocations.\n",
            "Do not: Maintain portfolio allocations.\n",
            "Forbidden:\n- Maintain portfolio allocations.\n- Run paper execution.\n",
            "Do not maintain:\n- portfolio allocations\n- paper positions\n",
            "Portfolio management is retired when dry_run != false.\n",
            "Do not maintain portfolio allocations when checks are not false.\n",
        )
        for text in probes:
            with self.subTest(text=text):
                self.assertEqual(scan_text(text), [])

    def test_semantic_acceptance_matrix_scopes_false_fields(self) -> None:
        allowed = (
            "paper_execution: false\n",
            "paper_execution:\n  false\n",
            "paper_execution:\n  enabled: false\n",
            "paper_execution: off\n",
            "paper_execution: disabled\n",
            "paper_execution: null\n",
            "paper_execution_enabled=false\n",
        )
        for text in allowed:
            with self.subTest(text=text):
                self.assertEqual(scan_text(text), [])
        self.assertTrue(scan_text("Paper execution when feature flag: false.\n"))
        self.assertTrue(scan_text("Portfolio state when audit mode = false.\n"))
        self.assertTrue(scan_text("Portfolio state when audit mode is not false.\n"))
        self.assertTrue(scan_text("paper_execution_enabled = False or True\n"))
        self.assertTrue(scan_text("paper_execution = False or True\n"))
        self.assertTrue(scan_text("paper_execution_enabled = False if dry_run else True\n"))
        self.assertTrue(scan_text('{"paper_execution": False or True}\n'))
        self.assertTrue(scan_text("portfolio_state:\n false or true\n"))

    def test_semantic_acceptance_matrix_handles_markdown_structure_fail_closed(self) -> None:
        active = (
            "# Bounded Auto-Archive Policy\nMaintain portfolio allocations.\n",
            "```python\n# Historical archive\n```\nMaintain portfolio allocations.\n",
            "<!--\n# Historical archive\n-->\nMaintain portfolio allocations.\n",
            "```\nMaintain portfolio allocations.\n```\n",
            "<!-- Maintain portfolio allocations. -->\n",
            "<details><summary>Historical archive\nMaintain portfolio allocations.</details>\n",
            "<details><summary>Historical archive</summary><summary>Current operations</summary>Maintain portfolio allocations.</details>\n",
            "<details><summary>Historical archive</summary>\n## Stop lines\nDo not run old routes.\n</details>\nMaintain portfolio allocations.\n",
            "status: retired\nHistorical evidence only\n# Current reactivation\nMaintain portfolio allocations.\n",
        )
        for text in active:
            with self.subTest(text=text):
                self.assertTrue(scan_text(text))
        self.assertEqual(
            scan_text("| Lifecycle | Behavior |\n| Retired | Maintain portfolio allocations |\n"),
            [],
        )

    def test_semantic_acceptance_matrix_uses_python_literal_owners(self) -> None:
        active = (
            "# Historical archive\nACTIVE_ROUTES = ('wf67',)\n",
            "ACTIVE_ROUTES = ('wf67',)\n",
            "NOT_RETIRED_ROUTES = ('wf67',)\n",
            "ACTIVE_RETIRED_ROUTES = ('wf67',)\n",
            "config = {'active_routes': ['wf67']}\n",
            "BLOCKED = {'portfolio_state': 'active'}\n",
            "BLOCKED = {'portfolio_state': 'authorized'}\n",
            "BLOCKED = {'portfolio_state': 'live'}\n",
            "RETIRED_ROUTES = ('paper execution may proceed',)\n",
            "RETIRED_ROUTES = ('wf67',); ACTIVE_ROUTES = ('wf67',)\n",
            "BLOCKED = ('wf67',); WF67_IS_ACTIVE = True\n",
            "config = {'retired_routes': ['wf67'], 'active_routes': ['wf67']}\n",
            "BLOCKED = {'portfolio_state': {'mode': 'live'}}\n",
            "RETIRED_ROUTES = ({'route': 'wf67', 'enabled': True},)\n",
        )
        for text in active:
            with self.subTest(text=text):
                self.assertTrue(scan_text(text, ".py"))
        self.assertEqual(scan_text("RETIRED_ROUTES = ('wf67',)\n", ".py"), [])
        self.assertEqual(scan_text("forbidden_tools = ['wf67']\n", ".py"), [])
        self.assertEqual(scan_text("config = {'retired_routes': ['wf67']}\n", ".py"), [])
        self.assertEqual(
            scan_text("FORBIDDEN_TRUE_FLAGS = {'paper_trade_submit_cancel_allowed'}\n", ".py"),
            [],
        )

    def test_semantic_acceptance_matrix_catches_negated_deactivation_and_current_continuity(self) -> None:
        probes = (
            "# Historical archive\nPaper execution is never disabled.\n",
            "# Historical archive\nDo not disable paper execution.\n",
            "# Historical archive\nPaper execution cannot be disabled.\n",
            "# Historical archive\nPaper execution remains callable.\n",
            "# Historical archive\nPaper positions are maintained by the current workflow.\n",
            "We maintained portfolio allocations in 2024 and continue today.\n",
            "paper_execution: {enabled: true}\n",
        )
        for text in probes:
            with self.subTest(text=text):
                self.assertTrue(scan_text(text))
        allowed = (
            "Paper execution cannot run.\n",
            "Paper execution will not run.\n",
            "paper_execution = None\n",
            "paper_execution: {enabled: false}\n",
        )
        for text in allowed:
            with self.subTest(text=text):
                self.assertEqual(scan_text(text), [])

    def test_semantic_acceptance_matrix_allows_past_audit_and_research_usage(self) -> None:
        probes = (
            "Paper execution ran in 2024.\n",
            "We maintained portfolio allocations in 2024.\n",
            "Paper execution used to run.\n",
            "Previously, we maintained portfolio allocations.\n",
            "Historical portfolio snapshots are archived while the validator is running.\n",
            "Archived portfolio snapshots enable archival search.\n",
            "Archived portfolio snapshots maintain provenance.\n",
            "Maintain historical portfolio snapshots as archive evidence only.\n",
            "The company allocated capital to a new factory.\n",
            "Capital allocation quality is a fundamental input.\n",
            "Company capital allocation quality informs recommendations.\n",
            "The index updates weights quarterly.\n",
            "Update weights in the machine-learning model.\n",
            "Maintain positions of chart labels.\n",
            "The research portfolio manages allocations of lab time.\n",
            "Model portfolio theory is described in a textbook.\n",
            "What is portfolio management?\n",
            "This tutorial compares position sizing with risk budgeting.\n",
            "No portfolio / position / paper state is maintained.\n",
            "It does not own or maintain sleeves, holdings, simulated positions.\n",
            "This review is review-only: no\ncanon/portfolio mutation.\n",
            "Former WF67 route was retired.\n",
        )
        for text in probes:
            with self.subTest(text=text):
                self.assertEqual(scan_text(text), [])

    def test_semantic_acceptance_matrix_normalizes_obfuscated_separators(self) -> None:
        probes = (
            "portfolio / state is active.\n",
            "portfolio--state is active.\n",
            "portfolio . state is active.\n",
        )
        for text in probes:
            with self.subTest(text=text):
                self.assertTrue(scan_text(text))

    def test_retired_workflow_acceptance_matrix_catches_active_config_forms(self) -> None:
        active = (
            "# Active routes\n\"wf68\",\n",
            "active_routes:\n- wf68\n",
            "wf68: true\n",
            "\"wf78\": true\n",
            "enabled_workflows:\n- wf78\n",
            "supported_workflows:\n- wf68\n",
            "WF68 is current.\n",
            "WF78 remains callable.\n",
            "Supported workflow: WF78\n",
            "# WF68 Tier Router\n",
            "# Historical archive\nWF78 accepts inputs.\n",
        )
        for text in active:
            with self.subTest(text=text):
                self.assertTrue(scan_skill_text(text))
        allowed = (
            "wf68: false\n",
            "# Retired\nWF68 is blocked.\n",
            "# Historical archive\nWF68 was running in 2024.\n",
        )
        for text in allowed:
            with self.subTest(text=text):
                self.assertEqual(scan_skill_text(text), [])

    def test_wf68_wf78_routes_and_skill_tombstone_are_fail_closed(self) -> None:
        self.assertTrue({"WF68", "WF78"}.issubset(pivot.RETIRED_WORKFLOWS))
        self.assertTrue({"wf68", "wf78"}.issubset(pivot.RETIRED_OVERRIDE_KEYS))
        tombstone = pivot.WF78_TOMBSTONE_SKILL.read_text(encoding="utf-8").lower()
        for marker in pivot.WF78_TOMBSTONE_MARKERS:
            self.assertIn(marker, tombstone)
        self.assertEqual(pivot.active_retired_workflow_skill_hits(pivot.WF78_TOMBSTONE_SKILL), [])
        self.assertEqual(scan_skill_text("# Boundary\nDo not run WF68 or resume WF78.\n"), [])
        self.assertTrue(scan_skill_text("# Retired\nRun WF78 routing now.\n"))
        self.assertTrue(scan_skill_text("# Skill\nWF68 is active.\n"))

    def test_direct_callable_legacy_executables_are_deny_only_tombstones(self) -> None:
        expected = {
            "alpaca_paper_execution_guard_validator.py",
            "alpaca_paper_readiness_validator.py",
            "alpaca_paper_trade_executor.py",
            "portfolio_mutation_apply_helper.py",
            "wf67_autonomous_paper_manager.py",
            "wf67_order_card_request_generator.py",
            "wf86_assisted_order_card_builder.py",
            "wf86_autotrader_readiness_packet.py",
        }
        self.assertEqual({path.name for path in pivot.DIRECT_CALLABLE_LEGACY_TOMBSTONES}, expected)
        for path in pivot.DIRECT_CALLABLE_LEGACY_TOMBSTONES:
            with self.subTest(path=path):
                self.assertEqual(pivot.direct_callable_tombstone_findings(path), [])

    def test_direct_callable_tombstone_guard_catches_reachable_capability(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_name:
            path = Path(tmp_name) / "legacy.py"
            path.write_text(
                '"""Retired tombstone."""\n'
                "import requests\n"
                "def main():\n"
                "    print(\"--apply https://example.invalid\")\n"
                "    return 0\n",
                encoding="utf-8",
            )
            findings = pivot.direct_callable_tombstone_findings(path)
        joined = "\n".join(findings)
        self.assertIn("forbidden_text:--apply", joined)
        self.assertIn("forbidden_import:requests", joined)
        self.assertIn("return_not_statically_nonzero", joined)

    def test_payload_text_normalizes_command_argv(self) -> None:
        contract = {"payload": {"kind": "command", "argv": ["python", "scripts/SAFE.py"]}}
        self.assertEqual(pivot.payload_text(contract), "python scripts/safe.py")

    def test_blocked_token_set_covers_retired_execution_routes(self) -> None:
        joined = " ".join(pivot.BLOCKED_ACTIVE_PAYLOAD_TOKENS)
        self.assertIn("position_sizing", joined)
        self.assertIn("paper_reconciliation", joined)
        self.assertIn("wf87_", joined)

    def test_artifact_index_allowlist_excludes_retired_finance_sources(self) -> None:
        source = pivot.ROOT / "scripts" / "artifact_index.py"
        values = pivot.literal_sequence_assignment(source, "TRUTH_SPINE_FILES")
        values += pivot.literal_sequence_assignment(source, "FILE_STATE_ONLY_FILES")
        self.assertTrue(values)
        joined = "\n".join(values).lower()
        for token in pivot.RETIRED_ARTIFACT_INDEX_TOKENS:
            self.assertNotIn(token, joined)

    def test_sql_consumer_classifier_covers_retired_workflows_and_state(self) -> None:
        for value in [
            "scripts/wf78_auto_tier_router.py",
            "scripts/wf67_paper_position_refresh.py",
            "scripts/portfolio_mutation_proposal_generator.py",
            "scripts/trade_grade_decision_cards.py",
            "scripts/tuesday_position_sizing_readiness.py",
            "scripts/auto_apply_entry_band_maintenance.py",
            "scripts/test_ticker_intelligence_card_sizing_policy.py",
            "scripts/wf72_entry_stop_sql_activate.py",
        ]:
            self.assertTrue(pivot.is_legacy_sql_consumer(value), value)
        self.assertFalse(pivot.is_legacy_sql_consumer("scripts/alert_level_freshness_controller.py"))

    def test_live_finance_sql_canon_is_alerts_only(self) -> None:
        detail, errors = pivot.validate_finance_sql_state()
        self.assertEqual(errors, [], detail)
        self.assertEqual(detail["guard_status"], "ok")
        self.assertEqual(detail["guard_warning_count"], 0)
        self.assertEqual(detail["tier_routing_row_count"], 0)
        self.assertEqual(detail["active_legacy_consumer_count"], 0)


if __name__ == "__main__":
    unittest.main()
