#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

import finance_refresh_chain_state_reconcile as reconcile  # noqa: E402


def expect(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def fixture_state() -> dict:
    return {
        "window": "sunday",
        "owner": "scripts/run_finance_refresh_chain.py",
        "started_at_utc": "2026-08-09T03:21:57Z",
        "completed_at_utc": "",
        "status": "running",
        "exit_code": None,
        "recovery": {"triggered": False, "active": False, "reason": "", "failed_step": None},
        "steps": [
            {"index": 1, "script": "one.py", "command": "one.py", "status": "ok", "started_at_utc": "2026-08-09T03:21:57Z", "completed_at_utc": "2026-08-09T03:21:58Z", "exit_code": 0, "duration_seconds": 1.0},
            {"index": 2, "script": "two.py", "command": "two.py", "status": "running", "started_at_utc": "2026-08-09T03:21:58Z", "completed_at_utc": "", "exit_code": None, "duration_seconds": None},
            {"index": 3, "script": "three.py", "command": "three.py", "status": "pending", "started_at_utc": "", "completed_at_utc": "", "exit_code": None, "duration_seconds": None},
        ],
    }


def write_fixture(path: Path) -> bytes:
    raw = json.dumps(fixture_state(), indent=2).encode("utf-8")
    path.write_bytes(raw)
    return raw


def clear_probe() -> dict:
    return {"status": "clear", "matched_process_count": 0, "processes": []}


def test_dry_run_is_non_mutating(errors: list[str]) -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        state = root / "run-chain-sunday.json"
        log = root / "run-chain-sunday.jsonl"
        proof = root / "proof.json"
        backup = root / "state" / "backups"
        before = write_fixture(state)
        log_before = b'{"event":"chain_started"}\n'
        log.write_bytes(log_before)
        result, code = reconcile.reconcile(
            apply=False, write=True, validate=True, state_path=state, log_path=log,
            proof_path=proof, backup_root=backup, process_probe=clear_probe,
        )
        expect(code == 0, f"dry run should pass: {result}", errors)
        expect(result["status"] == "ready_to_reconcile", "dry run should report ready", errors)
        expect(state.read_bytes() == before, "dry run must not edit state", errors)
        expect(log.read_bytes() == log_before, "dry run must not edit log", errors)
        expect(not backup.exists(), "dry run must not create backup", errors)


def test_apply_creates_exact_backup_and_terminal_failed_state(errors: list[str]) -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        state = root / "run-chain-sunday.json"
        log = root / "run-chain-sunday.jsonl"
        proof = root / "proof.json"
        backup = root / "state" / "backups"
        before = write_fixture(state)
        log_before = b'{"event":"chain_started"}\n'
        log.write_bytes(log_before)
        result, code = reconcile.reconcile(
            apply=True, write=True, validate=True, state_path=state, log_path=log,
            proof_path=proof, backup_root=backup, process_probe=clear_probe,
        )
        expect(code == 0, f"apply should pass: {result}", errors)
        expect(result["status"] == "reconciled", "apply should report reconciled", errors)
        updated = json.loads(state.read_text(encoding="utf-8"))
        expect(updated["status"] == "failed", "state must become terminal failed", errors)
        expect(updated["exit_code"] == 130, "state must preserve interrupted exit code", errors)
        expect(not any(step.get("status") == "running" for step in updated["steps"]), "state must not retain a running step", errors)
        interrupted = [step for step in updated["steps"] if step.get("interruption_reason") == reconcile.INTERRUPTION_REASON]
        expect(len(interrupted) == 1 and interrupted[0].get("status") == "failed", "running step must become failed/interrupted", errors)
        backup_dir = Path(result["backup_dir"])
        expect((backup_dir / state.name).read_bytes() == before, "state backup must be byte exact", errors)
        expect((backup_dir / log.name).read_bytes() == log_before, "log backup must be byte exact", errors)
        expect(b"chain_interruption_reconciled" in log.read_bytes(), "append-only reconciliation event required", errors)
        expect(json.loads(proof.read_text(encoding="utf-8"))["status"] == "reconciled", "proof must record reconciliation", errors)


def test_rollback_restores_exact_original_pair(errors: list[str]) -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        state = root / "run-chain-sunday.json"
        log = root / "run-chain-sunday.jsonl"
        proof = root / "proof.json"
        backup = root / "state" / "backups"
        before = write_fixture(state)
        log_before = b'{"event":"chain_started"}\n'
        log.write_bytes(log_before)
        applied, code = reconcile.reconcile(
            apply=True, write=True, validate=True, state_path=state, log_path=log,
            proof_path=proof, backup_root=backup, process_probe=clear_probe,
        )
        expect(code == 0, f"setup apply should pass: {applied}", errors)
        rolled, rollback_code = reconcile.rollback(
            backup_dir=Path(applied["backup_dir"]), write=True, state_path=state,
            log_path=log, proof_path=proof, backup_root=backup,
        )
        expect(rollback_code == 0, f"rollback should pass: {rolled}", errors)
        expect(rolled["status"] == "rolled_back", "rollback should report rolled_back", errors)
        expect(state.read_bytes() == before, "rollback must restore exact state", errors)
        expect(log.read_bytes() == log_before, "rollback must restore exact log", errors)


def test_active_process_blocks_apply(errors: list[str]) -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        state = root / "run-chain-sunday.json"
        log = root / "run-chain-sunday.jsonl"
        proof = root / "proof.json"
        backup = root / "state" / "backups"
        before = write_fixture(state)
        log.write_bytes(b"")
        result, code = reconcile.reconcile(
            apply=True, write=True, validate=True, state_path=state, log_path=log,
            proof_path=proof, backup_root=backup,
            process_probe=lambda: {"status": "active", "matched_process_count": 1, "processes": [{"ProcessId": 1}]},
        )
        expect(code == 2 and result["status"] == "blocked", "active process must block apply", errors)
        expect(state.read_bytes() == before, "blocked apply must leave state unchanged", errors)
        expect(not backup.exists(), "blocked apply must not make a backup", errors)


def main() -> int:
    errors: list[str] = []
    test_dry_run_is_non_mutating(errors)
    test_apply_creates_exact_backup_and_terminal_failed_state(errors)
    test_rollback_restores_exact_original_pair(errors)
    test_active_process_blocks_apply(errors)
    if errors:
        for error in errors:
            print(f"FAIL: {error}")
        return 1
    print("ok: finance_refresh_chain_state_reconcile tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
