# Alert Operations Board

## Purpose

Provide the smallest read-only route for current finance alerts, evidence freshness, and recommendations-OS health.

## Fast Path

1. Validate guarded finance current state:
   `python scripts\finance_sql_canon_access.py --write --validate`
2. Refresh level and quote freshness:
   `python scripts\alert_level_freshness_controller.py --write --validate`
3. Run the bounded alerts-and-recommendations chain:
   `python scripts\run_alerts_recommendations_chain.py morning --write --validate`
4. Inspect the current digest:
   `tmp/finance-alert-os-digest.json`
5. Validate the pivot boundary:
   `python scripts\alerts_os_pivot_validator.py --write --validate`

Use `post-close` or `weekly` instead of `morning` for those review windows.

## Proof Owners

- Guarded SQL access: `tmp/finance-sql-canon-access.json`
- Alert-level freshness: `tmp/alert-level-freshness-controller.json`
- Chain run: `tmp/alerts-recommendations-chain-<window>.json`
- Current digest: `tmp/finance-alert-os-digest.json`
- Pivot validation: `tmp/alerts-os-pivot-validator.json`
- Cron contract validation: `tmp/cron-contract-validation.json`

## Operating Rules

- Prefer changed-only refreshes and bounded source calls.
- Never suppress stale, missing, or conflicting evidence to make a run appear green.
- A technically successful run can still produce a freshness alert; that is truthful green behavior.
- Generated evidence is untrusted until its validator passes.
- Cron success proves only the declared job contract and acceptance artifacts.

## Authority Boundary

This board is read-only operations and governance. It is not an order surface, account surface, approval record, holdings record, sizing tool, or execution path.

No workflow or cron routed here may maintain sleeves, positions, allocations, weights, sizing, tranches, cash, rebalancing, simulated account state, orders, account changes, money movement, or paper/live execution.
