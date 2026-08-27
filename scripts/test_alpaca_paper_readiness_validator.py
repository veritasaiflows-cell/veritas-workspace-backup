#!/usr/bin/env python3
"""Regression tests for WF63 readiness validation residue handling."""

from __future__ import annotations

import importlib.util
import json
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "alpaca_paper_readiness_validator.py"


def load_module():
    spec = importlib.util.spec_from_file_location("alpaca_paper_readiness_validator", MODULE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load validator module")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def expect(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def test_utf16_json_artifacts_parse(errors: list[str]) -> None:
    mod = load_module()
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        artifacts = root / "tmp" / "alpaca-paper-readiness"
        artifacts.mkdir(parents=True)
        path = artifacts / "artifact.json"
        payload = {
            "status": "ok",
            "secrets_redacted": True,
            "credential_source": {"secret_values_persisted": False},
        }
        path.write_bytes(json.dumps(payload).encode("utf-16"))
        expect(mod.load_json(path)["status"] == "ok", "UTF-16 JSON should parse", errors)

        mod.ROOT = root
        mod.ARTIFACT_SCAN_DIR = artifacts
        findings = mod.scan_readiness_artifacts_for_secrets()
        expect(findings == [], f"UTF-16 redacted artifact should not produce secret findings: {findings}", errors)


def test_live_endpoint_reference_allowlist_stays_granular(errors: list[str]) -> None:
    mod = load_module()
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        scripts_dir = root / "scripts"
        scripts_dir.mkdir()

        allowed_file = scripts_dir / "wf55_outcome_ledger_v2.py"
        allowed_file.write_text('LIVE_ENDPOINT = "https://api.alpaca.markets"\n', encoding="utf-8")

        mod.ROOT = root
        mod.SCAN_DIRS = [scripts_dir]
        findings = mod.scan_active_forbidden_patterns()
        expect(findings == [], f"allowed live-endpoint reference should not block: {findings}", errors)

        allowed_file.write_text(
            'LIVE_ENDPOINT = "https://api.alpaca.markets"\n'
            'DANGEROUS = "POST /v2/orders"\n',
            encoding="utf-8",
        )
        findings = mod.scan_active_forbidden_patterns()
        expect(
            findings == [{"path": "scripts/wf55_outcome_ledger_v2.py", "pattern": "POST /v2/orders"}],
            f"other forbidden patterns should still block in allowlisted files: {findings}",
            errors,
        )


def main() -> int:
    errors: list[str] = []
    test_utf16_json_artifacts_parse(errors)
    test_live_endpoint_reference_allowlist_stays_granular(errors)
    if errors:
        print(json.dumps({"status": "failed", "errors": errors}, indent=2))
        return 1
    print(json.dumps({"status": "ok", "tests": 2}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
