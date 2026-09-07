# HEARTBEAT.md - main

Profile revision: `2026-09-04.role-bound-models.v4`.

No autonomous heartbeat work is authorized for this isolated agent.

- Act only when Main assigns a bounded task or the runtime invokes an already-authorized task.
- Do not create cron schedules, enable heartbeats, change runtime/config, or initiate cross-agent/external activity.
- On an unscoped invocation, return no action and wait for Main routing.
