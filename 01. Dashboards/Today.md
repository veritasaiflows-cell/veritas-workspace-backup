<!-- THIN HUMAN SURFACE
Backup before thinning: backups/sql-json-md-thinning/20260619T192613Z/01. Dashboards/Today.md
Structured owner: generated/read-only dashboard and finance proof packets.
Authority: orientation page only; no execution, owner approval, portfolio mutation, archive/delete/apply authority, or inferred approval.
-->

# Today

## Use

This dashboard is a human orientation pointer. It does not hand-maintain finance tables or current ticker state.

Use generated/read-only routes for live operating context:

- Startup brief: `python scripts\startup_brief_packet.py --write --validate`
- Workflow routing: `python scripts\workflow_router.py WF78 --answer all`
- SQL-generated/read-only finance guard: `python scripts\finance_sql_canon_access.py --write --validate`
- SQL-generated/read-only trade-grade readiness: `python scripts\trade_grade_os_freshness_cron_runner.py --write --validate`
- Cron control: `python scripts\cron_control_packet.py --write --validate`
- Lane status: `python scripts\concurrent_lane_manager.py --status --write --validate`

Generated/read-only dashboard files:

- `tmp/startup-brief-packet.json`
- `tmp/trade-grade-os-freshness-cron-runner.json`
- `tmp/cron-control-packet.json`
- `tmp/concurrent-lane-status.json`

## Boundary

Dashboard orientation does not approve capital deployment, paper/live execution, account changes, portfolio/canon mutation, schedule mutation, archive/delete/apply, or external delivery.

## Historical Trail

The pre-thinning Today page was preserved before this rewrite:

- `backups/sql-json-md-thinning/20260619T192613Z/01. Dashboards/Today.md`
