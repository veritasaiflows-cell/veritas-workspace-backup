from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = ROOT / "tmp" / "proposal-patch-scope-validation.json"
APPROVED_PATHS = {
    "04. Research/Coverage and Watchlist.md",
    "03. Portfolio/Execution Board.md",
    "03. Portfolio/Portfolio Snapshot.md",
    "07. Risk/Risk Rules.md",
    "tmp/portfolio-config.json",
}
APPROVED_PREFIXES = (
    "tmp/portfolio-mutation-proposals/",
)
CATEGORY_OWNER_PATHS = {
    "entry_band": {"03. Portfolio/Execution Board.md", "tmp/portfolio-config.json"},
    "ticker_state": {"03. Portfolio/Execution Board.md", "04. Research/Coverage and Watchlist.md", "tmp/portfolio-config.json"},
    "review_note": {"03. Portfolio/Execution Board.md", "03. Portfolio/Portfolio Snapshot.md", "04. Research/Coverage and Watchlist.md", "07. Risk/Risk Rules.md"},
    "sleeve": {"03. Portfolio/Portfolio Snapshot.md"},
    "sizing": {"03. Portfolio/Portfolio Snapshot.md", "07. Risk/Risk Rules.md"},
    "sector_posture": {"03. Portfolio/Portfolio Snapshot.md", "07. Risk/Risk Rules.md"},
    "earnings_state": {"03. Portfolio/Execution Board.md", "04. Research/Coverage and Watchlist.md", "tmp/portfolio-config.json"},
}
FORBIDDEN_FRAGMENTS = (
    "brokerage",
    "account",
    "orders",
    "credential",
    "secret",
    "token",
    ".openclaw/openclaw.json",
    "exec-approvals",
)
FORBIDDEN_PORTFOLIO_MUTATION_FIELDS = {
    "owner_approval_granted",
    "portfolio_mutation_allowed",
    "trade_or_account_action_allowed",
    "execution_entitlement_granted",
}


def re_absolute_windows_path(path: str) -> bool:
    return len(path) > 2 and path[1] == ":" and path[2] in {"/", "\\"}


def relpath(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def load_packets(path: Path) -> list[tuple[Path, dict[str, Any]]]:
    def expand(source: Path, data: Any) -> list[tuple[Path, dict[str, Any]]]:
        if isinstance(data, dict) and data.get("artifact_type") == "wf56_scoped_apply_approval":
            return []
        if isinstance(data, dict) and isinstance(data.get("proposals"), list):
            return [(source, item) for item in data["proposals"] if isinstance(item, dict)]
        if isinstance(data, dict):
            return [(source, data)]
        return []

    if path.is_dir():
        packets = []
        for item in sorted(path.glob("*.json")):
            try:
                data = json.loads(item.read_text(encoding="utf-8"))
            except Exception:
                continue
            packets.extend(expand(item, data))
        return packets
    data = json.loads(path.read_text(encoding="utf-8"))
    packets = expand(path, data)
    if not packets:
        raise ValueError("proposal input must be a JSON object or directory of JSON objects")
    return packets


def proposed_paths(packet: dict[str, Any]) -> list[str]:
    paths: list[str] = []
    for key in ("proposed_files_to_edit", "affected_files", "target_files"):
        value = packet.get(key)
        if isinstance(value, list):
            paths.extend(str(item) for item in value)
    for patch_key in ("patch", "proposed_patch", "exact_patch_preview"):
        patch = packet.get(patch_key) or {}
        if isinstance(patch, dict):
            for key in ("file", "path", "target", "target_file"):
                if patch.get(key):
                    paths.append(str(patch[key]))
            changes = patch.get("changes")
            if isinstance(changes, list):
                for change in changes:
                    if isinstance(change, dict):
                        for key in ("file", "path", "target", "target_file"):
                            if change.get(key):
                                paths.append(str(change[key]))
    return sorted(set(p.replace("\\", "/") for p in paths if str(p).strip()))


def patch_categories(packet: dict[str, Any]) -> list[str]:
    categories: list[str] = []
    for key in ("adjustment_category", "proposal_category", "mutation_category"):
        if packet.get(key):
            categories.append(str(packet[key]))
    for patch_key in ("patch", "proposed_patch", "exact_patch_preview"):
        patch = packet.get(patch_key) or {}
        if not isinstance(patch, dict):
            continue
        if patch.get("adjustment_category"):
            categories.append(str(patch["adjustment_category"]))
        changes = patch.get("changes")
        if isinstance(changes, list):
            for change in changes:
                if isinstance(change, dict) and change.get("adjustment_category"):
                    categories.append(str(change["adjustment_category"]))
    return sorted(set(item for item in categories if item))


def validate_packet(source: Path, packet: dict[str, Any]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    paths = proposed_paths(packet)
    categories = patch_categories(packet)
    if not paths:
        findings.append({"severity": "warning", "source": relpath(source), "issue": "no proposed edit paths found; scope cannot be verified"})
    for path in paths:
        lowered = path.lower()
        if path.startswith("/") or re_absolute_windows_path(path) or ".." in Path(path).parts:
            findings.append({"severity": "critical", "source": relpath(source), "path": path, "issue": "absolute path or traversal is not allowed"})
        if any(fragment in lowered for fragment in FORBIDDEN_FRAGMENTS):
            findings.append({"severity": "critical", "source": relpath(source), "path": path, "issue": "forbidden edit surface"})
        if path not in APPROVED_PATHS and not path.startswith(APPROVED_PREFIXES):
            findings.append({"severity": "critical", "source": relpath(source), "path": path, "issue": "path outside approved WF56 portfolio proposal scope"})
        for category in categories:
            allowed = CATEGORY_OWNER_PATHS.get(category)
            if allowed is None:
                findings.append({"severity": "critical", "source": relpath(source), "path": path, "category": category, "issue": "unsupported adjustment category"})
            elif path in APPROVED_PATHS and path not in allowed:
                findings.append({"severity": "critical", "source": relpath(source), "path": path, "category": category, "issue": "target file does not own adjustment category"})
    for field in FORBIDDEN_PORTFOLIO_MUTATION_FIELDS:
        if packet.get(field) is True:
            findings.append({"severity": "critical", "source": relpath(source), "field": field, "issue": "proposal may not grant authority"})
    if packet.get("apply_allowed") is True or packet.get("canonical_mutation_allowed") is True:
        findings.append({"severity": "critical", "source": relpath(source), "issue": "proposal cannot be apply-capable"})
    if packet.get("main_session_final_action_required") is False:
        findings.append({"severity": "critical", "source": relpath(source), "field": "main_session_final_action_required", "issue": "main-session final action must remain required"})
    return findings


def build_report(path: Path) -> dict[str, Any]:
    packets = load_packets(path)
    findings: list[dict[str, Any]] = []
    for source, packet in packets:
        findings.extend(validate_packet(source, packet))
    critical = sum(1 for item in findings if item.get("severity") == "critical")
    warning = sum(1 for item in findings if item.get("severity") == "warning")
    return {
        "generated_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "status": "ok" if critical == 0 else "blocked",
        "authority": {"apply_allowed": False, "portfolio_mutation_allowed": False, "trade_or_account_action_allowed": False},
        "input": str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path),
        "summary": {"packets_checked": len(packets), "critical": critical, "warning": warning},
        "findings": findings,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate review-only proposal patch scope.")
    parser.add_argument("input", nargs="?", default="tmp/portfolio-mutation-proposals", help="Proposal JSON file or directory")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    report = build_report(ROOT / args.input)
    if args.write:
        DEFAULT_OUT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(f"wrote {DEFAULT_OUT}")
    print(f"proposal_patch_scope_validator: {report['status']} ({report['summary']['critical']} critical, {report['summary']['warning']} warning)")
    return 1 if report["summary"]["critical"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
