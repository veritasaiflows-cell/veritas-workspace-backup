#!/usr/bin/env python3
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import legacy_audit_root_cleanup_packet as packet_mod


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_packet_digest_and_references() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        write(root / "08. Audit and Governance" / "Go Validator Audit 2026-06-21.md", "audit\n")
        write(root / "08. Audit and Governance" / "P0 P1 P2 Workflow Residue Audit 2026-06-21.md", "audit\n")
        write(root / "Audit" / "command-center-ui-navigation-audit-2026-06-18.md", "audit\n")
        write(root / "Audit" / "SMB-SaaS-Parallel-Implementation-Plan-2026-06-18.md", "plan\n")
        write(root / "memory" / "2026-06-22.md", "See 08. Audit and Governance/Go Validator Audit 2026-06-21.md\n")

        packet = packet_mod.build_packet(root)
        errors = packet_mod.validate_packet(packet)
        assert errors == []
        assert packet["status"] == "ready_for_owner_approval"
        assert len(packet["microbatch_digest"]) == 64
        assert packet["summary"]["operation_count"] == 4
        assert packet["summary"]["promote_count"] == 3
        assert packet["summary"]["archive_count"] == 1
        assert packet["summary"]["reference_count"] == 1
        json.dumps(packet)


def test_existing_target_blocks() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        write(root / "08. Audit and Governance" / "Go Validator Audit 2026-06-21.md", "audit\n")
        write(root / "08. Audits" / "Go Validator Audit 2026-06-21.md", "existing\n")

        packet = packet_mod.build_packet(root)
        errors = packet_mod.validate_packet(packet)
        assert packet["status"] == "blocked"
        assert any("target paths already exist" in error for error in errors)


if __name__ == "__main__":
    test_packet_digest_and_references()
    test_existing_target_blocks()
    print("legacy audit root cleanup packet tests passed")
