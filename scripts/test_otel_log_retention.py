#!/usr/bin/env python3
"""Focused tests for OTEL log-retention helpers."""
from __future__ import annotations

import tempfile
from pathlib import Path

import otel_log_retention as retention


def expect(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def main() -> int:
    errors: list[str] = []
    with tempfile.TemporaryDirectory() as raw:
        root = Path(raw)
        log = root / "collector.err.log"
        archive = root / "archive"
        log.write_text("first log\n", encoding="utf-8")
        result = retention.rotate_log(log, archive, keep=2)
        expect(not log.exists(), "source log should move to archive", errors)
        archived = archive / Path(result["archive"]).name
        expect(archived.exists(), "archive log missing", errors)
        expect(archived.read_text(encoding="utf-8") == "first log\n", "archive content drifted", errors)
        expect(result["source_before"]["size_bytes"] > 0, "source state missing size", errors)
        expect(result["source_sha256_first_mb"] is not None, "source hash missing", errors)

        for index in range(4):
            log.write_text(f"log {index}\n", encoding="utf-8")
            retention.rotate_log(log, archive, keep=2)
        archives = list(archive.glob("collector.err.*.log"))
        expect(len(archives) == 2, f"retention keep=2 failed: {len(archives)} archives", errors)

    if errors:
        print("otel_log_retention_tests_failed")
        for error in errors:
            print(f"- {error}")
        return 1
    print("otel_log_retention_tests_passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
