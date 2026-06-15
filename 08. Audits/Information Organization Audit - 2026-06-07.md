# Information Organization Audit - 2026-06-07

## Scope

Audit of how information is organized and retrieved for:

- ticker finance intelligence
- workflow state
- PM implementation/control state
- daily cron and recurring operating surfaces
- derived indexes, SQLite caches, and generated proof artifacts

This audit is review-only. It grants no canon, portfolio, SQL-promotion, paper/live execution, account, external/customer, archive/delete, or owner-approval authority.

## Executive Finding

The workspace is not suffering from a lack of organization. It is suffering from too many valid surfaces being treated as peers.

The fix is not another broad registry. The fix is stricter front-door routing:

- tickers: `finance_intelligence_state.py ticker <TICKER> --pretty`
- workflows: `workflow_routing_index.py --route WF##` or `--sql-route WF##`
- PM work: `pm_implementation_job_queue.py --write --write-db --validate`
- daily cron pickup: `cron_freshness_spine.py` then `cron_signal_scorecard.py`
- broad proof lookup: `artifact_index.py incremental` then `artifact_index.py validate`

Generated artifacts should remain routed proof, not user-facing starting points.

## Evidence Snapshot

| Area | Evidence | Result |
|---|---|---|
| Workflow routing | `workflow_routing_index.py --write --write-db --validate` | 31 routes, SQLite integrity ok, 0 critical, 0 warning |
| PM queue | `pm_implementation_job_queue.py --write --write-db --validate` | 10 jobs, 9 ready, 1 blocked, 0 collision groups |
| PM program state | `pm_program_state.py --write --write-db --validate` | yellow, 14 lanes, 8 ready/complete, 1 blocked, 4 need validation |
| Ticker state | `finance_intelligence_state.py validate --pretty` | ok, 200 universe rows, 42 production answer-path rows, 158 thin review rows |
| Ticker artifacts | filesystem count | 200 ticker cards, 42 answer packets |
| Cron freshness | `cron_freshness_spine.py --write --validate` | warning only, 25 enabled jobs, 0 blocked, 9 require attention |
| Cron signal scorecard | `cron_signal_scorecard.py --write --validate` | ok, 31 signals, 11 require attention, 20 quiet success, 0 blocked |
| Truth surfaces | `truth_surface_inventory.py --write --validate` | ok, 20 major surfaces, 6 first-open routes, 1 archive candidate |
| Route latency | `route-efficiency-scorecard.json` | ok, 5 probes, 0 slow, 0 unavailable |
| DB lifecycle | `db_lifecycle_manifest.py --write --validate` | 31 DBs classified, 0 unknown, 0 integrity errors, 1 archive-ready after approval |

## Findings

### 1. Ticker Information Is Now Structurally Cleaner

The recent WF77 structure is correct:

- `finance_intelligence_state.py ticker <TICKER> --pretty` is the front door.
- `tmp/ticker-intelligence-cards/<TICKER>.current.json` is the current evidence card/cache.
- `tmp/ticker-answer-packets/<TICKER>.current.json` is a derived response cache.
- WF78 surfaces are operational repair/promotion/freshness-debt surfaces, not normal Q&A entry points.

This resolves the prior confusion between `artifact_index.py answer-packet`, ticker cards, and `finance_intelligence_state.py`.

Remaining issue: all 200 ticker cards exist, but only 42 are production answer-path rows and the validation still reports 200 stale ticker-card states. That means normal Q&A is easier, but promotion-quality finance answers still need source-open or repair routing.

Recommendation:

- Keep `finance_intelligence_state.py ticker` as the only default ticker lookup.
- Use answer packets only when fresh relative to the card.
- Use `artifact_index.py answer-packet <TICKER>` only for cache freshness inspection.
- Use WF78 only when a ticker needs repair, promotion review, owner-card prep, capital review, or freshness-debt resolution.
- Do not create a fourth ticker Q&A surface.

### 2. Workflow Information Is Well Indexed, But Active Workflows Is Too Dense

`Active Workflows.md` remains the live authority surface, and `workflow_routing_index.py` is a good derived lookup. Validation is clean.

The friction is readability, especially WF78. WF78 contains many valid repair/proof surfaces, but for normal operations it reads like a catalog rather than a route.

Recommendation:

- Keep `Active Workflows.md` as authority.
- Keep `workflow_routing_index.py` as the lookup front door.
- For each major WF, preserve three fields clearly:
  - front door
  - escalation surfaces
  - stop lines
- Do not expand WF rows with every secondary script unless that script changes the operator's next action.

### 3. PM Organization Improved After Proof Budgets

PM is now closer to the right shape:

- 10 implementation jobs
- 9 ready
- 1 blocked
- 0 collision groups
- validation budgets present: micro, narrow, shared, major
- closeout modes present: queue_only, pm_state, handoff, integration

This means not every implementation slice needs full integration closeout.

Recommendation:

- Keep PM as the implementation queue, not the historical memory layer.
- Continue using proof budgets instead of full validator chains for every job.
- Promote ad hoc implementation work into PM only when it becomes multi-pass, cross-surface, or likely to be resumed later.
- Avoid adding a separate ad hoc classifier unless repeated missed implementation work returns.

### 4. Daily Work Has Signal Classification, But Still Creates Review Noise

Cron is not blocked:

- 25 enabled jobs
- 0 blocked
- 20 quiet-success signals
- 11 attention signals

The daily problem is not failure; it is attention triage. Morning/post-close/main-session-required artifacts can look equally important unless the signal scorecard is used first.

Recommendation:

- Daily pickup order should be:
  1. `cron_freshness_spine.py --write --validate`
  2. `cron_signal_scorecard.py --write --validate`
  3. inspect only `requires_main_attention` items
  4. route resulting work through WF/PM/ticker front doors
- Do not treat every cron-generated warning as a new implementation job.
- Keep quiet-success artifacts out of main-session review unless they changed material state.

### 5. Artifact Index Is Useful, But It Is Sensitive To Write Ordering

During this audit, `artifact_index.py validate` blocked because workflow route artifacts were rebuilt after the last artifact-index incremental pass. When `fast_path_qa` and closeout wrote fresh files in parallel, the index could again look stale.

This is a workflow-ordering issue, not a broken artifact index.

Recommendation:

- Run artifact index validation only after all parallel writers finish.
- Treat this as the serialized closeout tail:
  - route/PM/cron/finance writers
  - `fast_path_qa.py --write --validate`
  - `artifact_index.py incremental`
  - `artifact_index.py validate`
  - `control_closeout_bundle.py --write --validate`
- Do not run artifact-index freshness validation in parallel with tools that write indexed artifacts.

### 6. Database Organization Is Classified, Not Chaotic

The DB lifecycle manifest found:

- 31 databases
- 50 sidecars
- 0 unknown databases
- 0 integrity errors
- 1 archive-ready DB after owner approval

This is not emergency sprawl. It is mostly derived/support storage with known lifecycle labels.

Recommendation:

- Do not archive/delete during implementation flow.
- Use DB lifecycle review as owner-decision cleanup only.
- Keep SQL/SQLite routes labeled as derived lookup unless an exact approved gate says otherwise.

### 7. TOOLS.md Is Close To Becoming Too Large

`TOOLS.md` is doing its job as the environment and routing front-door file, but it is at risk of becoming a runbook catalog.

Recommendation:

- Keep only durable front doors, command routes, and boundary notes in `TOOLS.md`.
- Move procedure detail into skills/playbooks.
- When a section exceeds a quick lookup role, replace detail with a single front door and escalation route.

## Recommended Operating Model

Use this hierarchy:

| Need | First surface | Escalate only when |
|---|---|---|
| Answer a ticker question | `finance_intelligence_state.py ticker <TICKER> --pretty` | source-open/material recommendation, stale packet/card, promotion/capital review |
| Find workflow status | `workflow_routing_index.py --route WF##` | route points to exact owner note/artifact |
| Pick implementation work | `pm_implementation_job_queue.py --write --write-db --validate` | job needs owner decision, blocked dependency, or cross-WF collision |
| Daily review | `cron_signal_scorecard.py --write --validate` | signal requires main attention |
| Broad proof lookup | `artifact_index.py incremental` + `artifact_index.py validate` | stale/missing index or material artifact drift |
| Cleanup DB/files | `db_lifecycle_manifest.py --write --validate` | owner approves archive/delete path |

## Priority Recommendations

1. Enforce the ticker front door. Do not let answer packets, cards, artifact index, and WF78 all compete as equal Q&A entry points.
2. Keep WF78 operational surfaces behind the WF78 route. They are repair machinery, not normal lookup UX.
3. Keep PM proof budgets live. They directly reduce implementation friction.
4. Serialize artifact-index closeout after parallel writers complete.
5. Trim `TOOLS.md` only by replacing procedural detail with front-door routes. Do not split it into another unmanaged catalog.
6. Add no new registry unless repeated missed routing happens after these front doors are used.

## Next Implementation Opportunities

### Low Overhead

- Add a small "daily pickup order" note to `TOOLS.md`.
- Ensure `fast_path_qa.py` continues to publish its ordered closeout chain.
- Keep ticker front-door wording in `TOOLS.md` and Active Workflows aligned.

### Medium

- Add per-WF `front_door`, `escalation_only`, and `stop_line_summary` fields to `workflow_routing_index.py` output if repeated route confusion returns.
- Add PM queue display filters by validation budget and closeout mode if cockpit review remains noisy.

### Avoid For Now

- Do not create a new mega-index.
- Do not create a new daily digest unless it replaces an existing one.
- Do not promote SQL or artifact caches into authority surfaces.
- Do not automate archive/delete cleanup without owner approval.

## Bottom Line

The information layer is strong enough. The efficiency gain comes from using the right first surface every time and keeping generated proof artifacts behind those front doors.

The workspace should optimize for route discipline, not more organization objects.
