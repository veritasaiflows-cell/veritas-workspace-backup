#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import io
import sys
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "dream_review_packet.py"


def load_module():
    spec = importlib.util.spec_from_file_location("dream_review_packet", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_cron_hour_window() -> None:
    module = load_module()
    assert module.cron_hour_in_window("0 3 * * *")["ok"] is True
    assert module.cron_hour_in_window("30 5 * * *")["ok"] is True
    assert module.cron_hour_in_window("0 6 * * *")["ok"] is False
    assert module.cron_hour_in_window("bad")["ok"] is False


def test_payload_validation_authority_and_schedule() -> None:
    module = load_module()
    payload = {
        "authority_boundary": dict(module.AUTHORITY_BOUNDARY),
        "config": {"enabled": True, "timezone": module.APPROVED_TZ, "frequency": "0 3 * * *"},
        "schedule": {"inside_approved_window": True},
        "memory_status": {"dirty": False, "embedding_probe_ok": True},
        "rem_harness": {"status": "not_requested"},
    }
    validation = module.validate_payload(payload)
    assert validation["status"] == "ok"


def test_config_and_rem_summaries() -> None:
    module = load_module()
    config = module.config_summary(
        {
            "config": {
                "dreaming": {
                    "enabled": True,
                    "timezone": "America/Phoenix",
                    "frequency": "0 3 * * *",
                    "phases": {"deep": {"maxPromotedSnippetTokens": 160}},
                }
            }
        }
    )
    assert config["enabled"] is True
    assert config["deep"]["maxPromotedSnippetTokens"] == 160

    rem = module.rem_harness_summary(
        {
            "remConfig": {"enabled": True, "cron": "0 3 * * *", "timezone": "America/Phoenix"},
            "rem": {"sourceEntryCount": 0, "reflections": ["- none"], "candidateTruths": [], "candidateKeys": []},
            "deep": {
                "candidateCount": 1,
                "candidates": [
                    {
                        "path": "memory/2026-06-19.md",
                        "startLine": 1,
                        "endLine": 2,
                        "score": 0.91,
                        "recallCount": 5,
                        "uniqueQueries": 4,
                        "conceptTags": ["learning"],
                    }
                ],
            },
        }
    )
    assert rem["candidate_truth_count"] == 0
    assert rem["deep_candidate_count"] == 1
    assert rem["top_candidates"][0]["concept_tags"] == ["learning"]


def test_memory_status_distinguishes_legacy_file_from_runtime_sqlite_state() -> None:
    module = load_module()
    summary = module.memory_status_summary(
        {
            "agentId": "main",
            "status": {
                "backend": "builtin",
                "dbPath": "C:/mock/memory-core.sqlite",
                "files": 7,
                "chunks": 19,
                "dirty": False,
            },
            "embeddingProbe": {"ok": True},
            "audit": {"entryCount": 2},
            "dreamingAudit": {"sessionIngestionExists": False},
        }
    )
    assert summary["legacy_session_ingestion_artifact_exists"] is False
    assert summary["runtime_memory_core_sqlite_ingestion"] == {
        "state": "reported",
        "database_path": "C:/mock/memory-core.sqlite",
        "indexed_file_count": 7,
        "indexed_chunk_count": 19,
    }


def test_dream_artifact_summary_labels_legacy_session_ingestion() -> None:
    module = load_module()
    with patch.object(module.Path, "exists", return_value=False):
        artifacts = module.dream_artifact_summary()
    assert artifacts["diary"]["path"] == "DREAMS.md"
    assert artifacts["legacy_session_ingestion"] == {
        "path": "memory/.dreams/session-ingestion.json",
        "exists": False,
        "kind": "legacy_file_artifact",
    }
    assert "session_ingestion" not in artifacts


def test_disabled_containment_next_action_uses_mocked_runtime_sources() -> None:
    module = load_module()
    config_payload = {
        "config": {
            "dreaming": {
                "enabled": False,
                "timezone": module.APPROVED_TZ,
                "frequency": "0 3 * * *",
            }
        }
    }
    status_payload = {
        "agentId": "main",
        "status": {"dbPath": "C:/mock/memory-core.sqlite", "dirty": False, "files": 2, "chunks": 4},
        "embeddingProbe": {"ok": True},
        "dreamingAudit": {"sessionIngestionExists": False},
    }
    artifacts = {
        "diary": {"exists": False},
        "session_corpus": {"file_count": 0},
        "legacy_session_ingestion": {"exists": False},
    }
    with (
        patch.object(
            module,
            "run_openclaw_json",
            side_effect=[(config_payload, {"ok": True}), (status_payload, {"ok": True})],
        ),
        patch.object(module, "dream_artifact_summary", return_value=artifacts),
    ):
        payload = module.build_payload(include_rem_harness=False, timeout=1)
    assert payload["validation"]["status"] == "critical"
    assert payload["status"] == "critical"
    assert payload["memory_status"]["legacy_session_ingestion_artifact_exists"] is False
    assert payload["memory_status"]["runtime_memory_core_sqlite_ingestion"]["state"] == "reported"
    assert "no overnight sweep is expected" in payload["next_safe_action"]
    assert "explicitly authorizes" in payload["next_safe_action"]


def test_validate_exit_stays_nonzero_when_dreaming_is_disabled() -> None:
    module = load_module()
    payload = {
        "authority_boundary": dict(module.AUTHORITY_BOUNDARY),
        "config": {"enabled": False, "timezone": module.APPROVED_TZ, "frequency": "0 3 * * *"},
        "schedule": {"inside_approved_window": True},
        "memory_status": {"dirty": False, "embedding_probe_ok": True},
        "rem_harness": {"status": "not_requested"},
        "dream_artifacts": {},
        "next_safe_action": "mocked",
    }
    payload["validation"] = module.validate_payload(payload)
    assert any(check["name"] == "dreaming_enabled" and check["severity"] == "critical" for check in payload["validation"]["errors"])
    with (
        patch.object(module, "build_payload", return_value=payload),
        patch.object(sys, "argv", ["dream_review_packet.py", "--validate"]),
        redirect_stdout(io.StringIO()),
    ):
        assert module.main() == 1


def main() -> int:
    test_cron_hour_window()
    test_payload_validation_authority_and_schedule()
    test_config_and_rem_summaries()
    test_memory_status_distinguishes_legacy_file_from_runtime_sqlite_state()
    test_dream_artifact_summary_labels_legacy_session_ingestion()
    test_disabled_containment_next_action_uses_mocked_runtime_sources()
    test_validate_exit_stays_nonzero_when_dreaming_is_disabled()
    print("dream review packet tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
