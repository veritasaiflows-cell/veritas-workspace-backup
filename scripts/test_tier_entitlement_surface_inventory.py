#!/usr/bin/env python
"""Hermetic tests for the Tier Entitlement Phase 1 surface inventory.

Every test builds its own fixture text or synthetic rows. Nothing here reads live
guarded SQL, live workspace scope constants, or the generated inventory artifact,
so a workspace change can never turn a detector regression into a green run.
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import tier_entitlement_surface_inventory as inv  # noqa: E402


# Fixture universe: deliberately contains one-character names so the ambiguity
# floor is exercised against real guarded-SQL shapes rather than a tidy sample.
UNIVERSE = {
    "NVDA": "Tier A",
    "MSFT": "Tier A",
    "META": "Tier A",
    "GOOG": "Tier A",
    "AMZN": "Tier B",
    "CAT": "Tier B",
    "ETN": "Tier B",
    "A": "Tier C",
    "C": "Tier C",
    "T": "Tier C",
    "BRK.B": "Tier C",
    "ZZZC": "Tier C",
}


def lines_of(text: str) -> list[str]:
    return text.splitlines()


class ScopeLiteralExtractionTests(unittest.TestCase):
    def test_module_string_list_reads_list_and_tuple(self) -> None:
        text = 'DEFAULT_TIER_A = ["ETN", "NVDA"]\nALERT = ("MSFT", "CAT")\n'
        self.assertEqual(inv.module_string_list(text, "DEFAULT_TIER_A"), ["ETN", "NVDA"])
        self.assertEqual(inv.module_string_list(text, "ALERT"), ["MSFT", "CAT"])

    def test_module_string_list_refuses_non_literal_members(self) -> None:
        text = "SCOPE = [BUILD_ME, 'NVDA']\n"
        self.assertIsNone(inv.module_string_list(text, "SCOPE"))

    def test_module_string_list_ignores_nested_and_missing_names(self) -> None:
        text = "def f():\n    SCOPE = ['NVDA', 'MSFT']\n    return SCOPE\n"
        self.assertIsNone(inv.module_string_list(text, "SCOPE"))
        self.assertIsNone(inv.module_string_list(text, "ABSENT"))

    def test_argv_scope_collects_only_flagged_values(self) -> None:
        argv = ["script.py", "--tickers", "NVDA", "MSFT", "--write", "--validate"]
        self.assertEqual(inv.argv_scope(argv), ["NVDA", "MSFT"])

    def test_argv_scope_returns_nothing_without_a_scope_flag(self) -> None:
        self.assertEqual(inv.argv_scope(["script.py", "--write", "morning"]), [])


class TickerResolutionTests(unittest.TestCase):
    def test_alias_normalisation_is_applied(self) -> None:
        resolved, aliases = inv.resolve_universe_tickers(["BRK-B"], UNIVERSE)
        self.assertEqual(resolved, ["BRK.B"])
        self.assertEqual(aliases, ["BRK-B->BRK.B"])

    def test_names_outside_the_guarded_universe_are_dropped(self) -> None:
        resolved, _ = inv.resolve_universe_tickers(["NVDA", "NOTREAL"], UNIVERSE)
        self.assertEqual(resolved, ["NVDA"])

    def test_lowercase_literals_are_not_tickers(self) -> None:
        resolved, _ = inv.resolve_universe_tickers(["nvda"], UNIVERSE)
        self.assertEqual(resolved, [])

    def test_ambiguity_classification_uses_core_length(self) -> None:
        self.assertTrue(inv.is_ambiguous_ticker("A"))
        self.assertTrue(inv.is_ambiguous_ticker("T"))
        self.assertFalse(inv.is_ambiguous_ticker("NVDA"))
        self.assertFalse(inv.is_ambiguous_ticker("BRK.B"))


class LiteralScopeDetectorTests(unittest.TestCase):
    def test_true_positive_literal_scope(self) -> None:
        text = 'ALERT_TICKERS = (\n    "NVDA",\n    "MSFT",\n    "CAT",\n    "ETN",\n)\n'
        hit = inv.detect_literal_ticker_scope(lines_of(text), UNIVERSE)
        self.assertIsNotNone(hit)
        assert hit is not None
        self.assertEqual(hit["tickers"], ["CAT", "ETN", "MSFT", "NVDA"])
        self.assertEqual(hit["tier_counts"], {"Tier A": 2, "Tier B": 2})
        self.assertTrue(hit["evidence"])

    def test_tier_control_labels_do_not_create_a_scope(self) -> None:
        # "A", "B", and "C" are tier labels here, but "A" and "C" are also real
        # guarded-SQL tickers. The ambiguity floor must reject this file.
        text = 'TIERS = ("A", "B", "C")\nORDER = ["A", "C", "T"]\n'
        self.assertIsNone(inv.detect_literal_ticker_scope(lines_of(text), UNIVERSE))

    def test_two_unambiguous_names_stay_below_the_floor(self) -> None:
        text = 'PAIR = ("NVDA", "MSFT", "A")\n'
        self.assertIsNone(inv.detect_literal_ticker_scope(lines_of(text), UNIVERSE))

    def test_stale_day_map_is_not_a_scope(self) -> None:
        text = 'STALE_DAYS = {"daily": 1, "weekly": 7}\nWINDOWS = ["morning", "midday"]\n'
        self.assertIsNone(inv.detect_literal_ticker_scope(lines_of(text), UNIVERSE))

    def test_ambiguous_names_ride_along_once_the_floor_is_met(self) -> None:
        text = 'SCOPE = ["NVDA", "MSFT", "CAT", "A", "T"]\n'
        hit = inv.detect_literal_ticker_scope(lines_of(text), UNIVERSE)
        assert hit is not None
        self.assertEqual(hit["ambiguous_tickers"], ["A", "T"])
        self.assertEqual(hit["unambiguous_count"], 3)
        for entry in hit["evidence"]:
            self.assertNotIn(entry["detail"], {"A", "T"})


class CronArgvDetectorTests(unittest.TestCase):
    def test_cron_argv_scope_is_detected(self) -> None:
        payload = {"payload": {"argv": ["refresh.py", "--tickers", "NVDA", "MSFT", "CAT"]}}
        text = json.dumps(payload, indent=2)
        hit = inv.detect_cron_argv_scope(payload, lines_of(text), UNIVERSE)
        assert hit is not None
        self.assertEqual(hit["tickers"], ["CAT", "MSFT", "NVDA"])
        self.assertEqual(hit["evidence"][0]["kind"], "cron_argv_scope")

    def test_cron_without_a_ticker_argv_is_not_a_scope(self) -> None:
        payload = {"payload": {"argv": ["chain.py", "morning", "--write"]}}
        text = json.dumps(payload, indent=2)
        self.assertIsNone(inv.detect_cron_argv_scope(payload, lines_of(text), UNIVERSE))


class PatternClassTests(unittest.TestCase):
    def test_local_tier_state_and_registry_scope_are_distinguished(self) -> None:
        local_text = 'payload["tier_sets"] = {"A": tier_a}\nDEFAULT_TIER_B = ["CAT"]\n'
        local = inv.detect_pattern_class(lines_of(local_text), inv.LOCAL_TIER_PATTERNS, "local_tier_state")
        self.assertTrue(local)

        registry_text = 'rows = conn.execute("SELECT ticker FROM current_active_universe")\n'
        registry = inv.detect_pattern_class(
            lines_of(registry_text), inv.REGISTRY_SCOPE_PATTERNS, "registry_derived_scope"
        )
        self.assertTrue(registry)

    def test_registry_read_is_not_local_tier_state(self) -> None:
        registry_text = 'rows = conn.execute("SELECT ticker, tier FROM universe_membership")\n'
        self.assertEqual(
            inv.detect_pattern_class(lines_of(registry_text), inv.LOCAL_TIER_PATTERNS, "local_tier_state"),
            [],
        )


class TruthClassRoleTests(unittest.TestCase):
    def test_one_surface_can_consume_and_produce_different_truth_classes(self) -> None:
        text = (
            "rows = conn.execute('SELECT ticker, band_low FROM reference_levels')\n"
            "conn.execute('INSERT INTO alert_state (ticker, level) VALUES (?, ?)', row)\n"
        )
        roles = inv.detect_truth_class_roles(lines_of(text))
        self.assertEqual(roles["reference_band"]["role"], "consumer")
        self.assertEqual(roles["material_alert_state"]["role"], "producer")

    def test_read_and_write_of_the_same_class_yields_both(self) -> None:
        text = (
            "conn.execute('SELECT level FROM alert_state')\n"
            "conn.execute('UPDATE alert_state SET level = ?', (level,))\n"
        )
        roles = inv.detect_truth_class_roles(lines_of(text))
        self.assertEqual(roles["material_alert_state"]["role"], "both")
        self.assertEqual(roles["material_alert_state"]["roles"], ["consumer", "producer"])

    def test_prose_surfaces_are_demoted_to_policy_reference(self) -> None:
        text = "The generated `tier_sets` block is not authoritative; guarded SQL owns effective tier.\n"
        roles = inv.detect_truth_class_roles(lines_of(text), executable=False)
        for entry in roles.values():
            self.assertEqual(entry["role"], "policy_reference")
            self.assertEqual(entry["roles"], ["policy_reference"])


class RetiredReferenceTests(unittest.TestCase):
    RETIRED = {"wf78_promotion_engine.py": "retirement_policy_exact_path"}

    def test_guard_reference_is_lifecycle_proof_not_reactivation(self) -> None:
        text = 'FORBIDDEN = ("wf78_promotion_engine.py",)  # retired: deny this route\n'
        result = inv.detect_retired_references(lines_of(text), self.RETIRED, "scripts/guard.py")
        self.assertTrue(result["guard_evidence"])
        self.assertEqual(result["reactivation_evidence"], [])

    def test_subprocess_dispatch_is_a_reactivation_edge(self) -> None:
        text = 'run([sys.executable, "scripts/wf78_promotion_engine.py", "--write"])\n'
        result = inv.detect_retired_references(lines_of(text), self.RETIRED, "scripts/runner.py")
        self.assertTrue(result["reactivation_evidence"])
        self.assertEqual(result["reactivation_evidence"][0]["detail"], "wf78_promotion_engine.py")

    def test_import_is_a_reactivation_edge(self) -> None:
        text = "import wf78_promotion_engine\n"
        result = inv.detect_retired_references(lines_of(text), self.RETIRED, "scripts/runner.py")
        self.assertTrue(result["reactivation_evidence"])

    def test_plain_prose_mention_is_neither(self) -> None:
        text = "The old wf78_promotion_engine.py produced the 2026-05 rankings.\n"
        result = inv.detect_retired_references(lines_of(text), self.RETIRED, "notes/history.md")
        self.assertTrue(result["plain_reference_evidence"])
        self.assertEqual(result["reactivation_evidence"], [])
        self.assertEqual(result["guard_evidence"], [])

    def test_a_retired_file_never_flags_itself(self) -> None:
        text = 'NAME = "wf78_promotion_engine.py"\nimport wf78_promotion_engine\n'
        result = inv.detect_retired_references(
            lines_of(text), self.RETIRED, "scripts/wf78_promotion_engine.py"
        )
        self.assertEqual(result["referenced_names"], [])
        self.assertEqual(result["reactivation_evidence"], [])


class ExclusionTests(unittest.TestCase):
    def test_vendored_dependencies_are_excluded(self) -> None:
        self.assertEqual(
            inv.excluded_reason("skills/sec/.venv/Lib/site-packages/pandas/core/reshape/merge.py"),
            "vendored_or_cache_path",
        )
        self.assertEqual(inv.excluded_reason("scripts/__pycache__/x.cpython-312.pyc"), "vendored_or_cache_path")

    def test_declared_roots_report_their_stated_role(self) -> None:
        for prefix in inv.EXCLUDED_ROOTS:
            self.assertEqual(inv.excluded_reason(f"{prefix}/nested/file.py"), inv.EXCLUDED_ROOTS[prefix])

    def test_ordinary_scripts_are_not_excluded(self) -> None:
        self.assertIsNone(inv.excluded_reason("scripts/alert_level_freshness_controller.py"))


class EdgeTests(unittest.TestCase):
    def _rows(self) -> list[dict[str, Any]]:  # type: ignore[name-defined]
        return [
            {"path": "scripts/caller.py", "operational_status": "active"},
            {"path": "scripts/retired_target.py", "operational_status": "retired"},
        ]

    def test_guard_only_reference_creates_no_operational_edge(self) -> None:
        rows = self._rows()
        texts = {
            "scripts/caller.py": ['DENY = ("retired_target.py",)  # retired route, do not run'],
            "scripts/retired_target.py": ["pass"],
        }
        edges = inv.build_edges(rows, texts, {})
        self.assertTrue(edges)
        self.assertTrue(all(edge["kind"] == "guard_reference" for edge in edges))
        self.assertFalse(any(edge["operational"] for edge in edges))

    def test_subprocess_call_creates_an_operational_edge(self) -> None:
        rows = self._rows()
        texts = {
            "scripts/caller.py": ['run([sys.executable, "scripts/retired_target.py"])'],
            "scripts/retired_target.py": ["pass"],
        }
        edges = inv.build_edges(rows, texts, {})
        operational = [edge for edge in edges if edge["operational"]]
        self.assertEqual(len(operational), 1)
        self.assertEqual(operational[0]["kind"], "subprocess_command")

    def test_every_edge_carries_evidence(self) -> None:
        rows = self._rows()
        texts = {
            "scripts/caller.py": ['import retired_target'],
            "scripts/retired_target.py": ["pass"],
        }
        for edge in inv.build_edges(rows, texts, {}):
            self.assertTrue(edge["evidence"])


class ScopeDivergenceTests(unittest.TestCase):
    def test_two_scopes_report_shared_and_unique_names(self) -> None:
        scopes = {
            "chain_alert_scope": {"path": "scripts/chain.py", "resolved": ["NVDA", "MSFT", "CAT"]},
            "analyst_default_scope": {
                "path": "scripts/analyst.py",
                "resolved": ["NVDA", "MSFT", "ETN"],
                "local_tier_labels": {},
            },
        }
        result = inv.scope_divergence(scopes, UNIVERSE)
        self.assertEqual(result["shared"], ["MSFT", "NVDA"])
        self.assertEqual(result["alert_scope_only"], ["CAT"])
        self.assertEqual(result["analyst_scope_only"], ["ETN"])

    def test_local_tier_labels_conflicting_with_guarded_sql_are_reported(self) -> None:
        scopes = {
            "chain_alert_scope": {"path": "scripts/chain.py", "resolved": []},
            "analyst_default_scope": {
                "path": "scripts/analyst.py",
                "resolved": ["META", "CAT"],
                "local_tier_labels": {"META": "B", "CAT": "B"},
            },
        }
        result = inv.scope_divergence(scopes, UNIVERSE)
        conflicts = {item["ticker"]: item["conflict"] for item in result["analyst_local_tier_conflicts"]}
        self.assertEqual(conflicts, {"META": "META:local_B/sql_A"})
        self.assertFalse(result["analyst_artifact_local_tier_sets_authoritative"])


class BaselineReconciliationTests(unittest.TestCase):
    def _matching_inputs(self) -> tuple[dict, dict]:
        frozen = inv.FROZEN_BASELINE
        sql_state = {
            "tier_counts": dict(frozen["guarded_sql_tier_counts"]),
            "complete_reference_level_counts": dict(frozen["complete_reference_level_counts"]),
        }
        divergence = {
            "alert_scope_count": frozen["alert_scope_count"],
            "alert_scope_tier_counts": dict(frozen["alert_scope_tier_counts"]),
            "analyst_scope_count": frozen["analyst_scope_count"],
            "shared_count": frozen["shared_scope_count"],
            "alert_scope_only": ["X"] * frozen["unique_per_scope_count"],
            "analyst_scope_only": ["Y"] * frozen["unique_per_scope_count"],
        }
        return sql_state, divergence

    def test_equal_counts_reconcile_to_match(self) -> None:
        sql_state, divergence = self._matching_inputs()
        result = inv.baseline_reconciliation(sql_state, divergence)
        self.assertEqual(result["verdict"], "match")
        self.assertEqual(result["drift"], [])

    def test_a_changed_count_reports_drift_without_masking_the_observation(self) -> None:
        sql_state, divergence = self._matching_inputs()
        sql_state["tier_counts"]["Tier C"] = int(sql_state["tier_counts"]["Tier C"]) + 7
        result = inv.baseline_reconciliation(sql_state, divergence)
        self.assertEqual(result["verdict"], "baseline_drift")
        self.assertTrue(any("Tier C" in item for item in result["drift"]))
        self.assertEqual(
            result["observed"]["guarded_sql_tier_counts"]["Tier C"],
            int(inv.FROZEN_BASELINE["guarded_sql_tier_counts"]["Tier C"]) + 7,
        )


class TierCAuditTests(unittest.TestCase):
    def _audit(self, *, in_scope: int, complete_bands: int, total: int = 268) -> dict:
        sql_state = {
            "tier_counts": {"Tier A": 15, "Tier B": 17, "Tier C": total},
            "complete_reference_level_counts": {"Tier A": 15, "Tier B": 17, "Tier C": complete_bands},
        }
        divergence = {"alert_scope_tier_counts": {"Tier A": 10, "Tier B": 8, "Tier C": in_scope}}
        rows = [
            {
                "path": "scripts/controller.py",
                "lifecycle": "active",
                "detection_classes": ["literal_ticker_scope"],
                "truth_classes": ["material_alert_state"],
                "truth_class_roles": {"material_alert_state": {"role": "producer"}},
            }
        ]
        return inv.tier_c_audit(sql_state, divergence, rows)

    def _price_right(self, audit: dict) -> dict:
        return next(item for item in audit["paths"] if item["path_id"] == "price_right_override")

    def test_price_right_is_blind_when_quotes_are_missing(self) -> None:
        audit = self._audit(in_scope=0, complete_bands=268)
        self.assertEqual(self._price_right(audit)["verdict"], "blind_spot")

    def test_price_right_is_blind_when_bands_are_incomplete(self) -> None:
        audit = self._audit(in_scope=268, complete_bands=168)
        self.assertEqual(self._price_right(audit)["verdict"], "blind_spot")

    def test_price_right_needs_both_dimensions_complete(self) -> None:
        audit = self._audit(in_scope=268, complete_bands=268)
        price_right = self._price_right(audit)
        self.assertEqual(price_right["verdict"], "covered")
        self.assertTrue(all(dimension["complete"] for dimension in price_right["dimensions"]))

    def test_hard_scoped_producer_cannot_prove_tier_c_material_change_coverage(self) -> None:
        audit = self._audit(in_scope=0, complete_bands=168)
        material = next(item for item in audit["paths"] if item["path_id"] == "material_change_override")
        self.assertEqual(material["verdict"], "blind_spot")
        self.assertTrue(material["per_producer_tier_c_coverage"])
        self.assertFalse(material["per_producer_tier_c_coverage"][0]["tier_c_coverage_proven"])


class DeterminismTests(unittest.TestCase):
    def test_semantic_hash_excludes_the_timestamp(self) -> None:
        payload = {"generated_at_utc": "2026-08-31T00:00:00Z", "surfaces": [], "value": 1}
        other = dict(payload, generated_at_utc="2027-01-01T00:00:00Z")
        semantic = {k: v for k, v in payload.items() if k != "generated_at_utc"}
        semantic_other = {k: v for k, v in other.items() if k != "generated_at_utc"}
        self.assertEqual(
            inv.sha256_bytes(json.dumps(semantic, sort_keys=True, default=str).encode("utf-8")),
            inv.sha256_bytes(json.dumps(semantic_other, sort_keys=True, default=str).encode("utf-8")),
        )


class AuthorityTests(unittest.TestCase):
    def test_no_authority_flag_grants_a_mutation(self) -> None:
        for key, value in inv.AUTHORITY.items():
            if key.endswith("_allowed"):
                self.assertFalse(value, f"{key} must remain false in a review-only inventory")

    def test_dispositions_are_proposals_only(self) -> None:
        self.assertEqual(
            set(inv.ALLOWED_DISPOSITIONS),
            {
                "keep",
                "consolidate_phase2",
                "quarantine_phase2",
                "retirement_review",
                "archive_review",
                "delete_review",
            },
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
