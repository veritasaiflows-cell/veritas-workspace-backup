from __future__ import annotations

import contextlib
import io
import unittest
import json
import sys
import tempfile
from pathlib import Path
from unittest import mock

import run_alerts_recommendations_chain as chain
import phase3g_dynamic_execution as phase3g_adapter
from finance_sql_canon_access import DynamicEntitlementScopeError, dynamic_entitlement_payload_fingerprint


class FakeDynamicScope:
    source = "guarded_sql:universe_membership.tier"

    def __init__(self) -> None:
        self.fingerprint = dynamic_entitlement_payload_fingerprint({
            "members": [{"ticker": "AAA", "tier": "A", "decision_grade_eligible": True}],
        })
        self.memberships = ["AAA"]
        self.overflow_tickers: list[str] = []
        self.aliases = {"AAA": "AAA"}
        self.integrity_breaches: list[object] = []

    def payload(self) -> dict[str, object]:
        return {
            "source": "guarded_sql:universe_membership.tier",
            "members": [{"ticker": "AAA", "tier": "A", "decision_grade_eligible": True}],
            "fingerprint": self.fingerprint,
            "count": 1,
            "tier_breakdown": {"A": 1, "B": 0},
            "integrity_breaches": [],
            "envelope_name": "test",
            "envelope_count": 1,
            "overflow_tickers": [],
            "overflow_count": 0,
        }


class FakeDynamicClient:
    def __init__(self, scope: FakeDynamicScope) -> None:
        self.scope = scope
        self.calls = 0

    def dynamic_entitlement_scope(self, *args: object, **kwargs: object) -> FakeDynamicScope:
        self.calls += 1
        return self.scope


class AlertsRecommendationsChainTests(unittest.TestCase):
    def test_active_plan_excludes_retired_stages(self) -> None:
        for window in ("morning", "midday", "post-close", "weekly"):
            scripts = {stage["script"] for stage in chain.stage_plan(window)}
            self.assertFalse(scripts & chain.RETIRED_STAGE_SCRIPTS)

    def test_legacy_market_state_refresh_is_not_a_stage(self) -> None:
        self.assertNotIn("market_state_refresh.py", {stage["script"] for stage in chain.stage_plan("morning")})

    def test_delivery_flags_reach_only_the_digest(self) -> None:
        plan = chain.stage_plan("morning", send=True, weekday_only=True)
        digest = next(stage for stage in plan if stage["name"] == "recommendation_digest")
        self.assertIn("--send", digest["args"])
        self.assertIn("--weekday-only", digest["args"])
        for stage in plan:
            if stage is not digest:
                self.assertNotIn("--send", stage["args"])

    def test_digest_source_coherence_requires_exact_controller_hash_and_summary(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            controller_path = root / "controller.json"
            digest_path = root / "digest.json"
            controller = {
                "generated_at_utc": "2026-08-30T00:00:00Z",
                "summary": {"alert_state_counts": {"monitor_only": 1}},
            }
            controller_path.write_text(json.dumps(controller), encoding="utf-8")
            digest = {
                "status": "ok",
                "validation": {"status": "ok"},
                "summary": controller["summary"],
                "source_artifacts": {
                    "alert_levels": {
                    "sha256": chain.file_sha256(controller_path),
                        "generated_at_utc": controller["generated_at_utc"],
                    }
                },
            }
            digest_path.write_text(json.dumps(digest), encoding="utf-8")
            clean = chain.digest_source_coherence("weekly", controller_path=controller_path, digest_path=digest_path)
            self.assertEqual(clean["status"], "ok")
            digest["source_artifacts"]["alert_levels"]["sha256"] = "bad"
            digest_path.write_text(json.dumps(digest), encoding="utf-8")
            bad = chain.digest_source_coherence("weekly", controller_path=controller_path, digest_path=digest_path)
            self.assertEqual(bad["status"], "error")

    def test_weekly_funnel_refresh_requires_exact_promoted_controller(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            controller = root / chain.RECURRING_SHARED_CONTROLLER_REL
            controller.parent.mkdir(parents=True)
            controller.write_text(json.dumps({"generated_at_utc": "2026-09-27T15:00:01Z"}), encoding="utf-8")
            with (
                mock.patch.object(chain, "ROOT", root),
                mock.patch("recommendation_funnel.evaluate") as evaluate,
            ):
                result = chain._refresh_recommendation_funnel_after_promotion(
                    window="weekly", promotion={"status": "ok", "controller_sha256": "wrong"})
            self.assertEqual(result["status"], "error")
            self.assertEqual(result["reason"], "shared_controller_hash_changed_before_funnel")
            evaluate.assert_not_called()
            self.assertFalse((root / "tmp/recommendation-funnel.json").exists())

    def test_weekly_funnel_refresh_writes_only_review_authority_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            controller = root / chain.RECURRING_SHARED_CONTROLLER_REL
            controller.parent.mkdir(parents=True)
            controller.write_text(json.dumps({"generated_at_utc": "2026-09-27T15:00:01Z"}), encoding="utf-8")
            payload = {
                "schema": "veritas.recommendation_funnel.v1",
                "generated_at_utc": "2026-09-27T15:00:02Z",
                "candidates": ["AAA"],
                "authority": {
                    "review_only": True,
                    "alert_or_canon_change": False,
                    "delivery": False,
                    "capital_or_execution": False,
                    "owner_approval_inferred": False,
                },
            }
            expected_hash = chain.file_sha256(controller)
            with (
                mock.patch.object(chain, "ROOT", root),
                mock.patch("recommendation_funnel.evaluate", return_value=payload) as evaluate,
            ):
                result = chain._refresh_recommendation_funnel_after_promotion(
                    window="weekly", promotion={"status": "ok", "controller_sha256": expected_hash})
            self.assertEqual(result["status"], "ok")
            self.assertEqual(result["controller_sha256"], expected_hash)
            self.assertEqual(json.loads((root / "tmp/recommendation-funnel.json").read_text()), payload)
            evaluate.assert_called_once_with(root)

    def test_weekly_funnel_suppression_is_written_and_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            controller = root / chain.RECURRING_SHARED_CONTROLLER_REL
            controller.parent.mkdir(parents=True)
            controller.write_text(json.dumps({"generated_at_utc": "2026-09-27T15:00:01Z"}), encoding="utf-8")
            payload = {
                "schema": "veritas.recommendation_funnel.v1",
                "status": "stale_suppressed",
                "stale_reason": "same-version mismatch",
                "generated_at_utc": "2026-09-27T15:00:02Z",
                "candidates": [],
                "authority": {
                    "review_only": True,
                    "alert_or_canon_change": False,
                    "delivery": False,
                    "capital_or_execution": False,
                    "owner_approval_inferred": False,
                },
            }
            with (
                mock.patch.object(chain, "ROOT", root),
                mock.patch("recommendation_funnel.evaluate", return_value=payload),
            ):
                result = chain._refresh_recommendation_funnel_after_promotion(
                    window="weekly",
                    promotion={"status": "ok", "controller_sha256": chain.file_sha256(controller)},
                )
            self.assertEqual(result["status"], "error")
            self.assertEqual(result["reason"], "stale_suppressed")
            self.assertEqual(result["stale_reason"], "same-version mismatch")
            self.assertEqual(json.loads((root / "tmp/recommendation-funnel.json").read_text()), payload)

    def test_dynamic_preview_resolves_once_and_never_runs_or_writes(self) -> None:
        client = FakeDynamicClient(FakeDynamicScope())
        scope, preview = chain.dynamic_entitlement_preview(client)
        self.assertEqual(client.calls, 1)
        self.assertEqual(preview["provider_calls"], 0)
        self.assertEqual(preview["subprocess_stages"], 0)
        self.assertEqual(preview["output_writes"], 0)
        self.assertEqual(preview["scope"]["fingerprint"], scope.fingerprint)

    def test_child_payload_mismatch_fails_without_sql(self) -> None:
        payload = FakeDynamicScope().payload()
        payload["members"][0]["ticker"] = "CHANGED"
        with self.assertRaisesRegex(DynamicEntitlementScopeError, "guarded_sql_scope_payload_fingerprint_mismatch"):
            chain.child_scope_plan(payload, payload["fingerprint"])

    def test_dynamic_cli_preview_and_denial_make_zero_subprocess_or_writes(self) -> None:
        # Valid preview-only is inert: exactly one adapter scope read, exit 0,
        # and positively zero provider/subprocess/write work. The legacy lane
        # performs no second scope read.
        adapter_client = FakeDynamicClient(FakeDynamicScope())
        legacy_client = FakeDynamicClient(FakeDynamicScope())
        stdout = io.StringIO()
        with (
            mock.patch.object(phase3g_adapter, "FinanceSqlCanonAccess", return_value=adapter_client),
            mock.patch.object(chain, "FinanceSqlCanonAccess", return_value=legacy_client),
            mock.patch.object(chain.subprocess, "run") as run_stage,
            mock.patch.object(chain, "write_json") as write_json,
            mock.patch.object(sys, "argv", ["chain", "morning", "--dynamic-entitlement-preview"]),
            contextlib.redirect_stdout(stdout),
        ):
            self.assertEqual(chain.main(), 0)
            self.assertEqual(adapter_client.calls, 1)
            self.assertEqual(legacy_client.calls, 0)
            run_stage.assert_not_called()
            write_json.assert_not_called()
        planned = json.loads(stdout.getvalue())
        self.assertEqual(planned["status"], "planned")
        self.assertEqual(planned["provider_calls"], 0)
        self.assertEqual(planned["subprocess_stages"], 0)
        self.assertEqual(planned["output_writes"], 0)
        # Contradictory preview+write is rejected early: exit 1 with zero
        # scope/SQL reads and zero provider/subprocess/write work.
        adapter_client = FakeDynamicClient(FakeDynamicScope())
        stdout = io.StringIO()
        with (
            mock.patch.object(phase3g_adapter, "FinanceSqlCanonAccess", return_value=adapter_client),
            mock.patch.object(chain.subprocess, "run") as run_stage,
            mock.patch.object(chain, "write_json") as write_json,
            mock.patch.object(sys, "argv", ["chain", "morning", "--dynamic-entitlement-preview", "--write"]),
            contextlib.redirect_stdout(stdout),
        ):
            self.assertEqual(chain.main(), 1)
            self.assertEqual(adapter_client.calls, 0)
            run_stage.assert_not_called()
            write_json.assert_not_called()
        denied = json.loads(stdout.getvalue())
        self.assertEqual(denied["status"], "error")
        self.assertEqual(denied["error"], "dynamic_incompatible_cli_options")
        # Scope+write with a non-policy origin is rejected before any
        # scope/SQL read and performs zero provider/subprocess/write work.
        adapter_client = FakeDynamicClient(FakeDynamicScope())
        stdout = io.StringIO()
        with (
            mock.patch.object(phase3g_adapter, "FinanceSqlCanonAccess", return_value=adapter_client),
            mock.patch.object(chain.subprocess, "run") as run_stage,
            mock.patch.object(chain, "write_json") as write_json,
            mock.patch.object(sys, "argv", ["chain", "morning", "--dynamic-entitlement-scope", "--write"]),
            contextlib.redirect_stdout(stdout),
        ):
            self.assertEqual(chain.main(), 1)
            self.assertEqual(adapter_client.calls, 0)
            run_stage.assert_not_called()
            write_json.assert_not_called()
        denied = json.loads(stdout.getvalue())
        self.assertEqual(denied["status"], "error")
        self.assertEqual(denied["error"], "dynamic_execution_requires_write_and_policy_origin")


if __name__ == "__main__":
    unittest.main()
