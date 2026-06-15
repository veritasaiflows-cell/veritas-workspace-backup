from __future__ import annotations

import json
import tempfile
from pathlib import Path

import implementation_completion_ledger as ledger
from market_data_utils import atomic_write_json


def write_source(path: Path, job_id: str) -> None:
    atomic_write_json(path, {
        "schema": "veritas.pm_execution_loop.v1",
        "generated_at_utc": "2026-06-10T00:00:00Z",
        "status": "ok",
        "mode": "execute",
        "purpose": "test source",
        "summary": {
            "next_safe_action": "test next",
            "proof_failed": [],
            "closeout_failed": [],
        },
        "selected": [{
            "job_id": job_id,
            "title": "Test job",
            "implementation_class": "test_class",
            "owner_surface": "test_owner",
            "collision_group": "test_group",
            "target_files": [],
        }],
        "proof_results": [{
            "name": f"{job_id}:proof[0]",
            "command": "python scripts\\example.py --write --validate",
            "ok": True,
            "returncode": 0,
            "completed_at_utc": "2026-06-10T00:00:01Z",
        }],
        "closeout_results": [{
            "name": f"{job_id}:closeout[0]",
            "command": "python scripts\\repeatable_work_closeout.py --write --validate",
            "ok": True,
            "returncode": 0,
            "completed_at_utc": "2026-06-10T00:00:02Z",
        }],
        "validation": {"status": "ok", "errors": [], "warnings": []},
        "authority_boundary": {"review_only": True},
    })


def test_recorded_entries_form_hash_chain() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        source1 = root / "source1.json"
        source2 = root / "source2.json"
        ledger_path = root / "ledger.jsonl"
        write_source(source1, "job-1")
        write_source(source2, "job-2")

        args1 = type("Args", (), {
            "source": source1,
            "ledger": ledger_path,
            "out": root / "out1.json",
            "job_id": None,
            "title": None,
            "summary": None,
            "record": True,
        })()
        report1 = ledger.build_report(args1)
        assert report1["status"] == "ok"
        assert report1["summary"]["entry_count_after"] == 1

        args2 = type("Args", (), {
            "source": source2,
            "ledger": ledger_path,
            "out": root / "out2.json",
            "job_id": None,
            "title": None,
            "summary": None,
            "record": True,
        })()
        report2 = ledger.build_report(args2)
        assert report2["status"] == "ok"
        assert report2["summary"]["entry_count_after"] == 2

        entries = ledger.load_entries(ledger_path)
        validation = ledger.validate_entries(entries)
        assert validation["status"] == "ok"
        assert entries[1]["previous_entry_hash"] == entries[0]["entry_hash"]
        assert entries[0]["source_report"]["sha256"] == ledger.sha256_file(source1)
        assert entries[0]["source_report"]["snapshot"]["exists"] is True
        assert entries[0]["source_report"]["snapshot"]["sha256"] == entries[0]["source_report"]["sha256"]


def test_validate_detects_tampered_entry() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        source = root / "source.json"
        ledger_path = root / "ledger.jsonl"
        write_source(source, "job-1")
        args = type("Args", (), {
            "source": source,
            "ledger": ledger_path,
            "out": root / "out.json",
            "job_id": None,
            "title": None,
            "summary": None,
            "record": True,
        })()
        report = ledger.build_report(args)
        assert report["status"] == "ok"

        row = json.loads(ledger_path.read_text(encoding="utf-8").splitlines()[0])
        row["job"]["title"] = "Tampered"
        ledger_path.write_text(json.dumps(row, sort_keys=True) + "\n", encoding="utf-8")

        validation = ledger.validate_entries(ledger.load_entries(ledger_path))
        assert validation["status"] == "blocked"
        assert "entry_hash_mismatch:1" in validation["errors"]


def test_recording_same_source_is_idempotent() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        source = root / "source.json"
        ledger_path = root / "ledger.jsonl"
        write_source(source, "job-1")
        args = type("Args", (), {
            "source": source,
            "ledger": ledger_path,
            "out": root / "out.json",
            "job_id": None,
            "title": None,
            "summary": None,
            "record": True,
        })()

        first = ledger.build_report(args)
        second = ledger.build_report(args)

        assert first["status"] == "ok"
        assert second["status"] == "ok"
        assert first["summary"]["new_entry_count"] == 1
        assert second["summary"]["new_entry_count"] == 0
        assert second["summary"]["entry_count_after"] == 1


def test_pm_dry_run_source_is_not_completion() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        source = root / "source.json"
        ledger_path = root / "ledger.jsonl"
        write_source(source, "job-1")
        data = json.loads(source.read_text(encoding="utf-8"))
        data["mode"] = "dry_run"
        source.write_text(json.dumps(data), encoding="utf-8")
        args = type("Args", (), {
            "source": source,
            "ledger": ledger_path,
            "out": root / "out.json",
            "job_id": None,
            "title": None,
            "summary": None,
            "record": True,
        })()

        report = ledger.build_report(args)

        assert report["status"] == "ok"
        assert report["recorded"] is False
        assert report["summary"]["new_entry_count"] == 0


def test_manual_completed_jobs_source_records_each_job() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        source = root / "backfill.json"
        ledger_path = root / "ledger.jsonl"
        atomic_write_json(source, {
            "schema": "veritas.implementation_completion_backfill.v1",
            "generated_at_utc": "2026-06-10T02:00:00Z",
            "status": "ok",
            "summary": {"next_safe_action": "test backfill"},
            "completed_jobs": [
                {
                    "job_id": "job-1",
                    "title": "First backfill job",
                    "summary": "first summary",
                    "completed_at_utc": "2026-06-10T01:00:00Z",
                    "implementation_class": "test_backfill",
                    "owner_surface": "test",
                    "target_files": [],
                },
                {
                    "job_id": "job-2",
                    "title": "Second backfill job",
                    "summary": "second summary",
                    "completed_at_utc": "2026-06-10T01:30:00Z",
                    "implementation_class": "test_backfill",
                    "owner_surface": "test",
                    "target_files": [],
                },
            ],
            "validation": {"status": "ok", "errors": [], "warnings": []},
        })
        args = type("Args", (), {
            "source": source,
            "ledger": ledger_path,
            "out": root / "out.json",
            "job_id": None,
            "title": None,
            "summary": None,
            "record": True,
        })()

        report = ledger.build_report(args)

        assert report["status"] == "ok"
        assert report["summary"]["new_entry_count"] == 2
        entries = ledger.load_entries(ledger_path)
        assert [entry["job"]["job_id"] for entry in entries] == ["job-1", "job-2"]
        assert entries[0]["completed_at_utc"] == "2026-06-10T01:00:00Z"
        assert entries[1]["job"]["summary"] == "second summary"
