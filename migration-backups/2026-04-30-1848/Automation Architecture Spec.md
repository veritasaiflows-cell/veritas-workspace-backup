# Automation Architecture Spec

## Purpose

Define the first real architecture for scheduled and semi-automated Veritas OS operation.

This spec is not trying to maximize automation.
It is trying to make automation trustworthy, legible, and easy to expand later.

## Core principle

Automation should progress in this order:
1. generate fresh artifacts
2. generate useful review surfaces
3. provide gated apply helpers
4. expand autonomous maintenance only where trust is repeatedly proven

Do not skip steps.

## Current operating phases

### Phase 1 — Stable scheduled artifact generation
Allowed now.

### Phase 2 — Stable review surfaces and sync checklists
Allowed now.

### Phase 3 — Gated patch/apply helpers for narrow note sections
Allowed selectively when the mutation boundary is narrow and validation is clear.

### Phase 4 — Broader autonomous maintenance
Not yet allowed as a default posture.

## Authority model

### Canonical note layer
Human-readable notes remain canonical for judgment, interpretation, and final operating guidance.

Examples:
- `03. Portfolio/Technical Entry and Invalidation Sheet.md`
- `03. Portfolio/Deployment Trigger Sheet.md`
- `03. Portfolio/Portfolio Snapshot.md`
- `05. Intelligence/Earnings/`
- `05. Intelligence/Weekly Positioning Review.md`

### Machine-readable config and artifact layer
Scripts may produce and maintain structured artifacts and machine-readable config used for workflow acceleration.

Examples:
- `tmp/portfolio-config.json`
- `tmp/technical-refresh.json`
- `tmp/trigger-sheet.json`
- `tmp/positioning-ranking.json`
- `tmp/band-proposals.json`

### Presentation layer
Workbook, dashboard, and PDF outputs are operator surfaces and presentation surfaces, not canonical judgment.

Examples:
- `06. Playbooks/Workbooks/Veritas Operating Workbook.xlsx`
- `tmp/veritas-command-center.html`
- PDF products built from the note layer

## Workflow ownership by window

### Morning window
Owner:
- `scripts/run_finance_refresh_chain.py morning`

Job:
- pre-open readiness refresh
- rebuild macro, technical, regime, band-supporting, dashboard, and workbook export artifacts

Safe outputs:
- generated artifacts
- review surfaces
- status/checklist surfaces

Not safe yet:
- silent canonical note rewrites

### Post-close window
Owner:
- `scripts/run_finance_refresh_chain.py post-close`

Job:
- end-of-day refresh
- earnings timing refresh
- post-earnings prep staging
- dashboard/workbook refresh

Safe outputs:
- generated artifacts
- selective post-earnings prep packets
- review surfaces

Not safe yet:
- autonomous interpretation notes
- silent trigger-sheet doctrine changes in note layer

### Post-earnings window
Owner:
- `scripts/run_finance_refresh_chain.py post-earnings`

Job:
- event-driven packet refresh and selective sync preparation

Safe outputs:
- prep artifacts
- candidate note-target surfaces

Not safe yet:
- autonomous scorecard conclusions
- autonomous downstream note mutation without approval

### Sunday window
Owner:
- `scripts/run_finance_refresh_chain.py sunday`

Job:
- weekly rebuild
- macro/positioning/intelligence prep
- workbook/dashboard refresh

Safe outputs:
- refreshed artifacts
- weekly prep surfaces

Not safe yet:
- autonomous final weekly judgment note without review

## Schedule recommendation v1

### Weekdays
- One `morning` run before the working session.
- One `post-close` run after market close and data settlement.

### Sunday
- One `sunday` run before the weekly review session.

### Earnings follow-up
Default posture:
- do not create many per-ticker cron jobs yet
- rely on `post-close` and next `morning` first
- add isolated event jobs only when a specific workflow repeatedly proves it deserves one

## Safe automation boundary now

Allowed now:
- scheduled artifact generation
- scheduled chart/report generation
- scheduled workbook export generation
- scheduled dashboard generation
- scheduled review/checklist generation
- thin gated apply helpers

Still human-gated:
- canonical note rewrites
- interpretation-heavy note updates
- recommendation-bearing narrative changes
- high-consequence config changes where the rollback path is weak

## Trust gates before wider autonomy

Before expanding autonomy, verify all of the following:
- artifact freshness is explicit
- upstream source conflicts are visible
- one workflow window owns each output
- validation exists and is run after mutation-capable helpers
- canonical note ownership is explicit
- rollback or correction path is simple
- automation does not erase uncertainty language

If any gate is weak, do not widen autonomy.

## Band automation policy

### Current status
Current band workflow is in the correct semi-automated phase:
- `technical_refresh.py`
- `band_refresh.py`
- `entry_band_fetch.py --all-tracked --html`
- `generate_entry_band_status.py`
- `apply_band_update.py`
- `band_note_sync.py`

### Current allowed automation
- proposal generation
- review-surface generation
- thin sync-checklist generation
- human-gated application to machine config

### Not yet allowed by default
- silent canonical note rewrites
- auto-approval of proposed bands
- automatic recommendation-state promotion from mechanical bands alone

## Mechanism routing

### Use cron when
- timing matters
- the job is recurring
- the output is artifact generation or review preparation

### Use heartbeat when
- the task is lightweight maintenance only
- no exact schedule is required

### Use TaskFlow when
- the work spans detached tasks but still needs one owner context
- waiting state and resumable state matter

### Keep manual when
- the workflow is interpretation-heavy
- trust is weak
- the mutation surface is too broad

## Immediate next build targets

1. Define concrete cron schedule candidates for `morning`, `post-close`, and `sunday`
2. Add validation expectations per workflow window
3. Design the v2 band methodology spec
4. Decide where a gated note patch/apply helper is safe enough to introduce next

## Non-goals for this phase

- full autonomous portfolio management
- silent narrative rewriting of the note layer
- replacing judgment with formula theater
- scheduling every possible event just because it can be scheduled
