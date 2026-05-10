from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

WORKSPACE = Path(__file__).resolve().parents[1]

FORBIDDEN_PATTERNS: list[tuple[str, str]] = [
    (r"\bbuy now\b", "uses direct trade instruction"),
    (r"\badd now\b", "uses direct trade instruction"),
    (r"\bready now\b", "implies immediate readiness authority"),
    (r"\bresolved now\b", "overstates unresolved truth"),
    (r"\bblocker cleared\b", "clears a blocker in summary language"),
    (r"\bpromote\b.+\bto\b", "uses promotion language that can imply authority"),
]

DEPLOYABLE_NOW_PATTERNS = (r"\bis deployable now\b", r"\bare deployable now\b")
DEPLOYABLE_NOW_EXCEPTIONS = (
    "nothing is deployable now",
    "no name is deployable now",
    "no names are deployable now",
)

ROUTING_MARKERS = ("read ", "review ", "confirm ", "reconcile ", "watch ", "defer ", "review-only")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Lint a bounded commercial brief draft against its packet contract.")
    parser.add_argument("--packet", required=True)
    parser.add_argument("--draft", required=True)
    return parser.parse_args()



def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))



def citation_markers(path: str) -> set[str]:
    clean = path.replace("\\", "/")
    without_ext = clean[:-3] if clean.endswith(".md") else clean
    base = without_ext.split("/")[-1]
    return {
        clean,
        without_ext,
        f"[[{without_ext}]]",
        f"[[{without_ext.replace('/', '\\')}]]",
        f"[[{base}]]",
    }



def lint(packet: dict[str, Any], draft_text: str) -> dict[str, Any]:
    issues: list[str] = []
    lowered = draft_text.lower()

    if str(packet.get("consumer_posture") or "") != "review_only":
        issues.append("packet consumer_posture is not review_only")
    if bool(packet.get("canonical_mutation_allowed")):
        issues.append("packet incorrectly allows canonical mutation")

    if not any(marker in lowered for marker in ROUTING_MARKERS):
        issues.append("draft is missing review/routing language")

    citations = packet.get("required_citations") or []
    has_citation = False
    for citation in citations:
        markers = {m.lower() for m in citation_markers(str(citation))}
        if any(marker in lowered for marker in markers):
            has_citation = True
            break
    if not has_citation:
        issues.append("draft does not cite any required owner layer")

    deployable_now_hit = any(re.search(pattern, lowered) for pattern in DEPLOYABLE_NOW_PATTERNS)
    if deployable_now_hit and not any(exception in lowered for exception in DEPLOYABLE_NOW_EXCEPTIONS):
        issues.append("publishes deployable-now state")

    for pattern, reason in FORBIDDEN_PATTERNS:
        if re.search(pattern, lowered):
            issues.append(reason)

    unresolved_truths = packet.get("unresolved_truths") or []
    if unresolved_truths and not any(token in lowered for token in ("unresolved", "warning", "review-only", "owner", "confirm")):
        issues.append("draft does not visibly preserve unresolved-truth posture")

    return {
        "status": "ok" if not issues else "failed",
        "issue_count": len(issues),
        "issues": issues,
    }



def main() -> None:
    args = parse_args()
    packet_path = Path(args.packet)
    draft_path = Path(args.draft)
    packet = load_json(packet_path)
    draft_text = draft_path.read_text(encoding="utf-8")
    result = {
        "packet": str(packet_path.relative_to(WORKSPACE)).replace("\\", "/") if packet_path.is_absolute() else str(packet_path),
        "draft": str(draft_path.relative_to(WORKSPACE)).replace("\\", "/") if draft_path.is_absolute() else str(draft_path),
    }
    result.update(lint(packet, draft_text))
    print(json.dumps(result, indent=2))
    if result["status"] != "ok":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
