#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "security_warning_ledger.py"


def load_module():
    spec = importlib.util.spec_from_file_location("security_warning_ledger", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_security_warning_ledger_dedupes_and_preserves_config_stopline() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        source = Path(tmpdir) / "cyber-security-daily-audit.json"
        finding = {
            "severity": "warning",
            "source": "openclaw_security_audit_basic",
            "message": "Reverse proxy headers are not trusted",
            "remediation": "Set gateway.trustedProxies or keep local-only.",
            "evidence": "gateway.bind is loopback",
        }
        deep_finding = dict(finding)
        deep_finding["source"] = "openclaw_security_audit_deep"
        source.write_text(json.dumps({"findings": [finding, deep_finding]}), encoding="utf-8")

        payload = module.build_payload(source, Path(tmpdir) / "missing-decisions.json")

        assert payload["status"] == "warning"
        assert payload["summary"]["warning_count"] == 1
        assert payload["summary"]["owner_decision_required_count"] == 1
        assert payload["warnings"][0]["status"] == "open"
        assert payload["warnings"][0]["sources"] == [
            "openclaw_security_audit_basic",
            "openclaw_security_audit_deep",
        ]
        assert payload["authority_boundary"]["config_auth_runtime_mutation_allowed"] is False
        assert payload["authority_boundary"]["network_exposure_change_allowed"] is False


def test_security_warning_ledger_applies_scoped_accepted_risk_decision() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        source = Path(tmpdir) / "cyber-security-daily-audit.json"
        decisions = Path(tmpdir) / "security-warning-decisions.json"
        finding = {
            "severity": "warning",
            "source": "openclaw_security_audit_deep",
            "message": "Reverse proxy headers are not trusted",
            "remediation": "Set gateway.trustedProxies or keep local-only.",
            "evidence": "gateway.bind is loopback and no proxy is configured",
        }
        source.write_text(json.dumps({"findings": [finding]}), encoding="utf-8")
        decisions.write_text(json.dumps({
            "decisions": [{
                "match_message": "Reverse proxy headers are not trusted",
                "evidence_contains": ["gateway.bind is loopback"],
                "status": "accepted_risk",
                "reason": "Local-only gateway without a reverse proxy.",
                "decided_by": "owner",
                "decided_at_utc": "2026-08-08T00:00:00Z",
            }],
        }), encoding="utf-8")

        payload = module.build_payload(source, decisions)

        assert payload["status"] == "accepted_risk"
        assert payload["summary"]["open_warning_count"] == 0
        assert payload["summary"]["accepted_risk_count"] == 1
        assert payload["summary"]["owner_decision_required_count"] == 0
        assert payload["warnings"][0]["status"] == "accepted_risk"
        assert payload["warnings"][0]["accepted_risk"] is True


def test_security_warning_ledger_matches_literal_quoted_evidence() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        source = Path(tmpdir) / "cyber-security-daily-audit.json"
        decisions = Path(tmpdir) / "security-warning-decisions.json"
        source.write_text(json.dumps({"findings": [{
            "severity": "warning",
            "source": "openclaw_security_audit_deep",
            "message": "Potential multi-user setup detected (personal-assistant model warning)",
            "remediation": "Split trust boundaries.",
            "evidence": 'channels.telegram.groupPolicy="allowlist"',
        }]}), encoding="utf-8")
        decisions.write_text(json.dumps({"decisions": [{
            "match_message": "Potential multi-user setup detected (personal-assistant model warning)",
            "evidence_contains": ['groupPolicy="allowlist"'],
            "status": "accepted_risk",
            "reason": "One trusted operator with an allowlisted channel.",
        }]}), encoding="utf-8")

        payload = module.build_payload(source, decisions)

        assert payload["summary"]["open_warning_count"] == 0
        assert payload["summary"]["accepted_risk_count"] == 1


if __name__ == "__main__":
    test_security_warning_ledger_dedupes_and_preserves_config_stopline()
    test_security_warning_ledger_applies_scoped_accepted_risk_decision()
    test_security_warning_ledger_matches_literal_quoted_evidence()
    print("security warning ledger tests passed")
