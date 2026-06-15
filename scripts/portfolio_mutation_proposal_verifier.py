from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import portfolio_mutation_patch_preview_validator as patch_validator
import portfolio_mutation_proposal_schema_validator as schema_validator
import proposal_patch_scope_validator as scope_validator

ROOT = Path(__file__).resolve().parents[1]
PROPOSAL_ROOT = ROOT / "tmp" / "portfolio-mutation-proposals"
OUT_JSON = PROPOSAL_ROOT / "verifier-report.json"
OUT_MD = PROPOSAL_ROOT / "verifier-report.md"
FALSE_AUTHORITY_FLAGS = (
    "apply_allowed",
    "owner_approval_granted",
    "trade_or_account_action_allowed",
)
REQUIRED_TRUE_FLAGS = ("main_session_final_action_required",)
BLOCKING_FRESHNESS = {"stale", "partial", "missing", "contradictory", "manual_dependency"}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def packet_items(path: Path, data: Any) -> list[tuple[str, dict[str, Any]]]:
    if not isinstance(data, dict):
        return []
    if isinstance(data.get("proposals"), list):
        return [(f"{rel(path)}#proposals[{idx}]", item) for idx, item in enumerate(data["proposals"], start=1) if isinstance(item, dict)]
    if data.get("artifact_type") == "wf56_scoped_apply_approval":
        return []
    return [(rel(path), data)]


def exact_material_files() -> list[Path]:
    paths: list[Path] = []
    for subdir in (PROPOSAL_ROOT, PROPOSAL_ROOT / "exact-patch-material"):
        if subdir.exists():
            paths.extend(sorted(subdir.glob("*.json")))
    excluded = {OUT_JSON.name, "proposal-patch-scope-validation.json", "patch-preview-validation.json"}
    return sorted(set(path for path in paths if path.name not in excluded))


def add_finding(findings: list[dict[str, Any]], severity: str, source: str, issue: str, **extra: Any) -> None:
    findings.append({"severity": severity, "source": source, "issue": issue, **extra})


def verify_authority_packet(source: str, packet: dict[str, Any], findings: list[dict[str, Any]]) -> None:
    for key in FALSE_AUTHORITY_FLAGS:
        if packet.get(key) is not False:
            add_finding(findings, "critical", source, f"{key} must be false", actual=packet.get(key))
    for key in REQUIRED_TRUE_FLAGS:
        if packet.get(key) is not True:
            add_finding(findings, "critical", source, f"{key} must be true", actual=packet.get(key))
    patch = packet.get("exact_patch_preview")
    if isinstance(patch, dict):
        for key in FALSE_AUTHORITY_FLAGS:
            if patch.get(key) is not False:
                add_finding(findings, "critical", source, f"exact_patch_preview.{key} must be false", actual=patch.get(key))
        for key in REQUIRED_TRUE_FLAGS:
            if patch.get(key) is not True:
                add_finding(findings, "critical", source, f"exact_patch_preview.{key} must be true", actual=patch.get(key))


def verify_freshness(source: str, packet: dict[str, Any], findings: list[dict[str, Any]]) -> None:
    freshness = packet.get("source_freshness") or {}
    classification = freshness.get("overall_classification") or freshness.get("classification")
    trust = freshness.get("trust_level")
    explicit_blocker = bool(freshness.get("explicit_blocker") or freshness.get("owner_review_required") or freshness.get("review_required"))
    if classification in BLOCKING_FRESHNESS:
        severity = "warning" if explicit_blocker else "critical"
        add_finding(findings, severity, source, "decision-critical freshness is not clean", classification=classification, explicit_blocker=explicit_blocker)
    if trust in {"review_required", "blocked"} and not explicit_blocker:
        add_finding(findings, "critical", source, "review-required trust level lacks explicit blocker", trust_level=trust)


def verify_packet(source_path: Path, source: str, packet: dict[str, Any]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    verify_authority_packet(source, packet, findings)
    verify_freshness(source, packet, findings)
    schema = schema_validator.validate_packet(packet)
    for item in schema.get("errors") or []:
        add_finding(findings, "critical", source, f"schema: {item}")
    for item in schema.get("blockers") or []:
        add_finding(findings, "critical", source, f"schema: {item}")
    for item in scope_validator.validate_packet(source_path, packet):
        findings.append({"source": source, **item})
    if packet.get("exact_patch_preview"):
        semantic, changes = patch_validator.validate_patch_semantics(packet)
        for item in semantic:
            findings.append({"source": source, **item})
        if not changes:
            add_finding(findings, "critical", source, "exact patch preview has no changes")
    return findings


def verify_top_level(path: Path, data: Any) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    if not isinstance(data, dict) or not isinstance(data.get("proposals"), list):
        return findings
    source = rel(path)
    for key in FALSE_AUTHORITY_FLAGS:
        if data.get(key) is not False:
            add_finding(findings, "critical", source, f"top-level {key} must be false", actual=data.get(key))
    if data.get("main_session_final_action_required") is not True:
        add_finding(findings, "critical", source, "top-level main_session_final_action_required must be true", actual=data.get("main_session_final_action_required"))
    authority = data.get("authority") or {}
    for key in FALSE_AUTHORITY_FLAGS:
        if authority.get(key) is not False:
            add_finding(findings, "critical", source, f"authority.{key} must be false", actual=authority.get(key))
    if authority.get("main_session_final_action_required") is not True:
        add_finding(findings, "critical", source, "authority.main_session_final_action_required must be true", actual=authority.get("main_session_final_action_required"))
    return findings


def build_report(input_path: Path) -> dict[str, Any]:
    findings: list[dict[str, Any]] = []
    files = [input_path] if input_path.is_file() else exact_material_files()
    files = [path for path in files if path.exists() and path.suffix.lower() == ".json"]
    packets_checked = 0
    exact_patch_packets = 0
    for path in files:
        try:
            data = load_json(path)
        except Exception as exc:  # noqa: BLE001
            add_finding(findings, "critical", rel(path), f"cannot read JSON: {exc}")
            continue
        findings.extend(verify_top_level(path, data))
        for source, packet in packet_items(path, data):
            packets_checked += 1
            if packet.get("exact_patch_preview"):
                exact_patch_packets += 1
            findings.extend(verify_packet(path, source, packet))
    critical = sum(1 for item in findings if item.get("severity") == "critical")
    warning = sum(1 for item in findings if item.get("severity") == "warning")
    return {
        "schema_version": 1,
        "generated_at_utc": utc_now(),
        "status": "ok" if critical == 0 else "blocked",
        "input": rel(input_path),
        "authority": {
            "apply_allowed": False,
            "owner_approval_granted": False,
            "trade_or_account_action_allowed": False,
            "main_session_final_action_required": True,
            "verifier_is_read_only": True,
            "canonical_writes_performed": False,
        },
        "summary": {
            "files_checked": len(files),
            "packets_checked": packets_checked,
            "exact_patch_packets_checked": exact_patch_packets,
            "critical": critical,
            "warning": warning,
        },
        "findings": findings,
    }


def write_markdown(report: dict[str, Any]) -> None:
    lines = [
        "# Portfolio Mutation Proposal Verifier Report",
        "",
        f"- Status: **{report.get('status')}**",
        f"- Generated: `{report.get('generated_at_utc')}`",
        "- Authority: read-only verifier; apply_allowed=false; owner_approval_granted=false; trade_or_account_action_allowed=false; main_session_final_action_required=true.",
        "",
        "## Summary",
        "",
    ]
    summary = report.get("summary") or {}
    for key in ("files_checked", "packets_checked", "exact_patch_packets_checked", "critical", "warning"):
        lines.append(f"- {key}: {summary.get(key)}")
    if report.get("findings"):
        lines.extend(["", "## Findings", ""])
        for item in report["findings"]:
            lines.append(f"- **{item.get('severity')}** `{item.get('source')}` — {item.get('issue')}")
    OUT_MD.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Read-only verifier for WF64/WF56 portfolio mutation proposal and exact patch artifacts.")
    parser.add_argument("--input", default="tmp/portfolio-mutation-proposals", help="Proposal JSON file or proposal directory to verify")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    report = build_report(ROOT / args.input)
    if args.write:
        PROPOSAL_ROOT.mkdir(parents=True, exist_ok=True)
        OUT_JSON.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        write_markdown(report)
        print(f"wrote {OUT_JSON}")
        print(f"wrote {OUT_MD}")
    print(f"portfolio_mutation_proposal_verifier: {report['status']} ({report['summary']['critical']} critical, {report['summary']['warning']} warning)")
    return 1 if report["summary"]["critical"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
