# Workspace Route Map

Generated packets, SQL, indexes, wiki pages, and caches route proof; they do not replace canon or approval.

## Status And Startup

- Shallow status: `python scripts\status_card_packet.py --read-only --frontdoor --render --validate`
- Critical fallback: `python scripts\startup_brief_packet.py --write --validate`
- Post-compaction pickup: `python scripts\future_session_enhancement_packet.py --write --write-md --validate`

## Workflow And Continuity

- Named workflow: `python scripts\workflow_router.py WF## --answer summary|next|blockers|helper|all`
- Concurrent writes: `python scripts\concurrent_lane_manager.py --status --write --validate`
- Project handoff: `project-continuity-manager`
- Memory routing: `memory-continuity-manager`

## Graphs And Recall

- Graph scope: `scripts/graphify-out` is the only maintained code graph (daily freshness gate + weekly conditional refresh). Root `graphify-out` is on-demand reference only; skills graphs are unbuilt.
- Freshness first: `python scripts\memory_graph_maintenance.py --mode gate --write --validate`, then read `tmp\operational-graph-maintenance.json` (fresh means generated <24h ago with status ok).
- Health: `python scripts\lib\graphify_router.py health`
- Smallest lookup: `python scripts\lib\graphify_router.py --graph scripts query "<question>" --budget 1500`, `path "<A>" "<B>"`, or `affected "<node>"`.
- Never rebuild a graph to answer an ordinary request. On-demand refresh only when stale blocks the task: `python scripts\memory_graph_maintenance.py --mode refresh --max-seconds 600 --write --validate`. `rg` plus exact owner files is the fallback.
- Graph edges are derivation-only; verify against current source before material claims.

## Implementation And QA

- Intake: `task-intake-contract`
- Implementation: `disciplined-implementation`
- Changed-file proof: `python scripts\changed_file_validator_router.py --write --validate`
- Independent QA: `workspace-qa-pass`

## Workspace And Skills

- Structure/archive: `workspace-governor`
- Broad audit: `veritas-workspace-audit-orchestrator`
- Skill changes: Skill Workshop, then `python scripts\skill_workshop_body_guard.py --write --validate` and `openclaw skills check`

## Cron And Runtime

- Cron: `cron-automation-manager`
- Control proof: `python scripts\cron_control_packet.py --write --validate`
- Runtime: `openclaw-operator`
- Troubleshooting: `openclaw-troubleshooter`

## Finance Alerts And Recommendations

- Routing: `veritas-intelligence-effort-router`
- Guarded SQL: `python scripts\finance_sql_canon_access.py --write --validate`
- Direct chain: `python scripts\run_alerts_recommendations_chain.py midday --timeout-seconds 120 --write --validate`
- Pivot boundary: `python scripts\alerts_os_pivot_validator.py --write --validate`
- Canon: `03. Alerts and Recommendations`

Portfolio maintenance, paper operation, account state, order preparation, and execution are not active finance routes.

## Data And Windows

Use `SQLite` for database safety. Use native PowerShell, `rg`, explicit literal paths, and one-shell destructive operations.