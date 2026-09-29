"""Tests for scripts/tier_owner_decision.py (temp roots only)."""
from __future__ import annotations

import datetime as dt
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

import tier_owner_decision as tod  # noqa: E402

LIVE_ROOT = Path(__file__).resolve().parent.parent
NOW = dt.datetime(2026, 9, 28, 18, 0, tzinfo=dt.timezone.utc)
SHA = "ab" * 32


def record(**overrides) -> dict:
    base = {
        "schema": tod.DECISION_SCHEMA, "decision_id": "p4-xyz-cb-20260928", "decision": "approved",
        "ticker": "XYZ", "from_tier": "C", "to_tier": "B", "card_id": "card_XYZ",
        "proposal_packet_sha256": SHA, "granted_by": "Randall", "channel": "Telegram direct",
        "message_ref": "msg 12000", "grant_text": "Approve XYZ C->B", "recorded_by": "Main",
        "granted_at": "2026-09-28T10:00:00-07:00", "expires_at": "2026-10-05T10:00:00-07:00",
    }
    base.update(overrides)
    return base


def entry(**overrides) -> dict:
    base = {"ticker": "XYZ", "from_tier": "C", "to_tier": "B", "card_id": "card_XYZ",
            "proposal_packet_sha256": SHA}
    base.update(overrides)
    return base


def cutover(**overrides) -> dict:
    base = {"id": tod.CUTOVER_ID, "active": True, "covers": ["tier_membership_writer"],
            "granted_by": "Randall", "granted_at": "2026-10-16T09:00:00-07:00", "grant_text": "cut over"}
    base.update(overrides)
    return base


def write_cutover(root: Path, doc) -> None:
    p = root / tod.CUTOVER_REL
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(doc), encoding="utf-8")


# --- cutover gate --------------------------------------------------------------------

def test_live_workspace_has_no_cutover_approval():
    with pytest.raises(tod.DecisionRefusal, match="cutover_not_approved"):
        tod.cutover_gate(LIVE_ROOT)


def test_cutover_gate_absent_refuses(tmp_path):
    with pytest.raises(tod.DecisionRefusal, match="cutover_not_approved"):
        tod.cutover_gate(tmp_path)


@pytest.mark.parametrize("doc,reason", [
    (cutover(active=False), "cutover_not_active"),
    (cutover(active="true"), "cutover_not_active"),
    (cutover(id="band-renewal-option-b"), "wrong_id"),
    (cutover(covers=["reference_level_onboarding_writer"]), "does_not_cover"),
    (cutover(covers="tier_membership_writer"), "does_not_cover"),
    (cutover(grant_text=""), "missing:grant_text"),
    ([], "wrong_id"),
])
def test_cutover_gate_refusals(tmp_path, doc, reason):
    write_cutover(tmp_path, doc)
    with pytest.raises(tod.DecisionRefusal, match=reason):
        tod.cutover_gate(tmp_path)


def test_cutover_gate_active(tmp_path):
    write_cutover(tmp_path, cutover())
    assert tod.cutover_gate(tmp_path)["active"] is True


# --- record validation -----------------------------------------------------------------

def test_valid_record_round_trip(tmp_path):
    path = tod.write_record(tmp_path, record())
    loaded, sha = tod.load_decision(tmp_path, "p4-xyz-cb-20260928")
    assert loaded["ticker"] == "XYZ" and len(sha) == 64
    assert path.parent == (tmp_path / tod.DECISIONS_REL).resolve()


def test_records_are_never_overwritten(tmp_path):
    tod.write_record(tmp_path, record())
    with pytest.raises(tod.DecisionRefusal, match="exists"):
        tod.write_record(tmp_path, record(grant_text="changed"))


@pytest.mark.parametrize("bad_id", ["../escape", "UPPER-case-id", "a", "x/y/z1234", ""])
def test_decision_id_shape_enforced(tmp_path, bad_id):
    with pytest.raises(tod.DecisionRefusal, match="decision_id_invalid"):
        tod.decision_path(tmp_path, bad_id)


@pytest.mark.parametrize("overrides,reason", [
    ({"decision": "pending"}, "not_approved"),
    ({"from_tier": "C", "to_tier": "A"}, "transition_invalid"),
    ({"proposal_packet_sha256": "abc"}, "packet_sha_invalid"),
    ({"card_id": ""}, "card_id_missing"),
    ({"message_ref": " "}, "missing:message_ref"),
    ({"granted_at": "2026-09-28T10:00:00"}, "needs_timezone"),
    ({"expires_at": "2026-10-20T10:00:00-07:00"}, "validity_window"),
    ({"expires_at": "2026-09-28T09:00:00-07:00"}, "validity_window"),
    ({"schema": "other"}, "schema_invalid"),
])
def test_record_validation(overrides, reason):
    with pytest.raises(tod.DecisionRefusal, match=reason):
        tod.validate_record(record(**overrides), "p4-xyz-cb-20260928")


def test_record_id_must_match_filename(tmp_path):
    tod.write_record(tmp_path, record())
    path = tod.decision_path(tmp_path, "p4-xyz-cb-20260928")
    doc = json.loads(path.read_text(encoding="utf-8"))
    doc["decision_id"] = "p4-other-20260928"
    path.write_text(json.dumps(doc), encoding="utf-8")
    with pytest.raises(tod.DecisionRefusal, match="decision_id_mismatch"):
        tod.load_decision(tmp_path, "p4-xyz-cb-20260928")


def test_missing_record_refuses(tmp_path):
    with pytest.raises(tod.DecisionRefusal, match="missing"):
        tod.load_decision(tmp_path, "p4-nothing-here")


# --- binding --------------------------------------------------------------------------

def test_bind_exact_match_passes():
    tod.bind(record(), entry(), NOW)


@pytest.mark.parametrize("field,value", [
    ("ticker", "ABC"), ("from_tier", "B"), ("to_tier", "C"),
    ("card_id", "card_OTHER"), ("proposal_packet_sha256", "cd" * 32),
])
def test_bind_mismatch_refuses(field, value):
    with pytest.raises(tod.DecisionRefusal, match=f"binding_mismatch:.*:{field}"):
        tod.bind(record(), entry(**{field: value}), NOW)


def test_bind_expired_and_not_yet_valid():
    with pytest.raises(tod.DecisionRefusal, match="expired"):
        tod.bind(record(), entry(), dt.datetime(2026, 10, 6, tzinfo=dt.timezone.utc))
    with pytest.raises(tod.DecisionRefusal, match="not_yet_valid"):
        tod.bind(record(), entry(), dt.datetime(2026, 9, 27, tzinfo=dt.timezone.utc))


# --- CLI ------------------------------------------------------------------------------

def test_cli_record_and_check(tmp_path, capsys):
    rc = tod.main(["record", "--root", str(tmp_path), "--decision-id", "p4-xyz-cb-20260928",
                   "--ticker", "xyz", "--from-tier", "c", "--to-tier", "b", "--card-id", "card_XYZ",
                   "--proposal-packet-sha256", SHA, "--channel", "Telegram direct",
                   "--message-ref", "msg 12000", "--grant-text", "Approve XYZ",
                   "--granted-at", "2026-09-28T10:00:00-07:00"])
    assert rc == 0
    capsys.readouterr()
    rc = tod.main(["check", "--root", str(tmp_path), "--decision-id", "p4-xyz-cb-20260928"])
    out = json.loads(capsys.readouterr().out)
    assert rc == 0 and out["transition"] == "C->B"
    assert out["cutover_gate"]["status"] == "blocked"


def test_cli_record_rejects_c_to_a(tmp_path, capsys):
    rc = tod.main(["record", "--root", str(tmp_path), "--decision-id", "p4-xyz-ca-20260928",
                   "--ticker", "XYZ", "--from-tier", "C", "--to-tier", "A", "--card-id", "c",
                   "--proposal-packet-sha256", SHA, "--channel", "t", "--message-ref", "m",
                   "--grant-text", "g", "--granted-at", "2026-09-28T10:00:00-07:00"])
    assert rc == 2
    assert not (tmp_path / tod.DECISIONS_REL).exists() or not any((tmp_path / tod.DECISIONS_REL).iterdir())
