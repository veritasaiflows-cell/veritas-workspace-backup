#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "cyber_security_daily_audit_cron_runner.py"
AUDIT_SCRIPT = ROOT / "scripts" / "cyber_security_daily_audit.py"


def load_module():
    spec = importlib.util.spec_from_file_location("cyber_security_daily_audit_cron_runner", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_audit_module():
    spec = importlib.util.spec_from_file_location("cyber_security_daily_audit", AUDIT_SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_prefilter_reuses_only_fresh_noncritical_security_audit() -> None:
    module = load_module()
    now = datetime.now(timezone.utc).replace(microsecond=0)
    signature = {"hash": "abc123", "source_count": 1, "sources": []}
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        proof = tmp / "proof.json"
        audit = tmp / "audit.json"
        proof.write_text(
            json.dumps(
                {
                    "generated_at_utc": now.isoformat().replace("+00:00", "Z"),
                    "proof_status": "ok",
                    "errors": [],
                    "input_signature": signature,
                }
            ),
            encoding="utf-8",
        )
        audit.write_text(
            json.dumps(
                {
                    "generated_at_utc": now.isoformat().replace("+00:00", "Z"),
                    "status": "warning",
                    "stop_line": False,
                }
            ),
            encoding="utf-8",
        )

        decision = module.prefilter_decision(proof, audit, signature, now=now)

    assert decision["can_reuse_existing_audit"] is True
    assert decision["reason"] == "unchanged_inputs_and_fresh_security_proof"


def test_prefilter_refreshes_on_critical_or_stale_audit() -> None:
    module = load_module()
    now = datetime.now(timezone.utc).replace(microsecond=0)
    signature = {"hash": "abc123", "source_count": 1, "sources": []}
    stale = now - timedelta(hours=module.PREFILTER_UNCHANGED_WARNING_MAX_AGE_HOURS + 1)
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        proof = tmp / "proof.json"
        audit = tmp / "audit.json"
        proof.write_text(
            json.dumps(
                {
                    "generated_at_utc": now.isoformat().replace("+00:00", "Z"),
                    "proof_status": "ok",
                    "errors": [],
                    "input_signature": signature,
                }
            ),
            encoding="utf-8",
        )
        audit.write_text(
            json.dumps(
                {
                    "generated_at_utc": now.isoformat().replace("+00:00", "Z"),
                    "status": "critical",
                    "stop_line": True,
                }
            ),
            encoding="utf-8",
        )
        critical = module.prefilter_decision(proof, audit, signature, now=now)

        audit.write_text(
            json.dumps(
                {
                    "generated_at_utc": stale.isoformat().replace("+00:00", "Z"),
                    "status": "warning",
                    "stop_line": False,
                }
            ),
            encoding="utf-8",
        )
        stale_decision = module.prefilter_decision(proof, audit, signature, now=now)

    assert critical["can_reuse_existing_audit"] is False
    assert critical["reason"] == "previous_audit_stop_line_or_critical"
    assert stale_decision["can_reuse_existing_audit"] is False
    assert stale_decision["reason"] == "previous_audit_not_fresh"


def test_prefilter_reuses_unchanged_warning_audit_inside_extended_ttl() -> None:
    module = load_module()
    now = datetime.now(timezone.utc).replace(microsecond=0)
    signature = {"hash": "abc123", "source_count": 1, "sources": []}
    reusable_warning = now - timedelta(hours=module.PREFILTER_MAX_AGE_HOURS + 6)
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        proof = tmp / "proof.json"
        audit = tmp / "audit.json"
        proof.write_text(
            json.dumps(
                {
                    "generated_at_utc": reusable_warning.isoformat().replace("+00:00", "Z"),
                    "proof_status": "ok",
                    "errors": [],
                    "input_signature": signature,
                }
            ),
            encoding="utf-8",
        )
        audit.write_text(
            json.dumps(
                {
                    "generated_at_utc": reusable_warning.isoformat().replace("+00:00", "Z"),
                    "status": "warning",
                    "stop_line": False,
                }
            ),
            encoding="utf-8",
        )

        decision = module.prefilter_decision(proof, audit, signature, now=now)

    assert decision["can_reuse_existing_audit"] is True
    assert decision["reason"] == "unchanged_inputs_and_reusable_warning_security_proof"


def test_prefilter_reuses_when_only_cron_wrapper_source_changed() -> None:
    module = load_module()
    now = datetime.now(timezone.utc).replace(microsecond=0)
    previous_signature = {
        "hash": "old-wrapper-hash",
        "sources": [
            {"label": "producer:cyber_security_daily_audit_cron_runner", "sha256": "old"},
            {"label": "producer:cyber_security_daily_audit", "sha256": "audit"},
            {"label": "workspace_boundary_check", "sha256": "boundary"},
        ],
    }
    current_signature = {
        "hash": "new-wrapper-hash",
        "sources": [
            {"label": "producer:cyber_security_daily_audit_cron_runner", "sha256": "new"},
            {"label": "producer:cyber_security_daily_audit", "sha256": "audit"},
            {"label": "workspace_boundary_check", "sha256": "boundary"},
        ],
    }
    reusable_warning = now - timedelta(hours=module.PREFILTER_MAX_AGE_HOURS + 6)
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        proof = tmp / "proof.json"
        audit = tmp / "audit.json"
        proof.write_text(
            json.dumps(
                {
                    "generated_at_utc": reusable_warning.isoformat().replace("+00:00", "Z"),
                    "proof_status": "ok",
                    "errors": [],
                    "input_signature": previous_signature,
                }
            ),
            encoding="utf-8",
        )
        audit.write_text(
            json.dumps(
                {
                    "generated_at_utc": reusable_warning.isoformat().replace("+00:00", "Z"),
                    "status": "warning",
                    "stop_line": False,
                }
            ),
            encoding="utf-8",
        )

        decision = module.prefilter_decision(proof, audit, current_signature, now=now)

    assert decision["source_unchanged"] is True
    assert decision["can_reuse_existing_audit"] is True
    assert decision["previous_input_hash"] != decision["current_input_hash"]
    assert decision["previous_audit_input_hash_without_runner"] == decision["current_audit_input_hash_without_runner"]


def test_audit_command_timeout_terminates_process_tree() -> None:
    module = load_audit_module()
    started = time.monotonic()
    result = module.run_command([sys.executable, "-c", "import time; time.sleep(60)"], 1)
    elapsed = time.monotonic() - started

    assert result["timed_out"] is True
    assert result["returncode"] is None
    assert elapsed < 15


def test_runner_timeout_writes_warning_proof_when_prior_audit_is_fresh_and_noncritical() -> None:
    module = load_module()
    now = datetime.now(timezone.utc).replace(microsecond=0)
    original = {
        "AUDIT_JSON": module.AUDIT_JSON,
        "PROOF_JSON": module.PROOF_JSON,
        "build_input_signature": module.build_input_signature,
        "prefilter_decision": module.prefilter_decision,
        "run_audit_script": module.run_audit_script,
        "argv": sys.argv,
    }
    try:
        with tempfile.TemporaryDirectory(dir=ROOT / "tmp") as tmpdir:
            tmp = Path(tmpdir)
            module.AUDIT_JSON = tmp / "audit.json"
            module.PROOF_JSON = tmp / "proof.json"
            module.AUDIT_JSON.write_text(
                json.dumps(
                    {
                        "generated_at_utc": now.isoformat().replace("+00:00", "Z"),
                        "status": "warning",
                        "stop_line": False,
                        "operator_action_required": True,
                    }
                ),
                encoding="utf-8",
            )
            module.build_input_signature = lambda: {"hash": "test"}
            module.prefilter_decision = lambda *args, **kwargs: {"can_reuse_existing_audit": False}
            module.run_audit_script = lambda: {
                "returncode": None,
                "stdout": "",
                "stderr": "timeout",
                "timed_out": True,
            }
            sys.argv = ["cyber_security_daily_audit_cron_runner.py"]

            assert module.main() == 0
            proof = json.loads(module.PROOF_JSON.read_text(encoding="utf-8"))
    finally:
        module.AUDIT_JSON = original["AUDIT_JSON"]
        module.PROOF_JSON = original["PROOF_JSON"]
        module.build_input_signature = original["build_input_signature"]
        module.prefilter_decision = original["prefilter_decision"]
        module.run_audit_script = original["run_audit_script"]
        sys.argv = original["argv"]

    assert proof["status"] == "warning"
    assert proof["proof_status"] == "warning"
    assert proof["operator_action"] == "MAIN_SESSION_REQUIRED"
    assert proof["audit_timed_out"] is True


def main() -> int:
    test_prefilter_reuses_only_fresh_noncritical_security_audit()
    test_prefilter_refreshes_on_critical_or_stale_audit()
    test_prefilter_reuses_unchanged_warning_audit_inside_extended_ttl()
    test_prefilter_reuses_when_only_cron_wrapper_source_changed()
    test_audit_command_timeout_terminates_process_tree()
    test_runner_timeout_writes_warning_proof_when_prior_audit_is_fresh_and_noncritical()
    print("cyber_security_daily_audit_cron_runner_tests_passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
