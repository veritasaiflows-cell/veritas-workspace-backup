#!/usr/bin/env python3
"""Build the thin truth-surface inventory and route efficiency scorecard.

This is a WF73 control-plane proof artifact. It classifies major workspace
surfaces as authority, router, proof, dashboard, legacy, or archive-candidate,
then times the intended fast-path reads. It never moves, deletes, archives,
promotes SQL/canon, mutates portfolio state, touches runtime config, or grants
approval/execution authority.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import URLError
from urllib.request import urlopen

from market_data_utils import atomic_write_json, load_json_artifact

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
INVENTORY_OUT = TMP / "truth-surface-inventory.json"
EFFICIENCY_OUT = TMP / "route-efficiency-scorecard.json"

SCHEMA = "veritas.truth_surface_inventory.v1"
EFFICIENCY_SCHEMA = "veritas.route_efficiency_scorecard.v1"

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "classification_only": True,
    "latency_probe_only": True,
    "file_mutation_allowed": False,
    "archive_or_delete_allowed": False,
    "canon_or_portfolio_mutation_allowed": False,
    "sql_canon_promotion_allowed": False,
    "customer_or_external_delivery_allowed": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "config_auth_runtime_mutation_allowed": False,
    "owner_approval_inferred": False,
}

SURFACES = [
    {
        "path": "06. Playbooks/Active Workflows.md",
        "class": "authority",
        "owner": "WF73 / main-session live queue",
        "open_first_rank": 1,
        "reason": "Live queue state, current lane, blockers, and stop lines.",
    },
    {
        "path": "06. Playbooks/Startup Truth Index.md",
        "class": "router",
        "owner": "startup route map",
        "open_first_rank": 2,
        "reason": "Boot and post-compaction route map.",
    },
    {
        "path": "tmp/workflow-routing-index.json",
        "class": "router",
        "owner": "WF73 workflow routing index",
        "open_first_rank": 3,
        "reason": "Derived route proof; JSON owner for route SQLite.",
    },
    {
        "path": "tmp/workflow-routing-index.sqlite",
        "class": "router",
        "owner": "WF73 workflow routing index",
        "open_first_rank": 4,
        "reason": "Fast derived route lookup; never canon or approval.",
    },
    {
        "path": "tmp/workflow-routing-index-validation.json",
        "class": "proof",
        "owner": "WF73 workflow routing index",
        "open_first_rank": 5,
        "reason": "Route/parity/authority validation proof.",
    },
    {
        "path": "tmp/veritas-artifact-index.sqlite",
        "class": "router",
        "owner": "artifact cockpit / proof lookup",
        "open_first_rank": 6,
        "reason": "Derived proof lookup for artifacts and freshness.",
    },
    {
        "path": "tmp/pm-control-packet.json",
        "class": "dashboard",
        "owner": "PM program state",
        "open_first_rank": 7,
        "reason": "Readiness, blockers, lane state, and next actions.",
    },
    {
        "path": "tmp/pm-program-state.sqlite",
        "class": "dashboard",
        "owner": "PM program state",
        "open_first_rank": 8,
        "reason": "Derived PM lookup only.",
    },
    {
        "path": "tmp/cron-freshness-spine.json",
        "class": "proof",
        "owner": "WF76 cron/control freshness",
        "open_first_rank": 9,
        "reason": "Single cron freshness proof surface.",
    },
    {
        "path": "tmp/artifact-intelligence-action-scorer.json",
        "class": "router",
        "owner": "artifact intelligence action scorer",
        "open_first_rank": 10,
        "reason": "Cross-artifact materiality and next-work routing.",
    },
    {
        "path": "tmp/finance-decision-sync-spine.json",
        "class": "router",
        "owner": "finance decision sync spine",
        "open_first_rank": 10,
        "reason": "Single derived ticker decision-state spine for WF78/WF68/WF67/band/repair/paper-position synchronization.",
    },
    {
        "path": "tmp/canonical-finance-data-plane-contract.json",
        "class": "router",
        "owner": "WF84 canonical finance data-plane",
        "open_first_rank": 10,
        "reason": "Internal trade-grade personal finance OS schema/feeder/validator contract; review-only and not customer/account/capital/execution authority.",
    },
    {
        "path": "tmp/canonical-finance-data-plane.json",
        "class": "router",
        "owner": "WF84 canonical finance data-plane",
        "open_first_rank": 10,
        "reason": "Read-only canonical finance data-plane packet built from validated WF78 and finance-state feeders; internal interface only, not owner truth or approval authority.",
    },
    {
        "path": "tmp/canonical-finance-data-plane-validation.json",
        "class": "validator",
        "owner": "WF84 canonical finance data-plane",
        "open_first_rank": 10,
        "reason": "Validation proof for the WF84 canonical packet, including row parity, tier caps, source scope, and authority-boundary checks.",
    },
    {
        "path": "tmp/canonical-finance-data-plane.sqlite",
        "class": "index",
        "owner": "WF84 canonical finance data-plane",
        "open_first_rank": 11,
        "reason": "Derived SQLite lookup companion loaded only from the validated WF84 JSON packet; rebuildable and not canon, approval, portfolio, or execution authority.",
    },
    {
        "path": "tmp/canonical-finance-data-plane-retirement-readiness.json",
        "class": "validator",
        "owner": "WF84 canonical finance data-plane",
        "open_first_rank": 11,
        "reason": "Preview-only duplicate-surface retirement readiness proof; no archive/delete/apply authority.",
    },
    {
        "path": "tmp/trade-grade-decision-os-contract.json",
        "class": "router",
        "owner": "WF85 trade-grade decision and approval-card OS",
        "open_first_rank": 10,
        "reason": "Contract-first decision/approval-card layer above WF84; review-only and not capital/execution/customer/canon authority.",
    },
    {
        "path": "tmp/trade-grade-source-freshness-gate.json",
        "class": "validator",
        "owner": "WF85 trade-grade decision and approval-card OS",
        "open_first_rank": 10,
        "reason": "Source-open, freshness, WF84 JSON/SQLite parity, and material-claim guard proof before decision-card readiness.",
    },
    {
        "path": "tmp/trade-grade-decision-cards.json",
        "class": "router",
        "owner": "WF85 trade-grade decision and approval-card OS",
        "open_first_rank": 10,
        "reason": "Fail-closed review-only decision-card queue above WF84; not approval, execution, canon, portfolio, cash, or customer authority.",
    },
    {
        "path": "tmp/trade-grade-decision-card-authority-validation.json",
        "class": "validator",
        "owner": "WF85 trade-grade decision and approval-card OS",
        "open_first_rank": 10,
        "reason": "Generated-card authority and forbidden-action vocabulary scan; required before approval-card draft gates.",
    },
    {
        "path": "tmp/trade-grade-approval-card-gate.json",
        "class": "validator",
        "owner": "WF85 trade-grade decision and approval-card OS",
        "open_first_rank": 10,
        "reason": "Approval-card draft eligibility separator; drafts are NOT approval and remain owner/WF67 gated.",
    },
    {
        "path": "tmp/trade-grade-risk-sizing-overlay.json",
        "class": "proof",
        "owner": "WF85 trade-grade decision and approval-card OS",
        "open_first_rank": 10,
        "reason": "Recommendation-only risk/sizing/staggering posture over decision cards; no portfolio/cash/risk-rule mutation.",
    },
    {
        "path": "tmp/trade-grade-repair-conveyor.json",
        "class": "router",
        "owner": "WF85 trade-grade decision and approval-card OS",
        "open_first_rank": 10,
        "reason": "Review-only conveyor from fail-closed WF85 cards to WF78/WF84 source, freshness, and band/stop repair lanes before review-ready pilots.",
    },
    {
        "path": "tmp/band-hygiene-freshness-controller.json",
        "class": "proof",
        "owner": "finance band hygiene and freshness controller",
        "open_first_rank": 10,
        "reason": "Quote freshness plus bounded entry-band hygiene/apply proof feeding the finance decision sync spine.",
    },
    {
        "path": "tmp/wf78-event-triggered-rerouting.json",
        "class": "router",
        "owner": "WF78 evidence/routing repair",
        "open_first_rank": 11,
        "reason": "WF78 repair, reroute, and owner-card-prep queue.",
    },
    {
        "path": "tmp/wf78-legacy-42-tier-migration-planner.json",
        "class": "router",
        "owner": "WF78 legacy 42 to Tier A/B migration",
        "open_first_rank": 11,
        "reason": "Shadow migration and dependency gate for folding legacy production-current-42 tickers into the 25/50 Tier A/B operating model.",
    },
    {
        "path": "tmp/wf78-capital-review-queue.json",
        "class": "proof",
        "owner": "WF78 capital-review prep",
        "open_first_rank": 12,
        "reason": "Non-executing capital-review candidate state.",
    },
    {
        "path": "tmp/parallel-repeatable-work-orchestration.json",
        "class": "router",
        "owner": "WF78 repeatable orchestration",
        "open_first_rank": 13,
        "reason": "Current repeatable evidence/card/macro orchestration proof.",
    },
    {
        "path": "tmp/macro-event-guard-loop.json",
        "class": "proof",
        "owner": "WF78/macro event guard",
        "open_first_rank": 14,
        "reason": "Review-only macro guard refresh for ticker routing context.",
    },
    {
        "path": "tmp/wf78-owner-card-prep-loop.json",
        "class": "proof",
        "owner": "WF78/WF67 owner-card prep",
        "open_first_rank": 15,
        "reason": "Non-executing owner-card and WF67 request prep proof.",
    },
    {
        "path": "tmp/wf78-tier-a-evidence-repair-batch.json",
        "class": "proof",
        "owner": "WF78 Tier A repair",
        "open_first_rank": 16,
        "reason": "Tier A challenged evidence repair tracking proof.",
    },
    {
        "path": "tmp/repeatable-work-closeout.json",
        "class": "proof",
        "owner": "repeatable closeout chain",
        "open_first_rank": 17,
        "reason": "Standard closeout validation proof for repeatable work.",
    },
    {
        "path": "tmp/dashboard-data.json",
        "class": "dashboard",
        "owner": "WF79 command center",
        "open_first_rank": 30,
        "reason": "Legacy-heavy UI payload; not source truth.",
    },
    {
        "path": "tmp/veritas-command-center-compact.html",
        "class": "dashboard",
        "owner": "WF79 command center",
        "open_first_rank": 31,
        "reason": "Compact UI shell proof, local review only.",
    },
    {
        "path": "tmp/workflow-alias-index.json",
        "class": "legacy",
        "owner": "legacy route alias index",
        "open_first_rank": 90,
        "reason": "Superseded by workflow routing index; no cleanup authority.",
    },
]

COMMAND_PROBES = [
    {
        "name": "workflow_sql_route_wf78",
        "command": ["python", "scripts\\workflow_routing_index.py", "--sql-route", "WF78"],
        "target_seconds": 2.0,
    },
    {
        "name": "workflow_sql_next_actions",
        "command": ["python", "scripts\\workflow_routing_index.py", "--sql-next-actions"],
        "target_seconds": 5.0,
    },
    {
        "name": "workflow_sql_freshness",
        "command": ["python", "scripts\\workflow_routing_index.py", "--sql-freshness"],
        "target_seconds": 5.0,
    },
]

HTTP_PROBES = [
    {
        "name": "pm_cockpit_health",
        "url": "http://127.0.0.1:8765/health",
        "target_seconds": 2.0,
        "timeout_seconds": 8,
        "optional_when_local_service_offline": True,
    },
    {
        "name": "pm_cockpit_workflow_routes",
        "url": "http://127.0.0.1:8765/api/workflows/routes",
        "target_seconds": 5.0,
        "timeout_seconds": 12,
        "optional_when_local_service_offline": True,
    },
]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def parse_utc(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def age_hours(value: Any, now: datetime) -> float | None:
    parsed = parse_utc(value)
    if parsed is None:
        return None
    return round(max(0.0, (now - parsed).total_seconds() / 3600), 2)


def surface_row(spec: dict[str, Any], now: datetime) -> dict[str, Any]:
    path = ROOT / spec["path"]
    payload = load_json_artifact(path) if path.suffix.lower() == ".json" else None
    row = {
        **spec,
        "exists": path.exists(),
        "size_bytes": path.stat().st_size if path.exists() else 0,
        "mtime_utc": datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z") if path.exists() else None,
        "generated_at_utc": payload.get("generated_at_utc") if isinstance(payload, dict) else None,
        "status": payload.get("status") if isinstance(payload, dict) else None,
        "age_hours": age_hours(payload.get("generated_at_utc"), now) if isinstance(payload, dict) else None,
        "first_open": spec["class"] in {"authority", "router"} and spec["open_first_rank"] <= 10,
        "archive_candidate_only_after_approval": spec["class"] in {"legacy", "archive-candidate"},
        "authority_note": "classification only; no move/delete/archive authority",
    }
    if path.suffix.lower() == ".sqlite" and path.exists():
        try:
            with sqlite3.connect(path) as con:
                row["sqlite_integrity_check"] = con.execute("PRAGMA integrity_check").fetchone()[0]
        except sqlite3.Error as exc:
            row["sqlite_integrity_check"] = f"error: {exc}"
    return row


def run_command_probe(probe: dict[str, Any]) -> dict[str, Any]:
    start = time.perf_counter()
    try:
        completed = subprocess.run(
            probe["command"],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=30,
            check=False,
        )
        elapsed = round(time.perf_counter() - start, 3)
        rc = completed.returncode
        stderr = completed.stderr.strip()[:500]
    except subprocess.TimeoutExpired:
        elapsed = round(time.perf_counter() - start, 3)
        rc = 124
        stderr = "timeout"
    ok = rc == 0
    return {
        "name": probe["name"],
        "kind": "command",
        "command": " ".join(probe["command"]),
        "returncode": rc,
        "elapsed_seconds": elapsed,
        "target_seconds": probe["target_seconds"],
        "status": "ok" if ok and elapsed <= probe["target_seconds"] else "slow" if ok else "failed",
        "stderr_preview": stderr,
    }


def run_http_probe(probe: dict[str, Any]) -> dict[str, Any]:
    start = time.perf_counter()
    status_code: int | None = None
    error: str | None = None
    bytes_read = 0
    try:
        with urlopen(probe["url"], timeout=probe["timeout_seconds"]) as resp:
            body = resp.read()
            status_code = getattr(resp, "status", None)
            bytes_read = len(body)
    except URLError as exc:
        error = str(exc)[:500]
    except TimeoutError:
        error = "timeout"
    elapsed = round(time.perf_counter() - start, 3)
    ok = status_code is not None and 200 <= int(status_code) < 300
    status = "ok" if ok and elapsed <= probe["target_seconds"] else "slow" if ok else "unavailable"
    expected_offline = status == "unavailable" and probe.get("optional_when_local_service_offline") is True
    return {
        "name": probe["name"],
        "kind": "http",
        "url": probe["url"],
        "status_code": status_code,
        "elapsed_seconds": elapsed,
        "target_seconds": probe["target_seconds"],
        "status": "expected_offline" if expected_offline else status,
        "optional_when_local_service_offline": bool(probe.get("optional_when_local_service_offline")),
        "bytes_read": bytes_read,
        "error": error,
    }


def build_reports(run_probes: bool = True) -> tuple[dict[str, Any], dict[str, Any]]:
    now_dt = datetime.now(timezone.utc)
    now = now_dt.replace(microsecond=0).isoformat().replace("+00:00", "Z")
    rows = [surface_row(spec, now_dt) for spec in SURFACES]
    class_counts: dict[str, int] = {}
    for row in rows:
        class_counts[row["class"]] = class_counts.get(row["class"], 0) + 1
    missing = [row["path"] for row in rows if not row["exists"] and row["class"] != "legacy"]
    first_open = sorted(
        [
            {
                "rank": row["open_first_rank"],
                "path": row["path"],
                "class": row["class"],
                "owner": row["owner"],
                "reason": row["reason"],
            }
            for row in rows
            if row["first_open"]
        ],
        key=lambda row: row["rank"],
    )
    inventory = {
        "schema": SCHEMA,
        "generated_at_utc": now,
        "status": "ok" if not missing else "warning",
        "purpose": "Classify major truth/routing/proof/dashboard surfaces and define the fast open-first route.",
        "authority_boundary": AUTHORITY_BOUNDARY,
        "summary": {
            "surface_count": len(rows),
            "class_counts": class_counts,
            "missing_non_legacy_count": len(missing),
            "archive_candidate_count": sum(1 for row in rows if row["archive_candidate_only_after_approval"]),
            "first_open_count": len(first_open),
            "next_safe_action": "Use first_open_order before broad scans; no archive/delete without explicit approval and reference checks.",
        },
        "first_open_order": first_open,
        "surfaces": sorted(rows, key=lambda row: (row["open_first_rank"], row["path"])),
        "validation": {
            "status": "ok" if not missing else "warning",
            "errors": [],
            "warnings": [f"missing non-legacy surface: {path}" for path in missing],
        },
        "stop_lines": [
            "Inventory is classification/proof only; no file move, delete, archive, canon/portfolio mutation, SQL promotion, customer output, config/runtime mutation, paper/live/account action, or owner approval inference.",
        ],
    }

    probe_results = []
    if run_probes:
        probe_results.extend(run_command_probe(probe) for probe in COMMAND_PROBES)
        probe_results.extend(run_http_probe(probe) for probe in HTTP_PROBES)
    slow = [row for row in probe_results if row["status"] == "slow"]
    failed = [row for row in probe_results if row["status"] in {"failed", "unavailable"}]
    expected_offline = [row for row in probe_results if row["status"] == "expected_offline"]
    efficiency = {
        "schema": EFFICIENCY_SCHEMA,
        "generated_at_utc": now,
        "status": "ok" if not slow and not failed else "warning",
        "purpose": "Measure fast-path route/control lookup latency and identify cockpit/API bottlenecks.",
        "authority_boundary": AUTHORITY_BOUNDARY,
        "targets": {
            "health_status_seconds": 2.0,
            "workflow_route_seconds": 5.0,
            "heavy_proof_drilldown_seconds": 8.0,
        },
        "summary": {
            "probe_count": len(probe_results),
            "slow_count": len(slow),
            "failed_or_unavailable_count": len(failed),
            "expected_offline_count": len(expected_offline),
            "next_safe_action": "Optimize failed/slow command routes first; start the local PM cockpit only when UI/API probe proof is specifically needed.",
        },
        "probes": probe_results,
        "validation": {
            "status": "ok" if not failed else "warning",
            "errors": [],
            "warnings": [
                *[f"slow probe: {row['name']} {row['elapsed_seconds']}s > {row['target_seconds']}s" for row in slow],
                *[f"failed/unavailable probe: {row['name']} status={row['status']}" for row in failed],
                *[f"expected offline optional probe: {row['name']}" for row in expected_offline],
            ],
        },
        "stop_lines": inventory["stop_lines"],
    }
    return inventory, efficiency


def main() -> int:
    parser = argparse.ArgumentParser(description="Build truth-surface inventory and route efficiency scorecard.")
    parser.add_argument("--write", action="store_true", help="Write JSON proof artifacts.")
    parser.add_argument("--validate", action="store_true", help="Return non-zero on validation errors.")
    parser.add_argument("--no-probes", action="store_true", help="Skip latency probes.")
    args = parser.parse_args()

    inventory, efficiency = build_reports(run_probes=not args.no_probes)
    if args.write:
        atomic_write_json(INVENTORY_OUT, inventory)
        atomic_write_json(EFFICIENCY_OUT, efficiency)
        print(f"wrote {rel(INVENTORY_OUT)} status={inventory['status']}")
        print(f"wrote {rel(EFFICIENCY_OUT)} status={efficiency['status']}")
    else:
        print(json.dumps({"inventory": inventory["summary"], "efficiency": efficiency["summary"]}, indent=2))

    errors = inventory["validation"]["errors"] + efficiency["validation"]["errors"]
    if args.validate and errors:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
