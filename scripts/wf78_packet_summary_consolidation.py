"""Preview shared summary consolidation for WF78 routing/promotion packets.

This proof identifies repeated authority/summary/validation block patterns
across active WF78 packet families. It does not remove fields or change routing.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
OUT = TMP / "wf78-packet-summary-consolidation.json"
SHARED_HEADER_OUT = TMP / "wf78-packet-shared-header.json"

PACKET_GLOBS = [
    "wf78-tier-a-final-promotion-packet*.json",
    "wf78-tier-b-final-promotion-packet*.json",
    "wf78-auto-tier-routing.json",
    "wf78-routing-dashboard.json",
    "wf78-production-tier-adjudication.json",
    "wf78-tier-b-research-packets.json",
    "wf78-tier-b-evidence-repair.json",
]

REPEATED_KEYS = {
    "authority",
    "authority_boundary",
    "summary",
    "validation",
    "status",
    "stop_lines",
    "stoplines",
    "source_artifacts",
    "proof_artifacts",
    "generated_at_utc",
}


def relpath(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def safe_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def packet_paths() -> list[Path]:
    paths: list[Path] = []
    for pattern in PACKET_GLOBS:
        paths.extend(sorted(TMP.glob(pattern)))
    return sorted(dict.fromkeys(paths))


def count_keys(data: Any, *, max_depth: int = 4) -> Counter[str]:
    counts: Counter[str] = Counter()

    def walk(node: Any, depth: int) -> None:
        if depth > max_depth:
            return
        if isinstance(node, dict):
            for key, value in node.items():
                if key in REPEATED_KEYS:
                    counts[key] += 1
                walk(value, depth + 1)
        elif isinstance(node, list):
            for item in node[:100]:
                walk(item, depth + 1)

    walk(data, 0)
    return counts


def build_report() -> dict[str, Any]:
    packets: list[dict[str, Any]] = []
    aggregate: Counter[str] = Counter()
    family_counts: dict[str, int] = defaultdict(int)
    for path in packet_paths():
        data = safe_json(path)
        if not isinstance(data, dict):
            continue
        counts = count_keys(data)
        aggregate.update(counts)
        family = path.stem
        for suffix in (".production-bench", ".next-batch", ".next-batch-2", ".next-batch-3"):
            family = family.replace(suffix, "")
        family_counts[family] += 1
        packets.append(
            {
                "path": relpath(path),
                "family": family,
                "bytes": path.stat().st_size,
                "top_level_keys": sorted(data.keys()),
                "repeated_key_counts": dict(sorted(counts.items())),
                "status": data.get("status"),
                "authority_present": "authority" in data or "authority_boundary" in data,
                "validation_present": "validation" in data,
                "summary_present": "summary" in data,
            }
        )
    shared_candidates = [
        {
            "key": key,
            "occurrences": count,
            "recommended_consolidation": "shared_packet_header_ref" if key in {"authority", "authority_boundary", "generated_at_utc", "source_artifacts", "proof_artifacts"} else "shared_summary_or_validation_ref",
        }
        for key, count in sorted(aggregate.items(), key=lambda row: (-row[1], row[0]))
        if count >= 3
    ]
    return {
        "schema_version": "wf78_packet_summary_consolidation.v1",
        "generated_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "status": "preview_ready",
        "authority": {
            "review_only": True,
            "wf78_routing_changed": False,
            "tier_label_changed": False,
            "capital_deployment_allowed": False,
            "trade_or_execution_allowed": False,
            "proof_deletion_allowed": False,
            "archive_or_cleanup_allowed": False,
            "canonical_mutation_allowed": False,
            "portfolio_mutation_allowed": False,
            "sql_canon_promotion_allowed": False,
            "customer_or_public_output_allowed": False,
            "paper_or_live_execution_allowed": False,
            "brokerage_or_account_action_allowed": False,
            "owner_approval_inferred": False,
        },
        "summary": {
            "packet_count": len(packets),
            "family_counts": dict(sorted(family_counts.items())),
            "shared_candidate_count": len(shared_candidates),
            "removal_ready": False,
            "next_safe_action": "Introduce shared header/summary refs as additive compatibility fields; keep existing embedded blocks until WF78 all-safe and consumer proof pass.",
        },
        "shared_block_candidates": shared_candidates,
        "packets": packets,
    }


def build_shared_header(report: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": "wf78_packet_shared_header.v1",
        "generated_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "status": "additive_reference_ready",
        "authority": report["authority"],
        "source_consolidation_report": relpath(OUT),
        "shared_header_fields": [
            "generated_at_utc",
            "status",
            "authority",
            "source_artifacts",
            "proof_artifacts",
            "validation",
            "summary",
        ],
        "consumer_policy": {
            "existing_embedded_fields_preserved": True,
            "field_removal_ready": False,
            "wf78_routing_changed": False,
            "capital_or_trade_authority_changed": False,
        },
        "recommended_next_step": "Future WF78 packets may add a shared_header_ref to this artifact while preserving existing embedded compatibility fields.",
    }


def validate(report: dict[str, Any]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    authority = as_dict(report.get("authority"))
    if authority.get("review_only") is not True:
        findings.append({"severity": "critical", "issue": "review_only_not_true"})
    for key, value in authority.items():
        if key.endswith("_allowed") or key.endswith("_changed") or key.endswith("_inferred"):
            if value is not False:
                findings.append({"severity": "critical", "issue": "authority_flag_not_false", "flag": key, "value": value})
    if report.get("summary", {}).get("packet_count", 0) < 3:
        findings.append({"severity": "critical", "issue": "packet_count_low", "count": report.get("summary", {}).get("packet_count")})
    if report.get("summary", {}).get("removal_ready") is not False:
        findings.append({"severity": "critical", "issue": "removal_ready_claimed"})
    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description="Build WF78 packet summary consolidation preview.")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    args = parser.parse_args()
    report = build_report()
    findings = validate(report)
    report["validation"] = {
        "status": "ok" if not any(f.get("severity") == "critical" for f in findings) else "blocked",
        "critical": sum(1 for f in findings if f.get("severity") == "critical"),
        "warning": sum(1 for f in findings if f.get("severity") == "warning"),
        "findings": findings,
    }
    if args.write:
        OUT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        SHARED_HEADER_OUT.write_text(json.dumps(build_shared_header(report), indent=2) + "\n", encoding="utf-8")
        print(f"wrote {relpath(OUT)}")
        print(f"wrote {relpath(SHARED_HEADER_OUT)}")
    print(f"wf78_packet_summary_consolidation: {report['validation']['status']} ({report['validation']['critical']} critical)")
    return 1 if args.validate and report["validation"]["critical"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
