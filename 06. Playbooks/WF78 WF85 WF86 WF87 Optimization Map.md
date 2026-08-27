# WF78 / WF85 / WF86 / WF87 Optimization Map

Status: active implementation map as of 2026-06-21.

Authority: review-only workflow optimization. This map does not approve capital deployment, paper/live execution, brokerage/account action, money movement, customer output, canon/portfolio mutation, or owner approval inference.

## Primary Entry Points

Use `python scripts\wf78_intelligence_routing_v2.py --layer daily_core_v2 --write --validate` as the primary scheduled WF78 route/freshness proof.

Use `python scripts\wf78_daily_freshness_loop.py --phase <phase> --write --validate` only as the compatibility phase runner or targeted repair route.

Use `python scripts\wf78_intelligence_routing_v2.py --layer daily_core_v2 --dry-run --no-subprocess --write --validate` for fast structural proof without spawning child scripts.

Use `python scripts\wf78_scaleout_packet.py --write --validate` for the consolidated 100/101-200/201-500 scaleout route map.

Use `python scripts\wf78_ticker_import_gate.py --range 100 --validate` or `python scripts\wf78_ticker_import_gate.py --range 101-200 --validate` for route-preview facade checks. Preview validation verifies the backend script path, current backend proof artifact, and fail-closed `--validate` command shape without running an import. Do not use `--execute --apply` unless the backend import gate has an exact owner approval reference.

## Shared Modules

| Module | Purpose |
|---|---|
| `scripts\wf_runner_lib.py` | Shared time, path, JSON, subprocess, dependency-batch, and authority-scan primitives. |
| `scripts\wf_registry.py` | Central path/schema names for WF78/WF85/WF86/WF87 artifacts and cron contracts. |
| `scripts\wf_manifest.py` | Declarative WF78 daily steps, phase aliases, v2 layers, expected artifacts, and WF86/WF87 trigger policy. |

## Phase Map

| Phase | Use | Notes |
|---|---|---|
| `card_refresh` | Refresh ticker-card and price bridge context. | Review-only; no trade/customer output. |
| `tier_routing` | Rebuild Tier A/B/C route state and routing deltas. | V2 calls manifest steps directly, not the daily-loop black box. |
| `fundamentals` | Refresh/probe fundamental metrics. | Use only when the full refresh window can tolerate slower provider work. |
| `evidence_repair` | Resolve freshness, band, source-open, and repair-debt packets. | V2 `freshness` layer maps here. |
| `source_capture` | Build official-source and owner-lineage capture queues. | No registry apply authority from this map. |
| `owner_review` | Build review queues and proposals. | No capital/execution authority. |
| `wf84_sync` | Refresh canonical data-plane and decision-card proof surfaces. | SQL/data-plane proof only; not deployment approval. |

## V2 Layer Map

| Layer | Purpose | Backing |
|---|---|---|
| `preflight` | Cron and artifact-index health. | Explicit commands in `wf_manifest.py`. |
| `tier_routing` | Tier route state. | Direct manifest phase `tier_routing`. |
| `freshness` | Freshness/band/source repair. | Direct manifest phase `evidence_repair`. |
| `repair_scan` | Ranked repair queue checkpoint. | No-command checkpoint; `ledger_publish` owns the final daily movement ledger write. |
| `card_materialization` | Review-only card queue. | Explicit autonomous-routing card command. |
| `ledger_publish` | Durable routing event and movement ledger. | Explicit ledger commands. |
| `postflight` | Artifact-index refresh. | Explicit artifact-index commands. |

## Scaleout Route Map

| Route | Front Door | Authority |
|---|---|---|
| `100_review_monitor` | `wf78_ticker_import_gate.py --range 100 --validate` | Owner-approved historical review-monitor route; preview only unless backend apply has exact owner approval reference. |
| `101_200_review_monitor` | `wf78_ticker_import_gate.py --range 101-200 --validate` | Owner-approved historical review-monitor route; preview only unless backend apply has exact owner approval reference. |
| `201_500_reputation_batches` | `wf78_500_ticker_reputation_gate.py --write --write-db --validate` | Reputation/batch proof only; no import/apply authority. |
| `small_mid_cap_candidate_pass` | `wf78_small_mid_cap_scaleout_candidate_pass.py --write --validate` | Discovery only; no import/apply authority. |

## WF86 / WF87 Trigger Policy

WF87 is active, not retired. It has market-hours and command-center cron contracts.

WF86 shadow outputs are refreshed by WF86 shadow/reconciliation routes and surfaced mainly through `tmp\paper-autotrader\shadow-decisions.json` and `tmp\paper-autotrader\shadow-eligibility.json`, not only `tmp\wf86-*.json`. WF87 market-hours probes can surface the same readiness state, but WF87 is not the only WF86 refresh owner.

Treat WF86/WF87 as event/market-hours review systems unless a later cron contract explicitly changes cadence. A clean WF87 probe or command center remains evidence only, not approval or execution authority.

## Validation

Minimum structural proof:

```powershell
python -m py_compile scripts\wf_runner_lib.py scripts\wf_registry.py scripts\wf_manifest.py scripts\wf78_daily_freshness_loop.py scripts\wf78_intelligence_routing_v2.py
python scripts\test_wf_runner_lib.py
python scripts\test_wf78_pipeline_smoke.py
python scripts\test_wf78_orchestrator_compat.py
python scripts\wf78_intelligence_routing_v2.py --layer daily_core_v2 --dry-run --no-subprocess --write --validate
python scripts\wf78_scaleout_packet.py --write --validate
```

Cron-facing proof:

```powershell
python scripts\cron_contract_validator.py --write --validate
python scripts\changed_file_validator_router.py --write --validate
```
