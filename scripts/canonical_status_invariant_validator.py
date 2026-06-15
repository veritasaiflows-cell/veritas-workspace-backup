from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from board_state_contract import canonical_action_state


def canonical_status(value: Any) -> str:
    return canonical_action_state(str(value or "").replace("_", " ").replace("-", " "))

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "tmp" / "canonical-status-invariant-validation.json"
OWNER_SURFACES = {
    "coverage_watchlist",
    "execution_board",
    "portfolio_snapshot",
    "portfolio_config",
}
FORBIDDEN_TRANSITIONS = {
    ("DO NOT TOUCH", "DEPLOYABLE NOW"),
    ("BLOCKED", "DEPLOYABLE NOW"),
    ("POST-EARNINGS REVIEW", "DEPLOYABLE NOW"),
}
AUTHORITY_FALSE_FIELDS = (
    "owner_approval_granted",
    "apply_allowed",
    "canonical_mutation_allowed",
    "portfolio_mutation_allowed",
    "trade_or_account_action_allowed",
)


def relpath(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def load_packets(path: Path) -> list[tuple[Path, dict[str, Any]]]:
    def expand(source: Path, data: Any) -> list[tuple[Path, dict[str, Any]]]:
        if isinstance(data, dict) and isinstance(data.get("proposals"), list):
            return [(source, item) for item in data["proposals"] if isinstance(item, dict)]
        if isinstance(data, dict):
            return [(source, data)]
        return []

    if path.is_dir():
        out = []
        for item in sorted(path.glob("*.json")):
            try:
                data = json.loads(item.read_text(encoding="utf-8"))
            except Exception:
                continue
            out.extend(expand(item, data))
        return out
    data = json.loads(path.read_text(encoding="utf-8"))
    packets = expand(path, data)
    if not packets:
        raise ValueError("proposal input must be a JSON object or directory of JSON objects")
    return packets


def validate_packet(source: Path, packet: dict[str, Any]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    if packet.get("mutation_type") != "canonical_status_move":
        return findings
    current = packet.get("current_status_tuple") or {}
    proposed = packet.get("proposed_status_tuple") or {}
    if not isinstance(current, dict) or not isinstance(proposed, dict):
        return [{"severity": "critical", "source": relpath(source), "issue": "status tuples must be objects"}]
    for label, status_tuple in (("current_status_tuple", current), ("proposed_status_tuple", proposed)):
        missing = sorted(OWNER_SURFACES - set(status_tuple))
        if missing:
            findings.append({"severity": "critical", "source": relpath(source), "issue": f"{label} missing owner surfaces", "missing": missing})
    for surface in sorted(set(current) & set(proposed)):
        transition = (canonical_status(current.get(surface)), canonical_status(proposed.get(surface)))
        if transition in FORBIDDEN_TRANSITIONS:
            findings.append({"severity": "critical", "source": relpath(source), "surface": surface, "issue": "forbidden status transition without explicit owner decision", "transition": list(transition)})
    affected = packet.get("affected_owner_surfaces")
    if not isinstance(affected, list) or not affected:
        findings.append({"severity": "critical", "source": relpath(source), "issue": "affected_owner_surfaces must list touched owner surfaces"})
    else:
        unknown = sorted(set(str(item) for item in affected) - OWNER_SURFACES)
        if unknown:
            findings.append({"severity": "critical", "source": relpath(source), "issue": "affected_owner_surfaces includes unknown surfaces", "surfaces": unknown})
        tuple_keys = set(current) | set(proposed)
        if not set(str(item) for item in affected).issubset(tuple_keys):
            findings.append({"severity": "critical", "source": relpath(source), "issue": "affected_owner_surfaces must be subset of status tuple keys"})
    deltas = packet.get("field_level_deltas")
    if not isinstance(deltas, list):
        findings.append({"severity": "critical", "source": relpath(source), "issue": "field_level_deltas must be a list"})
    else:
        required_delta_keys = {"owner_surface", "field", "from", "to", "mutation_class"}
        for index, delta in enumerate(deltas):
            if not isinstance(delta, dict):
                findings.append({"severity": "critical", "source": relpath(source), "issue": "field_level_delta must be an object", "index": index})
                continue
            missing_delta = sorted(required_delta_keys - set(delta))
            if missing_delta:
                findings.append({"severity": "critical", "source": relpath(source), "issue": "field_level_delta missing required keys", "index": index, "missing": missing_delta})
            if delta.get("owner_surface") and str(delta.get("owner_surface")) not in OWNER_SURFACES:
                findings.append({"severity": "critical", "source": relpath(source), "issue": "field_level_delta has unknown owner_surface", "index": index, "owner_surface": delta.get("owner_surface")})
    invariant_checks = packet.get("canonical_invariant_checks") or {}
    if not isinstance(invariant_checks, dict) or invariant_checks.get("status") not in {"pass", "review_only_pass"}:
        findings.append({"severity": "critical", "source": relpath(source), "issue": "canonical_invariant_checks.status must pass before proposal is usable"})
    for field in AUTHORITY_FALSE_FIELDS:
        if packet.get(field) is True:
            findings.append({"severity": "critical", "source": relpath(source), "field": field, "issue": "canonical-status proposal may not grant authority"})
    return findings


def build_report(path: Path) -> dict[str, Any]:
    packets = load_packets(path)
    findings: list[dict[str, Any]] = []
    checked = 0
    for source, packet in packets:
        if packet.get("mutation_type") == "canonical_status_move":
            checked += 1
        findings.extend(validate_packet(source, packet))
    critical = sum(1 for item in findings if item.get("severity") == "critical")
    warning = sum(1 for item in findings if item.get("severity") == "warning")
    return {
        "generated_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "status": "ok" if critical == 0 else "blocked",
        "authority": {"canonical_mutation_allowed": False, "portfolio_mutation_allowed": False, "trade_or_account_action_allowed": False},
        "summary": {"canonical_status_packets_checked": checked, "critical": critical, "warning": warning},
        "findings": findings,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate canonical status move invariants in review-only proposals.")
    parser.add_argument("input", nargs="?", default="tmp/portfolio-mutation-proposals")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    report = build_report(ROOT / args.input)
    if args.write:
        OUT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(f"wrote {OUT}")
    print(f"canonical_status_invariant_validator: {report['status']} ({report['summary']['critical']} critical, {report['summary']['warning']} warning)")
    return 1 if report["summary"]["critical"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
