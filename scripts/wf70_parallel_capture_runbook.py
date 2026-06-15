"""WF70 Phase 6 — Parallel capture runbook generator.

Produces a review-only runbook artifact describing how the 31-ticker official
IR capture universe can be run as parallel disjoint-ticker workers without
artifact collision, then merged by the validator.

Workers are naturally disjoint because each capture script writes to separate
per-ticker files under tmp/official-ir-captures/. No shared-state writes occur
during the capture phase. The registry/validator step runs after all workers
complete to prove authority-clean coverage.

Authority: review-only. Does not fetch sources, mutate captures, or widen any
canon/portfolio/trade/account/order/sizing/sleeve/cash/risk-rule authority.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
OUT_JSON = ROOT / "tmp" / "wf70-phase6-parallel-capture-runbook.json"
OUT_MD = ROOT / "tmp" / "wf70-phase6-parallel-capture-runbook.md"

AUTHORITY = {
    "review_only": True,
    "canonical_note_mutation_allowed": False,
    "portfolio_mutation_allowed": False,
    "deployment_authority_allowed": False,
    "owner_approval_inferred": False,
    "trade_or_account_action_allowed": False,
    "paper_order_action_allowed": False,
    "sizing_sleeve_cash_risk_rule_mutation_allowed": False,
}

# Capture workers: each entry is (worker_id, script, tickers).
# Workers are disjoint — each ticker appears in exactly one worker.
WORKERS: list[tuple[str, str, list[str]]] = [
    ("W1", "goog_official_ir_capture.py", ["GOOG"]),
    ("W2", "tech_official_ir_capture.py", ["AMZN", "MSFT", "NVDA"]),
    ("W3", "priority_official_ir_capture.py", ["BRK.B", "GS", "JPM", "LMT", "RTX", "XOM"]),
    ("W4", "etn_vrt_official_ir_capture.py", ["ETN", "VRT"]),
    ("W5a", "batch2_official_ir_capture.py", ["AMD", "CAT", "CVX", "PLTR"]),
    ("W5b", "batch2b_official_ir_capture.py", ["GE", "LLY", "META", "PH"]),
    ("W6", "longtail_official_ir_capture.py", [
        "BKNG", "CME", "ECL", "KTOS", "LIN", "LNG", "NFLX", "SMCI", "TMUS", "VMC", "WMB",
    ]),
]

POST_MERGE_STEPS = [
    {
        "step": "validate_all",
        "script": "official_ir_capture_validator.py --all --write",
        "purpose": "Verify authority-clean coverage across all captures after parallel workers complete.",
        "depends_on": "all_workers_complete",
    },
    {
        "step": "registry_refresh",
        "script": "official_capture_period_registry.py --write",
        "purpose": "Refresh the period registry/latest-selector to reflect any new captures.",
        "depends_on": "validate_all",
    },
    {
        "step": "reconciliation_refresh",
        "script": "fundamental_ir_reconciliation_packets.py --write",
        "purpose": "Rebuild IR reconciliation packets from updated captures via registry.",
        "depends_on": "registry_refresh",
    },
    {
        "step": "bridge_refresh",
        "script": "official_earnings_bridge.py --write",
        "purpose": "Rebuild official earnings bridge from updated reconciliation packets.",
        "depends_on": "reconciliation_refresh",
    },
]

SEQUENCING_RULES = [
    "All workers (W1–W6) may run in parallel. Each writes to disjoint per-ticker files under tmp/official-ir-captures/.",
    "No worker may write to another worker's output path. Ticker sets are non-overlapping.",
    "Post-merge steps run sequentially after all workers complete, in the order listed.",
    "If any worker exits non-zero, stop and diagnose before running post-merge steps.",
    "The registry/validator post-merge step is the authority gate; no downstream consumer should run until it passes.",
    "Parallel execution does not change authority boundaries: all outputs remain review-only.",
]

COLLISION_SAFETY = [
    "Each capture script writes one file per ticker (e.g., goog-q1-2026.json). No two workers share a ticker.",
    "The validator (post-merge) scans all captures atomically after workers complete — not concurrently.",
    "The registry selector runs after the validator, so latest_by_ticker always reflects the post-merge validated set.",
    "Period-slug collisions (two workers writing the same ticker+period) are prevented by the disjoint ticker assignment.",
]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def build_runbook() -> dict[str, Any]:
    worker_records = []
    all_tickers: list[str] = []
    for worker_id, script, tickers in WORKERS:
        all_tickers.extend(tickers)
        worker_records.append({
            "worker_id": worker_id,
            "script": script,
            "tickers": sorted(tickers),
            "ticker_count": len(tickers),
            "can_run_parallel_with": [w for w, _, _ in WORKERS if w != worker_id],
            "output_files": [f"tmp/official-ir-captures/{t.lower().replace('.', '_')}-<period>.json" for t in tickers],
        })

    # Verify disjoint
    assert len(all_tickers) == len(set(all_tickers)), "Worker ticker sets overlap — runbook is invalid"

    return {
        "generated_at_utc": utc_now(),
        "workflow": "WF70 Official Company Source Capture and Reconciliation",
        "phase": "6 — parallel capture runbook",
        "status": "ok",
        "authority": AUTHORITY,
        "summary": {
            "total_tickers": len(all_tickers),
            "workers": len(WORKERS),
            "post_merge_steps": len(POST_MERGE_STEPS),
        },
        "workers": worker_records,
        "post_merge_steps": POST_MERGE_STEPS,
        "sequencing_rules": SEQUENCING_RULES,
        "collision_safety": COLLISION_SAFETY,
        "consumer_contract": (
            "Run all workers, then validate_all, then registry_refresh, then reconciliation_refresh, "
            "then bridge_refresh. Downstream consumers (capital recommendations, daily review objects, "
            "dashboards) should not run until bridge_refresh completes clean."
        ),
    }


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(path)


def write_md(path: Path, data: dict[str, Any]) -> None:
    lines = [
        "# WF70 Phase 6 — Parallel Capture Runbook",
        "",
        f"Generated: `{data['generated_at_utc']}`",
        "",
        "Review-only. No source fetches, canon/portfolio mutations, trades, orders, or authority widening.",
        "",
        "## Summary",
        "",
        f"- Total tickers: {data['summary']['total_tickers']}",
        f"- Workers: {data['summary']['workers']}",
        f"- Post-merge steps: {data['summary']['post_merge_steps']}",
        "",
        "## Workers (run in parallel)",
        "",
        "| Worker | Script | Tickers |",
        "|---|---|---|",
    ]
    for w in data["workers"]:
        lines.append(f"| {w['worker_id']} | `{w['script']}` | {', '.join(w['tickers'])} |")
    lines += [
        "",
        "## Post-Merge Steps (run sequentially after all workers complete)",
        "",
        "| Step | Script | Depends on |",
        "|---|---|---|",
    ]
    for s in data["post_merge_steps"]:
        lines.append(f"| {s['step']} | `{s['script']}` | {s['depends_on']} |")
    lines += [
        "",
        "## Sequencing Rules",
        "",
    ]
    for rule in data["sequencing_rules"]:
        lines.append(f"- {rule}")
    lines += [
        "",
        "## Collision Safety",
        "",
    ]
    for item in data["collision_safety"]:
        lines.append(f"- {item}")
    lines += [
        "",
        "## Consumer Contract",
        "",
        data["consumer_contract"],
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    data = build_runbook()
    write_json(OUT_JSON, data)
    write_md(OUT_MD, data)
    print(f"wrote {OUT_JSON.relative_to(ROOT)}")
    print(f"wrote {OUT_MD.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
