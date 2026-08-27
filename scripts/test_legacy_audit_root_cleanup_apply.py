from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APPLY_SCRIPT = ROOT / "scripts" / "legacy_audit_root_cleanup_apply.py"


def load_apply_module(root: Path):
    sys.path.insert(0, str(ROOT / "scripts"))
    spec = importlib.util.spec_from_file_location("legacy_audit_root_cleanup_apply", APPLY_SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.ROOT = root
    module.PACKET = root / "tmp" / "legacy-audit-root-cleanup-packet.json"
    module.APPLY_REPORT = root / "tmp" / "legacy-audit-root-cleanup-apply-report.json"
    return module


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def seed_packet(root: Path, module):
    files = {
        "08. Audit and Governance/Go Validator Audit 2026-06-21.md": "go audit\n",
        "08. Audit and Governance/P0 P1 P2 Workflow Residue Audit 2026-06-21.md": "workflow audit\n",
        "Audit/command-center-ui-navigation-audit-2026-06-18.md": "ui audit\n",
        "Audit/SMB-SaaS-Parallel-Implementation-Plan-2026-06-18.md": "smb plan\n",
    }
    targets = {
        "08. Audit and Governance/Go Validator Audit 2026-06-21.md": (
            "promote",
            "08. Audits/Go Validator Audit 2026-06-21.md",
        ),
        "08. Audit and Governance/P0 P1 P2 Workflow Residue Audit 2026-06-21.md": (
            "promote",
            "08. Audits/P0 P1 P2 Workflow Residue Audit 2026-06-21.md",
        ),
        "Audit/command-center-ui-navigation-audit-2026-06-18.md": (
            "promote",
            "08. Audits/command-center-ui-navigation-audit-2026-06-18.md",
        ),
        "Audit/SMB-SaaS-Parallel-Implementation-Plan-2026-06-18.md": (
            "archive",
            "09. Archive/Legacy Audit Roots - Archived/Audit/SMB-SaaS-Parallel-Implementation-Plan-2026-06-18.md",
        ),
    }
    operations = []
    for source_rel in sorted(files):
        source = root / source_rel
        write(source, files[source_rel])
        action, target_rel = targets[source_rel]
        operations.append(
            {
                "source_path": source_rel,
                "action": action,
                "target_path": target_rel,
                "target_exists": False,
                "bytes": source.stat().st_size,
                "sha256": module.file_sha256(source),
                "reference_count": 0,
                "reference_samples": [],
                "rationale": "test",
                "requires_reference_update": False,
            }
        )
    digest = module.packet_digest(operations)
    phrase = (
        f"Approve legacy audit root cleanup microbatch {digest} exactly as listed in "
        "tmp/legacy-audit-root-cleanup-packet.json."
    )
    packet = {
        "schema": module.PACKET_SCHEMA,
        "status": "ready_for_owner_approval",
        "microbatch_digest": digest,
        "approval_phrase": phrase,
        "operations": operations,
    }
    write_json(module.PACKET, packet)
    return packet


def test_dry_run_does_not_move() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        module = load_apply_module(root)
        packet = seed_packet(root, module)

        report = module.build_report(packet_path=module.PACKET, approval_phrase=packet["approval_phrase"], apply=False)

        assert report["validation"]["status"] == "ok"
        assert report["status"] == "dry_run_ok"
        assert report["summary"]["operation_count"] == 4
        assert (root / "Audit" / "command-center-ui-navigation-audit-2026-06-18.md").exists()
        assert not (root / "08. Audits" / "command-center-ui-navigation-audit-2026-06-18.md").exists()


def test_apply_moves_and_removes_empty_legacy_roots() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        module = load_apply_module(root)
        packet = seed_packet(root, module)

        report = module.build_report(packet_path=module.PACKET, approval_phrase=packet["approval_phrase"], apply=True)

        assert report["validation"]["status"] == "ok"
        assert report["status"] == "applied_legacy_audit_root_cleanup"
        assert report["summary"]["moved_count"] == 4
        assert not (root / "Audit").exists()
        assert not (root / "08. Audit and Governance").exists()
        assert (root / "08. Audits" / "command-center-ui-navigation-audit-2026-06-18.md").exists()
        assert (
            root
            / "09. Archive"
            / "Legacy Audit Roots - Archived"
            / "Audit"
            / "SMB-SaaS-Parallel-Implementation-Plan-2026-06-18.md"
        ).exists()


def test_reference_updates_only_active_surfaces() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        module = load_apply_module(root)
        packet = seed_packet(root, module)
        old_path = "Audit/SMB-SaaS-Parallel-Implementation-Plan-2026-06-18.md"
        new_path = "09. Archive/Legacy Audit Roots - Archived/Audit/SMB-SaaS-Parallel-Implementation-Plan-2026-06-18.md"
        write(root / "memory" / "2026-06-18.md", f"See {old_path}\n")
        write(root / "06. Playbooks" / "Active Workflows.md", f"Plan: {old_path}\n")
        write(root / "scripts" / "pm_implementation_job_queue.py", f'PATH = "{old_path}"\n')
        write(root / "state" / "agent-message-ledger.jsonl", f'{{"path":"{old_path}"}}\n')

        report = module.build_report(packet_path=module.PACKET, approval_phrase=packet["approval_phrase"], apply=True)

        assert report["validation"]["status"] == "ok"
        assert new_path in (root / "memory" / "2026-06-18.md").read_text(encoding="utf-8")
        assert new_path in (root / "06. Playbooks" / "Active Workflows.md").read_text(encoding="utf-8")
        assert new_path in (root / "scripts" / "pm_implementation_job_queue.py").read_text(encoding="utf-8")
        assert old_path in (root / "state" / "agent-message-ledger.jsonl").read_text(encoding="utf-8")
        assert report["summary"]["active_reference_files_updated"] == 3
        assert report["summary"]["skipped_historical_or_generated_reference_files"] == 1


def test_approval_phrase_mismatch_blocks() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        module = load_apply_module(root)
        seed_packet(root, module)

        report = module.build_report(packet_path=module.PACKET, approval_phrase="wrong", apply=True)

        assert report["validation"]["status"] == "blocked"
        assert "approval_phrase_mismatch" in report["validation"]["errors"]
        assert (root / "Audit" / "command-center-ui-navigation-audit-2026-06-18.md").exists()


def test_existing_target_blocks() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        module = load_apply_module(root)
        packet = seed_packet(root, module)
        write(root / "08. Audits" / "command-center-ui-navigation-audit-2026-06-18.md", "existing\n")

        report = module.build_report(packet_path=module.PACKET, approval_phrase=packet["approval_phrase"], apply=True)

        assert report["validation"]["status"] == "blocked"
        assert any(error.startswith("target_exists:") for error in report["validation"]["errors"])
        assert (root / "Audit" / "command-center-ui-navigation-audit-2026-06-18.md").exists()


if __name__ == "__main__":
    test_dry_run_does_not_move()
    test_apply_moves_and_removes_empty_legacy_roots()
    test_reference_updates_only_active_surfaces()
    test_approval_phrase_mismatch_blocks()
    test_existing_target_blocks()
    print("legacy audit root cleanup apply tests passed")
