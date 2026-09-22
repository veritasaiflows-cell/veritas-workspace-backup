"""Unit tests for the G6 hermetic full-chain PACKET script.

All subprocess/pytest invocations are mocked; the real hermetic suite is
never executed from these unit tests.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import g6_hermetic_full_chain_packet as pkt


def _ok_proc():
    return SimpleNamespace(returncode=0, stdout="14 passed", stderr="")


def _fail_proc():
    return SimpleNamespace(returncode=1, stdout="13 passed, 1 failed", stderr="FAILED x")


def test_schema_and_out_path_constants():
    assert pkt.SCHEMA == "veritas.phase3.g6_hermetic_full_chain_packet.v1"
    assert pkt.PACKAGE_LIFETIME_SECONDS == 600
    assert pkt.G6_COMPLETE is False
    assert pkt.NEXT_GATE == "bounded_real_run"
    assert str(pkt.OUT_PATH).replace("\\", "/").endswith(
        "tmp/phase3-main-only-20260905/g6-hermetic-20260907/"
        "g6-hermetic-full-chain-packet.json"
    )


def test_declared_classes_cover_exactly_five_spec_classes():
    assert set(pkt.CLASSES) == {"success", "failure", "overflow", "debt", "cancellation"}
    assert tuple(pkt.EXPECTED_CLASSES) == (
        "success",
        "failure",
        "overflow",
        "debt",
        "cancellation",
    )
    assert len(pkt.all_nodeids()) == 14
    assert "scripts/test_phase3g_debt_scope.py::DebtScopeTest::test_debt_label_never_confers_readiness" in pkt.all_nodeids()
    assert "scripts/test_phase3g_coherent_reference_read.py::test_guard_sql_is_actually_interrupted" in pkt.all_nodeids()


def test_build_packet_ok_shape():
    packet = pkt.build_packet(0, "14 passed", "")
    assert packet["schema"] == pkt.SCHEMA
    assert packet["status"] == "ok"
    assert packet["package_lifetime_seconds"] == 600
    assert packet["g6_complete"] is False
    assert packet["next_gate"] == "bounded_real_run"
    assert packet["authority_boundary"]
    assert set(packet["classes"]) == set(pkt.EXPECTED_CLASSES)
    assert packet["validation"]["pytest_returncode"] == 0
    assert packet["validation"]["all_passed"] is True
    assert pkt.validate_packet(packet) == []


def test_build_packet_blocked_on_pytest_failure():
    packet = pkt.build_packet(1, "1 failed", "FAILED x")
    assert packet["status"] == "blocked"
    assert all(v["status"] == "failed" for v in packet["classes"].values())
    errors = pkt.validate_packet(packet)
    assert any("pytest nonzero" in e for e in errors)


def test_validate_packet_missing_class():
    packet = pkt.build_packet(0, "ok", "")
    del packet["classes"]["debt"]
    errors = pkt.validate_packet(packet)
    assert "class missing: debt" in errors


def test_run_pytest_uses_no_cacheprovider_cwd_and_timeout():
    with mock.patch.object(
        pkt.subprocess, "run", return_value=_ok_proc()
    ) as run_mock:
        pkt.run_pytest(["a::b"])
    (cmd,), kwargs = run_mock.call_args
    assert cmd[:6] == [sys.executable, "-B", "-m", "pytest", "-q", "-p"]
    assert cmd[6] == "no:cacheprovider"
    assert cmd[7:] == ["a::b"]
    assert kwargs["cwd"] == pkt.ROOT
    assert kwargs["timeout"] == 180


def test_main_write_and_validate_ok_mocked(tmp_path):
    out = tmp_path / "sub" / "packet.json"
    with mock.patch.object(pkt.subprocess, "run", return_value=_ok_proc()):
        rc = pkt.main(["--write", "--validate", "--out", str(out)])
    assert rc == 0
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["schema"] == pkt.SCHEMA
    assert data["status"] == "ok"
    assert pkt.validate_packet(data) == []


def test_main_validate_fails_returns_1_mocked(tmp_path, capsys):
    out = tmp_path / "packet.json"
    with mock.patch.object(pkt.subprocess, "run", return_value=_fail_proc()):
        rc = pkt.main(["--write", "--validate", "--out", str(out)])
    assert rc == 1
    assert out.exists()
    assert "BLOCKED" in capsys.readouterr().err


def test_main_timeout_is_blocked_mocked(tmp_path):
    def _boom(*a, **k):
        raise subprocess.TimeoutExpired(cmd="pytest", timeout=180)

    out = tmp_path / "packet.json"
    with mock.patch.object(pkt.subprocess, "run", side_effect=_boom):
        rc = pkt.main(["--write", "--validate", "--out", str(out)])
    assert rc == 1
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["status"] == "blocked"
    assert data["validation"]["pytest_returncode"] == 124


def test_unit_tests_never_touch_real_subprocess():
    with mock.patch.object(
        pkt.subprocess, "run", side_effect=AssertionError("must stay mocked")
    ):
        with pytest.raises(AssertionError):
            pkt.run_pytest(["x"])


def test_canonicalize_quote_crlf_bytes_pass_strict_contract():
    import phase3g_dynamic_execution as dyn
    from phase3f_external_canary_approval import canonical_json_bytes

    obj = {"status": "ok", "n": 1}
    raw = json.dumps(obj, indent=2).replace("\n", "\r\n").encode("utf-8")
    out = dyn.canonicalize_quote_evidence_bytes(raw, maximum_bytes=4096)
    assert b"\r" not in out
    assert out == canonical_json_bytes(json.loads(out.decode("utf-8")))
