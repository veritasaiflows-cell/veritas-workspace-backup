<!-- GENERATED REVIEW-ONLY SURFACE
Source JSON: tmp/human-facing-truth-surface.json
Generated: 2026-05-31T16:56:13Z
Authority: orientation only; not canon, approval, archive apply, delete apply, portfolio mutation, paper/live order, account action, or money movement.
-->

# Executive Brief

## Bottom line

This is the single fast human-facing truth surface for Randall and Veritas. It routes to the live proof owners and replaces scattered dashboard pickup notes as the first read.

- Status: **review_only_ok**
- Generated: `2026-05-31T16:56:13Z`
- Finance SQL state: `ok` with `42` universe rows, `42` current ticker cards, and `42` latest valid entry/stop refs.
- SQL canon promotion: expanded authority is `False`; full SQL canon migration allowed is `False`.
- Core human folders 01-05: `23` live files, `0` eligible archive candidates, `1` blocked archive candidate, `0` compression targets.
- Live-surface migration: `ok`; earnings `9`, parser-compatible surfaces `2`, audit surfaces `1`, archived originals verified `12`.
- Archive delete posture: `planned_delete_blocked_requires_future_exact_approval`; delete allowed now count is `0`.

## Authority boundary

This surface is review-only. It does not grant owner approval, canonical portfolio mutation, archive apply, delete apply, paper/live execution, brokerage/account action, sizing, sleeve, cash, risk-rule, customer delivery, or money-movement authority.

## Validator posture

- Artifact index: `ok`
- Workspace boundary: `ok`
- Dashboard truth lint: `ok` with `0` warnings
- Workflow hygiene: `warning` with blocking count `0`
- Heartbeat continuation candidates: `ok`, handoff-ready `5`, blocked `0`

## Canonical routes

- **live finance/ticker proof** -> `tmp/finance-intelligence-state.sqlite and tmp/ticker-intelligence-cards/`
- **portfolio posture/model** -> `03. Portfolio/Portfolio Snapshot.md`
- **entry bands/stops/deployment state** -> `03. Portfolio/Execution Board.md compact parser surface + state/finance/execution-board-replacement.json`
- **research universe/watchlist** -> `04. Research/Coverage and Watchlist.md compact parser surface + state/finance/coverage-watchlist-replacement.json`
- **post-earnings scorecard lookup** -> `05. Intelligence/Earnings/README.md + state/finance/earnings-scorecard-index.json`
- **macro and regime** -> `02. Markets/Macro Regime Dashboard.md plus tmp/macro-*.json artifacts`
- **workflow status** -> `06. Playbooks/Active Workflows.md and owning continuity notes`
- **archive/delete posture** -> `tmp/core-folders-flattening-watchdog.json and tmp/archive-delete-readiness-plan.json`

## Remaining residue

- **blocked_archive_candidate**: `1`. Remove or update blocking script/control-surface references before moving.
- **delete_blocked**: `None`. Run retention/restore proof before any future delete helper exists.

## Next actions

- Keep the new compact live surfaces parser-compatible while continuing to route source-open history through state/finance replacement proof and archive paths.
- Keep delete blocked until archived-file retention, restore drill, replacement proof, and a separate exact delete approval exist.
- Run the watchdog after each finance-chain or weekly hygiene pass so folders 01-05 stay flat.

## Source proof

- `finance_state_validation` -> `tmp/finance-intelligence-state-validation.json` (exists `True`, status `ok`, generated `2026-05-31T04:57:00Z`)
- `core_folder_watchdog` -> `tmp/core-folders-flattening-watchdog.json` (exists `True`, status `no_archive_candidates_ready`, generated `2026-05-31T06:58:14Z`)
- `core_live_surface_migration` -> `tmp/core-live-surface-migration.json` (exists `True`, status `ok`, generated `2026-05-31T06:26:17Z`)
- `archive_delete_readiness` -> `tmp/archive-delete-readiness-plan.json` (exists `True`, status `planned_delete_blocked_requires_future_exact_approval`, generated `2026-05-31T07:20:22Z`)
- `artifact_index_validation` -> `tmp/artifact-index-validation.json` (exists `False`, status `ok`, generated `2026-05-31T16:56:13Z`)
- `dashboard_truth_lint` -> `tmp/dashboard-truth-lint.json` (exists `True`, status `ok`, generated `2026-05-31T06:26:25Z`)
- `workspace_boundary_check` -> `tmp/workspace-boundary-check.json` (exists `True`, status `ok`, generated `2026-05-31T16:51:30Z`)
- `workflow_hygiene` -> `tmp/workflow-hygiene-check.json` (exists `True`, status `warning`, generated `2026-05-31T09:52:15Z`)
- `heartbeat_continuation_candidates` -> `tmp/heartbeat-continuation-candidates.json` (exists `True`, status `ok`, generated `2026-05-31T16:51:30Z`)
