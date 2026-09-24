"""Alert event ledger wiring into the recurring chain (design test 6).

Synthetic recurring runs with chain.ROOT redirected: the ledger appends only
after a verified shared promotion, and a ledger failure never changes the
alerts run status. No production path is touched.
"""
from __future__ import annotations

import json
import sqlite3
import time
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

import finance_sql_canon_access as canon
import phase3g_recurring_reference_inputs as inputs
import run_alerts_recommendations_chain as chain
import alert_event_ledger as ledger
from phase3g_synthetic_fixture import build_fixture
from test_phase3g_recurring_integration import quote_documents
from test_tier_entitlement_phase3f_canary import write_policy

WORKSPACE = Path(__file__).resolve().parents[1]


def make_bound(root: Path):
    build_fixture(root)
    deadline = time.monotonic() + 30
    rows = inputs._collect(root, deadline, True)
    raw = inputs.canonical_json_bytes(rows)
    package = inputs.assemble(inputs._BoundCapture(raw, inputs._sha(raw), deadline, True, inputs._SEAL))
    write_policy(root)
    quote, validation = quote_documents(("S000", "S001"), generated=datetime.now(timezone.utc).isoformat())
    return package, quote, validation


def run(root: Path, run_id: str, *, before_run=None) -> dict:
    import analyst_consensus_refresh as analyst
    package, quote, validation = make_bound(root)
    if before_run:
        before_run(root)
    with mock.patch.object(chain, "ROOT", root), \
         mock.patch.object(canon.FinanceSqlCanonAccess, "dynamic_entitlement_scope", side_effect=AssertionError("second selection")), \
         mock.patch.object(chain, "reserve_provider_calls", side_effect=AssertionError("alert-only budget is zero")), \
         mock.patch.object(analyst, "_build_phase3f_analyst_component_with_authorization", side_effect=AssertionError("weekly analyst invoked")):
        return chain.run_policy_canary(components=("alert_level_freshness",), run_id=run_id,
            alert_quote_snapshot_json=quote, alert_quote_validation_json=validation,
            dynamic_execution=True, recurring_reference_inputs=package, recurring_window="midday")


def production_ledger_state() -> tuple[bool, bool]:
    return (WORKSPACE / ledger.LEDGER_REL).exists(), (WORKSPACE / ledger.RECEIPT_REL).exists()


def test_promoted_run_is_ledgered_under_root(tmp_path: Path) -> None:
    before = production_ledger_state()
    root = tmp_path / "a"
    result = run(root, "recurring-ledger-a1")
    assert result["shared_promotion"]["status"] == "ok"
    entry = result["alert_ledger"]
    assert entry["status"] == "ok" and entry["appended"] >= 2 and entry["verify"]["status"] == "ok"
    records = ledger.read_records(root / ledger.LEDGER_REL)
    assert records[0]["record_type"] == "genesis"
    assert {r["payload"]["ticker"] for r in records[1:]} == {"S000", "S001"}
    assert all(r["payload"]["run_id"] == "recurring-ledger-a1" for r in records[1:])
    assert all(r["payload"]["controller_sha256"] == result["shared_promotion"]["controller_sha256"] for r in records[1:])
    proof = json.loads((root / chain.PHASE3F_POLICY_RUN_ROOT / "recurring-ledger-a1.canary_proof.json").read_text())
    assert proof["alert_ledger"]["status"] == "ok"
    assert json.loads((root / ledger.RECEIPT_REL).read_text(encoding="utf-8"))["run_id"] == "recurring-ledger-a1"
    assert production_ledger_state() == before


def test_ledger_failure_never_changes_run_status(tmp_path: Path) -> None:
    before = production_ledger_state()
    baseline = run(tmp_path / "ok", "recurring-ledger-b0")
    with mock.patch.object(ledger, "record_promoted_run", side_effect=RuntimeError("ledger exploded")):
        failed = run(tmp_path / "boom", "recurring-ledger-b1")
    assert failed["status"] == baseline["status"]
    assert failed["shared_promotion"]["status"] == baseline["shared_promotion"]["status"] == "ok"
    assert failed["alert_ledger"]["status"] == "error"
    assert "RuntimeError: ledger exploded" in failed["alert_ledger"]["errors"][0]
    assert (tmp_path / "boom/tmp/alert-level-freshness-controller.json").is_file()
    assert production_ledger_state() == before


def test_disabled_switch_leaves_run_untouched(tmp_path: Path) -> None:
    root = tmp_path / "d"

    def switch_off(r: Path) -> None:
        (r / ledger.DISABLED_REL).parent.mkdir(parents=True, exist_ok=True)
        (r / ledger.DISABLED_REL).write_text("off\n", encoding="utf-8")
    result = run(root, "recurring-ledger-d1", before_run=switch_off)
    assert result["alert_ledger"]["status"] == "disabled"
    assert not (root / ledger.LEDGER_REL).exists()
