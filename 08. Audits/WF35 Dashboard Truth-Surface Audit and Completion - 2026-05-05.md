# WF35 Dashboard Truth-Surface Audit and Completion - 2026-05-05

## Plain-English verdict
WF35 is complete as a truth-architecture pass. The dashboard/read-stack structure is usable, but the rule must stay explicit: dashboards are navigation and summary surfaces, not portfolio canon.

## Owner map
- Dashboard/orientation only:
  - `Home.md`
  - `01. Dashboards/Executive Brief.md`
  - `01. Dashboards/This Week.md`
  - `01. Dashboards/Next Actions.md`
  - dated dashboard snapshots under `01. Dashboards/`
- Weekly operating stance:
  - `05. Intelligence/Weekly Positioning Review.md`
- Macro truth:
  - `02. Markets/Macro Regime Dashboard.md`
- Market universe / mirror, not thesis canon:
  - `02. Markets/Watchlist.md`
- Portfolio posture and allocation:
  - `03. Portfolio/Portfolio Snapshot.md`
- Deployment state and entry decision truth:
  - `03. Portfolio/Deployment Trigger Sheet.md`
- Technical discipline:
  - `03. Portfolio/Technical Entry and Invalidation Sheet.md`
- Risk doctrine:
  - `07. Risk/Risk Rules.md`

## What was risky
- Dated or generated dashboard artifacts can look fresher than canonical notes.
- Machine companions can be mistaken for approved truth if their subordinate status is not explicit.
- Technical notes can overlap deployment language if they do not route final deployable-state authority back to the trigger sheet.
- Dashboard summaries can become a second canon if they assert conclusions instead of routing to owner notes.

## Actions completed
- Added `scripts/dashboard_truth_lint.py` as a read-only dashboard truth linter.
- Wrote latest linter output to `tmp/dashboard-truth-lint.json`.
- Defined the owner map above as the controlling WF35 handoff.
- Fed the owner map into the WF36 SQLite schema as the `owners` table.
- Preserved the current folder layout; no broad dashboard/document move was justified.

## Current validation
`python scripts/dashboard_truth_lint.py` returns `status: ok`.

That means the current fast check found no active dashboard truth violations under the current lint rules. It does not mean historical dashboard packets are canon. Historical and machine outputs remain subordinate.

## Standing policy
- Dashboards may summarize, route, warn, and orient.
- Dashboards may not become canonical deployment, allocation, risk, or thesis truth.
- `*-machine.md` surfaces are generated companions / review evidence, not approved truth.
- Dated dashboard files are historical read packets unless explicitly refreshed and approved into an owning canonical note.
- If dashboard evidence conflicts with canon, the right wording is: **evidence changed; canonical note pending sync**.

## Stop lines preserved
- No dashboard gets to declare final deployable state.
- No generated companion becomes canon because it is newer.
- No summary note duplicates full trigger logic, allocation truth, or risk doctrine.
- No file moves were made where link churn would exceed benefit.

## Acceptance checklist
- [x] Truth-owner map completed.
- [x] Generated-note subordinate policy recorded.
- [x] Dashboard/document linter created and run.
- [x] Owner map integrated into SQL retrieval layer.
- [x] Dashboard surfaces remain summary/routing surfaces, not canon.
- [x] No broad top-level reorg needed.

## Completion status
**Closed with follow-up.**

Follow-up belongs to WF36 and later dashboard-generation work:
- WF36 keeps owner/freshness semantics queryable.
- Future dashboard generators should emit subordinate language automatically for machine companions.
- WF32 should keep JSON summary vocabulary aligned so dashboards cannot claim more than their source artifacts prove.
