"""Synthetic full-guard -> assembler -> sealed alert -> retained digest proof.

No production SQL, policy, ledger or provider is touched. Production-marked
construction is explicit test-only private fixture injection, not a public API.
"""
from __future__ import annotations
import hashlib
import json
import sys
import sqlite3
import time
from dataclasses import replace
from contextlib import closing
from datetime import datetime,timezone
from unittest import mock

import pytest
import finance_sql_canon_access as canon
import phase3g_recurring_reference_inputs as inputs
import phase3g_dynamic_execution as adapter
import run_alerts_recommendations_chain as chain
from phase3g_synthetic_fixture import build_fixture
from test_tier_entitlement_phase3f_canary import write_policy


def quote_documents(tickers, *, generated):
    import alert_level_freshness_controller as alert
    session=dict(market_session_window="market_closed_weekend_or_holiday",fresh_intraday_allowed=False,
                 closed_market_expected_stale_allowed=True)
    snapshot=dict(status="ok",generated_at_utc=generated,
        authority={name:False for name in alert.QUOTE_PROOF_REQUIRED_FALSE_AUTHORITY},
        credential_source={"ambiguous_or_live_names_detected":False},symbols_missing=[],
        symbols_requested=list(tickers),symbols_observed=list(tickers),market_session=session,
        snapshots=[dict(symbol=t,price=100.0,source_timestamp_utc=generated,
            calendar_freshness_status="current_last_completed_session",freshness_status="current_but_not_intraday_fresh",
            **session) for t in tickers])
    validation=dict(status="ok",critical_count=0,findings=[],
                    validated_artifact="tmp/intraday-alerts/quote-snapshot-proof.json")
    return inputs.canonical_json_bytes(snapshot),inputs.canonical_json_bytes(validation)


@pytest.fixture
def bound(tmp_path,request):
    root=tmp_path/"synthetic"
    db=build_fixture(root)
    generated=datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00","Z")
    with closing(sqlite3.connect(db)) as conn:
        if getattr(request,"param",True) is False:
            conn.execute("UPDATE universe_membership SET decision_grade_eligible=1 WHERE ticker='S001'")
        # This integration case exercises entitlement debt, not the independent
        # 14-day level-age decay policy. Keep its synthetic reference snapshot
        # aligned with the synthetic quote instead of inheriting the fixture's
        # historical 2026-09-05 timestamp and becoming wall-clock dependent.
        conn.execute("UPDATE reference_levels SET source_generated_at_utc=?",(generated,))
        conn.execute("UPDATE evidence_freshness SET source_generated_at_utc=?",(generated,))
        conn.execute("UPDATE source_lineage SET source_generated_at_utc=?, inserted_at_utc=?",(generated,generated))
        conn.commit()
    deadline=time.monotonic()+30
    rows=inputs._collect(root,deadline,True)
    raw=inputs.canonical_json_bytes(rows)
    package=inputs.assemble(inputs._BoundCapture(raw,inputs._sha(raw),deadline,True,inputs._SEAL))
    write_policy(root)
    quote,validation=quote_documents(("S000","S001"),generated=generated)
    return root,package,quote,validation


@pytest.mark.parametrize("bound",[False,True],indirect=True)
def test_full_guard_assembler_sealed_component_retained_digest_no_provider(bound):
    import analyst_consensus_refresh as analyst
    root,package,quote,validation=bound
    with mock.patch.object(chain,"ROOT",root), \
         mock.patch.object(canon.FinanceSqlCanonAccess,"dynamic_entitlement_scope",side_effect=AssertionError("second selection")), \
         mock.patch.object(chain,"reserve_provider_calls",side_effect=AssertionError("alert-only budget is zero")), \
         mock.patch.object(analyst,"_build_phase3f_analyst_component_with_authorization",side_effect=AssertionError("weekly analyst invoked")):
        result=chain.run_policy_canary(components=("alert_level_freshness",),run_id="recurring-synthetic-a1",
            alert_quote_snapshot_json=quote,alert_quote_validation_json=validation,
            dynamic_execution=True,recurring_reference_inputs=package,recurring_window="midday")
    has_debt=bool(json.loads(package.scope)["eligibility_debt"])
    assert result["status"] == ("completed_with_visible_debt" if has_debt else "completed")
    assert result["component_metrics"]["analyst_consensus"]["status"]=="skipped_not_approved"
    assert result["component_metrics"]["alert_level_freshness"]["provider_method_attempts"]==0
    run=root/chain.PHASE3F_POLICY_RUN_ROOT
    proof_file=run/"recurring-synthetic-a1.canary_proof.json"
    proof=json.loads(proof_file.read_text())
    assert proof["scope_count"]==2
    assert proof["scope_payload_sha256"]==hashlib.sha256(package.scope).hexdigest()
    assert proof["recurring_reference_provenance_sha256"]==hashlib.sha256(package.provenance).hexdigest()
    assert proof["recurring_reference_provenance"]["readset_sha256"]
    controller_file=run/"recurring-synthetic-a1.alert_level_freshness.json"
    assert proof["recurring_digest"]["controller_sha256"]==hashlib.sha256(controller_file.read_bytes()).hexdigest()
    controller=json.loads(controller_file.read_text())
    assert all(row["level_as_of_utc"]==row["quote_as_of_utc"] for row in controller["rows"])
    assert all(row["level_age_hours"] <= controller["policy"]["max_level_age_days"]*24
               for row in controller["rows"])
    assert proof["recurring_digest"]["external_delivery"]=="not_run"
    assert proof["recurring_digest"]["status"]=="ok"
    assert proof["recurring_digest"]["message_preview"]
    assert proof["recurring_digest"]["summary"]["monitor_only_tickers"]==(["S000"] if has_debt else ["S000","S001"])
    assert proof["recurring_digest"]["summary"]["freshness_review_tickers"]==(["S001"] if has_debt else [])
    evidence=proof["guarded_sql_membership_selection_evidence"]
    assert evidence["second_selection_performed"] is False
    assert evidence["additional_membership_selections_in_this_run"]==0
    assert evidence["scope_payload_sha256"]==hashlib.sha256(package.scope).hexdigest()
    shared_controller=root/chain.RECURRING_SHARED_CONTROLLER_REL
    assert json.loads(shared_controller.read_text())==controller
    assert proof["shared_promotion"]["controller_sha256"]==hashlib.sha256(shared_controller.read_bytes()).hexdigest()
    assert not (root/"state/dynamic-entitlement-provider-call-ledger.json").exists()


@pytest.mark.parametrize("case",["untrusted","expired","changed_manifest","foreign_quote","analyst","client","raw_reference","missing_package"])
def test_recurring_rejects_before_policy_reservation_or_writes(bound,case):
    root,package,quote,validation=bound
    kwargs=dict(components=("alert_level_freshness",),run_id="never-run",dynamic_execution=True,
                recurring_reference_inputs=package,recurring_window="morning",
                alert_quote_snapshot_json=quote,alert_quote_validation_json=validation)
    if case=="untrusted": kwargs["recurring_reference_inputs"]={"verified":True}
    if case=="expired": kwargs["recurring_reference_inputs"]=replace(package,expires_monotonic=0)
    if case=="changed_manifest": kwargs["recurring_reference_inputs"]=replace(package,provenance=b"{}")
    if case=="foreign_quote": kwargs["alert_quote_snapshot_json"]=inputs.canonical_json_bytes({"quotes":[{"ticker":"FOREIGN"}]})
    if case=="analyst": kwargs["components"]=("analyst_consensus","alert_level_freshness")
    if case=="client": kwargs["client"]=object()
    if case=="raw_reference": kwargs["alert_reference_evidence_json"]=package.evidence
    if case=="missing_package": kwargs["recurring_reference_inputs"]=None
    with mock.patch.object(chain,"prepare_policy_canary",side_effect=AssertionError("policy work reached")) as prepare:
        with pytest.raises((ValueError,RuntimeError,KeyError)):
            chain.run_policy_canary(**kwargs)
    prepare.assert_not_called()
    assert not (root/chain.PHASE3F_POLICY_RUN_ROOT).exists()


def test_recurring_cli_acquires_once_and_excludes_weekly_analyst(bound):
    import argparse
    root,package,quote,validation=bound
    # The recurring lane supplies quotes through automatic policy-authorized
    # intake; explicit quote files are rejected, so none are passed here.
    args=argparse.Namespace(dynamic_entitlement_scope=True,dynamic_entitlement_preview=False,dry_run=False,
        write=True,scope_origin="phase3f_dynamic_entitlement",recurring_reference_inputs=True,
        alert_reference_evidence=None,alert_quote_snapshot=None,alert_quote_validation=None,
        dynamic_run_id="cli-synthetic",window="midday")
    argv=["chain","midday","--dynamic-entitlement-scope","--recurring-reference-inputs","--write",
          "--scope-origin","phase3f_dynamic_entitlement"]
    intake=dict(run_id="cli-synthetic",snapshot_json=quote,validation_json=validation,
                receipt={"provider":"alpaca_market_data","attempts_observed":1})
    with mock.patch.object(sys,"argv",argv),mock.patch.object(chain,"ROOT",root), \
         mock.patch.object(inputs,"acquire_reference_inputs",return_value=package) as acquire, \
         mock.patch.object(adapter,"_automatic_quote_intake",return_value=intake) as quote_intake, \
         mock.patch.object(adapter,"FinanceSqlCanonAccess",side_effect=AssertionError("second accessor")), \
         mock.patch.object(chain,"run_policy_canary",return_value={"status":"completed"}) as run:
        assert adapter.dispatch(args,components=("alert_level_freshness","analyst_consensus"))==0
    acquire.assert_called_once_with(max_scope_count=128,
                                    package_lifetime_seconds=adapter.PACKAGE_LIFETIME_SECONDS)
    quote_intake.assert_called_once()
    assert quote_intake.call_args.args[2] is package
    assert run.call_args.kwargs["components"]==("alert_level_freshness",)
    assert run.call_args.kwargs["recurring_reference_inputs"] is package
    # Receipts must land inside the redirected root. A real-workspace write here
    # overwrites the production chain proofs and quote proof with synthetic
    # fixture data, which is exactly what happened before this assertion existed.
    assert (root/"tmp/alerts-recommendations-chain-midday.json").exists()
    assert (root/"tmp/alerts-recommendations-chain-current.json").exists()
    assert (root/"tmp/intraday-alerts/quote-snapshot-proof.json").read_bytes()==quote
    assert (root/"tmp/intraday-alerts/quote-snapshot-proof-validation.json").read_bytes()==validation


def test_recurring_cli_rejects_explicit_quote_files_before_any_work(bound):
    import argparse
    root,package,quote,validation=bound
    quote_file=root/"quote.json"; quote_file.write_bytes(quote)
    args=argparse.Namespace(dynamic_entitlement_scope=True,dynamic_entitlement_preview=False,dry_run=False,
        write=True,scope_origin="phase3f_dynamic_entitlement",recurring_reference_inputs=True,
        alert_reference_evidence=None,alert_quote_snapshot=quote_file,alert_quote_validation=None,
        dynamic_run_id="cli-synthetic",window="midday")
    argv=["chain","midday","--dynamic-entitlement-scope","--recurring-reference-inputs","--write",
          "--scope-origin","phase3f_dynamic_entitlement","--alert-quote-snapshot",str(quote_file)]
    with mock.patch.object(sys,"argv",argv),mock.patch.object(chain,"ROOT",root), \
         mock.patch.object(inputs,"acquire_reference_inputs",side_effect=AssertionError("acquired")), \
         mock.patch.object(adapter,"_automatic_quote_intake",side_effect=AssertionError("intake")):
        assert adapter.dispatch(args,components=("alert_level_freshness","analyst_consensus"))==1


def test_weekly_funnel_failure_is_visible_debt_in_canary_proof(bound):
    import analyst_consensus_refresh as analyst
    root,package,quote,validation=bound
    funnel_result={"status":"error","reason":"stale_suppressed","stale_reason":"same-version mismatch"}
    with mock.patch.object(chain,"ROOT",root), \
         mock.patch.object(canon.FinanceSqlCanonAccess,"dynamic_entitlement_scope",side_effect=AssertionError("second selection")), \
         mock.patch.object(chain,"reserve_provider_calls",side_effect=AssertionError("alert-only budget is zero")), \
         mock.patch.object(analyst,"_build_phase3f_analyst_component_with_authorization",side_effect=AssertionError("weekly analyst invoked")), \
         mock.patch.object(chain,"_refresh_recommendation_funnel_after_promotion",return_value=funnel_result) as refresh:
        result=chain.run_policy_canary(components=("alert_level_freshness",),run_id="recurring-weekly-funnel-a1",
            alert_quote_snapshot_json=quote,alert_quote_validation_json=validation,
            dynamic_execution=True,recurring_reference_inputs=package,recurring_window="weekly")
    assert result["status"]=="completed_with_visible_debt"
    assert result["recommendation_funnel"]==funnel_result
    refresh.assert_called_once()
    proof=json.loads((root/chain.PHASE3F_POLICY_RUN_ROOT/
                      "recurring-weekly-funnel-a1.canary_proof.json").read_text())
    assert proof["status"]=="completed_with_visible_debt"
    assert proof["recommendation_funnel"]==funnel_result
