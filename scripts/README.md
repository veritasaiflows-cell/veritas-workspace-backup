# Supported Scripts

This directory contains active automation and validators. Source files are not authority by themselves; use the owning doctrine, skill, playbook, contract, and workflow lifecycle.

## Finance: alerts and recommendations only

The supported finance chain is:

```text
guarded SQL → explicit active-symbol quote proof → alert freshness/suppression → non-executing digest
```

Primary commands:

```powershell
python scripts\finance_sql_canon_access.py --write --validate
python scripts\intraday_quote_snapshot_proof.py --symbols ETN JPM NVDA GOOG MSFT GS VRT BRK.B XOM LMT RTX AMZN CAT LLY CVX PLTR AMD LNG --timeout-seconds 15
python scripts\alert_level_freshness_controller.py --write --validate
python scripts\finance_alert_os_digest.py --mode morning --write --write-md --validate
python scripts\run_alerts_recommendations_chain.py morning --timeout-seconds 120 --write --validate
python scripts\alerts_os_pivot_validator.py --write --validate
```

The chain also supports `midday`, `post-close`, and `weekly`. Delivery requires a separately authorized caller and is never implied by a clean local proof.

Static reference levels come only from guarded canon. Scripts must not rederive or auto-apply them. Closed-market or last-completed-session quotes are monitor-only; they must not fire a fresh intraday alert.

The finance OS does not own or maintain sleeves, holdings, positions, allocations, weights, sizing, tranches, cash, rebalancing, simulated positions, approval/order packages, brokerage/account state, or execution routes. Historical scripts may remain for audit or compatibility only when their active lifecycle is explicitly retired and no enabled producer or consumer reaches them.

## Workflow and status

```powershell
python scripts\workflow_router.py WF## --answer summary
python scripts\workflow_routing_index.py --write --validate
python scripts\status_card_packet.py --write --write-md --validate
python scripts\status_card_freshness_runner.py --write --validate
```

## Cron control

```powershell
python scripts\cron_operator_ledger.py --write --write-md --validate
python scripts\cron_contract_validator.py --require-contracts --fail-on-drift --write --validate
python scripts\cron_freshness_spine.py --write --validate
python scripts\cron_control_packet.py --write --validate
```

Cron proof generation is not permission to add, edit, enable, disable, reschedule, force-run, or deliver a job.

## Memory, wiki, and artifact proof

```powershell
python scripts\semantic_memory_maintenance.py --max-seconds 600 --batch-size 16 --write --validate
python scripts\artifact_index.py validate
python scripts\workflow_hygiene_check.py --write --validate
```

Indexes, caches, wiki pages, and generated packets are routing or proof surfaces. They do not outrank owner canon or grant approval.

## Development rules

- Prefer explicit inputs, outputs, freshness limits, lineage, and fail-closed validation.
- Default to read-only behavior; write only the declared derived artifact or exact approved owner surface.
- Keep secrets out of output and tests.
- Preserve truthful warnings; do not convert missing or stale evidence into a cosmetic green.
- Add focused regression tests for every repaired failure mode.
- Use `--help` only after confirming the target script handles it without side effects.
- Retire obsolete routes instead of documenting them as supported compatibility commands.
