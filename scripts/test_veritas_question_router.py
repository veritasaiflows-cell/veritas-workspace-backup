from __future__ import annotations

import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest import mock

import veritas_question_router as router


class VeritasQuestionRouterTests(unittest.TestCase):
    BASELINE_18 = {
        "AMD", "AMZN", "BRK.B", "CAT", "CVX", "ETN", "GOOG", "GS", "JPM",
        "LLY", "LMT", "LNG", "MSFT", "NVDA", "PLTR", "RTX", "VRT", "XOM",
    }
    COVERAGE_CONTROL = {"CME", "ITA", "LIN", "META", "PH"}

    @classmethod
    def setUpClass(cls) -> None:
        cls.temp_dir = tempfile.TemporaryDirectory()
        root = Path(cls.temp_dir.name)
        cls.fixture_paths = {
            "sql_guard": root / "sql.json",
            "quote_proof": root / "quote.json",
            "controller": root / "controller.json",
            "digest": root / "digest.json",
            "pivot": root / "pivot.json",
            "analyst_consensus": root / "analyst.json",
        }
        cls._write_json(cls.fixture_paths["sql_guard"], {"status": "ok"})
        cls._write_json(
            cls.fixture_paths["quote_proof"],
            {
                "status": "ok",
                "symbols_observed": sorted((cls.BASELINE_18 - {"BRK.B"}) | {"BRK-B"}),
            },
        )
        cls._write_json(
            cls.fixture_paths["controller"],
            {
                "status": "ok",
                "rows": [
                    {
                        "ticker": ticker,
                        "latest_price": 1.0,
                        "validation_status": "ok",
                        "freshness_status": "current_test_fixture",
                        "reasons": [],
                    }
                    for ticker in sorted(cls.BASELINE_18)
                ],
            },
        )
        cls._write_json(cls.fixture_paths["digest"], {"status": "ok"})
        cls._write_json(cls.fixture_paths["pivot"], {"status": "ok"})
        cls._write_json(
            cls.fixture_paths["analyst_consensus"],
            {"status": "sourced_current", "tickers": {ticker: {} for ticker in sorted(cls.BASELINE_18)}},
        )
        cls.source_patch = mock.patch.dict(router.SOURCE_PATHS, cls.fixture_paths, clear=True)
        cls.source_patch.start()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.source_patch.stop()
        cls.temp_dir.cleanup()

    @staticmethod
    def _write_json(path: Path, payload: dict[str, object]) -> None:
        path.write_text(json.dumps(payload), encoding="utf-8")

    def test_ticker_alert_route_uses_only_active_proofs(self) -> None:
        scope = router.guarded_alert_scope(router.FinanceSqlCanonAccess())
        route = router.build_route("What is the entry band for VRT?")
        self.assertEqual(route["question_class"], "ticker_intelligence")
        self.assertEqual(route["ticker"], "VRT")
        self.assertEqual(route["ticker_scope"]["eligible_tier_a_b_count"], len(scope.tickers))
        self.assertEqual(route["ticker_scope"]["fingerprint"], scope.fingerprint)
        self.assertFalse(route["ticker_scope"]["fallback_used"])
        paths = [row["path"] for row in route["primary_route"]]
        self.assertTrue(any(path.endswith("controller.json") for path in paths))
        text = json.dumps(route).lower()
        for token in ("03. portfolio", "trade-grade", "deployment-readiness", "finance_intelligence_state.py"):
            self.assertNotIn(token, text)

    def test_guarded_scope_is_exact_current_tier_a_plus_b_set(self) -> None:
        client = router.FinanceSqlCanonAccess()
        scope = router.guarded_alert_scope(client)
        expected = {
            ticker for ticker, row in client.universe_memberships().items()
            if row.active and row.tier in {"A", "B"}
        }
        self.assertEqual(set(scope.tickers), expected)
        self.assertFalse({row.tier for row in scope.memberships.values()} - {"A", "B"})

    def test_provider_alias_resolves_only_through_sql_owner(self) -> None:
        route = router.build_route("What is the entry band for BRK-B?")
        self.assertEqual(route["ticker"], "BRK.B")
        self.assertNotIn("guarded_sql_identity_unresolved", " ".join(route["missing_or_residue"]))

    def test_provider_alias_uses_single_scope_snapshot_not_second_sql_read(self) -> None:
        scope = router.guarded_alert_scope(router.FinanceSqlCanonAccess())

        class BrokenResolver:
            def dynamic_entitlement_scope(self) -> object:
                return scope

            def resolve_tickers(self, tickers: list[str]) -> dict[str, str]:
                raise AssertionError("router must not perform a second SQL identity lookup")

        with mock.patch.object(router, "FinanceSqlCanonAccess", return_value=BrokenResolver()):
            route = router.build_route("What is the entry band for BRK-B?")
        self.assertEqual(route["ticker"], "BRK.B")
        self.assertNotIn("guarded_sql_identity_unresolved", " ".join(route["missing_or_residue"]))

    def test_provider_alias_mismatched_canonical_identity_fails_closed(self) -> None:
        scope = router.guarded_alert_scope(router.FinanceSqlCanonAccess())
        wrong_aliases = dict(scope.aliases)
        wrong_aliases["BRK-B"] = "MISSING"

        class WrongResolver:
            def dynamic_entitlement_scope(self) -> object:
                return replace(scope, aliases=wrong_aliases)

        with mock.patch.object(router, "FinanceSqlCanonAccess", return_value=WrongResolver()):
            route = router.build_route("What is the entry band for BRK-B?")
        self.assertIsNone(route["ticker"])
        self.assertFalse(router.final_answer_allowed(route))
        self.assertTrue(
            any(
                item.startswith("guarded_sql_identity_unresolved:BRK-B:ValueError")
                for item in route["missing_or_residue"]
            )
        )
        self.assertNotIn("enrolled_but_not_observed:AMD", route["missing_or_residue"])

    def test_unknown_ticker_fails_closed(self) -> None:
        route = router.build_route("What is the alert state for ZQZQ?")
        self.assertFalse(router.final_answer_allowed(route))
        self.assertIsNone(route["ticker"])
        self.assertTrue(any(item.startswith("guarded_sql_identity_unresolved:ZQZQ") for item in route["missing_or_residue"]))

    def test_tier_c_identity_remains_outside_alert_scope(self) -> None:
        route = router.build_route("What is the alert state for AAPL?")
        self.assertEqual(route["ticker"], "AAPL")
        self.assertFalse(router.final_answer_allowed(route))
        self.assertIn("ticker_not_in_active_alert_scope:AAPL", route["missing_or_residue"])

    def test_sql_failure_emits_visible_error_and_no_ticker_scoped_route(self) -> None:
        class BrokenSql:
            def dynamic_entitlement_scope(self) -> object:
                raise RuntimeError("fixture database unavailable")

        with mock.patch.object(router, "FinanceSqlCanonAccess", return_value=BrokenSql()):
            route = router.build_route("What is the alert state for VRT?")
        self.assertIsNone(route["ticker"])
        self.assertFalse(route["ticker_scope"]["scope_available"])
        self.assertIsNone(route["ticker_scope"]["eligible_tier_a_b_count"])
        self.assertFalse(router.final_answer_allowed(route))
        self.assertIn("guarded_sql_scope_unavailable:RuntimeError", route["missing_or_residue"])
        self.assertNotIn("fixture database unavailable", json.dumps(route))

    def test_enrolled_but_unobserved_control_names_stay_blocked(self) -> None:
        for ticker in sorted(self.COVERAGE_CONTROL):
            with self.subTest(ticker=ticker):
                route = router.build_route(f"What is the alert state for {ticker}?")
                self.assertEqual(route["ticker"], ticker)
                self.assertFalse(router.final_answer_allowed(route))
                self.assertTrue(
                    any(item.startswith(f"enrolled_but_not_observed:{ticker}:") for item in route["missing_or_residue"]),
                    route["missing_or_residue"],
                )

    def test_source_has_no_hard_coded_or_cached_scope_fallback(self) -> None:
        source = Path(router.__file__).read_text(encoding="utf-8")
        self.assertNotIn("TRACKED_TICKERS", source)
        self.assertNotIn("ALERT_SCOPE_TIERS", source)
        self.assertNotIn("EXPECTED_32", source)
        self.assertNotIn("tier-entitlement-surface-inventory", source)
        self.assertNotIn("coverage-watchlist-replacement", source)

    def test_action_request_fails_closed(self) -> None:
        route = router.build_route("Can we paper buy VRT tomorrow?")
        self.assertEqual(route["question_class"], "authority_guardrail")
        self.assertFalse(router.final_answer_allowed(route))
        self.assertIn("request_outside_alerts_and_recommendations_os", route["missing_or_residue"])


if __name__ == "__main__":
    unittest.main()
