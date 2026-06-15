"""Inventory presentation artifact families for flattening/retrieval work.

Phase 0 for Presentation Artifact Flattening and Retrieval Routing. The script
is read-only over existing artifacts and writes a proof inventory that maps
presentation families, owners, consumers, sizes, sidecars, repeated-block
signals, and first dashboard DTO candidates.

Authority: review/proof only. No cleanup, archive, canon/portfolio mutation,
SQL-canon promotion, customer/public output, paper/live/account action, or
owner-approval inference.
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
SCRIPTS = ROOT / "scripts"
APPS = ROOT / "apps"
OUT = TMP / "presentation-artifact-flattening-inventory.json"

WATCH_FAMILIES = {
    "dashboard-data": {
        "owner_workflow": "WF79 Command Center V2",
        "primary_owner_script": "scripts/dashboard_payload.py",
        "class": "presentation_dto",
    },
    "dashboard-last": {
        "owner_workflow": "WF79 Command Center V2",
        "primary_owner_script": "scripts/dashboard_payload.py",
        "class": "presentation_dto",
    },
    "dashboard-presentation-adapter": {
        "owner_workflow": "WF79 Command Center V2",
        "primary_owner_script": "scripts/dashboard_presentation_adapter.py",
        "class": "presentation_adapter",
    },
    "dashboard-presentation-view-model": {
        "owner_workflow": "WF79 Command Center V2",
        "primary_owner_script": "scripts/dashboard_presentation_view_model.py",
        "class": "presentation_view_model",
    },
    "dashboard-presentation-acceptance": {
        "owner_workflow": "WF79 Command Center V2",
        "primary_owner_script": "scripts/dashboard_presentation_acceptance.py",
        "class": "validation_proof",
    },
    "dashboard-data-thin-preview": {
        "owner_workflow": "WF79 Command Center V2",
        "primary_owner_script": "scripts/dashboard_thin_payload_preview.py",
        "class": "thin_payload_preview",
    },
    "dashboard-data-thin-preview-validation": {
        "owner_workflow": "WF79 Command Center V2",
        "primary_owner_script": "scripts/dashboard_thin_payload_preview.py",
        "class": "validation_proof",
    },
    "dashboard-v2-reader-migration": {
        "owner_workflow": "WF79 Command Center V2",
        "primary_owner_script": "scripts/dashboard_v2_reader_migration.py",
        "class": "reader_migration_proof",
    },
    "dashboard-compact-shell-validation": {
        "owner_workflow": "WF79 Command Center V2",
        "primary_owner_script": "scripts/dashboard_compact_shell.py",
        "class": "validation_proof",
    },
    "dashboard-compact-shell-acceptance": {
        "owner_workflow": "WF79 Command Center V2",
        "primary_owner_script": "scripts/dashboard_compact_shell_acceptance.py",
        "class": "acceptance_proof",
    },
    "dashboard-shrink-readiness-score": {
        "owner_workflow": "WF79 Command Center V2",
        "primary_owner_script": "scripts/dashboard_shrink_readiness_score.py",
        "class": "replacement_readiness_score",
    },
    "dashboard-compatibility-payload": {
        "owner_workflow": "WF79 Command Center V2",
        "primary_owner_script": "scripts/dashboard_compatibility_payload.py",
        "class": "compatibility_payload_proof",
    },
    "dashboard-compatibility-payload-validation": {
        "owner_workflow": "WF79 Command Center V2",
        "primary_owner_script": "scripts/dashboard_compatibility_payload.py",
        "class": "validation_proof",
    },
    "dashboard-presentation-renderer-validation": {
        "owner_workflow": "WF79 Command Center V2",
        "primary_owner_script": "scripts/dashboard_presentation_renderer.py",
        "class": "validation_proof",
    },
    "presentation-render-default-compatibility": {
        "owner_workflow": "Presentation Artifact Flattening",
        "primary_owner_script": "scripts/presentation_render_default_compatibility.py",
        "class": "compatibility_proof",
    },
    "presentation-retrieval-route-map": {
        "owner_workflow": "Presentation Artifact Flattening",
        "primary_owner_script": "scripts/presentation_retrieval_route_map.py",
        "class": "retrieval_route_map",
    },
    "presentation-retrieval-enforcement": {
        "owner_workflow": "Presentation Artifact Flattening",
        "primary_owner_script": "scripts/presentation_retrieval_enforcement.py",
        "class": "retrieval_route_validation",
    },
    "full-portfolio-view": {
        "owner_workflow": "WF58/WF64/WF56 portfolio communication",
        "primary_owner_script": "scripts/full_portfolio_view.py",
        "class": "presentation_dto",
    },
    "wf75-operator-console": {
        "owner_workflow": "WF75 Retail/service-led readiness",
        "primary_owner_script": "scripts/wf75_operator_console.py",
        "class": "presentation_dto",
    },
    "retail-saas-fixture-demo": {
        "owner_workflow": "WF75 Retail/service fixture",
        "primary_owner_script": "scripts/retail_saas_fixture_demo.py",
        "class": "fixture_and_render_family",
    },
    "wf78-tier-b-final-promotion-packet": {
        "owner_workflow": "WF78 tier/routing spine",
        "primary_owner_script": "scripts/wf78_tier_b_final_promotion_packet.py",
        "class": "source_proof_packet",
    },
    "wf78-tier-a-final-promotion-packet": {
        "owner_workflow": "WF78 tier/routing spine",
        "primary_owner_script": "scripts/wf78_tier_a_final_promotion_packet.py",
        "class": "source_proof_packet",
    },
    "wf78-auto-tier-routing": {
        "owner_workflow": "WF78 tier/routing spine",
        "primary_owner_script": "scripts/wf78_auto_tier_router.py",
        "class": "source_proof_packet",
    },
    "wf78-packet-summary-consolidation": {
        "owner_workflow": "WF78 tier/routing spine",
        "primary_owner_script": "scripts/wf78_packet_summary_consolidation.py",
        "class": "consolidation_preview",
    },
    "wf78-packet-shared-header": {
        "owner_workflow": "WF78 tier/routing spine",
        "primary_owner_script": "scripts/wf78_packet_summary_consolidation.py",
        "class": "shared_header_reference",
    },
}

REPEATED_KEYS = {
    "authority",
    "authority_boundary",
    "boundary",
    "source",
    "sources",
    "status",
    "state",
    "stop_lines",
    "stoplines",
    "summary",
    "validation",
    "warnings",
    "proof",
    "proofs",
    "metadata",
}


def relpath(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        return str(path)


def family_name(path: Path) -> str:
    name = path.name
    stem = path.stem
    # Collapse validation/render variants under the same logical family.
    stem = re.sub(r"\.customer-export$", "", stem)
    stem = re.sub(r"\.html-validation$", "", stem)
    stem = re.sub(r"\.validation$", "", stem)
    stem = re.sub(r"\.rerun$", "", stem)
    stem = re.sub(r"\.seeded-bad.*$", "", stem)
    # Keep WF78 final-promotion packet variants together.
    stem = re.sub(r"\.(production-bench|next-batch|next-batch-\d+)$", "", stem)
    return stem


def safe_json(path: Path) -> Any | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def collect_keys(data: Any, max_depth: int = 5) -> Counter[str]:
    counts: Counter[str] = Counter()

    def walk(node: Any, depth: int) -> None:
        if depth > max_depth:
            return
        if isinstance(node, dict):
            counts.update(str(key) for key in node.keys())
            for value in node.values():
                walk(value, depth + 1)
        elif isinstance(node, list):
            for value in node[:100]:
                walk(value, depth + 1)

    walk(data, 0)
    return counts


def top_level_shape(data: Any) -> dict[str, Any]:
    if not isinstance(data, dict):
        return {"type": type(data).__name__, "top_level_keys": []}
    return {
        "type": "dict",
        "top_level_keys": sorted(data.keys()),
        "top_level_key_count": len(data),
    }


def find_consumers(paths: list[Path]) -> list[dict[str, Any]]:
    needles = {path.name for path in paths}
    needles.update(relpath(path) for path in paths)
    consumers: dict[str, set[str]] = defaultdict(set)
    for root in (SCRIPTS, APPS):
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if path.suffix.lower() not in {".py", ".js", ".ts", ".tsx"}:
                continue
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue
            for needle in needles:
                if needle and needle in text:
                    consumers[relpath(path)].add(needle)
    return [
        {"path": path, "matched": sorted(matches)}
        for path, matches in sorted(consumers.items())
    ]


def dashboard_dto_candidates(data: Any) -> list[dict[str, Any]]:
    if not isinstance(data, dict):
        return []
    candidates: list[dict[str, Any]] = []
    for key, value in data.items():
        if isinstance(value, (dict, list)):
            shape = top_level_shape(value)
            key_counts = collect_keys(value, max_depth=3)
            repeated = {k: key_counts[k] for k in sorted(REPEATED_KEYS & set(key_counts))}
            candidates.append(
                {
                    "section": key,
                    "node_type": type(value).__name__,
                    "top_level_key_count": shape.get("top_level_key_count"),
                    "top_level_keys_sample": (shape.get("top_level_keys") or [])[:30],
                    "repeated_signal_keys": repeated,
                    "recommended_dto_fields": [
                        "headline",
                        "state",
                        "freshness",
                        "severity",
                        "primary_reason",
                        "owner_action_required",
                        "source_ref",
                        "proof_ref",
                        "authority_summary",
                    ],
                }
            )
    return sorted(candidates, key=lambda row: (-len(row["repeated_signal_keys"]), row["section"]))


def build_inventory() -> dict[str, Any]:
    families: dict[str, dict[str, Any]] = {}
    for path in sorted(TMP.glob("*")):
        if not path.is_file() or path.suffix.lower() not in {".json", ".md", ".html", ".csv"}:
            continue
        fam = family_name(path)
        if fam not in WATCH_FAMILIES:
            continue
        entry = families.setdefault(
            fam,
            {
                "family": fam,
                **WATCH_FAMILIES[fam],
                "files": [],
                "total_size_kb": 0.0,
                "sidecar_count": 0,
                "json_count": 0,
                "human_render_count": 0,
                "validation_render_count": 0,
                "consumers": [],
                "repeated_key_counts": {},
                "top_level_shape": {},
            },
        )
        size_kb = round(path.stat().st_size / 1024, 1)
        entry["total_size_kb"] = round(entry["total_size_kb"] + size_kb, 1)
        entry["files"].append({"path": relpath(path), "suffix": path.suffix.lower(), "size_kb": size_kb})
        if path.suffix.lower() == ".json":
            entry["json_count"] += 1
            data = safe_json(path)
            if data is not None:
                counts = collect_keys(data)
                repeated = {key: counts[key] for key in sorted(REPEATED_KEYS & set(counts))}
                entry["repeated_key_counts"][relpath(path)] = repeated
                entry["top_level_shape"][relpath(path)] = top_level_shape(data)
                if fam == "dashboard-data":
                    entry["dashboard_dto_candidates"] = dashboard_dto_candidates(data)
        elif path.suffix.lower() in {".md", ".html"}:
            entry["human_render_count"] += 1
            entry["sidecar_count"] += 1
        else:
            entry["sidecar_count"] += 1
        if any(token in path.name for token in ("validation", "seeded-bad")):
            entry["validation_render_count"] += 1

    for entry in families.values():
        paths = [TMP / item["path"].split("/", 1)[1] for item in entry["files"] if item["path"].startswith("tmp/")]
        entry["consumers"] = find_consumers(paths)
        entry["files"] = sorted(entry["files"], key=lambda item: item["path"])
        entry["retrieval_flattening_priority"] = priority_for(entry)

    ordered = sorted(families.values(), key=lambda item: (item["retrieval_flattening_priority"], -item["total_size_kb"]))
    return {
        "schema_version": "presentation_artifact_flattening_inventory.v1",
        "generated_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "status": "ok",
        "authority": {
            "review_only": True,
            "cleanup_or_delete_allowed": False,
            "archive_allowed": False,
            "canonical_mutation_allowed": False,
            "portfolio_mutation_allowed": False,
            "sql_canon_promotion_allowed": False,
            "customer_or_public_output_allowed": False,
            "paper_or_live_execution_allowed": False,
            "brokerage_or_account_action_allowed": False,
            "owner_approval_inferred": False,
        },
        "summary": {
            "families": len(ordered),
            "total_size_kb": round(sum(item["total_size_kb"] for item in ordered), 1),
            "highest_priority": [item["family"] for item in ordered[:4]],
        },
        "phase0_acceptance": {
            "owner_script_identified": all(bool(item.get("primary_owner_script")) for item in ordered),
            "consumer_inventory_present": all("consumers" in item for item in ordered),
            "size_recorded": all(item.get("total_size_kb", 0) >= 0 for item in ordered),
            "authority_boundary_present": True,
            "no_schema_changes": True,
            "no_deletes_moves_or_archives": True,
        },
        "families": ordered,
        "recommended_next_slice": {
            "phase": "Phase 1 dashboard DTO design",
            "target_family": "dashboard-data",
            "owner": "WF79 Command Center V2",
            "action": "Design compact dashboard panel DTOs from the inventory; do not rewrite payload until consumer acceptance is explicit.",
        },
    }


def priority_for(entry: dict[str, Any]) -> int:
    family = entry["family"]
    if family == "dashboard-data":
        return 1
    if family == "dashboard-last":
        return 2
    if family == "dashboard-presentation-adapter":
        return 2
    if family in {"dashboard-presentation-view-model", "dashboard-presentation-acceptance", "dashboard-presentation-renderer-validation"}:
        return 2
    if family == "full-portfolio-view":
        return 3
    if family == "wf75-operator-console":
        return 4
    if family.startswith("wf78"):
        return 5
    return 6


def main() -> int:
    parser = argparse.ArgumentParser(description="Inventory presentation artifacts for flattening/retrieval work.")
    parser.add_argument("--write", action="store_true", help="Write tmp/presentation-artifact-flattening-inventory.json.")
    args = parser.parse_args()
    report = build_inventory()
    if args.write:
        OUT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(f"wrote {relpath(OUT)}")
    summary = report["summary"]
    print(
        "presentation_artifact_inventory: "
        f"{report['status']} ({summary['families']} families, {summary['total_size_kb']} KB)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
