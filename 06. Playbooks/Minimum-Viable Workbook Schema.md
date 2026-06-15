# Minimum-Viable Workbook Schema

## Purpose

Define the first implementation-ready schema for the Veritas operating workbook.

This document turns the broader workbook architecture into a buildable minimum-viable product.

Recommended workbook name:
- `Veritas Operating Workbook.xlsx`

Goal of MVP:
- improve weekly operating control
- expose drift and blockers quickly
- support post-earnings closure
- support capital-priority review

This is the first workbook to build.
It is intentionally narrow.

---

## MVP scope

Build only these 5 tabs in v1:
1. Control Panel
2. Watchlist Operating Board
3. Deployment Ranking
4. Earnings Workflow Tracker
5. Entry Bands and Technical Drift

Do **not** build all eight workbook tabs in the first pass.
That would slow delivery and increase schema drift.

---

## Shared design rules

- every tab uses a frozen header row
- every tab uses filters
- no merged cells in operating tables
- use controlled vocabularies only
- every row must have a stable primary key
- every derived field should document its source when feasible
- formulas should stay simple and auditable

Primary row key by tab:
- ticker for name-based tabs
- `ticker + quarter` for earnings tracker rows
- one-row KPI summary blocks for control panel

---

## Controlled vocabularies

### `board_state`
- Deployable
- Almost deployable
- Blocked
- Bench
- Repair
- Do not touch

### `earnings_state`
- Upcoming
- Reported, evidence pending
- Interpreted
- Synced
- Closed with follow-up

### `trust_grade`
- Clean
- Usable with caution
- Partial
- Stale

### `priority_bucket`
- Highest priority
- High priority
- Secondary
- Watch only
- No-action

### `review_flag`
- None
- Review needed
- Stale
- Blocked by catalyst
- Manual check required

---

## Tab 1 — Control Panel

### Purpose
One-screen operating summary for the current board state.

### Layout
Use two sections:
1. KPI summary block
2. active warnings / exceptions block

### KPI fields
| Field | Type | Source | Notes |
|---|---|---|---|
| refresh_timestamp | datetime | `tmp/dashboard-validation.json` or chain metadata | latest trusted refresh |
| validation_grade | enum | `tmp/dashboard-validation.json` | maps to trust grade |
| critical_count | integer | `tmp/dashboard-validation.json` | |
| warning_count | integer | `tmp/dashboard-validation.json` | |
| actionable_count | integer | `tmp/trigger-sheet.json` | count of deployable / near-deployable names by rule |
| blocked_count | integer | `tmp/trigger-sheet.json` | |
| extended_count | integer | `tmp/trigger-sheet.json` or technical artifact | names above disciplined entry range |
| repair_count | integer | `tmp/trigger-sheet.json` | includes repair / broken / do not touch |
| stale_band_count | integer | band/technical sources | names with stale or review-needed bands |
| near_earnings_count | integer | `tmp/earnings-calendar.json` | names inside blocker window |
| macro_regime | text | `tmp/macro-regime.json` | current regime label |
| policy_mode | text | `tmp/policy-expectations.json` | primary / mixed / manual |

### Exception block fields
| Field | Type | Source | Notes |
|---|---|---|---|
| warning_code | text | `tmp/dashboard-validation.json` | one row per major warning |
| severity | enum | same | critical / warning |
| summary | text | same | short readable summary |
| action_needed | text | derived/manual | what must be checked next |

### Hard rule
This tab is for triage only.
No long tables.
No research commentary.

---

## Tab 2 — Watchlist Operating Board

### Purpose
Structured summary of the tracked universe.

### Row key
`ticker`

### Required columns
| Column | Type | Source | Notes |
|---|---|---|---|
| ticker | text | canonical | primary key |
| company | text | watchlist / config | |
| coverage_tier | text | `04. Research/Coverage and Watchlist.md` | controlled values later if needed |
| sleeve | text | snapshot / config | portfolio theme / sleeve |
| board_state | enum | trigger/note layer | use controlled vocabulary |
| deployability_label | text | trigger sheet | short action posture |
| nearest_catalyst_date | date | earnings/events | closest material event |
| catalyst_type | text | earnings/events | earnings / macro / other |
| earnings_blocked | boolean | earnings + trigger logic | |
| thesis_status | text | note layer | intact / under review / weakened / broken |
| technical_freshness | enum | technical/band sources | none / review / stale |
| priority_bucket | enum | weekly positioning judgment | |
| canonical_note_pointer | text | note path | main note / scorecard / thesis home |
| last_sync_date | date | workflow output | |
| notes_short | text | manual short field | optional 1-line context |

### Hard rule
This sheet is summary-grade.
It must not become a duplicate thesis database.

---

## Tab 3 — Deployment Ranking

### Purpose
Rank limited-capital opportunities.

### Row key
`ticker`

### Required columns
| Column | Type | Source | Notes |
|---|---|---|---|
| ticker | text | canonical | primary key |
| board_state | enum | trigger sheet | |
| distance_to_band_pct | decimal | trigger/technical artifact | negative or positive allowed |
| entry_band_low | decimal | technical sheet / artifact | |
| entry_band_high | decimal | technical sheet / artifact | |
| technical_readiness | text | technical judgment | e.g. ready / extended / repair |
| earnings_catalyst_risk | text | earnings artifact | e.g. blocked / near / clear |
| macro_fit | text | macro/positioning judgment | e.g. favorable / mixed / poor |
| invalidation_clarity | text | technical/note layer | clear / moderate / weak |
| portfolio_role | text | snapshot / thesis | |
| priority_rank | integer | manual judgment rank | explicit ordering |
| priority_bucket | enum | derived from rank/judgment | |
| reason_for_rank | text | manual short rationale | required |
| next_trigger | text | note layer | what improves or breaks the case |

### Hard rule
This ranking is judgment-assisted, not formula-owned.
A spreadsheet score must not silently replace portfolio judgment.

---

## Tab 4 — Earnings Workflow Tracker

### Purpose
Track post-earnings closure cleanly.

### Row key
`ticker + quarter`

### Required columns
| Column | Type | Source | Notes |
|---|---|---|---|
| ticker | text | canonical | |
| company | text | canonical | |
| quarter | text | earnings artifact | e.g. Q1 2026 |
| report_date | date | earnings artifact / IR | |
| earnings_state | enum | workflow state | controlled vocabulary |
| ir_confirmed | boolean | manual / verified | |
| scorecard_created | boolean | note existence | |
| interpreted | boolean | scorecard completion | |
| board_synced | boolean | downstream sync complete | |
| follow_up_open | boolean | unresolved items remain | |
| next_required_action | text | workflow | required when not closed |
| owner_note | text | canonical note path | scorecard path |
| deployment_impact | text | short judgment | improved / unchanged / worsened |
| technical_impact | text | short judgment | |
| unresolved_issue | text | optional | |

### Hard rule
This tab should make half-finished earnings work impossible to miss.

---

## Tab 5 — Entry Bands and Technical Drift

### Purpose
Monitor band quality, freshness, and technical review burden.

### Row key
`ticker`

### Required columns
| Column | Type | Source | Notes |
|---|---|---|---|
| ticker | text | canonical | |
| current_price | decimal | technical artifact | |
| entry_band_low | decimal | technical sheet / artifact | |
| entry_band_high | decimal | technical sheet / artifact | |
| stop_invalidation | decimal/text | technical sheet | numeric where possible |
| distance_to_band_pct | decimal | derived | |
| stale_flag | boolean | band artifact | |
| review_flag | enum | band/technical judgment | controlled vocabulary |
| last_band_update | date | note/log | |
| note_owner | text | canonical note path | |
| posture | text | technical judgment | above band / in band / below band / broken |
| comments_short | text | optional | concise context only |

### Hard rule
This tab exists to surface drift.
If every row looks equally important, the tab failed.

---

## Suggested derived logic

### `priority_bucket`
- rank 1-2 -> Highest priority
- rank 3-5 -> High priority
- rank 6+ -> Secondary or below

### `technical_freshness`
- stale flag true -> Stale
- review flag set but not stale -> Review needed
- otherwise -> None

### `validation_grade`
- map directly from dashboard validation summary

Keep derived logic simple and reviewable.

---

## Import / export posture

### Near-term recommendation
Use structured exports from Python rather than manual workbook maintenance.

Preferred input pattern:
- JSON artifacts -> normalized CSV exports -> workbook tabs

Recommended future export files:
- `tmp/workbook-control-panel.csv`
- `tmp/workbook-watchlist-board.csv`
- `tmp/workbook-deployment-ranking.csv`
- `tmp/workbook-earnings-tracker.csv`
- `tmp/workbook-technical-drift.csv`

This is cleaner than trying to make Excel parse raw JSON directly.

---

## Acceptance criteria for MVP workbook

The MVP workbook is good enough only if it can answer these fast:
1. what is actionable right now?
2. what is blocked and why?
3. which earnings workflows are unfinished?
4. which bands are stale or under review?
5. where would capital go first if conditions improved?
6. is the trust layer clean or degraded?

If the workbook cannot answer those quickly, it is not ready.

---

## Recommended next implementation step

Build the schema first, then create the export layer.

Best order:
1. finalize workbook column schema
2. define export contracts from current artifacts
3. build workbook template
4. populate with exported structured tables
5. test against one real weekly cycle and one real post-earnings cycle

---

## Bottom line

The MVP workbook should behave like an operating console, not a vanity dashboard.

If it helps run the week, close earnings loops, and rank real opportunities, it worked.
If it becomes a second messy database, kill it.
