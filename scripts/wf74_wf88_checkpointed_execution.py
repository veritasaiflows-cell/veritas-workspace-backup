#!/usr/bin/env python3
"""Run WF74 -> WF88 as a checkpointed review-only execution chain.

This runner records resumable checkpoints around existing workflow producers.
It does not add apply authority, mutate cron schedules, delete/archive files,
or change finance/account/execution state.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STATE_DIR = ROOT / "state" / "workflow-checkpoints"
DEFAULT_DB = STATE_DIR / "wf74-wf88-checkpoints.sqlite"
DEFAULT_OUT = ROOT / "tmp" / "wf74-wf88-checkpointed-execution.json"
SCHEMA = "veritas.wf74_wf88_checkpointed_execution.v0"
WORKFLOW_ID = "WF74-WF88"

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "checkpoint_runner_only": True,
    "runs_existing_producers": True,
    "auto_apply_allowed": False,
    "skill_application_allowed": False,
    "delete_archive_or_move_allowed": False,
    "cron_schedule_mutation_allowed": False,
    "config_auth_runtime_mutation_allowed": False,
    "sql_or_source_mutation_allowed": False,
    "canonical_note_mutation_allowed": False,
    "portfolio_mutation_allowed": False,
    "cash_sizing_risk_mutation_allowed": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "customer_or_external_output_allowed": False,
    "model_training_claim_allowed": False,
    "raw_prompt_or_tool_capture_allowed": False,
    "owner_approval_inferred": False,
}


@dataclass(frozen=True)
class Step:
    step_id: str
    command: list[str]
    expected_outputs: list[str]
    input_paths: list[str]
    timeout_seconds: int = 300


def default_steps() -> list[Step]:
    py = sys.executable
    return [
        Step(
            "wf74_improvement_opportunity_queue",
            [py, "scripts/wf74_improvement_opportunity_queue.py", "--write", "--validate"],
            ["tmp/wf74-improvement-opportunity-queue.json"],
            [
                "tmp/coding-outcome-ledger-current.json",
                "tmp/otel-ops-control.json",
                "tmp/pm-control-packet.json",
            ],
        ),
        Step(
            "wf74_autonomy_work_router",
            [py, "scripts/wf74_autonomy_work_router.py", "--write", "--validate"],
            ["tmp/wf74-autonomy-work-router.json"],
            ["tmp/wf74-improvement-opportunity-queue.json", "tmp/improvement-ledger-current.json"],
        ),
        Step(
            "wf74_auto_patch_proposer",
            [py, "scripts/wf74_auto_patch_proposer.py", "--write", "--validate"],
            ["tmp/wf74-auto-patch-proposer.json"],
            ["tmp/wf74-improvement-opportunity-queue.json", "tmp/wf74-reflection-to-proposal-autopilot.json"],
        ),
        Step(
            "wf74_decision_docket",
            [py, "scripts/wf74_decision_docket.py", "--write", "--write-md", "--validate"],
            ["tmp/wf74-decision-docket.json", "tmp/wf74-decision-docket.md"],
            [
                "tmp/wf74-improvement-opportunity-queue.json",
                "tmp/wf74-autonomy-work-router.json",
                "tmp/wf74-auto-patch-proposer.json",
            ],
        ),
        Step(
            "wf74_learning_loop_eval_harness",
            [py, "scripts/wf74_learning_loop_eval_harness.py", "--write", "--validate"],
            ["tmp/wf74-learning-loop-eval-harness.json"],
            ["data/wf74-learning-loop-evals/cases.json"],
        ),
        Step(
            "token_efficiency_scorecard",
            [py, "scripts/token_efficiency_scorecard.py", "--write", "--write-md", "--validate"],
            ["tmp/token-efficiency-scorecard.json", "tmp/token-efficiency-scorecard.md"],
            ["tmp/token-usage-ledger-current.json", "tmp/token-budget-status.json"],
        ),
        Step(
            "implementation_token_attribution_bridge",
            [py, "scripts/implementation_token_attribution_bridge.py", "--write", "--write-md", "--validate"],
            ["tmp/implementation-token-attribution-bridge.json", "tmp/implementation-token-attribution-bridge.md"],
            ["state/concurrent-lane-register.json", "tmp/token-usage-ledger-current.json"],
        ),
        Step(
            "wf88_os2_control_seed",
            [py, "scripts/wf88_os2_control_packet.py", "--write", "--write-md", "--validate"],
            ["tmp/wf88-os2-control-packet.json", "tmp/wf88-os2-control-packet.md"],
            ["tmp/wf74-decision-docket.json", "tmp/implementation-token-attribution-bridge.json"],
        ),
        Step(
            "wf88_wiki_synthesis_packet",
            [py, "scripts/wf88_wiki_synthesis_packet.py", "--write", "--write-md", "--validate"],
            ["tmp/wf88-wiki-synthesis-packet.json", "tmp/wf88-wiki-synthesis-packet.md"],
            [
                "tmp/wf88-os2-control-packet.json",
                "tmp/wf74-decision-docket.json",
                "tmp/token-efficiency-scorecard.json",
            ],
        ),
        Step(
            "wf88_os2_control_final",
            [py, "scripts/wf88_os2_control_packet.py", "--write", "--write-md", "--validate"],
            ["tmp/wf88-os2-control-packet.json", "tmp/wf88-os2-control-packet.md"],
            ["tmp/wf88-wiki-synthesis-packet.json", "tmp/wf74-decision-docket.json"],
        ),
    ]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def atomic_write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as handle:
        handle.write(encoded)
        tmp_path = Path(handle.name)
    tmp_path.replace(path)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def file_digest(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"path": rel(ROOT, path), "present": False}
    data = path.read_bytes()
    return {
        "path": rel(ROOT, path),
        "present": True,
        "sha256": sha256_bytes(data),
        "size_bytes": len(data),
        "mtime_ns": path.stat().st_mtime_ns,
    }


def hash_payload(payload: Any) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def tail(text: str, limit: int = 4000) -> str:
    if len(text) <= limit:
        return text
    return text[-limit:]


def open_db(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def ensure_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS runs (
          run_id TEXT PRIMARY KEY,
          workflow_id TEXT NOT NULL,
          schema TEXT NOT NULL,
          status TEXT NOT NULL,
          created_at_utc TEXT NOT NULL,
          updated_at_utc TEXT NOT NULL,
          started_at_utc TEXT,
          completed_at_utc TEXT,
          current_step TEXT,
          stop_after TEXT,
          authority_boundary_json TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS step_runs (
          run_id TEXT NOT NULL REFERENCES runs(run_id) ON DELETE CASCADE,
          step_id TEXT NOT NULL,
          position INTEGER NOT NULL,
          status TEXT NOT NULL,
          command_json TEXT NOT NULL,
          command_text TEXT NOT NULL,
          expected_outputs_json TEXT NOT NULL,
          input_digest_json TEXT NOT NULL,
          input_hash TEXT NOT NULL,
          output_digest_json TEXT,
          output_hash TEXT,
          started_at_utc TEXT,
          completed_at_utc TEXT,
          duration_seconds REAL,
          returncode INTEGER,
          stdout_tail TEXT,
          stderr_tail TEXT,
          error TEXT,
          PRIMARY KEY(run_id, step_id)
        );
        CREATE INDEX IF NOT EXISTS idx_step_runs_run_position ON step_runs(run_id, position);
        CREATE INDEX IF NOT EXISTS idx_runs_status_updated ON runs(status, updated_at_utc);
        """
    )


def latest_incomplete_run(conn: sqlite3.Connection) -> str | None:
    row = conn.execute(
        """
        SELECT run_id FROM runs
        WHERE workflow_id=? AND status IN ('created', 'running', 'paused', 'failed')
        ORDER BY updated_at_utc DESC
        LIMIT 1
        """,
        (WORKFLOW_ID,),
    ).fetchone()
    return str(row[0]) if row else None


def new_run_id() -> str:
    return f"wf74-wf88-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"


def ensure_run(conn: sqlite3.Connection, *, run_id: str, stop_after: str | None, resume: bool) -> None:
    now = utc_now()
    existing = conn.execute("SELECT status FROM runs WHERE run_id=?", (run_id,)).fetchone()
    if existing:
        if not resume:
            raise RuntimeError(f"run already exists; use --resume or a new --run-id: {run_id}")
        conn.execute(
            "UPDATE runs SET status='running', updated_at_utc=?, started_at_utc=COALESCE(started_at_utc, ?), stop_after=? WHERE run_id=?",
            (now, now, stop_after, run_id),
        )
        return
    conn.execute(
        """
        INSERT INTO runs(
          run_id, workflow_id, schema, status, created_at_utc, updated_at_utc,
          started_at_utc, stop_after, authority_boundary_json
        ) VALUES (?, ?, ?, 'running', ?, ?, ?, ?, ?)
        """,
        (run_id, WORKFLOW_ID, SCHEMA, now, now, now, stop_after, json.dumps(AUTHORITY_BOUNDARY, sort_keys=True)),
    )


def step_input_digest(root: Path, step: Step, prior_output_hashes: dict[str, str]) -> tuple[list[dict[str, Any]], str]:
    digest = {
        "command": step.command,
        "input_paths": [file_digest(root / path) for path in step.input_paths],
        "prior_output_hashes": prior_output_hashes,
    }
    return digest["input_paths"], hash_payload(digest)


def output_digest(root: Path, step: Step) -> tuple[list[dict[str, Any]], str]:
    digest = [file_digest(root / path) for path in step.expected_outputs]
    return digest, hash_payload(digest)


def completed_step_valid(conn: sqlite3.Connection, root: Path, run_id: str, step: Step) -> bool:
    row = conn.execute(
        "SELECT status, output_hash FROM step_runs WHERE run_id=? AND step_id=?",
        (run_id, step.step_id),
    ).fetchone()
    if not row or row[0] != "completed":
        return False
    _, current_hash = output_digest(root, step)
    return bool(current_hash == row[1])


def record_step_start(
    conn: sqlite3.Connection,
    *,
    run_id: str,
    step: Step,
    position: int,
    input_digest: list[dict[str, Any]],
    input_hash: str,
) -> None:
    now = utc_now()
    conn.execute(
        """
        INSERT INTO step_runs(
          run_id, step_id, position, status, command_json, command_text,
          expected_outputs_json, input_digest_json, input_hash, started_at_utc
        ) VALUES (?, ?, ?, 'running', ?, ?, ?, ?, ?, ?)
        ON CONFLICT(run_id, step_id) DO UPDATE SET
          status='running',
          command_json=excluded.command_json,
          command_text=excluded.command_text,
          expected_outputs_json=excluded.expected_outputs_json,
          input_digest_json=excluded.input_digest_json,
          input_hash=excluded.input_hash,
          started_at_utc=excluded.started_at_utc,
          completed_at_utc=NULL,
          duration_seconds=NULL,
          returncode=NULL,
          stdout_tail=NULL,
          stderr_tail=NULL,
          error=NULL
        """,
        (
            run_id,
            step.step_id,
            position,
            json.dumps(step.command),
            " ".join(step.command),
            json.dumps(step.expected_outputs),
            json.dumps(input_digest, sort_keys=True),
            input_hash,
            now,
        ),
    )
    conn.execute(
        "UPDATE runs SET status='running', updated_at_utc=?, current_step=? WHERE run_id=?",
        (now, step.step_id, run_id),
    )


def record_step_end(
    conn: sqlite3.Connection,
    *,
    run_id: str,
    step: Step,
    status: str,
    duration: float,
    returncode: int | None,
    stdout: str,
    stderr: str,
    error: str | None,
    root: Path,
) -> str:
    out_digest, out_hash = output_digest(root, step)
    now = utc_now()
    conn.execute(
        """
        UPDATE step_runs SET
          status=?, completed_at_utc=?, duration_seconds=?, returncode=?,
          stdout_tail=?, stderr_tail=?, error=?, output_digest_json=?, output_hash=?
        WHERE run_id=? AND step_id=?
        """,
        (
            status,
            now,
            round(duration, 3),
            returncode,
            tail(stdout),
            tail(stderr),
            error,
            json.dumps(out_digest, sort_keys=True),
            out_hash,
            run_id,
            step.step_id,
        ),
    )
    conn.execute("UPDATE runs SET updated_at_utc=? WHERE run_id=?", (now, run_id))
    return out_hash


def run_step(root: Path, step: Step) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        step.command,
        cwd=root,
        text=True,
        capture_output=True,
        timeout=step.timeout_seconds,
    )


def run_pipeline(
    *,
    root: Path,
    db_path: Path,
    out_path: Path,
    steps: list[Step],
    run_id: str | None,
    resume: bool,
    stop_after: str | None,
    write: bool,
) -> dict[str, Any]:
    conn = open_db(db_path)
    completed_hashes: dict[str, str] = {}
    try:
        ensure_schema(conn)
        if resume and not run_id:
            run_id = latest_incomplete_run(conn)
        run_id = run_id or new_run_id()
        conn.execute("BEGIN IMMEDIATE")
        ensure_run(conn, run_id=run_id, stop_after=stop_after, resume=resume)
        conn.commit()

        run_status = "complete"
        failed_step: str | None = None
        skipped_steps: list[str] = []
        for position, step in enumerate(steps, start=1):
            if resume and completed_step_valid(conn, root, run_id, step):
                _, out_hash = output_digest(root, step)
                completed_hashes[step.step_id] = out_hash
                skipped_steps.append(step.step_id)
                continue

            input_digest, input_hash = step_input_digest(root, step, completed_hashes)
            conn.execute("BEGIN IMMEDIATE")
            record_step_start(
                conn,
                run_id=run_id,
                step=step,
                position=position,
                input_digest=input_digest,
                input_hash=input_hash,
            )
            conn.commit()
            start = time.monotonic()
            try:
                result = run_step(root, step)
                duration = time.monotonic() - start
                missing_outputs = [path for path in step.expected_outputs if not (root / path).exists()]
                if result.returncode == 0 and not missing_outputs:
                    status = "completed"
                    error = None
                elif result.returncode == 0:
                    status = "failed"
                    error = f"missing_expected_outputs:{','.join(missing_outputs)}"
                else:
                    status = "failed"
                    error = f"returncode:{result.returncode}"
                conn.execute("BEGIN IMMEDIATE")
                out_hash = record_step_end(
                    conn,
                    run_id=run_id,
                    step=step,
                    status=status,
                    duration=duration,
                    returncode=result.returncode,
                    stdout=result.stdout,
                    stderr=result.stderr,
                    error=error,
                    root=root,
                )
                conn.commit()
                if status != "completed":
                    run_status = "failed"
                    failed_step = step.step_id
                    break
                completed_hashes[step.step_id] = out_hash
            except subprocess.TimeoutExpired as exc:
                duration = time.monotonic() - start
                conn.execute("BEGIN IMMEDIATE")
                record_step_end(
                    conn,
                    run_id=run_id,
                    step=step,
                    status="failed",
                    duration=duration,
                    returncode=None,
                    stdout=exc.stdout or "",
                    stderr=exc.stderr or "",
                    error=f"timeout:{step.timeout_seconds}",
                    root=root,
                )
                conn.commit()
                run_status = "failed"
                failed_step = step.step_id
                break

            if stop_after and step.step_id == stop_after:
                run_status = "paused"
                break

        now = utc_now()
        conn.execute("BEGIN IMMEDIATE")
        conn.execute(
            """
            UPDATE runs
            SET status=?, updated_at_utc=?, completed_at_utc=CASE WHEN ? IN ('complete', 'failed') THEN ? ELSE completed_at_utc END
            WHERE run_id=?
            """,
            (run_status, now, run_status, now, run_id),
        )
        conn.commit()
        payload = summarize_run(conn, root=root, db_path=db_path, run_id=run_id, skipped_steps=skipped_steps)
        payload["failed_step"] = failed_step
        payload["stop_after"] = stop_after
        if write:
            atomic_write_json(out_path, payload)
        return payload
    finally:
        conn.close()


def summarize_run(
    conn: sqlite3.Connection,
    *,
    root: Path,
    db_path: Path,
    run_id: str,
    skipped_steps: list[str] | None = None,
) -> dict[str, Any]:
    run = conn.execute(
        "SELECT run_id, status, created_at_utc, updated_at_utc, started_at_utc, completed_at_utc, current_step FROM runs WHERE run_id=?",
        (run_id,),
    ).fetchone()
    if not run:
        raise RuntimeError(f"missing run: {run_id}")
    step_rows = list(
        conn.execute(
            """
            SELECT step_id, position, status, command_text, expected_outputs_json,
                   input_hash, output_hash, duration_seconds, returncode, error
            FROM step_runs
            WHERE run_id=?
            ORDER BY position
            """,
            (run_id,),
        )
    )
    steps: list[dict[str, Any]] = []
    counts: dict[str, int] = {}
    for row in step_rows:
        step_id, position, status, command_text, outputs_json, input_hash, output_hash, duration, returncode, error = row
        counts[status] = counts.get(status, 0) + 1
        steps.append(
            {
                "step_id": step_id,
                "position": position,
                "status": status,
                "command": command_text,
                "expected_outputs": json.loads(outputs_json),
                "input_hash": input_hash,
                "output_hash": output_hash,
                "duration_seconds": duration,
                "returncode": returncode,
                "error": error,
            }
        )
    return {
        "schema": SCHEMA,
        "status": "ok" if run[1] == "complete" else run[1],
        "generated_at_utc": utc_now(),
        "workflow_id": WORKFLOW_ID,
        "run_id": run[0],
        "run_status": run[1],
        "created_at_utc": run[2],
        "updated_at_utc": run[3],
        "started_at_utc": run[4],
        "completed_at_utc": run[5],
        "current_step": run[6],
        "db_path": rel(root, db_path),
        "step_count": len(steps),
        "status_counts": counts,
        "skipped_steps": skipped_steps or [],
        "steps": steps,
        "authority_boundary": AUTHORITY_BOUNDARY,
    }


def validate_latest(*, root: Path, db_path: Path, out_path: Path | None = None) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    if not db_path.exists():
        errors.append("missing_checkpoint_db")
        return {"status": "error", "errors": errors, "warnings": warnings}
    conn = open_db(db_path)
    try:
        ensure_schema(conn)
        row = conn.execute(
            "SELECT run_id, status FROM runs WHERE workflow_id=? ORDER BY updated_at_utc DESC LIMIT 1",
            (WORKFLOW_ID,),
        ).fetchone()
        if not row:
            errors.append("missing_run")
            return {"status": "error", "errors": errors, "warnings": warnings}
        run_id, run_status = row
        summary = summarize_run(conn, root=root, db_path=db_path, run_id=run_id)
        if run_status != "complete":
            errors.append(f"latest_run_not_complete:{run_status}")
        expected_step_count = len(default_steps()) if root == ROOT else summary["step_count"]
        completed_count = summary["status_counts"].get("completed", 0)
        if completed_count != expected_step_count:
            errors.append(f"incomplete_step_count:{completed_count}/{expected_step_count}")
        for step in summary["steps"]:
            for output in step["expected_outputs"]:
                if not (root / output).exists():
                    errors.append(f"missing_output:{output}")
        if out_path and out_path.exists():
            try:
                payload = json.loads(out_path.read_text(encoding="utf-8"))
                if payload.get("run_id") != run_id:
                    warnings.append("summary_out_not_latest_run")
            except json.JSONDecodeError:
                errors.append("summary_out_invalid_json")
    finally:
        conn.close()
    return {"status": "ok" if not errors else "error", "errors": errors, "warnings": warnings}


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run WF74 -> WF88 with durable checkpoints.")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--run-id")
    parser.add_argument("--stop-after")
    parser.add_argument("--db", default=str(DEFAULT_DB))
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    parser.add_argument("--pretty", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    db_path = Path(args.db)
    out_path = Path(args.out)
    payload: dict[str, Any] | None = None
    if args.write:
        payload = run_pipeline(
            root=ROOT,
            db_path=db_path,
            out_path=out_path,
            steps=default_steps(),
            run_id=args.run_id,
            resume=args.resume,
            stop_after=args.stop_after,
            write=True,
        )
    if args.validate:
        validation = validate_latest(root=ROOT, db_path=db_path, out_path=out_path)
        if payload is None:
            if db_path.exists():
                conn = open_db(db_path)
                try:
                    row = conn.execute(
                        "SELECT run_id FROM runs WHERE workflow_id=? ORDER BY updated_at_utc DESC LIMIT 1",
                        (WORKFLOW_ID,),
                    ).fetchone()
                    payload = summarize_run(conn, root=ROOT, db_path=db_path, run_id=row[0]) if row else {}
                finally:
                    conn.close()
            else:
                payload = {"schema": SCHEMA, "status": "error", "generated_at_utc": utc_now()}
        payload["validation"] = validation
        if args.write:
            payload["status"] = "ok" if validation["status"] == "ok" else "error"
            atomic_write_json(out_path, payload)
        if validation["status"] != "ok":
            if args.pretty:
                print(json.dumps(payload, indent=2, sort_keys=True))
            return 1
    if args.pretty and payload is not None:
        print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
