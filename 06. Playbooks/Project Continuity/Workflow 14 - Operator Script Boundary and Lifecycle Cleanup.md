# Workflow 14 - Operator Script Boundary and Lifecycle Cleanup

## Objective
- Separate operator-only tooling from chain-active scripts where that improves clarity, then clean up stale or redundant operator report wrappers without breaking callers.

## Current State
- Workflow 14 is complete.
- `scripts/` now has an explicit operator boundary without breaking the stable CLI surface:
  - operator-only implementations moved behind `scripts/operators/`
  - root CLI entrypoints remain as thin compatibility wrappers where docs and operator habits already depend on those paths
  - `entry_band_fetch.py` now explains the JSX inline-embed pattern explicitly

## Last Meaningful Progress
- Completed evidence-first caller tracing before moving anything.
- Verified `call_log_sync.py` must remain in the root because the Sunday chain calls it directly.
- Verified `workbook_template.py` must remain in the root because `run_finance_refresh_chain.py --build-workbook` can call it as a manual packaging tail.
- Verified the PDF/PPT report wrappers are still active documented operator entrypoints across playbooks, skills, and `scripts/README.md`, so archiving them now would be guessing rather than cleanup.
- Post-chain hardening revalidated the boundary with clean live checks and normalized the lowercase workflow/audit filename residue to Title Case.

## Outstanding
- Workflow 14 residue is now explicit rather than hidden:
  - equity report wrapper retirement was not approved by evidence; they stay live
  - Workflow 15 remains the only named follow-on in this stream, and it is still deferred by design

## Blockers / Trust Gaps
- The compatibility-wrapper posture is intentional: clean enough to clarify ownership, conservative enough not to break the documented CLI surface.
- If future evidence shows the equity PDF/PPT wrappers are truly inactive, open a fresh archive packet instead of retroactively claiming this workflow should have removed them.

## Next Action
- Close Workflow 14 honestly.
- Leave Workflow 15 deferred unless a real performance/modularity pressure appears.

## Key Files
- `scripts/run_finance_refresh_chain.py` - authoritative chain-active caller map.
- `scripts/entry_band_fetch.py` - JSX embed explanation belongs here.
- `scripts/equity_visual_report.py` - likely canonical report generator after the path fix.
- `scripts/operators/README.md` - explicit operator-boundary index.

## Automation / Refresh Path
- Structural cleanup only after the low-risk hygiene pass proves stable.
- Keep archive moves explicit and backup-first.

## Closure State
- Status: honestly complete
- QC: passed
- Outcome:
  - moved operator-only implementations behind `scripts/operators/` for:
    - `apply_band_update.py`
    - `band_note_sync.py`
    - `daily_note_dedupe.py`
    - `post_earnings_scorecard.py`
    - `test_universe.py`
  - preserved root CLI compatibility wrappers so existing docs and prompts do not break
  - left `call_log_sync.py`, `workbook_template.py`, and the equity report scripts in place for evidence-based reasons
