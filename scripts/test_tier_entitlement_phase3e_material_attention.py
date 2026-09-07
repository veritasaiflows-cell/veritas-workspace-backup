#!/usr/bin/env python3
"""Focused regression and falsification tests for Phase 3E."""

from __future__ import annotations

import copy
import hashlib
import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import tier_entitlement_phase3e_material_attention as phase3e
from finance_sql_canon_access import DynamicEntitlementScopeError


def event(
    symbol: str = "CCC",
    *,
    event_kind: str = "evidence_conflict",
    event_state: str = "conflicted",
    cause: str = "serious_freshness_conflict",
    source_owner: str = "evidence-owner",
    source_version: str = "v1",
    source_event_id: str = "event-1",
    materiality: str = "material",
    cause_scope: str = "ticker_specific",
    ticker_consequence_ref: str = "consequence:ccc",
    source_policy_ref: str = "policy:quote-conflict-v1",
    evidence_refs: list[str] | None = None,
) -> dict[str, object]:
    return {
        "symbol": symbol,
        "event_kind": event_kind,
        "event_state": event_state,
        "cause": cause,
        "source_owner": source_owner,
        "source_version": source_version,
        "source_event_id": source_event_id,
        "materiality": materiality,
        "cause_scope": cause_scope,
        "ticker_consequence_ref": ticker_consequence_ref,
        "source_policy_ref": source_policy_ref,
        "evidence_refs": evidence_refs or ["evidence:one"],
    }


def request(
    *,
    events: list[dict[str, object]] | None = None,
    status_updates: list[dict[str, object]] | None = None,
    ordinal: int = 100,
    day_id: str | None = None,
    run_id: str | None = None,
) -> dict[str, object]:
    return {
        "schema": phase3e.INPUT_SCHEMA,
        "run_id": run_id or f"run-{ordinal}",
        "market_day": {
            "id": day_id or f"day-{ordinal}",
            "ordinal": ordinal,
            "calendar_owner": "market-calendar-owner",
            "calendar_version": "calendar-v1",
        },
        "events": events or [],
        "status_updates": status_updates or [],
    }


def status_update(
    key: str,
    kind: str,
    *,
    ordinal: int,
    owner: str = "review-owner",
    displaced: str = "",
    resolution: str = "",
) -> dict[str, object]:
    return {
        "event_dedupe_key": key,
        "update_kind": kind,
        "recorded_by_owner": owner,
        "market_day_id": f"day-{ordinal}",
        "market_day_ordinal": ordinal,
        "displaced_by_work_ref": displaced,
        "resolution_source_event_id": resolution,
    }


class FakeScope:
    def __init__(self, tiers: dict[str, str], aliases: dict[str, str] | None = None):
        self.identities = {
            ticker: SimpleNamespace(tier=tier, ticker=ticker)
            for ticker, tier in sorted(tiers.items())
        }
        self.aliases = {ticker: ticker for ticker in tiers}
        if aliases:
            self.aliases.update(aliases)


class FakeClient:
    def __init__(self, scope: FakeScope | None = None, error: Exception | None = None):
        self.scope = scope or FakeScope({"CCC": "C", "AAA": "A", "BBB": "B"})
        self.error = error
        self.calls: list[tuple[object, object]] = []

    def dynamic_entitlement_scope(self, *, envelope_name=None, envelope_count=None):
        self.calls.append((envelope_name, envelope_count))
        if self.error:
            raise self.error
        return self.scope

    def __getattr__(self, name: str):
        raise AssertionError(f"unexpected database method: {name}")


class Phase3EMaterialAttentionTests(unittest.TestCase):
    def build(
        self,
        doc: dict[str, object],
        *,
        prior: dict[str, object] | None = None,
        client: FakeClient | None = None,
    ) -> tuple[dict[str, object], FakeClient]:
        selected = client or FakeClient()
        result = phase3e.build_material_attention_ledger(doc, prior=prior, client=selected)
        return result, selected

    def test_tier_c_alias_positive_is_candidate_only(self):
        client = FakeClient(FakeScope({"BRK.B": "C"}, {"BRK-B": "BRK.B"}))
        row = event(
            "brk-b",
            event_kind="invalidation_alert",
            cause="thesis_invalidation",
            source_policy_ref="",
        )
        result, client = self.build(request(events=[row]), client=client)
        self.assertEqual(result["status"], "review_only_candidates")
        self.assertEqual(result["scope_binding"]["resolver_invocation_count"], 1)
        self.assertIsNone(result["scope_binding"]["tier_c_scope_fingerprint"])
        self.assertEqual(client.calls, [(None, None)])
        self.assertEqual(result["unresolved_candidates"][0]["canonical_ticker"], "BRK.B")
        self.assertEqual(result["notifications"][0]["reason"], "new")
        authority = result["authority"]
        for key in (
            "queue_owner",
            "queue_priority_authority",
            "tier_write_authority",
            "recommendation_authority",
            "provider_or_external_authority",
        ):
            self.assertIs(authority[key], False)
        self.assertIsNone(result["degraded_mode_digest"]["total_queued"])

    def test_unchanged_item_survives_repeated_runs_without_notification(self):
        first, _ = self.build(request(events=[event()], ordinal=100))
        current = first
        for ordinal in range(101, 107):
            current, _ = self.build(
                request(events=[event()], ordinal=ordinal), prior=current
            )
            self.assertEqual(len(current["unresolved_candidates"]), 1)
            self.assertEqual(current["notifications"], [])
            self.assertEqual(
                current["unresolved_candidates"][0]["first_seen"]["market_day_ordinal"],
                100,
            )
        item = current["unresolved_candidates"][0]
        self.assertEqual(item["age_market_days"], 6)
        self.assertEqual(item["status_refresh_age_market_days"], 6)
        self.assertIn("review_or_deferral_overdue", item["debts"])
        self.assertIn("five_market_day_status_breach", item["debts"])

    def test_material_change_notifies_but_does_not_refresh_status_clock(self):
        first, _ = self.build(request(events=[event()], ordinal=100))
        changed = event(source_event_id="event-2", evidence_refs=["evidence:two"])
        second, _ = self.build(request(events=[changed], ordinal=103), prior=first)
        item = second["unresolved_candidates"][0]
        self.assertEqual(second["notifications"][0]["reason"], "materially_changed")
        self.assertEqual(item["last_status_refresh"]["market_day_ordinal"], 100)
        self.assertEqual(item["status_refresh_age_market_days"], 3)

    def test_source_version_change_creates_new_key_and_keeps_prior_open(self):
        first, _ = self.build(request(events=[event()], ordinal=100))
        newer = event(source_version="v2", source_event_id="event-2")
        second, _ = self.build(request(events=[newer], ordinal=101), prior=first)
        self.assertEqual(len(second["unresolved_candidates"]), 2)
        self.assertEqual([row["reason"] for row in second["notifications"]], ["new"])

    def test_review_deferral_and_source_owner_resolution_are_explicit(self):
        first, _ = self.build(request(events=[event()], ordinal=100))
        key = first["unresolved_candidates"][0]["event_dedupe_key"]
        reviewed, _ = self.build(
            request(
                ordinal=101,
                status_updates=[status_update(key, "reviewed", ordinal=101)],
            ),
            prior=first,
        )
        self.assertEqual(
            reviewed["unresolved_candidates"][0]["last_status_refresh"]["kind"],
            "reviewed",
        )
        self.assertNotIn(
            "owner_unassigned", reviewed["unresolved_candidates"][0]["debts"]
        )
        deferred, _ = self.build(
            request(
                ordinal=102,
                status_updates=[
                    status_update(
                        key,
                        "deferred",
                        ordinal=102,
                        displaced="work:higher-consequence",
                    )
                ],
            ),
            prior=reviewed,
        )
        self.assertEqual(
            deferred["unresolved_candidates"][0]["latest_deferral"][
                "displaced_by_work_ref"
            ],
            "work:higher-consequence",
        )
        resolved, _ = self.build(
            request(
                ordinal=103,
                status_updates=[
                    status_update(
                        key,
                        "resolved",
                        ordinal=103,
                        owner="evidence-owner",
                        resolution="event-resolution-1",
                    )
                ],
            ),
            prior=deferred,
        )
        self.assertEqual(resolved["unresolved_candidates"], [])
        self.assertEqual(resolved["status_transitions"][0]["update_kind"], "resolved")

    def test_invalid_deferral_and_resolution_remain_visible_conflicts(self):
        first, _ = self.build(request(events=[event()], ordinal=100))
        key = first["unresolved_candidates"][0]["event_dedupe_key"]
        deferred, _ = self.build(
            request(
                ordinal=101,
                status_updates=[status_update(key, "deferred", ordinal=101, displaced="")],
            ),
            prior=first,
        )
        self.assertEqual(len(deferred["unresolved_candidates"]), 1)
        self.assertEqual(
            deferred["identity_and_tier_conflicts"][0]["reason"],
            "deferral_missing_displaced_work",
        )
        resolved, _ = self.build(
            request(
                ordinal=102,
                status_updates=[status_update(key, "resolved", ordinal=102)],
            ),
            prior=deferred,
        )
        self.assertEqual(len(resolved["unresolved_candidates"]), 1)
        self.assertEqual(
            resolved["identity_and_tier_conflicts"][0]["reason"],
            "resolution_not_source_owner_bound",
        )

    def test_duplicate_status_updates_reject_both_without_refresh(self):
        first, _ = self.build(request(events=[event()], ordinal=100))
        key = first["unresolved_candidates"][0]["event_dedupe_key"]
        result, _ = self.build(
            request(
                ordinal=101,
                status_updates=[
                    status_update(key, "reviewed", ordinal=101, owner="owner-one"),
                    status_update(key, "reviewed", ordinal=101, owner="owner-two"),
                ],
            ),
            prior=first,
        )
        self.assertEqual(result["status_transitions"], [])
        self.assertEqual(
            result["unresolved_candidates"][0]["last_status_refresh"][
                "market_day_ordinal"
            ],
            100,
        )
        self.assertEqual(
            result["identity_and_tier_conflicts"][0]["reason"],
            "duplicate_status_update",
        )

    def test_material_flood_carries_all_fifty_and_reports_candidate_digest(self):
        tiers = {f"C{index:03d}": "C" for index in range(50)}
        client = FakeClient(FakeScope(tiers))
        rows = [
            event(
                ticker,
                event_kind="thesis_change",
                cause="thesis_changed",
                source_event_id=f"event-{ticker}",
                source_policy_ref="",
            )
            for ticker in tiers
        ]
        first, _ = self.build(request(events=rows), client=client)
        self.assertEqual(len(first["unresolved_candidates"]), 50)
        self.assertEqual(first["degraded_mode_digest"]["total_unresolved_candidates"], 50)
        self.assertIsNone(first["degraded_mode_digest"]["total_queued"])
        second, _ = self.build(
            request(events=rows, ordinal=101),
            prior=first,
            client=FakeClient(FakeScope(tiers)),
        )
        self.assertEqual(len(second["unresolved_candidates"]), 50)
        self.assertEqual(second["notifications"], [])

    def test_broad_macro_fanout_groups_once_without_candidates(self):
        tiers = {f"C{index:03d}": "C" for index in range(268)}
        rows = [
            event(
                ticker,
                event_kind="thesis_change",
                cause="macro_regime_change",
                source_event_id=f"macro-{ticker}",
                cause_scope="broad_macro",
                ticker_consequence_ref="",
                source_policy_ref="",
            )
            for ticker in tiers
        ]
        result, _ = self.build(
            request(events=rows), client=FakeClient(FakeScope(tiers))
        )
        self.assertEqual(result["unresolved_candidates"], [])
        self.assertEqual(len(result["grouped_macro_events"]), 1)
        self.assertEqual(len(result["grouped_macro_events"][0]["canonical_tickers"]), 268)

    def test_a_or_b_event_is_out_of_lane_not_silently_discarded(self):
        result, _ = self.build(
            request(
                events=[
                    event(
                        "AAA",
                        event_kind="invalidation_alert",
                        cause="thesis_invalidation",
                        source_policy_ref="",
                    )
                ]
            )
        )
        self.assertEqual(result["unresolved_candidates"], [])
        self.assertEqual(result["out_of_lane"][0]["canonical_ticker"], "AAA")
        self.assertEqual(result["out_of_lane"][0]["owner_surface"], "no_owner_surface")

    def test_unknown_alias_and_undefined_policy_are_visible(self):
        result, _ = self.build(
            request(
                events=[
                    event("UNKNOWN", source_event_id="unknown-event"),
                    event(
                        event_kind="freshness_decay",
                        source_event_id="freshness-event",
                    ),
                    event(
                        event_kind="price_reference_change",
                        source_event_id="price-event",
                    ),
                ]
            )
        )
        reasons = {row["reason"] for row in result["identity_and_tier_conflicts"]}
        self.assertEqual(
            reasons,
            {"unknown_or_conflicting_alias", "undefined_phase3e_policy_kind"},
        )

    def test_serious_freshness_conflict_requires_named_upstream_policy(self):
        result, _ = self.build(
            request(events=[event(source_policy_ref="")])
        )
        self.assertEqual(
            result["identity_and_tier_conflicts"][0]["reason"],
            "serious_freshness_conflict_missing_upstream_policy",
        )
        self.assertEqual(result["unresolved_candidates"], [])

    def test_same_run_dedupe_collision_rejects_key(self):
        first = event(source_event_id="event-1", evidence_refs=["evidence:one"])
        second = event(source_event_id="event-2", evidence_refs=["evidence:two"])
        result, _ = self.build(request(events=[first, second]))
        self.assertEqual(result["unresolved_candidates"], [])
        self.assertEqual(
            result["identity_and_tier_conflicts"][0]["reason"],
            "event_dedupe_collision",
        )

    def test_same_content_dedupe_is_permutation_stable(self):
        source_z = event(
            event_kind="thesis_change",
            event_state="changed",
            cause="thesis_changed",
            source_owner="owner",
            source_event_id="source-z",
            source_policy_ref="",
        )
        source_a = copy.deepcopy(source_z)
        source_a["source_event_id"] = "source-a"
        forward, _ = self.build(
            request(events=[source_z, source_a], run_id="permutation-run")
        )
        reverse, _ = self.build(
            request(events=[source_a, source_z], run_id="permutation-run")
        )
        self.assertEqual(
            phase3e.canonical_json_bytes(forward),
            phase3e.canonical_json_bytes(reverse),
        )
        self.assertEqual(
            forward["unresolved_candidates"][0]["latest_source_event_id"],
            "source-a",
        )

    def test_scope_conflict_blocks_new_admission_and_carries_prior(self):
        first, _ = self.build(request(events=[event()], ordinal=100))
        failing = FakeClient(
            error=DynamicEntitlementScopeError("guarded_sql_scope_tier_conflict")
        )
        blocked, client = self.build(
            request(events=[event(source_event_id="event-2")], ordinal=101),
            prior=first,
            client=failing,
        )
        self.assertEqual(blocked["status"], "blocked")
        self.assertEqual(blocked["blocking_errors"], ["guarded_sql_scope_tier_conflict"])
        self.assertEqual(len(blocked["unresolved_candidates"]), 1)
        self.assertEqual(client.calls, [(None, None)])

    def test_authority_shaped_input_is_rejected_before_sql(self):
        doc = request(events=[event()])
        doc["events"][0]["priority"] = "urgent"
        client = FakeClient()
        with self.assertRaisesRegex(
            phase3e.MaterialAttentionError, "authority_shaped_field_rejected"
        ):
            phase3e.build_material_attention_ledger(doc, client=client)
        self.assertEqual(client.calls, [])

    def test_prior_corruption_and_market_day_regression_fail_closed_before_sql(self):
        first, _ = self.build(request(events=[event()], ordinal=100))
        corrupt = copy.deepcopy(first)
        corrupt["unresolved_candidates"].append(
            copy.deepcopy(corrupt["unresolved_candidates"][0])
        )
        client = FakeClient()
        with self.assertRaisesRegex(
            phase3e.MaterialAttentionError, "prior_duplicate_event_dedupe_key"
        ):
            phase3e.build_material_attention_ledger(
                request(ordinal=101), prior=corrupt, client=client
            )
        self.assertEqual(client.calls, [])
        with self.assertRaisesRegex(
            phase3e.MaterialAttentionError, "market_day_ordinal_regression"
        ):
            phase3e.build_material_attention_ledger(
                request(ordinal=99), prior=first, client=client
            )
        self.assertEqual(client.calls, [])

    def test_prior_material_hash_tamper_fails_closed_before_sql(self):
        first, _ = self.build(request(events=[event()], ordinal=100))
        tampered = copy.deepcopy(first)
        tampered["unresolved_candidates"][0]["evidence_refs"] = ["evidence:tampered"]
        client = FakeClient()
        with self.assertRaisesRegex(
            phase3e.MaterialAttentionError, "material_content_hash_mismatch"
        ):
            phase3e.build_material_attention_ledger(
                request(ordinal=101), prior=tampered, client=client
            )
        self.assertEqual(client.calls, [])

    def test_prior_market_day_strings_are_canonical_before_sql(self):
        first, _ = self.build(request(events=[event()], ordinal=100))
        for field in ("id", "calendar_owner", "calendar_version"):
            with self.subTest(field=field):
                tampered = copy.deepcopy(first)
                original = tampered["market_day"][field]
                tampered["market_day"][field] = f" {original} "
                client = FakeClient()
                with self.assertRaisesRegex(
                    phase3e.MaterialAttentionError,
                    rf"prior\.market_day\.{field}_not_canonical",
                ):
                    phase3e.build_material_attention_ledger(
                        request(ordinal=101), prior=tampered, client=client
                    )
                self.assertEqual(client.calls, [])

    def test_rehashed_semantically_invalid_prior_fails_closed_before_sql(self):
        cases = [
            (
                "freshness_policy",
                event(),
                {"source_policy_ref": ""},
                "serious_freshness_conflict_missing_upstream_policy",
            ),
            (
                "catalyst_consequence",
                event(
                    event_kind="catalyst_alert",
                    event_state="announced",
                    cause="earnings_catalyst",
                    source_event_id="catalyst-1",
                    source_policy_ref="",
                ),
                {"ticker_consequence_ref": ""},
                "catalyst_missing_distinct_ticker_consequence",
            ),
            (
                "candidate_shaped_macro",
                event(
                    event_kind="thesis_change",
                    event_state="changed",
                    cause="macro_regime_change",
                    source_event_id="macro-candidate-1",
                    source_policy_ref="",
                ),
                {"cause_scope": "broad_macro", "ticker_consequence_ref": ""},
                "broad_macro_without_distinct_ticker_consequence",
            ),
            (
                "whitespace_freshness_policy",
                event(),
                {"source_policy_ref": "   "},
                "source_policy_ref_not_canonical",
            ),
            (
                "whitespace_catalyst_consequence",
                event(
                    event_kind="catalyst_alert",
                    event_state="announced",
                    cause="earnings_catalyst",
                    source_event_id="catalyst-space-1",
                    source_policy_ref="",
                ),
                {"ticker_consequence_ref": "   "},
                "ticker_consequence_ref_not_canonical",
            ),
            (
                "whitespace_macro_consequence",
                event(
                    event_kind="thesis_change",
                    event_state="changed",
                    cause="macro_regime_change",
                    source_event_id="macro-space-1",
                    source_policy_ref="",
                ),
                {"cause_scope": "broad_macro", "ticker_consequence_ref": "   "},
                "ticker_consequence_ref_not_canonical",
            ),
            (
                "whitespace_wrapped_cause",
                event(),
                {"cause": " serious_freshness_conflict ", "source_policy_ref": ""},
                "cause_not_canonical",
            ),
            (
                "invalid_canonical_ticker_identifier",
                event(),
                {"canonical_ticker": "CCC!"},
                "canonical_ticker_invalid",
            ),
        ]
        for name, seed, mutation, expected_error in cases:
            with self.subTest(name=name):
                prior, _ = self.build(request(events=[seed], ordinal=100))
                tampered = copy.deepcopy(prior)
                candidate = tampered["unresolved_candidates"][0]
                candidate.update(mutation)
                candidate["event_dedupe_key"] = phase3e._candidate_dedupe_key(
                    candidate["canonical_ticker"], candidate
                )
                candidate["material_content_hash"] = phase3e._material_content_hash(
                    candidate["canonical_ticker"], candidate
                )
                client = FakeClient()
                with self.assertRaisesRegex(
                    phase3e.MaterialAttentionError, expected_error
                ):
                    phase3e.build_material_attention_ledger(
                        request(ordinal=101), prior=tampered, client=client
                    )
                self.assertEqual(client.calls, [])

    def test_resolver_boundary_is_exactly_one_call_and_no_other_db_method(self):
        client = FakeClient()
        result, _ = self.build(request(events=[event()]), client=client)
        self.assertEqual(result["status"], "review_only_candidates")
        self.assertEqual(client.calls, [(None, None)])

    def test_output_has_no_effective_authority_fields(self):
        result, _ = self.build(request(events=[event()]))
        forbidden = {
            "priority",
            "rank",
            "score",
            "p0",
            "p3",
            "effective_tier_override",
            "recommendation",
            "approval",
            "action",
            "provider_request",
        }

        def walk(value):
            if isinstance(value, dict):
                for key, child in value.items():
                    self.assertNotIn(key.casefold(), forbidden)
                    walk(child)
            elif isinstance(value, list):
                for child in value:
                    walk(child)

        walk(result)
        self.assertEqual(result["inherited_blockers"], ["external_baseline_blocked"])

    def test_cli_default_does_not_write_and_out_requires_write(self):
        doc = request(events=[event()])
        with tempfile.TemporaryDirectory() as directory:
            input_path = Path(directory) / "input.json"
            output_path = Path(directory) / "should-not-exist.json"
            input_path.write_text(json.dumps(doc), encoding="utf-8")
            fake_access = lambda: FakeClient()
            stdout = io.StringIO()
            stderr = io.StringIO()
            with patch.object(phase3e, "FinanceSqlCanonAccess", fake_access):
                with redirect_stdout(stdout), redirect_stderr(stderr):
                    exit_code = phase3e.main(["--input", str(input_path)])
            self.assertEqual(exit_code, 0)
            self.assertFalse(output_path.exists())
            self.assertEqual(stderr.getvalue(), "")
            with patch.object(phase3e, "FinanceSqlCanonAccess", fake_access):
                with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                    exit_code = phase3e.main(
                        ["--input", str(input_path), "--out", str(output_path)]
                    )
            self.assertEqual(exit_code, 2)
            self.assertFalse(output_path.exists())

    def test_cli_duplicate_json_key_is_rejected_before_sql(self):
        raw = (
            '{"schema":"%s","schema":"%s","run_id":"run-100",'
            '"market_day":{"id":"day-100","ordinal":100,'
            '"calendar_owner":"market-calendar-owner",'
            '"calendar_version":"calendar-v1"},"events":[],"status_updates":[]}'
            % (phase3e.INPUT_SCHEMA, phase3e.INPUT_SCHEMA)
        )
        with tempfile.TemporaryDirectory() as directory:
            input_path = Path(directory) / "duplicate.json"
            input_path.write_text(raw, encoding="utf-8")
            constructed = 0

            def access():
                nonlocal constructed
                constructed += 1
                return FakeClient()

            with patch.object(phase3e, "FinanceSqlCanonAccess", access):
                with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                    exit_code = phase3e.main(["--input", str(input_path)])
        self.assertEqual(exit_code, 2)
        self.assertEqual(constructed, 0)

    def test_output_path_is_confined_to_dedicated_json_artifact_root(self):
        accepted = phase3e._contained_output_path(
            "tmp/phase3e-material-attention/candidate-ledger.json"
        )
        self.assertEqual(
            accepted,
            (phase3e.PHASE3E_OUTPUT_ROOT / "candidate-ledger.json").resolve(),
        )
        with self.assertRaisesRegex(
            phase3e.MaterialAttentionError,
            "output_path_outside_phase3e_artifact_root",
        ):
            phase3e._contained_output_path("06. Playbooks/owner-canon.json")
        with self.assertRaisesRegex(
            phase3e.MaterialAttentionError, "output_path_must_be_json"
        ):
            phase3e._contained_output_path(
                "tmp/phase3e-material-attention/candidate-ledger.txt"
            )

    def test_source_has_no_provider_subprocess_or_sql_write_path(self):
        source = Path(phase3e.__file__).read_text(encoding="utf-8")
        forbidden_imports = ("import requests", "import yfinance", "import subprocess")
        for token in forbidden_imports:
            self.assertNotIn(token, source)
        self.assertNotIn("universe_memberships(", source)
        self.assertNotIn("execute(", source)
        self.assertNotIn("executemany(", source)


if __name__ == "__main__":
    unittest.main(verbosity=2)
