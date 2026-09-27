"""Tests for the append-only recommendation decision ledger (Phase 4 draft).

Run from the scratch root with either::

    PYTHONDONTWRITEBYTECODE=1 python -m unittest -v \
        scripts/test_recommendation_decision_ledger.py

or under pytest on the host. Tests use only TemporaryDirectory roots (the
production sentinel lives in a *separate* TemporaryDirectory outside the
ledger root), import the module relative to their own location (never an
absolute scratch path), and never touch production state.

The production provider allowlist contains no test entries. Tests that need
a test provider run under mock.patch.dict on PROVIDER_MESSAGE_ID_PATTERNS
(started in ChainTest.setUp); production call sites accept no ``providers``
override, and ``check``/``fix_head``/``fix_tail`` pass straight through.
"""
from __future__ import annotations

import hashlib
import inspect
import json
import multiprocessing
import os
import stat
import subprocess
import sys
import threading
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

import recommendation_decision_ledger as ledger

HEX_A = "a" * 64
HEX_B = "b" * 64
HEX_C = "c" * 64
HEX_D = "d" * 64
HEX_E = hashlib.sha256(b"owner-review-artifact").hexdigest()
HEX_R = hashlib.sha256(b"raw-provider-receipt-bytes").hexdigest()

TEST_PROVIDERS = {
    "local-test-provider": r"mid-[A-Za-z0-9][A-Za-z0-9_.:=-]{1,63}",
}


def machine() -> dict:
    return {"origin": "machine", "recorded_by": "funnel-agent"}


def human() -> dict:
    return {"origin": "human", "recorded_by": "randall"}


def provider() -> dict:
    return {"origin": "provider", "recorded_by": "receipt-poller"}


def snapshot(tag: str = "d1") -> dict:
    return {
        "methodology_version": "funnel-v1",
        "sql_pin": "alerts_os_reference_baseline_v1@2026-09-26",
        "controller_sha256": HEX_A,
        "funnel_sha256": HEX_B,
        "ranked_candidates": [
            {"candidate_id": "AAA", "score": 0.81},
            {"candidate_id": "BBB", "score": 0.66},
        ],
        "exclusions": [
            {"candidate_id": "CCC", "reason": "earnings inside window"},
        ],
        "recorded_at_utc": "2026-09-26T19:00:00Z",
        "tag": tag,
    }


def proof(decision_id: str, snapshot_hash: str, reviewed_hash: str,
          provider_name: str = "local-test-provider",
          message_id: str = "mid-stable-0001") -> dict:
    return {
        "provider": provider_name,
        "message_id": message_id,
        "message_sha256": HEX_C,
        "recipient_binding_sha256": HEX_D,
        "decision_id": decision_id,
        "candidate_snapshot_hash": snapshot_hash,
        "reviewed_record_hash": reviewed_hash,
        "receipt_sha256": HEX_R,
    }


def check(root: Path, **kw: Any) -> dict:
    return ledger.verify(root=root, **kw)


def fix_head(root: Path, **kw: Any) -> dict:
    return ledger.repair_head(root=root, **kw)


def fix_tail(root: Path, **kw: Any) -> dict:
    return ledger.repair_torn_tail(root=root, **kw)


def snapshot_ref_of(root: Path, decision_id: str) -> dict:
    records = ledger.read_records(root / ledger.LEDGER_REL)
    snaps = [r for r in records
             if r.get("event_type") == "candidate_snapshot"
             and r.get("decision_id") == decision_id]
    assert snaps, "expected a candidate snapshot"
    return {"seq": snaps[0]["seq"], "record_hash": snaps[0]["record_hash"]}


def review_hash_of(root: Path, decision_id: str) -> str:
    records = ledger.read_records(root / ledger.LEDGER_REL)
    revs = [r for r in records
            if r.get("event_type") == "reviewed"
            and r.get("decision_id") == decision_id]
    assert revs, "expected a reviewed record"
    return str(revs[0]["record_hash"])


def review(root: Path, decision_id: str, event_id: str | None = None,
           reviewer: str = "randall") -> dict:
    return ledger.append_reviewed(
        root=root, decision_id=decision_id,
        event_id=event_id or f"{decision_id}-rev",
        snapshot_ref=snapshot_ref_of(root, decision_id),
        reviewer=reviewer, review_artifact_sha256=HEX_E,
        provenance=human())


def full_receipted_chain(root: Path, decision_id: str = "d1",
                         proof_provider: str = "local-test-provider",
                         proof_mid: str = "mid-stable-0001") -> dict:
    """Snapshot -> reviewed -> send_unconfirmed -> sent_receipted.

    The test provider resolves through the suite-level mock.patch.dict;
    production call sites take no ``providers`` override."""
    ledger.append_candidate_snapshot(
        root=root, decision_id=decision_id, event_id=f"{decision_id}-snap",
        snapshot=snapshot(decision_id), provenance=machine())
    ref = snapshot_ref_of(root, decision_id)
    review(root, decision_id)
    ledger.append_send_unconfirmed(
        root=root, decision_id=decision_id, event_id=f"{decision_id}-unc",
        reason="no provider receipt within window", provenance=machine())
    return ledger.append_sent_receipted(
        root=root, decision_id=decision_id, event_id=f"{decision_id}-sent",
        message_sha256=HEX_C, recipient_binding_sha256=HEX_D,
        send_proof=proof(decision_id, ref["record_hash"],
                         review_hash_of(root, decision_id),
                         provider_name=proof_provider, message_id=proof_mid),
        provenance=provider())


def _mp_worker(root_str: str, worker: int) -> None:
    import sys as _sys
    from pathlib import Path as _Path
    _sys.path.insert(0, str(_Path(__file__).resolve().parent))
    import recommendation_decision_ledger as _ledger

    root = _Path(root_str)
    for j in range(2):
        name = f"mp{worker}-{j}"
        snap = {
            "methodology_version": "funnel-v1",
            "sql_pin": "pin",
            "controller_sha256": "a" * 64,
            "funnel_sha256": "b" * 64,
            "ranked_candidates": [{"candidate_id": "AAA"}],
            "exclusions": [],
            "recorded_at_utc": "2026-09-26T19:00:00Z",
        }
        _ledger.append_candidate_snapshot(
            root=root, decision_id=name, event_id=f"{name}-snap",
            snapshot=snap, provenance={"origin": "machine"})


class ChainTest(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.root = Path(self.tmp.name)
        # Test-provider injection for this suite only, via mock.patch.dict:
        # production call sites take no ``providers`` override (see
        # test_no_providers_override_on_public_apis). Also pin bytecode
        # off so spawned children never write outside temporary roots.
        self._prov = mock.patch.dict(
            ledger.PROVIDER_MESSAGE_ID_PATTERNS, TEST_PROVIDERS)
        self._prov.start()
        self._bytecode_was = os.environ.get("PYTHONDONTWRITEBYTECODE")
        os.environ["PYTHONDONTWRITEBYTECODE"] = "1"

    def _confined_names(self, *sibling_prefixes: str):
        """Snapshot only this isolated root and explicitly targeted siblings."""
        root_names = sorted(
            str(path.relative_to(self.root)) for path in self.root.rglob("*"))
        sibling_names = sorted(
            path.name for path in self.root.parent.iterdir()
            if any(path.name.startswith(prefix) for prefix in sibling_prefixes))
        return root_names, sibling_names

    def tearDown(self):
        self._prov.stop()
        if self._bytecode_was is None:
            os.environ.pop("PYTHONDONTWRITEBYTECODE", None)
        else:
            os.environ["PYTHONDONTWRITEBYTECODE"] = self._bytecode_was
        self.tmp.cleanup()

    def test_valid_full_event_chain(self):
        res = full_receipted_chain(self.root)
        self.assertEqual(res["status"], "ok")
        ledger.append_candidate_snapshot(
            root=self.root, decision_id="d2", event_id="d2-snap",
            snapshot=snapshot("d2"), provenance=machine())
        review(self.root, "d2")
        ledger.append_not_sent(
            root=self.root, decision_id="d2", event_id="d2-drop",
            reason="macro posture disfavored", provenance=human())
        report = check(self.root)
        self.assertEqual(report["status"], "ok")
        self.assertEqual(report["records"], 7)
        seqs = [r["seq"] for r in
                ledger.read_records(self.root / ledger.LEDGER_REL)]
        self.assertEqual(seqs, [1, 2, 3, 4, 5, 6, 7])
        self.assertEqual(report, check(self.root))

    def test_production_allowlist_has_no_test_entries(self):
        self._prov.stop()  # inspect the real production allowlist
        try:
            for name in ledger.PROVIDER_MESSAGE_ID_PATTERNS:
                lowered = name.casefold()
                for token in ("test", "local", "mock", "fake",
                              "stub", "dummy"):
                    self.assertNotIn(token, lowered)
        finally:
            self._prov.start()

    def test_verify_rejects_off_allowlist_provider(self):
        full_receipted_chain(self.root)  # test-provider rows
        self.assertEqual(check(self.root)["status"], "ok")
        self._prov.stop()  # back to the production allowlist
        try:
            prod = ledger.verify(root=self.root)  # production allowlist
            self.assertEqual(prod["status"], "error")
            self.assertTrue(any("allowlist" in e for e in prod["errors"]))
            with self.assertRaises(ValueError):
                ledger.append_sent_receipted(
                    root=self.root, decision_id="d1",
                    event_id="d1-sent-prod",
                    message_sha256=HEX_C, recipient_binding_sha256=HEX_D,
                    send_proof=proof("d1", snapshot_ref_of(
                        self.root, "d1")["record_hash"],
                        review_hash_of(self.root, "d1")),
                    provenance=provider())  # no override exists
        finally:
            self._prov.start()

    def test_forged_looking_allowed_provider_accepted_and_disclosed(self):
        # Well-formed through an allowlisted provider, but every digest is
        # fabricated and nothing was verified: the ledger records the claim.
        ledger.append_candidate_snapshot(
            root=self.root, decision_id="f", event_id="f-snap",
            snapshot=snapshot("f"), provenance=machine())
        ref = snapshot_ref_of(self.root, "f")
        review(self.root, "f")
        forged = proof("f", ref["record_hash"], review_hash_of(self.root, "f"),
                       provider_name="telegram-bot-api", message_id="42")
        forged["message_sha256"] = "1" * 64
        forged["recipient_binding_sha256"] = "2" * 64
        forged["receipt_sha256"] = "3" * 64
        res = ledger.append_sent_receipted(
            root=self.root, decision_id="f", event_id="f-sent",
            message_sha256="1" * 64, recipient_binding_sha256="2" * 64,
            send_proof=forged, provenance=provider())  # production allowlist
        self.assertEqual(res["status"], "ok")
        self.assertEqual(ledger.verify(root=self.root)["status"], "ok")
        # The limit is explicit, not hidden: the docstring says digests and
        # reviewer identity are caller-asserted, unverified claims.
        doc = ledger.__doc__ or ""
        lowered = doc.casefold()
        self.assertIn("caller-asserted", lowered)
        self.assertIn("unverified", lowered)
        self.assertIn("records claims, not proof", lowered)
        self.assertIn("main/owner gate", lowered)

    def test_invalid_transitions(self):
        with self.assertRaises(ValueError):
            ledger.append_reviewed(
                root=self.root, decision_id="x", event_id="x-rev",
                snapshot_ref={"seq": 1, "record_hash": HEX_A},
                reviewer="randall", review_artifact_sha256=HEX_E,
                provenance=human())
        with self.assertRaises(ValueError):
            ledger.append_not_sent(
                root=self.root, decision_id="x", event_id="x-drop",
                reason="too early", provenance=machine())
        with self.assertRaises(ValueError):
            ledger.append_send_unconfirmed(
                root=self.root, decision_id="x", event_id="x-unc",
                reason="too early", provenance=machine())
        with self.assertRaises(ValueError):
            ledger.append_sent_receipted(
                root=self.root, decision_id="x", event_id="x-sent",
                message_sha256=HEX_C, recipient_binding_sha256=HEX_D,
                send_proof=proof("x", HEX_A, HEX_B),
                provenance=provider())
        ledger.append_candidate_snapshot(
            root=self.root, decision_id="y", event_id="y-snap",
            snapshot=snapshot("y"), provenance=machine())
        with self.assertRaises(ValueError):
            ledger.append_send_unconfirmed(
                root=self.root, decision_id="y", event_id="y-unc",
                reason="no review yet", provenance=machine())
        with self.assertRaises(ValueError):
            ledger.append_sent_receipted(
                root=self.root, decision_id="y", event_id="y-sent",
                message_sha256=HEX_C, recipient_binding_sha256=HEX_D,
                send_proof=proof("y", snapshot_ref_of(
                    self.root, "y")["record_hash"], HEX_B),
                provenance=provider())
        full_receipted_chain(self.root, "z")
        with self.assertRaises(ValueError):
            ledger.append_not_sent(
                root=self.root, decision_id="z", event_id="z-late",
                reason="after receipt", provenance=human())
        ledger.append_candidate_snapshot(
            root=self.root, decision_id="w", event_id="w-snap",
            snapshot=snapshot("w"), provenance=machine())
        ledger.append_not_sent(
            root=self.root, decision_id="w", event_id="w-drop",
            reason="not sending", provenance=human())
        with self.assertRaises(ValueError):
            ledger.append_send_unconfirmed(
                root=self.root, decision_id="w", event_id="w-unc",
                reason="after terminal", provenance=machine())
        with self.assertRaises(ValueError):
            ledger.append_candidate_snapshot(
                root=self.root, decision_id="w", event_id="w-snap-2",
                snapshot=snapshot("w"), provenance=machine())
        with self.assertRaises(ValueError):
            review(self.root, "w", event_id="w-rev")

    def test_machine_labels_rejected_for_reviewed_and_sent(self):
        ledger.append_candidate_snapshot(
            root=self.root, decision_id="m", event_id="m-snap",
            snapshot=snapshot("m"), provenance=machine())
        ref = snapshot_ref_of(self.root, "m")
        with self.assertRaises(ValueError):
            ledger.append_reviewed(
                root=self.root, decision_id="m", event_id="m-rev",
                snapshot_ref=ref, reviewer="Clive",
                review_artifact_sha256=HEX_E, provenance=machine())
        review(self.root, "m")
        with self.assertRaises(ValueError):
            ledger.append_sent_receipted(
                root=self.root, decision_id="m", event_id="m-sent",
                message_sha256=HEX_C, recipient_binding_sha256=HEX_D,
                send_proof=proof("m", ref["record_hash"],
                                 review_hash_of(self.root, "m")),
                provenance=machine())
        with self.assertRaises(ValueError):
            ledger.append_sent_receipted(
                root=self.root, decision_id="m", event_id="m-sent",
                message_sha256=HEX_C, recipient_binding_sha256=HEX_D,
                send_proof=proof("m", ref["record_hash"],
                                 review_hash_of(self.root, "m")),
                provenance=human())

    def test_reviewed_requires_evidence_exact_labels_only(self):
        # Exact generic labels are refused; real names -- including ones a
        # substring heuristic would false-reject (Clive, Abbott, Talbot) --
        # are accepted as caller-asserted strings (see trust limit).
        for bad in ("human", "owner", "unknown", "reviewer"):
            with self.subTest(bad):
                with self.assertRaises(ValueError):
                    ledger._validate_reviewer(bad)
        for name in ("randall", "Clive", "Abbott", "Talbot",
                     "funnel-agent", "veritas-main"):
            with self.subTest(name):
                self.assertEqual(ledger._validate_reviewer(name), name)
        ledger.append_candidate_snapshot(
            root=self.root, decision_id="e", event_id="e-snap",
            snapshot=snapshot("e"), provenance=machine())
        ref = snapshot_ref_of(self.root, "e")
        with self.assertRaises(ValueError):
            ledger.append_reviewed(
                root=self.root, decision_id="e", event_id="e-rev-bad",
                snapshot_ref=ref, reviewer="human",
                review_artifact_sha256=HEX_E, provenance=human())
        with self.assertRaises(ValueError):
            ledger.append_reviewed(
                root=self.root, decision_id="e", event_id="e-rev-noart",
                snapshot_ref=ref, reviewer="randall",
                review_artifact_sha256="not-a-digest", provenance=human())
        with self.assertRaises(ValueError):
            ledger.append_reviewed(
                root=self.root, decision_id="e", event_id="e-rev-wrong",
                snapshot_ref={"seq": 99, "record_hash": HEX_A},
                reviewer="randall", review_artifact_sha256=HEX_E,
                provenance=human())
        self.assertEqual(check(self.root)["records"], 1)
        ok = review(self.root, "e", reviewer="Clive")
        self.assertEqual(ok["status"], "ok")

    def test_weak_send_proof_false_greens(self):
        ledger.append_candidate_snapshot(
            root=self.root, decision_id="p", event_id="p-snap",
            snapshot=snapshot("p"), provenance=machine())
        ref = snapshot_ref_of(self.root, "p")
        review(self.root, "p")
        rev_hash = review_hash_of(self.root, "p")
        good = proof("p", ref["record_hash"], rev_hash)
        cases: dict[str, Any] = {
            "missing proof (None)": None,
            "empty proof": {},
            "boolean-only": {"sent": True},
            "delivered boolean": {"delivered": True},
            "cli-returncode-only": {"returncode": 0},
            "free-text-only": {"note": "looks sent to me"},
            "digest-state-only": {"digest": "sent", "delivered": False},
            "missing provider": {**good, "provider": ""},
            "missing receipt digest": {k: v for k, v in good.items()
                                       if k != "receipt_sha256"},
            "malformed receipt digest": {**good, "receipt_sha256": "zz"},
            "missing review binding": {k: v for k, v in good.items()
                                       if k != "reviewed_record_hash"},
            "provider=cli": {**good, "provider": "cli",
                             "message_id": "returncode=0"},
            "provider=digest": {**good, "provider": "digest",
                                "message_id": "sent ok"},
            "cli free-text id": {**good, "message_id": "returncode=0"},
            "exit-code id": {**good, "message_id": "exit 0, delivered"},
            "free-text id": {**good, "message_id": "sent via cli!!"},
            "wrong-format id": {**good, "message_id": "12345"},
            "placeholder id": {**good, "message_id": "pending"},
            "short id": {**good, "message_id": "ab"},
            "non-hex message hash": {**good, "message_sha256": "not-a-hash"},
        }
        for i, (label, weak) in enumerate(cases.items()):
            with self.subTest(label):
                with self.assertRaises(ValueError):
                    ledger.append_sent_receipted(
                        root=self.root, decision_id="p",
                        event_id=f"p-sent-{i}",
                        message_sha256=HEX_C,
                        recipient_binding_sha256=HEX_D,
                        send_proof=weak, provenance=provider())
        report = check(self.root)
        self.assertEqual((report["status"], report["records"]), ("ok", 2))

    def test_binding_mismatches(self):
        ledger.append_candidate_snapshot(
            root=self.root, decision_id="b", event_id="b-snap",
            snapshot=snapshot("b"), provenance=machine())
        ref = snapshot_ref_of(self.root, "b")
        review(self.root, "b")
        rev_hash = review_hash_of(self.root, "b")
        good = proof("b", ref["record_hash"], rev_hash)
        mismatches = {
            "message hash": ({**good, "message_sha256": HEX_A}, HEX_C, HEX_D),
            "recipient binding": ({**good, "recipient_binding_sha256": HEX_A},
                                  HEX_C, HEX_D),
            "decision id": ({**good, "decision_id": "other"}, HEX_C, HEX_D),
            "snapshot hash": ({**good, "candidate_snapshot_hash": HEX_A},
                              HEX_C, HEX_D),
            "review hash": ({**good, "reviewed_record_hash": HEX_A},
                            HEX_C, HEX_D),
        }
        for i, (label, (bad_proof, msg, recip)) in enumerate(
                mismatches.items()):
            with self.subTest(label):
                with self.assertRaises(ValueError):
                    ledger.append_sent_receipted(
                        root=self.root, decision_id="b",
                        event_id=f"b-sent-{i}",
                        message_sha256=msg,
                        recipient_binding_sha256=recip,
                        send_proof=bad_proof, provenance=provider())

    def test_replay_idempotent_conflict_fails(self):
        first = ledger.append_candidate_snapshot(
            root=self.root, decision_id="r", event_id="r-snap",
            snapshot=snapshot("r"), provenance=machine())
        again = ledger.append_candidate_snapshot(
            root=self.root, decision_id="r", event_id="r-snap",
            snapshot=snapshot("r"), provenance=machine())
        self.assertEqual(again["status"], "ok_duplicate_event")
        self.assertEqual(again["appended"], 0)
        self.assertEqual(again["record_hash"], first["record_hash"])
        self.assertEqual(check(self.root)["records"], 1)
        altered = snapshot("r")
        altered["exclusions"] = []
        with self.assertRaises(ValueError):
            ledger.append_candidate_snapshot(
                root=self.root, decision_id="r", event_id="r-snap",
                snapshot=altered, provenance=machine())
        with self.assertRaises(ValueError):
            ledger.append_candidate_snapshot(
                root=self.root, decision_id="other", event_id="r-snap",
                snapshot=snapshot("other"), provenance=machine())

    def test_replay_compare_is_type_strict(self):
        prov: dict[str, Any] = {"origin": "machine", "v": 1}
        ledger.append_candidate_snapshot(
            root=self.root, decision_id="s", event_id="s-snap",
            snapshot=snapshot("s"), provenance=prov)
        # True == 1 in Python, but the canonical bytes differ: conflicting
        # reuse must fail, not report a duplicate no-op.
        strict: dict[str, Any] = {"origin": "machine", "v": True}
        with self.assertRaises(ValueError):
            ledger.append_candidate_snapshot(
                root=self.root, decision_id="s", event_id="s-snap",
                snapshot=snapshot("s"), provenance=strict)
        self.assertEqual(check(self.root)["records"], 1)

    def test_nan_payload_refused(self):
        poisoned = snapshot("n")
        poisoned["ranked_candidates"][0]["score"] = float("nan")
        with self.assertRaises(ValueError):
            ledger.append_candidate_snapshot(
                root=self.root, decision_id="n", event_id="n-snap",
                snapshot=poisoned, provenance=machine())
        self.assertFalse((self.root / ledger.LEDGER_REL).exists())

    def test_payload_and_envelope_tamper(self):
        full_receipted_chain(self.root)
        path = self.root / ledger.LEDGER_REL
        lines = path.read_text(encoding="utf-8").splitlines()
        row = json.loads(lines[0])
        row["payload"]["snapshot"]["exclusions"] = []
        tampered = lines[:]
        tampered[0] = json.dumps(row, sort_keys=True)
        path.write_text("\n".join(tampered) + "\n", encoding="utf-8")
        report = check(self.root)
        self.assertEqual(report["status"], "error")
        self.assertTrue(any("payload_sha256" in e for e in report["errors"]))

    def test_envelope_seq_tamper(self):
        full_receipted_chain(self.root)
        path = self.root / ledger.LEDGER_REL
        lines = path.read_text(encoding="utf-8").splitlines()
        row = json.loads(lines[2])
        row["seq"] = 99
        lines[2] = json.dumps(row, sort_keys=True)
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        report = check(self.root)
        self.assertEqual(report["status"], "error")
        self.assertTrue(any("seq 99" in e for e in report["errors"]))

    def test_envelope_field_injection(self):
        full_receipted_chain(self.root)
        path = self.root / ledger.LEDGER_REL
        lines = path.read_text(encoding="utf-8").splitlines()
        row = json.loads(lines[0])
        row["sent"] = True
        row["delivered"] = True
        row["position_size"] = 100
        row["account_id"] = "123-456"
        row["email"] = "randall@example.com"
        row["record_hash"] = ledger.envelope_hash(row)
        lines[0] = json.dumps(row, sort_keys=True)
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        report = check(self.root)
        self.assertEqual(report["status"], "error")
        self.assertTrue(any("envelope" in e for e in report["errors"]))
        # Payload/envelope decision_id mismatch and bad recorded_at_utc.
        row = json.loads(lines[1])
        row["payload"] = dict(row["payload"])
        row["payload"]["decision_id"] = "someone-else"
        row["recorded_at_utc"] = "not a time"
        row["payload_sha256"] = ledger.sha256_hex(
            ledger.canonical_bytes(row["payload"]))
        row["record_hash"] = ledger.envelope_hash(row)
        lines[1] = json.dumps(row, sort_keys=True)
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        report = check(self.root)
        self.assertEqual(report["status"], "error")
        self.assertTrue(any("decision_id" in e for e in report["errors"]))
        self.assertTrue(any("recorded_at_utc" in e for e in report["errors"]))

    def test_line_delete_and_reorder(self):
        full_receipted_chain(self.root)
        path = self.root / ledger.LEDGER_REL
        lines = path.read_text(encoding="utf-8").splitlines()
        path.write_text("\n".join([lines[0]] + lines[2:]) + "\n",
                        encoding="utf-8")
        report = check(self.root)
        self.assertEqual(report["status"], "error")
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        self.assertEqual(check(self.root)["status"], "ok")
        path.write_text("\n".join([lines[1], lines[0]] + lines[2:]) + "\n",
                        encoding="utf-8")
        report = check(self.root)
        self.assertEqual(report["status"], "error")
        self.assertTrue(any("seq" in e or "prev_record_hash" in e
                            for e in report["errors"]))

    def test_unicode_line_breaks_round_trip(self):
        tricky = snapshot("u")
        tricky["exclusions"] = [{"candidate_id": "X",
                                 "reason": "pasted text and\x85nel"}]
        res = ledger.append_candidate_snapshot(
            root=self.root, decision_id="u", event_id="u-snap",
            snapshot=tricky, provenance=machine())
        self.assertEqual(res["status"], "ok")
        self.assertEqual(check(self.root)["status"], "ok")
        # A later append still works: the ledger is not bricked.
        review(self.root, "u")
        ledger.append_not_sent(
            root=self.root, decision_id="u", event_id="u-drop",
            reason="done", provenance=human())
        report = check(self.root)
        self.assertEqual((report["status"], report["records"]), ("ok", 3))
        stored = ledger.read_records(self.root / ledger.LEDGER_REL)[0]
        reason = stored["payload"]["snapshot"]["exclusions"][0]["reason"]
        for char in (" ", " ", "\x85"):
            self.assertIn(char, reason)
        _stored = ledger.read_records(self.root / ledger.LEDGER_REL)[0]
        self.assertIn(" ", stored["payload"]["snapshot"][
            "exclusions"][0]["reason"])

    def test_verify_rejects_hand_forged_semantics(self):
        ledger.append_candidate_snapshot(
            root=self.root, decision_id="h", event_id="h-snap",
            snapshot=snapshot("h"), provenance=machine())
        records = ledger.read_records(self.root / ledger.LEDGER_REL)
        forged = ledger.build_record(
            seq=2, prev_hash=records[-1]["record_hash"],
            event_type="sent_receipted", decision_id="h",
            event_id="h-forged",
            payload={"decision_id": "h", "provenance": machine()})
        path = self.root / ledger.LEDGER_REL
        with open(path, "ab") as stream:
            stream.write(ledger.canonical_bytes(forged) + b"\n")
        fix_head(self.root)
        report = check(self.root)
        self.assertEqual(report["status"], "error")
        self.assertTrue(any("semantic" in e for e in report["errors"]))

    def test_verify_malformed_input_returns_report(self):
        path = self.root / ledger.LEDGER_REL
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"\xff\xfe\x00bad")
        report = check(self.root)
        self.assertEqual(report["status"], "error")
        self.assertTrue(any("UTF-8" in e for e in report["errors"]))
        path.write_text('{"seq": 1}\n[1,2]\n{"oops": \n', encoding="utf-8")
        report = check(self.root)
        self.assertEqual(report["status"], "error")
        self.assertTrue(any("line 2" in e for e in report["errors"]))
        self.assertTrue(any("line 3" in e for e in report["errors"]))

    def test_non_object_head_returns_error(self):
        full_receipted_chain(self.root)
        head = self.root / ledger.HEAD_REL
        head.write_text("[1, 2]", encoding="utf-8")
        report = check(self.root)  # must not raise
        self.assertEqual(report["status"], "error")
        self.assertTrue(any("head file" in e for e in report["errors"]))
        head.write_text('"str"', encoding="utf-8")
        report = check(self.root)
        self.assertEqual(report["status"], "error")
        # Appends fail closed with ValueError, not AttributeError.
        with self.assertRaises(ValueError):
            ledger.append_candidate_snapshot(
                root=self.root, decision_id="nh", event_id="nh-snap",
                snapshot=snapshot("nh"), provenance=machine())

    def test_head_mismatch(self):
        full_receipted_chain(self.root)
        head = self.root / ledger.HEAD_REL
        state = json.loads(head.read_text(encoding="utf-8"))
        state["record_hash"] = HEX_A
        head.write_text(json.dumps(state), encoding="utf-8")
        report = check(self.root)
        self.assertEqual(report["status"], "error")
        self.assertTrue(any("head file" in e for e in report["errors"]))
        with self.assertRaises(ValueError):
            ledger.append_candidate_snapshot(
                root=self.root, decision_id="blocked", event_id="blocked",
                snapshot=snapshot("blocked"), provenance=machine())

    def test_interrupted_head_update_recovery(self):
        full_receipted_chain(self.root)
        head = self.root / ledger.HEAD_REL
        head.write_text("{torn", encoding="utf-8")
        self.assertEqual(check(self.root)["status"], "error")
        fixed = fix_head(self.root)
        self.assertEqual((fixed["status"], fixed["repaired"]), ("ok", True))
        self.assertEqual(check(self.root)["status"], "ok")
        head.unlink()
        report = check(self.root)
        self.assertEqual(report["status"], "error")
        self.assertTrue(any("head file" in e for e in report["errors"]))
        self.assertEqual(fix_head(self.root)["status"], "ok")
        self.assertEqual(check(self.root)["status"], "ok")
        path = self.root / ledger.LEDGER_REL
        lines = path.read_text(encoding="utf-8").splitlines()
        row = json.loads(lines[0])
        row["payload_sha256"] = HEX_A
        lines[0] = json.dumps(row, sort_keys=True)
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        failed = fix_head(self.root)
        self.assertEqual(failed["status"], "error")
        self.assertFalse(failed["repaired"])

    def test_head_replace_failure_rolls_back(self):
        ledger.append_candidate_snapshot(
            root=self.root, decision_id="k", event_id="k-snap",
            snapshot=snapshot("k"), provenance=machine())
        real_replace = os.replace
        calls = []

        def failing_replace(src, dst, **kwargs):
            calls.append((src, dst))
            raise PermissionError("simulated torn head swap")

        os.replace = failing_replace
        try:
            with self.assertRaises(ledger.LedgerCommitError):
                review(self.root, "k")
        finally:
            os.replace = real_replace
        self.assertTrue(calls)
        records = ledger.read_records(self.root / ledger.LEDGER_REL)
        self.assertEqual(len(records), 1)
        self.assertEqual(check(self.root)["status"], "ok")
        ok = review(self.root, "k")
        self.assertEqual(ok["status"], "ok")
        self.assertEqual(check(self.root)["records"], 2)

    def test_repair_head_honors_rel_args(self):
        full_receipted_chain(self.root)
        res = fix_head(self.root, head_rel="custom/alt.head.json")
        self.assertEqual((res["status"], res["repaired"]), ("ok", True))
        self.assertTrue((self.root / "custom/alt.head.json").is_file())
        report = check(self.root, head_rel="custom/alt.head.json")
        self.assertEqual(report["status"], "ok")
        self.assertEqual(report["records"], 4)

    def test_repair_paths_confined(self):
        full_receipted_chain(self.root)
        outside = self.root.parent / "victim.txt"
        outside.write_text("last line precious\n", encoding="utf-8")
        try:
            bad_tail = fix_tail(self.root, ledger_rel="../victim.txt")
            self.assertEqual(bad_tail["status"], "error")
            self.assertFalse(bad_tail["repaired"])
            bad_head = fix_head(self.root, head_rel="../planted.head.json")
            self.assertEqual(bad_head["status"], "error")
            self.assertFalse(bad_head["repaired"])
            bad_verify = check(self.root, ledger_rel="../victim.txt")
            self.assertEqual(bad_verify["status"], "error")
            self.assertEqual(outside.read_text(encoding="utf-8"),
                             "last line precious\n")
            self.assertFalse((self.root.parent / "planted.head.json").exists())
        finally:
            outside.unlink(missing_ok=True)
            (self.root.parent / "planted.head.json").unlink(missing_ok=True)

    def test_torn_tail_strict(self):
        ledger.append_candidate_snapshot(
            root=self.root, decision_id="t", event_id="t-snap",
            snapshot=snapshot("t"), provenance=machine())
        path = self.root / ledger.LEDGER_REL
        pristine = path.read_bytes()
        # A file ending in newline is never cut, torn or not.
        untouched = fix_tail(self.root)
        self.assertEqual(untouched["repaired"], False)
        self.assertEqual(path.read_bytes(), pristine)
        # Torn tail with a valid prefix: truncate only the tail.
        with open(path, "ab") as stream:
            stream.write(b'{"schema": "veritas.phase4_decision_record')
        self.assertEqual(check(self.root)["status"], "error")
        self.assertEqual(fix_head(self.root)["status"], "error")
        fixed = fix_tail(self.root)
        self.assertEqual((fixed["status"], fixed["repaired"]), ("ok", True))
        self.assertEqual(check(self.root)["records"], 1)
        # A complete final record without trailing newline is not torn.
        raw = path.read_bytes().rstrip(b"\n")
        path.write_bytes(raw)
        complete = fix_tail(self.root)
        self.assertEqual(complete["repaired"], False)
        self.assertEqual(path.read_bytes(), raw)
        self.assertEqual(check(self.root)["status"], "ok")
        # Torn tail on top of mid-chain tamper: error, file byte-identical.
        lines = path.read_text(encoding="utf-8").splitlines()
        row = json.loads(lines[0])
        row["payload_sha256"] = HEX_A
        lines[0] = json.dumps(row, sort_keys=True)
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        with open(path, "ab") as stream:
            stream.write(b'{"torn": ')
        before = path.read_bytes()
        failed = fix_tail(self.root)
        self.assertEqual(failed["status"], "error")
        self.assertFalse(failed["repaired"])
        self.assertEqual(path.read_bytes(), before)
        # Undecodable byte inside an earlier record: never cut record 3.
        path.write_bytes(pristine)  # restore the valid one-record chain
        self.assertEqual(check(self.root)["status"], "ok")
        ledger.append_candidate_snapshot(
            root=self.root, decision_id="t2", event_id="t2-snap",
            snapshot=snapshot("t2"), provenance=machine())
        raw = path.read_bytes()
        cut = raw.find(b'"ranked_candidates"')
        damaged = raw[:cut] + b"\xff" + raw[cut:]
        if damaged.endswith(b"\n"):
            damaged = damaged[:-1] + b'{"torn": '
        path.write_bytes(damaged)
        before = path.read_bytes()
        failed = fix_tail(self.root)
        self.assertFalse(failed["repaired"])
        self.assertEqual(path.read_bytes(), before)

    def test_failed_append_advances_nothing(self):
        before_records = ledger.read_records(self.root / ledger.LEDGER_REL)
        head_before = ((self.root / ledger.HEAD_REL).read_bytes()
                       if (self.root / ledger.HEAD_REL).is_file() else None)
        with self.assertRaises(ValueError):
            ledger.append_reviewed(
                root=self.root, decision_id="ghost", event_id="ghost-rev",
                snapshot_ref={"seq": 1, "record_hash": HEX_A},
                reviewer="randall", review_artifact_sha256=HEX_E,
                provenance=human())
        self.assertEqual(ledger.read_records(self.root / ledger.LEDGER_REL),
                         before_records)
        head_after = ((self.root / ledger.HEAD_REL).read_bytes()
                      if (self.root / ledger.HEAD_REL).is_file() else None)
        self.assertEqual(head_after, head_before)

    def test_lock_timeout_writes_nothing(self):
        holder_ready = threading.Event()
        release = threading.Event()

        def holder():
            with ledger._file_lock(ledger._lock_path(self.root),
                                   timeout=10.0):
                holder_ready.set()
                release.wait(timeout=15.0)

        thread = threading.Thread(target=holder)
        thread.start()
        self.assertTrue(holder_ready.wait(timeout=10.0))
        try:
            with self.assertRaises(ledger.LedgerLockTimeout):
                ledger.append_candidate_snapshot(
                    root=self.root, decision_id="lt", event_id="lt-snap",
                    snapshot=snapshot("lt"), provenance=machine(),
                    lock_timeout=0.5)
        finally:
            release.set()
            thread.join()
        self.assertFalse((self.root / ledger.LEDGER_REL).exists())
        self.assertFalse((self.root / ledger.HEAD_REL).exists())

    def test_concurrent_append_threads_serialize(self):
        errors: list = []
        results: list = []

        def worker(i: int):
            try:
                results.append(ledger.append_candidate_snapshot(
                    root=self.root, decision_id=f"c{i}",
                    event_id=f"c{i}-snap", snapshot=snapshot(f"c{i}"),
                    provenance=machine()))
            except Exception as exc:  # noqa: BLE001 -- collected, asserted
                errors.append(exc)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(errors, [])
        self.assertEqual(len(results), 8)
        report = check(self.root)
        self.assertEqual((report["status"], report["records"]), ("ok", 8))
        seqs = sorted(r["seq"] for r in
                      ledger.read_records(self.root / ledger.LEDGER_REL))
        self.assertEqual(seqs, list(range(1, 9)))

    def test_concurrent_append_processes_serialize(self):
        procs = [multiprocessing.Process(target=_mp_worker,
                                         args=(str(self.root), w))
                 for w in range(4)]
        try:
            for p in procs:
                p.start()
            for p in procs:
                p.join(timeout=120)
            for p in procs:
                if p.is_alive():
                    p.terminate()
                    p.join(timeout=10)
            self.assertEqual([p.exitcode for p in procs], [0, 0, 0, 0])
        finally:
            for p in procs:
                if p.is_alive():
                    p.terminate()
        report = check(self.root)
        self.assertEqual((report["status"], report["records"]), ("ok", 8))
        seqs = sorted(r["seq"] for r in
                      ledger.read_records(self.root / ledger.LEDGER_REL))
        self.assertEqual(seqs, list(range(1, 9)))

    def test_forbidden_field_recursive_scan(self):
        nested = snapshot("f")
        nested["ranked_candidates"][0]["sizing"] = {"weight": 0.5}
        with self.assertRaises(ValueError):
            ledger.append_candidate_snapshot(
                root=self.root, decision_id="f", event_id="f-snap",
                snapshot=nested, provenance=machine())
        variants = ("position_size", "order_id", "target_weight",
                    "cash_balance", "expected_return", "fill_price",
                    "Position ", "POSITION", "orderId", "targetWeight",
                    "allocation", "Account", "CASH", "execution",
                    "holdings", "fill", "pnl", "performance",
                    "quantity", "shares", "tranche", "brokerage",
                    "weight", "return", "size", "position")
        for i, bad_key in enumerate(variants):
            with self.subTest(bad_key):
                poisoned = snapshot(bad_key)
                poisoned["exclusions"] = [{"candidate_id": "X",
                                           "reason": "ok",
                                           bad_key: "1"}]
                with self.assertRaises(ValueError):
                    ledger.append_candidate_snapshot(
                        root=self.root, decision_id=f"f{i}",
                        event_id=f"f{i}-snap", snapshot=poisoned,
                        provenance=machine())
        shortcuts = ({"delivered": True}, {"delivered": "true"},
                     {"sent": True}, {"sent": 1}, {"was_sent": True},
                     {"delivery_status": "delivered"})
        for i, extra in enumerate(shortcuts):
            with self.subTest(sorted(extra)[0]):
                poisoned = snapshot("g")
                poisoned["exclusions"] = [{"candidate_id": "X",
                                           "reason": "ok", **extra}]
                with self.assertRaises(ValueError):
                    ledger.append_candidate_snapshot(
                        root=self.root, decision_id=f"g{i}",
                        event_id=f"g{i}-snap", snapshot=poisoned,
                        provenance=machine())
        raw_recipients = ({"to": "someone"}, {"recipient": "someone"},
                          {"username": "@r"}, {"chat_id": "123"},
                          {"email": "a@b.c"}, {"phone": "555"},
                          {"recipient_name": "R"})
        for i, extra in enumerate(raw_recipients):
            with self.subTest(sorted(extra)[0]):
                poisoned = snapshot("h")
                poisoned["exclusions"] = [{"candidate_id": "X",
                                           "reason": "ok", **extra}]
                with self.assertRaises(ValueError):
                    ledger.append_candidate_snapshot(
                        root=self.root, decision_id=f"h{i}",
                        event_id=f"h{i}-snap", snapshot=poisoned,
                        provenance=machine())
        poisoned = snapshot("t")
        poisoned["exclusions"] = [{"candidate_id": "X", "reason": "ok",
                                   "extra": ({"position": 1},)}]
        with self.assertRaises(ValueError):
            ledger.append_candidate_snapshot(
                root=self.root, decision_id="tu", event_id="tu-snap",
                snapshot=poisoned, provenance=machine())

    def test_scan_residual_variants(self):
        tricky_keys = ("chatId", "tgChatId", "to_addr", "sizes",
                       "positionsize", "POSITIONSIZE", "executions",
                       " position", "ｐｏｓｉｔｉｏｎ", "order\u200b_id")
        for i, bad_key in enumerate(tricky_keys):
            with self.subTest(repr(bad_key)):
                poisoned = snapshot("v")
                poisoned["exclusions"] = [{"candidate_id": "X",
                                           "reason": "ok", bad_key: "1"}]
                with self.assertRaises(ValueError):
                    ledger.append_candidate_snapshot(
                        root=self.root, decision_id=f"v{i}",
                        event_id=f"v{i}-snap", snapshot=poisoned,
                        provenance=machine())
        # The digest exemption applies only to real digests: a raw address
        # under the exempt key name is still refused.
        poisoned = snapshot("w")
        poisoned["exclusions"] = [{"candidate_id": "X", "reason": "ok",
                                   "recipient_binding_sha256":
                                   "randall@example.com"}]
        with self.assertRaises(ValueError):
            ledger.append_candidate_snapshot(
                root=self.root, decision_id="w0", event_id="w0-snap",
                snapshot=poisoned, provenance=machine())

    def test_redirected_root_containment_and_sentinel(self):
        with TemporaryDirectory() as prod_dir:
            live = Path(prod_dir) / "production-sentinel"
            live.write_bytes(b"production bytes - must never be touched")
            mtime_before = live.stat().st_mtime_ns
            mode_before = stat.S_IMODE(live.stat().st_mode)
            sub = self.root / "redirected"
            full_receipted_chain(sub)
            written = [p for p in sub.rglob("*") if p.is_file()]
            self.assertTrue(written)
            for p in written:
                self.assertIn(str(sub), str(p))
            stray = [p for p in self.root.rglob("*.jsonl")
                     if sub not in p.parents]
            self.assertEqual(stray, [])
            self.assertEqual(live.read_bytes(),
                             b"production bytes - must never be touched")
            self.assertEqual(live.stat().st_mtime_ns, mtime_before)
            self.assertEqual(stat.S_IMODE(live.stat().st_mode), mode_before)

    def test_cli_is_read_only_and_requires_root(self):
        full_receipted_chain(self.root, proof_provider="telegram-bot-api",
                             proof_mid="987654321")
        script = str(Path(ledger.__file__))
        env = dict(os.environ)
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        ok = subprocess.run(
            [sys.executable, "-B", script, "--root", str(self.root)],
            capture_output=True, text=True, check=False,
            env=env, cwd=str(self.root))
        self.assertEqual(ok.returncode, 0, ok.stderr)
        self.assertEqual(json.loads(ok.stdout)["status"], "ok")
        missing = subprocess.run(
            [sys.executable, "-B", script], capture_output=True, text=True,
            check=False, env=env, cwd=str(self.root))
        self.assertNotEqual(missing.returncode, 0)
        # POSIX-rooted, drive-relative, parent-reference, empty, dot, and
        # absolute-root escapes are all refused with code 2 on every
        # platform.
        for bad in ("/etc/passwd", "D:x", "../x", "", ".",
                    str(self.root)):
            with self.subTest(bad):
                escaped = subprocess.run(
                    [sys.executable, "-B", script, "--root",
                     str(self.root), "--ledger", bad],
                    capture_output=True, text=True, check=False,
                    env=env, cwd=str(self.root))
                self.assertEqual(escaped.returncode, 2)
                self.assertEqual(json.loads(escaped.stdout)["status"],
                                 "error")
        source = Path(ledger.__file__).read_text(encoding="utf-8")
        main_src = source.split("def main(", 1)[1]
        self.assertNotIn("append_", main_src)
        self.assertNotIn("repair_", main_src)

    def test_cli_creates_nothing(self):
        script = str(Path(ledger.__file__))
        env = dict(os.environ)
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        with TemporaryDirectory() as bare:
            # A bare root is non-green unless explicitly allowed.
            proc = subprocess.run(
                [sys.executable, "-B", script, "--root", bare],
                capture_output=True, text=True, check=False,
                env=env, cwd=bare)
            self.assertNotEqual(proc.returncode, 0)
            self.assertEqual(json.loads(proc.stdout)["status"], "error")
            allowed = subprocess.run(
                [sys.executable, "-B", script, "--root", bare,
                 "--allow-empty"],
                capture_output=True, text=True, check=False,
                env=env, cwd=bare)
            self.assertEqual(allowed.returncode, 0, allowed.stderr)
            self.assertEqual(json.loads(allowed.stdout)["status"], "ok")
            self.assertEqual(
                sorted(p.name for p in Path(bare).rglob("*")), [])

    def test_no_providers_override_on_public_apis(self):
        for func in (ledger.append_sent_receipted, ledger.verify,
                     ledger.repair_head, ledger.repair_torn_tail):
            with self.subTest(func.__name__):
                self.assertNotIn("providers",
                                 inspect.signature(func).parameters)
        # A production caller cannot smuggle an override kwarg in.
        with self.assertRaises(TypeError):
            ledger.append_sent_receipted(
                root=self.root, decision_id="d1", event_id="d1-sent-x",
                message_sha256=HEX_C, recipient_binding_sha256=HEX_D,
                send_proof=proof("d1", HEX_A, HEX_B),
                provenance=provider(),
                providers=TEST_PROVIDERS)  # type: ignore[call-arg]

    def test_contained_accepts_only_strict_children(self):
        good = ledger._contained(self.root, ledger.LEDGER_REL)
        self.assertTrue(str(good).startswith(str(self.root) + os.sep))
        bad = ["", " ", ".", "./", ".\\",
               "/etc/passwd", "D:x", "\\\\host\\share",
               "../x", "a/../../x", "..", str(self.root)]
        parent_before = self._confined_names(self.root.name, "x")
        for rel in bad:
            with self.subTest(repr(rel)):
                with self.assertRaises(ValueError):
                    ledger._contained(self.root, rel)
        # Refusals touch nothing next to the root: no .tmp/.lock strays.
        self.assertEqual(
            self._confined_names(self.root.name, "x"), parent_before)

    def test_confined_refusals_leave_parent_and_head_alone(self):
        full_receipted_chain(self.root)
        head = self.root / ledger.HEAD_REL
        head_before = head.read_bytes()
        outside = self.root.parent / "victim2.txt"
        outside.write_text("untouched\n", encoding="utf-8")
        parent_before = self._confined_names(self.root.name, outside.name)
        try:
            for rel in ("../victim2.txt", "", "."):
                with self.subTest(rel=rel):
                    for call in (ledger.verify, ledger.repair_head,
                                 ledger.repair_torn_tail):
                        res = call(root=self.root, ledger_rel=rel)
                        self.assertEqual(res["status"], "error")
                        self.assertFalse(res.get("repaired", False))
                    res = ledger.repair_head(root=self.root, head_rel=rel)
                    self.assertEqual(res["status"], "error")
                    self.assertFalse(res["repaired"])
            self.assertEqual(outside.read_text(encoding="utf-8"),
                             "untouched\n")
            self.assertEqual(head.read_bytes(), head_before)
            self.assertEqual(
                self._confined_names(self.root.name, outside.name),
                parent_before)
        finally:
            outside.unlink(missing_ok=True)

    def test_cli_confinement_refusals(self):
        full_receipted_chain(self.root, proof_provider="telegram-bot-api",
                             proof_mid="555666777")
        script = str(Path(ledger.__file__))
        env = dict(os.environ)
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        head_before = (self.root / ledger.HEAD_REL).read_bytes()
        parent_before = self._confined_names(self.root.name, "x")
        for bad in ("", ".", "../x", "/etc/passwd", "D:x"):
            with self.subTest(repr(bad)):
                proc = subprocess.run(
                    [sys.executable, "-B", script, "--root",
                     str(self.root), "--ledger", bad],
                    capture_output=True, text=True, check=False,
                    env=env, cwd=str(self.root))
                self.assertEqual(proc.returncode, 2)
                self.assertEqual(json.loads(proc.stdout)["status"],
                                 "error")
        self.assertEqual((self.root / ledger.HEAD_REL).read_bytes(),
                         head_before)
        self.assertEqual(
            self._confined_names(self.root.name, "x"), parent_before)

    def test_append_inserts_separator_for_complete_no_newline_tail(self):
        ledger.append_candidate_snapshot(
            root=self.root, decision_id="n1", event_id="n1-snap",
            snapshot=snapshot("n1"), provenance=machine())
        path = self.root / ledger.LEDGER_REL
        raw = path.read_bytes()
        self.assertTrue(raw.endswith(b"\n"))
        path.write_bytes(raw.rstrip(b"\n"))  # complete, no newline
        res = review(self.root, "n1")
        self.assertEqual(res["status"], "ok")
        rows = [ln for ln in path.read_bytes().split(b"\n") if ln.strip()]
        self.assertEqual(len(rows), 2)
        report = check(self.root)
        self.assertEqual((report["status"], report["records"]),
                         ("ok", 2))

    def test_append_refuses_torn_tail_and_advances_nothing(self):
        ledger.append_candidate_snapshot(
            root=self.root, decision_id="n2", event_id="n2-snap",
            snapshot=snapshot("n2"), provenance=machine())
        path = self.root / ledger.LEDGER_REL
        before = path.read_bytes()
        head = self.root / ledger.HEAD_REL
        head_before = head.read_bytes()
        torn = b'{"schema": "veritas.phase4_decision_record'
        with open(path, "ab") as stream:
            stream.write(torn)
        with self.assertRaises(ValueError):
            review(self.root, "n2")
        self.assertEqual(path.read_bytes(), before + torn)
        self.assertEqual(head.read_bytes(), head_before)

    def test_field_scan_accepts_legit_keys_rejects_exact(self):
        legit = snapshot("legit")
        legit["exclusions"] = [{"candidate_id": "X", "reason": "ok",
                                "price_to_book": 1.2,
                                "debt_to_equity": 0.4,
                                "debt_to_assets": 0.2,
                                "ev_to_ebitda": 7.5,
                                "days_to_earnings": 21,
                                "time_to_catalyst": 14,
                                "sector_composition": "mid",
                                "weighted_score": 0.9,
                                "shareholder_yield": 0.03,
                                "rank": 1}]
        res = ledger.append_candidate_snapshot(
            root=self.root, decision_id="legit", event_id="legit-snap",
            snapshot=legit, provenance=machine())
        self.assertEqual(res["status"], "ok")
        for i, bad_key in enumerate(("order", "position", "share",
                                     "account", "weight", "recipient",
                                     "positionsize", "to_addr",
                                     "to")):
            with self.subTest(bad_key):
                poisoned = snapshot(f"scan{i}")
                poisoned["exclusions"] = [{"candidate_id": "X",
                                           "reason": "ok", bad_key: "1"}]
                with self.assertRaises(ValueError):
                    ledger.append_candidate_snapshot(
                        root=self.root, decision_id=f"scan{i}",
                        event_id=f"scan{i}-snap", snapshot=poisoned,
                        provenance=machine())

    def test_field_scan_rejects_compound_and_to_evasions(self):
        compounds = ("accountnumber", "accountbalance", "accountid",
                     "targetweight", "weighting", "ordersize", "orderid",
                     "ordertype", "positionsize", "positionid",
                     "sharesize", "sharecount", "marketshare",
                     "recipientid")
        for i, bad_key in enumerate(compounds):
            with self.subTest(bad_key=bad_key):
                poisoned = snapshot(f"compound{i}")
                poisoned["exclusions"] = [{"candidate_id": "X",
                                           "reason": "ok", bad_key: "1"}]
                with self.assertRaises(ValueError):
                    ledger.append_candidate_snapshot(
                        root=self.root, decision_id=f"compound{i}",
                        event_id=f"compound{i}-snap", snapshot=poisoned,
                        provenance=machine())
        # False values prove these are refused as raw recipient keys, not
        # merely by the independent truthy delivery-shortcut guard.
        for i, bad_key in enumerate(("send_to_user", "deliver_to_number",
                                     "to_", "to.", "to_addr", "ship_to")):
            with self.subTest(bad_key=bad_key):
                poisoned = snapshot(f"to{i}")
                poisoned["exclusions"] = [{"candidate_id": "X",
                                           "reason": "ok", bad_key: False}]
                with self.assertRaises(ValueError):
                    ledger.append_candidate_snapshot(
                        root=self.root, decision_id=f"to{i}",
                        event_id=f"to{i}-snap", snapshot=poisoned,
                        provenance=machine())

    def test_canonical_hex_rejects_uppercase(self):
        self.assertFalse(ledger._is_hex64("A" * 64))
        self.assertTrue(ledger._is_hex64("a" * 64))
        ledger.append_candidate_snapshot(
            root=self.root, decision_id="u1", event_id="u1-snap",
            snapshot=snapshot("u1"), provenance=machine())
        with self.assertRaises(ValueError):
            ledger.append_reviewed(
                root=self.root, decision_id="u1", event_id="u1-rev",
                snapshot_ref=snapshot_ref_of(self.root, "u1"),
                reviewer="randall", review_artifact_sha256="E" * 64,
                provenance=human())


class ImportHygieneTest(unittest.TestCase):
    def test_import_has_no_side_effects(self):
        script = ("import sys; sys.path.insert(0, %r); "
                  "import recommendation_decision_ledger as m; "
                  "print(m.SCHEMA)" % str(Path(ledger.__file__).parent))
        with TemporaryDirectory() as cwd:
            env = dict(os.environ)
            env["PYTHONDONTWRITEBYTECODE"] = "1"
            proc = subprocess.run(
                [sys.executable, "-B", "-c", script], capture_output=True,
                text=True, cwd=cwd, check=False, env=env)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertIn(ledger.SCHEMA, proc.stdout)
            # Glob while the temp dir still exists: a module that wrote
            # files into cwd at import time would be caught here.
            leftovers = sorted(Path(cwd).rglob("*"))
            self.assertEqual(leftovers, [])

    def test_source_has_no_live_integration(self):
        source = Path(ledger.__file__).read_text(encoding="utf-8")
        banned = [
            "recommendation_funnel", "finance_alert_os_digest",
            "alert_event_ledger", "thesis_record_validator",
            "urlopen", "requests", "urllib", "socket", "smtplib",
            "subprocess", "shutil", "sqlite3",
        ]
        for token in banned:
            with self.subTest(token):
                self.assertNotIn(token, source)
        # Check the code after the module docstring (not a slice that can
        # never fail): no import-time workspace root, no default write path.
        code = source.split('"""', 2)[2]
        self.assertNotIn("Path(__file__)", code)
        self.assertNotIn("parents[", code)
        self.assertNotIn("resolve().parent", code)
        top_level_paths = [
            line for line in code.splitlines()
            if line and not line[0].isspace()
            and ("Path(" in line or "open(" in line)
            and line.startswith(("ROOT", "BASE", "STATE", "LEDGER",
                                 "HEAD", "_"))
            and "=" in line and "def " not in line and "import" not in line
        ]
        self.assertEqual(top_level_paths, [])

    def test_stdlib_only_and_compact(self):
        source = Path(ledger.__file__).read_text(encoding="utf-8")
        self.assertNotIn("openclaw", source.casefold())
        self.assertLess(len(source.encode("utf-8")), 70_000)

    def test_trust_limit_stated(self):
        source = Path(ledger.__file__).read_text(encoding="utf-8")
        docstring = source.split('"""', 2)[1]
        lowered = docstring.casefold()
        self.assertIn("caller-asserted", lowered)
        self.assertIn("unverified", lowered)
        self.assertNotIn("fabricating bound evidence artifacts", docstring)


class HashPropertiesTest(unittest.TestCase):
    def test_canonical_hash_stable_across_key_order(self):
        a = {"z": 1, "a": [3, 2, {"y": "x"}]}
        b = {"a": [3, 2, {"y": "x"}], "z": 1}
        self.assertEqual(ledger.canonical_bytes(a), ledger.canonical_bytes(b))
        self.assertEqual(ledger.sha256_hex(ledger.canonical_bytes(a)),
                         hashlib.sha256(ledger.canonical_bytes(b)).hexdigest())

    def test_canonical_rejects_nan(self):
        with self.assertRaises(ValueError):
            ledger.canonical_bytes({"x": float("nan")})


if __name__ == "__main__":
    unittest.main()
