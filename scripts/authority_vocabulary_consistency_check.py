from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "tmp" / "authority-vocabulary-consistency.json"
DEFAULT_PATHS = [
    ROOT / "tmp" / "portfolio-mutation-proposals",
    ROOT / "tmp" / "canonical-note-patch-proposal.md",
    ROOT / "tmp" / "portfolio-snapshot-patch-proposal.md",
    ROOT / "tmp" / "full-portfolio-view.json",
]
FORBIDDEN_PATTERNS = {
    "trade_action": re.compile(r"\b(place|submit|execute)\s+(?:a\s+)?(?:trade|order)\b", re.IGNORECASE),
    "approval_granted": re.compile(r"\b(?:owner\s+)?approval\s+(?:is\s+)?granted\b", re.IGNORECASE),
    "auto_approved": re.compile(r"\bauto[-\s]?approved\b", re.IGNORECASE),
    "clear_to_deploy": re.compile(r"\bclear\s+to\s+deploy\b", re.IGNORECASE),
    "guaranteed_return": re.compile(r"\bguaranteed\s+return\b", re.IGNORECASE),
    "win_probability": re.compile(r"\bwin\s+probability\b", re.IGNORECASE),
    "deploy_probability": re.compile(r"\bdeploy\s+probability\b", re.IGNORECASE),
}
REQUIRED_BOUNDARY_PATTERN = re.compile(r"review[-\s]?only|no .*trade|not canonical|no portfolio mutation", re.IGNORECASE)


def iter_files(paths: Iterable[Path]) -> list[Path]:
    files: list[Path] = []
    for path in paths:
        if path.is_dir():
            files.extend(sorted(p for p in path.rglob("*") if p.suffix.lower() in {".json", ".md", ".txt"}))
        elif path.exists():
            files.append(path)
    return files


def text_for(path: Path) -> str:
    if path.suffix.lower() == ".json":
        try:
            return json.dumps(json.loads(path.read_text(encoding="utf-8")), sort_keys=True)
        except Exception:
            return path.read_text(encoding="utf-8", errors="replace")
    return path.read_text(encoding="utf-8", errors="replace")


def build_report(paths: list[Path]) -> dict:
    findings: list[dict] = []
    files = iter_files(paths)
    for path in files:
        rel = str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path)
        text = text_for(path)
        for label, pattern in FORBIDDEN_PATTERNS.items():
            for match in pattern.finditer(text):
                findings.append({"severity": "critical", "file": rel, "issue": "forbidden authority vocabulary", "label": label, "snippet": match.group(0)[:120]})
        if path.suffix.lower() in {".md", ".json"} and "proposal" in rel.lower() and not REQUIRED_BOUNDARY_PATTERN.search(text):
            findings.append({"severity": "warning", "file": rel, "issue": "proposal/report should contain visible review-only/no-authority boundary language"})
    critical = sum(1 for item in findings if item.get("severity") == "critical")
    warning = sum(1 for item in findings if item.get("severity") == "warning")
    return {
        "generated_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "status": "ok" if critical == 0 else "blocked",
        "authority": {"apply_allowed": False, "owner_approval_granted": False, "trade_or_account_action_allowed": False},
        "summary": {"files_checked": len(files), "critical": critical, "warning": warning},
        "findings": findings,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Check authority vocabulary in proposal/report artifacts.")
    parser.add_argument("paths", nargs="*", help="Files or directories to scan")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    paths = [ROOT / p for p in args.paths] if args.paths else DEFAULT_PATHS
    report = build_report(paths)
    if args.write:
        OUT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(f"wrote {OUT}")
    print(f"authority_vocabulary_consistency_check: {report['status']} ({report['summary']['critical']} critical, {report['summary']['warning']} warning)")
    return 1 if report["summary"]["critical"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
