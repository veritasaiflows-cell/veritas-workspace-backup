# Workflow 35 - Dashboard and Document Truth-Surface Integration

## Objective
- Make the folder architecture, dashboard layer, and document/read surfaces agree on truth ownership.
- Ensure humans and automation can tell the difference between canonical notes, generated machine companions, review packets, dashboards, and archive/history.

## Current State
- **Closed with follow-up on 2026-05-05.**
- The top-level finance domain structure is sound: `01. Dashboards`, `02. Markets`, `03. Portfolio`, `04. Research`, `05. Intelligence`, and `07. Risk` have clear broad ownership.
- The controlling rule is now explicit: dashboards summarize, route, and warn; they do not become canonical portfolio truth.
- The truth-owner map was recorded in the completion audit and inserted into the WF36 SQLite `owners` table.

## Last Meaningful Progress
- Finance-folder audit completed on 2026-05-05 and recommended no broad top-level reorg.
- Added and ran `scripts/dashboard_truth_lint.py`; latest `tmp/dashboard-truth-lint.json` returns `status: ok`.
- Completion audit: `08. Audits/WF35 Dashboard Truth-Surface Audit and Completion - 2026-05-05.md`.

## Scope
- define dashboard/document truth ownership map
- standardize generated-note companion handling (`*-machine.md`, dated machine snapshots, report sidecars)
- update read-stack documents and dashboard links so the operator path reflects canonical owner surfaces
- decide whether `Machine Views/` or naming-only governance is enough for recurring generated note companions
- ensure dashboard integration improves truth rather than adding another surface

## Out of Scope
- moving top-level finance domains
- merging `Watchlist`, `Portfolio Snapshot`, `Deployment Trigger Sheet`, or `Technical Entry and Invalidation Sheet`
- changing finance recommendation logic
- broad JSON schema normalization owned by Workflow 32
- command-center fresh-brief expansion owned by Workflow 23

## Preflight / Entry Checklist
- [ ] confirm Workflow 32 has not already changed JSON/note truth semantics
- [ ] inspect `Home.md`, `Executive Brief`, `This Week`, `Next Actions`, `Weekly Positioning Review`, `Macro Regime Dashboard`, `Watchlist`, `Portfolio Snapshot`, and `Risk Rules`
- [ ] inventory `*-machine.md` notes and dated dashboard machine variants
- [ ] identify every current read-stack surface that could be mistaken for canon

## Execution Posture
- `serial main-session`

## Owner Layer
- canonical dashboard orientation -> `01. Dashboards/Executive Brief.md`, `This Week.md`, `Next Actions.md`
- market truth -> `02. Markets/`
- portfolio/deployment truth -> `03. Portfolio/`
- research truth -> `04. Research/`
- event/briefing intelligence -> `05. Intelligence/`
- risk doctrine -> `07. Risk/`
- generated review companions -> explicitly subordinate machine-labeled notes or `tmp/` artifacts

## Review Window
- manual integration window after contract/truth-spine work
- not scheduled automation in v1

## Stop Lines
- a dashboard starts acting as canonical portfolio truth
- a machine companion can be mistaken for human-approved canonical state
- a proposed move breaks dated history navigation without a replacement
- the pass drifts into broad command-center feature expansion before truth ownership is locked

## Surface / Handoff Posture
- dashboard layer may summarize and link
- documents may explain owner hierarchy and review path
- canonical mutation remains with owner notes only
- machine notes remain review artifacts unless explicitly promoted by a human-controlled workflow

## Canonical Mutation Posture
- canonical finance-note mutation allowed only for ownership/disclaimer/link corrections, not investment judgment changes
- generated-note relocation or naming changes require reference checks and compatibility consideration

## Phased Completion Approach

### Phase 1 - Truth-owner map
- build a table of operator surfaces, owner layer, generated inputs, and allowed claims
- identify any duplicate/ambiguous claims across dashboard, market, portfolio, and intelligence notes

### Phase 2 - Generated-note governance decision
- choose naming-only discipline versus a `Machine Views/` subfolder for recurring generated note companions
- document the rule in `Notes Layer Governance Protocol` / `Workspace Structure Protocol`
- avoid moving files unless the benefit exceeds link churn

### Phase 3 - Dashboard/document integration
- update `Home.md` and read-stack notes so they point to owner surfaces and warn where a surface is summary-only
- update `Executive Brief` / `Next Actions` only where current wording could imply false canon
- ensure dashboards link to supporting artifacts without outranking them

### Phase 4 - Validation and closeout
- run reference/link checks for any moved/renamed notes
- inspect dashboard/read-stack after edits
- run a bounded workspace QA pass or independent audit
- name residual dashboard truth risks honestly

## Acceptance Gates
- every major dashboard/document surface has an explicit owner role or subordinate summary posture
- generated note companions are consistently marked, placed, or documented
- `Home.md` and the fast operator read stack route to the correct canonical surfaces
- no dashboard or machine companion presents itself as the source of portfolio truth
- integration is reflected in both dashboard-facing notes and governance documents

## Exit / Closeout Checklist
- [ ] truth-owner map completed
- [ ] generated-note policy decision recorded
- [ ] dashboard/document updates applied if needed
- [ ] reference checks completed for any moves/renames
- [ ] independent QA/audit pass completed or explicitly deferred with reason
- [ ] checkpoint decision recorded

## Checkpoint Decision
- checkpoint recommended with the WF34-WF36 hardening batch after final queue/registry verification

## Next Pass
- Closed with follow-up. WF36 keeps the owner map queryable; WF32 should keep JSON/dashboard vocabulary aligned in the next finance-surface pass.

## Next 1-2 Adjacent Candidate Workflows
- Workflow 23 - Command Center Fresh Brief and Decision Surface Tightening
- Workflow 32 - Finance Surface Contract and JSON Spine Normalization

## Key Files
- `Home.md`
- `01. Dashboards/Executive Brief.md`
- `01. Dashboards/This Week.md`
- `01. Dashboards/Next Actions.md`
- `05. Intelligence/Weekly Positioning Review.md`
- `02. Markets/Macro Regime Dashboard.md`
- `02. Markets/Watchlist.md`
- `03. Portfolio/Portfolio Snapshot.md`
- `03. Portfolio/Deployment Trigger Sheet.md`
- `03. Portfolio/Technical Entry and Invalidation Sheet.md`
- `05. Intelligence/Weekly Intelligence Brief.md`
- `06. Playbooks/Notes Layer Governance Protocol.md`
- `06. Playbooks/Workspace Structure Protocol.md`
