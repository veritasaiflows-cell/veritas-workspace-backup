# Command Center UI / Navigation Audit - 2026-06-18

## Scope

Target reviewed:

- `10. Deliverables/Command Center/veritas-command-center.html`
- `10. Deliverables/Command Center/veritas-command-center-compact.html`
- `tmp/dashboard-data.json`
- `tmp/dashboard-presentation-view-model.json`
- `tmp/veritas-command-center-compact-reader.json`
- `apps/pm-control-cockpit` at `http://127.0.0.1:8765`
- WF routes: WF79, WF84, WF85, WF65, WF60-WF61

Boundary: audit and local review-only generated artifacts only. No canon/portfolio mutation, no capital deployment, no paper/live/account action, no public/customer output, no cron schedule mutation, and no owner approval inference.

## Executive Finding

The Command Center should be narrowed into a finance-first daily actionability surface. Its first screen should answer:

- Is the finance state current enough to use?
- What is actionable after the last refresh?
- What is capital-deployment-review-worthy, owner-gated, blocked, below-stop, or stale?
- What do fundamentals and macro currently allow or caveat?
- What proof artifact backs the read?

The local PM cockpit at `http://127.0.0.1:8765` should own workflow/operator/non-finance visibility: WFs, PM lanes, handoffs, closeout, SMB, Retail, Academy, SQL/control-plane, sources, authority, and generic notes/deliverables.

Current implementation is close but not clean:

- The compact Command Center route exists and validates.
- The full static Command Center still behaves like an all-in-one dashboard.
- The compact reader still contains a `workflow_pm` panel that belongs in the PM cockpit.
- The finance dashboard payload can lag fresher fundamentals/macro artifacts, making the actionability surface look stale even after some finance sources are fresh.

## Current State Proof

### Finance Command Center

- Full static deliverable: `10. Deliverables/Command Center/veritas-command-center.html`
- Size: about 2 MB.
- Current full navigation has 11 tabs:
  - Overview
  - Deployment
  - Technicals
  - Portfolio
  - Fundamentals
  - Earnings
  - Macro
  - Risk
  - Triggers
  - Decision Queue
  - Post-Earnings
  - Entry Bands
- The nav hint still says `1-9`, but the dashboard has more than 9 tabs.
- The compact view model validates with 8 panels and is only about `0.39%` of the legacy payload size.
- Compact panels:
  - `command_today`
  - `trust_and_freshness`
  - `deployment`
  - `market_macro`
  - `portfolio`
  - `technical`
  - `fundamentals_earnings`
  - `workflow_pm`

### Freshness / Actionability Reality

Recent local proof after refresh:

- `tmp/fundamental-metrics-current.json`: generated `2026-06-18T04:16:04Z`.
- `tmp/fundamental-metrics-validation.json`: generated `2026-06-18T05:13:27Z`, status `warning`, critical `0`, warnings `10`.
- `tmp/macro-signal-spine.json`: generated `2026-06-18T05:13:41Z`, status `warning`, validation `ok`.
- `tmp/macro-energy-supply.json`: generated `2026-06-18T05:13:41Z`, status `warning`, validation `ok`.
- `tmp/dashboard-data.json`: regenerated during this audit at `2026-06-18 05:52 UTC`; still reports exec freshness `stale`.
- `tmp/daily-review-objects-post-close.json`: generated `2026-06-16T20:51:55Z`.
- `tmp/market-intelligence-events-post-close.json`: generated `2026-06-16T20:51:52Z`.

This means the Command Center can show fresh fundamentals and macro caveats while still failing the daily actionability promise because daily review and market-intelligence queues are stale.

### PM Cockpit

Live local PM cockpit:

- `http://127.0.0.1:8765/health`: status `ok`, source count `130`, missing required `0`, stale required `0`.
- `npm run validate` in `apps/pm-control-cockpit`: status `ok`, source count `130`, missing required `0`, stale required `0`, SQL adapter `ok`.
- PM cockpit tabs already include:
  - Randall
  - Deliverables
  - Veritas PM
  - Lanes
  - Handoff
  - SMB
  - Retail
  - Workflows
  - Academy
  - SQL
  - Closeout
  - Sources
  - Authority

This is the right home for workflow and non-finance operating state.

## Findings

### P0 - Daily Actionability Is Not Yet Guaranteed

The Command Center cannot reliably answer "what is actionable after last refresh" unless the dashboard payload is regenerated after the finance refresh chain and after daily review/market-intelligence packets.

Evidence:

- Fundamentals and macro artifacts are fresh relative to the dashboard payload.
- Daily review and market intelligence post-close packets are from `2026-06-16`.
- `validate_dashboard_state.py` reports `overall_exec_status: stale` and `source_freshness: stale / review_required`.
- Deployment check shows no deployable-now names, but multiple owner-gated review buckets.

Required workflow implementation:

- WF84/WF85 should feed the daily finance state and answer/actionability queues.
- WF65 should feed the fundamentals current-read and warning caveats.
- WF60-WF61 should feed macro/energy current-read and caveats.
- WF79 should render the finance-first Command Center only after those inputs are refreshed.

Acceptance rule:

- The Command Center first screen is usable only when its generated timestamp is newer than the latest required finance input for the chosen operating window.
- If not, the first screen must say "refresh required before relying on actionability."

### P1 - Command Center Navigation Is Too Broad

The full dashboard is doing too many jobs. It mixes finance actionability, row-level proof, workflow focus, note freshness, authority, and operational state.

Recommended first-level finance nav:

1. Today
2. Capital
3. Fundamentals
4. Macro
5. Technicals
6. Portfolio
7. Earnings
8. Bands
9. Proof

Anything outside those categories should link out to the PM cockpit.

Specific cleanup:

- Remove `workflow_pm` from the compact finance reader.
- Remove or demote Workflow Focus from the finance first screen.
- Keep Daily Review and Market Intelligence only when they drive finance actionability.
- Move generic workflow freshness, non-finance notes, helper lanes, handoffs, source registry, closeout, academy, SMB, Retail, and SQL/control-plane operations to the PM cockpit.

### P1 - Human Labels Need To Replace Machine IDs

Compact panels currently expose machine IDs like `command_today`, `market_macro`, and `fundamentals_earnings`.

Recommended labels:

- `command_today` -> `Today`
- `trust_and_freshness` -> `Trust`
- `deployment` -> `Capital`
- `market_macro` -> `Macro`
- `portfolio` -> `Portfolio`
- `technical` -> `Technicals`
- `fundamentals_earnings` -> `Fundamentals`
- `workflow_pm` -> migrate to PM cockpit, not a finance tab

This is a UI clarity issue, not a data authority issue.

### P1 - Freshness Labels Need Window Awareness

After market close, 9-hour-old technical and market data may be acceptable for a post-close daily read but stale for intraday/premarket execution context.

Current UI uses a blunt stale/fresh posture. It should show:

- operating window: morning, midday, post-close, post-earnings, sunday
- data as-of timestamp
- next expected refresh
- stale for current window: true/false
- actionability allowed: yes/no/review-only

This avoids false panic after a normal post-close refresh and prevents stale intraday data from appearing actionable.

### P1 - Fundamentals And Macro Need To Be First-Screen Caveats

The daily finance view should surface:

- fundamentals validation: warning-only / critical count / named warning categories
- macro signal: posture and validation
- energy supply: validation and source caveat
- finance warning router: whether warnings are caveat-only or blocking

Current truth:

- Fundamentals: warning-only, critical `0`, warnings `10`.
- Foreign issuer IR required: ASML, SAP, TSM.
- Manual SEC period review: BBY, DE, GD.
- SEC companyfacts lag wait: BF-B, DECK, EA, MCK.
- Macro: warning-class defensive-review bias, validation ok.
- Energy: warning-class, validation ok, Baker Hughes fallback caveat required.

These should be visible in the Today/Trust strip, not buried in a table.

### P1 - Capital View Should Be A Decision Funnel, Not A Data Table

Current deployment proof is useful but too table-heavy for the primary view.

Current deployment-check summary:

- Deployable now: none.
- Promotion review: GOOG, ITA, LIN, NVDA, PH, VRT, XLB.
- Entry-policy review: RTX, VMC.
- Almost / pullback-only: ETN, GS, JPM, MSFT.
- Below stop: AMZN, CME, CVX, LNG, META, NFLX, PLTR, TMUS, XLC, XLE.

Recommended capital first screen:

- Deployable now
- Owner review
- Pullback/no-chase
- Below stop
- Blocked/stale
- Watch/research

Each bucket should show count, tickers, proof path, and the authority boundary: no approval or execution.

### P2 - Static Deliverable And Live Cockpit Need Different Promises

`10. Deliverables/Command Center/veritas-command-center.html` is a static shelf artifact. The PM cockpit is a live local app.

Serving-purpose contract:

- Static Command Center: finance daily snapshot and row-level drilldown after the finance refresh chain.
- PM cockpit: live local operator console for workflow, source health, lanes, handoff, closeout, SMB/Retail/Academy/SQL, and non-finance notes.

The static Command Center should not try to be the PM cockpit. The PM cockpit should not imply capital approval.

### P2 - PM Cockpit Subtitle Creates Scope Confusion

The PM cockpit page title/subtitle currently says "Veritas Command Center" and "Randall human finance view with Veritas PM proof and source health."

Recommended copy:

- Title: `Veritas PM Cockpit`
- Subtitle: `Local operator console for workflows, sources, lanes, handoffs, and proof health. Finance actionability lives in the Command Center snapshot.`

This will reduce confusion between the two surfaces.

## Proposed WF Ownership

| Surface | Owner WF | Purpose | Should Stay In Finance Command Center? | Should Move To PM Cockpit? |
|---|---:|---|---:|---:|
| Today actionability | WF79 + WF84/WF85 | First-screen finance state | Yes | No |
| Capital deployment buckets | WF85 + deployment check | Owner-gated review queue | Yes | No |
| Fundamentals current read | WF65 | Evidence and caveats | Yes | No |
| Macro / energy current read | WF60-WF61 | Evidence and caveats | Yes | No |
| Technical / bands | WF60-WF61 + deployment | Entry/no-chase context | Yes | No |
| Portfolio posture | Finance state | Context only, no mutation | Yes | No |
| Workflow status / lanes | WF79 PM cockpit | Operator control | Link only | Yes |
| SMB / Retail / Academy | WF75/WF79-SMB | Product/control-plane work | No | Yes |
| SQL/control-plane | WF72/WF73 | Read support and routing proof | Drilldown only | Yes |
| Non-finance notes | PM / Deliverables | Operating visibility | No | Yes |
| Sources / authority / closeout | PM cockpit | Trust and proof operations | Link only | Yes |

## Daily Finance View Contract

Create or enforce a daily finance actionability contract with these fields:

- `generated_at_utc`
- `operating_window`
- `market_data_as_of`
- `next_refresh_due`
- `actionability_status`
- `deployable_now_count`
- `owner_review_count`
- `pullback_only_count`
- `below_stop_count`
- `blocked_or_stale_count`
- `fundamentals_status`
- `fundamentals_warning_count`
- `macro_status`
- `macro_caveat`
- `energy_status`
- `energy_caveat`
- `source_freshness_status`
- `proof_artifacts`
- `authority_boundary`

This can be a small derived artifact, for example:

- `tmp/finance-daily-actionability-snapshot.json`

WF79 should render that snapshot first. The full dashboard should remain row-level drilldown.

## Recommended Implementation Slice

### Slice 1 - Finance Command Center Simplification

Owner: WF79 with WF84/WF85/WF65/WF60-WF61 inputs.

Changes:

- Make compact Command Center the default finance route.
- Rename machine IDs to human finance labels.
- Drop `workflow_pm` from the finance compact reader.
- Add a PM cockpit link for workflows/non-finance state.
- Add a first-screen Today strip:
  - actionability
  - capital bucket summary
  - fundamentals status
  - macro/energy status
  - source freshness
  - proof timestamp

Acceptance:

- `python scripts\dashboard_presentation_view_model.py --write --validate`
- `python scripts\dashboard_compact_shell.py --write --validate`
- `python scripts\validate_dashboard_state.py`
- `python scripts\deliverables_publisher.py --write --validate`

### Slice 2 - Daily Refresh Ordering

Owner: WF84/WF85 plus WF65 and WF60-WF61.

Required order:

1. Refresh market/technical/deployment inputs for the operating window.
2. Refresh fundamentals and validation.
3. Refresh macro signal and energy supply.
4. Refresh `finance_evidence_warning_router.py`.
5. Refresh daily review objects and market intelligence events.
6. Generate dashboard payload.
7. Generate compact shell.
8. Publish deliverable snapshot.

Acceptance:

- Command Center generated timestamp is newer than required finance inputs.
- Compact reader `stale_input_count` is `0`, or it explicitly blocks actionability.
- Finance warning router has `blocking_section_count=0` for caveat-only operation.

### Slice 3 - PM Cockpit Scope Cleanup

Owner: PM cockpit / WF79 operator view.

Changes:

- Rename the app title to `Veritas PM Cockpit`.
- Keep tabs for workflows, lanes, handoff, closeout, SMB, Retail, Academy, SQL, sources, authority, and deliverables.
- Add a visible link to the finance Command Center snapshot.
- Ensure non-finance notes and workflow status route here, not into the finance dashboard.

Acceptance:

- `cd apps\pm-control-cockpit; npm run validate`
- `GET http://127.0.0.1:8765/health` returns missing required `0` and stale required `0`.
- Workflow/SMB/Retail/Academy/SQL tabs remain local review-only.

## How To Ensure Both Surfaces Serve Their Purpose

Use a simple separation test:

1. If the question is "What can I do with capital today?" open the finance Command Center.
2. If the question is "What workflow, source, lane, handoff, or non-finance system state needs work?" open the PM cockpit.
3. If an item in the finance Command Center is not tied to a ticker, macro/sector state, deployment bucket, owner-gated capital review, fundamentals, technicals, or proof freshness, move it to PM cockpit.
4. If an item in PM cockpit implies capital deployment, execution approval, or portfolio mutation, downgrade it to proof/status language and link to the finance Command Center instead.

## Current Verdict

The architecture is directionally right:

- Compact Command Center exists and validates.
- PM cockpit is live and healthy.
- Authority boundaries are preserved.

But the product split is not yet clean:

- Finance Command Center still carries workflow/operator residue.
- Daily finance actionability can be stale even when fundamentals and macro are fresh.
- Non-finance workflow and note surfaces should move to the PM cockpit.
- The PM cockpit should be renamed/reworded so it does not compete with the finance Command Center.

Recommended next action: implement Slice 1 first. It is the smallest change that gives Randall a daily finance-first surface without losing row-level drilldown or PM operator visibility.
