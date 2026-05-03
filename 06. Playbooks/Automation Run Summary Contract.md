# Automation Run Summary Contract

## Purpose

Define the machine-readable run-summary artifact for each scheduled or event-driven Veritas OS workflow window.

This contract exists to answer four questions cleanly:
1. did the window run
2. what actually completed
3. what trust state should downstream surfaces show
4. where should the operator stop trusting automation and review manually

## Scope

This contract applies to:
- `morning`
- `post-close`
- `post-earnings`
- `sunday`

It does not replace:
- `tmp/dashboard-validation.json`
- `tmp/dashboard-acceptance-report.json`
- `tmp/workbook-export-manifest.json`

Those remain source artifacts.
The run-summary artifact is the normalized workflow-level closure layer above them.

## Canonical artifact path

One file per workflow window:
- `tmp/run-summary-morning.json`
- `tmp/run-summary-post-close.json`
- `tmp/run-summary-post-earnings.json`
- `tmp/run-summary-sunday.json`

Optional future convenience alias:
- `tmp/run-summary-latest.json`

Do not collapse all historical windows into one mutable truth file in v1.
Per-window ownership is cleaner.

## Contract shape

```json
{
  "window": "morning",
  "run_id": "2026-05-01T12:45:00Z_morning",
  "generated_at_utc": "2026-05-01T12:52:14Z",
  "status": "warning",
  "stop_line": false,
  "owner": {
    "entrypoint": "python scripts/run_finance_refresh_chain.py morning",
    "window_owner": "scripts/run_finance_refresh_chain.py"
  },
  "timing": {
    "started_at_utc": "2026-05-01T12:45:00Z",
    "completed_at_utc": "2026-05-01T12:52:14Z",
    "duration_seconds": 434
  },
  "validation": {
    "acceptance_passed": true,
    "dashboard_validation_status": "warning",
    "critical": 0,
    "warning": 8,
    "info": 0,
    "exec_freshness": "usable_with_caution"
  },
  "outputs": {
    "command_center": { "status": "ok", "path": "tmp/veritas-command-center.html" },
    "dashboard_validation": { "status": "ok", "path": "tmp/dashboard-validation.json" },
    "dashboard_acceptance": { "status": "ok", "path": "tmp/dashboard-acceptance-report.json" },
    "workbook_exports": { "status": "ok", "path": "tmp/workbook-export-manifest.json" },
    "intelligence_note": { "status": "ok", "path": "01. Dashboards/Pre-Market Snapshot/2026-05-01.md" }
  },
  "warnings": [
    "Policy expectations still rely on fallback/manual elements",
    "Band review queue remains open"
  ],
  "blockers": [],
  "fallback_state": {
    "used": true,
    "reason": "policy expectations fallback source in effect"
  },
  "downstream": {
    "command_center_badge": "warning",
    "workbook_trust_grade": "warning",
    "presentation_allowed": false,
    "canonical_note_mutation_allowed": false
  }
}
```

## Required top-level fields

- `window`
- `run_id`
- `generated_at_utc`
- `status`
- `stop_line`
- `owner`
- `timing`
- `validation`
- `outputs`
- `warnings`
- `blockers`
- `fallback_state`
- `downstream`

## Status vocabulary

Allowed `status` values:
- `ok`
- `warning`
- `blocked`
- `error`

Use them narrowly:

### `ok`
- required outputs completed
- no critical validation failures
- warnings may be zero or trivial
- no stop line triggered

### `warning`
- required outputs completed
- no critical validation failures
- one or more visible warnings remain
- decision support may still be usable with caution

### `blocked`
- workflow completed partially or fully, but a stop line was triggered
- downstream surfaces must not present the run as ready
- operator review is required before relying on it

### `error`
- workflow failed to complete meaningfully
- one or more required outputs missing because the run broke
- downstream surfaces must show failed state, not stale confidence

## Stop-line rule

`stop_line: true` when any of the following are true:
- acceptance test failed
- dashboard validation artifact missing when required for the window
- command center render failed for windows that own it
- required intelligence note failed to write when that note is part of the window contract
- required staging artifact failed to write
- downstream output would otherwise look trustworthy while a core owner artifact is missing

A warning does not automatically imply stop line.
A blocked or error state does.

## Validation block

The `validation` object should normalize key facts from existing artifacts.

Required fields:
- `acceptance_passed`
- `dashboard_validation_status`
- `critical`
- `warning`
- `info`
- `exec_freshness`

Rules:
- source `acceptance_passed` from `tmp/dashboard-acceptance-report.json`
- source warning/critical/info counts from `tmp/dashboard-validation.json`
- `dashboard_validation_status` should mirror the window-level interpretation, not invent a second taxonomy
- `exec_freshness` may use existing values such as:
  - `ok`
  - `partial`
  - `stale`
  - `usable_with_caution`

## Output status block

Each required output for a window should be named explicitly.

Allowed per-output statuses:
- `ok`
- `missing`
- `partial`
- `failed`
- `not_applicable`

Rules:
- do not infer `ok` when the file is absent
- use `not_applicable` only when the output does not belong to that workflow window
- use `partial` when the artifact exists but carries explicit degraded or partial state

## Fallback state block

The run summary must preserve fallback honesty.

Required fields:
- `used` (boolean)
- `reason` (string or empty)

Examples:
- policy expectations fallback source in effect
- manual target-range dependency remains
- earnings timing confirmation still pending

If any meaningful fallback is active, this block should say so even if the overall status is still `warning` instead of `blocked`.

## Downstream policy block

The `downstream` object prevents every consumer from inventing its own trust rule.

Required fields:
- `command_center_badge`
- `workbook_trust_grade`
- `presentation_allowed`
- `canonical_note_mutation_allowed`

Rules:
- `presentation_allowed` is false by default in v1 unless the window status is `ok` and the specific product rules allow it
- `canonical_note_mutation_allowed` stays false by default in v1 for scheduled windows
- command center and workbook surfaces should consume this block rather than reinterpret warning counts differently

## Window-specific required outputs

### Morning
Required:
- `tmp/dashboard-validation.json`
- `tmp/dashboard-acceptance-report.json`
- `tmp/veritas-command-center.html`
- `tmp/workbook-export-manifest.json`
- pre-market snapshot if included in the live chain

### Post-close
Required:
- `tmp/dashboard-validation.json`
- `tmp/dashboard-acceptance-report.json`
- `tmp/veritas-command-center.html`
- `tmp/workbook-export-manifest.json`
- `tmp/post-earnings-prep.json`
- `tmp/post-earnings-note-targets.json`
- post-market snapshot when scheduled
- daily executive summary when scheduled

### Post-earnings
Required:
- `tmp/post-earnings-prep.json`
- `tmp/post-earnings-note-targets.json`
- validation artifact if dashboard generation is part of the run

### Sunday
Required:
- `tmp/dashboard-validation.json`
- `tmp/dashboard-acceptance-report.json`
- `tmp/veritas-command-center.html`
- `tmp/workbook-export-manifest.json`
- `tmp/weekly-macro-snapshot.json`
- `tmp/weekly-intelligence-brief.json`

## Failure-state propagation rules

These rules are the real plumbing standard.

### Rule 1 — One trust state fans out
The run summary becomes the workflow-level trust source for:
- command center status badge
- workbook control-panel trust state
- packaging eligibility
- scheduled-run review logging

Do not let each surface invent its own parallel state machine.

### Rule 2 — Missing required output beats cosmetic success
If a required output is missing, downstream surfaces must show `blocked` or `error` even if some later files still rendered.

Example:
- command center HTML exists
- dashboard validation artifact missing
- result must still downgrade, not display as healthy just because HTML rendered

### Rule 3 — Warning state stays visible
Visible warnings from validation artifacts must propagate into:
- command center warning block
- workbook control panel warning count
- any later packaging eligibility decision

Warnings are not noise.
They are part of the product.

### Rule 4 — Stop line disables presentation
If `stop_line` is true:
- do not mark workbook or PDF packaging as eligible
- do not mark the workflow window as clean decision support
- do not permit autonomous note mutation

### Rule 5 — Scheduled note mutation remains off by default
Even if status is `ok`, scheduled runs do not gain silent canonical note rewrite permission in v1.

### Rule 6 — Fallback honesty survives fan-out
Fallback/manual dependencies must remain visible downstream.
No consumer may translate fallback dependence into fake precision.

### Rule 7 — Event prep is not interpretation
`post-earnings` outputs must propagate as prep/candidate state only.
Do not let downstream surfaces imply interpreted completion when the workflow has not actually performed interpretation.

## Recommended implementation order

1. Create the run-summary writer after each workflow window finishes
2. Populate it from existing artifacts instead of replacing existing validators
3. Add command center consumption of run-summary status
4. Add workbook export consumption of run-summary status
5. Add packaging eligibility checks later
6. Keep canonical note mutation gates manual

## Non-goals

- replacing existing validation artifacts
- inventing a second truth layer for judgment
- using the run summary to justify autonomous recommendations
- hiding degraded runs behind a simplified green badge
