#!/usr/bin/env python3
from __future__ import annotations

import runtime_ops_consolidated_digest as digest


def expect(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def main() -> int:
    errors: list[str] = []
    command = digest.future_session_packet_command()
    expect("scripts\\future_session_enhancement_packet.py" in command, "future-session producer missing from command", errors)
    expect("--skip-if-unchanged" in command, "future-session command missing changed-input prefilter flag", errors)
    expect("--write" in command and "--write-md" in command and "--validate" in command, "future-session command must still write and validate when refresh is required", errors)
    expect(digest.source_jobs_for(["future-session"]) == ["Runtime - Future Session Packet Refresh"], "future-session source job mapping changed", errors)
    if errors:
        print("runtime_ops_consolidated_digest_tests_failed")
        for error in errors:
            print(f"- {error}")
        return 1
    print("runtime_ops_consolidated_digest_tests_passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
