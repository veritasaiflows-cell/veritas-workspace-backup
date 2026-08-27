from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "wf88_cron_retired_job_inventory.py"


def load_module():
    sys.path.insert(0, str(ROOT / "scripts"))
    spec = importlib.util.spec_from_file_location("wf88_cron_retired_job_inventory", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_inventory_lists_disabled_jobs_without_mutation_authority() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        tmp = root / "tmp"
        cron = tmp / "cron-control-packet.json"
        tmp.mkdir()
        cron.write_text(
            json.dumps(
                {
                    "schema": "veritas.cron_control_packet.v1",
                    "status": "ok",
                    "freshness": {
                        "jobs": [
                            {
                                "id": "enabled-1",
                                "name": "Enabled job",
                                "enabled": True,
                                "status": "fresh",
                            },
                            {
                                "id": "disabled-1",
                                "name": "Disabled job",
                                "enabled": False,
                                "status": "disabled",
                                "expected_artifacts": ["tmp/proof.json"],
                            },
                        ]
                    },
                }
            ),
            encoding="utf-8",
        )
        with (
            mock.patch.object(module, "ROOT", root),
            mock.patch.object(module, "TMP", tmp),
            mock.patch.object(module, "CRON_CONTROL", cron),
            mock.patch.object(module, "OUT", tmp / "wf88-cron-retired-job-inventory.json"),
            mock.patch.object(module, "MD_OUT", tmp / "wf88-cron-retired-job-inventory.md"),
            mock.patch.object(
                module,
                "load_live_jobs",
                return_value=(
                    [
                        {
                            "id": "disabled-1",
                            "name": "Disabled job",
                            "enabled": False,
                            "schedule": {"kind": "cron", "expr": "0 9 * * *", "tz": "America/Phoenix"},
                            "payload": {"kind": "agentTurn", "message": "proof only"},
                            "sessionTarget": "isolated",
                            "delivery": {"mode": "none"},
                        }
                    ],
                    {"source": "test-live-cron-list", "ok": True},
                ),
            ),
        ):
            packet = module.build_packet()

    assert packet["validation"]["status"] == "ok"
    assert packet["summary"]["enabled_job_count"] == 1
    assert packet["summary"]["disabled_or_retired_job_count"] == 1
    assert packet["summary"]["mutation_ready_now_count"] == 0
    assert packet["summary"]["live_scheduler_export_ok"] is True
    assert packet["summary"]["rollback_export_ready_count"] == 1
    assert packet["summary"]["rollback_export_required_count"] == 0
    row = packet["disabled_or_retired_jobs"][0]
    assert row["job_id"] == "disabled-1"
    assert row["rollback_export_required"] is False
    assert row["rollback_restore_job"]["job"]["payload"]["message"] == "proof only"
    assert row["delete_ready_now"] is False
    assert row["cron_schedule_mutation_allowed_now"] is False
    assert packet["authority_boundary"]["cron_schedule_mutation_allowed"] is False


def test_inventory_keeps_rollback_required_when_live_export_missing() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        tmp = root / "tmp"
        cron = tmp / "cron-control-packet.json"
        tmp.mkdir()
        cron.write_text(
            json.dumps(
                {
                    "schema": "veritas.cron_control_packet.v1",
                    "status": "ok",
                    "freshness": {
                        "jobs": [
                            {
                                "id": "disabled-1",
                                "name": "Disabled job",
                                "enabled": False,
                                "status": "disabled",
                            },
                        ]
                    },
                }
            ),
            encoding="utf-8",
        )
        with (
            mock.patch.object(module, "ROOT", root),
            mock.patch.object(module, "TMP", tmp),
            mock.patch.object(module, "CRON_CONTROL", cron),
            mock.patch.object(module, "OUT", tmp / "wf88-cron-retired-job-inventory.json"),
            mock.patch.object(module, "MD_OUT", tmp / "wf88-cron-retired-job-inventory.md"),
            mock.patch.object(module, "load_live_jobs", return_value=([], {"source": "test-live-cron-list", "ok": False})),
        ):
            packet = module.build_packet()

    assert packet["validation"]["status"] == "ok"
    assert "live_scheduler_export_unavailable" in packet["validation"]["warnings"]
    assert packet["summary"]["rollback_export_ready_count"] == 0
    assert packet["summary"]["rollback_export_required_count"] == 1
    assert packet["disabled_or_retired_jobs"][0]["rollback_restore_job"] is None


def test_inventory_recovers_rollback_payload_from_snapshot_when_live_job_absent() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        tmp = root / "tmp"
        cron = tmp / "cron-control-packet.json"
        snapshot = tmp / "cron-snapshot.json"
        tmp.mkdir()
        cron.write_text(
            json.dumps(
                {
                    "schema": "veritas.cron_control_packet.v1",
                    "status": "ok",
                    "freshness": {
                        "jobs": [
                            {
                                "id": "disabled-1",
                                "name": "Disabled job",
                                "enabled": False,
                                "status": "disabled",
                            },
                        ]
                    },
                }
            ),
            encoding="utf-8",
        )
        snapshot.write_text(
            json.dumps(
                {
                    "jobs": [
                        {
                            "id": "disabled-1",
                            "name": "Disabled job",
                            "enabled": False,
                            "schedule": {"kind": "cron", "expr": "0 9 * * *", "tz": "America/Phoenix"},
                            "payload": {"kind": "agentTurn", "message": "snapshot proof only"},
                            "sessionTarget": "isolated",
                            "delivery": {"mode": "none"},
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )
        with (
            mock.patch.object(module, "ROOT", root),
            mock.patch.object(module, "TMP", tmp),
            mock.patch.object(module, "CRON_CONTROL", cron),
            mock.patch.object(module, "OUT", tmp / "wf88-cron-retired-job-inventory.json"),
            mock.patch.object(module, "MD_OUT", tmp / "wf88-cron-retired-job-inventory.md"),
            mock.patch.object(module, "recovery_snapshot_candidates", return_value=[snapshot]),
            mock.patch.object(module, "load_live_jobs", return_value=([], {"source": "test-live-cron-list", "ok": True})),
        ):
            packet = module.build_packet()

    row = packet["disabled_or_retired_jobs"][0]
    assert packet["validation"]["status"] == "ok"
    assert packet["summary"]["rollback_export_ready_count"] == 1
    assert packet["summary"]["rollback_export_required_count"] == 0
    assert packet["summary"]["rollback_export_recovered_from_snapshot_count"] == 1
    assert row["live_scheduler_export_job_found"] is False
    assert row["rollback_export_status"] == "rollback_restore_payload_recovered_from_snapshot"
    assert row["rollback_export_source"] == "historical_scheduler_snapshot"
    assert row["rollback_export_snapshot_path"] == "tmp/cron-snapshot.json"
    assert row["rollback_export_required"] is False
    assert row["rollback_restore_job"]["job"]["payload"]["message"] == "snapshot proof only"
    assert row["delete_ready_now"] is False
