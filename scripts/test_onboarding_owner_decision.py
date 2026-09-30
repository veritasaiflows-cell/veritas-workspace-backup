"""Tests for onboarding owner decisions; all written records use temp roots."""
from __future__ import annotations

import datetime as dt
import hashlib
import importlib.util
import json
import sys
from pathlib import Path
from unittest import mock

import pytest


PATH = Path(__file__).resolve().parent / "onboarding_owner_decision.py"
spec = importlib.util.spec_from_file_location("onboarding_owner_decision_under_test", PATH)
assert spec and spec.loader
od = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = od
spec.loader.exec_module(od)

NOW = dt.datetime(2026, 9, 29, 18, tzinfo=dt.timezone.utc)
SHA = "ab" * 32
DID = "p4-bac-insert-20260929"


def record(**overrides):
    doc = {
        "schema": od.ONBOARDING_SCHEMA, "decision_id": DID, "decision": "approved",
        "ticker": "BAC", "mode": "insert", "band_packet_sha256": SHA,
        "as_of": "2026-09-26", "granted_by": "Randall",
        "channel": "Telegram direct", "message_ref": "msg 12000",
        "grant_text": "Approve this BAC band", "recorded_by": "Main",
        "granted_at": (NOW - dt.timedelta(hours=1)).isoformat(),
        "expires_at": (NOW + dt.timedelta(days=7)).isoformat(),
    }
    doc.update(overrides)
    return doc


def request(**overrides):
    value = {"ticker": "BAC", "mode": "insert", "band_packet_sha256": SHA,
             "as_of": "2026-09-26"}
    value.update(overrides)
    return value


def write_cutover(root, covers):
    path = root / od._tier.CUTOVER_REL
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"id": "phase4-tier-cutover", "active": True,
                                "covers": covers, "granted_by": "Randall",
                                "granted_at": NOW.isoformat(),
                                "grant_text": "Approve component cutover"}), encoding="utf-8")


def test_round_trip_and_digest(tmp_path):
    path = od.write_record(tmp_path, record())
    loaded, sha = od.load_decision(tmp_path, DID)
    assert loaded == record()
    assert sha == hashlib.sha256(path.read_bytes()).hexdigest()
    assert path.parent == (tmp_path / od.ONBOARDING_DECISIONS_REL).resolve()
    assert od.decision_digest(loaded) == od.decision_digest(dict(reversed(list(loaded.items()))))
    od.bind(loaded, request(), NOW)


@pytest.mark.parametrize("overrides,reason", [
    ({"schema": "other"}, "onboarding_decision_schema_invalid"),
    ({"decision_id": "p4-other-decision"}, "onboarding_decision_id_mismatch"),
    ({"decision": "pending"}, "onboarding_decision_not_approved"),
    ({"ticker": "bac"}, "onboarding_decision_ticker_invalid"),
    ({"ticker": "TOOLONGTICKER"}, "onboarding_decision_ticker_invalid"),
    ({"mode": "delete"}, "onboarding_decision_mode_invalid"),
    ({"band_packet_sha256": "AB" * 32}, "onboarding_decision_packet_sha_invalid"),
    ({"band_packet_sha256": "abc"}, "onboarding_decision_packet_sha_invalid"),
    ({"as_of": "2026-02-30"}, "onboarding_decision_as_of_invalid"),
    ({"as_of": "2026-9-26"}, "onboarding_decision_as_of_invalid"),
    ({"granted_at": "2026-09-29T17:00:00"}, "onboarding_decision_validity_window_invalid"),
    ({"expires_at": (NOW + dt.timedelta(days=15)).isoformat()},
     "onboarding_decision_validity_window_invalid"),
    ({"expires_at": (NOW - dt.timedelta(days=1)).isoformat()},
     "onboarding_decision_validity_window_invalid"),
])
def test_validation_refusals(overrides, reason):
    with pytest.raises(od.DecisionRefusal, match=reason):
        od.validate_record(record(**overrides), DID)


@pytest.mark.parametrize("field", od.REQUIRED_TEXT)
def test_required_text(field):
    with pytest.raises(od.DecisionRefusal,
                       match=f"onboarding_decision_missing:{field}:"):
        od.validate_record(record(**{field: " "}), DID)


@pytest.mark.parametrize("field,value", [
    ("ticker", "AAPL"), ("mode", "refresh"),
    ("band_packet_sha256", "cd" * 32), ("as_of", "2026-09-27"),
])
def test_binding_mismatch(field, value):
    with pytest.raises(od.DecisionRefusal,
                       match=f"onboarding_decision_binding_mismatch:{DID}:{field}"):
        od.bind(record(), request(**{field: value}), NOW)


def test_time_boundaries():
    with pytest.raises(od.DecisionRefusal, match="not_yet_valid"):
        od.bind(record(), request(), NOW - dt.timedelta(days=1))
    with pytest.raises(od.DecisionRefusal, match="expired"):
        od.bind(record(), request(), NOW + dt.timedelta(days=7))


def test_exact_fourteen_day_window_and_path_escape(tmp_path):
    doc = record(granted_at=NOW.isoformat(),
                 expires_at=(NOW + dt.timedelta(days=14)).isoformat())
    path = od.write_record(tmp_path, doc)
    loaded, _ = od.load_decision(tmp_path, DID)
    assert path.is_file() and loaded == doc
    od.bind(loaded, request(), NOW)

    original_resolve = Path.resolve

    def redirected_resolve(self, *args, **kwargs):
        if self.name == f"{DID}.json":
            return original_resolve(tmp_path / "escaped.json", *args, **kwargs)
        return original_resolve(self, *args, **kwargs)

    with mock.patch.object(Path, "resolve", redirected_resolve):
        with pytest.raises(od.DecisionRefusal,
                           match=f"onboarding_decision_id_path_escape:{DID}"):
            od.decision_path(tmp_path, DID)


def test_missing_overwrite_and_path_traversal(tmp_path):
    with pytest.raises(od.DecisionRefusal, match="record_missing"):
        od.load_decision(tmp_path, DID)
    od.write_record(tmp_path, record())
    with pytest.raises(od.DecisionRefusal, match="record_exists"):
        od.write_record(tmp_path, record(grant_text="different"))
    for bad_id in ("../escape", "UPPER-case", "a", "x/y/z1234", ""):
        with pytest.raises(od.DecisionRefusal, match="decision_id_invalid"):
            od.decision_path(tmp_path, bad_id)


def test_cutover_is_component_specific(tmp_path):
    with pytest.raises(od.DecisionRefusal, match="cutover_not_approved"):
        od.cutover_gate(tmp_path, od.COMPONENT)
    write_cutover(tmp_path, ["tier_membership_writer"])
    with pytest.raises(od.DecisionRefusal, match="cutover_does_not_cover"):
        od.cutover_gate(tmp_path, od.COMPONENT)
    write_cutover(tmp_path, [od.COMPONENT])
    assert od.cutover_gate(tmp_path, od.COMPONENT)["active"] is True


def test_cli_record_check_and_max_window(tmp_path, capsys):
    argv = ["record", "--root", str(tmp_path), "--decision-id", DID,
            "--ticker", "bac", "--mode", "insert", "--band-packet-sha256", SHA,
            "--as-of", "2026-09-26", "--channel", "direct", "--message-ref", "m1",
            "--grant-text", "Approved", "--granted-at", NOW.isoformat()]
    assert od.main(argv + ["--valid-days", "15"]) == 2
    assert not (tmp_path / od.ONBOARDING_DECISIONS_REL).exists()
    capsys.readouterr()
    assert od.main(argv) == 0
    capsys.readouterr()
    assert od.main(["check", "--root", str(tmp_path), DID]) == 0
    output = json.loads(capsys.readouterr().out)
    assert output["mode"] == "insert" and output["cutover_gate"]["status"] == "blocked"
