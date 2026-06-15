from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = ROOT / "tmp" / "sec-evidence-packets" / "current-sec-evidence.json"
DEFAULT_OUTPUT = ROOT / "tmp" / "sec-evidence-packets" / "current-sec-evidence-validation.json"

REQUIRED_FALSE = {
    "canonical_mutation_allowed_by_this_packet",
    "portfolio_mutation_allowed_by_this_packet",
    "proposal_apply_allowed",
    "owner_approval_granted",
    "owner_approval_inference_allowed",
    "trade_execution_allowed",
    "trade_or_account_action_allowed",
    "brokerage_account_action_allowed",
    "money_movement_allowed",
    "sizing_allocation_action_allowed",
    "model_ranked_deployment_allowed",
}

REQUIRED_TRUE = {"review_packet_generation_allowed", "official_source_evidence_allowed"}

FORBIDDEN_PATTERNS = {
    "win_probability": re.compile(r"\bwin\s+probability\b|\bwin_probability\b", re.I),
    "win_rate": re.compile(r"\bwin\s+rate\b|\bwin_rate\b", re.I),
    "expected_return": re.compile(r"\bexpected\s+return\b|\bexpected_return\b", re.I),
    "percent_chance": re.compile(r"\b\d+(?:\.\d+)?\s*%\s+(?:chance|likelihood)\b", re.I),
    "calibrated_score": re.compile(r"\bcalibrated\s+(?:score|readiness\s+score)\b", re.I),
    "model_ranked": re.compile(r"\bmodel[-_\s]+ranked\b", re.I),
    "trade_approved": re.compile(r"\btrade\s+approved\b", re.I),
}


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def walk_strings(value: Any, path: str = "$") -> list[tuple[str, str]]:
    found: list[tuple[str, str]] = []
    if isinstance(value, dict):
        for key, item in value.items():
            found.append((f"{path}.{key}", str(key)))
            found.extend(walk_strings(item, f"{path}.{key}"))
    elif isinstance(value, list):
        for idx, item in enumerate(value):
            found.extend(walk_strings(item, f"{path}[{idx}]"))
    elif isinstance(value, str):
        found.append((path, value))
    return found


def validate_authority(authority: Any, *, path: str, findings: list[dict[str, Any]]) -> None:
    if not isinstance(authority, dict):
        findings.append({"severity": "critical", "issue": "authority_not_object", "path": path})
        return
    for field in REQUIRED_FALSE:
        if authority.get(field) is not False:
            findings.append({"severity": "critical", "issue": "authority_field_not_false", "path": f"{path}.{field}", "value": authority.get(field)})
    for field in REQUIRED_TRUE:
        if authority.get(field) is not True:
            findings.append({"severity": "warning", "issue": "authority_field_not_true", "path": f"{path}.{field}", "value": authority.get(field)})


def validate_packet(data: dict[str, Any]) -> dict[str, Any]:
    findings: list[dict[str, Any]] = []
    if data.get("schema_version") != 1:
        findings.append({"severity": "critical", "issue": "unexpected_schema_version", "value": data.get("schema_version")})
    if data.get("evidence_class") != "official_sec_edgar":
        findings.append({"severity": "critical", "issue": "unexpected_evidence_class", "value": data.get("evidence_class")})
    if not str(data.get("sec_user_agent", "")).strip() or "admin@example.com" in str(data.get("sec_user_agent", "")):
        findings.append({"severity": "critical", "issue": "invalid_sec_user_agent", "value": data.get("sec_user_agent")})
    validate_authority(data.get("authority"), path="$.authority", findings=findings)
    packets = data.get("packets")
    if not isinstance(packets, list) or not packets:
        findings.append({"severity": "critical", "issue": "missing_packets"})
        packets = []
    for idx, packet in enumerate(packets):
        p = f"$.packets[{idx}]"
        for field in ["ticker", "evidence_class", "retrievals", "provenance", "authority"]:
            if field not in packet:
                findings.append({"severity": "critical", "issue": "packet_missing_required_field", "path": f"{p}.{field}"})
        if packet.get("evidence_class") != "official_sec_edgar":
            findings.append({"severity": "critical", "issue": "packet_bad_evidence_class", "path": f"{p}.evidence_class"})
        if not packet.get("cik"):
            findings.append({"severity": "critical", "issue": "packet_missing_cik", "path": f"{p}.cik", "ticker": packet.get("ticker")})
        filings = packet.get("retrievals", {}).get("filings") if isinstance(packet.get("retrievals"), dict) else None
        if not isinstance(filings, dict):
            findings.append({"severity": "critical", "issue": "packet_missing_filings", "path": f"{p}.retrievals.filings"})
        else:
            for form in ["10-K", "10-Q", "8-K"]:
                if form not in filings:
                    findings.append({"severity": "warning", "issue": "packet_missing_requested_form", "path": f"{p}.retrievals.filings.{form}", "ticker": packet.get("ticker")})
        provenance = packet.get("provenance")
        if not isinstance(provenance, dict) or not provenance.get("retrieved_at_utc") or not provenance.get("sec_skill_sha256"):
            findings.append({"severity": "critical", "issue": "packet_incomplete_provenance", "path": f"{p}.provenance", "ticker": packet.get("ticker")})
        validate_authority(packet.get("authority"), path=f"{p}.authority", findings=findings)
    for path, text in walk_strings(data):
        for name, pattern in FORBIDDEN_PATTERNS.items():
            if pattern.search(text):
                findings.append({"severity": "critical", "issue": "forbidden_probability_or_execution_language", "pattern": name, "path": path})
    critical = sum(1 for item in findings if item.get("severity") == "critical")
    warning = sum(1 for item in findings if item.get("severity") == "warning")
    return {
        "schema_version": 1,
        "validated_artifact": str(DEFAULT_INPUT.relative_to(ROOT).as_posix()) if DEFAULT_INPUT.exists() else "",
        "status": "critical" if critical else ("warning" if warning else "ok"),
        "summary": {"critical": critical, "warning": warning, "findings": len(findings), "packets_checked": len(packets)},
        "findings": findings,
    }


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate Veritas SEC evidence packet authority/provenance contract.")
    parser.add_argument("--input", default=str(DEFAULT_INPUT))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    input_path = Path(args.input)
    report = validate_packet(load_json(input_path))
    report["validated_artifact"] = input_path.relative_to(ROOT).as_posix() if input_path.is_relative_to(ROOT) else str(input_path)
    if args.write:
        write_json(Path(args.output), report)
    print(json.dumps({"status": report["status"], "summary": report["summary"]}, sort_keys=True))
    return 1 if report["summary"]["critical"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
