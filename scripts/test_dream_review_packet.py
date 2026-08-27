#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
from pathlib import Path


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


def test_dream_diary_path_points_to_workspace_root() -> None:
    module = load_module()
    artifacts = module.dream_artifact_summary()
    assert artifacts["diary"]["path"] == "DREAMS.md"


def main() -> int:
    test_cron_hour_window()
    test_payload_validation_authority_and_schedule()
    test_config_and_rem_summaries()
    test_dream_diary_path_points_to_workspace_root()
    print("dream review packet tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
