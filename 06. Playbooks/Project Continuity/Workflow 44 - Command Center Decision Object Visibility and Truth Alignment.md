# Workflow 44 - Command Center Decision Object Visibility and Truth Alignment

## Objective
- Make `tmp/veritas-command-center.html` a fuller decision surface by rendering the key generated decision objects that already exist in `tmp/`.
- Preserve owner-gated, review-only, non-canonical boundaries.

## Current State
- Queued from `08. Audits/Command Center Full Truth Alignment Audit - 2026-05-09.md`.
- Current verdict: dashboard validation and acceptance are clean, but the Command Center is not fully truth-aligned because important decision objects are missing or under-rendered.

## Last Meaningful Progress
- Audit confirmed `tmp/veritas-command-center.html` exists and current validators pass.
- Audit found ETN promotion review, daily review objects, market-intelligence escalations, owner-state/technical-risk layering, authority vocabulary, and run-summary execution ambiguity gaps.
- 2026-05-09 bounded WF44 slice implemented first-class Promotion Review visibility and a review-only Decision Queue / Daily Intelligence tab.
- `tmp/dashboard-data.json` now carries `deployment_summary.promotion_review=["ETN"]`, `today_action.promotionReview=["ETN"]`, `trigger_sheet.summary.promotion_review=["ETN"]`, and `decision_queue` blocks for daily-review and market-intelligence artifacts.
- Main-session QC reran `python scripts\generate_dashboard.py`, `python scripts\validate_dashboard_state.py --write`, `python scripts\test_dashboard_acceptance.py`, `python scripts\dashboard_truth_lint.py`, and direct dashboard-data / HTML inspection. Result: validation clean, acceptance 18/18, truth lint ok, decision queue rendered with review-only / owner-approval-required language.

## Outstanding
- Preserve dual-layer owner state plus technical risk for repair/do-not-touch names such as LMT in a follow-up pass; this slice intentionally did not broaden into owner/risk precedence.
- Keep monitoring that future generated dashboard refreshes preserve Promotion Review and Decision Queue rendering.

## Blockers / Trust Gaps
- Do not treat clean dashboard validation as proof the Command Center is globally decision-complete; the LMT-style dual-layer risk/owner-state slice remains open.
- Do not let rendered UI imply canonical note mutation, trade execution, portfolio mutation, deployment-state mutation, or owner approval.

## Next Action
- Queue or implement the LMT dual-layer owner/risk visibility follow-up after higher-priority stale-source fail-soft work, unless Randall wants WF44 fully closed first.

## Key Files
- `08. Audits/Command Center Full Truth Alignment Audit - 2026-05-09.md` - source audit.
- `tmp/veritas-command-center.html` - rendered target.
- `tmp/dashboard-data.json` - embedded data source.
- `tmp/daily-review-objects-post-close.json` - missing decision objects.
- `tmp/market-intelligence-events-post-close.json` - missing escalation objects.
- `scripts/dashboard_payload.py` - payload owner.
- `scripts/dashboard-js/04-overview.js` - overview rendering owner.
- `scripts/dashboard-js/11-triggers.js` - trigger summary rendering owner.
- `scripts/test_dashboard_acceptance.py` - acceptance owner.

## Acceptance Gate
- [passed] Rendered Command Center shows Promotion Review with ETN distinctly from deployable-now and almost.
- [passed] Rendered Command Center shows current-window daily review counts/escalations and market-intelligence escalations.
- [pending follow-up] LMT-style names preserve owner do-not-touch/repair state while showing below-stop as secondary risk.
- [passed] Dashboard validation remains clean and acceptance tests explicitly cover the new visibility requirements.

## Automation / Refresh Path
- Remains generated from `scripts/generate_dashboard.py`; no canonical note mutation.
