#!/usr/bin/env python3
"""Targeted tests for openclaw_cache_efficiency_scorecard."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import openclaw_cache_efficiency_scorecard as scorecard


def write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def test_bootstrap_scoring_flags_large_and_volatile_stable_file() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        write(root / "AGENTS.md", "Current date guidance\n" + ("x" * 12_100))
        write(root / "HEARTBEAT.md", "changes often")
        scores = {item.path: item for item in scorecard.score_bootstrap_files(root)}

    assert scores["AGENTS.md"].exists is True
    assert scores["AGENTS.md"].truncated_by_default_file_cap is True
    assert any("time-sensitive" in warning for warning in (scores["AGENTS.md"].warnings or []))
    assert scores["HEARTBEAT.md"].cache_prefix_role == "volatile_suffix"


def test_tool_result_scoring_detects_oversized_json_tool_result() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        transcript = write(
            root / "transcript.json",
            json.dumps({"messages": [{"role": "tool", "content": "A" * 21_000}]}),
        )
        results = scorecard.score_tool_results([transcript])

    assert len(results) == 1
    assert results[0].severity == "high"
    assert results[0].chars == 21_000
    assert results[0].recommendation


def test_openclaw_shaped_transcript_repeated_large_reads() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        transcript = write(
            root / "openclaw-session-export.json",
            json.dumps(
                {
                    "turns": [
                        {
                            "type": "tool_result",
                            "tool": "read",
                            "input": {"path": "AGENTS.md", "offset": 1, "limit": 2000},
                            "content": "A" * 9_000,
                        },
                        {
                            "role": "tool",
                            "name": "read",
                            "args": {"path": "AGENTS.md", "offset": 2001, "limit": 2000},
                            "output": "B" * 10_000,
                        },
                        {
                            "type": "toolResult",
                            "toolName": "exec",
                            "arguments": {"command": "rg pattern"},
                            "toolResult": {"text": "short output"},
                        },
                    ]
                }
            ),
        )
        results = scorecard.score_tool_results([transcript])
        repeated = scorecard.score_repeated_large_reads(results)

    assert len(results) == 2
    assert {item.tool_name for item in results} == {"read"}
    assert repeated[0].target == "AGENTS.md"
    assert repeated[0].occurrences == 2
    assert "offset/limit" in repeated[0].recommendation


def test_jsonl_session_transcript_is_scanned_for_tool_results() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        transcript = write(
            root / "session.jsonl",
            "\n".join(
                [
                    json.dumps({"type": "session", "id": "fixture"}),
                    json.dumps(
                        {
                            "type": "message",
                            "message": {
                                "role": "toolResult",
                                "toolName": "read",
                                "content": [{"type": "text", "text": "C" * 8_500}],
                            },
                        }
                    ),
                ]
            ),
        )
        results = scorecard.score_tool_results([transcript])

    assert len(results) == 1
    assert results[0].source.endswith("session.jsonl")
    assert results[0].locator.startswith("$line[2]")
    assert results[0].chars == 8_500


def test_preview_redacts_secret_like_text() -> None:
    assert scorecard.safe_preview("authorization: Bearer abc123") == "[redacted: preview matched secret/credential-like text]"


def test_redacted_tool_telemetry_exports_body_free_secret_safe_summary() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        secret_body = "authorization: Bearer abc123\n" + ("S" * 9_000)
        transcript = write(
            root / "session.jsonl",
            "\n".join(
                [
                    json.dumps(
                        {
                            "type": "tool_result",
                            "tool": "web_fetch",
                            "input": {"url": "https://example.test/path?token=secret-token"},
                            "status": "success",
                            "duration_ms": 123,
                            "truncated": True,
                            "content": secret_body,
                        }
                    ),
                    json.dumps(
                        {
                            "role": "tool",
                            "name": "read",
                            "args": {"path": "tmp/example.json"},
                            "output": "short output",
                        }
                    ),
                ]
            ),
        )
        report = scorecard.build_redacted_tool_telemetry(root, [transcript])

    assert report["events_count"] == 2
    first = report["events"][0]
    assert first["tool_name"] == "web_fetch"
    assert first["status"] == "success"
    assert first["duration_ms"] == 123
    assert first["output_chars"] == len(secret_body)
    assert first["path_category"] == "external_url"
    assert first["truncated"] is True
    assert "secret-token" not in json.dumps(report)
    assert "Bearer abc123" not in json.dumps(report)
    assert "SSSS" not in json.dumps(report)
    assert report["events"][1]["path_category"] == "workspace_tmp"


def test_redacted_tool_telemetry_markdown_contains_no_body_column() -> None:
    report = {
        "generated_at_utc": "2026-01-01T00:00:00Z",
        "report_only": True,
        "mutations_performed": False,
        "authority_boundary": "No config/auth/runtime mutation",
        "redaction_contract": "No raw tool-result bodies are exported.",
        "transcripts_scanned": ["session.jsonl"],
        "events_count": 1,
        "events_with_medium_or_high_output": 0,
        "events_truncated_or_hard_warn": 0,
        "summary_by_tool": {"read": {"count": 1, "total_output_chars": 12, "max_output_chars": 12}},
        "summary_by_path_category": {"workspace_file": {"count": 1, "total_output_chars": 12, "max_output_chars": 12}},
        "events": [
            {
                "tool_name": "read",
                "status": "success",
                "duration_ms": None,
                "output_chars": 12,
                "path_category": "workspace_file",
                "target_redacted": "AGENTS.md",
                "truncated": False,
                "recommendation": "Use a smaller read offset/limit.",
            }
        ],
    }
    markdown = scorecard.render_redacted_tool_telemetry_markdown(report)

    assert "Output chars" in markdown
    assert "Preview" not in markdown
    assert "body" not in markdown.lower().split("## Largest events", 1)[-1]
    assert "content-free" in markdown


def test_report_includes_operator_command_path_without_transcript() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        write(root / "AGENTS.md", "stable")
        report = scorecard.build_report(root, [])

    assert report["tool_results"]["operator_command_path"]
    assert any("--transcript" in item for item in report["tool_results"]["operator_command_path"])


def test_resolve_transcript_paths_can_include_latest_main_session(monkeypatch=None) -> None:
    explicit = Path("explicit.jsonl").resolve()
    original = scorecard.discover_latest_main_session_transcript
    try:
        scorecard.discover_latest_main_session_transcript = lambda: explicit
        assert scorecard.resolve_transcript_paths([], include_latest_main=True) == [explicit]
        assert scorecard.resolve_transcript_paths([explicit], include_latest_main=True) == [explicit]
    finally:
        scorecard.discover_latest_main_session_transcript = original


def test_build_report_preserves_report_only_boundary() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        write(root / "AGENTS.md", "stable")
        report = scorecard.build_report(root, [])

    assert report["report_only"] is True
    assert report["mutations_performed"] is False
    assert "No config/auth/runtime mutation" in report["authority_boundary"]
    assert report["bootstrap"]["total_existing_chars"] == len("stable")


if __name__ == "__main__":
    test_bootstrap_scoring_flags_large_and_volatile_stable_file()
    test_tool_result_scoring_detects_oversized_json_tool_result()
    test_openclaw_shaped_transcript_repeated_large_reads()
    test_jsonl_session_transcript_is_scanned_for_tool_results()
    test_preview_redacts_secret_like_text()
    test_redacted_tool_telemetry_exports_body_free_secret_safe_summary()
    test_redacted_tool_telemetry_markdown_contains_no_body_column()
    test_report_includes_operator_command_path_without_transcript()
    test_resolve_transcript_paths_can_include_latest_main_session()
    test_build_report_preserves_report_only_boundary()
    print("openclaw_cache_efficiency_scorecard_tests_passed")
